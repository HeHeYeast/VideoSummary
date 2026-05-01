"""Tests for cmd_extract_frames_batch — Phase 4 FPS-01/02/03/04 + K5 enforcement.

Tests 1..10 mirror PLAN.md Task 3 <behavior> block. Uses stdlib unittest +
unittest.mock to avoid pytest dependency.
"""
from __future__ import annotations

import inspect
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import agent.tools as tools_mod
from agent.tools import cmd_extract_frames_batch


def _baseline_schedule_obj(duration_s: float = 600.0) -> dict:
    """A trivially-valid schedule covering full video at fps=0.05 (baseline pass)."""
    return {
        "version": 1,
        "video": "video.mp4",
        "default_scale": "854:-1",
        "default_quality": 4,
        "segments": [
            {"start": 0, "end": duration_s, "fps": 0.05, "label": "baseline"},
        ],
    }


def _write_schedule(slug_dir: Path, obj: dict) -> Path:
    p = slug_dir / "schedule.json"
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def _make_args(slug_dir: Path, *, force: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        schedule=str(slug_dir / "schedule.json"),
        out=str(slug_dir / "frames"),
        force=force,
    )


def _ascii_tmpdir_root() -> str:
    """Return an ASCII-only directory for tempfile.TemporaryDirectory.

    On zh-CN Windows the default %USERPROFILE%/AppData/Local/Temp resolves to
    a path containing the user's CJK username (e.g., '管啸野'), which trips
    cmd_extract_frames_batch's _validate_out_path CJK rejection. Pick an
    ASCII-safe location: project's own tests/ (always ASCII because the repo
    is under D:/gxy_code/...).
    """
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_batch"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


