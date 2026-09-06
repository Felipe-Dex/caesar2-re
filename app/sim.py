"""Host stand-in for one city sim pulse.

Ghidra (findings/ghidra_sim.md, findings/ghidra_walkers_tick.md):

    view_frame       0x3CF9A   display frame (draw + optional sim)
    sim_tick_due     0x3E4B9   speed / pause gate (host Space/T ignores)
    city_sim_phase   0x3F60C   one [0x1026A8] slot — app/city_sim.py
    walkers_tick     0x459D0   app/walker_tick.py
    actors26_tick    0x45A7A   skipped

Original pulse order is **phase then walkers**. Space/T matches that:
one slot (not the full 0xD6 dump) + one walkers_tick.

    from app.sim import on_sim_step
    n = on_sim_step(city, walkers, sim)
"""

from __future__ import annotations

from collections.abc import MutableSequence
from dataclasses import dataclass

from app.city_sim import PhaseResult, SimState, city_sim_phase
from app.walker_tick import TickResult, sprite_id_for, walkers_tick
from app.walkers import Walker

__all__ = [
    "PulseResult",
    "TickResult",
    "on_sim_step",
    "sprite_id_for",
    "walkers_tick",
]


@dataclass
class PulseResult:
    phase: PhaseResult
    walkers: TickResult


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
    phase = city_sim_phase(tiles, sim)
    walked = walkers_tick(tiles, walkers)
    return PulseResult(phase=phase, walkers=walked)
