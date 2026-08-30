# C2MODEL.DAT map (Caesar II 1.1A)

Evidence is this file (4360 bytes = **1090 little-endian int32s**). FAQ / manual / wiki numbers are hypotheses until they appear here. Do not copy `C2MODEL.DAT` into git.

| | |
|---|---|
| Path (install) | `C:\Users\Felip\OneDrive\Games\Caesar2\C2MODEL.DAT` |
| Size | **4360** bytes (verified) |
| Layout | 1090 x `int32` LE, no magic, min **-20**, max **20000** |
| Unique values | 110 (143 zeros, 97 negatives) |
| Dumper | `tools/dump_c2model.py` |
| Labeled dump | `findings/c2model_tables.json` (numbers + labels, no binary) |
| C2.ENG | 146 strings; short labels used below (`Novice`, `Theater`, `Shrine`, `Tent`, `Gardens`, `Farm`, `Citizen`, `Cost:`) |
| Named | **751 / 1090 = 68.9%** high+medium; **493 / 1090 = 45.2%** high only |
| Unknown / low | 291 low + 1 unlabeled + 47 pad zeros |

## Record-structure conclusion

**Not a uniform record array.** 1090 divides as 2, 5, 10, 109, 218, 545. Whole-file stride 5 or 10 does not produce one record type: table lengths are 3, 5, 6, 9, 10, 20, 32, 33, 47, 52, plus zero-run pads.

The file is a **concatenation of named tables** (economy, housing, land-value pairs, ranks) with **zero padding** as separators (`[157:165]`, `[175:196]`, `[206:215]`, `[612:617]`, `[1016:1020]`).

Sub-regions that *are* records:

| Stride | Where | Meaning |
|---|---|---|
| 5 | `[0:15]` | one int per difficulty (Novice..Impossible) |
| 4 | `[55:95]` | 5 difficulties x 4 fields |
| 32 | `[215:279]`, `[404:436]`, `[500:564]` | one slot per housing grade |
| 2 | `[500:612]`, `[732:790]` | `(land_bonus, radius)` pairs |
| 20 | `[790:990]` | 5 difficulties x 20 rank slots |
| 5 | `[617:732]` | 23 rows; meaning low confidence |

## Index ranges

Confidence: **high** = exact sequence in this file (or unique mechanic). **medium** = clear structure + partial FAQ / internal check. **low** = shape only. **pad** = separator zeros.

