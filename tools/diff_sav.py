#!/usr/bin/env python3
"""Diff two Caesar II .SAV files (fixed 225745 bytes on this install).

Does not print the save bodies. Reports header fields, ASCII runs, and
coalesced changed ranges so we can map a struct without copying assets.
"""

from __future__ import annotations

import argparse
import math
import struct
import sys
from collections import Counter
from pathlib import Path

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
SAV_SIZE = 225745
HEADER_SIZE = 1745
PLANE_SIZE = 6400
N_PLANES = 35
MAP_W = 80


def u16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def i32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def ascii_runs(buf: bytes, min_len: int = 4) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    i = 0
    n = len(buf)
    while i < n:
        if 32 <= buf[i] < 127:
            j = i
            while j < n and 32 <= buf[j] < 127:
                j += 1
            if j - i >= min_len:
                out.append((i, buf[i:j].decode("ascii")))
            i = j
        else:
            i += 1
    return out


def coalesce_byte_diffs(a: bytes, b: bytes) -> list[tuple[int, int]]:
    """Inclusive-exclusive [start, end) ranges where a != b."""
    ranges: list[tuple[int, int]] = []
    start = None
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            if start is None:
                start = i
        elif start is not None:
            ranges.append((start, i))
            start = None
    if start is not None:
        ranges.append((start, len(a)))
    return ranges


def first_nonzero(buf: bytes, start: int = 0) -> int:
    for i in range(start, len(buf)):
        if buf[i] != 0:
            return i
    return -1


def dump_header(name: str, buf: bytes) -> None:
    print(f"-- {name} --")
    print(f"  size         : {len(buf)}")
    print(f"  hex[0:32]    : {buf[:32].hex()}")
    print(
        "  u16[0:16]    : "
        + " ".join(f"{u16(buf, i):5d}" for i in range(0, 16, 2))
    )
    print(
        "  u32[0:32]    : "
        + " ".join(f"{u32(buf, i):10d}" for i in range(0, 32, 4))
    )
    nz = first_nonzero(buf)
    print(f"  first nonzero: {nz}")
    # density in 4 KiB windows
    windows = []
    step = 4096
    for off in range(0, len(buf), step):
        chunk = buf[off : off + step]
        nzc = sum(1 for b in chunk if b)
        windows.append((off, nzc, len(chunk)))
    print("  nonzero/4KiB : " + ", ".join(
        f"{off:6d}:{nzc:4d}" for off, nzc, _ in windows if nzc
    ))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff Caesar II .SAV files.")
    parser.add_argument("--a", type=Path, default=DEFAULT_GAME / "FELIPE01.SAV")
    parser.add_argument("--b", type=Path, default=DEFAULT_GAME / "FELIPE02.SAV")
    parser.add_argument("--also", type=Path, default=DEFAULT_GAME / "LASTYEAR.SAV")
    parser.add_argument("--max-ranges", type=int, default=40)
    args = parser.parse_args(argv)

    files = [("A", args.a), ("B", args.b)]
    if args.also is not None and args.also.exists():
        files.append(("C", args.also))

    blobs: dict[str, bytes] = {}
    print("=== SAV ===")
    for tag, path in files:
        data = path.read_bytes()
        blobs[tag] = data
        print(f"{tag}             : {path.name}  {len(data)} bytes")
        if len(data) != SAV_SIZE:
            print(f"  WARNING: expected {SAV_SIZE} on this install")

    for tag, path in files:
        dump_header(path.name, blobs[tag])
        runs = ascii_runs(blobs[tag], min_len=5)
        print(f"  ascii runs   : {len(runs)}")
        for off, s in runs[:20]:
            print(f"    @{off:6d}  {s!r}")
        if len(runs) > 20:
            print(f"    ... {len(runs) - 20} more")

    a, b = blobs["A"], blobs["B"]
    if len(a) != len(b):
        print("A/B sizes differ; range diff skipped")
        return 0

    n_diff = sum(1 for x, y in zip(a, b) if x != y)
    print(f"\n=== A vs B byte diff ===")
    print(f"changed bytes : {n_diff} / {len(a)}  ({100.0 * n_diff / len(a):.2f}%)")
    ranges = coalesce_byte_diffs(a, b)
    print(f"changed ranges: {len(ranges)}")

    # length histogram of ranges
    lens = Counter(end - start for start, end in ranges)
    print("range lengths : " + ", ".join(
        f"{ln}B×{c}" for ln, c in lens.most_common(15)
    ))

    print("-- ranges --")
    for i, (start, end) in enumerate(ranges[: args.max_ranges]):
        n = end - start
        av = a[start:end]
        bv = b[start:end]
        note = ""
        if n == 2:
            note = f"  u16 {u16(a, start)} -> {u16(b, start)}"
        elif n == 4:
            note = (
                f"  u32 {u32(a, start)} -> {u32(b, start)}"
                f"  i32 {i32(a, start)} -> {i32(b, start)}"
            )
        elif n <= 16:
            note = f"  {av.hex()} -> {bv.hex()}"
        else:
            note = f"  a[:8]={av[:8].hex()} b[:8]={bv[:8].hex()}"
        print(f"  [{i:3d}] {start:6d}..{end:6d}  ({n:5d} B){note}")
    if len(ranges) > args.max_ranges:
        print(f"  ... {len(ranges) - args.max_ranges} more ranges")

    if len(ranges) >= 3:
        g = 0
        for start, _ in ranges:
            g = math.gcd(g, start)
        print(f"gcd(range starts) = {g}")

    # Plane-aware view of the 80x80 SoA tail.
    print("\n=== A vs B by 80x80 plane (header 1745 + 35×6400) ===")
    hdr_diff = sum(1 for x, y in zip(a[:HEADER_SIZE], b[:HEADER_SIZE]) if x != y)
    print(f"header 0..{HEADER_SIZE} changed bytes: {hdr_diff}")
    print(f"{'p':>3} {'off':>7} {'ndiff':>6} {'pct':>7}  bbox of changed cells")
    for i in range(N_PLANES):
        off = HEADER_SIZE + i * PLANE_SIZE
        pa, pb = a[off : off + PLANE_SIZE], b[off : off + PLANE_SIZE]
        nd = sum(1 for x, y in zip(pa, pb) if x != y)
        xs = [k % MAP_W for k, (x, y) in enumerate(zip(pa, pb)) if x != y]
        ys = [k // MAP_W for k, (x, y) in enumerate(zip(pa, pb)) if x != y]
        if xs:
            bbox = f"({min(xs)},{min(ys)})-({max(xs)},{max(ys)})"
        else:
            bbox = "(none)"
        print(f"{i:3d} {off:7d} {nd:6d} {100.0 * nd / PLANE_SIZE:6.2f}%  {bbox}")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        sys.exit(1)
