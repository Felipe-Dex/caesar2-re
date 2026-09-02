# Achea — actors da província

Não são os **91 walkers da cidade**. Cidade = SavChunk **8** (201 × 58). Província = SavChunk **7** (`actor26_pool`, **26 × 175** @ file+16). Tick `actors26_tick` `0x45A7A`. Draw `MY_STDS.PL8` via `tile[+7]`.

| | |
|---|---|
| Planilha | `findings/Achea_province_walkers.xlsx` |
| Regenerar | `tools/_achea_province_walkers_xlsx.py` |
| Grade da província (prédios) | `findings/Achea_province.xlsx` — **não** foi mexida |
| Save | `C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV` |

## Convenção de coordenada

**Igual ao `Achea_province.xlsx`.** Linha 1 = **x**. Coluna A = **y**. Célula Excel = tile `(x, y)`.

`(0,0)` = ponta **norte** do losango. Confirmado: Your City 2×2 continua em `(32,24)` = AH26.

`x`/`y` do actor estão em **`+6` / `+7`** (não `+4`/`+5` do walker 58 B). `tile_off` em `+8` bate com `(y*60+x)*8` nos 4 vivos — o tile de ocupação é inteiro. **`+0xC` / `+0xD` são frac** (sub-tile do sprite). O desenho pode ficar um pouco ao lado do centro da célula.

| Campo | walker cidade 58 B | actor26 175 B |
|---|---|---|
| occupied | +0 | +0 |
| type | **+2** | **+4** |
| x / y | **+4 / +5** (0–79) | **+6 / +7** (0–59) |
| dest | +0xC / +0xD | +0xE / +0xF |
| state | +0x10 | +0x12 |

## ACHEA23 — 4 vivos (tipos 1 e 6)

Slots 5–25 vazios. Tipo 3 **bárbaro da cidade** não mora aqui: nasce no chunk 8 quando um actor tipo **2–5** pisa Your City `0x92`. Nesta save **não há** tipos 2–5 nem 7–8.

Offsets / C2.ENG / Ghidra: **`findings/province_actors.md`**.

| slot | tipo | Query (ACHEA23) | (x, y) | Excel | estado | dest | extra |
|---:|---:|---|---|---|---:|---|---|
| 1 | **1** | painel **Prima Cohors** · Formed **223 BC** | (36, 27) | **AL29** | 8 | nenhum (`0x7F`,`0x80`) | 1330 Heavy; morale/ready EXCELLENT; rank Major. HUD continua **187 BC** |
| 2 | **6** | **Merchant Ship** | (8, 43) | J45 | 12 | **(1, 44)** Campania | cargo `+0x99`=7 Copper; portal (0,44). Andando |
| 3 | **6** | **Merchant Ship** · **Carrying Silk from Trade Route** | (44, 18) | **AT20** | 13 | parked | **`+0x99`=12 Silk**; portal **(59,10)** Trade Route |
| 4 | **6** | **Merchant Ship** | (12, 28) | N30 | 13 | parked | cargo `+0x99`=7 Copper; portal (0,44) |

`tile[+7]` nos quatro = o slot (1…4). Outros `+7` ≠ 0 na grade são índice de stamp 2×2, **não** actor.

Tipo **6 nesta save = Merchant Ship** (Q&A + picker). Não afirmar que todo tipo 6 em qualquer save é merchant: o EXE 1.1A mapeia **6→Merchant / 7→Enemy Ship / 8→Barbarian Ship**, mas 7–8 estão vazios aqui (AI = RET).

## Query — não é [66] / `0x632A4`

Títulos da **cidade** = C2.ENG **[66]** + (tipo−1): Forum Clerk, … Rioter. Picker na gap `0x632A4`.

Títulos de **exército / navio** = extras de **[44]** `Formed `. Picker da **província**: `view_frame` se `[0xCCB09]==5`:

* tipo **1** → `actor26_cohort_panel` `0x5BABF` (diálogo grande, não o título “Cohort” sozinho).
* tipo ≠ 1 → `actor26_query_tooltip` `0x5BE03`.

| skip a partir de [44] | string | tipo EXE |
|---:|---|---|
| 5 | **Cohort** | botão / rótulo, não o título do painel |
| 25 | **Enemy Army** | tipo ≤ 2 (tooltip; tipo 1 usa o painel) |
| 26 | **Barbarians** | tipo 3–5 |
| 27 | **Merchant Ship** | **tipo 6** (ACHEA23 confirmado) |
| 28 | **Enemy Ship** | tipo 7 — zero nesta save |
| 29 | **Barbarian Ship** | tipo 8 — zero nesta save |
| 30 / 31 | **Carrying** / **from** | só tipo 6 |

Screenshot da coorte (187 BC / 28561 Dn): **Prima Cohors**, **Formed 223 BC**, 14 ícones no record (UI mostra uma fila), “We have **1330** battle-ready soldiers.” “**1330** Heavy, 0 Light, 0 Sling, 0 Auxiliaries.” “Troop morale: **EXCELLENT**” “Readiness: **EXCELLENT**.” Botões Movement Route / Return to Fort / Cohort Rest. Rank **Major**.

## Q&A fechado (não precisa reclicar)

| ★ | tipo | (x, y) | resultado |
|---|---:|---|---|
| 1 | 1 | (36, 27) AL29 | painel Prima Cohors — **não** Forum Clerk |
| 2 | 6 | (44, 18) AT20 | Merchant Ship + Silk / Trade Route |

Tipos 2–5 e 7–8: zero nesta save.
