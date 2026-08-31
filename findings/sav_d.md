# D.SAV — Well / Theater / Cleared / Rubble + factory column

Local file `findings/D.SAV` (gitignored; do not commit). Parser: `tools/_d_sav_dump.py`. Same chunk-13 walk as `sav_ab.md`.

**Not** an A/B/C continuation. Year-BC **33** (A/B/C are 36). Treasury **10899**, construction spend **1090**, sim phase **0**. Different generated grass than A (`0x05` / `0x1C` absent on A).

User labels at the north tip (same `(x,y)` as A/B/C) plus **eight** factories in one column, top→bottom.

| User | Map `(x,y)` | Id | Size | Notes |
|---|---|---|---|---|
| **Well** | (0,0) | **`0xD7`** | **1×1** | BUILD1B, type **`0x0F`**. Paints +13 **`0x02`** r=2 |
| **Cleared** | (1,0) | **`0x1C`** | 1×1 terrain | Unique on this save. A has **zero** `0x1C` |
| **Rubble** | (2,0) | **`0x05`** | 1×1 terrain | Unique. Only `id<8` on this map. `+3=0x42` `+4=0x6E` |
| **Theater** | (3,0) | **`0xE5`** | **2×2** | (3,0)–(4,1). BUILD1C, type **`0x13`**. Pair-1 small |

Factories: one merged **3×24** `0xFA` blob at `(9,0)–(11,23)`. Eight origins, **x=9**, y = 0,3,6,9,12,15,18,21. `+19` table: `findings/factory.md`.

---

## 1. Chunk 13 — north tip

File offset `50395 + (y*80+x)*20`.

```
(0,0) Well     D7 01 00 08 10 00 00 00 00 00 00 00 03 02 00 FA 00 00 00 00
(1,0) Cleared  1C 00 00 00 00 00 00 00 00 00 00 00 03 02 00 FD 00 00 00 00
(2,0) Rubble   05 00 00 42 6E 00 00 00 00 00 00 00 03 02 00 FD 00 00 00 00
(3,0) Theater  E5 01 00 0C 24 00 00 00 00 00 00 00 03 00 00 FD 00 00 00 00
(4,0)          E5 01 00 0C 26 01 00 00 00 00 00 00 03 00 00 FD 00 00 00 00
(3,1)          E5 01 00 0E 25 02 00 00 00 00 00 00 03 00 00 FD 00 00 00 00
(4,1)          E5 01 00 0C 27 03 00 00 00 00 00 00 03 00 00 FD 00 00 00 00
```

Ids `≥0x78` on this save: **`0xFA`×72**, **`0xE5`×4**, **`0xD7`×1**. Nothing else.

---

## 2. Well `0xD7`

1×1 BUILD1B (`+3=0x08`), `+4=0x10`, `+1=0x01` (same bit as Tent; **not** pipe `0x80`/`0x40`). Advisor type **`0x0F`** (`FUN_00012a8f`: `0xD7–0xDA`).

**Not** `0xBC–0xBD` / `0xCB`. Does **not** join the `+1 & 0xC0` aqueduct graph.

`FUN_0003fef7` paints ids `0xD7–0xDA` → +13 bit **`0x02`**, radius **2**. Observed: +13=`0x02` exactly on the Chebyshev r=2 corner `(0..2,0..2)`; Theater at x=3 is outside and stays 0. Old “Farms `0xD7–0xDA`” label is **retracted** — that painter is Well (and unseen siblings `0xD8–0xDA`).

`0xD8–0xDA` still unseen (same type / painter; **not** named).

---

## 3. Theater `0xE5`

**2×2** BUILD1C, type **`0x13`**. Origin NW `(3,0)`: `+5` lo-nibble 0,1,2,3 on the four cells; `+4` = `0x24`/`0x26`/`0x25`/`0x27`. Neighbours south/east of the stamp are grass (`0x15`/`0x08`/`0x0A`), not more `0xE5`. **Not** 3×3.

Closes pair-1 small (`build_palette.md` §4). Odeum `0xE6` stays the 2×2 large sibling (bigger +12 rings). +12 on the north tip is `0x03` (channel bits 0–1, near value).

---

## 4. Cleared `0x1C` / Rubble `0x05`

Both **terrain** (`id<0x78`). Each appears **once** on D and **never** on A.

| User | Id | +1 | +3 | +4 | Verdict |
|---|---|---|---|---|---|
| **Cleared** | **`0x1C`** | 0 | 0 | 0 | Flattened land. Clear-area **does** write `+0` |
| **Rubble** | **`0x05`** | 0 | `0x42` | `0x6E` | Only `id<8` on this map. `+4=0x6E` is also Reservoir dry |

Natural grass on both maps is `0x08–0x17`. River is still `+1 & 0x10` on that family, not `id<8` (`achea.md` §5). Retract “clear area does not stamp `tile[+0]`”.

---

## 5. Factory column

Origins (`0xFA`, `+5 & 0xF == 0`), north→south (increasing y, same x):

| y | `+19` | User |
|---:|---:|---|
| 0 | 1 | Winery |
| 3 | 3 | Tailor |
| 6 | 5 | Lead Works |
| 9 | 7 | Copper Works |
| 12 | 9 | Glass Works |
| 15 | 11 | Stone Works |
| 18 | 13 | Spice Dealer |
| 21 | 15 | Fish Monger |

Each 3×3 uses `+4=0x3E…0x46` and origin-only `+19`. Full nibble table: `findings/factory.md`.
