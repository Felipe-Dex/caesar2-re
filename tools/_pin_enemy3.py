#!/usr/bin/env python3
"""Pin edge picker 0x537ed, rally 0x40c00, smash 0x68c01, year counter."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000


def load_image() -> bytes:
    if BIN.exists():
        return BIN.read_bytes()
    return bytes(map_image(load_ps(DEFAULT_EXE), apply_fixups=True).image)


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 250) -> None:
    off = va - BASE
    code = img[off : off + min(nbytes, max(0, len(img) - off))]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print(f"\n==== {title} {va:#x} ====")
    n = 0
    for insn in dec.disasm(code, va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")
        n += 1
        if n >= limit:
            print("  ...")
            break


def find_imm32(img: bytes, value: int, lo: int = 0x10000, hi: int = 0x80000) -> list[int]:
    pat = struct.pack("<I", value)
    hits = []
    raw = img[lo - BASE : hi - BASE]
    start = 0
    while True:
        i = raw.find(pat, start)
        if i < 0:
            break
        hits.append(lo + i)
        start = i + 1
    return hits


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


def ctx(img: bytes, va: int, before: int = 20, after: int = 24) -> None:
    dump_asm(img, va - before, before + after + 8, f"ctx {va:#x}", limit=40)


def main() -> None:
    img = load_image()
    dump_asm(img, 0x537ED, 0x140, "edge pick 0x537ed", limit=160)
    dump_asm(img, 0x40C00, 0x110, "rally writer 0x40c00", limit=90)
    dump_asm(img, 0x68C01, 0x180, "smash/rect 0x68c01", limit=140)
    dump_asm(img, 0x48C26, 0x80, "state5 fail 0x48c26", limit=50)

    print("\n==== 0x102ac0 / 0x102a78 / 0x102630 / 0xc4578 / 0x117a60 writers ====")
    for name, addr in (
        ("0x102ac0 year?", 0x102AC0),
        ("0x102a78 counter", 0x102A78),
        ("0x102630 rally idx", 0x102630),
        ("0xc4578", 0xC4578),
        ("0x1025a8 peace?", 0x1025A8),
    ):
        hits = find_imm32(img, addr)
        writes = []
        for h in hits:
            # look for mov [addr] nearby
            writes.append(h)
        print(f"  {name} hits={len(hits)} {[hex(h) for h in hits[:20]]}")
        for h in hits[:8]:
            ctx(img, h, 12, 16)

    print("\n==== CALL 0x537ed ====")
    for va in find_calls_to(img, 0x537ED):
        print(f"  {va:#x}")
        ctx(img, va, 16, 12)

    print("\n==== CALL 0x40c00? rally parent ====")
    # function containing 0x40ce6 — dump from a likely prolog
    dump_asm(img, 0x40B80, 0x40, "before rally writer", limit=30)

    # type 3 damage? look at dest_ok wall bit and walker_can_step type
    print("\n==== dest_ok / can_step type3 extras ====")
    dump_asm(img, 0x48470, 0x80, "walker_can_step head", limit=50)
    dump_asm(img, 0x48606, 0xA0, "walker_dest_ok", limit=70)


if __name__ == "__main__":
    main()
