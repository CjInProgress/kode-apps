"""The rule runner, the source helpers and the command line, on the fixture app.

    tools/run_tests.sh
"""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import FIXTURES, KODEOS_TOOLS, TOOLS, make_app, make_ctx

from kcheck import core, source
from kcheck.core import Finding


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()
        core.RULES.pop("Z9", None)

    def test_finding_format(self):
        self.assertEqual(Finding("A2", "reject", "CMakeLists.txt", 12, "x").format(),
                         "A2 reject CMakeLists.txt:12 x")

    def test_duplicate_rule_id_raises(self):
        core.rule("Z9", "reject")(lambda ctx: [])
        with self.assertRaises(ValueError):
            core.rule("Z9", "reject")(lambda ctx: [])

    def test_crashing_rule_is_a_reject(self):
        def boom(ctx):
            raise RuntimeError("bad")
        core.rule("Z9", "reject")(boom)
        found = core.run(make_ctx(make_app(self.tmp.name)), only={"Z9"})
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].level, "reject")
        self.assertTrue(found[0].msg.startswith("Z9 crashed:"))

    def test_rule_order(self):
        self.assertEqual(sorted(["E16", "A2", "B10", "B9", "A10"], key=core.order),
                         ["A2", "A10", "B9", "B10", "E16"])

    def test_sources_include_other_cpp_extensions(self):
        app = Path(self.tmp.name) / "app"
        for rel in ("a.cc", "b.cxx", "c.hh"):
            (app / rel).parent.mkdir(parents=True, exist_ok=True)
            (app / rel).write_text("")
        self.assertEqual([p.name for p in source.sources(app)], ["a.cc", "b.cxx", "c.hh"])

    def test_component_deps_four_space_indent_and_quoted_name(self):
        yml = ('dependencies:\n    "kodediy/kode":\n        git: git@github.com:kodediy/kode-sdk.git\n'
               '        path: components/kode\n        version: v00.00.27\n')
        app = make_app(self.tmp.name, {"main/idf_component.yml": yml})
        self.assertEqual(source.component_deps(app)["kodediy/kode"]["version"], "v00.00.27")

    def test_sources_skip_generated_dirs(self):
        app = Path(self.tmp.name) / "app"
        for rel in ("main/a.c", "components/x/b.cpp", "include/c.hpp", "build/d.c",
                    "managed_components/e.h", ".git/f.c"):
            (app / rel).parent.mkdir(parents=True, exist_ok=True)
            (app / rel).write_text("")
        got = [p.relative_to(app).as_posix() for p in source.sources(app)]
        self.assertEqual(got, ["components/x/b.cpp", "include/c.hpp", "main/a.c"])

    def test_strip_code_keeps_lines(self):
        text = 'a = 1; /* one\ntwo\nthree */ b = "//x";\nc = \'"\';\n'
        out = source.strip_code(text)
        self.assertEqual(out.count("\n"), text.count("\n"))
        lines = out.split("\n")
        self.assertIn("a = 1;", lines[0])
        self.assertNotIn("one", lines[0])
        self.assertIn("b =", lines[2])
        self.assertNotIn("//x", lines[2])
        self.assertIn("c =", lines[3])

    def test_comments_and_strings(self):
        got = source.comments_and_strings('x = "hi"; // note\n/* a\nb */\n')
        self.assertEqual(got, [(1, '"hi"'), (1, "// note"), (2, "/* a\nb */")])

    def test_read_sdkconfig(self):
        p = Path(self.tmp.name) / "sdkconfig.defaults"
        p.write_text('# a comment\nCONFIG_A=y\nCONFIG_B="x"\n# CONFIG_C is not set\n')
        self.assertEqual(source.read_sdkconfig(p), {"CONFIG_A": "y", "CONFIG_B": "x", "CONFIG_C": "n"})

    def test_cmake_parsers(self):
        app = make_app(self.tmp.name)
        self.assertEqual(source.cmake_project(app), "good_app")
        self.assertEqual(source.cmake_project_ver((app / "CMakeLists.txt").read_text()), "1.0.0")
        self.assertTrue(source.cmake_idf_target_before_project(app))

    def test_component_deps_quotes(self):
        yml = ('dependencies:\n  kodediy/kode:\n    git: git@github.com:kodediy/kode-sdk.git\n'
               '    path: components/kode\n    version: "v00.00.27"\n'
               '  kodediy/kui:\n    path: components/kui\n    version: v00.00.27  # pinned\n')
        app = make_app(self.tmp.name, {"main/idf_component.yml": yml})
        deps = source.component_deps(app)
        self.assertEqual(deps["kodediy/kode"]["version"], "v00.00.27")
        self.assertEqual(deps["kodediy/kui"]["version"], "v00.00.27")
        self.assertEqual(deps["kodediy/kode"]["path"], "components/kode")

    def test_line_of(self):
        self.assertEqual(source.line_of("a\nb\nc", 4), 3)

    def test_good_app_has_no_reject(self):
        found = core.run(make_ctx(make_app(self.tmp.name)))
        rejects = [f.format() for f in found if f.level == "reject"]
        self.assertEqual(rejects, [])


class RulesMdTest(unittest.TestCase):
    REVIEW_ONLY = {"B9", "C1", "C4", "C6", "C9", "C10", "D1", "D2", "D4", "D7", "E10", "E14"}
    PENDING = {"D3", "D5", "D6", "D10"}

    def test_rules_md_lists_every_id(self):
        core.load_rules()
        text = (TOOLS.parent / "RULES.md").read_text()
        rows = re.findall(r"^\|\s*([A-E]\d+)\s*\|", text, re.M)
        want = set(core.RULES) | {"A1"} | self.REVIEW_ONLY
        self.assertEqual(sorted(rows, key=core.order), sorted(want, key=core.order))
        for rule_id in self.PENDING:
            self.assertRegex(text, rf"\b{rule_id}\b")


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def check(self, app, *extra):
        rel = Path(self.tmp.name) / "releases.json"
        rel.write_text(json.dumps([{"tagName": t} for t in ("v00.00.27", "v00.00.26")]))
        cmd = [sys.executable, "-I", str(TOOLS / "check_app.py"), "check", "--app", str(app),
               "--catalog", str(FIXTURES / "catalog"), "--build", str(FIXTURES / "good_build"),
               "--sdk", str(FIXTURES / "sdk"), "--releases", str(rel),
               "--kappdata-dir", str(KODEOS_TOOLS), *extra]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_good_app_exits_0(self):
        out = Path(self.tmp.name) / "findings.txt"
        r = self.check(make_app(self.tmp.name), "--output", str(out))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 reject", r.stdout)
        self.assertTrue(out.is_file())

    def test_missing_app_dir_exits_2(self):
        r = self.check(Path(self.tmp.name) / "nowhere")
        self.assertEqual(r.returncode, 2)

    def test_sdk_tag_and_version(self):
        app = make_app(self.tmp.name)
        for sub, want in (("sdk-tag", "v00.00.27"), ("version", "1.0.0")):
            r = subprocess.run([sys.executable, "-I", str(TOOLS / "check_app.py"), sub, str(app)],
                               capture_output=True, text=True)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, want))


if __name__ == "__main__":
    unittest.main()
