#!/usr/bin/env python3
"""Parse Caesar II PS.EXE: MZ stub + DOS/16M BW chain + Watcom LE.

Reads the retail file in-place. Does not copy the EXE into the repo.

Container measured on v1.1A (1995-10-04, 1_040_111 bytes):

    0x000000  MZ real-mode stub (DOS/4GW launcher; size from e_cp/e_cblp)
    0x00F474  BW #1  DOS/16M EXP named VMM.EXP (extender kernel)
    0x01E0C4  BW #2  DOS/16M EXP (next overlay)
    0x037D4C  LE     Watcom C/C++32 game image (2 objects, page 4096)

Ghidra/IDA/radare2 are not required. Optional later import: extract the
LE blob (file offset of the LE signature through EOF) or load the mapped
image this module writes.
"""

from __future__ import annotations

import argparse
import struct
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_EXE = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2\PS.EXE")
EXPECTED_SIZE = 1_040_111

# Object flags (OS/2 LE / Watcom)
OBJ_READABLE = 0x0001
OBJ_WRITABLE = 0x0002
OBJ_EXECUTABLE = 0x0004
OBJ_RESOURCE = 0x0008
OBJ_DISCARDABLE = 0x0010
OBJ_SHARED = 0x0020
OBJ_PRELOAD = 0x0040
OBJ_INVALID = 0x0080
OBJ_ZEROFILL = 0x0100
OBJ_RESIDENT = 0x0200
OBJ_CONTIG = 0x0300
OBJ_LONG_LOCK = 0x0400
OBJ_ALIAS_16_16 = 0x1000
OBJ_BIG = 0x2000
OBJ_CONFORMING = 0x4000
OBJ_IOPL = 0x8000

PAGE_LEGAL = 0
PAGE_ITERATED = 1
PAGE_INVALID = 2
PAGE_ZEROFILL = 3
PAGE_RANGE = 4
PAGE_COMPRESSED = 5

OS_NAMES = {1: "OS/2", 2: "Windows", 3: "DOS 4.x (EU)", 4: "Windows 386"}
CPU_NAMES = {1: "286", 2: "386", 3: "486", 4: "Pentium"}


def u8(buf: bytes, off: int) -> int:
    return buf[off]


def u16(buf: bytes, off: int) -> int:
    return struct.unpack_from("<H", buf, off)[0]


def u24(buf: bytes, off: int) -> int:
    """Little-endian 24-bit (generic)."""
    return buf[off] | (buf[off + 1] << 8) | (buf[off + 2] << 16)


def u24be(buf: bytes, off: int) -> int:
    """Big-endian 24-bit — LE object page-map page numbers (this EXE)."""
    return (buf[off] << 16) | (buf[off + 1] << 8) | buf[off + 2]


def u32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def i32(buf: bytes, off: int) -> int:
    return struct.unpack_from("<i", buf, off)[0]


def mz_image_size(data: bytes, off: int = 0) -> int:
    last = u16(data, off + 2)
    pages = u16(data, off + 4)
    if pages == 0:
        return 0
    if last == 0:
        return pages * 512
    return (pages - 1) * 512 + last


def flag_names(flags: int) -> str:
    parts = []
    if flags & OBJ_READABLE:
        parts.append("R")
    if flags & OBJ_WRITABLE:
        parts.append("W")
    if flags & OBJ_EXECUTABLE:
        parts.append("X")
    if flags & OBJ_PRELOAD:
        parts.append("preload")
    if flags & OBJ_ZEROFILL:
        parts.append("zerofill")
    if flags & OBJ_BIG:
        parts.append("big32")
    if flags & OBJ_SHARED:
        parts.append("shared")
    extra = flags & ~(
        OBJ_READABLE
        | OBJ_WRITABLE
        | OBJ_EXECUTABLE
        | OBJ_PRELOAD
        | OBJ_ZEROFILL
        | OBJ_BIG
        | OBJ_SHARED
    )
    if extra:
        parts.append(f"+{extra:#x}")
    return "|".join(parts) if parts else f"{flags:#x}"


