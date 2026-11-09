"""Block E: khal's code style, everything in English.

    tools/run_tests.sh
"""
import tempfile
import unittest

from tests.helpers import FIXTURES, make_app, make_ctx

from kcheck import core

AO = (FIXTURES / "good_app" / "main" / "good_app_ao.c").read_text()
HDR = (FIXTURES / "good_app" / "main" / "good_app_ao.h").read_text()
MAIN = (FIXTURES / "good_app" / "main" / "good_app_main.c").read_text()
BLOCK_E = {f"E{n}" for n in range(1, 17)}
PROTO = "void good_app_start(void);"


def hdr_with(decl, doc="/**\n * @brief Stop it.\n */\n"):
    return HDR.replace(PROTO, PROTO + "\n\n" + doc + decl)


def in_idle(line):
    return AO.replace('        KLOG_I(TAG, "a button");', f'        KLOG_I(TAG, "a button");\n        {line}')


class RulesETest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def found(self, edits=None, level=None):
        app = make_app(self.tmp.name, edits)
        return sorted({(f.rule, f.level) for f in core.run(make_ctx(app), only=BLOCK_E)
                       if level is None or f.level == level})

    def test_good_app_silent(self):
        app = make_app(self.tmp.name)
        self.assertEqual([f.format() for f in core.run(make_ctx(app), only=BLOCK_E)], [])

    def test_e1_accent_rejects(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle("/* número */")}), [("E1", "reject")])

    def test_e1_accent_in_cmake_rejects(self):
        cmake = (FIXTURES / "good_app" / "CMakeLists.txt").read_text() + "# versión\n"
        self.assertEqual(self.found({"CMakeLists.txt": cmake}), [("E1", "reject")])

    def test_e1_bom_rejects(self):
        app = make_app(self.tmp.name, {"main/good_app_main.c": b"\xef\xbb\xbf" + MAIN.encode()})
        got = [(f.rule, f.level, f.line) for f in core.run(make_ctx(app), only={"E1"})]
        self.assertEqual(got, [("E1", "reject", 1)])

    def test_e1_spanish_word_warns(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle("/* esto es para el boton */")}), [("E1", "warn")])

    def test_e1_spanish_on_glass_warns(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle('KLOG_I(TAG, "pulsa para salir");')}),
                         [("E1", "warn")])

    def test_e1_spanish_in_readme_warns(self):
        self.assertEqual(self.found({"README.md": "# good_app\n\nUna app para probar.\n"}), [("E1", "warn")])

    def test_e1_english_silent(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle("/* the icon is for the console */")}), [])

    def test_e2_missing_spdx(self):
        self.assertEqual(self.found({"main/good_app_main.c": MAIN.split("\n", 1)[1]}), [("E2", "reject")])

    def test_e2_missing_file_tag(self):
        self.assertEqual(self.found({"main/good_app_main.c": MAIN.replace(" * @file good_app_main.c\n", "")}),
                         [("E2", "reject")])

    def test_e2_long_header_passes(self):
        long_doc = " * @brief The fixture app's entry point.\n" + " *\n * More words.\n" * 8
        main = MAIN.replace(" * @brief The fixture app's entry point: the system, then its one Active Object.\n", long_doc)
        self.assertEqual(self.found({"main/good_app_main.c": main}), [])

    def test_e3_no_guard(self):
        hdr = HDR.replace("#ifndef GOOD_APP_AO_H_\n#define GOOD_APP_AO_H_\n", "").replace(
            "#endif /* GOOD_APP_AO_H_ */\n", "")
        self.assertEqual(self.found({"main/good_app_ao.h": hdr}), [("E3", "reject")])

    def test_e3_no_extern_c(self):
        hdr = HDR.replace('#ifdef __cplusplus\nextern "C" {\n#endif\n', "").replace("#ifdef __cplusplus\n}\n#endif\n", "")
        self.assertEqual(self.found({"main/good_app_ao.h": hdr}), [("E3", "reject")])

    def test_e3_crlf_still_passes(self):
        edits = {"main/good_app_ao.h": HDR.replace("\n", "\r\n").encode(),
                 "main/good_app_main.c": MAIN.replace("\n", "\r\n").encode()}
        self.assertEqual([r for r in self.found(edits) if r[0] in ("E2", "E3", "E5")], [])

    def test_e4_no_sections_warns(self):
        self.assertEqual(self.found({"main/good_app_ao.h": HDR.replace("/* ---- Calls ---- */\n\n", "")}),
                         [("E4", "warn")])

    def test_e5_missing_param(self):
        self.assertEqual(self.found({"main/good_app_ao.h": hdr_with("void good_app_stop(uint8_t why);")}),
                         [("E5", "reject")])

    def test_e5_missing_return(self):
        doc = "/**\n * @brief How many.\n */\n"
        self.assertEqual(self.found({"main/good_app_ao.h": hdr_with("uint8_t good_app_count(void);", doc)}),
                         [("E5", "reject")])

    def test_e5_no_doc(self):
        self.assertEqual(self.found({"main/good_app_ao.h": hdr_with("void good_app_stop(void);", "")}),
                         [("E5", "reject")])

    def test_e5_full_doc_passes(self):
        doc = "/**\n * @brief How many of a kind.\n * @param kind The kind.\n * @return The count.\n */\n"
        self.assertEqual(self.found({"main/good_app_ao.h": hdr_with("uint8_t good_app_count(uint8_t kind);", doc)}), [])

    def test_e5_void_needs_no_return(self):
        self.assertEqual(self.found({"main/good_app_ao.h": hdr_with("void good_app_stop(void);")}), [])

    def test_e5_macro_without_comment_warns(self):
        hdr = HDR.replace("/* ---- Calls ---- */", "/* ---- Limits ---- */\n\n#define GOOD_MAX 4U\n\n/* ---- Calls ---- */")
        self.assertEqual(self.found({"main/good_app_ao.h": hdr}), [("E5", "warn")])

    def test_e6_brace(self):
        self.assertEqual(self.found({"main/good_app_ao.c": AO.replace("    else\n    {", "    else {")}),
                         [("E6", "reject")])

    def test_e7_yoda(self):
        self.assertEqual(self.found({"main/good_app_ao.c": AO.replace("BUTTON_SIG == e->sig", "e->sig == BUTTON_SIG")}),
                         [("E7", "reject")])

    def test_e8_ternary(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle("status = (0U != e->sig) ? Q_HANDLED() : status;")}),
                         [("E8", "reject")])

    def test_e9_int_warns(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle("int n = 0;")}), [("E9", "warn")])

    def test_e11_printf_warns(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle('printf("x");')}), [("E11", "warn")])

    def test_e11_no_tag_warns(self):
        self.assertEqual(self.found({"main/good_app_ao.c": AO.replace('#define TAG "good.ao"   /**< This file\'s log tag. */\n', "")}),
                         [("E11", "warn")])

    def test_e12_include_order_warns(self):
        ao = AO.replace('#include "good_app_ao.h"\n\n#include "kode_ao.h"', '#include "kode_ao.h"\n#include "good_app_ao.h"')
        self.assertEqual(self.found({"main/good_app_ao.c": ao}), [("E12", "warn")])

    def test_e13_ignored_status_warns(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle("kode_led_rgb(1U, 2U, 3U);")}), [("E13", "warn")])

    def test_e13_cast_to_void_silent(self):
        self.assertEqual(self.found({"main/good_app_ao.c": in_idle("(void)kode_led_rgb(1U, 2U, 3U);")}), [])

    def test_e15_tab(self):
        self.assertEqual(self.found({"main/good_app_ao.c": AO.replace("    QState status;", "\tQState status;")}),
                         [("E15", "reject")])

    def test_e16_wrapped_paragraph_warns(self):
        self.assertEqual(self.found({"README.md": "# good_app\n\nThe smallest app that passes\nevery rule.\n"}),
                         [("E16", "warn")])

    def test_e16_lists_and_code_silent(self):
        md = "# good_app\n\n- one\n- two\n\n```\na\nb\n```\n\n| a |\n| b |\n"
        self.assertEqual(self.found({"README.md": md}), [])


if __name__ == "__main__":
    unittest.main()
