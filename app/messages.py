"""City Only advisor / event banners — FUN_00058c87 stand-in.

EXE: EAX = official C2.ENG slot + 1, 16-deep queue. Title is the official
string; body is the next packed NUL ([slot]+1). Slots below 79 are
confirm-pack / status-bar toasts: red HUD line + SFX, not a talking-head.
Official C2.ENG [7]+14 is ``Need More Plebs!!!`` (confirm title, not the
bar). [35]+26 ``Idle Plebs`` is the Forum labor-row label ([36]+19), not
a HUD toast. The red bar the original shouts — same phrase as unused.wav
``0x90448`` — is ``Plebs are needed!``. Fire [81] only after a real 69A37
housing ignite (timer 10), not leftover +3 bit7 / +11 0x30.

City Only only. Career banners (Emperor letters [115]+, invasion [82]/[90–95],
cohorts, Empire Expands, Stern Warning) stay skipped. C2.ENG [60] is the
Query structure pack (title “NO Land Value”); [60]+4 “NO Water Supply” is
overlay text, not a 58c87 city-map banner.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.city_map import MAP_H, MAP_W, TILE_STRIDE
from app.unlocks import POP_UNLOCK

# FUN_00058c87 depth.
QUEUE_CAP = 16
DRAW_FIRE = 0x80
ID_HOUSING_LO = 0x82
ID_HOUSING_HI = 0xA1
# Confirm-pack / labor allocate — status bar, not 58c87 (slots < 79).
STATUS_BAR_KEYS = frozenset({"need_plebs", "idle"})
# User-verified HUD + unused.wav cue. C2.ENG [7]+14 is the confirm title.
NEED_PLEBS_HUD = "Plebs are needed!"
# Shrine / Temple / Basilica origins — Hail / Stolen copy.
TEMPLE_LO, TEMPLE_HI = 0xA2, 0xAC

# Peak pop → flyout name (unlocks.py). Shown after [114]+1.
UNLOCK_LABEL: dict[int, str] = {
    400: "Janiculan",
    800: "Odeum",
    1200: "Library",
    1800: "Palatine",
    2400: "Coliseum",
    4800: "C.Maximus",
}

# First-time population banners [103]…[111].
POP_MILESTONE: tuple[tuple[int, int], ...] = (
    (200, 103),
    (500, 104),
    (1000, 105),
    (2000, 106),
    (5000, 107),
    (10000, 108),
    (20000, 109),
    (30000, 110),
    (40000, 111),
)

_FB = {
    7: {11: "Click to Continue", 14: "Need More Plebs!!!"},
    35: {26: "Idle Plebs"},
    78: {0: "Right Click to remove this message."},
    79: {
        0: "Hail",
        1: "It's time to build your city!  Remember that Temples guard the precious Denarii in your treasury.",
    },
    81: {
        0: "Fire Alert!",
        1: "A fire has broken out somewhere in the city! It will quickly spread to adjacent buildings, unless contained or put out by vigiles.",
    },
    84: {
        0: "Services Cut",
        1: "Due to a lack of Denarii spent on pleb welfare, the number of pleb groups has fallen back such that for the first time, services to the city have had to be lessened.",
    },
    88: {
        0: "Stolen!",
        1: "Thieves have run off with much of your treasury.  Leaving your Denarii lying around on the floor of the Forum has proven to be a bad idea.",
    },
    97: {
        0: "No Denarii!",
        1: "You have exhausted the funds in your treasury.",
    },
    100: {
        0: "Insufficient Plebs",
        1: "The Plebeian Tribune reports that you do not have enough able-bodied plebs available to support construction activities.",
    },
    103: {0: "Good Going!", 1: "Your city population has reached 200 for the first time in its history."},
    104: {0: "Well Done!", 1: "Your city population has reached 500 for the first time in its history."},
    105: {0: "Congratulations!", 1: "Your city population has reached 1,000 for the first time in its history."},
    106: {0: "Congratulations!", 1: "Your city population has reached 2,000 for the first time in its history."},
    107: {0: "Congratulations!", 1: "Your city population has reached 5,000 for the first time in its history!"},
    108: {0: "Excellent!", 1: "Your city population has reached 10,000 for the first time in its history!"},
    109: {0: "Incredible!", 1: "Your city population has grown to 20,000 people for the first time in its history!"},
    110: {0: "Unbelievable!", 1: "Your city population has grown to 30,000 people for the first time in its history!"},
    111: {0: "Astounding!", 1: "Your city population has grown to 40,000 people for the first time in its history!"},
    114: {
        0: "New Structure Available",
        1: "The civil-engineering capacity of your city has risen high enough to allow you to build this new structure!",
    },
}


@dataclass(frozen=True)
class AdvisorMessage:
    """One 58c87 / confirm-pack line. Click or right-click dismisses."""

    key: str
    title: str
    body: str
    slot: int  # official C2.ENG (EAX − 1). 7 = confirm pack.
    dismiss: str


@dataclass
class MessageWatch:
    pending: list[AdvisorMessage] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)
    peak: int = 0
    pop: int = 0
    construction_short: bool = False
    idle_short: bool = False
    on_fire: bool = False
    broke: bool = False
    hail_done: bool = False
    last_ready: int = -1
    last_staffed: tuple[bool, ...] | None = None
    status_line: str = ""
    status_alert: bool = False
    status_sfx: str = ""


def _eng(eng, slot: int, skip: int, fallback: str) -> str:
    if eng is not None:
        got = eng.skip(slot, skip)
        if got:
            return got.rstrip()
    return fallback


def _line(eng, slot: int, skip: int) -> str:
    fb = _FB.get(slot, {}).get(skip, "")
    return _eng(eng, slot, skip, fb)


def ensure_watch(sim) -> MessageWatch:
    watch = getattr(sim, "msg_watch", None)
    if not isinstance(watch, MessageWatch):
        watch = MessageWatch()
        sim.msg_watch = watch
    return watch


def enqueue(sim, msg: AdvisorMessage) -> bool:
    watch = ensure_watch(sim)
    if msg.key in watch.seen:
        return False
    if any(item.key == msg.key for item in watch.pending):
        return False
    if len(watch.pending) >= QUEUE_CAP:
        return False
    watch.seen.add(msg.key)
    watch.pending.append(msg)
    return True


def pop_message(sim) -> AdvisorMessage | None:
    watch = ensure_watch(sim)
    if not watch.pending:
        return None
    return watch.pending.pop(0)


def pending_count(sim) -> int:
    return len(ensure_watch(sim).pending)


def post_labor_status(sim, key: str, eng=None) -> str:
    """Labor-short toast: red status bar + unused.wav, no 58c87 queue.

    Both the idle=0 short-row case and the leftover-idle + short-row case
    use the HUD line (not C2.ENG [7]+14 / [35]+26). ``eng`` is accepted
    so Forum allocate stays call-compatible.
    """
    _ = eng
    watch = ensure_watch(sim)
    watch.status_line = NEED_PLEBS_HUD
    watch.status_alert = True
    watch.status_sfx = "need_plebs"
    return NEED_PLEBS_HUD


def peek_status(sim) -> str:
    return ensure_watch(sim).status_line


def take_status_sfx(sim) -> str:
    """Pop the pending labor SFX event (``need_plebs`` → unused.wav), or ``""``."""
    watch = ensure_watch(sim)
    key = watch.status_sfx
    watch.status_sfx = ""
    return key


def is_status_bar_key(key: str) -> bool:
    return key in STATUS_BAR_KEYS


def seed_watch_from_city(sim, tiles: bytearray) -> MessageWatch:
    """After a successful SAV load, latch edges so scan does not dump.

    ``seen`` / peak / Hail / fire / labor / theft live in RAM only — not
    in the file. Treating the deserialized city as rising edges re-fires
    Hail, pop milestones, unlocks, Fire Alert, labor status-bar toasts,
    Stolen, and No Denarii. Original C2 does not dump the 58c87 queue
    on F4. Hail stays New Game / new-map City Only.
    """
    watch = ensure_watch(sim)
    watch.pending.clear()
    watch.status_line = ""
    watch.status_alert = False
    watch.status_sfx = ""
    if not getattr(sim, "city_only", 0):
        return watch

    from app.unlocks import note_population, peak_population

    pop = int(getattr(sim, "population", 0))
    note_population(sim, pop)
    peak = peak_population(sim)
    _houses, temples, fires, _ = _city_counts(tiles)
    staffed = _staffed(sim)
    ready = max(0, int(getattr(sim, "plebs_ready", 0)))
    need_more, idle_short = _labor_toasts(sim)
    treas = int(getattr(sim, "treasury", 0))

    watch.hail_done = True
    watch.seen.add("hail")
    watch.peak = peak
    watch.pop = pop
    for gate in UNLOCK_LABEL:
        if gate <= peak:
            watch.seen.add(f"unlock:{gate}")
    for thresh, _slot in POP_MILESTONE:
        if thresh <= pop:
            watch.seen.add(f"pop:{thresh}")

    watch.on_fire = fires > 0
    if fires > 0:
        watch.seen.add("fire")
    watch.construction_short = need_more
    if need_more:
        watch.seen.add("need_plebs")
    watch.idle_short = idle_short
    if idle_short:
        watch.seen.add("idle")
    watch.last_ready = ready
    watch.last_staffed = staffed
    if temples == 0 and pop > 0:
        watch.seen.add("theft")
    watch.broke = treas < 0
    if treas < 0:
        watch.seen.add("broke")
    return watch


def _make(eng, key: str, slot: int, *, extra: str = "") -> AdvisorMessage:
    title = _line(eng, slot, 0)
    if slot == 7:
        title = _line(eng, 7, 14)
    body = _line(eng, slot, 1)
    if extra:
        body = f"{body}  {extra}".rstrip()
    dismiss = _line(eng, 78, 0)
    return AdvisorMessage(
        key=key, title=title, body=body, slot=slot, dismiss=dismiss
    )


def _off(x: int, y: int) -> int:
    return y * MAP_W * TILE_STRIDE + x * TILE_STRIDE


def _is_burning(tid: int, draw: int, timer: int) -> bool:
    """Real ignite leftover: housing/rubble +3 bit7 and +16 countdown.

    +3 ``0x80`` is also prefecture, aqueduct-over-road, and stamp leftovers
    on ``0x9E–0xA1`` villas — those have timer 0 and are not a fire.
    """
    if not (draw & DRAW_FIRE) or timer == 0:
        return False
    if tid < 8:
        return True
    return ID_HOUSING_LO <= tid <= ID_HOUSING_HI


def _city_counts(tiles: bytearray) -> tuple[int, int, int, int]:
    """houses, temples, fires, max housing id."""
    houses = temples = fires = max_id = 0
    need = MAP_W * MAP_H * TILE_STRIDE
    if len(tiles) < need:
        return 0, 0, 0, 0
    for y in range(MAP_H):
        for x in range(MAP_W):
            off = _off(x, y)
            tid = tiles[off]
            if _is_burning(tid, tiles[off + 3], tiles[off + 16]):
                fires += 1
            if tiles[off + 5] & 0xF:
                continue
            if ID_HOUSING_LO <= tid <= ID_HOUSING_HI:
                houses += 1
                if tid > max_id:
                    max_id = tid
            elif TEMPLE_LO <= tid <= TEMPLE_HI:
                temples += 1
    return houses, temples, fires, max_id


def _staffed(sim) -> tuple[bool, ...]:
    from app.forum import CREW, LABOR_CONSTRUCTION, LABOR_ROWS, labor_row_staffed

    asg = list(getattr(sim, "labor_assigned", None) or [0] * LABOR_ROWS)
    need = list(getattr(sim, "labor_need", None) or [0] * LABOR_ROWS)
    while len(asg) < LABOR_ROWS:
        asg.append(0)
    while len(need) < LABOR_ROWS:
        need.append(0)
    asg[LABOR_CONSTRUCTION] = CREW
    need[LABOR_CONSTRUCTION] = CREW
    return tuple(labor_row_staffed(asg[i], need[i]) for i in range(LABOR_ROWS))


def _labor_toasts(sim) -> tuple[bool, bool]:
    """Labor-short rising edges: idle=0 vs leftover-idle + short row.

    Construction assigned stays locked at 20. Both edges post the same
    HUD line (``Plebs are needed!``). Idle-only leftover with every row
    at need stays quiet.
    """
    from app.forum import labor_idle_of

    any_short = any(not ok for ok in _staffed(sim))
    if not any_short:
        return False, False
    if labor_idle_of(sim) > 0:
        return False, True
    return True, False


def scan_city_messages(
    sim,
    tiles: bytearray,
    eng=None,
    *,
    hail: bool = False,
    houses_up: int = 0,
    month_wrapped: bool = False,
    fire_ignited: int = 0,
) -> list[str]:
    """Push City Only banners. Career / Emperor packs are not enqueued."""
    fired: list[str] = []
    if not getattr(sim, "city_only", 0):
        return fired
    watch = ensure_watch(sim)
    if month_wrapped:
        from app.forum import refresh_labor_need

        refresh_labor_need(sim, tiles)

    from app.unlocks import peak_population

    pop = int(getattr(sim, "population", 0))
    peak = peak_population(sim)
    _houses, temples, fires, _ = _city_counts(tiles)
    staffed = _staffed(sim)
    ready = max(0, int(getattr(sim, "plebs_ready", 0)))
    need_more, idle_short = _labor_toasts(sim)
    any_short = any(not ok for ok in staffed)
    treas = int(getattr(sim, "treasury", 0))

    if hail and not watch.hail_done:
        watch.hail_done = True
        if enqueue(sim, _make(eng, "hail", 79)):
            fired.append("hail")

    if peak > watch.peak:
        for gate, name in UNLOCK_LABEL.items():
            if watch.peak < gate <= peak:
                extra = name
                if enqueue(sim, _make(eng, f"unlock:{gate}", 114, extra=extra)):
                    fired.append(f"unlock:{name}")
        watch.peak = peak
    if pop > watch.pop:
        for thresh, slot in POP_MILESTONE:
            if watch.pop < thresh <= pop:
                if enqueue(sim, _make(eng, f"pop:{thresh}", slot)):
                    fired.append(f"pop:{thresh}")
        watch.pop = pop

    # [81] only when 69A37 painted a real fire this pass (timer != 0).
    # Leftover +3 bit7 / +11 0x30 / fire_ignited-without-paint stay quiet.
    if fire_ignited > 0 and fires > 0 and not watch.on_fire:
        watch.seen.discard("fire")
        if enqueue(sim, _make(eng, "fire", 81)):
            fired.append("fire")
    watch.on_fire = fires > 0

    if need_more and not watch.construction_short:
        watch.seen.discard("need_plebs")
        post_labor_status(sim, "need_plebs", eng)
        fired.append("need_plebs")
    watch.construction_short = need_more

    if watch.last_ready >= 0 and ready < watch.last_ready and any_short:
        if "services_cut" not in watch.seen:
            if enqueue(sim, _make(eng, "services_cut", 84)):
                fired.append("services_cut")
    if watch.last_ready < 0:
        watch.last_ready = ready
    else:
        watch.last_ready = ready

    if idle_short and not watch.idle_short:
        watch.seen.discard("idle")
        post_labor_status(sim, "idle", eng)
        fired.append("idle")
    watch.idle_short = idle_short

    if (
        month_wrapped
        and treas > 0
        and temples == 0
        and pop > 0
        and "theft" not in watch.seen
    ):
        if enqueue(sim, _make(eng, "theft", 88)):
            fired.append("theft")

    broke = treas < 0
    if broke and not watch.broke:
        watch.seen.discard("broke")
        if enqueue(sim, _make(eng, "broke", 97)):
            fired.append("broke")
    watch.broke = broke

    watch.last_staffed = staffed
    return fired


def selftest() -> list[str]:
    from app.city_sim import SimState
    from app.forum import LABOR_ASSIGNED_INIT, init_city_only_labor

    lines: list[str] = []
    tiles = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    sim = SimState(city_only=1, skill=2, treasury=12000, population=0, pop_peak=0)
    init_city_only_labor(sim)
    got = scan_city_messages(sim, tiles, hail=True)
    if "hail" not in got:
        lines.append(f"FAIL  hail {got}")
    else:
        lines.append("ok    Hail [79] on City Only start")

    career = SimState(city_only=0, population=500, treasury=100)
    career.msg_watch = MessageWatch()
    if scan_city_messages(career, tiles, hail=True):
        lines.append("FAIL  career scan must stay empty")
    else:
        lines.append("ok    Career banners skipped")

    sim = SimState(city_only=1, population=399, pop_peak=399, treasury=100)
    init_city_only_labor(sim)
    off = 10 * MAP_W * TILE_STRIDE + 10 * TILE_STRIDE
    tiles[off] = 0x82
    tiles[off + 5] = 0
    sim.population = 400
    sim.pop_peak = 400
    got = scan_city_messages(sim, tiles)
    if "unlock:Janiculan" not in got:
        lines.append(f"FAIL  janiculan unlock {got}")
    else:
        lines.append("ok    New Structure Available at pop 400")

    sim = SimState(city_only=1, population=199, pop_peak=199, treasury=100)
    init_city_only_labor(sim)
    sim.population = 200
    sim.pop_peak = 200
    got = scan_city_messages(sim, tiles)
    if "pop:200" not in got:
        lines.append(f"FAIL  pop 200 {got}")
    else:
        lines.append("ok    Good Going! at pop 200")

    sim = SimState(city_only=1, population=20, treasury=100, labor_assigned=list(LABOR_ASSIGNED_INIT))
    init_city_only_labor(sim)
    sim.labor_assigned = [20, 0, 0, 0, 0, 0, 0]
    sim.labor_need = [20, 8, 0, 0, 0, 0, 0]
    sim.plebs_ready = 20
    got = scan_city_messages(sim, tiles)
    if "need_plebs" not in got:
        lines.append(f"FAIL  need plebs {got}")
    elif peek_status(sim) != NEED_PLEBS_HUD:
        lines.append(f"FAIL  need plebs status {peek_status(sim)!r}")
    elif any(m.key == "need_plebs" for m in ensure_watch(sim).pending):
        lines.append("FAIL  Plebs are needed! must not enqueue 58c87")
    else:
        lines.append("ok    Plebs are needed! status-bar when a row is short and idle=0")

    sim = SimState(city_only=1, population=20, treasury=100)
    init_city_only_labor(sim)
    sim.labor_assigned = [20, 0, 0, 0, 0, 0, 0]
    sim.labor_need = [20, 8, 0, 0, 0, 0, 0]
    sim.plebs_ready = 42
    got = scan_city_messages(sim, tiles)
    if "idle" not in got:
        lines.append(f"FAIL  idle {got}")
    elif peek_status(sim) != NEED_PLEBS_HUD:
        lines.append(f"FAIL  idle status {peek_status(sim)!r}")
    elif any(m.key == "idle" for m in ensure_watch(sim).pending):
        lines.append("FAIL  leftover-idle short-row must not enqueue 58c87")
    else:
        lines.append("ok    Plebs are needed! status-bar when surplus + a short row")

    sim = SimState(city_only=1, population=20, treasury=100)
    init_city_only_labor(sim)
    sim.labor_assigned = list(LABOR_ASSIGNED_INIT)
    sim.labor_need = [20, 0, 0, 0, 0, 0, 0]
    sim.plebs_ready = 42
    got = scan_city_messages(sim, tiles)
    if "idle" in got or "need_plebs" in got:
        lines.append(f"FAIL  all-staffed leftover idle {got}")
    else:
        lines.append("ok    leftover idle with every row at need stays quiet")

    from app.forum import apply_month_labor

    sim = SimState(city_only=1, population=20, treasury=100, welfare=0, labor_index=5)
    init_city_only_labor(sim)
    sim.welfare = 0
    sim.plebs_ready = 42
    sim.labor_assigned = [20, 12, 4, 4, 0, 0, 0]
    sim.labor_need = [20, 12, 4, 4, 0, 0, 0]
    watch = ensure_watch(sim)
    watch.last_ready = 42
    apply_month_labor(sim)
    sim.labor_need = [20, 12, 4, 4, 0, 0, 0]
    got = scan_city_messages(sim, tiles)
    if "services_cut" not in got:
        lines.append(f"FAIL  services cut {got} ready={sim.plebs_ready}")
    else:
        lines.append("ok    Services Cut after welfare-0 month")

    tiles2 = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    hoff = 12 * MAP_W * TILE_STRIDE + 12 * TILE_STRIDE
    tiles2[hoff] = 0x82
    tiles2[hoff + 5] = 0
    tiles2[hoff + 3] = DRAW_FIRE
    tiles2[hoff + 16] = 10
    sim = SimState(city_only=1, population=8, treasury=100, fire_ignited=1)
    init_city_only_labor(sim)
    got = scan_city_messages(sim, tiles2, fire_ignited=1)
    if "fire" not in got:
        lines.append(f"FAIL  fire {got}")
    else:
        lines.append("ok    Fire Alert! on ignite")

    tiles_flag = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    sim = SimState(city_only=1, population=8, treasury=100)
    init_city_only_labor(sim)
    got = scan_city_messages(sim, tiles_flag, fire_ignited=1)
    if "fire" in got:
        lines.append(f"FAIL  fire_ignited without paint queued [81] {got}")
    else:
        lines.append("ok    fire_ignited without painted fire is not [81]")

    tiles_pf = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    poff = 14 * MAP_W * TILE_STRIDE + 14 * TILE_STRIDE
    tiles_pf[poff] = 0xE3
    tiles_pf[poff + 3] = DRAW_FIRE
    tiles_pf[poff + 5] = 0
    villa = 16 * MAP_W * TILE_STRIDE + 16 * TILE_STRIDE
    tiles_pf[villa] = 0x9E
    tiles_pf[villa + 3] = DRAW_FIRE
    tiles_pf[villa + 5] = 0
    sim = SimState(city_only=1, population=8, treasury=100)
    init_city_only_labor(sim)
    got = scan_city_messages(sim, tiles_pf)
    if "fire" in got:
        lines.append(f"FAIL  prefecture/villa +3 bit7 is not fire {got}")
    else:
        lines.append("ok    prefecture / 0x9E leftover +3 bit7 is not Fire Alert")

    tiles_load = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    tiles_load[hoff] = 0x82
    tiles_load[hoff + 3] = DRAW_FIRE
    tiles_load[hoff + 5] = 0
    tiles_load[hoff + 16] = 10
    sim = SimState(
        city_only=1,
        population=2400,
        pop_peak=2400,
        treasury=500,
        labor_assigned=list(LABOR_ASSIGNED_INIT),
        labor_need=[20, 8, 4, 4, 0, 0, 0],
        plebs_ready=42,
    )
    init_city_only_labor(sim)
    sim.population = 2400
    sim.pop_peak = 2400
    sim.labor_assigned = [20, 0, 4, 4, 0, 0, 0]
    sim.labor_need = [20, 8, 4, 4, 0, 0, 0]
    sim.plebs_ready = 42
    seed_watch_from_city(sim, tiles_load)
    got = scan_city_messages(sim, tiles_load, hail=True, month_wrapped=True)
    if got:
        lines.append(f"FAIL  load seed re-fired {got}")
    else:
        lines.append("ok    Load seed: no Hail / pop / unlock / fire / labor / theft")
    got = scan_city_messages(sim, tiles_load, fire_ignited=1)
    if "fire" in got:
        lines.append(f"FAIL  load re-alerted existing fire {got}")
    else:
        lines.append("ok    Load seed: Fire Alert only on a later new ignite")

    tiles3 = bytearray(MAP_W * MAP_H * TILE_STRIDE)
    sim_fresh = SimState(city_only=1, population=8, treasury=100)
    init_city_only_labor(sim_fresh)
    seed_watch_from_city(sim_fresh, tiles3)
    got = scan_city_messages(sim_fresh, tiles3, fire_ignited=1)
    if "fire" in got:
        lines.append(f"FAIL  load seed fire_ignited without paint {got}")
    else:
        lines.append("ok    load seed: fire_ignited without paint stays quiet")
    tiles3[hoff] = 0x82
    tiles3[hoff + 3] = DRAW_FIRE
    tiles3[hoff + 5] = 0
    tiles3[hoff + 16] = 10
    got = scan_city_messages(sim_fresh, tiles3, fire_ignited=1)
    if "fire" not in got:
        lines.append(f"FAIL  new ignite after load seed {got}")
    else:
        lines.append("ok    Fire Alert! on new painted ignite after load")

    tiles3[hoff] = 0x82
    tiles3[hoff + 5] = 0
    sim = SimState(city_only=1, population=8, treasury=100)
    init_city_only_labor(sim)
    got = scan_city_messages(sim, tiles3)
    if "water" in got:
        lines.append(f"FAIL  Query [60]+4 must not enqueue {got}")
    else:
        lines.append("ok    [60] Query pack is not a 58c87 banner")

    sim = SimState(city_only=1, population=20, treasury=500)
    init_city_only_labor(sim)
    got = scan_city_messages(sim, tiles3, month_wrapped=True)
    if "theft" not in got:
        lines.append(f"FAIL  theft {got}")
    elif "hail" in got or "fire" in got:
        lines.append(f"FAIL  year wrap dumped Hail/Fire {got}")
    else:
        lines.append("ok    Stolen! on wrap with gold and no temples")
    wrap_sim = SimState(city_only=1, population=0, treasury=12000, month=0)
    init_city_only_labor(wrap_sim)
    got = scan_city_messages(wrap_sim, tiles3, hail=False, month_wrapped=True)
    if "hail" in got or "fire" in got:
        lines.append(f"FAIL  Dec wrap must not Hail/Fire {got}")
    else:
        lines.append("ok    year wrap does not Hail or dump Fire Alert")

    sim = SimState(city_only=1, population=20, treasury=-3)
    init_city_only_labor(sim)
    got = scan_city_messages(sim, tiles3)
    if "broke" not in got:
        lines.append(f"FAIL  broke {got}")
    else:
        lines.append("ok    No Denarii! when treasury < 0")

    msg = pop_message(sim)
    if msg is None or msg.slot not in (7, 35, 79, 81, 84, 88, 97, 100, 103, 114):
        lines.append(f"FAIL  pop_message {msg}")
    else:
        lines.append("ok    queue pop + click-dismiss fields")

    if "janiculan" not in POP_UNLOCK:
        lines.append("FAIL  unlocks table")
    else:
        lines.append("ok    unlock gates match unlocks.py")
    try:
        from app.assets import load_eng
        from app.config import resolve_game_dir

        game, _why = resolve_game_dir()
        eng = load_eng(game)
    except (OSError, ValueError):
        lines.append("ok    C2.ENG skip (no install)")
        return lines
    if eng.skip(7, 14) != "Need More Plebs!!!":
        lines.append(f"FAIL  [7]+14 {eng.skip(7, 14)!r}")
    elif NEED_PLEBS_HUD != "Plebs are needed!":
        lines.append(f"FAIL  HUD {NEED_PLEBS_HUD!r}")
    elif eng.skip(35, 26) != "Idle Plebs":
        lines.append(f"FAIL  [35]+26 {eng.skip(35, 26)!r}")
    else:
        lines.append("ok    C2.ENG [7]+14 title / [35]+26 Forum row / HUD Plebs are needed!")
    if eng.skip(81, 0) != "Fire Alert!":
        lines.append(f"FAIL  [81] {eng.skip(81, 0)!r}")
    else:
        lines.append("ok    C2.ENG Fire Alert!")
    if eng.skip(114, 0) != "New Structure Available":
        lines.append(f"FAIL  [114] {eng.skip(114, 0)!r}")
    else:
        lines.append("ok    C2.ENG New Structure Available")
    if eng.skip(60, 0) != "NO Land Value" or eng.skip(60, 4) != "NO Water Supply":
        lines.append(f"FAIL  [60] pack {eng.skip(60, 0)!r} +4 {eng.skip(60, 4)!r}")
    else:
        lines.append("ok    C2.ENG [60] is Query pack, not a banner")
    return lines
