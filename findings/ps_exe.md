# PS.EXE — engine logic and structure (Caesar II 1.1A)

**Scope:** static analysis of the user’s legally owned retail `PS.EXE` (1 040 111 B, 1995-10-04). No copy of the binary is in this repo. No anti-tamper / CD-check work.

**Method:** Python LE/BW parser (`tools/ps_le.py`) + Capstone on the mapped 32-bit image after applying 28 451 internal fixups. Ghidra project: `findings/ghidra.md`. Strings + tables + disassembly of xref sites named the I/O layer; city-sim internals still want the GUI decompiler.

**Do not merge this into `REVERSE.md` from this workstream.** Media formats (PL8 / RAW / SMK / C2.ENG / C2MODEL naming / SAV plane IDs) belong to other agents. This file only reports **EXE evidence** those agents can consume.

**Regenerate:**

```text
python tools/ps_le.py
python tools/dump_ps_strings.py
python tools/dump_ps_tables.py
python tools/dump_ps_funcs.py
python tools/dump_ps_disasm.py
python tools/dump_ps_savtable.py
```

Default `--exe` is `C:\Users\Felip\OneDrive\Games\Caesar2\PS.EXE`. Full string dump → `notes/ps_strings_all.txt` (gitignored). Save-chunk TSV → `notes/ps_sav_chunks.tsv` (gitignored).

---

## 1. Container

`PS.EXE` is a **bound DOS/4GW** program, not a raw LE at `e_lfanew`. `e_lfanew` at 0x3C is garbage (`0x09B40000`). Real chain:

| File offset | Kind | Name / notes |
|---|---|---|
| `0x000000` | MZ stub | DOS/4GW launcher. Size from `e_cp`/`e_cblp` = **62 580** (`0xF474`). `C2.BAT` runs `havevesa` / `UNIVESA` then `ps.exe`; the stub execs sibling `DOS4GW.EXE`. |
| `0x00F474` | BW (DOS/16M EXP) | **`VMM.EXP`**. `next_header` at BW+0x1C → `0x1E0C4`. Tenberry virtual-memory manager. |
| `0x01E0C4` | BW | **`4GWPRO.EXP`**. `next_header` → `0x352A4`. |
| `0x0352A4` | MZ | Tiny stub in front of the LE (`MZ` + `e_cblp=0xA4`). |
| `0x037D4C` | **LE** | Watcom C/C++32 game image. Only plausible LE in the file (score: endian 0, CPU 386, OS OS/2, page 4096, 2 objects, 137 pages). |

Module resident name: **`c2_x`**. Imports: 0. Debug info: none (stripped). Module flags `0x200`.

### 1.1 LE header (file `0x37D4C`)

| Field | Value |
|---|---|
| CPU / OS | 386 / OS/2 (normal Watcom DOS/4GW) |
| Pages | 137 × 4096, last page **3659** B |
| Packed page bytes | 560 715 (exact: `file_size − packed = 479396 = 0x750A4`) |
| `data_pages_off` in header | `0x3FE00` — **not** the on-disk start (BW binding). Use EOF-packed formula. |
| CS object / EIP | obj **1**, EIP `0x62500` → linear **`0x72500`** |
| SS object / ESP | obj **2**, ESP `0x89260` → linear **`0x119260`** (top of object 2) |
| Auto DS | object 2 |
| Fixups | section size 249 414; **28 451** internal records applied |

Page-map page numbers are **big-endian 24-bit** + flags (`00 00 01 00` = page 1). All 137 pages are type 0 (legal).

### 1.2 Objects (32-bit flat)

| Obj | VA | vsize | Pages | Flags | Role |
|---|---|---|---:|---|---|
| 1 | `0x00010000`..`0x0008B9C0` | `0x7B9C0` (506 304) | 124 | R\|X\|big32 | code + rodata |
| 2 | `0x00090000`..`0x00119260` | `0x89260` (561 760) | 13 file-backed + BSS | R\|W\|big32 | strings, tables, CRT heap/stack, **city BSS** |

Gap `0x8B9C0`–`0x90000` is unmapped. File-backed obj2 is only 13×4096 + last-page remainder; the rest of `0x89260` is **zero-fill BSS**. The 225 745-byte save image and the 20×6400 map block live there (see §5).

Mapped image used by the tools: base `0x10000`, size 1 086 048, 137 pages, 712 mapped C-strings (NUL-terminated ASCII). Raw-file C-strings (including the extender stub): 1309.

