# Caesar II — Fase 1 (exploração)

**Última atualização:** 2026-08-28 (rev. 11 — SMK: 14/14 remuxados via ffmpeg; smackaudio 22050 u8)  
**Fonte:** `C:\Users\Felip\OneDrive\Games\Caesar2` (árvore plana; CD/retail DOS)  
**Versão:** `README.TXT` = **1.1A** (27 Feb 1996); string em `C2.ENG` = **“Caesar II - Version 1.1”**; `PS.EXE` datado **1995-10-04**.

Notas só com evidência. Hipóteses marcadas. Não copiar assets para distribuição.

**Caveat de ferramenta:** o índice do Cursor/OneDrive **omite** `.exe`, `.pl8`, `.256`, `.smk`, `.sav`, etc. (reparse/cloud). Inventário confiável = `Get-ChildItem` no PowerShell, não glob da IDE.

---

## 0. Veredito da instalação

É um **install DOS HD plano e jogável o suficiente**: executável, extender, gráficos PL8, paletas, Smacker, XMI, WAV, `.RAW` (provável PCM), saves, tabelas `.DAT`. Não é a raiz do CD (`HD\`, `PL8\`, …); o instalador já misturou tudo numa pasta.

| Extensão | Qtd | Bytes (soma) | Papel |
|---|---:|---:|---|
| `.PL8` | 299 | 24 398 332 | Sprites / tiles / UI / tutoriais / batalha |
| `.SMK` | 14 | 18 037 256 | Cutscenes Smacker |
| `.RAW` | 73 | 11 930 788 | PCM 8-bit unsigned mono **22050 Hz** (A/B/C + `PREBATLE.RAW`), não framebuffer |
| `.WAV` | 84 | 1 409 995 | SFX PCM |
| `.EXE` | 7 | 1 521 887 | Engine + tools |
| `.SAV` | 3 | 677 235 | Saves (tamanho fixo) |
| `.ENG` | 2 | 487 070 | Strings / help (inglês) |
| `.MDI` / `.DIG` | 16+9 | ~274 k | Drivers Miles AIL |
| `.256` | 147 | 112 896 | Paletas RGB (todas **768 bytes**) |
| `.XMI` | 5 | 54 494 | Música XMIDI |
| `.DAT` | 4 | 167 016 | Tabelas de jogo |

Executáveis presentes: `PS.EXE`, `DOS4GW.EXE`, `HAVEVESA.EXE`, `UNIVESA.EXE`, `SETSOUND.EXE`, `STUB.EXE`, `CHECK.EXE`.

---

## 1. `PS.EXE` — engine

| Campo | Valor |
|---|---|
| Caminho | `C:\Users\Felip\OneDrive\Games\Caesar2\PS.exe` |
| Tamanho | **1 040 111** bytes |
| Data NTFS | 1995-10-04 05:51:58 |
| Magic | `MZ` (DOS) |
| Extender | **DOS/4GW** (Rational Systems, stub no EXE; `DOS4GW.EXE` 254 556 bytes ao lado) |
| Compiler | **WATCOM C/C++32** (strings de runtime 1988–1994) |
| Launch | `C2.BAT` → `havevesa.exe` / `UNIVESA.EXE` → `ps.exe` (o stub MZ carrega o 4GW) |

Strings úteis (erro de I/O, sem disassembly):

- `Error loading graphics data - code %d - file not found.`
- `Error loading overlay data - file not found.`
- `Error loading battle data - %s not found.`
- `Not enough free memory to run Caesar2.`
- `resource.cfg`, `c2.eng`, `help.eng`, `history.dat`, `regions.dat`, `cd.dat`, `caesar2.inf`, `caesar2.sav`, `lastyear.sav`, `forum_x.gd8`

Lista embutida de `a01.raw`…`a30.raw`, `b01.raw`…`b30.raw`, `c01.raw`…`c44.raw` — o disco só tem A01–A09, B01–B20, C01–C43. O EXE conhece slots a mais (não usados nesta release, ou assets no CD não copiados).

`shot1.lbm`…`shot8.lbm` referenciados (“Exit from c2 tutorial mode .lbm file too large”) — **não estão** no HD; hipótese: leftovers de ferramenta interna (Deluxe Paint).

---

## 2. `.PL8` + `.256` — formato gráfico principal (confirmado nestes bins)

Paleta `.256`: **exatamente 768 bytes** = 256 × RGB (3 bytes, sem alpha). Em todos os samples desta install, **cada canal está em 0–63** (DAC VGA 6-bit). Expansão para 8-bit: `(c << 2) | (c >> 4)`. Índice 0 → alpha 0 no PNG.

Ex. `AHOUSE.256` começa `00 00 00 00 00 2A …`. `HOUSES1.PL8` **não** tem `.256` próprio; `CITYFIXT.256` é a paleta certa para tiles de cidade (`HOUSES1`, `BUILD1A`, `CITYFIXT`).

### Header PL8 (medido, little-endian)

Casa com a doc comunitária [pl8image](https://pl8image.readthedocs.io/en/latest/.pl8.html), com tamanhos de campo **corrigidos por evidência**:

| Offset | Tipo | Campo |
|---|---|---|
| 0 | u16 | flags (bit 0 = RLE na doc comunitária — **0/299** aqui; byte alto = zoom, ver abaixo) |
| 2 | u16 | número de sprites |
| 4 | u32 | desconhecido |
| 8 + 16×i | record 16 B | sprite *i* |

Record de sprite (16 bytes):

| Offset no record | Tipo | Campo | Evidência |
|---|---|---|---|
| 0 | u16 | width | `TUT_01A`: `80 02` = **640** |
| 2 | u16 | height | `E0 01` = **480** |
| 4 | u32 | data offset | `18 00 00 00` = **24** |
| 8 | u16 | x | |
| 10 | u16 | y | |
| 12 | u8 | tile type | |
| 13 | u8 | extra rows (ISO) | |
| 14 | u16 | unknown | |

Fórmula que bate em todos os samples:

`dataOffset(sprite0) = 8 + 16 × spriteCount`

| Arquivo | flags | sprites | spr0 | dataOff | checagem |
|---|---:|---:|---|---:|---|
| `AHOUSE.PL8` | 0002 | 1 | **182×132** | 24 | 24+182×132 = **24048** (tamanho do ficheiro) |
| `TUT_01A.PL8` | 0002 | 1 | **640×480** | 24 | 24+307200 = **307224** |
| `BACKGRND.PL8` | 0002 | 1 | 640×480 | 24 | idem |
| `BUILD1A.PL8` | 0002 | 123 | **58×30** | 1976 | 8+16×123 = 1976 |
| `HOUSES1.PL8` | 0002 | 106 | **58×30** | 1704 | 8+16×106 = 1704 |
| `CITYFIXT.PL8` | 0002 | 140 | **58×30** | 2248 | 8+16×140 = 2248 |
| `FONT_C2.PL8` | 0102 | 108 | 7×8 | 1736 | 8+16×108 = 1736 |
| `MOUSE.PL8` | 0202 | 22 | 16×16 | 360 | 8+16×22 = 360 |
| `SYSTEM.PL8` | 0202 | 64 | 16×16 | 1032 | 8+16×64 = 1032 |

**42** ficheiros PL8 têm tamanho **24048** → um sprite 182×132 sem compressão (ícones grandes de edifício: `AHOUSE`, `AFORUM`, `AFARM`, …).

**31** ficheiros têm **307224** → fullscreen 640×480 + header 24 B (tutoriais `TUT_*`, `BACKGRND`, `RAT_FRON`, …).

Pixels a seguir ao header, **tipo 0** (bitmap): **1 byte = índice de paleta**, `width×height` bytes (sem RLE).

### Flags — inventário completo (299/299)

Nenhum PL8 desta 1.1A tem o bit 0 ligado. A cadeia `span == packed_bytes` fecha em **299/299**. `RO2*` / `GM2*` **não** estão comprimidos: são bitmaps tipo 0 (~12–20×29–36 no zoom 2; ~6–10×14–16 no zoom 3).

| flags | Qtd | bit0 | Byte alto | Uso medido |
|---|---:|---|---|---|
| `0x0002` | 219 | 0 | 0 | zoom 1: cidade 58×30, unidades ~15×30, ícones 182×132, tutoriais 640×480 |
| `0x0102` | 63 | 0 | 1 | zoom 2: cidade 26×14 (`BUILD2*`, `HOUSES2`, `CITYFIX2`), unidades `*3*` ~8×15, `FONT_C2` |
| `0x0202` | 17 | 0 | 2 | zoom 3 / UI: cidade 10×6 (`BUILD3*`, `HOUSES3`, `CITYFIX3`), `MOUSE`, `SYSTEM`, `ICONS` |

O dígito no nome (`BUILD1/2/3`, `HOUSES1/2/3`, `RO2`/`RO3`) acompanha o byte alto **excepto** `MY_STDS3.PL8` (flags `0x0002`, sprites ~13×5). Bit 1 (`0x0002`) está **sempre** ligado — formato / “tem tabela”; sem contra-exemplo.

RLE comunitário ([pl8image](https://pl8image.readthedocs.io/en/latest/.pl8.html)): chunk `u8 n_opaque`; `0` → `u8` run transparente (índice 0); `N` → N índices. Implementado em `decode_pl8.py` (`rle_decode`) **sem sample nesta install** — não exercitado. Não inventar 0,0 = 256 nem RLE+ISO até aparecer um ficheiro com bit 0.

### Paletas e export (`images/`)

147 ficheiros `.256` (todos 768 B). Resolução em `resolve_palette`:

1. `{stem}.256` se existir (**143** PL8)
2. alias exacto: `CITYFIX2/3`→`CITYFIXT`, `PROVFIX2/3`→`PROVFIXT`, `BATLFIX3`→`BATLFIX2`, `RAT_FRON`→`RAT_BACK`, `FORUMBIT`→`FORUM`, `E_PARTS*`→`EMPIRE`, `INT_BATL`→`BATT1`, `INT_CITY`→`CITY1`, `INT_PROV`→`PROV1`, `HORSEB`→`BATT1`, `FONT*`→`CITY1` (**15**)
3. família: `BUILD*`/`HOUSES*`/`CITY*`/`OVERLAY*`/`LANDFILL`/`LTLMEN*` → `CITYFIXT`; `PROV*`/`PRVBLD*`/`MOUNTNS*` → `PROVFIXT`; unidades `RO/GM/GL/GK/EG/AF/AR/BR/CA/HN/PA`+dígito e `MY_STDS*`/`PACAVA*` → `BATLFIX2`; UI `ICONS`/`MOUSE`/`SYSTEM`/`PANELS`/`MAIN`/`MISC`/`SMACKER` → `CITY1` (**141**)
4. fallback documentado: `CITYFIXT.256`

Identidades medidas (bytes iguais): `CITYFIXT == PROVFIXT`; `CITY1 == CITY2 == VIEW1 == PROV1`; `BATT1 == BATT2`; `BATLFIX2` difere de `BATT1` em **1** byte. `CITYFIXT` vs `CITY1`: 730/768 iguais (slots de ciclo?).

`python tools/decode_pl8.py --export-all` → `images/{stem}.png` (1 sprite) ou `images/{stem}_sheet.png` (n>1). **299/299** nesta install. Gitignored. Folhas já boas na raiz (`AHOUSE.png`, `BUILD1A_sheet.png`, `CITYFIXT_sheet.png`, `HOUSES1_sheet.png`) mantidas.

### ISO (tile_type 1–4) — exercitado e fechado nestes bins

Diamante 58×30 = **900 bytes** no disco (não 1740 = 58×30 unpacked). Decoder: `tools/decode_pl8.py`. Algoritmo base da doc [pl8image](https://pl8image.readthedocs.io/en/latest/.pl8.html); tamanhos de campo da doc estavam ligeiramente errados — os records de **16 bytes** medidos aqui são a fonte.

Tamanho packed (58×30):

| tile_type | Payload no disco | Extra rows no canvas |
|---|---|---|
| **1** | sempre **900** (só diamante), **mesmo se `extra_rows` > 0** | canvas = 30; `extra_rows` é metadata, não payload |
| **2** | 900 + extra × **58** | canvas = 30 + extra |
| **3** / **4** | 900 + extra × **30** | canvas = 30 + extra (faixa esquerda / direita) |

A mesma geometria escala: zoom 2 **26×14** diamante = **196** B (`BUILD2A` 123/123); zoom 3 **10×6** = **36** B (`HOUSES3` 106/106). Extra tipo 2 = extra×W; tipo 3/4 = extra×(W/2+1) — a cadeia fecha sem regra nova.

`sprite[0].data_offset == 8 + 16 × n_sprites` — bateu em todos os samples. Cadeia `span == packed_bytes` usada como prova: cada sprite ocupa exatamente o intervalo até o offset do seguinte (último até EOF, ignorando slack de zeros).

| Arquivo | sprites | types | chain | Paleta | Folha local (gitignored) |
|---|---:|---|---|---|---|
| `AHOUSE.PL8` | 1 | 0 | 1/1 (bitmap 182×132) | `AHOUSE.256` | casa sobre relva |
| `HOUSES1.PL8` | 106 | 1–4 | **106/106** | `CITYFIXT.256` | tendas → insulae, muros, reservatórios |
| `BUILD1A.PL8` | 123 | 1–4 (59/16/24/24) | **123/123** | `CITYFIXT.256` | telhados, praças, muros, props |
| `CITYFIXT.PL8` | 140 | 1×133 + 0×7 | **140/140** | `CITYFIXT.256` | relva, árvores, rio, aquedutos; 7 bitmaps 2×2 / 2×3 |

`CITYFIXT` foi o caso que forçou a regra do tipo 1: 133 sprites tipo 1 com `extra_rows` 4–30 mas span **900**. Tratar extra como tipo 2 (`900+extra×58`) quebrava a cadeia.

Convenção de nomes (batalha) inalterada abaixo.

### Convenção de nomes (batalha)

Padrão `XXnWWWW[X].PL8`:

- Prefixo de facção/unidade: `RO` Roman, `GM`/`GL`/`GK` (Gaul/German/Greek **hipótese**), `EG` Egypt, `AF`/`AR` Africa/Arabia, `BR`, `CA`, `PA`, `HN` Hannibal, …
- Dígito `2` / `3`: **zoom** (casa com flags `0x0002` / `0x0102` / `0x0202` e geometria 58×30 → 26×14 → 10×6)
- Arma: `SWDA`/`SWDB` sword, `SPRA`/`SPRB` spear, `BOWC` bow, `KNFB` knife, `CAVA` cavalry, `SLGC` sling, `JAVC` javelin
- Sufixo `X`: variante (espelhado / morto / player?)

Alinhado às queixas clássicas da comunidade (`RO2SWDA.PL8 not found`) — **estes ficheiros estão nesta pasta.**

---

## 3. `.RAW` — não é o segundo pipeline gráfico

73 ficheiros. **Sem magic.** Série A/B/C: quase todos começam com uma run de `0x7F`. `C34.RAW` começa com um gradiente (`96 98 99 9B…`). `PREBATLE.RAW` (846 335 B) começa `80 80 81…`.

Nenhum RAW tem tamanho 307200 / 307224 → **não** são ecrãs 640×480 crus.

### Retratação: `A01.RAW` ≠ framebuffer 448×448

200 704 = **448×448 = 0x31000** é só o tamanho (factorização redonda). Wrap a 448 (e a 256 / 320 / 512 / 640 / 224 / iso-diamond 894×448) produz o mesmo aspecto: faixas horizontais de estático + barras sólidas `7F`.

O PNG do utilizador (`A01_view1`) usou `VIEW1.256`: índices vizinhos (~127±30) viram magenta/ciano/amarelo. Isso **não** é paisagem — é paleta de tiles em cima de um sinal 1D.

Medidas que matam o layout 2D:

| Teste | Resultado |
|---|---|
| Δ médio lag 1 | **5.2** (sinal suave em 1D) |
| Δ médio lag 64…800 | **~33** em *todas* as larguras (stdev do ficheiro ≈ 36) — nenhum período de linha |
| vm/hm em 70+ larguras | sempre **~6.3**; fracção de vizinhos verticais com Δ≤8 ≈ 21% |
| alinhamento das runs `7F` | nenhum W faz as faixas começarem em col 0 |
| skip de header 0–128 | não melhora |
| RLE PCX / PackBits / count-value / escape `7F` | falha (E25) |
| packing ISO tipo 1 (H²=200704) | diamante com as *mesmas* bandas `7F` + shear |

As “rampas” da row 7 (`80,76,71…`) são amostras consecutivas, não um horizonte.

### Confirmado: PCM 8-bit unsigned mono 22050 Hz (H1)

Os `.WAV` de cidade do install (`A09.WAV`, `FIRE.WAV`, `SWORDHT.WAV`, …) são **PCM unsigned 8-bit mono 11025 Hz**. Os bancos `.RAW` usam o mesmo formato de amostra, mas a **22050 Hz**. O EXE fala Miles/`AIL_set_sample_address` (PCM sem RIFF) e `null.voc`.

| Sinal | RAW | WAV de cidade |
|---|---|---|
| Byte | 8-bit unsigned, ~248 valores | 8-bit unsigned |
| Taxa | **22050 Hz** (A01 ouvido) | **11025 Hz** |
| Centro | `0x7F` (A/B/C) ou `0x80` (`PREBATLE`) | `0x80` |
| Runs longas | silêncio (A01: ≈0.13s + 0.83s + 0.76s @ 22050) | silêncio |
| Envelope | 3 rajadas (A01); ataques (C34) | SFX com pausas |
| Tamanhos | variáveis (A09=23 121 … C39=261 814) | duração do clip |

A01 @ 22050 Hz ≈ **9.1 s** (200 704 / 22050), três blocos de actividade — clip longo (voz / ambiente / sting), não um tile. A 11025 Hz soava a **cerca de metade da velocidade** (~18.2 s); 32000 Hz ficou em chipmunk — não usar.

`A09.WAV` (11 560 amostras) e `A09.RAW` (23 121 B = 2×11560+1) **não** são o mesmo payload (MAD≈35). O nome partilhado é coincidência ou outra take; o *formato* de amostra é o mesmo, a taxa não.

Decoder: `tools/decode_raw.py` (default = waveform / `--rate 22050`; `--export-all` → `sound/`; `--width` só para wrap experimental). PNG/WAV só local.

### Corte no fim (C31) — fechado

O utilizador ouviu `preview\C31.wav` terminar em *“… but its resources seem worth the …”* (linha de **Germania Superior**: *“… worth the danger”*). Velocidade 22050 Hz correcta; falta a cauda.

Hipóteses testadas (C31.RAW = 191 857 B = **8.701 s** @ 22050):

| Hipótese | Resultado |
|---|---|
| WAV com `data`/`RIFF` mais curto que o PCM | **Não.** `C31.wav` = RAW+44; chunk `data` = 191 857; `pcm == raw` |
| Decoder a cortar `0x7F` / silêncio / footer | **Não.** `write_pcm_wav` grava o ficheiro inteiro; os últimos **1860** B já são `0x7F` *no RAW* |
| Campo de comprimento no header | **Não.** Sem magic; `le32[0]` = `7F7F7F7F`, não um size |
| Últimos bytes = 16-bit / 2.º chunk | **Não.** Cauda = silêncio u8 `7F` (last 2 k: std≈0) |
| Continua em `C32.RAW` | **Improvável.** C32 é outro clip completo (~8.77 s, 4 rajadas, lead `7F` de 38 ms). C31 já acaba em silêncio (~0.12 s). Concat = duas linhas, não a palavra *danger* |

Envelope C31 (energia |s−7F|>4, gaps ≤100 ms): 0.13–1.31 s, 2.31–5.63 s, 6.39–7.90 s, **8.01–8.58 s** (0.56 s, std≈35 — volume normal). Depois só pad `7F`. A última rajada cabe em *“worth the”*; *“danger”* (~0.4–0.5 s) **não está no payload**.

**Veredito:** o PCM no disco já acaba a meio da frase. Não é bug do writer WAV nem do decoder. C32 (e A02/A05/…) são irmãos da mesma série, não caudas. C41 é o único par com fim “quente” + vizinho activo — outro assunto. Série no disco: A01–09, B01–20, C01–43, `PREBATLE` (EXE ainda cita a10–a30 / b21–b30 / c44).

Export canónico: `sound\{stem}.wav` + `_waveform.png` + `_spec.png`.

---

## 4. Dados, texto, saves

### `C2.ENG` (31 876 B) — strings UI (formato fechado)

```
0000  "Textfile"          # 8 bytes, sem NUL
0008  u32 0               # não é offset
000C  u32 offsets[n]      # absolutos, LE; n = (offsets[0] - 12) / 4
          → pool de C-strings Latin-1 (NUL)
```

Medido: **n = 146**, **142 offsets únicos** (4 aliases). Pool em 596…31784, slack 92 B. Offsets **não** são estritamente crescentes — o mesmo pointer pode servir vários IDs (ex. `"To"` nos índices 115–145, fragmentos de frase).

Extractor: `tools/extract_eng.py`. Dump completo fica em `notes/c2_eng_strings.txt` (gitignored — texto original do jogo).

Índice 0–23 é o vocabulário de menu + query (amostra, não o ficheiro): `File`, `Options`, `Speed`, `Help`, `Prima Cohors`, `Latium`, `Romans`, `Citizen`, `Caesar II - Version 1.1`, `Reservoir`, `Wall`, `Baths`, `Market`, `Wheat`, `Gems`, `Clay`, `Aventine`, `Grammaticus`, `Shrine`, `Theater`, `Tent`. Calendário: `January`, `BC`, `Week 1`. Dificuldade: `Novice`. Não há neste ficheiro os nomes `Decurion` / `Consul` / `Janiculan` / `Fountain` / `Impossible` — ou estão no EXE / `HELP.ENG`, ou são compostos.

`HELP.ENG` (455 194 B): magic **`Helpfile`**, 58 zeros, primeiro payload em offset 66 (`u32 116008`, depois ASCII `null.p…`). **Não** é a mesma tabela de offsets. Formato ainda opaco.

### `C2MODEL.DAT` (4360 B = **1090 × int32 LE**)

Sem magic. Dump: `tools/dump_c2model.py`. Cruzado com o FAQ Falanx / caesar2.com (números de v1.0; esta install é 1.1A).

| Índices | Valores | Identificação |
|---|---|---|
| 0–4 | 20, 15, 10, 5, 2 | 5 slots (uma por dificuldade?). **Opaco** |
| **5–9** | **20000, 15000, 12000, 7000, 5000** | **Fundos iniciais** Novice→Impossible |
| 10–14 | 2000, 500, 250, 150, 100 | Degraus de dinheiro / custos de província. Hipótese |
| **115–117** | **80, 200, 600** | **Shrine, Temple, Basilica** |
| **118–123** | **300, 500, 700, 1000, 1500, 2500** | **Theater…Circus Maximus** |
| 124–157 | 0, 5, 10, … 160 | Rampa ×5 — o “hit” de ranks em 128 é **coincidência** |
| **196–205** | **3, 20, 50, 500, 100, 250, 1000, 150, 400, 500** | Gardens, Road, Wall, Fort, Work camp, Farm, Port, Warehouse, Shipyard, Trading post |
| **215–246** | occupancy 32 graus | **2,4,6,8,10,12,6,7,…300,500** = FAQ de habitações **exato** |
| 790–989 | blocos de 20 ints, `99` = sentinela | Hipótese **forte:** 5 dificuldades × ~20 slots de rank (individual + average). Normal individual `20…65` em 830; average `30…74` em 930. 1.1A tem slots extra além dos 10 ranks do FAQ v1.0 |

Custos de cidade **não** estão na ordem do FAQ (water→sanitation→…); estão agrupados por família (worship, entertainment, province). `H2` sobe de hipótese pura para **parcialmente confirmado**.

### `REGIONS.DAT` (158 400 B)

Sem ASCII; bytes tipo mapa/índices (`15 98 11 17…`). **Hipótese:** mapa de províncias / terreno da camada império. 158400 = 396×400 ou 180×880 — não cravar geometria.

### `HISTORY.DAT` (4000 B, data 2011)

int32s mistos (incluindo negativos `D5 FE FF FF` = −299). **Hipótese:** histórico de campanha / high scores do jogador, não do CD.

### `DISCS.DAT` (256 B) + `DISCS.IX` (1996 B)

Referenciados via `cd.dat` no EXE. **Hipótese:** layout de CD / catálogo de ficheiros no disco.

### `FORUM_X.GD8` (3040 B)

Começa zeros. String no EXE junto de `forumbit.pl8`. **Hipótese:** geometria/overlay do fórum, não texto.

### Saves `.SAV` — tamanho **fixo 225 745** = **1745 + 35×6400**

Sem magic ASCII. Encaixe exacto com o mapa de cidade da comunidade (**80×80** tiles):

```
0000     header 1745 B   (escalares; esparso)
06D1     35 planos SoA   de 80×80 = 6400 B cada   (offset 1745)
         … até EOF 225745
```

1745 + 35×6400 = 225745. **SoA, não array-of-structs:** o plano 6 é **6400 zeros consecutivos** nos três saves (campo reservado / não usado). Num AoS de 35 bytes/tile esses zeros estariam de 35 em 35 bytes, não num bloco contínuo.

| Plano | Offset | nz FELIPE01 | A=B | Notas |
|---:|---:|---:|---:|---|
| 0–4 | 1745… | 516–2681 | 66–95% | camadas com estrutura espacial (estradas / overlays?) |
| **5** | 33745 | **13** | 99.8% | quase vazio |
| **6** | 40145 | **0** | 100% | **sempre zero** |
| 7–27 | … | ~650–2000 | 65–91% | |
| **28–31** | 180945… | ~2600–3100 | **~48%** | mais diferentes entre campanhas → **candidatos a tipo de tile / edifício** |
| 32–33 | … | ~1750 | ~72% | |
| 34 | 219345 | 935 | 90% | banda horizontal tipo rio/terreno; metade sul vazia |

Header (u32 LE):

| Ficheiro | u32@0 | u32@8 | u32@12 | nonzero no header |
|---|---:|---:|---:|---:|
| `FELIPE01.SAV` | **1024** | 50 | 54 | 120 |
| `FELIPE02.SAV` | **1024** | 29 | 56 | 130 |
| `LASTYEAR.SAV` | 16842752 (`00 00 01 01`) | 33 | 18 | 57 |

`u32@8` **hipótese:** ano BC (`C2.ENG` tem `January` / `BC` / `Week 1`). `u32@12` opaco. Depois do offset 16 o header é quase todo zero até ~191 (bloco de estado: dinheiro / população / flags — ainda sem labels).

A hipótese antiga 40×40×31 @ ~176128 **não se segura**: 176128 cai *dentro* dos planos 27–34; o bloco de 6400 zeros do plano 6 é a prova de alinhamento. `tools/probe_sav_map.py` gera mapas ASCII de ocupação (`.` / `#`) sem exportar IDs.

Para **nomear** cada plano: um par controlado (construir 1 casa ou 1 estrada, gravar). Os planos 28–31 são o sítio onde isso deve aparecer.

### `CAESAR2.INF` (64 B, 2011)

Contém o nome de jogador `Sophia Dex` — save metadata / perfil, não do retail 1995.

### `RESOURCE.CFG` (51 B)

```ini
[Config]
resaud=M
resmap=M
ressfx=M
rescdis=M
```

String `resource.cfg` existe em `PS.EXE`. Valor `M` continua **opaco** (CD original = 283 bytes). Hipótese inalterada: código de origem HD/CD escrito pelo Sierra INSTALL, não path SCI.

---

## 5. Áudio e vídeo (formatos públicos)

| Tipo | Magic / evidência | Notas |
|---|---|---|
| `.XMI` | `FORM` … `XDIR` `INFO` `CAT ` | Miles XMIDI. 5 faixas: `BATEST2`, `CITYPROV`, `FORUM1–3` |
| `.SMK` | `SMK2` (14/14); sem `SMK4` / AVI / FLC / FLI | Smacker (RAD). Ver §5.1 |
| `.WAV` | PCM; nomes batem com edifícios/combate | Miles digital (`DIG.INI` → `SBLASTER.DIG`) |
| `.AD` / `.OPL` | `CAESAR.AD`, `CAESAR.OPL` | Hipótese: fallback AdLib/OPL |

Miles AIL **3.02** (18-Jan-95) em `DIG.INI` / `MDI.INI` / `AILDRVR.LST`.

### 5.1 `.SMK` — Smacker (RAD Game Tools), não um codec novo

14 ficheiros, **18 037 256** B, todos na raiz do install. Magic **`SMK2`** (4 bytes). Header público de **104** B ([wiki.multimedia.cx/Smacker](https://wiki.multimedia.cx/index.php/Smacker)): `Width`, `Height`, `Frames`, `FrameRate` (signed), `Flags`, `AudioSize[7]`, árvores Huffman, `AudioRate[7]`.

`FrameRate` nesta install: **−8333** → fps = `100000/8333` = **12.00** (13 clips); `MESSAGE` = **−7100** → **14.08** fps. `Flags` = 0 (sem ring frame / Y-double).

Áudio (campo `AudioRate[0]` = `0xC0005622` em todos): bit 31 compressed + bit 30 present; **22050 Hz, 8-bit, mono, DPCM** (Smacker Huffman). ffmpeg 9.0.1 (Gyan): `smackvideo` `pal8` + `smackaudio` (`smackaud` / `SMKA`) **22050 Hz mono u8**. Mesma taxa/largura dos bancos `.RAW` — outro pipeline (vídeo vs AIL), mesmo formato de amostra.

Não há `.AVI` / `.FLC` / `.FLI`. `SMACKER.PL8` + `SMACKER.256` é **chrome de UI** (já em `images/`), não um clip.

| Ficheiro | Bytes | Res | Frames | fps | dur | Papel (nome) |
|---|---:|---|---:|---:|---:|---|
| `ARMYWARN.SMK` | 462 504 | 320×152 | 50 | 12 | 4.17 s | aviso de exército |
| `BATTLOST.SMK` | 1 212 792 | 320×152 | 90 | 12 | 7.50 s | batalha perdida |
| `BATTWON.SMK` | 1 134 136 | 320×152 | 120 | 12 | 10.00 s | batalha ganha |
| `CONGRAT.SMK` | 1 074 088 | 320×152 | 126 | 12 | 10.50 s | parabéns / rank |
| `FIRE.SMK` | 1 543 704 | 320×152 | 150 | 12 | 12.50 s | incêndio |
| `INTRO.SMK` | 791 340 | **640×480** | 360 | 12 | 30.00 s | intro / title (único fullscreen) |
| `LOSEGAME.SMK` | 1 587 792 | 320×152 | 193 | 12 | 16.08 s | derrota de campanha |
| `MESSAGE.SMK` | 664 576 | 320×152 | 121 | **14.08** | 8.59 s | mensagem |
| `PROMOTE.SMK` | 1 535 764 | 320×152 | 120 | 12 | 10.00 s | promoção |
| `RIOTERS.SMK` | 1 045 912 | 320×152 | 120 | 12 | 10.00 s | motim |
| `ROBBERY.SMK` | 724 260 | 320×152 | 120 | 12 | 10.00 s | roubo |
| `SICK.SMK` | 1 217 164 | 320×152 | 120 | 12 | 10.00 s | doença |
| `WARNING.SMK` | 557 868 | 320×152 | 56 | 12 | 4.67 s | aviso |
| `WINGAME.SMK` | 4 485 356 | 320×152 | 437 | 12 | 36.42 s | vitória de campanha (maior) |

320×152 é janela letterbox no UI 640×480 (encaixa no chrome `SMACKER.PL8`). `INTRO` é VGA cheio; frame 0 = cartão “CAESAR II” em relevo. `WINGAME` / `LOSEGAME` começam em frame preto (fade-in) — PNG de 1 kB, não falha de decode.

Export: `python tools/decode_smk.py --export-all` → ffmpeg `libx264` + AAC em `videos/{stem}.mp4` e `{stem}_frame0.png`. **14/14** nesta 1.1A. ffmpeg avisou `Skipping FULL tree` em `INTRO.SMK` (árvore Huffman vazia); o MP4 saiu 30 s / 640×480 na mesma. Gitignored. Não copiar `.SMK` para o git.

Decoder nosso **não** implementa Smacker — só lê o header de 104 B e chama ffmpeg. Codec = `smackvid` / `smackaud` no binário do Gyan.FFmpeg 9.0.1.

---

## 6. Comparação com Caesar III / Pharaoh

| | Caesar II (estes bins) | C3 / Pharaoh |
|---|---|---|
| Cor | 256 cores, paleta `.256` | 16-bit `.555` |
| Catálogo de sprites | **dentro do próprio `.PL8`** (count + records) | `.SG2`/`.SG3` separado do pixel dump |
| Tile cidade | PL8 com sprites **58×30** (`BUILD*`, `HOUSES*`, `CITYFIXT`) | Diamante **58×30** no `.555` |
| Fullscreen | PL8 640×480 | BMP/555 / painéis SG |
| Paleta | `.256` 768 B RGB | embutida / 16-bit |
| Engine | Watcom 32 + DOS4GW (`PS.EXE`) | Win32 C3 |
| Saves | 225 745 B fixos | outro layout |

**58×30 no C2 já é o diamante do C3.** Ancestral direto do tile; o *container* mudou (PL8 → SG2+555). Parsers de Augustus **não** abrem estes ficheiros, mas um conversor PL8-58×30 → atlas moderno é o atalho mais promissor.

`.RAW` não tem equivalente C3 óbvio (e provavelmente nem é gráfico).

---

## 7. Próximos passos (repriorizados)

1. **Par controlado de `.SAV`:** um save, **uma** casa (ou 1 tile de estrada), gravar outro. Diff nos planos 28–31 (80×80 SoA @ 1745). Isso nomeia o campo “tipo de edifício”.
2. **RAW:** taxa **22050 Hz** e dump em `sound/` feitos. No EXE, confirmar se A/B/C são bancos AIL (batalha vs cidade / VO de província). Corte C31 = payload curto no install, não no decoder.
3. **PL8:** decoder 0–4 + zoom 26×14 / 10×6 + `--export-all` → `images/` (**299/299**). RLE bit 0 **não existe** nestes bins; o caminho comunitário fica no decoder por se outra install o tiver.
4. **`HELP.ENG`:** o magic `Helpfile` + offset 116008 não é a tabela `Textfile`; parsear só se precisarmos do texto de ajuda.
5. **Ghidra em `PS.EXE` (LE/Watcom)** depois de 1–4: loader PL8 e reader de `C2MODEL.DAT`.
6. CD original ainda útil para o `RESOURCE.CFG` de 283 B e para RAW A10+ se existirem.

Não priorizar XMIDI (já há libs). Smacker fechado nesta install (ffmpeg). Não priorizar crack/CD check.

Feito nesta fase: decoder PL8 0–4 (incl. zoom 2/3); export `images/`; `C2.ENG`; `C2MODEL.DAT`; `.SAV` 80×80 SoA; `.RAW` retractado como imagem (H1 = PCM 8-bit unsigned mono **22050 Hz**); `.SMK` inventariado + remux `videos/` (**14/14**). Dumps em `notes/` (gitignored).

---

## 8. Log de evidências

| ID | Observação | Tipo |
|---|---|---|
| E1 | README v1.1A; `C2.ENG` “Version 1.1”; `PS.EXE` 1995-10-04 | fato |
| E2 | `PS.EXE` 1040111 B, MZ + DOS/4GW + Watcom C/C++32 | fato |
| E3 | `.256` = 768 B RGB | fato |
| E4 | PL8: `dataOff0 = 8+16×N`; `AHOUSE` 182×132; `TUT_01A` 640×480 | fato |
| E5 | `BUILD1A` / `HOUSES1` / `CITYFIXT` sprite0 = **58×30** | fato |
| E6 | 3× `.SAV` = 225745 B, MD5 distintos | fato |
| E7 | `C2.ENG` magic `Textfile` + offsets u32 | fato |
| E8 | `C2MODEL.DAT` = 1090 int32 | fato |
| E9 | `INTRO.SMK` = `SMK2` 640×480; XMI = `FORM`/`XDIR` | fato (SMK expandido em E36) |
| E10 | EXE lista RAW a01–a30 / b01–b30 / c01–c44; disco tem menos | fato |
| E11 | Índice Cursor omitia EXE/PL8/SMK (OneDrive) | fato (metodologia) |
| E12 | Paleta `.256`: bytes 0–63; expand VGA 6-bit → 8-bit | fato |
| E13 | ISO 58×30 diamond = 900 B; type 2 extra×58; type 3/4 extra×30 | fato |
| E14 | Type 1: `extra_rows` no record, payload continua 900 (`CITYFIXT` 133/133) | fato |
| E15 | Cadeia span=packed: `HOUSES1` 106/106, `BUILD1A` 123/123, `CITYFIXT` 140/140 | fato |
| E16 | Folhas visuais: casas/água (`HOUSES1`), rio/aqueduto (`CITYFIXT`), praças/muros (`BUILD1A`) | fato |
| E17 | `C2.ENG`: 146 strings, pool @ 596, 142 offsets únicos; aliases `"To"` | fato |
| E18 | `C2MODEL[5:10]` = fundos iniciais 20000…5000 (5 dificuldades) | fato |
| E19 | `C2MODEL[215:247]` = occupancy 32 graus de habitação (FAQ) | fato |
| E20 | `C2MODEL[118:124]` entertainment costs; `[115:118]` shrine/temple/basilica | fato |
| E21 | `C2MODEL[196:206]` custos de província (+ Gardens=3) | fato |
| E22 | FELIPE01 vs 02: 25.7% bytes diferentes (campanhas distintas) | fato |
| E23 | `.SAV` = 1745 + 35×6400; plano 6 = 6400 zeros nos 3 saves (SoA 80×80) | fato |
| E24 | `A01.RAW` = 200704 B = 448²; Δhoriz≈5.2; `7F` = valor central (ex-“céu”) | fato (tamanho); layout 2D **retractado** |
| E25 | RLE PCX/PackBits/count-value/`7F`-escape não fecha A02/A04/C01/PREBATLE | fato |
| E26 | Nenhuma largura 64–800 tem correlação vertical (vm≈42, vm/hm≈6.3) | fato |
| E27 | WAV de cidade = u8 mono **11025 Hz**; RAW partilha histograma / silêncio `7F`/`80` | fato |
| E28 | Wrap 448 + `VIEW1.256` = estático neon + barras `7F` (PNG do utilizador) | fato |
| E29 | A01.RAW @ **22050 Hz** = velocidade correcta (~9.1 s); 11025 = metade; 32000 = chipmunk | fato |
| E30 | C31.wav RIFF/`data` = RAW inteiro (191 857); sem length field; cauda = 1860×`7F` | fato |
| E31 | C31 última rajada 8.01–8.58 s (std≈35); C32 = clip de 8.77 s, não suffixo | fato |
| H1 | RAW A/B/C + `PREBATLE` = PCM 8-bit unsigned mono **22050 Hz** (Miles AIL) | confirmado (E29) |
| H2 | `C2MODEL` = tabelas de economia — **parcialmente confirmado** (E18–E21) | hipótese |
| H3 | `REGIONS.DAT` = mapa de províncias | hipótese |
| H4 | `M` em RESOURCE.CFG = origem HD/CD | hipótese |
| E32 | 0/299 PL8 com flags bit 0; cadeia span=packed em 299/299; `RO2SWDA` = 178 bitmaps ~12×29 | fato |
| E33 | flags `0x0002`/`0x0102`/`0x0202` = zoom 58×30 / 26×14 / 10×6 (`BUILD*`/`HOUSES*`/`CITYFIX*`) | fato |
| E34 | `CITYFIXT.256 == PROVFIXT.256`; `CITY1 == CITY2 == VIEW1 == PROV1`; `BATT1 == BATT2` | fato |
| E35 | Folhas: `RO2SWDA` legionário + *scutum*; `GM2SWDA` túnica castanha + escudo redondo; `HOUSES1` tendas→aquedutos; `TUT_01A` painel 640×480 | fato |
| H5 | Dígito 2/3 nos PL8 de batalha = zoom | confirmado (E33; excepção `MY_STDS3`) |
| H6 | `.SAV` u32@8 = ano BC; planos 28–31 = tipo de tile | hipótese |
| H7 | `C2MODEL[790:990]` = ranks × dificuldade (`99` = slot vazio) | hipótese |
| E36 | 14/14 `.SMK` = `SMK2`; 13× 320×152 @ 12 fps + `INTRO` 640×480 @ 12 + `MESSAGE` @ 14.08; áudio `smackaud` 22050 Hz mono u8; 0 AVI/FLC/FLI; ffmpeg 14/14 | fato |

---

## 9. Fora de escopo

- Implementar engine Godot/C++ nesta fase.
- Copiar/redistribuir assets.
- Crack, bypass de CD, patch do EXE.
- Assumir que loaders de Caesar III abrem C2.
