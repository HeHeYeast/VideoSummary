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
)

FORBIDDEN_LITERALS = ("summary.md", "plan.md", "schedule.json")


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


if __name__ == "__main__":
    unittest.main()
