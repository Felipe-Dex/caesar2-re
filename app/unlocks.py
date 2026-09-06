"""City build unlocks — FAQ §4 / C2MODEL pop_unlocks.

The packed i32 run ``400,800,1200,1800,2400,4800`` is **absent** from
``PS.EXE`` / ``c2_x.bin`` (searched). The same six thresholds are the
C2MODEL gap list and the Caesar II FAQ population table (caesar2.com /
GameFAQs Falanx). Once the peak is reached the building stays available
even if population later drops (FAQ). Skill does not change this table.
City Only Normal starts at pop 0 — Palatine / C.Maximus / etc. start locked.

Worship *evolve* (not the palette buttons) also has pop gates; those are
not construction flags.
"""

from __future__ import annotations

# Flyout key / place tool name → required population.
# Matches C2MODEL pop_unlocks order (same six numbers).
POP_UNLOCK: dict[str, int] = {
    "janiculan": 400,
    "odeum": 800,
    "library": 1200,
    "palatine": 1800,
    "coliseum": 2400,
    "cmaximus": 4800,
}

TOOL_POP_UNLOCK: dict[str, int] = dict(POP_UNLOCK)


def peak_population(sim) -> int:
    if sim is None:
        return 0
    return max(int(getattr(sim, "population", 0)), int(getattr(sim, "pop_peak", 0)))


def note_population(sim, population: int) -> int:
    """Write current pop and raise the sticky peak (FAQ unlock latch)."""
    pop = int(population)
    sim.population = pop
    peak = int(getattr(sim, "pop_peak", 0))
    if pop > peak:
        sim.pop_peak = pop
    return pop


def tool_unlock_need(tool: str | None) -> int:
    if not tool:
        return 0
    return TOOL_POP_UNLOCK.get(tool, 0)


def tool_is_unlocked(tool: str | None, sim) -> bool:
    need = tool_unlock_need(tool)
    if need <= 0:
        return True
    return peak_population(sim) >= need


def unlock_refuse(tool: str | None, sim) -> str | None:
    if tool_is_unlocked(tool, sim):
        return None
    need = tool_unlock_need(tool)
    return f"leftover — pop {need} (FAQ / C2MODEL)"
