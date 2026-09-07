"""City sim painters: +13 water, +15 land-value / service cap, +17 flood.

EXE: wipe 0x51–0x54, paint 0x3FDD0 / 0x3FEF7 / 0x40695 / 0x40D08 / 0x430DA.
Lane helpers match findings/ghidra_water.md and ghidra_tile.md.
"""

from __future__ import annotations

from app.city_map import FLAG_PAD, MAP_H, MAP_W, ROW_STRIDE, TILE_STRIDE
from app.walker_tick import tile_or_radius

HOUSE_SIZE: tuple[int, ...] = (1,) * 26 + (2, 2, 2, 2, 3, 3)


def i8(b: int) -> int:
    return b - 256 if b >= 128 else b

# C2MODEL [215:247] occupancy — origins only (+5 lo == 0).
HOUSE_OCCUPANCY: tuple[int, ...] = (
    2, 4, 6, 8, 10, 12,
    6, 7, 8, 9, 12, 16,
    20, 24, 28, 32, 36, 42, 48, 54,
    20, 25, 30, 35, 40, 45,
    100, 120, 150, 200,
    300, 500,
)
# C2MODEL [247:279] / EXE 0x969E7 — tax wealth. 0x4498D adds only if +10 & 0x0C.
HOUSE_TAX_WEALTH: tuple[int, ...] = (
    1, 2, 3, 4, 5, 6,
    8, 10, 12, 14, 17, 20,
    24, 28, 32, 37, 42, 47, 52, 58,
    64, 70, 77, 84, 92, 100,
    400, 420, 450, 500,
    1200, 1400,
)
MARKET_TAX_BITS = 0x0C
ID_FACTORY = 0xFA
# 0x44dbf: factory stock (+9 hi-nibble) * 70 → [0x102934], if +10 & 0x0C.
FACTORY_WEALTH_UNIT = 0x46
FACTORY_PAD_MASK = 0x27

# 0x962FD / 0x96301 — housing (bonus, radius) by grade.
_HOUSE_LV: tuple[tuple[int, int], ...] = (
    (-2, 1), (-2, 1), (-2, 1), (-1, 1), (-1, 1), (-1, 1),
    (0, 1), (0, 1), (0, 1), (0, 1), (1, 1), (1, 1),
    (1, 1), (1, 1), (1, 1), (1, 1), (1, 1), (1, 1),
    (1, 1), (1, 1), (2, 1), (2, 1), (2, 1), (2, 1),
    (2, 1), (2, 1), (8, 2), (8, 2), (8, 2), (8, 2),
    (16, 2), (16, 2),
)

ID_GARDEN_LO, ID_GARDEN_HI = 0x78, 0x7B
ID_PLAZA_LO, ID_PLAZA_HI = 0x7C, 0x7E
ID_HOUSING_LO, ID_HOUSING_HI = 0x82, 0xA1
ID_RESERVOIR = 0xBE
ID_WELL_LO, ID_WELL_HI = 0xD7, 0xDA
ID_FOUNTAIN_LO, ID_FOUNTAIN_HI = 0xDB, 0xDE
ID_BATH_LO, ID_BATH_HI = 0xDF, 0xE2
ID_PREFECTURE = 0xE3
ID_BARRACKS = 0xE4
ID_THEATER = 0xE5
ID_ODEUM = 0xE6
ID_ARENA = 0xE7
ID_COLISEUM = 0xE8
ID_CIRCUS_LO, ID_CIRCUS_HI = 0xE9, 0xEC
ID_CMAX_LO, ID_CMAX_HI = 0xED, 0xF0
ID_GRAMMATICUS = 0xF3
ID_RHETOR = 0xF4
ID_LIBRARY = 0xF5
ID_HOSPITAL = 0xFB
ID_RIVER_LO, ID_RIVER_HI = 0x1E, 0x51
ID_TOWER = 0xBF
ID_GATE = 0xC0
ID_WALL_NS = 0xC1
ID_WALL_EW = 0xC2
# +1 bits 0x02/0x04 (wall / tower). Gate 0x24 includes 0x04.
FORTIFICATION_IDS = frozenset({ID_TOWER, ID_GATE, ID_WALL_NS, ID_WALL_EW})

# FUN_0004034b / tile_or_radius 0x6CD7E. extra grows +x/+y for the N×N origin.
GRAMMATICUS_SPLASH_R = 6
GRAMMATICUS_SPLASH_EXTRA = 1
RHETOR_SPLASH_R = 8
RHETOR_SPLASH_EXTRA = 2
EDU_GRAMMATICUS_BIT = 0x10
EDU_RHETOR_BIT = 0x20
BATH_SPLASH_BIT = 0x08
BATH_SPLASH_EXTRA = 1
# FUN_0003fef7: fountain +4 = LUT 0x94f6c[id] (dry) or +1 (wet / +13&4).
FOUNTAIN_DRY_VAR = {0xDB: 0x0C, 0xDC: 0x0E, 0xDD: 0x5F, 0xDE: 0x61}
# FUN_0006a368: baths 2×2 +4. Wet 0x20+stage*4; dry 0x63+stage*4.
# Piece order raster y,x: +0,+2 / +1,+3 (LASTYEAR / place stamp).
BATH_WET_BASE = 0x20
BATH_DRY_BASE = 0x63
BATH_PIECE_DELTA = (0, 2, 1, 3)
SECURITY_COV_BITS = 0x30
PREFECTURE_SPLASH_R = 2
BARRACKS_SPLASH_R = 3
HOSPITAL_COVER_POP_FULL = 100
HOSPITAL_COVER_UNIT = 1000
LIBRARY_COVER_UNIT = 1200
CIVIC_COVER_SIZE = 3
FORUM_ACCESS_BITS = 0x0C


def _off(x: int, y: int) -> int:
    return y * ROW_STRIDE + x * TILE_STRIDE


def _in_map(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def wipe_lane(tiles: bytearray, lane: int) -> None:
    """city_map_clear_byte8 0x6E188 — one 80×80 lane."""
    if not (0 <= lane < TILE_STRIDE) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return
    for i in range(MAP_W * MAP_H):
        tiles[i * TILE_STRIDE + lane] = 0


def recount_population(tiles: bytearray) -> int:
    """Sum C2MODEL occupancy on housing origins."""
    pop = 0
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off + 5] & 0xF:
                continue
            hid = tiles[off]
            if ID_HOUSING_LO <= hid <= ID_HOUSING_HI:
                pop += HOUSE_OCCUPANCY[hid - ID_HOUSING_LO]
    return pop


