# A.SAV vs B.SAV — surgical pair

Local files only (`C:\Users\Felip\caesar2-re\A.SAV`, `B.SAV`). Not in git (`*.SAV` / `*.sav` in `.gitignore`). No save bodies copied here.

Parsed as `sav_write` `0x70174`: **500 sequential `SavChunk`s = 221745**, then **4000** `history.dat` trailer = **225745**. Chunk 13 is the 80×80×20 AoS city map at file offset **50395** (`app/city_map.py` `load_city_from_sav`). Sizes from `notes/ps_sav_chunks.tsv`.

Iso previews (gitignored): `sav_preview/A_iso.png`, `sav_preview/B_iso.png`.

**Confirmed:** B’s only building is a **Reservoir** at (0,0): id **`0xBE`**, 1×1, HOUSES1 variant **`0x6E`** → sprite **90**, treasury **−51**. C2.ENG **[12]** = `Reservoir`. C2MODEL has **no** 51 (`[101]=50` is the FAQ list price).

---

## 1. File sizes

| File | Bytes |
|---|---:|
| `A.SAV` | **225745** |
| `B.SAV` | **225745** |

Both match `221745 + 4000`. Trailer (last 4000) is **byte-identical**. Total XOR: **443** bytes.

---

## 2. Chunks with any byte difference

Six slots. Walker pool (8), actor26 pool (7), year (5), difficulty (16), view kind (0), history trailer: **unchanged**.

| idx | file off | size | VA | Name / evidence | A | B | ndiff |
|---:|---:|---:|---|---|---|---|---:|
| **13** | 50395 | 128000 | `0xE2FBC` | city map 80×80×20 | (see §3) | (see §3) | **434** |
| **17** | 207296 | 4 | `0xC4598` | **LFSR RNG** (`FUN_00028003`) | `2002862591` | `208432322` | 4 |
| **23** | 207320 | 4 | `0x10265C` | **sim-phase row cursor** (`city_sim_phase` `0x3F60C` writes `DAT_0010265c` from `[0x1026A8]`) | **14** | **0** | 1 |
| **28** | 207340 | 4 | `0x102AAC` | **`city_treasury`** | **19990** | **19939** | 2 |
| **155** | 207908 | 4 | `0x102A2C` | monthly **construction / spend term** (read by `FUN_00056d39` / `FUN_00056c1c`; not yet zeroed by the settle path) | **0** | **51** | 1 |
| **170** | 207968 | 4 | `0x102C8C` | unknown (zeroed by `FUN_00058c3e` with advisor flags; not that path — would be 0) | **9** | **1** | 1 |

### Named scalars that did **not** move

| idx | Field | Both |
|---:|---|---|
| 0 | view kind | 0 (city) |
| 5 | year-BC hypothesis | **36** |
| 6 | view scalar | 0 |
| 16 | difficulty | 0 (Novice) |
| 24 | sim phase `[0x1026A8]` | **16** both |
| 25 | assignment seed | −300 |
| 29 / 30 | init fives | 5 |
| 341 | rating from C2MODEL[0] | 20 |
| 370 | view_submode | 0 |
| 406 | skip_actors | 1 |

Treasury **−51** equals chunk 155. A is already `20000 − 10` (Novice start). User confirmed the stamp is a **Reservoir**. Observed debit **51** is **not** in C2MODEL (1090 int32s; no slot equals 51). Closest labeled price is **`[101]=50`** (FAQ reservoir, with `1, 5, 20, 40, 75, 50` at `[96:102]`). Gardens 3 / Plaza 12 / Well 20 / Fountain 15 / Market 40 / Prefecture 100 are other labeled city costs — none is 51.

---

## 3. Chunk 13 — changed tiles

**430 tiles** differ. Only **one** changes `+0` (building id). The other **429** change **only `+13`**: `0 → 2`.

| Class | n | Where | Bytes that move |
|---|---:|---|---|
| Origin stamp | **1** | **(0, 0)** | `+0 +1 +3 +4 +9` |
| Land-paint splash | **429** | **x=51…79, y=0…37** (river NE band, not around the origin) | **`+13` only** |

No tile changes `+7/+8` (walkers), `+10` (coverage), `+12` (amenity), `+14` (influence), `+16` (fire), `+17` (road access). A has **zero** buildings (`id ≥ 0x78`). B has **exactly one**. Live walkers in chunk 8: **0 / 201** on both.

`+13` in A is **all zeros** (fresh `city_map_generate` / `clear_byte8(0xD)`). B’s 429 cells sit on the **existing river** (`+1 & 0x10` on 74 tiles in that bbox) — a **radius band around the river**, not a radius around (0,0). Neighbors of (0,0) are unchanged.

Sim phase is **16** on both (still in the evolve-row band `< 0x51`). `+13` paint lives in phases `0x56+`. So B has already **wrapped a full `0xD6` cycle** at least once; A has not. That is time, not the house footprint.

### 3.1 Tile (0, 0) — the only id change

File offset `50395 + (0×80+0)×20 = 50395`.

```
A: 14 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
B: BE 80 00 20 6E 00 00 00 00 6E 00 00 00 00 00 00 00 00 00 00
```

