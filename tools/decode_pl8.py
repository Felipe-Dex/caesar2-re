#!/usr/bin/env python3
"""Caesar II .PL8 decoder (Phase 1).

Layout measured on this install (little-endian), then checked against
AHOUSE.PL8 (1 sprite, 182x132, file size 24048):

    offset 0  u16  flags
    offset 2  u16  n_sprites
    offset 4  u32  unknown_04          # not interpreted
    offset 8  SpriteRecord[n_sprites]  # 16 bytes each

    SpriteRecord (16 bytes):
        0   u16  width
        2   u16  height
        4   u32  data_offset           # from start of file
        8   u16  x                     # draw offset; unused for decode
        10  u16  y
        12  u8   tile_type             # 0 bitmap; 1-4 isometric
        13  u8   extra_rows            # ISO extra; type 1 stores it but no extra payload
        14  u16  unknown_14

    data_offset of sprite 0 == 8 + 16 * n_sprites   (measured)

Retail 1.1A: flags bit 0 (community RLE) is never set. All 299 PL8 files
are uncompressed; span == packed_bytes. High byte of flags tracks zoom
(0x00 / 0x01 / 0x02) together with the 1/2/3 digit in BUILD*/HOUSES*/RO*.

Palette .256 is 256 * 3 bytes RGB (no padding, no alpha).
On this install every byte is in 0..63 (VGA 6-bit DAC). The loader
expands to 8-bit with (c << 2) | (c >> 4). Index 0 is emitted as
alpha=0; on AHOUSE that index is almost unused (the grass is not key 0).
"""

from __future__ import annotations

import argparse
import struct
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

FILE_HEADER_SIZE = 8
SPRITE_RECORD_SIZE = 16
PALETTE_SIZE = 256 * 3

# Community docs: bit 0 of flags means RLE. This 1.1A install has 0 such files.
FLAG_RLE = 0x0001

TILE_BITMAP = 0
# 1-4: isometric diamond + optional extra rows (types 2/3/4 only on disk).

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
DEFAULT_IMAGES = Path(r"C:\Users\Felip\caesar2-re\images")

# Unit packs without a sibling .256 (RO2SWDA, GM2*, …).
BATTLE_PREFIXES = frozenset(
    {"AF", "AR", "BR", "CA", "EG", "GK", "GL", "GM", "HN", "PA", "RO"}
)

# Exact-stem aliases when the PL8 has no own .256.
STEM_ALIASES: dict[str, str] = {
    "BATLFIX3": "BATLFIX2",
    "CITYFIX2": "CITYFIXT",
    "CITYFIX3": "CITYFIXT",
    "E_PARTS": "EMPIRE",
    "E_PARTS2": "EMPIRE",
    "FONT3C2": "CITY1",
    "FONT_C2": "CITY1",
    "FORUMBIT": "FORUM",
    "HORSEB": "BATT1",
    "INT_BATL": "BATT1",
    "INT_CITY": "CITY1",
    "INT_PROV": "PROV1",
    "PROVFIX2": "PROVFIXT",
    "PROVFIX3": "PROVFIXT",
    "RAT_FRON": "RAT_BACK",
}

UI_STEMS = frozenset(
    {"ICONS", "MAIN", "MISC", "MOUSE", "PANELS", "SMACKER", "SYSTEM"}
)


@dataclass(frozen=True)
class SpriteRecord:
    index: int
    width: int
    height: int
    data_offset: int
    x: int
    y: int
    tile_type: int
    extra_rows: int
    unknown_14: int
    raw: bytes

    @property
    def unpacked_bytes(self) -> int:
        return self.width * self.height

    @property
    def canvas_height(self) -> int:
        # Type 1 stores extra_rows but CITYFIXT shows no extra payload (span=900).
        if self.tile_type in (2, 3, 4):
            return self.height + self.extra_rows
        return self.height

    def packed_bytes(self) -> int:
        """Payload size on disk for this record (ISO diamond + extra rows)."""
        if self.tile_type == TILE_BITMAP:
            return self.unpacked_bytes
        diamond = iso_diamond_bytes(self.width, self.height)
        return diamond + extra_row_bytes(
            self.width, self.tile_type, self.extra_rows
        )


def u16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def vga6_to_8(c: int) -> int:
    """Expand a 6-bit VGA DAC channel (0..63) to 8-bit (0..255)."""
    return (c << 2) | (c >> 4)