def housing_tax_wealth(tiles: bytearray) -> int:
    """0x4498D: C2MODEL tax wealth on housing origins with market (+10 & 0x0C)."""
    wealth = 0
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off + 5] & 0xF:
                continue
            hid = tiles[off]
            if not (ID_HOUSING_LO <= hid <= ID_HOUSING_HI):
                continue
            if not (tiles[off + 10] & MARKET_TAX_BITS):
                continue
            wealth += HOUSE_TAX_WEALTH[hid - ID_HOUSING_LO]
    return wealth


def industry_tax_wealth(tiles: bytearray) -> int:
    """0x44d7b: 0xFA cells with +1&0x27 and market (+10&0x0C); stock×70.

    Goods nibble is +19 lo; it only indexes the per-good counter, not GDP.
    No stock / no market → 0 (do not invent output).
    """
    wealth = 0
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off] != ID_FACTORY:
                continue
            if not (tiles[off + 1] & FACTORY_PAD_MASK):
                continue
            if not (tiles[off + 10] & MARKET_TAX_BITS):
                continue
            stock = (tiles[off + 9] & 0xF0) >> 4
            wealth += stock * FACTORY_WEALTH_UNIT
    return wealth


def count_taxed_factories(tiles: bytearray) -> int:
    """0xFA origins used as the industry av-bill denominator stand-in."""
    n = 0
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off] != ID_FACTORY:
                continue
            if tiles[off + 5] & 0xF:
                continue
            n += 1
    return n


# goods_16x48 0xD2B6C / SavChunk 339. 41b33 reads +24 (supplied %) and +28 (raw).
GOODS_RECORD = 48
GOODS_COUNT = 16
GOODS_SUPPLIED = 24
GOODS_RAW = 28
FACTORY_OCC_R = 2
FACTORY_OCC_EXTRA = 2
# City Only stand-in: EXE 0x43F05 zeros +24/+28; campaign-only 0x43F5A
# reseeds supplied. Farms are province so raw stays 0. Sandbox fills the
# table the 41b33 City Only cap (province_links<=0 → prod 4) already
# expects. raw=500 is the 0x191…0x258 band (no extra labor penalty).
CITY_ONLY_SUPPLIED = 100
CITY_ONLY_RAW = 500
CITY_ONLY_LABOR = 4
# Overlay: city_tile_draw_flag80 0x37F80. Origin frame = (+19 & 0xF) + 9.
# Non-origin +3 bit7: CITYTOP[hi(west +9)+0x18] (0x37F43, dest 0x9416C).
FACTORY_LABEL_FRAME_BASE = 9
FACTORY_JUG_FRAME_BASE = 0x18
# EXE debug strings 0x90FB5 + UI names from factory.md.
FACTORY_TYPE_NAMES: tuple[str, ...] = (
    "Bakery",
    "Winery",
    "Butcher",
    "Tailor",
    "Gems",
    "Lead Works",
    "Iron",
    "Copper Works",
    "Clay",
    "Glass Works",
    "Marble",
    "Stone Works",
    "Silk",
    "Spice Dealer",
    "Ivory Dealer",
    "Fish Monger",
)


def factory_type_name(nibble: int) -> str:
    idx = nibble & 0xF
    if 0 <= idx < len(FACTORY_TYPE_NAMES):
        return FACTORY_TYPE_NAMES[idx]
    return "Factory"


def factory_label_frame(nibble: int) -> int:
    """CITYTOP frame for the origin goods etiqueta."""
    return (nibble & 0xF) + FACTORY_LABEL_FRAME_BASE


def factory_jug_frame(plus9: int) -> int | None:
    """CITYTOP frame for porch amphorae. Distinct from the goods etiqueta."""
    stock = (plus9 & 0xF0) >> 4
    if stock <= 0:
        return None
    return stock + FACTORY_JUG_FRAME_BASE


def goods_i32(goods: bytes | bytearray | None, nibble: int, off: int) -> int:
    """One i32 from a 16×48 goods record. Missing / short table → 0."""
    idx = nibble & 0xF
    base = idx * GOODS_RECORD + off
    if goods is None or base + 4 > len(goods):
        return 0
    return int.from_bytes(goods[base : base + 4], "little", signed=True)


def goods_set_i32(goods: bytearray, nibble: int, off: int, value: int) -> None:
    idx = nibble & 0xF
    base = idx * GOODS_RECORD + off
    if base + 4 > len(goods):
        return
    goods[base : base + 4] = int(value).to_bytes(4, "little", signed=True)


def seed_city_only_good(goods: bytearray, nibble: int) -> None:
    """Sandbox raw+supplied so 41b33 can write +9 (no province farms)."""
    goods_set_i32(goods, nibble, 0, 1)
    goods_set_i32(goods, nibble, GOODS_SUPPLIED, CITY_ONLY_SUPPLIED)
    goods_set_i32(goods, nibble, GOODS_RAW, CITY_ONLY_RAW)


def seed_city_only_industry(sim, nibble: int | None = None) -> None:
    """Fill chunk 339 for City Only. ``nibble`` None = all 16 goods."""
    goods = getattr(sim, "goods", None)
    if not isinstance(goods, bytearray) or len(goods) < GOODS_COUNT * GOODS_RECORD:
        sim.goods = bytearray(GOODS_COUNT * GOODS_RECORD)
        goods = sim.goods
    if nibble is None:
        for i in range(GOODS_COUNT):
            seed_city_only_good(goods, i)
    else:
        seed_city_only_good(goods, nibble)
    if int(getattr(sim, "factory_labor", 0) or 0) < CITY_ONLY_LABOR:
        sim.factory_labor = CITY_ONLY_LABOR


def housing_occupancy_box(
    tiles: bytearray, x: int, y: int, *, radius: int = 2, extra: int = 2
) -> int:
    """FUN_0006df8d EAX=extra EDX=x EBX=y ECX=radius. Housing origins only."""
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    x0 = x - radius
    y0 = y - radius
    span = radius * 2 + 1
    if extra:
        span = span + extra
    width = span
    height = span
    if x0 < 0:
        width += x0
        x0 = 0
    elif x0 + width > MAP_W:
        width -= (x0 + width) - MAP_W
    if y0 < 0:
        height += y0
        y0 = 0
    elif y0 + height > MAP_H:
        height -= (y0 + height) - MAP_H
    if width <= 0 or height <= 0:
        return 0
    total = 0
    for ny in range(y0, y0 + height):
        for nx in range(x0, x0 + width):
            off = _off(nx, ny)
            hid = tiles[off]
            if hid < ID_HOUSING_LO or hid > ID_HOUSING_HI:
                continue
            if tiles[off + 5] & 0xF:
                continue
            total += HOUSE_OCCUPANCY[hid - ID_HOUSING_LO]
    return total


