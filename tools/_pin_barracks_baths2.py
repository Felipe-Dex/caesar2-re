#!/usr/bin/env python3
"""Read-only follow-up: 3fef7 baths arm + stamp occupancy."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 80) -> None:
    off = va - BASE
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    print(f"\n==== {title} {va:#x} ====")
    n = 0
    for insn in dec.disasm(img[off : off + nbytes], va):
        print(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} "
            f"{insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= limit:
            print("  ...")
            break


def find_calls_to(img: bytes, dest: int, lo: int = 0x10000, hi: int = 0x90000) -> list[int]:
    hits = []
    off = lo - BASE
    span = hi - lo
    i = 0
    while i < span - 4:
        if img[off + i] == 0xE8:
            rel = struct.unpack_from("<i", img, off + i + 1)[0]
            if lo + i + 5 + rel == dest:
                hits.append(lo + i)
        i += 1
    return hits


def find_cmp_imm(img: bytes, imm: int, lo: int, hi: int) -> list[int]:
    """cmp eax/edx/reg, imm32 or cmp ebx, imm32."""
    hits = []
    needle = struct.pack("<I", imm)
    off = lo - BASE
    span = hi - lo
    i = 0
    while i < span - 5:
        if img[off + i] == 0x3D and img[off + i + 1 : off + i + 5] == needle:
            hits.append(lo + i)
        if img[off + i] in (0x81, 0x83) and img[off + i + 2 : off + i + 6] == needle:
            hits.append(lo + i)
        i += 1
    return hits


def main() -> None:
    img, src = load_image()
    print(f"image {src} len={len(img)}")

    dump_asm(img, 0x40099, 0xE0, "3fef7 baths arm 0x40099", 70)
    dump_asm(img, 0x42840, 0x160, "place graphic 0x42840", 80)

    print("\n=== cmp 0x78 (terrain max) 0x2F000-0x32000 / 0x65000-0x6C000 ===")
    for va in find_cmp_imm(img, 0x78, 0x2F000, 0x32000) + find_cmp_imm(
        img, 0x78, 0x65000, 0x6C000
    ):
        print(f"  {va:#x}")

    print("\n=== cmp 0xE4 0x2F000-0x32000 ===")
    for va in find_cmp_imm(img, 0xE4, 0x2F000, 0x32000):
        print(f"  {va:#x}")

    print("\n=== callers of stamp fn around 0x42900 ===")
    # find function start: last ret before 0x42900, then next push
    dump_asm(img, 0x30280, 0x120, "0x30280 (6dba2 caller)", 55)

    # Occupancy helper often called before 6a368 place. Search calls to
    # a tile-ok predicate. 0x6Bxxx / 0x66xxx.
    print("\n=== calls into 0x665DF flood / 0x6xxxx near place ===")
    for dest in (0x665DF, 0x669C6, 0x67A6A):
        cs = find_calls_to(img, dest)
        print(f"  {dest:#x}: {[hex(c) for c in cs[:12]]}")


if __name__ == "__main__":
    main()
