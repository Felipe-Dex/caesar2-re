# Ghidra walk — walkers, actors26, tile AoS

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP HTTP `127.0.0.1:8080`). No EXE in git. Continues `findings/ghidra_city.md`.

**Result:** each sim tick, `walkers_tick` `0x459D0` walks 201×58 and dispatches **type 1–7** then **state 0–12**. `actors26_tick` `0x45A7A` walks 26×175 on the **province** 60×60×8 map (skipped if `[0x9CE81]`). City tile at `0xE2FBC` is 20 bytes; **byte 0 is terrain/building id**, **byte 1 is path/feature flags (walkability)**, **+7/+8 are the two walker slots**. No separate walk plane. City draw uses **`LTLMEN{1,2,3}B.PL8`** (220×16×16), not `RO2*`. Host hook: `from app.walkers import overlay_walkers`.

Type/state stubs at `0x45AFE`+ are **not** Ghidra functions (gap after `actors26_tick` end `0x45AFD`). Listing via Capstone on the mapped image.

---

## 1. `walkers_tick` `0x459D0`

```
INC  sim_tick_mod64 [0x117B1C]; if > 0x3F → 0     ; 64-tick phase
CLAMP [0x10266C] and [0x102674] to 0/1            ; type 7 / type 3 set these to 2
walker_live_count [0x102664] = 0
for walker_iter [0x1156F8] = 0 .. 200:            ; slot 0 exists; spawn starts at 1
  rec = walker_pool + i*0x3A
  if rec[+0] == 0: skip
  live_count++
  type = rec[+2]
  if type < 1 or type > 7: walker_free(i)
  else: walker_type_fn[type]()                    ; 0x99D24
```

`walker_free` `0x2AECB`: if `tile[+7] == i` or `tile[+8] == i` clear that slot (tile from `rec[+6]`), then `walker_zero_record` (58 zero bytes).

`walkers_relink_tiles` `0x2AFCB`: wipe every tile’s +7/+8, then re-place live walkers (third walker on a tile is freed).

### Type table `walker_type_fn` `0x99D24`

Handlers are thin: `walker_state_fn[rec[+0x10]]()`, then `walker_set_sprite(base)`, then every 64 ticks (`sim_tick_mod64==0`) `rec[+0x24]++`; when life hits the cap, **state = 2** (free next tick).

| Type | VA | Sprite base | Life cap | Extra |
|---:|---|---:|---:|---|
| 1 | `0x45AFE` | `0x36` | 18 | |
| 2 | `0x45B53` | `0x1B` | 30 | |
| 3 | `0x45BA8` | `0xA6` | 72 | `[0x102CB4]=[0x102674]=2`. Searched by `FUN_00047d1a` with type 7 |
| 4 | `0x45C0E` | `0x6E` | 35 | |
| 5 | `0x45C63` | `0x51` | 20 | |
| 6 | `0x45CB8` | 0 | 30 | |
| 7 | `0x45D0A` | `0x89` or 0 if state==12 | 20 | `[0x102CB4]=[0x10266C]=2`. Prefects/engineers/soldiers candidate with type 3 |

C2 Query titles for 1/2/4/5/6 are now from **Achea Q&A** (below). Types 3 and 7 are the only ones `FUN_00047d1a` hunts in a radius.

Live SAV pairing (FELIPE01/02 / LASTYEAR): type **1→state 3**, **2→4**, **4→7**, **5→8**, **6→10**. Types 3 and 7 were absent on those cities.

### State table `walker_state_fn` `0x99D68`

| State | VA | What |
|---:|---|---|
| 0 | `0x45EDC` | `RET` (nop) |
| **1** | `0x45EDD` | Wait: `--rec[+0x0F]`; on 0 copy `rec[+0x0E]` → state, set anim bit0, `rec[+0x1E]=5` |
| **2** | `0x45F2C` | **`jmp walker_free`** |
| **3** | `0x45F38` | `walker_anim_roam`; OR **`0x0C` into tile[+10]** in r=3 (`tile_or_radius`) |
| **4** | `0x45FE9` | roam; OR **`0xC0` into tile[+10]** in r=3 |
| 5–12 | `0x46155`…`0x468FE` | more work (not fully read; 5+ exist) |

