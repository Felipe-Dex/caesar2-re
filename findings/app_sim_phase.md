# Host — `city_sim_phase` (housing first)

Space/T no `python -m app` agora corre **um** slot de `city_sim_phase` `0x3F60C` e depois `walkers_tick` `0x459D0` — a mesma ordem de `view_frame`. **Não** despeja os `0xD6` slots de uma vez (isso seria ~um mês). Detalhe do EXE: `findings/ghidra_sim.md` §5.

## Como tentar

1. Preferir um save com `+15` vivo: `20230610.SAV` ou `FELIPE02.SAV`. Achea / FELIPE01 têm `+15` **zerado** (wipe da fase `0x52`).
2. Sem janela:

```text
C:\Users\Felip\AppData\Local\Programs\Python\Python314\python.exe -m app --sim-smoke --no-audio
```

   O smoke escolhe `20230610` se existir; senão FELIPE02 / LASTYEAR / FELIPE01 / Achea.

3. Com janela: `python -m app --sav "C:\Users\Felip\OneDrive\Games\Caesar2\20230610.SAV"`
4. Tecla **3** — mapa. **Space** / **T** — um pulso (1 slot + walkers). **E** — as 80 filas de evolve de uma vez (atalho do host, não é um pulso do EXE).
5. HUD: `slot 0x..` · `houses +N/-N merge=` · data · `moved=` dos walkers.

## Teclas (escolha)

| Tecla | O que faz | Porquê |
|---|---|---|
| **Space** / **T** | 1 slot `city_sim_phase` **depois** `walkers_tick` | Ordem original do pulso. Um frame com `sim_tick_due` = isto (sem o gate de ms). |
| **E** | `evolve_all_rows` (80 filas) | FELIPE01 nasce em fase `0x6C` (slot stub). Sem **E** precisas de muitos Space até voltar a `1…0x50`. |
| setas / +/- | câmara | Não misturam com o tick. |

Não há tecla “mês inteiro” (`0xD7` slots). Wrap `> 0xD6` só avança o **mês** (`calendar_advance`); `economy_recompute` fica stub.

## O que é real (Y)

- Slots **`1…0x50`**: `city_buildings_evolve_row` — só habitação `0x82–0xA1` com `+5 & 0xF == 0`. Banda `0x96235`. Up / down in-place; villa 2×2 e palace 3×3 (`housing_merge.md`). Decay de `+10` quando `[0x1026A4]==0`.
- Slots **`0x55`**, **`0xD4…0xD6`**: nop / empty.
- **Wrap**: mês++ (e ano no December). Sem tesouro / HISTORY / lastyear.sav.

## Stub (N) — não crasha

Água / fogo / emit / flood `+17` / paint `+12…+15` / overlay / `actors26_tick`. Wipes `0x51–0x54` **de propósito não correm** (destruiriam `+15` vivo sem o paint `0x76–0x8D`).

Outros edifícios no evolve-row (poços `0xD7+`, indústria, fórum…) são ignorados.

## Caveat Achea `+15`

`ACHEA23.SAV` e `FELIPE01.SAV`: todas as casas com **`+15 = 0`**. Isso **não** é no-op no EXE: `0 < ev_min` → **desce** de grau (Small house `0x89` vira `0x88`, etc.). O host faz o mesmo. Para ver **subida** / merge, usa `20230610.SAV` (fase 17, já na banda evolve) ou `FELIPE02.SAV`.

Selftest sintético (sem SAV): `0x89` com `+15=20` sobe; `+15=10` desce; `0x9B` com `+15=60` e 3 vazios em SE vira villa `0x9C`; `0x9F` com `+15=64` vira palace `0xA0`.

No `20230610.SAV`, `--sim-smoke` mudou IDs (`+1/-18` nesta máquina). Um Space na fase gravada `0x11` pode não acertar casa fora da banda nessa fila — usa **E** ou segura Space na banda `1…0x50`.
