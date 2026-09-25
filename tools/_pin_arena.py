#!/usr/bin/env python3
"""Read-only: prove Arena 0xE7 is a City Construction Kit stamp.

Ghidra HTTP is down this pass. Listing from mapped PS.EXE / c2_x.bin.
C2.ENG + C2MODEL stay on the retail install (not copied).
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
GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
C2MODEL = GAME / "C2MODEL.DAT"
C2ENG = GAME / "C2.ENG"
HELP = GAME / "HELP.ENG"


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_asm(img: bytes, va: int, nbytes: int, title: str, limit: int = 60) -> None:
    off = va - BASE
    if off < 0 or off >= len(img):
        print(f"\n==== {title} {va:#x} (OOB) ====")
        return
    code = img[off : off + nbytes]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    print(f"\n==== {title} {va:#x} ====")
    n = 0
    for insn in dec.disasm(code, va):
        print(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} "
            f"{insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= limit:
            print("  ...")
            break


def find_imm8_cmp(img: bytes, value: int, lo: int, hi: int) -> list[int]:
    """cmp r/m8, imm8 (80 /7 ib) and cmp al, imm8 (3C ib)."""
    hits = []
    off = lo - BASE
    span = hi - lo
    for i in range(span - 2):
        b0, b1, b2 = img[off + i], img[off + i + 1], img[off + i + 2]
        if b0 == 0x3C and b1 == value:
            hits.append(lo + i)
        if b0 == 0x80 and (b1 & 0x38) == 0x38 and b2 == value:
            hits.append(lo + i)
        if b0 == 0x83 and (b1 & 0x38) == 0x38 and b2 == value:
            hits.append(lo + i)
    return hits


def find_imm32(img: bytes, value: int, lo: int, hi: int) -> list[int]:
    needle = struct.pack("<I", value)
    hits = []
    off = lo - BASE
    start = 0
    span = hi - lo
    while True:
        i = img.find(needle, off + start, off + span)
        if i < 0:
            break
        hits.append(i + BASE)
        start = i - off + 1
    return hits


def find_bytes(img: bytes, needle: bytes, lo: int = 0x10000, hi: int | None = None) -> list[int]:
    if hi is None:
        hi = BASE + len(img)
    hits = []
    start = lo - BASE
    end = hi - BASE
    while True:
        i = img.find(needle, start, end)
        if i < 0:
            break
        hits.append(i + BASE)
        start = i + 1
    return hits


def parse_textfile(path: Path) -> list[str]:
    data = path.read_bytes()
    if not data.startswith(b"Textfile"):
        raise ValueError(f"{path.name} magic {data[:8]!r}")
    first = struct.unpack_from("<I", data, 12)[0]
    n = (first - 12) // 4
    offs = [struct.unpack_from("<I", data, 12 + 4 * i)[0] for i in range(n)]
    out = []
    for off in offs:
        end = data.find(b"\x00", off)
        out.append(data[off:end].decode("latin-1", errors="replace"))
    return out


def help_hits(needle: bytes) -> list[tuple[int, bytes]]:
    if not HELP.exists():
        return []
    data = HELP.read_bytes()
    hits = []
    start = 0
    while True:
        i = data.find(needle, start)
        if i < 0:
            break
        lo = max(0, i - 80)
        hi = min(len(data), i + 120)
        hits.append((i, data[lo:hi]))
        start = i + 1
        if len(hits) >= 8:
            break
    return hits


def main() -> None:
    img, src = load_image()
    print(f"image {src} len={len(img)}")

    print("\n=== DAT_00094FE5[0xE4:0xF1] size class (9->3x3, 4->2x2) ===")
    for tid in range(0xE4, 0xF1):
        rec = img[0x94FE5 + tid - BASE]
        n = {1: 1, 4: 2, 9: 3, 0x10: 4}.get(rec, 0)
        print(f"  id {tid:#x} type={rec} N={n or '?'}")

    print("\n=== C2MODEL entertainment_costs [118:124] ===")
    if C2MODEL.exists():
        vals = list(struct.unpack("<1090i", C2MODEL.read_bytes()))
        names = ("Theater", "Odeum", "Arena", "Coliseum", "Circus", "C.Maximus")
        for i, name in enumerate(names):
            print(f"  [{118 + i}] {vals[118 + i]}  {name}")
        print("  pop_unlocks [gap] search 400,800,1200,1800,2400,4800:")
        needle = b"".join(struct.pack("<i", v) for v in (400, 800, 1200, 1800, 2400, 4800))
        raw = C2MODEL.read_bytes()
        p = raw.find(needle)
        print(f"    at byte {p} ints[{p // 4}:{p // 4 + 6}]" if p >= 0 else "    ABSENT")
        print("  other-buildings LV pairs around Odeum 3;4 / Coliseum 4;5:")
        for i in range(732, 790, 2):
            b, r = vals[i], vals[i + 1]
            tag = ""
            if (b, r) == (3, 4):
                tag = "  << Odeum-like"
            elif (b, r) == (4, 5):
                tag = "  << Coliseum-like"
            elif (b, r) == (2, 2):
                tag = "  << Theater-like"
            print(f"    [{i}] bonus={b} r={r}{tag}")
    else:
        print("  C2MODEL missing")

    print("\n=== C2.ENG strings containing Arena / Theater / Colise ===")
    if C2ENG.exists():
        strs = parse_textfile(C2ENG)
        for i, s in enumerate(strs):
            low = s.lower()
            if any(k in low for k in ("arena", "theater", "theatre", "odeum", "colis", "circus")):
                print(f"  [{i:3d}] {s[:120]!r}")
    else:
        print("  C2.ENG missing")

    print("\n=== HELP.ENG Arena / Colosseum tips ===")
    for needle in (b"Arena", b"Arenas", b"Colosseum", b"Theater"):
        hs = help_hits(needle)
        print(f"  {needle!r} hits={len(hs)}")
        for off, blob in hs[:2]:
            print(f"    @{off} {blob!r}")

    print("\n=== cmp imm 0xE5/E6/E7/E8 in place / painter bands ===")
    bands = (
        (0x2F000, 0x32000, "click/place dispatcher"),
        (0x3F000, 0x41000, "+12 painter 4034b"),
        (0x65000, 0x6B000, "stamp / occupancy"),
        (0x12000, 0x14000, "advisor type 12a8f"),
    )
    for lo, hi, label in bands:
        print(f"  -- {label} {lo:#x}-{hi:#x} --")
        for tid in (0xE5, 0xE6, 0xE7, 0xE8):
            c8 = find_imm8_cmp(img, tid, lo, hi)
            c32 = find_imm32(img, tid, lo, hi)
            if c8 or c32:
                print(f"    {tid:#x} cmp8={[hex(x) for x in c8[:12]]} imm32={[hex(x) for x in c32[:8]]}")

    print("\n=== +4 3×3 packing after Odeum 0x28-0x2B / before Coliseum 0x35-0x3D ===")
    # Raster y,x: base, +2, +5 / +1, +4, +7 / +3, +6, +8
    arena_vars = bytes((0x2C, 0x2E, 0x31, 0x2D, 0x30, 0x33, 0x2F, 0x32, 0x34))
    coli_vars = bytes((0x35, 0x37, 0x3A, 0x36, 0x39, 0x3C, 0x38, 0x3B, 0x3D))
    print(f"  hypothesized Arena +4: {[hex(b) for b in arena_vars]}")
    print(f"  known Coliseum +4:     {[hex(b) for b in coli_vars]}")
    for name, needle in (
        ("arena_pack", arena_vars),
        ("coli_pack", coli_vars),
        ("arena_seq", bytes(range(0x2C, 0x35))),
        ("coli_seq", bytes(range(0x35, 0x3E))),
    ):
        hits = find_bytes(img, needle)
        print(f"  {name} hits={[hex(h) for h in hits[:8]]}")

    # Per-id +4 base table? search 24 28 2C 35 (theater/odeum/arena/coli bases)
    bases = bytes((0x24, 0x28, 0x2C, 0x35, 0x00))  # maybe not packed
    print("  theater/odeum/arena/coli bases 24 28 2C 35:")
    print(f"    {[hex(h) for h in find_bytes(img, bytes((0x24, 0x28, 0x2C, 0x35)))[:8]]}")
    print(f"    24 28 2C: {[hex(h) for h in find_bytes(img, bytes((0x24, 0x28, 0x2C)))[:8]]}")

    print("\n=== place dispatcher 0x2FE8E head ===")
    dump_asm(img, 0x2FE8E, 0x120, "2FE8E place tool switch", 70)

    print("\n=== +12 painter 0x4034b Arena arm (cmp 0xE7) ===")
    e7s = find_imm8_cmp(img, 0xE7, 0x40000, 0x40800) + find_imm32(img, 0xE7, 0x40000, 0x40800)
    print(f"  hits {[hex(x) for x in e7s]}")
    if e7s:
        dump_asm(img, e7s[0] - 8, 0xA0, "4034b near first 0xE7", 40)

    print("\n=== FUN_00012a8f advisor-type (0xE7 → type 5 with 0xE8) ===")
    dump_asm(img, 0x12A8F, 0x180, "12a8f id ranges", 80)

    print("\n=== flyout pick Arena tool 0x19 @ 0x32961 ===")
    dump_asm(img, 0x32921, 0x80, "Theater/Odeum/Arena/Coliseum flyout", 30)
    print("\n=== EXE cost dwords 0x967a3.. ===")
    for va, name in (
        (0x967A3, "Theater"),
        (0x967A7, "Odeum"),
        (0x967AB, "Arena"),
        (0x967AF, "Coliseum"),
        (0x967B3, "Circus"),
        (0x967B7, "C.Maximus"),
    ):
        val = struct.unpack_from("<i", img, va - BASE)[0]
        print(f"  {va:#x} {name} = {val}")

    print("\n=== LUT 0x94230 piece deltas + Arena/Coliseum +4 ===")
    lut = img[0x94230 - BASE : 0x94230 - BASE + 9]
    print(f"  LUT = {[hex(b) for b in lut]}")
    print(f"  Arena  0x2C+LUT = {[hex(0x2C + b) for b in lut]}")
    print(f"  Coli   0x35+LUT = {[hex(0x35 + b) for b in lut]}")

    print("\n=== place write tool 0x19 @ 0x30607 ===")
    dump_asm(img, 0x305A1, 0xA0, "Theater 0x17 .. Coliseum 0x1a", 40)


if __name__ == "__main__":
    main()