def list_pl8(game: Path) -> list[Path]:
    found: dict[str, Path] = {}
    for p in game.iterdir():
        if p.is_file() and p.suffix.upper() == ".PL8":
            found[p.name.upper()] = p
    return [found[k] for k in sorted(found)]


def list_palettes(game: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for p in game.iterdir():
        if p.is_file() and p.suffix.upper() == ".256":
            found[p.stem.upper()] = p
    return found


def find_palette(game: Path, stem: str) -> Path | None:
    return list_palettes(game).get(stem.upper())


def resolve_palette(
    pl8: Path, game: Path, pal_override: Path | None = None
) -> tuple[Path, str]:
    """Pick a .256 for this PL8. Own stem wins; then aliases / families."""
    if pal_override is not None:
        return pal_override, "cli"

    pals = list_palettes(game)
    stem = pl8.stem.upper()
    if stem in pals:
        return pals[stem], "own"

    alias = STEM_ALIASES.get(stem)
    if alias and alias in pals:
        return pals[alias], f"alias:{alias}"

    if stem.startswith(
        ("BUILD", "HOUSES", "CITYFIX", "CITYTOP", "OVERLAY", "LANDFILL", "LTLMEN")
    ):
        if "CITYFIXT" in pals:
            return pals["CITYFIXT"], "family:city"
    if stem.startswith(("PROVFIX", "PRVBLD", "MOUNTNS")):
        if "PROVFIXT" in pals:
            return pals["PROVFIXT"], "family:prov"
    if stem.startswith(("MY_STDS", "PACAVA")):
        if "BATLFIX2" in pals:
            return pals["BATLFIX2"], "family:battle"
    if (
        len(stem) >= 3
        and stem[:2] in BATTLE_PREFIXES
        and stem[2].isdigit()
        and "BATLFIX2" in pals
    ):
        return pals["BATLFIX2"], "family:battle"
    if stem in UI_STEMS and "CITY1" in pals:
        return pals["CITY1"], "family:ui"

    if "CITYFIXT" in pals:
        return pals["CITYFIXT"], "fallback:CITYFIXT"
    if "CITY1" in pals:
        return pals["CITY1"], "fallback:CITY1"
    raise FileNotFoundError(f"no .256 palette available for {pl8.name} under {game}")


def load_palette(path: Path, *, verbose: bool = True) -> list[tuple[int, int, int]]:
    data = path.read_bytes()
    if len(data) != PALETTE_SIZE:
        raise ValueError(
            f"{path.name}: expected {PALETTE_SIZE} bytes (256xRGB), got {len(data)}"
        )
    raw_max = max(data) if data else 0
    scale_6bit = raw_max <= 63
    if verbose:
        print(
            f"palette max   : {raw_max}  "
            f"({'VGA 6-bit -> 8-bit' if scale_6bit else 'already 8-bit'})"
        )

    def chan(v: int) -> int:
        return vga6_to_8(v) if scale_6bit else v

    return [
        (chan(data[i]), chan(data[i + 1]), chan(data[i + 2]))
        for i in range(0, PALETTE_SIZE, 3)
    ]


def parse_pl8(
    path: Path, *, print_limit: int = 6, verbose: bool = True
) -> tuple[int, int, list[SpriteRecord], bytes]:
    data = path.read_bytes()
    if len(data) < FILE_HEADER_SIZE + SPRITE_RECORD_SIZE:
        raise ValueError(f"{path.name}: file too small ({len(data)} bytes)")

    flags = u16(data, 0)
    n_sprites = u16(data, 2)
    unknown_04 = u32(data, 4)
    table_end = FILE_HEADER_SIZE + SPRITE_RECORD_SIZE * n_sprites

    if verbose:
        print(f"file          : {path.name}")
        print(f"file size     : {len(data)} bytes")
        print(f"flags         : 0x{flags:04X}  (RLE bit0={'yes' if flags & FLAG_RLE else 'no'})")
        print(f"n_sprites     : {n_sprites}")
        print(f"unknown_04    : 0x{unknown_04:08X} ({unknown_04})")
        print(f"table_end     : {table_end}  (= 8 + 16 * n_sprites)")

    if n_sprites < 1:
        raise ValueError("n_sprites == 0")
    if table_end > len(data):
        raise ValueError(f"sprite table overruns file ({table_end} > {len(data)})")

    sprites: list[SpriteRecord] = []
    show = set(range(min(print_limit, n_sprites)))
    if n_sprites:
        show.add(n_sprites - 1)

    for i in range(n_sprites):
        rec_off = FILE_HEADER_SIZE + i * SPRITE_RECORD_SIZE
        raw = data[rec_off : rec_off + SPRITE_RECORD_SIZE]
        spr = SpriteRecord(
            index=i,
            width=u16(raw, 0),
            height=u16(raw, 2),
            data_offset=u32(raw, 4),
            x=u16(raw, 8),
            y=u16(raw, 10),
            tile_type=raw[12],
            extra_rows=raw[13],
            unknown_14=u16(raw, 14),
            raw=raw,
        )
        sprites.append(spr)
        if not verbose or i not in show:
            continue
        hex_rec = " ".join(f"{b:02X}" for b in raw)
        print(
            f"sprite[{i}]     : {spr.width}x{spr.height}  "
            f"data_offset={spr.data_offset}  "
            f"xy=({spr.x},{spr.y})  type={spr.tile_type}  extra={spr.extra_rows}  "
            f"unk14=0x{spr.unknown_14:04X}"
        )
        print(f"  record hex  : {hex_rec}")
        print(f"  unpacked    : {spr.unpacked_bytes} bytes (width*height)")

    if verbose and n_sprites > print_limit + 1:
        print(f"  ... ({n_sprites - len(show)} sprites omitted)")

    return flags, unknown_04, sprites, data


def check_offset_chain(
    sprites: list[SpriteRecord], file_size: int, *, verbose: bool = True
) -> int:
    """Return number of sprites whose payload != packed_bytes."""
    mismatches = 0
    types: dict[int, int] = {}
    sizes: dict[tuple[int, int], int] = {}
    for spr in sprites:
        types[spr.tile_type] = types.get(spr.tile_type, 0) + 1
        sizes[(spr.width, spr.height)] = sizes.get((spr.width, spr.height), 0) + 1
        span = expected_span(sprites, file_size, spr.index)
        need = spr.packed_bytes()
        if span != need:
            mismatches += 1
            if verbose and mismatches <= 8:
                print(
                    f"CHAIN BREAK  : sprite[{spr.index}] "
                    f"{spr.width}x{spr.height} type={spr.tile_type} extra={spr.extra_rows} "
                    f"need={need} span={span} delta={span - need}"
                )

    if verbose:
        predicted0 = FILE_HEADER_SIZE + SPRITE_RECORD_SIZE * len(sprites)
        last = sprites[-1]
        last_end = last.data_offset + expected_span(sprites, file_size, last.index)
        print(
            f"offset check  : sprite[0].data_offset={sprites[0].data_offset}  "
            f"predicted={predicted0}"
        )
        print(f"size histogram: {dict(sorted(sizes.items(), key=lambda kv: -kv[1]))}")
        print(f"tile_type hist: {types}")
        print(
            f"chain match   : {len(sprites) - mismatches}/{len(sprites)}  "
            f"(span == packed_bytes)"
        )
        print(f"payload end   : {last_end}  file={file_size}  slack={file_size - last_end}")
    return mismatches


def iso_diamond_bytes(width: int, height: int) -> int:
    """Pixel count of the centred isometric diamond (pl8image, type 1)."""
    half = height // 2
    n = 0
    for y in range(half):
        n += y * 4 + 2
    for y in range(half, height):
        n += (height - y - 1) * 4 + 2
    return n


def extra_row_bytes(width: int, tile_type: int, extra_rows: int) -> int:
    # Type 1 is diamond-only even when extra_rows > 0 (measured on CITYFIXT.PL8).
    if extra_rows <= 0 or tile_type in (TILE_BITMAP, 1):
        return 0
    half_w = width // 2
    if tile_type == 3:
        per_row = half_w + 1
    elif tile_type == 4:
        per_row = width - (half_w - 1)
    else:
        per_row = width
    return extra_rows * per_row


def unpack_iso(payload: bytes, spr: SpriteRecord) -> tuple[bytes, int, int]:
    """Unpack ISO encodings 1-4 into a row-major buffer (index 0 = empty).

    Payload sizes measured on HOUSES1.PL8 and CITYFIXT.PL8 (58x30):
      type 1 (any extra_rows) -> 900  (diamond only; extra is not on disk)
      type 2 extra N          -> 900 + N*58
      type 3/4 extra N        -> 900 + N*30
    Same geometry scales to zoom-2 26x14 and zoom-3 10x6 (chain-verified).
    """
    w, h = spr.width, spr.height
    extra = spr.extra_rows
    canvas_h = h + extra
    out = bytearray(w * canvas_h)
    pos = 0

    def get() -> int:
        nonlocal pos
        if pos >= len(payload):
            raise ValueError(
                f"sprite[{spr.index}] ISO ran out of bytes at {pos}/{len(payload)}"
            )
        b = payload[pos]
        pos += 1
        return b

    half_h = h // 2
    half_w = w // 2

    shift = extra if spr.tile_type in (2, 3, 4) else 0

    for y in range(half_h):
        row_start = (half_h - 1 - y) * 2
        row_stop = row_start + (y * 4) + 2
        dest_y = y + shift
        for x in range(row_start, row_stop):
            out[dest_y * w + x] = get()

    for y in range(half_h, h):
        k = h - y - 1
        row_start = (half_h - 1 - k) * 2
        row_stop = row_start + (k * 4) + 2
        dest_y = y + shift
        for x in range(row_start, row_stop):
            out[dest_y * w + x] = get()

    if spr.tile_type in (2, 3, 4):
        for y_ in range(extra, 0, -1):
            right = half_w + 1 if spr.tile_type == 3 else w
            left = half_w - 1 if spr.tile_type == 4 else 0
            for x in range(left, right):
                if x <= half_w:
                    y = y_ + (half_h - 1) - (x // 2)
                else:
                    y = y_ + (x // 2) - (half_h - 1)
                if not (0 <= y < canvas_h and 0 <= x < w):
                    raise ValueError(
                        f"sprite[{spr.index}] ISO extra write out of bounds "
                        f"x={x} y={y} canvas={w}x{canvas_h}"
                    )
                out[y * w + x] = get()

    if pos != len(payload):
        raise ValueError(
            f"sprite[{spr.index}] ISO consumed {pos} of {len(payload)} bytes"
        )
    return bytes(out), w, canvas_h


def expected_span(sprites: list[SpriteRecord], file_size: int, index: int) -> int:
    """Bytes available for sprite[index]: up to next offset or EOF."""
    start = sprites[index].data_offset
    if index + 1 < len(sprites):
        end = sprites[index + 1].data_offset
    else:
        end = file_size
    return end - start


def rle_decode(src: bytes, expected: int) -> bytes:
    """Community pl8image RLE (flags bit 0). Unused on this 1.1A install (0 files).

    Each chunk starts with u8 n_opaque:
      0 → next u8 is a transparent run (index 0)
      N → next N bytes are palette indices
    """
    out = bytearray()
    i = 0
    n = len(src)
    while len(out) < expected:
        if i >= n:
            raise ValueError(
                f"RLE underrun at {i}/{n}, produced {len(out)}/{expected}"
            )
        n_opaque = src[i]
        i += 1
        if n_opaque == 0:
            if i >= n:
                raise ValueError("RLE transparent count missing")
            n_trans = src[i]
            i += 1
            if n_trans == 0:
                raise ValueError("RLE chunk 0,0 is undefined (no sample on this install)")
            out.extend(b"\x00" * n_trans)
        else:
            if i + n_opaque > n:
                raise ValueError(
                    f"RLE opaque run of {n_opaque} overruns source at {i}/{n}"
                )
            out.extend(src[i : i + n_opaque])
            i += n_opaque
    if len(out) != expected:
        raise ValueError(f"RLE produced {len(out)} bytes, expected {expected}")
    return bytes(out)


def decode_bitmap(indices: bytes, width: int, height: int, palette) -> Image.Image:
    need = width * height
    if len(indices) < need:
        raise ValueError(f"bitmap buffer {len(indices)} < {need}")
    blob = indices[:need]
    img = Image.frombytes("P", (width, height), blob)
    flat: list[int] = []
    for rgb in palette:
        flat.extend(rgb)
    img.putpalette(flat)
    rgba = img.convert("RGBA")
    alpha = blob.translate(bytes([0] + [255] * 255))
    rgba.putalpha(Image.frombytes("L", (width, height), alpha))
    return rgba


def make_sheet(frames: list[Image.Image], cell: tuple[int, int] | None = None) -> Image.Image:
    if not frames:
        raise ValueError("no frames to sheet")
    cw = cell[0] if cell else max(im.size[0] for im in frames)
    ch = cell[1] if cell else max(im.size[1] for im in frames)
    cols = min(16, len(frames))
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cw, rows * ch), (0, 0, 0, 0))
    for i, im in enumerate(frames):
        x = (i % cols) * cw
        y = (i // cols) * ch
        sheet.paste(im, (x, y), im)
    return sheet


def decode_sprite(
    data: bytes,
    spr: SpriteRecord,
    flags: int,
    file_size: int,
    sprites: list[SpriteRecord],
    palette,
    *,
    verbose: bool = True,
) -> Image.Image:
    span = expected_span(sprites, file_size, spr.index)
    need = spr.packed_bytes()

    if verbose:
        print(f"pixel span    : offset {spr.data_offset} .. +{span} (available)")
        print(
            f"pixel packed  : {need}  unpacked={spr.unpacked_bytes}  "
            f"canvas_h={spr.canvas_height}"
        )

    if spr.data_offset + max(span, 0) > file_size or span < 0:
        raise ValueError(
            f"sprite[{spr.index}] data_offset={spr.data_offset} span={span} "
            f"overruns file ({file_size})"
        )

    raw = data[spr.data_offset : spr.data_offset + max(span, 0)]
    if flags & FLAG_RLE:
        blob = rle_decode(raw, need)
    else:
        if span != need:
            if verbose:
                print("SIZE MISMATCH : packed-size hypothesis does not fit this sprite.")
                print(f"  available payload = {span}")
                print(f"  packed_bytes      = {need}")
                print(f"  width*height      = {spr.unpacked_bytes}")
                print(f"  difference        = {span - need}")
            raise ValueError(
                f"pixel payload {span} != packed {need} "
                f"({spr.width}x{spr.height} type={spr.tile_type} extra={spr.extra_rows})"
            )
        blob = raw

    if spr.tile_type == TILE_BITMAP:
        return decode_bitmap(blob, spr.width, spr.height, palette)
    if spr.tile_type in (1, 2, 3, 4):
        indices, w, h = unpack_iso(blob, spr)
        return decode_bitmap(indices, w, h, palette)
    raise NotImplementedError(f"tile_type={spr.tile_type} is not implemented")


def decode_frames(
    data: bytes,
    sprites: list[SpriteRecord],
    flags: int,
    palette,
) -> list[Image.Image]:
    return [
        decode_sprite(
            data, spr, flags, len(data), sprites, palette, verbose=False
        )
        for spr in sprites
    ]


def export_one(
    pl8: Path,
    palette_path: Path,
    out: Path,
    *,
    sheet: bool,
    index: int,
    verbose: bool,
) -> Image.Image:
    flags, _unknown_04, sprites, blob = parse_pl8(pl8, verbose=verbose)
    if verbose:
        mismatches = check_offset_chain(sprites, len(blob), verbose=True)
        if sprites[0].data_offset != FILE_HEADER_SIZE + SPRITE_RECORD_SIZE * len(sprites):
            print(
                "WARNING       : dataOffset != 8+16*nSprites. "
                "Header-size hypothesis needs revisiting."
            )
    else:
        mismatches = check_offset_chain(sprites, len(blob), verbose=False)

    palette = load_palette(palette_path, verbose=verbose)
    if verbose:
        print(f"palette       : {palette_path.name}  256 RGB  index0={palette[0]}")

    out.parent.mkdir(parents=True, exist_ok=True)
    if sheet or (len(sprites) > 1 and index < 0):
        frames = decode_frames(blob, sprites, flags, palette)
        image = make_sheet(frames)
        if verbose:
            print(f"sheet frames  : {len(frames)}  cell={frames[0].size}")
    else:
        if index < 0:
            index = 0
        if not (0 <= index < len(sprites)):
            raise IndexError(f"--index {index} out of range 0..{len(sprites)-1}")
        image = decode_sprite(blob, sprites[index], flags, len(blob), sprites, palette)

    image.save(out)
    if verbose:
        print(f"wrote         : {out}  ({image.size[0]}x{image.size[1]} RGBA)")
        if mismatches:
            print(f"FAILED chain  : {mismatches} sprite(s) did not match packed_bytes")
    if mismatches and not (flags & FLAG_RLE):
        raise ValueError(f"{pl8.name}: {mismatches} sprite(s) span != packed_bytes")
    return image


def export_all(game: Path, dest_dir: Path) -> int:
    files = list_pl8(game)
    if not files:
        raise FileNotFoundError(f"no .PL8 under {game}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    failed: list[tuple[str, str]] = []
    pal_reasons: Counter[str] = Counter()
    print(f"=== export {len(files)} PL8 -> {dest_dir} ===")
    for p in files:
        try:
            pal_path, reason = resolve_palette(p, game)
            pal_reasons[reason.split(":")[0]] += 1
            flags, _unk, sprites, blob = parse_pl8(p, verbose=False)
            palette = load_palette(pal_path, verbose=False)
            frames = decode_frames(blob, sprites, flags, palette)
            if len(frames) == 1:
                image = frames[0]
                out = dest_dir / f"{p.stem}.png"
            else:
                image = make_sheet(frames)
                out = dest_dir / f"{p.stem}_sheet.png"
            image.save(out)
            print(
                f"  {p.name:16s} {len(blob):8d} B  "
                f"fl=0x{flags:04X} n={len(sprites):<4d}  "
                f"pal={pal_path.stem:12s} ({reason:16s})  {out.name}  "
                f"{image.size[0]}x{image.size[1]}"
            )
        except (OSError, ValueError, NotImplementedError, IndexError) as exc:
            failed.append((p.name, str(exc)))
            print(f"  FAILED {p.name}: {exc}")
    print(
        f"done        : {len(files) - len(failed)}/{len(files)}  "
        f"failed={len(failed)}  palettes={dict(pal_reasons)}"
    )
    if failed:
        print("failures    :")
        for name, err in failed:
            print(f"  {name}: {err}")
    return 1 if failed else 0


def inventory(game: Path) -> None:
    files = list_pl8(game)
    pals = list_palettes(game)
    flag_hist: Counter[int] = Counter()
    rle_n = 0
    print(f"=== PL8 inventory ({len(files)})  palettes={len(pals)} ===")
    print(f"{'name':16s} {'size':>8s}  flags    n    spr0          pal")
    for p in files:
        data = p.read_bytes()
        flags, nspr = struct.unpack_from("<HH", data, 0)
        flag_hist[flags] += 1
        if flags & FLAG_RLE:
            rle_n += 1
        w = h = t = -1
        if nspr >= 1 and 8 + 16 <= len(data):
            w, h = struct.unpack_from("<HH", data, 8)
            t = data[20]
        pal_path, reason = resolve_palette(p, game)
        print(
            f"{p.name:16s} {len(data):8d}  0x{flags:04X}  {nspr:4d}  "
            f"{w:3d}x{h:<4d} t={t}  {pal_path.stem} ({reason})"
        )
    print("flag hist   : " + " ".join(f"0x{k:04X}={v}" for k, v in sorted(flag_hist.items())))
    print(f"RLE bit0    : {rle_n}/{len(files)} (community bit; unused on this install)")


def main(argv: list[str] | None = None) -> int:
    default_out = Path(r"C:\Users\Felip\caesar2-re\AHOUSE.png")

    parser = argparse.ArgumentParser(description="Decode Caesar II .PL8 sprites.")
    parser.add_argument("--game", type=Path, default=DEFAULT_GAME)
    parser.add_argument("--pl8", type=Path, default=None)
    parser.add_argument("--pal", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--index", type=int, default=0, help="sprite index to export")
    parser.add_argument(
        "--sheet",
        action="store_true",
        help="export every sprite as one contact sheet",
    )
    parser.add_argument("--inventory", action="store_true")
    parser.add_argument(
        "--export-all",
        action="store_true",
        help="decode every install .PL8 into --images-dir (sheet if n>1)",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=DEFAULT_IMAGES,
        help="preview output directory (default: repo images/)",
    )
    args = parser.parse_args(argv)

    if args.inventory:
        inventory(args.game)
        return 0

    if args.export_all:
        return export_all(args.game, args.images_dir)

    pl8 = args.pl8 or (args.game / "AHOUSE.PL8")
    pal, _reason = resolve_palette(pl8, args.game, args.pal)
    out = args.out or default_out
    export_one(pl8, pal, out, sheet=args.sheet, index=args.index, verbose=True)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, NotImplementedError, IndexError) as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        sys.exit(1)
