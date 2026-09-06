"""start_city_assignment / init_new_city — City Only only (milestone 1).

EXE: start_city_assignment 0x1049B → init_new_city 0x10565 →
city_map_generate 0x65809. Career / apply_regions_map 0x706C3 / actors26
are not this module. Ghidra HTTP was down; generate was read with Capstone
on ghidra_work/c2_x.bin (tools/_city_map_generate_disasm.py).

    python -m app --new --city-only [--skill 0..4]
"""

from __future__ import annotations

import struct
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.city_map import (
    FLAG_RIVER,
    MAP_BYTES,
    MAP_H,
    MAP_W,
    ROW_STRIDE,
    SAV_HISTORY_BYTES,
    TILE_STRIDE,
    CityMap,
)
from app.city_sim import SimState
from app.config import find_file
from app.walkers import Walker

# C2.ENG [42] / [43]: Novice … Impossible!  chunk 16 = 0…4
SKILL_NAMES: tuple[str, ...] = (
    "Novice",
    "Easy",
    "Normal",
    "Hard",
    "Impossible!",
)

# C2MODEL[5:10] / EXE 0x96F2F — new assignment, [0x102590]==0 so no deduct.
TREASURY_BY_SKILL: tuple[int, ...] = (20000, 15000, 12000, 7000, 5000)

# C2MODEL[0:5] → city_ratings_seed 0x58BAE / chunk 341
RATINGS_SEED_BY_SKILL: tuple[int, ...] = (20, 15, 10, 5, 2)

# city_map_generate 0x65809: EAX lane order (1–17, not 0/18/19).
_CLEAR_LANES: tuple[int, ...] = (
    2, 1, 3, 9, 0x10, 5, 6, 7, 8, 0xF, 0xD, 0xE, 0xA, 0xB, 0xC, 4, 0x11
)

# city_map_trace_feature: 0x3C0 steps; start x = 0x18 + (rng&0x1F).
_TRACE_STEPS = 0x3C0
_TRACE_X0 = 0x18
DIR_N, DIR_E, DIR_S, DIR_W = 0, 2, 4, 6
# +1 bit 0x08: 0x65B3E sets it on corner matches (ghidra_water.md +1 & 0x18).
FLAG_RIVER_BANK = 0x08
# CITYFIXT water family after bank remap (D.SAV / Achea river +0).
ID_RIVER_LO = 0x1E
ID_RIVER_HI = 0x51
ID_RUBBLE = 0x05

