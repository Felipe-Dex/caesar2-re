"""Placeholder city map — 80×80 tiles × 20 bytes (AoS). No sim.

Ghidra (see findings/ghidra_city.md):

    BSS              0xE2FBC   historically city_planes_20x80x80
    SavChunk         13        128000 bytes
    tile step        0x14      = 20
    row step         0x640     = 1600 = 80×20

Engine writes (later, not here):

    city_map_zero_lanes     0x6E140
    city_map_generate       0x65809   rand terrain + river-like trace
    city_map_fill_rand      0x65AFA   byte 0 = (rng & 0xF) + 8
    city_map_trace_feature  0x658D1   OR 0x10 into byte 1
    city_map_draw           0x360F7   (from view_frame 0x3CF9A)

Do not invent houses, walkers, or economy. Byte meanings come from a
1-house SAV pair (file_off = 50395 + tile*20 + byte), not from this stub.
"""

from __future__ import annotations

from dataclasses import dataclass, field

MAP_W = 80
MAP_H = 80
TILE_BYTES = 20
MAP_BYTES = MAP_W * MAP_H * TILE_BYTES  # 128000
TILE_STRIDE = 0x14
ROW_STRIDE = 0x640
GHIDRA_BSS = 0xE2FBC
SAV_CHUNK = 13


@dataclass
class CityMap:
    """Empty 80×80×20 blob. Same size as SavChunk 13; contents are zeros."""

    width: int = MAP_W
    height: int = MAP_H
    tiles: bytearray = field(default_factory=lambda: bytearray(MAP_BYTES))

    def offset(self, x: int, y: int) -> int:
        return y * ROW_STRIDE + x * TILE_STRIDE

    def tile(self, x: int, y: int) -> memoryview:
        off = self.offset(x, y)
        return memoryview(self.tiles)[off : off + TILE_BYTES]

    def clear(self) -> None:
        """Stand-in for city_map_zero_lanes — wipe only, no generate."""
        self.tiles[:] = b"\x00" * MAP_BYTES
