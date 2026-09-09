#!/usr/bin/env python3
"""Pin FUN_00052828 body + type3_count edge pick + rally writers + 0x68c01."""

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


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 400) -> None:
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
    pat = struct.pack("<I", value)
    hits = []
    off = lo - BASE
    raw = img[off : off + (hi - lo)]
    start = 0
    while True:
        i = raw.find(pat, start)
        if i < 0:
            break
        hits.append(lo + i)
        start = i + 1
    return hits


def ctx(img: bytes, va: int, before: int = 24, after: int = 32) -> None:
    dump_asm(img, va - before, before + after + 8, f"ctx {va:#x}", limit=60)


def main() -> None:
    img = load_image()

    dump_asm(img, 0x52828, 0xA0, "FUN_00052828 full", limit=120)
    dump_asm(img, 0x536E2, 0x80, "type3_count head (edge pick)", limit=80)

    print("\n==== writers of 0x102628 / 0x10262C (all code) ====")
    for name, addr in (("0x102628", 0x102628), ("0x10262C", 0x10262C)):
        hits = find_imm32(img, addr, 0x10000, 0x80000)
        print(f"  {name} hits={len(hits)}")
        for h in hits:
            # skip the type3_count / state5 reads we already know
            print(f"    {h:#x}")
            ctx(img, h, 16, 20)

    print("\n==== CALL 0x68c01 (spawn tile helper) ====")
    for va in find_calls_to(img, 0x68C01):
        if 0x53000 <= va <= 0x53880 or 0x45B00 <= va <= 0x46900:
            print(f"  {va:#x}")
            ctx(img, va, 20, 12)

    dump_asm(img, 0x68C01, 0x80, "FUN_00068c01", limit=70)

    print("\n==== [0x117bb0] [0x117bb4] writers ====")
    for name, addr in (("[0x117bb0]", 0x117BB0), ("[0x117bb4]", 0x117BB4)):
        hits = find_imm32(img, addr, 0x10000, 0x80000)
        print(f"  {name} {len(hits)} hits")
        for h in hits[:16]:
            print(f"    {h:#x}")
            ctx(img, h, 12, 16)

    print("\n==== CALL 0x48c26 from state 5 fail ====")
    dump_asm(img, 0x48C26, 0x80, "FUN_00048c26", limit=50)

    # 0x3fca0 wrap — who calls 52828
    dump_asm(img, 0x3FCA0, 0x60, "economy_recompute head", limit=40)
    dump_asm(img, 0x3FC55, 0x50, "caller of 3fca0 / 52828", limit=40)


if __name__ == "__main__":
    main()
