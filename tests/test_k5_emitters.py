"""K5 source-grep static assertions for Phase 07 emitters.

Mirrors tests/test_scenes.py:TestK5Boundary at line 191-199 — the locked
acceptance test for K5 boundary preservation. Each new emitter source
MUST NOT contain the literals 'summary.md' / 'plan.md' / 'schedule.json'.

Per .planning/phases/07-warm-up-k5-emitters-d-29-foundation/07-CONTEXT.md
specifics: this is the literal source-grep template — failing this
assertion is a phase-blocking error.
"""
from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from agent.tools import (
    cmd_transcribe_lint,
    cmd_mode_signals,
    cmd_schedule_suggest,
    cmd_glossary_audit,
    cmd_glossary_append,  # NEW Phase 08 TEACH-A3
    cmd_summary_lint,  # NEW Phase 09 CORR-03a
    cmd_topics_bootstrap, cmd_topics_audit, cmd_topics_resolve,  # Phase 10 D-06
)

FORBIDDEN_LITERALS = ("summary.md", "plan.md", "schedule.json")

# Phase 08 TEACH-A3 — for modules where the literal substring `summary.md`
# is LEGITIMATELY present as part of an OUTPUT bullet-link template (the
# glossary writes a markdown link `[<slug>](<slug>/summary.md)` INTO the
# accumulator file — it does NOT write to per-slug summary). We assert no
# WRITE patterns target the forbidden filenames instead. Mirrors the
# Phase 07 plan-01 deviation #2 fix (intent-correct write-pattern regex).
_WRITE_PATTERNS_FORBIDDEN = (
    r"write_text\([^)]*summary\.md",
    r"write_text\([^)]*plan\.md",
    r"write_text\([^)]*schedule\.json",
    r"open\([^)]*summary\.md[^)]*['\"]w",
    r"open\([^)]*plan\.md[^)]*['\"]w",
    r"open\([^)]*schedule\.json[^)]*['\"]w",
    r"os\.replace\([^)]*summary\.md",
    r"os\.replace\([^)]*plan\.md",
    r"os\.replace\([^)]*schedule\.json",
    r"_atomic_write\([^)]*summary\.md",
    r"_atomic_write\([^)]*plan\.md",
    r"_atomic_write\([^)]*schedule\.json",
)

# Phase 10 D-06: forbidden write targets for topics resolve. The literal
# `index.json` is ALLOWED (legitimate write target for cmd_topics_resolve);
# all 5 D-29 core artifacts are forbidden.
_RESOLVE_FORBIDDEN_PATTERNS = (
    r"write_text\([^)]*summary\.md", r"write_text\([^)]*plan\.md",
    r"write_text\([^)]*paragraphs\.json", r"write_text\([^)]*segs\.json",
    r"write_text\([^)]*meta\.json",
    r"open\([^)]*summary\.md[^)]*['\"]w", r"open\([^)]*plan\.md[^)]*['\"]w",
    r"open\([^)]*paragraphs\.json[^)]*['\"]w",
    r"open\([^)]*segs\.json[^)]*['\"]w",
    r"open\([^)]*meta\.json[^)]*['\"]w",
    r"os\.replace\([^)]*summary\.md", r"os\.replace\([^)]*plan\.md",
    r"os\.replace\([^)]*paragraphs\.json", r"os\.replace\([^)]*segs\.json",
    r"os\.replace\([^)]*meta\.json",
    r"_atomic_write\([^)]*summary\.md", r"_atomic_write\([^)]*plan\.md",
    r"_atomic_write\([^)]*paragraphs\.json",
    r"_atomic_write\([^)]*segs\.json",
    r"_atomic_write\([^)]*meta\.json",
    r"write_json_atomic\([^)]*summary\.md",
    r"write_json_atomic\([^)]*plan\.md",
    r"write_json_atomic\([^)]*paragraphs\.json",
    r"write_json_atomic\([^)]*segs\.json",
    r"write_json_atomic\([^)]*meta\.json",
)


