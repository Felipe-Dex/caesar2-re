"""Optional RAW playback. Miles / AIL is not implemented.

Ghidra: miles_init 0x11758, AIL_startup 0x72992, push_22050_raw_rate 0x120A6.
tools/decode_raw.py: unsigned 8-bit PCM mono @ 22050 Hz (A01 user-verified).
"""

from __future__ import annotations

import sys
import tempfile
import wave
from pathlib import Path

from app.config import find_file

RAW_RATE = 22050
PREVIEW_SECONDS = 2
PREFERRED_RAW = "A01.RAW"


def play_raw_preview(game: Path, name: str = PREFERRED_RAW) -> str:
    """Play a short RAW clip. Returns a status string; never raises to the UI."""
    path = find_file(game, name)
    if path is None:
        return f"skip audio: {name} not found"

    if sys.platform != "win32":
        return "skip audio: winsound is Windows-only (no Miles yet)"

    try:
        import winsound
    except ImportError:
        return "skip audio: winsound missing"

    samples = path.read_bytes()[: RAW_RATE * PREVIEW_SECONDS]
    if not samples:
        return f"skip audio: {path.name} empty"

    tmp = Path(tempfile.gettempdir()) / "c2_v0_preview.wav"
    with wave.open(str(tmp), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(1)
        wav.setframerate(RAW_RATE)
        wav.writeframes(samples)
    try:
        winsound.PlaySound(str(tmp), winsound.SND_FILENAME | winsound.SND_ASYNC)
    except RuntimeError as exc:
        return f"skip audio: {exc}"
    return f"playing {path.name} ({len(samples)} B @ {RAW_RATE} Hz, async)"
