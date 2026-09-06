#!/usr/bin/env python3
"""Local-only dump of Forum/Oracle/Empire string packs + EXE picker xrefs.

Does not write a full C2.ENG/HELP.ENG dump into the repo.
"""

from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.extract_eng import parse_textfile, u32
from tools.ps_le import load_ps, map_image, xrefs_to_va

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
NUL = b"\x00"


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


def show_pack(label: str, rows: list[tuple[int, int, str]], maxlen: int = 220) -> None:
    print(f"\n===== {label}  ({len(rows)} strings) =====")
    for i, off, s in rows:
        shown = s.replace("\r", "\\r").replace("\n", "\\n")
        if len(shown) > maxlen:
            shown = shown[: maxlen - 3] + "..."
        print(f"  +{i:3d} @{off:6d} ({len(s):4d}) {shown}")


def ascii_runs(data: bytes, minu: int = 8) -> list[tuple[int, str]]:
    out = []
    cur: list[str] = []
    start = 0
    for i, b in enumerate(data):
        if 32 <= b < 127:
            if not cur:
                start = i
            cur.append(chr(b))
        else:
            if len(cur) >= minu:
                out.append((start, "".join(cur)))
            cur = []
    if len(cur) >= minu:
        out.append((start, "".join(cur)))
    return out


def parse_help(data: bytes) -> None:
    print("\n===== HELP.ENG header =====")
    print(f"  magic={data[:8]!r} size={len(data)}")
    zeros = 0
    for b in data[8:]:
        if b != 0:
            break
        zeros += 1
    print(f"  zeros after magic: {zeros}  first nonzero @{8 + zeros}")
    pos = 8 + zeros
    print(f"  u32s @{pos}: {[u32(data, pos + 4 * i) for i in range(8)]}")

    # Try offset table: first u32 often points at pool / record table
    first = u32(data, pos)
    print(f"  first u32={first} (in file={0 <= first < len(data)})")

    # Scan for 44-ish consecutive file offsets that land on flavor-like text
    germania = b"This northern province contains a large barbarian presence"
    g_off = data.find(germania)
    print(f"  germania flavor @{g_off}")

    # Walk NUL strings around that hit
    if g_off >= 0:
        # rewind to start of this C-string
        start = g_off
        while start > 0 and data[start - 1] != 0:
            start -= 1
        print("\n===== HELP.ENG strings around Germania flavor =====")
        pos = start
        for i in range(80):
            end = data.find(NUL, pos)
            if end < 0:
                break
            s = data[pos:end].decode("latin-1", "replace")
            if s:
                shown = s.replace("\r", "\\r").replace("\n", "\\n")
                if len(shown) > 200:
                    shown = shown[:197] + "..."
                print(f"  help+{i:3d} @{pos:6d} ({len(s):4d}) {shown}")
            pos = end + 1
            if pos > g_off + 20000:
                break

    # Broader: all long prose that looks like province flavor
    print("\n===== HELP.ENG long prose (80+ chars, province-ish) =====")
    flavor_re = re.compile(
        r"(province|barbarian|resources|conquer|empire|trade|wheat|wine|gold|iron|"
        r"gaul|hispan|africa|egypt|britain|germania|macedonia|greece|asia|syria|"
        r"unconquer|roman|legion|harbor|harbour|forest|mountain|coast)",
        re.I,
    )
    n = 0
    for off, s in ascii_runs(data, 40):
        if len(s) < 80:
            continue
        if not flavor_re.search(s):
            continue
        # skip help-system chrome
        if s.lower().startswith(("click", "right click", "press ", "use the")):
            continue
        shown = s if len(s) <= 220 else s[:217] + "..."
        print(f"  @{off:6d} ({len(s):4d}) {shown}")
        n += 1
    print(f"  (matched {n})")

    # Hunt a table of file offsets pointing at flavor starts
    print("\n===== HELP.ENG offset-table hunt (u32 → long string) =====")
    long_starts = []
    pos = 0
    while True:
        end = data.find(NUL, pos)
        if end < 0:
            break
        if end - pos >= 60:
            long_starts.append(pos)
        pos = end + 1 if end >= pos else pos + 1
    long_set = set(long_starts)
    print(f"  long C-strings (>=60): {len(long_starts)}")

    # sliding window of 40+ consecutive u32s that are all in long_set
    best = []
    i = 0
    while i + 4 <= len(data):
        vals = []
        j = i
        while j + 4 <= len(data):
            v = u32(data, j)
            if v in long_set:
                vals.append((j, v))
                j += 4
            else:
                break
        if len(vals) >= 20:
            best.append((i, vals))
            i = j
        else:
            i += 4
    print(f"  runs of >=20 consecutive long-string ptrs: {len(best)}")
    for off, vals in best[:12]:
        print(f"  table @{off} count={len(vals)} first={vals[0][1]} last={vals[-1][1]}")
        for k, (slot_off, tgt) in enumerate(vals[:8]):
            end = data.find(NUL, tgt)
            s = data[tgt:end].decode("latin-1", "replace")
            shown = s[:80].replace("\n", "\\n")
            print(f"    [{k:3d}] -> @{tgt} {shown!r}")

    # Also try: 44 consecutive u32s in a tight range even if not all long
    print("\n===== HELP.ENG 44-wide u32 tables landing in string pool =====")
    pool_lo, pool_hi = 10000, len(data)
    hits = 0
    i = 0
    while i + 44 * 4 <= len(data) and hits < 15:
        vals = [u32(data, i + 4 * k) for k in range(44)]
        ok = all(pool_lo <= v < pool_hi for v in vals)
        if ok and all(vals[k] < vals[k + 1] or vals[k] == 0 for k in range(43)):
            # monotonic-ish
            increasing = sum(1 for k in range(43) if vals[k] < vals[k + 1])
            if increasing >= 36:
                print(f"  @{i} monotonic {increasing}/43  first={vals[0]} last={vals[-1]}")
                for k in (0, 1, 15, 16, 32, 43):
                    tgt = vals[k]
                    end = data.find(NUL, tgt)
                    s = data[tgt:end].decode("latin-1", "replace")[:90]
                    print(f"    pid? {k:2d} -> @{tgt} {s!r}")
                hits += 1
                i += 44 * 4
                continue
        i += 4


