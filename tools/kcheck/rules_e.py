"""Rules of block E of RULES.md: khal's code style, everything in English.

E10 and E14 are judged by the reviewer. E6, E7 and E8 come from cstyle.py's
lint, E9 from basic_types.py, so the author's tools and the CI agree.
"""
from __future__ import annotations

import re
from pathlib import Path

import basic_types
import cstyle

from kcheck import source
from kcheck.core import Finding, rule

SPDX = "/* SPDX-License-Identifier: GPL-3.0-or-later */"
HEADER_LINES = 10
TEXT_FILES = ("CMakeLists.txt", "main/CMakeLists.txt", "sdkconfig.defaults", "main/idf_component.yml",
              "appdata/app.json")
BOM = b"\xef\xbb\xbf"
SPANISH_WORDS = ("que", "para", "con", "una", "los", "las", "del", "por", "esto", "pero", "como", "cuando",
                 "donde", "si", "no se", "hay", "esta", "este", "aqui", "tambien")
SPANISH_RE = re.compile(r"\b(" + "|".join(w.replace(" ", r"\s+") for w in SPANISH_WORDS) + r")\b", re.I)
SECTION_RE = re.compile(r"/\* ---- .+ ---- \*/")
TAG_RE = re.compile(r'^\s*#\s*define\s+TAG\s+"[a-z0-9_]+(\.[a-z0-9_]+)*"', re.M)
STATUS_FN_RE = re.compile(r"\bkode_status_t\s+(\w+)\s*\(")


def _text(p: Path) -> str:
    """The file's text with CRLF read as LF and a BOM dropped."""
    data = p.read_bytes()
    if data.startswith(BOM):
        data = data[len(BOM):]
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _headers(ctx):
    return [p for p in source.sources(ctx.app) if p.suffix in (".h", ".hpp")]


def _markdown(ctx):
    return sorted(p for p in ctx.app.rglob("*.md")
                  if not set(p.relative_to(ctx.app).parts) & set(source.SKIP_DIRS))


@rule("E1", "reject")
def e1_english(ctx):
    files = source.sources(ctx.app) + [ctx.app / f for f in TEXT_FILES if (ctx.app / f).is_file()]
    for p in files:
        where = source.rel(ctx.app, p)
        data = p.read_bytes()
        if data.startswith(BOM):
            yield Finding("E1", "reject", where, 1, "byte order mark: save the file as plain ASCII")
            data = data[len(BOM):]
        for n, line in enumerate(data.split(b"\n"), 1):
            if any(b > 0x7E or (b < 0x20 and b not in (0x09, 0x0D)) for b in line):
                yield Finding("E1", "reject", where, n, "a character outside ASCII: everything is in English")
    for p in source.sources(ctx.app):
        for n, piece in source.comments_and_strings(_text(p)):
            m = SPANISH_RE.search(piece)
            if m:
                yield Finding("E1", "warn", source.rel(ctx.app, p), n, f"{m.group(1)!r} reads as Spanish")
    for p in _markdown(ctx):
        for n, line in enumerate(_text(p).split("\n"), 1):
            m = SPANISH_RE.search(line)
            if m:
                yield Finding("E1", "warn", source.rel(ctx.app, p), n, f"{m.group(1)!r} reads as Spanish")


@rule("E2", "reject")
def e2_file_header(ctx):
    for p in source.sources(ctx.app):
        where = source.rel(ctx.app, p)
        lines = _text(p).split("\n")
        if not lines or lines[0].rstrip() != SPDX:
            yield Finding("E2", "reject", where, 1, f"line 1 must be {SPDX}")
        # The block must start near the top; it may run on past HEADER_LINES.
        head_end = len("\n".join(lines[:HEADER_LINES]))
        text = "\n".join(lines)
        m = re.search(r"/\*\*(.*?)\*/", text, re.S)
        if m and m.start() > head_end:
            m = None
        if not m or not re.search(rf"@file\s+{re.escape(p.name)}\b", m.group(1)) or "@brief" not in m.group(1):
            yield Finding("E2", "reject", where, 0, f"a /** block with @file {p.name} and @brief at the top")


