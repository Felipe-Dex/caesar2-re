# Ghidra walk — CRT → `c2_main`

Static analysis of the user’s retail `c2_x` image (Ghidra 12.1.3 + GhidraMCP). No EXE in git. No CD-check / crack work.

**Result:** the function formerly labeled `c2_early_init` **is the game `main`**. It was renamed **`c2_main` @ `0x10010`** (body `0x10010`–`0x10408`). There is no separate `WinMain`. The LE entry `start` @ `0x72500` is Watcom CRT only.

---

## Boot chain (VAs)

```
DOS/4GW stub
  → start            0x72500   Watcom CRT (LE CS:EIP). PSP / env / BSS wipe.
  → crt_InitRtns     0x7B8D0   priority constructor table
  → crt_cmain        0x7B881   stack guard, then:
       crt_InitRtns-ish 0x84EE9
       c2_main       0x10010   ← game; never returns except via exit_
       exit_         0x720F6
```

`start` does **not** call `c2_main` directly. Xref: `crt_cmain+0x7B8C1` → `c2_main`. After `c2_main` returns, `crt_cmain` calls `exit_`. Error paths inside `c2_main` also call `cprintf_` then `exit_` (the old “delay_ms @ 0x720F6” guess was wrong).

---

## `c2_main` — what it does, in order

Watcom register args (EAX/EDX/EBX/ECX). Ghidra’s decompiler often **drops** those args; call sites were confirmed in the listing.

| Step | VA / callee | What |
|---|---|---|
| Heap / DOS mem | `FUN_0007201b`, `FUN_0007202c` | CRT-ish. Fail → return (no game). |
| `resource.cfg` | `load_file_cfg` `0x2456E` | HD/CD origin letter. |
| Drive-letter prompt | `FUN_00011095` + strings at `0x90011`… | Exists. **Not followed.** |
| Zero GFX handles | `gfx_zero_handles_a` `0x10CB9`, `_b` `0x10D80` | Clears `0x1023xx` / `0x1024xx` pointers. |
| **Boot assets + ENG** | **`gfx_load_boot_assets` `0x10E89`** | 14× `load_file`. See list below. Fail → `cprintf_("File not found - code %d")` + `exit_`. |
| Zoom-1 PL8 set | `gfx_load_zoom_set` `0x107DB` | Table at `0x927E0`; `malloc_` + `load_file`. Fail string: `Error loading graphics data`. |
| Mouse | `mouse_detect` `0x259F9` | INT-style (`0x44`). Fail → `No mouse driver found.` + `exit_`. |
| **VESA / VGA** | **`video_init` `0x28341`** | `[0xCCB08]==2` → **640×480** (`0x280`×`0x1E0`); `==1` → 320×200. `malloc_` framebuffer `[0xC4CB4]`. |
| **Miles** | **`miles_init` `0x11758`** (from `video_init`) | `AIL_startup` `0x72992` → `miles_install_DIG` `0x117B8` → `miles_install_MDI` `0x118A2` (`"CAESAR"`). |
| SFX heap | `sfx_try_alloc` `0x13546` | Optional bank. `FUN_0001359E` is a stub `return 1`. OOM → `Not enough free memory to run Caesar2.` + `exit_`. |
| Zoom + scan LUT | `zoom_set_params` `0x29601`, `video_build_scan_lut` `0x29529` | Zoom 0/1/2 tile metrics; 640×480 / 16 grid. |
| Profile | `load_caesar2_inf` `0x703E0` | `open_("caesar2.inf")`. |
| Prepare video | `video_prepare_smk` `0x59C87` | Palette + fade/clear. Ghidra “noreturn” on `video_blit_dirty` is **false** (that fn returns). |
| **Intro** | **`smk_play` `0x5AB3D`** | Call site `0x10279`: `mov eax, "intro.smk"`. Loop until done / skip. |
| **Music** | **`music_load_xmi` `0x12279`** | Next: `edx=1`, `eax="forum1.xmi"`. |
| **Title** | **`title_screen` `0x5D37F`** | `load_file("backgrnd.256")` + `backgrnd.pl8` (640×480), then `jmp 0x5AFC6` (menu chrome). |
| Title input | `title_input_wait` `0x2E7B1` | Spin until `[0xC459C]==1` (click / key). |
| **Outer loop** | `while ([0xCCAFF7]==0)` | Quit flag. See modes below. |
| Shutdown | `0x59C86` (nop), `0x703A5`, `0x135A3`, `0x1358A`, handle free, `0x283B6` | Then return to `exit_`. |

