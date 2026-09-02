# actor26 — Query / painel (província)

Não é o Query da **cidade** (`0x632A4`, walkers 58 B, C2.ENG **[66]**). Overlay da província: `view_frame` `0x3CF9A` quando `[0xCCB09]==5` e `[0x117A96]!=0`. Slot seleccionado `[0x1156D2]`. Record = `actor26_pool` `0x114500` + slot×`0xAF`.

| Clique | Função | Título |
|---|---|---|
| tipo **1** | `actor26_cohort_panel` `0x5BABF` | **[4]** + `rec[+0x28]` (`Prima Cohors` = 0) |
| tipo ≠ 1 | `actor26_query_tooltip` `0x5BE03` | **[44]** + skip por tipo (abaixo) |

Corpo do relatório da coorte: `actor26_cohort_report_body` `0x5C036`. Ano: `format_year_bc_ad` `0x62118`.

Save de referência: **ACHEA23** (`findings/achea_province_walkers.md`). HUD **187 BC January** / **28561 Dn**. ACHEA23 só tem tipos **1** e **6**.

### Tipos 1–8 (`rec[+4]`)

Dispatch `actors26_tick` `0x45A7A` → `0x99D44[type]` (tipo 0 unused `0x45D8E`; 1–8 abaixo). Query: tipo 1 = painel; senão `actor26_query_tooltip` `0x5BE03` (`EAX=0x2D` **[44]**, `EDX` por tipo). Spawn de terra: `economy_recompute` `0x3FCA0` → `FUN_000528bb` (tenta **5, 4, 3, 2** nesta ordem, um por pulso). Banner: `FUN_00058c87` `EAX` = slot oficial **+ 1** (igual `FUN_00026f16`; invasão na cidade `EAX=0x53` → **[82]** `The City Is Attacked!`). Sem string **Wolf** no C2.ENG.

| Tipo | Query **[44]+EDX** | Banner ao nascer | Handler / spawn | Conf. |
|---:|---|---|---|---|
| **1** | painel **[4]** (não o tooltip) | — (jogador / `CALL 0x2AA02` `EAX=1` @ `0x3123E`) | `0x45D8F` `actor26_set_sprite_t1` | alta (ACHEA23) |
| **2** | EDX 0x19 → **Enemy Army** | **[93]** `Enemy Invades!` (`EAX=0x5E` @ `0x532EE`) | `0x45E39` + `actor26_set_sprite_t2`; spawn `FUN_00053215` `EAX=2`; tropas ×8; `marchb2.wav`; origem `[0x1026E8]` | alta EXE; sem save |
| **3** | EDX 0x1A → **Barbarians** | **[92]** `Barbarian Invasion!` (`EAX=0x5D` @ `0x53203`) | `0x45E64` + `FUN_00047ae2`; spawn `FUN_00053127` `EAX=3`; tropas ×6; `marchb2.wav`; origem `[0x1026E8]` | alta EXE; sem save |
| **4** | EDX 0x1A → **Barbarians** | **[90]** `Raiders Sighted!` (`EAX=0x5B` @ `0x53115`) | mesmo handler que 3; spawn `FUN_0005302b` `EAX=4`; tropas ×3; `marchb2.wav`; origem `[0x1026E8]` | alta EXE; sem save |
| **5** | EDX 0x1A → **Barbarians** | **[91]** `Local Uprising!` (`EAX=0x5C` @ `0x53363`) | `0x45E75` (sprite t2 se `[0x1025CC]∈{6,0xF,0x12,0x22}`, senão `FUN_00047ae2`); spawn `FUN_00053300` `EAX=5`; tropas ×`FUN_000533fb` (vila `0x93`–`0x96`); `uprise.wav`; origem **`[0x1025CC]`** (esta província) | alta EXE; sem save |
| **6** | EDX 0x1B → **Merchant Ship** | — (comércio) | `0x45EC3` `FUN_00047a44(0x4E)`; spawn `FUN_00054087` `EAX=6` só | alta (ACHEA23) |
| **7** | EDX 0x1C → **Enemy Ship** | — | `0x45ED2`: `[0x102CF0]=2` + **RET**. **Nenhum** `actor26_spawn` com `EAX=7` neste 1.1A | tooltip só |
| **8** | EDX 0x1D → **Barbarian Ship** | — | mesmo RET que 7. **Nenhum** spawn `EAX=8` | tooltip só |

Tipos **2–5** são exércitos terrestres (notas antigas certas). **7–8 “sem AI”** também é certo neste build; o mapeamento posterior para navios no tooltip **não** contradiz isso — só não há spawn. Não há unidade “Wolf”.

