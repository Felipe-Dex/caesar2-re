# Ghidra walk — city tile AoS 20 B

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP HTTP `127.0.0.1:8080`). No EXE in git. Continues `findings/ghidra_walkers.md` / `ghidra_city.md`. **Did not edit `app/`.**

**Result:** tile `0xE2FBC` is 80×80×20 AoS. `city_map_draw` `0x360F7` does **not** name +12/+14/+16/+17 — it only ticks anim counters and calls terrain / walkers / overlays. Those four bytes are owned by the **sim phase dispatcher** `FUN_0003f60c` (`[0x1026A8]` 0…`0xD6`). Each cycle **wipes +12/+13/+14/+15** then **repaints** them from building ids. `tile_or_radius` `0x6CD7E` is **not** +10-only: stack is `(lane, bits)`, ECX = radius (Watcom EAX/EDX/EBX/ECX).

---

## 1. 20-byte map

Index: `off = (y * 80 + x) * 20`. Row step `0x640`. First-tile VAs: +N → `0xE2FBC+N`.

| Off | Size | Name | Conf | Evidence |
|---:|---|---|---|---|
| **+0** | u8 | **terrain / building id** | high | generate; draw `<0x78` LUT `0x96F58`, `≥0x78` `city_tile_draw_building`. Housing **0x82–0xA1**. Industry **0xAE–0xB9**. Water `<8`. Specials `0xC0`, `0xD5–D6`, `0xE3–0xF0`, `0xF3–0xF4`, `0xFA`, `0xFC–0xFF` |
| **+1** | u8 | **path / feature flags** | high | walkability. Bit `0x10` river. Bit `0x20` building pad. Bit `0x40` walker bob. Bit `0x02` queue. `+17` flood treats `+1 & 0x1E` as a “source” |
| **+2** | u8 | overlay marker | med | drawn when `[0x102B2C]≠0` |
| **+3** | u8 | draw / class flags | high | bit0 dirty; bit1 drawn-this-pass; bits 2–4 sheet; **bit7 `0x80` = fire/special overlay** (`city_tile_draw_flag80`). +16 lives only while this bit is set |
| **+4** | u8 | building variant / sheet | high | `city_map_zero_lanes` zeros this lane |
| **+5** | u8 | packed spawn | med | lo-nibble: origin-tile / industry timer. Painters skip when lo-nibble ≠ 0 |
| **+6** | u8 | spawn countdown | med | `0x4118B` / `0x4133E` |
| **+7** | u8 | walker slot 0 | high | index 1–200 or 0 |
| **+8** | u8 | walker slot 1 | high | second walker |
| **+9** | u8 | overlay anim / saved id | med | water / flag80 frame; demolish restores +0 from here on river+pad |
| **+10** | u8 | **walker + building service bits** | high | walkers OR `0x0C` / `0xC0`; evolve-row decays `0x30`/`0x0C`/`0xC0`. Buildings also OR here via `tile_or_radius` lane `0xA` (industry `0x0C`, `0xE3`/`0xE4` `0x30`, `0xFC–0xFF` `0xC0`) |
| **+11** | u8 | housing grade bits | med | evolve-row bits 4–5 (`0x30`); lo-nibble is the immigrant-score nibble (`FUN_00041dd4`) |
| **+12** | u8 | **amenity coverage (3×2-bit)** | **high** | wiped phase `0x54`; max-merged by `FUN_0006ce67` from ids **0xE5–0xF0**. Overlay stub at `0x3E991` reads first-tile `DAT_000e2fc8` |
| **+13** | u8 | housing / land-paint bits | med | wiped phase `0x51`. `tile_or_radius` lane `0xD`: `0xF3`→`0x10`, `0xF4`→`0x20`, `0xBE`→`0x04`, `0xFA`→`0x80`, `0xFC–0xFF`→`0x40`. Walker scan `0x4A7FF` tests `0x40`/`0x80` |
| **+14** | u8 | **building-influence flags** | **high** | wiped phase `0x53`; `tile_or_radius` lane `0xE`. Single bits, not 2-bit strength. Housing spawn tests `& 3` |
| **+15** | i8 | **land-value accumulator** | high | wiped phase `0x52`. `FUN_0006da0e` adds signed deltas, clamp **−64…+64**. `FUN_00040d08` also writes a housing-target grade here. Not “industry only” |
| **+16** | i8 | **fire / disaster timer** | **high** | countdown while +3 bit7 set. Ignite `FUN_00069a37` writes **10**; spread `FUN_00069334`; resolve `FUN_000691c4` / `FUN_000696e8`. Water tile: hits 0 → clear bit7 |
| **+17** | u8 | **road-access flood (0–100)** | **high** | `FUN_000430da` 4-pass scanline. `+1 & 0x1E` → **100**; open tiles propagate / increment, cap 100. Housing evolve: signed `+17 > 15` |
| **+18** | u8 | queue / occupant | med | `walker_dest_ok` increments when +1 bit2 |
| **+19** | u8 | **0xFA goods / subtype nibble** | **med** | lo-nibble indexes `goods_16x48` (`FUN_00041b33`). Overlay frame for id `0xFA`. **Not** cleared at generate. Demolish zeros it |