@dataclass
class BwOverlay:
    offset: int
    next_header: int
    exp_path: str
    raw_size: int


@dataclass
class LeObject:
    index: int  # 1-based
    virtual_size: int
    base: int
    flags: int
    page_map_index: int  # 1-based
    page_count: int
    reserved: int

    @property
    def end(self) -> int:
        return self.base + self.virtual_size


@dataclass
class LeHeader:
    file_offset: int
    signature: bytes
    byte_order: int
    word_order: int
    level: int
    cpu: int
    os: int
    version: int
    module_flags: int
    num_pages: int
    cs_object: int
    eip: int
    ss_object: int
    esp: int
    page_size: int
    last_page: int
    fixup_size: int
    loader_size: int
    object_table_off: int
    num_objects: int
    page_map_off: int
    iterate_off: int
    resource_off: int
    num_resources: int
    resident_names_off: int
    entry_off: int
    directives_off: int
    num_directives: int
    fixup_page_off: int
    fixup_record_off: int
    import_mod_off: int
    num_imports: int
    import_proc_off: int
    page_cksum_off: int
    data_pages_off: int
    preload_pages: int
    nonres_names_off: int
    nonres_names_len: int
    auto_ds: int
    debug_off: int
    debug_len: int
    heap_size: int
    stack_size: int


@dataclass
class MappedImage:
    """Linear image after page assembly (fixups optional)."""

    objects: list[LeObject]
    # va -> (object_index, offset_in_object)
    pages_loaded: int
    image: bytearray
    base: int
    size: int
    file_of_va: dict[int, int] = field(default_factory=dict)  # first byte of each page
    va_of_file: dict[int, int] = field(default_factory=dict)
    fixups: list[tuple[int, int, int]] = field(default_factory=list)  # va, target_va, src_type
    strings: list[tuple[int, str]] = field(default_factory=list)

    def va_to_off(self, va: int) -> int | None:
        if va < self.base or va >= self.base + self.size:
            return None
        return va - self.base

    def read_u32(self, va: int) -> int:
        off = self.va_to_off(va)
        if off is None:
            raise ValueError(f"VA {va:#x} out of image")
        return u32(self.image, off)

    def contains(self, va: int) -> bool:
        return self.base <= va < self.base + self.size

    def object_at(self, va: int) -> LeObject | None:
        for obj in self.objects:
            if obj.base <= va < obj.end:
                return obj
        return None


@dataclass
class PsExe:
    path: Path
    data: bytes
    mz_stub_size: int
    bw_overlays: list[BwOverlay]
    le: LeHeader
    objects: list[LeObject]
    page_map: list[tuple[int, int]]  # (page_num_1based, flags)
    module_name: str
    resident_names: list[tuple[str, int]]
    mapped: MappedImage | None = None


def parse_bw(data: bytes, off: int) -> BwOverlay:
    if data[off : off + 2] != b"BW":
        raise ValueError(f"not BW at {off:#x}: {data[off:off+4]!r}")
    # Tenberry DOS/16M: next overlay pointer at +0x1C (measured: BW1 -> 0x1E0C4).
    next_header = u32(data, off + 0x1C)
    # EXP path is a 13-byte 8.3 name at +0x70 (VMM.EXP on this file).
    raw = data[off + 0x70 : off + 0x70 + 13]
    exp_path = raw.split(b"\x00", 1)[0].decode("ascii", errors="replace")
    end = next_header if 0 < next_header <= len(data) else len(data)
    return BwOverlay(
        offset=off,
        next_header=next_header,
        exp_path=exp_path,
        raw_size=max(0, end - off),
    )


