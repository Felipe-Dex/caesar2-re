# Province — gaps (2026-09-01)

O que ainda falta no mapa/sim provincial, e o que o EXE + SAV fecharam **sem** Query novo. Taxonomia actor26 (terra vs mar, tropas ×8/×6/×3) fica em `findings/province_actors.md` — não reabrir.

Saves: **ACHEA23** (pid chunk **223** = **15** → C2.ENG **[5]+16 `Achaea`**). Também lidos: 20230610 (pid 4), FELIPE01 (12), FELIPE02 (14). Chunk 14 @ file **178395**.

---

## Status

| Item | Status | Onde |
|---|---|---|
| Bens em Farm / Mine / Quarry / Warehouse | **Done** | origin `tile[+7] >> 4` = enum 0–15; Warehouse também `+3 & 0x40` |
| Port cargo vs flags em `+7` | **Partial** | origin `+7`: bit **`0x80`** = água (`FUN_0006d497`); bits **`0x1C>>2`** = fullness 0–3. **Não** é o nibble de bem |
| Trading post `+7 & 0x60` | **Partial** | escolhe um dos 4 bens de `climate_lookup_init` (vizinhos) |
| Chunk 14 `+5` / `+2` / `+6` | **Partial** | `+6` = 0 em 3600 tiles (3 saves). `+2` = `00`/`FE`/`FF`. `+5` terreno 0/1 |
| LUT `0x95393` nomes de origem | **Done** | 44×4 vizinhos; skip **[5]+(byte+1)** |
| Chunk **335** Industry (8 linhas) | **Done** (ACHEA23) | 4 locais + 4 import |
| Montanhas `0x86`, `0x8A`, `0x8E` | **Done** (outras saves) | mesma família; Achea continua sem |
| Montanhas `0x8F`–`0x91` | **Needs user save** | `apply_regions` carimba; 0 nos 4 SAV |
| Muros `0xB7`–`0xBD` / `0xC0` | **Partial** | tabela EXE fechada; `0xBC`/`0xBD` sem tile nos SAV |
| Terreno `0x00`–`0x7C` nomes | **Needs Query** | classes só; LUT `0x97B40` é sprite, não string |
| actor26 tipos **2–5** | **Needs user save + Query** | EXE+C2.ENG já nomeados; ACHEA23 só 1 e 6 |
| Navios **7–8** | **Done** (não nascem) | handler RET; zero `actor26_spawn` EAX=7/8 neste 1.1A |
| `actors26_tick` AI detalhe | **Partial** | dispatch + spawn documentados; corpo 2–5 sem save |

---

## 1. Done agora (EXE + ACHEA23 / outras SAV)

### 1.1 Bens no record 8 B — origin only

`FUN_0004327b` (economia provincial) + overlay `FUN_0003a003`. Mesmo enum que factory `+19` / navio `+0x99` / C2.ENG **[15]+1**.

| Prédio | Id | Campo | ACHEA23 (origins) |
|---|---|---|---|
| **Farm** | `0xDF` | `+7 >> 4` | (11,17) (24,24) (18,38) → **1 Grapes** |
| **Mine** | `0xE3` | `+7 >> 4` | (23,10) **5 Lead**; (14,34) **6 Iron**; (22,35) **5 Lead** |
| **Quarry** | `0xE7` | `+7 >> 4` | (20,2) **8 Clay** |
| **Warehouse** | `0xD4` | `+7 >> 4` **e** `+3 & 0x40` = ícone | 19/24 com ícone: Clay / Copper / Lead / Grapes / Iron / Marble. Vazios: `+3` sem `0x40`, `+7=0` |
| Work camp / Shipyard | `0xD3` / `0xD5` | `+7` = 0 ou índice 0…3 do 2×2 | sem nibble de bem |

As outras 3 células do 2×2 ficam com `+7` = 1/2/3 (índice do stamp). **Não** copiar o nibble delas.

Se `+7 >> 4 == 0` no pulso: Mine puxa `0x95ADF[pid*10]`; Quarry `0x95AE2[pid*10]`. Achea já está preenchida.

Casa com a planilha: `Warehouse (Lead)` / `Warehouse (Grapes)` / `Farm (Grapes)` / `Mine (Lead)` / `Quarry (Clay)` — o nome entre parênteses **é** este nibble, não um segundo id.

### 1.2 Chunk 335 `0xD2AEC` (Industry) — ACHEA23

`province_goods_setup` `0x577E4`. File **219524**. 8 slots × 16 B: dword id + dword kind (0=local, 1=vizinho “aberto”, 2=import).

| Slot | Id | Kind | Nome |
|---:|---:|---:|---|
| 0–3 | 1, 5, 6, 8 | 0 | Grapes, Lead, Iron, Clay |
| 4 | 7 | 1 | Copper |
| 5–7 | 12, 10, 7 | 2 | Silk, Marble, Copper |

Linha local Achea em `0x95ADC + 15*10`: `1, 16, 16, 5, 6, 16, 8, …` (16 = skip). Casa com Farm/Mine/Quarry.

### 1.3 LUT `0x95393` — origens / vizinhos (c2_x.bin, VA − `0x10000`)

44 × 4 bytes. Valor `n` → C2.ENG **[5] + (n+1)** (Latium…; **+45…+47 Trade Route**; +48 Local Waters).

Achea pid **15**, vizinhos `[14, 44, 16, 1]` → **Macedonia / Trade Route / Creta / Campania**.

