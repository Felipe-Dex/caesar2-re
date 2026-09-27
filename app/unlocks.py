"""City build unlocks — EXE 0x441C3 / FAQ §4 / C2MODEL pop_unlocks.

Thresholds are immediates in ``0x441C3`` (not a packed i32 run). Palette
availability uses peak ``[0x102A94]`` (SavChunk 409). ``[114]`` New
Structure uses step ``[0x102C3C]`` (SavChunk 411): Colosseum is pop
``>= 2400`` and step ``== 4``, then ``inc`` so a later flicker cannot
re-fire. Skill does not change this table. City Only Normal starts at
pop 0 — Palatine / C.Maximus / etc. start locked.

Worship *evolve* (not the palette buttons) also has pop gates; those are
not construction flags.
"""

from __future__ import annotations

# Flyout key / place tool name → required population.
# EXE 0x44337 / 0x44408 order (same six numbers as C2MODEL).
POP_UNLOCK: dict[str, int] = {
    "janiculan": 400,
    "odeum": 800,
    "library": 1200,
    "palatine": 1800,
    "coliseum": 2400,
    "cmaximus": 4800,
}

UNLOCK_GATES: tuple[int, ...] = (400, 800, 1200, 1800, 2400, 4800)

TOOL_POP_UNLOCK: dict[str, int] = dict(POP_UNLOCK)


def peak_population(sim) -> int:
    if sim is None:
        return 0
    return max(int(getattr(sim, "population", 0)), int(getattr(sim, "pop_peak", 0)))


def note_population(sim, population: int) -> int:
    """Write current pop and raise the sticky peak (0x441C8 / FAQ)."""
    pop = int(population)
    sim.population = pop
    peak = int(getattr(sim, "pop_peak", 0))
    if pop > peak:
        sim.pop_peak = pop
    return pop


def announced_unlock_count(peak: int) -> int:
    """How many [114] steps a city at this peak has already crossed."""
    n = 0
    for gate in UNLOCK_GATES:
        if peak >= gate:
            n += 1
        else:
            break
    return n


def seed_unlock_step(sim, peak: int) -> int:
    """Raise [0x102C3C] so load / dip does not re-fire 58c87 EAX=0x73."""
    n = announced_unlock_count(int(peak))
    step = int(getattr(sim, "unlock_step", 0) or 0)
    if n > step:
        sim.unlock_step = n
    return int(getattr(sim, "unlock_step", 0) or 0)


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