def factory_produce(
    tiles: bytearray,
    x: int,
    y: int,
    *,
    goods: bytes | bytearray | None = None,
    labor: int = 0,
    province_links: int = 0,
    city_only: bool = False,
) -> int:
    """FUN_00041b33 — write +9 hi stock nibble (0–7) on a 0xFA origin.

    Indexes goods_16x48 by origin +19 lo. Raw dword +28 ≤ 0 or supplied %
    +24 ≤ 0 → stock 0 unless ``city_only`` already seeded the table.
    City Only with no nearby houses uses stage 1 (workshop cycle) so a
    picked type is not stuck at stock 0 after the player places it.
    """
    if not _in_map(x, y):
        return 0
    off = _off(x, y)
    if tiles[off] != ID_FACTORY:
        return 0
    plus9 = tiles[off + 9]
    stage = plus9 & 0x03
    market = plus9 & 0x0C
    nibble = tiles[off + 19] & 0xF
    supplied = goods_i32(goods, nibble, GOODS_SUPPLIED)
    raw = goods_i32(goods, nibble, GOODS_RAW)
    occ = housing_occupancy_box(
        tiles, x, y, radius=FACTORY_OCC_R, extra=FACTORY_OCC_EXTRA
    )
    if city_only and occ == 0 and stage == 0:
        stage = 1
    if occ > 0x82:
        stage += 4
    elif occ > 0x5A:
        stage += 3
    elif occ > 0x32:
        stage += 2
    elif occ > 0x0A:
        stage += 1
    if stage <= 0:
        prod = 0
    elif stage <= 1:
        prod = 3
    elif stage <= 2:
        prod = 5
    else:
        prod = 7
    if market == 0:
        labor -= 2
        if prod > 4:
            prod = 4
    if raw <= 0:
        prod = 0
    elif raw <= 0x32:
        labor -= 3
        if prod > 1:
            prod = 1
    elif raw <= 0xC8:
        labor -= 2
        if prod > 3:
            prod = 3
    elif raw <= 0x190:
        labor -= 1
        if prod > 5:
            prod = 5
    elif raw <= 0x258:
        pass
    elif raw <= 0x320:
        labor += 1
    elif raw <= 0x3E8:
        labor += 2
    else:
        labor += 3
    if province_links <= 0:
        if prod > 4:
            prod = 4
    elif province_links == 1:
        labor += 1
    else:
        labor += 2
    if supplied <= 0:
        prod = 0
    elif supplied <= 0x14:
        if prod > 1:
            prod = 1
    elif supplied <= 0x22:
        if prod > 2:
            prod = 2
    elif supplied <= 0x32:
        if prod > 3:
            prod = 3
    elif supplied <= 0x43:
        if prod > 4:
            prod = 4
    elif supplied <= 0x4B:
        if prod > 5:
            prod = 5
    elif supplied <= 0x63:
        if prod > 6:
            prod = 6
    stock = labor if labor < prod else prod
    if stock < 0:
        stock = 0
    if stock > 7:
        stock = 7
    tiles[off + 9] = (tiles[off + 9] & 0x0F) | ((stock & 0xF) << 4)
    # 0x37F43: east cell (+5 lo==1) flag80 reads west +9. Career/D.SAV
    # already have +3 bit7 there; host place used to set only the origin.
    if x + 1 < MAP_W:
        eoff = _off(x + 1, y)
        if tiles[eoff] == ID_FACTORY:
            tiles[eoff + 3] |= 0x80
    if stage:
        cur = tiles[off + 9] & 0xFC
        if stage == 2:
            cur |= 1
        elif stage == 3:
            cur |= 2
        tiles[off + 9] = cur
    if market:
        cur = tiles[off + 9] & 0xF3
        if market == 8:
            cur |= 4
        elif market == 0x0C:
            cur |= 8
        tiles[off + 9] = cur
    return stock


def factory_produce_row(
    tiles: bytearray,
    y0: int,
    n: int,
    *,
    goods: bytes | bytearray | None = None,
    labor: int = 0,
    province_links: int = 0,
    city_only: bool = False,
) -> int:
    """0x41719 factory arm: +3 |= 1 on every 0xFA; 41b33 on origins."""
    written = 0
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off] != ID_FACTORY:
                continue
            tiles[off + 3] |= 1
            if tiles[off + 5] & 0xF:
                continue
            factory_produce(
                tiles,
                x,
                y,
                goods=goods,
                labor=labor,
                province_links=province_links,
                city_only=city_only,
            )
            written += 1
    return written


def add_land_value(
    tiles: bytearray,
    x: int,
    y: int,
    size: int,
    radius: int,
    bonus: int,
    *,
    skip_own: bool = False,
    skip_housing: bool = False,
) -> None:
    """FUN_0006da0e — add signed bonus over (size+2r) square, clamp −64…+64.

    Housing skips its own footprint so a tent's −2 does not cancel fountain/garden
    splash on that cell (C2MODEL radiates onto neighbors). It also skips other
    housing: a dense hut grid's −2 must not pin watered cells at the +15=2
    hut stay band (0x83 stay 0…3).
    """
    if size <= 0 or bonus == 0:
        return
    x0 = x - radius
    y0 = y - radius
    side = size + 2 * radius
    for dy in range(side):
        for dx in range(side):
            tx, ty = x0 + dx, y0 + dy
            if not _in_map(tx, ty):
                continue
            if skip_own and x <= tx < x + size and y <= ty < y + size:
                continue
            dest = _off(tx, ty)
            if skip_housing:
                hid = tiles[dest]
                if ID_HOUSING_LO <= hid <= ID_HOUSING_HI:
                    continue
            off = dest + 15
            cur = i8(tiles[off]) + bonus
            if cur > 64:
                cur = 64
            elif cur < -64:
                cur = -64
            tiles[off] = cur & 0xFF


