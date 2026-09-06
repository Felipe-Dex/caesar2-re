#!/usr/bin/env python3
"""Kind-4 oracle advice + HELP topic id = pid+0x47c."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.extract_eng import u32
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
OUT = ROOT / "notes" / "_forum_pickers2.txt"


def disasm(mapped, va: int, nbytes: int) -> list[str]:
    off = mapped.va_to_off(va)
    if off is None:
        return [f"!! {va:#x} unmapped"]
    code = bytes(mapped.image[off : off + nbytes])
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    lines = [f"==== {va:#x} ({nbytes:#x} B) ===="]
    n = 0
    for insn in dec.disasm(code, va):
        lines.append(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= 240:
            lines.append("  ...")
            break
    return lines


def find_calls_to(mapped, dest: int, lo: int = 0x10000, hi: int = 0x90000) -> list[int]:
    img = mapped.image
    start = mapped.va_to_off(lo) or 0
    end = mapped.va_to_off(hi) or len(img)
    base = mapped.base
    out = []
    i = start
    while i < end - 5:
        if img[i] == 0xE8:
            rel = struct.unpack_from("<i", img, i + 1)[0]
            if base + i + 5 + rel == dest:
                out.append(base + i)
        i += 1
    return out


def main() -> None:
    L: list[str] = []
    w = L.append
    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    helpb = (GAME / "HELP.ENG").read_bytes()

    # HELP record layout at flavor0 xref
    flavor0 = helpb.find(b"Thanks to our recent campaigns")
    xref0 = helpb.find(struct.pack("<I", flavor0))
    roads = helpb.find(b"All roads lead here")
    xref_r = helpb.find(struct.pack("<I", roads))
    w(f"roads xref {xref_r} flavor0 xref {xref0} recsz {xref0-xref_r}")
    w("record hex (roads, 58 B): " + helpb[xref_r : xref_r + 58].hex())
    w("record hex (flavor0, 58 B): " + helpb[xref0 : xref0 + 58].hex())
    w("record hex (germania, 58 B): " + helpb[68506 : 68506 + 58].hex())

    # interpret 58-byte record
    def rec(off: int, label: str) -> None:
        if off < 0 or off + 58 > len(helpb):
            return
        words = [u32(helpb, off + 4 * i) for i in range(14)]
        w(f"  {label} @{off} u32s={words}")

    rec(xref_r, "roads")
    rec(xref0, "flavor0")
    rec(68506, "germania")
    rec(67578, "achaea")

    # topic id hunt: 1148+pid = 0x47c+pid
    # if skip 0 Latium -> topic 1148; skip 32 Germania -> 1180
    w("\n===== search HELP for topic ids 1148..1192 as u16/u32 =====")
    for tid in (1148, 1149, 1164, 1180, 0x47c, 0x47c + 16, 0x47c + 32):
        n32 = helpb.find(struct.pack("<I", tid))
        n16 = helpb.find(struct.pack("<H", tid))
        w(f"  tid {tid} u32@{n32} u16@{n16}")

    # 0x57b48 HELP draw
    L.extend(disasm(mapped, 0x57B48, 0x200))
    w("\ncalls to 0x57b48:")
    for va in find_calls_to(mapped, 0x57B48)[:30]:
        w(f"  {va:#x}")

    # forum_panel_draw
    L.extend(disasm(mapped, 0x33B73, 0x280))
    L.extend(disasm(mapped, 0x33B06, 0x80))

    # kind 4 advice function 0x5f033
    L.extend(disasm(mapped, 0x5F033, 0x200))
    L.extend(disasm(mapped, 0x5E9EB, 0x100))

    # Search EAX=0x20 calls and print 12 insns before
    w("\n===== EAX=0x20 call 0x26f16/27071 context (12 insns) =====")
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    for dest, name in ((0x26F16, "26f16"), (0x27071, "27071")):
        for cva in find_calls_to(mapped, dest):
            off = mapped.va_to_off(cva - 0x28)
            if off is None:
                continue
            chunk = bytes(mapped.image[off : off + 0x28])
            if b"\xb8\x20\x00\x00\x00" not in chunk:
                continue
            w(f"  -- {cva:#x} {name} --")
            for insn in dec.disasm(chunk, cva - 0x28):
                w(f"     {insn.address:08x}  {insn.mnemonic:8s} {insn.op_str}")

    # Search computed skip: look for add edx, 8 / lea edx, [reg+8] near forum
    img = mapped.image
    base = mapped.base
    w("\n===== add edx, 8  (83 c2 08) in 0x5e000-0x5f800 =====")
    start = mapped.va_to_off(0x5E000) or 0
    end = mapped.va_to_off(0x5F800) or 0
    i = start
    while i < end:
        if img[i : i + 3] == bytes([0x83, 0xC2, 0x08]):
            w(f"  {base+i:#x}")
        if img[i : i + 3] == bytes([0x83, 0xC2, 0x07]):
            w(f"  {base+i:#x} add edx,7")
        i += 1

    # rating click: xrefs to 0x102530 (empire rating)
    w("\n===== disp 0x102530 / 574 / 538 / 52c =====")
    for va, name in (
        (0x102530, "empire"),
        (0x102574, "peace"),
        (0x102538, "prosperity"),
        (0x10252C, "culture"),
    ):
        needle = struct.pack("<I", va)
        n = 0
        i = 0
        hits = []
        while n < 25:
            j = img.find(needle, i)
            if j < 0:
                break
            hits.append(base + j)
            i = j + 1
            n += 1
        w(f"  {name} {va:#x}: " + ", ".join(f"{h:#x}" for h in hits))

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size})")


if __name__ == "__main__":
    main()
