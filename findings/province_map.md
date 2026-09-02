# Province map — SavChunk 14 (60×60×8)

**Save used:** `ACHEA23.SAV` (`C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV`). Chunk 14 is **populated** (14 303 / 28 800 bytes nonzero). `20230610.SAV` and `FELIPE01.SAV` are also live; not empty. Spreadsheet: `findings/Achea_province.xlsx`.

Do **not** copy city tile names (Tent / Casa / Plaza / …) onto these ids. City draw splits at **`0x78`**; province draw (`FUN_00039032` @ `0x39032`) splits at **`0x7D`**.

---

## Layout

| | |
|---|---|
| BSS | `0xD94FC` (`prov_tiles_60x60x8`) |
| SavChunk | **14** |
| File offset | **178395** (`notes/ps_sav_chunks.tsv`) |
| Size | 28800 = **60 × 60 × 8** |
| Index | `off = (y * 60 + x) * 8` |

Filled at new city by **`apply_regions_map` `0x706C3`**: `regions.dat` record (3600 bytes = 60×60) → **`prov_tile_stamp` `0x6A7CE`**. Later player builds write the same 8-byte records.

`tile_or_radius` `0x6CD7E` is **city-only** (80×80 × stride 20). Province equivalent is **`FUN_0006ccaa`**: write one lane across a radius on the 60×60×8 grid (assign, not OR).

---

## 8-byte record (guesses)

| Off | VA | Use | Conf | Notes |
|---:|---|---|---|---|
| **+0** | `0xD94FC` | **type / id** | high | `prov_tile_stamp` writes `param_3` here. Draw: `< 0x7D` → terrain LUT `0x97B40[id*4 + zoom>>1] + 0x10`; `≥ 0x7D` → `FUN_00039dcd` (building sheets). Achea: **147** distinct values. Terrain carpet is `0x22`–`0x29` (~263 each). |
| **+1** | `0xD94FD` | **flags (OR)** | high | Stamp ORs `param_6`. Occupancy reject: bits `0x10` or `0x01`. `actor26_spawn`: bit 3 / bits 0–4. `FUN_00068178` treats **`0x20` as pad** (place-building). `prov_map_fixup_flags` may clear `0x10` when bit `0x08` set and id `< 0x7C`. Achea top: `0x18` (2223), `0x00` (661), `0x08`, `0x10`, `0x20`. Region land `0x20`–`0x7B` stamps `0x18`. |
| **+2** | `0xD94FE` | unknown (anim / dirty-ish) | low | Never written by `prov_tile_stamp`. Achea: `0x00` / `0xFE` / `0xFF` dominate (`0xFF` on the north row). Not a type. |
| **+3** | `0xD94FF` | **sheet + dirty** | high | Stamp: `(& 0xE3) \| param_4`. Draw building: **`& 0x1C`** picks PL8 sheet (0 / 4 / 8 / 0xC / 0x10), same idea as city `+3`. Bit **0** = dirty (draw clears + SFX). Bit **1** = drawn this pass. Region Hill / mountain `0x7D`–`0x8D` have `+3 = 4`. |
| **+4** | `0xD9500` | **variant / sprite** | high | Stamp: size-1 writes `param_5`; 2×2/3×3/4×4 add a small LUT (`0x9422C`…). Building draw uses this as the sprite index. Terrain often copies byte0 (`+4 ≈ +0`). Region `0x7D`–`0x84` → variant `0`–`7`. |
| **+5** | `0xD9501` | unknown | low | Almost only `0` / `1` on Achea (2019 / 1575). Not opened in stamp/draw this pass. |
| **+6** | `0xD9502` | unused? | med | **All 3600 tiles = 0** on Achea / 20230610 / FELIPE01. |
| **+7** | `0xD9503` | **actor26 slot** | high | `actor26_spawn` writes pool index; `actor26_free` zeros it. Stamp refuses the tile if `+7 != 0`. Origin of a 2×2 stamp also checks this. |

`combat_mode4_step` pokes id **`0x97`** / variant **`0x32`** into this blob when `view_submode == 4`.

---

## byte0 histogram (ACHEA23)

3600 tiles, **147** ids. Terrain (`< 0x7D`) **3155**. Specials (`≥ 0x7D`) **445** tiles / **45** ids.