### 1.3 Watcom calling convention (measured)

Default 32-bit **register** convention, confirmed at every game I/O site:

| Arg | Register |
|---|---|
| 1 | **EAX** |
| 2 | **EDX** |
| 3 | **EBX** |
| 4 | **ECX** |
| more | stack (`push` / `add esp, N`) |
| return | EAX (0 / −1 for I/O) |

CRT `open` / `read` / `write` (`0x722AD`, `0x77B37`, `0x7A995`) use the **stack** (Watcom `cdecl` / pragma aux for POSIX-like helpers). Miles AIL wrappers at `0x74xxx` are **stdcall** (args pushed, `add esp` after `fprintf`-style debug, then a tail call).

Typical prologue: `push ebx` / `push esi` / `push edi` / `push ebp`. No PDB, no Watcom debug overlay.

---

## 2. Strings

UI labels are **not** in the EXE. Cross-check vs `C2.ENG` (146 / 109 unique): **0 overlap**. The engine loads `c2.eng` into a 40 000-byte buffer (`0xB831C`) and indexes that table. `HELP.ENG` is a sibling open (`help.eng` at VA `0x90E16`), not the same format.

Error strings in the game image are stored with a **leading `\\n`**, so a naive printable-start scan misses them. They are at VA `0x901F1` and neighbours.

### 2.1 Classified (raw file)

| Bucket | n | Notes |
|---|---:|---|
| filename | 563 | PL8 / 256 / WAV / RAW / SMK / XMI / SAV / DAT / ENG / LBM |
| error | 41 | mostly DOS/4GW + Watcom CRT in the stub; game errors need the `\\n` scan |
| miles | 116 `AIL_*` debug format strings | Miles 3.x (`AIL3DIG` / `AIL3MDI`) |
| format | 23 | VESA + extender |
| other | 640 | includes building WAV names, tutorial PL8 list |

### 2.2 File names the engine actually opens (xref’d)

**Startup / city graphics** (loader cluster ~`0x10DCA`, helper `load_file` `0x2444A`):

`resource.cfg`, `cityfixt.256`, `landfill.pl8`, `font_c2.pl8`, `font3c2.pl8`, `mouse.pl8`, `system.pl8`, `panels.pl8`, `smacker.pl8`, `misc.pl8`, `c2.eng`, `int_city.pl8`, `provfixt.256`, `int_prov.pl8`, `int_batl.pl8`, `cd.dat`, `build1f.pl8` / `build2f.pl8` / `build3f.pl8` (zoom sheets).

**City / forum / empire chrome:** `forumbit.pl8`, `forum_x.gd8`, `forum.pl8`/`forum.256`, `empire.pl8`/`empire.256`/`e_parts2.pl8`, `backgrnd.pl8`, `rat_back.pl8`/`rat_fron.pl8`, `logo1/2.pl8`+`.256`.

**Saves / campaign:** `caesar2.sav`, `lastyear.sav`, `*.sav`, `history.dat`, `caesar2.inf`, `regions.dat`, `help.eng`.

**Cutscenes / music:** `intro.smk`, `wingame.smk`, `losegame.smk`, `battwon.smk`, `battlost.smk`, `promote.smk`, `message.smk`, `prebatle.raw`, `forum1/2/3.xmi`, `cityprov.xmi`, `batest2.xmi`.

**Not in the EXE as a C-string:** `c2model`, `C2MODEL`, `model.dat`. The file `C2MODEL.DAT` exists on disk (other agent) but **this EXE never names it**. No `fopen`/`fread` strings either — I/O is Watcom `open`/`read`/`write`.

**Leftovers:** `shot1.lbm`…`shot8.lbm` (Deluxe Paint), `null.pl8` / `null.voc` / `null.smk` / `null.wav`, RAW slots `a10–a30` / `b21–b30` / `c44` (install has fewer files).

### 2.3 Miles

Full AIL 3.02-style debug trace table (`AIL_startup()` … `AIL_set_sample_address(0x%X,0x%X,%u)` … `AIL_install_MDI_INI`). Drivers named: `SB16.DIG`, `SBPRO.DIG`, `SBLASTER.DIG`. `AIL_DEBUG` / `AIL_SYS_DEBUG` env vars.