State 3/4 are **service coverage painters**. `city_buildings_evolve_row` `0x42360` later **decays** those same +10 bits (0x0C→8→4, 0xC0→0x80→0x40, 0x30→0x20→0x10).

### Spawn `walker_spawn` `0x2A7EF` (decompiled)

Watcom `__regparm3`: **EAX=type**, **EDX=x**, **EBX=y**, stack `param_3` = road(0) vs building-pad(≠0). Returns 1 on success, 0 on fail. Slot 0 is never filled here (scan **1…200**).

```
if x,y not in 0..79: return 0
off = (y*80 + x)*20
need empty tile[+7] or tile[+8]
tile[+1] bits 0+1+3+7 must be 0          ; mask 0x8B
if param_3==0: tile[+1] bits 2+4+6 == 0  ; 0x54; so +1 is 0 or 0x20
else:          tile[+1] bit 0x20 set     ; building pad
for slot = 1 .. 200:
  if pool[slot].occupied: continue
  occupied=1, type=EAX, facing=1
  x/y = dest_x/y = EDX/EBX
  tile_off = off
  x_frac = x<<4, y_frac = y<<4
  +0x1E = 5
  rng u16 at +0x2E = ([0x1026B0] + clock) & 0x7FFF
  link tile[+7] if empty else tile[+8]
  tile[+3] |= 1                          ; dirty
  +0x23 = (param_3 != 0)                 ; on_road inverted: 0=road, 1=pad
  +0x32 = rotating 0..15 (type==3 uses a 0..15 counter; else 0..31)
  return 1
```

Ghidra C at this VA is trustworthy except the `CONCAT11` flag test (it is `tile[+1] & 0x8B == 0`). Comment set in the image.

Wrapper `walker_spawn_retry` `0x42236`: EAX=type, EDX=x, EBX=y, stack pad-flag, stack **retry class**. Class **1/4/9/0x10** → 4/8/12/16 attempts; anything else → single `walker_spawn`.

`0x94FE5[building_id]` is that **retry class**, not the walker type. Industry ids **0xAE–0xB1→4**, **0xB2–0xB5→9**, **0xB6–0xB9→0x10**.

| Caller | VA | Building id | EAX type | next_state | Notes |
|---|---|---:|---:|---:|---|
| industry | `0x4118B` / call `0x41278` | **0xAE–0xB9** | **1** | 3 (2 if class 9, 1 if class 0x10) | pad; tile[+5] lo-nibble==0 |
| barracks-ish | `0x4133E` / `0x413F8` | **0xBF** | **4** | 6 | only if `FUN_00047d1a` finds type **3 or 7** in r=6; writes `+0x2C` home_walker |
| | `0x414A9` / `0x41574` | **0xE3** | **5** | 8 | pad; retry class 1 |
| | `0x414A9` / `0x4165A` | **0xE4** | **4** | (set) | pad; retry class 9 |
| | `0x41719` / `0x417F9` | **0xFC–0xFF** | **2** | 4 | pad; `+0x28` = home tile_off |
| | `0x41719` / `0x4192F` | (same fn, later id) | **6** | (set) | pad; retry class 9 |
| | `0x41DD4` | tile[+3] bit7 / water `<8` | — | — | no `walker_spawn_retry` in the head; not a type emitter |

No `mov eax, 3` / `mov eax, 7` at these sites. Types 3 and 7 still have **no named spawn** (invasion / fort / other file). `FUN_00047d1a` `0x47D1A` is a radius scan that returns a live type-3-or-7 slot index.

### Walker record 58 B @ `walker_pool` `0x1107A4` (SavChunk 8)

