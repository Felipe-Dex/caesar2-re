"""City placement v1 — tent / road / clear plus City Only civic stamps.

Road on straight river (`+1 & 0x10`, no bank `0x08`, id 0x1E–0x2D) becomes
a bridge: +0 = 0x4E–0x51, +9 saves the water id, +1 keeps 0x10 and ORs pad
(FUN_000669c6 `0x669C6`). Curve/corner (`+1 & 0x08`, ids 0x36/0x3A/0x46/0x4A
and remaps) is refused. A cardinal neighbour that is already a bridge
(`0x4E–0x51`, river+pad) is refused — 665DF walks only ±0x14 / ±0x640
and will not flood river→river. Diagonals are allowed. Road will not
write when ``+0 >= 0x7C`` (``FUN_000669c6`` ``0x66B8D``) — skip that
cell, rest of the line still stamps. Clear: ``+0 >= 0x82`` (``0x68D2F``)
→ rubble 0x05 (``FUN_000696e8``); garden ``0x78–0x7B`` and plaza/statue
``0x7C–0x7E`` share the ``< 0x82`` flatten (``FUN_000697fe`` → grass
0x1A–0x1D; host 0x1C). Rubble → 0x1C (D.SAV / user). Multi-tile
``id >= 0x82`` uses ``DAT_00094FE5`` + ``+5`` lo-nibble to wipe the
whole N×N (``FUN_00069483``). Open river refused; bridge clear
restores +9 (0x6985B).

Civic: Reservoir ``0xBE`` **1×1** (A/B; ``+1=0x80``), fills if cardinal
to river (``+1&0x18``) or a charged pipe (ghidra_water.md). Well ``0xD7``,
Fountain ``0xDD``, Gardens ``0x78–0x7B`` (LUT ``0x93FCC``), Praefecture ``0xE3``
``+3=0x80`` ``+4=0x50``, Tower ``0xBF``, Barracks ``0xE4`` 3×3. Aqueduct
``0xCB–0xD6`` must attach to a reservoir or an existing aqueduct
(the rubber-band line is one component — start/end either way).
Autotile is ``FUN_00067a6a`` LUT ``0x94D8F`` ×14 (same matcher as roads):
caps ``0xCB–0xCE``, NS ``0xCF``, EW ``0xD0``, corners ``0xD1–0xD4``,
T/cross ``0xD5``/``0xD6`` (``+1=0x60``). Road ``0x52–0x5C`` is allowed
(Gate analog): LUT ``0x94E37`` ×2 writes ``0xD5`` (NS pipe) / ``0xD6``
(EW pipe), ``+1=0x60``, ``+3=0x90``. Dry ``+9`` from 20230610 / FELIPE.
Charge (``rebuild_pipe_charge``) only from a river-fed reservoir, then
walk the ``+1 & 0xC0`` graph — isolated / disconnected aqueduct stays
dry. Clear wipes grass ``0xCB–0xD6`` to rubble ``0x05``; road-combo
(``+3&0x80``) restores the road. Reservoir ``+9`` from LUT ``0x94E7F``
(inlet on the tank wall when a pipe is cardinal).
Tower ``0xBF`` autotile: standalone sprite when no Wall ``0xC1``/``0xC2``
/ Gate ``0xC0`` neighbour; Achea ``+4`` when a wall joins.
Does **not** write road ``0x52–0x5C`` and must **not** run road retile —
that was turning neighbour grass+``FLAG_PAD`` into a fake road. River
refused except the documented road→bridge case. Drag-rect for 1×1 civics
is treasury-atomic.

Click-drag (host): commit on mouse-up only. Road / Wall / Aqueduct =
axis-aligned straight line (dominant |dx|≥|dy| → horizontal at start y,
else vertical at start x; no L). House/Clear/1×1 civic paint = axis-aligned
rectangle, raster y then x.
Stamp tools (Barracks 3×3, Reservoir 1×1, any N×N): one footprint follows
the cursor; ghost overlay; release places once. Place uses dirty iso (no
full-map flush — that thumbnailed the canvas and looked like a zoom pop).
Clear of a tall building still sets ``flush_iso``. Tent / civic-rect drag
is **atomic** if treasury < cost×N. N×N>1×1 (forum / temple / theater /
barracks / …) is stamp-follow; Circus 6×3 EW (0xEB+0xEC) / 3×6 NS
(0xE9+0xEA) and C.Maximus 4×8 / 8×4 are one paired ghost — odd facing
swaps the long axis. Plaza is 1×1 rect on/next to a road. Wall is a road-style
line (gate when the line hits a road).

Not the full EXE stamp. Tent 6 is observed (sav_c), not C2MODEL. City
road / aqueduct / Palatine have no pinned city-cost slot — do not invent;
no debit. Arena ``0xE7`` is leftover (no SAV origin / +4) — not stamped.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.city_map import (
    FLAG_PAD,
    FLAG_RIVER,
    FLAG_RIVER_BANK,
    FLAG_WATER_SOURCE,
    ID_TERRAIN_MAX,
    MAP_H,
    MAP_W,
    TILE_STRIDE,
    VAR_TOWER_ALONE,
    CityMap,
    iso_origin_x,
    iso_overlap_radius,
    iso_tile_size,
    rotate_footprint_local,
)
from app.city_paint import (
    factory_produce,
    factory_type_name,
    paint_baths_emitter,
    paint_education_emitter,
    sync_water_building_graphic,
    paint_entertainment_emitter,
    paint_factory_emitter,
    paint_security_emitter,
    paint_water_emitter,
    seed_city_only_industry,
)
from app.city_sim import SimState

ID_TENT = 0x82
ID_RUBBLE = 0x05
ID_CLEAR = 0x1C
ID_ROAD_LO = 0x52
ID_ROAD_HI = 0x5C
# Isolated / N–S ends reuse the NS graphic (province_roads.md).
ID_ROAD_NS = 0x52
ID_ROAD_EW = 0x53
# 669C6: straight water 0x1E–0x2D → bridge CITYFIXT 0x4E–0x51.
ID_STRAIGHT_LO = 0x1E
ID_STRAIGHT_HI = 0x2E
ID_BRIDGE_LO = 0x4E
ID_BRIDGE_HI = 0x51
# 669C6 @ 0x66B8D: cmp +0, 0x7C / jge skip — no road id on plaza+buildings.
ID_ROAD_OCCUPIED = 0x7C
# DAT_00094FE5[0x82:0x100]. Clear 0x68D41. 4→2×2, 9→3×3, 0x10→4×4 (0x68D54).
_DAT_94FE5_FROM_82 = bytes.fromhex(
    "010101010101010101010101010101010101010101010101010104040404090901010101040404040909090904040404090909091010101000000101010101010101010101010101010101010101010101010101010101010101010101040404040109040409090909090910101010000004090900000000090904040404"
)

# sav_c.md: C.SAV origin tent debit. C2MODEL has no 6.
COST_TENT = 6
# sav_ab.md treasury −51. C2MODEL [101]=50 is FAQ list, not the debit.
COST_RESERVOIR = 51
# C2MODEL [102:114]: Gardens 3, Well 20, Fountain 15, Barracks 400,
# Prefecture 100. FAQ [96:102] Tower 75.
COST_GARDEN = 3
COST_WELL = 20
COST_FOUNTAIN = 15
COST_PREFECTURE = 100
COST_TOWER = 75
COST_BARRACKS = 400
# C2MODEL [102:124] / FAQ [96:102]. Palatine has no unique slot — no debit.
COST_PLAZA = 12
COST_WALL = 20
COST_GATE = 5
COST_SHRINE = 80
COST_TEMPLE = 200
COST_BASILICA = 600
COST_AVENTINE = 100
COST_JANICULAN = 400
COST_THEATER = 300
COST_ODEUM = 500
COST_COLISEUM = 1000
COST_CIRCUS = 1500
COST_CMAXIMUS = 2500
COST_GRAMMATICUS = 250
COST_RHETOR = 500
COST_LIBRARY = 1000
COST_BATHS = 30
COST_MARKET = 40
COST_HOSPITAL = 500
COST_FACTORY = 80

ID_GARDEN = 0x78
ID_GARDEN_HI = 0x7B
ID_RESERVOIR = 0xBE
ID_TOWER = 0xBF
ID_AQUEDUCT_STUB = 0xCB
ID_AQUEDUCT_LO = 0xCB
ID_AQUEDUCT_HI = 0xD6
ID_WELL = 0xD7
ID_FOUNTAIN = 0xDD
ID_PLAZA = 0x7C
ID_PLAZA_JOIN = 0x7D
ID_PLAZA_STATUE = 0x7E
ID_SHRINE = 0xA2
ID_TEMPLE = 0xA6
ID_BASILICA = 0xAB
ID_AVENTINE = 0xAF
ID_JANICULAN = 0xB2
ID_PALATINE = 0xB7
ID_GATE = 0xC0
ID_WALL_NS = 0xC1
ID_WALL_EW = 0xC2
ID_PREFECTURE = 0xE3
ID_BARRACKS = 0xE4
ID_THEATER = 0xE5
ID_ODEUM = 0xE6
ID_COLISEUM = 0xE8
ID_CIRCUS_A = 0xE9
ID_CIRCUS_B = 0xEA
ID_CIRCUS_C = 0xEB
ID_CIRCUS_D = 0xEC
ID_CMAX_A = 0xED
ID_CMAX_B = 0xEE
ID_CMAX_C = 0xEF
ID_CMAX_D = 0xF0
ID_GRAMMATICUS = 0xF3
ID_RHETOR = 0xF4
ID_LIBRARY = 0xF5
ID_FACTORY = 0xFA
ID_HOSPITAL = 0xFB
ID_MARKET = 0xFC
ID_BATHS = 0xDF
# A/B reservoir: +1=0x80, +3=0x20, +4=+9=0x6E. D.SAV well +3=0x08 +4=0x10.
FLAG_PIPE = 0x40
FLAG_RESERVOIR = 0x80
DRAW_RESERVOIR = 0x20
VAR_RESERVOIR = 0x6E
DRAW_WELL = 0x08
VAR_WELL = 0x10
DRAW_FOUNTAIN = 0x08
VAR_FOUNTAIN = 0x5F  # LUT 0x94f6c[0xDD] dry; wet is +1 (0x60) on +13&4
DRAW_GARDEN = 0x04
# FUN_00068950: +4 = (LUT[i]>>2)+0x77. Base 0x77 is the n=0 hedge, not a
# fixed stamp — 0x77-only was the all-identical-tile bug.
VAR_GARDEN = 0x77
# DAT_00093FCC — 64 bytes. Place 0x68A2A / +4 twin 0x68A5A.
_GARDEN_LUT = bytes.fromhex(
    "0a050b030d040f07090800020c0e0106"
    "000b020d040f060908070a010c030e05"
    "090a01020d0e0500070c03040f060b08"
    "06010d030b0500040c020e0f09070a08"
)
DRAW_PREFECTURE = 0x80
VAR_PREFECTURE = 0x50
DRAW_TOWER = 0x08
# Achea (55,1)/(72,52) E-only → 0x96. Lone 0xBF uses VAR_TOWER_ALONE.
VAR_TOWER = 0x96
FLAG_TOWER = 0x04
# Neighbor mask N=1 E=2 S=4 W=8 → +4. 0x18–0x1B family via LUT 0x97600.
_TOWER_FROM_MASK: dict[int, int] = {
    0x0: VAR_TOWER_ALONE,
    0x1: 0x9C,
    0x2: 0x96,
    0x3: 0x96,
    0x4: 0x9B,
    0x5: 0x9A,
    0x6: 0x96,
    0x7: 0x9A,
    0x8: 0x9C,
    0x9: 0x9C,
    0xA: 0x9A,
    0xB: 0x9A,
    0xC: 0x9B,
    0xD: 0x9A,
    0xE: 0x9A,
    0xF: 0x9A,
}
DRAW_BARRACKS = 0x00
# Achea 3×3 raster y,x. +4 0x51–0x59 (not sequential in row order).
_BARRACKS_VAR = (
    0x51, 0x53, 0x56,
    0x52, 0x55, 0x58,
    0x54, 0x57, 0x59,
)
BARRACKS_SIZE = 3
# Achea run +3=0x10 (sheet 0x10). Dry +4 from ghidra_water.md §4.
DRAW_AQUEDUCT = 0x10
# FUN_00067a6a: pipe + FLAG_PAD → LUT 0x94E37, then +3 |= 0x80 (sheet stays 0x10).
DRAW_AQUEDUCT_ROAD = 0x90
ID_AQUEDUCT_ROAD_NS = 0xD5
ID_AQUEDUCT_ROAD_EW = 0xD6

TOOL_TENT = "tent"
TOOL_ROAD = "road"
TOOL_CLEAR = "clear"
TOOL_QUERY = "query"
TOOL_RESERVOIR = "reservoir"
TOOL_AQUEDUCT = "aqueduct"
TOOL_WELL = "well"
TOOL_FOUNTAIN = "fountain"
TOOL_GARDEN = "garden"
TOOL_PREFECTURE = "prefecture"
TOOL_TOWER = "tower"
TOOL_BARRACKS = "barracks"
TOOL_PLAZA = "plaza"
TOOL_WALL = "wall"
TOOL_SHRINE = "shrine"
TOOL_TEMPLE = "temple"
TOOL_BASILICA = "basilica"
TOOL_AVENTINE = "aventine"
TOOL_JANICULAN = "janiculan"
TOOL_PALATINE = "palatine"
TOOL_THEATER = "theater"
TOOL_ODEUM = "odeum"
TOOL_COLISEUM = "coliseum"
TOOL_CIRCUS = "circus"
TOOL_CMAXIMUS = "cmaximus"
TOOL_GRAMMATICUS = "grammaticus"
TOOL_RHETOR = "rhetor"
TOOL_LIBRARY = "library"
TOOL_BATHS = "baths"
TOOL_MARKET = "market"
TOOL_HOSPITAL = "hospital"
TOOL_FACTORY = "factory"
_CIVIC_1X1 = frozenset(
    {
        TOOL_WELL,
        TOOL_FOUNTAIN,
        TOOL_GARDEN,
        TOOL_AQUEDUCT,
        TOOL_PREFECTURE,
        TOOL_TOWER,
        TOOL_RESERVOIR,
        TOOL_PLAZA,
        TOOL_SHRINE,
    }
)
# One footprint under the cursor (not a House/Clear paint rect).
STAMP_TOOLS = frozenset(
    {
        TOOL_BARRACKS,
        TOOL_RESERVOIR,
        TOOL_TEMPLE,
        TOOL_BASILICA,
        TOOL_AVENTINE,
        TOOL_JANICULAN,
        TOOL_PALATINE,
        TOOL_THEATER,
        TOOL_ODEUM,
        TOOL_COLISEUM,
        TOOL_CIRCUS,
        TOOL_CMAXIMUS,
        TOOL_GRAMMATICUS,
        TOOL_RHETOR,
        TOOL_LIBRARY,
        TOOL_BATHS,
        TOOL_MARKET,
        TOOL_HOSPITAL,
        TOOL_FACTORY,
    }
)
_STAMP_SIZE = {TOOL_BARRACKS: BARRACKS_SIZE, TOOL_RESERVOIR: 1}
LINE_TOOLS = frozenset({TOOL_ROAD, TOOL_WALL, TOOL_AQUEDUCT})
RECT_TOOLS = frozenset(
    {TOOL_TENT, TOOL_CLEAR} | (_CIVIC_1X1 - STAMP_TOOLS - LINE_TOOLS)
)
SPAN_TOOLS = RECT_TOOLS | LINE_TOOLS | STAMP_TOOLS

_CARDINALS = ((0, -1), (1, 0), (0, 1), (-1, 0))  # N E S W
# mask N=1 E=2 S=4 W=8 → city twin 0x52–0x5C (province_roads.md §2)
_ROAD_FROM_MASK: tuple[int, ...] = (
    0x52,  # 0 isolated
    0x52,  # N
    0x53,  # E
    0x54,  # N+E NE
    0x52,  # S
    0x52,  # N+S
    0x55,  # E+S SE
    0x58,  # N+E+S T no W
    0x53,  # W
    0x57,  # N+W NW
    0x53,  # E+W
    0x5B,  # N+E+W T no S
    0x56,  # S+W SW
    0x5A,  # N+S+W T no E
    0x59,  # E+S+W T no N
    0x5C,  # all
)


@dataclass
class PlaceResult:
    ok: bool
    message: str
    dirty: list[tuple[int, int]] = field(default_factory=list)
    cost: int = 0
    query: str | None = None
    flush_iso: bool = False


@dataclass
class DragPreview:
    """Rubber-band cells. ``stamp`` writes on release; ``ok`` is the highlight."""

    tool: str
    cells: list[tuple[int, int]]
    ok: list[tuple[int, int]]
    skip: list[tuple[int, int]]
    stamp: list[tuple[int, int]]
    cost: int = 0
    refuse: str | None = None
    message: str = ""
    width: int = 1
    height: int = 1


@dataclass(frozen=True)
class StampSpec:
    """One city stamp. ``variants`` is raster y then x for the first (or only) block.

    ``tid2`` / ``variants2`` are the abutting half (Circus / C.Maximus).
    ``need_road`` is Plaza: must touch a city road (or sit on one).
    """

    tool: str
    label: str
    tid: int
    w: int
    h: int
    cost: int
    flags: int
    draw: int
    variants: tuple[int, ...]
    family: frozenset[int]
    tid2: int = 0
    variants2: tuple[int, ...] = ()
    extra19: int | None = None
    need_road: bool = False


# Occupancy +4 from Achea / D.SAV / 20230610 origins. Sheet = +3 & 0x1C.
_STAMPS: dict[str, StampSpec] = {}
_FACTORY_GOODS = 0


def set_factory_goods(nibble: int) -> None:
    """Origin ``+19`` lo-nibble (factory.md). Bakery=0 … Fish=15."""
    global _FACTORY_GOODS
    _FACTORY_GOODS = int(nibble) & 0xF


def factory_goods() -> int:
    return _FACTORY_GOODS


def _reg(spec: StampSpec) -> StampSpec:
    _STAMPS[spec.tool] = spec
    return spec


_reg(StampSpec(TOOL_TEMPLE, "Temple", ID_TEMPLE, 2, 2, COST_TEMPLE, 0x01, 0x00,
               (0x40, 0x42, 0x41, 0x43), frozenset(range(0xA6, 0xA9))))
_reg(StampSpec(TOOL_BASILICA, "Basilica", ID_BASILICA, 3, 3, COST_BASILICA, 0x01, 0x0C,
               (0x09, 0x0B, 0x0E, 0x0A, 0x0D, 0x10, 0x0C, 0x0F, 0x11),
               frozenset({0xAA, 0xAB, 0xAC})))
_reg(StampSpec(TOOL_AVENTINE, "Aventine", ID_AVENTINE, 2, 2, COST_AVENTINE, 0x01, 0x04,
               (0x04, 0x06, 0x05, 0x07), frozenset({0xAE, 0xAF, 0xB0})))
_reg(StampSpec(TOOL_JANICULAN, "Janiculan", ID_JANICULAN, 3, 3, COST_JANICULAN, 0x01, 0x04,
               (0x10, 0x12, 0x15, 0x11, 0x14, 0x17, 0x13, 0x16, 0x18),
               frozenset({0xB2, 0xB3, 0xB4})))
_reg(StampSpec(TOOL_PALATINE, "Palatine", ID_PALATINE, 4, 4, 0, 0x01, 0x04,
               (0x44, 0x46, 0x49, 0x4D, 0x45, 0x48, 0x4C, 0x50,
                0x47, 0x4B, 0x4F, 0x52, 0x4A, 0x4E, 0x51, 0x53),
               frozenset({0xB6, 0xB7, 0xB8, 0xB9})))
_reg(StampSpec(TOOL_THEATER, "Theater", ID_THEATER, 2, 2, COST_THEATER, 0x01, 0x0C,
               (0x24, 0x26, 0x25, 0x27), frozenset({0xE5})))
_reg(StampSpec(TOOL_ODEUM, "Odeum", ID_ODEUM, 2, 2, COST_ODEUM, 0x01, 0x0C,
               (0x28, 0x2A, 0x29, 0x2B), frozenset({0xE6})))
_reg(StampSpec(TOOL_COLISEUM, "Coliseum", ID_COLISEUM, 3, 3, COST_COLISEUM, 0x01, 0x0C,
               (0x35, 0x37, 0x3A, 0x36, 0x39, 0x3C, 0x38, 0x3B, 0x3D),
               frozenset({0xE8})))
_reg(StampSpec(TOOL_CIRCUS, "Circus", ID_CIRCUS_C, 6, 3, COST_CIRCUS, 0x01, 0x14,
               (0x32, 0x34, 0x37, 0x33, 0x36, 0x39, 0x35, 0x38, 0x3A),
               frozenset(range(0xE9, 0xED)),
               tid2=ID_CIRCUS_D,
               variants2=(0x3B, 0x3D, 0x40, 0x3C, 0x3F, 0x42, 0x3E, 0x41, 0x43)))
_reg(StampSpec(TOOL_CMAXIMUS, "C.Maximus", ID_CMAX_A, 4, 8, COST_CMAXIMUS, 0x01, 0x14,
               (0x12, 0x14, 0x17, 0x1B, 0x13, 0x16, 0x1A, 0x1E,
                0x15, 0x19, 0x1D, 0x20, 0x18, 0x1C, 0x1F, 0x21),
               frozenset(range(0xED, 0xF1)),
               tid2=ID_CMAX_B,
               variants2=(0x22, 0x24, 0x27, 0x2B, 0x23, 0x26, 0x2A, 0x2E,
                          0x25, 0x29, 0x2D, 0x30, 0x28, 0x2C, 0x2F, 0x31)))
# Achea NS Circus 0xE9+0xEA at (35,38). BUILD1D +4 0x00–0x11.
_CIRCUS_NS_VAR = (0x00, 0x02, 0x05, 0x01, 0x04, 0x07, 0x03, 0x06, 0x08)
_CIRCUS_NS_VAR2 = (0x09, 0x0B, 0x0E, 0x0A, 0x0D, 0x10, 0x0C, 0x0F, 0x11)
# Leftover C.Max EW 0xEF+0xF0 — BUILD1D continues after EW circus 0x43.
_CMAX_EW_VAR = (
    0x44, 0x46, 0x49, 0x4D, 0x45, 0x48, 0x4C, 0x50,
    0x47, 0x4B, 0x4F, 0x52, 0x4A, 0x4E, 0x51, 0x53,
)
_CMAX_EW_VAR2 = (
    0x54, 0x56, 0x59, 0x5D, 0x55, 0x58, 0x5C, 0x60,
    0x57, 0x5B, 0x5F, 0x62, 0x5A, 0x5E, 0x61, 0x63,
)
_reg(StampSpec(TOOL_GRAMMATICUS, "Grammaticus", ID_GRAMMATICUS, 2, 2, COST_GRAMMATICUS, 0x01, 0x08,
               (0x40, 0x42, 0x41, 0x43), frozenset({0xF3})))
_reg(StampSpec(TOOL_RHETOR, "Rhetor", ID_RHETOR, 3, 3, COST_RHETOR, 0x01, 0x08,
               (0x44, 0x46, 0x49, 0x45, 0x48, 0x4B, 0x47, 0x4A, 0x4C),
               frozenset({0xF4})))
_reg(StampSpec(TOOL_LIBRARY, "Library", ID_LIBRARY, 3, 3, COST_LIBRARY, 0x01, 0x08,
               (0x4D, 0x4F, 0x52, 0x4E, 0x51, 0x54, 0x50, 0x53, 0x55),
               frozenset({0xF5})))
_reg(StampSpec(TOOL_BATHS, "Baths", ID_BATHS, 2, 2, COST_BATHS, 0x01, 0x08,
               (0x63, 0x65, 0x64, 0x66), frozenset(range(0xDF, 0xE3))))
_reg(StampSpec(TOOL_MARKET, "Market", ID_MARKET, 2, 2, COST_MARKET, 0x01, 0x08,
               (0x30, 0x32, 0x31, 0x33), frozenset(range(0xFC, 0x100))))
_reg(StampSpec(TOOL_HOSPITAL, "Hospital", ID_HOSPITAL, 3, 3, COST_HOSPITAL, 0x01, 0x08,
               (0x56, 0x58, 0x5B, 0x57, 0x5A, 0x5D, 0x59, 0x5C, 0x5E),
               frozenset({0xFB})))
_reg(StampSpec(TOOL_FACTORY, "Factory", ID_FACTORY, 3, 3, COST_FACTORY, 0x01, 0x0C,
               (0x3E, 0x40, 0x43, 0x3F, 0x42, 0x45, 0x41, 0x44, 0x46),
               frozenset({0xFA}), extra19=0))
_reg(StampSpec(TOOL_BARRACKS, "Barracks", ID_BARRACKS, 3, 3, COST_BARRACKS, 0x01, DRAW_BARRACKS,
               _BARRACKS_VAR, frozenset({ID_BARRACKS})))
_reg(StampSpec(TOOL_SHRINE, "Shrine", ID_SHRINE, 1, 1, COST_SHRINE, 0x01, 0x00,
               (0x3C,), frozenset(range(0xA2, 0xA6))))
_reg(StampSpec(TOOL_PLAZA, "Plaza", ID_PLAZA, 1, 1, COST_PLAZA, FLAG_PAD, 0x04,
               (0x74,), frozenset({0x7C, 0x7D, 0x7E}), need_road=True))

_STAMP_SIZE.update({s.tool: s.w for s in _STAMPS.values() if s.w == s.h})
_PAIR_SIBLING = {
    0xE9: 0xEA, 0xEA: 0xE9, 0xEB: 0xEC, 0xEC: 0xEB,
    0xED: 0xEE, 0xEE: 0xED, 0xEF: 0xF0, 0xF0: 0xEF,
}


def in_map(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def is_river(city: CityMap, x: int, y: int) -> bool:
    if not in_map(x, y):
        return False
    return bool(city.tiles[city.offset(x, y) + 1] & FLAG_RIVER)


def is_bridge(city: CityMap, x: int, y: int) -> bool:
    """River + pad. EXE wipe 0x6985B restores +0 from +9 on this pair."""
    if not in_map(x, y):
        return False
    flags = city.tiles[city.offset(x, y) + 1]
    return bool(flags & FLAG_RIVER) and bool(flags & FLAG_PAD)


def is_bridgeable_river(city: CityMap, x: int, y: int) -> bool:
    """Straight only. 669C6 skips +1 & 0x08; remaps +0 in 0x1E–0x2D."""
    if not in_map(x, y):
        return False
    off = city.offset(x, y)
    tid = city.tiles[off]
    flags = city.tiles[off + 1]
    if not (flags & FLAG_RIVER) or (flags & FLAG_RIVER_BANK):
        return False
    return ID_STRAIGHT_LO <= tid < ID_STRAIGHT_HI


def has_adjacent_bridge(city: CityMap, x: int, y: int) -> bool:
    """True if a cardinal neighbour is already a bridge. EXE 665DF is 4-way."""
    return any(is_bridge(city, x + dx, y + dy) for dx, dy in _CARDINALS)


def bridge_id_for(tid: int) -> int:
    return ID_BRIDGE_LO + ((tid - ID_STRAIGHT_LO) >> 2)


def is_city_road(city: CityMap, x: int, y: int) -> bool:
    if not in_map(x, y):
        return False
    off = city.offset(x, y)
    tid = city.tiles[off]
    flags = city.tiles[off + 1]
    if flags & FLAG_RIVER:
        return bool(flags & FLAG_PAD)
    if ID_ROAD_LO <= tid <= ID_ROAD_HI:
        return True
    return tid < ID_TERRAIN_MAX and bool(flags & FLAG_PAD)


def _road_mask(city: CityMap, x: int, y: int) -> int:
    mask = 0
    bit = 1
    for dx, dy in _CARDINALS:
        if is_city_road(city, x + dx, y + dy):
            mask |= bit
        bit <<= 1
    return mask


def road_id_for(city: CityMap, x: int, y: int) -> int:
    return _ROAD_FROM_MASK[_road_mask(city, x, y)]


def _write_terrain(
    city: CityMap, x: int, y: int, tid: int, flags: int, *, wipe: bool = False
) -> None:
    off = city.offset(x, y)
    city.tiles[off] = tid & 0xFF
    city.tiles[off + 1] = flags & 0xFF
    city.tiles[off + 3] = 0
    city.tiles[off + 4] = 0
    if wipe:
        city.tiles[off + 9] = 0
        city.tiles[off + 10] = 0


def _retile_roads(city: CityMap, cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Rewrite existing city-road ids only. Never promote grass / pipe / aqueduct.

    ``is_city_road`` treats leftover ``FLAG_PAD`` on terrain as a road neighbour
    (so a real 0x52 can T-junction). Writing ``road_id_for`` onto that grass
    is what minted the fake 0x52 next to an aqueduct.
    """
    dirty: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for x, y in cells:
        if (x, y) in seen or not is_city_road(city, x, y):
            continue
        seen.add((x, y))
        if is_bridge(city, x, y):
            dirty.append((x, y))
            continue
        if is_aqueduct(city, x, y) or is_pipe(city, x, y):
            continue
        off = city.offset(x, y)
        tid = city.tiles[off]
        if not (ID_ROAD_LO <= tid <= ID_ROAD_HI):
            continue
        city.tiles[off] = road_id_for(city, x, y)
        city.tiles[off + 1] = (city.tiles[off + 1] | FLAG_PAD) & 0xFF
        dirty.append((x, y))
    return dirty


