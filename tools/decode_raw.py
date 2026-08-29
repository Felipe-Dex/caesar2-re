#!/usr/bin/env python3
"""Probe Caesar II .RAW files (Phase 1).

A/B/C and PREBATLE are 8-bit unsigned PCM mono at 22050 Hz (user-verified
on A01). City .WAV SFX (FIRE.WAV, SWORDHT.WAV, …) remain 11025 Hz — same
sample format, different rate. Treating A01.RAW as a 448x448 indexed
framebuffer is a size coincidence (200704 = 0x31000 = 448^2) and
produces wrap + palette static.

Default preview is a waveform. --export-all writes wav + waveform + spec
into sound/. --width still forces a 2D dump for experiments.
Do not commit decoded PNGs or WAVs.
"""

from __future__ import annotations

import argparse
import math
import sys
import wave
from collections import Counter
from pathlib import Path

from PIL import Image

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
DEFAULT_SOUND = Path(r"C:\Users\Felip\caesar2-re\sound")
DEFAULT_RATE = 22050  # RAW banks (A01 user-verified); city .WAV SFX stay 11025


def ramp_palette() -> list[tuple[int, int, int]]:
    """Synthetic LUT — RAW is not indexed like CITYFIXT/VIEW1."""
    pal: list[tuple[int, int, int]] = []
    for i in range(256):
        if abs(i - 0x7F) <= 2:
            pal.append((90, 140, 190))
        elif i < 40:
            pal.append((i * 2, i, 20))
        elif i < 90:
            t = (i - 40) / 50
            pal.append((int(40 + 80 * t), int(70 + 90 * t), int(30 + 20 * t)))
        elif i < 160:
            t = (i - 90) / 70
            pal.append((int(120 + 50 * t), int(140 - 20 * t), int(60 + 40 * t)))
        else:
            t = min(1.0, (i - 160) / 80)
            pal.append((int(180 + 40 * t), int(180 + 40 * t), int(160 + 50 * t)))
    return pal


def gray_palette() -> list[tuple[int, int, int]]:
    return [(i, i, i) for i in range(256)]


PALETTE_SIZE = 256 * 3


def vga6_to_8(c: int) -> int:
    return (c << 2) | (c >> 4)


def load_palette(path: Path) -> list[tuple[int, int, int]]:
    data = path.read_bytes()
    if len(data) != PALETTE_SIZE:
        raise ValueError(f"{path.name}: expected {PALETTE_SIZE} bytes, got {len(data)}")
    raw_max = max(data) if data else 0
    scale = raw_max <= 63

    def chan(v: int) -> int:
        return vga6_to_8(v) if scale else v

    return [
        (chan(data[i]), chan(data[i + 1]), chan(data[i + 2]))
        for i in range(0, PALETTE_SIZE, 3)
    ]


def factors_of(n: int, lo: int = 16, hi: int = 1024) -> list[tuple[int, int]]:
    out = []
    for w in range(lo, hi + 1):
        if n % w == 0:
            h = n // w
            if lo <= h <= hi:
                out.append((w, h))
    return out


def run_stats(data: bytes) -> tuple[int, int, list[tuple[int, int]]]:
    if not data:
        return 0, 0, []
    runs = 0
    longest = 1
    cur = 1
    val_runs: Counter[int] = Counter()
    for i in range(1, len(data)):
        if data[i] == data[i - 1]:
            cur += 1
            longest = max(longest, cur)
        else:
            runs += 1
            val_runs[data[i - 1]] += 1
            cur = 1
    runs += 1
    val_runs[data[-1]] += 1
    return runs, longest, val_runs.most_common(8)


def try_pcx_rle(data: bytes, limit: int = 400_000) -> bytes | None:
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        i += 1
        if (b & 0xC0) == 0xC0:
            count = b & 0x3F
            if i >= n:
                return None
            out.extend([data[i]] * max(count, 1))
            i += 1
        else:
            out.append(b)
        if len(out) > limit:
            return None
    return bytes(out)


def try_packbits(data: bytes, limit: int = 400_000) -> bytes | None:
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        ctrl = data[i]
        i += 1
        if ctrl <= 127:
            count = ctrl + 1
            if i + count > n:
                return None
            out.extend(data[i : i + count])
            i += count
        elif ctrl != 128:
            count = 257 - ctrl
            if i >= n:
                return None
            out.extend([data[i]] * count)
            i += 1
        if len(out) > limit:
            return None
    return bytes(out)


