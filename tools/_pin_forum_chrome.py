#!/usr/bin/env python3
"""Pin remaining Forum chrome: [28] grid, [33] Empire, [34] Legion, [35] Industry,
[37] Rome, [30]/[7]/[76] Personal. EMPIRE.PL8 640×480. Ghidra HTTP optional.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.assets import load_eng
from app.city_sim import SimState
from app.config import find_file, resolve_game_dir
from app.forum import (
    KIND_CENTURION,
    KIND_CHROME,
    KIND_EMPIRE,
    KIND_MERCHANT,
    KIND_PERSONAL,
    KIND_ROME,
    ForumState,
    button_rect,
    click_forum,
    empire_circa_title,
    load_empire_map,
    load_governor_name,
    promotions_left,
    selftest as forum_selftest,
)

OUT = Path(__file__).resolve().parents[1] / "notes" / "_pin_forum_chrome.txt"


def main() -> None:
    lines: list[str] = []
    game, how = resolve_game_dir()
    lines.append(f"game {game} ({how})")
    eng = load_eng(game)
    for slot, n, lab in (
        (28, 12, "chrome [28]"),
        (30, 6, "personal [30]"),
        (33, 4, "empire [33]"),
        (34, 12, "legion [34]"),
        (35, 7, "industry [35]"),
        (37, 28, "rome [37]"),
        (7, 11, "ranks [7]"),
    ):
        lines.append(f"\n===== {lab} =====")
        for i in range(n):
            got = eng.skip(slot, i)
            if got:
                lines.append(f"  +{i:2d} {got!r}")
    lines.append(f"\nINF name {load_governor_name(game)!r}")
    lines.append(f"circa -228 {empire_circa_title(-228, eng)!r}")
    lines.append(f"Decurion promotions {promotions_left(1)}")
    emp = load_empire_map(game)
    lines.append(f"EMPIRE.PL8 {None if emp is None else emp.size}")
    for name in ("EMPIRE.PL8", "E_PARTS2.PL8", "FORUM.PL8", "CAESAR2.INF"):
        path = find_file(game, name)
        lines.append(f"  {name} {'ok' if path else 'MISSING'}")
    st = ForumState(kind=KIND_CHROME)
    sim = SimState(city_only=1)
    for i, kind, lab in (
        (8, KIND_MERCHANT, "MERCHANT"),
        (1, KIND_CENTURION, "CENTURION"),
        (9, KIND_ROME, "ROME"),
        (7, KIND_PERSONAL, "PERSONAL"),
        (2, KIND_EMPIRE, "EMPIRE MAP"),
        (5, KIND_CHROME, "CLEAR FORUM"),
    ):
        st.kind = KIND_CHROME
        x, y, _w, _h = button_rect(i)
        msg = click_forum(st, x + 2, y + 2, sim)
        lines.append(f"click {lab}: kind={st.kind} msg={msg!r} expect={kind}")
    lines.append("\n===== forum selftest =====")
    lines.extend(forum_selftest())
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