def find_calls_to(mapped, dest: int, lo: int = 0x10000, hi: int = 0x80000) -> list[int]:
    img = mapped.image
    start = mapped.va_to_off(lo) or 0
    end = mapped.va_to_off(hi) or len(img)
    base = mapped.base
    out = []
    i = start
    while i < end - 5:
        if img[i] == 0xE8:
            rel = struct.unpack_from("<i", img, i + 1)[0]
            tgt = base + i + 5 + rel
            if tgt == dest:
                out.append(base + i)
        i += 1
    return out


def disasm_range(mapped, va: int, nbytes: int = 0x200) -> None:
    off = mapped.va_to_off(va)
    if off is None:
        print(f"  !! {va:#x} not mapped")
        return
    code = bytes(mapped.image[off : off + nbytes])
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    print(f"\n---- disasm {va:#x} ({nbytes:#x} bytes) ----")
    n = 0
    for insn in dec.disasm(code, va):
        print(f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}")
        n += 1
        if n >= 180:
            print("  ...")
            break


def scan_slot_immediates(mapped) -> None:
    """Find mov eax, imm32 for official-slot+1 values used with eng draw."""
    img = mapped.image
    base = mapped.base
    wanted = {
        0x06: "[5] names EAX=6",
        0x1D: "[28] buttons EAX=29",
        0x1F: "[30] career EAX=31",
        0x20: "[31] oracle EAX=32",
        0x21: "[32] scribe EAX=33",
        0x22: "[33] empire chrome EAX=34",
        0x26: "[37] rome EAX=38",
        0x30: "[47] select/conquered EAX=48",
    }
    print("\n===== mov eax, slot+1  (B8 xx 00 00 00) =====")
    for imm, label in wanted.items():
        pat = bytes([0xB8, imm, 0, 0, 0])
        hits = []
        i = 0
        while True:
            j = img.find(pat, i)
            if j < 0:
                break
            hits.append(base + j)
            i = j + 1
        print(f"  {label}: {len(hits)} hits")
        for va in hits[:30]:
            print(f"    {va:#x}")


def main() -> None:
    eng_path = GAME / "C2.ENG"
    help_path = GAME / "HELP.ENG"
    eng = eng_path.read_bytes()
    offs, strings, pad, unique = parse_textfile(eng)
    print(f"C2.ENG n={len(strings)} unique={unique} pad={pad}")

    packs = {
        5: (50, "province names [5]"),
        28: (32, "forum buttons + treasurer [28]"),
        30: (50, "career / ratings chrome [30]"),
        31: (40, "oracle [31]"),
        32: (20, "scribe [32]"),
        33: (16, "empire chrome [33]"),
        37: (45, "ROME [37]"),
        47: (24, "province select / conquered [47]"),
    }
    for slot, (n, label) in packs.items():
        rows = packed_from(eng, offs[slot], n)
        show_pack(f"[{slot}] {strings[slot]!r} — {label}", rows)

    parse_help(help_path.read_bytes())

    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    print(f"\n===== EXE mapped {len(mapped.image)} base {mapped.base:#x} =====")
    scan_slot_immediates(mapped)

    for dest, name in (
        (0x263CC, "c2_eng lookup 0x263CC"),
        (0x26F16, "eng draw 0x26F16"),
        (0x27071, "eng wrap 0x27071"),
        (0x33B73, "forum_panel_draw"),
        (0x53AB1, "53ab1 empire?"),
        (0x55DC1, "55dc1 empire?"),
        (0x604F4, "604f4 empire?"),
    ):
        try:
            xrs = list(xrefs_to_va(mapped, dest))
        except Exception:
            xrs = find_calls_to(mapped, dest)
        print(f"\n  xrefs → {name}: {len(xrs)}")
        for va in xrs[:40]:
            print(f"    {va:#x}")

    # Kind-4 / oracle: dump forum_panel_draw and a window around EAX=0x20 hits
    disasm_range(mapped, 0x33B73, 0x280)
    for va in (0x53AB1, 0x55DC1, 0x604F4):
        disasm_range(mapped, va, 0x180)


if __name__ == "__main__":
    main()