`22050` is a **`push imm32`** at VA `0x120A6` and `0x120FB` (function around `0x11FF0`) — sample rate for RAW / Miles digital. `11025` appears once (WAV path, city SFX).

`AIL_set_sample_address` debug wrapper ~`0x74300` → real API `0x7EA10` (stack args). RAW vs WAV: city ambience/combat names are `.wav`; narration/banks A/B/C + `prebatle` are `.raw` (unsigned PCM, no RIFF) fed through `AIL_set_sample_address`.

---

## 3. Tables

### 3.1 C2MODEL.DAT — **not embedded**

The first 80 bytes of `C2MODEL.DAT` do **not** occur in the mapped image (aligned or not). Immediate **4360** (file size) is absent. Immediate **1090** (int count) appears three times (`0x84294`, `0x85112`, `0x88207`) as `mov r/m32, imm` — possible loop bounds, not a memcpy of the DAT.

The five starting-money values `20000,15000,12000,7000,5000` occur **once**, unaligned (VA `0x096F2F` / file 1 015 763). Treat as coincidence or a packed subsequence until Ghidra shows a real load. **Costs and the 32 housing occupancy grades live in `C2MODEL.DAT` on disk; this EXE does not duplicate that file.**

### 3.2 RAW filename bank (confirmed)

Packed 8.3 names, 8 bytes each, VA **`0x93694`**:

`a01.raw`…`a30.raw`, `b01.raw`…`b30.raw`, `c01.raw`…`c44.raw` (104 names).

Index code at ~`0x135A9`: `shl eax, 3` / `add edx, eax` / `edx = 0x93694` — **EAX is the clip index**.

### 3.3 REGIONS.DAT records (confirmed)

`regions.dat` load at `0x706C6`:

```
; ecx = 3600 * index   (shl/sub/shl/add/shl measured)
mov ebx, 0xE10          ; 3600
mov eax, "regions.dat"
call load_file          ; 0x2444A
```

`158400 / 3600 = 44` records. Dest base `[0xC4D10]`. Same pointer later receives the 4000-byte `history.dat` blob during save/load — **aliased buffer, or reused after region load**. Ghidra should confirm lifetime.

### 3.4 Zoom / building PL8 lists

Three parallel name tables (zoom 1/2/3), VA ~`0x927F8`:

`ltlmen1b.pl8`, `cityfixt.pl8`, `houses1.pl8`, `build1a–d.pl8`, `citytop1.pl8`  
and the `2` / `3` twins. Matches the PL8 workstream’s flags `0x0002` / `0x0102` / `0x0202`.

Tutorial pair list `tut_01a.pl8`…`tut_16b.pl8` + matching `.256` (install only has through `TUT_13B`; EXE knows 14–16).

### 3.5 Constants

| Constant | In EXE? | Evidence |
|---|---|---|
| 80 (map side) | yes, many `mov r32, 80` | startup `0x10032` (`mov edx, 0x50` then allocator); lots of city code |
| 6400 | 39 times, **not** as clean `push`/`mov eax` | used as `[reg+disp], 6400` / ALU; 20×6400 block in BSS |
| 35 | many `mov eax, 35` clustered `0x5FC11`–`0x5FFCE` | **hypothesized plane / walker loop** — needs Ghidra |
| 1745 | **no** | header size is not an immediate (scatter-gather, §5) |
| 225745 | **no** | same — sum of table + 4000 |
| 22050 | yes, 2× `push` | Miles RAW rate |
| 20000 / 5000 | yes | money compares (`cmp eax, 20000` at `0x2537D`, `0x5671F`) |

---

## 4. Functions (hypothesized names)

VAs are **linear** after fixups (obj1 base `0x10000`). File offset = page file-map + delta (`tools/ps_le.py` `file_offset_of_va`). `CS:EIP` `0x72500` is Watcom CRT startup, not `main`.