def try_count_value(data: bytes, limit: int = 400_000) -> bytes | None:
    if len(data) % 2:
        return None
    out = bytearray()
    for i in range(0, len(data), 2):
        count = data[i]
        if count == 0:
            return None
        out.extend([data[i + 1]] * count)
        if len(out) > limit:
            return None
    return bytes(out)


def try_value_count(data: bytes, limit: int = 400_000) -> bytes | None:
    if len(data) % 2:
        return None
    out = bytearray()
    for i in range(0, len(data), 2):
        count = data[i + 1]
        if count == 0:
            return None
        out.extend([data[i]] * count)
        if len(out) > limit:
            return None
    return bytes(out)


def try_7f_rle(data: bytes, limit: int = 400_000) -> bytes | None:
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        b = data[i]
        i += 1
        if b == 0x7F:
            if i + 1 >= n:
                return None
            count = data[i]
            value = data[i + 1]
            i += 2
            if count == 0:
                return None
            out.extend([value] * count)
        else:
            out.append(b)
        if len(out) > limit:
            return None
    return bytes(out)


def nice_rects(n: int) -> list[tuple[int, int]]:
    prefer = (
        (448, 448),
        (640, 480),
        (640, 400),
        (320, 200),
        (320, 240),
        (256, 256),
        (128, 128),
        (64, 64),
        (58, 30),
    )
    hits = [(w, h) for w, h in prefer if w * h == n]
    for w, h in factors_of(n, 32, 800):
        if abs(w - h) <= 64 or w in (256, 320, 448, 512, 640) or h in (200, 240, 400, 480):
            if (w, h) not in hits:
                hits.append((w, h))
    return hits[:12]


def indices_to_image(indices: bytes, width: int, height: int, palette) -> Image.Image:
    if len(indices) < width * height:
        raise ValueError(f"need {width * height} pixels, got {len(indices)}")
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        row = y * width
        for x in range(width):
            idx = indices[row + x]
            px[x, y] = palette[idx]
    return img


def waveform_image(samples: bytes, width: int = 900, height: int = 220) -> Image.Image:
    """Plot unsigned 8-bit PCM; 0x7F/0x80 sits on the midline."""
    img = Image.new("RGB", (width, height), (16, 16, 24))
    px = img.load()
    mid = height // 2
    n = len(samples)
    if n == 0:
        return img
    for x in range(width):
        i0 = int(x * n / width)
        i1 = max(i0 + 1, int((x + 1) * n / width))
        chunk = samples[i0:i1]
        lo = min(chunk)
        hi = max(chunk)
        y0 = int((1 - hi / 255) * (height - 1))
        y1 = int((1 - lo / 255) * (height - 1))
        if y1 < y0:
            y0, y1 = y1, y0
        for y in range(y0, y1 + 1):
            px[x, y] = (180, 200, 140)
        px[x, mid] = (70, 70, 90)
    return img


