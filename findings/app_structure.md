# Host — plano de estrutura (`app/`)

Viewer Python **descartável** (Phase 1). Não é o motor Godot/C++. O objetivo deste doc é **não misturar boot, assets, estado, sim e draw** no mesmo sítio — e usar **os mesmos nomes das funções do EXE**, para um port futuro ser óbvio.

Como testar o pulso: `app_sim_phase.md` + `app_tick.md`. Quem corre em cidade / província / forum: `view_modes.md`. New Game = **dois** modos (City Only / Career) × **cinco** skills (`Novice`…`Impossible!`), não um load de SAV: `new_game.md`. Host City Only: `city_only.md`.

Não há `app/ARCHITECTURE.md`. Este ficheiro é o mapa.

---

## 1. Como está hoje

`python -m app` → `app/__main__.py` resolve o install, chama `boot.run_boot`, depois ou sai (`--check` / `--map-preview` / `--sim-smoke`) ou abre `window.show`.

### Módulos (árvore actual)

```
app/
  __main__.py      CLI + smoke / preview
  config.py        CAESAR2_PATH / config.local.json
  boot.py          c2_main @ 0x10010 — ordem de stubs + carga
  assets.py        PL8 / .256 / C2.ENG (decoders em tools/)
  audio.py         2 s de RAW (não é Miles)
  city_map.py      SavChunk 13 + render_iso (LUT + zoom)
  walkers.py       SavChunk 8 + overlay LTLMEN
  city_sim.py      city_sim_phase 0x3F60C (slots 1–0x50 reais)
  walker_tick.py   walkers_tick 0x459D0
  calendar.py      data HUD (chunks 25/26)
  new_game.py      start_city_assignment City Only + city_map_generate
  place.py         stamp Tent/Road/Clear + tesouro (v1)
  city_chrome.py   INT_CITY sidebar + hitboxes 3×5
  city_overlay.py  overlay-filter 0x98B34 + Query stub
  sim.py           um pulso: phase depois walkers
  window.py        tkinter 640×480 + teclas + câmara + cache iso
```

`BootContext` é o saco de sessão: install, arte do título, `CityMap`, lista de `Walker`, `SimState`. Serve. Não é um ECS.

### Quem desenha

| Superfície | Módulo | EXE |
|---|---|---|
| Título (`backgrnd.pl8`) | `assets.pick_boot_image` + `window._fit` | `title_screen` `0x5D37F` |
| Sprite solto (tecla 2) | `assets.load_pl8_image` | debug do host, não é view |
| Mapa iso 80×80 | `city_map.render_iso` | `city_map_draw` `0x360F7` / terrain `0x361DC` |
| Pessoas | `walkers.overlay_walkers` | `city_map_draw_walkers` `0x364A0` |
| Viewport 640×480 + HUD de debug | `window.crop_viewport` / `compose_frame` | `video_init` `0x28341` + blobs de HUD **não** portados |
| Província / forum / actors26 | **não existem no host** | `province_map_draw` / `forum_view` |

`window.py` **não** é um game loop a 60 Hz. É `title_input_wait` `0x2E7B1`: espera tecla, redesenha. Sem `sim_tick_due`, sem `video_blit_dirty`.

### Quem faz tick

| Tecla / CLI | Função | Ordem EXE |
|---|---|---|
| **Space** / **T** | `sim.on_sim_step` | `city_sim_phase` **depois** `walkers_tick` (igual a `view_frame`) |
| **E** | `city_sim.evolve_all_rows` | **atalho do host** — 80 filas; não é um pulso |
| `--sim-smoke` | selftest + evolve80 | sem janela |

Um Space = **um** slot `[0x1026A8]`, não o dump `0xD6`. Wrap `> 0xD6` avança o mês em `calendar` (`economy_recompute` stub). Relógio de walkers (`mod64`) vive em `walker_tick._CLOCK` (global). `actors26_tick` **não corre**.

### Teclas

