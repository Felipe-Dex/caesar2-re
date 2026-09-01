# Forum / Império

Tela de carreira (não o prédio Aventine/Janiculan na cidade). Entrada, dados e o que um stub precisaria. Sem UI completa nesta sessão.

Arquitectura vs cidade/província (quem faz tick, dois loops): **`findings/view_modes.md`**.

---

## 1. Como se entra

`[0x102AA4]` **`view_submode`** (SavChunk **370**):

| Valor | Quem trata | Tela |
|---:|---|---|
| 0 | `view_frame` | cidade / província / batalha |
| **1** | `c2_main` → **`forum_view` `0x59A15`** (era `FUN_00059A15`) | **forum / império** |
| 2 | early RET no pulse; `FUN_000555e1` grava 2 | ? |
| 3 | `FUN_00010529` (passo de carreira / ano) | nova city |
| 4 | `combat_mode4_step` | combate |

`enter_view_mode` `0x3351B` **não** abre o forum. Ele só escolhe city / province / battle via `[0x117A8D]` (chunk 0). O forum é um **submodo** que derruba o loop de `view_frame` (`c2_main`: se `view_submode != 0` → `session=1`; depois se `== 1` chama `forum_view`).

Quem **grava 1** (amostra):

| Função | Quando |
|---|---|
| `FUN_00033d21` | Depois de um diálogo; chamado de `FUN_0005977b` quando o rating despenca (`[0x102A58] < -2`) |
| `FUN_00054dc5` | Todo mês (`calendar_advance`); se tesouro `< 0`, countdown `[0x102A6C]` → força forum |
| `FUN_00058d31` | Caminho de UI/combate (grava `view_submode = [0xC459C]`, às vezes 1) |

Clique “Forum” no chrome da cidade ainda não foi o `CALL` isolado. Candidato extra: `0x289B2` → **`forum_panels` `0x338F9`** (função sem bounds no Ghidra).

No jogo: botão / tecla do Forum (manual: Forum) ou recado do Imperador. HUD da cidade some; entra a tela com Ratings / Scribe / Empire.

---

## 2. `forum_view` `0x59A15`

Corpo curto `0x59A15`–`0x59A70`:

```
[0xCCB09] = 0
FUN_0001239c()          ; Miles / handles de som
forum_view_setup()      ; 0x59A71
[0xC459C] = 0
FUN_000135a4()
while [0xC459C] == 0:
    forum_frame()       ; 0x3D5AA input + blit (não é view_frame)
FUN_000121a9()
FUN_0005a9fc()          ; teardown + palette
```

`forum_view_setup` `0x59A71` (era `FUN_00059a71`): `palette_restore`, `FUN_00028db0`, `[0x117A60]=0x32`, **`FUN_00059fc2`** (moldura 16×16: `FUN_00059ff8` + `FUN_0005a213`), blit de string, `[0xCCB07]=1`, `video_blit_dirty` (Ghidra marca noreturn — **falso**).

Isto é o **loop fino** (`forum_frame` `0x3D5AA`). A UI rica (vários painéis) está em **`forum_panels` `0x338F9`** + **`forum_panel_draw` `0x33B73`**.

---

## 3. Painéis (`forum_panel_draw` `0x33B73`, kind `[0x117A5C]`)

`forum_panels` `0x338F9`: carrega arte (`FUN_0005d308`), desenha o kind atual, loop `forum_panel_input` `0x33B06`. Clique lê um hitmap 80-wide em `regions_or_history_ptr + 120000` e troca `[0x117A5C]`.

| `[0x117A5C]` | O que o C mostra | Dados |
|---:|---|---|
| 0 / default | 12× `FUN_0003ddf7` (rótulos) | — |
| **1** | tesouro + `FUN_0005d892` / `FUN_0005dbad` (lê o ano) | ratings / números |
| 2 | outro painel (rank `[0x102578]`) | — |
| **3** | `history_dat_read` `0x70B76` + `FUN_0005f18e` / `FUN_0005f2e0` | carreira / `history.dat` |
| 4 | texto + valores | — |
| 5 | `load_file` (+ `FUN_00057a47` se o hit for 5) | SMK / evento? |
| 6 | comércio | — |
| **7** | 8 linhas de **`0xD2AEC`** (chunk **335** goods) | província / indústria |
| 8 | saldo `[0x102A84]` | — |
| 10 / 11 | load extra / `FUN_0005f8b8` | — |

`FUN_0005d308` (só de `forum_panels`): 3× `load_file` + 12× `FUN_0003ddf7` — casa com **`forum.pl8` / `forum.256` / `forumbit.pl8`** e doze rótulos (meses?).

---

## 4. Ficheiros que o forum lê

| Ficheiro | Tamanho / papel | Conf |
|---|---|---|
| **`forum.pl8`** + **`forum.256`** | chrome da tela | high (string @ `0x90D27`, xrefs em `FUN_00033b73` / `FUN_0005d308`) |
| **`forumbit.pl8`** | bits / overlay | high (`FUN_0003d97f`) |
| **`forum_x.gd8`** | 3040 B; load `ebx=4000` | med — geometria, não texto |
| **`empire.pl8`** / `empire.256` / `e_parts2.pl8` | mapa do império | med (lista do boot, não aberto aqui) |
| **`forum1.xmi` / `forum2.xmi` / `forum3.xmi`** | música | high (`c2_main` já toca `forum1.xmi` no boot) |
| **`forum.wav`** | SFX | high |
| **`C2.ENG`** | strings da tela | high (abaixo) |
| **`REGIONS.DAT`** | 44 × 3600 → `apply_regions_map` `0x706C3` → chunk 14 (60×60×8) | high para o **mapa de província**; hitmap `+120000` no forum ainda **opaco** |
| **`HISTORY.DAT`** | 4000 B, trailer de todo `.SAV` | high como campanha; **não** é o layout da tela |