Ao pisar Your City `0x92` (`FUN_0004987d`): qualquer **2–5** chama `walker_spawn_type3_from_actor26` `0x53562` (walker cidade tipo 3 **Enemy**) e põe state 2. Pisar `0x97` / outro occupied manda **[112]/[113]** (`EAX=0x71`/`0x72`), não o banner de spawn.

Como ver no jogo (ACHEA23 não chega): esperar o pulso anual / paz (`FUN_00052eb9` + RNG). Tipo **5** nasce junto de um tile `0x93`–`0x96` (estado de vila; **não** é Roman Town `0x97` / Border Town `0x98` — `0x97` vira `0x93` quando um 2–5 pisa) com *Local Uprising!*. Tipo **4** = *Raiders Sighted!* (raid que entra). Tipo **3** = *Barbarian Invasion!* (horda). Tipo **2** = *Enemy Invades!* + Query **Enemy Army** (rivais). Query em 3/4/5 diz só **Barbarians** — o banner é que distingue.

---

## 1. C2.ENG (não está no índice de 146 como frase única)

Lookup: `FUN_00026f16` — `EAX` = slot oficial **+ 1**, `EDX` = extras NUL. Igual ao Query da cidade.

### Painel da coorte — oficiais **[4]**, **[44]**, **[25]**, **[34]**

| Uso | EAX | EDX | String |
|---|---:|---:|---|
| Nome da unidade | `0x5` | `rec[+0x28]` | **[4]** `Prima Cohors`, The Rabbits, … The Defenders |
| `Formed ` | `0x2D` | 0 | **[44]** `Formed ` (espaço no fim) |
| Ano | `format_year_bc_ad` | — | decimal `abs(i32)` |
| Era | `0x1A` | 0 se ano&lt;0; 1 se ≥0 | **[25]** `BC` / **[25]+1** `AD` |
| Movement / Route / Return / to Fort / Cohort / Rest | `0x2D` | 1…6 | botões do screenshot |
| COHORT REPORT | `0x2D` | 7 | **[44]+7** |
| We have  / battle-ready soldiers | `0x2D` | 8 / 9 | |
| Confined to fort | `0x2D` | 10 | se readiness=0 e `+0x93≠0` |
| Troop morale: … | `0x2D` | 11+`+0x94` | VERY LOW…**EXCELLENT** (0…4) |
| Readiness: … | `0x2D` | 16+`+0x95` | UNFIT…**EXCELLENT** (0…4) |
| Heavy, / Light, / Sling, / Auxiliaries | `0x2D` | 21…24 | |
| Demobilized / Normal / Minor / Major | `0x23` | ver `+0xA0` | **[34]** extras |

**Formato de “Formed 223 BC”:** não é um `printf("Formed %d BC")`. Três pedaços: `[44] "Formed "` + número (`abs` do i32) + `[25] "BC"`. Ano **negativo** = a.C. (mesmo encoding que `city_year` `0x102AA0` / chunk 25: HUD −187 → 187 BC). ACHEA23: `+0x3A` = **−223**.

### Tooltip do navio / exército — **[44]** + tipo

`actor26_query_tooltip` `0x5BE03` (só tipo ≠ 1). Assembly: `CMP EAX,2` / `5` / `6` / `7` depois `MOV EDX,…` / `MOV EAX,0x2D` / `CALL FUN_00026f16`. Tipo 1 nunca entra aqui, então **≤2 = tipo 2** na prática.

| `rec[+4]` | EDX | Título |
|---:|---:|---|
| ≤2 | 0x19 (25) | Enemy Army |
| 3…5 | 0x1A (26) | Barbarians |
| **6** | **0x1B (27)** | **Merchant Ship** |
| 7 | 0x1C (28) | Enemy Ship |
| ≥8 | 0x1D (29) | Barbarian Ship |

Nesta 1.1A o tipo **6** cai sempre em Merchant Ship. **7** / **8** seriam Enemy / Barbarian Ship; ACHEA23 não tem 7–8 (handlers RET; zero `actor26_spawn` com esses EAX). Não há save que mostre Enemy Ship.

Tipo 6 extra: `[44]+30` `Carrying` + bem + `[44]+31` `from` + origem.

---

## 2. Record 175 B — campos fechados neste passe

Pool SavChunk **7**. Spawn de navio `FUN_00054087` grava `city_year` em `+0x3A` e os params em `+0x96…+0x99`.

