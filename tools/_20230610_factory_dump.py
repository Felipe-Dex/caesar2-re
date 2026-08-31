#!/usr/bin/env python3
"""Dump 20230610.SAV D1–D8 unknowns + factory tiles. Does not copy the SAV."""

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
    load_city_from_sav,
)
from _20230610_parse import ACHEA_NAMED, same_id_blobs  # noqa: E402

SAV = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2\20230610.SAV")

USER_FACTORIES = [
    ("Ivory Dealer T66/(18,64)", 18, 64),
    ("Bakery (75,28)", 75, 28),
    ("Stone Works (75,36)", 75, 36),
    ("Butcher (71,36)", 71, 36),
    ("Winery OK (68,41)", 68, 41),
    ("Bakery (68,46)", 68, 46),
    ("Bakery (68,48)", 68, 48),
    ("Bakery (57,51)", 57, 51),
    ("Winery OK (53,51)", 53, 51),
    ("Winery OK (49,51)", 49, 51),
]


def footprint_of(ids, x: int, y: int) -> dict:
    tid = ids[y][x]
    seen = {(x, y)}
    stack = [(x, y)]
    cells = []
    while stack:
        cx, cy = stack.pop()
        cells.append((cx, cy))
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if (
                0 <= nx < MAP_W
                and 0 <= ny < MAP_H
                and (nx, ny) not in seen
                and ids[ny][nx] == tid
            ):
                seen.add((nx, ny))
                stack.append((nx, ny))
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    return {
        "n": len(cells),
        "xmin": min(xs),
        "xmax": max(xs),
        "ymin": min(ys),
        "ymax": max(ys),
        "w": max(xs) - min(xs) + 1,
        "h": max(ys) - min(ys) + 1,
        "cells": cells,
    }


def dump_xy(city, ids, label: str, x: int, y: int) -> None:
    if not (0 <= x < MAP_W and 0 <= y < MAP_H):
        print(f"  {label}  ({x},{y})  OOB")
        return
    t = city.tile(x, y)
    raw = t.raw
    fp = footprint_of(ids, x, y) if t.terrain_id >= ID_TERRAIN_MAX else None
    fp_s = (
        f"{fp['w']}x{fp['h']} n={fp['n']} "
        f"({fp['xmin']},{fp['ymin']})-({fp['xmax']},{fp['ymax']})"
        if fp
        else "terrain"
    )
    print(
        f"  {label:28s}  ({x:2d},{y:2d})  id=0x{t.terrain_id:02X}  "
        f"+4=0x{t.variant:02X}  +5=0x{t.spawn_packed:02X}  "
        f"+9=0x{t.overlay_anim:02X}  +19=0x{t.special:02X} "
        f"(lo={t.special & 0xF})  fp={fp_s}"
    )
    print(f"       raw={' '.join(f'{b:02X}' for b in raw)}")


