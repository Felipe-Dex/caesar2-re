# City ambience — birds / water / clicks

**Answer first:** we **did** find them. They are retail ``.WAV`` files on the flat 1.1A tree (`C:\Users\Felip\OneDrive\Games\Caesar2`), named in `PS.EXE`. They were **not** in repo `sound/` (that dump is the A/B/C + PREBATLE RAW bank). Ambience loops were **intentionally not started** until this hook. There is **no** `/audios` folder in the repo.

Do not copy WAVs into git. Resolve from the install (`app.audio.resolve_wav`).

---

## 1. `/audios` vs `sound/` vs retail

| Place | What it is | Birds / water / click? |
|---|---|---|
| **`audios/`** | **Does not exist** in this repo | — |
| **`sound/`** (also `SOUND/`, same dir) | Decoded **A01–A09 / B01–B20 / C01–C43 / PREBATLE** RAW → WAV + spectrograms. Advisor / province flavor / boot sting. Unsigned PCM @ 22050 Hz. | **No.** `A09.wav` here is the labor toast, not a click. |
| **`videos/`** | SMK → mp4 talking-heads / cutscenes (`INTRO`, `CONGRAT`, `FIRE`, …) | Cutscene audio only. Not city birds/water. |
| **Retail root** | Flat 1.1A: **83 WAV** + **5 XMI** + Miles `.DIG`/`.MDI` + RAW banks | **Yes.** `GARDENB.WAV`, `FOUNTN.WAV`, `POSCL.WAV`, … |

Host `SfxPlayer` already played one-shots from retail (`place` / `poscl` / `negcl2` / `fire` / rubble / `forum` / `a09`). It did **not** start the city bind loops.

---

## 2. Exact filenames

UI click (not missing):

| Role | EXE 8.3 | Retail file | VA / xref |
|---|---|---|---|
| **Click** | `poscl.wav` | `POSCL.WAV` (532 B, 0.04 s) | `0x9042C` → `miles_init` `0x117E4` |
| Deny | `negcl2.wav` | `NEGCL2.WAV` (624 B, 0.05 s) | `0x90436` → `0x1180A` |

City birds (bind `city_sfx_bind_wavs` `0x12F2A`):

| EXE | Retail | Notes |
|---|---|---|
| **`gardenb.wav`** | **`GARDENB.WAV`** | First city slot (`0x12F6B`). ~1.81 s @ 11025 Hz mono 8-bit loop. |
| `gardenc.wav` | `GARDENC.WAV` | Garden variant. Not started. |
| `gardend.wav` | `GARDEND.WAV` | Garden variant. Not started. |

Province birds (`province_sfx_bind_wavs` `0x13187`, not City Only):

`birdsp2.wav`…`birdsp5.wav` → `BIRDSP2.WAV`…`BIRDSP5.WAV`. Same ~1.8 s loop size.

City water (same `0x12F2A` table — **no** `water.wav`):

| EXE | Retail | Notes |
|---|---|---|
| **`fountn.wav`** | **`FOUNTN.WAV`** | Fountain. Host water loop. |
| `fountnx.wav` | `FOUNTNX.WAV` | Fountain variant. |
| `well.wav` | `WELL.WAV` | Well. |
| `aquadct.wav` | `AQUADCT.WAV` | Aqueduct. |
| `reserv.wav` | `RESERV.WAV` | Reservoir. |
| `bathhs.wav` | `BATHHS.WAV` | Baths. |

Province water (not City Only): `surf1.wav` / `surf2.wav`, `shore1.wav` / `shore2.wav`.

All of those ambience clips are ~20 KB, 11025 Hz, ~1.8 s — Miles loop fodder. Clicks are one-shots.

---

## 3. Not MIDI / not inside SMK / not VOC

- **WAV** — city SFX + building loops. Miles digital (`AIL_*`, `SB16.DIG`).
- **XMI** — music only: `CITYPROV.XMI`, `FORUM1.XMI` / `FORUM2.XMI` / `FORUM3.XMI`, `BATEST2.XMI`. Options **Music** (host still says “XMI not in host”).
- **RAW** — narration banks A/B/C + `PREBATLE.RAW` @ 22050. This is what `sound/` extracted.
- **SMK** — advisor / intro video + their own audio tracks (`videos/*.mp4`).
- **VOC** — none on the 1.1A tree. EXE leftover `null.voc` only.

So: not “never found.” Found, sitting on the retail tree with EXE names. `sound/` was the wrong folder to listen through.

---

## 4. Host hook (small — no mixer)

`app/audio.py`:

- Click stays **`poscl.wav`**. Already wired on HUD / place / menus.
- City map starts two loops when Sound is on: **`gardenb.wav`** + **`fountn.wav`**.
- Options Sound / `--no-audio` stop them. Do not play `A01.RAW`.
- No proximity mixer. Siblings (`gardenc`/`d`, `well`, `aquadct`, `reserv`, `bathhs`, `temple1`, circus, markets, …) stay unbound.

EXE city bind order (25 slots, `cmp edx, 0x19` then `movsd` copies from `0x90453`):

`gardenb`, `gardenc`, `gardend`, `circus1`, `barrack2`, `bathhs`, `colisum5`, `colisum6`, `fire`, `forum`, `fountn`, `fountnx`, `grammat2`, `rhetor`, `marketh`, `marketl`, `plazab`, `well`, `reserv`, `aquadct`, `temple1`, `theatre`, `hbiz`, `lbiz`, `null` (twice).

Retail name typos vs EXE (case-insensitive resolve still misses these): `colisum5`/`6` → `COLISM5.WAV`/`COLISM6.WAV`; `quarry.wav` → `QUARRYA/B/C.WAV`; `knieht.wav` → `KNIFEHT.WAV`; `armadv`/`armcav` → `ARMYADV`/`ARMYCAV`; `mining3.wav` absent (`MINING4/5/6.WAV` on disk).
