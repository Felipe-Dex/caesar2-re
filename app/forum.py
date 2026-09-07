"""forum_view 0x59A15 stand-in — City Only chrome + PLEBS labor.

Forum is a submode (view_submode=1): no sim tick. Open from a Forum
building (0xAF / 0xB2–0xB4 / 0xB7–0xB9) or INT_CITY view-tab sprite 11.
Career EMPIRE / ROME / PERSONAL stay stubs. Oracle is chunks 286–289
(+ avg 46). Scribe is HISTORY graphs only (no letters).

Labor table = SavChunk 56 (8× assigned/need) @ [0xD2E6C]. Need is
recomputed from the city map; assigned is player-controlled (sliders)
except construction, which is locked to need 20 (EXE labor_init; no +/-).
Ready pool is chunk 52 [0x102A68], set by labor_init 0x563E2 on New Game
only (not population//20, not sav_read). Idle still subtracts those 20.
assigned < need (0x28219) shuts that row: construction → forums,
fire → prefect, water → fountain/bath paint; idle+factory_labor==0
→ factory leftover / no type-6 emit (tile +6 wait gate).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.city_map import MAP_H, MAP_W, TILE_STRIDE
from app.city_paint import (
    count_taxed_factories,
    housing_tax_wealth,
    industry_tax_wealth,
    recount_population,
)
from app.city_sim import SimState

# Host kinds (not the EXE [0x117A5C] numbers — TREASURER took 3 first).
KIND_CHROME = 0
KIND_ORACLE = 1
KIND_TREASURER = 3
KIND_PLEBS = 8
KIND_EXIT = 9
KIND_SCRIBE = 10

# C2.ENG [28]+0…11 in file order → visual 4×3 (forum_qa.md).
_BUTTON_SKIP: tuple[int, ...] = (
    10, 6, 11, 1,
    3, 0, 8, 2,
    7, 4, 5, 9,
)
_BUTTON_KIND: tuple[int, ...] = (
    KIND_ORACLE, 0, 0, KIND_TREASURER,
    KIND_SCRIBE, 0, KIND_PLEBS, 0,
    0, 0, 0, KIND_EXIT,
)
_BUTTON_FALLBACK: tuple[str, ...] = (
    "ORACLE", "CENTURION", "EMPIRE MAP", "TREASURER",
    "SCRIBE", "CLEAR FORUM", "PLEBS", "PERSONAL",
    "MERCHANT", "ROME", "HELP", "EXIT",
)

LABOR_ROWS = 7  # [36]+12…18; +19 Idle is the remainder
LABOR_LABEL_SKIP = tuple(range(12, 20))
LABOR_CONSTRUCTION = 0
LABOR_FIRE = 1
LABOR_ROADS = 2
LABOR_WATER = 3
LABOR_WALLS = 4
# labor_init 0x563E2: construction need always 20; assigned = need (locked).
CREW = 20
# FAQ / 0x444A5: 2 per fountain origin 0xDB–0xDE + 2 per baths 0xDF–0xE2.
WATER_PER_BUILDING = 2
# City Only [0x1025C8] = skill*2+1 (0x346F6). Table 0x9659D {welfare, ready}.
# 0x3FCA0 then runs one 0x56440 tick: table 40 → 42 (A/B/C + D.SAV).
_CITY_ONLY_WELFARE = (7, 7, 8, 9, 9)
READY_TABLE = 40
READY_AFTER_INIT_TICK = 42
LABOR_ASSIGNED_INIT = (20, 12, 4, 4, 0, 0, 0)
# PS.EXE SavChunk[500] @ 0x9ABC0, relocated ptrs. F5 writes these; F4
# maps them back. labor_init 0x563E2 seeds them on New Game only.
PLEBS_READY_VA = 0x102A68  # chunk 52
PLEBS_WELFARE_VA = 0x102A98  # chunk 54
PLEBS_ESTIMATE_VA = 0x102AC4  # chunk 55
PLEBS_TABLE_VA = 0xD2E6C  # chunk 56, 8× {assigned,need} i32; idle @ +0x38
TAX_RATE_VA = 0x102A7C  # chunk 29
IND_TAX_VA = 0x102AA8  # chunk 30
LABOR_INDEX_VA = 0x1025C8  # chunk 416
# 0x56440 score = ((0x965F5 - index/3) * welfare * 100) / ready. 0x965F5 = 7.
WAGE_K = 7
WELFARE_MAX = 0x61A8  # slider cap 0x3410D
TAX_RATE_MAX = 25
TAX_SCALE = 600  # [0x1029D8] init; monthly raw = wealth * 600 * rate / 100
# 0x2dc74 table 0x9936c, origin eax=0x178 edx=0x12. Left = +, right = −.
TAX_HIT_X = 0x178
TAX_HIT_Y = 0x12
TAX_HIT_W = 0x18
TAX_HIT_H = 0x18
TAX_RATE_X = 0x1B0
_FORUMBIT_LEFT = 0x23
_FORUMBIT_RIGHT = 0x25

# HISTORY.DAT / .SAV trailer — 200 × 20 B (history_dat.md). Scribe scales
# are the UI caps from C2.ENG [32]+1…+4, not extra stored fields.
HIST_REC = 20
HIST_CAP = 200
HIST_BYTES = HIST_REC * HIST_CAP
SCRIBE_WINDOWS = (10, 20, 30)
SCRIBE_SCALES = (10_000, 50_000, 8_000, 4_000)

FORUM_IDS = frozenset(
    {0xAE, 0xAF, 0xB0, 0xB2, 0xB3, 0xB4, 0xB6, 0xB7, 0xB8, 0xB9}
)

_BTN_X0, _BTN_Y0 = 8, 368
_BTN_W, _BTN_H = 154, 34
_BTN_GAP = 4

_PANEL_X, _PANEL_Y = 16, 36
_PANEL_W, _PANEL_H = 608, 320

# Native C2 Forum overlay. Integer-upscaled to the city well (left of the
# 162 px INT_CITY strip — same as city_chrome.SIDEBAR_W). At 640×480 the
# overlay is full-window; the sidebar is never stretched.
FORUM_NATIVE_W = 640
FORUM_NATIVE_H = 480
_FORUM_SIDEBAR_W = 162
_FORUM_LETTERBOX = (12, 16, 28)

_SLIDER_X = 220
_SLIDER_W = 160
_ROW_H = 22


@dataclass
class LaborState:
    """Chunk 52/54/55/56. assigned[0:7] + idle = ready."""

    ready: int = 0
    estimate: int = 0
    last_ready: int = 0
    welfare: int = 0
    assigned: list[int] = field(default_factory=lambda: [0] * LABOR_ROWS)
    need: list[int] = field(default_factory=lambda: [0] * LABOR_ROWS)

    @property
    def idle(self) -> int:
        used = CREW
        for i, n in enumerate(self.assigned):
            if i == LABOR_CONSTRUCTION:
                continue
            used += max(0, n)
        return max(0, self.ready - used)

    def clamp(self) -> None:
        for i in range(LABOR_ROWS):
            self.assigned[i] = max(0, int(self.assigned[i]))
            self.need[i] = max(0, int(self.need[i]))
        self.assigned[LABOR_CONSTRUCTION] = CREW
        extra = sum(self.assigned) - self.ready
        if extra > 0:
            for i in range(LABOR_ROWS - 1, -1, -1):
                if i == LABOR_CONSTRUCTION:
                    continue
                take = min(self.assigned[i], extra)
                self.assigned[i] -= take
                extra -= take
                if extra <= 0:
                    break
        self.assigned[LABOR_CONSTRUCTION] = CREW


@dataclass
class ForumState:
    """forum_view session. kind 0 = chrome illustration + 12 buttons."""

    kind: int = KIND_PLEBS
    labor: LaborState = field(default_factory=LaborState)
    bg: Image.Image | None = None
    bits: list = field(default_factory=list)
    oracle_advice: int | None = None  # 0…3 column, or None
    scribe_years: int = 10  # 10 / 20 / 30 — arrows only change the window


def _eng(eng, slot: int, skip: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, skip)
        if got:
            return got.rstrip()
    return fallback


def _off(x: int, y: int) -> int:
    return y * MAP_W * TILE_STRIDE + x * TILE_STRIDE


def _origin(tiles: bytearray, x: int, y: int) -> bool:
    return (tiles[_off(x, y) + 5] & 0xF) == 0


def is_forum_building(tid: int) -> bool:
    return tid in FORUM_IDS


def count_origins(tiles: bytearray, pred) -> int:
    n = 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off + 5] & 0xF:
                continue
            if pred(tiles[off]):
                n += 1
    return n


def _div8(n: int) -> int:
    """0x4447B signed n/8. Need counters are non-negative."""
    return max(0, int(n)) // 8


def labor_need_from_city(tiles: bytearray, *, city_only: bool) -> list[int]:
    """Need from the map. EXE 0x44470 + census 0x44AD4 / 0x44B0E.

    Construction is always 20 (0x56403). Water is 2 per fountain origin
    (0xDB–0xDE) and 2 per baths origin (0xDF–0xE2) — not reservoir/well
    and not a flat 20. Fire / roads / walls are tile counts ÷ 8.
    """
    roads = 0
    walls = 0
    water_blds = 0
    fire_tiles = 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            tid = tiles[off]
            if 0x52 <= tid <= 0x5C or 0x4E <= tid <= 0x51 or 0x7C <= tid <= 0x7E:
                roads += 1
                continue
            if tid == 0xC0:
                roads += 1
                continue
            if tid in (0xC1, 0xC2):
                walls += 1
                continue
            origin = (tiles[off + 5] & 0xF) == 0
            if origin and 0xDB <= tid <= 0xDE:
                water_blds += 1
            elif origin and 0xDF <= tid <= 0xE2:
                water_blds += 1
            if tid < 0x78:
                continue
            if 0x78 <= tid <= 0x7B or tid == 0xBF:
                continue
            if 0xBC <= tid <= 0xE2:
                continue
            fire_tiles += 1
    provincial = 0 if city_only else 0
    return [
        CREW,
        _div8(fire_tiles),
        _div8(roads),
        water_blds * WATER_PER_BUILDING,
        _div8(walls),
        provincial,
        0,
    ]


def labor_index_from_skill(skill: int) -> int:
    """0x346F6: [0x1025C8] = skill*2+1."""
    return max(0, min(4, int(skill))) * 2 + 1


def _score_hire_band(score: int) -> tuple[int, int] | None:
    """0x56440 (ebx, edx) percents, or None = no ready change (score ≤ 105)."""
    if score < 10:
        return 50, 1
    if score < 25:
        return 30, 2
    if score < 50:
        return 20, 3
    if score < 75:
        return 15, 4
    if score < 95:
        return 9, 5
    if score > 2000:
        return 2, 200
    if score > 1500:
        return 2, 150
    if score > 1000:
        return 2, 100
    if score > 750:
        return 2, 60
    if score > 500:
        return 2, 40
    if score > 300:
        return 2, 20
    if score > 200:
        return 3, 15
    if score > 150:
        return 4, 11
    if score > 125:
        return 5, 9
    if score > 105:
        return 6, 8
    return None


def labor_tick_ready(ready: int, welfare: int, labor_index: int) -> int:
    """One 0x56440 month on the ready pool. Does not debit treasury."""
    ready = max(0, int(ready))
    welfare = max(0, int(welfare))
    if ready <= 0:
        score = 0
    else:
        score = ((WAGE_K - int(labor_index) // 3) * welfare * 100) // ready
    band = _score_hire_band(score)
    if band is None:
        return ready
    ebx, edx = band
    nxt = ready + ready * edx // 100 - ready * ebx // 100 + 1
    return 1 if nxt < 1 else nxt


def apply_month_labor(sim: SimState) -> int:
    """0x56440 on WRAP — ready pool then clamp sliders to the new total."""
    ready = max(0, int(getattr(sim, "plebs_ready", 0)))
    sim.plebs_last = ready
    idx = int(getattr(sim, "labor_index", 0) or labor_index_from_skill(getattr(sim, "skill", 0)))
    nxt = labor_tick_ready(ready, max(0, int(getattr(sim, "welfare", 0))), idx)
    sim.plebs_ready = nxt
    asg = list(getattr(sim, "labor_assigned", None) or [0] * LABOR_ROWS)
    while len(asg) < LABOR_ROWS:
        asg.append(0)
    extra = sum(asg[:LABOR_ROWS]) - nxt
    if extra > 0:
        for i in range(LABOR_ROWS - 1, -1, -1):
            take = min(asg[i], extra)
            asg[i] -= take
            extra -= take
            if extra <= 0:
                break
    sim.labor_assigned = asg[:LABOR_ROWS]
    return nxt


def forecast_ready(labor: LaborState, sim: SimState) -> int:
    """0x5660B first tick: next-month ready, live ready unchanged."""
    idx = int(getattr(sim, "labor_index", 0) or labor_index_from_skill(getattr(sim, "skill", 0)))
    est = labor_tick_ready(labor.ready, labor.welfare, idx)
    labor.estimate = est
    sim.plebs_estimate = est
    return est


def monthly_pop_tax_raw(wealth: int, tax_rate: int) -> int:
    """0x45696 / 0x281df: wealth * 600 * rate / 100."""
    return max(0, int(wealth)) * TAX_SCALE * max(0, int(tax_rate)) // 100


def year_pop_tax_estimate(wealth: int, tax_rate: int, ytd: int = 0, months: int = 0) -> int:
    """0x56DF5 → chunk 39. Remaining months at current wealth/rate, then /12/100."""
    left = max(0, 12 - max(0, int(months)))
    total = monthly_pop_tax_raw(wealth, tax_rate) * left + max(0, int(ytd))
    return (total // 12) // 100


def year_ind_tax_estimate(wealth: int, tax_rate: int, ytd: int = 0, months: int = 0) -> int:
    """0x56E54 → chunk 40. Same scale as population; wealth is [0x102904]."""
    return year_pop_tax_estimate(wealth, tax_rate, ytd=ytd, months=months)


def ytd_tax_dn(ytd: int) -> int:
    """Raw YTD → Dn. Same (//12)//100 as year_pop_tax_estimate when left=0."""
    return (max(0, int(ytd)) // 12) // 100


def collect_monthly_tax(sim: SimState) -> None:
    """0x45696 / 0x456C6 — month wrap uses live rates (chunks 29 / 30)."""
    pop_raw = monthly_pop_tax_raw(
        int(getattr(sim, "tax_wealth", 0)),
        int(getattr(sim, "tax_rate", 5)),
    )
    sim.tax_ytd = int(getattr(sim, "tax_ytd", 0)) + pop_raw
    sim.tax_months = int(getattr(sim, "tax_months", 0)) + 1
    ind_raw = monthly_pop_tax_raw(
        int(getattr(sim, "ind_wealth", 0)),
        int(getattr(sim, "industrial_tax", 5)),
    )
    sim.ind_tax_ytd = int(getattr(sim, "ind_tax_ytd", 0)) + ind_raw
    sim.ind_tax_months = int(getattr(sim, "ind_tax_months", 0)) + 1


def parse_history(blob: bytes | bytearray | None) -> list[tuple[int, int, int, int, int]]:
    """Non-empty 20 B records: (pop, treasury, taxP, taxI, year)."""
    raw = bytes(blob or b"")
    if len(raw) < HIST_REC:
        return []
    recs: list[tuple[int, int, int, int, int]] = []
    n = min(HIST_CAP, len(raw) // HIST_REC)
    for i in range(n):
        vals = struct.unpack_from("<5i", raw, i * HIST_REC)
        if any(v != 0 for v in vals):
            recs.append(vals)
    return recs


def history_window(
    recs: list[tuple[int, int, int, int, int]], years: int
) -> list[tuple[int, int, int, int, int]]:
    """Last N records (Scribe arrows: 10 / 20 / 30)."""
    n = 10 if years not in SCRIBE_WINDOWS else int(years)
    if not recs:
        return []
    return recs[-n:]


def _history_next_slot(blob: bytearray) -> int:
    last = -1
    n = min(HIST_CAP, len(blob) // HIST_REC)
    for i in range(n):
        vals = struct.unpack_from("<5i", blob, i * HIST_REC)
        if any(v != 0 for v in vals):
            last = i
    nxt = last + 1
    return 0 if nxt >= HIST_CAP else nxt


def append_history_year(sim: SimState) -> None:
    """FUN_00070ae3 — one 20 B trailer rec. close_year_books calls this."""
    blob = getattr(sim, "history", None)
    if not isinstance(blob, bytearray):
        blob = bytearray(blob or b"")
    if len(blob) < HIST_BYTES:
        blob.extend(b"\x00" * (HIST_BYTES - len(blob)))
    sim.history = blob
    rec = (
        int(getattr(sim, "population", 0)),
        int(getattr(sim, "treasury", 0)),
        int(getattr(sim, "pop_tax_last", 0)),
        int(getattr(sim, "ind_tax_last", 0)),
        int(getattr(sim, "year_raw", 0)),
    )
    struct.pack_into("<5i", blob, _history_next_slot(blob) * HIST_REC, *rec)


def oracle_advice_skip(sim: SimState, col: int) -> int:
    """0x57450 + city-only force id 17 → [31]+24. col 0…3.

    Empire / Peace (ids < 9) stay the city-only stub. Prosperity uses
    surplus / housing wealth we already store. Culture has no coverage
    mins in SimState — else branch is services ([31]+23).
    """
    if col < 0 or col > 3:
        return 7
    if getattr(sim, "city_only", 0) and col < 2:
        return 24
    if col == 2:
        books = treasurer_estimate(sim)
        if books.surplus < 0:
            return 17
        if int(getattr(sim, "tax_wealth", 0)) < 10:
            return 18
        return 19
    if col == 3:
        return 23
    return 24


def apply_month_treasury(sim: SimState) -> TreasurerBooks:
    """WRAP cash: +pop +ind −welfare. City Only tribute 0.

    Constructions are already deducted at place (`construct_ytd` is books only).
    Tax Dn is the increment of ytd_tax_dn so 12 months = year ESTIMATE.
    Operating is one month of welfare (0x565f9 / ESTIMATE welfare×months).
    """
    if not hasattr(sim, "treasury"):
        return TreasurerBooks()
    pop0 = ytd_tax_dn(getattr(sim, "tax_ytd", 0))
    ind0 = ytd_tax_dn(getattr(sim, "ind_tax_ytd", 0))
    collect_monthly_tax(sim)
    pop_dn = ytd_tax_dn(sim.tax_ytd) - pop0
    ind_dn = ytd_tax_dn(sim.ind_tax_ytd) - ind0
    operating = max(0, int(getattr(sim, "welfare", 0)))
    sim.operating_ytd = int(getattr(sim, "operating_ytd", 0)) + operating
    tribute = 0
    constructions = 0
    delta = pop_dn + ind_dn - operating - constructions - tribute
    sim.treasury = int(sim.treasury) + delta
    return TreasurerBooks(
        pop_tax=pop_dn,
        ind_tax=ind_dn,
        constructions=constructions,
        operating=operating,
        tribute=tribute,
        surplus=delta,
        wealth=max(0, int(getattr(sim, "tax_wealth", 0))),
        months_left=max(0, 12 - max(0, min(11, int(getattr(sim, "month", 0))))),
    )


def close_year_books(sim: SimState) -> None:
    """December→January: chunks 33–37 last-year + reset YTD (0x56c1c).

    Tax was already credited monthly. Career tribute hits treasury here;
    City Only tribute stays 0.
    """
    if not hasattr(sim, "pop_tax_last"):
        return
    pop = ytd_tax_dn(getattr(sim, "tax_ytd", 0))
    ind = ytd_tax_dn(getattr(sim, "ind_tax_ytd", 0))
    constructions = max(0, int(getattr(sim, "construct_ytd", 0)))
    operating = max(0, int(getattr(sim, "operating_ytd", 0)))
    tribute = 0 if getattr(sim, "city_only", 0) else max(0, int(getattr(sim, "tribute", 0)))
    if tribute:
        sim.treasury = int(sim.treasury) - tribute
    sim.pop_tax_last = pop
    sim.ind_tax_last = ind
    sim.construct_last = constructions
    sim.operating_last = operating
    sim.surplus_last = pop + ind - constructions - operating - tribute
    append_history_year(sim)
    sim.tax_ytd = 0
    sim.tax_months = 0
    sim.ind_tax_ytd = 0
    sim.ind_tax_months = 0
    sim.operating_ytd = 0
    sim.construct_ytd = 0


@dataclass
class TreasurerBooks:
    """Last-year ACCOUNTS + live ESTIMATE (0x56D39 / 0x5D892)."""

    pop_tax: int = 0
    ind_tax: int = 0
    constructions: int = 0
    operating: int = 0
    tribute: int = 0
    surplus: int = 0
    wealth: int = 0
    months_left: int = 12


def treasurer_estimate(sim: SimState, tiles: bytearray | None = None) -> TreasurerBooks:
    """Year ESTIMATE. City Only skips tribute. Industry uses [0x102934] or 0."""
    if tiles is not None:
        sim.tax_wealth = housing_tax_wealth(tiles)
        sim.ind_wealth = industry_tax_wealth(tiles)
    wealth = max(0, int(getattr(sim, "tax_wealth", 0)))
    ind_wealth = max(0, int(getattr(sim, "ind_wealth", 0)))
    month = max(0, min(11, int(getattr(sim, "month", 0))))
    left = 12 - month
    welfare = max(0, int(getattr(sim, "welfare", 0)))
    ytd_op = max(0, int(getattr(sim, "operating_ytd", 0)))
    operating = ytd_op + welfare * left
    pop_tax = year_pop_tax_estimate(
        wealth,
        int(getattr(sim, "tax_rate", 5)),
        ytd=int(getattr(sim, "tax_ytd", 0)),
        months=int(getattr(sim, "tax_months", 0)),
    )
    ind_tax = year_ind_tax_estimate(
        ind_wealth,
        int(getattr(sim, "industrial_tax", 5)),
        ytd=int(getattr(sim, "ind_tax_ytd", 0)),
        months=int(getattr(sim, "ind_tax_months", 0)),
    )
    tribute = 0 if getattr(sim, "city_only", 0) else max(0, int(getattr(sim, "tribute", 0)))
    constructions = max(0, int(getattr(sim, "construct_ytd", 0)))
    surplus = pop_tax + ind_tax - constructions - operating - tribute
    return TreasurerBooks(
        pop_tax=pop_tax,
        ind_tax=ind_tax,
        constructions=constructions,
        operating=operating,
        tribute=tribute,
        surplus=surplus,
        wealth=wealth,
        months_left=left,
    )


def init_city_only_labor(sim: SimState) -> None:
    """0x563E2 + City Only index 0x346F6 + one 0x3FCA0 / 0x56440 tick.

    New Game / start_city_assignment only. sav_read must not call this —
    it overwrites chunk 52/54/56 sliders with LABOR_ASSIGNED_INIT.
    """
    skill = max(0, min(4, int(getattr(sim, "skill", 0))))
    sim.labor_index = labor_index_from_skill(skill)
    sim.welfare = _CITY_ONLY_WELFARE[skill]
    sim.plebs_ready = READY_AFTER_INIT_TICK
    sim.plebs_last = READY_AFTER_INIT_TICK
    sim.labor_assigned = list(LABOR_ASSIGNED_INIT)
    sim.labor_need = [CREW, 0, 0, 0, 0, 0, 0]
    # 0x5660B runs on PLEBS draw — next month, not the already-applied init tick.
    sim.plebs_estimate = labor_tick_ready(
        READY_AFTER_INIT_TICK, sim.welfare, sim.labor_index
    )


def apply_saved_plebs(sim: SimState, tiles: bytearray | None = None) -> LaborState:
    """SAV → PLEBS sliders. Does not run labor_init 0x563E2.

    Construction stays 20 Need 20. Other assigned/welfare/ready keep the
    file bytes. Need (except construction) refreshes from the live map.
    """
    assigned = list(getattr(sim, "labor_assigned", None) or [0] * LABOR_ROWS)
    need = list(getattr(sim, "labor_need", None) or [0] * LABOR_ROWS)
    while len(assigned) < LABOR_ROWS:
        assigned.append(0)
    while len(need) < LABOR_ROWS:
        need.append(0)
    assigned[LABOR_CONSTRUCTION] = CREW
    if tiles is not None:
        need = labor_need_from_city(tiles, city_only=bool(getattr(sim, "city_only", 0)))
    need[LABOR_CONSTRUCTION] = CREW
    sim.labor_assigned = assigned[:LABOR_ROWS]
    sim.labor_need = need[:LABOR_ROWS]
    return labor_from_sim(sim)


def sync_labor(labor: LaborState, tiles: bytearray, sim: SimState) -> LaborState:
    """Refresh need from the live city; keep chunk-52 ready and sliders."""
    pop = recount_population(tiles)
    sim.population = pop
    ready = max(0, int(getattr(sim, "plebs_ready", 0)))
    labor.ready = ready
    labor.last_ready = int(getattr(sim, "plebs_last", 0) or ready)
    labor.welfare = max(0, int(getattr(sim, "welfare", 0)))
    labor.need = labor_need_from_city(tiles, city_only=bool(sim.city_only))
    labor.clamp()
    sim.tax_wealth = housing_tax_wealth(tiles)
    sim.ind_wealth = industry_tax_wealth(tiles)
    sim.factory_count = count_taxed_factories(tiles)
    sim.plebs_ready = labor.ready
    sim.welfare = labor.welfare
    sim.labor_assigned = list(labor.assigned)
    sim.labor_need = list(labor.need)
    if labor.ready:
        used = labor.ready - labor.idle
        sim.employed_pct = 100 * used // labor.ready
    forecast_ready(labor, sim)
    return labor


def labor_percent(assigned: int, need: int) -> int:
    """0x28219 assigned×100/need, cap 100. need==0 → 100 (0x45200 early-out)."""
    assigned = max(0, int(assigned))
    need = int(need)
    if need <= 0:
        return 100
    pct = assigned * 100 // need
    return 100 if pct > 100 else pct


def labor_row_staffed(assigned: int, need: int) -> bool:
    """Row can run: need 0, or assigned covers need (percent 100)."""
    return labor_percent(assigned, need) >= 100


def labor_idle_of(sim: SimState) -> int:
    ready = max(0, int(getattr(sim, "plebs_ready", 0)))
    asg = list(getattr(sim, "labor_assigned", None) or [])[:LABOR_ROWS]
    used = CREW
    for i, n in enumerate(asg):
        if i == LABOR_CONSTRUCTION:
            continue
        used += max(0, int(n))
    return max(0, ready - used)


def refresh_labor_need(sim: SimState, tiles: bytearray) -> list[int]:
    """Recompute chunk-56 need from the live map. Sliders / ready unchanged."""
    need = labor_need_from_city(tiles, city_only=bool(getattr(sim, "city_only", 0)))
    sim.labor_need = list(need)
    return need


def labor_shutoff(sim: SimState) -> frozenset[str]:
    """Kinds that do not run this cycle (assigned < need, or no idle factory seed).

    Construction (need always 20) gates forums. Fire gates prefect 0xE3.
    Water gates fountain/bath paint. Idle==0 and factory_labor==0 gates
    0xFA workers (leftover +9 stock). 0x28219 / 0x45200 / 0x56654.
    """
    asg = list(getattr(sim, "labor_assigned", None) or [0] * LABOR_ROWS)
    need = list(getattr(sim, "labor_need", None) or [0] * LABOR_ROWS)
    while len(asg) < LABOR_ROWS:
        asg.append(0)
    while len(need) < LABOR_ROWS:
        need.append(0)
    off: set[str] = set()
    if not labor_row_staffed(asg[LABOR_CONSTRUCTION], need[LABOR_CONSTRUCTION]):
        off.add("forum")
        off.add("construction")
    if not labor_row_staffed(asg[LABOR_FIRE], need[LABOR_FIRE]):
        off.add("prefect")
    if not labor_row_staffed(asg[LABOR_WATER], need[LABOR_WATER]):
        off.add("water")
    idle = labor_idle_of(sim)
    if idle <= 0 and int(getattr(sim, "factory_labor", 0) or 0) <= 0:
        off.add("factory")
    return frozenset(off)


def labor_from_sim(sim: SimState) -> LaborState:
    assigned = list(getattr(sim, "labor_assigned", None) or [0] * LABOR_ROWS)
    need = list(getattr(sim, "labor_need", None) or [0] * LABOR_ROWS)
    while len(assigned) < LABOR_ROWS:
        assigned.append(0)
    while len(need) < LABOR_ROWS:
        need.append(0)
    assigned[LABOR_CONSTRUCTION] = CREW
    return LaborState(
        ready=int(getattr(sim, "plebs_ready", 0)),
        estimate=int(getattr(sim, "plebs_estimate", 0)),
        last_ready=int(getattr(sim, "plebs_last", 0)),
        welfare=int(getattr(sim, "welfare", 0)),
        assigned=assigned[:LABOR_ROWS],
        need=need[:LABOR_ROWS],
    )


def load_forum_art(game: Path) -> Image.Image | None:
    try:
        from app import assets

        frames, _path = assets.load_pl8_frames(game, "FORUM.PL8")
        if frames:
            return frames[0].convert("RGB")
    except (OSError, ValueError, FileNotFoundError):
        return None
    return None


def load_forum_bits(game: Path) -> list:
    try:
        from app import assets

        frames, _path = assets.load_pl8_frames(game, "FORUMBIT.PL8")
        return frames
    except (OSError, ValueError, FileNotFoundError):
        return []


def open_forum(sim: SimState, tiles: bytearray, game: Path | None = None) -> ForumState:
    """forum_view_setup — enter PLEBS (the panel this pass is for)."""
    state = ForumState(kind=KIND_PLEBS, labor=labor_from_sim(sim))
    if game is not None:
        state.bg = load_forum_art(game)
        state.bits = load_forum_bits(game)
    sync_labor(state.labor, tiles, sim)
    return state


def forum_layout(win_w: int, win_h: int) -> tuple[int, int, int]:
    """Integer nearest-neighbor scale + origin for the 640×480 Forum overlay.

    ``scale = max(1, min(well_w // 640, well_h // 480))``. The well is the
    iso area left of the 162 px chrome when the window is wider than 640;
    at native size Forum is full-window so the sidebar is not reserved.
    Origin is the well's top-left (0, 0) — HUD still paints on top.
    """
    w = max(1, int(win_w))
    h = max(1, int(win_h))
    well_w = w - _FORUM_SIDEBAR_W if w > FORUM_NATIVE_W else w
    well_h = h
    scale = max(1, min(well_w // FORUM_NATIVE_W, well_h // FORUM_NATIVE_H))
    return scale, 0, 0


def forum_to_native(mx: int, my: int, win_w: int, win_h: int) -> tuple[int, int]:
    """Window pixel → native 640×480 Forum space (same layout as blit)."""
    scale, ox, oy = forum_layout(win_w, win_h)
    return (int(mx) - ox) // scale, (int(my) - oy) // scale


def button_rect(index: int) -> tuple[int, int, int, int]:
    col, row = index % 4, index // 4
    x = _BTN_X0 + col * (_BTN_W + _BTN_GAP)
    y = _BTN_Y0 + row * (_BTN_H + _BTN_GAP)
    return (x, y, _BTN_W, _BTN_H)


def button_at(mx: int, my: int) -> int | None:
    for i in range(12):
        x, y, w, h = button_rect(i)
        if x <= mx < x + w and y <= my < y + h:
            return i
    return None


def _font() -> ImageFont.ImageFont:
    return ImageFont.load_default()


def _slider_rects(row: int) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 86 + row * _ROW_H
    minus = (_SLIDER_X, y, 16, 16)
    bar = (_SLIDER_X + 20, y + 4, _SLIDER_W, 8)
    plus = (_SLIDER_X + 24 + _SLIDER_W, y, 16, 16)
    return minus, bar, plus


def _welfare_rects() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 58
    return ((_PANEL_X + 200, y, 16, 16), (_PANEL_X + 280, y, 16, 16))


def _tax_rects(row: int) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """EXE 0x9936c: left sprite = +, right sprite = −. row 0 pop, 1 industry."""
    y = TAX_HIT_Y + row * TAX_HIT_H
    plus = (TAX_HIT_X, y, TAX_HIT_W, TAX_HIT_H)
    minus = (TAX_HIT_X + TAX_HIT_W, y, TAX_HIT_W, TAX_HIT_H)
    return plus, minus


def hit_plebs(mx: int, my: int, labor: LaborState) -> str | None:
    """Slider / welfare hit. Returns an action token or None."""
    wm, wp = _welfare_rects()
    if _in_rect(mx, my, wm):
        return "welfare-"
    if _in_rect(mx, my, wp):
        return "welfare+"
    for i in range(LABOR_ROWS):
        if i == LABOR_CONSTRUCTION:
            continue
        minus, bar, plus = _slider_rects(i)
        if _in_rect(mx, my, minus):
            return f"row{i}-"
        if _in_rect(mx, my, plus):
            return f"row{i}+"
        if _in_rect(mx, my, bar) and labor.ready > 0:
            frac = (mx - bar[0]) / max(1, bar[2])
            return f"row{i}={int(frac * labor.ready)}"
    return None


def hit_treasurer(mx: int, my: int) -> str | None:
    """Population / industrial tax arrows — 0x9936c left +, right −."""
    for row, key in ((0, "tax"), (1, "ind")):
        plus, minus = _tax_rects(row)
        if _in_rect(mx, my, plus):
            return f"{key}+"
        if _in_rect(mx, my, minus):
            return f"{key}-"
    return None


def apply_treasurer_hit(action: str, sim: SimState) -> None:
    if action == "tax-":
        sim.tax_rate = max(0, int(sim.tax_rate) - 1)
    elif action == "tax+":
        sim.tax_rate = min(TAX_RATE_MAX, int(sim.tax_rate) + 1)
    elif action == "ind-":
        sim.industrial_tax = max(0, int(getattr(sim, "industrial_tax", 5)) - 1)
    elif action == "ind+":
        sim.industrial_tax = min(TAX_RATE_MAX, int(getattr(sim, "industrial_tax", 5)) + 1)


def _in_rect(x: int, y: int, r: tuple[int, int, int, int]) -> bool:
    rx, ry, rw, rh = r
    return rx <= x < rx + rw and ry <= y < ry + rh


def apply_plebs_hit(labor: LaborState, action: str, sim: SimState) -> str:
    """Apply a PLEBS hit. Returns ``need_plebs`` when allocate has no idle."""
    blocked = False
    if action == "welfare-":
        labor.welfare = max(0, labor.welfare - 1)
    elif action == "welfare+":
        labor.welfare = min(WELFARE_MAX, labor.welfare + 1)
    elif action.endswith("-") and action.startswith("row"):
        i = int(action[3:-1])
        if 0 <= i < LABOR_ROWS and i != LABOR_CONSTRUCTION and labor.assigned[i] > 0:
            labor.assigned[i] -= 1
    elif action.endswith("+") and action.startswith("row"):
        i = int(action[3:-1])
        if 0 <= i < LABOR_ROWS and i != LABOR_CONSTRUCTION:
            if labor.idle > 0:
                labor.assigned[i] += 1
            else:
                blocked = True
    elif "=" in action and action.startswith("row"):
        left, _, raw = action.partition("=")
        i = int(left[3:])
        want = max(0, int(raw))
        if 0 <= i < LABOR_ROWS and i != LABOR_CONSTRUCTION:
            others = sum(
                CREW if j == LABOR_CONSTRUCTION else labor.assigned[j]
                for j in range(LABOR_ROWS)
                if j != i
            )
            labor.assigned[i] = max(0, min(want, labor.ready - others))
    labor.assigned[LABOR_CONSTRUCTION] = CREW
    labor.clamp()
    sim.welfare = labor.welfare
    sim.labor_assigned = list(labor.assigned)
    sim.plebs_ready = labor.ready
    forecast_ready(labor, sim)
    if blocked:
        from app.messages import post_labor_status

        post_labor_status(sim, "need_plebs")
        return "need_plebs"
    return ""


def click_forum(
    state: ForumState,
    mx: int,
    my: int,
    sim: SimState,
    *,
    eng=None,
    frame_size: tuple[int, int] | None = None,
) -> str:
    """One left-click. Empty string = consumed, no HUD. 'exit' leaves forum.

    ``mx``/``my`` are window pixels. Pass ``frame_size`` so hits use the
    same integer-scaled rects as ``blit_forum``.
    """
    if frame_size is not None:
        mx, my = forum_to_native(mx, my, frame_size[0], frame_size[1])
    hit = button_at(mx, my)
    if hit is not None:
        skip = _BUTTON_SKIP[hit]
        kind = _BUTTON_KIND[hit]
        label = _eng(eng, 28, skip, _BUTTON_FALLBACK[hit])
        if kind == KIND_EXIT:
            return "exit"
        if kind in (KIND_PLEBS, KIND_ORACLE, KIND_TREASURER, KIND_SCRIBE):
            state.kind = kind
            state.oracle_advice = None
            return label
        state.kind = KIND_CHROME
        if skip in (11, 4, 2, 6):  # EMPIRE MAP / ROME / PERSONAL / CENTURION
            return _eng(
                eng, 31, 24,
                "You cannot get promoted when playing in city-only mode.",
            )
        return f"{label} — ainda não"

    if state.kind == KIND_PLEBS:
        action = hit_plebs(mx, my, state.labor)
        if action:
            return apply_plebs_hit(state.labor, action, sim)
        return ""

    if state.kind == KIND_TREASURER:
        action = hit_treasurer(mx, my)
        if action:
            apply_treasurer_hit(action, sim)
            return ""
        return ""

    if state.kind == KIND_ORACLE:
        col = _oracle_column(mx, my)
        if col is not None:
            state.oracle_advice = col
            return ""
        return ""

    if state.kind == KIND_SCRIBE:
        action = hit_scribe(mx, my)
        if action:
            apply_scribe_hit(state, action)
            return ""
        return ""
    return ""


def _scribe_year_rects() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 28
    return ((_PANEL_X + 220, y, 16, 16), (_PANEL_X + 320, y, 16, 16))


def hit_scribe(mx: int, my: int) -> str | None:
    minus, plus = _scribe_year_rects()
    if _in_rect(mx, my, minus):
        return "years-"
    if _in_rect(mx, my, plus):
        return "years+"
    return None


def apply_scribe_hit(state: ForumState, action: str) -> None:
    years = 10 if state.scribe_years not in SCRIBE_WINDOWS else int(state.scribe_years)
    if action == "years-":
        state.scribe_years = 10 if years <= 10 else years - 10
    elif action == "years+":
        state.scribe_years = 30 if years >= 30 else years + 10


def _oracle_column(mx: int, my: int) -> int | None:
    y = _PANEL_Y + 48
    if not (_PANEL_Y + 40 <= my < y + 80):
        return None
    w = _PANEL_W // 4
    if not (_PANEL_X <= mx < _PANEL_X + _PANEL_W):
        return None
    return (mx - _PANEL_X) // w


def blit_forum(
    frame_size: tuple[int, int],
    state: ForumState,
    sim: SimState,
    *,
    eng=None,
) -> Image.Image:
    """Compose native 640×480 Forum, then integer-upscale into ``frame_size``."""
    w, h = frame_size
    scale, ox, oy = forum_layout(w, h)
    native = _blit_forum_native(state, sim, eng=eng)
    if scale > 1:
        native = native.resize(
            (FORUM_NATIVE_W * scale, FORUM_NATIVE_H * scale),
            Image.Resampling.NEAREST,
        )
    if native.size == (w, h) and ox == 0 and oy == 0:
        return native
    canvas = Image.new("RGB", (w, h), _FORUM_LETTERBOX)
    canvas.paste(native, (ox, oy))
    return canvas


def _blit_forum_native(state: ForumState, sim: SimState, *, eng=None) -> Image.Image:
    """Paint the C2 Forum at 640×480 (panel, sliders, 4×3 chrome)."""
    if state.bg is not None:
        out = state.bg.resize((FORUM_NATIVE_W, FORUM_NATIVE_H), Image.Resampling.NEAREST)
    else:
        out = Image.new("RGB", (FORUM_NATIVE_W, FORUM_NATIVE_H), (28, 24, 20))
    out = out.convert("RGBA")
    draw = ImageDraw.Draw(out)
    font = _font()
    title = _eng(eng, 36, 0, "Plebeian Tribune") if state.kind == KIND_PLEBS else (
        _eng(eng, 31, 0, "Your Ratings") if state.kind == KIND_ORACLE else (
            _eng(eng, 28, 12, "Treasury") if state.kind == KIND_TREASURER else (
                _eng(eng, 32, 0, "Your Scribe") if state.kind == KIND_SCRIBE else
                _eng(eng, 28, 0, "CLEAR FORUM")
            )
        )
    )
    if state.kind != KIND_CHROME:
        draw.rectangle(
            (_PANEL_X, _PANEL_Y, _PANEL_X + _PANEL_W - 1, _PANEL_Y + _PANEL_H - 1),
            fill=(8, 20, 18, 230),
            outline=(200, 180, 90, 255),
        )
        draw.text((_PANEL_X + 10, _PANEL_Y + 8), title[:48], fill=(255, 228, 160, 255), font=font)
        if state.kind == KIND_PLEBS:
            _draw_plebs(draw, font, state.labor, eng)
        elif state.kind == KIND_ORACLE:
            _draw_oracle(draw, font, sim, state.oracle_advice, eng)
        elif state.kind == KIND_TREASURER:
            _draw_treasurer(draw, font, sim, eng, image=out, bits=state.bits)
        elif state.kind == KIND_SCRIBE:
            _draw_scribe(draw, font, sim, state.scribe_years, eng)
    for i, skip in enumerate(_BUTTON_SKIP):
        x, y, bw, bh = button_rect(i)
        kind = _BUTTON_KIND[i]
        lit = (kind == state.kind and kind != KIND_CHROME) or (
            state.kind == KIND_CHROME and kind == 0 and i == 5
        )
        if kind == state.kind and kind != 0:
            lit = True
        fill = (40, 70, 50, 230) if not lit else (160, 40, 30, 240)
        if kind == state.kind and kind in (
            KIND_PLEBS, KIND_ORACLE, KIND_TREASURER, KIND_SCRIBE
        ):
            fill = (160, 40, 30, 240)
        draw.rectangle((x, y, x + bw - 1, y + bh - 1), fill=fill, outline=(200, 190, 140, 255))
        lab = _eng(eng, 28, skip, _BUTTON_FALLBACK[i])
        draw.text((x + 8, y + 10), lab[:16], fill=(255, 230, 180, 255), font=font)
    return out.convert("RGB")


def _draw_plebs(draw: ImageDraw.ImageDraw, font, labor: LaborState, eng) -> None:
    ready_lab = _eng(eng, 36, 1, "plebs ready for work")
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 28),
        f"{labor.ready} {ready_lab}",
        fill=(220, 230, 210, 255),
        font=font,
    )
    delta = labor.ready - labor.last_ready
    if delta > 0:
        change = f"{_eng(eng, 36, 3, 'A rise of')} {delta}"
    elif delta < 0:
        change = f"{_eng(eng, 36, 2, 'A fall of')} {abs(delta)}"
    else:
        change = _eng(eng, 36, 4, "No change")
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 42),
        f"{change} {_eng(eng, 36, 5, 'from last month')}",
        fill=(200, 210, 190, 255),
        font=font,
    )
    wm, wp = _welfare_rects()
    draw.rectangle((wm[0], wm[1], wm[0] + wm[2] - 1, wm[1] + wm[3] - 1), outline=(200, 180, 90))
    draw.text((wm[0] + 4, wm[1] + 1), "-", fill=(255, 228, 160), font=font)
    draw.text(
        (wm[0] + 22, wm[1] + 1),
        f"{labor.welfare} Dn",
        fill=(255, 228, 160),
        font=font,
    )
    draw.rectangle((wp[0], wp[1], wp[0] + wp[2] - 1, wp[1] + wp[3] - 1), outline=(200, 180, 90))
    draw.text((wp[0] + 4, wp[1] + 1), "+", fill=(255, 228, 160), font=font)
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 58),
        _eng(eng, 36, 6, "With"),
        fill=(200, 210, 190),
        font=font,
    )
    draw.text(
        (_PANEL_X + 310, _PANEL_Y + 58),
        _eng(eng, 36, 7, "spent monthly on pleb welfare"),
        fill=(200, 210, 190),
        font=font,
    )
    est = _eng(eng, 36, 8, "The clerks estimate that their")
    if labor.estimate < labor.ready:
        swell = _eng(eng, 36, 9, "numbers will fall to")
    elif labor.estimate > labor.ready:
        swell = _eng(eng, 36, 10, "numbers will swell to")
    else:
        swell = _eng(eng, 36, 11, "numbers will be about the same")
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 72),
        f"{est} {swell} {labor.estimate}",
        fill=(200, 210, 190),
        font=font,
    )
    need_lab = _eng(eng, 36, 20, "Need")
    na = _eng(eng, 36, 21, "N/A")
    for i in range(LABOR_ROWS + 1):
        y = _PANEL_Y + 86 + i * _ROW_H
        if i < LABOR_ROWS:
            name = _eng(eng, 36, LABOR_LABEL_SKIP[i], f"row {i}")
            locked = i == LABOR_CONSTRUCTION
            assigned = CREW if locked else labor.assigned[i]
            need = CREW if locked else labor.need[i]
            if i >= 5:
                need_s = na
            else:
                need_s = str(need)
            minus, bar, plus = _slider_rects(i)
            draw.text((_PANEL_X + 10, y), name[:20], fill=(240, 230, 180), font=font)
            if not locked:
                draw.rectangle((minus[0], minus[1], minus[0] + 15, minus[1] + 15), outline=(200, 180, 90))
                draw.text((minus[0] + 4, minus[1] + 1), "-", fill=(255, 228, 160), font=font)
            draw.rectangle((bar[0], bar[1], bar[0] + bar[2], bar[1] + bar[3]), outline=(120, 110, 70))
            if labor.ready:
                fill_w = int(bar[2] * assigned / labor.ready)
                draw.rectangle(
                    (bar[0], bar[1], bar[0] + max(0, fill_w), bar[1] + bar[3]),
                    fill=(180, 140, 40),
                )
            if not locked:
                draw.rectangle((plus[0], plus[1], plus[0] + 15, plus[1] + 15), outline=(200, 180, 90))
                draw.text((plus[0] + 4, plus[1] + 1), "+", fill=(255, 228, 160), font=font)
            short = assigned < need and i < 5
            col = (255, 120, 90) if short else (220, 230, 210)
            draw.text(
                (_SLIDER_X + 48 + _SLIDER_W, y),
                f"{assigned}  {need_lab} {need_s}",
                fill=col,
                font=font,
            )
        else:
            name = _eng(eng, 36, 19, "Idle Plebs")
            draw.text((_PANEL_X + 10, y), name, fill=(240, 230, 180), font=font)
            draw.text(
                (_SLIDER_X, y),
                str(labor.idle),
                fill=(220, 230, 210),
                font=font,
            )