| Off | Tipo | Quem lê | ACHEA23 slot 1 (coorte) | Notas |
|---:|---|---|---|---|
| +4 | u8 | ambos | 1 | tipo |
| +0x28 | u8 | painel | **0** | índice **[4]** → Prima Cohors |
| **+0x3A** | **i32** | `format_year_bc_ad` | **−223** | ano formado (signed BC) |
| +0x3E … | 14 × 4 B | ícones | 14× `(1,1,0,0)` | loop `ECX&lt;0xE`; tipo 1=Heavy. Screenshot mostra uma fila (~16); o EXE itera **14** |
| **+0x7A** | i32 | relatório | 0 | Sling |
| **+0x7E** | i32 | relatório | 0 | Light |
| **+0x82** | i32 | relatório | **1330** | Heavy |
| **+0x86** | i32 | relatório | 0 | Auxiliaries |
| **+0x8A** | i32 | relatório | **1330** | battle-ready (`We have %d battle-ready soldiers`) |
| +0x92 | u8 | espaçamento ícones | 14 | |
| +0x93 | u8 | “Confined to fort” | 0x30 | |
| **+0x94** | u8 | morale 0…4 | **4** | EXCELLENT. Spawn default era 2 |
| **+0x95** | u8 | readiness 0…4 | **4** | EXCELLENT |
| **+0xA0** | u8 | rank | **2** | 0=Normal, 1=Minor, **2=Major**; state 10=Demobilized |

| Off | Tipo | Quem lê | Navios ACHEA23 | Notas |
|---:|---|---|---|---|
| +0x23 / +0x24 | u8 | anim / sprite | 7/0, **12**/1, 11/0 | **não** é cargo. Incrementado em `FUN_00049396`; zero em `FUN_000471ea` |
| **+0x96 / +0x97** | u8 | spawn | (0,44), **(59,10)**, (0,44) | portal: Campania / **Trade Route `0x9D`** / Campania |
| **+0x98** | u8 | origem UI | 6, **2**, 6 | `skip` = `LUT[0x95393 + province×4 + (+0x98>>1)] + 1` sobre **[5]** (Latium, Campania, … **Trade Route** em +45…+47) |
| **+0x99** | u8 | cargo UI | 7, **12**, 7 | **enum 0–15** (ver §3). Silk=12 |

`+0x3A` nos navios = `city_year` no spawn (i32 **−188** nesta save) — o tooltip **não** imprime Formed.

---

## 3. Bens (Silk) = mesmo enum 0–15

C2.ENG **[15]** `Market` depois: Wheat, Grapes, Cattle, Wool, Gems, Lead, Iron, Copper, Clay, Sand, Marble, Stone, **Silk**, Spices, Ivory, Fish.

O tooltip faz `EAX=0x10` (**[15]**), `EDX = rec[+0x99] + 1` → Silk quando `+0x99==12`.

É o **mesmo índice** que:

| Sítio | Como |
|---|---|
| Factory cidade `0xFA` | origin `tile[+19] & 0xF` (`findings/factory.md`) — nibble **12** = silk (EXE `silk sup/sat`) |
| Chunk **335** `0xD2AEC` | `province_goods_setup` `0x577E4` grava ids **&lt; 0x10** |
| Chunk **339** `0xD2B6C` | `goods_16x48` indexado por esse id |

**C2MODEL.DAT** não tem esta tabela de nomes/ids — só custos / housing / ranks. O enum vive no EXE + C2.ENG.

---

## 4. ACHEA23 — qual navio tem Silk

| slot | (x,y) | Excel | `+0x99` | `+0x96,97` | UI (tipo 6) |
|---:|---|---|---:|---|---|
| 2 | (8, 43) | J45 | 7 Copper | (0, 44) Campania | Merchant Ship; *não* Queryado pelo user |
| **3** | **(44, 18)** | **AT20** | **12 Silk** | **(59, 10) Trade Route** | **Carrying Silk from Trade Route** |
| 4 | (12, 28) | N30 | 7 Copper | (0, 44) Campania | Merchant Ship; *não* Queryado |

Só o slot **3** fecha Silk + origem Trade Route (Q&A + bytes).

---

## 5. Ainda opaco

- LUT `0x95393` (4 bytes / província → skip **[5]**): fórmula fechada; bytes no `c2_x.bin` não estão em VA identity — mapa LE ainda falho.
- Tipos 2–5 / 7–8: zero nesta save (ACHEA23). Títulos e banners acima são do EXE + C2.ENG; falta Query ao vivo. 7–8 sem spawn neste 1.1A.
- `+0x23` nos parked (12 / 11) parece frame congelado, não cargo.
- Painel de **batalha** `FUN_000649B1` / `FUN_00064F8A` (EAX=`0x47` = **[70]** Heavy Infantry…) é outra UI, não este Query da província.
