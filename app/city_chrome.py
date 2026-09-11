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
# 4 rotate-left (CCW), 5 rotate-right (CW), 6 pause, 7 play, 8 faster, 9 flag.
_ROTATE_SPRITE_ACTIONS: dict[int, str] = {
    4: "rotate_left",
    5: "rotate_right",
}
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

# MISC.PL8 — not INT_CITY. gfx_blit 0x27BFA (EAX=0xD1A2C).
# Corner N: view_frame 0x3D065 / city_enter 0x5ACF0. Index = [0x102BE0] >> 1
# (signed). [0x102BE0] is walker camera 0/2/4/6 = walker_camera(facing).
# Dest EBX=0x1C4 ECX=0x1A. Faster ([0xC45A0]>=2) skips the view_frame blit;
# city enter always draws it. Host always blits.
NORTH_ARROW_XY = (0x1C4, 0x1A)
# Minimap N-up: FUN_0003ed7c tail. EDX=4, dest ([0x102B5C]+2, [0x102B60]+2).
# Boot writes B5C=0x1E0 B60=0x30 (0x10715).
MINIMAP_NORTH_XY = (0x1E0 + 2, 0x30 + 2)
MINIMAP_NORTH_SPRITE = 4

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
    "rotate_left": "Rot L",
    "rotate_right": "Rot R",
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
    misc_frames: list[Image.Image] = field(default_factory=list)
    source: str = "stub"

    @classmethod
    def load(cls, game: Path) -> CityChrome:
        from app import assets

        try:
            packed = assets.load_pl8_sprites_xy(game, "INT_CITY.PL8")
        except (OSError, ValueError, FileNotFoundError):
            return cls._fallback(misc_frames=_load_misc(game))
        frames = [img for img, _x, _y in packed]
        dests = [(x, y) for _img, x, y in packed]
        hits = _hits_from_records(packed)
        misc = _load_misc(game)
        if not hits:
            return cls._fallback(
                frames=frames,
                dests=dests,
                misc_frames=misc,
                source="int_city+fallback-hits",
            )
        hits = _expand_grid_hits(hits)
        hits = _with_rotate_hits(hits, packed)
        hits = _with_speed_hits(hits, packed)
        hits = _with_view_hits(hits, packed)
        hits = _with_overlay_well(hits)
        return cls(
            frames=frames,
            dests=dests,
            hits=hits,
            misc_frames=misc,
            source="int_city.pl8",
        )

    @classmethod
    def _fallback(
        cls,
        frames: list[Image.Image] | None = None,
        dests: list[tuple[int, int]] | None = None,
        misc_frames: list[Image.Image] | None = None,
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
        hits = _with_rotate_fallback(hits)
        hits = _with_speed_fallback(hits)
        hits = _with_view_fallback(hits)
        hits = _with_overlay_well(hits)
        return cls(
            frames=frames or [],
            dests=dests or [],
            hits=hits,
            misc_frames=misc_frames or [],
            source=source,
        )

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
        facing: int = 0,
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
        _paste_misc_sprite(out, self.misc_frames, north_sprite_index(facing), NORTH_ARROW_XY, ox)
        return out.convert("RGB")

    def blit_minimap_north(self, frame: Image.Image, *, ox: int = 0) -> Image.Image:
        """MISC[4] N-up after the minimap / legend fill (3ed7c would cover it first)."""
        out = frame.convert("RGBA")
        _paste_misc_sprite(
            out, self.misc_frames, MINIMAP_NORTH_SPRITE, MINIMAP_NORTH_XY, ox
        )
        return out.convert(frame.mode) if frame.mode != "RGBA" else out


def chrome_ox(win_w: int) -> int:
    """Shift INT_CITY / minimap so the 162 px strip stays on the right."""
    return max(0, int(win_w) - SCREEN_W)


def north_sprite_index(facing: int) -> int:
    """MISC 0–3. ``[0x102BE0] >> 1`` with BE0 = walker camera 0/2/4/6.

    Same as ``walker_camera(facing) >> 1`` / ``(-facing) & 3``.
    """
    return (-int(facing)) & 3


def _load_misc(game: Path) -> list[Image.Image]:
    from app import assets

    try:
        packed = assets.load_pl8_sprites_xy(game, "MISC.PL8")
    except (OSError, ValueError, FileNotFoundError):
        return []
    return [img for img, _x, _y in packed]


def _paste_misc_sprite(
    frame: Image.Image,
    misc: list[Image.Image],
    index: int,
    dest: tuple[int, int],
    ox: int,
) -> None:
    if index < 0 or index >= len(misc):
        return
    spr = misc[index]
    x, y = dest
    frame.paste(spr, (x + ox, y), spr if spr.mode == "RGBA" else None)


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


def _with_rotate_hits(
    hits: list[ChromeHit], packed: list[tuple[Image.Image, int, int]]
) -> list[ChromeHit]:
    dx = SIDEBAR_X - _FLOAT_X0
    dy = SIDEBAR_Y - _FLOAT_Y0
    extra: list[ChromeHit] = []
    for idx, action in _ROTATE_SPRITE_ACTIONS.items():
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


def _with_rotate_fallback(hits: list[ChromeHit]) -> list[ChromeHit]:
    extra: list[ChromeHit] = []
    x0, y0 = SIDEBAR_X + 6, SIDEBAR_Y + 4
    for i, action in enumerate(("rotate_left", "rotate_right")):
        extra.append(
            ChromeHit(action, _LABEL[action], (x0 + i * 28, y0, 26, 22))
        )
    return extra + hits


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
    x0, y0 = SIDEBAR_X + 62, SIDEBAR_Y + 4
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
    """INT_CITY overlay name well. Window plays SfxPlayer overlay/a09 only."""
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


def selftest() -> list[str]:
    """MISC north gadget: facing → sprite, dests, blit on a dummy frame."""
    lines: list[str] = []
    if north_sprite_index(0) != 0 or north_sprite_index(1) != 3:
        lines.append(
            f"FAIL  north sprite facing 0/1 = "
            f"{north_sprite_index(0)}/{north_sprite_index(1)} want 0/3"
        )
    elif north_sprite_index(2) != 2 or north_sprite_index(3) != 1:
        lines.append(
            f"FAIL  north sprite facing 2/3 = "
            f"{north_sprite_index(2)}/{north_sprite_index(3)} want 2/1"
        )
    else:
        lines.append("ok    MISC north sprite (-facing)&3 via walker_camera>>1")
    if NORTH_ARROW_XY != (452, 26) or MINIMAP_NORTH_XY != (482, 50):
        lines.append(f"FAIL  north dest {NORTH_ARROW_XY} {MINIMAP_NORTH_XY}")
    else:
        lines.append("ok    MISC dest (452,26) + minimap N (482,50)")
    ch = CityChrome._fallback()
    frame = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
    painted = ch.blit(frame, facing=1)
    if painted.size != (SCREEN_W, SCREEN_H):
        lines.append(f"FAIL  chrome blit size {painted.size}")
    else:
        lines.append("ok    chrome blit keeps 640×480 with facing")
    try:
        from app.config import resolve_game_dir

        game, _why = resolve_game_dir()
        loaded = CityChrome.load(game)
    except (OSError, ValueError, FileNotFoundError):
        lines.append("ok    MISC north skip (no install)")
        return lines
    if len(loaded.misc_frames) < 5:
        lines.append(f"FAIL  MISC frames {len(loaded.misc_frames)}")
        return lines
    blank = Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0))
    corner = loaded.blit(blank, facing=0)
    nx, ny = NORTH_ARROW_XY
    spr0 = loaded.misc_frames[0]
    crop = corner.crop((nx, ny, nx + spr0.width, ny + spr0.height))
    if crop.getextrema()[0][1] < 80:
        lines.append(f"FAIL  MISC[0] not blitted at {NORTH_ARROW_XY}")
    else:
        lines.append("ok    MISC[0] north arrow at (452,26)")
    radar = loaded.blit_minimap_north(Image.new("RGB", (SCREEN_W, SCREEN_H), (0, 0, 0)))
    mx, my = MINIMAP_NORTH_XY
    spr4 = loaded.misc_frames[MINIMAP_NORTH_SPRITE]
    rcrop = radar.crop((mx, my, mx + spr4.width, my + spr4.height))
    if rcrop.getextrema()[0][1] < 80:
        lines.append(f"FAIL  MISC[4] not blitted at {MINIMAP_NORTH_XY}")
    else:
        lines.append("ok    MISC[4] N-up on minimap (482,50)")
    return lines
