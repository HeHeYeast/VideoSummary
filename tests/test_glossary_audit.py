"""Unit tests for agent/glossary_audit.py (Phase 07 Phase-08-helper stub).

4 tests (G1..G4) — verify schema-stable output on missing/empty/duplicate
glossary file + forward-compat shape for Phase 08 TEACH-A3 plug-in.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from agent.glossary_audit import audit_glossary


def _ascii_tmpdir_root() -> str:
    """Mirror tests/test_lock.py:_ascii_tmpdir_root — zh-CN %TEMP% has CJK."""
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_glossary"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


class TestGlossaryAudit(unittest.TestCase):
    """4 tests covering glossary auditor stub behavior."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_G1_missing_file_returns_exists_false_shape(self):
        """G1: missing file -> exists=False shape with all empties."""
        nonexistent = self.tmp / "no_such_glossary.md"
        result = audit_glossary(path=nonexistent)
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["exists"], False)
        self.assertEqual(result["term_count"], 0)
        self.assertEqual(result["duplicate_terms"], [])
        self.assertEqual(result["conflicting_definitions"], [])
        self.assertEqual(result["glossary_path"], str(nonexistent))

    def test_G2_empty_file_exists_true_zero_terms(self):
        """G2: empty file -> exists=True, term_count=0, no dups."""
        empty = self.tmp / "empty.md"
        empty.write_text("", encoding="utf-8")
        result = audit_glossary(path=empty)
        self.assertEqual(result["exists"], True)
        self.assertEqual(result["term_count"], 0)
        self.assertEqual(result["duplicate_terms"], [])
        self.assertEqual(result["conflicting_definitions"], [])

    def test_G3_duplicate_term_with_conflicting_definitions(self):
        """G3: duplicate term entries with divergent defs -> reported."""
        dup_md = self.tmp / "dup.md"
        dup_md.write_text(
            "## TermA\n\nDefinition X\n\n## TermB\n\nA stable definition\n\n"
            "## TermA\n\nDefinition Y\n",
            encoding="utf-8",
        )
        result = audit_glossary(path=dup_md)
        self.assertEqual(result["exists"], True)
        self.assertEqual(result["term_count"], 3)  # 3 H2 anchors
        self.assertEqual(result["duplicate_terms"], ["TermA"])
        self.assertEqual(len(result["conflicting_definitions"]), 1)
        conflict = result["conflicting_definitions"][0]
        self.assertEqual(conflict["term"], "TermA")
        self.assertEqual(len(conflict["definitions"]), 2)
        self.assertIn("Definition X", conflict["definitions"])
        self.assertIn("Definition Y", conflict["definitions"])

    def test_G4_schema_keys_stable_for_phase08_extension(self):
        """G4: forward-compat — Phase 08 TEACH-A3 plugs in cross-summary frequency.
        Test asserts the 6-key schema is stable; Phase 08 may ADD keys but
        must NOT remove these.
        """
        result = audit_glossary(path=self.tmp / "missing.md")
        required_keys = {
            "version",
            "glossary_path",
            "exists",
            "term_count",
            "duplicate_terms",
            "conflicting_definitions",
        }
        self.assertTrue(required_keys.issubset(result.keys()),
                        f"missing keys: {required_keys - result.keys()}; got {result.keys()}")
        # Default-path argument case
        # Make sure default points to "output/_glossary.md" (relative) — sanity
        result_default = audit_glossary(path=None)
        self.assertIn("_glossary.md", result_default["glossary_path"])


if __name__ == "__main__":
    unittest.main()
