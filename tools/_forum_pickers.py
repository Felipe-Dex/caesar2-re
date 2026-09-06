#!/usr/bin/env python3
"""Oracle / empire tooltip pickers + HELP 58-byte topic table."""

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
OUT = ROOT / "notes" / "_forum_pickers.txt"
NUL = b"\x00"


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
            if base + i + 5 + rel == dest:
                out.append(base + i)
        i += 1
    return out


def disasm(mapped, va: int, nbytes: int) -> list[str]:
    off = mapped.va_to_off(va)
    if off is None:
        return [f"!! {va:#x} unmapped"]
    code = bytes(mapped.image[off : off + nbytes])
    dec = Cs(CS_ARCH_X86, CS_MODE_32)
    dec.detail = False
    lines = [f"==== {va:#x} ({nbytes:#x} B) ===="]
    n = 0
    for insn in dec.disasm(code, va):
        lines.append(
            f"  {insn.address:08x}  {insn.bytes.hex():24s} {insn.mnemonic:8s} {insn.op_str}"
        )
        n += 1
        if n >= 220:
            lines.append("  ...")
            break
    return lines


def find_prologue(mapped, va: int, max_back: int = 0x400) -> int:
    """Walk back for typical Watcom prologue (push ebx/esi/edi or 83 ec)."""
    img = mapped.image
    for delta in range(0, max_back, 1):
        a = va - delta
        off = mapped.va_to_off(a)
        if off is None:
            continue
        b = img[off]
        # push ebx (53) / push esi (56) / push edi (57) / sub esp
        if b in (0x53, 0x56, 0x57, 0x55) and delta > 8:
            # require a call-site landing here: previous bytes often INT3/NOP or ret of prev
            prev = img[off - 1] if off > 0 else 0
            if prev in (0xC3, 0xC2, 0x90, 0xCC) or img[off : off + 3] == bytes([0x83, 0xEC]):
                return a
        if img[off : off + 2] == bytes([0x83, 0xEC]) and delta > 8:
            return a
    return va


def edx_imm_before(mapped, call_va: int, lookback: int = 0x30) -> int | None:
    off = mapped.va_to_off(call_va - lookback)
    if off is None:
        return None
    chunk = bytes(mapped.image[off : off + lookback])
    last = None
    for k in range(0, lookback - 4):
        # mov edx, imm32  BA xx xx xx xx
        if chunk[k] == 0xBA:
            imm = struct.unpack_from("<I", chunk, k + 1)[0]
            if imm < 0x80:
                last = imm
        # xor edx,edx
        if chunk[k : k + 2] == b"\x31\xd2":
            last = 0
    return last