@rule("E3", "reject")
def e3_guard(ctx):
    for p in _headers(ctx):
        where = source.rel(ctx.app, p)
        text = _text(p)
        m = re.search(r"^\s*#\s*ifndef\s+(\w+_H_)\s*$", text, re.M)
        guard = m.group(1) if m else None
        last = [line for line in text.split("\n") if line.strip()][-1:] or [""]
        if (guard is None or not re.search(rf"^\s*#\s*define\s+{guard}\s*$", text, re.M)
                or last[0].strip() != f"#endif /* {guard} */"):
            yield Finding("E3", "reject", where, 0, "an include guard NAME_H_, closed by #endif /* NAME_H_ */")
        if not re.search(r'#\s*ifdef\s+__cplusplus\s*\n\s*extern\s+"C"\s*\{', text):
            yield Finding("E3", "reject", where, 0, 'an #ifdef __cplusplus extern "C" { block')


@rule("E4", "warn")
def e4_sections(ctx):
    for p in _headers(ctx):
        if not SECTION_RE.search(_text(p)):
            yield Finding("E4", "warn", source.rel(ctx.app, p), 0, "no /* ---- Name ---- */ section lines")


def _prototypes(text):
    """(offset, return type, name, params) of each top-level function declaration."""
    code = source.strip_code(text)
    code = re.sub(r"^[ \t]*#[^\n]*", lambda m: " " * len(m.group(0)), code, flags=re.M)
    code = re.sub(r'\bextern\s+\{', lambda m: " " * len(m.group(0)), code)
    out, depth, start = [], 0, 0
    for i, c in enumerate(code):
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(depth - 1, 0)
            if depth == 0:
                start = i + 1
        elif c == ";" and depth == 0:
            stmt = code[start:i]
            lead = len(stmt) - len(stmt.lstrip())
            flat = " ".join(stmt.split())
            m = re.fullmatch(r"(.*?)\b(\w+)\s*\((.*)\)", flat)
            if m and m.group(1).strip() and not flat.startswith(("typedef", "return")) and "=" not in flat:
                out.append((start + lead, m.group(1).strip(), m.group(2), m.group(3)))
            start = i + 1
    return out


def _param_names(params):
    names, depth, cur = [], 0, ""
    for c in params + ",":
        if c in "([":
            depth += 1
        elif c in ")]":
            depth -= 1
        if c == "," and depth == 0:
            p = cur.strip()
            cur = ""
            fp = re.search(r"\(\s*\*\s*(\w+)\s*\)", p)
            if fp:
                names.append(fp.group(1))
            elif p and p != "void" and p != "...":
                ids = re.findall(r"\w+", re.sub(r"\[.*?\]", "", p))
                if len(ids) > 1:
                    names.append(ids[-1])
            continue
        cur += c
    return names


@rule("E5", "reject")
def e5_doxygen(ctx):
    for p in _headers(ctx):
        where = source.rel(ctx.app, p)
        text = _text(p)
        for off, ret, name, params in _prototypes(text):
            line = source.line_of(text, off)
            before = text[:off].rstrip()
            doc = before[before.rfind("/**"):] if before.endswith("*/") and "/**" in before else ""
            if not doc:
                yield Finding("E5", "reject", where, line, f"{name}(): no /** @brief ... */ above it")
                continue
            missing = [] if "@brief" in doc else ["@brief"]
            missing += [f"@param {n}" for n in _param_names(params) if not re.search(rf"@param\s+{n}\b", doc)]
            is_void = re.sub(r"\b(static|inline|extern)\b", "", ret).strip() == "void"
            if not is_void and "@return" not in doc:
                missing.append("@return")
            if missing:
                yield Finding("E5", "reject", where, line, f"{name}(): its comment lacks {', '.join(missing)}")
        in_struct = False
        for n, raw in enumerate(text.split("\n"), 1):
            line = raw.strip()
            if re.match(r"typedef\s+struct\b.*\{\s*$", line):
                in_struct = True
                continue
            if in_struct and line.startswith("}"):
                in_struct = False
                continue
            is_macro = re.match(r"#\s*define\s+\w+(\([^)]*\))?\s+\S", line) is not None
            is_field = in_struct and line.endswith(";")
            if (is_macro or is_field) and "/**<" not in line:
                yield Finding("E5", "warn", where, n, "a macro or field without a /**< ... */ beside it")


