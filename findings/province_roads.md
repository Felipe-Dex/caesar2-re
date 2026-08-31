# Province roads + mountains (Achea)

**Save:** `ACHEA23.SAV`. Spreadsheet colors from `tools/_province_xlsx.py` `class_of`: **gray** = `0xA0`–`0xAF`, **light green** = `0x7D`–`0x91`. Did not rewrite the xlsx.

Province draw `FUN_00039032` `0x39032`: byte0 `< 0x7D` → terrain LUT; `≥ 0x7D` → `FUN_00039dcd` (building sheets). Both families here are specials.

---

## 1. Gray = Provincial Road (`0xA0`–`0xAA`)

168 tiles, **11** ids. Xlsx also paints `0xAB`–`0xAF` gray; those ids are **absent** on Achea (not extra pieces).

Every gray tile: `+1 = 0x20` (pad), `+2 = 0xFE`, `+4 = id − 0xA0` (0…10), `+5/+6/+7 = 0`. `+3` is `0x20` on 162/168 (`& 0x1C` → sheet 0). Three `0xA1` have `+3 = 0`; three `0xA4` have `+3 = 0x22` (dirty bit). Same family.

Autotile LUT **`0x94AEF`** (16 × 12 bytes). 8-neighbor pattern (N,NE,E,SE,S,SW,W,NW); cardinals 0/1, diagonals don’t-care (`2`). Matcher `FUN_0006c826`. Ends **reuse the straight graphic** (no cap ids). Isolated uses the NS straight.

| Prov id | +4 | Tiles | Direction | City twin | LUT rows |
|---|---:|---:|---|---|---|
| `0xA0` | 0 | 52 | **straight NS** (+ N/S ends, isolated) | `0x52` | 0, 1, 3, 5 |
| `0xA1` | 1 | 42 | **straight EW** (+ E/W ends) | `0x53` | 2, 4, 6 |
| `0xA2` | 2 | 14 | **corner NE** | `0x54` | 7 |
| `0xA3` | 3 | 1 | **corner SE** | `0x55` | 8 |
| `0xA4` | 4 | 15 | **corner SW** | `0x56` | 9 |
| `0xA5` | 5 | 4 | **corner NW** | `0x57` | 10 |
| `0xA6` | 6 | 6 | **T (no W)** — N+S+E | `0x58` | 11 |
| `0xA7` | 7 | 16 | **T (no N)** — S+E+W | `0x59` | 12 |
| `0xA8` | 8 | 10 | **T (no E)** — N+S+W | `0x5A` | 13 |
| `0xA9` | 9 | 6 | **T (no S)** — N+E+W | `0x5B` | 14 |
| `0xAA` | 10 | 2 | **cross** N+S+E+W | `0x5C` | 15 |

Four 4-connected road components (sizes 141 / 21 / 3 / 3).

A **gray-only** N/S/E/W count under-reads T/cross: province gather `FUN_0006baeb` uses mask **`0xE5`** (includes pad `0x20`), so a warehouse / farm / port / town / Your City counts as a connection. City gather uses mask **`0x20`** only, so city neighbor counts look cleaner.

Examples: `0xA7` (32,23)–(33,23) is T-into-`0x92` Your City; `0xAA` (15,37) is N=`0xA8` S=`0xD4` E=`0xA1` W=`0xEF`; `0xAA` (20,38) is W=`0xDF` Farm. Still the cross / T graphic.

---

## 2. City analogy

City Road is **not** plaza `0x7C`–`0x7E` (retracted). It is **terrain** `id < 0x78` + `tile[+1] & 0x20`. On Achea city the graphic ids are **`0x52`–`0x5C`** (230 tiles; 4 extra pad tiles sit on `0x4F`/`0x50`).

Same LUT, same matcher:

| | City `FUN_000669c6` `0x669C6` | Province `FUN_00068178` `0x68178` |
|---|---|---|
| Grid | 80×80 × 20 | 60×60 × 8 |
| Neighbor gather | `FUN_0006adb0`, mask `0x20` | `FUN_0006baeb`, mask `0xE5` |
| Table | `0x94AEF` × 16 | same |
| Write id | `DAT_00117a5e` as-is (`0x52`…`0x5C`) | `DAT_00117a5e + 0x4E` → `0xA0`…`0xAA` |
| Write +4 | (terrain; no variant byte) | `DAT_00117a5e − 0x52` → 0…10 |

City Achea neighbor check (among `0x52`–`0x5C`) matches the table: `0x52` = NS, `0x53` = EW, `0x54`–`0x57` = corners, `0x58`–`0x5B` = T, `0x5C` = 3 crosses.

`prov_id = city_id + 0x4E`.

---

## 3. Light green = REGIONS Hill / Small Mountain / Mountain (`0x7D`–`0x8D`)

