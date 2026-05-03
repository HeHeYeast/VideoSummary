"""Phase 08 TEACH-A3 tests: glossary append idempotency, lock race, first-seen-wins.

Mirrors the multiprocessing race test pattern from tests/test_queue.py
(Phase 07 MISC-02 T12/T13). The lock domain here is `output/.glossary.lock`
instead of `~/.videoSummary/.queue.lock` — same agent/_lock.FileLock
machinery, just a different lock-file path.

Tests:
  - T1: first append creates file with locked header preamble + H2 + bullet
  - T2: idempotent on (slug, term) — second call returns skipped, file byte-equal
  - T3: 2 child processes hitting same (slug, term) — exactly 1 H2 + 1 bullet
  - T4: first-seen-wins — same term + different slug + different definition
  - T5: Phase 07 audit_glossary forward-compat with Phase 08 schema
  - T6: lock contention with timeout=0 raises LockContended
"""
from __future__ import annotations

import multiprocessing as mp
import tempfile
import unittest
from pathlib import Path

from agent.glossary import (
    glossary_append,
    GLOSSARY_FILENAME,
    LOCK_FILENAME,
)
from agent._lock import FileLock, LockContended
from agent.glossary_audit import audit_glossary


def _ascii_tmpdir_root() -> Path:
    """Per-test tmpdir under tests/_tmp_glossary/ (ASCII-safe per CONTEXT D-19;
    Windows zh-CN GBK code-page would corrupt subprocess paths if we used
    %TEMP% which contains the user's CJK profile name).
    """
    root = Path(__file__).parent / "_tmp_glossary"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _child_append(output_dir: str, slug: str, term: str, definition: str,
                  result_q) -> None:
    """multiprocessing target: call glossary_append in a child process,
    push the result dict (or exception repr) onto result_q.
    """
    try:
        result = glossary_append(
            slug=slug, term=term, definition=definition,
            output_dir=output_dir, timeout=15.0,
        )
        result_q.put(("ok", result))
    except Exception as e:
        result_q.put(("error", repr(e)))


