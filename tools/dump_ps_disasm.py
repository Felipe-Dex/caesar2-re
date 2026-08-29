#!/usr/bin/env python3
"""Disassemble hypothesized PS.EXE functions (Capstone) and hunt SAV geometry.

Uses the mapped LE image after fixups. Prints a short listing around known
string xrefs and scans for pointer pairs whose difference is 1745 / 6400 /
225745 (sizeof computed from two labels, not an immediate).
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

from ps_le import (
    DEFAULT_EXE,
    file_offset_of_va,
    load_ps,
    map_image,
    xrefs_to_va,
)

TARGETS = {
    "startup/resource.cfg": 0x10000,
    "gfx_load_cluster": 0x10DCA,
    "c2eng_load_site": 0x10F90,
    "miles_rate_22050": 0x11FF0,
    "raw_bank_index": 0x13580,
    "lastyear_autosave": 0x34D80,
    "save_dialog": 0x6FACC,
    "save_caesar2": 0x7024A,
    "regions_dat": 0x706C6,
    "c2eng_alt": 0x704B0,
    "ail_set_sample_addr_dbg": 0x74300,
}

DIFFS = {
    1745: "SAV_header_sizeof",
    6400: "plane_80x80",
    224000: "35*6400",
    225745: "SAV_total",
    4360: "C2MODEL_size",
    1090: "C2MODEL_count",
    80: "map_side",
}


def md(mapped, va: int, count: int = 48) -> None:
    off = mapped.va_to_off(va)
    if off is None:
        print(f"  !! {va:#x} not mapped")
        return
    code = bytes(mapped.image[off : off + count * 8])
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print(f"---- {va:#x}  file {file_offset_of_va(mapped, va)} ----")
    n = 0
    for insn in dec.disasm(code, va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")
        n += 1
        if n >= count:
            break


def call_target(mapped, va: int) -> int | None:
    """If VA is an E8 rel32 call, return destination."""
    off = mapped.va_to_off(va)
    if off is None or mapped.image[off] != 0xE8:
        return None
    rel = struct.unpack_from("<i", mapped.image, off + 1)[0]
    return va + 5 + rel


def find_nl_strings(mapped, prefix: bytes) -> list[int]:
    img = bytes(mapped.image)
    out = []
    start = 0
    while True:
        i = img.find(prefix, start)
        if i < 0:
            break
        out.append(mapped.base + i)
        start = i + 1
    return out


def hunt_ptr_diffs(mapped) -> None:
    print("=== relocated pointer pairs (code immediates) with SAV-ish diffs ===")
    img = bytes(mapped.image)
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    # scan obj1 only (code)
    obj1 = mapped.objects[0]
    off0 = mapped.va_to_off(obj1.base)
    code = img[off0 : off0 + obj1.virtual_size]
    imms: list[tuple[int, int]] = []  # (site_va, imm)
    for insn in dec.disasm(code, obj1.base):
        if insn.mnemonic in ("mov", "lea", "push", "add", "sub", "cmp") and insn.op_str:
            # parse trailing 0ximm
            if "0x" in insn.op_str:
                try:
                    tail = insn.op_str.split("0x")[-1].split(",")[0].split("]")[0]
                    val = int(tail, 16)
                except ValueError:
                    continue
                if mapped.contains(val):
                    imms.append((insn.address, val))
    print(f"  code immediates that look like VAs: {len(imms)}")
    # nearby pairs in the same 32-byte window
    hits = []
    for i, (a_va, a) in enumerate(imms):
        for b_va, b in imms[i + 1 : i + 8]:
            if b_va - a_va > 32:
                break
            d = abs(a - b)
            if d in DIFFS:
                hits.append((d, a_va, a, b_va, b))
    print(f"  nearby pairs with known diffs: {len(hits)}")
    for d, a_va, a, b_va, b in hits[:40]:
        print(
            f"  {DIFFS[d]:18s} {d:7d}  @{a_va:#x}->{a:#x}  @{b_va:#x}->{b:#x}  "
            f"file {file_offset_of_va(mapped, a_va)}"
        )

    # also: two consecutive dwords in data that differ by these
    print("=== data dword pairs ===")
    obj2 = mapped.objects[1]
    o2 = mapped.va_to_off(obj2.base)
    backed = min(obj2.page_count * 4096, obj2.virtual_size)
    blob = img[o2 : o2 + backed]
    counts = Counter()
    examples = {d: [] for d in DIFFS}
    for i in range(0, len(blob) - 8, 4):
        a = struct.unpack_from("<I", blob, i)[0]
        b = struct.unpack_from("<I", blob, i + 4)[0]
        d = abs(a - b)
        if d in DIFFS:
            counts[d] += 1
            if len(examples[d]) < 6:
                examples[d].append((obj2.base + i, a, b))
    for d, name in DIFFS.items():
        print(f"  {name:18s} n={counts[d]}  ex={[(hex(v), hex(a), hex(b)) for v,a,b in examples[d]]}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Disassemble key PS.EXE sites.")
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    ap.add_argument("--site", type=lambda x: int(x, 0), default=None)
    ap.add_argument("--count", type=int, default=40)
    args = ap.parse_args(argv)

    ps = load_ps(args.exe)
    mapped = map_image(ps)

    if args.site is not None:
        md(mapped, args.site, args.count)
        return 0

    print("=== error-string xrefs (leading newline) ===")
    for pfx in (
        b"\nError loading graphics",
        b"\nError loading overlay",
        b"\nError loading battle",
        b"Not enough free memory",
    ):
        vas = find_nl_strings(mapped, pfx)
        for va in vas:
            xrs = xrefs_to_va(mapped, va)
            print(f"  {pfx!r:40s} VA {va:#x} xrefs={[hex(x) for x in xrs]}")

    print("\n=== common loader: calls after mov eax, filename ===")
    # from earlier hex: call follows mov eax, str
    sites = {
        "c2.eng@10fd4": 0x10FD9,
        "cityfixt@10e99": 0x10E9E,
        "font@10edf": 0x10EE4,
        "caesar2.sav@7042a": 0x7042F,
        "regions@706eb": 0x706F0,
    }
    for name, va in sites.items():
        # va might be the mov; find following E8
        off = mapped.va_to_off(va)
        tgt = None
        for delta in range(0, 8):
            t = call_target(mapped, va + delta)
            if t:
                tgt = t
                print(f"  {name:24s} call @{va+delta:#x} -> {t:#x}  file {file_offset_of_va(mapped, t)}")
                break
        if tgt is None:
            print(f"  {name:24s} no E8 near {va:#x}  bytes={bytes(mapped.image[off:off+12]).hex() if off else '?'}")

    print()
    hunt_ptr_diffs(mapped)

    print("\n=== disassembly of key sites ===")
    for name, va in TARGETS.items():
        print(f"\n## {name}")
        md(mapped, va, 36)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