| Hypothesized name | VA | File off | Convention | Evidence |
|---|---|---|---|---|
| `start` / CRT | `0x72500` | (obj1 page) | — | LE EIP. Calls into `0x7201B` from `0x10025`. |
| `c2_early_init` | `0x10010` | 479412 | — | Sets flags, `malloc`-ish `0x7202C(0xC1F5C, 80)`, then `load_file("resource.cfg")`. |
| **`load_file`** | **`0x2444A`** | **562414** | EAX=path, EDX=dst, EBX=max, ECX=flags? | `open(0x200)`, `seek 0x7A8DA`, `read 0x77B37`, `close 0x724FB`. On fail calls `0x2421E` (CD/path retry) and opens again. Used for `c2.eng`, PL8, `regions.dat`. |
| `load_file_cfg` | `0x2456E` | 562542 | EAX=path, EDX=dst | `resource.cfg` site `0x10062`. Sibling of `load_file`. |
| `open_` (CRT) | `0x722AD` | ~885000 | stack | Returns −1. Modes: `0x200` (read), `0x180`+`0x261` (create/write). |
| `read_` | `0x77B37` | — | EAX=fd, EDX=buf, EBX=len | Used by `load_file` and **`sav_read`**. |
| `write_` | `0x7A995` | — | EAX=fd, EDX=buf, EBX=len | Used by **`sav_write`**. |
| `close_` | `0x724FB` | — | EAX=fd | |
| `free_` | `0x72207` | — | EAX=ptr | GFX cluster frees old PL8 buffers. |
| `printf_` / `cprintf_` | `0x720B6` | — | stack | `\nError loading graphics data - code %d…` |
| `delay_ms?` | `0x720F6` | — | EAX=100 after errors | |
| **`gfx_load_city_assets`** | **`0x10DCA`** | **482926** | — | Frees 6+ handles, then `load_file` on `cityfixt.256`, fonts, mouse, panels, `c2.eng`. Failure returns codes 8, 9, **0xA**. |
| `gfx_error_graphics` | ~`0x10812` | 481668 | — | Loop `edi < 8`; on fail `push code; push "\\nError loading graphics…"`. |
| `load_c2_eng` (site) | `0x10FC7` | 483431 | — | `ebx=0x9C40` (40000), `edx=0xB831C`, `eax="c2.eng"`, `call load_file`. C2.ENG on disk is 31 876 B. |
| **`sav_write`** | **`0x70174`** | **872980** | EAX=path | Autosave: `lastyear.sav` at `0x34DBF`. Opens path create, opens `history.dat` read, writes 500 chunks, then appends 4000 B from `[0xC4D10]`. |
| **`sav_read`** | **`0x7024A`** | **873198** | EAX=path | Inverse: read chunks, then 4000 B from sav → `[0xC4D10]`, write that to `history.dat`. |
| `sav_year_end` | `0x34D92` | 630326 | — | If `[0x9CE85]==0` and `[0x9CE87]!=0` → `sav_write("lastyear.sav")`. Manual “Year End / Auto Save” (matches the printed manual). |
| `file_dialog_sav` | `0x6FACC` | 871280 | — | `*.sav` xrefs; UI state at `0x117Dxx`. |
| `open_small` | `0x2605F` | — | EAX=name, EDX=buf, EBX=12 | `caesar2.sav` / `c2.eng` / `help.eng` 12-byte header/stat? |
| `raw_name_from_index` | ~`0x13590` | — | EAX=index | `shl 3` into `0x93694`. |
| `miles_set_rate_22050` | ~`0x11FF0` / `0x12003` | 487572 | — | `push 22050`. |
| `AIL_set_sample_address` (dbg) | `0x74300` | 889764 | stdcall | Pushes format `0x9163A`, calls `0x7EA10`. |
| `load_regions` | `0x706C6` | 874346 | EAX=index | 3600-byte record × 44. |
| `forum_gd8_load` | `0x3DB24` / `0x5D1A3` | — | — | `forum_x.gd8`, `ebx=0xFA0` (4000) or `0x0FA0` wait — site uses `ebx=0x0FA0`? Measured `bb a0 0f 00 00` = **4000**. Same size as history. |

---

## 5. SAV load/save — for the SAV workstream

**Do not rewrite `probe_sav_map.py` / `diff_sav.py`.** Use this as the EXE-side map of how those 225 745 bytes are produced.

### 5.1 Serializer (confirmed)

City saves are **not** one `fwrite` of a 1745-byte header plus 35 planes. They are a **scatter-gather list**:

```
struct SavChunk { void *ptr; u32 size; };   // 8 bytes, 500 slots
SavChunk sav_chunks[500];                   // VA 0x9ABC0
```

Loop (both directions), `ecx = 0 … 0x1F4-1` (500). **First `size == 0` ends the loop** (not seen in this build — all 500 slots are live; slots 432–499 are 68 copies of the same 4-byte cell at `0x117D70`, i.e. padding / unused handles).

