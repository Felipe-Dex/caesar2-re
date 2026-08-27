# Caesar II — Fase 1 (exploração)

**Última atualização:** 2026-08-25 (rev. 2 — `PS.EXE` + inventário real via PowerShell)  
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

Paleta `.256`: **exatamente 768 bytes** = 256 × RGB (3 bytes, sem alpha). Ex. `AHOUSE.256` começa `00 00 00 00 00 2A …` (VGA-ish).

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

Pixels a seguir ao header, nestes samples: **1 byte = índice de paleta**, `width×height` bytes (sem RLE). Flags `0x0002` ↔ bitmap simples. RLE/ISO da doc pl8image ainda **não** foram exercitados nestes headers (provável nos packs de batalha `RO2*`, `GM2*`, etc.).

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

### `C2.ENG` (31 876 B) — strings UI

```
0000  "Textfile" + 8 zeros
0010  tabela de u32 offsets (LE) para C-strings
```

Amostras (formato, não dump completo): `Options`, `Speed`, `Help`, `Prima Cohors`, `Latium`, `Romans`, `Citizen`, `Caesar II - Version 1.1`, `Reservoir`.

`HELP.ENG` (455 194 B) — help longo; mesmo family **hipótese**.

### `C2MODEL.DAT` (4360 B = **1090 × int32 LE**)

Início: `20, 15, 10, 5, 2, 20000, 15000, 12000, 7000, 5000, 2000, 500, 250, 150, 100, 10, 16, 24, 35, 8`, …

**Hipótese:** tabelas numéricas de regras (custos, população, velocidade). Não é gráfico. Candidato nº 1 a “economia/edifícios” fora do EXE.

### `REGIONS.DAT` (158 400 B)

Sem ASCII; bytes tipo mapa/índices (`15 98 11 17…`). **Hipótese:** mapa de províncias / terreno da camada império. 158400 = 396×400 ou 180×880 — não cravar geometria.

### `HISTORY.DAT` (4000 B, data 2011)

int32s mistos (incluindo negativos `D5 FE FF FF` = −299). **Hipótese:** histórico de campanha / high scores do jogador, não do CD.

### `DISCS.DAT` (256 B) + `DISCS.IX` (1996 B)

Referenciados via `cd.dat` no EXE. **Hipótese:** layout de CD / catálogo de ficheiros no disco.

### `FORUM_X.GD8` (3040 B)

Começa zeros. String no EXE junto de `forumbit.pl8`. **Hipótese:** geometria/overlay do fórum, não texto.

### Saves `.SAV` — tamanho **fixo 225 745**

| Ficheiro | MD5 (não são cópias) | Header (primeiros 16 B) |
|---|---|---|
| `FELIPE01.SAV` | 9E5548… | `00 04 00 00  00 00 00 00  32 00 00 00  36 00 00 00` |
| `FELIPE02.SAV` | 67E93A… | (não dumpado neste passo) |
| `LASTYEAR.SAV` | 1F39CE… | `00 00 01 01  00 00 00 00  21 00 00 00  12 00 00 00` |

EXE pede `caesar2.sav` e `*.sav` / `lastyear.sav`. Sem magic ASCII. Diff de dois saves com uma ação (construir 1 casa) é o próximo passo de mapa de campos.

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

1. **Decoder PL8 mínimo** (só leitura, no repo de notas): header + sprite 0 de `AHOUSE.PL8` + `AHOUSE.256` → PNG. Se 182×132 fizer sentido visual, o layout está fechado. Depois `HOUSES1.PL8` (58×30 × 106).
2. **Diff de saves:** `FELIPE01.SAV` vs `FELIPE02.SAV` (já existem, hashes diferentes, mesmo tamanho). Mapear u16/u32 no header (`32`/`36` vs `21`/`12` — hipótese ano/mês ou mapa).
3. **`C2MODEL.DAT`:** dump dos 1090 int32 e cruzar com custos do manual (`C2MANUAL.DOC` está na pasta).
4. **`C2.ENG`:** extrair a tabela de strings completa para um índice de UI (não precisa do EXE).
5. **RAW:** tentar RLE simples (runs de `7F`) em `A04.RAW` (26 317 B) e ver se descomprime para um retângulo 8-bit. `A01.RAW` como 448×448 + paleta de um `.256` de UI.
6. **Ghidra em `PS.EXE` (LE/Watcom)** só depois de 1–5: procurar o loader que lê u16 width/height no offset 8 do PL8.
7. CD original ainda útil para o `RESOURCE.CFG` de 283 B e para RAW A10+ se existirem.

Não priorizar Smacker/XMIDI (já há libs). Não priorizar crack/CD check.

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
| H1 | Maioria dos RAW comprimida; A01 = 448×448 raw | hipótese |
| H2 | `C2MODEL.DAT` = tabelas de economia | hipótese |
| H3 | `REGIONS.DAT` = mapa de províncias | hipótese |
| H4 | `M` em RESOURCE.CFG = origem HD/CD | hipótese |
| H5 | Dígito 2/3 nos PL8 de batalha = zoom | hipótese |

---

## 9. Fora de escopo

- Implementar engine Godot/C++ nesta fase.
- Copiar/redistribuir assets.
- Crack, bypass de CD, patch do EXE.
- Assumir que loaders de Caesar III abrem C2.
