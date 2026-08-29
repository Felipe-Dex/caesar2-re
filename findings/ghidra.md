# Ghidra — mapped `c2_x` (Caesar II `PS.EXE`)

Static analysis of the user’s own 1995 retail install. No EXE in git. No cracks / CD-check work.

The useful image is the **Watcom LE after 28 451 fixups**, not the MZ stub. `tools/ps_le.py --write-image` writes a raw x86-32 blob (base **`0x10000`**, entry **`0x72500`**, module **`c2_x`**). Importing `PS.EXE` as MZ stops at the 62 KB DOS/4GW stub and is useless.

---

## Installed on this machine

| Thing | Path |
|---|---|
| JDK 21 (Temurin) | `C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot` |
| `java.exe` | `C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot\bin\java.exe` |
| Ghidra 12.1.3 | `C:\Users\Felip\AppData\Local\Programs\Ghidra\ghidra_12.1.3_PUBLIC` |
| GUI | `…\ghidra_12.1.3_PUBLIC\ghidraRun.bat` |
| Headless | `…\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat` |
| Mapped image | `ghidra_work/c2_x.bin` (1 086 048 B, gitignored) |
| Project | `ghidra_work/c2_x.gpr` + `ghidra_work/c2_x.rep/` (gitignored) |
| Program in project | `/c2_x.bin` |
| Analyze log | `ghidra_work/analyze.log` |
| GhidraMCP 1.4 (plugin) | `%USERPROFILE%\.ghidra\.ghidra_12.1.3_PUBLIC\Extensions\GhidraMCP` |
| GhidraMCP bridge | `tools/ghidramcp/GhidraMCP-release-1-4/bridge_mcp_ghidra.py` |

Ghidra is **not** on winget (ZIP-only portable). Install used:

```text
https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.3_build/ghidra_12.1.3_PUBLIC_20260817.zip
SHA-256  93a5d11a9ad510622acaaf908c556a7b9b764d338e78a7567f3689bf5081fd54
```

JDK: `winget install --id EclipseAdoptium.Temurin.21.JDK` (Ghidra 12 wants **JDK 21**).

If `ghidraRun.bat` cannot find Java, set `JAVA_HOME` to the Temurin path above (winget already set the system JavaHome).

---

## First 5 clicks (open the existing project)

1. Double-click `C:\Users\Felip\AppData\Local\Programs\Ghidra\ghidra_12.1.3_PUBLIC\ghidraRun.bat`. Accept the license if this is the first launch.
2. **File → Open Project…** (not New Project).
3. Browse to the repo folder `ghidra_work` and open **`c2_x.gpr`**.
4. In the project window, double-click **`c2_x.bin`**. CodeBrowser opens at the mapped image.
5. **Window → Bookmarks**. Filter category **`C2`**. Those are the named VAs from `findings/ps_exe.md`.

Then: **G** (Go To) `72500` — that is CRT `start`, not `main`. **Game `main` is `c2_main` @ `0x10010`.** Boot walk (CRT → assets → Miles → `intro.smk` → title → city loop): **`findings/ghidra_walk.md`**. Set the decompiler calling convention in your head to **Watcom register: EAX, EDX, EBX, ECX**. Ghidra’s closest compiler spec is **`gcc`** (no Watcom cspec). Miles AIL wrappers are **stdcall**.

---

## GhidraMCP (Cursor ↔ running Ghidra)