def _write_bridge(city: CityMap, x: int, y: int) -> int:
    off = city.offset(x, y)
    old = city.tiles[off]
    city.tiles[off + 9] = old
    bid = bridge_id_for(old)
    city.tiles[off] = bid
    city.tiles[off + 1] = (FLAG_RIVER | FLAG_PAD) & 0xFF
    city.tiles[off + 3] = 0
    city.tiles[off + 4] = 0
    return bid


def _clear_bridge(city: CityMap, x: int, y: int) -> int:
    off = city.offset(x, y)
    saved = city.tiles[off + 9]
    city.tiles[off] = saved
    city.tiles[off + 1] = FLAG_RIVER
    city.tiles[off + 3] = 0
    city.tiles[off + 4] = 0
    city.tiles[off + 9] = 0
    return saved


def _debit(sim: SimState | None, cost: int) -> str | None:
    if cost <= 0 or sim is None:
        return None
    if sim.treasury < cost:
        return f"tesouro {sim.treasury} < custo {cost}"
    sim.treasury -= cost
    return None


def _neighbor_ring(x: int, y: int) -> list[tuple[int, int]]:
    return [(x + dx, y + dy) for dx, dy in _CARDINALS]


# Tall HOUSES1 extra_rows overlap neighbor diamonds (more than 4-neighbours).
# Aqueduct is CITYFIXT type-1 (diamond dest Y; extra_rows is not a lift).
_TALL_TOOLS = frozenset(
    {
        TOOL_RESERVOIR,
        TOOL_PREFECTURE,
        TOOL_BARRACKS,
        TOOL_AQUEDUCT,
        TOOL_TEMPLE,
        TOOL_BASILICA,
        TOOL_AVENTINE,
        TOOL_JANICULAN,
        TOOL_PALATINE,
        TOOL_THEATER,
        TOOL_ODEUM,
        TOOL_COLISEUM,
        TOOL_CIRCUS,
        TOOL_CMAXIMUS,
        TOOL_GRAMMATICUS,
        TOOL_RHETOR,
        TOOL_LIBRARY,
        TOOL_BATHS,
        TOOL_MARKET,
        TOOL_HOSPITAL,
        TOOL_FACTORY,
    }
)


def iso_neighborhood(
    x: int, y: int, radius: int | None = None
) -> list[tuple[int, int]]:
    """Self + Chebyshev ring covering extra_rows and painter-front tiles."""
    r = iso_overlap_radius() if radius is None else radius
    cells: list[tuple[int, int]] = []
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            nx, ny = x + dx, y + dy
            if in_map(nx, ny):
                cells.append((nx, ny))
    return cells


def expand_iso_dirty(
    dirty: list[tuple[int, int]], seeds: list[tuple[int, int]]
) -> list[tuple[int, int]]:
    extra: list[tuple[int, int]] = []
    for sx, sy in seeds:
        extra.extend(iso_neighborhood(sx, sy))
    return list(dict.fromkeys([*dirty, *extra]))


def footprint_cells(x: int, y: int, size: int) -> list[tuple[int, int]]:
    """Inclusive NW-origin N×N block, raster y then x."""
    return footprint_rect(x, y, size, size)


def footprint_rect(x: int, y: int, w: int, h: int) -> list[tuple[int, int]]:
    """Inclusive NW-origin w×h block, raster y then x."""
    out: list[tuple[int, int]] = []
    for dy in range(h):
        for dx in range(w):
            out.append((x + dx, y + dy))
    return out


def footprint_type(tid: int) -> int:
    """DAT_00094FE5[id] for id ≥ 0x82. Clear dispatcher 0x68D41."""
    if tid < 0x82 or tid > 0xFF:
        return 0
    return _DAT_94FE5_FROM_82[tid - 0x82]


def clears_to_rubble(tid: int) -> bool:
    """City Clear collapse (``0x68D2F`` ``cmp +0, 0x82`` / ``jl`` flatten).

    ``id >= 0x82`` → ``FUN_000696e8`` (host rubble ``0x05``). Gardens
    ``0x78–0x7B`` and plaza/join/statue ``0x7C–0x7E`` are below that
    line and flatten via ``FUN_000697fe`` (EXE grass ``0x1A–0x1D``;
    host ``0x1C``). Housing / fire collapse still uses rubble.
    """
    return tid >= 0x82


def building_footprint_size(tid: int) -> int:
    """N for an N×N wipe. 0x68D54: type 4/9/0x10 → 2/3/4; else 1×1."""
    kind = footprint_type(tid)
    if kind == 4:
        return 2
    if kind == 9:
        return 3
    if kind == 0x10:
        return 4
    return 1


def is_road_occupied(city: CityMap, x: int, y: int) -> bool:
    """True when 669C6 @ 0x66B8D will not write a road id (+0 ≥ 0x7C)."""
    if not in_map(x, y):
        return True
    return city.tiles[city.offset(x, y)] >= ID_ROAD_OCCUPIED


def building_group_cells(city: CityMap, x: int, y: int) -> list[tuple[int, int]]:
    """FUN_00069483: origin from +5 lo-nibble, then size×size east/south.

    piece % N = column, piece / N = row. id < 0x82 (or type not 4/9/16)
    is 1×1. Circus pair 0xE9–0xF0 (second N×N after the first wipe) is
    not ported this pass.
    """
    if not in_map(x, y):
        return []
    off = city.offset(x, y)
    tid = city.tiles[off]
    size = building_footprint_size(tid)
    if size <= 1:
        return [(x, y)]
    piece = city.tiles[off + 5] & 0xF
    col = piece % size
    row = piece // size
    ox, oy = x - col, y - row
    cells = [
        c
        for c in footprint_cells(ox, oy, size)
        if in_map(c[0], c[1])
    ]
    sib = _PAIR_SIBLING.get(tid)
    if sib is not None:
        for dx, dy in ((size, 0), (-size, 0), (0, size), (0, -size)):
            nx, ny = ox + dx, oy + dy
            if in_map(nx, ny) and city.tiles[city.offset(nx, ny)] == sib:
                cells.extend(
                    c
                    for c in footprint_cells(nx, ny, size)
                    if in_map(c[0], c[1]) and c not in cells
                )
                break
    return cells


def is_long_pair_building(tid: int) -> bool:
    """Circus 0xE9–0xEC and C.Maximus 0xED–0xF0 — two N×N halves, not one square."""
    return 0xE9 <= (int(tid) & 0xFF) <= 0xF0


def stamp_wh(tool: str, facing: int = 0) -> tuple[int, int]:
    spec = _STAMPS.get(tool)
    if spec is not None:
        if spec.tid2 and (int(facing) & 1):
            return spec.h, spec.w
        return spec.w, spec.h
    n = _STAMP_SIZE.get(tool, 1)
    return n, n


def stamp_size(tool: str) -> int:
    """N for a square stamp. Non-square uses max(w,h) only as a fallback."""
    w, h = stamp_wh(tool)
    return w if w == h else max(w, h)


def _pair_axis_spec(
    spec: StampSpec, facing: int
) -> tuple[int, int, int, tuple[int, ...], int, tuple[int, ...]]:
    """w, h, tid, variants, tid2, variants2 for this view facing.

    Odd facing swaps the long axis and the leftover orientation pair
    (Achea NS Circus 0xE9+0xEA / leftover C.Max 0xEF+0xF0).
    """
    if spec.tid2 and (int(facing) & 1):
        if spec.tool == TOOL_CIRCUS:
            return (
                spec.h, spec.w,
                ID_CIRCUS_A, _CIRCUS_NS_VAR, ID_CIRCUS_B, _CIRCUS_NS_VAR2,
            )
        if spec.tool == TOOL_CMAXIMUS:
            return (
                spec.h, spec.w,
                ID_CMAX_C, _CMAX_EW_VAR, ID_CMAX_D, _CMAX_EW_VAR2,
            )
        return spec.h, spec.w, spec.tid, spec.variants, spec.tid2, spec.variants2
    return spec.w, spec.h, spec.tid, spec.variants, spec.tid2, spec.variants2


def stamp_ghost_pieces(
    tool: str, facing: int = 0
) -> list[tuple[int, int, int, int, int]]:
    """(dx, dy, terrain_id, draw, variant) relative to the NW origin."""
    if tool == TOOL_RESERVOIR:
        return [(0, 0, ID_RESERVOIR, DRAW_RESERVOIR, VAR_RESERVOIR)]
    spec = _STAMPS.get(tool)
    if spec is None:
        return []
    out: list[tuple[int, int, int, int, int]] = []
    if spec.tid2 and spec.variants2:
        # First half fills the NW block; second half is east (w>h) or south.
        # Native +4 for this axis — do not N×N-remap halves (that stamps the
        # origin piece on one end after paint remap).
        w, h, tid, vars1, tid2, vars2 = _pair_axis_spec(spec, facing)
        hw = w // 2 if w > h else w
        hh = h if w > h else h // 2
        ox2, oy2 = (hw, 0) if w > h else (0, hh)
        for i, var in enumerate(vars1):
            dx, dy = i % hw, i // hw
            out.append((dx, dy, tid, spec.draw, var))
        for i, var in enumerate(vars2):
            dx, dy = i % hw, i // hw
            out.append((ox2 + dx, oy2 + dy, tid2, spec.draw, var))
        return out
    for i, var in enumerate(spec.variants):
        dx, dy = i % spec.w, i // spec.w
        out.append((dx, dy, spec.tid, spec.draw, var))
    return _orient_stamp_ghost(out, facing)


def _orient_stamp_ghost(
    pieces: list[tuple[int, int, int, int, int]], facing: int
) -> list[tuple[int, int, int, int, int]]:
    """Keep facing-0 +4 on the visual slot (same remap as iso paint)."""
    f = int(facing) & 3
    if f == 0 or len(pieces) <= 1:
        return pieces

    def _square_block(
        block: list[tuple[int, int, int, int, int]],
    ) -> list[tuple[int, int, int, int, int]] | None:
        by_xy = {(dx, dy): (tid, draw, var) for dx, dy, tid, draw, var in block}
        xs = [p[0] for p in block]
        ys = [p[1] for p in block]
        ox, oy = min(xs), min(ys)
        n = max(max(xs) - ox + 1, max(ys) - oy + 1)
        if n * n != len(by_xy):
            return None
        if any((ox + dx, oy + dy) not in by_xy for dy in range(n) for dx in range(n)):
            return None
        out: list[tuple[int, int, int, int, int]] = []
        for dy in range(n):
            for dx in range(n):
                slx, sly = rotate_footprint_local(dx, dy, n, f)
                tid, draw, var = by_xy[(ox + slx, oy + sly)]
                out.append((ox + dx, oy + dy, tid, draw, var))
        return out

    square = _square_block(pieces)
    if square is not None:
        return square
    groups: dict[int, list[tuple[int, int, int, int, int]]] = {}
    for piece in pieces:
        groups.setdefault(piece[2], []).append(piece)
    if len(groups) < 2:
        return pieces
    out: list[tuple[int, int, int, int, int]] = []
    for block in groups.values():
        remapped = _square_block(block)
        if remapped is None:
            return pieces
        out.extend(remapped)
    return out


def is_aqueduct(city: CityMap, x: int, y: int) -> bool:
    if not in_map(x, y):
        return False
    tid = city.tiles[city.offset(x, y)]
    return ID_AQUEDUCT_LO <= tid <= ID_AQUEDUCT_HI


def is_reservoir(city: CityMap, x: int, y: int) -> bool:
    if not in_map(x, y):
        return False
    return city.tiles[city.offset(x, y)] == ID_RESERVOIR


def is_pipe(city: CityMap, x: int, y: int) -> bool:
    """Reservoir or aqueduct — ``+1 & 0xC0`` graph (ghidra_water.md)."""
    if not in_map(x, y):
        return False
    tid = city.tiles[city.offset(x, y)]
    if tid == ID_RESERVOIR:
        return True
    return ID_AQUEDUCT_LO <= tid <= ID_AQUEDUCT_HI


def is_plain_city_road(city: CityMap, x: int, y: int) -> bool:
    """Terrain road ``0x52–0x5C`` only — not grass+PAD and not a bridge."""
    if not in_map(x, y):
        return False
    tid = city.tiles[city.offset(x, y)]
    return ID_ROAD_LO <= tid <= ID_ROAD_HI


def is_aqueduct_road_combo(city: CityMap, x: int, y: int) -> bool:
    """Aqueduct over road: ``FUN_00067a6a`` sets ``+3 |= 0x80`` (0x90)."""
    if not is_aqueduct(city, x, y):
        return False
    return bool(city.tiles[city.offset(x, y) + 3] & 0x80)


def _is_water_source_adj(city: CityMap, x: int, y: int) -> bool:
    """Cardinal neighbour has ``+1 & 0x18`` (FUN_0002a18c)."""
    for dx, dy in _CARDINALS:
        nx, ny = x + dx, y + dy
        if in_map(nx, ny) and (city.tiles[city.offset(nx, ny) + 1] & FLAG_WATER_SOURCE):
            return True
    return False


