# Caesar II `.SAV` — static decode (city map)

Worked from the three saves on this install only. No gameplay tonight. No `.SAV` copied into git. No invented checksums. No fake save written for `PS.EXE`.

## Visualization command

```text
python tools/probe_sav_map.py --dump --out sav_preview
```

Optional: `--dir "C:\Users\Felip\OneDrive\Games\Caesar2"` (that is the default). `--no-png` for stats only. `--legacy` is the old 40×40 hunt.

Plane-aware A/B:

```text
python tools/diff_sav.py --a path\to\A.SAV --b path\to\B.SAV
```

## Inventory

All `.SAV` under `C:\Users\Felip\OneDrive\Games\Caesar2` (3 files, no others):

| File | Bytes | First 16 hex | mtime |
|---|---:|---|---|
| `FELIPE01.SAV` | **225745** | `00 04 00 00 00 00 00 00 32 00 00 00 36 00 00 00` | 2008-01-13 |
| `FELIPE02.SAV` | **225745** | `00 04 00 00 00 00 00 00 1d 00 00 00 38 00 00 00` | 2008-08-23 |
| `LASTYEAR.SAV` | **225745** | `00 00 01 01 00 00 00 00 21 00 00 00 12 00 00 00` | 2009-12-22 |

`1745 + 35 × 6400 = 225745`. Confirmed on all three. No ASCII magic. `LASTYEAR.SAV` is the name the EXE already knows (`lastyear.sav` / `caesar2.sav` strings). It is a real same-size save, not a different format.

FELIPE01 vs FELIPE02 remain **~26% different** (distinct campaigns). They are useless as a 1-house delta.

## PNG folder

Gitignored: `sav_preview/` (356 PNGs this run).

| Path | Contents |
|---|---|
| `sav_preview/FELIPE01/` | `plane_00`…`34` `_gray.png` `_occ.png` `_enum.png` + `montage_enum.png` `montage_occ.png` |
| `sav_preview/FELIPE02/` | same |
| `sav_preview/LASTYEAR/` | same |
| `sav_preview/_diff_FELIPE01_vs_FELIPE02/` | per-plane XOR occupancy |

Each plane image is 80×80 nearest-neighbor scaled ×8 (640×640). `_gray` stretches 0…max; `_occ` is nonzero; `_enum` is HSV-by-value (0 = black).

## Layout (fact)

```
0000     header 1745 B
06D1     plane[0]   80×80 = 6400 B     file offset 1745
         plane[i]   at 1745 + i×6400
         plane[34]  at 219345 … 225744
```

SoA, not 35-byte records. Proof remains plane 6: **6400 consecutive zeros** in all three files. An AoS of 35 bytes/tile would scatter those zeros every 35 bytes.

The old 40×40×31 @ 176128 hypothesis is dead: that offset sits inside planes 27–34.

## Header (1745 B)

No city name, no player name, no `C2.ENG` string, no `FELIPE` / `Latium` / `Novice` / `Rome` anywhere in the file. Names are **not** Latin-1 in the save. Player name `Sophia Dex` lives in `CAESAR2.INF` (64 B profile), not in `.SAV`. City / province is an ID (unrecovered).

After the first 16 bytes the header is sparse. The **current-city scalar block** does not start at a fixed offset:

| Save | First nonzero after +16 | Block start |
|---|---:|---:|
| FELIPE01 | 191 | **191** |
| LASTYEAR | 191 | **191** |
| FELIPE02 | 541 | **541** |

`541 − 191 = 350`. Align the two named saves on that delta and the same relative bytes light up (flag `1` at +0, constant `6` at +4, `0xB0` at +12, the `01 01` run, …). Hypothesis: a **350-byte career / assignment slot** (FELIPE02 sits in slot 1; slot 0 is zeros). Not proven. Cross-file compares **must use relative offsets**.

`LASTYEAR` uses the same block base as FELIPE01 but a different 4-byte prefix (`00 00 01 01` vs `00 04 00 00`). Treat named-save vs autosave prefixes as different until an EXE struct says otherwise.

### Field table

Relative offsets are from the city-block start (191 or 541). File offsets are absolute.

