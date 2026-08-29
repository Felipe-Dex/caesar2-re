# Name known c2_x VAs from findings/ps_exe.md after auto-analysis.
# @category Caesar2
# @runtime PyGhidra
# @menupath Analysis.Caesar2.Apply c2_x symbols
#
# Re-run from the GUI: Window > Script Manager > ghidra_c2_symbols.py > Run.
# VAs are linear after LE fixups (obj1 base 0x10000). Watcom register:
# EAX, EDX, EBX, ECX.

from ghidra.program.model.data import (
    ArrayDataType,
    CategoryPath,
    DWordDataType,
    PointerDataType,
    StructureDataType,
)
from ghidra.program.model.listing import CodeUnit
from ghidra.program.model.symbol import SourceType

WATCOM = "EAX=arg1, EDX=arg2, EBX=arg3, ECX=arg4; more on stack; ret EAX"


def _addr(va):
    return toAddr(va)


def _bookmark(va, text):
    createBookmark(_addr(va), "C2", text)


def _label(va, name):
    createLabel(_addr(va), name, True, SourceType.USER_DEFINED)


def _plate(va, text):
    setPlateComment(_addr(va), text)


def _eol(va, text):
    setEOLComment(_addr(va), text)


def _name_func(va, name, note):
    addr = _addr(va)
    fn = getFunctionAt(addr)
    if fn is None:
        fn = createFunction(addr, name)
    if fn is not None:
        try:
            fn.setName(name, SourceType.USER_DEFINED)
        except Exception:
            pass
        try:
            fn.setComment(note)
        except Exception:
            pass
    _label(va, name)
    _plate(va, note)
    _bookmark(va, name + " — " + note)


# --- functions / sites (minimum set + a few confirmed CRT helpers) ---
_name_func(
    0x72500,
    "start",
    "Watcom CRT entry (LE CS:EIP). Not main. Next: walk to c2_early_init 0x10010.",
)
_name_func(
    0x2444A,
    "load_file",
    WATCOM + " path / dest / max / flags?. open/seek/read/close.",
)
_name_func(
    0x70174,
    "sav_write",
    WATCOM + " EAX=path. 500 SavChunk then 4000 B from history.dat.",
)
_name_func(
    0x7024A,
    "sav_read",
    WATCOM + " EAX=path. Inverse of sav_write; trailer -> history.dat.",
)
_name_func(
    0x10DCA,
    "gfx_load_city_assets",
    "GFX cluster: cityfixt.256, fonts, mouse, panels, c2.eng via load_file.",
)
_name_func(
    0x34D92,
    "sav_year_end",
    "Year-end autosave: lastyear.sav when flags [0x9CE85]==0 and [0x9CE87]!=0.",
)
_name_func(
    0x74300,
    "AIL_set_sample_address_dbg",
    "Miles stdcall debug wrapper; real API 0x7EA10. Format string 0x9163A.",
)
_name_func(
    0x7EA10,
    "AIL_set_sample_address",
    "Miles AIL 3.x stdcall (stack args). Called from dbg wrapper 0x74300.",
)
_name_func(
    0x10010,
    "c2_early_init",
    "Early game init: malloc-ish then load_file(resource.cfg).",
)
_name_func(
    0x2456E,
    "load_file_cfg",
    WATCOM + " EAX=path EDX=dst. resource.cfg sibling of load_file.",
)
_name_func(
    0x706C6,
    "load_regions",
    WATCOM + " EAX=index. 3600-byte record x 44. Dest [0xC4D10].",
)
_name_func(
    0x722AD,
    "open_",
    "Watcom CRT open (stack). Modes 0x200 read, 0x180+0x261 create.",
)
_name_func(
    0x77B37,
    "read_",
    WATCOM + " EAX=fd EDX=buf EBX=len. Used by load_file and sav_read.",
)
_name_func(
    0x7A995,
    "write_",
    WATCOM + " EAX=fd EDX=buf EBX=len. Used by sav_write.",
)
_name_func(
    0x724FB,
    "close_",
    "Watcom CRT close. EAX=fd.",
)

