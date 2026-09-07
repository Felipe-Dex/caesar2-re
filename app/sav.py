"""sav_write 0x70174 stand-in — City Only dump of host-owned chunks.

The EXE walks 500 {ptr,size} slots at VA 0x9ABC0, then appends 4000 B
from history.dat. The host does not keep that BSS. This writer emits the
same container (221745 + 4000 = 225745) and fills every chunk we own.
Unknown slots are zero — D.SAV structure, empty payload.

Risk: 1.1A sav_read 0x7024A has no checksum and will ingest a 225745-byte
file. That is not a verified retail session. Province / actors26 / goods /
climate / most globals stay zero (not init_new_city BSS). City Only skips
some of those ticks; others may fault. See findings/sav_write.md.

Do not copy retail assets or commit .SAV files.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence
from pathlib import Path

from app.calendar import MONTH_CHUNK, YEAR_CHUNK
from app.city_map import (
    MAP_BYTES,
    N_SAV_CHUNKS,
    SAV_HISTORY_BYTES,
    SAV_SIZE,
    SAV_TABLE_BYTES,
    CityMap,
    load_chunk_sizes,
    load_city_from_sav,
    walk_sav_chunks,
)
from app.city_sim import (
    PHASE_CHUNK,
    ROW_CHUNK,
    WEEK_GATE_CHUNK,
    SimState,
    load_sim_from_sav,
)
from app.new_game import CHUNK_CITY_ONLY, CHUNK_PID, CHUNK_SKILL, CHUNK_TREASURY
from app.walkers import (
    SAV_CHUNK as WALKER_CHUNK,
    WALKER_BYTES,
    Walker,
    load_walkers_from_sav,
    pack_pool,
)

CITY_CHUNK = 13
LABOR_READY_CHUNK = 52
WELFARE_CHUNK = 54
LABOR_EST_CHUNK = 55
LABOR_TABLE_CHUNK = 56
TAX_RATE_CHUNK = 29
IND_TAX_CHUNK = 30
WRAP4_CHUNK = 22
WRAP3_CHUNK = 405
LABOR_INDEX_CHUNK = 416
YEAR_SEED_CHUNK = 325
RATINGS_SEED_CHUNK = 341
RANK_CHUNK = 291
HISTORY_COUNT_CHUNK = 338
POP_CHUNK = 32
GOODS_CHUNK = 339
FACTORY_LABOR_CHUNK = 140
PROVINCE_LINKS_CHUNK = 276

# Named File→Save vs sav_year_end lastyear.sav (REVERSE.md / FELIPE vs LASTYEAR).
_NAMED_FLAGS = (0, 4, 0, 0)
_LASTYEAR_FLAGS = (0, 0, 1, 0x01)

# Host File→Save / F5: {game}/sav/{8.3}.SAV — no OS picker. Original loader
# accepts DOS 8.3 names (CITY.SAV, FELIPE01.SAV, CAESAR2.SAV).
SAV_SUBDIR = "sav"
DEFAULT_SAV_NAME = "CITY.SAV"

# 500 writer sizes from PS.EXE SavChunk[500] (notes/ps_sav_chunks.tsv).
# Embedded so save works when the gitignored TSV is absent.
_EMBEDDED_SIZES: tuple[int, ...] = (
    1, 1, 1, 1, 4, 4, 4, 4550, 11658, 3978, 17688, 9045, 3460, 128000, 28800, 100, 1, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 64, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 64, 1, 1, 1, 1, 1, 1, 1, 1,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 1, 1, 4, 10816, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 50, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 12, 4, 4, 256, 4, 4, 4, 768,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 128, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 80, 80, 80, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 1, 4, 4, 4, 4, 4, 4, 4, 200, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
)

assert len(_EMBEDDED_SIZES) == N_SAV_CHUNKS
assert sum(_EMBEDDED_SIZES) == SAV_TABLE_BYTES

# Chunks the host can emit from live City Only state (not full BSS).
HOST_OWNED_CHUNKS: frozenset[int] = frozenset(
    {
        0,
        1,
        2,
        3,
        WALKER_CHUNK,
        CITY_CHUNK,
        CHUNK_SKILL,
        WRAP4_CHUNK,
        ROW_CHUNK,
        PHASE_CHUNK,
        YEAR_CHUNK,
        MONTH_CHUNK,
        WEEK_GATE_CHUNK,
        CHUNK_TREASURY,
        TAX_RATE_CHUNK,
        IND_TAX_CHUNK,
        31,
        POP_CHUNK,
        33,
        34,
        35,
        36,
        37,
        46,
        LABOR_READY_CHUNK,
        WELFARE_CHUNK,
        LABOR_EST_CHUNK,
        LABOR_TABLE_CHUNK,
        157,
        CHUNK_PID,
        286,
        287,
        288,
        289,
        RANK_CHUNK,
        YEAR_SEED_CHUNK,
        HISTORY_COUNT_CHUNK,
        RATINGS_SEED_CHUNK,
        GOODS_CHUNK,
        FACTORY_LABOR_CHUNK,
        PROVINCE_LINKS_CHUNK,
        WRAP3_CHUNK,
        CHUNK_CITY_ONLY,
        LABOR_INDEX_CHUNK,
    }
)


def chunk_sizes(game: Path | None = None) -> list[int]:
    """500 sav_write sizes. Prefer TSV / EXE; else the embedded table."""
    try:
        sizes = load_chunk_sizes(game)
    except (OSError, ValueError, ImportError):
        sizes = []
    if len(sizes) == N_SAV_CHUNKS and sum(sizes) == SAV_TABLE_BYTES:
        return list(sizes)
    return list(_EMBEDDED_SIZES)


def _i32(value: int) -> bytes:
    return struct.pack("<i", int(value))


def _u8(value: int) -> bytes:
    return bytes((int(value) & 0xFF,))


def _fit(raw: bytes, size: int) -> bytes:
    if len(raw) == size:
        return raw
    if len(raw) > size:
        return raw[:size]
    return raw + bytes(size - len(raw))


def _tiles(city: CityMap | bytearray | bytes) -> bytes:
    blob = city.tiles if isinstance(city, CityMap) else city
    raw = bytes(blob)
    if len(raw) != MAP_BYTES:
        raise ValueError(f"city map is {len(raw)} bytes, want {MAP_BYTES}")
    return raw


def _history(sim: SimState | None) -> bytes:
    raw = bytes(getattr(sim, "history", b"") or b"")
    return _fit(raw, SAV_HISTORY_BYTES)


def _labor_table(sim: SimState) -> bytes:
    raw = bytearray(64)
    assigned = list(getattr(sim, "labor_assigned", None) or [0] * 7)
    need = list(getattr(sim, "labor_need", None) or [0] * 7)
    for i in range(7):
        struct.pack_into("<i", raw, i * 8, int(assigned[i]) if i < len(assigned) else 0)
        struct.pack_into("<i", raw, i * 8 + 4, int(need[i]) if i < len(need) else 0)
    return bytes(raw)


def _is_lastyear(path: Path | None) -> bool:
    return path is not None and path.name.lower() == "lastyear.sav"


def sav_dir(game: Path) -> Path:
    """Install `sav/` folder. Caller creates it on write."""
    return Path(game) / SAV_SUBDIR


def _dos83_stem(raw: str) -> str:
    """Uppercase A–Z / 0–9, max 8 chars — original C2 file-dialog names."""
    out: list[str] = []
    for ch in raw.upper():
        if ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
            out.append(ch)
        if len(out) >= 8:
            break
    return "".join(out)


def slot_name(city: CityMap | None = None, sim: SimState | None = None) -> str:
    """8.3 .SAV name. Reuse a loaded filename; else CITY.SAV."""
    for raw in (
        getattr(city, "source", None),
        getattr(sim, "source", None),
    ):
        if not raw:
            continue
        text = str(raw).strip()
        if not text.lower().endswith(".sav"):
            continue
        stem = _dos83_stem(Path(text).stem)
        if stem:
            return f"{stem}.SAV"
    return DEFAULT_SAV_NAME


def dest_path(game: Path, city: CityMap | None = None, sim: SimState | None = None) -> Path:
    """`{game}/sav/{slot}.SAV`. Creates `sav/` if missing."""
    folder = sav_dir(game)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / slot_name(city, sim)


def owned_payloads(
    city: CityMap | bytearray | bytes,
    walkers: Sequence[Walker] | bytearray | bytes,
    sim: SimState,
    *,
    lastyear: bool = False,
) -> dict[int, bytes]:
    """Live bytes for every SavChunk the host keeps."""
    tiles = _tiles(city)
    pop = int(getattr(sim, "population", 0) or 0)
    try:
        from app.city_paint import recount_population

        pop = recount_population(bytearray(tiles))
    except Exception:
        pass
    flags = _LASTYEAR_FLAGS if lastyear else _NAMED_FLAGS
    city_only = 1 if getattr(sim, "city_only", 0) else 0
    tribute = 0 if city_only else int(getattr(sim, "tribute", 0) or 0)
    return {
        0: _u8(flags[0]),
        1: _u8(flags[1]),
        2: _u8(flags[2]),
        3: _u8(flags[3]),
        WALKER_CHUNK: pack_pool(walkers),
        CITY_CHUNK: tiles,
        CHUNK_SKILL: _u8(getattr(sim, "skill", 0)),
        WRAP4_CHUNK: _i32(getattr(sim, "wrap4", 0)),
        ROW_CHUNK: _i32(getattr(sim, "row", 0)),
        PHASE_CHUNK: _i32(getattr(sim, "phase", 1)),
        YEAR_CHUNK: _i32(getattr(sim, "year_raw", -300)),
        MONTH_CHUNK: _i32(getattr(sim, "month", 0)),
        WEEK_GATE_CHUNK: _i32(getattr(sim, "week_gate", 0)),
        CHUNK_TREASURY: _i32(getattr(sim, "treasury", 0)),
        TAX_RATE_CHUNK: _i32(getattr(sim, "tax_rate", 5)),
        IND_TAX_CHUNK: _i32(getattr(sim, "industrial_tax", 5)),
        31: _i32(getattr(sim, "employed_pct", 0)),
        POP_CHUNK: _i32(pop),
        33: _i32(getattr(sim, "surplus_last", 0)),
        34: _i32(getattr(sim, "pop_tax_last", 0)),
        35: _i32(getattr(sim, "ind_tax_last", 0)),
        36: _i32(getattr(sim, "construct_last", 0)),
        37: _i32(getattr(sim, "operating_last", 0)),
        46: _i32(getattr(sim, "rating_avg", 0)),
        LABOR_READY_CHUNK: _i32(getattr(sim, "plebs_ready", 0)),
        WELFARE_CHUNK: _i32(getattr(sim, "welfare", 0)),
        LABOR_EST_CHUNK: _i32(getattr(sim, "plebs_estimate", 0)),
        LABOR_TABLE_CHUNK: _labor_table(sim),
        FACTORY_LABOR_CHUNK: _i32(getattr(sim, "factory_labor", 0)),
        157: _i32(tribute),
        CHUNK_PID: _i32(getattr(sim, "pid", 0)),
        PROVINCE_LINKS_CHUNK: _i32(getattr(sim, "province_links", 0)),
        286: _i32(getattr(sim, "rating_empire", 0)),
        287: _i32(getattr(sim, "rating_peace", 0)),
        288: _i32(getattr(sim, "rating_prosperity", 0)),
        289: _i32(getattr(sim, "rating_culture", 0)),
        RANK_CHUNK: _i32(0),
        YEAR_SEED_CHUNK: _i32(getattr(sim, "year_raw", -300)),
        HISTORY_COUNT_CHUNK: _i32(0),
        GOODS_CHUNK: bytes(getattr(sim, "goods", b"") or bytes(768)),
        RATINGS_SEED_CHUNK: _i32(getattr(sim, "ratings_seed", 0)),
        WRAP3_CHUNK: _i32(getattr(sim, "wrap3", 0)),
        CHUNK_CITY_ONLY: _u8(city_only),
        LABOR_INDEX_CHUNK: _i32(getattr(sim, "labor_index", 1)),
    }


def build_sav_bytes(
    city: CityMap | bytearray | bytes,
    walkers: Sequence[Walker] | bytearray | bytes,
    sim: SimState,
    *,
    game: Path | None = None,
    sizes: Sequence[int] | None = None,
    path: Path | None = None,
) -> bytes:
    """500 sequential chunks + 4000 B history, same as sav_write 0x70174."""
    table_sizes = list(sizes) if sizes is not None else chunk_sizes(game)
    if len(table_sizes) != N_SAV_CHUNKS:
        raise ValueError(f"{len(table_sizes)} chunk sizes, want {N_SAV_CHUNKS}")
    if sum(table_sizes) != SAV_TABLE_BYTES:
        raise ValueError(
            f"chunk sizes sum {sum(table_sizes)}, want {SAV_TABLE_BYTES}"
        )
    owned = owned_payloads(city, walkers, sim, lastyear=_is_lastyear(path))
    parts: list[bytes] = []
    for index, size in enumerate(table_sizes):
        if index in owned:
            parts.append(_fit(owned[index], size))
        else:
            parts.append(bytes(size))
    blob = b"".join(parts) + _history(sim)
    if len(blob) != SAV_SIZE:
        raise ValueError(f"built SAV is {len(blob)} bytes, want {SAV_SIZE}")
    return blob


def write_sav(
    path: Path,
    city: CityMap | bytearray | bytes,
    walkers: Sequence[Walker] | bytearray | bytes,
    sim: SimState,
    *,
    game: Path | None = None,
    sizes: Sequence[int] | None = None,
) -> Path:
    """Write a 225745-byte .SAV. Caller chooses the path (install, not git)."""
    dest = Path(path)
    dest.write_bytes(
        build_sav_bytes(city, walkers, sim, game=game, sizes=sizes, path=dest)
    )
    return dest


def selftest() -> list[str]:
    """Round-trip City Only chunks through a tempfile. No retail copy."""
    import tempfile

    from app.new_game import ExeRng, start_city_assignment

    lines: list[str] = []
    if slot_name() != DEFAULT_SAV_NAME:
        lines.append(f"FAIL  default slot {slot_name()!r}")
    else:
        lines.append("ok    default slot CITY.SAV")
    named = CityMap(source="FELIPE01.SAV")
    if slot_name(named) != "FELIPE01.SAV":
        lines.append(f"FAIL  named slot {slot_name(named)!r}")
    else:
        lines.append("ok    named slot FELIPE01.SAV")
    gen = CityMap(source="city_map_generate")
    if slot_name(gen) != DEFAULT_SAV_NAME:
        lines.append(f"FAIL  generate slot {slot_name(gen)!r}")
    else:
        lines.append("ok    generate slot CITY.SAV")
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp)
        dest = dest_path(fake, gen)
        want = fake / SAV_SUBDIR / DEFAULT_SAV_NAME
        if dest != want or not dest.parent.is_dir():
            lines.append(f"FAIL  dest_path {dest}")
        else:
            lines.append("ok    dest_path {game}/sav/CITY.SAV")
    sizes = chunk_sizes()
    if len(sizes) != N_SAV_CHUNKS or sum(sizes) != SAV_TABLE_BYTES:
        lines.append(f"FAIL  writer sizes {len(sizes)} sum={sum(sizes)}")
        return lines
    lines.append("ok    500 SavChunk sizes sum 221745")

    fresh = start_city_assignment(skill=2, rng=ExeRng.from_seed(1))
    tiles = fresh.city.tiles
    off = 10 * 80 * 20 + 10 * 20
    tiles[off] = 0x82
    tiles[off + 1] = 0x01
    fresh.sim.month = 3
    fresh.sim.year_raw = -300
    fresh.sim.tax_rate = 7
    fresh.sim.industrial_tax = 4
    fresh.sim.treasury = 11900
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "CITYONLY.SAV"
        write_sav(dest, fresh.city, fresh.walkers, fresh.sim, sizes=sizes)
        n = dest.stat().st_size
        if n != SAV_SIZE:
            lines.append(f"FAIL  size {n} want {SAV_SIZE}")
            return lines
        lines.append(f"ok    wrote {n} B (221745 + 4000 history)")
        data = dest.read_bytes()
        chunks = walk_sav_chunks(data, sizes)
        city = load_city_from_sav(dest, sizes)
        walkers = load_walkers_from_sav(dest, sizes)
        sim = load_sim_from_sav(dest, sizes)
        if city.tiles != tiles:
            lines.append("FAIL  chunk 13 city 80x80x20 mismatch")
        else:
            lines.append("ok    chunk 13 city 80x80x20")
        if len(pack_pool(walkers)) != WALKER_BYTES:
            lines.append(f"FAIL  walkers {len(pack_pool(walkers))}")
        elif any(w.occupied for w in walkers):
            lines.append("FAIL  new-game walkers not empty")
        else:
            lines.append("ok    chunk 8 walkers 201x58 (empty pool)")
        if sim.year_raw != -300 or sim.month != 3:
            lines.append(f"FAIL  calendar {sim.year_raw} month={sim.month}")
        else:
            lines.append("ok    chunks 25/26 calendar")
        if sim.tax_rate != 7 or sim.industrial_tax != 4:
            lines.append(f"FAIL  tax {sim.tax_rate}/{sim.industrial_tax}")
        else:
            lines.append("ok    chunks 29/30 tax")
        if sim.plebs_ready != fresh.sim.plebs_ready or sim.welfare != fresh.sim.welfare:
            lines.append(
                f"FAIL  labor 52/54 {sim.plebs_ready}/{sim.welfare} "
                f"want {fresh.sim.plebs_ready}/{fresh.sim.welfare}"
            )
        else:
            lines.append("ok    chunks 52/54 labor")
        if chunks[CHUNK_CITY_ONLY][0] != 1 or sim.city_only != 1:
            lines.append(f"FAIL  chunk 406={chunks[CHUNK_CITY_ONLY][0]} sim={sim.city_only}")
        else:
            lines.append("ok    chunk 406=1 City Only")
        if sim.skill != 2 or sim.pid != 0 or sim.treasury != 11900:
            lines.append(
                f"FAIL  skill={sim.skill} pid={sim.pid} treasury={sim.treasury}"
            )
        else:
            lines.append("ok    skill 16 / pid 223 / treasury 28")
        if city.tiles[off] != 0x82:
            lines.append("FAIL  tent origin not in reloaded map")
        owned_nonzero = 0
        zero_slots = 0
        for i, raw in enumerate(chunks):
            if i in HOST_OWNED_CHUNKS:
                if any(raw):
                    owned_nonzero += 1
            elif any(raw):
                zero_slots += 1
        if zero_slots:
            lines.append(f"FAIL  {zero_slots} unowned chunks not zero")
        else:
            lines.append(
                f"ok    unowned slots zero-padded ({len(HOST_OWNED_CHUNKS)} owned live)"
            )
        if dest.read_bytes()[SAV_TABLE_BYTES:] != bytes(SAV_HISTORY_BYTES):
            lines.append("FAIL  history trailer not 4000 zeros")
        else:
            lines.append("ok    history.dat trailer 4000 zeros (City Only reset)")
    return lines
