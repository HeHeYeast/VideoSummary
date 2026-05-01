"""Tests for agent/state.py — Phase 2 reducer + Phase 4 D-14 segment-level extension.

Tests A..G mirror the PLAN.md task 2 <behavior> block 1:1.

Uses stdlib unittest (pytest is not in the project's default deps; Phase 2
RESEARCH precedent for stdlib-only tests).
"""
from __future__ import annotations

import unittest

from agent.state import derived_segment_state, derived_state


class TestDerivedSegmentState(unittest.TestCase):
    """Phase 4 D-14 落地 — segment-level resume reducer."""

    def test_A_basic_completed(self):
        events = [
            {"stage": "extract_frames_batch", "status": "completed",
             "details": {"segment_index": 0}},
            {"stage": "extract_frames_batch", "status": "completed",
             "details": {"segment_index": 2}},
        ]
        self.assertEqual(
            derived_segment_state(events, stage="extract_frames_batch"),
            {0, 2},
        )

    def test_B_failed_after_completed_drops_index(self):
        events = [
            {"stage": "extract_frames_batch", "status": "completed",
             "details": {"segment_index": 0}},
            {"stage": "extract_frames_batch", "status": "failed",
             "details": {"segment_index": 0}},
        ]
        self.assertEqual(
            derived_segment_state(events, stage="extract_frames_batch"),
            set(),
        )

    def test_C_completed_after_failed_re_includes(self):
        events = [
            {"stage": "extract_frames_batch", "status": "failed",
             "details": {"segment_index": 0}},
            {"stage": "extract_frames_batch", "status": "completed",
             "details": {"segment_index": 0}},
        ]
        self.assertEqual(
            derived_segment_state(events, stage="extract_frames_batch"),
            {0},
        )

    def test_D_started_without_completed_not_included(self):
        events = [
            {"stage": "extract_frames_batch", "status": "started",
             "details": {"segment_index": 5}},
        ]
        self.assertEqual(
            derived_segment_state(events, stage="extract_frames_batch"),
            set(),
        )

    def test_E_different_stage_filtered_out(self):
        events = [
            {"stage": "transcribe", "status": "completed",
             "details": {"segment_index": 0}},
        ]
        self.assertEqual(
            derived_segment_state(events, stage="extract_frames_batch"),
            set(),
        )

    def test_F_missing_details_segment_index_ignored(self):
        events = [
            {"stage": "extract_frames_batch", "status": "completed"},
            {"stage": "extract_frames_batch", "status": "completed",
             "details": {}},
            {"stage": "extract_frames_batch", "status": "completed",
             "details": {"segment_index": None}},
        ]
        self.assertEqual(
            derived_segment_state(events, stage="extract_frames_batch"),
            set(),
        )


class TestDerivedStateRegression(unittest.TestCase):
    """Test G: existing derived_state shape unchanged."""

    def test_G_existing_derived_state_unchanged(self):
        events = [
            {"ts": "2026-05-01T00:00:00Z", "stage": "transcribe",
             "status": "started", "params_hash": "abc"},
            {"ts": "2026-05-01T00:00:01Z", "stage": "transcribe",
             "status": "completed", "params_hash": "abc"},
            {"ts": "2026-05-01T00:00:02Z", "stage": "aggregate",
             "status": "started", "params_hash": "def"},
        ]
        state = derived_state(events)

        # Shape contract: dict mapping stage_name -> {status, last_completed_at, params_hash}
        self.assertIn("transcribe", state)
        self.assertIn("aggregate", state)
        self.assertEqual(state["transcribe"]["status"], "completed")
        self.assertEqual(state["transcribe"]["last_completed_at"], "2026-05-01T00:00:01Z")
        self.assertEqual(state["transcribe"]["params_hash"], "abc")
        self.assertEqual(state["aggregate"]["status"], "started")
        self.assertIsNone(state["aggregate"]["last_completed_at"])
        self.assertEqual(state["aggregate"]["params_hash"], "def")

        # Ensure shape keys are exactly the documented set (no leakage of
        # segment-level keys into stage-level reducer).
        self.assertEqual(
            set(state["transcribe"].keys()),
            {"status", "last_completed_at", "params_hash"},
        )


if __name__ == "__main__":
    unittest.main()
