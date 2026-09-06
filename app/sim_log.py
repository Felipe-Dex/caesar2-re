"""Append-only city sim log for City Only play / parent-agent reads.

Source of truth: logs/city_sim.log (repo root). Capped ~1.5 MB.
"""

from __future__ import annotations

from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "logs"
LOG_PATH = LOG_DIR / "city_sim.log"
MAX_BYTES = 1_500_000
KEEP_BYTES = 800_000
_LAST: list[str] = []
_LAST_MAX = 12


def last_lines(n: int = 3) -> list[str]:
    return _LAST[-max(1, n) :]


def last_line() -> str:
    return _LAST[-1] if _LAST else ""


def _rotate() -> None:
    if not LOG_PATH.is_file() or LOG_PATH.stat().st_size < MAX_BYTES:
        return
    data = LOG_PATH.read_bytes()
    LOG_PATH.write_bytes(data[-KEEP_BYTES:])


def write(line: str) -> str:
    """Append one line. Returns the line (HUD can reuse it)."""
    text = line.rstrip()
    if not text:
        return ""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _rotate()
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(text + "\n")
    _LAST.append(text)
    if len(_LAST) > _LAST_MAX:
        del _LAST[: len(_LAST) - _LAST_MAX]
    return text


def format_phase(
    *,
    date: str,
    phase: int,
    name: str,
    houses_up: int = 0,
    houses_down: int = 0,
    spawned: int = 0,
    note: str = "",
) -> str:
    bits = [
        date,
        f"slot {phase:#x}",
        name,
        f"houses +{houses_up}/-{houses_down}",
        f"spawn={spawned}",
    ]
    if note:
        bits.append(note)
    return "  ".join(bits)
