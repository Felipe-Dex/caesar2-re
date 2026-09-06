# Forum — Q&A ACHEA23 (2026-09-05)

Tela de carreira (`view_submode=1`), **não** o prédio Aventine. Arquitectura: `findings/forum.md`. Prints no Cursor assets (Magic DosBox); **não** copiados para o git.

| | |
|---|---|
| Save | `C:\Users\Felip\OneDrive\Games\Caesar2\Achea.sav\ACHEA23.SAV` (225745 B) |
| HUD implícito | **187 BC January** (chunk **25** = **−187**, **26** = **0**) · tesouro **28561** |
| Nome no ecrã | **Felipe Dex** — **não** está no `.SAV` (nem `Felipe` / `Dex` / `Sophia`). `CAESAR2.INF` actual = `Sophia Dex`. Forum lê buffer de carreira / INF, não o trailer. |
| Ghidra | MCP `127.0.0.1:8080` recusou ligação nesta sessão. VAs = tabela SavChunk (`ghidra_city.md`). |

Dump: `python tools/_hud_fields_dump.py` + scan ACHEA23 + packs em **`findings/forum_strings.md`**. Confirmação: **Caesar II** (não C3). Onze prints bastaram para o chrome; **não** faltam fotos de Peace / Culture / Achaea / outras unconquered — o disco + o picker fecham esses packs.

---

## 0. Chrome — 12 botões

Kind **0**. Arte `forum.pl8` / `forum.256` / `forumbit.pl8`. Rótulos **não** são os títulos longos `[31]–[35]`. Pack C2.ENG **[28]+0…11**:

| + | Botão | Painel |
|---:|---|---|
| 10 | **ORACLE** | ratings (colunas) |
| 3 | **SCRIBE** | só gráficos HISTORY + setas de janela (10 / 20 / 30 anos) |
| 7 | **MERCHANT** | Industry |
| 6 | **CENTURION** | The Legion |
| 0 | **CLEAR FORUM** | (não clicado) |
| 4 | **ROME** | tribute + favor + **slot de pedido do Imperador** |
| 11 | **EMPIRE MAP** | mapa do império |
| 8 | **PLEBS** | Plebeian Tribune |
| 5 | **HELP** | (não clicado) |
| 1 | **TREASURER** | contas |
| 2 | **PERSONAL** | carreira |
| 9 | **EXIT** | sai (kind 9) |

Grelha no ecrã (4 colunas × 3 linhas). Activo = texto vermelho + ícone olho azul/branco.

```
ORACLE      | CENTURION   | EMPIRE MAP | TREASURER
SCRIBE      | CLEAR FORUM | PLEBS      | PERSONAL
MERCHANT    | ROME        | HELP       | EXIT
```

ORACLE e EMPIRE MAP são ecrãs cheios (`Right Click to Return to Forum`). Os outros oito mantêm a ilustração do Forum + a grelha.

---

## 1. ORACLE — Your Ratings (kind **1**)

Ecrã das **quatro colunas** (cidade + montanhas). C2.ENG **[30]+6…+13** / **[31]**.

| UI | Valor | Need | Chunk | VA | File off |
|---|---:|---:|---:|---|---:|
| Empire | **94** % | 30 % | **286** | `0x102530` | 219320 |
| Peace | **98** % | 30 % | **287** | `0x102574` | 219324 |
| Prosperity | **71** % | 30 % | **288** | `0x102538` | 219328 |
| Culture | **34** % | 30 % | **289** | `0x10252C` | 219332 |
| Average rating | **74** % | 40 % | **46** (cópias **60**, **257**, **376**) | `0x1028A8` | 207412 |

**Need 30 / 40** = C2MODEL rank slot **2** na dificuldade **Normal** (chunk **16** `0x9CE80` = **2**): individual `[830+2]=30`, average `[930+2]=40`. Hard tem os mesmos 30/40 neste slot.

Estes cinco inteiros **não** entram no trailer HISTORY (20 B = pop / tesouro / taxP / taxI / ano). Hipótese antiga confirmada.

Texto sem clique: `Select any of the ratings above to receive advice on improving them.` = **[31]+7**.

