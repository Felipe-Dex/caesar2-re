#!/usr/bin/env python3
"""Read-only: stamp occupancy helpers 6e0d6 / 6db08 / 69cfc."""

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


def main() -> None:
    img, src = load_image()
    print(f"image {src} len={len(img)}")
    for dest, name in (
        (0x6E0D6, "6e0d6"),
        (0x6DB08, "6db08"),
        (0x69CFC, "69cfc"),
    ):
        print(f"  calls {name}: {[hex(c) for c in find_calls_to(img, dest)[:16]]}")
    dump_asm(img, 0x6E0D6, 0x100, "6e0d6 occupancy?", 55)
    dump_asm(img, 0x6DB08, 0x80, "6db08 N x N probe", 40)
    dump_asm(img, 0x69CFC, 0xA0, "69cfc stamp", 45)
    dump_asm(img, 0x69D84, 0x80, "69cfc occupancy walk", 40)
    dump_asm(img, 0x69F26, 0xA0, "69f26 3x3 stamp head", 45)
    # Who writes [0xccb03]?
    needle = struct.pack("<I", 0xCCB03)
    hits = []
    i = 0
    while True:
        j = img.find(needle, i)
        if j < 0:
            break
        hits.append(j + BASE)
        i = j + 1
    print(f"\n=== refs 0xCCB03 ===")
    print(f"  {[hex(h) for h in hits[:24]]}")
    if hits:
        dump_asm(img, hits[0] - 0x10, 0x30, "first CCB03 ref", 12)


if __name__ == "__main__":
    main()