def _block_and(tiles: bytearray, x: int, y: int, size: int, lane: int, mask: int) -> int:
    """OR-test mask on lane over size×size. 6dba2 (+13) / 6dc09 (+14)."""
    if size <= 1:
        return tiles[_off(x, y) + lane] & mask
    for dy in range(size):
        for dx in range(size):
            if not _in_map(x + dx, y + dy):
                continue
            if tiles[_off(x + dx, y + dy) + lane] & mask:
                return 1
    return 0


def _block_max(tiles: bytearray, x: int, y: int, size: int, lane: int, mask: int) -> int:
    """Max of (lane & mask) over size×size. 6dc68 (+10) / 6dce0 (+12)."""
    best = 0
    if size <= 1:
        return tiles[_off(x, y) + lane] & mask
    for dy in range(size):
        for dx in range(size):
            if not _in_map(x + dx, y + dy):
                continue
            v = tiles[_off(x + dx, y + dy) + lane] & mask
            if v > best:
                best = v
    return best


def entertainment_level(amenity12: int) -> int:
    """FUN_00040d08 / overlay 0x3E983: sum of three 2-bit +12 channels.

    Theater/Odeum bits 0–1, Arena/Coliseum 2–3, Circus/C.Maximus 4–5.
    Each channel is 0–3 (near/mid/far ring). Query prints this 0–9 total,
    not the packed byte (51 = 0x33 → 3+0+3 = 6).
    """
    return (amenity12 & 3) + ((amenity12 & 0x0C) >> 2) + ((amenity12 & 0x30) >> 4)


def entertainment_level_block(
    tiles: bytearray, x: int, y: int, size: int = 1
) -> int:
    """Same channel sum, max-merged over a housing footprint (6dce0)."""
    ch0 = _block_max(tiles, x, y, size, 12, 0x03)
    ch1 = (_block_max(tiles, x, y, size, 12, 0x0C) >> 2) & 3
    ch2 = (_block_max(tiles, x, y, size, 12, 0x30) >> 4) & 3
    return ch0 + ch1 + ch2


def paint_plus13_buildings(tiles: bytearray, y0: int, n: int) -> int:
    """FUN_0003fdd0 — charged 0xBE +13 0x04; markets +13 0x40."""
    painted = 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _off(x, y)
            hid = tiles[off]
            if hid == ID_RESERVOIR:
                charge = tiles[off + 10] & 3
                if charge in (1, 2, 3):
                    tile_or_radius(tiles, x, y, 3 + charge, 13, 0x04)
                    painted += 1
            elif 0xFC <= hid <= 0xFF:
                tile_or_radius(tiles, x, y, 2, 13, 0x40)
                painted += 1
            elif hid == 0xFA:
                paint_factory_emitter(tiles, x, y)
                painted += 1
    return painted


def paint_factory_emitter(tiles: bytearray, x: int, y: int) -> None:
    """0x3FDD0 factory arm + place 0x3043B: +13 0x80 / +14 0x10/0x20."""
    tile_or_radius(tiles, x, y, 4, 14, 0x20)
    tile_or_radius(tiles, x, y, 2, 14, 0x10)
    tile_or_radius(tiles, x, y, 1, 13, 0x80)


# FUN_0003fef7 / FUN_0003fdd0 radii (Chebyshev). Fountain is not a well.
WELL_SPLASH_R = 2
FOUNTAIN_SPLASH_R = 6
RIVER_SPLASH_R = 3


def reservoir_ring_radius(charge: int) -> int:
    """Charged 0xBE → +13 0x04. Charge 1/2/3 → r=4/5/6."""
    if charge not in (1, 2, 3):
        return 0
    return 3 + charge


def fountain_in_reservoir_ring(tiles: bytearray, x: int, y: int) -> bool:
    """EXE: fountain emits only when its tile has +13&4 (charged 0xBE ring).

    Also walks charged reservoirs so place-time works before phase 0x56
    has rewritten +13 (wipe 0x51 clears the ring until then).
    """
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return False
    if tiles[_off(x, y) + 13] & 0x04:
        return True
    for ty in range(MAP_H):
        for tx in range(MAP_W):
            off = _off(tx, ty)
            if tiles[off] != ID_RESERVOIR:
                continue
            radius = reservoir_ring_radius(tiles[off + 10] & 3)
            if radius and max(abs(tx - x), abs(ty - y)) <= radius:
                return True
    return False


def paint_water_emitter(tiles: bytearray, x: int, y: int) -> int:
    """Place-time +13 so Water overlay shows the blob before 0x56 / 0x6E.

    Well: +13 0x02 r=2 (no pipe). Fountain: +13 0x01 r=6 only if charged.
    Charged reservoir: +13 0x04 r=4/5/6 and small +13 0x01 r=charge.
    """
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    off = _off(x, y)
    hid = tiles[off]
    painted = 0
    if ID_WELL_LO <= hid <= ID_WELL_HI:
        tile_or_radius(tiles, x, y, WELL_SPLASH_R, 13, 0x02)
        painted += 1
    elif ID_FOUNTAIN_LO <= hid <= ID_FOUNTAIN_HI:
        if fountain_in_reservoir_ring(tiles, x, y):
            tile_or_radius(tiles, x, y, FOUNTAIN_SPLASH_R, 13, 0x01)
            painted += 1
        sync_water_building_graphic(tiles, x, y)
    elif hid == ID_RESERVOIR:
        charge = tiles[off + 10] & 3
        ring_r = reservoir_ring_radius(charge)
        if ring_r:
            tile_or_radius(tiles, x, y, ring_r, 13, 0x04)
            tile_or_radius(tiles, x, y, charge, 13, 0x01)
            painted += 1
    return painted


def paint_plus13_water(
    tiles: bytearray, y0: int, n: int, *, water_staffed: bool = True
) -> int:
    """FUN_0003fef7 — river/well/reservoir-small/fountain rings onto +13.

    Fountain/bath splash is skipped when water labor is understaffed
    (0x45069: water_pct ≤ 10 → [0x102724]=0).
    """
    painted = 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _off(x, y)
            hid = tiles[off]
            if ID_RIVER_LO <= hid <= ID_RIVER_HI:
                tile_or_radius(tiles, x, y, RIVER_SPLASH_R, 13, 0x02)
                painted += 1
            elif ID_WELL_LO <= hid <= ID_WELL_HI:
                tile_or_radius(tiles, x, y, WELL_SPLASH_R, 13, 0x02)
                painted += 1
            elif hid == ID_RESERVOIR:
                charge = tiles[off + 10] & 3
                if charge in (1, 2, 3):
                    tile_or_radius(tiles, x, y, charge, 13, 0x01)
                    painted += 1
            elif ID_FOUNTAIN_LO <= hid <= ID_FOUNTAIN_HI:
                # EXE: +13&4 → 0x01 r=6. Dry fountain (no reservoir ring) is silent.
                if water_staffed and tiles[off + 13] & 0x04:
                    tile_or_radius(tiles, x, y, FOUNTAIN_SPLASH_R, 13, 0x01)
                    painted += 1
                sync_water_building_graphic(tiles, x, y, water_staffed=water_staffed)
            elif ID_BATH_LO <= hid <= ID_BATH_HI:
                if water_staffed:
                    painted += paint_baths_emitter(tiles, x, y)
                sync_water_building_graphic(tiles, x, y, water_staffed=water_staffed)
    return painted