| Class (guess, not a name) | Ids | Tiles |
|---|---|---:|
| Water-ish | `0x00`–`0x17` | ~620 |
| Land carpet | `0x22`–`0x29` | ~2114 |
| Other terrain | `0x18`–`0x21`, `0x2A`–`0x7C` | rest of 3155 |
| REGIONS Hill / Small Mountain / Mountain (sheet 4) | `0x7D`–`0x8D` | **170** — 1×1 Hill · 2×2 Small Mountain · 3×3 Mountain; see `province_roads.md` |
| Your City | **`0x92`** | **4** (2×2 @ 32,24) |
| Towns / sea-lane portals | `0x97`, `0x98`, `0x9D`–`0x9F` | 8 |
| Provincial Road (`+1 = 0x20`) | `0xA0`–`0xAA` | **168** — 11 autotile dirs; see `province_roads.md` |
| Other built | `0xB6`, `0xBE`, `0xBF`, `0xD2`–`0xEF` | 103 |

`apply_regions_map` maps region bytes `0x7D`…`0x9C` to stamp args (Hill / Small Mountain / Mountain / city / markers). Player palette (C2MODEL costs): Road, Wall, Fort, Work camp, Farm/Mine/Quarry, Port, Warehouse, Shipyard, Trading post. C2.ENG **[53]** `Prov. Wall`. Extra query-pool strings in `C2.ENG` (not in the 146-slot index): `Roman Town`, `Border Town`, `Sea Lane`, `Provincial Road`, `Provincial Wall`, `Merchant Ship`, `Enemy Ship`, `Barbarian Ship`.

---

## User fill (Achea_province.xlsx, 2026-08-30)

Read-only pass over the user’s `mapa` sheet. Generator left `Desconhecido N` on every special; the user overwrote some. Axes are **not** swapped: header is x=0…59 / y=0…59, and the known 2×2 at (32,24) plus the three documented edge markers still sit where chunk 14 says.

**445** specials (`≥ 0x7D`). **67** cells have a real name on the sheet. **378** still say `Desconhecido *`. **4** terrain cells (`< 0x7D`) were also named (Meadow). **24 / 45** special ids are now named (sheet + wall/port + this session’s Hill / Small Mountain / Mountain). The xlsx `mapa` was **not** rewritten; a `legenda_montanhas` copy tab was added.

What is good:

- Same byte0 → same building family. Exception: Port uses **`0xEC` / `0xED` / `0xEF`** for facing (same 2×2, different `+4`). Goods / fullness / “very many people” are **query flavor**, not extra ids (`Warehouse (Lead)` and `Warehouse (Grapes)` are both `0xD4`).
- 2×2 footprints hold one id per stamp (Farm / Mine / Quarry / Port / Trading post / Your City). Port may be `0xEC` or `0xEF` (facing). The user often named only the origin cell and left the other three as `Desconhecido` — that is incomplete, not wrong.
- Edge portals `0x9D`/`0x9E`/`0x9F` correctly labeled **Sea Lane** (destinations in the tooltip).
- `0x92` is **Your City**, not “Invasão”. Ghidra’s old name was the *attack target*: actor26 types 2–5 stepping on this id spawn city walker type 3 (`Barbarian Invasion!` is C2.ENG **[92]**). The tile itself is the city.

Noise (not axis bugs):

- `Work Camp` vs `Workcamp`; `Roman Town (very many people)` vs `(Very many people)` vs `Roman Towns`.
- `Border Town (To` truncated.
- Meadow `0x1C`/`0x1D`/`0x1E` is terrain the user marked as farmable, not a special id.

### Name → id so far

Canonical name = family. Parentheticals omitted. Counts are all tiles of that id on Achea, not only the cells the user typed.

