#!/usr/bin/env python3
"""Hypothesize PS.EXE functions from string xrefs, C2MODEL overlap, and immediates.

Walks backward from pointer sites to a Watcom-ish prologue (push ebx/esi/edi
or push ebp / mov ebp,esp). Prints a compact function list with file offsets
for Ghidra. Does not need a decompiler.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

from ps_le import (
    DEFAULT_EXE,
    file_offset_of_va,
    find_u32s,
    load_ps,
    map_image,
    xrefs_to_va,
)

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")

# Byte sequences that usually open a Watcom 32-bit function.
PROLOGUES = (
    bytes.fromhex("53 56 57"),          # push ebx; push esi; push edi
    bytes.fromhex("56 57"),              # push esi; push edi
    bytes.fromhex("53 57"),              # push ebx; push edi
    bytes.fromhex("55 8B EC"),          # push ebp; mov ebp,esp
    bytes.fromhex("53 51 56"),          # push ebx; push ecx; push esi
    bytes.fromhex("51 56 57"),
    bytes.fromhex("53 56"),
)


def find_prologue(img: bytes, mapped_off: int, back: int = 0x200) -> int | None:
    """Return image-offset of the nearest prologue at or before mapped_off."""
    start = max(0, mapped_off - back)
    window = img[start : mapped_off + 1]
    best = None
    for p in PROLOGUES:
        i = 0
        while True:
            j = window.find(p, i)
            if j < 0:
                break
            cand = start + j
            if best is None or cand > best:
                best = cand
            i = j + 1
    return best


def hexdump(img: bytes, off: int, n: int = 24) -> str:
    chunk = img[off : off + n]
    return chunk.hex(" ")


def find_cstr(mapped, needle: bytes) -> list[int]:
    img = bytes(mapped.image)
    out = []
    start = 0
    while True:
        i = img.find(needle, start)
        if i < 0:
            break
        # prefer NUL-terminated
        if i + len(needle) < len(img) and img[i + len(needle)] == 0:
            out.append(mapped.base + i)
        start = i + 1
    return out


def report_string(ps, mapped, label: str, needle: bytes) -> list[dict]:
    img = bytes(mapped.image)
    rows = []
    for va in find_cstr(mapped, needle):
        xrefs = xrefs_to_va(mapped, va)
        for xr in xrefs:
            off = mapped.va_to_off(xr)
            pro = find_prologue(img, off) if off is not None else None
            pro_va = mapped.base + pro if pro is not None else None
            rows.append(
                {
                    "label": label,
                    "str_va": va,
                    "xref": xr,
                    "func": pro_va,
                    "str_file": file_offset_of_va(mapped, va),
                    "xref_file": file_offset_of_va(mapped, xr),
                    "func_file": file_offset_of_va(mapped, pro_va) if pro_va else None,
                    "bytes": hexdump(img, off - 8, 20) if off and off >= 8 else "",
                }
            )
    return rows


def compare_c2model(mapped, dat: bytes) -> None:
    img = bytes(mapped.image)
    print("=== C2MODEL.DAT vs mapped image ===")
    print(f"  dat bytes       : {len(dat)}")
    # aligned search
    aligned = []
    unaligned = []
    start = 0
    while True:
        i = img.find(dat[:64], start)  # first 16 ints as fingerprint
        if i < 0:
            break
        (aligned if (mapped.base + i) % 4 == 0 else unaligned).append(mapped.base + i)
        start = i + 1
    print(f"  fingerprint[16] aligned VAs : {[hex(v) for v in aligned]}")
    print(f"  fingerprint[16] other VAs   : {[hex(v) for v in unaligned[:6]]} (n={len(unaligned)})")

    # full-file search
    full = []
    start = 0
    while True:
        i = img.find(dat, start)
        if i < 0:
            break
        full.append(mapped.base + i)
        start = i + 1
    print(f"  exact full DAT  : {[hex(v) for v in full]}")
    if full:
        va = full[0]
        print(f"  ** C2MODEL.DAT is embedded verbatim at VA {va:#x} **")
        xrefs = xrefs_to_va(mapped, va)
        print(f"  xrefs to table  : {len(xrefs)} {[hex(x) for x in xrefs[:12]]}")
        return

    # longest prefix match at aligned addresses
    best = (0, None)
    for i in range(0, len(img) - 64, 4):
        n = 0
        while n < len(dat) and i + n < len(img) and img[i + n] == dat[n]:
            n += 1
        if n > best[0]:
            best = (n, mapped.base + i)
    print(f"  longest aligned prefix: {best[0]} bytes at VA {best[1]:#x}" if best[1] else "  no prefix")


def scan_ail(mapped, raw: bytes) -> None:
    print("=== Miles AIL strings (raw file) ===")
    i = 0
    hits = []
    while True:
        j = raw.find(b"AIL", i)
        if j < 0:
            break
        end = raw.find(b"\x00", j)
        if 0 < end - j < 80:
            s = raw[j:end].decode("ascii", errors="replace")
            hits.append((j, s))
        i = j + 3
    for off, s in hits:
        print(f"  {off:#08x}  {s}")
    print(f"  count={len(hits)}")
    print("=== sample/play related mapped strings ===")
    for needle in (
        b"AIL_set_sample",
        b"AIL_startup",
        b"AIL_init",
        b"sample",
        b".raw",
        b".wav",
        b"null.voc",
        b"prebatle",
        b"22050",
        b"11025",
    ):
        vas = find_cstr(mapped, needle)
        print(f"  {needle!r:24s} n={len(vas)} {[hex(v) for v in vas[:4]]}")


def scan_io_modes(mapped) -> None:
    print("=== fopen-style mode strings ===")
    for needle in (b"rb", b"wb", b"r+b", b"w+b", b"rt", b"wt", b"ab"):
        vas = find_cstr(mapped, needle)
        # filter true 2-3 char modes
        kept = []
        img = mapped.image
        for va in vas:
            off = mapped.va_to_off(va)
            if off is None:
                continue
            n = 0
            while off + n < len(img) and img[off + n] != 0:
                n += 1
            if 1 <= n <= 4:
                kept.append(va)
        print(f"  {needle!r:8s} n={len(kept)} {[hex(v) for v in kept[:8]]}")


def dump_around(mapped, va: int, before: int = 32, after: int = 48) -> None:
    off = mapped.va_to_off(va)
    if off is None:
        print(f"  (VA {va:#x} not mapped)")
        return
    chunk = mapped.image[max(0, off - before) : off + after]
    print(f"  bytes @ {va-before:#x}: {chunk.hex(' ')}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Hypothesize PS.EXE functions from xrefs.")
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    args = ap.parse_args(argv)

    ps = load_ps(args.exe)
    mapped = map_image(ps)
    img = bytes(mapped.image)

    dat_path = args.game / "C2MODEL.DAT"
    if dat_path.is_file():
        compare_c2model(mapped, dat_path.read_bytes())
    else:
        print(f"C2MODEL.DAT missing at {dat_path}")

    print()
    scan_ail(mapped, ps.data)
    print()
    scan_io_modes(mapped)

    needles = [
        ("resource.cfg", b"resource.cfg"),
        ("intro.smk", b"intro.smk"),
        ("c2.eng", b"c2.eng"),
        ("help.eng", b"help.eng"),
        ("caesar2.sav", b"caesar2.sav"),
        ("lastyear.sav", b"lastyear.sav"),
        ("*.sav", b"*.sav"),
        ("history.dat", b"history.dat"),
        ("regions.dat", b"regions.dat"),
        ("cd.dat", b"cd.dat"),
        ("Error loading graphics", b"Error loading graphics"),
        ("Error loading overlay", b"Error loading overlay"),
        ("Error loading battle", b"Error loading battle"),
        ("Not enough free memory", b"Not enough free memory"),
        ("cityfixt.256", b"cityfixt.256"),
        ("font_c2.pl8", b"font_c2.pl8"),
        ("houses1.pl8", b"houses1.pl8"),
        ("null.voc", b"null.voc"),
        ("prebatle.raw", b"prebatle.raw"),
        ("a01.raw", b"a01.raw"),
        ("forum_x.gd8", b"forum_x.gd8"),
        ("c2model", b"c2model"),
        ("C2MODEL", b"C2MODEL"),
        ("model.dat", b"model.dat"),
    ]

    print("\n=== hypothesized functions (string xref -> prologue) ===")
    print(
        f"{'label':28s} {'funcVA':>10s} {'funcFile':>10s} {'xrefVA':>10s} {'strVA':>10s}"
    )
    seen_func: dict[int, list[str]] = {}
    for label, needle in needles:
        rows = report_string(ps, mapped, label, needle)
        if not rows:
            # still print string VA if present
            vas = find_cstr(mapped, needle)
            print(f"{label:28s}  (no ptr xref)  strVAs={[hex(v) for v in vas]}")
            continue
        for r in rows:
            fv = r["func"]
            fv_s = f"{fv:#010x}" if fv is not None else "       n/a"
            ff_s = str(r["func_file"]) if r["func_file"] is not None else "n/a"
            print(
                f"{r['label']:28s} {fv_s:>12s} {ff_s:>10s} "
                f"{r['xref']:#10x} {r['str_va']:#10x}  {r['bytes']}"
            )
            if fv:
                seen_func.setdefault(fv, []).append(label)

    print("\n=== functions with multiple string hits ===")
    for fv, labs in sorted(seen_func.items(), key=lambda kv: -len(kv[1])):
        if len(labs) > 1:
            print(f"  {fv:#x}  file {file_offset_of_va(mapped, fv)}  {labs}")

    print("\n=== 6400 (0x1900) as mov/push/cmp immediate ===")
    needle = struct.pack("<I", 6400)
    for i in find_u32s(img, 6400):
        pre4 = img[max(0, i - 6) : i]
        va = mapped.base + i
        # look for C7 (mov rm,imm32) or 68 push or B8..BB
        kind = "?"
        if i >= 1 and img[i - 1] in (0x68, 0xB8, 0xB9, 0xBA, 0xBB, 0x05, 0x3D, 0x2D):
            kind = {
                0x68: "push",
                0xB8: "mov eax",
                0xB9: "mov ecx",
                0xBA: "mov edx",
                0xBB: "mov ebx",
                0x05: "add eax",
                0x3D: "cmp eax",
                0x2D: "sub eax",
            }[img[i - 1]]
        elif i >= 2 and img[i - 2] == 0xC7:
            kind = "mov rm32,imm"
        elif i >= 3 and img[i - 3] == 0xC7:
            kind = "mov rm32,imm (modrm)"
        elif i >= 6 and img[i - 6] == 0xC7:
            kind = "mov [r+disp32],imm"
        if kind != "?":
            pro = find_prologue(img, i)
            print(
                f"  VA {va:#08x} file {file_offset_of_va(mapped, va)}  {kind:20s}  "
                f"func {mapped.base+pro:#x}" if pro else
                f"  VA {va:#08x} file {file_offset_of_va(mapped, va)}  {kind:20s}  func ?"
            )

    print("\n=== 22050 push sites (Miles sample rate) ===")
    for i in find_u32s(img, 22050):
        va = mapped.base + i
        pro = find_prologue(img, i)
        print(
            f"  VA {va:#x} pre={img[i-6:i].hex(' ')} func={mapped.base+pro:#x}"
            if pro
            else f"  VA {va:#x} pre={img[i-6:i].hex(' ')}"
        )

    print("\n=== context around caesar2.sav / lastyear.sav xrefs ===")
    for name in (b"caesar2.sav", b"lastyear.sav", b"c2.eng", b"Error loading graphics"):
        for va in find_cstr(mapped, name):
            print(f"{name!r} at {va:#x}")
            for xr in xrefs_to_va(mapped, va):
                print(f"  xref {xr:#x}")
                dump_around(mapped, xr)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
