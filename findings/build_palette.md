# City build palette — Caesar II 1.1A

User-listed **English UI labels** from the city build menu (three rows). Those labels are the **source of truth for names**. Tile ids come from A/B/C/D saves, FELIPE01 sheet census, and `FUN_00012a8f` `0x12A8F` advisor-type ranges. C2.ENG indices only where the string **equals** the UI word (not a substring of another phrase). No EXE / SAV / PL8 in git.

**Closed names:** **`0x82` Tent** (`sav_c.md`, C2.ENG **[23]**), **`0xBE` Reservoir** (`sav_ab.md`, C2.ENG **[12]**), **`0xB7` Palatine** (Achea D56), **`0xD7` Well** / **`0xE5` Theater** (`sav_d.md`). Grid v3 also closed Garden / Plaza / Fountain stages / Janiculan stages / Market stages (`achea.md` §10). **`0xCB`** = aqueduct cap / stub (20230610 D1). Remaining UNKNOWN: Arena, Fountain 3rd, missing Palatine/Temple states.

---

## 0. The three rows (source of truth)

English labels as listed from the 1.1A city UI. Nested names are the flyout under that button.

```
Row 1:  zoom in | clear area | Housing | Roads | Forums (Aventine, Janiculan, Palatine)
Row 2:  zoom out | Water (Reservoir, Aqueduct, Well, Fountain) | Security (Wall, Tower, Barracks, Praefecture)
Row 3:  Query (?) | Entert'ment (Theater, Odeum, Arena, Coliseum, Circus, C.Maximus)
         | Worship (Shrine, Temple, Basilica) | Education (Grammaticus, Rhetor, Library)
         | Amenities (Gardens, Plaza)
```

Zoom in/out and Query do **not** stamp `tile[+0]`. **Clear area does:** D.SAV (1,0) is terrain **`0x1C`** (unique; absent on A). Housing places the vacant tent; later grades are evolve, not extra palette buttons.

`Baths` / `Market` / `Industry` / `Hospital` exist in C2.ENG and C2MODEL but are **not** on this three-row snapshot. Achea named **Baths `0xDF`/`0xE0`/`0xE2`**, **Market `0xFD`/`0xFE`/`0xFF`**, **Hospital `0xFB`**, **Library `0xF5`**, **Factory `0xFA`** (`achea.md` §9–§10). Do not invent a fourth row in the UI list.

---

## 1. C2.ENG cross-walk

`tools/extract_eng.py` on this install (`C2.ENG`, 146 slots). Match = exact label (case-insensitive). `(none)` means the UI word is EXE / HELP.ENG / composed.

| Palette name | C2.ENG | Notes |
|---|---|---|
| zoom in / zoom out | **(none)** | tool |
| clear area | **(none)** | **[28]** is `CLEAR FORUM`, not this button |
| Housing | **(none)** | button; first stamp is Tent |
| Roads | **(none)** | |
| Forums | **(none)** | **[28]** `CLEAR FORUM`, **[66]** ` - Forum Clerk` |
| Aventine | **[19]** `Aventine` | |
| Janiculan | **(none)** | |
| Palatine | **(none)** | |
| Reservoir | **[12]** `Reservoir` | A/B closed |
| Aqueduct | **(none)** | |
| Well | **(none)** | **[104]** is `Well Done!` — **not** a hit |
| Fountain | **(none)** | EXE has `Fountains ` (filename-ish), not a menu label |
| Wall | **[13]** `Wall` | **[53]** `Prov. Wall` is the province button |
| Tower | **(none)** | |
| Barracks | **(none)** | |
| Praefecture | **(none)** | C2MODEL FAQ spelling is Prefecture |
| Query | **[73]** `Query` | tool; the `?` glyph |
| Entert'ment | **(none)** | |
| Theater | **[22]** `Theater` | |
| Odeum | **(none)** | |
| Arena | **(none)** | |
| Coliseum | **(none)** | |
| Circus | **(none)** | |
| C.Maximus | **(none)** | FAQ / C2MODEL: Circus Maximus |
| Worship | **(none)** | |
| Shrine | **[21]** `Shrine` | |
| Temple | **(none)** | EXE sfx `temple1.wav` only |
| Basilica | **(none)** | |
| Education | **(none)** | |
| Grammaticus | **[20]** `Grammaticus` | |
| Rhetor | **(none)** | |
| Library | **(none)** | |
| Amenities | **(none)** | |
| Gardens | **[57]** `Gardens` | **[59]** `Garden` (singular) is a sibling, not the button |
| Plaza | **(none)** | |
| Tent (Housing stamp) | **[23]** `Tent` | not a separate palette button |

