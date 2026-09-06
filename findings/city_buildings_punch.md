# Remaining city constructions (punch list)

IDs / footprints / costs from EXE DAT `0x94FE5`, C2MODEL, Achea / D.SAV / 20230610. Host stamps live in `app/place.py` + `app/palette.py`. INT_CITY unused row-2 slots follow **decoded frames** (CITY1.256): **Industry** (sprite 21, blue/green bottles) then **Sanitation** (sprite 22, vessel + green cross). HELP.ENG Cty Icn is the same order (`industry` then `health`). Bind flyout **content** to the picture — do not invert again. Not a 4th palette row.

## Already placeable (City Only host)

| UI | Id | Pé | Custo | Como escolher |
|---|---|---|---|---|
| Housing → Tent | `0x82` | 1×1 rect | 6 | Housing |
| Roads / bridge | `0x52–0x5C` / `0x4E–0x51` | linha | — | Roads |
| Clear | rubble `0x05` → `0x1C` | rect | — | Clear (wipe N×N via `DAT_00094FE5` + `+5`; pares Circus / C.Maximus) |
| Reservoir | `0xBE` | 1×1 stamp-follow | 51 | Water → Reservoir |
| Aqueduct | stub `0xCB` · NS `0xD0` · EW `0xD1` · `0xD6` | 1×1 | — | Water → Aqueduct (não retile vizinhos como estrada) |
| Well | `0xD7` | 1×1 rect | 20 | Water → Well |
| Fountain | `0xDD` | 1×1 rect | 15 | Water → Fountain |
| Gardens | `0x78–0x7B` | 1×1 rect | 3 | Amenities → Gardens (LUT `0x93FCC`) |
| Praefecture | `0xE3` | 1×1 rect | 100 | Security → Praefecture |
| Tower | `0xBF` | 1×1 rect | 75 | Security → Tower |
| Barracks | `0xE4` | 3×3 stamp-follow | 400 | Security → Barracks |

Query é ferramenta (sem stamp). Zoom in/out são só chrome.

## Newly placeable this pass

N×N>1×1 = **stamp-follow** (um ghost, commit no mouse-up). 1×1 = rect (como Gardens). Wall = linha (como Roads).

| UI | Id | Pé | Custo | Como escolher |
|---|---|---|---|---|
| Plaza | `0x7C` (`+1=FLAG_PAD`, `+4=0x74`) | 1×1 rect | 12 | Amenities → Plaza (precisa de estrada / plaza cardinal; pode sentar na estrada) |
| Wall | EW `0xC2` `+4=0x04` · NS `0xC1` `+4=0x00` · `+1=0x02` | linha | 20 | Security → Wall |
| Gate | `0xC0` `+1=0x24` · NS `+4=0x92` · EW `+4=0x93` | combo | 5 | automático quando a linha de Wall cruza uma estrada (não é botão) |
| Aventine | `0xAF` `+3=0x04` `+4=04,06,05,07` | 2×2 | 100 | Forums → Aventine |
| Janiculan | `0xB2` `+4=10,12,15,11,14,17,13,16,18` | 3×3 | 400 | Forums → Janiculan |
| Palatine | `0xB7` `+4=44,46,49,4D,…53` | 4×4 | 0 | Forums → Palatine (**sem slot C2MODEL único — não debitar**) |
| Theater | `0xE5` `+3=0x0C` `+4=24,26,25,27` | 2×2 | 300 | Entert'ment → Theater |
| Odeum | `0xE6` `+4=28,2A,29,2B` | 2×2 | 500 | Entert'ment → Odeum |
| Coliseum | `0xE8` `+4=35,37,3A,36,39,3C,38,3B,3D` | 3×3 | 1000 | Entert'ment → Coliseum |
| Circus | `0xEB`+`0xEC` `+3=0x14` | **6×3** EW | 1500 | Entert'ment → Circus (um ghost pareado) |
| C.Maximus | `0xED`+`0xEE` `+3=0x14` | **4×8** NS | 2500 | Entert'ment → C.Maximus |
| Shrine | `0xA2` `+3=0x00` `+4=0x3C` | 1×1 rect | 80 | Worship → Shrine (`0xA3` é estado da família, não 2º tile) |
| Temple | `0xA6` `+4=40,42,41,43` | 2×2 | 200 | Worship → Temple |
| Basilica | `0xAB` `+3=0x0C` `+4=09,0B,0E,0A,0D,10,0C,0F,11` | 3×3 | 600 | Worship → Basilica |
| Grammaticus | `0xF3` `+3=0x08` `+4=40,42,41,43` | 2×2 | 250 | Education → Grammaticus |
| Rhetor | `0xF4` `+4=44,46,49,45,48,4B,47,4A,4C` | 3×3 | 500 | Education → Rhetor |
| Library | `0xF5` `+4=4D,4F,52,4E,51,54,50,53,55` | 3×3 | 1000 | Education → Library |
| Baths | `0xDF` `+3=0x08` `+4=20,22,21,23` | 2×2 | 30 | **Sanitation** (INT_CITY sprite 22 / grid 9, vessel+cross) → Baths |
| Hospital | `0xFB` `+4=56,58,5B,57,5A,5D,59,5C,5E` | 3×3 | 500 | Sanitation → Hospital |
| Market | `0xFC` `+4=30,32,31,33` | 2×2 | 40 | **Industry** (INT_CITY sprite 21 / grid 8, bottles) → Market |
| Factory | `0xFA` `+3=0x0C` `+4=3E…46` `+19` goods | 3×3 | 80 | Industry → Factory → type picker (C2.ENG Bakery + 7 named workshops) |

