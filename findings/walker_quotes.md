# Walker Query quotes (C2.ENG + picker)

City Query on a live walker (types **1–7**). Strings are in `C2.ENG` after official table **[63]**; the EXE never puts each quote in the 146-slot offset table. No full `C2.ENG` dump here.

**Lookup:** `FUN_000263cc` `0x263CC` — `EAX` = official slot **+ 1** (reads the u32 table from file+8), `EDX` = how many extra NULs to walk. Draw is `FUN_00027071` `0x27071` (wrapped) or `FUN_00026f16` `0x26F16`. Buffer `c2_eng_buf` `0xB831C`.

**Picker:** unnamed blob `0x632A4`–`0x637DE` (Ghidra left a gap between `FUN_00062451` and `FUN_000649B1`). Selected walker slot in `[0x1156E4]`; record = `walker_pool + slot*0x3A`.

| What | EXE `EAX` | Official slot | `EDX` skip |
|---|---:|---:|---|
| Quote body | `0x40` | **[63]** `There are no people in the vicinity.` | computed 4…30 (below) |
| Roman name | `0x41` | **[64]** `Aemilius Calvus` | `rec[+0x32]` (Achea: 0 = Calvus, 15 = Piscator, …) |
| Enemy name | `0x42` | **[65]** `Gregor the Invader` | `rec[+0x32]` when **type == 3** |
| Title | `0x43` | **[66]** ` - Forum Clerk` | **type − 1** |

Titles in file order: Forum Clerk, Market Trader, **Enemy**, Soldier, Vigile, Worker, Rioter. Type 3’s Query heading is **Enemy**, not “Barbarian”.

`[63]` skips **0–3** are the empty-tile people line (`There are no people…` / `person in` / `people in` / `the vicinity.`), not walker speech.

C2.ENG keeps the surrounding `"` on every walker line. Spellings below are the file (screenshot “costumers” / “disctrict” are **not** in `C2.ENG`).

---

## Selection rule

After the name + title, the picker sets `EAX = skip` then `eng_wrap(EAX=0x40, EDX=skip)`.

Default skip is `0x0F` (`mov eax, 0xF` at `0x6350C`) and every type 1–7 overwrites it.

**Type 1 Forum Clerk** — `FUN_0006dd50` `0x6DD50` on walker `(x,y)`, radius **5**, mode **0**. Counts houses `id ∈ 0x82–0xA1` with `tile[+5] & 0xF == 0`. `houses = [0x102400]`. Uncovered (`tile[+10] & 0x0C == 0`) → `[0x1023FC]++`. Else `[0x1023F8] += (tile[+10] & 0x0C) >> 2` (1…3). `FUN_00028219` is `a*100/b`.

| Skip | When |
|---:|---|
| 4 | uncovered% `> 50` |
| 5 | uncovered% `> 10` |
| 6 | uncovered% `> 0` |
| 7 | all covered; coverage_sum * 100 / (houses*3) `< 60` |
| 8 | that ratio `< 90` |
| 9 | that ratio `≥ 90` |

**Type 2 Market Trader** — uses `score_a` `rec[+0x26]` / `score_b` `rec[+0x27]` from `FUN_0004a7ff` `0x4A7FF`. State 4 calls it with **EAX=1, EDX=1**: `score_a` += houses in r=1 (then decays, cap 100); `score_b` += `tile[+13] & 0x80` (factory `0xFA` paints that bit).

| Skip | When |
|---:|---|
| 0x0A (10) | `score_a < 1` |
| 0x0B (11) | `score_a < 8` |
| 0x0C (12) | `score_b < 1` (houses OK, no factory bit) |
| 0x0D (13) | else |

**Type 3 Enemy** — always skip **0x0E (14)**. The next string (skip 15) is **not** selected for type 3.

**Type 4 Soldier** — if `rec[+0x10] == 6` (hunt, `ghidra_walkers_tick.md` state 6) → skip **15**. Else `0x6DD50` radius 5, mode **1**: uncovered = houses with `tile[+10] & 0x30 == 0` (E3/E4 patrol bits).

| Skip | When |
|---:|---|
| 15 | state 6 (hunt) — same string as type 5 hunt |
| 0x10 (16) | uncovered% `> 50` |
| 0x11 (17) | uncovered% `> 10` |
| 0x12 (18) | else |

**Type 5 Vigile** — state **6** → skip 15; state **9** (fire seek) → skip **0x13 (19)**. Else `0x6DD50` mode **2**: `[0x1023FC] += tile[+11] & 0x0F` (immigrant/unrest nibble). Ratio = that sum * 100 / (houses `<< 4`).

| Skip | When |
|---:|---|
| 15 | state 6 |
| 19 | state 9 |
| 0x14 (20) | unrest% `> 80` |
| 0x15 (21) | `> 60` |
| 0x16 (22) | `> 40` |
| 0x17 (23) | `> 20` |
| 0x18 (24) | else |

**Type 6 Worker** — same `score_a` / `score_b`, but state 10 calls `0x4A7FF` with **EAX=1, EDX=0**: `score_b` += `tile[+13] & 0x40` (market `0xFC–0xFF`).

| Skip | When |
|---:|---|
| 0x19 (25) | `score_a < 1` |
| 0x1A (26) | `score_a < 8` |
| 0x1B (27) | `score_b < 1` (people OK, no market bit) |
| 0x1C (28) | else |

