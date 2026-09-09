"""Host stand-in for walkers_tick 0x459D0.

One pulse: ++mod64 wrap 64, clamp type-7/type-3 latches, then each live
SavChunk-8 slot (201 × 58) runs walker_type_fn → walker_state_fn →
walker_set_sprite → life_phase. Movement is walker_anim_roam 0x47EFA /
walker_anim_path 0x48084 → walker_step 0x488DC (tile[+7]/[+8]).

city_sim_phase 0x3F60C lives in app/city_sim.py (called before this).
Type 7 rioter spawn is unrest_spawn_rows (41DD4, next_state 0x0B).
Not implemented here: actors26_tick 0x45A7A, path-fail helpers.
State 8→9 fire seek is 0x4A397 / 0x4A57F / 0x4A716 / 0x4A76D.
See findings/app_tick.md.
"""

from __future__ import annotations

import struct
from collections.abc import MutableSequence
from dataclasses import dataclass

from app.city_map import FLAG_PAD, FLAG_RIVER, MAP_H, MAP_W, TILE_BYTES, is_aqueduct_id
from app.walkers import (
    TYPE_LTLMEN_BASE,
    TYPE_MAX,
    TYPE_MIN,
    WALKER_BYTES,
    WALKER_COUNT,
    WALKER_STRIDE,
    Walker,
    drop_walker_slide,
    note_walker_slide,
)

# Record bytes — findings/ghidra_walkers.md
_OFF_OCCUPIED = 0
_OFF_TYPE = 2
_OFF_FACING = 3
_OFF_X = 4
_OFF_Y = 5
_OFF_TILE = 6
_OFF_DEST_X = 0x0C
_OFF_DEST_Y = 0x0D
_OFF_NEXT_STATE = 0x0E
_OFF_WAIT = 0x0F
_OFF_STATE = 0x10
_OFF_BUMP = 0x11
_OFF_UNK_1E = 0x1E
_OFF_WALK_FRAME = 0x1F
_OFF_ANIM_TIMER = 0x20
_OFF_ANIM_FLAGS = 0x21
_OFF_WANT_MOVE = 0x22
_OFF_ON_ROAD = 0x23
_OFF_LIFE = 0x24
_OFF_SCORE_A = 0x26
_OFF_SCORE_B = 0x27
_OFF_HOME = 0x28
_OFF_HOME_WALKER = 0x2C
_OFF_CHASE = 0x2D
_OFF_RNG = 0x2E
_OFF_RNG_LOCK = 0x30
_OFF_LINGER = 0x33
_OFF_NAME = 0x32
_OFF_SPRITE_ID = 0x34

_ANIM_DONE = 0x01
_ANIM_FAIL = 0x02

_TILE_FLAGS = 1
_TILE_DRAW = 3
_TILE_SLOT0 = 7
_TILE_SLOT1 = 8
_TILE_QUEUE = 18

# walker_step 0x488DC — facing 0–7 = N NE E SE S SW W NW
_FACING_DELTA: tuple[tuple[int, int, int], ...] = (
    (0, -1, -0x640),
    (1, -1, -0x62C),
    (1, 0, 0x14),
    (1, 1, 0x654),
    (0, 1, 0x640),
    (-1, 1, 0x62C),
    (-1, 0, -0x14),
    (-1, -1, -0x654),
)

# walker_type_fn life caps (0x45AFE..0x45D0A)
_LIFE_CAP = {1: 18, 2: 30, 3: 72, 4: 35, 5: 20, 6: 30, 7: 20}

# 0x9673E[type] when +0x23==0 (road); 0x96735[type] when +0x23!=0 (pad)
_SPEED_ROAD = 2
_SPEED_PAD = 1

_MAP_MAX = MAP_W - 1  # 79; diagonal edge uses 78 ('N')

# Walkable pavement is per walker type (EXE). dest_ok is FLAG_PAD-only
# for city roads; the host also stamps 0x20 on aqueduct T/cross
# (0xD5/0xD6) and leftover grass, which put walkers on the pipe.
# Shared: city roads 0x52–0x5C, bridges 0x4E–0x51, plaza 0x7C–0x7E
# (plaza stays walkable even if +1 lost 0x20).
# Clerks (type 1) also use forum interiors 0xAE–0xB9 (no FLAG_PAD)
# so they can *cross* the courtyard to reach a road. Spawn / seat /
# pick_pad prefer 0x52–0x5C (and plaza) — they must not patrol 0xAE–0xB9.
# Types 2–7 (trader / soldier / vigile / worker / …) stay off 0xAE–0xB9.
ID_ROAD_LO = 0x52
ID_ROAD_HI = 0x5C
ID_BRIDGE_LO = 0x4E
ID_BRIDGE_HI = 0x51
ID_PLAZA_LO = 0x7C
ID_PLAZA_HI = 0x7E
ID_FORUM_LO = 0xAE
ID_FORUM_HI = 0xB9
TYPE_CLERK = 1
TYPE_ENEMY = 3
TYPE_RIOTER = 7

# C2MODEL [75:91] / EXE 0x96ECB — skill*4. Skill 4 reads past 16 ints; use Hard.
# (min years [0x102ac0], rng window, month wait [0x102a78], spawn count)
INVASION_BY_SKILL: tuple[tuple[int, int, int, int], ...] = (
    (10, 20, 60, 1),
    (10, 20, 60, 1),
    (8, 20, 48, 1),
    (6, 25, 36, 3),
)
# 1×1 housing only — EXE 0x41DD4 cmp 0x82…0x9B (villas 0x9C–0xA1 skip).
ID_RIOTER_HOUSE_LO = 0x82
ID_RIOTER_HOUSE_HI = 0x9B
# After this many step-dones still on 0xAE–0xB9, force dest toward road.
_CLERK_FORUM_LINGER = 2
# 0x96c5b — 64 signed ticks. 9 = use 0x96b53[tile_id] instead.
_UNREST_TICK: tuple[int, ...] = (
    9, 1, 0, 9, 0, -1, 0, 2, 0, 9, 0, 0, 9, 0, 0, 9,
    0, 0, 1, 0, 1, 0, 9, -1, 0, 9, 0, 9, 3, 0, 0, 9,
    0, 1, 9, 0, 0, 9, -1, 1, 0, -1, 0, 0, 1, 0, 9, 1,
    0, 9, 0, 2, 0, 9, 0, 9, 9, -1, 1, 0, 9, 1, -2, 0,
)
# 0x96b53[id] for housing 0x82–0x9B (tents raise unrest; better houses damp).
_UNREST_HOUSE: tuple[int, ...] = (
    3, 3, 3, 3, 3, 2, 2, 2, 2, 2, 0, 0, -1, -1, -2, -2,
    -3, -3, -3, -3, -6, -6, -6, -6, -8, -8,
)


def _is_forum_floor(tid: int) -> bool:
    return ID_FORUM_LO <= tid <= ID_FORUM_HI


def _is_city_pavement(tid: int) -> bool:
    return (
        ID_ROAD_LO <= tid <= ID_ROAD_HI
        or ID_BRIDGE_LO <= tid <= ID_BRIDGE_HI
        or ID_PLAZA_LO <= tid <= ID_PLAZA_HI
    )


@dataclass
class WalkerClock:
    """Persists across Space/T pulses (sim_tick_mod64 0x117B1C)."""

    mod64: int = 0
    latch7: int = 0  # [0x10266C]
    latch3: int = 0  # [0x102674]
    rng: int = 1
    # SavChunks 20/21 at [0x10262C]/[0x102628] — land-value peak (0x40695)
    rally_ok: bool = False
    rally_x: int = 0
    rally_y: int = 0
    edge_clock: int = 0  # [0x117bac] — 0x537ed mix


@dataclass(frozen=True)
class TickResult:
    live: int
    stepped: int
    animated: int
    freed: int


_CLOCK = WalkerClock()


def reset_clock() -> None:
    """Test helper — does not exist in the EXE."""
    global _CLOCK
    _CLOCK = WalkerClock()


def sprite_id_for(type_id: int, facing: int, walk_frame: int, *, state: int = 0) -> int:
    """walker_set_sprite 0x479B8 (camera 0). Type 7 state 12 uses base 0."""
    if type_id == 7 and state == 12:
        base = 0
    else:
        base = TYPE_LTLMEN_BASE.get(type_id, 0)
    frame = walk_frame & 3
    extra = 0 if frame == 0 else (2 if frame == 2 else 1)
    return base + (facing % 8) * 3 + extra


def _i8(rec: bytearray, off: int) -> int:
    v = rec[off]
    return v - 256 if v > 127 else v


def _set_i8(rec: bytearray, off: int, value: int) -> None:
    rec[off] = value & 0xFF


def _tile_off(x: int, y: int) -> int:
    return y * 0x640 + x * 0x14


def _in_map(x: int, y: int) -> bool:
    return 0 <= x < MAP_W and 0 <= y < MAP_H


def _tile_at(tiles: bytearray, x: int, y: int) -> int:
    return y * (MAP_W * TILE_BYTES) + x * TILE_BYTES


def is_walker_road(tiles: bytearray, off: int, type_id: int | None = None) -> bool:
    """Walkable pavement for this walker type.

    All types: city road 0x52–0x5C, bridge 0x4E–0x51, plaza 0x7C–0x7E.
    Type 1 only: forum interiors 0xAE–0xB9 (clerk platform, no FLAG_PAD).
    Aqueduct is an elevated pipe except the road-under combo (``+3&0x80``,
    LUT ``0x94E37``). Grass T/cross may carry FLAG_PAD and stay blocked.
    ``type_id is None`` is city pavement only (no forum) so a missed type
    cannot reopen the courtyard to traders.
    """
    if off < 0 or off + TILE_BYTES > len(tiles):
        return False
    tid = tiles[off]
    flags = tiles[off + _TILE_FLAGS]
    if is_aqueduct_id(tid):
        # Grass T/cross may carry FLAG_PAD; only +3&0x80 is road-under-pipe.
        return bool(flags & FLAG_PAD) and bool(tiles[off + _TILE_DRAW] & 0x80)
    if ID_FORUM_LO <= tid <= ID_FORUM_HI:
        return type_id == TYPE_CLERK
    if ID_PLAZA_LO <= tid <= ID_PLAZA_HI:
        return True
    if not (flags & FLAG_PAD):
        return False
    if ID_ROAD_LO <= tid <= ID_ROAD_HI:
        return True
    if ID_BRIDGE_LO <= tid <= ID_BRIDGE_HI:
        return True
    return bool(flags & FLAG_RIVER)


def _path_log(msg: str) -> None:
    from app.sim_log import write

    write(msg)


def _u16(rec: bytearray, off: int) -> int:
    return rec[off] | (rec[off + 1] << 8)


def _set_u16(rec: bytearray, off: int, value: int) -> None:
    rec[off] = value & 0xFF
    rec[off + 1] = (value >> 8) & 0xFF


def _rec(pool: bytearray, slot: int) -> bytearray:
    off = slot * WALKER_STRIDE
    return pool[off : off + WALKER_STRIDE]


def _put(pool: bytearray, slot: int, rec: bytearray) -> None:
    off = slot * WALKER_STRIDE
    pool[off : off + WALKER_STRIDE] = rec


def facing_from_delta(x: int, y: int, dest_x: int, dest_y: int, facing: int = 0) -> int:
    """facing_from_delta 0x2B4DD. Same tile → facing+8 (arrived)."""
    if dest_x < x:
        if dest_y < y:
            return 7
        if dest_y == y:
            return 6
        return 5
    if dest_x == x:
        if dest_y < y:
            return 0
        if dest_y == y:
            return facing + 8
        return 4
    if dest_y < y:
        return 1
    if dest_y == y:
        return 2
    return 3


def walker_set_dest(rec: bytearray, facing: int) -> None:
    """walker_set_dest 0x48E59 — dest is one tile along facing."""
    if facing < 0 or facing > 7:
        return
    rec[_OFF_FACING] = facing
    dx, dy, _doff = _FACING_DELTA[facing]
    _set_i8(rec, _OFF_DEST_X, _i8(rec, _OFF_X) + dx)
    _set_i8(rec, _OFF_DEST_Y, _i8(rec, _OFF_Y) + dy)


def tile_or_radius(
    tiles: bytearray,
    x: int,
    y: int,
    radius: int,
    lane: int,
    bits: int,
    extra: int = 0,
) -> None:
    """tile_or_radius 0x6CD7E: clipped square of side 2*r+1 (+ EAX extra)."""
    if not tiles:
        return
    span = radius + max(0, extra)
    for ny in range(max(0, y - radius), min(MAP_H, y + span + 1)):
        for nx in range(max(0, x - radius), min(MAP_W, x + span + 1)):
            tiles[_tile_at(tiles, nx, ny) + lane] |= bits


def walker_dest_ok(
    tiles: bytearray, dest_off: int, type_id: int | None = None
) -> int:
    """walker_dest_ok 0x48606 (param_2 != 1 walk path). 999 / 1 pad / 2 empty / 0."""
    if dest_off < 0 or dest_off + TILE_BYTES > len(tiles):
        return 0
    slot0 = tiles[dest_off + _TILE_SLOT0]
    slot1 = tiles[dest_off + _TILE_SLOT1]
    flags = tiles[dest_off + _TILE_FLAGS]
    if slot0 and slot1:
        return 999
    if is_walker_road(tiles, dest_off, type_id):
        return 1
    if flags == 0:
        return 2
    return 0


def walker_can_step(tiles: bytearray, rec: bytearray, facing: int) -> int:
    """walker_can_step 0x48470 — bounds then dest_ok."""
    if facing < 0 or facing > 7:
        return 0
    x = _i8(rec, _OFF_X)
    y = _i8(rec, _OFF_Y)
    # Edge tests match the switch at 0x48470 ('N' = 78).
    if facing in (1, 2, 3) and x > _MAP_MAX - 1:
        return 0
    if facing in (5, 6, 7) and x < 1:
        return 0
    if facing in (0, 1, 7) and y < 1:
        return 0
    if facing in (3, 4, 5) and y > _MAP_MAX - 1:
        return 0
    if facing == 2 and x > _MAP_MAX - 1:
        return 0
    dx, dy, _doff = _FACING_DELTA[facing]
    nx, ny = x + dx, y + dy
    if not _in_map(nx, ny):
        return 0
    return walker_dest_ok(tiles, _tile_off(nx, ny), rec[_OFF_TYPE])


def _nearest_city_pavement(
    tiles: bytearray, x: int, y: int, *, radius: int = 12
) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    best_d = 10**9
    for ny in range(max(0, y - radius), min(MAP_H, y + radius + 1)):
        for nx in range(max(0, x - radius), min(MAP_W, x + radius + 1)):
            off = _tile_off(nx, ny)
            if off >= len(tiles):
                continue
            if not _is_city_pavement(tiles[off]):
                continue
            d = abs(nx - x) + abs(ny - y)
            if d < best_d:
                best_d = d
                best = (nx, ny)
    return best


def _clerk_exit_facing(
    tiles: bytearray, x: int, y: int, facing: int
) -> int | None:
    """Cardinal step that shrinks distance to the nearest road/plaza."""
    target = _nearest_city_pavement(tiles, x, y)
    if target is None:
        return None
    tx, ty = target
    opposite = (facing + 4) & 7
    best_f: int | None = None
    best_d = 10**9
    best_rev = True
    for f, (dx, dy) in ((0, (0, -1)), (2, (1, 0)), (4, (0, 1)), (6, (-1, 0))):
        nx, ny = x + dx, y + dy
        if not _in_map(nx, ny):
            continue
        off = _tile_off(nx, ny)
        if not is_walker_road(tiles, off, TYPE_CLERK):
            continue
        d = abs(nx - tx) + abs(ny - ty)
        rev = f == opposite
        if d < best_d or (d == best_d and best_rev and not rev):
            best_d = d
            best_f = f
            best_rev = rev
    return best_f


