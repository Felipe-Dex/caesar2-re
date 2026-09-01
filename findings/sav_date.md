# Data do HUD (mês + ano)

Achea print: **187 BC January**, tesouro **28561**. Confere no SAV. Chunk 5 **não** é o ano.

Parser: `app/calendar.py`. Dump: `python tools/_sav_date_dump.py`. Não avança o calendário no viewer (outro agente mexe em `walkers_tick`).

---

## 1. Onde mora

| Campo | Chunk | VA | Size | File off | Tipo | Achea |
|---|---:|---|---:|---:|---|---|
| **ano** | **25** | `0x102AA0` `city_year` | 4 | **207328** | i32 LE | **−187** |
| **mês** | **26** | `0x102A88` `city_month` | 4 | **207332** | i32 LE 0…11 | **0** (January) |
| tesouro | 28 | `0x102AAC` | 4 | 207340 | i32 | 28561 |
| gate semanal? | 27 | `0x102A74` | 4 | 207336 | i32 | **0** em todos os saves amostrados |
| seed do assignment | 325 | `0x102AB4` | 4 | 219476 | i32 | **−300** (sempre) |
| anos no assignment | 326 | `0x102A9C` | 4 | 219480 | i32 | 111 (Achea) |
| (morto) year-BC hyp | 5 | `0x102BA4` | 4 | 8 | u32 | 65 ≠ 187 |

Mês **0 = January** … **11 = December**. `start_city_assignment` `0x1049B` grava ano **−300**, mês **0**, gate **0**.

HUD da cidade (`FUN_0006189d` `0x6189D`):

1. `FUN_00062118(EAX=ano, EDX=0x130)` — imprime o valor absoluto; se ano `< 0` acrescenta **BC** (senão **AD**).
2. `FUN_00026f16(EAX=0x19, EDX=mês)` — `C2.ENG` slot de arquivo **[24]** = `January`, depois pula `mês` strings NUL.

Os 12 meses **não** são 12 slots da tabela de 146. Estão empacotados a partir do offset 3149:

```text
January\0February\0March\0April\0May\0June\0July\0
August\0September\0October\0November\0December\0BC\0AD\0To\0Week 1
```

Índice EXE `0x19` = slot de arquivo 24 (`+1` por causa da tabela em `file+8`). `December` não aparece como slot próprio no `extract_eng`.

---

## 2. Saves (mesmo parser)

| Save | Chunk 25 | Chunk 26 | HUD lido | Chunk 5 |
|---|---:|---:|---|---:|
| **ACHEA23** | −187 | 0 | **187 BC January** | 65 |
| 20230610 | −269 | 10 | 269 BC November | 19 |
| FELIPE01 | −258 | 2 | 258 BC March | 50 |
| FELIPE02 | −228 | 0 | 228 BC January | 29 |
| LASTYEAR | −296 | 0 | 296 BC January | 33 |
| D.SAV | −300 | 0 | 300 BC January | 33 |

Achea: tesouro chunk 28 = **28561** (print). D.SAV é assignment fresco (ano seed).

Como conferir no hex (Achea): `i32` @ **207328** = `45 FF FF FF` (−187); @ **207332** = `00 00 00 00`. No jogo: canto do HUD, **187 BC January** + **28561 Dn**.

---

## 3. Quem avança (não implementar aqui)

Cada wrap de `city_sim_phase` `0x3F60C` (fase `> 0xD6`) chama **`calendar_advance` `0x3FBCF`** (era `FUN_0003fbcf`):

```
[0x102A74] += 1
if > 0:                    ; nestes saves sempre dispara (gate=0)
    [0x102A74] = 0
    economy_recompute()
    city_month += 1
    if city_month < 12:
        FUN_00054dc5()     ; tesouro negativo → pode forçar forum
    else:
        city_month = 0
        city_year += 1     ; −187 → −186 = 186 BC
        [0x102A9C] += 1
        [0x102AC0] += 1
        FUN_0003fd3e()     ; snapshot pop/tesouro/ano
        sav_year_end()     ; lastyear.sav se as flags deixarem
```

Um ciclo de fases (~`0xD7` pulses de sim) = **um mês**. `Week 1` existe no `C2.ENG` mas o dword do chunk 27 está **0** em todos os saves desta pasta — a “semana” do HUD ainda não foi pinada.

`FUN_00010529` (quando `view_submode==3`): se mês ≠ 0, zera o mês e `city_year += 1`, depois `init_new_city`.

Não meter isto em `app/sim.py` / `walkers_tick`. `app/calendar.py` só **lê**.

---

## 4. Ainda opaco (lista velha — ver §5)

