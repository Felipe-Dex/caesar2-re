# Province army banners / tooltip (types 2–5)

Analog of `findings/walker_quotes.md` for **land armies** on the province map. City walkers have spoken quotes after **[63]**. These actors do **not**: Query is title + count + people name. Taxonomy / sizes: `findings/province_actors.md`.

No full `C2.ENG` dump here.

**Lookup:** `FUN_00026f16` — `EAX` = official slot **+ 1**, `EDX` = extra NULs. Banner wrapper `FUN_00058c87` (same EAX rule). Number line uses `FUN_00026f95` (not a skip into [44]).

**Picker:** `actor26_query_tooltip` `0x5BE03` when `rec[+4] != 1`. Selected slot `[0x1156D2]`. Type 1 never enters here (cohort panel).

ACHEA23 has **no** types 2–5. Strings below are EXE + C2.ENG only.

---

## Banners (official table)

Spawn calls `FUN_00058c87` after `actor26_spawn`. `EAX` = official **+ 1**.

| Type | Scale (Query still “Barbarians” on 3–5) | EAX | Official | Banner |
|---:|---|---:|---:|---|
| **2** | rival army | `0x5E` @ `0x532EE` | **[93]** | `Enemy Invades!` |
| **3** | invasion (largest barb) | `0x5D` @ `0x53203` | **[92]** | `Barbarian Invasion!` |
| **4** | raiders | `0x5B` @ `0x53115` | **[90]** | `Raiders Sighted!` |
| **5** | local uprising (smallest) | `0x5C` @ `0x53363` | **[91]** | `Local Uprising!` |

City step on Your City `0x92` is a **different** banner: `EAX=0x53` → **[82]** `The City Is Attacked!` (`walker_spawn_type3_from_actor26` `0x53562` — city walker type 3 **Enemy**, quote skip 14 in `walker_quotes.md`). Not reopened here.

---

## Query title ([44] extras)

`CMP` type 2 / 5 / 6 / 7 then `EAX=0x2D`, `EDX` as below. Type ≤2 in this function is type **2** (type 1 already left).

| Type | EDX | Title |
|---:|---:|---|
| 2 | 0x19 (25) | Enemy Army |
| 3–5 | 0x1A (26) | Barbarians |
| 6 | 0x1B (27) | Merchant Ship |
| 7 | 0x1C (28) | Enemy Ship |
| ≥8 | 0x1D (29) | Barbarian Ship |

Type 6 then **[44]+30** `Carrying` + good **[15]** + **[44]+31** `from` + origin. Types 7–8: title only in 1.1A (handlers RET; no spawn).

---

## Query body (types ≠ 6)

Not speech. After the title:

1. `FUN_00026f95` with `EAX = rec[+0x8A]` (battle-ready) and `EBX → 0x90CDC` (a single space in the mapped image). `EDX=0x20` here is a layout arg, **not** [44] skip 32 (`GAME OVER`).
2. `FUN_00026f16` `EAX=0x7` (**[6]** `Romans`) `EDX = rec[+0x9B]` (origin province id written at spawn).

So the second line is **count + people**, e.g. province id 15 → **[6]+15** `Greeks`. [6] extras (file order, skip from `Romans`): Lucanians, Etruscans, Sicilians, Corsicans, Gauls, Carthaginians, Celtiberians (×3), Gauls, Mauri, Dalmatians, Gauls, Macedonians, **Greeks**, Cretans, Belgae, Egyptians, Blemmyes, Judeans, Britons, Blemmyes, Phoenicians, Seleucids, Cilicians, Biythnians, Galatians, Thracians, Scordiscans, Pannoniae, Chatti, Frisians, Cypriots, Armenians, Parthians, Picts (×2), Saxons, Alamanni, Vandals, Visigoths (×2), Huns, Arabs, Huns.

`+0x9B` is the **province id**, not the mix index (`+0x9D` = `[0x95443 + id]`).

---

## Size (why 3/4/5 are a scale split)

Verified in `FUN_000528bb` / `FUN_00052a64` / `FUN_00052bd1` / `FUN_00052d3c` — the spawn helpers (`53215` / `53127` / `5302b` / `53300`) do **not** write counts; the dispatcher does.

| Type | Mul | Typical `+0x8A` (mix sum 60–110) |
|---:|---:|---|
| 2 | ×8 | 480–880 |
| 3 | ×6 | 360–660 |
| 4 | ×3 | 180–330 |
| 5 | ×(tile `0x93`…`0x96` − `0x92`) | 60–440 |

ACHEA23 this-province mix (only useful for a type **5** here): sum **100** → 100/200/300/400.

---

## VAs

| VA | What |
|---|---|
| `0x5BE03` | `actor26_query_tooltip` |
| `0x26F16` | C2.ENG draw |
| `0x26F95` | integer + suffix |
| `0x58C87` | banner |
| `0x528BB` | land spawn dispatcher (5→4→3→2) |
| `0x95443` | province → mix index (u8; first ~50 ids stay in 0…23) |
| `0x95763` | mix rows, stride `0x14` |
