# Achea — screenshot + SAV naming workflow

Local files only. **Not in git.** Do not copy the save or the prints into the repo.

| | |
|---|---|
| Folder | `C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\` (a **directory**, not a `.SAV`) |
| Save | `ACHEA23.SAV` — **225745** B, 29 Aug 2026 22:42 |
| Prints | six Magic DosBox JPGs, same minute (`Screenshot_20260829_223511` … `223623`) |
| Parser | `app/city_map.py` `load_city_from_sav` — 500 sequential `SavChunk`s, map = chunk **13** |
| Iso (gitignored) | `sav_preview/Achea_iso.png` (thumb) + `sav_preview/Achea_iso_full.png` (4640×2400) |
| Palette names | `findings/build_palette.md` (sibling; not overwritten) |

**Workflow verdict: yes.** One mid-game city plus paused city-view prints is enough to *confirm* closed ids (`0x82–0xA1` housing, `0xBE` Reservoir, aqueducts, river-as-flag) and to *shortlist* entertainment / wall / farm blobs. Grid Q&A named Temple / Circus / Market / Baths / Praefecture, then Janiculan / Barracks / Basilica / Hospital / Library / Aventine (`§9`), then the v3 dump closed Palatine / Garden / Plaza / Road-as-terrain / stages (`§10`). Hex still cannot see the building; the prints cannot see tile ids.

---

## 0. What the prints show

All six shots are the same paused session (Magic DosBox on Android chrome: `esc` / `espaço`).

| UI | Value |
|---|---|
| Date | **187 BC January** |
| Treasury | **28561 Dn** |
| Overlay | **Unrest** (sidebar, above minimap) |
| Banner | **Game Paused** |
| View | city iso, several camera pans + one closer housing zoom |
| City name on HUD | **not printed** — name is the folder / assignment (`Achea` = Achaea) |

Visible city (developed, not a Novice stamp):

- Dense **red-roof insulae** / multi-storey housing; the last print is a close-up of those, **not** vacant brown tents.
- **Circular Coliseum / arena** (at least one, some pans look like two).
- Long **Circus / C.Maximus** oval.
- **Stone wall** + towers / gate on the developed edge.
- **Aqueduct** spine + several **circular / square water basins** (Reservoir / Fountain / Well lookalikes).
- White-column **forums / temples**.
- Square **fort / barracks** enclosure on one pan.
- Peripheral **warehouses / granaries** and a winding **blue river** on the minimap (city packed in the upper-right quadrant).
- Some houses show **blue hover icons** (water / unrest overlay, not a building id).

---

## 1. SAV scalars that match the HUD

`ACHEA23.SAV` is a real 1.1A named save (`221745 + 4000`). Chunk 13 is 80×80×20. **91** live walkers in chunk 8.

| Chunk | Field | Value | Print |
|---:|---|---:|---|
| **28** | `city_treasury` | **28561** | **28561 Dn** |
| **25** | signed i32 | **−187** | **187 BC** |
| 5 | old “year-BC” hypothesis | **65** | does **not** match 187 |
| 16 | difficulty | **2** | not on HUD |
| 0 | view kind | 0 | city view |

**Year is chunk 25 as a signed BC year, not chunk 5.** FELIPE / A–C notes that treated chunk 5 as year-BC do not survive this save. Month (January) was not pinned this pass.

No ASCII `"Achea"` in the file. The city name lives in the filename / career slot, not as a readable string in the 500-chunk stream.

---

## 2. `tile[+0]` histogram

6400 tiles, **146** distinct ids. Terrain (`< 0x78`) **4968**. Buildings (`≥ 0x78`) **1432**.

### Closed / range totals vs the prints

| Class | Count | Match? |
|---|---:|---|
| Housing **`0x82–0xA1`** | **324** | **yes** — dense evolved city |
| First housing **`0x82` Tent** | **0** | prints show insulae, not tents |
| Forums **`0xA2–0xA8`** (HOUSES1 civic) | **48** | **split** — `0xA6–0xA8` is **Temple** (`§9`). Aventine is **`0xAF`** (type 7, not this range). `0xA2–0xA5` still unnamed 1-tile |
| **`0xBE` Reservoir** | **9** | **yes** — several basins; see §3 |
| Water ids **`< 8`** | **0** | **no** as raw `+0` |
| River **flag `+1 & 0x10`** | **212** | **yes** — winding river, bbox x=50…72, full height |
| Aqueduct **`0xCF–0xD6`** (CITYFIXT) | **25** (22×`0xD0`) | **yes** — visible spine |
| Plaza/wall sheet **`0x78–0x7E`** | **135** | **yes** — paved roads + stone wall |
| Industry **`0xAE–0xB9`** | **107** | type-7 forums: **`0xAF` Aventine**, **`0xB2–0xB4` Janiculan**, **`0xB7` Palatine**; leftover `0xAE`/`0xB0` |

Housing **starts at `0x86`**, not `0x82`. Top housing ids: **`0xA1` 90** (3×3 palace-grade clumps at x=64…69), **`0x89` 64**, **`0x8E` 63**. That is the close-up print: red-tile insulae / palaces, HOUSES1 sheet. `housing_grade` is still mostly `0` (277/324) — grade byte ≠ evolve id.

### Top building ids (count)

| Id | n | Sheet | Hypothesis (palette + Achea shape) |
|---|---:|---|---|
| **`0xFA`** | 135 | BUILD1C | large 3×3 / 3×6 / 9×3 pads in the built city — **not** named; farms-or-industry leftover, not Tent/Reservoir |
| **`0xFB`** | 108 | BUILD1B | **Hospital** (grid N=173 and N=179). Same id on every SW 3×3 / 6×3 blob |
| **`0xA1`** | 90 | HOUSES1 | top housing grade (3×3 palace clumps) |
| **`0xF5`** | 72 | BUILD1B | **Library** (grid N=174). Same id on every SW 3×3 / 6×3 blob |
| **`0x7C`** | 65 | BUILD1A | **Road** (screenshot Q&A) — interior 1-wide runs; type `0x0E` |
| **`0x89` / `0x8E`** | 64 / 63 | HOUSES1 | mid housing (insulae) |
| **`0xC1`** | 48 | BUILD1B | **1-wide strip at x=78** — N–S Wall family (geom); E–W Wall is **`0xC2`** |
| **`0xE4`** | 45 | HOUSES1 | **Barracks** (grid N=9). Five 3×3. Sibling of Praefecture `0xE3` |
| **`0xF3`** | 40 | BUILD1B | city-area, unnamed |
| **`0xE8`** | 27 | BUILD1C | **Colosseum / Coliseum** (screenshot Q&A) — three **3×3** at (71,13), (64,31), (50,34) |
| **`0xAB`** | 27 | BUILD1C | three **3×3**. **Basilica only** (`§9`) — Janiculan name dropped. Sibling `0xAC` 3×3 at (71,41) same family |
| **`0xB3`** | 27 | BUILD1A | **Janiculan** (grid N=8). Three 3×3. Type 7, not the old `0xAA–0xAC` size-split |
| **`0xB2`** | 27 | BUILD1A | 3×3 pair next to Janiculan — still unnamed |
| **`0xD0`** | 22 | CITYFIXT | aqueduct run |
| **`0xA3`** | 22 | HOUSES1 | forum-family, many 1-tile stamps (grades / corners) |
| **`0xED` / `0xEE`** | 16 / 16 | BUILD1D | one **4×8** C.Maximus at (71,25)–(74,32) (two 4×4 halves). Screenshot Q&A **HIGH** |
| **`0xBE`** | 9 | HOUSES1 | Reservoir (A/B closed) |
| **`0xE9` / `0xEA`** | 9 each | BUILD1D | leftover +12 3×3 (still unnamed) |
| **`0xEB` / `0xEC`** | 9 / 9 | BUILD1D | one **3×6 Circus** at (62,2)–(67,4) (two 3×3 halves). Grid Q&A **HIGH** — **not** C.Maximus |

`0xBF` is **Tower** (screenshot Q&A **HIGH**), not Barracks. Four 1×1 rim cells: **(78,1)**, **(55,1)** (by the river), **(72,52)**, **(78,52)**. **Barracks is `0xE4`** (grid N=9). The print’s walled square may be that 3×3 plus Wall, not a separate id.

---

## 3. Reservoir `0xBE` vs the basins in the prints

Nine tiles, all HOUSES1, variants **`0x71` / `0x79` / `0x7D` / `0x81`** → sprites 93 / 97 / 101. **Not** the surgical empty-map stamp (`+4=0x6E` → sprite 90). Same id, later orientations / states.

Prints also show **square blue pools** and **red-dome rotundas**. Fountain on this save is **`0xDD`/`0xDC`/`0xDE`**. **Well is `0xD7`** (D.SAV; Achea has none). **`0xCB` is an aqueduct cap / stub**, not a Well (20230610 D1). Achea has **no** `0xBC–0xBD` and **no** `0xCB–0xCE`.

---

## 4. What the screenshots give that hex does not

- **Identity of landmarks** — Coliseum oval vs Circus track vs wall vs aqueduct. Hex only has counts and bboxes.
- **Evolve state of housing** — “these are insulae, not tents.” Hex agrees (`0x82=0`, `0xA1` dominant) but cannot *show* the red roofs.
- **Active overlay** — Unrest, pause, which build-menu icon is lit (Forum on the first shot).
- **Camera / which district** — six pans cover the walled core, the water spine, and a housing close-up. One SAV is the whole 80×80; without prints you cannot tell which blob is “the circus I am looking at.”
- **HUD cross-check** — treasury and year lock two scalar chunks in one shot.

Hex still wins on: exact id, sheet, variant, river-as-flag (the river is **not** `+0 < 8`), walker count, and “there are zero tents.”

---

## 5. Remaining mismatches

1. **Water ids `< 8` are empty.** The river is `tile[+1] & 0x10` on grass-family terrain (`0x08–0x17` dominate the histogram). Do not hunt `0x00–0x07` on this map.
2. **`0x82` Tent is absent.** The range `0x82–0xA1` is full; the *first* id is not. Naming from a developed city will miss vacant-tent art.
3. **Coliseum / C.Maximus / Circus closed on this save.** `0xE8` = Colosseum (3× 3×3). `0xED`+`0xEE` = one 4×8 C.Maximus. `0xEB`+`0xEC` = one 3×6 Circus (grid Q&A). The old “too square” note was two halves of the oval.
4. **Fort in the print ≠ `0xBF`.** `0xBF` is **Tower**. **Barracks is `0xE4`** (grid N=9). The print’s walled square may be that 3×3 plus Wall.
5. **Well `0xD7` closed** on D.SAV (`findings/sav_d.md`). Fountain / Plaza / Gardens / Road-as-terrain named in §10. **`0xCB` = aqueduct stub** (20230610), not Well. `0xC1` (N–S rim) is geometry-only.
6. **Host iso** is the full 80×80 (thumb 960×497). It matches the *minimap shape* (four clusters + river) but is too small to read individual buildings the way the DosBox pans do.
7. **City name** is not in the SAV body.

---

## 6. Does the format work?

**Yes, as a confirmation + shortlist loop:**

1. Pause, screenshot the city (and one Query hover if possible).
2. Save. Keep the `.SAV` **next to** the prints in a folder named after the city — `Achea.sav\ACHEA23.SAV` + JPGs is a good pack.
3. Parse chunk 13; histogram `+0`; render `sav_preview/<name>_iso.png` (gitignored).
4. Lock HUD scalars (treasury, year) first, then check closed ranges, then only then guess new ids.

It does **not** replace a surgical empty→one-building pair for UNKNOWN palette buttons (`build_palette.md` §5).

### Ask the user next (if still ambiguous)

1. Optional leftover civic: **D98 `0xE9`** / **D110 `0xEA`** (3×3 +12) — Theater is **`0xE5`** (D.SAV); these may be Arena / other.
2. Optional: **D138 `0xA2`** / **`0xA3`** blobs — hyp Shrine 1/2 (later named in §11).
3. Optional: Fountain 3rd (`0xDB` leftover in type 8) or Well siblings `0xD8–0xDA`.

Do not commit `ACHEA23.SAV`, the JPGs, or `sav_preview/`.

---

## 7. Q&A protocol (prints → tile)

Iso math (`render_iso`): `(0,0)` = north tip; **right** = `x−y`; **down** = `x+y`. So visual **top-right / NE** is **high x, low y** (east). **`(0, max y)` is the west tip**, not NE. Occupied buildings are `x=1…79`, `y=1…78` — **no** tile at `x=0` or `y=79`.

Ask **one** landmark per print. Reply with the print + “yes / no / other (what?)”. We already have the id; you name what you see. Do **not** treat our id as a name.

| Ask | Tile | Id | Sheet | Footprint | Answer (2026-08-30) |
|---|---|---|---|---|---|
| **“tile (78,1) id 0xBF — is this your Tower?”** | `(78,1)` | **`0xBF`** | BUILD1B | **1×1** | **Yes — Tower.** Also `(55,1)` (by the river). Siblings `(72,52)`, `(78,52)`. **Not** Barracks. |
| **“the 4×8 at (71,25) ids 0xED / 0xEE — is this the long Circus oval?”** | `(71,25)` then `(71,29)` | **`0xED` + `0xEE`** | BUILD1D | two **4×4** = **4×8** | **Yes — C.Maximus.** User also said 4×2 (iso). Short sides face ±y. |

**River (closed as flag, not a Q):** **yes.** `tile[+1] & 0x10`, **212** tiles, bbox **x=50…72, y=0…79** (every row, 1–10 tiles). `+0` is grass-family (`0x1E–0x39`), **zero** `id<8`. Matches the winding blue band on the iso / minimap. Overlay: `sav_preview/Achea_river.png` (gitignored).

One-shot dumps: `tools/_achea_qa.py` (river + corners); `tools/_achea_label_dump.py` (this Q&A). Both read `ACHEA23.SAV` in place, do not copy it.

---

## 8. Screenshot Q&A 2026-08-30 (HIGH unless coords miss)

User named landmarks from the same Achea prints. Hex = chunk 13. **Iso “above” = decreasing `x+y` = decreasing y at fixed x** (screen-top is north tip). Confirmed by the stack sitting at x≈71 above the circus.

### 8.1 Tower `0xBF` — HIGH

| Tile | Id | Sheet | `+4` |
|---|---|---|---|
| **(78,1)** | **`0xBF`** | BUILD1B | `0x9B` |
| **(55,1)** | **`0xBF`** | BUILD1B | `0x96` |
| (72,52) | `0xBF` | BUILD1B | `0x96` |
| (78,52) | `0xBF` | BUILD1B | `0x9C` |

Four isolated 1×1, all the same id. User: both northern cells are **Tower** (second by the river). **`0xBF` = Tower, not Barracks.** Palette FELIPE01 Barracks label is **wrong**.

### 8.2 Wall + Gate on y=1, x=55…78 — HIGH

Walk y=1:

| x | Id | n on this line |
|---|---|---:|
| 55 | `0xBF` Tower | 1 |
| 56–69 | **`0xC2`** | 14 |
| **70** | **`0xC0`** | **1** |
| 71–77 | **`0xC2`** | 7 |
| 78 | `0xBF` Tower | 1 |

User: line connecting the towers = **Wall**. Near middle, closer to 78 = **Gate** (Wall+Road together).

- **Wall (E–W) = `0xC2`.** 21 tiles on this run. Same id again at (73,52)–(77,52) between the southern towers. Map-wide `0xC2` = 26, all on those two tower-to-tower lines.
- **Gate = `0xC0`.** Unique on the north line at **(70,1)** — 8 tiles from (78,1), 15 from (55,1). `+1=0x24`, `+3=0x88`, `+4=0x93` (wall `0xC2` is `+1=0x02`, `+4=0x04`). Two more `0xC0` on the east rim: **(78,24)** and **(78,40)**, each interrupting the `0xC1` strip — same gate sprite family (`+1=0x24`, `+3=0x88`).
- **`0xC1`** = 1-wide strip at **x=78** (48 tiles, broken by the two east gates). Same sheet / flags as `0xC2`, N–S orientation. User did **not** name it today. Geometry says Wall (N–S). Leave one notch below HIGH.

Old wall hyp `0x7C–0x81` (advisor type `0x0E`, BUILD1A) is **not** this perimeter. Those ids are the interior strip — see Road.

### 8.3 C.Maximus `0xED`+`0xEE` — HIGH

| | |
|---|---|
| Origin | **(71,25)** |
| Bbox | **(71,25)–(74,32)** |
| Size | **4×8** (x-span 4, y-span 8). User also said 4×2 (iso). |
| Halves | `0xED` 4×4 at (71,25)–(74,28); `0xEE` 4×4 at (71,29)–(74,32) |
| Sheet | BUILD1D |

Only elongated entertainment blob. Short sides face **±y** (north y=25, south y=32). Long sides face ±x.

`0xED` and `0xEE` are **two halves of one C.Maximus**, not Circus vs Temple (`build_palette.md` §4 pair table was wrong on that split).

### 8.4 Road beside the short side — HIGH for these tiles

North short face (y=24, x=71–74) is **terrain** (`0x53`), not a building id. The paved strip the user called **Road** is **`0x7C` / `0x7E`** (and `0x7D` at junctions) along **x=70** and the y=24 crossing just west of the circus. BUILD1A, `+1=0x20`.

**Retracted in §10:** those `0x7C`/`0x7E` tiles are **Plaza** (BT column). Real Road on this save is terrain + pad (`0x52`/`0x53`/`0x54` at BT4:BT7). Perimeter Wall is `0xC2`/`0xC1`.

### 8.5 Stack “above” the circus (decreasing y)

Iso-above = **decreasing y** at x≈71. Civic column:

| y | Origin | Id | Size | User name today |
|---|---|---|---|---|
| 25–32 | (71,25) | `0xED`+`0xEE` | 4×8 | C.Maximus |
| 24 | x=70 | `0x7C`/`0x7E` | 1-wide | Road |
| **20–23** | **(71,20)** | **`0xB7`** | **4×4** | user guessed Palatine **(71,22)** — **coords land here** |
| 17–19 | **(71,17)** | **`0xAB`** | **3×3** | Basilica (first) / or Palatine if size-only |
| 16 | — | terrain / `0x7E` | gap | |
| 13–15 | **(71,13)** | **`0xE8`** | **3×3** | **Colosseum** |
| 10–12 | **(71,10)** | **`0xAB`** | **3×3** | Basilica (second) |

**Colosseum `0xE8` at (71,13) — HIGH** for this cluster. Two more `0xE8` 3×3 at (64,31) and (50,34) (prints: “at least one, maybe two”).

**Basilica = `0xAB` on this stack — HIGH for the cluster names.** Both 3×3s above/below the Colosseum are the **same id** `0xAB` (variants 9–17, BUILD1C). A third `0xAB` 3×3 sits at (50,4); one `0xAC` 3×3 at (71,41). No `0xAA` on this save.

### 8.6 Palatine 3×3 vs 4×4 — CONFLICT, not HIGH

User today: beside the short side, Road then a **3×3 Palatine Forum**, guess **(71,22)**. Yesterday: Palatine **4×4**, Janiculan **3×3**, Aventine **2×2**.

Hex at the guess:

| | |
|---|---|
| **(71,22)** | **`0xB7`**, BUILD1A, **4×4** bbox **(71,20)–(74,23)**, 16 tiles, advisor type **7** (industry). Only `0xB7` on this save. |
| Nearest 3×3 | **(71,17) `0xAB`** — 5 tiles north. **Basilica only** (`§9`). Janiculan is **`0xB3`**. |

Do **not** silently overwrite.

- **Size-today (3×3):** Palatine this cluster = `(71,17) 0xAB`. Then Palatine and both Basilicas share `0xAB` — two UI names on one id. Bad.
- **Coord-today (71,22):** Palatine = `0xB7` 4×4. Matches **yesterday’s 4×4**. Stack order Palatine → Basilica → Colosseum → Basilica then fits (`0xB7`, `0xAB`, `0xE8`, `0xAB`). Type 7 now matches real forums (`0xAF` / `0xB3`), but they said 3×3 today.
- **Old size-split retracted:** `0xAA–0xAC` is **not** Janiculan. `0xAB` = **Basilica only**. Janiculan = **`0xB3`**. `0xAA` / `0xAC` unnamed (no N).

**v3 closed Palatine = `0xB7`.** Basilica on the two `0xAB` 3×3s; Colosseum on `0xE8`. The 4×4 size was right.

### 8.7 Name → id (this Q&A only)

| UI / user name | Id | Conf | Notes |
|---|---|---|---|
| **Tower** | **`0xBF`** | **HIGH** | 1×1 BUILD1B. Barracks label retracted. |
| **Wall** | **`0xC2`** | **HIGH** | E–W between towers. |
| Wall (N–S rim) | `0xC1` | geom | x=78 strip. Not named today. |
| **Gate** | **`0xC0`** | **HIGH** | (70,1); also (78,24), (78,40). Combo, not a palette button. |
| **Road** | **`0x7C`/`0x7E`** (`0x7D` join) | **HIGH** here | Beside circus short side. Old Wall hyp for `0x7C–0x81` conflicts. |
| **C.Maximus** | **`0xED`+`0xEE`** | **HIGH** | 4×8 at (71,25). Two halves. |
| **Colosseum** | **`0xE8`** | **HIGH** here | 3×3 at (71,13). UI: Coliseum. |
| **Basilica** | **`0xAB`** | **HIGH** | 3×3 at (71,17) and (71,10). **Janiculan dropped** — that name is `0xB3` (`§9`). |
| **Palatine Forum** | **`0xB7`** | **HIGH** (v3) | 4×4 at (71,20). D56 closed the old 3×3-vs-4×4 conflict. |

**Next ask:** grid leftover **56** (`§9`). 8 and 9 are named.

---

## 9. Grid labels 2026-08-30 (HIGH)

User named yellow `Desconhecido N` cells on `findings/Achea_grid.xlsx` (chunk 13 of `ACHEA23.SAV`). N→id from the legend. Same id gets the name on every blob. Remaining `Desconhecido N` **keep their old numbers** (gaps at promoted N). Regenerator: `tools/_achea_grid_xlsx.py`. Does **not** copy the SAV.

C2.ENG: **[19]** is `Aventine`, **[21]** is `Shrine`. Temple is **not** an ENG slot (EXE sfx `temple1.wav` only).

**Forums were swapped with Religion.** The old size-split put Aventine/Janiculan on `0xA6–0xAC` (type `0x12`). Those ids are worship. Real forums sit in type **7** / BUILD1A.

### 9.1 Name → id (both batches)

| UI / user name | Old N | Id | Size | Sheet | Conf | Notes |
|---|---|---|---|---|---|---|
| **Temple** | *(was Aventine on map)* | **`0xA6–0xA8`** (`0xA7` unseen here) | **2×2** same-id | HOUSES1 | **HIGH** | Worship, not a forum. Achea: one `0xA6` at (73,3), two `0xA8`. |
| **Basilica** | *(stack Q&A)* | **`0xAB`** | **3×3** | BUILD1C | **HIGH** | **This id only** — not Janiculan. Three 3×3 + leftovers. `0xAA` / `0xAC` unnamed (no N). |
| **Aventine** | **170** (+ other `0xAF`, incl. N=6) | **`0xAF`** | **2×2** | BUILD1A | **HIGH** | Real forum. 4 stamps (16 tiles), `+4` 4–7. Type **7**. |
| **Janiculan** | **8** (+ other `0xB3`) | **`0xB3`** | **3×3** | BUILD1A | **HIGH** | Real forum. 3 stamps. Type **7**. Not `0xAA–0xAC`. |
| **Circus** | **1 + 2** | **`0xEB` + `0xEC`** | two **3×3** = **3×6** | BUILD1D | **HIGH** | Combined **(62,2)–(67,4)**. **Not** C.Maximus. |
| **Market** | **3, 4** (+ other `0xFD`) | **`0xFD`** | **2×2** | BUILD1B | **HIGH** | 32 tiles / 8 stamps. |
| **Baths** | **7** (+ other `0xE0`) | **`0xE0`** | **2×2** | BUILD1B | **HIGH** | 28 tiles / 7 stamps. |
| **Praefecture** | **17** (+ other `0xE3`) | **`0xE3`** | **2×1** / 1-wide | HOUSES1 | **HIGH** | 17 tiles, all `+4=0x50`. |
| **Barracks** | **9** (+ other `0xE4`) | **`0xE4`** | **3×3** | HOUSES1 | **HIGH** | 45 tiles / 5 stamps. `+4` 0x51–0x59. **Not** `0xBF` (Tower). |
| **Hospital** | **173, 179** (+ other `0xFB`) | **`0xFB`** | **3×3** (6×3 = two abutting) | BUILD1B | **HIGH** | Same type, two named blobs. 108 tiles / 12 stamps, SW belt y≥62. |
| **Library** | **174** (+ other `0xF5`) | **`0xF5`** | **3×3** (6×3 = two abutting) | BUILD1B | **HIGH** | 72 tiles / 8 stamps, SW belt. |

**N not renumbered.** Promoted (gone from yellow): 1, 2, 3, 4, 6, 7, 8, 9, 17, 170, 173, 174, 179 and every other blob of those ids.

### 9.2 Palatine — closed in §10

`0xB7` 4×4 at (71,20) = grid **N=56** = **Palatine**. See §10.

### 9.3 Still open (ask next)

Superseded by **§10**. After v3: 21 `Desconhecido` blobs, 6 unique ids (`0xA2`, `0xA3`, `0xAE`, `0xB0`, `0xE9`, `0xEA`).

---

## 10. Grid v3 dump 2026-08-30 (HIGH)

User named a large set of leftover `Desconhecido N` plus Excel ranges. Directory stages: [caesar2.com building directory](https://www.caesar2.com/caesar-ii-building-directory/) — LV bands 0–15 / 16–30 / 31–45 / 46–64 for forums, worship, baths, fountains; Plaza has **3** states; Markets evolve by trader traffic, not LV. **Hypothesis only** where Achea has no matching id.

Workbook: `findings/Achea_grid_v3.xlsx` (mapa + legenda + nomes + progress). Regenerator: `tools/_achea_grid_xlsx.py`. N **not** renumbered. Does **not** copy the SAV.

### 10.1 Palatine closed

**`0xB7` = Palatine.** 4×4 BUILD1A type 7 at (71,20). D56. Matches the 4×4 size story. The old 3×3 guess was `0xAB` Basilica.

### 10.2 Stages that match Achea ids

| Família | 1º | 2º | 3º | 4º / max | Notas |
|---|---|---|---|---|---|
| **Janiculan** | **`0xB2`** D61 | **`0xB3`** (old) | *unseen* (`0xB5`?) | **`0xB4`** D97 | 3×3. User: 1st / 2nd / most evolved |
| **Market** | *unseen* (`0xFC`?) | **`0xFD`** pouco | **`0xFE`** D10 frequente | **`0xFF`** D46 thriving | 2×2. Not LV |
| **Fountain** | **`0xDD`** D18 | **`0xDC`** D52 | *unseen* (3rd still unnamed) | **`0xDE`** D83 | 1×1. Ids **not** sequential |
| **Baths** | **`0xDF`** D51 | **`0xE0`** (estágio não dito) | *unseen* (`0xE1`?) | **`0xE2`** D82 | 2×2 |
| **Shrine** | *hyp `0xA2`* | *hyp `0xA3`* | **`0xA4`** D14/D95 | **`0xA5`** D94 | 1-tile. 1st/2nd **not named** |
| **Basilica** | — | **`0xAB`** | — | **`0xAC`** most evolved | 3×3 |
| **Plaza** | **`0x7C`** BT47 | **`0x7D`** junta | **`0x7E`** BT46 estátua | *(só 3 no directory)* | Old Road name **retracted** |

### 10.3 Other v3 names

| Nome | N / range | Id | Notes |
|---|---|---|---|
| **Grammaticus** | D5, D125, D147 | **`0xF3`** | 2×2. User wrote Gramaticus |
| **Rhetor** | D84 | **`0xF4`** | 3×3 |
| **Odeum** | D41 | **`0xE6`** | 2×2. Pair-1 large |
| **Garden** | D42, D142 | **`0x7B`**, **`0x78`** | `0x79`/`0x7A` named as Garden (same cluster) |
| **Road** | BT4:BT7, BT7:BZ7 | terrain **`0x52`/`0x53`/`0x54`** + pad | Was blank. Map-wide: any `id<0x78` with `+1 & 0x20` |
| **Winery** | D22 norte (perto D13) | **`0xFA`** `+19=1` | 3×3. Full 16-nibble table: `findings/factory.md` |
| **Lead Works** | D40, D22 sul | **`0xFA`** `+19=5` | 3×3. Full 16-nibble table: `findings/factory.md` (D.SAV closed Tailor/Copper/Glass/Spice/Fish) |

### 10.4 Progress

Building tiles `id≥0x78`: **1432**. Named **1379** (96.3%). Unique ids **79** → named **73**, unknown **6**. Unknown blobs **21** (N stable).

Unknown ids: **`0xA2`**, **`0xA3`**, **`0xAE`**, **`0xB0`**, **`0xE9`**, **`0xEA`**.

---

## 11. Labels after v3 (2026-08-30) — leftover empty

User named leftover N (spreadsheet **not** regenerated). Same id → same name on every blob.

| Nome | N | Id | Notes |
|---|---|---|---|
| **Shrine 1** | 138 | **`0xA2`** | only 1-tile blob |
| **Shrine 2** | 101, 139, 128, 129 | **`0xA3`** | also N=21, 23, 29, 33, 59, 60, 65, 76, 90, 93, 108 |
| **Aventine 1** | 140 | **`0xAE`** | 2×2 at (56,44) |
| **Aventine 3** | 171 | **`0xB0`** | also N=92 at (61,35) |
| **Circus** | 98 + 110 | **`0xE9` + `0xEA`** | 3×3+3×3 = 3×6 at (35,38)–(37,43) |

**Desconhecido leftover: none.** No extra unknown N with a different id.

Temple tiles (user wrote `(y,x)`; map is `(x,y)`): **(73,3) = `0xA6`** lowest / 1º; **(61,39) = `0xA8`** 3º. Other Temple: `0xA8` at (68,5). `0xA7` / `0xA9` unseen.

| Família | 1º | 2º | 3º | 4º / max | Nesta save |
|---|---|---|---|---|---|
| **Aventine** | **`0xAE`** | **`0xAF`** | **`0xB0`** | *unseen* (`0xB1`) | 1–3 complete |
| **Palatine** | *unseen* | **`0xB7`** (já marcado; não desnomear) | *unseen* | **`0xB9`** (20230610 D3) | Achea: só o 2º |
| **Basilica** | *unseen* (`0xAA`) | **`0xAB`** (já marcado = 2º) | *unseen* | **`0xAC`** | 2º + 4º |
| **Shrine** | **`0xA2`** | **`0xA3`** | **`0xA4`** | **`0xA5`** | 1–4 complete |
| **Temple** | **`0xA6`** (73,3) | **`0xA7`** (20230610 D4/D5/D7) | **`0xA8`** (61,39) | *unseen* (`0xA9`) | Achea: 1º + 3º |

Factory scheme (all `0xFA` + origin `+19`): `findings/factory.md`.