| Indices | N | Conf | Meaning |
|---|---:|---|---|
| 0-4 | 5 | medium | Difficulty scalars `20,15,10,5,2`. **Not** promotion counts (`5,7,10,15,20` are **absent**). |
| **5-9** | 5 | **high** | **Starting money** Novice→Impossible: `20000,15000,12000,7000,5000`. C2.ENG has `Novice` only (`Impossible` is not in C2.ENG). |
| 10-14 | 5 | medium | Money-like `2000,500,250,150,100`. Hypothesis: per-province cut / stipend. FAQ v1.0 “−250 each province” is **not** stored as a 5-vector. |
| 15-34 | 20 | low | 5x4 decreasing rows (`10,16,24,35` / …). Hypothesis: land-value ceilings. FAQ business caps `10,16,26` are **absent** (`26` is not in the file at all). |
| 35-54 | 20 | low | Another 5x4-ish block. Opaque. |
| 55-74 | 20 | medium | 5 difficulties x 4 percentages. Novice=Easy=`50,60,80,90`; harder rows drop. Hypothesis: 4-rating leniency / event threshold. |
| 75-94 | 20 | medium | 5 x `(a,b,c,d)`: `(10,20,60,1)` twice, then `(8,20,48,1)`, `(6,25,36,3)`, `(4,25,24,7)`. Hypothesis: event timing / severity. |
| 95 | 1 | unknown | Lone `0`. |
| 96-101 | 6 | medium | `1, 5, 20, 40, 75, 50`. FAQ: gateway=5, city wall=20, tower=75, reservoir=50. `1` and `40` unlabeled. A/B Reservoir debit is **51** (`findings/sav_ab.md`); **51 is absent** from this file. |
| 102-114 | 13 | medium | City costs, **family order** (not FAQ water→…): Gardens 3, Plaza 12, Well 20, Baths 30, Hospital\|Rhetor 500, Fountain 15, Barracks\|Janiculan 400, Prefecture\|Aventine 100, Market 40, Business 80, Grammaticus 250, Rhetor\|Hospital 500, Library 1000. Ambiguities are shared FAQ prices. |
| **115-117** | 3 | **high** | **Shrine 80, Temple 200, Basilica 600.** |
| **118-123** | 6 | **high** | **Theater 300 … Circus Maximus 2500.** |
| 124-156 | 33 | high | `0,5,10,…,160`. Rank `20…65` at `[128]` is a **subsequence of this ramp** — coincidence. Real ranks are at `[790:990]`. |
| 157-164 | 8 | pad | Zeros. |
| 165-174 | 10 | medium | Money ladder `100…2500` (10 steps). Tribute / gift / tier costs — not unique to one FAQ list. |
| 175-195 | 21 | pad | Zeros. |
| 196 | 1 | medium | `3` = Gardens (also `[102]`), glued to the province block. |
| **197-205** | 9 | **high** | **Province costs:** Road 20, Wall 50, Fort 500, Work camp 100, Farm/Mine/Quarry 250, Port 1000, Warehouse 150, Shipyard 400, Trading post 500. |
| 206-214 | 9 | pad | Zeros. `[214]=0` plus occupancy `2,4,6,8` is a **false** land-value hit. |
| **215-246** | 32 | **high** | **Housing occupancy**, 32 grades, exact FAQ (One hut=2 … Large palace=500). Names from FAQ; C2.ENG has `Tent` only. |
| **247-278** | 32 | **high** | **Tax / wealth per house** (not required LV). Imperial insula `58/54≈1.07` vs Simple domus `64/20=3.2` matches FAQ “~3× tax” at that upgrade. |
| 279-325 | 47 | medium | Signed curve `10 … -16 … 0`. Lookup vs index 0…46. |
| 326-377 | 52 | medium | Sister curve `10 … -20 … 100`. |
| 378-403 | 26 | medium | `-2 … 40` saturating. Length 26 fits tax% 0…25; jump at index 7 matches FAQ “do not raise above 7–8%”. Unrest or LV penalty. |
| 404-435 | 32 | medium | Signed `+3 … -12` per housing grade (need / decay — opaque). |
| 436-499 | 64 | low | Small ints, many `9` (n/a?). 32 pairs. Possible extra service flags. |
| **500-563** | 64 | **high** | **Housing land (bonus, radius)** x 32: slums `(-2,1)` … villas `(8,2)` x4, palaces `(16,2)` x2. |
| **564-611** | 48 | **high** | **Forum + worship land (bonus, radius)** exact FAQ: Aventine, Janiculan, Palatine, Shrine, Temple, Basilica (4 grades each). |
| 612-616 | 5 | pad | Zeros. |
| 617-731 | 115 | low | 23 x 5. Many rows sum 80–100. First row `5,0,0,80,0` may be a header. Mix/weights — not province count. |
| **732-789** | 58 | **high** | **Other buildings (bonus, radius)** x 29. Confirmed: Odeum `3;4`, Coliseum `4;5`, Plaza `4;1`, Baths `3;3…6;3`. |
| **790-889** | 100 | **high** | **Individual rating %**, 5 difficulties x 20 rank slots. `99` = unused (Novice 5, Easy 7). Normal pads with `65`; Hard with `82`; Impossible fills 20 (`25…94`). FAQ v1.0 listed 10 ranks (Citizen…Consul); 1.1A has 20 slots. |
| **890-989** | 100 | **high** | **Average rating %**, same 5 x 20. Normal `30…74` padded; Impossible `35…97`. |
| 990-1009 | 20 | medium | 10 x `(7, 40)` — one pair per FAQ rank. Units unknown. |
| 1010-1015 | 6 | low | `7,20,80,40,20,4`. `20` = construction pleb crew (FAQ). `4` = common walker period (months). |
| 1016-1019 | 4 | pad | Zeros. |
| **1020-1022** | 3 | **high** | **Imperial tax brackets** `8000, 5000, 3000` (FAQ personal-savings bands). Percents `10/19/26` are **absent** (`19` and `26` not in file). |
| 1023 | 1 | medium | `30` = plebs per work camp (FAQ). |
| 1024-1082 | 59 | low | Almost all `10`, one `20` at `[1043]`. Per-type default? |
| 1083-1089 | 7 | low | `3,1,-3,-1,4,2,-1`. Not FAQ goal-shift `-1,-1,0,+1,+1`. |

## Housing (32 grades)

Occupancy `[215:247]` and tax/wealth `[247:279]`:

