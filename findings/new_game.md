# New Game — City Only vs Career (não é load de SAV)

O utilizador perguntou *“e para criar um novo jogo?”* a seguir ao plano de `app_structure.md`. Correcção: o original **não** tem um só “New Game / assignment”. Tem **dois modos** no ecrã de opções:

- **City Only** — o jogador chama assim; o ficheiro escreve **City-only Mode**
- **Career** — o jogador chama assim; o menu escreve **Campaign?** / **YES -- City, Province, Empire**; o Forum PERSONAL escreve **The career of**

Isto **não** é desenhar um IP original: é o que o EXE faz depois de **Start a New Game** vs `sav_read` de um `.SAV` — e onde isso cabe no host. **Duas entradas**, não uma.

**City Only marco 1 está no host** (`python -m app --new --city-only`). Career / REGIONS / actors26 **não**. Fatias seguintes: `city_only.md`. GhidraMCP HTTP `127.0.0.1:8080` recusou na passa do generate — Capstone em `c2_x.bin`. Factos deste doc = `C2.ENG` / `HELP.ENG` + Capstone + chunk **16** dos `.SAV` locais. Walks: `ghidra_walk.md`, `ghidra_city.md`, `c2model.md`, `history_dat.md`, `forum.md` / `forum_qa.md` / `forum_strings.md`, `province_map.md`, `sav_date.md`.

Irmão curto no mapa de camadas: `app_structure.md` §6.

---

## 0. Nomes (não misturar)

| Quem fala | City Only | Career |
|---|---|---|
| Utilizador | City Only | Career (antes escrito “carrer”) |
| Menu **New Game Options** (`C2.ENG` **[38]** / **[42]**) | `NO -- City-only Mode` · `CITY-ONLY MODE ` | `Campaign?` · `YES -- City, Province, Empire` |
| **Choose a Skill Level** (mesmo ecrã; **não** é *Very Hard*) | `Novice` … `Impossible!` → chunk **16** `0x9CE80` = **0…4** | igual — a dificuldade **não** escolhe o modo |
| Forum PERSONAL | — | `The career of ` (`[30]+0`) + cargo **[7]** |
| Oracle / avisos | `You cannot get promoted when playing in city-only mode…` (`[31]+24`) · `Not part of city-only mode.` (`[10]+4`) · `You do not have a province to manage.` (`[10]+5`) · `This feature is used in the full campaign game.` (`[38]+1` / `[37]+42`) | `Promotion!!!` (`[69]`) · pick `Select a Highlighted Province` (`[47]+0`) |
| `HELP.ENG` | *simplified version… only have to worry about what the City needs* · tutorial = *CITY-ONLY game* · *city-building-only game* (só Prosperity / Culture) · *City Building Only* (Empire *does not apply*) | *full game* / *full campaign game* (cidade + Province Level + batalhas opcionais; 4 ratings → promoção) |
| Jargão RE deste repo | — | **assignment** = `start_city_assignment` `0x1049B` (síntese da cidade). **Não** é um terceiro modo. |

Não há string de menu **Career** nem **City-Building** no `C2.ENG` (146 slots + packs). `README.TXT` / `README.md` do jogo e do repo **não** nomeiam os modos. `City-Building` só aparece no `HELP.ENG`.

O chrome `0x5AFC6` (Capstone) é dirty-rect, **não** o store. Quem grava os bytes: INF/default `0x70595` / `0x7062C` (16 + 406) e as setas de Options `0x348CF` / `0x348EA` / `0x34909`. City-only = **`[0x9CE81]`** (SavChunk **406**, também `skip_actors_flag`). Skill = **`[0x9CE80]`** (SavChunk **16**).

---

## 1. O que o original faz

Não é “ficheiro vazio + título”. Depois do boot, `c2_main` `0x10010` já passou `title_screen` `0x5D37F` (`backgrnd.256` + `backgrnd.pl8`) e saltou para o chrome do menu `0x5AFC6`. `title_input_wait` `0x2E7B1` gira até `[0xC459C]==1`.