def _draw_oracle(draw, font, sim: SimState, advice: int | None, eng) -> None:
    names = (
        _eng(eng, 31, 1, "Empire"),
        _eng(eng, 31, 2, "Peace"),
        _eng(eng, 31, 3, "Prosperity"),
        _eng(eng, 31, 4, "Culture"),
    )
    vals = (
        int(getattr(sim, "rating_empire", 0)),
        int(getattr(sim, "rating_peace", 0)),
        int(getattr(sim, "rating_prosperity", 0)),
        int(getattr(sim, "rating_culture", 0)),
    )
    avg = int(getattr(sim, "rating_avg", 0))
    w = _PANEL_W // 4
    for i, (name, val) in enumerate(zip(names, vals)):
        x = _PANEL_X + i * w
        draw.rectangle((x + 8, _PANEL_Y + 40, x + w - 8, _PANEL_Y + 110), outline=(200, 180, 90))
        draw.text((x + 16, _PANEL_Y + 48), name, fill=(255, 228, 160), font=font)
        draw.text((x + 16, _PANEL_Y + 68), f"{val} %", fill=(220, 230, 210), font=font)
        if not getattr(sim, "city_only", 0):
            draw.text(
                (x + 16, _PANEL_Y + 84),
                f"{_eng(eng, 31, 6, '(Need')} 0 %)",
                fill=(180, 180, 160),
                font=font,
            )
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 120),
        f"{_eng(eng, 31, 5, 'Average rating: ')}{avg} %",
        fill=(220, 230, 210),
        font=font,
    )
    if advice is None:
        prompt = _eng(
            eng, 31, 7,
            "Select any of the ratings above to receive advice on improving them.",
        )
    else:
        skip = oracle_advice_skip(sim, advice)
        fallback = (
            "You cannot get promoted when playing in city-only mode. "
            "Get ADVICE on your city's Prosperity or Culture ratings by clicking on their boxes."
            if skip == 24 else ""
        )
        prompt = _eng(eng, 31, skip, fallback)
    draw.text((_PANEL_X + 10, _PANEL_Y + 150), prompt[:86], fill=(200, 210, 190), font=font)
    y = _PANEL_Y + 166
    for chunk in (prompt[86:172], prompt[172:258]):
        if chunk:
            draw.text((_PANEL_X + 10, y), chunk, fill=(200, 210, 190), font=font)
            y += 14


