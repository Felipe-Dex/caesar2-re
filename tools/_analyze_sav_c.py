#!/usr/bin/env python3
"""One-shot A/B/C.SAV surgical pair. Prints facts; does not copy save bodies."""

from __future__ import annotations

import struct
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.city_map import (  # noqa: E402
    ID_HOUSING_HI,
    ID_HOUSING_LO,
    ID_TERRAIN_MAX,
    MAP_H,
    MAP_W,
    SAV_HISTORY_BYTES,
    SAV_SIZE,
    SAV_TABLE_BYTES,
    TILE_BYTES,
    load_chunk_sizes,
    walk_sav_chunks,
)
from app.walkers import WALKER_COUNT, WALKER_STRIDE, STATE_FREE  # noqa: E402

NAMED = {
    0: "view kind",
    5: "year-BC hypothesis",
    6: "view scalar",
    7: "actor26 pool",
    8: "walker pool",
    13: "city map 80x80x20",
    16: "difficulty",
    17: "LFSR RNG",
    23: "sim-phase row cursor",
    24: "sim phase [0x1026A8]",
    25: "assignment seed",
    28: "city_treasury",
    29: "init fives",
    30: "init fives",
    155: "monthly construction / spend term",
    170: "unknown (advisor-flag sibling)",
    341: "rating from C2MODEL[0]",
    370: "view_submode",
    406: "skip_actors",
}

FIELD_OFF = {
    0: "id",
    1: "flags",
    2: "overlay",
    3: "draw/class",
    4: "variant",
    5: "spawn packed",
    6: "spawn cd",
    7: "walker0",
    8: "walker1",
    9: "overlay anim",
    10: "coverage",
    11: "housing grade",
    12: "amenity",
    13: "land-paint",
    14: "influence",
    15: "land-value",
    16: "fire",
    17: "road access",
    18: "queue",
    19: "goods/subtype",
}


def i32(buf: bytes | memoryview, off: int = 0) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def u32(buf: bytes | memoryview, off: int = 0) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def hex20(b: bytes | memoryview) -> str:
    return " ".join(f"{x:02X}" for x in bytes(b))


def live_walkers(chunk: memoryview) -> int:
    n = 0
    for i in range(WALKER_COUNT):
        rec = chunk[i * WALKER_STRIDE : (i + 1) * WALKER_STRIDE]
        if rec[0] and rec[0x22] != STATE_FREE:
            n += 1
    return n


def buildings(blob: memoryview) -> list[tuple[int, int, int]]:
    out = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            tid = blob[(y * MAP_W + x) * TILE_BYTES]
            if tid >= ID_TERRAIN_MAX:
                out.append((x, y, tid))
    return out


def housing(blob: memoryview) -> list[tuple[int, int, int]]:
    return [(x, y, tid) for x, y, tid in buildings(blob) if ID_HOUSING_LO <= tid <= ID_HOUSING_HI]


def tile_at(blob: memoryview, x: int, y: int) -> bytes:
    off = (y * MAP_W + x) * TILE_BYTES
    return bytes(blob[off : off + TILE_BYTES])


def file_off_tile(chunk13_off: int, x: int, y: int) -> int:
    return chunk13_off + (y * MAP_W + x) * TILE_BYTES


def classify_tile_delta(a: bytes, c: bytes) -> str:
    moved = [i for i in range(TILE_BYTES) if a[i] != c[i]]
    if moved == [13]:
        return "+13 only"
    if 0 in moved:
        return "id+" + ",".join(f"+{i}" for i in moved if i != 0)
    return ",".join(f"+{i}" for i in moved)


def plus13_only_bbox(diffs: list[tuple[int, int, bytes, bytes]]) -> None:
    only = [(x, y) for x, y, a, c in diffs if classify_tile_delta(a, c) == "+13 only"]
    print(f"  +13-only tiles: {len(only)}")
    if not only:
        return
    xs = [x for x, _ in only]
    ys = [y for _, y in only]
    print(f"  +13-only bbox : ({min(xs)},{min(ys)})-({max(xs)},{max(ys)})")
    vals = Counter()
    for x, y, a, c in diffs:
        if classify_tile_delta(a, c) == "+13 only":
            vals[(a[13], c[13])] += 1
    print(f"  +13 A->C vals : {dict(vals)}")
    by_y: dict[int, list[int]] = {}
    for x, y in only:
        by_y.setdefault(y, []).append(x)
    print("  +13-only rows:")
    for y in sorted(by_y):
        xs = sorted(by_y[y])
        # coalesce
        ranges = []
        lo = hi = xs[0]
        for x in xs[1:]:
            if x == hi + 1:
                hi = x
            else:
                ranges.append(f"{lo}-{hi}" if lo != hi else str(lo))
                lo = hi = x
        ranges.append(f"{lo}-{hi}" if lo != hi else str(lo))
        print(f"    y={y:2d} x={','.join(ranges)}")


