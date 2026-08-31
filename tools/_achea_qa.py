#!/usr/bin/env python3
"""One-shot ACHEA23 river + corner dump. Does not copy the SAV."""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from app.city_map import (  # noqa: E402
    FLAG_RIVER,
    ID_TERRAIN_MAX,
    ISO_HALF_H,
    ISO_HALF_W,
    MAP_H,
    MAP_W,
    load_city_from_sav,
    render_iso,
)

SAV = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV")
OUT = ROOT / "sav_preview" / "Achea_river.png"

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


def blobs_of(ids: list[list[int]], draws: list[list[int]]) -> list[dict]:
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
                    "sheet": sn(draws[cells[0][1]][cells[0][0]]),
                }
            )
    return out


def print_group(title: str, hits: list[dict], limit: int = 40) -> None:
    tiles = sum(b["n"] for b in hits)
    print(f"=== {title} blobs={len(hits)} tiles={tiles} ===")
    for b in sorted(hits, key=lambda z: (z["ymin"], z["xmin"]))[:limit]:
        print(
            f"  id=0x{b['id']:02X} n={b['n']:3d} {b['w']}x{b['h']} "
            f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']}) {b['sheet']}"
        )


def paint_river(city, rivers: list[tuple[int, int]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    full = ROOT / "sav_preview" / "Achea_iso_full.png"
    if full.is_file():
        img = Image.open(full).convert("RGBA")
    else:
        img = render_iso(city)
    origin_x = (MAP_W - 1) * ISO_HALF_W
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for x, y in rivers:
        sx = origin_x + (x - y) * ISO_HALF_W
        sy = (x + y) * ISO_HALF_H
        draw.polygon(
            [
                (sx + ISO_HALF_W, sy),
                (sx + ISO_HALF_W * 2 - 1, sy + ISO_HALF_H),
                (sx + ISO_HALF_W, sy + ISO_HALF_H * 2 - 1),
                (sx, sy + ISO_HALF_H),
            ],
            fill=(40, 140, 230, 160),
        )
    out = Image.alpha_composite(img, overlay)
    out.save(OUT)
    print(f"wrote {OUT} {out.size[0]}x{out.size[1]} rivers={len(rivers)}")


def main() -> None:
    city = load_city_from_sav(SAV)
    ids = [[city.tile(x, y).terrain_id for x in range(MAP_W)] for y in range(MAP_H)]
    draws = [[city.tile(x, y).draw for x in range(MAP_W)] for y in range(MAP_H)]

    rivers: list[tuple[int, int]] = []
    id_on_river: Counter[int] = Counter()
    for y in range(MAP_H):
        for x in range(MAP_W):
            t = city.tile(x, y)
            if t.flags & FLAG_RIVER:
                rivers.append((x, y))
                id_on_river[t.terrain_id] += 1
    xs = [p[0] for p in rivers]
    ys = [p[1] for p in rivers]
    print(
        f"RIVER n={len(rivers)} bbox x={min(xs)}..{max(xs)} y={min(ys)}..{max(ys)} "
        f"id<8={sum(1 for row in ids for v in row if v < 8)}"
    )
    print("RIVER +0 top", id_on_river.most_common(8))
    print("RIVER rows-with-flag", len(set(ys)), "cols-with-flag", len(set(xs)))

    blobs = blobs_of(ids, draws)

    groups = [
        ("wall 7C-81", lambda b: 0x7C <= b["id"] <= 0x81),
        ("plaza 78-7B", lambda b: 0x78 <= b["id"] <= 0x7B),
        ("BF", lambda b: b["id"] == 0xBF),
        ("C0", lambda b: b["id"] == 0xC0),
        ("C1", lambda b: b["id"] == 0xC1),
        ("E3", lambda b: b["id"] == 0xE3),
        ("E8", lambda b: b["id"] == 0xE8),
        ("E9", lambda b: b["id"] == 0xE9),
        ("ED", lambda b: b["id"] == 0xED),
        ("EE", lambda b: b["id"] == 0xEE),
        ("E5-E7", lambda b: b["id"] in (0xE5, 0xE6, 0xE7)),
        ("EA-EC", lambda b: b["id"] in (0xEA, 0xEB, 0xEC)),
    ]
    for title, pred in groups:
        print_group(title, [b for b in blobs if pred(b)])

    skip = set(range(0x82, 0xA2)) | {0xFA, 0xFB, 0xF5, 0xC1, 0xC2, 0x7C}
    print("=== large/elongated n>=8 not housing/FA/FB/F5/C1/C2/7C ===")
    for b in sorted(blobs, key=lambda z: -z["n"]):
        if b["n"] < 8 or b["id"] in skip:
            continue
        aspect = max(b["w"], b["h"]) / max(1, min(b["w"], b["h"]))
        print(
            f"  id=0x{b['id']:02X} n={b['n']:3d} {b['w']}x{b['h']} asp={aspect:.1f} "
            f"bbox=({b['xmin']},{b['ymin']})-({b['xmax']},{b['ymax']}) {b['sheet']}"
        )

    print("=== neighborhood y0-8 x70-79 ===")
    for y in range(9):
        row = []
        for x in range(70, 80):
            tid = ids[y][x]
            row.append(".." if tid < 0x78 else f"{tid:02X}")
        print(f"y={y:02d}", " ".join(row))

    print("=== neighborhood y0-4 x50-79 ===")
    for y in range(5):
        row = []
        for x in range(50, 80):
            tid = ids[y][x]
            row.append(".." if tid < 0x78 else f"{tid:02X}")
        print(f"y={y:02d}", " ".join(row))

    print("=== x=78 occupied ===")
    for y in range(MAP_H):
        if ids[y][78] >= 0x78:
            t = city.tile(78, y)
            print(
                f"  (78,{y:2d}) id=0x{t.terrain_id:02X} {sn(t.draw)} "
                f"+3=0x{t.draw:02X} +1=0x{t.flags:02X} +4=0x{t.variant:02X}"
            )

    print("=== all 0x7C-0x81 ===")
    for y in range(MAP_H):
        for x in range(MAP_W):
            if 0x7C <= ids[y][x] <= 0x81:
                t = city.tile(x, y)
                print(
                    f"  ({x:2d},{y:2d}) id=0x{t.terrain_id:02X} {sn(t.draw)} "
                    f"+3=0x{t.draw:02X} +4=0x{t.variant:02X}"
                )

    # isolated 1x1 near visual NE (high x, low y)
    print("=== 1x1 blobs with xmin>=50 and ymin<=15 ===")
    for b in sorted(blobs, key=lambda z: (z["ymin"], -z["xmin"])):
        if b["n"] == 1 and b["xmin"] >= 50 and b["ymin"] <= 15:
            x, y = b["cells"][0]
            t = city.tile(x, y)
            print(
                f"  ({x:2d},{y:2d}) id=0x{t.terrain_id:02X} {sn(t.draw)} "
                f"+3=0x{t.draw:02X} +1=0x{t.flags:02X} +4=0x{t.variant:02X}"
            )

    paint_river(city, rivers)


if __name__ == "__main__":
    main()
