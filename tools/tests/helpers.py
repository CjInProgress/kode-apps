"""Test helpers: a fresh copy of the fixture app, a Context around it, and PNGs.

    make_app(tmp, {"main/x.c": "...", "LICENSE": None})   copy, then write or delete
    make_ctx(app, releases=[...])                          a Context for the rules
    write_png(path, w, h)                                  a valid PNG, standard library only
"""
import os
import shutil
import struct
import sys
import zlib
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))

from kcheck.core import Context  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
KODEOS_TOOLS = Path(os.environ.get("KODEOS_TOOLS", TOOLS.parents[1] / "KodeOs" / "tools"))


def write_png(path, w, h):
    """Write a w x h grey PNG at path."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"".join(b"\x00" + b"\x80" * w for _ in range(h))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def make_app(tmp, edits=None, name="good_app"):
    """Copy the fixture app to tmp/<name> and apply edits: a path to new text, or to None to delete it."""
    app = Path(tmp) / name
    shutil.copytree(FIXTURES / "good_app", app)
    for rel, text in (edits or {}).items():
        p = app / rel
        if text is None:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(text, bytes):
                p.write_bytes(text)
            else:
                p.write_text(text)
    return app


def make_ctx(app, **over):
    """A Context that every rule can run on, with the fixture SDK and a passing RAM check."""
    args = dict(app=Path(app), name=Path(app).name, catalog=FIXTURES / "catalog",
                build=FIXTURES / "good_build", sdk=FIXTURES / "sdk",
                releases=["v00.00.27", "v00.00.26", "v00.00.25"], kappdata_dir=KODEOS_TOOLS,
                secrets_report=FIXTURES / "good_build" / "gitleaks.json",
                ram_checker=lambda elf, budget: (True, "ok"))
    args.update(over)
    return Context(**args)


def ids(findings, level=None):
    """The rule ids of findings, optionally of one level only."""
    return [f.rule for f in findings if level is None or f.level == level]
