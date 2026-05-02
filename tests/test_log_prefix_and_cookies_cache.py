"""Tests for Phase 6 PARA-04/05/06: log prefix + cookies cache + CLAUDE.md docs.

Stdlib unittest only. Tests:
  - TestLogPrefix: cmd_* status lines start with [<slug>] <cmd>:
  - TestCookiesCache: douyin cookies cached per-process; --reload forces re-read
  - TestClaudeMdDocs: ## 多终端并行 (Phase 6) section exists between anchors;
                      4 critical sections still byte-equal in known substrings
"""
from __future__ import annotations

import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock


def _ascii_tmpdir_root() -> str:
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_phase6"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


REPO_ROOT = Path(__file__).parent.parent.resolve()
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"


class TestLogPrefix(unittest.TestCase):
    """PARA-04: cmd_* status lines prefixed with [<slug>] <cmd>:"""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.slug = "BVtest"
        self.slug_dir = Path(self._td.name) / self.slug
        self.slug_dir.mkdir(parents=True)

    def tearDown(self):
        self._td.cleanup()

    def test_3e_helper_format(self):
        """_log(slug, cmd, msg) prints '[slug] cmd: msg' to stdout."""
        from agent.tools import _log
        buf = io.StringIO()
        with redirect_stdout(buf):
            _log("BVtest", "transcribe", "segments: 42")
        self.assertEqual(buf.getvalue().rstrip("\n"), "[BVtest] transcribe: segments: 42")

    def test_3e_aggregate_status_prefixed(self):
        """cmd_aggregate's 'output: ...' line carries the prefix."""
        from agent import tools as tools_mod
        segs_path = self.slug_dir / "segs.json"
        segs_path.write_text("[]", encoding="utf-8")
        para_path = self.slug_dir / "paragraphs.json"

        buf = io.StringIO()
        with patch("agent.asr_v2.aggregate_paragraphs", return_value=[]), \
             patch("agent.asr_v2.paragraphs_to_dicts", return_value=[]), \
             patch("agent.tools.write_json_atomic"), \
             patch("agent.tools.FileLock") as mock_lock:
            mock_lock.return_value.__enter__ = MagicMock(return_value=None)
            mock_lock.return_value.__exit__ = MagicMock(return_value=None)
            args = SimpleNamespace(
                segs_json=str(segs_path),
                out=str(para_path),
                profile="tutorial",
                gap=None,
                force=False,
            )
            with redirect_stdout(buf):
                try:
                    tools_mod.cmd_aggregate(args)
                except Exception:
                    pass
        out = buf.getvalue()
        self.assertRegex(
            out, r"\[BVtest\] aggregate: ",
            f"no '[BVtest] aggregate:' prefix in stdout: {out!r}",
        )

    def test_3e_existing_substring_preserved(self):
        """Old test_silence.py:test_5 asserts 'FPS-04' substring; still present after prefix."""
        import inspect
        from agent.tools import cmd_detect_silence
        src = inspect.getsource(cmd_detect_silence)
        self.assertIn("FPS-04", src,
                      "FPS-04 reference removed from cmd_detect_silence source")


