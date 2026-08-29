"""Resolve the user's Caesar II install. Never copy game files into git."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
REPO_ROOT = APP_DIR.parent
LOCAL_CONFIG_NAME = "config.local.json"
ENV_VAR = "CAESAR2_PATH"

# Last-resort fallback used by tools/decode_*.py on this machine only.
# Prefer env or config.local.json so another checkout does not assume this path.
_TOOLS_DEFAULT = Path(r"C:\Users\Felip\OneDrive\Games\Caesar2")


class InstallError(FileNotFoundError):
    """Raised when the Caesar II directory cannot be resolved."""


def local_config_path() -> Path:
    return APP_DIR / LOCAL_CONFIG_NAME


def _read_local_config() -> Path | None:
    path = local_config_path()
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = data.get("caesar2_path") or data.get("path")
    if not raw:
        return None
    return Path(str(raw)).expanduser()


def resolve_game_dir(cli_path: Path | None = None) -> tuple[Path, str]:
    """Return (directory, how it was chosen).

    Order: --game, CAESAR2_PATH, app/config.local.json, tools default if present.
    """
    if cli_path is not None:
        return cli_path.expanduser().resolve(), "--game"

    env = os.environ.get(ENV_VAR, "").strip()
    if env:
        return Path(env).expanduser().resolve(), ENV_VAR

    local = _read_local_config()
    if local is not None:
        return local.resolve(), LOCAL_CONFIG_NAME

    if _TOOLS_DEFAULT.is_dir():
        return _TOOLS_DEFAULT.resolve(), "tools-default"

    raise InstallError(
        f"Caesar II folder not found. Set {ENV_VAR}, pass --game, or copy "
        f"app/config.example.json to {LOCAL_CONFIG_NAME} and edit caesar2_path."
    )


def find_file(game: Path, name: str) -> Path | None:
    """Case-insensitive lookup of a file in the install root (flat 1.1A tree)."""
    direct = game / name
    if direct.is_file():
        return direct
    want = name.upper()
    try:
        for child in game.iterdir():
            if child.is_file() and child.name.upper() == want:
                return child
    except OSError:
        return None
    return None