def walker_pick_pad_facing(
    tiles: bytearray,
    x: int,
    y: int,
    facing: int,
    rng: int,
    type_id: int | None = None,
) -> int:
    """walker_pick_pad_facing 0x48C9F — cardinal pads; 8 = stuck.

    Type 1: road/plaza/bridge wins over courtyard 0xAE–0xB9 when both
    exist. Forum pads stay legal so a clerk already inside can walk out.
    """
    opposite = (facing + 4) & 7
    pads: dict[int, tuple[int, int]] = {}
    city: dict[int, tuple[int, int]] = {}
    forum: dict[int, tuple[int, int]] = {}
    for f, (dx, dy) in ((0, (0, -1)), (2, (1, 0)), (4, (0, 1)), (6, (-1, 0))):
        nx, ny = x + dx, y + dy
        if not _in_map(nx, ny):
            continue
        off = _tile_off(nx, ny)
        if off + TILE_BYTES > len(tiles):
            continue
        if not is_walker_road(tiles, off, type_id):
            continue
        slots = (tiles[off + _TILE_SLOT0], tiles[off + _TILE_SLOT1])
        pads[f] = slots
        if _is_forum_floor(tiles[off]):
            forum[f] = slots
        else:
            city[f] = slots
    if type_id == TYPE_CLERK and city:
        pads = city
    elif type_id == TYPE_CLERK and forum:
        exit_f = _clerk_exit_facing(tiles, x, y, facing)
        if exit_f is not None:
            return exit_f
    if not pads:
        return 8
    if len(pads) == 1:
        return next(iter(pads))
    empty = [f for f, (a, b) in pads.items() if a == 0 and b == 0]
    start = rng & 6

    def _cycle() -> list[int]:
        out = []
        f = start
        for _ in range(4):
            out.append(f)
            f = 0 if f + 2 > 6 else f + 2
        return out

    if empty:
        for f in _cycle():
            if f in empty and f != opposite:
                return f
    for f in _cycle():
        if f in pads and f != opposite:
            return f
    return 8


def walker_unlink(tiles: bytearray, rec: bytearray, slot: int) -> None:
    off = struct.unpack_from("<i", rec, _OFF_TILE)[0]
    if off < 0 or off + TILE_BYTES > len(tiles):
        return
    if tiles[off + _TILE_SLOT0] == slot:
        tiles[off + _TILE_SLOT0] = 0
    elif tiles[off + _TILE_SLOT1] == slot:
        tiles[off + _TILE_SLOT1] = 0


def walker_free(pool: bytearray, tiles: bytearray, slot: int) -> None:
    """walker_free 0x2AECB then walker_zero_record."""
    rec = _rec(pool, slot)
    walker_unlink(tiles, rec, slot)
    drop_walker_slide(slot)
    _put(pool, slot, bytearray(WALKER_STRIDE))


# walker_spawn_retry LUTs 0x99BE4 / 0x99C04 / 0x99C44 / 0x99CA4
_RETRY_OFFSETS: dict[int, tuple[tuple[int, int], ...]] = {
    1: ((0, -1), (1, 0), (0, 1), (-1, 0)),
    4: (
        (0, -1), (1, -1), (2, 0), (2, 1),
        (1, 2), (0, 2), (-1, 1), (-1, 0),
    ),
    9: (
        (0, -1), (1, -1), (2, -1), (3, 0),
        (3, 1), (3, 2), (2, 3), (1, 3),
        (0, 3), (-1, 2), (-1, 1), (-1, 0),
    ),
    0x10: (
        (0, -1), (1, -1), (2, -1), (3, -1),
        (4, 0), (4, 1), (4, 2), (4, 3),
        (3, 4), (2, 4), (1, 4), (0, 4),
        (-1, 3), (-1, 2), (-1, 1), (-1, 0),
    ),
}

_LAST_SPAWN_SLOT = 0
LAST_EMIT_NOTE = ""


def walker_spawn(
    pool: bytearray,
    tiles: bytearray,
    type_id: int,
    x: int,
    y: int,
    *,
    pad: int = 0,
    rng: int = 1,
) -> int:
    """walker_spawn 0x2A7EF. Returns slot 1…200 or 0. Never fills slot 0."""
    global _LAST_SPAWN_SLOT
    if not _in_map(x, y):
        return 0
    off = _tile_off(x, y)
    if off + TILE_BYTES > len(tiles):
        return 0
    if tiles[off + _TILE_SLOT0] and tiles[off + _TILE_SLOT1]:
        return 0
    flags = tiles[off + _TILE_FLAGS]
    if flags & 0x8B:
        return 0
    if pad:
        # Courtyard 0xAE–0xB9 is walkable for type 1 (exit path) but is
        # never a spawn dest — clerks sit on the class-4 road rim.
        if _is_forum_floor(tiles[off]):
            return 0
        if not is_walker_road(tiles, off, type_id):
            if is_aqueduct_id(tiles[off]):
                _path_log(f"walker spawn skip aqueduct  xy={x},{y}  id={tiles[off]:#x}")
            elif flags & FLAG_PAD:
                _path_log(
                    f"walker spawn skip non-road pad  xy={x},{y}  "
                    f"id={tiles[off]:#x}  flags={flags:#x}"
                )
            return 0
    elif flags & 0x54:
        return 0
    for slot in range(1, WALKER_COUNT):
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED]:
            continue
        rec = bytearray(WALKER_STRIDE)
        rec[_OFF_OCCUPIED] = 1
        rec[_OFF_TYPE] = type_id & 0xFF
        rec[_OFF_FACING] = 1
        _set_i8(rec, _OFF_X, x)
        _set_i8(rec, _OFF_Y, y)
        _set_i8(rec, _OFF_DEST_X, x)
        _set_i8(rec, _OFF_DEST_Y, y)
        struct.pack_into("<i", rec, _OFF_TILE, off)
        rec[0xA] = (x << 4) & 0xFF
        rec[0xB] = (y << 4) & 0xFF
        rec[_OFF_UNK_1E] = 5
        _set_u16(rec, _OFF_RNG, rng & 0x7FFF)
        rec[_OFF_ON_ROAD] = 1 if pad else 0
        rec[_OFF_NAME] = (rng + slot) & (0x0F if type_id == 3 else 0x1F)
        drop_walker_slide(slot)
        if tiles[off + _TILE_SLOT0] == 0:
            tiles[off + _TILE_SLOT0] = slot
        else:
            tiles[off + _TILE_SLOT1] = slot
        tiles[off + 3] |= 1
        _put(pool, slot, rec)
        _LAST_SPAWN_SLOT = slot
        return slot
    return 0


def walker_spawn_retry(
    pool: bytearray,
    tiles: bytearray,
    type_id: int,
    x: int,
    y: int,
    *,
    pad: int = 0x20,
    retry_class: int = 1,
    start: int = 0,
    rng: int = 1,
) -> int:
    """walker_spawn_retry 0x42236. Returns 1-based attempt index or 0."""
    offsets = _RETRY_OFFSETS.get(retry_class)
    if offsets is None:
        return 1 if walker_spawn(pool, tiles, type_id, x, y, pad=pad, rng=rng) else 0
    attempts = len(offsets)
    idx = start % attempts if start else 0
    for n in range(attempts):
        dx, dy = offsets[idx]
        if walker_spawn(pool, tiles, type_id, x + dx, y + dy, pad=pad, rng=rng):
            return n + 1
        idx = 0 if idx + 1 >= attempts else idx + 1
    return 0


def invasion_row(skill: int) -> tuple[int, int, int, int]:
    """C2MODEL [75:91] row. Skill 4 has no 5th dword-quad — Hard."""
    if skill < 0:
        skill = 0
    if skill > 3:
        skill = 3
    return INVASION_BY_SKILL[skill]


def edge_pick_type3(side: int, rng127: int, clock: WalkerClock) -> tuple[int, int]:
    """0x537ed — map-edge (x,y). EAX=side 0–7, EDX=80, EBX=63."""
    side &= 7
    size = MAP_W
    mask = 0x3F
    clock.edge_clock = (clock.edge_clock + 1) & 0xFFFFFFFF
    mix = (rng127 + clock.edge_clock) & mask
    half_gap = (size - mask) >> 1
    if half_gap < 0:
        half_gap = 0
    along = mask - (mask >> 2)
    if along < 0:
        along = 0
    ebx = half_gap + mix
    ecx = along + (mix >> 1)
    wrapped = 0
    if ebx >= size:
        ebx >>= 1
    if ecx >= size:
        ecx -= size
        wrapped = 1
    last = size - 1
    edx = last - ecx
    if side == 0:
        return ebx, 0
    if side == 1:
        return (last, ecx) if wrapped else (ecx, 0)
    if side == 2:
        return last, ebx
    if side == 3:
        return (edx, last) if wrapped else (last, ecx)
    if side == 4:
        return ebx, last
    if side == 5:
        return (0, edx) if wrapped else (edx, last)
    if side == 6:
        return 0, ebx
    return (ecx, 0) if wrapped else (0, edx)


def rally_from_plus15(tiles: bytearray) -> tuple[int, int]:
    """0x40695 tail: max signed tile[+15] → [0x10262C]/[0x102628]."""
    best = 0
    rx, ry = 0, 0
    found = False
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _tile_off(x, y)
            if off + 15 >= len(tiles):
                continue
            val = tiles[off + 15]
            signed = val - 256 if val >= 128 else val
            if not found or signed > best:
                best = signed
                rx, ry = x, y
                found = True
    if not found or best <= 0:
        return 0, 0
    return rx, ry


def walker_spawn_type3_count(
    pool: bytearray,
    tiles: bytearray,
    count: int,
    side: int,
    *,
    clock: WalkerClock | None = None,
    rng: int = 1,
) -> int:
    """walker_spawn_type3_count 0x536E2. Pad 0, state 1 → 5, dest = rally."""
    clk = clock if clock is not None else _CLOCK
    rx, ry = rally_from_plus15(tiles)
    clk.rally_ok = True
    clk.rally_x = rx & 0xFF
    clk.rally_y = ry & 0xFF
    spawned = 0
    rng127 = rng & 0x7F
    for _ in range(max(0, count)):
        x, y = edge_pick_type3(side, rng127, clk)
        x = max(0, min(MAP_W - 1, x))
        y = max(0, min(MAP_H - 1, y))
        off = _tile_off(x, y)
        if off + 1 < len(tiles) and (tiles[off + 1] & 0xE7):
            # EXE 0x68c01 dirties/smashes this cell; host only tries spawn.
            pass
        slot = walker_spawn(pool, tiles, TYPE_ENEMY, x, y, pad=0, rng=rng)
        if not slot:
            break
        walker_finish_spawn(pool, slot, next_state=5)
        rec = _rec(pool, slot)
        rec[_OFF_DEST_X] = clk.rally_x & 0xFF
        rec[_OFF_DEST_Y] = clk.rally_y & 0xFF
        rec[_OFF_LINGER] = 3
        _put(pool, slot, rec)
        spawned += 1
    return spawned


def city_only_try_invasion(
    state,
    tiles: bytearray,
    walkers: MutableSequence[Walker] | bytearray | None,
    *,
    years_played: int,
    clock: WalkerClock | None = None,
) -> int:
    """FUN_00052828. City Only (406≠0) only. Career returns 0.

    Monthly from economy_recompute. Not Stern Warning / Emperor / [90–95].
    """
    if not getattr(state, "city_only", 0):
        return 0
    clk = clock if clock is not None else _CLOCK
    min_years, window, wait, count = invasion_row(int(getattr(state, "skill", 2)))
    if min_years > years_played:
        return 0
    months = int(getattr(state, "invade_months", 0)) + 1
    state.invade_months = months
    if wait >= months:
        return 0
    clk.rng = (clk.rng + 1) & 0x7FFF
    rng127 = clk.rng & 0x7F
    forced = getattr(state, "invade_rng", None)
    if forced is not None:
        rng127 = int(forced) & 0x7F
    if rng127 < 0x14:
        return 0
    if window + 0x14 <= rng127:
        return 0
    state.invade_months = 0
    side = rng127 & 7
    stamp = int(getattr(state, "stamp_clock", 0)) & 0x3F
    count &= stamp + (rng127 & 7)
    if count <= 0:
        return 0
    pool = _pool_from(walkers if walkers is not None else bytearray(WALKER_BYTES))
    n = walker_spawn_type3_count(
        pool, tiles, count, side, clock=clk, rng=clk.rng
    )
    if walkers is not None:
        _write_back(walkers, pool)
    if n:
        state.attack_spawned = int(getattr(state, "attack_spawned", 0)) + n
    return n


def spawn_rioter(
    pool: bytearray,
    tiles: bytearray,
    x: int,
    y: int,
    *,
    rng: int = 1,
) -> int:
    """41DD4 tail: type 7, pad=0, retry class=0, next_state=0x0B."""
    if not walker_spawn_retry(
        pool, tiles, TYPE_RIOTER, x, y, pad=0, retry_class=0, rng=rng
    ):
        return 0
    walker_finish_spawn(pool, _LAST_SPAWN_SLOT, next_state=0x0B)
    return _LAST_SPAWN_SLOT


def _unrest_tick_score(tiles: bytearray, off: int, tid: int, addend: int, lut: int) -> int:
    """+11&0xF, then −1 no-market / −1 prefect / −1 +14&3, plus mood + LUT."""
    score = tiles[off + 11] & 0x0F
    if (tiles[off + 10] & 0x0C) == 0:
        score -= 1
    if tiles[off + 10] & 0x30:
        score -= 1
    if tiles[off + 14] & 3:
        score -= 1
    score += addend
    if lut == 9:
        idx = tid - ID_RIOTER_HOUSE_LO
        if 0 <= idx < len(_UNREST_HOUSE):
            score += _UNREST_HOUSE[idx]
    else:
        score += lut
    if score < 0:
        return 0
    return score


def unrest_spawn_rows(
    tiles: bytearray,
    walkers: MutableSequence[Walker] | bytearray | None,
    y0: int,
    n: int,
    state=None,
) -> int:
    """41DD4 else-branch: unrest nibble + type-7 rioter. Fire owns bit7.

    Housing 0x82–0x9B origin, not +3 bit7. Score > 15 → 691C4 rubble
    (no fire) then walker_spawn_retry EAX=7 pad=0 class=0, next_state 0x0B.
    """
    if y0 == 0 and state is not None:
        state.rioters_spawned = 0
        state.unrest_rng = (int(getattr(state, "unrest_rng", 0)) + 1) & 0x3F
    spawned = 0
    pool = None if walkers is None else _pool_from(walkers)
    y1 = min(MAP_H, y0 + n)
    addend = int(getattr(state, "unrest_add", 0)) if state is not None else 0
    for y in range(y0, y1):
        for x in range(MAP_W):
            off = _tile_off(x, y)
            if off + TILE_BYTES > len(tiles):
                continue
            if tiles[off + _TILE_DRAW] & 0x80:
                continue
            tid = tiles[off]
            if tid < ID_RIOTER_HOUSE_LO or tid > ID_RIOTER_HOUSE_HI:
                continue
            if tiles[off + 5] & 0x0F:
                continue
            rng = 0
            if state is not None:
                rng = (int(getattr(state, "unrest_rng", 0)) + 1) & 0x3F
                state.unrest_rng = rng
            lut = _UNREST_TICK[rng]
            score = _unrest_tick_score(tiles, off, tid, addend, lut)
            if score <= 15:
                tiles[off + 11] = (tiles[off + 11] & 0xF0) | (score & 0x0F)
                continue
            if state is not None:
                mood = int(getattr(state, "unrest_add", 0))
                if mood > 6:
                    state.unrest_add = 6
                elif mood > 2:
                    state.unrest_add = 2
                addend = int(state.unrest_add)
            from app.city_sim import tile_collapse_rubble

            tile_collapse_rubble(tiles, x, y, leave_fire=False)
            if pool is None:
                continue
            if spawn_rioter(pool, tiles, x, y):
                spawned += 1
                if state is not None:
                    state.rioters_spawned = (
                        int(getattr(state, "rioters_spawned", 0)) + 1
                    )
    if walkers is not None and pool is not None:
        _write_back(walkers, pool)
    return spawned


