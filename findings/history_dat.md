# HISTORY.DAT — trailer 4000 B do .SAV

Cópia 1:1 do ficheiro `history.dat` (VA string `0x90DD6`). `sav_write` `0x70174` lê 4000 B e anexa; `sav_read` escreve-os de volta. Ponteiro de I/O `[0xC4D10]` (alias com `REGIONS.DAT` no load). **Não** é o layout da tela Forum.

Parser de chunks: `app/city_map.py` (`SAV_HISTORY_BYTES = 4000`). Dump: `python tools/_hud_fields_dump.py`. Não commitar `.SAV` / `HISTORY.DAT`.

---

## 1. Forma

| | |
|---|---|
| Tamanho | **4000** = **200 × 20** |
| Record | 5 × `i32` LE @ `0x1025B0` |
| Reset | `history_dat_reset` `0x70A74` — zera os 5 dwords, `write_` 20 B × **200** |
| Append | `FUN_00070ae3` no wrap do ano (`FUN_0003fd3e`) — `lseek` `index*20`, escreve 1 record |
| Contador | chunk **338** `0x1025A4` — incrementa, cap **200** |
| Anel | chunk **336** `0x1025F0` — próximo índice, wrap a 0 se `≥ 200` |
| Flag reset | chunk **337** `0x102584` — 0 após reset |

`FUN_00070b76` lê o ficheiro inteiro (`ebx=0xFA0`).

---

## 2. Record (20 B)

Preenchido em `FUN_0003fd3e` **antes** do write (cópia dos vivos → `0x1025B0`):

| Off | VA scratch | Fonte viva | Chunk fonte | Achea último rec | Significado |
|---:|---|---|---:|---:|---|
| **+0** | `0x1025B0` | `0x102AB0` | **32** | **9521** (vivo 9561) | **população** no 31 Dec |
| **+4** | `0x1025B4` | `0x102AAC` | **28** | **28561** | **tesouro** |
| **+8** | `0x1025B8` | `0x102A5C` | **34** | **5209** | **Population Tax** do ano (`FUN_00056c9f`) |
| **+12** | `0x1025BC` | `0x102A34` | **35** | **2797** | **Industry Tax** do ano (`FUN_00056cec`) |
| **+16** | `0x1025C0` | `0x102AA0` | **25** | **−187** | **ano** signed (187 BC) |

C2.ENG a partir de **Treasury** [29]: skip 12 = `Population Tax`, 13 = `Industry Tax`, 14 Constructions, 15 Operating Costs, 16 Annual Tribute. Só os dois impostos entram no record.

Peace / Prosperity / Culture (pack slot 30, skip 8–10) **não** estão nestes 20 B.

---

## 3. Saves

| Save | recs ≠0 | 1º ano | último (pop, tesouro, taxP, taxI, ano) | count c338 |
|---|---:|---:|---|---:|
| **ACHEA23** | 36 | −222 | 9521, 28561, 5209, 2797, **−187** | 36 |
| 20230610 | 31 | −299 | 8172, 17847, 4149, 2403, −269 | 31 |
| FELIPE01 | 42 | −299 | 12700, 19098, 6195, 2996, −258 | 42 |
| FELIPE02 | 29 | −256 | 8435, 20187, 4833, 1171, −228 | 29 |
| LASTYEAR | 4 | −299 | 334, 10985, 86, 7, −296 | 4 |
| D / A / B / C | 0 | — | (assignment fresco) | 0 |

FELIPE01 trailer **==** `HISTORY.DAT` desta install (campanha activa). Achea é blob próprio.

Achea rec 35 casa com tesouro/impostos/ano do HUD; pop do record é o snapshot de **fim de −187**, o vivo (9561) já cresceu em January. D.SAV vazio = ainda não houve wrap de ano.

Como conferir no hex: últimos 4000 B do `.SAV`. Achea rec 35 @ `225745−4000 + 35*20` = **221745+700** = **222445**: `i32` pop, tesouro, tax, tax, ano.

---

## 4. O que não é

- Não é lista de províncias / mensagens do Imperador.
- Não é `forum_x.gd8` (3040 B; `ebx=4000` no load é coincidência).
- Slots 200+ não existem; o anel recomeça no 0.
