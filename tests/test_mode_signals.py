"""Unit tests for agent/mode_signals.py (Phase 07 TOOL-A).

10 tests (M1..M10) — verify schema, K5 boundary (no recommended_mode),
and the 5 signals' counting logic.
"""
from __future__ import annotations

import hashlib
import json
import unittest

from agent.mode_signals import compute_signals, SIGNALS_FILENAME, _hash_paragraphs


class TestModeSignals(unittest.TestCase):
    """10 tests covering the 5 mode-classification signals."""

    def test_M1_returns_dict_with_5_signal_keys(self):
        """M1: compute_signals returns dict with the 5 expected signal keys."""
        result = compute_signals([{"text": "hello"}])
        expected = {
            "code_fence_density",
            "step_marker_density",
            "question_form_ratio",
            "speaker_turn_signals",
            "cross_tool_comparison_count",
        }
        self.assertEqual(set(result.keys()), expected)

    def test_M2_no_recommended_mode_field(self):
        """M2: K5 boundary — output MUST NOT contain `recommended_mode`."""
        result = compute_signals([{"text": "代码很多 ```python ``` ```js ```"}])
        self.assertNotIn("recommended_mode", result)
        self.assertNotIn("suggested_primary", result)
        self.assertNotIn("primary_mode", result)

    def test_M3_code_fence_density(self):
        """M3: code_fence_density.raw_count counts triple-backtick fences across paragraphs."""
        paragraphs = [
            {"text": "intro text"},
            {"text": "see this ```python\nprint('x')\n``` example"},
            {"text": "another ```js\nfoo\n``` and ```text\nbar\n```"},
        ]
        result = compute_signals(paragraphs)
        # 1 fence in para 1, 2 fences (```js, ```text) in para 2 = 3 total
        # Note: closing ``` without lang is a separate fence too — let's count exactly
        # ```python is 1, the closing ``` is 1, ```js is 1, closing ``` is 1, ```text is 1, closing ``` is 1
        # Actually the regex r"```\w*" matches both opening and closing
        # opening: ```python, ```js, ```text (3 with language)
        # closing: ``` ``` ``` (3 without language but matches \w* with empty)
        # so total = 6
        self.assertGreaterEqual(result["code_fence_density"]["raw_count"], 3)
        self.assertEqual(
            round(result["code_fence_density"]["per_paragraph"], 4),
            round(result["code_fence_density"]["raw_count"] / len(paragraphs), 4),
        )
        # evidence_paragraphs should include indices 1 and 2
        self.assertIn(1, result["code_fence_density"]["evidence_paragraphs"])
        self.assertIn(2, result["code_fence_density"]["evidence_paragraphs"])

    def test_M4_step_marker_density(self):
        """M4: step_marker matches 第N步 / 步骤N / Step N."""
        paragraphs = [
            {"text": "第一步 我们开始"},
            {"text": "步骤 2: 配置"},
            {"text": "Step 3 finalize"},
            {"text": "no markers here"},
        ]
        result = compute_signals(paragraphs)
        self.assertGreaterEqual(result["step_marker_density"]["raw_count"], 3)
        # 3 markers / 4 paragraphs = 0.75
        self.assertAlmostEqual(result["step_marker_density"]["per_paragraph"], 0.75, places=2)

    def test_M5_question_form_ratio(self):
        """M5: question_form counts ？ + ? characters."""
        paragraphs = [
            {"text": "为什么这样？因为如此。"},
            {"text": "How does it work? It works."},
            {"text": "no questions here."},
        ]
        result = compute_signals(paragraphs)
        # 1 ？+ 1 ? = 2 questions
        self.assertEqual(result["question_form_ratio"]["raw_count"], 2)
        # sentences_total — 4 sentences across 3 paragraphs (split by 。?！)
        self.assertGreater(result["question_form_ratio"]["sentences_total"], 0)

    def test_M6_speaker_turn_signals(self):
        """M6: intro_phrase_count matches 今天嘉宾 / 今天请到 / 有请 / 你怎么看 / 你认为."""
        paragraphs = [
            {"text": "今天嘉宾是 Karpathy"},
            {"text": "你怎么看 ECS 这件事？"},
            {"text": "正常段落"},
        ]
        result = compute_signals(paragraphs)
        self.assertEqual(result["speaker_turn_signals"]["intro_phrase_count"], 2)
        self.assertEqual(set(result["speaker_turn_signals"]["evidence_paragraphs"]), {0, 1})

    def test_M7_cross_tool_comparison_count(self):
        """M7: cross_tool counts vs / 对比 / 相比 / 区别."""
        paragraphs = [
            {"text": "Vue vs React"},
            {"text": "对比一下两者"},
            {"text": "相比之下，方法 B 更快"},
            {"text": "正常段落"},
        ]
        result = compute_signals(paragraphs)
        self.assertEqual(result["cross_tool_comparison_count"]["count"], 3)

    def test_M8_evidence_paragraphs_capped(self):
        """M8: evidence_paragraphs list is capped at 5 examples per signal."""
        # 10 paragraphs all with code fence -> only 5 indices in evidence
        paragraphs = [{"text": "```python\npass\n```"} for _ in range(10)]
        result = compute_signals(paragraphs)
        self.assertEqual(len(result["code_fence_density"]["evidence_paragraphs"]), 5)
        # And they should be the FIRST 5 (indices 0..4)
        self.assertEqual(result["code_fence_density"]["evidence_paragraphs"], [0, 1, 2, 3, 4])

    def test_M9_empty_paragraphs_no_crash(self):
        """M9: empty paragraphs -> all densities 0.0, all evidence empty, no crash."""
        result = compute_signals([])
        self.assertEqual(result["code_fence_density"]["per_paragraph"], 0.0)
        self.assertEqual(result["step_marker_density"]["per_paragraph"], 0.0)
        self.assertEqual(result["question_form_ratio"]["per_paragraph"], 0.0)
        self.assertEqual(result["speaker_turn_signals"]["intro_phrase_count"], 0)
        self.assertEqual(result["cross_tool_comparison_count"]["count"], 0)
        for key in result:
            ev = result[key].get("evidence_paragraphs", [])
            self.assertEqual(ev, [])

    def test_M10_paragraphs_hash_helper(self):
        """M10: _hash_paragraphs returns sha256 first 16 hex chars of paragraphs JSON dump."""
        paragraphs = [{"text": "hello"}, {"text": "world"}]
        h = _hash_paragraphs(paragraphs)
        self.assertEqual(len(h), 16)
        # Verify deterministic
        self.assertEqual(h, _hash_paragraphs(paragraphs))
        # Verify changes when content changes
        self.assertNotEqual(h, _hash_paragraphs([{"text": "hello"}]))
        # Verify it's a hex string
        self.assertTrue(all(c in "0123456789abcdef" for c in h))
        # Also check SIGNALS_FILENAME constant
        self.assertEqual(SIGNALS_FILENAME, "mode_signals.json")


if __name__ == "__main__":
    unittest.main()
