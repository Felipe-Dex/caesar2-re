"""Host stand-in for city_sim_phase 0x3F60C — one slot per pulse.

Implemented: housing evolve 1–0x50, wipes + paint +13/+14/+15, +17 flood,
walker emit, fire tick / collapse 0x9E–0xA1, wrap → calendar month.
City Only stubs (0xC2–0xD1, 0xD3) advance the slot with no work — they
are not jumped for a fake month.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from app.calendar import (
    MONTH_CHUNK,
    SPEED_SCALAR_DEFAULT,
    YEAR_CHUNK,
    GameDate,
    calendar_advance,
    format_hud_date,
    sim_tick_interval_ms,
)
from app.city_map import (
    FLAG_PAD,
    ID_HOUSING_HI,
    ID_HOUSING_LO,
    MAP_H,
    MAP_W,
    ROW_STRIDE,
    SAV_HISTORY_BYTES,
    SAV_SIZE,
    SAV_TABLE_BYTES,
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

# 42e25 ebx try 0..3: SE / SW / NW / NE. Same origin shift for 2×2 and 3×3.
# pick_block 42bc4 returns try+1; evolve_up decs before stamp.
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
        return "wipe +13"
    if phase == 0x52:
        return "wipe +15"
    if phase == 0x53:
        return "wipe +14"
    if phase == 0x54:
        return "wipe +12"
    if phase == 0x55:
        return "nop"
    if 0x56 <= phase <= 0x5D:
        return f"paint +13 reservoir row {(phase - 0x56) * 10}"
    if 0x5E <= phase <= 0x65:
        return f"paint +14 security row {(phase - 0x5E) * 10}"
    if 0x66 <= phase <= 0x6D:
        return f"paint +12 amenities / +13 education row {(phase - 0x66) * 10}"
    if 0x6E <= phase <= 0x75:
        return f"paint +13 water row {(phase - 0x6E) * 10}"
    if 0x76 <= phase <= 0x7D:
        return f"land-value +15 row {(phase - 0x76) * 10}"
    if 0x7E <= phase <= 0x8D:
        return f"housing cap +15 row {(phase - 0x7E) * 5}"
    if 0x8E <= phase <= 0x91:
        return f"forum emit row {(phase - 0x8E) * 20}"
    if 0x92 <= phase <= 0x95:
        return f"tower emit row {(phase - 0x92) * 20}"
    if 0x96 <= phase <= 0x99:
        return f"prefecture/barracks emit row {(phase - 0x96) * 20}"
    if 0x9A <= phase <= 0x9D:
        return f"market/factory emit row {(phase - 0x9A) * 20}"
    if 0x9E <= phase <= 0xA1:
        return "immigrant / rioter 0x41DD4 (City Only skip)"
    if 0xA2 <= phase <= 0xC1:
        return f"road flood +17 dir {(phase - 0xA2) // 8} row {((phase - 0xA2) % 8) * 10}"
    if 0xC2 <= phase <= 0xC9:
        return "0x445AF (City Only skip)"
    if phase == 0xCA:
        return "0x43F88 (City Only skip)"
    if phase == 0xCB:
        return "0x53C67 (City Only skip)"
    if phase == 0xCC:
        return "0x29A19 (City Only skip)"
    if phase == 0xCD:
        return "0x456F6 (City Only skip)"
    if 0xCE <= phase <= 0xD0:
        return "0x4327B (City Only skip)"
    if phase == 0xD1:
        return "0x43B2E (City Only skip)"
    if phase == 0xD2:
        return "walkers_relink_tiles"
    if phase == 0xD3:
        return "overlay dispatch (host paints live)"
    if 0xD4 <= phase <= 0xD6:
        return "empty"
    return f"unknown slot {phase:#x}"


def slot_implemented(phase: int) -> bool:
    """Work the host actually runs (not City Only empty skips)."""
    if 1 <= phase <= 0x54:
        return True
    if phase == 0x55:
        return True
    if 0x56 <= phase <= 0x8D:
        return True
    if 0x8E <= phase <= 0x9D:
        return True
    if 0xA2 <= phase <= 0xC1:
        return True
    if phase == 0xD2:
        return True
    if 0xD4 <= phase <= 0xD6:
        return True
    return False


def slot_city_only_skip(phase: int) -> bool:
    """EXE still increments these; City Only has nothing to do."""
    if phase == 0:
        return True
    if 0x9E <= phase <= 0xA1:
        return True
    if 0xC2 <= phase <= 0xD1:
        return True
    if phase == 0xD3:
        return True
    return False


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
    industrial_tax: int = 5
    history: bytearray = field(default_factory=lambda: bytearray(4000))
    # sim_tick_due 0x3E4B9 / view_frame catch-up. Original starts unpaused.
    paused: bool = False
    speed_scalar: int = SPEED_SCALAR_DEFAULT  # [0x9CE50]
    catchup: int = 0  # [0xC45A0] 0 → 1 pulse; ≠0 → 4
    tick_acc: int = 0  # [0x117ACC] ms accumulator
    population: int = 0  # [0x102AB0] — emit needs >= 2
    pop_peak: int = 0  # FAQ latch: unlocks stay after pop drops
    flood_dir: int = 0  # [0x102678] 0…3
    fire_ignited: int = 0  # one 69A37 per 0x9E–0xA1 pass
    # Forum / PLEBS — chunks 52 / 54 / 55 / 56 @ 0x102A68 / 0x102A98 /
    # 0x102AC4 / 0xD2E6C. Tax 29/30 @ 0x102A7C / 0x102AA8. Oracle 286–289
    # + avg 46. New City Only seeds via init_city_only_labor (0x563E2);
    # sav_read keeps the file bytes and must not re-run that init.
    plebs_ready: int = 0
    plebs_estimate: int = 0
    plebs_last: int = 0
    welfare: int = 0
    labor_index: int = 1  # [0x1025C8] = skill*2+1 (0x346F6)
    labor_assigned: list = field(default_factory=lambda: [0] * 7)
    labor_need: list = field(default_factory=lambda: [0] * 7)
    employed_pct: int = 0
    tax_wealth: int = 0  # [0x1028EC] market-served housing
    ind_wealth: int = 0  # [0x102934] factory stock×70
    factory_count: int = 0  # 0xFA origins; av-bill stand-in for [0x10279c]
    goods: bytearray = field(default_factory=lambda: bytearray(768))  # chunk 339
    factory_labor: int = 0  # chunk 140 [0x102b08] — 41b33 labor seed
    province_links: int = 0  # chunk 276 [0x102714] — 0 = City Only / no farms
    tribute: int = 0  # chunk 157; City Only stays 0
    tax_ytd: int = 0  # [0x102924] raw pop-tax accumulator
    tax_months: int = 0  # [0x1028E4]
    ind_tax_ytd: int = 0  # [0x102908]
    ind_tax_months: int = 0  # [0x1028F4]
    operating_ytd: int = 0  # [0x102A60] welfare already spent this year
    construct_ytd: int = 0  # [0x102A2C]
    surplus_last: int = 0
    pop_tax_last: int = 0
    ind_tax_last: int = 0
    construct_last: int = 0
    operating_last: int = 0
    rating_empire: int = 0
    rating_peace: int = 0
    rating_prosperity: int = 0
    rating_culture: int = 0
    rating_avg: int = 0

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
    walkers_spawned: int = 0
    month_wrapped: bool = False
    date_label: str = ""
    note: str = ""

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


def _chunk_u8(chunks: Sequence[memoryview], index: int, default: int = 0) -> int:
    """SavChunks 16 (skill) and 406 (city_only) are 1 byte in the writer table."""
    if index >= len(chunks) or len(chunks[index]) < 1:
        return default
    return chunks[index][0]


def _history_from_sav(data: bytes) -> bytearray:
    if len(data) >= SAV_SIZE:
        return bytearray(data[SAV_TABLE_BYTES:SAV_SIZE])
    return bytearray(SAV_HISTORY_BYTES)


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
    treasury = 0
    if len(chunks) > 28 and len(chunks[28]) >= 4:
        treasury = _chunk_i32(chunks, 28, 0)
    assigned, need = _load_labor_table(chunks)
    assigned[0] = 20
    need[0] = 20
    skill = _chunk_u8(chunks, 16, 0)
    city_only = _chunk_u8(chunks, 406, 0)
    goods = bytearray(768)
    if len(chunks) > 339 and len(chunks[339]) >= 768:
        goods[:] = chunks[339][:768]
    labor_index = _chunk_i32(chunks, 416, 0)
    if labor_index <= 0:
        labor_index = max(0, min(4, skill)) * 2 + 1
    state = SimState(
        phase=phase,
        row=_chunk_i32(chunks, ROW_CHUNK, 0),
        year_raw=_chunk_i32(chunks, YEAR_CHUNK, -300),
        month=month,
        week_gate=_chunk_i32(chunks, WEEK_GATE_CHUNK, 0),
        wrap3=_chunk_i32(chunks, 405, 0),
        wrap4=_chunk_i32(chunks, 22, 0),
        source=path.name,
        skill=skill,
        city_only=city_only,
        pid=_chunk_i32(chunks, 223, 0),
        treasury=treasury,
        ratings_seed=_chunk_i32(chunks, 341, 0),
        tax_rate=_chunk_i32(chunks, 29, 5),
        industrial_tax=_chunk_i32(chunks, 30, 5),
        history=_history_from_sav(data),
        labor_index=labor_index,
        population=_chunk_i32(chunks, 32, 0),
        employed_pct=_chunk_i32(chunks, 31, 0),
        plebs_ready=_chunk_i32(chunks, 52, 0),
        plebs_estimate=_chunk_i32(chunks, 55, 0),
        plebs_last=_chunk_i32(chunks, 52, 0),
        welfare=_chunk_i32(chunks, 54, 0),
        labor_assigned=assigned,
        labor_need=need,
        goods=goods,
        factory_labor=_chunk_i32(chunks, 140, 0),
        province_links=_chunk_i32(chunks, 276, 0),
        tribute=0 if city_only else _chunk_i32(chunks, 157, 0),
        surplus_last=_chunk_i32(chunks, 33, 0),
        pop_tax_last=_chunk_i32(chunks, 34, 0),
        ind_tax_last=_chunk_i32(chunks, 35, 0),
        construct_last=_chunk_i32(chunks, 36, 0),
        operating_last=_chunk_i32(chunks, 37, 0),
        rating_empire=_chunk_i32(chunks, 286, 0),
        rating_peace=_chunk_i32(chunks, 287, 0),
        rating_prosperity=_chunk_i32(chunks, 288, 0),
        rating_culture=_chunk_i32(chunks, 289, 0),
        rating_avg=_chunk_i32(chunks, 46, 0),
    )
    from app.forum import apply_saved_plebs

    apply_saved_plebs(state)
    return state


def _load_labor_table(chunks: Sequence[memoryview]) -> tuple[list[int], list[int]]:
    """Chunk 56 [0xD2E6C]: 8 pairs assigned/need (last pair = idle / pad)."""
    assigned = [0] * 7
    need = [0] * 7
    if len(chunks) <= 56 or len(chunks[56]) < 56:
        return assigned, need
    raw = chunks[56]
    for i in range(7):
        assigned[i] = struct.unpack_from("<i", raw, i * 8)[0]
        need[i] = struct.unpack_from("<i", raw, i * 8 + 4)[0]
    return assigned, need


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


def _has_pad_neighbor(tiles: bytearray, x: int, y: int) -> bool:
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        nx, ny = x + dx, y + dy
        if _in_map(nx, ny) and tiles[_off(nx, ny) + 1] & FLAG_PAD:
            return True
    return False


def house_stay_reason(tiles: bytearray, x: int, y: int, *, population: int = 0) -> str:
    """Why this origin did not (or would not) change grade this pulse."""
    from app.city_paint import housing_cap_detail, service_target_lv

    off = _off(x, y)
    hid = tiles[off]
    if not (ID_HOUSING_LO <= hid <= ID_HOUSING_HI):
        return "not-house"
    if tiles[off + 5] & 0xF:
        return "not-origin"
    grade = hid - 0x82
    lv = i8(tiles[off + 15])
    water = tiles[off + 13] & 0x03
    plus17 = i8(tiles[off + 17])
    stay_lo, stay_hi = EVOLVE_MIN[grade], EVOLVE_MAX[grade]
    cap, gate = housing_cap_detail(tiles, x, y, population=population)
    target = service_target_lv(lv, cap)
    bits = [
        f"id={hid:#x}",
        f"+15={lv}",
        f"target={target}",
        f"stay={stay_lo}..{stay_hi}",
        f"cap={cap}",
    ]
    if water == 0:
        bits.append("no-water +13")
    else:
        bits.append(f"water={water:#x}")
    if not _has_pad_neighbor(tiles, x, y):
        bits.append("no-road")
    if plus17:
        bits.append(f"+17={plus17}")
    bits.append(gate)
    if hid < 0x8E:
        bits.append(f"need-insula cap>=24 (have {cap})")
    if lv < stay_lo:
        bits.append("would-down")
    elif lv > stay_hi:
        bits.append("table-hit" if HOUSE_SIZE[grade] == HOUSE_SIZE[min(grade + 1, 31)] else "merge-blocked")
    else:
        bits.append("lv-in-stay")
    return " ".join(bits)


def diagnose_housing_row(
    tiles: bytearray, y: int, *, limit: int = 4, population: int = 0
) -> list[str]:
    out: list[str] = []
    if not (0 <= y < MAP_H):
        return out
    for x in range(MAP_W):
        off = _off(x, y)
        if tiles[off + 5] & 0xF:
            continue
        hid = tiles[off]
        if ID_HOUSING_LO <= hid <= ID_HOUSING_HI:
            out.append(
                f"({x},{y}) {house_stay_reason(tiles, x, y, population=population)}"
            )
            if len(out) >= limit:
                break
    return out


def evolve_row(
    tiles: bytearray, y: int, *, decay: bool = True, population: int = 0
) -> tuple[int, int, int]:
    """city_buildings_evolve_row 0x42360 for one map row. Housing only."""
    from app.city_paint import housing_cap_detail, service_target_lv

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
            raw = _block_lv(tiles, x, y, 3)
        elif grade >= 26:
            raw = _block_lv(tiles, x, y, 2)
        else:
            raw = i8(tiles[off + 15])
        cap, _gate = housing_cap_detail(tiles, x, y, population=population)
        raised = service_target_lv(raw, cap)
        lv = raised if raised > raw else raw
        if lv != raw:
            tiles[off + 15] = lv & 0xFF
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


def evolve_all_rows(
    tiles: bytearray, *, decay: bool = True, population: int = 0
) -> tuple[int, int, int]:
    """Host-only: all 80 evolve rows. Not one EXE pulse."""
    up = down = merge = 0
    for y in range(MAP_H):
        u, d, m = evolve_row(tiles, y, decay=decay, population=population)
        up += u
        down += d
        merge += m
    return up, down, merge


def diagnose_hut_insula(tiles: bytearray, *, population: int = 0, limit: int = 4) -> list[str]:
    """Why 0x83–0x8D origins have not reached primitive insula 0x8E."""
    out: list[str] = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off + 5] & 0xF:
                continue
            hid = tiles[off]
            if 0x83 <= hid < 0x8E:
                out.append(
                    f"hut-not-insula ({x},{y}) "
                    f"{house_stay_reason(tiles, x, y, population=population)}"
                )
                if len(out) >= limit:
                    return out
    return out


def _phase_wrap(state: SimState) -> bool:
    """Reset [0x1026A8] after 0xD6 and run calendar_advance 0x3FBCF + books."""
    state.wrap4 = (state.wrap4 + 1) % 4
    state.wrap3 = (state.wrap3 + 1) % 3
    state.phase = 0
    wrapped = calendar_advance(state)
    if getattr(state, "city_only", 0):
        from app.forum import apply_month_labor

        apply_month_labor(state)
    return wrapped


def _band10(phase: int, lo: int) -> tuple[int, int]:
    start = (phase - lo) * 10
    return start, 10


def _band5(phase: int, lo: int) -> tuple[int, int]:
    start = (phase - lo) * 5
    return start, 5


def _band20(phase: int, lo: int) -> tuple[int, int]:
    start = (phase - lo) * 20
    return start, 20


# +3 bit7 + +16 countdown. Ignite 0x69A37 writes 10; overlay 0x3E8A2
# paints +11 bits 4–5 (0x10/0x20/0x30). 445AF ignites when those bits
# are 0x30. Collapse to host rubble 0x05 (Clear); leftover bit7 so
# vigile state 9 can seek id<8 fires (4A716 / 4A57F).
ID_RUBBLE = 0x05
DRAW_FIRE = 0x80
FIRE_TIMER_IGNITE = 10


def tile_ignite(tiles: bytearray, off: int) -> None:
    """FUN_00069a37: +11 &= 0xC0, +3 |= 0x81, +16 = 10."""
    if off < 0 or off + 16 >= len(tiles):
        return
    tiles[off + 11] &= 0xC0
    tiles[off + 3] = (tiles[off + 3] | 0x81) & 0xFF
    tiles[off + 16] = FIRE_TIMER_IGNITE


def _housing_footprint(tiles: bytearray, x: int, y: int) -> list[tuple[int, int]]:
    """Origin from +5 lo-nibble; size from HOUSE_SIZE[grade]."""
    if not _in_map(x, y):
        return []
    off = _off(x, y)
    tid = tiles[off]
    if tid < ID_HOUSING_LO or tid > ID_HOUSING_HI:
        return [(x, y)]
    grade = tid - ID_HOUSING_LO
    size = HOUSE_SIZE[grade] if grade < len(HOUSE_SIZE) else 1
    if size <= 1:
        return [(x, y)]
    piece = tiles[off + 5] & 0xF
    col = piece % size
    row = piece // size
    ox, oy = x - col, y - row
    cells = []
    for dy in range(size):
        for dx in range(size):
            if _in_map(ox + dx, oy + dy):
                cells.append((ox + dx, oy + dy))
    return cells or [(x, y)]


def tile_ignite_building(tiles: bytearray, x: int, y: int) -> int:
    """693BB / 69408: ignite the housing footprint."""
    n = 0
    for cx, cy in _housing_footprint(tiles, x, y):
        tile_ignite(tiles, _off(cx, cy))
        n += 1
    return n


def tile_collapse_rubble(
    tiles: bytearray, x: int, y: int, *, leave_fire: bool = True
) -> int:
    """691C4 / 696E8 host: whole footprint → rubble 0x05.

    EXE 696E8 writes rng>>1 terrain. Host Clear / this pass stay on 0x05.
    leave_fire keeps +3 bit7 and +16 so vigiles can seek id<8.
    """
    n = 0
    for cx, cy in _housing_footprint(tiles, x, y):
        off = _off(cx, cy)
        tiles[off] = ID_RUBBLE
        tiles[off + 1] &= 0x18
        tiles[off + 4] = 0
        tiles[off + 5] = 0
        tiles[off + 9] = 0
        tiles[off + 10] = 0
        tiles[off + 11] &= 0xC0
        if leave_fire:
            tiles[off + 3] = (tiles[off + 3] | 0x81) & 0xFF
            tiles[off + 16] = FIRE_TIMER_IGNITE
        else:
            tiles[off + 3] = (tiles[off + 3] & 0x7F) | 0x01
            tiles[off + 16] = 0
        n += 1
    return n


def _fire_neighbor(x: int, y: int, facing: int) -> tuple[int, int] | None:
    if facing == 0:
        nx, ny = x, y - 1
    elif facing == 2:
        nx, ny = x + 1, y
    elif facing == 4:
        nx, ny = x, y + 1
    elif facing == 6:
        nx, ny = x - 1, y
    else:
        return None
    if not _in_map(nx, ny):
        return None
    return nx, ny


def fire_spread_housing(tiles: bytearray, x: int, y: int, facing: int) -> int:
    """FUN_00069334: ignite neighbor housing if that tile’s bit7 is clear."""
    nb = _fire_neighbor(x, y, facing)
    if nb is None:
        return 0
    nx, ny = nb
    off = _off(nx, ny)
    tid = tiles[off]
    if tid < ID_HOUSING_LO or tid > ID_HOUSING_HI:
        return 0
    if tiles[off + 3] & DRAW_FIRE:
        return 0
    return tile_ignite_building(tiles, nx, ny)


def _raise_fire_risk(tiles: bytearray, off: int) -> int:
    """+11 bits 4–5: 0 → 0x10 → 0x20 → 0x30 (overlay 0x3E8A2)."""
    bits = tiles[off + 11] & 0x30
    if bits >= 0x30:
        return 0x30
    nxt = 0x10 if bits == 0 else 0x20 if bits == 0x10 else 0x30
    tiles[off + 11] = (tiles[off + 11] & 0xCF) | nxt
    return nxt


def _lower_fire_risk(tiles: bytearray, off: int) -> int:
    bits = tiles[off + 11] & 0x30
    if bits == 0:
        return 0
    nxt = 0x20 if bits == 0x30 else 0x10 if bits == 0x20 else 0
    tiles[off + 11] = (tiles[off + 11] & 0xCF) | nxt
    return nxt


def fire_tick_rows(
    tiles: bytearray,
    y0: int,
    n: int,
    state: SimState | None = None,
) -> tuple[int, int, int]:
    """41DD4 fire slice (City Only: skip immigrant / rioter spawn).

    Returns (decremented, collapsed, ignited).
    """
    if state is not None and y0 == 0:
        state.fire_ignited = 0
    dec = col = ign = 0
    y1 = min(MAP_H, y0 + n)
    for y in range(y0, y1):
        for x in range(MAP_W):
            off = _off(x, y)
            tid = tiles[off]
            on_fire = bool(tiles[off + 3] & DRAW_FIRE)
            if on_fire:
                timer = tiles[off + 16]
                nxt = (timer - 1) & 0xFF
                tiles[off + 16] = nxt
                dec += 1
                if tid < 8:
                    if nxt == 0:
                        tiles[off + 3] &= 0x7F
                    else:
                        fire_spread_housing(
                            tiles, x, y, (0, 2, 4, 6)[(x + y) & 3]
                        )
                    continue
                if ID_HOUSING_LO <= tid <= ID_HOUSING_HI:
                    tiles[off + 11] &= 0xCF
                    if nxt == 0:
                        col += tile_collapse_rubble(tiles, x, y, leave_fire=True)
                    elif nxt != 9:
                        fire_spread_housing(
                            tiles, x, y, (0, 2, 4, 6)[(x + y) & 3]
                        )
                continue
            if not (ID_HOUSING_LO <= tid <= ID_HOUSING_HI):
                continue
            if tiles[off + 5] & 0xF:
                continue
            covered = bool(tiles[off + 10] & 0x30)
            if covered:
                _lower_fire_risk(tiles, off)
                continue
            risk = _raise_fire_risk(tiles, off)
            if risk == 0x30 and (state is None or state.fire_ignited == 0):
                ign += tile_ignite_building(tiles, x, y)
                if state is not None:
                    state.fire_ignited = 1
    return dec, col, ign


def _walker_live_count(walkers) -> int:
    if walkers is None:
        return 0
    if isinstance(walkers, bytearray):
        stride = 0x3A
        return sum(
            1
            for slot in range(1, min(201, len(walkers) // stride))
            if walkers[slot * stride]
        )
    return sum(1 for w in walkers if getattr(w, "occupied", 0))


def _log_phase(
    state: SimState,
    phase: int,
    name: str,
    *,
    up: int = 0,
    down: int = 0,
    spawned: int = 0,
    note: str = "",
    wrapped: bool = False,
    walkers=None,
    tiles: bytearray | None = None,
) -> str:
    from app.sim_log import format_phase, write

    line = format_phase(
        date=state.date_label,
        phase=phase,
        name=name,
        houses_up=up,
        houses_down=down,
        spawned=spawned,
        note=note,
    )
    write(line)
    if wrapped and tiles is not None:
        counts = housing_id_counts(tiles)
        house_bits = " ".join(
            f"{hid:#x}:{n}" for hid, n in sorted(counts.items())
        ) or "none"
        write(
            f"{state.date_label}  WRAP  pop={state.population}  "
            f"houses={{{house_bits}}}  walkers={_walker_live_count(walkers)}"
        )
    return line


def city_sim_phase(
    tiles: bytearray,
    state: SimState,
    walkers=None,
) -> PhaseResult:
    """One [0x1026A8] slot, then ++, wrap after 0xD6."""
    from app.city_paint import (
        cap_housing_plus15,
        flood_plus17,
        paint_land_value,
        paint_plus12_amenities,
        paint_plus13_buildings,
        paint_plus13_water,
        paint_plus14_security,
        recount_population,
        wipe_lane,
    )
    from app import walker_tick as wt
    from app.walker_tick import emit_walkers, relink_walker_tiles

    phase = state.phase
    name = slot_name(phase)
    implemented = slot_implemented(phase)
    up = down = merge = spawned = painted = 0
    wrapped = False
    note = ""
    can = len(tiles) >= MAP_W * MAP_H * TILE_STRIDE

    if can:
        from app.unlocks import note_population

        note_population(state, recount_population(tiles))

    if 1 <= phase <= 0x50:
        row = phase - 1
        state.row = row
        if can:
            up, down, merge = evolve_row(
                tiles, row, decay=state.wrap3 == 0, population=state.population
            )
            from app.unlocks import note_population

            note_population(state, recount_population(tiles))
            stays = diagnose_housing_row(
                tiles, row, population=state.population
            )
            if stays:
                note = f"n={len(stays)} " + "; ".join(stays)
    elif phase == 0x51 and can:
        wipe_lane(tiles, 13)
        note = "wiped +13"
    elif phase == 0x52 and can:
        wipe_lane(tiles, 15)
        note = "wiped +15"
    elif phase == 0x53 and can:
        wipe_lane(tiles, 14)
        note = "wiped +14"
    elif phase == 0x54 and can:
        wipe_lane(tiles, 12)
        note = "wiped +12"
    elif 0x56 <= phase <= 0x5D and can:
        y0, n = _band10(phase, 0x56)
        state.row = y0
        painted = paint_plus13_buildings(tiles, y0, n)
        note = f"written={painted}"
    elif 0x5E <= phase <= 0x65 and can:
        y0, n = _band10(phase, 0x5E)
        state.row = y0
        painted = paint_plus14_security(tiles, y0, n)
        note = f"written={painted}"
    elif 0x66 <= phase <= 0x6D and can:
        y0, n = _band10(phase, 0x66)
        state.row = y0
        painted = paint_plus12_amenities(tiles, y0, n)
        note = f"amenity-splash={painted}"
    elif 0x6E <= phase <= 0x75 and can:
        y0, n = _band10(phase, 0x6E)
        state.row = y0
        from app.forum import labor_shutoff, refresh_labor_need

        refresh_labor_need(state, tiles)
        shut = labor_shutoff(state)
        painted = paint_plus13_water(
            tiles, y0, n, water_staffed="water" not in shut
        )
        note = f"water-splash={painted}"
        if "water" in shut:
            note += " understaffed"
    elif 0x76 <= phase <= 0x7D and can:
        y0, n = _band10(phase, 0x76)
        state.row = y0
        painted = paint_land_value(tiles, y0, n)
        note = f"lv-written={painted}"
    elif 0x7E <= phase <= 0x8D and can:
        y0, n = _band5(phase, 0x7E)
        state.row = y0
        painted = cap_housing_plus15(tiles, y0, n, population=state.population)
        note = f"capped={painted} pop={state.population}"
        if painted:
            stalls = diagnose_hut_insula(tiles, population=state.population, limit=2)
            if stalls:
                note += " " + "; ".join(stalls)
    elif 0x8E <= phase <= 0x9D and can:
        y0, n = _band20(phase, 0x8E if phase <= 0x91 else (
            0x92 if phase <= 0x95 else (0x96 if phase <= 0x99 else 0x9A)
        ))
        state.row = y0
        if phase <= 0x91:
            kinds = "forum"
        elif phase <= 0x95:
            kinds = "tower"
        elif phase <= 0x99:
            kinds = "security"
        else:
            kinds = "market"
        from app.forum import labor_shutoff, refresh_labor_need

        refresh_labor_need(state, tiles)
        shut = labor_shutoff(state)
        spawned = emit_walkers(
            tiles,
            walkers,
            y0,
            n,
            population=state.population,
            kinds=kinds,
            wrap4=state.wrap4,
            goods=state.goods,
            factory_labor=state.factory_labor,
            province_links=state.province_links,
            shutoff=shut,
            city_only=bool(getattr(state, "city_only", 0)),
        )
        note = wt.LAST_EMIT_NOTE or f"pop={state.population}"
    elif 0x9E <= phase <= 0xA1 and can:
        y0, n = _band20(phase, 0x9E)
        state.row = y0
        dec, col, ign = fire_tick_rows(tiles, y0, n, state)
        painted = dec + col + ign
        note = f"fire --={dec} collapse={col} ignite={ign}"
    elif 0xA2 <= phase <= 0xC1 and can:
        slot = phase - 0xA2
        state.flood_dir = slot // 8
        y0 = (slot % 8) * 10
        state.row = y0
        if slot == 0:
            painted = flood_plus17(tiles, y0, 10, state.flood_dir)
            note = f"flood-rebuild={painted}"
    elif phase == 0xD2 and can:
        relink_walker_tiles(tiles, walkers)
        note = f"relink walkers={_walker_live_count(walkers)}"
    elif slot_city_only_skip(phase):
        note = "phase-skipped City Only"

    log_this = False
    if 1 <= phase <= 0x50 and note.startswith("n="):
        log_this = True
    elif phase in (0x51, 0x52, 0x53, 0x54, 0xA2):
        log_this = True
    elif painted or spawned or up or down:
        log_this = True
    elif 0x8E <= phase <= 0x9D and note and "civic=0" not in note:
        log_this = True
    elif 0x9E <= phase <= 0xA1 and painted:
        log_this = True
    elif phase == 0xD2 and "walkers=0" not in note:
        log_this = True
    log_line = ""
    if log_this:
        log_line = _log_phase(
            state,
            phase,
            name,
            up=up,
            down=down,
            spawned=spawned,
            note=note,
            wrapped=False,
            walkers=walkers,
            tiles=tiles,
        )

    state.phase = phase + 1
    if state.phase > PHASE_MAX:
        if can:
            from app.city_paint import housing_tax_wealth, industry_tax_wealth

            state.tax_wealth = housing_tax_wealth(tiles)
            state.ind_wealth = industry_tax_wealth(tiles)
        treas_before = int(state.treasury)
        wrapped = _phase_wrap(state)
        if not log_this:
            _log_phase(
                state,
                phase,
                name,
                up=up,
                down=down,
                spawned=spawned,
                note=note or "calendar wrap",
                wrapped=False,
                walkers=walkers,
                tiles=tiles,
            )
        from app.sim_log import write

        counts = housing_id_counts(tiles) if can else {}
        house_bits = " ".join(
            f"{hid:#x}:{n}" for hid, n in sorted(counts.items())
        ) or "none"
        write(
            f"{state.date_label}  WRAP  pop={state.population}  "
            f"houses={{{house_bits}}}  walkers={_walker_live_count(walkers)}  "
            f"treas={state.treasury} d={state.treasury - treas_before}"
        )
        if can:
            from app.forum import refresh_labor_need

            refresh_labor_need(state, tiles)
            for line in diagnose_hut_insula(
                tiles, population=state.population, limit=4
            ):
                write(f"{state.date_label}  {line}")

    if getattr(state, "city_only", 0) and can:
        from app.messages import scan_city_messages

        ign = 0
        if 0x9E <= phase <= 0xA1:
            ign = int(getattr(state, "fire_ignited", 0))
            if "ignite=" in note:
                try:
                    ign = max(ign, int(note.split("ignite=", 1)[1].split()[0]))
                except ValueError:
                    pass
        scan_city_messages(
            state,
            tiles,
            houses_up=up,
            month_wrapped=wrapped,
            fire_ignited=ign,
        )

    return PhaseResult(
        phase=phase,
        name=name,
        implemented=implemented,
        houses_up=up,
        houses_down=down,
        houses_merge=merge,
        walkers_spawned=spawned,
        month_wrapped=wrapped,
        date_label=state.date_label,
        note=note or log_line,
    )


def city_sim_clock_pulse(
    tiles: bytearray, state: SimState, walkers=None
) -> PhaseResult:
    """One auto-clock pulse (unpaused play / faster).

    Always one city_sim_phase slot — same as the EXE. Empty City Only
    slots still consume the pulse. Do not jump 0x51–0xD6 to the calendar.
    """
    return city_sim_phase(tiles, state, walkers)


def city_sim_until_wrap(
    tiles: bytearray, state: SimState, walkers=None
) -> PhaseResult:
    """Host M: remaining slots this cycle, then one calendar_advance.

    Runs evolve, water/+15 paint, walker emit, and +17 flood. City Only
    empty slots are nops that still increment. Does not skip paint/emit.
    """
    up = down = merge = spawned = 0
    last_phase = state.phase
    last_name = slot_name(state.phase)
    last_impl = slot_implemented(state.phase)
    wrapped = False
    guard = 0
    while guard < 0xE0:
        guard += 1
        result = city_sim_phase(tiles, state, walkers)
        up += result.houses_up
        down += result.houses_down
        merge += result.houses_merge
        spawned += result.walkers_spawned
        last_phase = result.phase
        last_name = result.name
        last_impl = result.implemented
        if result.month_wrapped:
            wrapped = True
            break

    return PhaseResult(
        phase=last_phase,
        name=last_name,
        implemented=last_impl,
        houses_up=up,
        houses_down=down,
        houses_merge=merge,
        walkers_spawned=spawned,
        month_wrapped=wrapped,
        date_label=state.date_label,
        note=f"month houses +{up}/-{down} spawn={spawned}",
    )


def slot_table_rows() -> list[tuple[str, str, str]]:
    """(id, one-line, Y/N) for findings/ghidra_sim.md."""
    bands = [
        ("0", slot_name(0), "N"),
        ("1–0x50", "housing evolve + merge (80 rows)", "Y"),
        ("0x51", slot_name(0x51), "Y"),
        ("0x52", slot_name(0x52), "Y"),
        ("0x53", slot_name(0x53), "Y"),
        ("0x54", slot_name(0x54), "Y"),
        ("0x55", slot_name(0x55), "Y"),
        ("0x56–0x5D", slot_name(0x56), "Y"),
        ("0x5E–0x65", slot_name(0x5E), "Y"),
        ("0x66–0x6D", slot_name(0x66), "Y"),
        ("0x6E–0x75", slot_name(0x6E), "Y"),
        ("0x76–0x7D", slot_name(0x76), "Y"),
        ("0x7E–0x8D", slot_name(0x7E), "Y"),
        ("0x8E–0x91", slot_name(0x8E), "Y"),
        ("0x92–0x95", slot_name(0x92), "Y"),
        ("0x96–0x99", slot_name(0x96), "Y"),
        ("0x9A–0x9D", slot_name(0x9A), "Y"),
        ("0x9E–0xA1", slot_name(0x9E), "Y"),
        ("0xA2–0xC1", slot_name(0xA2), "Y"),
        ("0xC2–0xC9", slot_name(0xC2), "N"),
        ("0xCA", slot_name(0xCA), "N"),
        ("0xCB", slot_name(0xCB), "N"),
        ("0xCC", slot_name(0xCC), "N"),
        ("0xCD", slot_name(0xCD), "N"),
        ("0xCE–0xD0", slot_name(0xCE), "N"),
        ("0xD1", slot_name(0xD1), "N"),
        ("0xD2", slot_name(0xD2), "Y"),
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

    def _house(
        tiles: bytearray,
        x: int,
        y: int,
        hid: int,
        *,
        lv: int = 0,
        flags: int = 1,
        piece: int = 0,
        w7: int = 0,
        w8: int = 0,
    ) -> None:
        off = _off(x, y)
        tiles[off] = hid
        tiles[off + 1] = flags
        tiles[off + 5] = piece
        tiles[off + 7] = w7
        tiles[off + 8] = w8
        tiles[off + 15] = lv & 0xFF

    def _block_ids(tiles: bytearray, ox: int, oy: int, n: int) -> list[int]:
        return [tiles[_off(ox + dx, oy + dy)] for dy in range(n) for dx in range(n)]

    def _block_piece(tiles: bytearray, ox: int, oy: int, n: int) -> list[int]:
        return [tiles[_off(ox + dx, oy + dy) + 5] & 0xF for dy in range(n) for dx in range(n)]

    tiles = _blank_tiles()
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        _house(tiles, 30 + dx, 20 + dy, ID_GRAND_DOMUS, lv=60)
    u, d, m = evolve_row(tiles, 20, decay=False)
    ids = _block_ids(tiles, 30, 20, 2)
    piece = _block_piece(tiles, 30, 20, 2)
    ok = ids == [0x9C] * 4 and piece == [0, 1, 2, 3] and m == 1 and u == 1
    lines.append(
        f"villa 4-house SE 0x9B->0x9C: {'ok' if ok else 'FAIL'} "
        f"ids={ids} +5={piece} m={m} u={u}"
    )

    tiles = _blank_tiles()
    _house(tiles, 21, 20, ID_GRAND_DOMUS, lv=60)
    tiles[_off(22, 20) + 1] = 0x20
    tiles[_off(22, 20)] = 0x52
    u, d, m = evolve_row(tiles, 20, decay=False)
    ids = _block_ids(tiles, 20, 20, 2)
    piece = _block_piece(tiles, 20, 20, 2)
    ok = ids == [0x9C] * 4 and piece == [0, 1, 2, 3] and m == 1
    lines.append(
        f"villa SW merge (SE road): {'ok' if ok else 'FAIL'} "
        f"ids={ids} +5={piece} m={m}"
    )

    tiles = _blank_tiles()
    _house(tiles, 21, 21, ID_GRAND_DOMUS, lv=60)
    tiles[_off(22, 21)] = 0x52
    tiles[_off(22, 21) + 1] = 0x20
    tiles[_off(21, 22)] = 0x52
    tiles[_off(21, 22) + 1] = 0x20
    u, d, m = evolve_row(tiles, 21, decay=False)
    ids = _block_ids(tiles, 20, 20, 2)
    piece = _block_piece(tiles, 20, 20, 2)
    ok = ids == [0x9C] * 4 and piece == [0, 1, 2, 3] and m == 1
    lines.append(
        f"villa NW merge (SE+SW road): {'ok' if ok else 'FAIL'} "
        f"ids={ids} +5={piece} m={m}"
    )

    tiles = _blank_tiles()
    _house(tiles, 20, 21, ID_GRAND_DOMUS, lv=60)
    tiles[_off(21, 22)] = 0x52
    tiles[_off(21, 22) + 1] = 0x20
    tiles[_off(19, 22)] = 0x52
    tiles[_off(19, 22) + 1] = 0x20
    tiles[_off(19, 20)] = 0x52
    tiles[_off(19, 20) + 1] = 0x20
    u, d, m = evolve_row(tiles, 21, decay=False)
    ids = _block_ids(tiles, 20, 20, 2)
    piece = _block_piece(tiles, 20, 20, 2)
    ok = ids == [0x9C] * 4 and piece == [0, 1, 2, 3] and m == 1
    lines.append(
        f"villa NE merge (SE+SW+NW road): {'ok' if ok else 'FAIL'} "
        f"ids={ids} +5={piece} m={m}"
    )

    tiles = _blank_tiles()
    _house(tiles, 20, 20, ID_GRAND_DOMUS, lv=52)
    u, d, m = evolve_row(tiles, 20, decay=False)
    ok = tiles[_off(20, 20)] == ID_GRAND_DOMUS and m == 0 and u == 0
    lines.append(
        f"villa stay +15=52 no merge: {'ok' if ok else 'FAIL'} "
        f"id={tiles[_off(20, 20)]:#x} m={m}"
    )

    tiles = _blank_tiles()
    _house(tiles, 21, 20, ID_GRAND_DOMUS, lv=60)
    tiles[_off(22, 20) + 7] = 1
    u, d, m = evolve_row(tiles, 20, decay=False)
    ids = _block_ids(tiles, 20, 20, 2)
    piece = _block_piece(tiles, 20, 20, 2)
    ok = ids == [0x9C] * 4 and piece == [0, 1, 2, 3] and m == 1
    lines.append(
        f"villa SW after SE walker: {'ok' if ok else 'FAIL'} "
        f"ids={ids} +5={piece} m={m}"
    )

    tiles = _blank_tiles()
    _house(tiles, 0, 10, ID_GRAND_DOMUS, lv=60)
    u, d, m = evolve_row(tiles, 10, decay=False)
    ok = tiles[_off(0, 10)] == ID_GRAND_DOMUS and m == 0
    lines.append(
        f"villa edge x=0 no merge: {'ok' if ok else 'FAIL'} "
        f"id={tiles[_off(0, 10)]:#x} m={m}"
    )

    tiles = _blank_tiles()
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        _house(tiles, 30 + dx, 10 + dy, 0x89, lv=20)
    u, d, m = evolve_row(tiles, 10, decay=False)
    ids = _block_ids(tiles, 30, 10, 2)
    ok = ids == [0x8A, 0x8A, 0x89, 0x89] and m == 0 and u == 2
    lines.append(
        f"four 0x89 stay 1x1 (no villa): {'ok' if ok else 'FAIL'} "
        f"ids={[hex(v) for v in ids]} m={m} u={u}"
    )

    tiles = _blank_tiles()
    for dy in range(2):
        for dx in range(2):
            _house(tiles, 21 + dx, 20 + dy, 0x9F, lv=64, piece=dy * 2 + dx)
    tiles[_off(23, 20)] = 0x52
    tiles[_off(23, 20) + 1] = 0x20
    u, d, m = evolve_row(tiles, 20, decay=False)
    ids = _block_ids(tiles, 20, 20, 3)
    piece = _block_piece(tiles, 20, 20, 3)
    ok = ids == [0xA0] * 9 and piece == list(range(9)) and m == 1
    lines.append(
        f"palace SW merge (SE road): {'ok' if ok else 'FAIL'} "
        f"ids={ids[:3]}.. +5={piece} m={m}"
    )

    tiles = _blank_tiles()
    for dy in range(2):
        for dx in range(2):
            _house(tiles, 20 + dx, 20 + dy, 0x9F, lv=64, piece=dy * 2 + dx)
    for dy in range(2):
        for dx in range(2):
            _house(
                tiles, 22 + dx, 20 + dy, 0x9D, lv=51, piece=dy * 2 + dx
            )
    u, d, m = evolve_row(tiles, 20, decay=False)
    ids = _block_ids(tiles, 20, 20, 3)
    piece = _block_piece(tiles, 20, 20, 3)
    leftover = tiles[_off(23, 20)]
    ok = (
        ids == [0xA0] * 9
        and piece == list(range(9))
        and leftover == ID_GRAND_DOMUS
        and m == 1
    )
    lines.append(
        f"palace SE splits overlapping villa: {'ok' if ok else 'FAIL'} "
        f"ids={ids[:3]}.. leftover={leftover:#x} m={m}"
    )

    from app.city_map import CityMap
    from app.place import ID_RUBBLE, TOOL_CLEAR, try_place

    tiles = _blank_tiles()
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        _house(tiles, 40 + dx, 40 + dy, ID_GRAND_DOMUS, lv=60)
    evolve_row(tiles, 40, decay=False)
    city = CityMap()
    city.tiles[:] = tiles
    r = try_place(city, 41, 41, TOOL_CLEAR, SimState(treasury=100))
    rubble = [city.tiles[city.offset(40 + dx, 40 + dy)] for dy in range(2) for dx in range(2)]
    ok = r.ok and rubble == [ID_RUBBLE] * 4
    lines.append(
        f"Clear N×N after villa merge: {'ok' if ok else 'FAIL'} "
        f"{r.message} ids={[hex(v) for v in rubble]}"
    )

    tiles = _blank_tiles()
    for dy in range(2):
        for dx in range(2):
            _house(tiles, 50 + dx, 50 + dy, 0x9F, lv=64, piece=dy * 2 + dx)
    evolve_row(tiles, 50, decay=False)
    city = CityMap()
    city.tiles[:] = tiles
    r = try_place(city, 52, 52, TOOL_CLEAR, SimState(treasury=100))
    rubble = [city.tiles[city.offset(50 + dx, 50 + dy)] for dy in range(3) for dx in range(3)]
    ok = r.ok and rubble == [ID_RUBBLE] * 9
    lines.append(
        f"Clear N×N after palace merge: {'ok' if ok else 'FAIL'} "
        f"{r.message} ids={[hex(v) for v in rubble]}"
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

    from app.calendar import selftest as calendar_selftest

    lines.extend(calendar_selftest())

    tiles = _blank_tiles()
    state = SimState(phase=0xD6, year_raw=-187, month=0)
    result = city_sim_phase(tiles, state)
    ok = (
        result.month_wrapped
        and state.phase == 0
        and state.month == 1
        and state.year_raw == -187
        and state.date_label == "187 BC February"
    )
    lines.append(
        f"Space wrap 0xD6→month++: {'ok' if ok else 'FAIL'} "
        f"phase={state.phase:#x} {state.date_label}"
    )

    tiles = _blank_tiles()
    state = SimState(phase=0xD6, year_raw=-187, month=11)
    city_sim_phase(tiles, state)
    ok = state.month == 0 and state.year_raw == -186 and state.date_label == "186 BC January"
    lines.append(
        f"Space wrap Dec→year++: {'ok' if ok else 'FAIL'} {state.date_label}"
    )

    tiles = _blank_tiles()
    state = SimState(phase=0xC0, year_raw=-300, month=5)
    result = city_sim_until_wrap(tiles, state)
    ok = (
        result.month_wrapped
        and state.phase == 0
        and state.month == 6
        and state.date_label == "300 BC July"
    )
    lines.append(
        f"M remaining slots wrap: {'ok' if ok else 'FAIL'} "
        f"phase={state.phase:#x} {state.date_label}"
    )

    tiles = _blank_tiles()
    state = SimState(phase=1, year_raw=-300, month=0, city_only=1)
    result = city_sim_until_wrap(tiles, state)
    ok = (
        result.month_wrapped
        and state.phase == 0
        and state.month == 1
        and state.year_raw == -300
        and state.date_label == "300 BC February"
    )
    lines.append(
        f"M City Only 0x1→Feb: {'ok' if ok else 'FAIL'} "
        f"phase={state.phase:#x} {state.date_label}"
    )

    tiles = _blank_tiles()
    state = SimState(phase=1, year_raw=-300, month=0, city_only=1)
    result = city_sim_clock_pulse(tiles, state)
    ok = (
        not result.month_wrapped
        and state.phase == 2
        and state.month == 0
        and state.date_label == "300 BC January"
    )
    lines.append(
        f"clock pulse housing 0x1: {'ok' if ok else 'FAIL'} "
        f"phase={state.phase:#x} {state.date_label}"
    )

    tiles = _blank_tiles()
    state = SimState(phase=0, year_raw=-300, month=0)
    result = city_sim_clock_pulse(tiles, state)
    ok = not result.month_wrapped and state.phase == 1 and state.month == 0
    lines.append(
        f"clock pulse phase 0→1: {'ok' if ok else 'FAIL'} phase={state.phase:#x}"
    )

    tiles = _blank_tiles()
    tiles[_off(4, 4) + 13] = 0xFF
    state = SimState(phase=0x51, year_raw=-300, month=0)
    result = city_sim_clock_pulse(tiles, state)
    ok = (
        not result.month_wrapped
        and state.phase == 0x52
        and state.month == 0
        and tiles[_off(4, 4) + 13] == 0
    )
    lines.append(
        f"clock 0x51 wipes +13, no month skip: {'ok' if ok else 'FAIL'} "
        f"phase={state.phase:#x} +13={tiles[_off(4, 4) + 13]}"
    )

    from app.city_paint import (
        EDU_GRAMMATICUS_BIT,
        EDU_RHETOR_BIT,
        GRAMMATICUS_SPLASH_R,
        paint_plus12_amenities,
        paint_plus13_buildings,
        paint_plus13_water,
    )

    tiles = _blank_tiles()
    off = _off(10, 10)
    tiles[off] = 0xBE
    tiles[off + 1] = 0x80
    tiles[off + 10] = 3
    paint_plus13_buildings(tiles, 10, 1)
    ring = tiles[_off(10, 10) + 13] & 4
    house = _off(12, 10)
    tiles[house] = 0xDD
    tiles[_off(12, 10) + 13] = tiles[_off(12, 10) + 13]  # fountain sees ring
    paint_plus13_water(tiles, 10, 3)
    splash = tiles[_off(14, 10) + 13] & 1
    ok = bool(ring) and bool(splash)
    lines.append(
        f"reservoir +13 0x04 / fountain +13 0x01: {'ok' if ok else 'FAIL'} "
        f"ring={ring:#x} splash={splash:#x}"
    )

    tiles = _blank_tiles()
    goff = _off(40, 20)
    tiles[goff] = 0xF3
    tiles[goff + 5] = 0
    hoff = _off(42, 20)
    tiles[hoff] = 0x83
    paint_plus12_amenities(tiles, 20, 1)
    gram = tiles[hoff + 13] & EDU_GRAMMATICUS_BIT
    far = _off(40 + GRAMMATICUS_SPLASH_R + 2, 20)
    tiles[far] = 0x83
    paint_plus12_amenities(tiles, 20, 1)
    far_bit = tiles[far + 13] & EDU_GRAMMATICUS_BIT
    ok = gram == EDU_GRAMMATICUS_BIT and far_bit == 0
    lines.append(
        f"grammaticus +13 0x10 r=6 extra=1: {'ok' if ok else 'FAIL'} "
        f"adj={gram:#x} far={far_bit:#x}"
    )

    tiles = _blank_tiles()
    roff = _off(30, 30)
    tiles[roff] = 0xF4
    tiles[_off(32, 32)] = 0x83
    paint_plus12_amenities(tiles, 30, 1)
    rhe = tiles[_off(32, 32) + 13] & EDU_RHETOR_BIT
    ok = rhe == EDU_RHETOR_BIT
    lines.append(
        f"rhetor +13 0x20 r=8 extra=2: {'ok' if ok else 'FAIL'} bit={rhe:#x}"
    )

    tiles = _blank_tiles()
    tiles[_off(10, 5)] = 0xF3
    tiles[_off(12, 5)] = 0x83
    tiles[_off(12, 5) + 13] = EDU_GRAMMATICUS_BIT
    wipe_state = SimState(phase=0x51, year_raw=-300, month=0)
    city_sim_clock_pulse(tiles, wipe_state)
    wiped = tiles[_off(12, 5) + 13]
    wipe_state.phase = 0x66
    city_sim_clock_pulse(tiles, wipe_state)
    restored = tiles[_off(12, 5) + 13] & EDU_GRAMMATICUS_BIT
    ok = wiped == 0 and restored == EDU_GRAMMATICUS_BIT
    lines.append(
        f"0x51 wipe + 0x66 education restore: {'ok' if ok else 'FAIL'} "
        f"wiped={wiped:#x} rest={restored:#x}"
    )

    tiles = _blank_tiles()
    tiles[_off(10, 5)] = 0xE5
    tiles[_off(12, 5)] = 0x83
    paint_plus12_amenities(tiles, 5, 1)
    near = tiles[_off(12, 5) + 12] & 0x03
    ok = near == 3
    lines.append(
        f"theater +12 bits 0-1 r=5 extra=1: {'ok' if ok else 'FAIL'} +12={near}"
    )
    wipe_state = SimState(phase=0x54, year_raw=-300, month=0)
    city_sim_clock_pulse(tiles, wipe_state)
    wiped = tiles[_off(12, 5) + 12]
    wipe_state.phase = 0x66
    city_sim_clock_pulse(tiles, wipe_state)
    restored = tiles[_off(12, 5) + 12] & 0x03
    ok = wiped == 0 and restored == 3
    lines.append(
        f"0x54 wipe + 0x66 entertainment restore: {'ok' if ok else 'FAIL'} "
        f"wiped={wiped:#x} rest={restored:#x}"
    )

    tiles = _blank_tiles()
    tiles[_off(10, 8)] = 0xBE
    tiles[_off(10, 8) + 10] = 3
    tiles[_off(10, 8) + 13] = 4
    tiles[_off(12, 8)] = 0xDF
    tiles[_off(12, 8) + 5] = 0
    tiles[_off(12, 8) + 13] = 4
    tiles[_off(14, 8)] = 0x83
    from app.city_paint import BATH_SPLASH_BIT, paint_plus13_water, paint_plus14_security

    paint_plus13_water(tiles, 8, 1)
    bath = tiles[_off(14, 8) + 13] & BATH_SPLASH_BIT
    ok = bath == BATH_SPLASH_BIT
    lines.append(
        f"baths +13 0x08 r=5 extra=1: {'ok' if ok else 'FAIL'} bit={bath:#x}"
    )
    wipe_state = SimState(
        phase=0x51,
        year_raw=-300,
        month=0,
        plebs_ready=42,
        labor_assigned=[20, 12, 4, 4, 0, 0, 0],
    )
    city_sim_clock_pulse(tiles, wipe_state)
    wiped = tiles[_off(14, 8) + 13]
    tiles[_off(10, 8) + 13] = 4
    tiles[_off(12, 8) + 13] = 4
    wipe_state.phase = 0x6E
    city_sim_clock_pulse(tiles, wipe_state)
    restored = tiles[_off(14, 8) + 13] & BATH_SPLASH_BIT
    ok = wiped == 0 and restored == BATH_SPLASH_BIT
    lines.append(
        f"0x51 wipe + 0x6E baths restore: {'ok' if ok else 'FAIL'} "
        f"wiped={wiped:#x} rest={restored:#x}"
    )

    tiles = _blank_tiles()
    tiles[_off(20, 10)] = 0xE3
    tiles[_off(21, 10)] = 0x83
    paint_plus14_security(tiles, 10, 1)
    sec10 = tiles[_off(21, 10) + 10] & 0x30
    ok = sec10 == 0x30
    lines.append(
        f"prefecture +10 0x30 r=2: {'ok' if ok else 'FAIL'} +10={sec10:#x}"
    )

    tiles = _blank_tiles()
    # Fountain water + garden LV: tent −2 is offset by garden +2 r=2.
    foff = _off(8, 8)
    tiles[foff] = 0xDD
    tiles[foff + 1] = 0x01
    tiles[foff + 13] = 4
    goff = _off(9, 8)
    tiles[goff] = 0x78
    tiles[goff + 1] = 0x01
    toff = _off(8, 9)
    tiles[toff] = 0x82
    tiles[toff + 1] = 0x01
    tiles[toff + 13] = 0x01
    from app.city_paint import cap_housing_plus15, paint_land_value

    paint_land_value(tiles, 8, 2)
    cap_housing_plus15(tiles, 8, 2, population=2)
    u, d, m = evolve_row(tiles, 9, decay=False)
    ok = tiles[toff] >= 0x83 and u >= 1
    lines.append(
        f"tent+water+garden evolve: {'ok' if ok else 'FAIL'} "
        f"id={tiles[toff]:#x} +15={tiles[toff + 15]} u={u}"
    )

    tiles = _blank_tiles()
    toff = _off(8, 9)
    tiles[toff] = 0x82
    tiles[toff + 1] = 0x01
    tiles[toff + 13] = 0x01
    from app.city_paint import cap_housing_plus15, housing_cap_detail

    cap, gate = housing_cap_detail(tiles, 8, 9, population=2)
    cap_housing_plus15(tiles, 8, 2, population=2)
    ids = []
    for _ in range(4):
        evolve_row(tiles, 9, decay=False, population=2)
        ids.append(tiles[toff])
    ok = cap == 6 and tiles[toff] >= 0x85 and tiles[toff + 15] >= 6
    lines.append(
        f"watered tent climbs huts (no market): {'ok' if ok else 'FAIL'} "
        f"ids={[hex(i) for i in ids]} +15={tiles[toff + 15]} cap={cap} {gate}"
    )

    tiles = _blank_tiles()
    foff = _off(8, 8)
    tiles[foff] = 0xDD
    tiles[foff + 1] = 0x01
    tiles[foff + 13] = 4
    for dx, dy in ((0, 1), (1, 1), (1, 0)):
        h = _off(8 + dx, 8 + dy)
        tiles[h] = 0x83
        tiles[h + 1] = 0x01
        tiles[h + 13] = 0x01
    from app.city_paint import paint_land_value

    paint_land_value(tiles, 8, 2)
    cap_housing_plus15(tiles, 8, 2, population=12)
    lv_grid = [tiles[_off(8 + dx, 8 + dy) + 15] for dy in range(1, 2) for dx in range(2)]
    evolve_row(tiles, 9, decay=False, population=12)
    hid_grid = [tiles[_off(8 + dx, 9) ] for dx in range(2)]
    ok = all(v >= 6 for v in lv_grid) and all(h >= 0x84 for h in hid_grid)
    lines.append(
        f"dense huts not pinned at +15=2: {'ok' if ok else 'FAIL'} "
        f"+15={lv_grid} ids={[hex(h) for h in hid_grid]}"
    )

    tiles = _blank_tiles()
    foff = _off(8, 8)
    tiles[foff] = 0xDD
    tiles[foff + 1] = 0x01
    toff = _off(8, 9)
    tiles[toff] = 0x82
    tiles[toff + 1] = 0x01
    paint_plus13_water(tiles, 8, 2)
    splash = tiles[toff + 13] & 1
    ok = splash == 0
    lines.append(
        f"dry fountain no +13 splash: {'ok' if ok else 'FAIL'} "
        f"+13={tiles[toff + 13]:#x}"
    )

    from app.walker_tick import emit_walkers
    from app.walkers import Walker, live_walkers

    tiles = _blank_tiles()
    poff = _off(20, 20)
    tiles[poff] = 0xE3
    tiles[poff + 1] = 0x01
    roff = _off(20, 19)
    tiles[roff] = 0x52
    tiles[roff + 1] = 0x20
    walkers: list[Walker] = []
    nsp = emit_walkers(tiles, walkers, 20, 1, population=4)
    live = live_walkers(walkers)
    ok = nsp >= 1 and len(live) >= 1 and live[0].type == 5
    lines.append(
        f"prefecture emit type 5: {'ok' if ok else 'FAIL'} "
        f"n={nsp} live={len(live)} type={live[0].type if live else 0}"
    )

    tiles = _blank_tiles()
    boff = _off(20, 20)
    tiles[boff] = 0xE4
    tiles[boff + 1] = 0x01
    tiles[_off(20, 19)] = 0x52
    tiles[_off(20, 19) + 1] = 0x20
    walkers = []
    nsp = emit_walkers(tiles, walkers, 20, 1, population=4)
    live = live_walkers(walkers)
    ok = nsp >= 1 and len(live) >= 1 and live[0].type == 4
    lines.append(
        f"barracks emit type 4: {'ok' if ok else 'FAIL'} "
        f"n={nsp} live={len(live)} type={live[0].type if live else 0}"
    )

    tiles = _blank_tiles()
    for dy in range(2):
        for dx in range(2):
            moff = _off(20 + dx, 20 + dy)
            tiles[moff] = 0xFC
            tiles[moff + 1] = 0x01
            tiles[moff + 5] = dy * 2 + dx
    tiles[_off(20, 22)] = 0x52
    tiles[_off(20, 22) + 1] = 0x20
    tiles[_off(21, 22)] = 0x52
    tiles[_off(21, 22) + 1] = 0x20
    walkers = []
    nsp = emit_walkers(tiles, walkers, 20, 3, population=4, kinds="market")
    live = live_walkers(walkers)
    sid = live[0].sprite_id if live else -1
    ok = (
        nsp >= 1
        and len(live) >= 1
        and live[0].type == 2
        and live[0].next_state == 4
        and 0x1B <= sid < 0x1B + 27
    )
    lines.append(
        f"market emit type 2: {'ok' if ok else 'FAIL'} "
        f"n={nsp} live={len(live)} type={live[0].type if live else 0} "
        f"next={live[0].next_state if live else -1} sprite={sid}"
    )

    tiles = _blank_tiles()
    for dy in range(2):
        for dx in range(2):
            foff = _off(20 + dx, 20 + dy)
            tiles[foff] = 0xAF
            tiles[foff + 1] = 0x01
            tiles[foff + 5] = dy * 2 + dx
    tiles[_off(20, 19)] = 0x52
    tiles[_off(20, 19) + 1] = 0x20
    walkers = []
    nsp = emit_walkers(
        tiles,
        walkers,
        20,
        3,
        population=4,
        kinds="forum",
        shutoff=frozenset({"forum"}),
    )
    wait = tiles[_off(20, 20) + 6] & 0x0F
    ok = nsp == 0 and wait > 0
    lines.append(
        f"understaffed forum emit off: {'ok' if ok else 'FAIL'} "
        f"n={nsp} wait={wait}"
    )

    tiles = _blank_tiles()
    toff = _off(8, 9)
    tiles[toff] = 0x82
    tiles[toff + 1] = 0x01
    foff = _off(8, 8)
    tiles[foff] = 0xDD
    tiles[foff + 1] = 0x01
    tiles[_off(9, 9)] = 0x52
    tiles[_off(9, 9) + 1] = 0x20
    tiles[_off(12, 8)] = 0xE4
    tiles[_off(12, 8) + 1] = 0x01
    tiles[_off(12, 7)] = 0x52
    tiles[_off(12, 7) + 1] = 0x20
    walkers = []
    state = SimState(phase=1, year_raw=-300, month=0, city_only=1)
    city_sim_until_wrap(tiles, state, walkers)
    water = tiles[toff + 13] & 0x03
    lv = tiles[toff + 15]
    city_sim_until_wrap(tiles, state, walkers)
    live = live_walkers(walkers)
    # Dry fountain is silent (+13). Evolve + barracks walker are the check.
    ok = tiles[toff] >= 0x83 and len(live) >= 1
    lines.append(
        f"month-cycle tent evolve + walker: {'ok' if ok else 'FAIL'} "
        f"id={tiles[toff]:#x} +15={lv}->{tiles[toff + 15]} +13={tiles[toff + 13]:#x} "
        f"walkers={len(live)} water={water:#x} {state.date_label}"
    )

    tiles = _blank_tiles()
    toff = _off(8, 9)
    tiles[toff] = 0x82
    tiles[toff + 1] = 0x01
    tiles[_off(9, 9)] = 0x52
    tiles[_off(9, 9) + 1] = 0x20
    roff = _off(10, 8)
    tiles[roff] = 0xBE
    tiles[roff + 1] = 0x80
    tiles[roff + 10] = 3
    foff = _off(8, 8)
    tiles[foff] = 0xDD
    tiles[foff + 1] = 0x01
    state = SimState(phase=1, year_raw=-300, month=0, city_only=1)
    for _ in range(4):
        city_sim_until_wrap(tiles, state)
    reason = house_stay_reason(tiles, 8, 9, population=state.population)
    ok = (
        tiles[toff] >= 0x85
        and tiles[toff] < 0x8E
        and "no-food" in reason
        and "need-insula" in reason
    )
    lines.append(
        f"4 months water-only stops before insula: {'ok' if ok else 'FAIL'} "
        f"id={tiles[toff]:#x} +15={tiles[toff + 15]} {reason}"
    )

    from app.city_paint import (
        factory_produce,
        factory_type_name,
        seed_city_only_good,
        GOODS_RAW,
        GOODS_SUPPLIED,
        CITY_ONLY_LABOR,
    )
    from app.walker_tick import pack_home_plus9

    fac = _blank_tiles()
    foff = _off(10, 10)
    fac[foff] = 0xFA
    fac[foff + 9] = 0x03
    fac[foff + 19] = 0
    zero = factory_produce(fac, 10, 10)
    ok = zero == 0 and (fac[foff + 9] & 0xF0) == 0
    lines.append(
        f"41b33 no raw → stock 0: {'ok' if ok else 'FAIL'} "
        f"stock={zero} +9={fac[foff + 9]:#04x}"
    )

    sandbox = bytearray(768)
    seed_city_only_good(sandbox, 0)
    fac[foff + 9] = 0
    play = factory_produce(
        fac, 10, 10, goods=sandbox, labor=CITY_ONLY_LABOR, city_only=True
    )
    ok = play > 0 and (fac[foff + 9] & 0xF0) != 0
    lines.append(
        f"City Only seeded workshop → stock {play}: {'ok' if ok else 'FAIL'} "
        f"+9={fac[foff + 9]:#04x} type={factory_type_name(0)}"
    )

    d_like = bytearray(768)
    struct.pack_into("<i", d_like, GOODS_SUPPLIED, 100)
    fac[foff + 9] = 0x03
    d_stock = factory_produce(fac, 10, 10, goods=d_like, labor=4, province_links=3)
    ok = d_stock == 0 and (fac[foff + 9] & 0xF0) == 0
    lines.append(
        f"D.SAV pct-only +28=0 → stock 0: {'ok' if ok else 'FAIL'} stock={d_stock}"
    )

    live = bytearray(768)
    struct.pack_into("<i", live, GOODS_SUPPLIED, 100)
    struct.pack_into("<i", live, GOODS_RAW, 3000)
    fac[foff + 9] = 0x0F  # stage 3 + market 0xC
    live_stock = factory_produce(
        fac, 10, 10, goods=live, labor=4, province_links=3
    )
    ok = live_stock == 7 and (fac[foff + 9] & 0xF0) == 0x70
    lines.append(
        f"career raw+supplied → stock 7: {'ok' if ok else 'FAIL'} "
        f"stock={live_stock} +9={fac[foff + 9]:#04x}"
    )

    packed = _blank_tiles()
    poff = _off(4, 4)
    packed[poff] = 0xFA
    packed[poff + 9] = 0x70  # stock 7
    pack_home_plus9(packed, poff, 9, 9)
    ok = (packed[poff + 9] & 0xF0) == 0x70 and (packed[poff + 9] & 0x0F) == 0x0F
    lines.append(
        f"worker pack keeps stock hi: {'ok' if ok else 'FAIL'} "
        f"+9={packed[poff + 9]:#04x}"
    )

    from app.walker_tick import selftest as walker_selftest
    from app.walker_quotes import selftest as quote_selftest

    lines.extend(walker_selftest())
    lines.extend(quote_selftest())

    from app.sim_log import LOG_PATH, last_line

    ok = LOG_PATH.is_file() and bool(last_line())
    lines.append(
        f"sim log {LOG_PATH.as_posix()}: {'ok' if ok else 'FAIL'} "
        f"tail={last_line()[-80:]!r}"
    )

    ok = sim_tick_interval_ms(state.speed_scalar) == 200
    lines.append(
        f"default speed_scalar 70 → 200ms: {'ok' if ok else 'FAIL'} "
        f"paused={state.paused}"
    )

    from app.sim import on_month_step, sim_tick_due

    gate = SimState()
    ok = sim_tick_due(gate, 50) == 0
    gate.tick_acc = 0
    ok = ok and sim_tick_due(gate, 200) == 1
    gate.paused = True
    gate.tick_acc = 0
    ok = ok and sim_tick_due(gate, 200) == 0
    gate.paused = False
    gate.catchup = 1
    gate.tick_acc = 0
    ok = ok and sim_tick_due(gate, 200) == 4
    lines.append(f"sim_tick_due pause/play/fast: {'ok' if ok else 'FAIL'}")

    tiles = _blank_tiles()
    state = SimState(phase=1, year_raw=-300, month=0, city_only=1)
    class _Map:
        def __init__(self, t: bytearray) -> None:
            self.tiles = t
    n = on_month_step(_Map(tiles), [], state)
    ok = n.phase.month_wrapped and state.date_label == "300 BC February"
    lines.append(
        f"M on_month_step City Only: {'ok' if ok else 'FAIL'} {state.date_label}"
    )

    from app.forum import monthly_pop_tax_raw, ytd_tax_dn

    tiles = _blank_tiles()
    wrap = SimState(
        phase=PHASE_MAX,
        year_raw=-300,
        month=0,
        city_only=1,
        treasury=12000,
        welfare=8,
        tax_rate=5,
        tax_wealth=100,
    )
    city_sim_phase(tiles, wrap)
    # empty map: wealth refresh → 0; operating still debits.
    ok = wrap.month == 1 and wrap.treasury == 11992 and wrap.tax_months == 1
    lines.append(
        f"WRAP empty City Only -op 8: {'ok' if ok else 'FAIL'} "
        f"treas={wrap.treasury} {wrap.date_label}"
    )
    tiles = _blank_tiles()
    toff = _off(10, 10)
    tiles[toff] = 0x9B  # grand domus wealth 100
    tiles[toff + 10] = 0x0C
    rich = SimState(
        phase=PHASE_MAX,
        year_raw=-300,
        month=0,
        city_only=1,
        treasury=12000,
        welfare=8,
        tax_rate=5,
        tax_wealth=0,
    )
    city_sim_phase(tiles, rich)
    pop5 = ytd_tax_dn(monthly_pop_tax_raw(100, 5))
    hi = SimState(
        phase=PHASE_MAX,
        year_raw=-300,
        month=0,
        city_only=1,
        treasury=12000,
        welfare=8,
        tax_rate=25,
        tax_wealth=0,
    )
    tiles2 = bytearray(tiles)
    city_sim_phase(tiles2, hi)
    pop25 = ytd_tax_dn(monthly_pop_tax_raw(100, 25))
    ok = (
        rich.treasury == 12000 + pop5 - 8
        and hi.treasury == 12000 + pop25 - 8
        and hi.treasury > rich.treasury
    )
    lines.append(
        f"raise tax WRAP Dn: {'ok' if ok else 'FAIL'} "
        f"5%={rich.treasury} 25%={hi.treasury}"
    )

    tiles = _blank_tiles()
    hoff = _off(10, 10)
    tiles[hoff] = 0x82
    tiles[hoff + 1] = 0x01
    tile_ignite(tiles, hoff)
    dec, col, ign = fire_tick_rows(tiles, 10, 1)
    ok = dec == 1 and tiles[hoff + 16] == 9 and tiles[hoff + 3] & DRAW_FIRE
    lines.append(
        f"fire tick --+16: {'ok' if ok else 'FAIL'} "
        f"dec={dec} +16={tiles[hoff + 16]} bit7={tiles[hoff + 3] & DRAW_FIRE:#x}"
    )

    tiles = _blank_tiles()
    hoff = _off(10, 10)
    tiles[hoff] = 0x89
    tiles[hoff + 1] = 0x01
    tiles[hoff + 3] = DRAW_FIRE
    tiles[hoff + 16] = 1
    dec, col, ign = fire_tick_rows(tiles, 10, 1)
    ok = (
        col >= 1
        and tiles[hoff] == ID_RUBBLE
        and tiles[hoff + 3] & DRAW_FIRE
    )
    lines.append(
        f"fire collapse rubble 0x05: {'ok' if ok else 'FAIL'} "
        f"col={col} id={tiles[hoff]:#x} bit7={tiles[hoff + 3] & DRAW_FIRE:#x}"
    )

    tiles = _blank_tiles()
    aoff = _off(10, 10)
    boff = _off(10, 9)  # (10+10)&3 → facing 0 north
    tiles[aoff] = 0x82
    tiles[aoff + 1] = 0x01
    tiles[aoff + 3] = DRAW_FIRE
    tiles[aoff + 16] = 8
    tiles[boff] = 0x83
    tiles[boff + 1] = 0x01
    fire_tick_rows(tiles, 10, 1)
    ok = bool(tiles[boff + 3] & DRAW_FIRE) and tiles[boff + 16] == FIRE_TIMER_IGNITE
    lines.append(
        f"fire spread neighbor house: {'ok' if ok else 'FAIL'} "
        f"bit7={tiles[boff + 3] & DRAW_FIRE:#x} +16={tiles[boff + 16]}"
    )

    tiles = _blank_tiles()
    hoff = _off(10, 10)
    tiles[hoff] = 0x82
    tiles[hoff + 1] = 0x01
    st = SimState(phase=0x9E, year_raw=-300, month=0, city_only=1)
    risks = []
    ignited = False
    for step in range(4):
        fire_tick_rows(tiles, 10, 1, st)
        risks.append(tiles[hoff + 11] & 0x30)
        if tiles[hoff + 3] & DRAW_FIRE:
            ignited = True
            break
    ok = ignited and tiles[hoff + 16] == FIRE_TIMER_IGNITE
    lines.append(
        f"uncovered house ignites at +11 0x30: {'ok' if ok else 'FAIL'} "
        f"risks={[hex(r) for r in risks]} +16={tiles[hoff + 16]}"
    )

    tiles = _blank_tiles()
    hoff = _off(10, 10)
    tiles[hoff] = 0x82
    tiles[hoff + 1] = 0x01
    tiles[hoff + 10] = 0x30
    tiles[hoff + 11] = 0x30
    fire_tick_rows(tiles, 10, 1)
    ok = (tiles[hoff + 11] & 0x30) == 0x20 and not (tiles[hoff + 3] & DRAW_FIRE)
    lines.append(
        f"prefect +10 0x30 lowers fire risk: {'ok' if ok else 'FAIL'} "
        f"+11={tiles[hoff + 11] & 0x30:#x}"
    )

    from app.messages import selftest as message_selftest

    lines.extend(message_selftest())
    return lines