def bath_splash_radius(hid: int) -> int:
    """FUN_0003fef7: ECX = id − 0xDA → 0xDF…0xE2 = r=5/6/7/8, extra=1."""
    if not (ID_BATH_LO <= hid <= ID_BATH_HI):
        return 0
    return hid - 0xDA


def baths_in_reservoir_ring(tiles: bytearray, x: int, y: int) -> bool:
    """EXE FUN_0006dba2 +13 0x04 over the 2×2 baths footprint."""
    if _block_and(tiles, x, y, 2, 13, 0x04):
        return True
    for dy in range(2):
        for dx in range(2):
            if fountain_in_reservoir_ring(tiles, x + dx, y + dy):
                return True
    return False


def paint_baths_emitter(tiles: bytearray, x: int, y: int) -> int:
    """Place-time / 0x6E +13 0x08. Needs a charged reservoir ring."""
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    off = _off(x, y)
    if tiles[off + 5] & 0xF:
        return 0
    hid = tiles[off]
    radius = bath_splash_radius(hid)
    if not radius:
        return 0
    if not baths_in_reservoir_ring(tiles, x, y):
        return 0
    tile_or_radius(
        tiles, x, y, radius, 13, BATH_SPLASH_BIT, extra=BATH_SPLASH_EXTRA
    )
    return 1


def fountain_dry_variant(hid: int) -> int:
    return FOUNTAIN_DRY_VAR.get(hid, 0)


def bath_variant_pieces(hid: int, wet: bool) -> tuple[int, int, int, int]:
    """2×2 +4 for FUN_0006a368. stage = id − 0xDF."""
    if not (ID_BATH_LO <= hid <= ID_BATH_HI):
        return (0, 0, 0, 0)
    base = (BATH_WET_BASE if wet else BATH_DRY_BASE) + (hid - ID_BATH_LO) * 4
    return tuple(base + d for d in BATH_PIECE_DELTA)


def apply_fountain_wet_graphic(tiles: bytearray, x: int, y: int, wet: bool) -> None:
    """Write +4 dry LUT or LUT+1. EXE 0x4005b / 0x40070."""
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return
    off = _off(x, y)
    dry = fountain_dry_variant(tiles[off])
    if not dry:
        return
    tiles[off + 4] = (dry + 1) if wet else dry


def apply_baths_wet_graphic(tiles: bytearray, x: int, y: int, wet: bool) -> None:
    """Rewrite the 2×2 +4 set. Origins only (+5 lo == 0)."""
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return
    off = _off(x, y)
    if tiles[off + 5] & 0xF:
        return
    hid = tiles[off]
    pieces = bath_variant_pieces(hid, wet)
    i = 0
    for dy in range(2):
        for dx in range(2):
            nx, ny = x + dx, y + dy
            if _in_map(nx, ny) and ID_BATH_LO <= tiles[_off(nx, ny)] <= ID_BATH_HI:
                tiles[_off(nx, ny) + 4] = pieces[i]
            i += 1


def sync_water_building_graphic(
    tiles: bytearray, x: int, y: int, *, water_staffed: bool = True
) -> bool:
    """Wet blit iff charged reservoir ring and water labor (same +13&4 as overlay)."""
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return False
    hid = tiles[_off(x, y)]
    if ID_FOUNTAIN_LO <= hid <= ID_FOUNTAIN_HI:
        wet = bool(water_staffed and fountain_in_reservoir_ring(tiles, x, y))
        apply_fountain_wet_graphic(tiles, x, y, wet)
        return wet
    if ID_BATH_LO <= hid <= ID_BATH_HI:
        wet = bool(water_staffed and baths_in_reservoir_ring(tiles, x, y))
        apply_baths_wet_graphic(tiles, x, y, wet)
        return wet
    return False


def is_fortification_id(tid: int) -> bool:
    return tid in FORTIFICATION_IDS


def tile_inside_walls(tiles: bytearray, x: int, y: int) -> bool:
    """True when wall/gate/tower blocks every path from the map edge.

    EXE Query External is signed +17>=16 (0x6434a). +17 flood 0x430da seeds
    every +1&0x1E tile (wall 0x02, tower 0x04, river 0x10, bank 0x08). The
    host isotropic stand-in then paints a City Only river map to >=16, so
    a prefect alone would always read Maximum. Enclosure is the External
    half (walls); Internal stays +10&0x30.
    """
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return False
    if is_fortification_id(tiles[_off(x, y)]):
        return False
    seen = bytearray(MAP_W * MAP_H)
    stack = []
    for i in range(MAP_W):
        stack.append((i, 0))
        stack.append((i, MAP_H - 1))
    for j in range(1, MAP_H - 1):
        stack.append((0, j))
        stack.append((MAP_W - 1, j))
    while stack:
        cx, cy = stack.pop()
        if not _in_map(cx, cy):
            continue
        idx = cy * MAP_W + cx
        if seen[idx]:
            continue
        if is_fortification_id(tiles[_off(cx, cy)]):
            continue
        seen[idx] = 1
        if cx == x and cy == y:
            return False
        stack.append((cx - 1, cy))
        stack.append((cx + 1, cy))
        stack.append((cx, cy - 1))
        stack.append((cx, cy + 1))
    return True


def paint_security_emitter(tiles: bytearray, x: int, y: int) -> int:
    """Place-time / 0x5E prefecture + barracks onto +14 and +10&0x30.

    +17 is the road flood (0xA2), not a building splash.
    """
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    off = _off(x, y)
    if tiles[off + 5] & 0xF:
        return 0
    hid = tiles[off]
    if hid == ID_PREFECTURE:
        tile_or_radius(tiles, x, y, PREFECTURE_SPLASH_R, 14, 0x02)
        tile_or_radius(tiles, x, y, PREFECTURE_SPLASH_R, 10, SECURITY_COV_BITS)
        return 1
    if hid == ID_BARRACKS:
        tile_or_radius(tiles, x, y, BARRACKS_SPLASH_R, 14, 0x01)
        tile_or_radius(tiles, x, y, BARRACKS_SPLASH_R, 10, SECURITY_COV_BITS)
        return 1
    return 0