### 1.1 Kind **4** — clique numa coluna

Clique troca o prompt por um dos **14** textos vivos **[31]+8…+13 / +16…+23** (Peace **+14/+15** são stubs — o EXE **nunca** os escolhe). Picker `0x57450` + draw `0x5F033`: id em `[0x102558]`, skip = id+7. Tabela completa + condições: **`findings/forum_strings.md`**. Print ACHEA23, cursor em **Empire 94 % (Need 30 %)**:

> Your EMPIRE rating depends on developing your province. Pacify barbarian camps, connect towns to your city with roads, and build sources of industry.

Isto é **[31]+11** (C2.ENG tem dois espaços após o ponto; o ecrã compacta). Ratings no print = os mesmos **94 / 98 / 71 / 34**, média **74**.

Os quatro packs no C2.ENG (1.1A). Skip fotografado em **negrito**:

| Rating | + | Texto no ENG |
|---|---:|---|
| Empire | 8 | `Youe EMPIRE rating is as high as it can be for your city's current size.` (typo *Youe* no ficheiro) |
| | 9 | `Your EMPIRE rating is limited by your low Imperial Favor.  When the Emperor talks, you should listen!` |
| | 10 | `To improve your EMPIRE rating, build a larger provincial road network.  Link your city to border towns.  Build trading posts and ports, and link them as well.` |
| | **11** | **`Your EMPIRE rating depends on developing your province.`** + pacificar campos, estradas às towns, indústria. **Print.** |
| Peace | 12 | máximo possível para o tamanho da cidade |
| | 13 | lidar depressa com exércitos invasores; mantê-los fora da cidade |
| | 14 | placeholder **`Peace rating - tip3`** |
| | 15 | placeholder **`Peace rating - tip4`** |
| Prosperity | 16 | máximo possível para o tamanho da cidade |
| | 17 | falta de lucros — *turn a profit, and do so regularly* |
| | 18 | housing income baixo — melhorar habitação / income tax |
| | 19 | aumentar a população da cidade |
| Culture | 20 | máximo possível para o tamanho da cidade |
| | 21 | querem mais espectáculos / entretenimento |
| | 22 | crise espiritual — poucos templos |
| | 23 | serviços (hospitais, escolas) + gardens / plazas para *cleanliness* |

Peace / Prosperity / Culture **estão no ENG** e a regra de skip está no EXE — **não fotografar** as outras colunas. Stubs Peace +14/+15 confirmados (nunca escritos).

---

## 2. SCRIBE — só gráficos + janela de anos (kind **3**)

**Não há cartas nem inbox.** Pedido aberto do Imperador vive em **ROME**, não aqui. Não voltar a pedir print de “cartas do Scribe”.

Cabeçalho **Your Scribe** (`[32]+0`). Texto `Look at records` / `for the last` / `years.` / `to` = **[32]+5…+8**. As setas **só** mudam a janela de análise: **10 years, 20 years, 30 years…** (print ACHEA23 = 10; user confirmou o resto). **197 BC to 187 BC** nesta janela.

Quatro barras. Escalas C2.ENG **[32]+1…+4** (não `[30]+32`):

| Gráfico | Escala UI | Fonte |
|---|---|---|
| City population | 0 – 10 000 | HISTORY +0 |
| City funds | 0 – 50 000 | HISTORY +4 |
| Pop. taxes | 0 – 8 000 | HISTORY +8 |
| Industry taxes | 0 – 4 000 | HISTORY +12 |

Janela 10 anos = recs **25–35** do trailer (anos **−197…−187**). Última barra = rec 35: pop **9521**, tesouro **28561**, taxP **5209**, taxI **2797**, ano **−187**. Pop vivo (chunk **32** = **9561**) já cresceu em January — o gráfico usa o snapshot de fim de ano.

---

## 3. EMPIRE MAP (kind **6**)

`Roman empire circa 187 BC` (**[30]+42** + `abs(city_year)`). `Select province for more info`. `Right Click to Return to Forum`.

Províncias romanas a cinzento-claro; aquilae douradas; estrela vermelha sobre Itália/Roma.

