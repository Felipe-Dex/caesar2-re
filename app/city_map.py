"""80×80 city tiles × 20 bytes (AoS) and a one-shot isometric preview.

Ghidra (findings/ghidra_city.md, ghidra_walkers.md):

    BSS              0xE2FBC
    SavChunk         13        128000 bytes
    tile step        0x14      = 20
    row step         0x640     = 1600 = 80×20

    city_map_draw_terrain  0x361DC
        id < 0x78  → CITYFIXT[LUT[id*4 + (zoom>>1)] + 0x10]
                     zoom 0 (chunk 4 / [0x102BE0] == 0): sprite = id + 16
        id ≥ 0x78  → city_tile_draw_building 0x3739F
                     sheet = tile[+3] & 0x1C
                     sprite = LUT[tile[+4]*4 + (zoom>>1)]  (+0x10 if sheet==0x10)

Do not invent walkers or economy. Remaining tile bytes
(+12, +14, +16, +17; +19 low confidence) still want a 1-house SAV pair.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw

from app.config import find_file

MAP_W = 80
MAP_H = 80
TILE_BYTES = 20
MAP_BYTES = MAP_W * MAP_H * TILE_BYTES  # 128000
TILE_STRIDE = 0x14
ROW_STRIDE = 0x640
GHIDRA_BSS = 0xE2FBC
SAV_CHUNK = 13

# sav_write 0x70174: 500 sequential {ptr,size} then 4000 B history.dat.
N_SAV_CHUNKS = 500
SAV_TABLE_BYTES = 221745
SAV_HISTORY_BYTES = 4000
SAV_SIZE = SAV_TABLE_BYTES + SAV_HISTORY_BYTES  # 225745
SAV_CHUNKS_VA = 0x9ABC0

# Prefix through chunk 13 (notes/ps_sav_chunks.tsv). Enough to slice the map
# when the 500-row table is not on disk.
_SIZES_THROUGH_CITY = (
    1,
    1,
    1,
    1,
    4,
    4,
    4,
    4550,
    11658,
    3978,
    17688,
    9045,
    3460,
    128000,
)

ID_TERRAIN_MAX = 0x78
ID_HOUSING_LO = 0x82
ID_HOUSING_HI = 0xA1
ID_WATER_MAX = 8
FLAG_RIVER = 0x10
FLAG_PAD = 0x20
# city_map_draw_terrain: LUT[id*4] + 0x10 at zoom 0.
CITYFIXT_TERRAIN_BIAS = 0x10

# city_tile_draw_building 0x3739F: tile[+3] bits 2–4 pick the zoom-1 PL8.
SHEET_HOUSES1 = 0x00
SHEET_BUILD1A = 0x04
SHEET_BUILD1B = 0x08
SHEET_BUILD1C = 0x0C
SHEET_CITYFIXT_BLD = 0x10
SHEET_BUILD1D = 0x14

# gfx_load_zoom_set 0x107DB slot → filename (zoom digit 1).
PL8_HOUSES1 = "HOUSES1"
PL8_BUILD1A = "BUILD1A"
PL8_BUILD1B = "BUILD1B"
PL8_BUILD1C = "BUILD1C"
PL8_BUILD1D = "BUILD1D"
PL8_CITYFIXT = "CITYFIXT"

# Zoom-0 column of each 4-byte LUT record (variant*4 + (zoom>>1), zoom==0).
# HOUSES1 0x97158 (174), BUILD1A 0x97410 (124), BUILD1B 0x97600 (164),
# BUILD1C 0x97890 (72), BUILD1D 0x979B0 (100), CITYFIXT-building 0x96F18 (144).
_LUT_HOUSES1 = bytes(range(90)) + bytes(20) + bytes(
    [
        90, 91, 92, 93, 90, 91, 92, 93, 98, 99, 100, 101, 94, 95, 96, 97,
        90, 91, 92, 93, 98, 99, 100, 101, 102, 103, 104, 105, 94, 95, 96, 97,
        90, 91, 92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105,
        102, 103, 104, 105, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105,
    ]
)
_LUT_BUILD1A = bytes.fromhex(
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "404142434445464748494a4b4c4d4e4f"
    "505152535455565758595a5b5c5d5e5f"
    "606162636465666768696a6b6c6d6e6f"
    "707172737475767778797a7b"
)
_LUT_BUILD1B = bytes.fromhex(
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "404142434445464748494a4b4c4d4e4f"
    "505152535455565758595a5b5c5d5e5f"
    "606162636465666768696a6b6c6d6e6f"
    "707172737475767778797a7b7c7d7e7f"
    "808182838485868788898a8b14161417"
    "1516151718181a19181a1b1918191a1b"
    "1b191a1b"
)
_LUT_BUILD1C = bytes.fromhex(
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "4041424344454647"
)
_LUT_BUILD1D = bytes.fromhex(
    "32333435363738393a3b3c3d3e3f4041"
    "42434445464748494a4b4c4d4e4f5051"
    "52535455565758595a5b5c5d5e5f6061"
    "6263000102030405060708090a0b0c0d"
    "0e0f101112131415161718191a1b1c1d"
    "1e1f202122232425262728292a2b2c2d"
    "2e2f3031"
)
_LUT_CITYFIXT_BLD = bytes.fromhex(
    "0000000000004e3a2e1b130701000000"
    "000102030405060708090a0b0c0d0e0f"
    "101112131415161718191a1b1c1d1e1f"
    "202122232425262728292a2b2c2d2e2f"
    "303132333435363738393a3b3c3d3e3f"
    "404142434445464748494a4b4c4d4e4f"
    "505152535455565758595a5b5c5d5e5f"
    "606162636465666768696a6b6c6d6e6f"
    "707172737475767778797a7b7c7d7e7f"
)

# sheet (+3 & 0x1C) → (zoom-0 LUT, PL8 key, added after LUT)
_SHEET_LUT: dict[int, tuple[bytes, str, int]] = {
    SHEET_HOUSES1: (_LUT_HOUSES1, PL8_HOUSES1, 0),
    SHEET_BUILD1A: (_LUT_BUILD1A, PL8_BUILD1A, 0),
    SHEET_BUILD1B: (_LUT_BUILD1B, PL8_BUILD1B, 0),
    SHEET_BUILD1C: (_LUT_BUILD1C, PL8_BUILD1C, 0),
    SHEET_CITYFIXT_BLD: (_LUT_CITYFIXT_BLD, PL8_CITYFIXT, CITYFIXT_TERRAIN_BIAS),
    SHEET_BUILD1D: (_LUT_BUILD1D, PL8_BUILD1D, 0),
}

# Host zoom 0/1/2 = PL8 digit 1/2/3 (flags 0x0002 / 0x0102 / 0x0202).
ISO_BY_ZOOM: tuple[tuple[int, int], ...] = (
    (58, 30),  # HOUSES1 / BUILD1* / CITYFIXT
    (26, 14),  # HOUSES2 / BUILD2* / CITYFIX2
    (10, 6),  # HOUSES3 / BUILD3* / CITYFIX3
)
ISO_W, ISO_H = ISO_BY_ZOOM[0]
ISO_HALF_W = ISO_W // 2
ISO_HALF_H = ISO_H // 2


def clamp_zoom(zoom: int) -> int:
    return max(0, min(int(zoom), len(ISO_BY_ZOOM) - 1))


def iso_tile_size(zoom: int = 0) -> tuple[int, int]:
    return ISO_BY_ZOOM[clamp_zoom(zoom)]


def iso_canvas_size(
    zoom: int = 0, width: int = MAP_W, height: int = MAP_H
) -> tuple[int, int]:
    """Native render_iso canvas at this zoom (not the 640×480 viewport)."""
    tile_w, tile_h = iso_tile_size(zoom)
    half_w, half_h = tile_w // 2, tile_h // 2
    origin_x = (width - 1) * half_w
    return (
        origin_x + (width - 1) * half_w + tile_w,
        (width - 1 + height - 1) * half_h + tile_h,
    )

PREFERRED_SAVES = ("FELIPE01.SAV", "FELIPE02.SAV", "LASTYEAR.SAV")


@dataclass(frozen=True)
class Tile:
    """One 20-byte city cell. Named fields match findings/ghidra_walkers.md."""

    terrain_id: int
    flags: int
    overlay: int
    draw: int
    variant: int
    spawn_packed: int
    spawn_cd: int
    walker0: int
    walker1: int
    overlay_anim: int
    coverage: int
    housing_grade: int
    unknown12: int
    desirability: int
    unknown14: int
    industry: int
    unknown16: int
    unknown17: int
    queue: int
    special: int
    raw: bytes = field(repr=False, compare=False)

    @classmethod
    def unpack(cls, raw: bytes) -> Tile:
        if len(raw) != TILE_BYTES:
            raise ValueError(f"tile is {len(raw)} bytes, want {TILE_BYTES}")
        b = raw
        return cls(
            terrain_id=b[0],
            flags=b[1],
            overlay=b[2],
            draw=b[3],
            variant=b[4],
            spawn_packed=b[5],
            spawn_cd=b[6],
            walker0=b[7],
            walker1=b[8],
            overlay_anim=b[9],
            coverage=b[10],
            housing_grade=b[11],
            unknown12=b[12],
            desirability=b[13],
            unknown14=b[14],
            industry=b[15],
            unknown16=b[16],
            unknown17=b[17],
            queue=b[18],
            special=b[19],
            raw=bytes(b),
        )

    @property
    def is_terrain(self) -> bool:
        return self.terrain_id < ID_TERRAIN_MAX

    @property
    def is_housing(self) -> bool:
        return ID_HOUSING_LO <= self.terrain_id <= ID_HOUSING_HI

    @property
    def is_water(self) -> bool:
        return self.terrain_id < ID_WATER_MAX

    @property
    def is_river(self) -> bool:
        return bool(self.flags & FLAG_RIVER)

    @property
    def is_pad(self) -> bool:
        return bool(self.flags & FLAG_PAD)

    def cityfixt_index(self) -> int | None:
        """CITYFIXT sprite for terrain, or None (buildings use other PL8s)."""
        if not self.is_terrain:
            return None
        return self.terrain_id + CITYFIXT_TERRAIN_BIAS

    def building_sprite(self) -> tuple[str, int] | None:
        """PL8 key + sprite from city_tile_draw_building (zoom 0)."""
        if self.is_terrain:
            return None
        info = _SHEET_LUT.get(self.draw & 0x1C)
        if info is None:
            return None
        lut, name, bias = info
        if self.variant >= len(lut):
            return None
        return name, lut[self.variant] + bias


@dataclass
class CityMap:
    """80×80×20 blob. Same size as SavChunk 13."""

    width: int = MAP_W
    height: int = MAP_H
    tiles: bytearray = field(default_factory=lambda: bytearray(MAP_BYTES))
    source: str = "empty"

    def offset(self, x: int, y: int) -> int:
        return y * ROW_STRIDE + x * TILE_STRIDE

    def tile_bytes(self, x: int, y: int) -> memoryview:
        off = self.offset(x, y)
        return memoryview(self.tiles)[off : off + TILE_BYTES]

    def tile(self, x: int, y: int) -> Tile:
        return Tile.unpack(bytes(self.tile_bytes(x, y)))

    def clear(self) -> None:
        """Stand-in for city_map_zero_lanes — wipe only, no generate."""
        self.tiles[:] = b"\x00" * MAP_BYTES
        self.source = "empty"

    def id_counts(self) -> dict[int, int]:
        counts: dict[int, int] = {}
        for i in range(0, len(self.tiles), TILE_BYTES):
            v = self.tiles[i]
            counts[v] = counts.get(v, 0) + 1
        return counts


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _sizes_from_tsv(path: Path) -> list[int]:
    sizes: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip() or line.startswith("#"):
            continue
        sizes.append(int(line.split("\t")[2]))
    if len(sizes) != N_SAV_CHUNKS:
        raise ValueError(f"{path.name}: {len(sizes)} rows, want {N_SAV_CHUNKS}")
    total = sum(sizes)
    if total != SAV_TABLE_BYTES:
        raise ValueError(f"{path.name}: sizes sum {total}, want {SAV_TABLE_BYTES}")
    return sizes


def _sizes_from_exe(game: Path) -> list[int]:
    exe = find_file(game, "PS.EXE")
    if exe is None:
        raise FileNotFoundError("PS.EXE not in the install folder")
    import sys

    tools = _repo_root() / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    import ps_le  # noqa: E402

    mapped = ps_le.map_image(ps_le.load_ps(exe), apply_fixups=False)
    sizes: list[int] = []
    for i in range(N_SAV_CHUNKS):
        off = mapped.va_to_off(SAV_CHUNKS_VA + i * 8 + 4)
        if off is None:
            raise ValueError(f"SavChunk size VA {SAV_CHUNKS_VA + i * 8 + 4:#x} unmapped")
        sizes.append(struct.unpack_from("<I", mapped.image, off)[0])
    total = sum(sizes)
    if total != SAV_TABLE_BYTES:
        raise ValueError(f"PS.EXE SavChunk sizes sum {total}, want {SAV_TABLE_BYTES}")
    return sizes


def load_chunk_sizes(game: Path | None = None) -> list[int]:
    """500 writer sizes, table order (sav_write 0x70174).

    Prefer notes/ps_sav_chunks.tsv, then the PS.EXE table, then the documented
    prefix through chunk 13.
    """
    tsv = _repo_root() / "notes" / "ps_sav_chunks.tsv"
    if tsv.is_file():
        return _sizes_from_tsv(tsv)
    if game is not None:
        try:
            return _sizes_from_exe(game)
        except (OSError, ValueError, ImportError):
            pass
    return list(_SIZES_THROUGH_CITY)


def walk_sav_chunks(data: bytes, sizes: Sequence[int]) -> list[memoryview]:
    """Split a .SAV as sav_write does: sequential sizes, then 4000 B trailer."""
    if len(data) != SAV_SIZE:
        raise ValueError(f"SAV is {len(data)} bytes, expected {SAV_SIZE}")
    if len(sizes) >= N_SAV_CHUNKS:
        table = sum(sizes[:N_SAV_CHUNKS])
        if table != SAV_TABLE_BYTES:
            raise ValueError(f"chunk sizes sum {table}, want {SAV_TABLE_BYTES}")
    pos = 0
    chunks: list[memoryview] = []
    view = memoryview(data)
    for sz in sizes:
        end = pos + sz
        if end > len(data):
            raise ValueError(f"chunk overruns file at {pos}+{sz}")
        chunks.append(view[pos:end])
        pos = end
    return chunks


def find_saves(folder: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for pat in ("*.SAV", "*.sav"):
        for path in sorted(folder.glob(pat)):
            key = path.resolve()
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return found


def pick_save(folder: Path) -> Path | None:
    found = {p.name.upper(): p for p in find_saves(folder)}
    for name in PREFERRED_SAVES:
        if name in found:
            return found[name]
    saves = find_saves(folder)
    return saves[0] if saves else None


def load_city_from_sav(
    path: Path, sizes: Sequence[int] | None = None, *, game: Path | None = None
) -> CityMap:
    """Read SavChunk 13 from a real .SAV (sequential 500-chunk stream)."""
    data = path.read_bytes()
    if sizes is None:
        sizes = load_chunk_sizes(game if game is not None else path.parent)
    chunks = walk_sav_chunks(data, sizes)
    if SAV_CHUNK >= len(chunks):
        raise ValueError(f"only {len(chunks)} chunks; need index {SAV_CHUNK}")
    raw = chunks[SAV_CHUNK]
    if len(raw) != MAP_BYTES:
        raise ValueError(f"chunk {SAV_CHUNK} is {len(raw)} bytes, want {MAP_BYTES}")
    return CityMap(tiles=bytearray(raw), source=path.name)


def _fallback_color(tile: Tile) -> tuple[int, int, int]:
    if tile.is_housing:
        return (196, 92, 64)
    if not tile.is_terrain:
        return (200, 170, 70)
    if tile.is_river or tile.is_water:
        return (40, 90, 180)
    return (48 + (tile.terrain_id % 24) * 3, 118, 52)


def _draw_diamond(
    img: Image.Image,
    x: int,
    y: int,
    color: tuple[int, int, int],
    *,
    tile_w: int = ISO_W,
    tile_h: int = ISO_H,
) -> None:
    half_w, half_h = tile_w // 2, tile_h // 2
    draw = ImageDraw.Draw(img)
    draw.polygon(
        [
            (x + half_w, y),
            (x + tile_w - 1, y + half_h),
            (x + half_w, y + tile_h - 1),
            (x, y + half_h),
        ],
        fill=color,
    )


def _blit_iso(
    img: Image.Image,
    frames: Sequence[Image.Image] | None,
    index: int | None,
    sx: int,
    sy: int,
    *,
    tile_w: int = ISO_W,
) -> bool:
    if frames is None or index is None:
        return False
    if not (0 <= index < len(frames)):
        return False
    spr = frames[index]
    if spr.width < tile_w // 2:
        return False
    img.paste(spr, (sx, sy), spr)
    return True


def render_iso(
    city: CityMap,
    sprites: Sequence[Image.Image] | None = None,
    *,
    sheets: dict[str, Sequence[Image.Image]] | None = None,
    bg: tuple[int, int, int] = (12, 16, 28),
    zoom: int = 0,
) -> Image.Image:
    """Blit 80×80 iso tiles. Terrain → CITYFIXT[id+16]; buildings → sheet LUT.

    ``zoom`` 0/1/2 picks diamond 58×30 / 26×14 / 10×6. Sheet keys stay
    HOUSES1 / BUILD1A–D / CITYFIXT; the caller loads the matching PL8 digit.
    Does not change Tile.unpack.
    """
    tile_w, tile_h = iso_tile_size(zoom)
    half_w, half_h = tile_w // 2, tile_h // 2
    origin_x = (MAP_W - 1) * half_w
    width = origin_x + (MAP_W - 1) * half_w + tile_w
    height = (MAP_W - 1 + MAP_H - 1) * half_h + tile_h
    img = Image.new("RGBA", (width, height), (*bg, 255))
    cityfixt: Sequence[Image.Image] | None = None
    if sheets is not None:
        cityfixt = sheets.get(PL8_CITYFIXT)
    if cityfixt is None:
        cityfixt = sprites

    for y in range(city.height):
        for x in range(city.width):
            tile = city.tile(x, y)
            sx = origin_x + (x - y) * half_w
            sy = (x + y) * half_h
            if tile.is_terrain:
                if _blit_iso(
                    img, cityfixt, tile.cityfixt_index(), sx, sy, tile_w=tile_w
                ):
                    continue
            else:
                spec = tile.building_sprite()
                if spec is not None:
                    name, idx = spec
                    frames = sheets.get(name) if sheets is not None else None
                    if name == PL8_CITYFIXT and frames is None:
                        frames = cityfixt
                    if _blit_iso(img, frames, idx, sx, sy, tile_w=tile_w):
                        continue
            _draw_diamond(
                img, sx, sy, _fallback_color(tile), tile_w=tile_w, tile_h=tile_h
            )
    return img