def _year_label(year_raw: int) -> str:
    if year_raw < 0:
        return f"{-int(year_raw)} BC"
    return f"{int(year_raw)} AD"


def _draw_scribe(draw, font, sim: SimState, years: int, eng) -> None:
    """HISTORY graphs only — pop / funds / pop tax / industry tax."""
    recs = history_window(parse_history(getattr(sim, "history", None)), years)
    window = 10 if years not in SCRIBE_WINDOWS else int(years)
    look = _eng(eng, 32, 5, "Look at records")
    last = _eng(eng, 32, 6, "for the last")
    yrs = _eng(eng, 32, 7, "years.")
    to = _eng(eng, 32, 8, "to")
    if recs:
        span = f"{_year_label(recs[0][4])} {to} {_year_label(recs[-1][4])}"
    else:
        span = f"{_year_label(int(getattr(sim, 'year_raw', 0)))} {to} {_year_label(int(getattr(sim, 'year_raw', 0)))}"
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 30),
        f"{look} {last} {window} {yrs}  {span}",
        fill=(200, 210, 190),
        font=font,
    )
    minus, plus = _scribe_year_rects()
    draw.rectangle((minus[0], minus[1], minus[0] + 15, minus[1] + 15), outline=(200, 180, 90))
    draw.text((minus[0] + 4, minus[1] + 1), "-", fill=(255, 228, 160), font=font)
    draw.rectangle((plus[0], plus[1], plus[0] + 15, plus[1] + 15), outline=(200, 180, 90))
    draw.text((plus[0] + 4, plus[1] + 1), "+", fill=(255, 228, 160), font=font)

    labels = (
        _eng(eng, 32, 1, "City population: 0 - "),
        _eng(eng, 32, 2, "City funds: 0 - "),
        _eng(eng, 32, 3, "Pop. taxes: 0 -"),
        _eng(eng, 32, 4, "Industry taxes: 0 -"),
    )
    series = (
        [r[0] for r in recs],
        [r[1] for r in recs],
        [r[2] for r in recs],
        [r[3] for r in recs],
    )
    gx = _PANEL_X + 12
    gw = _PANEL_W - 24
    gh = 44
    gy0 = _PANEL_Y + 52
    for i, (lab, scale, vals) in enumerate(zip(labels, SCRIBE_SCALES, series)):
        y = gy0 + i * (gh + 10)
        draw.text((gx, y), f"{lab}{scale}", fill=(255, 228, 160), font=font)
        bx = gx
        by = y + 14
        bw = gw
        bh = gh - 16
        draw.rectangle((bx, by, bx + bw - 1, by + bh - 1), outline=(120, 110, 70))
        n = max(window, 1)
        slot_w = max(1, bw // n)
        for k, val in enumerate(vals):
            frac = max(0.0, min(1.0, int(val) / scale)) if scale else 0.0
            bar_h = max(1, int((bh - 2) * frac)) if val else 0
            x0 = bx + (n - len(vals) + k) * slot_w
            if bar_h:
                draw.rectangle(
                    (x0 + 1, by + bh - 1 - bar_h, x0 + slot_w - 2, by + bh - 2),
                    fill=(180, 140, 40),
                )
        if vals:
            draw.text(
                (bx + bw - 70, y),
                str(vals[-1]),
                fill=(220, 230, 210),
                font=font,
            )


def _paste_bit(image, bits, index: int, x: int, y: int) -> bool:
    if image is None or not bits or index >= len(bits):
        return False
    spr = bits[index]
    if spr is None:
        return False
    frame = spr.convert("RGBA")
    image.paste(frame, (x, y), frame)
    return True


def _draw_tax_dial(
    draw,
    font,
    row: int,
    label: str,
    value: int,
    *,
    image=None,
    bits=None,
) -> None:
    """Circular needle + 0x9936c arrow pair. Rate text at x=0x1B0."""
    plus, minus = _tax_rects(row)
    y = plus[1]
    cx = plus[0] + TAX_HIT_W
    cy = y + TAX_HIT_H // 2
    r = 13
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(200, 180, 90), fill=(40, 32, 20, 240))
    draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), fill=(220, 190, 80))
    frac = max(0, min(TAX_RATE_MAX, int(value))) / TAX_RATE_MAX
    ang = math.radians(210.0 - frac * 240.0)
    nx = cx + int(math.cos(ang) * (r - 3))
    ny = cy - int(math.sin(ang) * (r - 3))
    draw.line((cx, cy, nx, ny), fill=(255, 228, 160), width=2)
    if not _paste_bit(image, bits, _FORUMBIT_LEFT, plus[0], plus[1]):
        draw.rectangle(
            (plus[0], plus[1], plus[0] + plus[2] - 1, plus[1] + plus[3] - 1),
            outline=(200, 180, 90),
        )
        draw.polygon(
            ((plus[0] + 16, cy), (plus[0] + 6, cy - 6), (plus[0] + 6, cy + 6)),
            fill=(255, 228, 160),
        )
    if not _paste_bit(image, bits, _FORUMBIT_RIGHT, minus[0], minus[1]):
        draw.rectangle(
            (minus[0], minus[1], minus[0] + minus[2] - 1, minus[1] + minus[3] - 1),
            outline=(200, 180, 90),
        )
        draw.polygon(
            ((minus[0] + 6, cy), (minus[0] + 16, cy - 6), (minus[0] + 16, cy + 6)),
            fill=(255, 228, 160),
        )
    draw.text((TAX_HIT_X - 108, y + 4), label[:22], fill=(200, 210, 190), font=font)
    draw.text((TAX_RATE_X, y + 4), f"{value} %", fill=(255, 228, 160), font=font)


