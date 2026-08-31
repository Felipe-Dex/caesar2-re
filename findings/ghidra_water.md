# Ghidra walk — water (reservoir / aqueduct)

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP HTTP `127.0.0.1:8080`). No EXE in git. Continues `findings/ghidra_tile.md` / `ghidra_sim.md` / `build_palette.md`. **Did not edit `app/`.** Saves stay local: Achea (`ACHEA23.SAV`, 9× `0xBE`), A/B pair, **20230610** (one `0xCB` stub), and **D.SAV** (Well `0xD7`). No SAV copied to git.

**Result:** water is **not** the +17 flood. A **pipe network** lives in `tile[+1]` bits `0xC0`: **`0x80` = Reservoir `0xBE`**, **`0x40` = aqueduct run `0xCF–0xD6` plus stub `0xCB`**. Placement rebuild (`FUN_00029e36`) injects **charge 3** into `+10` bits 0–1 on tiles next to river (`+1 & 0x18`), then walks the `0xC0` graph and **decays 3→2→1**. Charged `0xBE` then **paints `+13`** each sim cycle (wipe `0x51`, paint `0x56+`). **Well is `0xD7`** (D.SAV 1×1 BUILD1B): **not** on the pipe graph; paints +13 **`0x02`** r=2 (old “Farms `0xD7–0xDA`” label retracted). Fountain stages are named (`0xDD`/`0xDC`/`0xDE`; 3rd unseen, leftover **`0xDB`**). Do **not** call `0xCB` a Well — it is an aqueduct cap.

---

## 1. Two floods (do not mix)

| | **Water** | **+17 road-access** |
|---|---|---|
| Fn | `FUN_00029e36` (place-time) + painters `FUN_0003fdd0` / `FUN_0003fef7` | `FUN_000430da` phases `0xA2–0xC1` |
| When | **On place / tile update** (`FUN_00067a6a` → `29e36`). Charge is **saved** in `+10`. Painters re-read it every cycle | **Every** sim cycle, 4 scan directions |
| Source flag | `+1 & 0x18` (river `0x10` + undocumented `0x08`) | `+1 & 0x1E` (bits 1–4: queue `0x02`, `0x04`, `0x08`, river `0x10`) |
| Network flag | `+1 & 0xC0` | none — any `+1 & 0x1E` tile is a **100** seed |
| State | `+10 & 3` = charge **0–3**; wet sprite = `+4` bumped from dry `+9` | `+17` = **0–100** (or seed `0xF8` = −8) |
| Coverage | `+13` bits from charged `0xBE` (and others; §5) | distance-from-feature field; housing `FUN_00040d08` tests **signed `+17 > 15`** |
| `0xBE` at (0,0) A/B | `+1=0x80`, **`+10=0`**, dry `+4=+9=0x6E` — no river neighbour, no charge | `+17=0` (no cycle / not a `0x1E` source) |

`+1=0x80` is **invisible** to +17 (`0x80 & 0x1E == 0`). A charged reservoir can still show `+17=100` if a **road** neighbour leaked 100 onto it (Achea), or `0xF8` if it sits on open land.

Housing evolve uses **both**, independently: +17 for the road-access yes/no, +13 testers (`FUN_0006dba2`) for land-paint bits. They are not the same overlay.

---

## 2. Network flags (`tile[+1]`)

| Bit | Who (Achea + A/B) | Role |
|---:|---|---|
| **`0x80`** | **only** `0xBE` (9 on Achea; 1 on B) | Reservoir node. Walk **stops** here (`FUN_0002a635` RET after OR) |
| **`0x40`** | Achea: **only** `0xCF–0xD6` (25). 20230610 also **`0xCB`** (1) | Aqueduct run / stub. Walk **continues** |
| **`0x60`** | `0xD6` junctions (2 on Achea) | `0x40` + pad `0x20` |
| **`0x10`** | river terrain | Water **source** (`FUN_0002a18c` tests `+1 & 0x18` on cardinals) |
| **`0x08`** | undocumented | Also a `2a18c` source bit (bundled with river) |

