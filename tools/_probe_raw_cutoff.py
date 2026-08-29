#!/usr/bin/env python3
"""Local-only: why RAW clips cut off at the end. Do not commit outputs."""

from __future__ import annotations

import struct
import wave
from collections import Counter
from pathlib import Path

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
PREV = Path(r"C:\Users\Felip\caesar2-re\preview")
RATE = 22050


def stdev(chunk: bytes) -> float:
    if not chunk:
        return 0.0
    mean = sum(chunk) / len(chunk)
    return (sum((x - mean) ** 2 for x in chunk) / len(chunk)) ** 0.5


def tail_7f(data: bytes) -> int:
    i = len(data)
    while i > 0 and data[i - 1] == 0x7F:
        i -= 1
    return len(data) - i


def tail_near_mid(data: bytes, mid: int = 0x7F, tol: int = 2) -> int:
    i = len(data)
    while i > 0 and abs(data[i - 1] - mid) <= tol:
        i -= 1
    return len(data) - i


def chunk_stats(label: str, chunk: bytes) -> None:
    if not chunk:
        print(f"  {label}: empty")
        return
    print(
        f"  {label:10s} n={len(chunk):5d} mean={sum(chunk)/len(chunk):6.1f} "
        f"std={stdev(chunk):5.1f} unique={len(set(chunk)):3d} "
        f"min={min(chunk):3d} max={max(chunk):3d} "
        f"7F={chunk.count(0x7F)} 80={chunk.count(0x80)}"
    )


def parse_wav(path: Path, raw: bytes) -> None:
    if not path.exists():
        print(f"MISSING {path}")
        return
    wb = path.read_bytes()
    print(f"=== {path} file={len(wb)} RAW={len(raw)} RAW+44={len(raw)+44} ===")
    if len(wb) < 12:
        print("  too small")
        return
    print(
        f"  RIFF={wb[0:4]!r} size_field={struct.unpack_from('<I', wb, 4)[0]} "
        f"file-8={len(wb)-8} WAVE={wb[8:12]!r}"
    )
    off = 12
    while off + 8 <= len(wb):
        cid = wb[off : off + 4]
        csz = struct.unpack_from("<I", wb, off + 4)[0]
        print(f"  chunk {cid!r} size={csz} at={off} end={off + 8 + csz}")
        if cid == b"data":
            pcm = wb[off + 8 : off + 8 + csz]
            extra = len(wb) - (off + 8 + csz)
            print(
                f"    pcm={len(pcm)} extra_after={extra} "
                f"pcm==raw={pcm == raw} prefix={pcm == raw[: len(pcm)]}"
            )
            if len(pcm) != len(raw):
                print(f"    DELTA pcm-raw={len(pcm) - len(raw)}")
        off += 8 + csz + (csz & 1)
    with wave.open(str(path), "rb") as w:
        fr = w.readframes(w.getnframes())
        print(
            f"  wave ch={w.getnchannels()} sw={w.getsampwidth()} "
            f"rate={w.getframerate()} nframes={w.getnframes()} "
            f"read={len(fr)} ==raw={fr == raw}"
        )


def look_like_header(data: bytes) -> list[str]:
    notes = []
    if len(data) < 16:
        return notes
    u16 = struct.unpack_from("<H", data, 0)[0]
    u32 = struct.unpack_from("<I", data, 0)[0]
    notes.append(f"le16[0]={u16} le32[0]={u32} file={len(data)}")
    if u32 == len(data) or u32 == len(data) - 4:
        notes.append("FIRST_U32_MATCHES_SIZE")
    if u32 + 4 == len(data) or u32 + 8 == len(data) or u32 + 16 == len(data):
        notes.append(f"FIRST_U32_PLUS_HDR={u32}")
    # last 16 as possible footer
    tail_u32 = struct.unpack_from("<I", data, len(data) - 4)[0]
    notes.append(f"le32[-4]={tail_u32}")
    # scan first 64 for size-like fields
    for off in range(0, min(64, len(data) - 4), 2):
        v = struct.unpack_from("<I", data, off)[0]
        if v in (len(data), len(data) - off - 4, len(data) - 4, len(data) - 8, len(data) - 16):
            notes.append(f"SIZE_FIELD_AT_{off}={v}")
    return notes


def inventory() -> list[Path]:
    files = sorted(GAME.glob("*.RAW")) + sorted(GAME.glob("*.raw"))
    seen: dict[str, Path] = {}
    for p in files:
        seen[p.name.upper()] = p
    return [seen[k] for k in sorted(seen)]


