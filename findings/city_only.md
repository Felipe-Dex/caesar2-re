# City Only — do New Game até jogável (sem Career)

O utilizador quer **construir City Only de ponta a ponta**, e só depois Career. Este ficheiro é o plano das fatias. Irmãos: `app_structure.md` §6, `new_game.md`.

**Não** misturar REGIONS / actors26 / pick de província / `FUN_00010529` aqui. Isso é Career.

Ghidra MCP (`user-ghidra` / `project-0-caesar2-re-ghidra`) esteve **em baixo** no marco 1. Generate lido com Capstone em `ghidra_work/c2_x.bin` (`tools/_city_map_generate_disasm.py`).

---

## Como correr o marco 1

Python 3.14. Pasta do jogo: `CAESAR2_PATH` ou `app/config.local.json` (gitignored).

```text
C:\Users\Felip\AppData\Local\Programs\Python\Python314\python.exe -m app --new --city-only --no-audio
```

Skill (chunk **16**), default **2 Normal** (tesouro **12000**, como o D.SAV *antes* de gastar):

```text
python -m app --new --city-only --skill 0 --no-audio
python -m app --new --city-only --skill 2 --no-audio
```

| `--skill` | Label `C2.ENG` | Tesouro C2MODEL `[5:10]` |
|---:|---|---:|
| 0 | Novice | 20000 |
| 1 | Easy | 15000 |
| 2 | Normal (default) | 12000 |
| 3 | Hard | 7000 |
| 4 | Impossible! | 5000 |

Sem janela / smoke do gerador:

```text
python -m app --new --city-only --check --no-audio
python -m app --new --city-only --sim-smoke --no-audio
python -m app --new --city-only --map-preview sav_preview/city_only.png --no-audio
```

`--sav` continua a carregar um save. `--new` e `--sav` são exclusivos. `--new` sem `--city-only` recusa (Career não é esta sessão).

### O que se vê

A janela **abre já no mapa iso** (o mesmo `render_iso` / tecla **3** do load SAV — não o título `backgrnd.pl8`). Relva aleatória + um rio **animado** (4 frames da **mesma** orientação, `WATER_FRAME_MS` = 250 ms no host); **sem** casas, walkers, HISTORY. HUD: `City Only · Normal · treasury 12000 · 300 BC January`. Deixa a janela aberta — o rio cintila sem Space. Calibrar: um número no topo de `app/city_map.py`.

Load de `.SAV` **não mudou**: ainda começa no título; **3** entra no mapa.

### Teclas (vista iso)

