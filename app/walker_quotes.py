"""Walker Query quotes — C2.ENG [63]/[64]/[65]/[66] + picker 0x632A4.

findings/walker_quotes.md. Official slots (EngTable.skip), not EAX+1.
"""

from __future__ import annotations

from app.city_map import MAP_H, MAP_W, TILE_BYTES
from app.city_overlay import PlaceInfo
from app.walkers import Walker

# Official C2.ENG slots. EXE EAX = slot + 1.
ENG_QUOTE = 63
ENG_NAME = 64
ENG_ENEMY = 65
ENG_TITLE = 66

HOUSE_LO = 0x82
HOUSE_HI = 0xA1

_TITLE_FALLBACK = (
    "Forum Clerk",
    "Market Trader",
    "Enemy",
    "Soldier",
    "Vigile",
    "Worker",
    "Rioter",
)

_QUOTE_FALLBACK: dict[int, str] = {
    4: '"We hardly collect any tax from this district."',
    5: '"Many areas avoid paying their taxes."',
    6: '"Tax avoidance is a problem in the city."',
    7: '"There is no tax avoidance in the district, but our resources are stretched."',
    8: '"We have a good knowledge of this area, but it could be improved."',
    9: '"We have excellent records for this district."',
    10: '"There are too few people in this district to support our market."',
    11: '"We do a reasonable amount of trade with the people of this district."',
    12: '"We have enough customers from this district, but we need better access to a business."',
    13: '"Our market is very popular with the good people of this district."',
    14: '"AAARGH -- The only good Roman is a DEAD Roman!"',
    15: '"I can\'t talk now -- there\'s trouble in the city!"',
    16: '"We have lamentably little access to this part of this city."',
    17: '"We have too few patrols in this part of the city."',
    18: '"We have good patrols in this district. We feel we have the area secure."',
    19: '"I can\'t talk now -- the city is burning!"',
    20: '"This district will erupt in violence unless something is done about it."',
    21: '"There is much discontent in this district -- the area is a source of trouble."',
    22: '"Not everybody in this district is happy -- I hear the occasional rumors."',
    23: '"Most people in this district are well-behaved and content with their lot."',
    24: '"This is a very law-abiding and peaceful district."',
    25: '"There are too few workers in this district to maintain our industry."',
    26: '"We could do with more people in this district to help build up our industry."',
    27: '"Many of our workers live in this district, but they need better access to a market."',
    28: '"This is a popular location to live for many of our workers."',
    29: '"Well, wouldn\'t YOU riot if you had tax rates like we\'ve had these years?"',
    30: '"Boo!  Down with the Governor!"',
}


def _pct(a: int, b: int) -> int:
    if b <= 0:
        return 0
    return a * 100 // b


def scan_houses(
    tiles: bytes | bytearray, x: int, y: int, radius: int, mode: int
) -> tuple[int, int, int, int]:
    """FUN_0006dd50 0x6DD50. Returns houses, uncovered, coverage_sum, unrest_sum."""
    houses = 0
    uncovered = 0
    coverage_sum = 0
    unrest_sum = 0
    for ny in range(max(0, y - radius), min(MAP_H, y + radius + 1)):
        for nx in range(max(0, x - radius), min(MAP_W, x + radius + 1)):
            off = (ny * MAP_W + nx) * TILE_BYTES
            if off + 12 > len(tiles):
                continue
            tid = tiles[off]
            if not (HOUSE_LO <= tid <= HOUSE_HI):
                continue
            if tiles[off + 5] & 0x0F:
                continue
            houses += 1
            cov = tiles[off + 10]
            if mode == 0:
                if cov & 0x0C == 0:
                    uncovered += 1
                else:
                    coverage_sum += (cov & 0x0C) >> 2
            elif mode == 1:
                if cov & 0x30 == 0:
                    uncovered += 1
            else:
                unrest_sum += tiles[off + 11] & 0x0F
    return houses, uncovered, coverage_sum, unrest_sum


