#!/usr/bin/env python3
"""Caesar II .SAV map / header dump.

This install's saves are always 225745 bytes =
    1745-byte header + 35 planes * (80*80) bytes.

City size 80x80 is the community figure; the 6400-byte plane is measured
(plane 6 is 6400 consecutive zeros in FELIPE01, FELIPE02, and LASTYEAR).
That layout is structure-of-arrays, not 35-byte records.

One-command dump (header + plane stats + PNGs):

    python tools/probe_sav_map.py --dump --out sav_preview
"""

from __future__ import annotations

import argparse
import colorsys
import struct
from collections import Counter
from pathlib import Path

from PIL import Image

DEFAULT_GAME = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")
SAV_SIZE = 225745
HEADER_SIZE = 1745
MAP_W = 80
MAP_H = 80
PLANE_SIZE = MAP_W * MAP_H  # 6400
N_PLANES = 35
SCALE = 8
CITYFIXT_SPRITES = 140  # CITYFIXT.PL8 n_sprites (REVERSE.md E15)
HOUSES1_SPRITES = 106
BUILD1A_SPRITES = 123
TAIL_HINT = 176128  # leftover 40x40 hypothesis (disproved; kept for --legacy)


def u16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def i16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<h", buf, off)[0]


def i32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def load(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) != SAV_SIZE:
        raise ValueError(f"{path.name}: {len(data)} bytes, expected {SAV_SIZE}")
    return data


