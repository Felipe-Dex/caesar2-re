"""forum_view 0x59A15 stand-in — City Only chrome + PLEBS labor.

Forum is a submode (view_submode=1): no sim tick. Open from a Forum
building (0xAF / 0xB2–0xB4 / 0xB7–0xB9) or INT_CITY view-tab sprite 11.
Career EMPIRE / ROME / PERSONAL stay stubs. Oracle ratings are cheap
(chunks 286–289) and stay on this screen.

Labor table = SavChunk 56 (8× assigned/need). Need is recomputed from
the city map; assigned is player-controlled (sliders). Ready pool is
chunk 52 [0x102A68], set by labor_init 0x563E2 (not population//20).
"""

from __future__ import annotations

import math
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

# forum_panel_draw kinds we actually host.
KIND_CHROME = 0
KIND_ORACLE = 1
KIND_TREASURER = 3
KIND_PLEBS = 8
KIND_EXIT = 9

# C2.ENG [28]+0…11 in file order → visual 4×3 (forum_qa.md).
_BUTTON_SKIP: tuple[int, ...] = (
    10, 6, 11, 1,
    3, 0, 8, 2,
    7, 4, 5, 9,
)
_BUTTON_KIND: tuple[int, ...] = (
    KIND_ORACLE, 0, 0, KIND_TREASURER,
    0, 0, KIND_PLEBS, 0,
    0, 0, 0, KIND_EXIT,
)
_BUTTON_FALLBACK: tuple[str, ...] = (
    "ORACLE", "CENTURION", "EMPIRE MAP", "TREASURER",
    "SCRIBE", "CLEAR FORUM", "PLEBS", "PERSONAL",
    "MERCHANT", "ROME", "HELP", "EXIT",
)

LABOR_ROWS = 7  # [36]+12…18; +19 Idle is the remainder
LABOR_LABEL_SKIP = tuple(range(12, 20))
# labor_init 0x563E2: construction need always 20; slider defaults below.
CREW = 20
# FAQ / 0x444A5: 2 per fountain origin 0xDB–0xDE + 2 per baths 0xDF–0xE2.
WATER_PER_BUILDING = 2
# City Only [0x1025C8] = skill*2+1 (0x346F6). Table 0x9659D {welfare, ready}.
# 0x3FCA0 then runs one 0x56440 tick: table 40 → 42 (A/B/C + D.SAV).
_CITY_ONLY_WELFARE = (7, 7, 8, 9, 9)
READY_TABLE = 40
READY_AFTER_INIT_TICK = 42
LABOR_ASSIGNED_INIT = (20, 12, 4, 4, 0, 0, 0)
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

FORUM_IDS = frozenset(
    {0xAE, 0xAF, 0xB0, 0xB2, 0xB3, 0xB4, 0xB6, 0xB7, 0xB8, 0xB9}
)

_BTN_X0, _BTN_Y0 = 8, 368
_BTN_W, _BTN_H = 154, 34
_BTN_GAP = 4

_PANEL_X, _PANEL_Y = 16, 36
_PANEL_W, _PANEL_H = 608, 320

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
        used = sum(max(0, n) for n in self.assigned)
        return max(0, self.ready - used)

    def clamp(self) -> None:
        for i in range(LABOR_ROWS):
            self.assigned[i] = max(0, int(self.assigned[i]))
            self.need[i] = max(0, int(self.need[i]))
        extra = sum(self.assigned) - self.ready
        if extra > 0:
            for i in range(LABOR_ROWS - 1, -1, -1):
                take = min(self.assigned[i], extra)
                self.assigned[i] -= take
                extra -= take
                if extra <= 0:
                    break


@dataclass
class ForumState:
    """forum_view session. kind 0 = chrome illustration + 12 buttons."""

    kind: int = KIND_PLEBS
    labor: LaborState = field(default_factory=LaborState)
    bg: Image.Image | None = None
    bits: list = field(default_factory=list)
    oracle_advice: int | None = None  # 0…3 column, or None


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
    """0x563E2 + City Only index 0x346F6 + one 0x3FCA0 / 0x56440 tick."""
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


def labor_from_sim(sim: SimState) -> LaborState:
    assigned = list(getattr(sim, "labor_assigned", None) or [0] * LABOR_ROWS)
    need = list(getattr(sim, "labor_need", None) or [0] * LABOR_ROWS)
    while len(assigned) < LABOR_ROWS:
        assigned.append(0)
    while len(need) < LABOR_ROWS:
        need.append(0)
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


def apply_plebs_hit(labor: LaborState, action: str, sim: SimState) -> None:
    if action == "welfare-":
        labor.welfare = max(0, labor.welfare - 1)
    elif action == "welfare+":
        labor.welfare = min(WELFARE_MAX, labor.welfare + 1)
    elif action.endswith("-") and action.startswith("row"):
        i = int(action[3:-1])
        if 0 <= i < LABOR_ROWS and labor.assigned[i] > 0:
            labor.assigned[i] -= 1
    elif action.endswith("+") and action.startswith("row"):
        i = int(action[3:-1])
        if 0 <= i < LABOR_ROWS and labor.idle > 0:
            labor.assigned[i] += 1
    elif "=" in action and action.startswith("row"):
        left, _, raw = action.partition("=")
        i = int(left[3:])
        want = max(0, int(raw))
        if 0 <= i < LABOR_ROWS:
            others = sum(labor.assigned[j] for j in range(LABOR_ROWS) if j != i)
            labor.assigned[i] = max(0, min(want, labor.ready - others))
    labor.clamp()
    sim.welfare = labor.welfare
    sim.labor_assigned = list(labor.assigned)
    sim.plebs_ready = labor.ready
    forecast_ready(labor, sim)


