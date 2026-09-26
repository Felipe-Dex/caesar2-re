#!/usr/bin/env python3
"""Pin EXE Query fill-then-draw (0x64337 / 0x63845 / 0x62a59 / 0x26f16)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

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
    dec.detail = False
    print(f"\n==== {title} {va:#x}..{va + nbytes:#x} ====")
    n = 0
    for insn in dec.disasm(img[off : off + nbytes], va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")
        n += 1
        if n >= limit:
            print("  ...")
            break


def find_calls_to(img: bytes, dest: int, lo: int = 0x10000, hi: int = 0x80000) -> list[int]:
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


def main() -> None:
    img, src = load_image()
    print(f"image {src}  len={len(img)}")
    print("GhidraMCP 127.0.0.1:8080 was down; Capstone on mapped c2_x.")
    print()
    print("Query strings: 0x64337 samples tiles into [0x117a**],")
    print("0x63845 picks C2.ENG [60] skips, 0x62a59 evolve, then 0x26f16 blit.")
    print("No dialog chrome before those fills.")

    dump_asm(img, 0x64337, 0x100, "64337 tile -> 0x117a scratch", 40)
    dump_asm(img, 0x63845, 0x80, "63845 scratch -> [60] skip", 28)
    dump_asm(img, 0x62A59, 0x60, "62a59 evolve [60]+60..87", 24)

    print("\n==== callers 0x64337 (fill before draw) ====")
    for va in find_calls_to(img, 0x64337, 0x61000, 0x66000)[:12]:
        dump_asm(img, max(0x61000, va - 0x18), 0x30, f"call 64337 @{va:#x}", 12)

    print("\n==== callers 0x63845 ====")
    for va in find_calls_to(img, 0x63845, 0x61000, 0x66000)[:8]:
        dump_asm(img, max(0x61000, va - 0x18), 0x30, f"call 63845 @{va:#x}", 12)

    print("\n==== 0x26f16 in 0x62700..0x63000 (draw after fill) ====")
    for va in find_calls_to(img, 0x26F16, 0x62700, 0x63000)[:10]:
        dump_asm(img, max(0x62700, va - 0x10), 0x20, f"26f16 @{va:#x}", 10)


if __name__ == "__main__":
    main()
