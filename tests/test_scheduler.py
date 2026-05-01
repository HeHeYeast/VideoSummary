"""Tests for agent/scheduler.py — Phase 4 FPS-01/02/04.

Uses stdlib unittest (pytest is not in the project's default deps; Phase 2
RESEARCH precedent for stdlib-only tests).

Tests 1..13 mirror the PLAN.md task 1 <behavior> block 1:1.
"""
from __future__ import annotations

import json
import logging
import tempfile
import unittest
from pathlib import Path

from agent.scheduler import (
    Schedule,
    Segment,
    ScheduleValidationError,
    _interval_covered,
)


def _write_schedule(tmp_dir: Path, obj: dict) -> Path:
    p = tmp_dir / "schedule.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def _baseline_schedule(duration_s: float = 600.0) -> dict:
    """A trivially-valid schedule with one baseline-pass segment covering full video."""
    return {
        "version": 1,
        "video": "video.mp4",
        "default_scale": "854:-1",
        "default_quality": 4,
        "segments": [
            {"start": 0, "end": duration_s, "fps": 0.05, "label": "baseline"},
        ],
    }


class TestScheduleParseAndRoundtrip(unittest.TestCase):
    """Test 1: from_json + to_json roundtrip."""

    def test_roundtrip_preserves_segments_and_top_level(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            obj = _baseline_schedule(600.0)
            obj["segments"] = [
                {"start": 0, "end": 30, "fps": 0.2, "label": "intro"},
                {"start": 30, "end": 240, "fps": 0.4, "label": "code-demo-part1"},
                {"start": 240, "end": 245, "skip": True, "label": "filler"},
                {"start": 245, "end": 600, "fps": 0.3, "label": "code-demo-part2"},
            ]
            in_path = _write_schedule(tmp, obj)
            sched = Schedule.from_json(in_path)
            out_path = tmp / "schedule_out.json"
            sched.to_json(out_path)

            reparsed = Schedule.from_json(out_path)
            self.assertEqual(reparsed.version, sched.version)
            self.assertEqual(reparsed.video, sched.video)
            self.assertEqual(reparsed.default_scale, sched.default_scale)
            self.assertEqual(reparsed.default_quality, sched.default_quality)
            self.assertEqual(len(reparsed.segments), len(sched.segments))
            for a, b in zip(reparsed.segments, sched.segments):
                self.assertEqual(a.start, b.start)
                self.assertEqual(a.end, b.end)
                self.assertEqual(a.fps, b.fps)
                self.assertEqual(a.skip, b.skip)
                self.assertEqual(a.label, b.label)


class TestValidateMandatoryChecks(unittest.TestCase):
    """Tests 2..9: 5 D-05 mandatory checks."""

    def test_2_unsupported_version(self):
        with tempfile.TemporaryDirectory() as td:
            obj = _baseline_schedule()
            obj["version"] = 2
            p = _write_schedule(Path(td), obj)
            sched = Schedule.from_json(p)
            with self.assertRaisesRegex(ScheduleValidationError, "unsupported schedule version"):
                sched.validate(duration_s=600.0)

    def test_3_unknown_top_level_key(self):
        with tempfile.TemporaryDirectory() as td:
            obj = _baseline_schedule()
            obj["foo"] = 1
            p = _write_schedule(Path(td), obj)
            with self.assertRaisesRegex(ScheduleValidationError, r"unknown top-level keys.*foo"):
                Schedule.from_json(p)

    def test_4_unknown_per_segment_key(self):
        with tempfile.TemporaryDirectory() as td:
            obj = _baseline_schedule()
            obj["segments"][0]["bogus"] = 1
            p = _write_schedule(Path(td), obj)
            with self.assertRaisesRegex(
                ScheduleValidationError, r"segment 0: unknown keys.*bogus"
            ):
                Schedule.from_json(p)

    def test_5_fps_xor_skip(self):
        # 5a: both fps + skip:true
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[Segment(start=0, end=600, fps=0.05, skip=True)],
        )
        with self.assertRaisesRegex(ScheduleValidationError, r"fps.*skip"):
            sched.validate(duration_s=600.0)

        # 5b: neither fps nor skip
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[Segment(start=0, end=600)],  # fps=None, skip=False
        )
        with self.assertRaisesRegex(ScheduleValidationError, r"fps.*skip"):
            sched.validate(duration_s=600.0)

        # 5c: skip:1 (int not bool) — rejected at parse time
        with tempfile.TemporaryDirectory() as td:
            obj = _baseline_schedule()
            obj["segments"][0] = {"start": 0, "end": 600, "skip": 1}
            p = _write_schedule(Path(td), obj)
            with self.assertRaisesRegex(ScheduleValidationError, r"skip.*boolean"):
                Schedule.from_json(p)

        # 5d: skip:"true" (string) — rejected at parse time
        with tempfile.TemporaryDirectory() as td:
            obj = _baseline_schedule()
            obj["segments"][0] = {"start": 0, "end": 600, "skip": "true"}
            p = _write_schedule(Path(td), obj)
            with self.assertRaisesRegex(ScheduleValidationError, r"skip.*boolean"):
                Schedule.from_json(p)

    def test_6_first_start_too_large(self):
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[Segment(start=3.0, end=600, fps=0.05)],
        )
        with self.assertRaisesRegex(ScheduleValidationError, r"first segment must start"):
            sched.validate(duration_s=600.0)

    def test_7_last_end_too_small(self):
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[Segment(start=0, end=50, fps=0.05)],
        )
        with self.assertRaisesRegex(ScheduleValidationError, r"last segment must end"):
            sched.validate(duration_s=60.0)

    def test_8_within_tolerance_passes(self):
        # first.start = 1.5 (within 2s); last.end = duration - 1.5 (within 2s);
        # plus a baseline pass so silence-coverage degraded mode passes.
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[Segment(start=1.5, end=58.5, fps=0.05, label="baseline")],
        )
        # Should not raise (silence_map=None falls into D-08 fallback; baseline
        # pass present).
        sched.validate(duration_s=60.0)

    def test_9_overlap_and_gap(self):
        # 9a: overlap (prev.end > curr.start)
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[
                Segment(start=0, end=30, fps=0.05),
                Segment(start=29, end=60, fps=0.2),
            ],
        )
        with self.assertRaisesRegex(ScheduleValidationError, r"overlap"):
            sched.validate(duration_s=60.0)

        # 9b: gap (prev.end < curr.start)
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[
                Segment(start=0, end=30, fps=0.05),
                Segment(start=31, end=60, fps=0.2),
            ],
        )
        with self.assertRaisesRegex(ScheduleValidationError, r"gap"):
            sched.validate(duration_s=60.0)


