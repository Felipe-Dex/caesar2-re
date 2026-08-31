#!/usr/bin/env python3
"""Read-only: Achea province gray=road + light-green=mountain.

Does not write the xlsx. Does not copy the SAV.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SAV = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV")
BIN = ROOT / "ghidra_work" / "c2_x.bin"
BASE = 0x10000

CHUNK13_OFF = 50395
CHUNK13_SIZE = 128000
CHUNK14_OFF = 178395
CHUNK14_SIZE = 28800
CITY_W = CITY_H = 80
CITY_REC = 20
MAP_W = MAP_H = 60
REC = 8

GREEN_LO, GREEN_HI = 0x7D, 0x91
GRAY_LO, GRAY_HI = 0xA0, 0xAF

N, S, E, W = 1, 2, 4, 8
DIRS = ((0, -1, N, "N"), (0, 1, S, "S"), (1, 0, E, "E"), (-1, 0, W, "W"))
NEIGH8 = (
    (0, -1, "N"),
    (1, -1, "NE"),
    (1, 0, "E"),
    (1, 1, "SE"),
    (0, 1, "S"),
    (-1, 1, "SW"),
    (-1, 0, "W"),
    (-1, -1, "NW"),
)

DIR_NAME = {
    0: "isolated",
    N: "end-N",
    S: "end-S",
    E: "end-E",
    W: "end-W",
    N | S: "straight NS",
    E | W: "straight EW",
    N | E: "corner NE",
    N | W: "corner NW",
    S | E: "corner SE",
    S | W: "corner SW",
    N | S | E: "T (no W)",
    N | S | W: "T (no E)",
    N | E | W: "T (no S)",
    S | E | W: "T (no N)",
    N | S | E | W: "cross",
}

# 4-cardinal bits from 8-neighbor LUT (N NE E SE S SW W NW)
CARD_FROM_8 = (0, 2, 4, 6)  # N E S W indices
CARD_BITS = (N, E, S, W)


def rec_at(blob: bytes, x: int, y: int) -> bytes:
    return blob[(y * MAP_W + x) * REC : (y * MAP_W + x) * REC + REC]


def city_rec(blob: bytes, x: int, y: int) -> bytes:
    return blob[(y * CITY_W + x) * CITY_REC : (y * CITY_W + x) * CITY_REC + CITY_REC]


def mask_name(m: int) -> str:
    return DIR_NAME.get(m, f"mask={m:04b}")


def neighbors_mask(ids, x, y, pred, w=MAP_W, h=MAP_H) -> int:
    m = 0
    for dx, dy, bit, _ in DIRS:
        nx, ny = x + dx, y + dy
        if 0 <= nx < w and 0 <= ny < h and pred(ids[ny][nx]):
            m |= bit
    return m


def connected_components(cells: set[tuple[int, int]]) -> list[list[tuple[int, int]]]:
    seen: set[tuple[int, int]] = set()
    blobs: list[list[tuple[int, int]]] = []
    for start in sorted(cells, key=lambda c: (c[1], c[0])):
        if start in seen:
            continue
        stack = [start]
        blob: list[tuple[int, int]] = []
        seen.add(start)
        while stack:
            x, y = stack.pop()
            blob.append((x, y))
            for dx, dy, _, _ in DIRS:
                n = (x + dx, y + dy)
                if n in cells and n not in seen:
                    seen.add(n)
                    stack.append(n)
        blobs.append(blob)
    return blobs


def footprint(cells: list[tuple[int, int]]) -> tuple[int, int, int, int, int, int]:
    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    xmin, xmax, ymin, ymax = min(xs), max(xs), min(ys), max(ys)
    return xmin, ymin, xmax, ymax, xmax - xmin + 1, ymax - ymin + 1


def dump_lut(img: bytes) -> list[tuple[bytes, int, int, int, int]]:
    """16 x 12-byte records at VA 0x94AEF."""
    off = 0x94AEF - BASE
    raw = img[off : off + 16 * 12]
    rows = []
    for i in range(16):
        rec = raw[i * 12 : (i + 1) * 12]
        pat = rec[:8]
        tid, extra, nframes, frame = rec[8], rec[9], rec[10], rec[11]
        rows.append((pat, tid, extra, nframes, frame))
    return rows


def lut_card_mask(pat: bytes) -> int:
    """Reduce 8-neigh pattern to NESW, treating 2 as don't-care (ignored)."""
    m = 0
    for idx, bit in zip(CARD_FROM_8, CARD_BITS):
        if pat[idx] == 1:
            m |= bit
    return m