def report_pair(tag_a: str, tag_c: str, blobs: dict[str, bytes], chunks: dict[str, list], sizes: list[int]) -> None:
    a, c = blobs[tag_a], blobs[tag_c]
    print(f"\n========== {tag_a} vs {tag_c} ==========")
    xor = sum(1 for x, y in zip(a, c) if x != y)
    print(f"total XOR bytes: {xor}")
    print(f"trailer ident  : {a[-SAV_HISTORY_BYTES:] == c[-SAV_HISTORY_BYTES:]}")

    offs = []
    pos = 0
    for sz in sizes:
        offs.append(pos)
        pos += sz

    changed = []
    for i, (ca, cc) in enumerate(zip(chunks[tag_a], chunks[tag_c])):
        nd = sum(1 for x, y in zip(ca, cc) if x != y)
        if nd:
            changed.append((i, nd, offs[i], sizes[i]))
    print(f"changed chunks : {len(changed)}")
    print(f"{'idx':>4} {'off':>8} {'size':>7} {'ndiff':>6}  name")
    for i, nd, off, sz in changed:
        name = NAMED.get(i, "")
        extra = ""
        if sz == 4:
            extra = f"  i32 {i32(chunks[tag_a][i])} -> {i32(chunks[tag_c][i])}"
        elif sz == 1:
            extra = f"  u8 {chunks[tag_a][i][0]} -> {chunks[tag_c][i][0]}"
        print(f"{i:4d} {off:8d} {sz:7d} {nd:6d}  {name}{extra}")

    # named unchanged
    print("-- named scalars unchanged --")
    for i, name in NAMED.items():
        if i >= len(chunks[tag_a]):
            continue
        same = bytes(chunks[tag_a][i]) == bytes(chunks[tag_c][i])
        if same:
            blob = chunks[tag_a][i]
            val = i32(blob) if len(blob) == 4 else (blob[0] if len(blob) == 1 else f"{len(blob)}B")
            print(f"  {i:3d} {name}: {val}")

    map_a = chunks[tag_a][13]
    map_c = chunks[tag_c][13]
    print(f"\n-- chunk 13 tiles --")
    print(f"  buildings {tag_a}: {buildings(map_a)}")
    print(f"  buildings {tag_c}: {buildings(map_c)}")
    print(f"  housing   {tag_a}: {housing(map_a)}")
    print(f"  housing   {tag_c}: {housing(map_c)}")

    diffs = []
    for y in range(MAP_H):
        for x in range(MAP_W):
            ta, tc = tile_at(map_a, x, y), tile_at(map_c, x, y)
            if ta != tc:
                diffs.append((x, y, ta, tc))
    print(f"  tiles differ : {len(diffs)}")
    classes = Counter(classify_tile_delta(ta, tc) for _, _, ta, tc in diffs)
    print(f"  classes      : {dict(classes)}")

    id_changes = [(x, y, ta, tc) for x, y, ta, tc in diffs if ta[0] != tc[0]]
    print(f"  id changes   : {len(id_changes)}")
    for x, y, ta, tc in id_changes:
        foff = file_off_tile(offs[13], x, y)
        print(f"\n  TILE ({x},{y}) file {foff}")
        print(f"    {tag_a}: {hex20(ta)}")
        print(f"    {tag_c}: {hex20(tc)}")
        for i in range(TILE_BYTES):
            if ta[i] != tc[i]:
                print(f"    +{i:02d} {FIELD_OFF[i]:16s}  {ta[i]:3d} (0x{ta[i]:02X}) -> {tc[i]:3d} (0x{tc[i]:02X})")
        hid = tc[0]
        in_house = ID_HOUSING_LO <= hid <= ID_HOUSING_HI
        print(f"    housing 0x82-0xA1? {in_house}  id=0x{hid:02X}")
        print(f"    +3&0x1C sheet     : 0x{tc[3] & 0x1C:02X}")
        print(f"    +5 lo-nibble      : {tc[5] & 0xF} (0=origin)")

    other = [(x, y, ta, tc) for x, y, ta, tc in diffs if ta[0] == tc[0] and classify_tile_delta(ta, tc) != "+13 only"]
    print(f"\n  non-id non-+13 tiles: {len(other)}")
    for x, y, ta, tc in other[:40]:
        moved = [i for i in range(TILE_BYTES) if ta[i] != tc[i]]
        print(f"    ({x},{y}) {classify_tile_delta(ta, tc)}  {hex20(ta)} -> {hex20(tc)}")
        for i in moved:
            print(f"      +{i} {ta[i]}->{tc[i]}")
    if len(other) > 40:
        print(f"    ... {len(other) - 40} more")

    plus13_only_bbox(diffs)

    # neighbors of each id-change
    for x, y, ta, tc in id_changes:
        print(f"\n  neighbors of ({x},{y}):")
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < MAP_W and 0 <= ny < MAP_H):
                    continue
                na, nc = tile_at(map_a, nx, ny), tile_at(map_c, nx, ny)
                mark = "DIFF" if na != nc else "same"
                print(f"    ({nx},{ny}) {mark} id {na[0]:02X}->{nc[0]:02X}  {hex20(nc)}")

    wa, wc = live_walkers(chunks[tag_a][8]), live_walkers(chunks[tag_c][8])
    print(f"\n  live walkers {tag_a}/{tag_c}: {wa} / {wc}")
    treas_a = i32(chunks[tag_a][28])
    treas_c = i32(chunks[tag_c][28])
    spend_a = i32(chunks[tag_a][155])
    spend_c = i32(chunks[tag_c][155])
    print(f"  treasury {tag_a}->{tag_c}: {treas_a} -> {treas_c}  delta {treas_c - treas_a}")
    print(f"  chunk155 {tag_a}->{tag_c}: {spend_a} -> {spend_c}")
    print(f"  debit vs 155          : treasury delta {- (treas_c - treas_a)} vs 155 {spend_c - spend_a}")


