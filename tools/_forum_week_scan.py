#!/usr/bin/env python3
"""Scan mapped PS.EXE for Forum stores, overlay table, Week blit indices."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.extract_eng import parse_textfile
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")


def find_all(blob: bytes, needle: bytes) -> list[int]:
    out = []
    i = 0
    while True:
        j = blob.find(needle, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def main() -> None:
    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    img = mapped.image
    base = mapped.base
    print(f"mapped image {len(img)} base {base:#x}")

    def va_of(off: int) -> int:
        return base + off

    # Search relocated immediates
    patterns = {
        "mov_submode_imm": bytes.fromhex("C705A42A1000"),
        "mov_overlay_imm": bytes.fromhex("C605597A1100"),
        "mov_al_overlay": bytes.fromhex("A2597A1100"),
        "mov_submode_eax": bytes.fromhex("A3A42A1000"),
    }
    print("\n=== relocated stores ===")
    for name, pat in patterns.items():
        hits = find_all(img, pat)
        print(f"  {name}: {len(hits)} hits")
        for h in hits[:20]:
            extra = ""
            if name == "mov_submode_imm" and h + 10 <= len(img):
                extra = f" imm={struct.unpack_from('<I', img, h+6)[0]}"
            if name == "mov_overlay_imm" and h + 7 <= len(img):
                extra = f" imm={img[h+6]}"
            print(f"    {va_of(h):#x}{extra}")

    # Any 59 7A 11 00 (overlay VA as disp32)
    print("\n=== disp32 0x117A59 ===")
    for h in find_all(img, bytes.fromhex("597A1100"))[:40]:
        ctx = img[max(0, h - 3) : h + 8]
        print(f"  {va_of(h):#x}  {ctx.hex()}")

    print("\n=== disp32 0x102AA4 ===")
    for h in find_all(img, bytes.fromhex("A42A1000"))[:50]:
        ctx = img[max(0, h - 3) : h + 8]
        print(f"  {va_of(h):#x}  {ctx.hex()}")

    print("\n=== CALL rel32 to key funcs (code 0x10000-0x80000) ===")
    start = mapped.va_to_off(0x10000) or 0
    end = mapped.va_to_off(0x80000) or len(img)
    wanted = {0x58D31: "58d31", 0x33D21: "33d21", 0x59A15: "forum_view", 0x54DC5: "54dc5"}
    found: dict[str, list[int]] = {n: [] for n in wanted.values()}
    i = start
    while i < end - 5:
        if img[i] == 0xE8:
            rel = struct.unpack_from("<i", img, i + 1)[0]
            dest = va_of(i) + 5 + rel
            name = wanted.get(dest)
            if name:
                found[name].append(va_of(i))
        i += 1
    for name, hits in found.items():
        print(f"  {name}: {hits}")

    print("\n=== dword pointers to key VAs in 0x28000-0x2A000 ===")
    targets = {
        0x58D31: "FUN_58d31",
        0x33D21: "FUN_33d21",
        0x59A15: "forum_view",
        0x54DC5: "FUN_54dc5",
        0x338F9: "FUN_338f9",
        0x289B2: "289b2",
        0x28920: "28920",
    }
    # scan data-ish
    for va_start, va_end in ((0x28000, 0x2C000), (0x98000, 0x9C000)):
        off0 = mapped.va_to_off(va_start)
        if off0 is None:
            continue
        span = va_end - va_start
        chunk = img[off0 : off0 + span]
        for t, name in targets.items():
            b = struct.pack("<I", t)
            for h in find_all(chunk, b):
                print(f"  {va_start + h:#x} -> {name} ({t:#x})")

    print("\n=== overlay table 0x99b3c ===")
    off = mapped.va_to_off(0x99B3C)
    if off:
        for i in range(16):
            ptr = struct.unpack_from("<I", img, off + i * 4)[0]
            print(f"  [{i:2d}] {ptr:#08x}")

    print("\n=== table 0x28650 ===")
    off = mapped.va_to_off(0x28650)
    if off:
        for i in range(24):
            ptr = struct.unpack_from("<I", img, off + i * 4)[0]
            print(f"  [{i:2d}] {ptr:#08x}")

    # Week: EXE index 0x1C = slot 27 Week 1
    print("\n=== MOV EAX, 0x1C / 0x19 near likely blit ===")
    for imm, label in ((0x1C, "Week1 slot+1"), (0x19, "January+1"), (0x35, "overlay+1")):
        pat = bytes([0xB8, imm, 0, 0, 0])  # mov eax, imm32
        hits = find_all(img, pat)
        print(f"  {label}: {len(hits)} mov eax")
        for h in hits[:15]:
            print(f"    {va_of(h):#x}")

    eng = (GAME / "C2.ENG").read_bytes()
    _off, strings, _pad, _unique = parse_textfile(eng)
    print("\n=== packed from Treasury slot 29 ===")
    start = _off[29]
    pos = start
    for n in range(20):
        end = eng.find(b"\x00", pos)
        print(f"  skip {n:2d}  {eng[pos:end].decode('latin-1')!r}")
        pos = end + 1

    print("\n=== packed from slot 30 career ===")
    start = _off[30]
    pos = start
    for n in range(12):
        end = eng.find(b"\x00", pos)
        print(f"  skip {n:2d}  {eng[pos:end].decode('latin-1')!r}")
        pos = end + 1


if __name__ == "__main__":
    main()