- Semana (`Week 1`) — **fechado em §5**: não é SavChunk; HUD não imprime.
- Chunk 5 — view scalar (`city_view_reset` = 40), **não** calendário.
- Chunk 331 (`0x102AC0`) — **parcial em §6**: incrementa no wrap do ano; em Achea/FELIPE casa com o contador de HISTORY desta cidade.
- Host: data no título da janela ainda não está ligada (evitar conflito com o viewer de walkers).

---

## 5. Week 1 — não é campo de SAV (2026-08-30)

C2.ENG tem **Week 1…Week 4** no mesmo run empacotado a partir de January (skip **15…18**). Slot da tabela **[27]** = `Week 1`; 2–4 não têm slot próprio.

| Hipótese | Resultado |
|---|---|
| Chunk **27** `0x102A74` | **Não.** Só `start_city_assignment` (zera) e `calendar_advance` (`+=1`; se `>0` volta a 0). Gate mensal, **0** em todos os saves (Achea, 20230610, FELIPE01/02, LASTYEAR, D/A/B/C). |
| HUD `0x6189D` | Imprime **ano + BC/AD + mês**. Nenhum `FUN_00026f16` com EAX=`0x1C` / skip 15–18. Print Achea: **187 BC January** (sem semana). |
| Dword 1…4 noutro chunk | Nenhum dos escalares ao lado do calendário (24–35, 325–338, 341) é 1–4 variável entre saves. |

`city_sim_phase` chunk **24** `0x1026A8` é o único contador intra-mês (Achea **104**, FELIPE01 **108**, FELIPE02 **160**, 20230610 **17**, wrap `0xD6`). Dá para *derivar* semana `1 + phase*4/0xD7` em runtime, mas o EXE **não** grava isso e o HUD da cidade **não** mostra. Week fica como string de Query/outro painel (sites `0x6377c` / `0x6402b` usam índice `0x1C` em contexto de walker, não no chrome da data).

Como conferir: no jogo, canto do HUD = ano + mês. `python tools/_hud_fields_dump.py` — chunk 27 sempre 0.

---

## 6. Outros escalares HUD / calendário (Achea + saves)

| Campo | Chunk | VA | File off | Achea | Significado |
|---|---:|---|---:|---:|---|
| **ano** | 25 | `0x102AA0` | 207328 | **−187** | HUD 187 BC |
| **mês** | 26 | `0x102A88` | 207332 | **0** | January |
| gate mensal | 27 | `0x102A74` | 207336 | 0 | não é Week |
| tesouro | 28 | `0x102AAC` | 207340 | **28561** | 28561 Dn |
| **população** | **32** | `0x102AB0` | 207356 | **9561** | snapshot de fim de ano; limiar 500/1000 em `calendar_advance` |
| **Population Tax** (ano) | **34** | `0x102A5C` | 207364 | **5209** | `FUN_00056c9f`; HISTORY +8 |
| **Industry Tax** (ano) | **35** | `0x102A34` | 207368 | **2797** | `FUN_00056cec`; HISTORY +12 |
| saldo contas | 33 | `0x102A64` | 207360 | 2948 | surplus/loss do painel Treasury |
| rating C2MODEL | 341 | `0x102A58` | 220564 | 6 | pequeno (1…20 nestes saves); **não** é Peace/Prosperity |
| **overlay id** | **1** | `0x117A59` | 1 | **4** | **Unrest** (print). Ver `forum.md` §8 |
| view kind | 0 | `0x117A8D` | 0 | 0 | cidade |
| sim phase | 24 | `0x1026A8` | 207324 | 104 | pulso intra-mês |
| seed assignment | 325 | `0x102AB4` | 219476 | −300 | sempre |
| anos de carreira | 326 | `0x102A9C` | 219480 | 111 | `+=1` no wrap do ano |
| anos nesta cidade / hist | 331 | `0x102AC0` | 219500 | 36 | `+=1` no wrap; Achea=FELIPE casa com chunk 338 |
| HISTORY count | 338 | `0x1025A4` | 219788 | 36 | cap 200 |
| HISTORY ring idx | 336 | `0x1025F0` | 219780 | 36 | próximo slot 20 B |
| countdown tesouro<0 | 251 | `0x102A6C` | 208328 | 0 | força forum |

Peace / Prosperity / Culture existem no pack C2.ENG a partir do slot **30** (skip 8–10). **Não** entram no trailer HISTORY (lá vão imposto + pop + tesouro + ano). Não pinados a chunk nesta passada.

Dump: `python tools/_hud_fields_dump.py`. HISTORY: `findings/history_dat.md`.
