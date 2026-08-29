"""Load original install files. Decoders live in tools/ — do not fork the format."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.config import find_file

# tools/decode_pl8.py etc. are scripts, not a package.
_TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import decode_pl8  # noqa: E402
import extract_eng  # noqa: E402

# User-requested verify list (plus title art used by the window).
KEY_FILES = ("PS.EXE", "CITYFIXT.PL8", "C2.ENG", "INTRO.SMK")

# gfx_load_boot_assets @ 0x10E89 — 14× load_file (findings/ghidra_walk.md)
BOOT_ASSETS: tuple[tuple[int, str], ...] = (
    (1, "cityfixt.256"),
    (2, "landfill.pl8"),
    (3, "font_c2.pl8"),
    (4, "font3c2.pl8"),
    (5, "mouse.pl8"),
    (6, "system.pl8"),
    (7, "panels.pl8"),
    (8, "smacker.pl8"),
    (9, "misc.pl8"),
    (10, "c2.eng"),  # dest 0xB831C, max 0x9C40; site 0x10FC7
    (11, "int_city.pl8"),
    (12, "provfixt.256"),
    (13, "int_prov.pl8"),
    (14, "int_batl.pl8"),
)

TITLE_PL8 = "backgrnd.pl8"  # title_screen @ 0x5D37F
TITLE_PAL = "backgrnd.256"
SHEET_CAP = 64


@dataclass(frozen=True)
class FileStatus:
    name: str
    path: Path | None
    ok: bool
    size: int = 0


@dataclass
class EngTable:
    path: Path
    strings: list[str]
    offsets: list[int]
    unique: int

    def find(self, needle: str) -> tuple[int, str] | None:
        low = needle.lower()
        for i, s in enumerate(self.strings):
            if low in s.lower():
                return i, s
        return None


def verify_named(game: Path, names: tuple[str, ...]) -> list[FileStatus]:
    out: list[FileStatus] = []
    for name in names:
        path = find_file(game, name)
        out.append(
            FileStatus(
                name=name,
                path=path,
                ok=path is not None,
                size=path.stat().st_size if path is not None else 0,
            )
        )
    return out


def verify_key_files(game: Path) -> list[FileStatus]:
    return verify_named(game, KEY_FILES)


def verify_boot_assets(game: Path) -> list[FileStatus]:
    return verify_named(game, tuple(name for _, name in BOOT_ASSETS))


def read_resource_cfg(game: Path) -> str | None:
    """load_file_cfg @ 0x2456E — HD/CD origin letter. Value is still opaque."""
    path = find_file(game, "resource.cfg")
    if path is None:
        return None
    raw = path.read_bytes()
    text = raw.decode("latin-1", errors="replace").strip()
    return text[:80] if text else None


def load_eng(game: Path) -> EngTable:
    path = find_file(game, "C2.ENG")
    if path is None:
        raise FileNotFoundError("C2.ENG not found in the install folder")
    offsets, strings, _pad, unique = extract_eng.parse_textfile(path.read_bytes())
    return EngTable(path=path, strings=strings, offsets=offsets, unique=unique)


def load_pl8_image(
    game: Path,
    pl8_name: str,
    *,
    first_only: bool = False,
    sheet_cap: int = SHEET_CAP,
) -> tuple[Image.Image, Path, int]:
    """Decode one PL8 via tools/decode_pl8.py. Returns (image, path, n_sprites)."""
    pl8 = find_file(game, pl8_name)
    if pl8 is None:
        raise FileNotFoundError(f"{pl8_name} not found in {game}")
    pal_path, _why = decode_pl8.resolve_palette(pl8, game)
    palette = decode_pl8.load_palette(pal_path, verbose=False)
    flags, _unk, sprites, blob = decode_pl8.parse_pl8(pl8, verbose=False)
    if first_only or len(sprites) == 1:
        img = decode_pl8.decode_sprite(
            blob, sprites[0], flags, len(blob), sprites, palette, verbose=False
        )
        return img, pl8, len(sprites)
    frames = [
        decode_pl8.decode_sprite(
            blob, spr, flags, len(blob), sprites, palette, verbose=False
        )
        for spr in sprites[:sheet_cap]
    ]
    return decode_pl8.make_sheet(frames), pl8, len(sprites)


def pick_boot_image(game: Path) -> tuple[Image.Image, str, int]:
    """Title backgrnd.pl8 if present, else CITYFIXT first tile (iso)."""
    if find_file(game, TITLE_PL8) is not None:
        img, path, n = load_pl8_image(game, TITLE_PL8, first_only=True)
        return img, path.name, n
    img, path, n = load_pl8_image(game, "CITYFIXT.PL8", first_only=True)
    return img, path.name, n
