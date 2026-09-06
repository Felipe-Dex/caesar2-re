"""Host stand-in for walkers_tick 0x459D0.

One pulse: ++mod64 wrap 64, clamp type-7/type-3 latches, then each live
SavChunk-8 slot (201 × 58) runs walker_type_fn → walker_state_fn →
walker_set_sprite → life_phase. Movement is walker_anim_roam 0x47EFA /
walker_anim_path 0x48084 → walker_step 0x488DC (tile[+7]/[+8]).

city_sim_phase 0x3F60C lives in app/city_sim.py (called before this).
Not implemented here: actors26_tick 0x45A7A,
state-9 seek helpers, path-fail helpers. See findings/app_tick.md.
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
# Clerks (type 1) also use forum interiors 0xAE–0xB9 (no FLAG_PAD).
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


@dataclass
class WalkerClock:
    """Persists across Space/T pulses (sim_tick_mod64 0x117B1C)."""

    mod64: int = 0
    latch7: int = 0  # [0x10266C]
    latch3: int = 0  # [0x102674]
    rng: int = 1
    # SavChunks 20/21 at [0x10262C]/[0x102628] — not loaded; keep record dest
    rally_ok: bool = False
    rally_x: int = 0
    rally_y: int = 0


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
    Aqueduct is an elevated pipe — not a patrol surface even when +1 has
    FLAG_PAD (host T/cross 0xD5/0xD6). Residual grass+PAD is also out.
    ``type_id is None`` is city pavement only (no forum) so a missed type
    cannot reopen the courtyard to traders.
    """
    if off < 0 or off + TILE_BYTES > len(tiles):
        return False
    tid = tiles[off]
    flags = tiles[off + _TILE_FLAGS]
    if is_aqueduct_id(tid):
        return False
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


def walker_pick_pad_facing(
    tiles: bytearray,
    x: int,
    y: int,
    facing: int,
    rng: int,
    type_id: int | None = None,
) -> int:
    """walker_pick_pad_facing 0x48C9F — cardinal pads; 8 = stuck."""
    opposite = (facing + 4) & 7
    pads: dict[int, tuple[int, int]] = {}
    for f, (dx, dy) in ((0, (0, -1)), (2, (1, 0)), (4, (0, 1)), (6, (-1, 0))):
        nx, ny = x + dx, y + dy
        if not _in_map(nx, ny):
            continue
        off = _tile_off(nx, ny)
        if off + TILE_BYTES > len(tiles):
            continue
        if is_walker_road(tiles, off, type_id):
            pads[f] = (tiles[off + _TILE_SLOT0], tiles[off + _TILE_SLOT1])
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
) -> tuple[int, int] | None:
    """Prefer a road/plaza with a walkable neighbour, else any walkable pad."""
    ranked: list[tuple[int, int, int, int, int]] = []
    for ny in range(max(0, y - radius), min(MAP_H, y + radius + 1)):
        for nx in range(max(0, x - radius), min(MAP_W, x + radius + 1)):
            off = _tile_off(nx, ny)
            if not is_walker_road(tiles, off, type_id):
                continue
            tid = tiles[off]
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
    """Move a clerk off a dead-end forum floor onto plaza / road.

    Traders (and other non-clerks) already on 0xAE–0xB9 snap to the
    nearest city road / plaza — they may not stay on the courtyard.
    """
    rec = _rec(pool, slot)
    typ = rec[_OFF_TYPE]
    x, y = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    here = _tile_off(x, y)
    if is_walker_road(tiles, here, typ) and _pad_degree(tiles, x, y, typ) > 0:
        tid = tiles[here] if here < len(tiles) else 0
        if ID_ROAD_LO <= tid <= ID_ROAD_HI or ID_PLAZA_LO <= tid <= ID_PLAZA_HI:
            return
        # Clerk on forum with a road/plaza neighbour — step dest onto that pad.
        found = _find_connected_pad(tiles, x, y, radius=2, type_id=typ)
        if found and found != (x, y):
            fx, fy = found
            ft = tiles[_tile_off(fx, fy)]
            if ID_FORUM_LO <= ft <= ID_FORUM_HI:
                return
            _relocate_walker(pool, tiles, slot, fx, fy)
        return
    found = _find_connected_pad(tiles, x, y, radius=6, type_id=typ)
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
    """Last clerk fallback: plaza 0x7C then a forum platform tile."""
    found = _find_connected_pad(
        tiles, x + size // 2, y + size // 2, radius=size + 2, type_id=type_id
    )
    if found and walker_spawn(
        pool, tiles, type_id, found[0], found[1], pad=0x20, rng=rng
    ):
        return 1
    for dy in range(size):
        for dx in range(size):
            if walker_spawn(
                pool, tiles, type_id, x + dx, y + dy, pad=0x20, rng=rng
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
) -> int:
    """Spawn from civic buildings onto adjacent roads. Mutates walkers."""
    global LAST_EMIT_NOTE
    if walkers is None:
        LAST_EMIT_NOTE = "skip walkers=None"
        return 0
    if population < 2:
        LAST_EMIT_NOTE = f"skip pop={population}<2"
        _path_log(f"walker emit skip pop={population}<2")
        return 0
    pool = _pool_from(walkers)
    spawned = emit_walkers_row(
        tiles, pool, y0, n, population=population, rng=rng, kinds=kinds
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
) -> int:
    """Forum 0xAE–0xB9, prefecture 0xE3, barracks 0xE4, market 0xFC–0xFF.

    ``kinds`` is the city_sim band: forum / tower / security / market.
    None keeps the old combined scan (tests).
    """
    global LAST_EMIT_NOTE
    spawned = 0
    civic = 0
    waiting = 0
    noroad = 0
    markets = 0
    if population < 2:
        LAST_EMIT_NOTE = f"skip pop={population}<2"
        return 0
    want_forum = kinds in (None, "civic", "forum")
    want_tower = kinds in (None, "civic", "tower")
    want_security = kinds in (None, "civic", "security")
    want_market = kinds in (None, "civic", "market")
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
                # retry class 4 (DAT_00094FE5[0xFC]=4 → 2×2 rim). No
                # factory-stock gate — 0x41A4E only restages the sprite.
                typ, nxt, cls, tries = 2, 4, 4, 8
                size = 2
            else:
                continue
            civic += 1
            if typ == 2:
                markets += 1
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
        f"y0={y0} n={n} kinds={kinds or 'civic'}"
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


