# A.SAV vs C.SAV — one house (not B+house)

Local files only (`C:\Users\Felip\caesar2-re\A.SAV`, `B.SAV`, `C.SAV`). Not in git (`*.SAV` / `*.sav` in `.gitignore`). No save bodies copied here.

Same parser as `findings/sav_ab.md`: `sav_write` `0x70174`, **500 sequential `SavChunk`s = 221745**, then **4000** `history.dat` = **225745**. Chunk 13 is the 80×80×20 AoS city map at file offset **50395**.

Iso preview (gitignored): `sav_preview/C_iso.png` (also `A_iso.png` / `B_iso.png`).

**Confirmed:** C’s only building is housing **`0x82`** at **(0, 0)**: 1×1, HOUSES1 variant **0** → zoom-0 sprite **0**, treasury **−6**. C2.ENG **[23]** = `Tent`. This is **not** B plus a house — C replaced the empty grass at the origin; B’s `0xBE` Reservoir is absent.

---

## 0. C is not B+house

| Pair | XOR | Map buildings |
|---|---:|---|
| A vs B | **443** | (0,0) `0x14` → **`0xBE` Reservoir** |
| A vs C | **444** | (0,0) `0x14` → **`0x82` housing** |
| B vs C | **18** | (0,0) `0xBE` → `0x82` (same river `+13` already on both) |

B and C share the **identical 429-tile `+13=2` river band**. They are **parallel** stamps on the same time-advanced Novice map (A empty → one building each), not a sequence. C vs B is a 4-tile / 18-byte overlay (origin + 2×2 `+15`) and is **not** the empty-vs-house pair.

---

## 1. File sizes

| File | Bytes |
|---|---:|
| `A.SAV` | **225745** |
| `B.SAV` | **225745** |
| `C.SAV` | **225745** |

All match `221745 + 4000`. Trailer (last 4000) is **byte-identical** across A/B/C.

---

## 2. Chunks with any byte difference (A vs C)

Seven slots. Walker pool (8), actor26 pool (7), year (5), difficulty (16), view kind (0), sim phase (24), history trailer: **unchanged**.

| idx | file off | size | VA | Name / evidence | A | C | ndiff |
|---:|---:|---:|---|---|---|---|---:|
| **13** | 50395 | 128000 | `0xE2FBC` | city map 80×80×20 | (see §3) | (see §3) | **435** |
| **17** | 207296 | 4 | `0xC4598` | **LFSR RNG** (`FUN_00028003`) | `2002862591` | `2040943873` | 4 |
| **19** | 207304 | 4 | `0x102638` | **max `+15` this land-value pass** (`FUN_00040695` `DAT_00102638`; reset when row cursor is 0) | **0** | **1** | 1 |
| **23** | 207320 | 4 | `0x10265C` | **sim-phase row cursor** | **14** | **0** | 1 |
| **28** | 207340 | 4 | `0x102AAC` | **`city_treasury`** | **19990** | **19984** | 1 |
| **155** | 207908 | 4 | `0x102A2C` | monthly **construction / spend term** | **0** | **6** | 1 |
| **170** | 207968 | 4 | `0x102C8C` | unknown (advisor-flag sibling) | **9** | **15** | 1 |

A vs B did **not** move chunk 19 (both 0). C’s `1` equals the observed max tile `+15` (see §3.2). B vs C also moves 19 (`0 → 1`).

### Named scalars that did **not** move (A vs C)

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

Treasury **−6** equals chunk 155. A is already `20000 − 10` (Novice start). C2MODEL city-cost block `[96:123]` has **no** `6` (Gardens is 3; FAQ gateway is `[97]=5`). Occupancy `[217]=6` is the third hut grade (6 people), not a price. Same “observed debit ≠ FAQ list” pattern as Reservoir **51** vs `[101]=50`.

---

## 3. Chunk 13 — changed tiles (A vs C)

**433 tiles** differ. Only **one** changes `+0` (building id). **429** change **only `+13`**: `0 → 2` (same river band as A/B). **3** orthogonal neighbors change **only `+15`**: `0 → 1`.

| Class | n | Where | Bytes that move |
|---|---:|---|---|
| Origin stamp | **1** | **(0, 0)** | `+0 +1 +15` |
| Land-value radius | **3** | **(1,0) (0,1) (1,1)** | **`+15` only** |
| Land-paint splash | **429** | **x=51…79, y=0…37** (river NE band) | **`+13` only** |

No tile changes `+7/+8` (walkers), `+10` (coverage), `+12` (amenity), `+14` (influence), `+16` (fire), `+17` (road access). A has **zero** buildings (`id ≥ 0x78`). C has **exactly one**, and it **is** housing `0x82–0xA1`. Live walkers in chunk 8: **0 / 201** on A and C.

`+13` in A is **all zeros**. C’s 429-cell splash is **byte-identical** to B’s (same rows as `findings/sav_ab.md` §3.2). Neighbors of (0,0) are **not** in that band — the house `+15` splash is a separate 2×2.

Sim phase is **16** on A and C (evolve-row band `< 0x51`). `+13` paint lives in phases `0x56+`. C has already **wrapped a full `0xD6` cycle**, same as B.

### 3.1 Tile (0, 0) — the only id change

File offset `50395 + (0×80+0)×20 = 50395`.

```
A: 14 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
C: 82 01 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 00
```