def walker_finish_spawn(
    pool: bytearray,
    slot: int,
    *,
    next_state: int,
    home_off: int | None = None,
) -> None:
    """Emit tail: state 1, wait 0x14, next_state from the building."""
    if slot <= 0:
        return
    rec = _rec(pool, slot)
    rec[_OFF_STATE] = 1
    rec[_OFF_WAIT] = 0x14
    rec[_OFF_NEXT_STATE] = next_state & 0xFF
    if home_off is not None:
        struct.pack_into("<i", rec, _OFF_HOME, home_off)
    sid = sprite_id_for(rec[_OFF_TYPE], rec[_OFF_FACING], 0)
    rec[_OFF_SPRITE_ID] = sid & 0xFF
    rec[_OFF_SPRITE_ID + 1] = (sid >> 8) & 0xFF
    _put(pool, slot, rec)


def _retire_home_walker(
    pool: bytearray, tiles: bytearray, home_off: int, new_slot: int
) -> None:
    """FUN_00041A0A: free the previous trader/worker whose +0x28 is this tile."""
    if home_off < 0 or home_off + _TILE_QUEUE >= len(tiles):
        return
    old = tiles[home_off + _TILE_QUEUE]
    tiles[home_off + _TILE_QUEUE] = new_slot & 0xFF
    if old == 0 or old == new_slot or old >= WALKER_COUNT:
        return
    rec = _rec(pool, old)
    if rec[_OFF_OCCUPIED] == 0:
        return
    if struct.unpack_from("<i", rec, _OFF_HOME)[0] != home_off:
        return
    rec[_OFF_STATE] = 2
    _put(pool, old, rec)


def _spawn_on_nearby_pad(
    pool: bytearray,
    tiles: bytearray,
    type_id: int,
    x: int,
    y: int,
    *,
    size: int = 1,
    rng: int = 1,
) -> int:
    """Host fallback: any FLAG_PAD on the building rim (EXE LUT miss)."""
    for dy in range(-1, size + 1):
        for dx in range(-1, size + 1):
            if 0 <= dx < size and 0 <= dy < size:
                continue
            if walker_spawn(
                pool, tiles, type_id, x + dx, y + dy, pad=0x20, rng=rng
            ):
                return 1
    return 0


def _pad_degree(
    tiles: bytearray, x: int, y: int, type_id: int | None = None
) -> int:
    n = 0
    for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
        nx, ny = x + dx, y + dy
        if _in_map(nx, ny) and is_walker_road(tiles, _tile_off(nx, ny), type_id):
            n += 1
    return n


def _find_connected_pad(
    tiles: bytearray,
    x: int,
    y: int,
    *,
    radius: int = 6,
    type_id: int | None = None,
    city_only: bool = False,
) -> tuple[int, int] | None:
    """Prefer a road/plaza with a walkable neighbour, else any walkable pad.

    ``city_only`` skips courtyard 0xAE–0xB9 (clerk spawn / seat).
    """
    ranked: list[tuple[int, int, int, int, int]] = []
    for ny in range(max(0, y - radius), min(MAP_H, y + radius + 1)):
        for nx in range(max(0, x - radius), min(MAP_W, x + radius + 1)):
            off = _tile_off(nx, ny)
            if not is_walker_road(tiles, off, type_id):
                continue
            tid = tiles[off]
            if city_only and _is_forum_floor(tid):
                continue
            deg = _pad_degree(tiles, nx, ny, type_id)
            dist = abs(nx - x) + abs(ny - y)
            kind = 0
            if ID_ROAD_LO <= tid <= ID_ROAD_HI or ID_BRIDGE_LO <= tid <= ID_BRIDGE_HI:
                kind = 0
            elif ID_PLAZA_LO <= tid <= ID_PLAZA_HI:
                kind = 1
            else:
                kind = 2
            ranked.append((0 if deg else 1, kind, dist, nx, ny))
    if not ranked:
        return None
    ranked.sort()
    _k0, _k1, _d, nx, ny = ranked[0]
    return nx, ny


def _relocate_walker(
    pool: bytearray, tiles: bytearray, slot: int, nx: int, ny: int
) -> None:
    rec = _rec(pool, slot)
    drop_walker_slide(slot)
    walker_unlink(tiles, rec, slot)
    off = _tile_off(nx, ny)
    _set_i8(rec, _OFF_X, nx)
    _set_i8(rec, _OFF_Y, ny)
    _set_i8(rec, _OFF_DEST_X, nx)
    _set_i8(rec, _OFF_DEST_Y, ny)
    struct.pack_into("<i", rec, _OFF_TILE, off)
    rec[0xA] = (nx << 4) & 0xFF
    rec[0xB] = (ny << 4) & 0xFF
    if 0 <= off and off + TILE_BYTES <= len(tiles):
        if tiles[off + _TILE_SLOT0] == 0:
            tiles[off + _TILE_SLOT0] = slot
        elif tiles[off + _TILE_SLOT1] == 0:
            tiles[off + _TILE_SLOT1] = slot
        tiles[off + 3] |= 1
    _put(pool, slot, rec)


def _seat_on_connected_pad(pool: bytearray, tiles: bytearray, slot: int) -> None:
    """Seat a clerk on adjacent road / plaza, never the courtyard.

    0xAE–0xB9 stays walkable so they can exit; they must not start there.
    Traders already on the courtyard snap to the nearest city pad.
    """
    rec = _rec(pool, slot)
    typ = rec[_OFF_TYPE]
    x, y = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    here = _tile_off(x, y)
    if here < 0 or here >= len(tiles):
        return
    if _is_city_pavement(tiles[here]):
        return
    found = _find_connected_pad(
        tiles, x, y, radius=8, type_id=typ, city_only=True
    )
    if found and found != (x, y):
        _relocate_walker(pool, tiles, slot, found[0], found[1])


def _snap_off_forum(pool: bytearray, tiles: bytearray, slot: int) -> None:
    """If a non-clerk is standing on 0xAE–0xB9, move them to nearest road."""
    rec = _rec(pool, slot)
    if rec[_OFF_TYPE] == TYPE_CLERK:
        return
    x, y = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    here = _tile_off(x, y)
    if here < 0 or here >= len(tiles):
        return
    if not (ID_FORUM_LO <= tiles[here] <= ID_FORUM_HI):
        return
    found = _find_connected_pad(tiles, x, y, radius=8, type_id=rec[_OFF_TYPE])
    if found and found != (x, y):
        _relocate_walker(pool, tiles, slot, found[0], found[1])


def _spawn_on_forum_or_plaza(
    pool: bytearray,
    tiles: bytearray,
    type_id: int,
    x: int,
    y: int,
    *,
    size: int = 2,
    rng: int = 1,
) -> int:
    """Last clerk fallback: road 0x52–0x5C / plaza on the building rim.

    Same idea as market class-4 rim. Courtyard tiles are never a dest.
    """
    found = _find_connected_pad(
        tiles,
        x + size // 2,
        y + size // 2,
        radius=size + 2,
        type_id=type_id,
        city_only=True,
    )
    if found and walker_spawn(
        pool, tiles, type_id, found[0], found[1], pad=0x20, rng=rng
    ):
        return 1
    return 0


def walkers_relink_tiles(pool: bytearray, tiles: bytearray) -> None:
    """Phase 0xD2: wipe +7/+8 then re-place live slots 1…200."""
    if len(tiles) >= MAP_W * MAP_H * TILE_BYTES:
        for i in range(MAP_W * MAP_H):
            base = i * TILE_BYTES
            tiles[base + _TILE_SLOT0] = 0
            tiles[base + _TILE_SLOT1] = 0
    for slot in range(1, WALKER_COUNT):
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            continue
        off = struct.unpack_from("<i", rec, _OFF_TILE)[0]
        if off < 0 or off + TILE_BYTES > len(tiles):
            continue
        if tiles[off + _TILE_SLOT0] == 0:
            tiles[off + _TILE_SLOT0] = slot
        elif tiles[off + _TILE_SLOT1] == 0:
            tiles[off + _TILE_SLOT1] = slot


def emit_walkers(
    tiles: bytearray,
    walkers: MutableSequence[Walker] | bytearray | None,
    y0: int,
    n: int,
    *,
    population: int,
    rng: int = 1,
    kinds: str | None = None,
    wrap4: int = 0,
    goods: bytes | bytearray | None = None,
    factory_labor: int = 0,
    province_links: int = 0,
    shutoff: frozenset[str] | None = None,
    city_only: bool = False,
) -> int:
    """Spawn from civic buildings onto adjacent roads. Mutates walkers."""
    global LAST_EMIT_NOTE
    want_market = kinds in (None, "civic", "market")
    produced = 0
    closed = shutoff or frozenset()
    prod_labor = 0 if "factory" in closed else factory_labor
    if want_market:
        from app.city_paint import factory_produce_row

        produced = factory_produce_row(
            tiles,
            y0,
            n,
            goods=goods,
            labor=prod_labor,
            province_links=province_links,
            city_only=city_only,
        )
    if walkers is None:
        LAST_EMIT_NOTE = f"skip walkers=None produced={produced}"
        return 0
    if population < 2:
        LAST_EMIT_NOTE = f"skip pop={population}<2 produced={produced}"
        _path_log(f"walker emit skip pop={population}<2")
        if want_market:
            restage_market_band(tiles, y0, n, wrap4=wrap4, city_only=city_only)
        return 0
    pool = _pool_from(walkers)
    spawned = emit_walkers_row(
        tiles,
        pool,
        y0,
        n,
        population=population,
        rng=rng,
        kinds=kinds,
        wrap4=wrap4,
        goods=goods,
        factory_labor=factory_labor,
        province_links=province_links,
        produced=produced,
        shutoff=shutoff,
        city_only=city_only,
    )
    _write_back(walkers, pool)
    return spawned


def relink_walker_tiles(
    tiles: bytearray, walkers: MutableSequence[Walker] | bytearray | None
) -> None:
    if walkers is None:
        return
    pool = _pool_from(walkers)
    walkers_relink_tiles(pool, tiles)
    _write_back(walkers, pool)


def emit_walkers_row(
    tiles: bytearray,
    pool: bytearray,
    y0: int,
    n: int,
    *,
    population: int,
    rng: int = 1,
    kinds: str | None = None,
    wrap4: int = 0,
    goods: bytes | bytearray | None = None,
    factory_labor: int = 0,
    province_links: int = 0,
    produced: int | None = None,
    shutoff: frozenset[str] | None = None,
    city_only: bool = False,
) -> int:
    """Forum 0xAE–0xB9, prefecture 0xE3, barracks 0xE4, market 0xFC–0xFF.

    ``kinds`` is the city_sim band: forum / tower / security / market.
    None keeps the old combined scan (tests).
    ``wrap4`` is [0x102694]; odd values decay market +9 in 0x41A4E.
    Factory stock (0x41b33) runs from emit_walkers before the pop gate.
    """
    global LAST_EMIT_NOTE
    spawned = 0
    civic = 0
    waiting = 0
    noroad = 0
    markets = 0
    want_forum = kinds in (None, "civic", "forum")
    want_tower = kinds in (None, "civic", "tower")
    want_security = kinds in (None, "civic", "security")
    want_market = kinds in (None, "civic", "market")
    closed = shutoff or frozenset()
    prod_labor = 0 if "factory" in closed else factory_labor
    if produced is None and want_market:
        from app.city_paint import factory_produce_row

        produced = factory_produce_row(
            tiles,
            y0,
            n,
            goods=goods,
            labor=prod_labor,
            province_links=province_links,
            city_only=city_only,
        )
    if produced is None:
        produced = 0
    if population < 2:
        LAST_EMIT_NOTE = f"skip pop={population}<2 produced={produced}"
        return 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _tile_off(x, y)
            hid = tiles[off]
            if tiles[off + 5] & 0xF:
                continue
            wait = tiles[off + 6] & 0x0F
            start = (tiles[off + 5] >> 4) & 0x0F
            size = 1
            if 0xAE <= hid <= 0xB9 and want_forum:
                # Type 1 always roams (state 3). Class 9/0x10 used to overwrite
                # next_state with 2/1 — free / wait-forever, so clerks froze.
                typ, nxt, cls, tries = 1, 3, 1, 4
                if hid >= 0xB6:
                    cls, tries = 0x10, 16
                    size = 4
                elif hid >= 0xB2:
                    cls, tries = 9, 12
                    size = 3
                else:
                    cls, tries = 4, 8
                    size = 2
            elif hid == 0xBF and want_tower:
                # 0x4133E: type 4 next_state 6 only if type 3/7 in r=6.
                if walker_find_type3or7(pool, x, y, 6) == 0:
                    continue
                typ, nxt, cls, tries = 4, 6, 1, 4
            elif hid == 0xE3 and want_security:
                typ, nxt, cls, tries = 5, 8, 1, 4
            elif hid == 0xE4 and want_security:
                typ, nxt, cls, tries = 4, 7, 9, 12
                size = 3
            elif hid == 0xFA and want_market:
                # 0x41719 later id: type 6, next_state 10, retry class 9, 3×3.
                typ, nxt, cls, tries = 6, 10, 9, 12
                size = 3
            elif 0xFC <= hid <= 0xFF and want_market:
                # FUN_00041719 / 0x417F9: type 2, next_state 4, pad,
                # retry class 4 (DAT_00094FE5[0xFC]=4 → 2×2 rim).
                # 0x41A4E restages from +9 before the wait gate.
                restage_market_origin(
                    tiles, off, wrap4=wrap4, city_only=city_only
                )
                hid = tiles[off]
                typ, nxt, cls, tries = 2, 4, 4, 8
                size = 2
            else:
                continue
            civic += 1
            if typ == 2:
                markets += 1
            kind = (
                "forum"
                if typ == 1
                else (
                    "factory"
                    if typ == 6
                    else ("prefect" if hid == 0xE3 else "")
                )
            )
            if kind and kind in closed:
                # Labor vs building +6 wait / emit gate: hold countdown, no spawn.
                hold = 3 if wait == 0 else (wait - 1) & 0x0F
                tiles[off + 6] = (tiles[off + 6] & 0xF0) | hold
                waiting += 1
                if typ in (1, 6):
                    _path_log(
                        f"{kind} skip understaffed wait={hold} "
                        f"home={x},{y} id={hid:#x}"
                    )
                continue
            if wait:
                tiles[off + 6] = (tiles[off + 6] & 0xF0) | ((wait - 1) & 0x0F)
                waiting += 1
                if typ == 2:
                    _path_log(
                        f"market skip wait={wait} home={x},{y} id={hid:#x}"
                    )
                continue
            got = walker_spawn_retry(
                pool,
                tiles,
                typ,
                x,
                y,
                pad=0x20,
                retry_class=cls,
                start=start,
                rng=rng,
            )
            if not got:
                got = _spawn_on_nearby_pad(
                    pool, tiles, typ, x, y, size=size, rng=rng
                )
            if not got and typ == 1:
                got = _spawn_on_forum_or_plaza(
                    pool, tiles, typ, x, y, size=size, rng=rng
                )
            if not got and typ == 2:
                got = _spawn_on_market_road(
                    pool, tiles, typ, x, y, size=size, rng=rng
                )
            if got:
                walker_finish_spawn(
                    pool,
                    _LAST_SPAWN_SLOT,
                    next_state=nxt,
                    home_off=off,
                )
                # FUN_00041A0A: one live walker per origin (tile[+18] + home +0x28).
                _retire_home_walker(pool, tiles, off, _LAST_SPAWN_SLOT)
                if typ in (1, 2):
                    _seat_on_connected_pad(pool, tiles, _LAST_SPAWN_SLOT)
                if typ == 2:
                    rec = _rec(pool, _LAST_SPAWN_SLOT)
                    wx, wy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
                    sid = rec[_OFF_SPRITE_ID] | (rec[_OFF_SPRITE_ID + 1] << 8)
                    _path_log(
                        f"market spawn type=2 slot={_LAST_SPAWN_SLOT} "
                        f"home={x},{y} xy={wx},{wy} next=4 sprite={sid} "
                        f"(LTLMEN base {TYPE_LTLMEN_BASE[2]})"
                    )
                spawned += 1
                start = got & 0x0F
                wait = 3
            else:
                noroad += 1
                if typ == 2:
                    _path_log(
                        f"market skip no-road home={x},{y} id={hid:#x} "
                        f"(need 0x52-0x5C / plaza on 2x2 rim)"
                    )
                start = (start + 1) & 0x0F
                if start >= tries:
                    start = 0
                wait = 0
            tiles[off + 6] = (tiles[off + 6] & 0xF0) | (wait & 0x0F)
            tiles[off + 5] = (tiles[off + 5] & 0x0F) | ((start & 0x0F) << 4)
    LAST_EMIT_NOTE = (
        f"civic={civic} markets={markets} spawned={spawned} "
        f"waiting={waiting} no-road={noroad} pop={population} "
        f"y0={y0} n={n} kinds={kinds or 'civic'} produced={produced} "
        f"shutoff={'+'.join(sorted(closed)) or 'none'}"
    )
    return spawned


