"""Advisor talking-head clips next to FUN_00058c87 banners.

EXE table @ VA 0x9A5BC (14-byte 8.3 names). Indexer 0x59248:
``lea eax, [esi-0x50]`` then ``eax * 14`` — ESI is enqueue EAX
(official C2.ENG slot + 1). Stem = table[slot - 79].

Slots below 79 (Need More Plebs [7]+14 / Idle Plebs [35]+26) are
confirm-pack status-bar toasts — sound + red HUD text, no talking-head.
``null.smk`` means no clip. C2.ENG [60] is Query overlay, not a 58c87
slot — do not play a clip for it.

City Only start Hail [79] is the “build your city” briefing. The EXE
table names ``congrat.smk`` there (same talking-head as pop milestones
/ New Structure). The host plays that clip **muted** so the promotion
fanfare does not fire on map-open. Pop / unlock still play audio when
Sound is on. ``promote.smk`` is Career kind 5, not this banner.

Search (mp4 only, case-insensitive):
1. ``{root}/videos_new/{stem}.mp4``
2. ``{root}/video/{stem}.mp4``
3. ``{root}/videos/{stem}.mp4`` (decode_smk.py dest / this checkout)

Roots: game install first, then repo. ffmpeg pipe (same pattern as
``tools/decode_smk.py``). Missing file or decoder → banner only.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path

from PIL import Image

from app.config import REPO_ROOT

# Retail SMK letterbox; play call at 0x59260 ebx=0x50 edx=0x60.
SMK_X, SMK_Y = 80, 96
SMK_W, SMK_H = 320, 152
TABLE_BASE_SLOT = 79  # Hail [79] → index 0
FRAME_BYTES = SMK_W * SMK_H * 3
# Fallback only when ffprobe is missing. Retail SMK is 12 fps (MESSAGE 14.08).
DEFAULT_FPS = 12.0
DELAY_MS = 83
_BUF_CAP = 8

# table[slot - 79] — 40 records then other data. Pin: xrefs + C2.ENG titles.
_STEM_TABLE: tuple[str, ...] = (
    "congrat",   # 79 Hail
    "sick",      # 80 Disease!
    "fire",      # 81 Fire Alert!
    "warning",   # 82 The City Is Attacked!
    "congrat",   # 83 Another Year Passes
    "warning",   # 84 Services Cut
    "robbery",   # 85 Stolen!
    "rioters",   # 86 Rioting!
    "robbery",   # 87 Attempted Robbery
    "robbery",   # 88 Stolen!
    "warning",   # 89 Too many Cohorts!
    "armywarn",  # 90 Raiders Sighted!
    "armywarn",  # 91 Local Uprising!
    "armywarn",  # 92 Barbarian Invasion!
    "armywarn",  # 93 Enemy Invades!
    "armywarn",  # 94 Walls Attacked!
    "armywarn",  # 95 Defenses Breached!
    "warning",   # 96 Illegal Order
    "warning",   # 97 No Denarii!
    "warning",   # 98
    "warning",   # 99
    "warning",   # 100 Insufficient Plebs
    "warning",   # 101
    "warning",   # 102
    "congrat",   # 103 Good Going!
    "congrat",   # 104 Well Done!
    "congrat",   # 105 Congratulations!
    "congrat",   # 106 Congratulations!
    "congrat",   # 107 Congratulations!
    "congrat",   # 108 Excellent!
    "congrat",   # 109 Incredible!
    "congrat",   # 110 Unbelievable!
    "congrat",   # 111 Astounding!
    "armywarn",  # 112
    "armywarn",  # 113
    "congrat",   # 114 New Structure Available
    "congrat",   # 115
    "null",      # 116
    "null",      # 117
    "null",      # 118
)

_NEW_DIR = "videos_new"
_OLD_DIRS = ("video", "videos")
# Congrat fanfare is for first-time pop / unlock, not Hail or New Year.
_CONGRAT_AUDIO_SLOTS = frozenset(range(103, 112)) | {114, 115}


def video_stem_for_slot(slot: int) -> str | None:
    """Retail SMK stem for an official C2.ENG slot, or None if no clip."""
    if slot < TABLE_BASE_SLOT:
        return None
    idx = slot - TABLE_BASE_SLOT
    if idx < 0 or idx >= len(_STEM_TABLE):
        return "message"
    stem = _STEM_TABLE[idx]
    if stem == "null":
        return None
    return stem


def video_stem_for_message(msg) -> str | None:
    """Clip on disk. Hail [79] is congrat (muted separately)."""
    slot = int(getattr(msg, "slot", -1))
    return video_stem_for_slot(slot)


def advisor_plays_audio(msg) -> bool:
    """True when the talking-head may play mp4 audio (Options Sound)."""
    slot = int(getattr(msg, "slot", -1))
    key = str(getattr(msg, "key", "") or "")
    if key == "hail" or slot == 79:
        return False
    stem = video_stem_for_slot(slot)
    if stem == "congrat":
        return slot in _CONGRAT_AUDIO_SLOTS
    return stem is not None


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


def video_roots(game: Path | None) -> list[Path]:
    roots: list[Path] = []
    for raw in (game, REPO_ROOT, REPO_ROOT / "app", REPO_ROOT / "data"):
        if raw is None:
            continue
        path = Path(raw)
        if path.is_dir() and path not in roots:
            roots.append(path)
    return roots


def resolve_advisor_video(game: Path | None, stem: str | None) -> Path | None:
    """videos_new/{stem}.mp4, else video/{stem}.mp4, else videos/{stem}.mp4."""
    if not stem:
        return None
    name = f"{stem}.mp4"
    roots = video_roots(game)
    for root in roots:
        folder = _ci_dir(root, _NEW_DIR)
        if folder is not None:
            hit = _ci_file(folder, name)
            if hit is not None:
                return hit
    for folder_name in _OLD_DIRS:
        for root in roots:
            folder = _ci_dir(root, folder_name)
            if folder is None:
                continue
            hit = _ci_file(folder, name)
            if hit is not None:
                return hit
    return None


def find_ffmpeg() -> Path | None:
    which = shutil.which("ffmpeg")
    if which:
        return Path(which)
    winget = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
    if winget.is_dir():
        hits = sorted(winget.rglob("ffmpeg.exe"))
        if hits:
            return hits[0]
    return None


def _ffmpeg_sibling(name: str) -> Path | None:
    which = shutil.which(name)
    if which:
        return Path(which)
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        return None
    exe = f"{name}.exe" if sys.platform == "win32" else name
    sibling = ffmpeg.with_name(exe)
    return sibling if sibling.is_file() else None


def find_ffplay() -> Path | None:
    return _ffmpeg_sibling("ffplay")


def find_ffprobe() -> Path | None:
    return _ffmpeg_sibling("ffprobe")


def _parse_rate(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text or text in {"N/A", "0/0", "0"}:
        return None
    if "/" in text:
        num_s, den_s = text.split("/", 1)
        try:
            num, den = float(num_s), float(den_s)
        except ValueError:
            return None
        if den == 0:
            return None
        return num / den
    try:
        return float(text)
    except ValueError:
        return None


def _parse_dim(raw: str) -> int | None:
    text = (raw or "").strip()
    if not text or text in {"N/A", "0"}:
        return None
    try:
        val = int(float(text))
    except ValueError:
        return None
    return val if val > 0 else None


def probe_mp4(path: Path) -> tuple[float, float | None, int | None, int | None]:
    """Return (fps, duration_s, width, height). fps falls back to retail 12."""
    probe = find_ffprobe()
    if probe is None:
        return DEFAULT_FPS, None, None, None
    try:
        run = subprocess.run(
            [
                str(probe),
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=r_frame_rate,avg_frame_rate,duration,width,height",
                "-of",
                "default=noprint_wrappers=1:nokey=0",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return DEFAULT_FPS, None, None, None
    rates: dict[str, str] = {}
    for line in (run.stdout or "").splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            rates[key.strip()] = val.strip()
    fps = _parse_rate(rates.get("avg_frame_rate", ""))
    if fps is None or fps < 1:
        fps = _parse_rate(rates.get("r_frame_rate", ""))
    if fps is None or fps < 1 or fps > 60:
        fps = DEFAULT_FPS
    duration = _parse_rate(rates.get("duration", ""))
    return fps, duration, _parse_dim(rates.get("width", "")), _parse_dim(
        rates.get("height", "")
    )


def probe_mp4_timing(path: Path) -> tuple[float, float | None]:
    """Return (fps, duration_s). fps falls back to retail 12, never a guessed 30."""
    fps, duration, _w, _h = probe_mp4(path)
    return fps, duration


def _video_filter(src_w: int | None, src_h: int | None) -> str:
    """Fit into the EXE 320×152 play rect without stretch-skew.

    A 320×152 mp4 is copied as-is (no extra letterbox). Other aspects
    scale with decrease and pad *centered* — ``(ow-iw)/2`` evaluates to
    x=0 on some ffmpeg builds, so x/y are ``-1`` (center).
    """
    if src_w == SMK_W and src_h == SMK_H:
        return "setsar=1,format=rgb24"
    return (
        f"scale={SMK_W}:{SMK_H}:force_original_aspect_ratio=decrease"
        f":force_divisible_by=2,setsar=1,"
        f"pad={SMK_W}:{SMK_H}:-1:-1:color=black,format=rgb24"
    )


def videos_new_overrides(game: Path | None, stems: list[str]) -> list[str]:
    """Stems that resolve from videos_new (not the old video/ fallback)."""
    out: list[str] = []
    for stem in stems:
        path = resolve_advisor_video(game, stem)
        if path is None:
            continue
        if path.parent.name.upper() == "VIDEOS_NEW":
            out.append(stem)
    return out


class AdvisorClip:
    """Play one mp4 into 320x152 RGB frames, paced to probed source fps.

    One playthrough, then freeze on the last frame until ``close()``.
    ffmpeg is back-pressured: the decode thread only reads the next pipe
    frame when the PTS buffer has room. ``snapshot()`` picks the frame
    whose PTS window covers *now* — a late tk ``after()`` does not drain
    the pipe or flash every decoded frame.
    """

    def __init__(self, path: Path, *, mute: bool = True) -> None:
        self.path = path
        self.mute = mute
        self.fps, self.duration_s, self.src_w, self.src_h = probe_mp4(path)
        self.delay_ms = max(16, int(round(1000.0 / self.fps)))
        self.frame: Image.Image | None = None
        self.decoded = 0
        self.finished = False
        self.playthroughs = 0
        self._stop = threading.Event()
        self._cond = threading.Condition()
        self._buf: deque[tuple[float, Image.Image]] = deque()
        self._shown: Image.Image | None = None
        self._t0: float | None = None
        self._video: subprocess.Popen[bytes] | None = None
        self._audio: subprocess.Popen[bytes] | None = None
        self._thread: threading.Thread | None = None
        self._proc_lock = threading.Lock()

    def begin(self) -> bool:
        """Decode on a daemon thread. First frame may arrive after begin()."""
        if find_ffmpeg() is None:
            return False
        if self._thread is not None:
            return True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def start(self) -> bool:
        if not self.begin():
            return False
        for _ in range(40):
            with self._cond:
                if self._shown is not None or self.frame is not None:
                    return True
            assert self._thread is not None
            self._thread.join(0.05)
            if not self._thread.is_alive() and self.frame is None:
                return False
        return self.frame is not None

    def close(self) -> None:
        self._stop.set()
        with self._cond:
            self._cond.notify_all()
        self._kill_procs()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=0.4)

    def set_mute(self, mute: bool) -> None:
        """Honor Options Sound mid-clip. ``--no-audio`` starts muted."""
        self.mute = bool(mute)
        with self._proc_lock:
            if self.mute:
                audio = self._audio
                self._audio = None
            else:
                audio = None
                if self._audio is None and not self._stop.is_set():
                    self._audio = self._spawn_audio()
        if audio is None:
            return
        try:
            audio.kill()
            audio.wait(timeout=0.3)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _kill_procs(self) -> None:
        with self._proc_lock:
            procs = (self._video, self._audio)
            self._video = None
            self._audio = None
        for proc in procs:
            if proc is None:
                continue
            try:
                proc.kill()
                proc.wait(timeout=0.3)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def _kill_video_only(self) -> None:
        with self._proc_lock:
            video = self._video
            self._video = None
        if video is None:
            return
        try:
            video.kill()
            video.wait(timeout=0.3)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _spawn_video(self) -> subprocess.Popen[bytes] | None:
        ffmpeg = find_ffmpeg()
        if ffmpeg is None:
            return None
        vf = _video_filter(self.src_w, self.src_h)
        try:
            return subprocess.Popen(
                [
                    str(ffmpeg),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(self.path),
                    "-an",
                    "-vf",
                    vf,
                    "-f",
                    "rawvideo",
                    "-pix_fmt",
                    "rgb24",
                    "-s",
                    f"{SMK_W}x{SMK_H}",
                    "pipe:1",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        except OSError:
            return None

    def _spawn_audio(self) -> subprocess.Popen[bytes] | None:
        if self.mute:
            return None
        ffplay = find_ffplay()
        if ffplay is None:
            return None
        try:
            return subprocess.Popen(
                [
                    str(ffplay),
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nodisp",
                    "-autoexit",
                    str(self.path),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
        except OSError:
            return None

    def _loop(self) -> None:
        video = self._spawn_video()
        if video is None or video.stdout is None:
            self.finished = True
            return
        with self._proc_lock:
            self._video = video
            if self._audio is None:
                self._audio = self._spawn_audio()
        index = 0
        t0: float | None = None
        while not self._stop.is_set():
            with self._cond:
                while len(self._buf) >= _BUF_CAP and not self._stop.is_set():
                    self._cond.wait(timeout=0.05)
                if self._stop.is_set():
                    break
            raw = video.stdout.read(FRAME_BYTES)
            if raw is None or len(raw) < FRAME_BYTES:
                break
            img = Image.frombytes("RGB", (SMK_W, SMK_H), raw)
            with self._cond:
                if t0 is None:
                    t0 = time.monotonic()
                    self._t0 = t0
                pts = t0 + index / self.fps
                self._buf.append((pts, img))
                self.decoded += 1
                if self._shown is None:
                    self._shown = img
                    self.frame = img
                self._cond.notify_all()
            index += 1
        self._wait_playthrough_end()
        self._kill_video_only()
        with self._cond:
            if self._buf:
                last = self._buf[-1]
                self._buf.clear()
                self._buf.append(last)
                self._shown = last[1]
                self.frame = last[1]
            self.playthroughs = 1 if index else 0
            self.finished = True
            self._cond.notify_all()

    def _wait_playthrough_end(self) -> None:
        """Hold until the last buffered PTS window ends, then freeze."""
        period = 1.0 / self.fps
        while not self._stop.is_set():
            with self._cond:
                if not self._buf:
                    return
                last_pts = self._buf[-1][0]
            remain = last_pts + period - time.monotonic()
            if remain <= 0:
                return
            if self._stop.wait(min(0.05, remain)):
                return

    def snapshot(self) -> Image.Image | None:
        """Frame whose PTS window covers now. Does not read the ffmpeg pipe."""
        now = time.monotonic()
        period = 1.0 / self.fps
        with self._cond:
            while len(self._buf) > 1 and self._buf[0][0] + period <= now:
                self._buf.popleft()
            if self._buf and self._buf[0][0] <= now:
                self._shown = self._buf[0][1]
                self.frame = self._shown
            self._cond.notify_all()
            frame = self._shown
            if frame is None:
                return None
            return frame.copy()


def hosted_city_stems() -> dict[str, str | None]:
    """City Only banner keys → stem (None = no clip)."""
    return {
        "hail": video_stem_for_slot(79),
        "fire": video_stem_for_slot(81),
        "services_cut": video_stem_for_slot(84),
        "theft": video_stem_for_slot(88),
        "broke": video_stem_for_slot(97),
        "pop:200": video_stem_for_slot(103),
        "unlock": video_stem_for_slot(114),
    }


def selftest(game: Path | None = None) -> list[str]:
    lines: list[str] = []
    if video_stem_for_slot(81) != "fire":
        lines.append(f"FAIL  fire stem {video_stem_for_slot(81)!r}")
    else:
        lines.append("ok    [81] Fire Alert! -> fire")
    if video_stem_for_slot(88) != "robbery":
        lines.append(f"FAIL  theft stem {video_stem_for_slot(88)!r}")
    else:
        lines.append("ok    [88] Stolen! -> robbery")
    if video_stem_for_slot(79) != "congrat":
        lines.append(f"FAIL  EXE table [79] {video_stem_for_slot(79)!r}")
    else:
        lines.append("ok    EXE table [79] congrat.smk")
    hail = type("M", (), {"slot": 79, "key": "hail"})()
    pop200 = type("M", (), {"slot": 103, "key": "pop:200"})()
    unlock = type("M", (), {"slot": 114, "key": "unlock"})()
    if video_stem_for_message(hail) != "congrat":
        lines.append(f"FAIL  hail clip {video_stem_for_message(hail)!r}")
    elif advisor_plays_audio(hail):
        lines.append("FAIL  Hail must stay silent (no congrat fanfare)")
    else:
        lines.append("ok    Hail [79] -> congrat, muted")
    if video_stem_for_message(pop200) != "congrat" or not advisor_plays_audio(pop200):
        lines.append("FAIL  pop [103] should play congrat audio")
    else:
        lines.append("ok    [103] Good Going! may play congrat")
    if not advisor_plays_audio(unlock):
        lines.append("FAIL  unlock [114] should play congrat audio")
    else:
        lines.append("ok    [114] New Structure may play congrat")
    if video_stem_for_slot(84) != "warning":
        lines.append(f"FAIL  services stem {video_stem_for_slot(84)!r}")
    else:
        lines.append("ok    [84] Services Cut -> warning")
    if video_stem_for_slot(97) != "warning":
        lines.append(f"FAIL  broke stem {video_stem_for_slot(97)!r}")
    else:
        lines.append("ok    [97] No Denarii! -> warning")
    if video_stem_for_slot(114) != "congrat":
        lines.append(f"FAIL  unlock stem {video_stem_for_slot(114)!r}")
    else:
        lines.append("ok    [114] New Structure -> congrat")
    if video_stem_for_slot(7) is not None or video_stem_for_slot(35) is not None:
        lines.append(f"FAIL  labor toast stem {video_stem_for_slot(7)!r}")
    else:
        lines.append("ok    slot < 79 status-bar, no talking-head")
    if video_stem_for_slot(116) is not None:
        lines.append("FAIL  null.smk must skip")
    else:
        lines.append("ok    null.smk -> no clip")
    if resolve_advisor_video(game, None) is not None:
        lines.append("FAIL  empty stem resolved")
    else:
        lines.append("ok    missing stem stays banner-only")
    hosted = hosted_city_stems()
    if "water" in hosted:
        lines.append("FAIL  [60] Query pack must not host a clip")
    else:
        lines.append("ok    [60] not a hosted City Only banner")
    present = []
    for key, stem in hosted.items():
        path = resolve_advisor_video(game, stem)
        if path is not None:
            present.append(f"{key}={path.name}")
    if present:
        lines.append("ok    resolved " + ", ".join(present[:6]))
    else:
        lines.append("ok    no mp4 on disk (banner-only)")
    overrides = videos_new_overrides(game, [s for s in hosted.values() if s])
    if overrides:
        lines.append("ok    videos_new " + ",".join(sorted(set(overrides))))
    else:
        lines.append("ok    no videos_new override")
    clip_path = resolve_advisor_video(game, "congrat")
    if clip_path is None or find_ffmpeg() is None or find_ffprobe() is None:
        lines.append("ok    pacing skip (no congrat mp4 / ffmpeg)")
        return lines
    fps, dur, src_w, src_h = probe_mp4(clip_path)
    if fps < 1 or fps > 60:
        lines.append(f"FAIL  probed fps {fps}")
    else:
        lines.append(
            f"ok    probe {clip_path.parent.name}/congrat.mp4 "
            f"{src_w}x{src_h} {fps:.3f} fps dur={dur}"
        )
    clip = AdvisorClip(clip_path, mute=True)
    if not clip.start():
        lines.append("FAIL  clip start")
        clip.close()
        return lines
    time.sleep(0.30)
    shown = clip.snapshot()
    decoded = clip.decoded
    audio_on = clip._audio is not None
    cap = _BUF_CAP + int(clip.fps * 0.30) + 4
    clip.close()
    if shown is None:
        lines.append("FAIL  no snapshot after 0.3s")
    elif decoded > cap:
        lines.append(f"FAIL  pipe raced decoded={decoded} cap={cap} fps={clip.fps}")
    else:
        lines.append(
            f"ok    paced decoded={decoded} (<= {cap}) in 0.3s at {clip.fps:.3f} fps"
        )
    if audio_on:
        lines.append("FAIL  mute=True spawned ffplay")
    else:
        lines.append("ok    mute=True stays silent")
    if clip.playthroughs > 1:
        lines.append(f"FAIL  clip looped playthroughs={clip.playthroughs}")
    else:
        lines.append("ok    clip playthroughs<=1 in 0.3s")
    once = AdvisorClip(clip_path, mute=True)
    if once.start():
        limit = min((once.duration_s or 2.0) + 1.5, 15.0)
        deadline = time.monotonic() + limit
        last = None
        while not once.finished and time.monotonic() < deadline:
            last = once.snapshot()
            time.sleep(max(0.01, once.delay_ms / 1000.0))
        d1 = once.decoded
        frozen = once.snapshot() or last
        time.sleep(0.30)
        d2 = once.decoded
        loops = once.playthroughs
        ended = once.finished
        once.close()
        if loops > 1:
            lines.append(f"FAIL  replayed clip playthroughs={loops}")
        elif ended and d2 > d1:
            lines.append(f"FAIL  decoded grew after EOF {d1}->{d2}")
        elif ended and frozen is None:
            lines.append("FAIL  last frame dropped after EOF")
        elif ended:
            lines.append("ok    play once then freeze last frame")
        else:
            lines.append("ok    play-once still first pass (long clip)")
    else:
        once.close()
        lines.append("FAIL  play-once clip start")
    if shown is not None and shown.size == (SMK_W, SMK_H):
        left, right = _letterbox_lr(shown)
        if src_w == SMK_W and src_h == SMK_H:
            if left > 2 or right > 2:
                lines.append(f"FAIL  320x152 gained letterbox L{left} R{right}")
            else:
                lines.append("ok    320x152 blit has no extra letterbox")
        elif abs(left - right) > 2:
            lines.append(f"FAIL  letterbox not centered L{left} R{right}")
        else:
            lines.append(f"ok    letterbox centered L{left} R{right}")
    return lines


def _letterbox_lr(img: Image.Image) -> tuple[int, int]:
    """Count near-black columns on each side of a 320×152 RGB frame."""
    px = img.load()
    w, h = img.size

    def col_black(x: int) -> bool:
        dark = 0
        for y in range(h):
            r, g, b = px[x, y][:3]
            if r + g + b < 24:
                dark += 1
        return dark * 4 >= h * 3

    left = 0
    while left < w and col_black(left):
        left += 1
    right = 0
    while right < w and col_black(w - 1 - right):
        right += 1
    return left, right