| i | Grade | Occ | Tax/wealth | Occ note |
|---:|---|---:|---:|---|
| 0-5 | Huts | 2,4,6,8,10,12 | 1,2,3,4,5,6 | 0.5 per person |
| 6-11 | Houses | 6,7,8,9,12,16 | 8,10,12,14,17,20 | |
| 12-19 | Insulae | 20…54 | 24…58 | Imperial insula 54 / 58 |
| 20-25 | Domus | 20…45 | 64…100 | Population dip; ~3x tax/person |
| 26-29 | Villas (2x2) | 100…200 | 400…500 | |
| 30-31 | Palaces (3x3) | 300,500 | 1200,1400 | |

Required land value `0,2,4,…,64` is **not** in this file (computed in EXE, or 1.1A dropped it).

## Ranks x difficulty

20 slots, not 10. `99` = no such promotion on that difficulty.

| Difficulty | Promotions (FAQ; **not in file**) | Individual first / last filled | Average |
|---|---:|---|---|
| Novice | 5 | 15…35 then 99 | 25…45 then 99 |
| Easy | 7 | 15…45 then 99 | 25…55 then 99 |
| Normal | 10 | 20…65, pad 65 | 30…74, pad 74 |
| Hard | 15 | 20…82, pad 82 | 30…86, pad 86 |
| Impossible | 20 | 25…94 | 35…97 |

FAQ “−1 / −1 / default / +1 / +1 level” matches Novice/Easy starting 5 points below Normal, Impossible 5 above. Promotion **counts** themselves are EXE-side.

FAQ v1.0 names for slots 0–9: Citizen, Decurion, Apparitor, Magistrate, Quaestor, Procurator, Aedile, Praetor, Proconsul, Consul. C2.ENG has `Citizen` only.

## Absent from C2MODEL (likely EXE or computed)

- Promotion counts `5,7,10,15,20`
- Required housing LV `0,2,…,64`
- Pop unlocks `400,800,1200,1800,2400,4800`
- Worship population gates
- LV evolve `17,33,49`
- Business LV caps `10,16,26`
- Tax percents `10,19,26`
- Employment arrays (Circus Maximus 96 is not a table; `96` only at Impossible average `[988]`)
- Entertainment service radii `5,7,9` / `7,9,11`
- Goal-shift `-1,-1,0,+1,+1`
- Walker distances 36 / 28 as a dedicated table
- Filename `C2MODEL.DAT` as ASCII (unlike `history.dat` / `regions.dat`)
- Construction debit **51** (A/B Reservoir; treasury + chunk 155). File has **`[101]=50`** (FAQ reservoir), never 51.

## PS.EXE (light grep only)

The **4360-byte file is not embedded**. The same int32 runs exist as **scattered .data near EOF** (file size 1_040_111):

| C2MODEL range | PS.EXE file offset |
|---|---:|
| `[0:15]` front + money | 1015743 |
| `[5:10]` starting money | 1015763 |
| `[102:124]` city / worship / entertainment costs | 1013767 |
| `[197:206]` province costs | 1014147 |
| `[215:247]` occupancy | 1014283 |
| `[790:795]` Novice individual (also 1011471, 1013867) | 1011391 |
| `[1020:1023]` tax brackets | 1013441 |

`tools/ps_le.py` mapped image (this session) did **not** contain these bytes (`pages_loaded=0` or they sit past the LE objects). Treat file offsets as the evidence; VAs need a working map.

## C2.ENG cross-ref

Used as labels, not as a parallel table: `Novice`, `Theater`, `Shrine`, `Tent`, `Gardens`, `Garden`, `Farm`, `Wall`, `Baths`, `Market`, `Grammaticus`, **`Reservoir` = [12]**, `Aventine`, `Citizen`, `Cost:`, `Treasury`. A/B pins building id **`0xBE`** to that Reservoir string (`findings/sav_ab.md`, `findings/ghidra_buildings.md`). Missing from C2.ENG (EXE / HELP.ENG): `Decurion`, `Consul`, `Impossible`, `Fountain`, `Circus Maximus`, `Janiculan`, `Palatine`.

## How to dump

```text
python tools/dump_c2model.py --dat path\to\C2MODEL.DAT
python tools/dump_c2model.py --json findings/c2model_tables.json --exe path\to\PS.EXE
```

## Best next Ghidra question

**Where is the 1090-int table loaded?** `C2MODEL.DAT` is not an ASCII filename in `PS.EXE` (but `history.dat` / `regions.dat` are). Same int32 runs exist as .data near EOF (e.g. file-off **1013767** = `[102:215]`, **1014283** = occupancy, **1011391** = ranks, **1015743** = `[0:15]`). Is startup an `fopen`/`fread` of 4360 bytes onto a BSS array, or do those .data addresses *are* the tables and the DAT is an override? Xref the destination of a 4360-byte or 1090-int copy; do not assume the mapped LE image until page load is confirmed.
