# City Only — walker tipo 3 **Enemy** (bárbaro)

C2.ENG `[66]+2` ` - Enemy`. Não é lobo de C3. Não é Career actor26 / `[90–95]`.

Pin Capstone: `tools/_pin_enemy.py` / `_pin_enemy2.py` / `_pin_enemy3.py` no `c2_x.bin`.

## Quando nascem

`economy_recompute` `0x3FCA0` (todo wrap de mês, `calendar_advance` `0x3FBCF`) chama `FUN_00052828` **só se** chunk **406 ≠ 0**. Career salta o ramo.

Tabela `0x96ECB` = C2MODEL `[75:91]` (skill × 4 dwords). Skill 4 não tem 5ª fila — o DAT tem 16 ints.

| Skill | Anos mín. `[0x102ac0]` | Janela RNG | Espera meses `[0x102a78]` | Contagem |
|---|---:|---:|---:|---:|
| Novice / Easy | 10 | 20 | 60 | 1 |
| **Normal** | **8** | **20** | **48** | **1** |
| Hard | 6 | 25 | 36 | 3 |

`[0x102ac0]` incrementa no wrap de **ano**. Host: `years_played = year_raw + 300` *antes* do `calendar_advance` desse pulso.

Depois do gate de anos: `++[0x102a78]`; se o limiar `≥` contador, sai. RNG `[0xc2070]` (0…127): precisa `20 ≤ rng < window+20` (Normal: 20…39). Falha **não** zera o contador. Sucesso zera e chama `walker_spawn_type3_count` `0x536E2`.

Contagem `AND` (`[0x117a60]` + rng&7). Normal=1 → 0 ou 1 walker.

## Onde / o que fazem

`0x537ed` (EAX = rng&7): **bordo do mapa** 80×80 — N / NE / E / SE / S / SW / W / NW, não um portal C3.

Spawn `walker_spawn` EAX=3, pad **0**. Estado **1**, `next_state=5`, wait `0x14`. Destino = rally `[0x10262C]`/`[0x102628]` = tile com **maior +15** (fim de `0x40695`). Marcha `walker_anim_path(1)` até o pico de land value (casas boas), não um id de portão.

Vida cap **72** (cada 64 ticks → state 2 / free). Latch tipo 3 `[0x102674]=2` — soldados / vigiles (estados 6–8) caçam com `walker_find_type3or7` r=10. Barracks `0xBF` emite tipo 4 se 3/7 em r=6.

Muros: `dest_ok` sem pad bloqueia (`+1` wall 0x02). O banner diz que os muros só atrasam; o EXE **não** derrete muro no tick do tipo 3. `0x68c01` no spawn só corre se o tile de bordo tiver flags (`+1 & 0xe7`); em relva é nop. Sem combate “lobo come casa”.

## Banner

Se `esi>0` (pelo menos um spawn): `FUN_00058c87` EAX=`0x53` EBX=`0x17` → C2.ENG **[82]** `The City Is Attacked!` (`warning.smk`). **Não** Stern Warning `[98]`, **não** cartas do Imperador, **não** `[90–95]` provinciais.

`[0x1025A8] -= 0x40` (clamp 0). City Only Peace no host fica 0.

## Host

`app/walker_tick.py` `city_only_try_invasion` no wrap de `city_sim_phase`. `app/messages.py` enfileira `[82]`. Query title já é Enemy (`walker_quotes.py`).