def _draw_treasurer(draw, font, sim: SimState, eng, *, image=None, bits=None) -> None:
    est = treasurer_estimate(sim)
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 40),
        f"{_eng(eng, 28, 12, 'Treasury')}  {int(sim.treasury)} Dn",
        fill=(220, 230, 210),
        font=font,
    )
    pop = int(sim.population)
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 58),
        f"{_eng(eng, 28, 13, 'Citizens ')} {pop}",
        fill=(220, 230, 210),
        font=font,
    )
    emp = int(getattr(sim, "employed_pct", 0))
    draw.text(
        (_PANEL_X + 10, _PANEL_Y + 76),
        f"{_eng(eng, 28, 14, 'employed')} {emp} %",
        fill=(220, 230, 210),
        font=font,
    )
    _draw_tax_dial(
        draw, font, 0, _eng(eng, 28, 15, "Population Tax"), int(sim.tax_rate),
        image=image, bits=bits,
    )
    _draw_tax_dial(
        draw, font, 1, _eng(eng, 28, 16, "Industrial Tax"),
        int(getattr(sim, "industrial_tax", 5)),
        image=image, bits=bits,
    )
    if pop > 0 and est.pop_tax:
        av = est.pop_tax / pop
        draw.text(
            (TAX_RATE_X + 40, TAX_HIT_Y + 4),
            f"{_eng(eng, 28, 17, '(av. bill')} {av:.2f} Dn)",
            fill=(180, 190, 170),
            font=font,
        )
    factories = int(getattr(sim, "factory_count", 0))
    if factories > 0 and est.ind_tax:
        iav = est.ind_tax / factories
        draw.text(
            (TAX_RATE_X + 40, TAX_HIT_Y + TAX_HIT_H + 4),
            f"{_eng(eng, 28, 17, '(av. bill')} {iav:.2f} Dn)",
            fill=(180, 190, 170),
            font=font,
        )
    last = (
        int(getattr(sim, "surplus_last", 0)),
        int(getattr(sim, "pop_tax_last", 0)),
        int(getattr(sim, "ind_tax_last", 0)),
        int(getattr(sim, "construct_last", 0)),
        int(getattr(sim, "operating_last", 0)),
        0 if getattr(sim, "city_only", 0) else int(getattr(sim, "tribute", 0)),
    )
    live = (est.surplus, est.pop_tax, est.ind_tax, est.constructions, est.operating, est.tribute)
    labels = (
        "",
        f"{_eng(eng, 28, 22, '(+)')} {_eng(eng, 28, 24, 'Population Tax')}",
        f"{_eng(eng, 28, 22, '(+)')} {_eng(eng, 28, 25, 'Industry Tax')}",
        f"{_eng(eng, 28, 23, '(-)')} {_eng(eng, 28, 26, 'Constructions')}",
        f"{_eng(eng, 28, 23, '(-)')} {_eng(eng, 28, 27, 'Operating Costs')}",
        f"{_eng(eng, 28, 23, '(-)')} {_eng(eng, 28, 28, 'Annual Tribute')}",
    )
    y0 = _PANEL_Y + 134
    draw.text((_PANEL_X + 220, y0), _eng(eng, 28, 18, "ACCOUNTS "), fill=(255, 228, 160), font=font)
    draw.text((_PANEL_X + 360, y0), _eng(eng, 28, 19, "ESTIMATE "), fill=(255, 228, 160), font=font)
    for i, (lab, a, b) in enumerate(zip(labels, last, live)):
        y = y0 + 16 + i * 16
        if i == 0:
            word = _eng(eng, 28, 21, "surplus") if b >= 0 else _eng(eng, 28, 20, "loss")
            draw.text((_PANEL_X + 10, y), word, fill=(220, 230, 210), font=font)
        else:
            draw.text((_PANEL_X + 10, y), lab[:28], fill=(200, 210, 190), font=font)
        draw.text((_PANEL_X + 220, y), str(a), fill=(220, 230, 210), font=font)
        col = (255, 120, 90) if i == 0 and b < 0 else (220, 230, 210)
        draw.text((_PANEL_X + 360, y), str(b), fill=col, font=font)


