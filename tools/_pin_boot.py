#!/usr/bin/env python3
"""Pin c2_main boot: logos, intro.smk audio, then forum1.xmi on BACKGRND.

Ghidra HTTP is down — Capstone + mapped PS.EXE + retail tree.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.ps_le import DEFAULT_EXE, MappedImage, collect_cstrings, load_ps, map_image, xrefs_to_va

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000
RETAIL = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
REPO = Path(__file__).resolve().parents[1]

# Earlier walk (findings/ghidra_walk.md)
VA_C2_MAIN = 0x10010
VA_INTRO_CALL = 0x10279
VA_XMI_CALL = 0x10288
VA_TITLE_CALL = 0x1029E
VA_SMK_PLAY = 0x5AB3D
VA_MUSIC_LOAD = 0x12279
VA_TITLE_SCREEN = 0x5D37F
VA_VIDEO_PREPARE = 0x59C87
STR_INTRO = 0x901DC
STR_FORUM1 = 0x901E6


def load_image() -> tuple[bytes, MappedImage | None, str]:
    if BIN.exists():
        return BIN.read_bytes(), None, str(BIN)
    mapped = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), mapped, str(DEFAULT_EXE)


def disasm(img: bytes, va: int, size: int) -> list[str]:
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    lines = []
    for insn in dec.disasm(img[va - BASE : va - BASE + size], va):
        lines.append(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} "
            f"{insn.mnemonic:8s} {insn.op_str}"
        )
    return lines


def cstr_at(img: bytes, va: int) -> str:
    off = va - BASE
    if off < 0 or off >= len(img):
        return "?"
    end = img.find(b"\x00", off)
    if end < 0:
        end = off + 32
    return img[off:end].decode("latin-1", errors="replace")


def find_str(img: bytes, needle: bytes) -> list[int]:
    out = []
    start = 0
    while True:
        i = img.find(needle, start)
        if i < 0:
            break
        out.append(BASE + i)
        start = i + 1
    return out


def imm_loads(img: bytes, target: int) -> list[int]:
    """VAs of mov/push that embed target as imm32."""
    needle = struct.pack("<I", target & 0xFFFFFFFF)
    hits = []
    start = 0
    while True:
        i = img.find(needle, start)
        if i < 0:
            break
        hits.append(BASE + i)
        start = i + 1
    return hits


def list_retail(exts: tuple[str, ...]) -> list[Path]:
    if not RETAIL.is_dir():
        return []
    found: list[Path] = []
    for p in RETAIL.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            found.append(p)
    return sorted(found, key=lambda p: p.name.lower())


def main() -> int:
    img, mapped, src = load_image()
    print(f"image {src} len={len(img)}")
    print()
    print("==== c2_main tail (video_prepare -> title_screen) ====")
    for line in disasm(img, 0x10240, 0xC0):
        print(line)
    eax_intro = struct.unpack_from("<I", img, 0x10279 - BASE + 1)[0]
    eax_xmi = struct.unpack_from("<I", img, 0x10288 - BASE + 1)[0]
    print(f"intro ptr {eax_intro:#x} -> {cstr_at(img, eax_intro)!r} (want {STR_INTRO:#x})")
    print(f"xmi   ptr {eax_xmi:#x} -> {cstr_at(img, eax_xmi)!r} (want {STR_FORUM1:#x})")

    print()
    print("==== filename strings (boot-ish) ====")
    names = (
        b"intro.smk",
        b"INTRO.SMK",
        b"forum1.xmi",
        b"forum2.xmi",
        b"forum3.xmi",
        b"title.xmi",
        b"cityprov.xmi",
        b"batest2.xmi",
        b"logo1.pl8",
        b"logo2.pl8",
        b"LOGO1.PL8",
        b"LOGO2.PL8",
        b"backgrnd.pl8",
        b"backgrnd.256",
        b"A01.RAW",
        b"a01.raw",
    )
    for name in names:
        vas = find_str(img, name)
        print(f"  {name.decode():16s}  {', '.join(f'{v:#x}' for v in vas) or '(none)'}")

    print()
    print("==== xrefs to those strings (imm32) ====")
    interesting = []
    for name in (b"intro.smk", b"forum1.xmi", b"forum2.xmi", b"forum3.xmi",
                 b"title.xmi", b"cityprov.xmi", b"logo1.pl8", b"logo2.pl8",
                 b"backgrnd.pl8", b"backgrnd.256"):
        for va in find_str(img, name):
            for xref in imm_loads(img, va):
                interesting.append((name.decode(), va, xref))
                print(f"  {name.decode():16s} str {va:#x}  imm @ {xref:#x}")
                for line in disasm(img, xref - 8, 0x20):
                    print(line)
                print()

    print("==== c2_main 0x10010 .. 0x10408 ====")
    for line in disasm(img, VA_C2_MAIN, 0x3F8):
        print(line)

    print()
    print("==== E8 call sites to music_load_xmi / smk_play / title_screen ====")
    for dest, label in (
        (VA_MUSIC_LOAD, "music_load_xmi"),
        (VA_SMK_PLAY, "smk_play"),
        (VA_TITLE_SCREEN, "title_screen"),
        (VA_VIDEO_PREPARE, "video_prepare_smk"),
    ):
        for va in range(BASE, BASE + min(len(img), 0x70000) - 5):
            off = va - BASE
            if img[off] != 0xE8:
                continue
            rel = struct.unpack_from("<i", img, off + 1)[0]
            if (va + 5 + rel) & 0xFFFFFFFF != dest:
                continue
            print(f"  {va:08x}  call {label} ({dest:#x})")
            for line in disasm(img, va - 12, 0x20):
                print(line)
            print()

    print("==== retail SMK / XMI / logo+backgrnd PL8 ====")
    for p in list_retail((".smk", ".xmi", ".pl8", ".256")):
        low = p.name.lower()
        if low.endswith((".smk", ".xmi")) or low.startswith(("logo", "backgrnd", "intro")):
            rel = p.relative_to(RETAIL) if RETAIL in p.parents or p.parent == RETAIL else p
            print(f"  {rel}  {p.stat().st_size} B")

    print()
    print("==== videos_new / videos intro ====")
    for root in (REPO, RETAIL):
        for folder in ("videos_new", "video", "videos"):
            d = root / folder
            if not d.is_dir():
                continue
            for p in sorted(d.iterdir()):
                if p.is_file() and p.stem.lower() == "intro":
                    print(f"  {p}  {p.stat().st_size} B")

    print()
    print("==== host plan (from this pin) ====")
    print("  LOGO1.PL8 / LOGO2.PL8 = Sierra then Impressions stills (no XMI)")
    print("  intro.smk = gold CAESAR II card; audio is SMK smackaud, not an XMI")
    print("  forum1.xmi = music_load_xmi AFTER intro, with title_screen BACKGRND+[38]")
    print("  title.xmi = not in EXE strings")
    print("  A01.RAW = Career mandate VO, not this boot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
