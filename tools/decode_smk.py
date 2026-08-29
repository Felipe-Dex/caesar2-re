#!/usr/bin/env python3
"""Inventory / remux Caesar II .SMK (Smacker) via ffmpeg.

These are RAD Game Tools Smacker containers (magic SMK2 on this 1.1A
install). This script does not implement the codec — it reads the 104-byte
header for inventory and shells out to ffmpeg for decode.

    python tools/decode_smk.py --inventory
    python tools/decode_smk.py --export-all

Writes videos/{stem}.mp4 (H.264 + AAC) and videos/{stem}_frame0.png.
Do not commit decoded videos or original .SMK.
"""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
DEFAULT_VIDEOS = Path(r"C:\Users\Felip\caesar2-re\videos")
HEADER_SIZE = 104
VIDEO_EXTS = (".smk", ".avi", ".flc", ".fli")

# AudioRate bits — wiki.multimedia.cx/Smacker
AUD_COMPRESSED = 1 << 31
AUD_PRESENT = 1 << 30
AUD_16BIT = 1 << 29
AUD_STEREO = 1 << 28


@dataclass(frozen=True)
class SmkHeader:
    path: Path
    magic: bytes
    width: int
    height: int
    frames: int
    frame_rate: int
    flags: int
    trees_size: int
    audio_size: tuple[int, ...]
    audio_rate: tuple[int, ...]

    @property
    def fps(self) -> float:
        if self.frame_rate > 0:
            return 1000.0 / self.frame_rate
        if self.frame_rate < 0:
            return 100000.0 / (-self.frame_rate)
        return 10.0

    @property
    def duration_s(self) -> float:
        return self.frames / self.fps if self.fps else 0.0

    def audio_tracks(self) -> list[str]:
        out: list[str] = []
        for i, packed in enumerate(self.audio_rate):
            if not (packed & AUD_PRESENT):
                continue
            rate = packed & 0xFFFFFF
            bits = 16 if packed & AUD_16BIT else 8
            ch = "stereo" if packed & AUD_STEREO else "mono"
            packed_bit = "dpcm" if packed & AUD_COMPRESSED else "pcm"
            out.append(f"t{i}:{rate}Hz {bits}-bit {ch} {packed_bit}")
        return out


def find_ffmpeg(explicit: Path | None = None) -> Path:
    if explicit is not None:
        if not explicit.is_file():
            raise FileNotFoundError(f"ffmpeg not found: {explicit}")
        return explicit
    which = shutil.which("ffmpeg")
    if which:
        return Path(which)
    winget = Path.home() / (
        "AppData/Local/Microsoft/WinGet/Packages"
    )
    if winget.is_dir():
        hits = sorted(winget.rglob("ffmpeg.exe"))
        if hits:
            return hits[0]
    raise FileNotFoundError(
        "ffmpeg not on PATH. Install (winget install --id Gyan.FFmpeg) "
        "or pass --ffmpeg path\\to\\ffmpeg.exe"
    )