Achea: **zero** `+1 & 0xC0` tiles outside `0xBE` / `0xCF–0xD6`. 20230610 adds one **`0xCB`** stub (`+1=0x40`) on the south face of a `0xCF` run — same pipe bit.

Advisor (`FUN_00012a8f`): `0xBE` → type **`0x10`**. `0xBC–0xBD` and `0xCB–0xD6` → type **`0x11`**. **`0xD7–0xDA` → type `0x0F` (Well `0xD7`)**. `0xCB` is an **aqueduct stub**, not Well. `0xCC–0xCE` still unnamed (Achea, 20230610, D.SAV have none).

---

## 3. Charge flood — `FUN_00029e36` `0x29E36`

Called from `FUN_00067a6a` `0x67A6A` when the tile has `+1 & 0xC0`. **Not** a `city_sim_phase` slot. `evolve_row` decays `+10` bits `0x0C` / `0x30` / `0xC0` only — **bits 0–1 persist**.

```
FUN_0002a209          ; clear 120-slot work list @ 0xCFB20
FUN_00029d75          ; if +1 & 0xC0: +10 &= ~3, +4 = +9 (dry), enqueue
loop FUN_0002a300 / FUN_00029f42   ; BFS along +1 & 0xC0
FUN_0002a407(EAX=3)   ; river-adjacent nodes: +10 |= 3, +4 += 3, state 5
FUN_0002a498(3, 1)    ; from state-5 / charge-3: walk, write charge 3 (no decay)
FUN_0002a498(3, 0)    ; from charge-3: walk, write charge 2
FUN_0002a498(2, 0)    ; from charge-2: walk, write charge 1
```

`FUN_0002a18c` `0x2A18C` (source test): any cardinal neighbour with **`+1 & 0x18`**.

`FUN_0002a0db` `0x2A0DB`: bitmask of cardinals that have **`+1 & 0xC0`** (N=1 S=4 E=2 W=8). Used to turn the walk.

`FUN_0002a635` `0x2A635`: step one tile, `+10 |= incoming`, bump `+4` from dry:

| Tile | Charge 3 | Charge 2 | Charge 1 |
|---|---|---|---|
| `+1 & 0x80` (reservoir) | `+4 += 3` then **stop** | `+4 += 2` | `+4 += 1` |
| else (aqueduct) | `+4 += 2` then **continue** | `+4 += 1` | `+4 += 1` if ≥1 |

Skip if existing `+10 & 3` ≥ incoming. Cap 1000 steps.

Short Achea spines are all **charge 3** (first pass fills the component; decay never wins). Isolated B.SAV `0xBE` at (0,0) stays **charge 0**.

---

## 4. Wet sprites (charge stored in `+4` vs dry `+9`)

`+9` keeps the dry variant. Flood adds 1/2/3 onto `+4`. A/B dry stamp: `+4 = +9 = 0x6E` → HOUSES1 sprite 90.

Achea `0xBE` (all charge 3):

| +9 (dry) | +4 (wet = dry+3) | n |
|---:|---:|---:|
| `0x6E` | `0x71` | 3 |
| `0x76` | `0x79` | 2 |
| `0x7A` | `0x7D` | 1 |
| `0x7E` | `0x81` | 3 |

Achea aqueducts (charge 3, non-`0x80` bump +2): `0xD0` dry `0x76` → wet `0x78`; `0xD1` `0x7C`→`0x7E`; `0xD6` `0x70`→`0x72`. CITYFIXT sheet `0x10`. **8** run ids `0xCF–0xD6`; Achea only uses `0xD0` (22), `0xD1` (1), `0xD6` (2). **`0xCB`** is a 1-tile **cap / incomplete stub** (20230610 (26,31): `+3=0x31` → sheet `0x10`, `+4=0x7B`, south `0xCF`). Not on Achea.

---

## 5. `+13` painters (each cycle, after wipe `0x51`)

`tile_or_radius` `0x6CD7E`: stack `(lane, bits)`, ECX = radius, EAX = extra. Lane `0xD` = +13.

### 5.1 `FUN_0003fdd0` `0x3FDD0` — phases `0x56–0x5D`

