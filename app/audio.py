"""Optional RAW preview plus one-shot city SFX (not Miles / AIL).

Ghidra: miles_init 0x11758, AIL_startup 0x72992, push_22050_raw_rate 0x120A6.
tools/decode_raw.py: unsigned 8-bit PCM mono @ 22050 Hz (A01 user-verified).

City SFX are retail ``.wav`` names from the EXE (flat 1.1A tree, or
``sound/`` / ``SOUND/``). Play via pygame if present, else ffplay
(same helper as advisor_video). Never loop. City Only boot must not
play ``A01.RAW`` (that clip is a promotion-length sting).

Pinned play/bind sites (mapped VA):

- ``place.wav`` play ``0x2F40F``
- ``poscl.wav`` / ``negcl2.wav`` bind in ``miles_init`` ``0x117E4`` / ``0x1180A``
- ``fire.wav`` play ``FUN_000696e8`` ``0x697AC``
- ``smrub.wav`` ``0x697CF``; ``medrub.wav`` / ``lrgrub.wav`` ``0x696AC``
  (``cmp edi,2`` / ``jg`` → medium when ``edi<=2``, large when ``edi>2``)
- ``a09.wav`` ``0x619F3`` (overlay/HUD cue — play once, do not arm the
  EXE's every-8-tick loop)
- ``forum.wav`` is copied in ``city_sfx_bind_wavs`` ``0x12F2A`` (ambience
  table). Host plays it once on Forum enter.
- ``gardenb.wav``…``temple1.wav`` in that bind table are looping
  building ambience — do not start those loops.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from app.config import find_file

RAW_RATE = 22050
PREVIEW_SECONDS = 2
PREFERRED_RAW = "A01.RAW"
_MAX_LIVE = 3

# Event → EXE 8.3 name. Do not map City Only start to A01.
EVENT_WAV: dict[str, str] = {
    "place": "place.wav",
    "click": "poscl.wav",
    "click_no": "negcl2.wav",
    "fire": "fire.wav",
    "destroy_s": "smrub.wav",
    "destroy_m": "medrub.wav",
    "destroy_l": "lrgrub.wav",
    "overlay": "a09.wav",
    "forum": "forum.wav",
}


def destroy_event(n_tiles: int) -> str:
    """Rubble SFX class from ``FUN_000696e8`` / ``0x696AC`` (edi vs 2)."""
    if n_tiles <= 1:
        return "destroy_s"
    if n_tiles <= 2:
        return "destroy_m"
    return "destroy_l"


def _ci_dir(parent: Path, name: str) -> Path | None:
    direct = parent / name
    if direct.is_dir():
        return direct
    want = name.upper()
    try:
        for child in parent.iterdir():
            if child.is_dir() and child.name.upper() == want:
                return child
    except OSError:
        return None
    return None


def _ci_file(folder: Path, name: str) -> Path | None:
    direct = folder / name
    if direct.is_file():
        return direct
    want = name.upper()
    try:
        for child in folder.iterdir():
            if child.is_file() and child.name.upper() == want:
                return child
    except OSError:
        return None
    return None


def resolve_wav(game: Path | None, name: str) -> Path | None:
    """Retail WAV: install root, then ``sound/`` / ``SOUND/``. Not repo dumps."""
    if not name or game is None:
        return None
    fname = name if name.lower().endswith(".wav") else f"{name}.wav"
    hit = find_file(game, fname)
    if hit is not None:
        return hit
    for folder_name in ("sound", "SOUND"):
        folder = _ci_dir(game, folder_name)
        if folder is None:
            continue
        hit = _ci_file(folder, fname)
        if hit is not None:
            return hit
    return None


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


class SfxPlayer:
    """One-shot city WAV. ``enabled=False`` is Options Sound off / ``--no-audio``."""

    def __init__(self, game: Path | None, *, enabled: bool = True) -> None:
        self.game = game
        self.enabled = bool(enabled)
        self._pygame = None
        self._sounds: dict[str, object] = {}
        self._live: list[subprocess.Popen[bytes]] = []

    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)
        if not self.enabled:
            self.stop()

    def play(self, event: str) -> str:
        """Play a mapped event. Empty string if muted / missing. Never loops."""
        if not self.enabled:
            return ""
        name = EVENT_WAV.get(event)
        if not name:
            return ""
        path = resolve_wav(self.game, name)
        if path is None:
            return f"skip sfx: {name} not found"
        if self._play_pygame(path):
            return f"sfx {event}={path.name}"
        if self._play_ffplay(path):
            return f"sfx {event}={path.name}"
        return f"skip sfx: no pygame/ffplay for {path.name}"

    def stop(self) -> None:
        self._reap(kill=True)
        if self._pygame is not None:
            try:
                mixer = getattr(self._pygame, "mixer", None)
                if mixer is not None:
                    mixer.stop()
            except (AttributeError, RuntimeError):
                pass

    def close(self) -> None:
        self.stop()

    def _play_pygame(self, path: Path) -> bool:
        mixer = self._pygame_mixer()
        if mixer is None:
            return False
        key = str(path).upper()
        snd = self._sounds.get(key)
        if snd is None:
            try:
                snd = mixer.Sound(str(path))
            except (OSError, RuntimeError):
                return False
            self._sounds[key] = snd
        try:
            snd.play(loops=0)
        except RuntimeError:
            return False
        return True

    def _pygame_mixer(self):
        if self._pygame is False:
            return None
        if self._pygame is not None:
            return self._pygame.mixer
        try:
            import pygame
        except ImportError:
            self._pygame = False
            return None
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except (RuntimeError, pygame.error):
            self._pygame = False
            return None
        self._pygame = pygame
        return pygame.mixer

    def _play_ffplay(self, path: Path) -> bool:
        from app.advisor_video import find_ffplay

        ffplay = find_ffplay()
        if ffplay is None:
            return False
        self._reap(kill=False)
        while len(self._live) >= _MAX_LIVE:
            old = self._live.pop(0)
            _kill_proc(old)
        try:
            proc = subprocess.Popen(
                [
                    str(ffplay),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nodisp",
                    "-autoexit",
                    str(path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        except OSError:
            return False
        self._live.append(proc)
        return True

    def _reap(self, *, kill: bool) -> None:
        keep: list[subprocess.Popen[bytes]] = []
        for proc in self._live:
            if kill or proc.poll() is not None:
                _kill_proc(proc)
            else:
                keep.append(proc)
        self._live = [] if kill else keep


def _kill_proc(proc: subprocess.Popen[bytes]) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.kill()
        proc.wait(timeout=0.3)
    except (OSError, subprocess.TimeoutExpired):
        pass


def selftest(game: Path | None = None) -> list[str]:
    """Pin event→WAV, resolve retail files, honor mute. Does not play."""
    lines: list[str] = []
    want = {
        "place": "place.wav",
        "click": "poscl.wav",
        "click_no": "negcl2.wav",
        "fire": "fire.wav",
        "destroy_s": "smrub.wav",
        "destroy_m": "medrub.wav",
        "destroy_l": "lrgrub.wav",
        "overlay": "a09.wav",
        "forum": "forum.wav",
    }
    if EVENT_WAV != want:
        lines.append(f"FAIL  EVENT_WAV {EVENT_WAV}")
    else:
        lines.append("ok    EVENT_WAV pinned to EXE 8.3 names")
    if "A01" in " ".join(EVENT_WAV.values()).upper() or PREFERRED_RAW.lower() in {
        n.lower() for n in EVENT_WAV.values()
    }:
        lines.append("FAIL  A01 must not be a city SFX event")
    else:
        lines.append("ok    A01 is not a city SFX event")
    if destroy_event(1) != "destroy_s" or destroy_event(2) != "destroy_m":
        lines.append(f"FAIL  destroy 1/2 {destroy_event(1)} {destroy_event(2)}")
    elif destroy_event(3) != "destroy_l" or destroy_event(9) != "destroy_l":
        lines.append(f"FAIL  destroy 3+ {destroy_event(3)} {destroy_event(9)}")
    else:
        lines.append("ok    destroy edi<=2 medium, edi>2 large")
    player = SfxPlayer(game, enabled=False)
    if player.play("place") or player._live:
        lines.append("FAIL  muted SfxPlayer spawned audio")
    else:
        lines.append("ok    muted / --no-audio plays nothing")
    player.close()
    if game is None:
        lines.append("ok    resolve skip (no install)")
        return lines
    missing = []
    found = []
    for event, name in want.items():
        path = resolve_wav(game, name)
        if path is None:
            missing.append(name)
        else:
            found.append(f"{event}={path.name}")
    if missing:
        lines.append("ok    retail missing " + ", ".join(missing))
    if found:
        lines.append("ok    resolved " + ", ".join(found[:6]))
    else:
        lines.append("ok    no retail WAV (SFX stay silent)")
    return lines
