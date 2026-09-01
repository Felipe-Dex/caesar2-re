# Ghidra walk — real `walkers_tick` `0x459D0`

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP HTTP `127.0.0.1:8080`, plus Capstone on `ghidra_work/c2_x.bin`). No EXE in git. Continues `findings/ghidra_walkers.md` / `ghidra_sim.md`. **Did not wait for Palatine A/B or Query screenshots.** Host Space/T now calls `app.walker_tick.walkers_tick` (see `findings/app_tick.md`). Not `city_sim_phase`.

**Result:** one real tick increments a 64-phase clock, latches “type 7 / type 3 were alive”, then for each of 201 records dispatches **type 1–7 → state 0–12**. Movement is `walker_anim_roam` / `walker_anim_path` → `walker_step`, which unlinks/relinks **tile[+7]/[+8]**. Types **3 and 7** are the only hunted pair (`walker_find_type3or7` `0x47D1A`). Spawn is now found: **type 3 = barbarian** from a province actor26 hitting tile id `0x92`; **type 7 = rioter** from a housing score overflow in `FUN_00041dd4`. Type stubs at `0x45AFE`+ are still **not** Ghidra functions (gap after `actors26_tick`).

---

## 1. What one real tick does

Called from `view_frame` `0x3CF9A` after `city_sim_phase`, once per sim pulse (1 or 4 catch-up) — **city and province share this pulse** (`findings/view_modes.md`). Body `0x459D0`–`0x45A79` (decompiled).

```
++sim_tick_mod64 [0x117B1C]; if > 0x3F → 0          ; 64-tick life clock
[0x10266C] = (val > 1)                              ; type-7 latch: 2→1, else 0
[0x102674] = (val > 1)                              ; type-3 latch: 2→1, else 0
walker_live_count [0x102664] = 0
for walker_iter [0x1156F8] = 0 .. 200:              ; slot 0 exists; spawn fills 1..200
  rec = walker_pool[0x1107A4] + i*0x3A
  if rec[+0] == 0: skip
  live_count++
  type = rec[+2]
  if type < 1 or type > 7: walker_free(i)           ; 0x2AECB
  else: walker_type_fn[type]()                      ; 0x99D24
```

That is the **whole** walker AI for the pulse. No pathfinding outside the type/state callees. No city evolve / flood (those are `city_sim_phase`).

Each type handler (Capstone; not a Ghidra function):

```
walker_state_fn[rec[+0x10]]()                       ; 0x99D68
walker_set_sprite(base)   ; type 7: t7 helper unless state==12
if sim_tick_mod64 == 0:
  rec[+0x24]++                                      ; life_phase
  if life_phase >= cap: rec[+0x10] = 2              ; free next tick
```

Type 3 also writes `[0x102CB4]=[0x102674]=2`. Type 7 writes `[0x102CB4]=[0x10266C]=2`. The next tick’s clamp turns those **2 → 1**, so states 7/8 see “a barbarian/rioter existed last pulse” (same-pulse if the threat slot is processed first).

Host Space/T now runs this pulse (`app/walker_tick.py`). Gaps in §9 are still stubbed — see `findings/app_tick.md`.

---

## 2. Type table `walker_type_fn` `0x99D24`

Confirmed bytes: `[0]=0x45AFD` (unused), then 1…7 as below. Sprite via `walker_set_sprite` `0x479B8` except type 7.

| Type | VA | Sprite base | Life cap | Typical state (SAV / spawn) | Role (confidence) |
|---:|---|---:|---:|---|---|
| 1 | `0x45AFE` | `0x36` | 18 | 3 | Industry coverage. Emit `0x4118B` ids **0xAE–0xB9**. OR **0x0C** into tile[+10] r=3 |
| 2 | `0x45B53` | `0x1B` | 30 | 4 | Market-ish. Emit `0x41719` ids **0xFC–0xFF**. OR **0xC0**; writes home tile[+9] from scores |
| **3** | `0x45BA8` | `0xA6` | **72** | 5 (after wait) | **Barbarian.** Sets threat latch. Spawn §5. Longest life |
| 4 | `0x45C0E` | `0x6E` | 35 | 6 or 7 | Soldier / escort. `0xBF` if a 3/7 is nearby; also `0xE4` |
| 5 | `0x45C63` | `0x51` | 20 | 8 → 9 | Prefect-ish. Building `0xE3`. Hunts 3/7 or seeks (state 9) |
| 6 | `0x45CB8` | 0 | 30 | 10 | Second emit in `0x41719`. Roam + home **0xFA** goods nibble |
| **7** | `0x45D0A` | `0x89` or **0 if state==12** | 20 | 11 ↔ 12 | **Rioter.** Sets threat latch. Spawn §5. `walker_set_sprite_t7` `0x47A95` unless leaving (state 12) |