def find_le_header(data: bytes) -> int:
    """Scan for a Watcom-style LE (endian 0, 386, page 4096, 1..32 objects)."""
    best = None
    i = 0
    n = len(data) - 0xB0
    while i < n:
        j = data.find(b"LE", i)
        if j < 0 or j > n:
            break
        if _le_score(data, j) >= 12:
            best = j
            break
        i = j + 2
    if best is None:
        raise ValueError("no plausible LE header in PS.EXE")
    return best


def _le_score(data: bytes, off: int) -> int:
    if off + 0xB0 > len(data) or data[off : off + 2] != b"LE":
        return 0
    if data[off + 2] != 0 or data[off + 3] != 0:
        return 0
    level = u32(data, off + 4)
    cpu = u16(data, off + 8)
    os_ = u16(data, off + 10)
    pages = u32(data, off + 0x14)
    page = u32(data, off + 0x28)
    nobj = u32(data, off + 0x44)
    score = 0
    if level in (0, 1):
        score += 1
    if cpu in (1, 2, 3, 4):
        score += 2
    if os_ in (1, 2, 3, 4):
        score += 2
    if page == 4096:
        score += 4
    if 1 <= nobj <= 32:
        score += 2
    if 1 <= pages <= 4096:
        score += 2
    return score


def parse_le_header(data: bytes, off: int) -> LeHeader:
    o = off
    return LeHeader(
        file_offset=off,
        signature=data[o : o + 2],
        byte_order=u8(data, o + 2),
        word_order=u8(data, o + 3),
        level=u32(data, o + 4),
        cpu=u16(data, o + 8),
        os=u16(data, o + 10),
        version=u32(data, o + 12),
        module_flags=u32(data, o + 16),
        num_pages=u32(data, o + 20),
        cs_object=u32(data, o + 24),
        eip=u32(data, o + 28),
        ss_object=u32(data, o + 32),
        esp=u32(data, o + 36),
        page_size=u32(data, o + 40),
        last_page=u32(data, o + 44),
        fixup_size=u32(data, o + 48),
        loader_size=u32(data, o + 56),
        object_table_off=u32(data, o + 64),
        num_objects=u32(data, o + 68),
        page_map_off=u32(data, o + 72),
        iterate_off=u32(data, o + 76),
        resource_off=u32(data, o + 80),
        num_resources=u32(data, o + 84),
        resident_names_off=u32(data, o + 88),
        entry_off=u32(data, o + 92),
        directives_off=u32(data, o + 96),
        num_directives=u32(data, o + 100),
        fixup_page_off=u32(data, o + 104),
        fixup_record_off=u32(data, o + 108),
        import_mod_off=u32(data, o + 112),
        num_imports=u32(data, o + 116),
        import_proc_off=u32(data, o + 120),
        page_cksum_off=u32(data, o + 124),
        data_pages_off=u32(data, o + 128),
        preload_pages=u32(data, o + 132),
        nonres_names_off=u32(data, o + 136),
        nonres_names_len=u32(data, o + 140),
        auto_ds=u32(data, o + 148),
        debug_off=u32(data, o + 152),
        debug_len=u32(data, o + 156),
        heap_size=u32(data, o + 168),
        stack_size=u32(data, o + 172),
    )


def parse_objects(data: bytes, le: LeHeader) -> list[LeObject]:
    base = le.file_offset + le.object_table_off
    out = []
    for i in range(le.num_objects):
        o = base + i * 24
        out.append(
            LeObject(
                index=i + 1,
                virtual_size=u32(data, o),
                base=u32(data, o + 4),
                flags=u32(data, o + 8),
                page_map_index=u32(data, o + 12),
                page_count=u32(data, o + 16),
                reserved=u32(data, o + 20),
            )
        )
    return out


def parse_page_map(data: bytes, le: LeHeader) -> list[tuple[int, int]]:
    base = le.file_offset + le.page_map_off
    out = []
    for i in range(le.num_pages):
        o = base + i * 4
        out.append((u24be(data, o), data[o + 3]))
    return out


