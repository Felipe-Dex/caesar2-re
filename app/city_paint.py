"""City sim painters: +13 water, +15 land-value / service cap, +17 flood.

EXE: wipe 0x51–0x54, paint 0x3FDD0 / 0x3FEF7 / 0x40695 / 0x40D08 / 0x430DA.
Lane helpers match findings/ghidra_water.md and ghidra_tile.md.
"""

from __future__ import annotations

from app.city_map import MAP_H, MAP_W, ROW_STRIDE, TILE_STRIDE
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
ID_RIVER_LO, ID_RIVER_HI = 0x1E, 0x51


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
                tile_or_radius(tiles, x, y, 4, 14, 0x20)
                tile_or_radius(tiles, x, y, 2, 14, 0x10)
                tile_or_radius(tiles, x, y, 1, 13, 0x80)
                painted += 1
    return painted


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
    elif hid == ID_RESERVOIR:
        charge = tiles[off + 10] & 3
        ring_r = reservoir_ring_radius(charge)
        if ring_r:
            tile_or_radius(tiles, x, y, ring_r, 13, 0x04)
            tile_or_radius(tiles, x, y, charge, 13, 0x01)
            painted += 1
    return painted


def paint_plus13_water(tiles: bytearray, y0: int, n: int) -> int:
    """FUN_0003fef7 — river/well/reservoir-small/fountain rings onto +13."""
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
                if tiles[off + 13] & 0x04:
                    tile_or_radius(tiles, x, y, FOUNTAIN_SPLASH_R, 13, 0x01)
                    painted += 1
            elif ID_BATH_LO <= hid <= ID_BATH_HI:
                if (tiles[off + 5] & 0xF) == 0 and _block_and(
                    tiles, x, y, 2, 13, 0x04
                ):
                    tile_or_radius(tiles, x, y, 6, 13, 0x08, extra=1)
                    painted += 1
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
            if hid == ID_PREFECTURE:
                tile_or_radius(tiles, x, y, 2, 14, 0x02)
                tile_or_radius(tiles, x, y, 2, 10, 0x30)
                painted += 1
            elif hid == ID_BARRACKS:
                tile_or_radius(tiles, x, y, 3, 14, 0x01)
                tile_or_radius(tiles, x, y, 3, 10, 0x30)
                painted += 1
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
    if not _block_and(tiles, x, y, size, 13, 0x02) and not _block_and(
        tiles, x, y, size, 13, 0x01
    ):
        return 2, "no-water +13&0x01|0x02"
    if not _block_max(tiles, x, y, size, 10, 0x0C):
        return 6, "no-food +10&0x0C (market trader)"
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
    ch0 = _block_max(tiles, x, y, size, 12, 0x03)
    ch1 = (_block_max(tiles, x, y, size, 12, 0x0C) >> 2) & 3
    ch2 = (_block_max(tiles, x, y, size, 12, 0x30) >> 4) & 3
    ent = ch0 + ch1 + ch2
    if ent == 0:
        return 20, "no-entertainment +12 (City Only skip 0x66-0x6D)"
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
    if ent <= 3:
        return 32, "need more entertainment"
    if not _block_and(tiles, x, y, size, 13, 0x10):
        return 34, "need +13&0x10"
    if _block_and(tiles, x, y, size, 14, 0x02):
        return 34, "need more security"
    if population < 40:
        return 36, "need pop>=40"
    if ent <= 4:
        return 38, "need more entertainment"
    if _block_and(tiles, x, y, size, 13, 0x40):
        return 40, "need +13&0x40"
    if sec <= 1:
        return 42, "need more security"
    if population < 60:
        return 44, "need pop>=60"
    if ent <= 5:
        return 44, "need more entertainment"
    if not _block_and(tiles, x, y, size, 13, 0x20):
        return 46, "need +13&0x20"
    if population < 20:
        return 46, "need pop>=20"
    if ent <= 6:
        return 48, "need more entertainment"
    if population < 40:
        return 50, "need pop>=40"
    if population < 80:
        return 52, "need pop>=80"
    if population < 60:
        return 54, "need pop>=60"
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