# 0x94AA7 — 6 × 12 B (edx=6). Neigh N,NE,E,SE,S,SW,W,NW: 0=no 1=yes 2=any.
# +8 base id, +9 walk dir that keeps the primary, +10 variant period, +11 counter.
_BANK_TABLE: tuple[bytes, ...] = (
    bytes((1, 2, 0, 2, 1, 2, 0, 2, 0x26, DIR_S, 4, 0)),
    bytes((0, 2, 1, 2, 0, 2, 1, 2, 0x1E, DIR_W, 4, 0)),
    bytes((1, 2, 1, 2, 0, 2, 0, 2, 0x36, DIR_S, 4, 0)),
    bytes((0, 2, 1, 2, 1, 2, 0, 2, 0x46, DIR_W, 4, 0)),
    bytes((0, 2, 0, 2, 1, 2, 1, 2, 0x3A, DIR_N, 4, 0)),
    bytes((1, 2, 0, 2, 0, 2, 1, 2, 0x4A, DIR_E, 4, 0)),
)
_BANK_REMAP = {
    0x26: 0x2A,
    0x1E: 0x22,
    0x36: 0x2E,
    0x46: 0x42,
    0x3A: 0x32,
    0x4A: 0x3E,
}
_NEIGH8 = (
    (0, -1),
    (1, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
)

SKILL_DEFAULT = 2  # Normal — D.SAV / Achea
CHUNK_SKILL = 16
CHUNK_PID = 223
CHUNK_TREASURY = 28
CHUNK_CITY_ONLY = 406


@dataclass
class ExeRng:
    """rand 0x28003 (31-step LFSR at [0xC4598]) + rng_clock 0x2804C.

    clock() = rand() & 0x7F → [0xC2070]. Seed 0 stays 0 forever; avoid it.
    Host seed is time, not the title-screen clock — maps will not replay a
    specific EXE new-game.
    """

    state: int = 1
    value: int = 0

    @classmethod
    def from_seed(cls, seed: int | None = None) -> ExeRng:
        if seed is None:
            seed = time.time_ns() & 0x7FFFFFFF
        if seed == 0:
            seed = 1
        return cls(state=seed & 0xFFFFFFFF)

    def rand(self) -> int:
        state = self.state
        for _ in range(31):
            bit = ((state >> 4) & 1) ^ (state & 1)
            state >>= 1
            if bit:
                state |= 0x40000000
        self.state = state & 0xFFFFFFFF
        return self.state & 0x7FFF

    def clock(self) -> int:
        self.value = self.rand() & 0x7F
        return self.value


@dataclass
class NewCity:
    city: CityMap
    walkers: list[Walker]
    sim: SimState
    skill: int
    treasury: int
    notes: list[str] = field(default_factory=list)

    @property
    def skill_name(self) -> str:
        return SKILL_NAMES[self.skill]


def skill_name(skill: int) -> str:
    if 0 <= skill < len(SKILL_NAMES):
        return SKILL_NAMES[skill]
    return f"?{skill}"


def treasury_for_skill(skill: int, game: Path | None = None) -> int:
    """C2MODEL[5:10] if the DAT is on disk; else the EXE prefix table."""
    if not 0 <= skill <= 4:
        raise ValueError(f"skill must be 0..4, got {skill}")
    if game is not None:
        path = find_file(game, "C2MODEL.DAT")
        if path is not None:
            data = path.read_bytes()
            if len(data) >= 10 * 4:
                vals = struct.unpack_from("<5i", data, 5 * 4)
                return int(vals[skill])
    return TREASURY_BY_SKILL[skill]


def ratings_seed_for_skill(skill: int, game: Path | None = None) -> int:
    if not 0 <= skill <= 4:
        raise ValueError(f"skill must be 0..4, got {skill}")
    if game is not None:
        path = find_file(game, "C2MODEL.DAT")
        if path is not None:
            data = path.read_bytes()
            if len(data) >= 5 * 4:
                vals = struct.unpack_from("<5i", data, 0)
                return int(vals[skill])
    return RATINGS_SEED_BY_SKILL[skill]


def _off(x: int, y: int) -> int:
    return y * ROW_STRIDE + x * TILE_STRIDE


def _in_map(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def city_map_clear_byte8(tiles: bytearray, lane: int) -> None:
    """city_map_clear_byte8 0x6E188 — zero one 20-byte lane on 80×80."""
    if not 0 <= lane < TILE_STRIDE:
        return
    for i in range(0, MAP_BYTES, TILE_STRIDE):
        tiles[i + lane] = 0


def city_map_fill_rand_terrain(tiles: bytearray, rng: ExeRng) -> None:
    """city_map_fill_rand_terrain 0x65AFA — byte0 = (rng & 0xF) + 8."""
    for i in range(0, MAP_BYTES, TILE_STRIDE):
        tiles[i] = (rng.clock() & 0xF) + 8


def _river_neighbor_count(tiles: bytearray, x: int, y: int) -> int:
    """Stand-in for 0x6B0D1(eax=0x10): how many 8-neighbors already have +1 & 0x10."""
    n = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            nx, ny = x + dx, y + dy
            if _in_map(nx, ny) and tiles[_off(nx, ny) + 1] & FLAG_RIVER:
                n += 1
    return n


def _river_edge8(tiles: bytearray, x: int, y: int) -> list[int]:
    """0x6ADB0(eax=0x10): 8 neighbors; off-map counts as water."""
    out: list[int] = []
    for dx, dy in _NEIGH8:
        nx, ny = x + dx, y + dy
        if not _in_map(nx, ny):
            out.append(1)
        else:
            out.append(1 if tiles[_off(nx, ny) + 1] & FLAG_RIVER else 0)
    return out


def _bank_match(
    neigh: list[int], table: list[bytearray]
) -> tuple[int, int, int, int]:
    """0x6C826: first of 6 records. Returns (1-based index, base, keep_dir, variant)."""
    for i, rec in enumerate(table):
        matched = True
        for j in range(8):
            pat = rec[j]
            if pat == 2:
                continue
            has = neigh[j]
            if pat != 0:
                if has:
                    continue
                matched = False
                break
            if has:
                matched = False
                break
        if not matched:
            continue
        rec[11] += 1
        if rec[11] >= rec[10]:
            rec[11] = 0
        return i + 1, rec[8], rec[9], rec[11]
    return 0, 0, 0, 0


def city_map_bank_remap(tiles: bytearray) -> None:
    """city_map_bank_remap 0x65B3E — replace walk dirs with CITYFIXT water ids.

    Table 0x94AA7 + matcher 0x6C826. Only tiles with +1 & 0x10. Grass 8…23
    is left alone. Never writes rubble 0x05.
    """
    table = [bytearray(row) for row in _BANK_TABLE]
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if not (tiles[off + 1] & FLAG_RIVER):
                continue
            walk_dir = tiles[off]
            hit, base, keep_dir, variant = _bank_match(
                _river_edge8(tiles, x, y), table
            )
            if hit == 0:
                continue
            if walk_dir != keep_dir:
                base = _BANK_REMAP.get(base, base)
            tiles[off] = (base + variant) & 0xFF
            if hit > 2:
                tiles[off + 1] |= FLAG_RIVER_BANK


def city_map_trace_feature(tiles: bytearray, rng: ExeRng) -> int:
    """city_map_trace_feature 0x658D1 — drunk-walk river. Return remaining steps.

    Nonzero (including timeout −1) = generate keeps the map. Zero = refill.
    On keep, runs 0x65B3E so byte0 becomes water 0x1E+ instead of dirs 0/2/4/6.
    """
    edi = _TRACE_STEPS
    rng.clock()
    x = _TRACE_X0 + (rng.value & 0x1F)
    y = 0
    off = _off(x, y)
    tiles[off + 1] |= FLAG_RIVER
    tiles[off] = DIR_S
    esi = 0
    ebx = DIR_S
    edx = 0

    while True:
        edi -= 1
        if edi == -1:
            break
        if ebx == 0:
            y -= 1
            off -= ROW_STRIDE
            if _in_map(x, y):
                tiles[off + 1] |= FLAG_RIVER
                tiles[off] = DIR_N
        elif ebx == DIR_E:
            x += 1
            off += TILE_STRIDE
            if _in_map(x, y):
                tiles[off + 1] |= FLAG_RIVER
                tiles[off] = DIR_E
        elif ebx == DIR_S:
            y += 1
            off += ROW_STRIDE
            if _in_map(x, y):
                tiles[off + 1] |= FLAG_RIVER
                tiles[off] = DIR_S
        elif ebx == DIR_W:
            x -= 1
            off -= TILE_STRIDE
            if _in_map(x, y):
                tiles[off + 1] |= FLAG_RIVER
                tiles[off] = DIR_W
        # ebx == 8: skip move (north suppressed / rejected step)

        if x == 0 or y == 0 or x >= 0x4F or y >= 0x4F:
            break

        rng.clock()
        ecx = (rng.value & 3) * 2
        if ecx == 0 and esi < 4:
            ebx = 8
            continue
        if ecx == edx:
            ebx = 8
            continue
        lx, ly = x, y
        if ecx == DIR_N:
            ly -= 1
        elif ecx == DIR_E:
            lx += 1
        elif ecx == DIR_S:
            ly += 1
        elif ecx == DIR_W:
            lx -= 1
        if _in_map(lx, ly) and _river_neighbor_count(tiles, lx, ly) > 2:
            ebx = 8
            continue
        ebx = ecx
        edx = (ecx + 4) % 8
        if ecx == DIR_S:
            esi += 1
        if ecx == DIR_N:
            esi = 0

    if edi != 0:
        city_map_bank_remap(tiles)
    return edi


def city_map_generate(
    tiles: bytearray | CityMap, rng: ExeRng | None = None
) -> ExeRng:
    """city_map_generate 0x65809: clear lanes 1–17, grass, river + 0x65B3E; retry ≤ 6."""
    blob = tiles.tiles if isinstance(tiles, CityMap) else tiles
    if len(blob) != MAP_BYTES:
        raise ValueError(f"city tiles are {len(blob)} bytes, want {MAP_BYTES}")
    if rng is None:
        rng = ExeRng.from_seed()
    for lane in _CLEAR_LANES:
        city_map_clear_byte8(blob, lane)
    city_map_fill_rand_terrain(blob, rng)
    retries = 5
    while True:
        left = city_map_trace_feature(blob, rng)
        if left != 0:
            break
        city_map_fill_rand_terrain(blob, rng)
        retries -= 1
        if retries == -1:
            break
    if isinstance(tiles, CityMap):
        tiles.source = "city_map_generate"
    return rng


def river_tile_count(tiles: bytearray | CityMap) -> int:
    blob = tiles.tiles if isinstance(tiles, CityMap) else tiles
    n = 0
    for i in range(0, MAP_BYTES, TILE_STRIDE):
        if blob[i + 1] & FLAG_RIVER:
            n += 1
    return n


def start_city_assignment(
    *,
    skill: int = SKILL_DEFAULT,
    game: Path | None = None,
    rng: ExeRng | None = None,
) -> NewCity:
    """City Only path of start_city_assignment 0x1049B + init_new_city 0x10565.

    Sets chunk **406**=1, pid **223**=0, year −300, month 0, treasury from
    C2MODEL[skill], empty walkers / HISTORY. Skips apply_regions_map,
    actors26_clear (no pool in the host), climate / goods / economy_recompute.
    """
    if not 0 <= skill <= 4:
        raise ValueError(f"skill must be 0..4 (Novice…Impossible!), got {skill}")

    notes: list[str] = []
    treasury = treasury_for_skill(skill, game)
    ratings = ratings_seed_for_skill(skill, game)
    city = CityMap()
    city_map_generate(city, rng)
    n_river = river_tile_count(city)
    city.source = "city_map_generate"
    notes.append(
        f"city_map_generate: 80x80 grass+river  river={n_river} tiles  "
        f"ids={len(city.id_counts())}"
    )
    notes.append(
        f"init_new_city: City Only  skill={skill} {skill_name(skill)}  "
        f"treasury={treasury}  year=-300  pid=0  chunk406=1"
    )
    notes.append(
        "skipped: apply_regions_map, actors26, climate, province_goods, "
        "economy_recompute (Career / later slices)"
    )

    sim = SimState(
        phase=1,
        row=0,
        year_raw=-300,
        month=0,
        week_gate=0,
        source="new city-only",
        skill=skill,
        city_only=1,
        pid=0,
        treasury=treasury,
        ratings_seed=ratings,
        tax_rate=5,
        history=bytearray(SAV_HISTORY_BYTES),
    )
    return NewCity(
        city=city,
        walkers=[],
        sim=sim,
        skill=skill,
        treasury=treasury,
        notes=notes,
    )


def selftest(*, seed: int = 1) -> list[str]:
    """No window. Grass in 8…23; river ids 0x1E…0x51 + flag 0x10; no rubble."""
    lines: list[str] = []
    city = CityMap()
    city_map_generate(city, ExeRng.from_seed(seed))
    n_river = river_tile_count(city)
    counts = city.id_counts()
    grass = sum(n for tid, n in counts.items() if 8 <= tid <= 23)
    water = 0
    leftover_dir = 0
    rubble_river = 0
    for i in range(0, MAP_BYTES, TILE_STRIDE):
        tid = city.tiles[i]
        if not (city.tiles[i + 1] & FLAG_RIVER):
            continue
        if ID_RIVER_LO <= tid <= ID_RIVER_HI:
            water += 1
        if tid in (DIR_N, DIR_E, DIR_S, DIR_W):
            leftover_dir += 1
        if tid == ID_RUBBLE:
            rubble_river += 1
    zero = counts.get(0, 0)
    lines.append(
        f"seed={seed} river_flags={n_river} grass={grass} "
        f"water_ids={water} leftover_dirs={leftover_dir}"
    )
    if n_river < 20:
        lines.append("FAIL  river flag count < 20")
    else:
        lines.append("ok    river present")
    if grass < 1000:
        lines.append("FAIL  not enough grass (byte0 = (rng&0xF)+8)")
    else:
        lines.append("ok    grass fill")
    if water < 20 or water < n_river - 5:
        lines.append("FAIL  bank remap did not write water ids 0x1E…0x51")
    else:
        lines.append("ok    river ids after 0x65B3E")
    if leftover_dir:
        lines.append(f"FAIL  {leftover_dir} river tiles still walk dirs 0/2/4/6")
    if rubble_river:
        lines.append(f"FAIL  {rubble_river} river tiles are rubble 0x05")
    if counts.get(ID_RUBBLE, 0):
        lines.append("FAIL  rubble 0x05 on the map")
    if zero == MAP_W * MAP_H:
        lines.append("FAIL  80x80 still zeros")
    return lines