### `gfx_load_boot_assets` filenames (EAX = path, EDX = dest, EBX = max)

| # | Path VA | Name | Dest | Max |
|---:|---|---|---|---|
| 1 | `0x9037D` | `cityfixt.256` | `0xD331C` | `0x300` |
| 2 | `0x9038A` | `landfill.pl8` | `0xD014C` | `0x1540` |
| 3 | `0x90397` | `font_c2.pl8` | `0xC2080` | `0x24F4` |
| 4 | `0x903A3` | `font3c2.pl8` | `0xA6A2C` | `0x6E58` |
| 5 | `0x903AF` | `mouse.pl8` | `0xC4D56` | `0x21B6` |
| 6 | `0x903B9` | `system.pl8` | `0xAD884` | `0xA2C8` |
| 7 | `0x903C4` | `panels.pl8` | `0xC6F4A` | `0x5B91` |
| 8 | `0x903CF` | `smacker.pl8` | `0xA554C` | `0x14E0` |
| 9 | `0x903DB` | `misc.pl8` | `0xD1A2C` | `0xE00` |
| **10** | **`0x903E4`** | **`c2.eng`** | **`0xB831C`** | **`0x9C40` (40000)** |
| 11 | `0x903EB` | `int_city.pl8` | `0xD168C` | `0x1C8` |
| 12 | `0x903F8` | `provfixt.256` | `0xD301C` | `0x300` |
| 13 | `0x90405` | `int_prov.pl8` | `0xD185C` | `0x1C8` |
| 14 | `0x90412` | `int_batl.pl8` | `0xCFF7C` | `0x1C8` |

`c2.eng` load site is **`0x10FC7`** (mid-function, not its own fn). Fail codes 1…`0xE` match this order.

**Name correction:** `gfx_load_city_assets` @ `0x10DCA` only **frees** those handles (`free_` `0x72207`). Renamed **`gfx_free_city_handles`**. The load is `gfx_load_boot_assets`.

---

## After title — menu vs city

Quit flag: **`[0xCCAFF7]`**. Session-over: **`[0xCCAFF8]`**. View kind: **`[0x117A8D]`**. Submode: **`[0x102AA4]`**.

Outer loop (`c2_main`):

1. If `[0x102AA4]==3` → `FUN_00010529` (career / year step). Else if `[0xCCAFF0]==0` → **`start_city_assignment` `0x1049B`**.
2. If still in “city extras” (`[0xCCAFF0]==0`) → **`map_clear_80x80` `0x3E590`** (zeros an 80×80 plane at `0xD7BFC`).
3. **`enter_view_mode` `0x3351B`** — the real city / province / battle switch:

| `[0x117A8D]` | Meaning (from immediates + callees) |
|---|---|
| **0** | **City.** 80×80 (`0x50`), 480-high view. `gfx_load_zoom_set`, **`city_sfx_bind_wavs` `0x12F2A`** (`gardenb.wav` … `temple1.wav`), `FUN_0005AC1E`. |
| **1** | **Province.** 60-ish metrics (`0x3C`). `province_sfx_bind_wavs` `0x13187`, `province_view_enter_gfx` `0x5AD67`. |
| **2** | **Battle.** `FUN_00010AC9` (not the city zoom set), `FUN_00013351`, `FUN_0005AE68`. |

