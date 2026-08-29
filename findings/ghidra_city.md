# Ghidra walk — city frame, new city, SavChunks

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP HTTP `127.0.0.1:8080`). No EXE in git. Continues `findings/ghidra_walk.md`.

**Result:** the per-frame function while a view is live is **`view_frame` @ `0x3CF9A`** (real body **`0x3CF9A`–`0x3D3E5`**). Ghidra’s function bounds are wrong (`0x3CF9A`–`0x10CF67`); redefine the function at the first `RET`. City sim ticks are **`walkers_tick` `0x459D0`** and **`actors26_tick` `0x45A7A`**. Starting money is **`city_treasury` @ `0x102AAC`** from a **15-int** C2MODEL header embed at `0x96F1B` (not a 1090-int copy). The 128 000-byte block at `0xE2FBC` is **80×80 tiles × 20 bytes (AoS)**, not 20 SoA planes.

---

## 1. `enter_view_mode` `0x3351B` — setup, not the tick

One-shot. Reads view kind **`[0x117A8D]`** (SavChunk 0).

| `[0x117A8D]` | Mode | Metrics set | After zoom / SFX |
|---|---|---|---|
| **0** | **City** | 80×80 (`0x50`), 480-high (`0x1E0`) | `city_sfx_bind_wavs` `0x12F2A`, **`city_view_enter_gfx` `0x5AC1E`** |
| **1** | **Province** | `0x3C` (60) | `FUN_00013187`, `FUN_0005AD67` |
| **2** | **Battle** | `0x34` | `FUN_00010AC9`, `FUN_00013351`, `FUN_0005AE68` |

Also: `zoom_set_params` / `gfx_load_zoom_set` (city+province), battle uses `FUN_0002974F` + `FUN_00010AC9`. Then `FUN_0001107C`, `FUN_0002FA70`, return. No frame loop here.

`city_view_enter_gfx` loads city chrome (`load_file` + `FUN_000360F7` / blit). Ghidra marks `video_blit_dirty` noreturn — **false**.

---

## 2. City / view tick — `view_frame` `0x3CF9A`

Only xref: **`c2_main` @ `0x10379`**. Inner loop (session `[0xCCAFF8]`, quit `[0xCCAFF7]`):

```
while (!session && !quit && (already || (view_frame(), !session)))
    combat_mode4_step();          // 0x10409; only if [0x102AA4]==4
    if ([0x102AA4] != 0) session = 1;
```

`[0xC45A0]` is game speed / catch-up (0 → 1 sim step; ≠0 → 4). `[0x102AA4]` **`view_submode`**: 0 = play, 1 = forum/empire (jumps out; `c2_main` then `FUN_00059A15`), 2/3 = early return, 4 = combat post-step.

### Real body (listing)

Ghidra merged ~850 KB into this function. **First RET is `0x3D3E5`** (epilogue `POP EBP…RET` at `0x3D3DF`). The `JZ 0x10CF46` on submode==1 is a bad far flow; do not follow it in the C view.

```
INC  [0xC45B4]                 ; frame_counter
CALL timer_delta_ms  0x27372   ; DOS clock; dt → [0xC4CD0]
CALL sim_tick_due    0x3E4B9   ; speed gate from dt + [0x9CE50]
  if due:
    loop 1 or 4 times:
      CALL 0x27F31
      CALL rng_clock 0x2804C   ; [0xC2070] = rand & 0x7F
      CALL 0x3F60C
      if view_submode is 2 or 3: RET
      CALL walkers_tick  0x459D0
      CALL actors26_tick 0x45A7A
CALL 0x25F26, 0x25C13          ; input
if city  ([0x117A8D]==0): CALL city_map_draw 0x360F7
if province && [0xCCB09]!=5:  CALL 0x39013
… UI / panels (0x6189D money read, 0x61A67, 0x589B5, …)
CALL 0x25D7A
CALL 0x28DCE
CALL video_blit_dirty 0x29849
RET
```

`sim_tick_due`: accumulates `[0x117ACC] += dt`. Returns 0 (skip sim) when speed `< 2` and pause-ish flags (`[0x117A8C]`, `[0x102B2C]`, `[0xCCB09] > 4`, …) or not enough ms. Threshold uses `(100 - [0x9CE50]) / 10`.

`city_map_draw` `0x360F7`: animation counters, then `FUN_000361DC` / `0x364A0` / `0x365CC` (those **read `0xE2FBC`**).

### Sim pools (also SavChunks)