class TestSilenceCoverageFPS04(unittest.TestCase):
    """Tests 10..13: D-07/D-08 silence-coverage strict-OR-fallback."""

    def test_10_baseline_pass_silence_map_none_passes_with_warning(self):
        # Single segment covering whole video at fps <= 0.1 ⇒ baseline pass.
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[Segment(start=0, end=600, fps=0.05)],
        )
        with self.assertLogs("agent.scheduler", level="WARNING") as cm:
            sched.validate(duration_s=600.0, silence_map=None)
        joined = "\n".join(cm.output)
        # Locked warning string from D-08
        self.assertIn("silence_map.json not found", joined)
        self.assertIn("baseline-pass requirement only", joined)

    def test_11_no_baseline_pass_no_silence_map_raises(self):
        # All fps > 0.1, no full-coverage low-fps pass ⇒ raise D-08.
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[
                Segment(start=0, end=300, fps=0.3),
                Segment(start=300, end=600, fps=0.5),
            ],
        )
        with self.assertRaisesRegex(
            ScheduleValidationError,
            r"FPS-04: no silence_map\.json found, baseline pass missing",
        ):
            sched.validate(duration_s=600.0, silence_map=None)

    def test_12_silence_map_partial_coverage_raises(self):
        # silence_map flagged interval [100,110]; segments [(0,80,0.2),(80,105,0.3),
        # (105,200,skip=True)] — only [100,105] covered ⇒ raise.
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[
                Segment(start=0, end=80, fps=0.2),
                Segment(start=80, end=105, fps=0.3),
                Segment(start=105, end=200, skip=True),
            ],
        )
        silence_map = {
            "version": 1,
            "video": "v",
            "silence_intervals": [
                {"start": 100, "end": 110, "duration": 10, "flagged_for_review": True},
            ],
        }
        with self.assertRaisesRegex(
            ScheduleValidationError, r"FPS-04: silence interval"
        ):
            sched.validate(duration_s=200.0, silence_map=silence_map)

    def test_13_silence_map_full_coverage_passes(self):
        # Same silence_map; segments [(0,80,0.2),(80,200,0.3)] — covers [100,110]
        # via [80,200] ⇒ passes (no baseline pass needed).
        sched = Schedule(
            version=1, video="v", default_scale="854:-1", default_quality=4,
            segments=[
                Segment(start=0, end=80, fps=0.2),
                Segment(start=80, end=200, fps=0.3),
            ],
        )
        silence_map = {
            "version": 1,
            "video": "v",
            "silence_intervals": [
                {"start": 100, "end": 110, "duration": 10, "flagged_for_review": True},
            ],
        }
        sched.validate(duration_s=200.0, silence_map=silence_map)  # no raise


class TestIntervalCoveredHelper(unittest.TestCase):
    """Sanity check the set-theoretic helper directly."""

    def test_covered_fully(self):
        segs = [Segment(start=0, end=200, fps=0.3)]
        self.assertTrue(_interval_covered(100, 110, segs))

    def test_partial_left_gap(self):
        segs = [Segment(start=105, end=200, fps=0.3)]
        self.assertFalse(_interval_covered(100, 110, segs))

    def test_partial_right_gap(self):
        segs = [Segment(start=80, end=105, fps=0.3)]
        self.assertFalse(_interval_covered(100, 110, segs))

    def test_no_overlap_at_all(self):
        segs = [Segment(start=0, end=80, fps=0.3)]
        self.assertFalse(_interval_covered(100, 110, segs))

    def test_union_of_two_segments_covers(self):
        # Adjacent segments both not-skip ⇒ union covers
        segs = [
            Segment(start=80, end=105, fps=0.3),
            Segment(start=105, end=200, fps=0.4),
        ]
        self.assertTrue(_interval_covered(100, 110, segs))


if __name__ == "__main__":
    unittest.main()
