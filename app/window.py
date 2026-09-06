"""640×480 host window (video_init @ 0x28341 stand-in). Pillow blit via tkinter.

City map (key 3): viewport onto the native iso canvas. Arrow keys pan.
Without a build tool (or Query) click-drag pans. Housing / Roads / Clear /
Aqueduct rubber-band on drag and stamp on release (aqueduct is a road-style
line). Stamp tools (Barracks 3×3, Reservoir 1×1) ghost one footprint that
follows the cursor. +/- switch PL8 zoom 0/1/2.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from app.boot import BootContext
from app.calendar import TICK_MS
from app.city_chrome import (
    CityChrome,
    SCREEN_H,
    SCREEN_W,
    SIDEBAR_W,
    SIDEBAR_X,
    TOP_BAR_H,
    chrome_ox,
    speed_action,
)
from app.city_map import WATER_FRAME_MS, WATER_FRAMES
from app.city_overlay import (
    OVERLAY_CANCEL,
    OVERLAY_GEOGRAPHY,
    PlaceInfo,
    blit_overlay_chrome,
    blit_place_dialog,
    flyout_item_at,
    flyout_rect,
    load_overlay_palette,
    overlay_help,
    overlay_iso_wash,
    overlay_name,
    overlay_well_contains,
    place_dialog_contains,
    query_place,
)
from app.palette import PaletteState, action_for_tool
from app.place import (
    DRAW_AQUEDUCT,
    DRAW_GARDEN,
    SPAN_TOOLS,
    STAMP_TOOLS,
    TOOL_AQUEDUCT,
    TOOL_BARRACKS,
    TOOL_CLEAR,
    TOOL_FOUNTAIN,
    TOOL_GARDEN,
    TOOL_PLAZA,
    TOOL_PREFECTURE,
    TOOL_QUERY,
    TOOL_RESERVOIR,
    TOOL_ROAD,
    TOOL_TENT,
    TOOL_TOWER,
    TOOL_WALL,
    TOOL_WELL,
    DragPreview,
    aqueduct_preview_cells,
    canvas_to_view,
    garden_preview_cells,
    in_map,
    preview_span,
    screen_to_tile,
    stamp_ghost_pieces,
    try_place,
    try_place_span,
    view_to_canvas,
)

BG = (12, 16, 28)
PAN_STEP = (96, 48, 24)
CLICK_DRAG_PX = 6
# HUD 0x6189D: year at EDX=0x130 / y=6; treasury at ECX=0x230. Suffix EXE 0x90d4b.
HUD_DATE_X = 0x130
HUD_DATE_Y = 6
HUD_TREASURY_X = 0x230
HUD_TREASURY_Y = 6
HUD_TREASURY_SUFFIX = " Dn"
HUD_GOLD = (255, 228, 160, 255)
HUD_TREASURY_NEG = (255, 120, 90, 255)
# C2.ENG [0] File · [1] Options · [2] Speed · [3] Help
_MENU_SLOTS = (0, 1, 2, 3)
_MENU_FALLBACK = ("File", "Options", "Speed", "Help")
_MENU_ITEM_SKIP = {
    0: (1, 2, 3, 4),
    1: (1, 2, 3, 4, 5),
    2: (1, 2, 3),
    3: (1, 2, 3, 4, 5),
}
_MENU_ITEM_FALLBACK = {
    0: ("New Game", "Load", "Save", "Quit"),
    1: ("Music", "Sound", "Animations", "End of Year ", "Census"),
    2: ("Game Speed", "Scroll Speed", "Pause"),
    3: ("Hints and Tips", "Game Help", "History", "Icons", "About"),
}
_MENU_X0 = 8
_MENU_GAP = 14
_DROP_ITEM_H = 16


def _fit(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    if rgba.size == (SCREEN_W, SCREEN_H):
        return rgba
    canvas = Image.new("RGBA", (SCREEN_W, SCREEN_H), (*BG, 255))
    src = rgba
    if src.width > SCREEN_W or src.height > SCREEN_H:
        src = src.copy()
        src.thumbnail((SCREEN_W, SCREEN_H), Image.Resampling.NEAREST)
    elif src.width < 160 and src.height < 80:
        # CITYFIXT iso diamond is tiny; nearest-scale so it is visible.
        scale = min(SCREEN_W // max(src.width, 1), SCREEN_H // max(src.height, 1), 8)
        src = src.resize(
            (src.width * scale, src.height * scale), Image.Resampling.NEAREST
        )
    x = (SCREEN_W - src.width) // 2
    y = (SCREEN_H - src.height) // 2
    canvas.paste(src, (x, y), src)
    return canvas


def crop_viewport(
    canvas: Image.Image,
    cam_x: int,
    cam_y: int,
    *,
    view_w: int = SCREEN_W,
    view_h: int = SCREEN_H,
) -> tuple[Image.Image, int, int]:
    """Window-sized crop onto ``canvas``. Larger view → more iso pixels, same zoom."""
    vw = max(1, int(view_w))
    vh = max(1, int(view_h))
    max_x = max(0, canvas.width - vw)
    max_y = max(0, canvas.height - vh)
    x = max(0, min(int(cam_x), max_x))
    y = max(0, min(int(cam_y), max_y))
    view = Image.new("RGBA", (vw, vh), (*BG, 255))
    if canvas.width <= vw and canvas.height <= vh:
        px = (vw - canvas.width) // 2
        py = (vh - canvas.height) // 2
        view.paste(canvas, (px, py), canvas)
        return view, 0, 0
    box = (
        x,
        y,
        x + min(vw, canvas.width),
        y + min(vh, canvas.height),
    )
    crop = canvas.crop(box)
    view.paste(crop, (0, 0), crop)
    return view, x, y


_PREVIEW_FILL = {
    TOOL_TENT: (255, 210, 70, 115),
    TOOL_ROAD: (190, 195, 210, 125),
    TOOL_CLEAR: (255, 80, 60, 105),
    TOOL_RESERVOIR: (70, 160, 220, 120),
    TOOL_AQUEDUCT: (90, 170, 200, 120),
    TOOL_WELL: (80, 190, 210, 120),
    TOOL_FOUNTAIN: (70, 200, 220, 120),
    TOOL_GARDEN: (80, 190, 90, 115),
    TOOL_PREFECTURE: (210, 150, 80, 120),
    TOOL_TOWER: (180, 140, 90, 120),
    TOOL_BARRACKS: (200, 120, 70, 120),
    TOOL_WALL: (160, 155, 150, 125),
    TOOL_PLAZA: (210, 190, 140, 120),
}
_PREVIEW_REFUSE = (255, 55, 50, 115)
_PREVIEW_SKIP = (230, 40, 40, 160)


def _diamond_view_pts(
    tx: int,
    ty: int,
    zoom: int,
    cam_x: int,
    cam_y: int,
    canvas_w: int,
    canvas_h: int,
    *,
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> list[tuple[int, int]]:
    from app.city_map import iso_tile_size, tile_iso_xy

    sx, sy = tile_iso_xy(tx, ty, zoom=zoom)
    tw, th = iso_tile_size(zoom)
    pts = (
        (sx + tw // 2, sy),
        (sx + tw - 1, sy + th // 2),
        (sx + tw // 2, sy + th - 1),
        (sx, sy + th // 2),
    )
    return [
        canvas_to_view(
            px, py, cam_x, cam_y, canvas_w, canvas_h, screen_w=screen_w, screen_h=screen_h
        )
        for px, py in pts
    ]


def _as_ghost(spr: Image.Image, *, refuse: bool) -> Image.Image:
    rgba = spr.convert("RGBA")
    r, g, b, a = rgba.split()
    if refuse:
        r = r.point(lambda v: min(255, int(v) + 70))
        g = g.point(lambda v: int(v) // 2)
        b = b.point(lambda v: int(v) // 2)
    a = a.point(lambda v: int(v) * 150 // 255)
    return Image.merge("RGBA", (r, g, b, a))


def overlay_stamp_ghost(
    view: Image.Image,
    preview: DragPreview,
    zoom: int,
    cam_x: int,
    cam_y: int,
    canvas_w: int,
    canvas_h: int,
    sheets: dict | None = None,
    *,
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
) -> Image.Image:
    """One N×N stamp: translucent building sprites, or a single footprint bbox."""
    from app.city_map import (
        building_sprite_image,
        iso_sprite_dest,
        iso_tile_size,
        tile_iso_xy,
    )

    overlay = Image.new("RGBA", view.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fill = _PREVIEW_REFUSE if preview.refuse else _PREVIEW_FILL.get(
        preview.tool, (200, 200, 80, 110)
    )
    outline = (255, 255, 255, 200) if not preview.refuse else (255, 180, 160, 220)
    cells = [c for c in preview.cells if in_map(c[0], c[1])]
    painted = False
    if sheets and cells:
        ox = min(c[0] for c in preview.cells)
        oy = min(c[1] for c in preview.cells)
        th = iso_tile_size(zoom)[1]
        for dx, dy, tid, bdraw, variant in stamp_ghost_pieces(preview.tool):
            tx, ty = ox + dx, oy + dy
            if not in_map(tx, ty):
                continue
            spr = building_sprite_image(tid, bdraw, variant, sheets, zoom=zoom)
            if spr is None:
                continue
            ghost = _as_ghost(spr, refuse=bool(preview.refuse))
            sx, sy = tile_iso_xy(tx, ty, zoom=zoom)
            px, py = iso_sprite_dest(sx, sy, ghost.height, th)
            vx, vy = canvas_to_view(
                px, py, cam_x, cam_y, canvas_w, canvas_h, screen_w=screen_w, screen_h=screen_h
            )
            overlay.paste(ghost, (vx, vy), ghost)
            painted = True
    if not painted and cells:
        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        tw, th = iso_tile_size(zoom)
        n_sx, n_sy = tile_iso_xy(x0, y0, zoom=zoom)
        e_sx, e_sy = tile_iso_xy(x1, y0, zoom=zoom)
        s_sx, s_sy = tile_iso_xy(x1, y1, zoom=zoom)
        w_sx, w_sy = tile_iso_xy(x0, y1, zoom=zoom)
        quad = [
            (n_sx + tw // 2, n_sy),
            (e_sx + tw - 1, e_sy + th // 2),
            (s_sx + tw // 2, s_sy + th - 1),
            (w_sx, w_sy + th // 2),
        ]
        vquad = [
            canvas_to_view(
                px, py, cam_x, cam_y, canvas_w, canvas_h, screen_w=screen_w, screen_h=screen_h
            )
            for px, py in quad
        ]
        draw.polygon(vquad, fill=fill, outline=outline)
    for tx, ty in preview.skip:
        if not in_map(tx, ty):
            continue
        pts = _diamond_view_pts(
            tx, ty, zoom, cam_x, cam_y, canvas_w, canvas_h, screen_w=screen_w, screen_h=screen_h
        )
        draw.polygon(pts, outline=_PREVIEW_SKIP)
    return Image.alpha_composite(view.convert("RGBA"), overlay)


def overlay_span_preview(
    view: Image.Image,
    preview: DragPreview,
    zoom: int,
    cam_x: int,
    cam_y: int,
    canvas_w: int,
    canvas_h: int,
    sheets: dict | None = None,
    *,
    screen_w: int = SCREEN_W,
    screen_h: int = SCREEN_H,
    city=None,
) -> Image.Image:
    """Translucent iso diamonds (or one bbox fill) for the rubber-band."""
    overlay = Image.new("RGBA", view.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    fill = _PREVIEW_REFUSE if preview.refuse else _PREVIEW_FILL.get(
        preview.tool, (200, 200, 80, 110)
    )
    outline = (255, 255, 255, 200) if not preview.refuse else (255, 180, 160, 220)
    cells = preview.ok
    piece_rows: list[tuple[int, int, int, int]] = []
    piece_draw = 0
    if preview.tool == TOOL_GARDEN and sheets:
        piece_rows = garden_preview_cells(preview.ok, preview.stamp)
        piece_draw = DRAW_GARDEN
    elif preview.tool == TOOL_AQUEDUCT and sheets and city is not None:
        piece_rows = aqueduct_preview_cells(city, preview.ok, preview.stamp)
        piece_draw = DRAW_AQUEDUCT
    if piece_rows:
        from app.city_map import building_sprite_image, iso_sprite_dest, iso_tile_size, tile_iso_xy

        th = iso_tile_size(zoom)[1]
        painted = False
        for tx, ty, tid, variant in piece_rows:
            spr = building_sprite_image(tid, piece_draw, variant, sheets, zoom=zoom)
            if spr is None:
                continue
            ghost = _as_ghost(spr, refuse=bool(preview.refuse))
            sx, sy = tile_iso_xy(tx, ty, zoom=zoom)
            px, py = iso_sprite_dest(sx, sy, ghost.height, th)
            vx, vy = canvas_to_view(
                px, py, cam_x, cam_y, canvas_w, canvas_h, screen_w=screen_w, screen_h=screen_h
            )
            overlay.paste(ghost, (vx, vy), ghost)
            painted = True
        if painted:
            for tx, ty in preview.skip:
                pts = _diamond_view_pts(
                    tx, ty, zoom, cam_x, cam_y, canvas_w, canvas_h,
                    screen_w=screen_w, screen_h=screen_h,
                )
                draw.polygon(pts, outline=_PREVIEW_SKIP)
            return Image.alpha_composite(view.convert("RGBA"), overlay)
    draw_each = preview.tool in (TOOL_ROAD, TOOL_WALL, TOOL_AQUEDUCT) or len(cells) <= 80
    if draw_each:
        for tx, ty in cells:
            pts = _diamond_view_pts(
                tx, ty, zoom, cam_x, cam_y, canvas_w, canvas_h,
                screen_w=screen_w, screen_h=screen_h,
            )
            draw.polygon(pts, fill=fill, outline=outline)
    elif cells:
        from app.city_map import iso_tile_size, tile_iso_xy

        xs = [c[0] for c in cells]
        ys = [c[1] for c in cells]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        tw, th = iso_tile_size(zoom)
        n_sx, n_sy = tile_iso_xy(x0, y0, zoom=zoom)
        e_sx, e_sy = tile_iso_xy(x1, y0, zoom=zoom)
        s_sx, s_sy = tile_iso_xy(x1, y1, zoom=zoom)
        w_sx, w_sy = tile_iso_xy(x0, y1, zoom=zoom)
        quad = [
            (n_sx + tw // 2, n_sy),
            (e_sx + tw - 1, e_sy + th // 2),
            (s_sx + tw // 2, s_sy + th - 1),
            (w_sx, w_sy + th // 2),
        ]
        vquad = [
            canvas_to_view(
                px, py, cam_x, cam_y, canvas_w, canvas_h,
                screen_w=screen_w, screen_h=screen_h,
            )
            for px, py in quad
        ]
        draw.polygon(vquad, fill=fill, outline=outline)
    for tx, ty in preview.skip:
        pts = _diamond_view_pts(
            tx, ty, zoom, cam_x, cam_y, canvas_w, canvas_h,
            screen_w=screen_w, screen_h=screen_h,
        )
        draw.polygon(pts, outline=_PREVIEW_SKIP)
    return Image.alpha_composite(view.convert("RGBA"), overlay)


def _eng_skip(eng, slot: int, n: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, n)
        if got:
            return got
    return fallback


def _hud_font() -> ImageFont.ImageFont:
    return ImageFont.load_default()


def _text_size(font: ImageFont.ImageFont, text: str) -> tuple[int, int]:
    if hasattr(font, "getbbox"):
        box = font.getbbox(text)
        return max(1, box[2] - box[0]), max(1, box[3] - box[1])
    return font.getsize(text)


def hud_date_text(ctx: BootContext) -> str:
    """HUD 0x6189D: chunks 25/26 (year_raw / month) every blit — not a cached string."""
    from app.calendar import MONTHS, format_hud_date

    sim = ctx.sim
    live = format_hud_date(sim.date)
    month_i = int(sim.month)
    if not (0 <= month_i < 12) or ctx.eng is None:
        return live
    era_skip = 0 if sim.year_raw < 0 else 1
    era = _eng_skip(ctx.eng, 25, era_skip, "BC" if sim.year_raw < 0 else "AD")
    month = _eng_skip(ctx.eng, 24, month_i, MONTHS[month_i])
    if not era or not month:
        return live
    return f"{abs(int(sim.year_raw))} {era} {month}"


def hud_treasury_text(ctx: BootContext) -> str:
    return f"{int(ctx.sim.treasury)}{HUD_TREASURY_SUFFIX}"


def top_menu_layout(
    eng, font: ImageFont.ImageFont
) -> list[tuple[int, str, tuple[int, int, int, int], list[tuple[int, str]]]]:
    """File / Options / Speed / Help plus packed dropdown rows (C2.ENG)."""
    x = _MENU_X0
    rows: list[tuple[int, str, tuple[int, int, int, int], list[tuple[int, str]]]] = []
    for i, slot in enumerate(_MENU_SLOTS):
        label = _eng_skip(eng, slot, 0, _MENU_FALLBACK[i])
        tw, _th = _text_size(font, label)
        w = max(28, tw + 10)
        items = [
            (skip, _eng_skip(eng, slot, skip, fb).rstrip())
            for skip, fb in zip(_MENU_ITEM_SKIP[slot], _MENU_ITEM_FALLBACK[slot])
        ]
        rows.append((slot, label, (x, 0, w, TOP_BAR_H), items))
        x += w + _MENU_GAP
    return rows


def _dropdown_rect(
    title_rect: tuple[int, int, int, int], items: list[tuple[int, str]], font: ImageFont.ImageFont
) -> tuple[int, int, int, int]:
    tx, _ty, tw, th = title_rect
    iw = tw
    for _skip, lab in items:
        ww, _hh = _text_size(font, lab)
        iw = max(iw, ww + 16)
    return (tx, th, iw, max(1, len(items)) * _DROP_ITEM_H)


def _menu_title_at(
    layout: list[tuple[int, str, tuple[int, int, int, int], list[tuple[int, str]]]],
    x: int,
    y: int,
) -> int | None:
    if y >= TOP_BAR_H:
        return None
    for slot, _lab, rect, _items in layout:
        rx, ry, rw, rh = rect
        if rx <= x < rx + rw and ry <= y < ry + rh:
            return slot
    return None


def _menu_item_at(
    layout: list[tuple[int, str, tuple[int, int, int, int], list[tuple[int, str]]]],
    open_slot: int | None,
    x: int,
    y: int,
    font: ImageFont.ImageFont,
) -> tuple[int, int, str] | None:
    if open_slot is None:
        return None
    for slot, _lab, rect, items in layout:
        if slot != open_slot:
            continue
        dx, dy, dw, dh = _dropdown_rect(rect, items, font)
        if not (dx <= x < dx + dw and dy <= y < dy + dh):
            return None
        idx = (y - dy) // _DROP_ITEM_H
        if 0 <= idx < len(items):
            skip, lab = items[idx]
            return slot, skip, lab
        return None
    return None


def blit_int_city_minimap(
    frame: Image.Image,
    chrome: CityChrome,
    city,
    viewport: tuple | None,
    overlay_id: int = 0,
    *,
    ox: int = 0,
) -> tuple[Image.Image, tuple[int, int, int, int] | None]:
    """Scale the 80×80 map to ``MINIMAP_RECT`` (INT_CITY well above the 3×5).

    INT_CITY sprite 3 (478,368) is the stone relief, not this slot. ``chrome``
    is unused on purpose so a sibling HUD edit cannot pull dests[3] back in.
    """
    from app import city_map

    fn = getattr(city_map, "render_minimap", None)
    if fn is None:
        return frame, None
    _ = chrome
    mini = fn(city, viewport, overlay_id=overlay_id)
    mx, my, mw, mh = city_map.MINIMAP_RECT
    mx += ox
    if mini.size != (mw, mh):
        mini = mini.resize((mw, mh), Image.Resampling.NEAREST)
    out = frame.convert("RGB")
    out.paste(mini.convert("RGB"), (mx, my))
    return out, (mx, my, mw, mh)


def compose_city_hud(
    frame: Image.Image,
    ctx: BootContext,
    extra: str | None = None,
    *,
    menu_open: int | None = None,
) -> Image.Image:
    """File/Options/Speed/Help + date + Dn on the INT_CITY top bar (0x6189D)."""
    out = frame.convert("RGBA")
    fw, fh = out.size
    overlay = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _hud_font()
    layout = top_menu_layout(ctx.eng, font)
    for slot, label, rect, items in layout:
        rx, ry, rw, rh = rect
        if menu_open == slot:
            draw.rectangle((rx, ry, rx + rw - 1, rh - 1), fill=(20, 48, 40, 210))
        draw.text((rx + 4, HUD_DATE_Y), label, fill=HUD_GOLD, font=font)
        if menu_open == slot:
            dx, dy, dw, dh = _dropdown_rect(rect, items, font)
            draw.rectangle((dx, dy, dx + dw - 1, dy + dh - 1), fill=(8, 28, 24, 235))
            draw.rectangle((dx, dy, dx + dw - 1, dy + dh - 1), outline=(180, 160, 80, 255))
            for i, (_skip, lab) in enumerate(items):
                draw.text(
                    (dx + 6, dy + 2 + i * _DROP_ITEM_H),
                    lab,
                    fill=HUD_GOLD,
                    font=font,
                )
    date = hud_date_text(ctx)
    draw.text((HUD_DATE_X, HUD_DATE_Y), date, fill=HUD_GOLD, font=font)
    money = hud_treasury_text(ctx)
    fill = HUD_TREASURY_NEG if ctx.sim.treasury < 0 else HUD_GOLD
    draw.text((HUD_TREASURY_X, HUD_TREASURY_Y), money, fill=fill, font=font)
    if extra:
        extra_right = fw - SIDEBAR_W - 8
        draw.rectangle((6, fh - 28, extra_right, fh - 7), fill=(0, 0, 0, 170))
        draw.text((14, fh - 24), extra[:88], fill=(180, 220, 255, 255), font=font)
    return Image.alpha_composite(out, overlay).convert("RGB")


def _hud_lines(ctx: BootContext, *, map_mode: bool = False) -> list[str]:
    sim = ctx.sim
    if getattr(sim, "city_only", 0):
        from app.new_game import skill_name

        lines = [
            f"Caesar II — City Only  {skill_name(sim.skill)}  "
            f"treasury {sim.treasury}  {sim.date_label}",
            f"install: {ctx.game}  [{ctx.source}]",
            f"map: {ctx.city.width}x{ctx.city.height} {ctx.city.source}  "
            f"walkers=0  HISTORY=0  pid=0",
        ]
    else:
        lines = [
            "Caesar II — v0 skeleton (not a sim)",
            f"install: {ctx.game}  [{ctx.source}]",
            f"art: {ctx.image_name}   map: {ctx.city.width}x{ctx.city.height} {ctx.city.source}",
        ]
    if ctx.eng is not None and not getattr(sim, "city_only", 0):
        hit = ctx.eng.find("Caesar II - Version")
        if hit is None:
            hit = ctx.eng.find("Caesar II")
        if hit is not None:
            shown = hit[1].replace("\r", " ").replace("\n", " ")
            lines.append(f"C2.ENG[{hit[0]}]: {shown[:70]}")
    if map_mode:
        lines.append(
            "Arrasta Housing/Clear=rect, Roads=linha; "
            "Barracks/Reservoir=1 stamp (fantasma). Solta p/ carimbar. "
            "Query/nada=pan. Direito: cancela ferramenta ou Query no tile"
        )
    else:
        lines.append(
            "Esc quit   1 title   2 cityfixt   3 map   Space/T pulse   E evolve80   A raw"
        )
    return lines


def compose_frame(
    ctx: BootContext,
    extra: str | None = None,
    *,
    view: Image.Image | None = None,
    map_mode: bool = False,
) -> Image.Image:
    if view is not None:
        base = view.convert("RGBA")
        if not map_mode and base.size != (SCREEN_W, SCREEN_H):
            canvas = Image.new("RGBA", (SCREEN_W, SCREEN_H), (*BG, 255))
            canvas.paste(base, (0, 0), base)
            base = canvas
    elif map_mode:
        # Never _fit the native iso canvas (≈4640×2400) — that thumbnails
        # the whole city and looks like a zoom-out/zoom-in pop.
        base = Image.new("RGBA", (SCREEN_W, SCREEN_H), (*BG, 255))
    elif ctx.image is not None:
        base = _fit(ctx.image)
    else:
        base = Image.new("RGBA", (SCREEN_W, SCREEN_H), (*BG, 255))
    if map_mode:
        # City HUD (menu + date + Dn) is composed after INT_CITY chrome.
        if extra:
            bw, bh = base.size
            overlay = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            font = _hud_font()
            draw.rectangle(
                (6, bh - 28, bw - SIDEBAR_W - 8, bh - 7), fill=(0, 0, 0, 170)
            )
            draw.text(
                (14, bh - 24), extra[:88], fill=(180, 220, 255, 255), font=font
            )
            return Image.alpha_composite(base, overlay).convert("RGB")
        return base.convert("RGB")
    overlay = Image.new("RGBA", (SCREEN_W, SCREEN_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((6, 6, SCREEN_W - 7, 78), fill=(0, 0, 0, 170))
    font = _hud_font()
    y = 10
    for line in _hud_lines(ctx, map_mode=False):
        draw.text((14, y), line, fill=HUD_GOLD, font=font)
        y += 13
    if extra:
        draw.rectangle((6, SCREEN_H - 28, SCREEN_W - 7, SCREEN_H - 7), fill=(0, 0, 0, 170))
        draw.text((14, SCREEN_H - 24), extra[:88], fill=(180, 220, 255, 255), font=font)
    return Image.alpha_composite(base, overlay).convert("RGB")


def _scale_iso_fallback(src: Image.Image, from_zoom: int, to_zoom: int) -> Image.Image:
    """Nearest-neighbor stand-in when HOUSES2/3 PL8s are missing."""
    from app.city_map import iso_tile_size

    fw, fh = iso_tile_size(from_zoom)
    tw, th = iso_tile_size(to_zoom)
    nw = max(1, src.width * tw // fw)
    nh = max(1, src.height * th // fh)
    if (nw, nh) == src.size:
        return src
    return src.resize((nw, nh), Image.Resampling.NEAREST)


def show(ctx: BootContext, *, game: Path) -> None:
    """title_input_wait @ 0x2E7B1 stand-in: spin until Esc."""
    from app import assets, audio, city_map

    load_overlay_palette(game)
    root = tk.Tk()
    root.title("Caesar II — v0")
    root.geometry(f"{SCREEN_W}x{SCREEN_H}")
    root.minsize(SCREEN_W, SCREEN_H)
    root.resizable(True, True)
    root.configure(bg="#0c101c")

    label = tk.Label(root, borderwidth=0)
    label.pack(fill=tk.BOTH, expand=True)
    photo: ImageTk.PhotoImage | None = None
    win_w = SCREEN_W
    win_h = SCREEN_H
    _in_blit = False

    map_mode = False
    cam_x = 0
    cam_y = 0
    zoom = 0
    water_frame = 0
    river_xy: list[tuple[int, int]] = []
    pl8_sheets: dict[int, dict] = {}
    last_extra: str | None = None
    water_after: str | None = None
    sim_after: str | None = None
    terrain_cache: dict[int, Image.Image] = {}
    water_cache: dict[tuple[int, int], Image.Image] = {}
    map_cache: dict[int, Image.Image] = {}
    zoom_used_pl8: dict[int, bool] = {}
    drag: tuple[int, int, int, int] | None = None
    pending_click: tuple[int, int] | None = None
    press_on_chrome = False
    band_start: tuple[int, int] | None = None
    band_cur: tuple[int, int] | None = None
    tool: str | None = None
    pl8_zooms = assets.available_map_zooms(game)
    chrome = CityChrome.load(game)
    palette = PaletteState()
    menu_open: int | None = None
    minimap_rect: tuple[int, int, int, int] | None = None
    overlay_id = OVERLAY_GEOGRAPHY
    overlay_flyout = False
    place_dlg: PlaceInfo | None = None

    def current_canvas() -> Image.Image | None:
        return map_cache.get(zoom)

    def tile_at(vx: int, vy: int) -> tuple[int, int] | None:
        canvas = current_canvas()
        if canvas is None:
            return None
        cx, cy = view_to_canvas(
            vx, vy, cam_x, cam_y, canvas.width, canvas.height,
            screen_w=win_w, screen_h=win_h,
        )
        return screen_to_tile(cx, cy, zoom=zoom)

    def current_preview() -> DragPreview | None:
        if band_start is None or tool not in SPAN_TOOLS:
            return None
        end = band_cur or band_start
        return preview_span(
            ctx.city,
            tool,
            band_start[0],
            band_start[1],
            end[0],
            end[1],
            ctx.sim.treasury,
        )

    def blit(extra: str | None = None) -> None:
        nonlocal photo, cam_x, cam_y, last_extra, minimap_rect, _in_blit
        _in_blit = True
        try:
            _blit(extra)
        finally:
            _in_blit = False

    def _blit(extra: str | None = None) -> None:
        nonlocal photo, cam_x, cam_y, last_extra, minimap_rect
        if extra is not None:
            last_extra = extra
        ox = chrome_ox(win_w)
        view = None
        canvas = current_canvas() if map_mode else None
        if (
            canvas is None
            and map_mode
            and ctx.image is not None
            and (
                ctx.image.width > win_w or ctx.image.height > win_h
            )
        ):
            # Cache miss (flush / first zoom): keep the last iso crop at the
            # current pan, never a whole-map thumbnail.
            canvas = ctx.image
        prev = current_preview()
        if canvas is not None:
            view, cam_x, cam_y = crop_viewport(
                canvas, cam_x, cam_y, view_w=win_w, view_h=win_h
            )
            if overlay_id > 0:
                view = overlay_iso_wash(
                    view,
                    ctx.city.tiles,
                    overlay_id,
                    zoom,
                    cam_x,
                    cam_y,
                    canvas.width,
                    canvas.height,
                    view_w=win_w,
                    view_h=win_h,
                )
            if prev is not None:
                if prev.tool in STAMP_TOOLS:
                    view = overlay_stamp_ghost(
                        view,
                        prev,
                        zoom,
                        cam_x,
                        cam_y,
                        canvas.width,
                        canvas.height,
                        sheets=pl8_sheets.get(zoom),
                        screen_w=win_w,
                        screen_h=win_h,
                    )
                else:
                    view = overlay_span_preview(
                        view,
                        prev,
                        zoom,
                        cam_x,
                        cam_y,
                        canvas.width,
                        canvas.height,
                        sheets=pl8_sheets.get(zoom),
                        screen_w=win_w,
                        screen_h=win_h,
                        city=ctx.city,
                    )
        shown = extra
        if prev is not None:
            shown = f"{prev.message}  tesouro {ctx.sim.treasury}"
        if map_mode:
            frame = compose_frame(ctx, None, view=view, map_mode=True)
            frame = chrome.blit(
                frame,
                selected=action_for_tool(tool),
                speed=speed_action(ctx.sim),
                ox=ox,
            )
            canv = current_canvas()
            vp = (
                (cam_x, cam_y, zoom, canv.width, canv.height, win_w, win_h)
                if canv is not None
                else None
            )
            frame, minimap_rect = blit_int_city_minimap(
                frame, chrome, ctx.city, vp, overlay_id=overlay_id, ox=ox
            )
            frame = blit_overlay_chrome(
                frame,
                overlay_id,
                flyout_open=overlay_flyout,
                eng=ctx.eng,
                ox=ox,
            )
            if place_dlg is not None:
                frame = blit_place_dialog(frame, place_dlg)
            frame = compose_city_hud(frame, ctx, shown, menu_open=menu_open)
            frame = palette.blit(frame, selected=tool, ox=ox)
        else:
            frame = compose_frame(ctx, shown, view=view, map_mode=False)
        photo = ImageTk.PhotoImage(frame)
        label.configure(image=photo)
        label.image = photo  # type: ignore[attr-defined]

    def map_status(n_walkers: int, sheets: dict[str, list] | None = None) -> str:
        used = zoom_used_pl8.get(zoom, False)
        if used:
            how = f"PL8 zoom {zoom}"
        else:
            how = f"scale zoom {zoom}"
        names = "+".join(sheets) if sheets else "cached"
        tw, th = city_map.iso_tile_size(zoom)
        return (
            f"mapa {ctx.city.source}  zoom={zoom} ({tw}x{th} {how})  "
            f"pan={cam_x},{cam_y}  walkers={n_walkers}  "
            f"{overlay_name(overlay_id, ctx.eng)}  "
            f"água {water_frame}/{WATER_FRAMES} {WATER_FRAME_MS}ms  ({names})"
        )

    def paint_walkers(terrain: Image.Image, at_zoom: int) -> Image.Image:
        from app.walkers import overlay_walkers

        if not ctx.walkers:
            return terrain
        try:
            return overlay_walkers(terrain.copy(), ctx.walkers, game, zoom=at_zoom)
        except (OSError, ValueError):
            return terrain

    def remember_rivers() -> None:
        nonlocal river_xy
        river_xy = city_map.water_anim_tile_xy(ctx.city)

    def ensure_map(at_zoom: int) -> Image.Image:
        if at_zoom in map_cache:
            return map_cache[at_zoom]
        use_pl8 = at_zoom in pl8_zooms
        zoom_used_pl8[at_zoom] = use_pl8
        remember_rivers()
        if use_pl8:
            if at_zoom not in terrain_cache:
                sheets = assets.load_city_map_sheets(game, zoom=at_zoom)
                pl8_sheets[at_zoom] = sheets
                terrain_cache[at_zoom] = city_map.render_iso(
                    ctx.city,
                    sheets.get("CITYFIXT"),
                    sheets=sheets or None,
                    zoom=at_zoom,
                    water_frame=water_frame,
                )
                water_cache[(at_zoom, water_frame)] = terrain_cache[at_zoom]
                ctx.n_sprites = sum(len(v) for v in sheets.values())
            terrain = terrain_cache[at_zoom]
            painted = paint_walkers(terrain, at_zoom)
        elif at_zoom == 0:
            terrain_cache[0] = city_map.render_iso(
                ctx.city, zoom=0, water_frame=water_frame
            )
            water_cache[(0, water_frame)] = terrain_cache[0]
            painted = paint_walkers(terrain_cache[0], 0)
            zoom_used_pl8[0] = False
        else:
            base = ensure_map(0)
            painted = _scale_iso_fallback(base, 0, at_zoom)
            zoom_used_pl8[at_zoom] = False
        map_cache[at_zoom] = painted
        return painted

    def center_camera(canvas: Image.Image) -> None:
        nonlocal cam_x, cam_y
        cam_x = max(0, (canvas.width - win_w) // 2)
        cam_y = max(0, (canvas.height - win_h) // 2)

    def retain_center(old: Image.Image | None, new: Image.Image) -> None:
        nonlocal cam_x, cam_y
        if old is None or old.width < 1 or old.height < 1:
            center_camera(new)
            return
        fx = (cam_x + win_w / 2) / old.width
        fy = (cam_y + win_h / 2) / old.height
        cam_x = int(fx * new.width - win_w / 2)
        cam_y = int(fy * new.height - win_h / 2)

    def show_city_map(*, reset_cam: bool = False) -> None:
        nonlocal map_mode
        from app.walkers import drawable_walkers

        map_mode = True
        n_walkers = len(drawable_walkers(ctx.walkers))
        old = current_canvas()
        canvas = ensure_map(zoom)
        ctx.image = canvas
        ctx.image_name = f"map:{ctx.city.source}"
        if reset_cam or old is None:
            center_camera(canvas)
        blit(map_status(n_walkers, None if zoom in map_cache else None))

    def _refresh_after_sim(*, houses_changed: bool) -> None:
        map_cache.clear()
        if houses_changed:
            terrain_cache.clear()
            water_cache.clear()
        remember_rivers()
        if not map_mode:
            show_city_map(reset_cam=True)
        else:
            canvas = ensure_map(zoom)
            ctx.image = canvas

    def patch_water() -> bool:
        if zoom not in pl8_zooms or not river_xy:
            return False
        cached = water_cache.get((zoom, water_frame))
        if cached is not None:
            terrain_cache[zoom] = cached
            map_cache[zoom] = paint_walkers(cached, zoom)
            return True
        source = terrain_cache.get(zoom)
        sheets = pl8_sheets.get(zoom)
        cityfixt = sheets.get("CITYFIXT") if sheets else None
        if source is None or cityfixt is None:
            return False
        dest = source.copy()
        n = city_map.blit_water_tiles(
            dest,
            ctx.city,
            cityfixt,
            water_frame,
            zoom=zoom,
            cells=river_xy,
            sheets=sheets,
        )
        if n <= 0:
            return False
        water_cache[(zoom, water_frame)] = dest
        terrain_cache[zoom] = dest
        map_cache[zoom] = paint_walkers(dest, zoom)
        return True

    def on_water() -> None:
        """Host interior water cycle (250 ms). +0 / banks stay locked."""
        nonlocal water_frame, water_after
        water_after = root.after(WATER_FRAME_MS, on_water)
        if not map_mode or not river_xy:
            return
        water_frame = (water_frame + 1) % WATER_FRAMES
        if patch_water():
            from app.walkers import drawable_walkers

            blit(map_status(len(drawable_walkers(ctx.walkers))))

    def sim_step() -> None:
        """Space / T — one city_sim_phase slot then walkers_tick. Camera keys unchanged."""
        from app.sim import on_sim_step
        from app.walkers import drawable_walkers

        n = on_sim_step(ctx.city, ctx.walkers, ctx.sim)
        ph, w = n.phase, n.walkers
        _refresh_after_sim(houses_changed=ph.houses_changed > 0)
        from app.sim_log import last_line

        tail = last_line()
        blit(
            f"slot {ph.phase:#x} {ph.name}  houses +{ph.houses_up}/-{ph.houses_down} "
            f"merge={ph.houses_merge}  {ph.date_label}  "
            f"moved={w.stepped} frames={w.animated} live={w.live}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
            + (f"  | {tail[-88:]}" if tail else "")
        )

    def month_step() -> None:
        """M — remaining slots this cycle (paint/emit included), then month++."""
        from app.calendar import format_hud_date
        from app.sim import on_month_step
        from app.walkers import drawable_walkers

        n = on_month_step(ctx.city, ctx.walkers, ctx.sim)
        ph, w = n.phase, n.walkers
        date = format_hud_date(ctx.sim.date)
        _refresh_after_sim(houses_changed=ph.houses_changed > 0)
        from app.sim_log import last_line

        tail = last_line()
        blit(
            f"M {ph.name}  houses +{ph.houses_up}/-{ph.houses_down} "
            f"merge={ph.houses_merge}  {date}  "
            f"moved={w.stepped} live={w.live}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
            + (f"  | {tail[-88:]}" if tail else "")
        )

    def apply_speed(action: str) -> None:
        """INT_CITY play / faster / pause + Speed menu. Original starts unpaused."""
        sim = ctx.sim
        if action == "speed_pause":
            sim.paused = True
            sim.catchup = 0
        elif action == "speed_play":
            sim.paused = False
            sim.catchup = 0
        elif action == "speed_fast":
            sim.paused = False
            sim.catchup = 1
        else:
            return
        from app.walkers import drawable_walkers

        blit(
            f"{speed_action(sim)}  {sim.date_label}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
        )

    def clock_step() -> None:
        """sim_tick_due 0x3E4B9 — auto-advance when Speed is not paused."""
        nonlocal sim_after
        sim_after = root.after(TICK_MS, clock_step)
        if not map_mode:
            return
        from app.sim import on_clock_step, sim_tick_due
        from app.walkers import drawable_walkers

        n = sim_tick_due(ctx.sim, TICK_MS)
        if n <= 0:
            return
        result = on_clock_step(ctx.city, ctx.walkers, ctx.sim, pulses=n)
        ph, w = result.phase, result.walkers
        if (
            ph.houses_changed
            or ph.walkers_spawned
            or w.stepped
            or w.animated
            or w.live
        ):
            _refresh_after_sim(houses_changed=ph.houses_changed > 0)
        from app.sim_log import last_line

        tail = last_line()
        blit(
            f"{speed_action(ctx.sim)}  slot {ph.phase:#x}  "
            f"houses +{ph.houses_up}/-{ph.houses_down}  {ph.date_label}  "
            f"moved={w.stepped}  drawn={len(drawable_walkers(ctx.walkers))}"
            + (f"  | {tail[-88:]}" if tail else "")
        )

    def evolve_pass() -> None:
        """E — host-only: all 80 evolve rows. Not one EXE pulse."""
        from app.city_sim import evolve_all_rows
        from app.walkers import drawable_walkers

        up, down, merge = evolve_all_rows(
            ctx.city.tiles, decay=ctx.sim.wrap3 == 0
        )
        _refresh_after_sim(houses_changed=(up + down) > 0)
        blit(
            f"E evolve80  houses +{up}/-{down} merge={merge}  "
            f"phase still {ctx.sim.phase:#x}  {ctx.sim.date_label}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
        )

    def set_zoom(new_zoom: int) -> None:
        nonlocal zoom
        from app.city_map import clamp_zoom
        from app.walkers import drawable_walkers

        new_zoom = clamp_zoom(new_zoom)
        if new_zoom == zoom and zoom in map_cache:
            blit(map_status(len(drawable_walkers(ctx.walkers))))
            return
        old = current_canvas()
        zoom = new_zoom
        canvas = ensure_map(zoom)
        ctx.image = canvas
        retain_center(old, canvas)
        blit(map_status(len(drawable_walkers(ctx.walkers))))

    def pan(dx: int, dy: int) -> None:
        nonlocal cam_x, cam_y
        from app.walkers import drawable_walkers

        if not map_mode or current_canvas() is None:
            return
        cam_x += dx
        cam_y += dy
        blit(map_status(len(drawable_walkers(ctx.walkers))))

    def use_pl8(name: str, first_only: bool) -> None:
        nonlocal map_mode
        map_mode = False
        try:
            img, path, n = assets.load_pl8_image(game, name, first_only=first_only)
        except (OSError, ValueError) as exc:
            blit(str(exc))
            return
        ctx.image = img
        ctx.image_name = path.name
        ctx.n_sprites = n
        blit(f"loaded {path.name}")

    def on_key(event: tk.Event) -> None:  # type: ignore[type-arg]
        key = event.keysym.lower()
        ch = (getattr(event, "char", "") or "").lower()
        step = PAN_STEP[city_map.clamp_zoom(zoom)]
        if key in {"escape", "q"}:
            on_close()
        elif key in {"1"}:
            use_pl8("backgrnd.pl8", first_only=True)
        elif key in {"2"}:
            use_pl8("CITYFIXT.PL8", first_only=True)
        elif key in {"3"}:
            show_city_map(reset_cam=not map_mode)
        elif key in {"space", "t"}:
            sim_step()
        elif key in {"m"} or ch == "m":
            month_step()
        elif key in {"e"}:
            evolve_pass()
        elif key in {"a"}:
            blit(audio.play_raw_preview(game))
        elif not map_mode:
            return
        elif key in {"left"}:
            pan(-step, 0)
        elif key in {"right"}:
            pan(step, 0)
        elif key in {"up"}:
            pan(0, -step)
        elif key in {"down"}:
            pan(0, step)
        elif key in {"plus", "equal", "kp_add", "bracketright"}:
            set_zoom(zoom - 1)
        elif key in {"minus", "underscore", "kp_subtract", "bracketleft"}:
            set_zoom(zoom + 1)
        elif key in {"z"}:
            set_zoom((zoom + 1) % 3)
        elif key in {"home"}:
            canvas = current_canvas()
            if canvas is not None:
                center_camera(canvas)
                from app.walkers import drawable_walkers

                blit(map_status(len(drawable_walkers(ctx.walkers))))

    def invalidate_iso(cells: list[tuple[int, int]], *, flush: bool = False) -> None:
        """Patch cached iso canvases for touched tiles; drop stale water frames.

        Place/clear must redraw every diamond the wipe covered (painter
        order). Flush drops the iso cache and rebuilds the whole city
        map — not chrome / minimap — so a tall-sprite leftover never
        leaves a black hole.
        """
        if flush:
            terrain_cache.clear()
            map_cache.clear()
            water_cache.clear()
            canvas = ensure_map(zoom)
            ctx.image = canvas
            remember_rivers()
            return
        if not cells:
            return
        unique = list(dict.fromkeys(cells))
        for z in list(terrain_cache):
            if z not in pl8_zooms:
                terrain_cache.pop(z, None)
                map_cache.pop(z, None)
                continue
            sheets = pl8_sheets.get(z)
            cityfixt = sheets.get("CITYFIXT") if sheets else None
            src = terrain_cache.get(z)
            if src is None:
                continue
            dest = src.copy()
            city_map.blit_dirty_tiles(
                dest,
                ctx.city,
                unique,
                zoom=z,
                water_frame=water_frame,
                cityfixt=cityfixt,
                sheets=sheets,
            )
            terrain_cache[z] = dest
            map_cache[z] = paint_walkers(dest, z)
        for key in list(water_cache):
            water_cache.pop(key, None)
        for z, img in terrain_cache.items():
            if z in pl8_zooms:
                water_cache[(z, water_frame)] = img
        for z in list(map_cache):
            if z not in pl8_zooms:
                map_cache.pop(z, None)
        remember_rivers()

    def open_place(x: int, y: int) -> None:
        nonlocal place_dlg
        place_dlg = query_place(ctx.city, x, y)
        blit(f"Query {place_dlg.name}  tesouro {ctx.sim.treasury}")

    def place_at(vx: int, vy: int) -> None:
        nonlocal tool, place_dlg
        canvas = current_canvas()
        if canvas is None or tool is None:
            return
        cx, cy = view_to_canvas(
            vx, vy, cam_x, cam_y, canvas.width, canvas.height,
            screen_w=win_w, screen_h=win_h,
        )
        cell = screen_to_tile(cx, cy, zoom=zoom)
        if cell is None:
            blit("clique fora do mapa")
            return
        result = try_place(ctx.city, cell[0], cell[1], tool, ctx.sim)
        if result.query:
            open_place(cell[0], cell[1])
            return
        place_dlg = None
        if result.ok and (result.dirty or result.flush_iso):
            invalidate_iso(result.dirty, flush=result.flush_iso)
            ctx.image = current_canvas()
        blit(result.message + f"  tesouro {ctx.sim.treasury}")

    def select_chrome(hit) -> None:
        nonlocal tool, overlay_flyout, overlay_id, place_dlg
        action = hit.action
        if action.startswith("speed_"):
            overlay_flyout = False
            apply_speed(action)
            return
        if action == "overlay_menu":
            overlay_flyout = not overlay_flyout
            palette.close()
            place_dlg = None
            blit(f"Overlay: {overlay_name(overlay_id, ctx.eng)}")
            return
        if action == "zoom_in":
            overlay_flyout = False
            set_zoom(zoom - 1)
            return
        if action == "zoom_out":
            overlay_flyout = False
            set_zoom(zoom + 1)
            return
        overlay_flyout = False
        picked = palette.click_grid(action, hit.rect)
        if picked.tool is not None:
            tool = picked.tool
            place_dlg = None
        blit(f"{picked.message}  tesouro {ctx.sim.treasury}")

    def pick_overlay(idx: int) -> None:
        nonlocal overlay_id, overlay_flyout, tool, place_dlg
        overlay_flyout = False
        if idx == OVERLAY_CANCEL:
            # EXE 0x329EF: cancel build tool slots. Does not reset overlay.
            tool = None
            place_dlg = None
            blit(f"ferramenta cancelada  tesouro {ctx.sim.treasury}")
            return
        overlay_id = idx
        hint = overlay_help(idx, ctx.eng)
        blit(f"{overlay_name(idx, ctx.eng)} — {hint}")

    def _minimap_click(x: int, y: int) -> bool:
        nonlocal cam_x, cam_y
        from app import city_map

        hit = minimap_rect if minimap_rect is not None else city_map.MINIMAP_RECT
        mx, my, mw, mh = hit
        if not (mx <= x < mx + mw and my <= y < my + mh):
            return False
        canv = current_canvas()
        if canv is None:
            return True
        cam = city_map.minimap_click_pan(
            x,
            y,
            zoom,
            canv.width,
            canv.height,
            view_w=max(1, win_w - SIDEBAR_W),
            view_h=max(1, win_h - TOP_BAR_H),
            screen_w=win_w,
            screen_h=win_h,
            minimap=hit,
        )
        if cam is None:
            return False
        cam_x, cam_y = cam
        from app.walkers import drawable_walkers

        blit(map_status(len(drawable_walkers(ctx.walkers))))
        return True

    def _menu_click(x: int, y: int) -> bool:
        nonlocal menu_open
        font = _hud_font()
        layout = top_menu_layout(ctx.eng, font)
        item = _menu_item_at(layout, menu_open, x, y, font)
        if item is not None:
            slot, skip, lab = item
            menu_open = None
            if slot == 0 and skip == 4:
                on_close()
                return True
            if slot == 0 and skip == 3:
                blit(f"{lab} — ainda não (o host não grava .SAV)")
                return True
            if slot == 2 and skip == 3:
                apply_speed("speed_play" if ctx.sim.paused else "speed_pause")
                return True
            if slot == 2 and skip == 1:
                apply_speed("speed_play")
                return True
            blit(f"{lab} — ainda não")
            return True
        title = _menu_title_at(layout, x, y)
        if title is not None:
            menu_open = None if menu_open == title else title
            blit(last_extra)
            return True
        if menu_open is not None:
            menu_open = None
            blit(last_extra)
            return True
        return False

    def on_press(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal drag, pending_click, press_on_chrome, cam_x, cam_y
        nonlocal band_start, band_cur
        if not map_mode or current_canvas() is None:
            return
        if event.y < TOP_BAR_H or (
            menu_open is not None
            and _menu_item_at(
                top_menu_layout(ctx.eng, _hud_font()),
                menu_open,
                event.x,
                event.y,
                _hud_font(),
            )
            is not None
        ):
            pending_click = (event.x, event.y)
            drag = None
            press_on_chrome = True
            return
        ox = chrome_ox(win_w)
        if (
            chrome.hit_test(event.x, event.y, ox=ox) is not None
            or palette.covers(event.x, event.y, ox=ox)
            or (overlay_flyout and flyout_item_at(event.x, event.y, ox) is not None)
            or (place_dlg is not None and place_dialog_contains(event.x, event.y))
        ):
            pending_click = (event.x, event.y)
            drag = None
            press_on_chrome = True
            return
        from app.city_map import minimap_well_contains

        if minimap_rect is not None:
            mx, my, mw, mh = minimap_rect
            on_mini = mx <= event.x < mx + mw and my <= event.y < my + mh
        else:
            on_mini = minimap_well_contains(event.x - chrome_ox(win_w), event.y)
        if on_mini:
            _minimap_click(event.x, event.y)
            press_on_chrome = True
            pending_click = None
            drag = None
            return
        press_on_chrome = False
        pending_click = (event.x, event.y)
        if tool in STAMP_TOOLS:
            drag = None
            hit = tile_at(event.x, event.y)
            if hit is not None:
                band_start = hit
                band_cur = hit
                pending_click = None
                prev = current_preview()
                extra = (
                    f"{prev.message}  tesouro {ctx.sim.treasury}"
                    if prev is not None
                    else None
                )
                blit(extra)
            return
        if tool in SPAN_TOOLS:
            drag = None
        else:
            drag = (event.x, event.y, cam_x, cam_y)

    def on_motion(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal cam_x, cam_y, pending_click, band_start, band_cur
        if not map_mode or press_on_chrome:
            return
        if tool in SPAN_TOOLS and (pending_click is not None or band_start is not None):
            if band_start is None:
                if pending_click is None:
                    return
                if abs(event.x - pending_click[0]) + abs(event.y - pending_click[1]) < CLICK_DRAG_PX:
                    return
                start = tile_at(pending_click[0], pending_click[1])
                pending_click = None
                if start is None:
                    return
                band_start = start
            hit = tile_at(event.x, event.y)
            if hit is not None:
                band_cur = hit
            prev = current_preview()
            extra = (
                f"{prev.message}  tesouro {ctx.sim.treasury}"
                if prev is not None
                else None
            )
            blit(extra)
            return
        if drag is None:
            return
        sx, sy, ox, oy = drag
        if pending_click is not None:
            if abs(event.x - sx) + abs(event.y - sy) < CLICK_DRAG_PX:
                return
            pending_click = None
        cam_x = ox - (event.x - sx)
        cam_y = oy - (event.y - sy)
        from app.walkers import drawable_walkers

        blit(map_status(len(drawable_walkers(ctx.walkers))))

    def on_release(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal drag, pending_click, press_on_chrome, band_start, band_cur, tool
        nonlocal overlay_flyout, place_dlg
        click = pending_click
        start = band_start
        end = band_cur or band_start
        was_chrome = press_on_chrome
        pending_click = None
        drag = None
        band_start = None
        band_cur = None
        press_on_chrome = False
        if not map_mode:
            return
        if (
            start is not None
            and end is not None
            and tool in SPAN_TOOLS
            and not was_chrome
        ):
            result = try_place_span(
                ctx.city, start[0], start[1], end[0], end[1], tool, ctx.sim
            )
            if result.ok and (result.dirty or result.flush_iso):
                invalidate_iso(result.dirty, flush=result.flush_iso)
                ctx.image = current_canvas()
            blit(result.message + f"  tesouro {ctx.sim.treasury}")
            return
        if click is None:
            return
        if abs(event.x - click[0]) + abs(event.y - click[1]) >= CLICK_DRAG_PX:
            return
        if _menu_click(event.x, event.y):
            return
        ox = chrome_ox(win_w)
        if overlay_flyout:
            picked_ov = flyout_item_at(event.x, event.y, ox)
            if picked_ov is not None:
                pick_overlay(picked_ov)
                return
            fx, fy, fw, fh = flyout_rect(ox)
            if not (fx <= event.x < fx + fw and fy <= event.y < fy + fh):
                if not overlay_well_contains(event.x, event.y, ox):
                    overlay_flyout = False
        fly = palette.hit_test(event.x, event.y, ox=ox)
        if fly is not None:
            picked = palette.click_item(fly.key)
            if picked.tool is not None:
                tool = picked.tool
            blit(f"{picked.message}  tesouro {ctx.sim.treasury}")
            return
        if place_dlg is not None and place_dialog_contains(event.x, event.y):
            return
        hit = chrome.hit_test(event.x, event.y, ox=ox)
        if hit is not None:
            # Zoom lives on the sidebar 3×5. A map-well click must never
            # change PL8 zoom even if a hitbox is ever remapped too far left.
            if hit.action in {"zoom_in", "zoom_out"} and not chrome.covers(
                event.x, event.y, ox=ox
            ):
                hit = None
            else:
                select_chrome(hit)
                return
        if was_chrome:
            return
        if tool is not None and not chrome.covers(event.x, event.y, ox=ox):
            place_at(event.x, event.y)
            return
        if place_dlg is not None:
            place_dlg = None
            blit(last_extra)

    def on_right(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal tool, band_start, band_cur, pending_click, drag, menu_open
        nonlocal overlay_flyout, place_dlg
        if not map_mode:
            return
        aborted = band_start is not None
        band_start = None
        band_cur = None
        pending_click = None
        drag = None
        menu_open = None
        overlay_flyout = False
        palette.close()
        # EXE 0x329EF / overlay Cancel: right-click drops the build tool.
        # Query / no tool: inspect the tile (same as Query left-click).
        if aborted:
            tool = None
            place_dlg = None
            blit(f"arrasto cancelado  tesouro {ctx.sim.treasury}")
            return
        building = tool is not None and tool != TOOL_QUERY
        if building:
            tool = None
            place_dlg = None
            blit(f"ferramenta cancelada  tesouro {ctx.sim.treasury}")
            return
        ox = chrome_ox(win_w)
        if chrome.covers(event.x, event.y, ox=ox) or overlay_well_contains(
            event.x, event.y, ox
        ):
            tool = None
            place_dlg = None
            blit(f"ferramenta cancelada  tesouro {ctx.sim.treasury}")
            return
        hit = tile_at(event.x, event.y)
        if hit is None:
            tool = None
            place_dlg = None
            blit(f"ferramenta cancelada  tesouro {ctx.sim.treasury}")
            return
        open_place(hit[0], hit[1])

    def on_wheel(event: tk.Event) -> None:  # type: ignore[type-arg]
        if not map_mode:
            return
        delta = getattr(event, "delta", 0)
        if delta == 0:
            num = getattr(event, "num", 0)
            if num == 4:
                delta = 120
            elif num == 5:
                delta = -120
        if delta > 0:
            set_zoom(zoom - 1)
        elif delta < 0:
            set_zoom(zoom + 1)

    def on_resize(event: tk.Event) -> None:  # type: ignore[type-arg]
        """Larger window → larger iso clip. Same PL8 zoom, same pan."""
        nonlocal win_w, win_h
        if _in_blit or event.widget is not root:
            return
        nw = max(SCREEN_W, int(event.width))
        nh = max(SCREEN_H, int(event.height))
        if nw == win_w and nh == win_h:
            return
        win_w, win_h = nw, nh
        blit(last_extra)

    root.bind("<Key>", on_key)
    root.bind("<Configure>", on_resize)
    label.bind("<Button-1>", on_press)
    label.bind("<B1-Motion>", on_motion)
    label.bind("<ButtonRelease-1>", on_release)
    label.bind("<Button-3>", on_right)
    label.bind("<MouseWheel>", on_wheel)
    label.bind("<Button-4>", on_wheel)
    label.bind("<Button-5>", on_wheel)
    def on_close() -> None:
        if water_after is not None:
            root.after_cancel(water_after)
        if sim_after is not None:
            root.after_cancel(sim_after)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    if ctx.start_in_map:
        root.title("Caesar II — City Only")
        show_city_map(reset_cam=True)
    else:
        blit(ctx.audio_status)
    water_after = root.after(WATER_FRAME_MS, on_water)
    sim_after = root.after(TICK_MS, clock_step)
    root.mainloop()
