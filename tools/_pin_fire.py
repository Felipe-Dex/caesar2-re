#!/usr/bin/env python3
"""Pin 0x69A37 ignite + 41DD4 fire slice + flag80 / vigile / path-fail.

Read-only. Retail PS.EXE / mapped c2_x.bin.
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


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 220) -> None:
    off = va - BASE
    if off < 0 or off >= len(img):
        print(f"!! {title} {va:#x} out of range")
        return
    code = img[off : off + min(nbytes, max(0, len(img) - off))]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print(f"\n==== {title} {va:#x}..{va + nbytes:#x} ====")
    n = 0
    for insn in dec.disasm(code, va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")
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

    print("\n==== CALLS to 0x69A37 ignite ====")
    cs = find_calls_to(img, 0x69A37)
    print("  " + " ".join(f"{c:#x}" for c in cs[:24]) + (f"  (+{len(cs)-24})" if len(cs) > 24 else ""))

    dump_asm(img, 0x69A37, 0x80, "FUN_00069a37 ignite", limit=80)
    dump_asm(img, 0x69334, 0x90, "FUN_00069334 spread", limit=80)
    dump_asm(img, 0x693BB, 0x60, "693BB after climb / footprint ignite", limit=50)
    dump_asm(img, 0x691C4, 0x80, "FUN_000691c4 collapse", limit=70)
    dump_asm(img, 0x696E8, 0xA0, "FUN_000696e8 terrain rng", limit=90)
    dump_asm(img, 0x41DD4, 0x200, "41DD4 fire + unrest head", limit=180)
    dump_asm(img, 0x37E0F, 0x1C0, "city_tile_draw_flag80 0x37E0F", limit=160)
    dump_asm(img, 0x4A397, 0x80, "4A397 sector fire", limit=60)
    dump_asm(img, 0x4A57F, 0x80, "4A57F pick fire dest", limit=60)
    dump_asm(img, 0x4A716, 0x60, "4A716 extinguish", limit=40)
    dump_asm(img, 0x4A76D, 0x40, "4A76D still on target", limit=30)
    dump_asm(img, 0x2B54A, 0x80, "2B54A path-fail leftover", limit=50)
    dump_asm(img, 0x2BA63, 0x80, "2BA63 path-fail leftover", limit=50)


if __name__ == "__main__":
    main()
