# Caesar II — Phase 1 (exploration)

**Last update:** 2026-08-29 (rev. 15 — city tick `view_frame` @ `0x3CF9A`; `findings/ghidra_city.md`)  
**Source:** `C:\Users\Felip\OneDrive\Games\Caesar2` (flat tree; CD/retail DOS)  
**Version:** `README.TXT` = **1.1A** (27 Feb 1996); string in `C2.ENG` = **“Caesar II - Version 1.1”**; `PS.EXE` dated **1995-10-04**.

Notes only with evidence. Hypotheses marked. Do not copy assets for distribution.

Workstream sources for this revision: `findings/ghidra.md` (GUI how-to + named VAs). Engine facts stay in `findings/ps_exe.md`. Media formats (PL8 / RAW / SMK) are unchanged from rev. 11.

**Tool caveat:** the Cursor/OneDrive index **omits** `.exe`, `.pl8`, `.256`, `.smk`, `.sav`, etc. (reparse/cloud). Reliable inventory = `Get-ChildItem` in PowerShell, not the IDE glob.

---

## 0. Install verdict

This is a **playable-enough flat DOS HD install**: executable, extender, PL8 graphics, palettes, Smacker, XMI, WAV, `.RAW` (PCM), saves, `.DAT` tables. It is not the CD root (`HD\`, `PL8\`, …); the installer already mixed everything into one folder.

| Ext | Count | Bytes (sum) | Role |
|---|---:|---:|---|
| `.PL8` | 299 | 24 398 332 | Sprites / tiles / UI / tutorials / battle |
| `.SMK` | 14 | 18 037 256 | Smacker cutscenes |
| `.RAW` | 73 | 11 930 788 | PCM 8-bit unsigned mono **22050 Hz** (A/B/C + `PREBATLE.RAW`), not a framebuffer |
| `.WAV` | 84 | 1 409 995 | PCM SFX |
| `.EXE` | 7 | 1 521 887 | Engine + tools |
| `.SAV` | 3 | 677 235 | Saves (fixed size) |
| `.ENG` | 2 | 487 070 | Strings / help (English) |
| `.MDI` / `.DIG` | 16+9 | ~274 k | Miles AIL drivers |
| `.256` | 147 | 112 896 | RGB palettes (all **768 bytes**) |
| `.XMI` | 5 | 54 494 | XMIDI music |
| `.DAT` | 4 | 167 016 | Game tables |

Executables present: `PS.EXE`, `DOS4GW.EXE`, `HAVEVESA.EXE`, `UNIVESA.EXE`, `SETSOUND.EXE`, `STUB.EXE`, `CHECK.EXE`.

---

## 1. `PS.EXE` — engine

| Field | Value |
|---|---|
| Path | `C:\Users\Felip\OneDrive\Games\Caesar2\PS.exe` |
| Size | **1 040 111** bytes |
| NTFS date | 1995-10-04 05:51:58 |
| Magic | `MZ` (DOS) |
| Extender | **DOS/4GW** (Rational / Tenberry; sibling `DOS4GW.EXE` 254 556 B) |
| Compiler | **WATCOM C/C++32** (runtime strings 1988–1994) |
| Launch | `C2.BAT` → `havevesa.exe` / `UNIVESA.EXE` → `ps.exe` |

### 1.1 Container (confirmed)

`e_lfanew` at 0x3C is garbage (`0x09B40000`). The file is a **bound DOS/4GW** program, not a raw LE at the MZ pointer. Measured chain (`tools/ps_le.py`):

| File offset | Kind | Name / notes |
|---|---|---|
| `0x000000` | MZ stub | DOS/4GW launcher. Size from `e_cp`/`e_cblp` = **62 580** (`0xF474`). |
| `0x00F474` | BW (DOS/16M EXP) | **`VMM.EXP`**. `next_header` at BW+0x1C → `0x1E0C4`. Tenberry VMM. |
| `0x01E0C4` | BW | **`4GWPRO.EXP`**. `next_header` → `0x352A4`. |
| `0x0352A4` | MZ | Tiny stub in front of the LE (`MZ` + `e_cblp=0xA4`). |
| `0x037D4C` | **LE** | Watcom C/C++32 game image. Only plausible LE (endian 0, CPU 386, OS OS/2, page 4096, 2 objects, 137 pages). |

Module resident name: **`c2_x`**. Imports: 0. Debug info: none (stripped). Module flags `0x200`.

| LE field | Value |
|---|---|
| Pages | 137 × 4096, last page **3659** B |
| Packed page bytes | 560 715 |
| `data_pages_off` in header | `0x3FE00` — **not** the on-disk start (BW binding). Use EOF-packed formula. |
| CS object / EIP | obj **1**, EIP `0x62500` → linear **`0x72500`** |
| SS object / ESP | obj **2**, ESP `0x89260` → linear **`0x119260`** |
| Auto DS | object 2 |
| Fixups | **28 451** internal records |

| Obj | VA | vsize | Pages | Flags | Role |
|---|---|---|---:|---|---|
| 1 | `0x00010000`..`0x0008B9C0` | `0x7B9C0` (506 304) | 124 | R\|X\|big32 | code + rodata |
| 2 | `0x00090000`..`0x00119260` | `0x89260` (561 760) | 13 file-backed + BSS | R\|W\|big32 | strings, tables, CRT heap/stack, **city BSS** |

Gap `0x8B9C0`–`0x90000` is unmapped. File-backed obj2 is only 13×4096 + last-page remainder; the rest of `0x89260` is **zero-fill BSS**. The save scatter table and the 20×6400 map block live there.

`CS:EIP` **`0x72500`** is Watcom CRT startup, not `main`. CRT calls **`c2_main` @ `0x10010`** (whole game: boot assets / `c2.eng` / VESA+Miles / `intro.smk` / title / city loop). Boot walk: `findings/ghidra_walk.md`. City frame / `init_new_city` / named SavChunks: **`findings/ghidra_city.md`**.

### 1.2 Watcom calling convention (confirmed)

Default 32-bit **register** convention at every game I/O site:

| Arg | Register |
|---|---|
| 1 | **EAX** |
| 2 | **EDX** |
| 3 | **EBX** |
| 4 | **ECX** |
| more | stack (`push` / `add esp, N`) |
| return | EAX (0 / −1 for I/O) |

CRT `open` / `read` / `write` (`0x722AD`, `0x77B37`, `0x7A995`) use the **stack**. Miles AIL wrappers at `0x74xxx` are **stdcall**. Typical prologue: `push ebx` / `push esi` / `push edi` / `push ebp`. No PDB.

### 1.3 Strings and files the engine opens

UI labels are **not** in the EXE. Cross-check vs `C2.ENG`: **0 overlap**. The engine loads `c2.eng` into a 40 000-byte buffer (`0xB831C`). Error strings in the game image have a **leading `\n`**.

Useful I/O / error strings (unchanged from earlier revs):

- `Error loading graphics data - code %d - file not found.`
- `Error loading overlay data - file not found.`
- `Error loading battle data - %s not found.`
- `Not enough free memory to run Caesar2.`
- `resource.cfg`, `c2.eng`, `help.eng`, `history.dat`, `regions.dat`, `cd.dat`, `caesar2.inf`, `caesar2.sav`, `lastyear.sav`, `forum_x.gd8`

**Not in the EXE as a C-string:** `c2model`, `C2MODEL`, `model.dat`. `C2MODEL.DAT` exists on disk; this EXE never names it. I/O is Watcom `open`/`read`/`write`, not `fopen`.

Embedded list `a01.raw`…`a30.raw`, `b01.raw`…`b30.raw`, `c01.raw`…`c44.raw` at VA **`0x93694`** (8.3 names, 8 bytes each). The disk only has A01–A09, B01–B20, C01–C43. Index code ~`0x135A9`: `shl eax, 3` into that bank.

`shot1.lbm`…`shot8.lbm` referenced — **not** on the HD. Hypothesis: leftover internal tool (Deluxe Paint).

`22050` is a **`push imm32`** at VA `0x120A6` and `0x120FB` (Miles RAW rate). `11025` appears once (WAV / city SFX).

### 1.4 Named functions (hypothesized names, VAs confirmed)

VAs are **linear** after fixups (obj1 base `0x10000`). Full table: `findings/ps_exe.md`.

| Name | VA | Convention | Evidence |
|---|---|---|---|
| `start` / CRT | `0x72500` | — | LE EIP. |
| **`c2_main`** | **`0x10010`** | — | Game main (CRT `crt_cmain` → here → `exit_`). |
| **`load_file`** | **`0x2444A`** | EAX=path, EDX=dst, EBX=max | `open` / `seek` / `read` / `close`. Used for `c2.eng`, PL8, `regions.dat`. |
| `gfx_load_boot_assets` | `0x10E89` | — | `cityfixt.256`, fonts, mouse, panels, **`c2.eng`**. |
| **`sav_write`** | **`0x70174`** | EAX=path | 500 chunks, then 4000 B from `history.dat`. |
| **`sav_read`** | **`0x7024A`** | EAX=path | Inverse; writes the 4000 B trailer back to `history.dat`. |
| `sav_year_end` | `0x34D92` | — | If flags at `[0x9CE85]==0` and `[0x9CE87]!=0` → `sav_write("lastyear.sav")`. Year-end autosave (matches the printed manual). |
| `load_regions` | `0x706C6` | EAX=index | 3600-byte record × 44. Dest `[0xC4D10]`. |
| `raw_name_from_index` | ~`0x13590` | EAX=index | `shl 3` into `0x93694`. |

`1745` and `225745` **never appear as immediates** — the compiler emitted a pointer table, not `sizeof(SaveFile)`. `80` is a first-class immediate. `6400` appears 39 times as ALU / `[reg+disp]`. A `mov eax, 35` cluster at `0x5FC11`–`0x5FFCE` is a **hypothesized** plane / walker loop (not disassembled in depth).

### 1.5 Ghidra (mapped `c2_x`)

Headless project is ready. **How to open + what to name next:** `findings/ghidra.md`.

Image `ghidra_work/c2_x.bin` (gitignored) from `tools/ps_le.py --write-image`. Raw **`x86:LE:32:default` / `gcc`**, base **`0x10000`**, entry **`0x72500`**. Known I/O / SAV / Miles / `c2.eng` labels and `SavChunk[500]` are already applied. **`c2_main` @ `0x10010`** and **`view_frame` @ `0x3CF9A`** are named (walks: `findings/ghidra_walk.md`, `findings/ghidra_city.md`). Next GUI click: **G `3CF9A`** (redefine end at `0x3D3E5`) then **G `459D0`**. Default MZ import of `PS.EXE` is still **not useful**.

---

## 2. `.PL8` + `.256` — main graphics format (confirmed on these bins)

Palette `.256`: **exactly 768 bytes** = 256 × RGB (3 bytes, no alpha). On every sample in this install, **each channel is 0–63** (VGA 6-bit DAC). Expand to 8-bit: `(c << 2) | (c >> 4)`. Index 0 → alpha 0 in the PNG.

Ex. `AHOUSE.256` starts `00 00 00 00 00 2A …`. `HOUSES1.PL8` **has no** sibling `.256`; `CITYFIXT.256` is the right palette for city tiles (`HOUSES1`, `BUILD1A`, `CITYFIXT`).

### Header PL8 (measured, little-endian)

Matches community [pl8image](https://pl8image.readthedocs.io/en/latest/.pl8.html), with field sizes **corrected by evidence**:

| Offset | Type | Field |
|---|---|---|
| 0 | u16 | flags (bit 0 = RLE in community doc — **0/299** here; high byte = zoom, below) |
| 2 | u16 | sprite count |
| 4 | u32 | unknown |
| 8 + 16×i | 16 B record | sprite *i* |

Sprite record (16 bytes):

| Offset in record | Type | Field | Evidence |
|---|---|---|---|
| 0 | u16 | width | `TUT_01A`: `80 02` = **640** |
| 2 | u16 | height | `E0 01` = **480** |
| 4 | u32 | data offset | `18 00 00 00` = **24** |
| 8 | u16 | x | |
| 10 | u16 | y | |
| 12 | u8 | tile type | |
| 13 | u8 | extra rows (ISO) | |
| 14 | u16 | unknown | |

Formula that holds on all samples:

`dataOffset(sprite0) = 8 + 16 × spriteCount`

| File | flags | sprites | spr0 | dataOff | check |
|---|---:|---:|---|---:|---|
| `AHOUSE.PL8` | 0002 | 1 | **182×132** | 24 | 24+182×132 = **24048** (file size) |
| `TUT_01A.PL8` | 0002 | 1 | **640×480** | 24 | 24+307200 = **307224** |
| `BACKGRND.PL8` | 0002 | 1 | 640×480 | 24 | same |
| `BUILD1A.PL8` | 0002 | 123 | **58×30** | 1976 | 8+16×123 = 1976 |
| `HOUSES1.PL8` | 0002 | 106 | **58×30** | 1704 | 8+16×106 = 1704 |
| `CITYFIXT.PL8` | 0002 | 140 | **58×30** | 2248 | 8+16×140 = 2248 |
| `FONT_C2.PL8` | 0102 | 108 | 7×8 | 1736 | 8+16×108 = 1736 |
| `MOUSE.PL8` | 0202 | 22 | 16×16 | 360 | 8+16×22 = 360 |
| `SYSTEM.PL8` | 0202 | 64 | 16×16 | 1032 | 8+16×64 = 1032 |

**42** PL8 files are **24048** B → one uncompressed 182×132 sprite (large building icons: `AHOUSE`, `AFORUM`, `AFARM`, …).

**31** files are **307224** → fullscreen 640×480 + 24 B header (`TUT_*`, `BACKGRND`, `RAT_FRON`, …).

Pixels after the header, **type 0** (bitmap): **1 byte = palette index**, `width×height` bytes (no RLE).

### Flags — full inventory (299/299)

No PL8 in this 1.1A has bit 0 set. The `span == packed_bytes` chain closes on **299/299**. `RO2*` / `GM2*` are **not** compressed: they are type-0 bitmaps (~12–20×29–36 at zoom 2; ~6–10×14–16 at zoom 3).

| flags | Count | bit0 | High byte | Measured use |
|---|---:|---|---|---|
| `0x0002` | 219 | 0 | 0 | zoom 1: city 58×30, units ~15×30, icons 182×132, tutorials 640×480 |
| `0x0102` | 63 | 0 | 1 | zoom 2: city 26×14 (`BUILD2*`, `HOUSES2`, `CITYFIX2`), units `*3*` ~8×15, `FONT_C2` |
| `0x0202` | 17 | 0 | 2 | zoom 3 / UI: city 10×6 (`BUILD3*`, `HOUSES3`, `CITYFIX3`), `MOUSE`, `SYSTEM`, `ICONS` |

The digit in the name (`BUILD1/2/3`, `HOUSES1/2/3`, `RO2`/`RO3`) tracks the high byte **except** `MY_STDS3.PL8` (flags `0x0002`, sprites ~13×5). Bit 1 (`0x0002`) is **always** on — format / “has table”; no counter-example.

Community RLE ([pl8image](https://pl8image.readthedocs.io/en/latest/.pl8.html)): chunk `u8 n_opaque`; `0` → `u8` transparent run (index 0); `N` → N indices. Implemented in `decode_pl8.py` (`rle_decode`) **with no sample in this install** — not exercised. Do not invent 0,0 = 256 or RLE+ISO until a file with bit 0 appears.

EXE side (not pixel-reversed): named `.pl8` / `.256` go through `load_file` into heap buffers (`0x102414`, …). Zoom 1/2/3 filename triples are **data**, not computed from flags. ISO diamond immediates (900 / 1740) were **not** found in a quick scan.

### Palettes and export (`images/`)

147 `.256` files (all 768 B). Resolution in `resolve_palette`:

1. `{stem}.256` if present (**143** PL8)
2. exact alias: `CITYFIX2/3`→`CITYFIXT`, `PROVFIX2/3`→`PROVFIXT`, `BATLFIX3`→`BATLFIX2`, `RAT_FRON`→`RAT_BACK`, `FORUMBIT`→`FORUM`, `E_PARTS*`→`EMPIRE`, `INT_BATL`→`BATT1`, `INT_CITY`→`CITY1`, `INT_PROV`→`PROV1`, `HORSEB`→`BATT1`, `FONT*`→`CITY1` (**15**)
3. family: `BUILD*`/`HOUSES*`/`CITY*`/`OVERLAY*`/`LANDFILL`/`LTLMEN*` → `CITYFIXT`; `PROV*`/`PRVBLD*`/`MOUNTNS*` → `PROVFIXT`; units `RO/GM/GL/GK/EG/AF/AR/BR/CA/HN/PA`+digit and `MY_STDS*`/`PACAVA*` → `BATLFIX2`; UI `ICONS`/`MOUSE`/`SYSTEM`/`PANELS`/`MAIN`/`MISC`/`SMACKER` → `CITY1` (**141**)
4. documented fallback: `CITYFIXT.256`

Measured identities (equal bytes): `CITYFIXT == PROVFIXT`; `CITY1 == CITY2 == VIEW1 == PROV1`; `BATT1 == BATT2`; `BATLFIX2` differs from `BATT1` in **1** byte. `CITYFIXT` vs `CITY1`: 730/768 equal (cycle slots?).

`python tools/decode_pl8.py --export-all` → `images/{stem}.png` (1 sprite) or `images/{stem}_sheet.png` (n>1). **299/299** on this install. Gitignored. Root sheets already good (`AHOUSE.png`, `BUILD1A_sheet.png`, `CITYFIXT_sheet.png`, `HOUSES1_sheet.png`) kept.

### ISO (tile_type 1–4) — exercised and closed on these bins

58×30 diamond = **900 bytes** on disk (not 1740 = 58×30 unpacked). Decoder: `tools/decode_pl8.py`. Base algorithm from [pl8image](https://pl8image.readthedocs.io/en/latest/.pl8.html); community field sizes were slightly wrong — the **16-byte** records measured here are the source.

Packed size (58×30):

| tile_type | On-disk payload | Extra rows on canvas |
|---|---|---|
| **1** | always **900** (diamond only), **even if `extra_rows` > 0** | canvas = 30; `extra_rows` is metadata, not payload |
| **2** | 900 + extra × **58** | canvas = 30 + extra |
| **3** / **4** | 900 + extra × **30** | canvas = 30 + extra (left / right strip) |

The same geometry scales: zoom 2 **26×14** diamond = **196** B (`BUILD2A` 123/123); zoom 3 **10×6** = **36** B (`HOUSES3` 106/106). Extra type 2 = extra×W; type 3/4 = extra×(W/2+1) — the chain closes with no new rule.

`sprite[0].data_offset == 8 + 16 × n_sprites` — held on all samples. `span == packed_bytes` used as proof: each sprite occupies exactly the interval to the next offset (last to EOF, ignoring zero slack).

| File | sprites | types | chain | Palette | Local sheet (gitignored) |
|---|---:|---|---|---|---|
| `AHOUSE.PL8` | 1 | 0 | 1/1 (bitmap 182×132) | `AHOUSE.256` | house on grass |
| `HOUSES1.PL8` | 106 | 1–4 | **106/106** | `CITYFIXT.256` | tents → insulae, walls, reservoirs |
| `BUILD1A.PL8` | 123 | 1–4 (59/16/24/24) | **123/123** | `CITYFIXT.256` | roofs, plazas, walls, props |
| `CITYFIXT.PL8` | 140 | 1×133 + 0×7 | **140/140** | `CITYFIXT.256` | grass, trees, river, aqueducts; 7 bitmaps 2×2 / 2×3 |

`CITYFIXT` forced the type-1 rule: 133 type-1 sprites with `extra_rows` 4–30 but span **900**. Treating extra as type 2 (`900+extra×58`) broke the chain.

### Battle naming convention

Pattern `XXnWWWW[X].PL8`:

- Faction/unit prefix: `RO` Roman, `GM`/`GL`/`GK` (Gaul/German/Greek **hypothesis**), `EG` Egypt, `AF`/`AR` Africa/Arabia, `BR`, `CA`, `PA`, `HN` Hannibal, …
- Digit `2` / `3`: **zoom** (matches flags `0x0002` / `0x0102` / `0x0202` and geometry 58×30 → 26×14 → 10×6)
- Weapon: `SWDA`/`SWDB` sword, `SPRA`/`SPRB` spear, `BOWC` bow, `KNFB` knife, `CAVA` cavalry, `SLGC` sling, `JAVC` javelin
- Suffix `X`: variant (mirrored / dead / player?)

Matches the classic community complaints (`RO2SWDA.PL8 not found`) — **these files are in this folder.**

---

## 3. `.RAW` — not the second graphics pipeline

73 files. **No magic.** A/B/C series: almost all start with a run of `0x7F`. `C34.RAW` starts with a gradient (`96 98 99 9B…`). `PREBATLE.RAW` (846 335 B) starts `80 80 81…`.

No RAW has size 307200 / 307224 → **not** raw 640×480 screens.

### Retraction: `A01.RAW` ≠ 448×448 framebuffer

200 704 = **448×448 = 0x31000** is only the size (round factorization). Wrap at 448 (and at 256 / 320 / 512 / 640 / 224 / iso-diamond 894×448) produces the same look: horizontal static bands + solid `7F` bars.

The user PNG (`A01_view1`) used `VIEW1.256`: neighbouring indices (~127±30) become magenta/cyan/yellow. That is **not** landscape — it is a tile palette on a 1D signal.

Measurements that kill the 2D layout:

| Test | Result |
|---|---|
| Mean Δ lag 1 | **5.2** (smooth 1D signal) |
| Mean Δ lag 64…800 | **~33** at *all* widths (file stdev ≈ 36) — no line period |
| vm/hm on 70+ widths | always **~6.3**; fraction of vertical neighbours with Δ≤8 ≈ 21% |
| alignment of `7F` runs | no W makes the bands start at col 0 |
| skip header 0–128 | no improvement |
| PCX / PackBits / count-value / `7F`-escape RLE | fails (E25) |
| ISO type-1 packing (H²=200704) | diamond with the *same* `7F` bands + shear |

The “ramps” on row 7 (`80,76,71…`) are consecutive samples, not a horizon.

### Confirmed: PCM 8-bit unsigned mono 22050 Hz (H1)

City `.WAV` files in the install (`A09.WAV`, `FIRE.WAV`, `SWORDHT.WAV`, …) are **PCM unsigned 8-bit mono 11025 Hz**. The `.RAW` banks use the same sample format at **22050 Hz**. The EXE talks Miles / `AIL_set_sample_address` (PCM without RIFF) and `null.voc`.

| Signal | RAW | City WAV |
|---|---|---|
| Byte | 8-bit unsigned, ~248 values | 8-bit unsigned |
| Rate | **22050 Hz** (A01 heard) | **11025 Hz** |
| Center | `0x7F` (A/B/C) or `0x80` (`PREBATLE`) | `0x80` |
| Long runs | silence (A01: ≈0.13s + 0.83s + 0.76s @ 22050) | silence |
| Envelope | 3 bursts (A01); attacks (C34) | SFX with pauses |
| Sizes | variable (A09=23 121 … C39=261 814) | clip duration |

A01 @ 22050 Hz ≈ **9.1 s** (200 704 / 22050), three activity blocks — long clip (voice / ambience / sting), not a tile. At 11025 Hz it sounded at **about half speed** (~18.2 s); 32000 Hz was chipmunk — do not use.

`A09.WAV` (11 560 samples) and `A09.RAW` (23 121 B = 2×11560+1) are **not** the same payload (MAD≈35). Shared name is coincidence or another take; sample *format* matches, rate does not.

Decoder: `tools/decode_raw.py` (default = waveform / `--rate 22050`; `--export-all` → `sound/`; `--width` only for experimental wrap). PNG/WAV local only.

### End cut (C31) — closed

The user heard `preview\C31.wav` end at *“… but its resources seem worth the …”* (Germania Superior line: *“… worth the danger”*). 22050 Hz is the correct speed; the tail is missing.

Hypotheses tested (C31.RAW = 191 857 B = **8.701 s** @ 22050):

| Hypothesis | Result |
|---|---|
| WAV `data`/`RIFF` shorter than the PCM | **No.** `C31.wav` = RAW+44; `data` chunk = 191 857; `pcm == raw` |
| Decoder cutting `0x7F` / silence / footer | **No.** `write_pcm_wav` writes the whole file; the last **1860** B are already `0x7F` *in the RAW* |
| Length field in a header | **No.** No magic; `le32[0]` = `7F7F7F7F`, not a size |
| Last bytes = 16-bit / 2nd chunk | **No.** Tail = u8 silence `7F` (last 2 k: std≈0) |
| Continues in `C32.RAW` | **Unlikely.** C32 is another complete clip (~8.77 s). C31 already ends in silence (~0.12 s). Concat = two lines, not the word *danger* |

C31 envelope (energy |s−7F|>4, gaps ≤100 ms): 0.13–1.31 s, 2.31–5.63 s, 6.39–7.90 s, **8.01–8.58 s** (0.56 s, std≈35 — normal volume). Then only `7F` pad. The last burst fits *“worth the”*; *“danger”* (~0.4–0.5 s) **is not in the payload**.

**Verdict:** the PCM on disk already ends mid-sentence. Not a WAV-writer or decoder bug. C32 (and A02/A05/…) are siblings of the same series, not tails. Disk series: A01–09, B01–20, C01–43, `PREBATLE` (EXE still cites a10–a30 / b21–b30 / c44).

Canonical export: `sound\{stem}.wav` + `_waveform.png` + `_spec.png`.

---

## 4. Data, text, saves

### `C2.ENG` (31 876 B) — UI strings (format closed)

```
0000  "Textfile"          # 8 bytes, no NUL
0008  u32 0               # not an offset
000C  u32 offsets[n]      # absolute, LE; n = (offsets[0] - 12) / 4
          → Latin-1 C-string pool (NUL)
```

Measured: **n = 146**, **142 unique offsets** (4 aliases). Pool at 596…31784, slack 92 B. Offsets are **not** strictly increasing — the same pointer can serve several IDs (e.g. `"To"` at indices 115–145, phrase fragments).

Extractor: `tools/extract_eng.py`. Full dump in `notes/c2_eng_strings.txt` (gitignored — original game text).

Index 0–23 is menu + query vocabulary (sample, not the file): `File`, `Options`, `Speed`, `Help`, `Prima Cohors`, `Latium`, `Romans`, `Citizen`, `Caesar II - Version 1.1`, `Reservoir`, `Wall`, `Baths`, `Market`, `Wheat`, `Gems`, `Clay`, `Aventine`, `Grammaticus`, `Shrine`, `Theater`, `Tent`. Calendar: `January`, `BC`, `Week 1`. Difficulty: `Novice`. This file does not contain `Decurion` / `Consul` / `Janiculan` / `Fountain` / `Impossible` — those are in the EXE / `HELP.ENG`, or composed.

`HELP.ENG` (455 194 B): magic **`Helpfile`**, 58 zeros, first payload at offset 66 (`u32 116008`, then ASCII `null.p…`). **Not** the same offset table. Format still opaque.

### `C2MODEL.DAT` (4360 B = **1090 × int32 LE**)

No magic. Dump: `tools/dump_c2model.py`. Labeled JSON: `findings/c2model_tables.json` (numbers + labels, no binary). Cross-checked against the Falanx / caesar2.com FAQ (v1.0 numbers; this install is 1.1A).

**Not a uniform record array.** 1090 divides as 2, 5, 10, 109, 218, 545; whole-file stride 5 or 10 does not yield one record type. The file is a **concatenation of named tables** with zero-run pads as separators.

**Named:** **751 / 1090 = 68.9%** at high+medium confidence (**493 / 1090 = 45.2%** high only). Unknown / low: 291 + 1 unlabeled + 47 pad zeros.

| Indices | Conf | Meaning |
|---|---|---|
| 0–4 | medium | Difficulty scalars `20,15,10,5,2`. **Not** promotion counts (`5,7,10,15,20` are **absent**). |
| **5–9** | **high** | **Starting money** Novice→Impossible: `20000,15000,12000,7000,5000` |
| 10–14 | medium | Money-like `2000,500,250,150,100`. Hypothesis: per-province cut / stipend |
| **115–117** | **high** | **Shrine 80, Temple 200, Basilica 600** |
| **118–123** | **high** | **Theater 300 … Circus Maximus 2500** |
| 124–156 | high | Ramp `0,5,10,…,160` — rank `20…65` at `[128]` is a **subsequence coincidence** |
| **197–205** | **high** | **Province costs:** Road 20, Wall 50, Fort 500, Work camp 100, Farm 250, Port 1000, Warehouse 150, Shipyard 400, Trading post 500 |
| **215–246** | **high** | **Housing occupancy**, 32 grades, exact FAQ (one hut=2 … large palace=500) |
| **247–278** | **high** | Tax / wealth per house (imperial insula ~1.07× vs simple domus 3.2×) |
| **500–563** | **high** | Housing land `(bonus, radius)` × 32 |
| **564–611** | **high** | Forum + worship land, exact FAQ |
| **732–789** | **high** | Other buildings `(bonus, radius)` × 29 |
| **790–889** | **high** | **Individual rating %**, 5 difficulties × 20 rank slots. `99` = unused |
| **890–989** | **high** | **Average rating %**, same shape |
| **1020–1022** | **high** | Imperial tax brackets `8000, 5000, 3000` (percents `10/19/26` **absent**) |

City costs are **not** in FAQ water→sanitation order; they are grouped by family (worship, entertainment, province). FAQ v1.0 listed 10 ranks (Citizen…Consul); 1.1A has **20 slots**. Promotion **counts** themselves are EXE-side. Required housing LV `0,2,…,64`, pop unlocks, and tax percents are **absent** (computed in the EXE, or dropped in 1.1A). Full range list: `findings/c2model.md`.

`H2` stays **partially confirmed**.

#### Loader — still open (Ghidra)

- Filename **`C2MODEL.DAT` is not an ASCII string** in `PS.EXE` (unlike `history.dat` / `regions.dat`).
- The **4360-byte file is not embedded** in the mapped LE image: the first 80 bytes of the DAT do not occur there (aligned or not). Immediate **4360** is absent. Immediate **1090** appears three times (`0x84294`, `0x85112`, `0x88207`) as `mov r/m32, imm` — possible loop bounds, not a memcpy of the DAT.
- The five starting-money values occur **once**, unaligned (VA `0x096F2F` / file 1 015 763). Treat as coincidence or a packed subsequence until Ghidra shows a real load.
- Raw-file greps near EOF (C2MODEL workstream) found matching int32 runs at file offsets such as 1013767 / 1014283 / 1011391. Those hits sit **outside the mapped LE objects** (`pages_loaded=0` in that session). They are **not** evidence that the DAT is copied into `.data`.

**Unresolved:** how the 1090-int table gets into memory — constructed 8.3 name, a record inside another DAT, editor-only file, or a 1090-int copy whose destination is not yet xref’d.

### `REGIONS.DAT` (158 400 B)

No ASCII; map/index-like bytes (`15 98 11 17…`). EXE load at `0x706C6`: `ecx = 3600 * index`. **158400 / 3600 = 44** records. Dest base `[0xC4D10]`. **Hypothesis:** empire-layer province / terrain map. Geometry 396×400 or 180×880 — do not nail it. Same pointer later receives the 4000-byte `history.dat` blob during save/load — **aliased or reused**. Lifetime needs Ghidra.

### `HISTORY.DAT` (4000 B, dated 2011)

Mixed int32s (including negatives `D5 FE FF FF` = −299). **Confirmed role in the save path:** trailer of every `.SAV` is a copy of this blob (`sav_write` reads 4000 B from `history.dat` and appends them; `sav_read` writes them back). Player campaign / high-score blob, not retail CD. Older “campaign history” hypothesis is consistent with that.

### `DISCS.DAT` (256 B) + `DISCS.IX` (1996 B)

Referenced via `cd.dat` in the EXE. **Hypothesis:** CD layout / on-disc file catalogue.

### `FORUM_X.GD8` (3040 B)

Starts with zeros. EXE string next to `forumbit.pl8`. Load sites use `ebx=4000` (same size as history — coincidence or shared helper). **Hypothesis:** forum geometry/overlay, not text.

### Saves `.SAV`

Three files, all **225 745** B, no ASCII magic, MD5s distinct. FELIPE01 vs FELIPE02 ≈ **26%** different (distinct campaigns — useless as a 1-house delta). City name / player name / `FELIPE` / `Latium` / `Novice` / `Rome` are **not** Latin-1 anywhere in the save. Player name `Sophia Dex` lives in `CAESAR2.INF`, not `.SAV`.

`LASTYEAR.SAV` is the year-end autosave the EXE already knows (`lastyear.sav` at `0x34DBF`). Same size, not a different format.

#### Writer layout (confirmed) — **not** “1745 header + 35×6400”

`sav_write` (`0x70174`) / `sav_read` (`0x7024A`) walk a **scatter-gather table**, not one `fwrite` of a header plus 35 planes:

```
struct SavChunk { void *ptr; u32 size; };   // 8 bytes, 500 slots
SavChunk sav_chunks[500];                   // VA 0x9ABC0
```

Loop `ecx = 0 … 0x1F4-1` (500). First `size == 0` would end the loop; in this build **all 500 slots are live**. Slots 432–499 are 68 copies of the same 4-byte cell at `0x117D70` (padding / unused handles).

```
table bytes  = 221745
+ history    = 4000          // HISTORY.DAT; pointer [0xC4D10]
             = 225745        // exact .SAV size
```

Full 500 rows: `notes/ps_sav_chunks.tsv` (`index, ptr_va, size, file_off, note`). Do not copy `.SAV` into git.

| idx | ptr VA | size | file off | Note |
|---:|---|---:|---:|---|
| 0–3 | `0x117A8D`, `0x117A59`, `0x117A8B`×2 | 1 | 0 | flag bytes. Named saves share `u8@1=4`; `LASTYEAR` is `00 00 01 01` |
| 4 | `0x102BE0` | 4 | 4 | also written after save (`0x70307`) |
| **5** | **`0x102BA4`** | **4** | **8** | **u32@8** — year-BC **hypothesis** (50 / 29 / 33) |
| 6 | `0x102BA0` | 4 | 12 | u32@12 (54 / 56 / 18) — unknown |
| 7 | `0x114500` | 4550 | 16 | large blob (old “header tail” lives here) |
| 8 | `0x1107A4` | 11658 | 4566 | |
| 9 | `0x113560` | 3978 | 16224 | |
| 10 | `0x0D361C` | 17688 | 20202 | |
| 11 | `0x115702` | 9045 | 37890 | contains the 6400-zero run (old “plane 6”) |
| 12 | `0x102DE4` | 3460 | 46935 | |
| **13** | **`0x0E2FBC`** | **128000** | **50395** | **20 × 6400 = 20 × 80×80.** Strongest city-map SoA. BSS (no file backing). |
| 14 | `0x0D94FC` | 28800 | 178395 | 4.5×6400 — not an integer plane count |
| 15 | `0x103B68` | 100 | 207195 | |
| 16–254 | mostly `0x102xxx` | 1–4 | … | globals |
| 255 | `0x0E057C` | 10816 | 208338 | sits immediately after the 28800 block |
| 335 | `0x0D2AEC` | 256 | 219524 | |
| 339 | `0x0D2B6C` | 768 | 219792 | |
| 387–389 | `0x0D2EFC` / `0xD2F4C` / `0xD2EAC` | **80** each | 220872 | one map **row** or **column** (or 80 flags) |
| 432–499 | `0x117D70` | 4 × 68 | 221473 | padding |
| trailer | `[0xC4D10]` | 4000 | **221745** | `history.dat` |

The **20 contiguous 80×80 planes** at BSS `0xE2FBC` (128 000 B) are the in-engine map object to name with a controlled house/road pair.

#### Static size identity (still true as arithmetic)

`1745 + 35 × 6400 = 225745` remains exact on all three files. It is **not** how `sav_write` walks the file. `tools/probe_sav_map.py` still uses that split for occupancy PNGs (`sav_preview/`, gitignored) — useful pictures, **wrong writer IDs**.

Proof that the bytes are SoA-ish rather than 35-byte AoS: old “plane 6” is **6400 consecutive zeros** in all three files. An AoS of 35 bytes/tile would scatter those zeros every 35 bytes. The old 40×40×31 @ 176128 hypothesis stays dead.

Static header facts that survive remapping:

| File | u32@0 (bytes 0–3) | u32@8 (chunk 5) | u32@12 (chunk 6) | nonzero in first 1745 |
|---|---|---:|---:|---:|
| `FELIPE01.SAV` | `00 04 00 00` (1024) | **50** | 54 | 120 |
| `FELIPE02.SAV` | `00 04 00 00` (1024) | **29** | 56 | 130 |
| `LASTYEAR.SAV` | `00 00 01 01` | **33** | 18 | 57 |

`u32@8` = year BC is still a **hypothesis** (`C2.ENG` has `January` / `BC` / `Week 1`; three plausible late-Republic years; not month). After offset 16 the old “header” is sparse; FELIPE02’s first nonzero after +16 is at 541 vs 191 on the others (**hypothesis:** 350-byte career / assignment slot). Cross-file compares of that region must use relative offsets. No field matches C2MODEL starting money on these mid-game saves (expected if money was spent). Difficulty is **not** stored as the string `Novice`.

#### Remap: old 35-plane IDs → 500-chunk TSV

Old probe offset = `1745 + i×6400`. Those windows **cut across** writer chunks and are phase-shifted by **2550 B (~31.9 rows)** relative to chunk 13.

| Old plane | File range | Writer chunks (measured) | Keep / drop |
|---:|---|---|---|
| 0 | 1745–8144 | **7** (2821 B) + **8** (3579 B) | mixed blobs, not a map plane |
| 1 | 8145–14544 | **8** only | same |
| 2 | 14545–20944 | **8** + **9** + **10** | straddles three chunks |
| 3–4 | 20945–33744 | **10** (`0xD361C`, 17688 B) | interior of one blob |
| 5 | 33745–40144 | **10** + **11** | |
| **6** | 40145–46544 | **11 only** (`0x115702`, 9045 B) | **6400 zeros are real**, but they are a hole *inside* this blob — not a reserved city-map plane |
| 7 | 46545–52944 | **11** + **12** + first 2550 B of **13** | smear |
| **8–26** | 52945–174544 | **13** (`0xE2FBC`, 20×6400) | **real map bytes**, but each old “plane” is engine-plane *k* rows 32–79 **plus** engine-plane *k+1* rows 0–31 |
| 27 | 174545–180944 | tail of **13** + head of **14** | smear |
| **28–31** | 180945–206544 | **14** (`0xD94FC`, 28800 B) | static “building candidates” live **here**, not in the 20-plane block. Still phase-shifted 2550 B vs a 4.5×6400 split of chunk 14 |
| 32 | 206545–212944 | tail of **14** + **15** + ~240 tiny globals + head of **255** | **not** a tile-ID plane |
| 33 | 212945–219344 | rest of **255** (10816 B) + small globals | same |
| **34** | 219345–225744 | **209 writer slots** + **4000 B `history.dat` trailer** | **not water.** History starts at fake-plane row **y = 30.0**. The three 80-byte chunks sit at y≈19.1 / 20.1 / 21.1 — enough to paint a horizontal band in an 80×80 PNG |

Engine map planes (the ones to name next):

`file_off = 50395 + i×6400` for `i = 0…19`, VA `0xE2FBC + i×6400`.

#### What the static PNGs still support (as hypotheses, remapped)

- Spatial structure exists in chunk 13 (old 8–26 smeared) and chunk 14 (old 28–31). Vertical N–S strips and 2×2 clumps on career cities are real occupancy, just **mis-sliced**.
- High bytes 248–255 look like a sentinel family on developed cities and are nearly absent on LASTYEAR in the old 28–31 window (chunk 14).
- CITYFIXT-as-raw-index **fails** as a whole-plane rule (`max ≥ 250` on almost every occupied old plane). `OVERLAY1.PL8` having 35 sprites matching 35 planes is **coincidence**.
- Old plane 5’s 13 shared exact cells (e.g. `(56,52)=1`) sit in the chunk 10/11 boundary — rare markers, not houses.
- Old plane 34’s “river at y≈20–40, mode 255, south half empty” is at least partly a **visualization artifact** of drawing `history.dat` + 80-byte rows as an 80×80 image. Do not treat it as a water layer until chunk 13 / the 80-byte slots are viewed on their own.

#### What is *not* true

- Not 40×40.
- Not AoS of 35-byte tiles.
- Not “the on-disk writer is 1745 + 35×6400” — that is a size identity only.
- Not “every old plane is a CITYFIXT sprite index 0…139”.
- No checksum field identified. Do not invent one.
- Header has no Latin-1 city name.
- Do not hand-edit a `.SAV` for `PS.EXE` to load.

### `CAESAR2.INF` (64 B, 2011)

Contains player name `Sophia Dex` — save metadata / profile, not retail 1995.

### `RESOURCE.CFG` (51 B)

```ini
[Config]
resaud=M
resmap=M
ressfx=M
rescdis=M
```

String `resource.cfg` exists in `PS.EXE` (`load_file_cfg` at `0x2456E`). Value `M` remains **opaque** (original CD = 283 bytes). Hypothesis unchanged: HD/CD origin code written by Sierra INSTALL, not an SCI path.

---

## 5. Audio and video (public formats)

| Type | Magic / evidence | Notes |
|---|---|---|
| `.XMI` | `FORM` … `XDIR` `INFO` `CAT ` | Miles XMIDI. 5 tracks: `BATEST2`, `CITYPROV`, `FORUM1–3` |
| `.SMK` | `SMK2` (14/14); no `SMK4` / AVI / FLC / FLI | Smacker (RAD). See §5.1 |
| `.WAV` | PCM; names match buildings/combat | Miles digital (`DIG.INI` → `SBLASTER.DIG`) |
| `.AD` / `.OPL` | `CAESAR.AD`, `CAESAR.OPL` | Hypothesis: AdLib/OPL fallback |

Miles AIL **3.02** (18-Jan-95) in `DIG.INI` / `MDI.INI` / `AILDRVR.LST`.

### 5.1 `.SMK` — Smacker (RAD Game Tools), not a new codec

14 files, **18 037 256** B, all in the install root. Magic **`SMK2`** (4 bytes). Public **104** B header ([wiki.multimedia.cx/Smacker](https://wiki.multimedia.cx/index.php/Smacker)): `Width`, `Height`, `Frames`, `FrameRate` (signed), `Flags`, `AudioSize[7]`, Huffman trees, `AudioRate[7]`.

`FrameRate` on this install: **−8333** → fps = `100000/8333` = **12.00** (13 clips); `MESSAGE` = **−7100** → **14.08** fps. `Flags` = 0 (no ring frame / Y-double).

Audio (`AudioRate[0]` = `0xC0005622` on all): bit 31 compressed + bit 30 present; **22050 Hz, 8-bit, mono, DPCM** (Smacker Huffman). ffmpeg 9.0.1 (Gyan): `smackvideo` `pal8` + `smackaudio` (`smackaud` / `SMKA`) **22050 Hz mono u8**. Same rate/width as the `.RAW` banks — another pipeline (video vs AIL), same sample format.

No `.AVI` / `.FLC` / `.FLI`. `SMACKER.PL8` + `SMACKER.256` is **UI chrome** (already in `images/`), not a clip.

| File | Bytes | Res | Frames | fps | dur | Role (name) |
|---|---:|---|---:|---:|---:|---|
| `ARMYWARN.SMK` | 462 504 | 320×152 | 50 | 12 | 4.17 s | army warning |
| `BATTLOST.SMK` | 1 212 792 | 320×152 | 90 | 12 | 7.50 s | battle lost |
| `BATTWON.SMK` | 1 134 136 | 320×152 | 120 | 12 | 10.00 s | battle won |
| `CONGRAT.SMK` | 1 074 088 | 320×152 | 126 | 12 | 10.50 s | congratulations / rank |
| `FIRE.SMK` | 1 543 704 | 320×152 | 150 | 12 | 12.50 s | fire |
| `INTRO.SMK` | 791 340 | **640×480** | 360 | 12 | 30.00 s | intro / title (only fullscreen) |
| `LOSEGAME.SMK` | 1 587 792 | 320×152 | 193 | 12 | 16.08 s | campaign defeat |
| `MESSAGE.SMK` | 664 576 | 320×152 | 121 | **14.08** | 8.59 s | message |
| `PROMOTE.SMK` | 1 535 764 | 320×152 | 120 | 12 | 10.00 s | promotion |
| `RIOTERS.SMK` | 1 045 912 | 320×152 | 120 | 12 | 10.00 s | riot |
| `ROBBERY.SMK` | 724 260 | 320×152 | 120 | 12 | 10.00 s | robbery |
| `SICK.SMK` | 1 217 164 | 320×152 | 120 | 12 | 10.00 s | sickness |
| `WARNING.SMK` | 557 868 | 320×152 | 56 | 12 | 4.67 s | warning |
| `WINGAME.SMK` | 4 485 356 | 320×152 | 437 | 12 | 36.42 s | campaign victory (largest) |

320×152 is a letterbox window in the 640×480 UI (fits `SMACKER.PL8` chrome). `INTRO` is full VGA; frame 0 = embossed “CAESAR II” card. `WINGAME` / `LOSEGAME` start on a black frame (fade-in) — 1 kB PNG, not a decode failure.

Export: `python tools/decode_smk.py --export-all` → ffmpeg `libx264` + AAC in `videos/{stem}.mp4` and `{stem}_frame0.png`. **14/14** on this 1.1A. ffmpeg warned `Skipping FULL tree` on `INTRO.SMK` (empty Huffman tree); the MP4 still came out 30 s / 640×480. Gitignored. Do not copy `.SMK` into git.

Our decoder **does not** implement Smacker — it only reads the 104 B header and calls ffmpeg. Codec = `smackvid` / `smackaud` in the Gyan binary. FFmpeg 9.0.1.

---

## 6. Comparison with Caesar III / Pharaoh

| | Caesar II (these bins) | C3 / Pharaoh |
|---|---|---|
| Color | 256 colors, `.256` palette | 16-bit `.555` |
| Sprite catalogue | **inside the `.PL8` itself** (count + records) | `.SG2`/`.SG3` separate from the pixel dump |
| City tile | PL8 sprites **58×30** (`BUILD*`, `HOUSES*`, `CITYFIXT`) | **58×30** diamond in `.555` |
| Fullscreen | PL8 640×480 | BMP/555 / SG panels |
| Palette | `.256` 768 B RGB | embedded / 16-bit |
| Engine | Watcom 32 + DOS/4GW (`PS.EXE` LE `c2_x`) | Win32 C3 |
| Saves | 225 745 B fixed; **500-chunk scatter** + 4000 B history | other layout |

**58×30 in C2 is already the C3 diamond.** Direct ancestor of the tile; the *container* changed (PL8 → SG2+555). Augustus parsers **do not** open these files, but a PL8-58×30 → modern atlas converter is the most promising shortcut.

`.RAW` has no obvious C3 equivalent (and is not graphics).

---

## 7. Next steps (reprioritized)

1. **Ghidra GUI next:** **G `3CF9A`** (`view_frame`; redefine end `0x3D3E5`) then **G `459D0`** (`walkers_tick`). City walk: `findings/ghidra_city.md`. Still want a **1-house `.SAV` pair** (`diff_sav.py` + `notes/ps_sav_chunks.tsv`). Chunk 13 is **80×80×20 AoS** (not 20 SoA planes); chunk 14 is **60×60×8** province tiles. Do **not** hand-edit a save for `PS.EXE`.
2. **C2MODEL:** ints **0–14** are embedded at **`0x96F1B`**. Filename still absent; ints 15+ and the three `1090` sites are **not** a DAT loader (CRT dwords).
3. **RAW:** rate **22050 Hz** and dump in `sound/` done. In the EXE, confirm A/B/C as AIL banks (battle vs city / province VO). C31 cut = short payload on disk, not the decoder.
4. **PL8:** decoder 0–4 + zoom 26×14 / 10×6 + `--export-all` → `images/` (**299/299**). RLE bit 0 **does not exist** in these bins. Ghidra on the first use of a `houses1.pl8` buffer after `load_file`.
5. **`HELP.ENG`:** magic `Helpfile` + offset 116008 is not the `Textfile` table; parse only if we need help text.
6. Original CD still useful for the 283 B `RESOURCE.CFG` and for RAW A10+ if they exist.

Do not prioritize XMIDI (libs exist). Smacker is closed on this install (ffmpeg). Do not prioritize crack / CD check.

Done this phase: PL8 decoder 0–4 (incl. zoom 2/3); export `images/`; `C2.ENG`; `C2MODEL.DAT` tables (~69% named); `.SAV` writer = 500-chunk scatter + 20×80×80 BSS; `.RAW` retracted as image (H1 = PCM 8-bit unsigned mono **22050 Hz**); `.SMK` inventoried + remux `videos/` (**14/14**); `PS.EXE` LE map + sav table; Ghidra project on mapped `c2_x` (`findings/ghidra.md`). Dumps in `notes/` / `ghidra_work/` (gitignored).

---

## 8. Evidence log

| ID | Observation | Kind |
|---|---|---|
| E1 | README v1.1A; `C2.ENG` “Version 1.1”; `PS.EXE` 1995-10-04 | fact |
| E2 | `PS.EXE` 1040111 B, MZ + DOS/4GW + Watcom C/C++32 | fact |
| E3 | `.256` = 768 B RGB | fact |
| E4 | PL8: `dataOff0 = 8+16×N`; `AHOUSE` 182×132; `TUT_01A` 640×480 | fact |
| E5 | `BUILD1A` / `HOUSES1` / `CITYFIXT` sprite0 = **58×30** | fact |
| E6 | 3× `.SAV` = 225745 B, distinct MD5s | fact |
| E7 | `C2.ENG` magic `Textfile` + u32 offsets | fact |
| E8 | `C2MODEL.DAT` = 1090 int32 | fact |
| E9 | `INTRO.SMK` = `SMK2` 640×480; XMI = `FORM`/`XDIR` | fact (SMK expanded in E36) |
| E10 | EXE lists RAW a01–a30 / b01–b30 / c01–c44; disk has fewer | fact |
| E11 | Cursor index omitted EXE/PL8/SMK (OneDrive) | fact (methodology) |
| E12 | Palette `.256`: bytes 0–63; expand VGA 6-bit → 8-bit | fact |
| E13 | ISO 58×30 diamond = 900 B; type 2 extra×58; type 3/4 extra×30 | fact |
| E14 | Type 1: `extra_rows` in the record, payload stays 900 (`CITYFIXT` 133/133) | fact |
| E15 | span=packed chain: `HOUSES1` 106/106, `BUILD1A` 123/123, `CITYFIXT` 140/140 | fact |
| E16 | Visual sheets: houses/water (`HOUSES1`), river/aqueduct (`CITYFIXT`), plazas/walls (`BUILD1A`) | fact |
| E17 | `C2.ENG`: 146 strings, pool @ 596, 142 unique offsets; `"To"` aliases | fact |
| E18 | `C2MODEL[5:10]` = starting funds 20000…5000 (5 difficulties) | fact |
| E19 | `C2MODEL[215:247]` = occupancy 32 housing grades (FAQ) | fact |
| E20 | `C2MODEL[118:124]` entertainment costs; `[115:118]` shrine/temple/basilica | fact |
| E21 | `C2MODEL[196:206]` province costs (+ Gardens=3) | fact |
| E22 | FELIPE01 vs 02: 25.7% bytes different (distinct campaigns) | fact |
| E23 | `1745 + 35×6400 = 225745`; old “plane 6” = 6400 zeros in all 3 saves | fact (**size identity**, not writer layout — see E38) |
| E24 | `A01.RAW` = 200704 B = 448²; Δhoriz≈5.2; `7F` = center (ex-“sky”) | fact (size); 2D layout **retracted** |
| E25 | PCX/PackBits/count-value/`7F`-escape RLE does not close A02/A04/C01/PREBATLE | fact |
| E26 | No width 64–800 has vertical correlation (vm≈42, vm/hm≈6.3) | fact |
| E27 | City WAV = u8 mono **11025 Hz**; RAW shares histogram / `7F`/`80` silence | fact |
| E28 | Wrap 448 + `VIEW1.256` = neon static + `7F` bars (user PNG) | fact |
| E29 | A01.RAW @ **22050 Hz** = correct speed (~9.1 s); 11025 = half; 32000 = chipmunk | fact |
| E30 | C31.wav RIFF/`data` = whole RAW (191 857); no length field; tail = 1860×`7F` | fact |
| E31 | C31 last burst 8.01–8.58 s (std≈35); C32 = 8.77 s clip, not a suffix | fact |
| H1 | RAW A/B/C + `PREBATLE` = PCM 8-bit unsigned mono **22050 Hz** (Miles AIL) | confirmed (E29) |
| H2 | `C2MODEL` = economy tables — **partially confirmed** (E18–E21, E40) | hypothesis |
| H3 | `REGIONS.DAT` = province map (44 × 3600 confirmed; meaning hypothesized) | hypothesis |
| H4 | `M` in RESOURCE.CFG = HD/CD origin | hypothesis |
| E32 | 0/299 PL8 with flags bit 0; span=packed on 299/299; `RO2SWDA` = 178 bitmaps ~12×29 | fact |
| E33 | flags `0x0002`/`0x0102`/`0x0202` = zoom 58×30 / 26×14 / 10×6 | fact |
| E34 | `CITYFIXT.256 == PROVFIXT.256`; `CITY1 == CITY2 == VIEW1 == PROV1`; `BATT1 == BATT2` | fact |
| E35 | Sheets: `RO2SWDA` legionary + *scutum*; `GM2SWDA` brown tunic + round shield; `HOUSES1` tents→aqueducts; `TUT_01A` 640×480 panel | fact |
| H5 | Digit 2/3 on battle PL8 = zoom | confirmed (E33; exception `MY_STDS3`) |
| H6 | `.SAV` u32@8 (chunk 5, VA `0x102BA4`) = year BC | hypothesis |
| H7 | `C2MODEL[790:990]` = ranks × difficulty (`99` = empty slot) | confirmed as table shape (E40); FAQ names hypothesized |
| E36 | 14/14 `.SMK` = `SMK2`; 13× 320×152 @ 12 fps + `INTRO` 640×480 @ 12 + `MESSAGE` @ 14.08; audio `smackaud` 22050 Hz mono u8; 0 AVI/FLC/FLI; ffmpeg 14/14 | fact |
| E37 | `PS.EXE` = MZ stub + BW `VMM.EXP` + BW `4GWPRO.EXP` + tiny MZ + Watcom LE `c2_x` at `0x037D4C`; CS:EIP `0x72500`; 2 objects; 28451 fixups | fact |
| E38 | `sav_write` `0x70174` / `sav_read` `0x7024A`: 500 × `{ptr,size}` at VA `0x9ABC0` = 221745 B + 4000 B `history.dat` = 225745 | fact |
| E39 | 20 × 80×80 planes at BSS `0xE2FBC` (128000 B), file off 50395 (chunk 13) | fact |
| E40 | `C2MODEL` 751/1090 (68.9%) high+medium named; housing occupancy + rank 5×20 + land (bonus,radius) exact | fact |
| E41 | `C2MODEL` filename absent from EXE; DAT first 80 B not in mapped LE image; 1090 immediates ×3 | fact |
| E42 | `lastyear.sav` written from `0x34D92` (year-end autosave) | fact |
| E43 | Old 35-plane windows remapped onto the TSV: plane 6 ⊂ chunk 11; 8–26 = chunk 13 phase-shifted 2550 B; 28–31 ⊂ chunk 14; 34 = 209 slots + history trailer (y=30) | fact |
| H8 | Chunk 14 (28800 B @ `0xD94FC`) holds extra map-adjacent layers (old “building candidates”) | hypothesis |
| H9 | Old plane 34 “water band” is a PNG artifact of history.dat + 80-byte rows | hypothesis (strong; E43) |
| E44 | Ghidra 12.1.3 + Temurin 21; mapped `c2_x.bin` imported headless (base `0x10000`, entry `0x72500`, `SavChunk[500]` + known labels). How-to: `findings/ghidra.md` | fact (process) |

---

## 9. Out of scope

- Implementing a Godot/C++ engine in this phase.
- Copying / redistributing assets. Do not commit EXE / SAV / DAT / PL8 / SMK / RAW.
- Crack, CD bypass, EXE patch.
- Assuming Caesar III loaders open C2.