| Off | Size | Name | Evidence |
|---:|---|---|---|
| +0 | u8 | occupied | tick / spawn / free |
| +2 | u8 | type | 1–7 |
| +3 | u8 | facing | 0–7 = N NE E SE S SW W NW (`walker_step`) |
| +4 | i8 | x | 0–79 |
| +5 | i8 | y | 0–79 |
| +6 | i32 | tile_off | `y*0x640 + x*0x14` |
| +0xA | u8 | x_frac | spawn `x<<4` |
| +0xB | u8 | y_frac | spawn `y<<4` |
| +0xC | i8 | dest_x | `walker_set_dest` `0x48E59` |
| +0xD | i8 | dest_y | |
| +0xE | u8 | next_state | state 1 copies this |
| +0xF | u8 | wait_timer | state 1 |
| +0x10 | u8 | state | `walker_state_fn[]` |
| +0x11 | u8 | bump | set by `walker_dest_ok` |
| +0x1E | u8 | | spawn=5 |
| +0x1F | u8 | walk_frame | 0–15; sprite nibble |
| +0x20 | u8 | anim_timer | type-speed tables `0x96735` / `0x9673E` |
| +0x21 | u8 | anim_flags | bit0 done, bit1 fail |
| +0x22 | u8 | want_move | |
| +0x23 | u8 | on_road | spawn `param_3` |
| +0x24 | u8 | life_phase | +1 every 64 ticks |
| +0x26 | u8 | score_a | 0–100; housing scan `0x4A7FF` |
| +0x27 | u8 | score_b | 0–100 |
| +0x28 | i32 | home_off? | compared to tile_off in `0x41A0A` |
| +0x2C | u8 | home_walker | type-3 escort (`0x4133E`) |
| +0x2E | u16 | rng | |
| +0x32 | u8 | sprite_variant | |
| +0x34 | i16 | sprite_id | `walker_set_sprite` |
| +0x36 | u8 | bob | draw; 0x10 when tile[+1] has 0x40 |

`walker_step` `0x488DC` unlinks +7/+8, applies facing delta (`±0x14` / `±0x640` / `±0x62C` / `±0x654`), relinks. Two walkers already on dest → free.

`walker_dest_ok` `0x48606`: dest +1 bit `0x20` → 1; empty flags → 2; both slots full → 999; bit `0x02` increments tile[+18] up to 12 (queue).

---

## 2. `actors26_tick` `0x45A7A`

Skipped if `skip_actors_flag` `[0x9CE81]`. Else slots 0…25, stride `0xAF`:

```
if rec[+0] == 0: skip
rec[+0x36] = rec[+0x38] = 0          ; two u16s cleared every tick
live_count++
type = rec[+4]
if type < 1 or type > 8: actor26_free
else: actor26_type_fn[type]()        ; 0x99D44
```

`actor26_free` `0x2AF12`: `prov_tiles[+7] = 0` at `rec[+8]`, then zero 175 bytes.

These are **province** entities (60×60, 8-byte tiles @ `0xD94FC`), not city walkers.

### Type table `actor26_type_fn` `0x99D44`

Then `actor26_state_fn[rec[+0x12]]` @ `0x99D9C`.

| Type | VA | What |
|---:|---|---|
| 1 | `0x45D8F` | `actor26_set_sprite_t1`; if prov[+1] bit 2: timer +0x93=0x30, +0xA1=0x320; else decay those |
| 2 | `0x45E39` | `[0x102CF0]=2`; `actor26_set_sprite_t2`; state dispatch |
| 3, 4 | `0x45E64` | `[0x102CF0]=2`; `FUN_00047ae2`; same tail as type 2 |
| 5 | `0x45E75` | type 2 or 3 helper from `[0x1025CC] ∈ {6, 0xF, 0x12, 0x22}` |
| 6 | `0x45EC3` | `FUN_00047a44(0x4E)` then type-2 tail |
| 7, 8 | `0x45ED2` | `[0x102CF0]=2`; **RET** (no AI this build) |

### Spawn `actor26_spawn` `0x2AA02`

Province x/y in 0…59. Requires `prov[+7]==0`. `param_3==1` needs prov[+1] bit 3; `param_3==2` needs prov[+1] bits 0–4 clear. Slot 1…24 empty → occupied=1, type, x/y, dest=x/y, tile_off, frac `<<4`, +5=1 (facing), +0x22=5, +0x94=2, `prov[+7]=index`, `prov[+3]|=1`.

`FUN_0002b29b`: find by tile_off +0x2C, set occupied=**3** (leaving).