C2MODEL cost order (not ids): Gardens 3, Plaza 12, Well 20, Fountain 15; Shrine/Temple/Basilica **[115:118]**; Theater…Circus Maximus **[118:124]**. Observed A/B/C debits (Reservoir **51**, Tent **6**) are **not** those FAQ integers.

---

## 2. Palette → tile id

Confidence: **A/B** = surgical pair + user name. **range** = engine range + C2MODEL count. **size** = unique footprint in `0xA2–0xAD` (user 2×2 / 3×3 / 4×4). **FELIPE01** = id seen on that save (name inferred). **hyp** = this note. **UNKNOWN** = no id.

Advisor type = `FUN_00012a8f` presence slot (`[0xA3FBC + type*0x46] = 1`). Not a C2.ENG index. Housing returns without a type.

### Row 1

| UI | Id | Conf | Sheet / evidence |
|---|---|---|---|
| zoom in | — | tool | no `tile[+0]` |
| clear area | terrain **`0x1C`** | **D.SAV** | Flattened land at (1,0). Unique on that save; A has none. **Does** write `+0` |
| Housing | **`0x82`** first stamp; **`0x82–0xA1`** evolve | **A/B** + **range** | Tent 1×1 HOUSES1 variant 0 (`sav_c.md`). **32** ids = C2MODEL 32 grades. Advisor: none |
| Roads | **terrain** `id<0x78` + `tile[+1] & 0x20` | **Achea v3** | BT4:BT7 / BT7:BZ7 left blank on the grid — those cells are **`0x52`/`0x53`/`0x54`** (CITYFIXT), not `0x7C`. Old Road name on `0x7C–0x7E` **retracted** (those are Plaza). |
| Forums (family) | type **7** (`0xAE–0xBB`) | **Achea Q&A** | **Not** type `0x12`. Aventine `0xAF`, Janiculan `0xB2–0xB4`, Palatine **`0xB7`**. Directory: 4 LV states (0–15 / 16–30 / 31–45 / 46–64). |
| Aventine | **`0xAF`** | **Achea Q&A** | **2×2** BUILD1A, type **7**. Grid N=170. Leftover 2×2 `0xAE`/`0xB0` on Achea — **hyp** other Aventine states, not named. |
| Janiculan | **`0xB2`** 1st · **`0xB3`** 2nd · **`0xB4`** 4th | **Achea v3** | **3×3** BUILD1A, type **7**. D61 / old N=8 / D97. **`0xB5` unseen** (directory 4th-state slot or unused). Not `0xAB`. |
| Palatine | **`0xB7`** 2nd · **`0xB9`** 4th | **Achea + 20230610** | **4×4** BUILD1A, type **7**. `0xB9` = 20230610 D3. `0xB6`/`0xB8` still unseen. |

### Row 2

