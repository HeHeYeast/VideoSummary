"""Phase 09 CORR-03a — unit tests for agent.summary_lint.lint_summary().

14 tests covering:
  - 5 format invariants (timestamp / code-fence lang / relative frame paths /
    second-person imperative / trace-after-claim)
  - citation_stats happy path
  - citation eligibility violations (FORBIDDEN in TL;DR + 你需要 prelude)
  - glossary inconsistency drift detection
  - glossary_path=None graceful degrade
  - uncertainty marker counting
  - empty-summary edge case (0-byte file)
  - schema version + checked_at ISO-8601 shape

K5 boundary: tests use Write-to-tempdir only; never touch the project's
own summary / plan / schedule artifacts.
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from agent.summary_lint import LINT_FILENAME, lint_summary


class TestSummaryLint(unittest.TestCase):
    def setUp(self):
        # Each test gets its own tempdir; auto-cleanup via TemporaryDirectory ctx
        self._td = tempfile.TemporaryDirectory(prefix="test_summary_lint_")
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _write_summary(self, body: str) -> Path:
        p = self.tmp / "summary.md"
        p.write_text(body, encoding="utf-8")
        return p

    # ── Test 1: 5 invariants happy path ──
    def test_01_all_invariants_clean(self):
        body = (
            "# Test\n"
            "\n"
            "## 一、章节\n"
            "\n"
            "[00:01:23] **步骤一**：你打开 settings.json 配置参数 fps=0.4 [seg_0001_000005.jpg @ 00:01:23]。\n"
            "\n"
            "![](frames/seg_0001_000005.jpg)\n"
            "\n"
            "```python\n"
            "x = 1\n"
            "```\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        for inv_name, inv in result["format_invariants"].items():
            self.assertEqual(
                inv["violations"], [],
                f"invariant {inv_name} should have no violations, got {inv['violations']}",
            )

    # ── Test 2: timestamp invariant violation ──
    def test_02_timestamp_format_violations(self):
        body = (
            "## 一、章节\n"
            "\n"
            "[01:23] short timestamp here.\n"
            "[1:23:45] missing leading zero.\n"
            "[12:34:56] valid one — no violation.\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        violations = result["format_invariants"]["timestamp_format"]["violations"]
        self.assertEqual(len(violations), 2,
                         f"expected exactly 2 timestamp violations, got {violations}")
        # Verify line numbers are populated
        for v in violations:
            self.assertIn("line", v)
            self.assertIn("snippet", v)

    # ── Test 3: code-fence language violation ──
    def test_03_code_fence_language_violations(self):
        body = (
            "## 一、章节\n"
            "\n"
            "```\n"
            "no lang first.\n"
            "```\n"
            "\n"
            "```python\n"
            "ok = 1\n"
            "```\n"
            "\n"
            "```\n"
            "no lang second.\n"
            "```\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        violations = result["format_invariants"]["code_fence_language"]["violations"]
        self.assertEqual(len(violations), 2,
                         f"expected exactly 2 fence-lang violations, got {violations}")

    # ── Test 4: relative frame path violation ──
    def test_04_relative_frame_path_violations(self):
        body = (
            "## 一、章节\n"
            "\n"
            "![](D:/abs/path/frames/x.jpg)\n"
            "![](http://example.com/img.png)\n"
            "![](frames/seg_0001_000005.jpg)\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        violations = result["format_invariants"]["relative_frame_paths"]["violations"]
        self.assertEqual(len(violations), 2,
                         f"expected exactly 2 frame-path violations, got {violations}")

    # ── Test 5: 第二人称 imperative violation ──
    def test_05_second_person_imperative_violations(self):
        body = (
            "## 一、章节\n"
            "\n"
            "我们打开 settings.json 然后做点啥。\n"
            "settings.json 被打开 之后做点别的。\n"
            "你打开 settings.json — 这条是合规的。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        violations = result["format_invariants"]["second_person_imperative"]["violations"]
        self.assertGreaterEqual(len(violations), 2,
                                f"expected at least 2 second-person violations, got {violations}")

    # ── Test 6: trace_after_claim violation (5th invariant) ──
    def test_06_trace_after_claim_violations(self):
        body = (
            "## 一、章节\n"
            "\n"
            "本段说参数 fps=0.4 但没加溯源 token。\n"
            "本段说参数 fps=0.5 加了 token [seg_0001_000005.jpg @ 00:01:23]。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        violations = result["format_invariants"]["trace_after_claim"]["violations"]
        self.assertGreaterEqual(len(violations), 1,
                                f"expected at least 1 trace-after-claim violation, got {violations}")
        # Specifically, the line WITH the trace token should not be flagged
        flagged_lines = {v["line"] for v in violations}
        self.assertNotIn(
            5, flagged_lines,
            "the line with the trace token should NOT be in the violations",
        )

    # ── Test 7: citation_stats happy path ──
    def test_07_citation_stats_counts(self):
        body = (
            "## 一、章节\n"
            "\n"
            "本段说参数 fps=0.4 [seg_0001_000005.jpg @ 00:01:23]。\n"
            "本段说参数 fps=0.5 [seg_0002_000005.jpg @ 00:01:24]。\n"
            "本段说参数 fps=0.6 没溯源 token。\n"
            "本段标记 [?] 不确定。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        stats = result["citation_stats"]
        self.assertGreaterEqual(stats["claims_total"], 3)
        self.assertGreaterEqual(stats["claims_with_trace"], 2)
        self.assertGreaterEqual(len(stats["claims_without_trace"]), 1)
        self.assertEqual(stats["uncertainty_markers"], 1)
        # trace_density is a float in [0, 1]
        self.assertGreaterEqual(stats["trace_density"], 0.0)
        self.assertLessEqual(stats["trace_density"], 1.0)

    # ── Test 8: citation eligibility — FORBIDDEN in TL;DR ──
    def test_08_citation_eligibility_tldr_forbidden(self):
        body = (
            "## 5 分钟速读版\n"
            "\n"
            "速读版的核心 fps=0.4 [seg_0001_000005.jpg @ 00:01:23]。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        violations = result["citation_eligibility_violations"]
        self.assertEqual(len(violations), 1, f"expected 1 TL;DR violation, got {violations}")
        v = violations[0]
        self.assertEqual(v["section"], "TL;DR")
        self.assertIn("FORBIDDEN", v["reason"])

    # ── Test 9: citation eligibility — FORBIDDEN in 你需要 prelude ──
    def test_09_citation_eligibility_prelude_forbidden(self):
        body = (
            "## 读这篇前你需要知道\n"
            "\n"
            "你需要先理解 X [seg_0001_000005.jpg @ 00:01:23]。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        violations = result["citation_eligibility_violations"]
        self.assertEqual(len(violations), 1, f"expected 1 prelude violation, got {violations}")
        v = violations[0]
        self.assertEqual(v["section"], "你需要知道什么")
        self.assertIn("FORBIDDEN", v["reason"])

    # ── Test 10: glossary inconsistency ──
    def test_10_glossary_inconsistency(self):
        glossary = self.tmp / "_glossary.md"
        glossary.write_text(
            "# 术语表\n\n## LoRA (Low-Rank Adaptation Model)\n\n释义...\n",
            encoding="utf-8",
        )
        body = (
            "## 一、章节\n"
            "\n"
            "本段使用 LoRA (Low-Rank Adaptation) 微调。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p, glossary_path=glossary)
        drifts = result["glossary_inconsistencies"]
        self.assertGreaterEqual(len(drifts), 1, f"expected at least 1 drift, got {drifts}")
        d = drifts[0]
        self.assertEqual(d["term"], "LoRA")
        self.assertEqual(d["summary_definition"], "Low-Rank Adaptation")
        self.assertEqual(d["glossary_definition"], "Low-Rank Adaptation Model")
        self.assertTrue(d["drift_detected"])

    # ── Test 11: glossary inconsistency — None graceful degrade ──
    def test_11_glossary_path_none_graceful(self):
        body = (
            "## 一、章节\n"
            "\n"
            "本段使用 LoRA (Low-Rank Adaptation) 微调。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p, glossary_path=None)
        self.assertEqual(result["glossary_inconsistencies"], [])

    # ── Test 12: uncertainty marker count ──
    def test_12_uncertainty_marker_count(self):
        body = (
            "## 一、章节\n"
            "\n"
            "句子一 [?]。\n"
            "句子二 [?]。\n"
            "句子三 [?]。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        self.assertEqual(result["citation_stats"]["uncertainty_markers"], 3)

    # ── Test 13: empty-summary edge case ──
    def test_13_empty_summary_no_crash(self):
        p = self.tmp / "summary.md"
        p.write_text("", encoding="utf-8")  # 0 bytes
        result = lint_summary(p)
        # Schema validity
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["schema_version"], 1)
        for inv_name, inv in result["format_invariants"].items():
            self.assertEqual(inv["violations"], [])
        self.assertEqual(result["citation_stats"]["claims_total"], 0)
        self.assertEqual(result["citation_stats"]["claims_with_trace"], 0)
        self.assertEqual(result["citation_stats"]["uncertainty_markers"], 0)
        self.assertEqual(result["citation_eligibility_violations"], [])
        self.assertEqual(result["glossary_inconsistencies"], [])

    # ── Test 14: output schema version pin + checked_at format ──
    def test_14_schema_version_and_checked_at(self):
        p = self._write_summary("# t\n")
        result = lint_summary(p)
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["schema_version"], 1)
        self.assertIsInstance(result["summary_path"], str)
        self.assertIsInstance(result["checked_at"], str)
        # ISO-8601 with T and Z
        self.assertIn("T", result["checked_at"])
        self.assertTrue(result["checked_at"].endswith("Z"),
                        f"checked_at should end with Z, got {result['checked_at']!r}")
        # LINT_FILENAME constant is exported
        self.assertEqual(LINT_FILENAME, "summary_lint.json")

    # ── Test 15 (bonus): UTF-8 CJK round-trip ──
    def test_15_utf8_cjk_roundtrip(self):
        body = (
            "## 一、章节\n"
            "\n"
            "[00:01:23] **你打开 settings.json**：本段含中文 + emoji 表情符 [seg_0001_000005.jpg @ 00:01:23]。\n"
        )
        p = self._write_summary(body)
        result = lint_summary(p)
        # Should not crash on multi-byte characters
        self.assertIsInstance(result["summary_path"], str)
        # The body line is well-formed → no violations
        for inv in result["format_invariants"].values():
            self.assertEqual(inv["violations"], [])


if __name__ == "__main__":
    unittest.main()
