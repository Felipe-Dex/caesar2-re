#!/usr/bin/env python3
"""Pin construction debit: allow treasury < 0, then [97] No Denarii!."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.assets import load_eng
from app.config import resolve_game_dir
from tools.ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000
TREASURY = 0x102AAC
CONSTRUCT_YTD = 0x102A2C
BROKE_LEFT = 0x102A6C


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_asm(img: bytes, va: int, nbytes: int, title: str) -> None:
    off = va - BASE
    if off < 0 or off >= len(img):
        print(f"!! {title} {va:#x} out of range")
        return
    code = img[off : off + nbytes]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print(f"\n==== {title} {va:#x}..{va + nbytes:#x} ====")
    n = 0
    for insn in dec.disasm(code, va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")
        n += 1
        if n >= 240:
            print("  ...")
            break


def find_imm(img: bytes, value: int, lo: int = 0x10000, hi: int = 0xA0000) -> list[int]:
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


def main() -> None:
    game, _ = resolve_game_dir()
    eng = load_eng(game)
    print("==== C2.ENG [97] No Denarii / Stern ====")
    for skip in range(0, 12):
        print(f"  +{skip:2d}  {eng.skip(97, skip)!r}")
    print("\n==== C2.ENG [98] Stern Warning ====")
    for skip in range(0, 8):
        print(f"  +{skip:2d}  {eng.skip(98, skip)!r}")
    print("\n==== C2.ENG [28] Treasurer 12..28 ====")
    for skip in range(12, 29):
        print(f"  +{skip:2d}  {eng.skip(28, skip)!r}")

    img, src = load_image()
    print(f"\nimage {src} len={len(img)}")

    for name, va, n in (
        ("clip_28cd0", 0x28CD0, 0x50),
        ("place_debit_2f380", 0x2F380, 0x90),
        ("debit_30ae0", 0x30AE0, 0x50),
        ("refund_33ee0", 0x33EE0, 0x70),
        ("cal_3fc50", 0x3FC50, 0x50),
        ("hud_618c0", 0x618C0, 0x90),
        ("treas_funds_5d520", 0x5D520, 0x60),
    ):
        dump_asm(img, va, n, name)

    print("\n==== callers of 0x54dc5 ====")
    hits = []
    off = 0
    span = min(len(img), 0x80000)
    while off < span - 4:
        if img[off] == 0xE8:
            rel = struct.unpack_from("<i", img, off + 1)[0]
            if BASE + off + 5 + rel == 0x54DC5:
                hits.append(BASE + off)
        off += 1
    print([hex(v) for v in hits])

    print("\n==== 0x102AAC (treasury) insn sites ====")
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    for va in find_imm(img, TREASURY):
        start = max(BASE, va - 8)
        code = img[start - BASE : start - BASE + 28]
        for insn in dec.disasm(code, start):
            if TREASURY.to_bytes(4, "little") in insn.bytes:
                print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")

    print("\n==== 0x102A2C (construct_ytd) insn sites ====")
    for va in find_imm(img, CONSTRUCT_YTD):
        start = max(BASE, va - 8)
        code = img[start - BASE : start - BASE + 28]
        for insn in dec.disasm(code, start):
            if CONSTRUCT_YTD.to_bytes(4, "little") in insn.bytes:
                print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")

    print("\n==== 0x102A6C (broke_left) insn sites ====")
    for va in find_imm(img, BROKE_LEFT):
        start = max(BASE, va - 8)
        code = img[start - BASE : start - BASE + 28]
        for insn in dec.disasm(code, start):
            if BROKE_LEFT.to_bytes(4, "little") in insn.bytes:
                print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")

    print("\n==== mov eax, 0x62 ([97]+1 official) / 0x63 [98] ====")
    for val in (0x62, 0x63, 0x61):
        pat = bytes([0xB8]) + struct.pack("<I", val)
        off = 0
        n = 0
        while True:
            i = img.find(pat, off)
            if i < 0:
                break
            va = BASE + i
            print(f"  mov eax,{val:#x} @{va:#x}")
            dump_asm(img, max(BASE, va - 0x20), 0x50, f"eax={val:#x}")
            off = i + 1
            n += 1
            if n >= 8:
                break


if __name__ == "__main__":
    main()
