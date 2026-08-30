# Caesar II — v0 host (`app/`)

Disposable Python window so you can **launch today** while Ghidra keeps walking `PS.EXE`.
This is **not** the future engine. Prefer **Godot 4 or C++** once the sim map is named.
Godot was **not on PATH** on this machine, so v0 is **Python 3 + Pillow + tkinter** (stdlib window).

Julius-style: the program **reads your install**. It never copies `.PL8` / `.SMK` / `.RAW` / `.EXE` into git.

---

## Como apontar o jogo / Point at Caesar II

Pick **one** (first match wins):

1. Environment: `CAESAR2_PATH=C:\Users\Felip\OneDrive\Games\Caesar2`
2. Local file (gitignored): copy `config.example.json` → `config.local.json` and set `caesar2_path`
3. CLI: `python -m app --game "C:\Users\Felip\OneDrive\Games\Caesar2"`

On this PC a `config.local.json` already points at the OneDrive install. Do not commit it.

Need: a legal **1.1A** flat folder with `PS.EXE`, `C2.ENG`, `CITYFIXT.PL8`, `INTRO.SMK`.

---

## Como rodar / How to run

From the **repo root** (`caesar2-re`), same Python as the tools:

```text
C:\Users\Felip\AppData\Local\Programs\Python\Python314\python.exe -m app
```

Or, if that `python` is already on PATH:

```text
python -m app
```

Check only (no window — good for a quick smoke test):

```text
python -m app --check --no-audio
```

Pillow is already required by `tools/decode_pl8.py`. tkinter ships with this Windows Python. No Godot / pygame install.

Keys in the window: **Esc** quit · **1** `backgrnd.pl8` · **2** first `CITYFIXT` tile · **3** 80×80 city map + people (SavChunk 8) · **+** / **-** zoom 0/1/2 · arrows or drag to pan · **Home** re-center · **Space** / **T** one fake sim step (walker frame only; not `walkers_tick`) · **A** play 2 s of `A01.RAW`.

### Mapa da cidade / City map (tecla **3**)

Boot carrega o primeiro save da pasta do jogo (`FELIPE01.SAV`, senão `FELIPE02` / `LASTYEAR` / qualquer `.SAV`). **Não copia** o ficheiro para o git.

A janela **640×480** é uma **viewport** sobre o canvas iso nativo (já não encolhe o mapa inteiro para 960×497).

- **3** desenha o mapa isométrico 80×80 (SavChunk 13, 20 bytes/tile) e as pessoas do SavChunk 8. Terreno (`id < 0x78`) usa `CITYFIXT[id + 16]`. Edifícios (`id ≥ 0x78`) usam `tile[+3] & 0x1C` → `HOUSES1` / `BUILD1A`–`D` / `CITYFIXT` e `LUT[tile[+4]]` (`city_tile_draw_building` `0x3739F`). Casas `0x82–0xA1` e fóruns `0xA2–0xA8` neste save vão para `HOUSES1`. `AHOUSE` / `AFORUM` são ícones 182×132 do menu, não o mapa iso.
- **Pan:** setas (passo 96/48/24 px conforme o zoom) ou **clique-arrastar**. **Home** centra o canvas.
- **Zoom:** `+` / `=` / `]` aproxima (set 0 = `HOUSES1` / `BUILD1*` / `LTLMEN1B`, 58×30, flags `0x0002`). `-` / `[` / **Z** afasta. Set 1 = `HOUSES2` / `BUILD2*` / `CITYFIX2` / `LTLMEN2B` (26×14, `0x0102`). Set 2 = `HOUSES3` / `BUILD3*` / `CITYFIX3` / `LTLMEN3B` (10×6, `0x0202`). Roda do rato também muda o zoom. Se o PL8 faltar, o host faz scale nearest do zoom 0.
- **Space** / **T:** um passo falso (`app.sim.on_sim_step`) — `++walk_frame` (wrap 0…15) e reescreve `sprite_id`. **Não** é `walkers_tick` `0x459D0`. Pan/zoom não mexem.
- PNG sem janela (gitignorado): `python -m app --map-preview --no-audio`
- Save à escolha: `python -m app --sav "C:\Users\Felip\OneDrive\Games\Caesar2\LASTYEAR.SAV"`

---

## O que o v0 mostra / What you actually see

- Console: install path, key-file check, the 14 `gfx_load_boot_assets` names, C2.ENG count, boot notes.
- A **640×480** window (stand-in for VESA `video_init` @ `0x28341`).
- **Title art**: decoded `backgrnd.pl8` + `backgrnd.256` via `tools/decode_pl8.py` (not a copy of the format).
- HUD: path, one `C2.ENG` string (the “Caesar II - Version …” line if present).
- Optional: **2 seconds** of `A01.RAW` through Windows `winsound` (not Miles). Missing audio → skip.

No intro video. `INTRO.SMK` is only verified on disk (`smk_play` @ `0x5AB3D` is a stub; `tools/decode_smk.py` remuxes with ffmpeg, it does not play in-process).

---

## Stubs (Ghidra VAs — comments in `boot.py`)

| Original | VA | v0 |
|---|---|---|
| `c2_main` | `0x10010` | `boot.run_boot` |
| `load_file_cfg` / `resource.cfg` | `0x2456E` | read text, do not interpret the letter |
| `gfx_load_boot_assets` | `0x10E89` | verify 14 names; decode only title / CITYFIXT |
| `video_init` 640×480 | `0x28341` | tkinter window |
| `miles_init` | `0x11758` | skip / optional RAW |
| `smk_play` `intro.smk` | `0x5AB3D` | file exists? yes/no |
| `title_screen` | `0x5D37F` | real PL8 blit |
| `view_frame` / city tick | `0x3CF9A` | **Space / T** → `app.sim.on_sim_step` (fake `walk_frame`; **not** `walkers_tick` `0x459D0`) |
| city map SavChunk 13 | `0xE2FBC` | `city_map.py`: 80×80×20 from `.SAV`; tecla **3** |
| walkers SavChunk 8 | `0x1107A4` | `walkers.py`: 201×58; overlay after `render_iso` (tecla **3**) |

No live sim and no menu that starts a city. Houses / forums / industry / people blit from the original PL8s (tecla **3**).

---

## Godot vs Python

| | Choice |
|---|---|
| **v0 (this folder)** | Python + Pillow + tkinter. Throw away when Godot/C++ starts. |
| **Later** | Godot 4 or C++ that still **opens files from `CAESAR2_PATH`**. Same rule: no assets in git. |

If you install Godot 4 later, keep `app/` as a file-format test harness until the Godot project can import PL8 the same way.
