"""Smoke test for scripts/replay_v10_archives.py — Phase 07 PRE-V11-02.

Stdlib unittest only (Phase 2 RESEARCH precedent: pytest is not in default deps).

Tests:
  T1: Script importable; main() callable
  T2: --slug pointing at non-existent dir -> SKIP not crash
  T3: Synthetic archive (write minimal v10-shape segs.json + paragraphs.json
      + meta.json + summary.md to a temp dir; verify replay PASS)
  T4: Mutate the synthetic paragraphs.json by 1 byte -> replay returns FAIL
      with non-zero diffs list
  T5: Synthetic dir with .v11_features.json marker -> SKIP (not run)
  T6: Synthetic archive with `paragraphs.json.params.json` sidecar declaring
      `cli.profile = "podcast"` -> _load_profile_for_slug returns PROFILES["podcast"]
      (NOT tutorial -- proves the false-FAIL fix from B2 is wired)
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Add repo root so `from scripts.replay_v10_archives import ...` works
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import replay_v10_archives as rep
from agent._v11 import set_v11_marker
from agent.asr_v2 import PROFILES, aggregate_paragraphs, paragraphs_to_dicts
from agent.io import write_json_atomic


def _ascii_tmpdir_root() -> str:
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_replay"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


# Minimal valid 3-segment input that produces a non-empty paragraph list.
# Indices/keys match what `agent.io.load_segs` accepts (top-level list of dicts).
_SAMPLE_SEGS = [
    {"id": 0, "start": 0.0, "end": 5.0, "text": "hello world this is a test"},
    {"id": 1, "start": 5.5, "end": 10.0, "text": "second segment continues"},
    {"id": 2, "start": 10.5, "end": 15.0, "text": "and a third one ends here"},
]


def _bake_baseline_archive(slug_dir: Path, *, profile: str = "tutorial") -> None:
    """Write a synthetic v1.0-shape archive into slug_dir.

    Calls the same aggregate_paragraphs() + paragraphs_to_dicts() the replay
    script will call, then write_json_atomic — so bytes are guaranteed
    identical to what replay produces (no spurious FAIL from indent/encoding
    drift).
    """
    slug_dir.mkdir(parents=True, exist_ok=True)
    # segs.json
    write_json_atomic(slug_dir / "segs.json", _SAMPLE_SEGS)
    # paragraphs.json — generated identically to the replay path.
    p = PROFILES[profile]
    paras = aggregate_paragraphs(
        _SAMPLE_SEGS,
        gap_threshold=p["gap_threshold"],
        max_para_duration=p["max_para_duration"],
        sentence_gap=p["sentence_gap"],
    )
    write_json_atomic(slug_dir / "paragraphs.json", paragraphs_to_dicts(paras))
    # meta.json + summary.md — opaque blobs the replay only hashes
    write_json_atomic(slug_dir / "meta.json", {"slug": slug_dir.name, "title": "synthetic"})
    (slug_dir / "summary.md").write_text("# Synthetic baseline\n", encoding="utf-8")


class TestReplayV10(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    # ---- T1 ----
    def test_T1_script_importable_and_main_callable(self):
        self.assertTrue(callable(rep.main))
        self.assertTrue(callable(rep._replay_one))
        self.assertTrue(callable(rep._load_profile_for_slug))
        self.assertTrue(callable(rep._is_candidate))

    # ---- T2 ----
    def test_T2_nonexistent_slug_skips_not_crash(self):
        # Output dir exists, but no slug subdirs at all.
        self.root.mkdir(exist_ok=True)
        rc = rep.main.__call__ if False else None  # placeholder
        # Use sys.argv injection instead.
        argv_backup = sys.argv[:]
        try:
            sys.argv = [
                "scripts.replay_v10_archives",
                "--output-dir", str(self.root),
                "--slug", "definitely_does_not_exist",
                "--json",
            ]
            # Capture stdout via redirect
            from io import StringIO
            from contextlib import redirect_stdout
            buf = StringIO()
            with redirect_stdout(buf):
                rc = rep.main()
            # rc==0 (no FAIL) is the success contract; the slug is reported in
            # `skipped[]` because it's not a directory.
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["summary"]["fail"], 0)
            self.assertEqual(payload["summary"]["pass"], 0)
            # Skipped list should contain the missing slug with a "not a directory" reason.
            self.assertEqual(len(payload["skipped"]), 1)
            self.assertEqual(payload["skipped"][0]["slug"], "definitely_does_not_exist")
            self.assertIn("not a directory", payload["skipped"][0]["reason"])
        finally:
            sys.argv = argv_backup

    # ---- T3 ----
    def test_T3_synthetic_archive_replay_pass(self):
        slug = self.root / "synthetic_pass"
        _bake_baseline_archive(slug, profile="tutorial")
        result = rep._replay_one(slug)
        self.assertEqual(
            result["status"], "PASS",
            f"expected PASS, got: {result}"
        )
        self.assertEqual(result["diffs"], [])
        # profile resolution: no sidecar -> "tutorial-fallback"
        self.assertEqual(result["profile"], "tutorial-fallback")

    # ---- T4 ----
    def test_T4_one_byte_mutation_yields_FAIL(self):
        slug = self.root / "synthetic_fail"
        _bake_baseline_archive(slug, profile="tutorial")
        # Mutate paragraphs.json by appending a single byte.
        paras_path = slug / "paragraphs.json"
        original = paras_path.read_bytes()
        paras_path.write_bytes(original + b" ")
        result = rep._replay_one(slug)
        self.assertEqual(result["status"], "FAIL", f"expected FAIL, got: {result}")
        self.assertGreater(len(result["diffs"]), 0)
        # First diff must be on paragraphs.json with a hash mismatch reason.
        diff = result["diffs"][0]
        self.assertEqual(diff["file"], "paragraphs.json")
        self.assertIn("byte mismatch", diff["reason"])

    # ---- T5 ----
    def test_T5_v11_marker_skips_candidate(self):
        slug = self.root / "synthetic_marked"
        _bake_baseline_archive(slug, profile="tutorial")
        # Mark this slug as v1.1 opt-in -> _is_candidate must return False.
        set_v11_marker(slug, ["transcribe_lint"])
        ok, reason = rep._is_candidate(slug)
        self.assertFalse(ok)
        self.assertIn(".v11_features.json marker", reason)

    # ---- T6 ----
    def test_T6_sidecar_podcast_resolves_to_podcast_profile(self):
        """Proves the B2 fix is wired: sidecar profile=podcast -> PROFILES['podcast']."""
        slug = self.root / "synthetic_podcast"
        _bake_baseline_archive(slug, profile="tutorial")  # baseline irrelevant for this test
        # Write a sidecar that says podcast.
        sidecar = slug / "paragraphs.json.params.json"
        sidecar.write_text(
            json.dumps({
                "cli": {"profile": "podcast", "gap": None},
                "func": {"profile": "podcast",
                         "gap_threshold": 2.5, "max_para_duration": 90.0,
                         "sentence_gap": 1.5},
                "tools": {},
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        resolved = rep._load_profile_for_slug(slug)
        self.assertEqual(
            resolved, PROFILES["podcast"],
            f"_load_profile_for_slug should return PROFILES['podcast'] when sidecar "
            f"declares cli.profile=podcast; got {resolved}",
        )
        # Also verify _resolved_profile_name reports "podcast" for transparency.
        self.assertEqual(rep._resolved_profile_name(slug), "podcast")
        # Pre-Phase-5 archives (no sidecar) should fall back to tutorial.
        slug_no_sidecar = self.root / "synthetic_no_sidecar"
        _bake_baseline_archive(slug_no_sidecar, profile="tutorial")
        self.assertEqual(rep._load_profile_for_slug(slug_no_sidecar), PROFILES["tutorial"])
        self.assertEqual(rep._resolved_profile_name(slug_no_sidecar), "tutorial-fallback")


if __name__ == "__main__":
    unittest.main()
