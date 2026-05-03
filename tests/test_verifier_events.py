"""Phase 09 Plan 02 — unit tests for agent/verifier_events.py.

Tests the 3 helper functions:
  - emit_verifier_run(slug_dir, severity_counts=, output_path=, duration_ms=)
  - emit_rewrite_cycle_completed(slug_dir, critical_count_pre=, critical_count_post=,
        rewrite_path=, duration_ms=, unresolved_path=)
  - build_unresolved_md(slug, critical_findings)

K5 invariant: helpers ONLY emit state.jsonl events + render markdown templates;
they NEVER mutate summary.md, plan.md, or schedule.json.

All tests use tempfile.TemporaryDirectory for hermetic isolation.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent.verifier_events import (
    PRE_REVIEW_BACKUP_SUFFIX,
    REVIEW_FILENAME_TEMPLATE,
    UNRESOLVED_FILENAME_TEMPLATE,
    build_unresolved_md,
    emit_rewrite_cycle_completed,
    emit_verifier_run,
)


def _read_events(slug_dir: Path) -> list[dict]:
    """Read all JSONL lines from state.jsonl as dicts."""
    state_log = slug_dir / "state.jsonl"
    if not state_log.exists():
        return []
    events: list[dict] = []
    for line in state_log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return events


class TestEmitVerifierRun(unittest.TestCase):
    """Test 1: emit_verifier_run writes valid JSONL."""

    def test_emit_verifier_run_writes_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as td:
            slug_dir = Path(td)
            severity_counts = {"critical": 0, "warning": 2, "info": 5}
            emit_verifier_run(
                slug_dir,
                severity_counts=severity_counts,
                output_path="BVtest-REVIEW.md",
                duration_ms=4500,
            )
            events = _read_events(slug_dir)
            self.assertEqual(len(events), 1)
            ev = events[0]
            self.assertEqual(ev["stage"], "verifier")
            self.assertEqual(ev["status"], "completed")
            self.assertIn("ts", ev)
            self.assertIn("details", ev)
            self.assertEqual(ev["details"]["severity_counts"],
                             {"critical": 0, "warning": 2, "info": 5})
            self.assertEqual(ev["details"]["output_path"], "BVtest-REVIEW.md")
            self.assertEqual(ev["details"]["duration_ms"], 4500)


class TestEmitRewriteCycleCompletedClean(unittest.TestCase):
    """Test 2: emit_rewrite_cycle_completed (clean ship — critical_count_post == 0)."""

    def test_emit_rewrite_cycle_clean_ship(self):
        with tempfile.TemporaryDirectory() as td:
            slug_dir = Path(td)
            emit_rewrite_cycle_completed(
                slug_dir,
                critical_count_pre=3,
                critical_count_post=0,
                rewrite_path="summary.md.pre-review",
                duration_ms=12345,
            )
            events = _read_events(slug_dir)
            self.assertEqual(len(events), 1)
            ev = events[0]
            self.assertEqual(ev["stage"], "rewrite_cycle")
            self.assertEqual(ev["status"], "completed")
            self.assertEqual(ev["details"]["critical_count_pre"], 3)
            self.assertEqual(ev["details"]["critical_count_post"], 0)
            self.assertEqual(ev["details"]["rewrite_path"],
                             "summary.md.pre-review")
            self.assertEqual(ev["details"]["duration_ms"], 12345)
            # When critical_count_post == 0, unresolved_path should be absent
            self.assertNotIn("unresolved_path", ev["details"])


class TestEmitRewriteCycleCompletedUnresolved(unittest.TestCase):
    """Test 3: emit_rewrite_cycle_completed with unresolved (critical_count_post > 0)."""

    def test_emit_rewrite_cycle_with_unresolved(self):
        with tempfile.TemporaryDirectory() as td:
            slug_dir = Path(td)
            emit_rewrite_cycle_completed(
                slug_dir,
                critical_count_pre=5,
                critical_count_post=2,
                rewrite_path="summary.md.pre-review",
                duration_ms=20000,
                unresolved_path="BVtest-UNRESOLVED.md",
            )
            events = _read_events(slug_dir)
            self.assertEqual(len(events), 1)
            ev = events[0]
            self.assertEqual(ev["details"]["critical_count_pre"], 5)
            self.assertEqual(ev["details"]["critical_count_post"], 2)
            self.assertEqual(ev["details"]["unresolved_path"],
                             "BVtest-UNRESOLVED.md")

    def test_emit_rewrite_cycle_unresolved_path_absent_when_clean(self):
        """If critical_count_post == 0 even when unresolved_path passed,
        the field should not be set (defensive — clean ship semantics)."""
        with tempfile.TemporaryDirectory() as td:
            slug_dir = Path(td)
            emit_rewrite_cycle_completed(
                slug_dir,
                critical_count_pre=3,
                critical_count_post=0,
                rewrite_path="summary.md.pre-review",
                duration_ms=8000,
                unresolved_path="should-not-be-recorded.md",
            )
            events = _read_events(slug_dir)
            self.assertEqual(len(events), 1)
            self.assertNotIn("unresolved_path", events[0]["details"])


class TestBuildUnresolvedMdRendering(unittest.TestCase):
    """Test 4: build_unresolved_md renders proper markdown checklist."""

    def test_build_unresolved_md_with_findings(self):
        slug = "BVtest"
        findings = [
            {
                "location": "summary.md L42",
                "evidence": "fps=0.3 抽帧（缺少 trace token）",
                "rule": "trace_after_claim",
            },
            {
                "location": "summary.md §三、消化阶段",
                "evidence": "[para_0042 @ 00:23:15] 不存在于 paragraphs.json",
                "rule": "citation_timestamp_invalid",
            },
        ]
        md = build_unresolved_md(slug, findings)

        # H1
        self.assertIn(f"# UNRESOLVED — {slug}", md)
        # H2 checklist heading
        self.assertIn("## 人工介入清单", md)
        # 2 checklist items
        self.assertIn("- [ ] **1. summary.md L42**", md)
        self.assertIn("- [ ] **2. summary.md §三、消化阶段**", md)
        # Each item references its rule
        self.assertIn("`trace_after_claim`", md)
        self.assertIn("`citation_timestamp_invalid`", md)
        # Each item has evidence + 建议修复方向 placeholder
        self.assertIn("证据：", md)
        self.assertIn("建议修复方向：", md)
        # Backup reference
        self.assertIn(f"output/{slug}/summary.md.pre-review", md)


class TestBuildUnresolvedMdEmpty(unittest.TestCase):
    """Test 5: build_unresolved_md handles empty findings."""

    def test_build_unresolved_md_empty(self):
        md = build_unresolved_md("BVempty", [])
        # Still has H1
        self.assertIn("# UNRESOLVED — BVempty", md)
        # Defensive note when called with empty list
        self.assertIn("无 critical 残余", md)
        self.assertIn("不应触发本文件", md)


class TestUtf8CjkRoundtrip(unittest.TestCase):
    """Test 6: UTF-8 CJK round-trip — Windows zh-CN P-04 invariant.

    Both build_unresolved_md output AND state.jsonl writes must round-trip CJK
    cleanly via encoding='utf-8'.
    """

    def test_unresolved_md_cjk_roundtrip(self):
        slug = "BV测试中文"
        findings = [
            {
                "location": "summary.md 第 42 行",
                "evidence": "时间戳引用错误：[12:34:56] 不存在于 paragraphs.json",
                "rule": "citation_timestamp_invalid",
            },
        ]
        md = build_unresolved_md(slug, findings)
        # CJK literal preservation
        self.assertIn("BV测试中文", md)
        self.assertIn("时间戳引用错误", md)
        self.assertIn("第 42 行", md)
        # Disk write round-trip
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / f"{slug}-UNRESOLVED.md"
            out.write_text(md, encoding="utf-8")
            roundtrip = out.read_text(encoding="utf-8")
            self.assertEqual(md, roundtrip)

    def test_emit_verifier_run_cjk_in_path(self):
        """state.jsonl event with CJK output_path round-trips cleanly."""
        with tempfile.TemporaryDirectory() as td:
            slug_dir = Path(td)
            emit_verifier_run(
                slug_dir,
                severity_counts={"critical": 1, "warning": 0, "info": 0},
                output_path="BV测试中文-REVIEW.md",
                duration_ms=1000,
            )
            events = _read_events(slug_dir)
            self.assertEqual(events[0]["details"]["output_path"],
                             "BV测试中文-REVIEW.md")


class TestConstantsExported(unittest.TestCase):
    """Sanity: verify the module exports the documented constants."""

    def test_constants_present(self):
        self.assertEqual(PRE_REVIEW_BACKUP_SUFFIX, ".pre-review")
        # Templates contain a {slug} placeholder
        self.assertIn("{slug}", REVIEW_FILENAME_TEMPLATE)
        self.assertIn("{slug}", UNRESOLVED_FILENAME_TEMPLATE)
        # Format output is sensible
        self.assertEqual(REVIEW_FILENAME_TEMPLATE.format(slug="BVx"),
                         "BVx-REVIEW.md")
        self.assertEqual(UNRESOLVED_FILENAME_TEMPLATE.format(slug="BVx"),
                         "BVx-UNRESOLVED.md")


if __name__ == "__main__":
    unittest.main()
