# Housing merge (villa 2×2 / palace 3×3)

Evidence: `FUN_00042b75` `0x42B75` (up), `FUN_00042bc4` `0x42BC4` (pick a block), `FUN_00042c7f` `0x42C7F` (2×2), `FUN_00042d0d` `0x42D0D` (3×3), `FUN_00042e25` `0x42E25` (stamp), `FUN_00042f71` `0x42F71` (split villa → Grand domus), size byte `DAT_00094f40[grade*4]`, neighbor LUTs `0x99B64` / `0x99B94`, gfx addends `0x9422C` / `0x94230`. Evolve gate: `city_buildings_evolve_row` `0x42360` (only `+5 & 0xF == 0`). Saves: `ACHEA23.SAV`, `20230610.SAV`, `FELIPE02.SAV`. Numbers + VAs only; no EXE/SAV in git.

Related: `findings/housing_land_value.md` (stay bands). Size table: `0x82–0x9B` = 1×1, `0x9C–0x9F` = 2, `0xA0–0xA1` = 3.

---

## 1. Rule

A house **evolves in place** until the next grade’s footprint is bigger. Then `42b75` calls `42bc4(new_grade, new_size)` and, on success, `42e25` overwrites an N×N from a chosen **NW origin**.

**Villa (`0x9B` → `0x9C`, size 1→2).** The firing tile is any 1×1 origin (`+5` lo-nibble 0) whose `+15` is **above** the stay max (52). It is **not** allowed on the map edge (`x` or `y` in `{0,79}`). The EXE tries the four 2×2 that contain that tile, in this order:

| Try | Block (relative to firer) | Firer is | Origin |
|---|---|---|---|
| 0 | SE: `(x,y)…(x+1,y+1)` | NW | firer |
| 1 | SW: `(x-1,y)…(x,y+1)` | NE | 1 west |
| 2 | NW: `(x-1,y-1)…(x,y)` | SE | 1 west + 1 north |
| 3 | NE: `(x,y-1)…(x+1,y)` | SW | 1 north |

First fully valid block wins. **Not** even-aligned; any 2×2.

Each of the **three other** tiles must have `+7==+8==0` (no walkers), `+1` in `{0,1}` (no road/garden/pad bits), and if `+1==1` then **id < `0x9C`**. So: vacant `+1==0` **or** any housing below villa. **Not** required to be Grand domus, **not** required to share the firer’s `+15` band, **not** a separate road-access test (`+17` only matters earlier, via the service cap on `+15`).

**Palace (`0x9F` → `0xA0`, size 2→3).** Only the **villa origin** fires. The existing 2×2 (the other three tiles at `+1x / +1y / +1x+1y`) is **not** re-checked. The EXE tries the four ways to sit that 2×2 inside a 3×3 (villa as NW / NE / SE / SW of the palace) and validates only the **five new** tiles, same walker/`+1`/id&lt;`0xA0` test. Firer must be in `x,y ∈ 1…77`. Overlapping villas on those five tiles are split back to `0x9B` (`42f71`, origin recovered from `+5 % 2` / `+5 / 2`) then overwritten.

**Who fires first:** `city_sim_phase` sets row = `phase − 1` for phases `1…0x50`, then `x = 0…79`. Northern row, then western tile. Fillers never evolve. If two valid 2×2 exist for one firer, **SE wins**.

---

## 2. How the SAV marks the group

All N×N cells share the **same** `+0` id (not mountain-style piece ids).

| Byte | Meaning |
|---|---|
| `+0` | Stage id on every cell (`0x9C–0x9F` villa, `0xA0–0xA1` palace) |
| `+5` lo-nibble | Piece index, **row-major from NW**: villa `0,1 / 2,3`; palace `0,1,2 / 3,4,5 / 6,7,8`. **Origin = 0** |
| `+4` | Graphic = `DAT_00094f3f[grade*4]` + addend. 2×2 addends `(0,2 / 1,3)`. 3×3 `(0,2,5 / 1,4,7 / 3,6,8)` |
| `+1` | `\| = 1` on every cell after stamp |

To list a building: find `id ∈ 0x9C…0xA1` with `+5 & 0xF == 0`, then walk `size×size` east/south. Achea: every villa/palace matches this (14 origins, 0 mismatches).

---

## 3. Achea examples

**Grand villa** origin `(62,25)` `0x9F`: tiles `(62,25)+5=0`, `(63,25)+5=1`, `(62,26)+5=2`, `(63,26)+5=3`; `+4` = 38,40,39,41. All four `+1=0x01`. Cannot become palace: east face is Large palace `(64,25)`, other rings are road/`+1` bits.

**Large palace** origin `(64,21)` `0xA1` (one of ten 3×3):

```
(64,21)+5=0  (65,21)+5=1  (66,21)+5=2
(64,22)+5=3  (65,22)+5=4  (66,22)+5=5
(64,23)+5=6  (65,23)+5=7  (66,23)+5=8
```

`+4` = 51,53,56 / 52,55,58 / 54,57,59. Origins also at odd coords (`67,17` …) — not a parity grid.

Leftover **Grand domus** (12 on Achea, **zero** complete 0x9B 2×2): e.g. `(63,21)` cannot take SE (palace `0xA1`) or SW (terrain `+1=0x18`). Neighbors that *would* absorb: any housing `< 0x9C` or `+1==0`; roads `0x52–0x5C` / plazas `0x7C–0x7E` fail on `+1=0x20`.

`FELIPE02` villa `(28,39)` `+15=60` has a valid palace ring of five `0x9B` to the west (try 1) but **does not** upgrade: stay max for `0x9F` is 60, and up requires `+15 > max`. Neighbor LV is irrelevant; the origin (max of the 2×2 via `FUN_0006db08`) is the gate.

---

## 4. Open

Did not catch a merge mid-tick. Placement order and raster firer are from the EXE, not inferred from a before/after pair. `+1==0` non-housing is legal in the predicate (Achea `0x78`/`0x7B` next to `(63,21)` would pass); no saved villa still *shows* those ids because the stamp overwrites them.