| Offset | Type | FELIPE01 | FELIPE02 | LASTYEAR | Verdict | Note |
|---|---|---:|---:|---:|---|---|
| file +0 | u32 / u8+u8 | 1024 (`u8@1=4`) | 1024 (`u8@1=4`) | 16842752 (`00 00 01 01`) | **guessed** | Named saves share `u8@1=4` (difficulty 0–4? rank? format flag?). Autosave prefix differs. |
| file +4 | u32 | 0 | 0 | 0 | unused here | |
| file +8 | u32 | **50** | **29** | **33** | **confident (year BC)** | Matches `C2.ENG` calendar (`January` / `BC` / `Week 1`). Three plausible late-Republic years. Not month (those would be 1–12). |
| file +12 | u32 | 54 | 56 | 18 | **unknown** | Stable-ish on the two career saves. Not money, not pop. Could be scenario / week-counter / rating. |
| file +16 … block−1 | — | zeros | zeros | zeros | empty prefix | Length is 175 (F01/LY) or 525 (F02). |
| block +0 | u8 | 1 | 1 | 1 | **guessed** | Occupied / valid-city flag. Same on all three. |
| block +1 | u8 | 84 | 81 | 0 | **guessed** | 0–100 rating (peace / prosperity / favor). LASTYEAR 0 may mean “not stored” or a fresh snapshot. |
| block +4 | u8 | 6 | 6 | 6 | **guessed** | Same on all three. Month = June, or a constant (struct version / weeks-per-month). Too coincident for a free-running month unless all three were saved in June. |
| block +12 | u8 | 176 (`0xB0`) | 176 | 176 | **unknown** | Identical on all three. Packed flags? |
| block +58…+61 | i32 LE | −259 (`FD FE FF FF`) | (unaligned twin) | −300 (`D4 FE FF FF`) | **guessed** | Signed. `HISTORY.DAT` also has ~−299. Score / favor delta / days — not money. |
| block +237… | 14 × `01 01 00 00` | yes | yes (at +237) | no | **guessed** | 14 slots of u16=257. Rank / month / unlocked-building flags. |
| block +305 | u16 | **1700** | **793** | **0** | **guessed** | Magnitude fits mid-game **treasury or population**. C2MODEL starting money is 20000…5000 (not seen). FAQ pop unlocks include 1800 — 1700 is near that. LASTYEAR=0 argues against “always population” unless autosave omits it. |
| block +313 | u16 | **1700** | **1097** | **0** | **guessed** | Twin of +305. Same-value pair on F01; 793 vs 1097 on F02 (pop vs housing cap? treasury vs last-year money?). |
| block +323 | u16 | 1028 | 1028 | — | **unknown** | Same on both named saves (`0x0404`). |

No field in the header matches C2MODEL starting-money `{20000,15000,12000,7000,5000}` on these mid-game saves. That is expected if money has been spent.

Difficulty is **not** stored as the `C2.ENG` string `Novice`. `u8@1=4` is the only difficulty-shaped candidate, and it may just mark “named career save”.

## Planes — identity hypotheses

Sprite counts measured from this install (u16 @ PL8+2): `CITYFIXT=140`, `HOUSES1=106`, `BUILD1A=123`, `OVERLAY1=35`, `LANDFILL=214`. `OVERLAY1=35` matching 35 planes is treated as **coincidence** until proven.

**CITYFIXT-as-raw-index fails as a whole-plane rule.** Almost every occupied plane has `max ≥ 250`. High bytes `248–255` are a **sentinel family** (especially 248, 249, 250, 252, 254, 255). They are common on the two developed career cities and nearly absent on LASTYEAR planes 28–31.

A weaker form still stands: **most nonzero cells are in 1…139**. Planes 32–33 (career) and 28–31 (LASTYEAR) are the tightest CITYFIXT-range layers.

Period-5 of planes 28–31 is **low** (0.15–0.23). They are not 5-byte record tables mis-drawn as 80×80. The vertical stripes in the PNGs are **north–south linear features** (roads / walls / aqueducts / house strips) with empty columns between — typical C2 grid play, visible on all three independent cities.

### Per-plane (evidence from PNGs + histograms + cross-save %)

A=B is FELIPE01 vs FELIPE02 equal-fraction.

