#!/usr/bin/env python3
"""Pin EXE random fire / disease start vs 41DD4.

Retail 1.1A:
- 41DD4 (slots 0x9E–0xA1) is burn timer / spread / collapse / rioter only.
  No 69A37 from a cold house. No Fire-labour climb.
- 44F87: Fire rate [0x102738] += 100 − prevention. prevention = 45200
  assigned×100/need (D2E74/D2E78), cap 100; need 0 → 100. At 100% the
  addend is 0 and [0x10271c] stays 0xf423f → 445AF lottery never arms.
- 445AF 448F7: disease lottery 693BB + 58c87 EAX=0x51. Counts leftover
  +11&0x30. Hospital cover 45398 is Query / 40D08, not this latch.
- Disasters menu (host) is 69A37 / +11 0x30 and ignores labour / cover.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.ps_le import DEFAULT_EXE, MappedImage, load_ps, map_image

BIN = Path(__file__).resolve().parents[1] / "ghidra_work" / "c2_x.bin"
BASE = 0x10000
OUT = Path(__file__).resolve().parents[1] / "notes" / "_pin_fire_disease_start.txt"


def load_image() -> bytes:
    if BIN.exists():
        return BIN.read_bytes()
    mapped: MappedImage = map_image(load_ps(DEFAULT_EXE), apply_fixups=True)
    return bytes(mapped.image)


def find_calls_to(img: bytes, dest: int, lo: int, hi: int) -> list[int]:
    hits = []
    off = lo - BASE
    span = hi - lo
    i = 0
    while i < span - 4:
        if img[off + i] == 0xE8:
            rel = struct.unpack_from("<i", img, off + i + 1)[0]
            if lo + i + 5 + rel == dest:
                hits.append(lo + i)
        i += 1
    return hits


def main() -> int:
    img = load_image()
    lines: list[str] = []
    fail = 0

    ignite_in_41dd4 = find_calls_to(img, 0x69A37, 0x41DD4, 0x42236)
    if ignite_in_41dd4:
        fail += 1
        lines.append(f"FAIL  41DD4 calls 69A37 at {ignite_in_41dd4}")
    else:
        lines.append("ok    41DD4 has no CALL 69A37 (no random start)")

    if img[0x44F8B - BASE : 0x44F8B - BASE + 10] == bytes.fromhex(
        "c7051c2710003f420f00"
    ):
        lines.append("ok    44F87 latches [0x10271c]=0xf423f")
    else:
        fail += 1
        lines.append("FAIL  44F87 [0x10271c] latch")

    if img[0x44F95 - BASE : 0x44F95 - BASE + 7] == bytes.fromhex(
        "833d782e0d0000"
    ):
        lines.append("ok    44F87 skips when Fire need [0xD2E78]==0")
    else:
        fail += 1
        lines.append("FAIL  44F87 Fire-need gate")

    if img[0x4522E - BASE : 0x4522E - BASE + 5] == bytes.fromhex("a1742e0d00"):
        lines.append("ok    45200 prevention = assigned [0xD2E74] / need")
    else:
        fail += 1
        lines.append("FAIL  45200 assigned load")

    if img[0x448F7 - BASE] == 0xE8:
        rel = struct.unpack_from("<i", img, 0x448F8 - BASE)[0]
        dest = 0x448F7 + 5 + rel
        if dest == 0x693BB:
            lines.append("ok    445AF 448F7 CALL 693BB (disease lottery)")
        else:
            fail += 1
            lines.append(f"FAIL  448F7 calls {dest:#x} want 693BB")
    else:
        fail += 1
        lines.append("FAIL  448F7 not a CALL")

    if img[0x44907 - BASE : 0x44907 - BASE + 5] == bytes.fromhex("b851000000"):
        lines.append("ok    445AF 44907 EAX=0x51 Disease banner")
    else:
        fail += 1
        lines.append("FAIL  44907 Disease EAX")

    lines.append(
        "rule  Fire labour 100% -> 45200 prevention 100 -> 44F87 addend 0 "
        "-> no 445AF fire lottery"
    )
    lines.append(
        "rule  41DD4 never plants +11 0x30; hospital 45398 / baths +13&8 "
        "are Query/40D08, not a disease roll on this slot"
    )
    lines.append(
        "rule  45398: 0 if n=0; 100 if pop<100; else n*1000*100/pop"
    )
    lines.append(
        "rule  Disasters menu (host debug_ignite/infect) ignores labour "
        "and cover - that is the cheat, not the sim clock"
    )

    text = "\n".join(lines) + "\n"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"wrote {OUT}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