class TestCookiesCache(unittest.TestCase):
    """PARA-05: cookies read-once per process; --reload-cookies forces re-read."""

    def setUp(self):
        from agent.sources import douyin as douyin_mod
        # Reset cache between tests.
        douyin_mod._COOKIES_CACHE.clear()
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.cookies_path = Path(self._td.name) / "fake_cookies.txt"
        self.cookies_path.write_text(
            "# Netscape HTTP Cookie File\n"
            ".douyin.com\tTRUE\t/\tFALSE\t0\tsessionid\tdeadbeef\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self._td.cleanup()

    def test_3f_cached_on_second_call(self):
        from agent.sources.douyin import _read_cookies_cached
        # Patch Path.read_text so we can count actual disk reads.
        with patch.object(Path, "read_text", autospec=True,
                          return_value="# fake cookies content") as mock_read:
            text1 = _read_cookies_cached(self.cookies_path)
            text2 = _read_cookies_cached(self.cookies_path)
        self.assertEqual(text1, text2)
        self.assertEqual(mock_read.call_count, 1,
                         f"Path.read_text called {mock_read.call_count} times "
                         f"(expected 1 - second call should hit cache)")

    def test_3g_reload_forces_re_read(self):
        from agent.sources.douyin import _read_cookies_cached
        with patch.object(Path, "read_text", autospec=True,
                          return_value="# fake cookies content") as mock_read:
            _read_cookies_cached(self.cookies_path)
            _read_cookies_cached(self.cookies_path, reload=True)
        self.assertEqual(mock_read.call_count, 2,
                         f"reload=True did not force re-read; got {mock_read.call_count} reads")

    def test_3f_different_paths_separate_entries(self):
        from agent.sources.douyin import _read_cookies_cached
        other_path = Path(self._td.name) / "other_cookies.txt"
        other_path.write_text("# different cookies", encoding="utf-8")
        with patch.object(Path, "read_text", autospec=True,
                          return_value="# stub content") as mock_read:
            _read_cookies_cached(self.cookies_path)
            _read_cookies_cached(other_path)
            _read_cookies_cached(self.cookies_path)  # cached
            _read_cookies_cached(other_path)         # cached
        self.assertEqual(mock_read.call_count, 2,
                         "expected 2 reads (one per unique path)")

    def test_youtube_cache_module_attr_exists(self):
        from agent.sources.youtube import _COOKIES_CACHE
        self.assertIsInstance(_COOKIES_CACHE, dict)


class TestClaudeMdDocs(unittest.TestCase):
    """PARA-06: CLAUDE.md ## 多终端并行 (Phase 6) section + 4 critical sections preserved."""

    @classmethod
    def setUpClass(cls):
        cls.text = CLAUDE_MD.read_text(encoding="utf-8")
        cls.lines = cls.text.splitlines()

    def _line_of(self, heading: str) -> int:
        for i, line in enumerate(self.lines):
            if line.strip() == heading:
                return i
        self.fail(f"heading not found in CLAUDE.md: {heading!r}")

    def test_3a_new_section_exists(self):
        self.assertEqual(
            self.text.count("## 多终端并行 (Phase 6)"), 1,
            "## 多终端并行 (Phase 6) heading not found exactly once",
        )

    def test_3c_placement(self):
        env_line = self._line_of("## 环境变量（.env）")
        new_line = self._line_of("## 多终端并行 (Phase 6)")
        biantou_line = self._line_of("## 视频类型变奏")
        self.assertLess(env_line, new_line,
                        "## 多终端并行 must come AFTER ## 环境变量")
        self.assertLess(new_line, biantou_line,
                        "## 多终端并行 must come BEFORE ## 视频类型变奏")

    def test_3d_section_mentions_contract_terms(self):
        # Slice the text from the new heading to the next h2 (or ---) so we
        # only assert against the new section's body.
        start = self.text.index("## 多终端并行 (Phase 6)")
        rest = self.text[start + len("## 多终端并行 (Phase 6)"):]
        next_h2 = rest.find("\n## ")
        section = rest if next_h2 == -1 else rest[:next_h2]

        for term in ["per-slug isolation", "OOM", "nproc",
                     ".resume.lock", "vendor"]:
            self.assertIn(term, section,
                          f"new section missing required term: {term!r}")

    def test_3b_critical_sections_intact(self):
        """4+1 critical sections still present + their stable signatures unchanged."""
        critical = [
            ("## 抖音支持（首次设置）",
             "抖音 URL 的下载链路和 B 站不同"),
            ("## YouTube 支持（首次设置，可选）",
             "ingest 时会自动按 HTTPS_PROXY > HTTP_PROXY"),
            ("## Pyannote diarization 设置（首次设置，可选）",
             "pyannote"),
            ("## Windows zh-CN 终端设置（推荐）",
             "chcp 65001"),
            ("## 决策支持工具（Phase 4，可选）",
             "PySceneDetect"),
        ]
        for heading, signature in critical:
            self.assertIn(heading, self.text,
                          f"critical heading missing: {heading!r}")
            self.assertIn(signature, self.text,
                          f"critical section disturbed; signature missing: {signature!r}")


if __name__ == "__main__":
    unittest.main()
