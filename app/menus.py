"""City Only top menu — File / Options / Speed / Help (C2.ENG [0]…[3]).

Host also adds **Disasters** (not C2.ENG) so testers can force Fire /
Barbarian / Riot onto the real walker and 69A37 paths.

Actions match 1.1A City Only strings. No Career empire / Forum PERSONAL.
File→Save always lists `{repo}/sav/*.SAV` (click to overwrite, or type a
new 8.3). First F5 this session shows that list; later F5 overwrites the
last picked slot. No OS file dialog. Owned chunks live, rest zero.
Census is Options+5 (Census Panel [74]), not an overlay-filter.
Keyboard table: C2MANUAL.DOC p.48 — see CITY_ONLY_KEYS / CITY_ONLY_LEFTOVERS.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.city_map import MAP_H, MAP_W, TILE_STRIDE
from app.city_paint import HOUSE_OCCUPANCY, ID_HOUSING_HI, ID_HOUSING_LO, recount_population
from app.config import find_file

# C2.ENG packed run from File [0]. Official skip per title.
SLOT_FILE, SLOT_OPTIONS, SLOT_SPEED, SLOT_HELP = 0, 1, 2, 3
# Host-only tester menu. Not a C2.ENG packed slot — do not _eng_skip(4).
SLOT_DISASTERS = 4
FILE_NEW, FILE_LOAD, FILE_SAVE, FILE_QUIT = 1, 2, 3, 4
OPT_MUSIC, OPT_SOUND, OPT_ANIM, OPT_YEAR, OPT_CENSUS = 1, 2, 3, 4, 5
SPD_GAME, SPD_SCROLL, SPD_PAUSE = 1, 2, 3
HLP_HINTS, HLP_GAME, HLP_HISTORY, HLP_ICONS, HLP_ABOUT = 1, 2, 3, 4, 5
DIS_FIRE, DIS_BARBARIAN, DIS_RIOT = 1, 2, 3
DISASTER_TITLE = "Disasters"
DISASTER_ITEMS: tuple[tuple[int, str], ...] = (
    (DIS_FIRE, "Fire"),
    (DIS_BARBARIAN, "Barbarian"),
    (DIS_RIOT, "Riot"),
)

# HELP.ENG 58 B records @ 66 (forum_strings.md). Title u32 + body is the next C-string.
_HELP_MAGIC = b"Helpfile"
_HELP_REC = 58
_HELP_TABLE = 66
HELP_TOPIC_GAME = 0
HELP_TOPIC_HISTORY = 2
HELP_TOPIC_ICONS = 91
HELP_TOPIC_HINTS = 119

# [23] Tent…Mansion cover hut…villa grades; palaces are C2MODEL 30–31 only.
_HOUSE_FAMILIES: tuple[tuple[int, int, int | None, str], ...] = (
    (0, 6, 0, "Tent"),
    (6, 12, 1, "Shack"),
    (12, 20, 2, "Insula"),
    (20, 26, 3, "Domus"),
    (26, 30, 4, "Mansion"),
    (30, 32, None, "Palaces"),
)

_REPORT_X, _REPORT_Y = 16, 40
_REPORT_W, _REPORT_H = 320, 200
# Advisor banner — offset from Query (16,40) / Census so we do not share
# the Query OK gadget. Click-to-dismiss; EXE [78] is right-click.
_ADV_X, _ADV_Y = 72, 88
_ADV_W = 360
_ADV_LINE = 44


@dataclass
class HostOptions:
    """In-game Options / Speed extras. Miles/XMI and sav_year_end are not hosted."""

    music: bool = False
    sound: bool = True
    animations: bool = True
    auto_save: bool = False  # leftover — host does not write lastyear.sav
    annual_summary: bool = True  # [56]+6 / FUN_00061389 panel
    scroll_step: int = 1  # 1…3 × PAN_STEP


@dataclass(frozen=True)
class MenuReport:
    title: str
    lines: tuple[str, ...]


def _off(x: int, y: int) -> int:
    return y * MAP_W * TILE_STRIDE + x * TILE_STRIDE


def _eng(eng, slot: int, skip: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, skip)
        if got:
            return got.rstrip()
    return fallback


def on_off(eng, on: bool) -> str:
    return _eng(eng, 56, 3, "ON") if on else _eng(eng, 56, 2, "OFF")


def decorate_item(
    slot: int,
    skip: int,
    label: str,
    *,
    eng=None,
    options: HostOptions | None = None,
    sim=None,
) -> str:
    """Suffix ON/OFF / Play / Faster / scroll ×N — labels stay C2.ENG."""
    opt = options if options is not None else HostOptions()
    if slot == SLOT_OPTIONS:
        if skip == OPT_MUSIC:
            return f"{label}  {on_off(eng, opt.music)}"
        if skip == OPT_SOUND:
            return f"{label}  {on_off(eng, opt.sound)}"
        if skip == OPT_ANIM:
            return f"{label}  {on_off(eng, opt.animations)}"
        if skip == OPT_YEAR:
            return f"{label}  {on_off(eng, opt.annual_summary)}"
    if slot == SLOT_SPEED and sim is not None:
        if skip == SPD_GAME:
            if getattr(sim, "paused", False):
                return label
            if getattr(sim, "catchup", 0):
                return f"{label}  Faster"
            return f"{label}  Play"
        if skip == SPD_SCROLL:
            return f"{label}  {max(1, int(opt.scroll_step))}x"
        if skip == SPD_PAUSE and getattr(sim, "paused", False):
            return f"{label}  *"
    return label


def census_counts(tiles: bytearray) -> dict[str, int]:
    """Housing origins only (+5 lo == 0), same gate as recount_population."""
    out = {name: 0 for _a, _b, _sk, name in _HOUSE_FAMILIES}
    out["origins"] = 0
    if len(tiles) < MAP_W * MAP_H * TILE_STRIDE:
        return out
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            if tiles[off + 5] & 0xF:
                continue
            hid = tiles[off]
            if not (ID_HOUSING_LO <= hid <= ID_HOUSING_HI):
                continue
            grade = hid - ID_HOUSING_LO
            out["origins"] += 1
            for lo, hi, _sk, name in _HOUSE_FAMILIES:
                if lo <= grade < hi:
                    out[name] += 1
                    break
    return out


def census_report(tiles: bytearray, *, eng=None, population: int | None = None) -> MenuReport:
    """Census Panel [74] — pop we already count; no invented employment."""
    title = _eng(eng, 74, 0, "Census Panel")
    intro = _eng(eng, 74, 1, "The current records show:")
    pop_lab = _eng(eng, 74, 2, "City population is")
    pop = recount_population(tiles) if population is None else int(population)
    counts = census_counts(tiles)
    lines = [intro, f"{pop_lab} {pop}"]
    for _lo, _hi, skip, fallback in _HOUSE_FAMILIES:
        n = counts[fallback]
        if n <= 0:
            continue
        name = _eng(eng, 23, skip, fallback) if skip is not None else fallback
        lines.append(f"{name}  {n}")
    return MenuReport(title, tuple(lines[:12]))


def _year_delta(cur: int, prev: int, eng) -> str:
    """0x61497 — jl → [72]+8 (DOWN); else [72]+7 (UP). Equal is (UP 0)."""
    if int(cur) < int(prev):
        word = _eng(eng, 72, 8, "(DOWN")
        return f"{word} {int(prev) - int(cur)})"
    word = _eng(eng, 72, 7, "(UP")
    return f"{word} {int(cur) - int(prev)})"


def lose_game_report(*, eng=None) -> MenuReport:
    """C2.ENG [45] GAME OVER — 0x59aa7 panel. City Only bankruptcy end."""
    title = _eng(eng, 45, 0, "GAME OVER")
    body = _eng(
        eng,
        45,
        1,
        "Your poor decisions have cost you your future.  Stripped of all "
        "rank, position and honors, the Empire has another destiny planned for you...",
    )
    return MenuReport(title, tuple(_wrap_adv(body, 44)))


def win_game_report(sim, *, eng=None) -> MenuReport:
    """City Only win — PERSONAL [76]+17/+20, not Career [115]+ / promote.smk.

    EXE 0x5e077 uses +20 when remaining promotions < 2; City Only PERSONAL
    skips that chrome, but HELP measures only Prosperity + Culture against
    C2MODEL Citizen Need. Report, not a fake popup.
    """
    from app.forum import rating_need

    need, avg_need = rating_need(sim)
    p = int(getattr(sim, "rating_prosperity", 0))
    c = int(getattr(sim, "rating_culture", 0))
    you = _eng(eng, 76, 17, "You need")
    win = _eng(eng, 76, 20, "win the game.")
    title = _eng(eng, 69, 0, "Promotion!!!")
    lines = [
        f"{you} {win}",
        f"{_eng(eng, 31, 3, 'Prosperity')} {p} %  "
        f"{_eng(eng, 31, 6, '(Need')} {need} %)",
        f"{_eng(eng, 31, 4, 'Culture')} {c} %  "
        f"{_eng(eng, 31, 6, '(Need')} {need} %)",
        f"{_eng(eng, 31, 5, 'Average rating: ')}{(p + c) // 2} %  "
        f"{_eng(eng, 31, 6, '(Need')} {avg_need} %)",
    ]
    return MenuReport(title, tuple(lines))


def annual_summary_report(sim, *, eng=None) -> MenuReport:
    """C2.ENG [72] Annual Summary — FUN_00061389 after 0x3fd3e.

    City Only year wrap. Not Career [115]+ Emperor letters. Numbers are
    the HISTORY rec just appended (pop / treasury / pop tax / industry
    tax) vs the previous rec. First year compares against 0.
    """
    from app.forum import parse_history

    title = _eng(eng, 72, 0, "Annual Summary")
    clerks = _eng(eng, 72, 1, "from the Clerks")
    hint = _eng(
        eng, 72, 2, "(This panel can be toggled off from the Options menu.)"
    )
    recs = parse_history(getattr(sim, "history", None))
    if recs:
        pop, treas, tax_p, tax_i, _year = recs[-1]
        if len(recs) >= 2:
            p_pop, p_treas, p_tax_p, p_tax_i, _py = recs[-2]
        else:
            p_pop = p_treas = p_tax_p = p_tax_i = 0
    else:
        pop = int(getattr(sim, "population", 0))
        treas = int(getattr(sim, "treasury", 0))
        tax_p = int(getattr(sim, "pop_tax_last", 0))
        tax_i = int(getattr(sim, "ind_tax_last", 0))
        p_pop = p_treas = p_tax_p = p_tax_i = 0

    def row(skip: int, fallback: str, cur: int, prev: int) -> str:
        lab = _eng(eng, 72, skip, fallback)
        return f"{lab} {int(cur)}  {_year_delta(cur, prev, eng)}"

    lines = [clerks, *_wrap_adv(hint, 44)]
    lines.append(row(3, "City population is", pop, p_pop))
    lines.append(row(4, "Treasury funds are", treas, p_treas))
    lines.append(row(5, "Population tax was", tax_p, p_tax_p))
    lines.append(row(6, "Industry tax was", tax_i, p_tax_i))
    return MenuReport(title, tuple(lines))


def _help_cstring(data: bytes, off: int) -> str:
    if not (0 <= off < len(data)):
        return ""
    end = data.find(b"\x00", off)
    if end < 0:
        return ""
    return data[off:end].decode("latin-1", errors="replace")


def _first_sentence(text: str, cap: int = 140) -> str:
    cleaned = text.replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.replace("$", " ").replace("#", " ")
    cleaned = " ".join(cleaned.split())
    if not cleaned:
        return ""
    cut = cleaned.find(". ")
    if 20 <= cut < cap:
        return cleaned[: cut + 1]
    return cleaned[:cap]


def help_topic_excerpt(game: Path | None, topic: int, fallback_title: str) -> MenuReport:
    """Title + first sentence of the next HELP.ENG C-string. No manual dump."""
    if game is None:
        return MenuReport(fallback_title, ())
    path = find_file(game, "HELP.ENG")
    if path is None:
        return MenuReport(fallback_title, ())
    data = path.read_bytes()
    if not data.startswith(_HELP_MAGIC):
        return MenuReport(fallback_title, ())
    pos = _HELP_TABLE + topic * _HELP_REC
    if pos + 4 > len(data):
        return MenuReport(fallback_title, ())
    off = struct.unpack_from("<I", data, pos)[0]
    title = _help_cstring(data, off).strip() or fallback_title
    nxt = data.find(b"\x00", off)
    body = ""
    if nxt >= 0:
        body = _first_sentence(_help_cstring(data, nxt + 1))
    lines = (body,) if body and body != title else ()
    return MenuReport(title[:40], lines)


def about_report(eng) -> MenuReport:
    title = _eng(eng, 10, 0, "Caesar II - Version 1.1")
    date = _eng(eng, 10, 1, "October 5, 1995")
    copy = _eng(eng, 56, 13, "Copyright 1995 Sierra On-Line, Inc.")
    return MenuReport(title, (date, copy[:48], "City Only host"))


def report_rect() -> tuple[int, int, int, int]:
    return (_REPORT_X, _REPORT_Y, _REPORT_W, _REPORT_H)


def report_contains(x: int, y: int) -> bool:
    rx, ry, rw, rh = report_rect()
    return rx <= x < rx + rw and ry <= y < ry + rh


def report_line_at(x: int, y: int, n_lines: int) -> int | None:
    """0-based line under the title (same layout as blit_menu_report)."""
    if n_lines <= 0 or not report_contains(x, y):
        return None
    x0, y0, _w, h = report_rect()
    rel = y - (y0 + 24)
    if rel < 0:
        return None
    idx = rel // 13
    if idx < 0 or idx >= n_lines:
        return None
    if y0 + 24 + idx * 13 > y0 + h - 18:
        return None
    return idx


def blit_menu_report(frame: Image.Image, report: MenuReport) -> Image.Image:
    out = frame.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    x0, y0, w, h = report_rect()
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), fill=(8, 24, 22, 235))
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), outline=(200, 180, 90, 255))
    draw.text((x0 + 8, y0 + 6), report.title[:42], fill=(255, 228, 160, 255), font=font)
    y = y0 + 24
    for line in report.lines:
        draw.text((x0 + 8, y), line[:46], fill=(220, 230, 210, 255), font=font)
        y += 13
        if y > y0 + h - 18:
            break
    return Image.alpha_composite(out, overlay).convert("RGB")


def _wrap_adv(text: str, width: int = _ADV_LINE) -> list[str]:
    if not text:
        return []
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


def advisor_rect(msg, *, has_video: bool = False) -> tuple[int, int, int, int]:
    from app.advisor_video import SMK_H, SMK_W, SMK_X, SMK_Y

    lines = 1 + len(_wrap_adv(getattr(msg, "body", "") or "")) + 2
    text_h = max(96, 28 + 13 * lines + 14)
    if not has_video:
        return (_ADV_X, _ADV_Y, _ADV_W, text_h)
    # Video stays at EXE (80,96) 320×152. Center the banner on that hole
    # so 16:9 pillarbox is not left-heavy (_ADV_X=72 was 8px vs 32px).
    top = SMK_Y - _ADV_Y
    w = max(_ADV_W, SMK_W + 16)
    x = SMK_X - (w - SMK_W) // 2
    return (x, _ADV_Y, w, top + SMK_H + 8 + text_h)


def advisor_contains(x: int, y: int, msg, *, has_video: bool = False) -> bool:
    if msg is None:
        return False
    x0, y0, w, h = advisor_rect(msg, has_video=has_video)
    return x0 <= x < x0 + w and y0 <= y < y0 + h


def blit_advisor_dialog(
    frame: Image.Image,
    msg,
    *,
    eng=None,
    video: Image.Image | None = None,
    has_video: bool = False,
) -> Image.Image:
    """C2.ENG banner + optional 320×152 talker. Dismiss is not Query OK."""
    from app.advisor_video import SMK_H, SMK_W, SMK_X, SMK_Y

    has_video = has_video or video is not None
    out = frame.convert("RGBA")
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default()
    x0, y0, w, h = advisor_rect(msg, has_video=has_video)
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), fill=(16, 20, 36, 236))
    draw.rectangle((x0, y0, x0 + w - 1, y0 + h - 1), outline=(200, 180, 90, 255))
    text_y = y0 + 6
    if has_video:
        hole = (SMK_X, SMK_Y, SMK_X + SMK_W - 1, SMK_Y + SMK_H - 1)
        draw.rectangle(hole, fill=(0, 0, 0, 255))
        text_y = SMK_Y + SMK_H + 8
    draw.text((x0 + 8, text_y), msg.title[:42], fill=(255, 228, 160, 255), font=font)
    y = text_y + 18
    for line in _wrap_adv(msg.body or ""):
        draw.text((x0 + 8, y), line, fill=(220, 230, 210, 255), font=font)
        y += 13
        if y > y0 + h - 32:
            break
    hint = getattr(msg, "dismiss", "") or _eng(
        eng, 78, 0, "Right Click to remove this message."
    )
    click = _eng(eng, 7, 11, "Click to Continue")
    draw.text((x0 + 8, y0 + h - 26), click[:40], fill=(200, 190, 140, 255), font=font)
    draw.text((x0 + 8, y0 + h - 14), hint[:48], fill=(160, 150, 120, 255), font=font)
    composed = Image.alpha_composite(out, overlay).convert("RGB")
    if video is not None:
        clip = video.convert("RGB")
        if clip.size != (SMK_W, SMK_H):
            # Nearest keeps the EXE 320×152 grid; bilinear shears odd strides.
            clip = clip.resize((SMK_W, SMK_H), Image.Resampling.NEAREST)
        composed.paste(clip, (SMK_X, SMK_Y))
    return composed


def cycle_scroll(step: int) -> int:
    return 1 if int(step) >= 3 else int(step) + 1


def next_game_speed(sim) -> str:
    """Speed → Game Speed: Play, then Faster, then Play. Pause is its own item."""
    if getattr(sim, "paused", False):
        return "speed_play"
    if getattr(sim, "catchup", 0):
        return "speed_play"
    return "speed_fast"


def toggle_pause_action(sim) -> str:
    """Speed → Pause / P: resume Play, or pause. Does not touch Faster."""
    return "speed_play" if getattr(sim, "paused", False) else "speed_pause"


# C2MANUAL.DOC p.48 “Keyboard Commands” (1.1A). City Only binds rows we host.
# Debug title keys (1/2/3/Space/A) yield to this table once the city map is up.
CITY_ONLY_KEYS: tuple[tuple[str, str], ...] = (
    ("plus", "Zoom in"),
    ("minus", "Zoom out"),
    ("1", "Closest zoom"),
    ("2", "Medium zoom"),
    ("3", "Furthest zoom"),
    ("space", "Cancel current building"),
    ("f1", "Jump to City Level"),
    ("f2", "Jump to Forum"),
    ("f", "Jump to Forum"),
    ("f3", "Jump to Province Level"),
    ("f4", "Load game"),
    ("f5", "Save game"),
    ("p", "Pause Game"),
    ("y", "Yes (Yes/No panels)"),
    ("n", "No (Yes/No panels)"),
    ("escape", "Exit current screen/panel/menu"),
    ("a", "Accelerate Time"),
    ("c", "See Census Panel"),
    ("comma", "Rotate map left (INT_CITY sprite 4)"),
    ("period", "Rotate map right (INT_CITY sprite 5)"),
)

# Official keys / UI we cannot host yet. Do not invent overlay or Query letters.
CITY_ONLY_LEFTOVERS: tuple[str, ...] = (
    "Alt-F / Alt-F1 / Alt-F3 / Alt-D flags (sprite 9 unused)",
    "overlays — pull-down only; no letter key in the 1.1A table",
    "Query — mouse / right-click; no letter key in the 1.1A table",
    "R roads / other build letters — not in the 1.1A table",
)


def selftest() -> list[str]:
    lines: list[str] = []
    tiles = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    empty = census_report(tiles)
    if not any(ln.rstrip().endswith("0") for ln in empty.lines):
        lines.append(f"FAIL  empty census {empty.lines!r}")
    else:
        lines.append("ok    empty census")
    off = 10 * MAP_W * TILE_STRIDE + 10 * TILE_STRIDE
    tiles[off] = 0x82
    tiles[off + 5] = 0
    off2 = 10 * MAP_W * TILE_STRIDE + 12 * TILE_STRIDE
    tiles[off2] = 0x83
    tiles[off2 + 5] = 0
    filler = 11 * MAP_W * TILE_STRIDE + 10 * TILE_STRIDE
    tiles[filler] = 0x82
    tiles[filler + 5] = 1
    counts = census_counts(tiles)
    pop = recount_population(tiles)
    if counts["Tent"] != 2 or counts["origins"] != 2:
        lines.append(f"FAIL  tent origins {counts}")
    else:
        lines.append("ok    census origins skip +5 fillers")
    want = HOUSE_OCCUPANCY[0] + HOUSE_OCCUPANCY[1]
    if pop != want:
        lines.append(f"FAIL  census pop {pop} want {want}")
    else:
        lines.append("ok    census pop from occupancy table")
    from app.city_sim import SimState
    from app.forum import append_history_year

    first = SimState(city_only=1, population=80, treasury=11992, pop_tax_last=12, ind_tax_last=0)
    first.history = bytearray(4000)
    append_history_year(first)
    summary = annual_summary_report(first)
    body = " ".join(summary.lines)
    if summary.title != "Annual Summary":
        lines.append(f"FAIL  annual title {summary.title!r}")
    elif "from the Clerks" not in body:
        lines.append(f"FAIL  annual clerks {summary.lines!r}")
    elif "City population is 80" not in body or "(UP 80)" not in body:
        lines.append(f"FAIL  annual pop {summary.lines!r}")
    elif "Treasury funds are 11992" not in body:
        lines.append(f"FAIL  annual treas {summary.lines!r}")
    elif "Population tax was 12" not in body or "Industry tax was 0" not in body:
        lines.append(f"FAIL  annual tax {summary.lines!r}")
    else:
        lines.append("ok    Annual Summary first year pop/treas/tax (UP from 0)")
    second = SimState(
        city_only=1,
        population=100,
        treasury=11800,
        pop_tax_last=20,
        ind_tax_last=4,
        history=bytearray(first.history),
    )
    append_history_year(second)
    down = annual_summary_report(second)
    down_body = " ".join(down.lines)
    if "(UP 20)" not in down_body or "(DOWN 192)" not in down_body:
        lines.append(f"FAIL  annual UP/DOWN {down.lines!r}")
    else:
        lines.append("ok    Annual Summary (UP pop) (DOWN treasury)")
    won = win_game_report(
        SimState(city_only=1, skill=2, rating_prosperity=30, rating_culture=34)
    )
    lose = lose_game_report()
    if "win the game" not in " ".join(won.lines).lower():
        lines.append(f"FAIL  win report {won.lines!r}")
    elif lose.title != "GAME OVER":
        lines.append(f"FAIL  lose title {lose.title!r}")
    else:
        lines.append("ok    City Only win/lose reports use [76]+20 / [45]")
    opt = decorate_item(
        SLOT_OPTIONS, OPT_YEAR, "End of Year ", options=HostOptions(annual_summary=False)
    )
    if "OFF" not in opt:
        lines.append(f"FAIL  Annual Summary toggle {opt!r}")
    else:
        lines.append("ok    Options End of Year suffixes Annual Summary ON/OFF")
    lab = decorate_item(SLOT_OPTIONS, OPT_SOUND, "Sound", options=HostOptions(sound=False))
    if "OFF" not in lab:
        lines.append(f"FAIL  decorate {lab!r}")
    else:
        lines.append("ok    Options Sound OFF suffix")

    class _Play:
        paused = False
        catchup = 0

    class _Fast:
        paused = False
        catchup = 1

    if next_game_speed(_Play()) != "speed_fast":
        lines.append("FAIL  Game Speed from Play should Faster")
    else:
        lines.append("ok    Game Speed Play->Faster")
    if next_game_speed(_Fast()) != "speed_play":
        lines.append("FAIL  Game Speed from Faster should Play")
    else:
        lines.append("ok    Game Speed Faster->Play")
    if toggle_pause_action(_Play()) != "speed_pause":
        lines.append("FAIL  P from Play should pause")
    else:
        lines.append("ok    P Play->Pause")

    class _Paused:
        paused = True
        catchup = 0

    if toggle_pause_action(_Paused()) != "speed_play":
        lines.append("FAIL  P from Pause should Play")
    else:
        lines.append("ok    P Pause->Play")
    bound = {key for key, _lab in CITY_ONLY_KEYS}
    for need in ("p", "c", "a", "space", "f", "f1", "f2", "f3", "f4", "f5", "1", "2", "3"):
        if need not in bound:
            lines.append(f"FAIL  city key {need} missing")
            break
    else:
        lines.append("ok    City Only key table has P/C/A/Space/F/F1–F5/1–3")
    blob = " ".join(CITY_ONLY_LEFTOVERS).lower()
    if "overlay" not in blob or "query" not in blob:
        lines.append("FAIL  leftovers omit overlay/query")
    else:
        lines.append("ok    leftovers list overlay/query/flags")
    if "comma" not in bound or "period" not in bound:
        lines.append("FAIL  city key rotate < > missing")
    else:
        lines.append("ok    City Only key table has < > rotate")
    if SLOT_DISASTERS == 4 and [sk for sk, _lab in DISASTER_ITEMS] != [
        DIS_FIRE,
        DIS_BARBARIAN,
        DIS_RIOT,
    ]:
        lines.append(f"FAIL  Disasters items {DISASTER_ITEMS!r}")
    elif DISASTER_TITLE != "Disasters":
        lines.append(f"FAIL  Disasters title {DISASTER_TITLE!r}")
    else:
        lines.append("ok    Disasters menu lists Fire / Barbarian / Riot")
    if report_line_at(_REPORT_X + 8, _REPORT_Y + 24, 3) != 0:
        lines.append("FAIL  report_line_at first line")
    elif report_line_at(_REPORT_X + 8, _REPORT_Y + 24 + 13, 2) != 1:
        lines.append("FAIL  report_line_at [ new ] row")
    else:
        lines.append("ok    report_line_at first line + [ new ]")
    from app.messages import AdvisorMessage

    demo = AdvisorMessage(
        key="t", title="Fire Alert!", body="x", slot=81, dismiss="Right Click"
    )
    if not advisor_contains(_ADV_X + 4, _ADV_Y + 4, demo):
        lines.append("FAIL  advisor hit")
    else:
        lines.append("ok    advisor dialog hitbox")
    x0, y0, w, h = advisor_rect(demo, has_video=True)
    if h <= 152 or not advisor_contains(80 + 4, 96 + 4, demo, has_video=True):
        lines.append(f"FAIL  advisor video box {w}x{h}")
    elif x0 + (w - 320) // 2 != 80:
        lines.append(f"FAIL  advisor video not centered x={x0} w={w}")
    else:
        lines.append("ok    advisor video+text hitbox")
    excerpt = help_topic_excerpt(None, HELP_TOPIC_HINTS, "Hints and Tips")
    if excerpt.title != "Hints and Tips":
        lines.append("FAIL  help fallback")
    else:
        lines.append("ok    help excerpt without HELP.ENG")
    try:
        from app.config import resolve_game_dir

        game, _why = resolve_game_dir()
        hints = help_topic_excerpt(game, HELP_TOPIC_HINTS, "Hints and Tips")
        if "Hint" not in hints.title and "hint" not in hints.title.lower():
            lines.append(f"FAIL  HELP hints title {hints.title!r}")
        elif not hints.lines:
            lines.append("FAIL  HELP hints body missing")
        else:
            lines.append("ok    HELP.ENG Hints title + first line")
        about = about_report(None)
        if "Version" not in about.title:
            lines.append(f"FAIL  about {about.title!r}")
        else:
            lines.append("ok    About fallback")
        from app.assets import load_eng

        eng = load_eng(game)
        if eng.skip(72, 0) != "Annual Summary":
            lines.append(f"FAIL  C2.ENG [72] {eng.skip(72, 0)!r}")
        elif eng.skip(72, 3) != "City population is":
            lines.append(f"FAIL  C2.ENG [72]+3 {eng.skip(72, 3)!r}")
        elif eng.skip(56, 6) != "Annual Summary ":
            lines.append(f"FAIL  C2.ENG [56]+6 {eng.skip(56, 6)!r}")
        elif eng.skip(38, 2) != "Select a saved game to LOAD":
            lines.append(f"FAIL  C2.ENG [38]+2 {eng.skip(38, 2)!r}")
        elif eng.skip(38, 3) != "Select a file name to SAVE":
            lines.append(f"FAIL  C2.ENG [38]+3 {eng.skip(38, 3)!r}")
        else:
            lines.append("ok    C2.ENG [72] Annual + [38] Load/Save titles")
    except (OSError, ValueError, ImportError):
        lines.append("ok    HELP.ENG skipped (no install)")
    return lines
