"""640×480 host window (video_init @ 0x28341 stand-in). Pillow blit via tkinter.

Play path paints visible iso diamonds into the camera well — never the
~4640×2400 world bitmap. Walker / water ticks dirty that well only
(``video_blit_dirty`` 0x29849 stand-in). City Only keys follow
C2MANUAL.DOC p.48 (P pause, C census, A faster, Space cancel build,
F/F2 forum, F1 city, F3 province, F4/F5 load/save, 1/2/3 zoom, Esc
dismiss). Off-map debug: 1 title, 2 CITYFIXT, 3 enter map, Space/T sim
slot, A audio. Arrow keys pan. Housing / Roads / Clear / Aqueduct
rubber-band on drag. +/- zoom 0/1/2.
"""

from __future__ import annotations

import time
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
from app.forum import (
    KIND_CHROME,
    ForumState,
    blit_forum,
    blit_pause_square,
    click_forum,
    is_forum_building,
    open_forum,
)
from app.menus import (
    FILE_LOAD,
    FILE_NEW,
    FILE_QUIT,
    FILE_SAVE,
    HELP_TOPIC_GAME,
    HELP_TOPIC_HINTS,
    HELP_TOPIC_HISTORY,
    HELP_TOPIC_ICONS,
    HLP_ABOUT,
    HLP_GAME,
    HLP_HINTS,
    HLP_HISTORY,
    HLP_ICONS,
    HostOptions,
    MenuReport,
    OPT_ANIM,
    OPT_CENSUS,
    OPT_MUSIC,
    OPT_SOUND,
    OPT_YEAR,
    SLOT_FILE,
    SLOT_HELP,
    SLOT_OPTIONS,
    SLOT_SPEED,
    SPD_GAME,
    SPD_PAUSE,
    SPD_SCROLL,
    about_report,
    advisor_contains,
    blit_advisor_dialog,
    blit_menu_report,
    census_report,
    cycle_scroll,
    decorate_item,
    help_topic_excerpt,
    next_game_speed,
    on_off,
    report_contains,
    report_line_at,
    toggle_pause_action,
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
    place_dialog_close_contains,
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
# Credit at most one Play interval if a hitch blocked tk (render_iso ~170 ms).
_MAX_CLOCK_DT_MS = 250
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
    eng,
    font: ImageFont.ImageFont,
    *,
    options: HostOptions | None = None,
    sim=None,
) -> list[tuple[int, str, tuple[int, int, int, int], list[tuple[int, str]]]]:
    """File / Options / Speed / Help plus packed dropdown rows (C2.ENG)."""
    x = _MENU_X0
    rows: list[tuple[int, str, tuple[int, int, int, int], list[tuple[int, str]]]] = []
    for i, slot in enumerate(_MENU_SLOTS):
        label = _eng_skip(eng, slot, 0, _MENU_FALLBACK[i])
        tw, _th = _text_size(font, label)
        w = max(28, tw + 10)
        items = [
            (
                skip,
                decorate_item(
                    slot,
                    skip,
                    _eng_skip(eng, slot, skip, fb).rstrip(),
                    eng=eng,
                    options=options,
                    sim=sim,
                ),
            )
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
    options: HostOptions | None = None,
    report: MenuReport | None = None,
) -> Image.Image:
    """File/Options/Speed/Help + date + Dn on the INT_CITY top bar (0x6189D)."""
    out = frame.convert("RGBA")
    fw, fh = out.size
    overlay = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _hud_font()
    layout = top_menu_layout(ctx.eng, font, options=options, sim=ctx.sim)
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
    hud = Image.alpha_composite(out, overlay).convert("RGB")
    if report is not None:
        hud = blit_menu_report(hud, report)
    return hud


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

    host = tk.Canvas(
        root, highlightthickness=0, bd=0, bg="#0c101c",
        width=SCREEN_W, height=SCREEN_H,
    )
    host.pack(fill=tk.BOTH, expand=True)
    ui_item = host.create_image(0, 0, anchor="nw")
    well_item = host.create_image(0, TOP_BAR_H, anchor="nw")
    front_item = host.create_image(0, 0, anchor="nw")
    well_photo: ImageTk.PhotoImage | None = None
    ui_photo: ImageTk.PhotoImage | None = None
    front_photo: ImageTk.PhotoImage | None = None
    win_w = SCREEN_W
    win_h = SCREEN_H
    _in_blit = False

    map_mode = False
    map_ready = False
    cam_x = 0
    cam_y = 0
    zoom = 0
    water_frame = 0
    river_xy: list[tuple[int, int]] = []
    pl8_sheets: dict[int, dict] = {}
    last_extra: str | None = None
    water_after: str | None = None
    sim_after: str | None = None
    last_clock_mono = time.monotonic()
    view_terrain: Image.Image | None = None
    view_terrain_key: tuple | None = None
    ui_cache: Image.Image | None = None
    ui_cache_key: tuple | None = None
    ltlmen_cache: dict[int, list] = {}
    live_base: Image.Image | None = None
    live_key: tuple | None = None
    zoom_used_pl8: dict[int, bool] = {}
    _prof_ms: list[float] = []
    _prof_last = 0.0
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
    advisor_dlg = None
    advisor_clip = None
    advisor_video_after = None
    forum_state: ForumState | None = None
    menu_report: MenuReport | None = None
    load_picks: list[Path] | None = None
    options = HostOptions(sound=bool(getattr(ctx, "play_audio", True)))
    city_skill = int(ctx.sim.skill) if getattr(ctx.sim, "city_only", 0) else 2

    def world_wh() -> tuple[int, int]:
        return city_map.iso_canvas_size(zoom)

    def map_is_ready() -> bool:
        return map_ready

    def tile_at(vx: int, vy: int) -> tuple[int, int] | None:
        if not map_ready:
            return None
        ww, wh = world_wh()
        cx, cy = view_to_canvas(
            vx, vy, cam_x, cam_y, ww, wh,
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
        nonlocal cam_x, cam_y, last_extra, minimap_rect, _in_blit
        _in_blit = True
        try:
            _blit(extra)
        finally:
            _in_blit = False

    def _well_box() -> tuple[int, int, int, int]:
        ox = chrome_ox(win_w)
        return (0, TOP_BAR_H, SIDEBAR_X + ox, win_h)

    def _set_layer(item: int, img: Image.Image | None, which: str) -> None:
        nonlocal well_photo, ui_photo, front_photo
        if img is None:
            host.itemconfig(item, image="")
            if which == "well":
                well_photo = None
            elif which == "ui":
                ui_photo = None
            else:
                front_photo = None
            return
        photo = ImageTk.PhotoImage(img)
        host.itemconfig(item, image=photo)
        if which == "well":
            well_photo = photo
        elif which == "ui":
            ui_photo = photo
        else:
            front_photo = photo

    def _blit(extra: str | None = None) -> None:
        nonlocal cam_x, cam_y, last_extra, minimap_rect
        nonlocal ui_cache, ui_cache_key
        t0 = time.perf_counter()
        if extra is not None:
            last_extra = extra
        ox = chrome_ox(win_w)
        shown = extra if extra is not None else last_extra
        prev = current_preview()
        if prev is not None:
            shown = f"{prev.message}  tesouro {ctx.sim.treasury}"
        if forum_state is not None:
            frame = blit_forum((win_w, win_h), forum_state, ctx.sim, eng=ctx.eng)
            frame = compose_city_hud(
                frame,
                ctx,
                shown,
                menu_open=menu_open,
                options=options,
                report=menu_report,
            )
            _set_layer(well_item, None, "well")
            _set_layer(front_item, None, "front")
            _set_layer(ui_item, frame.convert("RGB"), "ui")
            _prof_note(t0)
            return
        if not map_mode:
            frame = compose_frame(ctx, shown, view=None, map_mode=False)
            _set_layer(well_item, None, "well")
            _set_layer(front_item, None, "front")
            _set_layer(ui_item, frame.convert("RGB"), "ui")
            _prof_note(t0)
            return
        ww, wh = world_wh()
        terrain, cam_x, cam_y = _ensure_view()
        view = _paint_live_view(terrain, cam_x, cam_y)
        if overlay_id > 0:
            view = overlay_iso_wash(
                view,
                ctx.city.tiles,
                overlay_id,
                zoom,
                cam_x,
                cam_y,
                ww,
                wh,
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
                    ww,
                    wh,
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
                    ww,
                    wh,
                    sheets=pl8_sheets.get(zoom),
                    screen_w=win_w,
                    screen_h=win_h,
                    city=ctx.city,
                )
        build_flyout = palette.open is not None
        overlays = (
            menu_open is not None
            or menu_report is not None
            or place_dlg is not None
            or advisor_dlg is not None
            or overlay_flyout
            or ctx.sim.paused
            or prev is not None
        )
        ui_key = (
            win_w,
            win_h,
            ox,
            overlay_id,
            tool,
            speed_action(ctx.sim),
            ctx.sim.date_label,
            int(ctx.sim.treasury),
            zoom,
            cam_x,
            cam_y,
            None if advisor_dlg is None else advisor_dlg.key,
        )
        if ui_cache is None or ui_cache_key != ui_key:
            frame = Image.new("RGB", (win_w, win_h), BG)
            frame = chrome.blit(
                frame,
                selected=action_for_tool(tool),
                speed=speed_action(ctx.sim),
                ox=ox,
            )
            vp = (cam_x, cam_y, zoom, ww, wh, win_w, win_h)
            frame, minimap_rect = blit_int_city_minimap(
                frame, chrome, ctx.city, vp, overlay_id=overlay_id, ox=ox
            )
            frame = blit_overlay_chrome(
                frame,
                overlay_id,
                flyout_open=False,
                eng=ctx.eng,
                ox=ox,
            )
            frame = compose_city_hud(
                frame,
                ctx,
                None,
                menu_open=None,
                options=options,
                report=None,
            )
            ui_cache = frame.convert("RGB")
            ui_cache_key = ui_key
            _set_layer(ui_item, ui_cache, "ui")
        palette.sync_unlocks(ctx.sim)
        wx0, wy0, wx1, wy1 = _well_box()
        well = view.convert("RGB").crop((wx0, wy0, wx1, wy1))
        if shown:
            draw = ImageDraw.Draw(well)
            ey = max(0, win_h - 28 - wy0)
            draw.rectangle((6, ey, well.width - 8, ey + 21), fill=(0, 0, 0))
            draw.text(
                (14, ey + 4),
                shown[:88],
                fill=(180, 220, 255),
                font=_hud_font(),
            )
        if overlays:
            frame = ui_cache.copy()
            frame.paste(well, (wx0, wy0))
            if overlay_flyout:
                frame = blit_overlay_chrome(
                    frame,
                    overlay_id,
                    flyout_open=True,
                    eng=ctx.eng,
                    ox=ox,
                )
            if build_flyout:
                frame = palette.blit(frame, selected=tool, ox=ox)
            if place_dlg is not None:
                frame = blit_place_dialog(frame, place_dlg)
            if advisor_dlg is not None:
                vid = advisor_clip.snapshot() if advisor_clip is not None else None
                frame = blit_advisor_dialog(
                    frame,
                    advisor_dlg,
                    eng=ctx.eng,
                    video=vid,
                    has_video=_advisor_has_video(),
                )
            if menu_open is not None or menu_report is not None:
                frame = compose_city_hud(
                    frame,
                    ctx,
                    shown,
                    menu_open=menu_open,
                    options=options,
                    report=menu_report,
                )
            if ctx.sim.paused:
                pause_spr = chrome.frames[6] if len(chrome.frames) > 6 else None
                frame = blit_pause_square(
                    frame,
                    pause_spr,
                    label=_eng_skip(ctx.eng, 8, 2, "Game Paused"),
                    view_w=max(1, win_w - SIDEBAR_W),
                    view_h=max(1, win_h - TOP_BAR_H),
                )
            _set_layer(well_item, None, "well")
            _set_layer(front_item, None, "front")
            _set_layer(ui_item, frame.convert("RGB"), "ui")
        else:
            host.coords(well_item, wx0, wy0)
            _set_layer(ui_item, ui_cache, "ui")
            _set_layer(well_item, well, "well")
            if build_flyout:
                # Flyout sits left of the 162 px chrome, over the iso well.
                # Keep it on front so Play can still dirty the well only.
                layer = Image.new("RGBA", (win_w, win_h), (0, 0, 0, 0))
                host.coords(front_item, 0, 0)
                host.tag_raise(front_item)
                _set_layer(
                    front_item,
                    palette.blit(layer, selected=tool, ox=ox),
                    "front",
                )
            else:
                _set_layer(front_item, None, "front")
        _prof_note(t0)

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

    def _ltlmen(at_zoom: int):
        from app.walkers import load_ltlmen_frames

        hit = ltlmen_cache.get(at_zoom)
        if hit is not None:
            return hit
        try:
            frames, _name = load_ltlmen_frames(game, zoom=at_zoom)
        except (OSError, ValueError):
            return None
        ltlmen_cache[at_zoom] = frames
        return frames

    def _prof_note(t0: float) -> None:
        nonlocal _prof_last
        ms = (time.perf_counter() - t0) * 1000.0
        _prof_ms.append(ms)
        if len(_prof_ms) > 80:
            del _prof_ms[:40]
        now = time.monotonic()
        if now - _prof_last >= 8.0 and _prof_ms:
            _prof_last = now
            n = min(40, len(_prof_ms))
            chunk = _prof_ms[-n:]
            avg = sum(chunk) / len(chunk)
            print(f"play blit {avg:.1f} ms/tick  n={len(chunk)}", flush=True)

    def _invalidate_live() -> None:
        nonlocal live_base, live_key, view_terrain, view_terrain_key
        live_base = None
        live_key = None
        view_terrain = None
        view_terrain_key = None

    def _ensure_sheets(at_zoom: int) -> dict | None:
        nonlocal map_ready
        use_pl8 = at_zoom in pl8_zooms
        zoom_used_pl8[at_zoom] = use_pl8
        remember_rivers()
        if use_pl8 and at_zoom not in pl8_sheets:
            sheets = assets.load_city_map_sheets(game, zoom=at_zoom)
            pl8_sheets[at_zoom] = sheets
            ctx.n_sprites = sum(len(v) for v in sheets.values())
        map_ready = True
        return pl8_sheets.get(at_zoom)

    def _ensure_view() -> tuple[Image.Image, int, int]:
        """Visible diamonds only — no 80×80 world canvas."""
        nonlocal cam_x, cam_y, view_terrain, view_terrain_key
        sheets = _ensure_sheets(zoom)
        key = (zoom, cam_x, cam_y, win_w, win_h)
        if view_terrain is not None and view_terrain_key == key:
            _ox, _oy, cx, cy = city_map.iso_view_origin(
                cam_x, cam_y, win_w, win_h, zoom
            )
            cam_x, cam_y = cx, cy
            return view_terrain, cx, cy
        cityfixt = sheets.get("CITYFIXT") if sheets else None
        view, cx, cy = city_map.render_iso_view(
            ctx.city,
            cityfixt,
            sheets=sheets,
            cam_x=cam_x,
            cam_y=cam_y,
            view_w=win_w,
            view_h=win_h,
            zoom=zoom,
            water_frame=0,
        )
        cam_x, cam_y = cx, cy
        view_terrain = view
        view_terrain_key = (zoom, cx, cy, win_w, win_h)
        _invalidate_live_only()
        return view, cx, cy

    def _invalidate_live_only() -> None:
        nonlocal live_base, live_key
        live_base = None
        live_key = None

    def _paint_live_view(terrain: Image.Image, vx: int, vy: int) -> Image.Image:
        """Water diamonds + walkers on the camera well. Does not mutate terrain."""
        nonlocal live_base, live_key
        wf = water_frame if options.animations else 0
        key = (zoom, vx, vy, terrain.width, terrain.height, wf)
        if live_base is None or live_key != key:
            view = terrain.copy()
            if wf and river_xy and zoom in pl8_zooms:
                sheets = pl8_sheets.get(zoom)
                cityfixt = sheets.get("CITYFIXT") if sheets else None
                if cityfixt is not None:
                    vis = city_map.cells_in_iso_view(
                        river_xy, vx, vy, view.width, view.height, zoom=zoom
                    )
                    if vis:
                        city_map.blit_water_tiles(
                            view,
                            ctx.city,
                            cityfixt,
                            wf,
                            zoom=zoom,
                            cells=vis,
                            sheets=sheets,
                            cam_x=vx,
                            cam_y=vy,
                            restore=False,
                        )
            live_base = view
            live_key = key
            view = view.copy()
        else:
            view = live_base.copy()
        if not ctx.walkers:
            return view
        from app.walkers import overlay_walkers

        try:
            overlay_walkers(
                view,
                ctx.walkers,
                game,
                zoom=zoom,
                sprites=_ltlmen(zoom),
                cam_x=vx,
                cam_y=vy,
                inplace=True,
            )
        except (OSError, ValueError):
            return view
        return view

    def remember_rivers() -> None:
        nonlocal river_xy
        river_xy = city_map.water_anim_tile_xy(ctx.city)

    def center_camera() -> None:
        nonlocal cam_x, cam_y
        ww, wh = world_wh()
        cam_x = max(0, (ww - win_w) // 2)
        cam_y = max(0, (wh - win_h) // 2)

    def retain_center(old_wh: tuple[int, int] | None, new_wh: tuple[int, int]) -> None:
        nonlocal cam_x, cam_y
        if old_wh is None or old_wh[0] < 1 or old_wh[1] < 1:
            center_camera()
            return
        fx = (cam_x + win_w / 2) / old_wh[0]
        fy = (cam_y + win_h / 2) / old_wh[1]
        cam_x = int(fx * new_wh[0] - win_w / 2)
        cam_y = int(fy * new_wh[1] - win_h / 2)

    def show_city_map(*, reset_cam: bool = False) -> None:
        nonlocal map_mode
        from app.walkers import drawable_walkers

        map_mode = True
        n_walkers = len(drawable_walkers(ctx.walkers))
        old = world_wh() if map_ready else None
        _ensure_sheets(zoom)
        ctx.image = None
        ctx.image_name = f"map:{ctx.city.source}"
        if reset_cam or old is None:
            center_camera()
        _invalidate_live()
        if getattr(ctx.sim, "city_only", 0):
            _scan_city_events(hail=True)
        blit(map_status(n_walkers, None if zoom in pl8_sheets else None))

    def _advisor_has_video() -> bool:
        return advisor_clip is not None

    def _stop_advisor_video() -> None:
        nonlocal advisor_clip, advisor_video_after
        if advisor_video_after is not None:
            try:
                root.after_cancel(advisor_video_after)
            except (tk.TclError, ValueError):
                pass
            advisor_video_after = None
        if advisor_clip is not None:
            advisor_clip.close()
            advisor_clip = None

    def _on_advisor_video() -> None:
        """Repaint only. snapshot() picks the PTS frame for now — no pipe drain."""
        nonlocal advisor_video_after
        advisor_video_after = None
        if advisor_dlg is None or advisor_clip is None:
            return
        blit(last_extra)
        delay = max(16, int(getattr(advisor_clip, "delay_ms", 83)))
        advisor_video_after = root.after(delay, _on_advisor_video)

    def _start_advisor_video(msg) -> None:
        nonlocal advisor_clip, advisor_video_after
        _stop_advisor_video()
        from app.advisor_video import (
            AdvisorClip,
            advisor_plays_audio,
            resolve_advisor_video,
            video_stem_for_message,
        )

        path = resolve_advisor_video(game, video_stem_for_message(msg))
        if path is None:
            return
        mute = (not options.sound) or (not advisor_plays_audio(msg))
        clip = AdvisorClip(path, mute=mute)
        if not clip.begin():
            clip.close()
            return
        advisor_clip = clip
        advisor_video_after = root.after(clip.delay_ms, _on_advisor_video)

    def _set_advisor(msg) -> None:
        nonlocal advisor_dlg
        if msg is None:
            _stop_advisor_video()
            advisor_dlg = None
            return
        advisor_dlg = msg
        _start_advisor_video(msg)

    def _pump_advisor() -> None:
        if advisor_dlg is not None:
            return
        from app.messages import pop_message

        nxt = pop_message(ctx.sim)
        if nxt is not None:
            _set_advisor(nxt)

    def _dismiss_advisor() -> bool:
        if advisor_dlg is None:
            return False
        _set_advisor(None)
        _pump_advisor()
        return True

    def _scan_city_events(*, hail: bool = False, houses_up: int = 0) -> None:
        if not getattr(ctx.sim, "city_only", 0):
            return
        from app.messages import scan_city_messages

        scan_city_messages(
            ctx.sim, ctx.city.tiles, ctx.eng, hail=hail, houses_up=houses_up
        )
        _pump_advisor()

    def _refresh_after_sim(*, houses_changed: bool) -> None:
        """Rebuild visible diamonds only when buildings changed."""
        if houses_changed:
            city_map.restore_river_tags(ctx.city)
            _invalidate_live()
            remember_rivers()
        if not map_mode:
            show_city_map(reset_cam=True)
            return

    def refresh_walkers_only() -> None:
        """Walkers sit on the viewport — static well stays put."""
        return

    def on_water() -> None:
        """Host interior water cycle (250 ms). +0 / banks stay locked."""
        nonlocal water_frame, water_after
        water_after = root.after(WATER_FRAME_MS, on_water)
        if not map_mode or forum_state is not None or not river_xy or not options.animations:
            return
        water_frame = (water_frame + 1) % WATER_FRAMES
        from app.walkers import drawable_walkers

        blit(map_status(len(drawable_walkers(ctx.walkers))))

    def sim_step() -> None:
        """T — one city_sim_phase slot then walkers_tick. City Space is cancel."""
        if forum_state is not None:
            return
        from app.sim import on_sim_step
        from app.walkers import drawable_walkers

        n = on_sim_step(ctx.city, ctx.walkers, ctx.sim)
        ph, w = n.phase, n.walkers
        _refresh_after_sim(houses_changed=ph.houses_changed > 0)
        _pump_advisor()
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
        if forum_state is not None:
            return
        from app.calendar import format_hud_date
        from app.sim import on_month_step
        from app.walkers import drawable_walkers

        n = on_month_step(ctx.city, ctx.walkers, ctx.sim)
        ph, w = n.phase, n.walkers
        date = format_hud_date(ctx.sim.date)
        _refresh_after_sim(houses_changed=ph.houses_changed > 0)
        _pump_advisor()
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

        extra = speed_action(sim)
        if action == "speed_pause" and sim.paused:
            extra = _eng_skip(ctx.eng, 8, 2, "Game Paused")
        blit(
            f"{extra}  {sim.date_label}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
        )

    def _enter_forum() -> None:
        nonlocal forum_state, place_dlg, overlay_flyout, tool, menu_report
        nonlocal load_picks
        place_dlg = None
        _set_advisor(None)
        overlay_flyout = False
        menu_report = None
        load_picks = None
        palette.close()
        tool = None
        forum_state = open_forum(ctx.sim, ctx.city.tiles, game)
        blit(_eng_skip(ctx.eng, 28, 8, "PLEBS"))

    def _leave_forum() -> None:
        nonlocal forum_state
        forum_state = None
        from app.walkers import drawable_walkers

        blit(map_status(len(drawable_walkers(ctx.walkers))))

    def _forum_back() -> bool:
        """Right-click / Esc: panel → chrome, chrome → city."""
        nonlocal forum_state
        if forum_state is None:
            return False
        if forum_state.kind != KIND_CHROME:
            forum_state.kind = KIND_CHROME
            blit(_eng_skip(ctx.eng, 28, 0, "CLEAR FORUM"))
            return True
        _leave_forum()
        return True

    def _menu_layout():
        return top_menu_layout(
            ctx.eng, _hud_font(), options=options, sim=ctx.sim
        )

    def _confirm(question: str) -> bool:
        from tkinter import messagebox

        return bool(messagebox.askyesno(root.title(), question, parent=root))

    def _close_report() -> None:
        nonlocal menu_report, load_picks
        menu_report = None
        load_picks = None

    def _open_report(
        report: MenuReport,
        extra: str | None = None,
        *,
        picks: list[Path] | None = None,
    ) -> None:
        nonlocal menu_report, place_dlg, load_picks
        place_dlg = None
        menu_report = report
        load_picks = picks
        blit(extra if extra is not None else report.title)

    def _open_census() -> None:
        """C / Options+5 — Census Panel [74]. Second C closes it."""
        title = _eng_skip(ctx.eng, 74, 0, "Census Panel")
        if menu_report is not None and menu_report.title == title:
            _close_report()
            blit(last_extra)
            return
        _open_report(census_report(ctx.city.tiles, eng=ctx.eng))

    def _file_save() -> None:
        from app.sav import dest_path, write_sav
        from app.sim_log import write

        dest = dest_path(game, ctx.city, ctx.sim)
        try:
            write_sav(dest, ctx.city, ctx.walkers, ctx.sim, game=game)
        except (OSError, ValueError):
            blit(_eng_skip(ctx.eng, 38, 6, "FILE ERROR -- Save Canceled"))
            return
        ctx.city.source = dest.name
        ctx.sim.source = dest.name
        n = dest.stat().st_size
        write(f"sav_write  {dest}  {n} B")
        blit(
            f"{_eng_skip(ctx.eng, 0, 3, 'Save')}  sav/{dest.name}  {n} B"
        )

    def _load_sav(dest: Path) -> None:
        nonlocal city_skill, tool, overlay_id, overlay_flyout, place_dlg
        nonlocal menu_report, forum_state, load_picks
        from app.city_map import load_chunk_sizes, load_city_from_sav
        from app.city_sim import load_sim_from_sav
        from app.sim_log import write
        from app.walkers import drawable_walkers, load_walkers_from_sav

        try:
            sizes = load_chunk_sizes(game)
            city = load_city_from_sav(dest, sizes, game=game)
            try:
                walkers = load_walkers_from_sav(dest, sizes, game=game)
            except (OSError, ValueError):
                walkers = []
            sim = load_sim_from_sav(dest, sizes, game=game)
        except (OSError, ValueError):
            blit(_eng_skip(ctx.eng, 38, 4, "FILE ERROR -- Load Canceled"))
            return
        ctx.city = city
        ctx.walkers = walkers
        ctx.sim = sim
        ctx.start_in_map = True
        if getattr(sim, "city_only", 0):
            city_skill = int(sim.skill)
        tool = None
        overlay_id = OVERLAY_GEOGRAPHY
        overlay_flyout = False
        place_dlg = None
        menu_report = None
        load_picks = None
        forum_state = None
        invalidate_iso([], flush=True)
        show_city_map(reset_cam=True)
        write(f"sav_read  {dest}  {dest.stat().st_size} B")
        blit(
            f"{_eng_skip(ctx.eng, 0, 2, 'Load')}  {dest.name}  "
            f"{sim.date_label}  tesouro {sim.treasury}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
        )

    def _load_label(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(Path(game).resolve()))
        except ValueError:
            return path.name

    def _apply_new_city() -> None:
        nonlocal city_skill, tool, overlay_id, overlay_flyout, place_dlg
        nonlocal menu_report, forum_state, load_picks
        from app.new_game import start_city_assignment
        from app.walkers import drawable_walkers

        fresh = start_city_assignment(skill=city_skill, game=game)
        ctx.city = fresh.city
        ctx.walkers = fresh.walkers
        ctx.sim = fresh.sim
        ctx.start_in_map = True
        tool = None
        overlay_id = OVERLAY_GEOGRAPHY
        overlay_flyout = False
        place_dlg = None
        menu_report = None
        load_picks = None
        forum_state = None
        invalidate_iso([], flush=True)
        show_city_map(reset_cam=True)
        blit(
            f"{_eng_skip(ctx.eng, 0, 1, 'New Game')}  "
            f"{fresh.skill_name}  tesouro {ctx.sim.treasury}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
        )

    def _apply_load() -> None:
        from app.city_map import find_saves

        found = find_saves(game)
        if not found:
            blit(_eng_skip(ctx.eng, 38, 4, "FILE ERROR -- Load Canceled"))
            return
        if len(found) == 1:
            _load_sav(found[0])
            return
        title = _eng_skip(ctx.eng, 38, 2, "Select a saved game to LOAD")
        picks = found[:12]
        _open_report(
            MenuReport(title, tuple(_load_label(p) for p in picks)),
            picks=picks,
        )

    def clock_step() -> None:
        """sim_tick_due 0x3E4B9 — auto-advance when Speed is not paused.

        Walker slides use wall-clock ms (1600 ms / tile = 32 display frames)
        so Play (200 ms sim) still crawls a few pixels every 50 ms blit.
        Display paints visible diamonds into the well; no world bitmap.
        """
        nonlocal sim_after, last_clock_mono
        now = time.monotonic()
        dt = int((now - last_clock_mono) * 1000)
        last_clock_mono = now
        dt = max(0, min(dt, _MAX_CLOCK_DT_MS))
        sim_after = root.after(TICK_MS, clock_step)
        if not map_mode or forum_state is not None:
            return
        from app.sim import on_clock_step, sim_tick_due
        from app.walkers import (
            advance_walker_slides,
            drawable_walkers,
            use_realtime_slides,
        )

        use_realtime_slides()
        n = sim_tick_due(ctx.sim, dt)
        sim_ran = False
        ph = w = None
        if n > 0:
            result = on_clock_step(ctx.city, ctx.walkers, ctx.sim, pulses=n)
            ph, w = result.phase, result.walkers
            sim_ran = True
        slid = False
        if not ctx.sim.paused:
            slid = advance_walker_slides()
        if sim_ran and ph is not None and w is not None:
            if ph.houses_changed > 0:
                _refresh_after_sim(houses_changed=True)
            _pump_advisor()
            from app.sim_log import last_line

            tail = last_line()
            blit(
                f"{speed_action(ctx.sim)}  slot {ph.phase:#x}  "
                f"houses +{ph.houses_up}/-{ph.houses_down}  {ph.date_label}  "
                f"moved={w.stepped}  drawn={len(drawable_walkers(ctx.walkers))}"
                + (f"  | {tail[-88:]}" if tail else "")
            )
        elif slid:
            blit()

    def evolve_pass() -> None:
        """E — host-only: all 80 evolve rows. Not one EXE pulse."""
        if forum_state is not None:
            return
        from app.city_sim import evolve_all_rows
        from app.walkers import drawable_walkers

        up, down, merge = evolve_all_rows(
            ctx.city.tiles, decay=ctx.sim.wrap3 == 0
        )
        _refresh_after_sim(houses_changed=(up + down) > 0)
        _scan_city_events(houses_up=up)
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
        if new_zoom == zoom and map_ready:
            blit(map_status(len(drawable_walkers(ctx.walkers))))
            return
        old = world_wh() if map_ready else None
        zoom = new_zoom
        _ensure_sheets(zoom)
        ctx.image = None
        retain_center(old, world_wh())
        _invalidate_live()
        blit(map_status(len(drawable_walkers(ctx.walkers))))

    def pan(dx: int, dy: int) -> None:
        nonlocal cam_x, cam_y
        from app.walkers import drawable_walkers

        if not map_mode or not map_ready:
            return
        mul = max(1, int(options.scroll_step))
        cam_x += dx * mul
        cam_y += dy * mul
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

    def _cancel_build() -> bool:
        """Space — cancel rubber-band / build tool. Query stays (not a build)."""
        nonlocal tool, band_start, band_cur, pending_click, drag, place_dlg
        aborted = band_start is not None
        band_start = None
        band_cur = None
        pending_click = None
        drag = None
        building = tool is not None and tool != TOOL_QUERY
        if not aborted and not building:
            return False
        tool = None
        place_dlg = None
        blit(
            ("arrasto cancelado" if aborted else "ferramenta cancelada")
            + f"  tesouro {ctx.sim.treasury}"
        )
        return True

    def _dismiss_city_ui() -> bool:
        """Esc — exit current screen/panel/menu. City Only does not quit here."""
        nonlocal menu_report, menu_open, overlay_flyout, place_dlg
        if menu_report is not None:
            _close_report()
            blit(last_extra)
            return True
        if menu_open is not None:
            menu_open = None
            blit(last_extra)
            return True
        if overlay_flyout:
            overlay_flyout = False
            blit(f"Overlay: {overlay_name(overlay_id, ctx.eng)}")
            return True
        if _dismiss_advisor():
            blit(last_extra)
            return True
        if place_dlg is not None:
            place_dlg = None
            blit(last_extra)
            return True
        if palette.open is not None:
            palette.close()
            blit(last_extra)
            return True
        if _cancel_build():
            return True
        return _forum_back()

    def on_key(event: tk.Event) -> None:  # type: ignore[type-arg]
        """City Only: C2MANUAL.DOC Keyboard Commands. Debug keys only off-map."""
        key = event.keysym.lower()
        ch = (getattr(event, "char", "") or "").lower()
        mods = int(getattr(event, "state", 0) or 0)
        alt = bool(mods & 0x20008)
        step = PAN_STEP[city_map.clamp_zoom(zoom)]
        if key in {"escape"}:
            if map_mode and _dismiss_city_ui():
                return
            if _forum_back():
                return
            if not map_mode:
                on_close()
            return
        if key in {"q"}:
            on_close()
            return
        if not map_mode:
            if key in {"1"}:
                use_pl8("backgrnd.pl8", first_only=True)
            elif key in {"2"}:
                use_pl8("CITYFIXT.PL8", first_only=True)
            elif key in {"3"}:
                show_city_map(reset_cam=True)
            elif key in {"space", "t"}:
                sim_step()
            elif key in {"m"} or ch == "m":
                month_step()
            elif key in {"e"}:
                evolve_pass()
            elif key in {"a"}:
                if not options.sound:
                    blit(
                        f"{_eng_skip(ctx.eng, 56, 1, 'Sounds are')} "
                        f"{on_off(ctx.eng, False)}"
                    )
                else:
                    blit(audio.play_raw_preview(game))
            return
        # 1.1A City Only — prefer EXE when a host debug key collides.
        if alt and key in {"f", "f1", "f3", "d"}:
            return
        if key in {"p"} or ch == "p":
            apply_speed(toggle_pause_action(ctx.sim))
            return
        if key in {"c"} or ch == "c":
            _open_census()
            return
        if key in {"a"} or ch == "a":
            apply_speed("speed_fast")
            return
        if key in {"space"}:
            _cancel_build()
            return
        if key in {"f", "f2"} or ch == "f":
            _enter_forum()
            return
        if key in {"f1"}:
            if forum_state is not None:
                _leave_forum()
            else:
                from app.walkers import drawable_walkers

                blit(map_status(len(drawable_walkers(ctx.walkers))))
            return
        if key in {"f3"}:
            blit(
                _eng_skip(
                    ctx.eng,
                    31,
                    24,
                    "You cannot get promoted when playing in city-only mode.",
                )
            )
            return
        if key in {"f4"}:
            _apply_load()
            return
        if key in {"f5"}:
            _file_save()
            return
        if key in {"1"}:
            set_zoom(0)
            return
        if key in {"2"}:
            set_zoom(1)
            return
        if key in {"3"}:
            set_zoom(2)
            return
        if key in {"t"}:
            sim_step()
        elif key in {"m"} or ch == "m":
            month_step()
        elif key in {"e"}:
            evolve_pass()
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
            if map_ready:
                center_camera()
                from app.walkers import drawable_walkers

                blit(map_status(len(drawable_walkers(ctx.walkers))))

    def invalidate_iso(cells: list[tuple[int, int]], *, flush: bool = False) -> None:
        """Drop the camera well so the next blit repaints visible diamonds.

        Place/clear used to patch a 4640×2400 world bitmap. The well is
        ~200–400 diamonds — cheaper to redraw than to keep a world canvas.
        """
        if flush:
            city_map.restore_river_tags(ctx.city)
        elif cells:
            city_map.restore_river_tags(ctx.city)
        _invalidate_live()
        remember_rivers()
        ctx.image = None

    def open_place(x: int, y: int) -> None:
        nonlocal place_dlg
        from app.walker_quotes import query_walker
        from app.walkers import find_walker_at

        hit = find_walker_at(ctx.walkers, x, y, tiles=ctx.city.tiles)
        if hit is not None:
            place_dlg = query_walker(
                hit, ctx.city.tiles, ctx.eng, ctx.sim.tax_rate
            )
            blit(f"Query {place_dlg.name}  tesouro {ctx.sim.treasury}")
            return
        place_dlg = query_place(ctx.city, x, y, ctx.eng)
        blit(f"Query {place_dlg.name}  tesouro {ctx.sim.treasury}")

    def place_at(vx: int, vy: int) -> None:
        nonlocal tool, place_dlg
        if not map_ready or tool is None:
            return
        ww, wh = world_wh()
        cx, cy = view_to_canvas(
            vx, vy, cam_x, cam_y, ww, wh,
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
        if result.ok:
            _scan_city_events()
        blit(result.message + f"  tesouro {ctx.sim.treasury}")

    def select_chrome(hit) -> None:
        nonlocal tool, overlay_flyout, overlay_id, place_dlg
        action = hit.action
        if action.startswith("speed_"):
            overlay_flyout = False
            apply_speed(action)
            return
        if action == "view_forum":
            overlay_flyout = False
            _enter_forum()
            return
        if action == "view_city":
            overlay_flyout = False
            if forum_state is not None:
                _leave_forum()
                return
            from app.walkers import drawable_walkers

            blit(map_status(len(drawable_walkers(ctx.walkers))))
            return
        if action == "view_province":
            overlay_flyout = False
            blit(
                _eng_skip(
                    ctx.eng,
                    31,
                    24,
                    "You cannot get promoted when playing in city-only mode.",
                )
            )
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
        if not map_ready:
            return True
        ww, wh = world_wh()
        cam = city_map.minimap_click_pan(
            x,
            y,
            zoom,
            ww,
            wh,
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
        nonlocal menu_open, menu_report, load_picks
        font = _hud_font()
        layout = _menu_layout()
        item = _menu_item_at(layout, menu_open, x, y, font)
        if item is not None:
            slot, skip, lab = item
            menu_open = None
            if slot == SLOT_FILE and skip == FILE_QUIT:
                q = _eng_skip(ctx.eng, 9, 0, "Exit to DOS?")
                if _confirm(q):
                    on_close()
                else:
                    blit(last_extra)
                return True
            if slot == SLOT_FILE and skip == FILE_SAVE:
                _file_save()
                return True
            if slot == SLOT_FILE and skip == FILE_NEW:
                q = _eng_skip(ctx.eng, 9, 1, "Start a New Game?")
                if _confirm(q):
                    _apply_new_city()
                else:
                    blit(last_extra)
                return True
            if slot == SLOT_FILE and skip == FILE_LOAD:
                _apply_load()
                return True
            if slot == SLOT_OPTIONS and skip == OPT_MUSIC:
                options.music = not options.music
                blit(
                    f"{_eng_skip(ctx.eng, 56, 0, 'Music is')} "
                    f"{on_off(ctx.eng, options.music)}"
                    + (" — XMI not in host" if options.music else "")
                )
                return True
            if slot == SLOT_OPTIONS and skip == OPT_SOUND:
                options.sound = not options.sound
                if advisor_clip is not None:
                    from app.advisor_video import advisor_plays_audio

                    mute = (not options.sound) or (
                        advisor_dlg is not None and not advisor_plays_audio(advisor_dlg)
                    )
                    advisor_clip.set_mute(mute)
                blit(
                    f"{_eng_skip(ctx.eng, 56, 1, 'Sounds are')} "
                    f"{on_off(ctx.eng, options.sound)}"
                )
                return True
            if slot == SLOT_OPTIONS and skip == OPT_ANIM:
                options.animations = not options.animations
                blit(
                    f"{_eng_skip(ctx.eng, 56, 5, 'Animations are')} "
                    f"{on_off(ctx.eng, options.animations)}"
                )
                return True
            if slot == SLOT_OPTIONS and skip == OPT_YEAR:
                options.auto_save = not options.auto_save
                blit(
                    f"{_eng_skip(ctx.eng, 56, 9, 'Auto-Save is')} "
                    f"{on_off(ctx.eng, options.auto_save)}"
                    + " — host does not write lastyear.sav"
                )
                return True
            if slot == SLOT_OPTIONS and skip == OPT_CENSUS:
                _open_report(census_report(ctx.city.tiles, eng=ctx.eng))
                return True
            if slot == SLOT_SPEED and skip == SPD_PAUSE:
                apply_speed(toggle_pause_action(ctx.sim))
                return True
            if slot == SLOT_SPEED and skip == SPD_GAME:
                apply_speed(next_game_speed(ctx.sim))
                return True
            if slot == SLOT_SPEED and skip == SPD_SCROLL:
                options.scroll_step = cycle_scroll(options.scroll_step)
                blit(
                    f"{_eng_skip(ctx.eng, 11, 2, 'Adjusting scroll speed')}  "
                    f"{options.scroll_step}x"
                )
                return True
            if slot == SLOT_HELP and skip == HLP_ABOUT:
                _open_report(about_report(ctx.eng))
                return True
            if slot == SLOT_HELP and skip == HLP_HINTS:
                _open_report(
                    help_topic_excerpt(
                        game, HELP_TOPIC_HINTS, _eng_skip(ctx.eng, 3, 1, "Hints and Tips")
                    )
                )
                return True
            if slot == SLOT_HELP and skip == HLP_GAME:
                _open_report(
                    help_topic_excerpt(
                        game, HELP_TOPIC_GAME, _eng_skip(ctx.eng, 3, 2, "Game Help")
                    )
                )
                return True
            if slot == SLOT_HELP and skip == HLP_HISTORY:
                _open_report(
                    help_topic_excerpt(
                        game, HELP_TOPIC_HISTORY, _eng_skip(ctx.eng, 3, 3, "History")
                    )
                )
                return True
            if slot == SLOT_HELP and skip == HLP_ICONS:
                _open_report(
                    help_topic_excerpt(
                        game, HELP_TOPIC_ICONS, _eng_skip(ctx.eng, 3, 4, "Icons")
                    )
                )
                return True
            blit(f"{lab} — ainda não")
            return True
        title = _menu_title_at(layout, x, y)
        if title is not None:
            menu_open = None if menu_open == title else title
            _close_report()
            blit(last_extra)
            return True
        if menu_open is not None:
            menu_open = None
            blit(last_extra)
            return True
        if menu_report is not None:
            if report_contains(x, y):
                if load_picks:
                    idx = report_line_at(x, y, len(load_picks))
                    if idx is not None:
                        dest = load_picks[idx]
                        _close_report()
                        _load_sav(dest)
                return True
            _close_report()
            blit(last_extra)
            return True
        return False

    def on_press(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal drag, pending_click, press_on_chrome, cam_x, cam_y
        nonlocal band_start, band_cur
        if forum_state is not None:
            pending_click = (event.x, event.y)
            drag = None
            press_on_chrome = True
            return
        if not map_mode or not map_ready:
            return
        if event.y < TOP_BAR_H or (
            menu_open is not None
            and _menu_item_at(
                _menu_layout(),
                menu_open,
                event.x,
                event.y,
                _hud_font(),
            )
            is not None
        ) or (menu_report is not None and report_contains(event.x, event.y)):
            pending_click = (event.x, event.y)
            drag = None
            press_on_chrome = True
            return
        ox = chrome_ox(win_w)
        if (
            chrome.hit_test(event.x, event.y, ox=ox) is not None
            or palette.covers(event.x, event.y, ox=ox)
            or (overlay_flyout and flyout_item_at(event.x, event.y, ox) is not None)
            or (
                place_dlg is not None
                and place_dialog_contains(
                    event.x, event.y, place_dlg, frame_size=(win_w, win_h)
                )
            )
            or advisor_contains(
                event.x, event.y, advisor_dlg, has_video=_advisor_has_video()
            )
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
            if result.ok:
                _scan_city_events()
            blit(result.message + f"  tesouro {ctx.sim.treasury}")
            return
        if click is None:
            return
        if abs(event.x - click[0]) + abs(event.y - click[1]) >= CLICK_DRAG_PX:
            return
        if _menu_click(event.x, event.y):
            return
        if advisor_contains(
            event.x, event.y, advisor_dlg, has_video=_advisor_has_video()
        ):
            _dismiss_advisor()
            blit(last_extra)
            return
        if forum_state is not None:
            msg = click_forum(
                forum_state,
                event.x,
                event.y,
                ctx.sim,
                eng=ctx.eng,
                frame_size=(win_w, win_h),
            )
            if msg == "exit":
                _leave_forum()
            else:
                blit(msg if msg else last_extra)
            return
        if menu_report is not None and report_contains(event.x, event.y):
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
        if place_dlg is not None and place_dialog_close_contains(
            event.x, event.y, place_dlg, frame_size=(win_w, win_h)
        ):
            place_dlg = None
            blit(last_extra)
            return
        if place_dlg is not None and place_dialog_contains(
            event.x, event.y, place_dlg, frame_size=(win_w, win_h)
        ):
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
        if tool is None and not chrome.covers(event.x, event.y, ox=ox):
            cell = tile_at(event.x, event.y)
            if cell is not None:
                tid = ctx.city.tile(cell[0], cell[1]).terrain_id
                if is_forum_building(tid):
                    _enter_forum()
                    return
        if place_dlg is not None:
            place_dlg = None
            blit(last_extra)

    def on_right(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal tool, band_start, band_cur, pending_click, drag, menu_open
        nonlocal overlay_flyout, place_dlg, menu_report, load_picks
        if forum_state is not None:
            _forum_back()
            return
        if advisor_dlg is not None:
            _dismiss_advisor()
            blit(last_extra)
            return
        if not map_mode:
            return
        aborted = band_start is not None
        band_start = None
        band_cur = None
        pending_click = None
        drag = None
        menu_open = None
        menu_report = None
        load_picks = None
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
    host.bind("<Button-1>", on_press)
    host.bind("<B1-Motion>", on_motion)
    host.bind("<ButtonRelease-1>", on_release)
    host.bind("<Button-3>", on_right)
    host.bind("<MouseWheel>", on_wheel)
    host.bind("<Button-4>", on_wheel)
    host.bind("<Button-5>", on_wheel)
    def on_close() -> None:
        _stop_advisor_video()
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
