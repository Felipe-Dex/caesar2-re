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

``AHOSPIT``:

* **Sidebar card** while the Hospital tool is selected (native 182×132,
  fitted into the 162 px INT_CITY strip). Never pasted onto the iso well
  — that left a painting stuck at ~ (292, 32).
* **Iso 0xFB only:** one blit on the front-most leftover of the 3×3
  (south corner), fitted to the union of the nine tall BUILD1B[86–94]
  sprite dests (zoom 0 = **174×143**). Later grass skips opaque PNG
  pixels; later buildings (market) paint on top. CITYTOP / walkers
  after. Barracks ``0xE4`` is ``HOUSES1[81–89]``.

Export spec for ``images_new/AHOSPIT.png``: one isometric painting for
the whole 3×3 (not nine tiles); transparent alpha background (flat
green/black plate is not required and is keyed out if present); match
the C2 iso camera — the building is tall (174×143 at zoom 0). Higher
res is OK; the host scales into that AABB.

Drop more files as ``images_new/{STEM}.png`` using the 8.3 stem
(``ABATHS``, ``AHOUSE``, ``AWELL``, …). PNGs are gitignored.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

from app.city_chrome import SIDEBAR_W, SIDEBAR_X, SIDEBAR_Y, TOP_BAR_H
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

# Hospital 0xFB +3=0x08 → BUILD1B. +4 0x56–0x5E → sprites 86–94.
# Barracks 0xE4 +3=0x00 → HOUSES1[81–89]. Shared *indices* 86–89, different sheet.
ID_HOSPITAL = 0xFB
ID_BARRACKS = 0xE4
HOSPITAL_DRAW = 0x08
BARRACKS_DRAW = 0x00
HOSPITAL_ISO_KEY = "BUILD1B"
HOSPITAL_ISO_FRAMES: tuple[int, ...] = (86, 87, 88, 89, 90, 91, 92, 93, 94)
AHOSPIT_SHEET_KEY = "AHOSPIT"
# Sidebar card: 182×132 fitted into the 162 px strip, above the 3×5.
STILL_CARD_PAD = 2


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
    """``images_new/{stem}.png`` or None. Does not look at the PL8.

    Uses ``REPO_ROOT`` (this file's checkout), not ``cwd``. city-only.bat
    cds to the repo, but the resolver still works if launched from elsewhere.
    """
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


def override_stamp(
    game: Path | None, stem: str, *, roots: list[Path] | None = None
) -> tuple[str, str | None, int]:
    """Identity of the current PNG (path + mtime). Changes when a file is dropped."""
    hit = resolve_image_png(game, stem, roots=roots)
    if hit is None:
        return (stem.upper(), None, 0)
    try:
        mtime = int(hit.stat().st_mtime_ns)
        return (stem.upper(), str(hit.resolve()), mtime)
    except OSError:
        return (stem.upper(), str(hit), 0)


# Classic sprite keys. Keep real alpha; punch only these plates.
_KEY_RGB: tuple[tuple[int, int, int], ...] = (
    (0, 0, 0),
    (255, 0, 255),
    (0, 255, 0),
)
_KEY_TOL = 12


def key_sprite_plate(img: Image.Image) -> Image.Image:
    """Keep PNG alpha; treat flat black / magenta / lime as transparent."""
    src = img.convert("RGBA")
    out: list[tuple[int, int, int, int]] = []
    punched = False
    for r, g, b, a in src.getdata():
        if a and any(
            abs(r - kr) <= _KEY_TOL
            and abs(g - kg) <= _KEY_TOL
            and abs(b - kb) <= _KEY_TOL
            for kr, kg, kb in _KEY_RGB
        ):
            out.append((r, g, b, 0))
            punched = True
        else:
            out.append((r, g, b, a))
    if not punched:
        return src
    src.putdata(out)
    return src


def fit_to_dest(img: Image.Image, dest_w: int, dest_h: int) -> Image.Image:
    """Fit ``img`` into dest, keep aspect, letterbox. Do not stretch."""
    src = key_sprite_plate(img)
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


def still_card_size(native: tuple[int, int]) -> tuple[int, int]:
    """Fit the 182×132 still into the sidebar (never the iso well)."""
    nw, nh = native
    max_w = max(1, SIDEBAR_W - STILL_CARD_PAD * 2)
    max_h = max(1, SIDEBAR_Y - TOP_BAR_H - STILL_CARD_PAD * 2)
    scale = min(max_w / max(1, nw), max_h / max(1, nh), 1.0)
    return max(1, int(round(nw * scale))), max(1, int(round(nh * scale)))


