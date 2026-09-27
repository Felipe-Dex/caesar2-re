#!/usr/bin/env python3
"""Pin Forum Oracle: RAT_BACK/RAT_FRON, [31] labels, hitboxes, B-series RAW.

Ghidra HTTP down — Capstone + retail PL8. Column click 0x3d843 → 0x343c3
→ picker 0x57450 (jmp 0x135a4 EAX=0x1f..0x2c). Draw 0x5e9eb / advice 0x5f033.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.assets import load_eng, load_pl8_sprites_xy
from app.config import find_file, resolve_game_dir
from app.forum import (
    KIND_CHROME,
    KIND_ORACLE,
    ForumState,
    _oracle_column,
    button_rect,
    click_forum,
    oracle_advice_id,
    oracle_advice_skip,
    oracle_raw_index,
    oracle_raw_stem,
    rating_need,
    selftest as forum_selftest,
)
from app.city_sim import SimState
from tools.ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000
RAW_BANK = 0x93694
OUT = Path(__file__).resolve().parents[1] / "notes" / "_pin_oracle.txt"

# Picker EAX for live advice ids 1–6, 9–16 (Peace stubs 7/8 never written).
LIVE_IDS = (1, 2, 3, 4, 5, 6, 9, 10, 11, 12, 13, 14, 15, 16)
EAX0 = 0x1F


def load_image() -> tuple[bytes, str]:
    if BIN.exists():
        return BIN.read_bytes(), str(BIN)
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image), str(DEFAULT_EXE)


def dump_asm(img: bytes, va: int, nbytes: int, title: str, lines: list[str]) -> None:
    off = va - BASE
    if off < 0 or off >= len(img):
        lines.append(f"!! {title} {va:#x} out of range")
        return
    code = img[off : off + nbytes]
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    lines.append(f"\n==== {title} {va:#x}..{va + nbytes:#x} ====")
    n = 0
    for insn in dec.disasm(code, va):
        lines.append(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} "
            f"{insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= 240:
            lines.append("  ...")
            break


def cstr(img: bytes, va: int) -> str:
    off = va - BASE
    if off < 0 or off >= len(img):
        return "?"
    end = img.find(b"\x00", off)
    if end < 0:
        end = off + 16
    return img[off:end].decode("latin-1", errors="replace")


def bank_name(img: bytes, idx: int) -> str:
    off = RAW_BANK - BASE + idx * 8
    return img[off : off + 8].split(b"\x00", 1)[0].decode("ascii", errors="replace")


def main() -> int:
    img, src = load_image()
    lines: list[str] = [f"image {src} len={len(img)}"]

    for va, name in (
        (0x90D60, "load ebx=0x300"),
        (0x90D6D, "load ebx=0xc350"),
        (0x90D1D, "load ebx=0x300"),
        (0x90CDE, "load ebx=0xea60"),
        (0x90D7A, "blit edx=0x1e0"),
        (0x90D27, "forum.pl8"),
    ):
        lines.append(f"  str {va:#x} {cstr(img, va)!r}  ({name})")

    dump_asm(img, 0x5E970, 0x80, "oracle load rat_back/forum", lines)
    dump_asm(img, 0x5E9EB, 0x280, "oracle draw columns 0x5e9eb", lines)
    dump_asm(img, 0x5EB70, 0x80, "oracle city_only 0x5eb81", lines)
    dump_asm(img, 0x3D843, 0x90, "kind 0xA click hitboxes", lines)
    dump_asm(img, 0x343C3, 0x20, "column click → picker", lines)
    dump_asm(img, 0x135A4, 0x40, "raw_name_from_index 0x135a4", lines)
    dump_asm(img, 0x5F033, 0xA0, "advice draw + city-only id 17", lines)

    lines.append("\n==== raw bank 0x1f..0x2c (advice EAX) ====")
    for i, aid in enumerate(LIVE_IDS):
        idx = EAX0 + i
        lines.append(f"  id {aid:2d} EAX {idx:#x} ({idx:2d}) {bank_name(img, idx)}")

    game, how = resolve_game_dir()
    lines.append(f"\ngame {game} ({how})")
    for name in ("RAT_BACK.PL8", "RAT_BACK.256", "RAT_FRON.PL8", "FORUM.PL8"):
        path = find_file(game, name)
        lines.append(f"  {name}: {path}")

    try:
        back = load_pl8_sprites_xy(game, "RAT_BACK.PL8")
        fron = load_pl8_sprites_xy(game, "RAT_FRON.PL8")
        lines.append(f"  RAT_BACK sprites {len(back)}")
        for i, (im, x, y) in enumerate(back[:8]):
            lines.append(f"    [{i}] {im.size} xy=({x},{y}) mode={im.mode}")
        lines.append(f"  RAT_FRON sprites {len(fron)}")
        for i, (im, x, y) in enumerate(fron[:12]):
            lines.append(f"    [{i}] {im.size} xy=({x},{y}) mode={im.mode}")
    except (OSError, ValueError, FileNotFoundError) as exc:
        lines.append(f"  PL8 fail {exc}")

    sound = game / "sound"
    if not sound.is_dir():
        sound = game / "SOUND"
    if sound.is_dir():
        bnames = sorted(p.name for p in sound.iterdir() if p.name.upper().startswith("B"))
        lines.append(f"  sound/ B* ({len(bnames)}): {', '.join(bnames[:24])}")
    else:
        root_b = sorted(p.name for p in game.iterdir() if p.name.upper().startswith("B0"))
        lines.append(f"  install B0* {root_b[:20]}")

    eng = load_eng(game)
    if eng:
        lines.append("\n==== C2.ENG [31]+0..7 / +24 ====")
        for skip in (0, 1, 2, 3, 4, 5, 6, 7, 24):
            got = eng.skip(31, skip) or ""
            lines.append(f"  +{skip:2d} {got[:90]!r}")
        lines.append(f"  [33]+3 {(eng.skip(33, 3) or '')[:60]!r}")

    lines.append("\n==== host oracle helpers ====")
    for aid in LIVE_IDS:
        lines.append(f"  id {aid} stem {oracle_raw_stem(aid)} idx {oracle_raw_index(aid)}")
    sim = SimState(city_only=1, skill=2, tax_wealth=4)
    lines.append(f"  city-only Empire id {oracle_advice_id(sim, 0)} skip {oracle_advice_skip(sim, 0)}")
    lines.append(f"  city-only Need {rating_need(sim)}")
    ox, oy, ow, oh = 10, 0x164, 0x8C, 0x21
    state = ForumState(kind=KIND_ORACLE)
    click_forum(state, ox + 4, oy + 4, sim)
    lines.append(f"  hit Empire advice={state.oracle_advice} sfx={state.oracle_sfx!r}")
    click_forum(state, ox + 160 * 2 + 4, oy + 4, sim)
    lines.append(f"  hit Prosperity advice={state.oracle_advice} sfx={state.oracle_sfx!r}")
    ex, ey, _ew, _eh = button_rect(2)
    stub = click_forum(ForumState(kind=KIND_CHROME), ex + 2, ey + 2, sim)
    lines.append(f"  EMPIRE MAP stub {stub[:48]!r}")

    lines.append("\n==== forum selftest ====")
    failed = 0
    for line in forum_selftest():
        lines.append(f"  {line}")
        if "FAIL" in line:
            failed += 1

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size})")
    for line in lines:
        if line.startswith("====") or "FAIL" in line or line.startswith("  str") or "stem" in line or "sprites" in line or "Need" in line or "hit " in line or "stub" in line:
            print(line)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