| Fn | VA | Walk | Base | Stride | Count | SavChunk |
|---|---|---|---|---|---|---|
| **`walkers_tick`** | `0x459D0` | `0xC9` = 201 | **`0x1107A4`** `walker_pool` | `0x3A` = 58 | **201 × 58 = 11658** | **8** |
| **`actors26_tick`** | `0x45A7A` | `0x1A` = 26 | **`0x114500`** `actor26_pool` | `0xAF` = 175 | **26 × 175 = 4550** | **7** |

Walkers: skip empty `base[i]==0`; type at `+2` dispatches `0x99D24[type]` (types 1–7) else `FUN_0002AECB` (free). Increments `[0x117B1C]` mod 64.

Actors: skipped entirely if **`[0x9CE81]`** (`skip_actors_flag`, SavChunk 406). Type at `+4` dispatches `0x99D44[type]` (1–8) else `FUN_0002AF12`.

---

## 3. `init_new_city` `0x10565`

Called from **`start_city_assignment` `0x1049B`** when `[0xCCAFF0]==0` && `[0xCCAFF1]==0`. That wrapper also sets `[0x102AA0] = [0x102AB4] = −300` (SavChunk 25; matches the signed history/header values) and `[0x102590] = 0` (so the money deduct below is zero).

Order inside `init_new_city`:

| Step | VA | What |
|---|---|---|
| `city_view_reset` | `0x106BB` | View kind 0, 80×80 metrics, 480-high. Seeds **`[0x102BA0]=80`**, **`[0x102BA4]=40`** (SavChunks 6 and 5 — year-BC candidate 40, or view scalars; later overwritten). |
| `history_dat_reset` | `0x70A74` | `open_("history.dat")` create; **200× `write_`** then close. Zeros campaign trailer. |
| `walkers_clear_pool` | `0x2B16A` | Slots 1…200 via `FUN_0002AECB`. |
| `actors26_clear_pool` | `0x2B190` | Slots 1…25 via `FUN_0002AF12`. |
| `[0x1025E8] = *(0x96221 + difficulty×4)` | | Small packed table; **not** C2MODEL[0]. |
| **`city_treasury`** | **`0x102AAC`** | See money below. SavChunk **28**. |
| `[0x1029D8]=600`, `[0x102A7C]=[0x102AA8]=5` | | Chunks 29 / 30. |
| `city_ratings_seed` | `0x58BAE` | **`[0x102A58] = C2MODEL[difficulty]`** (ints 0–4: 20,15,10,5,2). Chunk 341. |
| `city_camera_zero` | `0x6E8E5` | Zeros scroll-ish + 3× `FUN_0007AC87`. |
| `FUN_000346CE` | `0x346CE` | Career / advisor gate; can set session-over. |
| `city_map_zero_lanes` | `0x6E140` | Zeros lanes in **`0xE2FBC`**. |
| **`apply_regions_map`** | **`0x706C3`** | `load_file("regions.dat")`; **60×60** decode → `prov_tile_stamp`. |
| `prov_map_fixup_flags` | `0x6AD31` | Walk 60×60 × 8, clear a flag. |
| **`city_map_generate`** | **`0x65809`** | 17× `city_map_clear_byte8` then rand terrain + river-like trace. |
| `climate_lookup_init` | `0x53B83` | Tables `0x95393` / `0x95ADB`. |
| `city_pop_counters_zero` | `0x52A41` | Five u32s. |
| `province_goods_setup` | `0x577E4` | 44-province (`0x2C`) goods into **`0xD2AEC`** (chunk 335) and **`0xD2B6C`** (chunk 339). |
| `FUN_000563E2`, `FUN_000555F1` | | More counter inits. |
| `economy_counters_reset` | `0x43DD4` | Zeros a pile of u32s; **`[0x1029F4] = city_treasury`**; 16×48 table at `0xD2B6C`. |
| `economy_recompute` | `0x3FCA0` | `view_submode=0`; calls `FUN_00056695` (heavy **treasury** R/W). Called twice in spirit with `0x43DD4` / `0x577E4` repeats. |

`map_clear_80x80` `0x3E590` (from `c2_main`, not from init) zeros a **different** 80×80 at **`0xD7BFC`** (`map_scratch_80x80`). **Not** in the SavChunk table.

### Starting money / C2MODEL

```
difficulty = [0x9CE80]          // SavChunk 16, 0…4
treasury   = *(i32*)(0x96F2F + difficulty*4)
           - *(i32*)(0x96F43 + difficulty*4) * [0x102590]
```

