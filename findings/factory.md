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
| Overlay | `city_tile_draw_flag80`: origin etiqueta `(+19 & 0xF) + 9`; east cell jugs `hi(west +9) + 0x18` |

`FUN_00041b33` (only from `FUN_00041719`, id `0xFA`, origin tile): `+19 & 0xF` indexes `goods_16x48` at `0xD2B6C` (stride 48). Writes production into **`+9`**, not back into +19. Full rule: §5.

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

---

## 5. Production (`FUN_00041b33` `0x41B33`)

Called from market/factory emit `0x41719` (slots **`0x9A–0x9D`**) on every **origin** (`+5 & 0xF == 0`), **before** the pop≥2 spawn gate. Also `OR +3 bit 1` on every `0xFA` cell.

| Input | VA / field | Role |
|---|---|---|
| Goods type | origin `+19 & 0xF` | index into `goods_16x48` |
| Supplied % | record **+24** `0xD2B84` | cap 0–7; **≤0 → stock 0** |
| Raw qty | record **+28** `0xD2B88` | cap / labor bump; **≤0 → stock 0** |
| Labor seed | chunk **140** `[0x102B08]` | min’d with prod, clamp 0–7 → **+9 hi** |
| Province links | chunk **276** `[0x102714]` | **≤0 cap prod 4** (City Only / no farms) |
| Houses | `FUN_0006df8d` `0x6DF8D` EAX=2 r=2 | occupancy in 7×7; bumps +9 bits 0–1 → raw prod 0/3/5/7 |
| Market bits | +9 `& 0x0C` | 0 → cap prod 4 and labor−2 |

**Write:** stock 0–7 into **`+9` hi nibble**. Lo bits are restaged (3→2→1→0 / `0xC`→8→4→0) from the bumped stage. **Does not** decrement the goods table.

Worker type 6 / state 10 (`0x4675C`) calls `0x4A7FF` **EDX=0** and packs scores into **+9 bits 0–3 only**. Hi stock stays.

**No cart / load-to-market walker.** Type 2 traders scan factory splash `+13&0x80`; workers scan market splash `+13&0x40`. Industry tax still needs `+10&0x0C` and reads stock×70.

### Type picker + etiqueta

Placement `0x30407` stamps `0xFA` 3×3 (`+4=0x3E…0x46`, `+3` sheet `0x0C`). The **user** picks the good (HELP eight Business kinds). EXE then:

- writes origin **`+19` lo** from `[0x10243C]` (picker nibble)
- **`OR +3 bit7`** on the origin → `+3 = 0x8C` (D.SAV origins)
- **`OR +13 bit7`** (`0x80`) — factory splash for type-2 traders

The picker does **not** write `+9`. Overlay is a later blit, not a second building.

`city_map_draw_overlays` `0x365CC` calls `city_tile_draw_flag80` `0x37E0F` only when **`+3 & 0x80`**. Handle `[0x1023D0]` = `citytop1.pl8`.

| Cell | Test | CITYTOP frame | Dest LUT (zoom-0 cam 0) |
|---|---|---|---|
| Origin (`+5` lo == 0) | — | `(+19 & 0xF) + 9` (etiqueta: wheat/grapes/…) | `0x9410C`/`0x9413C` **(32, −18)** |
| Non-origin | `hi(west +9) ≠ 0` | `hi(west +9) + 0x18` (porch amphorae, frames 0x19–0x1F = 43×30) | `0x9416C`/`0x9419C` **(−54, 22)** |

Non-origin reads **`[tile−20]+9`** (`0xE2FB1` = current `+9` − 20) — the **west** cell’s stock, not its own. Career / D.SAV put bit7 on origin **and** `+5` lo==1 (east of origin, `+4=0x40`). Stock hi lives only on the origin; the east cell borrows it. Stock 0 skips the jug blit (`je 0x382F3`). Etiqueta and jugs are separate frames — do not hide the grape/wheat overlay.

Host: place ORs bit7 on origin and the east cell; `_paint_iso_tile` blits both CITYTOP layers. Without bit7 the factory is a bare BUILD1C pad.

### What starts production

No cart / load-to-market walker. `0x41719` (slots `0x9A–0x9D`) ORs `+3` bit0 and runs `41b33` on every origin **before** the pop≥2 worker-6 gate. Stock is **`+9` hi** from goods `+24` (supplied %) and `+28` (raw) and labor seed `[0x102B08]`. Type-6 workers pack scores into `+9` bits 0–3 only.

### City Only / farms

Farms are province. `init_new_city` **does** call `province_goods_setup` `0x577E4` (pid 0 locals + `goods[+0]=1`) and `0x43DD4`. `0x43F05` **zeros** all 16 records’ `+24`/`+28`. Campaign (`[0x9CE81]≠0`) then reseeds supplied % from `0x96927`; City Only skips that. Raw `+28` is later `pop / farm-counter` (`0x4453D`) — no farms → **0**. `41b33` with raw≤0 or supplied≤0 writes stock **0**. D.SAV chunk 339 has supplied % but `+28=0` and factory `+9=0`. Career SAVs already stock `+28` in the thousands.

Host City Only **sandbox-seeds** chunk 339 (`+0=1`, supplied 100, raw 500) and `factory_labor=4`, and treats empty occupancy as stage 1 so a placed Bakery/Winery/… is not stuck at stock 0 with no label. `province_links=0` still caps prod at 4 (EXE). Career load keeps the file table — do not overwrite.
