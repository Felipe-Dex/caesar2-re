# Factory `0xFA` + goods nibble

Saves: `20230610.SAV` (OneDrive), Achea, **`findings/D.SAV`**. Parsers: `tools/_20230610_factory_dump.py`, `tools/_d_sav_dump.py`. Engine: `findings/ghidra_tile.md` §9 (`FUN_00041b33`).

**One building id.** Every factory / workshop is **`0xFA`** (3×3 BUILD1C). The product is **not** a second building and **not** `+4`. It is **`tile[+19] & 0x0F` on the origin tile only**.

---

## 1. Scheme

| | |
|---|---|
| Id | **`0xFA`** on all 9 cells |
| Footprint | **3×3**. Adjacent stamps merge in a 4-conn flood (20230610: one **9×3**; D.SAV: one **3×24** = eight factories) |
| Origin | NW cell: **`+5 & 0xF == 0`**, `+4 = 0x3E` |
| Goods | **origin `+19` lo-nibble** (0–15). Other 8 cells have `+19 = 0` |
| `+4` | Sheet cell 0x3E–0x46 (one each per 3×3). Same on Bakery / Winery / Ivory. **Not** the subtype |
| Overlay | `city_tile_draw_flag80`: frame = `(+19 & 0xF) + 9` on the origin |

`FUN_00041b33` (only from `FUN_00041719`, id `0xFA`, origin tile): `+19 & 0xF` indexes `goods_16x48` at `0xD2B6C` (stride 48). Writes production into **`+9`**, not back into +19.

User coords on this save were **`(y,x)`** except Excel **T66 = map (18,64)**.

---

## 2. `+19` table

EXE debug strings at `0x90FB5`…`0x91087` (`"… sup/sat"`) are the 16 goods **in nibble order**. UI factory names from Achea + 20230610 + D.SAV.

| `+19` | EXE good | UI factory | Conf | Origins |
|---:|---|---|---|---|
| **0** | grain | **Bakery** | HIGH | 20230610 (44,67), (47,67), (27,74) |
| **1** | grapes | **Winery** | HIGH | 20230610 + Achea + **D.SAV (9,0)** |
| **2** | cattle | **Butcher** | HIGH | 20230610 (35,70); also (50,56) — user said Bakery, hex matches Butcher |
| **3** | timber | **Tailor** | HIGH | **D.SAV (9,3)** |
| 4 | gems | — | EXE only | — |
| **5** | lead | **Lead Works** | HIGH | Achea + **D.SAV (9,6)** |
| 6 | iron | — | EXE only | — |
| **7** | copper | **Copper Works** | HIGH | **D.SAV (9,9)** |
| 8 | clay | — | EXE only | — |
| **9** | sand | **Glass Works** | HIGH | **D.SAV (9,12)** |
| 10 | marble | — | EXE only | — |
| **11** | stone | **Stone Works** | HIGH | 20230610 (35,74), (48,74) + **D.SAV (9,15)** |
| 12 | silk | — | EXE only | — |
| **13** | spices | **Spice Dealer** | HIGH | **D.SAV (9,18)** |
| **14** | ivory | **Ivory Dealer** | HIGH | 20230610 (17,63) — T66 / (18,64) |
| **15** | fish | **Fish Monger** | HIGH | **D.SAV (9,21)** |

**Leftover nibbles (EXE good only, no UI name):** **4** gems, **6** iron, **8** clay, **10** marble, **12** silk.

D.SAV (`findings/sav_d.md`): one **3×24** blob `(9,0)–(11,23)`, eight origins at **x=9**, y step 3. User top→bottom = Winery, Tailor, Lead, Copper, Glass, Stone, Spice, Fish = odd nibbles **1,3,5,7,9,11,13,15**.

---

## 3. User factories → origin

| User name | User coord | Map (x,y) | Origin | `+19` |
|---|---|---|---|---|
| Ivory Dealer | T66 / (18,64) | (18,64) | (17,63) | **14** |
| Bakery | (75,28) | (28,75) | (27,74) | **0** |
| Stone Works | (75,36) | (36,75) | (35,74) | **11** |
| Butcher | (71,36) | (36,71) | (35,70) | **2** |
| Winery OK | (68,41) | (41,68) | (41,67) | **1** |
| Bakery | (68,46) | (46,68) | (44,67) | **0** |
| Bakery | (68,48) | (48,68) | (47,67) | **0** |
| Bakery | (57,51) | (51,57) | (50,56) | **2** (Butcher, not Bakery) |
| Winery OK | (53,51) | (51,53) | (50,52) | **1** |
| Winery OK | (49,51) | (51,49) | (50,48) | **1** |

The 9×3 at (41,67)–(49,69) is Winery \| Bakery \| Bakery.

D.SAV column (user top→bottom, x=9): Winery **1** · Tailor **3** · Lead **5** · Copper **7** · Glass **9** · Stone **11** · Spice **13** · Fish **15**. See `findings/sav_d.md`.

---

## 4. 20230610 D2–D8 (not factories)

Yellow `Desconhecido N` on `findings/20230610_grid.xlsx`. User names match the hyp ids except D6.

| N | User | Id | Size | Origin | Verdict |
|---|---|---|---|---|---|
| **D2** | Market hardly used | **`0xFC`** | 2×2 | (39,39) | Market **1** (Achea hyp closed) |
| **D3** | Palatine 4th | **`0xB9`** | 4×4 | (34,43) | Palatine **4** |
| **D4** | Temple 2nd | **`0xA7`** | 2×2 | (42,50) | Temple **2** |
| **D5** | Temple 2nd | **`0xA7`** | 2×2 | (50,61) | same |
| **D6** | Baths 4th | **`0xE1`** | 2×2 | (24,62) | **Baths 3** — same id as D8. Baths 4 is already **`0xE2`** (named, not yellow) |
| **D7** | Temple 2nd | **`0xA7`** | 2×2 | (32,64) | same |
| **D8** | Baths 3rd | **`0xE1`** | 2×2 | (28,68) | Baths **3** |

**D1 closed.** `0xCB` 1×1 at **(26,31)**. CITYFIXT (`+3=0x31` → sheet `0x10`), `+1=0x40`, `+4=0x7B`. South neighbor `(26,32)` = **`0xCF`** (`+1=0x40`). User: **incomplete aqueduct / cap / stub**. **Not** Well. `0xCC–0xCE` absent on this save.

**Yellow leftover on this save: none.** D2–D8 were already named. Well **`0xD7`** and Theater **`0xE5`** closed on **D.SAV** (`findings/sav_d.md`). This 20230610 map still **lacks** Fountain 3rd, Arena, Palatine 1/3, Temple 4 — those ids are **absent**, not unnamed blobs.

This save has no `0xA8`/`0xA9` (Temple 3/4), no `0xB6`–`0xB8` (Palatine 1–3), no `0xE5`/`0xE7`.
