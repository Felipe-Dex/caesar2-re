#!/usr/bin/env python3
"""Oracle advice conditions at 0x574xx + click 0x343c3."""

from __future__ import annotations

import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
OUT = ROOT / "notes" / "_forum_oracle_cond.txt"


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
        if n >= 280:
            lines.append("  ...")
            break
    return lines


def main() -> None:
    L: list[str] = []
    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    L.extend(disasm(mapped, 0x573E0, 0x280))
    L.append("")
    L.extend(disasm(mapped, 0x343C3, 0x120))
    L.append("")
    L.extend(disasm(mapped, 0x5E970, 0x80))
    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size})")


if __name__ == "__main__":
    main()