4. Inner loop: `FUN_0003CF9A` (input/UI; large — not fully read) then **`FUN_00010409`** (if `[0x102AA4]==4`, writes into chunk-14 BSS `0xD94FC` — combat / special).
5. If `[0x102AA4]==1` → **`forum_view` `0x59A15`** (`findings/forum.md`). Mapa das 3 views: **`findings/view_modes.md`**.
6. `music_load_xmi` again if not quitting.

**New city path:** `start_city_assignment` → `city_view_reset` `0x106BB` → **`init_new_city` `0x10565`**.

`init_new_city` indexes **`0x96F2F`** by difficulty `[0x9CE80]` — that is the five starting-money dwords (`20000…5000`) already noted as unaligned in the image. Then `apply_regions_map` **`0x706C3`** (was `load_regions` @ `0x706C6`): `load_file` + a **60×60** (`0x3C`) decode of `[0xC4D10]`.

---

## Names applied this walk (GhidraMCP `rename_function_by_address`)

| Name | VA |
|---|---|
| `c2_main` | `0x10010` |
| `crt_cmain` | `0x7B881` |
| `crt_InitRtns` | `0x7B8D0` |
| `exit_` / `cprintf_` / `malloc_` | `0x720F6` / `0x720B6` / `0x72124` |
| `gfx_load_boot_assets` | `0x10E89` |
| `gfx_free_city_handles` | `0x10DCA` |
| `gfx_zero_handles_a` / `_b` | `0x10CB9` / `0x10D80` |
| `gfx_load_zoom_set` | `0x107DB` |
| `video_init` | `0x28341` |
| `miles_init` / `AIL_startup` | `0x11758` / `0x72992` |
| `miles_install_DIG` / `_MDI` | `0x117B8` / `0x118A2` |
| `mouse_detect` | `0x259F9` |
| `sfx_try_alloc` | `0x13546` |
| `zoom_set_params` | `0x29601` |
| `video_build_scan_lut` | `0x29529` |
| `load_caesar2_inf` | `0x703E0` |
| `video_prepare_smk` | `0x59C87` |
| `smk_play` | `0x5AB3D` |
| `music_load_xmi` | `0x12279` |
| `title_screen` | `0x5D37F` |
| `title_input_wait` | `0x2E7B1` |
| `enter_view_mode` | `0x3351B` |
| `start_city_assignment` | `0x1049B` |
| `init_new_city` | `0x10565` |
| `city_view_reset` | `0x106BB` |
| `city_sfx_bind_wavs` | `0x12F2A` |
| `map_clear_80x80` | `0x3E590` |
| `apply_regions_map` | `0x706C3` |
| `palette_restore` | `0x254C6` |
| `video_blit_dirty` | `0x29849` |

Not renamed: `FUN_00011095` (drive prompt), `FUN_00059A15` (forum / empire), `FUN_00010529`, `FUN_00010AC9` (battle gfx).

**City frame / new city / SavChunks (next walk):** `findings/ghidra_city.md`. Tick is **`view_frame` `0x3CF9A`** (real end `0x3D3E5`; Ghidra bounds are wrong). Money **`city_treasury` `0x102AAC`**. Map at `0xE2FBC` is **80×80×20 AoS**.

---

## What to click next in the GUI

1. **G `3CF9A`** — **`view_frame`**. Listing only through **`0x3D3E5`**. Then **G `459D0`** (`walkers_tick`).
2. **G `65809`** — **`city_map_generate`**. Tile byte 0 / byte 1.
3. **G `56695`** — treasury spend (hottest `0x102AAC` xref).
4. **G `5D37F` / `5AFC6`** — title / File-menu if you still need that tail named.
5. 1-house A/B save to name the other 18 bytes of each city tile. Full C2MODEL.DAT (ints 15+) is still not in the EXE.

Do not start a crack session from the drive-letter strings.