def write_pcm_wav(samples: bytes, dest: Path, rate: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(rate)
        w.writeframes(samples)


def _fft(re: list[float], im: list[float]) -> None:
    n = len(re)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            re[i], re[j] = re[j], re[i]
            im[i], im[j] = im[j], im[i]
    length = 2
    while length <= n:
        ang = -2 * math.pi / length
        wlen_re, wlen_im = math.cos(ang), math.sin(ang)
        for i in range(0, n, length):
            wr, wi = 1.0, 0.0
            half = length // 2
            for k in range(half):
                u_re, u_im = re[i + k], im[i + k]
                v_re = re[i + k + half] * wr - im[i + k + half] * wi
                v_im = re[i + k + half] * wi + im[i + k + half] * wr
                re[i + k] = u_re + v_re
                im[i + k] = u_im + v_im
                re[i + k + half] = u_re - v_re
                im[i + k + half] = u_im - v_im
                nwr = wr * wlen_re - wi * wlen_im
                wi = wr * wlen_im + wi * wlen_re
                wr = nwr
        length <<= 1


def spectrogram_image(samples: bytes, fft_n: int = 256, out_w: int = 900, out_h: int = 180) -> Image.Image:
    """Log-magnitude spectrogram; low frequency at the bottom."""
    n = len(samples)
    img = Image.new("RGB", (out_w, out_h), (8, 8, 16))
    if n < fft_n:
        return img
    hop = max(1, (n - fft_n) // max(out_w - 1, 1))
    rows = fft_n // 2
    win_h = [0.5 - 0.5 * math.cos(2 * math.pi * i / (fft_n - 1)) for i in range(fft_n)]
    cols_mag: list[list[float]] = []
    peak = 1e-9
    pos = 0
    for _c in range(out_w):
        re = [(samples[pos + i] - 128.0) * win_h[i] for i in range(fft_n)]
        im = [0.0] * fft_n
        _fft(re, im)
        mags = [math.hypot(re[k], im[k]) for k in range(rows)]
        cols_mag.append(mags)
        peak = max(peak, max(mags) if mags else 0.0)
        pos += hop
        if pos + fft_n > n:
            break
    px = img.load()
    for x, mags in enumerate(cols_mag):
        for y in range(out_h):
            fy = (out_h - 1 - y) / (out_h - 1)
            k = fy * (rows - 1)
            k0 = int(k)
            k1 = min(k0 + 1, rows - 1)
            t = k - k0
            mag = mags[k0] * (1 - t) + mags[k1] * t
            db = 20 * math.log10(mag / peak + 1e-8)
            v = max(0.0, min(1.0, (db + 60) / 60))
            px[x, y] = (
                int(20 + 220 * v),
                int(16 + 80 * v + 140 * v * v),
                int(40 + 40 * (1 - v) + 80 * v),
            )
    return img


def list_raws(game: Path) -> list[Path]:
    files = sorted(game.glob("*.RAW")) + sorted(game.glob("*.raw"))
    seen: dict[str, Path] = {}
    for p in files:
        seen[p.name.upper()] = p
    return [seen[k] for k in sorted(seen)]


def export_preview(raw_path: Path, dest_dir: Path, rate: int) -> tuple[Path, Path, Path]:
    data = raw_path.read_bytes()
    dest_dir.mkdir(parents=True, exist_ok=True)
    stem = raw_path.stem
    wav = dest_dir / f"{stem}.wav"
    wave_png = dest_dir / f"{stem}_waveform.png"
    spec_png = dest_dir / f"{stem}_spec.png"
    write_pcm_wav(data, wav, rate)
    waveform_image(data).save(wave_png)
    spectrogram_image(data).save(spec_png)
    return wav, wave_png, spec_png


def export_all(game: Path, dest_dir: Path, rate: int) -> int:
    files = list_raws(game)
    if not files:
        raise FileNotFoundError(f"no .RAW under {game}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    failed: list[tuple[str, str]] = []
    print(f"=== export {len(files)} RAW -> {dest_dir}  u8 mono @ {rate} Hz ===")
    for p in files:
        try:
            wav, wave_png, spec_png = export_preview(p, dest_dir, rate)
            print(f"  {p.name:12s} {p.stat().st_size:8d} B  {wav.name}  {wave_png.name}  {spec_png.name}")
        except (OSError, ValueError) as exc:
            failed.append((p.name, str(exc)))
            print(f"  FAILED {p.name}: {exc}")
    print(f"done        : {len(files) - len(failed)}/{len(files)}  failed={len(failed)}")
    return 1 if failed else 0


def midpoint(data: bytes) -> int:
    hist = Counter(data)
    return hist.most_common(1)[0][0] if hist else 0


def inventory(game: Path) -> None:
    files = list_raws(game)
    print(f"=== RAW inventory ({len(files)}) ===")
    print("8-bit streams; 7F/80 = midpoint (silence if PCM). Not a shared framebuffer.")
    print(f"{'name':12s} {'size':>8s}  {'sec@22k':>7s}  hex[0:12]              mid  long")
    for p in files:
        data = p.read_bytes()
        _n_runs, longest, _top = run_stats(data)
        mid = midpoint(data)
        sec = len(data) / DEFAULT_RATE
        print(
            f"{p.name:12s} {len(data):8d}  {sec:6.2f}s  {data[:12].hex()}  "
            f"{mid:02x}  {longest:5d}"
        )


def probe_rle(path: Path) -> None:
    data = path.read_bytes()
    print(f"=== RLE probe {path.name} ({len(data)} bytes) ===")
    print(f"hex[0:32] : {data[:32].hex()}")
    hist = Counter(data)
    print(f"unique    : {len(hist)}  top={hist.most_common(8)}")
    print(f"nice raw rects: {nice_rects(len(data))}")
    print(f"duration  : {len(data)/DEFAULT_RATE:.2f}s at {DEFAULT_RATE} Hz (RAW bank rate)")

    trials = (
        ("pcx", try_pcx_rle),
        ("packbits", try_packbits),
        ("count_value", try_count_value),
        ("value_count", try_value_count),
        ("esc_7f", try_7f_rle),
    )
    for name, fn in trials:
        try:
            out = fn(data)
        except Exception as exc:  # noqa: BLE001 — probe
            print(f"  {name:12s} ERROR {exc}")
            continue
        if out is None:
            print(f"  {name:12s} fail / overrun")
            continue
        rects = nice_rects(len(out))
        print(
            f"  {name:12s} -> {len(out):7d} B  "
            f"ratio={len(data)/max(len(out),1):.3f}  rects={rects[:6]}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Probe Caesar II .RAW (PCM / 2D dump)")
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--raw", type=Path, default=None)
    parser.add_argument("--pal", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--width", type=int, default=None)
    parser.add_argument("--height", type=int, default=None)
    parser.add_argument(
        "--mode",
        choices=("auto", "waveform", "wav", "raw", "pcx", "packbits", "count_value", "value_count", "esc_7f"),
        default="auto",
    )
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument(
        "--export-all",
        action="store_true",
        help="write wav + waveform PNG + spec PNG for every RAW into --sound-dir",
    )
    parser.add_argument(
        "--sound-dir",
        type=Path,
        default=DEFAULT_SOUND,
        help="preview output directory (default: repo sound/)",
    )
    parser.add_argument("--probe", action="store_true")
    parser.add_argument(
        "--ramp",
        action="store_true",
        help="2D dump: synthetic ramp instead of a .256 (never use CITYFIXT/VIEW1)",
    )
    parser.add_argument("--gray", action="store_true", help="2D dump: index = gray")
    parser.add_argument(
        "--rate",
        type=int,
        default=DEFAULT_RATE,
        help="PCM sample rate (RAW banks default 22050; city WAV SFX are 11025)",
    )
    args = parser.parse_args(argv)

    if args.inventory:
        inventory(args.game)
        return 0

    if args.export_all:
        return export_all(args.game, args.sound_dir, args.rate)

    raw_path = args.raw or (args.game / "A01.RAW")
    data = raw_path.read_bytes()

    if args.probe:
        probe_rle(raw_path)
        return 0

    mid = midpoint(data)
    print(f"file        : {raw_path.name}  {len(data)} B")
    print(f"midpoint    : 0x{mid:02X}  ({data.count(mid)/len(data):.1%} of bytes)")
    print(f"pcm guess   : {len(data)/args.rate:.2f}s mono u8 @ {args.rate} Hz")

    want_wav = args.mode == "wav"
    want_wave = args.mode in ("auto", "waveform") and not args.width and not args.height
    if args.mode == "wav":
        want_wave = False

    if want_wav or (args.mode == "auto" and args.out and str(args.out).lower().endswith(".wav")):
        out = args.out or (DEFAULT_SOUND / f"{raw_path.stem}.wav")
        write_pcm_wav(data, out, args.rate)
        print(f"wrote wav   : {out}")
        if args.mode == "wav":
            return 0

    if want_wave:
        img = waveform_image(data)
        out = args.out or (DEFAULT_SOUND / f"{raw_path.stem}_waveform.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        print(f"wrote wave  : {out}  (not a landscape; 1D PCM preview)")
        return 0

    pixels = data
    if args.mode not in ("auto", "raw", "waveform", "wav"):
        fn = {
            "pcx": try_pcx_rle,
            "packbits": try_packbits,
            "count_value": try_count_value,
            "value_count": try_value_count,
            "esc_7f": try_7f_rle,
        }[args.mode]
        out = fn(data)
        if out is None:
            raise ValueError(f"{args.mode} failed")
        pixels = out
        print(f"mode        : {args.mode} -> {len(pixels)} bytes")

    if args.gray:
        palette = gray_palette()
        print("palette     : identity gray (not a .256)")
    elif args.ramp or not args.pal:
        palette = ramp_palette()
        print("palette     : synthetic ramp (not a .256)")
    else:
        palette = load_palette(args.pal)
        print(f"palette     : {args.pal.name}")

    w = args.width
    h = args.height
    if w and not h:
        if len(pixels) % w:
            raise ValueError(f"len {len(pixels)} not divisible by width {w}")
        h = len(pixels) // w
    elif h and not w:
        if len(pixels) % h:
            raise ValueError(f"len {len(pixels)} not divisible by height {h}")
        w = len(pixels) // h
    elif not w and not h:
        raise ValueError("2D dump needs --width (448x448 is not a proven layout)")

    print(f"decode 2D   : {raw_path.name} -> {w}x{h}  (experimental wrap)")
    img = indices_to_image(pixels, w, h, palette)
    out = args.out or (Path(r"C:\Users\Felip\caesar2-re") / f"{raw_path.stem}_{w}x{h}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"wrote       : {out}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"FAILED      : {exc}", file=sys.stderr)
        sys.exit(1)
