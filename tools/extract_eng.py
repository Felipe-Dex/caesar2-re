#!/usr/bin/env python3
"""Extract Caesar II C2.ENG (and optionally HELP.ENG) string tables.

C2.ENG layout measured on this 1.1A install (little-endian):

    0x00  8 bytes  magic "Textfile"
    0x08  u32      0 (unused / flags; not an offset)
    0x0C  u32[]    absolute offsets into this file
                   n = (offsets[0] - 12) / 4
                   duplicates are allowed (shared strings)

Each offset points at a NUL-terminated C string (Latin-1 / CP437-ish).
Do not commit the full dump — the strings are original game text.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path


MAGIC_TEXT = b"Textfile"
MAGIC_HELP = b"Helpfile"
DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def cstring(buf: bytes, off: int) -> bytes:
    end = buf.find(b"\x00", off)
    if end < 0:
        raise ValueError(f"unterminated string at {off}")
    return buf[off:end]


def parse_textfile(data: bytes) -> tuple[list[int], list[str], int, int]:
    if not data.startswith(MAGIC_TEXT):
        raise ValueError(f"magic is {data[:8]!r}, expected {MAGIC_TEXT!r}")
    if len(data) < 16:
        raise ValueError(f"file too small ({len(data)})")
    pad = u32(data, 8)
    first = u32(data, 12)
    if first < 16 or first >= len(data):
        raise ValueError(f"first string offset {first} out of range")
    if (first - 12) % 4 != 0:
        raise ValueError(f"offset table length {first - 12} not a multiple of 4")

    n = (first - 12) // 4
    offsets = [u32(data, 12 + 4 * i) for i in range(n)]
    if offsets[0] != first:
        raise ValueError(f"offsets[0]={offsets[0]} != first={first}")
    unique = len(set(offsets))
    for i, off in enumerate(offsets):
        if off < first or off >= len(data):
            raise ValueError(
                f"offsets[{i}]={off} outside string pool [{first}, {len(data)})"
            )

    strings = [cstring(data, off).decode("latin-1") for off in offsets]
    return offsets, strings, pad, unique


def peek_helpfile(data: bytes) -> None:
    """HELP.ENG is a sibling, not the same table. Report header only."""
    print(f"magic         : {data[:8]!r}")
    print(f"size          : {len(data)}")
    zeros = 0
    for b in data[8:]:
        if b != 0:
            break
        zeros += 1
    print(f"zeros after magic: {zeros}  (first non-zero at {8 + zeros})")
    if 8 + zeros + 4 <= len(data):
        print(f"u32 at first non-zero: {u32(data, 8 + zeros)}  "
              f"hex={data[8 + zeros:8 + zeros + 16].hex()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract C2.ENG string table.")
    parser.add_argument("--eng", type=Path, default=DEFAULT_GAME / "C2.ENG")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write index\\toffset\\tstring TSV (local only)",
    )
    parser.add_argument("--limit", type=int, default=12, help="preview first N")
    parser.add_argument("--helpfile", type=Path, default=None)
    args = parser.parse_args(argv)

    data = args.eng.read_bytes()
    print("=== C2.ENG ===")
    print(f"file          : {args.eng}  ({len(data)} bytes)")
    offsets, strings, pad, unique = parse_textfile(data)
    print(f"pad u32@0x08  : {pad}")
    print(f"n_strings     : {len(strings)}  (unique offsets {unique})")
    print(f"pool start    : {offsets[0]}  (= 12 + 4*n)")
    print(f"last offset   : {max(offsets)}  (table slot {len(offsets)-1} -> {offsets[-1]})")
    ends = [
        off + len(s.encode("latin-1")) + 1 for off, s in zip(offsets, strings)
    ]
    print(f"pool end      : {max(ends)}  slack={len(data) - max(ends)}")
    empty = sum(1 for s in strings if not s)
    print(f"empty strings : {empty}")
    longest = max(range(len(strings)), key=lambda i: len(strings[i]))
    print(f"longest       : [{longest}] {len(strings[longest])} chars")

    print("-- preview --")
    for i, s in enumerate(strings[: args.limit]):
        shown = s.replace("\r", "\\r").replace("\n", "\\n")
        if len(shown) > 80:
            shown = shown[:77] + "..."
        print(f"  [{i:3d}] @{offsets[i]:5d}  {shown}")

    needles = (
        "Options",
        "Citizen",
        "Decurion",
        "Consul",
        "Reservoir",
        "Aventine",
        "Janiculan",
        "Palatine",
        "Caesar II - Version",
        "Latium",
        "Prima Cohors",
        "Denarii",
        "Novice",
        "Impossible",
        "Fountain",
        "Well",
        "Theater",
        "Circus Maximus",
    )
    print("-- find --")
    for needle in needles:
        hits = [i for i, s in enumerate(strings) if needle.lower() in s.lower()]
        if not hits:
            print(f"  {needle!r}: (none)")
            continue
        for i in hits[:5]:
            shown = strings[i].replace("\r", "\\r").replace("\n", "\\n")
            if len(shown) > 70:
                shown = shown[:67] + "..."
            print(f"  {needle!r} -> [{i}] {shown}")

    print("-- short labels (len<=28) --")
    for i, s in enumerate(strings):
        if 0 < len(s) <= 28 and "\n" not in s and "\r" not in s:
            print(f"  [{i:3d}] {s}")

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write("index\toffset\tstring\n")
            for i, (off, s) in enumerate(zip(offsets, strings)):
                esc = s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n")
                fh.write(f"{i}\t{off}\t{esc}\n")
        print(f"wrote         : {args.out}")

    if args.helpfile is not None:
        print("\n=== HELP.ENG (header only) ===")
        peek_helpfile(args.helpfile.read_bytes())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        sys.exit(1)