### 1.0 Como o jogador escolhe o modo **e** a dificuldade (labels)

Pack do título / **New Game Options** — o mesmo texto vive em **[38]** e de novo em **[42]** (offsets oficiais; skip abaixo a partir de `[38]`). O índice de 146 slots só mostra `[38]` = `CITY-ONLY MODE ` e `[43]` = `Novice`; **Easy / Normal / Hard / Impossible!** são extras NUL do pack, não slots próprios. **`Very Hard`**: **0** hits em `C2.ENG` / `HELP.ENG` / `PS.EXE`. A palavra `Difficulty` **não** é rótulo de menu — só entra no blurb de Normal.

| Skip | Texto | Onde |
|---:|---|---|
| +8 | `Caesar II - Game Options` | **outro** diálogo (Options **in-game**; também muda o byte 16) |
| +9 | `Choose a Skill Level` | cabeçalho das 5 dificuldades |
| +10 | `A basic introduction to Caesar II` | blurb **0 Novice** |
| +11 | `A simpler challenge` | blurb **1 Easy** |
| +12 | `Our suggested level of difficulty` | blurb **2 Normal** |
| +13 | `More challenging for the experienced designer` | blurb **3 Hard** |
| +14 | `A suicide-pact with city deterioration!` | blurb **4 Impossible!** |
| +15 | `Campaign?` | New Game Options |
| +16 | `YES -- City, Province, Empire` | New Game Options |
| +17 | `NO -- City-only Mode` | New Game Options |
| +18 | `Your Name` | pack do título (entre Campaign e o menu); **não** afirmar que é um terceiro controlo do diálogo New Game sem o draw |
| +19 | `Run the CAESAR II Tutorial` | título |
| +20 | `Load a Previously Saved Game` | título |
| +21 | `Start a New Game` | título |
| +22 | `Click right or ENTER to accept` | chrome de aceitar |
| +23 | `Exit the Game` | título |
| +24 | `New Game Options` | **título deste diálogo** |
| +25 | `Start this Game` | confirma o diálogo |
| +26 | `Novice` | skill **0** — também `[43]+0` |
| +27 | `Easy` | skill **1** |
| +28 | `Normal` | skill **2** |
| +29 | `Hard` | skill **3** |
| +30 | `Impossible!` | skill **4** (ponto de exclamação no ENG) |

No ecrã **New Game Options** (só o que o pack nomeia a seguir a esse título): **Campaign?** YES/NO + **Choose a Skill Level** (`Novice`…`Impossible!` + os 5 blurbs) + **Start this Game**. Não inventar um terceiro eixo.

Draw do picker de skill (`0x5CF80`, Capstone): `FUN_00026f16` `EAX=0x2B` (`[42]`) `EDX=1` → `Choose a Skill Level`; `EAX=0x2C` (`[43]`) `EDX=[0x9CE80]` → o nome; `EAX=0x2B` `EDX=difficulty+2` → o blurb. O mesmo widget serve **Game Options** in-game. Setas: `0x348CF` incrementa se &lt; 4; `0x348EA` decrementa se &gt; 0. `0x34909` faz XOR de `[0x9CE81]` (liga/desliga Campaign no Options). Default INF `0x70595`: byte 16 = **0**, byte 406 = **1** (Novice + City Only); `0x7062C` escreve os dois a partir do perfil.

Menu **File** in-game (`[0]+0…4`): `File` · `New Game` · `Load` · `Save` · `Quit`. Confirmação: `[9]+1` `Start a New Game?`.

O ramo **novo vs load** no loop de `c2_main` (`ghidra_walk.md`) **não** distingue os dois modos — só “sintetizar vs BSS já cheia”:

```
se  [0x102AA4] view_submode == 3  →  FUN_00010529     # passo de carreira / ano (Career)
senão se [0xCCAFF0] == 0          →  start_city_assignment 0x1049B
# senão: cidade já está na BSS (load)
se ainda [0xCCAFF0] == 0          →  map_clear_80x80 0x3E590   # scratch 0xD7BFC, NÃO o chunk 13
enter_view_mode 0x3351B           # kind 0 cidade
loop view_frame …
```