```
table bytes  = 221745
+ history    = 4000          // HISTORY.DAT size; pointer [0xC4D10]
             = 225745        // exact .SAV size
```

That is why **1745 and 225745 never appear as immediates**: the compiler emitted a pointer table, not `sizeof(SaveFile)`.

| Direction | VA | `open` mode | Transfer |
|---|---|---|---|
| write | `0x70174` | path: `0x180`,`0x261`; `history.dat`: `0x200` | `write_` `0x7A995` for each chunk; then **read** 4000 from history, **write** them onto the sav |
| read | `0x7024A` | path: `0x200`; `history.dat`: create | `read_` `0x77B37` for each chunk; then **read** 4000 from sav, **write** them to `history.dat` |

Trailer of every `.SAV` = copy of `HISTORY.DAT` (4000 B). `HISTORY.DAT` on this install is 4000 B and dated 2011 — player campaign blob, not retail CD.

Full 500 rows: `notes/ps_sav_chunks.tsv` (`index, ptr_va, size, file_off, note`).

### 5.2 Large chunks (file order)

Cumulative offset = start of that chunk in the `.SAV`.

| idx | ptr VA | size | file off | Note |
|---:|---|---:|---:|---|
| 0–6 | flags / u32s at `0x117A8D`, `0x102BE0`, … | 1–4 | 0 | scalars (year? difficulty?). `[0x102BE0]` is also written after save (`0x70307`). |
| 7 | `0x114500` | 4550 | 16 | |
| 8 | `0x1107A4` | 11658 | 4566 | |
| 9 | `0x113560` | 3978 | 16224 | |
| 10 | `0x0D361C` | 17688 | 20202 | |
| 11 | `0x115702` | 9045 | 37890 | |
| 12 | `0x102DE4` | 3460 | 46935 | |
| **13** | **`0x0E2FBC`** | **128000** | **50395** | **20 × 6400 = 20 × 80×80.** Strongest city-map SoA block. BSS (no file backing in the EXE). |
| 14 | `0x0D94FC` | 28800 | 178395 | 4.5×6400 — not an integer plane count |
| 15 | `0x103B68` | 100 | 207195 | |
| 16–254 | mostly u32/u8 globals in `0x102xxx` | 1–4 | … | |
| 255 | `0x0E057C` | 10816 | 208338 | sits immediately after the 28800 block (`0xD94FC+28800`) |
| 335 | `0x0D2AEC` | 256 | 219524 | |
| 339 | `0x0D2B6C` | 768 | 219788 | |
| 387–389 | `0x0D2EFC`, `0x0D2F4C`, `0x0D2EAC` | **80** each | ~220872 | one map **row** or **column** (or 80 flags) |
| 499 | `0x117D70` | 4 | 221741 | last table slot |
| trailer | `[0xC4D10]` | 4000 | **221745** | `history.dat` |

### 5.3 Relation to 1745 + 35×6400

`1745 + 35×6400 = 225745` remains a true **size identity** (SAV agent). It is **not** how `sav_write` emits the file.

Implications for plane IDs:

- A 6400-zero “plane 6” at file 40145 would fall **inside chunk 12** (3460 B starting 46935) or the tail of chunk 11 — **not** inside the 20×6400 block (that block starts at **50395**).
- Re-map occupancy probes onto **this table’s file offsets**, or diff two saves and look up `file_off` in the TSV.
- The 20-plane block at VA `0xE2FBC` is the place to name layers (road, building, …) with a controlled house/road pair.

`u32@8` = year-BC is still a header-agent hypothesis; candidates are the 4-byte slots near file offset 0–16 (`0x102BE0`, `0x102BA4`, `0x102BA0`) plus the three 1-byte flags at `0x117A8D` / `0x117A59` / `0x117A8B` (the last is re-read after load at `0x70313`).

---

## 6. City sim / map

- **80** is a first-class immediate (`mov edx, 80` in early init; many city sites).
- **20 contiguous 80×80 planes** at BSS `0xE2FBC` (128 000 B) — best in-engine map object found.
- **`mov eax, 35` cluster** `0x5FC11`–`0x5FFCE` (file ~806069) — hypothesized “for each plane / walker type” loop. Not disassembled in depth.
- No pointer table with stride +6400 (planes are one base + `i*6400`, or the 20-plane blob).
- Tick / day / week: `lastyear` path is year-end, not per-tick. Tick function not named.

---

## 7. PL8 loader (EXE side)

