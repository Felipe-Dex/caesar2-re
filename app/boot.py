"""c2_main @ 0x10010 — boot order as stubs; real loads where they are cheap.

CRT start is 0x72500 (Watcom), not main. Walk: findings/ghidra_walk.md.
This module does not run a city sim (view_frame 0x3CF9A stays in Ghidra).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from app import assets, audio, city_map
from app.assets import EngTable, FileStatus
from app.city_map import CityMap
from app.city_sim import SimState, load_sim_from_sav
from app.walkers import Walker, live_walkers, load_walkers_from_sav

# Named VAs (Ghidra, mapped image base 0x10000).
VA_C2_MAIN = 0x10010
VA_LOAD_FILE_CFG = 0x2456E
VA_GFX_LOAD_BOOT = 0x10E89
VA_VIDEO_INIT = 0x28341
VA_MILES_INIT = 0x11758
VA_SMK_PLAY = 0x5AB3D
VA_TITLE_SCREEN = 0x5D37F
VA_TITLE_INPUT = 0x2E7B1
VA_VIEW_FRAME = 0x3CF9A


@dataclass
class BootContext:
    game: Path
    source: str
    resource_cfg: str | None
    key_files: list[FileStatus]
    boot_files: list[FileStatus]
    eng: EngTable | None
    image: Image.Image | None
    image_name: str
    n_sprites: int
    city: CityMap
    walkers: list[Walker]
    sim: SimState
    audio_status: str
    notes: list[str] = field(default_factory=list)
    start_in_map: bool = False
    play_audio: bool = True

    @property
    def key_ok(self) -> bool:
        return all(f.ok for f in self.key_files)


def run_boot(
    game: Path,
    source: str,
    *,
    play_audio: bool = True,
    sav: Path | None = None,
    city_only: bool = False,
    skill: int = 2,
) -> BootContext:
    notes: list[str] = []

    # 1. resource.cfg — load_file_cfg @ 0x2456E
    cfg = assets.read_resource_cfg(game)
    if cfg is None:
        notes.append("resource.cfg missing (HD/CD letter unknown)")
    else:
        notes.append(f"resource.cfg = {cfg!r}")

    # 2. gfx_load_boot_assets @ 0x10E89 — verify names; decode later
    key = assets.verify_key_files(game)
    boot = assets.verify_boot_assets(game)
    missing_boot = [f.name for f in boot if not f.ok]
    if missing_boot:
        notes.append(f"boot assets missing: {', '.join(missing_boot)}")
    else:
        notes.append("gfx_load_boot_assets: 14/14 names present on disk")

    # 2b. c2.eng — real parse via tools/extract_eng.py
    eng: EngTable | None = None
    try:
        eng = assets.load_eng(game)
        notes.append(f"C2.ENG: {len(eng.strings)} strings ({eng.unique} unique)")
    except (OSError, ValueError) as exc:
        notes.append(f"C2.ENG failed: {exc}")

    # 3. video_init @ 0x28341 — 640×480 window is opened by window.py
    notes.append("video_init stub: host window 640x480 (not VESA)")

    # 4. miles_init @ 0x11758 — not AIL
    audio_status = "audio skipped (--no-audio)"
    if play_audio and city_only:
        # City Only opens on the map with Hail. A01.RAW is a boot probe,
        # not the briefing — playing it here sounds like a promotion sting.
        audio_status = "city SFX on (no boot RAW / A01 sting)"
    elif play_audio:
        audio_status = audio.play_raw_preview(game)
    notes.append(audio_status)

    # 5. smk_play @ 0x5AB3D intro.smk — codec not in-process (ffmpeg remux only)
    intro = next((f for f in key if f.name.upper() == "INTRO.SMK"), None)
    if intro and intro.ok:
        notes.append(f"intro.smk present ({intro.size} B) - playback stub")
    else:
        notes.append("intro.smk missing — skip smk_play")

    # 6. title_screen @ 0x5D37F — real PL8 decode
    image: Image.Image | None = None
    image_name = "(none)"
    n_sprites = 0
    try:
        image, image_name, n_sprites = assets.pick_boot_image(game)
        notes.append(
            f"title art: {image_name} ({image.size[0]}x{image.size[1]}, {n_sprites} sprites)"
        )
    except (OSError, ValueError) as exc:
        notes.append(f"PL8 decode failed: {exc}")

    # 7. city — New Game (City Only) or SavChunk 13 from a .SAV
    city = CityMap()
    walkers: list[Walker] = []
    sim = SimState()
    start_in_map = False
    if city_only:
        from app.new_game import start_city_assignment

        fresh = start_city_assignment(skill=skill, game=game)
        city = fresh.city
        walkers = fresh.walkers
        sim = fresh.sim
        notes.extend(fresh.notes)
        start_in_map = True
    else:
        sav_path = sav if sav is not None else city_map.pick_save(game)
        if sav_path is None:
            notes.append(
                f"city_map: no .SAV — {city.width}x{city.height}x{city_map.TILE_BYTES} "
                f"zeros @ SavChunk {city_map.SAV_CHUNK} (VA {city_map.GHIDRA_BSS:#x})"
            )
        else:
            try:
                sizes = city_map.load_chunk_sizes(game)
                city = city_map.load_city_from_sav(sav_path, sizes, game=game)
                notes.append(
                    f"city_map: {sav_path.name} chunk {city_map.SAV_CHUNK} "
                    f"{city.width}x{city.height}x{city_map.TILE_BYTES} "
                    f"({len(city.id_counts())} tile ids) "
                    f"via {len(sizes)} sequential sizes"
                )
                try:
                    walkers = load_walkers_from_sav(sav_path, sizes, game=game)
                    notes.append(
                        f"walkers: {sav_path.name} chunk 8 "
                        f"{len(live_walkers(walkers))} live / {len(walkers)}"
                    )
                except (OSError, ValueError) as exc:
                    notes.append(f"walkers load failed: {exc}")
                try:
                    sim = load_sim_from_sav(sav_path, sizes, game=game)
                    from app.forum import apply_saved_plebs
                    from app.messages import seed_watch_from_city

                    apply_saved_plebs(sim, city.tiles)
                    seed_watch_from_city(sim, city.tiles)
                    notes.append(
                        f"city_sim: {sav_path.name} phase={sim.phase:#x} "
                        f"({sim.date_label}) - Space = one slot then walkers"
                    )
                except (OSError, ValueError) as exc:
                    notes.append(f"city_sim load failed: {exc}")
            except (OSError, ValueError) as exc:
                notes.append(f"city_map load failed: {exc}")

    return BootContext(
        game=game,
        source=source,
        resource_cfg=cfg,
        key_files=key,
        boot_files=boot,
        eng=eng,
        image=image,
        image_name=image_name,
        n_sprites=n_sprites,
        city=city,
        walkers=walkers,
        sim=sim,
        audio_status=audio_status,
        notes=notes,
        start_in_map=start_in_map,
        play_audio=play_audio,
    )
