# Ghidra walk — one city sim tick

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP HTTP `127.0.0.1:8080`). No EXE in git. Continues `findings/ghidra_city.md`, `ghidra_walkers.md`, `ghidra_tile.md`.

**Result:** a live city **or province** frame is `view_frame` `0x3CF9A` (real body ends at the first `RET` `0x3D3E5`; Ghidra still merges to `0x10CF67`). Who runs in city vs province vs forum: **`findings/view_modes.md`**. Each display frame always runs the timer + draw. **Sim work** runs only when `sim_tick_due` `0x3E4B9` returns 1, then **1 or 4** catch-up pulses. One pulse is: **`anim_phase_clocks` `0x27F31`** → `rng_clock` `0x2804C` → **`city_sim_phase` `0x3F60C`** (one `[0x1026A8]` slot, wrap `0xD6`) → **`walkers_tick` `0x459D0`** → **`actors26_tick` `0x45A7A`**. Host `app/sim.py` is a **fake frame increment**, not `walkers_tick`.

GhidraMCP this pass: decompiled `sim_tick_due`, `walkers_tick`, `actors26_tick`, `FUN_0003f60c` (renamed **`city_sim_phase`**). `view_frame` decompile timed out (bad bounds). CALL list below is the listing in `ghidra_city.md` plus the phase switch confirmed in C.

---

## 1. Who calls whom

```
c2_main 0x10379
  loop:
    view_frame           0x3CF9A
    combat_mode4_step    0x10409   ; only if view_submode [0x102AA4]==4
```

`[0xC45A0]` = game speed / catch-up (**0 → 1** pulse; **≠0 → 4**). `[0x102AA4]` `view_submode`: **0** play, **1** forum/empire (jumps out), **2/3** early RET inside the pulse, **4** combat.

---

## 2. `view_frame` `0x3CF9A` — every display frame

Ghidra function bounds are wrong. Stop at **`0x3D3E5`**.

| Order | VA | Name | When |
|---|---|---|---|
| 1 | — | `INC [0xC45B4]` | always (frame counter) |
| 2 | `0x27372` | `timer_delta_ms` | always; `dt` → `[0xC4CD0]` |
| 3 | `0x3E4B9` | **`sim_tick_due`** | always; 0 = skip the pulse block |
| 4… | (table §3) | **one sim pulse × 1 or 4** | only if due |
| 5 | `0x25F26` | `input_poll_cursor` | always (input) |
| 6 | `0x25C13` | `input_poll_buttons` | always (input) |
| 7 | `0x360F7` | `city_map_draw` | city (`[0x117A8D]==0`) |
| 8 | `0x39013` | `province_map_draw` | province && `[0xCCB09]!=5` |
| 9 | `0x6189D` / `0x61A67` / `0x589B5` / … | UI / money panels | always (not stubbed) |
| 10 | `0x25D7A` | `FUN_00025d7a` | always |
| 11 | `0x28DCE` | `FUN_00028dce` | always |
| 12 | `0x29849` | `video_blit_dirty` | always |

Do **not** treat draw as a sim tick. `city_map_draw` only bumps anim counters and blits (`ghidra_tile.md` §2).

---

## 3. One sim pulse (inside `view_frame`, when due)

```
loop catch-up (1 if [0xC45A0]==0 else 4):
  CALL anim_phase_clocks 0x27F31   ; mod 4/8/16/32/64/128/256 (not AI)
  CALL rng_clock  0x2804C   ; [0xC2070] = rand & 0x7F
  CALL city_sim_phase 0x3F60C
  if view_submode ∈ {2, 3}: RET   ; abort the rest of view_frame
  CALL walkers_tick   0x459D0
  CALL actors26_tick  0x45A7A
```

That is the whole city AI / coverage / fire / flood / walker dispatch for **one** tick. Enough to stub: **phase++ then walkers then actors**. Host v0 only fakes walker `walk_frame`.

---

## 4. `sim_tick_due` `0x3E4B9` (decompiled)

No nested sim CALLs. Accumulates `[0x117ACC] += dt` (`[0xC4CD0]`). Returns **0** (skip) when speed `[0xC45A0] < 2` **and** any pause-ish flag is set, or not enough ms:

- `[0x9CE50]` speed scalar → threshold `(100 - val) / 10`
- `[0x9CE64]`, `[0x117A8C]`, `[0x102B2C]`, `[0xCCB09] > 4`, `[0xCCB0C]`
- else need `[0x117ACC] >= iVar2*0x32 + 0x32`

Returns **1** → run the pulse(s). Host Space/T **ignores** this gate (manual step).

---

## 5. `city_sim_phase` `0x3F60C` (decompiled; was `FUN_0003f60c`)

Body `0x3F60C`–`0x3FB37`. Every pulse: `FUN_000128ea()`, then **one** slot of `[0x1026A8]`, then `++` and wrap after **`0xD6`** (`FUN_0003fbcf`, `FUN_000293ec`, `[0x117A8E]=1`).

Row cursor `[0x10265C]` is written from the phase (SavChunk 23). **Host does not run this switch.**

