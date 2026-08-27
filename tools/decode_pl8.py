#!/usr/bin/env python3
"""Minimal Caesar II .PL8 decoder (Phase 1).

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

Palette .256 is 256 * 3 bytes RGB (no padding, no alpha).
On this install every byte is in 0..63 (VGA 6-bit DAC). The loader
expands to 8-bit with (c << 2) | (c >> 4). Index 0 is emitted as
alpha=0; on AHOUSE that index is almost unused (the grass is not key 0).
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

FILE_HEADER_SIZE = 8
SPRITE_RECORD_SIZE = 16
PALETTE_SIZE = 256 * 3

# Community docs: bit 0 of flags means RLE. AHOUSE has flags=0x0002 (bit 0 clear).
FLAG_RLE = 0x0001

TILE_BITMAP = 0
# 1-4: isometric diamond + optional extra rows (types 2/3/4 only on disk).


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


def load_palette(path: Path) -> list[tuple[int, int, int]]:
    data = path.read_bytes()
    if len(data) != PALETTE_SIZE:
        raise ValueError(
            f"{path.name}: expected {PALETTE_SIZE} bytes (256xRGB), got {len(data)}"
        )
    raw_max = max(data) if data else 0
    scale_6bit = raw_max <= 63
    print(f"palette max   : {raw_max}  ({'VGA 6-bit -> 8-bit' if scale_6bit else 'already 8-bit'})")

    def chan(v: int) -> int:
        return vga6_to_8(v) if scale_6bit else v

    return [
        (chan(data[i]), chan(data[i + 1]), chan(data[i + 2]))
        for i in range(0, PALETTE_SIZE, 3)
    ]


def parse_pl8(
    path: Path, *, print_limit: int = 6
) -> tuple[int, int, list[SpriteRecord], bytes]:
    data = path.read_bytes()
    if len(data) < FILE_HEADER_SIZE + SPRITE_RECORD_SIZE:
        raise ValueError(f"{path.name}: file too small ({len(data)} bytes)")

    flags = u16(data, 0)
    n_sprites = u16(data, 2)
    unknown_04 = u32(data, 4)
    table_end = FILE_HEADER_SIZE + SPRITE_RECORD_SIZE * n_sprites

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
        if i not in show:
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

    if n_sprites > print_limit + 1:
        print(f"  ... ({n_sprites - len(show)} sprites omitted)")

    return flags, unknown_04, sprites, data


def check_offset_chain(sprites: list[SpriteRecord], file_size: int) -> int:
    """Return number of sprites whose payload != width*height."""
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
            if mismatches <= 8:
                print(
                    f"CHAIN BREAK  : sprite[{spr.index}] "
                    f"{spr.width}x{spr.height} type={spr.tile_type} extra={spr.extra_rows} "
                    f"need={need} span={span} delta={span - need}"
                )

    predicted0 = FILE_HEADER_SIZE + SPRITE_RECORD_SIZE * len(sprites)
    last = sprites[-1]
    last_end = last.data_offset + expected_span(sprites, file_size, last.index)
    print(f"offset check  : sprite[0].data_offset={sprites[0].data_offset}  predicted={predicted0}")
    print(f"size histogram: {dict(sorted(sizes.items(), key=lambda kv: -kv[1]))}")
    print(f"tile_type hist: {types}")
    print(f"chain match   : {len(sprites) - mismatches}/{len(sprites)}  (span == packed_bytes)")
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


def decode_bitmap(indices: bytes, width: int, height: int, palette) -> Image.Image:
    img = Image.new("RGBA", (width, height))
    pixels = img.load()
    for y in range(height):
        row = y * width
        for x in range(width):
            idx = indices[row + x]
            r, g, b = palette[idx]
            alpha = 0 if idx == 0 else 255
            pixels[x, y] = (r, g, b, alpha)
    return img


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
        print(f"pixel packed  : {need}  unpacked={spr.unpacked_bytes}  canvas_h={spr.canvas_height}")

    if spr.data_offset + max(span, 0) > file_size or span < 0:
        raise ValueError(
            f"sprite[{spr.index}] data_offset={spr.data_offset} span={span} "
            f"overruns file ({file_size})"
        )

    if flags & FLAG_RLE:
        raise NotImplementedError(
            "flags bit0 is set (RLE per community docs). "
            "Hypothesis of unpacked bitmap does not apply; implement RLE next."
        )

    if span != need:
        print("SIZE MISMATCH : packed-size hypothesis does not fit this sprite.")
        print(f"  available payload = {span}")
        print(f"  packed_bytes      = {need}")
        print(f"  width*height      = {spr.unpacked_bytes}")
        print(f"  difference        = {span - need}")
        raise ValueError(
            f"pixel payload {span} != packed {need} "
            f"({spr.width}x{spr.height} type={spr.tile_type} extra={spr.extra_rows})"
        )

    blob = data[spr.data_offset : spr.data_offset + need]
    if spr.tile_type == TILE_BITMAP:
        return decode_bitmap(blob, spr.width, spr.height, palette)
    if spr.tile_type in (1, 2, 3, 4):
        indices, w, h = unpack_iso(blob, spr)
        return decode_bitmap(indices, w, h, palette)
    raise NotImplementedError(f"tile_type={spr.tile_type} is not implemented")


def main(argv: list[str] | None = None) -> int:
    default_game = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
    default_out = Path(r"C:\Users\Felip\caesar2-re\AHOUSE.png")

    parser = argparse.ArgumentParser(description="Decode a Caesar II .PL8 sprite.")
    parser.add_argument("--pl8", type=Path, default=default_game / "AHOUSE.PL8")
    parser.add_argument("--pal", type=Path, default=default_game / "AHOUSE.256")
    parser.add_argument("--out", type=Path, default=default_out)
    parser.add_argument("--index", type=int, default=0, help="sprite index to export")
    parser.add_argument(
        "--sheet",
        action="store_true",
        help="export every sprite as one contact sheet",
    )
    args = parser.parse_args(argv)

    print("=== PL8 decode ===")
    flags, _unknown_04, sprites, blob = parse_pl8(args.pl8)
    mismatches = check_offset_chain(sprites, len(blob))
    if sprites[0].data_offset != FILE_HEADER_SIZE + SPRITE_RECORD_SIZE * len(sprites):
        print(
            "WARNING       : dataOffset != 8+16*nSprites. "
            "Header-size hypothesis needs revisiting."
        )

    palette = load_palette(args.pal)
    print(f"palette       : {args.pal.name}  256 RGB  index0={palette[0]}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.sheet:
        frames = [
            decode_sprite(
                blob, spr, flags, len(blob), sprites, palette, verbose=False
            )
            for spr in sprites
        ]
        image = make_sheet(frames)
        print(f"sheet frames  : {len(frames)}  cell={frames[0].size}")
    else:
        if not (0 <= args.index < len(sprites)):
            raise IndexError(f"--index {args.index} out of range 0..{len(sprites)-1}")
        image = decode_sprite(
            blob, sprites[args.index], flags, len(blob), sprites, palette
        )

    image.save(args.out)
    print(f"wrote         : {args.out}  ({image.size[0]}x{image.size[1]} RGBA)")
    if mismatches:
        print(f"FAILED chain  : {mismatches} sprite(s) did not match packed_bytes")
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, NotImplementedError, IndexError) as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        sys.exit(1)
