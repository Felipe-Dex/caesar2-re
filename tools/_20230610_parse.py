#!/usr/bin/env python3
"""Parse 20230610.SAV chunk 13: Basilica 3 / Palatine 4 + unnamed ids.

Does not copy the SAV. Writes findings/20230610_grid.xlsx only if >4 unnamed ids.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.city_map import (  # noqa: E402
    FLAG_PAD,
    FLAG_RIVER,
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

SAV = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2\20230610.SAV")
OUT_XLSX = ROOT / "findings" / "20230610_grid.xlsx"

SHEET_NAME = {
    SHEET_HOUSES1: "HOUSES1",
    SHEET_BUILD1A: "BUILD1A",
    SHEET_BUILD1B: "BUILD1B",
    SHEET_BUILD1C: "BUILD1C",
    SHEET_BUILD1D: "BUILD1D",
    SHEET_CITYFIXT_BLD: "CITYFIXT",
}

# Achea named set (achea.md §10–§11 + build_palette.md). Housing range counts.
ACHEA_NAMED: dict[int, str] = {}
for _i in range(0x78, 0x7C):
    ACHEA_NAMED[_i] = "Garden"
ACHEA_NAMED[0x7C] = "Plaza 1"
ACHEA_NAMED[0x7D] = "Plaza"
ACHEA_NAMED[0x7E] = "Plaza est"
ACHEA_NAMED[0x82] = "Tent"
for _i in range(0x83, 0xA2):
    ACHEA_NAMED[_i] = "Casa"
ACHEA_NAMED[0xA2] = "Shrine 1"
ACHEA_NAMED[0xA3] = "Shrine 2"
ACHEA_NAMED[0xA4] = "Shrine 3"
ACHEA_NAMED[0xA5] = "Shrine 4"
ACHEA_NAMED[0xA6] = "Temple 1"
ACHEA_NAMED[0xA7] = "Temple 2"
ACHEA_NAMED[0xA8] = "Temple 3"
ACHEA_NAMED[0xAB] = "Basilica 2"
ACHEA_NAMED[0xAC] = "Basilica 4"
ACHEA_NAMED[0xAE] = "Aventine 1"
ACHEA_NAMED[0xAF] = "Aventine 2"
ACHEA_NAMED[0xB0] = "Aventine 3"
ACHEA_NAMED[0xB2] = "Janiculan 1"
ACHEA_NAMED[0xB3] = "Janiculan 2"
ACHEA_NAMED[0xB4] = "Janiculan 4"
ACHEA_NAMED[0xB7] = "Palatine 2"
ACHEA_NAMED[0xB9] = "Palatine 4"
ACHEA_NAMED[0xBE] = "Reservatorio"
ACHEA_NAMED[0xBF] = "Tower"
ACHEA_NAMED[0xC0] = "Gate"
ACHEA_NAMED[0xC1] = "Wall N-S?"
ACHEA_NAMED[0xC2] = "Wall"
ACHEA_NAMED[0xCB] = "Aqueduto ponta"
for _i in range(0xCF, 0xD7):
    ACHEA_NAMED[_i] = "Aqueduto"
ACHEA_NAMED[0xD7] = "Well"
ACHEA_NAMED[0xDC] = "Fountain 2"
ACHEA_NAMED[0xDD] = "Fountain 1"
ACHEA_NAMED[0xDE] = "Fountain 4"
ACHEA_NAMED[0xDF] = "Baths 1"
ACHEA_NAMED[0xE0] = "Baths"
ACHEA_NAMED[0xE1] = "Baths 3"
ACHEA_NAMED[0xE2] = "Baths 4"
ACHEA_NAMED[0xE3] = "Praefecture"
ACHEA_NAMED[0xE4] = "Barracks"
ACHEA_NAMED[0xE5] = "Theater"
ACHEA_NAMED[0xE6] = "Odeum"
ACHEA_NAMED[0xE8] = "Colosseum"
ACHEA_NAMED[0xE9] = "Circus"
ACHEA_NAMED[0xEA] = "Circus"
ACHEA_NAMED[0xEB] = "Circus"
ACHEA_NAMED[0xEC] = "Circus"
ACHEA_NAMED[0xED] = "C.Maximus"
ACHEA_NAMED[0xEE] = "C.Maximus"
ACHEA_NAMED[0xF3] = "Grammaticus"
ACHEA_NAMED[0xF4] = "Rhetor"
ACHEA_NAMED[0xF5] = "Library"
ACHEA_NAMED[0xFA] = "Factory"
ACHEA_NAMED[0xFB] = "Hospital"
ACHEA_NAMED[0xFC] = "Market 1"
ACHEA_NAMED[0xFD] = "Market 2"
ACHEA_NAMED[0xFE] = "Market 3"
ACHEA_NAMED[0xFF] = "Market 4"


def advisor_type(tid: int) -> int | None:
    if tid < 0x78:
        return None
    if 0x78 <= tid <= 0x7B:
        return 1
    if 0x7C <= tid <= 0x81:
        return 0x0E
    if 0x82 <= tid <= 0xA1:
        return None
    if 0xA2 <= tid <= 0xAD:
        return 0x12
    if 0xAE <= tid <= 0xBB:
        return 7
    if 0xBC <= tid <= 0xBD:
        return 0x11
    if tid == 0xBE:
        return 0x10
    if 0xCB <= tid <= 0xD6:
        return 0x11
    if 0xD7 <= tid <= 0xDA:
        return 0x0F
    if 0xE5 <= tid <= 0xE6:
        return 0x13
    if 0xE7 <= tid <= 0xE8:
        return 5
    if 0xE9 <= tid <= 0xF2:
        return 2
    return None


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
                    if (
                        0 <= nx < MAP_W
                        and 0 <= ny < MAP_H
                        and not seen[ny][nx]
                        and ids[ny][nx] == tid
                    ):
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


def sheet_of(tiles, x: int, y: int) -> int:
    return tiles[y][x].draw & 0x1C


def main() -> None:
    if not SAV.is_file():
        raise SystemExit(f"missing {SAV}")
    print(f"=== SAV {SAV}  {SAV.stat().st_size} B ===")
    city = load_city_from_sav(SAV)
    tiles = [[city.tile(x, y) for x in range(MAP_W)] for y in range(MAP_H)]
    ids = [[t.terrain_id for t in row] for row in tiles]
    hist = Counter(tid for row in ids for tid in row if tid >= ID_TERRAIN_MAX)
    blobs = same_id_blobs(ids)

    print(f"\n=== HISTOGRAM id>=0x78  unique={len(hist)}  tiles={sum(hist.values())} ===")
    for tid, n in hist.most_common():
        name = ACHEA_NAMED.get(tid, "???")
        print(f"  0x{tid:02X}  n={n:4d}  {name}")

    print("\n=== 3x3 BLOBS (w=h=3, n=9) ===")
    three = [b for b in blobs if b["w"] == 3 and b["h"] == 3 and b["n"] == 9]
    three.sort(key=lambda b: (b["id"], b["ymin"], b["xmin"]))
    for b in three:
        x, y = b["xmin"], b["ymin"]
        sh = SHEET_NAME.get(sheet_of(tiles, x, y), f"+3={tiles[y][x].draw:#x}")
        at = advisor_type(b["id"])
        name = ACHEA_NAMED.get(b["id"], "UNNAMED")
        print(
            f"  id=0x{b['id']:02X}  bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
            f"sheet={sh}  type={at}  {name}  +4={tiles[y][x].variant:#x}"
        )

    print("\n=== 3x3 NOT 0xAB/0xAC (Basilica-3 candidates) ===")
    cand3 = [b for b in three if b["id"] not in (0xAB, 0xAC)]
    for b in cand3:
        x, y = b["xmin"], b["ymin"]
        sh = SHEET_NAME.get(sheet_of(tiles, x, y), "?")
        at = advisor_type(b["id"])
        print(
            f"  id=0x{b['id']:02X}  ({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
            f"{sh} type={at}  named={ACHEA_NAMED.get(b['id'], 'NO')}"
        )

    print("\n=== ALL 0xAA–0xAD tiles ===")
    for tid in range(0xAA, 0xAE):
        cells = [(x, y) for y in range(MAP_H) for x in range(MAP_W) if ids[y][x] == tid]
        print(f"  0x{tid:02X}  n={len(cells)}")

    print("\n=== 4x4 BLOBS (w=h=4, n=16) type-7 / Palatine family ===")
    four = [b for b in blobs if b["w"] == 4 and b["h"] == 4 and b["n"] == 16]
    four.sort(key=lambda b: (b["id"], b["ymin"], b["xmin"]))
    for b in four:
        x, y = b["xmin"], b["ymin"]
        sh = SHEET_NAME.get(sheet_of(tiles, x, y), "?")
        at = advisor_type(b["id"])
        name = ACHEA_NAMED.get(b["id"], "UNNAMED")
        print(
            f"  id=0x{b['id']:02X}  bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
            f"sheet={sh}  type={at}  {name}  +4={tiles[y][x].variant:#x}"
        )

    print("\n=== Palatine family 0xB6–0xB9 ===")
    for tid in range(0xB6, 0xBA):
        cells = [(x, y) for y in range(MAP_H) for x in range(MAP_W) if ids[y][x] == tid]
        print(f"  0x{tid:02X}  n={len(cells)}  named={ACHEA_NAMED.get(tid, 'NO')}")
        if cells:
            xs = [c[0] for c in cells]
            ys = [c[1] for c in cells]
            print(
                f"       bbox=({min(xs)},{min(ys)})-({max(xs)},{max(ys)})  "
                f"span {max(xs)-min(xs)+1}x{max(ys)-min(ys)+1}"
            )

    print("\n=== type-7 (0xAE–0xBB) present ===")
    for tid in range(0xAE, 0xBC):
        if tid not in hist:
            continue
        print(
            f"  0x{tid:02X}  n={hist[tid]:4d}  {ACHEA_NAMED.get(tid, 'UNNAMED')}  "
            f"type={advisor_type(tid)}"
        )

    print("\n=== worship 0xA2–0xAD present ===")
    for tid in range(0xA2, 0xAE):
        if tid not in hist:
            continue
        print(
            f"  0x{tid:02X}  n={hist[tid]:4d}  {ACHEA_NAMED.get(tid, 'UNNAMED')}  "
            f"type={advisor_type(tid)}"
        )

    unnamed_ids = sorted(tid for tid in hist if tid not in ACHEA_NAMED)
    print(f"\n=== UNNAMED IDS (not in Achea named set)  count={len(unnamed_ids)} ===")
    for tid in unnamed_ids:
        id_blobs = [b for b in blobs if b["id"] == tid]
        sheets = Counter(
            SHEET_NAME.get(sheet_of(tiles, b["xmin"], b["ymin"]), "?") for b in id_blobs
        )
        sizes = Counter(f"{b['w']}x{b['h']}n{b['n']}" for b in id_blobs)
        at = advisor_type(tid)
        print(
            f"  0x{tid:02X}  tiles={hist[tid]:4d}  blobs={len(id_blobs)}  "
            f"type={at}  sheets={dict(sheets)}  sizes={dict(sizes)}"
        )
        for b in sorted(id_blobs, key=lambda z: (z["ymin"], z["xmin"]))[:12]:
            print(
                f"       bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']})  "
                f"{b['w']}x{b['h']} n={b['n']}"
            )
        if len(id_blobs) > 12:
            print(f"       ... +{len(id_blobs) - 12} more blobs")

    print("\n=== GAP HITS (missing Achea stages if present) ===")
    gaps = {
        0xA7: "Temple 2?",
        0xA9: "Temple 4?",
        0xAA: "Basilica 1?",
        0xAD: "worship leftover?",
        0xB1: "Aventine 4?",
        0xB5: "Janiculan 3?",
        0xB6: "Palatine 1?",
        0xB8: "Palatine 3?",
        0xB9: "Palatine 4?",
        0xBC: "type-11 leftover?",
        0xBD: "type-11 leftover?",
        0xD7: "Well",
        0xD8: "Well 2?",
        0xD9: "Well 3?",
        0xDA: "Well 4?",
        0xDB: "Fountain 3?",
        0xCB: "Aqueduto ponta",
        0xCC: "Aqueduto ponta?",
        0xCD: "Aqueduto ponta?",
        0xCE: "Aqueduto ponta?",
        0xE1: "Baths 3?",
        0xE5: "Theater",
        0xE7: "Arena?",
        0xEF: "ent leftover?",
        0xF0: "ent leftover?",
        0xF1: "type-2 leftover?",
        0xF2: "type-2 leftover?",
        0xFC: "Market 1?",
        0x7F: "Plaza leftover?",
        0x80: "Plaza leftover?",
        0x81: "Plaza leftover?",
    }
    for tid, hyp in gaps.items():
        if tid in hist:
            print(f"  HIT  0x{tid:02X}  n={hist[tid]}  hyp={hyp}")
        else:
            print(f"  miss 0x{tid:02X}  {hyp}")

    print(f"\n=== DECISION unnamed_ids={len(unnamed_ids)}  xlsx={'YES' if len(unnamed_ids) > 4 else 'NO'} ===")
    return unnamed_ids, hist, blobs, tiles, ids


if __name__ == "__main__":
    main()