def _pipe_component(city: CityMap, seeds: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    stack = [c for c in seeds if is_pipe(city, c[0], c[1])]
    while stack:
        x, y = stack.pop()
        if (x, y) in seen:
            continue
        seen.add((x, y))
        for nx, ny in _neighbor_ring(x, y):
            if (nx, ny) not in seen and is_pipe(city, nx, ny):
                stack.append((nx, ny))
    return list(seen)


def _reset_pipe_tile(city: CityMap, x: int, y: int) -> None:
    off = city.offset(x, y)
    city.tiles[off + 10] &= ~3
    city.tiles[off + 4] = city.tiles[off + 9]


def _apply_pipe_charge(city: CityMap, x: int, y: int, charge: int) -> bool:
    off = city.offset(x, y)
    old = city.tiles[off + 10] & 3
    if old >= charge:
        return False
    city.tiles[off + 10] = (city.tiles[off + 10] & ~3) | (charge & 3)
    dry = city.tiles[off + 9]
    if city.tiles[off + 1] & FLAG_RESERVOIR:
        bump = charge
    else:
        bump = 2 if charge >= 3 else 1
    city.tiles[off + 4] = (dry + bump) & 0xFF
    return True


def _is_river_fed_reservoir(city: CityMap, x: int, y: int) -> bool:
    """Charge seed: Reservoir 0xBE whose cardinal neighbour is river ``+1&0x18``."""
    return is_reservoir(city, x, y) and _is_water_source_adj(city, x, y)


def rebuild_pipe_charge(city: CityMap, seeds: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Place/Clear stand-in for FUN_00029e36.

    Dry every pipe in the component (``+4 = +9``), then charge 3 only from
    a river-fed reservoir and walk the ``+1 & 0xC0`` graph. Isolated or
    disconnected aqueduct stays dry — do not seed from an aqueduct that
    merely touches river.
    """
    cells = _pipe_component(city, seeds)
    if not cells:
        return []
    for x, y in cells:
        _reset_pipe_tile(city, x, y)
    sources: list[tuple[int, int]] = []
    for x, y in cells:
        if _is_river_fed_reservoir(city, x, y):
            _apply_pipe_charge(city, x, y, 3)
            sources.append((x, y))
    seen = set(sources)
    stack = list(sources)
    while stack:
        x, y = stack.pop()
        for nx, ny in _neighbor_ring(x, y):
            if (nx, ny) in seen or not is_pipe(city, nx, ny):
                continue
            _apply_pipe_charge(city, nx, ny, 3)
            seen.add((nx, ny))
            if not (city.tiles[city.offset(nx, ny) + 1] & FLAG_RESERVOIR):
                stack.append((nx, ny))
    return cells


def aqueduct_connects(
    city: CityMap,
    x: int,
    y: int,
    pending: set[tuple[int, int]] | None = None,
) -> bool:
    """First segment must touch a reservoir or an aqueduct (4-neighbour)."""
    for dx, dy in _CARDINALS:
        nx, ny = x + dx, y + dy
        if pending is not None and (nx, ny) in pending:
            return True
        if is_reservoir(city, nx, ny) or is_aqueduct(city, nx, ny):
            return True
    return False


def _write_building(
    city: CityMap,
    x: int,
    y: int,
    tid: int,
    flags: int,
    draw: int,
    variant: int,
    *,
    piece: int = 0,
    dry: int | None = None,
    special: int | None = None,
) -> None:
    off = city.offset(x, y)
    city.tiles[off] = tid & 0xFF
    city.tiles[off + 1] = flags & 0xFF
    city.tiles[off + 3] = draw & 0xFF
    city.tiles[off + 4] = variant & 0xFF
    city.tiles[off + 5] = piece & 0xFF
    if dry is not None:
        city.tiles[off + 9] = dry & 0xFF
    if special is not None:
        city.tiles[off + 19] = special & 0xFF


def is_garden_id(tid: int) -> bool:
    return ID_GARDEN <= tid <= ID_GARDEN_HI


def garden_from_step(step: int) -> tuple[int, int]:
    """``(id, +4)`` for the *n*th stamp in a stroke.

    ``FUN_00068950`` increments ``[0x117A60]`` first, wraps at ``0x40``,
    then ``n = DAT_00093FCC[i] >> 2`` → ``+0 = 0x78+n``, ``+4 = 0x77+n``.
    Host starts each stroke at 0 (EXE saves/restores that byte).
    """
    idx = step + 1
    while idx >= 0x40:
        idx -= 0x40
    n = _GARDEN_LUT[idx] >> 2
    return 0x78 + n, 0x77 + n


def garden_preview_cells(
    ok: list[tuple[int, int]],
    stamp: list[tuple[int, int]],
) -> list[tuple[int, int, int, int]]:
    """``(x, y, id, +4)`` for stamp cells, same order as commit."""
    stamp_set = set(stamp)
    out: list[tuple[int, int, int, int]] = []
    step = 0
    for x, y in ok:
        if (x, y) not in stamp_set:
            continue
        tid, var = garden_from_step(step)
        out.append((x, y, tid, var))
        step += 1
    return out


def is_plaza_id(tid: int) -> bool:
    return ID_PLAZA <= tid <= ID_PLAZA_STATUE


def is_wall_id(tid: int) -> bool:
    return tid in (ID_WALL_NS, ID_WALL_EW, ID_GATE)


def _wall_neighbor_mask(city: CityMap, x: int, y: int) -> int:
    """Cardinal Wall 0xC1/0xC2 / Gate 0xC0. N=1 E=2 S=4 W=8."""
    mask = 0
    bit = 1
    for dx, dy in _CARDINALS:
        nx, ny = x + dx, y + dy
        if in_map(nx, ny) and is_wall_id(city.tiles[city.offset(nx, ny)]):
            mask |= bit
        bit <<= 1
    return mask


def tower_variant_for(mask: int) -> int:
    """0xBF +4. No wall neighbour → standalone (no wall-cap extras)."""
    return _TOWER_FROM_MASK.get(mask & 0x0F, VAR_TOWER_ALONE)


def _retile_towers(city: CityMap, cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    dirty: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for x, y in cells:
        if (x, y) in seen or not in_map(x, y):
            continue
        seen.add((x, y))
        off = city.offset(x, y)
        if city.tiles[off] != ID_TOWER:
            continue
        var = tower_variant_for(_wall_neighbor_mask(city, x, y))
        if city.tiles[off + 4] == var:
            continue
        city.tiles[off + 4] = var
        dirty.append((x, y))
    return dirty


def _plaza_touches_road(
    city: CityMap, x: int, y: int, pending: set[tuple[int, int]] | None = None
) -> bool:
    """Plaza sits on a road cell or a cardinal road / plaza neighbour."""
    if is_city_road(city, x, y) and not is_river(city, x, y):
        return True
    for dx, dy in _CARDINALS:
        nx, ny = x + dx, y + dy
        if pending is not None and (nx, ny) in pending:
            return True
        if not in_map(nx, ny):
            continue
        tid = city.tiles[city.offset(nx, ny)]
        if is_plaza_id(tid) or is_city_road(city, nx, ny):
            return True
    return False


def _civic_kind(
    city: CityMap,
    x: int,
    y: int,
    already: int,
    family: frozenset[int] | None = None,
    *,
    allow_road: bool = False,
    need_road: bool = False,
    pending: set[tuple[int, int]] | None = None,
) -> str:
    """'stamp' / 'keep' (already this id) / 'skip' (river, road, other building)."""
    if not in_map(x, y) or is_river(city, x, y):
        return "skip"
    tid = city.tiles[city.offset(x, y)]
    fam = family or frozenset({already} if already else ())
    if already == ID_GARDEN and is_garden_id(tid):
        return "keep"
    if tid in fam or tid == already:
        return "keep"
    if need_road and not _plaza_touches_road(city, x, y, pending):
        return "skip"
    if is_city_road(city, x, y) and not allow_road:
        return "skip"
    if tid >= ID_TERRAIN_MAX:
        return "skip"
    return "stamp"


def _pipe_mask(
    city: CityMap,
    x: int,
    y: int,
    pending: set[tuple[int, int]] | None = None,
) -> int:
    """Cardinal pipe mask. N=1 E=2 S=4 W=8 — same bits as ``FUN_0002a0db``."""
    mask = 0
    bit = 1
    for dx, dy in _CARDINALS:
        nx, ny = x + dx, y + dy
        if pending is not None and (nx, ny) in pending:
            mask |= bit
        elif is_pipe(city, nx, ny):
            mask |= bit
        bit <<= 1
    return mask


# FUN_00067a6a table 0x94D8F × 14 (matcher 0x6C826). Isolated → stub 0xCB.
# T/cross are not in that table; 20230610 / FELIPE write D5 (NS through)
# or D6 (EW through / cross) with +1=0x60.
_AQUEDUCT_FROM_MASK: dict[int, int] = {
    0x0: 0xCB,
    0x1: 0xCC,
    0x2: 0xCD,
    0x4: 0xCB,
    0x8: 0xCE,
    0x5: 0xCF,
    0xA: 0xD0,
    0x3: 0xD1,
    0x6: 0xD2,
    0xC: 0xD3,
    0x9: 0xD4,
}


def aqueduct_id_for(mask: int) -> int:
    """4-neighbour pipe mask → ``0xCB–0xD6``.

    Ends / straights / corners from LUT ``0x94D8F``. Three-or-more
    connections: ``0xD5`` if both N+S and not both E+W, else ``0xD6``.
    """
    hit = _AQUEDUCT_FROM_MASK.get(mask & 0x0F)
    if hit is not None:
        return hit
    ns = mask & 0x05
    ew = mask & 0x0A
    if ns == 0x05 and ew != 0x0A:
        return 0xD5
    return 0xD6


def aqueduct_road_id_for(mask: int) -> int:
    """LUT ``0x94E37``: NS pipe over road → ``0xD5``, else ``0xD6`` (EW)."""
    ns = mask & 0x05
    ew = mask & 0x0A
    if ns and not ew:
        return ID_AQUEDUCT_ROAD_NS
    return ID_AQUEDUCT_ROAD_EW


# FUN_00067a6a reservoir branch: matcher 0x94E7F ×16 → dry +4/+9.
# Charge later adds 1/2/3 onto +4 (Achea / 20230610).
_RESERVOIR_DRY: dict[int, int] = {
    0x0: 0x6E,
    0x1: 0x72,
    0x2: 0x76,
    0x4: 0x7A,
    0x8: 0x7E,
    0x3: 0x82,
    0x6: 0x86,
    0xC: 0x8A,
    0x9: 0x8E,
    0x5: 0x92,
    0xA: 0x96,
    0x7: 0x9A,
    0xE: 0x9E,
    0xD: 0xA2,
    0xB: 0xA6,
    0xF: 0xAA,
}


def reservoir_dry_for(mask: int) -> int:
    """Pipe-neighbour mask → HOUSES1 dry ``+9`` (inlet on the tank)."""
    return _RESERVOIR_DRY.get(mask & 0x0F, VAR_RESERVOIR)


# Dry +9 from 20230610 / FELIPE / Achea. Charge rebuild bumps +4.
_AQUEDUCT_DRY: dict[int, int] = {
    0xCB: 0x79,
    0xCC: 0x79,
    0xCD: 0x76,
    0xCE: 0x76,
    0xCF: 0x79,
    0xD0: 0x76,
    0xD1: 0x7C,
    0xD2: 0x7F,
    0xD3: 0x82,
    0xD4: 0x85,
    0xD5: 0x73,
    0xD6: 0x70,
}


def _aqueduct_variant(tid: int) -> int:
    return _AQUEDUCT_DRY.get(tid, 0x79)


def _is_road_combo_cell(city: CityMap, x: int, y: int) -> bool:
    return is_plain_city_road(city, x, y) or is_aqueduct_road_combo(city, x, y)


def _write_aqueduct_cell(city: CityMap, x: int, y: int) -> int:
    mask = _pipe_mask(city, x, y)
    if _is_road_combo_cell(city, x, y):
        tid = aqueduct_road_id_for(mask)
        flags = FLAG_PIPE | FLAG_PAD
        draw = DRAW_AQUEDUCT_ROAD
    else:
        tid = aqueduct_id_for(mask)
        flags = FLAG_PIPE
        if tid in (0xD5, 0xD6):
            flags |= FLAG_PAD
        draw = DRAW_AQUEDUCT
    var = _aqueduct_variant(tid)
    _write_building(city, x, y, tid, flags, draw, var, dry=var)
    return tid


def aqueduct_preview_cells(
    city: CityMap,
    ok: list[tuple[int, int]],
    stamp: list[tuple[int, int]],
) -> list[tuple[int, int, int, int]]:
    """``(x, y, id, +4)`` for the rubber-band line, same autotile as commit."""
    pending = set(stamp)
    out: list[tuple[int, int, int, int]] = []
    for x, y in ok:
        mask = _pipe_mask(city, x, y, pending)
        if _is_road_combo_cell(city, x, y):
            tid = aqueduct_road_id_for(mask)
        else:
            tid = aqueduct_id_for(mask)
        out.append((x, y, tid, _aqueduct_variant(tid)))
    return out


def _retile_aqueducts(city: CityMap, cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    dirty: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for x, y in cells:
        if (x, y) in seen or not is_aqueduct(city, x, y):
            continue
        seen.add((x, y))
        _write_aqueduct_cell(city, x, y)
        dirty.append((x, y))
    return dirty


def _write_reservoir_cell(city: CityMap, x: int, y: int) -> int:
    dry = reservoir_dry_for(_pipe_mask(city, x, y))
    _write_building(
        city, x, y, ID_RESERVOIR, FLAG_RESERVOIR, DRAW_RESERVOIR, dry, dry=dry
    )
    return ID_RESERVOIR


def _retile_reservoirs(city: CityMap, cells: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Rewrite 0xBE +9 from LUT 0x94E7F. Charge rebuild updates +4."""
    dirty: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()
    for x, y in cells:
        if (x, y) in seen or not is_reservoir(city, x, y):
            continue
        seen.add((x, y))
        off = city.offset(x, y)
        dry = reservoir_dry_for(_pipe_mask(city, x, y))
        if city.tiles[off + 9] == dry:
            continue
        city.tiles[off + 9] = dry
        dirty.append((x, y))
    return dirty


def _civic_unit_cost(tool: str) -> int:
    spec = _STAMPS.get(tool)
    if spec is not None:
        return spec.cost
    if tool == TOOL_GARDEN:
        return COST_GARDEN
    if tool == TOOL_WELL:
        return COST_WELL
    if tool == TOOL_FOUNTAIN:
        return COST_FOUNTAIN
    if tool == TOOL_PREFECTURE:
        return COST_PREFECTURE
    if tool == TOOL_TOWER:
        return COST_TOWER
    if tool == TOOL_RESERVOIR:
        return COST_RESERVOIR
    if tool == TOOL_WALL:
        return COST_WALL
    return 0


def _civic_already_id(tool: str) -> int:
    spec = _STAMPS.get(tool)
    if spec is not None:
        return spec.tid
    if tool == TOOL_GARDEN:
        return ID_GARDEN
    if tool == TOOL_WELL:
        return ID_WELL
    if tool == TOOL_FOUNTAIN:
        return ID_FOUNTAIN
    if tool == TOOL_PREFECTURE:
        return ID_PREFECTURE
    if tool == TOOL_TOWER:
        return ID_TOWER
    if tool == TOOL_RESERVOIR:
        return ID_RESERVOIR
    if tool == TOOL_AQUEDUCT:
        return ID_AQUEDUCT_STUB
    if tool == TOOL_WALL:
        return ID_WALL_EW
    return 0


def _stamp_family(tool: str) -> frozenset[int]:
    spec = _STAMPS.get(tool)
    if spec is not None:
        return spec.family
    already = _civic_already_id(tool)
    return frozenset({already} if already else ())


def _kind_for_tool(
    city: CityMap,
    x: int,
    y: int,
    tool: str,
    pending: set[tuple[int, int]] | None = None,
) -> str:
    if tool == TOOL_AQUEDUCT:
        return _aqueduct_kind(city, x, y, pending)
    if tool == TOOL_WALL:
        return _wall_kind(city, x, y)
    spec = _STAMPS.get(tool)
    already = _civic_already_id(tool)
    family = spec.family if spec is not None else _stamp_family(tool)
    return _civic_kind(
        city,
        x,
        y,
        already,
        family,
        allow_road=tool == TOOL_PLAZA,
        need_road=bool(spec.need_road) if spec is not None else False,
        pending=pending,
    )


def _tool_label(tool: str) -> str:
    spec = _STAMPS.get(tool)
    if spec is not None:
        return spec.label
    return {
        TOOL_GARDEN: "Gardens",
        TOOL_WELL: "Well",
        TOOL_FOUNTAIN: "Fountain",
        TOOL_PREFECTURE: "Praefecture",
        TOOL_TOWER: "Tower",
        TOOL_RESERVOIR: "Reservoir",
        TOOL_AQUEDUCT: "Aqueduct",
        TOOL_WALL: "Wall",
        TOOL_BARRACKS: "Barracks",
    }.get(tool, tool)


def _write_garden(city: CityMap, x: int, y: int, step: int = 0) -> str:
    tid, var = garden_from_step(step)
    _write_building(city, x, y, tid, 0x01, DRAW_GARDEN, var)
    return f"Garden {tid:#x} em ({x},{y})"


def _write_civic_1x1(city: CityMap, x: int, y: int, tool: str, *, step: int = 0) -> str:
    if tool == TOOL_GARDEN:
        return _write_garden(city, x, y, step)
    if tool == TOOL_WELL:
        _write_building(city, x, y, ID_WELL, 0x01, DRAW_WELL, VAR_WELL)
        return f"Well 0xD7 em ({x},{y})"
    if tool == TOOL_FOUNTAIN:
        _write_building(city, x, y, ID_FOUNTAIN, 0x01, DRAW_FOUNTAIN, VAR_FOUNTAIN)
        return f"Fountain 0xDD em ({x},{y})"
    if tool == TOOL_PREFECTURE:
        _write_building(city, x, y, ID_PREFECTURE, 0x01, DRAW_PREFECTURE, VAR_PREFECTURE)
        return f"Praefecture 0xE3 em ({x},{y})"
    if tool == TOOL_TOWER:
        var = tower_variant_for(_wall_neighbor_mask(city, x, y))
        _write_building(city, x, y, ID_TOWER, FLAG_TOWER, DRAW_TOWER, var)
        return f"Tower 0xBF em ({x},{y})"
    if tool == TOOL_RESERVOIR:
        _write_reservoir_cell(city, x, y)
        return f"Reservoir 0xBE em ({x},{y})"
    if tool == TOOL_AQUEDUCT:
        tid = _write_aqueduct_cell(city, x, y)
        return f"Aqueduct {tid:#x} em ({x},{y})"
    spec = _STAMPS.get(tool)
    if spec is not None and spec.w == 1 and spec.h == 1:
        _write_building(
            city, x, y, spec.tid, spec.flags, spec.draw, spec.variants[0]
        )
        return f"{spec.label} {spec.tid:#x} em ({x},{y})"
    return f"civic {tool} em ({x},{y})"


def _write_stamp(
    city: CityMap, ox: int, oy: int, spec: StampSpec, facing: int = 0
) -> list[tuple[int, int]]:
    dirty: list[tuple[int, int]] = []
    # Square N×N keeps facing-0 +4 in world bytes (paint remaps). Paired
    # long stamps write the orientation pair for this facing (no paint remap).
    write_face = facing if spec.tid2 else 0
    w, h = stamp_wh(spec.tool, write_face)
    for dx, dy, tid, draw, variant in stamp_ghost_pieces(spec.tool, write_face):
        x, y = ox + dx, oy + dy
        piece = (dy * w + dx) & 0xF
        if spec.tid2 and w > h:
            piece = (dy * (w // 2) + (dx % (w // 2))) & 0xF
        elif spec.tid2:
            piece = ((dy % (h // 2)) * w + dx) & 0xF
        extra = spec.extra19 if (dx, dy) == (0, 0) else None
        if spec.tool == TOOL_FACTORY and (dx, dy) == (0, 0):
            extra = factory_goods()
        _write_building(
            city, x, y, tid, spec.flags, draw, variant,
            piece=piece, special=extra,
        )
        if spec.tool == TOOL_FACTORY and (dx, dy) == (0, 0):
            # 0x30415: OR +3 bit7 so flag80 blits CITYTOP[(+19)+9].
            # 0x3043B: OR +13 0x80 (factory splash for type-2 traders).
            off = city.offset(x, y)
            city.tiles[off + 3] |= 0x80
            city.tiles[off + 13] |= 0x80
        elif spec.tool == TOOL_FACTORY and (dx, dy) == (1, 0):
            # Career/D.SAV: +5 lo==1 also has bit7. 0x37F43 blits jugs
            # from west +9 (origin stock) at CITYTOP[hi+0x18].
            city.tiles[city.offset(x, y) + 3] |= 0x80
        dirty.append((x, y))
    return dirty


def _write_barracks(city: CityMap, ox: int, oy: int) -> list[tuple[int, int]]:
    return _write_stamp(city, ox, oy, _STAMPS[TOOL_BARRACKS])


def _wall_kind(city: CityMap, x: int, y: int) -> str:
    if not in_map(x, y) or is_river(city, x, y):
        return "skip"
    if is_city_road(city, x, y) and not is_bridge(city, x, y):
        return "stamp"
    tid = city.tiles[city.offset(x, y)]
    if is_wall_id(tid):
        return "keep"
    if tid >= ID_TERRAIN_MAX:
        return "skip"
    return "stamp"


def _write_wall_cell(city: CityMap, x: int, y: int, horizontal: bool) -> int:
    if is_city_road(city, x, y) and not is_bridge(city, x, y):
        var = 0x93 if horizontal else 0x92
        _write_building(city, x, y, ID_GATE, 0x24, 0x88, var)
        return ID_GATE
    tid = ID_WALL_EW if horizontal else ID_WALL_NS
    var = 0x04 if horizontal else 0x00
    _write_building(city, x, y, tid, 0x02, 0x08, var)
    return tid


def _aqueduct_kind(
    city: CityMap,
    x: int,
    y: int,
    pending: set[tuple[int, int]] | None = None,
) -> str:
    if not in_map(x, y) or is_river(city, x, y):
        return "skip"
    if is_aqueduct(city, x, y):
        return "keep"
    if is_plain_city_road(city, x, y):
        if not aqueduct_connects(city, x, y, pending):
            return "skip"
        return "stamp"
    if is_city_road(city, x, y):
        return "skip"
    if city.tiles[city.offset(x, y)] >= ID_TERRAIN_MAX:
        return "skip"
    if not aqueduct_connects(city, x, y, pending):
        return "skip"
    return "stamp"


def _classify_aqueduct_span(
    city: CityMap, cells: list[tuple[int, int]]
) -> tuple[list[tuple[int, int]], list[tuple[int, int]], list[tuple[int, int]]]:
    """Rubber-band classify. The line is one component — drag direction
    does not matter. A cell stamps if it can reach an existing reservoir
    or aqueduct through other stampable cells on the same line.
    """
    keep: set[tuple[int, int]] = set()
    candidates: set[tuple[int, int]] = set()
    for x, y in cells:
        if not in_map(x, y) or is_river(city, x, y):
            continue
        if is_aqueduct(city, x, y):
            keep.add((x, y))
            continue
        if is_plain_city_road(city, x, y):
            candidates.add((x, y))
            continue
        if is_city_road(city, x, y) or city.tiles[city.offset(x, y)] >= ID_TERRAIN_MAX:
            continue
        candidates.add((x, y))

    stack: list[tuple[int, int]] = []
    for x, y in candidates:
        if aqueduct_connects(city, x, y, keep):
            stack.append((x, y))

    reachable: set[tuple[int, int]] = set()
    while stack:
        cur = stack.pop()
        if cur in reachable:
            continue
        reachable.add(cur)
        cx, cy = cur
        for dx, dy in _CARDINALS:
            nxt = (cx + dx, cy + dy)
            if nxt in candidates and nxt not in reachable:
                stack.append(nxt)

    ok: list[tuple[int, int]] = []
    skip: list[tuple[int, int]] = []
    stamp: list[tuple[int, int]] = []
    for x, y in cells:
        cell = (x, y)
        if cell in keep:
            ok.append(cell)
        elif cell in reachable:
            ok.append(cell)
            stamp.append(cell)
        else:
            skip.append(cell)
    return ok, skip, stamp


def try_place(
    city: CityMap,
    x: int,
    y: int,
    tool: str,
    sim: SimState | None = None,
    facing: int = 0,
) -> PlaceResult:
    """Stamp one cell. River: road→bridge on straight, else refuse."""
    if not in_map(x, y):
        return PlaceResult(False, "fora do mapa")
    if tool == TOOL_QUERY:
        return PlaceResult(True, "query", query=query_tile(city, x, y))

    if tool == TOOL_TENT:
        if is_river(city, x, y):
            return PlaceResult(False, f"rio em ({x},{y}) — +1 & 0x10")
        if is_city_road(city, x, y) or city.tiles[city.offset(x, y)] >= ID_TERRAIN_MAX:
            return PlaceResult(False, f"ocupado em ({x},{y})")
        err = _debit(sim, COST_TENT)
        if err:
            return PlaceResult(False, err, cost=COST_TENT)
        _write_terrain(city, x, y, ID_TENT, 0x01)
        city.tiles[city.offset(x, y) + 15] = 1
        dirty = [(x, y)]
        dirty.extend(_retile_roads(city, _neighbor_ring(x, y)))
        return PlaceResult(True, f"Tent 0x82 em ({x},{y})", dirty=dirty, cost=COST_TENT)

    if tool == TOOL_ROAD:
        if is_river(city, x, y):
            if not is_bridgeable_river(city, x, y):
                return PlaceResult(
                    False, f"curva do rio em ({x},{y}) — sem ponte"
                )
            if has_adjacent_bridge(city, x, y):
                return PlaceResult(
                    False, f"ponte adjacente em ({x},{y}) — sem ponte"
                )
            bid = _write_bridge(city, x, y)
            dirty = [(x, y)]
            dirty.extend(_retile_roads(city, _neighbor_ring(x, y)))
            return PlaceResult(True, f"ponte {bid:#x} em ({x},{y})", dirty=dirty)
        if is_road_occupied(city, x, y):
            return PlaceResult(False, f"ocupado em ({x},{y}) — +0 >= 0x7C")
        _write_terrain(city, x, y, ID_ROAD_NS, FLAG_PAD)
        dirty = _retile_roads(city, [(x, y), *_neighbor_ring(x, y)])
        return PlaceResult(
            True,
            f"estrada {city.tiles[city.offset(x, y)]:#x} em ({x},{y})",
            dirty=dirty,
        )

    if tool == TOOL_CLEAR:
        if is_bridge(city, x, y):
            saved = _clear_bridge(city, x, y)
            dirty = [(x, y)]
            dirty.extend(_retile_roads(city, _neighbor_ring(x, y)))
            return PlaceResult(
                True, f"ponte -> rio {saved:#x} em ({x},{y})", dirty=dirty
            )
        if is_river(city, x, y):
            return PlaceResult(False, f"rio em ({x},{y}) — +1 & 0x10")
        tid = city.tiles[city.offset(x, y)]
        group = building_group_cells(city, x, y)
        if clears_to_rubble(tid) and len(group) > 1:
            dirty = []
            ring: list[tuple[int, int]] = []
            pipe_seeds: list[tuple[int, int]] = []
            n_rubble = 0
            for gx, gy in group:
                goff = city.offset(gx, gy)
                if city.tiles[goff] < ID_TERRAIN_MAX:
                    continue
                if is_pipe(city, gx, gy):
                    pipe_seeds.append((gx, gy))
                _write_terrain(city, gx, gy, ID_RUBBLE, 0, wipe=True)
                n_rubble += 1
                dirty.append((gx, gy))
                ring.extend(_neighbor_ring(gx, gy))
            dirty.extend(_retile_roads(city, ring))
            dirty.extend(_retile_towers(city, ring))
            if pipe_seeds:
                dirty.extend(_retile_aqueducts(city, ring))
                dirty.extend(_retile_reservoirs(city, ring))
                dirty.extend(rebuild_pipe_charge(city, ring))
            dirty = expand_iso_dirty(dirty, list(group))
            return PlaceResult(
                True,
                f"rubble 0x05 {n_rubble} tiles (N×N {tid:#x})",
                dirty=list(dict.fromkeys(dirty)),
                flush_iso=True,
            )
        was_pipe = is_pipe(city, x, y)
        was_aqueduct = is_aqueduct(city, x, y)
        was_combo = was_aqueduct and bool(city.tiles[city.offset(x, y) + 3] & 0x80)
        was_tall = tid >= ID_TERRAIN_MAX or was_aqueduct
        if tid == ID_RUBBLE:
            _write_terrain(city, x, y, ID_CLEAR, 0, wipe=True)
            msg = f"clear 0x1C em ({x},{y})"
        elif was_combo:
            road_tid = ID_ROAD_NS if tid == ID_AQUEDUCT_ROAD_EW else ID_ROAD_EW
            _write_terrain(city, x, y, road_tid, FLAG_PAD)
            msg = f"aqueduct+road → estrada {road_tid:#x} em ({x},{y})"
        elif was_aqueduct or clears_to_rubble(tid):
            _write_terrain(city, x, y, ID_RUBBLE, 0, wipe=True)
            msg = f"rubble 0x05 em ({x},{y})"
        else:
            _write_terrain(city, x, y, ID_CLEAR, 0, wipe=True)
            msg = f"clear 0x1C em ({x},{y})"
        dirty = [(x, y)]
        road_ring = [(x, y), *_neighbor_ring(x, y)] if was_combo else _neighbor_ring(x, y)
        dirty.extend(_retile_roads(city, road_ring))
        dirty.extend(_retile_towers(city, _neighbor_ring(x, y)))
        if was_pipe or was_aqueduct:
            ring = _neighbor_ring(x, y)
            dirty.extend(_retile_aqueducts(city, ring))
            dirty.extend(_retile_reservoirs(city, [(x, y), *ring]))
            dirty.extend(rebuild_pipe_charge(city, ring))
        if was_tall:
            dirty = expand_iso_dirty(dirty, [(x, y)])
        return PlaceResult(
            True, msg, dirty=list(dict.fromkeys(dirty)), flush_iso=was_tall
        )

    if tool == TOOL_WALL:
        kind = _wall_kind(city, x, y)
        if kind == "skip":
            return PlaceResult(False, f"recusa wall em ({x},{y})")
        if kind == "keep":
            return PlaceResult(False, f"já wall em ({x},{y})")
        on_road = is_city_road(city, x, y) and not is_bridge(city, x, y)
        cost = COST_GATE if on_road else COST_WALL
        err = _debit(sim, cost)
        if err:
            return PlaceResult(False, err, cost=cost)
        tid = _write_wall_cell(city, x, y, horizontal=True)
        dirty = [(x, y)]
        dirty.extend(_retile_roads(city, _neighbor_ring(x, y)))
        dirty.extend(_retile_towers(city, [(x, y), *_neighbor_ring(x, y)]))
        name = "Gate" if tid == ID_GATE else "Wall"
        return PlaceResult(
            True,
            f"{name} {tid:#x} em ({x},{y})  -{cost}",
            dirty=list(dict.fromkeys(dirty)),
            cost=cost,
        )

    if tool in _STAMPS and tool not in _CIVIC_1X1:
        from app.unlocks import unlock_refuse

        locked = unlock_refuse(tool, sim)
        if locked:
            return PlaceResult(False, locked)
        spec = _STAMPS[tool]
        w, h = stamp_wh(tool, facing)
        cells = footprint_rect(x, y, w, h)
        skip = [c for c in cells if _kind_for_tool(city, c[0], c[1], tool) == "skip"]
        if skip:
            return PlaceResult(False, f"{spec.label} {w}×{h} recusado em ({x},{y})")
        stamp = [c for c in cells if _kind_for_tool(city, c[0], c[1], tool) == "stamp"]
        if not stamp:
            return PlaceResult(False, f"já {spec.label} em ({x},{y})")
        err = _debit(sim, spec.cost)
        if err:
            return PlaceResult(False, err, cost=spec.cost)
        dirty = _write_stamp(city, x, y, spec, facing)
        if spec.tid in (ID_GRAMMATICUS, ID_RHETOR):
            paint_education_emitter(city.tiles, x, y)
        if spec.tid == ID_BATHS or ID_BATHS <= spec.tid <= 0xE2:
            paint_baths_emitter(city.tiles, x, y)
            sync_water_building_graphic(city.tiles, x, y)
        if spec.tid in (ID_BARRACKS, ID_PREFECTURE):
            paint_security_emitter(city.tiles, x, y)
        if spec.tool == TOOL_FACTORY:
            paint_factory_emitter(city.tiles, x, y)
            if sim is not None and getattr(sim, "city_only", 0):
                seed_city_only_industry(sim, nibble=factory_goods())
                factory_produce(
                    city.tiles,
                    x,
                    y,
                    goods=sim.goods,
                    labor=sim.factory_labor,
                    province_links=0,
                    city_only=True,
                )
        for cx, cy in dirty:
            paint_entertainment_emitter(city.tiles, cx, cy)
        seeds = list(dirty)
        dirty.extend(_retile_roads(city, [n for c in dirty for n in _neighbor_ring(*c)]))
        dirty = expand_iso_dirty(dirty, seeds)
        paid = f"  -{spec.cost}" if spec.cost else ""
        if spec.tool == TOOL_FACTORY:
            label = f"Factory {factory_type_name(factory_goods())} 0xFA"
        else:
            label = f"{spec.label} {spec.tid:#x}"
        return PlaceResult(
            True,
            f"{label} {w}×{h} NO ({x},{y}){paid}",
            dirty=list(dict.fromkeys(dirty)),
            cost=spec.cost,
        )

    if tool in _CIVIC_1X1:
        already = _civic_already_id(tool)
        if tool == TOOL_AQUEDUCT:
            kind = _aqueduct_kind(city, x, y)
        else:
            kind = _kind_for_tool(city, x, y, tool)
        if kind == "skip":
            msg = (
                f"aqueduto precisa de reservatório ou aqueduto em ({x},{y})"
                if tool == TOOL_AQUEDUCT and in_map(x, y) and not is_river(city, x, y)
                else f"recusa {tool} em ({x},{y})"
            )
            return PlaceResult(False, msg)
        if kind == "keep":
            return PlaceResult(False, f"já {tool} em ({x},{y})")
        cost = _civic_unit_cost(tool)
        err = _debit(sim, cost)
        if err:
            return PlaceResult(False, err, cost=cost)
        msg = _write_civic_1x1(city, x, y, tool)
        dirty = [(x, y)]
        if tool == TOOL_TOWER:
            dirty.extend(_retile_towers(city, [(x, y), *_neighbor_ring(x, y)]))
        if tool == TOOL_AQUEDUCT:
            dirty.extend(_retile_aqueducts(city, [(x, y), *_neighbor_ring(x, y)]))
        if tool in (TOOL_AQUEDUCT, TOOL_RESERVOIR):
            dirty.extend(_retile_reservoirs(city, [(x, y), *_neighbor_ring(x, y)]))
            dirty.extend(rebuild_pipe_charge(city, [(x, y)]))
        if tool in (TOOL_WELL, TOOL_FOUNTAIN, TOOL_RESERVOIR):
            paint_water_emitter(city.tiles, x, y)
        if tool == TOOL_FOUNTAIN:
            sync_water_building_graphic(city.tiles, x, y)
        if tool == TOOL_PREFECTURE:
            paint_security_emitter(city.tiles, x, y)
        # Aqueduct must not trigger road retile — that wrote the fake 0x52.
        if tool != TOOL_AQUEDUCT:
            dirty.extend(_retile_roads(city, _neighbor_ring(x, y)))
        if tool in _TALL_TOOLS:
            dirty = expand_iso_dirty(dirty, [(x, y)])
        return PlaceResult(
            True,
            msg,
            dirty=list(dict.fromkeys(dirty)),
            cost=cost,
        )

    return PlaceResult(False, f"ferramenta desconhecida: {tool}")


def query_tile(city: CityMap, x: int, y: int) -> str:
    t = city.tile(x, y)
    bits = []
    if t.is_river and t.is_pad:
        bits.append("ponte")
    elif t.is_river:
        bits.append("rio")
        if t.flags & FLAG_RIVER_BANK:
            bits.append("curva")
    if t.is_pad and not (t.is_river):
        bits.append("pad")
    if ID_ROAD_LO <= t.terrain_id <= ID_ROAD_HI:
        bits.append("estrada")
    if ID_BRIDGE_LO <= t.terrain_id <= ID_BRIDGE_HI and t.is_river:
        bits.append(f"bridge {t.terrain_id:#x}")
    if t.terrain_id == ID_TENT:
        bits.append("Tent")
    if ID_GARDEN <= t.terrain_id <= ID_GARDEN_HI:
        bits.append("Garden")
    if t.terrain_id == ID_RESERVOIR:
        bits.append("Reservoir")
        if t.coverage & 3:
            bits.append(f"cheio +10={t.coverage & 3}")
    if t.terrain_id == ID_TOWER:
        bits.append("Tower")
    if ID_AQUEDUCT_LO <= t.terrain_id <= ID_AQUEDUCT_HI:
        bits.append(f"aqueduct {t.terrain_id:#x}")
        if t.draw & 0x80:
            bits.append("sobre estrada")
    if t.terrain_id == ID_WELL:
        bits.append("Well")
    if t.terrain_id == ID_FOUNTAIN:
        bits.append("Fountain")
    if t.terrain_id == ID_PREFECTURE:
        bits.append("Praefecture")
    if t.terrain_id == ID_BARRACKS:
        bits.append("Barracks")
    if is_plaza_id(t.terrain_id):
        bits.append("Plaza")
    if t.terrain_id == ID_SHRINE:
        bits.append("Shrine")
    if ID_TEMPLE <= t.terrain_id <= 0xA8:
        bits.append("Temple")
    if t.terrain_id in (0xAA, ID_BASILICA, 0xAC):
        bits.append("Basilica")
    if t.terrain_id in (0xAE, ID_AVENTINE, 0xB0):
        bits.append("Aventine")
    if t.terrain_id in (ID_JANICULAN, 0xB3, 0xB4):
        bits.append("Janiculan")
    if t.terrain_id in (0xB6, ID_PALATINE, 0xB8, 0xB9):
        bits.append("Palatine")
    if t.terrain_id == ID_GATE:
        bits.append("Gate")
    if t.terrain_id in (ID_WALL_NS, ID_WALL_EW):
        bits.append("Wall")
    if t.terrain_id == ID_THEATER:
        bits.append("Theater")
    if t.terrain_id == ID_ODEUM:
        bits.append("Odeum")
    if t.terrain_id == ID_COLISEUM:
        bits.append("Coliseum")
    if t.terrain_id in (ID_CIRCUS_A, ID_CIRCUS_B, ID_CIRCUS_C, ID_CIRCUS_D):
        bits.append("Circus")
    if t.terrain_id in (ID_CMAX_A, ID_CMAX_B, ID_CMAX_C, ID_CMAX_D):
        bits.append("C.Maximus")
    if t.terrain_id == ID_GRAMMATICUS:
        bits.append("Grammaticus")
    if t.terrain_id == ID_RHETOR:
        bits.append("Rhetor")
    if t.terrain_id == ID_LIBRARY:
        bits.append("Library")
    if ID_BATHS <= t.terrain_id <= 0xE2:
        bits.append("Baths")
    if t.terrain_id == ID_MARKET or 0xFD <= t.terrain_id <= 0xFF:
        bits.append("Market")
    if t.terrain_id == ID_HOSPITAL:
        bits.append("Hospital")
    if t.terrain_id == ID_FACTORY:
        bits.append(f"Factory {factory_type_name(t.special)}")
    if t.terrain_id == ID_RUBBLE:
        bits.append("rubble")
    if t.terrain_id == ID_CLEAR:
        bits.append("clear")
    extra = (" " + " ".join(bits)) if bits else ""
    saved = f" +9={t.overlay_anim:#04x}" if t.overlay_anim else ""
    return f"({x},{y}) +0={t.terrain_id:#04x} +1={t.flags:#04x}{saved}{extra}"


def screen_to_tile(
    px: int,
    py: int,
    *,
    zoom: int = 0,
    width: int = MAP_W,
    facing: int = 0,
) -> tuple[int, int] | None:
    """Inverse of tile_iso_xy using the diamond centre (not the sprite AABB)."""
    from app.city_map import draw_to_world

    tile_w, tile_h = iso_tile_size(zoom)
    half_w, half_h = tile_w // 2, tile_h // 2
    if half_w < 1 or half_h < 1:
        return None
    origin_x = iso_origin_x(zoom=zoom, width=width)
    col = (px - origin_x - half_w) / half_w
    row = (py - half_h) / half_h
    dx = (col + row) / 2.0
    dy = (row - col) / 2.0
    wx, wy = draw_to_world(dx, dy, facing, width=width, height=width)
    tx = int(round(wx))
    ty = int(round(wy))
    if in_map(tx, ty):
        return tx, ty
    return None


def view_to_canvas(
    vx: int,
    vy: int,
    cam_x: int,
    cam_y: int,
    canvas_w: int,
    canvas_h: int,
    *,
    screen_w: int = 640,
    screen_h: int = 480,
) -> tuple[int, int]:
    """Window pixel → native iso canvas pixel (same rules as crop_viewport)."""
    if canvas_w <= screen_w and canvas_h <= screen_h:
        ox = (screen_w - canvas_w) // 2
        oy = (screen_h - canvas_h) // 2
        return vx - ox, vy - oy
    return cam_x + vx, cam_y + vy


def canvas_to_view(
    cx: int,
    cy: int,
    cam_x: int,
    cam_y: int,
    canvas_w: int,
    canvas_h: int,
    *,
    screen_w: int = 640,
    screen_h: int = 480,
) -> tuple[int, int]:
    """Native iso canvas pixel → window pixel (inverse of view_to_canvas)."""
    if canvas_w <= screen_w and canvas_h <= screen_h:
        ox = (screen_w - canvas_w) // 2
        oy = (screen_h - canvas_h) // 2
        return cx + ox, cy + oy
    return cx - cam_x, cy - cam_y


def line_cells(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Axis-aligned straight line. |dx|≥|dy| → row y0, else column x0. No L."""
    dx = x1 - x0
    dy = y1 - y0
    out: list[tuple[int, int]] = []
    if abs(dx) >= abs(dy):
        step = 1 if dx >= 0 else -1
        for x in range(x0, x1 + step, step):
            if in_map(x, y0):
                out.append((x, y0))
    else:
        step = 1 if dy >= 0 else -1
        for y in range(y0, y1 + step, step):
            if in_map(x0, y):
                out.append((x0, y))
    return out


def rect_cells(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Inclusive axis-aligned bbox, raster order (y then x, min→max)."""
    xa, xb = (x0, x1) if x0 <= x1 else (x1, x0)
    ya, yb = (y0, y1) if y0 <= y1 else (y1, y0)
    out: list[tuple[int, int]] = []
    for y in range(ya, yb + 1):
        for x in range(xa, xb + 1):
            if in_map(x, y):
                out.append((x, y))
    return out


def span_cells(
    tool: str, x0: int, y0: int, x1: int, y1: int, facing: int = 0
) -> list[tuple[int, int]]:
    if tool in LINE_TOOLS:
        return line_cells(x0, y0, x1, y1)
    if tool in STAMP_TOOLS:
        w, h = stamp_wh(tool, facing)
        return footprint_rect(x1, y1, w, h)
    if tool in RECT_TOOLS:
        return rect_cells(x0, y0, x1, y1)
    if in_map(x1, y1):
        return [(x1, y1)]
    return []


def _road_line_kind(
    city: CityMap,
    x: int,
    y: int,
    pending_bridges: set[tuple[int, int]] | None = None,
) -> str:
    """'stamp' / 'keep' (already road or bridge) / 'skip' (curve, adj, occupied)."""
    if not in_map(x, y):
        return "skip"
    if is_city_road(city, x, y):
        return "keep"
    if is_river(city, x, y):
        if not is_bridgeable_river(city, x, y):
            return "skip"
        if has_adjacent_bridge(city, x, y):
            return "skip"
        if pending_bridges:
            for dx, dy in _CARDINALS:
                if (x + dx, y + dy) in pending_bridges:
                    return "skip"
        return "stamp"
    if is_road_occupied(city, x, y):
        return "skip"
    return "stamp"


def _road_skip_extra(n_curve: int, n_adj: int, n_occ: int = 0) -> str:
    parts: list[str] = []
    if n_curve:
        parts.append(f"{n_curve} curva(s) saltada(s)")
    if n_adj:
        parts.append(f"{n_adj} ponte(s) adjacente(s) saltada(s)")
    if n_occ:
        parts.append(f"{n_occ} ocupado(s) saltado(s)")
    return f"  ({', '.join(parts)})" if parts else ""


def _tent_stampable(city: CityMap, x: int, y: int) -> bool:
    if not in_map(x, y) or is_river(city, x, y):
        return False
    if is_city_road(city, x, y):
        return False
    tid = city.tiles[city.offset(x, y)]
    if tid == ID_TENT or tid >= ID_TERRAIN_MAX:
        return False
    return True


def _clear_stampable(city: CityMap, x: int, y: int) -> bool:
    if not in_map(x, y):
        return False
    # 0xCB–0xD6 are buildings (DAT type 1), not terrain/water. Occupancy
    # 0x7C is the road-skip gate — it must not block Clear here.
    if is_aqueduct(city, x, y):
        return True
    if is_river(city, x, y) and not is_bridge(city, x, y):
        return False
    return True


def preview_span(
    city: CityMap,
    tool: str,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    treasury: int = 0,
    facing: int = 0,
) -> DragPreview:
    """Classify a rubber-band without writing tiles or debiting."""
    cells = span_cells(tool, x0, y0, x1, y1, facing)
    xa, xb = (min(x0, x1), max(x0, x1))
    ya, yb = (min(y0, y1), max(y0, y1))
    width, height = xb - xa + 1, yb - ya + 1
    ok: list[tuple[int, int]] = []
    skip: list[tuple[int, int]] = []
    stamp: list[tuple[int, int]] = []

    if tool == TOOL_ROAD:
        pending_bridges: set[tuple[int, int]] = set()
        n_curve = 0
        n_adj = 0
        n_occ = 0
        for x, y in cells:
            kind = _road_line_kind(city, x, y, pending_bridges)
            if kind == "skip":
                skip.append((x, y))
                if is_bridgeable_river(city, x, y):
                    n_adj += 1
                elif is_road_occupied(city, x, y):
                    n_occ += 1
                else:
                    n_curve += 1
            elif kind == "keep":
                ok.append((x, y))
            else:
                ok.append((x, y))
                stamp.append((x, y))
                if is_river(city, x, y):
                    pending_bridges.add((x, y))
        extra = _road_skip_extra(n_curve, n_adj, n_occ)
        message = f"Estrada {len(ok)}{extra}"
        return DragPreview(
            tool, cells, ok, skip, stamp, message=message, width=width, height=height
        )

    if tool == TOOL_TENT:
        for x, y in cells:
            if _tent_stampable(city, x, y):
                ok.append((x, y))
                stamp.append((x, y))
            else:
                skip.append((x, y))
        cost = COST_TENT * len(stamp)
        refuse = None
        if stamp and treasury < cost:
            refuse = (
                f"tesouro {treasury} < {cost} ({len(stamp)} tendas) - "
                f"arrasto recusado (tudo ou nada)"
            )
            message = f"Housing {width}x{height}  {refuse}"
        elif not stamp:
            message = f"Housing {width}x{height}  nenhuma tenda nova"
        else:
            message = f"Housing {width}x{height} = {len(stamp)}  custo {cost}"
        return DragPreview(
            tool,
            cells,
            ok,
            skip,
            stamp,
            cost=cost,
            refuse=refuse,
            message=message,
            width=width,
            height=height,
        )

    if tool == TOOL_CLEAR:
        seen: set[tuple[int, int]] = set()
        for x, y in cells:
            if not _clear_stampable(city, x, y):
                skip.append((x, y))
                continue
            for gx, gy in building_group_cells(city, x, y):
                if (gx, gy) in seen:
                    continue
                seen.add((gx, gy))
                ok.append((gx, gy))
                stamp.append((gx, gy))
        message = f"Clear {width}x{height} = {len(stamp)}"
        return DragPreview(
            tool, cells, ok, skip, stamp, message=message, width=width, height=height
        )

    if tool == TOOL_WALL:
        for x, y in cells:
            kind = _wall_kind(city, x, y)
            if kind == "skip":
                skip.append((x, y))
            elif kind == "keep":
                ok.append((x, y))
            else:
                ok.append((x, y))
                stamp.append((x, y))
        cost = 0
        n_gate = 0
        for x, y in stamp:
            if is_city_road(city, x, y) and not is_bridge(city, x, y):
                cost += COST_GATE
                n_gate += 1
            else:
                cost += COST_WALL
        refuse = None
        if not stamp:
            message = f"Wall {width}x{height}  nenhum novo"
        elif treasury < cost:
            refuse = (
                f"tesouro {treasury} < {cost} ({len(stamp)}) - "
                f"arrasto recusado (tudo ou nada)"
            )
            message = f"Wall {len(stamp)}  {refuse}"
        else:
            extra = f"  {n_gate} gate" if n_gate else ""
            message = f"Wall {len(stamp)}{extra}  custo {cost}"
        return DragPreview(
            tool, cells, ok, skip, stamp, cost=cost, refuse=refuse,
            message=message, width=width, height=height,
        )

    if tool in STAMP_TOOLS:
        w, h = stamp_wh(tool, facing)
        width, height = w, h
        for cx, cy in cells:
            kind = _kind_for_tool(city, cx, cy, tool)
            if kind == "skip":
                skip.append((cx, cy))
            elif kind == "keep":
                ok.append((cx, cy))
            else:
                ok.append((cx, cy))
                stamp.append((cx, cy))
        unit = _civic_unit_cost(tool)
        cost = unit if stamp else 0
        label = _tool_label(tool)
        refuse = None
        if skip:
            refuse = f"{label} {w}×{h} recusado em ({x1},{y1})"
            message = refuse
        elif not stamp:
            message = f"já {label} em ({x1},{y1})"
        elif unit and treasury < cost:
            refuse = f"tesouro {treasury} < {cost}"
            message = f"{label} {w}x{h}  {refuse}"
        else:
            paid = f"  custo {cost}" if cost else ""
            message = f"{label} {w}x{h} NO ({x1},{y1}){paid}"
        return DragPreview(
            tool, cells, ok, skip, stamp, cost=cost, refuse=refuse,
            message=message, width=width, height=height,
        )

    if tool in _CIVIC_1X1:
        if tool == TOOL_AQUEDUCT:
            ok, skip, stamp = _classify_aqueduct_span(city, cells)
        else:
            pending: set[tuple[int, int]] = set()
            for cx, cy in cells:
                kind = _kind_for_tool(city, cx, cy, tool, pending)
                if kind == "skip":
                    skip.append((cx, cy))
                elif kind == "keep":
                    ok.append((cx, cy))
                else:
                    ok.append((cx, cy))
                    stamp.append((cx, cy))
                    if tool == TOOL_PLAZA:
                        pending.add((cx, cy))
        unit = _civic_unit_cost(tool)
        cost = unit * len(stamp)
        label = _tool_label(tool)
        refuse = None
        if stamp and unit and treasury < cost:
            refuse = (
                f"tesouro {treasury} < {cost} ({len(stamp)}) - "
                f"arrasto recusado (tudo ou nada)"
            )
            message = f"{label} {width}x{height}  {refuse}"
        elif not stamp:
            message = f"{label} {width}x{height}  nenhum novo"
        else:
            extra = f"  custo {cost}" if cost else ""
            message = f"{label} {width}x{height} = {len(stamp)}{extra}"
        return DragPreview(
            tool, cells, ok, skip, stamp, cost=cost, refuse=refuse,
            message=message, width=width, height=height,
        )

    return DragPreview(tool, cells, [], [], [], message="query")


def try_place_span(
    city: CityMap,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    tool: str,
    sim: SimState | None = None,
    facing: int = 0,
) -> PlaceResult:
    """Commit a rubber-band on mouse-up. Tent / civic drag is treasury-atomic."""
    if tool == TOOL_QUERY:
        return try_place(city, x1, y1, tool, sim, facing=facing)
    if tool in STAMP_TOOLS:
        return try_place(city, x1, y1, tool, sim, facing=facing)
    treasury = 0 if sim is None else sim.treasury
    preview = preview_span(city, tool, x0, y0, x1, y1, treasury, facing=facing)
    if preview.refuse:
        return PlaceResult(False, preview.message, cost=preview.cost)
    if not preview.stamp:
        return PlaceResult(False, preview.message)

    if tool == TOOL_TENT:
        err = _debit(sim, preview.cost)
        if err:
            return PlaceResult(False, err, cost=preview.cost)
        dirty: list[tuple[int, int]] = []
        ring: list[tuple[int, int]] = []
        for x, y in preview.stamp:
            _write_terrain(city, x, y, ID_TENT, 0x01)
            city.tiles[city.offset(x, y) + 15] = 1
            dirty.append((x, y))
            ring.extend(_neighbor_ring(x, y))
        dirty.extend(_retile_roads(city, ring))
        n = len(preview.stamp)
        return PlaceResult(
            True,
            f"Housing {preview.width}x{preview.height} = {n}  -{preview.cost}",
            dirty=dirty,
            cost=preview.cost,
        )

    if tool in _CIVIC_1X1:
        if tool == TOOL_AQUEDUCT and not any(
            aqueduct_connects(city, x, y) for x, y in preview.stamp
        ):
            return PlaceResult(False, "aqueduto isolado recusado")
        err = _debit(sim, preview.cost)
        if err:
            return PlaceResult(False, err, cost=preview.cost)
        dirty = []
        ring: list[tuple[int, int]] = []
        for step, (x, y) in enumerate(preview.stamp):
            _write_civic_1x1(city, x, y, tool, step=step)
            dirty.append((x, y))
            ring.extend(_neighbor_ring(x, y))
        if tool == TOOL_TOWER:
            dirty.extend(_retile_towers(city, list(preview.stamp) + ring))
        if tool == TOOL_AQUEDUCT:
            dirty.extend(_retile_aqueducts(city, list(preview.stamp) + ring))
        if tool in (TOOL_AQUEDUCT, TOOL_RESERVOIR):
            dirty.extend(_retile_reservoirs(city, list(preview.stamp) + ring))
            dirty.extend(rebuild_pipe_charge(city, list(preview.stamp)))
        if tool in (TOOL_WELL, TOOL_FOUNTAIN, TOOL_RESERVOIR):
            for x, y in preview.stamp:
                paint_water_emitter(city.tiles, x, y)
        if tool == TOOL_FOUNTAIN:
            for x, y in preview.stamp:
                sync_water_building_graphic(city.tiles, x, y)
        if tool == TOOL_PREFECTURE:
            for x, y in preview.stamp:
                paint_security_emitter(city.tiles, x, y)
        if tool != TOOL_AQUEDUCT:
            dirty.extend(_retile_roads(city, ring))
        if tool in _TALL_TOOLS:
            dirty = expand_iso_dirty(dirty, list(preview.stamp))
        n = len(preview.stamp)
        paid = f"  -{preview.cost}" if preview.cost else ""
        label = _tool_label(tool)
        return PlaceResult(
            True,
            f"{label} {preview.width}x{preview.height} = {n}{paid}",
            dirty=list(dict.fromkeys(dirty)),
            cost=preview.cost,
        )

    if tool == TOOL_WALL:
        err = _debit(sim, preview.cost)
        if err:
            return PlaceResult(False, err, cost=preview.cost)
        horizontal = preview.width >= preview.height
        dirty = []
        ring: list[tuple[int, int]] = []
        n_gate = 0
        for x, y in preview.stamp:
            tid = _write_wall_cell(city, x, y, horizontal)
            if tid == ID_GATE:
                n_gate += 1
            dirty.append((x, y))
            ring.extend(_neighbor_ring(x, y))
        dirty.extend(_retile_roads(city, ring))
        dirty.extend(_retile_towers(city, list(preview.stamp) + ring))
        extra = f"  {n_gate} gate" if n_gate else ""
        paid = f"  -{preview.cost}" if preview.cost else ""
        return PlaceResult(
            True,
            f"Wall {len(preview.stamp)}{extra}{paid}",
            dirty=list(dict.fromkeys(dirty)),
            cost=preview.cost,
        )

    extra = ""
    if tool == TOOL_ROAD and preview.skip:
        n_adj = sum(1 for sx, sy in preview.skip if is_bridgeable_river(city, sx, sy))
        n_occ = sum(
            1
            for sx, sy in preview.skip
            if not is_bridgeable_river(city, sx, sy) and is_road_occupied(city, sx, sy)
        )
        extra = _road_skip_extra(len(preview.skip) - n_adj - n_occ, n_adj, n_occ)

    dirty = []
    n_ok = 0
    flush = False
    done: set[tuple[int, int]] = set()
    for x, y in preview.stamp:
        if (x, y) in done:
            continue
        group = building_group_cells(city, x, y) if tool == TOOL_CLEAR else [(x, y)]
        result = try_place(city, x, y, tool, None)
        if result.ok:
            n_ok += 1
            dirty.extend(result.dirty)
            flush = flush or result.flush_iso
            done.update(group)
        else:
            done.add((x, y))
    if tool == TOOL_ROAD:
        dirty.extend(_retile_roads(city, list(preview.ok)))
        return PlaceResult(
            True, f"Estrada {n_ok}{extra}", dirty=list(dict.fromkeys(dirty))
        )
    return PlaceResult(
        True,
        f"Clear {preview.width}x{preview.height} = {len(preview.stamp)}",
        dirty=list(dict.fromkeys(dirty)),
        flush_iso=flush,
    )


def selftest() -> list[str]:
    lines: list[str] = []
    city = CityMap()
    city.source = "place-selftest"
    # Grass, not river.
    city.tiles[city.offset(10, 10)] = 0x14
    city.tiles[city.offset(11, 10)] = 0x14
    city.tiles[city.offset(10, 11)] = 0x14
    sim = SimState(treasury=20)
    r = try_place(city, 10, 10, TOOL_TENT, sim)
    t = city.tile(10, 10)
    if not r.ok or t.terrain_id != ID_TENT or t.flags != 0x01 or sim.treasury != 14:
        lines.append(f"FAIL  tent {r.message} id={t.terrain_id:#x} treas={sim.treasury}")
    else:
        lines.append("ok    tent 0x82 +1=0x01 debit 6")

    sim.treasury = 5
    r = try_place(city, 11, 10, TOOL_TENT, sim)
    if r.ok or sim.treasury != 5:
        lines.append(f"FAIL  tent should refuse treasury {sim.treasury}")
    else:
        lines.append("ok    tent refuse if treasury < 6")

    off = city.offset(20, 20)
    city.tiles[off] = 0x36
    city.tiles[off + 1] = FLAG_RIVER | FLAG_RIVER_BANK
    r = try_place(city, 20, 20, TOOL_ROAD, sim)
    if r.ok or city.tiles[off] != 0x36:
        lines.append(f"FAIL  road on curve {r.message} id={city.tiles[off]:#x}")
    else:
        lines.append("ok    recusa curva 0x36 +1=0x18")

    off = city.offset(21, 20)
    city.tiles[off] = 0x1E
    city.tiles[off + 1] = FLAG_RIVER
    r = try_place(city, 21, 20, TOOL_ROAD, sim)
    t = city.tile(21, 20)
    if (
        not r.ok
        or t.terrain_id != 0x4E
        or t.flags != (FLAG_RIVER | FLAG_PAD)
        or t.overlay_anim != 0x1E
    ):
        lines.append(
            f"FAIL  bridge {r.message} id={t.terrain_id:#x} "
            f"+1={t.flags:#x} +9={t.overlay_anim:#x}"
        )
    else:
        lines.append("ok    ponte 0x4E (recto 0x1E) +1=0x30 +9=0x1E")

    # Cardinal neighbour of (21,20) — 665DF is ±0x14 / ±0x640 only.
    off = city.offset(22, 20)
    city.tiles[off] = 0x1E
    city.tiles[off + 1] = FLAG_RIVER
    city.tiles[off + 9] = 0
    r = try_place(city, 22, 20, TOOL_ROAD, sim)
    if r.ok or city.tiles[off] != 0x1E or "adjacente" not in r.message:
        lines.append(f"FAIL  adj cardinal {r.message} id={city.tiles[off]:#x}")
    else:
        lines.append("ok    recusa ponte cardinal (22,20) colada a 0x4E")

    # Diagonal (22,21) to (21,20) — 8-way would refuse; EXE does not.
    off = city.offset(22, 21)
    city.tiles[off] = 0x1E
    city.tiles[off + 1] = FLAG_RIVER
    city.tiles[off + 9] = 0
    r = try_place(city, 22, 21, TOOL_ROAD, sim)
    t = city.tile(22, 21)
    if not r.ok or t.terrain_id != 0x4E:
        lines.append(f"FAIL  diagonal deve aceitar {r.message} id={t.terrain_id:#x}")
    else:
        lines.append("ok    diagonal (22,21) nao e vizinho cardinal")

    r = try_place(city, 22, 21, TOOL_CLEAR, sim)
    if not r.ok or city.tiles[city.offset(22, 21)] != 0x1E:
        lines.append("FAIL  clear ponte diagonal")
    else:
        lines.append("ok    clear ponte diagonal -> rio")

    # One-tile gap: (23,20) is not cardinal to (21,20).
    off = city.offset(23, 20)
    city.tiles[off] = 0x1E
    city.tiles[off + 1] = FLAG_RIVER
    city.tiles[off + 9] = 0
    r = try_place(city, 23, 20, TOOL_ROAD, sim)
    if not r.ok or city.tiles[off] != 0x4E:
        lines.append(f"FAIL  gap 1 {r.message} id={city.tiles[off]:#x}")
    else:
        lines.append("ok    ponte com 1 tile de intervalo")
    try_place(city, 23, 20, TOOL_CLEAR, sim)

    for src, want in ((0x22, 0x4F), (0x26, 0x50), (0x2A, 0x51)):
        off = city.offset(24, 20)
        city.tiles[off] = src
        city.tiles[off + 1] = FLAG_RIVER
        city.tiles[off + 9] = 0
        r = try_place(city, 24, 20, TOOL_ROAD, sim)
        got = city.tiles[off]
        if not r.ok or got != want:
            lines.append(f"FAIL  bridge {src:#x} -> {got:#x} want {want:#x}")
        else:
            lines.append(f"ok    ponte {src:#x} -> {want:#x}")
        try_place(city, 24, 20, TOOL_CLEAR, sim)

    r = try_place(city, 11, 10, TOOL_ROAD, sim)
    tid = city.tiles[city.offset(11, 10)]
    flags = city.tiles[city.offset(11, 10) + 1]
    if not r.ok or not (ID_ROAD_LO <= tid <= ID_ROAD_HI) or not (flags & FLAG_PAD):
        lines.append(f"FAIL  road {tid:#x} flags={flags:#x}")
    else:
        lines.append(f"ok    road stamp {tid:#x} + pad")

    try_place(city, 12, 10, TOOL_ROAD, sim)
    a = city.tiles[city.offset(11, 10)]
    b = city.tiles[city.offset(12, 10)]
    if a != ID_ROAD_EW or b != ID_ROAD_EW:
        lines.append(f"FAIL  autotile EW got {a:#x}/{b:#x}")
    else:
        lines.append("ok    road autotile 0x53 EW")

    # Land road south of the 0x4E bridge must see it as a neighbour.
    city.tiles[city.offset(21, 21)] = 0x14
    city.tiles[city.offset(21, 21) + 1] = 0
    r = try_place(city, 21, 21, TOOL_ROAD, sim)
    land = city.tiles[city.offset(21, 21)]
    br = city.tiles[city.offset(21, 20)]
    if not r.ok or land != ID_ROAD_NS or br != 0x4E:
        lines.append(f"FAIL  autotile vs ponte land={land:#x} br={br:#x}")
    else:
        lines.append("ok    estrada 0x52 cola na ponte 0x4E")

    r = try_place(city, 11, 10, TOOL_CLEAR, sim)
    if city.tiles[city.offset(11, 10)] != ID_CLEAR:
        lines.append("FAIL  clear road")
    else:
        lines.append("ok    clear estrada -> 0x1C")

    city.tiles[city.offset(13, 10)] = ID_TENT
    city.tiles[city.offset(13, 10) + 1] = 0x01
    r = try_place(city, 13, 10, TOOL_CLEAR, sim)
    if city.tiles[city.offset(13, 10)] != ID_RUBBLE:
        lines.append(f"FAIL  house->rubble {city.tiles[city.offset(13, 10)]:#x}")
    else:
        lines.append("ok    clear casa -> rubble 0x05")

    r = try_place(city, 13, 10, TOOL_CLEAR, sim)
    if city.tiles[city.offset(13, 10)] != ID_CLEAR:
        lines.append(f"FAIL  rubble->clear {city.tiles[city.offset(13, 10)]:#x}")
    else:
        lines.append("ok    clear rubble -> 0x1C")

    r = try_place(city, 21, 20, TOOL_CLEAR, sim)
    t = city.tile(21, 20)
    if not r.ok or t.terrain_id != 0x1E or t.flags != FLAG_RIVER or t.overlay_anim:
        lines.append(
            f"FAIL  clear ponte {r.message} id={t.terrain_id:#x} +1={t.flags:#x}"
        )
    else:
        lines.append("ok    clear ponte -> rio 0x1E")

    hit = screen_to_tile(*_tile_center(0, 0), zoom=0)
    if hit != (0, 0):
        lines.append(f"FAIL  screen_to_tile (0,0) -> {hit}")
    else:
        lines.append("ok    screen_to_tile (0,0)")
    hit = screen_to_tile(*_tile_center(5, 3), zoom=0)
    if hit != (5, 3):
        lines.append(f"FAIL  screen_to_tile (5,3) -> {hit}")
    else:
        lines.append("ok    screen_to_tile (5,3)")
    from app.city_map import tile_iso_xy as _iso

    tw, th = iso_tile_size(0)
    sx, sy = _iso(0, 0, facing=1)
    cx, cy = sx + tw // 2, sy + th // 2
    hit = screen_to_tile(cx, cy, zoom=0, facing=1)
    if hit != (0, 0):
        lines.append(f"FAIL  screen_to_tile facing 1 (0,0) -> {hit}")
    else:
        lines.append("ok    screen_to_tile facing 1 (0,0)")

    line = line_cells(0, 0, 5, 2)
    if line != [(x, 0) for x in range(6)]:
        lines.append(f"FAIL  line dominant-x {line}")
    else:
        lines.append("ok    estrada linha horizontal (|dx|>=|dy|), sem L")
    line = line_cells(0, 0, 2, 5)
    if line != [(0, y) for y in range(6)]:
        lines.append(f"FAIL  line dominant-y {line}")
    else:
        lines.append("ok    estrada linha vertical")
    line = line_cells(5, 5, 1, 5)
    if line != [(x, 5) for x in range(5, 0, -1)]:
        lines.append(f"FAIL  line reverse {line}")
    else:
        lines.append("ok    estrada linha invertida")
    if line_cells(3, 3, 3, 3) != [(3, 3)]:
        lines.append("FAIL  line 1-tile")
    else:
        lines.append("ok    linha de 1 tile")

    box = rect_cells(2, 2, 4, 3)
    if box != [(2, 2), (3, 2), (4, 2), (2, 3), (3, 3), (4, 3)]:
        lines.append(f"FAIL  rect raster {box}")
    else:
        lines.append("ok    rectangulo raster y depois x")

    city = CityMap()
    city.source = "place-span"
    for x, y in ((10, 10), (11, 10), (12, 10), (10, 11), (11, 11), (12, 11)):
        city.tiles[city.offset(x, y)] = 0x14
    sim = SimState(treasury=10)
    r = try_place_span(city, 10, 10, 12, 11, TOOL_TENT, sim)
    if r.ok or sim.treasury != 10:
        lines.append(f"FAIL  tent span atomic {r.message} treas={sim.treasury}")
    elif any(city.tiles[city.offset(x, y)] == ID_TENT for x, y in rect_cells(10, 10, 12, 11)):
        lines.append("FAIL  tent span atomic wrote tiles")
    else:
        lines.append("ok    Housing arrasto atomico (10 < 36) - nada escrito")

    sim.treasury = 20
    r = try_place_span(city, 10, 10, 11, 10, TOOL_TENT, sim)
    a = city.tiles[city.offset(10, 10)]
    b = city.tiles[city.offset(11, 10)]
    if not r.ok or a != ID_TENT or b != ID_TENT or sim.treasury != 8 or r.cost != 12:
        lines.append(
            f"FAIL  tent span place {r.message} {a:#x}/{b:#x} treas={sim.treasury}"
        )
    else:
        lines.append("ok    Housing 2 tiles -12 tesouro")

    r = try_place_span(city, 10, 10, 11, 10, TOOL_TENT, sim)
    if r.ok or sim.treasury != 8:
        lines.append(f"FAIL  tent span already {r.message} treas={sim.treasury}")
    else:
        lines.append("ok    Housing já 0x82 não debita de novo")

    off = city.offset(30, 20)
    city.tiles[off] = 0x36
    city.tiles[off + 1] = FLAG_RIVER | FLAG_RIVER_BANK
    city.tiles[city.offset(29, 20)] = 0x14
    city.tiles[city.offset(29, 20) + 1] = 0
    city.tiles[city.offset(31, 20)] = 0x1E
    city.tiles[city.offset(31, 20) + 1] = FLAG_RIVER
    city.tiles[city.offset(32, 20)] = 0x14
    city.tiles[city.offset(32, 20) + 1] = 0
    r = try_place_span(city, 29, 20, 32, 21, TOOL_ROAD, sim)
    curve = city.tiles[off]
    br = city.tiles[city.offset(31, 20)]
    land = city.tiles[city.offset(32, 20)]
    # dominant |dx|=3 >= |dy|=1 → horizontal y=20, no L onto y=21
    below = city.tiles[city.offset(29, 21)]
    if (
        not r.ok
        or curve != 0x36
        or br != 0x4E
        or not (ID_ROAD_LO <= land <= ID_ROAD_HI)
        or below not in (0, 0x14)
        or "curva" not in r.message
    ):
        lines.append(
            f"FAIL  road span {r.message} curve={curve:#x} br={br:#x} "
            f"land={land:#x} below={below:#x}"
        )
    else:
        lines.append("ok    estrada recta: ponte + salta curva, sem L")

    for x in (50, 51, 52, 53):
        city.tiles[city.offset(x, 25)] = 0x14
        city.tiles[city.offset(x, 25) + 1] = 0
    city.tiles[city.offset(51, 25)] = 0x1E
    city.tiles[city.offset(51, 25) + 1] = FLAG_RIVER
    city.tiles[city.offset(52, 25)] = 0x1E
    city.tiles[city.offset(52, 25) + 1] = FLAG_RIVER
    r = try_place_span(city, 50, 25, 53, 25, TOOL_ROAD, sim)
    a = city.tiles[city.offset(51, 25)]
    b = city.tiles[city.offset(52, 25)]
    if not r.ok or a != 0x4E or b != 0x1E or "adjacente" not in r.message:
        lines.append(f"FAIL  span adj {r.message} {a:#x}/{b:#x}")
    else:
        lines.append("ok    linha: 1a ponte, 2a saltada (cardinal)")

    city.tiles[city.offset(40, 40)] = ID_TENT
    city.tiles[city.offset(40, 40) + 1] = 0x01
    city.tiles[city.offset(41, 40)] = 0x14
    r = try_place_span(city, 40, 40, 41, 41, TOOL_CLEAR, sim)
    if (
        not r.ok
        or city.tiles[city.offset(40, 40)] != ID_RUBBLE
        or city.tiles[city.offset(41, 40)] != ID_CLEAR
        or city.tiles[city.offset(40, 41)] != ID_CLEAR
    ):
        lines.append(f"FAIL  clear span {r.message}")
    else:
        lines.append("ok    Clear rect: casa→0x05, relva→0x1C")

    city = CityMap()
    city.source = "place-civic"
    city.tiles[city.offset(15, 15)] = 0x14
    sim = SimState(treasury=50)
    r = try_place(city, 15, 15, TOOL_RESERVOIR, sim)
    if r.ok or sim.treasury != 50:
        lines.append(f"FAIL  reservoir treasury {r.message} treas={sim.treasury}")
    else:
        lines.append("ok    Reservoir recusa tesouro < 51")
    sim.treasury = 51
    r = try_place(city, 15, 15, TOOL_RESERVOIR, sim)
    t = city.tile(15, 15)
    east = city.tiles[city.offset(16, 15)]
    south = city.tiles[city.offset(15, 16)]
    se = city.tiles[city.offset(16, 16)]
    if (
        not r.ok
        or t.terrain_id != ID_RESERVOIR
        or t.flags != FLAG_RESERVOIR
        or t.variant != VAR_RESERVOIR
        or t.coverage & 3
        or east == ID_RESERVOIR
        or south == ID_RESERVOIR
        or se == ID_RESERVOIR
        or sim.treasury != 0
        or r.cost != 51
    ):
        lines.append(
            f"FAIL  reservoir {r.message} id={t.terrain_id:#x} +1={t.flags:#x} "
            f"+4={t.variant:#x} +10={t.coverage:#x} east={east:#x} treas={sim.treasury}"
        )
    else:
        lines.append("ok    Reservoir 1×1 0xBE +1=0x80 +4=0x6E seco -51")
    if (15, 16) not in r.dirty or (16, 16) not in r.dirty or (14, 16) not in r.dirty:
        lines.append(f"FAIL  reservoir dirty vizinhos {r.dirty}")
    else:
        lines.append("ok    Reservoir dirty S/SE/SW (extra_rows)")
    r = try_place(city, 15, 15, TOOL_CLEAR, sim)
    if (
        not r.ok
        or city.tiles[city.offset(15, 15)] != ID_RUBBLE
        or (15, 16) not in r.dirty
        or (16, 16) not in r.dirty
        or (17, 16) not in r.dirty
        or not r.flush_iso
    ):
        lines.append(
            f"FAIL  clear reservoir {r.message} "
            f"id={city.tiles[city.offset(15, 15)]:#x} flush={r.flush_iso}"
        )
    else:
        lines.append("ok    Clear reservatório → 0x05 + dirty amplo + flush iso")
    r = try_place(city, 15, 15, TOOL_CLEAR, sim)
    if not r.ok or city.tiles[city.offset(15, 15)] != ID_CLEAR:
        lines.append(f"FAIL  rubble→clear {city.tiles[city.offset(15, 15)]:#x}")
    else:
        lines.append("ok    Clear entulho → 0x1C")
    sim.treasury = 51
    try_place(city, 15, 15, TOOL_RESERVOIR, sim)

    off = city.offset(20, 20)
    city.tiles[off] = 0x1E
    city.tiles[off + 1] = FLAG_RIVER
    city.tiles[city.offset(21, 20)] = 0x14
    city.tiles[city.offset(21, 20) + 1] = 0
    sim.treasury = 51
    r = try_place(city, 20, 20, TOOL_RESERVOIR, sim)
    if r.ok or city.tiles[off] != 0x1E:
        lines.append(f"FAIL  reservoir rio {r.message}")
    else:
        lines.append("ok    Reservoir recusa rio")
    sim.treasury = 51
    r = try_place(city, 21, 20, TOOL_RESERVOIR, sim)
    t = city.tile(21, 20)
    if not r.ok or (t.coverage & 3) != 3 or t.variant != VAR_RESERVOIR + 3:
        lines.append(
            f"FAIL  reservoir fill {r.message} +10={t.coverage:#x} +4={t.variant:#x}"
        )
    else:
        lines.append("ok    Reservoir junto ao rio enche +10=3 +4=0x71")

    city.tiles[city.offset(30, 30)] = 0x14
    sim.treasury = 20
    r = try_place(city, 30, 30, TOOL_WELL, sim)
    t = city.tile(30, 30)
    if (
        not r.ok
        or t.terrain_id != ID_WELL
        or t.draw != DRAW_WELL
        or t.variant != VAR_WELL
        or sim.treasury != 0
    ):
        lines.append(f"FAIL  well {r.message} id={t.terrain_id:#x} treas={sim.treasury}")
    else:
        lines.append("ok    Well 0xD7 +3=0x08 +4=0x10 -20")
    well_near = city.tiles[city.offset(30, 32) + 13] & 2
    well_far = city.tiles[city.offset(30, 33) + 13] & 2
    if not well_near or well_far:
        lines.append(
            f"FAIL  well splash r=2 near={well_near:#x} far={well_far:#x}"
        )
    else:
        lines.append("ok    Well +13 0x02 r=2 (not infinite)")

    city.tiles[city.offset(31, 30)] = 0x14
    sim.treasury = 3
    r = try_place(city, 31, 30, TOOL_GARDEN, sim)
    t = city.tile(31, 30)
    g0, v0 = garden_from_step(0)
    if (
        not r.ok
        or t.terrain_id != g0
        or t.draw != DRAW_GARDEN
        or t.variant != v0
        or sim.treasury != 0
    ):
        lines.append(f"FAIL  garden {r.message} id={t.terrain_id:#x} +4={t.variant:#x}")
    else:
        lines.append(f"ok    Garden {g0:#x} +3=0x04 +4={v0:#x} -3")

    city.tiles[city.offset(32, 30)] = 0x14
    sim.treasury = 100
    r = try_place(city, 32, 30, TOOL_PREFECTURE, sim)
    t = city.tile(32, 30)
    if (
        not r.ok
        or t.terrain_id != ID_PREFECTURE
        or t.draw != DRAW_PREFECTURE
        or t.variant != VAR_PREFECTURE
    ):
        lines.append(f"FAIL  prefecture {r.message} +3={t.draw:#x} +4={t.variant:#x}")
    else:
        lines.append("ok    Praefecture 0xE3 +3=0x80 +4=0x50 -100")
    pref10 = city.tiles[city.offset(32, 30) + 10] & 0x30
    if pref10 != 0x30:
        lines.append(f"FAIL  prefecture +10 splash {pref10:#x}")
    else:
        lines.append("ok    Praefecture +10 0x30 r=2")

    city.tiles[city.offset(33, 30)] = 0x14
    sim.treasury = 15
    r = try_place(city, 33, 30, TOOL_FOUNTAIN, sim)
    t = city.tile(33, 30)
    if not r.ok or t.terrain_id != ID_FOUNTAIN or t.variant != VAR_FOUNTAIN:
        lines.append(f"FAIL  fountain {r.message} +4={t.variant:#x}")
    else:
        lines.append("ok    Fountain 0xDD +3=0x08 +4=0x5F dry -15")
    dry_nb = city.tiles[city.offset(35, 30) + 13] & 1
    if dry_nb:
        lines.append(f"FAIL  dry fountain leaked splash +13={dry_nb:#x}")
    else:
        lines.append("ok    dry Fountain (no reservoir ring) does not splash")
    city.tiles[city.offset(24, 20)] = 0x14
    city.tiles[city.offset(24, 20) + 1] = 0
    sim.treasury = 15
    r = try_place(city, 24, 20, TOOL_FOUNTAIN, sim)
    wet = city.tiles[city.offset(30, 20) + 13] & 1
    past = city.tiles[city.offset(31, 20) + 13] & 1
    fvar = city.tiles[city.offset(24, 20) + 4]
    if not r.ok or not wet or past or fvar != 0x60:
        lines.append(
            f"FAIL  charged fountain r=6 {r.message} d6={wet:#x} d7={past:#x} +4={fvar:#x}"
        )
    else:
        lines.append("ok    charged Fountain +13 0x01 r=6 +4=0x60 wet")

    city.tiles[city.offset(34, 30)] = 0x14
    sim.treasury = 75
    r = try_place(city, 34, 30, TOOL_TOWER, sim)
    t = city.tile(34, 30)
    if not r.ok or t.terrain_id != ID_TOWER or t.variant != VAR_TOWER_ALONE:
        lines.append(f"FAIL  tower {r.message} +4={t.variant:#x}")
    else:
        lines.append("ok    Tower 0xBF sozinho +4=0x80 (sem wall-cap)")

    for dy in range(3):
        for dx in range(3):
            city.tiles[city.offset(40 + dx, 40 + dy)] = 0x14
            city.tiles[city.offset(40 + dx, 40 + dy) + 1] = 0
    sim.treasury = 400
    r = try_place(city, 40, 40, TOOL_BARRACKS, sim)
    vars9 = [
        city.tiles[city.offset(40 + dx, 40 + dy) + 4]
        for dy in range(3)
        for dx in range(3)
    ]
    if (
        not r.ok
        or city.tiles[city.offset(40, 40)] != ID_BARRACKS
        or vars9 != list(_BARRACKS_VAR)
        or sim.treasury != 0
    ):
        lines.append(f"FAIL  barracks {r.message} +4={vars9}")
    else:
        lines.append("ok    Barracks 0xE4 3×3 +4=0x51–0x59 -400")
    e4 = [
        (40 + dx, 40 + dy)
        for dy in range(3)
        for dx in range(3)
        if city.tiles[city.offset(40 + dx, 40 + dy)] == ID_BARRACKS
    ]
    origins = [
        c for c in e4 if (city.tiles[city.offset(*c) + 5] & 0xF) == 0
    ]
    if r.flush_iso or len(e4) != 9 or origins != [(40, 40)]:
        lines.append(
            f"FAIL  barracks one-origin flush={r.flush_iso} n={len(e4)} {origins}"
        )
    else:
        lines.append("ok    Barracks place = 1 origem, dirty (sem flush iso)")

    if (
        building_footprint_size(ID_BARRACKS) != 3
        or building_footprint_size(ID_RESERVOIR) != 1
        or building_footprint_size(0x9C) != 2
        or building_footprint_size(0xA1) != 3
        or building_footprint_size(0xE3) != 1
    ):
        lines.append(
            f"FAIL  94FE5 size E4={building_footprint_size(ID_BARRACKS)} "
            f"BE={building_footprint_size(ID_RESERVOIR)}"
        )
    else:
        lines.append("ok    DAT_00094FE5 Barracks 3 / villa 2 / palace 3 / BE 1")

    r = try_place(city, 41, 41, TOOL_ROAD, sim)
    mid = city.tiles[city.offset(41, 41)]
    if r.ok or mid != ID_BARRACKS or "ocupado" not in r.message:
        lines.append(f"FAIL  road on barracks {r.message} id={mid:#x}")
    else:
        lines.append("ok    estrada recusa tile do quartel (+0 >= 0x7C)")

    city.tiles[city.offset(39, 40)] = 0x14
    city.tiles[city.offset(39, 40) + 1] = 0
    city.tiles[city.offset(43, 40)] = 0x14
    city.tiles[city.offset(43, 40) + 1] = 0
    prev = preview_span(city, TOOL_ROAD, 39, 40, 43, 40, 0)
    if (
        (41, 40) not in prev.skip
        or (39, 40) not in prev.stamp
        or (43, 40) not in prev.stamp
        or "ocupado" not in prev.message
    ):
        lines.append(f"FAIL  road skip barracks {prev.message} skip={prev.skip}")
    else:
        lines.append("ok    linha de estrada salta o 3×3, carimba os lados")
    r = try_place_span(city, 39, 40, 43, 40, TOOL_ROAD, sim)
    left = city.tiles[city.offset(39, 40)]
    hit = city.tiles[city.offset(41, 40)]
    right = city.tiles[city.offset(43, 40)]
    if (
        not r.ok
        or hit != ID_BARRACKS
        or not (ID_ROAD_LO <= left <= ID_ROAD_HI)
        or not (ID_ROAD_LO <= right <= ID_ROAD_HI)
    ):
        lines.append(
            f"FAIL  road span occ {r.message} {left:#x}/{hit:#x}/{right:#x}"
        )
    else:
        lines.append("ok    arrasto: estrada à volta do quartel, sem overwrite")

    r = try_place(city, 41, 41, TOOL_TENT, sim)
    if r.ok or city.tiles[city.offset(41, 41)] != ID_BARRACKS:
        lines.append(f"FAIL  tent on barracks {r.message}")
    else:
        lines.append("ok    tenda recusa tile do quartel")

    for dy in range(3):
        for dx in range(3):
            city.tiles[city.offset(55 + dx, 55 + dy)] = 0x14
            city.tiles[city.offset(55 + dx, 55 + dy) + 1] = 0
    sim.treasury = 400
    try_place(city, 55, 55, TOOL_BARRACKS, sim)
    r = try_place(city, 57, 56, TOOL_CLEAR, sim)
    ids9 = [
        city.tiles[city.offset(55 + dx, 55 + dy)]
        for dy in range(3)
        for dx in range(3)
    ]
    if not r.ok or any(v != ID_RUBBLE for v in ids9):
        lines.append(f"FAIL  clear barracks group {r.message} {ids9}")
    else:
        lines.append("ok    Clear num tile do quartel → 3×3 rubble 0x05")

    for dy in range(2):
        for dx in range(2):
            city.tiles[city.offset(70 + dx, 70 + dy)] = 0x9C
            city.tiles[city.offset(70 + dx, 70 + dy) + 1] = 0x01
            city.tiles[city.offset(70 + dx, 70 + dy) + 5] = dy * 2 + dx
    r = try_place(city, 71, 71, TOOL_CLEAR, sim)
    villa = [
        city.tiles[city.offset(70 + dx, 70 + dy)]
        for dy in range(2)
        for dx in range(2)
    ]
    if not r.ok or any(v != ID_RUBBLE for v in villa):
        lines.append(f"FAIL  clear villa group {r.message} {villa}")
    else:
        lines.append("ok    Clear num tile de villa 0x9C → 2×2 rubble")

    city.tiles[city.offset(36, 36)] = 0xD0
    city.tiles[city.offset(36, 36) + 1] = FLAG_PIPE
    r = try_place(city, 36, 36, TOOL_ROAD, sim)
    if r.ok or city.tiles[city.offset(36, 36)] != 0xD0:
        lines.append(f"FAIL  road on aqueduct {r.message}")
    else:
        lines.append("ok    estrada recusa aqueduto 0xD0")
    city.tiles[city.offset(36, 37)] = ID_RESERVOIR
    city.tiles[city.offset(36, 37) + 1] = FLAG_RESERVOIR
    r = try_place(city, 36, 37, TOOL_ROAD, sim)
    if r.ok or city.tiles[city.offset(36, 37)] != ID_RESERVOIR:
        lines.append(f"FAIL  road on reservoir {r.message}")
    else:
        lines.append("ok    estrada recusa reservatório 0xBE")
    city.tiles[city.offset(37, 37)] = ID_GARDEN
    city.tiles[city.offset(37, 37) + 1] = 0x01
    r = try_place(city, 37, 37, TOOL_ROAD, sim)
    gid = city.tiles[city.offset(37, 37)]
    if not r.ok or not (ID_ROAD_LO <= gid <= ID_ROAD_HI):
        lines.append(f"FAIL  road on garden should stamp {r.message} {gid:#x}")
    else:
        lines.append("ok    estrada em Garden 0x78 (EXE 0x66B8D só bloqueia ≥ 0x7C)")

    house = span_cells(TOOL_TENT, 5, 5, 7, 6)
    if house != rect_cells(5, 5, 7, 6) or len(house) != 6:
        lines.append(f"FAIL  housing rect {house}")
    else:
        lines.append("ok    Housing span continua rect 3x2")
    road = span_cells(TOOL_ROAD, 5, 5, 8, 7)
    if road != line_cells(5, 5, 8, 7):
        lines.append(f"FAIL  road line {road}")
    else:
        lines.append("ok    Roads span continua linha")
    clear = span_cells(TOOL_CLEAR, 5, 5, 6, 6)
    if clear != rect_cells(5, 5, 6, 6):
        lines.append(f"FAIL  clear rect {clear}")
    else:
        lines.append("ok    Clear span continua rect")
    ghost = span_cells(TOOL_BARRACKS, 5, 5, 11, 21)
    want = footprint_cells(11, 21, BARRACKS_SIZE)
    if ghost != want or len(ghost) != 9 or (5, 5) in ghost:
        lines.append(f"FAIL  barracks ghost {ghost}")
    else:
        lines.append("ok    Barracks arrasto = 1 footprint no cursor, não rect")
    res_cells = span_cells(TOOL_RESERVOIR, 5, 5, 8, 9)
    if res_cells != [(8, 9)]:
        lines.append(f"FAIL  reservoir ghost {res_cells}")
    else:
        lines.append("ok    Reservoir arrasto = 1 tile no cursor")
    pieces = stamp_ghost_pieces(TOOL_BARRACKS)
    if len(pieces) != 9 or pieces[0][4] != _BARRACKS_VAR[0]:
        lines.append(f"FAIL  barracks ghost pieces {pieces}")
    else:
        lines.append("ok    Barracks ghost 9 sprites")
    if stamp_ghost_pieces(TOOL_RESERVOIR) != [
        (0, 0, ID_RESERVOIR, DRAW_RESERVOIR, VAR_RESERVOIR)
    ]:
        lines.append("FAIL  reservoir ghost piece")
    else:
        lines.append("ok    Reservoir ghost 1 sprite")
    bath0 = stamp_ghost_pieces(TOOL_BATHS, facing=0)
    bath1 = stamp_ghost_pieces(TOOL_BATHS, facing=1)
    # Facing 1: visual-north (0,1) keeps the origin +4 0x63.
    sw1 = next((p for p in bath1 if p[0] == 0 and p[1] == 1), None)
    if not bath0 or bath0[0][4] != 0x63:
        lines.append(f"FAIL  baths ghost facing 0 {bath0}")
    elif sw1 is None or sw1[4] != 0x63:
        lines.append(f"FAIL  baths ghost facing 1 SW {sw1}")
    else:
        lines.append("ok    Baths ghost facing 1 keeps origin +4 on SW")

    for dy in range(3):
        for dx in range(3):
            city.tiles[city.offset(12 + dx, 22 + dy)] = 0x14
            city.tiles[city.offset(12 + dx, 22 + dy) + 1] = 0
    prev = preview_span(city, TOOL_BARRACKS, 0, 0, 12, 22, 400)
    if (
        prev.width != 3
        or prev.height != 3
        or set(prev.stamp) != set(footprint_cells(12, 22, 3))
        or prev.refuse
    ):
        lines.append(f"FAIL  barracks preview {prev.message} {prev.stamp}")
    else:
        lines.append("ok    Barracks preview 3x3 segue (12,22)")
    sim.treasury = 400
    r = try_place_span(city, 0, 0, 12, 22, TOOL_BARRACKS, sim)
    origin = city.tiles[city.offset(12, 22)]
    far = city.tiles[city.offset(40, 40)]
    if (
        not r.ok
        or origin != ID_BARRACKS
        or far != ID_BARRACKS
        or sim.treasury != 0
        or city.tiles[city.offset(0, 0)] == ID_BARRACKS
    ):
        lines.append(
            f"FAIL  barracks span-one {r.message} (12,22)={origin:#x} "
            f"(40,40)={far:#x} treas={sim.treasury}"
        )
    else:
        lines.append("ok    Barracks solta = um forte no cursor")

    city.tiles[city.offset(60, 60)] = 0x14
    city.tiles[city.offset(60, 60) + 1] = 0
    city.tiles[city.offset(61, 60)] = 0x14
    city.tiles[city.offset(61, 60) + 1] = 0
    sim.treasury = 51
    r = try_place_span(city, 60, 60, 61, 60, TOOL_RESERVOIR, sim)
    a = city.tiles[city.offset(60, 60)]
    b = city.tiles[city.offset(61, 60)]
    if not r.ok or a == ID_RESERVOIR or b != ID_RESERVOIR or sim.treasury != 0:
        lines.append(
            f"FAIL  reservoir stamp-one {r.message} {a:#x}/{b:#x} treas={sim.treasury}"
        )
    else:
        lines.append("ok    Reservoir solta = um só (não rect 2 tiles)")

    city.tiles[city.offset(50, 40)] = 0x14
    city.tiles[city.offset(51, 40)] = 0x14
    r = try_place(city, 50, 40, TOOL_AQUEDUCT, None)
    a = city.tiles[city.offset(50, 40)]
    if r.ok or a == ID_AQUEDUCT_STUB:
        lines.append(f"FAIL  aqueduct isolado {r.message} {a:#x}")
    else:
        lines.append("ok    Aqueduct isolado recusado")
    r = try_place_span(city, 50, 40, 53, 40, TOOL_AQUEDUCT, None)
    if r.ok or any(
        ID_AQUEDUCT_LO <= city.tiles[city.offset(50 + i, 40)] <= ID_AQUEDUCT_HI
        for i in range(4)
    ):
        lines.append(f"FAIL  aqueduct linha isolada {r.message}")
    else:
        lines.append("ok    Aqueduct linha isolada recusada")
    city.tiles[city.offset(16, 15)] = 0x14
    r = try_place(city, 16, 15, TOOL_AQUEDUCT, None)
    a = city.tiles[city.offset(16, 15)]
    if not r.ok or a != 0xCE:
        lines.append(f"FAIL  aqueduct no BE {r.message} {a:#x}")
    else:
        lines.append(f"ok    Aqueduct cola no Reservoir → {a:#x} (W-end 0xCE)")
    r = try_place(city, 51, 40, TOOL_AQUEDUCT, None)
    if r.ok:
        lines.append(f"FAIL  aqueduct longe {r.message}")
    else:
        lines.append("ok    Aqueduct longe da rede recusado")
    city.tiles[city.offset(17, 15)] = 0x14
    r = try_place(city, 17, 15, TOOL_AQUEDUCT, None)
    a = city.tiles[city.offset(16, 15)]
    b = city.tiles[city.offset(17, 15)]
    if not r.ok or a != 0xD0 or b != 0xCE:
        lines.append(f"FAIL  aqueduct EW {r.message} {a:#x}/{b:#x}")
    else:
        lines.append("ok    Aqueduct vizinho EW → 0xD0 / cap 0xCE")

    city.tiles[city.offset(15, 16)] = 0x14
    city.tiles[city.offset(15, 16) + 1] = 0
    r = try_place(city, 15, 16, TOOL_AQUEDUCT, None)
    ns = city.tiles[city.offset(15, 16)]
    city.tiles[city.offset(16, 16)] = 0x14
    city.tiles[city.offset(16, 16) + 1] = 0
    r2 = try_place(city, 16, 16, TOOL_AQUEDUCT, None)
    corner = city.tiles[city.offset(16, 16)]
    jn = city.tiles[city.offset(16, 15)]
    if not r.ok or ns != 0xCC:
        lines.append(f"FAIL  aqueduct NS {r.message} {ns:#x}")
    elif not r2.ok or corner != 0xD4 or jn != 0xD6:
        lines.append(
            f"FAIL  aqueduct junção {r2.message} corner={corner:#x} j={jn:#x}"
        )
    else:
        lines.append("ok    Aqueduct NS → 0xCC / canto 0xD4 / T 0xD6")

    # Relva vizinha com FLAG_PAD residual: o retile de estrada é que
    # escrevia o losango 0x52 que o jogador não pôs.
    pad_off = city.offset(17, 16)
    city.tiles[pad_off] = 0x14
    city.tiles[pad_off + 1] = FLAG_PAD
    city.tiles[city.offset(18, 15)] = 0x14
    city.tiles[city.offset(18, 15) + 1] = 0
    r = try_place(city, 18, 15, TOOL_AQUEDUCT, None)
    fake = city.tiles[pad_off]
    aq18 = city.tiles[city.offset(18, 15)]
    if not r.ok or ID_ROAD_LO <= fake <= ID_ROAD_HI or ID_ROAD_LO <= aq18 <= ID_ROAD_HI:
        lines.append(
            f"FAIL  aqueduct escreveu estrada {r.message} "
            f"pad={fake:#x} aq={aq18:#x}"
        )
    else:
        lines.append("ok    Aqueduct não escreve 0x52–0x5C (relva+pad intacta)")
    roads = [
        (x, y, city.tiles[city.offset(x, y)])
        for x, y in ((16, 16), (17, 14), (18, 16), (19, 15))
        if in_map(x, y) and ID_ROAD_LO <= city.tiles[city.offset(x, y)] <= ID_ROAD_HI
    ]
    if roads:
        lines.append(f"FAIL  aqueduct retilou vizinho para estrada {roads}")
    else:
        lines.append("ok    Aqueduct não dispara retile de estrada nos vizinhos")
    if r.flush_iso or (18, 16) not in r.dirty:
        lines.append(f"FAIL  aqueduct dirty extra_rows flush={r.flush_iso}")
    else:
        lines.append("ok    Aqueduct dirty extra_rows (como prédio, sem flush)")

    if (
        aqueduct_id_for(0) != 0xCB
        or aqueduct_id_for(0x0A) != 0xD0
        or aqueduct_id_for(0x05) != 0xCF
        or aqueduct_id_for(0x03) != 0xD1
        or aqueduct_id_for(0x07) != 0xD5
        or aqueduct_id_for(0x0B) != 0xD6
        or aqueduct_id_for(0x0F) != 0xD6
        or aqueduct_road_id_for(0x05) != 0xD5
        or aqueduct_road_id_for(0x0A) != 0xD6
        or reservoir_dry_for(0) != 0x6E
        or reservoir_dry_for(0x02) != 0x76
        or reservoir_dry_for(0x08) != 0x7E
    ):
        lines.append("FAIL  aqueduct LUT 0x94D8F mask")
    else:
        lines.append("ok    Aqueduct LUT 0x94D8F (cap/NS/EW/canto/T)")

    for x in range(19, 24):
        city.tiles[city.offset(x, 15)] = 0x14
        city.tiles[city.offset(x, 15) + 1] = 0
    r = try_place_span(city, 23, 15, 19, 15, TOOL_AQUEDUCT, None)
    ids = [city.tiles[city.offset(x, 15)] for x in range(19, 24)]
    if not r.ok or ids != [0xD0, 0xD0, 0xD0, 0xD0, 0xCE]:
        lines.append(f"FAIL  aqueduct reverse drag {r.message} {ids}")
    else:
        lines.append("ok    Aqueduct arrasto invertido (longe→reservatório) → 0xD0/0xCE")
    for x in range(19, 24):
        city.tiles[city.offset(x, 15)] = 0x14
        city.tiles[city.offset(x, 15) + 1] = 0
    r = try_place_span(city, 19, 15, 23, 15, TOOL_AQUEDUCT, None)
    ids = [city.tiles[city.offset(x, 15)] for x in range(19, 24)]
    if not r.ok or ids != [0xD0, 0xD0, 0xD0, 0xD0, 0xCE]:
        lines.append(f"FAIL  aqueduct line drag {r.message} {ids}")
    else:
        lines.append("ok    Aqueduct arrasto linha EW (como estrada) → 0xD0/0xCE")
    far = try_place_span(city, 60, 50, 64, 50, TOOL_AQUEDUCT, None)
    if far.ok:
        lines.append(f"FAIL  aqueduct linha isolada {far.message}")
    else:
        lines.append("ok    Aqueduct linha sem rede recusada")
    ghosts = aqueduct_preview_cells(
        city, [(60, 60), (61, 60)], [(60, 60), (61, 60)]
    )
    if len(ghosts) != 2 or ghosts[0][2] != 0xCD or ghosts[1][2] != 0xCE:
        lines.append(f"FAIL  aqueduct preview ghost {ghosts}")
    else:
        lines.append("ok    Aqueduct preview ghost EW caps na linha")

    # Inland BE fed only by aqueduct from a river-adjacent BE.
    city.tiles[city.offset(21, 21)] = 0x14
    city.tiles[city.offset(21, 21) + 1] = 0
    city.tiles[city.offset(21, 22)] = 0x14
    city.tiles[city.offset(21, 22) + 1] = 0
    r = try_place(city, 21, 21, TOOL_AQUEDUCT, None)
    sim.treasury = 51
    r2 = try_place(city, 21, 22, TOOL_RESERVOIR, sim)
    inland = city.tile(21, 22)
    if (
        not r.ok
        or not r2.ok
        or (inland.coverage & 3) != 3
        or inland.variant != 0x75
    ):
        lines.append(
            f"FAIL  inland fill aq={r.message} be={r2.message} "
            f"+10={inland.coverage:#x} +4={inland.variant:#x}"
        )
    else:
        lines.append("ok    Reservoir interior enche via aqueduto")

    # Isolated aqueduct (manual stub) must stay dry; Clear wipes 0xCB–0xD6.
    iso_off = city.offset(62, 40)
    city.tiles[iso_off] = 0xD0
    city.tiles[iso_off + 1] = FLAG_PIPE
    city.tiles[iso_off + 3] = DRAW_AQUEDUCT
    city.tiles[iso_off + 4] = 0x76
    city.tiles[iso_off + 9] = 0x76
    rebuild_pipe_charge(city, [(62, 40)])
    iso_t = city.tile(62, 40)
    if (iso_t.coverage & 3) or iso_t.variant != 0x76:
        lines.append(
            f"FAIL  aqueduct isolado molhado +10={iso_t.coverage:#x} +4={iso_t.variant:#x}"
        )
    else:
        lines.append("ok    Aqueduct isolado fica seco (+4=+9, charge 0)")
    river_off = city.offset(64, 40)
    city.tiles[river_off] = 0x1E
    city.tiles[river_off + 1] = FLAG_RIVER
    near_off = city.offset(65, 40)
    city.tiles[near_off] = 0xD0
    city.tiles[near_off + 1] = FLAG_PIPE
    city.tiles[near_off + 3] = DRAW_AQUEDUCT
    city.tiles[near_off + 4] = 0x76
    city.tiles[near_off + 9] = 0x76
    rebuild_pipe_charge(city, [(65, 40)])
    near_t = city.tile(65, 40)
    if (near_t.coverage & 3) or near_t.variant != 0x76:
        lines.append(
            f"FAIL  aqueduct no rio sem BE +10={near_t.coverage:#x} +4={near_t.variant:#x}"
        )
    else:
        lines.append("ok    Aqueduct no rio sem reservatório fica seco")
    r = try_place(city, 62, 40, TOOL_CLEAR, None)
    if not r.ok or city.tiles[iso_off] != ID_RUBBLE:
        lines.append(f"FAIL  clear aqueduct {r.message} id={city.tiles[iso_off]:#x}")
    else:
        lines.append("ok    Clear aqueduct 0xD0 → rubble 0x05")
    r = try_place_span(city, 65, 40, 65, 40, TOOL_CLEAR, None)
    if not r.ok or city.tiles[near_off] != ID_RUBBLE:
        lines.append(
            f"FAIL  clear span aqueduct {r.message} id={city.tiles[near_off]:#x}"
        )
    else:
        lines.append("ok    Clear span apaga 0xCB–0xD6")

    # Fresh spine: river → BE → AQ → AQ. Clear the first AQ; the far cap dries.
    for x, y in ((70, 10), (70, 11), (70, 12), (70, 13)):
        city.tiles[city.offset(x, y)] = 0x14
        city.tiles[city.offset(x, y) + 1] = 0
    city.tiles[city.offset(70, 10)] = 0x1E
    city.tiles[city.offset(70, 10) + 1] = FLAG_RIVER
    sim.treasury = 51
    r_be = try_place(city, 70, 11, TOOL_RESERVOIR, sim)
    r_a = try_place(city, 70, 12, TOOL_AQUEDUCT, None)
    r_b = try_place(city, 70, 13, TOOL_AQUEDUCT, None)
    far = city.tile(70, 13)
    if (
        not r_be.ok
        or not r_a.ok
        or not r_b.ok
        or (far.coverage & 3) != 3
    ):
        lines.append(
            f"FAIL  spine carga {r_be.message}/{r_a.message}/{r_b.message} "
            f"+10={far.coverage:#x}"
        )
    else:
        r_cut = try_place(city, 70, 12, TOOL_CLEAR, None)
        far = city.tile(70, 13)
        if (
            not r_cut.ok
            or not (ID_AQUEDUCT_LO <= far.terrain_id <= ID_AQUEDUCT_HI)
            or (far.coverage & 3)
            or far.variant != far.overlay_anim
        ):
            lines.append(
                f"FAIL  clear corta carga {r_cut.message} "
                f"id={far.terrain_id:#x} +10={far.coverage:#x} +4={far.variant:#x}"
            )
        else:
            lines.append("ok    Clear de um segmento seca o aqueduto desligado")

    # Aqueduct over 0x52–0x5C: LUT 0x94E37 → 0xD6 +3=0x90. Charge
    # continues; Clear restores the road (not rubble).
    for x, y in ((30, 20), (31, 20), (32, 20), (33, 20), (31, 19), (31, 21)):
        city.tiles[city.offset(x, y)] = 0x14
        city.tiles[city.offset(x, y) + 1] = 0
    city.tiles[city.offset(30, 20)] = 0x1E
    city.tiles[city.offset(30, 20) + 1] = FLAG_RIVER
    sim.treasury = 51
    r_be = try_place(city, 31, 20, TOOL_RESERVOIR, sim)
    r_aq = try_place(city, 32, 20, TOOL_AQUEDUCT, None)
    be_join = city.tile(31, 20)
    if (
        not r_be.ok
        or not r_aq.ok
        or be_join.overlay_anim != 0x76
        or be_join.variant != 0x79
    ):
        lines.append(
            f"FAIL  BE inlet E {r_be.message}/{r_aq.message} "
            f"+9={be_join.overlay_anim:#x} +4={be_join.variant:#x}"
        )
    else:
        lines.append("ok    Reservoir +9=0x76 / +4=0x79 (inlet E, LUT 0x94E7F)")
    city.tiles[city.offset(33, 20)] = 0x53
    city.tiles[city.offset(33, 20) + 1] = FLAG_PAD
    city.tiles[city.offset(33, 19)] = 0x52
    city.tiles[city.offset(33, 19) + 1] = FLAG_PAD
    city.tiles[city.offset(33, 21)] = 0x52
    city.tiles[city.offset(33, 21) + 1] = FLAG_PAD
    r_cross = try_place(city, 33, 20, TOOL_AQUEDUCT, None)
    cross = city.tile(33, 20)
    if (
        not r_cross.ok
        or cross.terrain_id != ID_AQUEDUCT_ROAD_EW
        or cross.flags != (FLAG_PIPE | FLAG_PAD)
        or cross.draw != DRAW_AQUEDUCT_ROAD
        or (cross.coverage & 3) != 3
    ):
        lines.append(
            f"FAIL  aqueduct-over-road {r_cross.message} "
            f"id={cross.terrain_id:#x} +1={cross.flags:#x} +3={cross.draw:#x} "
            f"+10={cross.coverage:#x}"
        )
    else:
        lines.append("ok    Aqueduct na estrada → 0xD6 +1=0x60 +3=0x90 (carga 3)")
    r_clr = try_place(city, 33, 20, TOOL_CLEAR, None)
    restored = city.tiles[city.offset(33, 20)]
    rest_fl = city.tiles[city.offset(33, 20) + 1]
    if (
        not r_clr.ok
        or not (ID_ROAD_LO <= restored <= ID_ROAD_HI)
        or not (rest_fl & FLAG_PAD)
        or restored == ID_RUBBLE
    ):
        lines.append(
            f"FAIL  clear combo {r_clr.message} id={restored:#x} +1={rest_fl:#x}"
        )
    else:
        lines.append(f"ok    Clear aqueduct+road restaura estrada {restored:#x}")

    off = city.offset(42, 40)
    city.tiles[off] = 0x1E
    city.tiles[off + 1] = FLAG_RIVER
    r = try_place(city, 42, 40, TOOL_WELL, sim)
    if r.ok:
        lines.append("FAIL  well no rio")
    else:
        lines.append("ok    Well recusa rio")

    city.tiles[city.offset(50, 50)] = 0x14
    city.tiles[city.offset(51, 50)] = 0x14
    sim.treasury = 4
    r = try_place_span(city, 50, 50, 51, 50, TOOL_GARDEN, sim)
    if r.ok or sim.treasury != 4:
        lines.append(f"FAIL  garden span atomic {r.message} treas={sim.treasury}")
    else:
        lines.append("ok    Gardens arrasto atómico (4 < 6)")
    sim.treasury = 6
    r = try_place_span(city, 50, 50, 51, 50, TOOL_GARDEN, sim)
    ga, va = garden_from_step(0)
    gb, vb = garden_from_step(1)
    a = city.tile(50, 50)
    b = city.tile(51, 50)
    if (
        not r.ok
        or a.terrain_id != ga
        or a.variant != va
        or b.terrain_id != gb
        or b.variant != vb
        or ga == gb
        or sim.treasury != 0
    ):
        lines.append(
            f"FAIL  garden span {r.message} {a.terrain_id:#x}/{b.terrain_id:#x} "
            f"+4={a.variant:#x}/{b.variant:#x} treas={sim.treasury}"
        )
    else:
        lines.append(f"ok    Gardens 2 tiles {ga:#x}/{gb:#x} +4={va:#x}/{vb:#x} -6")
    want_pairs = ((0x79, 0x78), (0x7A, 0x79), (0x78, 0x77), (0x7B, 0x7A))
    got_pairs = tuple(garden_from_step(i) for i in range(4))
    if got_pairs != want_pairs:
        lines.append(f"FAIL  garden LUT walk {got_pairs}")
    else:
        lines.append("ok    Garden LUT 0x93FCC passo 0–3 (inc-first)")
    city.tiles[city.offset(52, 50)] = 0x7B
    city.tiles[city.offset(52, 50) + 3] = DRAW_GARDEN
    city.tiles[city.offset(52, 50) + 4] = 0x7A
    prev_keep = preview_span(city, TOOL_GARDEN, 52, 50, 52, 50, 3)
    if prev_keep.stamp or not prev_keep.ok:
        lines.append(f"FAIL  garden keep 0x7B {prev_keep.stamp} {prev_keep.ok}")
    else:
        lines.append("ok    Garden 0x79–0x7B conta como já garden")
    ghosts = garden_preview_cells([(50, 50), (51, 50)], [(50, 50), (51, 50)])
    if (
        len(ghosts) != 2
        or ghosts[0][2:] != (ga, va)
        or ghosts[1][2:] != (gb, vb)
        or ghosts[0][2] == ghosts[1][2]
    ):
        lines.append(f"FAIL  garden preview ghost {ghosts}")
    else:
        lines.append("ok    Garden preview ghost varia no rect")

    # 0x68D2F: id < 0x82 → 697FE flatten (not 696E8 rubble). Garden and
    # plaza/join/statue share that path. Host flatten is 0x1C.
    if (
        clears_to_rubble(ID_GARDEN)
        or clears_to_rubble(ID_GARDEN_HI)
        or clears_to_rubble(ID_PLAZA)
        or clears_to_rubble(ID_PLAZA_JOIN)
        or clears_to_rubble(ID_PLAZA_STATUE)
        or not clears_to_rubble(ID_TENT)
    ):
        lines.append("FAIL  clears_to_rubble 0x78–0x7E vs 0x82")
    else:
        lines.append("ok    clears_to_rubble: garden/plaza < 0x82, tent ≥ 0x82")
    r = try_place(city, 50, 50, TOOL_CLEAR, None)
    if not r.ok or city.tiles[city.offset(50, 50)] != ID_CLEAR:
        lines.append(
            f"FAIL  clear garden {r.message} {city.tiles[city.offset(50, 50)]:#x}"
        )
    else:
        lines.append("ok    Clear garden 0x78–0x7B → 0x1C (sem rubble)")
    r = try_place(city, 51, 50, TOOL_CLEAR, None)
    if city.tiles[city.offset(51, 50)] != ID_CLEAR:
        lines.append(f"FAIL  clear garden2 {city.tiles[city.offset(51, 50)]:#x}")
    city.tiles[city.offset(53, 50)] = ID_PLAZA
    city.tiles[city.offset(53, 50) + 1] = FLAG_PAD
    city.tiles[city.offset(53, 50) + 3] = 0x04
    r = try_place(city, 53, 50, TOOL_CLEAR, None)
    if not r.ok or city.tiles[city.offset(53, 50)] != ID_CLEAR:
        lines.append(
            f"FAIL  clear plaza {r.message} {city.tiles[city.offset(53, 50)]:#x}"
        )
    else:
        lines.append("ok    Clear plaza 0x7C → 0x1C (mesmo path que garden)")
    city.tiles[city.offset(54, 50)] = ID_PLAZA_JOIN
    r = try_place(city, 54, 50, TOOL_CLEAR, None)
    city.tiles[city.offset(55, 50)] = ID_PLAZA_STATUE
    r2 = try_place(city, 55, 50, TOOL_CLEAR, None)
    if (
        city.tiles[city.offset(54, 50)] != ID_CLEAR
        or city.tiles[city.offset(55, 50)] != ID_CLEAR
    ):
        lines.append(
            f"FAIL  clear plaza join/statue "
            f"{city.tiles[city.offset(54, 50)]:#x}/"
            f"{city.tiles[city.offset(55, 50)]:#x}"
        )
    else:
        lines.append("ok    Clear plaza join 0x7D / statue 0x7E → 0x1C")

    def _grass_block(ox: int, oy: int, w: int = 1, h: int = 1) -> None:
        for dy in range(h):
            for dx in range(w):
                off = city.offset(ox + dx, oy + dy)
                city.tiles[off] = 0x14
                city.tiles[off + 1] = 0
                city.tiles[off + 3] = 0
                city.tiles[off + 4] = 0
                city.tiles[off + 5] = 0
                city.tiles[off + 19] = 0

    _grass_block(2, 2, 2, 2)
    sim.treasury = 200
    r = try_place(city, 2, 2, TOOL_TEMPLE, sim)
    temple_ids = [city.tiles[city.offset(2 + dx, 2 + dy)] for dy in range(2) for dx in range(2)]
    temple_var = [city.tiles[city.offset(2 + dx, 2 + dy) + 4] for dy in range(2) for dx in range(2)]
    if (
        not r.ok
        or temple_ids != [ID_TEMPLE] * 4
        or temple_var != [0x40, 0x42, 0x41, 0x43]
        or sim.treasury != 0
    ):
        lines.append(
            f"FAIL  temple {r.message} {temple_ids} {temple_var} treas={sim.treasury}"
        )
    else:
        lines.append("ok    Temple 0xA6 2×2 +4 SAV custo 200")

    _grass_block(2, 6)
    sim.treasury = 12
    r = try_place(city, 2, 6, TOOL_PLAZA, sim)
    if r.ok:
        lines.append(f"FAIL  plaza sem estrada {r.message}")
    else:
        lines.append("ok    Plaza recusa sem estrada")
    try_place(city, 3, 6, TOOL_ROAD, None)
    r = try_place(city, 2, 6, TOOL_PLAZA, sim)
    if not r.ok or city.tiles[city.offset(2, 6)] != ID_PLAZA or sim.treasury != 0:
        lines.append(
            f"FAIL  plaza junto à estrada {r.message} "
            f"{city.tiles[city.offset(2, 6)]:#x} treas={sim.treasury}"
        )
    else:
        lines.append("ok    Plaza 0x7C 1×1 custo 12 junto à estrada")

    _grass_block(2, 8, 5, 1)
    try_place(city, 4, 8, TOOL_ROAD, None)
    sim.treasury = 100
    r = try_place_span(city, 2, 8, 6, 8, TOOL_WALL, sim)
    wall_id = city.tiles[city.offset(2, 8)]
    gate_id = city.tiles[city.offset(4, 8)]
    if not r.ok or wall_id != ID_WALL_EW or gate_id != ID_GATE or sim.treasury != 15:
        lines.append(
            f"FAIL  wall {r.message} {wall_id:#x} {gate_id:#x} treas={sim.treasury}"
        )
    else:
        lines.append("ok    Wall linha EW + Gate 0xC0 na estrada")

    _grass_block(10, 8, 3, 1)
    sim.treasury = 175
    r = try_place(city, 10, 8, TOOL_TOWER, sim)
    r2 = try_place_span(city, 11, 8, 12, 8, TOOL_WALL, sim)
    lone = city.tile(10, 8)
    if (
        not r.ok
        or not r2.ok
        or lone.terrain_id != ID_TOWER
        or lone.variant != VAR_TOWER
    ):
        lines.append(
            f"FAIL  tower+wall E {r.message}/{r2.message} +4={lone.variant:#x}"
        )
    else:
        lines.append("ok    Tower com Wall a leste +4=0x96 (Achea E)")
    r = try_place(city, 11, 8, TOOL_CLEAR, None)
    r = try_place(city, 12, 8, TOOL_CLEAR, None)
    lone = city.tile(10, 8)
    if lone.terrain_id != ID_TOWER or lone.variant != VAR_TOWER_ALONE:
        lines.append(f"FAIL  tower após clear wall +4={lone.variant:#x}")
    else:
        lines.append("ok    Tower sem vizinho wall volta a standalone")

    _grass_block(2, 12, 6, 3)
    sim.treasury = 1500
    r = try_place(city, 2, 12, TOOL_CIRCUS, sim)
    circus_a = city.tiles[city.offset(2, 12)]
    circus_b = city.tiles[city.offset(5, 12)]
    if (
        not r.ok
        or circus_a != ID_CIRCUS_C
        or circus_b != ID_CIRCUS_D
        or stamp_wh(TOOL_CIRCUS) != (6, 3)
    ):
        lines.append(f"FAIL  circus {r.message} {circus_a:#x} {circus_b:#x}")
    else:
        lines.append("ok    Circus 0xEB+0xEC 6×3 custo 1500")
    group = building_group_cells(city, 5, 13)
    if len(group) != 18:
        lines.append(f"FAIL  circus clear-group {len(group)} {group[:4]}")
    else:
        lines.append("ok    Circus pair entra no wipe N×N")

    from app.city_map import graphic_source_xy

    ns_ghost = stamp_ghost_pieces(TOOL_CIRCUS, facing=1)
    ns_ids = {(p[0], p[1], p[2], p[4]) for p in ns_ghost}
    if (
        stamp_wh(TOOL_CIRCUS, 1) != (3, 6)
        or span_cells(TOOL_CIRCUS, 0, 0, 4, 5, facing=1) != footprint_rect(4, 5, 3, 6)
        or (0, 0, ID_CIRCUS_A, 0x00) not in ns_ids
        or (0, 3, ID_CIRCUS_B, 0x09) not in ns_ids
        or (2, 5, ID_CIRCUS_B, 0x11) not in ns_ids
        or any(p[2] in (ID_CIRCUS_C, ID_CIRCUS_D) for p in ns_ghost)
    ):
        lines.append(f"FAIL  circus ghost facing 1 {ns_ghost[:3]}")
    else:
        lines.append("ok    Circus ghost facing 1 is 0xE9+0xEA 3×6")
    _grass_block(20, 20, 3, 6)
    sim.treasury = 1500
    r = try_place(city, 20, 20, TOOL_CIRCUS, sim, facing=1)
    ns_a = city.tiles[city.offset(20, 20)]
    ns_b = city.tiles[city.offset(20, 23)]
    ns_var = city.tiles[city.offset(20, 20) + 4]
    ns_piece = city.tiles[city.offset(22, 25) + 5] & 0xF
    ns_group = building_group_cells(city, 20, 23)
    leftover = [
        (20 + dx, 20 + dy)
        for dy in range(6)
        for dx in range(3)
        if city.tiles[city.offset(20 + dx, 20 + dy)] not in (
            ID_CIRCUS_A, ID_CIRCUS_B,
        )
    ]
    if (
        not r.ok
        or ns_a != ID_CIRCUS_A
        or ns_b != ID_CIRCUS_B
        or ns_var != 0x00
        or ns_piece != 8
        or len(ns_group) != 18
        or leftover
        or graphic_source_xy(city, 20, 23, 1) != (20, 23)
    ):
        lines.append(
            f"FAIL  circus facing 1 {r.message} {ns_a:#x}/{ns_b:#x} "
            f"+4={ns_var:#x} p={ns_piece} n={len(ns_group)} extra={leftover}"
        )
    else:
        lines.append("ok    Circus facing 1 writes 0xE9+0xEA 3×6 cohesive")

    _grass_block(10, 2, 4, 8)
    sim.treasury = 2500
    sim.population = 0
    sim.pop_peak = 0
    r = try_place(city, 10, 2, TOOL_CMAXIMUS, sim)
    if r.ok or city.tiles[city.offset(10, 2)] == ID_CMAX_A:
        lines.append(f"FAIL  cmax unlocked at pop 0 {r.message}")
    else:
        lines.append("ok    C.Maximus leftover at pop 0")
    sim.pop_peak = 4800
    r = try_place(city, 10, 2, TOOL_CMAXIMUS, sim)
    cmax_a = city.tiles[city.offset(10, 2)]
    cmax_b = city.tiles[city.offset(10, 6)]
    if not r.ok or cmax_a != ID_CMAX_A or cmax_b != ID_CMAX_B:
        lines.append(f"FAIL  cmax {r.message} {cmax_a:#x} {cmax_b:#x}")
    else:
        lines.append("ok    C.Maximus 0xED+0xEE 4×8 custo 2500")
    _grass_block(30, 40, 8, 4)
    sim.treasury = 2500
    sim.pop_peak = 4800
    r = try_place(city, 30, 40, TOOL_CMAXIMUS, sim, facing=1)
    cm_a = city.tiles[city.offset(30, 40)]
    cm_b = city.tiles[city.offset(34, 40)]
    if (
        not r.ok
        or stamp_wh(TOOL_CMAXIMUS, 1) != (8, 4)
        or cm_a != ID_CMAX_C
        or cm_b != ID_CMAX_D
        or city.tiles[city.offset(30, 40) + 4] != 0x44
        or len(building_group_cells(city, 34, 41)) != 32
    ):
        lines.append(f"FAIL  cmax facing 1 {r.message} {cm_a:#x}/{cm_b:#x}")
    else:
        lines.append("ok    C.Maximus facing 1 writes 0xEF+0xF0 8×4")

    _grass_block(16, 2, 3, 3)
    sim.treasury = 80
    set_factory_goods(0)
    r = try_place(city, 16, 2, TOOL_FACTORY, sim)
    factory_extra = city.tiles[city.offset(16, 2) + 19]
    factory_draw = city.tiles[city.offset(16, 2) + 3]
    east_draw = city.tiles[city.offset(17, 2) + 3]
    if (
        not r.ok
        or city.tiles[city.offset(16, 2)] != ID_FACTORY
        or factory_extra != 0
        or factory_draw != 0x8C
        or east_draw != 0x8C
    ):
        lines.append(
            f"FAIL  factory {r.message} +19={factory_extra} "
            f"+3={factory_draw:#04x} east+3={east_draw:#04x}"
        )
    else:
        lines.append("ok    Factory 0xFA 3×3 +19=0 +3=0x8C (Bakery flag80)")
    _grass_block(40, 2, 3, 3)
    sim.treasury = 80
    sim.city_only = 1
    set_factory_goods(1)
    r = try_place(city, 40, 2, TOOL_FACTORY, sim)
    winery = city.tiles[city.offset(40, 2) + 19]
    stock = (city.tiles[city.offset(40, 2) + 9] & 0xF0) >> 4
    if not r.ok or winery != 1:
        lines.append(f"FAIL  winery +19={winery} {r.message}")
    elif stock == 0:
        lines.append(f"FAIL  winery City Only stock {stock} {r.message}")
    else:
        lines.append(f"ok    Factory type Winery +19=1 stock={stock}")
    set_factory_goods(0)
    sim.city_only = 0

    _grass_block(16, 8, 4, 4)
    sim.treasury = 10
    sim.pop_peak = 0
    r = try_place(city, 16, 8, TOOL_PALATINE, sim)
    if r.ok or city.tiles[city.offset(16, 8)] == ID_PALATINE:
        lines.append(f"FAIL  palatine unlocked at pop 0 {r.message}")
    else:
        lines.append("ok    Palatine leftover at pop 0")
    sim.pop_peak = 1800
    r = try_place(city, 16, 8, TOOL_PALATINE, sim)
    if not r.ok or city.tiles[city.offset(16, 8)] != ID_PALATINE or sim.treasury != 10:
        lines.append(f"FAIL  palatine {r.message} treas={sim.treasury}")
    else:
        lines.append("ok    Palatine 0xB7 4×4 sem débito (sem slot C2MODEL)")

    _grass_block(20, 2, 5, 3)
    city.tiles[city.offset(20, 2)] = ID_RESERVOIR
    city.tiles[city.offset(20, 2) + 1] = 0x80
    city.tiles[city.offset(20, 2) + 10] = 3
    city.tiles[city.offset(24, 2)] = ID_TENT
    city.tiles[city.offset(24, 2) + 1] = 0x01
    sim.treasury = 30
    r = try_place(city, 22, 2, TOOL_BATHS, sim)
    bath13 = city.tiles[city.offset(24, 2) + 13]
    from app.city_overlay import query_place

    qbath = " ".join(query_place(city, 24, 2).lines)
    bath4 = city.tiles[city.offset(22, 2) + 4]
    if (
        not r.ok
        or city.tiles[city.offset(22, 2)] != ID_BATHS
        or not (bath13 & 0x08)
        or bath4 != 0x20
        or "Near Baths" not in qbath
        or "Not Near Baths" in qbath
    ):
        lines.append(
            f"FAIL  baths splash {r.message} +13={bath13:#x} +4={bath4:#x} query={qbath}"
        )
    else:
        lines.append("ok    Baths 0xDF +13 0x08 r=5 extra=1 +4=0x20 wet")
    _grass_block(50, 2, 2, 2)
    sim.treasury = 30
    r = try_place(city, 50, 2, TOOL_BATHS, sim)
    dry4 = city.tiles[city.offset(50, 2) + 4]
    from app.city_overlay import OVERLAY_WATER, overlay_pixel

    dry_ov = overlay_pixel(city.tiles, city.offset(50, 2), OVERLAY_WATER)
    if not r.ok or dry4 != 0x63 or dry_ov != 0:
        lines.append(
            f"FAIL  dry baths off-pipe {r.message} +4={dry4:#x} ov={dry_ov:#x}"
        )
    else:
        lines.append("ok    Baths off-pipe +4=0x63 dry overlay plane 0")

    _grass_block(28, 2, 4, 3)
    city.tiles[city.offset(30, 2)] = ID_TENT
    city.tiles[city.offset(30, 2) + 1] = 0x01
    sim.treasury = 250
    r = try_place(city, 28, 2, TOOL_GRAMMATICUS, sim)
    hut13 = city.tiles[city.offset(30, 2) + 13]
    qjoin = " ".join(query_place(city, 30, 2).lines)
    if (
        not r.ok
        or city.tiles[city.offset(28, 2)] != ID_GRAMMATICUS
        or not (hut13 & 0x10)
        or "NO Grammaticus Access" in qjoin
        or "Grammaticus Access" not in qjoin
    ):
        lines.append(
            f"FAIL  grammaticus splash {r.message} +13={hut13:#x} query={qjoin}"
        )
    else:
        lines.append("ok    Grammaticus 0xF3 +13 0x10 on adjacent hut")

    _grass_block(34, 2, 4, 3)
    city.tiles[city.offset(36, 2)] = ID_TENT
    city.tiles[city.offset(36, 2) + 1] = 0x01
    sim.treasury = 300
    r = try_place(city, 34, 2, TOOL_THEATER, sim)
    hut12 = city.tiles[city.offset(36, 2) + 12]
    qent = " ".join(query_place(city, 36, 2).lines)
    if (
        not r.ok
        or city.tiles[city.offset(34, 2)] != ID_THEATER
        or not (hut12 & 0x03)
        or "Entertainment Level 0" in qent
        or "Entertainment Level" not in qent
    ):
        lines.append(
            f"FAIL  theater splash {r.message} +12={hut12:#x} query={qent}"
        )
    else:
        lines.append("ok    Theater 0xE5 +12 on adjacent hut")

    _grass_block(22, 6, 3, 3)
    sim.treasury = 500
    r = try_place(city, 22, 6, TOOL_HOSPITAL, sim)
    if not r.ok or city.tiles[city.offset(22, 6)] != ID_HOSPITAL:
        lines.append(f"FAIL  hospital {r.message}")
    else:
        lines.append("ok    Hospital 0xFB 3×3 custo 500")
    qhosp = " ".join(query_place(city, 22, 6).lines)
    if "No Hospital Cover" not in qhosp or "No Road Access" not in qhosp:
        lines.append(f"FAIL  hospital query isolated {qhosp}")
    else:
        lines.append("ok    Hospital query isolated → no road / no cover")
    city.tiles[city.offset(22, 5)] = 0x52
    city.tiles[city.offset(22, 5) + 1] = 0x20
    city.tiles[city.offset(22, 5) + 10] = 0x0C
    qok = " ".join(query_place(city, 22, 6).lines)
    if "Complete Hospital Cover" not in qok or "No Road Access" in qok:
        lines.append(f"FAIL  hospital query working {qok}")
    else:
        lines.append("ok    Hospital query road+forum → complete cover")
    _grass_block(26, 6, 3, 3)
    sim.treasury = 1000
    r = try_place(city, 26, 6, TOOL_LIBRARY, sim)
    if not r.ok or city.tiles[city.offset(26, 6)] != ID_LIBRARY:
        lines.append(f"FAIL  library {r.message}")
    else:
        lines.append("ok    Library 0xF5 3×3 custo 1000")
    city.tiles[city.offset(26, 5)] = 0x52
    city.tiles[city.offset(26, 5) + 1] = 0x20
    city.tiles[city.offset(26, 5) + 10] = 0x0C
    qlib = " ".join(query_place(city, 26, 6).lines)
    if "Complete Library Cover" not in qlib or "No Road Access" in qlib:
        lines.append(f"FAIL  library query {qlib}")
    else:
        lines.append("ok    Library query road+forum → complete cover")

    circus_span = span_cells(TOOL_CIRCUS, 0, 0, 3, 4)
    if circus_span != footprint_rect(3, 4, 6, 3):
        lines.append(f"FAIL  circus span n={len(circus_span)}")
    else:
        lines.append("ok    Circus ghost 6×3 no cursor")
    wall_span = span_cells(TOOL_WALL, 5, 5, 8, 7)
    if wall_span != line_cells(5, 5, 8, 7):
        lines.append(f"FAIL  wall span {wall_span}")
    else:
        lines.append("ok    Wall span continua linha")
    aq_span = span_cells(TOOL_AQUEDUCT, 5, 5, 8, 7)
    if aq_span != line_cells(5, 5, 8, 7):
        lines.append(f"FAIL  aqueduct span {aq_span}")
    else:
        lines.append("ok    Aqueduct span = linha (como estrada), não rect")

    from PIL import Image as _Image

    from app.city_map import iso_canvas_size, tile_iso_xy
    from app.window import overlay_span_preview, overlay_stamp_ghost

    city.tiles[city.offset(15, 25)] = 0x14
    city.tiles[city.offset(16, 25)] = 0x14
    cw, ch = iso_canvas_size(0)
    sx, sy = tile_iso_xy(12, 22, zoom=0)
    cam_x, cam_y = max(0, sx - 160), max(0, sy - 120)
    blank = _Image.new("RGBA", (640, 480), (20, 20, 20, 255))
    tent_prev = preview_span(city, TOOL_TENT, 15, 25, 16, 25, 999)
    tent_over = overlay_span_preview(blank, tent_prev, 0, cam_x, cam_y, cw, ch)
    stamp_prev = preview_span(city, TOOL_BARRACKS, 0, 0, 12, 22, 400)
    stamp_over = overlay_stamp_ghost(
        blank, stamp_prev, 0, cam_x, cam_y, cw, ch, sheets=None
    )
    if tent_over.tobytes() == blank.tobytes():
        lines.append("FAIL  housing overlay vazio")
    else:
        lines.append("ok    Housing overlay (diamantes, não ghost stamp)")
    if stamp_over.tobytes() == blank.tobytes():
        lines.append("FAIL  barracks ghost bbox vazio")
    else:
        lines.append("ok    Barracks ghost bbox (sem PL8)")

    from pathlib import Path as _Path

    from app.boot import BootContext
    from app.window import SCREEN_H, SCREEN_W, compose_frame

    huge = _Image.new("RGBA", (4640, 2400), (200, 30, 30, 255))
    fake = BootContext(
        game=_Path("."),
        source="t",
        resource_cfg=None,
        key_files=[],
        boot_files=[],
        eng=None,
        image=huge,
        image_name="map:t",
        n_sprites=0,
        city=city,
        walkers=[],
        sim=SimState(),
        audio_status="",
        start_in_map=True,
    )
    framed = compose_frame(fake, view=None, map_mode=True)
    mid = framed.getpixel((SCREEN_W // 2, SCREEN_H // 2))
    if framed.size != (SCREEN_W, SCREEN_H):
        lines.append(f"FAIL  map compose size {framed.size}")
    elif mid[0] > 80:
        lines.append("FAIL  map compose _fit do canvas iso (zoom-pop)")
    else:
        lines.append("ok    map compose não thumbnail o iso (sem zoom-pop)")

    from app.palette import selftest as palette_selftest

    lines.extend(palette_selftest())
    return lines


def _tile_center(x: int, y: int, zoom: int = 0) -> tuple[int, int]:
    from app.city_map import tile_iso_xy

    tile_w, tile_h = iso_tile_size(zoom)
    sx, sy = tile_iso_xy(x, y, zoom=zoom)
    return sx + tile_w // 2, sy + tile_h // 2
