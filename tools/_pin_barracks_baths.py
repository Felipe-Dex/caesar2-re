#!/usr/bin/env python3
"""Read-only: pin barracks N×N occupancy + baths wet vs reservoir.

Ghidra HTTP is down this pass. Listing from mapped PS.EXE / c2_x.bin.
"""

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
    code = img[off : off + nbytes]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    print(f"\n==== {title} {va:#x} ====")
    n = 0
    for insn in dec.disasm(code, va):
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


def find_imm32(img: bytes, value: int, lo: int = 0x10000, hi: int = 0x90000) -> list[int]:
    needle = struct.pack("<I", value)
    hits = []
    off = lo - BASE
    start = 0
    span = hi - lo
    while True:
        i = img.find(needle, off + start, off + span)
        if i < 0:
            break
        hits.append(i + BASE)
        start = i - off + 1
    return hits


def main() -> None:
    img, src = load_image()
    print(f"image {src} len={len(img)}")

    print("\n=== DAT_00094FE5[0xE4] barracks size class ===")
    rec = img[0x94FE5 + 0xE4 - BASE]
    print(f"  0x94FE5[0xE4] = {rec} (9 -> N=3 via 0x68D54)")

    print("\n=== calls 6dba2 (+13 mask over N×N) ===")
    cs = find_calls_to(img, 0x6DBA2)
    print(f"  {[hex(c) for c in cs]}")

    print("\n=== calls 6a368 (baths +4 wet/dry) ===")
    cs368 = find_calls_to(img, 0x6A368)
    print(f"  {[hex(c) for c in cs368]}")

    print("\n=== imm 0xDF in 0x3FEF7..0x401E7 ===")
    for va in find_imm32(img, 0xDF, 0x3FEF7, 0x401E7):
        print(f"  {va:#x}")
    print("=== imm 0xE2 in 0x3FEF7..0x401E7 ===")
    for va in find_imm32(img, 0xE2, 0x3FEF7, 0x401E7):
        print(f"  {va:#x}")
    print("=== imm 0xE4 in 0x65000..0x6A000 (place band) ===")
    for va in find_imm32(img, 0xE4, 0x65000, 0x6A000)[:20]:
        print(f"  {va:#x}")

    dump_asm(img, 0x6DBA2, 0x70, "6dba2 +13 OR-test N×N", 35)
    dump_asm(img, 0x6A368, 0xC0, "6a368 baths +4 2×2", 50)
    dump_asm(img, 0x3FEF7, 0x280, "3fef7 water painter head", 120)

    # Baths arm is usually after fountain 0xDB–0xDE. Scan for cmp 0xDF.
    print("\n=== 3fef7 bytes matching cmp ?, 0xDF ===")
    off = 0x3FEF7 - BASE
    for i in range(0x300):
        if img[off + i : off + i + 5] == bytes([0x3D, 0xDF, 0x00, 0x00, 0x00]):
            print(f"  cmp eax, 0xDF @ {0x3FEF7 + i:#x}")
            dump_asm(img, 0x3FEF7 + i, 0xA0, "3fef7 baths cmp 0xDF", 40)
        if img[off + i : off + i + 3] == bytes([0x83, 0xF8, 0xDF]):
            print(f"  cmp eax, 0xDF (83f8) @ {0x3FEF7 + i:#x}")
            dump_asm(img, 0x3FEF7 + i, 0xA0, "3fef7 baths cmp 0xDF short", 40)

    # Place occupancy: 94FE5 used outside clear 0x68D41.
    print("\n=== disp32 refs to 0x94FE5 (place / clear) ===")
    needle = struct.pack("<I", 0x94FE5)
    i = 0
    hits = []
    while True:
        j = img.find(needle, i)
        if j < 0:
            break
        hits.append(j + BASE)
        i = j + 1
    print(f"  {[hex(h) for h in hits[:30]]}")

    # Typical clear-tile: cmp +0, 0x7C / 0x82 inside a size loop near place.
    dump_asm(img, 0x68CDE, 0x80, "68CDE clear rect walker", 35)
    dump_asm(img, 0x42E25, 0x80, "42e25 merge_ok_tile", 35)

    dump_asm(img, 0x40099, 0x150, "3fef7 baths 0xDF-0xE2", 90)
    dump_asm(img, 0x42980, 0x280, "place stamp / 6a368 / occupancy", 140)
    dump_asm(img, 0x42E79, 0x90, "42e25 N x N walk", 40)

    print("\n=== calls 42e25 merge_ok_tile ===")
    print(f"  {[hex(c) for c in find_calls_to(img, 0x42E25)[:24]]}")
    print("\n=== calls 6a368 from ===")
    for c in cs368:
        dump_asm(img, c - 0x20, 0x40, f"caller prelude {c:#x}", 18)


if __name__ == "__main__":
    main()
