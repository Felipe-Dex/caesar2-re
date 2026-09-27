"""forum_view 0x59A15 stand-in — City Only Forum chrome.

Forum is a submode (view_submode=1): no sim tick. Open from a Forum
building (0xAF / 0xB2–0xB4 / 0xB7–0xB9) or INT_CITY view-tab sprite 11.
Idle is CLEAR FORUM (full FORUM.PL8, no overlay). Advisors paint on the
same crowd except Oracle (RAT_FRON) and EMPIRE MAP (EMPIRE.PL8). Empire
Map is chrome only — no REGIONS assignment / career travel. Click a
rating label plays B-series RAW (0x57450 → 0x135a4). Scribe is HISTORY
graphs only (no letters).

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

import struct
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.city_map import MAP_H, MAP_W, TILE_STRIDE
from app.city_paint import (
    ID_ARENA,
    ID_COLISEUM,
    ID_GARDEN_HI,
    ID_GARDEN_LO,
    ID_GRAMMATICUS,
    ID_HOSPITAL,
    ID_LIBRARY,
    ID_ODEUM,
    ID_PLAZA_HI,
    ID_PLAZA_LO,
    ID_RHETOR,
    ID_THEATER,
    civic_working,
    count_taxed_factories,
    housing_tax_wealth,
    industry_tax_wealth,
    recount_population,
)
from app.city_sim import SimState

# Host kinds (not the EXE [0x117A5C] numbers — TREASURER took 3 first).
KIND_CHROME = 0
KIND_ORACLE = 1
KIND_PERSONAL = 2
KIND_TREASURER = 3
KIND_EMPIRE = 6
KIND_MERCHANT = 7
KIND_PLEBS = 8
KIND_EXIT = 9
KIND_SCRIBE = 10
KIND_CENTURION = 11
KIND_ROME = 12
KIND_HELP = 13

# C2.ENG [28]+0…11 in file order → visual 4×3 (forum_qa.md).
_BUTTON_SKIP: tuple[int, ...] = (
    10, 6, 11, 1,
    3, 0, 8, 2,
    7, 4, 5, 9,
)
_BUTTON_KIND: tuple[int, ...] = (
    KIND_ORACLE, KIND_CENTURION, KIND_EMPIRE, KIND_TREASURER,
    KIND_SCRIBE, KIND_CHROME, KIND_PLEBS, KIND_PERSONAL,
    KIND_MERCHANT, KIND_ROME, KIND_HELP, KIND_EXIT,
)
_ADVISOR_KINDS = frozenset(
    {
        KIND_ORACLE,
        KIND_PERSONAL,
        KIND_TREASURER,
        KIND_EMPIRE,
        KIND_MERCHANT,
        KIND_PLEBS,
        KIND_SCRIBE,
        KIND_CENTURION,
        KIND_ROME,
    }
)
_OVERLAY_KINDS = frozenset(
    {
        KIND_PERSONAL,
        KIND_TREASURER,
        KIND_MERCHANT,
        KIND_PLEBS,
        KIND_SCRIBE,
        KIND_CENTURION,
        KIND_ROME,
    }
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
# Forum sliders with a Need column. Construction is locked 20/20; rows 5–6
# show N/A and must not trip the labor HUD.
LABOR_SLIDER_ROWS = (LABOR_FIRE, LABOR_ROADS, LABOR_WATER, LABOR_WALLS)
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
# C2MODEL [790+skill*20] / [890+skill*20] rank-0 (Citizen) Need.
# City Only has no rank; HELP measures only Prosperity + Culture.
NEED_IND_RANK0 = (15, 15, 20, 20, 25)
NEED_AVG_RANK0 = (25, 25, 30, 30, 35)
# 0x55431 scale: Peace/Empire 1, Culture 3, Prosperity 4.
CULTURE_CAP_SCALE = 3
PROSPERITY_CAP_SCALE = 4
HOUSING_INCOME_CAP = 0x3C
SURPLUS_LO, SURPLUS_HI = -5000, 5000
POP_PROS_TERM_CAP = 2000
BROKE_COUNTDOWN = 0x18  # 0x54dc5
# Worship 0xA2–0xAC origins. HELP: no road access required.
ID_SHRINE, ID_TEMPLE, ID_BASILICA = 0xA2, 0xA6, 0xAA
# Long entertainment: one origin per pair (not both tid / tid2 halves).
ID_CIRCUS_ORIGIN, ID_CMAX_ORIGIN = 0xEB, 0xED
# EXE 0x2dc74 / 0x9936c: left gadget = +, right = − (chunks 29 / 30).
# Screen origin (0x178, 0x12) sits above this host panel — Population Tax
# was clipped. Hits live in the panel top-right, same pair as the screenshot.
TAX_LABEL_X = 284
TAX_HIT_X = 394
TAX_HIT_Y = 48
TAX_HIT_W = 14
TAX_HIT_H = 14
TAX_ROW_H = 22
TAX_RATE_X = 428
TAX_AV_X = 462
_TREAS_FILL = (10, 22, 48, 236)
_TREAS_EDGE = (158, 184, 210, 255)
_TREAS_INK = (188, 202, 214, 255)
_TREAS_HEAD = (214, 222, 230, 255)
_TREAS_RULE = (120, 150, 180, 255)
_SERIF_CACHE: dict[int, ImageFont.ImageFont] = {}

# HISTORY.DAT / .SAV trailer — 200 × 20 B (history_dat.md). Scribe scales
# are the UI caps from C2.ENG [32]+1…+4, not extra stored fields.
HIST_REC = 20
HIST_CAP = 200
HIST_BYTES = HIST_REC * HIST_CAP
SCRIBE_WINDOWS = (10, 20, 30)
# Screenshot 2×2 caps (pop / funds / pop tax / industry tax).
SCRIBE_SCALES = (10_000, 25_000, 8_000, 2_000)
RANK_CAESAR = 10  # [7]+10; promotions left = 10 − rank (0x555ce)
SALARY_MAX = 500
SALARY_STEP = 10
WAGE_MAX = 200
WAGE_STEP = 5
CONSCRIPT_MAX = 100
FAVOR_QUOTES = 12  # [37]+3…+14
INF_NAME_OFF, INF_NAME_LEN = 24, 20
# goods_16x48: +4 store, +8 factories, +24 supplied%, +36 /month
GOODS_STORE, GOODS_FACTORIES, GOODS_PRODUCED = 4, 8, 36
GOODS_LABELS: tuple[str, ...] = (
    "Wheat", "Grapes", "Cattle", "Wool", "Gems", "Lead", "Iron", "Copper",
    "Clay", "Sand", "Marble", "Stone", "Silk", "Spice", "Ivory", "Fish",
)

FORUM_IDS = frozenset(
    {0xAE, 0xAF, 0xB0, 0xB2, 0xB3, 0xB4, 0xB6, 0xB7, 0xB8, 0xB9}
)

_BTN_X0, _BTN_Y0 = 8, 368
_BTN_W, _BTN_H = 154, 34
_BTN_GAP = 4

_PANEL_X, _PANEL_Y = 16, 36
_PANEL_W, _PANEL_H = 608, 320

# Oracle kind 0xA (host KIND_ORACLE). Draw 0x5e9eb / click 0x3d843.
# Labels [31]+1…+4 at y=0x167; Need [31]+6 at y=0x177; hit y=0x164.
ORACLE_HIT_X0 = 0x0A
ORACLE_HIT_Y = 0x164
ORACLE_HIT_W = 0x8C
ORACLE_HIT_H = 0x21
ORACLE_COL_STRIDE = 0xA0
ORACLE_NAME_Y = 0x167
ORACLE_NEED_Y = 0x177
ORACLE_NAME_X = (0x1C, 0xBC, 0x160, 0x1FC)
ORACLE_NEED_X = (0x1C, 0xBC, 0x15C, 0x1FC)
ORACLE_AVG_X, ORACLE_AVG_Y = 0xA0, 0x18A
ORACLE_PROMPT_X, ORACLE_PROMPT_Y = 0x18, 0x19E
ORACLE_BACK_X, ORACLE_BACK_Y = 0xCC, 0x1D0
ORACLE_COL_Y0 = 0x12C  # 300 − 3*rating = capital Y
ORACLE_COL_SCALE = 3
ORACLE_COL_W, ORACLE_COL_H = 96, 337
ORACLE_INK = (16, 176, 16, 255)
ORACLE_INK_DIM = (12, 140, 12, 255)
# 0x57450 live ids → EAX 0x1f…0x2c → raw_name_bank B02…B15.
ORACLE_LIVE_IDS = (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16)
ORACLE_RAW_EAX0 = 0x1F

# Native C2 Forum overlay. Compose at 640×480, then integer-upscale and
# letterbox into the window (same rule as the city well). Never stretch
# X independently of Y — that fattened RAT_FRON / EMPIRE.PL8 on widescreen.
FORUM_NATIVE_W = 640
FORUM_NATIVE_H = 480
FORUM_LETTERBOX = (12, 16, 28)
_FORUM_LETTERBOX = FORUM_LETTERBOX
# 0x33C3D dest table at 0x95cbb / 0x95cbd (ecx*4, i16 x/y). Skip = ecx+1.
# E_PARTS2 sprite xy is decorative — using it put Germania Exterior on the sea.
EMPIRE_HOTSPOTS: tuple[tuple[int, int], ...] = (
    (250, 241), (279, 264), (226, 202), (267, 307), (230, 253),
    (176, 198), (188, 315), (118, 226), (91, 264), (72, 215),
    (157, 193), (83, 309), (286, 223), (142, 166), (329, 255),
    (345, 292), (371, 331), (202, 155), (412, 352), (337, 352),
    (473, 327), (141, 101), (239, 351), (484, 289), (388, 276),
    (435, 273), (413, 246), (478, 244), (365, 224), (332, 208),
    (280, 184), (241, 169), (216, 137), (454, 315), (512, 203),
    (520, 267), (117, 98), (142, 45), (249, 88), (264, 147),
    (317, 165), (372, 171), (428, 169), (466, 168),
)
EMPIRE_HIT_W = 36
EMPIRE_HIT_H = 28
EMPIRE_GERMANIA_EXTERIOR = 39  # [5] skip; dest (249, 88) — north, not the Med.
EMPIRE_CRETA = 17
# 0x5C621 dialog: 0x59ff8 frame at (0x70,0x80), 0x1A×0x10 tiles of 16.
# EMPIRE.256[0x11] = (93,146,121) green-teal — C2 “quadro verde”, not VGA blue.
EMPIRE_DLG_X, EMPIRE_DLG_Y = 0x70, 0x80
EMPIRE_DLG_TILES_W, EMPIRE_DLG_TILES_H = 0x1A, 0x10
EMPIRE_DLG_W = EMPIRE_DLG_TILES_W * 16
EMPIRE_DLG_H = EMPIRE_DLG_TILES_H * 16
EMPIRE_NAME_X, EMPIRE_NAME_Y = 0x90, 0x9C
EMPIRE_STAT_X, EMPIRE_STAT_Y = 0x90, 0xC0
EMPIRE_FLAVOR_X, EMPIRE_FLAVOR_Y = 0x90, 0xE0
EMPIRE_FLAVOR_W, EMPIRE_FLAVOR_H = 0x160, 0x64
# 0x2ddad close/X: sprite 0x33, 24×24 (0x14dc4 / ebx=0x18). Top-right of frame.
EMPIRE_CLOSE_W, EMPIRE_CLOSE_H = 24, 24
EMPIRE_CLOSE_X = EMPIRE_DLG_X + EMPIRE_DLG_W - EMPIRE_CLOSE_W - 6
EMPIRE_CLOSE_Y = EMPIRE_DLG_Y + 6
# E_PARTS2 sprites 44–46: 64×25 @ (286,402), 64×25 @ (358,402), 32×25 @ (429,402).
EMPIRE_PLATE_X0, EMPIRE_PLATE_X1 = 286, 461
EMPIRE_PLATE_Y, EMPIRE_PLATE_H = 402, 25
EMPIRE_CAP_Y = 408  # [33]+1 inside the marble plate band
EMPIRE_FOOT_Y = 442  # [33]+3 below that frame
EMPIRE_TEAL = (93, 146, 121, 240)
EMPIRE_TEAL_INNER = (56, 100, 88, 255)
EMPIRE_TEAL_EDGE = (200, 216, 180, 255)
EMPIRE_TEAL_CLOSE = (60, 104, 90, 255)
EMPIRE_INK = (240, 228, 160, 255)
EMPIRE_INK_DIM = (210, 200, 140, 255)
# 0x135A4(skip+0x3A): table 0x93694. skip 1=B30, skip 2=C01 … skip 32=C31.
EMPIRE_RAW_BASE = 0x3A
# HELP.ENG: menus table 66+topic*58 with topic=skip+1148 → Creta island line.
EMPIRE_HELP_TOPIC0 = 1148
_HELP_MAGIC = b"Helpfile"
_HELP_REC = 58
_HELP_TABLE = 66

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

    kind: int = KIND_CHROME
    labor: LaborState = field(default_factory=LaborState)
    bg: Image.Image | None = None
    bits: list = field(default_factory=list)
    oracle_back: Image.Image | None = None  # RAT_FRON 640×480
    oracle_column: Image.Image | None = None  # RAT_BACK[0] 96×337
    oracle_advice: int | None = None  # 0…3 column, or None
    oracle_sfx: str = ""  # B-series stem from 0x135a4, empty if none
    scribe_years: int = 10  # 10 / 20 / 30 — arrows only change the window
    empire_map: Image.Image | None = None  # EMPIRE.PL8 640×480
    empire_parts: list = field(default_factory=list)  # E_PARTS2 (img,x,y)
    empire_pick: int | None = None  # [5] skip 1…44, chrome only
    empire_flavor: str = ""  # HELP.ENG body from 0x57B48
    empire_sfx: str = ""  # C-series stem, 0x135A4(skip+0x3A)
    field_focus: str = ""  # donate | gift | ""
    field_edit: str = ""


def _eng(eng, slot: int, skip: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, skip)
        if got:
            return got.rstrip()
    return fallback


def _fit_forum_native(src: Image.Image, fill=(12, 16, 28, 255)) -> Image.Image:
    """Paste ``src`` into 640×480 without stretching (aspect + letterbox)."""
    im = src.convert("RGBA")
    if im.size == (FORUM_NATIVE_W, FORUM_NATIVE_H):
        return im
    canvas = Image.new("RGBA", (FORUM_NATIVE_W, FORUM_NATIVE_H), fill)
    fitted = im.copy()
    fitted.thumbnail((FORUM_NATIVE_W, FORUM_NATIVE_H), Image.Resampling.NEAREST)
    canvas.paste(
        fitted,
        ((FORUM_NATIVE_W - fitted.width) // 2, (FORUM_NATIVE_H - fitted.height) // 2),
        fitted,
    )
    return canvas


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
            if 0xC1 <= tid <= 0xCA:
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


def rating_need(sim: SimState) -> tuple[int, int]:
    """C2MODEL Citizen Need for this skill. City Only has no rank slot."""
    skill = max(0, min(4, int(getattr(sim, "skill", 0))))
    return NEED_IND_RANK0[skill], NEED_AVG_RANK0[skill]


def rating_cap(raw: int, population: int, scale: int) -> int:
    """0x55431 — min(raw, 100, first n where n*10*scale >= pop)."""
    esi = max(0, min(100, int(raw)))
    pop = max(0, int(population))
    for n in range(100):
        if n * 10 * scale >= pop:
            return min(esi, n)
    return esi


def _count_origins(
    tiles: bytearray,
    lo: int,
    hi: int,
    *,
    working: bool,
    size: int | None = None,
) -> int:
    n = 0
    need = MAP_W * MAP_H * TILE_STRIDE
    if len(tiles) < need:
        return 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = y * MAP_W * TILE_STRIDE + x * TILE_STRIDE
            tid = tiles[off]
            if tid < lo or tid > hi:
                continue
            if tiles[off + 5] & 0xF:
                continue
            if working:
                if size is None:
                    if not civic_working(tiles, x, y):
                        continue
                elif not civic_working(tiles, x, y, size):
                    continue
            n += 1
    return n


def _clamp100(n: int) -> int:
    if n < 0:
        return 0
    return 100 if n > 100 else n


def _culture_covers(tiles: bytearray, population: int) -> tuple[int, int, int]:
    """0x55012 — entertainment / temple / services percents, each 0…100."""
    theater = _count_origins(tiles, ID_THEATER, ID_THEATER, working=True)
    odeum = _count_origins(tiles, ID_ODEUM, ID_ODEUM, working=True)
    arena = _count_origins(tiles, ID_ARENA, ID_ARENA, working=True)
    coliseum = _count_origins(tiles, ID_COLISEUM, ID_COLISEUM, working=True)
    circus = _count_origins(tiles, ID_CIRCUS_ORIGIN, ID_CIRCUS_ORIGIN, working=True)
    cmax = _count_origins(tiles, ID_CMAX_ORIGIN, ID_CMAX_ORIGIN, working=True)
    ent = (
        theater * 5
        + odeum * 8
        + arena * 12
        + coliseum * 16
        + circus * 20
        + cmax * 25
    ) * 100

    basilica = _count_origins(tiles, ID_BASILICA, 0xAC, working=False, size=3)
    temple = _count_origins(tiles, ID_TEMPLE, 0xA8, working=False, size=2)
    shrine = _count_origins(tiles, ID_SHRINE, 0xA5, working=False)
    cult = (basilica * 12 + temple * 7 + shrine * 2) * 100

    gram = _count_origins(tiles, ID_GRAMMATICUS, ID_GRAMMATICUS, working=True)
    rhetor = _count_origins(tiles, ID_RHETOR, ID_RHETOR, working=True)
    garden = _count_origins(tiles, ID_GARDEN_LO, ID_GARDEN_HI, working=False)
    plaza = _count_origins(tiles, ID_PLAZA_LO, ID_PLAZA_HI, working=False)
    hosp = _count_origins(tiles, ID_HOSPITAL, ID_HOSPITAL, working=True)
    lib = _count_origins(tiles, ID_LIBRARY, ID_LIBRARY, working=True)
    svc = (
        (gram + rhetor) // 2
        + garden * 4
        + plaza * 7
        + hosp * 10
        + lib * 20
    ) * 100

    denom = (int(population) >> 4) + 2
    if denom <= 0:
        denom = 2
    return (
        _clamp100(ent // denom),
        _clamp100(cult // denom),
        _clamp100(svc // denom),
    )


def _housing_income(sim: SimState, population: int) -> int:
    """0x56ed2 → [0x1025ac]. (wealth×600×rate/100/pop)/4, cap 60."""
    if population <= 0:
        return 0
    wealth = max(0, int(getattr(sim, "tax_wealth", 0)))
    rate = max(0, int(getattr(sim, "tax_rate", 5)))
    raw = wealth * TAX_SCALE * rate // 100 // population
    return min(HOUSING_INCOME_CAP, max(0, raw // 4))


def tick_city_ratings(
    sim: SimState, tiles: bytearray, *, month_was: int | None = None
) -> None:
    """0x54e3c — Culture 0x55012 + Prosperity 0x5524e. City Only skips E/P.

    Empire / Peace stay stubs. Average is (P+C)/2 — HELP measures those two.
    ``month_was`` is the completing month (calendar_advance already ++).
    December (11) adds year surplus [0x102A64] into [0x1025D8].
    """
    if tiles is not None:
        sim.tax_wealth = housing_tax_wealth(tiles)
        pop = recount_population(tiles)
        sim.population = pop
    else:
        pop = max(0, int(getattr(sim, "population", 0)))
    month = int(month_was) if month_was is not None else int(getattr(sim, "month", 0))
    if month == 11:
        sim.rating_surplus = int(getattr(sim, "rating_surplus", 0)) + int(
            getattr(sim, "surplus_last", 0)
        )
    surplus = int(getattr(sim, "rating_surplus", 0))
    if surplus < SURPLUS_LO:
        surplus = SURPLUS_LO
    if surplus > SURPLUS_HI:
        surplus = SURPLUS_HI
    sim.rating_surplus = surplus

    income = _housing_income(sim, pop)
    sim.housing_income = income
    pop_term = min(POP_PROS_TERM_CAP, pop) // 60
    raw_p = income + pop_term + surplus // 200
    capped_p = rating_cap(raw_p, pop, PROSPERITY_CAP_SCALE)
    sim.rating_prosperity = capped_p
    sim.rating_prosperity_cap = 1 if raw_p > capped_p and pop >= 10 else 0

    ent, temple, svc = _culture_covers(tiles or bytearray(), pop)
    sim.cover_entertainment = ent
    sim.cover_temple = temple
    sim.cover_services = svc
    raw_c = (ent + temple + svc) // 3
    capped_c = rating_cap(raw_c, pop, CULTURE_CAP_SCALE)
    sim.rating_culture = capped_c
    sim.rating_culture_cap = 1 if raw_c > capped_c and pop >= 10 else 0

    if getattr(sim, "city_only", 0):
        sim.rating_empire = 0
        sim.rating_peace = 0
        sim.rating_avg = (capped_p + capped_c) // 2
    else:
        sim.rating_avg = (capped_p + capped_c) // 2


def city_only_won(sim: SimState) -> bool:
    """City Only: P and C each >= Citizen Need, (P+C)/2 >= avg Need."""
    if not getattr(sim, "city_only", 0):
        return False
    need, avg_need = rating_need(sim)
    p = int(getattr(sim, "rating_prosperity", 0))
    c = int(getattr(sim, "rating_culture", 0))
    return p >= need and c >= need and (p + c) // 2 >= avg_need


def oracle_advice_id(sim: SimState, col: int) -> int:
    """0x57450 advice id 1…16. City-only rewrite to 17 is draw-only."""
    if col == 0:
        if int(getattr(sim, "rating_empire_cap", 0)):
            return 1
        if int(getattr(sim, "imperial_favor", 0)) < 80:
            return 2
        if int(getattr(sim, "province_links", 0)) == 0:
            return 3
        return 4
    if col == 1:
        if int(getattr(sim, "rating_peace_cap", 0)):
            return 5
        return 6
    if col == 2:
        if int(getattr(sim, "rating_prosperity_cap", 0)):
            return 9
        surplus = int(getattr(sim, "rating_surplus", 0))
        if surplus == 0:
            books = treasurer_estimate(sim)
            surplus = books.surplus
        if surplus < 0:
            return 10
        income = int(getattr(sim, "housing_income", 0))
        if income <= 0:
            income = int(getattr(sim, "tax_wealth", 0))
        if income < 10:
            return 11
        return 12
    if col == 3:
        if int(getattr(sim, "rating_culture_cap", 0)):
            return 13
        ent = int(getattr(sim, "cover_entertainment", 0))
        temple = int(getattr(sim, "cover_temple", 0))
        svc = int(getattr(sim, "cover_services", 0))
        if ent <= temple and ent <= svc:
            return 14
        if temple <= ent and temple <= svc:
            return 15
        return 16
    return 17


def oracle_advice_skip(sim: SimState, col: int) -> int:
    """0x57450 + city-only force id 17 → [31]+24. col 0…3.

    Empire / Peace stay the city-only stub. Prosperity uses surplus /
    housing_income. Culture uses cover mins [0x102580/56C/54C].
    Audio still uses the live id (B02…B15) even when text is +24.
    """
    if col < 0 or col > 3:
        return 7
    aid = oracle_advice_id(sim, col)
    if getattr(sim, "city_only", 0) and aid < 9:
        return 24
    return aid + 7


def oracle_raw_index(aid: int) -> int | None:
    """0x135a4 EAX = 0x1f + index of live id. None for stubs / city-only 17."""
    if aid not in ORACLE_LIVE_IDS:
        return None
    return ORACLE_RAW_EAX0 + ORACLE_LIVE_IDS.index(aid)


def oracle_raw_stem(aid: int) -> str:
    """Bank 0x93694: 0–29 A01–A30, 30–59 B01–B30. Advice starts at B02."""
    idx = oracle_raw_index(aid)
    if idx is None:
        return ""
    if idx < 30:
        return f"A{idx + 1:02d}"
    if idx < 60:
        return f"B{idx - 29:02d}"
    return f"C{idx - 59:02d}"


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


def labor_slider_short(sim: SimState) -> bool:
    """True when a user-adjustable PLEBS row has assigned < need.

    Construction locked at 20/20 is not a shortage. Provincial / unused
    rows (Need N/A) are ignored even if leftover SAV bytes look short.
    """
    asg = list(getattr(sim, "labor_assigned", None) or [0] * LABOR_ROWS)
    need = list(getattr(sim, "labor_need", None) or [0] * LABOR_ROWS)
    while len(asg) < LABOR_ROWS:
        asg.append(0)
    while len(need) < LABOR_ROWS:
        need.append(0)
    return any(
        not labor_row_staffed(asg[i], need[i]) for i in LABOR_SLIDER_ROWS
    )


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


def load_oracle_scene(game: Path) -> Image.Image | None:
    """RAT_FRON.PL8 — 640×480 city / mountains. Palette RAT_BACK.256."""
    try:
        from app import assets

        frames, _path = assets.load_pl8_frames(game, "RAT_FRON.PL8")
        if frames:
            return frames[0].convert("RGBA")
    except (OSError, ValueError, FileNotFoundError):
        return None
    return None


def load_oracle_column(game: Path) -> Image.Image | None:
    """RAT_BACK.PL8 sprite 0 — 96×337 marble column (xy 321,15 in the sheet)."""
    try:
        from app import assets

        packed = assets.load_pl8_sprites_xy(game, "RAT_BACK.PL8")
        if packed:
            return packed[0][0].convert("RGBA")
    except (OSError, ValueError, FileNotFoundError):
        return None
    return None


def load_empire_map(game: Path) -> Image.Image | None:
    """EMPIRE.PL8 — 640×480 parchment map. Palette EMPIRE.256."""
    try:
        from app import assets

        frames, _path = assets.load_pl8_frames(game, "EMPIRE.PL8")
        if frames:
            return frames[0].convert("RGBA")
    except (OSError, ValueError, FileNotFoundError):
        return None
    return None


def load_empire_parts(game: Path) -> list:
    """E_PARTS2.PL8 — 44 province stamps (xy) + 3 caption plates."""
    try:
        from app import assets

        packed = assets.load_pl8_sprites_xy(game, "E_PARTS2.PL8")
        return [(im.convert("RGBA"), int(x), int(y)) for im, x, y in packed]
    except (OSError, ValueError, FileNotFoundError):
        return []


def load_governor_name(game: Path | None) -> str:
    """CAESAR2.INF offset 24, 20 bytes — not a SavChunk (forum_qa.md)."""
    if game is None:
        return "Governor"
    try:
        from app.config import find_file

        path = find_file(game, "CAESAR2.INF")
        if path is None:
            return "Governor"
        raw = path.read_bytes()
    except OSError:
        return "Governor"
    text = raw.decode("latin-1", errors="replace")
    best = ""
    cur = []
    for ch in text:
        if ch.isprintable() and ch != "\x00" and (ch.isalnum() or ch in " .'-"):
            cur.append(ch)
            continue
        cand = "".join(cur).strip()
        if len(cand) > len(best) and any(c.isalpha() for c in cand):
            best = cand
        cur = []
    cand = "".join(cur).strip()
    if len(cand) > len(best) and any(c.isalpha() for c in cand):
        best = cand
    return best or "Governor"


def open_forum(sim: SimState, tiles: bytearray, game: Path | None = None) -> ForumState:
    """forum_view_setup — idle CLEAR FORUM (kind 0), crowd + 12 buttons."""
    state = ForumState(kind=KIND_CHROME, labor=labor_from_sim(sim))
    if game is not None:
        state.bg = load_forum_art(game)
        state.bits = load_forum_bits(game)
        state.oracle_back = load_oracle_scene(game)
        state.oracle_column = load_oracle_column(game)
        state.empire_map = load_empire_map(game)
        state.empire_parts = load_empire_parts(game)
        if not getattr(sim, "governor_name", ""):
            sim.governor_name = load_governor_name(game)
    sync_labor(state.labor, tiles, sim)
    return state


def forum_layout(win_w: int, win_h: int, *, top: int = 0) -> tuple[int, int, int]:
    """Integer nearest-neighbor scale + centered origin for the 640×480 FB.

    ``scale = max(1, min(well_w // 640, well_h // 480))``. ``top`` is the
    File-menu strip (city ``TOP_BAR_H``) so Oracle/Empire are not squashed
    into the chrome independently. Use canvas pixels, not the toplevel
    HWND (title bar made the FB aspect drift).
    """
    w = max(1, int(win_w))
    inset = max(0, int(top))
    h = max(1, int(win_h) - inset)
    scale = max(1, min(w // FORUM_NATIVE_W, h // FORUM_NATIVE_H))
    ox = (w - FORUM_NATIVE_W * scale) // 2
    oy = inset + (h - FORUM_NATIVE_H * scale) // 2
    return scale, ox, oy


def forum_to_native(mx: int, my: int, win_w: int, win_h: int) -> tuple[int, int]:
    """Window pixel → native 640×480 Forum space (same layout as blit)."""
    scale, ox, oy = forum_layout(win_w, win_h)
    return (int(mx) - ox) // scale, (int(my) - oy) // scale


def compose_forum_native(state: ForumState, sim: SimState, *, eng=None) -> Image.Image:
    """Always 640×480. Never a window-sized Oracle/Empire bitmap."""
    native = _blit_forum_native(state, sim, eng=eng)
    if native.size == (FORUM_NATIVE_W, FORUM_NATIVE_H):
        return native.convert("RGB")
    return _fit_forum_native(native, (*FORUM_LETTERBOX, 255)).convert("RGB")


def scale_forum_fb(
    native: Image.Image, dest_w: int, dest_h: int
) -> tuple[Image.Image, int, int, int]:
    """Integer-scale 640×480. Returns (fb, scale, ox, oy) — never dest-sized 16:9."""
    fb = native.convert("RGB")
    if fb.size != (FORUM_NATIVE_W, FORUM_NATIVE_H):
        fb = _fit_forum_native(fb, (*FORUM_LETTERBOX, 255)).convert("RGB")
    scale, ox, oy = forum_layout(dest_w, dest_h)
    if scale > 1:
        fb = fb.resize(
            (FORUM_NATIVE_W * scale, FORUM_NATIVE_H * scale),
            Image.Resampling.NEAREST,
        )
    return fb, scale, ox, oy


def letterbox_forum_fb(native: Image.Image, dest_w: int, dest_h: int) -> Image.Image:
    """Integer nearest-neighbor scale of 640×480, centered in dest.

    Shared by Oracle and Empire. Never ``resize((dest_w, dest_h))``.
    """
    w = max(1, int(dest_w))
    h = max(1, int(dest_h))
    fb, _scale, ox, oy = scale_forum_fb(native, w, h)
    if fb.size == (w, h) and ox == 0 and oy == 0:
        return fb
    canvas = Image.new("RGB", (w, h), FORUM_LETTERBOX)
    canvas.paste(fb, (ox, oy))
    return canvas


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


def _serif_font(size: int) -> ImageFont.ImageFont:
    """C2 Treasurer used a small serif, not the host bitmap / Julius UI."""
    got = _SERIF_CACHE.get(size)
    if got is not None:
        return got
    windir = Path(r"C:\Windows\Fonts")
    names = ("times.ttf", "timesi.ttf", "georgia.ttf", "cambria.ttc")
    if size >= 18:
        names = ("timesbd.ttf", "times.ttf", "georgiab.ttf", "georgia.ttf")
    for name in names:
        path = windir / name
        if path.is_file():
            font = ImageFont.truetype(str(path), size)
            _SERIF_CACHE[size] = font
            return font
    font = ImageFont.load_default()
    _SERIF_CACHE[size] = font
    return font


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
    y = TAX_HIT_Y + row * TAX_ROW_H
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
    # Oracle / Empire Map are full screens (no 4×3 chrome).
    if state.kind == KIND_ORACLE:
        col = _oracle_column(mx, my)
        if col is not None:
            state.oracle_advice = col
            state.oracle_sfx = oracle_raw_stem(oracle_advice_id(sim, col))
            return ""
        return ""
    if state.kind == KIND_EMPIRE:
        if state.empire_pick and _in_rect(mx, my, empire_close_rect()):
            state.empire_pick = None
            state.empire_flavor = ""
            state.empire_sfx = ""
            return ""
        skip = _empire_hit(state, mx, my)
        if skip is not None:
            state.empire_pick = skip
            state.empire_flavor = empire_flavor_text(skip)
            state.empire_sfx = empire_raw_stem(skip)
        else:
            state.empire_pick = None
            state.empire_flavor = ""
            state.empire_sfx = ""
        return ""

    hit = button_at(mx, my)
    if hit is not None:
        skip = _BUTTON_SKIP[hit]
        kind = _BUTTON_KIND[hit]
        label = _eng(eng, 28, skip, _BUTTON_FALLBACK[hit])
        if kind == KIND_EXIT:
            return "exit"
        _clear_forum_focus(state)
        if hit == 5 or kind == KIND_CHROME:
            state.kind = KIND_CHROME
            return label
        if kind == KIND_HELP:
            state.kind = KIND_CHROME if state.kind == KIND_HELP else KIND_HELP
            return label
        if kind in _ADVISOR_KINDS:
            if state.kind == kind:
                state.kind = KIND_CHROME
            else:
                state.kind = kind
            return label
        state.kind = KIND_CHROME
        return label

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

    if state.kind == KIND_SCRIBE:
        action = hit_scribe(mx, my)
        if action:
            apply_scribe_hit(state, action)
            return ""
        return ""

    if state.kind == KIND_PERSONAL:
        action = hit_personal(mx, my)
        if action:
            apply_personal_hit(action, state, sim)
            return ""
        return ""

    if state.kind == KIND_ROME:
        action = hit_rome(mx, my)
        if action:
            apply_rome_hit(action, state, sim)
            return ""
        return ""

    if state.kind == KIND_CENTURION:
        action = hit_centurion(mx, my)
        if action:
            apply_centurion_hit(action, sim)
            return ""
        return ""
    return ""


def _scribe_year_rects() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 56
    return ((_PANEL_X + 10, y, 16, 16), (_PANEL_X + 30, y, 16, 16))


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
    """0x3d875: x = 10 + esi*160, y=0x164, 140×33. Average is not a hit."""
    if not (ORACLE_HIT_Y <= my < ORACLE_HIT_Y + ORACLE_HIT_H):
        return None
    for col in range(4):
        x = ORACLE_HIT_X0 + col * ORACLE_COL_STRIDE
        if x <= mx < x + ORACLE_HIT_W:
            return col
    return None


def blit_forum(
    frame_size: tuple[int, int],
    state: ForumState,
    sim: SimState,
    *,
    eng=None,
) -> Image.Image:
    """Compose native 640×480 Forum, then integer-upscale into ``frame_size``."""
    w, h = frame_size
    return letterbox_forum_fb(compose_forum_native(state, sim, eng=eng), w, h)


def _blit_forum_native(state: ForumState, sim: SimState, *, eng=None) -> Image.Image:
    """Paint the C2 Forum at 640×480 (panel, sliders, 4×3 chrome)."""
    if state.kind == KIND_ORACLE:
        return _blit_oracle_native(state, sim, eng=eng)
    if state.kind == KIND_EMPIRE:
        return _blit_empire_native(state, sim, eng=eng)
    if state.bg is not None:
        out = state.bg.resize((FORUM_NATIVE_W, FORUM_NATIVE_H), Image.Resampling.NEAREST)
    else:
        out = Image.new("RGB", (FORUM_NATIVE_W, FORUM_NATIVE_H), (28, 24, 20))
    out = out.convert("RGBA")
    draw = ImageDraw.Draw(out)
    font = _font()
    if state.kind in (KIND_PLEBS, KIND_TREASURER, KIND_SCRIBE):
        if state.kind == KIND_TREASURER:
            draw.rectangle(
                (_PANEL_X, _PANEL_Y, _PANEL_X + _PANEL_W - 1, _PANEL_Y + _PANEL_H - 1),
                fill=_TREAS_FILL,
                outline=_TREAS_EDGE,
            )
            _draw_treasurer(draw, sim, eng)
        else:
            draw.rectangle(
                (_PANEL_X, _PANEL_Y, _PANEL_X + _PANEL_W - 1, _PANEL_Y + _PANEL_H - 1),
                fill=(8, 20, 18, 230),
                outline=(200, 180, 90, 255),
            )
            title = (
                _eng(eng, 36, 0, "Plebeian Tribune") if state.kind == KIND_PLEBS else
                _eng(eng, 32, 0, "Your Scribe")
            )
            draw.text((_PANEL_X + 10, _PANEL_Y + 8), title[:48], fill=(255, 228, 160, 255), font=font)
            if state.kind == KIND_PLEBS:
                _draw_plebs(draw, font, state.labor, eng)
            elif state.kind == KIND_SCRIBE:
                _draw_scribe(draw, font, sim, state.scribe_years, eng)
    elif state.kind == KIND_MERCHANT:
        _draw_merchant(draw, font, sim, eng)
    elif state.kind == KIND_CENTURION:
        _draw_centurion(draw, font, sim, eng)
    elif state.kind == KIND_ROME:
        _draw_rome(draw, font, state, sim, eng)
    elif state.kind == KIND_PERSONAL:
        _draw_personal(draw, font, state, sim, eng)
    for i, skip in enumerate(_BUTTON_SKIP):
        x, y, bw, bh = button_rect(i)
        kind = _BUTTON_KIND[i]
        lit = (state.kind == KIND_CHROME and i == 5) or (
            kind == state.kind and kind not in (KIND_CHROME, KIND_EXIT)
        )
        fill = (160, 40, 30, 240) if lit else (40, 70, 50, 230)
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


def _oracle_col_top(rating: int) -> int:
    """0x5eaa7: dest Y = 0x12c − rating*3."""
    return ORACLE_COL_Y0 - ORACLE_COL_SCALE * int(rating)


def _oracle_ratings(sim: SimState) -> tuple[int, int, int, int, int]:
    return (
        int(getattr(sim, "rating_empire", 0)),
        int(getattr(sim, "rating_peace", 0)),
        int(getattr(sim, "rating_prosperity", 0)),
        int(getattr(sim, "rating_culture", 0)),
        int(getattr(sim, "rating_avg", 0)),
    )


def _wrap_oracle_text(text: str, width: int = 72) -> list[str]:
    words = text.replace("\n", " ").split()
    if not words:
        return []
    lines: list[str] = []
    cur = words[0]
    for word in words[1:]:
        trial = f"{cur} {word}"
        if len(trial) <= width:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def _lock_oracle_column(column: Image.Image) -> Image.Image:
    """RAT_BACK[0] stays 96×337. Never stretch — that made chubby columns."""
    col = column.convert("RGBA")
    if col.size == (ORACLE_COL_W, ORACLE_COL_H):
        return col
    sx, sy = col.size
    if sx >= ORACLE_COL_W and sy >= ORACLE_COL_H and sx % ORACLE_COL_W == 0 and sy % ORACLE_COL_H == 0:
        kx, ky = sx // ORACLE_COL_W, sy // ORACLE_COL_H
        if kx == ky:
            return col.resize((ORACLE_COL_W, ORACLE_COL_H), Image.Resampling.NEAREST)
    out = Image.new("RGBA", (ORACLE_COL_W, ORACLE_COL_H), (0, 0, 0, 0))
    fitted = col.copy()
    fitted.thumbnail((ORACLE_COL_W, ORACLE_COL_H), Image.Resampling.NEAREST)
    out.paste(fitted, ((ORACLE_COL_W - fitted.width) // 2, 0), fitted)
    return out


def _blit_oracle_columns(out: Image.Image, column: Image.Image | None, ratings: tuple[int, ...]) -> None:
    """0x5eb1d: x = 32 + esi*160, y = clamp(300−3*rating, 0, 0x126). Sprite 0."""
    if column is None:
        draw = ImageDraw.Draw(out)
        for i, val in enumerate(ratings[:4]):
            y = max(0, min(0x126, _oracle_col_top(val)))
            x = 0x20 + i * ORACLE_COL_STRIDE
            draw.rectangle((x + 28, y + 12, x + 68, 340), fill=(196, 168, 96, 230))
            draw.rectangle((x + 16, y, x + 80, y + 18), fill=(210, 184, 110, 230))
        return
    col = _lock_oracle_column(column)
    for i, val in enumerate(ratings[:4]):
        x = 0x20 + i * ORACLE_COL_STRIDE
        y = max(0, min(0x126, _oracle_col_top(val)))
        out.paste(col, (x, y), col)


def _blit_oracle_native(state: ForumState, sim: SimState, *, eng=None) -> Image.Image:
    """Full-screen Your Ratings — no 4×3 chrome. Right-click returns."""
    if state.oracle_back is not None:
        out = _fit_forum_native(state.oracle_back, (40, 56, 72, 255))
    elif state.bg is not None:
        out = _fit_forum_native(state.bg, (40, 56, 72, 255))
    else:
        out = Image.new("RGBA", (FORUM_NATIVE_W, FORUM_NATIVE_H), (40, 56, 72, 255))
    e, p, pr, c, avg = _oracle_ratings(sim)
    _blit_oracle_columns(out, state.oracle_column, (e, p, pr, c))
    draw = ImageDraw.Draw(out)
    font = _serif_font(14)
    small = _serif_font(13)
    names = (
        _eng(eng, 31, 1, "Empire"),
        _eng(eng, 31, 2, "Peace"),
        _eng(eng, 31, 3, "Prosperity"),
        _eng(eng, 31, 4, "Culture"),
    )
    vals = (e, p, pr, c)
    need_ind, need_avg = rating_need(sim)
    city_only = bool(getattr(sim, "city_only", 0))
    need_tok = _eng(eng, 31, 6, "(Need")
    for i, (name, val) in enumerate(zip(names, vals)):
        draw.text((ORACLE_NAME_X[i], ORACLE_NAME_Y), f"{name} {val}%", fill=ORACLE_INK, font=font)
        show_need = (not city_only) or i >= 2
        if show_need:
            draw.text(
                (ORACLE_NEED_X[i], ORACLE_NEED_Y),
                f"{need_tok} {need_ind}%)",
                fill=ORACLE_INK,
                font=small,
            )
    avg_lab = _eng(eng, 31, 5, "Average rating: ")
    draw.text(
        (ORACLE_AVG_X, ORACLE_AVG_Y),
        f"{avg_lab}{avg}% {need_tok} {need_avg}%)",
        fill=ORACLE_INK,
        font=font,
    )
    if state.oracle_advice is None:
        prompt = _eng(
            eng, 31, 7,
            "Select any of the ratings above to receive advice on improving them.",
        )
    else:
        skip = oracle_advice_skip(sim, state.oracle_advice)
        fallback = (
            "You cannot get promoted when playing in city-only mode. "
            "Get ADVICE on your city's Prosperity or Culture ratings by clicking on their boxes. "
            if skip == 24 else ""
        )
        prompt = _eng(eng, 31, skip, fallback)
    y = ORACLE_PROMPT_Y
    for line in _wrap_oracle_text(prompt, 74)[:4]:
        draw.text((ORACLE_PROMPT_X, y), line, fill=ORACLE_INK, font=small)
        y += 14
    draw.text(
        (ORACLE_BACK_X, ORACLE_BACK_Y),
        _eng(eng, 33, 3, "Right Click to Return to Forum"),
        fill=ORACLE_INK,
        font=small,
    )
    return out.convert("RGB")


def _year_label(year_raw: int) -> str:
    if year_raw < 0:
        return f"{-int(year_raw)} BC"
    return f"{int(year_raw)} AD"


def _draw_scribe(draw, font, sim: SimState, years: int, eng) -> None:
    """HISTORY 2×2 charts — pop / funds / pop tax / industry tax."""
    recs = history_window(parse_history(getattr(sim, "history", None)), years)
    window = 10 if years not in SCRIBE_WINDOWS else int(years)
    look = _eng(eng, 32, 5, "Look at records")
    last = _eng(eng, 32, 6, "for the last")
    yrs = _eng(eng, 32, 7, "years.")
    to = _eng(eng, 32, 8, "to")
    if recs:
        span = f"{_year_label(recs[0][4])} {to} {_year_label(recs[-1][4])}"
    else:
        y0 = int(getattr(sim, "year_raw", 0))
        span = f"{_year_label(y0)} {to} {_year_label(y0)}"
    draw.text((_PANEL_X + 10, _PANEL_Y + 28), look, fill=(200, 210, 190), font=font)
    draw.text((_PANEL_X + 10, _PANEL_Y + 42), last, fill=(200, 210, 190), font=font)
    minus, plus = _scribe_year_rects()
    draw.rectangle((minus[0], minus[1], minus[0] + 15, minus[1] + 15), outline=(200, 180, 90))
    draw.text((minus[0] + 2, minus[1] + 1), "<", fill=(255, 228, 160), font=font)
    draw.rectangle((plus[0], plus[1], plus[0] + 15, plus[1] + 15), outline=(200, 180, 90))
    draw.text((plus[0] + 4, plus[1] + 1), ">", fill=(255, 228, 160), font=font)
    draw.text((_PANEL_X + 10, _PANEL_Y + 74), f"{window} {yrs}", fill=(200, 210, 190), font=font)
    draw.text((_PANEL_X + 10, _PANEL_Y + 88), span, fill=(200, 210, 190), font=font)

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
    colors = ((80, 200, 90), (230, 160, 70), (80, 200, 90), (230, 160, 70))
    gw, gh = 200, 70
    gx0, gy0 = _PANEL_X + 200, _PANEL_Y + 28
    for i, (lab, scale, vals, col) in enumerate(zip(labels, SCRIBE_SCALES, series, colors)):
        col_i, row_i = i % 2, i // 2
        x = gx0 + col_i * (gw + 16)
        y = gy0 + row_i * (gh + 28)
        bx, by, bw, bh = x, y, gw, 48
        draw.rectangle((bx, by, bx + bw - 1, by + bh - 1), outline=(180, 170, 140), fill=(18, 22, 28, 220))
        n = max(window, 1)
        slot_w = max(1, bw // n)
        for k, val in enumerate(vals):
            frac = max(0.0, min(1.0, int(val) / scale)) if scale else 0.0
            bar_h = max(1, int((bh - 2) * frac)) if val else 0
            x0 = bx + (n - len(vals) + k) * slot_w
            if bar_h:
                draw.rectangle(
                    (x0 + 1, by + bh - 1 - bar_h, x0 + slot_w - 2, by + bh - 2),
                    fill=col,
                )
        draw.text((x, y + bh + 2), f"{lab}{scale}", fill=(255, 228, 160), font=font)


def _ink() -> tuple[int, int, int, int]:
    return (230, 228, 210, 255)


def _clear_forum_focus(state: ForumState) -> None:
    state.oracle_advice = None
    state.oracle_sfx = ""
    state.empire_pick = None
    state.empire_flavor = ""
    state.empire_sfx = ""
    state.field_focus = ""
    state.field_edit = ""


def _i(sim: SimState, name: str, default: int = 0) -> int:
    return int(getattr(sim, name, default) or 0)


def promotions_left(rank: int) -> int:
    """0x555ce: rank 0…9; Caesar (10) needs 0 more."""
    return max(0, RANK_CAESAR - max(0, int(rank)))


def favor_quote_skip(favor: int) -> int:
    """[37]+3…+14. Favor 0–100 → 12 bands."""
    band = max(0, min(FAVOR_QUOTES - 1, int(favor) * FAVOR_QUOTES // 101))
    return 3 + band


def empire_circa_title(year_raw: int, eng=None) -> str:
    """[33]+2 + abs(year) + BC/AD. ``_eng`` rstrip ate the trailing space."""
    prefix = _eng(eng, 33, 2, "Roman empire circa ")
    return f"{prefix.rstrip()} {_year_label(year_raw)}"


def empire_raw_stem(skip: int) -> str:
    """0x5C621 → ``0x135A4(skip+0x3A)``. Table 0x93694 is ``cNN.raw`` inline."""
    n = int(skip)
    if n <= 1:
        return "B30"
    if 2 <= n <= 44:
        return f"C{n - 1:02d}"
    return ""


def empire_status_text(eng=None) -> str:
    """City Only: every map hit is [47]+9. No career conquer year."""
    return _eng(eng, 47, 9, "As yet unconquered.")


def empire_close_rect() -> tuple[int, int, int, int]:
    """0x2ddad 24×24 X on the 0x59ff8 frame. Native 640×480."""
    return (EMPIRE_CLOSE_X, EMPIRE_CLOSE_Y, EMPIRE_CLOSE_W, EMPIRE_CLOSE_H)


def empire_flavor_text(skip: int, game: Path | None = None) -> str:
    """HELP.ENG topic skip+1148 (0x57B48). Body is the dialog output."""
    n = int(skip)
    fallback = _EMPIRE_FLAVOR_FALLBACK.get(n, "")
    if game is None:
        try:
            from app.config import resolve_game_dir

            game, _how = resolve_game_dir()
        except (OSError, ValueError, FileNotFoundError):
            return fallback
    try:
        from app.config import find_file

        path = find_file(game, "HELP.ENG") if game is not None else None
        if path is None:
            return fallback
        data = path.read_bytes()
    except OSError:
        return fallback
    if not data.startswith(_HELP_MAGIC):
        return fallback
    topic = n + EMPIRE_HELP_TOPIC0
    pos = _HELP_TABLE + topic * _HELP_REC
    if pos + 4 > len(data):
        return fallback
    off = struct.unpack_from("<I", data, pos)[0]
    if off <= 0 or off >= len(data):
        return fallback
    end = data.find(b"\x00", off)
    if end < 0:
        end = min(len(data), off + 400)
    text = data[off:end].decode("latin-1", errors="replace").replace("\r", " ")
    return " ".join(text.split()) or fallback


_EMPIRE_FLAVOR_FALLBACK = {
    1: "All roads lead here...",
    17: (
        "This island is small, yet rich in farmland and minerals.  "
        "However, the populace may be troublesome."
    ),
    32: (
        "This northern province contains a large barbarian presence, "
        "but its resources seem worth the danger."
    ),
    34: (
        "Resources are scarce on this small island, and the people look "
        "to be difficult to manage.  Maintain vigilance."
    ),
    39: (
        "We've beaten back those upstart barbarians, and these lands are "
        "bereft of minerals.  Perhaps it's best to leave sleeping dogs lie?"
    ),
}


def industry_rows(sim: SimState) -> list[tuple[int, str, int, int, int, int]]:
    """City Only: local goods with store / factories / produced. No invented trade."""
    from app.city_paint import GOODS_COUNT, GOODS_SUPPLIED, goods_i32

    goods = getattr(sim, "goods", None)
    rows: list[tuple[int, str, int, int, int, int]] = []
    for i in range(GOODS_COUNT):
        store = goods_i32(goods, i, GOODS_STORE)
        factories = goods_i32(goods, i, GOODS_FACTORIES)
        produced = goods_i32(goods, i, GOODS_PRODUCED)
        supplied = goods_i32(goods, i, GOODS_SUPPLIED)
        if not (store or factories or produced):
            continue
        name = GOODS_LABELS[i] if i < len(GOODS_LABELS) else f"good {i}"
        rows.append((i, name, produced, store, factories, supplied))
        if len(rows) >= 8:
            break
    return rows


def _box(draw, rect: tuple[int, int, int, int], text: str, font, *, fill=False) -> None:
    x, y, w, h = rect
    draw.rectangle(
        (x, y, x + w - 1, y + h - 1),
        outline=(200, 190, 140),
        fill=(20, 28, 40, 230) if fill else None,
    )
    if text:
        draw.text((x + 3, y + 1), text[:8], fill=_ink(), font=font)


def _donate_rect() -> tuple[int, int, int, int]:
    return (_PANEL_X + 220, _PANEL_Y + 86, 28, 16)


def _gift_rect() -> tuple[int, int, int, int]:
    return (_PANEL_X + 280, _PANEL_Y + 70, 28, 16)


def _salary_rects() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 64
    return ((_PANEL_X + 200, y, 16, 16), (_PANEL_X + 218, y, 16, 16))


def _wage_rects() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 28
    return ((_PANEL_X + 160, y, 16, 16), (_PANEL_X + 178, y, 16, 16))


def _conscript_rects() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 46
    return ((_PANEL_X + 160, y, 16, 16), (_PANEL_X + 178, y, 16, 16))


def _aux_rects() -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    y = _PANEL_Y + 100
    return ((_PANEL_X + 160, y, 16, 16), (_PANEL_X + 178, y, 16, 16))


def hit_personal(mx: int, my: int) -> str | None:
    up, down = _salary_rects()
    if _in_rect(mx, my, up):
        return "salary+"
    if _in_rect(mx, my, down):
        return "salary-"
    if _in_rect(mx, my, _donate_rect()):
        return "donate"
    return None


def apply_personal_hit(action: str, state: ForumState, sim: SimState) -> None:
    if action == "salary+":
        sim.salary = min(SALARY_MAX, _i(sim, "salary") + SALARY_STEP)
    elif action == "salary-":
        sim.salary = max(0, _i(sim, "salary") - SALARY_STEP)
    elif action == "donate":
        state.field_focus = "donate"
        state.field_edit = str(_i(sim, "donate_amount")) if _i(sim, "donate_amount") else ""


def hit_rome(mx: int, my: int) -> str | None:
    if _in_rect(mx, my, _gift_rect()):
        return "gift"
    return None


def apply_rome_hit(action: str, state: ForumState, sim: SimState) -> None:
    if action == "gift":
        state.field_focus = "gift"
        state.field_edit = str(_i(sim, "gift_amount")) if _i(sim, "gift_amount") else ""


def hit_centurion(mx: int, my: int) -> str | None:
    for name, rects in (
        ("wage", _wage_rects()),
        ("conscript", _conscript_rects()),
        ("aux", _aux_rects()),
    ):
        up, down = rects
        if _in_rect(mx, my, up):
            return f"{name}+"
        if _in_rect(mx, my, down):
            return f"{name}-"
    return None


def apply_centurion_hit(action: str, sim: SimState) -> None:
    if action == "wage+":
        sim.legion_wages = min(WAGE_MAX, _i(sim, "legion_wages") + WAGE_STEP)
    elif action == "wage-":
        sim.legion_wages = max(0, _i(sim, "legion_wages") - WAGE_STEP)
    elif action == "conscript+":
        sim.conscription = min(CONSCRIPT_MAX, _i(sim, "conscription") + 1)
    elif action == "conscript-":
        sim.conscription = max(0, _i(sim, "conscription") - 1)
    elif action == "aux+":
        sim.auxiliaries = _i(sim, "auxiliaries") + 1
    elif action == "aux-":
        sim.auxiliaries = max(0, _i(sim, "auxiliaries") - 1)


def type_forum_key(state: ForumState, sim: SimState, key: str, char: str) -> bool:
    """Digits into donate / gift. True if consumed."""
    if state.kind not in (KIND_PERSONAL, KIND_ROME) or not state.field_focus:
        return False
    if key in {"escape"}:
        state.field_focus = ""
        state.field_edit = ""
        return True
    if key in {"backspace"}:
        state.field_edit = state.field_edit[:-1]
    elif key in {"return", "kp_enter"}:
        raw = int(state.field_edit or "0")
        if state.field_focus == "donate":
            sim.donate_amount = max(0, raw)
        else:
            sim.gift_amount = max(0, raw)
        state.field_focus = ""
        return True
    elif char.isdigit() and len(state.field_edit) < 7:
        state.field_edit += char
    else:
        return False
    raw = int(state.field_edit or "0")
    if state.field_focus == "donate":
        sim.donate_amount = raw
    else:
        sim.gift_amount = raw
    return True


def _empire_hit(state: ForumState, mx: int, my: int) -> int | None:
    """0x33C3D: dest (0x95cbb) AABB in 640×480. First ecx 0…0x2B wins.

    ``state`` is unused (parts are stamps, not the hit table). Mouse must
    already be native — ``click_forum`` maps window→FB first.
    """
    del state
    if not (0 <= mx < FORUM_NATIVE_W and 0 <= my < FORUM_NATIVE_H):
        return None
    for i, (x, y) in enumerate(EMPIRE_HOTSPOTS):
        if x <= mx < x + EMPIRE_HIT_W and y <= my < y + EMPIRE_HIT_H:
            return i + 1
    return None


def _draw_personal(draw, font, state: ForumState, sim: SimState, eng) -> None:
    name = getattr(sim, "governor_name", "") or "Governor"
    rank = max(0, min(10, _i(sim, "rank")))
    title = f"{_eng(eng, 30, 0, 'The career of ')}{name}"
    rank_s = _eng(eng, 7, rank, "Citizen")
    draw.text((_PANEL_X + 8, _PANEL_Y + 8), title[:42], fill=_ink(), font=font)
    draw.text((_PANEL_X + 400, _PANEL_Y + 8), rank_s, fill=_ink(), font=font)
    need = _eng(eng, 76, 17, "You need")
    promo = _eng(eng, 76, 18, "promotions to")
    emp = _eng(eng, 76, 19, "become Emperor.")
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 36),
        f"{need} {promotions_left(rank)} {promo} {emp}",
        fill=_ink(),
        font=font,
    )
    sal = _i(sim, "salary")
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 64),
        f"{_eng(eng, 30, 2, 'Monthly salary of')} {sal} Dn",
        fill=_ink(),
        font=font,
    )
    up, down = _salary_rects()
    _box(draw, up, "^", font)
    _box(draw, down, "v", font)
    draw.text(
        (_PANEL_X + 280, _PANEL_Y + 64),
        f"{_eng(eng, 30, 1, 'You have savings of')} {_i(sim, 'savings')} Dn",
        fill=_ink(),
        font=font,
    )
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 86),
        _eng(eng, 30, 3, "Donate money to the city?"),
        fill=_ink(),
        font=font,
    )
    shown = state.field_edit if state.field_focus == "donate" else str(_i(sim, "donate_amount") or "")
    _box(draw, _donate_rect(), shown or "", font, fill=state.field_focus == "donate")


def _draw_rome(draw, font, state: ForumState, sim: SimState, eng) -> None:
    draw.text((_PANEL_X + 8, _PANEL_Y + 8), _eng(eng, 37, 0, "Rome."), fill=_ink(), font=font)
    quote = _eng(eng, 37, favor_quote_skip(_i(sim, "imperial_favor")), '"He is indifferent to you."')
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 28),
        f"{_eng(eng, 37, 1, 'Imperial favor:')} {quote}",
        fill=_ink(),
        font=font,
    )
    tribute = 0 if getattr(sim, "city_only", 0) else _i(sim, "tribute")
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 46),
        f"{_eng(eng, 37, 2, 'Current annual tribute of')} {tribute} Dn.",
        fill=_ink(),
        font=font,
    )
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 64),
        _eng(eng, 37, 20, "The Emperor currently requests nothing."),
        fill=_ink(),
        font=font,
    )
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 82),
        _eng(eng, 37, 22, "Send a personal 'gift' to the Emperor"),
        fill=_ink(),
        font=font,
    )
    shown = state.field_edit if state.field_focus == "gift" else str(_i(sim, "gift_amount") or "")
    _box(draw, _gift_rect(), shown or "", font, fill=state.field_focus == "gift")
    avg = _eng(eng, 37, 27, "(Your average gift is ")
    draw.text(
        (_PANEL_X + 318, _PANEL_Y + 82),
        f"{avg}{_i(sim, 'gift_avg')} Dn)",
        fill=_ink(),
        font=font,
    )
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 100),
        f"{_eng(eng, 30, 1, 'You have savings of')} {_i(sim, 'savings')} Dn",
        fill=_ink(),
        font=font,
    )


def _draw_merchant(draw, font, sim: SimState, eng) -> None:
    draw.text((_PANEL_X + 8, _PANEL_Y + 8), _eng(eng, 35, 0, "Industry"), fill=_ink(), font=font)
    rows = industry_rows(sim)
    if not rows:
        draw.text(
            (_PANEL_X + 8, _PANEL_Y + 32),
            _eng(eng, 35, 3, "No factories in the city"),
            fill=_ink(),
            font=font,
        )
        return
    per = _eng(eng, 35, 1, "units produced/month")
    store_l = _eng(eng, 35, 2, "in storage")
    fac1 = _eng(eng, 35, 4, "factory")
    facn = _eng(eng, 35, 5, "factories")
    supp = _eng(eng, 35, 6, "supplied")
    for i, (_gid, name, produced, store, factories, supplied) in enumerate(rows):
        y = _PANEL_Y + 28 + i * 18
        fac = fac1 if factories == 1 else facn
        draw.text(
            (_PANEL_X + 8, y),
            f"{name}  {produced} {per}  {store} {store_l}  "
            f"{factories} {fac}  {supplied}% {supp}",
            fill=_ink(),
            font=font,
        )


def _draw_centurion(draw, font, sim: SimState, eng) -> None:
    draw.text((_PANEL_X + 8, _PANEL_Y + 8), _eng(eng, 34, 0, "The Legion"), fill=_ink(), font=font)
    wages = _i(sim, "legion_wages")
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 28),
        f"{_eng(eng, 34, 1, 'Monthly wages ')}{wages} Dn",
        fill=_ink(),
        font=font,
    )
    up, down = _wage_rects()
    _box(draw, up, "^", font)
    _box(draw, down, "v", font)
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 46),
        f"{_eng(eng, 34, 2, 'Conscription')} {_i(sim, 'conscription')}%",
        fill=_ink(),
        font=font,
    )
    cu, cd = _conscript_rects()
    _box(draw, cu, "^", font)
    _box(draw, cd, "v", font)
    soldiers = _i(sim, "soldiers")
    ready = _i(sim, "soldiers_ready")
    training = _i(sim, "soldiers_training")
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 64),
        f"{_eng(eng, 34, 4, 'The legion has ')}{soldiers} {_eng(eng, 34, 5, 'soldiers')}",
        fill=_ink(),
        font=font,
    )
    draw.text(
        (_PANEL_X + 8, _PANEL_Y + 80),
        f"{ready} {_eng(eng, 34, 6, 'ready')}  {training} {_eng(eng, 34, 7, 'in training.')}",
        fill=_ink(),
        font=font,
    )
    aux = _i(sim, "auxiliaries")
    if aux <= 0:
        draw.text(
            (_PANEL_X + 8, _PANEL_Y + 98),
            _eng(eng, 34, 34, "There are no auxiliaries"),
            fill=_ink(),
            font=font,
        )
    else:
        draw.text(
            (_PANEL_X + 8, _PANEL_Y + 98),
            f"{aux} {_eng(eng, 34, 31, 'auxiliaries')}  "
            f"{_eng(eng, 34, 32, 'Cost ')}0 Dn {_eng(eng, 34, 33, 'per month')}",
            fill=_ink(),
            font=font,
        )
    au, ad = _aux_rects()
    _box(draw, au, "^", font)
    _box(draw, ad, "v", font)
    draw.text((_PANEL_X + 300, _PANEL_Y + 8), _eng(eng, 44, 7, "COHORT REPORT"), fill=_ink(), font=font)
    draw.text((_PANEL_X + 300, _PANEL_Y + 24), _eng(eng, 4, 0, "Prima Cohors"), fill=_ink(), font=font)
    battle = _i(sim, "soldiers_ready")
    heavy = _i(sim, "legion_heavy")
    light = _i(sim, "legion_light")
    sling = _i(sim, "legion_sling")
    draw.text(
        (_PANEL_X + 300, _PANEL_Y + 56),
        f"{_eng(eng, 44, 8, 'We have ')}{battle} {_eng(eng, 44, 9, 'battle-ready soldiers')}",
        fill=_ink(),
        font=font,
    )
    draw.text(
        (_PANEL_X + 300, _PANEL_Y + 72),
        f"{heavy} Heavy, {light} Light, {sling} Sling, {aux} Auxiliaries",
        fill=_ink(),
        font=font,
    )
    morale = max(0, min(4, _i(sim, "legion_morale")))
    ready_i = max(0, min(4, _i(sim, "legion_readiness")))
    draw.text(
        (_PANEL_X + 300, _PANEL_Y + 88),
        _eng(eng, 34, 19 + morale, "Troop morale: EXCELLENT"),
        fill=_ink(),
        font=font,
    )
    draw.text(
        (_PANEL_X + 300, _PANEL_Y + 104),
        _eng(eng, 34, 24 + ready_i, "Readiness: EXCELLENT"),
        fill=_ink(),
        font=font,
    )
    cohorts = _i(sim, "cohorts")
    if cohorts <= 0:
        cohort_s = _eng(eng, 34, 8, "The legion has no cohorts.")
    elif cohorts == 1:
        cohort_s = _eng(eng, 34, 9, "Legion has 1 cohort.")
    else:
        cohort_s = f"{_eng(eng, 34, 10, 'Legion has')} {cohorts} {_eng(eng, 34, 11, 'cohorts.')}"
    cr = max(0, min(2, _i(sim, "cohort_rank")))
    rank_s = _eng(eng, 34, 29 + cr, "Major") if cr < 2 else _eng(eng, 34, 38, "Major")
    draw.text((_PANEL_X + 300, _PANEL_Y + 120), f"{cohort_s}  {rank_s}", fill=_ink(), font=font)


def _draw_empire_close(draw) -> None:
    """0x2ddad sprite 0x33 — 24×24 close/X on the blue frame."""
    x, y, w, h = empire_close_rect()
    draw.rectangle((x, y, x + w - 1, y + h - 1), fill=EMPIRE_TEAL_CLOSE, outline=EMPIRE_TEAL_EDGE)
    draw.rectangle((x + 1, y + 1, x + w - 2, y + h - 2), outline=(240, 230, 180, 255))
    pad = 6
    draw.line((x + pad, y + pad, x + w - pad - 1, y + h - pad - 1), fill=EMPIRE_INK, width=2)
    draw.line((x + w - pad - 1, y + pad, x + pad, y + h - pad - 1), fill=EMPIRE_INK, width=2)


def _blit_empire_native(state: ForumState, sim: SimState, *, eng=None) -> Image.Image:
    """Kind 6 — EMPIRE.PL8 full screen. No crowd, no 4×3 chrome."""
    if state.empire_map is not None:
        out = _fit_forum_native(state.empire_map, (48, 40, 28, 255))
    else:
        out = Image.new("RGBA", (FORUM_NATIVE_W, FORUM_NATIVE_H), (48, 40, 28, 255))
    for item in state.empire_parts[44:47]:
        spr, sx, sy = item
        plate = spr.convert("RGBA")
        out.paste(plate, (int(sx), int(sy)), plate)
    draw = ImageDraw.Draw(out)
    font = _serif_font(16)
    small = _serif_font(13)
    title = empire_circa_title(int(getattr(sim, "year_raw", 0)), eng)
    tw = draw.textlength(title, font=font) if hasattr(draw, "textlength") else 280
    draw.text(((FORUM_NATIVE_W - int(tw)) // 2, 18), title, fill=(16, 12, 8, 255), font=font)
    cap = _eng(eng, 33, 1, "Select province for more info")
    cw = draw.textlength(cap, font=small) if hasattr(draw, "textlength") else 240
    plate_mid = (EMPIRE_PLATE_X0 + EMPIRE_PLATE_X1) // 2
    draw.text((plate_mid - int(cw) // 2, EMPIRE_CAP_Y), cap, fill=(16, 12, 8, 255), font=small)
    foot = _eng(eng, 33, 3, "Right Click to Return to Forum")
    fw = draw.textlength(foot, font=small) if hasattr(draw, "textlength") else 260
    draw.text(((FORUM_NATIVE_W - int(fw)) // 2, EMPIRE_FOOT_Y), foot, fill=(240, 230, 200, 255), font=small)
    pick = state.empire_pick
    if pick and 1 <= pick <= len(EMPIRE_HOTSPOTS):
        name = _eng(eng, 5, pick, "Unknown Province")
        status = empire_status_text(eng)
        flavor = state.empire_flavor or empire_flavor_text(pick)
        hx, hy = EMPIRE_HOTSPOTS[pick - 1]
        draw.ellipse(
            (hx - 4, hy - 4, hx + EMPIRE_HIT_W + 4, hy + EMPIRE_HIT_H + 4),
            outline=(200, 32, 24, 255),
            width=2,
        )
        # 0x59ff8 teal chrome (EMPIRE.256[0x11]) + 0x2ddad close/X.
        panel = (
            EMPIRE_DLG_X,
            EMPIRE_DLG_Y,
            EMPIRE_DLG_X + EMPIRE_DLG_W,
            EMPIRE_DLG_Y + EMPIRE_DLG_H,
        )
        draw.rectangle(panel, fill=EMPIRE_TEAL, outline=EMPIRE_TEAL_EDGE)
        draw.text((EMPIRE_NAME_X, EMPIRE_NAME_Y), name, fill=EMPIRE_INK, font=font)
        draw.text((EMPIRE_STAT_X, EMPIRE_STAT_Y), status, fill=EMPIRE_INK_DIM, font=small)
        box = (
            EMPIRE_FLAVOR_X,
            EMPIRE_FLAVOR_Y,
            EMPIRE_FLAVOR_X + EMPIRE_FLAVOR_W,
            EMPIRE_FLAVOR_Y + EMPIRE_FLAVOR_H,
        )
        draw.rectangle(box, fill=EMPIRE_TEAL_INNER, outline=EMPIRE_TEAL_EDGE)
        fy = EMPIRE_FLAVOR_Y + 6
        for line in _wrap_oracle_text(flavor, 46)[:6]:
            draw.text((EMPIRE_FLAVOR_X + 8, fy), line, fill=EMPIRE_INK, font=small)
            fy += 14
        _draw_empire_close(draw)
    return out.convert("RGB")


def _prior_year_raw(year_raw: int) -> int:
    """Year on the ACCOUNTS header — the year that just closed. No year 0."""
    y = int(year_raw)
    if y == 1:
        return -1
    if y == 0:
        return -1
    return y - 1


def _surplus_phrase(amount: int, eng) -> str:
    word = _eng(eng, 28, 21, "surplus") if int(amount) >= 0 else _eng(eng, 28, 20, "loss")
    return f"{abs(int(amount))} Dn {word}"


def treasurer_column_head(year_raw: int, accounts: bool, amount: int, eng) -> str:
    """`124 BC ACCOUNTS  54 Dn loss` / `123 BC ESTIMATE  813 Dn surplus`."""
    title = _eng(eng, 28, 18, "ACCOUNTS") if accounts else _eng(eng, 28, 19, "ESTIMATE")
    return f"{_year_label(year_raw)} {title}  {_surplus_phrase(amount, eng)}"


def treasurer_ledger_line(credit: bool, amount: int, skip: int, fallback: str, eng) -> str:
    """`(+) 1856 Dn   Population Tax` — C2.ENG [28]+22…28."""
    sign = _eng(eng, 28, 22, "(+)") if credit else _eng(eng, 28, 23, "(-)")
    return f"{sign} {int(amount)} Dn   {_eng(eng, 28, skip, fallback)}"


def treasurer_captions(sim: SimState, eng=None) -> dict[str, str]:
    """Pinned C2 Treasurer wording (screenshot + [28]+12…28)."""
    est = treasurer_estimate(sim)
    pop = int(getattr(sim, "population", 0))
    emp = int(getattr(sim, "employed_pct", 0))
    tribute_last = 0 if getattr(sim, "city_only", 0) else int(getattr(sim, "tribute", 0))
    year = int(getattr(sim, "year_raw", 0))
    last_amt = (
        int(getattr(sim, "pop_tax_last", 0)),
        int(getattr(sim, "ind_tax_last", 0)),
        int(getattr(sim, "construct_last", 0)),
        int(getattr(sim, "operating_last", 0)),
        tribute_last,
    )
    live_amt = (est.pop_tax, est.ind_tax, est.constructions, est.operating, est.tribute)
    rows = (
        (True, 24, "Population Tax"),
        (True, 25, "Industry Tax"),
        (False, 26, "Constructions"),
        (False, 27, "Operating Costs"),
        (False, 28, "Annual Tribute"),
    )
    av_pre = _eng(eng, 28, 17, "(av. bill")
    pop_av = ""
    if pop > 0 and est.pop_tax:
        pop_av = f"{av_pre} {est.pop_tax / pop:.2f}Dn )"
    ind_av = ""
    factories = int(getattr(sim, "factory_count", 0))
    if factories > 0 and est.ind_tax:
        ind_av = f"{av_pre} {est.ind_tax / factories:.2f}Dn )"
    return {
        "treasury": f"{_eng(eng, 28, 12, 'Treasury')} {int(sim.treasury)} Dn",
        "citizens": (
            f"{pop} {_eng(eng, 28, 13, 'Citizens')}  "
            f"{emp}% {_eng(eng, 28, 14, 'employed')}"
        ),
        "pop_tax": _eng(eng, 28, 15, "Population Tax"),
        "ind_tax": _eng(eng, 28, 16, "Industrial Tax"),
        "pop_rate": f"{int(sim.tax_rate)}%",
        "ind_rate": f"{int(getattr(sim, 'industrial_tax', 5))}%",
        "pop_av": pop_av,
        "ind_av": ind_av,
        "accounts": treasurer_column_head(
            _prior_year_raw(year), True, int(getattr(sim, "surplus_last", 0)), eng
        ),
        "estimate": treasurer_column_head(year, False, est.surplus, eng),
        "accounts_rows": tuple(
            treasurer_ledger_line(credit, n, skip, fb, eng)
            for (credit, skip, fb), n in zip(rows, last_amt)
        ),
        "estimate_rows": tuple(
            treasurer_ledger_line(credit, n, skip, fb, eng)
            for (credit, skip, fb), n in zip(rows, live_amt)
        ),
    }


def _arrow_box(draw, rect: tuple[int, int, int, int], *, up: bool) -> None:
    x, y, w, h = rect
    draw.rectangle((x, y, x + w - 1, y + h - 1), outline=_TREAS_EDGE, fill=(18, 32, 58, 240))
    cx, cy = x + w // 2, y + h // 2
    if up:
        draw.polygon(((cx, y + 2), (x + 2, y + h - 3), (x + w - 3, y + h - 3)), fill=_TREAS_HEAD)
    else:
        draw.polygon(((cx, y + h - 3), (x + 2, y + 2), (x + w - 3, y + 2)), fill=_TREAS_HEAD)


def _draw_tax_row(draw, font, row: int, label: str, value: int, av: str) -> None:
    """Label + up/down pair + `6%` + `(av. bill 0.89Dn )` — not a Julius dial."""
    plus, minus = _tax_rects(row)
    y = plus[1]
    draw.text((TAX_LABEL_X, y + 1), label, fill=_TREAS_INK, font=font)
    _arrow_box(draw, plus, up=True)
    _arrow_box(draw, minus, up=False)
    draw.text((TAX_RATE_X, y + 1), f"{int(value)}%", fill=_TREAS_HEAD, font=font)
    if av:
        draw.text((TAX_AV_X, y + 1), av, fill=_TREAS_INK, font=font)


def _draw_ledger_column(draw, font, x: int, y0: int, head: str, rows: tuple[str, ...]) -> None:
    draw.text((x, y0), head, fill=_TREAS_HEAD, font=font)
    for i, line in enumerate(rows):
        draw.text((x, y0 + 18 + i * 16), line, fill=_TREAS_INK, font=font)


def _draw_treasurer(draw, sim: SimState, eng) -> None:
    """Original C2 Treasurer: stats left, tax rows right, ACCOUNTS | ESTIMATE."""
    caps = treasurer_captions(sim, eng)
    title = _serif_font(18)
    body = _serif_font(13)
    draw.text((_PANEL_X + 12, _PANEL_Y + 10), caps["treasury"], fill=_TREAS_HEAD, font=title)
    draw.text((_PANEL_X + 12, _PANEL_Y + 34), caps["citizens"], fill=_TREAS_INK, font=body)
    _draw_tax_row(draw, body, 0, caps["pop_tax"], int(sim.tax_rate), caps["pop_av"])
    _draw_tax_row(
        draw, body, 1,
        caps["ind_tax"],
        int(getattr(sim, "industrial_tax", 5)),
        caps["ind_av"],
    )
    mid = _PANEL_X + _PANEL_W // 2
    rule_y = _PANEL_Y + 78
    draw.line(
        (_PANEL_X + 8, rule_y, _PANEL_X + _PANEL_W - 9, rule_y),
        fill=_TREAS_RULE,
    )
    draw.line(
        (mid, rule_y + 4, mid, _PANEL_Y + _PANEL_H - 12),
        fill=_TREAS_RULE,
    )
    y0 = rule_y + 8
    _draw_ledger_column(draw, body, _PANEL_X + 12, y0, caps["accounts"], caps["accounts_rows"])
    _draw_ledger_column(draw, body, mid + 10, y0, caps["estimate"], caps["estimate_rows"])


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
    locked = SimState(
        city_only=1,
        labor_assigned=[0, 12, 4, 4, 0, 0, 0],
        labor_need=[20, 12, 4, 4, 0, 8, 0],
        plebs_ready=42,
    )
    if labor_slider_short(locked):
        lines.append("FAIL  slider short treats construction / N/A as understaffed")
    else:
        lines.append("ok    slider short ignores construction lock and N/A rows")
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
    elif forum_layout(1280, 960) != (2, 0, 0):
        lines.append(f"FAIL  forum scale 2x {forum_layout(1280, 960)}")
    elif forum_layout(1920, 1080) != (2, 320, 60):
        lines.append(f"FAIL  forum letterbox {forum_layout(1920, 1080)}")
    else:
        lines.append("ok    forum scale 1/2 + widescreen letterbox")
    wide = (1920, 1080)
    wscale, wox, woy = forum_layout(*wide)
    scaled = blit_forum(wide, state, sim)
    if scaled.size != wide:
        lines.append(f"FAIL  forum 2x blit {scaled.size}")
    elif scaled.getpixel((10, 10)) != _FORUM_LETTERBOX:
        lines.append("FAIL  forum widescreen missing letterbox")
    elif scaled.getpixel((wox + 10, woy + 10)) == _FORUM_LETTERBOX:
        lines.append("FAIL  forum 2x overlay empty")
    else:
        lines.append("ok    forum 2x nearest + centered letterbox")
    px, py, _pw, _ph = button_rect(11)
    exit_msg = click_forum(
        ForumState(kind=KIND_PLEBS, labor=labor),
        wox + px * wscale + 4,
        woy + py * wscale + 4,
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

    def _win(nx: int, ny: int) -> tuple[int, int]:
        return wox + nx * wscale + 2, woy + ny * wscale + 2

    _wm, wp = _welfare_rects()
    click_forum(state_s, *_win(wp[0], wp[1]), sim_s, frame_size=wide)
    if labor_s.welfare != 9:
        lines.append(f"FAIL  scaled welfare+ {labor_s.welfare}")
    else:
        lines.append("ok    2x PLEBS welfare slider")
    minus0, bar0, plus0 = _slider_rects(0)
    before0 = labor_s.assigned[0]
    idle0 = labor_s.idle
    click_forum(state_s, *_win(plus0[0], plus0[1]), sim_s, frame_size=wide)
    click_forum(state_s, *_win(minus0[0], minus0[1]), sim_s, frame_size=wide)
    click_forum(state_s, *_win(bar0[0], bar0[1]), sim_s, frame_size=wide)
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
    click_forum(state_s, *_win(plus1[0], plus1[1]), sim_s, frame_size=wide)
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
    p0, m0 = _tax_rects(0)
    p1, _m1 = _tax_rects(1)
    if p0[1] < _PANEL_Y or p1[1] <= p0[1] + p0[3] or m0[0] <= p0[0]:
        lines.append(f"FAIL  tax rows overlap {p0} {p1}")
    else:
        lines.append("ok    Population + Industrial tax rows unclipped")
    lay = SimState(
        city_only=1,
        year_raw=-123,
        treasury=1386,
        population=2510,
        employed_pct=75,
        tax_rate=6,
        industrial_tax=6,
        surplus_last=-54,
        pop_tax_last=1856,
        ind_tax_last=382,
        construct_last=1518,
        operating_last=720,
        tribute=0,
    )
    caps = treasurer_captions(lay)
    if (
        caps["treasury"] != "Treasury 1386 Dn"
        or "2510 Citizens" not in caps["citizens"]
        or "75% employed" not in caps["citizens"]
        or caps["accounts"] != "124 BC ACCOUNTS  54 Dn loss"
        or "123 BC ESTIMATE" not in caps["estimate"]
        or caps["accounts_rows"][0] != "(+) 1856 Dn   Population Tax"
        or caps["accounts_rows"][2] != "(-) 1518 Dn   Constructions"
        or caps["pop_rate"] != "6%"
    ):
        lines.append(f"FAIL  treasurer captions {caps}")
    else:
        lines.append("ok    Treasurer matches C2 ledger (year + Dn + two columns)")
    treas2 = ForumState(kind=KIND_TREASURER, labor=labor_w)
    click_forum(treas2, *_win(tp[0], tp[1]), sim_t, frame_size=wide)
    click_forum(treas2, *_win(ip[0], ip[1]), sim_t, frame_size=wide)
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
    elif oracle_advice_skip(sim_o, 3) != 21:
        lines.append(f"FAIL  culture skip {oracle_advice_skip(sim_o, 3)}")
    else:
        lines.append("ok    Oracle city-only 24 / Prosperity 18 / Culture 21")
    sim_svc = SimState(city_only=1, cover_entertainment=40, cover_temple=30, cover_services=10)
    if oracle_advice_skip(sim_svc, 3) != 23:
        lines.append(f"FAIL  culture services min {oracle_advice_skip(sim_svc, 3)}")
    else:
        lines.append("ok    Culture [31]+23 when services cover is the min")
    tick = SimState(city_only=1, skill=2, tax_rate=5, tax_wealth=0, population=0)
    tick_city_ratings(tick, bytearray(MAP_W * MAP_H * TILE_STRIDE))
    if tick.rating_prosperity != 0 or tick.rating_culture != 0 or tick.rating_empire != 0:
        lines.append(
            f"FAIL  empty tick P={tick.rating_prosperity} C={tick.rating_culture}"
        )
    elif not city_only_won(SimState(
        city_only=1, skill=2, rating_prosperity=30, rating_culture=30
    )):
        lines.append("FAIL  Normal P=C=30 should win (Need 20 / avg 30)")
    elif city_only_won(SimState(
        city_only=1, skill=2, rating_prosperity=20, rating_culture=20
    )):
        lines.append("FAIL  Normal P=C=20 avg 20 < Need 30")
    else:
        lines.append("ok    City Only win is P+C Need, not pop 50")
    cult_map = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    cult_map[0] = 0x82
    cult_map[TILE_STRIDE] = ID_SHRINE
    shrine = SimState(city_only=1, skill=2, tax_rate=5)
    tick_city_ratings(shrine, cult_map)
    if shrine.cover_temple <= 0 or shrine.rating_culture < 1:
        lines.append(
            f"FAIL  shrine culture cover={shrine.cover_temple} C={shrine.rating_culture}"
        )
    else:
        lines.append("ok    Culture ticks from shrine cover (not seed)")
    if oracle_raw_stem(1) != "B02" or oracle_raw_stem(4) != "B05" or oracle_raw_stem(16) != "B15":
        lines.append(
            f"FAIL  oracle RAW {oracle_raw_stem(1)} {oracle_raw_stem(4)} {oracle_raw_stem(16)}"
        )
    elif oracle_raw_index(7) is not None or oracle_raw_stem(17):
        lines.append("FAIL  Peace stubs / city-only 17 must not play RAW")
    else:
        lines.append("ok    Oracle click audio B02–B15 (0x1f…0x2c)")
    oracle = ForumState(kind=KIND_ORACLE, labor=labor)
    click_forum(oracle, ORACLE_HIT_X0 + 4, ORACLE_HIT_Y + 4, sim_o)
    if oracle.oracle_advice != 0:
        lines.append(f"FAIL  oracle col {oracle.oracle_advice}")
    elif oracle.oracle_sfx != oracle_raw_stem(oracle_advice_id(sim_o, 0)):
        lines.append(f"FAIL  oracle sfx {oracle.oracle_sfx!r}")
    else:
        lines.append("ok    Oracle column hit Empire → city-only stub + B-series")
    click_forum(oracle, ORACLE_HIT_X0 + 2 * ORACLE_COL_STRIDE + 4, ORACLE_HIT_Y + 4, sim_o)
    if oracle.oracle_advice != 2:
        lines.append(f"FAIL  oracle Prosperity col {oracle.oracle_advice}")
    else:
        lines.append("ok    Oracle Prosperity text hit (no crash)")
    if _oracle_column(ORACLE_AVG_X + 8, ORACLE_AVG_Y + 2) is not None:
        lines.append("FAIL  average rating must not be a column hit")
    else:
        lines.append("ok    Average rating is not a click target")
    ox0, oy0, _ow0, _oh0 = button_rect(0)
    still = ForumState(kind=KIND_ORACLE)
    click_forum(still, ox0 + 4, oy0 + 4, sim_o)
    if still.kind != KIND_ORACLE:
        lines.append(f"FAIL  Oracle chrome leak {still.kind}")
    else:
        lines.append("ok    Oracle full screen ignores 4×3 chrome")
    oframe = blit_forum((640, 480), ForumState(kind=KIND_ORACLE, labor=labor), sim_o)
    if oframe.size != (640, 480):
        lines.append(f"FAIL  oracle blit {oframe.size}")
    else:
        lines.append("ok    Oracle opens 4 ratings (640x480)")
    try:
        from app.config import resolve_game_dir

        game, _how = resolve_game_dir()
        col = load_oracle_column(game)
        scene = load_oracle_scene(game)
        if col is not None and col.size != (96, 337):
            lines.append(f"FAIL  RAT_BACK[0] {col.size}")
        elif scene is not None and scene.size[0] < 640:
            lines.append(f"FAIL  RAT_FRON {scene.size}")
        elif col is None or scene is None:
            lines.append("ok    Oracle PL8 missing (retail not required for unit pin)")
        else:
            art = ForumState(kind=KIND_ORACLE, labor=labor, oracle_back=scene, oracle_column=col)
            aframe = blit_forum((640, 480), art, SimState(city_only=1, skill=2, rating_prosperity=40, rating_culture=10))
            if aframe.size != (640, 480):
                lines.append(f"FAIL  oracle retail blit {aframe.size}")
            else:
                lines.append("ok    retail RAT_FRON + RAT_BACK[0] column 96x337")
    except (OSError, ValueError, FileNotFoundError) as exc:
        lines.append(f"ok    Oracle PL8 skip ({exc})")
    opened = ForumState(kind=KIND_CHROME)
    ox, oy, _ow, _oh = button_rect(2)
    emp = click_forum(opened, ox + 2, oy + 2, sim_o)
    if opened.kind != KIND_EMPIRE or "EMPIRE" not in emp.upper():
        lines.append(f"FAIL  EMPIRE MAP open {opened.kind} {emp!r}")
    else:
        lines.append("ok    EMPIRE MAP opens full-screen chrome (no career travel)")
    click_forum(opened, ox + 2, oy + 2, sim_o)
    # Empire swallows chrome clicks — right-click / Esc returns (window _forum_back).
    idle = ForumState(kind=KIND_CHROME)
    rx, ry, _rw, _rh = button_rect(9)
    rome = click_forum(idle, rx + 2, ry + 2, sim_o)
    if idle.kind != KIND_ROME or "ROME" not in rome.upper():
        lines.append(f"FAIL  ROME open {idle.kind} {rome!r}")
    else:
        lines.append("ok    ROME overlay opens")
    click_forum(idle, rx + 2, ry + 2, sim_o)
    if idle.kind != KIND_CHROME:
        lines.append(f"FAIL  re-click ROME dismiss {idle.kind}")
    else:
        lines.append("ok    re-click advisor returns to CLEAR FORUM")
    px, py, _pw2, _ph2 = button_rect(7)
    pers = click_forum(idle, px + 2, py + 2, sim_o)
    if idle.kind != KIND_PERSONAL:
        lines.append(f"FAIL  PERSONAL open {idle.kind} {pers!r}")
    else:
        lines.append("ok    PERSONAL overlay opens")
    cx, cy, _cw, _ch = button_rect(1)
    idle.kind = KIND_CHROME
    cent = click_forum(idle, cx + 2, cy + 2, sim_o)
    if idle.kind != KIND_CENTURION:
        lines.append(f"FAIL  CENTURION open {idle.kind} {cent!r}")
    else:
        lines.append("ok    CENTURION overlay opens")
    mx8, my8, _mw, _mh = button_rect(8)
    idle.kind = KIND_CHROME
    mer = click_forum(idle, mx8 + 2, my8 + 2, sim_o)
    if idle.kind != KIND_MERCHANT:
        lines.append(f"FAIL  MERCHANT open {idle.kind} {mer!r}")
    else:
        lines.append("ok    MERCHANT overlay opens")
    hx, hy, _hw, _hh = button_rect(10)
    idle.kind = KIND_CHROME
    help_msg = click_forum(idle, hx + 2, hy + 2, sim_o)
    if idle.kind != KIND_HELP or "HELP" not in help_msg.upper():
        lines.append(f"FAIL  HELP {idle.kind} {help_msg!r}")
    else:
        lines.append("ok    HELP highlights (no overlay)")
    clx, cly, _clw, _clh = button_rect(5)
    idle.kind = KIND_ROME
    cleared = click_forum(idle, clx + 2, cly + 2, sim_o)
    if idle.kind != KIND_CHROME or "CLEAR" not in cleared.upper():
        lines.append(f"FAIL  CLEAR FORUM {idle.kind} {cleared!r}")
    else:
        lines.append("ok    CLEAR FORUM dismisses overlay")
    fresh = open_forum(SimState(city_only=1), tiles)
    if fresh.kind != KIND_CHROME:
        lines.append(f"FAIL  open_forum idle {fresh.kind}")
    else:
        lines.append("ok    Forum enters idle CLEAR FORUM")
    if promotions_left(1) != 9 or promotions_left(10) != 0:
        lines.append(f"FAIL  promotions {promotions_left(1)} {promotions_left(10)}")
    else:
        lines.append("ok    promotions-to-Emperor = 10 − rank")
    if favor_quote_skip(0) != 3 or favor_quote_skip(50) != 8:
        lines.append(f"FAIL  favor skip {favor_quote_skip(0)} {favor_quote_skip(50)}")
    else:
        lines.append("ok    favor quote [37]+3…+14")
    circa = empire_circa_title(-290)
    if "circa 290 BC" not in circa:
        lines.append(f"FAIL  empire title {circa!r}")
    else:
        lines.append("ok    Roman empire circa 290 BC (space after circa)")
    rframe = blit_forum((640, 480), ForumState(kind=KIND_ROME), SimState(city_only=1, savings=0))
    pframe = blit_forum((640, 480), ForumState(kind=KIND_PERSONAL), SimState(city_only=1, rank=0))
    cframe = blit_forum((640, 480), ForumState(kind=KIND_CENTURION), SimState(city_only=1))
    mframe = blit_forum((640, 480), ForumState(kind=KIND_MERCHANT), SimState(city_only=1))
    eframe = blit_forum((640, 480), ForumState(kind=KIND_EMPIRE), SimState(city_only=1, year_raw=-300))
    if any(f.size != (640, 480) for f in (rframe, pframe, cframe, mframe, eframe)):
        lines.append("FAIL  new advisor blit size")
    else:
        lines.append("ok    Rome / Personal / Legion / Merchant / Empire blit 640x480")
    fat = Image.new("RGB", (FORUM_NATIVE_W, FORUM_NATIVE_H), (90, 70, 50))
    owide = letterbox_forum_fb(
        compose_forum_native(
            ForumState(kind=KIND_ORACLE, oracle_back=fat),
            SimState(city_only=1),
        ),
        1920,
        1080,
    )
    osc, oox, ooy = forum_layout(1920, 1080)
    emp_lb = letterbox_forum_fb(
        compose_forum_native(ForumState(kind=KIND_EMPIRE), SimState(city_only=1)),
        1920,
        1080,
    )
    if osc != 2 or (oox, ooy) != (320, 60):
        lines.append(f"FAIL  oracle widescreen layout {osc, oox, ooy}")
    elif owide.getpixel((4, 4)) != FORUM_LETTERBOX:
        lines.append("FAIL  oracle 16:9 stretched (no letterbox)")
    elif owide.getpixel((1915, 4)) != FORUM_LETTERBOX:
        lines.append("FAIL  oracle 16:9 missing right bar")
    elif owide.getpixel((oox + 8, ooy + 8)) == FORUM_LETTERBOX:
        lines.append("FAIL  oracle FB empty after letterbox")
    elif emp_lb.getpixel((4, 4)) != FORUM_LETTERBOX:
        lines.append("FAIL  empire 16:9 helper drifted from Oracle")
    else:
        lines.append("ok    Oracle/Empire share letterbox_forum_fb 16:9 bars")
    wide_src = Image.new("RGB", (1920, 1080), (90, 70, 50))
    forced = compose_forum_native(
        ForumState(kind=KIND_ORACLE, oracle_back=wide_src),
        SimState(city_only=1),
    )
    if forced.size != (FORUM_NATIVE_W, FORUM_NATIVE_H):
        lines.append(f"FAIL  compose_forum_native {forced.size}")
    else:
        lines.append("ok    compose_forum_native stays 640×480")
    scaled_fb, s_fb, x_fb, y_fb = scale_forum_fb(forced, 1920, 1080)
    if scaled_fb.size != (1280, 960) or (s_fb, x_fb, y_fb) != (2, 320, 60):
        lines.append(f"FAIL  scale_forum_fb {scaled_fb.size} {s_fb, x_fb, y_fb}")
    else:
        lines.append("ok    scale_forum_fb stays 4:3 (not dest 16:9)")
    col_fat = Image.new("RGBA", (192, 337), (200, 160, 80, 255))
    locked = _lock_oracle_column(col_fat)
    if locked.size != (ORACLE_COL_W, ORACLE_COL_H):
        lines.append(f"FAIL  oracle column lock {locked.size}")
    else:
        lines.append("ok    RAT_BACK column locked 96×337")
    o2 = blit_forum(
        (1280, 960),
        ForumState(kind=KIND_ORACLE, oracle_column=col_fat),
        SimState(city_only=1, rating_prosperity=40, rating_culture=10),
    )
    s2, x2, y2 = forum_layout(1280, 960)
    col_y = max(0, min(0x126, _oracle_col_top(40)))
    cx0 = x2 + (0x20 + 2 * ORACLE_COL_STRIDE) * s2
    cy0 = y2 + col_y * s2
    mid = o2.getpixel((cx0 + 8, cy0 + 8))
    past = o2.getpixel((cx0 + ORACLE_COL_W * s2 + 8, cy0 + 8))
    if s2 != 2 or mid[0] < 100 or past[0] > 80:
        lines.append(f"FAIL  oracle 2x column still fat {s2} {mid} {past}")
    else:
        lines.append("ok    Oracle 2x columns stay 96×337 game pixels")
    emp_st = ForumState(kind=KIND_EMPIRE)
    gx, gy = EMPIRE_HOTSPOTS[EMPIRE_GERMANIA_EXTERIOR - 1]
    click_forum(emp_st, gx + 4, gy + 4, SimState(city_only=1))
    sea = ForumState(kind=KIND_EMPIRE)
    click_forum(sea, 180, 280, SimState(city_only=1))
    mapped = ForumState(kind=KIND_EMPIRE)
    msc, mox, moy = forum_layout(1280, 720)
    click_forum(
        mapped,
        mox + gx + 4,
        moy + gy + 4,
        SimState(city_only=1),
        frame_size=(1280, 720),
    )
    if emp_st.empire_pick != EMPIRE_GERMANIA_EXTERIOR:
        lines.append(f"FAIL  Germania Exterior hotspot {emp_st.empire_pick}")
    elif sea.empire_pick == EMPIRE_GERMANIA_EXTERIOR:
        lines.append("FAIL  sea west of Italy hit Germania Exterior")
    elif mapped.empire_pick != EMPIRE_GERMANIA_EXTERIOR:
        lines.append(f"FAIL  empire mouse→640×480 {mapped.empire_pick}")
    else:
        lines.append("ok    Empire hits use 0x95cbb after window→FB map")
    if empire_raw_stem(1) != "B30" or empire_raw_stem(17) != "C16" or empire_raw_stem(32) != "C31":
        lines.append(
            f"FAIL  empire RAW {empire_raw_stem(1)} {empire_raw_stem(17)} {empire_raw_stem(32)}"
        )
    else:
        lines.append("ok    Empire VO C16/C31 from 0x135A4(skip+0x3A)")
    creta = ForumState(kind=KIND_EMPIRE)
    cx, cy = EMPIRE_HOTSPOTS[EMPIRE_CRETA - 1]
    click_forum(creta, cx + 4, cy + 4, SimState(city_only=1))
    if creta.empire_pick != EMPIRE_CRETA or creta.empire_sfx != "C16":
        lines.append(f"FAIL  Creta pick/sfx {creta.empire_pick} {creta.empire_sfx!r}")
    elif "island" not in creta.empire_flavor.lower():
        lines.append(f"FAIL  Creta flavor {creta.empire_flavor[:60]!r}")
    else:
        lines.append("ok    Creta dialog flavor + C16.RAW")
    click_forum(creta, 180, 280, SimState(city_only=1))
    if creta.empire_pick is not None or creta.empire_flavor:
        lines.append(f"FAIL  sea does not dismiss dialog {creta.empire_pick}")
    else:
        lines.append("ok    miss click clears Empire dialog")
    creta.empire_pick = EMPIRE_CRETA
    creta.empire_flavor = empire_flavor_text(EMPIRE_CRETA)
    dframe = blit_forum((640, 480), creta, SimState(city_only=1, year_raw=-289))
    gold = False
    for yy in range(EMPIRE_FLAVOR_Y + 4, EMPIRE_FLAVOR_Y + 22):
        for xx in range(EMPIRE_FLAVOR_X + 8, EMPIRE_FLAVOR_X + 80):
            pix = dframe.getpixel((xx, yy))
            if pix[0] > 180 and pix[1] > 160:
                gold = True
                break
        if gold:
            break
    if not gold:
        lines.append("FAIL  flavor invisible in green frame")
    elif "Govern this Province" in creta.empire_flavor:
        lines.append("FAIL  career Govern this Province leaked")
    else:
        lines.append("ok    flavor ink inside 0x59ff8 teal frame")
    fill = dframe.getpixel((EMPIRE_DLG_X + 20, EMPIRE_DLG_Y + 20))
    if fill[1] < 100 or fill[1] <= fill[2]:
        lines.append(f"FAIL  empire dialog not teal {fill}")
    else:
        lines.append("ok    Empire dialog fill EMPIRE.256[0x11] teal")
    if EMPIRE_CAP_Y != 408 or EMPIRE_FOOT_Y != 442:
        lines.append(f"FAIL  empire footer y {EMPIRE_CAP_Y} {EMPIRE_FOOT_Y}")
    else:
        lines.append("ok    Empire caption y=408 / footer y=442")
    creta.empire_pick = EMPIRE_CRETA
    creta.empire_flavor = empire_flavor_text(EMPIRE_CRETA)
    rx, ry, rw, rh = empire_close_rect()
    click_forum(creta, rx + rw // 2, ry + rh // 2, SimState(city_only=1))
    if creta.empire_pick is not None:
        lines.append(f"FAIL  close X leaves pick {creta.empire_pick}")
    else:
        lines.append("ok    Empire dialog close/X (0x2ddad) dismisses")
    creta.empire_pick = EMPIRE_CRETA
    creta.empire_flavor = "island"
    cbox = blit_forum((640, 480), creta, SimState(city_only=1))
    xpix = cbox.getpixel((rx + 4, ry + 4))
    if xpix[1] < 80 or xpix[1] <= xpix[2]:
        lines.append(f"FAIL  close gadget not teal {xpix}")
    else:
        lines.append("ok    close gadget painted on teal frame")
    sim_g = SimState(city_only=1)
    goods = bytearray(768)
    struct.pack_into("<i", goods, 1 * 48 + 8, 2)
    struct.pack_into("<i", goods, 1 * 48 + 4, 10)
    struct.pack_into("<i", goods, 1 * 48 + 36, 3)
    sim_g.goods = goods
    rows = industry_rows(sim_g)
    if not rows or rows[0][1] != "Grapes":
        lines.append(f"FAIL  industry rows {rows}")
    else:
        lines.append("ok    Merchant lists local Grapes from chunk 339")
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
    from app.city_map import CityMap
    from app.place import COST_ARENA, TOOL_ARENA, try_place

    pin_city = CityMap()
    pin_city.source = "treasurer-construct"
    for dy in range(3):
        for dx in range(3):
            pin_city.tiles[pin_city.offset(40 + dx, 2 + dy)] = 0x14
    pin_sim = SimState(city_only=1, treasury=800, tax_wealth=0, welfare=0, construct_ytd=0)
    before = treasurer_estimate(pin_sim)
    before_caps = treasurer_captions(pin_sim)
    placed = try_place(pin_city, 40, 2, TOOL_ARENA, pin_sim)
    after = treasurer_estimate(pin_sim)
    after_caps = treasurer_captions(pin_sim)
    if (
        not placed.ok
        or pin_sim.construct_ytd != COST_ARENA
        or after.constructions != COST_ARENA
        or after.surplus != before.surplus - COST_ARENA
        or after_caps["estimate_rows"][2] != f"(-) {COST_ARENA} Dn   Constructions"
        or before_caps["estimate_rows"][2] != "(-) 0 Dn   Constructions"
    ):
        lines.append(
            f"FAIL  place 700 books constructions {placed.message} "
            f"ytd={pin_sim.construct_ytd} {after} {after_caps.get('estimate_rows')}"
        )
    else:
        lines.append("ok    Arena 700 → ESTIMATE Constructions / surplus −700")
    wrap_ytd = SimState(
        city_only=1,
        year_raw=-299,
        tax_ytd=0,
        ind_tax_ytd=0,
        construct_ytd=COST_ARENA,
        operating_ytd=0,
        history=bytearray(HIST_BYTES),
    )
    close_year_books(wrap_ytd)
    if (
        wrap_ytd.construct_last != COST_ARENA
        or wrap_ytd.construct_ytd != 0
        or wrap_ytd.surplus_last != -COST_ARENA
    ):
        lines.append(
            f"FAIL  year books construct {wrap_ytd.construct_last} "
            f"ytd={wrap_ytd.construct_ytd} surplus={wrap_ytd.surplus_last}"
        )
    else:
        lines.append("ok    Dec wrap copies construct YTD → ACCOUNTS, zeros chunk 155")
    return lines