def parse_resident_names(data: bytes, le: LeHeader) -> list[tuple[str, int]]:
    off = le.file_offset + le.resident_names_off
    end = le.file_offset + le.entry_off if le.entry_off else off + 4096
    out: list[tuple[str, int]] = []
    while off < end and off < len(data):
        n = data[off]
        if n == 0:
            break
        name = data[off + 1 : off + 1 + n].decode("latin-1", errors="replace")
        ordinal = u16(data, off + 1 + n)
        out.append((name, ordinal))
        off += 1 + n + 2
    return out


def load_ps(path: Path | None = None) -> PsExe:
    path = path or DEFAULT_EXE
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise ValueError(f"{path}: not MZ")
    stub = mz_image_size(data, 0)
    overlays: list[BwOverlay] = []
    cur = stub
    seen: set[int] = set()
    while 0 <= cur < len(data) - 4 and cur not in seen:
        seen.add(cur)
        sig = data[cur : cur + 2]
        if sig == b"BW":
            ov = parse_bw(data, cur)
            overlays.append(ov)
            nxt = ov.next_header
            if nxt <= cur or nxt >= len(data):
                break
            cur = nxt
        elif sig == b"LE":
            break
        else:
            break

    le_off = find_le_header(data)
    le = parse_le_header(data, le_off)
    objects = parse_objects(data, le)
    page_map = parse_page_map(data, le)
    names = parse_resident_names(data, le)
    module = names[0][0] if names else ""
    return PsExe(
        path=path,
        data=data,
        mz_stub_size=stub,
        bw_overlays=overlays,
        le=le,
        objects=objects,
        page_map=page_map,
        module_name=module,
        resident_names=names,
    )


def data_pages_file_off(file_size: int, le: LeHeader) -> int:
    """File offset of page 1.

    The LE ``data_pages_off`` field (0x3FE00 here) is *not* the on-disk start
    when the image is bound after a DOS/16M BW chain. On this 1.1A EXE the
    137 pages sit packed at EOF:

        file_size - ((num_pages-1)*page_size + last_page) == 479396

    That identity is exact (560715 bytes of page data). Prefer it; fall back
    to ``le.file_offset + data_pages_off`` only if the EOF formula overruns.
    """
    packed = (le.num_pages - 1) * le.page_size + le.last_page
    eof_off = file_size - packed
    if eof_off >= le.file_offset:
        return eof_off
    rel = le.file_offset + le.data_pages_off
    if rel + packed <= file_size:
        return rel
    return le.data_pages_off


def _page_file_off(
    file_size: int, le: LeHeader, page_num: int, flags: int
) -> tuple[int, int] | None:
    """Return (file_offset, copy_size) for a 1-based file page number."""
    if page_num == 0 or flags in (PAGE_INVALID, PAGE_ZEROFILL):
        return None
    idx = page_num - 1
    off = data_pages_file_off(file_size, le) + idx * le.page_size
    size = le.last_page if page_num == le.num_pages else le.page_size
    return off, size


def map_image(ps: PsExe, apply_fixups: bool = True) -> MappedImage:
    le = ps.le
    if not ps.objects:
        raise ValueError("no objects")
    bases = [o.base for o in ps.objects]
    ends = [o.base + max(o.virtual_size, o.page_count * le.page_size) for o in ps.objects]
    low = min(bases)
    high = max(ends)
    image = bytearray(high - low)
    file_of_va: dict[int, int] = {}
    va_of_file: dict[int, int] = {}
    loaded = 0

    for obj in ps.objects:
        first = obj.page_map_index - 1
        for i in range(obj.page_count):
            pidx = first + i
            if pidx < 0 or pidx >= len(ps.page_map):
                continue
            page_num, flags = ps.page_map[pidx]
            dest_va = obj.base + i * le.page_size
            dest = dest_va - low
            loc = _page_file_off(len(ps.data), le, page_num, flags)
            if loc is None:
                continue
            foff, size = loc
            if foff < 0 or foff >= len(ps.data):
                continue
            chunk = ps.data[foff : foff + size]
            image[dest : dest + len(chunk)] = chunk
            file_of_va[dest_va] = foff
            va_of_file[foff] = dest_va
            loaded += 1

    mapped = MappedImage(
        objects=ps.objects,
        pages_loaded=loaded,
        image=image,
        base=low,
        size=len(image),
        file_of_va=file_of_va,
        va_of_file=va_of_file,
    )
    if apply_fixups:
        mapped.fixups = apply_le_fixups(ps, mapped)
    mapped.strings = collect_cstrings(mapped)
    ps.mapped = mapped
    return mapped


