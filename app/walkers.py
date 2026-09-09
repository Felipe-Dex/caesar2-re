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
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from app.city_map import (
    MAP_H,
    MAP_W,
    iso_tile_size,
    load_chunk_sizes,
    walk_sav_chunks,
    world_to_draw,
)

# LTLMEN{1,2,3}B bitmap size (type-0, not the iso diamond).
LTLMEN_SIZE_BY_ZOOM: tuple[int, ...] = (16, 8, 4)

WALKER_STRIDE = 0x3A  # 58
WALKER_COUNT = 201  # 0xC9
WALKER_BYTES = WALKER_STRIDE * WALKER_COUNT  # 11658
GHIDRA_BSS = 0x1107A4
SAV_CHUNK = 8

TYPE_MIN = 1
TYPE_MAX = 7
TYPE_RIOTER = 7  # C2.ENG [66]+6 " - Rioter"

# walker_type_fn 0x45AFE..0x45D0A → walker_set_sprite(base).
# LTLMEN1B rows (sprite.y): 6=201, 2=226, 1=251, 5=276, 4=301, 7=326, 3=351.
TYPE_LTLMEN_BASE: dict[int, int] = {
    1: 0x36,  # 54
    2: 0x1B,  # 27
    3: 0xA6,  # 166 City Only Enemy — 0x52828 edge spawn, not C3 wolves
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

# EXE walker_anim_* : walk_frame 0…15. Timer tables 0x9673E (road, all 2)
# and 0x96735 (pad, all 1) → 32 / 16 sim ticks per tile. Display is 50 ms
# (sim_tick_due unit). Play pulses every 200 ms @ speed 70, so a walk_frame
# lerp teleports; the slide is driven from real time instead.
DISPLAY_TICK_MS = 50
WALK_FRAMES_PAD = 16
WALK_FRAMES_ROAD = 32
WALK_DISPLAY_FRAMES = WALK_FRAMES_ROAD
WALK_MS_PER_TILE = WALK_FRAMES_ROAD * DISPLAY_TICK_MS  # 1600


@dataclass
class _Slide:
    x0: float
    y0: float
    x1: float
    y1: float
    facing: int
    start_ms: float
    duration_ms: float


_SLIDES: dict[int, _Slide] = {}
# 0.0+ = virtual clock (selftest). None = time.monotonic() for Play.
_CLOCK_MS: float | None = 0.0


def _now_ms() -> float:
    if _CLOCK_MS is not None:
        return _CLOCK_MS
    return time.monotonic() * 1000.0


def use_realtime_slides() -> None:
    """Play mode: interpolate from wall-clock ms so skipped frames still crawl."""
    global _CLOCK_MS
    _CLOCK_MS = None


def clear_walker_slides() -> None:
    global _CLOCK_MS
    _SLIDES.clear()
    _CLOCK_MS = 0.0


def drop_walker_slide(slot: int) -> None:
    _SLIDES.pop(slot, None)


def _slide_t(slide: _Slide) -> float:
    dur = slide.duration_ms if slide.duration_ms > 0 else WALK_MS_PER_TILE
    return max(0.0, min(1.0, (_now_ms() - slide.start_ms) / dur))


def note_walker_slide(
    slot: int, x0: float, y0: float, x1: float, y1: float, facing: int
) -> None:
    """Slide previous diamond centre → next over WALK_MS_PER_TILE.

    Mid-slide steps continue from the current pixel. Same-cell notes
    (spawn / warp) are ignored so we never snap t to 1 in one frame.
    """
    x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
    old = _SLIDES.get(slot)
    if old is not None:
        t = _slide_t(old)
        if t < 1.0:
            x0 = old.x0 + (old.x1 - old.x0) * t
            y0 = old.y0 + (old.y1 - old.y0) * t
    if abs(x1 - x0) < 1e-6 and abs(y1 - y0) < 1e-6:
        return
    _SLIDES[slot] = _Slide(
        x0, y0, x1, y1, facing, _now_ms(), float(WALK_MS_PER_TILE)
    )


def advance_walker_slides(steps: float = 1.0) -> bool:
    """Advance the virtual clock, or report live wall-clock slides."""
    global _CLOCK_MS
    if _CLOCK_MS is not None:
        _CLOCK_MS += steps * DISPLAY_TICK_MS
    return any(_slide_t(slide) < 1.0 for slide in _SLIDES.values())


def slide_walk_frame(slot: int, walk_frame: int) -> int:
    """0–15 walk_frame stand-in while a slide is in progress (not idle 0)."""
    slide = _SLIDES.get(slot)
    if slide is None:
        return walk_frame
    t = _slide_t(slide)
    if t >= 1.0:
        return walk_frame
    frame = int(t * 16.0)
    if frame < 1:
        frame = 1
    if frame > 15:
        frame = 15
    return frame


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
    anim_timer: int
    on_road: int
    life_phase: int
    score_a: int
    score_b: int
    home_off: int
    home_walker: int
    name_id: int
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
            anim_timer=raw[0x20],
            on_road=raw[0x23],
            life_phase=raw[0x24],
            score_a=raw[0x26],
            score_b=raw[0x27],
            home_off=home_off,
            home_walker=raw[0x2C],
            name_id=raw[0x32],
            sprite_id=sprite_id,
            bob=raw[0x36],
            raw=bytes(raw),
        )

    @property
    def live(self) -> bool:
        return self.occupied != 0 and TYPE_MIN <= self.type <= TYPE_MAX

    def ltlmen_index(self, *, camera: int = 0, walk_frame: int | None = None) -> int:
        """LTLMEN sprite. Prefer the saved id from walker_set_sprite."""
        if walk_frame is None and 0 <= self.sprite_id < 220:
            return self.sprite_id
        base = TYPE_LTLMEN_BASE.get(self.type, 0)
        slide = _SLIDES.get(self.slot)
        facing = slide.facing if slide is not None and _slide_t(slide) < 1.0 else self.facing
        rel = (facing - camera) % 8
        frame = (self.walk_frame if walk_frame is None else walk_frame) & 3
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


