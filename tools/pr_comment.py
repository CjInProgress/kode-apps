#!/usr/bin/env python3
"""The body of the one pull request comment the workflow keeps up to date.

    pr_comment.py FINDINGS_DIR [--results tests=success,find=success,check=skipped] > comment.md

FINDINGS_DIR holds catalog.txt (the `check_app.py catalog` output) and, per
app, <name>.txt (the `check_app.py check --output` file) and <name>.meta
(`version=`, `artifact=`, `status=built|failed|removed`, one per line).
The first line of the body is the marker the workflow finds the comment by.
A job that did not succeed, and an app that changed but never reported, are
said in the body, so the comment never reads as a pass the CI did not give.
"""
from __future__ import annotations

import sys
from pathlib import Path

MARKER = "<!-- kode-apps-check -->"


def _meta(path):
    out = {}
    for line in path.read_text().splitlines():
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def _findings(path):
    """(rule, level, where, message) of each finding line; summary and change lines are skipped."""
    got = []
    if not path.is_file():
        return got
    for line in path.read_text().splitlines():
        parts = line.split(" ", 3)
        if len(parts) >= 3 and parts[1] in ("reject", "warn"):
            got.append((parts[0], parts[1], parts[2], parts[3] if len(parts) > 3 else ""))
    return got


def _item(f):
    return f"- `{f[0]}` {f[2]} {f[3]}".rstrip()


def _section(name, meta, findings):
    lines = [f"### {name} {meta.get('version', '')}".rstrip()]
    if meta.get("status") == "failed":
        lines.append("**The build failed**: the findings below come from the sources alone.")
    rejects = [f for f in findings if f[1] == "reject"]
    warns = [f for f in findings if f[1] == "warn"]
    lines.append(f"**{len(rejects)} reject, {len(warns)} warn**")
    lines.extend(_item(f) for f in rejects)
    if warns:
        lines += ["", f"<details><summary>{len(warns)} warnings for the reviewer</summary>", ""]
        lines.extend(_item(f) for f in warns)
        lines += ["", "</details>"]
    if meta.get("artifact"):
        lines += ["", f"The .bin and appdata/ to install: {meta['artifact']}"]
    return lines


def _changes(path):
    """The app names of the `change` lines of catalog.txt."""
    if not path.is_file():
        return []
    return [line.split()[1] for line in path.read_text().splitlines()
            if line.startswith("change ") and len(line.split()) >= 2]


def render(findings_dir: Path, results: dict[str, str] | None = None) -> str:
    out = [MARKER, "## Catalog check", ""]
    failed = [f"{job} ended {r}" for job, r in sorted((results or {}).items()) if r not in ("success", "skipped")]
    if failed:
        out += [f"**Not every job finished**: {', '.join(failed)}. Read the run's log.", ""]
    catalog = _findings(findings_dir / "catalog.txt")
    if catalog:
        out += ["### The catalog"] + [_item(f) for f in catalog] + [""]
    apps = sorted(p.stem for p in findings_dir.glob("*.meta"))
    for name in _changes(findings_dir / "catalog.txt"):
        if name not in apps:
            out += [f"{name} was not checked: its job did not report.", ""]
    for name in apps:
        meta = _meta(findings_dir / f"{name}.meta")
        if meta.get("status") == "removed":
            out += [f"{name} leaves the catalog.", ""]
            continue
        out += _section(name, meta, _findings(findings_dir / f"{name}.txt")) + [""]
    if not apps and not catalog and not failed and not _changes(findings_dir / "catalog.txt"):
        out.append("No app changes in this pull request; the catalog's own files pass.")
    return "\n".join(out).rstrip() + "\n"


def _parse_results(text):
    return dict(item.split("=", 1) for item in text.split(",") if "=" in item)


if __name__ == "__main__":
    results = None
    if len(sys.argv) > 3 and sys.argv[2] == "--results":
        results = _parse_results(sys.argv[3])
    sys.stdout.write(render(Path(sys.argv[1]), results))
