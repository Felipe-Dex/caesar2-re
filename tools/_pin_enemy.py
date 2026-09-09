#!/usr/bin/env python3
"""Pin City Only type-3 Enemy spawn 0x52828 + march + [82] banner.

Read-only. Retail PS.EXE / mapped c2_x.bin. Not Career actor26 0x53562
except as a contrast (EAX=0x53 banner).
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.assets import load_eng
from app.config import resolve_game_dir

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 400) -> None:
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


def find_imm_eax(img: bytes, value: int, lo: int = 0x10000, hi: int = 0x90000) -> list[int]:
    pat = bytes([0xB8]) + struct.pack("<I", value)
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


def context_around(img: bytes, va: int, before: int = 32, after: int = 40) -> None:
    dump_asm(img, va - before, before + after + 8, f"ctx {va:#x}", limit=80)


def dump_i32s(img: bytes, va: int, n: int, title: str) -> None:
    off = va - BASE
    vals = struct.unpack_from(f"<{n}i", img, off)
    print(f"\n==== {title} {va:#x} i32[{n}] ====")
    print(f"  {vals}")


def main() -> None:
    game, why = resolve_game_dir()
    print(f"game {game} ({why})")
    img, src = load_image()
    print(f"image {src} len={len(img)}")

    eng = load_eng(game)
    print("\n==== C2.ENG [81] [82] [86] [90-95] ====")
    for slot in (81, 82, 86, 90, 91, 92, 93, 94, 95):
        title = eng.skip(slot, 0)
        body = eng.skip(slot, 1)
        print(f"  [{slot}]+0 {title!r}")
        print(f"  [{slot}]+1 {body!r}")

    dat = game / "C2MODEL.DAT"
    if dat.exists():
        data = dat.read_bytes()
        vals = struct.unpack_from("<16i", data, 75 * 4)
        print(f"\n==== C2MODEL [75:91] {dat} ====")
        print(f"  {vals}")
        for skill, name in enumerate(("Novice", "Easy", "Normal", "Hard", "Impossible")):
            row = vals[skill * 3 : skill * 3 + 3] if skill * 3 + 3 <= 16 else vals[skill * 3 :]
            print(f"  skill {skill} {name}: {row}")

    dump_i32s(img, 0x96ECB, 16, "EXE 0x96ECB = C2MODEL[75:91]")

    print("\n==== CALL 0x52828 ====")
    for va in find_calls_to(img, 0x52828):
        print(f"  {va:#x}")
        context_around(img, va, 24, 16)

    print("\n==== CALL walker_spawn_type3_count 0x536E2 ====")
    for va in find_calls_to(img, 0x536E2):
        print(f"  {va:#x}")
        context_around(img, va, 40, 24)

    print("\n==== CALL walker_spawn 0x2A7EF in 0x52800-0x53800 ====")
    for va in find_calls_to(img, 0x2A7EF, 0x52800, 0x53880):
        print(f"  {va:#x}")
        context_around(img, va, 48, 32)

    print("\n==== CALL FUN_00058c87 0x58C87 in 0x52800-0x53800 ====")
    for va in find_calls_to(img, 0x58C87, 0x52800, 0x53880):
        print(f"  {va:#x}")
        context_around(img, va, 32, 20)

    print("\n==== mov eax, 0x53 (banner [82]) ====")
    for va in find_imm_eax(img, 0x53):
        if 0x40000 <= va <= 0x60000:
            print(f"  {va:#x}")
            context_around(img, va, 16, 28)

    print("\n==== imm32 0x102628 / 0x10262C (rally) 0x45000-0x54000 ====")
    for name, addr in (("rally_y 0x102628", 0x102628), ("rally_x 0x10262C", 0x10262C)):
        hits = [h for h in find_imm32(img, addr, 0x45000, 0x54000)]
        print(f"  {name}: {[hex(h) for h in hits]}")
        for h in hits[:12]:
            context_around(img, h, 20, 20)

    dump_asm(img, 0x52828, 0x180, "FUN_00052828 City Only type3", limit=220)
    dump_asm(img, 0x536E2, 0x120, "walker_spawn_type3_count", limit=160)
    dump_asm(img, 0x45BA8, 0x70, "type3 handler", limit=50)
    dump_asm(img, 0x46155, 0xA0, "state 5 barbarian march", limit=80)

    print("\n==== CALL 0x3FCA0 economy_recompute ====")
    for va in find_calls_to(img, 0x3FCA0)[:20]:
        print(f"  {va:#x}")

    # city_only flag [0x9CE81] hits near 0x52828
    print("\n==== imm32 0x9CE81 (chunk 406) near 0x52700-0x52A00 ====")
    for h in find_imm32(img, 0x9CE81, 0x52700, 0x52B00):
        print(f"  {h:#x}")
        context_around(img, h, 16, 20)


if __name__ == "__main__":
    main()
