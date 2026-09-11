#!/usr/bin/env python3
"""Pin 0x537ed edge pick + 0x536E2 type-3 spawn + 0x2A7EF pad-0 reject.

Read-only. Why Disasters→Barbarian vanished: corners are water (+1 0x54
includes FLAG_RIVER 0x10); pad-0 spawn rejects 0x54; host &= 0x24 left
0x04 (still in 0x54). EXE 0x68c01 is +3 &= ~0x40, not a flag wipe.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ps_le import DEFAULT_EXE, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000
OUT = Path(__file__).resolve().parents[1] / "notes" / "_pin_barbarian.txt"


def load_image() -> bytes:
    if BIN.exists():
        return BIN.read_bytes()
    return bytes(map_image(load_ps(DEFAULT_EXE), apply_fixups=True).image)


def dump(img: bytes, va: int, nbytes: int, title: str, limit: int = 80) -> list[str]:
    off = va - BASE
    code = img[off : off + nbytes]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    lines = [f"==== {title} {va:#x} ===="]
    n = 0
    for insn in dec.disasm(code, va):
        lines.append(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} "
            f"{insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= limit:
            break
    return lines


def main() -> None:
    img = load_image()
    lines: list[str] = []
    lines.append("City Only type-3 Enemy — 0x537ed rim / 0x536E2 spawn")
    lines.append("0x536E2: EAX=side EDX=0x50 EBX=0x3F -> 0x537ed")
    lines.append("  [0x117bb0]=x [0x117bb4]=y; +1&0xE7 -> 0x68c01 1x1")
    lines.append("  walker_spawn EAX=3 pad=0; fail → stop (no retry)")
    lines.append("0x2A7EF pad=0: reject +1&0x8B or +1&0x54 (0x54 has river 0x10)")
    lines.append("0x68c01 1×1: +3 &= 0xBF; does not clear 0x54")
    lines.append("Host &=0x24 left 0x04 so still rejected. Corners are water.")
    lines.append("")
    lines.extend(dump(img, 0x536E2, 0xA0, "type3_count", 40))
    lines.append("")
    lines.extend(dump(img, 0x537ED, 0x80, "edge pick head", 28))
    lines.append("")
    lines.extend(dump(img, 0x2A867, 0x40, "spawn pad-0 0x54 reject", 16))
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    sys.stdout.buffer.write(text.encode("utf-8", errors="replace"))
    print(f"wrote {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
