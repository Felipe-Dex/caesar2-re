"""640×480 host window (video_init @ 0x28341 stand-in). Pillow blit via tkinter."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageTk

from app.boot import BootContext

SCREEN_W = 640
SCREEN_H = 480
BG = (12, 16, 28)


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


def _hud_lines(ctx: BootContext) -> list[str]:
    lines = [
        "Caesar II — v0 skeleton (not a sim)",
        f"install: {ctx.game}  [{ctx.source}]",
        f"art: {ctx.image_name}   map: {ctx.city.width}x{ctx.city.height} empty",
    ]
    if ctx.eng is not None:
        hit = ctx.eng.find("Caesar II - Version")
        if hit is None:
            hit = ctx.eng.find("Caesar II")
        if hit is not None:
            shown = hit[1].replace("\r", " ").replace("\n", " ")
            lines.append(f"C2.ENG[{hit[0]}]: {shown[:70]}")
    lines.append("Esc quit   1 title   2 cityfixt tile   A raw   (Godot later)")
    return lines


def compose_frame(ctx: BootContext, extra: str | None = None) -> Image.Image:
    base = _fit(ctx.image) if ctx.image is not None else Image.new(
        "RGBA", (SCREEN_W, SCREEN_H), (*BG, 255)
    )
    overlay = Image.new("RGBA", (SCREEN_W, SCREEN_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle((6, 6, SCREEN_W - 7, 78), fill=(0, 0, 0, 170))
    font = ImageFont.load_default()
    y = 10
    for line in _hud_lines(ctx):
        draw.text((14, y), line, fill=(255, 228, 160, 255), font=font)
        y += 13
    if extra:
        draw.rectangle((6, SCREEN_H - 28, SCREEN_W - 7, SCREEN_H - 7), fill=(0, 0, 0, 170))
        draw.text((14, SCREEN_H - 24), extra, fill=(180, 220, 255, 255), font=font)
    return Image.alpha_composite(base, overlay).convert("RGB")


def show(ctx: BootContext, *, game: Path) -> None:
    """title_input_wait @ 0x2E7B1 stand-in: spin until Esc."""
    from app import assets, audio

    root = tk.Tk()
    root.title("Caesar II — v0")
    root.geometry(f"{SCREEN_W}x{SCREEN_H}")
    root.resizable(False, False)
    root.configure(bg="#0c101c")

    label = tk.Label(root, borderwidth=0)
    label.pack()
    photo: ImageTk.PhotoImage | None = None

    def blit(extra: str | None = None) -> None:
        nonlocal photo
        frame = compose_frame(ctx, extra)
        photo = ImageTk.PhotoImage(frame)
        label.configure(image=photo)
        label.image = photo  # type: ignore[attr-defined]

    def use_pl8(name: str, first_only: bool) -> None:
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
        if key in {"escape", "q"}:
            root.destroy()
        elif key in {"1",}:
            use_pl8("backgrnd.pl8", first_only=True)
        elif key in {"2",}:
            use_pl8("CITYFIXT.PL8", first_only=True)
        elif key in {"a",}:
            blit(audio.play_raw_preview(game))

    root.bind("<Key>", on_key)
    blit(ctx.audio_status)
    root.mainloop()
