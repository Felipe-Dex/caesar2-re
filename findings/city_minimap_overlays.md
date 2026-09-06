# City minimap overlay-filter

Retail `c2_x` / mapped `PS.EXE`. Overlay **id** is SavChunk **1** at `[0x117A59]`. Host: `app/city_overlay.py`. INT_CITY sprites 4–12 are **not** this table (rotate / play / view-tab art at the authored float origin).

## 1. How the EXE opens the list

| Piece | VA | What |
|---|---|---|
| Table | `0x98B34` | 11 × 18 B: `u16 id` + `u32 handler` + pad (`0x10` flag) |
| Open popup | `FUN_00032A90` | `EAX=0x98B32` `EDX=11` `CALL 0x2E5C7` |
| Click site | `0x315B9` | Mouse in the INT_CITY **sprite 1** well. `cmp [0xC4CE0], 0x25C` (604): **x < 604** → menu; **x ≥ 604** → `0x32A0C` (legend / refresh) |
| Well dest | PL8 | Sprite 1 `(478, 24)` 162×24 — name strip **above** the 80×80 well `(478, 48, 162, 160)` |
| HUD name | `FUN_00061C56` | `EAX=0x35` (C2.ENG slot **52**), `EDX=[0x117A59]` at `(0x1E4, 0x1D)` |
| Reset | `city_view_reset` | id **0** Geography |

Host: click the sprite-1 well to open a Geography…Cancel flyout (same names). Not the 3×5 build grid.

## 2. IDs (C2.ENG slot 52 + skip)

| id | Handler | Name | Help (skip 12+) |
|---:|---|---|---|
| 0 | `0x32AE3` | Geography | Clears other map reports to show the city in detail. |
| 1 | `0x32AF7` | Land Value | Shows property values across the city. |
| 2 | `0x32B0A` | Water | Shows areas with access to water sources. |
| 3 | `0x32B13` | Security | Shows levels of security across the city. |
| 4 | `0x32B1C` | Unrest | (packed; Achea chunk 1 = 4) |
| 5 | `0x32B25` | Tax Coverage | |
| 6 | `0x32B2E` | Entert'ment | |
| 7 | `0x32B37` | Education | |
| 8 | `0x32B40` | Illness | |
| 9 | `0x32B49` | Markets | |
| 10 | `0x329EF` | Cancel | **Zeros build-tool slots** `[0x102430]/[0x102484]/[0x102448]/[0x102434]`. Does **not** write `[0x117A59]`. Geography is how you clear the report. |

Handlers store the id, set `[0x117A58]=1`, then `JMP 0x3E590` (wipe 80×80 plane `0xD7BFC`).

## 3. Paint (phase `0xD3` / `FUN_0003e5e3`)

`call dword [eax*4 + 0x99B3C]` per tile. `[0x102C00]` = linear index; `[0x102C0C]` += `0x14`. Writes **one palette index** to `0xD7BFC+i` (CITY1.256). Geography writes **0** (minimap stays terrain).

| id | Painter | Reads | Color meaning (index → CITY1.256) |
|---:|---|---|---|
| 0 | `0x3E656` | — | 0 = geography / no tint |
| 1 | `0x3E666` | signed **+15**, clamp 0…64 | 0 if ≤0; else `(lv>>3)*3 + 0x7E` (teal→khaki ramp) |
| 2 | `0x3E6BA` | **+1&0xC0**, **+0**, **+13&7** | pipe / Well–Fountain `0xD7–0xDE` → **0x96**; charge+ring → **0x87**; charge → **0x84**; ring `+13&4` → **0x8D** |
| 3 | `0x3E7DB` | **+0**, **+1&6**, **+10&0x30**, signed **+17** | road/river `0x1E–0x51`, Praefecture `0xE3`, Barracks `0xE4` → **0x96**; coverage score 2/1 → **0x8D** / **0x90** / **0x93** |
| 4 | `0x3EA8E` | **+11&0x0F** | 0 empty; ≥11 **0x77**; ≥5 **0x78**; else **0x79** |
| 5 | `0x3E757` | **+0** `0xAE–0xB9`, **+10&0x0C** | forums **0x96**; tax bits 4/8/C → **0x93** / **0x90** / **0x8D** |
| 6 | `0x3E983` | **+0** `0xE5–0xF0`, **+12** 3×2-bit | venues **0x96**; sum `n` → `(n-1)*3 + 0x7E` |
| 7 | `0x3E8FA` | **+0** `0xF3–0xF5`, **+13&0x30** | schools **0x96**; both **0x87**; `0x10` **0x8D**; `0x20` **0x84** |
| 8 | `0x3E8A2` | **+11&0x30** | `0x10` **0x79**; `0x20` **0x78**; `0x30` **0x77** |
| 9 | `0x3EA03` | **+0** `0xFA`/`0xFC–0xFF`, **+10&0xC0** | market/factory **0x96**; walker 0x40/0x80/0xC0 → **0x93** / **0x90** / **0x8D** |