def apply_le_fixups(ps: PsExe, mapped: MappedImage) -> list[tuple[int, int, int]]:
    """Apply internal 32-bit fixups. Returns (source_va, target_va, src_type)."""
    le = ps.le
    rec_base = le.file_offset + le.fixup_record_off
    page_tbl = le.file_offset + le.fixup_page_off
    # One u32 per page plus a terminator.
    nslots = le.num_pages + 1
    offs = [u32(ps.data, page_tbl + 4 * i) for i in range(nslots)]
    applied: list[tuple[int, int, int]] = []
    obj_by_idx = {o.index: o for o in ps.objects}

    for page_i in range(le.num_pages):
        start = offs[page_i]
        end = offs[page_i + 1]
        if end < start:
            continue
        # Which object owns this page (1-based page map index = page_i+1)?
        page_va = _va_of_page_index(ps, page_i + 1)
        if page_va is None:
            continue
        cur = rec_base + start
        stop = rec_base + end
        while cur + 4 <= stop and cur + 2 < len(ps.data):
            src_type = ps.data[cur]
            flags = ps.data[cur + 1]
            src_off = u16(ps.data, cur + 2)
            cur += 4
            list_mode = bool(src_type & 0x20)
            src_kind = src_type & 0x0F
            tgt_kind = flags & 0x03
            additive = bool(flags & 0x04)
            tgt32 = bool(flags & 0x10)
            obj16 = bool(flags & 0x20)
            add32 = bool(flags & 0x80)

            src_offs = [src_off]
            if list_mode:
                # src_off is a count; then that many u16 source offsets.
                count = src_off
                src_offs = []
                for _ in range(count):
                    if cur + 2 > len(ps.data):
                        break
                    src_offs.append(u16(ps.data, cur))
                    cur += 2

            if tgt_kind != 0:
                # Import / entry — not expected on this retail EXE. Skip record.
                break

            if obj16:
                if cur + 2 > len(ps.data):
                    break
                obj_no = u16(ps.data, cur)
                cur += 2
            else:
                if cur + 1 > len(ps.data):
                    break
                obj_no = ps.data[cur]
                cur += 1

            if tgt32:
                if cur + 4 > len(ps.data):
                    break
                target = u32(ps.data, cur)
                cur += 4
            else:
                if cur + 2 > len(ps.data):
                    break
                target = u16(ps.data, cur)
                cur += 2

            add_val = 0
            if additive:
                if add32:
                    if cur + 4 > len(ps.data):
                        break
                    add_val = i32(ps.data, cur)
                    cur += 4
                else:
                    if cur + 2 > len(ps.data):
                        break
                    add_val = struct.unpack_from("<h", ps.data, cur)[0]
                    cur += 2

            obj = obj_by_idx.get(obj_no)
            if obj is None:
                continue
            target_va = obj.base + target + add_val
            for so in src_offs:
                src_va = page_va + so
                dest = mapped.va_to_off(src_va)
                if dest is None:
                    continue
                if src_kind in (7, 6):  # 32-bit offset / 16:32 offset part
                    if dest + 4 <= len(mapped.image):
                        struct.pack_into("<I", mapped.image, dest, target_va & 0xFFFFFFFF)
                        applied.append((src_va, target_va, src_kind))
                elif src_kind == 8:  # 32-bit self-relative
                    rel = (target_va - (src_va + 4)) & 0xFFFFFFFF
                    if dest + 4 <= len(mapped.image):
                        struct.pack_into("<I", mapped.image, dest, rel)
                        applied.append((src_va, target_va, src_kind))
                elif src_kind == 5:  # 16-bit offset
                    if dest + 2 <= len(mapped.image):
                        struct.pack_into("<H", mapped.image, dest, target_va & 0xFFFF)
                        applied.append((src_va, target_va, src_kind))
    return applied