def civic_stamp_origin(
    tiles: bytearray, x: int, y: int, size: int = CIVIC_COVER_SIZE
) -> tuple[int, int]:
    """FUN_00069483: +5 lo-nibble → NW origin of the N×N stamp."""
    if not _in_map(x, y) or size <= 1:
        return x, y
    piece = tiles[_off(x, y) + 5] & 0xF
    return x - (piece % size), y - (piece // size)


def civic_edge_access(
    tiles: bytearray, x: int, y: int, size: int = CIVIC_COVER_SIZE
) -> tuple[bool, bool]:
    """FUN_00044deb (ECX=0): 3×3 rim pad +1&0x20, forum on that pad +10&0x0C.

    Hospital 0xFB / Library 0xF5 only increment the working count when a
    neighbour road/plaza (FLAG_PAD) also has tax/forum bits.
    """
    has_road = False
    has_forum = False
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return False, False

    def _look(nx: int, ny: int) -> None:
        nonlocal has_road, has_forum
        if not _in_map(nx, ny):
            return
        off = _off(nx, ny)
        if not (tiles[off + 1] & FLAG_PAD):
            return
        has_road = True
        if tiles[off + 10] & FORUM_ACCESS_BITS:
            has_forum = True

    if y > 0:
        for i in range(size):
            _look(x + i, y - 1)
    if y + size < MAP_H:
        for i in range(size):
            _look(x + i, y + size)
    if x > 0:
        for i in range(size):
            _look(x - 1, y + i)
    if x + size < MAP_W:
        for i in range(size):
            _look(x + size, y + i)
    return has_road, has_forum


def civic_working(tiles: bytearray, x: int, y: int, size: int = CIVIC_COVER_SIZE) -> bool:
    """Road access AND forum access on the same pad neighbour."""
    _road, forum = civic_edge_access(tiles, x, y, size)
    return forum


def _count_civic_origins(
    tiles: bytearray, tid: int, *, working: bool = True
) -> int:
    n = 0
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off] != tid:
                continue
            if tiles[off + 5] & 0xF:
                continue
            if working and not civic_working(tiles, x, y):
                continue
            n += 1
    return n


def count_hospitals(tiles: bytearray, *, working: bool = True) -> int:
    """0xFB origins. FUN_00044d26: raw [0x102868], working [0x10285c] after 0x44deb."""
    return _count_civic_origins(tiles, ID_HOSPITAL, working=working)


def count_libraries(tiles: bytearray, *, working: bool = True) -> int:
    """0xF5 origins. FUN_00044d54: raw [0x102834], working [0x10286c] after 0x44deb."""
    return _count_civic_origins(tiles, ID_LIBRARY, working=working)


def _cover_percent(n: int, pop: int, unit: int) -> int:
    """FUN_00045398 / 0x453e5 + 0x28219: 0 if n<=0; 100 if pop<100; else n*unit*100/pop."""
    if n <= 0:
        return 0
    if pop < HOSPITAL_COVER_POP_FULL:
        return 100
    cover = (n * unit * 100) // pop
    return 100 if cover > 100 else cover


def hospital_cover_percent(tiles: bytearray, *, population: int | None = None) -> int:
    """City-wide hospital cover 0…100. No per-tile splash (0x4034b / 0x3fef7).

    Working 0xFB only (road+forum rim). 0x45398: n=0 → 0; pop<100 → 100;
    else 0x28219(n*1000, pop) = n*1000*100/pop.
    """
    n = count_hospitals(tiles, working=True)
    pop = recount_population(tiles) if population is None else population
    return _cover_percent(n, pop, HOSPITAL_COVER_UNIT)


def library_cover_percent(tiles: bytearray, *, population: int | None = None) -> int:
    """City-wide library cover 0…100. 0xF5 has no tile_or_radius in 0x4034b.

    Working 0xF5 only (same 0x44deb gate). 0x453e5: n=0 → 0; pop<100 → 100;
    else 0x28219(n*1200, pop) = n*1200*100/pop.
    """
    n = count_libraries(tiles, working=True)
    pop = recount_population(tiles) if population is None else population
    return _cover_percent(n, pop, LIBRARY_COVER_UNIT)


def tile_maxmerge_plus12(
    tiles: bytearray,
    x: int,
    y: int,
    radius: int,
    value: int,
    mask: int,
    keep: int,
    extra: int = 0,
) -> None:
    """FUN_0006ce67 — if (tile[+12] & mask) < value: keep | value."""
    if not tiles or radius < 0:
        return
    span = radius + max(0, extra)
    for ny in range(max(0, y - radius), min(MAP_H, y + span + 1)):
        for nx in range(max(0, x - radius), min(MAP_W, x + span + 1)):
            off = _off(nx, ny) + 12
            if (tiles[off] & mask) < value:
                tiles[off] = (tiles[off] & keep) | value


def paint_education_emitter(tiles: bytearray, x: int, y: int) -> int:
    """Place-time +13 so Query / Education overlay work before 0x66.

    EXE FUN_0004034b: 0xF3 → +13 0x10 r=6 extra=1; 0xF4 → +13 0x20 r=8 extra=2.
    0xF5 Library is not in that painter.
    """
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    off = _off(x, y)
    if tiles[off + 5] & 0xF:
        return 0
    hid = tiles[off]
    if hid == ID_GRAMMATICUS:
        tile_or_radius(
            tiles, x, y, GRAMMATICUS_SPLASH_R, 13, EDU_GRAMMATICUS_BIT,
            extra=GRAMMATICUS_SPLASH_EXTRA,
        )
        return 1
    if hid == ID_RHETOR:
        tile_or_radius(
            tiles, x, y, RHETOR_SPLASH_R, 13, EDU_RHETOR_BIT,
            extra=RHETOR_SPLASH_EXTRA,
        )
        return 1
    return 0