`[0xCCAFF0]` / `[0xCCAFF1]` são o gate. **0 + 0** = correr a síntese. Qualquer outro valor = **não** chamar `init_new_city` (o load já encheu os 500 chunks). Isto é **new vs load**, não City Only vs Career.

### 1.1 Load (o que o host já faz)

`sav_read` `0x7024A` (EAX=path): lê os **500** `SavChunk` para a BSS, depois os **4000** B do trailer → `[0xC4D10]` e **reescreve** `history.dat`. Diálogo de ficheiro: `file_dialog_sav` `0x6FACC` (`*.sav`). O EXE também conhece `caesar2.sav` / `lastyear.sav`.

O host: `boot.run_boot` → `city_map.pick_save` → chunks 13 / 8 / sim. **Só este caminho existe hoje.** O modo vem no SAV (chunk **406**), não se escolhe no boot.

### 1.2 Duas inits (não uma)

Não há um “New Game.DAT”. Há **uma** função de síntese da cidade (`start_city_assignment` → `init_new_city`), **dois modos** e **cinco** dificuldades. 2 × 5 = **dez** combinações de flags; as dez ainda chamam o **mesmo** `city_map_generate` (relva+rio). A dificuldade **não** ramifica o terreno. Tratar New Game como um único `--region 15` é o erro que este doc corrige.

| Entrada | Menu | Flag observada | O que o jogador vê a seguir |
|---|---|---|---|
| **City Only** | `Campaign?` → `NO -- City-only Mode` → `Start this Game` | chunk **406** / `[0x9CE81]` = **1** nos SAV A/B/C/D/LASTYEAR | cidade gerada; **sem** pick de província (pid chunk **223** = **0**; `[10]+5` *You do not have a province to manage.*) |
| **Career (nova)** | `Campaign?` → `YES -- City, Province, Empire` | chunk **406** = **0** | mapa do império: **Select a Highlighted Province** (`[47]+0…4`); pid → chunk **223**; rank **Citizen (0)** |
| **Career (promoção)** | `view_submode==3` → `FUN_00010529` | continua **406** = 0 | o mesmo pick; depois `init_new_city` de novo |

`FUN_00010529` (`sav_date.md`): se o mês ≠ 0, zera o mês e `city_year += 1`, **depois** `init_new_city`. Não é um segundo gerador de terreno. **Só Career** — City Only não promove (`[31]+24`).

O pick **é** o mapa do império (forum kind **6** / chrome EMPIRE MAP), não um ecrã à parte. 44 hits (`ecx = 0…0x2B`). Clique: `[0x102DE0] = ecx+1` (skip em `[5]`). **pid** = skip−1 = chunk **223** `[0x1025CC]`. Achaea = **15** → `[5]+16`. Latium skip **1** é casa do Imperador (`[47]+5`), não um assignment jogável da mesma forma.

Carreira (FAQ + C2.ENG **[7]**): Citizen … Consul (0…9) depois Caesar. Print PERSONAL Achea: *You need **8** promotions to become Emperor* = `10 − 2` (chunk **291** = **2** Apparitor), não um dword mágico 8. Pack `[76]+17…20`: `You need` / `promotions to` / `become Emperor.` / `win the game.` — a frase *win the game* existe; **não** vimos o ramo EXE que a escolhe (Ghidra em baixo).

Nome do jogador **não** vai no `.SAV` — mora em `CAESAR2.INF` (`load_caesar2_inf` `0x703E0`). O Forum lê o buffer / INF.

### 1.3 O que City Only salta (só o que está pinado)

Não inventar um “modo sem Forum”. O Forum **existe**; várias linhas são substituídas ou recusadas.