Tooltip **existe** ao clicar uma província (não só sea lanes de Achaea). Caixa verde; `Right Click to Exit` (o chrome do mapa continua `Right Click to Return to Forum`).

Print **Germania Superior** (unconquered; C2, não C3):

| Linha | Texto | Fonte |
|---|---|---|
| Título (moldura + caixa) | **Germania Superior** | C2.ENG **[5]+32** |
| Estado | **As yet unconquered.** | C2.ENG **[47]+9** |
| Flavor | *This northern province contains a large barbarian presence, but its resources seem worth the danger.* | **HELP.ENG** (não está na tabela de 146 do C2.ENG). Mesmo texto que o corte de `C31.wav` em `REVERSE.md` |

**Não falta print.** 44 nomes `[5]+1…+44`, status `[47]+5…+9`, 44 flavors HELP (Latium `All roads…` + 43). Índice = skip do clique (`[0x102DE0] = ecx+1` = pid+1). Achaea / rotas / unconquered irmãos: `findings/forum_strings.md`.

---

## 4. MERCHANT — Industry (kind **7**)

Oito linhas. **Chunk 335** `0xD2AEC` file **219524**: só **id + kind** (0 local / 1 vizinho / 2 import). Números = **chunk 339** `goods_16x48` `0xD2B6C` file **219792**, um record 48 B (12×i32) por bem 0–15.

Layout 339 observado (Grapes/Lead/Iron/Clay/Copper):

| Off | Campo UI |
|---:|---|
| +4 | armazenado |
| +8 | factories (o número do meio) |
| +24 | % supplied (100) |
| +36 | produced / month |

| Linha | Bem | Kind (335) | /mês | Store | Factories | 339 good |
|---|---|---:|---:|---:|---:|---:|
| 1 | Grapes | 0 local | **8** | **30** | **4** 100% | 1 |
| 2 | Lead | 0 | **5** | **28** | **3** 100% | 5 |
| 3 | Iron | 0 | **3** | **7** | **2** 100% | 6 |
| 4 | Clay | 0 | **2** | **8** | **2** 100% | 8 |
| 5 | Copper via **Macedonia** (camelo) | 1 | — | **48** | **4** 100% | 7 |
| 6 | Silk via **Trade Route** | 2 | — | **0** | no factories | 12 |
| 7 | Marble via **Creta** | 2 | — | **0** | no factories | 10 |
| 8 | Copper via **Campania** | 2 | — | **48** | **4** 100% | 7 |

Origens 5–8 = LUT `0x95393` pid 15 → Macedonia / Trade Route / Creta / Campania (`province_gaps.md` §1.3). As duas linhas Copper **partilham** o record good **7** (48 / 4 uma vez).

---

## 5. CENTURION — The Legion (kind **8**)

C2.ENG **[34]+…**. Cohort report = mesmo texto que Query da província (`province_actors.md`).

| UI | Valor | Chunk / campo | VA |
|---|---|---|---|
| Monthly wages | **95** Dn (setas) | **194** | `0x102940` |
| Conscription | **0** % (setas) | **195** | `0x10295C` |
| The legion has N soldiers | **1330** | **198** | `0x102944` |
| ready | **1330** | **199** | `0x10297C` |
| in training | **0** | **200** | `0x102948` |
| auxiliaries | **0** · Gauls (Swordsmen) · 0 Dn/mês | **197** | `0x10296C` |
| Legion has 1 cohort | **1** | **196** | `0x102984` |
| Prima Cohors battle-ready | **1330** | **204** + actor26 slot 1 **`+0x8A`** | `0x10294C` / pool `0x114500` |
| Heavy / Light / Sling / Aux | 1330 / 0 / 0 / 0 | **203** + `+0x82` | `0x102950` |
| Troop morale / Readiness | EXCELLENT / EXCELLENT | actor26 `+0x94`/`+0x95` = **4** | |
| Rank | **Major** | actor26 `+0xA0` = **2** | |

Chunk **53** `[0x102A84]` = **0** neste save — **não** é o efectivo (hipótese antiga em `forum.md` / `forum_qa` checklist). Casa com Query AL29: **1330 Heavy**.

---