def paint_entertainment_emitter(tiles: bytearray, x: int, y: int) -> int:
    """Place-time +12 so Query / Entert'ment overlay work before 0x66.

    EXE FUN_0004034b → FUN_0006ce67 (EAX extra, ECX radius, origins only).
    """
    if not _in_map(x, y) or len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    off = _off(x, y)
    if tiles[off + 5] & 0xF:
        return 0
    hid = tiles[off]
    if hid == ID_THEATER:
        tile_maxmerge_plus12(tiles, x, y, 9, 1, 0x03, 0xFC, extra=1)
        tile_maxmerge_plus12(tiles, x, y, 7, 2, 0x03, 0xFC, extra=1)
        tile_maxmerge_plus12(tiles, x, y, 5, 3, 0x03, 0xFC, extra=1)
        return 1
    if hid == ID_ODEUM:
        tile_maxmerge_plus12(tiles, x, y, 11, 1, 0x03, 0xFC, extra=1)
        tile_maxmerge_plus12(tiles, x, y, 9, 2, 0x03, 0xFC, extra=1)
        tile_maxmerge_plus12(tiles, x, y, 7, 3, 0x03, 0xFC, extra=1)
        return 1
    if hid == ID_ARENA:
        tile_maxmerge_plus12(tiles, x, y, 9, 4, 0x0C, 0xF3, extra=2)
        tile_maxmerge_plus12(tiles, x, y, 7, 8, 0x0C, 0xF3, extra=2)
        tile_maxmerge_plus12(tiles, x, y, 5, 0x0C, 0x0C, 0xF3, extra=2)
        return 1
    if hid == ID_COLISEUM:
        tile_maxmerge_plus12(tiles, x, y, 11, 4, 0x0C, 0xF3, extra=2)
        tile_maxmerge_plus12(tiles, x, y, 9, 8, 0x0C, 0xF3, extra=2)
        tile_maxmerge_plus12(tiles, x, y, 7, 0x0C, 0x0C, 0xF3, extra=2)
        return 1
    if ID_CIRCUS_LO <= hid <= ID_CIRCUS_HI:
        tile_maxmerge_plus12(tiles, x, y, 10, 0x10, 0x30, 0xCF, extra=2)
        tile_maxmerge_plus12(tiles, x, y, 8, 0x20, 0x30, 0xCF, extra=2)
        tile_maxmerge_plus12(tiles, x, y, 6, 0x30, 0x30, 0xCF, extra=2)
        return 1
    if ID_CMAX_LO <= hid <= ID_CMAX_HI:
        tile_maxmerge_plus12(tiles, x, y, 12, 0x10, 0x30, 0xCF, extra=3)
        tile_maxmerge_plus12(tiles, x, y, 10, 0x20, 0x30, 0xCF, extra=3)
        tile_maxmerge_plus12(tiles, x, y, 8, 0x30, 0x30, 0xCF, extra=3)
        return 1
    return 0


def paint_plus12_amenities(tiles: bytearray, y0: int, n: int) -> int:
    """FUN_0004034b — +12 entertainment rings and +13 education splash."""
    painted = 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            painted += paint_education_emitter(tiles, x, y)
            painted += paint_entertainment_emitter(tiles, x, y)
    return painted


def paint_plus14_security(tiles: bytearray, y0: int, n: int) -> int:
    """FUN_000401e7 — prefecture / barracks / tower / gate onto +14 and +10."""
    painted = 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off + 5] & 0xF:
                continue
            hid = tiles[off]
            sec = paint_security_emitter(tiles, x, y)
            if sec:
                painted += sec
            elif hid == 0xC0:
                tile_or_radius(tiles, x, y, 2, 14, 0x04)
                painted += 1
            elif 0xBF <= hid <= 0xCA:
                tile_or_radius(tiles, x, y, 2, 14, 0x08)
                painted += 1
            elif 0xAE <= hid <= 0xB9:
                tile_or_radius(tiles, x, y, 3, 10, 0x0C)
                painted += 1
            elif 0xFC <= hid <= 0xFF:
                tile_or_radius(tiles, x, y, 2, 10, 0xC0)
                painted += 1
    return painted


def paint_land_value(tiles: bytearray, y0: int, n: int) -> int:
    """FUN_00040695 — radiate signed +15 from buildings / gardens / fountain."""
    painted = 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _off(x, y)
            hid = tiles[off]
            flags = tiles[off + 1]
            if flags & 0x20:
                if flags & 4:
                    add_land_value(tiles, x, y, 1, 1, 2)
                    painted += 1
                elif flags & 0x10:
                    add_land_value(tiles, x, y, 2, 1, 1)
                    painted += 1
                elif hid == 0x5C:
                    add_land_value(tiles, x, y, 1, 1, 2)
                    painted += 1
                elif 0x58 <= hid <= 0x5B:
                    add_land_value(tiles, x, y, 1, 1, 1)
                    painted += 1
            elif flags & 1:
                if tiles[off + 5] & 0xF:
                    continue
                if ID_HOUSING_LO <= hid <= ID_HOUSING_HI:
                    grade = hid - ID_HOUSING_LO
                    bonus, rad = _HOUSE_LV[grade]
                    add_land_value(
                        tiles,
                        x,
                        y,
                        HOUSE_SIZE[grade],
                        rad,
                        bonus,
                        skip_own=True,
                        skip_housing=True,
                    )
                    painted += 1
                elif ID_FOUNTAIN_LO <= hid <= ID_FOUNTAIN_HI:
                    add_land_value(tiles, x, y, 1, 2, 2)
                    painted += 1
                elif hid == ID_PREFECTURE:
                    add_land_value(tiles, x, y, 1, 2, 3)
                    painted += 1
                elif hid == ID_BARRACKS:
                    add_land_value(tiles, x, y, 3, 2, 3)
                    painted += 1
                elif ID_GARDEN_LO <= hid <= ID_GARDEN_HI:
                    add_land_value(tiles, x, y, 1, 2, 2)
                    painted += 1
                elif ID_PLAZA_LO <= hid <= ID_PLAZA_HI:
                    add_land_value(tiles, x, y, 1, 1, 4)
                    painted += 1
            elif flags & 0x18:
                tiles[off + 15] = 0
                painted += 1
    return painted