**Walkability** is still byte 1. **+12 is not +10.** `tile_or_radius(lane=0xC)` does not exist — +12 uses the dedicated max-merge `FUN_0006ce67` (hardcoded `DAT_000e2fc8`).

---

## 2. `city_map_draw` `0x360F7`

```
[0x117AC8] = ([0x117AC8]+1) % 4
[0x117AB4]++  ; wrap at 0x80
derive >>1 / >>2 / >>3 / >>4 anim phases
if overlay [0x117A59] ∈ {0,1,4,8}: [0x117AC4]=1 else 0
city_map_draw_terrain()     ; +0 id, +3 dirty/drawn. No +12/+14/+16/+17
if [0x102BE4] != 1: city_map_draw_walkers()
city_map_draw_overlays()    ; +3 bit7 → city_tile_draw_flag80 (uses +9, +19 for 0xFA)
```

Fire graphics are **+3 bit7**, not a read of +16. +16 only times how long that bit stays on.

Overlay filter `[0x117A59]` (SavChunk 1) also dispatches `PTR_LAB_00099b3c[overlay]` from `FUN_0003e5e3` (phase `0xD3`). First-tile **+12** is a DATA xref at **`0x3E991`** (no Ghidra function — same gap style as walker type stubs). First-tile **+17** xref at **`0x3E7EF`** is the same class of stub.

---

## 3. `city_map_generate` `0x65809`

17× `city_map_clear_byte8(lane)` then `fill_rand_terrain` + `trace_feature`. Listing (EAX = lane):

`2, 1, 3, 9, 0x10, 5, 6, 7, 8, 0xF, 0xD, 0xE, 0xA, 0xB, 0xC, 4, 0x11`

= lanes **1–17**. **Not 0, 18, 19.** So +12/+14/+16/+17 start at 0 on a new map; +19 is left alone (and is 0 from BSS / previous `zero_lanes` only if that path ran).

`city_map_clear_byte8` `0x6E188`: `param_1` = byte lane; 80×10× stride `0xA0`, zeros that lane on 8 tiles per inner step (whole 128 000 map).

---

## 4. Sim phases that own +12 / +14 / +15 / +17

`FUN_0003f60c` (called from `view_frame` when a sim tick is due). `[0x1026A8]` increments every call; wraps after `0xD6`.

| Phase | Lane / fn | What |
|---|---|---|
| `0x51` | `clear_byte8(0xD)` | wipe **+13** |
| `0x52` | `clear_byte8(0xF)` | wipe **+15** |
| `0x53` | `clear_byte8(0xE)` | wipe **+14** |
| `0x54` | `clear_byte8(0xC)` | wipe **+12** |
| `0x56–0x5D` | `FUN_0003fdd0` | `tile_or_radius` onto **+13** and **+14** from `0xBE` / `0xFA` / `0xFC–0xFF` |
| `0x5E–0x65` | `FUN_000401e7` | paint **+14** (+ some +10) from `0xE3`/`0xE4`/`0xC0`/`0xBF–0xCA` / industry / `0xFC–0xFF` |
| `0x66–0x6D` | `FUN_0004034b` | paint **+12** from `0xE5–0xF0`; also +13 from `0xF3`/`0xF4` |
| `0x6E–0x75` | `FUN_0003fef7` | more `tile_or_radius` (messy decompile; Well `0xD7–0xDA` +13 `0x02` r=2 / `0xBE`) |
| `0x76–0x7D` | `FUN_00040695` | accumulate **+15** land value (`FUN_0006da0e`) |
| `0x7E–0x8D` | `FUN_00040d08` | housing-target grade → **+15**; reads **+17** (`> 15`) |
| `0x9E–0xA1` | `FUN_00041dd4` | housing immigrant score; reads **+14 & 3**; decrements **+16** on flag80 tiles |
| `0xA2–0xC1` | `FUN_000430da` | rebuild **+17** (4 scan directions, `DAT_00102678` 0…3) |