| UI | Id | Conf | Sheet / evidence |
|---|---|---|---|
| zoom out | — | tool | no `tile[+0]` |
| Reservoir | **`0xBE`** | **A/B** | 1×1 HOUSES1 `+4=0x6E` → sprite 90. Advisor type **`0x10`**. C2.ENG **[12]** |
| Aqueduct | **`0xCF–0xD6`** run · **`0xCB`** cap / stub | FELIPE01 + **20230610** | CITYFIXT (sheet `0x10`). **8** run orientations. Stub: 20230610 **(26,31)** `+1=0x40`, south `0xCF`. Advisor type **`0x11`**. `0xCC–0xCE` unnamed (possible sibling stubs). |
| Well | **`0xD7`** | **D.SAV** | **1×1** BUILD1B, type **`0x0F`**. (0,0) `+4=0x10`, `+1=0x01` — **not** pipe `0xC0`. Paints +13 **`0x02`** r=2. **`0xCB` is not Well.** `0xBC–0xBD` leftover type `0x11`. `0xD8–0xDA` unseen (same type / painter, not named) |
| Fountain | **`0xDD`** 1st · **`0xDC`** 2nd · **`0xDE`** 4th | **Achea v3** | 1×1 BUILD1B. D18 / D52 / D83. Ids are **not** sequential. **3rd unseen** — leftover in type 8 is **`0xDB`**. Not `0xBC–0xBD` / `0xCB`. Directory: 4 LV states. |
| Wall | **`0xC2`** (E–W) | **Achea Q&A** | Line (55,1)–(78,1) between Towers. BUILD1B. N–S rim **`0xC1`** (x=78) is same family, not named today. Gate is **`0xC0`** (combo, not a button) |
| Tower | **`0xBF`** | **Achea Q&A** | 1×1 BUILD1B. Achea (78,1) and (55,1) + two south. **Not** Barracks. C2MODEL FAQ price 75 at `[100]` |
| Barracks | **`0xE4`** | **Achea Q&A** | **3×3** HOUSES1. Grid N=9. **Not** `0xBF` (Tower) |
| Praefecture | **`0xE3`** | **Achea Q&A** | HOUSES1, `+4=0x50`. Achea: 2×1 at (61,9) (grid N=17) plus 1×1 stamps. **Not** in `0xBF–0xCA`. C2MODEL FAQ spelling is Prefecture |

### Row 3

| UI | Id | Conf | Sheet / evidence |
|---|---|---|---|
| Query | — | tool | C2.ENG **[73]** |
| Theater | **`0xE5`** | **D.SAV** | **2×2** BUILD1C, type **`0x13`**. (3,0)–(4,1). Pair-1 small. C2.ENG **[22]**. See §4 |
| Odeum | **`0xE6`** | **Achea v3** | 2×2 BUILD1C. D41. Pair-1 large. |
| Coliseum | **`0xE8`** | **Achea Q&A** | 3×3 BUILD1C. Achea stack (71,13) named **Colosseum**. Pair-2 large (`§4`) |
| Circus | **`0xEB`+`0xEC`** · **`0xEA`** (piece) | **Achea Q&A + walkers** | 3×6 = two 3×3 halves. BUILD1D. First pair **(62,2)–(67,4)** = `0xEB`+`0xEC` (§9 HIGH). Second pair **(35,38)–(37,43)** = `0xE9`+`0xEA` (`achea.md` §11); walker perto **HIGH** on **`0xEA`** only. **`0xE9`** stays the abutting sibling (already named Circus in §11). **Not** C.Maximus. |
| C.Maximus | **`0xED`+`0xEE`** | **Achea Q&A** | 4×8 = two 4×4 halves. BUILD1D. **Not** Circus |
| Shrine | **`0xA2`** 1st · **`0xA3`** 2nd · **`0xA4`** 3rd · **`0xA5`** 4th | **Achea v3 + §11 + walkers** | 1-tile HOUSES1. 3rd/4th = D14/D95 and D94 (v3). 1st/2nd named leftover N in `achea.md` §11. Walker perto **HIGH** on **`0xA3` = 2nd** (was `id0xA3` next to type-5 Vigile). C2.ENG **[21]**. |
| Temple | **`0xA6`** 1st · **`0xA7`** 2nd · **`0xA8`** 3rd (`0xA9` unseen) | **Achea + 20230610** | **2×2** HOUSES1. `0xA7` = 20230610 D4/D5/D7. |
| Basilica | **`0xAB`** · **`0xAC`** most evolved | **Achea v3** | **3×3** BUILD1C. `0xAC` = 4th (user). `0xAA` unseen. |
| Grammaticus | **`0xF3`** | **Achea v3** | 2×2 BUILD1B. D5, D125, D147. C2.ENG **[20]**. Paints +13 `0x10`. |
| Rhetor | **`0xF4`** | **Achea v3** | 3×3 BUILD1B. D84. Paints +13 `0x20`. |
| Library | **`0xF5`** | **Achea Q&A** | **3×3** BUILD1B. Grid N=174. SW belt on Achea |
| Gardens | **`0x78–0x7B`** | **Achea v3** | 1-tile BUILD1A, advisor type **1**. D42=`0x7B`, D142=`0x78`; `0x79`/`0x7A` sit in the same garden cluster. **Not** Plaza. |
| Plaza | **`0x7C`** lv1 · **`0x7E`** +statue · **`0x7D`** join | **Achea v3** | BT8:BT47. BUILD1A, type `0x0E`. Directory: **3** states only. Old Road name on this range **retracted**. |
| Baths *(not on these 3 rows)* | **`0xDF`** 1st · **`0xE0`** · **`0xE1`** 3rd · **`0xE2`** 4th | **Achea + 20230610** | 2×2 BUILD1B. `0xE1` closed as D8 (D6 is the same id, not 4th). |
| Market *(not on these 3 rows)* | **`0xFC`** 1st · **`0xFD`** infreq · **`0xFE`** often · **`0xFF`** thriving | **Achea + 20230610** | 2×2 BUILD1B. `0xFC` = D2 “hardly used”. |
| Hospital *(not on these 3 rows)* | **`0xFB`** | **Achea Q&A** | 3×3 BUILD1B. Grid N=173 and N=179 |
| Factory / Business *(not on these 3 rows)* | **`0xFA`** | **20230610 + D.SAV** | One 3×3 id. Origin `+19` lo-nibble = goods 0–15. D.SAV closed Tailor/Copper/Glass/Spice/Fish. See `findings/factory.md`. |

