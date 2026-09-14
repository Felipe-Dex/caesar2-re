"""Optional RAW preview plus one-shot city SFX (not Miles / AIL).

Ghidra: miles_init 0x11758, AIL_startup 0x72992, push_22050_raw_rate 0x120A6.
tools/decode_raw.py: unsigned 8-bit PCM mono @ 22050 Hz (A01 user-verified).

City SFX are retail ``.wav`` names from the EXE. Search order:
``{repo}/wav/{name}`` (case-insensitive), then the install root, then
``sound/`` / ``SOUND/``. On Windows, play through WinMM (mixes with
Tk). pygame if present, else ffplay, else winsound one-shots. One-shots
never loop. City Only boot must not play ``A01.RAW`` (promotion sting).

Repo ``wav/`` is a local (gitignored) copy of the retail WAVs. Repo
``sound/`` is the A/B/C + PREBATLE RAW bank (advisor / sting), not
city SFX. There is no ``audios/`` folder. Birds / water / clicks
are those WAVs — see ``findings/city_ambience.md``.

Pinned play/bind sites (mapped VA):

- ``place.wav`` play ``0x2F40F``
- ``poscl.wav`` / ``negcl2.wav`` bind in ``miles_init`` ``0x117E4`` / ``0x1180A``
  (UI click / deny). Host click is ``poscl.wav``.
- ``fire.wav`` play ``FUN_000696e8`` ``0x697AC``
- ``smrub.wav`` ``0x697CF``; ``medrub.wav`` / ``lrgrub.wav`` ``0x696AC``
  (``cmp edi,2`` / ``jg`` → medium when ``edi<=2``, large when ``edi>2``)
- ``a09.wav`` — user-verified ``Plebs are needed!`` labor toast. Play
  once on the rising-edge HUD (not every tick). Overlay well / flyout
  pick is silent (no ``a09.wav``, ``unused.wav``, or ``poscl.wav``).
- ``forum.wav`` is copied in ``city_sfx_bind_wavs`` ``0x12F2A`` (ambience
  table). Host plays it once on Forum enter.
- ``unused.wav`` bind ``0x129B2`` / str ``0x90448`` is the EXE labor
  phrase name. City Only plays ``a09.wav`` (playtest). File may be
  absent on a flat 1.1A tree.
- City bind ``0x12F2A`` copies names into 25 slots at ``0xA3FBC``
  (stride ``0x46``). Mixer tick ``0x12E1E`` (from ``view_frame``
  ``0x3D3D5``) starts at slot 1. Tile draw ``0x3747E`` → mapper
  ``0x12A8F`` sets slot[+0] when that building is on-screen.
  Play is a one-shot via ``0x11B7B`` after slot[+4] reaches ``0xC8``.
  Housing ``0x82–0xA1`` maps to no slot. Garden ``0x78–0x7B`` → slot 1
  (``gardenb/c/d``). ``gardenb.wav`` is the dog (loud burst; no
  ``dog.wav`` in the EXE or retail tree). Do not global-loop anything.
  Honor Options Sound / ``--no-audio``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import wave
from array import array
from pathlib import Path

from app.config import REPO_ROOT, find_file

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
    "forum": "forum.wav",
    "need_plebs": "a09.wav",
}

# City bind 0x12F2A. Slot 0 is unused. Mixer 0x12E1E walks ebx=1..0x18.
# Retail spelling where EXE 8.3 does not match the 1.1A filename.
SLOT_WAVS: dict[int, tuple[str, ...]] = {
    1: ("gardenb.wav", "gardenc.wav", "gardend.wav"),
    2: ("circus1.wav",),
    3: ("barrack2.wav",),
    4: ("bathhs.wav",),
    5: ("colism5.wav", "colism6.wav"),
    6: ("fire.wav",),
    7: ("forum.wav",),
    8: ("fountn.wav",),
    9: ("fountnx.wav",),
    10: ("grammat2.wav",),
    11: ("rhetor.wav",),
    12: ("marketh.wav",),
    13: ("marketl.wav",),
    14: ("plazab.wav",),
    15: ("well.wav",),
    16: ("reserv.wav",),
    17: ("aquadct.wav",),
    18: ("temple1.wav",),
    19: ("theatre.wav",),
    20: ("hbiz.wav",),
    21: ("lbiz.wav",),
}
DOG_SLOT = 1
DOG_WAV = "gardenb.wav"
MIXER_THRESH = 0xC8  # 0x12E63
_AMBIENCE_RESERVED = 2
_MIX_RATE = 11025
_MIX_CHUNK = 2048


def sfx_slot_for_tile_id(tid: int, factory_nibble: int = 0) -> int | None:
    """``0x12A8F`` tile id → slot. Housing ``0x82–0xA1`` is silent."""
    tid = int(tid) & 0xFF
    if tid < 0x78:
        return None
    if tid < 0x7C:
        return 1
    if tid < 0x82:
        return 0xE
    if tid < 0xA2:
        return None
    if tid < 0xAE:
        return 0x12
    if tid < 0xBC:
        return 7
    if tid < 0xBE:
        return 0x11
    if tid < 0xBF:
        return 0x10
    if tid < 0xCB:
        return None
    if tid < 0xD7:
        return 0x11
    if tid < 0xDB:
        return 0xF
    if tid < 0xDF:
        return 8
    if tid < 0xE3:
        return 4
    if tid < 0xE4:
        return 0x17
    if tid < 0xE5:
        return 3
    if tid < 0xE7:
        return 0x13
    if tid < 0xE9:
        return 5
    if tid < 0xF3:
        return 2
    if tid < 0xF4:
        return 0xA
    if tid < 0xF5:
        return 0xB
    if tid < 0xFA:
        return None
    if tid < 0xFB:
        return 0x14 if int(factory_nibble) > 3 else 0x15
    if tid < 0xFC:
        return 0x16
    if tid < 0xFE:
        return 0xD
    return 0xC


def enabled_sfx_slots(
    tiles: bytes | bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    width: int = 80,
    height: int = 80,
    stride: int = 20,
) -> set[int]:
    """Slots whose buildings sit in the inclusive tile AABB (draw-path gate)."""
    from app.city_map import MAP_H, MAP_W, TILE_STRIDE

    w = width or MAP_W
    h = height or MAP_H
    step = stride or TILE_STRIDE
    slots: set[int] = set()
    xa = max(0, min(int(x0), w - 1))
    xb = max(0, min(int(x1), w - 1))
    ya = max(0, min(int(y0), h - 1))
    yb = max(0, min(int(y1), h - 1))
    if xa > xb:
        xa, xb = xb, xa
    if ya > yb:
        ya, yb = yb, ya
    need = w * h * step
    if len(tiles) < need:
        return slots
    for ty in range(ya, yb + 1):
        row = ty * w * step
        for tx in range(xa, xb + 1):
            off = row + tx * step
            tid = tiles[off]
            nibble = (tiles[off + 9] >> 4) & 0xF if off + 9 < len(tiles) else 0
            slot = sfx_slot_for_tile_id(tid, nibble)
            if slot is not None:
                slots.add(slot)
    return slots


def visible_sfx_slots(
    tiles: bytes | bytearray,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    zoom: int = 0,
) -> set[int]:
    """Mapper slots for buildings overlapping the camera well."""
    from app.city_map import visible_iso_tile_range

    x0, y0, x1, y1 = visible_iso_tile_range(cam_x, cam_y, view_w, view_h, zoom)
    return enabled_sfx_slots(tiles, x0, y0, x1, y1)


def dog_eligible_in_rect(
    tiles: bytes | bytearray, x0: int, y0: int, x1: int, y1: int
) -> bool:
    """True when a garden tile (slot 1) sits in the AABB. Housing does not count."""
    return DOG_SLOT in enabled_sfx_slots(tiles, x0, y0, x1, y1)


def dog_eligible(
    tiles: bytes | bytearray,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    zoom: int = 0,
) -> bool:
    """True when a garden is in the camera well. EXE keys on ``0x78–0x7B``, not houses."""
    return DOG_SLOT in visible_sfx_slots(tiles, cam_x, cam_y, view_w, view_h, zoom)


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
    """Repo ``wav/`` first, then install root, then ``sound/`` / ``SOUND/``."""
    if not name:
        return None
    fname = name if name.lower().endswith(".wav") else f"{name}.wav"
    repo_wav = _ci_dir(REPO_ROOT, "wav")
    if repo_wav is not None:
        hit = _ci_file(repo_wav, fname)
        if hit is not None:
            return hit
    if game is None:
        return None
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


def load_pcm(path: Path) -> array | None:
    """Retail city WAV → signed 16-bit mono @ 11025 Hz. None if unreadable."""
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            width = wav.getsampwidth()
            rate = wav.getframerate()
            nframes = wav.getnframes()
            raw = wav.readframes(nframes)
            comptype = wav.getcomptype()
    except (OSError, wave.Error):
        return None
    if comptype not in ("NONE", "not compressed") or channels < 1 or width < 1:
        return None
    if width == 1:
        mono = raw[0::channels] if channels > 1 else raw
        pcm = array("h", ((b - 128) << 8 for b in mono))
    elif width == 2:
        samples = array("h")
        samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
        if channels > 1:
            pcm = array("h", samples[::channels])
        else:
            pcm = samples
    else:
        return None
    if not pcm:
        return None
    if rate != _MIX_RATE and rate > 0:
        pcm = _resample(pcm, rate, _MIX_RATE)
    return pcm


def _resample(pcm: array, src_rate: int, dst_rate: int) -> array:
    if src_rate == dst_rate or not pcm:
        return pcm
    n = max(1, int(len(pcm) * dst_rate / src_rate))
    out = array("h", [0]) * n
    last = len(pcm) - 1
    for i in range(n):
        out[i] = pcm[min(last, i * src_rate // dst_rate)]
    return out


class _Voice:
    __slots__ = ("pcm", "pos", "loops")

    def __init__(self, pcm: array, loops: int) -> None:
        self.pcm = pcm
        self.pos = 0
        self.loops = loops


class _WinmmMixer:
    """In-process 11025 Hz s16 mono mixer. Tk-safe (no SDL / pygame)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._voices: list[_Voice] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._hwo = None
        self.ok = False

    def start(self) -> bool:
        if self.ok:
            return True
        if sys.platform != "win32":
            return False
        try:
            handle = _wave_out_open(_MIX_RATE)
        except OSError:
            return False
        if handle is None:
            return False
        self._hwo = handle
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.ok = True
        return True

    def play(self, pcm: array, *, loops: int = 0) -> bool:
        if not pcm or not self.start():
            return False
        with self._lock:
            self._voices.append(_Voice(pcm, loops))
        return True

    def stop(self) -> None:
        with self._lock:
            self._voices = []
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.6)
        self._thread = None
        hwo = self._hwo
        self._hwo = None
        self.ok = False
        if hwo is not None:
            _wave_out_close(hwo)

    def _run(self) -> None:
        import ctypes

        winmm = ctypes.WinDLL("winmm")
        hwo = self._hwo
        if hwo is None:
            return
        headers: list[tuple[object, ctypes.Array]] = []
        try:
            for _ in range(2):
                buf = ctypes.create_string_buffer(_MIX_CHUNK * 2)
                hdr = _WAVEHDR()
                hdr.lpData = ctypes.cast(buf, ctypes.c_void_p)
                hdr.dwBufferLength = _MIX_CHUNK * 2
                if winmm.waveOutPrepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr)):
                    return
                self._fill(buf)
                if winmm.waveOutWrite(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr)):
                    winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    return
                headers.append((hdr, buf))
            idx = 0
            while not self._stop.is_set():
                hdr, buf = headers[idx]
                if not _wave_hdr_done(hdr):
                    self._stop.wait(0.004)
                    continue
                winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                self._fill(buf)
                hdr.dwFlags = 0
                hdr.dwBufferLength = _MIX_CHUNK * 2
                if winmm.waveOutPrepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr)):
                    break
                if winmm.waveOutWrite(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr)):
                    winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                    break
                idx = 1 - idx
        finally:
            try:
                winmm.waveOutReset(hwo)
            except OSError:
                pass
            for hdr, _buf in headers:
                try:
                    winmm.waveOutUnprepareHeader(hwo, ctypes.byref(hdr), ctypes.sizeof(hdr))
                except OSError:
                    pass

    def _fill(self, buf) -> None:
        acc = [0] * _MIX_CHUNK
        with self._lock:
            keep: list[_Voice] = []
            for voice in self._voices:
                pcm = voice.pcm
                n = len(pcm)
                if n < 1:
                    continue
                pos = voice.pos
                loops = voice.loops
                for i in range(_MIX_CHUNK):
                    acc[i] += pcm[pos]
                    pos += 1
                    if pos >= n:
                        if loops < 0:
                            pos = 0
                        elif loops > 0:
                            loops -= 1
                            pos = 0
                        else:
                            pos = n
                            break
                voice.pos = pos
                voice.loops = loops
                if pos < n or loops != 0:
                    keep.append(voice)
            self._voices = keep
        raw = array("h", (max(-32767, min(32767, s)) for s in acc))
        buf.raw = raw.tobytes()


