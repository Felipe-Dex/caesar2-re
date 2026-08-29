#!/usr/bin/env python3
"""Dump the PS.EXE save-chunk table and related I/O helpers."""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

from ps_le import DEFAULT_EXE, file_offset_of_va, load_ps, map_image, xrefs_to_va


def u32(mapped, va: int) -> int:
    return struct.unpack_from("<I", mapped.image, mapped.va_to_off(va))[0]


def cstr(mapped, va: int) -> str:
    off = mapped.va_to_off(va)
    if off is None:
        return "?"
    end = bytes(mapped.image).find(b"\x00", off)
    return bytes(mapped.image)[off:end].decode("latin-1", errors="replace")


def disasm(mapped, va: int, n: int = 40) -> None:
    off = mapped.va_to_off(va)
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    print(f"---- {va:#x} file {file_offset_of_va(mapped, va)} ----")
    k = 0
    for insn in dec.disasm(bytes(mapped.image[off : off + n * 8]), va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():20s} {insn.mnemonic:8s} {insn.op_str}")
        k += 1
        if k >= n:
            break


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    args = ap.parse_args(argv)
    ps = load_ps(args.exe)
    mapped = map_image(ps)
    img = bytes(mapped.image)

    print("=== save chunk table @ 0x9ABC0 (500 x {ptr,size}, first zero size ends) ===")
    print("  sav_write 0x70174 uses write 0x7A995; sav_read 0x7024A uses read 0x77B37")
    print("  after the loop both also copy 4000 B via [0xC4D10] (HISTORY.DAT size)")
    base = 0x9ABC0
    running = 0
    rows = []
    for i in range(500):
        ptr = u32(mapped, base + i * 8)
        size = u32(mapped, base + i * 8 + 4)
        if size == 0:
            print(f"  [{i:3d}] size=0  (end)  cum={running}")
            break
        running += size
        note = ""
        if size == 6400:
            note = "80x80"
        elif size % 6400 == 0:
            note = f"{size // 6400}*6400"
        elif size == 80:
            note = "80"
        elif size == 4000:
            note = "history?"
        rows.append((i, ptr, size, running, note))
        if size >= 64 or i < 20:
            print(
                f"  [{i:3d}] ptr={ptr:#010x}  size={size:7d}  "
                f"file_off={running - size:7d}  {note}"
            )
    print(
        f"  chunks with size>=64 shown; n={len(rows)}  table_bytes={running}  "
        f"+4000={running + 4000}  (SAV is 225745)"
    )

    print("\n=== load_file @ 0x2444A (EAX=name EDX=dst EBX=max) ===")
    disasm(mapped, 0x2444A, 45)

    print("\n=== save @ 0x7024A ===")
    disasm(mapped, 0x7024A, 80)

    print("\n=== lastyear autosave xref site ===")
    disasm(mapped, 0x34D90, 30)

    print("\n=== gfx error 0x10903 ===")
    disasm(mapped, 0x108E0, 28)

    print("\n=== mov-imm of C2MODEL / SAV sizes ===")
    for val, name in (
        (4360, "4360_C2MODEL"),
        (1090, "1090_ints"),
        (31876, "C2ENG_file"),
        (40000, "0x9c40"),
        (3600, "region_rec"),
        (158400, "regions_dat"),
    ):
        needle = struct.pack("<I", val)
        hits = []
        start = 0
        while True:
            i = img.find(needle, start)
            if i < 0:
                break
            hits.append(mapped.base + i)
            start = i + 1
        print(f"  {name:16s} n={len(hits)} {[hex(h) for h in hits[:8]]}")

    print("\n=== .dat strings ===")
    start = 0
    seen = set()
    while True:
        i = img.find(b".dat", start)
        if i < 0:
            break
        j = i
        while j > 0 and 32 <= img[j - 1] < 127:
            j -= 1
        s = img[j : i + 4].decode("ascii", errors="replace")
        va = mapped.base + j
        if va not in seen:
            seen.add(va)
            print(f"  {va:#x} {s!r} xrefs={len(xrefs_to_va(mapped, va))}")
        start = i + 1

    tsv = Path("notes/ps_sav_chunks.tsv")
    tsv.parent.mkdir(parents=True, exist_ok=True)
    with tsv.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("index\tptr_va\tsize\tfile_off\tnote\n")
        off = 0
        for i, ptr, size, _cum, note in rows:
            fh.write(f"{i}\t{ptr:#x}\t{size}\t{off}\t{note}\n")
            off += size
        fh.write(f"# trailer\t[0xc4d10]\t4000\t{off}\thistory.dat blob\n")
    print(f"\nwrote {tsv} ({len(rows)} chunks)")

    print("\n=== sav_write @ 0x70174 (lastyear / named save) ===")
    disasm(mapped, 0x70174, 40)

    print("\n=== packed RAW names from a01.raw ===")
    va = 0x93694
    for _ in range(120):
        s = cstr(mapped, va)
        if not s:
            break
        print(f"  {va:#x} {s}")
        va += len(s) + 1

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
