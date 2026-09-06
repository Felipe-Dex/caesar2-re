#!/usr/bin/env python3
"""Phase 2: HELP flavor pack + EXE picker (ASCII-only output)."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.extract_eng import parse_textfile, u32
from tools.ps_le import load_ps, map_image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
NUL = b"\x00"
OUT = ROOT / "notes" / "_forum_strings_dump2.txt"


def packed_from(data: bytes, start: int, n: int = 80) -> list[tuple[int, int, str]]:
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


def find_calls_to(mapped, dest: int, lo: int = 0x10000, hi: int = 0x90000) -> list[int]:
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


def disasm_at(mapped, va: int, nbytes: int = 0x120) -> list[str]:
    off = mapped.va_to_off(va)
    if off is None:
        return [f"  !! {va:#x} not mapped"]
    code = bytes(mapped.image[off : off + nbytes])
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    lines = [f"---- {va:#x} ({nbytes:#x} B) ----"]
    n = 0
    for insn in dec.disasm(code, va):
        lines.append(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= 160:
            lines.append("  ...")
            break
    return lines


def window(mapped, va: int, before: int = 0x60, after: int = 0x40) -> list[str]:
    return disasm_at(mapped, va - before, before + after)


def parse_help_topics(data: bytes, w) -> None:
    w("\n===== HELP.ENG topic-table guess =====")
    # After 8-byte magic + 58 zeros, payload at 66.
    # Record hunt: (u32 off, u32 extra, name...) repeating.
    pos = 66
    recs = []
    while pos + 8 < 116008:
        off = u32(data, pos)
        extra = u32(data, pos + 4)
        # filename-ish?
        name_end = data.find(NUL, pos + 8)
        if name_end < 0 or name_end - (pos + 8) > 32:
            break
        name = data[pos + 8 : name_end].decode("latin-1", "replace")
        if not (20 <= off < len(data)):
            break
        recs.append((pos, off, extra, name))
        pos = name_end + 1
        # align?
        while pos < 116008 and data[pos] == 0:
            pos += 1
        if len(recs) > 80:
            break
    w(f"  naive name-records: {len(recs)}")
    for i, (p, off, extra, name) in enumerate(recs[:20]):
        w(f"    rec{i} @{p} off={off} extra={extra} name={name!r}")

    # Alternative: fixed 8-byte records from 66
    w("\n===== HELP.ENG u32 pairs from 66 =====")
    for i in range(20):
        a = u32(data, 66 + 8 * i)
        b = u32(data, 70 + 8 * i)
        w(f"  [{i:3d}] {a:10d} {b:10d}  hex {a:08x} {b:08x}")

    # Topic IDs in text (#digits#)
    import re

    ids = [int(x) for x in re.findall(rb"#(\d{2,5})#", data)]
    w(f"\n  #N# ids in HELP: {len(ids)} unique={len(set(ids))} min={min(ids) if ids else None} max={max(ids) if ids else None}")
    # look for table of those ids pointing at flavor
    flavor0 = data.find(b"Thanks to our recent campaigns")
    germania = data.find(b"This northern province contains a large barbarian presence")
    w(f"  flavor0 @{flavor0} germania @{germania}")


def main() -> None:
    lines: list[str] = []

    def w(s: str = "") -> None:
        lines.append(s)

    eng = (GAME / "C2.ENG").read_bytes()
    offs, strings, _pad, _u = parse_textfile(eng)
    helpb = (GAME / "HELP.ENG").read_bytes()

    # Province names 0..49 from [5]
    names = packed_from(eng, offs[5], 50)
    w("===== [5] names =====")
    for i, off, s in names:
        w(f"  +{i:3d} {s}")

    # Flavor pack: walk from first romanized line
    start = helpb.find(b"Thanks to our recent campaigns")
    rows = packed_from(helpb, start, 60)
    w(f"\n===== HELP flavor walk from @{start} =====")
    stop_at = None
    for i, off, s in rows:
        if s.startswith("AVE") or "Creation of the Roman Empire" in s:
            stop_at = i
            w(f"  +{i:3d} @{off} STOP {s[:60]!r}")
            break
        shown = s.replace("\r", "\\r").replace("\n", "\\n")
        w(f"  +{i:3d} @{off:6d} ({len(s):3d}) {shown}")
    w(f"  flavor count before history: {stop_at}")

    # Also walk a bit BEFORE flavor0 in case there is a conquered pack
    pre = start
    while pre > 0 and helpb[pre - 1] == 0:
        pre -= 1
    # rewind a few strings
    rewind = start
    for _ in range(8):
        if rewind < 2:
            break
        rewind -= 1
        while rewind > 0 and helpb[rewind - 1] != 0:
            rewind -= 1
    w(f"\n===== HELP strings just before flavor0 (from @{rewind}) =====")
    for i, off, s in packed_from(helpb, rewind, 12):
        shown = s.replace("\n", "\\n")[:120]
        w(f"  pre+{i:3d} @{off:6d} ({len(s):3d}) {shown}")

    parse_help_topics(helpb, w)

    # Hunt u32 table that points at each flavor start
    flavor_offs = [off for i, off, s in rows[:stop_at or 0]]
    flavor_set = set(flavor_offs)
    w(f"\n===== u32 ptrs to flavor starts ({len(flavor_offs)}) =====")
    imgh = helpb
    found_tables = []
    i = 0
    while i + 4 <= len(imgh):
        v = u32(imgh, i)
        if v in flavor_set:
            # extend
            seq = []
            j = i
            while j + 4 <= len(imgh):
                vv = u32(imgh, j)
                if vv in flavor_set:
                    seq.append((j, vv, flavor_offs.index(vv)))
                    j += 4
                else:
                    break
            if len(seq) >= 8:
                found_tables.append((i, seq))
                i = j
                continue
        i += 4
    w(f"  tables (>=8 consecutive flavor ptrs): {len(found_tables)}")
    for off, seq in found_tables[:8]:
        idxs = [t[2] for t in seq]
        w(f"  @{off} n={len(seq)} idxs={idxs[:20]}{'...' if len(idxs)>20 else ''}")

    # Also search whole HELP for each flavor offset as u32 (may be sparse)
    w("\n===== individual u32 xrefs to first/last/germania flavor =====")
    germania = helpb.find(b"This northern province contains a large barbarian presence")
    achaea = helpb.find(b"The Greeks' constant squabbling")
    for label, tgt in (("flavor0", flavor_offs[0] if flavor_offs else -1),
                       ("achaea?", achaea),
                       ("germania", germania),
                       ("last", flavor_offs[stop_at - 1] if stop_at else -1)):
        if tgt < 0:
            continue
        needle = struct.pack("<I", tgt)
        hits = []
        p = 0
        while True:
            j = imgh.find(needle, p)
            if j < 0:
                break
            hits.append(j)
            p = j + 1
        w(f"  {label} @{tgt}: {len(hits)} xrefs {hits[:12]}")

    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    img = mapped.image
    base = mapped.base
    w(f"\n===== EXE base {base:#x} =====")

    calls_263 = find_calls_to(mapped, 0x263CC)
    calls_26f = find_calls_to(mapped, 0x26F16)
    calls_270 = find_calls_to(mapped, 0x27071)
    w(f"  calls 0x263CC: {len(calls_263)}")
    w(f"  calls 0x26F16: {len(calls_26f)}")
    w(f"  calls 0x27071: {len(calls_270)}")

    # For each eng-draw call, look back 0x30 bytes for mov eax, imm
    def eax_imm_before(call_va: int, lookback: int = 0x40) -> int | None:
        off = mapped.va_to_off(call_va - lookback)
        if off is None:
            return None
        chunk = bytes(img[off : off + lookback])
        # last B8 xx 00 00 00 before the call
        last = None
        for k in range(0, lookback - 4):
            if chunk[k] == 0xB8 and chunk[k + 2 : k + 5] == b"\x00\x00\x00":
                last = chunk[k + 1]
        return last

    want = {0x06, 0x1D, 0x20, 0x21, 0x22, 0x26, 0x30}
    w("\n===== eng-draw calls with mov eax, slot+1 nearby =====")
    by_slot: dict[int, list[int]] = {s: [] for s in want}
    for cva in calls_26f + calls_270:
        imm = eax_imm_before(cva)
        if imm in want:
            by_slot[imm].append(cva)
    for s in sorted(want):
        vas = by_slot[s]
        w(f"  EAX={s:#x} ({len(vas)}): " + ", ".join(f"{v:#x}" for v in vas[:20]))

    # Dump windows around [31] and [5]/[47] calls
    w("\n===== windows: EAX=0x20 ([31] oracle) =====")
    for va in by_slot.get(0x20, [])[:12]:
        lines.extend(window(mapped, va, 0x80, 0x20))

    w("\n===== windows: EAX=0x06 ([5] names) =====")
    for va in by_slot.get(0x06, [])[:16]:
        lines.extend(window(mapped, va, 0x50, 0x18))

    w("\n===== windows: EAX=0x30 ([47] conquered) =====")
    for va in by_slot.get(0x30, [])[:12]:
        lines.extend(window(mapped, va, 0x70, 0x18))

    # forum_panel_draw and empire suspects
    w("\n===== forum_panel_draw 0x33B73 =====")
    lines.extend(disasm_at(mapped, 0x33B73, 0x300))

    w("\n===== 0x53AB1 =====")
    lines.extend(disasm_at(mapped, 0x53AB1, 0x200))
    w("\n===== 0x55DC1 =====")
    lines.extend(disasm_at(mapped, 0x55DC1, 0x200))
    w("\n===== 0x604F4 =====")
    lines.extend(disasm_at(mapped, 0x604F4, 0x200))

    # help.eng string xrefs
    hay = bytes(img)
    for needle in (b"help.eng", b"HELP.ENG"):
        p = hay.find(needle)
        w(f"  exe {needle!r} mapped-off {p}")

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