def main() -> None:
    L: list[str] = []
    w = L.append

    helpb = (GAME / "HELP.ENG").read_bytes()
    eng = (GAME / "C2.ENG").read_bytes()
    offs, strings, *_ = parse_textfile(eng)

    # 58-byte HELP records around first flavor ptr
    flavor0 = helpb.find(b"Thanks to our recent campaigns")
    germania = helpb.find(b"This northern province contains a large barbarian presence")
    roads = helpb.find(b"All roads lead here")
    needle = struct.pack("<I", flavor0)
    xref0 = helpb.find(needle)
    w(f"flavor0 @{flavor0} xref @{xref0} roads @{roads} germania @{germania}")

    # Try record sizes 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56, 58, 60
    names = []
    pos = offs[5]
    for i in range(50):
        end = eng.find(NUL, pos)
        names.append(eng[pos:end].decode("latin-1"))
        pos = end + 1

    flavors = []
    pos = flavor0
    for i in range(45):
        end = helpb.find(NUL, pos)
        s = helpb[pos:end].decode("latin-1")
        if s.startswith("AVE"):
            break
        flavors.append((i, pos, s))
        pos = end + 1

    # Include "All roads" as candidate pid 0 / Latium
    w(f"\nroads string @{roads}: {helpb[roads:helpb.find(NUL, roads)].decode('latin-1')!r}")
    roads_xref = helpb.find(struct.pack("<I", roads))
    w(f"roads xref @{roads_xref}  delta to flavor0 xref {xref0 - roads_xref if roads_xref>=0 else 'n/a'}")

    recsz = 58
    base = xref0
    # walk backward/forward
    w(f"\n===== HELP recs size {recsz} around flavor xref {base} =====")
    for k in range(-4, 48):
        rec = base + k * recsz
        if rec < 0 or rec + 8 > len(helpb):
            continue
        ptr = u32(helpb, rec)
        extra = helpb[rec : rec + 16].hex()
        text = ""
        if 1000 < ptr < len(helpb):
            end = helpb.find(NUL, ptr)
            text = helpb[ptr:end].decode("latin-1", "replace")[:90]
        w(f"  k={k:+3d} @{rec:6d} ptr={ptr:6d} {text!r}")

    # Also dump first 16 bytes of record at several candidate sizes using germania
    g_xref = helpb.find(struct.pack("<I", germania))
    w(f"\ngermania xref @{g_xref} delta {g_xref - xref0} /58={(g_xref-xref0)/58}")

    mapped = map_image(load_ps(GAME / "PS.EXE"), apply_fixups=True)
    calls = find_calls_to(mapped, 0x26F16)
    w(f"\n===== 0x26F16 calls with EDX imm 7..24 (oracle advice) =====")
    advice = []
    for cva in calls:
        edx = edx_imm_before(mapped, cva, 0x28)
        # also check eax
        off = mapped.va_to_off(cva - 0x28)
        eax = None
        if off is not None:
            chunk = bytes(mapped.image[off : off + 0x28])
            for k in range(0, 0x28 - 4):
                if chunk[k] == 0xB8 and chunk[k + 2 : k + 5] == b"\x00\x00\x00":
                    eax = chunk[k + 1]
        if edx is not None and 7 <= edx <= 24:
            advice.append((cva, eax, edx))
            w(f"  call {cva:#x}  EAX={eax} EDX={edx}")

    # Empire name/status
    w("\n===== 0x26F16 calls EAX=6 or 0x30 =====")
    for cva in calls:
        off = mapped.va_to_off(cva - 0x30)
        if off is None:
            continue
        chunk = bytes(mapped.image[off : off + 0x30])
        eax = None
        edx = None
        for k in range(0, 0x30 - 4):
            if chunk[k] == 0xB8 and chunk[k + 2 : k + 5] == b"\x00\x00\x00":
                eax = chunk[k + 1]
            if chunk[k] == 0xBA:
                imm = struct.unpack_from("<I", chunk, k + 1)[0]
                if imm < 0x80:
                    edx = imm
            if chunk[k : k + 2] == b"\x31\xd2":
                edx = 0
        if eax in (6, 0x30):
            w(f"  call {cva:#x} EAX={eax} EDX={edx}")

    # Full functions
    targets = [
        0x5C4C0,  # near [47] / [5]
        0x5C5A0,
        0x5C680,
        0x5EA50,  # oracle columns
        0x5EE50,  # maybe advice
        0x5EF80,
        0x60880,  # empire map?
        0x60A40,
        0x53AB1,
        0x55DC1,
        0x604F4,
        0x33B73,
    ]
    # Better: disasm from guessed prologues of key call sites
    for site in (0x5C5EE, 0x5C697, 0x5C768, 0x5C7C2, 0x5C837, 0x60AD5,
                 0x5EE8F, 0x5EEEB, 0x5EF3A, 0x5EF8B, 0x5EFDD, 0x5F0B5,
                 0x5EBB9):
        pro = find_prologue(mapped, site, 0x300)
        w(f"\nprologue near {site:#x} -> {pro:#x}")

    w("\n")
    L.extend(disasm(mapped, 0x5C4E0, 0x400))
    w("\n")
    L.extend(disasm(mapped, 0x60980, 0x280))
    w("\n")
    L.extend(disasm(mapped, 0x5EE70, 0x280))
    w("\n")
    L.extend(disasm(mapped, 0x5EAF0, 0x80))

    # kind 4 input: search for stores to advice skip / [0x117A5C]=4
    img = mapped.image
    base = mapped.base
    w("\n===== mov [0x117A5C], 4 =====")
    pat = bytes.fromhex("C705 5C7A1100 04000000")
    i = 0
    while True:
        j = img.find(pat, i)
        if j < 0:
            break
        w(f"  {base+j:#x}")
        i = j + 1
    # any disp 5C7A1100
    w("===== disp 0x117A5C =====")
    n = 0
    i = 0
    needle = bytes.fromhex("5C7A1100")
    while n < 40:
        j = img.find(needle, i)
        if j < 0:
            break
        ctx = img[max(0, j - 3) : j + 8]
        w(f"  {base+j:#x}  {ctx.hex()}")
        i = j + 1
        n += 1

    OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size})")


if __name__ == "__main__":
    main()