| Peça | Evidência | City Only | Career |
|---|---|---|---|
| `actors26_tick` (mapa provincial vivo) | `[0x9CE81]` skip (`ghidra_city.md`, `ghidra_walkers.md`) | **não corre** | corre |
| Conselho Oracle Empire / Peace | `forum_strings.md`: se city-only e id &lt; 9 → skip **24** | *cannot get promoted…* | conselhos 1…6 |
| Ratings que contam | `HELP.ENG` city-building-only | **só** Prosperity + Culture | quatro (Empire / Peace / Prosperity / Culture) → promoção |
| Província para gerir | chunk **223** = 0 nos SAV 406=1; `[10]+5` | **não** (pid 0) | pid 1…43 (Achea = 15) |
| Pick / campanha `REGIONS` | `[47]` + `apply_regions_map` no Career novo / promoção | **não observado** (pid 0) | 44 records, pick destacado |
| Promoções / `FUN_00010529` | `[31]+24` + submode 3 | **não** | 8 (a partir de Apparitor) até Caesar; `promote.smk` kind 5 |
| Tribute / ROME / EMPIRE MAP | strings `[37]+41/42` `CITY-ONLY MODE` / *full campaign game*; `[38]+1` | **gated** (o EXE mostra o aviso; o store de cada botão **não** foi relido) | painel ROME + mapa + tribute (`forum.md`) |
| Tutorial | `HELP.ENG` | *This tutorial uses the basic, CITY-ONLY game.* | — |

`init_new_city` **ainda** chama `apply_regions_map` na listagem (`ghidra_city.md`). Se City Only passa por essa linha com pid 0, ou se o menu nem chega a `start_city_assignment` com o mesmo path — **desconhecido** até Ghidra em `0x5AFC6` / `0x1049B`.

### 1.4 O que Career faz a mais

- Três camadas no rótulo do menu: **City, Province, Empire**.
- Rank chunk **291** + tabela **[7]**; C2MODEL `[790:990]` = limiares por dificuldade × slot (`forum_qa.md`).
- Campanha: cada promoção escolhe fronteira; Pompous Maximus conquista o resto (`HELP.ENG` + `[47]+6`).
- `REGIONS.DAT` 44×3600 → chunk **14** da província actual.
- Tribute anual, favor, pedido do Imperador (ROME). Savings acompanham a promoção (`HELP.ENG` Personal Advisor).
- Segundo sítio de init: `FUN_00010529` (não é New Game do título).

### 1.5 `start_city_assignment` `0x1049B` → `init_new_city` `0x10565`

Só corre se `[0xCCAFF0]==0` && `[0xCCAFF1]==0`. O wrapper grava:

- `[0x102AA0]` = `[0x102AB4]` = **−300** (chunk 25 ano + chunk 325 seed)
- mês **0** (January), gate mensal **0**
- `[0x102590] = 0` → o desconto de tesouro abaixo dá zero

Isto é **comum** aos dois modos nos SAV frescos (ano −300). Não prova o modo.

Ordem **dentro** de `init_new_city` (`ghidra_city.md`):

1. `city_view_reset` `0x106BB` — `view_kind` **0**, métricas 80×80
2. `history_dat_reset` `0x70A74` — recria `history.dat`: **200 × 20 B a zero**
3. `walkers_clear_pool` `0x2B16A` — slots 1…200
4. `actors26_clear_pool` `0x2B190` — slots 1…25
5. tesouro + ratings a partir do prefixo C2MODEL no EXE
6. taxas `[0x102A7C]=[0x102AA8]=5` (chunks 29 / 30)
7. `city_ratings_seed` `0x58BAE` — chunk 341 = `C2MODEL[difficulty]`
8. câmara / `FUN_000346CE` (gate de carreira; pode fechar a sessão)
9. `city_map_zero_lanes` `0x6E140`
10. **`apply_regions_map` `0x706C3`** — `regions.dat` record → chunk 14
11. `prov_map_fixup_flags` `0x6AD31`
12. **`city_map_generate` `0x65809`** — terreno **aleatório** 80×80 + rio
13. clima / pop a zero / `province_goods_setup` / `economy_counters_reset` / `economy_recompute`

Depois `c2_main` chama `enter_view_mode` (kind 0) e o `view_frame`. **Não** escreve um `.SAV` neste ponto.