class TestGlossaryAppend(unittest.TestCase):

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(
            prefix="glossary_test_", dir=str(_ascii_tmpdir_root()),
        )
        self.tmpdir = Path(self._tmp.name)
        self.glossary_md = self.tmpdir / GLOSSARY_FILENAME

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_T1_append_creates_file_with_header(self):
        """First append creates file with locked header preamble + H2 + bullet."""
        result = glossary_append(
            slug="BVfoo",
            term="LoRA (Low-Rank Adaptation)",
            definition="参数高效的微调技术。",
            output_dir=str(self.tmpdir),
            context="测试 context",
        )
        self.assertEqual(result["action"], "appended")
        self.assertTrue(result["term_h2_created"])
        self.assertTrue(result["slug_link_added"])
        self.assertTrue(self.glossary_md.exists())
        text = self.glossary_md.read_text(encoding="utf-8")
        self.assertIn("# 术语表", text)
        self.assertIn("跨 slug 累积的术语", text)
        self.assertIn("## LoRA (Low-Rank Adaptation)", text)
        self.assertIn("参数高效的微调技术", text)
        self.assertIn("[BVfoo](BVfoo/" + "summary.md)", text)
        self.assertIn("测试 context", text)

    def test_T2_append_idempotent_same_slug_term(self):
        """Second call with identical (slug, term) returns skipped + no file change."""
        glossary_append(slug="BVbar", term="ECS (Entity-Component-System)",
                        definition="数据导向架构。",
                        output_dir=str(self.tmpdir))
        text_after_first = self.glossary_md.read_text(encoding="utf-8")
        result2 = glossary_append(slug="BVbar", term="ECS (Entity-Component-System)",
                                  definition="数据导向架构。",
                                  output_dir=str(self.tmpdir))
        text_after_second = self.glossary_md.read_text(encoding="utf-8")
        self.assertEqual(result2["action"], "skipped")
        self.assertEqual(result2["reason"], "duplicate_slug_link")
        self.assertFalse(result2["term_h2_created"])
        self.assertFalse(result2["slug_link_added"])
        self.assertEqual(text_after_first, text_after_second)

    def test_T3_concurrent_append_via_multiprocessing(self):
        """2 child processes calling glossary_append on same (slug, term).
        Mirrors tests/test_queue.py:T12 race-test pattern. Both must complete
        without exception; exactly one wins, other sees idempotent skip."""
        ctx = mp.get_context("spawn")  # spawn for Windows compat
        result_q = ctx.Queue()
        p1 = ctx.Process(target=_child_append,
                         args=(str(self.tmpdir), "BVrace",
                               "Diffusion (扩散模型)",
                               "通过逐步去噪生成图像。", result_q))
        p2 = ctx.Process(target=_child_append,
                         args=(str(self.tmpdir), "BVrace",
                               "Diffusion (扩散模型)",
                               "通过逐步去噪生成图像。", result_q))
        p1.start()
        p2.start()
        p1.join(timeout=30)
        p2.join(timeout=30)
        self.assertFalse(p1.is_alive(), "Child 1 hung past 30s timeout")
        self.assertFalse(p2.is_alive(), "Child 2 hung past 30s timeout")
        self.assertEqual(p1.exitcode, 0, f"Child 1 exit {p1.exitcode}")
        self.assertEqual(p2.exitcode, 0, f"Child 2 exit {p2.exitcode}")
        # Drain queue
        results = []
        while not result_q.empty():
            results.append(result_q.get())
        self.assertEqual(len(results), 2)
        for status, payload in results:
            self.assertEqual(status, "ok", f"child returned error: {payload}")
        # Final file: exactly 1 H2 anchor + 1 slug-link bullet
        text = self.glossary_md.read_text(encoding="utf-8")
        self.assertEqual(
            text.count("## Diffusion (扩散模型)"), 1,
            f"expected exactly 1 H2 anchor; got\n{text}",
        )
        self.assertEqual(
            text.count("[BVrace](BVrace/" + "summary.md)"), 1,
            f"expected exactly 1 slug-link bullet; got\n{text}",
        )

    def test_T4_first_seen_wins_definition(self):
        """Same term, different slug + different definition: first definition stays."""
        glossary_append(slug="BVfirst", term="Tokenizer (分词器)",
                        definition="version_one — first definition.",
                        output_dir=str(self.tmpdir))
        glossary_append(slug="BVsecond", term="Tokenizer (分词器)",
                        definition="version_two_must_be_ignored.",
                        output_dir=str(self.tmpdir))
        text = self.glossary_md.read_text(encoding="utf-8")
        self.assertIn("version_one — first definition.", text)
        self.assertNotIn("version_two_must_be_ignored", text)
        self.assertIn("[BVfirst](BVfirst/" + "summary.md)", text)
        self.assertIn("[BVsecond](BVsecond/" + "summary.md)", text)
        # Exactly one H2 for this term
        self.assertEqual(text.count("## Tokenizer (分词器)"), 1)

    def test_T5_audit_sees_appended_terms(self):
        """Phase 07 audit_glossary correctly counts Phase 08-appended H2 anchors."""
        glossary_append(slug="BVa", term="Term A (alpha)",
                        definition="Def A.", output_dir=str(self.tmpdir))
        glossary_append(slug="BVb", term="Term B (beta)",
                        definition="Def B.", output_dir=str(self.tmpdir))
        glossary_append(slug="BVc", term="Term C (gamma)",
                        definition="Def C.", output_dir=str(self.tmpdir))
        audit = audit_glossary(path=str(self.glossary_md))
        self.assertTrue(audit["exists"])
        # term_count counts H2 anchors. The header preamble has NO H2; only the
        # 3 term sections do. So term_count == 3.
        self.assertEqual(audit["term_count"], 3)
        self.assertEqual(audit["duplicate_terms"], [])
        self.assertEqual(audit["conflicting_definitions"], [])

    def test_T6_lock_contention_with_zero_timeout(self):
        """If lock is held externally, append with timeout=0 raises LockContended."""
        lock_path = self.tmpdir / LOCK_FILENAME
        with FileLock(lock_path):
            with self.assertRaises(LockContended):
                glossary_append(
                    slug="BVcontended", term="X (x)",
                    definition="d.", output_dir=str(self.tmpdir),
                    timeout=0.0,
                )


if __name__ == "__main__":
    unittest.main()
