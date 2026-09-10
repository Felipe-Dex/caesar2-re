"""City build flyouts — Water / Security / Amenities plus remaining menus.

Decoded INT_CITY frames bind content to the picture: sprite 21 bottles
→ Industry (Market / Factory types), sprite 22 vessel+cross → Sanitation
(Baths / Hospital). HELP.ENG Cty Icn is the same order. Title and items
stay paired. Arena stays leftover (no SAV origin). Factory opens the
goods picker (HELP: eight kinds of Business; C2.ENG [61] Bakery).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from app.city_chrome import SIDEBAR_X, action_for_tool as _chrome_action
from app.unlocks import POP_UNLOCK, peak_population
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
    set_factory_goods,
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
    TOOL_FACTORY: "Factory 0xFA 3×3 (custo 80; goods picker +19)",
}


# HELP.ENG: "Markets, and eight kinds of Business." C2.ENG [61] Bakery.
# Other UI names from factory.md (origin +19, Achea / D.SAV / 20230610).
# Leftover EXE nibbles 4/6/8/10/12 (gems/iron/clay/marble/silk) have no UI name.
FACTORY_KINDS: tuple[tuple[int, str], ...] = (
    (0, "Bakery"),
    (1, "Winery"),
    (2, "Butcher"),
    (3, "Tailor"),
    (5, "Lead Works"),
    (7, "Copper Works"),
    (9, "Glass Works"),
    (11, "Stone Works"),
)


@dataclass(frozen=True)
class FlyoutItem:
    key: str
    label: str
    tool: str | None
    hint: str
    goods: int | None = None


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
        FlyoutItem("factory", "Factory", None, "Factory 0xFA — choose goods type"),
    ),
    "factory_types": tuple(
        FlyoutItem(
            f"factory_{nibble}",
            name,
            TOOL_FACTORY,
            f"Factory 0xFA 3×3 +19={nibble} {name}",
            goods=nibble,
        )
        for nibble, name in FACTORY_KINDS
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
    pop_peak: int = 0
    factory_goods: int = 0

    def close(self) -> None:
        self.open = None
        self.hits = []
        self._anchor = None

    def sync_unlocks(self, sim) -> None:
        self.pop_peak = peak_population(sim)
        if self.open is not None:
            self._rebuild_hits()

    def hit_test(self, x: int, y: int, ox: int = 0) -> FlyoutHit | None:
        nx = x - ox
        for hit in self.hits:
            rx, ry, rw, rh = hit.rect
            if rx <= nx < rx + rw and ry <= y < ry + rh:
                return hit
        return None

    def covers(self, x: int, y: int, ox: int = 0) -> bool:
        return self.hit_test(x, y, ox=ox) is not None

    def _items_for(self, action: str) -> tuple[FlyoutItem, ...]:
        items = _FLYOUTS.get(action)
        if not items:
            return ()
        out: list[FlyoutItem] = []
        for it in items:
            need = POP_UNLOCK.get(it.key, 0)
            if need and self.pop_peak < need:
                out.append(
                    FlyoutItem(
                        it.key,
                        it.label,
                        None,
                        f"leftover — pop {need} (FAQ / C2MODEL)",
                        it.goods,
                    )
                )
            else:
                out.append(it)
        return tuple(out)

    def click_grid(self, action: str, anchor: tuple[int, int, int, int] | None = None) -> ClickResult:
        if action in _DIRECT:
            self.close()
            tool = _DIRECT[action]
            return ClickResult(tool, f"ferramenta: {_TOOL_HINT[tool]}")
        items = self._items_for(action)
        if not items and action not in _FLYOUTS:
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
            if key == "factory":
                return self.click_grid("factory_types", self._anchor)
            if item.tool is None:
                return ClickResult(None, item.hint, keep_tool=True)
            if item.goods is not None:
                self.factory_goods = item.goods & 0xF
                set_factory_goods(self.factory_goods)
            # EXE: pick dismisses the popup; the 3×5 category stays yellow.
            self.close()
            return ClickResult(item.tool, f"ferramenta: {item.hint}")
        return ClickResult(None, "flyout", keep_tool=True)

    def _rebuild_hits(self) -> None:
        self.hits = []
        if self.open is None:
            return
        items = self._items_for(self.open)
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
        """Draw host flyouts. ``ox`` slides them with the INT_CITY strip.

        Hits live in native 640 space (sidebar at x=478). Window clicks pass
        the same ``ox`` as ``hit_test`` / ``covers``. RGBA frames keep alpha
        outside the flyout so the iso well can sit underneath.
        """
        if not self.hits:
            return frame
        keep_alpha = frame.mode == "RGBA"
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
        if keep_alpha:
            return out
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
    "factory_types": "Factory",
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
    res = pal.hits[0] if pal.hits else None
    if res is None or res.key != "reservoir":
        lines.append("FAIL  flyout hit reservoir missing")
    else:
        rx, ry, rw, rh = res.rect
        slide = 80
        at0 = pal.hit_test(rx + 2, ry + 2, ox=0)
        at_ox = pal.hit_test(rx + slide + 2, ry + 2, ox=slide)
        miss = pal.hit_test(rx + 2, ry + 2, ox=slide)
        if (
            at0 is None
            or at0.key != "reservoir"
            or at_ox is None
            or at_ox.key != "reservoir"
            or miss is not None
        ):
            lines.append(
                f"FAIL  flyout hit ox at0={getattr(at0, 'key', None)} "
                f"at_ox={getattr(at_ox, 'key', None)} miss={getattr(miss, 'key', None)}"
            )
        else:
            lines.append("ok    flyout hit +ox matches chrome slide")
    r = pal.click_item("reservoir")
    if r.tool != TOOL_RESERVOIR or pal.open is not None or pal.hits:
        lines.append(f"FAIL  reservoir {r.tool} open={pal.open} hits={len(pal.hits)}")
    else:
        lines.append("ok    Reservoir escolhe 0xBE e fecha flyout")
    r = pal.click_grid("water", (478, 300, 30, 24))
    if pal.open != "water" or len(pal.hits) != 4:
        lines.append(f"FAIL  water reopen open={pal.open} n={len(pal.hits)}")
    else:
        lines.append("ok    Water reabre depois do pick")
    r = pal.click_item("fountain")
    if r.tool != TOOL_FOUNTAIN or pal.open is not None:
        lines.append(f"FAIL  fountain {r.message} open={pal.open}")
    else:
        lines.append("ok    Fountain escolhe 0xDD")
    r = pal.click_grid("security", (478, 330, 30, 24))
    r = pal.click_item("tower")
    if r.tool != TOOL_TOWER or pal.open is not None:
        lines.append(f"FAIL  tower {r.tool} open={pal.open}")
    else:
        lines.append("ok    Tower escolhe 0xBF")
    r = pal.click_grid("security", (478, 330, 30, 24))
    r = pal.click_item("barracks")
    if r.tool != TOOL_BARRACKS:
        lines.append(f"FAIL  barracks {r.tool}")
    else:
        lines.append("ok    Barracks escolhe 0xE4")
    r = pal.click_grid("security", (478, 330, 30, 24))
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
    r = pal.click_grid("amenities", (478, 360, 30, 24))
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
    if r.tool is not None or "leftover" not in r.message or pal.open != "entertainment":
        lines.append(f"FAIL  arena {r.message} open={pal.open}")
    else:
        lines.append("ok    Arena permanece leftover")
    r = pal.click_item("circus")
    if r.tool != TOOL_CIRCUS or pal.open is not None:
        lines.append(f"FAIL  circus {r.tool} open={pal.open}")
    else:
        lines.append("ok    Circus escolhe 0xEB+0xEC")
    r = pal.click_grid("health", (478, 330, 30, 24))
    r = pal.click_item("baths")
    if r.tool != TOOL_BATHS or pal.open is not None:
        lines.append(f"FAIL  health {r.message} open={pal.open}")
    else:
        lines.append("ok    Sanitation → Baths 0xDF")
    r = pal.click_grid("commerce", (478, 330, 30, 24))
    if pal.open != "commerce" or "Market" not in r.message or "Factory" not in r.message:
        lines.append(f"FAIL  industry items {r.message}")
    else:
        lines.append("ok    Industry title + Market/Factory items")
    r = pal.click_item("factory")
    if pal.open != "factory_types" or r.tool is not None:
        lines.append(f"FAIL  factory picker {r.message} open={pal.open}")
    else:
        lines.append("ok    Factory abre type picker")
    r = pal.click_item("factory_1")
    if r.tool != TOOL_FACTORY or pal.factory_goods != 1 or pal.open is not None:
        lines.append(f"FAIL  winery {r.message} goods={pal.factory_goods} open={pal.open}")
    else:
        lines.append("ok    Factory type Winery +19=1")
    pal.pop_peak = 0
    r = pal.click_grid("forums", (478, 280, 30, 24))
    r = pal.click_item("palatine")
    if r.tool is not None or "leftover" not in r.message or pal.open != "forums":
        lines.append(f"FAIL  palatine locked {r.message} open={pal.open}")
    else:
        lines.append("ok    Palatine leftover at pop 0")
    pal.pop_peak = 1800
    pal.close()
    r = pal.click_grid("forums", (478, 280, 30, 24))
    r = pal.click_item("palatine")
    if r.tool != TOOL_PALATINE or pal.open is not None:
        lines.append(f"FAIL  palatine unlock {r.message} open={pal.open}")
    else:
        lines.append("ok    Palatine unlock at pop 1800")
    from app.city_chrome import SPRITE_GRID, grid_action_at

    if grid_action_at(8) != "commerce" or grid_action_at(9) != "health":
        lines.append(
            f"FAIL  row2 extras {grid_action_at(8)}/{grid_action_at(9)} "
            "(want commerce/health = sprite 21 bottles Industry then 22 vessel Sanitation)"
        )
    elif SPRITE_GRID[8] != (21, "commerce") or SPRITE_GRID[9] != (22, "health"):
        lines.append(f"FAIL  sprite dump {SPRITE_GRID[8]} {SPRITE_GRID[9]}")
    else:
        lines.append("ok    sprite 21 Industry bottles / sprite 22 Sanitation vessel")
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
    from app.city_chrome import CityChrome, SIDEBAR_X, chrome_ox

    ch = CityChrome._fallback()
    water = next((h for h in ch.hits if h.action == "water"), None)
    slide = chrome_ox(720)
    if water is None:
        lines.append("FAIL  chrome water hit missing")
    else:
        wx, wy, _ww, _wh = water.rect
        hit = ch.hit_test(wx + slide + 1, wy + 1, ox=slide)
        covered = ch.covers(SIDEBAR_X + slide, wy, ox=slide)
        if hit is None or hit.action != "water" or not covered:
            lines.append(
                f"FAIL  chrome 3x5 ox hit={getattr(hit, 'action', None)} covers={covered}"
            )
        else:
            lines.append("ok    INT_CITY 3×5 hit +ox (Water)")
    left = next((h for h in ch.hits if h.action == "rotate_left"), None)
    right = next((h for h in ch.hits if h.action == "rotate_right"), None)
    if left is None or right is None:
        lines.append("FAIL  chrome rotate hits missing")
    else:
        lx, ly, _lw, _lh = left.rect
        hit = ch.hit_test(lx + 1, ly + 1)
        if hit is None or hit.action != "rotate_left":
            lines.append(f"FAIL  rotate_left hit={getattr(hit, 'action', None)}")
        else:
            lines.append("ok    INT_CITY rotate-left / rotate-right gadgets")
    from app.city_chrome import selftest as chrome_selftest

    lines.extend(chrome_selftest())
    return lines
