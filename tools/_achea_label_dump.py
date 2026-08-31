#!/usr/bin/env python3
"""Dump ACHEA23 tiles for screenshot Q&A. Does not copy the SAV."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.city_map import (  # noqa: E402
    ID_TERRAIN_MAX,
    MAP_H,
    MAP_W,
    load_city_from_sav,
)

SAV = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV")

SHEET = {
    0x00: "HOUSES1",
    0x04: "BUILD1A",
    0x08: "BUILD1B",
    0x0C: "BUILD1C",
    0x10: "CITYFIXT",
    0x14: "BUILD1D",
}


def sn(draw: int) -> str:
    return SHEET.get(draw & 0x1C, f"?{draw & 0x1C:#x}")


def fmt(t, x, y) -> str:
    return (
        f"({x:2d},{y:2d}) id=0x{t.terrain_id:02X} {sn(t.draw):8s} "
        f"+1=0x{t.flags:02X} +3=0x{t.draw:02X} +4=0x{t.variant:02X} "
        f"+12=0x{t.unknown12:02X} +17=0x{t.unknown17:02X}"
    )


def same_id_blobs(ids: list[list[int]]) -> list[dict]:
    seen = [[False] * MAP_W for _ in range(MAP_H)]
    out: list[dict] = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            tid = ids[y][x]
            if tid < ID_TERRAIN_MAX or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            cells: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < MAP_W and 0 <= ny < MAP_H and not seen[ny][nx] and ids[ny][nx] == tid:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            out.append(
                {
                    "id": tid,
                    "n": len(cells),
                    "xmin": min(xs),
                    "xmax": max(xs),
                    "ymin": min(ys),
                    "ymax": max(ys),
                    "w": max(xs) - min(xs) + 1,
                    "h": max(ys) - min(ys) + 1,
                    "cells": cells,
                }
            )
    return out


def any_id_blobs(ids: list[list[int]], pred) -> list[dict]:
    seen = [[False] * MAP_W for _ in range(MAP_H)]
    out: list[dict] = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            if not pred(ids[y][x]) or seen[y][x]:
                continue
            stack = [(x, y)]
            seen[y][x] = True
            cells: list[tuple[int, int]] = []
            idc: Counter[int] = Counter()
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                idc[ids[cy][cx]] += 1
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < MAP_W and 0 <= ny < MAP_H and not seen[ny][nx] and pred(ids[ny][nx]):
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            out.append(
                {
                    "n": len(cells),
                    "xmin": min(xs),
                    "xmax": max(xs),
                    "ymin": min(ys),
                    "ymax": max(ys),
                    "w": max(xs) - min(xs) + 1,
                    "h": max(ys) - min(ys) + 1,
                    "idc": idc,
                    "cells": cells,
                }
            )
    return out


def dump_rect(city, x0, y0, x1, y1, title: str) -> None:
    print(f"=== {title} x={x0}..{x1} y={y0}..{y1} ===")
    print("     " + " ".join(f"{x:02d}" for x in range(x0, x1 + 1)))
    for y in range(y0, y1 + 1):
        row = []
        for x in range(x0, x1 + 1):
            tid = city.tile(x, y).terrain_id
            row.append(".." if tid < 0x78 else f"{tid:02X}")
        print(f"y={y:02d} " + " ".join(row))


def dump_rect_detail(city, x0, y0, x1, y1, title: str) -> None:
    print(f"=== {title} DETAIL ===")
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            t = city.tile(x, y)
            if t.terrain_id >= 0x78:
                print("  " + fmt(t, x, y))


def main() -> None:
    city = load_city_from_sav(SAV)
    ids = [[city.tile(x, y).terrain_id for x in range(MAP_W)] for y in range(MAP_H)]
    blobs = same_id_blobs(ids)

    print("=== 1. ALL 0xBF ===")
    bfs = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            if ids[y][x] == 0xBF:
                t = city.tile(x, y)
                bfs.append((x, y))
                print("  " + fmt(t, x, y))
    print(f"  count={len(bfs)} expected (78,1) and (55,1): {(78,1) in bfs} {(55,1) in bfs}")

    print("=== 2. WALK x=55..78 y=0..4 ===")
    dump_rect(city, 50, 0, 79, 6, "wall corridor")
    print("--- y=1 x=55..78 ---")
    for x in range(55, 79):
        t = city.tile(x, 1)
        print("  " + fmt(t, x, 1))
    print("--- unique ids on y=1 x=55..78 ---")
    c = Counter(ids[1][x] for x in range(55, 79))
    print(" ", {f"0x{k:02X}": n for k, n in c.most_common()})

    print("=== 2b. nearby y=0 and y=2 same x range ===")
    for y in (0, 2, 3):
        print(f"--- y={y} ---")
        for x in range(55, 79):
            t = city.tile(x, y)
            if t.terrain_id >= 0x78:
                print("  " + fmt(t, x, y))

    print("=== 2c. unique-id candidates on wall line (count==1 in corridor) ===")
    corridor = [(x, y) for y in range(0, 5) for x in range(55, 79)]
    corr_ids = Counter(ids[y][x] for x, y in corridor if ids[y][x] >= 0x78)
    print("  corridor id counts:", {f"0x{k:02X}": n for k, n in corr_ids.most_common()})
    for (x, y) in corridor:
        tid = ids[y][x]
        if tid >= 0x78 and corr_ids[tid] <= 3:
            print(f"  rare {fmt(city.tile(x, y), x, y)}")

    print("=== 2d. ALL 0x7C-0x81 and 0x78-0x7B near y<=8 x>=50 ===")
    for y in range(9):
        for x in range(50, 80):
            tid = ids[y][x]
            if 0x78 <= tid <= 0x81:
                print("  " + fmt(city.tile(x, y), x, y))

    print("=== 2e. ALL 0xC0-0xCA on y<=8 x>=50 ===")
    for y in range(9):
        for x in range(50, 80):
            tid = ids[y][x]
            if 0xC0 <= tid <= 0xCA:
                print("  " + fmt(city.tile(x, y), x, y))

    print("=== 3. 0xED / 0xEE blobs ===")
    for b in sorted(blobs, key=lambda z: (z["ymin"], z["xmin"])):
        if b["id"] in (0xED, 0xEE):
            print(
                f"  id=0x{b['id']:02X} n={b['n']} {b['w']}x{b['h']} "
                f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})"
            )

    circus = any_id_blobs(ids, lambda i: i in (0xED, 0xEE))
    for b in circus:
        print(
            f"  MIXED n={b['n']} {b['w']}x{b['h']} "
            f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']}) "
            f"ids={ {f'0x{k:02X}': n for k, n in b['idc'].items()} }"
        )
        dump_rect(city, b["xmin"] - 2, b["ymin"] - 3, b["xmax"] + 2, b["ymax"] + 2, "circus neighborhood")
        dump_rect_detail(city, b["xmin"] - 2, b["ymin"] - 3, b["xmax"] + 2, b["ymax"] + 2, "circus neighborhood")

    print("=== 3b. short-side neighbors ===")
    # 4x8 at x=71-74 y=25-32: short sides are the 4-wide edges at y=25 (north) and y=32 (south)
    # or if 8x4 then short sides at x edges.
    for b in circus:
        w, h = b["w"], b["h"]
        print(f"  footprint {w}x{h} (w=x span, h=y span)")
        if w < h:
            print("  short sides = y-min and y-max (constant-x 4-wide)")
            short_ys = [b["ymin"], b["ymax"]]
            for sy in short_ys:
                print(f"  -- along y={sy} x={b['xmin']-2}..{b['xmax']+2} --")
                for x in range(b["xmin"] - 2, b["xmax"] + 3):
                    if 0 <= x < MAP_W:
                        print("    " + fmt(city.tile(x, sy), x, sy))
                for ny in (sy - 1, sy + 1):
                    if 0 <= ny < MAP_H:
                        print(f"  -- adjacent row y={ny} --")
                        for x in range(b["xmin"] - 2, b["xmax"] + 3):
                            if 0 <= x < MAP_W:
                                t = city.tile(x, ny)
                                print("    " + fmt(t, x, ny))
        else:
            print("  short sides = x-min and x-max")

    print("=== 4. 3x3 same-id near (71,22) and all 0xAA-0xAC ===")
    dump_rect(city, 65, 10, 79, 28, "forum stack window")
    for b in sorted(blobs, key=lambda z: (z["ymin"], z["xmin"])):
        if b["id"] in (0xAA, 0xAB, 0xAC, 0xA6, 0xA7, 0xA8, 0xA2, 0xA3, 0xA4, 0xA5):
            print(
                f"  id=0x{b['id']:02X} n={b['n']} {b['w']}x{b['h']} "
                f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})"
            )

    print("=== 4b. 3x3 filled squares any civic ===")
    for b in blobs:
        if b["w"] == 3 and b["h"] == 3 and b["n"] == 9:
            print(
                f"  id=0x{b['id']:02X} origin=({b['xmin']},{b['ymin']}) "
                f"sheet={sn(city.tile(b['xmin'], b['ymin']).draw)}"
            )

    print("=== 4c. tile (71,22) and 5x5 around ===")
    dump_rect(city, 68, 18, 76, 26, "(71,22) neighborhood")
    dump_rect_detail(city, 68, 18, 76, 26, "(71,22) neighborhood")

    print("=== 5. 0xE8 blobs (Coliseum hyp) ===")
    for b in sorted(blobs, key=lambda z: (z["ymin"], z["xmin"])):
        if b["id"] == 0xE8:
            print(
                f"  id=0xE8 n={b['n']} {b['w']}x{b['h']} "
                f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})"
            )
    e8mix = any_id_blobs(ids, lambda i: i == 0xE8)
    for b in e8mix:
        dump_rect(city, max(0, b["xmin"] - 3), max(0, b["ymin"] - 3), min(79, b["xmax"] + 3), min(79, b["ymax"] + 3), "E8 neighborhood")

    print("=== 5b. 0xE5-0xF0 blobs near x>=65 y<=30 ===")
    for b in sorted(blobs, key=lambda z: (z["ymin"], z["xmin"])):
        if 0xE5 <= b["id"] <= 0xF0 and b["xmin"] >= 60 and b["ymin"] <= 35:
            print(
                f"  id=0x{b['id']:02X} n={b['n']} {b['w']}x{b['h']} "
                f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']}) "
                f"sheet={sn(city.tile(b['xmin'], b['ymin']).draw)}"
            )

    print("=== 5c. iso-above stack: decreasing y at x~71, then decreasing x ===")
    print("--- column x=68..76 y=0..32 (above circus toward north tip = smaller x+y) ---")
    dump_rect(city, 68, 0, 76, 32, "iso-north of circus")
    print("--- iso screen-top is smaller x+y; at x=71 circus y=25 -> above is y<25 ---")
    print("  (71,22) x+y=93; (71,25) x+y=96; smaller y = ABOVE on iso")
    print("  decreasing x at fixed y also decreases x+y (also above-left on iso)")

    print("=== 5d. all 3x3 and 0xE8 along decreasing-y from circus ===")
    dump_rect_detail(city, 68, 0, 76, 24, "above circus")

    print("=== 6. all 0xC0-0xCA map-wide counts ===")
    c_all = Counter()
    for y in range(MAP_H):
        for x in range(MAP_W):
            if 0xC0 <= ids[y][x] <= 0xCA:
                c_all[ids[y][x]] += 1
    print(" ", {f"0x{k:02X}": n for k, n in sorted(c_all.items())})

    print("=== 6b. 0x78-0x81 map-wide counts ===")
    c78 = Counter()
    for y in range(MAP_H):
        for x in range(MAP_W):
            if 0x78 <= ids[y][x] <= 0x81:
                c78[ids[y][x]] += 1
    print(" ", {f"0x{k:02X}": n for k, n in sorted(c78.items())})

    print("=== 6c. 0xC1 / 0x7C / 0x7D / 0x7E / 0x7F blobs touching y=1 ===")
    for want in (0x7C, 0x7D, 0x7E, 0x7F, 0x80, 0x81, 0xC0, 0xC1, 0xC2, 0xC3):
        hits = [b for b in blobs if b["id"] == want]
        if not hits:
            continue
        print(f"  --- 0x{want:02X} n_blobs={len(hits)} ---")
        for b in hits:
            print(
                f"    n={b['n']} {b['w']}x{b['h']} "
                f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})"
            )


if __name__ == "__main__":
    main()
