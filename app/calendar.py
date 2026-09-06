"""City HUD date from SavChunks 25/26 (FUN_0003fbcf / FUN_0006189d).

year = chunk 25 (i32, negative = BC). month = chunk 26 (0=January … 11).
city_sim_phase wrap > 0xD6 calls calendar_advance (month++).

City clock: sim_tick_due 0x3E4B9 gates pulses from [0x9CE50] + dt.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

# start_city_assignment: [0x102AA0] = -300, [0x102A88] = 0 (January).
YEAR_VA = 0x102AA0
YEAR_CHUNK = 25
YEAR_SIZE = 4

MONTH_VA = 0x102A88
MONTH_CHUNK = 26
MONTH_SIZE = 4

# C2.ENG file slot [24] = January. Packed NUL run: Jan…Dec, BC, AD, To, Week 1.
# HUD FUN_00026f16: EAX=0x19 (EXE index = file slot+1), EDX=month skips NULs.
C2ENG_JANUARY = 24

# sim_tick_due 0x3E4B9: [0x9CE50] speed scalar → (100-val)/10 ; need acc >= n*0x32+0x32.
# Default 70 is the usual Impressions slider (C3/Pharaoh). Ghidra was down this pass;
# not re-read from init_new_city. Play uses catch-up 1×; Faster uses 4× ([0xC45A0]).
SPEED_SCALAR_DEFAULT = 70
TICK_MS = 0x32  # 50 — EXE unit in sim_tick_due


def sim_tick_interval_ms(speed_scalar: int = SPEED_SCALAR_DEFAULT) -> int:
    """Milliseconds between sim_tick_due pulses (0x3E4B9)."""
    val = max(0, min(100, int(speed_scalar)))
    steps = (100 - val) // 10
    return steps * TICK_MS + TICK_MS

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)


@dataclass(frozen=True)
class GameDate:
    """HUD calendar. year_raw is the signed SavChunk 25 dword."""

    year_raw: int
    month: int  # 0..11
    month_chunk: int = MONTH_CHUNK

    @property
    def year_bc(self) -> int | None:
        if self.year_raw < 0:
            return -self.year_raw
        return None

    @property
    def year_ad(self) -> int | None:
        if self.year_raw >= 0:
            return self.year_raw
        return None

    @property
    def month_name(self) -> str:
        if 0 <= self.month < 12:
            return MONTHS[self.month]
        return f"?{self.month}"


def chunk_i32(chunks: Sequence[memoryview], index: int) -> int:
    raw = chunks[index]
    if len(raw) < 4:
        raise ValueError(f"chunk {index} is {len(raw)} bytes, want 4")
    return struct.unpack_from("<i", raw, 0)[0]


def load_sav_date(chunks: Sequence[memoryview]) -> GameDate:
    year = chunk_i32(chunks, YEAR_CHUNK)
    month = chunk_i32(chunks, MONTH_CHUNK)
    return GameDate(year_raw=year, month=month, month_chunk=MONTH_CHUNK)


def format_hud_date(date: GameDate) -> str:
    """Same order as city HUD: year then era then month (187 BC January)."""
    if date.year_raw < 0:
        return f"{-date.year_raw} BC {date.month_name}"
    return f"{date.year_raw} AD {date.month_name}"


def date_from_sav_path(path: Path, sizes: Sequence[int], *, month_chunk: int = MONTH_CHUNK) -> GameDate:
    from app.city_map import walk_sav_chunks

    chunks = walk_sav_chunks(path.read_bytes(), sizes)
    year = chunk_i32(chunks, YEAR_CHUNK)
    month = chunk_i32(chunks, month_chunk)
    return GameDate(year_raw=year, month=month, month_chunk=month_chunk)


class DateCounters(Protocol):
    """Duck type for SimState year/month/week_gate (chunks 25/26/27)."""

    year_raw: int
    month: int
    week_gate: int


def calendar_advance(state: DateCounters) -> bool:
    """0x3FBCF — one month after city_sim_phase wrap > 0xD6.

    Chunk 27 week_gate += 1; if > 0 (always on saved cities) reset and month++.
    December (11) wraps to January and year_raw += 1 (−187 → −186 = 186 BC).
    """
    state.week_gate += 1
    if state.week_gate <= 0:
        return False
    state.week_gate = 0
    # tax/treasury month tick: economy_recompute 0x3FCA0 (C2MODEL [247:279]/[378:404] not trivial) — stub
    state.month += 1
    if state.month < 12:
        return True
    state.month = 0
    state.year_raw += 1
    return True


def selftest() -> list[str]:
    """No SAV. Chunk 25/26 labels + one 0x3FBCF month / year wrap."""

    class _S:
        def __init__(self, year_raw: int, month: int, week_gate: int = 0) -> None:
            self.year_raw = year_raw
            self.month = month
            self.week_gate = week_gate

    lines: list[str] = []
    acheia = GameDate(year_raw=-187, month=0)
    ok = format_hud_date(acheia) == "187 BC January"
    lines.append(f"chunks 25/26 HUD -187/0: {'ok' if ok else 'FAIL'} {format_hud_date(acheia)}")

    nov = GameDate(year_raw=-269, month=10)
    ok = format_hud_date(nov) == "269 BC November"
    lines.append(f"chunks 25/26 HUD -269/10: {'ok' if ok else 'FAIL'} {format_hud_date(nov)}")

    s = _S(-187, 0)
    moved = calendar_advance(s)
    ok = moved and s.month == 1 and s.year_raw == -187 and s.week_gate == 0
    lines.append(
        f"calendar_advance Jan→Feb: {'ok' if ok else 'FAIL'} "
        f"{format_hud_date(GameDate(s.year_raw, s.month))}"
    )

    s = _S(-187, 11)
    moved = calendar_advance(s)
    ok = moved and s.month == 0 and s.year_raw == -186
    lines.append(
        f"calendar_advance Dec→Jan year++: {'ok' if ok else 'FAIL'} "
        f"{format_hud_date(GameDate(s.year_raw, s.month))}"
    )

    ok = sim_tick_interval_ms(100) == 50 and sim_tick_interval_ms(70) == 200
    ok = ok and sim_tick_interval_ms(50) == 300 and sim_tick_interval_ms(0) == 550
    lines.append(
        f"sim_tick_due interval 100/70/50/0: {'ok' if ok else 'FAIL'} "
        f"{sim_tick_interval_ms(70)}ms @70"
    )
    return lines