def click_forum(
    state: ForumState, mx: int, my: int, sim: SimState, *, eng=None
) -> str:
    """One left-click. Empty string = consumed, no HUD. 'exit' leaves forum."""
    hit = button_at(mx, my)
    if hit is not None:
        skip = _BUTTON_SKIP[hit]
        kind = _BUTTON_KIND[hit]
        label = _eng(eng, 28, skip, _BUTTON_FALLBACK[hit])
        if kind == KIND_EXIT:
            return "exit"
        if kind in (KIND_PLEBS, KIND_ORACLE, KIND_TREASURER):
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
            apply_plebs_hit(state.labor, action, sim)
            return ""
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
    w, h = frame_size
    if state.bg is not None:
        out = state.bg.resize((640, 480), Image.Resampling.NEAREST)
        if (w, h) != (640, 480):
            canvas = Image.new("RGB", (w, h), (12, 16, 28))
            canvas.paste(out, (0, 0))
            out = canvas
    else:
        out = Image.new("RGB", (w, h), (28, 24, 20))
    out = out.convert("RGBA")
    draw = ImageDraw.Draw(out)
    font = _font()
    title = _eng(eng, 36, 0, "Plebeian Tribune") if state.kind == KIND_PLEBS else (
        _eng(eng, 31, 0, "Your Ratings") if state.kind == KIND_ORACLE else (
            _eng(eng, 28, 12, "Treasury") if state.kind == KIND_TREASURER else
            _eng(eng, 28, 0, "CLEAR FORUM")
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
    for i, skip in enumerate(_BUTTON_SKIP):
        x, y, bw, bh = button_rect(i)
        kind = _BUTTON_KIND[i]
        lit = (kind == state.kind and kind != KIND_CHROME) or (
            state.kind == KIND_CHROME and kind == 0 and i == 5
        )
        if kind == state.kind and kind != 0:
            lit = True
        fill = (40, 70, 50, 230) if not lit else (160, 40, 30, 240)
        if kind == state.kind and kind in (KIND_PLEBS, KIND_ORACLE, KIND_TREASURER):
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
            assigned = labor.assigned[i]
            need = labor.need[i]
            if i >= 5:
                need_s = na
            else:
                need_s = str(need)
            minus, bar, plus = _slider_rects(i)
            draw.text((_PANEL_X + 10, y), name[:20], fill=(240, 230, 180), font=font)
            draw.rectangle((minus[0], minus[1], minus[0] + 15, minus[1] + 15), outline=(200, 180, 90))
            draw.text((minus[0] + 4, minus[1] + 1), "-", fill=(255, 228, 160), font=font)
            draw.rectangle((bar[0], bar[1], bar[0] + bar[2], bar[1] + bar[3]), outline=(120, 110, 70))
            if labor.ready:
                fill_w = int(bar[2] * assigned / labor.ready)
                draw.rectangle(
                    (bar[0], bar[1], bar[0] + max(0, fill_w), bar[1] + bar[3]),
                    fill=(180, 140, 40),
                )
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
        draw.text((x + 16, _PANEL_Y + 84), f"{_eng(eng, 31, 6, '(Need')} 0 %)", fill=(180, 180, 160), font=font)
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
    elif sim.city_only and advice < 2:
        prompt = _eng(
            eng, 31, 24,
            "You cannot get promoted when playing in city-only mode. "
            "Get ADVICE on your city's Prosperity or Culture ratings by clicking on their boxes.",
        )
    else:
        # Prosperity 9…12 / Culture 13…16 → skip 16…23; pick the “grow” line.
        skip = 19 if advice == 2 else 23
        prompt = _eng(eng, 31, skip, "")
    draw.text((_PANEL_X + 10, _PANEL_Y + 150), prompt[:86], fill=(200, 210, 190), font=font)
    y = _PANEL_Y + 166
    for chunk in (prompt[86:172], prompt[172:258]):
        if chunk:
            draw.text((_PANEL_X + 10, y), chunk, fill=(200, 210, 190), font=font)
            y += 14


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
    if labor.assigned[0] != 1:
        lines.append(f"FAIL  slider {labor.assigned}")
    else:
        lines.append("ok    plebs slider +1")
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
    frame = blit_forum((640, 480), state, sim)
    if frame.size != (640, 480):
        lines.append(f"FAIL  forum blit {frame.size}")
    else:
        lines.append("ok    forum 640x480")
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
    paused = blit_pause_square(frame, None, label="Game Paused")
    if paused.tobytes() == frame.tobytes():
        lines.append("FAIL  pause square empty")
    else:
        lines.append("ok    pause square paints")
    return lines
