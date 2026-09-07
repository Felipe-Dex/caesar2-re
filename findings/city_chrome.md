# City chrome + placement v1 (host)

City Only iso **640×480**. Não é Forum. Não é Career. Ghidra HTTP estava em baixo nesta sessão; layout veio do PL8 + `build_palette.md` / `forum.md` §8.

## Como jogar no host

```text
python -m app --new --city-only --no-audio
```

`--sav` continua a carregar um save (título; **3** entra no mapa). O tesouro do SAV passa a ser lido do chunk **28** para o débito funcionar.

1. **Paleta** — sidebar **direita** (`INT_CITY.PL8` dest x=478). Clique num botão.
2. **Housing** escolhe Tent `0x82`. **Roads** escolhe estrada (ponte no rio recto). **Clear** é em dois passos: prédio→`0x05`, rubble→`0x1C`. **Query** inspecciona. **Water / Amenities / Security** abrem flyout (`app/palette.py`): Reservoir / Aqueduct / Well / Gardens / Praefecture **colocado**; Fountain / Plaza / Wall / Tower / Barracks / Forums / Entert'ment / Worship / Education = **ainda não**.
3. **Clique** no mapa = 1 tile (1×1) ou **3×3 NO** no Reservoir. **Clique-arrasta** com Housing / Roads / Clear / Well / Gardens / Aqueduct / Praefecture = borracha (preview); **só carimba ao soltar**. Reservoir: o arrasto só move o pé 3×3 (não enche um rect de bacias).
4. **Housing / Clear / 1×1 civic** pintam o **rectângulo** eixo-alinhado do tile inicial ao actual (preenche todas as células, ordem raster y depois x).
5. **Roads** só **linha recta** (sem L): eixo dominante do start ao cursor — se `|dx| ≥ |dy|` horizontal na linha `y` de início, senão vertical na coluna `x` de início. Ponte se a linha cruza rio recto; **curvas na linha são saltadas** (o resto confirma no soltar). Rubber-band do EXE **não** foi lido nesta passagem (Ghidra MCP em baixo).
6. **Botão direito:** com ferramenta de construir (ou a meio do arrasto) **cancela** sem carimbar (`0x329EF`). Sem ferramenta / **Query**: abre o diálogo do tile. **Esc** / **Q** ainda saem.
7. Tesouro no HUD. Tent = **6** por tenda **nova**. Well **20**, Gardens **3**, Praefecture **100**, Reservoir **51** (uma bacia 3×3). No arrasto 1×1, se o tesouro não chega para N novos, o host **recusa o rectângulo inteiro**.

**Pan vs construir:** com Housing / Roads / Clear / civic 1×1 activos, arrastar = borracha, **não** pan. Sem ferramenta, ou com **Query**, arrastar continua a fazer pan. Zoom / sidebar / setas **iguais**. Overlay: diamantes coloridos nas células afectadas + contagem no HUD.

## Original (EXE / PL8)

| Peça | Onde | Notas |
|---|---|---|
| `INT_CITY.PL8` | boot asset 11, paleta `CITY1.256` | 28 sprites. **Não** copiar para o git |
| Sprite 0 | `(0,0)` 640×24 | barra de topo |
| Sprite 1 | `(478,24)` 162×24 | faixa direita |
| Sprite 2 | `(478,208)` 162×160 | **painel com a grelha 3×5 já pintada** |
| Sprite 3 | `(478,368)` 162×112 | relevo de pedra (fundo; **não** é o minimapa) |
| Sprites 13–27 | xy flutuante `(245,287)`… | os 15 ícones da grelha, origem de autor `(244,211)` |

As 3 filas (`build_palette.md`). HELP.ENG Cty Icn e os frames
decodificados de INT_CITY coincidem: sprite 21 = garrafas (Industry),
sprite 22 = vaso + cruz verde (Sanitation):

```
Row 1: zoom in | clear | Housing | Roads | Forums
Row 2: zoom out | Water | Security | Industry | Sanitation
Row 3: Query | Entert'ment | Worship | Education | Amenities
```

Sprite 21 / grid 8 = Industry (Market / Factory) — garrafas. Sprite 22 /
grid 9 = Sanitation (Baths / Hospital) — vaso+cruz. Title e items no
mesmo click path. `ox` (janela > 640) desloca o strip 162 px e os rects
no clique (hitboxes da 3×5 preenchidas, sem gaps).

C2.ENG: **[23]** `Tent`, **[73]** `Query`, **[29]** `Treasury`, **[51]** `Cost: `. Housing / Roads / Water **não** são slots ENG (EXE / HELP). **[12]** `Reservoir` é o 1º do flyout Water — o host **já** carimba `0xBE` (3×3 NO).