### 2.1 Forum size split (chunk 13)

User sizes (2026-08-29): **Aventine 2×2**, **Janiculan 3×3**, **Palatine 4×4**. Those sizes were right; we put them on the **wrong advisor range**. Type **`0x12`** (`0xA2–0xAD`) is **worship** (Temple 2×2, Basilica 3×3). Real forums are type **7** / BUILD1A.

| UI | Id | Size | Sheet | Type | Conf |
|---|---|---|---|---:|---|
| **Aventine** | **`0xAF`** | **2×2** | BUILD1A | 7 | **Achea HIGH** (N=170) |
| **Janiculan** | **`0xB2`/`0xB3`/`0xB4`** | **3×3** | BUILD1A | 7 | **v3** 1st/2nd/4th. `0xB5` unseen |
| **Palatine** | **`0xB7`** | **4×4** | BUILD1A | 7 | **v3 HIGH** (D56). Closed |
| **Temple** | **`0xA6–0xA8`** | **2×2** | HOUSES1 | `0x12` | **Achea HIGH** |
| **Basilica** | **`0xAB`** / **`0xAC`** 4th | **3×3** | BUILD1C | `0x12` | **v3**. `0xAA` unseen |

Type-7 leftovers: `0xAE`/`0xB0` 2×2 (hyp Aventine other states — **not named**). Walker retry classes (`ghidra_walkers.md`): `0xAE–0xB1→4`, `0xB2–0xB5→9`, `0xB6–0xB9→0x10` — packing story only until those leftover ids get a user name.

The old “12 ids = 3 forums × 4 grades” line in `0xA2–0xAD` was a count coincidence. Worship packing: Shrine **`0xA2`–`0xA5`** (1st–4th) + Temple `0xA6–0xA8` + Basilica `0xAB`/`0xAC`.

---

## 3. `FUN_00012a8f` ranges (id → advisor type)

`id < 0x78` returns (terrain). Housing `0x82–0xA1` returns. Used here only to **group** palette families.