def quote_skip(
    walker: Walker,
    tiles: bytes | bytearray | None = None,
    *,
    tax_rate: int = 5,
) -> int:
    """Picker 0x632A4 — skip count from official [63]. Default 0x0F."""
    typ = walker.type
    if typ < 1 or typ > 7:
        return 0x0F
    blob = tiles if tiles is not None else b""
    if typ == 1:
        houses, uncovered, coverage_sum, _unrest = scan_houses(
            blob, walker.x, walker.y, 5, 0
        )
        if houses <= 0:
            return 4
        unp = _pct(uncovered, houses)
        if unp > 50:
            return 4
        if unp > 10:
            return 5
        if unp > 0:
            return 6
        ratio = _pct(coverage_sum, houses * 3)
        if ratio < 60:
            return 7
        if ratio < 90:
            return 8
        return 9
    if typ == 2:
        if walker.score_a < 1:
            return 10
        if walker.score_a < 8:
            return 11
        if walker.score_b < 1:
            return 12
        return 13
    if typ == 3:
        return 14
    if typ == 4:
        if walker.state == 6:
            return 15
        houses, uncovered, _cs, _un = scan_houses(blob, walker.x, walker.y, 5, 1)
        if houses <= 0:
            return 16
        unp = _pct(uncovered, houses)
        if unp > 50:
            return 16
        if unp > 10:
            return 17
        return 18
    if typ == 5:
        if walker.state == 6:
            return 15
        if walker.state == 9:
            return 19
        houses, _un, _cs, unrest = scan_houses(blob, walker.x, walker.y, 5, 2)
        if houses <= 0:
            return 24
        unp = _pct(unrest, houses << 4)
        if unp > 80:
            return 20
        if unp > 60:
            return 21
        if unp > 40:
            return 22
        if unp > 20:
            return 23
        return 24
    if typ == 6:
        if walker.score_a < 1:
            return 25
        if walker.score_a < 8:
            return 26
        if walker.score_b < 1:
            return 27
        return 28
    if tax_rate > 10:
        return 29
    return 30


def _eng_skip(eng, slot: int, n: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, n)
        if got:
            return got
    return fallback


def query_walker(
    walker: Walker,
    tiles: bytes | bytearray | None = None,
    eng=None,
    tax_rate: int = 5,
) -> PlaceInfo:
    """Name + title + C2.ENG quote. Same dialog as place Query."""
    skip = quote_skip(walker, tiles, tax_rate=tax_rate)
    title_i = max(0, min(6, walker.type - 1))
    if walker.type == 3:
        name = _eng_skip(eng, ENG_ENEMY, walker.name_id, "Gregor the Invader")
    else:
        name = _eng_skip(eng, ENG_NAME, walker.name_id, "Aemilius Calvus")
    title = _eng_skip(eng, ENG_TITLE, title_i, _TITLE_FALLBACK[title_i])
    if title and not title.startswith(" "):
        heading = f"{name} - {title.lstrip(' -')}"
    else:
        heading = f"{name}{title}"
    quote = _eng_skip(eng, ENG_QUOTE, skip, _QUOTE_FALLBACK.get(skip, ""))
    lines = [heading, quote]
    return PlaceInfo(
        walker.x,
        walker.y,
        heading,
        walker.type,
        0,
        tuple(lines),
    )


def selftest() -> list[str]:
    lines: list[str] = []
    raw = bytearray(0x3A)
    raw[0] = 1
    raw[2] = 1
    raw[4] = 10
    raw[5] = 10
    raw[0x10] = 3
    clerk = Walker.unpack(bytes(raw), slot=1)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    skip = quote_skip(clerk, tiles, tax_rate=5)
    ok = skip == 4
    lines.append(f"clerk quote no houses: {'ok' if ok else 'FAIL'} skip={skip}")

    off = (10 * MAP_W + 10) * TILE_BYTES
    tiles[off] = 0x82
    tiles[off + 10] = 0x0C
    skip = quote_skip(clerk, tiles, tax_rate=5)
    ok = skip == 9
    lines.append(f"clerk quote excellent: {'ok' if ok else 'FAIL'} skip={skip}")

    raw[2] = 4
    raw[0x10] = 7
    tiles[off + 10] = 0x30
    soldier = Walker.unpack(bytes(raw), slot=2)
    skip = quote_skip(soldier, tiles, tax_rate=5)
    ok = skip == 18
    lines.append(f"soldier quote secure: {'ok' if ok else 'FAIL'} skip={skip}")

    tiles[off + 10] = 0x0C
    info = query_walker(clerk, tiles, eng=None, tax_rate=5)
    ok = "Clerk" in info.name and "records" in "".join(info.lines).lower()
    lines.append(f"query_walker dialog: {'ok' if ok else 'FAIL'} {info.name}")
    return lines