class TestK5BoundaryPhase07(unittest.TestCase):
    """K5: each new emitter (handler + module source) must not reference
    the decision artifact filenames literally.
    """

    def _check_function_source(self, fn, name: str) -> None:
        src = inspect.getsource(fn)
        for forbidden in FORBIDDEN_LITERALS:
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: {name} source contains forbidden literal {forbidden!r}",
            )

    def _check_module_file(self, module_path: str) -> None:
        # Resolve relative to repo root (tests/ sibling)
        here = Path(__file__).parent.parent
        full = here / module_path
        src = full.read_text(encoding="utf-8")
        for forbidden in FORBIDDEN_LITERALS:
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: {module_path} contains forbidden literal {forbidden!r}",
            )

    def test_K5_handler_cmd_transcribe_lint(self):
        self._check_function_source(cmd_transcribe_lint, "cmd_transcribe_lint")

    def test_K5_handler_cmd_mode_signals(self):
        self._check_function_source(cmd_mode_signals, "cmd_mode_signals")

    def test_K5_handler_cmd_schedule_suggest(self):
        self._check_function_source(cmd_schedule_suggest, "cmd_schedule_suggest")

    def test_K5_handler_cmd_glossary_audit(self):
        self._check_function_source(cmd_glossary_audit, "cmd_glossary_audit")

    def test_K5_module_transcribe_lint(self):
        self._check_module_file("agent/transcribe_lint.py")

    def test_K5_module_mode_signals(self):
        self._check_module_file("agent/mode_signals.py")

    def test_K5_module_schedule_suggestion(self):
        self._check_module_file("agent/schedule_suggestion.py")

    def test_K5_module_glossary_audit(self):
        self._check_module_file("agent/glossary_audit.py")

    # ── Phase 08 TEACH-A3 K5 boundary tests for agent/glossary.py ──
    # Cannot extend FORBIDDEN_LITERALS tuple because the bullet-link template
    # legitimately contains the literal substring `summary.md` as OUTPUT
    # formatting (markdown link inside the glossary accumulator file). We
    # use intent-correct write-pattern regex tests instead, mirroring the
    # Phase 07 plan-01 deviation #2 fix.

    def test_K5_handler_cmd_glossary_append(self):
        """Phase 08 TEACH-A3: glossary append handler must not WRITE to
        summary / plan / schedule decision artifacts."""
        import re as _re
        src = inspect.getsource(cmd_glossary_append)
        for pat in _WRITE_PATTERNS_FORBIDDEN:
            self.assertFalse(
                _re.search(pat, src),
                f"K5 violation in cmd_glossary_append: write pattern {pat!r} found in source",
            )

    def test_K5_module_glossary(self):
        """Phase 08 TEACH-A3: agent/glossary.py source must not contain WRITE
        patterns targeting decision artifacts. The literal substring
        'summary.md' is permitted ONLY inside the slug-link bullet template
        (output to the glossary accumulator file, not a write to the
        per-slug summary). The literals 'plan.md' / 'schedule.json' have no
        legitimate use and are forbidden entirely."""
        import re as _re
        here = Path(__file__).parent.parent
        src = (here / "agent/glossary.py").read_text(encoding="utf-8")
        # Forbid literal "plan.md" and "schedule.json" entirely (no legitimate use)
        for forbidden in ("plan.md", "schedule.json"):
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: agent/glossary.py contains forbidden literal {forbidden!r}",
            )
        # For "summary.md": forbid any WRITE pattern targeting it.
        for pat in _WRITE_PATTERNS_FORBIDDEN:
            self.assertFalse(
                _re.search(pat, src),
                f"K5 violation: agent/glossary.py write pattern {pat!r} matches source",
            )

    def test_K5_glossary_append_writes_only_to_accumulator(self):
        """Behavioral K5 check: a glossary_append call only mutates the
        glossary file, never any per-slug summary / plan / schedule artifact
        in the same output dir."""
        import tempfile
        from agent.glossary import glossary_append, GLOSSARY_FILENAME
        with tempfile.TemporaryDirectory(
            dir=str(Path(__file__).parent / "_tmp_glossary"),
        ) as td:
            td_path = Path(td)
            # Pre-create fake per-slug artifacts to guard against accidental writes
            (td_path / "BVfake").mkdir()
            fake_summary = td_path / "BVfake" / ("summary" + ".md")
            fake_summary.write_text("ORIGINAL\n", encoding="utf-8")
            fake_plan = td_path / "BVfake" / ("plan" + ".md")
            fake_plan.write_text("ORIGINAL\n", encoding="utf-8")
            fake_schedule = td_path / "BVfake" / ("schedule" + ".json")
            fake_schedule.write_text("ORIGINAL\n", encoding="utf-8")
            glossary_append(
                slug="BVfake", term="TestTerm (Test)",
                definition="A definition.",
                output_dir=str(td_path),
            )
            # Assertion: only the glossary accumulator was created/modified
            self.assertTrue((td_path / GLOSSARY_FILENAME).exists())
            self.assertEqual(fake_summary.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertEqual(fake_plan.read_text(encoding="utf-8"), "ORIGINAL\n")
            self.assertEqual(fake_schedule.read_text(encoding="utf-8"), "ORIGINAL\n")

    # ── Phase 09 CORR-03a K5 boundary tests for summary_lint ──
    # Cannot extend FORBIDDEN_LITERALS tuple because the literal `summary.md`
    # legitimately appears in (a) argparse help text and (b) the input arg
    # path receiver. We use intent-correct write-pattern regex tests instead,
    # mirroring the Phase 08-01 agent/glossary.py exception.

    def test_K5_handler_cmd_summary_lint(self):
        """Phase 09 CORR-03a: summary_lint handler must not WRITE to
        summary / plan / schedule decision artifacts."""
        import re as _re
        src = inspect.getsource(cmd_summary_lint)
        for pat in _WRITE_PATTERNS_FORBIDDEN:
            self.assertFalse(
                _re.search(pat, src),
                f"K5 violation in cmd_summary_lint: write pattern {pat!r} found in source",
            )

    def test_K5_module_summary_lint(self):
        """Phase 09 CORR-03a: agent/summary_lint.py source must not contain
        WRITE patterns targeting decision artifacts. The literal substring
        `summary.md` is permitted ONLY as the input arg in lint_summary's
        signature + as the LINT_FILENAME sibling-naming context. The literals
        `plan.md` / `schedule.json` have no legitimate use and are forbidden
        entirely."""
        import re as _re
        here = Path(__file__).parent.parent
        src = (here / "agent/summary_lint.py").read_text(encoding="utf-8")
        for forbidden in ("plan.md", "schedule.json"):
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: agent/summary_lint.py contains forbidden literal {forbidden!r}",
            )
        for pat in _WRITE_PATTERNS_FORBIDDEN:
            self.assertFalse(
                _re.search(pat, src),
                f"K5 violation: agent/summary_lint.py write pattern {pat!r} matches source",
            )

    # ── Phase 10 D-06 K5 boundary tests ──

    def test_topics_bootstrap_no_index_json_writes(self):
        """Phase 10 D-06.1: cmd_topics_bootstrap source has no `index.json`,
        `summary.md`, `plan.md`, `schedule.json` literals (writes ONLY
        the topics governance file)."""
        src = inspect.getsource(cmd_topics_bootstrap)
        for forbidden in ("index.json", "summary.md", "plan.md", "schedule.json"):
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: cmd_topics_bootstrap mentions {forbidden!r}",
            )

    def test_topics_audit_no_writes(self):
        """Phase 10 D-06.1: cmd_topics_audit must be read-only —
        forbid any write API pattern (the literal `index.json` is fine
        because audit READS them)."""
        import re as _re
        src = inspect.getsource(cmd_topics_audit)
        write_patterns = (
            r"\.write_text\(", r"\.write_bytes\(",
            r"open\([^)]*['\"][aw]",
            r"os\.replace\(",
            r"_atomic_write\(", r"write_json_atomic\(",
        )
        for pat in write_patterns:
            self.assertFalse(
                _re.search(pat, src),
                f"K5 violation: cmd_topics_audit must be read-only; "
                f"pattern {pat!r} found",
            )

    def test_topics_resolve_only_writes_topics_md_and_index_json(self):
        """Phase 10 D-06.1: cmd_topics_resolve may write the topics governance
        file and per-slug index sidecars; D-29 core artifacts are forbidden."""
        import re as _re
        src = inspect.getsource(cmd_topics_resolve)
        for pat in _RESOLVE_FORBIDDEN_PATTERNS:
            self.assertFalse(
                _re.search(pat, src),
                f"K5 violation: cmd_topics_resolve write pattern {pat!r} found",
            )

    def test_topics_module_no_summary_writes(self):
        """Phase 10 D-06.1: agent/topics.py module source must NOT contain
        the literals `summary.md`, `plan.md`, `paragraphs.json`, `segs.json`,
        `meta.json`, `schedule.json`. The literals `_topics.md` and
        `index.json` are LEGITIMATE here."""
        here = Path(__file__).parent.parent
        src = (here / "agent" / "topics.py").read_text(encoding="utf-8")
        forbidden_literals = (
            "summary.md", "plan.md", "paragraphs.json",
            "segs.json", "meta.json", "schedule.json",
        )
        for forbidden in forbidden_literals:
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: agent/topics.py contains forbidden literal "
                f"{forbidden!r}",
            )
        import re as _re
        for pat in _RESOLVE_FORBIDDEN_PATTERNS:
            self.assertFalse(
                _re.search(pat, src),
                f"K5 violation: agent/topics.py write pattern {pat!r} found",
            )

    # ── Phase 11 D-10.1 K5 boundary tests for agent/index.py + cmd_index_* ──

    def test_K5_module_index_no_summary_writes(self):
        """Phase 11 D-10.1: agent/index.py module source must NOT contain the
        5 D-29 core literals (`summary.md`, `plan.md`, `paragraphs.json`,
        `segs.json`, `meta.json`). The literals `index.json` (own write
        target) and `_topics.md` (Phase 10 dependency) ARE legitimate.

        Note: `cmd_index_write` and `cmd_index_rebuild` handler-level K5 tests
        are added in Plan 11-01 Task 2 (when the handlers ship in
        `agent/tools.py`). This test ships in Task 1 since the module is
        the Wave 0 deliverable.
        """
        here = Path(__file__).parent.parent
        src = (here / "agent" / "index.py").read_text(encoding="utf-8")
        forbidden_literals = (
            "summary.md", "plan.md", "paragraphs.json",
            "segs.json", "meta.json",
        )
        for forbidden in forbidden_literals:
            self.assertNotIn(
                forbidden, src,
                f"K5 violation: agent/index.py contains forbidden literal "
                f"{forbidden!r}",
            )


if __name__ == "__main__":
    unittest.main()