### 1.6 Como nasce o primeiro `.SAV`

`init_new_city` **não** chama `sav_write`.

`sav_write` `0x70174` (EAX=path): abre o destino, escreve os 500 chunks da BSS, lê 4000 B de `history.dat` (`[0xC4D10]`, **o mesmo** ponteiro que o load de `REGIONS.DAT` — buffer reutilizado) e anexa. Tamanho fixo **225745**.

Quem dispara o write:

- diálogo File → Save (`file_dialog_sav`)
- `sav_year_end` `0x34D92` → `lastyear.sav` se as flags deixarem

### 1.7 Os SAV desta pasta (modo pelo chunk 406)

Parser: chunks **25** (ano), **291** (rank), **326** (anos no assignment), **406** (`[0x9CE81]`), **16** (dificuldade), **223** (pid), **28** (tesouro), **338** (HISTORY count).

| Save | 406 | 16 diff | 223 pid | 291 rank | 25 ano | 28 tesouro | Veredicto |
|---|---:|---:|---:|---:|---:|---:|---|
| **ACHEA23** (`Achea.sav/`) | **0** | **2 Normal** | **15** Achaea | **2** Apparitor | −187 | 28561 | **Career a meio**, Normal. Need Oracle **30/40** = C2MODEL slot 2 × Normal |
| 20230610 | 0 | **2** | 4 | 0 Citizen | −269 | 13966 | Career Normal (1º assignment ainda Citizen) |
| FELIPE01 | 0 | **2** | 12 | 0 | −258 | 18232 | Career Normal |
| FELIPE02 | 0 | **2** | 14 | 1 Decurion | −228 | 20187 | Career Normal |
| **D.SAV** (`findings/`) | **1** | **2 Normal** | **0** | 0 | **−300** | **10899** | **City Only Normal**, ano seed. **Não** Easy (16≠1). Start C2MODEL = **12000**; já gastou (Well / Theater / fábricas, `sav_d.md`) |
| A / B / C | 1 | **0 Novice** | 0 | 0 | −300 | 19990 / 19939 / 19984 | City Only Novice (cirurgia). Start **20000** − construções |
| LASTYEAR | 1 | **0 Novice** | 0 | 0 | −296 | 10985 | City Only Novice com 4 anos jogados |

**Achea vs D.SAV:** os dois são **16=2 Normal**. O que os distingue é o **modo** (406/pid/rank), não a skill. D.SAV **não** é Easy.

**Achea.sav** é pasta; o ficheiro é `ACHEA23.SAV`. Career a meio está fechado (Apparitor, pid 15, 406=0, print PERSONAL / Oracle Empire).

**D.SAV 300 BC** não é “Career a 0”. Ano −300 é o seed de `start_city_assignment` **nos dois** modos. O que decide é **406=1** + **pid=0**. Career novo teria 406=0 e um pid escolhido no mapa (e HISTORY 0 até ao primeiro wrap — isso **também** é verdade em City Only).

### 1.8 O que o chunk **16** muda (e o que **não**)

Byte `[0x9CE80]`, 0…4. `init_new_city` **lê**-o; **não** o escreve (já veio do diálogo / INF / Options). `city_map_generate` `0x65809` **não** indexa este byte — 2 modos × 5 skills = **cinco** (dez) inits, **um** gerador de terreno.