class _WAVEHDR:
    """Filled lazily so non-Windows imports stay cheap."""

    def __new__(cls):
        import ctypes
        from ctypes import wintypes

        class WAVEHDR(ctypes.Structure):
            _fields_ = [
                ("lpData", ctypes.c_void_p),
                ("dwBufferLength", wintypes.DWORD),
                ("dwBytesRecorded", wintypes.DWORD),
                ("dwUser", ctypes.c_void_p),
                ("dwFlags", wintypes.DWORD),
                ("dwLoops", wintypes.DWORD),
                ("lpNext", ctypes.c_void_p),
                ("reserved", ctypes.c_void_p),
            ]

        return WAVEHDR()


def _wave_hdr_done(hdr) -> bool:
    return bool(int(getattr(hdr, "dwFlags", 0)) & 0x00000001)


def _wave_out_open(rate: int):
    import ctypes
    from ctypes import wintypes

    class WAVEFORMATEX(ctypes.Structure):
        _fields_ = [
            ("wFormatTag", wintypes.WORD),
            ("nChannels", wintypes.WORD),
            ("nSamplesPerSec", wintypes.DWORD),
            ("nAvgBytesPerSec", wintypes.DWORD),
            ("nBlockAlign", wintypes.WORD),
            ("wBitsPerSample", wintypes.WORD),
            ("cbSize", wintypes.WORD),
        ]

    winmm = ctypes.WinDLL("winmm")
    fmt = WAVEFORMATEX(1, 1, rate, rate * 2, 2, 16, 0)
    hwo = ctypes.c_void_p()
    err = winmm.waveOutOpen(ctypes.byref(hwo), 0xFFFFFFFF, ctypes.byref(fmt), 0, 0, 0)
    if err:
        return None
    return hwo