On a new assignment `[0x102590]==0` → full starting money.

EXE bytes at **`0x96F1B`** are exactly **C2MODEL.DAT ints 0–14** (15 × int32). Int 15 is `0` in the EXE vs `10` in the DAT — prefix stops there.

| VA | C2MODEL index | Values |
|---|---|---|
| `0x96F1B` | 0–4 | `20,15,10,5,2` (difficulty scalars → `[0x102A58]`) |
| `0x96F2F` | 5–9 | `20000,15000,12000,7000,5000` (start money) |
| `0x96F43` | 10–14 | `2000,500,250,150,100` (deduct × `[0x102590]`) |

**No `c2model` / `C2MODEL.DAT` string.** Full 4360-byte file is **not** in the mapped image (int 15 already diverges). The three `1090` immediates (`0x84294`, `0x85112`, `0x88207`) are raw dwords `42 04 00 00` in CRT gaps, **not** a 1090-int copy loop.

Housing occupancy / land / rank tables stay on disk only until another loader is found.

### 80×80 city map at `0xE2FBC` (SavChunk 13)

Size 128 000 = 20×6400 is still true as arithmetic. **Engine indexing is AoS:**

- Tile step **`0x14` = 20 bytes**
- Row step **`0x640` = 1600 = 80×20**
- `city_map_fill_rand_terrain` `0x65AFA`: 80×80, writes byte 0 = `(rng & 0xF) + 8`
- `city_map_trace_feature` `0x658D1`: drunk-walk (~960 steps), writes direction 0/2/4/6 on byte 0, **OR `0x10` into byte 1** (`0xE2FBD`). North/south ±`0x640`, east/west ±`0x14`. Looks like river / coast / feature.

`city_map_clear_byte8` `0x6E188(lane)`: 80×10× stride `0xA0`, zeros 8 byte-lanes. Called **17 times** from `city_map_generate`.

**Byte map (this + `findings/ghidra_walkers.md`):** +0 terrain/building id (`<0x78` grass-ish, `0x82–0xA1` housing); +1 path/feature flags (walkability, bit `0x10` river, `0x20` building pad); +3 draw/class; +4 building variant; +7/+8 walker slots (max 2); +10 service coverage bits. Remaining 12/14/16/17 still want a 1-house save pair (`file_off = 50395 + tile*20 + byte`).

### Province layer at `0xD94FC` (SavChunk 14)

**60×60 records × 8 bytes = 28800.** `apply_regions_map` walks `0x3C×0x3C` region bytes and calls **`prov_tile_stamp` `0x6A7CE`**, which writes:

| Off | Use |
|---|---|
| +0 | type (`param_3`; region bytes `0x7D`…`0x9C` map to terrain / specials) |
| +1 | flags (OR) |
| +3 | more flags |
| +4 | variant / orientation |

`combat_mode4_step` pokes type `0x97` / variant `0x32` into this blob when `[0x102AA4]==4`.

---

## 4. SavChunks named from this walk

Cross-check: `notes/ps_sav_chunks.tsv`. Trailer is **not** a table slot: after 500 chunks, `sav_write` `0x70174` **reads 4000 B `history.dat`** and appends them (pointer `[0xC4D10]`, same as `regions.dat` dest — reused). `sav_read` writes that trailer back to `history.dat`. New city **`history_dat_reset`** recreates the file (200 writes).

