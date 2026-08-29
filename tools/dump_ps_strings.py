#!/usr/bin/env python3
"""Classify ASCII C-strings in PS.EXE (raw file + mapped LE image).

Cross-checks C2.ENG. Writes a full dump (original game text) under notes/
which is gitignored. Prints a classified summary to stdout.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

from ps_le import (
    DEFAULT_EXE,
    extract_raw_strings,
    file_offset_of_va,
    load_ps,
    map_image,
    xrefs_to_va,
)

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")

EXTS = (
    ".pl8",
    ".raw",
    ".wav",
    ".sav",
    ".eng",
    ".dat",
    ".256",
    ".smk",
    ".xmi",
    ".lbm",
    ".gd8",
    ".cfg",
    ".inf",
    ".ini",
    ".mdi",
    ".dig",
    ".voc",
    ".ad",
    ".opl",
)

AIL_RE = re.compile(r"^AIL_|^AIL[A-Z]|miles|XMIDI|DIGPAK|\.DIG|\.MDI", re.I)
ERR_RE = re.compile(
    r"error|not found|not enough|cannot|failed|invalid|missing", re.I
)
FMT_RE = re.compile(r"%[-+0-9.*]*[sdxXucf]")


def load_c2eng(path: Path) -> list[str]:
    data = path.read_bytes()
    if not data.startswith(b"Textfile"):
        return []
    import struct

    first = struct.unpack_from("<I", data, 12)[0]
    n = (first - 12) // 4
    out = []
    for i in range(n):
        off = struct.unpack_from("<I", data, 12 + 4 * i)[0]
        end = data.find(b"\x00", off)
        out.append(data[off:end].decode("latin-1"))
    return out


def classify(s: str) -> str:
    low = s.lower()
    if AIL_RE.search(s) or "ail" in low and (
        "sample" in low or "driver" in low or "midi" in low
    ):
        return "miles"
    if any(low.endswith(ext) or ext in low for ext in EXTS):
        return "filename"
    if ERR_RE.search(s):
        return "error"
    if FMT_RE.search(s):
        return "format"
    if "watcom" in low or "wcompile" in low or "copyright (c) 1988" in low:
        return "runtime"
    if "dos/4" in low or "dos4g" in low or "rational" in low:
        return "extender"
    if s.startswith("smk") or "smack" in low:
        return "smacker"
    return "other"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Classify PS.EXE strings.")
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    ap.add_argument("--game", type=Path, default=DEFAULT_GAME)
    ap.add_argument("--out", type=Path, default=Path("notes/ps_strings_all.txt"))
    ap.add_argument("--limit-xrefs", type=int, default=8)
    args = ap.parse_args(argv)

    ps = load_ps(args.exe)
    mapped = map_image(ps)
    raw = extract_raw_strings(ps.data)
    eng = load_c2eng(args.game / "C2.ENG")
    eng_set = {s for s in eng if s}

    buckets: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for off, s in raw:
        buckets[classify(s)].append((off, s))

    mapped_by_text = {s: va for va, s in mapped.strings}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(f"# PS.EXE raw C-strings  n={len(raw)}\n")
        for off, s in raw:
            fh.write(f"{off:7d}\t{off:#08x}\t{s}\n")
    print(f"wrote           : {args.out}  ({len(raw)} strings)")

    print("=== classification (raw file) ===")
    for key in ("filename", "error", "miles", "smacker", "format", "runtime", "extender", "other"):
        print(f"  {key:10s} {len(buckets[key])}")

    print("\n=== filenames ===")
    for off, s in buckets["filename"]:
        print(f"  {off:#08x}  {s}")

    print("\n=== errors ===")
    for off, s in buckets["error"]:
        print(f"  {off:#08x}  {s}")

    print("\n=== Miles / AIL ===")
    for off, s in buckets["miles"]:
        print(f"  {off:#08x}  {s}")

    print("\n=== Smacker ===")
    for off, s in buckets["smacker"]:
        print(f"  {off:#08x}  {s}")

    print("\n=== format strings ===")
    for off, s in buckets["format"][:80]:
        print(f"  {off:#08x}  {s}")

    # C2.ENG overlap
    raw_set = {s for _, s in raw}
    both = sorted(eng_set & raw_set)
    only_eng = sorted(eng_set - raw_set)
    print(f"\n=== C2.ENG overlap ===")
    print(f"  eng strings     : {len(eng_set)}")
    print(f"  also in EXE     : {len(both)}")
    print(f"  ENG-only        : {len(only_eng)}")
    print("  -- also in EXE (sample) --")
    for s in both[:40]:
        print(f"    {s!r}")
    print("  -- ENG-only (labels, first 40) --")
    short = [s for s in only_eng if 0 < len(s) <= 28 and "\n" not in s]
    for s in short[:40]:
        print(f"    {s!r}")

    interesting = []
    for key in ("filename", "error", "miles"):
        interesting.extend(buckets[key])
    extra_needles = (
        "caesar2.sav",
        "lastyear.sav",
        "c2model",
        "c2.eng",
        "resource.cfg",
        "fopen",
        "AIL_set_sample",
        "6400",
    )
    print("\n=== xrefs (mapped VA -> pointer sites) ===")
    for off, s in interesting:
        va = mapped_by_text.get(s)
        if va is None:
            # try case-insensitive / substring in mapped
            hits = [v for v, t in mapped.strings if t == s]
            va = hits[0] if hits else None
        if va is None:
            continue
        xrefs = xrefs_to_va(mapped, va)
        foff = file_offset_of_va(mapped, va)
        print(
            f"  {s!r:48s}  strVA {va:#08x}  file {foff}  "
            f"xrefs={len(xrefs)} {['%#x' % x for x in xrefs[: args.limit_xrefs]]}"
        )

    # extra needles that might be lowercase in file
    print("\n=== extra mapped hits ===")
    for needle in extra_needles:
        hits = [(va, t) for va, t in mapped.strings if needle.lower() in t.lower()]
        for va, t in hits[:6]:
            xrefs = xrefs_to_va(mapped, va)
            print(f"  {t!r:48s}  VA {va:#08x}  xrefs={len(xrefs)} {[hex(x) for x in xrefs[:6]]}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
