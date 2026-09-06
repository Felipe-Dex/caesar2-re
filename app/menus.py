"""City Only top menu — File / Options / Speed / Help (C2.ENG [0]…[3]).

Actions match 1.1A City Only strings. No Career empire / Forum PERSONAL.
Save does not write a .SAV: sav_write 0x70174 needs 500 BSS chunks the host
does not keep. Census is Options+5 (Census Panel [74]), not an overlay-filter.
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
FILE_NEW, FILE_LOAD, FILE_SAVE, FILE_QUIT = 1, 2, 3, 4
OPT_MUSIC, OPT_SOUND, OPT_ANIM, OPT_YEAR, OPT_CENSUS = 1, 2, 3, 4, 5
SPD_GAME, SPD_SCROLL, SPD_PAUSE = 1, 2, 3
HLP_HINTS, HLP_GAME, HLP_HISTORY, HLP_ICONS, HLP_ABOUT = 1, 2, 3, 4, 5

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


@dataclass
class HostOptions:
    """In-game Options / Speed extras. Miles/XMI and sav_year_end are not hosted."""

    music: bool = False
    sound: bool = True
    animations: bool = True
    auto_save: bool = False
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
            return f"{label}  {on_off(eng, opt.auto_save)}"
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


def cycle_scroll(step: int) -> int:
    return 1 if int(step) >= 3 else int(step) + 1


def next_game_speed(sim) -> str:
    """Speed → Game Speed: Play, then Faster, then Play. Pause is its own item."""
    if getattr(sim, "paused", False):
        return "speed_play"
    if getattr(sim, "catchup", 0):
        return "speed_play"
    return "speed_fast"


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
    except (OSError, ValueError, ImportError):
        lines.append("ok    HELP.ENG skipped (no install)")
    return lines
