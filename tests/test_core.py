"""Unit tests for splitpay_core (pure logic — no PDFs, no GUI needed).

Run from the repository root:
    python -m unittest discover tests -v
"""

import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# splitpay_core imports fitz at module level; the pure functions under test
# don't use it, so a stub is enough when PyMuPDF isn't installed.
try:
    import fitz  # noqa: F401
except ImportError:
    sys.modules["fitz"] = types.ModuleType("fitz")

import splitpay_core as core  # noqa: E402


class TestSanitizeFilename(unittest.TestCase):
    def test_removes_invalid_chars(self):
        self.assertEqual(core.sanitize_filename("a b/c*d"), "a_bcd")

    def test_strips_and_replaces_spaces(self):
        self.assertEqual(core.sanitize_filename("  John Doe  "), "John_Doe")

    def test_keeps_word_chars_and_dashes(self):
        self.assertEqual(core.sanitize_filename("A-1_b"), "A-1_b")

    def test_empty(self):
        self.assertEqual(core.sanitize_filename(""), "")


class TestNormalizeFolderName(unittest.TestCase):
    def test_croatian_diacritics(self):
        self.assertEqual(core.normalize_folder_name("Đurđa Šarić ž"), "durdasaricz")

    def test_spaces_and_case(self):
        self.assertEqual(core.normalize_folder_name("John Doe"), "johndoe")

    def test_specials_removed(self):
        self.assertEqual(core.normalize_folder_name("A.B/C-1"), "abc1")


class TestLinePatterns(unittest.TestCase):
    LINES = ["ACME d.o.o.", "John Doe", "228-11", "Payslip June"]

    def test_whole_line_token_is_zero_based(self):
        self.assertEqual(
            core.build_value_from_line_pattern(self.LINES, "[LINE 1]"), "John Doe"
        )

    def test_char_from(self):
        self.assertEqual(
            core.build_value_from_line_pattern(self.LINES, "[LINE 1(6)]"), "Doe"
        )

    def test_char_range_one_based_inclusive(self):
        self.assertEqual(
            core.build_value_from_line_pattern(self.LINES, "[LINE 2(1/3)]"), "228"
        )

    def test_out_of_range_line_is_empty(self):
        self.assertEqual(
            core.build_value_from_line_pattern(self.LINES, "[LINE 99]"), ""
        )

    def test_mixed_text_and_tokens(self):
        self.assertEqual(
            core.build_value_from_line_pattern(self.LINES, "X_[LINE 2(1/3)]_Y"),
            "X_228_Y",
        )

    def test_empty_pattern(self):
        self.assertEqual(core.build_value_from_line_pattern(self.LINES, ""), "")
        self.assertEqual(core.build_value_from_line_pattern(self.LINES, None), "")

    def test_filename_appends_pdf_and_sanitizes(self):
        self.assertEqual(
            core.build_filename_from_line_pattern(self.LINES, "[LINE 1]_[LINE 2(1/3)]"),
            "John_Doe_228.pdf",
        )

    def test_filename_empty_result(self):
        self.assertEqual(core.build_filename_from_line_pattern(self.LINES, ""), "")

    def test_filename_existing_pdf_extension_not_doubled(self):
        result = core.build_filename_from_line_pattern(self.LINES, "[LINE 1].pdf")
        self.assertEqual(result, "John_Doe.pdf")


class TestUnresolvedTokens(unittest.TestCase):
    """A pattern whose tokens all resolve empty must yield no filename, even
    when literal separators remain — so the page routes to !manual_review."""

    def test_blank_page_with_literal_underscore_is_unresolved(self):
        blank = ["", "", ""]
        self.assertEqual(
            core.build_filename_from_line_pattern(blank, "[LINE 1]_[LINE 2]"),
            "",
        )

    def test_out_of_range_tokens_with_literals_are_unresolved(self):
        lines = ["only one line"]
        self.assertEqual(
            core.build_filename_from_line_pattern(lines, "[LINE 5]_[LINE 6(1/3)]"),
            "",
        )

    def test_literal_underscore_preserved_when_a_token_resolves(self):
        lines = ["Acme", "Payslip"]
        self.assertEqual(
            core.build_filename_from_line_pattern(lines, "[LINE 0]_[LINE 1]"),
            "Acme_Payslip.pdf",
        )

    def test_partial_resolution_keeps_literal(self):
        # First token resolves, second is empty -> still a valid page.
        lines = ["Acme", ""]
        self.assertEqual(
            core.build_filename_from_line_pattern(lines, "[LINE 0]_[LINE 1]"),
            "Acme_.pdf",
        )