| Phase | CALL | What (from this + `ghidra_tile.md`) |
|---|---|---|
| always | `FUN_000128ea` | unnamed |
| `0` | `FUN_0004308b` | once per cycle |
| `1`…`0x50` | `city_buildings_evolve_row` `0x42360` | 80 rows; decays +10; housing grades |
| `0x51`…`0x54` | `city_map_clear_byte8` | wipe **+13 / +15 / +14 / +12** |
| `0x55` | — | nop |
| `0x56`…`0x5D` | `FUN_0003fdd0` | paint +13/+14 |
| `0x5E`…`0x65` | `FUN_000401e7` | paint +14 (+ some +10) |
| `0x66`…`0x6D` | `FUN_0004034b` | paint **+12** amenities |
| `0x6E`…`0x75` | `FUN_0003fef7` | more `tile_or_radius` |
| `0x76`…`0x7D` | `FUN_00040695` | **+15** land value |
| `0x7E`…`0x8D` | `FUN_00040d08` | housing target; reads **+17** |
| `0x8E`…`0x91` | `FUN_0004118B` | industry walker emit (type 1) |
| `0x92`…`0x95` | `FUN_0004133E` | barracks-ish emit |
| `0x96`…`0x99` | `FUN_000414A9` | emit types 5 / 4 |
| `0x9A`…`0x9D` | `FUN_00041719` | emit types 2 / 6 |
| `0x9E`…`0xA1` | `FUN_00041DD4` | immigrant score; **`--tile[+16]`** if +3 bit7 |
| `0xA2`…`0xC1` | `FUN_000430DA` | rebuild **+17** road flood (**do not stub yet**) |
| `0xC2`…`0xC9` | `FUN_000445AF` | unnamed |
| `0xCA` | `FUN_00043F88` | unnamed |
| `0xCB` | `FUN_00053C67`, `FUN_0006CA74` | unnamed |
| `0xCC` | `FUN_00029A19` | unnamed |
| `0xCD` | `FUN_000456F6` | unnamed |
| `0xCE`…`0xD0` | `FUN_0004327B` | rows 0 / `0x14` / `0x28` |
| `0xD1` | `FUN_00043B2E` | unnamed |
| `0xD2` | `walkers_relink_tiles` `0x2AFCB`, `FUN_0002B0A2` | rebuild tile +7/+8 |
| `0xD3` | `FUN_0003E5E3` | overlay dispatch |
| wrap `> 0xD6` | **`calendar_advance` `0x3FBCF`**, `FUN_000293EC` | month/year (`sav_date.md`) |

Placement / water flood are **out of scope** for the v0 host stub.

---

## 6. `walkers_tick` `0x459D0` (decompiled)

Body `0x459D0`–`0x45A79`. **201 × 58** @ `walker_pool` `0x1107A4`.

```
INC  sim_tick_mod64 [0x117B1C]; if > 0x3F → 0
CLAMP [0x10266C], [0x102674] to 0/1
walker_live_count [0x102664] = 0
for walker_iter [0x1156F8] = 0 .. 200:
  rec = walker_pool + i*0x3A
  if rec[+0] == 0: skip
  live_count++
  type = rec[+2]
  if type < 1 or type > 7: walker_free(i)          ; 0x2AECB
  else: walker_type_fn[type]()                     ; 0x99D24
```

Type handlers (not this stub): `walker_state_fn[rec[+0x10]]`, `walker_set_sprite`, life `rec[+0x24]++` every 64 ticks. State 2 → free. State 3/4 roam + paint +10. `walker_step` `0x488DC` actually moves the record.

Host Space/T now runs `walkers_tick` (`app/walker_tick.py`). See `findings/app_tick.md`.

### Record bytes the stub touches

| Off | Field | Stub |
|---:|---|---|
| +0 | occupied | read (skip if 0) |
| +2 | type 1–7 | read |
| +3 | facing 0–7 | **read only** (sprite formula; no fake turn) |
| +0x10 | state | skip if 2 (free) |
| +0x1F | `walk_frame` 0–15 | **++ wrap** |
| +0x34 | `sprite_id` i16 | rewrite `base + (facing%8)*3 + nibble` |

---

## 7. `actors26_tick` `0x45A7A` (decompiled)

Skipped if `[0x9CE81]`. Else 26 × 175 @ `0x114500`; type 1–8 → `0x99D44`. **Host does not tick actors.**

---

## 8. Host hook — `app/sim.py`

```
from app.sim import on_sim_step, step_walkers
n = on_sim_step(city, walkers)    # Space or T
```

| Key | Who binds it | What |
|---|---|---|
| **Space** or **T** | `app/window.py` `sim_step` | `on_sim_step` then drop `map_cache` and re-overlay from `terrain_cache` |

`__main__.py` re-exports `on_sim_step`. Pan / zoom stay on arrows / `+/-` (camera). Space/T does not move the camera.

Optional later (comment only in `sim.py`): `--tile[+16]` while `tile[+3] & 0x80` (`FUN_00041dd4`). **Not** `FUN_000430da` (+17 flood). **Not** building placement.

---

## 9. Names this pass

| Name | VA |
|---|---|
| `city_sim_phase` | `0x3F60C` (renamed from `FUN_0003f60c`) |
| `view_frame` / `sim_tick_due` / `walkers_tick` / `actors26_tick` | already named |

Still unnamed: `0x27F31`, `0x25F26`, `0x25C13`, `0x25D7A`, `0x28DCE`, most phase callees.

---

## 10. What to click next

1. **G `3CF9A`** — redefine the function at the first `RET` `0x3D3E5` so the C view is usable.
2. **G `27F31`** — pre-rng pulse head.
3. **G `41DD4`** — fire `--[+16]` (only if the host grows a real tick).
4. Do **not** implement `0x430DA` flood or placement in v0.

Do not start a crack session from the drive-letter strings.