| Tecla | Efeito | Notas |
|---|---|---|
| Esc / Q | sair | |
| **1** | título `backgrnd.pl8` | sai do mapa |
| **2** | 1º tile `CITYFIXT` | debug |
| **3** | mapa iso + walkers | entra `map_mode` |
| Space / T | 1 pulso | câmara não muda |
| E | evolve80 | host-only |
| A | 2 s `A01.RAW` | |
| setas / arrastar | pan | só no mapa; passo 96/48/24. Com Housing/Roads/Clear o arrasto é borracha, não pan |
| + − / ] [ / Z / roda | zoom 0/1/2 | PL8 ou scale nearest |
| Home | recentrar | |

`--new --city-only` abre **já no mapa** (não no título). Load `.SAV` continua a nascer no título; **3** entra no mapa.

Não há tecla cidade↔província, Forum, ou “mês inteiro”.

### O que é stub

Já nomeado, sem efeito (ou de propósito skip):

- Quase todos os slots de `city_sim_phase` fora de `1…0x50` (wipes `0x51–0x54` **não** correm — destruiriam `+15`).
- `economy_recompute`, `actors26_tick`, spawn de walkers a partir da província.
- Estado walker **9** (seek), path-fail `0x2B54A` / `0x2BA63`, scores de casa `0x4A7FF`, rally chunks 20/21.
- `smk_play` intro, Miles, `sim_tick_due`, HUD real, cursor, chrome Forum.
- Views província / forum / batalha.
- **New Game Career** — `--career` / REGIONS / actors26. City Only marco 1 já existe (`--new --city-only`). Detalhe: `new_game.md` · `city_only.md`.

Detalhe: `app_sim_phase.md`, `app_tick.md`.

### Quem está gordo

| Ficheiro | ~linhas | Porquê |
|---|---:|---|
| `walker_tick.py` | 800 | **um** `walkers_tick` — deixar junto |
| `city_sim.py` | 600 | dispatcher + evolve/merge — deixar junto |
| `city_map.py` | 540 | SAV I/O **e** LUT/draw — candidato a `sav.py` |
| `window.py` | 420 | host + teclas + câmara + cache iso — **o gordo a partir** |
| `sim.py` | 60 | já é só o pulso — **não partir** |

---

## 2. Como o EXE está organizado

Fonte: `view_modes.md`, `ghidra_walk.md`, `ghidra_sim.md`.

```
c2_main 0x10010
  boot (cfg, gfx, video, Miles, intro.smk, title)
  enter_view_mode 0x3351B          # kind 0 cidade / 1 província / 2 batalha
  loop:
      view_frame 0x3CF9A           # se view_submode==0
      se view_submode==1 → forum_view 0x59A15   # NÃO é view_frame
```

**Cidade e província são a mesma pulse.** Trocar a view só muda gfx, SFX e o ramo de draw. Walkers da cidade continuam a andar no mapa provincial. Forum **congela** o sim (`forum_frame` = input + blit).

### `view_frame` — draw vs sim

Cada frame de ecrã: timer + input + **draw** + HUD + blit.

O bloco de **sim** só corre se `sim_tick_due` `0x3E4B9` = 1 (1× ou 4× catch-up):

```
anim_phase_clocks → rng_clock → city_sim_phase → walkers_tick → actors26_tick
                         wrap >0xD6 → calendar_advance
```

Depois, **draw** (não é tick):

- kind 0 → `city_map_draw` `0x360F7`
- kind 1 → `province_map_draw` `0x39013` (tiles 60×60 + `province_draw_actor26`)

### Mapa ficheiro nosso ↔ EXE

| EXE | VA | `app/` hoje |
|---|---|---|
| `c2_main` | `0x10010` | `boot.run_boot` + `__main__` (CLI) |
| `load_file_cfg` | `0x2456E` | `assets.read_resource_cfg` |
| `gfx_load_boot_assets` | `0x10E89` | `assets.verify_boot_assets` |
| `video_init` | `0x28341` | `window.show` (tkinter) |
| `miles_init` | `0x11758` | `audio` (skip / RAW) |
| `smk_play` | `0x5AB3D` | ficheiro existe? |
| `title_screen` | `0x5D37F` | tecla **1** + boot image |
| `title_input_wait` | `0x2E7B1` | `window` mainloop |
| `start_city_assignment` | `0x1049B` | `new_game.start_city_assignment` — **só City Only** |
| `init_new_city` | `0x10565` | mesmo módulo (subset; sem REGIONS / economy) |
| `apply_regions_map` | `0x706C3` | — (`REGIONS.DAT` 44×3600) **Career** |
| `city_map_generate` | `0x65809` | `new_game.city_map_generate` (relva+rio; não zeros) |
| `sav_read` / `sav_write` | `0x7024A` / `0x70174` | só **read** via `load_*_from_sav` |
| `enter_view_mode` | `0x3351B` | **ausente** (já nasce “na cidade”) |
| `view_frame` | `0x3CF9A` | **não existe**; Space ≈ só o pulso |
| `sim_tick_due` | `0x3E4B9` | host ignora (tecla = due) |
| `city_sim_phase` | `0x3F60C` | `city_sim.city_sim_phase` |
| `walkers_tick` | `0x459D0` | `walker_tick.walkers_tick` |
| `actors26_tick` | `0x45A7A` | stub (skip) |
| `calendar_advance` | `0x3FBCF` | wrap em `city_sim` + `calendar` |
| `city_map_draw` | `0x360F7` | `city_map.render_iso` + overlay |
| `province_map_draw` | `0x39013` | — |
| `forum_view` / `forum_frame` | `0x59A15` / `0x3D5AA` | — |
| SavChunk 13 tiles | `0xE2FBC` | `city_map.CityMap` |
| SavChunk 8 walkers | `0x1107A4` | `walkers.Walker` |
| SavChunk 7 actors26 | `0x114500` | — |

`sim.on_sim_step` é o pedaço de sim do `view_frame`, não o frame inteiro. Não fingir que `window.py` é `view_frame`.

---

## 3. Estrutura alvo (viewer descartável)

Camadas, **não** pastas obrigatórias no dia 1. Um ficheiro por função EXE enquanto couber.

```
boot/config  →  assets (PL8/256)  →  sav/chunks  →  world state
                         │                              (city tiles, walkers, actors26)
                         │         start_city_assignment / apply_regions_map
                         │         (2 modos × 5 skills; um city_map_generate — new_game.md)
                         │         (só se NÃO houver sav_read)
                         ↓
                       sim          (city_sim_phase, walkers_tick, calendar)
                         ↓
                       views        (title, iso city; depois province, forum)
                         ↓
                       host window  (tkinter / video_init)
```

Regra: **sim não importa Pillow**. View não avança fase. Host não conhece bytes de tile.

### Árvore proposta (nomes = EXE)

```
app/
  __main__.py           # CLI — fica magro
  config.py             # já está
  boot.py               # c2_main (stubs + load)
  assets.py             # gfx_load_* ; decoders ficam em tools/
  audio.py              # miles stub

  sav.py                # NOVO quando doer: walk_sav_chunks, load_chunk_sizes, pick_save
  new_game.py           # City Only já está; Career / apply_regions_map depois — city_only.md

  city_map.py           # estado 80×80×20 + render_iso (draw da cidade)
  walkers.py            # records + overlay (draw)
  actors26.py           # SÓ quando actors26_tick existir

  city_sim.py           # city_sim_phase + evolve (já extraído)
  walker_tick.py        # walkers_tick (já extraído)
  calendar.py           # já extraído
  sim.py                # pulso view_frame: phase → walkers → (depois actors26)

  window.py             # video_init + bind teclas + blit
  city_iso.py           # NOVO: cache zoom / ensure_map / câmara do mapa
                        # (stand-in de city_map_draw; não criar views/ ainda)
  # title.py            # só se _fit + teclas 1–2 incomodarem
  # province.py         # province_map_draw — depois
  # forum.py            # forum_view — depois, loop sem sim
```

`BootContext` continua a ser o saco. Quando houver `view_kind`, um `int` 0/1/2 chega — não uma hierarquia de ViewController.

### O que partir de `sim.py` / `window.py`

**`sim.py` — não partir.** Já é o orquestrador do pulso (~60 linhas). Quando `actors26_tick` existir, acrescentar uma linha aí, com esse nome.

**`window.py` — partir o mapa, não o tkinter.** Sair para `city_iso.py` (nome curto; no port = `city_map_draw`):

- cache `terrain_cache` / `map_cache` / zoom PL8
- `ensure_map`, `paint_walkers`, fallback scale
- `center_camera` / `retain_center` / `crop_viewport` (viewport pode ir junto)

Fica em `window.py`: `Tk()`, `compose_frame` (HUD debug), `on_key`, bind rato, chamar `sim.on_sim_step`.

### O que **não** partir ainda

- `walker_tick.py` em type_fn / state_fn / step — é **uma** função EXE.
- Slots stub de `city_sim.py` em 20 ficheiros. Um `slot_name` + `if 1…0x50`.
- `render_iso` para fora de `city_map.py` (LUT vive com o tile).
- Pacote `views/` com um só módulo.
- `enter_view_mode`, HUD `0x6189D`, cursor, `sim_tick_due` em tempo real.
- Godot, C++, plugin, ECS, pasta `engine/`.

---

## 4. Ordem de extração (depois de `city_sim.py`)

Passos pequenos. Um por vez. Sem big-bang. **Não fazer agora** — só a ordem.

1. **`city_iso.py` a partir de `window.py`**  
   Cache + `ensure_map` + overlay. Teclas 3 / zoom / pan / refresh-após-Space passam a chamar este módulo. Teste: tecla 3 + zoom + Space ainda redesenha casas.

2. **`sav.py` a partir de `city_map.py`**  
   `walk_sav_chunks`, `load_chunk_sizes`, `find_saves` / `pick_save`. `city_map`, `walkers`, `city_sim`, `calendar` importam daqui. Teste: `--sim-smoke` + tecla 3 no mesmo SAV.

3. **`start_city_assignment` / `apply_regions_map` (New Game ×2 modos ×5 skills)**  
   Depois de `sav.py` (a tabela de 500 diz o que encher), **antes** do forum. **Duas** CLIs de modo, não uma: `--new --city-only` (406=1, sem pick) e `--new --career --region 15` (406=0 + REGIONS). Skill = chunk **16** 0…4 (default INF = Novice). O mapa do império espera (7). Detalhe: `new_game.md`. Teste Career Normal: Achaea pid 15 → chunk 14 carimbado + cidade gerada (não zeros) + tesouro **12000** + ano −300 + walkers 0.

4. **`actors26` só com o tick**  
   `actors26.py` (chunk 7) + uma linha em `sim.on_sim_step` **depois** de `walkers_tick`. Sem isto o mapa provincial fica morto (`view_modes.md`). Sem viewer provincial neste passo.

5. **`view_kind` mínimo no host**  
   0 = iso cidade (já temos). Tecla futura ↔ `switch_to_province` / `switch_to_city`. Província pode ser ecrã “não implementado” até haver `province_map_draw`. Não abrir Forum aqui.

6. **`province.py` (`province_map_draw`)**  
   Chunk 14 + sprites actor26. O pulso **não muda** — mesmo `on_sim_step`. Walkers da cidade não se desenham. Chunk 14 pode já vir de (3), não só de SAV.

7. **`forum.py` (`forum_view`)**  
   Loop **sem** sim. Chrome / painéis quando `forum.md` tiver um kind útil. Pick *Select a Highlighted Province* mora aqui. Último de propósito.

Se (1) ou (2) for o único que dói esta semana, parar aí. (3)–(7) esperam Ghidra, não pastas vazias. Sem (2) não fazer (3).

---

## 5. Honestidade (não over-engineer)

Isto é um **host para lançar e ver o SAV**. New Game sem placement continua a ser um viewer (relva + província). Vai para o lixo quando Godot 4 ou C++ abrir os mesmos ficheiros a partir de `CAESAR2_PATH`.

- Não criar camada “por se acaso”. Extrair quando um ficheiro tiver **duas** razões de mudar (draw vs I/O, host vs mapa).
- Nomes de função = Ghidra (`city_sim_phase`, `walkers_tick`, `view_frame`, `forum_view`). O port copia o nome, não um `GameManager`.
- `sim.py` = metade sim de `view_frame`. `window.py` ≠ `view_frame`. Forum ≠ este loop.
- Space/T como gate é suficiente. Relógio de 50 ms / catch-up 4× é trabalho de motor, não deste viewer.
- Um stub que **não crasha** e tem o nome do slot vale mais que um framework de plugins.
- `tools/` continua a ser o sítio dos decoders. `app/` só chama.

---

## 6. New Game (dois modos × cinco skills, não um load)

Pergunta: *“e para criar um novo jogo?”* = **Start a New Game** no título, depois **New Game Options** no `C2.ENG` — **não** um IP novo, e **não** um só assignment.

O diálogo (`[38]` / `[42]`; título `New Game Options`) tem **dois** controlos oficiais — não inventar um terceiro:

| Controlo | Labels | Byte SAV |
|---|---|---|
| **Campaign?** | `YES -- City, Province, Empire` / `NO -- City-only Mode` | chunk **406** `[0x9CE81]` |
| **Choose a Skill Level** | `Novice` · `Easy` · `Normal` · `Hard` · `Impossible!` (0…4). **Sem** *Very Hard*. Cabeçalho **não** é a palavra `Difficulty` | chunk **16** `[0x9CE80]` |

Mais no mesmo diálogo: `Start this Game` + `Click right or ENTER to accept`. `Your Name` está no pack, entre Campaign e o menu do título — **não** pinado como terceiro eixo deste ecrã. In-game **Caesar II - Game Options** reusa o picker de skill (setas `0x348CF` / `0x348EA`).

| Modo | Menu | Flag 406 | Extra |
|---|---|---|---|
| **City Only** | `NO -- City-only Mode` | **1** | sem pick, pid **223** = 0; sem promoção; sem `actors26_tick`; Oracle só Prosperity/Culture; spawn tipo 3 na cidade lê C2MODEL `[75:91]` |
| **Career** | `YES -- City, Province, Empire` | **0** | rank Citizen…Caesar; pick **Select a Highlighted Province**; `REGIONS.DAT`; tribute / EMPIRE MAP; `FUN_00010529`; Need = C2MODEL `[790:990]` × (16, rank) |

2 × 5 = dez flags; **um** `city_map_generate`. O EXE, depois do título: se `[0xCCAFF0]==0` → `start_city_assignment` `0x1049B` → `init_new_city` `0x10565` (ano −300, tesouro `C2MODEL[5:10]` indexado pelo **16**, pools vazias, relva+rio). **Não** escreve `.SAV` aí. Load = `sav_read` e **salta** a init. Default INF: 16=0 Novice, 406=1 City Only.

**Achea** (`ACHEA23.SAV`): Career a meio, **Normal=2**, Apparitor=2 → Oracle Need **30/40**. **D.SAV**: City Only, **também Normal=2** (tesouro 10899 ≠ Easy 15000), pid 0. A/B/C/LASTYEAR = City Only **Novice=0**.

O host já faz **City Only** (`--new --city-only`, skill 0…4). Sem placement, o marco honesto é **ver relva gerada**. Career continua ausente.

Plano completo (labels, o que a skill muda, camadas): **`new_game.md`** §1.0 / §1.8. Fatias até jogável: **`city_only.md`**.

Irmãos: `app/README.md` (como correr) · `app_sim_phase.md` · `app_tick.md` · `view_modes.md` · **`new_game.md`**.