| Off | Field | A | B | Note |
|---:|---|---:|---:|---|
| **+0** | id | `0x14` (20) terrain | **`0xBE` (190)** | **Reservoir** (user A/B). Generate grass-ish (`(rng&0xF)+8`). **Not** housing `0x82–0xA1` |
| **+1** | flags | 0 | **`0x80`** | bit 7. **Not** pad `0x20` / river `0x10`. Walker spawn mask `0x8B` forbids this bit |
| +2 | overlay | 0 | 0 | |
| **+3** | draw/class | 0 | **`0x20`** | bit 5. `+3 & 0x1C = 0` → **HOUSES1** (`city_tile_draw_building`) |
| **+4** | variant | 0 | **`0x6E` (110)** | zoom-0 LUT[110] = **HOUSES1 sprite 90** |
| +5 | spawn packed | 0 | 0 | origin tile (lo-nibble 0) |
| +6 | spawn cd | 0 | 0 | |
| +7 / +8 | walker slots | 0 | 0 | |
| **+9** | overlay anim | 0 | **`0x6E`** | copy of variant |
| +10 | coverage | 0 | 0 | |
| +11 | housing grade | 0 | 0 | |
| +12 | amenity | 0 | 0 | |
| +13 | land-paint | 0 | 0 | 0xBE did **not** paint itself |
| +14 | influence | 0 | 0 | |
| +15 | land-value | 0 | 0 | |
| +16 | fire | 0 | 0 | |
| +17 | road access | 0 | 0 | |
| +18 | queue | 0 | 0 | |
| +19 | goods/subtype | 0 | 0 | |

**Confirmed (user A/B, high):** **`0xBE` = Reservoir**, **1×1**, HOUSES1 variant **`0x6E`** → zoom-0 LUT[110] = **sprite 90**. C2.ENG **[12]** is the string `Reservoir` (file offset 2659). Cost debit **51** (treasury + chunk 155). C2MODEL has **no** `51`; FAQ list price is **`[101]=50`**. One HOUSES1 stamp at the **north iso tip** (grid 0,0). Small brown sprite (frame 90), not a tent/insula/villa.

Ghidra already lists `0xBE` as a `+13` painter (`lane 0xD` → bit `0x04`) and as a HOUSES1 id on FELIPE01. `FUN_00012a8f` maps `0xBE` → advisor type **`0x10`** (not a C2.ENG index). This pair does **not** show that `0x04` splash — origin `+13` stays 0, and the 429-cell splash is `0x02` on the river, not `0x04` around (0,0).

### 3.2 `+13` river band (429 tiles)

Every one of these is **identical except `+13`**: A `0x00`, B `0x02`. Ids/flags stay terrain (mostly `0x08–0x17`, plus river `0x20+` with `+1 = 0x10` / `0x18`).

Example (51, 0), file `51415`:

```
A: 15 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
B: 15 00 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00
```

Example river (54, 0), file `51475`:

```
A: 26 10 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
B: 26 10 00 00 00 00 00 00 00 00 00 00 00 02 00 00 00 00 00 00
```

Row ranges (`+13` only):

| y | x |
|---:|---|
| 0 | 51–63 |
| 1–2 | 51–67 |
| 3–4 | 51–69 |
| 5 | 54–70 |
| 6 | 55–70 |
| 7–8 | 57–70 |
| 9 | 61–71 |
| 10 | 62–71 |
| 11 | 62–72 |
| 12–15 | 62–74 |
| 16 | 65–74 |
| 17 | 65–79 |
| 18 | 66–79 |
| 19–23 | 68–79 |
| 24 | 69–79 |
| 25–30 | 72–79 |
| 31–36 | 74–79 |
| 37 | 75–79 |

`0x02` is **not** in the documented `+13` OR table (`0xBE→0x04`, `0xF3→0x10`, `0xF4→0x20`, `0xFA→0x80`, `0xFC–0xFF→0x40`). First full paint pass after generate, sourced from the **river feature**, not from the (0,0) stamp.

---

## 4. Cleanliness

| Signal | Clean? |
|---|---|
| One building id | **yes** — only (0,0) `0x14 → 0xBE` |
| Housing `0x82–0xA1` | **no** — this is `0xBE` Reservoir |
| Walkers / chunk 8 | **yes** — 0 live, tiles `+7/+8` untouched |
| Fire `+16` / `+3` bit7 | **yes** |
| Year / difficulty / view | **yes** |
| History trailer | **yes** |
| Money | **yes** — −51, matches chunk 155 |
| Sim time | **no** — RNG moved; phase index still 16 but `+13` river band means a **full `0xD6` wrap** already ran on B; row cursor 14→0 |

**Verdict:** **Reservoir mapping is closed.** Usable as a **1-tile `0xBE` Reservoir + treasury −51** pair on a virgin Novice map. **Not** the gold-standard “pause, one house, save.” The 429-tile `+13` splash is **first-cycle river land-paint**, not 429 buildings. Re-do if the goal is a tent/house (`0x82+`) with **no** sim wrap (save B before phase `0x51`, or pause).

---

## 5. Tools used

```text
python -c "… city_map.load_chunk_sizes / walk_sav_chunks …"
python -m app --sav A.SAV --map-preview sav_preview/A_iso.png
python -m app --sav B.SAV --map-preview sav_preview/B_iso.png
```

GhidraMCP on `0xC4598`, `0x10265C`, `0x102A2C`, `0x102C8C`, `city_sim_phase` `0x3F60C`.