class TestExtractionNaming(unittest.TestCase):
    def test_single_page_uses_source_name(self):
        self.assertEqual(
            core.extraction_filename("/tmp/payroll_july_2026.pdf", page=5),
            "payroll_july_2026_page_5.pdf",
        )

    def test_range_uses_source_name(self):
        self.assertEqual(
            core.extraction_filename(
                "/tmp/payroll_july_2026.pdf", page_from=5, page_to=10
            ),
            "payroll_july_2026_pages_5-10.pdf",
        )

    def test_source_name_is_sanitized(self):
        self.assertEqual(
            core.extraction_filename("/tmp/July Payroll 2026.pdf", page=3),
            "July_Payroll_2026_page_3.pdf",
        )

    def test_extraction_not_labelled_merge(self):
        name = core.extraction_filename("/tmp/source.pdf", page=5)
        self.assertFalse(name.startswith("merged"))
        self.assertEqual(name, "source_page_5.pdf")

    def test_empty_source_name_falls_back(self):
        # A source whose base name sanitizes to nothing falls back to "document".
        self.assertEqual(
            core.extraction_filename("/tmp/@@@.pdf", page=1), "document_page_1.pdf"
        )


class TestMergeNaming(unittest.TestCase):
    def test_merge_default_is_merge_specific(self):
        name = core.merge_default_filename()
        self.assertTrue(name.startswith("merged_"))
        self.assertTrue(name.endswith(".pdf"))
        self.assertNotIn("page", name)


class TestUniquePaths(unittest.TestCase):
    def test_unique_path_suffix(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "f.pdf")
            self.assertEqual(core.get_unique_path(p), p)
            open(p, "w").close()
            self.assertEqual(core.get_unique_path(p), os.path.join(d, "f_1.pdf"))
            open(os.path.join(d, "f_1.pdf"), "w").close()
            self.assertEqual(core.get_unique_path(p), os.path.join(d, "f_2.pdf"))


class TestAuditCsv(unittest.TestCase):
    def test_roundtrip(self):
        rows = [
            {
                "Page": 1,
                "Status": "OK",
                "Filename": "a.pdf",
                "FolderRaw": "John Doe",
                "FolderName": "johndoe",
                "Note": "",
            },
            {
                "Page": 2,
                "Status": "Failed",
                "Filename": "",
                "FolderRaw": "",
                "FolderName": "",
                "Note": "Sent to Unmatched_Page_2.pdf",
            },
        ]
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "audit.csv")
            core.write_audit_csv(path, rows)
            with open(path, "r", encoding="utf-8-sig") as f:
                content = f.read()
        lines = content.strip().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0], ",".join(core.AUDIT_FIELDS))
        self.assertIn("johndoe", lines[1])
        self.assertIn("Unmatched_Page_2.pdf", lines[2])


class TestMoveItem(unittest.TestCase):
    def test_move_up(self):
        self.assertEqual(core.move_item(["a", "b", "c"], 2, -1), (["a", "c", "b"], 1))

    def test_move_down(self):
        self.assertEqual(core.move_item(["a", "b", "c"], 0, +1), (["b", "a", "c"], 1))

    def test_move_up_at_top_is_noop(self):
        self.assertEqual(core.move_item(["a", "b"], 0, -1), (["a", "b"], 0))

    def test_move_down_at_bottom_is_noop(self):
        self.assertEqual(core.move_item(["a", "b"], 1, +1), (["a", "b"], 1))

    def test_none_index_is_noop(self):
        self.assertEqual(core.move_item(["a", "b"], None, -1), (["a", "b"], None))

    def test_returns_new_list(self):
        original = ["a", "b"]
        result, _ = core.move_item(original, 0, +1)
        self.assertIsNot(result, original)
        self.assertEqual(original, ["a", "b"])  # unchanged