| Ids | Type | Palette guess |
|---|---:|---|
| `0x78–0x7B` | 1 | **Garden** (v3; was Plaza hyp) |
| `0x7C–0x81` | `0x0E` | **Plaza** on Achea (`0x7C`/`0x7D`/`0x7E`); was Road / Wall hyp |
| `0x82–0xA1` | — | Housing (Tent…palace) |
| `0xA2–0xAD` | `0x12` | **Worship:** Shrine **`0xA2`–`0xA5`**, Temple **`0xA6–0xA8`**, Basilica **`0xAB`/`0xAC`**. `0xA9`/`0xAA`/`0xAD` open |
| `0xAE–0xBB` | 7 | **Forums:** Aventine **`0xAF`**, Janiculan **`0xB2–0xB4`**, Palatine **`0xB7`**. Leftover `0xAE`/`0xB0` |
| `0xBC–0xBD` | `0x11` | Water leftover (not Well) |
| **`0xBE`** | **`0x10`** | **Reservoir (A/B)** |
| `0xBF–0xCA` | — | **`0xBF` Tower**, **`0xC2` Wall**, **`0xC0` Gate**, **`0xC1`** N–S wall-ish. Barracks is **`0xE4`**; Praefecture is **`0xE3`**. Gardens still mixed |
| `0xCB–0xD6` | `0x11` | **`0xCB` aqueduct stub** + `0xCC–0xCE` unnamed + **`0xCF–0xD6` aqueduct run** |
| **`0xD7–0xDA`** | **`0x0F`** | **Well `0xD7`** (D.SAV). `0xD8–0xDA` unseen. Old “Farms” label **retracted** |
| `0xDB–0xDE` | 8 | Fountain (`0xDD`/`0xDC`/`0xDE`; **`0xDB`** = 3rd leftover) |
| `0xE5–0xE6` | `0x13` | +12 bits 0–1 |
| `0xE7–0xE8` | 5 | +12 bits 2–3 |
| `0xE9–0xF2` | 2 | +12 bits 4–5 on **`0xE9–0xF0` only**; `0xF1–0xF2` same type, **no** +12 |

FELIPE01 sheets for the +12 band: BUILD1C **`0xE6–0xE8`**, BUILD1D **`0xED`/`0xEE`**. `0xE5` / `0xE9–0xEC` / `0xEF–0xF0` were not on that save’s census.

---

## 4. +12 `3×2-bit` — six pairs vs Gardens / Plaza

`tile[+12]` is wiped each cycle then max-merged by `FUN_0006ce67` from **`0xE5–0xF0` only** (`findings/ghidra_tile.md` §5). Three 2-bit channels. Small/large siblings share a channel; larger id has the bigger rings.

FAQ entertainment rings **`5,7,9` / `7,9,11`** are **absent** from C2MODEL (EXE-side). They match the first two channels as far→near **5/7/9** and **7/9/11**.

| Pair | Small | Large | +12 | Rings small / large | Advisor | Best-guess names |
|---:|---|---|---|---|---:|---|
| 1 | **`0xE5`** | **`0xE6`** | bits 0–1 | 9/7/5 · 11/9/7 | `0x13` | **Theater `0xE5` D.SAV 2×2 / Odeum `0xE6` v3** |
| 2 | **`0xE7`** | **`0xE8`** | bits 2–3 | 9/7/5 · 11/9/7 | 5 | **Arena / Coliseum** — **`0xE8` = Colosseum** (Achea Q&A) |
| 3 | **`0xE9`** | **`0xED`** | bits 4–5 | 10/8/6 · 12/10/8 | 2 | **`0xED` is a C.Maximus half**, not a solo large. Pair-3/4 split is **wrong** |
| 4 | **`0xEA`** | **`0xEE`** | bits 4–5 | same | 2 | **`0xEE` is the other C.Maximus half** (Achea 4×8 = `0xED`+`0xEE`) |
| 5 | **`0xEB`** | **`0xEF`** | bits 4–5 | same | 2 | **`0xEB` is a Circus half**, not Grammaticus. Pair-5/6 split is **wrong** |
| 6 | **`0xEC`** | **`0xF0`** | bits 4–5 | same | 2 | **`0xEC` is the other Circus half** (Achea 3×6 = `0xEB`+`0xEC`) |

**Why this split**

