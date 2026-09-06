#!/usr/bin/env python3
"""Local dump: New Game Options + difficulty (C2.ENG / HELP / SAV / C2MODEL / EXE).

Does not write game binaries into the repo. Print-only.
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.city_map import load_chunk_sizes, walk_sav_chunks
from tools.extract_eng import parse_textfile
from tools.ps_le import load_ps, map_image, xrefs_to_va

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
NUL = b"\x00"
DIFFS = ("Novice", "Easy", "Normal", "Hard", "Impossible")


def packed_from(data: bytes, start: int, n: int) -> list[tuple[int, int, str]]:
    rows = []
    pos = start
    for i in range(n):
        if pos >= len(data):
            break
        end = data.find(NUL, pos)
        if end < 0:
            break
        s = data[pos:end].decode("latin-1")
        rows.append((i, pos, s))
        pos = end + 1
    return rows


def show_pack(label: str, rows: list[tuple[int, int, str]], maxlen: int = 160) -> None:
    print(f"\n===== {label}  ({len(rows)} strings) =====")
    for i, off, s in rows:
        shown = s.replace("\r", "\\r").replace("\n", "\\n")
        if len(shown) > maxlen:
            shown = shown[: maxlen - 3] + "..."
        print(f"  +{i:3d} @{off:6d} ({len(s):4d}) {shown}")


def ascii_hits(data: bytes, needles: tuple[str, ...]) -> None:
    low = data.lower()
    for needle in needles:
        n = needle.encode("ascii", "ignore").lower()
        if not n:
            continue
        count = low.count(n)
        print(f"  {needle!r}: {count} raw hits")
        start = 0
        shown = 0
        while shown < 12:
            i = low.find(n, start)
            if i < 0:
                break
            lo = max(0, i - 24)
            hi = min(len(data), i + len(n) + 40)
            ctx = data[lo:hi]
            ctx = "".join(chr(b) if 32 <= b < 127 else "." for b in ctx)
            print(f"    @{i:7d}  {ctx}")
            start = i + 1
            shown += 1


def find_saves() -> list[Path]:
    found: list[Path] = []
    for path in (
        GAME / "Achea.sav" / "ACHEA23.SAV",
        GAME / "20230610.SAV",
        GAME / "FELIPE01.SAV",
        GAME / "FELIPE02.SAV",
        GAME / "LASTYEAR.SAV",
        GAME / "D.SAV",
        ROOT / "findings" / "D.SAV",
        ROOT / "A.SAV",
        ROOT / "B.SAV",
        ROOT / "C.SAV",
        GAME / "A.SAV",
        GAME / "B.SAV",
        GAME / "C.SAV",
    ):
        if path.is_file() and path not in found:
            found.append(path)
    extra = GAME / "Achea.sav"
    if extra.is_dir():
        for p in extra.glob("*.SAV"):
            if p.is_file() and p not in found:
                found.append(p)
    for folder in (GAME, ROOT, ROOT / "findings"):
        if folder.is_dir():
            for p in folder.glob("*.SAV"):
                if p.is_file() and p not in found:
                    found.append(p)
    return found


def i32(b: bytes, off: int = 0) -> int:
    return struct.unpack_from("<i", b, off)[0]


def u8(b: bytes, off: int = 0) -> int:
    return b[off]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-saves", action="store_true")
    ap.add_argument("--xrefs-only", action="store_true")
    args = ap.parse_args()
    if args.xrefs_only:
        dump_xrefs_and_tables()
        return
    eng = (GAME / "C2.ENG").read_bytes()
    offs, strings, pad, unique = parse_textfile(eng)
    print(f"C2.ENG n={len(strings)} unique={unique} pad={pad}")

    needles = (
        "Easy",
        "Normal",
        "Hard",
        "Very Hard",
        "Difficulty",
        "Novice",
        "Impossible",
        "New Game Options",
        "Campaign?",
        "Start this Game",
        "CITY-ONLY",
    )
    print("\n===== C2.ENG official 146 slots (needle in string) =====")
    for needle in needles:
        hits = [i for i, s in enumerate(strings) if needle.lower() in s.lower()]
        if not hits:
            print(f"  {needle!r}: (none in 146-slot index)")
            continue
        for i in hits[:8]:
            shown = strings[i].replace("\r", "\\r").replace("\n", "\\n")
            if len(shown) > 90:
                shown = shown[:87] + "..."
            print(f"  {needle!r} -> [{i}] {shown!r}")

    print("\n===== C2.ENG full-file ASCII hunt =====")
    ascii_hits(eng, needles)

    for slot, n in ((38, 80), (42, 80), (0, 20), (9, 12)):
        if slot < len(offs):
            rows = packed_from(eng, offs[slot], n)
            show_pack(f"[{slot}] first={strings[slot]!r}", rows)

    help_path = GAME / "HELP.ENG"
    if help_path.is_file():
        helpb = help_path.read_bytes()
        print("\n===== HELP.ENG ASCII hunt =====")
        ascii_hits(helpb, needles + ("city-only", "campaign", "tutorial", "Impossible!"))

    exe = (GAME / "PS.EXE").read_bytes()
    print("\n===== PS.EXE raw ASCII hunt =====")
    ascii_hits(exe, needles)

    sizes = load_chunk_sizes(GAME)
    print("\n===== SAV chunk 16 / 28 / 223 / 291 / 406 =====")
    if args.no_saves:
        print("  (skipped)")
    for path in [] if args.no_saves else find_saves():
        data = path.read_bytes()
        if len(data) != 225745:
            print(f"  {path} size={len(data)} SKIP")
            continue
        chunks = walk_sav_chunks(data, sizes)
        d16 = u8(bytes(chunks[16]))
        treas = i32(bytes(chunks[28]))
        pid = i32(bytes(chunks[223])) if len(chunks[223]) >= 4 else -1
        rank = i32(bytes(chunks[291])) if len(chunks[291]) >= 4 else -1
        mode = u8(bytes(chunks[406]))
        year = i32(bytes(chunks[25]))
        seed = i32(bytes(chunks[325])) if len(chunks[325]) >= 4 else None
        hist = i32(bytes(chunks[338])) if len(chunks[338]) >= 4 else None
        label = DIFFS[d16] if 0 <= d16 < 5 else f"?{d16}"
        rel = path.relative_to(path.anchor) if False else path
        print(
            f"  {path.name:16s} 16={d16} ({label:10s})  "
            f"28={treas:7d}  223={pid:3d}  291={rank:2d}  "
            f"406={mode}  25={year:5d}  325={seed}  338={hist}  "
            f"path={path}"
        )

    dat = (GAME / "C2MODEL.DAT").read_bytes()
    ints = list(struct.unpack(f"<{len(dat)//4}i", dat))
    print("\n===== C2MODEL prefix + ranks =====")
    print(f"  [0:5]   scalars     {ints[0:5]}")
    print(f"  [5:10]  treasury    {ints[5:10]}")
    print(f"  [10:15] discount    {ints[10:15]}")
    print(f"  [55:75] pct 5x4     {ints[55:75]}")
    print(f"  [75:95] event?      {ints[75:95]}")
    print("  individual 5x20 [790:890]:")
    for d, name in enumerate(DIFFS):
        row = ints[790 + d * 20 : 810 + d * 20]
        print(f"    {d} {name:11s} {row}")
        print(f"      slot2 Apparitor = {row[2]}")
    print("  average 5x20 [890:990]:")
    for d, name in enumerate(DIFFS):
        row = ints[890 + d * 20 : 910 + d * 20]
        print(f"    {d} {name:11s} {row}")
        print(f"      slot2 Apparitor = {row[2]}")

    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    print(f"\n===== EXE mapped base={mapped.base:#x} size={len(mapped.image)} =====")
    xrs = xrefs_to_va(mapped, 0x9CE80)
    print(f"  dword ptr xrefs → 0x9CE80: {len(xrs)}")
    for va in xrs[:80]:
        print(f"    {va:#x}")

    # also search the 4-byte LE address in code as immediate
    needle = struct.pack("<I", 0x9CE80)
    img = bytes(mapped.image)
    hits = []
    start = 0
    while True:
        i = img.find(needle, start)
        if i < 0:
            break
        hits.append(mapped.base + i)
        start = i + 1
    print(f"  raw LE 80 CE 09 00 hits: {len(hits)}")
    for va in hits[:80]:
        print(f"    {va:#x}")

    # 0x96221 table (init_new_city small packed)
    print("\n===== table 0x96221 (5 x i32?) =====")
    off = mapped.va_to_off(0x96221)
    if off is not None:
        vals = struct.unpack_from("<8i", mapped.image, off)
        print(f"  i32s: {vals}")
        print(f"  bytes: {bytes(mapped.image[off:off+20]).hex()}")

    print("\n===== C2MODEL embed 0x96F1B =====")
    off = mapped.va_to_off(0x96F1B)
    if off is not None:
        vals = struct.unpack_from("<16i", mapped.image, off)
        print(f"  {vals}")

    dump_help_excerpts()
    disasm_diff_hits(mapped, hits)


def dump_xrefs_and_tables() -> None:
    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    needle = struct.pack("<I", 0x9CE80)
    img = bytes(mapped.image)
    hits = []
    start = 0
    while True:
        i = img.find(needle, start)
        if i < 0:
            break
        hits.append(mapped.base + i)
        start = i + 1
    print(f"raw LE 0x9CE80 hits: {len(hits)}")
    for va in hits:
        print(f"  {va:#x}")
    dump_help_excerpts()
    disasm_diff_hits(mapped, hits)
    dat = (GAME / "C2MODEL.DAT").read_bytes()
    ints = list(struct.unpack(f"<{len(dat)//4}i", dat))
    print("\n===== C2MODEL prefix + ranks =====")
    print(f"  [0:5]   {ints[0:5]}")
    print(f"  [5:10]  {ints[5:10]}")
    print(f"  [10:15] {ints[10:15]}")
    print(f"  [55:75] {ints[55:75]}")
    print(f"  [75:95] {ints[75:95]}")
    for d, name in enumerate(DIFFS):
        row_i = ints[790 + d * 20 : 810 + d * 20]
        row_a = ints[890 + d * 20 : 910 + d * 20]
        print(f"  {d} {name:11s} ind={row_i}  avg={row_a}  slot2={row_i[2]}/{row_a[2]}")


def dump_help_excerpts() -> None:
    helpb = (GAME / "HELP.ENG").read_bytes()
    print("\n===== HELP.ENG excerpts =====")
    for needle in (
        b"harder difficulty",
        b"harder provinces or skill",
        b"Campaign option",
        b"CITY-ONLY",
        b"skill level",
        b"Skill Level",
        b"Novice",
        b"Impossible",
        b"immigrant",
        b"Immigrant",
        b"enemy",
        b"barbarian",
    ):
        i = 0
        n = 0
        while n < 4:
            j = helpb.lower().find(needle.lower(), i)
            if j < 0:
                break
            lo = max(0, j - 80)
            hi = min(len(helpb), j + 220)
            ctx = "".join(chr(b) if 32 <= b < 127 else "." for b in helpb[lo:hi])
            print(f"  {needle!r} @{j}")
            print(f"    {ctx}")
            i = j + 1
            n += 1


def disasm_diff_hits(mapped, hits: list[int]) -> None:
    try:
        from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    except ImportError:
        print("capstone missing")
        return
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print("\n===== disasm around 0x9CE80 immediates =====")
    for va in hits:
        start = va - 16
        off = mapped.va_to_off(start)
        if off is None:
            print(f"  {va:#x} unmapped")
            continue
        code = bytes(mapped.image[off : off + 40])
        print(f"\n  --- hit {va:#x} ---")
        for insn in dec.disasm(code, start):
            mark = " <" if insn.address <= va < insn.address + insn.size else "  "
            print(f"  {mark}{insn.address:08x}  {insn.mnemonic:8s} {insn.op_str}")


if __name__ == "__main__":
    main()
