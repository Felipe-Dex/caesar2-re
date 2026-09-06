"""640×480 host window (video_init @ 0x28341 stand-in). Pillow blit via tkinter.

City map (key 3): viewport onto the native iso canvas. Arrow keys / click-drag
pan; +/- switch PL8 zoom sets 0/1/2 (58×30 / 26×14 / 10×6).
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from app.boot import BootContext
from app.city_map import WATER_FRAME_MS, WATER_FRAMES

SCREEN_W = 640
SCREEN_H = 480
BG = (12, 16, 28)
PAN_STEP = (96, 48, 24)


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
    canvas: Image.Image, cam_x: int, cam_y: int
) -> tuple[Image.Image, int, int]:
    """640×480 window onto ``canvas``. Returns (view, clamped_x, clamped_y)."""
    max_x = max(0, canvas.width - SCREEN_W)
    max_y = max(0, canvas.height - SCREEN_H)
    x = max(0, min(int(cam_x), max_x))
    y = max(0, min(int(cam_y), max_y))
    view = Image.new("RGBA", (SCREEN_W, SCREEN_H), (*BG, 255))
    if canvas.width <= SCREEN_W and canvas.height <= SCREEN_H:
        px = (SCREEN_W - canvas.width) // 2
        py = (SCREEN_H - canvas.height) // 2
        view.paste(canvas, (px, py), canvas)
        return view, 0, 0
    box = (
        x,
        y,
        x + min(SCREEN_W, canvas.width),
        y + min(SCREEN_H, canvas.height),
    )
    crop = canvas.crop(box)
    view.paste(crop, (0, 0), crop)
    return view, x, y


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
            "Esc sair   1 titulo   3 mapa   Space/T pulso   E evolve80   +/- zoom   setas pan   Home"
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
        if base.size != (SCREEN_W, SCREEN_H):
            canvas = Image.new("RGBA", (SCREEN_W, SCREEN_H), (*BG, 255))
            canvas.paste(base, (0, 0), base)
            base = canvas
    elif ctx.image is not None:
        base = _fit(ctx.image)
    else:
        base = Image.new("RGBA", (SCREEN_W, SCREEN_H), (*BG, 255))
    overlay = Image.new("RGBA", (SCREEN_W, SCREEN_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((6, 6, SCREEN_W - 7, 78), fill=(0, 0, 0, 170))
    font = ImageFont.load_default()
    y = 10
    for line in _hud_lines(ctx, map_mode=map_mode):
        draw.text((14, y), line, fill=(255, 228, 160, 255), font=font)
        y += 13
    if extra:
        draw.rectangle((6, SCREEN_H - 28, SCREEN_W - 7, SCREEN_H - 7), fill=(0, 0, 0, 170))
        draw.text((14, SCREEN_H - 24), extra, fill=(180, 220, 255, 255), font=font)
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

    root = tk.Tk()
    root.title("Caesar II — v0")
    root.geometry(f"{SCREEN_W}x{SCREEN_H}")
    root.resizable(False, False)
    root.configure(bg="#0c101c")

    label = tk.Label(root, borderwidth=0)
    label.pack()
    photo: ImageTk.PhotoImage | None = None

    map_mode = False
    cam_x = 0
    cam_y = 0
    zoom = 0
    water_frame = 0
    river_xy: list[tuple[int, int]] = []
    pl8_sheets: dict[int, dict] = {}
    last_extra: str | None = None
    water_after: str | None = None
    terrain_cache: dict[int, Image.Image] = {}
    water_cache: dict[tuple[int, int], Image.Image] = {}
    map_cache: dict[int, Image.Image] = {}
    zoom_used_pl8: dict[int, bool] = {}
    drag: tuple[int, int, int, int] | None = None
    pl8_zooms = assets.available_map_zooms(game)

    def current_canvas() -> Image.Image | None:
        return map_cache.get(zoom)

    def blit(extra: str | None = None) -> None:
        nonlocal photo, cam_x, cam_y, last_extra
        if extra is not None:
            last_extra = extra
        view = None
        canvas = current_canvas() if map_mode else None
        if canvas is not None:
            view, cam_x, cam_y = crop_viewport(canvas, cam_x, cam_y)
        frame = compose_frame(ctx, extra, view=view, map_mode=map_mode)
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
        river_xy = city_map.river_tile_xy(ctx.city)

    def ensure_map(at_zoom: int) -> Image.Image:
        if at_zoom in map_cache:
            return map_cache[at_zoom]
        use_pl8 = at_zoom in pl8_zooms
        zoom_used_pl8[at_zoom] = use_pl8
        blit(f"rendering zoom {at_zoom}…")
        root.update_idletasks()
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
        cam_x = max(0, (canvas.width - SCREEN_W) // 2)
        cam_y = max(0, (canvas.height - SCREEN_H) // 2)

    def retain_center(old: Image.Image | None, new: Image.Image) -> None:
        nonlocal cam_x, cam_y
        if old is None or old.width < 1 or old.height < 1:
            center_camera(new)
            return
        fx = (cam_x + SCREEN_W / 2) / old.width
        fy = (cam_y + SCREEN_H / 2) / old.height
        cam_x = int(fx * new.width - SCREEN_W / 2)
        cam_y = int(fy * new.height - SCREEN_H / 2)

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
        blit(
            f"slot {ph.phase:#x} {ph.name}  houses +{ph.houses_up}/-{ph.houses_down} "
            f"merge={ph.houses_merge}  {ph.date_label}  "
            f"moved={w.stepped} frames={w.animated} live={w.live}  "
            f"drawn={len(drawable_walkers(ctx.walkers))}"
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

    def on_press(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal drag
        if not map_mode or current_canvas() is None:
            return
        drag = (event.x, event.y, cam_x, cam_y)

    def on_motion(event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal cam_x, cam_y
        if drag is None or not map_mode:
            return
        sx, sy, ox, oy = drag
        cam_x = ox - (event.x - sx)
        cam_y = oy - (event.y - sy)
        from app.walkers import drawable_walkers

        blit(map_status(len(drawable_walkers(ctx.walkers))))

    def on_release(_event: tk.Event) -> None:  # type: ignore[type-arg]
        nonlocal drag
        drag = None

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

    root.bind("<Key>", on_key)
    label.bind("<Button-1>", on_press)
    label.bind("<B1-Motion>", on_motion)
    label.bind("<ButtonRelease-1>", on_release)
    label.bind("<MouseWheel>", on_wheel)
    label.bind("<Button-4>", on_wheel)
    label.bind("<Button-5>", on_wheel)
    def on_close() -> None:
        if water_after is not None:
            root.after_cancel(water_after)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    if ctx.start_in_map:
        root.title("Caesar II — City Only")
        show_city_map(reset_cam=True)
    else:
        blit(ctx.audio_status)
    water_after = root.after(WATER_FRAME_MS, on_water)
    root.mainloop()
