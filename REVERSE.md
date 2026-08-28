# Caesar II — Fase 1 (exploração)

**Última atualização:** 2026-08-27 (rev. 4 — `C2.ENG` / `C2MODEL.DAT` / header `.SAV`)  
**Fonte:** `C:\Users\Felip\OneDrive\Games\Caesar2` (árvore plana; CD/retail DOS)  
**Versão:** `README.TXT` = **1.1A** (27 Feb 1996); string em `C2.ENG` = **“Caesar II - Version 1.1”**; `PS.EXE` datado **1995-10-04**.

Notas só com evidência. Hipóteses marcadas. Não copiar assets para distribuição.

**Caveat de ferramenta:** o índice do Cursor/OneDrive **omite** `.exe`, `.pl8`, `.256`, `.smk`, `.sav`, etc. (reparse/cloud). Inventário confiável = `Get-ChildItem` no PowerShell, não glob da IDE.

---

## 0. Veredito da instalação

É um **install DOS HD plano e jogável o suficiente**: executável, extender, gráficos PL8/RAW, paletas, Smacker, XMI, WAV, saves, tabelas `.DAT`. Não é a raiz do CD (`HD\`, `PL8\`, …); o instalador já misturou tudo numa pasta.

| Extensão | Qtd | Bytes (soma) | Papel |
|---|---:|---:|---|
| `.PL8` | 299 | 24 398 332 | Sprites / tiles / UI / tutoriais / batalha |
| `.SMK` | 14 | 18 037 256 | Cutscenes Smacker |
| `.RAW` | 73 | 11 930 788 | Arte extra (A/B/C + `PREBATLE.RAW`) |
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
| 0 | u16 | flags (`0x0002` bitmap simples nos samples de cidade; `0x0202` mouse/system; `0x0102` fonte) |
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

Pixels a seguir ao header, **tipo 0** (bitmap): **1 byte = índice de paleta**, `width×height` bytes (sem RLE). Flags `0x0002` ↔ bitmap simples. RLE (bit 0 de flags) **ainda não** foi exercitado (provável em packs de batalha `RO2*`, `GM2*`, etc.).

### ISO (tile_type 1–4) — exercitado e fechado nestes bins

Diamante 58×30 = **900 bytes** no disco (não 1740 = 58×30 unpacked). Decoder: `tools/decode_pl8.py`. Algoritmo base da doc [pl8image](https://pl8image.readthedocs.io/en/latest/.pl8.html); tamanhos de campo da doc estavam ligeiramente errados — os records de **16 bytes** medidos aqui são a fonte.

Tamanho packed (58×30):

| tile_type | Payload no disco | Extra rows no canvas |
|---|---|---|
| **1** | sempre **900** (só diamante), **mesmo se `extra_rows` > 0** | canvas = 30; `extra_rows` é metadata, não payload |
| **2** | 900 + extra × **58** | canvas = 30 + extra |
| **3** / **4** | 900 + extra × **30** | canvas = 30 + extra (faixa esquerda / direita) |

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
- Dígito `2` / `3`: hipótese = zoom ou formação
- Arma: `SWDA`/`SWDB` sword, `SPRA`/`SPRB` spear, `BOWC` bow, `KNFB` knife, `CAVA` cavalry, `SLGC` sling, `JAVC` javelin
- Sufixo `X`: variante (espelhado / morto / player?)

Alinhado às queixas clássicas da comunidade (`RO2SWDA.PL8 not found`) — **estes ficheiros estão nesta pasta.**

---

## 3. `.RAW` — segundo pipeline gráfico

73 ficheiros. **Sem magic.** A01/A04/B01/C01 começam com dezenas de `7F` (índice de paleta, não ASCII). `PREBATLE.RAW` começa `80 80 81 81…`.

Nenhum RAW tem tamanho 307200 ou 307224 → **não** são ecrãs 640×480 crus.

| Ficheiro | Bytes | Fatoração útil |
|---|---:|---|
| `A01.RAW` | 200704 | **448×448** exato (também 256×784, etc.) |
| Quase todos os outros | variável | **não** divisíveis por 640/320/256 |

**Hipótese forte:** a maioria é **comprimida** (RLE ou pack isométrico), daí tamanhos “primos”. `A01.RAW` pode ser um caso sem compressão (quadrado 448). O decoder visual da IDE mostrou `C01.RAW` como cidade isométrica — pixels 8-bit, layout ainda opaco.

O EXE referencia até `a30` / `b30` / `c44`; no disco: A09, B20, C43. Não tratar os em falta como corrupção até ver o CD `RAW\`.

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

### Saves `.SAV` — tamanho **fixo 225 745**

Sem magic ASCII. Header como u32 LE:

| Ficheiro | u32@0 | u32@8 | u32@12 | Notas |
|---|---:|---:|---:|---|
| `FELIPE01.SAV` | **1024** | 50 | 54 | |
| `FELIPE02.SAV` | **1024** | 29 | 56 | |
| `LASTYEAR.SAV` | 16842752 (`00 00 01 01`) | 33 | 18 | snapshot de virada de ano |

`u32@8` **hipótese:** ano de calendário (o `C2.ENG` tem `January` / `BC` / `Week 1`). `u32@12` continua opaco (não é mês 1–12).

`tools/diff_sav.py` em FELIPE01 vs FELIPE02: **57 957 bytes (25.7%)** diferentes, 35 473 ranges. São **duas campanhas distintas**, não um par controlado (construir 1 casa). Não dá para mapear o struct de tile assim.

Densidade: os três saves ficam densos a partir de ~176 128. Folga até EOF = 49 617 B ≈ **40×40×31 + 17**. **Hipótese:** mapa de cidade 40×40 com ~31 bytes/tile no fim do save. Região ~4 096–48 000 está vazia em `LASTYEAR` e preenchida nos FELIPE — província / batalha / walkers.

Próximo passo de mapa: **um** save, uma ação, gravar outro (`F5`).

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
| `.SMK` | `SMK2` + u32 640, u32 480 em `INTRO.SMK` | Smacker 640×480. 14 clips (`INTRO`, `WINGAME`, `FIRE`, …) |
| `.WAV` | PCM; nomes batem com edifícios/combate | Miles digital (`DIG.INI` → `SBLASTER.DIG`) |
| `.AD` / `.OPL` | `CAESAR.AD`, `CAESAR.OPL` | Hipótese: fallback AdLib/OPL |

Miles AIL **3.02** (18-Jan-95) em `DIG.INI` / `MDI.INI` / `AILDRVR.LST`.

---

## 6. Comparação com Caesar III / Pharaoh

| | Caesar II (estes bins) | C3 / Pharaoh |
|---|---|---|
| Cor | 256 cores, paleta `.256` | 16-bit `.555` |
| Catálogo de sprites | **dentro do próprio `.PL8`** (count + records) | `.SG2`/`.SG3` separado do pixel dump |
| Tile cidade | PL8 com sprites **58×30** (`BUILD*`, `HOUSES*`, `CITYFIXT`) | Diamante **58×30** no `.555` |
| Fullscreen | PL8 640×480 ou `.RAW` | BMP/555 / painéis SG |
| Paleta | `.256` 768 B RGB | embutida / 16-bit |
| Engine | Watcom 32 + DOS4GW (`PS.EXE`) | Win32 C3 |
| Saves | 225 745 B fixos | outro layout |

**58×30 no C2 já é o diamante do C3.** Ancestral direto do tile; o *container* mudou (PL8 → SG2+555). Parsers de Augustus **não** abrem estes ficheiros, mas um conversor PL8-58×30 → atlas moderno é o atalho mais promissor.

`.RAW` não tem equivalente C3 óbvio.

---

## 7. Próximos passos (repriorizados)

1. **Par controlado de `.SAV`:** carregar um save, construir **uma** casa (ou um tile de estrada), gravar outro. Diff com `tools/diff_sav.py`. Confirmar ou matar a hipótese 40×40×31 @ ~176128.
2. **RAW:** tentar RLE simples (runs de `7F`) em `A04.RAW` (26 317 B). `A01.RAW` como 448×448 + paleta de um `.256` de UI.
3. **RLE de PL8** (flags bit 0) se aparecer em `RO2*` / `GM2*` — ainda não exercitado.
4. **`HELP.ENG`:** o magic `Helpfile` + offset 116008 não é a tabela `Textfile`; parsear só se precisarmos do texto de ajuda.
5. **Ghidra em `PS.EXE` (LE/Watcom)** depois de 1–4: loader PL8 e reader de `C2MODEL.DAT`.
6. CD original ainda útil para o `RESOURCE.CFG` de 283 B e para RAW A10+ se existirem.

Não priorizar Smacker/XMIDI (já há libs). Não priorizar crack/CD check.

Feito nesta fase: decoder PL8 0–4; `C2.ENG` (146 strings); `C2MODEL.DAT` cruzado com FAQ; header `.SAV`. Dumps de texto/números ficam em `notes/` (gitignored).

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
| E9 | `INTRO.SMK` = `SMK2` 640×480; XMI = `FORM`/`XDIR` | fato |
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
| H1 | Maioria dos RAW comprimida; A01 = 448×448 raw | hipótese |
| H2 | `C2MODEL` = tabelas de economia — **parcialmente confirmado** (E18–E21) | hipótese |
| H3 | `REGIONS.DAT` = mapa de províncias | hipótese |
| H4 | `M` em RESOURCE.CFG = origem HD/CD | hipótese |
| H5 | Dígito 2/3 nos PL8 de batalha = zoom | hipótese |
| H6 | `.SAV` u32@8 = ano BC; mapa cidade 40×40×31 B @ ~176128 | hipótese |
| H7 | `C2MODEL[790:990]` = ranks × dificuldade (`99` = slot vazio) | hipótese |

---

## 9. Fora de escopo

- Implementar engine Godot/C++ nesta fase.
- Copiar/redistribuir assets.
- Crack, bypass de CD, patch do EXE.
- Assumir que loaders de Caesar III abrem C2.
