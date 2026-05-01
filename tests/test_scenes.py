"""Tests for agent/scenes.py + cmd_detect_scenes — Phase 4 FPS-05 + K5 enforcement.

Tests 1..7 mirror PLAN.md Task 1 <behavior> block. Uses stdlib unittest +
unittest.mock (no pytest dep — Phase 2 RESEARCH stdlib-only test precedent).
"""
from __future__ import annotations

import inspect
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import agent.tools as tools_mod
from agent.tools import cmd_detect_scenes


def _ascii_tmpdir_root() -> str:
    """Return an ASCII-only directory for tempfile.TemporaryDirectory.

    Same rationale as test_extract_frames_batch — zh-CN Windows %TEMP% has CJK
    in the username, which trips _validate_out_path.
    """
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_scenes"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


class _FT:
    """Minimal stub of PySceneDetect FrameTimecode — only .get_seconds() is used."""
    def __init__(self, s: float):
        self._s = s

    def get_seconds(self) -> float:
        return self._s


class TestDetectScenesWrapper(unittest.TestCase):
    """Tests 1, 2, 3: agent/scenes.py:detect_scenes wrapper."""

    def test_1_wrapper_conversion_to_dicts(self):
        """Test 1: list[(FT, FT)] becomes list[{start, end}] of plain floats."""
        from agent import scenes as scenes_mod

        fake_raw = [
            (_FT(0.0), _FT(12.5)),
            (_FT(12.5), _FT(47.2)),
        ]
        # Monkey-patch the lazy import path: stub the scenedetect package entirely.
        fake_scenedetect = MagicMock()
        fake_scenedetect.detect = MagicMock(return_value=fake_raw)
        fake_scenedetect.ContentDetector = MagicMock()

        with patch.dict(sys.modules, {"scenedetect": fake_scenedetect}):
            result = scenes_mod.detect_scenes("dummy.mp4")

        self.assertEqual(result, [
            {"start": 0.0, "end": 12.5},
            {"start": 12.5, "end": 47.2},
        ])
        # Types are plain float, not FrameTimecode
        for item in result:
            self.assertIsInstance(item["start"], float)
            self.assertIsInstance(item["end"], float)

    def test_2_default_threshold(self):
        """Test 2: detect_scenes default threshold is 27.0."""
        from agent import scenes as scenes_mod

        fake_scenedetect = MagicMock()
        fake_scenedetect.detect = MagicMock(return_value=[])
        fake_cd = MagicMock()
        fake_scenedetect.ContentDetector = fake_cd

        with patch.dict(sys.modules, {"scenedetect": fake_scenedetect}):
            scenes_mod.detect_scenes("dummy.mp4")

        fake_cd.assert_called_once_with(threshold=27.0)

    def test_3_custom_threshold(self):
        """Test 3: detect_scenes accepts custom threshold."""
        from agent import scenes as scenes_mod

        fake_scenedetect = MagicMock()
        fake_scenedetect.detect = MagicMock(return_value=[])
        fake_cd = MagicMock()
        fake_scenedetect.ContentDetector = fake_cd

        with patch.dict(sys.modules, {"scenedetect": fake_scenedetect}):
            scenes_mod.detect_scenes("dummy.mp4", threshold=35.0)

        fake_cd.assert_called_once_with(threshold=35.0)


class TestCmdDetectScenes(unittest.TestCase):
    """Tests 4, 5, 6: cmd_detect_scenes CLI handler."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.slug_dir = Path(self._td.name) / "BVtest"
        self.slug_dir.mkdir(parents=True)
        # Placeholder video file — we patch detect_scenes so content doesn't matter.
        (self.slug_dir / "video.mp4").write_bytes(b"fake-mp4")

    def tearDown(self):
        self._td.cleanup()

    def test_4_cmd_writes_locked_json_shape(self):
        """Test 4: cmd_detect_scenes writes {version:1, video, scenes:[...]}."""
        out_path = self.slug_dir / "scenes.json"
        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(out_path),
            threshold=27.0,
        )

        with patch("agent.scenes.detect_scenes", return_value=[
            {"start": 0.0, "end": 12.5},
            {"start": 12.5, "end": 47.2},
        ]):
            cmd_detect_scenes(args)

        self.assertTrue(out_path.exists())
        obj = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(set(obj.keys()), {"version", "video", "scenes"})
        self.assertEqual(obj["version"], 1)
        self.assertEqual(obj["video"], "video.mp4")
        self.assertEqual(obj["scenes"], [
            {"start": 0.0, "end": 12.5},
            {"start": 12.5, "end": 47.2},
        ])

    def test_5_stdout_reports_count_and_median(self):
        """Test 5: stdout matches r'detected 2 scenes; median duration = '."""
        out_path = self.slug_dir / "scenes.json"
        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(out_path),
            threshold=27.0,
        )

        buf = io.StringIO()
        with patch("agent.scenes.detect_scenes", return_value=[
            {"start": 0.0, "end": 12.5},   # duration 12.5
            {"start": 12.5, "end": 47.2},  # duration 34.7
        ]), redirect_stdout(buf):
            cmd_detect_scenes(args)

        out = buf.getvalue()
        self.assertIn("detected 2 scenes", out)
        self.assertIn("median duration =", out)

    def test_6_cjk_out_rejected(self):
        """Test 6: CJK in --out raises ValueError before PySceneDetect runs."""
        # Build CJK out path directly (bypass tmpdir which is ASCII).
        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(self.slug_dir / "测试" / "scenes.json"),
            threshold=27.0,
        )

        with patch("agent.scenes.detect_scenes") as mock_detect:
            with self.assertRaises(ValueError):
                cmd_detect_scenes(args)
            self.assertEqual(mock_detect.call_count, 0,
                             "detect_scenes ran before CJK rejection")


class TestSubparserRegistered(unittest.TestCase):
    """Test 7: detect_scenes subcommand is registered + --help shows --threshold."""

    def test_7_help_works_and_mentions_threshold(self):
        """Test 7: `python -m agent.tools detect_scenes --help` exits 0; mentions --threshold."""
        result = subprocess.run(
            [sys.executable, "-m", "agent.tools", "detect_scenes", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0,
                         f"non-zero exit; stderr={result.stderr!r}")
        self.assertIn("--threshold", result.stdout)


class TestK5Boundary(unittest.TestCase):
    """K5: cmd_detect_scenes source must NOT contain 'schedule.json' substring.

    Per locked acceptance criteria: tool NEVER auto-promotes scenes into a schedule.
    """

    def test_k5_source_does_not_mention_schedule_json(self):
        src = inspect.getsource(cmd_detect_scenes)
        self.assertNotIn("schedule.json", src,
                         "K5 violation: cmd_detect_scenes source contains 'schedule.json'")


if __name__ == "__main__":
    unittest.main()