Plane **0** → host keeps the geography pixel (dimmed). Nonzero → CITY1.256 RGB (fallback table in `city_overlay.py`; no palette file in git).

## 4. Iso vs minimap

`city_map_draw` `0x36169`: if id ∈ **{0,1,4,8}** then `[0x117AC4]=1` else 0. That flag remaps **housing** on the iso/minimap path (`0x38B86` family: house → color 7). Host now tints **both** the minimap (CITY1.256 plane) and the iso viewport (`overlay_iso_wash` after `crop_viewport`). The wash is post-crop so it does **not** fight the dirty-iso cache.

Water overlay uses the **real pipe graph** (`+1&0xC0` on Reservoir/aqueduct cells only) and **+13** splash. Charge `+10&3` is stored on place (`rebuild_pipe_charge`) but the EXE painter reads **+13**, not +10. Host also paints Reservoir `0xBE`, aqueduct `0xCB–0xD6`, and river as watered (`0x96` / `0x84`) so the overlay is visible before splash phases `0x56+` / `0x6E+`. **Uncovered land is plane 0** (dimmed geography) — not a dry-red flood. `+1&0xC0` does **not** splash neighbours.

Fountain `0xDB–0xDE` emits **+13 `0x01` r=6** only when the tile is in a charged reservoir ring (`+13&4`, r=4/5/6 from charge 1/2/3). Dry fountain (no ring) is the building colour only. Well `0xD7–0xDA` always emits **+13 `0x02` r=2**. Place writes those bytes immediately; phases `0x56–0x5D` / `0x6E–0x75` rewrite them after wipe `0x51`.

Same honesty: Security **+17** / **+10&0x30**, Tax **+10&0x0C**, Entert'ment **+12**, Education **+13&0x30**, Markets **+10&0xC0** are empty on a fresh map (phase stubs). Buildings still highlight (Reservoir, Well, Forum, school, market, Praefecture). Unrest / Illness use **+11** on houses when evolve has written the nibble.

## 5. Right-click vs Query (original)

| Input | EXE | Host |
|---|---|---|
| Overlay menu **Cancel** (id 10) | `0x329EF` zeros tool slots | drop build tool; overlay id unchanged |
| Right-click while a **build** tool is active / mid-drag | cancel tool (same slots) | cancel tool / abort rubber-band (**no stamp**) |
| Right-click, **no** tool or **Query** | inspect tile | Query dialog (name + known bytes) |
| Query button then left-click | inspect | same dialog |
| Geography | clear report | overlay id 0; terrain minimap |

Do **not** inspect when a stamp/span tool is selected — that would steal cancel-tool.

## 6. Host how-to

```text
python -m app --new --city-only --no-audio
```

1. Click the **name well** at the top of the right sidebar (`(478,24)` 162×24).
2. Pick Water / Unrest / … . Geography = normal minimap + iso. Cancel = drop the build tool.
3. Water: **blue** (`0x84` +13&3 / river), **tan** (`0x96` pipe / well / fountain / reservoir / aqueduct), **purple** (`0x87` charge+ring), **khaki ring** (`0x8D` +13&4). Uncovered grass stays geography (no red wash). Fountain blob is r=6 only when the fountain sits in a charged reservoir ring.
4. Maximize / resize the window: same PL8 zoom, larger iso clip (more tiles). Chrome stays 162 px 1:1 on the right.
5. Query tool or right-click (no tool) on a tile → place dialog.