def _spawn_on_market_road(
    pool: bytearray,
    tiles: bytearray,
    type_id: int,
    x: int,
    y: int,
    *,
    size: int = 2,
    rng: int = 1,
) -> int:
    """Host fallback: road 0x52–0x5C / plaza next to the 2×2 market."""
    found = _find_connected_pad(
        tiles, x + size // 2, y + size // 2, radius=size + 1, type_id=type_id
    )
    if found and walker_spawn(
        pool, tiles, type_id, found[0], found[1], pad=0x20, rng=rng
    ):
        return 1
    return 0


def walker_step(pool: bytearray, tiles: bytearray, slot: int) -> bool:
    """walker_step 0x488DC. False if dest had two walkers (freed)."""
    rec = _rec(pool, slot)
    walker_unlink(tiles, rec, slot)
    facing = rec[_OFF_FACING]
    if facing > 7:
        _put(pool, slot, rec)
        return False
    ox, oy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    dx, dy, doff = _FACING_DELTA[facing]
    _set_i8(rec, _OFF_X, ox + dx)
    _set_i8(rec, _OFF_Y, oy + dy)
    note_walker_slide(slot, ox, oy, ox + dx, oy + dy, facing)
    tile = struct.unpack_from("<i", rec, _OFF_TILE)[0] + doff
    struct.pack_into("<i", rec, _OFF_TILE, tile)
    rec[0xA] = (_i8(rec, _OFF_X) << 4) & 0xFF
    rec[0xB] = (_i8(rec, _OFF_Y) << 4) & 0xFF
    if 0 <= tile and tile + TILE_BYTES <= len(tiles):
        if tiles[tile + _TILE_SLOT0] == 0:
            tiles[tile + _TILE_SLOT0] = slot
        elif tiles[tile + _TILE_SLOT1] == 0:
            tiles[tile + _TILE_SLOT1] = slot
        else:
            _put(pool, slot, rec)
            walker_free(pool, tiles, slot)
            return False
    _put(pool, slot, rec)
    return True


def _advance_anim(rec: bytearray) -> bool:
    """Shared roam/path timer. True if bit0 (step-done) is set after this pulse."""
    if rec[_OFF_ANIM_FLAGS] & _ANIM_DONE:
        rec[_OFF_WALK_FRAME] = 0
        rec[_OFF_ANIM_TIMER] = 0
        return True
    speed = _SPEED_ROAD if rec[_OFF_ON_ROAD] == 0 else _SPEED_PAD
    rec[_OFF_ANIM_TIMER] = (rec[_OFF_ANIM_TIMER] + 1) & 0xFF
    # Exceed-or-equal the type-speed byte (0x9673E road=2, 0x96735 pad=1)
    # → 2 / 1 ticks per walk_frame → 32 / 16 pulses per tile.
    if rec[_OFF_ANIM_TIMER] >= speed:
        rec[_OFF_ANIM_TIMER] = 0
        rec[_OFF_WALK_FRAME] = (rec[_OFF_WALK_FRAME] + 1) & 0xFF
        if rec[_OFF_WALK_FRAME] > 15:
            rec[_OFF_ANIM_FLAGS] |= _ANIM_DONE
    return False


def walker_anim_roam(
    pool: bytearray, tiles: bytearray, slot: int, pads_only: int
) -> int:
    """walker_anim_roam 0x47EFA. EAX=0 → only dest_ok==1 (pad). Returns 1 if bit0."""
    rec = _rec(pool, slot)
    if not _advance_anim(rec):
        _put(pool, slot, rec)
        return 0
    if rec[_OFF_WANT_MOVE] == 0:
        _put(pool, slot, rec)
        return 1
    facing = facing_from_delta(
        _i8(rec, _OFF_X),
        _i8(rec, _OFF_Y),
        _i8(rec, _OFF_DEST_X),
        _i8(rec, _OFF_DEST_Y),
        rec[_OFF_FACING],
    )
    if facing >= 8:
        rec[_OFF_WANT_MOVE] = 0
        rec[_OFF_ANIM_FLAGS] |= _ANIM_FAIL
        _put(pool, slot, rec)
        return 1
    code = walker_can_step(tiles, rec, facing)
    ok = code != 0 and code < 3 and not (pads_only == 0 and code == 2)
    if ok:
        rec[_OFF_ON_ROAD] = 1
        rec[_OFF_ANIM_FLAGS] = rec[_OFF_ANIM_FLAGS] & ~_ANIM_DONE
        rec[_OFF_FACING] = facing
        rec[_OFF_WALK_FRAME] = 1
        _put(pool, slot, rec)
        walker_step(pool, tiles, slot)
        return 1
    dx, dy, _doff = _FACING_DELTA[facing] if 0 <= facing <= 7 else (0, 0, 0)
    nx, ny = _i8(rec, _OFF_X) + dx, _i8(rec, _OFF_Y) + dy
    dest_off = _tile_off(nx, ny) if _in_map(nx, ny) else -1
    dest_id = tiles[dest_off] if dest_off >= 0 and dest_off < len(tiles) else -1
    dest_flags = (
        tiles[dest_off + _TILE_FLAGS]
        if dest_off >= 0 and dest_off + _TILE_FLAGS < len(tiles)
        else -1
    )
    _path_log(
        f"walker path blocked  slot={slot}  type={rec[_OFF_TYPE]}  "
        f"xy={_i8(rec, _OFF_X)},{_i8(rec, _OFF_Y)}  facing={facing}  "
        f"dest={nx},{ny}  id={dest_id:#x}  flags={dest_flags:#x}  code={code}"
    )
    rec[_OFF_STATE] = 1
    rec[_OFF_WAIT] = 0x14
    rec[_OFF_FACING] = (rec[_OFF_FACING] + 4) & 7
    _put(pool, slot, rec)
    return 1


def walker_anim_path(pool: bytearray, tiles: bytearray, slot: int) -> int:
    """walker_anim_path 0x48084. Path-fail helpers 0x2B54A / 0x2BA63 stubbed."""
    rec = _rec(pool, slot)
    if not _advance_anim(rec):
        _put(pool, slot, rec)
        return 0
    if rec[_OFF_WANT_MOVE] == 0:
        _put(pool, slot, rec)
        return 1
    facing = facing_from_delta(
        _i8(rec, _OFF_X),
        _i8(rec, _OFF_Y),
        _i8(rec, _OFF_DEST_X),
        _i8(rec, _OFF_DEST_Y),
        rec[_OFF_FACING],
    )
    if facing >= 8:
        rec[_OFF_STATE] = 1
        rec[_OFF_WAIT] = 0x78
        rec[_OFF_ANIM_FLAGS] |= _ANIM_FAIL
        _put(pool, slot, rec)
        return 1
    code = walker_can_step(tiles, rec, facing)
    if code == 999 or (code == 0 and rec[_OFF_BUMP] != 0):
        rec[_OFF_FACING] = (rec[_OFF_FACING] + 1) & 7
        if rec[_OFF_BUMP] == 0:
            rec[_OFF_STATE] = 1
            rec[_OFF_WAIT] = 0x10
        else:
            rec[_OFF_BUMP] = 0
        _put(pool, slot, rec)
        return 1
    if code == 0:
        # Stub: unread 0x2B54A / 0x2BA63 / 0x48A49 / 0x483D6 — sidestep, keep dest
        rec[_OFF_STATE] = 1
        rec[_OFF_WAIT] = 0x14
        rec[_OFF_FACING] = (rec[_OFF_FACING] + 1) & 7
        _put(pool, slot, rec)
        return 1
    rec[_OFF_ON_ROAD] = 1 if code == 1 else 0
    rec[_OFF_ANIM_FLAGS] = rec[_OFF_ANIM_FLAGS] & ~_ANIM_DONE
    rec[_OFF_FACING] = facing
    rec[_OFF_WALK_FRAME] = 1
    _put(pool, slot, rec)
    walker_step(pool, tiles, slot)
    return 1


def walker_find_type3or7(pool: bytearray, x: int, y: int, radius: int) -> int:
    """walker_find_type3or7 0x47D1A. 0 = none (slot 0 is never spawned)."""
    x0 = max(0, x - radius)
    y0 = max(0, y - radius)
    x1 = min(MAP_W, x + radius)  # high edge exclusive
    y1 = min(MAP_H, y + radius)
    best = 0
    best_d = 10**9
    for slot in range(WALKER_COUNT):
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            continue
        typ = rec[_OFF_TYPE]
        if typ not in (3, 7):
            continue
        wx, wy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
        if not (x0 <= wx < x1 and y0 <= wy < y1):
            continue
        dist = max(abs(wx - x), abs(wy - y))
        if dist < best_d:
            best_d = dist
            best = slot
    return best


# 0x41A4E / 0x41b33 / state 4+10: +9 bits 0–1 usage, 2–3 goods.
# Factory 0x41b33 keeps production in the hi nibble — never smash 0xF0.
_MARKET_PLUS9_USAGE = 0x03
_MARKET_PLUS9_GOODS = 0x0C
_ADDEND_2X2 = (0, 2, 1, 3)


def _pack_score_nibble(score: int, *, shift: int) -> int:
    """State 4/10: score>0 → 2 or 8; score≥8 → 3 or 0xC."""
    if score <= 0:
        return 0
    if score < 8:
        return 2 << shift
    return 3 << shift


def pack_home_plus9(tiles: bytearray, home: int, score_a: int, score_b: int) -> None:
    """Write usage/goods into +9 bits 0–3. Keep factory stock in bits 4–7."""
    if home < 0 or home + 9 >= len(tiles):
        return
    cur = tiles[home + 9]
    nxt = cur
    if score_a > 0:
        nxt = (nxt & ~_MARKET_PLUS9_USAGE) | _pack_score_nibble(score_a, shift=0)
    if score_b > 0:
        nxt = (nxt & ~_MARKET_PLUS9_GOODS) | _pack_score_nibble(score_b, shift=2)
    tiles[home + 9] = nxt


def decay_plus9_service(v: int) -> int:
    """0x41A4E / 0x41b33 tail: 3→2→1→0 and 0xC→8→4→0. Hi nibble stays."""
    usage, goods = v & _MARKET_PLUS9_USAGE, v & _MARKET_PLUS9_GOODS
    if usage:
        v = (v & ~_MARKET_PLUS9_USAGE) | (
            1 if usage == 2 else 2 if usage == 3 else 0
        )
    if goods:
        v = (v & ~_MARKET_PLUS9_GOODS) | (
            4 if goods == 8 else 8 if goods == 0x0C else 0
        )
    return v


def _stamp_market_stage(tiles: bytearray, off: int, stage: int) -> None:
    """0x6A368 stand-in: 2×2 id 0xFC+stage, +4 = 0x30+stage*4 + addend."""
    tid = 0xFC + (stage & 3)
    base = 0x30 + (stage & 3) * 4
    x = (off % 0x640) // 0x14
    y = off // 0x640
    for dy in range(2):
        for dx in range(2):
            nx, ny = x + dx, y + dy
            if not _in_map(nx, ny):
                continue
            cell = _tile_off(nx, ny)
            hid = tiles[cell]
            if cell != off and not (0xFC <= hid <= 0xFF):
                continue
            tiles[cell] = tid
            tiles[cell + 4] = (base + _ADDEND_2X2[dy * 2 + dx]) & 0xFF


def seed_city_only_market_stock(tiles: bytearray, off: int) -> bool:
    """Sandbox +9 goods bits. EXE fills them from type-2 score_b (factory
    splash); City Only has no province grain, so empty markets never feed.
    Does not invent a granary — only bits 2–3, same packed nibble as 0x45FE9.
    """
    if off < 0 or off + 9 >= len(tiles):
        return False
    if not (0xFC <= tiles[off] <= 0xFF):
        return False
    if tiles[off + 9] & _MARKET_PLUS9_GOODS:
        return False
    tiles[off + 9] = (tiles[off + 9] & ~_MARKET_PLUS9_GOODS) | _MARKET_PLUS9_GOODS
    return True


def restage_market_band(
    tiles: bytearray, y0: int, n: int, *, wrap4: int = 0, city_only: bool = False
) -> int:
    """0x41719 market arm: 0x41A4E on every origin in the emit band."""
    n_ok = 0
    for y in range(y0, min(MAP_H, y0 + n)):
        for x in range(MAP_W):
            off = _tile_off(x, y)
            if off + 9 >= len(tiles):
                continue
            if tiles[off + 5] & 0xF:
                continue
            if 0xFC <= tiles[off] <= 0xFF:
                restage_market_origin(
                    tiles, off, wrap4=wrap4, city_only=city_only
                )
                n_ok += 1
    return n_ok


def restage_market_origin(
    tiles: bytearray, off: int, *, wrap4: int = 0, city_only: bool = False
) -> int:
    """FUN_00041a4e 0x41A4E. Stage from +9; decay bits 0–3 when wrap4&1.

    No goods (bits 2–3==0) forces stage 1 (0xFD). Else stage = bits 0–1.
    City Only reseeds goods after decay so houses keep eating without farms.
    """
    if off < 0 or off + 9 >= len(tiles):
        return 0
    hid = tiles[off]
    if not (0xFC <= hid <= 0xFF):
        return 0
    plus9 = tiles[off + 9]
    usage = plus9 & _MARKET_PLUS9_USAGE
    goods = plus9 & _MARKET_PLUS9_GOODS
    stage = 1 if goods == 0 else usage
    want = 0xFC + stage
    if hid != want:
        _stamp_market_stage(tiles, off, stage)
    if wrap4 & 1:
        plus9 = decay_plus9_service(plus9)
        tiles[off + 9] = plus9
    if city_only:
        seed_city_only_market_stock(tiles, off)
    return stage


def market_has_goods(tiles: bytearray, home: int) -> bool:
    """Market +9 bits 2–3: factory contact packed by state 4."""
    if home < 0 or home + 9 >= len(tiles):
        return False
    hid = tiles[home]
    return 0xFC <= hid <= 0xFF and bool(tiles[home + 9] & _MARKET_PLUS9_GOODS)


def walker_housing_scan(rec: bytearray, tiles: bytearray, *, factory_bit: bool) -> None:
    """FUN_0004a7ff 0x4A7FF. EAX=1 (r=1); EDX=1 factory +13&0x80, EDX=0 market +13&0x40.

    score_a += houses 0x82–0xA1, then −2 if >4 else −1 if >0, cap 100.
    score_b += 2 per factory-bit tile (EDX=1) or 3 per market-bit (EDX=0),
    then −1 if >0, cap 100. State 4/10 pack bits 0–3 of home[+9] only —
    factory production stock lives in the hi nibble (0x41b33).
    """
    x, y = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    houses = 0
    factory_tiles = 0
    market_tiles = 0
    for ny in range(max(0, y - 1), min(MAP_H, y + 2)):
        for nx in range(max(0, x - 1), min(MAP_W, x + 2)):
            off = _tile_off(nx, ny)
            if off + 13 >= len(tiles):
                continue
            tid = tiles[off]
            if 0x82 <= tid <= 0xA1:
                houses += 1
            splash = tiles[off + 13]
            if splash & 0x80:
                factory_tiles += 1
            if splash & 0x40:
                market_tiles += 1
    score_a = rec[_OFF_SCORE_A] + houses
    if score_a > 4:
        score_a -= 2
    elif score_a > 0:
        score_a -= 1
    rec[_OFF_SCORE_A] = min(100, max(0, score_a))
    score_b = rec[_OFF_SCORE_B]
    if factory_bit:
        score_b += factory_tiles * 2
    else:
        score_b += market_tiles * 3
    if score_b > 0:
        score_b -= 1
    rec[_OFF_SCORE_B] = min(100, max(0, score_b))
    home = struct.unpack_from("<i", rec, _OFF_HOME)[0]
    if home < 0 or home + 9 >= len(tiles):
        return
    hid = tiles[home]
    typ = rec[_OFF_TYPE]
    if (typ == 2 and 0xFC <= hid <= 0xFF) or (typ == 6 and hid == 0xFA):
        pack_home_plus9(tiles, home, rec[_OFF_SCORE_A], rec[_OFF_SCORE_B])