| Id | User name | Tiles | Named / blank | Footprint |
|---|---|---:|---|---|
| `0x92` | **Your City** | 4 | 4 / 0 | 2×2 @ (32,24) |
| `0x97` | **Roman Town** | 4 | 4 / 0 | four 1-tiles (19,24) (21,32) (24,2) (41,31) |
| `0x98` | **Border Town** | 1 | 1 / 0 | (2, 0) north tip |
| `0x9D` | **Sea Lane** (To Trade Route) | 1 | 1 / 0 | (59, 10) east |
| `0x9E` | **Sea Lane** (To Creta) | 1 | 1 / 0 | (40, 59) south |
| `0x9F` | **Sea Lane** (To Campania) | 1 | 1 / 0 | (0, 44) west |
| `0xB6` | **Provincial Wall (with gate)** | 1 | 1 / 0 | (33, 11) — EW opening, `+4=0x29` |
| `0xBE` | **Provincial Wall** | 1 | 0 / 1 | (33, 40) — end-N / isolated piece (user) |
| `0xBF` | **Provincial Wall** | 1 | 1 / 0 | (32, 11) — end-E, next to the gate |
| `0xD2` | **Cohort Fort** | 1 | 1 / 0 | (36, 27) — actor26 type **1** sits here |
| `0xD3` | **Work Camp** | 7 | 5 / 2 | 1-tile camps |
| `0xD4` | **Warehouse** | 24 | 13 / 11 | pairs next to industry; goods not in byte0 |
| `0xD5` | **Shipyard** | 8 | 8 / 0 | two 2×2 in (17,37)–(27,42) |
| `0xDF` | **Farm** | 12 | 8 / 4 | three 2×2 (Grapes named on two) |
| `0xE3` | **Mine** | 12 | 8 / 4 | three 2×2 (Lead named on two) |
| `0xE7` | **Quarry** | 4 | 1 / 3 | 2×2 @ (20,2) (Clay on origin) |
| `0xEB` | **Trading Post** | 4 | 1 / 3 | 2×2 @ (4,2) |
| `0xEC` | **Port** | 16 | 8 / 8 | four 2×2; default facing (`+4` base `0x50`) |
| `0xEF` | **Port** (seaward / other facing) | 4 | 0 / 4 | 2×2 @ (13,36); same building, `+4` base `0x5C` |
| `0x1C`–`0x1E` | Meadow *(terrain)* | 4 named | — | farmable land, not a special |
| `0x7D` | **Hill** (tipo A, `+4=0`) | 10 | 0 / 10 | 1×1 — user D2 |
| `0x7E` | **Hill** (tipo B, `+4=1`) | 16 | 0 / 16 | 1×1 — user D3 |
| `0x81` | **Hill** (tipo E, `+4=4`) | 10 | 0 / 10 | 1×1 — user D4 “different type” |
| `0x87` | **Small Mountain** | 8 | 0 / 8 | 2×2 — user D5 |
| `0x8D` | **Mountain** | 18 | 0 / 18 | 3×3 — user D7 |

Hill / Small Mountain / Mountain are query names. The sheet still shows `Desconhecido N` on those cells (this pass did not rewrite `mapa`). Family = stamp size: 1×1 = Hill (eight `+4` types), 2×2 = Small Mountain, 3×3 `0x8D` = Mountain. Full N→id: `province_roads.md` §3.

User also said **D11 = Small Mountain** and **D14 = Hill**. Those N are `0x7F` (1×1 `+4=2`) and `0x8B` (2×2 `+4=32…35`). Canonical name follows stamp size (Hill / Small Mountain). If the in-game query really said the other word, the string does not follow the stamp.

### Still blank

| Class | Ids | Tiles | Likely |
|---|---|---:|---|
| Hill 1×1, no user N | `0x80` D16, `0x82` D6, `0x83` D8, `0x84` D22 | 42 | same family as D2/D3/D4; other `+4` types |
| Small Mountain 2×2, no user N | `0x85` D28, `0x88` D33, `0x89` D26, `0x8C` D9 | 36 | same family as D5 |
| D11 / D14 (label ≠ stamp) | `0x7F` D11, `0x8B` D14 | 30 | stamp says Hill / Small Mountain |
| Missing on Achea | `0x86`, `0x8A` (2×2); `0x8E`–`0x91` (3×3) | 0 | not on this map |
| Provincial Road (gray) | `0xA0`–`0xAA` | 168 | 11-dir autotile, city twin `0x52`–`0x5C`. Still unnamed on the sheet. |

No lone unknown building left on Achea. Do **not** look for ships in this blank list. They are not a byte0.

**Achea province structures are complete** for the player palette + region stamps: Road, Wall, Fort, Work camp, Farm / Mine / Quarry, Port, Warehouse, Shipyard, Trading post, Your City, Roman Town, Border Town, Sea Lane, Hill / Small Mountain / Mountain. The sheet still leaves roads and most mountain cells as `Desconhecido`. Wall pieces `0xB7`–`0xBD` / `0xC0` and Port facing `0xED` exist in the engine / other saves, not on this map.

---

## Wall pieces (2026-08-30)

User: **(33,40)** `0xBE` = Provincial Wall, one orientation (like city walls). Confirmed. Did not rewrite the xlsx.

`FUN_000687eb` `0x687EB` (from `FUN_00068178` when `+1 & 2`): gather mask **6**, matcher `FUN_0006c826`.