| Peça | Evidência | Efeito |
|---|---|---|
| **Tesouro** inicial | `0x105ED`: `[0x102AAC] = [0x96F2F + 16×4] − [0x96F43 + 16×4] × [0x102590]` | C2MODEL `[5:10]` = 20000 / 15000 / **12000** / 7000 / 5000. Jogo novo: desconto 0. Achea 28561 ≠ start (111 anos). D.SAV 10899 ≈ 12000 − spend |
| **Need** Oracle (Career) | C2MODEL `[790:990]` = 5 × 20 slots. Achea rank **2** + diff **2**: individual `[832]=30`, average `[932]=40` | **Need 30 / 40** confirmado. Hard slot 2 é *também* 30/40; Novice/Easy slot 2 = 25/35; Impossible = 35/45. Não é um 30 mágico |
| Promoções até Caesar | EXE `0x9621C` bytes `05 07 0A 0F 14` = **5, 7, 10, 15, 20** (FAQ; **ausente** do DAT). Draw PERSONAL `0x5E01C`: `table[16] − [0x102590]` | Achea: 10 − 2 = **8**. `[0x102590]` incrementa com a promoção (init = 0; Achea = rank 2) |
| Seed ratings chunk **341** | `city_ratings_seed` `0x58BAE`: `[0x102A58] = C2MODEL[16]` | 20 / 15 / 10 / 5 / 2. **Não** é o Need 30/40 |
| Invasão **província** (Career) | `FUN_00052eb9` `0x52EB9`: `ecx = 16<<4`; lê `0x96DDB` / `+0x50` / `+0xA0` | = C2MODEL `[15:35]` / `[35:55]` / `[55:75]` (5×4). Ano / janela RNG / limiar. Mix de tropas **não** é esta tabela (isso é `0x95763`, por origem) |
| Inimigo **cidade** (City Only) | `0x52828`: só se **406 ≠ 0**; tabela `0x96ECB` = C2MODEL `[75:91]`; `walker_spawn_type3_count` | Normal = `(8, 20, 48, 1)`. Career **salta** este ramo |
| RNG / eventos | `0x5676B` (`eax += 16` vs `[0xC2070]`); `0x56F9F` (`(rng&7)−3−16`) | leem o byte; **função não nomeada** nesta passa — não chamar “immigrant rate” |
| `[0x1025E8]` | `0x10584`: dword `[0x96221 + 16×4]` | tabela pequena **0, 0, 2, 1, 1**. **Não** é C2MODEL[0]. Uso depois: opaco |

**Imigrante:** `FUN_00041dd4` `0x41DD4` **não** aparece nos 31 hits LE de `0x9CE80`. O score é nibble de casa (`ghidra_tile.md`). **Não** há taxa de imigração por dificuldade neste 1.1A (pelo menos não lendo o chunk 16).

HELP.ENG *não* lista as cinco skills. Diz só: *harder difficulty levels* (poupança entre províncias) e *harder provinces or skill levels* (jardins/plazas para tendas não sumirem). Sem tabela de spawn.

---

## 2. O que copiar vs o que sintetizar

A cidade **80×80 não vem** de `REGIONS.DAT`. A província **60×60 sim** — e **só importa no Career**.

### Copiar

| Fonte | O quê | Destino no estado |
|---|---|---|
| **`REGIONS.DAT`** 158400 B = **44 × 3600** | record `index = pid` (0…43), `ecx = 3600 * index` | `apply_regions_map` → `prov_tile_stamp` `0x6A7CE` → chunk **14** (60×60×8 @ `0xD94FC`). **Entrada Career.** |
| **C2MODEL** ints **0–14** (também em `0x96F1B` no EXE; o DAT de 1090 ints **não** é `fopen`) | `[0:5]` scalars 20/15/10/5/2; `[5:10]` tesouro inicial; `[10:15]` desconto × `[0x102590]` | chunk **341** ratings; chunk **28** tesouro. **Ambos os modos.** Indexados pelo chunk **16**. |
| `C2.ENG` **[5]** / **[7]** / **[38]** / **[42]** / **[43]** / **[47]** | nomes de província, cargos, **New Game Options**, **Novice…Impossible!**, chrome do pick | só strings |
| `CAESAR2.INF` | nome do jogador | **não** é SavChunk |

Tesouro num jogo novo (`[0x102590]==0` → desconto 0):

| Dificuldade (chunk 16) | C2MODEL `[5:10]` |
|---|---:|
| 0 Novice | 20000 |
| 1 Easy | 15000 |
| 2 Normal | 12000 |
| 3 Hard | 7000 |
| 4 Impossible | 5000 |

`C2MODEL.DAT` **não** tem o filename no EXE. O prefixo de 15 ints chega. Rank tables `[790:990]` (20 slots × 5 diffs) ficam no disco / embed tardio — o host **não** precisa delas para *entrar* no mapa; Career precisa delas para o Oracle “Need”.