def still_screen_xy(
    dest: tuple[int, int], *, ox: int = 0
) -> tuple[int, int]:
    """Sidebar card, above the 3×5. x is always ≥ SIDEBAR_X + ox."""
    _dw, dh = dest
    x = SIDEBAR_X + int(ox) + STILL_CARD_PAD
    y = max(TOP_BAR_H + STILL_CARD_PAD, SIDEBAR_Y - dh - STILL_CARD_PAD)
    return x, y


def attach_ahospit_source(
    sheets: dict[str, list[Image.Image]],
    game: Path | None,
    *,
    roots: list[Path] | None = None,
) -> list[str]:
    """Park the PNG on ``sheets['AHOSPIT']``. Do not mutate HOUSES1 / BUILD1B.

    ``city_map`` blits it once per ``0xFB`` origin into the 3×3 AABB.
    """
    hit = resolve_image_png(game, "AHOSPIT", roots=roots)
    if hit is None:
        sheets.pop(AHOSPIT_SHEET_KEY, None)
        return []
    try:
        src = key_sprite_plate(Image.open(hit).convert("RGBA"))
    except OSError:
        return []
    sheets[AHOSPIT_SHEET_KEY] = [src]
    return [f"{AHOSPIT_SHEET_KEY} {src.size[0]}x{src.size[1]} -> 0xFB BUILD1B"]


def apply_ahospit_iso(
    sheets: dict[str, list[Image.Image]],
    game: Path | None,
    *,
    roots: list[Path] | None = None,
) -> list[str]:
    """Back-compat name: attach source only (no HOUSES1 smash)."""
    return attach_ahospit_source(sheets, game, roots=roots)


def hospital_has_override(
    sheets: dict[str, list[Image.Image]] | None,
) -> bool:
    """True when AHOSPIT.png is parked on the city sheets."""
    if not sheets:
        return False
    return bool(sheets.get(AHOSPIT_SHEET_KEY))


def hospital_iso_sprite(
    sheets: dict[str, list[Image.Image]] | None,
    dest_w: int,
    dest_h: int,
) -> Image.Image | None:
    """AHOSPIT.png fitted to dest (3×3 AABB or sidebar card), or None."""
    if not sheets:
        return None
    srcs = sheets.get(AHOSPIT_SHEET_KEY)
    if not srcs:
        return None
    return fit_to_dest(key_sprite_plate(srcs[0]), dest_w, dest_h)