| idx | ptr | size | Name / evidence |
|---:|---|---:|---|
| **0** | `0x117A8D` | 1 | **view kind** 0/1/2 (`enter_view_mode`) |
| 1 | `0x117A59` | 1 | overlay / filter; tested in `city_map_draw` |
| 2–3 | `0x117A8B` | 1+1 | flags; `c2_main` zeros |
| 4 | `0x102BE0` | 4 | camera-ish; `apply_regions_map` zeros; `view_frame` uses for a blit |
| **5** | `0x102BA4` | 4 | `city_view_reset` = **40**; save u32@8 year-BC **hypothesis** (50/29/33) |
| **6** | `0x102BA0` | 4 | `city_view_reset` = **80** |
| **7** | `0x114500` | 4550 | **`actor26_pool`** 26×175; `actors26_tick` |
| **8** | `0x1107A4` | 11658 | **`walker_pool`** 201×58; `walkers_tick` |
| 9 | `0x113560` | 3978 | **26×153** (size only; not opened this pass) |
| 10 | `0xD361C` | 17688 | **201×88** (size only) |
| 11 | `0x115702` | 9045 | **201×45** (size only; contains the old “plane 6” 6400-zero hole) |
| 12 | `0x102DE4` | 3460 | unknown blob |
| **13** | `0xE2FBC` | 128000 | **city map 80×80×20 AoS** (`city_planes_20x80x80`) |
| **14** | `0xD94FC` | 28800 | **province tiles 60×60×8** (`prov_tiles_60x60x8`) |
| 15 | `0x103B68` | 100 | unknown |
| **16** | `0x9CE80` | 1 | **`difficulty`** 0–4 (indexes C2MODEL header) |
| **25** | `0x102AA0` | 4 | new assignment **−300** |
| **28** | `0x102AAC` | 4 | **`city_treasury`** |
| 29 | `0x102A7C` | 4 | init = 5 |
| 30 | `0x102AA8` | 4 | init = 5 |
| **335** | `0xD2AEC` | 256 | **`province_goods_slots`** (`province_goods_setup`) |
| **339** | `0xD2B6C` | 768 | **`goods_16x48`** 16×48; `economy_counters_reset` |
| **341** | `0x102A58` | 4 | **`rating_from_c2model0`** |
| **370** | `0x102AA4` | 4 | **`view_submode`** |
| 387–389 | `0xD2EFC` / `D2F4C` / `D2EAC` | 80 each | one map row / 80 flags (unchanged) |
| **406** | `0x9CE81` | 1 | **`skip_actors_flag`** (skips `actors26_tick` + alt goods) |
| 432–499 | `0x117D70` | 4×68 | padding (unchanged) |
| **trailer** | `[0xC4D10]` | 4000 | **`history.dat`** |

Slots 9–11 size-factor names are **hypotheses** until a loop with those strides is decompiled.

---

## 5. Names applied (GhidraMCP `rename_function_by_address` / `renameData`)

| Name | VA |
|---|---|
| `view_frame` | `0x3CF9A` |
| `walkers_tick` / `actors26_tick` | `0x459D0` / `0x45A7A` |
| `sim_tick_due` | `0x3E4B9` |
| `city_map_draw` | `0x360F7` |
| `timer_delta_ms` / `rng_clock` | `0x27372` / `0x2804C` |
| `city_map_generate` / `_fill_rand_terrain` / `_trace_feature` | `0x65809` / `0x65AFA` / `0x658D1` |
| `city_map_zero_lanes` / `_clear_byte8` | `0x6E140` / `0x6E188` |
| `prov_tile_stamp` / `prov_map_fixup_flags` | `0x6A7CE` / `0x6AD31` |
| `walkers_clear_pool` / `actors26_clear_pool` | `0x2B16A` / `0x2B190` |
| `history_dat_reset` | `0x70A74` |
| `city_ratings_seed` / `economy_counters_reset` / `economy_recompute` | `0x58BAE` / `0x43DD4` / `0x3FCA0` |
| `province_goods_setup` / `climate_lookup_init` | `0x577E4` / `0x53B83` |
| `city_view_enter_gfx` / `combat_mode4_step` | `0x5AC1E` / `0x10409` |
| `city_treasury` / `difficulty` / `view_submode` | `0x102AAC` / `0x9CE80` / `0x102AA4` |
| `c2model_i0_diff_scalars` / `_i5_start_money` / `_i10_money_deduct` | `0x96F1B` / `0x96F2F` / `0x96F43` |
| `walker_pool` / `actor26_pool` / `prov_tiles_60x60x8` | `0x1107A4` / `0x114500` / `0xD94FC` |
| `walker_spawn` / `walker_free` / `walker_step` | `0x2A7EF` / `0x2AECB` / `0x488DC` |
| `actor26_spawn` / `actor26_free` | `0x2AA02` / `0x2AF12` |

---

Walkers / tile bytes (this pass): **`findings/ghidra_walkers.md`**.

---

## 6. What to click next in the GUI

1. **G `2A7EF`** — **`walker_spawn`**. Then define functions at **`0x45AFE`** (type1 stub) and **`0x45F38`** (state 3 coverage).
2. **G `42360`** — **`city_buildings_evolve_row`**. Tile +11 / +13 / +15 vs housing grades.
3. **G `4118B`** — industry walker emitter; table `0x94FE5`.
4. **G `56695`** — treasury spend / income (hottest `city_treasury` xref).
5. Still want a **1-house A/B save** for tile bytes 12/14/16/17 and to pin walker types 1–7 to C2.ENG names.

Do not start a crack session from the drive-letter strings.
