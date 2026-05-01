"""Tests for whisper_repetition_guard — Phase 5 TEACH-11 / D-22..D-25 + REVIEW WR-02.

Tests cover both detector branches:
  - consecutive run-length (D-22 字面: '啊啊啊啊')
  - density-based phrase-repeat (REVIEW WR-02: '我们这里用我们这里用...')

D-24 redline preservation (input list never mutated) is asserted directly.

Stdlib unittest only (no pytest dep — Phase 2 RESEARCH stdlib-only test precedent).
"""
from __future__ import annotations

import copy
import unittest

from agent.tools import (
    _count_consecutive_trigrams,
    _count_repeated_trigrams,
    _density_hit,
    whisper_repetition_guard,
)


class TestConsecutiveDetector(unittest.TestCase):
    """字符级连续 run-length 检测 (D-22 字面)."""

    def test_char_pad_run_detected(self):
        runs = _count_consecutive_trigrams("啊" * 10)
        self.assertGreater(runs.get("啊啊啊", 0), 3)

    def test_natural_text_no_long_run(self):
        runs = _count_consecutive_trigrams("今天天气真好我们去公园散步")
        self.assertTrue(all(r <= 1 for r in runs.values()))

    def test_short_text_returns_empty(self):
        self.assertEqual(_count_consecutive_trigrams("ab"), {})
        self.assertEqual(_count_consecutive_trigrams(""), {})


class TestDensityDetector(unittest.TestCase):
    """REVIEW WR-02: phrase-level repeat catch via density."""

    def test_phrase_repeat_canonical_case_fires(self):
        # The literal docstring example from D-22.
        text = "我们这里用" * 5
        hit = _density_hit(text)
        self.assertIsNotNone(hit, "D-22 docstring case must trigger after WR-02 fix")
        gram, count = hit
        self.assertEqual(count, 5)

    def test_haha_phrase_repeat_fires(self):
        hit = _density_hit("haha haha haha haha haha")
        self.assertIsNotNone(hit)

    def test_natural_language_no_false_fire(self):
        text = "今天天气真好我们去公园散步吧昨晚我读了一本书觉得非常有意思"
        self.assertIsNone(_density_hit(text))

    def test_below_min_count_no_fire(self):
        # count=3 is below _DENSITY_MIN_COUNT=4
        text = "abcabcabc"
        hit = _density_hit(text)
        # 'abc' count=3 < 4 → must NOT fire
        self.assertIsNone(hit)

    def test_short_text_no_crash(self):
        self.assertIsNone(_density_hit(""))
        self.assertIsNone(_density_hit("ab"))


class TestWhisperRepetitionGuard(unittest.TestCase):
    """End-to-end guard behavior."""

    def test_phrase_repeat_in_single_segment_warned(self):
        segs = [
            {"start": 10.0, "end": 12.0, "text": "今天我们来讨论这个新功能"},
            {"start": 12.0, "end": 18.0, "text": "我们这里用" * 4},
            {"start": 18.0, "end": 21.0, "text": "所以这个就是这样的"},
        ]
        warnings = whisper_repetition_guard(segs)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["seg_indices"], [1])
        self.assertEqual(warnings[0]["trigram"], "我们这")

    def test_char_pad_in_single_segment_warned(self):
        segs = [{"start": 0.0, "end": 5.0, "text": "啊" * 20}]
        warnings = whisper_repetition_guard(segs)
        self.assertGreaterEqual(len(warnings), 1)

    def test_natural_language_no_warnings(self):
        segs = [
            {"start": 0.0, "end": 3.0, "text": "今天天气真好"},
            {"start": 3.0, "end": 6.0, "text": "我们去公园散步吧"},
            {"start": 6.0, "end": 10.0, "text": "昨晚我读了一本书觉得很有意思"},
        ]
        self.assertEqual(whisper_repetition_guard(segs), [])

    def test_d24_input_not_mutated(self):
        """D-24 redline: guard must NEVER mutate input segs list."""
        segs = [
            {"start": 0.0, "end": 5.0, "text": "我们这里用" * 5},
            {"start": 5.0, "end": 8.0, "text": "正常文本内容"},
        ]
        snapshot = copy.deepcopy(segs)
        _ = whisper_repetition_guard(segs)
        self.assertEqual(segs, snapshot, "D-24: input segs mutated by guard")

    def test_empty_input_no_crash(self):
        self.assertEqual(whisper_repetition_guard([]), [])

    def test_short_text_no_crash(self):
        segs = [{"start": 0.0, "end": 1.0, "text": "ab"}]
        self.assertEqual(whisper_repetition_guard(segs), [])

    def test_warning_schema_d23(self):
        """D-23 schema: each warning has required fields."""
        segs = [{"start": 0.0, "end": 5.0, "text": "我们这里用" * 5}]
        warnings = whisper_repetition_guard(segs)
        self.assertGreaterEqual(len(warnings), 1)
        w = warnings[0]
        for field in ("start", "end", "trigram", "count",
                      "context_before", "context_after", "seg_indices"):
            self.assertIn(field, w, f"D-23 schema field {field!r} missing")


if __name__ == "__main__":
    unittest.main()
