"""Phase 11 KB-01/03/04/05 tests: per-slug index sidecar + top-level aggregator.

Mirrors tests/test_topics.py shape (setUp/tearDown ASCII-safe tmpdir under
tests/_tmp_index/, multiprocessing race test for write_per_slug_index).

Test classes:
  TestValidate       - KB-01 8-field schema validator behavior
  TestReadWrite      - KB-01/04 read_per_slug_index + write_per_slug_index
  TestRebuild        - KB-04/05 aggregator rebuild + stale + skip-on-malformed
  TestGlossaryH2     - KB-03 _glossary.md H2 anchor extraction (vacuous-empty)
  TestAtomic         - concurrency: 2-process write race
"""
from __future__ import annotations

import io
import json
import multiprocessing as mp
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from agent.index import (
    validate_per_slug_index,
    read_per_slug_index,
    write_per_slug_index,
    rebuild_aggregator,
    read_aggregator,
    glossary_h2_anchors,
    IndexValidationError,
    INDEX_FILENAME,
    AGGREGATOR_FILENAME,
    LOCK_FILENAME,
    VALID_MODES,
    REQUIRED_FIELDS,
)
from agent._lock import FileLock, LockContended


# Minimal Phase 10 _topics.md fixture (Approved: 2 categories with subtopics).
_TOPICS_FIXTURE = """\
# Topics Taxonomy

> v1.2 knowledge-base governance.

## Approved Taxonomy

- LLM
  - LoRA
  - RAG
- AI-Tooling
  - Claude-Code

## Pending

<!-- (Claude 申请新 topic 时由 Phase 11 generator 在此 append H3 entry) -->
"""


def _ascii_tmpdir_root() -> Path:
    """Per-test tmpdir under tests/_tmp_index/ (ASCII-safe per Phase 10 D-19;
    Windows zh-CN GBK code-page would corrupt subprocess paths if we used
    %TEMP% which contains the user's CJK profile name).
    """
    root = Path(__file__).parent / "_tmp_index"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _make_minimal_index(slug="BVtest", mode="replicate-guide", topics=None):
    """Construct a minimal valid 8-field index dict."""
    return {
        "slug": slug,
        "title": "Test video",
        "duration_s": 10.0,
        "mode": mode,
        "topics": list(topics) if topics is not None else [],
        "keywords": [],
        "tldr_oneliner": "smoke",
        "chapters": [],
    }