class TestTextEmptiness(unittest.TestCase):
    def test_all_blank_is_empty(self):
        self.assertTrue(core.text_is_effectively_empty(["", "   ", "\n\t"]))

    def test_none_entries_are_empty(self):
        self.assertTrue(core.text_is_effectively_empty([None, ""]))

    def test_any_text_is_not_empty(self):
        self.assertFalse(core.text_is_effectively_empty(["", "John Doe", ""]))

    def test_empty_list_is_empty(self):
        self.assertTrue(core.text_is_effectively_empty([]))


class TestFriendlyOpenError(unittest.TestCase):
    def test_password_maps_to_protected_message(self):
        self.assertIn("password-protected", core._friendly_open_error("needs password"))

    def test_encrypt_maps_to_protected_message(self):
        self.assertIn("password-protected", core._friendly_open_error("document is encrypted"))

    def test_missing_file_message(self):
        self.assertIn("could not be found", core._friendly_open_error("No such file"))

    def test_generic_maps_to_corrupt_message(self):
        self.assertIn("corrupted", core._friendly_open_error("format error: garbage"))


class _FakeDoc:
    def __init__(self, needs_pass=False, pages=None):
        self.needs_pass = needs_pass
        self._pages = list(pages or [])
        self.closed = False

    def __len__(self):
        return len(self._pages)

    def load_page(self, i):
        text = self._pages[i]

        class _P:
            def get_text(self_inner):
                return text

        return _P()

    def close(self):
        self.closed = True


class TestOpenPdfChecked(unittest.TestCase):
    def setUp(self):
        self._orig_open = getattr(core.fitz, "open", None)

    def tearDown(self):
        core.fitz.open = self._orig_open

    def test_password_protected_raises_pdf_error(self):
        core.fitz.open = lambda path: _FakeDoc(needs_pass=True)
        with self.assertRaises(core.PdfError) as ctx:
            core.open_pdf_checked("x.pdf")
        self.assertIn("password-protected", str(ctx.exception))

    def test_corrupt_open_raises_pdf_error(self):
        def boom(path):
            raise RuntimeError("cannot open broken file: format error")

        core.fitz.open = boom
        with self.assertRaises(core.PdfError) as ctx:
            core.open_pdf_checked("x.pdf")
        self.assertIn("corrupted", str(ctx.exception))

    def test_valid_pdf_returns_doc(self):
        core.fitz.open = lambda path: _FakeDoc(pages=["hello"])
        doc = core.open_pdf_checked("x.pdf")
        self.assertEqual(len(doc), 1)

    def test_preflight_reports_text_presence(self):
        core.fitz.open = lambda path: _FakeDoc(pages=["Name", "228"])
        info = core.preflight_pdf("x.pdf")
        self.assertEqual(info["page_count"], 2)
        self.assertTrue(info["has_text"])

    def test_preflight_flags_scanned_pdf(self):
        core.fitz.open = lambda path: _FakeDoc(pages=["", "   "])
        info = core.preflight_pdf("x.pdf")
        self.assertFalse(info["has_text"])


class TestSchemaLoading(unittest.TestCase):
    def test_corrupt_json_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bad.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("{ this is not valid json ")
            self.assertIsNone(core._read_schema_file(path))

    def test_non_object_json_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "list.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write("[1, 2, 3]")
            self.assertIsNone(core._read_schema_file(path))

    def test_valid_schema_returns_dict(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "ok.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write('{"file_pattern": "[LINE 0].pdf", "folder_pattern": ""}')
            data = core._read_schema_file(path)
            self.assertEqual(data["file_pattern"], "[LINE 0].pdf")


if __name__ == "__main__":
    unittest.main(verbosity=2)