`REGIONS.DAT` o que um stub de forum **precisa** para o mapa: 44 records (províncias do império), cada um 60×60 bytes que viram tiles de província (Your City `0x92`, towns, sea lanes — `province_map.md`). Lista de províncias / mensagens do imperador / promoção **não** saem desse decode 60×60; moram em globais + `HISTORY.DAT` + strings.

---

## 5. `C2.ENG` (slots da tabela de 146)

| Slot | Texto | Uso óbvio |
|---:|---|---|
| 24 + packed | January…December, BC, AD | data (HUD e forum) |
| **28** | `CLEAR FORUM` | botão / ação |
| 29 | `Treasury` | painel 1 |
| 30 | `The career of ` | cabeçalho |
| **31** | `Your Ratings` | kind 1 |
| **32** | `Your Scribe` | mensagens |
| **33** | `The Empire` | kind mapa |
| **34** | `The Legion` | kind militar |
| 35 | `Industry` | kind 7 |
| 36 | `Plebeian Tribune` | cargo |
| 66 | ` - Forum Clerk` | query / cargo |
| 69 | `Promotion!!!` | kind 5 / `promote.smk` |
| 72 | `Annual Summary` | virada de ano |
| 99 | `The Empire Expands!` | evento |

Ícones grandes `AFORUM.PL8` (182×132) são o **menu de construção** do fórum na cidade, não esta tela.

---

## 6. Stub mínimo (não feito)

Ler `C2.ENG` [31]–[34] + data (`app/calendar.py`) + tesouro chunk 28. Dump dos 44 nomes de `REGIONS` ainda não existe (o DAT não tem ASCII). Não desenhar `forum.pl8` hoje.

---

## 7. Ainda opaco (lista velha — ver §8–§9)

- Qual tecla / hitbox da cidade seta `view_submode=1` no clique **directo** — **parcial em §8**.
- Significado exato do hitmap @ `ptr+120000` (GD8? fatia de REGIONS?).
- Qual kind é “mensagem do Imperador” vs “promoção” vs “scribe”.
- `HISTORY.DAT` campo-a-campo — **fechado** em `findings/history_dat.md`.
- `FUN_00059c86` está vazio no decompile (stub / bounds).

---

## 8. Hitboxes da cidade: overlay (fechado) vs Forum (stores)

Scan do LE relocado: **só dois** `mov [0x102AA4], 1` no EXE:

| VA do store | Função | Quando |
|---|---|---|
| `0x33d78` | `FUN_00033d21` | Depois do loop de diálogo (`[0xC459C]`). Único `CALL` = `0x59892` em `FUN_0005977b` (rating `< -2`). |
| `0x54e2e` | `FUN_00054dc5` | Tesouro `< 0`; countdown chunk **251** → força forum. |

Mais: `0x58f29` faz `mov [0x102AA4], EAX` com EAX = `[0xC459C]` (1 quando o loop sai), **só se** `param ∈ 0x7D…0x84` **e** `[0x102C4C]==2`. `CALL 0x58d31` no código é só o thunk em `0x58d27` (wrapper imediatamente acima). Não há ponteiro `dword` para `0x58d31` / `0x33d21` na tabela de 18 B do palette.

**Overlay (sidebar, acima do minimapa)** — tabela 18 B a partir de `0x98B34`, campo `u16 id` + `u32 handler`:

| id | Handler | C2.ENG (slot **52** + skip) | Achea |
|---:|---|---|---|
| 0 | `0x32AE3` | Geography | — |
| 1 | `0x32AF7` | Land Value | — |
| 2 | `0x32B0A` | Water | 20230610 = 2 |
| 3 | `0x32B13` | Security | — |
| **4** | `0x32B1C` | **Unrest** | **chunk 1 = 4** (print) |
| 5 | `0x32B25` | Tax Coverage | — |
| 6 | `0x32B2E` | Entert'ment | — |
| 7 | `0x32B37` | Education | — |
| 8 | `0x32B40` | Illness | — |
| 9 | `0x32B49` | Markets | — |
| 10 | `0x32A9EF` | Cancel (skip 10) | — |

Chunk **1** `0x117A59` é o id. HUD `FUN_00061c56`: `EAX=0x35`, `EDX=[0x117A59]`. `city_view_reset` zera (Geography). Dispatch de tint `PTR_LAB_00099b3c`[id].

Esta tabela **não** tem handler que grave `view_submode=1`. É palette de reports, não o botão Forum/Império.

City ↔ Province no chrome: `switch_to_city` `0x3168C` / `switch_to_province` `0x3179D` (bloco ~`0x337A7`–`0x338F1`). Mexem em `view_kind` `[0x117A8D]`, **não** no submodo forum.

**O que falta para o clique Forum:** o CALL/hitbox que chega a `FUN_00033d21` ou ao wrapper `0x58d10` a partir do chrome (não é overlay id 0–9, não é `switch_to_*`). Candidato ainda: tecla / rect hardcoded / ponteiro que o Ghidra não cortou. `FUN_00058c87` é **fila de recados** (16 slots), não o store do submodo.

Como conferir overlay: Achea sidebar **Unrest** ⇔ byte @ SAV off **1** = `04`. Trocar overlay no jogo e regravar deve mudar só esse byte.

---

## 9. HISTORY (apontador)

Trailer 4000 B = 200 × 20 B. Campos nomeados em `findings/history_dat.md`. Painel Treasury (`FUN_0005d892`) usa os mesmos dwords de imposto (skip 12–16 a partir de `Treasury`).
