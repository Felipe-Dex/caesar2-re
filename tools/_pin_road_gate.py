#!/usr/bin/env python3
"""Read-only pin: road-on-wall → Gate 0xC0 (mapped PS.EXE / c2_x.bin).

Ghidra HTTP was down. Capstone listing of:
  0x665DF  road flood — +1&0x02 → (+1&0xF9)|0x04, then OR pad 0x20
  0x66B0E  669C6 retile — +1&0x04 → 67201 (before +0>=0x7C skip)
  0x673B9  67201 — pad+0x04 writes +0=0xC0 +3=0x88 +4 LUT 0x94D17

Host: app/place.py selftest (road-on-wall / grass / barracks).
"""

from __future__ import annotations

import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 40) -> None:
    off = va - BASE
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    print(f"\n==== {title} {va:#x} ====")
    n = 0
    for insn in dec.disasm(img[off : off + nbytes], va):
        print(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} "
            f"{insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= limit:
            print("  ...")
            break


def main() -> None:
    img, src = load_image()
    print(f"image {src} len={len(img)}")
    print("DAT_00094FE5[0xC0]=", img[0x94FE5 + 0xC0 - BASE], "(1x1)")
    dump_asm(img, 0x66633, 0x60, "665DF wall +1&0x02 → 0x04, OR pad", 22)
    dump_asm(img, 0x66B0E, 0x40, "669C6 +1&0x04 → 67201 before 0x7C", 16)
    dump_asm(img, 0x673DD, 0x70, "67201 pad+0x04 write Gate 0xC0", 28)
    print(
        "\nEXE rule: road tool on wall (+1 0x02) becomes Gate 0xC0 "
        "+1=0x24 +3=0x88 +4=0x92/0x93. No extra debit (road has no "
        "city-cost slot). Barracks +0>=0x7C still skipped."
    )

    from app.place import selftest as place_selftest
    from app.walker_tick import selftest as walker_selftest

    print("\n=== host place selftest (gate / barracks lines) ===")
    for line in place_selftest():
        if any(
            key in line
            for key in (
                "road-on-wall",
                "Gate 0xC0",
                "grass still road",
                "Barracks 0xE4",
                "estrada recusa",
                "arrasto: estrada",
                "Wall linha",
            )
        ):
            print(" ", line)
            if line.startswith("FAIL"):
                sys.exit(1)
    print("\n=== host walker dest_ok gate ===")
    for line in walker_selftest():
        if "gate" in line.lower() or "forum/plaza" in line:
            print(" ", line)
            if "FAIL" in line:
                sys.exit(1)


if __name__ == "__main__":
    main()
