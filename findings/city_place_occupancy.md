# City place occupancy + Clear whole-building

Ghidra HTTP was down this pass. Listing from mapped `ghidra_work/c2_x.bin` (Capstone). No EXE in git.

**Host:** `app/place.py` — road skips occupied cells; Clear wipes the N×N from `+5`. Barracks/Reservoir stamp-follow preview unchanged.

---

## 1. Road occupancy — `FUN_000669c6` `0x669C6`

This function is a **3×3 neighbourhood retile**, not the click dispatcher. Callers: `0x66832` (flood `0x665DF`), `0x68E33` (rect after-clear).

Per tile (already `+1 & 0x20` pad):

| Check | VA | Effect |
|---|---|---|
| `+1 & 0x20` clear | `0x66A36` | skip |
| `+1 & 0x08` bank | `0x66A4B` | skip |
| river `+1 & 0x10` | `0x66A67` | remap `0x1E–0x2D` → bridge `0x4E–0x51` |
| `+1 & 0x40` pipe | `0x66B4D` | `FUN_00067a6a`; fail → clear pad |
| **`+0 >= 0x7C`** | **`0x66B8D`** | **do not write a road id** |
| else | `0x66B92` | gather mask `0x20` (`0x6ADB0`) + LUT `0x94AEF` → `DAT_00117a5e` |

**Rule in plain language:** a road graphic is never written onto plaza `0x7C`+ or any building id above that (housing `0x82+`, Barracks `0xE4`, Reservoir `0xBE`, aqueduct `0xCB`/`0xCF–0xD6`, …). The skip is **per cell** — the rest of a drag still stamps (same as curve / adjacent-bridge).

Gardens `0x78–0x7B` are **below** `0x7C`. The EXE will write a road id there if the tile is in this retile. Host matches that; do not invent a `≥ 0x78` road block.

Host road **place** (not only retile) now refuses `+0 >= 0x7C` before setting pad, so Barracks / aqueduct never become roads.

---

## 2. Clear whole footprint — `DAT_00094FE5` + `FUN_00069483` `0x69483`

Rect walker `0x68CDE` (city, stride 20):

```
if +1 & 0x10:  # river
    if also pad: restore +9, clear pad
    else skip
else if +0 >= 0x82:
    type = DAT_00094FE5[+0]
    if type == 0: FUN_000697fe flatten
    if type == 4:  FUN_00069483(tile, size=2)
    if type == 9:  FUN_00069483(tile, size=3)
    if type == 0x10: FUN_00069483(tile, size=4)
    else: FUN_000696e8  # 1×1 housing / BE / well / aqueduct segment
else:
    flatten via 697FE unless id < 8 and +3 has 0x40/0x80
```

`0x68D2F` is the split: **`+0 >= 0x82`** → collapse `696E8` (host rubble `0x05`); below that → flatten `697FE`. Gardens `0x78–0x7B` and plaza / join / statue `0x7C–0x7E` are **below** `0x82`, so Clear restores grass (`697FE` writes `0x1A + (LUT[0x93FCC]>>2)` = `0x1A–0x1D`; host `0x1C`). They do **not** leave rubble. Housing / fire still uses `696E8` / host `0x05`.

`FUN_00069483` (EAX = tile off, EDX = N):

```
piece = tile[+5] & 0xF
col = piece % N
row = piece / N
origin = tile - col*20 - row*80*20
for y in 0..N-1:
    for x in 0..N-1:
        FUN_000696e8(tile)   # wipe one cell
        tile += 20
    tile += (80-N)*20
```

Then extra pair-walk for Circus / C.Maximus ids `0xE9–0xF0` (second N×N). **Not ported.**

`FUN_0006985b` `0x6985B` is the **single-tile** wipe (restore river from +9). `FUN_00069963` is **province** demolish (`0xD94FC`), not city.

`DAT_00094FE5` sizes that match known footprints:

| Id | Type byte | N | Name |
|---|---:|---:|---|
| `0x82–0x9B` | 1 | 1 | housing 1×1 |
| `0x9C–0x9F` | 4 | 2 | villa |
| `0xA0–0xA1` | 9 | 3 | palace |
| `0xA6–0xA8` | 4 | 2 | Temple |
| `0xAA–0xAC` | 9 | 3 | Basilica |
| `0xAF` | 4 | 2 | Aventine |
| `0xB3` | 9 | 3 | Janiculan |
| `0xB7` | 16 | 4 | Palatine-ish |
| `0xBE` | 1 | 1 | Reservoir |
| `0xE3` | 1 | 1 | Praefecture |
| **`0xE4`** | **9** | **3** | **Barracks** |
| `0xE8` | 9 | 3 | Colosseum |
| `0xED–0xF0` | 16 | 4 | C.Maximus family |
| `0xCB` / `0xCF–0xD6` | 1 | 1 | aqueduct **segment** (not the whole run) |

Host Clear of a building still writes rubble **`0x05`** (D.SAV / user). `696E8` writes `rng>>1` terrain (fire/collapse). Do not replace 0x05 with that rng this pass.

Aqueducts are a **network of 1×1** in this table. Clearing one stub does **not** wipe the pipe run.

---

## 3. Still TODO (construction rules)

- Player click dispatcher that **first** sets pad `+1 |= 0x20` (669C6 only retiles existing pad). Occupancy `≥ 0x7C` is pinned; the exact “refuse whole stroke vs skip cell” UI ding is not.
- Road cost (city slot still unpinned).
- Circus / C.Maximus **pair** wipe after `69483` (`0xE9–0xF0`).
- Wall / gate / plaza stamp occupancy (plaza **is** `0x7C` — blocked for roads).
- Housing-on-road / garden-on-building beyond the civic skip already in `_civic_kind`.
- Tent splash `+15` 2×2 (C.SAV).
- Full aqueduct LUT `0xCF–0xD6` (only stub / NS / EW / junction ported).
- Forum / entertainment / worship / education stamps.
- `696E8` rng terrain vs host rubble `0x05` if a surgical Clear A/B ever disagrees.
