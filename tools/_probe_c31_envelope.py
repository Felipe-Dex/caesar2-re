#!/usr/bin/env python3
"""C31 last-speech envelope + string hunt. Local only."""

from __future__ import annotations

import re
import struct
from pathlib import Path

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
RATE = 22050


def last_active(data: bytes, thresh: int = 10, mid: int = 0x7F) -> dict:
    last = -1
    for i in range(len(data) - 1, -1, -1):
        if abs(data[i] - mid) >= thresh:
            last = i
            break
    return {
        "last_i": last,
        "last_s": last / RATE if last >= 0 else None,
        "remain_s": (len(data) - 1 - last) / RATE if last >= 0 else None,
    }


def bursts(data: bytes, mid: int = 0x7F, sil_tol: int = 4, min_gap: int = 2205, min_act: int = 1102):
    silent = [abs(b - mid) <= sil_tol for b in data]
    out = []
    i = 0
    n = len(data)
    while i < n:
        while i < n and silent[i]:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and not silent[j]:
            j += 1
        # merge short gaps
        k = j
        while k < n and silent[k] and (k - j) < min_gap:
            k += 1
        if k < n and not silent[k] and (k - j) < min_gap:
            continue  # will extend on next? simpler: absorb
        if j - i >= min_act:
            out.append((i, j))
        i = j if k == j else j
        if k > j and k < n and not silent[k]:
            # restart from i to include gap-merged — do a cleaner pass below
            pass
        i = j
    return out


def bursts2(data: bytes, mid: int = 0x7F, sil_tol: int = 4, merge_gap: int = 2205, min_act: int = 800):
    n = len(data)
    active = [abs(b - mid) > sil_tol for b in data]
    segs = []
    i = 0
    while i < n:
        while i < n and not active[i]:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and active[j]:
            j += 1
        segs.append([i, j])
        i = j
    merged = []
    for s, e in segs:
        if merged and s - merged[-1][1] <= merge_gap:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged if e - s >= min_act]


def window_std(data: bytes, start: int, win: int = 512) -> float:
    chunk = data[start : start + win]
    if not chunk:
        return 0.0
    m = sum(chunk) / len(chunk)
    return (sum((x - m) ** 2 for x in chunk) / len(chunk)) ** 0.5


def main() -> None:
    raw = (GAME / "C31.RAW").read_bytes()
    c32 = (GAME / "C32.RAW").read_bytes()
    print(f"C31 {len(raw)} B {len(raw)/RATE:.3f}s")
    for th in (6, 8, 10, 16, 24):
        info = last_active(raw, th)
        print(f"  last |s-7F|>={th}: i={info['last_i']} t={info['last_s']:.3f}s remain={info['remain_s']:.3f}s")

    print("C31 bursts (merged gaps <=100ms):")
    bs = bursts2(raw)
    for s, e in bs:
        print(f"  {s/RATE:6.2f}s .. {e/RATE:6.2f}s  dur={(e-s)/RATE:.2f}s  std={window_std(raw, s, e-s):.1f}")
    if bs:
        print(f"  last burst end -> EOF gap: {(len(raw)-bs[-1][1])/RATE:.3f}s")

    print("C31 last 1.0s windows (50ms):")
    start = max(0, len(raw) - RATE)
    for off in range(start, len(raw), RATE // 20):
        w = raw[off : off + RATE // 20]
        m = sum(w) / len(w)
        sd = (sum((x - m) ** 2 for x in w) / len(w)) ** 0.5
        print(f"  t={off/RATE:6.3f} n={len(w)} std={sd:5.1f} min={min(w):3d} max={max(w):3d}")

    print("C32 first bursts:")
    bs32 = bursts2(c32)
    for s, e in bs32[:6]:
        print(f"  {s/RATE:6.2f}s .. {e/RATE:6.2f}s  dur={(e-s)/RATE:.2f}s")
    print(f"  C32 burst count={len(bs32)} total_active={sum(e-s for s,e in bs32)/RATE:.2f}s")

    # lead silence
    i = 0
    while i < len(c32) and c32[i] == 0x7F:
        i += 1
    print(f"C32 lead exact 7F: {i} ({i/RATE:.3f}s) first_nonzero_delta at {i}")

    print("\n=== string hunt ===")
    needles = [
        b"danger",
        b"DANGER",
        b"Danger",
        b"resources",
        b"RESOURCES",
        b"worth the",
        b"WORTH",
        b"C31",
        b"c31",
        b".RAW",
        b".raw",
    ]
    # scan interesting game files
    paths = list(GAME.glob("*"))
    for p in paths:
        if not p.is_file():
            continue
        if p.stat().st_size > 8_000_000:
            continue
        if p.suffix.lower() in {".smk", ".wav", ".raw", ".xmi", ".mid"}:
            continue
        data = p.read_bytes()
        hits = []
        for n in needles:
            if n in data:
                hits.append(n)
        if hits:
            print(f"  {p.name}: {[h.decode('ascii', 'replace') for h in hits]}")

    # printable strings around danger/resources in EXE and ENG
    for name in ("C2.EXE", "C2.ENG", "CAESAR2.EXE", "C2SETUP.EXE"):
        p = GAME / name
        if not p.exists():
            # try case-insensitive
            cand = [x for x in GAME.glob("*") if x.name.upper() == name]
            if not cand:
                continue
            p = cand[0]
        data = p.read_bytes()
        print(f"\n--- strings in {p.name} ({len(data)}) ---")
        for pat in (b"danger", b"DANGER", b"resources", b"worth", b"C31", b"c31.raw", b"C31.RAW"):
            idx = 0
            found = 0
            while found < 8:
                i = data.find(pat, idx)
                if i < 0:
                    break
                lo = max(0, i - 40)
                hi = min(len(data), i + 60)
                frag = re.sub(rb"[^\x20-\x7e]", b".", data[lo:hi])
                print(f"  @{i}: {frag!r}")
                idx = i + 1
                found += 1

    # list EXE / ENG
    print("\n=== exe-like / dat in game dir ===")
    for p in sorted(GAME.iterdir()):
        if p.is_file() and p.suffix.lower() in {".exe", ".eng", ".dat", ".txt", ".cfg", ".ini"}:
            print(f"  {p.name:16s} {p.stat().st_size:8d}")


if __name__ == "__main__":
    main()