def _housing_service_cap(
    tiles: bytearray, x: int, y: int, size: int, population: int
) -> tuple[int, str]:
    """FUN_00040d08 housing ladder — first failing gate writes the even cap."""
    hosp = hospital_cover_percent(tiles, population=population)
    lib = library_cover_percent(tiles, population=population)
    if not _block_and(tiles, x, y, size, 13, 0x02) and not _block_and(
        tiles, x, y, size, 13, 0x01
    ):
        return 2, "no-water +13&0x01|0x02"
    if not _block_max(tiles, x, y, size, 10, 0x0C):
        return 6, "no-food +10&0x0C (stocked market trader)"
    if _block_and(tiles, x, y, size, 13, 0x80):
        return 10, "warehouse +13&0x80"
    if not _block_max(tiles, x, y, size, 10, 0xC0):
        return 12, "no-goods +10&0xC0 (market)"
    if not _block_and(tiles, x, y, size, 13, 0x01):
        return 14, "well-only; need fountain +13&0x01"
    if _block_and(tiles, x, y, size, 14, 0x10):
        return 16, "bad +14&0x10"
    if not _block_and(tiles, x, y, size, 13, 0x08):
        return 18, "no-baths +13&0x08"
    ent = entertainment_level_block(tiles, x, y, size)
    if ent == 0:
        return 20, "no-entertainment +12"
    if _block_and(tiles, x, y, size, 14, 0x01):
        return 24, "need more entertainment / security"
    road = i8(tiles[_off(x, y) + 17]) > 15
    sec = 1 if _block_max(tiles, x, y, size, 10, 0x30) else 0
    if road:
        sec += 1
    if sec == 0:
        return 24, "need more entertainment / security"
    if _block_and(tiles, x, y, size, 14, 0x20):
        return 26, "need more entertainment / security"
    if ent <= 1 or _block_and(tiles, x, y, size, 14, 0x08):
        return 26, "need more entertainment / security"
    if ent <= 2:
        return 28, "need more entertainment"
    if _block_and(tiles, x, y, size, 14, 0x04):
        return 30, "need more entertainment / pop"
    if population < 20:
        return 30, "need pop>=20"
    if hosp < 20:
        return 30, "need hospital cover>=20"
    if ent <= 3:
        return 32, "need more entertainment"
    if not _block_and(tiles, x, y, size, 13, 0x10):
        return 34, "need +13&0x10"
    if _block_and(tiles, x, y, size, 14, 0x02):
        return 34, "need more security"
    if population < 40:
        return 36, "need pop>=40"
    if hosp < 40:
        return 36, "need hospital cover>=40"
    if ent <= 4:
        return 38, "need more entertainment"
    if _block_and(tiles, x, y, size, 13, 0x40):
        return 40, "need +13&0x40"
    if sec <= 1:
        return 42, "need more security"
    if population < 60:
        return 44, "need pop>=60"
    if hosp < 60:
        return 44, "need hospital cover>=60"
    if ent <= 5:
        return 44, "need more entertainment"
    if not _block_and(tiles, x, y, size, 13, 0x20):
        return 46, "need +13&0x20"
    if lib < 20:
        return 46, "need library cover>=20"
    if population < 20:
        return 46, "need pop>=20"
    if ent <= 6:
        return 48, "need more entertainment"
    if population < 40:
        return 50, "need pop>=40"
    if lib < 40:
        return 50, "need library cover>=40"
    if population < 80:
        return 52, "need pop>=80"
    if hosp < 80:
        return 52, "need hospital cover>=80"
    if population < 60:
        return 54, "need pop>=60"
    if lib < 60:
        return 54, "need library cover>=60"
    if ent <= 7:
        return 56, "need more entertainment"
    if population < 100:
        return 58, "need pop>=100"
    if population < 80:
        return 58, "need pop>=80"
    if ent <= 8:
        return 60, "need more entertainment"
    if population < 100:
        return 62, "need pop>=100"
    return 64, "palace-cap"


def housing_cap_detail(
    tiles: bytearray, x: int, y: int, *, population: int = 0
) -> tuple[int, str]:
    """Service cap and first failing gate for a housing origin."""
    if not _in_map(x, y):
        return 0, "off-map"
    off = _off(x, y)
    hid = tiles[off]
    if hid < ID_HOUSING_LO or hid > ID_HOUSING_HI:
        return 0, "not-house"
    size = HOUSE_SIZE[hid - ID_HOUSING_LO]
    return _housing_service_cap(tiles, x, y, size, population)


def service_target_lv(acc: int, cap: int) -> int:
    """Evolve +15 from 40695 acc and the 40d08 service cap.

    EXE 0x41157 only clips down (if cap < acc: write cap). A watered City Only
    block then sits at acc=2 (fountain +2 vs hut stay 0…3) and never leaves
    the first hut. Host writes the service target through the house/insula
    rung (cap ≤ 20) so each month can step toward water/food/entertainment.
    Above 20, gardens/fountain acc still raise +15 and only clip to cap.
    """
    if cap <= 20:
        return cap
    if acc < 20:
        acc = 20
    if acc > cap:
        return cap
    return acc


def cap_housing_plus15(
    tiles: bytearray, y0: int, n: int, *, population: int = 0
) -> int:
    """FUN_00040d08 — write service-allowed +15 on housing origins."""
    written = 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _off(x, y)
            hid = tiles[off]
            if hid < ID_HOUSING_LO or hid > ID_HOUSING_HI:
                continue
            if tiles[off + 5] & 0xF:
                continue
            grade = hid - ID_HOUSING_LO
            size = HOUSE_SIZE[grade]
            cap, _gate = _housing_service_cap(tiles, x, y, size, population)
            cur = i8(tiles[off + 15])
            new = service_target_lv(cur, cap)
            if new != cur:
                tiles[off + 15] = new & 0xFF
                written += 1
    return written


def flood_plus17(tiles: bytearray, y0: int, n: int, direction: int) -> int:
    """FUN_000430da stand-in. +1&0x1E seeds 100; open tiles decay from neighbors.

    EXE walks four scan directions across 0xA2–0xC1. One isotropic fill is
    enough for housing's signed +17>15 road-access gate.
    """
    del direction, y0, n
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            tiles[off + 17] = 100 if tiles[off + 1] & 0x1E else 0
    changed = 1
    while changed:
        changed = 0
        for y in range(MAP_H):
            for x in range(MAP_W):
                off = _off(x, y)
                if tiles[off + 1] & 0x1E:
                    continue
                best = tiles[off + 17]
                for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
                    nx, ny = x + dx, y + dy
                    if not _in_map(nx, ny):
                        continue
                    n17 = tiles[_off(nx, ny) + 17]
                    if n17 > best:
                        best = n17
                if best > 1:
                    want = best - 1
                    if want > 100:
                        want = 100
                    if tiles[off + 17] < want:
                        tiles[off + 17] = want
                        changed += 1
    return 1
