"""SavChunk 8: 201 × 58-byte city walkers.

Ghidra (findings/ghidra_walkers.md):

    BSS              0x1107A4
    SavChunk         8         11658 bytes
    stride           0x3A      = 58
    count            201       slot 0 exists; walker_spawn fills 1..200

    Draw (city_tile_draw_walker_sprites 0x382FB):
        rec[+0x34] indexes gfx_load_zoom_set slot 0 = LTLMEN{1,2,3}B.PL8
        (220 × 16×16 bitmaps at zoom 1). RO2SLGC / RO2SPRB / RO2SWDA are
        battle units (178 frames) — not this pool.

Hook — sibling owns city_map.render_iso / __main__:

    from app.walkers import overlay_walkers
    img = overlay_walkers(img, walkers, game)
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from app.city_map import (
    ISO_H,
    ISO_HALF_H,
    ISO_HALF_W,
    ISO_W,
    MAP_H,
    MAP_W,
    load_chunk_sizes,
    walk_sav_chunks,
)

WALKER_STRIDE = 0x3A  # 58
WALKER_COUNT = 201  # 0xC9
WALKER_BYTES = WALKER_STRIDE * WALKER_COUNT  # 11658
GHIDRA_BSS = 0x1107A4
SAV_CHUNK = 8

TYPE_MIN = 1
TYPE_MAX = 7

# walker_type_fn 0x45AFE..0x45D0A → walker_set_sprite(base).
# LTLMEN1B rows (sprite.y): 6=201, 2=226, 1=251, 5=276, 4=301, 7=326, 3=351.
TYPE_LTLMEN_BASE: dict[int, int] = {
    1: 0x36,  # 54
    2: 0x1B,  # 27
    3: 0xA6,  # 166
    4: 0x6E,  # 110
    5: 0x51,  # 81
    6: 0x00,
    7: 0x89,  # 137; state 12 uses 0; FUN_00047a95 may +0x1B/+0x1C
}

# gfx_load_zoom_set 0x107DB table @ 0x927D0, slot 0 per zoom set.
LTLMEN_BY_ZOOM: tuple[str, ...] = (
    "LTLMEN1B.PL8",
    "LTLMEN2B.PL8",
    "LTLMEN3B.PL8",
)

# RO2* are battle (FUN_00010AC9), not SavChunk 8. Kept so callers do not guess.
RO2_BATTLE_PL8: tuple[str, ...] = (
    "RO2SLGC.PL8",
    "RO2SPRB.PL8",
    "RO2SWDA.PL8",
)

STATE_FREE = 2


@dataclass(frozen=True)
class Walker:
    """One 58-byte city walker. Named fields match findings/ghidra_walkers.md."""

    slot: int
    occupied: int
    type: int
    facing: int
    x: int
    y: int
    tile_off: int
    x_frac: int
    y_frac: int
    dest_x: int
    dest_y: int
    next_state: int
    wait_timer: int
    state: int
    walk_frame: int
    on_road: int
    life_phase: int
    home_off: int
    home_walker: int
    sprite_id: int
    bob: int
    raw: bytes = field(repr=False, compare=False)

    @classmethod
    def unpack(cls, raw: bytes, slot: int = 0) -> Walker:
        if len(raw) != WALKER_STRIDE:
            raise ValueError(f"walker is {len(raw)} bytes, want {WALKER_STRIDE}")
        tile_off = struct.unpack_from("<i", raw, 6)[0]
        home_off = struct.unpack_from("<i", raw, 0x28)[0]
        sprite_id = struct.unpack_from("<h", raw, 0x34)[0]
        return cls(
            slot=slot,
            occupied=raw[0],
            type=raw[2],
            facing=raw[3],
            x=int.from_bytes(raw[4:5], "little", signed=True),
            y=int.from_bytes(raw[5:6], "little", signed=True),
            tile_off=tile_off,
            x_frac=raw[0xA],
            y_frac=raw[0xB],
            dest_x=int.from_bytes(raw[0xC:0xD], "little", signed=True),
            dest_y=int.from_bytes(raw[0xD:0xE], "little", signed=True),
            next_state=raw[0xE],
            wait_timer=raw[0xF],
            state=raw[0x10],
            walk_frame=raw[0x1F],
            on_road=raw[0x23],
            life_phase=raw[0x24],
            home_off=home_off,
            home_walker=raw[0x2C],
            sprite_id=sprite_id,
            bob=raw[0x36],
            raw=bytes(raw),
        )

    @property
    def live(self) -> bool:
        return self.occupied != 0 and TYPE_MIN <= self.type <= TYPE_MAX

    def ltlmen_index(self, *, camera: int = 0) -> int:
        """LTLMEN sprite. Prefer the saved id from walker_set_sprite."""
        if 0 <= self.sprite_id < 220:
            return self.sprite_id
        base = TYPE_LTLMEN_BASE.get(self.type, 0)
        rel = (self.facing - camera) % 8
        frame = self.walk_frame & 3
        extra = 0 if frame == 0 else (2 if frame == 2 else 1)
        return base + rel * 3 + extra


def unpack_pool(blob: bytes | memoryview) -> list[Walker]:
    if len(blob) != WALKER_BYTES:
        raise ValueError(f"chunk {SAV_CHUNK} is {len(blob)} bytes, want {WALKER_BYTES}")
    raw = bytes(blob)
    return [
        Walker.unpack(raw[i * WALKER_STRIDE : (i + 1) * WALKER_STRIDE], slot=i)
        for i in range(WALKER_COUNT)
    ]


def live_walkers(pool: Sequence[Walker]) -> list[Walker]:
    return [w for w in pool if w.live]


def drawable_walkers(pool: Sequence[Walker]) -> list[Walker]:
    """Occupied type 1–7, not state 2 (free), tile in 0..79."""
    return [
        w
        for w in pool
        if w.live
        and w.state != STATE_FREE
        and 0 <= w.x < MAP_W
        and 0 <= w.y < MAP_H
    ]


def load_walkers_from_sav(
    path: Path, sizes: Sequence[int] | None = None, *, game: Path | None = None
) -> list[Walker]:
    """Read SavChunk 8 from a real .SAV (same 500-chunk stream as city_map)."""
    data = path.read_bytes()
    if sizes is None:
        sizes = load_chunk_sizes(game if game is not None else path.parent)
    chunks = walk_sav_chunks(data, sizes)
    if SAV_CHUNK >= len(chunks):
        raise ValueError(f"only {len(chunks)} chunks; need index {SAV_CHUNK}")
    return unpack_pool(chunks[SAV_CHUNK])


def iso_origin_x(width: int = MAP_W) -> int:
    return (width - 1) * ISO_HALF_W


def tile_iso_xy(
    x: int, y: int, *, origin_x: int | None = None
) -> tuple[int, int]:
    """Diamond top-left. Same formula as city_map.render_iso."""
    if origin_x is None:
        origin_x = iso_origin_x()
    sx = origin_x + (x - y) * ISO_HALF_W
    sy = (x + y) * ISO_HALF_H
    return sx, sy


def walker_iso_xy(
    walker: Walker, *, origin_x: int | None = None
) -> tuple[int, int]:
    """Blit origin for a 16×16 LTLMEN: feet near the bottom-center of the tile."""
    sx, sy = tile_iso_xy(walker.x, walker.y, origin_x=origin_x)
    return sx + ISO_HALF_W - 8, sy + ISO_H - 18


def load_ltlmen_frames(
    game: Path, *, zoom: int = 0
) -> tuple[list[Image.Image], str]:
    from app.assets import load_pl8_frames

    name = LTLMEN_BY_ZOOM[max(0, min(zoom, 2))]
    frames, path = load_pl8_frames(game, name)
    return frames, path.name


def overlay_walkers(
    img: Image.Image,
    walkers: Sequence[Walker],
    game: Path,
    *,
    zoom: int = 0,
    sprites: Sequence[Image.Image] | None = None,
    camera: int = 0,
    origin_x: int | None = None,
) -> Image.Image:
    """Blit live walkers onto an existing iso city image.

    ``img`` must be the native ``render_iso`` canvas (not the 640×480 fit).
    Does not call ``city_map.render_iso``. Uses ``tools/decode_pl8.py`` via
    ``assets.load_pl8_frames`` — never copies a PL8 into git.

        from app.walkers import overlay_walkers
    """
    if sprites is None:
        sprites, _name = load_ltlmen_frames(game, zoom=zoom)
    n = len(sprites)
    if origin_x is None:
        # Match render_iso: origin from map width, not image width.
        origin_x = iso_origin_x(MAP_W)
        expected_w = origin_x + (MAP_W - 1) * ISO_HALF_W + ISO_W
        if img.width != expected_w:
            origin_x = (img.width - ISO_W) // 2

    out = img.convert("RGBA")
    for walker in drawable_walkers(walkers):
        idx = walker.ltlmen_index(camera=camera)
        if not (0 <= idx < n):
            continue
        spr = sprites[idx]
        px, py = walker_iso_xy(walker, origin_x=origin_x)
        out.paste(spr, (px, py), spr)
    return out