### Actor26 record 175 B @ `actor26_pool` `0x114500` (SavChunk 7)

| Off | Size | Name |
|---:|---|---|
| +0 | u8 | occupied (1 live, 3 leaving) |
| +1…+3 | u8 | sprite bytes (`actor26_set_sprite_*`) |
| +4 | u8 | type 1–8 |
| +5 | u8 | facing (spawn=1) |
| +6 | i8 | x (0–59) |
| +7 | i8 | y |
| +8 | i32 | prov_tile_off (`(y*60+x)*8`) |
| +0xC / +0xD | u8 | x_frac / y_frac |
| +0xE / +0xF | i8 | dest x/y |
| +0x12 | u8 | AI state |
| +0x22 | u8 | spawn=5 |
| +0x25 | u8 | flags \|=1 |
| +0x2C | i32 | tile_off copy |
| +0x32 | u16 | rng |
| +0x36 / +0x38 | u16 | **zeroed every tick** |
| +0x93 | u8 | timer (type 1) |
| +0x94 | u8 | spawn=2 |
| +0xA1 | u16 | timer (type 1) |
| +0xA3 | i32 | tile_off copy |

---

## 3. Tile AoS 20 B @ `0xE2FBC` (SavChunk 13)

Index: `off = (y * 80 + x) * 20`. Row step `0x640`. `city_map_generate` clears lanes **1–17** (not 0, 18, 19), then `fill_rand_terrain` writes byte 0 = `(rng&0xF)+8`, `trace_feature` writes river dirs 0/2/4/6 on byte 0 and **OR 0x10 into byte 1**.

### Byte map (partial)

| Off | Name | Confidence | Evidence |
|---:|---|---|---|
| **+0** | **terrain / building id** | high | generate; draw: `<0x78` terrain LUT `0x96F58`; `≥0x78` `city_tile_draw_building`. **0x82–0xA1 housing**. **0xAE–0xB9** industry spawners. **0xBF** type-3 request. Water `<8`. Specials `0xC0`, `0xD5–D6`, `0xE3`, `0xE7`, `0xE8`, `0xFA` |
| **+1** | **path / feature flags** | high | **walkability**. Bit `0x10` river. Bit `0x20` building pad (required to spawn from a building). Bit `0x40` walker bob. Bit `0x02` queue. Spawn mask: bits 0,1,3,7 must be 0. `tile_neighbor_flags` tests this byte on 8-neighbors |
| **+2** | overlay marker | med | drawn when `[0x102B2C]≠0` (`city_tile_draw_walker_sprites`); 3 vs other picks mouse-PL8 frames |
| **+3** | draw / class flags | high | bit0 dirty (spawn sets; draw clears + SFX). bit1 “drawn this pass”. bits 2–4 (`0x1C`) building **sheet** (0/4/8/0xC/0x10/0x14 → tables `0x97158`…). bit7 `0x80` → `city_tile_draw_flag80` |
| **+4** | building variant / sheet index | high | used when +0 `≥0x78`; `city_map_zero_lanes` zeros this lane |
| **+5** | packed spawn | med | lo-nibble: industry spawn timer (must be 0 to emit). hi-nibble: packed with +6 in `0x4118B` |
| **+6** | spawn countdown (lo nibble) | med | `0x4118B` / `0x4133E` |
| **+7** | walker slot 0 | high | index 1–200 or 0 |
| **+8** | walker slot 1 | high | second walker on the tile |
| **+9** | overlay anim | med | water / flag80 frame |
| **+10** | **service coverage bits** | high | walkers OR `0x0C` / `0xC0`; evolve-row decays 0x30/0x20/0x10 and 0x0C/8/4 |
| **+11** | housing grade bits | med | evolve-row bits 4–5 (`0x30`) on housing 0x82–0xA1 |
| +12 | unknown | — | cleared at generate (lane 0xC) |
| **+13** | housing / desirability nibble | med | evolve-row + walker scan `0x4A7FF` (bits 0x40/0x80) |
| +14 | unknown | — | lane 0xE |
| **+15** | industry growth byte | med | evolve-row compares vs `0x96275` tables |
| +16, +17 | unknown | — | lanes 0x10, 0x11 |
| **+18** | queue / occupant | med | `walker_dest_ok` increments when +1 bit2; `0x41A0A` also treats as walker index |
| **+19** | special nibble | low | type `0xFA` overlay; **not** cleared at generate |