Tabela **0x98B34** (18 B, `u16 id` + `u32 handler`) é o **overlay de relatório** (Geography…Markets, chunk 1). **Não** é a paleta de construir. Cancel = id 10 (`0x329EF` zera a ferramenta; **não** reseta o overlay). Clique no poço INT_CITY sprite 1 `(478,24)` 162×24. Host: `app/city_overlay.py` · `findings/city_minimap_overlays.md`. Punch list de prédios: `findings/city_buildings_punch.md`.

## Host (o que está / o que é stub)

**Fiel o bastante**

- Blit `INT_CITY` 0–3 nas dest x/y do PL8 (sidebar direita, como o EXE).
- Hitboxes da 3×5: sprites 13–27 deslocados `(478-244, 208-211)` para cima do painel 2.
- Housing → Tent `0x82` `+1=0x01` `+15=1` no próprio tile (`sav_c.md`).
- Roads → terreno `0x52–0x5C` + `+1 |= 0x20`. Autotile cardinal (NS `0x52`, EW `0x53`, cantos/T/cruz) e retile dos 4 vizinhos (inclui ponte como vizinho). LUT 8-vizinhos `0x94AEF` **não** portada (diagonais don’t-care no EXE).
- **Ponte** no rio recto (`+1 & 0x10`, sem bank `0x08`, id `0x1E–0x2D`): `+0` = `0x4E–0x51`, `+9` = id da água, `+1` = `0x30` (`FUN_000669c6`). **Recusa curva** (`+1 & 0x08`, ids `0x36`/`0x3A`/`0x46`/`0x4A` e remaps). **Recusa vizinho cardinal já ponte** (`0x4E–0x51` / rio+pad) — flood `0x665DF` só anda `±0x14` / `±0x640` e não cruza rio→rio. Diagonal é permitida. Numa linha de estrada essa célula é saltada (como a curva).
- **Ocupação de estrada** (`0x66B8D`): não escreve `+0` se `id ≥ 0x7C` (quartel / reservatório / aqueduto / casa). A célula é **saltada**; o resto da linha confirma. Gardens `0x78–0x7B` ficam abaixo do limiar do EXE. Detalhe: `findings/city_place_occupancy.md`.
- Clear: `id ≥ 0x82` (casas `0x82–0xA1`, civic) → rubble **`0x05`** (`0x68D2F` / `696E8`). Garden `0x78–0x7B` e plaza/estátua `0x7C–0x7E` flatten **`0x1C`** (`697FE`, sem rubble). Clear em rubble → flatten **`0x1C`**. Relva/estrada → `0x1C` (D.SAV). Ponte → restaura `+9` (`0x6985B`). Multi-tile (`DAT_00094FE5` + `+5`, `FUN_00069483`): Clear num tile do quartel 3×3 (ou villa 2×2 / palace 3×3) derruba o **pé inteiro**.
- Recusa rio aberto (`+1 & 0x10` sem pad) em Tent / Clear / civic / curva. Civic também recusa estrada e prédio (`id ≥ 0x78`).
- Débito Tent **6** (A/C). Reservoir **51** (A/B). Well **20** / Gardens **3** / Praefecture **100** (C2MODEL `[102:114]`). Arrasto 1×1 é **atómico**.
- **Reservoir** `0xBE` 3×3 origem NO: `+1=0x80` `+3=0x20` `+4=+9=0x6E` `+5=0…8` (`sav_ab.md` no origin; A/B cirúrgico foi 1×1 no canto — este host reserva o pé 3×3 como os outros multi-tile).
- **Well** `0xD7` 1×1 BUILD1B `+3=0x08` `+4=0x10` `+1=0x01` (`sav_d.md`).
- **Gardens** `0x78` 1×1 BUILD1A `+3=0x04` `+4=0`.
- **Praefecture** `0xE3` 1×1 HOUSES1 `+4=0x50`.
- **Aqueduct** isolado → stub `0xCB`; NS → `0xD0`; EW → `0xD1`; cruzamento → `0xD6`. `+1=0x40` (junção `0x60`). Sem débito. LUT completa `0xCF–0xD6` **não** portada.
- Clique paleta / clique mapa / direito ou **Space** cancela a ferramenta. **Esc** fecha painel/menu (City Only não sai). **P** pause · **C** census · **A** faster · **F**/**F2** forum · **F1** cidade · **F4**/**F5** load/save. **Q** ainda sai (host). Leftovers: rotate / flags / overlay letters / Query letter.
- **Top menus** (`C2.ENG` [0]…[3], `app/menus.py`). **File:** New Game = City Only de novo (`Start a New Game?` [9]+1, mesma skill; sem Campaign). Load = diálogo `*.sav` no install (não redistribui). Save / **F5** = diálogo e `app/sav.py` (225745 B; chunks que o host tem; resto a zero — `findings/sav_write.md`). Quit = `Exit to DOS?` [9]+0. **Options:** Music / Sound / Animations ON|OFF ([56]); End of Year = `Auto-Save is` (sem `lastyear.sav`); **Census** = painel [74] pop + origens Tent…Mansion. **Speed:** Pause toggle; Game Speed cicla Play↔Faster (INT_CITY 7–8); Scroll Speed = 1×/2×/3× do pan. **Help:** título + 1ª frase HELP.ENG (Hints 119 / Help 0 / History 2 / Icons 91); About = [10] versão + [56]+13. Sem ecrãs Career.
- **Speed** (INT_CITY sprites 6–8 remapeados no painel, acima da 3×5): **Pause** / **Play** (triângulo azul) / **Faster** (amarelo). Default **unpaused** (play, 1 pulso / due, scalar 70 → 200 ms). Faster = 4 pulsos (`[0xC45A0]`). HUD date (chunks 25/26) actualiza no wrap. **M** ainda fecha um mês. Sem economia.
- Clique-arrasta: preview (diamantes) até ao mouse-up; direito aborta sem stamp. Estrada = linha recta (eixo dominante). Casa/Clear = bbox. Tesouro do arrasto de tendas é **atómico** (tudo ou nada).
- Cache iso: `blit_dirty_tiles` nas células tocadas (não rebuild 80×80).
- **Minimapa** 80×80 (1 px = 1 tile) no poço vazio **acima** da paleta. Ver § Minimapa.

