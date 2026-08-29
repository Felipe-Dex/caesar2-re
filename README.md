# Caesar II reverse-engineering notes (Phase 1)

Exploratory notes and a minimal `.PL8` decoder for **Caesar II** (1995, Impressions / Sierra). The goal is to understand original file formats for a future engine (Godot 4 or C++) that can load *your* copy of the game, similar to Julius/Augustus for Caesar III.

This repository **does not include** original game files or decoded sprites. You need a legally obtained Caesar II install.

## What is here

- `REVERSE.md` — file map (rev. 12): PL8 / RAW 22050 / SMK, plus `PS.EXE` LE container, SAV **500-chunk writer**, C2MODEL tables. Do not copy EXE/SAV/DAT into git.
- `findings/` — overnight workstream notes (`ps_exe.md`, `sav.md`, `c2model.md`); `notes/ps_sav_chunks.tsv` is the save scatter table (gitignored)
- `tools/ps_le.py` — MZ stub + DOS/16M BW + Watcom LE mapper (does not copy the EXE)
- `tools/decode_pl8.py` — Python 3 decoder (stdlib + Pillow)
  - bitmap sprites (`tile_type=0`, e.g. `AHOUSE.PL8`, battle units `RO2*` / `GM2*`)
  - isometric tiles (`tile_type` 1–4, e.g. `HOUSES1`, `BUILD1A`, `CITYFIXT`; also zoom 26×14 / 10×6)
  - type 1 may store `extra_rows` but the payload is diamond-only (900 B at 58×30)
  - VGA 6-bit `.256` palettes expanded to 8-bit
  - `--export-all` → `images/` (own `.256`, else city/battle/UI fallback)
- `tools/extract_eng.py` — `C2.ENG` string table (`Textfile` + u32 offsets)
- `tools/dump_c2model.py` — `C2MODEL.DAT` as int32 + FAQ sequence hunt
- `tools/diff_sav.py` — header / ASCII / coalesced byte-diff of `.SAV` files
- `tools/probe_sav_map.py` — occupancy PNGs using the `1745+35×6400` **size identity** (writer is 500 chunks at VA `0x9ABC0`; see `REVERSE.md`)
- `tools/dump_ps_savtable.py` — dump the 500 `{ptr,size}` save chunks from `PS.EXE`
- `tools/decode_raw.py` — `.RAW` inventory / waveform / spectrogram / WAV @ 22050 Hz (not a 448×448 image)
- `tools/decode_smk.py` — `.SMK` inventory + ffmpeg remux (Smacker → MP4); does not reimplement the codec
- `sound/` — local previews only (`*.wav`, `*_waveform.png`, `*_spec.png`); gitignored, do not publish
- `images/` — local PL8 previews (`{stem}.png` or `{stem}_sheet.png`); gitignored, do not publish
- `videos/` — local Smacker previews (`{stem}.mp4`, `{stem}_frame0.png`); gitignored, do not publish

## Decoder

```text
python tools/decode_pl8.py --pl8 path\to\AHOUSE.PL8 --pal path\to\AHOUSE.256 --out AHOUSE.png
python tools/decode_pl8.py --pl8 path\to\HOUSES1.PL8 --pal path\to\CITYFIXT.256 --sheet --out HOUSES1_sheet.png
python tools/decode_pl8.py --pl8 path\to\CITYFIXT.PL8 --pal path\to\CITYFIXT.256 --sheet --out CITYFIXT_sheet.png
python tools/decode_pl8.py --inventory
python tools/decode_pl8.py --export-all
python tools/extract_eng.py --eng path\to\C2.ENG
python tools/dump_c2model.py --dat path\to\C2MODEL.DAT
python tools/diff_sav.py --a path\to\FELIPE01.SAV --b path\to\FELIPE02.SAV
python tools/decode_raw.py --inventory
python tools/decode_raw.py --export-all
python tools/decode_raw.py --raw path\to\A01.RAW --out sound\A01_waveform.png
python tools/decode_raw.py --raw path\to\A01.RAW --mode wav --out sound\A01.wav
python tools/decode_smk.py --inventory
python tools/decode_smk.py --export-all
python tools/decode_smk.py --smk path\to\INTRO.SMK
```

`decode_pl8.py --export-all` writes every install `.PL8` into `images/` (`{stem}.png` if one sprite, `{stem}_sheet.png` otherwise). Palette: sibling `.256` if present, else `CITYFIXT` / `BATLFIX2` / `CITY1` (see `REVERSE.md`). `decode_raw.py --export-all` writes every `.RAW` into `sound/` as unsigned 8-bit PCM mono **22050 Hz** plus waveform and spectrogram PNGs. `decode_smk.py --export-all` remuxes every `.SMK` through **ffmpeg** into `videos/{stem}.mp4` (H.264 + AAC) plus `{stem}_frame0.png`. Point `--pl8` / `--pal` / `--game` at your game folder. Do not commit PNGs, WAVs, MP4s, or `notes/` string dumps. Needs `ffmpeg` on PATH (`winget install --id Gyan.FFmpeg`, or `--ffmpeg`).

## v0 window (`app/`)

Disposable Python host you can launch **now** (Godot was not installed). It reads **your** Caesar II folder — it does not copy `.PL8` / `.SMK` / `.RAW` / `.EXE` into git.

```text
python -m app
python -m app --check --no-audio
```

Set `CAESAR2_PATH`, or copy `app/config.example.json` → `app/config.local.json` (gitignored). Shows a 640×480 window with a decoded title `backgrnd.pl8` and C2.ENG text. City sim is **not** here — see `app/README.md`.

## Status

Phase 1 (understanding). `app/` is a file-load skeleton, not a playable engine.
