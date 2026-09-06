#!/usr/bin/env python3
"""Kind-4 draw 0x5e327 + who writes [0x102558]."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
OUT = ROOT / "notes" / "_forum_oracle_pick.txt"


def disasm(mapped, va: int, nbytes: int) -> list[str]:
    off = mapped.va_to_off(va)
    if off is None:
        return [f"!! {va:#x}"]
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
        if n >= 260:
            lines.append("  ...")
            break
    return lines


def main() -> None:
    L: list[str] = []
    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    img = mapped.image
    base = mapped.base

    L.extend(disasm(mapped, 0x5E327, 0x380))
    L.append("")
    L.extend(disasm(mapped, 0x3D754, 0x180))
    L.append("")
    L.extend(disasm(mapped, 0x3D5DA, 0x180))

    L.append("\n===== stores to 0x102558 =====")
    needle = bytes.fromhex("58251000")
    i = 0
    n = 0
    while n < 40:
        j = img.find(needle, i)
        if j < 0:
            break
        ctx = img[max(0, j - 6) : j + 8]
        L.append(f"  {base+j:#x}  {ctx.hex()}")
        i = j + 1
        n += 1

    # kind 1 column click
    L.append("\n===== 0x3d5da already above; also 0x5d4a4 kind1 draw head =====")
    L.extend(disasm(mapped, 0x5D4A4, 0x80))

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size})")


if __name__ == "__main__":
    main()