def _lint(ctx, wanted):
    for p in source.sources(ctx.app):
        where = source.rel(ctx.app, p)
        for rule_id, n, what in cstyle.lint_text(_text(p), str(p)):
            if rule_id == wanted:
                yield Finding(rule_id, "reject", where, n, what)


@rule("E6", "reject")
def e6_blocks(ctx):
    yield from _lint(ctx, "E6")


@rule("E7", "reject")
def e7_yoda(ctx):
    yield from _lint(ctx, "E7")


@rule("E8", "reject")
def e8_no_ternary(ctx):
    yield from _lint(ctx, "E8")


@rule("E9", "warn")
def e9_sized_types(ctx):
    for path, hits in basic_types.scan([str(ctx.app)]).items():
        for n, line in hits:
            yield Finding("E9", "warn", Path(path).relative_to(ctx.app).as_posix(), n,
                          f"a plain basic type: {line.strip()}")


@rule("E11", "warn")
def e11_logging(ctx):
    for p in source.sources(ctx.app):
        where = source.rel(ctx.app, p)
        text = _text(p)
        code = source.strip_code(text)
        m = re.search(r"\bprintf\s*\(", code)
        if m:
            yield Finding("E11", "warn", where, source.line_of(code, m.start()), "log with KLOG_*, not printf")
        if p.suffix in (".c", ".cpp") and re.search(r"\bKLOG_\w+\s*\(", code) and not TAG_RE.search(text):
            yield Finding("E11", "warn", where, 0, 'a file that logs defines TAG as "module.sub"')


@rule("E12", "warn")
def e12_include_order(ctx):
    names = {p.name for p in _headers(ctx)}
    for p in source.sources(ctx.app):
        own = p.with_suffix(".h").name
        if p.suffix not in (".c", ".cpp") or own not in names:
            continue
        m = re.search(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', _text(p), re.M)
        if m and m.group(1) != own:
            yield Finding("E12", "warn", source.rel(ctx.app, p), source.line_of(_text(p), m.start()),
                          f'the first #include is the file\'s own "{own}"')


def _status_functions(ctx):
    names = set()
    if ctx.sdk is None:
        return names
    for h in (ctx.sdk / "components").glob("**/include/*.h"):
        names.update(STATUS_FN_RE.findall(source.strip_code(h.read_text(errors="replace"))))
    return names


@rule("E13", "warn")
def e13_status_checked(ctx):
    names = _status_functions(ctx)
    if not names:
        return
    call = re.compile(r"^\s*(" + "|".join(sorted(names)) + r")\s*\(", re.M)
    for p in source.sources(ctx.app):
        code = source.strip_code(_text(p))
        for m in call.finditer(code):
            yield Finding("E13", "warn", source.rel(ctx.app, p), source.line_of(code, m.start()),
                          f"{m.group(1)}() returns kode_status_t: check it or cast to (void)")


@rule("E15", "reject")
def e15_no_tabs(ctx):
    for p in source.sources(ctx.app):
        for n, line in enumerate(_text(p).split("\n"), 1):
            if "\t" in line:
                yield Finding("E15", "reject", source.rel(ctx.app, p), n, "a tab: indent with four spaces")


def _plain(line):
    s = line.lstrip()
    return bool(s) and not line.startswith("    ") and not re.match(r"(#|-|\*|\||>|\d+\.)", s)


@rule("E16", "warn")
def e16_markdown_lines(ctx):
    for p in _markdown(ctx):
        lines = _text(p).split("\n")
        fenced = False
        for n in range(len(lines) - 1):
            if lines[n].lstrip().startswith("```"):
                fenced = not fenced
                continue
            if not fenced and _plain(lines[n]) and _plain(lines[n + 1]):
                yield Finding("E16", "warn", source.rel(ctx.app, p), n + 1, "a paragraph goes on one line")