def _roam_step_done(
    pool: bytearray,
    tiles: bytearray,
    slot: int,
    *,
    or_bits: int | None,
    or_r: int,
    housing: bool = False,
    factory_bit: bool = True,
) -> bytearray | None:
    """anim_roam(0) return 1 = step-done: OR +10, optional 0x4A7FF, then pick."""
    if walker_anim_roam(pool, tiles, slot, 0) == 0:
        return None
    rec = _rec(pool, slot)
    if rec[_OFF_OCCUPIED] == 0:
        return None
    if or_bits is not None:
        tile_or_radius(
            tiles, _i8(rec, _OFF_X), _i8(rec, _OFF_Y), or_r, 10, or_bits
        )
    if housing:
        walker_housing_scan(rec, tiles, factory_bit=factory_bit)
    return rec


def _pick_or_die(
    rec: bytearray,
    tiles: bytearray,
    clock: WalkerClock,
    *,
    wait_on_stuck: int,
    slot: int = 0,
) -> None:
    x, y = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    typ = rec[_OFF_TYPE]
    here = _tile_off(x, y)
    on_forum = (
        typ == TYPE_CLERK
        and 0 <= here < len(tiles)
        and _is_forum_floor(tiles[here])
    )
    if on_forum:
        linger = (rec[_OFF_LINGER] + 1) & 0xFF
        rec[_OFF_LINGER] = linger
        if linger >= _CLERK_FORUM_LINGER:
            exit_f = _clerk_exit_facing(tiles, x, y, rec[_OFF_FACING])
            if exit_f is not None:
                walker_set_dest(rec, exit_f)
                rec[_OFF_WANT_MOVE] = 1
                rec[_OFF_LINGER] = 0
                return
    elif typ == TYPE_CLERK:
        rec[_OFF_LINGER] = 0
    facing = walker_pick_pad_facing(
        tiles,
        x,
        y,
        rec[_OFF_FACING],
        clock.rng,
        typ,
    )
    clock.rng = (clock.rng + 1) & 0x7FFF
    if facing >= 8:
        rec[_OFF_STATE] = 2
        if wait_on_stuck:
            rec[_OFF_WAIT] = wait_on_stuck
        _path_log(
            f"walker path stuck  slot={slot}  type={typ}  "
            f"xy={x},{y}  no road neighbour"
        )
        return
    walker_set_dest(rec, facing)
    rec[_OFF_WANT_MOVE] = 1


def _roam_then_pick(
    pool: bytearray,
    tiles: bytearray,
    slot: int,
    clock: WalkerClock,
    *,
    or_bits: int | None,
    or_r: int,
    wait_on_stuck: int = 0x28,
    housing: bool = False,
    factory_bit: bool = True,
) -> None:
    """Shared tail of roam states 3/4/10 after anim_roam(0)."""
    rec = _roam_step_done(
        pool,
        tiles,
        slot,
        or_bits=or_bits,
        or_r=or_r,
        housing=housing,
        factory_bit=factory_bit,
    )
    if rec is None:
        return
    _pick_or_die(rec, tiles, clock, wait_on_stuck=wait_on_stuck, slot=slot)
    _put(pool, slot, rec)


def _tile_on_fire_water(tiles: bytearray, off: int) -> bool:
    """id < 8 and +3 bit7 — 4A716 / 4A57F / 4A76D predicate."""
    if off < 0 or off + _TILE_DRAW >= len(tiles):
        return False
    return tiles[off] < 8 and bool(tiles[off + _TILE_DRAW] & 0x80)


def _manhattan(ax: int, ay: int, bx: int, by: int) -> int:
    """FUN_00028247 after the Watcom __CHK prologue."""
    return abs(ax - bx) + abs(ay - by)


def _sector_xy(x: int, y: int) -> tuple[int, int]:
    return x >> 3, y >> 3


def _sector_has_burning(tiles: bytearray, cx: int, cy: int) -> bool:
    if cx < 0 or cy < 0 or cx > 9 or cy > 9:
        return False
    x0, y0 = cx * 8, cy * 8
    for ty in range(y0, min(MAP_H, y0 + 8)):
        for tx in range(x0, min(MAP_W, x0 + 8)):
            if _tile_on_fire_water(tiles, _tile_off(tx, ty)):
                return True
    return False


def vigile_sector_has_fire(tiles: bytearray, x: int, y: int) -> bool:
    """FUN_0004a397 — current 8×8 sector or a neighbor has id<8 + bit7."""
    cx, cy = _sector_xy(x, y)
    if _sector_has_burning(tiles, cx, cy):
        return True
    for dcx, dcy in (
        (0, -1),
        (-1, -1),
        (1, -1),
        (0, 1),
        (-1, 1),
        (1, 1),
        (-1, 0),
        (1, 0),
    ):
        if _sector_has_burning(tiles, cx + dcx, cy + dcy):
            return True
    return False


def vigile_fire_claimed(pool: bytearray, tile_off: int) -> bool:
    """FUN_0004a7ae: another live state-9 walker already has this home."""
    for slot in range(1, WALKER_COUNT):
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            continue
        if rec[_OFF_STATE] != 9:
            continue
        if struct.unpack_from("<i", rec, _OFF_HOME)[0] == tile_off:
            return True
    return False


def vigile_extinguish_here(tiles: bytearray, rec: bytearray) -> bool:
    """FUN_0004a716: standing on burning water/rubble — --+16 or clear bit7."""
    off = struct.unpack_from("<i", rec, _OFF_TILE)[0]
    if not _tile_on_fire_water(tiles, off):
        return False
    if tiles[off + 16] == 1:
        tiles[off + _TILE_DRAW] &= 0x7F
    else:
        tiles[off + 16] = (tiles[off + 16] - 1) & 0xFF
    return True


def vigile_still_on_target(tiles: bytearray, rec: bytearray) -> bool:
    """FUN_0004a76D: home_walker set and home tile still id<8 + bit7."""
    if rec[_OFF_HOME_WALKER] == 0:
        return False
    home = struct.unpack_from("<i", rec, _OFF_HOME)[0]
    return _tile_on_fire_water(tiles, home)


def vigile_pick_fire(
    tiles: bytearray, pool: bytearray, rec: bytearray
) -> tuple[int, int, int] | None:
    """4A397 sector + 4A57F closest burning id<8 in that 8×8."""
    wx, wy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    cx, cy = _sector_xy(wx, wy)
    chosen = (cx, cy) if _sector_has_burning(tiles, cx, cy) else None
    if chosen is None:
        for dcx, dcy in (
            (0, -1),
            (-1, -1),
            (1, -1),
            (0, 1),
            (-1, 1),
            (1, 1),
            (-1, 0),
            (1, 0),
        ):
            ncx, ncy = cx + dcx, cy + dcy
            if _sector_has_burning(tiles, ncx, ncy):
                chosen = (ncx, ncy)
                break
    if chosen is None:
        return None
    sx, sy = chosen[0] * 8, chosen[1] * 8
    best_free: tuple[int, int, int, int] | None = None
    best_taken: tuple[int, int, int, int] | None = None
    for ty in range(sy, min(MAP_H, sy + 8)):
        for tx in range(sx, min(MAP_W, sx + 8)):
            off = _tile_off(tx, ty)
            if not _tile_on_fire_water(tiles, off):
                continue
            dist = _manhattan(wx, wy, tx, ty)
            claimed = vigile_fire_claimed(pool, off)
            row = (dist, tx, ty, off)
            if claimed:
                if best_taken is None or dist < best_taken[0]:
                    best_taken = row
            elif best_free is None or dist < best_free[0]:
                best_free = row
    free_d = best_free[0] if best_free else 100
    taken_d = best_taken[0] if best_taken else 100
    pick = None
    if free_d > 0x28 and taken_d < 0x24 and best_taken:
        pick = best_taken
    elif free_d > 0x0C and taken_d < 6 and best_taken:
        pick = best_taken
    elif free_d > 8 and taken_d < 4 and best_taken:
        pick = best_taken
    elif best_free and free_d < 100:
        pick = best_free
    elif best_taken and taken_d < 100:
        pick = best_taken
    if pick is None:
        return None
    return pick[1], pick[2], pick[3]


def _lock_chase(pool: bytearray, rec: bytearray, target_slot: int) -> None:
    tgt = _rec(pool, target_slot)
    rec[_OFF_HOME_WALKER] = target_slot & 0xFF
    _set_u16(rec, _OFF_RNG_LOCK, _u16(tgt, _OFF_RNG))
    rec[_OFF_DEST_X] = tgt[_OFF_X]
    rec[_OFF_DEST_Y] = tgt[_OFF_Y]
    rec[_OFF_CHASE] = 0
    rec[_OFF_BUMP] = 0


def _state_dispatch(
    pool: bytearray, tiles: bytearray, slot: int, clock: WalkerClock
) -> None:
    rec = _rec(pool, slot)
    state = rec[_OFF_STATE]
    if state == 0:
        return
    if state == 1:
        wait = rec[_OFF_WAIT]
        wait = (wait - 1) & 0xFF
        rec[_OFF_WAIT] = wait
        if wait == 0 or wait > 127:
            rec[_OFF_ANIM_TIMER] = 0
            rec[_OFF_WALK_FRAME] = 0
            rec[_OFF_WANT_MOVE] = 0
            rec[_OFF_STATE] = rec[_OFF_NEXT_STATE]
            rec[_OFF_ANIM_FLAGS] |= _ANIM_DONE
            rec[_OFF_UNK_1E] = 5
        _put(pool, slot, rec)
        return
    if state == 2:
        walker_free(pool, tiles, slot)
        return
    if state == 3:
        _roam_then_pick(
            pool, tiles, slot, clock, or_bits=0x0C, or_r=3, wait_on_stuck=0
        )
        return
    if state == 4:
        rec = _roam_step_done(
            pool,
            tiles,
            slot,
            or_bits=0xC0,
            or_r=3,
            housing=True,
            factory_bit=True,
        )
        if rec is None:
            return
        # EXE state 4 ORs only 0xC0. Food +10 0x0C is the 40d08 hut gate;
        # stocked traders (and paint_market_emitter) refresh it while +9 goods last.
        # Empty 0xFC does not feed. +10 then decays 0x0C→8→4 like evolve_row.
        home = struct.unpack_from("<i", rec, _OFF_HOME)[0]
        if market_has_goods(tiles, home):
            tile_or_radius(
                tiles, _i8(rec, _OFF_X), _i8(rec, _OFF_Y), 3, 10, 0x0C
            )
        _pick_or_die(rec, tiles, clock, wait_on_stuck=0, slot=slot)
        _put(pool, slot, rec)
        return
    if state == 5:
        rec[_OFF_WANT_MOVE] = 1
        rec[_OFF_NEXT_STATE] = 5
        _put(pool, slot, rec)
        if walker_anim_path(pool, tiles, slot) == 0:
            rec = _rec(pool, slot)
            if rec[_OFF_OCCUPIED]:
                rec[_OFF_WAIT] = 0
                rec[_OFF_LINGER] = 3
                _put(pool, slot, rec)
            return
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            return
        if rec[_OFF_ANIM_FLAGS] & _ANIM_DONE:
            linger = rec[_OFF_LINGER]
            if linger:
                rec[_OFF_LINGER] = linger - 1
            else:
                rec[_OFF_LINGER] = 3
                if clock.rally_ok:
                    rec[_OFF_DEST_X] = clock.rally_x & 0xFF
                    rec[_OFF_DEST_Y] = clock.rally_y & 0xFF
            _put(pool, slot, rec)
        return
    if state == 6:
        rec[_OFF_WANT_MOVE] = 1
        _put(pool, slot, rec)
        if walker_anim_path(pool, tiles, slot) == 0:
            return
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0 or (rec[_OFF_ANIM_FLAGS] & _ANIM_DONE) == 0:
            return
        home = rec[_OFF_HOME_WALKER]
        tgt = _rec(pool, home)
        if tgt[_OFF_OCCUPIED] and _u16(rec, _OFF_RNG_LOCK) == _u16(tgt, _OFF_RNG):
            rec[_OFF_DEST_X] = tgt[_OFF_X]
            rec[_OFF_DEST_Y] = tgt[_OFF_Y]
            rec[_OFF_CHASE] = (rec[_OFF_CHASE] + 1) & 0xFF
            if rec[_OFF_CHASE] > 4:
                rec[_OFF_CHASE] = 0
                rec[_OFF_BUMP] = 0
            _put(pool, slot, rec)
            return
        found = walker_find_type3or7(
            pool, _i8(rec, _OFF_X), _i8(rec, _OFF_Y), 10
        )
        if found == 0:
            rec[_OFF_STATE] = 2
            _put(pool, slot, rec)
            return
        _lock_chase(pool, rec, found)
        _put(pool, slot, rec)
        return
    if state == 7:
        rec = _roam_step_done(pool, tiles, slot, or_bits=0x30, or_r=4)
        if rec is None:
            return
        if clock.latch7 or clock.latch3:
            found = walker_find_type3or7(
                pool, _i8(rec, _OFF_X), _i8(rec, _OFF_Y), 10
            )
            if found:
                _lock_chase(pool, rec, found)
                rec[_OFF_STATE] = 6
                _put(pool, slot, rec)
                return
        _pick_or_die(rec, tiles, clock, wait_on_stuck=0x28, slot=slot)
        _put(pool, slot, rec)
        return
    if state == 8:
        rec = _roam_step_done(pool, tiles, slot, or_bits=0x30, or_r=3)
        if rec is None:
            return
        if vigile_sector_has_fire(tiles, _i8(rec, _OFF_X), _i8(rec, _OFF_Y)):
            rec[_OFF_STATE] = 9
            _put(pool, slot, rec)
            return
        if clock.latch7 or clock.latch3:
            found = walker_find_type3or7(
                pool, _i8(rec, _OFF_X), _i8(rec, _OFF_Y), 10
            )
            if found:
                _lock_chase(pool, rec, found)
                rec[_OFF_STATE] = 6
                _put(pool, slot, rec)
                return
        _pick_or_die(rec, tiles, clock, wait_on_stuck=0x28, slot=slot)
        _put(pool, slot, rec)
        return
    if state == 9:
        rec[_OFF_NEXT_STATE] = 9
        _put(pool, slot, rec)
        if walker_anim_path(pool, tiles, slot) == 0:
            return
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            return
        if rec[_OFF_ANIM_FLAGS] & _ANIM_FAIL:
            rec[_OFF_STATE] = 9
            rec[_OFF_HOME_WALKER] = 0
            rec[_OFF_ANIM_FLAGS] &= ~_ANIM_FAIL
        if (rec[_OFF_ANIM_FLAGS] & _ANIM_DONE) == 0:
            _put(pool, slot, rec)
            return
        if vigile_extinguish_here(tiles, rec):
            rec[_OFF_WANT_MOVE] = 0
            rec[_OFF_HOME_WALKER] = 0
            _put(pool, slot, rec)
            return
        if vigile_still_on_target(tiles, rec):
            rec[_OFF_WANT_MOVE] = 1
            _put(pool, slot, rec)
            return
        rec[_OFF_HOME_WALKER] = 0
        rec[_OFF_WANT_MOVE] = 0
        struct.pack_into("<i", rec, _OFF_HOME, 0)
        dest = vigile_pick_fire(tiles, pool, rec)
        if dest is not None:
            dx, dy, hoff = dest
            _set_i8(rec, _OFF_DEST_X, dx)
            _set_i8(rec, _OFF_DEST_Y, dy)
            struct.pack_into("<i", rec, _OFF_HOME, hoff)
            rec[_OFF_BUMP] = 0
            rec[_OFF_HOME_WALKER] = 1
            rec[_OFF_WANT_MOVE] = 1
            _put(pool, slot, rec)
            return
        rec[_OFF_STATE] = 2
        _put(pool, slot, rec)
        return
    if state == 10:
        _roam_then_pick(
            pool,
            tiles,
            slot,
            clock,
            or_bits=None,
            or_r=0,
            housing=True,
            factory_bit=False,
        )
        return
    if state == 11:
        rec[_OFF_WANT_MOVE] = 0
        wait = (rec[_OFF_WAIT] - 1) & 0xFF
        rec[_OFF_WAIT] = wait
        if wait == 0 or wait > 127:
            rec[_OFF_STATE] = 12
            if clock.rally_ok:
                rec[_OFF_DEST_X] = clock.rally_x & 0xFF
                rec[_OFF_DEST_Y] = clock.rally_y & 0xFF
            rec[_OFF_ANIM_TIMER] = 0
            rec[_OFF_WALK_FRAME] = 0
            rec[_OFF_UNK_1E] = 5
        _put(pool, slot, rec)
        return
    if state == 12:
        rec[_OFF_WANT_MOVE] = 1
        _put(pool, slot, rec)
        if walker_anim_path(pool, tiles, slot) == 0:
            return
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            return
        if rec[_OFF_ANIM_FLAGS] & _ANIM_DONE:
            if clock.rally_ok:
                rec[_OFF_DEST_X] = clock.rally_x & 0xFF
                rec[_OFF_DEST_Y] = clock.rally_y & 0xFF
            rec[_OFF_STATE] = 11
            rec[_OFF_WAIT] = 0x1E
            _put(pool, slot, rec)
        return
    # Unknown state: leave record alone (no crash)


