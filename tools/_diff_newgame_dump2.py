#!/usr/bin/env python3
"""Focused disasm: New Game Options store + difficulty tables. Local only."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.extract_eng import parse_textfile
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
NUL = b"\x00"


def packed(data: bytes, start: int, n: int) -> None:
    pos = start
    for i in range(n):
        end = data.find(NUL, pos)
        s = data[pos:end].decode("latin-1")
        print(f"  +{i:3d} {s!r}")
        pos = end + 1


def disasm(mapped, va: int, nbytes: int) -> None:
    off = mapped.va_to_off(va)
    code = bytes(mapped.image[off : off + nbytes])
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    print(f"\n---- {va:#x} +{nbytes:#x} ----")
    for insn in dec.disasm(code, va):
        print(f"  {insn.address:08x}  {insn.mnemonic:8s} {insn.op_str}")


def main() -> None:
    eng = (GAME / "C2.ENG").read_bytes()
    offs, strings, *_ = parse_textfile(eng)
    for slot in (38, 42, 43, 44):
        print(f"\n===== [{slot}] first={strings[slot]!r} =====")
        packed(eng, offs[slot], 12 if slot >= 43 else 32)

    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)

    print("\n===== tables =====")
    for va, n, kind in (
        (0x9621C, 8, "B"),
        (0x96221, 8, "I"),
        (0x96DDB, 24, "I"),
        (0x96ECB, 16, "I"),
        (0x96F1B, 16, "I"),
        (0x96F2F, 8, "I"),
    ):
        off = mapped.va_to_off(va)
        if kind == "B":
            print(f"  {va:#x} bytes: {bytes(mapped.image[off:off+n]).hex()}")
        else:
            vals = struct.unpack_from(f"<{n}i", mapped.image, off)
            print(f"  {va:#x} i32[{n}]: {vals}")

    for va, n in (
        (0x1049B, 0x80),
        (0x10565, 0x120),
        (0x348C0, 0x60),
        (0x52820, 0xA0),
        (0x52EB9, 0x80),
        (0x54EA0, 0x90),
        (0x56750, 0x40),
        (0x56F90, 0x40),
        (0x583C8, 0x40),
        (0x5CF80, 0x80),
        (0x5E000, 0xA0),
        (0x5AFC6, 0x80),
        (0x70580, 0xC0),
        (0x41DD4, 0x40),
    ):
        disasm(mapped, va, n)


if __name__ == "__main__":
    main()