**Type 7 Rioter** — `cmp dword [0x102A7C], 0x0A`. That dword is SavChunk **29** (boot **5**, `ghidra_city.md`). The string that wins when `> 10` is about tax rates; treat **[0x102A7C] as the city tax percent** until a dedicated tax write is pinned.

| Skip | When |
|---:|---|
| 0x1D (29) | `[0x102A7C] > 10` |
| 0x1E (30) | else |

No unused quote in 4…30: every skip is reachable. Skip 15 is shared (type 4/5 hunt), not a second type-3 line.

---

## Quotes (file order, skip from [63])

### Type 1 — Forum Clerk (6)

| Skip | Quote |
|---:|---|
| 4 | `"We hardly collect any tax from this district."` |
| 5 | `"Many areas avoid paying their taxes."` |
| 6 | `"Tax avoidance is a problem in the city."` |
| 7 | `"There is no tax avoidance in the district, but our resources are stretched."` |
| 8 | `"We have a good knowledge of this area, but it could be improved."` |
| 9 | `"We have excellent records for this district."` |

### Type 2 — Market Trader (4)

| Skip | Quote |
|---:|---|
| 10 | `"There are too few people in this district to support our market."` |
| 11 | `"We do a reasonable amount of trade with the people of this district."` |
| 12 | `"We have enough customers from this district, but we need better access to a business."` |
| 13 | `"Our market is very popular with the good people of this district."` |

### Type 3 — Enemy (1 used)

| Skip | Quote | Used when |
|---:|---|---|
| 14 | `"AAARGH -- The only good Roman is a DEAD Roman!"` | type == 3 (always) |
| 15 | `"I can't talk now -- there's trouble in the city!"` | **not** type 3 — type 4/5 **state 6** |

### Type 4 — Soldier (3 + hunt)

| Skip | Quote |
|---:|---|
| 15 | `"I can't talk now -- there's trouble in the city!"` (state 6) |
| 16 | `"We have lamentably little access to this part of this city."` |
| 17 | `"We have too few patrols in this part of the city."` |
| 18 | `"We have good patrols in this district. We feel we have the area secure."` |

### Type 5 — Vigile (5 + hunt/fire)

| Skip | Quote |
|---:|---|
| 15 | hunt (state 6) — same as soldier |
| 19 | `"I can't talk now -- the city is burning!"` (state 9) |
| 20 | `"This district will erupt in violence unless something is done about it."` |
| 21 | `"There is much discontent in this district -- the area is a source of trouble."` |
| 22 | `"Not everybody in this district is happy -- I hear the occasional rumors."` |
| 23 | `"Most people in this district are well-behaved and content with their lot."` |
| 24 | `"This is a very law-abiding and peaceful district."` |

### Type 6 — Worker (4)

| Skip | Quote |
|---:|---|
| 25 | `"There are too few workers in this district to maintain our industry."` |
| 26 | `"We could do with more people in this district to help build up our industry."` |
| 27 | `"Many of our workers live in this district, but they need better access to a market."` |
| 28 | `"This is a popular location to live for many of our workers."` |

### Type 7 — Rioter (2)

| Skip | Quote |
|---:|---|
| 29 | `"Well, wouldn't YOU riot if you had tax rates like we've had these years?"` |
| 30 | `"Boo!  Down with the Governor!"` |

---

## Achea (ACHEA23) — why those five lines

Picker at Query time on the Q&A slots (`findings/achea_walkers.md`). Scores = `rec[+0x26]/[+0x27]` in that save.

| Type | Slot | State | `score_a` / `score_b` | Skip | Why |
|---:|---:|---:|---|---:|---|
| 1 | 34 | 3 | unused | **9** | Plaza houses all have `+10` `0x0C`; coverage ratio ≥ 90% → excellent records |
| 2 | 67 | 4 | **12 / 0** | **12** | `score_a ≥ 8` and `score_b < 1` → customers OK, no factory `+13` `0x80` in r=1 |
| 4 | 20 | 7 | unused | **18** | state ≠ 6; patrol uncovered% ≤ 10 → good patrols |
| 5 | 15 | 8 | unused | **24** | state ≠ 6/9; unrest% ≤ 20 → law-abiding |
| 6 | 90, 68 | 10 | **6 / 100** | **26** | `1 ≤ score_a < 8` (market bit is already 100, so not skip 27) |

Names on those slots match `[64] + rec[+0x32]`: 15 Maelius Piscator, 16 Ennius Lentulus, 25 Caelius Clodius, 0 Aemilius Calvus, 31 Gaius Pernix, 17 Iunius Maior.

---

## VAs

| VA | What |
|---|---|
| `0x263CC` | `c2_eng` offset = table[EAX] |
| `0x26F16` / `0x27071` | draw / wrap from that pointer + EDX NULs |
| `0x632A4` | name + title + quote picker (walker Query) |
| `0x6350C`…`0x637D9` | skip by type; `call 0x27071` with `EAX=0x40` |
| `0x6DD50` | house scan r=5; modes 0/1/2 |
| `0x28219` | percent `eax*100/edx` |
| `0x4A7FF` | `score_a` / `score_b` (type 2 EDX=1, type 6 EDX=0) |