## Minimapa (host)

**Onde:** vazio da sidebar **acima** da grelha, não no relevo (sprite 3).
Sprite 1 acaba em y=48; sprite 2 (paleta) começa em y=208. O poço é
`(478, 48, 162, 160)` — o bitmap nativo **80×80** é escalado nearest-neighbor
até preencher esse rect (`MINIMAP_RECT` em `city_map.py`). Dest do EXE **não**
foi pinado (Ghidra em baixo).

**Cores:** relva verde, rio azul, estrada/ponte cinza, casa terracota, entulho
castanho (outros prédios dourados). Rectângulo **amarelo** = viewport iso
(pan/zoom), só a área à esquerda da sidebar (478×456 abaixo da barra de 24).

**Clique:** sim — clique no poço `(478,48,162,160)` centra a câmara nesse tile
(pixel → tile via escala). **Não** rouba a paleta (y≥208) nem os flyouts
(abrem à esquerda). Arrastar no poço não faz borracha nem pan do mapa iso.

**Overlays:** clique no poço do **nome** `(478,24)` 162×24 (sprite 1) → lista
Geography…Cancel. Pinta o 80×80 (não o iso). Detalhe: `city_minimap_overlays.md`.

## Stub / host-only

- Flyouts **listam** todos os nomes do §0. Colocam Reservoir / Aqueduct / Well / Fountain / Gardens / Praefecture / Tower / Barracks. Plaza, Forums, Entert'ment, Worship, Education, Wall = “ainda não” (`city_buildings_punch.md`). Lista do host, não o popup PL8 do EXE.
- Overlay-filter `0x98B34` / fase `0xD3` — minimapa **e** iso (`overlay_iso_wash`). Water: fontes + rio + `+13` + dry red. Janela redimensionável; zoom PL8 não muda.
- Custo de **estrada / ponte de cidade** — C2MODEL `[197]=20` é **província**. Sem débito. Não inventar.
- Splash `+15` 2×2 da tenda (C pinta vizinhos; o host só no tile).
- Query / direito (sem ferramenta) abre um diálogo mínimo (nome + bytes já conhecidos). Sem flavor dump do EXE.
- Highlight do botão = rect dourado, não o estado premido do EXE.
- Se `INT_CITY.PL8` faltar: barra 3 filas com labels (mesmo sítio).

## Custos

| Stamp | Id | Custo no host | Fonte |
|---|---|---:|---|
| Tent | `0x82` | **6** (arrasto: 6×N **atómico**) | `sav_c.md` (não está no C2MODEL) |
| Road | `0x52–0x5C` | **0** (desconhecido) | cidade não pinada; não usar 20 provincial |
| Bridge | `0x4E–0x51` | **0** | rio recto; `+9` guarda a água |
| Clear | `0x05` depois `0x1C` | **0** | `id≥0x82`→rubble; garden/plaza `0x78–0x7E` flatten; rubble→flatten |
| Reservoir | `0xBE` 3×3 | **51** (1 bacia) | `sav_ab.md` (C2MODEL `[101]=50` é FAQ) |
| Well | `0xD7` | **20** (arrasto: 20×N **atómico**) | C2MODEL `[102:114]` Well |
| Gardens | `0x78` | **3** (arrasto: 3×N **atómico**) | C2MODEL `[102]` / `[196]` |
| Praefecture | `0xE3` | **100** (arrasto: 100×N **atómico**) | C2MODEL Prefecture\|Aventine |
| Aqueduct | `0xCB` / `0xD0` / `0xD1` / `0xD6` | **0** (desconhecido) | sem slot cidade pinado |

Fountain / Forums / resto do flyout **não** entram.
