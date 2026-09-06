"""Host stand-in for city_sim_phase 0x3F60C — one slot per pulse.

Ghidra HTTP was down this pass; dispatcher + evolve/merge were read from
c2_x.bin (Capstone) and findings/ghidra_sim.md / housing_merge.md.

Implemented: slots 1–0x50 housing evolve + villa/palace merge, wrap →
calendar month. Everything else is a named stub (no crash, no wipe).
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.calendar import MONTH_CHUNK, YEAR_CHUNK, GameDate, format_hud_date
from app.city_map import (
    ID_HOUSING_HI,
    ID_HOUSING_LO,
    MAP_H,
    MAP_W,
    ROW_STRIDE,
    TILE_STRIDE,
    load_chunk_sizes,
    walk_sav_chunks,
)

# [0x1026A8] after ++ ; wrap when > 0xD6. Inclusive last slot is 0xD6.
PHASE_MAX = 0xD6
PHASE_CHUNK = 24
ROW_CHUNK = 23
WEEK_GATE_CHUNK = 27

# 0x96235 — 32 × (i8 min, i8 max). Stay if min ≤ +15 ≤ max.
_EV_RAW = bytes.fromhex(
    "fd010003020504070609090b0b0d0d10"
    "1012121414161618181a1a1c1c1e1e20"
    "2022222424262628282a2a2c2c2e2e30"
    "3032323434363638383a3a3c3c3e3e7d"
)
EVOLVE_MIN: tuple[int, ...] = tuple(
    b - 256 if b >= 128 else b for b in _EV_RAW[0::2]
)
EVOLVE_MAX: tuple[int, ...] = tuple(
    b - 256 if b >= 128 else b for b in _EV_RAW[1::2]
)

# DAT_00094f3f[grade*4] gfx, DAT_00094f40[grade*4] size.
GFX_BASE: tuple[int, ...] = tuple(range(26)) + (26, 30, 34, 38, 42, 51)
HOUSE_SIZE: tuple[int, ...] = (1,) * 26 + (2, 2, 2, 2, 3, 3)
GFX_GRAND_DOMUS = 25  # 0x94FA3
ID_GRAND_DOMUS = 0x9B
ID_TENT_GRASS = 0x1A  # 42fa4 after grade-0 down

# 0x9422C / 0x94230
ADDEND_2X2: tuple[int, ...] = (0, 2, 1, 3)
ADDEND_3X3: tuple[int, ...] = (0, 2, 5, 1, 4, 7, 3, 6, 8)

# Origin shift for try 0..3 (SE / SW / NW / NE). Same for 2×2 and 3×3.
TRY_ORIGIN: tuple[tuple[int, int], ...] = ((0, 0), (-1, 0), (-1, -1), (0, -1))

# 0x99B64 — three *other* tiles of the 2×2, relative to firer.
TRY_2X2_OTHERS: tuple[tuple[tuple[int, int], ...], ...] = (
    ((1, 0), (1, 1), (0, 1)),
    ((-1, 0), (-1, 1), (0, 1)),
    ((-1, 0), (-1, -1), (0, -1)),
    ((1, 0), (1, -1), (0, -1)),
)

# 0x99B94 — five *new* tiles of the 3×3, relative to villa origin.
TRY_3X3_NEW: tuple[tuple[tuple[int, int], ...], ...] = (
    ((2, 0), (2, 1), (2, 2), (1, 2), (0, 2)),
    ((-1, 0), (-1, 1), (-1, 2), (0, 2), (1, 2)),
    ((-1, 0), (-1, 1), (-1, -1), (1, -1), (0, -1)),
    ((2, 0), (2, 1), (2, -1), (1, -1), (0, -1)),
)

def slot_name(phase: int) -> str:
    if phase == 0:
        return "once-per-cycle 0x4308B (stub)"
    if 1 <= phase <= 0x50:
        return f"housing evolve row {phase - 1}"
    if phase == 0x51:
        return "wipe +13 (stub, keep saved)"
    if phase == 0x52:
        return "wipe +15 (stub, keep saved)"
    if phase == 0x53:
        return "wipe +14 (stub, keep saved)"
    if phase == 0x54:
        return "wipe +12 (stub, keep saved)"
    if phase == 0x55:
        return "nop"
    if 0x56 <= phase <= 0x5D:
        return "paint +13/+14 0x3FDD0 (stub)"
    if 0x5E <= phase <= 0x65:
        return "paint +14 0x401E7 (stub)"
    if 0x66 <= phase <= 0x6D:
        return "paint +12 amenities 0x4034B (stub)"
    if 0x6E <= phase <= 0x75:
        return "tile_or_radius 0x3FEF7 (stub)"
    if 0x76 <= phase <= 0x7D:
        return "land-value +15 0x40695 (stub)"
    if 0x7E <= phase <= 0x8D:
        return "housing target cap +15 0x40D08 (stub)"
    if 0x8E <= phase <= 0x91:
        return "industry emit type1 (stub)"
    if 0x92 <= phase <= 0x95:
        return "barracks emit (stub)"
    if 0x96 <= phase <= 0x99:
        return "emit types 5/4 (stub)"
    if 0x9A <= phase <= 0x9D:
        return "emit types 2/6 (stub)"
    if 0x9E <= phase <= 0xA1:
        return "immigrant / rioter 0x41DD4 (stub)"
    if 0xA2 <= phase <= 0xC1:
        return "road flood +17 0x430DA (stub)"
    if 0xC2 <= phase <= 0xC9:
        return "0x445AF (stub)"
    if phase == 0xCA:
        return "0x43F88 (stub)"
    if phase == 0xCB:
        return "0x53C67 / 0x6CA74 (stub)"
    if phase == 0xCC:
        return "0x29A19 (stub)"
    if phase == 0xCD:
        return "0x456F6 (stub)"
    if 0xCE <= phase <= 0xD0:
        return "0x4327B rows (stub)"
    if phase == 0xD1:
        return "0x43B2E (stub)"
    if phase == 0xD2:
        return "walkers_relink_tiles (stub)"
    if phase == 0xD3:
        return "overlay dispatch (stub)"
    if 0xD4 <= phase <= 0xD6:
        return "empty"
    return f"unknown slot {phase:#x}"


def slot_implemented(phase: int) -> bool:
    return 1 <= phase <= 0x50


def i8(b: int) -> int:
    return b - 256 if b >= 128 else b


@dataclass
class SimState:
    """SavChunks 23–27 plus wrap counters that live next to the phase.

    New Game also fills skill (16), city_only (406), pid (223), treasury (28).
    SAV load leaves those at 0 unless a later pass reads the extra chunks.
    """

    phase: int = 1
    row: int = 0
    year_raw: int = -300
    month: int = 0
    week_gate: int = 0
    wrap3: int = 0  # [0x1026A4] — +10 decay when 0
    wrap4: int = 0  # [0x102694]
    source: str = "default"
    skill: int = 0
    city_only: int = 0
    pid: int = 0
    treasury: int = 0
    ratings_seed: int = 0
    tax_rate: int = 5
    history: bytearray = field(default_factory=lambda: bytearray(4000))

    @property
    def date(self) -> GameDate:
        return GameDate(year_raw=self.year_raw, month=self.month)

    @property
    def date_label(self) -> str:
        return format_hud_date(self.date)


@dataclass
class PhaseResult:
    phase: int
    name: str
    implemented: bool
    houses_up: int = 0
    houses_down: int = 0
    houses_merge: int = 0
    month_wrapped: bool = False
    date_label: str = ""

    @property
    def houses_changed(self) -> int:
        return self.houses_up + self.houses_down


def _off(x: int, y: int) -> int:
    return y * ROW_STRIDE + x * TILE_STRIDE


def _in_map(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def _chunk_i32(chunks: Sequence[memoryview], index: int, default: int = 0) -> int:
    if index >= len(chunks) or len(chunks[index]) < 4:
        return default
    return struct.unpack_from("<i", chunks[index], 0)[0]


def load_sim_from_sav(
    path: Path, sizes: Sequence[int] | None = None, *, game: Path | None = None
) -> SimState:
    data = path.read_bytes()
    if sizes is None:
        sizes = load_chunk_sizes(game if game is not None else path.parent)
    chunks = walk_sav_chunks(data, sizes)
    phase = _chunk_i32(chunks, PHASE_CHUNK, 1)
    if not (0 <= phase <= PHASE_MAX):
        phase = 1
    month = _chunk_i32(chunks, MONTH_CHUNK, 0)
    if not (0 <= month <= 11):
        month = 0
    return SimState(
        phase=phase,
        row=_chunk_i32(chunks, ROW_CHUNK, 0),
        year_raw=_chunk_i32(chunks, YEAR_CHUNK, -300),
        month=month,
        week_gate=_chunk_i32(chunks, WEEK_GATE_CHUNK, 0),
        source=path.name,
    )


def _decay_coverage(tiles: bytearray, off: int) -> None:
    """evolve_row +10 groups 0x30 / 0xC0 / 0x0C when [0x1026A4]==0."""
    v = tiles[off + 10]
    g30, g_c0, g0c = v & 0x30, v & 0xC0, v & 0x0C
    if g30:
        v = (v & 0xCF) | (0x20 if g30 == 0x30 else 0x10 if g30 == 0x20 else 0)
    if g_c0:
        v = (v & 0x3F) | (0x80 if g_c0 == 0xC0 else 0x40 if g_c0 == 0x80 else 0)
    if g0c:
        v = (v & 0xF3) | (8 if g0c == 0x0C else 4 if g0c == 8 else 0)
    tiles[off + 10] = v


def _block_lv(tiles: bytearray, x: int, y: int, size: int) -> int:
    """FUN_0006db08 — max of raw +15 over size×size, then signed."""
    best = 0
    for dy in range(size):
        for dx in range(size):
            if not _in_map(x + dx, y + dy):
                continue
            raw = tiles[_off(x + dx, y + dy) + 15]
            if raw > best:
                best = raw
    return i8(best)


def _merge_ok_tile(tiles: bytearray, x: int, y: int, new_id: int) -> bool:
    """Walker-empty, +1 in {0,1}, and if pad then id < new_id."""
    if not _in_map(x, y):
        return False
    off = _off(x, y)
    if tiles[off + 7] or tiles[off + 8]:
        return False
    flags = tiles[off + 1]
    if flags & 0xFE:
        return False
    if flags & 1 and tiles[off] >= new_id:
        return False
    return True


def _split_villa(tiles: bytearray, ox: int, oy: int) -> None:
    """42f71 — 2×2 at origin becomes Grand domus fillers."""
    for dy in range(2):
        for dx in range(2):
            if not _in_map(ox + dx, oy + dy):
                continue
            off = _off(ox + dx, oy + dy)
            tiles[off] = ID_GRAND_DOMUS
            tiles[off + 3] = (tiles[off + 3] | 1)
            tiles[off + 4] = GFX_GRAND_DOMUS
            tiles[off + 5] = 0


def _try_2x2(tiles: bytearray, x: int, y: int, new_id: int, try_i: int) -> bool:
    if x in (0, 79) or y in (0, 79):
        return False
    for dx, dy in TRY_2X2_OTHERS[try_i]:
        if not _merge_ok_tile(tiles, x + dx, y + dy, new_id):
            return False
    return True


def _try_3x3(tiles: bytearray, x: int, y: int, new_id: int, try_i: int) -> bool:
    if x <= 0 or y <= 0 or x >= 78 or y >= 78:
        return False
    cells = TRY_3X3_NEW[try_i]
    for dx, dy in cells:
        if not _merge_ok_tile(tiles, x + dx, y + dy, new_id):
            return False
    for dx, dy in cells:
        tx, ty = x + dx, y + dy
        if not _in_map(tx, ty):
            continue
        hid = tiles[_off(tx, ty)]
        if 0x9C <= hid <= 0x9F:
            nibble = tiles[_off(tx, ty) + 5] & 0xF
            _split_villa(tiles, tx - (nibble % 2), ty - (nibble // 2))
    return True


def _pick_block(tiles: bytearray, x: int, y: int, new_grade: int, new_size: int) -> int | None:
    """42bc4. Returns try index 0..3 or None."""
    new_id = new_grade + 0x82
    if new_size == 2:
        pred = _try_2x2
    elif new_size == 3:
        pred = _try_3x3
    else:
        return None
    for try_i in range(4):
        if pred(tiles, x, y, new_id, try_i):
            return try_i
    return None


def _stamp(
    tiles: bytearray, ox: int, oy: int, grade: int, size: int
) -> None:
    """42e25 from a chosen NW origin (try already applied)."""
    gfx = GFX_BASE[grade]
    addend = ADDEND_2X2 if size == 2 else ADDEND_3X3 if size == 3 else ()
    piece = 0
    for dy in range(size):
        for dx in range(size):
            if not _in_map(ox + dx, oy + dy):
                piece += 1
                continue
            off = _off(ox + dx, oy + dy)
            if tiles[off] < ID_HOUSING_LO:
                tiles[off + 3] &= 0x7F
            tiles[off] = grade + 0x82
            tiles[off + 1] |= 1
            tiles[off + 3] = (tiles[off + 3] | 1) & 0xC3
            tiles[off + 5] = piece
            if size == 1:
                tiles[off + 4] = gfx
            elif piece < len(addend):
                tiles[off + 4] = gfx + addend[piece]
            piece += 1


def _fill_grand_domus_leftover(
    tiles: bytearray, ox: int, oy: int, old_size: int, new_size: int
) -> None:
    """42efa — leftover cells of a shrinking footprint become 0x9B."""
    for dy in range(old_size):
        for dx in range(old_size):
            if dx < new_size and dy < new_size:
                continue
            if not _in_map(ox + dx, oy + dy):
                continue
            off = _off(ox + dx, oy + dy)
            tiles[off] = ID_GRAND_DOMUS
            tiles[off + 3] |= 1
            tiles[off + 4] = GFX_GRAND_DOMUS
            tiles[off + 5] = 0


def _delete_tent(tiles: bytearray, x: int, y: int) -> None:
    """42fa4 — grade 0 down becomes grass 0x1A."""
    off = _off(x, y)
    tiles[off] = ID_TENT_GRASS
    tiles[off + 9] = 0
    tiles[off + 1] &= 0x18
    tiles[off + 3] = (tiles[off + 3] & 0xC3) | 1
    tiles[off + 10] &= 0xFC
    tiles[off + 11] &= 0xC0
    tiles[off + 5] = 0


def _evolve_down(tiles: bytearray, x: int, y: int, grade: int) -> bool:
    if grade <= 0:
        _delete_tent(tiles, x, y)
        return True
    old_size = HOUSE_SIZE[grade]
    new_grade = grade - 1
    new_size = HOUSE_SIZE[new_grade]
    _stamp(tiles, x, y, new_grade, new_size)
    if old_size != new_size:
        _fill_grand_domus_leftover(tiles, x, y, old_size, new_size)
    return True


def _evolve_up(tiles: bytearray, x: int, y: int, grade: int) -> int:
    """Returns 0 stay, 1 in-place, 2 merge."""
    if grade >= 31:
        return 0
    old_size = HOUSE_SIZE[grade]
    new_grade = grade + 1
    new_size = HOUSE_SIZE[new_grade]
    ox, oy = x, y
    merged = False
    if old_size != new_size:
        try_i = _pick_block(tiles, x, y, new_grade, new_size)
        if try_i is None:
            return 0
        dx, dy = TRY_ORIGIN[try_i]
        ox, oy = x + dx, y + dy
        merged = True
    _stamp(tiles, ox, oy, new_grade, new_size)
    return 2 if merged else 1


def evolve_row(tiles: bytearray, y: int, *, decay: bool = True) -> tuple[int, int, int]:
    """city_buildings_evolve_row 0x42360 for one map row. Housing only."""
    up = down = merge = 0
    if not (0 <= y < MAP_H):
        return 0, 0, 0
    for x in range(MAP_W):
        off = _off(x, y)
        if decay:
            _decay_coverage(tiles, off)
        if tiles[off + 5] & 0xF:
            continue
        hid = tiles[off]
        if not (ID_HOUSING_LO <= hid <= ID_HOUSING_HI):
            continue
        grade = hid - 0x82
        if grade >= 30:
            lv = _block_lv(tiles, x, y, 3)
        elif grade >= 26:
            lv = _block_lv(tiles, x, y, 2)
        else:
            lv = i8(tiles[off + 15])
        if lv < EVOLVE_MIN[grade]:
            if _evolve_down(tiles, x, y, grade):
                down += 1
        elif lv > EVOLVE_MAX[grade]:
            kind = _evolve_up(tiles, x, y, grade)
            if kind == 2:
                merge += 1
                up += 1
            elif kind == 1:
                up += 1
    return up, down, merge


def evolve_all_rows(tiles: bytearray, *, decay: bool = True) -> tuple[int, int, int]:
    """Host-only: all 80 evolve rows. Not one EXE pulse."""
    up = down = merge = 0
    for y in range(MAP_H):
        u, d, m = evolve_row(tiles, y, decay=decay)
        up += u
        down += d
        merge += m
    return up, down, merge


def _calendar_advance(state: SimState) -> bool:
    """0x3FBCF month step. economy_recompute 0x3FCA0 is stubbed."""
    state.week_gate += 1
    if state.week_gate < 1:
        return False
    state.week_gate = 0
    state.month += 1
    if state.month < 12:
        return True
    state.month = 0
    state.year_raw += 1
    return True


def city_sim_phase(tiles: bytearray, state: SimState) -> PhaseResult:
    """One [0x1026A8] slot, then ++, wrap after 0xD6."""
    phase = state.phase
    name = slot_name(phase)
    implemented = slot_implemented(phase)
    up = down = merge = 0
    wrapped = False

    if 1 <= phase <= 0x50:
        row = phase - 1
        state.row = row
        up, down, merge = evolve_row(tiles, row, decay=state.wrap3 == 0)
    # else: stub / empty / wipe-skipped

    state.phase = phase + 1
    if state.phase > PHASE_MAX:
        state.wrap4 = (state.wrap4 + 1) % 4
        state.wrap3 = (state.wrap3 + 1) % 3
        state.phase = 0
        wrapped = _calendar_advance(state)

    return PhaseResult(
        phase=phase,
        name=name,
        implemented=implemented,
        houses_up=up,
        houses_down=down,
        houses_merge=merge,
        month_wrapped=wrapped,
        date_label=state.date_label,
    )


def slot_table_rows() -> list[tuple[str, str, str]]:
    """(id, one-line, Y/N) for findings/ghidra_sim.md."""
    bands = [
        ("0", slot_name(0), "N"),
        ("1–0x50", "housing evolve + merge (80 rows)", "Y"),
        ("0x51", slot_name(0x51), "N"),
        ("0x52", slot_name(0x52), "N"),
        ("0x53", slot_name(0x53), "N"),
        ("0x54", slot_name(0x54), "N"),
        ("0x55", slot_name(0x55), "Y"),
        ("0x56–0x5D", slot_name(0x56), "N"),
        ("0x5E–0x65", slot_name(0x5E), "N"),
        ("0x66–0x6D", slot_name(0x66), "N"),
        ("0x6E–0x75", slot_name(0x6E), "N"),
        ("0x76–0x7D", slot_name(0x76), "N"),
        ("0x7E–0x8D", slot_name(0x7E), "N"),
        ("0x8E–0x91", slot_name(0x8E), "N"),
        ("0x92–0x95", slot_name(0x92), "N"),
        ("0x96–0x99", slot_name(0x96), "N"),
        ("0x9A–0x9D", slot_name(0x9A), "N"),
        ("0x9E–0xA1", slot_name(0x9E), "N"),
        ("0xA2–0xC1", slot_name(0xA2), "N"),
        ("0xC2–0xC9", slot_name(0xC2), "N"),
        ("0xCA", slot_name(0xCA), "N"),
        ("0xCB", slot_name(0xCB), "N"),
        ("0xCC", slot_name(0xCC), "N"),
        ("0xCD", slot_name(0xCD), "N"),
        ("0xCE–0xD0", slot_name(0xCE), "N"),
        ("0xD1", slot_name(0xD1), "N"),
        ("0xD2", slot_name(0xD2), "N"),
        ("0xD3", slot_name(0xD3), "N"),
        ("0xD4–0xD6", slot_name(0xD4), "Y"),
        ("wrap >0xD6", "calendar_advance month; economy stub", "Y"),
    ]
    return bands


def housing_id_counts(tiles: bytearray) -> dict[int, int]:
    counts: dict[int, int] = {}
    for y in range(MAP_H):
        for x in range(MAP_W):
            hid = tiles[_off(x, y)]
            if ID_HOUSING_LO <= hid <= ID_HOUSING_HI:
                counts[hid] = counts.get(hid, 0) + 1
    return counts


def _blank_tiles() -> bytearray:
    return bytearray(MAP_W * MAP_H * 20)


def selftest() -> list[str]:
    """No display. Synthetic tiles — does not need a .SAV."""
    lines: list[str] = []
    tiles = _blank_tiles()
    off = _off(10, 10)
    tiles[off] = 0x89
    tiles[off + 15] = 20  # stay max for 0x89 is 16
    u, d, m = evolve_row(tiles, 10, decay=False)
    ok = tiles[off] == 0x8A and u == 1 and d == 0 and m == 0
    lines.append(f"1x1 up 0x89->0x8A +15=20: {'ok' if ok else 'FAIL'} id={tiles[off]:#x} u={u}")

    tiles = _blank_tiles()
    off = _off(10, 10)
    tiles[off] = 0x89
    tiles[off + 15] = 10  # min is 13
    u, d, m = evolve_row(tiles, 10, decay=False)
    ok = tiles[off] == 0x88 and d == 1
    lines.append(f"1x1 down 0x89->0x88 +15=10: {'ok' if ok else 'FAIL'} id={tiles[off]:#x} d={d}")

    tiles = _blank_tiles()
    off = _off(10, 10)
    tiles[off] = 0x89
    tiles[off + 15] = 16
    u, d, m = evolve_row(tiles, 10, decay=False)
    ok = tiles[off] == 0x89 and u == 0 and d == 0
    lines.append(f"1x1 stay +15=16: {'ok' if ok else 'FAIL'} id={tiles[off]:#x}")

    tiles = _blank_tiles()
    off = _off(20, 20)
    tiles[off] = ID_GRAND_DOMUS
    tiles[off + 15] = 60  # stay max 52
    u, d, m = evolve_row(tiles, 20, decay=False)
    ok = tiles[off] == 0x9C and m == 1
    piece = [tiles[_off(20 + dx, 20 + dy) + 5] & 0xF for dy in range(2) for dx in range(2)]
    ids = [tiles[_off(20 + dx, 20 + dy)] for dy in range(2) for dx in range(2)]
    lines.append(
        f"villa SE merge 0x9B->0x9C: {'ok' if ok and ids == [0x9C] * 4 and piece == [0, 1, 2, 3] else 'FAIL'} "
        f"ids={ids} +5={piece} m={m}"
    )

    tiles = _blank_tiles()
    for dy in range(2):
        for dx in range(2):
            off = _off(20 + dx, 20 + dy)
            tiles[off] = 0x9F
            tiles[off + 5] = dy * 2 + dx
            tiles[off + 15] = 64
    u, d, m = evolve_row(tiles, 20, decay=False)
    ids = [tiles[_off(20 + dx, 20 + dy)] for dy in range(3) for dx in range(3)]
    piece = [tiles[_off(20 + dx, 20 + dy) + 5] & 0xF for dy in range(3) for dx in range(3)]
    ok = ids == [0xA0] * 9 and piece == list(range(9)) and m == 1
    lines.append(
        f"palace SE merge 0x9F->0xA0: {'ok' if ok else 'FAIL'} ids={ids[:3]}.. +5={piece} m={m}"
    )

    tiles = _blank_tiles()
    # Achea-style wipe: +15=0 on a Small house → down (EXE), not a no-op.
    off = _off(5, 5)
    tiles[off] = 0x89
    tiles[off + 15] = 0
    u, d, m = evolve_row(tiles, 5, decay=False)
    lines.append(
        f"Achea-style +15=0 on 0x89: down->{tiles[off]:#x} (d={d}) - not a no-op"
    )
    return lines