def find_saves(folder: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[Path] = set()
    for pat in ("*.SAV", "*.sav"):
        for p in sorted(folder.glob(pat)):
            key = p.resolve()
            if key in seen:
                continue
            seen.add(key)
            found.append(p)
    return found


def pl8_sprite_count(path: Path) -> int | None:
    if not path.is_file() or path.stat().st_size < 4:
        return None
    return u16(path.read_bytes()[:4], 2)


def planes_of(data: bytes) -> list[bytes]:
    start = HEADER_SIZE
    return [data[start + i * PLANE_SIZE : start + (i + 1) * PLANE_SIZE] for i in range(N_PLANES)]


def city_block_start(hdr: bytes) -> int:
    """First nonzero byte after the leading 16-byte scalar prefix."""
    for i in range(16, len(hdr)):
        if hdr[i]:
            return i
    return -1


def ascii_runs(buf: bytes, min_len: int = 4) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    i = 0
    n = len(buf)
    while i < n:
        if 32 <= buf[i] < 127:
            j = i
            while j < n and 32 <= buf[j] < 127:
                j += 1
            if j - i >= min_len:
                out.append((i, buf[i : j].decode("ascii")))
            i = j
        else:
            i += 1
    return out


def occupancy_bbox(plane: bytes, width: int = MAP_W) -> tuple[int, int, int, int, int]:
    height = len(plane) // width
    xs: list[int] = []
    ys: list[int] = []
    for y in range(height):
        row = plane[y * width : (y + 1) * width]
        for x, v in enumerate(row):
            if v:
                xs.append(x)
                ys.append(y)
    if not xs:
        return (-1, -1, -1, -1, 0)
    return (min(xs), min(ys), max(xs), max(ys), len(xs))


def ascii_occupancy(plane: bytes, width: int = MAP_W, step: int = 2) -> str:
    height = len(plane) // width
    lines = []
    for y in range(0, height, step):
        chars = []
        for x in range(0, width, step):
            block = False
            for dy in range(step):
                if y + dy >= height:
                    break
                row = plane[(y + dy) * width : (y + dy + 1) * width]
                if any(row[x : x + step]):
                    block = True
                    break
            chars.append("#" if block else ".")
        lines.append("".join(chars))
    return "\n".join(lines)


def neighbor_stats(plane: bytes, width: int = MAP_W) -> tuple[float, float, float]:
    """Return (same_frac, mean_abs_diff, filled_agree) over 4-neighbors."""
    height = len(plane) // width
    same = 0
    tot = 0
    adiff = 0
    fill_same = 0
    fill_tot = 0
    for y in range(height):
        for x in range(width):
            v = plane[y * width + x]
            for dx, dy in ((1, 0), (0, 1)):
                nx, ny = x + dx, y + dy
                if nx >= width or ny >= height:
                    continue
                w = plane[ny * width + nx]
                tot += 1
                adiff += abs(v - w)
                if v == w:
                    same += 1
                if v or w:
                    fill_tot += 1
                    if v == w:
                        fill_same += 1
    if tot == 0:
        return (0.0, 0.0, 0.0)
    return (
        same / tot,
        adiff / tot,
        (fill_same / fill_tot) if fill_tot else 0.0,
    )


def row_col_density(plane: bytes, width: int = MAP_W) -> tuple[list[int], list[int]]:
    height = len(plane) // width
    rows = [sum(1 for b in plane[y * width : (y + 1) * width] if b) for y in range(height)]
    cols = [
        sum(1 for y in range(height) if plane[y * width + x])
        for x in range(width)
    ]
    return rows, cols


def band_score(counts: list[int]) -> tuple[float, int, int]:
    """How concentrated nonzero cells are in a contiguous band.

    Returns (max_window_frac, best_start, best_width) using the smallest
    window that holds >= 80% of occupied rows/cols.
    """
    total = sum(counts)
    if total == 0:
        return (0.0, -1, 0)
    n = len(counts)
    best_w = n
    best_i = 0
    target = 0.80 * total
    for i in range(n):
        acc = 0
        for w in range(1, n - i + 1):
            acc += counts[i + w - 1]
            if acc >= target and w < best_w:
                best_w = w
                best_i = i
                break
    return (1.0 - (best_w / n), best_i, best_w)


def coord_hits(plane: bytes, width: int = MAP_W) -> tuple[int, int, int]:
    """Count cells where value == x, == y, or == x+y (coord-like planes)."""
    height = len(plane) // width
    eq_x = eq_y = eq_sum = 0
    for y in range(height):
        base = y * width
        for x in range(width):
            v = plane[base + x]
            if v == x:
                eq_x += 1
            if v == y:
                eq_y += 1
            if v == (x + y) & 0xFF:
                eq_sum += 1
    return eq_x, eq_y, eq_sum


def bits_used(plane: bytes) -> int:
    acc = 0
    for b in plane:
        acc |= b
    return acc


def classify_plane(plane: bytes) -> str:
    cnt = Counter(plane)
    uniq = len(cnt)
    nz = sum(1 for b in plane if b)
    mx = max(plane) if plane else 0
    same, mad, fill_ag = neighbor_stats(plane)
    mask = bits_used(plane)
    pop = bin(mask).count("1")
    eq_x, eq_y, _ = coord_hits(plane)
    rows, cols = row_col_density(plane)
    row_band, _, _ = band_score(rows)
    col_band, _, _ = band_score(cols)

    if nz == 0:
        return "empty"
    if eq_x >= 5000:
        return "coord-x"
    if eq_y >= 5000:
        return "coord-y"
    if uniq <= 8 and mx <= 16 and same >= 0.70 and nz >= 2000:
        return "enum-smooth (terrain/height?)"
    if uniq <= 16 and mx < CITYFIXT_SPRITES and same >= 0.55 and nz >= 1500:
        return "enum (terrain tile IDs?)"
    if uniq <= 24 and mx < CITYFIXT_SPRITES and nz >= 800:
        return "small-enum (tile / overlay IDs?)"
    if row_band >= 0.45 and col_band < 0.25:
        return "horizontal-band (river/coast?)"
    if col_band >= 0.45 and row_band < 0.25:
        return "vertical-band (river/coast?)"
    if uniq >= 80 and mx >= 200 and fill_ag < 0.25:
        return "high-entropy (IDs / packed?)"
    if pop <= 4 and uniq <= 16 and mx == mask:
        return "bitfield-like"
    if nz <= 80:
        return "sparse-points"
    if same >= 0.75:
        return "smooth-field"
    if fill_ag >= 0.35 and 20 <= uniq <= 80:
        return "clustered-IDs (buildings?)"
    return f"mixed (uniq={uniq} mad={mad:.2f})"


def enum_color(v: int) -> tuple[int, int, int]:
    if v == 0:
        return (0, 0, 0)
    h = ((v * 0.141) % 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, 0.75, 1.0)
    return (int(r * 255), int(g * 255), int(b * 255))


def render_gray(plane: bytes, scale: int = SCALE) -> Image.Image:
    mx = max(plane) if plane and max(plane) else 1
    img = Image.new("L", (MAP_W, MAP_H))
    img.putdata([int(b * 255 / mx) for b in plane])
    return img.resize((MAP_W * scale, MAP_H * scale), Image.Resampling.NEAREST)


def render_occ(plane: bytes, scale: int = SCALE) -> Image.Image:
    img = Image.new("L", (MAP_W, MAP_H))
    img.putdata([255 if b else 0 for b in plane])
    return img.resize((MAP_W * scale, MAP_H * scale), Image.Resampling.NEAREST)


def render_enum(plane: bytes, scale: int = SCALE) -> Image.Image:
    img = Image.new("RGB", (MAP_W, MAP_H))
    img.putdata([enum_color(b) for b in plane])
    return img.resize((MAP_W * scale, MAP_H * scale), Image.Resampling.NEAREST)


def write_pngs(stem: str, planes: list[bytes], out_dir: Path) -> Path:
    dest = out_dir / stem
    dest.mkdir(parents=True, exist_ok=True)
    thumbs: list[Image.Image] = []
    for i, plane in enumerate(planes):
        gray = render_gray(plane)
        occ = render_occ(plane)
        enu = render_enum(plane)
        gray.save(dest / f"plane_{i:02d}_gray.png")
        occ.save(dest / f"plane_{i:02d}_occ.png")
        enu.save(dest / f"plane_{i:02d}_enum.png")
        label = Image.new("RGB", (enu.width, enu.height + 18), (16, 16, 16))
        label.paste(enu, (0, 18))
        thumbs.append(enu)
    cols = 7
    rows = (N_PLANES + cols - 1) // cols
    tw, th = thumbs[0].size
    sheet = Image.new("RGB", (cols * tw, rows * th), (8, 8, 8))
    for i, im in enumerate(thumbs):
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet.save(dest / "montage_enum.png")
    # occupancy montage
    occs = [render_occ(p) for p in planes]
    sheet_o = Image.new("RGB", (cols * tw, rows * th), (8, 8, 8))
    for i, im in enumerate(occs):
        sheet_o.paste(im.convert("RGB"), ((i % cols) * tw, (i // cols) * th))
    sheet_o.save(dest / "montage_occ.png")
    return dest


def dump_header(name: str, data: bytes) -> None:
    hdr = data[:HEADER_SIZE]
    print(f"-- {name} header --")
    print(f"  size         : {len(data)}")
    print(f"  hex[0:32]    : {hdr[:32].hex()}")
    print(
        "  u16[0:16]    : "
        + " ".join(f"{u16(hdr, i):5d}" for i in range(0, 16, 2))
    )
    print(
        "  u32[0:16]    : "
        + " ".join(f"{u32(hdr, i):10d}" for i in range(0, 16, 4))
    )
    print(f"  u8@1         : {hdr[1]}  (named-save flag / difficulty?)")
    print(f"  u32@8        : {u32(hdr, 8)}  (year BC?)")
    print(f"  u32@12       : {u32(hdr, 12)}  (opaque scalar)")
    nz = sum(1 for b in hdr if b)
    start = city_block_start(hdr)
    print(f"  header nz    : {nz} / {HEADER_SIZE}")
    print(f"  city-block @ : {start}")
    runs = ascii_runs(hdr, 4)
    print(f"  ascii runs   : {len(runs)}")
    for off, s in runs[:12]:
        print(f"    @{off:4d}  {s!r}")

    if start < 0:
        return
    block = hdr[start:]
    print(f"  relative u8 (first 64 of block @{start}):")
    print("   " + " ".join(f"{b:02X}" for b in block[:64]))
    print("  relative u16 at +0..+40 (may be unaligned to file):")
    for rel in range(0, min(40, len(block) - 1), 2):
        print(f"    +{rel:3d}  u16={u16(block, rel):6d}  i16={i16(block, rel):7d}")

    # money / pop candidates inside the block: u16 in 200..30000
    print("  clean u16-in-block (even rel, high byte 0, value 50..30000):")
    for rel in range(0, len(block) - 1, 2):
        v = u16(block, rel)
        if 50 <= v <= 30000 and (v >> 8) == 0:
            print(f"    +{rel:4d} (abs {start + rel:4d})  u16={v}")
    print("  clean i32-in-block (rel % 4 == 0, |v| 50..200000, high 16 zero or sign-extend):")
    for rel in range(0, len(block) - 3, 4):
        v = i32(block, rel)
        hi = (v >> 16) & 0xFFFF
        if 50 <= abs(v) <= 200000 and hi in (0, 0xFFFF):
            print(f"    +{rel:4d} (abs {start + rel:4d})  i32={v}")


def dump_plane_stats(name: str, planes: list[bytes], sprite_n: dict[str, int]) -> None:
    print(f"\n=== planes {name} ===")
    print(
        f"{'p':>3} {'off':>7} {'nz':>5} {'uniq':>5} {'max':>4} "
        f"{'1-139':>6} {'140-247':>8} {'248+':>5} "
        f"{'same':>6} {'p80':>6}  class"
    )
    city = sprite_n.get("CITYFIXT", CITYFIXT_SPRITES)
    houses = sprite_n.get("HOUSES1", HOUSES1_SPRITES)
    build = sprite_n.get("BUILD1A", BUILD1A_SPRITES)
    for i, plane in enumerate(planes):
        cnt = Counter(plane)
        nz = sum(1 for b in plane if b)
        mx = max(plane) if plane else 0
        lo = sum(1 for b in plane if 1 <= b < city)
        mid = sum(1 for b in plane if city <= b < 248)
        hi = sum(1 for b in plane if b >= 248)
        same, _mad, _ = neighbor_stats(plane)
        p80 = 0.0
        if len(plane) > MAP_W:
            n = len(plane) - MAP_W
            p80 = sum(1 for k in range(n) if plane[k] == plane[k + MAP_W]) / n
        klass = classify_plane(plane)
        print(
            f"{i:3d} {HEADER_SIZE + i * PLANE_SIZE:7d} {nz:5d} {len(cnt):5d} "
            f"{mx:4d} {lo:6d} {mid:8d} {hi:5d} {same:6.3f} {p80:6.3f}  {klass}"
        )
    print("\n  top values / bbox / CITYFIXT-fit:")
    for i, plane in enumerate(planes):
        cnt = Counter(plane)
        x0, y0, x1, y1, n = occupancy_bbox(plane)
        mx = max(plane) if plane else 0
        fit_city = mx < city
        fit_house = mx < houses
        fit_build = mx < build
        top = ", ".join(f"{v}:{c}" for v, c in cnt.most_common(6))
        print(
            f"  p[{i:2d}] bbox=({x0},{y0})-({x1},{y1}) nz={n:4d}  "
            f"max<{city}? {str(fit_city):5s}  houses? {str(fit_house):5s}  "
            f"build? {str(fit_build):5s}  top=[{top}]"
        )


def dump_cross(blobs: dict[str, bytes]) -> None:
    names = list(blobs.keys())
    if len(names) < 2:
        return
    print("\n=== cross-save plane identity ===")
    planes = {n: planes_of(blobs[n]) for n in names}

    def short(n: str) -> str:
        if n.upper().startswith("LAST"):
            return "LY"
        digits = "".join(ch for ch in n if ch.isdigit())
        return digits[-2:] if digits else n[:4]

    header = "p"
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            header += f"  {short(names[i])}={short(names[j])}"
    print("  " + header)
    for p in range(N_PLANES):
        bits = [f"{p:2d}"]
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = planes[names[i]][p], planes[names[j]][p]
                same = sum(1 for x, y in zip(a, b) if x == y) / PLANE_SIZE
                bits.append(f"{same:7.1%}")
        print("  " + "  ".join(bits))

    print("\n=== pairwise plane correlation (first save, neighbor-plane) ===")
    first = planes[names[0]]
    print("  adjacent-plane equal-frac and XOR-popcount (are they lo/hi u16?):")
    for i in range(N_PLANES - 1):
        a, b = first[i], first[i + 1]
        eq = sum(1 for x, y in zip(a, b) if x == y) / PLANE_SIZE
        both_nz = sum(1 for x, y in zip(a, b) if x and y)
        # treat (a,b) as u16 LE and see uniqueness
        u16s = [a[k] | (b[k] << 8) for k in range(PLANE_SIZE)]
        print(
            f"  p[{i:2d}]+[{i+1:2d}] equal={eq:.1%} both_nz={both_nz:5d}  "
            f"u16-unique={len(set(u16s)):5d}  u16-max={max(u16s)}"
        )


def dump_header_compare(blobs: dict[str, bytes]) -> None:
    print("\n=== header city-block overlay (relative) ===")
    starts = {n: city_block_start(blobs[n][:HEADER_SIZE]) for n in blobs}
    for n, s in starts.items():
        print(f"  {n}: block @{s}")
    names = list(blobs.keys())
    # compare relative bytes where both blocks exist
    if len(names) < 2:
        return
    max_len = min(
        HEADER_SIZE - starts[n] if starts[n] >= 0 else 0 for n in names
    )
    print(f"  comparable relative length: {max_len}")
    print("  rel   " + "  ".join(f"{n[:10]:>10s}" for n in names) + "  note")
    for rel in range(max_len):
        vals = [blobs[n][starts[n] + rel] for n in names]
        if any(vals):
            extra = ""
            if len(set(vals)) == 1:
                extra = "  SAME"
            print(
                f"  +{rel:3d} "
                + "  ".join(f"{v:10d}" for v in vals)
                + extra
            )


def run_dump(folder: Path, out_dir: Path, write_png: bool) -> int:
    saves = find_saves(folder)
    print("=== SAV inventory ===")
    if not saves:
        print(f"  no .SAV under {folder}")
        return 1
    blobs: dict[str, bytes] = {}
    for path in saves:
        data = path.read_bytes()
        ok = len(data) == SAV_SIZE
        print(
            f"  {path.name:16s}  {len(data):7d} B  "
            f"{'OK' if ok else 'SIZE MISMATCH'}  "
            f"hex[0:16]={data[:16].hex()}"
        )
        if ok:
            blobs[path.stem] = data
        else:
            print(f"    WARNING: expected {SAV_SIZE}; skipped")

    sprite_n = {
        "CITYFIXT": pl8_sprite_count(folder / "CITYFIXT.PL8") or CITYFIXT_SPRITES,
        "HOUSES1": pl8_sprite_count(folder / "HOUSES1.PL8") or HOUSES1_SPRITES,
        "BUILD1A": pl8_sprite_count(folder / "BUILD1A.PL8") or BUILD1A_SPRITES,
        "OVERLAY1": pl8_sprite_count(folder / "OVERLAY1.PL8") or 0,
        "LANDFILL": pl8_sprite_count(folder / "LANDFILL.PL8") or 0,
    }
    print("\n=== PL8 sprite counts (tile-ID hypothesis) ===")
    for k, v in sprite_n.items():
        print(f"  {k:12s}  {v}")

    print("\n=== layout ===")
    print(
        f"  {HEADER_SIZE} + {N_PLANES} x {PLANE_SIZE} = "
        f"{HEADER_SIZE + N_PLANES * PLANE_SIZE}  (file {SAV_SIZE})"
    )

    print("\n=== headers ===")
    for name, data in blobs.items():
        dump_header(name, data)

    dump_header_compare(blobs)

    for name, data in blobs.items():
        dump_plane_stats(name, planes_of(data), sprite_n)

    dump_cross(blobs)

    print("\n=== plane 6 zero check ===")
    for name, data in blobs.items():
        p6 = planes_of(data)[6]
        nz = sum(1 for b in p6 if b)
        print(f"  {name}: plane6 nz={nz} / {PLANE_SIZE}  all_zero={nz == 0}")

    if write_png:
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"\n=== PNG write -> {out_dir.resolve()} ===")
        for name, data in blobs.items():
            dest = write_pngs(name, planes_of(data), out_dir)
            print(f"  {dest}")
        # cross-save overlay of most-divergent planes
        if len(blobs) >= 2:
            names = list(blobs.keys())
            a, b = names[0], names[1]
            pa, pb = planes_of(blobs[a]), planes_of(blobs[b])
            dest = out_dir / f"_diff_{a}_vs_{b}"
            dest.mkdir(parents=True, exist_ok=True)
            for i in range(N_PLANES):
                diff = bytes(x ^ y for x, y in zip(pa[i], pb[i]))
                render_occ(diff).save(dest / f"plane_{i:02d}_xor.png")
            print(f"  {dest} (XOR occupancy)")

    print("\n=== ASCII occupancy (2x2) first save, selected planes ===")
    first_name = next(iter(blobs))
    first = planes_of(blobs[first_name])
    for i in (0, 1, 3, 5, 6, 7, 28, 29, 30, 31, 34):
        plane = first[i]
        x0, y0, x1, y1, n = occupancy_bbox(plane)
        print(f"-- {first_name} p[{i}] bbox=({x0},{y0})-({x1},{y1}) nz={n} --")
        print(ascii_occupancy(plane, MAP_W, 2))

    return 0


# --- legacy 40x40 hunt (kept so older notes still run) ---

def factor_grids(file_size: int) -> list[tuple[int, int, int, int, int]]:
    widths = (32, 36, 40, 42, 44, 48, 50, 52, 60, 64, 72, 80, 100, 120, 128)
    out = []
    for w in widths:
        cells = w * w
        for rec in range(1, 81):
            for layers in range(1, 12):
                payload = cells * rec * layers
                if payload > file_size:
                    continue
                header = file_size - payload
                if 0 <= header <= 4096 or header in (
                    17,
                    145,
                    1024,
                    4096,
                    49152,
                    TAIL_HINT,
                    file_size - 49600,
                    file_size - 49617,
                ):
                    if header <= 8192 or abs(header - TAIL_HINT) < 64:
                        out.append((header, w, cells, rec, layers))
    out.append((TAIL_HINT, 40, 1600, 31, 1))
    out.append((file_size - 40 * 40 * 31, 40, 1600, 31, 1))
    seen = set()
    uniq = []
    for row in out:
        if row not in seen:
            seen.add(row)
            uniq.append(row)
    return uniq


def period_score(buf: bytes, stride: int, sample: int = 8000) -> float:
    if stride <= 0 or stride >= len(buf):
        return 0.0
    n = min(sample, len(buf) - stride)
    if n <= 0:
        return 0.0
    hit = sum(1 for i in range(n) if buf[i] == buf[i + stride])
    return hit / n


def record_histogram(buf: bytes, rec: int, field: int = 0) -> Counter:
    c: Counter = Counter()
    if rec <= 0 or field >= rec:
        return c
    n = len(buf) // rec
    for i in range(n):
        c[buf[i * rec + field]] += 1
    return c


def zero_run_starts(buf: bytes, min_len: int = 256) -> list[tuple[int, int]]:
    runs = []
    i = 0
    n = len(buf)
    while i < n:
        if buf[i] == 0:
            j = i
            while j < n and buf[j] == 0:
                j += 1
            if j - i >= min_len:
                runs.append((i, j - i))
            i = j
        else:
            i += 1
    return runs


def density_windows(buf: bytes, step: int = 1024) -> list[tuple[int, int, int]]:
    out = []
    for off in range(0, len(buf), step):
        chunk = buf[off : off + step]
        nz = sum(1 for b in chunk if b)
        out.append((off, nz, len(chunk)))
    return out


def same_at(a: bytes, b: bytes, start: int, length: int) -> float:
    chunk_a = a[start : start + length]
    chunk_b = b[start : start + length]
    n = min(len(chunk_a), len(chunk_b))
    if n == 0:
        return 0.0
    return sum(1 for x, y in zip(chunk_a, chunk_b) if x == y) / n


def run_legacy(folder: Path) -> int:
    names = ("FELIPE01.SAV", "FELIPE02.SAV", "LASTYEAR.SAV")
    blobs = {n: load(folder / n) for n in names}
    a, b, c = (blobs[n] for n in names)

    print("=== sizes / headers ===")
    for n, data in blobs.items():
        u0, u8v, u12 = u32(data, 0), u32(data, 8), u32(data, 12)
        print(f"{n}: u32@0={u0} u32@8={u8v} u32@12={u12}")

    print("\n=== long zero runs (>=256) FELIPE01 ===")
    for start, ln in zero_run_starts(a, 256)[:30]:
        print(f"  @{start:6d}  {ln:6d} B")
    print(f"  total runs: {len(zero_run_starts(a, 256))}")

    print("\n=== exact fit candidates (header<=8KiB or near tail hint) ===")
    for header, w, cells, rec, layers in factor_grids(SAV_SIZE):
        payload = cells * rec * layers
        if header > 8192 and abs(header - TAIL_HINT) > 32:
            continue
        print(
            f"  header={header:6d}  {w}x{w}  rec={rec:2d}  layers={layers}  "
            f"payload={payload}"
        )

    print("\n=== SoA 80x80 byte planes from header 1745 (35-byte tile / 35 planes) ===")
    start = SAV_SIZE - 80 * 80 * 35
    print(f"  start={start}")
    for i in range(N_PLANES):
        off = start + i * PLANE_SIZE
        plane = a[off : off + PLANE_SIZE]
        cnt = Counter(plane)
        nz = sum(1 for x in plane if x)
        print(
            f"  plane[{i:2d}] @{off}  nz={nz}/6400  unique={len(cnt)}  "
            f"top={cnt.most_common(6)}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump Caesar II .SAV header + 80x80 planes.")
    parser.add_argument("--dir", type=Path, default=DEFAULT_GAME)
    parser.add_argument(
        "--dump",
        action="store_true",
        default=True,
        help="header + plane stats + PNGs (default)",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="old 40x40 / periodicity hunt",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("sav_preview"),
        help="PNG output folder (gitignored)",
    )
    parser.add_argument("--no-png", action="store_true")
    args = parser.parse_args(argv)
    if args.legacy:
        return run_legacy(args.dir)
    return run_dump(args.dir, args.out, write_png=not args.no_png)


if __name__ == "__main__":
    raise SystemExit(main())