def _wave_out_close(hwo) -> None:
    import ctypes

    winmm = ctypes.WinDLL("winmm")
    try:
        winmm.waveOutReset(hwo)
        winmm.waveOutClose(hwo)
    except OSError:
        pass


class _SlotState:
    __slots__ = ("count", "variant")

    def __init__(self, slot: int) -> None:
        self.count = slot << 3  # bind 0x12F40
        self.variant = 0


class SfxPlayer:
    """One-shot city WAV plus proximity mixer (no global loops).

    ``enabled=False`` is Options Sound off / ``--no-audio``.
    Windows prefers WinMM so Tk + missing pygame still hear clicks / SFX.
    """

    def __init__(self, game: Path | None, *, enabled: bool = True) -> None:
        self.game = game
        self.enabled = bool(enabled)
        self.backend = ""
        self._pygame = None
        self._winmm: _WinmmMixer | None = None
        self._pcm: dict[str, array] = {}
        self._sounds: dict[str, object] = {}
        self._live: list[subprocess.Popen[bytes]] = []
        self._ambience_live: list[subprocess.Popen[bytes]] = []
        self._ambience_on = False
        self._slots = {i: _SlotState(i) for i in SLOT_WAVS}
        if self.enabled:
            self.prepare()

    def prepare(self) -> str:
        """Claim the output device before Tk when possible."""
        if not self.enabled:
            self.backend = "muted"
            return self.backend
        if self._winmm_mixer() is not None:
            self.backend = "winmm"
            return self.backend
        if self._pygame_mixer() is not None:
            self.backend = "pygame"
            return self.backend
        from app.advisor_video import find_ffplay

        if find_ffplay() is not None:
            self.backend = "ffplay"
            return self.backend
        if sys.platform == "win32":
            self.backend = "winsound"
            return self.backend
        self.backend = "none"
        return self.backend

    def set_enabled(self, on: bool) -> None:
        self.enabled = bool(on)
        if not self.enabled:
            self.stop()
            self.backend = "muted"
        else:
            self.prepare()

    def play(self, event: str) -> str:
        """Play a mapped one-shot. Empty string if muted / missing. Never loops."""
        if not self.enabled:
            return ""
        name = EVENT_WAV.get(event)
        if not name:
            return ""
        return self.play_name(name)

    def play_name(self, name: str) -> str:
        """Play a retail WAV stem as a one-shot. Empty if muted / missing."""
        if not self.enabled or not name:
            return ""
        path = resolve_wav(self.game, name)
        if path is None:
            return f"skip sfx: {name} not found"
        if self._play_winmm(path, loops=0):
            return f"sfx {name}"
        if self._play_pygame(path):
            return f"sfx {name}"
        if self._play_ffplay(path):
            return f"sfx {name}"
        if self._play_winsound(path, loop=False):
            return f"sfx {name}"
        return f"skip sfx: no audio device for {path.name}"

    def start_ambience(self) -> str:
        """No-op. EXE does not start gardenb/fountn at city enter."""
        return ""

    def tick_ambience(
        self,
        tiles: bytes | bytearray,
        cam_x: int,
        cam_y: int,
        view_w: int,
        view_h: int,
        zoom: int = 0,
    ) -> str:
        """One mixer pulse: increment enabled slots, maybe fire a one-shot.

        ``0x12E1E``: if slot[+0] (building drawn this frame) then ++[+4];
        play via ``0x11B7B`` when [+4] >= ``0xC8``, then reset and cycle
        variant. Host uses the camera well as the draw-path gate.
        """
        if not self.enabled:
            return ""
        slots = visible_sfx_slots(tiles, cam_x, cam_y, view_w, view_h, zoom)
        played: list[str] = []
        for slot, wavs in SLOT_WAVS.items():
            if slot not in slots:
                continue
            state = self._slots[slot]
            state.count += 1
            if state.count < MIXER_THRESH:
                continue
            state.count = 0
            name = wavs[state.variant % len(wavs)]
            state.variant = (state.variant + 1) % len(wavs)
            msg = self.play_name(name)
            if msg:
                played.append(name)
        return " ".join(played)

    def stop(self) -> None:
        self._reap(kill=True)
        for proc in self._ambience_live:
            _kill_proc(proc)
        self._ambience_live = []
        self._ambience_on = False
        self._slots = {i: _SlotState(i) for i in SLOT_WAVS}
        if self._winmm is not None:
            self._winmm.stop()
            self._winmm = None
        if self._pygame:
            try:
                mixer = getattr(self._pygame, "mixer", None)
                if mixer is not None:
                    mixer.stop()
            except (AttributeError, RuntimeError):
                pass
        if sys.platform == "win32":
            try:
                import winsound

                winsound.PlaySound(None, winsound.SND_PURGE)
            except (ImportError, RuntimeError):
                pass

    def close(self) -> None:
        self.stop()

    def _pcm_for(self, path: Path) -> array | None:
        key = str(path).upper()
        hit = self._pcm.get(key)
        if hit is not None:
            return hit
        pcm = load_pcm(path)
        if pcm is None:
            return None
        self._pcm[key] = pcm
        return pcm

    def _play_winmm(self, path: Path, *, loops: int) -> bool:
        mixer = self._winmm_mixer()
        if mixer is None:
            return False
        pcm = self._pcm_for(path)
        if pcm is None:
            return False
        return mixer.play(pcm, loops=loops)

    def _winmm_mixer(self) -> _WinmmMixer | None:
        if self._winmm is False:
            return None
        if self._winmm is not None:
            return self._winmm
        mix = _WinmmMixer()
        if not mix.start():
            self._winmm = False
            return None
        self._winmm = mix
        self.backend = "winmm"
        return mix

    def _play_pygame(
        self, path: Path, *, loops: int = 0, reserved: int | None = None
    ) -> bool:
        mixer = self._pygame_mixer()
        if mixer is None:
            return False
        key = str(path).upper()
        snd = self._sounds.get(key)
        if snd is None:
            try:
                snd = mixer.Sound(str(path))
            except Exception:
                return False
            self._sounds[key] = snd
        try:
            if reserved is not None:
                mixer.Channel(int(reserved)).play(snd, loops=loops)
            else:
                snd.play(loops=loops)
        except Exception:
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
                pygame.mixer.pre_init(_MIX_RATE, -16, 1, 512)
                pygame.mixer.init(frequency=_MIX_RATE, size=-16, channels=1, buffer=512)
            n = max(16, int(pygame.mixer.get_num_channels()))
            pygame.mixer.set_num_channels(n)
            pygame.mixer.set_reserved(_AMBIENCE_RESERVED)
        except Exception:
            self._pygame = False
            return None
        self._pygame = pygame
        return pygame.mixer

    def _play_ffplay(self, path: Path, *, loop: bool = False) -> bool:
        from app.advisor_video import find_ffplay

        ffplay = find_ffplay()
        if ffplay is None:
            return False
        if not loop:
            self._reap(kill=False)
            while len(self._live) >= _MAX_LIVE:
                old = self._live.pop(0)
                _kill_proc(old)
        cmd = [
            str(ffplay),
            "-hide_banner",
            "-loglevel",
            "error",
            "-nodisp",
            "-vn",
            "-autoexit",
        ]
        if loop:
            cmd.extend(["-loop", "0"])
        cmd.append(str(path))
        env = os.environ.copy()
        env.setdefault("SDL_AUDIODRIVER", "directsound")
        popen_kw: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
            "env": env,
        }
        if sys.platform == "win32":
            popen_kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.Popen(cmd, **popen_kw)
        except OSError:
            return False
        if loop:
            time.sleep(0.05)
            if proc.poll() is not None:
                return False
            self._ambience_live.append(proc)
        else:
            self._live.append(proc)
        self.backend = self.backend or "ffplay"
        return True

    def _play_winsound(self, path: Path, *, loop: bool) -> bool:
        if sys.platform != "win32":
            return False
        try:
            import winsound
        except ImportError:
            return False
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        if loop:
            flags |= winsound.SND_LOOP
        try:
            winsound.PlaySound(str(path), flags)
        except RuntimeError:
            return False
        self.backend = self.backend or "winsound"
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
        "forum": "forum.wav",
        "need_plebs": "a09.wav",
    }
    if EVENT_WAV != want:
        lines.append(f"FAIL  EVENT_WAV {EVENT_WAV}")
    elif EVENT_WAV.get("overlay"):
        lines.append("FAIL  overlay pick must be silent (no WAV)")
    elif EVENT_WAV["need_plebs"] != "a09.wav":
        lines.append("FAIL  labor toast must be a09.wav")
    elif EVENT_WAV["click"] != "poscl.wav":
        lines.append("FAIL  click must be poscl.wav")
    else:
        lines.append("ok    EVENT_WAV pinned to EXE 8.3 names")
        lines.append("ok    click is poscl.wav; labor toast is a09.wav; overlay pick is silent")
    if SLOT_WAVS.get(DOG_SLOT) != ("gardenb.wav", "gardenc.wav", "gardend.wav"):
        lines.append(f"FAIL  slot 1 {SLOT_WAVS.get(DOG_SLOT)}")
    elif SLOT_WAVS.get(8) != ("fountn.wav",):
        lines.append(f"FAIL  slot 8 {SLOT_WAVS.get(8)}")
    elif DOG_WAV != "gardenb.wav":
        lines.append("FAIL  dog wav must be gardenb.wav")
    elif MIXER_THRESH != 0xC8:
        lines.append(f"FAIL  mixer thresh {MIXER_THRESH:#x}")
    else:
        lines.append("ok    dog is gardenb.wav (slot 1); no global gardenb/fountn loop")
    amb_want = {"dog": "gardenb.wav", "water": "fountn.wav"}
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
    if player.play("place") or player._live or player.start_ambience() or player._ambience_live:
        lines.append("FAIL  muted SfxPlayer spawned audio")
    elif player._winmm:
        lines.append("FAIL  muted SfxPlayer opened WinMM")
    else:
        lines.append("ok    muted / --no-audio plays nothing")
    player.close()
    if sfx_slot_for_tile_id(0x20) is not None:
        lines.append(f"FAIL  grass slot {sfx_slot_for_tile_id(0x20)}")
    elif sfx_slot_for_tile_id(0x78) != 1 or sfx_slot_for_tile_id(0x7B) != 1:
        lines.append("FAIL  garden 0x78-0x7B must be slot 1")
    elif sfx_slot_for_tile_id(0x82) is not None or sfx_slot_for_tile_id(0xA1) is not None:
        lines.append("FAIL  housing 0x82-0xA1 must be silent")
    elif sfx_slot_for_tile_id(0x7C) != 0xE:
        lines.append("FAIL  plaza slot")
    elif sfx_slot_for_tile_id(0xDD) != 8 or sfx_slot_for_tile_id(0xD7) != 0xF:
        lines.append("FAIL  fountain/well slots")
    elif sfx_slot_for_tile_id(0xBE) != 0x10 or sfx_slot_for_tile_id(0xCB) != 0x11:
        lines.append("FAIL  reserv/aquadct slots")
    else:
        lines.append("ok    0x12A8F mapper: garden=1 housing=none fountain=8 well=15")
    blank = bytearray(80 * 80 * 20)
    house = bytearray(blank)
    house[40 * 80 * 20 + 40 * 20] = 0x82
    garden = bytearray(blank)
    garden[40 * 80 * 20 + 40 * 20] = 0x78
    far = bytearray(blank)
    far[0] = 0x78
    if dog_eligible_in_rect(blank, 0, 0, 79, 79):
        lines.append("FAIL  empty map must not be dog-eligible")
    elif dog_eligible_in_rect(house, 0, 0, 79, 79):
        lines.append("FAIL  house in view is not dog-eligible (EXE keys gardens)")
    elif not dog_eligible_in_rect(garden, 30, 30, 50, 50):
        lines.append("FAIL  garden in view must be dog-eligible")
    elif dog_eligible_in_rect(garden, 0, 0, 5, 5):
        lines.append("FAIL  garden off-rect must not be dog-eligible")
    elif dog_eligible_in_rect(far, 30, 30, 50, 50):
        lines.append("FAIL  garden off-screen must not be dog-eligible")
    else:
        lines.append("ok    dog: empty/house silent; garden in view only")
    if dog_eligible(blank, 0, 0, 478, 456, 0):
        lines.append("FAIL  empty camera well is dog-eligible")
    elif not dog_eligible(garden, 0, 0, 2000, 1200, 0):
        lines.append("FAIL  garden at (40,40) should be in a wide well")
    else:
        from app.city_map import iso_canvas_size, visible_iso_tile_range

        ww, wh = iso_canvas_size(0)
        cam_x, cam_y = max(0, ww - 400), max(0, wh - 300)
        x0, y0, x1, y1 = visible_iso_tile_range(cam_x, cam_y, 400, 300, 0)
        off_screen = 40 < x0 or 40 > x1 or 40 < y0 or 40 > y1
        far_hit = dog_eligible(garden, cam_x, cam_y, 400, 300, 0)
        if off_screen and far_hit:
            lines.append("FAIL  garden at (40,40) eligible when camera AABB excludes it")
        elif not off_screen:
            lines.append(f"ok    dog camera gate (far AABB still {x0},{y0}..{x1},{y1})")
        else:
            lines.append("ok    dog camera gate: empty silent; garden follows viewport")
    quiet = SfxPlayer(game, enabled=False)
    if quiet.tick_ambience(garden, 0, 0, 640, 480, 0) or quiet._ambience_on:
        lines.append("FAIL  muted tick_ambience played")
    else:
        lines.append("ok    muted tick_ambience is silent")
    quiet.close()
    pcm_ok = 0
    for name in ("gardenb.wav", "fountn.wav", "poscl.wav"):
        path = resolve_wav(game, name)
        if path is None:
            continue
        pcm = load_pcm(path)
        if pcm is None or len(pcm) < 8:
            lines.append(f"FAIL  load_pcm {name}")
        else:
            pcm_ok += 1
    if pcm_ok >= 3:
        lines.append("ok    load_pcm gardenb/fountn/poscl")
    elif pcm_ok:
        lines.append(f"ok    load_pcm {pcm_ok} clips")
    missing = []
    found = []
    repo_first = False
    for event, name in {**want, **amb_want}.items():
        path = resolve_wav(game, name)
        if path is None:
            missing.append(name)
        else:
            found.append(f"{event}={path.name}")
            if path.parent.name.lower() == "wav":
                repo_first = True
    if repo_first:
        lines.append("ok    resolve prefers repo wav/")
    if game is None and not found:
        lines.append("ok    resolve skip (no install)")
        return lines
    if missing:
        lines.append("ok    retail missing " + ", ".join(missing))
    if found:
        lines.append("ok    resolved " + ", ".join(found[:8]))
    elif game is not None:
        lines.append("ok    no retail WAV (SFX stay silent)")
    if sys.platform == "win32":
        live = SfxPlayer(game, enabled=True)
        backend = live.prepare()
        winmm_ok = live._winmm not in (None, False) and bool(
            getattr(live._winmm, "ok", False)
        )
        live.close()
        if backend != "winmm" or not winmm_ok:
            lines.append(f"FAIL  Windows SFX backend {backend!r} (want winmm)")
        else:
            lines.append("ok    Windows SFX backend winmm")
    return lines