| Id | Need | Lane / bits | Radius (ECX) |
|---|---|---|---|
| **`0xBE`** | `+10 & 3` ∈ {1,2,3} | +13 **`0x04`** | charge **1→4, 2→5, 3→6** |
| `0xFC–0xFF` | — | +13 `0x40` | 2 |
| `0xFA` | — | +14 `0x20` r=4; +14 `0x10` r=2; +13 `0x80` r=1 | |

Charge **0** → skip (A/B origin `+13` stays 0).

### 5.2 `FUN_0003fef7` `0x3FEF7` — phases `0x6E–0x75`

| Id | Need | Lane / bits | Radius |
|---|---|---|---|
| Terrain **`0x1E–0x51`** | — | +13 **`0x02`** | 3 |
| **Well `0xD7–0xDA`** | — | +13 **`0x02`** | **2** |
| **`0xBE`** | `+10 & 3` ∈ {1,2,3} | +13 **`0x01`** | **charge 1/2/3** |
| `0xDB–0xDE` | `+13 & 4` | +13 `0x01` | 6 |
| `0xDF–0xE2` origin | `FUN_0006dba2` +13 `0x04` on a 2×2 | +13 **`0x08`** | 6, EAX extra 1 |

The A/B river band (`+13=0x02` on 429 tiles) is the **`0x1E–0x51` r=3** painter, not the (0,0) reservoir.

### 5.3 Achea live `+13` bit `0x04`

1139 tiles, Chebyshev distance to nearest charged `0xBE` is **0…6 only** — matches radius 6. 286 / 324 housing tiles have the bit; the 38 without are all **d = 7 or 8** (just outside the ring), including some `0xA1` palaces.

`+13` bits **`0x01` and `0x08` are 0 on every Achea house**. So the large splash (`0x04`, r=6) is what the city actually shows; the small `0x01` ring (r=1–3) does **not** reach the insulae.

---

## 6. Housing vs water (`FUN_00040d08` listing)

`FUN_0006dba2` tests **`tile[+13] & BL`** over an ESI×ESI block (ESI = size LUT `0x95063[id]`, else 1).

First housing gate (ids `0x82–0xA1`):

```
6dba2(+13, mask 0x02)   ; river-terrain splash
6dba2(+13, mask 0x01)   ; charged-reservoir small splash
if both 0: +15 target = 2
```

Later +13 masks in the same function: `0x80` (bad / warehouse), `0x08` (need), `0x10` / `0x20` / `0x40` (need / suppress). `+17 > 15` is a **separate** road-access rung, not these bits.

**Tension (leave open):** Achea palaces fail `0x01|0x02` and some fail `0x04`, yet sit at high ids. Either +15 has not been rewritten since they evolved, evolve-row does not instantly drop id, or the first gate is not “has fountain water.” Do **not** call `+13` bit `0x04` the house-water flag without a paused A/B that toggles one fountain.

---

## 7. Achea — 9 reservoirs, 3 spines

Local `ACHEA23.SAV` only (not in git). All nine `0xBE` have **`+1=0x80`**, **charge 3**, wet `+4 = +9+3`.

| (x,y) | River nb (`+1&0x18`) | Aqueduct nb | Notes |
|---|---:|---:|---|
| (65, 9) | 1 | 0 | Standalone on river |
| (61, 19) | 2 | 0 | Standalone on river |
| (64, 42) | 1 | 0 | Standalone on river |
| (46, 16) | 0 | 1 | Fed **only** by the y=16 spine |
| (56, 16) | 2 | 1 | River + spine |
| (58, 29) | 2 | 1 | River + y=30 spine |
| (64, 30) | 0 | 1 | Fed **only** by the y=30 spine |
| (45, 42) | 0 | 1 | Fed **only** by the y=42 spine |
| (56, 42) | 1 | 1 | River + spine |

Spines (all charge 3):

```
y=16: BE(46) — D0×5 — D6(52) — D0×3 — BE(56)
y=30: BE(58,29) / D1(58,30) — D0×4 — D6(63) — BE(64,30)
y=42: BE(45) — D0×10 — BE(56)     + standalone BE(64,42)
```