Official release: [LaurieWired/GhidraMCP 1.4](https://github.com/LaurieWired/GhidraMCP/releases/tag/1.4) (2025-06-23). That tag **claims Ghidra 11.3.2**, not 12. There is no newer official release. Unmerged PRs (#164, #166) only bump `ghidraVersion` for 12.1.x (no Java source change). This machine’s copy of `extension.properties` was patched to **`ghidraVersion=12.1.3`** so Ghidra 12 will load it. If the plugin fails to start or HTTP 8080 never appears, that version gap is the first suspect.

There is **no** PyPI package named `ghidramcp`. The README Python side is the MCP SDK plus `bridge_mcp_ghidra.py` from the release zip.

| Thing | Value |
|---|---|
| Release zip | `https://github.com/LaurieWired/GhidraMCP/releases/download/1.4/GhidraMCP-release-1-4.zip` |
| Local unpack | `tools/ghidramcp/` (gitignored) |
| Plugin (user) | `C:\Users\Felip\.ghidra\.ghidra_12.1.3_PUBLIC\Extensions\GhidraMCP` |
| Plugin (install copy) | `…\ghidra_12.1.3_PUBLIC\Ghidra\Extensions\GhidraMCP` |
| HTTP bridge inside Ghidra | `http://127.0.0.1:8080/` (default; **Edit → Tool Options → GhidraMCP HTTP Server**) |
| Python | `C:\Users\Felip\AppData\Local\Programs\Python\Python314\python.exe` |
| pip | `mcp` **1.29.1** (README pin `>=1.2.0,<2`) + `requests` **2.34.2** |
| Cursor MCP | `~/.cursor/mcp.json` and `.cursor/mcp.json` (server name **`ghidra`**, stdio → bridge script) |

### Start order

1. Open Ghidra, then **`c2_x.gpr`**, then double-click **`c2_x.bin`** so **CodeBrowser** is the tool with the mapped image. The HTTP server only lives in CodeBrowser. Headless / the project window alone is not enough.
2. **One-time in Ghidra** (then restart Ghidra if it was already running when the files were copied):
   - **File → Configure → Developer** → enable **GhidraMCPPlugin**.
   - If it is missing: **File → Install Extensions** → `+` → pick `tools/ghidramcp/GhidraMCP-release-1-4/GhidraMCP-1-4.zip` (or the folder already under Extensions) → restart Ghidra → enable as above.
3. Confirm the plugin is up: browser or `curl http://127.0.0.1:8080/` while CodeBrowser is open. Then Cursor MCP (`ghidra`) can talk to it.
4. **Restart Cursor** (or reload MCP servers) after the `mcp.json` change. Cursor starts the Python bridge; Ghidra must already be serving 8080.

Do not start a long RE session from this install note. Keep `ghidra_work/`, the mapped `.bin`, and `PS.EXE` out of git.

---

## What is already named (headless post-script)

Applied by `tools/C2Symbols.java` after auto-analysis (also `tools/ghidra_c2_symbols.py` for the GUI Script Manager). Re-run either from **Window → Script Manager** if you wipe labels.

| Name | VA | Kind |
|---|---|---|
| `start` | `0x72500` | CRT entry (LE EIP) |
| **`c2_main`** | **`0x10010`** | game main (was `c2_early_init`) |
| `crt_cmain` | `0x7B881` | CRT wrapper → `c2_main` → `exit_` |
| `load_file` | `0x2444A` | EAX=path EDX=dst EBX=max |
| `load_file_cfg` | `0x2456E` | `resource.cfg` sibling |
| `gfx_load_boot_assets` | `0x10E89` | 14× `load_file` incl. `c2.eng` |
| `gfx_free_city_handles` | `0x10DCA` | free only (old name was wrong) |
| `load_c2_eng_site` | `0x10FC7` | mid-fn; dest `0xB831C` |
| `c2_eng_buf` | `0xB831C` | 40 000 B |
| `sav_write` / `sav_read` | `0x70174` / `0x7024A` | 500 chunks + history |
| `sav_chunks` | `0x9ABC0` | `SavChunk[500]` type applied |
| `sav_year_end` | `0x34D92` | `lastyear.sav` |
| `city_planes_20x80x80` | `0xE2FBC` | 20 × 6400 BSS |
| `raw_name_bank` | `0x93694` | 104 × 8.3 names |
| `AIL_set_sample_address_dbg` | `0x74300` | debug wrapper |
| `AIL_set_sample_address` | `0x7EA10` | real API |
| `push_22050_raw_rate` | `0x120A6` | `push 22050` |
| `apply_regions_map` | `0x706C3` | was `load_regions` @ `0x706C6`; dest `[0xC4D10]` |
| `open_` / `read_` / `write_` / `close_` | `0x722AD` / `0x77B37` / `0x7A995` / `0x724FB` | CRT I/O |
| `imm_1090_c2model_*` | `0x84294`, `0x85112`, `0x88207` | breadcrumbs only |

Memory blocks: **`.text`** `0x10000` RX length `0x7B9C0`; **`.data`** `0x90000` RW length `0x89260`. The LE gap `0x8B9C0`–`0x90000` was **unmapped** (not resident).

---

## What you name next (in the GUI)

Do not wait for another headless pass. Rename functions as you read them.

1. **`main` — done.** `c2_main` @ `0x10010`. City tick **`view_frame` `0x3CF9A`** (redefine end `0x3D3E5`). Details: `findings/ghidra_walk.md`, **`findings/ghidra_city.md`**.
2. **500 `SavChunk` slots** at `0x9ABC0` — the `SavChunk` type is on the array; name each `ptr` from `notes/ps_sav_chunks.tsv` after a 1-house save pair. Slots 432–499 are padding copies of `0x117D70`.
3. **C2MODEL loader** — filename is **absent**; DAT is **not** in this image. Start at the three `1090` bookmarks. Do not assume a `fopen("c2model.dat")`.
4. Optional: name the 20 planes at `0xE2FBC` after the same save pair; the `mov eax, 35` cluster `0x5FC11`–`0x5FFCE`; first use of a `houses1.pl8` buffer after `load_file`.

---

## Regenerate the image / re-import

```text
python tools/ps_le.py --write-image ghidra_work/c2_x.bin
```

Headless (already run once; close the GUI project first):

```text
set JAVA_HOME=C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot
set GHIDRA_HEADLESS_MAXMEM=4G
"%LOCALAPPDATA%\Programs\Ghidra\ghidra_12.1.3_PUBLIC\support\analyzeHeadless.bat" ^
  <repo>\ghidra_work c2_x ^
  -import <repo>\ghidra_work\c2_x.bin ^
  -loader BinaryLoader -loader-baseAddr 0x10000 -loader-blockName c2_x ^
  -processor x86:LE:32:default -cspec gcc ^
  -scriptPath <repo>\tools ^
  -preScript C2Layout.java -postScript C2Symbols.java ^
  -analysisTimeoutPerFile 1800 -log <repo>\ghidra_work\analyze.log -overwrite
```

### File → Import checklist (if you skip headless)

1. **New Project** (or open `c2_x`) → **Import File** → `ghidra_work/c2_x.bin`.
2. Format **Raw Binary**. Language **`x86:LE:32:default`**. Compiler **`gcc`**.
3. Options: base address **`0x00010000`**.
4. After import: **Window → Script Manager** → run `C2Layout.java` (splits `.text` / `.data`, entry `0x72500`), then **Analysis → Auto Analyze**.
5. Run `C2Symbols.java`. If you only want bookmarks, **G** to each VA in the table above and **Bookmark**.

Python twins (`ghidra_c2_layout.py` / `ghidra_c2_symbols.py`) are **PyGhidra** (Ghidra 12 default). This machine’s Python is 3.14, which 12.1.3 allows. Headless used the **Java** scripts so it does not depend on PyGhidra.

---

## Git

`ghidra_work/`, `*.gpr`, `*.rep/`, `*.gzf`, analyze logs, and the mapped `.bin` are gitignored. Do not commit the image, the Ghidra project, or `PS.EXE`.
