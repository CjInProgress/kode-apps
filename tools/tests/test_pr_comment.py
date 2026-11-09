"""The pull request comment the workflow keeps up to date.

    tools/run_tests.sh
"""
import tempfile
import unittest
from pathlib import Path

import pr_comment


class PrCommentTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def app(self, name, lines, **meta):
        (self.dir / f"{name}.txt").write_text("\n".join(lines) + "\n")
        meta.setdefault("status", "built")
        (self.dir / f"{name}.meta").write_text("".join(f"{k}={v}\n" for k, v in meta.items()))

    def test_marker_first_line(self):
        self.app("scope", ["0 reject, 0 warn"], version="1.0.0")
        self.assertEqual(pr_comment.render(self.dir).split("\n")[0], pr_comment.MARKER)

    def test_counts_and_lists(self):
        self.app("scope", ["A2 reject CMakeLists.txt:0 bad name", "E9 warn main/a.c:3 int n;",
                           "E4 warn main/a.h:0 no sections", "1 reject, 2 warn"],
                 version="1.0.0", artifact="https://example.invalid/run/1")
        body = pr_comment.render(self.dir)
        self.assertIn("### scope 1.0.0", body)
        self.assertIn("**1 reject, 2 warn**", body)
        details = body.index("<details>")
        self.assertLess(body.index("`A2` CMakeLists.txt:0 bad name"), details)
        self.assertGreater(body.index("`E9` main/a.c:3 int n;"), details)
        self.assertIn("https://example.invalid/run/1", body)

    def test_removed_app_line(self):
        (self.dir / "old.meta").write_text("status=removed\n")
        self.assertIn("old leaves the catalog.", pr_comment.render(self.dir))

    def test_two_apps_both_listed(self):
        self.app("alpha", ["B6 reject .:0 not built", "1 reject, 0 warn"], version="0.1.0", status="failed")
        self.app("beta", ["0 reject, 0 warn"], version="2.0.0")
        body = pr_comment.render(self.dir)
        self.assertIn("### alpha 0.1.0", body)
        self.assertIn("### beta 2.0.0", body)
        self.assertIn("The build failed", body)

    def test_catalog_findings(self):
        (self.dir / "catalog.txt").write_text("A1 reject .gitmodules:0 url must be relative\nchange x - 1111\n")
        body = pr_comment.render(self.dir)
        self.assertIn("### The catalog", body)
        self.assertIn("`A1` .gitmodules:0 url must be relative", body)
        self.assertNotIn("change x", body)

    def test_nothing_to_report(self):
        (self.dir / "catalog.txt").write_text("")
        self.assertIn("No app changes", pr_comment.render(self.dir))

    def test_change_without_meta_is_not_checked(self):
        (self.dir / "catalog.txt").write_text("change foo - 1111\n")
        body = pr_comment.render(self.dir)
        self.assertIn("foo was not checked", body)
        self.assertNotIn("pass", body)

    def test_failed_job_is_said(self):
        self.app("scope", ["0 reject, 0 warn"], version="1.0.0")
        body = pr_comment.render(self.dir, {"tests": "failure", "find": "success", "check": "skipped"})
        self.assertIn("tests ended failure", body)


if __name__ == "__main__":
    unittest.main()