def blit_pause_square(
    frame: Image.Image,
    pause_spr: Image.Image | None,
    *,
    label: str = "Game Paused",
    view_w: int = 478,
    view_h: int = 456,
) -> Image.Image:
    """INT_CITY sprite 6 (pause) centered on the city well — the Pause square."""
    out = frame.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    cx = max(40, view_w // 2)
    cy = 24 + max(40, view_h // 2)
    if pause_spr is not None:
        spr = pause_spr.convert("RGBA")
        if spr.width < 48:
            spr = spr.resize((spr.width * 2, spr.height * 2), Image.Resampling.NEAREST)
        x = cx - spr.width // 2
        y = cy - spr.height // 2 - 10
        pad = 8
        draw.rectangle(
            (x - pad, y - pad, x + spr.width + pad, y + spr.height + pad + 16),
            fill=(8, 20, 16, 210),
            outline=(200, 180, 90, 255),
        )
        overlay.paste(spr, (x, y), spr)
        draw.text((x, y + spr.height + 2), label[:22], fill=(255, 228, 160, 255), font=_font())
    else:
        s = 36
        draw.rectangle((cx - s, cy - s, cx + s, cy + s), fill=(8, 20, 16, 220), outline=(200, 180, 90, 255))
        draw.rectangle((cx - 10, cy - 16, cx - 2, cy + 16), fill=(80, 160, 220, 255))
        draw.rectangle((cx + 2, cy - 16, cx + 10, cy + 16), fill=(80, 160, 220, 255))
        draw.text((cx - 34, cy + s + 4), label[:22], fill=(255, 228, 160, 255), font=_font())
    return Image.alpha_composite(out, overlay).convert("RGB")


def selftest() -> list[str]:
    lines: list[str] = []
    tiles = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    need = labor_need_from_city(tiles, city_only=True)
    if need != [CREW, 0, 0, 0, 0, 0, 0]:
        lines.append(f"FAIL  empty need {need}")
    else:
        lines.append("ok    empty city construction 20")
    foff = 10 * MAP_W * TILE_STRIDE + 10 * TILE_STRIDE
    boff = 12 * MAP_W * TILE_STRIDE + 12 * TILE_STRIDE
    tiles[foff] = 0xDD
    tiles[foff + 5] = 0
    tiles[boff] = 0xDF
    tiles[boff + 5] = 0
    need = labor_need_from_city(tiles, city_only=True)
    if need[3] != 4:
        lines.append(f"FAIL  water need {need[3]}")
    else:
        lines.append("ok    1 fountain + 1 baths → water 4")
    tiles[foff] = 0
    tiles[boff] = 0
    if not is_forum_building(0xAF) or is_forum_building(0x82):
        lines.append("FAIL  forum id gate")
    else:
        lines.append("ok    Aventine is a Forum building")
    sim = SimState(city_only=1, population=400, plebs_ready=20)
    labor = LaborState()
    sync_labor(labor, tiles, sim)
    if labor.ready != 20:
        lines.append(f"FAIL  ready {labor.ready}")
    else:
        lines.append("ok    ready from chunk 52")
    sim_new = SimState(city_only=1, skill=2)
    init_city_only_labor(sim_new)
    if (
        sim_new.plebs_ready != READY_AFTER_INIT_TICK
        or sim_new.welfare != 8
        or sim_new.labor_assigned != list(LABOR_ASSIGNED_INIT)
    ):
        lines.append(
            f"FAIL  new-game labor {sim_new.plebs_ready} "
            f"{sim_new.welfare} {sim_new.labor_assigned}"
        )
    else:
        lines.append("ok    City Only Normal ready 42 welfare 8 sliders 20/12/4/4")
    sim_sav = SimState(
        city_only=1,
        skill=2,
        labor_index=5,
        plebs_ready=42,
        welfare=9,
        tax_rate=9,
        industrial_tax=6,
        labor_assigned=[20, 13, 4, 4, 0, 0, 0],
        labor_need=[CREW, 0, 0, 0, 0, 0, 0],
    )
    restored = apply_saved_plebs(sim_sav, tiles)
    if (
        restored.assigned[LABOR_FIRE] != 13
        or restored.assigned[LABOR_CONSTRUCTION] != CREW
        or restored.need[LABOR_CONSTRUCTION] != CREW
        or restored.welfare != 9
        or restored.ready != 42
        or sim_sav.tax_rate != 9
    ):
        lines.append(
            f"FAIL  SAV PLEBS {restored.assigned} ready={restored.ready} "
            f"welfare={restored.welfare}"
        )
    else:
        lines.append("ok    SAV PLEBS Fire 13 welfare 9, construction 20")
    apply_plebs_hit(restored, "row0+", sim_sav)
    apply_plebs_hit(restored, "row0-", sim_sav)
    if restored.assigned[LABOR_CONSTRUCTION] != CREW or restored.assigned[LABOR_FIRE] != 13:
        lines.append(f"FAIL  construction lock after SAV {restored.assigned}")
    else:
        lines.append("ok    construction +/- ignored after load, Fire stays 13")
    if labor_percent(12, 12) != 100 or labor_percent(6, 12) != 50:
        lines.append(f"FAIL  labor percent {labor_percent(12, 12)} {labor_percent(6, 12)}")
    else:
        lines.append("ok    0x28219 assigned*100/need")
    if labor_percent(4, 0) != 100:
        lines.append(f"FAIL  need 0 percent {labor_percent(4, 0)}")
    else:
        lines.append("ok    need 0 staffed 100")
    sim_gate = SimState(
        city_only=1,
        plebs_ready=42,
        labor_assigned=list(LABOR_ASSIGNED_INIT),
        labor_need=[CREW, 0, 0, 0, 0, 0, 0],
        factory_labor=0,
    )
    shut0 = labor_shutoff(sim_gate)
    if shut0:
        lines.append(f"FAIL  fresh Normal shutoff {sorted(shut0)}")
    else:
        lines.append("ok    Normal 20/12/4/4 idle 2 nothing shut")
    sim_gate.labor_assigned = [0, 12, 4, 4, 0, 0, 0]
    shut_c = labor_shutoff(sim_gate)
    if "forum" not in shut_c or "construction" not in shut_c:
        lines.append(f"FAIL  construction 0 shutoff {sorted(shut_c)}")
    else:
        lines.append("ok    construction assigned 0 forum/construction off")
    sim_gate.labor_assigned = list(LABOR_ASSIGNED_INIT)
    sim_gate.labor_need = [CREW, 0, 0, 6, 0, 0, 0]
    shut_w = labor_shutoff(sim_gate)
    if "water" not in shut_w:
        lines.append(f"FAIL  water 4<6 shutoff {sorted(shut_w)}")
    else:
        lines.append("ok    water assigned 4 need 6 fountains/baths off")
    sim_gate.labor_need = [CREW, 0, 0, 0, 0, 0, 0]
    sim_gate.labor_assigned = [20, 12, 4, 6, 0, 0, 0]
    shut_f = labor_shutoff(sim_gate)
    if "factory" not in shut_f:
        lines.append(f"FAIL  idle 0 factory shutoff {sorted(shut_f)}")
    else:
        lines.append("ok    idle 0 factory_labor 0 factory leftover")
    labor_pop = LaborState()
    sync_labor(labor_pop, tiles, SimState(city_only=1, population=400))
    if labor_pop.ready != 0:
        lines.append(f"FAIL  ready without chunk 52 {labor_pop.ready}")
    else:
        lines.append("ok    ready is not population//20")
    if button_at(_BTN_X0 + 2, _BTN_Y0 + 2) != 0:
        lines.append("FAIL  button 0 hit")
    else:
        lines.append("ok    4×3 chrome hit ORACLE")
    # Visual grid index 6 = PLEBS (row 1 col 2).
    px, py, _pw, _ph = button_rect(6)
    if button_at(px + 2, py + 2) != 6 or _BUTTON_KIND[6] != KIND_PLEBS:
        lines.append("FAIL  PLEBS button")
    else:
        lines.append("ok    PLEBS is grid cell 6")
    state = ForumState(kind=KIND_PLEBS, labor=labor)
    apply_plebs_hit(labor, "row0+", sim)
    apply_plebs_hit(labor, "row0-", sim)
    apply_plebs_hit(labor, "row0=0", sim)
    if labor.assigned[0] != CREW or labor.need[0] != CREW:
        lines.append(f"FAIL  construction locked {labor.assigned[0]} need {labor.need[0]}")
    else:
        lines.append("ok    construction +/- do nothing, still 20 Need 20")
    fire0 = labor.assigned[1]
    got = apply_plebs_hit(labor, "row1+", sim)
    if labor.assigned[0] != CREW:
        lines.append(f"FAIL  fire+ stole construction {labor.assigned}")
    elif labor.assigned[1] != fire0:
        lines.append(f"FAIL  fire+ from idle 0 {labor.assigned}")
    elif got != "need_plebs":
        lines.append(f"FAIL  allocate toast {got!r}")
    else:
        lines.append("ok    construction 20 reserved; Fire cannot steal it")
    # 0x56440 / 0x5660B: Normal index 5, ready 42, welfare 8 → next month 44.
    idx = labor_index_from_skill(2)
    if idx != 5:
        lines.append(f"FAIL  labor index {idx}")
    else:
        lines.append("ok    Normal labor index 5")
    if labor_tick_ready(40, 8, 5) != 42:
        lines.append(f"FAIL  init tick 40->{labor_tick_ready(40, 8, 5)}")
    else:
        lines.append("ok    0x56440 welfare 8 ready 40 -> 42")
    nxt = labor_tick_ready(42, 8, 5)
    if nxt != 44:
        lines.append(f"FAIL  forecast 8/42 -> {nxt}")
    else:
        lines.append("ok    next month swell 42 -> 44 at welfare 8")
    labor_w = LaborState(ready=42, last_ready=42, welfare=8)
    sim_w = SimState(city_only=1, skill=2, labor_index=5, plebs_ready=42, welfare=8)
    apply_plebs_hit(labor_w, "welfare+", sim_w)
    if labor_w.welfare != 9 or labor_w.estimate != labor_tick_ready(42, 9, 5):
        lines.append(f"FAIL  welfare+ forecast {labor_w.welfare} {labor_w.estimate}")
    else:
        lines.append(f"ok    raise budget -> next month {labor_w.estimate} immediately")
    if labor_tick_ready(42, 12, 5) != 46:
        lines.append(f"FAIL  welfare 12 -> {labor_tick_ready(42, 12, 5)}")
    else:
        lines.append("ok    welfare 12 -> swell to 46")
    if labor_tick_ready(42, 0, 5) != 22:
        lines.append(f"FAIL  welfare 0 -> {labor_tick_ready(42, 0, 5)}")
    else:
        lines.append("ok    welfare 0 -> fall to 22")
    sim_t = SimState(city_only=1, skill=2, treasury=12000, welfare=8, tax_rate=5, month=0)
    books = treasurer_estimate(sim_t)
    if books.pop_tax != 0 or books.tribute != 0 or books.operating != 96 or books.surplus != -96:
        lines.append(f"FAIL  empty treasurer {books}")
    else:
        lines.append("ok    City Only estimate op 96 tribute 0 surplus -96")
    sim_t.welfare = 9
    books9 = treasurer_estimate(sim_t)
    if books9.operating != 108:
        lines.append(f"FAIL  welfare 9 operating {books9.operating}")
    else:
        lines.append("ok    raise welfare -> operating 108 live")
    apply_treasurer_hit("tax+", sim_t)
    if sim_t.tax_rate != 6:
        lines.append(f"FAIL  tax+ {sim_t.tax_rate}")
    else:
        lines.append("ok    treasurer pop dial +1")
    tent = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    toff = 10 * MAP_W * TILE_STRIDE + 10 * TILE_STRIDE
    tent[toff] = 0x85  # communal hut wealth 4
    tent[toff + 5] = 0
    tent[toff + 10] = 0x0C
    if housing_tax_wealth(tent) != 4:
        lines.append(f"FAIL  tax wealth {housing_tax_wealth(tent)}")
    else:
        lines.append("ok    market tent wealth 4")
    if year_pop_tax_estimate(4, 5) != 1:
        lines.append(f"FAIL  pop tax est {year_pop_tax_estimate(4, 5)}")
    else:
        lines.append("ok    wealth 4 x 5% -> year tax 1")
    if year_pop_tax_estimate(0, 5) != 0:
        lines.append("FAIL  empty wealth tax")
    else:
        lines.append("ok    no housing -> no invented tax")
    sim_t.tax_wealth = 100
    before = treasurer_estimate(sim_t).pop_tax
    apply_treasurer_hit("tax+", sim_t)
    after = treasurer_estimate(sim_t).pop_tax
    if sim_t.tax_rate != 7 or after <= before:
        lines.append(f"FAIL  pop dial estimate {sim_t.tax_rate} {before}->{after}")
    else:
        lines.append(f"ok    turn pop dial -> ESTIMATE tax {before}->{after}")
    fac = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    foff = 8 * MAP_W * TILE_STRIDE + 8 * TILE_STRIDE
    fac[foff] = 0xFA
    fac[foff + 1] = 0x20
    fac[foff + 9] = 0x20  # stock 2
    fac[foff + 10] = 0x0C
    fac[foff + 19] = 1
    if industry_tax_wealth(fac) != 140:
        lines.append(f"FAIL  factory wealth {industry_tax_wealth(fac)}")
    else:
        lines.append("ok    factory stock 2 x 70 -> wealth 140")
    if industry_tax_wealth(bytearray(MAP_W * MAP_H * TILE_STRIDE)) != 0:
        lines.append("FAIL  invented industry wealth")
    else:
        lines.append("ok    no factories -> industry tax 0")
    sim_t.ind_wealth = 140
    sim_t.industrial_tax = 5
    ind0 = treasurer_estimate(sim_t).ind_tax
    apply_treasurer_hit("ind+", sim_t)
    ind1 = treasurer_estimate(sim_t).ind_tax
    if sim_t.industrial_tax != 6 or ind1 <= ind0:
        lines.append(f"FAIL  ind dial estimate {sim_t.industrial_tax} {ind0}->{ind1}")
    else:
        lines.append(f"ok    turn industry dial -> ESTIMATE tax {ind0}->{ind1}")
    apply_treasurer_hit("tax+", SimState(tax_rate=25))
    cap = SimState(tax_rate=25, industrial_tax=25)
    apply_treasurer_hit("tax+", cap)
    apply_treasurer_hit("ind+", cap)
    if cap.tax_rate != 25 or cap.industrial_tax != 25:
        lines.append(f"FAIL  rate cap {cap.tax_rate}/{cap.industrial_tax}")
    else:
        lines.append("ok    tax dials clamp 0-25")
    month_sim = SimState(tax_rate=10, industrial_tax=8, tax_wealth=100, ind_wealth=140)
    collect_monthly_tax(month_sim)
    if month_sim.tax_months != 1 or month_sim.ind_tax_months != 1:
        lines.append(f"FAIL  month collect {month_sim.tax_months}")
    elif month_sim.tax_ytd != monthly_pop_tax_raw(100, 10):
        lines.append(f"FAIL  month pop ytd {month_sim.tax_ytd}")
    else:
        lines.append("ok    next month collects at live dial rates")
    wrap = SimState(
        city_only=1,
        treasury=12000,
        welfare=8,
        tax_rate=5,
        tax_wealth=100,
        industrial_tax=5,
        ind_wealth=140,
    )
    books_w = apply_month_treasury(wrap)
    pop_dn = ytd_tax_dn(monthly_pop_tax_raw(100, 5))
    ind_dn = ytd_tax_dn(monthly_pop_tax_raw(140, 5))
    want = 12000 + pop_dn + ind_dn - 8
    if books_w.tribute != 0 or books_w.constructions != 0:
        lines.append(f"FAIL  wrap tribute/construct {books_w}")
    elif wrap.treasury != want or books_w.operating != 8:
        lines.append(f"FAIL  wrap treas {wrap.treasury} want {want}")
    else:
        lines.append(
            f"ok    WRAP +pop {pop_dn} +ind {ind_dn} -op 8 tribute 0 -> {wrap.treasury}"
        )
    raised = SimState(
        city_only=1,
        treasury=12000,
        welfare=8,
        tax_rate=10,
        tax_wealth=100,
        industrial_tax=5,
        ind_wealth=140,
    )
    apply_month_treasury(raised)
    if raised.treasury <= wrap.treasury:
        lines.append(f"FAIL  raise tax wrap {raised.treasury} vs 5% {wrap.treasury}")
    else:
        lines.append(f"ok    raise tax -> WRAP Dn {wrap.treasury}->{raised.treasury}")
    frame = blit_forum((640, 480), state, sim)
    if frame.size != (640, 480):
        lines.append(f"FAIL  forum blit {frame.size}")
    else:
        lines.append("ok    forum 640x480")
    if forum_layout(640, 480) != (1, 0, 0):
        lines.append(f"FAIL  forum scale 640 {forum_layout(640, 480)}")
    elif forum_layout(640 * 2 + _FORUM_SIDEBAR_W, 480 * 2) != (2, 0, 0):
        lines.append(f"FAIL  forum scale 2x {forum_layout(1442, 960)}")
    elif forum_layout(640 * 3 + _FORUM_SIDEBAR_W, 480 * 3) != (3, 0, 0):
        lines.append(f"FAIL  forum scale 3x {forum_layout(2082, 1440)}")
    else:
        lines.append("ok    forum scale 1/2/3 from well/640")
    wide = (FORUM_NATIVE_W * 2 + _FORUM_SIDEBAR_W, FORUM_NATIVE_H * 2)
    scaled = blit_forum(wide, state, sim)
    if scaled.size != wide:
        lines.append(f"FAIL  forum 2x blit {scaled.size}")
    elif scaled.getpixel((10, 10)) == _FORUM_LETTERBOX:
        lines.append("FAIL  forum 2x overlay empty")
    elif scaled.getpixel((FORUM_NATIVE_W * 2 + 8, 10)) != _FORUM_LETTERBOX:
        lines.append("FAIL  forum 2x stretched into sidebar")
    else:
        lines.append("ok    forum 2x nearest well, sidebar 1:1 strip")
    px, py, _pw, _ph = button_rect(11)
    exit_msg = click_forum(
        ForumState(kind=KIND_PLEBS, labor=labor),
        px * 2 + 4,
        py * 2 + 4,
        sim,
        frame_size=wide,
    )
    if exit_msg != "exit":
        lines.append(f"FAIL  scaled EXIT hit {exit_msg!r}")
    else:
        lines.append("ok    2x 4×3 hit-test uses scaled rects")
    labor_s = LaborState(
        ready=42, last_ready=42, welfare=8, assigned=list(LABOR_ASSIGNED_INIT)
    )
    sim_s = SimState(
        city_only=1, skill=2, labor_index=5, plebs_ready=42, welfare=8
    )
    sim_s.labor_assigned = list(LABOR_ASSIGNED_INIT)
    state_s = ForumState(kind=KIND_PLEBS, labor=labor_s)
    _wm, wp = _welfare_rects()
    click_forum(state_s, wp[0] * 2 + 2, wp[1] * 2 + 2, sim_s, frame_size=wide)
    if labor_s.welfare != 9:
        lines.append(f"FAIL  scaled welfare+ {labor_s.welfare}")
    else:
        lines.append("ok    2x PLEBS welfare slider")
    minus0, bar0, plus0 = _slider_rects(0)
    before0 = labor_s.assigned[0]
    idle0 = labor_s.idle
    click_forum(state_s, plus0[0] * 2 + 2, plus0[1] * 2 + 2, sim_s, frame_size=wide)
    click_forum(state_s, minus0[0] * 2 + 2, minus0[1] * 2 + 2, sim_s, frame_size=wide)
    click_forum(state_s, bar0[0] * 2 + 2, bar0[1] * 2 + 2, sim_s, frame_size=wide)
    if (
        labor_s.assigned[0] != CREW
        or labor_s.assigned[0] != before0
        or labor_s.idle != idle0
        or hit_plebs(plus0[0] + 2, plus0[1] + 2, labor_s) is not None
        or hit_plebs(minus0[0] + 2, minus0[1] + 2, labor_s) is not None
    ):
        lines.append(f"FAIL  scaled construction locked {labor_s.assigned} idle {labor_s.idle}")
    else:
        lines.append("ok    construction +/- do nothing, still 20 Need 20")
    fire_s = labor_s.assigned[1]
    minus1, _bar1, plus1 = _slider_rects(1)
    click_forum(state_s, plus1[0] * 2 + 2, plus1[1] * 2 + 2, sim_s, frame_size=wide)
    if labor_s.assigned[0] != CREW or labor_s.assigned[1] != fire_s + 1:
        lines.append(f"FAIL  fire+ after locked construction {labor_s.assigned}")
    else:
        lines.append("ok    Fire +/- still moves; construction stays 20")
    treas = ForumState(kind=KIND_TREASURER, labor=labor_w)
    tframe = blit_forum((640, 480), treas, sim_t)
    tp, _tm = _tax_rects(0)
    click_forum(treas, tp[0] + 2, tp[1] + 2, sim_t)
    ip, _im = _tax_rects(1)
    click_forum(treas, ip[0] + 2, ip[1] + 2, sim_t)
    if tframe.size != (640, 480) or sim_t.tax_rate != 8 or sim_t.industrial_tax != 7:
        lines.append(
            f"FAIL  treasurer blit/hit {tframe.size} "
            f"{sim_t.tax_rate}/{sim_t.industrial_tax}"
        )
    else:
        lines.append("ok    treasurer dial hit + ESTIMATE refresh")
    treas2 = ForumState(kind=KIND_TREASURER, labor=labor_w)
    click_forum(treas2, tp[0] * 2 + 2, tp[1] * 2 + 2, sim_t, frame_size=wide)
    click_forum(treas2, ip[0] * 2 + 2, ip[1] * 2 + 2, sim_t, frame_size=wide)
    if sim_t.tax_rate != 9 or sim_t.industrial_tax != 8:
        lines.append(
            f"FAIL  scaled treasurer hit {sim_t.tax_rate}/{sim_t.industrial_tax}"
        )
    else:
        lines.append("ok    2x treasurer dial hit")
    paused = blit_pause_square(frame, None, label="Game Paused")
    if paused.tobytes() == frame.tobytes():
        lines.append("FAIL  pause square empty")
    else:
        lines.append("ok    pause square paints")
    if parse_history(bytearray(HIST_BYTES)):
        lines.append("FAIL  empty HISTORY parse")
    else:
        lines.append("ok    empty HISTORY → no scribe bars")
    blob = bytearray(HIST_BYTES)
    struct.pack_into("<5i", blob, 0, 100, 12000, 4, 1, -300)
    struct.pack_into("<5i", blob, HIST_REC, 140, 11800, 6, 2, -299)
    recs = parse_history(blob)
    win = history_window(recs, 10)
    if recs != [(100, 12000, 4, 1, -300), (140, 11800, 6, 2, -299)]:
        lines.append(f"FAIL  HISTORY parse {recs}")
    elif win != recs:
        lines.append(f"FAIL  HISTORY window {win}")
    else:
        lines.append("ok    HISTORY 2 recs → 10-year window")
    extra = [(i, 0, 0, 0, -290 + i) for i in range(25)]
    if len(history_window(extra, 10)) != 10 or len(history_window(extra, 30)) != 25:
        lines.append("FAIL  HISTORY window 10/30")
    else:
        lines.append("ok    HISTORY window last 10 / all 25")
    sx, sy, _sw, _sh = button_rect(4)
    if _BUTTON_KIND[4] != KIND_SCRIBE or button_at(sx + 2, sy + 2) != 4:
        lines.append("FAIL  SCRIBE button")
    else:
        lines.append("ok    SCRIBE is grid cell 4")
    sim_h = SimState(
        city_only=1,
        year_raw=-299,
        population=140,
        treasury=11800,
        history=blob,
        rating_prosperity=12,
        rating_culture=4,
        rating_avg=4,
        tax_wealth=4,
    )
    scribe = ForumState(kind=KIND_SCRIBE, labor=labor)
    sframe = blit_forum((640, 480), scribe, sim_h)
    click_forum(scribe, sx + 2, sy + 2, sim_h)
    if scribe.kind != KIND_SCRIBE or sframe.size != (640, 480):
        lines.append(f"FAIL  scribe blit/kind {scribe.kind} {sframe.size}")
    else:
        lines.append("ok    SCRIBE blit Your Scribe + HISTORY bars")
    _sm, sp = _scribe_year_rects()
    click_forum(scribe, sp[0] + 2, sp[1] + 2, sim_h)
    if scribe.scribe_years != 20:
        lines.append(f"FAIL  scribe years+ {scribe.scribe_years}")
    else:
        lines.append("ok    SCRIBE arrow 10 → 20 years")
    click_forum(scribe, sp[0] + 2, sp[1] + 2, sim_h)
    click_forum(scribe, sp[0] + 2, sp[1] + 2, sim_h)
    if scribe.scribe_years != 30:
        lines.append(f"FAIL  scribe years cap {scribe.scribe_years}")
    else:
        lines.append("ok    SCRIBE window clamps 30")
    sim_o = SimState(city_only=1, tax_wealth=4)
    if oracle_advice_skip(sim_o, 0) != 24 or oracle_advice_skip(sim_o, 1) != 24:
        lines.append("FAIL  city-only Empire/Peace skip")
    elif oracle_advice_skip(sim_o, 2) != 18:
        lines.append(f"FAIL  prosperity housing skip {oracle_advice_skip(sim_o, 2)}")
    elif oracle_advice_skip(sim_o, 3) != 23:
        lines.append(f"FAIL  culture skip {oracle_advice_skip(sim_o, 3)}")
    else:
        lines.append("ok    Oracle city-only 24 / Prosperity 18 / Culture 23")
    oracle = ForumState(kind=KIND_ORACLE, labor=labor)
    click_forum(oracle, _PANEL_X + 20, _PANEL_Y + 50, sim_o)
    if oracle.oracle_advice != 0:
        lines.append(f"FAIL  oracle col {oracle.oracle_advice}")
    else:
        lines.append("ok    Oracle column hit Empire → city-only stub")
    ox, oy, _ow, _oh = button_rect(2)
    stub = click_forum(ForumState(kind=KIND_CHROME), ox + 2, oy + 2, sim_o)
    if "cannot get promoted" not in stub.lower() and "city-only" not in stub.lower():
        lines.append(f"FAIL  EMPIRE MAP stub {stub!r}")
    else:
        lines.append("ok    Career EMPIRE MAP stays city-only stub")
    close_sim = SimState(
        city_only=1,
        year_raw=-299,
        population=80,
        treasury=11000,
        tax_ytd=monthly_pop_tax_raw(100, 5) * 12,
        ind_tax_ytd=monthly_pop_tax_raw(140, 5) * 12,
        history=bytearray(HIST_BYTES),
    )
    close_year_books(close_sim)
    closed = parse_history(close_sim.history)
    if len(closed) != 1 or closed[0][0] != 80 or closed[0][4] != -299:
        lines.append(f"FAIL  year wrap HISTORY {closed}")
    else:
        lines.append("ok    December wrap appends HISTORY rec")
    return lines
