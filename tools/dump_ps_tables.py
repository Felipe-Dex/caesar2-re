#!/usr/bin/env python3
"""Hunt constants and int32 tables inside the mapped PS.EXE image.

Looks for SAV geometry (80, 6400, 1745, 225745), C2MODEL numbers
(20000..5000, housing occupancy), and filename/cost arrays.
Does not rewrite probe_sav_map / dump_c2model — those stay with the SAV/model agents.
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter
from pathlib import Path

from ps_le import (
    DEFAULT_EXE,
    file_offset_of_va,
    find_u16s,
    find_u32s,
    load_ps,
    map_image,
    u32,
    xrefs_to_va,
)

# FAQ / C2MODEL sequences we expect either in the DAT file or duplicated in .text/.data
SEQUENCES: dict[str, list[int]] = {
    "starting_money_5diff": [20000, 15000, 12000, 7000, 5000],
    "house_occupancy_32": [
        2, 4, 6, 8, 10, 12, 6, 7, 8, 9, 12, 16, 20, 24, 28, 32,
        36, 42, 48, 54, 20, 25, 30, 35, 40, 45, 100, 120, 150, 200, 300, 500,
    ],
    "worship_costs": [80, 200, 600],
    "entertainment_costs": [300, 500, 700, 1000, 1500, 2500],
    "province_costs_plus_garden": [3, 20, 50, 500, 100, 250, 1000, 150, 400, 500],
    "pop_unlocks": [400, 800, 1200, 1800, 2400, 4800],
    "lv_evolve": [17, 33, 49],
    "rank_individual": [20, 25, 30, 35, 40, 45, 50, 55, 60, 65],
    "rank_average": [30, 35, 40, 45, 50, 55, 60, 65, 70, 74],
}

CONSTANTS: dict[str, int] = {
    "map_side_80": 80,
    "plane_bytes_6400": 6400,
    "sav_header_1745": 1745,
    "sav_size_225745": 225745,
    "c2model_bytes_4360": 4360,
    "c2model_ints_1090": 1090,
    "pcm_rate_22050": 22050,
    "pcm_rate_11025": 11025,
    "vga_640": 640,
    "vga_480": 480,
    "start_money_novice": 20000,
    "start_money_imp": 5000,
    "planes_35": 35,
}


def find_seq_bytes(hay: bytes, values: list[int], width: int = 4) -> list[int]:
    if width == 4:
        needle = b"".join(struct.pack("<i", v) for v in values)
    elif width == 2:
        needle = b"".join(struct.pack("<h", v) for v in values)
    else:
        needle = bytes(v & 0xFF for v in values)
    hits = []
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    return hits


def dump_int_row(img: bytes, off: int, count: int, width: int = 4) -> str:
    vals = []
    for i in range(count):
        if width == 4:
            vals.append(struct.unpack_from("<i", img, off + 4 * i)[0])
        else:
            vals.append(struct.unpack_from("<h", img, off + 2 * i)[0])
    return " ".join(str(v) for v in vals)


def classify_imm_site(img: bytes, off: int) -> str:
    """Tiny x86 prefix hint: byte before a 32-bit immediate."""
    if off == 0:
        return "?"
    b = img[off - 1]
    names = {
        0xB8: "mov eax,imm32",
        0xB9: "mov ecx,imm32",
        0xBA: "mov edx,imm32",
        0xBB: "mov ebx,imm32",
        0x68: "push imm32",
        0x05: "add eax,imm32",
        0x2D: "sub eax,imm32",
        0x3D: "cmp eax,imm32",
        0xA1: "mov eax,[imm32]",
        0xA3: "mov [imm32],eax",
    }
    if b in names:
        return names[b]
    if off >= 2 and img[off - 2] == 0xC7:
        return "mov r/m32,imm32"
    if off >= 3 and img[off - 3] in (0x81, 0x83):
        return "alu r/m,imm"
    return f"pre={b:02x}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Hunt tables/constants in mapped PS.EXE.")
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    ap.add_argument("--out", type=Path, default=None, help="optional TSV of sequence hits")
    args = ap.parse_args(argv)

    ps = load_ps(args.exe)
    mapped = map_image(ps)
    img = bytes(mapped.image)
    raw = ps.data

    print("=== mapped constants (u32 immediates / data) ===")
    print(f"{'name':28s} {'value':>10s}  file-hits  map-hits  sample_VA (prefix)")
    for name, val in CONSTANTS.items():
        file_hits = find_u32s(raw, val)
        map_hits = find_u32s(img, val)
        samples = []
        for h in map_hits[:6]:
            va = mapped.base + h
            samples.append(f"{va:#x}/{classify_imm_site(img, h)}")
        print(
            f"{name:28s} {val:10d}  {len(file_hits):9d}  {len(map_hits):8d}  "
            + "  ".join(samples)
        )

    print("\n=== u16 80 / 6400 (map geometry) ===")
    for name, val, finder in (
        ("u16_80", 80, find_u16s),
        ("u16_6400", 6400, find_u16s),
        ("u16_1745", 1745, find_u16s),
        ("u16_35", 35, find_u16s),
    ):
        mh = finder(img, val)
        print(f"  {name:12s} n={len(mh)}")

    print("\n=== known sequences in mapped image ===")
    rows = []
    for name, seq in SEQUENCES.items():
        for width, wname in ((4, "i32"), (2, "i16")):
            hits = find_seq_bytes(img, seq, width=width)
            if not hits:
                continue
            for h in hits:
                va = mapped.base + h
                foff = file_offset_of_va(mapped, va)
                print(
                    f"  {name:28s} {wname}  VA {va:#08x}  file {foff}  "
                    f"n={len(seq)}"
                )
                rows.append((name, wname, va, foff, len(seq)))
            # context: 4 ints before
            if width == 4 and hits:
                h0 = hits[0]
                pre = max(0, h0 - 16)
                print(f"      pre  : {dump_int_row(img, pre, 4)}")
                print(f"      row  : {dump_int_row(img, h0, min(12, len(seq)))}")
                post = h0 + 4 * len(seq)
                if post + 16 <= len(img):
                    print(f"      post : {dump_int_row(img, post, 4)}")

    # filename blob: look for packed ".pl8" / ".raw" runs
    print("\n=== extension clusters in mapped image ===")
    for ext in (b".pl8", b".PL8", b".raw", b".RAW", b".sav", b".SAV", b".eng"):
        hits = []
        start = 0
        while True:
            i = img.find(ext, start)
            if i < 0:
                break
            hits.append(mapped.base + i)
            start = i + 1
        print(f"  {ext!r:10s} n={len(hits)}  first={hex(hits[0]) if hits else '-'}")

    # 35 consecutive pointer-sized slots that look like plane bases?
    print("\n=== 6400-stride pointer-ish runs (hyp: plane table) ===")
    # Search for two u32s that differ by 6400
    stride_hits = 0
    examples = []
    for i in range(0, len(img) - 8, 4):
        a = u32(img, i)
        b = u32(img, i + 4)
        if b - a == 6400 and mapped.contains(a) and mapped.contains(b):
            # count following
            n = 2
            prev = b
            j = i + 8
            while j + 4 <= len(img):
                c = u32(img, j)
                if c - prev != 6400:
                    break
                n += 1
                prev = c
                j += 4
            if n >= 8:
                stride_hits += 1
                if len(examples) < 8:
                    examples.append((mapped.base + i, n, a, prev))
    print(f"  runs >=8 with +6400 and both VAs mapped: {stride_hits}")
    for va, n, first, last in examples:
        print(f"    VA {va:#x}  count={n}  first={first:#x} last={last:#x}")

    # xrefs to 6400 as relocation targets? not useful. Print code sites of imm 6400.
    print("\n=== code-ish sites of imm32 6400 / 1745 / 225745 ===")
    for val, label in ((6400, "6400"), (1745, "1745"), (225745, "savsize"), (80, "80"), (35, "35")):
        hits = find_u32s(img, val)
        codeish = []
        for h in hits:
            hint = classify_imm_site(img, h)
            if hint != f"pre={img[h-1]:02x}" if h else True:
                if not hint.startswith("pre=") or img[h - 1] in (
                    0x04, 0x14, 0x1C, 0x24, 0x2C, 0x34, 0x3C, 0x44, 0x4C,
                    0x54, 0x5C, 0x64, 0x6C, 0x74, 0x7C, 0x81, 0x83, 0xC7,
                    0x05, 0x0D, 0x15, 0x1D, 0x25, 0x2D, 0x35, 0x3D,
                ):
                    codeish.append((mapped.base + h, hint))
        print(f"  {label}: {len(hits)} total, showing {min(12, len(codeish))} code-ish")
        for va, hint in codeish[:12]:
            foff = file_offset_of_va(mapped, va)
            print(f"    VA {va:#08x}  file {foff}  {hint}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write("name\twidth\tva\tfile_off\tn\n")
            for row in rows:
                fh.write(f"{row[0]}\t{row[1]}\t{row[2]:#x}\t{row[3]}\t{row[4]}\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