### Sintetizar (não ler de SAV)

| Peça | Como o EXE faz | **Não** é |
|---|---|---|
| Cidade 80×80×20 | `city_map_generate`: 17× `clear_byte8` (lanes 1–17) + `fill_rand_terrain` (`byte0 = (rng&0xF)+8`) + `trace_feature` (rio: dirs 0/2/4/6, **OR `0x10` em +1**) | zeros; cópia de REGIONS; cenário pré-construído |
| Walkers chunk 8 | pool vazia | pessoas do Achea.sav |
| Actors26 chunk 7 | pool vazia (spawn vem **depois**, do mapa provincial) | 0 *obrigatório* no tick; City Only **nem ticka** actors26 |
| Calendário | ano **−300**, mês **0**, seed chunk 325 = −300 | ano do assignment anterior (salvo `FUN_00010529` no wrap) |
| Tesouro | tabela acima (indexada pelo **16**) | 28561 do Achea; 10899 do D.SAV |
| Dificuldade chunk **16** | 0…4 do diálogo / INF | adivinhar “Easy” pelo tesouro |
| HISTORY trailer | 4000 B **a zero** (200 records). D.SAV confirma | copiar o `HISTORY.DAT` da campanha antiga |
| `view_kind` | 0 | 1/2 |
| Flag **406** | **1** City Only · **0** Career | adivinhar pelo ano −300 |
| Rank chunk 291 | Career novo → **Citizen (0)**; Achea a meio → **Apparitor (2)**; City Only observado **0** | inventar “8” |
| Bens / economia | `province_goods_setup` `0x577E4` + `economy_counters_reset` | copiar chunk 335/339 de outro SAV |

Cidade “vazia” no sentido de **sem casas / sem placement**. Terreno **não** é ecrã preto: relva aleatória + rio. `CityMap()` do host sem SAV (80×80 zeros) é **mais vazio** que o original.

---

## 3. Porque o `app/` ainda não faz New Game

`python -m app` só sabe **abrir um `.SAV`**.

| Em falta | Onde dói |
|---|---|
| Sem as **duas** entradas (+ skill 0…4) | um `--new` único finge que Career = City Only e esquece o tesouro |
| Sem `start_city_assignment` / `init_new_city` | `boot.py` passo 7 = `pick_save` ou zeros |
| Sem gravar chunk **406** | o host não sabe que ratings / actors26 / pick aplicar |
| Sem gravar chunk **16** | tesouro / Need / spawn usam o default INF (Novice) ou lixo |
| Sem `apply_regions_map` | chunk 14 **não existe** no host; REGIONS.DAT nunca é lido (**Career**) |
| Sem `city_map_generate` | sem SAV = relva 0, não o terreno do EXE |
| Sem pick de província | sem forum kind 6, sem `--region 15` (**só Career**) |
| Sem **placement** | Space/T só faz tick do que já está no mapa; relva não evolui para cidade |
| Sem `sav_write` | o host não grava o primeiro SAV (e não precisa, para *ver*) |
| Sem `view_kind` / `enter_view_mode` | já “nasce na cidade” se houver SAV (`app_structure.md`) |

O README já diz: *“No live sim and no menu that starts a city.”*

---

## 4. Onde senta nas camadas e na ordem

Fluxo alvo — **dois** entry points (nomes = EXE + labels `C2.ENG`):

```
boot.run_boot
  → title (já temos a arte)
  → New Game Options          # [38]/[42] Campaign? YES/NO + Choose a Skill Level
        [0x9CE80] = 0…4          # Novice…Impossible!  (comum aos dois ramos)
        ├─ NO  City-only Mode
        │    [0x9CE81] = 1
        │    start_city_assignment / init_new_city
        │    sem pick; pid 0
        └─ YES City, Province, Empire
             [0x9CE81] = 0
             pick pid               # CLI --region 15 agora; forum kind 6 depois
             start_city_assignment / init_new_city
             apply_regions_map      # REGIONS.DAT → chunk 14
        # as 2×5 combinações partilham city_map_generate
  → enter_view_mode kind 0
  → view_frame (Space = pulso, como hoje)
```

