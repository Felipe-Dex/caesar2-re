#!/usr/bin/env python3
"""Capstone listing of walkers_tick type/state stubs (not Ghidra functions).

Reads the mapped LE image. Does not copy PS.EXE into the repo.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000

# Type stubs + state stubs through the last known state (12 @ 0x468FE).
RANGES = [
    ("walker_type_fn table", 0x99D24, 8 * 4),
    ("walker_state_fn table", 0x99D68, 16 * 4),
    ("type-speed 0x96735", 0x96735, 16),
    ("type-speed 0x9673E", 0x9673E, 16),
    ("type1..actors26_t1", 0x45AFE, 0x45D8F - 0x45AFE),
    ("walker states 0..12+", 0x45EDC, 0x46B00 - 0x45EDC),
]

TYPE_LABELS = {
    0x45AFE: "TYPE1",
    0x45B53: "TYPE2",
    0x45BA8: "TYPE3",
    0x45C0E: "TYPE4",
    0x45C63: "TYPE5",
    0x45CB8: "TYPE6",
    0x45D0A: "TYPE7",
}
STATE_LABELS = {
    0x45EDC: "STATE0",
    0x45EDD: "STATE1",
    0x45F2C: "STATE2",
    0x45F38: "STATE3",
    0x45FE9: "STATE4",
    0x46155: "STATE5?",
}


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_table(img: bytes, va: int, nbytes: int, title: str) -> None:
    off = va - BASE
    print(f"\n==== {title} @ {va:#x} ====")
    for i in range(0, nbytes, 4):
        if off + i + 4 > len(img):
            break
        val = struct.unpack_from("<I", img, off + i)[0]
        print(f"  [{i // 4:2d}] {va + i:#08x} = {val:#08x}")


def dump_bytes(img: bytes, va: int, nbytes: int, title: str) -> None:
    off = va - BASE
    raw = img[off : off + nbytes]
    print(f"\n==== {title} @ {va:#x} ({nbytes} B) ====")
    print(" ", raw.hex())


def dump_asm(img: bytes, va: int, nbytes: int, title: str) -> None:
    off = va - BASE
    code = img[off : off + nbytes]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print(f"\n==== {title} {va:#x}..{va + nbytes:#x} ====")
    for insn in dec.disasm(code, va):
        lab = TYPE_LABELS.get(insn.address) or STATE_LABELS.get(insn.address) or ""
        if lab:
            print(f"  ---- {lab} ----")
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")


def find_imm_eax(img: bytes, values: tuple[int, ...], lo: int, hi: int) -> None:
    """Hunt `mov eax, imm8/imm32` in [lo, hi)."""
    print(f"\n==== mov eax, {values} in {lo:#x}..{hi:#x} ====")
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    off = lo - BASE
    code = img[off : hi - BASE]
    for insn in dec.disasm(code, lo):
        if insn.mnemonic != "mov":
            continue
        if not insn.op_str.startswith("eax, "):
            continue
        rhs = insn.op_str[5:].strip()
        try:
            n = int(rhs, 0)
        except ValueError:
            continue
        if n in values:
            print(f"  {insn.address:08x}  {insn.mnemonic} {insn.op_str}")


def find_calls_to(img: bytes, target: int, lo: int, hi: int) -> list[int]:
    hits = []
    off = lo - BASE
    i = 0
    span = hi - lo
    while i < span - 4:
        if img[off + i] == 0xE8:
            rel = struct.unpack_from("<i", img, off + i + 1)[0]
            dest = lo + i + 5 + rel
            if dest == target:
                hits.append(lo + i)
        i += 1
    return hits


def main() -> None:
    img, src = load_image()
    print(f"image {src}  {len(img)} B")
    dump_table(img, 0x99D24, 8 * 4, "walker_type_fn")
    dump_table(img, 0x99D68, 16 * 4, "walker_state_fn")
    dump_bytes(img, 0x96735, 16, "speed table 0x96735 (on_road?)")
    dump_bytes(img, 0x9673E, 16, "speed table 0x9673E (off_road?)")
    dump_asm(img, 0x45AFE, 0x45D8F - 0x45AFE, "type handlers 1-7")
    dump_asm(img, 0x45EDC, 0x46B80 - 0x45EDC, "state handlers")

    print("\n==== CALL walker_spawn 0x2A7EF ====")
    for va in find_calls_to(img, 0x2A7EF, 0x10000, 0x80000):
        print(f"  {va:#08x}")
    print("\n==== CALL walker_spawn_retry 0x42236 ====")
    for va in find_calls_to(img, 0x42236, 0x10000, 0x80000):
        print(f"  {va:#08x}")
    print("\n==== CALL walker_find_type3or7 0x47D1A ====")
    for va in find_calls_to(img, 0x47D1A, 0x10000, 0x80000):
        print(f"  {va:#08x}")

    find_imm_eax(img, (3, 7), 0x41000, 0x42500)
    find_imm_eax(img, (3, 7), 0x53000, 0x54200)
    find_imm_eax(img, (3, 7), 0x45AFE, 0x46B80)


if __name__ == "__main__":
    main()