## 6. PLEBS — Plebeian Tribune

C2.ENG **[36]+0…21**.

| UI | Valor | Chunk | VA | File off |
|---|---|---:|---|---:|
| N plebs ready for work | **468** | **52** | `0x102A68` | 207436 |
| Estimated final plebs | **468** | **55** | `0x102AC4` | 207448 |
| No change from last month | — | string +4/+5 | | |
| welfare / mês | **98** Dn (setas) | **54** | `0x102A98` | 207444 |
| Idle Plebs | **7** | **56** +0x38 (também **57**) | `0xD2E6C` | 207452 |

Chunk **56** (64 B, 8 pares assigned/need + idle):

| Off | Assigned | Need | Linha |
|---:|---:|---:|---|
| +0 / +4 | 20 | 20 | Construction work |
| +8 / +0xC | 141 | 141 | Fire Prevention |
| +0x10 / +0x14 | 41 | 41 | City Roads |
| +0x18 / +0x1C | 40 | 40 | City Water |
| +0x20 / +0x24 | 9 | 9 | City Walls |
| +0x28 / +0x2C | 210 | 210 | Provincial Work |
| +0x30 / +0x34 | 0 | 0 | Army Duty |
| +0x38 / +0x3C | 7 | 0 | Idle / pad |

20+141+41+40+9+210+0+7 = **468**.

---

## 7. PERSONAL — The career of

C2.ENG **[30]+0…5**. Cargo **[7]+rank**.

| UI | Valor | Onde |
|---|---|---|
| The career of **Felipe Dex** | — | não no SAV; INF ≠ ecrã |
| Rank | **Apparitor** | chunk **291** `0x102578` = **2** → **[7]+2** |
| You need **8** promotions to become Emperor | 8 | **10 − 2** (Citizen…Consul = 0…9, depois Caesar). Não é dword 8 isolado óbvio |
| Monthly salary | **200** Dn (setas) | chunk **403** `0x102A48` file 221164 |
| You have savings of | **15279** Dn | chunk **402** `0x102A04` file 221160 |
| Donate money to the city? | checkbox vazio | flag não pinada |

---

## 8. ROME — tribute + favor + pedido do Imperador

C2.ENG **[37]+0…40**. Este painel é **tribute + quote de favor + slot de pedido do Imperador** (e gift). O slot é o campo que um passe antigo chamou “fila de cartas” — **não** é o SCRIBE.

Print ACHEA23: **`The Emperor currently requests nothing.`**

| UI | Valor | Onde |
|---|---|---|
| Imperial favor | `"It has been better, sir."` | **[37]+8** = índice **5** / 12 quotes (+3…+14). Chunk do índice: candidatos **410** / **422** (=5), sem Ghidra |
| Current annual tribute | **79** Dn | **157** `0x1029FC`, cópias **158 / 164 / 165** |
| **Emperor request slot** | **nothing** (ACHEA23) | string **`[37]+20`** `The Emperor currently requests nothing.` · prefixo activo **`[37]+21`** `The Emperor currently requests ` + bem/qtd (**+15…+19** = units / warehouse / dispatch). **Chunk do pedido = desconhecido** (Ghidra 8080 em baixo; sem save com request ≠ 0) |
| Send a personal 'gift'… | checkbox vazio | **[37]+22** |
| (Your average gift is **0** Dn) | 0 | **[37]+27**; dword 0 junto de savings (**400 / 401 / 407**); qual é o gift sem Ghidra |
| You have savings of | **15279** Dn | mesmo **402** |

---

## 9. TREASURER

C2.ENG **[28]+12…28**. `FUN_0005d892`.

| UI | Valor | Chunk | VA | File off |
|---|---|---:|---|---:|
| Treasury | **28561** Dn | **28** | `0x102AAC` | 207340 |
| Citizens | **9561** | **32** | `0x102AB0` | 207356 |
| employed | **62** % | **31** (cópias **20**, **321**) | `0x102A80` | 207352 |
| Population Tax rate | **4** % (setas) | **29** | `0x102A7C` | 207344 |
| Industrial Tax rate | **7** % (setas) | **30** | `0x102AA8` | 207348 |
| av. bill pop | **0.54** Dn | **calculado** `5209/9561 ≈ 0.545` | | |
| av. bill ind | **201.88** Dn | calculado (denominador não pinado) | | |