def main() -> int:
    paths = {tag: ROOT / f"{tag}.SAV" for tag in "ABC"}
    for tag, p in paths.items():
        if not p.is_file():
            print(f"MISSING {p}", file=sys.stderr)
            return 1
    sizes = load_chunk_sizes()
    print(f"chunk sizes: {len(sizes)} sum={sum(sizes)} (want {SAV_TABLE_BYTES})")
    blobs = {tag: p.read_bytes() for tag, p in paths.items()}
    chunks = {}
    for tag, data in blobs.items():
        print(f"{tag}.SAV {len(data)} bytes  (want {SAV_SIZE})")
        chunks[tag] = walk_sav_chunks(data, sizes)
        print(f"  nchunks={len(chunks[tag])}  map={len(chunks[tag][13])}  walkers={len(chunks[tag][8])}")

    # A vs B reminder
    xor_ab = sum(1 for x, y in zip(blobs["A"], blobs["B"]) if x != y)
    xor_ac = sum(1 for x, y in zip(blobs["A"], blobs["C"]) if x != y)
    xor_bc = sum(1 for x, y in zip(blobs["B"], blobs["C"]) if x != y)
    print(f"\nXOR A-B={xor_ab}  A-C={xor_ac}  B-C={xor_bc}")
    print(f"C==B? {blobs['C'] == blobs['B']}  C==A? {blobs['C'] == blobs['A']}")

    report_pair("A", "C", blobs, chunks, sizes)

    # Decide if C looks like B+house
    map_b, map_c = chunks["B"][13], chunks["C"][13]
    blds_b, blds_c = buildings(map_b), buildings(map_c)
    print(f"\n========== C vs B (house-on-reservoir check) ==========")
    print(f"buildings B: {blds_b}")
    print(f"buildings C: {blds_c}")
    print(f"B has 0xBE at (0,0)? {tile_at(map_b, 0, 0)[0] == 0xBE}")
    print(f"C has 0xBE at (0,0)? {tile_at(map_c, 0, 0)[0] == 0xBE}")
    # C looks like B+house if C still has B's reservoir and extra housing, or if
    # C's map is a superset of B's buildings.
    looks_like_b_plus = bool(set(blds_b) & set(blds_c)) or (
        tile_at(map_c, 0, 0)[0] == 0xBE and housing(map_c)
    )
    print(f"looks like B+house: {looks_like_b_plus}")
    report_pair("B", "C", blobs, chunks, sizes)

    # plus13 compare: does C have A's zeros or B's river splash?
    def plus13_nonzero(m: memoryview) -> int:
        return sum(1 for i in range(13, len(m), TILE_BYTES) if m[i])

    print("\n========== +13 paint summary ==========")
    for tag in "ABC":
        m = chunks[tag][13]
        nz = plus13_nonzero(m)
        vals = Counter(m[i] for i in range(13, len(m), TILE_BYTES) if m[i])
        print(f"  {tag} +13 nonzero tiles: {nz}  vals={dict(vals)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
