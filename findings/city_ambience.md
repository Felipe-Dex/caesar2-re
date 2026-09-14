# City ambience — birds / water / clicks

**Answer first:** we **did** find them. They are retail ``.WAV`` files on the flat 1.1A tree (`C:\Users\Felip\OneDrive\Games\Caesar2`), named in `PS.EXE`. They were **not** in repo `sound/` (that dump is the A/B/C + PREBATLE RAW bank). Ambience loops were **intentionally not started** until this hook. There is **no** `/audios` folder in the repo.

Do not copy WAVs into git. Resolve `{repo}/wav/` first, then the install (`app.audio.resolve_wav`). Windows plays through WinMM so Tk + missing pygame still hear loops/clicks.

---

## 1. `/audios` vs `sound/` vs retail

| Place | What it is | Birds / water / click? |
|---|---|---|
| **`audios/`** | **Does not exist** in this repo | — |
| **`sound/`** (also `SOUND/`, same dir) | Decoded **A01–A09 / B01–B20 / C01–C43 / PREBATLE** RAW → WAV + spectrograms. Advisor / province flavor / boot sting. Unsigned PCM @ 22050 Hz. | **No.** `A09.wav` here is the labor toast, not a click. |
| **`videos/`** | SMK → mp4 talking-heads / cutscenes (`INTRO`, `CONGRAT`, `FIRE`, …) | Cutscene audio only. Not city birds/water. |
| **Retail root** | Flat 1.1A: **83 WAV** + **5 XMI** + Miles `.DIG`/`.MDI` + RAW banks | **Yes.** `GARDENB.WAV`, `FOUNTN.WAV`, `POSCL.WAV`, … |

Host `SfxPlayer` plays one-shots from retail (`place` / `poscl` / `negcl2` / `fire` / rubble / `forum` / `a09`) plus the proximity mixer (same one-shot path). It must **not** global-loop ``gardenb`` / ``fountn``.

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
| **`gardenb.wav`** | **`GARDENB.WAV`** | Slot 1 variant 0 (`0x12F6B`). **The dog** (loud bark burst). One-shot when a garden is on-screen, not a city-enter loop. |
| `gardenc.wav` | `GARDENC.WAV` | Garden variant. Not started. |
| `gardend.wav` | `GARDEND.WAV` | Garden variant. Not started. |

Province birds (`province_sfx_bind_wavs` `0x13187`, not City Only):

`birdsp2.wav`…`birdsp5.wav` → `BIRDSP2.WAV`…`BIRDSP5.WAV`. Same ~1.8 s loop size.

City water (same `0x12F2A` table — **no** `water.wav`):

| EXE | Retail | Notes |
|---|---|---|
| **`fountn.wav`** | **`FOUNTN.WAV`** | Slot 8. Fountain in view only (occasional one-shot). |
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

## 4. EXE proximity mixer (not a city-enter loop)

Bind ``city_sfx_bind_wavs`` ``0x12F2A`` only **copies names** into 25 slots at ``0xA3FBC`` (stride ``0x46``). It does **not** start playback. Slot 0 is unused. Names live at slot+6 / +0x16 / +0x26 (variants).

| Slot | WAV | Tile ids (mapper ``0x12A8F``) |
|---|---|---|
| 1 | **gardenb** / gardenc / gardend | **0x78–0x7B garden** |
| 2 | circus1 | 0xE9–0xF2 circus |
| 3 | barrack2 | 0xE4 barracks |
| 4 | bathhs | 0xDF–0xE2 baths |
| 5 | colisum5 / colisum6 | 0xE7–0xE8 coliseum |
| 6 | fire | not from ``0x12A8F`` (overlay ``0x37E96``) |
| 7 | forum | 0xAE–0xBB |
| 8 | fountn | **0xDB–0xDE fountain** |
| 9 | fountnx | no city-tile enable |
| 10 | grammat2 | 0xF3 |
| 11 | rhetor | 0xF4 |
| 12 | marketh | 0xFE+ |
| 13 | marketl | 0xFC–0xFD market |
| 14 | plazab | 0x7C–0x81 plaza |
| 15 | well | **0xD7–0xDA well** |
| 16 | reserv | **0xBE reservoir** |
| 17 | aquadct | **0xCB–0xD6 aqueduct** (also 0xBC–0xBD) |
| 18 | temple1 | 0xA2–0xAD shrine/temple/basilica |
| 19 | theatre | 0xE5–0xE6 theater/odeum |
| 20 / 21 | hbiz / lbiz | 0xFA factory (``tile[+9]>>4 > 3`` → hbiz) |
| 22 / 23 | null | 0xFB hospital / 0xE3 prefecture |
| — | **none** | **housing 0x82–0xA1**, terrain ``< 0x78``, walls 0xBF–0xCA, library 0xF5–0xF9 |

**Dog:** there is **no** ``dog.wav`` / ``bark`` / ``wolf`` string in ``PS.EXE`` and no such file on the 1.1A tree. The bark is **``GARDENB.WAV``** (slot 1 variant 0). Peak ~72 with two loud bursts; ``GARDENC``/``GARDEND`` are quieter birds (~peak 20–27). Same ~1.81 s / 11025 Hz loop fodder, but the mixer plays them as **one-shots**.

**Viewport gate:** city tile draw ``0x3739F`` / ``0x3747E`` reads ``tile[+0]`` and calls ``0x12A8F``, which sets ``slot[+0]=1``. Only **drawn** (on-screen) buildings enable a slot. Housing never does.

**Occasional fire:** mixer ``0x12E1E`` (``view_frame`` tail ``0x3D3D5``) walks slots 1…24. If ``[+0]`` was set this frame: clear it, ``[++4]``, and if ``[+4] >= 0xC8`` (200) play ``0x11B7B`` (same one-shot path as ``place.wav``), reset ``[+4]`` from ``[0xC2070]`` (BSS, 0), cycle variant at ``[+1]`` vs count ``[+2]``. Init ``[+4] = slot<<3`` (garden starts at 8 → first play after 192 enabled frames). Sound off ``[0x9CE58]`` / Miles down ``[0x9D40C]`` / ``[0x9CE86]==0`` skip play.

So: empty new city (no gardens) **never** plays the dog. A house in view is **not** enough. A garden in view → slot 1 counts up → every ~200 view frames play ``gardenb`` then ``gardenc`` then ``gardend``. Fountain / well / reservoir / aqueduct / baths are the same one-shot-when-in-view rule, **not** global loops.

``0x39013`` enables slot 1 unconditionally — that is the **province** path (``[0x117A8D]==1``), which rebinds slot 1 to ``birdsp2…``. Not City Only.

## 5. Host hook

`app/audio.py` / `app/window.py`:

- Click stays **`poscl.wav`**. Advisor mp4 audio unchanged.
- **No** city-enter loop of ``gardenb`` / ``fountn``. That was the empty-map dog.
- ``clock_step`` (50 ms) calls ``tick_ambience``: scan the camera well, increment enabled slots, one-shot when ``>= 0xC8``.
- Options Sound / ``--no-audio`` mute everything (mixer + clicks + advisor).

Retail name typos vs EXE (case-insensitive resolve still misses these): `colisum5`/`6` → `COLISM5.WAV`/`COLISM6.WAV`; `quarry.wav` → `QUARRYA/B/C.WAV`; `knieht.wav` → `KNIFEHT.WAV`; `armadv`/`armcav` → `ARMYADV`/`ARMYCAV`; `mining3.wav` absent (`MINING4/5/6.WAV` on disk). Host slot 5 uses the retail ``colism5/6`` stems.