+10 is **not** wiped here (evolve-row decays it). +16/+17 are **not** in the 0x51–0x54 wipe list; +16 is per-tile state, +17 is fully rewritten by the flood.

### `tile_or_radius` `0x6CD7E` (Watcom)

```
EAX = extra (0, or 1/2 for the 0xF3/0xF4 calls)
EDX = x
EBX = y
ECX = radius
[esp+0] = lane   ; 0xA=+10, 0xC unused here, 0xD=+13, 0xE=+14
[esp+4] = bits   ; OR into that lane
```

Body: `city_planes[off + lane] |= bits` over a clipped square of side `2*radius+1` (+ `EAX` extra).

### `FUN_0006ce67` — +12 only

Max-merge, not OR:

```
if ((tile[+12] & mask) < value)
    tile[+12] = (tile[+12] & keep) | value;
```

Three rings per building (near / mid / far), same 2-bit decay shape as +10 (`1/2/3`, `4/8/0xC`, `0x10/0x20/0x30`).

---

## 5. +12 amenity coverage — bit groups

Only origin tiles (`+5 & 0xF == 0`). Radii from the listing (ECX).

| Ids | Keep / mask / values | Radii (near→far) | Channel |
|---|---|---|---|
| **0xE5** | keep `0xFC`, mask `0x03`, values **1 / 2 / 3** | 9 / 7 / 5 | bits 0–1 |
| **0xE6** | same | 11 / 9 / 7 | bits 0–1 (larger sibling) |
| **0xE7** | keep `0xF3`, mask `0x0C`, values **4 / 8 / 0xC** | 9 / 7 / 5 | bits 2–3 |
| **0xE8** | same | 11 / 9 / 7 | bits 2–3 (larger). Flag80 sprites `0x3B`/`0x3C` |
| **0xE9–0xEC** | keep `0xCF`, mask `0x30`, values **0x10 / 0x20 / 0x30** | 10 / 8 / 6 | bits 4–5 |
| **0xED–0xF0** | same | 12 / 10 / 8 | bits 4–5 (larger set) |

C2 names (shrine/temple, baths, theater, …) are **not** proven. 0xE5 vs 0xE6 (and E7/E8, E9–EC vs ED–F0) are the small/large pair of the same channel.

`0xF3`/`0xF4` in this same function paint **+13** (`lane 0xD`, bits `0x10`/`0x20`), not +12.

---

## 6. +14 building-influence flags

OR via `tile_or_radius` lane `0xE`. Rebuilt from scratch each cycle.

| Bit | Source id | Radius | Also paints |
|---|---|---:|---|
| **0x01** | `0xE4` | 3 | +10 `0x30` r=3 |
| **0x02** | `0xE3` | 2 | +10 `0x30` (flag80 overlay, anim +9) |
| **0x04** | `0xC0` | 2 | flag80 uses +4 as sheet |
| **0x08** | `0xBF`…`0xCA` | 2 | `0xBF` is the type-3 walker request building |
| **0x10** | `0xFA` | 2 | warehouse-ish; also +13 `0x80` |
| **0x20** | `0xFA` | 4 | |

`FUN_00041dd4` (housing 0x82–0x9B, origin tile): immigrant score nibble = `+11 & 0xF`, then **−1** if `+10 & 0x0C == 0`, **−1** if `+10 & 0x30 != 0`, **−1** if **`+14 & 3`**. Score `> 15` → spawn (next_state 0x0B). So bits 0–1 (E3/E4 radius) **suppress** that spawn. Polarity vs “good coverage” is mixed; do not call +14 “service coverage”.

---

## 7. +16 fire / disaster timer

Paired with **+3 bit7**. Draw: `city_map_draw_overlays` → `city_tile_draw_flag80` if bit7.

