#!/usr/bin/env python3
"""Capstone listing of city_sim_phase + housing evolve (Ghidra HTTP down).

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
    ("city_sim_phase", 0x3F60C, 0x3FB38 - 0x3F60C),
    ("calendar_advance", 0x3FBCF, 0x3FD3E - 0x3FBCF),
    ("city_buildings_evolve_row", 0x42360, 0x42B2D - 0x42360),
    ("house_evolve_down", 0x42B2D, 0x42B75 - 0x42B2D),
    ("house_evolve_up", 0x42B75, 0x42BC4 - 0x42B75),
    ("house_pick_block", 0x42BC4, 0x42C7F - 0x42BC4),
    ("house_try_2x2", 0x42C7F, 0x42D0D - 0x42C7F),
    ("house_try_3x3", 0x42D0D, 0x42E25 - 0x42D0D),
    ("house_stamp", 0x42E25, 0x42F71 - 0x42E25),
    ("house_split_villa", 0x42F71, 0x4308B - 0x42F71),
    ("block_lv_scan", 0x6DB08, 0x80),
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


def dump_bytes(img: bytes, va: int, nbytes: int, title: str) -> None:
    off = va - BASE
    raw = img[off : off + nbytes]
    print(f"\n==== {title} @ {va:#x} ({nbytes} B) ====")
    for i in range(0, len(raw), 16):
        chunk = raw[i : i + 16]
        print(f"  {va + i:08x}  {chunk.hex()}")


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


def i8(b: int) -> int:
    return b - 256 if b >= 128 else b


def main() -> None:
    img, src = load_image()
    print(f"image {src}  {len(img)} B")

    dump_bytes(img, 0x96235, 64, "evolve stay 0x96235")
    dump_bytes(img, 0x94F3C, 32 * 4 + 8, "gfx/size 0x94F3C")
    dump_bytes(img, 0x9422C, 16, "stamp addends 0x9422C")
    dump_bytes(img, 0x99B64, 48, "neighbor LUT 0x99B64")
    dump_bytes(img, 0x99B94, 48, "neighbor LUT 0x99B94")

    print("\n==== gfx/size decoded ====")
    for g in range(32):
        rec = img[0x94F3F - BASE + g * 4 : 0x94F3F - BASE + g * 4 + 4]
        sz_dword = struct.unpack_from("<i", img, 0x94F40 - BASE + g * 4)[0]
        print(
            f"  g{g:02d} id=0x{0x82+g:02X} rec={rec.hex()} gfx={rec[0]} "
            f"b1={rec[1]} dword@94F40={sz_dword}"
        )

    print("\n==== city_sim_phase CALLs ====")
    for site, dest in find_calls(img, 0x3F60C, 0x3FB38):
        print(f"  {site:#08x} -> {dest:#08x}")

    print("\n==== evolve_row CALLs ====")
    for site, dest in find_calls(img, 0x42360, 0x42B2D):
        print(f"  {site:#08x} -> {dest:#08x}")

    print("\n==== up/merge CALLs ====")
    for name, lo, n in RANGES[3:]:
        print(f"  -- {name} --")
        for site, dest in find_calls(img, lo, lo + n):
            print(f"    {site:#08x} -> {dest:#08x}")

    for name, va, n in RANGES:
        dump_asm(img, va, n, name)


if __name__ == "__main__":
    main()
