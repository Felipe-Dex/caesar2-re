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

from app.city_map import ID_TERRAIN_MAX, MAP_H, MAP_W, TILE_STRIDE, CityMap
from app.city_paint import HOUSE_OCCUPANCY, ID_HOUSING_LO

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
    "Shows unrest / immigrant nibble on houses.",
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


def overlay_name(overlay_id: int, eng=None) -> str:
    if eng is not None:
        got = eng.skip(52, overlay_id)
        if got:
            return got
    if 0 <= overlay_id < len(OVERLAY_NAMES):
        return OVERLAY_NAMES[overlay_id]
    return f"overlay {overlay_id}"


def overlay_help(overlay_id: int, eng=None) -> str:
    if eng is not None and overlay_id <= 3:
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
    # 0x3E6BA: pipe tile +1&0xC0 or Well/Fountain 0xD7–0xDE → 0x96.
    # +13&3 (well/fountain/reservoir-small) and +13&4 (reservoir ring).
    # Else plane 0 — dimmed geography, not a dry-red flood.
    # +1&0xC0 is only the reservoir/aqueduct cell itself, not a map-wide pipe.
    if 0xD7 <= tid <= 0xDE:
        return 0x96
    if _is_pipe_building(tid) and (flags & 0xC0):
        return 0x96
    charge = splash & 3
    ring = splash & 4
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


def _paint_security(tid: int, flags: int, cov10: int, flood17: int) -> int:
    # 0x3E7DB. Prefects +10&0x30; road-access +17>=16; buildings 0xE3/E4.
    score = 0
    if i8(flood17) >= 0x10:
        score = 1
    if cov10 & 0x30:
        score += 1
    if flags & 6:
        return 0x96
    if 0x1E <= tid <= 0x51:
        return 0x96
    if tid in (0xE3, 0xE4):
        return 0x96
    if score == 0:
        return 0
    if score == 2:
        return 0x8D
    if cov10 & 0x30:
        return 0x93
    if score == 1:
        return 0x90
    return 0


def _paint_unrest(grade11: int) -> int:
    # 0x3EA8E: +11 lo-nibble (immigrant / unrest). 0 empty; ≥11 / ≥5 / else.
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
    ch0 = amenity12 & 3
    ch1 = (amenity12 & 0x0C) >> 2
    ch2 = (amenity12 & 0x30) >> 4
    total = ch0 + ch1 + ch2
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
    if splash & 0x04 or splash & 0x02:
        water = _eng_skip(eng, 60, 2, "Water Supply")
    elif splash & 0x01:
        water = _eng_skip(eng, 60, 3, "Primitive Water Supply")
    else:
        water = _eng_skip(eng, 60, 4, "NO Water Supply")
    bits = []
    if splash & 1:
        bits.append("small")
    if splash & 2:
        bits.append("well/river")
    if splash & 4:
        bits.append("reservoir ring")
    if bits:
        lines.append(f"{water} ({', '.join(bits)})")
    else:
        lines.append(water)
    if tid == 0xBE or (0xCB <= tid <= 0xD6):
        charge = t.coverage & 3
        lines.append(f"pipe +1&0xC0={t.flags & 0xC0:#x}  charge +10&3={charge}")
    if tid == 0xD7 or 0xDB <= tid <= 0xDE:
        if 0xDB <= tid <= 0xDE and not (splash & 4):
            lines.append("fountain dry (needs charged reservoir ring)")
    if t.coverage & 0x0C:
        lines.append(_eng_skip(eng, 60, 5, "Forum Access"))
    else:
        lines.append(_eng_skip(eng, 60, 6, "NO Forum Access"))
    sec = t.coverage & 0x30
    if sec == 0x10:
        lines.append(_eng_skip(eng, 60, 7, "Internal Security Only"))
    elif sec == 0x20:
        lines.append(_eng_skip(eng, 60, 8, "External Security Only"))
    elif sec == 0x30:
        lines.append(
            f"{_eng_skip(eng, 60, 7, 'Internal Security Only')} / "
            f"{_eng_skip(eng, 60, 8, 'External Security Only')}"
        )
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
        f"{_eng_skip(eng, 60, 16, 'Entertainment Level')} {t.unknown12}"
    )
    if t.draw & 0x80:
        lines.append(f"fire risk  +3 bit7  timer +16={t.unknown16}")
    elif t.unknown16:
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


def place_dialog_contains(x: int, y: int) -> bool:
    return _DLG_X <= x < _DLG_X + _DLG_W and _DLG_Y <= y < _DLG_Y + _DLG_H + 80


def blit_place_dialog(frame: Image.Image, info: PlaceInfo) -> Image.Image:
    out = frame.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    wrapped: list[str] = []
    for line in info.lines:
        wrapped.extend(_wrap_query_line(line))
    h = max(_DLG_H, 28 + 13 * len(wrapped) + 10)
    x0, y0, w = _DLG_X, _DLG_Y, _DLG_W
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), fill=(8, 24, 22, 230))
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), outline=(200, 180, 90, 255))
    draw.text((x0 + 8, y0 + 6), "Query", fill=(255, 228, 160, 255), font=font)  # C2.ENG [73]
    y = y0 + 22
    for line in wrapped:
        draw.text((x0 + 8, y), line, fill=(220, 230, 210, 255), font=font)
        y += 13
        if y > y0 + h - 14:
            break
    return Image.alpha_composite(out, overlay).convert("RGB")


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
    elif "fire risk" not in hjoin:
        lines.append(f"FAIL  query house risk {house.lines}")
    else:
        lines.append("ok    query housing workers/water/risk")
    if overlay_name(2) != "Water" or overlay_name(10) != "Cancel":
        lines.append("FAIL  names")
    else:
        lines.append("ok    C2.ENG overlay names")
    if flyout_item_at(*OVERLAY_WELL[:2]) is not None:
        lines.append("FAIL  flyout over well")
    else:
        lines.append("ok    flyout left of sidebar")

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
