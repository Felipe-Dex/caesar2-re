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
4. Tecla **3** (off-map) entra no mapa; no mapa **3** é furthest zoom. **T** — um pulso (1 slot + walkers). **Space** no mapa cancela a ferramenta (1.1A). **M** — fecha o ciclo + `calendar_advance`. **E** — as 80 filas de evolve de uma vez (atalho do host, não é um pulso do EXE). City Only **não pausado**: play / faster no chrome INT_CITY (sprites 7/8; **P** / pause = sprite 6 ou Speed → Pause) corre `sim_tick_due` `0x3E4B9` sozinho. **A** = Faster. **C** = Census.
5. HUD: `slot 0x..` · `houses +N/-N merge=` · data · `moved=` dos walkers. A data (chunks 25/26) muda quando o mês rola — play e espera January→February.

## Teclas (escolha)

| Tecla | O que faz | Porquê |
|---|---|---|
| **Space** / **T** | 1 slot `city_sim_phase` **depois** `walkers_tick` | Ordem original do pulso. Um frame com `sim_tick_due` = isto (sem o gate de ms). |
| **M** | slots que restam neste ciclo (evolve + paint + emit + flood) e um `calendar_advance` | Atalho do host. **Não** salta `0x51–0xD6`. |
| play / faster / pause | chrome INT_CITY + menu Speed | `sim_tick_due`: intervalo `(100-[0x9CE50])/10*50+50` ms (default scalar **70** → **200 ms**). Play = 1 pulso; Faster = 4 (`[0xC45A0]`). Um mês = 0xD7 slots (~215 dues em play). |
| **E** | `evolve_all_rows` (80 filas) | FELIPE01 nasce em fase `0x6C` (slot stub). Sem **E** precisas de muitos Space até voltar a `1…0x50`. |
| setas / +/- | câmara | Não misturam com o tick. |

**M** fecha o mês à mão. City Only começa **unpaused** (como o EXE). Wrap `> 0xD6` só avança o **mês** (`calendar_advance`); `economy_recompute` fica stub.

## O que é real (Y)

- Slots **`1…0x50`**: `city_buildings_evolve_row` — só habitação `0x82–0xA1` com `+5 & 0xF == 0`. Banda `0x96235`. Up / down in-place; villa 2×2 e palace 3×3 (`housing_merge.md`). Decay de `+10` quando `[0x1026A4]==0`.
- Slots **`0x51–0x54`**: wipe `+13` / `+15` / `+14` / `+12`.
- Slots **`0x56–0x5D` / `0x5E–0x65` / `0x66–0x6D` / `0x6E–0x75` / `0x76–0x7D` / `0x7E–0x8D`**: paint reservoir / security / amenities+education / water / land-value / housing cap (`app/city_paint.py`).
- Slots **`0x8E–0x9D`**: walker emit (fórum / torre / prefecture+barracks / mercado+**factory `0x41b33` +9 stock**). **`0xD2`**: relink `+7/+8`.
- Slots **`0x9E–0xA1`**: fire tick `0x41DD4` (City Only: sem immigrant/rioter). `--[+16]` se +3 bit7; house 0 → rubble `0x05`; uncovered house sobe +11 `0x10/0x20/0x30` e ignite `0x69A37`.
- Slots **`0xA2–0xC1`**: flood `+17` (rebuild no primeiro slot).
- Slots **`0x55`**, **`0xD4…0xD6`**: nop / empty.
- **Wrap**: mês++ (e ano no December). Sem tesouro / HISTORY / lastyear.sav.

## Log

`logs/city_sim.log` (gitignore). Uma linha por fase com trabalho: slot, nome, `houses +N/-N`, spawn, razão de stay (`no-water +13`, `lv-in-stay`, `no-road`, `merge-blocked`). Wrap: `houses={id:count}` + walker count. Corta ~1.5 MB. HUD espelha a última linha.

## City Only skip (fase incrementa, sem trabalho)

`0`, `0xC2–0xD1`, `0xD3` overlay (o host pinta live). `0x9E–0xA1` corre o fire tick (não o spawn immigrant/rioter). `0x66–0x6D` corre: `FUN_0004034b` +12 venues e +13 education (`0xF3` r=6 extra=1 bit `0x10`; `0xF4` r=8 extra=2 bit `0x20`). +12 também no place: Theater `0xE5` bits 0–1 extra=1 r=9/7/5; Odeum `0xE6` extra=1 r=11/9/7; Arena `0xE7` bits 2–3 extra=2 r=9/7/5; Coliseum `0xE8` extra=2 r=11/9/7; Circus `0xE9–0xEC` bits 4–5 extra=2 r=10/8/6; C.Maximus `0xED–0xF0` extra=3 r=12/10/8. Wipe +12 é `0x54`. Baths `0xDF–0xE2` +13 `0x08` r=`id−0xDA` extra=1 (needs reservoir ring) on place + `0x6E`. Prefecture/barracks +10 `0x30` r=2/3 on place + `0x5E`. Hospital `0xFB` / Library `0xF5` have **no** tile splash. Both need a 3×3 rim pad (`+1&0x20`) that also has forum (`+10&0x0C`) (`FUN_00044deb` ECX=0). Query cover is city-wide working count: 0 if n=0; 100 if pop<100; else hospital `n*1000*100/pop`, library `n*1200*100/pop` (`0x45398` / `0x453e5` + `0x28219`).

Outros edifícios no evolve-row (poços `0xD7+`, indústria, fórum…) são ignorados nessa fila — o emit/paint trata-os noutros slots.

## Caveat Achea `+15`

`ACHEA23.SAV` e `FELIPE01.SAV`: todas as casas com **`+15 = 0`**. Isso **não** é no-op no EXE: `0 < ev_min` → **desce** de grau (Small house `0x89` vira `0x88`, etc.). O host faz o mesmo. Para ver **subida** / merge, usa `20230610.SAV` (fase 17, já na banda evolve) ou `FELIPE02.SAV`.

Selftest sintético (sem SAV): `0x89` com `+15=20` sobe; `+15=10` desce; `0x9B` com `+15=60` e 3 vazios em SE vira villa `0x9C`; `0x9F` com `+15=64` vira palace `0xA0`.

No `20230610.SAV`, `--sim-smoke` mudou IDs (`+1/-18` nesta máquina). Um Space na fase gravada `0x11` pode não acertar casa fora da banda nessa fila — usa **E** ou segura Space na banda `1…0x50`.
