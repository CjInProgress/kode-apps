"""The rule runner: findings, the context every rule reads, and the registry.

Each rule is one function, registered under its id from RULES.md, that takes
a Context and yields Findings. run() calls them in id order; a rule that
raises becomes a reject of its own, so a bug in a rule never passes an app.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

LEVELS = ("reject", "warn")


@dataclass(frozen=True)
class Finding:
    rule: str
    level: str
    path: str
    line: int
    msg: str

    def format(self) -> str:
        return f"{self.rule} {self.level} {self.path}:{self.line} {self.msg}"


@dataclass
class Context:
    app: Path
    name: str
    catalog: Path
    build: Path | None = None
    sdk: Path | None = None
    releases: list[str] = field(default_factory=list)
    module_releases: dict[str, list[str]] = field(default_factory=dict)
    old_cmake: str | None = None
    kappdata_dir: Path | None = None
    secrets_report: Path | None = None
    ram_checker: Callable[[Path, Path], tuple[bool, str]] | None = None


RULES: dict[str, Callable[[Context], Iterable[Finding]]] = {}


def rule(rule_id: str, level: str) -> Callable:
    """Register fn under rule_id; level is the rule's usual level, for RULES.md."""
    if level not in LEVELS:
        raise ValueError(f"{rule_id}: unknown level {level}")

    def register(fn):
        if rule_id in RULES:
            raise ValueError(f"{rule_id}: registered twice")
        RULES[rule_id] = fn
        return fn
    return register


def order(rule_id: str) -> tuple[str, int]:
    """Sort key: the block letter, then the number as a number."""
    m = re.fullmatch(r"([A-Z])(\d+)", rule_id)
    return (m.group(1), int(m.group(2))) if m else (rule_id, 0)


def load_rules() -> None:
    """Import every rule module once, which registers its rules."""
    from kcheck import rules_a, rules_b, rules_c, rules_d, rules_e  # noqa: F401


def run(ctx: Context, only: set[str] | None = None) -> list[Finding]:
    load_rules()
    found: list[Finding] = []
    for rule_id in sorted(RULES, key=order):
        if only is not None and rule_id not in only:
            continue
        try:
            found.extend(RULES[rule_id](ctx))
        except Exception as exc:  # a broken rule must fail the app, never pass it
            found.append(Finding(rule_id, "reject", ".", 0, f"{rule_id} crashed: {exc!r}"))
    return found


def exit_code(findings: list[Finding]) -> int:
    return 1 if any(f.level == "reject" for f in findings) else 0
