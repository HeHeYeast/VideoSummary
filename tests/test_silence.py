"""Tests for agent/silence.py + cmd_detect_silence — Phase 4 FPS-06 + K5 enforcement.

Tests 1..8 mirror PLAN.md Task 2 <behavior> block. Uses stdlib unittest +
unittest.mock (no pytest dep — Phase 2 RESEARCH stdlib-only test precedent).
"""
from __future__ import annotations

import builtins
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
from agent.tools import cmd_detect_silence


def _ascii_tmpdir_root() -> str:
    """Return an ASCII-only directory for tempfile.TemporaryDirectory.

    Same rationale as test_extract_frames_batch — zh-CN Windows %TEMP% has CJK
    in the username, which trips _validate_out_path.
    """
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_silence"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


class TestLazyImport(unittest.TestCase):
    """Test 1: clean RuntimeError when silero-vad not installed."""

    def test_1_lazy_import_error_with_install_hint(self):
        """detect_silence raises RuntimeError mentioning install hint when silero-vad absent."""
        from agent import silence as silence_mod

        # Block silero_vad from being importable inside detect_silence.
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "silero_vad" or name.startswith("silero_vad."):
                raise ImportError("No module named 'silero_vad'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=fake_import):
            with self.assertRaises(RuntimeError) as ctx:
                silence_mod.detect_silence("dummy.wav", duration_s=10.0)

        msg = str(ctx.exception)
        self.assertIn("requirements-optional.txt", msg)
        self.assertIn("silero-vad", msg)
        self.assertIn("torch", msg)


class TestInvertSpeechToSilence(unittest.TestCase):
    """Test 2: leading + middle + trailing silence (Pitfall P7).
       Test 3: >5s flagged_for_review."""

    def test_2_invert_with_leading_and_trailing(self):
        """Test 2: leading + middle + trailing silence all present."""
        from agent.silence import _invert_speech_to_silence

        speech_ts = [
            {"start": 5.0, "end": 10.0},
            {"start": 20.0, "end": 25.0},
        ]
        silences = _invert_speech_to_silence(speech_ts, duration_s=30.0)

        self.assertEqual(len(silences), 3)
        # Leading
        self.assertAlmostEqual(silences[0]["start"], 0.0)
        self.assertAlmostEqual(silences[0]["end"], 5.0)
        # Middle
        self.assertAlmostEqual(silences[1]["start"], 10.0)
        self.assertAlmostEqual(silences[1]["end"], 20.0)
        # Trailing
        self.assertAlmostEqual(silences[2]["start"], 25.0)
        self.assertAlmostEqual(silences[2]["end"], 30.0)

    def test_2b_no_leading_silence(self):
        """Speech starts at 0 — no leading silence interval."""
        from agent.silence import _invert_speech_to_silence

        speech_ts = [{"start": 0.0, "end": 10.0}]
        silences = _invert_speech_to_silence(speech_ts, duration_s=30.0)

        self.assertEqual(len(silences), 1)
        self.assertAlmostEqual(silences[0]["start"], 10.0)
        self.assertAlmostEqual(silences[0]["end"], 30.0)

    def test_3_flag_threshold(self):
        """Test 3: >5s gets flagged_for_review:true; <=5s does not."""
        from agent.silence import detect_silence

        # Make silence_vad import return a fake that gives controlled output.
        fake_silero = MagicMock()
        fake_silero.load_silero_vad = MagicMock(return_value="model")
        fake_silero.read_audio = MagicMock(return_value="wav")
        # speech_ts that yields silence intervals [10.0, 16.0] (6s) and [20.0, 24.0] (4s).
        fake_silero.get_speech_timestamps = MagicMock(return_value=[
            {"start": 0.0, "end": 10.0},
            {"start": 16.0, "end": 20.0},
            {"start": 24.0, "end": 30.0},
        ])

        with patch.dict(sys.modules, {"silero_vad": fake_silero}):
            intervals = detect_silence("dummy.wav", duration_s=30.0)

        # Find [10.0, 16.0]: duration=6.0 → flagged
        long_iv = next(i for i in intervals if i["start"] == 10.0)
        self.assertTrue(long_iv.get("flagged_for_review") is True,
                        f"6s silence not flagged: {long_iv}")

        # Find [20.0, 24.0]: duration=4.0 → NOT flagged
        short_iv = next(i for i in intervals if i["start"] == 20.0)
        self.assertNotIn("flagged_for_review", short_iv,
                         f"4s silence wrongly flagged: {short_iv}")


class TestCmdDetectSilence(unittest.TestCase):
    """Tests 4, 5, 6, 7: cmd_detect_silence CLI handler."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.slug_dir = Path(self._td.name) / "BVtest"
        self.slug_dir.mkdir(parents=True)
        (self.slug_dir / "video.mp4").write_bytes(b"fake-mp4")

    def tearDown(self):
        self._td.cleanup()

    def _patch_ffprobe(self, duration_s: float = 30.0):
        return patch(
            "agent.sources._common.ffprobe_video",
            return_value={
                "codec": "h264", "container": "mp4",
                "has_audio": True, "fps_mode": "CFR",
                "width": 1280, "height": 720,
                "duration_s": duration_s,
            },
        )

    def test_4_output_schema(self):
        """Test 4: cmd_detect_silence writes {version:1, video, silence_intervals:[...]}."""
        out_path = self.slug_dir / "silence_map.json"
        # Make audio.wav exist so cmd_detect_silence reuses it (Pitfall P5).
        (self.slug_dir / "audio.wav").write_bytes(b"fake-wav")

        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(out_path),
        )

        fake_intervals = [
            {"start": 0.0, "end": 1.2, "duration": 1.2},
            {"start": 47.2, "end": 53.8, "duration": 6.6,
             "flagged_for_review": True},
        ]
        with self._patch_ffprobe(60.0), \
             patch("agent.silence.detect_silence", return_value=fake_intervals):
            cmd_detect_silence(args)

        self.assertTrue(out_path.exists())
        obj = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(set(obj.keys()), {"version", "video", "silence_intervals"})
        self.assertEqual(obj["version"], 1)
        self.assertEqual(obj["video"], "video.mp4")
        self.assertEqual(obj["silence_intervals"], fake_intervals)

    def test_5_stdout_hint(self):
        """Test 5: stdout matches r'Found N silence intervals; M flagged > 5s' + mentions FPS-04."""
        out_path = self.slug_dir / "silence_map.json"
        (self.slug_dir / "audio.wav").write_bytes(b"fake-wav")

        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(out_path),
        )

        fake_intervals = [
            {"start": 0.0, "end": 1.2, "duration": 1.2},
            {"start": 47.2, "end": 53.8, "duration": 6.6,
             "flagged_for_review": True},
        ]
        buf = io.StringIO()
        with self._patch_ffprobe(60.0), \
             patch("agent.silence.detect_silence", return_value=fake_intervals), \
             redirect_stdout(buf):
            cmd_detect_silence(args)

        out = buf.getvalue()
        self.assertIn("Found 2 silence intervals", out)
        self.assertIn("1 flagged > 5s", out)
        self.assertIn("FPS-04", out)

    def test_6_cjk_out_rejected(self):
        """Test 6: CJK in --out raises ValueError before silero-vad runs."""
        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(self.slug_dir / "测试" / "silence_map.json"),
        )

        with patch("agent.silence.detect_silence") as mock_ds:
            with self.assertRaises(ValueError):
                cmd_detect_silence(args)
            self.assertEqual(mock_ds.call_count, 0,
                             "detect_silence ran before CJK rejection")

    def test_7_audio_resolution_reuses_existing(self):
        """Test 7a: audio.wav exists → no ffmpeg subprocess."""
        from agent import silence as silence_mod

        (self.slug_dir / "audio.wav").write_bytes(b"fake-wav")
        out_path = self.slug_dir / "silence_map.json"
        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(out_path),
        )

        with self._patch_ffprobe(30.0), \
             patch("agent.silence.detect_silence", return_value=[]), \
             patch("subprocess.run") as mock_run:
            cmd_detect_silence(args)

        # subprocess.run NOT called for audio extraction (audio.wav already there).
        # ffprobe is patched at agent.sources._common.ffprobe_video import site,
        # so subprocess.run shouldn't fire from inside our path either.
        self.assertEqual(mock_run.call_count, 0,
                         f"ffmpeg subprocess invoked when audio.wav already exists "
                         f"(call_args_list={mock_run.call_args_list!r})")

    def test_7b_audio_resolution_extracts_when_missing(self):
        """Test 7b: audio.wav missing → ffmpeg extract fires."""
        # No audio.wav prepared.
        out_path = self.slug_dir / "silence_map.json"
        args = SimpleNamespace(
            video=str(self.slug_dir / "video.mp4"),
            out=str(out_path),
        )

        # When subprocess.run is mocked it returns a MagicMock; we still need
        # detect_silence patched so we don't actually invoke silero-vad.
        with self._patch_ffprobe(30.0), \
             patch("agent.silence.detect_silence", return_value=[]), \
             patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            cmd_detect_silence(args)

        # ffmpeg extract called at least once (cmd[0] == "ffmpeg")
        self.assertGreaterEqual(mock_run.call_count, 1,
                                "ffmpeg subprocess never invoked when audio.wav missing")
        first_call_args = mock_run.call_args_list[0][0][0]
        self.assertEqual(first_call_args[0], "ffmpeg")


class TestSubparserRegistered(unittest.TestCase):
    """Test 8: detect_silence subcommand is registered + --help works without silero-vad."""

    def test_8_help_works_without_silero_vad(self):
        """Test 8: `python -m agent.tools detect_silence --help` exits 0 (lazy import)."""
        # Even if silero-vad isn't installed, --help should work because import is lazy.
        result = subprocess.run(
            [sys.executable, "-m", "agent.tools", "detect_silence", "--help"],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0,
                         f"non-zero exit; stderr={result.stderr!r}")
        self.assertIn("--out", result.stdout)


class TestK5Boundary(unittest.TestCase):
    """K5: cmd_detect_silence source must NOT contain 'schedule.json' substring.

    Per locked acceptance criteria: tool NEVER auto-promotes silence intervals
    into a schedule. Note: the docstring may discuss FPS-04 / coverage check
    semantics, but must NOT use the literal schedule artifact filename.
    """

    def test_k5_source_does_not_mention_schedule_json(self):
        src = inspect.getsource(cmd_detect_silence)
        self.assertNotIn("schedule.json", src,
                         "K5 violation: cmd_detect_silence source contains 'schedule.json'")


if __name__ == "__main__":
    unittest.main()