| Branch | `+1` | Write |
|---|---|---|
| Gate | bit `2` **and** pad `0x20` | id **`0xB6`** hardcoded; LUT `0x94D77` × 2 → `+4` **`0x29`** (N=0 S=0, EW opening) or **`0x28`** (E=0 W=0, NS opening) |
| Run / end | bit `2`, no pad | id = **`DAT_00117a5e − 10`**; LUT `0x94BAF` × 14; `+4` from `0x94F90[city_id]` |
| Fort | bit `4` | id **`0xD2`** (unchanged) |

City twins are `0xC1`–`0xCA`. Province = city − 10. Full piece set:

| Prov | City | `+4` | Direction | Achea |
|---|---|---:|---|---|
| **`0xB6`** | *(gate, not −10)* | `0x28` / `0x29` | gate | (33,11) `B6 22 FE 00 29 …` |
| `0xB7` | `0xC1` | `0x1A` | straight NS | — (FELIPE01 run) |
| `0xB8` | `0xC2` | `0x1D` | straight EW | — |
| `0xB9` | `0xC3` | `0x20` | corner NE | — |
| `0xBA` | `0xC4` | `0x21` | corner SE | — |
| `0xBB` | `0xC5` | `0x22` | corner SW | — |
| `0xBC` | `0xC6` | `0x23` | corner NW | unused on Achea / FELIPE01 / 20230610 |
| `0xBD` | `0xC7` | `0x1B` | end-S | unused on those saves |
| **`0xBE`** | `0xC8` | `0x1C` | end-N (also the isolated stub) | (33,40) `BE 02 FE 00 1C …` |
| **`0xBF`** | `0xC9` | `0x1E` | end-E | (32,11) `BF 02 FE 02 1E …` |
| `0xC0` | `0xCA` | `0x1F` | end-W | — (FELIPE01) |

Achea only has the three. (32,11) `0xBF` sits west of the (33,11) gate; (33,40) `0xBE` is a lone stub south of a Port, no wall neighbours. Same family: `+1` bit `2`, `+2=0xFE`, `+5…+7=0`. Gate adds pad `0x20` (`+1=0x22`).

---

## Port `0xEC` vs `0xEF` (2026-08-30)

User: **(13,36)** `0xEF` = Port with the bottom exposed to the sea, hence not `0xEC`. Confirmed — **same building**, not a new type. Did not rewrite the xlsx.

Place (`FUN_0002fa70`, tool `0x28`) always stamps **`0xEC`** via `FUN_0006a58e` `0x6A58E` (2×2): `ebx=0xEC`, `+4` base **`0x50`**, sheet `+3 |= 8`, `+7` = cell 0…3. Water-adjacent check `0x6AB2A` (gather mask **8**). Draw (`FUN_00039dcd`) uses **`+4`**, not byte0, so the facing is the sprite set.

| Id | `+4` base (LUT `0,2,1,3`) | Facing | Achea | Also |
|---|---|---|---|---|
| **`0xEC`** | `0x50`–`0x53` | default (place) | four 2×2 | 20230610 |
| `0xED` | `0x54`–`0x57` | other | **none** | 20230610 (32,27) |
| `0xEE` | *(would be `0x58`)* | — | none | unused as Port (city C.Maximus is `0xEE`) |
| **`0xEF`** | `0x5C`–`0x5F` | seaward / bottom-to-sea (user) | (13,36)–(14,37) | 20230610, FELIPE01 |

ACHEA23 records (same `+1=0x09`, `+2=0xFE`, sheet `0x28`/`0x29`; `+5/+6=0`):

```text
0xEC (16,24)  EC 09 FE 29 50/52/51/53   +7 60 01 02 03
0xEC (33,37)  EC 09 FE 28 50/52/51/53   +7 40 01 02 03
0xEC (27,39)  EC 09 FE 28 50/52/51/53   +7 C0 01 02 03
0xEC (17,43)  EC 09 FE 28 50/52/51/53   +7 E0 01 02 03
0xEF (13,36)  EF 09 FE 29 5C/5E/5D/5F   +7 74 01 02 03
```

`+7` on the origin is later flags (not an actor26 slot here); the other three cells keep the stamp index 1/2/3. Water `0x10`–`0x17` has `+1=0`. The `0xEF` 2×2 sits on a coastal strip (water `0x11`/`0x12`/`0x16` to the NW); the four `0xEC` sit inland next to warehouse / shipyard / road.

---

