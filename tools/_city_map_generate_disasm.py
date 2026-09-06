#!/usr/bin/env python3
"""Capstone listing of init_new_city + city_map_generate (Ghidra HTTP down).

Reads mapped LE image. Does not copy PS.EXE into the repo.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000

RANGES = [
    ("start_city_assignment", 0x1049B, 0xCA),
    ("init_new_city", 0x10565, 0x156),
    ("city_map_generate", 0x65809, 0x658D1 - 0x65809),
    ("city_map_trace_feature", 0x658D1, 0x65AFA - 0x658D1),
    ("city_map_fill_rand_terrain", 0x65AFA, 0x120),
    ("city_map_clear_byte8", 0x6E188, 0x80),
    ("city_map_zero_lanes", 0x6E140, 0x48),
]


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_asm(img: bytes, va: int, nbytes: int, title: str) -> None:
    off = va - BASE
    code = img[off : off + nbytes]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print(f"\n==== {title} {va:#x}..{va + nbytes:#x} ====")
    for insn in dec.disasm(code, va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")


def find_calls(img: bytes, lo: int, hi: int) -> list[tuple[int, int]]:
    hits = []
    off = lo - BASE
    i = 0
    span = hi - lo
    while i < span - 4:
        if img[off + i] == 0xE8:
            rel = struct.unpack_from("<i", img, off + i + 1)[0]
            dest = lo + i + 5 + rel
            hits.append((lo + i, dest))
        i += 1
    return hits


def main() -> None:
    img, src = load_image()
    print(f"image {src}  {len(img)} B")

    for name, va, n in RANGES:
        print(f"\n==== {name} CALLs ====")
        for site, dest in find_calls(img, va, va + n):
            print(f"  {site:#08x} -> {dest:#08x}")
        dump_asm(img, va, n, name)


if __name__ == "__main__":
    main()
