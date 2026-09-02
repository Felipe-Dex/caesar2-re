# Achea — walkers no Excel

Snapshot de **ACHEA23.SAV** (SavChunk 8, 201 × 58). Não copia o save.

| | |
|---|---|
| Planilha | `findings/Achea_walkers.xlsx` |
| Regenerar | `tools/_achea_walkers_xlsx.py` |
| Grade da cidade (prédios) | `findings/Achea_grid_v3.xlsx` — **não** foi mexida |
| Save | `C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV` |
| Província (não estes) | `findings/achea_province_walkers.md` — chunk 7, 4 actors |

## Como abrir

1. Abre `findings/Achea_walkers.xlsx`.
2. Folha **query** — os 5 tiles ★ para clicar primeiro.
3. Folha **mapa** — mesma grade 80×80 do `Achea_grid_v3`. Célula colorida = pessoa (`t1` … `t6`). `★tN` = Query este.
4. Folha **legenda** — lista completa (slot, tipo, x, y, estado, prédio perto). Se dois estão no mesmo tile, o mapa empilha `t1+t5`; a legenda lista os dois.

Walkers **andam**. Carrega **ACHEA23**, **pause**, Query já. Se a pessoa não estiver no tile, olha a rua/plaza do lado (1–2 casas).

## Convenção de coordenada

**Igual ao mapa da cidade.** Linha 1 = **x**. Coluna A = **y**. Célula Excel = tile `(x, y)` do jogo.

`(0,0)` = ponta **norte** do losango (primeiro tile clicável). Não é o canto superior-esquerdo da tela 2D.

Se você costuma anotar `(y, x)`, inverta: aqui e no Query é **`(x, y)`**. Exemplo: Colosseum = `(71, 13)`, não `(13, 71)`.

## O que mandar de volta

**1 / 2 / 4 / 5 / 6 já têm nome + frase completa** (abaixo). Tipos **3** e **7**: títulos e falas estão em `findings/walker_quotes.md` (C2.ENG); falta só um Query ao vivo.

| ★ | tipo | (x, y) | Excel | perto |
|---|---:|---|---|---|
| 1 | 1 | (70, 12) | BT14 | Plaza, entre Basilica e Colosseum |
| 2 | 2 | (70, 20) | BT22 | Plaza est, Palatine / Basilica |
| 3 | 4 | (70, 8) | BT10 | Plaza est, Temple / Janiculan 2 |
| 4 | 5 | (70, 24) | BT26 | Plaza est, face norte do C.Maximus |
| 5 | 6 | (53, 37) | BC39 | Plaza 1, Colosseum oeste |

## Achea Q&A — tipo → nome do Query

Primeiros walkers da plaza: o usuário foi um pouco à **esquerda** das células ★ (mais fácil de ver). Mesmos tipos — a Plaza 1 em x≈44–52, y≈7–9 também tem t1 / t2 / t4 / t5 / t6.

Fonte: print da folha **legenda** + `C2.ENG` (`findings/walker_quotes.md`). Títulos oficiais do Query = coluna `nome`. Nomes latinos = `rec[+0x32]` na tabela [64]. Texto **do ficheiro** (aspas fazem parte da string; o print tinha `costumers` / `disctrict` — no ENG é `customers` / `district`).

| tipo | Query (oficial) | casa no print | Excel | (x, y) | slot | pessoa | frase completa |
|---:|---|---|---|---|---:|---|---|
| **1** | **Forum Clerk** | Forum | AW9 | (47, 7) | 34 | Maelius Piscator | `"We have excellent records for this district."` |
| **2** | **Market Trader** | Market 3 | AV9 | (46, 7) | 67 | Ennius Lentulus | `"We have enough customers from this district, but we need better access to a business."` |
| **4** | **Soldier** | Barracks | AT10 | (44, 8) | 20 | Caelius Clodius | `"We have good patrols in this district. We feel we have the area secure."` |
| **5** | **Vigile** | Praefecture | BB11 | (52, 9) | 15 | Aemilius Calvus | `"This is a very law-abiding and peaceful district."` |
| **6** | **Worker** | Winery | BB9 | (52, 7) | 90 | Gaius Pernix | `"We could do with more people in this district to help build up our industry."` |
| **6** | **Worker** | Winery | BB11 | (52, 9) | 68 | Iunius Maior | `"We could do with more people in this district to help build up our industry."` |

Bate com Ghidra: 1 fórum (`0xAE–0xB9`, C2.ENG [66] ` - Forum Clerk`), 2 market (`0xFC–0xFF`), 4 barracks (`0xE4`), 5 prefect (`0xE3`; Query diz **Vigile**, não Prefect), 6 factory (`0xFA` / Winery). Tipo 1/4/5 nesta save **não** têm `home_off` — a coluna casa do print é anotação do Query.

### Perto — ids sem nome no KNOWN

A coluna `perto` escreve `id0xNN` quando o tile vizinho não está em `KNOWN` (`tools/_achea_grid_xlsx.py`). Q&A 2026-09-01:

| o que aparecia | tipo perto | usuário | já documentado |
|---|---|---|---|
| **`id0xEA`** | — | **Circus** | peça do par `0xE9`+`0xEA` (`achea.md` §11). `0xE9` irmão, não nomeado neste Q&A. Não retrata `0xEB`+`0xEC`. |
| **`id0xA3`** | **5 Vigile** | **Shrine 2nd** | mesmo id que §11 Shrine 2. 1º/3º/4º (`0xA2`/`0xA4`/`0xA5`) não saíram deste Q&A. |

### Ainda falta

- **Tipo 3** (Query **Enemy**) e **7** (**Rioter**) — zero em ACHEA23; precisa save com invasão / motim para ver o título ao vivo. As falas já estão no ENG: 3 = só `AAARGH -- The only good Roman is a DEAD Roman!`; 7 = taxa `> 10` vs `Boo!  Down with the Governor!`.
- Frases 1/2/4/5/6: **feitas** (`walker_quotes.md`). Porquê estas cinco na Plaza 1: clerk cobertura fórum ≥90%; market `score_a=12` / `score_b=0` (falta fábrica); soldier/vigile cobertura boa / unrest baixo; worker `score_a=6` (falta gente; `score_b=100` já tem mercado).