def _type_fn(pool: bytearray, tiles: bytearray, slot: int, clock: WalkerClock) -> None:
    rec = _rec(pool, slot)
    typ = rec[_OFF_TYPE]
    if typ == 3:
        clock.latch3 = 2
    elif typ == 7:
        clock.latch7 = 2
    _state_dispatch(pool, tiles, slot, clock)
    rec = _rec(pool, slot)
    if rec[_OFF_OCCUPIED] == 0:
        return
    sid = sprite_id_for(
        rec[_OFF_TYPE], rec[_OFF_FACING], rec[_OFF_WALK_FRAME], state=rec[_OFF_STATE]
    )
    struct.pack_into("<h", rec, _OFF_SPRITE_ID, sid)
    if clock.mod64 == 0:
        rec[_OFF_LIFE] = (rec[_OFF_LIFE] + 1) & 0xFF
        cap = _LIFE_CAP.get(rec[_OFF_TYPE], 30)
        if rec[_OFF_LIFE] >= cap:
            rec[_OFF_STATE] = 2
    _put(pool, slot, rec)


def _pool_from(walkers: MutableSequence[Walker] | bytearray) -> bytearray:
    if isinstance(walkers, bytearray):
        if len(walkers) != WALKER_BYTES:
            raise ValueError(f"walker pool is {len(walkers)} bytes, want {WALKER_BYTES}")
        return walkers
    blob = bytearray(WALKER_BYTES)
    for walker in walkers:
        if 0 <= walker.slot < WALKER_COUNT:
            off = walker.slot * WALKER_STRIDE
            blob[off : off + WALKER_STRIDE] = walker.raw
    return blob


def _write_back(
    walkers: MutableSequence[Walker] | bytearray, blob: bytearray
) -> None:
    if isinstance(walkers, bytearray):
        if walkers is not blob:
            walkers[:] = blob
        return
    # Rebuild so newly spawned slots persist (new-game walkers=[]).
    walkers.clear()
    for slot in range(WALKER_COUNT):
        off = slot * WALKER_STRIDE
        rec = blob[off : off + WALKER_STRIDE]
        if rec[_OFF_OCCUPIED]:
            walkers.append(Walker.unpack(bytes(rec), slot=slot))


def walkers_tick(
    tiles: bytearray,
    walkers: MutableSequence[Walker] | bytearray,
    *,
    clock: WalkerClock | None = None,
) -> TickResult:
    """One walkers_tick 0x459D0. Mutates tiles (+7/+8/+10) and walker records."""
    clk = clock if clock is not None else _CLOCK
    clk.mod64 = clk.mod64 + 1
    if clk.mod64 > 0x3F:
        clk.mod64 = 0
    clk.latch7 = 1 if clk.latch7 > 1 else 0
    clk.latch3 = 1 if clk.latch3 > 1 else 0

    pool = _pool_from(walkers)
    before = [(_i8(pool, i * WALKER_STRIDE + _OFF_X),
               _i8(pool, i * WALKER_STRIDE + _OFF_Y),
               pool[i * WALKER_STRIDE + _OFF_WALK_FRAME],
               pool[i * WALKER_STRIDE + _OFF_OCCUPIED])
              for i in range(WALKER_COUNT)]

    live = 0
    for slot in range(WALKER_COUNT):
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            continue
        live += 1
        typ = rec[_OFF_TYPE]
        if typ < TYPE_MIN or typ > TYPE_MAX:
            walker_free(pool, tiles, slot)
        else:
            _snap_off_forum(pool, tiles, slot)
            _type_fn(pool, tiles, slot, clk)

    stepped = 0
    animated = 0
    freed = 0
    after_live = 0
    for slot in range(WALKER_COUNT):
        occ = pool[slot * WALKER_STRIDE + _OFF_OCCUPIED]
        if occ:
            after_live += 1
        bx, by, bf, bo = before[slot]
        if bo and not occ:
            freed += 1
            continue
        if not occ:
            continue
        ax = _i8(pool, slot * WALKER_STRIDE + _OFF_X)
        ay = _i8(pool, slot * WALKER_STRIDE + _OFF_Y)
        af = pool[slot * WALKER_STRIDE + _OFF_WALK_FRAME]
        if ax != bx or ay != by:
            stepped += 1
        elif af != bf:
            animated += 1

    _write_back(walkers, pool)
    if after_live and (stepped or freed):
        _path_log(
            f"walkers_tick  live={after_live}  moved={stepped}  "
            f"frames={animated}  freed={freed}"
        )
    return TickResult(live=after_live, stepped=stepped, animated=animated, freed=freed)


