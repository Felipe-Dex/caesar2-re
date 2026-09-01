"""City HUD date from SavChunks (FUN_0003fbcf / FUN_0006189d).

Does not tick the calendar. Walkers / sim stay elsewhere.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

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