# Mid-function sites (labels + bookmarks, not new functions)
_label(0x10FC7, "load_c2_eng_site")
_eol(0x10FC7, "ebx=0x9C40 (40000) edx=0xB831C eax=c2.eng  call load_file")
_bookmark(0x10FC7, "c2.eng load site — dest 0xB831C, max 40000")

_label(0x120A6, "push_22050_raw_rate")
_eol(0x120A6, "push 22050 — Miles RAW sample rate (also 0x120FB)")
_bookmark(0x120A6, "push 22050 Hz (RAW / Miles digital)")

_label(0x120FB, "push_22050_raw_rate_b")
_eol(0x120FB, "push 22050 — second Miles RAW rate site")

_label(0x11FF0, "miles_set_rate_22050")
_bookmark(0x11FF0, "function around push 22050 — name if prologue is here")

# --- data ---
_label(0x9ABC0, "sav_chunks")
_plate(0x9ABC0, "SavChunk sav_chunks[500] — {void *ptr; u32 size}. First size==0 ends loop.")
_bookmark(0x9ABC0, "sav table — 500 slots; name each from notes/ps_sav_chunks.tsv")

_label(0xE2FBC, "city_planes_20x80x80")
_plate(0xE2FBC, "BSS 20 x 6400 = 128000. City map SoA (SAV chunk 13, file off 50395).")
_bookmark(0xE2FBC, "20 planes BSS — name layers after a 1-house SAV pair")

_label(0xB831C, "c2_eng_buf")
_plate(0xB831C, "40000-byte dest of c2.eng (on disk 31876). Indexed UI strings.")
_bookmark(0xB831C, "c2.eng dest buffer")

_label(0x93694, "raw_name_bank")
_plate(0x93694, "Packed 8.3 RAW names, 8 bytes each: a01-a30, b01-b30, c01-c44 (104).")
_bookmark(0x93694, "RAW filename bank — index via shl eax,3 at ~0x135A9")

_label(0xC4D10, "regions_or_history_ptr")
_plate(0xC4D10, "Pointer: regions.dat dest, later aliased to 4000 B history.dat. Lifetime TBD.")
_bookmark(0xC4D10, "[0xC4D10] regions vs history alias — confirm lifetime")

# 1090 immediates — C2MODEL breadcrumb (do not claim a loader yet)
_IMM1090 = ((0x84294, "imm_1090_c2model_a"), (0x85112, "imm_1090_c2model_b"), (0x88207, "imm_1090_c2model_c"))
for va, name in _IMM1090:
    _label(va, name)
    _eol(va, "mov r/m32, 1090 — possible C2MODEL int count; filename absent")
    _bookmark(va, "1090 immediate — C2MODEL loader breadcrumb")

# Apply SavChunk[500] if the range is still undefined / data
dtm = currentProgram.getDataTypeManager()
sav = StructureDataType(CategoryPath("/c2_x"), "SavChunk", 0)
sav.add(PointerDataType.dataType, 4, "ptr", "runtime dest")
sav.add(DWordDataType.dataType, 4, "size", "bytes")
sav = dtm.addDataType(sav, None)
arr = ArrayDataType(sav, 500, 8)
start = _addr(0x9ABC0)
end = _addr(0x9ABC0 + 500 * 8 - 1)
try:
    clearListing(start, end)
    createData(start, arr)
    println("c2 symbols: SavChunk[500] at 0x9ABC0")
except Exception as exc:
    println("c2 symbols: SavChunk apply skipped (%s)" % exc)

# 20-plane blob as a comment-sized array of bytes is too large; leave a dword marker
try:
    createData(_addr(0xE2FBC), DWordDataType.dataType)
except Exception:
    pass

println("c2 symbols: applied load_file/sav_*/gfx/AIL/CRT + data labels")
