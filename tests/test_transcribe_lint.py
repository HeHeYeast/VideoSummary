"""Unit tests for agent/transcribe_lint.py (Phase 07 CORR-01a).

12 tests covering all 5 detection strategies + allowlist + schema.
Test 12 is the B1 fix proof: homophone_cluster fires on '训练' 8x + '迅练' 1x.
"""
from __future__ import annotations

import unittest

from agent.transcribe_lint import (
    detect_warnings,
    WARNINGS_FILENAME,
    ALLOWED_EVIDENCE_SOURCES,
)


def _make_seg(idx: int, text: str, start: float = 0.0, end: float = 5.0) -> dict:
    return {"id": idx, "start": start, "end": end, "text": text}


class TestTranscribeLint(unittest.TestCase):
    """L1 ASR suspect-token detector — 12 tests covering 5 strategies + allowlist."""

    def test_01_clean_chinese_text_no_warnings(self):
        """Test 1: pure Chinese text + numbers + punct → empty warnings list (P-01 false-positive guard)."""
        segs = [
            _make_seg(0, "你好这是一段测试。"),
            _make_seg(1, "今天天气很好，我们出去走走。"),
            _make_seg(2, "1234 加 5678 等于 6912。"),
        ]
        warnings = detect_warnings(segs, meta={})
        self.assertEqual(warnings, [], f"expected no warnings on clean text, got {warnings}")

    def test_02_hapax_latin_token_flagged(self):
        """Test 2: hapax-legomenon Latin token in CJK context → warning with hapax/mixed_script source."""
        segs = [_make_seg(0, "我用 Lora 训练")]
        warnings = detect_warnings(segs, meta={})
        self.assertTrue(len(warnings) >= 1, "expected at least one warning")
        self.assertEqual(warnings[0]["suspect_text"], "Lora")
        self.assertIn(warnings[0]["evidence_source"], {"hapax", "mixed_script"})

    def test_03_frequency_variance_flags_inconsistent_spelling(self):
        """Test 3: 'Lora' 5x + 'LoRA' 3x → frequency_variance with 'Lora' (the high-freq form) suggested."""
        segs = [
            _make_seg(0, "用 Lora 训练效果好"),
            _make_seg(1, "Lora 模型小"),
            _make_seg(2, "我喜欢 Lora 方法"),
            _make_seg(3, "Lora 很流行"),
            _make_seg(4, "Lora 是个好东西"),
            _make_seg(5, "用 LoRA 训练"),
            _make_seg(6, "LoRA 也行"),
            _make_seg(7, "LoRA 是缩写"),
        ]
        warnings = detect_warnings(segs, meta={})
        # Find any frequency_variance warning where suggested_text="Lora"
        fv = [w for w in warnings if w["evidence_source"] == "frequency_variance"]
        self.assertTrue(len(fv) >= 1, f"expected frequency_variance warning(s), got {warnings}")
        # Suggested text should be the higher-freq form (Lora)
        for w in fv:
            self.assertEqual(w["suggested_text"], "Lora",
                             f"suggested should be highest-freq form 'Lora', got {w['suggested_text']}")

    def test_04_title_token_cross_reference(self):
        """Test 4: meta title contains 'LoRA'; segs contain 'Lora' → title_token suggests 'LoRA'."""
        segs = [_make_seg(0, "我用 Lora 训练模型")]
        meta = {"title": "LoRA 训练教程"}
        warnings = detect_warnings(segs, meta=meta)
        title_w = [w for w in warnings if w["evidence_source"] == "title_token"]
        self.assertTrue(len(title_w) >= 1,
                        f"expected title_token warning, got {warnings}")
        self.assertEqual(title_w[0]["suspect_text"], "Lora")
        self.assertEqual(title_w[0]["suggested_text"], "LoRA")

    def test_05_pypinyin_import_works(self):
        """Test 5: from pypinyin import lazy_pinyin succeeds and produces a list."""
        from pypinyin import lazy_pinyin
        result = lazy_pinyin("LoRA")
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) >= 1)

    def test_06_stopwords_and_punct_never_flagged(self):
        """Test 6: ZH stopwords + numbers + punct never flagged regardless of frequency."""
        segs = [
            _make_seg(0, "你你你 我我我 这这这 那那那"),
            _make_seg(1, "1234 5678 !!! ???"),
            _make_seg(2, "你 1 我 2 这 3"),
        ]
        warnings = detect_warnings(segs, meta={})
        self.assertEqual(warnings, [],
                         f"expected no warnings on stopwords/punct, got {warnings}")

    def test_07_single_cjk_chars_never_flagged(self):
        """Test 7: single CJK chars never flagged (per PITFALLS P-01)."""
        segs = [
            _make_seg(0, "好 行 是 也 又 没"),
            _make_seg(1, "啊 呀 呢 吧 哦 嗯"),
        ]
        warnings = detect_warnings(segs, meta={})
        self.assertEqual(warnings, [],
                         f"single-char CJK should not be flagged, got {warnings}")

    def test_08_warning_schema_keys(self):
        """Test 8: every warning has required keys; confidence in [0.0, 1.0]."""
        segs = [_make_seg(0, "我用 Lora 训练")]
        warnings = detect_warnings(segs, meta={})
        self.assertTrue(len(warnings) >= 1)
        required_keys = {
            "para_id", "seg_index", "start", "end",
            "suspect_text", "suggested_text", "evidence_source",
            "confidence", "context_before", "context_after",
        }
        for w in warnings:
            self.assertTrue(required_keys.issubset(w.keys()),
                            f"missing keys: {required_keys - w.keys()}; warning={w}")
            self.assertGreaterEqual(w["confidence"], 0.0)
            self.assertLessEqual(w["confidence"], 1.0)
            # suggested_text may be empty string
            self.assertIsInstance(w["suggested_text"], str)

    def test_09_evidence_source_in_allowlist(self):
        """Test 9: every warning's evidence_source is one of ALLOWED_EVIDENCE_SOURCES."""
        # Construct segs that should trigger multiple strategies
        segs = [
            _make_seg(0, "我用 Lora 训练", start=0.0, end=2.0),
            _make_seg(1, "Lora 又 Lora", start=2.0, end=4.0),
            _make_seg(2, "今天讲解模型训练的基础", start=4.0, end=6.0),
            _make_seg(3, "你需要先准备训练数据", start=6.0, end=8.0),
            _make_seg(4, "我们用GPU加速训练", start=8.0, end=10.0),
            _make_seg(5, "训练完成后保存", start=10.0, end=12.0),
            _make_seg(6, "重新训练几小时", start=12.0, end=14.0),
            _make_seg(7, "训练参数关键", start=14.0, end=16.0),
            _make_seg(8, "增量训练节省时间", start=16.0, end=18.0),
            _make_seg(9, "完整训练到此", start=18.0, end=20.0),
            _make_seg(10, "迅练而不是别的", start=20.0, end=22.0),
        ]
        warnings = detect_warnings(segs, meta={"title": "LoRA 训练入门"})
        self.assertTrue(len(warnings) >= 1)
        for w in warnings:
            self.assertIn(w["evidence_source"], ALLOWED_EVIDENCE_SOURCES,
                          f"unknown evidence_source: {w['evidence_source']}")

    def test_10_empty_segs_no_crash(self):
        """Test 10: empty segs list → empty warnings list, no exception."""
        self.assertEqual(detect_warnings([], meta={}), [])
        self.assertEqual(detect_warnings([], meta=None), [])

    def test_11_warnings_filename_constant(self):
        """Test 11: WARNINGS_FILENAME == 'transcribe_warnings.json'."""
        self.assertEqual(WARNINGS_FILENAME, "transcribe_warnings.json")

    def test_12_homophone_cluster_pinyin_match(self):
        """B1 fix: prove pypinyin homophone_cluster strategy actually fires.

        Setup: '训练' appears 8 times (high-freq, correct spelling), '迅练' appears
        1 time (sparse, same pinyin 'xunlian', presumed ASR typo). The detector
        must emit a warning suggesting '训练' for '迅练'.

        Without this strategy, pypinyin would be dead weight in requirements.txt.
        """
        # Pre-load the homophone test data. 8 segs with '训练', 1 seg with '迅练'.
        _HOMOPHONE_TEST_DATA = [
            {"id": 0, "start": 0.0,  "end": 5.0,  "text": "今天讲解模型训练的基础"},
            {"id": 1, "start": 5.0,  "end": 10.0, "text": "你需要先准备训练数据"},
            {"id": 2, "start": 10.0, "end": 15.0, "text": "我们用GPU加速训练"},
            {"id": 3, "start": 15.0, "end": 20.0, "text": "训练完成后保存模型"},
            {"id": 4, "start": 20.0, "end": 25.0, "text": "重新训练通常需要几小时"},
            {"id": 5, "start": 25.0, "end": 30.0, "text": "训练参数包括learning rate"},
            {"id": 6, "start": 30.0, "end": 35.0, "text": "增量训练可以节省时间"},
            {"id": 7, "start": 35.0, "end": 40.0, "text": "完整训练流程到此结束"},
            # The suspect — same pinyin (xunlian), but only appears once
            {"id": 8, "start": 40.0, "end": 45.0, "text": "我刚才说的是迅练而不是别的"},
        ]
        warnings = detect_warnings(_HOMOPHONE_TEST_DATA, meta={})

        # Find the homophone_cluster warning for '迅练'
        homophone_warnings = [
            w for w in warnings
            if w["evidence_source"] == "homophone_cluster" and w["suspect_text"] == "迅练"
        ]
        self.assertEqual(
            len(homophone_warnings), 1,
            f"expected exactly 1 homophone_cluster warning for '迅练', got {len(homophone_warnings)}: "
            f"all warnings = {warnings}",
        )

        w = homophone_warnings[0]
        self.assertEqual(w["suggested_text"], "训练",
                         "suggested_text should be the high-freq same-pinyin candidate")
        self.assertEqual(w["evidence_source"], "homophone_cluster")
        self.assertAlmostEqual(w["confidence"], 0.65, places=2,
                               msg="locked confidence value for homophone_cluster")
        self.assertIn("evidence_detail", w,
                      "homophone_cluster warnings MUST include evidence_detail")
        self.assertIn("pinyin=xunlian", w["evidence_detail"],
                      "evidence_detail should contain pinyin signature")
        self.assertIn("candidate freq=8", w["evidence_detail"],
                      "evidence_detail should include the candidate's frequency")
        self.assertEqual(w["seg_index"], 8, "warning should locate the suspect at seg_idx 8")


if __name__ == "__main__":
    unittest.main()
