# Caesar II reverse-engineering notes (Phase 1)

Exploratory notes and a minimal `.PL8` decoder for **Caesar II** (1995, Impressions / Sierra). The goal is to understand original file formats for a future engine (Godot 4 or C++) that can load *your* copy of the game, similar to Julius/Augustus for Caesar III.

This repository **does not include** original game files or decoded sprites. You need a legally obtained Caesar II install.

## What is here

- `REVERSE.md` — file map, evidence (offsets, sizes), PL8 header, comparison with C3 SG2/555
- `tools/decode_pl8.py` — Python 3 decoder (stdlib + Pillow)
  - bitmap sprites (`tile_type=0`, e.g. `AHOUSE.PL8`)
  - isometric tiles (`tile_type` 1–4, e.g. `HOUSES1`, `BUILD1A`, `CITYFIXT`)
  - type 1 may store `extra_rows` but the payload is diamond-only (900 B at 58×30)
  - VGA 6-bit `.256` palettes expanded to 8-bit

## Decoder

```text
python tools/decode_pl8.py --pl8 path\to\AHOUSE.PL8 --pal path\to\AHOUSE.256 --out AHOUSE.png
python tools/decode_pl8.py --pl8 path\to\HOUSES1.PL8 --pal path\to\CITYFIXT.256 --sheet --out HOUSES1_sheet.png
python tools/decode_pl8.py --pl8 path\to\CITYFIXT.PL8 --pal path\to\CITYFIXT.256 --sheet --out CITYFIXT_sheet.png
```

Point `--pl8` / `--pal` at your game folder. Do not commit the PNGs.

## Status

Phase 1 (understanding). Not a playable engine.