def _va_of_page_index(ps: PsExe, page_index_1: int) -> int | None:
    for obj in ps.objects:
        first = obj.page_map_index
        last = first + obj.page_count - 1
        if first <= page_index_1 <= last:
            return obj.base + (page_index_1 - first) * ps.le.page_size
    return None


def file_offset_of_va(mapped: MappedImage, va: int) -> int | None:
    """Best-effort file offset of a mapped VA (page-aligned lookup + delta)."""
    page = va & ~0xFFF
    delta = va & 0xFFF
    foff = mapped.file_of_va.get(page)
    if foff is None:
        # try nearby page starts stored in the dict
        for pva, fo in mapped.file_of_va.items():
            if pva <= va < pva + 4096:
                return fo + (va - pva)
        return None
    return foff + delta


def collect_cstrings(
    mapped: MappedImage, min_len: int = 4, max_len: int = 240
) -> list[tuple[int, str]]:
    img = mapped.image
    out: list[tuple[int, str]] = []
    i = 0
    n = len(img)
    while i < n:
        b = img[i]
        if 32 <= b < 127:
            j = i
            while j < n and 32 <= img[j] < 127:
                j += 1
            if j - i >= min_len and (j >= n or img[j] == 0):
                s = img[i:j].decode("ascii")
                if j - i <= max_len:
                    out.append((mapped.base + i, s))
                i = j + 1
                continue
            i = j
        else:
            i += 1
    return out


def extract_raw_strings(
    data: bytes, min_len: int = 4, max_len: int = 240
) -> list[tuple[int, str]]:
    """NUL-terminated ASCII from the raw file (no mapping needed)."""
    out: list[tuple[int, str]] = []
    i = 0
    n = len(data)
    while i < n:
        if 32 <= data[i] < 127:
            j = i
            while j < n and 32 <= data[j] < 127:
                j += 1
            if min_len <= j - i <= max_len and (j >= n or data[j] == 0):
                out.append((i, data[i:j].decode("ascii")))
            i = j + 1
        else:
            i += 1
    return out


