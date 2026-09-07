"""City chrome — INT_CITY.PL8 sidebar (right) + 3-row build hitboxes.

Original blit dests are in the PL8 sprite x/y. Panel 2 at (478, 208) already
has the 3×5 tool grid painted. Individual sprites 13–27 are the same icons
authored at a floating origin (244, 211); hitboxes remap that grid onto the
sidebar. Overlay-filter table 0x98B34 (Geography…Markets) is NOT this panel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.city_overlay import OVERLAY_WELL
from app.place import (
    TOOL_CLEAR,
    TOOL_QUERY,
    TOOL_ROAD,
    TOOL_TENT,
)

SCREEN_W = 640
SCREEN_H = 480
# INT_CITY[2] — right panel with the 3×5 grid baked in.
SIDEBAR_X = 478
SIDEBAR_Y = 208
SIDEBAR_W = 162
SIDEBAR_H = 160
TOP_BAR_H = 24
# Sprites 4–27 were authored relative to this origin (see PL8 x/y).
_FLOAT_X0 = 244
_FLOAT_Y0 = 211

# INT_CITY sprites 13–27 left-to-right, top-to-bottom. Decoded frames
# (CITY1.256): sprite 21 = blue/green bottles → Industry; sprite 22 =
# dark vessel + green cross → Sanitation. HELP.ENG Cty Icn is the same
# order (Industry then Sanitation). Bind flyout CONTENT to the picture.
_ROW1 = ("zoom_in", "clear", "housing", "roads", "forums")
_ROW2 = ("zoom_out", "water", "security", "commerce", "health")
_ROW3 = ("query", "entertainment", "worship", "education", "amenities")
_GRID_ACTIONS: tuple[str, ...] = _ROW1 + _ROW2 + _ROW3
# sprite index 13+i → action. Proof dump for the crossed-menu bug.
SPRITE_GRID = tuple(
    (13 + i, _GRID_ACTIONS[i]) for i in range(15)
)

# First of the 3×5 in INT_CITY (sprite 13).
_GRID_SPRITE0 = 13
# Sprites 4–9 sit on the palette panel above the 3×5 (rotate / pause / play / fast / flag).
# 4–5 rotate, 6 pause, 7 play (blue triangle), 8 faster (yellow), 9 flag.
_SPEED_SPRITE_ACTIONS: dict[int, str] = {
    6: "speed_pause",
    7: "speed_play",
    8: "speed_fast",
}
# INT_CITY 10–12 — city / people (Forum advisor) / province. 52×26 at y=235.
_VIEW_SPRITE_ACTIONS: dict[int, str] = {
    10: "view_city",
    11: "view_forum",
    12: "view_province",
}

_LABEL = {
    "zoom_in": "zoom +",
    "zoom_out": "zoom −",
    "clear": "Clear",
    "housing": "Housing",
    "roads": "Roads",
    "forums": "Forums",
    "water": "Water",
    "security": "Security",
    "query": "Query",
    "entertainment": "Entert'ment",
    "worship": "Worship",
    "education": "Education",
    "amenities": "Amenities",
    "health": "Sanitation",
    "commerce": "Industry",
    "overlay_menu": "Overlay",
    "speed_pause": "Pause",
    "speed_play": "Play",
    "speed_fast": "Faster",
    "view_city": "City",
    "view_forum": "Forum",
    "view_province": "Province",
}

_PLACEABLE = {
    "housing": TOOL_TENT,
    "roads": TOOL_ROAD,
    "clear": TOOL_CLEAR,
    "query": TOOL_QUERY,
}


@dataclass(frozen=True)
class ChromeHit:
    action: str
    label: str
    rect: tuple[int, int, int, int]


@dataclass
class CityChrome:
    """Loaded INT_CITY frames + remapped 3×5 hitboxes. Missing PL8 → stub bar."""

    frames: list[Image.Image] = field(default_factory=list)
    dests: list[tuple[int, int]] = field(default_factory=list)
    hits: list[ChromeHit] = field(default_factory=list)
    source: str = "stub"

    @classmethod
    def load(cls, game: Path) -> CityChrome:
        from app import assets

        try:
            packed = assets.load_pl8_sprites_xy(game, "INT_CITY.PL8")
        except (OSError, ValueError, FileNotFoundError):
            return cls._fallback()
        frames = [img for img, _x, _y in packed]
        dests = [(x, y) for _img, x, y in packed]
        hits = _hits_from_records(packed)
        if not hits:
            return cls._fallback(frames=frames, dests=dests, source="int_city+fallback-hits")
        hits = _expand_grid_hits(hits)
        hits = _with_speed_hits(hits, packed)
        hits = _with_view_hits(hits, packed)
        hits = _with_overlay_well(hits)
        return cls(frames=frames, dests=dests, hits=hits, source="int_city.pl8")

    @classmethod
    def _fallback(
        cls,
        frames: list[Image.Image] | None = None,
        dests: list[tuple[int, int]] | None = None,
        source: str = "stub",
    ) -> CityChrome:
        hits: list[ChromeHit] = []
        x0, y0 = SIDEBAR_X + 6, SIDEBAR_Y + 78
        w, h = 30, 24
        gap = 1
        for row, actions in enumerate((_ROW1, _ROW2, _ROW3)):
            for col, action in enumerate(actions):
                x = x0 + col * (w + gap)
                y = y0 + row * (h + gap)
                hits.append(
                    ChromeHit(action, _LABEL.get(action, action), (x, y, w, h))
                )
        hits = _with_speed_fallback(hits)
        hits = _with_view_fallback(hits)
        hits = _with_overlay_well(hits)
        return cls(frames=frames or [], dests=dests or [], hits=hits, source=source)

    def covers(self, x: int, y: int, ox: int = 0) -> bool:
        """Window pixels. Chrome is the top bar plus the right 162 px strip."""
        if y < TOP_BAR_H:
            return True
        return x >= SIDEBAR_X + ox and y < SCREEN_H

    def hit_test(self, x: int, y: int, ox: int = 0) -> ChromeHit | None:
        """Hitboxes live in native 640 space. ``ox`` is the maximize slide
        (same offset as ``blit`` / palette flyouts / the chrome layer)."""
        nx = x - ox
        for hit in self.hits:
            rx, ry, rw, rh = hit.rect
            if rx <= nx < rx + rw and ry <= y < ry + rh:
                return hit
        return None

    def blit(
        self,
        frame: Image.Image,
        *,
        selected: str | None = None,
        speed: str | None = None,
        stub_labels: bool = False,
        ox: int = 0,
    ) -> Image.Image:
        """Paste chrome at native 1:1 pixels. ``ox`` slides the 162 px strip right."""
        out = frame.convert("RGBA")
        n = min(4, len(self.frames), len(self.dests))
        if n >= 1:
            spr0 = self.frames[0]
            x0, y0 = self.dests[0]
            out.paste(spr0, (x0, y0), spr0)
            if ox > 0:
                bar_h = min(TOP_BAR_H, spr0.height)
                col_x = min(400, max(0, spr0.width - 1))
                col = spr0.crop((col_x, 0, col_x + 1, bar_h))
                for x in range(SIDEBAR_X, SIDEBAR_X + ox):
                    out.paste(col, (x, 0))
                cap_x = max(0, spr0.width - SIDEBAR_W)
                cap = spr0.crop((cap_x, 0, spr0.width, bar_h))
                out.paste(cap, (SIDEBAR_X + ox, 0), cap)
        for i in range(1, n):
            spr = self.frames[i]
            x, y = self.dests[i]
            out.paste(spr, (x + ox, y), spr)
        draw = ImageDraw.Draw(out)
        font = ImageFont.load_default()
        lit = {a for a in (selected, speed) if a}
        if self.source.startswith("stub") or stub_labels or n < 3:
            draw.rectangle(
                (SIDEBAR_X + ox, SIDEBAR_Y, SCREEN_W - 1 + ox, SIDEBAR_Y + SIDEBAR_H),
                fill=(16, 40, 36, 210),
            )
            for hit in self.hits:
                rx, ry, rw, rh = hit.rect
                rx += ox
                fill = (40, 90, 70, 230)
                if hit.action in lit:
                    fill = (180, 150, 40, 240)
                draw.rectangle((rx, ry, rx + rw - 1, ry + rh - 1), fill=fill)
                if hit.label:
                    draw.text((rx + 2, ry + 6), hit.label[:8], fill=(240, 230, 180), font=font)
        elif lit:
            for hit in self.hits:
                if hit.action not in lit:
                    continue
                rx, ry, rw, rh = hit.rect
                rx += ox
                draw.rectangle((rx - 1, ry - 1, rx + rw, ry + rh), outline=(255, 220, 80, 255))
        return out.convert("RGB")


def chrome_ox(win_w: int) -> int:
    """Shift INT_CITY / minimap so the 162 px strip stays on the right."""
    return max(0, int(win_w) - SCREEN_W)


def _hits_from_records(
    packed: list[tuple[Image.Image, int, int]],
) -> list[ChromeHit]:
    if len(packed) < _GRID_SPRITE0 + 15:
        return []
    hits: list[ChromeHit] = []
    dx = SIDEBAR_X - _FLOAT_X0
    dy = SIDEBAR_Y - _FLOAT_Y0
    for i, action in enumerate(_GRID_ACTIONS):
        img, sx, sy = packed[_GRID_SPRITE0 + i]
        hits.append(
            ChromeHit(
                action,
                _LABEL.get(action, action),
                (sx + dx, sy + dy, img.width, img.height),
            )
        )
    return hits


def _expand_grid_hits(hits: list[ChromeHit]) -> list[ChromeHit]:
    """Tile the 3×5 so maximize / ``ox`` clicks hit the picture, not a gap."""
    grid = [h for h in hits if h.action in _GRID_ACTIONS]
    extra = [h for h in hits if h.action not in _GRID_ACTIONS]
    if len(grid) != 15:
        return hits
    xs = [h.rect[0] for h in grid]
    ys = [h.rect[1] for h in grid]
    x1 = max(h.rect[0] + h.rect[2] for h in grid)
    y1 = max(h.rect[1] + h.rect[3] for h in grid)
    x0, y0 = min(xs), min(ys)
    cw = max(1, x1 - x0)
    ch = max(1, y1 - y0)
    grown: list[ChromeHit] = []
    for i, hit in enumerate(grid):
        col, row = i % 5, i // 5
        rx = x0 + (col * cw) // 5
        ry = y0 + (row * ch) // 3
        rw = x0 + ((col + 1) * cw) // 5 - rx
        rh = y0 + ((row + 1) * ch) // 3 - ry
        grown.append(ChromeHit(hit.action, hit.label, (rx, ry, max(1, rw), max(1, rh))))
    return extra + grown


def _with_speed_hits(
    hits: list[ChromeHit], packed: list[tuple[Image.Image, int, int]]
) -> list[ChromeHit]:
    dx = SIDEBAR_X - _FLOAT_X0
    dy = SIDEBAR_Y - _FLOAT_Y0
    extra: list[ChromeHit] = []
    for idx, action in _SPEED_SPRITE_ACTIONS.items():
        if idx >= len(packed):
            continue
        img, sx, sy = packed[idx]
        extra.append(
            ChromeHit(
                action,
                _LABEL.get(action, action),
                (sx + dx, sy + dy, img.width, img.height),
            )
        )
    return extra + hits


def _with_speed_fallback(hits: list[ChromeHit]) -> list[ChromeHit]:
    extra: list[ChromeHit] = []
    x0, y0 = SIDEBAR_X + 6, SIDEBAR_Y + 4
    for i, action in enumerate(("speed_pause", "speed_play", "speed_fast")):
        extra.append(
            ChromeHit(action, _LABEL[action], (x0 + i * 32, y0, 30, 22))
        )
    return extra + hits


def _with_view_hits(
    hits: list[ChromeHit], packed: list[tuple[Image.Image, int, int]]
) -> list[ChromeHit]:
    dx = SIDEBAR_X - _FLOAT_X0
    dy = SIDEBAR_Y - _FLOAT_Y0
    extra: list[ChromeHit] = []
    for idx, action in _VIEW_SPRITE_ACTIONS.items():
        if idx >= len(packed):
            continue
        img, sx, sy = packed[idx]
        extra.append(
            ChromeHit(
                action,
                _LABEL.get(action, action),
                (sx + dx, sy + dy, img.width, img.height),
            )
        )
    return extra + hits


def _with_view_fallback(hits: list[ChromeHit]) -> list[ChromeHit]:
    extra: list[ChromeHit] = []
    x0, y0 = SIDEBAR_X + 6, SIDEBAR_Y + 28
    for i, action in enumerate(("view_city", "view_forum", "view_province")):
        extra.append(
            ChromeHit(action, _LABEL[action], (x0 + i * 52, y0, 50, 22))
        )
    return extra + hits


def _with_overlay_well(hits: list[ChromeHit]) -> list[ChromeHit]:
    wx, wy, ww, wh = OVERLAY_WELL
    well = ChromeHit("overlay_menu", "Overlay", (wx, wy, ww, wh))
    return [well, *hits]


def speed_action(sim) -> str:
    """Which INT_CITY speed button is lit (pause / play / faster)."""
    if getattr(sim, "paused", False):
        return "speed_pause"
    if getattr(sim, "catchup", 0):
        return "speed_fast"
    return "speed_play"


def tool_for_action(action: str) -> str | None:
    return _PLACEABLE.get(action)


def action_for_tool(tool: str | None) -> str | None:
    if tool == TOOL_TENT:
        return "housing"
    if tool == TOOL_ROAD:
        return "roads"
    if tool == TOOL_CLEAR:
        return "clear"
    if tool == TOOL_QUERY:
        return "query"
    return None


def grid_action_at(index: int) -> str:
    """INT_CITY 3×5 cell. 8 = Industry (sprite 21 bottles), 9 = Sanitation (sprite 22)."""
    return _GRID_ACTIONS[index]
