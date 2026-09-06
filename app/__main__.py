"""Launch the v0 skeleton from the repo root: python -m app"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from app.boot import run_boot
from app.config import InstallError, resolve_game_dir
from app.sim import on_sim_step  # Space / T — phase slot then walkers


def _print_status(ctx) -> None:
    print(f"install       : {ctx.game}")
    print(f"resolved via  : {ctx.source}")
    print("-- key files --")
    for item in ctx.key_files:
        mark = "ok" if item.ok else "MISSING"
        extra = f"  {item.size} B" if item.ok else ""
        print(f"  [{mark:7}] {item.name}{extra}")
    print("-- boot assets (gfx_load_boot_assets 0x10E89) --")
    for item in ctx.boot_files:
        mark = "ok" if item.ok else "MISSING"
        print(f"  [{mark:7}] {item.name}")
    print("-- boot notes --")
    for note in ctx.notes:
        print(f"  {note}")
    print(
        "sim           : Space/T -> "
        f"{on_sim_step.__module__}.on_sim_step "
        "(one slot then walkers_tick; M = month; play/faster auto-clock; E = evolve80)"
    )
    sim = getattr(ctx, "sim", None)
    if sim is not None:
        print(
            f"city_sim      : phase={sim.phase:#x} row={sim.row} "
            f"{sim.date_label}  src={sim.source}"
        )
        if getattr(sim, "city_only", 0):
            from app.new_game import river_tile_count, skill_name

            print(
                f"new game      : City Only  skill={sim.skill} {skill_name(sim.skill)}  "
                f"treasury={sim.treasury}  pid={sim.pid}  "
                f"river={river_tile_count(ctx.city)}"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Caesar II v0 — load original files, show one PL8. "
            "--new --city-only starts a fresh city (grass+river). "
            "Space/T = one city_sim_phase slot then walkers_tick. "
            "M = skip stubs + one calendar_advance (month++). "
            "Unpaused play/faster auto-advances months (sim_tick_due). "
            "E = host evolve-all-rows. See findings/city_only.md."
        )
    )
    parser.add_argument(
        "--game",
        type=Path,
        default=None,
        help="Caesar II install folder (overrides CAESAR2_PATH and config.local.json)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify files + decode, then exit (no window)",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="skip the optional 2s RAW preview",
    )
    parser.add_argument(
        "--no-window",
        action="store_true",
        help="same as --check (kept for scripts)",
    )
    parser.add_argument(
        "--sav",
        type=Path,
        default=None,
        help="load this .SAV as SavChunk 13 (default: FELIPE01 / first in install)",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Start a New Game (requires --city-only; Career is not this milestone)",
    )
    parser.add_argument(
        "--city-only",
        action="store_true",
        help="New Game Options: NO -- City-only Mode (chunk 406=1, pid 0)",
    )
    parser.add_argument(
        "--skill",
        type=int,
        default=None,
        metavar="N",
        help="Choose a Skill Level 0..4 (Novice…Impossible!). Default 2 Normal",
    )
    parser.add_argument(
        "--map-preview",
        type=Path,
        nargs="?",
        const=Path("sav_preview/city_iso.png"),
        help="write isometric city PNG (gitignored) and exit",
    )
    parser.add_argument(
        "--sim-smoke",
        action="store_true",
        help="run housing evolve selftest + one SAV evolve80 (no window)",
    )
    args = parser.parse_args(argv)

    if args.city_only and not args.new:
        parser.error("--city-only requires --new")
    if args.new and not args.city_only:
        parser.error("--new requires --city-only (Career / --region is not this milestone)")
    if args.new and args.sav is not None:
        parser.error("--new and --sav are mutually exclusive")
    if args.skill is not None and not args.new:
        parser.error("--skill requires --new --city-only")
    skill = 2 if args.skill is None else args.skill
    if args.new and not 0 <= skill <= 4:
        parser.error("--skill must be 0..4 (Novice Easy Normal Hard Impossible!)")

    try:
        game, source = resolve_game_dir(args.game)
    except InstallError as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        return 2

    if not game.is_dir():
        print(f"FAILED        : not a directory: {game}", file=sys.stderr)
        return 2

    sav = args.sav
    if args.new:
        sav = None
    if sav is None and args.sim_smoke and not args.new:
        from app.city_map import pick_save

        for name in (
            "20230610.SAV",
            "FELIPE02.SAV",
            "LASTYEAR.SAV",
            "FELIPE01.SAV",
            "ACHEA23.SAV",
        ):
            cand = game / name
            if cand.is_file():
                sav = cand
                break
            for nested in (
                game / name.split(".")[0] / name,
                game / "Achea.sav" / name,
            ):
                if nested.is_file():
                    sav = nested
                    break
            if sav is not None:
                break
        if sav is None:
            sav = pick_save(game)
    if sav is not None and not sav.is_file():
        alt = game / sav.name
        if alt.is_file():
            sav = alt

    ctx = run_boot(
        game,
        source,
        play_audio=not args.no_audio and not args.sim_smoke,
        sav=sav,
        city_only=args.new,
        skill=skill,
    )
    _print_status(ctx)

    if args.map_preview is not None:
        from app import assets, city_map

        dest = args.map_preview
        dest.parent.mkdir(parents=True, exist_ok=True)
        sheets = assets.load_city_map_sheets(game)
        if "CITYFIXT" not in sheets:
            print("FAILED        : CITYFIXT decode missing", file=sys.stderr)
        print(
            "map sheets    : "
            + ", ".join(f"{k}={len(v)}" for k, v in sheets.items())
        )
        native = city_map.render_iso(
            ctx.city, sheets.get("CITYFIXT"), sheets=sheets or None
        )
        n_walkers = 0
        if ctx.walkers:
            from app.walkers import drawable_walkers, overlay_walkers

            try:
                n_walkers = len(drawable_walkers(ctx.walkers))
                native = overlay_walkers(native, ctx.walkers, game)
            except (OSError, ValueError) as exc:
                print(f"walkers skip  : {exc}", file=sys.stderr)
                n_walkers = 0
        thumb = native.copy()
        thumb.thumbnail((960, 720), Image.Resampling.BILINEAR)
        thumb.save(dest)
        print(f"map preview   : {dest.resolve()}  ({thumb.size[0]}x{thumb.size[1]})")
        print(f"map source    : {ctx.city.source}")
        print(f"walkers       : {n_walkers} drawn  (SavChunk 8)")
        return 0 if ctx.city.source != "empty" else 1

    if args.sim_smoke and args.new:
        from app.city_map import selftest as water_selftest
        from app.new_game import selftest as new_city_selftest

        print("-- water LUT selftest --")
        failed = 0
        for line in water_selftest():
            print(f"  {line}")
            if "FAIL" in line:
                failed += 1
        if failed:
            print("FAILED        : water LUT selftest")
            return 1
        print("-- new city-only selftest --")
        for line in new_city_selftest():
            print(f"  {line}")
            if "FAIL" in line:
                failed += 1
        from app.place import selftest as place_selftest

        print("-- place selftest --")
        for line in place_selftest():
            print(f"  {line}")
            if "FAIL" in line:
                failed += 1
        if failed:
            print("FAILED        : city_map_generate selftest")
            return 1
        print("ok            : city-only generate smoke passed")
        return 0

    if args.sim_smoke:
        from app.city_sim import evolve_all_rows, housing_id_counts, selftest

        print("-- city_sim selftest --")
        failed = 0
        for line in selftest():
            print(f"  {line}")
            if "FAIL" in line:
                failed += 1
        before = housing_id_counts(ctx.city.tiles)
        up, down, merge = evolve_all_rows(ctx.city.tiles, decay=False)
        after = housing_id_counts(ctx.city.tiles)
        print(
            f"-- evolve80 on {ctx.city.source} --  "
            f"houses +{up}/-{down} merge={merge}  phase={ctx.sim.phase:#x}  "
            f"{ctx.sim.date_label}"
        )
        changed = sorted(set(before) | set(after))
        for hid in changed:
            b, a = before.get(hid, 0), after.get(hid, 0)
            if b != a:
                print(f"  id {hid:#x}: {b} -> {a}")
        if not changed or (up + down) == 0:
            print(
                "  no house-id change - Achea/FELIPE01 often have +15 wiped "
                "(use 20230610.SAV / FELIPE02.SAV)"
            )
        if failed:
            print("FAILED        : city_sim selftest")
            return 1
        print("ok            : city_sim smoke passed")
        return 0

    if args.check or args.no_window:
        from app.city_map import selftest as water_selftest

        print("-- water LUT selftest --")
        water_fail = 0
        for line in water_selftest():
            print(f"  {line}")
            if "FAIL" in line:
                water_fail += 1
        if water_fail:
            print("FAILED        : water LUT selftest")
            return 1
        from app.place import selftest as place_selftest

        print("-- place selftest --")
        place_fail = 0
        for line in place_selftest():
            print(f"  {line}")
            if "FAIL" in line:
                place_fail += 1
        if place_fail:
            print("FAILED        : place selftest")
            return 1
        from app.city_overlay import selftest as overlay_selftest

        print("-- overlay selftest --")
        overlay_fail = 0
        for line in overlay_selftest():
            print(f"  {line}")
            if "FAIL" in line:
                overlay_fail += 1
        if overlay_fail:
            print("FAILED        : overlay selftest")
            return 1
        if args.new:
            from app.new_game import river_tile_count

            n_river = river_tile_count(ctx.city)
            if ctx.city.source == "empty" or n_river < 1:
                print("FAILED        : city_map_generate produced no river")
                return 1
            if ctx.sim.treasury <= 0 or ctx.sim.city_only != 1:
                print("FAILED        : City Only treasury / chunk 406")
                return 1
        if not ctx.key_ok or ctx.image is None or ctx.eng is None:
            print("FAILED        : key file, C2.ENG, or PL8 decode missing")
            return 1
        print("ok            : v0 check passed")
        return 0

    from app.window import show

    show(ctx, game=game)
    return 0


if __name__ == "__main__":
    sys.exit(main())
