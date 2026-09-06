"""City build flyouts — Water / Security / Amenities plus remaining menus.

English labels match HELP.ENG. INT_CITY artwork (not Cty Icn string
order) puts Sanitation on the marble-column sprite then Industry on
the workshop sprite — ``health`` then ``commerce``. Arena stays stub
(no SAV origin). Senate / farms are not city stamps. INT_CITY 3×5
hitboxes stay in ``city_chrome``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from app.city_chrome import SIDEBAR_X, action_for_tool as _chrome_action
from app.place import (
    TOOL_AQUEDUCT,
    TOOL_AVENTINE,
    TOOL_BARRACKS,
    TOOL_BASILICA,
    TOOL_BATHS,
    TOOL_CIRCUS,
    TOOL_CLEAR,
    TOOL_CMAXIMUS,
    TOOL_COLISEUM,
    TOOL_FACTORY,
    TOOL_FOUNTAIN,
    TOOL_GARDEN,
    TOOL_GRAMMATICUS,
    TOOL_HOSPITAL,
    TOOL_JANICULAN,
    TOOL_LIBRARY,
    TOOL_MARKET,
    TOOL_ODEUM,
    TOOL_PALATINE,
    TOOL_PLAZA,
    TOOL_PREFECTURE,
    TOOL_QUERY,
    TOOL_RESERVOIR,
    TOOL_RHETOR,
    TOOL_ROAD,
    TOOL_SHRINE,
    TOOL_TEMPLE,
    TOOL_TENT,
    TOOL_THEATER,
    TOOL_TOWER,
    TOOL_WALL,
    TOOL_WELL,
)

# Direct grid buttons (no flyout).
_DIRECT = {
    "housing": TOOL_TENT,
    "roads": TOOL_ROAD,
    "clear": TOOL_CLEAR,
    "query": TOOL_QUERY,
}

_TOOL_ACTION = {
    TOOL_TENT: "housing",
    TOOL_ROAD: "roads",
    TOOL_CLEAR: "clear",
    TOOL_QUERY: "query",
    TOOL_RESERVOIR: "water",
    TOOL_AQUEDUCT: "water",
    TOOL_WELL: "water",
    TOOL_FOUNTAIN: "water",
    TOOL_GARDEN: "amenities",
    TOOL_PLAZA: "amenities",
    TOOL_PREFECTURE: "security",
    TOOL_TOWER: "security",
    TOOL_BARRACKS: "security",
    TOOL_WALL: "security",
    TOOL_AVENTINE: "forums",
    TOOL_JANICULAN: "forums",
    TOOL_PALATINE: "forums",
    TOOL_THEATER: "entertainment",
    TOOL_ODEUM: "entertainment",
    TOOL_COLISEUM: "entertainment",
    TOOL_CIRCUS: "entertainment",
    TOOL_CMAXIMUS: "entertainment",
    TOOL_SHRINE: "worship",
    TOOL_TEMPLE: "worship",
    TOOL_BASILICA: "worship",
    TOOL_GRAMMATICUS: "education",
    TOOL_RHETOR: "education",
    TOOL_LIBRARY: "education",
    TOOL_BATHS: "health",
    TOOL_HOSPITAL: "health",
    TOOL_MARKET: "commerce",
    TOOL_FACTORY: "commerce",
}

_TOOL_HINT = {
    TOOL_TENT: "Housing → rectângulo de Tent 0x82 (6 cada; tudo ou nada)",
    TOOL_ROAD: "Roads → linha recta (ponte no rio recto; salta curva)",
    TOOL_CLEAR: "Clear → rectângulo (prédio→0x05, entulho→0x1C)",
    TOOL_QUERY: "Query (arrastar ainda faz pan)",
    TOOL_RESERVOIR: "Reservoir 0xBE 1×1 (custo 51; fantasma; enche junto ao rio)",
    TOOL_AQUEDUCT: "Aqueduct linha 0xCB–0xD6 (como estrada; precisa de Reservoir)",
    TOOL_WELL: "Well 0xD7 (rect 1×1; custo 20)",
    TOOL_FOUNTAIN: "Fountain 0xDD (rect 1×1; custo 15)",
    TOOL_GARDEN: "Gardens 0x78–0x7B LUT 0x93FCC (rect; custo 3)",
    TOOL_PLAZA: "Plaza 0x7C (rect 1×1; custo 12; precisa de estrada)",
    TOOL_PREFECTURE: "Praefecture 0xE3 +3=0x80 +4=0x50 (custo 100)",
    TOOL_TOWER: "Tower 0xBF (rect 1×1; custo 75)",
    TOOL_BARRACKS: "Barracks 0xE4 3×3 (custo 400; um stamp, fantasma segue o rato)",
    TOOL_WALL: "Wall 0xC1/0xC2 linha (custo 20; Gate 0xC0 na estrada, custo 5)",
    TOOL_AVENTINE: "Aventine 0xAF 2×2 (custo 100; stamp-follow)",
    TOOL_JANICULAN: "Janiculan 0xB2 3×3 (custo 400; stamp-follow)",
    TOOL_PALATINE: "Palatine 0xB7 4×4 (sem débito C2MODEL; stamp-follow)",
    TOOL_THEATER: "Theater 0xE5 2×2 (custo 300; stamp-follow)",
    TOOL_ODEUM: "Odeum 0xE6 2×2 (custo 500; stamp-follow)",
    TOOL_COLISEUM: "Coliseum 0xE8 3×3 (custo 1000; stamp-follow)",
    TOOL_CIRCUS: "Circus 0xEB+0xEC 6×3 (custo 1500; um ghost pareado)",
    TOOL_CMAXIMUS: "C.Maximus 0xED+0xEE 4×8 (custo 2500; um ghost pareado)",
    TOOL_SHRINE: "Shrine 0xA2 (rect 1×1; custo 80; família 0xA2–0xA5)",
    TOOL_TEMPLE: "Temple 0xA6 2×2 (custo 200; stamp-follow)",
    TOOL_BASILICA: "Basilica 0xAB 3×3 (custo 600; stamp-follow)",
    TOOL_GRAMMATICUS: "Grammaticus 0xF3 2×2 (custo 250; stamp-follow)",
    TOOL_RHETOR: "Rhetor 0xF4 3×3 (custo 500; stamp-follow)",
    TOOL_LIBRARY: "Library 0xF5 3×3 (custo 1000; stamp-follow)",
    TOOL_BATHS: "Baths 0xDF 2×2 (custo 30; stamp-follow)",
    TOOL_HOSPITAL: "Hospital 0xFB 3×3 (custo 500; stamp-follow)",
    TOOL_MARKET: "Market 0xFC 2×2 (custo 40; stamp-follow)",
    TOOL_FACTORY: "Factory 0xFA 3×3 (custo 80; +19=0 Bakery)",
}


@dataclass(frozen=True)
class FlyoutItem:
    key: str
    label: str
    tool: str | None
    hint: str


# Nested names from build_palette.md §0. tool=None → ainda não.
_FLYOUTS: dict[str, tuple[FlyoutItem, ...]] = {
    "water": (
        FlyoutItem("reservoir", "Reservoir", TOOL_RESERVOIR, _TOOL_HINT[TOOL_RESERVOIR]),
        FlyoutItem("aqueduct", "Aqueduct", TOOL_AQUEDUCT, _TOOL_HINT[TOOL_AQUEDUCT]),
        FlyoutItem("well", "Well", TOOL_WELL, _TOOL_HINT[TOOL_WELL]),
        FlyoutItem("fountain", "Fountain", TOOL_FOUNTAIN, _TOOL_HINT[TOOL_FOUNTAIN]),
    ),
    "security": (
        FlyoutItem("wall", "Wall", TOOL_WALL, _TOOL_HINT[TOOL_WALL]),
        FlyoutItem("tower", "Tower", TOOL_TOWER, _TOOL_HINT[TOOL_TOWER]),
        FlyoutItem("barracks", "Barracks", TOOL_BARRACKS, _TOOL_HINT[TOOL_BARRACKS]),
        FlyoutItem("praefecture", "Praefecture", TOOL_PREFECTURE, _TOOL_HINT[TOOL_PREFECTURE]),
    ),
    "amenities": (
        FlyoutItem("gardens", "Gardens", TOOL_GARDEN, _TOOL_HINT[TOOL_GARDEN]),
        FlyoutItem("plaza", "Plaza", TOOL_PLAZA, _TOOL_HINT[TOOL_PLAZA]),
    ),
    "forums": (
        FlyoutItem("aventine", "Aventine", TOOL_AVENTINE, _TOOL_HINT[TOOL_AVENTINE]),
        FlyoutItem("janiculan", "Janiculan", TOOL_JANICULAN, _TOOL_HINT[TOOL_JANICULAN]),
        FlyoutItem("palatine", "Palatine", TOOL_PALATINE, _TOOL_HINT[TOOL_PALATINE]),
    ),
    "entertainment": (
        FlyoutItem("theater", "Theater", TOOL_THEATER, _TOOL_HINT[TOOL_THEATER]),
        FlyoutItem("odeum", "Odeum", TOOL_ODEUM, _TOOL_HINT[TOOL_ODEUM]),
        FlyoutItem("arena", "Arena", None, "Arena 0xE7 — leftover (DAT 3×3, sem origem SAV / +4)"),
        FlyoutItem("coliseum", "Coliseum", TOOL_COLISEUM, _TOOL_HINT[TOOL_COLISEUM]),
        FlyoutItem("circus", "Circus", TOOL_CIRCUS, _TOOL_HINT[TOOL_CIRCUS]),
        FlyoutItem("cmaximus", "C.Maximus", TOOL_CMAXIMUS, _TOOL_HINT[TOOL_CMAXIMUS]),
    ),
    "worship": (
        FlyoutItem("shrine", "Shrine", TOOL_SHRINE, _TOOL_HINT[TOOL_SHRINE]),
        FlyoutItem("temple", "Temple", TOOL_TEMPLE, _TOOL_HINT[TOOL_TEMPLE]),
        FlyoutItem("basilica", "Basilica", TOOL_BASILICA, _TOOL_HINT[TOOL_BASILICA]),
    ),
    "education": (
        FlyoutItem("grammaticus", "Grammaticus", TOOL_GRAMMATICUS, _TOOL_HINT[TOOL_GRAMMATICUS]),
        FlyoutItem("rhetor", "Rhetor", TOOL_RHETOR, _TOOL_HINT[TOOL_RHETOR]),
        FlyoutItem("library", "Library", TOOL_LIBRARY, _TOOL_HINT[TOOL_LIBRARY]),
    ),
    "health": (
        FlyoutItem("baths", "Baths", TOOL_BATHS, _TOOL_HINT[TOOL_BATHS]),
        FlyoutItem("hospital", "Hospital", TOOL_HOSPITAL, _TOOL_HINT[TOOL_HOSPITAL]),
    ),
    "commerce": (
        FlyoutItem("market", "Market", TOOL_MARKET, _TOOL_HINT[TOOL_MARKET]),
        FlyoutItem("factory", "Factory", TOOL_FACTORY, _TOOL_HINT[TOOL_FACTORY]),
    ),
}

_ITEM_H = 16
_FLYOUT_W = 118


@dataclass(frozen=True)
class FlyoutHit:
    key: str
    item: FlyoutItem
    rect: tuple[int, int, int, int]


@dataclass
class ClickResult:
    """Sidebar / flyout click. ``tool`` None means keep the current tool."""

    tool: str | None
    message: str
    keep_tool: bool = False


@dataclass
class PaletteState:
    """Open flyout + hitboxes. Host-only list; not the EXE popup art."""

    open: str | None = None
    hits: list[FlyoutHit] = field(default_factory=list)
    _anchor: tuple[int, int, int, int] | None = None

    def close(self) -> None:
        self.open = None
        self.hits = []
        self._anchor = None

    def hit_test(self, x: int, y: int, ox: int = 0) -> FlyoutHit | None:
        nx = x - ox
        for hit in self.hits:
            rx, ry, rw, rh = hit.rect
            if rx <= nx < rx + rw and ry <= y < ry + rh:
                return hit
        return None

    def covers(self, x: int, y: int, ox: int = 0) -> bool:
        return self.hit_test(x, y, ox=ox) is not None

    def click_grid(self, action: str, anchor: tuple[int, int, int, int] | None = None) -> ClickResult:
        if action in _DIRECT:
            self.close()
            tool = _DIRECT[action]
            return ClickResult(tool, f"ferramenta: {_TOOL_HINT[tool]}")
        items = _FLYOUTS.get(action)
        if items is None:
            self.close()
            return ClickResult(None, f"{action} — ainda não")
        if self.open == action:
            self.close()
            return ClickResult(None, f"{_LABEL.get(action, action)} fechado", keep_tool=True)
        self.open = action
        self._anchor = anchor
        self._rebuild_hits()
        names = ", ".join(it.label for it in items)
        return ClickResult(None, f"{_LABEL.get(action, action)}: {names}")

    def click_item(self, key: str) -> ClickResult:
        for hit in self.hits:
            if hit.key != key:
                continue
            item = hit.item
            if item.tool is None:
                return ClickResult(None, item.hint, keep_tool=True)
            return ClickResult(item.tool, f"ferramenta: {item.hint}")
        return ClickResult(None, "flyout", keep_tool=True)

    def _rebuild_hits(self) -> None:
        self.hits = []
        if self.open is None:
            return
        items = _FLYOUTS.get(self.open)
        if not items:
            return
        ax, ay, _aw, _ah = self._anchor or (SIDEBAR_X, 208, 30, 24)
        x = max(4, ax - _FLYOUT_W - 4)
        y = ay
        if y + len(items) * _ITEM_H > 476:
            y = max(24, 476 - len(items) * _ITEM_H)
        for i, item in enumerate(items):
            self.hits.append(
                FlyoutHit(item.key, item, (x, y + i * _ITEM_H, _FLYOUT_W, _ITEM_H))
            )

    def blit(
        self, frame: Image.Image, *, selected: str | None = None, ox: int = 0
    ) -> Image.Image:
        """Draw host flyouts. ``ox`` slides them with the INT_CITY strip."""
        if not self.hits:
            return frame
        out = frame.convert("RGBA")
        draw = ImageDraw.Draw(out)
        font = ImageFont.load_default()
        for hit in self.hits:
            rx, ry, rw, rh = hit.rect
            rx += ox
            placeable = hit.item.tool is not None
            active = selected is not None and hit.item.tool == selected
            fill = (40, 90, 70, 235) if placeable else (36, 36, 40, 230)
            if active:
                fill = (180, 150, 40, 245)
            draw.rectangle((rx, ry, rx + rw - 1, ry + rh - 1), fill=fill)
            draw.rectangle((rx, ry, rx + rw - 1, ry + rh - 1), outline=(200, 190, 140, 255))
            color = (240, 230, 180) if placeable else (150, 150, 150)
            suffix = "" if placeable else " …"
            draw.text((rx + 4, ry + 2), f"{hit.item.label}{suffix}"[:18], fill=color, font=font)
        return out.convert("RGB")


_LABEL = {
    "water": "Water",
    "security": "Security",
    "amenities": "Amenities",
    "forums": "Forums",
    "entertainment": "Entert'ment",
    "worship": "Worship",
    "education": "Education",
    "health": "Sanitation",
    "commerce": "Industry",
}


def action_for_tool(tool: str | None) -> str | None:
    if tool is None:
        return None
    return _TOOL_ACTION.get(tool) or _chrome_action(tool)


def tool_hint(tool: str | None) -> str:
    if tool is None:
        return ""
    return _TOOL_HINT.get(tool, tool)


def selftest() -> list[str]:
    lines: list[str] = []
    pal = PaletteState()
    r = pal.click_grid("housing")
    if r.tool != TOOL_TENT:
        lines.append(f"FAIL  housing {r.tool}")
    else:
        lines.append("ok    housing directo → tent")
    r = pal.click_grid("water", (478, 300, 30, 24))
    if r.tool is not None or pal.open != "water" or len(pal.hits) != 4:
        lines.append(f"FAIL  water flyout tool={r.tool} n={len(pal.hits)}")
    else:
        lines.append("ok    Water abre 4 itens")
    r = pal.click_item("reservoir")
    if r.tool != TOOL_RESERVOIR:
        lines.append(f"FAIL  reservoir {r.tool}")
    else:
        lines.append("ok    Reservoir escolhe 0xBE")
    r = pal.click_item("fountain")
    if r.tool != TOOL_FOUNTAIN:
        lines.append(f"FAIL  fountain {r.message}")
    else:
        lines.append("ok    Fountain escolhe 0xDD")
    r = pal.click_grid("security", (478, 330, 30, 24))
    r = pal.click_item("tower")
    if r.tool != TOOL_TOWER:
        lines.append(f"FAIL  tower {r.tool}")
    else:
        lines.append("ok    Tower escolhe 0xBF")
    r = pal.click_item("barracks")
    if r.tool != TOOL_BARRACKS:
        lines.append(f"FAIL  barracks {r.tool}")
    else:
        lines.append("ok    Barracks escolhe 0xE4")
    r = pal.click_item("wall")
    if r.tool != TOOL_WALL:
        lines.append(f"FAIL  wall {r.message}")
    else:
        lines.append("ok    Wall escolhe linha 0xC1/0xC2")
    r = pal.click_grid("amenities", (478, 360, 30, 24))
    r = pal.click_item("gardens")
    if r.tool != TOOL_GARDEN:
        lines.append(f"FAIL  gardens {r.tool}")
    else:
        lines.append("ok    Gardens escolhe ferramenta")
    r = pal.click_item("plaza")
    if r.tool != TOOL_PLAZA:
        lines.append(f"FAIL  plaza {r.tool}")
    else:
        lines.append("ok    Plaza escolhe 0x7C")
    r = pal.click_grid("forums", (478, 280, 30, 24))
    r = pal.click_item("aventine")
    if r.tool != TOOL_AVENTINE:
        lines.append(f"FAIL  forums {r.message}")
    else:
        lines.append("ok    Aventine escolhe 0xAF")
    r = pal.click_grid("entertainment", (478, 300, 30, 24))
    r = pal.click_item("arena")
    if r.tool is not None or "leftover" not in r.message:
        lines.append(f"FAIL  arena {r.message}")
    else:
        lines.append("ok    Arena permanece leftover")
    r = pal.click_item("circus")
    if r.tool != TOOL_CIRCUS:
        lines.append(f"FAIL  circus {r.tool}")
    else:
        lines.append("ok    Circus escolhe 0xEB+0xEC")
    r = pal.click_grid("health", (478, 330, 30, 24))
    r = pal.click_item("baths")
    if r.tool != TOOL_BATHS:
        lines.append(f"FAIL  health {r.message}")
    else:
        lines.append("ok    Sanitation → Baths 0xDF")
    r = pal.click_grid("commerce", (478, 330, 30, 24))
    r = pal.click_item("factory")
    if r.tool != TOOL_FACTORY:
        lines.append(f"FAIL  commerce {r.message}")
    else:
        lines.append("ok    Industry → Factory 0xFA")
    from app.city_chrome import grid_action_at

    if grid_action_at(8) != "health" or grid_action_at(9) != "commerce":
        lines.append(
            f"FAIL  row2 extras {grid_action_at(8)}/{grid_action_at(9)} "
            "(want health/commerce = column Sanitation then workshop Industry)"
        )
    else:
        lines.append("ok    sprite 21 Sanitation / sprite 22 Industry")
    if _LABEL.get("health") != "Sanitation" or _LABEL.get("commerce") != "Industry":
        lines.append("FAIL  flyout labels")
    else:
        lines.append("ok    labels Sanitation / Industry")
    if action_for_tool(TOOL_WELL) != "water":
        lines.append("FAIL  action well")
    else:
        lines.append("ok    Well destaca Water")
    if action_for_tool(TOOL_TEMPLE) != "worship":
        lines.append("FAIL  action temple")
    else:
        lines.append("ok    Temple destaca Worship")
    return lines
