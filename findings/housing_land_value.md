# Housing stages, tile[+15], and evolve thresholds

Evidence: `ACHEA23.SAV` / `20230610.SAV` / `FELIPE02.SAV` / `LASTYEAR.SAV` (gitignored), `C2MODEL.DAT` `[215:247]` occupancy, EXE table `0x96235` (32×`(i8 min, i8 max)`), `city_buildings_evolve_row` `0x42360`, `FUN_00040d08` `0x40D08`, `FUN_00040695` `0x40695`. Names from FAQ / [caesar2.com directory](https://www.caesar2.com/caesar-ii-building-directory/) / `tools/dump_c2model.py` `HOUSE_GRADES`. `0x82` = **Tent** from A/B + C2.ENG (same slot as FAQ “One hut”). Numbers + labels only; no EXE/SAV/DAT in git.

Dumper: `tools/_housing_lv_dump.py`. Table: `findings/housing_land_value.csv`.

---

## 1. The spreadsheet lumped the range

`tools/_achea_grid_xlsx.py` `KNOWN`:

| Id | Sheet label |
|---|---|
| `0x82` | Tent |
| `0x83–0xA1` | **Casa** (“graus de habitação”) |

Achea / v3 / new xlsx cells: **Casa ≈ 324–325**, Tent = 1 (legend only). `20230610_grid.xlsx`: **Casa=313**. That is one tag for 32 grades. The EXE indexes grade = `id − 0x82` (`i8(id + 0x7E)` in `0x42360`).

---

## 2. Two different “land values”

| What | Where | Meaning |
|---|---|---|
| **Tile field `+15`** | city 20 B, VA `0xE2FBC+15` | Current **desirability accumulator** on that cell. Phase `0x52` **wipes** it; `FUN_00040695` adds signed deltas (`FUN_0006da0e`, clamp −64…+64); `FUN_00040d08` then **caps it down** to a service ceiling (water / road `+17>15` / entertainment…). Overlay number. **Not** a property of the building type. |
| **Evolve band** | EXE `0x96235[grade*2]`, `0x96236[grade*2]` | Stay if `ev_min ≤ +15 ≤ ev_max`. `+15 < min` → `FUN_00042b2d` (down). `+15 > max` → `FUN_00042b75` (up). Villas/palaces (`grade > 25`) compare a **block** scan (`FUN_0006db08`), not the single origin byte. |
| **Directory “Required LV”** | caesar2.com / FAQ `0,2,4,…,64` | Threshold **to become** that stage ≈ `ev_max(prev)+1`. **Absent from C2MODEL** (`c2model.md`). |
| **C2MODEL `(bonus, radius)`** `[500:564]` | slums `(−2,1)` … palaces `(16,2)` | What the house **radiates onto neighbors**, not what it needs to evolve. Occupancy `[215:247]` is **people**, not LV. |

`FUN_00040d08` housing path writes even caps `2,6,10,12,14,…,64` when a service gate fails (no water → cap `2`). Saved `+15` is `min(accumulated, service_cap)`.

---

## 3. Achea `+15` is wiped — do not average it

All **324** housing tiles in `ACHEA23.SAV` have **`+15 = 0`**. Other lanes are live (`+10` coverage, `+12` amenity, `+13` land-paint, `+17` road flood). Same wipe on `FELIPE01.SAV`. Phase `0x52` ran; `0x76–0x8D` had not yet repainted when the file was written.

**Achea is useless for per-type land-value averages.** Counts below are still the id census.

Live `+15` is in **`20230610.SAV`**, **`FELIPE02.SAV`**, **`LASTYEAR.SAV`**.

On those saves, many 1×1 types sit at a **single** value = the **top of the EXE stay band** (e.g. every `0x89` = 16, every `0x8E` = 26). That is the evolve ceiling / service cap, not “Small house always has LV 16.” Types that **vary** (`0x90` 6…30, `0x9B` 12…64, `0x9F` 12…64, `0xA1` pads 32…64) prove `+15` is **neighborhood + services**. The number that belongs to the *type* is the **threshold**, not the mean of `+15`.

---

## 4. Table (id = `0x82 + grade`)

Achea **tiles** / **origins** (`+5` lo-nibble == 0). `0xA1` 90/10 = ten 3×3. `0x9F` 12/3 = three 2×2. `0x9D` 4/1 = one 2×2.

`20230610` `+15` = min / med / max on **all tiles** of that id (empty = absent).

| Id | Stage (FAQ / directory) | Achea n (tiles / orig) | 20230610 +15 | Become (dir) | Stay EXE | Occ | Radiates (b,r) | Foot |
|---|---|---:|---|---:|---|---:|---|---|
| `0x82` | Tent / One hut | 0 | — | 0 | −3…1 | 2 | −2, 1 | 1×1 |
| `0x83` | Two huts | 0 | — | 2 | 0…3 | 4 | −2, 1 | 1×1 |
| `0x84` | Three huts | 0 | — | 4 | 2…5 | 6 | −2, 1 | 1×1 |
| `0x85` | Communal hut | 0 | — | 6 | 4…7 | 8 | −1, 1 | 1×1 |
| `0x86` | Large communal hut | 1 / 1 | — | 8 | 6…9 | 10 | −1, 1 | 1×1 |
| `0x87` | Primitive house | 2 / 2 | 10 / 10 / 10 | 10 | 9…11 | 12 | −1, 1 | 1×1 |
| `0x88` | Simple house | 10 / 10 | — | 12 | 11…13 | 6 | 0, 1 | 1×1 |
| `0x89` | Small house | **64 / 64** | 16 / 16 / 16 | 14 | 13…16 | 7 | 0, 1 | 1×1 |
| `0x8A` | Average house | 10 / 10 | 16 / 16 / 18 | 16 | 16…18 | 8 | 0, 1 | 1×1 |
| `0x8B` | Improved house | 2 / 2 | 20 | 18 | 18…20 | 9 | 0, 1 | 1×1 |
| `0x8C` | Large house | 8 / 8 | — | 20 | 20…22 | 12 | 1, 1 | 1×1 |
| `0x8D` | Grand house | 16 / 16 | 23 / 24 / 24 | 22 | 22…24 | 16 | 1, 1 | 1×1 |
| `0x8E` | Primitive insula | **63 / 63** | 26 / 26 / 26 | 24 | 24…26 | 20 | 1, 1 | 1×1 |
| `0x8F` | Simple insula | 2 / 2 | 12 / 26 / 26 | 26 | 26…28 | 24 | 1, 1 | 1×1 |
| `0x90` | Small insula | 3 / 3 | **6 / 12 / 30** | 28 | 28…30 | 28 | 1, 1 | 1×1 |
| `0x91` | Average insula | 4 / 4 | 6 / 32 / 32 | 30 | 30…32 | 32 | 1, 1 | 1×1 |
| `0x92` | Improved insula | 1 / 1 | 6 / 23 / 34 | 32 | 32…34 | 36 | 1, 1 | 1×1 |
| `0x93` | Large insula | 1 / 1 | 6 | 34 | 34…36 | 42 | 1, 1 | 1×1 |
| `0x94` | Grand insula | 3 / 3 | 38 | 36 | 36…38 | 48 | 1, 1 | 1×1 |
| `0x95` | Imperial insula | 3 / 3 | 40 | 38 | 38…40 | 54 | 1, 1 | 1×1 |
| `0x96` | Simple domus | 1 / 1 | — | 40 | 40…42 | 20 | 2, 1 | 1×1 |
| `0x97` | Small domus | 3 / 3 | 44 | 42 | 42…44 | 25 | 2, 1 | 1×1 |
| `0x98` | Average domus | 4 / 4 | 46 | 44 | 44…46 | 30 | 2, 1 | 1×1 |
| `0x99` | Improved domus | 2 / 2 | 47 / 48 / 48 | 46 | 46…48 | 35 | 2, 1 | 1×1 |
| `0x9A` | Large domus | 3 / 3 | 56 | 48 | 48…50 | 40 | 2, 1 | 1×1 |
| `0x9B` | Grand domus | 12 / 12 | **12 / 60 / 64** | 50 | 50…52 | 45 | 2, 1 | 1×1 |
| `0x9C` | Simple villa | 0 | — | 52 | 52…54 | 100 | 8, 2 | 2×2 |
| `0x9D` | Small villa | 4 / 1 | 56 | 54 | 54…56 | 120 | 8, 2 | 2×2 |
| `0x9E` | Improved villa | 0 | — | 58 | 56…58 | 150 | 8, 2 | 2×2 |
| `0x9F` | Grand villa | 12 / 3 | **12 / 12 / 64** | 60 | 58…60 | 200 | 8, 2 | 2×2 |
| `0xA0` | Small palace | 0 | — | 62 | 60…62 | 300 | 16, 2 | 3×3 |
| `0xA1` | Large palace | **90 / 10** | 32 / 64 / 64 (origins all 64) | 64 | 62…125 | 500 | 16, 2 | 3×3 |

Directory villa LV skips **56** (52, 54, **58**, 60). EXE has a 56–58 band on `0x9E`. `0xA1` `ev_max=125` = no further upgrade.

`LASTYEAR.SAV` still has early huts: `0x83` +15=11, `0x84` 7…12 (above the stay band — mid-evolve or service-cap lag).

---

## 5. Achea id census (25 distinct; no Tent)

Housing **starts at `0x86`**. Dominant: `0xA1` 90, `0x89` 64, `0x8E` 63. Matches prints (insulae / palaces, not tents). Absent: `0x82–0x85`, `0x9C`, `0x9E`, `0xA0`.

`20230610.SAV`: 21 ids, 312 housing tiles; no Tent; same palace/villa sizes.

---

## 6. What to use

- **Name the stage** with the FAQ/directory string (Tent for `0x82`).
- **“Land value of this house type”** = directory / EXE **become** / **stay** band, not Achea `+15`.
- **Map overlay LV** = live `tile[+15]` after paint; varies by neighborhood; Achea’s save caught the wipe.
