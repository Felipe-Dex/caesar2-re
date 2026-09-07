# City Only `sav_write` (host)

EXE: `sav_write` `0x70174` (EAX=path) walks **500** `{ptr,size}` at VA `0x9ABC0`, then appends **4000** B from `history.dat`. Fixed size **225745**. Inverse: `sav_read` `0x7024A` (no checksum).

The host does **not** keep those 500 BSS cells. File → Save / **F5** writes the same container: every chunk we own from live state, the rest **zero** (D.SAV slot sizes, empty payload). Trailer is `SimState.history` or 4000 zeros (`history_dat_reset`). `.SAV` is gitignored. Do not copy retail files into the repo.

## Owned (live)

| Chunk | Size | Source |
|---:|---:|---|
| 0–3 | 1 | named `00 04 00 00` (`lastyear.sav` → `00 00 01 01`) |
| **8** | 11658 | walkers 201×58 |
| **13** | 128000 | city 80×80×20 |
| **16** | 1 | skill 0…4 |
| 22–24 / 27 / 405 | 4 | wrap / row / phase / week_gate |
| **25 / 26** | 4 | year (signed BC) / month |
| **28** | 4 | treasury |
| **29 / 30** | 4 | pop tax / industrial tax |
| 31–37 / 46 | 4 | pop, employment, last-year money, rating avg |
| **52 / 54 / 55 / 56** | 4 / 4 / 4 / 64 | labor ready / welfare / estimate / sliders |
| 140 / 157 / 223 / 276 | 4 | factory labor / tribute / pid / province links |
| 286–289 / 291 | 4 | ratings + City Only rank 0 |
| 325 / 338 / 341 | 4 | year seed / HISTORY count / ratings seed |
| **339** | 768 | goods table |
| **406** | 1 | City Only flag **1** |
| 416 | 4 | labor index |
| trailer | 4000 | history.dat |

## Risk — can 1.1A load it?

**Structurally yes.** `sav_read` only copies 500 sized slots + 4000 B. A 225745-byte file with this table is a valid container (same as D.SAV).

**Not a verified retail session.** Chunks the host never allocated (7 actors26, 9–12, 14 province 60×60×8, climate, most mid-table globals, 432–499 pad copies of `0x117D70`) are **zero**, not `init_new_city` BSS. City Only skips `actors26_tick` and province play, so empty 7/14 may be survivable. Other zeros can break advisors, goods, or crash if the EXE walks a table it expected the new-city init to fill.

Treat host saves as a **complete dump of chunks we own**, loadable by this host and *maybe* by 1.1A. Do not ship them as certified original saves.
