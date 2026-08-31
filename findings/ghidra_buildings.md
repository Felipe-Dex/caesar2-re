# Ghidra walk — city building sprites

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP HTTP `127.0.0.1:8080`). No EXE in git. Continues `findings/ghidra_city.md` / `ghidra_walkers.md`.

**Result:** there is **no** `id → PL8` table. `city_map_draw_terrain` `0x361DC` sends `id < 0x78` through the CITYFIXT terrain LUT and `id ≥ 0x78` to **`city_tile_draw_building` `0x3739F`**. That function indexes a **sheet LUT** with **`tile[+4]`** and picks the PL8 from **`tile[+3] & 0x1C`**. Housing `0x82–0xA1` is sheet `0` → `HOUSES1.PL8`. `AHOUSE.PL8` / `AFORUM.PL8` are 182×132 UI icons and are **not** in the zoom set.

---

## 1. Call chain

```
view_frame 0x3CF9A
  city_map_draw 0x360F7
    city_map_draw_terrain 0x361DC
      if tile[+0] < 0x78:
          sprite = LUT_0x96F58[id*4 + (zoom>>1)] + 0x10   ; CITYFIXT
          blit via FUN_00035d67
      else:
          city_tile_draw_building 0x3739F
    city_map_draw_walkers 0x364A0     ; sibling
    city_map_draw_overlays 0x365CC    ; CITYTOP / flags — not this pass
```

Zoom used here is `[0x102BE0] >> 1` (SavChunk 4). Host map is zoom 0.

---

## 2. `city_tile_draw_building` `0x3739F`

Listing (not the Ghidra C view — that mis-attributed `FUN_00012a8f`’s arg):

```
EAX = tile_off [0x102BCC]
variant = tile[+4]                 ; [EAX + 0xE2FC0]
sheet   = tile[+3] & 0x1C          ; [EAX + 0xE2FBF]
lut_i   = variant*4 + (zoom>>1)
switch sheet:
  0x00: sprite = lut_houses [lut_i]     handle [0x1023EC]  HOUSES1
  0x04: sprite = lut_build1a[lut_i]     handle [0x1023E4]  BUILD1A
  0x08: sprite = lut_build1b[lut_i]     handle [0x1023D8]  BUILD1B
  0x0C: sprite = lut_build1c[lut_i]     handle [0x1023DC]  BUILD1C
  0x10: sprite = lut_0x96F18[lut_i]+10  handle [0x102418]  CITYFIXT
  0x14: sprite = lut_build1d[lut_i]     handle [0x1023D4]  BUILD1D
  else: RET
EAX = tile[+0]                     ; building id
CALL FUN_00012a8f                  ; advisor “type present” flags, not blit
; then read PL8 sprite record at handle + sprite*16 + 8 and blit
```

`FUN_00012a8f` `0x12A8F` is a **presence** table (`[0xA3FBC + type*0x46] = 1`) keyed by **id ranges** (housing `0x82–0xA1` returns immediately). It does not choose art.

---

## 3. Sheet → PL8 (`gfx_load_zoom_set` `0x107DB`)

20-byte records `{ u32 malloc_size; char name[16]; }` start at **`0x927CC`** (`ltlmen1b.pl8`) / **`0x927E0`** (`cityfixt.pl8`). City zoom-1 eight-file set:

| Slot | Handle | Filename | Used by draw_building |
|---:|---|---|---|
| 0 | `[0x102410]` | `ltlmen1b.pl8` | no (walkers) |
| 1 | `[0x102418]` | `cityfixt.pl8` | sheet `0x10` |
| 2 | `[0x1023EC]` | `houses1.pl8` | sheet `0x00` |
| 3 | `[0x1023E4]` | `build1a.pl8` | sheet `0x04` |
| 4 | `[0x1023D8]` | `build1b.pl8` | sheet `0x08` |
| 5 | `[0x1023DC]` | `build1c.pl8` | sheet `0x0C` |
| 6 | `[0x1023D4]` | `build1d.pl8` | sheet `0x14` |
| 7 | `[0x1023D0]` | `citytop1.pl8` | no (overlay pass) |

Zoom 2/3 twins: `houses2/3`, `build2a–d` / `build3a–d`, `cityfix2/3`. Host renderer stays on zoom 1 / LUT column 0.

`AHOUSE` / `AFORUM` (1 sprite, 182×132, own `.256`) are **not** in this table.

---

## 4. LUTs (rodata, 4 bytes / variant = four zoom columns)

| Sheet | VA | Records | Zoom-0 rule (v1.1A) |
|---|---|---:|---|
| HOUSES1 | `0x97158` | 174 | identity `0…89`; `90…111` = 0; then remaps 90–105 |
| BUILD1A | `0x97410` | 124 | identity `0…123` (sprite 123 is OOB — PL8 has 123 frames) |
| BUILD1B | `0x97600` | 164 | identity `0…139`; `140…163` remaps to 20–27 |
| BUILD1C | `0x97890` | 72 | identity `0…71` (sprite 71 OOB — 71 frames) |
| BUILD1D | `0x979B0` | 100 | **not** identity: `50…99` then `0…49` |
| CITYFIXT bld | `0x96F18` | 144 | then `+ 0x10`; overlaps terrain LUT at `0x96F58` after 16 entries |

