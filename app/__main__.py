"""Launch the v0 skeleton from the repo root: python -m app"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from app.boot import run_boot
from app.config import InstallError, resolve_game_dir


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Caesar II v0 — load original files, show one PL8. Not a sim."
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
        "--map-preview",
        type=Path,
        nargs="?",
        const=Path("sav_preview/city_iso.png"),
        help="write isometric city PNG (gitignored) and exit",
    )
    args = parser.parse_args(argv)

    try:
        game, source = resolve_game_dir(args.game)
    except InstallError as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        return 2

    if not game.is_dir():
        print(f"FAILED        : not a directory: {game}", file=sys.stderr)
        return 2

    sav = args.sav
    if sav is not None and not sav.is_file():
        alt = game / sav.name
        if alt.is_file():
            sav = alt

    ctx = run_boot(game, source, play_audio=not args.no_audio, sav=sav)
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

    if args.check or args.no_window:
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
