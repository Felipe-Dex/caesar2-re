#!/usr/bin/env python3
"""Dump Week / overlay / HISTORY / calendar-adjacent scalars. Local only."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.city_map import SAV_CHUNKS_VA, SAV_HISTORY_BYTES, load_chunk_sizes, walk_sav_chunks
from tools.extract_eng import parse_textfile
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")

WANT = [
    0x102A74, 0x102A88, 0x102A9C, 0x102AA0, 0x102AA4, 0x102AA8, 0x102AAC,
    0x102AB0, 0x102AB4, 0x102AC0, 0x102A58, 0x102A5C, 0x102A34, 0x102A64,
    0x1025B0, 0x1025B4, 0x1025B8, 0x1025BC, 0x1025C0, 0x1025A4, 0x1025F0,
    0x102584, 0x117A59, 0x117A8D, 0x102C50, 0x102B2C, 0x102A6C, 0x102BA4,
    0x102578, 0x1024BC, 0x1024C0, 0x1026A8,
]


def sav_chunk_table() -> list[tuple[int, int]]:
    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    rows: list[tuple[int, int]] = []
    for i in range(500):
        off = mapped.va_to_off(SAV_CHUNKS_VA + i * 8)
        ptr, size = struct.unpack_from("<II", mapped.image, off)
        rows.append((ptr, size))
    return rows


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
    ):
        if path.is_file() and path not in found:
            found.append(path)
    extra = GAME / "Achea.sav"
    if extra.is_dir():
        for p in extra.glob("*.SAV"):
            if p not in found:
                found.append(p)
    return found


def i32(b: bytes, off: int = 0) -> int:
    return struct.unpack_from("<i", b, off)[0]


def main() -> None:
    table = sav_chunk_table()
    by_ptr = {ptr: i for i, (ptr, _sz) in enumerate(table)}
    sizes = load_chunk_sizes(GAME)

    print("=== chunk map ===")
    for ptr in WANT:
        i = by_ptr.get(ptr)
        if i is None:
            print(f"  {ptr:#08x}  NOT IN TABLE")
            continue
        print(f"  {ptr:#08x}  chunk {i:3d}  size {table[i][1]:5d}  off {sum(s for _p, s in table[:i])}")

    print("\n=== C2.ENG Week / overlay / forum ===")
    eng = (GAME / "C2.ENG").read_bytes()
    _off, strings, _pad, _unique = parse_textfile(eng)
    for needle in ("Week", "Unrest", "Forum", "January", "Peace", "Fire", "Water", "Crime", "Damage", "Land"):
        hits = [(i, s) for i, s in enumerate(strings) if needle.lower() in s.lower()]
        print(f"  {needle!r}: {hits[:20]}")

    print("\n=== C2.ENG 20..80 ===")
    for i in range(20, min(81, len(strings))):
        print(f"  [{i:3d}] {strings[i]!r}")

    # Packed run from January
    jan = next((i for i, s in enumerate(strings) if s == "January"), None)
    if jan is not None:
        print(f"\n=== packed from slot {jan} (shared offset walk) ===")
        raw = eng
        start = _off[jan]
        pos = start
        for n in range(24):
            end = raw.find(b"\x00", pos)
            s = raw[pos:end].decode("latin-1")
            print(f"  skip {n:2d}  {s!r}")
            pos = end + 1

    # Overlay names from EXE EAX=0x35 => file slot 0x34 = 52
    print("\n=== overlay names from slot 52 + skip ===")
    if len(strings) > 52:
        raw = eng
        start = _off[52]
        pos = start
        for n in range(16):
            end = raw.find(b"\x00", pos)
            s = raw[pos:end].decode("latin-1")
            print(f"  overlay {n:2d}  {s!r}")
            pos = end + 1

    print("\n=== binary: mov [0x102AA4], imm32 ===")
    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    needle = bytes.fromhex("C705 A42A1000")  # mov dword [0x102AA4], imm
    img = mapped.image
    # Need file offset of VA in image — search all
    # Pattern is absolute VA encoding; search raw EXE too
    exe = (GAME / "PS.EXE").read_bytes()
    for label, blob in (("exe", exe),):
        off = 0
        while True:
            i = blob.find(needle, off)
            if i < 0:
                break
            imm = struct.unpack_from("<I", blob, i + 6)[0]
            print(f"  {label}+{i:#x}  store {imm}")
            off = i + 1

    print("\n=== binary: mov byte [0x117A59], imm ===")
    needle2 = bytes.fromhex("C605 597A1100")
    off = 0
    while True:
        i = exe.find(needle2, off)
        if i < 0:
            break
        print(f"  exe+{i:#x}  store {exe[i+6]}")
        off = i + 1

    print("\n=== HISTORY trailers ===")
    hist_path = GAME / "HISTORY.DAT"
    if hist_path.is_file():
        h = hist_path.read_bytes()
        print(f"  HISTORY.DAT size={len(h)}")
        _dump_history("HISTORY.DAT", h)

    for path in find_saves():
        data = path.read_bytes()
        if len(data) < SAV_HISTORY_BYTES:
            continue
        trailer = data[-SAV_HISTORY_BYTES:]
        chunks = walk_sav_chunks(data, sizes)
        print(f"\n=== {path.name} scalars ===")
        for ptr in WANT:
            i = by_ptr.get(ptr)
            if i is None or i >= len(chunks):
                continue
            raw = bytes(chunks[i])
            if len(raw) == 4:
                print(f"  c{i:3d} {ptr:#08x}  i32={i32(raw):8d}")
            elif len(raw) == 1:
                print(f"  c{i:3d} {ptr:#08x}  u8={raw[0]}")
        ident = "HISTORY.DAT" if hist_path.is_file() and trailer == h else "own"
        print(f"  trailer vs HISTORY.DAT: {ident}")
        _dump_history(path.name, trailer)


def _dump_history(name: str, blob: bytes) -> None:
    n = len(blob) // 20
    nonempty = []
    for i in range(n):
        rec = blob[i * 20 : (i + 1) * 20]
        vals = struct.unpack("<5i", rec)
        if any(v != 0 for v in vals):
            nonempty.append((i, vals))
    print(f"  {name}: {len(nonempty)}/{n} nonempty 20B records")
    for i, vals in nonempty[:8]:
        print(f"    rec {i:3d}  pop={vals[0]:7d}  treas={vals[1]:8d}  a={vals[2]:6d}  b={vals[3]:6d}  year={vals[4]:5d}")
    if len(nonempty) > 8:
        print(f"    ... {len(nonempty) - 8} more")
        i, vals = nonempty[-1]
        print(f"    rec {i:3d}  pop={vals[0]:7d}  treas={vals[1]:8d}  a={vals[2]:6d}  b={vals[3]:6d}  year={vals[4]:5d}")


if __name__ == "__main__":
    main()