| Tecla | Efeito |
|---|---|
| **Esc** / **Q** | sair |
| **1** | título `backgrnd.pl8` (sai do mapa) |
| **2** | 1º tile `CITYFIXT` (debug; só fora do mapa) |
| **3** | voltar ao mapa iso |
| **Space** / **T** | 1 pulso (`city_sim_phase` depois `walkers_tick`) — relva não evolui |
| **E** | evolve80 (host; sem casas = nop) |
| setas / arrastar | pan |
| **+** **−** / **]** **[** / **Z** / roda | zoom 0/1/2 |
| **Home** | recenter |
| **A** | 2 s `A01.RAW` (fora do mapa) |

Não há placement, Forum, paleta, nem tecla cidade↔província.

---

## 1. Marco 1 — feito (`--new --city-only`)

| Contrato | Host |
|---|---|
| chunk **406** = 1 | `SimState.city_only` |
| pid chunk **223** = 0 | `SimState.pid` |
| ano −300, mês 0 | `SimState.year_raw` / `month` |
| tesouro C2MODEL × skill | `SimState.treasury` (DAT se existir; senão tabela EXE) |
| walkers / actors / HISTORY | lista vazia; actors **não** alocados; 4000 B a zero |
| `city_map_generate` | `app/new_game.py` — relva + rio, **não** 80×80 zeros |
| vista | `BootContext.start_in_map` → `window.show_city_map` |

Módulo: `app/new_game.py` (`start_city_assignment`, `init` City Only, `city_map_generate`). `boot.run_boot(..., city_only=True, skill=N)` **não** chama `pick_save`.

### Generate — o que é fiel / o que não

Capstone em `0x65809` / `0x65AFA` / `0x658D1` / `0x28003`:

**Fiel o bastante**

- 17× `clear_byte8` lanes `2,1,3,9,0x10,5,6,7,8,0xF,0xD,0xE,0xA,0xB,0xC,4,0x11` (1–17)
- `fill_rand_terrain`: byte 0 = `(rng_clock & 0xF) + 8` (relva 8…23)
- LFSR `0x28003` + `rng_clock` `& 0x7F`
- Rio: começa no bordo norte, `x = 24 + (rng & 0x1F)`, 1º tile id **4** (sul), **OR `0x10` em +1**
- Drunk-walk ~960 passos, dirs 0/2/4/6, sem norte cedo (`esi < 4`), sem 180°, rejeita se >2 vizinhos já tiverem `0x10`
- Para no bordo (`x/y == 0` ou `≥ 79`); retry ≤ 6 se o trace devolver 0

**Diferenças (documentadas, não inventar o resto)**

- Seed do LFSR = relógio do host, **não** o RNG depois do título. O mapa **não** replaya um New Game concreto do EXE.
- `0x6B0D1` (teste de vizinho) no EXE lê um conjunto fixo de offsets; o host conta os **8** vizinhos com `+1 & 0x10`. Mesmo limiar `> 2`.
- **`0x65B3E` corre** no fim do trace (quando edi ≠ 0). Tabela `0x94AA7` + `0x6C826`: byte0 passa de dirs 0/2/4/6 para água `0x1E+` (CITYFIXT azul). Cantos OR `0x08` em +1. Relva 8…23 intacta; rubble `0x05` não é placeholder.
- `apply_regions_map` / `prov_map_fixup` / clima / `province_goods_setup` / `economy_recompute` **não** correm (Career ou fatias 3–4). O EXE chama `apply_regions_map` mesmo com pid 0 — o host **salta** de propósito.
- `city_map_zero_lanes` omitido: o blob já nasce a zero.

---

## Fatias seguintes (ordem)

Cada fatia: **objetivo**, **depende de**, **não é Career**. Não avançar Career / REGIONS / actors26 até City Only estar jogável.

### 2. Placement — estrada, tenda `0x82`, clear, débito do tesouro

- **Objetivo:** o jogador clica (ou tecla de debug) e **põe** estrada e uma tenda `0x82` no mapa gerado; **clear** remove; tesouro desce pelo custo C2MODEL (família `[102:]` / FAQ). Sem isto o Space só faz tick de relva.
- **Depende de:** marco 1 (mapa + tesouro vivo). Precisa dos ids de tile e do débito (A/B Reservoir = 51 é *outro* edifício — não inventar preços).
- **Não Career:** sem estrada provincial, sem `REGIONS`, sem forte / farm de província.

### 3. `+17` flood, `+15` recompute, água, imigrante / occupy

- **Objetivo:** depois de uma estrada + tenda, o pulso **pinta `+17`** (slots `0xA2–0xC1`, `0x430DA`) e **`+15`** (slots `0x76–0x8D`). Água (poço / fonte) entra no score. Imigrante `0x41DD4` (slots `0x9E–0xA1`) **ocupa** a tenda. Sem flood a casa não “vive”.
- **Depende de:** (2) placement. Wipes `0x51–0x54` só quando o paint existir (hoje o host **não** wipe para não destruir SAV).
- **Não Career:** spawn tipo 3 de **cidade** lê C2MODEL `[75:91]` só se 406≠0 — isso é City Only, mas é **inimigo**, não imigrante. Não abrir o ramo de invasão provincial.

### 4. `economy_recompute` no wrap do mês

- **Objetivo:** wrap `> 0xD6` já avança o mês (`calendar`). Ligar `economy_recompute` `0x3FCA0` o suficiente para o tesouro / impostos **não** ficarem congelados. HISTORY append no wrap do **ano** (`history_dat.md`) — 200×20 ainda a zero até lá.
- **Depende de:** (3) casas ocupadas (senão o recompute é um nop honesto). Marco 1 já tem tesouro + HISTORY vazio.
- **Não Career:** tribute / favor / pedido do Imperador **não** entram. Sem ROME.

### 5. Forum subset TREASURER / PLEBS / ORACLE P+C

- **Objetivo:** Forum **existe** em City Only (não é “modo sem Forum”). Abrir um subset: tesouro, plebeus, Oracle **só Prosperity + Culture**. Aviso `[31]+24` *cannot get promoted…* se alguém pedir Empire/Peace.
- **Depende de:** (4) números reais no tesouro / ratings. `forum.md` / `forum_strings.md`.
- **Não Career:** sem PERSONAL de promoção, sem EMPIRE MAP, sem pick `[47]`, sem Need `[790:990]`. Oracle ids &lt; 9 em city-only → skip 24.

### 6. Paleta 3 filas + overlay

- **Objetivo:** chrome de construção (`build_palette.md`) — 3 filas de edifícios + overlay de overlay-filter (chunk 1 / fase `0xD3`). O clique de (2) passa a escolher da paleta, não de um atalho de debug.
- **Depende de:** (2) o store de placement; (5) ajuda a não misturar Forum com paleta de cidade.
- **Não Career:** paleta **provincial** (estrada 20, forte, farm…) espera Career.

### 7. Win / lose a partir do EXE (não inventar)

- **Objetivo:** condição de vitória / derrota **lida no EXE** (strings `CONGRAT` / `LOSEGAME` / *win the game* no pack `[76]`). City Only: HELP diz só Prosperity + Culture. **Não** inventar um “reach 50 pop”.
- **Depende de:** (5) Oracle / ratings a mexer. Ghidra no ramo que escolhe a frase *win the game* (ainda **não** pinado — `new_game.md` §1.2).
- **Não Career:** promoção a Caesar / 8 promoções / `promote.smk` **não** são o win de City Only.

---

## Fora desta fila (Career, mais tarde)

`--new --career --region 15`, `apply_regions_map`, chunk 14, `actors26_tick`, mapa do império, tribute. **Não começar** até (2)–(7) ou até o utilizador pedir. O generate da cidade **80×80 é o mesmo**.

---

## Honestidade

- Marco 1 **sem** placement = viewer de cidade fresca. Space não “joga”.
- `CityMap()` a zeros **não** é New Game.
- Ano −300 **não** prova o modo; 406=1 + pid=0 sim.
- Skill default do **host** é Normal (2), não o INF Novice (0) — o utilizador pediu default 2.
