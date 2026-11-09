"""Block D: the home hold and the screenshots.

    tools/run_tests.sh
"""
import tempfile
import unittest

from tests.helpers import FIXTURES, ids, make_app, make_ctx, write_png

from kcheck import core

SDKCONFIG = (FIXTURES / "good_app" / "sdkconfig.defaults").read_text()
BLOCK_D = {f"D{n}" for n in range(1, 11)}


class RulesDTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def rejects(self, app):
        return ids(core.run(make_ctx(app), only=BLOCK_D), "reject")

    def test_good_app_passes(self):
        self.assertEqual(self.rejects(make_app(self.tmp.name)), [])

    def test_d8_home_hold_off(self):
        app = make_app(self.tmp.name, {"sdkconfig.defaults": SDKCONFIG + "CONFIG_KODEOS_HOME_HOLD=n\n"})
        self.assertEqual(self.rejects(app), ["D8"])

    def test_d9_none(self):
        self.assertEqual(self.rejects(make_app(self.tmp.name, {"appdata/screenshots": None})), ["D9"])

    def test_d9_five(self):
        app = make_app(self.tmp.name)
        for n in range(2, 6):
            write_png(app / "appdata" / "screenshots" / f"{n}.png", 410, 502)
        self.assertEqual(self.rejects(app), ["D9"])

    def test_d9_four_pass(self):
        app = make_app(self.tmp.name)
        for n in range(2, 5):
            write_png(app / "appdata" / "screenshots" / f"{n}.png", 410, 502)
        self.assertEqual(self.rejects(app), [])

    def test_d9_wrong_size(self):
        app = make_app(self.tmp.name)
        write_png(app / "appdata" / "screenshots" / "1.png", 400, 502)
        self.assertEqual(self.rejects(app), ["D9"])

    def test_d9_not_png(self):
        app = make_app(self.tmp.name, {"appdata/screenshots/1.png": b"\xff\xd8\xff\xe0" + b"\0" * 40})
        self.assertEqual(self.rejects(app), ["D9"])

    def test_d8_reads_the_resolved_sdkconfig_after_a_build(self):
        app = make_app(self.tmp.name, {"sdkconfig": "CONFIG_KODEOS_BOOT_ROLE_APP=y\n# CONFIG_KODEOS_HOME_HOLD is not set\n"})
        self.assertEqual(self.rejects(app), ["D8"])


if __name__ == "__main__":
    unittest.main()