def pack_pool(walkers: Sequence[Walker] | bytearray | bytes | memoryview) -> bytes:
    """201 × 58 for SavChunk 8. Empty list → zeros (walkers_clear_pool)."""
    if isinstance(walkers, (bytes, bytearray, memoryview)):
        raw = bytes(walkers)
        if len(raw) != WALKER_BYTES:
            raise ValueError(f"chunk {SAV_CHUNK} is {len(raw)} bytes, want {WALKER_BYTES}")
        return raw
    blob = bytearray(WALKER_BYTES)
    for walker in walkers:
        slot = int(getattr(walker, "slot", -1))
        rec = getattr(walker, "raw", b"")
        if 0 <= slot < WALKER_COUNT and len(rec) == WALKER_STRIDE:
            off = slot * WALKER_STRIDE
            blob[off : off + WALKER_STRIDE] = rec
    return bytes(blob)


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


def iso_origin_x(width: int = MAP_W, *, zoom: int = 0) -> int:
    tile_w, _tile_h = iso_tile_size(zoom)
    return (width - 1) * (tile_w // 2)


# walker_step 0x488DC — facing 0–7 = N NE E SE S SW W NW
_FACING_XY: tuple[tuple[int, int], ...] = (
    (0, -1),
    (1, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
)


def tile_iso_xy(
    x: float,
    y: float,
    *,
    origin_x: int | None = None,
    zoom: int = 0,
    facing: int = 0,
) -> tuple[int, int]:
    """Diamond top-left. Same formula as city_map.render_iso."""
    tile_w, tile_h = iso_tile_size(zoom)
    half_w, half_h = tile_w / 2.0, tile_h / 2.0
    if origin_x is None:
        origin_x = iso_origin_x(zoom=zoom)
    dx, dy = world_to_draw(x, y, facing)
    sx = origin_x + (dx - dy) * half_w
    sy = (dx + dy) * half_h
    return int(round(sx)), int(round(sy))


def walker_draw_ltlmen_index(walker: Walker, *, camera: int = 0) -> int:
    """Walk-cycle index while sliding; saved sprite_id when standing."""
    slide = _SLIDES.get(walker.slot)
    if slide is not None and _slide_t(slide) < 1.0:
        return walker.ltlmen_index(
            camera=camera, walk_frame=slide_walk_frame(walker.slot, walker.walk_frame)
        )
    return walker.ltlmen_index(camera=camera)


def walker_draw_xy(walker: Walker) -> tuple[float, float]:
    """Tile coords for blit. Time-based slide first; else walk_frame 1–15 lerp.

    ``walker_step`` commits x/y first. The slide holds the previous diamond
    centre → next centre for WALK_MS_PER_TILE so Play (50 ms display /
    200 ms sim) still crawls a few pixels every blit. Fallback lerp uses
    facing + anim_timer so Space/T and SAV loads do not snap.
    """
    slide = _SLIDES.get(walker.slot)
    if slide is not None:
        t = _slide_t(slide)
        return slide.x0 + (slide.x1 - slide.x0) * t, slide.y0 + (
            slide.y1 - slide.y0
        ) * t
    x, y = float(walker.x), float(walker.y)
    frame = walker.walk_frame
    facing = walker.facing
    if 1 <= frame <= 15 and 0 <= facing <= 7:
        dx, dy = _FACING_XY[facing]
        speed = 2 if walker.on_road == 0 else 1
        sub = walker.anim_timer / (speed + 1)
        t = (frame + sub) / 16.0
        x -= dx * (1.0 - t)
        y -= dy * (1.0 - t)
    return x, y


def find_walker_at(
    pool: Sequence[Walker],
    x: int,
    y: int,
    *,
    tiles: bytes | bytearray | None = None,
) -> Walker | None:
    """Query pick: tile +7/+8, then closest live sprite (lerp may sit between)."""
    by_slot = {w.slot: w for w in pool if w.live}
    if tiles is not None and 0 <= x < MAP_W and 0 <= y < MAP_H:
        off = (y * MAP_W + x) * 20
        if off + 9 <= len(tiles):
            for idx in (tiles[off + 7], tiles[off + 8]):
                hit = by_slot.get(idx)
                if hit is not None and hit.state != STATE_FREE:
                    return hit
    best: Walker | None = None
    best_d = 1.35
    for walker in drawable_walkers(pool):
        fx, fy = walker_draw_xy(walker)
        dist = max(abs(fx - x), abs(fy - y))
        if dist < best_d:
            best_d = dist
            best = walker
    return best


def walker_iso_xy(
    walker: Walker,
    *,
    origin_x: int | None = None,
    zoom: int = 0,
    facing: int = 0,
) -> tuple[int, int]:
    """Blit origin for LTLMEN: feet on the road diamond."""
    tile_w, tile_h = iso_tile_size(zoom)
    men = LTLMEN_SIZE_BY_ZOOM[max(0, min(zoom, 2))]
    fx, fy = walker_draw_xy(walker)
    sx, sy = tile_iso_xy(fx, fy, origin_x=origin_x, zoom=zoom, facing=facing)
    # Centre of the iso diamond is the pad. Bottom-edge feet sit on the
    # SE neighbour diamond (same dest Y as type-1 aqueduct).
    cx = sx + tile_w // 2
    cy = sy + tile_h // 2
    return cx - men // 2, cy - men + men // 4


_LTLMEN_FRAMES: dict[tuple[str, int], list[Image.Image]] = {}


def load_ltlmen_frames(
    game: Path, *, zoom: int = 0
) -> tuple[list[Image.Image], str]:
    from app.assets import load_pl8_frames

    z = max(0, min(zoom, 2))
    name = LTLMEN_BY_ZOOM[z]
    key = (str(Path(game)), z)
    hit = _LTLMEN_FRAMES.get(key)
    if hit is not None:
        return hit, name
    frames, path = load_pl8_frames(game, name)
    _LTLMEN_FRAMES[key] = frames
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
    cam_x: int = 0,
    cam_y: int = 0,
    inplace: bool = False,
    facing: int = 0,
) -> Image.Image:
    """Blit live walkers onto an iso canvas or a camera crop of it.

    Full-canvas callers omit ``cam_x`` / ``cam_y``. Play mode pastes onto
    the 640×480 crop (``inplace=True``) so we never copy the 80×80 iso.
    Does not call ``city_map.render_iso``. Uses ``assets.load_pl8_frames``.
    """
    if sprites is None:
        sprites, _name = load_ltlmen_frames(game, zoom=zoom)
    n = len(sprites)
    tile_w, _tile_h = iso_tile_size(zoom)
    if origin_x is None:
        # Match render_iso: origin from map width, not image width.
        origin_x = iso_origin_x(MAP_W, zoom=zoom)
        expected_w = origin_x + (MAP_W - 1) * (tile_w // 2) + tile_w
        # Viewport crops are smaller; keep the map origin and subtract cam.
        if img.width != expected_w and cam_x == 0 and cam_y == 0:
            origin_x = (img.width - tile_w) // 2

    if inplace and img.mode == "RGBA":
        out = img
    elif img.mode == "RGBA":
        out = img.copy()
    else:
        out = img.convert("RGBA")
    men = LTLMEN_SIZE_BY_ZOOM[max(0, min(zoom, 2))]
    vw, vh = out.size
    for walker in drawable_walkers(walkers):
        idx = walker_draw_ltlmen_index(walker, camera=camera)
        if not (0 <= idx < n):
            continue
        spr = sprites[idx]
        px, py = walker_iso_xy(walker, origin_x=origin_x, zoom=zoom, facing=facing)
        px -= cam_x
        py -= cam_y
        if px + men < 0 or py + men < 0 or px >= vw or py >= vh:
            continue
        out.paste(spr, (px, py), spr)
    return out