**Walkability** is byte 1, not a 21st plane. Max **two** walkers per tile. Housing ids **0x82–0xA1**. Overlay/filter `[0x117A59]` (SavChunk 1) still gates which draw pass runs.

---

## 4. Names applied (GhidraMCP)

| Name | VA |
|---|---|
| `walker_spawn` / `_retry` / `_free` / `_zero_record` | `0x2A7EF` / `0x42236` / `0x2AECB` / `0x2AE42` |
| `walkers_relink_tiles` | `0x2AFCB` |
| `walker_step` / `_set_sprite` / `_anim_roam` / `_anim_path` | `0x488DC` / `0x479B8` / `0x47EFA` / `0x48084` |
| `walker_set_sprite_t7` (type 7 extra frames) | `0x47A95` |
| `walker_find_type3or7` | `0x47D1A` |
| `walker_can_step` / `_dest_ok` | `0x48470` / `0x48606` |
| `facing_from_delta` | `0x2B4DD` |
| `actor26_spawn` / `_free` / `_zero_record` | `0x2AA02` / `0x2AF12` / `0x2AE55` |
| `actor26_set_sprite_t1` / `_t2` | `0x47C4B` / `0x47B94` |
| `tile_or_radius` / `tile_neighbor_flags` | `0x6CD7E` / `0x6B0D1` |
| `city_map_draw_terrain` / `_walkers` / `_overlays` | `0x361DC` / `0x364A0` / `0x365CC` |
| `city_tile_draw_building` / `_walker_sprites` / `_flag80` | `0x3739F` / `0x382FB` / `0x37E0F` |
| `city_buildings_evolve_row` | `0x42360` |

Type/state stubs were **not** created as functions (rename API needs an existing fn). Comments set at `0x45AFE` / `0x45BA8`.

---

## 4b. Achea Q&A — Query titles

User Query on **ACHEA23**, plaza a bit **left** of the suggested civic-column tiles (same types on Plaza 1). Official title = Query heading, not the Latin person name.

| Type | Query title | Home / emit (Ghidra) | Achea check |
|---:|---|---|---|
| 1 | **Forum Clerk** | `0xAE–0xB9`; C2.ENG [66] ` - Forum Clerk` | casa annotated Forum; no `home_off` in this save |
| 2 | **Market Trader** | `0xFC–0xFF` | home Market 3 |
| 3 | **Enemy** (C2.ENG; no Achea slot) | barbarian spawn | title from [66]+2 |
| 4 | **Soldier** | `0xE4` / `0xBF` escort | casa annotated Barracks |
| 5 | **Vigile** | `0xE3` | casa annotated Praefecture (Query is Vigile, not Prefect) |
| 6 | **Worker** | factory `0xFA` | home Winery (two slots) |
| 7 | **Rioter** (C2.ENG; no Achea slot) | rioter spawn | title from [66]+6 |

Full quotes + skip table + picker: `findings/walker_quotes.md`. Person names = official **[64]** + `rec[+0x32]`. Type 3 title in C2.ENG is **Enemy**.

---

## 5. Type → sprite (LTLMEN, not RO2)

`walker_set_sprite` `0x479B8` writes `rec[+0x34] = base + facing_rel*3 + walk_nibble`.
`city_tile_draw_walker_sprites` `0x382FB` then does `sprite_id * 0x10 + 8` into **`[0x102410]`**.

That pointer is **`gfx_load_zoom_set` `0x107DB` slot 0**. Zoom table starts at **`0x927D0`** (20-byte `{name[16], size}`):

| Zoom | Slot 0 file | n / size | flags |
|---:|---|---|---|
| 0 | `ltlmen1b.pl8` | 220 × 16×16 | `0x0002` |
| 1 | `ltlmen2b.pl8` | 220 | `0x0102` |
| 2 | `ltlmen3b.pl8` | 220 | `0x0102` |

