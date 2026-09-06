"""Host stand-in for one city sim pulse.

Ghidra (findings/ghidra_sim.md, findings/ghidra_walkers_tick.md):

    view_frame       0x3CF9A   display frame (draw + optional sim)
    sim_tick_due     0x3E4B9   speed / pause gate
    city_sim_phase   0x3F60C   one [0x1026A8] slot — app/city_sim.py
    walkers_tick     0x459D0   app/walker_tick.py
    actors26_tick    0x45A7A   skipped

Original pulse order is **phase then walkers**. Space/T matches that:
one slot (not the full 0xD6 dump) + one walkers_tick. Unpaused City Only
uses sim_tick_due so months advance without mashing M.

**M** is a host shortcut: remaining slots this cycle (evolve, water,
land-value, walker emit, +17 flood) then one calendar_advance.

    from app.sim import on_sim_step, on_month_step, on_clock_step
    n = on_sim_step(city, walkers, sim)
    m = on_month_step(city, walkers, sim)
    c = on_clock_step(city, walkers, sim, pulses=1)
"""

from __future__ import annotations

from collections.abc import MutableSequence
from dataclasses import dataclass

from app.calendar import sim_tick_interval_ms
from app.city_sim import (
    PhaseResult,
    SimState,
    _phase_wrap,
    city_sim_clock_pulse,
    city_sim_phase,
    city_sim_until_wrap,
)
from app.walker_tick import TickResult, sprite_id_for, walkers_tick
from app.walkers import Walker

__all__ = [
    "PulseResult",
    "TickResult",
    "on_clock_step",
    "on_month_step",
    "on_sim_step",
    "sim_pulses_per_due",
    "sim_tick_due",
    "sprite_id_for",
    "walkers_tick",
]


@dataclass
class PulseResult:
    phase: PhaseResult
    walkers: TickResult


def sim_pulses_per_due(catchup: int) -> int:
    """view_frame catch-up: [0xC45A0]==0 → 1 pulse, else 4."""
    return 1 if int(catchup) == 0 else 4


def sim_tick_due(sim: SimState, dt_ms: int) -> int:
    """0x3E4B9 — accumulate dt; 0 if paused or not enough ms.

    Returns how many pulses to run (0, 1, or 4). Host Space/T still ignores
    this gate (manual step).
    """
    if sim.paused:
        return 0
    sim.tick_acc += max(0, int(dt_ms))
    need = sim_tick_interval_ms(sim.speed_scalar)
    if sim.tick_acc < need:
        return 0
    sim.tick_acc -= need
    return sim_pulses_per_due(sim.catchup)


def on_sim_step(
    map,
    walkers: MutableSequence[Walker] | bytearray,
    sim: SimState | None = None,
) -> PulseResult:
    """One host sim pulse. Camera window: **Space** or **T**.

    Order matches view_frame: city_sim_phase 0x3F60C then walkers_tick 0x459D0.
    One Space = one slot, not 0xD7 slots. actors26_tick still skipped.
    """
    tiles = getattr(map, "tiles", None)
    if not isinstance(tiles, bytearray):
        tiles = bytearray()
    if sim is None:
        sim = SimState()
    phase = city_sim_phase(tiles, sim, walkers)
    walked = walkers_tick(tiles, walkers)
    return PulseResult(phase=phase, walkers=walked)


def on_month_step(
    map,
    walkers: MutableSequence[Walker] | bytearray,
    sim: SimState | None = None,
) -> PulseResult:
    """Host **M** — run until phase wrap / one calendar_advance.

    Finishes remaining slots this cycle (including water / +15 / emit /
    +17), then month++ (year++ on December). One walkers_tick after wrap.
    """
    tiles = getattr(map, "tiles", None)
    if not isinstance(tiles, bytearray):
        tiles = bytearray()
    if sim is None:
        sim = SimState()
    month_before, year_before = sim.month, sim.year_raw
    phase = city_sim_until_wrap(tiles, sim, walkers)
    if sim.month == month_before and sim.year_raw == year_before:
        wrapped = _phase_wrap(sim)
        phase = PhaseResult(
            phase=phase.phase,
            name="calendar_advance",
            implemented=False,
            houses_up=phase.houses_up,
            houses_down=phase.houses_down,
            houses_merge=phase.houses_merge,
            walkers_spawned=phase.walkers_spawned,
            month_wrapped=wrapped,
            date_label=sim.date_label,
            note=phase.note,
        )
    walked = walkers_tick(tiles, walkers)
    return PulseResult(phase=phase, walkers=walked)


def on_clock_step(
    map,
    walkers: MutableSequence[Walker] | bytearray,
    sim: SimState | None = None,
    *,
    pulses: int = 1,
) -> PulseResult:
    """Unpaused auto-clock: 1 (play) or 4 (faster) pulses, then walkers.

    Each pulse is one city_sim_phase slot (housing, paint, emit, or flood).
    Stops early if the month wraps so one due does not skip a year.
    """
    tiles = getattr(map, "tiles", None)
    if not isinstance(tiles, bytearray):
        tiles = bytearray()
    if sim is None:
        sim = SimState()
    n = max(1, int(pulses))
    phase = city_sim_clock_pulse(tiles, sim, walkers)
    for _ in range(n - 1):
        if phase.month_wrapped:
            break
        nxt = city_sim_clock_pulse(tiles, sim, walkers)
        phase = PhaseResult(
            phase=nxt.phase,
            name=nxt.name,
            implemented=nxt.implemented,
            houses_up=phase.houses_up + nxt.houses_up,
            houses_down=phase.houses_down + nxt.houses_down,
            houses_merge=phase.houses_merge + nxt.houses_merge,
            walkers_spawned=phase.walkers_spawned + nxt.walkers_spawned,
            month_wrapped=phase.month_wrapped or nxt.month_wrapped,
            date_label=sim.date_label,
            note=nxt.note,
        )
    walked = walkers_tick(tiles, walkers)
    return PulseResult(phase=phase, walkers=walked)