def blit_tool_still(
    frame: Image.Image,
    game: Path | None,
    tool: str | None,
    *,
    ox: int = 0,
    cache: dict | None = None,
) -> Image.Image:
    """Sidebar card only, while that tool is selected. Cleared when tool changes.

    Cache is keyed by ``override_stamp`` so a PNG dropped after launch
    replaces a PL8 surface on the next blit.
    """
    stem = still_stem_for_tool(tool)
    if stem is None:
        return frame
    stamp = override_stamp(game, stem)
    packed: tuple[Image.Image, Path, tuple[int, int]] | None
    prev = cache.get(stem) if cache is not None else None
    if prev is not None and prev[0] == stamp:
        packed = prev[1]
    else:
        packed = load_still(game, stem)
        if cache is not None:
            cache[stem] = (stamp, packed)
    if packed is None:
        return frame
    native = packed[2]
    card = still_card_size(native)
    img = fit_to_dest(packed[0], card[0], card[1])
    x, y = still_screen_xy(card, ox=ox)
    if x < SIDEBAR_X + int(ox):
        return frame
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
        lines.append("ok    AHOSPIT dest 182x132 sidebar card / 0xFB BUILD1B iso")
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
        houses = [Image.new("RGBA", (58, 30), (10, 20, 30, 255)) for _ in range(90)]
        houses[86] = Image.new("RGBA", (58, 56), (10, 20, 30, 255))
        sheets = {"HOUSES1": houses, "BUILD1B": []}
        applied = attach_ahospit_source(sheets, game, roots=[root])
        over = hospital_iso_sprite(sheets, 58, 83)
        mid = over.getpixel((29, 41)) if over is not None else (0, 0, 0, 0)
        if not applied or over is None or over.size != (58, 83) or mid[0] < 180:
            lines.append(f"FAIL  attach 0xFB {applied} {None if over is None else over.size} mid={mid}")
        elif houses[86].getpixel((29, 28))[0] != 10:
            lines.append("FAIL  HOUSES1[86] mutated (barracks leftover)")
        else:
            lines.append("ok    AHOSPIT attached for 0xFB; HOUSES1[86] untouched")
        from app.city_map import (
            CityMap,
            hospital_diamond_aabb,
            hospital_override_dest,
            hospital_sprite_aabb,
            tile_iso_xy,
        )

        gx, gy, gw, gh = hospital_diamond_aabb(10, 10)
        ax, ay, aw, ah = hospital_sprite_aabb(10, 10, sheets)
        if (gw, gh) != (174, 90):
            lines.append(f"FAIL  ground diamond AABB {gw}x{gh} want 174x90")
        elif (aw, ah) != (174, 143):
            lines.append(f"FAIL  tall BUILD1B AABB {aw}x{ah} want 174x143 (not 174x90)")
        else:
            lines.append("ok    dest rect = BUILD1B[86-94] union 174x143 (not 174x90)")
        plate = Image.new("RGBA", (8, 8), (0, 255, 0, 255))
        plate.putpixel((3, 3), (200, 40, 40, 255))
        plate.putpixel((0, 0), (255, 0, 255, 255))
        plate.putpixel((7, 7), (0, 0, 0, 255))
        keyed = key_sprite_plate(plate)
        if keyed.getpixel((1, 1))[3] != 0 or keyed.getpixel((3, 3))[3] != 255:
            lines.append(f"FAIL  chroma key {keyed.getpixel((1, 1))} mid={keyed.getpixel((3, 3))}")
        elif keyed.getpixel((0, 0))[3] != 0 or keyed.getpixel((7, 7))[3] != 0:
            lines.append("FAIL  magenta/black plate not keyed")
        else:
            lines.append("ok    chroma keys lime/magenta/black; building stays")
        pin_city = CityMap()
        dests: list[tuple[int, int, int, int]] = []
        for ox, oy in ((10, 10), (20, 14)):
            for row in range(3):
                for col in range(3):
                    off = pin_city.offset(ox + col, oy + row)
                    pin_city.tiles[off] = ID_HOSPITAL
                    pin_city.tiles[off + 3] = HOSPITAL_DRAW
                    pin_city.tiles[off + 4] = 0x56 + row * 3 + col
                    pin_city.tiles[off + 5] = row * 3 + col
                    t = pin_city.tile(ox + col, oy + row)
                    sx, sy = tile_iso_xy(ox + col, oy + row)
                    d = hospital_override_dest(
                        t, sx, sy, ox + col, oy + row, sheets
                    )
                    if d is not None:
                        dests.append(d)
        unique = set(dests)
        if len(dests) != 2 or len(unique) != 2:
            lines.append(f"FAIL  hospital dests {len(dests)} unique={len(unique)} want 2")
        else:
            lines.append("ok    one blit per 0xFB origin (not 9)")
        from app.city_map import hospital_front_xy, iso_sprite_dest, render_iso

        if hospital_front_xy(10, 10) != (12, 12):
            lines.append(f"FAIL  front cell {hospital_front_xy(10, 10)} want (12, 12)")
        else:
            lines.append("ok    front-most 0xFB cell is south corner (12, 12)")
        grass = [Image.new("RGBA", (58, 30), (0, 200, 0, 255)) for _ in range(50)]
        sheets["CITYFIXT"] = grass
        sheets[AHOSPIT_SHEET_KEY] = [Image.new("RGBA", (174, 143), (220, 30, 30, 255))]
        b1b = [Image.new("RGBA", (58, 30), (0, 0, 0, 0)) for _ in range(100)]
        from app.city_map import _HOSPITAL_Z0_WH

        for var, (bw, bh) in _HOSPITAL_Z0_WH.items():
            b1b[var] = Image.new("RGBA", (bw, bh), (1, 2, 3, 255))
        for idx in (0x30, 0x31, 0x32, 0x33):
            b1b[idx] = Image.new("RGBA", (58, 70), (40, 40, 220, 255))
        sheets["BUILD1B"] = b1b
        for y in range(pin_city.height):
            for x in range(pin_city.width):
                if pin_city.tile(x, y).terrain_id != ID_HOSPITAL:
                    pin_city.tiles[pin_city.offset(x, y)] = 0x14
        world = render_iso(pin_city, sheets=sheets, zoom=0)
        gax, gay, gaw, gah = hospital_sprite_aabb(10, 10, sheets)
        gsx, gsy = tile_iso_xy(10, 13)
        ox0, oy0 = max(gax, gsx), max(gay, gsy)
        ox1, oy1 = min(gax + gaw, gsx + 58), min(gay + gah, gsy + 30)
        if ox1 <= ox0 or oy1 <= oy0:
            lines.append("FAIL  south grass does not overlap hospital AABB")
        else:
            pix = world.getpixel(((ox0 + ox1) // 2, (oy0 + oy1) // 2))
            if pix[0] < 180 or pix[1] > 80:
                lines.append(f"FAIL  south grass covered PNG {pix}")
            else:
                lines.append("ok    grass south of 0xFB does not cover the PNG")
        market_vars = (0x30, 0x32, 0x31, 0x33)
        for i, (mx, my) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
            off = pin_city.offset(12 + mx, 13 + my)
            pin_city.tiles[off] = 0xFC
            pin_city.tiles[off + 3] = HOSPITAL_DRAW
            pin_city.tiles[off + 4] = market_vars[i]
            pin_city.tiles[off + 5] = i
        world = render_iso(pin_city, sheets=sheets, zoom=0)
        msx, msy = tile_iso_xy(12, 13)
        mpx, mpy = iso_sprite_dest(msx, msy, 70, 30)
        mx0, my0 = max(gax, mpx), max(gay, mpy)
        mx1, my1 = min(gax + gaw, mpx + 58), min(gay + gah, mpy + 70)
        if mx1 <= mx0 or my1 <= my0:
            lines.append("FAIL  market south of 0xFB does not overlap PNG")
        else:
            mpix = world.getpixel(((mx0 + mx1) // 2, (my0 + my1) // 2))
            if mpix[2] < 180 or mpix[0] > 80:
                lines.append(f"FAIL  hospital PNG covered market {mpix}")
            else:
                lines.append("ok    market south of 0xFB draws on top of the PNG")
        card = still_card_size((182, 132))
        cx, cy = still_screen_xy(card, ox=0)
        if cx < SIDEBAR_X or cx + card[0] > SIDEBAR_X + SIDEBAR_W:
            lines.append(f"FAIL  still card leaves sidebar {cx},{cy} {card}")
        else:
            lines.append(f"ok    still card in sidebar {cx},{cy} {card[0]}x{card[1]}")
        stamp_a = override_stamp(game, "AHOSPIT", roots=[root])
        stamp_b = override_stamp(game, "AHOSPIT", roots=[empty])
        if stamp_a[1] is None or stamp_b[1] is not None or stamp_a == stamp_b:
            lines.append(f"FAIL  stamp {stamp_a} {stamp_b}")
        else:
            lines.append("ok    override stamp changes when PNG appears")

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
                lines.append(f"ok    resolve {live}")
            from app.city_map import building_sprite_image

            raw_h1, _p1 = assets.load_pl8_frames(game, "HOUSES1.PL8")
            raw_b1b, _p2 = assets.load_pl8_frames(game, "BUILD1B.PL8")
            sheets = assets.load_city_map_sheets(game, zoom=0)
            h1 = sheets.get("HOUSES1")
            if h1 is None or len(h1) <= 86:
                lines.append("FAIL  city sheets missing HOUSES1[86]")
            elif h1[86].getpixel((29, 28)) != raw_h1[86].getpixel((29, 28)):
                lines.append("FAIL  HOUSES1[86] still smashed (barracks 0xE4)")
            else:
                lines.append("ok    HOUSES1[81-89] still retail (barracks 0xE4)")
            hosp = building_sprite_image(ID_HOSPITAL, HOSPITAL_DRAW, 0x56, sheets)
            retail_h = raw_b1b[86] if len(raw_b1b) > 86 else None
            if hosp is None or retail_h is None:
                lines.append("FAIL  0xFB BUILD1B[86] blit missing")
            elif hosp.size != retail_h.size:
                lines.append(f"FAIL  0xFB dest {hosp.size} vs BUILD1B[86] {retail_h.size}")
            elif hosp.getpixel((29, hosp.size[1] // 2)) != retail_h.getpixel(
                (29, retail_h.size[1] // 2)
            ):
                lines.append("FAIL  leftover BUILD1B[86] smashed (painter skips it)")
            else:
                lines.append("ok    leftover BUILD1B[86] stays PL8 (one AABB blit)")
            barr = building_sprite_image(ID_BARRACKS, BARRACKS_DRAW, 0x51, sheets)
            if barr is None or barr.size != raw_h1[81].size:
                lines.append(f"FAIL  0xE4 dest {None if barr is None else barr.size}")
            elif barr.getpixel((29, 28)) != raw_h1[81].getpixel((29, 28)):
                lines.append("FAIL  0xE4 barracks blit used AHOSPIT")
            else:
                lines.append("ok    0xE4 barracks blit stays HOUSES1 PL8")
            import os

            old = os.getcwd()
            try:
                os.chdir(Path(old).anchor)
                again = resolve_image_png(game, "AHOSPIT")
            finally:
                os.chdir(old)
            if again is None or again.resolve() != live.resolve():
                lines.append(f"FAIL  resolve depends on cwd {again}")
            else:
                lines.append("ok    resolve ignores cwd (city-only.bat / REPO_ROOT)")
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