`LTLMEN1B` atlas rows (sprite.y): type6=201, type2=226, type1=251, type5=276, type4=301, type7=326, type3=351, leftover row y=376 (indices 193–219, unused by the type table).

**`RO2SLGC` / `RO2SPRB` / `RO2SWDA`** (and `RO3*`) are **battle** packs: 178 bitmaps ~12–18×29–31, loaded by the battle path (`FUN_00010AC9`), palette `BATLFIX2`. **No walker type 1–7 indexes an RO2 file.** Do not blit RO2 onto the city iso.

| Type | Sprite base | LTLMEN index | Typical state (SAV) | Emitter |
|---:|---:|---|---:|---|
| 1 | `0x36` | 54–80 | 3 (OR `0x0C` / r=3) | industry `0xAE–0xB9` |
| 2 | `0x1B` | 27–53 | 4 (OR `0xC0` / r=3) | buildings `0xFC–0xFF` |
| 3 | `0xA6` | 166–192 | — (none in FELIPE*) | hunted by `0x47D1A`; no spawn site yet |
| 4 | `0x6E` | 110–136 | 7 | `0xBF` (escort) and `0xE4` |
| 5 | `0x51` | 81–107 | 8 | building `0xE3` |
| 6 | 0 | 0–26 | 10 | `0x41719` second site |
| 7 | `0x89` or 0 if state==12 | 137–163; `FUN_00047a95` may use 164/165 | — | hunted by `0x47D1A` |

Type 7 uses `FUN_00047a95` `0x47A95` (not `walker_set_sprite`) when state ≠ 12: `wait_timer` bands pick `base+0x1B` or `base+0x1C`.

### Host: `app/walkers.py`

Parses SavChunk **8** with the same 500-size stream as `city_map.walk_sav_chunks` (file_off **4566**, 11658 B). Host calls `overlay_walkers` after `render_iso` (tecla **3** / `--map-preview`). Does **not** edit `render_iso` itself.

```
from app.walkers import overlay_walkers
img = overlay_walkers(img, walkers, game)   # img = native render_iso canvas
```

`overlay_walkers` loads `LTLMEN1B.PL8` via `assets.load_pl8_frames` → `decode_pl8` (no PL8 copy). Blit at `tile_iso_xy` (same diamond math as `render_iso`) with the 16×16 feet near the tile bottom-center. Prefers saved `sprite_id`; else `TYPE_LTLMEN_BASE[type] + facing*3 + frame`.

---

## 6. Short VA list (skeleton comments)

```
0x459D0  walkers_tick
0x45A7A  actors26_tick
0x2A7EF  walker_spawn
0x2AECB  walker_free
0x488DC  walker_step
0x2AA02  actor26_spawn
0x1107A4 walker_pool     201 * 58
0x114500 actor26_pool    26 * 175
0xE2FBC  city tile AoS   80 * 80 * 20
0x99D24  walker_type_fn[8]
0x99D68  walker_state_fn[16]
0x479B8  walker_set_sprite
0x47A95  walker_set_sprite_t7
0x47D1A  walker_find_type3or7
0x927D0  zoom PL8 table (slot0 = ltlmen*b)
0x102410 LTLMEN handle (draw)
```

---

## 7. What to click next in the GUI

1. **G `47D1A`** — `FUN_00047d1a` (type 3/7 radius hunt). Follow xrefs to find who **spawns** type 3 and 7 (`mov eax, 3` / `7` into `walker_spawn` / `_retry`). Define the function.
2. **G `45AFE`** — define **type1** (and `0x45F38` state 3) so the C view exists. Stubs are still a gap after `actors26_tick`.
3. **G `42360`** — **`city_buildings_evolve_row`**. Names +11 / +13 / +15 vs C2MODEL housing grades.
4. **G `56695`** — treasury (still hottest `city_treasury` xref).
5. Pin building ids **0xBF / 0xE3 / 0xE4 / 0xFC** to C2.ENG names. Still want a **1-house A/B save** for tile bytes 12/14/16/17.

Do not start a crack session from the drive-letter strings.