def walker_housing_scan(rec: bytearray, tiles: bytearray, *, factory_bit: bool) -> None:
    """FUN_0004a7ff 0x4A7FF. EAX=1; EDX=1 factory +13&0x80, EDX=0 market +13&0x40.

    score_a += houses 0x82–0xA1 in Chebyshev r=1, then −1 decay, cap 100.
    score_b += the +13 mask bit (0x80 once hits the cap). State 4 packs
    both into home[+9] when home is a market; state 10 when home is 0xFA.
    """
    x, y = _i8(rec, _OFF_X), _i8(rec, _OFF_Y)
    houses = 0
    bits = 0
    mask = 0x80 if factory_bit else 0x40
    for ny in range(max(0, y - 1), min(MAP_H, y + 2)):
        for nx in range(max(0, x - 1), min(MAP_W, x + 2)):
            off = _tile_off(nx, ny)
            if off + 13 >= len(tiles):
                continue
            tid = tiles[off]
            if 0x82 <= tid <= 0xA1:
                houses += 1
            bits += tiles[off + 13] & mask
    rec[_OFF_SCORE_A] = min(100, max(0, rec[_OFF_SCORE_A] - 1) + houses)
    if bits:
        rec[_OFF_SCORE_B] = min(100, rec[_OFF_SCORE_B] + min(bits, 100))
    home = struct.unpack_from("<i", rec, _OFF_HOME)[0]
    if home < 0 or home + 9 >= len(tiles):
        return
    hid = tiles[home]
    typ = rec[_OFF_TYPE]
    if (typ == 2 and 0xFC <= hid <= 0xFF) or (typ == 6 and hid == 0xFA):
        tiles[home + 9] = ((rec[_OFF_SCORE_B] >> 3) << 4) | (rec[_OFF_SCORE_A] >> 3)


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
    facing = walker_pick_pad_facing(
        tiles,
        _i8(rec, _OFF_X),
        _i8(rec, _OFF_Y),
        rec[_OFF_FACING],
        clock.rng,
        rec[_OFF_TYPE],
    )
    clock.rng = (clock.rng + 1) & 0x7FFF
    if facing >= 8:
        rec[_OFF_STATE] = 2
        if wait_on_stuck:
            rec[_OFF_WAIT] = wait_on_stuck
        _path_log(
            f"walker path stuck  slot={slot}  type={rec[_OFF_TYPE]}  "
            f"xy={_i8(rec, _OFF_X)},{_i8(rec, _OFF_Y)}  no road neighbour"
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
        _roam_then_pick(
            pool,
            tiles,
            slot,
            clock,
            or_bits=0xC0,
            or_r=3,
            wait_on_stuck=0,
            housing=True,
            factory_bit=True,
        )
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
        # FUN_0004a397 → state 9 (fire/building seek) — stub: stay in 8
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
        # Seek helpers 0x4A716 / 0x4A76D / 0x4A397 / 0x4A57F unread.
        # Keep dest; still walk if want_move + dest are set.
        rec[_OFF_NEXT_STATE] = 9
        _put(pool, slot, rec)
        if walker_anim_path(pool, tiles, slot) == 0:
            return
        rec = _rec(pool, slot)
        if rec[_OFF_OCCUPIED] == 0:
            return
        if rec[_OFF_ANIM_FLAGS] & _ANIM_FAIL:
            rec[_OFF_STATE] = 9
            rec[_OFF_ANIM_FLAGS] &= ~_ANIM_FAIL
        # Do not free on unread seek fail — keep last heading
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
    grass = _tile_off(12, 10)
    tiles[grass + _TILE_FLAGS] = FLAG_PAD
    bridge = _tile_off(13, 10)
    tiles[bridge] = 0x4E
    tiles[bridge + _TILE_FLAGS] = FLAG_RIVER | FLAG_PAD
    empty = _tile_off(14, 10)

    ok = (
        walker_dest_ok(tiles, road) == 1
        and walker_dest_ok(tiles, aq) == 0
        and walker_dest_ok(tiles, grass) == 0
        and walker_dest_ok(tiles, bridge) == 1
        and walker_dest_ok(tiles, empty) == 2
    )
    lines.append(
        f"dest_ok road/bridge vs aqueduct/grass-pad: {'ok' if ok else 'FAIL'} "
        f"r={walker_dest_ok(tiles, road)} aq={walker_dest_ok(tiles, aq)} "
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
        and (ID_PLAZA_LO <= tid <= ID_PLAZA_HI or ID_FORUM_LO <= tid <= ID_FORUM_HI)
    )
    lines.append(
        f"clerk pad plaza/forum next=3: {'ok' if ok else 'FAIL'} "
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
    cov = tiles[_tile_off(11, 10) + 10] & 0xC0
    ok = rec[_OFF_SCORE_A] >= 1 and cov == 0xC0
    lines.append(
        f"trader 4a7ff + +10 0xC0: {'ok' if ok else 'FAIL'} "
        f"score_a={rec[_OFF_SCORE_A]} cov={cov:#x}"
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
    return lines
