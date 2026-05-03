"""Unit tests for agent/schedule_suggestion.py (Phase 07 TOOL-B).

6 tests (S1..S6) — verify schema, mandatory FPS-04 baseline,
optional inputs degrade gracefully, K5 source-grep boundary.
"""
from __future__ import annotations

import inspect
import unittest
from pathlib import Path

import agent.schedule_suggestion as sched_mod
from agent.schedule_suggestion import compute_suggestion, SUGGESTION_FILENAME


class TestScheduleSuggestion(unittest.TestCase):
    """6 tests covering fps-segment suggestion + K5 boundary."""

    def test_S1_returns_locked_schema(self):
        """S1: compute_suggestion returns dict with required top-level keys."""
        result = compute_suggestion(
            paragraphs=[{"text": "intro"}],
            scenes=None,
            silence_map=None,
            duration_s=600.0,
            video_filename="x.mp4",
        )
        for key in ("version", "video", "duration_s", "suggested_segments", "suggestion_meta"):
            self.assertIn(key, result, f"missing top-level key {key}")
        self.assertEqual(result["version"], 1)
        self.assertEqual(result["video"], "x.mp4")
        self.assertEqual(result["duration_s"], 600.0)
        self.assertIsInstance(result["suggested_segments"], list)
        self.assertIsInstance(result["suggestion_meta"], dict)

    def test_S2_always_includes_fps_04_baseline(self):
        """S2: output ALWAYS contains a 'fps-04-baseline' segment with fps <= 0.1 covering full duration."""
        result = compute_suggestion(
            paragraphs=[],
            duration_s=300.0,
        )
        baselines = [
            s for s in result["suggested_segments"]
            if s.get("label") == "fps-04-baseline"
        ]
        self.assertEqual(len(baselines), 1, f"expected exactly 1 baseline segment, got {len(baselines)}")
        b = baselines[0]
        self.assertLessEqual(b["fps"], 0.1, "baseline fps must be <= 0.1 (FPS-04 enforced)")
        self.assertEqual(b["start"], 0.0)
        self.assertEqual(b["end"], 300.0, "baseline must cover full duration")

    def test_S3_silence_map_none_uses_silence_map_false(self):
        """S3: silence_map=None -> suggestion_meta.uses_silence_map=False; default + baseline still produced."""
        result = compute_suggestion(
            paragraphs=[],
            silence_map=None,
            duration_s=400.0,
        )
        self.assertFalse(result["suggestion_meta"]["uses_silence_map"])
        self.assertFalse(result["suggestion_meta"]["uses_scenes_json"])
        self.assertEqual(result["suggestion_meta"]["scene_cut_count"], 0)
        self.assertEqual(result["suggestion_meta"]["flagged_silences"], 0)
        # Should still have at least default-coverage + baseline
        labels = [s.get("label") for s in result["suggested_segments"]]
        self.assertIn("default-coverage", labels)
        self.assertIn("fps-04-baseline", labels)

    def test_S4_dense_cuts_trigger_high_fps_segment(self):
        """S4: when scenes has many cuts in a window, at least one segment has fps>=0.3 labeled 'code-demo'."""
        # 5 cuts in 0-60s window
        scenes = [
            {"start": 0.0, "end": 5.0},
            {"start": 10.0, "end": 15.0},
            {"start": 20.0, "end": 25.0},
            {"start": 30.0, "end": 35.0},
            {"start": 40.0, "end": 45.0},
        ]
        result = compute_suggestion(
            paragraphs=[],
            scenes=scenes,
            duration_s=600.0,
        )
        code_demo_segs = [
            s for s in result["suggested_segments"]
            if s.get("label") == "code-demo" and s.get("fps", 0) >= 0.3
        ]
        self.assertGreaterEqual(len(code_demo_segs), 1,
                                f"expected at least 1 code-demo segment with fps>=0.3, got {result['suggested_segments']}")
        self.assertTrue(result["suggestion_meta"]["uses_scenes_json"])
        self.assertEqual(result["suggestion_meta"]["scene_cut_count"], 5)

    def test_S5_flagged_silence_creates_low_fps_segment(self):
        """S5: silence_map flags > 5s span -> at least one segment covers it with fps <= 0.05."""
        silence_map = [
            {"start": 100.0, "end": 110.0, "flagged_for_review": True},
            {"start": 200.0, "end": 202.0, "flagged_for_review": False},
        ]
        result = compute_suggestion(
            paragraphs=[],
            silence_map=silence_map,
            duration_s=600.0,
        )
        talkthrough = [
            s for s in result["suggested_segments"]
            if s.get("label") == "talkthrough" and s.get("fps", 1.0) <= 0.05
        ]
        self.assertGreaterEqual(len(talkthrough), 1)
        # Verify it covers the flagged silence interval
        self.assertEqual(talkthrough[0]["start"], 100.0)
        self.assertEqual(talkthrough[0]["end"], 110.0)
        self.assertTrue(result["suggestion_meta"]["uses_silence_map"])
        self.assertEqual(result["suggestion_meta"]["flagged_silences"], 1)

    def test_S6_source_no_forbidden_literals_K5_boundary(self):
        """S6: source code MUST NOT contain literal 'schedule.json' / 'summary.md' / 'plan.md' (K5 boundary)."""
        src = Path(sched_mod.__file__).read_text(encoding="utf-8")
        for forbidden in ("schedule.json", "summary.md", "plan.md"):
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: agent/schedule_suggestion.py contains forbidden literal {forbidden!r}",
            )
        # Also assert the constant is the suggestion artifact name
        self.assertEqual(SUGGESTION_FILENAME, "schedule_suggestion.json")


if __name__ == "__main__":
    unittest.main()