O `=` nos flags 406/16 é o **contrato do host**. Store lido: INF `0x7062C` + Options `0x348CF`. Quando o MCP voltar: **G `1049B`**, **G `5CF80`**, xref `[0x9CE80]`.

Na pilha de `app_structure.md` §3: **depois** de `sav/chunks` (precisas da tabela de 500 para saber o que encher), **ao lado** de `world state`, **antes** de `sim` e **muito antes** de `forum.py`. Não é um `GameManager`. Um módulo com `start_city_assignment` / `apply_regions_map` / `city_map_generate` chega — **com um bool de modo**, não um só caminho Achaea.

### Ordem de extração (encaixe)

Depois de `sav.py`, **antes** do forum. O pick visual do império **espera** `forum.py`. Até lá: índice. **City Only pode ser o primeiro marco** (não precisa de REGIONS nem do pick).

1. `city_iso.py` (já no plano)
2. **`sav.py`** — sem isto não há sítios nomeados para sintetizar
3. **duas inits** ← **este doc**
   - `--new --city-only` — 406=1, pid 0, ano −300, tesouro C2MODEL**[16]**, cidade gerada, walkers 0. Teste Novice: igual A.SAV fresco (sem as casas da cirurgia, tesouro ~20000). Teste Normal: start 12000, como o D.SAV *antes* de gastar.
   - `--new --career --region 15` — 406=0, chunk 14 com Your City `0x92` / hills; cidade 80×80 com ids `< 0x78` e um rio (`+1 & 0x10`); walkers 0; tesouro = **12000** se diff=**2**; rank 0. **Ainda sem placement.** Dificuldade é o 3.º flag, não um 3.º gerador.
4. `actors26` tick (já no plano) — **só o ramo Career**; City Only continua a skip
5. `view_kind` mínimo
6. `province.py` draw — chunk 14 **já** pode vir de REGIONS, não só de SAV
7. `forum.py` — chrome do pick + PERSONAL (Apparitor / 8 promoções) + aviso city-only

Placement / menu File Save = **depois**. Não misturar com este passo.

---

## 5. Honestidade

- New Game **sem** sim de placement = mapa gerado (relva + rio). Space não “joga”. City Only neste marco = **viewer de cidade fresca**. Career neste marco = isso **mais** a província de `REGIONS.DAT`.
- New Game Career **com** terreno de `REGIONS.DAT` (Achaea 60×60, Your City `0x92` @ 32,24 no Achea jogado — a posição vem do record 15, não do SAV) é o primeiro marco *“comecei a Acaia do zero”*. Isso **não** precisa de Forum, nem de `sav_write`, nem de Godot.
- New Game **jogável** (estrada, casa, imigrante) espera placement + spawn. Fora desta fatia.
- `CityMap()` a zeros **não** é New Game. É um bug de fallback.
- Copiar Achea.sav e apagar casas **não** é New Game: o rio, o chunk 14, o rank Apparitor e o HISTORY já são de 111 anos de Career.
- Ano **−300** **não** distingue os modos. Distingue: chunk **406** + pid **223**. Skill: chunk **16** (Achea e D.SAV são os dois Normal).
- Ghidra MCP desta sessão: **em baixo**. Capstone no LE mapeado: `0x5AFC6` é dirty-rect, **não** o store. Quem escreve 16+406: INF/default `0x70595` / `0x7062C`; Options `0x348CF` / `0x348EA` / `0x34909`. Quando o MCP voltar: **G `1049B`**, **G `10565`**, **G `706C3`**, **G `5CF80`**, xref **`0x9CE80`**.
- `Very Hard` **não existe** neste 1.1A. Quinto valor = `Impossible!`.
- Imigrante **não** lê o chunk 16. Inimigo **sim** (tabelas C2MODEL 5×4), com ramos diferentes City Only vs Career.