| Off | Field | A | C | Note |
|---:|---|---:|---:|---|
| **+0** | id | `0x14` (20) terrain | **`0x82` (130)** | **First housing id.** Range `0x82–0xA1`. C2.ENG **[23]** `Tent` |
| **+1** | flags | 0 | **`0x01`** | bit 0. `FUN_00040695` requires this bit to apply housing land-value. **Not** pad `0x20` / river `0x10` / B’s Reservoir `0x80` |
| +2 | overlay | 0 | 0 | |
| **+3** | draw/class | 0 | **0** | `+3 & 0x1C = 0` → **HOUSES1**. Reservoir used `0x20` (same sheet, extra bit 5) |
| **+4** | variant | 0 | **0** | zoom-0 LUT[0] = **HOUSES1 sprite 0** |
| +5 | spawn packed | 0 | 0 | origin tile (lo-nibble 0) |
| +6 | spawn cd | 0 | 0 | |
| +7 / +8 | walker slots | 0 | 0 | |
| **+9** | overlay anim | 0 | **0** | Reservoir copied variant here (`0x6E`); house does not |
| +10 | coverage | 0 | 0 | |
| +11 | housing grade | 0 | 0 | still grade 0 (empty tent / vacant) |
| +12 | amenity | 0 | 0 | |
| +13 | land-paint | 0 | 0 | house did **not** paint `+13` on itself |
| +14 | influence | 0 | 0 | |
| **+15** | land-value | 0 | **1** | i8 accumulator. Chunk 19 stores this map-max |
| +16 | fire | 0 | 0 | |
| +17 | road access | 0 | 0 | |
| +18 | queue | 0 | 0 | |
| +19 | goods/subtype | 0 | 0 | |

**Confirmed (user C, high):** **`0x82` = first housing / Tent**, **1×1**, HOUSES1 variant **0** → sprite **0**. One HOUSES1 stamp at the **north iso tip** (grid 0,0). Small brown hut with dark roof, not the Reservoir sprite 90. Cost debit **6** (treasury + chunk 155). C2MODEL has **no** labeled city cost `6`.

`+3/+4/+9` staying 0 is the empty-housing look: FELIPE01 used nonzero variants on evolved houses (`0x89` → variant 7). This stamp has not evolved.

### 3.2 `+15` 2×2 (house land-value, not in A/B)

Chebyshev radius **1** around (0,0). Map corner clips the 3×3 to four tiles. C2MODEL housing land for slums / first grades is **`(-2, 1)`** (`[500:502]`) — **radius matches**; stored value is **`+1`**, not `−2`. Do not force the bonus number from this pair.

| Tile | File off | A `+15` | C `+15` | Other bytes |
|---|---:|---:|---:|---|
| (0, 0) | 50395 | 0 | **1** | also `+0/+1` (the house) |
| (1, 0) | 50415 | 0 | **1** | id stays `0x17` |
| (0, 1) | 51995 | 0 | **1** | id stays `0x0C` |
| (1, 1) | 52015 | 0 | **1** | id stays `0x11` |

Example (1, 0):

```
A: 17 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00
C: 17 00 00 00 00 00 00 00 00 00 00 00 00 00 00 01 00 00 00 00
```

B’s Reservoir left all four `+15` at **0**. This 2×2 is **housing-specific**. `FUN_00040695` then writes chunk 19 = max(`+15`) = **1**.

### 3.3 `+13` river band (429 tiles)

**Identical** to A vs B §3.2: A `0x00`, C `0x02`, same bbox / row ranges. Not from the (0,0) stamp. First-cycle river land-paint after a `0xD6` wrap.

---

## 4. Cleanliness vs the Reservoir pair

| Signal | A vs B (Reservoir) | A vs C (house) |
|---|---|---|
| One building id | **yes** — (0,0) `0x14 → 0xBE` | **yes** — (0,0) `0x14 → 0x82` |
| Housing `0x82–0xA1` | **no** | **yes** — first id, variant 0 |
| Walkers / chunk 8 | **yes** — 0 live | **yes** — 0 live |
| Fire `+16` / `+3` bit7 | **yes** | **yes** |
| Year / difficulty / view | **yes** | **yes** |
| History trailer | **yes** | **yes** |
| Money | **yes** — −51 = chunk 155 | **yes** — **−6 = chunk 155** |
| Extra map bytes | 429× `+13` only | **same 429× `+13`** plus **3× `+15`** (useful) |
| Extra scalars | RNG, row cursor, chunk 170 | **same set + chunk 19** (max `+15`, house-caused) |
| Sim time | **no** — full `0xD6` wrap | **no** — **same wrap** |

**XOR:** A/C **444** vs A/B **443**. One extra byte is chunk 19.

**Verdict:** **Housing mapping is closed** for the vacant tent: **`0x82`**, 1×1, HOUSES1 sprite 0, flag `+1=0x01`, land-value `+15=1` on Chebyshev r=1, treasury **−6**. Usable as the gold-standard “one house” id stamp.

The pair is **not cleaner than the Reservoir experiment on sim-time**. Same 429-tile river `+13` splash, same phase-16 / wrapped-cycle caveat. The extra A/C bytes are **house-caused** (2×2 `+15`, chunk 19), not more random noise — so the *housing* signal is cleaner than A/B even though the *clock* is the same. Re-do only if the goal is a tent with **no** sim wrap (save before phase `0x51`, or pause).

C vs B (18 bytes) is a clean **Reservoir vs Tent** overlay on an already-wrapped map. Do not use it as empty-vs-house.

---

## 5. Tools used

```text
python tools/_analyze_sav_c.py
python -c "… city_map.load_city_from_sav / render_iso → sav_preview/C_iso.png"
```

GhidraMCP on `0x102638` (`FUN_00040695` max `+15`). C2.ENG **[23]** `Tent`. C2MODEL `[500:502] = -2, 1`.
