#!/usr/bin/env python3
"""Pin title boot files + music_load_xmi forum1.xmi (not A01 mandate).

Read-only vs PS.EXE / c2_x.bin. Ghidra HTTP down — Capstone + strings.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000
VA_INTRO = 0x10279
VA_XMI = 0x1028D
VA_TITLE = 0x1029E
STR_INTRO = 0x901DC
STR_FORUM1 = 0x901E6
RAW_BANK = 0x93694


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def main() -> int:
    img, src = load_image()
    print(f"image {src} len={len(img)}")
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    print("==== c2_main intro.smk + forum1.xmi + title_screen ====")
    for insn in dec.disasm(img[0x10279 - BASE : 0x102A3 - BASE], 0x10279):
        print(
            f"  {insn.address:08x}  {insn.bytes.hex():22s} "
            f"{insn.mnemonic:8s} {insn.op_str}"
        )
    eax_intro = struct.unpack_from("<I", img, 0x10279 - BASE + 1)[0]
    eax_xmi = struct.unpack_from("<I", img, 0x10288 - BASE + 1)[0]
    print(f"intro.smk ptr {eax_intro:#x} (want {STR_INTRO:#x})")
    print(f"forum1.xmi ptr {eax_xmi:#x} (want {STR_FORUM1:#x})")
    print(f"raw bank[0] {img[RAW_BANK - BASE : RAW_BANK - BASE + 8]!r}")
    print("A01.RAW is bank index 0 = Career mandate VO, not this boot chain")

    from app.title import selftest

    print("\n==== host title selftest ====")
    failed = 0
    for line in selftest():
        print(f"  {line}")
        if "FAIL" in line:
            failed += 1
    from app.audio import selftest as audio_selftest

    print("\n==== host audio (title plan) ====")
    for line in audio_selftest():
        if "title" in line.lower() or "forum1" in line.lower() or "A01" in line:
            print(f"  {line}")
            if "FAIL" in line:
                failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