- **12** +12 ids = Entert'ment **6** + Worship **3** + Education **3** was the count story. Achea named **Basilica = `0xAB`** (type `0x12`, not +12) and **Library = `0xF5`** (also not +12). Worship/education are not this pool.
- Pairs 1–2 have the FAQ entertainment radii and **two** advisor types (culture vs blood-sport). Pair 3 is the remaining entertainment pair, forced onto channel bits 4–5 with worship/education (one 2-bit “other civic” nibble).
- Pairs 3–6 are **one** advisor type (`2`) and **one** channel — names **inside** the 4+4 are unordered. The table’s pairing is only “nth small ↔ nth large”.
- **`0xF1–0xF2`** share type `2` but do **not** paint +12. Baths is **`0xE0`**, Hospital is **`0xFB`** (Achea).

**`0xEB`+`0xEC` = Circus** (two 3×3, same pattern as C.Maximus `0xED`+`0xEE`). Achea also has a second 3×6 **`0xE9`+`0xEA`** (`achea.md` §11); walker perto confirmed **`0xEA`** as Circus (piece). Pair 5–6 smalls are one building, not two education buttons. Do not collapse the two pairs into one id.

**Gardens / Plaza are not `0xE5–0xF0`.** They do not call `FUN_0006ce67`. Garden is the type-`1` BUILD1A block (`0x78–0x7B`). Plaza is type `0x0E` (`0x7C–0x7E`). +17 is the road/plaza **access flood**, not +12.

Pair 1 small (**Theater `0xE5`**) is **D.SAV** (2×2 at (3,0)–(4,1)). Pair 1 large (**Odeum `0xE6`**) is v3. Pair 2 large (`0xE8`), Circus `0xEB`+`0xEC`, and C.Maximus `0xED`+`0xEE` are screenshot / grid Q&A, not A/B.

---

## 5. Next surgical A/B

Pause (or save before sim phase `0x51`) so the river `+13` wrap does not muddy the pair. One building, virgin Novice map, same protocol as `sav_ab.md` / `sav_c.md`.

**Highest leverage** (names still UNKNOWN):

1. **Arena** — pair-2 small **`0xE7`** (Coliseum is `0xE8`).
2. **Fountain 3rd** — leftover in type 8 is **`0xDB`** (`0xDD`/`0xDC`/`0xDE` named).
3. **Well siblings** — `0xD8–0xDA` (same type `0x0F` / +13 `0x02` painter; **not** named).
4. **Missing other 3rd/1st states** — Janiculan `0xB5`?, Palatine `0xB6`/`0xB8`, Temple `0xA9`. Baths `0xE1` and Market `0xFC` closed on 20230610.

Already done: empty→**Reservoir** (`0xBE`), empty→**Tent** (`0x82`), D.SAV→**Well `0xD7`** / **Theater `0xE5`**. Grid v3 closed Palatine `0xB7`, Garden `0x78–0x7B`, Plaza `0x7C–0x7E`, Road=terrain+pad, Fountain/Janiculan/Market/Baths stages, Grammaticus `0xF3`, Rhetor `0xF4`, Odeum `0xE6`, Factory `0xFA`.

---

## 6. Gaps

- No `id → C2.ENG` table in the EXE walk yet (`0xBE → [12]` is A/B + string match, not a proven LUT).
- Palatine **`0xB7` closed**. Other Palatine grades (`0xB6`/`0xB8`/`0xB9`) unseen.
- Type-7 leftovers: `0xAE`/`0xB0` (hyp Aventine stages).
- Well **`0xD7` closed** (D.SAV). `0xD8–0xDA` unseen. `0xBC–0xBD` still leftover type `0x11`. Fountain 3rd unseen (`0xDB` hyp). `0xCB` = aqueduct stub (20230610 D1).
- Leftover `0xE7` (Arena / pair-2 small). **`0xE9`/`0xEA`** are the second Circus 3×6 (`achea.md` §11; walker **`0xEA`**). Theater **`0xE5` closed**.
- `0xF1–0xF2` leftover. Zoom / Query are UI only. Clear area stamps **`0x1C`**. Rubble is terrain **`0x05`**.

Do not start a crack session from the drive-letter strings.
