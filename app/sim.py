"""Host stand-in for one city sim pulse. Not walkers_tick.

Ghidra (findings/ghidra_sim.md, findings/ghidra_walkers_tick.md):

    view_frame       0x3CF9A   display frame (draw + optional sim)
    sim_tick_due     0x3E4B9   speed / pause gate
    city_sim_phase   0x3F60C   one [0x1026A8] slot (evolve / paint / flood)
    walkers_tick     0x459D0   201 × 58: type 1-7 → state 0-12 → roam/path/step
    actors26_tick    0x45A7A   province pool (skipped here)

A **real** walkers_tick (do not invent here): ++sim_tick_mod64 wrap 64,
clamp type7/type3 latches, then per live slot walker_state_fn then
walker_set_sprite then life_phase++ every 64 ticks (cap → state 2/free).
Movement is walker_anim_roam / walker_anim_path → walker_step, which
relinks tile[+7]/[+8]. Type 3 barbarian / type 7 rioter. State 9 seek
and path-fail helpers are still unread — do **not** replace this stub
with guessed AI.

This module only advances walk_frame / sprite_id in the 58-byte records
so the iso map can animate. It does **not** call walker_type_fn,
walker_step, or city_sim_phase.

Camera window: bind **Space** or **T** → on_sim_step(map, walkers),
then re-blit walkers onto a terrain-only cache.

    from app.sim import on_sim_step
    n = on_sim_step(city, walkers)
"""

from __future__ import annotations

import struct
from collections.abc import MutableSequence

from app.walkers import (
    STATE_FREE,
    TYPE_LTLMEN_BASE,
    TYPE_MAX,
    TYPE_MIN,
    WALKER_BYTES,
    WALKER_COUNT,
    WALKER_STRIDE,
    Walker,
    unpack_pool,
)

# Walker record (ghidra_walkers.md). Stub writes +0x1F and +0x34 only.
_OFF_OCCUPIED = 0
_OFF_TYPE = 2
_OFF_FACING = 3
_OFF_STATE = 0x10
_OFF_WALK_FRAME = 0x1F
_OFF_SPRITE_ID = 0x34

WALK_FRAME_MASK = 0x0F  # game walk_frame is 0..15

# Tile +16 fire / disaster timer (ghidra_tile.md §7). Not implemented.
# FUN_00041dd4 0x41DD4: if tile[+3] bit7, --[+16]. Water id<8 at 0 → clear bit7.
# Do not run FUN_000430da 0x430DA (+17 road-access flood) from this stub.
_TILE_OFF_DRAW = 3
_TILE_OFF_FIRE = 16
_TILE_FLAG80 = 0x80


def _sprite_nibble(walk_frame: int) -> int:
    """Same 0/1/2 extra as Walker.ltlmen_index (walk_frame & 3)."""
    frame = walk_frame & 3
    if frame == 0:
        return 0
    if frame == 2:
        return 2
    return 1


def sprite_id_for(type_id: int, facing: int, walk_frame: int) -> int:
    """walker_set_sprite 0x479B8 stand-in: base + facing*3 + nibble."""
    base = TYPE_LTLMEN_BASE.get(type_id, 0)
    return base + (facing % 8) * 3 + _sprite_nibble(walk_frame)


def step_record(raw: bytearray) -> bool:
    """In-place fake anim on one 58-byte record. True if the frame moved."""
    if len(raw) != WALKER_STRIDE:
        raise ValueError(f"walker is {len(raw)} bytes, want {WALKER_STRIDE}")
    if raw[_OFF_OCCUPIED] == 0:
        return False
    typ = raw[_OFF_TYPE]
    if typ < TYPE_MIN or typ > TYPE_MAX:
        return False
    if raw[_OFF_STATE] == STATE_FREE:
        return False
    frame = (raw[_OFF_WALK_FRAME] + 1) & WALK_FRAME_MASK
    raw[_OFF_WALK_FRAME] = frame
    # facing (+3) is left alone so they do not spin; sprite uses current facing.
    struct.pack_into(
        "<h", raw, _OFF_SPRITE_ID, sprite_id_for(typ, raw[_OFF_FACING], frame)
    )
    return True


def step_pool(blob: bytearray) -> int:
    """Advance every live slot in a 201 × 58 bytearray. Returns how many moved."""
    if len(blob) != WALKER_BYTES:
        raise ValueError(f"walker pool is {len(blob)} bytes, want {WALKER_BYTES}")
    n = 0
    for i in range(WALKER_COUNT):
        off = i * WALKER_STRIDE
        rec = blob[off : off + WALKER_STRIDE]
        if step_record(rec):
            blob[off : off + WALKER_STRIDE] = rec
            n += 1
    return n


def step_walkers(
    walkers: MutableSequence[Walker] | bytearray,
) -> int:
    """Advance walk_frame (wrap 0..15) in the 58-byte records.

    list[Walker]: replaces each item in place (ctx.walkers stays the same list).
    bytearray: mutates the 201 × 58 pool in place.

    Returns how many live records were advanced. Not walkers_tick 0x459D0.
    """
    if isinstance(walkers, bytearray):
        if len(walkers) == WALKER_STRIDE:
            return int(step_record(walkers))
        return step_pool(walkers)

    n = 0
    for i, walker in enumerate(walkers):
        raw = bytearray(walker.raw)
        if step_record(raw):
            walkers[i] = Walker.unpack(bytes(raw), slot=walker.slot)
            n += 1
    return n


def on_sim_step(map, walkers) -> int:
    """One host sim pulse. Camera window: **Space** or **T**.

    ``map`` is the CityMap (tiles kept for a later fire-timer pass).
    ``walkers`` is ctx.walkers (list of 201 Walker) or a 11658-byte pool.

    After this returns, re-run overlay_walkers on a **terrain-only** image.
    Do not blit onto a cache that already has people.

    This is **not** walkers_tick (no type/state/step/tile +7/+8).
    Real pulse: findings/ghidra_walkers_tick.md. Optional later:
    decrement tile[+16] while +3 bit7 — see _TILE_OFF_FIRE. No +17 flood.
    """
    _ = map  # reserved: --tile[+16] fire timer (FUN_00041dd4), not +17 flood
    return step_walkers(walkers)
