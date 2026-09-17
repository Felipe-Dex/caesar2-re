"""title_screen 0x5D37F + chrome 0x5AFC6 — opening menu (not City Only).

EXE boot (findings/ghidra_walk.md): ``logo1.pl8`` / ``logo2.pl8`` (Sierra /
Impressions) live on the 1.1A tree; ``title_screen`` loads ``backgrnd.256`` +
``backgrnd.pl8`` (640×480) then jumps to menu chrome. C2.ENG **[38]** names
the title items. Career / REGIONS is shown, not hosted.

``--city-only`` never enters this module's screen — it stays ``city``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.city_chrome import SCREEN_H, SCREEN_W
from app.config import find_file
from app.menus import (
    HostOptions,
    MenuReport,
    OPT_ANIM,
    OPT_MUSIC,
    OPT_SOUND,
    SLOT_OPTIONS,
    decorate_item,
)

SCREEN_TITLE = "title"
SCREEN_CITY = "city"

ACTION_NEW = "new_city"
ACTION_LOAD = "load"
ACTION_OPTIONS = "options"
ACTION_QUIT = "quit"
ACTION_CAREER = "career"

# C2.ENG packed run from CITY-ONLY MODE [38].
ENG_TITLE = 38
SKIP_NEW = 21
SKIP_LOAD = 20
SKIP_QUIT = 23
SKIP_CAMPAIGN = 15
SKIP_CAREER_YES = 16
SKIP_CAREER_STUB = 1
SKIP_GAME_OPTIONS = 8
ENG_FILE = 0
SKIP_OPTIONS = 5
ENG_VERSION = 10

# BACKGRND.PL8 is one 640×480 bitmap (no painted buttons). Chrome sits over
# the lower-left city — same gold outline family as File/Options reports.
PANEL_X = 28
PANEL_Y = 248
PANEL_W = 292
HEADER_H = 28
ITEM_H = 22
ITEM_PAD_X = 10

TITLE_PL8 = "backgrnd.pl8"
TITLE_PAL = "backgrnd.256"
LOGO_PL8S: tuple[str, ...] = ("LOGO1.PL8", "LOGO2.PL8")
LOGO_MS = 1600

_GOLD = (255, 228, 160, 255)
_DIM = (140, 128, 96, 255)
_INK = (220, 230, 210, 255)
_PANEL = (8, 24, 22, 220)
_OUTLINE = (200, 180, 90, 255)


@dataclass(frozen=True)
class TitleItem:
    action: str
    label: str
    rect: tuple[int, int, int, int]
    enabled: bool = True


@dataclass
class TitleSession:
    """Window-free title/menu state. ``--city-only`` starts on the city."""

    screen: str = SCREEN_TITLE
    toast: str = ""
    options_open: bool = False

    def apply(self, action: str, *, stub: str = "") -> str:
        if action == ACTION_NEW:
            self.screen = SCREEN_CITY
            self.toast = ""
            self.options_open = False
            return ACTION_NEW
        if action == ACTION_CAREER:
            self.toast = stub or "not in this build"
            return ACTION_CAREER
        if action == ACTION_OPTIONS:
            self.options_open = True
            return ACTION_OPTIONS
        if action == ACTION_LOAD:
            return ACTION_LOAD
        if action == ACTION_QUIT:
            return ACTION_QUIT
        return action


def launch_screen(*, city_only: bool) -> str:
    """Boot surface. City Only skips logos + title."""
    return SCREEN_CITY if city_only else SCREEN_TITLE


def launch_screen_from_argv(argv: list[str] | None = None) -> str:
    """Argv without a window. ``--city-only`` → city; else title/menu."""
    raw = list(argv or [])
    return launch_screen(city_only="--city-only" in raw)


def _eng(eng, slot: int, skip: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, skip)
        if got:
            return got.rstrip()
    return fallback


def career_stub_text(eng=None) -> str:
    return _eng(
        eng,
        ENG_TITLE,
        SKIP_CAREER_STUB,
        "This feature is used in the full campaign game.",
    )


def menu_items(*, eng=None) -> list[TitleItem]:
    """Original title pack + Options. Career is listed, gray, no-op."""
    rows: tuple[tuple[str, str, bool], ...] = (
        (
            ACTION_NEW,
            _eng(eng, ENG_TITLE, SKIP_NEW, "Start a New Game"),
            True,
        ),
        (
            ACTION_CAREER,
            _eng(eng, ENG_TITLE, SKIP_CAMPAIGN, "Campaign?"),
            False,
        ),
        (
            ACTION_LOAD,
            _eng(eng, ENG_TITLE, SKIP_LOAD, "Load a Previously Saved Game"),
            True,
        ),
        (
            ACTION_OPTIONS,
            _eng(eng, ENG_FILE, SKIP_OPTIONS, "Options"),
            True,
        ),
        (
            ACTION_QUIT,
            _eng(eng, ENG_TITLE, SKIP_QUIT, "Exit the Game"),
            True,
        ),
    )
    out: list[TitleItem] = []
    y = PANEL_Y + HEADER_H
    for action, label, enabled in rows:
        out.append(
            TitleItem(
                action=action,
                label=label,
                rect=(PANEL_X, y, PANEL_W, ITEM_H),
                enabled=enabled,
            )
        )
        y += ITEM_H
    return out


def item_at(
    x: int, y: int, items: list[TitleItem] | None = None, *, eng=None
) -> TitleItem | None:
    rows = items if items is not None else menu_items(eng=eng)
    for item in rows:
        rx, ry, rw, rh = item.rect
        if rx <= x < rx + rw and ry <= y < ry + rh:
            return item
    return None


def click_title(
    x: int, y: int, items: list[TitleItem] | None = None, *, eng=None
) -> str | None:
    hit = item_at(x, y, items, eng=eng)
    if hit is None:
        return None
    return hit.action


def options_report(options: HostOptions | None = None, *, eng=None) -> MenuReport:
    """In-game Options subset (Music / Sound / Animations). No Career."""
    opt = options if options is not None else HostOptions()
    title = _eng(eng, ENG_TITLE, SKIP_GAME_OPTIONS, "Caesar II - Game Options")
    lines = (
        decorate_item(
            SLOT_OPTIONS, OPT_MUSIC, _eng(eng, ENG_FILE, 6, "Music"),
            eng=eng, options=opt,
        ),
        decorate_item(
            SLOT_OPTIONS, OPT_SOUND, _eng(eng, ENG_FILE, 7, "Sound"),
            eng=eng, options=opt,
        ),
        decorate_item(
            SLOT_OPTIONS, OPT_ANIM, _eng(eng, ENG_FILE, 8, "Animations"),
            eng=eng, options=opt,
        ),
    )
    return MenuReport(title, lines)


def load_boot_logos(game: Path) -> list[tuple[str, Image.Image]]:
    """Sierra then Impressions — only if both PL8s resolve from the install."""
    from app import assets

    out: list[tuple[str, Image.Image]] = []
    for name in LOGO_PL8S:
        if find_file(game, name) is None:
            continue
        try:
            img, path, _n = assets.load_pl8_image(game, name, first_only=True)
        except (OSError, ValueError):
            continue
        out.append((path.name, img))
    return out


def load_title_background(game: Path) -> tuple[Image.Image, str, int]:
    """``title_screen`` 0x5D37F — ``backgrnd.pl8`` + ``backgrnd.256``."""
    from app import assets

    img, path, n = assets.load_pl8_image(game, TITLE_PL8, first_only=True)
    return img, path.name, n


def compose_title(
    background: Image.Image | None,
    *,
    eng=None,
    extra: str | None = None,
    items: list[TitleItem] | None = None,
) -> Image.Image:
    """640×480 title: retail BACKGRND + C2.ENG chrome. No debug HUD."""
    if background is not None:
        base = background.convert("RGBA")
        if base.size != (SCREEN_W, SCREEN_H):
            canvas = Image.new("RGBA", (SCREEN_W, SCREEN_H), (12, 16, 28, 255))
            src = base
            if src.width > SCREEN_W or src.height > SCREEN_H:
                src = src.copy()
                src.thumbnail((SCREEN_W, SCREEN_H), Image.Resampling.NEAREST)
            x = (SCREEN_W - src.width) // 2
            y = (SCREEN_H - src.height) // 2
            canvas.paste(src, (x, y), src)
            base = canvas
    else:
        base = Image.new("RGBA", (SCREEN_W, SCREEN_H), (12, 16, 28, 255))
    overlay = Image.new("RGBA", (SCREEN_W, SCREEN_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    rows = items if items is not None else menu_items(eng=eng)
    bottom = PANEL_Y + HEADER_H + ITEM_H * len(rows) + 8
    draw.rectangle(
        (PANEL_X, PANEL_Y, PANEL_X + PANEL_W - 1, bottom - 1),
        fill=_PANEL,
        outline=_OUTLINE,
    )
    header = _eng(eng, ENG_VERSION, 0, "Caesar II - Version 1.1")
    draw.text((PANEL_X + ITEM_PAD_X, PANEL_Y + 8), header[:42], fill=_GOLD, font=font)
    for item in rows:
        rx, ry, _rw, _rh = item.rect
        fill = _GOLD if item.enabled else _DIM
        draw.text((rx + ITEM_PAD_X, ry + 4), item.label[:44], fill=fill, font=font)
    if extra:
        draw.rectangle(
            (6, SCREEN_H - 28, SCREEN_W - 7, SCREEN_H - 7),
            fill=(0, 0, 0, 170),
        )
        draw.text((14, SCREEN_H - 24), extra[:88], fill=_INK, font=font)
    return Image.alpha_composite(base, overlay).convert("RGB")


def selftest() -> list[str]:
    lines: list[str] = []
    if launch_screen(city_only=False) != SCREEN_TITLE:
        lines.append("FAIL  no --city-only must start at title")
    else:
        lines.append("ok    argv without --city-only starts at title/menu")
    if launch_screen(city_only=True) != SCREEN_CITY:
        lines.append("FAIL  --city-only must start on city")
    else:
        lines.append("ok    --city-only starts on city map")
    if launch_screen_from_argv([]) != SCREEN_TITLE:
        lines.append("FAIL  empty argv not title")
    elif launch_screen_from_argv(["--new", "--city-only"]) != SCREEN_CITY:
        lines.append("FAIL  --new --city-only argv not city")
    elif launch_screen_from_argv(["--check", "--no-audio"]) != SCREEN_TITLE:
        lines.append("FAIL  --check without --city-only left title")
    else:
        lines.append("ok    argv parse title vs --city-only")

    items = menu_items()
    actions = [it.action for it in items]
    if ACTION_NEW not in actions or ACTION_LOAD not in actions:
        lines.append(f"FAIL  title items {actions}")
    elif ACTION_OPTIONS not in actions or ACTION_QUIT not in actions:
        lines.append(f"FAIL  title items {actions}")
    elif ACTION_CAREER not in actions:
        lines.append("FAIL  Career button missing")
    else:
        lines.append("ok    title lists New / Career / Load / Options / Quit")
    career = next(it for it in items if it.action == ACTION_CAREER)
    if career.enabled:
        lines.append("FAIL  Career must stay disabled")
    else:
        lines.append("ok    Career listed gray (no campaign)")

    new = next(it for it in items if it.action == ACTION_NEW)
    nx, ny, _nw, _nh = new.rect
    if click_title(nx + 4, ny + 4, items) != ACTION_NEW:
        lines.append("FAIL  click New City miss")
    else:
        lines.append("ok    click New City hits Start a New Game")
    session = TitleSession()
    if session.screen != SCREEN_TITLE:
        lines.append("FAIL  session default not title")
    elif session.apply(ACTION_NEW) != ACTION_NEW or session.screen != SCREEN_CITY:
        lines.append(f"FAIL  New City stay {session.screen!r}")
    else:
        lines.append("ok    click New City transitions to city")
    stuck = TitleSession()
    stub = career_stub_text()
    if stuck.apply(ACTION_CAREER, stub=stub) != ACTION_CAREER:
        lines.append("FAIL  Career action")
    elif stuck.screen != SCREEN_TITLE:
        lines.append("FAIL  Career must not enter city")
    elif "campaign" not in stuck.toast.lower() and "not in this build" not in stuck.toast.lower():
        lines.append(f"FAIL  Career stub {stuck.toast!r}")
    else:
        lines.append("ok    Career click stays on title (campaign stub)")

    frame = compose_title(None)
    if frame.size != (SCREEN_W, SCREEN_H):
        lines.append(f"FAIL  title compose {frame.size}")
    else:
        lines.append("ok    title compose 640x480")

    try:
        from app.assets import load_eng
        from app.config import resolve_game_dir

        game, _why = resolve_game_dir()
        eng = load_eng(game)
        if eng.skip(ENG_TITLE, SKIP_NEW) != "Start a New Game":
            lines.append(f"FAIL  C2.ENG [38]+21 {eng.skip(ENG_TITLE, SKIP_NEW)!r}")
        elif eng.skip(ENG_TITLE, SKIP_LOAD) != "Load a Previously Saved Game":
            lines.append(f"FAIL  C2.ENG [38]+20 {eng.skip(ENG_TITLE, SKIP_LOAD)!r}")
        elif find_file(game, TITLE_PL8) is None:
            lines.append("FAIL  backgrnd.pl8 missing")
        else:
            lines.append("ok    C2.ENG title pack + backgrnd.pl8 resolve")
        logos = [name for name in LOGO_PL8S if find_file(game, name) is not None]
        if logos:
            lines.append(f"ok    boot logos on disk: {', '.join(logos)}")
        else:
            lines.append("ok    boot logos absent (skip splash)")
        mandate = eng.skip(69, 4) or ""
        if "fulfilled the mandate" not in mandate.lower():
            lines.append(f"FAIL  C2.ENG [69]+4 {mandate!r}")
        else:
            lines.append("ok    mandate line is C2.ENG [69]+4 (A01.RAW, not title)")
    except (OSError, ValueError, ImportError):
        lines.append("ok    title ENG/PL8 skipped (no install)")
    from app.advisor_video import advisor_plays_audio
    from app.audio import MANDATE_RAW, TITLE_XMI, title_boot_audio

    if title_boot_audio(city_only=False, play_audio=True) != TITLE_XMI:
        lines.append("FAIL  title boot is not forum1.xmi")
    elif title_boot_audio(city_only=True, play_audio=True) != "city_sfx":
        lines.append("FAIL  city-only still wants title music")
    elif MANDATE_RAW[:3].lower() in title_boot_audio(city_only=False, play_audio=True).lower():
        lines.append("FAIL  A01 mandate still on title boot")
    else:
        lines.append("ok    title boot does not start A01/mandate")
    hail = type("M", (), {"slot": 79, "key": "hail"})()
    year = type("M", (), {"slot": 83, "key": "year"})()
    if not advisor_plays_audio(hail) or not advisor_plays_audio(year):
        lines.append("FAIL  Hail/year must keep mp4 audio")
    else:
        lines.append("ok    Hail [79] / New Year [83] still have mp4 audio")
    return lines