## Ships (not a 60×60 tile id)

The user found the **Sea Lane** *portals* (`0x9D`/`0x9E`/`0x9F`). Those are 1-tile stamps on the map edge. HELP.ENG: ships *come from* a sea lane; a Shipyard *provides more ships*. C2.ENG unit names: `Merchant Ship`, `Enemy Ship`, `Barbarian Ship`. None of those are grid ids.

**Where they live:** SavChunk **7** = `actor26_pool` **26 × 175** @ file offset **16**, BSS **`0x114500`**. Ticked by `actors26_tick` `0x45A7A` (type jumptable `0x99D44`). Type **6** handler `0x45EC3` sets sprite with `FUN_00047a44(0x4E)` (base frame **78**) then the type-2 movement tail. Types 2–5 are the land armies that can step on Your City (`0x92`). Types 7–8 have no AI in this build.

**How they are drawn:** province frame `FUN_00039013` `0x39013` → tiles `FUN_00039032` then overlay `FUN_000392c7` `0x392C7`. Per tile, `FUN_0003ab6d` `0x3AB6D` reads **`tile[+7]`** as the actor26 slot and blits **`MY_STDS.PL8`** via handle `[0x102410]` (zoom-set slot 0). Ship frames `0x4E`… are **64×40** (zoom-1); cohort frames around `0x12`/`0x19` are **32×18** / **32×36**. They are sprites on top of whatever terrain they occupy — they never become byte0.

**ACHEA23 live actors (chunk 7):** planilha + Query em `findings/Achea_province_walkers.xlsx` / `achea_province_walkers.md`.

| Slot | Type | Tile | Dest | Note |
|---:|---:|---|---|---|
| 1 | **1** | (36, 27) `0xD2` Fort | (127, 128) = none | cohort at the fort |
| 2 | **6** | (8, 43) terrain `0x23` | **(1, 44)** | walking toward Sea Lane Campania `(0, 44)` |
| 3 | **6** | (44, 18) terrain `0x29` | (44, 18) | parked, state 13 |
| 4 | **6** | (12, 28) terrain `0x51` | (12, 28) | parked, state 13 |

No other actor26 occupied. City walker pool (chunk 8, 201×58) is city-only.

**Not map ships:** `ASHIPYA.PL8` is a 182×132 advisor icon (same size as `AHOUSE`). `PUNBOAT.PL8` is one 401×224 bitmap named from the HELP.ENG filename table (illustration), not a walk cycle. EXE has `shipyrd1.wav` / `shipyrd2.wav` only — no function named ship/sea/boat/lane except `city_map_zero_lanes`.

**If they are not on the 60×60 sheet:** look at the moving sprite (Query → Merchant/Enemy/Barbarian Ship), or dump chunk 7. While a ship sits on a tile, `tile[+7]` holds its pool index (1…25). The cell’s byte0 stays terrain / sea-lane / road.

---

## Tools

```text
python tools/_province_xlsx.py
python tools/_achea_province_labels.py
python tools/_achea_ships_probe.py
python tools/_province_roads.py
```

`_province_xlsx.py` **rewrites** the xlsx (do not run it over the user’s labels). The `_achea_*` / `_province_roads.py` scripts are read-only. `mapa` / `legenda` / `nomes` / `byte0` were not rewritten; a `legenda_montanhas` copy tab was added. Does not commit the SAV.

---

## Roads + mountains (2026-08-30)

User: everything **gray** on `Achea_province.xlsx` is Road; **light green** is mountains. Confirmed. Full tables: `findings/province_roads.md`.

- Gray `0xA0`–`0xAA` (168): Provincial Road. Same LUT `0x94AEF` as city terrain `0x52`–`0x5C`; province writes `city_id + 0x4E` and `+4 = 0…10`. Ends reuse the straight piece. T/cross also connect through buildings (mask `0xE5`).
- Green `0x7D`–`0x8D` (170): REGIONS sheet-4 stamps. **Hill** = 1×1 (`0x7D`–`0x84`, eight `+4` types), **Small Mountain** = 2×2 (`0x85`–`0x8C`), **Mountain** = 3×3 `0x8D`. User N: D2/D3/D4 Hill, D5 Small Mountain, D7 Mountain. D11 (`0x7F` 1×1) / D14 (`0x8B` 2×2) cross that rule — canonical follows stamp. Touched same-id 1×1s are separate Hills, not a wider sprite. Missing on Achea: `0x86`, `0x8A`, `0x8E`–`0x91`.
