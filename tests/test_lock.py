"""Tests for agent/_lock.py + agent/tools.py FileLock integration — Phase 6 PARA-01/02/03.

Stdlib unittest only (Phase 2 RESEARCH precedent: pytest is not in default deps).
Mocks subprocess + heavy ASR/ffmpeg calls so tests run in <2s.

Coverage:
  TestFileLockPrimitive (tests A–F): the FileLock primitive in isolation.
  TestIntegration (tests G–H): agent/tools.py wrappers route to slug/.resume.lock
    and concurrent same-slug calls fail fast with LockContended.
"""
from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from agent._lock import FileLock, LockContended


def _ascii_tmpdir_root() -> str:
    """Mirror tests/test_silence.py: zh-CN Windows %TEMP% has CJK in username,
    which trips _validate_out_path on cmd_extract_frames_batch and clutters
    error messages. Pick an ASCII-safe location under tests/."""
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_lock"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


class TestFileLockPrimitive(unittest.TestCase):
    """6 tests on the FileLock primitive only — no agent/tools.py touchpoints."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_A_acquire_release_happy_path(self):
        p = self.tmp / "x.lock"
        with FileLock(p):
            self.assertTrue(p.exists(), "lock file not created")
            content = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(content["pid"], os.getpid())
            self.assertIn("ts", content)

    def test_B_timeout_zero_contended_raises_with_holder_info(self):
        p = self.tmp / "x.lock"
        held = FileLock(p)
        held.acquire()
        try:
            with self.assertRaises(LockContended) as ctx:
                with FileLock(p, timeout=0):
                    self.fail("should not reach inside contended lock")
            msg = str(ctx.exception)
            self.assertIn("PID", msg, f"holder PID missing from error: {msg!r}")
            self.assertIn("since", msg, f"holder timestamp missing: {msg!r}")
        finally:
            held.release()

    def test_C_stale_pid_takeover(self):
        p = self.tmp / "x.lock"
        # Pre-write a holder JSON with a guaranteed-dead PID.
        # PID 999999 is conventionally outside any sane PID range; if it ever
        # exists on the test host, the test is skipped (we just don't take over).
        dead_pid = 999999
        try:
            os.kill(dead_pid, 0)
            self.skipTest(f"PID {dead_pid} unexpectedly alive; cannot test stale takeover")
        except (OSError, PermissionError):
            pass  # expected — PID is dead
        p.write_text(
            json.dumps({"pid": dead_pid, "ts": "2020-01-01T00:00:00+00:00"}),
            encoding="utf-8",
        )
        # Now FileLock should acquire (stale-PID takeover) and overwrite.
        with FileLock(p):
            content = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(content["pid"], os.getpid(),
                             "stale lock not taken over (content still has dead PID)")

    def test_D_timeout_positive_polls_then_raises(self):
        p = self.tmp / "x.lock"
        held = FileLock(p)
        held.acquire()
        try:
            t0 = time.monotonic()
            with self.assertRaises(LockContended):
                with FileLock(p, timeout=0.3):
                    self.fail("should not reach inside contended lock")
            elapsed = time.monotonic() - t0
            self.assertGreaterEqual(elapsed, 0.25,
                                    f"timeout=0.3 returned in {elapsed:.2f}s (too fast)")
            self.assertLess(elapsed, 1.5,
                            f"timeout=0.3 returned in {elapsed:.2f}s (too slow)")
        finally:
            held.release()

    def test_E_release_idempotent(self):
        p = self.tmp / "x.lock"
        lock = FileLock(p)
        lock.acquire()
        lock.release()
        lock.release()  # must not raise

    @unittest.skipUnless(platform.system() == "Windows", "Windows-only branch")
    def test_F_windows_branch_uses_msvcrt(self):
        self.assertIn("msvcrt", sys.modules)
        p = self.tmp / "win.lock"
        with FileLock(p):
            self.assertTrue(p.exists())

    @unittest.skipIf(platform.system() == "Windows", "POSIX-only branch")
    def test_F_posix_branch_uses_fcntl(self):
        self.assertIn("fcntl", sys.modules)
        p = self.tmp / "posix.lock"
        with FileLock(p):
            self.assertTrue(p.exists())


class TestIntegration(unittest.TestCase):
    """2 tests on agent/tools.py FileLock wiring — mock heavy work."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.slug_dir = Path(self._td.name) / "BVtest"
        self.slug_dir.mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_G_resume_lock_path_per_command(self):
        """Each cmd uses the slug-dir-derived lock path, not args.out."""
        seen_paths: list[Path] = []

        @contextmanager
        def capturing_filelock(path, *, timeout=0.0):
            seen_paths.append(Path(path))
            yield None  # no-op lock for this test

        from agent import tools as tools_mod

        # ─── cmd_transcribe: args.out IS slug dir ─────────────────────────
        seen_paths.clear()
        (self.slug_dir / "audio.wav").write_bytes(b"fake")
        with patch("agent.tools.FileLock", capturing_filelock), \
             patch("src.asr.extract_audio"), \
             patch("src.asr.transcribe", return_value=[]), \
             patch("agent.tools.write_json_atomic"):
            args = SimpleNamespace(
                video_path=str(self.slug_dir / "video.mp4"),
                out=str(self.slug_dir),
                whisper="small",
                profile="tutorial",
                force=False,
            )
            try:
                tools_mod.cmd_transcribe(args)
            except Exception:
                pass  # we only care about FileLock path capture
        self.assertTrue(any(p == self.slug_dir / ".resume.lock" for p in seen_paths),
                        f"cmd_transcribe did not lock {self.slug_dir / '.resume.lock'}; "
                        f"seen={seen_paths!r}")

        # ─── cmd_aggregate: out is file path; slug = out.parent ──────────
        seen_paths.clear()
        segs_path = self.slug_dir / "segs.json"
        segs_path.write_text("[]", encoding="utf-8")
        para_path = self.slug_dir / "paragraphs.json"
        with patch("agent.tools.FileLock", capturing_filelock), \
             patch("agent.asr_v2.aggregate_paragraphs", return_value=[]), \
             patch("agent.asr_v2.paragraphs_to_dicts", return_value=[]), \
             patch("agent.tools.write_json_atomic"):
            args = SimpleNamespace(
                segs_json=str(segs_path),
                out=str(para_path),
                profile="tutorial",
                gap=None,
                force=False,
            )
            try:
                tools_mod.cmd_aggregate(args)
            except Exception:
                pass
        self.assertTrue(any(p == self.slug_dir / ".resume.lock" for p in seen_paths),
                        f"cmd_aggregate did not lock {self.slug_dir / '.resume.lock'}; "
                        f"seen={seen_paths!r}")

        # ─── cmd_extract_frames_batch: args.out=frames/; slug=parent ────
        seen_paths.clear()
        frames_dir = self.slug_dir / "frames"
        sched_path = self.slug_dir / "schedule.json"
        sched_path.write_text(json.dumps({
            "version": 1, "video": "video.mp4",
            "default_scale": "854:-1", "default_quality": 4,
            "segments": [],
        }), encoding="utf-8")
        with patch("agent.tools.FileLock", capturing_filelock), \
             patch("agent.scheduler.Schedule") as MockSched, \
             patch("agent.sources._common.ffprobe_video",
                   return_value={"duration_s": 10.0, "codec": "h264",
                                 "container": "mp4", "fps_mode": "CFR"}):
            MockSched.from_json.return_value = MagicMock(
                video="video.mp4", segments=[],
                default_scale="854:-1", default_quality=4,
            )
            args = SimpleNamespace(
                schedule=str(sched_path),
                out=str(frames_dir),
                force=False,
            )
            try:
                tools_mod.cmd_extract_frames_batch(args)
            except Exception:
                pass
        self.assertTrue(any(p == self.slug_dir / ".resume.lock" for p in seen_paths),
                        f"cmd_extract_frames_batch did not lock "
                        f"{self.slug_dir / '.resume.lock'}; seen={seen_paths!r}")

    def test_H_concurrent_same_slug_fails_fast(self):
        """Holding resume.lock externally → cmd_transcribe raises LockContended."""
        from agent import tools as tools_mod
        external = FileLock(self.slug_dir / ".resume.lock")
        external.acquire()
        try:
            args = SimpleNamespace(
                video_path=str(self.slug_dir / "video.mp4"),
                out=str(self.slug_dir),
                whisper="small",
                profile="tutorial",
                force=False,
            )
            with patch("src.asr.extract_audio"), \
                 patch("src.asr.transcribe", return_value=[]):
                with self.assertRaises(LockContended) as ctx:
                    tools_mod.cmd_transcribe(args)
                msg = str(ctx.exception)
                self.assertIn("PID", msg)
        finally:
            external.release()


if __name__ == "__main__":
    unittest.main()
