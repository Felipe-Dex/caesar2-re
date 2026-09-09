"""City overlay-filter (SavChunk 1 / [0x117A59]) and place-query stub.

EXE: table 0x98B34 (u16 id + u32 handler). Handlers 0x32AE3…0x32B49 write
the id then clear the 80×80 plane at 0xD7BFC (0x3E590). Phase 0xD3
``FUN_0003e5e3`` walks 80×80 and calls ``PTR_LAB_00099b3c[id]``.

Cancel (id 10, 0x329EF) zeros build-tool slots — it does **not** reset
the overlay. Geography (id 0) is “clear reports”. Popup from the INT_CITY
sprite-1 well via ``FUN_00032A90`` (call site 0x315B9; x < 0x25C).
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image, ImageDraw, ImageFont

from app.city_map import (
    ID_TERRAIN_MAX,
    MAP_H,
    MAP_W,
    MINIMAP_WELL,
    TILE_STRIDE,
    CityMap,
    tile_is_burning,
)
from app.city_paint import (
    BATH_SPLASH_BIT,
    HOUSE_OCCUPANCY,
    HOUSE_SIZE,
    ID_HOUSING_HI,
    ID_HOUSING_LO,
    ID_HOSPITAL,
    ID_LIBRARY,
    SECURITY_COV_BITS,
    civic_edge_access,
    civic_stamp_origin,
    entertainment_level,
    entertainment_level_block,
    factory_type_name,
    hospital_cover_percent,
    library_cover_percent,
    tile_inside_walls,
)

OVERLAY_GEOGRAPHY = 0
OVERLAY_LAND_VALUE = 1
OVERLAY_WATER = 2
OVERLAY_SECURITY = 3
OVERLAY_UNREST = 4
OVERLAY_TAX = 5
OVERLAY_ENTERTAINMENT = 6
OVERLAY_EDUCATION = 7
OVERLAY_ILLNESS = 8
OVERLAY_MARKETS = 9
OVERLAY_CANCEL = 10

# C2.ENG official slot 52 (HUD EAX=0x35) + skip. Help strings skip 12+.
OVERLAY_NAMES: tuple[str, ...] = (
    "Geography",
    "Land Value",
    "Water",
    "Security",
    "Unrest",
    "Tax Coverage",
    "Entert'ment",
    "Education",
    "Illness",
    "Markets",
    "Cancel",
)

OVERLAY_HELP: tuple[str, ...] = (
    "Clears other map reports to show the city in detail.",
    "Shows property values across the city.",
    "Shows areas with access to water sources.",
    "Shows levels of security across the city.",
    "Shows unrest nibble on houses.",
    "Shows tax-collector coverage (+10 bits 0x0C).",
    "Shows entertainment coverage (+12).",
    "Shows education splash (+13 0x10/0x20).",
    "Shows illness bits on houses (+11 0x30).",
    "Shows market / factory walker coverage (+10 0xC0).",
    "Close this list (also cancels the build tool).",
)

# city_map_draw 0x36169: these set [0x117AC4]=1 (iso housing remap to
# colour 7). Geography is in the EXE set but means “no report” — host
# iso wash skips id 0. Land Value / Unrest / Illness still wash.
ISO_TINT_OVERLAYS = frozenset(
    {OVERLAY_GEOGRAPHY, OVERLAY_LAND_VALUE, OVERLAY_UNREST, OVERLAY_ILLNESS}
)

# EXE 0x3E6BA never writes a dry colour — plane 0 keeps dimmed geography.
# Do not invent a full-map red (old host 0xFE). Coverage is +13 rings only.
_ISO_WASH_ALPHA = 120

# CITY1.256 indices written to 0xD7BFC. Runtime load preferred; this is
# the measured fallback so the host still paints without the file in git.
_PAL_FALLBACK: dict[int, tuple[int, int, int]] = {
    0x76: (105, 142, 113),
    0x77: (56, 142, 121),
    0x78: (56, 121, 105),
    0x79: (48, 105, 89),
    0x7A: (40, 89, 81),
    0x7B: (73, 97, 105),
    0x7C: (81, 113, 121),
    0x7D: (89, 134, 134),
    0x7E: (48, 73, 89),
    0x7F: (73, 81, 97),
    0x80: (73, 89, 121),
    0x81: (65, 73, 105),
    0x82: (48, 56, 81),
    0x83: (32, 48, 89),
    0x84: (24, 40, 81),
    0x85: (65, 24, 73),
    0x86: (81, 24, 89),
    0x87: (97, 32, 105),
    0x88: (113, 56, 97),
    0x89: (121, 73, 113),
    0x8A: (142, 97, 113),
    0x8B: (182, 134, 134),
    0x8C: (142, 121, 113),
    0x8D: (142, 121, 97),
    0x90: (121, 105, 89),
    0x91: (105, 97, 81),
    0x92: (89, 89, 73),
    0x93: (89, 81, 73),
    0x94: (158, 223, 121),
    0x95: (81, 113, 81),
    0x96: (150, 142, 97),
    0x97: (150, 142, 113),
}

_overlay_rgb: dict[int, tuple[int, int, int]] = dict(_PAL_FALLBACK)

# INT_CITY sprite 1 — overlay name well. Click x<0x25C opens 0x32A90.
OVERLAY_WELL = (478, 24, 162, 24)
OVERLAY_SPLIT_X = 0x25C  # 604 — 4-color / ? cluster on the right

_FLYOUT_W = 130
_FLYOUT_ITEM_H = 14
_DLG_X, _DLG_Y = 16, 40
_DLG_W, _DLG_H = 420, 280
_DLG_LINE = 52
_DLG_OK_W, _DLG_OK_H = 56, 18
_DLG_OK_PAD = 8


def overlay_name(overlay_id: int, eng=None) -> str:
    if eng is not None:
        got = eng.skip(52, overlay_id)
        if got:
            return got
    if 0 <= overlay_id < len(OVERLAY_NAMES):
        return OVERLAY_NAMES[overlay_id]
    return f"overlay {overlay_id}"


def overlay_help(overlay_id: int, eng=None) -> str:
    if eng is not None and 0 <= overlay_id <= 9:
        got = eng.skip(52, 12 + overlay_id)
        if got:
            return got
    if 0 <= overlay_id < len(OVERLAY_HELP):
        return OVERLAY_HELP[overlay_id]
    return ""


def load_overlay_palette(game) -> None:
    """Fill RGB from CITY1.256 when the install is present."""
    global _overlay_rgb
    try:
        from pathlib import Path

        from app.config import find_file
        from tools import decode_pl8

        path = find_file(Path(game), "CITY1.256")
        if path is None:
            return
        pal = decode_pl8.load_palette(path, verbose=False)
        filled = dict(_PAL_FALLBACK)
        for i in range(0x76, 0x98):
            if i < len(pal):
                filled[i] = tuple(pal[i][:3])
        _overlay_rgb = filled
    except (OSError, ValueError, ImportError, FileNotFoundError):
        _overlay_rgb = dict(_PAL_FALLBACK)


def palette_rgb(index: int) -> tuple[int, int, int]:
    if index <= 0:
        return (0, 0, 0)
    return _overlay_rgb.get(index, (index, index // 2, 40))


def i8(b: int) -> int:
    return b - 256 if b >= 128 else b


def overlay_pixel(tiles: bytearray | bytes, off: int, overlay_id: int) -> int:
    """One 0xD7BFC byte. Painters at 0x3E656…0x3EA8E."""
    if overlay_id <= 0 or overlay_id > 9:
        return 0
    tid = tiles[off]
    flags = tiles[off + 1]
    if overlay_id == OVERLAY_LAND_VALUE:
        return _paint_land_value(tiles[off + 15])
    if overlay_id == OVERLAY_WATER:
        return _paint_water(tid, flags, tiles[off + 13])
    if overlay_id == OVERLAY_SECURITY:
        return _paint_security(tid, flags, tiles[off + 10], tiles[off + 17])
    if overlay_id == OVERLAY_UNREST:
        return _paint_unrest(tiles[off + 11])
    if overlay_id == OVERLAY_TAX:
        return _paint_tax(tid, tiles[off + 10])
    if overlay_id == OVERLAY_ENTERTAINMENT:
        return _paint_entertainment(tid, tiles[off + 12])
    if overlay_id == OVERLAY_EDUCATION:
        return _paint_education(tid, tiles[off + 13])
    if overlay_id == OVERLAY_ILLNESS:
        return _paint_illness(tiles[off + 11])
    if overlay_id == OVERLAY_MARKETS:
        return _paint_markets(tid, tiles[off + 10])
    return 0


def _paint_land_value(lv_byte: int) -> int:
    # 0x3E666: clamp signed +15 to 0…64; 0 → plane 0; else (lv/8)*3 + 0x7E.
    lv = i8(lv_byte)
    if lv < 0:
        lv = 0
    if lv >= 0x40:
        lv = 0x40
    if lv <= 0:
        return 0
    return (lv >> 3) * 3 + 0x7E


def _is_pipe_building(tid: int) -> bool:
    return tid == 0xBE or (0xCB <= tid <= 0xD6)


def _paint_water(tid: int, flags: int, splash: int) -> int:
    # 0x3E6BA: pipe tile +1&0xC0 or Well 0xD7–0xDA → 0x96.
    # Fountain 0xDB–0xDE / Baths 0xDF–0xE2: 0x96 only with +13&4 so the
    # tan footprint matches the wet +4 blit (FUN_0003fef7). Dry stays
    # plane 0. +13&3 / +13&4 on other tiles still 0x84 / 0x8D / 0x87.
    if 0xD7 <= tid <= 0xDA:
        return 0x96
    ring = splash & 4
    if 0xDB <= tid <= 0xE2 and ring:
        return 0x96
    if _is_pipe_building(tid) and (flags & 0xC0):
        return 0x96
    charge = splash & 3
    if charge and ring:
        return 0x87
    if charge:
        return 0x84
    if ring:
        return 0x8D
    if _is_pipe_building(tid):
        return 0x96
    if (flags & 0x10) or tid < 8 or (0x1E <= tid <= 0x51):
        return 0x84
    return 0


def _is_security_road(tid: int) -> bool:
    """Pavement the overlay should mark — not river 0x1E–0x51."""
    if 0x52 <= tid <= 0x5C:
        return True
    if 0x4E <= tid <= 0x51:
        return True
    return 0x7C <= tid <= 0x7E


def _paint_security(tid: int, _flags: int, cov10: int, flood17: int) -> int:
    # 0x3E7DB. Score = (signed +17>=16) + (+10&0x30).
    # EXE also writes 0x96 for flags&6, river 0x1E–0x51, and both 0xE3/0xE4
    # — one khaki on the host iso/minimap. Split the two buildings (CITY1.256
    # 0x96 tan vs 0x8B salmon), keep the 0x8D/0x90/0x93 coverage ramp, and
    # leave river / open land on plane 0 (dimmed geography).
    if tid == 0xE3:
        return 0x96
    if tid == 0xE4:
        return 0x8B
    score = 0
    if i8(flood17) >= 0x10:
        score = 1
    if cov10 & 0x30:
        score += 1
    if score == 0:
        return 0
    if score == 2:
        return 0x8D
    if cov10 & 0x30:
        return 0x93
    if score == 1 and _is_security_road(tid):
        return 0x90
    return 0


def _paint_unrest(grade11: int) -> int:
    # 0x3EA8E: +11 lo-nibble (Unrest / riot). 0 empty; ≥11 / ≥5 / else.
    nibble = grade11 & 0x0F
    if nibble == 0:
        return 0
    if nibble >= 0x0B:
        return 0x77
    if nibble >= 5:
        return 0x78
    return 0x79


def _paint_tax(tid: int, cov10: int) -> int:
    # 0x3E757: forums 0xAE–0xB9 → 0x96; +10&0x0C strength.
    if 0xAE <= tid <= 0xB9:
        return 0x96
    bits = cov10 & 0x0C
    if bits == 0:
        return 0
    if bits == 4:
        return 0x93
    if bits == 8:
        return 0x90
    return 0x8D


def _paint_entertainment(tid: int, amenity12: int) -> int:
    # 0x3E983: venues 0xE5–0xF0 → 0x96; sum of three 2-bit channels.
    if 0xE5 <= tid <= 0xF0:
        return 0x96
    total = entertainment_level(amenity12)
    if total == 0:
        return 0
    return (total - 1) * 3 + 0x7E


def _paint_education(tid: int, splash13: int) -> int:
    # 0x3E8FA: schools 0xF3–0xF5 → 0x96; +13 0x10 Grammaticus / 0x20 Rhetor.
    if 0xF3 <= tid <= 0xF5:
        return 0x96
    bit10 = splash13 & 0x10
    bit20 = splash13 & 0x20
    if bit10 and bit20:
        return 0x87
    if bit10:
        return 0x8D
    if bit20:
        return 0x84
    return 0


def _paint_illness(grade11: int) -> int:
    # 0x3E8A2: +11 bits 4–5 (evolve-row).
    bits = grade11 & 0x30
    if bits == 0:
        return 0
    if bits == 0x10:
        return 0x79
    if bits == 0x20:
        return 0x78
    return 0x77


def _paint_markets(tid: int, cov10: int) -> int:
    # 0x3EA03: markets 0xFC–0xFF / factory 0xFA → 0x96; +10&0xC0 strength.
    if 0xFC <= tid <= 0xFF or tid == 0xFA:
        return 0x96
    bits = cov10 & 0xC0
    if bits == 0:
        return 0
    if bits == 0x40:
        return 0x93
    if bits == 0x80:
        return 0x90
    return 0x8D


def apply_overlay_colors(
    pixels: list[tuple[int, int, int]],
    tiles: bytearray | bytes,
    overlay_id: int,
) -> list[tuple[int, int, int]]:
    """Replace geography pixels where the EXE plane byte is nonzero."""
    if overlay_id <= 0:
        return pixels
    out: list[tuple[int, int, int]] = []
    for i, base in enumerate(pixels):
        off = i * TILE_STRIDE
        idx = overlay_pixel(tiles, off, overlay_id)
        if idx:
            out.append(palette_rgb(idx))
        else:
            out.append(((base[0] * 5) // 8, (base[1] * 5) // 8, (base[2] * 5) // 8))
    return out


def overlay_iso_wash(
    view: Image.Image,
    tiles: bytearray | bytes,
    overlay_id: int,
    zoom: int,
    cam_x: int,
    cam_y: int,
    canvas_w: int,
    canvas_h: int,
    *,
    view_w: int | None = None,
    view_h: int | None = None,
    facing: int = 0,
) -> Image.Image:
    """Translucent iso diamonds from the 0xD7BFC plane (post-crop, not cached).

    Geography (id 0) is a no-op. Other modes use ``overlay_pixel`` — same
    CITY1.256 indices as the minimap. Does not rewrite the dirty-iso canvas.
    """
    if overlay_id <= 0 or overlay_id > 9:
        return view
    from app.city_map import MAP_H, MAP_W, iso_tile_size, tile_iso_xy, view_tiles_for_camera
    from app.place import canvas_to_view

    vw = view_w if view_w is not None else view.size[0]
    vh = view_h if view_h is not None else view.size[1]
    x0, y0, x1, y1 = view_tiles_for_camera(
        cam_x,
        cam_y,
        zoom,
        canvas_w,
        canvas_h,
        view_w=max(1, vw - 162),
        view_h=max(1, vh - 24),
        screen_w=vw,
        screen_h=vh,
        facing=facing,
    )
    x0 = max(0, x0 - 1)
    y0 = max(0, y0 - 1)
    x1 = min(MAP_W - 1, x1 + 1)
    y1 = min(MAP_H - 1, y1 + 1)
    overlay = Image.new("RGBA", view.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    tw, th = iso_tile_size(zoom)
    painted = False
    for ty in range(y0, y1 + 1):
        row = ty * MAP_W * TILE_STRIDE
        for tx in range(x0, x1 + 1):
            off = row + tx * TILE_STRIDE
            idx = overlay_pixel(tiles, off, overlay_id)
            if not idx:
                continue
            rgb = palette_rgb(idx)
            sx, sy = tile_iso_xy(tx, ty, zoom=zoom)
            pts = (
                (sx + tw // 2, sy),
                (sx + tw - 1, sy + th // 2),
                (sx + tw // 2, sy + th - 1),
                (sx, sy + th // 2),
            )
            vpts = [
                canvas_to_view(
                    px,
                    py,
                    cam_x,
                    cam_y,
                    canvas_w,
                    canvas_h,
                    screen_w=vw,
                    screen_h=vh,
                )
                for px, py in pts
            ]
            draw.polygon(vpts, fill=(*rgb, _ISO_WASH_ALPHA))
            painted = True
    if not painted:
        return view
    return Image.alpha_composite(view.convert("RGBA"), overlay)


# --- place query (right-click / Query tool) ---

_BUILDING_NAME: dict[int, str] = {}


def _fill_names() -> None:
    if _BUILDING_NAME:
        return
    names: dict[int, str] = {
        0x05: "Rubble",
        0x1C: "Cleared land",
        0x78: "Gardens",
        0x79: "Gardens",
        0x7A: "Gardens",
        0x7B: "Gardens",
        0x7C: "Plaza",
        0x7D: "Plaza",
        0x7E: "Plaza",
        0xA2: "Shrine",
        0xA3: "Shrine",
        0xA4: "Shrine",
        0xA5: "Shrine",
        0xA6: "Temple",
        0xA7: "Temple",
        0xA8: "Temple",
        0xA9: "Temple",
        0xAB: "Basilica",
        0xAC: "Basilica",
        0xAF: "Aventine",
        0xB2: "Janiculan",
        0xB3: "Janiculan",
        0xB4: "Janiculan",
        0xB7: "Palatine",
        0xB9: "Palatine",
        0xBE: "Reservoir",
        0xBF: "Tower",
        0xC0: "Gate",
        0xC1: "Wall",
        0xC2: "Wall",
        0xCB: "Aqueduct",
        0xCC: "Aqueduct",
        0xCD: "Aqueduct",
        0xCE: "Aqueduct",
        0xD0: "Aqueduct",
        0xD1: "Aqueduct",
        0xD6: "Aqueduct",
        0xD7: "Well",
        0xDB: "Fountain",
        0xDC: "Fountain",
        0xDD: "Fountain",
        0xDE: "Fountain",
        0xDF: "Baths",
        0xE0: "Baths",
        0xE1: "Baths",
        0xE2: "Baths",
        0xE3: "Praefecture",
        0xE4: "Barracks",
        0xE5: "Theater",
        0xE6: "Odeum",
        0xE7: "Arena",
        0xE8: "Coliseum",
        0xE9: "Circus",
        0xEA: "Circus",
        0xEB: "Circus",
        0xEC: "Circus",
        0xED: "C.Maximus",
        0xEE: "C.Maximus",
        0xF3: "Grammaticus",
        0xF4: "Rhetor",
        0xF5: "Library",
        0xFA: "Factory",
        0xFB: "Hospital",
        0xFC: "Market",
        0xFD: "Market",
        0xFE: "Market",
        0xFF: "Market",
    }
    for i in range(0xCB, 0xD7):
        names.setdefault(i, "Aqueduct")
    for i in range(0x82, 0xA2):
        names.setdefault(i, "Housing")
    names[0x82] = "Tent"
    _BUILDING_NAME.update(names)


def _eng_skip(eng, slot: int, skip: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, skip)
        if got:
            return got.rstrip()
    return fallback


def _housing_query_origin(t, x: int, y: int) -> tuple[int, int, int]:
    """Housing origin and size from +5 lo-nibble (same as evolve)."""
    grade = t.terrain_id - ID_HOUSING_LO
    size = HOUSE_SIZE[grade] if 0 <= grade < len(HOUSE_SIZE) else 1
    if size <= 1:
        return x, y, 1
    piece = t.spawn_packed & 0xF
    return x - (piece % size), y - (piece // size), size


def _block_or13(city: CityMap, x: int, y: int, size: int) -> int:
    splash = 0
    for dy in range(size):
        for dx in range(size):
            tx, ty = x + dx, y + dy
            if 0 <= tx < MAP_W and 0 <= ty < MAP_H:
                splash |= city.tiles[city.offset(tx, ty) + 13]
    return splash


def query_water_line(splash: int, eng=None) -> str:
    """C2.ENG [60] water line from +13. Fountain 0x01 beats well/river 0x02.

    +13&0x01 fountain / reservoir-small → [60]+2 Water Supply
    +13&0x02 only (well/river) → [60]+3 Primitive Water Supply
    neither → [60]+4 NO Water Supply
    +13&0x04 is charged reservoir ring (pipe). It wets Fountain 0xDD
    (needs +13&4) but is not house drinking water by itself.
    """
    fountain = bool(splash & 0x01)
    well = bool(splash & 0x02)
    ring = bool(splash & 0x04)
    if fountain:
        water = _eng_skip(eng, 60, 2, "Water Supply")
        src = ["fountain"]
        if ring:
            src.append("reservoir")
        return f"{water} ({', '.join(src)})"
    if well:
        water = _eng_skip(eng, 60, 3, "Primitive Water Supply")
        return f"{water} (well/river)"
    if ring:
        water = _eng_skip(eng, 60, 4, "NO Water Supply")
        return f"{water} (reservoir pipe)"
    return _eng_skip(eng, 60, 4, "NO Water Supply")


def building_name(tid: int, eng=None) -> str:
    """C2.ENG official names when present; host table otherwise."""
    _fill_names()
    if 0x82 <= tid <= 0xA1:
        grade = tid - 0x82
        return _eng_skip(eng, 57, 14 + grade, _BUILDING_NAME.get(tid, "Housing"))
    if 0x78 <= tid <= 0x7B:
        return _eng_skip(eng, 56, 10, "Gardens")
    if tid == 0x7C:
        return _eng_skip(eng, 56, 11, "Plaza")
    if tid == 0x7D:
        return _eng_skip(eng, 57, 8, "Plaza")
    if tid == 0x7E:
        return _eng_skip(eng, 57, 9, "Plaza with Statue")
    if 0x52 <= tid <= 0x5C:
        return _eng_skip(eng, 56, 15, "Road")
    if 0x4E <= tid <= 0x51:
        return "Bridge"
    if tid == 0x05:
        return _eng_skip(eng, 57, 11, "Rubble")
    if tid == 0x1C:
        return _eng_skip(eng, 57, 12, "Empty Land")
    named = {
        0xBE: (12, 0, "Reservoir"),
        0xD7: (12, 2, "Well"),
        0xDB: (12, 3, "Fountain"),
        0xDC: (12, 3, "Fountain"),
        0xDD: (12, 3, "Fountain"),
        0xDE: (12, 3, "Fountain"),
        0xC0: (13, 0, "Wall"),
        0xC1: (13, 0, "Wall"),
        0xC2: (13, 0, "Wall"),
        0xBF: (13, 1, "Tower"),
        0xE4: (13, 2, "Barracks"),
        0xE3: (13, 3, "Praefecture"),
        0xDF: (14, 0, "Baths"),
        0xE0: (14, 0, "Baths"),
        0xE1: (14, 0, "Baths"),
        0xE2: (14, 0, "Baths"),
        0xFB: (14, 1, "Hospital"),
        0xFC: (15, 0, "Market"),
        0xFD: (15, 0, "Market"),
        0xFE: (15, 0, "Market"),
        0xFF: (15, 0, "Market"),
        0xAF: (19, 0, "Aventine"),
        0xAE: (19, 0, "Aventine"),
        0xB0: (19, 0, "Aventine"),
        0xB2: (19, 1, "Janiculan"),
        0xB3: (19, 1, "Janiculan"),
        0xB4: (19, 1, "Janiculan"),
        0xB7: (19, 2, "Palatine"),
        0xB6: (19, 2, "Palatine"),
        0xB8: (19, 2, "Palatine"),
        0xB9: (19, 2, "Palatine"),
        0xF3: (20, 0, "Grammaticus"),
        0xF4: (20, 1, "Rhetor"),
        0xF5: (20, 2, "Library"),
        0xA2: (21, 0, "Shrine"),
        0xA3: (21, 0, "Shrine"),
        0xA4: (21, 0, "Shrine"),
        0xA5: (21, 0, "Shrine"),
        0xA6: (21, 1, "Temple"),
        0xA7: (21, 1, "Temple"),
        0xA8: (21, 1, "Temple"),
        0xAB: (21, 2, "Basilica"),
        0xAC: (21, 2, "Basilica"),
        0xE5: (22, 0, "Theater"),
        0xE6: (22, 1, "Odeum"),
        0xE7: (22, 2, "Arena"),
        0xE8: (22, 3, "Coliseum"),
        0xE9: (22, 4, "Circus"),
        0xEA: (22, 4, "Circus"),
        0xEB: (22, 4, "Circus"),
        0xEC: (22, 4, "Circus"),
        0xED: (22, 5, "C.Maximus"),
        0xEE: (22, 5, "C.Maximus"),
        0xFA: (61, 0, "Factory"),
    }
    if tid in named:
        slot, skip, fb = named[tid]
        return _eng_skip(eng, slot, skip, fb)
    if 0xCB <= tid <= 0xD6:
        return _eng_skip(eng, 12, 1, "Aqueduct")
    if tid in _BUILDING_NAME:
        return _BUILDING_NAME[tid]
    if tid < 8:
        return "Water"
    if tid < ID_TERRAIN_MAX:
        return "Terrain"
    return f"Building {tid:#04x}"


@dataclass(frozen=True)
class PlaceInfo:
    x: int
    y: int
    name: str
    terrain_id: int
    flags: int
    lines: tuple[str, ...]


def query_place(city: CityMap, x: int, y: int, eng=None) -> PlaceInfo:
    """Full structure box: C2.ENG [60] + tile bytes (not walker quotes)."""
    t = city.tile(x, y)
    tid = t.terrain_id
    name = building_name(tid, eng)
    if t.is_river and t.is_pad:
        name = "Bridge"
    elif t.is_river:
        name = _eng_skip(eng, 57, 10, "River")
    lines = [
        name,
        f"tile ({x},{y})  id {tid:#04x}  +1 {t.flags:#04x}",
    ]
    land = i8(t.industry)
    if land:
        lines.append(f"{_eng_skip(eng, 60, 1, 'Land Value is')} {land}")
    else:
        lines.append(_eng_skip(eng, 60, 0, "NO Land Value"))
    if t.is_housing:
        grade = tid - ID_HOUSING_LO
        if 0 <= grade < len(HOUSE_OCCUPANCY):
            lines.append(f"workers {HOUSE_OCCUPANCY[grade]}")
        nibble = t.housing_grade & 0x0F
        if nibble:
            lines.append(f"unrest {nibble}")
        ill = t.housing_grade & 0x30
        if ill:
            lines.append(f"illness +11&0x30={ill:#x}")
    splash = t.desirability
    amenity12 = t.unknown12
    ent_size = 1
    ox, oy = x, y
    if t.is_housing:
        ox, oy, ent_size = _housing_query_origin(t, x, y)
        splash = _block_or13(city, ox, oy, ent_size)
        amenity12 = entertainment_level_block(city.tiles, ox, oy, ent_size)
    else:
        amenity12 = entertainment_level(amenity12)
    lines.append(query_water_line(splash, eng))
    if tid == 0xBE or (0xCB <= tid <= 0xD6):
        charge = t.coverage & 3
        lines.append(f"pipe +1&0xC0={t.flags & 0xC0:#x}  charge +10&3={charge}")
    if tid == 0xFA:
        kind = factory_type_name(t.special)
        stock = (t.overlay_anim & 0xF0) >> 4
        lines.append(f"{kind}  +19={t.special & 0xF}  stock {stock}")
        if t.draw & 0x80:
            if t.spawn_packed & 0xF:
                lines.append("output jugs (flag80)")
            else:
                lines.append("goods label (flag80)")
    if tid == 0xD7 or 0xDB <= tid <= 0xDE:
        if 0xDB <= tid <= 0xDE and not (splash & 4):
            lines.append("fountain dry (needs charged reservoir ring)")
    if t.coverage & 0x0C:
        lines.append(_eng_skip(eng, 60, 5, "Forum Access"))
    else:
        lines.append(_eng_skip(eng, 60, 6, "NO Forum Access"))
    # FUN_00063845 edi=2 @ 0x638a7 / fill 0x64337:
    #   internal = 0x6dc68(+10 & 0x30)  → [0x117a72]
    #   ext_bit  = signed(+17) >= 16     → [0x117a65]
    #   if internal: [0x117a65] += 1
    #   >1 → [60]+0x5C Maximum; [0x117a72] → +7 Internal;
    #   [0x117a65]>0 → +8 External; else +9 NO Security.
    # +17 flood 0x430da seeds +1&0x1E (wall 0x02, tower 0x04, river 0x10).
    # Host flood_plus17 fills a City Only river map, so +17>=16 is not a
    # wall test. External = enclosed by wall/gate/tower (same C2.ENG line).
    internal = bool(t.coverage & SECURITY_COV_BITS)
    external = tile_inside_walls(city.tiles, x, y)
    if internal and external:
        lines.append(_eng_skip(eng, 60, 0x5C, "Maximum Security"))
    elif internal:
        lines.append(_eng_skip(eng, 60, 7, "Internal Security Only"))
    elif external:
        lines.append(_eng_skip(eng, 60, 8, "External Security Only"))
    else:
        lines.append(_eng_skip(eng, 60, 9, "NO Security"))
    if t.coverage & 0xC0:
        lines.append(_eng_skip(eng, 60, 10, "Market Access"))
    else:
        lines.append(_eng_skip(eng, 60, 11, "NO Market Access"))
    edu = splash & 0x30
    if edu & 0x10:
        lines.append(_eng_skip(eng, 60, 12, "Grammaticus Access"))
    else:
        lines.append(_eng_skip(eng, 60, 13, "NO Grammaticus Access"))
    if edu & 0x20:
        lines.append(_eng_skip(eng, 60, 14, "Rhetor Access"))
    else:
        lines.append(_eng_skip(eng, 60, 15, "NO Rhetor Access"))
    lines.append(
        f"{_eng_skip(eng, 60, 16, 'Entertainment Level')} {amenity12}"
    )
    if splash & BATH_SPLASH_BIT:
        lines.append(_eng_skip(eng, 60, 17, "Near Baths"))
    else:
        lines.append(_eng_skip(eng, 60, 18, "Not Near Baths"))
    hosp = hospital_cover_percent(city.tiles)
    if hosp >= 100:
        lines.append(_eng_skip(eng, 60, 19, "Complete Hospital Cover"))
    elif hosp > 0:
        lines.append(f"{_eng_skip(eng, 60, 20, 'Hospital Cover is')} {hosp}")
    else:
        lines.append(_eng_skip(eng, 60, 0x54, "No Hospital Cover"))
    lib = library_cover_percent(city.tiles)
    if lib >= 100:
        lines.append(_eng_skip(eng, 60, 21, "Complete Library Cover"))
    elif lib > 0:
        lines.append(f"{_eng_skip(eng, 60, 22, 'Library Cover is')} {lib}")
    else:
        lines.append(_eng_skip(eng, 60, 0x55, "No Library Cover"))
    if tid in (ID_HOSPITAL, ID_LIBRARY):
        ox, oy = civic_stamp_origin(city.tiles, x, y)
        has_road, has_forum = civic_edge_access(city.tiles, ox, oy)
        if has_road:
            lines.append(_eng_skip(eng, 60, 88, "Road Access"))
        else:
            lines.append(_eng_skip(eng, 60, 89, "No Road Access"))
            lines.append(
                _eng_skip(
                    eng, 60, 90,
                    "This building needs access to a road to function effectively.",
                )
            )
        if has_forum:
            lines.append(_eng_skip(eng, 60, 82, "This building is operational."))
        else:
            lines.append(
                _eng_skip(
                    eng, 60, 83,
                    "This building is mothballed. Without access to a forum, "
                    "most of your city cannot find it.",
                )
            )
        cover = hosp if tid == ID_HOSPITAL else lib
        if cover < 100:
            if tid == ID_HOSPITAL:
                lines.append(
                    _eng_skip(
                        eng, 60, 74,
                        "Insufficient city-wide hospital facilities affects "
                        "this dwelling's ability to grow further.",
                    )
                )
            else:
                lines.append(
                    _eng_skip(
                        eng, 60, 78,
                        "Insufficient city-wide library facilities affect "
                        "this dwelling's ability to grow further.",
                    )
                )
    if tile_is_burning(tid, t.draw, t.unknown16):
        lines.append(f"on fire  timer +16={t.unknown16}")
    elif ID_HOUSING_LO <= tid <= ID_HOUSING_HI:
        if t.unknown16:
            lines.append(f"fire timer +16={t.unknown16}")
        else:
            lines.append("fire risk none")
    return PlaceInfo(x, y, name, tid, t.flags, tuple(lines))


def flyout_rect(ox: int = 0) -> tuple[int, int, int, int]:
    x = OVERLAY_WELL[0] - _FLYOUT_W - 4 + ox
    y = OVERLAY_WELL[1]
    h = 11 * _FLYOUT_ITEM_H
    return (x, y, _FLYOUT_W, h)


def flyout_item_at(mx: int, my: int, ox: int = 0) -> int | None:
    x, y, w, h = flyout_rect(ox)
    if not (x <= mx < x + w and y <= my < y + h):
        return None
    idx = (my - y) // _FLYOUT_ITEM_H
    if 0 <= idx <= 10:
        return idx
    return None


def overlay_well_contains(x: int, y: int, ox: int = 0) -> bool:
    wx, wy, ww, wh = OVERLAY_WELL
    wx += ox
    return wx <= x < wx + ww and wy <= y < wy + wh


def blit_overlay_chrome(
    frame: Image.Image,
    overlay_id: int,
    *,
    flyout_open: bool = False,
    selected: int | None = None,
    eng=None,
    ox: int = 0,
) -> Image.Image:
    """Name on INT_CITY sprite 1 + optional Geography…Cancel list."""
    out = frame.convert("RGBA")
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    wx, wy, ww, wh = OVERLAY_WELL
    wx += ox
    label = overlay_name(overlay_id, eng)
    draw.rectangle((wx + 4, wy + 4, wx + ww - 36, wy + wh - 4), fill=(8, 28, 24, 180))
    draw.text((wx + 8, wy + 7), label[:18], fill=(255, 228, 160, 255), font=font)
    if flyout_open:
        fx, fy, fw, fh = flyout_rect(ox)
        draw.rectangle((fx, fy, fx + fw - 1, fy + fh - 1), fill=(8, 28, 24, 240))
        draw.rectangle((fx, fy, fx + fw - 1, fy + fh - 1), outline=(180, 160, 80, 255))
        for i, name in enumerate(OVERLAY_NAMES):
            iy = fy + i * _FLYOUT_ITEM_H
            active = i == overlay_id or i == selected
            if active:
                draw.rectangle(
                    (fx + 1, iy, fx + fw - 2, iy + _FLYOUT_ITEM_H - 1),
                    fill=(180, 150, 40, 220),
                )
            color = (240, 230, 180, 255)
            if i == OVERLAY_CANCEL:
                color = (200, 180, 160, 255)
            draw.text((fx + 6, iy + 1), name, fill=color, font=font)
    return out.convert("RGB")


# FUN_00061d52 — color key in the INT_CITY minimap well (478,48,162,160).
# Geography (id 0) keeps the radar. Report overlays paint swatches + C2.ENG [52].
_LEGEND_TITLE_XY = (14, 8)
_LEGEND_HELP_XY = (7, 32)
_LEGEND_SWATCH = (10, 98)
_LEGEND_SWATCH_GAP = 20
_LEGEND_SWATCH_WH = 14
_LEGEND_LABEL_X = 34

# 0x61f24 / 0x61fb9: CITY1.256 index + [52] skip. Security uses 0x61fb9
# (eax=0x20 → Internal / External / Both = +32,+31,+30).
_LEGEND_THREE: dict[int, tuple[tuple[int, int, str], ...]] = {
    OVERLAY_WATER: (
        (0x84, 25, "Water Supply"),
        (0x8D, 26, "Pipe Access"),
        (0x87, 27, "Both"),
    ),
    OVERLAY_SECURITY: (
        (0x93, 32, "Internal"),
        (0x90, 31, "External"),
        (0x8D, 30, "Both"),
    ),
    OVERLAY_UNREST: (
        (0x79, 22, "Low"),
        (0x78, 23, "Medium"),
        (0x77, 24, "High"),
    ),
    OVERLAY_TAX: (
        (0x93, 22, "Low"),
        (0x90, 23, "Medium"),
        (0x8D, 24, "High"),
    ),
    OVERLAY_EDUCATION: (
        (0x84, 28, "Rhetor"),
        (0x8D, 29, "Grammaticus"),
        (0x87, 30, "Both"),
    ),
    OVERLAY_ILLNESS: (
        (0x79, 22, "Low"),
        (0x78, 23, "Medium"),
        (0x77, 24, "High"),
    ),
    OVERLAY_MARKETS: (
        (0x93, 22, "Low"),
        (0x90, 23, "Medium"),
        (0x8D, 24, "High"),
    ),
}


def overlay_has_legend(overlay_id: int) -> bool:
    """INT_CITY well color key — Geography is the radar, not a key."""
    return overlay_id in _LEGEND_THREE or overlay_id in (
        OVERLAY_LAND_VALUE,
        OVERLAY_ENTERTAINMENT,
    )


def blit_overlay_legend(
    frame: Image.Image,
    overlay_id: int,
    *,
    eng=None,
    ox: int = 0,
) -> Image.Image:
    """FUN_00061d52: name + ' key' + help + swatches in the minimap well."""
    if overlay_id <= 0 or not overlay_has_legend(overlay_id):
        return frame
    mx, my, mw, mh = MINIMAP_WELL
    mx += ox
    out = frame.convert("RGBA")
    draw = ImageDraw.Draw(out)
    font = ImageFont.load_default()
    draw.rectangle((mx, my, mx + mw - 1, my + mh - 1), fill=(8, 24, 20, 240))
    draw.rectangle(
        (mx, my, mx + mw - 1, my + mh - 1), outline=(180, 160, 80, 255)
    )
    title = overlay_name(overlay_id, eng)
    key = _eng_skip(eng, 52, 11, " key")
    if not key.startswith(" "):
        key = " " + key
    draw.text(
        (mx + _LEGEND_TITLE_XY[0], my + _LEGEND_TITLE_XY[1]),
        (title + key)[:22],
        fill=(255, 228, 160, 255),
        font=font,
    )
    help_txt = overlay_help(overlay_id, eng)
    hy = my + _LEGEND_HELP_XY[1]
    for line in _wrap_query_line(help_txt, 22)[:4]:
        draw.text(
            (mx + _LEGEND_HELP_XY[0], hy),
            line,
            fill=(200, 210, 190, 255),
            font=font,
        )
        hy += 12
    rows = _LEGEND_THREE.get(overlay_id)
    if rows is None:
        # 0x6203c: nine (lv>>3)*3+0x7E chips; Low [52]+22 / High +24.
        sx = mx + 8
        sy = my + 100
        for i in range(9):
            rgb = palette_rgb((i * 3) + 0x7E)
            x0 = sx + i * 16
            draw.rectangle((x0, sy, x0 + 14, sy + 12), fill=rgb + (255,))
        draw.text(
            (sx, sy + 16),
            _eng_skip(eng, 52, 22, "Low"),
            fill=(220, 230, 210, 255),
            font=font,
        )
        draw.text(
            (sx + 112, sy + 16),
            _eng_skip(eng, 52, 24, "High"),
            fill=(220, 230, 210, 255),
            font=font,
        )
        return out.convert("RGB")
    sx = mx + _LEGEND_SWATCH[0]
    sy = my + _LEGEND_SWATCH[1]
    wh = _LEGEND_SWATCH_WH
    for i, (index, skip, fallback) in enumerate(rows):
        y0 = sy + i * _LEGEND_SWATCH_GAP
        rgb = palette_rgb(index)
        draw.rectangle((sx, y0, sx + wh, y0 + wh), fill=rgb + (255,))
        draw.rectangle(
            (sx, y0, sx + wh, y0 + wh), outline=(200, 180, 90, 255)
        )
        draw.text(
            (mx + _LEGEND_LABEL_X, y0 + 1),
            _eng_skip(eng, 52, skip, fallback)[:14],
            fill=(220, 230, 210, 255),
            font=font,
        )
    return out.convert("RGB")


def _wrap_query_line(text: str, width: int = _DLG_LINE) -> list[str]:
    if len(text) <= width:
        return [text]
    out: list[str] = []
    rest = text
    while rest:
        if len(rest) <= width:
            out.append(rest)
            break
        cut = rest.rfind(" ", 0, width)
        if cut <= 0:
            cut = width
        out.append(rest[:cut])
        rest = rest[cut:].lstrip()
    return out


def _query_layout(win_w: int, win_h: int) -> tuple[int, int, int]:
    """Same integer scale as Forum — Query blit is native 420×280."""
    from app.forum import forum_layout

    return forum_layout(win_w, win_h)


def _query_to_native(
    x: int, y: int, frame_size: tuple[int, int] | None
) -> tuple[int, int]:
    if frame_size is None:
        return int(x), int(y)
    from app.forum import forum_to_native

    return forum_to_native(int(x), int(y), frame_size[0], frame_size[1])


def _place_dialog_wrapped(info: PlaceInfo | None) -> list[str]:
    wrapped: list[str] = []
    if info is None:
        return wrapped
    for line in info.lines:
        wrapped.extend(_wrap_query_line(line))
    return wrapped


def place_dialog_rect(info: PlaceInfo | None = None) -> tuple[int, int, int, int]:
    """Native 640×480 rect (x, y, w, h). Grows with wrapped Query lines."""
    n = len(_place_dialog_wrapped(info))
    body = 22 + 13 * n + 10
    h = max(_DLG_H, body + _DLG_OK_H + _DLG_OK_PAD + 4)
    return (_DLG_X, _DLG_Y, _DLG_W, h)


def place_dialog_ok_rect(
    info: PlaceInfo | None = None,
) -> tuple[int, int, int, int]:
    """Native OK gadget — bottom-right of the structure box."""
    x0, y0, w, h = place_dialog_rect(info)
    return (
        x0 + w - _DLG_OK_PAD - _DLG_OK_W,
        y0 + h - _DLG_OK_PAD - _DLG_OK_H,
        _DLG_OK_W,
        _DLG_OK_H,
    )


def place_dialog_contains(
    x: int,
    y: int,
    info: PlaceInfo | None = None,
    *,
    frame_size: tuple[int, int] | None = None,
) -> bool:
    """Window pixels. Converts through Forum scale when ``frame_size`` is set."""
    nx, ny = _query_to_native(x, y, frame_size)
    x0, y0, w, h = place_dialog_rect(info)
    return x0 <= nx < x0 + w and y0 <= ny < y0 + h


def place_dialog_close_contains(
    x: int,
    y: int,
    info: PlaceInfo | None = None,
    *,
    frame_size: tuple[int, int] | None = None,
) -> bool:
    """True on the OK gadget (window pixels, Forum-scaled)."""
    nx, ny = _query_to_native(x, y, frame_size)
    bx, by, bw, bh = place_dialog_ok_rect(info)
    return bx <= nx < bx + bw and by <= ny < by + bh


def blit_place_dialog(frame: Image.Image, info: PlaceInfo) -> Image.Image:
    """Structure / walker-quote box. Native coords, Forum integer-upscale."""
    font = ImageFont.load_default()
    wrapped = _place_dialog_wrapped(info)
    x0, y0, w, h = place_dialog_rect(info)
    bx, by, bw, bh = place_dialog_ok_rect(info)
    overlay = Image.new("RGBA", (x0 + w, y0 + h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), fill=(8, 24, 22, 230))
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), outline=(200, 180, 90, 255))
    draw.text((x0 + 8, y0 + 6), "Query", fill=(255, 228, 160, 255), font=font)  # C2.ENG [73]
    y = y0 + 22
    text_bottom = by - 4
    for line in wrapped:
        if y > text_bottom - 12:
            break
        draw.text((x0 + 8, y), line, fill=(220, 230, 210, 255), font=font)
        y += 13
    # EXE Query is click-outside (no X). Host OK so dismiss is obvious.
    ok = "OK"
    draw.rectangle((bx, by, bx + bw - 1, by + bh - 1), fill=(40, 36, 16, 255))
    draw.rectangle((bx, by, bx + bw - 1, by + bh - 1), outline=(200, 180, 90, 255))
    tw = draw.textlength(ok[:8], font=font) if hasattr(draw, "textlength") else 12
    draw.text(
        (bx + max(4, (bw - int(tw)) // 2), by + 3),
        ok[:8],
        fill=(255, 228, 160, 255),
        font=font,
    )
    piece = overlay.crop((x0, y0, x0 + w, y0 + h))
    scale, ox, oy = _query_layout(frame.width, frame.height)
    if scale > 1:
        piece = piece.resize((w * scale, h * scale), Image.Resampling.NEAREST)
    out = frame.convert("RGBA")
    dest = (ox + x0 * scale, oy + y0 * scale)
    out.paste(piece, dest, piece)
    return out.convert("RGB")


def selftest() -> list[str]:
    lines: list[str] = []
    tiles = bytearray(MAP_W * MAP_H * TILE_STRIDE)

    def put(x: int, y: int, **kw: int) -> int:
        off = (y * MAP_W + x) * TILE_STRIDE
        for key, val in kw.items():
            if key == "tid":
                tiles[off] = val
            elif key == "flags":
                tiles[off + 1] = val
            else:
                tiles[off + int(key)] = val
        return off

    off = put(0, 0, tid=0x14)
    if overlay_pixel(tiles, off, OVERLAY_GEOGRAPHY) != 0:
        lines.append("FAIL  geography")
    else:
        lines.append("ok    geography plane 0")

    off = put(1, 0, tid=0x82, **{"15": 32})
    got = overlay_pixel(tiles, off, OVERLAY_LAND_VALUE)
    want = (32 >> 3) * 3 + 0x7E
    if got != want:
        lines.append(f"FAIL  land value {got:#x} want {want:#x}")
    else:
        lines.append("ok    land value +15 -> 0xD7BFC")

    off = put(2, 0, tid=0xBE, flags=0x80)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x96:
        lines.append("FAIL  water pipe")
    else:
        lines.append("ok    water pipe +1&0xC0 -> 0x96")
    off = put(3, 0, tid=0x82, flags=0, **{"13": 0x05})
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x87:
        lines.append(
            f"FAIL  water ring+charge {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water +13&3 and &4 -> 0x87")
    off = put(4, 0, tid=0xD7, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x96:
        lines.append("FAIL  water well")
    else:
        lines.append("ok    water Well 0xD7 -> 0x96")
    off = put(19, 0, tid=0xDD, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0:
        lines.append(
            f"FAIL  dry fountain overlay {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water dry Fountain 0xDD -> plane 0")
    off = put(20, 0, tid=0xDD, flags=0, **{"13": 0x04})
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x96:
        lines.append(
            f"FAIL  wet fountain overlay {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water Fountain +13&4 -> 0x96")
    off = put(21, 0, tid=0xDF, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0:
        lines.append(
            f"FAIL  dry baths overlay {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water dry Baths 0xDF -> plane 0")
    off = put(22, 0, tid=0xDF, flags=0, **{"13": 0x04})
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x96:
        lines.append(
            f"FAIL  wet baths overlay {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water Baths +13&4 -> 0x96")
    off = put(13, 0, tid=0xBE, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x96:
        lines.append("FAIL  water reservoir")
    else:
        lines.append("ok    water Reservoir 0xBE -> 0x96 (before +13)")
    off = put(14, 0, tid=0xCF, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x96:
        lines.append("FAIL  water aqueduct")
    else:
        lines.append("ok    water aqueduct 0xCF -> 0x96")
    off = put(15, 0, tid=0x1E, flags=0x10)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x84:
        lines.append(
            f"FAIL  water river {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water river -> 0x84")
    off = put(16, 0, tid=0x14, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0:
        lines.append(
            f"FAIL  water dry {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water grass -> plane 0 (no red flood)")
    off = put(17, 0, tid=0x14, flags=0xC0)
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0:
        lines.append(
            f"FAIL  water leaked pipe {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water +1&0xC0 on grass is not a pipe")
    off = put(18, 0, tid=0x14, flags=0, **{"13": 0x01})
    if overlay_pixel(tiles, off, OVERLAY_WATER) != 0x84:
        lines.append(
            f"FAIL  water fountain splash {overlay_pixel(tiles, off, OVERLAY_WATER):#x}"
        )
    else:
        lines.append("ok    water +13&1 -> 0x84 (fountain/well blob)")
    if overlay_pixel(tiles, off, OVERLAY_GEOGRAPHY) != 0:
        lines.append("FAIL  geography still tints")
    else:
        lines.append("ok    geography no tint")

    off = put(5, 0, tid=0xE3, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0x96:
        lines.append("FAIL  security prefecture")
    else:
        lines.append("ok    security Praefecture -> 0x96")
    off = put(19, 0, tid=0xE4, flags=0)
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0x8B:
        lines.append(
            f"FAIL  security barracks {overlay_pixel(tiles, off, OVERLAY_SECURITY):#x}"
        )
    else:
        lines.append("ok    security Barracks -> 0x8B")
    off = put(20, 0, tid=0x1E, flags=0x10)
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0:
        lines.append(
            f"FAIL  security river {overlay_pixel(tiles, off, OVERLAY_SECURITY):#x}"
        )
    else:
        lines.append("ok    security river -> plane 0 (no 0x96 flood)")
    off = put(21, 0, tid=0x14, flags=0, **{"17": 0x20})
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0:
        lines.append(
            f"FAIL  security grass +17 {overlay_pixel(tiles, off, OVERLAY_SECURITY):#x}"
        )
    else:
        lines.append("ok    security grass +17 -> plane 0")
    off = put(22, 0, tid=0x52, flags=0x20, **{"17": 0x20})
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0x90:
        lines.append(
            f"FAIL  security road {overlay_pixel(tiles, off, OVERLAY_SECURITY):#x}"
        )
    else:
        lines.append("ok    security road +17 -> 0x90")
    off = put(23, 0, tid=0x52, flags=0x20, **{"10": 0x30, "17": 0x20})
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0x8D:
        lines.append(
            f"FAIL  security covered road {overlay_pixel(tiles, off, OVERLAY_SECURITY):#x}"
        )
    else:
        lines.append("ok    security road +10&0x30 +17 -> 0x8D")
    off = put(24, 0, tid=0x82, flags=0, **{"10": 0x30})
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0x93:
        lines.append(
            f"FAIL  security house cover {overlay_pixel(tiles, off, OVERLAY_SECURITY):#x}"
        )
    else:
        lines.append("ok    security house +10&0x30 -> 0x93")
    off = put(25, 0, tid=0xBF, flags=0x04)
    if overlay_pixel(tiles, off, OVERLAY_SECURITY) != 0:
        lines.append(
            f"FAIL  security tower {overlay_pixel(tiles, off, OVERLAY_SECURITY):#x}"
        )
    else:
        lines.append("ok    security tower flags&6 -> plane 0")

    off = put(6, 0, tid=0x82, **{"11": 12})
    if overlay_pixel(tiles, off, OVERLAY_UNREST) != 0x77:
        lines.append(f"FAIL  unrest {overlay_pixel(tiles, off, OVERLAY_UNREST):#x}")
    else:
        lines.append("ok    unrest nibble >=11 -> 0x77")
    off = put(7, 0, tid=0x82, **{"11": 0})
    if overlay_pixel(tiles, off, OVERLAY_UNREST) != 0:
        lines.append("FAIL  unrest empty")
    else:
        lines.append("ok    unrest 0 -> empty (no fake heatmap)")

    off = put(8, 0, tid=0xAF)
    if overlay_pixel(tiles, off, OVERLAY_TAX) != 0x96:
        lines.append("FAIL  tax forum")
    else:
        lines.append("ok    tax forum -> 0x96")

    off = put(9, 0, tid=0x14, **{"12": 0x03 + 0x0C + 0x30})
    got = overlay_pixel(tiles, off, OVERLAY_ENTERTAINMENT)
    if got != (9 - 1) * 3 + 0x7E:
        lines.append(f"FAIL  ent {got:#x}")
    else:
        lines.append("ok    entertainment channel sum")

    off = put(10, 0, tid=0xF3)
    if overlay_pixel(tiles, off, OVERLAY_EDUCATION) != 0x96:
        lines.append("FAIL  edu school")
    else:
        lines.append("ok    education school -> 0x96")

    off = put(11, 0, tid=0x82, **{"11": 0x20})
    if overlay_pixel(tiles, off, OVERLAY_ILLNESS) != 0x78:
        lines.append("FAIL  illness")
    else:
        lines.append("ok    illness +11&0x30")

    off = put(12, 0, tid=0xFA)
    if overlay_pixel(tiles, off, OVERLAY_MARKETS) != 0x96:
        lines.append("FAIL  markets factory")
    else:
        lines.append("ok    markets factory -> 0x96")

    city_fac = CityMap()
    foff = city_fac.offset(4, 4)
    city_fac.tiles[foff] = 0xFA
    city_fac.tiles[foff + 3] = 0x8C
    city_fac.tiles[foff + 19] = 1
    qfac = query_place(city_fac, 4, 4)
    joined_fac = " ".join(qfac.lines)
    if "Winery" not in joined_fac:
        lines.append(f"FAIL  query factory type {qfac.lines}")
    else:
        lines.append("ok    query Factory Winery +19=1")

    city = CityMap()
    city.tiles[city.offset(0, 0)] = 0xBE
    city.tiles[city.offset(0, 0) + 1] = 0x80
    info = query_place(city, 0, 0)
    joined = " ".join(info.lines)
    if info.name != "Reservoir" or "pipe" not in joined:
        lines.append(f"FAIL  query {info.name} {info.lines}")
    elif "Land Value" not in joined or "Water" not in joined:
        lines.append(f"FAIL  query fields {info.lines}")
    elif len(info.lines) < 8:
        lines.append(f"FAIL  query too short {len(info.lines)}")
    else:
        lines.append("ok    query Reservoir structure box")
    hoff = city.offset(1, 0)
    city.tiles[hoff] = 0x82
    city.tiles[hoff + 13] = 0x05
    city.tiles[hoff + 15] = 32
    house = query_place(city, 1, 0)
    hjoin = " ".join(house.lines)
    if "workers 2" not in hjoin or "Water Supply" not in hjoin:
        lines.append(f"FAIL  query house {house.lines}")
    elif "Primitive" in hjoin or "well/river" in hjoin:
        lines.append(f"FAIL  query house fountain labeled primitive {house.lines}")
    elif "fountain" not in hjoin:
        lines.append(f"FAIL  query house missing fountain {house.lines}")
    elif "fire risk" not in hjoin:
        lines.append(f"FAIL  query house risk {house.lines}")
    else:
        lines.append("ok    query housing workers/water/risk")
    poff = city.offset(2, 0)
    city.tiles[poff] = 0xE3
    city.tiles[poff + 3] = 0x80
    city.tiles[poff + 4] = 0x50
    pref_q = query_place(city, 2, 0)
    pjoin = " ".join(pref_q.lines)
    if "on fire" in pjoin or "fire risk" in pjoin:
        lines.append(f"FAIL  query prefecture treated as fire {pref_q.lines}")
    else:
        lines.append("ok    query prefecture +3 bit7 is not fire")
    city.tiles[hoff + 3] = 0x80
    city.tiles[hoff + 16] = 10
    burn_q = query_place(city, 1, 0)
    if "on fire" not in " ".join(burn_q.lines):
        lines.append(f"FAIL  query burning house {burn_q.lines}")
    else:
        lines.append("ok    query painted ignite is on fire")
    city.tiles[hoff + 3] = 0
    city.tiles[hoff + 16] = 0
    # Screenshot bugs: +13 0x01 is fountain (not primitive); +12 51 = 0x33 → 6.
    city.tiles[hoff + 13] = 0x01
    city.tiles[hoff + 12] = 51
    hut_q = query_place(city, 1, 0)
    hut_join = " ".join(hut_q.lines)
    if "Primitive" in hut_join or "well/river" in hut_join:
        lines.append(f"FAIL  query +13&1 primitive {hut_q.lines}")
    elif "Water Supply (fountain)" not in hut_join:
        lines.append(f"FAIL  query +13&1 fountain {hut_q.lines}")
    elif "Entertainment Level 6" not in hut_join:
        lines.append(f"FAIL  query +12=51 → level {hut_q.lines}")
    elif "Entertainment Level 51" in hut_join:
        lines.append(f"FAIL  query printed packed +12 {hut_q.lines}")
    else:
        lines.append("ok    query fountain 0x01 + entertainment 51→6")
    city.tiles[hoff + 13] = 0x02
    city.tiles[hoff + 12] = 0
    well_q = " ".join(query_place(city, 1, 0).lines)
    if "Primitive Water Supply (well/river)" not in well_q:
        lines.append(f"FAIL  query well-only {well_q}")
    else:
        lines.append("ok    query +13&2 only → Primitive well/river")
    city.tiles[hoff + 13] = 0x07
    mix_q = " ".join(query_place(city, 1, 0).lines)
    if "Primitive" in mix_q or "well/river" in mix_q:
        lines.append(f"FAIL  query fountain+well still primitive {mix_q}")
    elif "Water Supply (fountain, reservoir)" not in mix_q:
        lines.append(f"FAIL  query mixed water {mix_q}")
    else:
        lines.append("ok    query +13&7 fountain hides well/river")
    city.tiles[hoff + 13] = 0x04
    ring_q = " ".join(query_place(city, 1, 0).lines)
    if "NO Water Supply (reservoir pipe)" not in ring_q:
        lines.append(f"FAIL  query ring-only {ring_q}")
    else:
        lines.append("ok    query +13&4 only → reservoir pipe, no drink")
    city.tiles[hoff + 13] = 0x05
    city.tiles[hoff + 12] = 0
    from app.city_paint import (
        paint_baths_emitter,
        paint_education_emitter,
        paint_entertainment_emitter,
        paint_security_emitter,
    )

    goff = city.offset(4, 4)
    city.tiles[goff] = 0xF3
    city.tiles[goff + 5] = 0
    paint_education_emitter(city.tiles, 4, 4)
    h2 = city.offset(6, 4)
    city.tiles[h2] = 0x83
    city.tiles[h2 + 1] = 0x01
    city.tiles[h2 + 13] = city.tiles[h2 + 13]
    edu = query_place(city, 6, 4)
    ejoin = " ".join(edu.lines)
    if "Grammaticus Access" not in ejoin or "NO Grammaticus Access" in ejoin:
        lines.append(f"FAIL  query grammaticus {edu.lines}")
    else:
        lines.append("ok    query house next to Grammaticus → access")
    voff = city.offset(10, 4)
    city.tiles[voff] = 0xE5
    city.tiles[voff + 5] = 0
    paint_entertainment_emitter(city.tiles, 10, 4)
    h3 = city.offset(12, 4)
    city.tiles[h3] = 0x83
    city.tiles[h3 + 1] = 0x01
    city.tiles[h3 + 12] = city.tiles[h3 + 12]
    ent = query_place(city, 12, 4)
    njoin = " ".join(ent.lines)
    if "Entertainment Level 0" in njoin or "Entertainment Level" not in njoin:
        lines.append(f"FAIL  query theater {ent.lines}")
    elif "Entertainment Level 51" in njoin:
        lines.append(f"FAIL  query theater packed +12 {ent.lines}")
    else:
        lines.append("ok    query house next to Theater → Entertainment > 0")
    from app.city_paint import ID_RESERVOIR, paint_plus13_buildings, paint_plus13_water

    # Charged 0xBE ring + wet 0xDD r=6 extra=0. Adjacent hut must Query
    # fountain, not primitive well/river.
    roff = city.offset(40, 8)
    city.tiles[roff] = ID_RESERVOIR
    city.tiles[roff + 10] = 3
    foff = city.offset(42, 8)
    city.tiles[foff] = 0xDD
    city.tiles[foff + 5] = 0
    h6 = city.offset(43, 8)
    city.tiles[h6] = 0x86
    city.tiles[h6 + 1] = 0x01
    paint_plus13_buildings(city.tiles, 0, MAP_H)
    paint_plus13_water(city.tiles, 0, MAP_H)
    fount_q = query_place(city, 43, 8)
    fq = " ".join(fount_q.lines)
    hut13 = city.tiles[h6 + 13]
    if not (hut13 & 0x01):
        lines.append(f"FAIL  fountain splash missed hut +13={hut13:#x}")
    elif "Primitive" in fq or "well/river" in fq:
        lines.append(f"FAIL  query hut by fountain primitive {fount_q.lines}")
    elif "Water Supply" not in fq or "fountain" not in fq:
        lines.append(f"FAIL  query hut by fountain {fount_q.lines}")
    else:
        lines.append("ok    query hut next to charged fountain → fountain")
    boff = city.offset(16, 4)
    city.tiles[boff] = 0xDF
    city.tiles[boff + 5] = 0
    city.tiles[boff + 13] = 0x04
    paint_baths_emitter(city.tiles, 16, 4)
    h4 = city.offset(18, 4)
    city.tiles[h4] = 0x83
    city.tiles[h4 + 1] = 0x01
    city.tiles[h4 + 13] = city.tiles[h4 + 13]
    bath_q = query_place(city, 18, 4)
    bjoin = " ".join(bath_q.lines)
    if "Near Baths" not in bjoin or "Not Near Baths" in bjoin:
        lines.append(f"FAIL  query baths {bath_q.lines}")
    else:
        lines.append("ok    query house next to Baths → Near Baths")
    soff = city.offset(22, 4)
    city.tiles[soff] = 0xE3
    city.tiles[soff + 5] = 0
    paint_security_emitter(city.tiles, 22, 4)
    h5 = city.offset(23, 4)
    city.tiles[h5] = 0x83
    city.tiles[h5 + 1] = 0x01
    city.tiles[h5 + 10] = city.tiles[h5 + 10]
    sec_q = query_place(city, 23, 4)
    sjoin = " ".join(sec_q.lines)
    if "Internal Security Only" not in sjoin or "NO Security" in sjoin:
        lines.append(f"FAIL  query prefecture {sec_q.lines}")
    elif "Maximum Security" in sjoin:
        lines.append(f"FAIL  query prefecture without walls → max {sec_q.lines}")
    else:
        lines.append("ok    query house next to Praefecture → Internal Security")
    # Host +17 stand-in is river-wide; EXE External is walls (0x64337 +17
    # is the same byte, but City Only river must not promote to Maximum).
    city.tiles[h5 + 17] = 100
    flood_q = query_place(city, 23, 4)
    fjoin = " ".join(flood_q.lines)
    if "Maximum Security" in fjoin or "External Security Only" in fjoin:
        lines.append(f"FAIL  query +17 without walls {flood_q.lines}")
    elif "Internal Security Only" not in fjoin:
        lines.append(f"FAIL  query +17 still internal {flood_q.lines}")
    else:
        lines.append("ok    query +17 flood without walls stays Internal")
    from app.city_paint import ID_WALL_EW, ID_WALL_NS, tile_inside_walls

    def _box(ox: int, oy: int) -> None:
        for i in range(5):
            city.tiles[city.offset(ox + i, oy)] = ID_WALL_EW
            city.tiles[city.offset(ox + i, oy + 4)] = ID_WALL_EW
            city.tiles[city.offset(ox, oy + i)] = ID_WALL_NS
            city.tiles[city.offset(ox + 4, oy + i)] = ID_WALL_NS

    _box(40, 40)
    woff = city.offset(42, 42)
    city.tiles[woff] = 0x83
    city.tiles[woff + 1] = 0x01
    if not tile_inside_walls(city.tiles, 42, 42):
        lines.append("FAIL  enclosure 5×5 wall box")
    else:
        lines.append("ok    5×5 wall box encloses (42,42)")
    wall_q = query_place(city, 42, 42)
    wjoin = " ".join(wall_q.lines)
    if "External Security Only" not in wjoin or "Maximum Security" in wjoin:
        lines.append(f"FAIL  query walls only {wall_q.lines}")
    else:
        lines.append("ok    query enclosed house → External Security Only")
    city.tiles[woff + 10] = SECURITY_COV_BITS
    max_q = query_place(city, 42, 42)
    mjoin = " ".join(max_q.lines)
    if "Maximum Security" not in mjoin:
        lines.append(f"FAIL  query walls+prefect {max_q.lines}")
    else:
        lines.append("ok    query enclosed + prefect → Maximum Security")
    open_q = query_place(city, 1, 0)
    if "NO Security" not in " ".join(open_q.lines):
        lines.append(f"FAIL  query open house {open_q.lines}")
    else:
        lines.append("ok    query house with no prefect/walls → NO Security")
    hosp_off = city.offset(26, 4)
    city.tiles[hosp_off] = 0xFB
    city.tiles[hosp_off + 5] = 0
    dead = query_place(city, 26, 4)
    dj = " ".join(dead.lines)
    if (
        "No Hospital Cover" not in dj
        or "No Road Access" not in dj
        or "mothballed" not in dj
    ):
        lines.append(f"FAIL  query hospital isolated {dead.lines}")
    else:
        lines.append("ok    isolated Hospital 0xFB → no road / no forum / no cover")
    road = city.offset(26, 3)
    city.tiles[road] = 0x52
    city.tiles[road + 1] = 0x20
    city.tiles[road + 10] = 0x0C
    live = query_place(city, 26, 4)
    lj = " ".join(live.lines)
    if "Complete Hospital Cover" not in lj or "Road Access" not in lj:
        lines.append(f"FAIL  query hospital working {live.lines}")
    elif "No Road Access" in lj or "mothballed" in lj:
        lines.append(f"FAIL  query hospital still dead {live.lines}")
    else:
        lines.append("ok    Hospital 0xFB road+forum → operational + complete cover")
    lib_off = city.offset(30, 4)
    city.tiles[lib_off] = 0xF5
    city.tiles[lib_off + 5] = 0
    lib_dead = query_place(city, 30, 4)
    ldj = " ".join(lib_dead.lines)
    if "No Library Cover" not in ldj or "No Road Access" not in ldj:
        lines.append(f"FAIL  query library isolated {lib_dead.lines}")
    else:
        lines.append("ok    isolated Library 0xF5 → no road / no cover")
    lroad = city.offset(30, 3)
    city.tiles[lroad] = 0x52
    city.tiles[lroad + 1] = 0x20
    city.tiles[lroad + 10] = 0x0C
    lib_live = query_place(city, 30, 4)
    llj = " ".join(lib_live.lines)
    if "Complete Library Cover" not in llj or "operational" not in llj:
        lines.append(f"FAIL  query library working {lib_live.lines}")
    else:
        lines.append("ok    Library 0xF5 road+forum → operational + complete cover")
    big = CityMap()
    bo = big.offset(2, 2)
    big.tiles[bo] = 0xFB
    big.tiles[big.offset(2, 1)] = 0x52
    big.tiles[big.offset(2, 1) + 1] = 0x20
    big.tiles[big.offset(2, 1) + 10] = 0x0C
    lo = big.offset(6, 2)
    big.tiles[lo] = 0xF5
    big.tiles[big.offset(6, 1)] = 0x52
    big.tiles[big.offset(6, 1) + 1] = 0x20
    big.tiles[big.offset(6, 1) + 10] = 0x0C
    # 0x9C villa origin occupancy 100; 20 of them → pop 2000.
    for i in range(20):
        ho = big.offset(10 + i, 10)
        big.tiles[ho] = 0x9C
    hp = hospital_cover_percent(big.tiles)
    lp = library_cover_percent(big.tiles)
    qbig = " ".join(query_place(big, 2, 2).lines)
    if hp != 50 or lp != 60:
        lines.append(f"FAIL  cover formula hosp={hp} lib={lp} (want 50/60)")
    elif "Hospital Cover is 50" not in qbig or "Insufficient city-wide hospital" not in qbig:
        lines.append(f"FAIL  query pop-short {qbig}")
    else:
        lines.append("ok    cover n×1000×100/pop and n×1200×100/pop")
    if overlay_name(2) != "Water" or overlay_name(10) != "Cancel":
        lines.append("FAIL  names")
    else:
        lines.append("ok    C2.ENG overlay names")
    if flyout_item_at(*OVERLAY_WELL[:2]) is not None:
        lines.append("FAIL  flyout over well")
    else:
        lines.append("ok    flyout left of sidebar")
    if overlay_has_legend(OVERLAY_GEOGRAPHY) or not overlay_has_legend(
        OVERLAY_WATER
    ):
        lines.append("FAIL  legend ids")
    else:
        lines.append("ok    Water/Security have a key; Geography does not")
    blank = Image.new("RGB", (640, 480), (0, 0, 0))
    water_key = blit_overlay_legend(blank, OVERLAY_WATER)
    sec_key = blit_overlay_legend(blank, OVERLAY_SECURITY)
    geo_key = blit_overlay_legend(blank, OVERLAY_GEOGRAPHY)
    wx, wy, _ww, _wh = MINIMAP_WELL
    if water_key.getpixel((wx + 20, wy + 20)) == (0, 0, 0):
        lines.append("FAIL  water legend well empty")
    elif sec_key.getpixel((wx + 20, wy + 20)) == (0, 0, 0):
        lines.append("FAIL  security legend well empty")
    elif geo_key.getpixel((wx + 20, wy + 20)) != (0, 0, 0):
        lines.append("FAIL  geography painted a legend")
    elif water_key.getpixel((wx + 12, wy + 100)) == (0, 0, 0):
        lines.append("FAIL  water swatch missing")
    else:
        lines.append("ok    Water/Security legend in minimap well")

    qinfo = PlaceInfo(0, 0, "T", 0, 0, ("a",))
    ox, oy, ow, oh = place_dialog_ok_rect(qinfo)
    if not place_dialog_contains(20, 50, qinfo):
        lines.append("FAIL  query box hit native")
    elif place_dialog_contains(500, 50, qinfo):
        lines.append("FAIL  query box miss native")
    elif not place_dialog_close_contains(ox + 2, oy + 2, qinfo):
        lines.append("FAIL  query OK hit native")
    else:
        lines.append("ok    query OK / box hit native")
    wide = (1442, 960)
    if not place_dialog_close_contains(ox * 2 + 2, oy * 2 + 2, qinfo, frame_size=wide):
        lines.append("FAIL  query OK hit 2x Forum scale")
    elif not place_dialog_contains(
        (_DLG_X + _DLG_W - 8) * 2, (_DLG_Y + 20) * 2, qinfo, frame_size=wide
    ):
        lines.append("FAIL  query box right edge 2x")
    elif place_dialog_contains(20, 50, qinfo, frame_size=wide):
        lines.append("FAIL  query native click is not 2x")
    else:
        lines.append("ok    query hit-test uses Forum 2x scale")
    painted = blit_place_dialog(Image.new("RGB", (640, 480), (0, 0, 0)), qinfo)
    if painted.getpixel((ox + 4, oy + 4)) == (0, 0, 0):
        lines.append("FAIL  query OK not painted")
    else:
        lines.append("ok    query OK painted")

    from app.city_map import iso_canvas_size, iso_tile_size, tile_iso_xy

    cw, ch = iso_canvas_size(0)
    put(40, 40, tid=0x1E, flags=0x10)
    sx, sy = tile_iso_xy(40, 40, zoom=0)
    tw, th = iso_tile_size(0)
    cam_x = max(0, sx + tw // 2 - 320)
    cam_y = max(0, sy + th // 2 - 240)
    blank = Image.new("RGBA", (640, 480), (20, 40, 20, 255))
    geo = overlay_iso_wash(blank, tiles, OVERLAY_GEOGRAPHY, 0, cam_x, cam_y, cw, ch)
    if geo.tobytes() != blank.tobytes():
        lines.append("FAIL  geography iso wash")
    else:
        lines.append("ok    geography iso no wash")
    washed = overlay_iso_wash(blank, tiles, OVERLAY_WATER, 0, cam_x, cam_y, cw, ch)
    if washed.tobytes() == blank.tobytes():
        lines.append("FAIL  water iso wash empty")
    else:
        lines.append("ok    water iso wash tints viewport")
    grass_only = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    for i in range(MAP_W * MAP_H):
        grass_only[i * TILE_STRIDE] = 0x14
    sx, sy = tile_iso_xy(41, 40, zoom=0)
    cam_x = max(0, sx + tw // 2 - 320)
    cam_y = max(0, sy + th // 2 - 240)
    dry = overlay_iso_wash(blank, grass_only, OVERLAY_WATER, 0, cam_x, cam_y, cw, ch)
    if dry.tobytes() != blank.tobytes():
        lines.append("FAIL  water iso wash paints dry grass")
    else:
        lines.append("ok    water iso wash skips uncovered grass")
    from pathlib import Path as _Path

    from app.boot import BootContext
    from app.sim import SimState
    from app.window import compose_frame, crop_viewport

    big = Image.new("RGBA", (2000, 1200), (30, 80, 30, 255))
    view800, cx, cy = crop_viewport(big, 100, 80, view_w=800, view_h=600)
    if view800.size != (800, 600):
        lines.append(f"FAIL  crop resize {view800.size}")
    else:
        lines.append("ok    crop_viewport 800×600 (more map, same zoom)")
    native = crop_viewport(big, 0, 0, view_w=640, view_h=480)[0]
    if native.size != (640, 480):
        lines.append(f"FAIL  crop native {native.size}")
    else:
        lines.append("ok    crop_viewport native 640×480")
    huge = Image.new("RGBA", (4640, 2400), (200, 30, 30, 255))
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
        city=CityMap(),
        walkers=[],
        sim=SimState(),
        audio_status="",
        start_in_map=True,
    )
    framed = compose_frame(fake, view=None, map_mode=True)
    if framed.size != (640, 480) or framed.getpixel((320, 240))[0] > 80:
        lines.append("FAIL  maximize must not _fit full iso")
    else:
        lines.append("ok    compose_frame map_mode no zoom-pop")
    wide = compose_frame(fake, view=view800.convert("RGB"), map_mode=True)
    if wide.size != (800, 600):
        lines.append(f"FAIL  compose keeps viewport {wide.size}")
    else:
        lines.append("ok    compose_frame keeps 800×600 viewport")
    return lines
