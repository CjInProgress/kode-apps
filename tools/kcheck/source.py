"""What the rules read from an app: its sources, its settings and its build files.

Nothing here judges. Every helper keeps line numbers intact, so a finding can
point at the line the author has to change.
"""
from __future__ import annotations

import re
from pathlib import Path

SOURCE_EXT = (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".hh", ".hxx")
SKIP_DIRS = ("build", "managed_components", ".git")
MANIFEST_RE = re.compile(r'KODE_APP_MANIFEST\(\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\)')


def sources(app: Path) -> list[Path]:
    """Every C and C++ source of the app, outside the generated folders, in path order."""
    out = []
    for p in app.rglob("*"):
        rel = p.relative_to(app)
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        if p.is_file() and p.suffix in SOURCE_EXT:
            out.append(p)
    return sorted(out, key=lambda p: p.relative_to(app).as_posix())


def manifests(app: Path) -> list[tuple[str, int, str, str]]:
    """(path, line, display name, categories) of every KODE_APP_MANIFEST(...) outside comments."""
    hits = []
    for p in sources(app):
        code = strip_comments(p.read_text(errors="replace"))
        for m in MANIFEST_RE.finditer(code):
            hits.append((rel(app, p), line_of(code, m.start()), m.group(1), m.group(2)))
    return hits


def _scan(text: str):
    """Yield (kind, start, end) for every comment and literal: kind is comment or literal."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            yield "comment", i, j
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            yield "comment", i, j
            i = j
        elif c in "\"'":
            j = i + 1
            while j < n and text[j] != c and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            yield "literal", i, j
            i = j
        else:
            i += 1


def strip_code(text: str) -> str:
    """The text with comments and string or char literals blanked, newlines kept."""
    out = list(text)
    for _, start, end in _scan(text):
        for k in range(start, end):
            if out[k] != "\n":
                out[k] = " "
    return "".join(out)


def strip_comments(text: str) -> str:
    """The text with comments blanked and literals kept, newlines kept."""
    out = list(text)
    for kind, start, end in _scan(text):
        if kind == "comment":
            for k in range(start, end):
                if out[k] != "\n":
                    out[k] = " "
    return "".join(out)


def comments_and_strings(text: str) -> list[tuple[int, str]]:
    """The line and text of every comment and every string literal (not char literals)."""
    got = []
    for kind, start, end in _scan(text):
        piece = text[start:end]
        if kind == "comment" or piece.startswith('"'):
            got.append((line_of(text, start), piece))
    return got


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def read_sdkconfig(path: Path) -> dict[str, str]:
    return {key: value for _, key, value in sdkconfig_lines(path)}


def sdkconfig_lines(path: Path) -> list[tuple[int, str, str]]:
    """(line, key, value) of each setting; `# CONFIG_X is not set` reads as n; quotes stripped."""
    got = []
    if not path.is_file():
        return got
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        line = line.strip()
        m = re.fullmatch(r"# (CONFIG_\w+) is not set", line)
        if m:
            got.append((n, m.group(1), "n"))
            continue
        m = re.fullmatch(r"(CONFIG_\w+)=(.*)", line)
        if m:
            value = m.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] == '"':
                value = value[1:-1]
            got.append((n, m.group(1), value))
    return got


def _cmake(app: Path) -> str:
    p = app / "CMakeLists.txt"
    return p.read_text(errors="replace") if p.is_file() else ""


def _cmake_code(text: str) -> str:
    """CMake text with its # comments blanked, newlines kept."""
    return re.sub(r"#[^\n]*", lambda m: " " * len(m.group(0)), text)


def cmake_project(app: Path) -> str | None:
    m = re.search(r"^\s*project\(\s*([\w-]+)", _cmake_code(_cmake(app)), re.M)
    return m.group(1) if m else None


def cmake_project_ver(text: str) -> str | None:
    m = re.search(r'^\s*set\(\s*PROJECT_VER\s+"([^"]*)"\s*\)', _cmake_code(text), re.M)
    return m.group(1) if m else None


def cmake_idf_target_before_project(app: Path) -> bool:
    code = _cmake_code(_cmake(app))
    target = re.search(r'^\s*set\(\s*IDF_TARGET\s+"?esp32p4"?\s*\)', code, re.M)
    project = re.search(r"^\s*project\(", code, re.M)
    return bool(target and project and target.start() < project.start())


def component_deps(app: Path) -> dict[str, dict[str, str]]:
    """The kodediy/* entries of main/idf_component.yml in block form: each one's fields.

    Only the block form is read (an entry on its own line, its fields below
    it, any indentation); a flow-style entry is not, and reads as absent.
    """
    p = app / "main" / "idf_component.yml"
    deps: dict[str, dict[str, str]] = {}
    if not p.is_file():
        return deps
    lines = [line for line in p.read_text(errors="replace").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    in_deps, entry_indent, current = False, None, None
    for line in lines:
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_deps = line.strip() == "dependencies:"
            current = None
            continue
        if not in_deps:
            continue
        if entry_indent is None:
            entry_indent = indent
        if indent == entry_indent:
            m = re.fullmatch(r"\s*[\"']?(kodediy/[\w-]+)[\"']?\s*:\s*", line)
            current = deps.setdefault(m.group(1), {}) if m else None
            continue
        m = re.fullmatch(r"\s*(\w+)\s*:\s*(.*?)\s*", re.sub(r"\s+#.*$", "", line))
        if current is not None and indent > entry_indent and m:
            current[m.group(1)] = m.group(2).strip("\"'")
    return deps


def settings(app: Path) -> dict[str, str]:
    """The settings the build uses: the resolved sdkconfig when there is one, else sdkconfig.defaults.

    A committed sdkconfig, or one a build generated, wins over every defaults
    file in ESP-IDF, so the rules that read a setting read this.
    """
    resolved = app / "sdkconfig"
    if resolved.is_file():
        return read_sdkconfig(resolved)
    return read_sdkconfig(app / "sdkconfig.defaults")


def rel(ctx_app: Path, p: Path) -> str:
    return p.relative_to(ctx_app).as_posix()
