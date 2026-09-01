#!/usr/bin/env python3
"""Dump calendar scalars from named saves. Does not copy or commit the SAV."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.calendar import MONTHS, YEAR_CHUNK, chunk_i32
from app.city_map import SAV_CHUNKS_VA, load_chunk_sizes, walk_sav_chunks
from tools.extract_eng import parse_textfile
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
WANT_PTRS = {
    0x102A74: "week_counter?",
    0x102A88: "month (0=Jan)",
    0x102A9C: "year_alt?",
    0x102AA0: "year (signed BC)",
    0x102AA8: "chunk30 init5",
    0x102AAC: "treasury",
    0x102AB0: "population?",
    0x102AB4: "year_seed -300",
    0x102AC0: "year_inc_sibling",
    0x102BA4: "chunk5 old year-BC hyp",
}


def sav_chunk_table(game: Path) -> list[tuple[int, int]]:
    mapped = map_image(load_ps(game / "PS.EXE"), apply_fixups=True)
    rows: list[tuple[int, int]] = []
    for i in range(500):
        off = mapped.va_to_off(SAV_CHUNKS_VA + i * 8)
        if off is None:
            raise SystemExit(f"SavChunk[{i}] unmapped")
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
        ROOT / "findings" / "D.SAV",
    ):
        if path.is_file():
            found.append(path)
    return found


def main() -> None:
    table = sav_chunk_table(GAME)
    print("=== SavChunk ptr hits ===")
    by_ptr = {ptr: i for i, (ptr, _sz) in enumerate(table)}
    for ptr, name in WANT_PTRS.items():
        i = by_ptr.get(ptr)
        if i is None:
            print(f"  {ptr:#08x}  {name:24s}  NOT IN TABLE")
            continue
        print(f"  {ptr:#08x}  {name:24s}  chunk {i:3d}  size {table[i][1]}")

    sizes = load_chunk_sizes(GAME)
    print("\n=== C2.ENG 20..40 ===")
    eng = (GAME / "C2.ENG").read_bytes()
    _off, strings, _pad, _unique = parse_textfile(eng)
    for i in range(20, min(41, len(strings))):
        print(f"  [{i:3d}] {strings[i]!r}")
    for needle in ("January", "BC", "AD", "Week 1", "December", "Forum", "Empire"):
        hits = [i for i, s in enumerate(strings) if needle.lower() in s.lower()]
        print(f"  find {needle!r}: {hits[:12]}")

    print("\n=== save dates ===")
    for path in find_saves():
        data = path.read_bytes()
        chunks = walk_sav_chunks(data, sizes)
        month_idx = by_ptr.get(0x102A88)
        y = chunk_i32(chunks, YEAR_CHUNK)
        m = chunk_i32(chunks, month_idx) if month_idx is not None else -1
        c5 = chunk_i32(chunks, 5)
        treas = chunk_i32(chunks, 28)
        month_name = MONTHS[m] if 0 <= m < 12 else f"?{m}"
        era = f"{-y} BC" if y < 0 else f"{y} AD"
        print(
            f"  {path.name:16s}  HUD={era} {month_name:12s}  "
            f"c25={y:6d}  month_raw={m} (chunk {month_idx})  c5={c5:4d}  treasury={treas}"
        )
        extra = []
        for ptr, name in WANT_PTRS.items():
            i = by_ptr.get(ptr)
            if i is None or i >= len(chunks):
                continue
            raw = bytes(chunks[i])
            if len(raw) == 4:
                extra.append(f"{i}:{struct.unpack_from('<i', raw)[0]}")
            elif len(raw) == 1:
                extra.append(f"{i}:{raw[0]}")
        print(f"    extras  {', '.join(extra)}")


if __name__ == "__main__":
    main()
