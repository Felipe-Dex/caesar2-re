"""Launch the v0 skeleton from the repo root: python -m app"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
    args = parser.parse_args(argv)

    try:
        game, source = resolve_game_dir(args.game)
    except InstallError as exc:
        print(f"FAILED        : {exc}", file=sys.stderr)
        return 2

    if not game.is_dir():
        print(f"FAILED        : not a directory: {game}", file=sys.stderr)
        return 2

    ctx = run_boot(game, source, play_audio=not args.no_audio)
    _print_status(ctx)

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