Ghidra names applied: `lut_houses_sprite`, `lut_build1a_sprite`, `lut_build1b_sprite`, `lut_build1c_sprite`, `lut_build1d_sprite`.

---

## 5. FELIPE01.SAV — which id uses which sheet

`tile[+3] & 0x1C` vs `tile[+0]` (SavChunk 13):

| Sheet | PL8 | Building ids on this save |
|---|---|---|
| `0x00` | **HOUSES1** | housing **`0x88–0xA1`**; **Temple `0xA6–0xA8`** (2×2, variants 64–75); 1-tile civic **`0xA2–0xA5`**; **`0xBE` Reservoir** (A/B); **Praefecture `0xE3`**; **Barracks `0xE4`** |
| `0x04` | **BUILD1A** | plaza hyp **`0x78–0x7B`**; **Road `0x7C`/`0x7E`**; **Aventine `0xAF`**; **Janiculan `0xB3`**; leftover `0xAE–0xB5` |
| `0x08` | **BUILD1B** | **Tower `0xBF`**; **Wall `0xC2`** / N–S `0xC1`; **Gate `0xC0`**; **Well `0xD7`** (D.SAV 1×1); **Baths `0xE0`**; **Library `0xF5`**; **Hospital `0xFB`**; **Market `0xFD`** |
| `0x0C` | **BUILD1C** | **Basilica `0xAA–0xAC`** (3×3; `0xAB` Basilica **only**); **Colosseum `0xE8`**; **Theater `0xE5`** (D.SAV 2×2); `0xE6`, `0xFA` |
| `0x10` | **CITYFIXT** | aqueduct run **`0xCF–0xD6`** + stub **`0xCB`** |
| `0x14` | **BUILD1D** | **Circus `0xEB`+`0xEC`** (two 3×3); **C.Maximus `0xED`+`0xEE`** (two 4×4) |

Housing **`+4` is not the id**: `0x89` → variant 7 → `HOUSES1[7]`; `0xA1` (3×3 palace) uses variants 51–59. **Temple `0xA6–0xA8`** sits on **HOUSES1** (variants 64–75), not `AFORUM`. **Aventine is `0xAF`** (BUILD1A). **Janiculan is `0xB3`**. **Basilica is `0xAA–0xAC`**. Reservoir **`0xBE`** uses variant **`0x6E`** → LUT[110] = **sprite 90**. Achea names: `findings/achea.md` §8–§9.

### 5.1 Confirmed building ids (A/B)

User-confirmed surgical pair `A.SAV` / `B.SAV` (`findings/sav_ab.md`). No save bodies here.

| Id | Name | Size | Sheet / `+4` | Zoom-0 sprite | Observed cost | C2.ENG |
|---|---|---|---|---:|---:|---|
| **`0xBE`** | **Reservoir** | **1×1** | HOUSES1 / **`0x6E`** | **90** | **51** | **[12]** `Reservoir` |

C2MODEL has **no** integer **51**. FAQ list price is **`[101]=50`** (`[96:102]` = `1, 5, 20, 40, 75, 50`). `FUN_00012a8f` maps `0xBE` → advisor type **`0x10`** (presence flag, not a C2.ENG index). Engine table `id → [12]` is still unproven; the name match is the A/B + the string at [12].

### 5.1b Screenshot Q&A (Achea, not A/B)

`ACHEA23.SAV` city-view names. Coords match unless noted. Full dump: `findings/achea.md` §8.

