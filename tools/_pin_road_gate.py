#!/usr/bin/env python3
"""Read-only pin: wall↔road Gate 0xC0 and aqueduct↔road 0xD5/0xD6.

Ghidra HTTP down. Capstone on mapped PS.EXE / c2_x.bin.
  0x665DF  road flood — +1&0x02 → 0x24; OR pad; then 669C6
  0x66B0E  669C6 — +1&0x04 → 67201; +1&0x40 → 67a6a; else +0>=0x7C skip
  0x66F10  wall flood
  0x67201  pad+0x04 → Gate 0xC0
  0x67A6A  pipe+pad → LUT 0x94E37 → 0xD5/0xD6
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


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 50) -> None:
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


def main() -> None:
    img, src = load_image()
    print(f"image {src} len={len(img)}")
    dump_asm(img, 0x66F10, 0x100, "66F10 wall place head", 55)
    dump_asm(img, 0x66B0E, 0x80, "669C6 +1&0x04 / +1&0x40 / 0x7C", 35)
    dump_asm(img, 0x67A6A, 0x120, "67a6a aqueduct retile", 60)
    print("\n=== LUT 0x94E37 (aqueduct-over-road x2) ===")
    off = 0x94E37 - BASE
    for i in range(2):
        row = img[off + i * 12 : off + i * 12 + 12]
        print(f"  {i} {row.hex(' ')}")

    from app.place import selftest as place_selftest

    print("\n=== host place selftest (gate / aqueduct-road) ===")
    keys = (
        "road-on-wall",
        "wall-on-road",
        "Gate 0xC0",
        "0xD5",
        "0xD6",
        "aqueduct",
        "estrada recusa",
        "road-on-aqueduct",
        "aqueduct-on-road",
        "grass still",
        "Barracks 0xE4 3x3: overlap",
    )
    for line in place_selftest():
        if any(k in line for k in keys):
            print(" ", line)
            if line.startswith("FAIL"):
                sys.exit(1)


if __name__ == "__main__":
    main()