That is the fill rule in one city: **river-adjacent `0xBE` (or a `0xC0` tile next to `+1&0x18`) seeds charge 3; `0x40` aqueducts carry it to inland `0xBE`.**

Prints also show square pools / red-dome rotundas. Achea has **no** `0xBC–0xBD`, **no** `0xCB–0xCE`, and **no** `0xD7`. Fountain on Achea is **`0xDD`/`0xDC`/`0xDE`** (v3). **`0xCB`** on 20230610 is an aqueduct stub, not a basin. **Well is `0xD7`** (D.SAV). `0xBC–0xBD` remain type-`0x11` leftover. `0xDF`/`0xE0`/`0xE2` are 2×2 Baths that **read** `+13` bit `0x04`; **not** Well / Fountain.

---

## 8. Well `0xD7` — Fountain named, `0xCB` is not a Well

| Range | Advisor | Name | On Achea? | On 20230610? | On D.SAV? |
|---|---|---|---|---|---|
| `0xBC–0xBD` | `0x11` | UNKNOWN (not Well) | **no** | **no** | **no** |
| **`0xCB`** | `0x11` | **Aqueduct cap / stub** | **no** | **yes** (26,31) | **no** |
| `0xCC–0xCE` | `0x11` | unnamed (possible sibling stubs; **not** named) | **no** | **no** | **no** |
| `0xCF–0xD6` | `0x11` | Aqueduct run | **yes** | **yes** | **no** |
| **`0xD7`** | **`0x0F`** | **Well** | **no** | **no** | **yes** (0,0) 1×1 |
| `0xD8–0xDA` | `0x0F` | unseen Well siblings (not named) | **no** | **no** | **no** |
| `0xDD`/`0xDC`/`0xDE` | 8 | Fountain 1 / 2 / 4 | **yes** | — | **no** |
| Fountain 3rd | 8 | **unseen** (`0xDB` leftover in type 8) | — | — | **no** |

`FUN_00067a6a` can rewrite `0xC1`→`0xBD` / `0xC2`→`0xBC` when `+1` has `0x40|0x02`. That is a morph lead, **not** a Well name.

D.SAV Well does **not** set `+1` pipe bits. +13 `0x02` on `(0..2,0..2)` matches the `0xD7–0xDA` r=2 painter. Housing first gate (`0x02` river/well **or** `0x01` fountain/reservoir-small) can now be tested with this stamp.

Still useful: Fountain 3rd A/B (`0xDB` hyp). Palatine is a different A/B (forum size); it does not replace this.

`FUN_00070be8` dumps debug strings `"Water rate "` / `"Fountains "` — overlay text, not the flood.

---

## 9. Suggested names (not applied)

This pass did **not** rename in Ghidra.

| Name | VA |
|---|---|
| `city_water_rebuild` | `0x29E36` |
| `city_water_reset_tile` | `0x29D75` |
| `city_water_source_adj` | `0x2A18C` |
| `city_water_inject` | `0x2A407` |
| `city_water_propagate` | `0x2A498` |
| `city_water_walk` | `0x2A635` |
| `city_water_neighbors` | `0x2A0DB` |
| `city_paint_plus13_water` | `0x3FDD0` (`0xBE` → +13 `0x04`) |

---

## 10. Still unknown

- Well **`0xD7` closed**. `0xD8–0xDA` siblings unseen. `0xBC–0xBD` still unnamed type `0x11`.
- Fountain 3rd id (`0xDB` leftover in type 8). Whether Fountain paints `+13` `0x08` (or another bit) and at what radius.
- Whether `0xCC–0xCE` are other aqueduct-cap orientations (hyp only).
- Why Achea houses miss `+13` `0x01`/`0x08` while `0x04` matches r=6; how that sits with the `40d08` first gate.
- `+1` bit `0x08` as a water-source (bundled in `0x18` / also inside +17’s `0x1E`).
- Overlay index in `PTR_LAB_00099b3c` that draws water (`+10` stubs `0x3E763` / `0x3E7F5`; +13 stubs `0x3E6CD` / `0x3E907`).
- Full-map rebuild on load (charge is in the SAV; may not need one).

Do not start a crack session from the drive-letter strings.