| Plane | Off | F01 nz | A=B | Hypothesis | Evidence |
|---:|---:|---:|---:|---|---|
| **0** | 1745 | 1414 | 80% | **Building / zone footprints (south city)** | Occupancy only y≈34–79 on both career saves; organic (not a hard cut); values dominated by 1–8; 1287/1414 nonzero in 1–139. LASTYEAR has a thin mid-band only (less built). |
| 1 | 8145 | 823 | 88% | North-side overlay / sparse terrain | Complementary to plane 0 (F01 y=0–37). LASTYEAR **empty**. Empty-when-undeveloped ⇒ not base terrain. |
| 2 | 14545 | 516 | 95% | Sparse overlay | High neighbor-agreement. LASTYEAR empty. |
| **3** | 20945 | 2681 | 66% | **Dense tile-state / desirability-like** | Full-map bbox; 2488 cells in 1–139; high entropy; LASTYEAR empty. Looks like an active-city field, not rocks/water. |
| 4 | 27345 | 567 | 90% | North band overlay | y≈0–24. LASTYEAR empty. |
| **5** | 33745 | 13 | 99.8% | **Rare markers (shared points)** | 13–17 cells on a line y=52–56. F01 and F02 share several **exact** (x,y) (e.g. `(56,52)=1`, `(42,53)=255`). Not player houses. Invasion / gate / resource / walker-anchor candidates. LASTYEAR empty. |
| **6** | 40145 | **0** | 100% | **Unused / never-triggered** | 6400 zeros in all three. Reserved layer or a system these saves never armed (see below). |
| 7 | 46545 | 649 | 91% | Sparse structures / edge marks | Four-ish repeated clusters (F01 PNG) + top-edge ticks. Sentinels 248/100 appear. |
| **8–26** | 52945… | 650–2100 | 65–88% | **Coverage / service family** | Same sentinel vocabulary (`100`, `248`, `249`, `252`, `8`, `1`). Neighbor-agree 0.63–0.87. LASTYEAR **18–26 are almost identical** (exactly 640 nz, top `249:208` `248:112`) — a frozen 8-row-ish strip, not three different cities’ terrain. Reads as radius/coverage maps that collapse to a template when the city is thin. |
| 27 | 174545 | 1449 | 75% | Transition into 28–31 | Mix of 8–26 sentinels and 28–31 IDs (`254`/`249`). |
| **28–31** | 180945… | 2600–3400 | **~48%** | **Strongest building / tile-type candidates** | Most divergent across campaigns. Highest occupancy. Vertical N–S strips + 2×2-ish clumps. Dominant extras: F01 `254`, F02 `250`/`254`, plus 16/24 (common C2 house/road-ish constants). LASTYEAR stays inside 1…159 with **zero** 248–255 — same planes, earlier/emptier encoding. **This is where a 1-house A/B will speak.** |
| **32–33** | 206545… | ~1750 | ~72% | **Tile-ID / edge / orientation (CITYFIXT-range)** | F01 p33: 1745 of 1748 nonzero in 1–139 (only 3 sentinels). p32 similar + some `255`. PNGs: blocky footprints on top, N–S lines below (roads/pipes). Best raw-index fit we have. Still ~90 unique values — could be sprite IDs **or** packed small enums. |
| **34** | 219345 | 935 | 90% | **Water / coast / river (terrain)** | Full-width **horizontal band** on all three (y≈20–40); south half empty; nonzero mode **255** (322 / 327 / 252 cells). This is the geographic smoking gun. Not a building layer (would not draw a map-wide stripe in three different campaigns unless they share a river-at-that-latitude generator — still terrain). |

### Plane 6

Documented as **unused or never-triggered** on this install. Three saves, three campaigns/years, still 6400 zeros. Options that remain open:

- reserved / leftover from a 36-byte design
- a system these cities never ran (battle overlay, riot, fire, unused climate)
- a flag plane that stays zero until an event

A surgical save that *causes* a known overlay (set a fire, start a riot) is the way to name it. Do not treat “always zero” as “padding after EOF” — it sits between live planes 5 and 7.

## What is *not* true

- Not 40×40.
- Not AoS of 35-byte tiles.
- Not “every plane is a CITYFIXT sprite index 0…139”.
- Adjacent planes are **not** lo/hi u16 pairs (u16-unique is hundreds, but that is mostly `0|hi` / `lo|0`; `both_nz` overlap is spatial, not a split integer).
- No plane is a coordinate plane (`value==x` / `value==y` ≈ 80, i.e. chance).
- No checksum field identified. Do not invent one.
- Header has no Latin-1 city name.

## Remaining need: surgical save pair

Static work has gone as far as occupancy + value ranges + geography can take it. FELIPE01 vs 02 will not name a plane.

**Gold standard (later, one evening):**

1. Load one existing city (FELIPE01 is fine).
2. Save as `A.SAV` (no change).
3. Build **one** 1×1 or 2×2 house (or one road tile) on empty grass.
4. Save as `B.SAV`.
5. `python tools/diff_sav.py --a A.SAV --b B.SAV`

Expected: a handful of cells in **planes 28–31** and likely **0 / 32 / 33**; header scalars (money −cost, maybe pop) at **block +305 / +313**. That names “building type” vs “footprint” vs “coverage”.

A second pair (one road, or one fountain) separates road/water from housing. A fire/riot pair is the only realistic way to see if plane 6 ever turns on.

Do not hand-edit a `.SAV` for `PS.EXE` to load. Wait for the EXE agent’s load/save struct if it lands in `findings/ps_exe.md`.