class IndexBaseTest(unittest.TestCase):
    """Common setUp / tearDown: ASCII-safe tmpdir under tests/_tmp_index/."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(
            prefix="idx_", dir=str(_ascii_tmpdir_root()),
        )
        self.tmpdir = Path(self._tmp.name)
        # Phase 10 _topics.md fixture - required by write_per_slug_index for
        # whitelist enforcement (and by the pending-append path).
        (self.tmpdir / "_topics.md").write_text(
            _TOPICS_FIXTURE, encoding="utf-8",
        )

    def tearDown(self):
        try:
            self._tmp.cleanup()
        except Exception:
            pass


class TestValidate(unittest.TestCase):
    """KB-01: 8-field schema validator (no disk access required)."""

    def test_missing_required_field_raises(self):
        for missing in REQUIRED_FIELDS:
            d = _make_minimal_index()
            d.pop(missing)
            with self.assertRaises(IndexValidationError) as ctx:
                validate_per_slug_index(d)
            self.assertIn(missing, str(ctx.exception))

    def test_all_4_modes_accepted(self):
        for m in VALID_MODES:
            d = _make_minimal_index(mode=m)
            validate_per_slug_index(d)  # must not raise

    def test_replicate_guide_fallback_accepted(self):
        """Pitfall 2 / A4: 17 archives lack plan.md; backfill defaults to
        'replicate-guide'. Validator must accept this canonical fallback.
        """
        d = _make_minimal_index(mode="replicate-guide")
        validate_per_slug_index(d)

    def test_invalid_mode_rejected(self):
        d = _make_minimal_index(mode="wrong-mode")
        with self.assertRaises(IndexValidationError) as ctx:
            validate_per_slug_index(d)
        self.assertIn("mode", str(ctx.exception))

    def test_topics_must_be_list(self):
        d = _make_minimal_index()
        d["topics"] = "not-a-list"
        with self.assertRaises(IndexValidationError):
            validate_per_slug_index(d)

    def test_pending_topic_accepted_unconditionally(self):
        d = _make_minimal_index(topics=["pending: NewTopic"])
        # Even with a strict whitelist, pending: prefix bypasses.
        validate_per_slug_index(d, approved_topics={"LLM", "AI-Tooling"})

    def test_topic_not_in_whitelist_rejected_with_set(self):
        d = _make_minimal_index(topics=["NotApproved"])
        with self.assertRaises(IndexValidationError) as ctx:
            validate_per_slug_index(d, approved_topics={"LLM", "AI-Tooling"})
        self.assertIn("NotApproved", str(ctx.exception))

    def test_topic_not_in_whitelist_accepted_without_set(self):
        d = _make_minimal_index(topics=["AnythingGoes"])
        # approved_topics=None -> no whitelist enforcement (used by rebuild)
        validate_per_slug_index(d, approved_topics=None)

    def test_chapters_missing_field_rejected(self):
        d = _make_minimal_index()
        d["chapters"] = [{"title": "ch1", "start": 0.0}]  # missing 'excerpt'
        with self.assertRaises(IndexValidationError) as ctx:
            validate_per_slug_index(d)
        msg = str(ctx.exception)
        self.assertIn("chapters[0]", msg)
        self.assertIn("excerpt", msg)

    def test_chapter_start_must_be_number(self):
        d = _make_minimal_index()
        d["chapters"] = [{"title": "ch1", "start": "not-a-number", "excerpt": "x"}]
        with self.assertRaises(IndexValidationError) as ctx:
            validate_per_slug_index(d)
        self.assertIn("start", str(ctx.exception))

    def test_duration_int_and_float_accepted_string_rejected(self):
        d_int = _make_minimal_index()
        d_int["duration_s"] = 42
        validate_per_slug_index(d_int)  # int OK

        d_float = _make_minimal_index()
        d_float["duration_s"] = 42.0
        validate_per_slug_index(d_float)  # float OK

        d_str = _make_minimal_index()
        d_str["duration_s"] = "42"
        with self.assertRaises(IndexValidationError):
            validate_per_slug_index(d_str)

    def test_non_dict_input_rejected(self):
        with self.assertRaises(IndexValidationError):
            validate_per_slug_index([])
        with self.assertRaises(IndexValidationError):
            validate_per_slug_index("not-a-dict")


class TestReadWrite(IndexBaseTest):
    """KB-01/04: read_per_slug_index + write_per_slug_index round-trip."""

    def _slug_dir(self, name="BVtest"):
        sd = self.tmpdir / name
        sd.mkdir(parents=True, exist_ok=True)
        return sd

    def test_read_missing_returns_none(self):
        sd = self._slug_dir()
        self.assertIsNone(read_per_slug_index(sd))

    def test_read_corrupt_returns_none(self):
        sd = self._slug_dir()
        (sd / INDEX_FILENAME).write_text("{not json", encoding="utf-8")
        self.assertIsNone(read_per_slug_index(sd))

    def test_read_valid_returns_dict(self):
        sd = self._slug_dir()
        d = _make_minimal_index(slug="BVtest")
        write_per_slug_index(sd, d, output_dir=self.tmpdir)
        loaded = read_per_slug_index(sd)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["slug"], "BVtest")

    def test_write_invalid_schema_raises_no_file(self):
        sd = self._slug_dir()
        bad = _make_minimal_index()
        bad.pop("tldr_oneliner")
        with self.assertRaises(IndexValidationError):
            write_per_slug_index(sd, bad, output_dir=self.tmpdir)
        self.assertFalse((sd / INDEX_FILENAME).exists())

    def test_write_unapproved_topic_rejected_unless_force(self):
        sd = self._slug_dir()
        d = _make_minimal_index(topics=["NotApproved"])
        with self.assertRaises(IndexValidationError):
            write_per_slug_index(sd, d, output_dir=self.tmpdir)
        # With force=True, whitelist enforcement is skipped.
        write_per_slug_index(sd, d, output_dir=self.tmpdir, force=True)
        self.assertTrue((sd / INDEX_FILENAME).exists())

    def test_write_appends_pending_topic_to_topics_md(self):
        sd = self._slug_dir(name="BVpend")
        d = _make_minimal_index(slug="BVpend", topics=["pending: NewConcept"])
        result = write_per_slug_index(sd, d, output_dir=self.tmpdir)
        self.assertEqual(result["_topics_pending_appended"], ["NewConcept"])
        # Verify the H3 was appended to _topics.md
        topics_text = (self.tmpdir / "_topics.md").read_text(encoding="utf-8")
        self.assertIn("### NewConcept", topics_text)

    def test_idempotent_skip_on_byte_equal_stdin(self):
        sd = self._slug_dir(name="BVidem")
        d = _make_minimal_index(slug="BVidem")
        first = write_per_slug_index(sd, d, output_dir=self.tmpdir)
        self.assertEqual(first["action"], "written")
        second = write_per_slug_index(sd, d, output_dir=self.tmpdir)
        self.assertEqual(second["action"], "skipped")

    def test_per_slug_write_triggers_aggregator_rebuild(self):
        sd = self._slug_dir(name="BVagg")
        d = _make_minimal_index(slug="BVagg")
        write_per_slug_index(sd, d, output_dir=self.tmpdir)
        agg = read_aggregator(self.tmpdir)
        self.assertIn("BVagg", agg)
        self.assertEqual(agg["BVagg"]["slug"], "BVagg")

    def test_aggregator_lexicographic_ordering(self):
        for name in ["BVc", "BVa", "BVb"]:
            sd = self._slug_dir(name=name)
            d = _make_minimal_index(slug=name)
            write_per_slug_index(sd, d, output_dir=self.tmpdir)
        agg = read_aggregator(self.tmpdir)
        self.assertEqual(list(agg.keys()), ["BVa", "BVb", "BVc"])


class TestRebuild(IndexBaseTest):
    """KB-04/05: rebuild_aggregator: empty / skip-on-malformed / stale /
    hidden-dir exclusion / idempotent."""

    def _make_per_slug(self, slug, content_dict=None, force=True):
        sd = self.tmpdir / slug
        sd.mkdir(parents=True, exist_ok=True)
        d = content_dict or _make_minimal_index(slug=slug)
        write_per_slug_index(sd, d, output_dir=self.tmpdir, force=force)
        return sd

    def test_empty_output_dir_returns_zero_no_skipped(self):
        # Nothing under tmpdir except _topics.md
        result = rebuild_aggregator(self.tmpdir)
        self.assertEqual(result["slugs_included"], 0)
        self.assertEqual(result["slugs_skipped"], [])
        self.assertEqual(result["stale_detected"], [])
        # Aggregator file written as `{}`.
        agg_text = (self.tmpdir / AGGREGATOR_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(json.loads(agg_text), {})

    def test_skip_on_malformed_per_slug(self):
        # Create 2 valid + 1 corrupt
        self._make_per_slug("BVgood1")
        self._make_per_slug("BVgood2")
        bad_dir = self.tmpdir / "BVbad"
        bad_dir.mkdir()
        (bad_dir / INDEX_FILENAME).write_text("{not json", encoding="utf-8")
        # Rebuild
        result = rebuild_aggregator(self.tmpdir)
        self.assertEqual(result["slugs_included"], 2)
        skipped_slugs = [s["slug"] for s in result["slugs_skipped"]]
        self.assertIn("BVbad", skipped_slugs)
        # Reason mentions schema or unreadable (json decode error)
        bad_entry = [s for s in result["slugs_skipped"] if s["slug"] == "BVbad"][0]
        self.assertTrue(
            "unreadable" in bad_entry["reason"]
            or "schema" in bad_entry["reason"]
        )

    def test_skip_on_schema_invalid_per_slug(self):
        # Create one with broken schema (missing field after manual edit)
        sd = self.tmpdir / "BVschemabad"
        sd.mkdir()
        (sd / INDEX_FILENAME).write_text(
            json.dumps({"slug": "BVschemabad"}), encoding="utf-8",
        )
        result = rebuild_aggregator(self.tmpdir)
        skipped_slugs = [s["slug"] for s in result["slugs_skipped"]]
        self.assertIn("BVschemabad", skipped_slugs)
        bad_entry = [s for s in result["slugs_skipped"] if s["slug"] == "BVschemabad"][0]
        self.assertIn("schema invalid", bad_entry["reason"])

    def test_stale_detection(self):
        # Create one valid, then bump its mtime past the aggregator's.
        sd = self._make_per_slug("BVstale")
        ip = sd / INDEX_FILENAME
        # Sleep tiny amount then touch per-slug to be newer than aggregator
        time.sleep(0.05)
        future = time.time() + 60
        os.utime(ip, (future, future))
        result = rebuild_aggregator(self.tmpdir)
        self.assertIn("BVstale", result["stale_detected"])

    def test_hidden_dirs_excluded(self):
        # Create a per-slug under a `_archive` dir (hidden / ignored)
        underscore = self.tmpdir / "_archive"
        underscore.mkdir()
        (underscore / INDEX_FILENAME).write_text(
            json.dumps(_make_minimal_index(slug="_archive")),
            encoding="utf-8",
        )
        # Also one under a `.dot` dir
        dotdir = self.tmpdir / ".hidden"
        dotdir.mkdir()
        (dotdir / INDEX_FILENAME).write_text(
            json.dumps(_make_minimal_index(slug=".hidden")),
            encoding="utf-8",
        )
        # And one valid normal slug
        self._make_per_slug("BVok")
        result = rebuild_aggregator(self.tmpdir)
        agg = read_aggregator(self.tmpdir)
        self.assertIn("BVok", agg)
        self.assertNotIn("_archive", agg)
        self.assertNotIn(".hidden", agg)

    def test_idempotent_double_rebuild(self):
        self._make_per_slug("BVa")
        self._make_per_slug("BVb")
        rebuild_aggregator(self.tmpdir)
        agg_text_1 = (self.tmpdir / AGGREGATOR_FILENAME).read_text(encoding="utf-8")
        rebuild_aggregator(self.tmpdir)
        agg_text_2 = (self.tmpdir / AGGREGATOR_FILENAME).read_text(encoding="utf-8")
        self.assertEqual(agg_text_1, agg_text_2)


class TestGlossaryH2(IndexBaseTest):
    """KB-03: glossary_h2_anchors helper + read_aggregator robustness."""

    def test_missing_glossary_returns_empty_list(self):
        gp = self.tmpdir / "_glossary.md"
        # gp does not exist (Pitfall 3 vacuously-empty case)
        self.assertEqual(glossary_h2_anchors(gp), [])

    def test_extracts_h2_anchors_byte_equal_canonical(self):
        gp = self.tmpdir / "_glossary.md"
        gp.write_text(
            "# Glossary\n\n"
            "## LoRA (Low-Rank Adaptation)\n"
            "- [BVxxx](BVxxx/summary.md)\n\n"
            "## RAG (Retrieval-Augmented Generation)\n"
            "definition.\n\n"
            "### sub-anchor\nshould not match\n",
            encoding="utf-8",
        )
        anchors = glossary_h2_anchors(gp)
        self.assertEqual(
            anchors,
            ["LoRA (Low-Rank Adaptation)", "RAG (Retrieval-Augmented Generation)"],
        )

    def test_h3_not_matched(self):
        gp = self.tmpdir / "_glossary.md"
        gp.write_text(
            "## Real-H2\n### Fake-H3\n#### Fake-H4\n",
            encoding="utf-8",
        )
        self.assertEqual(glossary_h2_anchors(gp), ["Real-H2"])

    def test_trailing_whitespace_trimmed(self):
        gp = self.tmpdir / "_glossary.md"
        gp.write_text("## LoRA   \n## RAG\t\n", encoding="utf-8")
        self.assertEqual(glossary_h2_anchors(gp), ["LoRA", "RAG"])

    def test_read_aggregator_missing_returns_empty(self):
        self.assertEqual(read_aggregator(self.tmpdir), {})

    def test_read_aggregator_corrupt_returns_empty(self):
        (self.tmpdir / AGGREGATOR_FILENAME).write_text(
            "{not json", encoding="utf-8",
        )
        self.assertEqual(read_aggregator(self.tmpdir), {})


def _child_write(slug, tmpdir_str, q):
    """multiprocessing target - write_per_slug_index in a child process."""
    try:
        sd = Path(tmpdir_str) / slug
        sd.mkdir(parents=True, exist_ok=True)
        d = _make_minimal_index(slug=slug)
        r = write_per_slug_index(sd, d, output_dir=Path(tmpdir_str), timeout=15.0)
        q.put(("ok", r["action"]))
    except Exception as e:
        q.put(("error", repr(e)))


class TestAtomic(IndexBaseTest):
    """Concurrency: 2-process write race + lock contention bounds."""

    def test_concurrent_writes_different_slugs_both_succeed(self):
        # Spawn 2 child processes writing different slugs simultaneously.
        ctx = mp.get_context("spawn")
        q1 = ctx.Queue()
        q2 = ctx.Queue()
        p1 = ctx.Process(target=_child_write, args=("BVa", str(self.tmpdir), q1))
        p2 = ctx.Process(target=_child_write, args=("BVb", str(self.tmpdir), q2))
        p1.start()
        p2.start()
        p1.join(timeout=30)
        p2.join(timeout=30)
        self.assertFalse(p1.is_alive())
        self.assertFalse(p2.is_alive())
        r1 = q1.get(timeout=5)
        r2 = q2.get(timeout=5)
        self.assertEqual(r1[0], "ok", f"child 1: {r1}")
        self.assertEqual(r2[0], "ok", f"child 2: {r2}")
        # Aggregator should contain both slugs.
        agg = read_aggregator(self.tmpdir)
        self.assertIn("BVa", agg)
        self.assertIn("BVb", agg)


if __name__ == "__main__":
    unittest.main()
