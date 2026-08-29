#!/usr/bin/env python3
"""Local-only stats + spectrogram for Caesar II RAW/WAV (do not commit outputs)."""

from __future__ import annotations

import math
import wave
from collections import Counter
from pathlib import Path

from PIL import Image

GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
PREVIEW = Path(r"C:\Users\Felip\caesar2-re\preview")
RATE = 11025
SILENCE_LO, SILENCE_HI = 0x7B, 0x84  # ±5 around 0x7F/0x80


def load_u8(path: Path) -> bytes:
    if path.suffix.lower() == ".wav":
        with wave.open(str(path), "rb") as w:
            assert w.getsampwidth() == 1 and w.getnchannels() == 1
            return w.readframes(w.getnframes())
    return path.read_bytes()


def fft(re: list[float], im: list[float]) -> None:
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


def hann(n: int) -> list[float]:
    if n == 1:
        return [1.0]
    return [0.5 - 0.5 * math.cos(2 * math.pi * i / (n - 1)) for i in range(n)]


def stats(samples: bytes, rate: int = RATE) -> dict:
    n = len(samples)
    hist = Counter(samples)
    mid = hist.most_common(1)[0][0]
    dc = sum(samples) / n
    centered = [s - 128.0 for s in samples]
    rms = math.sqrt(sum(x * x for x in centered) / n)
    peak = max(abs(x) for x in centered)
    crest = peak / rms if rms else 0.0
    silent = [(SILENCE_LO <= s <= SILENCE_HI) for s in samples]
    silence_frac = sum(silent) / n
    runs: list[int] = []
    cur = 0
    in_run = False
    for s in silent:
        if s:
            if not in_run:
                in_run = True
                cur = 1
            else:
                cur += 1
        elif in_run:
            runs.append(cur)
            in_run = False
    if in_run:
        runs.append(cur)
    long_runs = [r for r in runs if r >= rate // 10]  # >= 100 ms
    # bursts: active islands >= 80 ms separated by >= 80 ms silence
    bursts = 0
    i = 0
    min_gap = rate // 12
    min_act = rate // 12
    while i < n:
        while i < n and silent[i]:
            i += 1
        if i >= n:
            break
        j = i
        while j < n and not silent[j]:
            j += 1
        if j - i >= min_act:
            bursts += 1
        i = j
        # skip short gaps so syllable-clusters stay one burst? keep raw count
        _ = min_gap
    # zero-crossing on signed
    zc = 0
    prev = centered[0]
    for x in centered[1:]:
        if (prev >= 0) != (x >= 0):
            zc += 1
        prev = x
    zcr = zc / (n / rate)

    # spectral: 4 averaged windows
    win = 512
    hop = n // 6 if n > win * 4 else win
    win_h = hann(win)
    bands = [0.0, 0.0, 0.0, 0.0]  # 0-400, 400-1500, 1500-4000, 4000-nyquist
    centroid_acc = 0.0
    mag_acc = 0.0
    nwin = 0
    pos = 0
    while pos + win <= n:
        re = [(samples[pos + i] - 128.0) * win_h[i] for i in range(win)]
        im = [0.0] * win
        fft(re, im)
        half = win // 2
        for k in range(1, half):
            mag = math.hypot(re[k], im[k])
            freq = k * rate / win
            mag_acc += mag
            centroid_acc += mag * freq
            if freq < 400:
                bands[0] += mag
            elif freq < 1500:
                bands[1] += mag
            elif freq < 4000:
                bands[2] += mag
            else:
                bands[3] += mag
        nwin += 1
        pos += hop
        if nwin >= 24:
            break
    band_sum = sum(bands) or 1.0
    return {
        "bytes": n,
        "sec": n / rate,
        "mid": mid,
        "mid_frac": samples.count(mid) / n,
        "dc": dc,
        "rms": rms,
        "peak": peak,
        "crest": crest,
        "silence_frac": silence_frac,
        "n_sil_runs": len(runs),
        "longest_sil_s": (max(runs) / rate) if runs else 0.0,
        "n_long_sil": len(long_runs),
        "bursts": bursts,
        "zcr": zcr,
        "centroid": (centroid_acc / mag_acc) if mag_acc else 0.0,
        "e_low": bands[0] / band_sum,
        "e_formant": bands[1] / band_sum,
        "e_mid": bands[2] / band_sum,
        "e_high": bands[3] / band_sum,
        "windows": nwin,
    }


def spectrogram(samples: bytes, dest: Path, rate: int = RATE, fft_n: int = 256) -> None:
    hop = 64
    n = len(samples)
    if n < fft_n:
        return
    cols = min(900, 1 + (n - fft_n) // hop)
    hop = max(1, (n - fft_n) // max(cols - 1, 1))
    rows = fft_n // 2  # 0..nyquist
    # downsample freq axis to ~180 px (keep low freqs)
    out_h = 180
    out_w = cols
    img = Image.new("RGB", (out_w, out_h), (8, 8, 16))
    px = img.load()
    win_h = hann(fft_n)
    # first pass max
    cols_mag: list[list[float]] = []
    peak = 1e-9
    pos = 0
    for _c in range(cols):
        re = [(samples[pos + i] - 128.0) * win_h[i] for i in range(fft_n)]
        im = [0.0] * fft_n
        fft(re, im)
        mags = [math.hypot(re[k], im[k]) for k in range(rows)]
        cols_mag.append(mags)
        peak = max(peak, max(mags) if mags else 0.0)
        pos += hop
        if pos + fft_n > n:
            break
    # log scale, map freq linearly 0..nyquist to y (low at bottom)
    for x, mags in enumerate(cols_mag):
        for y in range(out_h):
            # y=0 top = high freq
            fy = (out_h - 1 - y) / (out_h - 1)  # 0=DC, 1=nyquist
            k = fy * (rows - 1)
            k0 = int(k)
            k1 = min(k0 + 1, rows - 1)
            t = k - k0
            mag = mags[k0] * (1 - t) + mags[k1] * t
            db = 20 * math.log10(mag / peak + 1e-8)
            # -60..0 dB
            v = max(0.0, min(1.0, (db + 60) / 60))
            r = int(20 + 220 * v)
            g = int(16 + 80 * v + 140 * v * v)
            b = int(40 + 40 * (1 - v) + 80 * v)
            px[x, y] = (r, g, b)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)


def classify(st: dict) -> str:
    """Envelope/spectrum heuristic — not a listen."""
    if st["sec"] > 40 and st["silence_frac"] < 0.15 and st["bursts"] > 20:
        return "ambient/music (long continuous energy, fade-capable)"
    if st["sec"] < 4 and st["crest"] > 8 and st["silence_frac"] < 0.15:
        return "short SFX / sting (high crest, little silence)"
    if st["e_formant"] > 0.35 and st["silence_frac"] > 0.08 and st["bursts"] >= 2:
        return "voice-like (formant band + pauses + bursts)"
    if st["silence_frac"] > 0.12 and st["bursts"] >= 2:
        return "voice-like (pauses + bursts; weaker formant)"
    if st["sec"] > 8 and st["silence_frac"] < 0.08:
        return "ambient-like (sustained)"
    return "unclear (PCM-shaped but class mixed)"


def fmt(st: dict) -> str:
    return (
        f"  {st['sec']:6.2f}s  mid=0x{st['mid']:02X} ({st['mid_frac']:.1%})  "
        f"DC={st['dc']:.1f}  RMS={st['rms']:.1f}  crest={st['crest']:.2f}  "
        f"sil={st['silence_frac']:.1%}  long_sil={st['n_long_sil']} "
        f"(max {st['longest_sil_s']:.2f}s)  bursts={st['bursts']}  "
        f"zcr={st['zcr']:.0f}/s  centroid={st['centroid']:.0f}Hz  "
        f"E[0-400]={st['e_low']:.2f} [400-1.5k]={st['e_formant']:.2f} "
        f"[1.5-4k]={st['e_mid']:.2f} [>4k]={st['e_high']:.2f}"
    )


def main() -> None:
    refs = [
        GAME / "FIRE.WAV",
        GAME / "A09.WAV",
        GAME / "SWORDHT.WAV",
    ]
    raws = [
        GAME / "A01.RAW",
        GAME / "A04.RAW",
        GAME / "A09.RAW",
        GAME / "C01.RAW",
        GAME / "C31.RAW",
        GAME / "C34.RAW",
        GAME / "PREBATLE.RAW",
    ]
    print("=== reference game WAV ===")
    for p in refs:
        s = load_u8(p)
        st = stats(s)
        print(f"{p.name}")
        print(fmt(st))
        print(f"  class={classify(st)}")
        dest = PREVIEW / f"{p.stem}_game_spec.png"
        spectrogram(s, dest)
        print(f"  spec -> {dest}")
    print("=== RAW as u8 PCM @ 11025 ===")
    for p in raws:
        s = load_u8(p)
        st = stats(s)
        print(f"{p.name}")
        print(fmt(st))
        print(f"  class={classify(st)}")
        dest = PREVIEW / f"{p.stem}_spec.png"
        spectrogram(s, dest)
        print(f"  spec -> {dest}")


if __name__ == "__main__":
    main()