Not reverse-engineered at the pixel level (decoder already exists). EXE facts:

- Loads named `.pl8` / `.256` through **`load_file`** into heap buffers, then keeps pointers at `0x102414`, `0x102418`, `0x10241C`, `0x102424`, `0x102428`, `0x1023CC`, `0x1023E0`, … (freed in `gfx_load_city_assets`).
- Error path distinguishes **graphics** / **overlay** / **battle** (`0x10903`, `0x10AAC`, `0x10C5B`) with a numeric `code %d` (loop index or zoom).
- Zoom 1/2/3 filename triples are data, not computed from flags — the high byte of PL8 flags is still a file-format concern, not an EXE table we dumped.

ISO diamond math (900 B, types 1–4) was **not** located as immediates (900 / 1740 absent in a quick scan). Ghidra on the first use of a `houses1.pl8` buffer after `load_file` is the next step.

---

## 8. Open questions

1. **How does `C2MODEL.DAT` get into memory?** No filename, no 4360-byte read. Possibly a constructed 8.3, a record inside another DAT, or only consumed by an editor. Three `1090` immediates are the breadcrumb.
2. **Name every `SavChunk`.** 500 slots; most are 4-byte globals in `0x102xxx`. Needs a decompiler + the controlled save pair.
3. **City tick / desirability / walkers.** `0x5FCxx` 35-loop and anything that stores into `0xE2FBC`.
4. **Building type ID ↔ PL8 sprite.** Name tables exist; the integer ID map does not (likely a `struct BuildingInfo[]` in BSS or C2MODEL).
5. **`[0xC4D10]` aliasing** — regions (44×3600) vs history (4000). Lifetime.
6. **`0x2605F` 12-byte opens** of `caesar2.sav` / `c2.eng` / `help.eng` — header peek vs full load.
7. **CRT vs game `main`.** Walk from `0x72500` to the first call into `0x10010` / menu.

---

## 9. Importing in Ghidra

Project is on disk: **`findings/ghidra.md`** (open `ghidra_work/c2_x.gpr`, JDK / first clicks / named VAs). Suggested import if you rebuild (no EXE copy required):

```text
python tools/ps_le.py --write-image notes/ps_le_image.bin
```

In Ghidra:

1. **New project → Import** `notes/ps_le_image.bin` as **Raw Binary**.
2. Language **`x86:LE:32:default`**, compiler **`unknown`** (or gcc — Watcom is closer to gcc than Visual Studio).
3. Base address **`0x00010000`**.
4. Split / rename blocks: `0x10000` RX length `0x7B9C0` (`.text`); `0x90000` RW length `0x89260` (`.data`/BSS). Optional hole `0x8B9C0–0x90000`.
5. Entry **`0x00072500`**. Create function; it is CRT, not `WinMain`.
6. Apply types from §4 / §5. Load `notes/ps_sav_chunks.tsv` as a 500-entry `SavChunk` at `0x9ABC0`.
7. Set calling convention on `0x2444A` / `0x70174` / `0x7024A` to **register (EAX,EDX,EBX,ECX)**.

Alternative: import `PS.EXE` and hope a Linear Executable loader sees `LE` at `0x37D4C`. Default MZ import will stop at the 62 KB stub and is **not useful**. Some Ghidra builds need the LE extracted (`[0x37D4C : EOF]`) as its own file; you still must map pages with the EOF-packed rule (`tools/ps_le.py` already does this).

IDA: same mapped image, or `unp`/`wdump` to peel BW overlays. radare2: `r2 -a x86 -b 32 -m 0x10000 notes/ps_le_image.bin`.

---

## 10. Tools (this workstream)

| Path | Role |
|---|---|
| `tools/ps_le.py` | MZ stub, BW chain, LE header/objects/page map, fixups, mapped image |
| `tools/dump_ps_strings.py` | Classify + C2.ENG overlap + xrefs |
| `tools/dump_ps_tables.py` | Immediates + FAQ sequences + 6400-stride hunt |
| `tools/dump_ps_funcs.py` | String → prologue, C2MODEL compare, AIL list |
| `tools/dump_ps_disasm.py` | Capstone listings + pointer-diff hunt |
| `tools/dump_ps_savtable.py` | 500-chunk table, `load_file`, RAW bank, TSV |

`--write-image` on `ps_le.py` is optional and should stay under `notes/` / `findings/dumps/` (gitignored).
