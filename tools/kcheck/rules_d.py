"""Rules of block D of RULES.md: the interface.

D1, D2, D4 and D7 are judged by the reviewer; D3, D5, D6 and D10 wait for
the style to be closed. Only the two mechanical ones live here.
"""
from __future__ import annotations

import struct

from kcheck import source
from kcheck.core import Finding, rule

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
GLASS_W = 410
GLASS_H = 502
SHOTS_MIN = 1
SHOTS_MAX = 4
SHOTS_DIR = "appdata/screenshots"


@rule("D8", "reject")
def d8_home_hold(ctx):
    if source.settings(ctx.app).get("CONFIG_KODEOS_HOME_HOLD") == "n":
        yield Finding("D8", "reject", "sdkconfig.defaults", 0,
                      "CONFIG_KODEOS_HOME_HOLD=n takes away the one way back to kodeOS")


def _png_size(path):
    head = path.read_bytes()[:24]
    if len(head) < 24 or not head.startswith(PNG_SIGNATURE):
        return None
    return struct.unpack(">II", head[16:24])


@rule("D9", "reject")
def d9_screenshots(ctx):
    folder = ctx.app / SHOTS_DIR
    shots = sorted(p for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []
    if not SHOTS_MIN <= len(shots) <= SHOTS_MAX:
        yield Finding("D9", "reject", SHOTS_DIR, 0, f"{len(shots)} screenshots, {SHOTS_MIN} to {SHOTS_MAX} wanted")
    for p in shots:
        size = _png_size(p)
        where = source.rel(ctx.app, p)
        if size is None:
            yield Finding("D9", "reject", where, 0, "not a PNG")
        elif size != (GLASS_W, GLASS_H):
            yield Finding("D9", "reject", where, 0, f"{size[0]} x {size[1]}, the glass is {GLASS_W} x {GLASS_H}")
