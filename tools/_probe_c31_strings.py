#!/usr/bin/env python3
"""Hunt province VO text + RAW size tables. Local only."""

from __future__ import annotations

import re
import struct
from pathlib import Path

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
RATE = 22050


def ascii_strings(data: bytes, minu: int = 6) -> list[tuple[int, str]]:
    out = []
    cur = []
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not cur:
                start = i
            cur.append(chr(b))
        else:
            if len(cur) >= minu:
                out.append((start, "".join(cur)))
            cur = []
    if len(cur) >= minu:
        out.append((start, "".join(cur)))
    return out


def dump_around(path: Path, needles: list[bytes], ctx: int = 180) -> None:
    data = path.read_bytes()
    print(f"\n===== {path.name} ({len(data)}) =====")
    for n in needles:
        idx = 0
        hits = 0
        while hits < 12:
            i = data.find(n, idx)
            if i < 0:
                break
            lo, hi = max(0, i - ctx), min(len(data), i + len(n) + ctx)
            frag = re.sub(rb"[^\x09\x0a\x0d\x20-\x7e]", b".", data[lo:hi])
            print(f"-- {n!r} @{i} --")
            print(frag.decode("ascii", "replace"))
            idx = i + 1
            hits += 1
        if hits == 0:
            print(f"-- {n!r}: none --")


def find_sizes_in(data: bytes, sizes: dict[int, str]) -> None:
    hits = []
    for off in range(0, len(data) - 3):
        v = struct.unpack_from("<I", data, off)[0]
        if v in sizes:
            hits.append((off, v, sizes[v]))
    print(f"  size-table hits: {len(hits)}")
    for off, v, name in hits[:40]:
        around = data[max(0, off - 16) : off + 20]
        print(f"    @{off:08x} {v} ({name})  {around.hex()}")


def main() -> None:
    needles = [
        b"worth the",
        b"worth the danger",
        b"danger",
        b"Germania",
        b"barbarian",
        b"C31",
        b"c31",
        b".RAW",
        b".raw",
        b"A01.RAW",
        b"PREBATLE",
    ]
    for name in ("HELP.ENG", "C2.ENG", "PS.EXE", "REGIONS.DAT", "HISTORY.DAT", "RESOURCE.CFG"):
        p = GAME / name
        if p.exists():
            dump_around(p, needles)

    # RAW sizes
    raws = sorted(GAME.glob("*.RAW")) + sorted(GAME.glob("*.raw"))
    sizes = {}
    for p in raws:
        sizes[p.stat().st_size] = p.name.upper()
    print("\n===== RAW sizes inside PS.EXE / HELP.ENG / REGIONS.DAT =====")
    for name in ("PS.EXE", "HELP.ENG", "REGIONS.DAT", "C2.ENG", "DISCS.DAT"):
        p = GAME / name
        if not p.exists():
            continue
        print(f"--- {p.name} ---")
        find_sizes_in(p.read_bytes(), sizes)

    # unique RAW sizes? if two files share size, skip
    from collections import Counter
    c = Counter(sizes)
    # sizes maps size->name, last wins; rebuild properly
    by_sz: dict[int, list[str]] = {}
    for p in raws:
        by_sz.setdefault(p.stat().st_size, []).append(p.name.upper())
    unique = {sz: names[0] for sz, names in by_sz.items() if len(names) == 1}
    print(f"\nunique RAW sizes: {len(unique)} / {len(by_sz)}")

    # filename table in PS.EXE
    ps = (GAME / "PS.EXE").read_bytes()
    print("\n===== RAW-like strings in PS.EXE =====")
    for off, s in ascii_strings(ps, 5):
        u = s.upper()
        if ".RAW" in u or re.fullmatch(r"[ABC]\d{2}", u) or "PREBAT" in u:
            print(f"  @{off}: {s!r}")

    print("\n===== province-like strings in HELP.ENG =====")
    helpb = (GAME / "HELP.ENG").read_bytes()
    keys = (
        "province",
        "barbarian",
        "resources",
        "danger",
        "Gaul",
        "Germania",
        "Hispania",
        "Africa",
        "worth",
    )
    for off, s in ascii_strings(helpb, 20):
        if any(k.lower() in s.lower() for k in keys):
            if len(s) < 400:
                print(f"  @{off}: {s}")


if __name__ == "__main__":
    main()