C2 menu names for 1/2/4/5/6 are **still not from strings**. 3 = barbarian and 7 = rioter are the user’s labels **plus** spawn sites (province invasion / housing overflow) and `rioters.smk` on disk.

Speed tables (index = type). `walker_anim_*` uses `0x9673E[type]` when `rec[+0x23]==0` (road spawn) and `0x96735[type]` when `+0x23!=0` (building pad). Types 1–7 are **all 2** on road and **all 1** on pad — per-type columns do not differ. Higher value = more ticks per `walk_frame`.

---

## 3. State table `walker_state_fn` `0x99D68`

Entries **0–12** are city walkers. **13–15** (`0x4695F` / `0x46960` / `0x469D4`) are **`actor26_state_fn`** — the tables share `0x99D9C`. Do not treat those as walker AI.

| State | VA | Motion | What |
|---:|---|---|---|
| 0 | `0x45EDC` | — | `RET` |
| **1** | `0x45EDD` | wait | `--rec[+0x0F]`; on 0: copy `+0x0E` → state, clear frame/timer/`want_move`, OR anim bit0, `+0x1E=5` |
| **2** | `0x45F2C` | — | **`jmp walker_free`** |
| **3** | `0x45F38` | `walker_anim_roam(0)` | If step-done: `tile_or_radius` **OR 0x0C → +10, r=3**. Then `walker_pick_pad_facing`; 8 → state 2; else `walker_set_dest` + `want_move=1` |
| **4** | `0x45FE9` | roam | Same + **OR 0xC0**. `FUN_0004a7ff(1)` housing scores. If `home_off` tile[+0] ∈ **0xFC–0xFF**, pack `score_a`/`score_b` into that tile[+9] |
| **5** | `0x46155` | `walker_anim_path(1)` | Barbarian march. `want_move=1`, keep `next_state=5`. Dest refreshed from **`[0x10262C]` / `[0x102628]`** (SavChunks 20/21). `+0x33` is a 3-tick linger |
| **6** | `0x461F5` | `walker_anim_path(2)` | Chase `home_walker` (`+0x2C`). If target live and rng lock matches, dest = target x/y; after 5 follows, reset. If dead: `walker_find_type3or7(x,y,r=10)` or **state 2** |
| **7** | `0x4634B` | roam | **OR 0x30 → +10, r=4**. If `[0x10266C]` or `[0x102674]` ≠ 0, hunt r=10 → **state 6**. Else pad-facing / die |
| **8** | `0x464A3` | roam | **OR 0x30, r=3**. `FUN_0004a397` → **state 9**. Else same hunt as 7 → state 6 |
| **9** | `0x46619` | `walker_anim_path(2)` | `next_state=9`. Seek helpers `0x4A716` / `0x4A76D` / `0x4A397` / `0x4A57F` (fire / building — **not fully read**). Fail → state 2 |
| **10** | `0x4675C` | roam | `FUN_0004a7ff(1)`. If home tile[+0]==**0xFA**, pack scores into +9. Pad-facing / die |
| **11** | `0x468A1` | wait | `--wait`; on 0 → **state 12**, dest = `[0x10262C]`/`[0x102628]`, reset anim, `+0x1E=5` |
| **12** | `0x468FE` | `walker_anim_path(1)` | Walk to that dest; on step-done → **state 11**, wait `0x1E`. Type 7 uses sprite base **0** here |

Roam states share a tail: `walker_pick_pad_facing` `0x48C9F` looks at N/E/S/W neighbors’ **tile[+1] bit 0x20** (pad) and prefers empty +7/+8. Returns facing 0/2/4/6 or **8** (stuck → free). Then `walker_set_dest` `0x48E59` writes dest one tile that way.

---

## 4. Movement (not the host frame bump)

### `walker_anim_roam` `0x47EFA`

If anim bit0 clear: `++anim_timer`; when it exceeds the type-speed byte, reset and `++walk_frame` (0…15); at 16 set bit0 (step done).

If bit0 set and `want_move`: `facing_from_delta` toward dest. `walker_can_step`:

- result ∈ {1,2} (and roam-ok): `on_road=1` if dest was pad, clear bit0, set facing, `walk_frame=1`, **`walker_step`**
- else: `bump=1`, `wait=0x14`, facing **+4 & 7** (turn around)
- facing ≥ 8: `want_move=0`, anim bit1 (fail)

### `walker_anim_path` `0x48084`

Same timer/frame. On step-done: if dest facing ≥ 8 → wait `0x78`, fail bit. `walker_can_step` then:

- **999** or (**0** and `bump`): facing **+1 & 7** (sidestep)
- **0**: path helpers `0x2B54A` / `0x2BA63` / `0x48A49` / `0x483D6` (**not opened this pass**)
- **1** or **2**: set `on_road` from the code, clear bit0, **`walker_step`**