**188 BC ACCOUNTS** (ano acabado; HISTORY rec 35 está stampado **−187** depois do wrap — o rótulo UI é o ano jogado, 188 BC):

| Linha | Valor | Chunk | VA |
|---|---:|---:|---|
| surplus | **2948** | **33** | `0x102A64` |
| (+) Population Tax | **5209** | **34** | `0x102A5C` |
| (+) Industry Tax | **2797** | **35** | `0x102A34` |
| (−) Constructions | **263** | **36** | `0x102A54` |
| (−) Operating Costs | **4716** | **37** | `0x102A30` |
| (−) Annual Tribute | **79** | **157** (ou cópia) | `0x1029FC` |

**187 BC ESTIMATE** (ano corrente):

| Linha | Valor | Chunk | VA |
|---|---:|---:|---|
| surplus | **3405** | **38** | `0x102A1C` |
| (+) Population Tax | **5172** | **39** | `0x102A44` |
| (+) Industry Tax | **3028** | **40** | `0x102A10` |
| (−) Constructions | **0** | **41** | `0x102A40` |
| (−) Operating Costs | **4716** | **42** | `0x102A28` |
| (−) Annual Tribute | **79** | mesmo tribute | |

Chunk **29** = taxa pop **4** confirma a leitura do rioter (`walker_quotes.md`: `[0x102A7C] > 10`). Init de cidade = 5 (`ghidra_city.md`).

---

## Ainda falta (não é texto Oracle / Empire)

Packs Oracle + nomes + flavor + `[47]` status: **fechados** em `findings/forum_strings.md`. **Não** pedir mais prints de Peace / Culture / Achaea / Germania Inferior / Hibernia.

| Item | Porquê |
|---|---|
| **Pedido do Imperador ≠ nothing** | o **slot** é a linha ROME **[37]+20/+21**. Falta um save *com* request para pinar o **chunk**. `FUN_00058c87` = fila de **banners** (16 slots), não este campo. **Não** procurar isto no SCRIBE |
| **HELP / EXIT / CLEAR FORUM** | chrome óbvio; CLEAR FORUM ainda sem print do efeito |
| **Gift / Donate** on | checkbox + valor; grava save *antes/depois* se mexeres |
| **Favor dword** | quote índice 5; VA canónica por xref a **[37]+3** |
| **Average gift** | 0; vários dwords 0 ao pé de savings |
| **Qual cópia do tribute 79** o TREASURER vs ROME lê | 157 vs 158/164/165 |
| **av. bill indústria 201.88** | fórmula |
| **Nome Felipe Dex** | sítio no INF / RAM, não no SAV |
| Kinds exactos de TREASURER / PLEBS / ROME / PERSONAL | Ghidra `forum_panel_draw` quando o MCP voltar |

Não precisamos de Query da cidade nem de save novo **a menos** que Donate / gift / setas de salário mudem números.

---

## Pedido original (checklist)

O chrome **não** é “cinco botões no topo” (`Your Ratings` …). São os 12 acima. O resto do pedido:

1. Ratings — **feito**. Pack Oracle **[31]+8…+24** + picker `0x57450` em `findings/forum_strings.md`. **Não** fotografar Peace / Culture.
2. Scribe — **fechado**. Só gráficos + setas de janela (10/20/30 anos). **Nunca** pedir cartas / inbox neste botão.
3. Empire — **feito**. 44 nomes + 44 flavors HELP + status `[47]`. **Não** fotografar Achaea / rotas / outras unconquered.
4. Legion — **feito** (1330 = Query Prima Cohors).
5. Industry — **feito** (8 linhas = 335+339).
6. Extra: PERSONAL / TREASURER / PLEBS / ROME saíram no mesmo passe. Pedido do Imperador = **linha ROME**, vazio em ACHEA23.

Não usar a ordem antiga como lista de prints em falta: **não** pedir Scribe-cartas. Números vivos nas tabelas de cima.
