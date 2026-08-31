#!/usr/bin/env python3
"""Read-only: Achea province wall pieces + Port 0xEC vs 0xEF.

Does not write the xlsx. Does not copy the SAV.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

SAV = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV")
BIN = Path(r"C:\Users\Felip\caesar2-re\ghidra_work\c2_x.bin")
BASE = 0x10000
CHUNK14_OFF = 178395
MAP_W = 60
REC = 8


def rec(blob: bytes, x: int, y: int) -> bytes:
    return blob[(y * MAP_W + x) * REC : (y * MAP_W + x) * REC + REC]


def hx(b: bytes) -> str:
    return " ".join(f"{v:02X}" for v in b)


def dump_lut(img: bytes, va: int, nrows: int, title: str) -> None:
    off = va - BASE
    print(f"=== {title} @ {va:#x}  {nrows} rows x 12 ===")
    print("  i  N NE  E SE  S SW  W NW | +8 +9 +A +B   id-10")
    ids = []
    for i in range(nrows):
        row = img[off + i * 12 : off + i * 12 + 12]
        neigh = " ".join(f"{b:2d}" for b in row[:8])
        print(
            f"  {i:2d} {neigh} | {row[8]:02X} {row[9]:02X} {row[10]:02X} {row[11]:02X}"
            f"   {(row[8] - 10) & 0xFF:02X}"
        )
        ids.append(row[8])
    print(f"  unique +8: {[hex(x) for x in sorted(set(ids))]}")
    print(f"  unique id-10: {[hex((x - 10) & 0xFF) for x in sorted(set(ids))]}")
    print()


def main() -> None:
    blob = SAV.read_bytes()[CHUNK14_OFF : CHUNK14_OFF + 28800]
    assert len(blob) == 28800
    img = BIN.read_bytes()

    dump_lut(img, 0x94BAF, 14, "wall pieces (no-pad, FUN_000687eb)")
    dump_lut(img, 0x94D77, 2, "wall GATE -> 0xB6")
    dump_lut(img, 0x94C57, 16, "fort -> 0xD2")

    off = 0x94F90 - BASE
    print("=== +4 LUT 0x94F90 selected indexes ===")
    for i in range(0xB0, 0xD0):
        print(f"  [{i:02X}] = {img[off + i]:02X}")
    print()

    # scan for MOV r32, imm32 of 0xEC / 0xEF / 0xB6 near province
    print("=== imm32 0x000000EC / EF / B6 / BE / BF in image (first 40 each) ===")
    needles = {
        "EC": bytes([0xEC, 0, 0, 0]),
        "EF": bytes([0xEF, 0, 0, 0]),
        "B6": bytes([0xB6, 0, 0, 0]),
        "BE": bytes([0xBE, 0, 0, 0]),
        "BF": bytes([0xBF, 0, 0, 0]),
        "ED": bytes([0xED, 0, 0, 0]),
        "EE": bytes([0xEE, 0, 0, 0]),
    }
    for name, pat in needles.items():
        hits = []
        start = 0
        while True:
            i = img.find(pat, start)
            if i < 0:
                break
            va = i + BASE
            # likely code if previous byte is B8/BA/B9/BB (mov r32,imm32) or C6
            prev = img[i - 1] if i else 0
            hits.append((va, prev))
            start = i + 1
        movs = [(va, p) for va, p in hits if p in (0xB8, 0xBA, 0xB9, 0xBB, 0x68)]
        print(f"  {name}: {len(hits)} raw, {len(movs)} after MOV/PUSH")
        for va, p in movs[:20]:
            print(f"    {va:#08x} prev={p:02X}")

    print()
    print("=== C6 MOV r/m8, imm8 of EC/EF (modrm+imm) sample ===")
    for imm in (0xEC, 0xEF, 0xB6, 0xBE, 0xBF, 0xED, 0xEE):
        # C6 80 xx xx xx xx IMM  or C6 40 xx IMM
        count = 0
        for i in range(len(img) - 2):
            if img[i] == 0xC6 and img[i + 1] in (0x00, 0x40, 0x80, 0xC0) and False:
                pass
        # simpler: C6 ?? ?? IMM where last is our byte and opcode is C6
        found = []
        i = 0
        while i < len(img) - 6:
            if img[i] == 0xC6:
                # C6 /0  — several encodings
                # C6 80 disp32 imm8
                if img[i + 1] == 0x80 and img[i + 6] == imm:
                    va = i + BASE
                    disp = int.from_bytes(img[i + 2 : i + 6], "little")
                    found.append((va, f"C6 80 disp={disp:#x}"))
                elif img[i + 1] == 0x40 and img[i + 3] == imm:
                    found.append((i + BASE, f"C6 40 {img[i+2]:02X}"))
                elif img[i + 1] == 0x00 and img[i + 2] == imm:
                    found.append((i + BASE, "C6 00"))
            i += 1
        print(f"  {imm:02X}: {len(found)}")
        for va, note in found[:15]:
            print(f"    {va:#08x} {note}")

    print()
    # wider water around ports
    print("=== 8x8 around each port origin (byte0) ===")
    origins = [(16, 24, 0xEC), (33, 37, 0xEC), (27, 39, 0xEC), (17, 43, 0xEC), (13, 36, 0xEF)]
    for ox, oy, expect in origins:
        print(f"-- ({ox},{oy}) {expect:#04x} --")
        for y in range(oy - 3, oy + 5):
            row = []
            for x in range(ox - 3, ox + 5):
                if 0 <= x < 60 and 0 <= y < 60:
                    tid = rec(blob, x, y)[0]
                    mark = "*" if (ox <= x <= ox + 1 and oy <= y <= oy + 1) else " "
                    row.append(f"{mark}{tid:02X}")
                else:
                    row.append(" --")
            print("  ", " ".join(row))

    print()
    print("=== 0x00-0x21 histogram (water-ish candidates) ===")
    c = Counter()
    for y in range(60):
        for x in range(60):
            tid = rec(blob, x, y)[0]
            if tid <= 0x21:
                c[tid] += 1
    for tid in range(0x22):
        if c[tid]:
            print(f"  {tid:02X}: {c[tid]}")


if __name__ == "__main__":
    main()
