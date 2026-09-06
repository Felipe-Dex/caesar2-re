"""80×80 city tiles × 20 bytes (AoS) and a one-shot isometric preview.

Ghidra (findings/ghidra_city.md, ghidra_walkers.md):

    BSS              0xE2FBC
    SavChunk         13        128000 bytes
    tile step        0x14      = 20
    row step         0x640     = 1600 = 80×20

    city_map_draw  0x360F7
        [0x117AC8] = ([0x117AC8]+1) ; wrap after 3   ; every city_map_draw
        [0x117AB4]++ ; wrap 0x80                     ; same cadence
        then terrain / walkers / overlays            ; NOT a sim pulse
        Capstone: 117AC8 xrefs are only this increment (never read).
        0x361DC does not use it. view_frame calls draw when city &&
        speed<=1. No EXE ms constant — host uses WATER_FRAME_MS.

    city_map_draw_terrain  0x361DC
        id < 0x78  → CITYFIXT[LUT_0x96F58[id*4 + (zoom>>1)] + 0x10]
                     LUT columns are zoom remaps, not water frames.
                     River 0x1E cols are 1E 26 22 2A (other orientations).
        id ≥ 0x78  → city_tile_draw_building 0x3739F
                     sheet = tile[+3] & 0x1C
                     sprite = LUT[tile[+4]*4 + (zoom>>1)]  (+0x10 if sheet==0x10)

    EXE river is static +0 (no CPU id cycle, no overlay blit, VGA DAC
    is a full palette load). Host must not cycle 0x1E–0x21: alpha matches
    (xor 0) but the water/bank outline crawls (0x1E vs 0x1F water_xor=60
    of 142; ~735/900 indices differ). Lock tile[+0]; cintilar só o
    interior azul, máscara e margens iguais em todos os frames.

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
# city_map_draw_terrain: LUT[id*4 + (zoom>>1)] + 0x10. Host zoom col = 0.
# [0x117AC8] is incremented 0..3 and never consumed. Do not remap +0.
CITYFIXT_TERRAIN_BIAS = 0x10
WATER_FRAMES = 4
# Host-only interior cycle. EXE has no ms constant; 250 ms ≈ old cadence.
WATER_FRAME_MS = 250
# city_map_bank_remap bases (0x1E, 0x22, … 0x4A) and period-4 variants.
ID_RIVER_LO = 0x1E
ID_RIVER_HI = 0x51

# Terrain LUT 0x96F58: 0x78 records × 4 zoom columns. Col 0 is identity.
# Grass 0x00–0x1D is identity on every column. River cols remap to the
# other three orientations of the same family (not animation frames).
_LUT_TERRAIN = bytes.fromhex(
    "0000000001010101020202020303030304040404050505050606060607070707"
    "08080808090909090a0a0a0a0b0b0b0b0c0c0c0c0d0d0d0d0e0e0e0e0f0f0f0f"
    "1010101011111111121212121313131314141414151515151616161617171717"
    "18181818191919191a1a1a1a1b1b1b1b1c1c1c1c1d1d1d1d"
    "1e26222a1f27232b2028242c2129252d222a1e26232b1f27242c2028252d21"
    "2926222a1e27232b1f28242c2029252d212a1e26222b1f27232c2028242d21"
    "29252e3e32422f3f3343304034443141354532422e3e33432f3f34443040"
    "35453141364a3a46374b3b47384c3c48394d3d493a46364a3b47374b3c48"
    "384c3d49394d3e32422e3f33432f4034443041354531422e3e32432f3f33"
    "443040344531413546364a3a47374b3b48384c3c49394d3d4a3a46364b3b"
    "47374c3c48384d3d49394e514f504f504e51504e514f514f504e52535253"
    "5352535254575655555457565655545757565554585b5a5959585b5a5a59"
    "585b5b5a59585c5c5c5c5d5d5d5d5e5e5e5e5f5f5f5f6063606361646164"
    "6265626563606360646164616562656266696669676a676a686b686b6966"
    "69666a676a676b686b686c75726f6d7673706e7774716f6c7572706d7673"
    "716e7774726f6c7573706d7674716e7775726f6c7673706d7774716e"
)

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


def iso_origin_x(zoom: int = 0, width: int = MAP_W) -> int:
    return (width - 1) * (iso_tile_size(zoom)[0] // 2)


def tile_iso_xy(
    x: int,
    y: int,
    *,
    origin_x: int | None = None,
    zoom: int = 0,
    width: int = MAP_W,
) -> tuple[int, int]:
    """Diamond top-left. Same formula as render_iso."""
    tile_w, tile_h = iso_tile_size(zoom)
    half_w, half_h = tile_w // 2, tile_h // 2
    if origin_x is None:
        origin_x = iso_origin_x(zoom=zoom, width=width)
    return origin_x + (x - y) * half_w, (x + y) * half_h


def river_tile_xy(city: CityMap) -> list[tuple[int, int]]:
    """Tiles with +1 bit 0x10 (city_map_trace_feature river)."""
    out: list[tuple[int, int]] = []
    tiles = city.tiles
    for y in range(city.height):
        row = y * ROW_STRIDE
        for x in range(city.width):
            if tiles[row + x * TILE_STRIDE + 1] & FLAG_RIVER:
                out.append((x, y))
    return out

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

    def cityfixt_index(self, water_frame: int = 0) -> int | None:
        """CITYFIXT sprite for terrain, or None (buildings use other PL8s).

        Zoom-0: ``LUT[id*4] + 0x10`` (column 0 is identity). ``water_frame``
        does not change +0 — margens ficam no tile gerado. Grass and
        river share this path; only the blit remaps interior water pixels.
        """
        if not self.is_terrain:
            return None
        tid = self.terrain_id
        off = tid * 4
        if 0 <= off < len(_LUT_TERRAIN):
            return _LUT_TERRAIN[off] + CITYFIXT_TERRAIN_BIAS
        return tid + CITYFIXT_TERRAIN_BIAS

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


# Tallest BUILD1* / HOUSES1 / CITYFIXT sprite per host zoom (measured PL8).
# Used only to bound which tiles can overlap a river AABB.
_MAX_SPRITE_H = (96, 48, 24)
ISO_BG = (12, 16, 28)
# CITYFIXT.256 blues used as river fill (not grass 90 / bank browns).
_WATER_B_OVER_R = 20
_WATER_B_OVER_G = 8
_water_anim_cache: dict[int, tuple[Image.Image, ...]] = {}


def _is_water_rgba(px: tuple[int, ...]) -> bool:
    r, g, b = px[0], px[1], px[2]
    a = px[3] if len(px) > 3 else 255
    return a > 0 and b >= r + _WATER_B_OVER_R and b >= g + _WATER_B_OVER_G


def _water_interior_frames(spr: Image.Image) -> tuple[Image.Image, ...]:
    """4 copies: same alpha / bank pixels; only interior blues rotate.

    Host stand-in — EXE 0x361DC blits one locked CITYFIXT id.
    """
    key = id(spr)
    hit = _water_anim_cache.get(key)
    if hit is not None:
        return hit
    src = spr.convert("RGBA")
    pixels = list(src.getdata())
    colors: list[tuple[int, int, int]] = []
    seen: set[tuple[int, int, int]] = set()
    for px in pixels:
        if not _is_water_rgba(px):
            continue
        rgb = (px[0], px[1], px[2])
        if rgb in seen:
            continue
        seen.add(rgb)
        colors.append(rgb)
    colors.sort(key=lambda c: (c[2], c[1], c[0]))
    frames: list[Image.Image] = [src]
    n = len(colors)
    if n >= 2:
        cmap = {c: i for i, c in enumerate(colors)}
        for step in range(1, WATER_FRAMES):
            out_px = []
            for px in pixels:
                if not _is_water_rgba(px):
                    out_px.append(px)
                    continue
                i = cmap[(px[0], px[1], px[2])]
                nr, ng, nb = colors[(i + step) % n]
                out_px.append((nr, ng, nb, px[3]))
            frame = Image.new("RGBA", src.size)
            frame.putdata(out_px)
            frames.append(frame)
    else:
        frames = [src] * WATER_FRAMES
    packed = tuple(frames)
    _water_anim_cache[key] = packed
    return packed


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


def _tile_frames(
    tile: Tile,
    water_frame: int,
    cityfixt: Sequence[Image.Image] | None,
    sheets: dict[str, Sequence[Image.Image]] | None,
) -> tuple[Sequence[Image.Image] | None, int | None]:
    if tile.is_terrain:
        idx = tile.cityfixt_index()
        if (
            tile.is_river
            and ID_RIVER_LO <= tile.terrain_id <= ID_RIVER_HI
            and cityfixt is not None
            and idx is not None
            and 0 <= idx < len(cityfixt)
        ):
            return _water_interior_frames(cityfixt[idx]), int(water_frame) % WATER_FRAMES
        return cityfixt, idx
    spec = tile.building_sprite()
    if spec is None:
        return None, None
    name, idx = spec
    frames = sheets.get(name) if sheets is not None else None
    if name == PL8_CITYFIXT and frames is None:
        frames = cityfixt
    return frames, idx


def _sprite_size(
    frames: Sequence[Image.Image] | None,
    index: int | None,
    tile_w: int,
    tile_h: int,
) -> tuple[int, int]:
    if frames is None or index is None or not (0 <= index < len(frames)):
        return tile_w, tile_h
    spr = frames[index]
    if spr.width < tile_w // 2:
        return tile_w, tile_h
    return spr.width, spr.height


def _paint_iso_tile(
    img: Image.Image,
    tile: Tile,
    sx: int,
    sy: int,
    *,
    tile_w: int,
    tile_h: int,
    water_frame: int,
    cityfixt: Sequence[Image.Image] | None,
    sheets: dict[str, Sequence[Image.Image]] | None,
) -> None:
    frames, idx = _tile_frames(tile, water_frame, cityfixt, sheets)
    if _blit_iso(img, frames, idx, sx, sy, tile_w=tile_w):
        return
    _draw_diamond(img, sx, sy, _fallback_color(tile), tile_w=tile_w, tile_h=tile_h)


def _rects_overlap(
    a: tuple[int, int, int, int], b: tuple[int, int, int, int]
) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def render_iso(
    city: CityMap,
    sprites: Sequence[Image.Image] | None = None,
    *,
    sheets: dict[str, Sequence[Image.Image]] | None = None,
    bg: tuple[int, int, int] = ISO_BG,
    zoom: int = 0,
    water_frame: int = 0,
) -> Image.Image:
    """Blit 80×80 iso tiles. Terrain → CITYFIXT LUT+16; buildings → sheet LUT.

    ``zoom`` 0/1/2 picks diamond 58×30 / 26×14 / 10×6. Sheet keys stay
    HOUSES1 / BUILD1A–D / CITYFIXT; the caller loads the matching PL8 digit.
    ``water_frame`` rotates interior water pixels on river tiles. +0 and
    the bank silhouette stay locked. Does not change Tile.unpack.
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
            sx = origin_x + (x - y) * half_w
            sy = (x + y) * half_h
            _paint_iso_tile(
                img,
                city.tile(x, y),
                sx,
                sy,
                tile_w=tile_w,
                tile_h=tile_h,
                water_frame=water_frame,
                cityfixt=cityfixt,
                sheets=sheets,
            )
    return img