def find_bytes(hay: bytes, needle: bytes) -> list[int]:
    hits = []
    start = 0
    while True:
        i = hay.find(needle, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    return hits


def find_u32s(hay: bytes, value: int) -> list[int]:
    return find_bytes(hay, struct.pack("<I", value & 0xFFFFFFFF))


def find_u16s(hay: bytes, value: int) -> list[int]:
    return find_bytes(hay, struct.pack("<H", value & 0xFFFF))


def xrefs_to_va(mapped: MappedImage, target: int) -> list[int]:
    """Mapped-image offsets (as VA) that contain a 32-bit pointer to target."""
    needle = struct.pack("<I", target & 0xFFFFFFFF)
    out = []
    start = 0
    img = bytes(mapped.image)
    while True:
        i = img.find(needle, start)
        if i < 0:
            break
        out.append(mapped.base + i)
        start = i + 1
    return out


def print_summary(ps: PsExe, mapped: MappedImage | None = None) -> None:
    le = ps.le
    print("=== PS.EXE container ===")
    print(f"file            : {ps.path}  ({len(ps.data)} bytes)")
    print(f"MZ stub size    : {ps.mz_stub_size}  ({ps.mz_stub_size:#x})")
    for i, ov in enumerate(ps.bw_overlays):
        print(
            f"BW[{i}]          : file {ov.offset:#x}  next={ov.next_header:#x}  "
            f"name={ov.exp_path!r}  span={ov.raw_size}"
        )
    print(f"LE header       : file {le.file_offset} ({le.file_offset:#x})")
    print(f"signature       : {le.signature!r}  endian={le.byte_order}/{le.word_order}  level={le.level}")
    print(
        f"cpu/os          : {le.cpu} ({CPU_NAMES.get(le.cpu, '?')}) / "
        f"{le.os} ({OS_NAMES.get(le.os, '?')})"
    )
    print(f"module flags    : {le.module_flags:#x}")
    print(f"module name     : {ps.module_name!r}  resident_names={len(ps.resident_names)}")
    print(
        f"entry           : CS obj {le.cs_object} EIP {le.eip:#x}   "
        f"linear {ps.objects[le.cs_object-1].base + le.eip:#x}"
        if 1 <= le.cs_object <= len(ps.objects)
        else f"entry           : CS obj {le.cs_object} EIP {le.eip:#x}"
    )
    print(
        f"stack           : SS obj {le.ss_object} ESP {le.esp:#x}   "
        f"linear {ps.objects[le.ss_object-1].base + le.esp:#x}"
        if 1 <= le.ss_object <= len(ps.objects)
        else f"stack           : SS obj {le.ss_object} ESP {le.esp:#x}"
    )
    packed = (le.num_pages - 1) * le.page_size + le.last_page
    data_off = data_pages_file_off(len(ps.data), le)
    print(
        f"pages           : {le.num_pages} x {le.page_size}  last={le.last_page}  "
        f"hdr_data_pages={le.data_pages_off:#x}  on_disk={data_off:#x}  packed={packed}"
    )
    print(f"objects         : {le.num_objects}")
    for obj in ps.objects:
        print(
            f"  obj {obj.index}: va {obj.base:#010x}..{obj.end:#010x}  "
            f"vsize={obj.virtual_size:#x}  pages={obj.page_count} @map {obj.page_map_index}  "
            f"{flag_names(obj.flags)}"
        )
    print(f"fixup section   : size {le.fixup_size}  page_tbl=+{le.fixup_page_off:#x}  recs=+{le.fixup_record_off:#x}")
    print(f"imports         : {le.num_imports}")
    print(f"debug           : off {le.debug_off:#x} len {le.debug_len}")
    print(f"heap/stack hdr  : {le.heap_size} / {le.stack_size}")
    print(f"auto DS object  : {le.auto_ds}")
    if mapped:
        print(
            f"mapped image    : base {mapped.base:#x} size {mapped.size}  "
            f"pages_loaded={mapped.pages_loaded}  fixups={len(mapped.fixups)}  "
            f"cstrings={len(mapped.strings)}"
        )
        cs = ps.objects[le.cs_object - 1]
        print(f"CS:EIP linear   : {cs.base + le.eip:#x}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Parse PS.EXE MZ/BW/LE and map the 32-bit image.")
    ap.add_argument("--exe", type=Path, default=DEFAULT_EXE)
    ap.add_argument("--no-fixups", action="store_true")
    ap.add_argument(
        "--write-image",
        type=Path,
        default=None,
        help="write mapped 32-bit image (local only; gitignored dumps)",
    )
    args = ap.parse_args(argv)
    ps = load_ps(args.exe)
    mapped = map_image(ps, apply_fixups=not args.no_fixups)
    print_summary(ps, mapped)
    if args.write_image is not None:
        args.write_image.parent.mkdir(parents=True, exist_ok=True)
        args.write_image.write_bytes(mapped.image)
        print(f"wrote image     : {args.write_image}  ({len(mapped.image)} bytes, base {mapped.base:#x})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
