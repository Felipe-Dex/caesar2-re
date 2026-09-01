"""Host stand-in for one city sim pulse.

Ghidra (findings/ghidra_sim.md, findings/ghidra_walkers_tick.md):

    view_frame       0x3CF9A   display frame (draw + optional sim)
    sim_tick_due     0x3E4B9   speed / pause gate
    city_sim_phase   0x3F60C   skipped — not this module
    walkers_tick     0x459D0   implemented in app/walker_tick.py
    actors26_tick    0x45A7A   skipped

Camera window: bind **Space** or **T** → on_sim_step(map, walkers),
then re-blit walkers onto a terrain-only cache.

    from app.sim import on_sim_step
    n = on_sim_step(city, walkers)
"""

from __future__ import annotations

from collections.abc import MutableSequence

from app.walker_tick import TickResult, sprite_id_for, walkers_tick
from app.walkers import Walker

# Re-export so existing `from app.sim import sprite_id_for` keep working.
__all__ = ["TickResult", "on_sim_step", "sprite_id_for", "walkers_tick"]


def on_sim_step(map, walkers: MutableSequence[Walker] | bytearray) -> TickResult:
    """One host sim pulse. Camera window: **Space** or **T**.

    Runs walkers_tick 0x459D0 on the 58-byte records and tile[+7]/[+8].
    Does **not** run city_sim_phase / actors26_tick / economy / battle.

    After this returns, re-run overlay_walkers on a **terrain-only** image.
    """
    tiles = getattr(map, "tiles", None)
    if not isinstance(tiles, bytearray):
        tiles = bytearray()
    return walkers_tick(tiles, walkers)