def selftest() -> list[str]:
    """Synthetic road / aqueduct / leftover-pad cases. No display."""
    lines: list[str] = []
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    road = _tile_off(10, 10)
    tiles[road] = 0x52
    tiles[road + _TILE_FLAGS] = FLAG_PAD
    aq = _tile_off(11, 10)
    tiles[aq] = 0xD6
    tiles[aq + _TILE_FLAGS] = FLAG_PAD | 0x40
    combo = _tile_off(11, 11)
    tiles[combo] = 0xD6
    tiles[combo + _TILE_FLAGS] = FLAG_PAD | 0x40
    tiles[combo + _TILE_DRAW] = 0x90
    grass = _tile_off(12, 10)
    tiles[grass + _TILE_FLAGS] = FLAG_PAD
    bridge = _tile_off(13, 10)
    tiles[bridge] = 0x4E
    tiles[bridge + _TILE_FLAGS] = FLAG_RIVER | FLAG_PAD
    empty = _tile_off(14, 10)

    ok = (
        walker_dest_ok(tiles, road) == 1
        and walker_dest_ok(tiles, aq) == 0
        and walker_dest_ok(tiles, combo) == 1
        and walker_dest_ok(tiles, grass) == 0
        and walker_dest_ok(tiles, bridge) == 1
        and walker_dest_ok(tiles, empty) == 2
    )
    lines.append(
        f"dest_ok road/bridge vs aqueduct/grass-pad: {'ok' if ok else 'FAIL'} "
        f"r={walker_dest_ok(tiles, road)} aq={walker_dest_ok(tiles, aq)} "
        f"combo={walker_dest_ok(tiles, combo)} "
        f"g={walker_dest_ok(tiles, grass)} br={walker_dest_ok(tiles, bridge)}"
    )

    forum = _tile_off(15, 10)
    tiles[forum] = 0xB7
    tiles[forum + _TILE_FLAGS] = 0x01
    plaza = _tile_off(16, 10)
    tiles[plaza] = 0x7C
    tiles[plaza + _TILE_FLAGS] = 0x00
    ok = (
        walker_dest_ok(tiles, forum, 1) == 1
        and walker_dest_ok(tiles, forum, 2) == 0
        and walker_dest_ok(tiles, forum, 4) == 0
        and walker_dest_ok(tiles, forum, 5) == 0
        and walker_dest_ok(tiles, forum, 6) == 0
        and walker_dest_ok(tiles, plaza, 1) == 1
        and walker_dest_ok(tiles, plaza, 2) == 1
        and walker_dest_ok(tiles, plaza, 4) == 1
        and walker_dest_ok(tiles, road, 2) == 1
    )
    lines.append(
        f"dest_ok per type forum/plaza: {'ok' if ok else 'FAIL'} "
        f"clerk_f={walker_dest_ok(tiles, forum, 1)} "
        f"trader_f={walker_dest_ok(tiles, forum, 2)} "
        f"trader_p={walker_dest_ok(tiles, plaza, 2)}"
    )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    poff = _tile_off(20, 20)
    tiles[poff] = 0xE3
    tiles[poff + 1] = 0x01
    # Isolated aqueduct T next to prefecture — must not spawn there.
    aoff = _tile_off(20, 19)
    tiles[aoff] = 0xD6
    tiles[aoff + 1] = FLAG_PAD | 0x40
    nsp = emit_walkers_row(tiles, pool, 20, 1, population=4)
    live = sum(1 for s in range(WALKER_COUNT) if pool[s * WALKER_STRIDE + _OFF_OCCUPIED])
    ok = nsp == 0 and live == 0
    lines.append(f"emit skips aqueduct pad: {'ok' if ok else 'FAIL'} n={nsp} live={live}")

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    tiles[_tile_off(20, 20)] = 0xE3
    tiles[_tile_off(20, 20) + 1] = 0x01
    for x, y in ((20, 19), (21, 19), (22, 19), (22, 20), (22, 21), (21, 21), (20, 21), (20, 20)):
        if x == 20 and y == 20:
            continue
        off = _tile_off(x, y)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    nsp = emit_walkers_row(tiles, pool, 20, 1, population=4)
    clock = WalkerClock()
    moved = 0
    on_road = True
    last_xy = None
    seen: set[tuple[int, int]] = set()
    for _ in range(90):
        result = walkers_tick(tiles, pool, clock=clock)
        moved += result.stepped
        for slot in range(WALKER_COUNT):
            rec = _rec(pool, slot)
            if rec[_OFF_OCCUPIED] == 0:
                continue
            x, y = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
            last_xy = (x, y)
            seen.add((x, y))
            tid = tiles[_tile_off(x, y)]
            if not (ID_ROAD_LO <= tid <= ID_ROAD_HI):
                on_road = False
    ok = nsp >= 1 and moved >= 2 and len(seen) >= 2 and on_road and last_xy is not None
    lines.append(
        f"roam patrols 0x52-0x5C: {'ok' if ok else 'FAIL'} "
        f"spawn={nsp} moved={moved} xy={last_xy} on_road={on_road}"
    )

    rec = bytearray(WALKER_STRIDE)
    rec[_OFF_FACING] = 0
    _set_i8(rec, _OFF_X, 10)
    _set_i8(rec, _OFF_Y, 10)
    walker_set_dest(rec, 2)
    ok = rec[_OFF_FACING] == 2 and _i8(rec, _OFF_DEST_X) == 11 and _i8(rec, _OFF_DEST_Y) == 10
    lines.append(f"set_dest faces dest: {'ok' if ok else 'FAIL'} facing={rec[_OFF_FACING]}")

    from app.walkers import Walker, clear_walker_slides, walker_draw_xy

    clear_walker_slides()
    raw = bytearray(WALKER_STRIDE)
    raw[_OFF_OCCUPIED] = 1
    raw[_OFF_TYPE] = 1
    raw[_OFF_FACING] = 2
    _set_i8(raw, _OFF_X, 10)
    _set_i8(raw, _OFF_Y, 10)
    raw[_OFF_WALK_FRAME] = 8
    mid = Walker.unpack(bytes(raw), slot=1)
    mx, my = walker_draw_xy(mid)
    ok = abs(mx - 9.5) < 0.01 and abs(my - 10.0) < 0.01
    lines.append(f"walk_frame lerp mid-step: {'ok' if ok else 'FAIL'} xy={mx},{my}")
    raw[_OFF_WALK_FRAME] = 0
    idle = Walker.unpack(bytes(raw), slot=1)
    ix, iy = walker_draw_xy(idle)
    ok = ix == 10.0 and iy == 10.0
    lines.append(f"walk_frame 0 sits on tile: {'ok' if ok else 'FAIL'} xy={ix},{iy}")

    from app.walkers import (
        WALK_DISPLAY_FRAMES,
        advance_walker_slides,
        note_walker_slide,
        walker_draw_xy as draw_xy,
    )

    clear_walker_slides()
    note_walker_slide(1, 10.0, 10.0, 11.0, 10.0, 2)
    raw[_OFF_WALK_FRAME] = 1
    stepped = Walker.unpack(bytes(raw), slot=1)
    xs: list[float] = []
    for _ in range(WALK_DISPLAY_FRAMES):
        advance_walker_slides()
        sx, sy = draw_xy(stepped)
        xs.append(sx)
    ok = (
        xs[0] > 10.0
        and xs[-1] >= 10.95
        and all(xs[i] <= xs[i + 1] + 1e-6 for i in range(len(xs) - 1))
    )
    lines.append(
        f"display slide continuous: {'ok' if ok else 'FAIL'} "
        f"x0={xs[0]:.3f} x1={xs[-1]:.3f}"
    )
    clear_walker_slides()

    reset_clock()
    clear_walker_slides()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    # Palatine 4×4 forum, no road — clerks used to freeze on the floor.
    for dy in range(4):
        for dx in range(4):
            off = _tile_off(30 + dx, 30 + dy)
            tiles[off] = 0xB7
            tiles[off + 1] = 0x01
    plaza = _tile_off(29, 30)
    tiles[plaza] = 0x7C
    tiles[plaza + 1] = FLAG_PAD
    nsp = emit_walkers_row(tiles, pool, 30, 1, population=4)
    rec = None
    slot = 0
    for i in range(WALKER_COUNT):
        cand = _rec(pool, i)
        if cand[_OFF_OCCUPIED] and cand[_OFF_TYPE] == 1:
            rec = cand
            slot = i
            break
    nxt = rec[_OFF_NEXT_STATE] if rec is not None else -1
    wx = wy = tid = -1
    if rec is not None:
        wx, wy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
        tid = tiles[_tile_off(wx, wy)]
    ok = (
        nsp >= 1
        and rec is not None
        and nxt == 3
        and (
            ID_PLAZA_LO <= tid <= ID_PLAZA_HI
            or ID_ROAD_LO <= tid <= ID_ROAD_HI
        )
        and not (ID_FORUM_LO <= tid <= ID_FORUM_HI)
    )
    lines.append(
        f"clerk pad plaza/road next=3: {'ok' if ok else 'FAIL'} "
        f"spawn={nsp} next={nxt} xy={wx},{wy} id={tid:#x}"
    )
    if rec is not None:
        rec[_OFF_STATE] = 3
        rec[_OFF_WAIT] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        _put(pool, slot, rec)
        clock = WalkerClock()
        moved = 0
        for _ in range(40):
            result = walkers_tick(tiles, pool, clock=clock)
            moved += result.stepped + result.animated
        ok = moved >= 1
        lines.append(f"clerk animates on forum/plaza: {'ok' if ok else 'FAIL'} moved={moved}")

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    # 2×2 Aventine at a T — class-4 rim is 0x52–0x5C, not the courtyard.
    for dy in range(2):
        for dx in range(2):
            off = _tile_off(20 + dx, 20 + dy)
            tiles[off] = 0xAE
            tiles[off + 1] = 0x01
            tiles[off + 5] = dy * 2 + dx
    for y in range(19, 23):
        off = _tile_off(19, y)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    for x in range(19, 23):
        off = _tile_off(x, 22)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    nsp = emit_walkers_row(tiles, pool, 20, 3, population=4, kinds="forum")
    rec = None
    slot = 0
    for i in range(WALKER_COUNT):
        cand = _rec(pool, i)
        if cand[_OFF_OCCUPIED] and cand[_OFF_TYPE] == 1:
            rec = cand
            slot = i
            break
    nxt = rec[_OFF_NEXT_STATE] if rec is not None else -1
    wx = wy = tid = -1
    if rec is not None:
        wx, wy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
        tid = tiles[_tile_off(wx, wy)]
    ok = (
        nsp == 1
        and rec is not None
        and nxt == 3
        and ID_ROAD_LO <= tid <= ID_ROAD_HI
    )
    lines.append(
        f"clerk spawn dest road 0x52-0x5C: {'ok' if ok else 'FAIL'} "
        f"spawn={nsp} next={nxt} xy={wx},{wy} id={tid:#x}"
    )
    tiles[_tile_off(20, 20) + 6] = 0
    n2 = emit_walkers_row(tiles, pool, 20, 3, population=4, kinds="forum")
    live1 = [
        s
        for s in range(WALKER_COUNT)
        if pool[s * WALKER_STRIDE + _OFF_OCCUPIED]
        and pool[s * WALKER_STRIDE + _OFF_TYPE] == 1
        and pool[s * WALKER_STRIDE + _OFF_STATE] != 2
    ]
    ok = n2 >= 1 and len(live1) == 1
    lines.append(
        f"one clerk per forum origin: {'ok' if ok else 'FAIL'} "
        f"n2={n2} live={len(live1)}"
    )
    rec = None
    slot = 0
    for i in live1:
        rec = _rec(pool, i)
        slot = i
        break
    if rec is not None:
        rec[_OFF_STATE] = 3
        rec[_OFF_WAIT] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        _put(pool, slot, rec)
        clock = WalkerClock()
        moved = 0
        forum_hits = 0
        last_tid = tid
        for _ in range(80):
            result = walkers_tick(tiles, pool, clock=clock)
            moved += result.stepped
            live = _rec(pool, slot)
            if live[_OFF_OCCUPIED] == 0:
                continue
            tx, ty = _i8(live, _OFF_X), _i8(live, _OFF_Y)
            last_tid = tiles[_tile_off(tx, ty)]
            if ID_FORUM_LO <= last_tid <= ID_FORUM_HI:
                forum_hits += 1
        taxed = False
        for y in range(19, 23):
            for x in range(19, 23):
                off = _tile_off(x, y)
                if ID_ROAD_LO <= tiles[off] <= ID_ROAD_HI and tiles[off + 10] & 0x0C:
                    taxed = True
        ok = (
            moved >= 1
            and forum_hits <= 4
            and ID_ROAD_LO <= last_tid <= ID_ROAD_HI
            and taxed
        )
        lines.append(
            f"clerk roams roads tax +10 0x0C: {'ok' if ok else 'FAIL'} "
            f"moved={moved} forum_hits={forum_hits} last={last_tid:#x} tax={taxed}"
        )
        _relocate_walker(pool, tiles, slot, 21, 21)
        rec = _rec(pool, slot)
        rec[_OFF_STATE] = 3
        rec[_OFF_WAIT] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        rec[_OFF_LINGER] = 0
        _put(pool, slot, rec)
        clock = WalkerClock()
        left = False
        for _ in range(24):
            walkers_tick(tiles, pool, clock=clock)
            live = _rec(pool, slot)
            if live[_OFF_OCCUPIED] == 0:
                break
            tx, ty = _i8(live, _OFF_X), _i8(live, _OFF_Y)
            hid = tiles[_tile_off(tx, ty)]
            if ID_ROAD_LO <= hid <= ID_ROAD_HI:
                left = True
                break
        foff = _tile_off(21, 21)
        ok = (
            left
            and walker_dest_ok(tiles, foff, 1) == 1
            and walker_dest_ok(tiles, foff, 2) == 0
        )
        lines.append(
            f"clerk exits courtyard dest_ok: {'ok' if ok else 'FAIL'} "
            f"left={left} clerk_f={walker_dest_ok(tiles, foff, 1)} "
            f"trader_f={walker_dest_ok(tiles, foff, 2)}"
        )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    # 2×2 market; road only on the south rim (class-1 origin cardinals miss).
    for dy in range(2):
        for dx in range(2):
            off = _tile_off(20 + dx, 20 + dy)
            tiles[off] = 0xFC
            tiles[off + 1] = 0x01
            tiles[off + 5] = dy * 2 + dx
    for rx in (20, 21):
        roff = _tile_off(rx, 22)
        tiles[roff] = 0x52
        tiles[roff + 1] = FLAG_PAD
    nsp = emit_walkers_row(tiles, pool, 20, 3, population=4, kinds="market")
    rec = None
    slot = 0
    for i in range(WALKER_COUNT):
        cand = _rec(pool, i)
        if cand[_OFF_OCCUPIED] and cand[_OFF_TYPE] == 2:
            rec = cand
            slot = i
            break
    nxt = rec[_OFF_NEXT_STATE] if rec is not None else -1
    wx = wy = tid = sid = -1
    if rec is not None:
        wx, wy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
        tid = tiles[_tile_off(wx, wy)]
        sid = rec[_OFF_SPRITE_ID] | (rec[_OFF_SPRITE_ID + 1] << 8)
    base = TYPE_LTLMEN_BASE[2]
    ok = (
        nsp >= 1
        and rec is not None
        and nxt == 4
        and ID_ROAD_LO <= tid <= ID_ROAD_HI
        and base <= sid < base + 27
    )
    lines.append(
        f"market trader type 2 on south road: {'ok' if ok else 'FAIL'} "
        f"spawn={nsp} next={nxt} xy={wx},{wy} id={tid:#x} sprite={sid}"
    )
    if rec is not None:
        rec[_OFF_STATE] = 4
        rec[_OFF_WAIT] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        _put(pool, slot, rec)
        clock = WalkerClock()
        moved = 0
        on_road = True
        for _ in range(40):
            result = walkers_tick(tiles, pool, clock=clock)
            moved += result.stepped
            for i in range(WALKER_COUNT):
                live = _rec(pool, i)
                if live[_OFF_OCCUPIED] == 0 or live[_OFF_TYPE] != 2:
                    continue
                tx, ty = _i8(live, _OFF_X), _i8(live, _OFF_Y)
                hid = tiles[_tile_off(tx, ty)]
                if not (
                    ID_ROAD_LO <= hid <= ID_ROAD_HI
                    or ID_PLAZA_LO <= hid <= ID_PLAZA_HI
                ):
                    on_road = False
        ok = moved >= 1 and on_road
        lines.append(
            f"market trader walks 0x52-0x5C: {'ok' if ok else 'FAIL'} "
            f"moved={moved} on_road={on_road}"
        )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    # 2×2 market west of Palatine; south + west roads. Trader must not
    # roam onto the tan courtyard (0xAE–0xB9).
    for dy in range(2):
        for dx in range(2):
            off = _tile_off(20 + dx, 20 + dy)
            tiles[off] = 0xFC
            tiles[off + 1] = 0x01
            tiles[off + 5] = dy * 2 + dx
    for dy in range(4):
        for dx in range(4):
            off = _tile_off(22 + dx, 20 + dy)
            tiles[off] = 0xB7
            tiles[off + 1] = 0x01
    for x in range(19, 27):
        off = _tile_off(x, 24)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    for y in range(19, 25):
        off = _tile_off(19, y)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    nsp = emit_walkers_row(tiles, pool, 20, 3, population=4, kinds="market")
    rec = None
    slot = 0
    for i in range(WALKER_COUNT):
        cand = _rec(pool, i)
        if cand[_OFF_OCCUPIED] and cand[_OFF_TYPE] == 2:
            rec = cand
            slot = i
            break
    in_forum = False
    moved = 0
    if rec is not None:
        rec[_OFF_STATE] = 4
        rec[_OFF_WAIT] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        _put(pool, slot, rec)
        clock = WalkerClock()
        for _ in range(80):
            result = walkers_tick(tiles, pool, clock=clock)
            moved += result.stepped
            for i in range(WALKER_COUNT):
                live = _rec(pool, i)
                if live[_OFF_OCCUPIED] == 0 or live[_OFF_TYPE] != 2:
                    continue
                tx, ty = _i8(live, _OFF_X), _i8(live, _OFF_Y)
                hid = tiles[_tile_off(tx, ty)]
                if ID_FORUM_LO <= hid <= ID_FORUM_HI:
                    in_forum = True
    ok = nsp >= 1 and rec is not None and moved >= 1 and not in_forum
    lines.append(
        f"trader stays off forum 0xAE-0xB9: {'ok' if ok else 'FAIL'} "
        f"spawn={nsp} moved={moved} in_forum={in_forum}"
    )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for dy in range(4):
        for dx in range(4):
            off = _tile_off(30 + dx, 30 + dy)
            tiles[off] = 0xB7
            tiles[off + 1] = 0x01
    for x in range(29, 35):
        off = _tile_off(x, 34)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    slot = walker_spawn(pool, tiles, 2, 31, 34, pad=0x20)
    if slot:
        _relocate_walker(pool, tiles, slot, 31, 31)
    rec = _rec(pool, slot) if slot else None
    if rec is not None:
        rec[_OFF_STATE] = 4
        rec[_OFF_NEXT_STATE] = 4
        rec[_OFF_WAIT] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        _put(pool, slot, rec)
        walkers_tick(tiles, pool, clock=WalkerClock())
        rec = _rec(pool, slot)
        wx, wy = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
        tid = tiles[_tile_off(wx, wy)]
        ok = (
            rec[_OFF_OCCUPIED] != 0
            and not (ID_FORUM_LO <= tid <= ID_FORUM_HI)
            and (
                ID_ROAD_LO <= tid <= ID_ROAD_HI
                or ID_PLAZA_LO <= tid <= ID_PLAZA_HI
            )
        )
        lines.append(
            f"trader on forum snaps to road: {'ok' if ok else 'FAIL'} "
            f"xy={wx},{wy} id={tid:#x}"
        )
    else:
        lines.append("trader on forum snaps to road: FAIL no spawn")

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for dy in range(2):
        for dx in range(2):
            off = _tile_off(20 + dx, 20 + dy)
            tiles[off] = 0xFC
            tiles[off + 1] = 0x01
            tiles[off + 5] = dy * 2 + dx
    for rx in (20, 21):
        roff = _tile_off(rx, 22)
        tiles[roff] = 0x52
        tiles[roff + 1] = FLAG_PAD
    n1 = emit_walkers_row(tiles, pool, 20, 3, population=4, kinds="market")
    tiles[_tile_off(20, 20) + 6] = 0
    n2 = emit_walkers_row(tiles, pool, 20, 3, population=4, kinds="market")
    walkers_tick(tiles, pool, clock=WalkerClock())
    live2 = [
        s
        for s in range(WALKER_COUNT)
        if pool[s * WALKER_STRIDE + _OFF_OCCUPIED]
        and pool[s * WALKER_STRIDE + _OFF_TYPE] == 2
        and pool[s * WALKER_STRIDE + _OFF_STATE] != 2
    ]
    ok = n1 >= 1 and n2 >= 1 and len(live2) == 1
    lines.append(
        f"one trader per market origin: {'ok' if ok else 'FAIL'} "
        f"n1={n1} n2={n2} live={len(live2)}"
    )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for x in range(10, 14):
        off = _tile_off(x, 10)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    hoff = _tile_off(11, 9)
    tiles[hoff] = 0x83
    tiles[hoff + 1] = 0x01
    tiles[hoff + 13] = 0x80
    moff = _tile_off(10, 10)
    tiles[moff] = 0xFC
    slot = walker_spawn(pool, tiles, 2, 11, 10, pad=0x20)
    rec = _rec(pool, slot)
    rec[_OFF_STATE] = 4
    rec[_OFF_NEXT_STATE] = 4
    rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
    rec[_OFF_WANT_MOVE] = 0
    struct.pack_into("<i", rec, _OFF_HOME, moff)
    _put(pool, slot, rec)
    walkers_tick(tiles, pool, clock=WalkerClock())
    rec = _rec(pool, slot)
    road10 = tiles[_tile_off(11, 10) + 10]
    house10 = tiles[hoff + 10]
    goods = tiles[moff + 9] & _MARKET_PLUS9_GOODS
    ok = (
        rec[_OFF_SCORE_B] >= 1
        and road10 & 0xC0 == 0xC0
        and goods == 0x08
        and road10 & 0x0C == 0x0C
        and house10 & 0x0C == 0x0C
    )
    lines.append(
        f"trader goods + food +10 0x0C: {'ok' if ok else 'FAIL'} "
        f"score_b={rec[_OFF_SCORE_B]} +9={tiles[moff + 9]:#x} "
        f"road={road10:#x} house={house10:#x}"
    )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for x in range(10, 14):
        off = _tile_off(x, 10)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    hoff = _tile_off(11, 9)
    tiles[hoff] = 0x83
    tiles[hoff + 1] = 0x01
    moff = _tile_off(10, 10)
    tiles[moff] = 0xFC
    slot = walker_spawn(pool, tiles, 2, 11, 10, pad=0x20)
    rec = _rec(pool, slot)
    rec[_OFF_STATE] = 4
    rec[_OFF_NEXT_STATE] = 4
    rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
    rec[_OFF_WANT_MOVE] = 0
    struct.pack_into("<i", rec, _OFF_HOME, moff)
    _put(pool, slot, rec)
    walkers_tick(tiles, pool, clock=WalkerClock())
    rec = _rec(pool, slot)
    road10 = tiles[_tile_off(11, 10) + 10]
    ok = (
        rec[_OFF_SCORE_B] == 0
        and tiles[moff + 9] & _MARKET_PLUS9_GOODS == 0
        and road10 & 0xC0 == 0xC0
        and road10 & 0x0C == 0
    )
    lines.append(
        f"empty market no food +10 0x0C: {'ok' if ok else 'FAIL'} "
        f"score_b={rec[_OFF_SCORE_B]} +9={tiles[moff + 9]:#x} road={road10:#x}"
    )

    tiles[moff] = 0xFC
    tiles[moff + 9] = 0x2F  # stock 2 + goods 0xC + usage 3
    stage = restage_market_origin(tiles, moff, wrap4=1)
    ok = (
        tiles[moff] == 0xFF
        and stage == 3
        and tiles[moff + 9] & 0xF0 == 0x20
        and tiles[moff + 9] & 0x0F == 0x0A
    )
    lines.append(
        f"41A4E restage+decay keeps stock: {'ok' if ok else 'FAIL'} "
        f"id={tiles[moff]:#x} stage={stage} +9={tiles[moff + 9]:#x}"
    )
    tiles[moff] = 0xFC
    tiles[moff + 9] = 0x00
    stage = restage_market_origin(tiles, moff, wrap4=0)
    ok = tiles[moff] == 0xFD and stage == 1
    lines.append(
        f"empty market restage 0xFD: {'ok' if ok else 'FAIL'} "
        f"id={tiles[moff]:#x} stage={stage}"
    )

    tiles[moff] = 0xFC
    tiles[moff + 9] = 0x00
    stage = restage_market_origin(tiles, moff, wrap4=1, city_only=True)
    goods = tiles[moff + 9] & _MARKET_PLUS9_GOODS
    ok = goods == _MARKET_PLUS9_GOODS
    lines.append(
        f"City Only 41A4E reseeds goods: {'ok' if ok else 'FAIL'} "
        f"stage={stage} +9={tiles[moff + 9]:#x}"
    )
    tiles[moff + 9] = _MARKET_PLUS9_GOODS
    restage_market_origin(tiles, moff, wrap4=1, city_only=True)
    after = tiles[moff + 9] & _MARKET_PLUS9_GOODS
    ok = after in (4, 8, _MARKET_PLUS9_GOODS)
    lines.append(
        f"City Only goods decay then last: {'ok' if ok else 'FAIL'} "
        f"+9 goods={after:#x}"
    )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for x in range(10, 14):
        off = _tile_off(x, 10)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    hoff = _tile_off(11, 9)
    tiles[hoff] = 0x83
    tiles[hoff + 1] = 0x01
    moff = _tile_off(10, 10)
    tiles[moff] = 0xFC
    seed_city_only_market_stock(tiles, moff)
    slot = walker_spawn(pool, tiles, 2, 11, 10, pad=0x20)
    rec = _rec(pool, slot)
    rec[_OFF_STATE] = 4
    rec[_OFF_NEXT_STATE] = 4
    rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
    rec[_OFF_WANT_MOVE] = 0
    struct.pack_into("<i", rec, _OFF_HOME, moff)
    _put(pool, slot, rec)
    walkers_tick(tiles, pool, clock=WalkerClock())
    road10 = tiles[_tile_off(11, 10) + 10]
    house10 = tiles[hoff + 10]
    ok = (
        tiles[moff + 9] & _MARKET_PLUS9_GOODS
        and road10 & 0x0C == 0x0C
        and house10 & 0x0C == 0x0C
        and road10 & 0xC0 == 0xC0
    )
    lines.append(
        f"City Only seed feeds house +10 0x0C: {'ok' if ok else 'FAIL'} "
        f"+9={tiles[moff + 9]:#x} road={road10:#x} house={house10:#x}"
    )

    foff = _tile_off(12, 12)
    tiles[foff] = 0xFA
    tiles[foff + 9] = 0x50  # stock 5
    pack_home_plus9(tiles, foff, 9, 9)
    ok = tiles[foff + 9] == 0x5F  # stock 5 + usage 3 + goods 0xC
    lines.append(
        f"factory +9 pack keeps hi stock: {'ok' if ok else 'FAIL'} "
        f"+9={tiles[foff + 9]:#x}"
    )

    from app.walkers import slide_walk_frame, walker_draw_ltlmen_index

    clear_walker_slides()
    note_walker_slide(1, 10.0, 10.0, 11.0, 10.0, 2)
    raw = bytearray(WALKER_STRIDE)
    raw[_OFF_OCCUPIED] = 1
    raw[_OFF_TYPE] = 2
    raw[_OFF_FACING] = 2
    _set_i8(raw, _OFF_X, 11)
    _set_i8(raw, _OFF_Y, 10)
    raw[_OFF_WALK_FRAME] = 0
    sid_base = TYPE_LTLMEN_BASE[2]
    struct.pack_into("<h", raw, _OFF_SPRITE_ID, sid_base)
    walking = Walker.unpack(bytes(raw), slot=1)
    advance_walker_slides()
    frame = slide_walk_frame(1, 0)
    idx = walker_draw_ltlmen_index(walking)
    ok = frame >= 1 and idx != sid_base
    lines.append(
        f"slide walk-cycle not idle: {'ok' if ok else 'FAIL'} "
        f"frame={frame} idx={idx} idle={sid_base}"
    )
    clear_walker_slides()

    reset_clock()
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    foff = _tile_off(12, 10)
    tiles[foff] = 0x05
    tiles[foff + _TILE_DRAW] = 0x80
    tiles[foff + 16] = 4
    ok = vigile_sector_has_fire(tiles, 10, 10) and not vigile_sector_has_fire(
        tiles, 40, 40
    )
    lines.append(
        f"vigile 4A397 sector fire: {'ok' if ok else 'FAIL'}"
    )

    rec = bytearray(WALKER_STRIDE)
    struct.pack_into("<i", rec, _OFF_TILE, foff)
    rec[_OFF_HOME_WALKER] = 1
    struct.pack_into("<i", rec, _OFF_HOME, foff)
    ok = vigile_still_on_target(tiles, rec)
    tiles[foff + 16] = 1
    did = vigile_extinguish_here(tiles, rec)
    ok = ok and did and (tiles[foff + _TILE_DRAW] & 0x80) == 0
    lines.append(
        f"vigile 4A716 +16==1 clears bit7: {'ok' if ok else 'FAIL'} "
        f"+3={tiles[foff + _TILE_DRAW]:#x}"
    )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for x in range(10, 14):
        off = _tile_off(x, 10)
        tiles[off] = 0x52
        tiles[off + 1] = FLAG_PAD
    foff = _tile_off(12, 10)
    tiles[foff] = 0x05
    tiles[foff + _TILE_DRAW] = 0x80
    tiles[foff + 16] = 6
    slot = walker_spawn(pool, tiles, 5, 10, 10, pad=0x20)
    rec = _rec(pool, slot) if slot else None
    if rec is not None:
        rec[_OFF_STATE] = 8
        rec[_OFF_NEXT_STATE] = 8
        rec[_OFF_WAIT] = 0
        rec[_OFF_WANT_MOVE] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        _put(pool, slot, rec)
        walkers_tick(tiles, pool, clock=WalkerClock())
        rec = _rec(pool, slot)
        ok = rec[_OFF_OCCUPIED] != 0 and rec[_OFF_STATE] == 9
        lines.append(
            f"vigile state 8→9 on sector fire: {'ok' if ok else 'FAIL'} "
            f"state={rec[_OFF_STATE]}"
        )
        rec[_OFF_STATE] = 9
        rec[_OFF_NEXT_STATE] = 9
        rec[_OFF_WANT_MOVE] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        rec[_OFF_HOME_WALKER] = 0
        struct.pack_into("<i", rec, _OFF_HOME, 0)
        _put(pool, slot, rec)
        walkers_tick(tiles, pool, clock=WalkerClock())
        rec = _rec(pool, slot)
        home = struct.unpack_from("<i", rec, _OFF_HOME)[0]
        ok = (
            rec[_OFF_STATE] == 9
            and rec[_OFF_HOME_WALKER] == 1
            and rec[_OFF_WANT_MOVE] == 1
            and home == foff
        )
        lines.append(
            f"vigile state 9 seeks burning rubble: {'ok' if ok else 'FAIL'} "
            f"home={home} dest={_i8(rec, _OFF_DEST_X)},{_i8(rec, _OFF_DEST_Y)}"
        )
        _relocate_walker(pool, tiles, slot, 12, 10)
        rec = _rec(pool, slot)
        rec[_OFF_STATE] = 9
        rec[_OFF_NEXT_STATE] = 9
        rec[_OFF_WANT_MOVE] = 0
        rec[_OFF_ANIM_FLAGS] = _ANIM_DONE
        rec[_OFF_HOME_WALKER] = 1
        struct.pack_into("<i", rec, _OFF_HOME, foff)
        struct.pack_into("<i", rec, _OFF_TILE, foff)
        tiles[foff + 16] = 1
        tiles[foff + _TILE_DRAW] = 0x80
        _put(pool, slot, rec)
        walkers_tick(tiles, pool, clock=WalkerClock())
        ok = (tiles[foff + _TILE_DRAW] & 0x80) == 0
        lines.append(
            f"vigile state 9 extinguishes: {'ok' if ok else 'FAIL'} "
            f"+3={tiles[foff + _TILE_DRAW]:#x}"
        )
    else:
        lines.append("vigile state 8→9 on sector fire: FAIL no spawn")
        lines.append("vigile state 9 seeks burning rubble: FAIL no spawn")
        lines.append("vigile state 9 extinguishes: FAIL no spawn")

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for dy in range(2):
        for dx in range(2):
            off = _tile_off(20 + dx, 20 + dy)
            tiles[off] = 0xAF
            tiles[off + 1] = 0x01
            tiles[off + 5] = dy * 2 + dx
    road = _tile_off(20, 19)
    tiles[road] = 0x52
    tiles[road + 1] = 0x20
    nsp = emit_walkers_row(
        tiles, pool, 20, 3, population=4, kinds="forum", shutoff=frozenset({"forum"})
    )
    wait = tiles[_tile_off(20, 20) + 6] & 0x0F
    ok = nsp == 0 and wait > 0
    lines.append(
        f"understaffed forum +6 wait no clerk: {'ok' if ok else 'FAIL'} "
        f"spawn={nsp} wait={wait}"
    )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for dy in range(3):
        for dx in range(3):
            off = _tile_off(20 + dx, 20 + dy)
            tiles[off] = 0xFA
            tiles[off + 1] = 0x01
            tiles[off + 5] = dy * 3 + dx
    tiles[_tile_off(20, 20) + 19] = 1
    tiles[_tile_off(20, 23)] = 0x52
    tiles[_tile_off(20, 23) + 1] = 0x20
    nsp = emit_walkers_row(
        tiles, pool, 20, 4, population=4, kinds="market", shutoff=frozenset({"factory"})
    )
    stock = (tiles[_tile_off(20, 20) + 9] & 0xF0) >> 4
    wait = tiles[_tile_off(20, 20) + 6] & 0x0F
    ok = nsp == 0 and wait > 0 and stock == 0
    lines.append(
        f"understaffed factory leftover no worker: {'ok' if ok else 'FAIL'} "
        f"spawn={nsp} wait={wait} stock={stock}"
    )

    reset_clock()
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    for dy in range(2):
        for dx in range(2):
            off = _tile_off(20 + dx, 20 + dy)
            tiles[off] = 0xAF
            tiles[off + 1] = 0x01
            tiles[off + 5] = dy * 2 + dx
    road = _tile_off(20, 19)
    tiles[road] = 0x52
    tiles[road + 1] = 0x20
    walkers: list[Walker] = []
    try:
        nsp = emit_walkers(
            tiles, walkers, 20, 3, population=4, kinds="forum", city_only=True
        )
    except TypeError as exc:
        lines.append(f"emit_walkers city_only: FAIL {exc}")
    else:
        live = [w for w in walkers if getattr(w, "occupied", 0)]
        tid = -1
        if live:
            tid = tiles[_tile_off(live[0].x, live[0].y)]
        trader_on_forum = any(
            w.type == 2 and _is_forum_floor(tiles[_tile_off(w.x, w.y)])
            for w in live
        )
        ok = (
            nsp >= 1
            and live
            and live[0].type == TYPE_CLERK
            and ID_ROAD_LO <= tid <= ID_ROAD_HI
            and not trader_on_forum
        )
        lines.append(
            f"emit_walkers city_only clerk on road: {'ok' if ok else 'FAIL'} "
            f"spawn={nsp} type={live[0].type if live else 0} id={tid:#x}"
        )

    reset_clock()
    pool = bytearray(WALKER_BYTES)
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    hoff = _tile_off(10, 10)
    tiles[hoff] = 0x82
    tiles[hoff + 1] = 0x01
    tiles[hoff + 11] = 0x0F
    class _St:
        unrest_rng = 1
        unrest_add = 2
        rioters_spawned = 0

    st = _St()
    nsp = unrest_spawn_rows(tiles, pool, 10, 1, st)
    rec = _rec(pool, 1) if nsp else bytearray(WALKER_STRIDE)
    ok = (
        nsp == 1
        and tiles[hoff] == 0x05
        and (tiles[hoff + 3] & 0x80) == 0
        and rec[_OFF_TYPE] == TYPE_RIOTER
        and rec[_OFF_STATE] == 1
        and rec[_OFF_NEXT_STATE] == 0x0B
        and rec[_OFF_WAIT] == 0x14
        and st.rioters_spawned == 1
    )
    lines.append(
        f"rioter spawn type 7 next=0x0B rubble: {'ok' if ok else 'FAIL'} "
        f"n={nsp} id={tiles[hoff]:#x} type={rec[_OFF_TYPE]} "
        f"st={rec[_OFF_STATE]} nxt={rec[_OFF_NEXT_STATE]}"
    )

    if nsp:
        for _ in range(22):
            walkers_tick(tiles, pool)
        rec = _rec(pool, 1)
        ok = rec[_OFF_OCCUPIED] == 1 and rec[_OFF_TYPE] == TYPE_RIOTER and rec[_OFF_STATE] in (
            11,
            12,
        )
        lines.append(
            f"rioter roam states 11/12: {'ok' if ok else 'FAIL'} "
            f"state={rec[_OFF_STATE]} latch7={_CLOCK.latch7}"
        )
    else:
        lines.append("FAIL  rioter roam skipped (no spawn)")

    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    hoff = _tile_off(10, 10)
    tiles[hoff] = 0x82
    tiles[hoff + 1] = 0x01
    tiles[hoff + 10] = 0x30
    tiles[hoff + 11] = 0x0F
    st = _St()
    st.unrest_rng = 1
    st.unrest_add = 2
    nsp = unrest_spawn_rows(tiles, bytearray(WALKER_BYTES), 10, 1, st)
    ok = nsp == 0 and tiles[hoff] == 0x82 and (tiles[hoff + 11] & 0x0F) == 0x0F
    lines.append(
        f"prefect +10 0x30 holds unrest <=15: {'ok' if ok else 'FAIL'} "
        f"n={nsp} nibble={tiles[hoff + 11] & 0x0F}"
    )

    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    hoff = _tile_off(10, 10)
    tiles[hoff] = 0x9E
    tiles[hoff + 1] = 0x01
    tiles[hoff + 11] = 0x0F
    st = _St()
    st.unrest_rng = 1
    st.unrest_add = 2
    nsp = unrest_spawn_rows(tiles, bytearray(WALKER_BYTES), 10, 1, st)
    ok = nsp == 0 and tiles[hoff] == 0x9E
    lines.append(
        f"villa 0x9E does not spawn rioter: {'ok' if ok else 'FAIL'} n={nsp}"
    )

    reset_clock()
    tiles = bytearray(MAP_W * MAP_H * TILE_BYTES)
    peak = _tile_off(40, 40)
    tiles[peak + 15] = 40
    pool = bytearray(WALKER_BYTES)

    class _Inv:
        city_only = 1
        skill = 2
        invade_months = 48
        invade_rng = 0x20
        stamp_clock = 1
        attack_spawned = 0

    nsp = city_only_try_invasion(_Inv(), tiles, pool, years_played=8)
    rec = _rec(pool, 1) if nsp else bytearray(WALKER_STRIDE)
    ok = (
        nsp == 1
        and rec[_OFF_TYPE] == TYPE_ENEMY
        and rec[_OFF_STATE] == 1
        and rec[_OFF_NEXT_STATE] == 5
        and rec[_OFF_WAIT] == 0x14
        and rec[_OFF_DEST_X] == 40
        and rec[_OFF_DEST_Y] == 40
        and _Inv.city_only == 1
    )
    xy = (_i8(rec, _OFF_X), _i8(rec, _OFF_Y)) if nsp else (-1, -1)
    edge = xy[0] in (0, 79) or xy[1] in (0, 79)
    lines.append(
        f"City Only type 3 from edge toward +15: {'ok' if ok and edge else 'FAIL'} "
        f"n={nsp} xy={xy} dest={rec[_OFF_DEST_X]},{rec[_OFF_DEST_Y]} "
        f"st={rec[_OFF_STATE]} nxt={rec[_OFF_NEXT_STATE]}"
    )

    career = _Inv()
    career.city_only = 0
    nsp = city_only_try_invasion(career, tiles, bytearray(WALKER_BYTES), years_played=20)
    lines.append(
        f"Career skips 0x52828: {'ok' if nsp == 0 else 'FAIL'} n={nsp}"
    )

    early = _Inv()
    early.invade_months = 0
    nsp = city_only_try_invasion(early, tiles, bytearray(WALKER_BYTES), years_played=2)
    lines.append(
        f"year gate 8 > years: {'ok' if nsp == 0 else 'FAIL'} n={nsp}"
    )
    return lines