Xlsx green is `0x7D`–`0x91` (feature, `< 0x92`). Achea has **170** tiles / **15** ids through `0x8D`. Missing: `0x86`, `0x8A` (2×2 band), `0x8E`–`0x91` (3×3 band). All present tiles: `+1 = 0x10`, `+3 = 4` (sheet 4; one `0x7F` is `+3 = 5`), `+5 = 0`.

`apply_regions_map` `0x706C3` stamps from `regions.dat`. Variant stride + `prov_tile_stamp` `+4` LUTs (`0x9422C` 2×2 = `0,2,1,3`; `0x94230` 3×3 = `0,2,5,1,4,7,3,6,8`) match the footprints.

User (2026-08-30) queried leftover `Desconhecido N` (first-export legend: N = unique id ≥ `0x7D`, skip `0x92`). Family from stamp size: **Hill** = 1×1 (`0x7D`–`0x84`, eight `+4` types), **Small Mountain** = 2×2 (`0x85`–`0x8C`), **Mountain** = 3×3 `0x8D`. “Different type” = another id / `+4` in the 1×1 set. `mapa` was not rewritten.

| N | Id | Stamp | +4 | Name | Achea tiles | User |
|---:|---|---|---|---|---:|---|
| 2 | `0x7D` | **1×1** | 0 | **Hill** (type A) | 10 | Hill, different type |
| 3 | `0x7E` | **1×1** | 1 | **Hill** (type B) | 16 | Hill |
| 11 | `0x7F` | **1×1** | 2 | **Hill** (type C) | 14 | said Small Mountain — but 1×1, not 2×2 |
| 16 | `0x80` | **1×1** | 3 | **Hill** (type D) | 12 | unlabeled |
| 4 | `0x81` | **1×1** | 4 | **Hill** (type E) | 10 | Hill, different type |
| 6 | `0x82` | **1×1** | 5 | **Hill** (type F) | 7 | unlabeled |
| 8 | `0x83` | **1×1** | 6 | **Hill** (type G) | 15 | unlabeled |
| 22 | `0x84` | **1×1** | 7 | **Hill** (type H) | 8 | unlabeled |
| 28 | `0x85` | **2×2** | 8…11 | **Small Mountain** | 4 | unlabeled |
| — | `0x86` | **2×2** | (12…15) | **Small Mountain** | 0 | **missing** on Achea |
| 5 | `0x87` | **2×2** | 16…19 | **Small Mountain** | 8 | Small Mountain |
| 33 | `0x88` | **2×2** | 20…23 | **Small Mountain** | 8 | unlabeled |
| 26 | `0x89` | **2×2** | 24…27 | **Small Mountain** | 8 | unlabeled |
| — | `0x8A` | **2×2** | (28…31) | **Small Mountain** | 0 | **missing** on Achea |
| 14 | `0x8B` | **2×2** | 32…35 | **Small Mountain** | 16 | said Hill — but 2×2, not 1×1 |
| 9 | `0x8C` | **2×2** | 36…39 | **Small Mountain** | 16 | unlabeled |
| 7 | `0x8D` | **3×3** | 40…48 | **Mountain** | 18 | Mountain |
| — | `0x8E` | **3×3** | (49…57) | **Mountain**? | 0 | missing |
| — | `0x8F` | **3×3** | (58…66) | **Mountain**? | 0 | missing |
| — | `0x90` | **3×3** | (67…75) | **Mountain**? | 0 | missing |
| — | `0x91` | **3×3** | (76…84) | **Mountain**? | 0 | missing; `apply_regions` special-cases variant `0x4C` |

D11 (`0x7F`) and D14 (`0x8B`) cross the size rule. Canonical name = stamp: D11 = Hill, D14 = Small Mountain. If the in-game query really said the other word, the string does not follow the stamp.

**Stamp size** (one graphic), not merged-adjacent same-id blobs. Example bboxes: `0x7D` (18,0); `0x7E` (5,0) (pairs → 1×2); `0x7F` (7,1); `0x80` (18,2); `0x81` (17,0); `0x82` (15,0); `0x83` (16,0); `0x84` (18,3); `0x85` (18,6)–(19,7); `0x87` (8,0)–(9,1); `0x88` (21,16)–(22,17) + (20,18)–(21,19) (4-conn looks 3×4); `0x89` (13,4)–(14,5); `0x8B` (7,2)–(8,3); `0x8C` (16,4)–(17,5) + stacked (13,0)–(14,3); `0x8D` (10,0)–(12,2).

Same-id 1×2 / 2×1 / 3×1 on the 1×1 band are **adjacent Hills**, not a wider sprite (`+4` is constant per id). Mixed-id “ranges” (5 irregular blobs, largest 16×11 / 99 tiles) are forests of different stamps touching.

---

## Tools

```text
python tools/_province_roads.py
```

Read-only. Does not write the xlsx. Does not copy the SAV.