def main() -> None:
    city = load_city_from_sav(SAV)
    tiles = [[city.tile(x, y) for x in range(MAP_W)] for y in range(MAP_H)]
    ids = [[t.terrain_id for t in row] for row in tiles]
    specials = [[t.special for t in row] for row in tiles]
    blobs = same_id_blobs(ids)

    unnamed = [b for b in blobs if b["id"] not in ACHEA_NAMED]
    unnamed.sort(key=lambda b: (b["ymin"], b["xmin"], b["id"]))
    print("=== Desconhecido N (ids not in ACHEA_NAMED) ===")
    for n, b in enumerate(unnamed, start=1):
        x, y = b["xmin"], b["ymin"]
        t = tiles[y][x]
        print(
            f"  D{n}  id=0x{b['id']:02X}  {b['w']}x{b['h']} n={b['n']}  "
            f"({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
            f"+4=0x{t.variant:02X}  +19=0x{t.special:02X}"
        )

    print("\n=== USER FACTORY COORDS (map x,y and swapped y,x) ===")
    for label, x, y in USER_FACTORIES:
        dump_xy(city, ids, label, x, y)
        if (x, y) != (y, x):
            dump_xy(city, ids, f"  swapped ({y},{x})", y, x)

    print("\n=== ALL 0xFA BLOBS ===")
    fa = [b for b in blobs if b["id"] == 0xFA]
    fa.sort(key=lambda b: (b["ymin"], b["xmin"]))
    nib_hist: Counter[int] = Counter()
    plus4_hist: Counter[int] = Counter()
    for i, b in enumerate(fa, start=1):
        nibs = Counter()
        plus4 = Counter()
        plus5 = Counter()
        origin = None
        for cx, cy in b["cells"]:
            t = tiles[cy][cx]
            nibs[t.special & 0xF] += 1
            plus4[t.variant] += 1
            plus5[t.spawn_packed] += 1
            if (t.spawn_packed & 0xF) == 0:
                origin = (cx, cy, t)
        nib_hist.update({k: 1 for k in nibs})
        plus4_hist.update(plus4)
        ox, oy = (origin[0], origin[1]) if origin else (b["xmin"], b["ymin"])
        ot = origin[2] if origin else tiles[oy][ox]
        print(
            f"  FA{i:02d}  ({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
            f"{b['w']}x{b['h']} n={b['n']}  origin=({ox},{oy})  "
            f"+4=0x{ot.variant:02X}  +5=0x{ot.spawn_packed:02X}  "
            f"+19=0x{ot.special:02X} lo={ot.special & 0xF}  "
            f"nibs={dict(nibs)}  +4s={ {hex(k): v for k, v in plus4.items()} }"
        )

    print("\n=== 0xFA +19 lo-nibble histogram (blob-level, origin tile) ===")
    origin_nibs: Counter[int] = Counter()
    for b in fa:
        for cx, cy in b["cells"]:
            t = tiles[cy][cx]
            if (t.spawn_packed & 0xF) == 0:
                origin_nibs[t.special & 0xF] += 1
                break
        else:
            origin_nibs[specials[b["ymin"]][b["xmin"]] & 0xF] += 1
    for k, n in sorted(origin_nibs.items()):
        print(f"  +19 lo={k:2d} (0x{k:X})  blobs={n}")

    print("\n=== 0xCB tiles (D1 aqueduct stub) ===")
    for y in range(MAP_H):
        for x in range(MAP_W):
            if ids[y][x] == 0xCB:
                t = tiles[y][x]
                print(
                    f"  (x={x},y={y})  +1=0x{t.flags:02X}  +3=0x{t.draw:02X}  "
                    f"+4=0x{t.variant:02X}  +19=0x{t.special:02X}  "
                    f"neighbors="
                    + ",".join(
                        f"({nx},{ny})=0x{ids[ny][nx]:02X}"
                        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                        for nx, ny in ((x + dx, y + dy),)
                        if 0 <= nx < MAP_W and 0 <= ny < MAP_H
                    )
                )

    print("\n=== ALL 0xFA ORIGIN TILES (+5 lo-nibble == 0) ===")
    for y in range(MAP_H):
        for x in range(MAP_W):
            t = tiles[y][x]
            if t.terrain_id != 0xFA:
                continue
            if (t.spawn_packed & 0xF) != 0:
                continue
            print(
                f"  origin ({x:2d},{y:2d})  +4=0x{t.variant:02X}  +5=0x{t.spawn_packed:02X}  "
                f"+9=0x{t.overlay_anim:02X}  +19=0x{t.special:02X} lo={t.special & 0xF}"
            )

    print("\n=== FA06 9x3 every tile (41,67)-(49,69) ===")
    for y in range(67, 70):
        for x in range(41, 50):
            t = tiles[y][x]
            print(
                f"  ({x},{y}) id=0x{t.terrain_id:02X} +4=0x{t.variant:02X} "
                f"+5=0x{t.spawn_packed:02X} +19=0x{t.special:02X} lo={t.special & 0xF}"
            )

    print("\n=== 3x3 around each mapped factory (user y,x -> map x,y) ===")
    mapped = [
        ("Ivory", 18, 64),
        ("Bakery", 28, 75),
        ("Stone", 36, 75),
        ("Butcher", 36, 71),
        ("Winery68/41", 41, 68),
        ("Bakery68/46", 46, 68),
        ("Bakery68/48", 48, 68),
        ("Bakery57/51", 51, 57),
        ("Winery53/51", 51, 53),
        ("Winery49/51", 51, 49),
    ]
    for label, cx, cy in mapped:
        print(f"  -- {label} click ({cx},{cy}) --")
        for y in range(max(0, cy - 1), min(MAP_H, cy + 2)):
            for x in range(max(0, cx - 1), min(MAP_W, cx + 2)):
                t = tiles[y][x]
                mark = "*" if (x, y) == (cx, cy) else " "
                print(
                    f"   {mark}({x:2d},{y:2d}) 0x{t.terrain_id:02X} "
                    f"+4={t.variant:02X} +5={t.spawn_packed:02X} +19={t.special:02X}"
                )

    print("\n=== Baths 0xDF–0xE2 blobs ===")
    for tid in range(0xDF, 0xE3):
        id_blobs = [b for b in blobs if b["id"] == tid]
        print(f"  0x{tid:02X}  n={sum(b['n'] for b in id_blobs)}  blobs={len(id_blobs)}")
        for b in sorted(id_blobs, key=lambda z: (z["ymin"], z["xmin"])):
            t = tiles[b["ymin"]][b["xmin"]]
            print(
                f"       ({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
                f"{b['w']}x{b['h']}  +4=0x{t.variant:02X}"
            )

    print("\n=== Temple 0xA6–0xA9 / Palatine 0xB6–0xB9 / Market 0xFC–0xFF ===")
    for tid in list(range(0xA6, 0xAA)) + list(range(0xB6, 0xBA)) + list(range(0xFC, 0x100)):
        cells = [(x, y) for y in range(MAP_H) for x in range(MAP_W) if ids[y][x] == tid]
        print(f"  0x{tid:02X}  n={len(cells)}")


if __name__ == "__main__":
    main()
