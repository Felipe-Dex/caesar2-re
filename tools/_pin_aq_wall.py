#!/usr/bin/env python3
"""Read-only pin: aqueduct↔wall morph 0xC1→0xBD / 0xC2→0xBC.

Ghidra HTTP down. Capstone on mapped c2_x.bin.
  0x67A6A  +1&0x40|0x02 rewrites C1/C2
  0x66F10  wall flood pad/pipe
  0x669C6  road/pipe retile
"""

from __future__ import annotations

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


def find_imm(img: bytes, imm: int, title: str, limit: int = 20) -> None:
    """Find B8/C6/C7 immediates that write a byte id."""
    print(f"\n==== xrefs-ish imm {title} {imm:#x} ====")
    needle = bytes((0xB8, imm, 0, 0, 0))  # mov eax, imm32
    n = 0
    start = 0
    while n < limit:
        i = img.find(needle, start)
        if i < 0:
            break
        print(f"  mov eax,{imm:#x} at {i + BASE:#x}")
        n += 1
        start = i + 1
    # c605 xx xx xx xx imm  mov byte [abs], imm
    pat = bytes((0xC6, 0x05))
    start = 0
    n = 0
    while n < limit:
        i = img.find(pat, start)
        if i < 0:
            break
        if i + 7 < len(img) and img[i + 6] == imm:
            print(f"  mov byte [...], {imm:#x} at {i + BASE:#x}")
            n += 1
        start = i + 1


def main() -> None:
    img, src = load_image()
    print(f"image {src} len={len(img)}")
    # DAT_00094FE5[id] size/type from 0x82
    # 94FE5 is indexed from 0x82; for 0xBC: 94FE5 + (0xBC-0x82)
    base_lut = 0x94FE5 - BASE
    for tid in (0xBC, 0xBD, 0xBE, 0xC0, 0xC1, 0xC2, 0xCB, 0xD0):
        print(f"  DAT_94FE5[{tid:#x}] = {img[base_lut + (tid - 0x82)]}")

    # +4 LUT 0x94f6c
    lut = 0x94F6C - BASE
    print("\n=== LUT 0x94F6C +4[+0] ===")
    for tid in range(0xBC, 0xC3):
        print(f"  {tid:#x} -> {img[lut + tid]:#x}")

    dump_asm(img, 0x67AF0, 0x1C0, "67a6a wall-bit C1/C2 morph", 90)
    dump_asm(img, 0x67270, 0x80, "67201 write 0xBC/0xBD", 40)
    dump_asm(img, 0x66FBB, 0x80, "66F10 +1&0x04 / +1&0x20 / OR wall", 40)
    dump_asm(img, 0x66B47, 0x50, "669C6 +1&0x40 -> 67a6a", 25)
    print("\n=== LUT 0x94E4F (aqueduct-through-wall x2) ===")
    off = 0x94E4F - BASE
    for i in range(4):
        row = img[off + i * 12 : off + i * 12 + 12]
        print(f"  {i} {row.hex(' ')}")
    print("\n=== LUT 0x94D17 / 0x94CEB around wall+4 ===")
    for va in (0x94CEB, 0x94CED, 0x94D17):
        off = va - BASE
        print(f"  {va:#x} {img[off:off+16].hex(' ')}")
    find_imm(img, 0xBC, "0xBC")
    find_imm(img, 0xBD, "0xBD")

    from app.place import selftest as place_selftest

    print("\n=== host place selftest (aqueduct-wall / gate / road) ===")
    keys = (
        "wall-on-aqueduct",
        "aqueduct-on-wall",
        "0xBC",
        "0xBD",
        "wall-on-road",
        "road-on-wall",
        "Gate 0xC0",
        "grass aqueduct",
        "grass wall",
        "Barracks 0xE4 3x3: overlap",
    )
    for line in place_selftest():
        if any(k in line for k in keys):
            print(" ", line)
            if line.startswith("FAIL"):
                sys.exit(1)


if __name__ == "__main__":
    main()