def main() -> None:
    files = inventory()
    print(f"=== RAW inventory ({len(files)}) ===")
    print(f"{'name':12s} {'size':>8s} {'sec':>7s} {'7F%':>6s} {'tail7F':>7s} {'tstd':>6s} hex0  hex-8")
    rows = []
    for p in files:
        data = p.read_bytes()
        hist = Counter(data)
        mid = hist.most_common(1)[0][0]
        tstd = stdev(data[-2000:] if len(data) >= 2000 else data)
        rows.append((p, data))
        print(
            f"{p.name:12s} {len(data):8d} {len(data)/RATE:6.2f}s "
            f"{100*data.count(0x7F)/len(data):5.1f}% {tail_7f(data):7d} "
            f"{tstd:6.1f} {data[:8].hex()}  {data[-8:].hex()}"
        )

    print("\n=== name sequences / gaps ===")
    by_series: dict[str, list[int]] = {"A": [], "B": [], "C": []}
    extras = []
    for p, data in rows:
        name = p.stem.upper()
        if len(name) >= 2 and name[0] in by_series and name[1:].isdigit():
            by_series[name[0]].append(int(name[1:]))
        else:
            extras.append((p.name, len(data)))
    for letter, nums in by_series.items():
        nums = sorted(nums)
        missing = [i for i in range(nums[0], nums[-1] + 1) if i not in nums] if nums else []
        print(f"  {letter}: {nums[0]:02d}..{nums[-1]:02d} count={len(nums)} missing={missing}")
    print(f"  extras: {extras}")

    print("\n=== small files (< 8s) that might be tails ===")
    for p, data in rows:
        if len(data) < 8 * RATE:
            print(
                f"  {p.name:12s} {len(data):8d} {len(data)/RATE:6.2f}s "
                f"head={data[:12].hex()} tailstd={stdev(data[-500:] if len(data)>=500 else data):.1f}"
            )

    print("\n=== C31 deep ===")
    c31p = GAME / "C31.RAW"
    raw = c31p.read_bytes()
    print(f"size={len(raw)} duration={len(raw)/RATE:.3f}s")
    print(f"head64: {raw[:64].hex(' ')}")
    print(f"tail64: {raw[-64:].hex(' ')}")
    print(f"trailing 0x7F: {tail_7f(raw)}")
    print(f"trailing ~7F+-2: {tail_near_mid(raw)}")
    print(f"header notes: {look_like_header(raw)}")
    for label, chunk in (
        ("first2k", raw[:2000]),
        ("mid2k", raw[len(raw) // 2 : len(raw) // 2 + 2000]),
        ("last4k", raw[-4000:]),
        ("last2k", raw[-2000:]),
        ("last500", raw[-500:]),
        ("last100", raw[-100:]),
        ("last32", raw[-32:]),
    ):
        chunk_stats(label, chunk)

    for wp in (PREV / "C31.wav", PREV / "C31_22050.wav"):
        parse_wav(wp, raw)

    print("\n=== C32 as possible sequel ===")
    c32p = GAME / "C32.RAW"
    if c32p.exists():
        c32 = c32p.read_bytes()
        print(f"C32 size={len(c32)} dur={len(c32)/RATE:.3f}s")
        print(f"C32 head64: {c32[:64].hex(' ')}")
        print(f"C32 tail64: {c32[-64:].hex(' ')}")
        print(f"C32 trailing 7F: {tail_7f(c32)} header={look_like_header(c32)}")
        chunk_stats("C32 first2k", c32[:2000])
        chunk_stats("C32 last2k", c32[-2000:])
        # junction: last 200 of C31 vs first 200 of C32
        print("junction C31[-200] / C32[:200]:")
        chunk_stats("C31[-200]", raw[-200:])
        chunk_stats("C32[:200]", c32[:200])
        print(f"C31+C32 = {len(raw)+len(c32)} B / {(len(raw)+len(c32))/RATE:.3f}s")
    else:
        print("NO C32.RAW")

    print("\n=== adjacent pairs: tail energy vs next-head energy ===")
    # For each sequential pair, report if first ends "hot" (speech) and next starts "hot"
    named = {p.stem.upper(): (p, d) for p, d in rows}
    for letter in "ABC":
        nums = by_series[letter]
        for a, b in zip(nums, nums[1:]):
            if b != a + 1:
                continue
            da = named[f"{letter}{a:02d}"][1]
            db = named[f"{letter}{b:02d}"][1]
            t = stdev(da[-1500:] if len(da) >= 1500 else da)
            h = stdev(db[:1500] if len(db) >= 1500 else db)
            t7 = tail_7f(da)
            h7f = 0
            i = 0
            while i < min(len(db), 4000) and db[i] == 0x7F:
                i += 1
            h7f = i
            flag = ""
            if t > 12 and t7 < 200:
                flag += " HOT_END"
            if h > 12 and h7f < 200:
                flag += " HOT_NEXT"
            if t > 12 and t7 < 200 and h > 8:
                flag += " **CONCAT_CAND**"
            print(
                f"  {letter}{a:02d}+{letter}{b:02d}  "
                f"{len(da):7d}+{len(db):7d}  "
                f"tailstd={t:5.1f} tail7F={t7:5d}  "
                f"nextstd={h:5.1f} next_lead7F={h7f:5d}{flag}"
            )

    print("\n=== named clips of interest ===")
    for stem in ("A01", "A04", "A09", "C01", "C31", "C34", "PREBATLE"):
        hits = [p for p, _ in rows if p.stem.upper() == stem]
        if not hits:
            print(f"  {stem}: MISSING")
            continue
        p = hits[0]
        d = named[p.stem.upper()][1]
        nxt_name = None
        if stem[0] in "ABC" and stem[1:].isdigit():
            nxt_name = f"{stem[0]}{int(stem[1:])+1:02d}"
        print(
            f"  {p.name}: {len(d)} B {len(d)/RATE:.2f}s tail7F={tail_7f(d)} "
            f"tailstd={stdev(d[-1500:] if len(d)>=1500 else d):.1f} "
            f"next={nxt_name} exists={nxt_name in named if nxt_name else False}"
        )
        if nxt_name and nxt_name in named:
            nd = named[nxt_name][1]
            print(
                f"    {nxt_name}: {len(nd)} B {len(nd)/RATE:.2f}s "
                f"head7F_run={sum(1 for i in range(len(nd)) if all(nd[j]==0x7F for j in range(i+1)))} "
                f"headstd={stdev(nd[:1500] if len(nd)>=1500 else nd):.1f}"
            )


if __name__ == "__main__":
    main()