| Id | Name | Size | Sheet | Conf |
|---|---|---|---|---|
| **`0xBF`** | **Tower** | 1×1 | BUILD1B | **HIGH** — (78,1) and (55,1). **Not** Barracks |
| **`0xC2`** | **Wall** | 1-wide E–W | BUILD1B | **HIGH** — tower-to-tower y=1 |
| **`0xC0`** | **Gate** | 1×1 combo | BUILD1B | **HIGH** — (70,1); also (78,24), (78,40) |
| **`0xC1`** | Wall N–S (geom) | 1-wide x=78 | BUILD1B | not named today |
| **`0x7C`/`0x7E`** | **Road** | 1-wide | BUILD1A | **HIGH** beside circus. Old Wall hyp retracted for perimeter |
| **`0xED`+`0xEE`** | **C.Maximus** | **4×8** | BUILD1D | **HIGH** — (71,25)–(74,32) |
| **`0xEB`+`0xEC`** | **Circus** | **3×6** | BUILD1D | **HIGH** — (62,2)–(67,4); two 3×3. **Not** C.Maximus |
| **`0xE8`** | **Colosseum** | 3×3 | BUILD1C | **HIGH** this cluster — (71,13) |
| **`0xA6–0xA8`** | **Temple** | **2×2** | HOUSES1 | **HIGH** — worship, not Aventine |
| **`0xAA–0xAC`** | **Basilica** | **3×3** | BUILD1C | **HIGH** — `0xAB` Basilica **only**. Janiculan dropped |
| **`0xAF`** | **Aventine** | **2×2** | BUILD1A | **HIGH** — real forum. Grid N=170 |
| **`0xB3`** | **Janiculan** | **3×3** | BUILD1A | **HIGH** — real forum. Grid N=8 |
| **`0xFD`** | **Market** | 2×2 | BUILD1B | **HIGH** — grid N=3, N=4 |
| **`0xE0`** | **Baths** | 2×2 | BUILD1B | **HIGH** — grid N=7 |
| **`0xE3`** | **Praefecture** | 2×1 / 1-wide | HOUSES1 | **HIGH** — grid N=17 |
| **`0xE4`** | **Barracks** | **3×3** | HOUSES1 | **HIGH** — grid N=9. **Not** Tower |
| **`0xF5`** | **Library** | **3×3** | BUILD1B | **HIGH** — grid N=174 |
| **`0xFB`** | **Hospital** | **3×3** | BUILD1B | **HIGH** — grid N=173, N=179 |
| **`0xB7`** | Palatine? | 4×4 at (71,20) | BUILD1A | **UNKNOWN** — type 7 like forums. Grid **N=56** |

### 5.2 Forum footprints (user sizes → ids)

Aventine **2×2**, Janiculan **3×3**, Palatine **4×4** (2026-08-29) — sizes were right, range was wrong (forums↔religion swap). Palatine still **UNKNOWN**. Full note: `findings/build_palette.md` §2.1 / `achea.md` §9.

| UI | Id | Size | Sheet | `+4` | Conf |
|---|---|---|---|---|---|
| **Aventine** | **`0xAF`** | **2×2** | BUILD1A | 4–7 | **Achea HIGH** (grid N=170). Type 7 |
| **Temple** | **`0xA6` `0xA7` `0xA8`** | **2×2** filled, same id | HOUSES1 | 64–67 / 68–71 / 72–75 | **Achea HIGH** (worship) |
| **Janiculan** | **`0xB3`** | **3×3** | BUILD1A | 0x19–0x21 | **Achea HIGH** (grid N=8). Type 7. **Not** `0xAA–0xAC` |
| **Basilica** | **`0xAA` `0xAB` `0xAC`** | **3×3** filled, same id | BUILD1C | 0–8 / 9–17 / 18–26 | **Achea HIGH**. `0xAB` Basilica **only** |
| **Palatine** | **UNKNOWN** | leftover **`0xB7` 4×4** | BUILD1A | — | Type 7. Grid N=56. Not closed |
| *(unnamed)* | **`0xA2–0xA5`** | 1×1 / 1-wide only | HOUSES1 | 60 / 61 / 62 / 63 | not a square forum |
| *(unseen)* | **`0xA9` `0xAD`** | — | — | — | 4th-grade hyp of Temple / Basilica |

No mixed-id 2×2 / 3×3 / 4×4 in the forum range. Career-city 4×4s are **`0xB7`/`0xB9`** (BUILD1A industry) and **`0xED`/`0xEE`** (now C.Maximus), not type `0x12`.

---

## 6. Host map (`app/city_map.py`)

`Tile.building_sprite()` returns `(PL8_key, index)` from the zoom-0 LUT column. `render_iso(..., sheets=)` blits `HOUSES1` + `BUILD1A`–`D` + `CITYFIXT`. Palette is still `CITYFIXT.256` (`tools/decode_pl8.py`). No asset copies.

---

## 7. Gaps

- Zoom 2/3 columns and `HOUSES2/3` / `BUILD2*` / `BUILD3*` are not in the host (zoom 0 only).
- `citytop1.pl8` (slot 7) and `city_map_draw_overlays` are unread — roofs / extras may sit there.
- `FUN_00012a8f` type ids are not yet pinned to C2.ENG names except **`0xBE` = Reservoir** (A/B; C2.ENG **[12]**). Forum **sizes** pin Janiculan (`build_palette.md` §2.1); **Aventine is UNKNOWN** (old 2×2 is Temple). Palatine 3×3 vs 4×4 is an open A/B; Achea `0xAB` is also Basilica. `0xBE` → advisor type `0x10`. Screenshot / grid Q&A (not A/B): Tower `0xBF`, Wall `0xC2`, Gate `0xC0`, C.Maximus `0xED`+`0xEE`, Circus `0xEB`+`0xEC`, Colosseum `0xE8`, Temple `0xA6–0xA8`, Market `0xFD`, Baths `0xE0`, Praefecture `0xE3`.
- BUILD1A/C last LUT index is one past `n_sprites − 1`; renderer skips OOB.
- Tile bytes +12 / +14 / +16 / +17 still want a 1-house A/B save (sibling).
- Walkers / overlay sprites are a different pass.

Do not start a crack session from the drive-letter strings.
