"""Tests for agent/_v11.py — Phase 07 PRE-V11-01.

Stdlib unittest only (Phase 2 RESEARCH precedent: pytest is not in default deps).
Mirrors tests/test_lock.py style: per-test TemporaryDirectory under
tests/_tmp_v11/ for ASCII-safe paths on zh-CN Windows hosts.

Coverage (10 tests, mapped 1:1 to plan <behavior> block):
  T1  is_v11_enabled returns False on missing marker
  T2  is_v11_enabled returns True when marker has non-empty features list
  T3  is_v11_enabled returns False when features_enabled is empty list
  T4  set_v11_marker writes valid JSON with version=1 + features + ISO timestamp
  T5  set_v11_marker is idempotent on same input (modulo marker_set_at)
  T6  set_v11_marker rejects unknown feature names with ValueError listing allowed names
  T7  get_v11_marker returns dict on success, None on missing
  T8  Corrupt JSON in marker -> get_v11_marker returns None silently
  T9  Marker file lives at <slug_dir>/.v11_features.json (exact path)
  T10 V11_FEATURES exposes locked allowlist of 8 names
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from agent._v11 import (
    MARKER_FILENAME,
    V11_FEATURES,
    get_v11_marker,
    is_v11_enabled,
    set_v11_marker,
)


def _ascii_tmpdir_root() -> str:
    """Mirror tests/test_lock.py: zh-CN Windows %TEMP% has CJK in username,
    which clutters error paths. Pick an ASCII-safe location under tests/."""
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_v11"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


class TestV11Marker(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.slug = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    # ---- T1 ----
    def test_T01_is_v11_enabled_false_on_missing_marker(self):
        self.assertFalse(is_v11_enabled(self.slug))
        self.assertFalse((self.slug / MARKER_FILENAME).exists())

    # ---- T2 ----
    def test_T02_is_v11_enabled_true_when_features_nonempty(self):
        set_v11_marker(self.slug, ["transcribe_lint"])
        self.assertTrue(is_v11_enabled(self.slug))

    # ---- T3 ----
    def test_T03_is_v11_enabled_false_when_features_empty(self):
        # write the marker manually with an empty list so we don't have to
        # bypass the (legitimate) allowlist check in set_v11_marker.
        target = self.slug / MARKER_FILENAME
        target.write_text(
            json.dumps({"version": 1, "features_enabled": [], "marker_set_at": "x"}),
            encoding="utf-8",
        )
        self.assertFalse(is_v11_enabled(self.slug))
        # also: feature-specific gating still returns False
        self.assertFalse(is_v11_enabled(self.slug, "transcribe_lint"))

    # ---- T4 ----
    def test_T04_set_v11_marker_writes_valid_schema(self):
        set_v11_marker(self.slug, ["transcribe_lint"])
        marker = json.loads(
            (self.slug / MARKER_FILENAME).read_text(encoding="utf-8")
        )
        self.assertEqual(marker["version"], 1)
        self.assertEqual(marker["features_enabled"], ["transcribe_lint"])
        self.assertIn("marker_set_at", marker)
        # crude ISO-8601 sanity check (matches now_iso() output)
        ts = marker["marker_set_at"]
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    # ---- T5 ----
    def test_T05_set_v11_marker_idempotent_modulo_timestamp(self):
        set_v11_marker(self.slug, ["transcribe_lint", "mode_signals"])
        first = json.loads((self.slug / MARKER_FILENAME).read_text(encoding="utf-8"))
        # Re-call with identical input.
        set_v11_marker(self.slug, ["transcribe_lint", "mode_signals"])
        second = json.loads((self.slug / MARKER_FILENAME).read_text(encoding="utf-8"))
        # version + features identical
        self.assertEqual(first["version"], second["version"])
        self.assertEqual(first["features_enabled"], second["features_enabled"])
        # marker_set_at may differ (overwritten on each call) — that's the only allowed drift
        self.assertIn("marker_set_at", second)

    # ---- T6 ----
    def test_T06_set_v11_marker_rejects_unknown_feature(self):
        with self.assertRaises(ValueError) as ctx:
            set_v11_marker(self.slug, ["transcribe_lint", "definitely_not_a_real_feature"])
        msg = str(ctx.exception)
        self.assertIn("unknown v11 features", msg)
        self.assertIn("definitely_not_a_real_feature", msg)
        # Marker must NOT have been created when validation fails.
        self.assertFalse((self.slug / MARKER_FILENAME).exists())

    # ---- T7 ----
    def test_T07_get_v11_marker_returns_dict_or_none(self):
        # missing
        self.assertIsNone(get_v11_marker(self.slug))
        # present
        set_v11_marker(self.slug, ["mode_signals"])
        obj = get_v11_marker(self.slug)
        self.assertIsInstance(obj, dict)
        self.assertEqual(obj["features_enabled"], ["mode_signals"])

    # ---- T8 ----
    def test_T08_corrupt_json_returns_none_silently(self):
        target = self.slug / MARKER_FILENAME
        # stray non-JSON file (e.g., from manual experimentation)
        target.write_text("not json{", encoding="utf-8")
        # MUST NOT raise; treats corrupt marker as "no marker" (silent v1.0 path).
        result = get_v11_marker(self.slug)
        self.assertIsNone(result)
        # is_v11_enabled also tolerates the corrupt marker
        self.assertFalse(is_v11_enabled(self.slug))

    # ---- T9 ----
    def test_T09_marker_path_is_dot_v11_features_json(self):
        set_v11_marker(self.slug, ["glossary"])
        # Exact filename — not v11_features.json (no dot), not .v11.json (short)
        self.assertTrue((self.slug / ".v11_features.json").exists())
        self.assertFalse((self.slug / "v11_features.json").exists())
        self.assertFalse((self.slug / ".v11.json").exists())
        self.assertEqual(MARKER_FILENAME, ".v11_features.json")

    # ---- T10 ----
    def test_T10_v11_features_locked_allowlist(self):
        # Phase 07 names (locked, MUST remain for backward-compat):
        phase_07_names = (
            "transcribe_lint",
            "mode_signals",
            "schedule_suggest",
            "trace_tokens",
            "self_contained_header",
            "glossary",
            "tldr",
            "verifier",
        )
        # Phase 08 NEW names (explicit aliases referenced by CLAUDE.md prompt
        # extensions; self_contained_header is reused not duplicated):
        phase_08_names = (
            "inline_trace_tokens",
            "self_check_confidence",
            "cross_slug_glossary",
            "tldr_speedrun",
            "l2_l3_correction",
        )
        # Phase 09 ADD (this plan extends 13 → 15):
        phase_09_names = (
            "summary_lint",       # CORR-03a — mechanical lint CLI explicit name
            "verifier_phase_75",  # CORR-03b/c — Phase 7.5 verifier subagent
        )
        # tuple OR list — both acceptable; we check membership + count.
        # Phase 09 extension: 8 Phase 07 + 5 Phase 08 + 2 NEW Phase 09 = 15 entries.
        self.assertEqual(len(V11_FEATURES), 15)
        for f in phase_07_names:
            self.assertIn(f, V11_FEATURES, f"Phase 07 name {f} must remain (backward-compat)")
        for f in phase_08_names:
            self.assertIn(f, V11_FEATURES, f"Phase 08 name {f} must remain (backward-compat)")
        for f in phase_09_names:
            self.assertIn(f, V11_FEATURES, f"Phase 09 name {f} must be added")


if __name__ == "__main__":
    unittest.main()
