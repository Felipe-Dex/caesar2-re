#!/usr/bin/env python3
"""Dump findings/D.SAV chunk 13: north-tip tiles + 0xFA factory origins.

Does not copy or commit the SAV.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from app.city_map import (  # noqa: E402
    ID_TERRAIN_MAX,
    MAP_H,
    MAP_W,
    SHEET_BUILD1A,
    SHEET_BUILD1B,
    SHEET_BUILD1C,
    SHEET_BUILD1D,
    SHEET_CITYFIXT_BLD,
    SHEET_HOUSES1,
    load_city_from_sav,
)
from _20230610_parse import ACHEA_NAMED, advisor_type, same_id_blobs  # noqa: E402

SAV = ROOT / "findings" / "D.SAV"

SHEET_NAME = {
    SHEET_HOUSES1: "HOUSES1",
    SHEET_BUILD1A: "BUILD1A",
    SHEET_BUILD1B: "BUILD1B",
    SHEET_BUILD1C: "BUILD1C",
    SHEET_BUILD1D: "BUILD1D",
    SHEET_CITYFIXT_BLD: "CITYFIXT",
}

KNOWN_PLUS19 = {
    0: "Bakery",
    1: "Winery",
    2: "Butcher",
    3: "Tailor",
    5: "Lead Works",
    7: "Copper Works",
    9: "Glass Works",
    11: "Stone Works",
    13: "Spice Dealer",
    14: "Ivory Dealer",
    15: "Fish Monger",
}


def dump_tile(city, x: int, y: int, label: str = "") -> None:
    if not (0 <= x < MAP_W and 0 <= y < MAP_H):
        print(f"  {label} ({x},{y}) OOB")
        return
    t = city.tile(x, y)
    name = ACHEA_NAMED.get(t.terrain_id, "???")
    sh = SHEET_NAME.get(t.draw & 0x1C, f"+3={t.draw:#x}")
    print(
        f"  {label:16s} ({x:2d},{y:2d})  id=0x{t.terrain_id:02X} ({t.terrain_id:3d})  "
        f"name={name:16s}  sheet={sh:8s}  type={advisor_type(t.terrain_id)}  "
        f"+1=0x{t.flags:02X} +3=0x{t.draw:02X} +4=0x{t.variant:02X} "
        f"+5=0x{t.spawn_packed:02X} +9=0x{t.overlay_anim:02X} "
        f"+13=0x{t.desirability:02X} +19=0x{t.special:02X} (lo={t.special & 0xF})"
    )
    print(f"       raw={' '.join(f'{b:02X}' for b in t.raw)}")


def main() -> None:
    if not SAV.is_file():
        raise SystemExit(f"missing {SAV}")
    print(f"=== SAV {SAV}  {SAV.stat().st_size} B ===")
    city = load_city_from_sav(SAV, game=ROOT)
    tiles = [[city.tile(x, y) for x in range(MAP_W)] for y in range(MAP_H)]
    ids = [[t.terrain_id for t in row] for row in tiles]
    hist = Counter(tid for row in ids for tid in row if tid >= ID_TERRAIN_MAX)
    blobs = same_id_blobs(ids)

    print("\n=== NORTH TIP (0,0)-(3,0) + 6x6 neighborhood ===")
    user = {(0, 0): "Well", (1, 0): "Cleared", (2, 0): "Rubble", (3, 0): "Theater"}
    for x in range(4):
        dump_tile(city, x, 0, user.get((x, 0), ""))

    print("\n=== 8x8 around (0,0)-(5,5) ids ===")
    for y in range(8):
        row = " ".join(f"{ids[y][x]:02X}" for x in range(8))
        print(f"  y={y}  {row}")

    print("\n=== 8x8 +5 lo-nibble (origin=0) ===")
    for y in range(8):
        row = " ".join(f"{tiles[y][x].spawn_packed & 0xF:X}" for x in range(8))
        print(f"  y={y}  {row}")

    print("\n=== every tile in 6x6 with raw ===")
    for y in range(6):
        for x in range(6):
            dump_tile(city, x, y)

    print("\n=== HISTOGRAM id>=0x78 ===")
    for tid, n in hist.most_common():
        name = ACHEA_NAMED.get(tid, "???")
        print(f"  0x{tid:02X}  n={n:4d}  {name}")

    print("\n=== WELL / THEATER CANDIDATE IDS (0xBC-0xBD, 0xCB-0xCE, 0xE5, 0xE7) ===")
    for tid in [0xBC, 0xBD, 0xCB, 0xCC, 0xCD, 0xCE, 0xE5, 0xE7, 0xE9, 0xEA]:
        cells = [(x, y) for y in range(MAP_H) for x in range(MAP_W) if ids[y][x] == tid]
        print(f"  0x{tid:02X}  n={len(cells)}")
        for cx, cy in cells[:20]:
            dump_tile(city, cx, cy, f"  0x{tid:02X}")

    print("\n=== BLOBS overlapping (0,0)-(5,5) ===")
    for b in blobs:
        if b["xmax"] < 0 or b["xmin"] > 5 or b["ymax"] < 0 or b["ymin"] > 5:
            continue
        print(
            f"  id=0x{b['id']:02X}  {b['w']}x{b['h']} n={b['n']}  "
            f"({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
            f"{ACHEA_NAMED.get(b['id'], 'UNNAMED')}"
        )

    print("\n=== TERRAIN ids at (0,0)-(5,5) that are <0x78 ===")
    for y in range(6):
        for x in range(6):
            t = tiles[y][x]
            if t.terrain_id < ID_TERRAIN_MAX:
                print(
                    f"  ({x},{y}) id=0x{t.terrain_id:02X} +1=0x{t.flags:02X} "
                    f"+4=0x{t.variant:02X} +9=0x{t.overlay_anim:02X}"
                )

    print("\n=== ALL 0xFA ORIGINS (+5 lo-nibble == 0) ===")
    origins = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            t = tiles[y][x]
            if t.terrain_id != 0xFA:
                continue
            if (t.spawn_packed & 0xF) != 0:
                continue
            origins.append((x, y, t))
    origins.sort(key=lambda z: (z[1], z[0]))
    print(f"  count={len(origins)}")
    for i, (x, y, t) in enumerate(origins, start=1):
        lo = t.special & 0xF
        known = KNOWN_PLUS19.get(lo, "NEW?")
        print(
            f"  #{i:02d}  ({x:2d},{y:2d})  iso_n={x + y:3d}  "
            f"+4=0x{t.variant:02X} +5=0x{t.spawn_packed:02X} "
            f"+9=0x{t.overlay_anim:02X} +19=0x{t.special:02X} lo={lo:2d}  {known}"
        )

    print("\n=== 0xFA origins sorted by iso north (x+y asc) then x ===")
    by_iso = sorted(origins, key=lambda z: (z[0] + z[1], z[0], z[1]))
    for i, (x, y, t) in enumerate(by_iso, start=1):
        lo = t.special & 0xF
        known = KNOWN_PLUS19.get(lo, "NEW?")
        print(
            f"  iso#{i:02d}  ({x:2d},{y:2d})  x+y={x + y:3d}  lo={lo:2d}  {known}"
        )

    print("\n=== 0xFA origins grouped by x (same column) ===")
    by_x: dict[int, list] = {}
    for item in origins:
        by_x.setdefault(item[0], []).append(item)
    for x, items in sorted(by_x.items(), key=lambda kv: -len(kv[1])):
        items = sorted(items, key=lambda z: z[1])
        print(f"  x={x}  n={len(items)}  y={[z[1] for z in items]}")
        for xx, y, t in items:
            lo = t.special & 0xF
            print(
                f"       ({xx},{y}) lo={lo:2d} {KNOWN_PLUS19.get(lo, 'NEW?')}"
            )

    print("\n=== ALL 0xFA BLOBS ===")
    fa = [b for b in blobs if b["id"] == 0xFA]
    fa.sort(key=lambda b: (b["ymin"], b["xmin"]))
    for i, b in enumerate(fa, start=1):
        print(
            f"  FA{i:02d}  ({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
            f"{b['w']}x{b['h']} n={b['n']}"
        )

    print("\n=== UNNAMED IDS ===")
    unnamed_ids = sorted(tid for tid in hist if tid not in ACHEA_NAMED)
    for tid in unnamed_ids:
        id_blobs = [b for b in blobs if b["id"] == tid]
        sizes = Counter(f"{b['w']}x{b['h']}n{b['n']}" for b in id_blobs)
        print(
            f"  0x{tid:02X}  tiles={hist[tid]:4d}  blobs={len(id_blobs)}  "
            f"type={advisor_type(tid)}  sizes={dict(sizes)}"
        )
        for b in sorted(id_blobs, key=lambda z: (z["ymin"], z["xmin"]))[:8]:
            print(
                f"       ({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
                f"{b['w']}x{b['h']} n={b['n']}"
            )


if __name__ == "__main__":
    main()
