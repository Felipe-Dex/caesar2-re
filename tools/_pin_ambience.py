#!/usr/bin/env python3
"""Pin city SFX proximity mixer (dog = gardenb, gardens only).

Read-only vs PS.EXE / c2_x.bin. Also prints host selftest lines.
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
    print("dog wav: gardenb.wav (no dog/bark/wolf stem in EXE)")
    print("slot 1 names @ 0xa4008 / 0xa4018 / 0xa4028 = gardenb/c/d")
    print("mapper 0x12A8F: 0x78-0x7B -> slot 1; 0x82-0xA1 -> none")
    print("mixer 0x12E1E from view_frame 0x3D3D5; thresh 0xC8; play 0x11B7B")
    print("bind 0x12F2A copies names only (enter_view_mode 0x336E3)")
    for dest, name in (
        (0x12A8F, "tile_to_slot"),
        (0x12E1E, "mixer_tick"),
        (0x11B7B, "sfx_play_name"),
    ):
        cs = find_calls_to(img, dest)
        print(f"  calls {name} {dest:#x}: {[hex(c) for c in cs[:8]]}")
    dump_asm(img, 0x12A8F, 0x40, "tile_to_slot head (garden / plaza / housing)", 20)
    dump_asm(img, 0x12E1E, 0x50, "mixer_tick head", 25)
    dump_asm(img, 0x3746E, 0x20, "city tile draw -> mapper", 12)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.audio import selftest

    print("\n==== host audio selftest ====")
    game = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
    for line in selftest(game if game.is_dir() else None):
        print("  " + line)


if __name__ == "__main__":
    main()