def blit_water_tiles(
    img: Image.Image,
    city: CityMap,
    cityfixt: Sequence[Image.Image] | None,
    water_frame: int,
    *,
    zoom: int = 0,
    cells: Sequence[tuple[int, int]] | None = None,
    sheets: dict[str, Sequence[Image.Image]] | None = None,
    bg: tuple[int, int, int] = ISO_BG,
) -> int:
    """Re-blit river tiles onto an existing canvas (not a full 80×80 pass).

    Alpha paste is not a replace, so each river AABB is rebuilt on a
    small crop (bg + overlapping tiles, iso order) and pasted back.
    Sprite size is the locked +0 diamond (interior cycle keeps the mask).
    Returns tiles blitted.
    """
    if cityfixt is None and sheets is not None:
        cityfixt = sheets.get(PL8_CITYFIXT)
    if cityfixt is None:
        return 0
    rivers = cells if cells is not None else river_tile_xy(city)
    if not rivers:
        return 0
    z = clamp_zoom(zoom)
    tile_w, tile_h = iso_tile_size(z)
    half_w, half_h = tile_w // 2, tile_h // 2
    origin_x = (MAP_W - 1) * half_w
    max_h = _MAX_SPRITE_H[z]
    ring = max(1, (max_h + half_h - 1) // half_h)

    clear_rects: list[tuple[int, int, int, int]] = []
    for x, y in rivers:
        tile = city.tile(x, y)
        sx = origin_x + (x - y) * half_w
        sy = (x + y) * half_h
        frames, idx = _tile_frames(tile, water_frame, cityfixt, sheets)
        sw, sh = _sprite_size(frames, idx, tile_w, tile_h)
        box = (sx, sy, sx + sw, sy + sh)
        clear_rects.append(box)

    box_cache: dict[tuple[int, int], tuple[int, int, int, int]] = {}

    def sprite_box(tx: int, ty: int) -> tuple[int, int, int, int]:
        hit = box_cache.get((tx, ty))
        if hit is not None:
            return hit
        tile = city.tile(tx, ty)
        sx = origin_x + (tx - ty) * half_w
        sy = (tx + ty) * half_h
        frames, idx = _tile_frames(tile, water_frame, cityfixt, sheets)
        sw, sh = _sprite_size(frames, idx, tile_w, tile_h)
        hit = (sx, sy, sx + sw, sy + sh)
        box_cache[(tx, ty)] = hit
        return hit

    n = 0
    seen_boxes: set[tuple[int, int, int, int]] = set()
    for (rx, ry), rect in zip(rivers, clear_rects):
        x0 = max(0, rect[0])
        y0 = max(0, rect[1])
        x1 = min(img.width, rect[2])
        y1 = min(img.height, rect[3])
        box = (x0, y0, x1, y1)
        if x1 <= x0 or y1 <= y0 or box in seen_boxes:
            continue
        seen_boxes.add(box)
        crop = Image.new("RGBA", (x1 - x0, y1 - y0), (*bg, 255))
        overlapping: list[tuple[int, int]] = []
        for dy in range(-ring, ring + 1):
            for dx in range(-ring, ring + 1):
                nx, ny = rx + dx, ry + dy
                if not (0 <= nx < city.width and 0 <= ny < city.height):
                    continue
                if _rects_overlap(sprite_box(nx, ny), box):
                    overlapping.append((nx, ny))
        overlapping.sort(key=lambda p: (p[1], p[0]))
        for nx, ny in overlapping:
            sx = origin_x + (nx - ny) * half_w
            sy = (nx + ny) * half_h
            _paint_iso_tile(
                crop,
                city.tile(nx, ny),
                sx - x0,
                sy - y0,
                tile_w=tile_w,
                tile_h=tile_h,
                water_frame=water_frame,
                cityfixt=cityfixt,
                sheets=sheets,
            )
            n += 1
        img.paste(crop, (x0, y0))
    return n


def selftest() -> list[str]:
    """Grass and river +0 locked; LUT cols are not frames; mask holds."""
    lines: list[str] = []
    grass = Tile.unpack(bytes([8, 0]) + bytes(18))
    flag18 = Tile.unpack(bytes([0x18, FLAG_RIVER]) + bytes(18))
    river = Tile.unpack(bytes([0x1E, FLAG_RIVER]) + bytes(18))
    corner = Tile.unpack(bytes([0x36, FLAG_RIVER]) + bytes(18))
    g0 = grass.cityfixt_index(0)
    g1 = grass.cityfixt_index(1)
    if g0 != 8 + CITYFIXT_TERRAIN_BIAS or g0 != g1:
        lines.append(f"FAIL  grass sprite {g0}/{g1}, want {8 + CITYFIXT_TERRAIN_BIAS}")
    else:
        lines.append("ok    grass ignore water_frame")
    f18 = [flag18.cityfixt_index(f) for f in range(WATER_FRAMES)]
    if f18 != [0x18 + CITYFIXT_TERRAIN_BIAS] * WATER_FRAMES:
        lines.append(f"FAIL  0x18 flag tile {f18}, want static grass")
    else:
        lines.append("ok    0x18 grass+flag ignore water_frame")
    want_1e = [0x1E + CITYFIXT_TERRAIN_BIAS] * WATER_FRAMES
    got_1e = [river.cityfixt_index(f) for f in range(WATER_FRAMES)]
    lut_cols = [
        _LUT_TERRAIN[0x1E * 4 + f] + CITYFIXT_TERRAIN_BIAS for f in range(WATER_FRAMES)
    ]
    if got_1e != want_1e:
        lines.append(f"FAIL  river 0x1E locked {got_1e}, want {want_1e}")
    elif got_1e == lut_cols:
        lines.append(f"FAIL  river still uses LUT columns {lut_cols}")
    else:
        lines.append("ok    river 0x1E locked +0 (not LUT, not 0x1E–0x21 cycle)")
    want_36 = [0x36 + CITYFIXT_TERRAIN_BIAS] * WATER_FRAMES
    got_36 = [corner.cityfixt_index(f) for f in range(WATER_FRAMES)]
    if got_36 != want_36:
        lines.append(f"FAIL  corner 0x36 locked {got_36}, want {want_36}")
    else:
        lines.append("ok    corner 0x36 locked +0")
    mid = Tile.unpack(bytes([0x20, FLAG_RIVER]) + bytes(18))
    locked_20 = 0x20 + CITYFIXT_TERRAIN_BIAS
    if mid.cityfixt_index(0) != locked_20:
        lines.append(f"FAIL  variant 0x20 lost +0 {mid.cityfixt_index(0)}")
    elif mid.cityfixt_index(2) != locked_20:
        lines.append(f"FAIL  variant 0x20 remapped {mid.cityfixt_index(2)}")
    else:
        lines.append("ok    generate variant keeps its own +0")
    if river.cityfixt_index(0) == grass.cityfixt_index(0):
        lines.append("FAIL  river sprite equals grass")
    if WATER_FRAMES != 4 or WATER_FRAME_MS != 250:
        lines.append("FAIL  WATER_FRAMES / WATER_FRAME_MS")
    else:
        lines.append(f"ok    {WATER_FRAMES} frames, host {WATER_FRAME_MS} ms")
    spr = Image.new("RGBA", (6, 6), (0, 0, 0, 0))
    pix = spr.load()
    pix[1, 1] = (40, 80, 180, 255)
    pix[2, 1] = (50, 90, 200, 255)
    pix[3, 1] = (90, 140, 70, 255)
    pix[1, 2] = (40, 80, 180, 0)
    anim = _water_interior_frames(spr)
    a0 = list(anim[0].getdata())
    a1 = list(anim[1].getdata())
    if [p[3] for p in a0] != [p[3] for p in a1]:
        lines.append("FAIL  interior cycle changed alpha")
    elif a0[1 * 6 + 3][0:3] != (90, 140, 70) or a1[1 * 6 + 3][0:3] != (90, 140, 70):
        lines.append("FAIL  bank pixel moved")
    elif a0[1 * 6 + 1][0:3] == a1[1 * 6 + 1][0:3]:
        lines.append("FAIL  water interior did not cycle")
    else:
        lines.append("ok    interior cycle keeps mask + bank")
    return lines