### `walker_step` `0x488DC`

1. Unlink: if current tile[+7]==iter clear +7; else if +8==iter XOR-clear +8.
2. Apply facing 0–7 to `x`/`y`/`tile_off`:

| Facing | Δx | Δy | Δoff |
|---:|---:|---:|---|
| 0 N | 0 | −1 | −`0x640` |
| 1 NE | +1 | −1 | −`0x62C` |
| 2 E | +1 | 0 | +`0x14` |
| 3 SE | +1 | +1 | +`0x654` |
| 4 S | 0 | +1 | +`0x640` |
| 5 SW | −1 | +1 | +`0x62C` |
| 6 W | −1 | 0 | −`0x14` |
| 7 NW | −1 | −1 | −`0x654` |

3. Relink dest: empty +7 → write iter; else empty +8; else **`walker_free`** (third walker on a tile dies).

### `walker_can_step` `0x48470` / `walker_dest_ok` `0x48606`

Bounds: x/y stay in 0…79 (`'N'` = 78 for diagonal). Then dest_ok:

- both +7 and +8 occupied → **999**
- dest[+1] bit **0x20** → **1** (pad)
- dest[+1] == 0 → **2** (empty / road-ish)
- bit **0x02**: `++tile[+18]` up to 12 (queue), else 0
- other flag combos → 0 (blocked) or side calls (`0x68C01`, `0x691C4`)

---

## 5. Tile[+7] / [+8] — the two walker slots

City tile `0xE2FBC + (y*80+x)*20`.

| Off | Role |
|---:|---|
| **+7** | walker index 1…200, or 0. First occupant |
| **+8** | second occupant |

There is **no** third slot and **no** separate walk plane. Walkability is **tile[+1]**.

Who writes them:

| Fn | VA | +7 / +8 |
|---|---|---|
| `walker_spawn` | `0x2A7EF` | needs one empty; prefers +7 then +8. Also `tile[+3] \|= 1` |
| `walker_step` | `0x488DC` | unlink old, relink dest; both full → free |
| `walker_free` | `0x2AECB` | if +7==i → 0; else if +8==i → 0; then zero 58 B |
| `walkers_relink_tiles` | `0x2AFCB` | wipe **every** tile’s +7/+8 (unrolled 4 tiles / iter), then re-place live slots **1…200**; third on a tile is `walker_zero_record`. Phase `0xD2` |

`walker_dest_ok` / `walker_pick_pad_facing` **read** the slots (full = blocked / skip that neighbor). Draw (`city_tile_draw_walker_sprites`) uses them to know who stands on the diamond.

---

## 6. Type 3 / 7 — spawn and `walker_find_type3or7`

### `walker_find_type3or7` `0x47D1A` (decompiled)

Watcom: **EAX=x, EDX=y, EBX=radius**. Clamp box to 0…79. Scan 201 slots for occupied **type 3 or 7** inside the box (high edge exclusive). Distance is Chebyshev via `FUN_0002827a` `0x2827A`. Returns **closest slot index**, or **0** (slot 0 is never spawned, so 0 = none).

### Xrefs (CALL sites only)

| VA | Parent | Radius (EBX) | Why |
|---|---|---:|---|
| `0x413C3` | `FUN_0004133E` (phase barracks, id **0xBF**) | 6 (existing notes) | If found and `[0x102AB0]>1`: `walker_spawn_retry` **type 4**, `next_state=6`, `home_walker` = that slot |
| `0x462D2` | **state 6** | 10 | Escort lost its target → re-acquire or die |
| `0x463CC` | **state 7** | 10 | Coverage walker becomes hunter → state 6 |
| `0x46542` | **state 8** | 10 | Same |

No other CALLs in `0x10000`–`0x80000`.

### Type 3 spawn — **found**

`walker_spawn` xrefs besides `_retry`:

| VA | Function (renamed this pass) | EAX |
|---|---|---|
| `0x5364A` | **`walker_spawn_type3_from_actor26`** `0x53562` | **`mov eax, 3`** |
| `0x53760` | **`walker_spawn_type3_count`** `0x536E2` | **`mov eax, 3`** |

`0x53562` is called from `FUN_0004987D` when a live **actor26 type 2–5** steps on a province tile whose **id == 0x92**. Count of barbarians is 2/3/5/7/9 from `actor26[+0x8A]`. Pad flag **0** (road). After spawn: state **1**, `next_state=5`, wait `0x14`, dest = `[0x10262C]`/`[0x102628]`. Message queue `FUN_00058C87(EAX=0x53, EBX=0x17)`. Subtracts `0x40` from `[0x1025A8]`.

