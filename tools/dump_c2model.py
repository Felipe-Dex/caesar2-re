#!/usr/bin/env python3
"""Dump C2MODEL.DAT as little-endian int32s and hunt known Caesar II tables.

File is 4360 bytes = 1090 x int32. No magic. Hypotheses are tagged against
community FAQ numbers (caesar2.com / Falanx), not against the EXE.
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter
from pathlib import Path

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")

# Sequences from the Falanx / caesar2.com FAQ (v1.0 numbers; this install is 1.1A).
KNOWN = {
    "difficulty_starting_money": [20000, 15000, 12000, 7000, 5000],
    "difficulty_promotions": [5, 7, 10, 15, 20],
    "rank_individual_pct": [20, 25, 30, 35, 40, 45, 50, 55, 60, 65],
    "rank_average_pct": [30, 35, 40, 45, 50, 55, 60, 65, 70, 74],
    "house_land_value": [
        0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30,
        32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 54, 54, 56, 58, 60, 64,
    ],
    "house_occupancy": [
        2, 4, 6, 8, 10, 12, 6, 7, 8, 9, 12, 16, 20, 24, 28, 32,
        36, 42, 48, 54, 20, 25, 30, 35, 40, 45, 100, 120, 150, 200, 300, 500,
    ],
    "city_building_costs": [
        20, 50, 15, 30, 300, 500, 700, 1000, 1500, 2500, 250, 500,
        20, 75, 5, 80, 200, 600, 3, 12, 100, 400, 1500, 100, 400, 40, 80, 500, 1000,
    ],
    "entertainment_costs": [300, 500, 700, 1000, 1500, 2500],
    "worship_costs": [80, 200, 600],
    "province_costs_reordered": [20, 50, 500, 100, 250, 1000, 150, 400, 500],
    "pop_unlocks": [400, 800, 1200, 1800, 2400, 4800],
    "worship_pop_shrine": [500, 2000, 5000],
    "lv_evolve_grades": [17, 33, 49],
    "business_lv_caps": [10, 16, 26],
}


def find_seq(values: list[int], needle: list[int]) -> list[int]:
    hits = []
    n = len(needle)
    if n == 0 or n > len(values):
        return hits
    for i in range(len(values) - n + 1):
        if values[i : i + n] == needle:
            hits.append(i)
    return hits


def find_all(values: list[int], x: int) -> list[int]:
    return [i for i, v in enumerate(values) if v == x]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump C2MODEL.DAT int32 tables.")
    parser.add_argument("--dat", type=Path, default=DEFAULT_GAME / "C2MODEL.DAT")
    parser.add_argument("--width", type=int, default=10, help="ints per dump row")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write index\\tvalue TSV (ok to commit; numbers only)",
    )
    args = parser.parse_args(argv)

    data = args.dat.read_bytes()
    if len(data) % 4 != 0:
        raise ValueError(f"{args.dat.name}: size {len(data)} not multiple of 4")
    values = list(struct.unpack(f"<{len(data) // 4}i", data))

    print("=== C2MODEL.DAT ===")
    print(f"file          : {args.dat}  ({len(data)} bytes, {len(values)} int32)")
    print(f"min/max       : {min(values)} / {max(values)}")
    print(f"zeros         : {values.count(0)}")
    print(f"negatives     : {sum(1 for v in values if v < 0)}")
    uniq = Counter(values)
    print(f"unique values : {len(uniq)}")
    print("most common   : " + ", ".join(f"{v}×{c}" for v, c in uniq.most_common(12)))

    print("-- known FAQ sequences --")
    for name, seq in KNOWN.items():
        hits = find_seq(values, seq)
        if hits:
            print(f"  HIT  {name:28s}  at index {hits}  (len {len(seq)})")
        else:
            # partial: first 5 of a long seq
            if len(seq) >= 5:
                sub = find_seq(values, seq[:5])
                if sub:
                    print(f"  PART {name:28s}  first5 at {sub}")
                    continue
            print(f"  miss {name}")

    print("-- dump --")
    w = max(1, args.width)
    for row in range(0, len(values), w):
        chunk = values[row : row + w]
        body = " ".join(f"{v:7d}" for v in chunk)
        print(f"  [{row:4d}] {body}")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write("index\tvalue\n")
            for i, v in enumerate(values):
                fh.write(f"{i}\t{v}\n")
        print(f"wrote         : {args.out}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        sys.exit(1)
