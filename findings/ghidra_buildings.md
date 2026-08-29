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
| `0x00` | **HOUSES1** | housing **`0x88–0xA1`**; civic **`0xA2–0xA8`** (forum-sized 2×2 / 4-variant clumps); also `0xBE`, `0xE3`, `0xE4` |
| `0x04` | **BUILD1A** | plazas/walls **`0x78–0x7E`**; industry **`0xAE–0xB5`, `0xB9`** |
| `0x08` | **BUILD1B** | roads/gardens-ish `0xC1`/`0xC2`; barracks `0xBF`; farms/other `0xDB–0xFF` cluster |
| `0x0C` | **BUILD1C** | `0xAA`, `0xAC`, `0xE6–0xE8`, `0xFA` |
| `0x10` | **CITYFIXT** | aqueducts **`0xCF–0xD6`** |
| `0x14` | **BUILD1D** | `0xED`, `0xEE` |

Housing **`+4` is not the id**: `0x89` → variant 7 → `HOUSES1[7]`; `0xA1` (3×3 palace) uses variants 51–59. Forums **`0xA2–0xA8`** also sit on **HOUSES1** (variants 60–75), not `AFORUM`.

---

## 6. Host map (`app/city_map.py`)

`Tile.building_sprite()` returns `(PL8_key, index)` from the zoom-0 LUT column. `render_iso(..., sheets=)` blits `HOUSES1` + `BUILD1A`–`D` + `CITYFIXT`. Palette is still `CITYFIXT.256` (`tools/decode_pl8.py`). No asset copies.

---

## 7. Gaps

- Zoom 2/3 columns and `HOUSES2/3` / `BUILD2*` / `BUILD3*` are not in the host (zoom 0 only).
- `citytop1.pl8` (slot 7) and `city_map_draw_overlays` are unread — roofs / extras may sit there.
- `FUN_00012a8f` type ids are not yet pinned to C2.ENG names (Forum / Baths / Market / Reservoir strings exist; no id table).
- BUILD1A/C last LUT index is one past `n_sprites − 1`; renderer skips OOB.
- Tile bytes +12 / +14 / +16 / +17 still want a 1-house A/B save (sibling).
- Walkers / overlay sprites are a different pass.

Do not start a crack session from the drive-letter strings.