Primeiro byte de `0x95ADB[n*10]`: 14→Copper, 44→**Silk**, 16→Marble, 1→Copper. **Igual** aos slots 4–7 do chunk 335 e aos Sea Lane `0x9D`/`0x9E`/`0x9F` + navios ACHEA23.

Fórmula do tooltip (`actor26_query_tooltip`): `skip = LUT[pid*4 + (rec[+0x98]>>1)] + 1` sobre **[5]**. Já estava no actors; os **bytes** agora leem no image.

### 1.4 Montanhas que Achea não tem

`apply_regions_map` `0x706C3` carimba a gama inteira. Outras SAV fecham o `+4`:

| Id | Stamp | `+4` | Onde | Nome |
|---|---|---|---|---|
| `0x86` | 2×2 | 12…15 | 20230610, FELIPE02 | **Small Mountain** |
| `0x8A` | 2×2 | 28…31 | 20230610, FELIPE02 | **Small Mountain** |
| `0x8E` | 3×3 | 49…57 | FELIPE02 (29,41)–(31,43) | **Mountain** |
| `0x8F`–`0x91` | 3×3 | 58…84 / `0x91` variant `0x4C` | **0** nestes SAV | Mountain (EXE); falta tile |

`+1=0x10`, `+3=4` (sheet 4), igual ao resto da família.

### 1.5 Navios 7–8

Confirmado neste 1.1A: handlers `0x45ED2` RET; nenhum spawn EAX=7/8. Tooltip **Enemy Ship** / **Barbarian Ship** existe; unidade não nasce. Não pedir screenshot.

---

## 2. Partial (mapa feito; falta um clique ou outro SAV)

### 2.1 Port `0xEC`/`0xEF` origin `+7`

Depois do stamp (0…3) o tick **reescreve** o origin. Bits: `0x80` água, `0x1C` nível. ACHEA23 origins: `0x60`, `0x40`, `0xC0`, `0xE0`, `0x74` — **não** ler como nibble de bem (Iron/Gems/Silk…). Query do Port (o que a UI diz que carrega) ainda falta.

### 2.2 Trading post `0xEB`

(4,2) origin `+7=0x10`. `FUN_0004327b`: `+7 & 0x60` escolhe `DAT_001025e0` / `8c` / `f4` / `a0` (bens dos 4 vizinhos). Query “Trading Post (Grapes?)” confirmaria.

### 2.3 Chunk 14 bytes extra

| Off | ACHEA23 | Leitura |
|---:|---|---|
| **+0…+4, +7** | ver `province_map.md` + §1.1 | id / flags / sheet / variant / slot-ou-bens |
| **+2** | 1962×`00`, 1339×`FE`, 236×`FF` (linha norte) | sujo / anim; stamp não grava |
| **+5** | terreno 2019×`01` + 1130×`00`; 6×`0x41` em (40–42,24–26); specials **0** | não é bem. Demolir (`FUN_00069963`) zera |
| **+6** | **3600 × 0** (Achea / 20230610 / FELIPE01) | morto neste build |

### 2.4 Muros `0xB7`–`0xC0`

Tabela cidade−10 em `province_map.md`. FELIPE01 tem `B7`–`BB`, `BE`, `BF`, `C0`. **`0xBC` / `0xBD`** (canto NW / fim-S) sem tile. Achea só `B6`/`BE`/`BF`.

### 2.5 `actors26_tick`

Jumptable `0x99D44`, spawn e banners: `province_actors.md`. Corpo AI dos tipos 2–5 não pisado em ACHEA23.

---

## 3. Needs user (save hostil, REGIONS de outra província, ou Query)

1. **Query tipos 2–5** quando nascerem (*Enemy Invades!* / *Barbarian Invasion!* / *Raiders Sighted!* / *Local Uprising!*). ACHEA23 não tem. Painel/tooltip + (x,y) + screenshot. **Não** mudar a tabela terra/mar / ×8 ×6 ×3.
2. **Montanha `0x8F`/`0x90`/`0x91`:** assignment cujo `regions.dat` traga esses bytes (ou print + SAV). EXE já diz 3×3 Mountain.
3. **Port / Trading post Query:** texto de carga / “from”. Fecha §2.1–2.2.
4. **Terreno `0x00`–`0x7C`:** Query 4–6 células por classe (água `0x10`–`0x17`, carpet `0x22`–`0x29`, meadow `0x1C`–`0x1E` já Meadow, resto `0x2A`–`0x7C`). Sem string no EXE. Achea **não tem** `0x0C` `0x0F` `0x18`–`0x1B` `0x1F` `0x20` `0x64`–`0x65` `0x67`–`0x6B` `0x6D` `0x6F` `0x72` `0x75` `0x78` `0x7A`–`0x7C`.
5. **Muro `0xBC`/`0xBD`:** só se aparecer noutro mapa (confirmar canto/fim).
6. Planilha `Achea_province.xlsx`: roads `0xA0`–`0xAA` e a maior parte das hills ainda `Desconhecido` — cosmética; ids já nomeados.

Não precisamos ao vivo para o primeiro passe do Forum — ver `findings/forum_qa.md`.

---

## Tools (read-only)

Dumps desta sessão não foram deixados no repo. Reproduzir:

```text
# chunk 14 + LUT: VA 0x95393 / 0x95ADB no c2_x.bin (base 0x10000)
# chunk 335 ACHEA23 file 219524
# pid = i32 LE @ file 208216 (chunk 223)
```