| Fn | VA | What |
|---|---|---|
| `FUN_00069a37` | `0x69A37` | ignite: +11 `&= 0xC0`, +3 `\|= 0x81`, +9 = rng table, **+16 = 10** |
| `FUN_00069334` | `0x69334` | spread to neighbor housing if that tile’s bit7 is clear |
| `FUN_00041dd4` | `0x41DD4` | each row: if bit7, **+16−−**. Water (`id<8`): 0 → clear bit7. Housing 0x82–0xA1: 0 → `FUN_000691c4` |
| `FUN_0004a716` | `0x4A716` | walker on burning water: +16==1 → clear bit7, else −− |
| `FUN_000696e8` | `0x696E8` | destroy / convert (new +0 from rng); +3 `\|= 0xC0`; +16 = `(rng>>2)+8` |
| `FUN_0006985b` | `0x6985B` | wipe tile: +16=0, +19=0, restore river terrain from +9 |

`fire.wav` / `"Fire rate "` exist as strings; C2 collapse may share bit7++16 (table `0x94FE5` types 4/9/0x10 go through `FUN_00069483` instead of `696e8`). Name is **fire timer** with that caveat.

---

## 8. +17 road-access flood

`FUN_000430da` `0x430DA`. Four passes (`DAT_00102678` 0…3), steps `±0x14` / `±0x640` (and diagonal bases `0x62C` / `0x1EDC0`).

- If `+1 & 0x1E == 0` (no bits 1–4): treat as open land; write a running value (seed `0xF8` = −8 signed) or increment existing +17 toward 100 and take min with the runner.
- Else: write **100**, then peek the neighbor’s +1 to decide whether the runner stays 100.

Housing `FUN_00040d08`: `local_1c = (char)+17 > 15` as a yes/no for the upgrade-grade ladder. 100 (on a flagged tile) passes; `0xF8` (−8) fails.

This is a **distance-from-feature** field, not a painter. Closest C2 name: **road / plaza access**. Exact +1 bits that mark “road” vs “river/queue” are not pinned (0x1E includes river `0x10` and queue `0x02`).

---

## 9. +19 (bonus)

Confirmed readers:

- `city_tile_draw_flag80`: id `0xFA` and `+5` lo-nibble==0 → frame = `(+19 & 0xF) + 9`
- `FUN_00041b33` (only caller `FUN_00041719`, id `0xFA`): `+19 & 0xF` indexes `(&DAT_000d2b84)[i*12]` / `d2b88` (goods 16×48 at `0xD2B6C` + 24). Writes a 0–7 production nibble into **+9**, not back into +19

Writers of the nibble itself were **not** found as `DAT_000e2fcf` xrefs (only wipe + draw + 41b33). Placement / warehouse-fill likely uses `tile_ptr[19]` without the first-tile symbol. **Not** cleared at generate; demolish (`6985b`) sets 0.

---

## 10. Names applied / not applied

This pass did **not** rename in Ghidra (read-only). Suggested:

| Name | VA |
|---|---|
| `tile_or_radius` | already `0x6CD7E` — comment: lane in `[esp]`, bits in `[esp+4]` |
| `tile_maxmerge_plus12` | `0x6CE67` |
| `city_sim_phase` | `0x3F60C` |
| `city_paint_plus12` | `0x4034B` |
| `city_paint_plus14` | `0x401E7` |
| `city_flood_plus17` | `0x430DA` |
| `tile_ignite` / `tile_wipe` | `0x69A37` / `0x6985B` |

---

## 11. Still unknown

- C2.ENG names for **0xE5–0xF0** (which amenity is bits 0–1 / 2–3 / 4–5).
- C2 names for **0xE3 / 0xE4 / 0xC0** (the +14 low bits). 0xE3 is a flag80 special; 0xC0 uses +4 as a sheet.
- Why `+10 & 0x30` (painted by E3/E4) **decrements** the immigrant score — problem flag vs inverted service.
- Whether +16 is **only** fire or also collapse (shared bit7).
- Which +1 bits are “road” for the +17 flood (`0x1E` is a bundle).
- Who **writes** +19 lo-nibble (warehouse stock / farm crop).
- Overlay index in `PTR_LAB_00099b3c` that lands on `0x3E991` / `0x3E7EF` (stubs are not functions).

A 1-house A/B save is still the cheapest confirm for +12/+14 bit polarity. Do not start a crack session from the drive-letter strings.