`0x536E2` is the same spawn loop with an explicit count (caller `FUN_00052828` ← `economy_recompute`). Also type 3.

### Type 7 spawn — **found**

`walker_spawn_retry` at **`0x4219B`** in `FUN_00041DD4` (phase `0x9E`–`0xA1`):

```
; housing id 0x82–0x9B, tile[+5] lo-nibble==0, packed score > 15
mov eax, 7
call walker_spawn_retry          ; three stack 0s → pad=0, retry class=0 (one try)
; rec: state=1, wait=0x14, next_state=0x0B (11)
FUN_00058c87(EAX=0x57, EBX=0x15) ; unless [0x117AA3]
```

Road spawn next to the angry house. Then states **11 ↔ 12** walk toward the same rally dword pair.

**False positive:** `mov eax, 3/7` at `0x41BD5` / `0x41BEB` is a **goods/housing cap**, not a walker type.

No `mov eax, 7` into `walker_spawn` itself. Rioters only go through `_retry`.

---

## 7. Record bytes touched this pass (additions)

Pool `0x1107A4`, stride 58. Previous map in `ghidra_walkers.md` still holds. New / clarified:

| Off | Name | Notes |
|---:|---|---|
| +0x2D | chase_count | state 6; 0…5 then reset |
| +0x30 | rng_lock | copy of target’s `+0x2E` while escorting |
| +0x33 | linger | state 5 countdown (init 3) — **not** `sprite_variant` (`+0x32`) |

Rally dest used by type 3 / states 5, 11, 12:

| VA | SavChunk | Use |
|---|---:|---|
| `[0x10262C]` | **20** | dest_x (byte written into `+0x0C`) |
| `[0x102628]` | **21** | dest_y (`+0x0D`) |

Who **writes** those dwords is still unnamed.

---

## 8. Names applied (GhidraMCP this pass)

| Name | VA |
|---|---|
| `walker_pick_pad_facing` | `0x48C9F` (was `FUN_00048c9f`) |
| `walker_set_dest` | `0x48E59` |
| `walker_spawn_type3_from_actor26` | `0x53562` |
| `walker_spawn_type3_count` | `0x536E2` |

Comments set on `walkers_tick` and `walker_find_type3or7`. Type/state stubs still have no function objects (rename API needs an existing fn).

---

## 9. Honest gaps

- Type 1/2/4/5/6 C2.ENG names — not proven. 3/7 are spawn-backed, not string-backed (only `rioters.smk`).
- State 9 callees `0x4A716` / `0x4A76D` / `0x4A397` / `0x4A57F` — fire vs building vs water not opened.
- `walker_anim_path` fail path (`0x2B54A`, `0x2BA63`, `0x48A49`, `0x483D6`) unread.
- Who writes `[0x102628]` / `[0x10262C]` (forum? map edge? invasion rally?).
- `FUN_00058C87` message ids `0x53` / `0x57` not mapped to C2.ENG lines.
- `walker_pick_pad_facing` C is messy (Watcom); listing is the source of truth.
- No Palatine 1-house A/B, so tile[+12]/[+14]/[+16]/[+17] vs walker scores still want a save pair.
- Host `walker_step` is in `app/walker_tick.py`; dest_ok / path-fail / state-9 helpers are still incomplete (see `app_tick.md`).

---

## 10. Short VA list

```
0x459D0  walkers_tick
0x45AFE  type1 … 0x45D0A type7   (not Ghidra fns)
0x45EDC  state0 … 0x468FE state12
0x47D1A  walker_find_type3or7
0x47EFA  walker_anim_roam
0x48084  walker_anim_path
0x488DC  walker_step
0x48470  walker_can_step
0x48606  walker_dest_ok
0x48C9F  walker_pick_pad_facing
0x48E59  walker_set_dest
0x2A7EF  walker_spawn
0x2AECB  walker_free
0x2AFCB  walkers_relink_tiles
0x4133E  barracks emit (type 4 if 3/7 in r=6)
0x41DD4  housing phase — type 7 rioter
0x53562  actor26 0x92 — type 3 barbarian
0x536E2  type 3 × N
0x99D24  walker_type_fn
0x99D68  walker_state_fn
0x102628 / 0x10262C  rally dest (chunks 21 / 20)
0xE2FBC+7 / +8       walker slots
```

---

## 11. What to click next in the GUI

1. **G `45AFE`** — define **type1** (and then `0x45F38` state 3) so the C view exists. Stubs are still a gap after `actors26_tick`.
2. **G `4A716`** — state 9 seek (hottest unread walker AI).
3. **G `102628`** — xrefs: who writes the barbarian/rioter rally.
4. Pin C2.ENG lines for `FUN_00058C87` ids **0x53** / **0x57**.

Do not start a crack session from the drive-letter strings.