def list_videos(game: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for ext in VIDEO_EXTS:
        for path in game.glob(f"*{ext}"):
            key = path.name.upper()
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
        for path in game.glob(f"*{ext.upper()}"):
            key = path.name.upper()
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return sorted(found, key=lambda p: p.name.upper())


def read_smk_header(path: Path) -> SmkHeader:
    data = path.read_bytes()[:HEADER_SIZE]
    if len(data) < HEADER_SIZE:
        raise ValueError(f"{path.name}: truncated header ({len(data)} B)")
    magic = data[:4]
    if magic not in (b"SMK2", b"SMK4"):
        raise ValueError(f"{path.name}: bad magic {magic!r} (want SMK2/SMK4)")
    width, height, frames = struct.unpack_from("<III", data, 4)
    frame_rate, flags = struct.unpack_from("<iI", data, 16)
    audio_size = struct.unpack_from("<7I", data, 24)
    trees_size = struct.unpack_from("<I", data, 52)[0]
    audio_rate = struct.unpack_from("<7I", data, 72)
    return SmkHeader(
        path=path,
        magic=magic,
        width=width,
        height=height,
        frames=frames,
        frame_rate=frame_rate,
        flags=flags,
        trees_size=trees_size,
        audio_size=audio_size,
        audio_rate=audio_rate,
    )


def inventory(game: Path) -> int:
    files = list_videos(game)
    smk = [p for p in files if p.suffix.lower() == ".smk"]
    other = [p for p in files if p.suffix.lower() != ".smk"]
    print(f"game       : {game}")
    print(f"SMK        : {len(smk)}")
    print(f"AVI/FLC/FLI: {len(other)}")
    print()
    print(
        f"{'name':<16} {'bytes':>10} magic  WxH       frames   fps  "
        f"{'dur':>6} audio"
    )
    total = 0
    for path in smk:
        hdr = read_smk_header(path)
        total += path.stat().st_size
        tracks = ", ".join(hdr.audio_tracks()) or "(none)"
        print(
            f"{path.name:<16} {path.stat().st_size:10} {hdr.magic.decode()}  "
            f"{hdr.width}x{hdr.height:<5} {hdr.frames:6} {hdr.fps:5.2f} "
            f"{hdr.duration_s:6.2f}s {tracks}"
        )
    print(f"total bytes: {total}")
    for path in other:
        print(f"other      : {path.name}  {path.stat().st_size} B")
    return 0


def run_ffmpeg(ffmpeg: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    cmd = [str(ffmpeg), "-hide_banner", "-loglevel", "error", "-y", *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def export_one(
    smk: Path,
    out_dir: Path,
    ffmpeg: Path,
    *,
    frame0: bool,
) -> tuple[bool, str]:
    hdr = read_smk_header(smk)
    out_dir.mkdir(parents=True, exist_ok=True)
    mp4 = out_dir / f"{smk.stem}.mp4"
    result = run_ffmpeg(
        ffmpeg,
        [
            "-i",
            str(smk),
            "-vf",
            "format=yuv420p",
            "-c:v",
            "libx264",
            "-crf",
            "20",
            "-preset",
            "medium",
            "-c:a",
            "aac",
            "-b:a",
            "96k",
            "-movflags",
            "+faststart",
            str(mp4),
        ],
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout or "ffmpeg failed").strip().splitlines()
        tail = err[-1] if err else "ffmpeg failed"
        return False, f"{smk.name}: {tail}"

    note = f"{smk.name} -> {mp4.name}  {hdr.width}x{hdr.height} {hdr.fps:.2f}fps {hdr.duration_s:.2f}s"
    if frame0:
        png = out_dir / f"{smk.stem}_frame0.png"
        fr = run_ffmpeg(
            ffmpeg,
            ["-i", str(smk), "-frames:v", "1", str(png)],
        )
        if fr.returncode != 0:
            return True, note + "  (frame0 failed)"
        note += f"  + {png.name}"
    return True, note


def export_all(game: Path, out_dir: Path, ffmpeg: Path, *, frame0: bool) -> int:
    files = [p for p in list_videos(game) if p.suffix.lower() == ".smk"]
    if not files:
        print(f"no .SMK under {game}", file=sys.stderr)
        return 1
    print(f"ffmpeg     : {ffmpeg}")
    print(f"out        : {out_dir}")
    ok = 0
    failed: list[str] = []
    for path in files:
        success, msg = export_one(path, out_dir, ffmpeg, frame0=frame0)
        print(("ok  " if success else "FAIL") + "        : " + msg)
        if success:
            ok += 1
        else:
            failed.append(msg)
    print(f"decoded    : {ok}/{len(files)}")
    if failed:
        print("failed     :")
        for line in failed:
            print(f"  {line}")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inventory / remux Caesar II .SMK via ffmpeg")
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--smk", type=Path, default=None)
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="output MP4 for a single --smk (default: videos/{stem}.mp4)",
    )
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument(
        "--export-all",
        action="store_true",
        help="write MP4 + first-frame PNG for every SMK into --videos-dir",
    )
    parser.add_argument(
        "--videos-dir",
        type=Path,
        default=DEFAULT_VIDEOS,
        help="preview output directory (default: repo videos/)",
    )
    parser.add_argument("--ffmpeg", type=Path, default=None, help="ffmpeg.exe path")
    parser.add_argument(
        "--no-frame0",
        action="store_true",
        help="skip videos/{stem}_frame0.png",
    )
    args = parser.parse_args(argv)

    if args.inventory:
        return inventory(args.game)

    ffmpeg = find_ffmpeg(args.ffmpeg)

    if args.export_all:
        return export_all(args.game, args.videos_dir, ffmpeg, frame0=not args.no_frame0)

    smk = args.smk or (args.game / "INTRO.SMK")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        # write exactly --out; still honor frame0 next to it
        tmp_dir = args.out.parent
        ok, msg = export_one(smk, tmp_dir, ffmpeg, frame0=not args.no_frame0)
        dest = tmp_dir / f"{smk.stem}.mp4"
        if ok and dest.resolve() != args.out.resolve():
            dest.replace(args.out)
        print(("ok          : " if ok else "FAILED      : ") + msg)
        return 0 if ok else 1

    ok, msg = export_one(smk, args.videos_dir, ffmpeg, frame0=not args.no_frame0)
    print(("ok          : " if ok else "FAILED      : ") + msg)
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, FileNotFoundError) as exc:
        print(f"FAILED      : {exc}", file=sys.stderr)
        sys.exit(1)
