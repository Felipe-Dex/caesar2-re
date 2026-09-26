"""Higher-quality stills from ``images_new/{stem}.png``.

Retail city / advisor / HUD bitmaps are 8.3 PL8 names (``AHOSPIT.PL8``).
Search (PNG only, case-insensitive), then the install PL8:

1. ``{repo}/images_new/{stem}.png``
2. ``{game}/images_new/{stem}.png`` (optional drop next to the install)
3. retail ``{stem}.PL8``

A PNG does **not** have to match the 1995 pixel size. Same rule as
``videos_new``: the mp4 can be larger / different res and is fitted into
the advisor dest (320×152). Here the dest is the original sprite 0 rect.
Scale with LANCZOS, keep aspect, letterbox (transparent pad) so isometric
footprints are not stretched.

``AHOSPIT`` is the hospital **build-menu still** (one blit, 182×132, own
``.256``). It is **not** the iso hospital: tile ``0xFB`` draws
``HOUSES1`` LUT variants ``0x56–0x5E`` (``tile[+3]&0x1C`` sheet 0).
One PNG replaces that single still, not a sprite sheet.

Drop more files as ``images_new/{STEM}.png`` using the 8.3 stem
(``ABATHS``, ``AHOUSE``, ``AWELL``, …). PNGs are gitignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from app.city_chrome import SIDEBAR_X, TOP_BAR_H
from app.config import REPO_ROOT

_TOOLS = REPO_ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_NEW_DIR = "images_new"

# Native dest = PL8 sprite 0 (1995). PNG may be any resolution.
# 42 of the A* menu stills are 182×132 / 24048 B (AHOUSE family).
STILL_DEST: dict[str, tuple[int, int]] = {
    "AAQUADU": (182, 132),
    "AARENA": (182, 132),
    "ABARRAC": (182, 132),
    "ABASILI": (182, 132),
    "ABATHS": (182, 132),
    "ABTOWN": (182, 132),
    "ACAMP": (182, 132),
    "ACIRCUS": (182, 132),
    "ACMAXIM": (182, 132),
    "ACOLISE": (182, 132),
    "AFARM": (182, 132),
    "AFORT": (182, 132),
    "AFORUM": (182, 132),
    "AFOUNTA": (182, 132),
    "AGARDEN": (182, 132),
    "AGRAMMA": (182, 132),
    "AHOSPIT": (182, 132),  # hospital menu still (test stem)
    "AHOUSE": (182, 132),
    "AHOUSE2": (58, 338),
    "ALIBRAR": (182, 132),
    "AMARKET": (182, 132),
    "AMINE": (182, 132),
    "AODEUM": (182, 132),
    "APLAZA": (182, 132),
    "APORT": (182, 132),
    "APPGATE": (327, 274),
    "APREFEC": (182, 132),
    "APROADS": (182, 132),
    "APWALLS": (182, 132),
    "AQUADUCT": (414, 193),
    "AQUARRY": (182, 132),
    "ARESERV": (182, 132),
    "ARHETOR": (182, 132),
    "ARMYWARN": (320, 152),  # advisor letterbox (SMK play rect size)
    "AROAD": (182, 132),
    "ASHIPYA": (182, 132),
    "ASHRINE": (182, 132),
    "ATEMPLE": (182, 132),
    "ATHEATE": (182, 132),
    "ATOWER": (182, 132),
    "ATOWN": (182, 132),
    "ATPOST": (182, 132),
    "ATRIBE": (182, 132),
    "AUGCAMEO": (266, 305),
    "AUGFORU2": (414, 241),
    "AUGHOOD": (231, 305),
    "AUGPOINT": (258, 317),
    "AWALL": (182, 132),
    "AWAREHO": (182, 132),
    "AWELL": (182, 132),
}

# Hosted city tools → 8.3 still stem. Hospital is the images_new test.
TOOL_STILL_STEM: dict[str, str] = {
    "hospital": "AHOSPIT",
    "baths": "ABATHS",
    "tent": "AHOUSE",
    "road": "AROAD",
    "reservoir": "ARESERV",
    "aqueduct": "AAQUADU",
    "well": "AWELL",
    "fountain": "AFOUNTA",
    "garden": "AGARDEN",
    "plaza": "APLAZA",
    "prefecture": "APREFEC",
    "tower": "ATOWER",
    "barracks": "ABARRAC",
    "wall": "AWALL",
    "theater": "ATHEATE",
    "odeum": "AODEUM",
    "arena": "AARENA",
    "coliseum": "ACOLISE",
    "circus": "ACIRCUS",
    "cmaximus": "ACMAXIM",
    "shrine": "ASHRINE",
    "temple": "ATEMPLE",
    "basilica": "ABASILI",
    "grammaticus": "AGRAMMA",
    "rhetor": "ARHETOR",
    "library": "ALIBRAR",
    "market": "AMARKET",
    "aventine": "AFORUM",
    "janiculan": "AFORUM",
    "palatine": "AFORUM",
}

DEFAULT_A_STILL = (182, 132)


def pl8_stem(pl8_name: str) -> str:
    """``AHOSPIT.PL8`` / ``ahospit.pl8`` → ``AHOSPIT``."""
    return Path(pl8_name).stem.upper()


def still_stem_for_tool(tool: str | None) -> str | None:
    if not tool:
        return None
    return TOOL_STILL_STEM.get(str(tool))


def still_dest_size(stem: str, game: Path | None = None) -> tuple[int, int]:
    """Native blit size for ``stem``. AHOSPIT is 182×132 (one frame)."""
    key = stem.upper()
    hit = STILL_DEST.get(key)
    if hit is not None:
        return hit
    meta = _pl8_sprite0_size(game, f"{key}.PL8")
    if meta is not None:
        return meta
    if key.startswith("A"):
        return DEFAULT_A_STILL
    return DEFAULT_A_STILL


def _ci_dir(parent: Path, name: str) -> Path | None:
    direct = parent / name
    if direct.is_dir():
        return direct
    want = name.upper()
    try:
        for child in parent.iterdir():
            if child.is_dir() and child.name.upper() == want:
                return child
    except OSError:
        return None
    return None


def _ci_file(folder: Path, name: str) -> Path | None:
    direct = folder / name
    if direct.is_file():
        return direct
    want = name.upper()
    try:
        for child in folder.iterdir():
            if child.is_file() and child.name.upper() == want:
                return child
    except OSError:
        return None
    return None


def image_roots(game: Path | None, extra: list[Path] | None = None) -> list[Path]:
    """Repo first (images_new test), then the install."""
    roots: list[Path] = []
    for raw in (extra or ()):
        path = Path(raw)
        if path.is_dir() and path not in roots:
            roots.append(path)
    for raw in (REPO_ROOT, game, REPO_ROOT / "app", REPO_ROOT / "data"):
        if raw is None:
            continue
        path = Path(raw)
        if path.is_dir() and path not in roots:
            roots.append(path)
    return roots


def resolve_image_png(
    game: Path | None,
    stem: str | None,
    *,
    roots: list[Path] | None = None,
) -> Path | None:
    """``images_new/{stem}.png`` or None. Does not look at the PL8."""
    if not stem:
        return None
    name = f"{stem}.png"
    search = roots if roots is not None else image_roots(game)
    for root in search:
        folder = _ci_dir(root, _NEW_DIR)
        if folder is None:
            continue
        hit = _ci_file(folder, name)
        if hit is not None:
            return hit
    return None


def fit_to_dest(img: Image.Image, dest_w: int, dest_h: int) -> Image.Image:
    """Fit ``img`` into dest, keep aspect, letterbox. Do not stretch."""
    src = img.convert("RGBA")
    if dest_w < 1 or dest_h < 1:
        return src
    if src.size == (dest_w, dest_h):
        return src
    scale = min(dest_w / src.width, dest_h / src.height)
    nw = max(1, int(round(src.width * scale)))
    nh = max(1, int(round(src.height * scale)))
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    if resized.size == (dest_w, dest_h):
        return resized
    canvas = Image.new("RGBA", (dest_w, dest_h), (0, 0, 0, 0))
    ox = (dest_w - nw) // 2
    oy = (dest_h - nh) // 2
    canvas.paste(resized, (ox, oy), resized)
    return canvas


def _pl8_sprite0_size(game: Path | None, pl8_name: str) -> tuple[int, int] | None:
    if game is None:
        return None
    from app.config import find_file
    import decode_pl8

    pl8 = find_file(game, pl8_name)
    if pl8 is None:
        return None
    try:
        _flags, _unk, sprites, _blob = decode_pl8.parse_pl8(pl8, verbose=False)
    except (OSError, ValueError):
        return None
    if not sprites:
        return None
    spr = sprites[0]
    return int(spr.width), int(spr.height)


def _pl8_sprite_count(game: Path | None, pl8_name: str) -> int | None:
    if game is None:
        return None
    from app.config import find_file
    import decode_pl8

    pl8 = find_file(game, pl8_name)
    if pl8 is None:
        return None
    try:
        _flags, _unk, sprites, _blob = decode_pl8.parse_pl8(pl8, verbose=False)
    except (OSError, ValueError):
        return None
    return len(sprites)


def overlay_single_image(
    game: Path | None,
    pl8_name: str,
    *,
    roots: list[Path] | None = None,
) -> tuple[Image.Image, Path] | None:
    """PNG override for a **single-blit** PL8, already fitted to dest.

    Multi-sprite sheets (HOUSES1 / BUILD1* / CITYFIXT / INT_CITY) stay on
    the PL8 — one PNG is not a frame list. ``AHOSPIT`` is one blit.
    """
    stem = pl8_stem(pl8_name)
    hit = resolve_image_png(game, stem, roots=roots)
    if hit is None:
        return None
    n = _pl8_sprite_count(game, pl8_name)
    if n is not None and n > 1:
        return None
    dest = still_dest_size(stem, game)
    img = fit_to_dest(Image.open(hit), dest[0], dest[1])
    return img, hit


def load_still(
    game: Path | None,
    stem: str,
    *,
    roots: list[Path] | None = None,
) -> tuple[Image.Image, Path, tuple[int, int]] | None:
    """PNG (images_new) or retail PL8, fitted to the native dest."""
    dest = still_dest_size(stem, game)
    hit = resolve_image_png(game, stem, roots=roots)
    if hit is not None:
        return fit_to_dest(Image.open(hit), dest[0], dest[1]), hit, dest
    if game is None:
        return None
    from app import assets

    try:
        img, path, _n = assets.load_pl8_image(
            game, f"{stem}.PL8", first_only=True, skip_override=True
        )
    except (OSError, ValueError, FileNotFoundError):
        return None
    return fit_to_dest(img, dest[0], dest[1]), path, dest


def still_screen_xy(
    dest: tuple[int, int], *, ox: int = 0
) -> tuple[int, int]:
    """Host card: left of INT_CITY. AHOSPIT PL8 x/y is (0,0) — EXE dest is not in the record."""
    dw, _dh = dest
    x = SIDEBAR_X + int(ox) - dw - 4
    y = TOP_BAR_H + 8
    return max(4, x), y


def blit_tool_still(
    frame: Image.Image,
    game: Path | None,
    tool: str | None,
    *,
    ox: int = 0,
    cache: dict | None = None,
) -> Image.Image:
    """Paste the selected-tool A* still over the iso well (front layer)."""
    stem = still_stem_for_tool(tool)
    if stem is None:
        return frame
    packed: tuple[Image.Image, Path, tuple[int, int]] | None
    if cache is not None and stem in cache:
        packed = cache[stem]
    else:
        packed = load_still(game, stem)
        if cache is not None:
            cache[stem] = packed
    if packed is None:
        return frame
    img, _path, dest = packed
    x, y = still_screen_xy(dest, ox=ox)
    out = frame.convert("RGBA")
    out.paste(img, (x, y), img)
    if frame.mode == "RGBA":
        return out
    return out.convert(frame.mode)


def images_new_overrides(game: Path | None, stems: list[str]) -> list[str]:
    """Stems that resolve from images_new (not the PL8)."""
    out: list[str] = []
    for stem in stems:
        path = resolve_image_png(game, stem)
        if path is None:
            continue
        if path.parent.name.upper() == "IMAGES_NEW":
            out.append(stem)
    return out


def selftest(game: Path | None = None) -> list[str]:
    """Pin: dummy images_new wins; missing file falls back to PL8; scale-to-dest."""
    import tempfile

    lines: list[str] = []
    dest = still_dest_size("AHOSPIT", game)
    if dest != (182, 132):
        lines.append(f"FAIL  AHOSPIT dest {dest} want 182x132")
    else:
        lines.append("ok    AHOSPIT dest 182x132 (hospital menu still, not HOUSES1 iso)")
    if still_stem_for_tool("hospital") != "AHOSPIT":
        lines.append(f"FAIL  hospital stem {still_stem_for_tool('hospital')!r}")
    else:
        lines.append("ok    TOOL_HOSPITAL -> AHOSPIT")
    if resolve_image_png(game, None) is not None:
        lines.append("FAIL  empty stem resolved")
    else:
        lines.append("ok    missing stem stays PL8")

    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        folder = root / _NEW_DIR
        folder.mkdir()
        dummy = folder / "AHOSPIT.png"
        # Wider / different res than 182×132 — must letterbox, not stretch.
        Image.new("RGBA", (400, 200), (220, 40, 40, 255)).save(dummy)
        hit = resolve_image_png(game, "AHOSPIT", roots=[root])
        if hit is None or hit.resolve() != dummy.resolve():
            lines.append(f"FAIL  dummy resolve {hit}")
        else:
            lines.append("ok    dummy images_new/AHOSPIT.png wins")
        fitted = fit_to_dest(Image.open(dummy), dest[0], dest[1])
        if fitted.size != dest:
            lines.append(f"FAIL  scale dest {fitted.size} want {dest}")
        else:
            px = fitted.getpixel((0, 0))
            mid = fitted.getpixel((dest[0] // 2, dest[1] // 2))
            # Letterbox: corners stay transparent; center is the red dummy.
            if px[3] != 0:
                lines.append(f"FAIL  letterbox corner alpha {px}")
            elif mid[0] < 180:
                lines.append(f"FAIL  scaled center {mid}")
            else:
                lines.append("ok    higher-res PNG fits 182x132 (aspect + letterbox)")
        empty = root / "empty"
        empty.mkdir()
        miss = resolve_image_png(game, "AHOSPIT", roots=[empty])
        if miss is not None:
            lines.append(f"FAIL  empty images_new still hit {miss}")
        else:
            lines.append("ok    without PNG, resolver misses (PL8 fallback)")

    if game is not None:
        from app import assets
        from app.config import find_file

        pl8 = find_file(game, "AHOUSE.PL8")
        if pl8 is None:
            lines.append("ok    AHOUSE.PL8 skip (no install)")
        else:
            img, path, n = assets.load_pl8_image(
                game, "AHOUSE.PL8", first_only=True, skip_override=True
            )
            if path.parent.name.upper() == "IMAGES_NEW":
                lines.append(f"FAIL  AHOUSE skip_override still {path}")
            elif img.size != (182, 132) or n != 1:
                lines.append(f"FAIL  AHOUSE PL8 {img.size} n={n}")
            else:
                lines.append("ok    no AHOUSE.png -> retail PL8")
        live = resolve_image_png(game, "AHOSPIT")
        if live is not None and live.parent.name.upper() == "IMAGES_NEW":
            still = load_still(game, "AHOSPIT")
            if still is None or still[0].size != dest:
                lines.append(f"FAIL  live AHOSPIT still {None if still is None else still[0].size}")
            else:
                lines.append(f"ok    live images_new/{live.name} -> {dest[0]}x{dest[1]}")
        else:
            still = load_still(game, "AHOSPIT")
            if still is None:
                lines.append("ok    no AHOSPIT.png; PL8 load skipped or missing")
            elif still[1].suffix.lower() == ".pl8" and still[0].size == dest:
                lines.append("ok    no AHOSPIT.png -> retail PL8 182x132")
            else:
                lines.append(f"FAIL  AHOSPIT fallback {still[1]} {still[0].size}")
        over = images_new_overrides(game, ["AHOSPIT", "AHOUSE"])
        if "AHOSPIT" in over:
            lines.append("ok    images_new override AHOSPIT")
        else:
            lines.append("ok    no images_new AHOSPIT (drop PNG to test in-game)")
    return lines