Housing evolve `0x82–0xA1` **não** são botões da paleta. Aventine / Janiculan / Palatine **são** stamps de Forum (não evolve-only).

Place checks: civic recusa rio / prédio ocupado / (na maior parte) estrada. Plaza `allow_road` + `need_road`. Wall recusa rio e ocupado; na estrada vira Gate. Sem check extra de água além do que o aqueduto / reservatório já fazem.

## Still blocked (não inventar)

| Nome | Porquê |
|---|---|
| **Arena `0xE7`** | DAT diz 3×3 e C2MODEL tem custo 700, mas **sem origem SAV / +4**. Flyout fica “leftover”. |
| Senate | **não** é stamp de cidade |
| Farms | só província |
| Housing extras (villa / palace grades) | evolve-only `0x82–0xA1` |
| Fountain / Well / Garden stages | evolve / runtime, não botões |
| Factory leftover nibbles | gems/iron/clay/marble/silk (4/6/8/10/12) — no UI name |
| Aqueduct LUT `0xCF–0xD6` completa | autotile parcial (NS/EW/junção) como antes |

Unseen leftovers (não stamp): `0xAE`/`0xB0`, `0xB5`/`0xB6`/`0xB8`, `0xA9`/`0xAA`/`0xAD`, `0xD8–0xDA`, `0xDB`, `0xCC–0xCE`, `0xBC–0xBD`, `0xF1–0xF2`, Circus/C.Max pares `0xE9`/`0xEA` / `0xEF`/`0xF0` (o host carimba `EB+EC` / `ED+EE`).

## Paleta / chrome

3 filas do EXE (`build_palette.md` §0) + 2 slots INT_CITY. Arte INT_CITY
(decoded PL8 = Cty Icn): house, road, forum, water, security, **industry**,
**health**, entert, temple, educat, gardens. Labels: **Industry**
(Market / Factory types) no sprite 21 bottles, **Sanitation**
(Baths / Hospital) no sprite 22 vessel+cross.

```
Row 1: zoom in | clear | Housing | Roads | Forums
Row 2: zoom out | Water | Security | Industry | Sanitation
Row 3: Query | Entert'ment | Worship | Education | Amenities
```

Sprite 21 / grid 8 = Industry (bottles). Sprite 22 / grid 9 = Sanitation
(vessel+cross). Do not swap Worship / Entertainment / Education / Forums.

Sprites 4–5 continuam rotate (não páginas da paleta). Não há 4ª fila.

## This pass

Stamps + flyouts ligados. Overlay / Play / dirty blit / zoom-pop / garden LUT / aqueduct-não-vira-estrada mantidos.