def main() -> None:
    sav = SAV.read_bytes()
    if len(sav) != 225745:
        raise SystemExit(f"{SAV} size {len(sav)} != 225745")
    blob = sav[CHUNK14_OFF : CHUNK14_OFF + CHUNK14_SIZE]
    ids = [[rec_at(blob, x, y)[0] for x in range(MAP_W)] for y in range(MAP_H)]
    recs = [[rec_at(blob, x, y) for x in range(MAP_W)] for y in range(MAP_H)]

    img = BIN.read_bytes() if BIN.is_file() else b""
    if img:
        print("=== LUT 0x94AEF (16 x 12) city id / province = city+0x4E ===")
        rows = dump_lut(img)
        for i, (pat, tid, extra, nframes, frame) in enumerate(rows):
            bits = "".join(
                {0: ".", 1: name[0] if len(name) == 1 else name[0].lower(), 2: "?"}.get(pat[j], "?")
                for j, (_, _, name) in enumerate(NEIGH8)
            )
            card = lut_card_mask(pat)
            print(
                f"  [{i:2}] pat={pat.hex()} 8=[{bits}] card={mask_name(card):12} "
                f"city=0x{tid:02X} prov=0x{tid + 0x4E:02X} var={tid - 0x52} "
                f"extra=0x{extra:02X} frames={nframes} frame={frame}"
            )
        size2 = img[0x9422C - BASE : 0x9422C - BASE + 4]
        size3 = img[0x94230 - BASE : 0x94230 - BASE + 9]
        size4 = img[0x94239 - BASE : 0x94239 - BASE + 16]
        print(f"  stamp +4 LUT 2x2 0x9422C: {list(size2)}")
        print(f"  stamp +4 LUT 3x3 0x94230: {list(size3)}")
        print(f"  stamp +4 LUT 4x4 0x94239: {list(size4)}")

    gray_ids = sorted(
        {ids[y][x] for y in range(MAP_H) for x in range(MAP_W) if GRAY_LO <= ids[y][x] <= GRAY_HI}
    )
    green_ids = sorted(
        {ids[y][x] for y in range(MAP_H) for x in range(MAP_W) if GREEN_LO <= ids[y][x] <= GREEN_HI}
    )
    print("\n=== color ranges (xlsx class_of) ===")
    print(f"  gray 0x{GRAY_LO:02X}-0x{GRAY_HI:02X} present: {[hex(t) for t in gray_ids]}")
    print(f"  missing gray: {[hex(t) for t in range(GRAY_LO, GRAY_HI + 1) if t not in gray_ids]}")
    print(f"  green 0x{GREEN_LO:02X}-0x{GREEN_HI:02X} present: {[hex(t) for t in green_ids]}")
    print(f"  missing green: {[hex(t) for t in range(GREEN_LO, GREEN_HI + 1) if t not in green_ids]}")

    is_road = lambda t: GRAY_LO <= t <= GRAY_HI
    is_mnt = lambda t: GREEN_LO <= t <= GREEN_HI

    # ---- ROADS ----
    print("\n=== GRAY provincial road ===")
    road_cells = [(x, y) for y in range(MAP_H) for x in range(MAP_W) if is_road(ids[y][x])]
    print(f"  tiles={len(road_cells)} ids={len(gray_ids)}")

    plus = {k: Counter() for k in range(1, 8)}
    id_plus = defaultdict(lambda: {k: Counter() for k in range(1, 8)})
    id_mask = defaultdict(Counter)
    mask_id = defaultdict(Counter)
    id_count = Counter()
    id_examples = {}
    plus4_vs_id = Counter()

    for x, y in road_cells:
        r = recs[y][x]
        tid = r[0]
        id_count[tid] += 1
        for k in range(1, 8):
            plus[k][r[k]] += 1
            id_plus[tid][k][r[k]] += 1
        plus4_vs_id[(tid, r[4])] += 1
        m = neighbors_mask(ids, x, y, is_road)
        id_mask[tid][m] += 1
        mask_id[m][tid] += 1
        if tid not in id_examples:
            id_examples[tid] = (x, y, m, r)

    for k in range(1, 8):
        print(f"  +{k} all: {dict(plus[k])}")
    agree = sum(1 for (tid, v4), n in plus4_vs_id.items() if v4 == tid - 0xA0)
    print(f"  +4 == id-0xA0 tiles: {agree}/{len(road_cells)}")

    print("\n  --- id -> NESW among any gray ---")
    for tid in gray_ids:
        print(f"  0x{tid:02X} n={id_count[tid]:3} +1={dict(id_plus[tid][1])} +3={dict(id_plus[tid][3])} +4={dict(id_plus[tid][4])}")
        for m, n in sorted(id_mask[tid].items(), key=lambda z: -z[1]):
            bits = "".join(name if m & bit else "." for _, _, bit, name in DIRS)
            print(f"      [{bits:4}] {mask_name(m):12} n={n}")
        x, y, m, r = id_examples[tid]
        print(f"      ex ({x},{y}) rec={r.hex()}")

    print("\n  --- NESW mask -> ids ---")
    for m in sorted(mask_id):
        bits = "".join(name if m & bit else "." for _, _, bit, name in DIRS)
        ids_here = ", ".join(f"0x{t:02X}:{c}" for t, c in sorted(mask_id[m].items()))
        print(f"  {mask_name(m):12} [{bits:4}] {ids_here}")

    blobs = connected_components(set(road_cells))
    print(f"\n  road 4-conn components: {len(blobs)} sizes={[len(b) for b in sorted(blobs, key=len, reverse=True)]}")

    attach = Counter()
    for x, y in road_cells:
        for dx, dy, _, _ in DIRS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < MAP_W and 0 <= ny < MAP_H and not is_road(ids[ny][nx]):
                attach[ids[ny][nx]] += 1
    print("  non-road 4-neighbors:")
    for t, n in attach.most_common(15):
        print(f"    0x{t:02X} n={n}")

    # ---- CITY ROADS ----
    city = sav[CHUNK13_OFF : CHUNK13_OFF + CHUNK13_SIZE]
    cids = [[city_rec(city, x, y)[0] for x in range(CITY_W)] for y in range(CITY_H)]
    cplus1 = [[city_rec(city, x, y)[1] for x in range(CITY_W)] for y in range(CITY_H)]
    is_city_road_id = lambda t: 0x52 <= t <= 0x5C
    is_city_pad = lambda x, y: (cplus1[y][x] & 0x20) != 0 and cids[y][x] < 0x78
    city_id_cells = [(x, y) for y in range(CITY_H) for x in range(CITY_W) if is_city_road_id(cids[y][x])]
    city_pad_cells = [(x, y) for y in range(CITY_H) for x in range(CITY_W) if is_city_pad(x, y)]
    print("\n=== CITY roads (chunk 13) ===")
    print(f"  ids 0x52-0x5C tiles={len(city_id_cells)} hist={dict(Counter(cids[y][x] for x, y in city_id_cells))}")
    print(f"  terrain+pad (<0x78 & +1&0x20) tiles={len(city_pad_cells)} id hist={dict(Counter(cids[y][x] for x, y in city_pad_cells))}")

    cid_mask = defaultdict(Counter)
    for x, y in city_id_cells:
        m = neighbors_mask(cids, x, y, is_city_road_id, CITY_W, CITY_H)
        cid_mask[cids[y][x]][m] += 1
    print("  0x52-0x5C NESW among same range:")
    for tid in sorted(cid_mask):
        parts = ", ".join(f"{mask_name(m)}={n}" for m, n in sorted(cid_mask[tid].items(), key=lambda z: -z[1]))
        print(f"    0x{tid:02X} n={sum(cid_mask[tid].values()):4}  {parts}")

    # pad-neighbor among pad tiles, grouped by id
    pad_mask = defaultdict(Counter)
    for x, y in city_pad_cells:
        pred = lambda t, xx=x, yy=y: False  # filled below
        m = 0
        for dx, dy, bit, _ in DIRS:
            nx, ny = x + dx, y + dy
            if 0 <= nx < CITY_W and 0 <= ny < CITY_H and is_city_pad(nx, ny):
                m |= bit
        pad_mask[cids[y][x]][m] += 1
    print("  terrain+pad NESW among other pad:")
    for tid in sorted(pad_mask):
        if sum(pad_mask[tid].values()) < 5:
            continue
        parts = ", ".join(f"{mask_name(m)}={n}" for m, n in pad_mask[tid].most_common(4))
        print(f"    0x{tid:02X} n={sum(pad_mask[tid].values()):4}  {parts}")

    # ---- MOUNTAINS ----
    print("\n=== LIGHT GREEN / REGIONS 0x7D-0x91 ===")
    green_cells = [(x, y) for y in range(MAP_H) for x in range(MAP_W) if is_mnt(ids[y][x])]
    print(f"  tiles={len(green_cells)} ids={len(green_ids)}")

    def band(tid: int) -> str:
        if 0x7D <= tid <= 0x84:
            return "1x1 band (apply_regions variant=id-0x7D)"
        if 0x85 <= tid <= 0x8C:
            return "2x2 band (variant stride 4)"
        if 0x8D <= tid <= 0x90:
            return "3x3 band (variant stride 9)"
        if tid == 0x91:
            return "0x91 (variant 0x4C)"
        return "?"

    print("\n  --- per id same-id 4-conn footprints ---")
    for tid in green_ids:
        cells = {(x, y) for y in range(MAP_H) for x in range(MAP_W) if ids[y][x] == tid}
        blobs = connected_components(cells)
        plus1c = Counter(recs[y][x][1] for x, y in cells)
        plus3c = Counter(recs[y][x][3] for x, y in cells)
        plus4c = Counter(recs[y][x][4] for x, y in cells)
        plus5c = Counter(recs[y][x][5] for x, y in cells)
        sizes = Counter()
        size_ex = {}
        for b in blobs:
            xmin, ymin, xmax, ymax, w, h = footprint(b)
            filled = len(b) == w * h
            key = (w, h, len(b), filled)
            sizes[key] += 1
            if key not in size_ex:
                size_ex[key] = (xmin, ymin, xmax, ymax)
        print(
            f"  0x{tid:02X} tiles={len(cells):3} blobs={len(blobs):3} {band(tid)}"
        )
        print(f"      +1={dict(plus1c)} +3={dict(plus3c)} +4={dict(plus4c)} +5={dict(plus5c)}")
        for key, n in sorted(sizes.items(), key=lambda z: (-z[1], z[0])):
            w, h, ncells, filled = key
            xmin, ymin, xmax, ymax = size_ex[key]
            tag = f"{w}x{h}" if filled else f"bbox {w}x{h} n={ncells} IRREG"
            print(f"      {tag:28} blobs={n:3}  ex=({xmin},{ymin})-({xmax},{ymax})")

    mixed = connected_components(set(green_cells))
    print(f"\n  any-green 4-conn blobs={len(mixed)}")
    simple = Counter()
    for b in mixed:
        xmin, ymin, xmax, ymax, w, h = footprint(b)
        filled = len(b) == w * h
        nids = len({ids[y][x] for x, y in b})
        simple[(w, h, len(b), filled, nids)] += 1
    print("  size / filled / n_ids:")
    for (w, h, ncells, filled, nids), n in sorted(simple.items(), key=lambda z: (-z[1], z[0])):
        tag = f"{w}x{h}" if filled else f"bbox {w}x{h} n={ncells} IRREG"
        print(f"      {tag:28} n_ids={nids} blobs={n}")

    print("\n  mixed blob list:")
    for b in sorted(mixed, key=lambda z: (min(p[1] for p in z), min(p[0] for p in z))):
        xmin, ymin, xmax, ymax, w, h = footprint(b)
        idc = Counter(ids[y][x] for x, y in b)
        idhex = ",".join(f"0x{t:02X}x{c}" for t, c in sorted(idc.items()))
        filled = "rect" if len(b) == w * h else "irreg"
        print(f"      ({xmin},{ymin})-({xmax},{ymax}) {w}x{h} n={len(b)} {filled} [{idhex}]")


if __name__ == "__main__":
    main()