class _BatchTestBase(unittest.TestCase):
    """Common setUp: a tmp slug dir with a `video.mp4` placeholder + schedule."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.slug_dir = Path(self._td.name) / "BVtest"
        self.slug_dir.mkdir(parents=True)
        # video.mp4 placeholder (ffprobe is mocked, so file content doesn't matter,
        # but the file must exist for path resolution).
        (self.slug_dir / "video.mp4").write_bytes(b"fake-mp4-for-tests")

    def tearDown(self):
        self._td.cleanup()

    def _patch_ffprobe(self, duration_s: float = 600.0):
        """Patch agent.sources._common.ffprobe_video to return a canned probe.

        Patch must target the import site (sources._common.ffprobe_video) since
        cmd_extract_frames_batch does an import-inside-function from there.
        """
        return patch(
            "agent.sources._common.ffprobe_video",
            return_value={
                "codec": "h264", "container": "mp4",
                "has_audio": True, "fps_mode": "CFR",
                "width": 1280, "height": 720,
                "duration_s": duration_s,
            },
        )


class TestValidationGate(_BatchTestBase):
    """Test 1: validation fires before any ffmpeg subprocess."""

    def test_1_validation_gate_blocks_ffmpeg(self):
        # Overlapping segments — fails D-05.3
        bad = _baseline_schedule_obj(60.0)
        bad["segments"] = [
            {"start": 0, "end": 30, "fps": 0.2},
            {"start": 29, "end": 60, "fps": 0.3},  # overlap
        ]
        _write_schedule(self.slug_dir, bad)

        with self._patch_ffprobe(60.0), \
             patch("subprocess.run") as mock_run:
            from agent.scheduler import ScheduleValidationError
            with self.assertRaises(ScheduleValidationError):
                cmd_extract_frames_batch(_make_args(self.slug_dir))
            self.assertEqual(mock_run.call_count, 0,
                             "ffmpeg subprocess called before validation rejected schedule")


class TestResume(_BatchTestBase):
    """Tests 2 + 3: segment-level resume via state.jsonl."""

    def _write_state_with_segment_completed(self, *segment_indices):
        """Write state.jsonl with completed events for given segment_indices."""
        log_path = self.slug_dir / "state.jsonl"
        with open(log_path, "a", encoding="utf-8") as f:
            for idx in segment_indices:
                f.write(json.dumps({
                    "ts": "2026-05-01T00:00:00+00:00",
                    "stage": "extract_frames_batch",
                    "status": "completed",
                    "params_hash": "",
                    "details": {"segment_index": idx, "start": 0, "end": 100,
                                "frames_count": 5},
                }) + "\n")

    def _three_segment_schedule(self):
        sched = _baseline_schedule_obj(300.0)
        sched["segments"] = [
            {"start": 0, "end": 100, "fps": 0.05, "label": "baseline-part-A"},
            {"start": 100, "end": 200, "fps": 0.2, "label": "code"},
            {"start": 200, "end": 300, "fps": 0.3, "label": "demo"},
        ]
        # Add baseline pass covering full duration
        sched["segments"] = [
            {"start": 0, "end": 300, "fps": 0.05, "label": "baseline"},
        ]
        return sched

    def test_2_resume_skips_completed(self):
        # 3 fps segments; pre-mark segment 0 completed.
        sched = _baseline_schedule_obj(300.0)
        # Need a baseline pass for FPS-04 to pass — make one segment fps=0.05 covering all
        # Then split via additional segments? No — D-05.3 requires no overlap. Use
        # ALL fps≤0.1 to satisfy baseline, but 3 segments to test resume.
        sched["segments"] = [
            {"start": 0, "end": 100, "fps": 0.05},
            {"start": 100, "end": 200, "fps": 0.05},
            {"start": 200, "end": 300, "fps": 0.05},
        ]
        # Note: baseline pass requires ONE segment spanning full duration.
        # Workaround: keep one-segment schedule but test resume differently.
        sched["segments"] = [
            {"start": 0, "end": 300, "fps": 0.05},
        ]
        _write_schedule(self.slug_dir, sched)
        # Pre-mark segment 0 completed in state.jsonl
        self._write_state_with_segment_completed(0)

        with self._patch_ffprobe(300.0), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            cmd_extract_frames_batch(_make_args(self.slug_dir, force=False))
            # Single segment was already completed → ffmpeg should NOT run.
            self.assertEqual(mock_run.call_count, 0,
                             "ffmpeg ran for already-completed segment")

    def test_3_force_bypasses_resume(self):
        sched = _baseline_schedule_obj(300.0)
        sched["segments"] = [{"start": 0, "end": 300, "fps": 0.05}]
        _write_schedule(self.slug_dir, sched)
        self._write_state_with_segment_completed(0)

        with self._patch_ffprobe(300.0), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            cmd_extract_frames_batch(_make_args(self.slug_dir, force=True))
            self.assertEqual(mock_run.call_count, 1,
                             "--force did not bypass resume")


class TestSkipSemantics(_BatchTestBase):
    """Test 4: skip-segment skipped without ffmpeg."""

    def test_4_skip_segment_does_not_run_ffmpeg(self):
        sched = _baseline_schedule_obj(300.0)
        # Baseline pass + one skip segment within bounds. D-05.3 requires
        # contiguous coverage — one continuous baseline can't have a skip
        # carved out without 3 segments. Use 3 segments where segment 1 is skip.
        # FPS-04 needs a baseline pass spanning the full video. Cover with
        # additional baseline-fps segments around the skip.
        sched["segments"] = [
            {"start": 0, "end": 100, "fps": 0.05},
            {"start": 100, "end": 105, "skip": True, "label": "filler"},
            {"start": 105, "end": 300, "fps": 0.05},
        ]
        # Note: this lacks a single baseline pass spanning [0, 300]. But
        # silence_map=None ⇒ D-08 fallback requires baseline pass. So we'll
        # need to provide a silence_map (empty silences) instead, OR use a
        # single segment that has skip but is impossible.
        # Simpler: provide an empty silence_map (no flagged intervals) — D-07
        # condition (b) trivially satisfied.
        _write_schedule(self.slug_dir, sched)
        (self.slug_dir / "silence_map.json").write_text(
            json.dumps({
                "version": 1, "video": "video.mp4",
                "silence_intervals": [],  # no flagged intervals
            }),
            encoding="utf-8",
        )

        with self._patch_ffprobe(300.0), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            cmd_extract_frames_batch(_make_args(self.slug_dir))
            # 3 segments, 2 fps + 1 skip → only 2 ffmpeg calls
            self.assertEqual(mock_run.call_count, 2,
                             f"expected 2 ffmpeg calls for 2 fps segments, "
                             f"got {mock_run.call_count}")

        # And state.jsonl should have a completed event for the skip segment
        # (segment_index=1) with skip=True in details
        log = (self.slug_dir / "state.jsonl").read_text(encoding="utf-8")
        events = [json.loads(line) for line in log.splitlines() if line.strip()]
        skip_completed = [
            e for e in events
            if e.get("stage") == "extract_frames_batch"
            and e.get("status") == "completed"
            and e.get("details", {}).get("segment_index") == 1
            and e.get("details", {}).get("skip") is True
        ]
        self.assertEqual(
            len(skip_completed), 1,
            "skip segment did not emit a completed event with skip=True",
        )


class TestFailurePropagation(_BatchTestBase):
    """Test 5: per-segment failure raises and stops."""

    def test_5_failure_stops_subsequent_segments(self):
        sched = _baseline_schedule_obj(300.0)
        sched["segments"] = [
            {"start": 0, "end": 100, "fps": 0.05},
            {"start": 100, "end": 200, "fps": 0.05},
            {"start": 200, "end": 300, "fps": 0.05},
        ]
        _write_schedule(self.slug_dir, sched)
        # Provide silence_map with no flagged intervals so multi-segment passes
        (self.slug_dir / "silence_map.json").write_text(
            json.dumps({"version": 1, "video": "v", "silence_intervals": []}),
            encoding="utf-8",
        )

        # Mock ffmpeg: succeed on call 0, fail on call 1, never reach call 2
        call_log = []

        def fake_run(cmd, check=False, capture_output=False, **kwargs):
            call_log.append(cmd)
            if len(call_log) == 1:
                return MagicMock(returncode=0, stderr=b"")
            # Second call fails
            raise subprocess.CalledProcessError(
                returncode=1, cmd=cmd, stderr=b"fake ffmpeg error"
            )

        with self._patch_ffprobe(300.0), \
             patch("subprocess.run", side_effect=fake_run) as mock_run:
            with self.assertRaisesRegex(
                RuntimeError, r"extract_frames_batch segment 1 failed"
            ):
                cmd_extract_frames_batch(_make_args(self.slug_dir))
            # Ensure third segment was NOT attempted
            self.assertEqual(mock_run.call_count, 2,
                             "subsequent segment ran after failure")

        # And a failed event should be recorded for segment 1
        log = (self.slug_dir / "state.jsonl").read_text(encoding="utf-8")
        events = [json.loads(line) for line in log.splitlines() if line.strip()]
        failed = [
            e for e in events
            if e.get("status") == "failed"
            and e.get("details", {}).get("segment_index") == 1
        ]
        self.assertEqual(len(failed), 1,
                         "failed event for segment 1 missing from state.jsonl")


class TestEventDetailsShape(_BatchTestBase):
    """Test 6: completed event details contain segment_index, start, end, frames_count."""

    def test_6_event_details_shape(self):
        sched = _baseline_schedule_obj(300.0)
        sched["segments"] = [{"start": 0, "end": 300, "fps": 0.05}]
        _write_schedule(self.slug_dir, sched)

        with self._patch_ffprobe(300.0), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=b"")
            cmd_extract_frames_batch(_make_args(self.slug_dir))

        log = (self.slug_dir / "state.jsonl").read_text(encoding="utf-8")
        events = [json.loads(line) for line in log.splitlines() if line.strip()]
        completed = [
            e for e in events
            if e.get("stage") == "extract_frames_batch"
            and e.get("status") == "completed"
        ]
        self.assertEqual(len(completed), 1)
        d = completed[0].get("details", {})
        self.assertIn("segment_index", d)
        self.assertIn("start", d)
        self.assertIn("end", d)
        self.assertIn("frames_count", d)


class TestFilenameGrammar(_BatchTestBase):
    """Test 7: ffmpeg argv contains the seg_<int(start):04d>_%06d.jpg pattern."""

    def test_7_filename_grammar_preserved(self):
        sched = _baseline_schedule_obj(300.0)
        sched["segments"] = [{"start": 30, "end": 300, "fps": 0.05}]
        # We need the schedule to satisfy D-05.2 (first.start <= 2s)? start=30 fails.
        # Use a baseline that starts at 0 and satisfies first.start.
        sched["segments"] = [{"start": 0, "end": 300, "fps": 0.05}]
        _write_schedule(self.slug_dir, sched)

        argv_seen = []

        def fake_run(cmd, check=False, capture_output=False, **kwargs):
            argv_seen.append(cmd)
            return MagicMock(returncode=0, stderr=b"")

        with self._patch_ffprobe(300.0), \
             patch("subprocess.run", side_effect=fake_run):
            cmd_extract_frames_batch(_make_args(self.slug_dir))

        self.assertEqual(len(argv_seen), 1)
        argv = argv_seen[0]
        # Filename pattern: seg_<int(start):04d>_%06d.jpg → seg_0000_%06d.jpg
        joined = " ".join(str(x) for x in argv)
        self.assertIn("seg_0000_", joined,
                      f"filename grammar 'seg_<int(start):04d>_' not in argv: {argv}")
        self.assertIn("%06d.jpg", joined,
                      f"%06d.jpg pattern not in argv: {argv}")
        # -vsync vfr per Phase 3 D-23 grammar
        self.assertIn("vfr", argv)


class TestCJKRejection(_BatchTestBase):
    """Test 8: CJK in --out raises ValueError before schedule load."""

    def test_8_cjk_rejected(self):
        # Note: _BatchTestBase setUp uses ASCII tmpdir. Override args.out with CJK.
        sched = _baseline_schedule_obj(300.0)
        _write_schedule(self.slug_dir, sched)

        args = SimpleNamespace(
            schedule=str(self.slug_dir / "schedule.json"),
            out=str(self.slug_dir / "中文_frames"),  # CJK in path
            force=False,
        )
        with self.assertRaisesRegex(ValueError, r"CJK"):
            cmd_extract_frames_batch(args)


class TestRegisteredCommand(unittest.TestCase):
    """Test 9: cmd_extract_frames_batch is callable + accessible via module attribute."""

    def test_9_function_callable(self):
        self.assertTrue(callable(cmd_extract_frames_batch))
        # Argparse registration is verified by the `--help` invocation in the
        # outer test_*.py harness. Here we just assert importability.


class TestK5Boundary(unittest.TestCase):
    """Test 10: K5 enforcement — function source must not reference scenes/silence
    auto-promotion paths (locked at CONTEXT line 10)."""

    def test_10_no_scenes_module_in_source(self):
        src = inspect.getsource(cmd_extract_frames_batch)
        self.assertNotIn(
            "agent.scenes", src,
            "K5 violation: cmd_extract_frames_batch imports agent.scenes (auto-promotion forbidden)",
        )

    def test_10b_no_scenes_artifact_in_source(self):
        src = inspect.getsource(cmd_extract_frames_batch)
        self.assertNotIn(
            "scenes.json", src,
            "K5 violation: cmd_extract_frames_batch references scenes.json (auto-promotion forbidden)",
        )

    def test_10c_no_silence_module_in_source(self):
        src = inspect.getsource(cmd_extract_frames_batch)
        self.assertNotIn(
            "agent.silence", src,
            "K5 violation: cmd_extract_frames_batch imports agent.silence "
            "(silence_map.json read for validation only, not via that module)",
        )


if __name__ == "__main__":
    unittest.main()
