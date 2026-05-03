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


class TestCLIWriteEdges(IndexBaseTest):
    """Phase 11 Q-G: CLI subprocess edge cases for `index write` / `rebuild`."""

    def _run_cli(self, args, stdin=""):
        """Invoke `python -m agent.tools` with given argv + stdin; return CompletedProcess."""
        repo_root = Path(__file__).parent.parent
        return subprocess.run(
            [sys.executable, "-m", "agent.tools", *args],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            timeout=30,
        )

    def _make_slug_dir(self, name="BVcli"):
        sd = self.tmpdir / name
        sd.mkdir(parents=True, exist_ok=True)
        return sd

    def _valid_payload(self, slug):
        return json.dumps(_make_minimal_index(slug=slug))

    def test_missing_from_stdin_flag(self):
        self._make_slug_dir("BVcli1")
        r = self._run_cli([
            "index", "write", "--slug", "BVcli1",
            "--output-dir", str(self.tmpdir),
        ])
        self.assertEqual(r.returncode, 1)
        self.assertIn("--from-stdin", r.stderr)

    def test_empty_stdin(self):
        self._make_slug_dir("BVcli2")
        r = self._run_cli(
            ["index", "write", "--slug", "BVcli2",
             "--from-stdin", "--output-dir", str(self.tmpdir)],
            stdin="",
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("got empty", r.stderr)

    def test_malformed_json(self):
        self._make_slug_dir("BVcli3")
        r = self._run_cli(
            ["index", "write", "--slug", "BVcli3",
             "--from-stdin", "--output-dir", str(self.tmpdir)],
            stdin="{not json",
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("malformed JSON", r.stderr)

    def test_slug_mismatch(self):
        self._make_slug_dir("BVcli4")
        # stdin has slug=BVother but --slug=BVcli4 -> fail
        bad_payload = json.dumps(_make_minimal_index(slug="BVother"))
        r = self._run_cli(
            ["index", "write", "--slug", "BVcli4",
             "--from-stdin", "--output-dir", str(self.tmpdir)],
            stdin=bad_payload,
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("does not match", r.stderr)

    def test_slug_dir_not_found(self):
        # No mkdir of BVnoexist
        r = self._run_cli(
            ["index", "write", "--slug", "BVnoexist",
             "--from-stdin", "--output-dir", str(self.tmpdir)],
            stdin=self._valid_payload("BVnoexist"),
        )
        self.assertEqual(r.returncode, 1)
        self.assertIn("not found", r.stderr)

    def test_happy_path_writes_per_slug_and_aggregator(self):
        self._make_slug_dir("BVok")
        r = self._run_cli(
            ["index", "write", "--slug", "BVok", "--from-stdin",
             "--output-dir", str(self.tmpdir), "--json"],
            stdin=self._valid_payload("BVok"),
        )
        self.assertEqual(r.returncode, 0, f"stderr: {r.stderr}")
        out = json.loads(r.stdout)
        self.assertEqual(out["action"], "written")
        self.assertEqual(out["slug"], "BVok")
        # Per-slug + aggregator both written
        self.assertTrue((self.tmpdir / "BVok" / INDEX_FILENAME).exists())
        self.assertTrue((self.tmpdir / AGGREGATOR_FILENAME).exists())
        agg = json.loads(
            (self.tmpdir / AGGREGATOR_FILENAME).read_text(encoding="utf-8")
        )
        self.assertIn("BVok", agg)

    def test_rebuild_empty_dir(self):
        # Fresh tmp with only _topics.md - no slugs
        r = self._run_cli(
            ["index", "rebuild",
             "--output-dir", str(self.tmpdir), "--json"],
        )
        self.assertEqual(r.returncode, 0, f"stderr: {r.stderr}")
        out = json.loads(r.stdout)
        self.assertEqual(out["slugs_included"], 0)
        self.assertEqual(out["slugs_skipped"], [])

    def test_rebuild_zero_valid_with_skips_returncode_1(self):
        # Pre-create one corrupt per-slug; no valid -> returncode 1
        bad_dir = self.tmpdir / "BVbad"
        bad_dir.mkdir()
        (bad_dir / INDEX_FILENAME).write_text("{not json", encoding="utf-8")
        r = self._run_cli(
            ["index", "rebuild",
             "--output-dir", str(self.tmpdir), "--json"],
        )
        self.assertEqual(r.returncode, 1, f"stderr: {r.stderr}")
        out = json.loads(r.stdout)
        self.assertEqual(out["slugs_included"], 0)
        self.assertTrue(len(out["slugs_skipped"]) >= 1)


class TestScanArchivesForBackfill(unittest.TestCase):
    """Phase 12 D-01.2 / D-01.6: scan_archives_for_backfill behavior."""

    def setUp(self):
        self.scratch = (
            Path(__file__).parent / "_tmp_index"
            / f"scan_{self._testMethodName}"
        )
        if self.scratch.exists():
            import shutil
            shutil.rmtree(self.scratch)
        self.scratch.mkdir(parents=True)

    def _make_archive(self, slug, *, with_summary=True, summary_bytes=None,
                      with_index=False):
        d = self.scratch / slug
        d.mkdir(parents=True, exist_ok=True)
        if with_summary:
            sm = d / ("summa" "ry.md")
            if summary_bytes is not None:
                sm.write_bytes(summary_bytes)
            else:
                sm.write_text("# stub\n", encoding="utf-8")
        if with_index:
            idx = d / "index.json"
            idx.write_text('{"slug":"' + slug + '"}', encoding="utf-8")
        return d

    def test_finds_summary_dirs_and_excludes_underscores(self):
        from agent.index import scan_archives_for_backfill
        self._make_archive("bv001")
        self._make_archive("bv002")
        self._make_archive("bv003")
        self._make_archive("_internal")  # excluded
        self._make_archive(".cache")     # excluded
        result = scan_archives_for_backfill(self.scratch)
        self.assertEqual(result["action"], "scanned")
        self.assertEqual(result["total_slugs"], 3)
        self.assertEqual(result["to_backfill"], ["bv001", "bv002", "bv003"])
        self.assertEqual(result["skipped_existing"], [])
        self.assertEqual(result["failed"], [])
        self.assertTrue(result["_topics_path"].endswith("_topics.md"))
        self.assertIsNone(result["_glossary_path"])

    def test_skip_existing_index_unless_force(self):
        from agent.index import scan_archives_for_backfill
        self._make_archive("bv001", with_index=True)
        self._make_archive("bv002")
        # Without force
        r1 = scan_archives_for_backfill(self.scratch)
        self.assertEqual(r1["to_backfill"], ["bv002"])
        self.assertEqual(r1["skipped_existing"], ["bv001"])
        # With force
        r2 = scan_archives_for_backfill(self.scratch, force=True)
        self.assertEqual(r2["to_backfill"], ["bv001", "bv002"])
        self.assertEqual(r2["skipped_existing"], [])

    def test_corrupt_summary_lists_in_failed_not_to_backfill(self):
        from agent.index import scan_archives_for_backfill
        self._make_archive("bv001")
        self._make_archive(
            "bv004", with_summary=True, summary_bytes=b"\xff\xfe\xfd",
        )
        result = scan_archives_for_backfill(self.scratch)
        self.assertIn("bv001", result["to_backfill"])
        slugs_failed = [f["slug"] for f in result["failed"]]
        self.assertIn("bv004", slugs_failed)
        bv4 = next(f for f in result["failed"] if f["slug"] == "bv004")
        self.assertIn("not readable", bv4["reason"])

    def test_glossary_path_when_present(self):
        from agent.index import scan_archives_for_backfill
        self._make_archive("bv001")
        (self.scratch / "_glossary.md").write_text("# g\n", encoding="utf-8")
        result = scan_archives_for_backfill(self.scratch)
        self.assertEqual(
            result["_glossary_path"],
            str(self.scratch / "_glossary.md"),
        )

    def test_missing_output_dir_returns_empty(self):
        from agent.index import scan_archives_for_backfill
        bogus = self.scratch / "does_not_exist"
        result = scan_archives_for_backfill(bogus)
        self.assertEqual(result["total_slugs"], 0)
        self.assertEqual(result["to_backfill"], [])
        self.assertEqual(result["failed"], [])

    def test_dir_without_summary_not_detected_as_archive(self):
        """KB-13 boundary: a dir under output/ that has no slug-summary file
        is silently skipped (not an archive, not a failure)."""
        from agent.index import scan_archives_for_backfill
        self._make_archive("bv001")
        # bv002 dir exists but has no slug-summary file
        d = self.scratch / "bv002"
        d.mkdir()
        (d / "video.mp4").write_text("x", encoding="utf-8")
        result = scan_archives_for_backfill(self.scratch)
        self.assertEqual(result["to_backfill"], ["bv001"])
        # bv002 not in any list
        self.assertNotIn("bv002", result["to_backfill"])
        self.assertNotIn("bv002", result["skipped_existing"])
        slugs_failed = [f["slug"] for f in result["failed"]]
        self.assertNotIn("bv002", slugs_failed)


class TestSearchIndex(unittest.TestCase):
    """Phase 12 D-04: search_index substring match."""

    def setUp(self):
        self.scratch = (
            Path(__file__).parent / "_tmp_index"
            / f"search_{self._testMethodName}"
        )
        if self.scratch.exists():
            import shutil
            shutil.rmtree(self.scratch)
        self.scratch.mkdir(parents=True)

    def _seed_aggregator(self, entries):
        agg_path = self.scratch / ".index.json"
        agg_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_substring_match_in_title(self):
        from agent.index import search_index
        self._seed_aggregator({
            "douyin_karpathy_llm_wiki": {
                "slug": "douyin_karpathy_llm_wiki",
                "title": "Karpathy 又被吹爆",
                "duration_s": 242.0, "mode": "interview-distillation",
                "topics": ["LLM-Wiki"], "keywords": [],
                "tldr_oneliner": "x", "chapters": [],
            }
        })
        results = search_index("Karpathy", output_dir=self.scratch)
        self.assertEqual(len(results), 1)
        self.assertIn("title", results[0]["matched_fields"])

    def test_substring_match_in_chapter_excerpt(self):
        from agent.index import search_index
        self._seed_aggregator({
            "bv001": {
                "slug": "bv001", "title": "T", "duration_s": 1.0,
                "mode": "concept-explanation", "topics": [], "keywords": [],
                "tldr_oneliner": "y",
                "chapters": [{"title": "intro", "start": 0,
                              "excerpt": "ECS 之争"}],
            }
        })
        results = search_index("ECS", output_dir=self.scratch)
        self.assertEqual(len(results), 1)
        self.assertIn("chapters[0].excerpt", results[0]["matched_fields"])
        self.assertEqual(results[0]["chapter_hits"],
                         [{"title": "intro", "start": 0}])

    def test_case_insensitive(self):
        from agent.index import search_index
        self._seed_aggregator({
            "bv001": {
                "slug": "bv001", "title": "Karpathy LLM Wiki",
                "duration_s": 1.0, "mode": "concept-explanation",
                "topics": [], "keywords": [], "tldr_oneliner": "",
                "chapters": [],
            }
        })
        results = search_index("karpathy", output_dir=self.scratch)
        self.assertEqual(len(results), 1)

    def test_no_match_returns_empty(self):
        from agent.index import search_index
        self._seed_aggregator({
            "bv001": {
                "slug": "bv001", "title": "T", "duration_s": 1.0,
                "mode": "concept-explanation", "topics": [], "keywords": [],
                "tldr_oneliner": "", "chapters": [],
            }
        })
        results = search_index("nonexistent_xyz", output_dir=self.scratch)
        self.assertEqual(results, [])

    def test_empty_aggregator_returns_empty(self):
        from agent.index import search_index
        results = search_index("anything", output_dir=self.scratch)
        self.assertEqual(results, [])

    def test_keyword_hit(self):
        from agent.index import search_index
        self._seed_aggregator({
            "bv001": {
                "slug": "bv001", "title": "T", "duration_s": 1.0,
                "mode": "concept-explanation", "topics": [],
                "keywords": ["LoRA", "Karpathy"],
                "tldr_oneliner": "", "chapters": [],
            }
        })
        results = search_index("LoRA", output_dir=self.scratch)
        self.assertEqual(len(results), 1)
        self.assertIn("keywords", results[0]["matched_fields"])


class TestListIndex(unittest.TestCase):
    """Phase 12 D-05: list_index filter behavior."""

    def setUp(self):
        self.scratch = (
            Path(__file__).parent / "_tmp_index"
            / f"list_{self._testMethodName}"
        )
        if self.scratch.exists():
            import shutil
            shutil.rmtree(self.scratch)
        self.scratch.mkdir(parents=True)

    def _seed_aggregator(self, entries):
        agg_path = self.scratch / ".index.json"
        agg_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _entry(self, slug, *, mode="replicate-guide", topics=None):
        return {
            "slug": slug, "title": f"T-{slug}", "duration_s": 1.0,
            "mode": mode, "topics": topics or [], "keywords": [],
            "tldr_oneliner": "", "chapters": [],
        }

    def test_no_filter_returns_all(self):
        from agent.index import list_index
        self._seed_aggregator({
            "bv001": self._entry("bv001"),
            "bv002": self._entry("bv002"),
            "bv003": self._entry("bv003"),
        })
        results = list_index(output_dir=self.scratch)
        self.assertEqual([r["slug"] for r in results],
                         ["bv001", "bv002", "bv003"])

    def test_filter_by_topic_membership(self):
        from agent.index import list_index
        self._seed_aggregator({
            "a": self._entry("a", topics=["LLM-Wiki", "RAG"]),
            "b": self._entry("b", topics=["Game-Dev"]),
        })
        results = list_index(topic="LLM-Wiki", output_dir=self.scratch)
        self.assertEqual([r["slug"] for r in results], ["a"])

    def test_filter_by_mode_equality(self):
        from agent.index import list_index
        self._seed_aggregator({
            "a": self._entry("a", mode="replicate-guide"),
            "b": self._entry("b", mode="interview-distillation"),
        })
        results = list_index(mode="replicate-guide", output_dir=self.scratch)
        self.assertEqual([r["slug"] for r in results], ["a"])

    def test_filter_topic_and_mode_is_AND_logic(self):
        from agent.index import list_index
        self._seed_aggregator({
            "a": self._entry("a", topics=["X"], mode="replicate-guide"),
            "b": self._entry("b", topics=["X"], mode="concept-explanation"),
            "c": self._entry("c", topics=["Y"], mode="replicate-guide"),
        })
        results = list_index(topic="X", mode="replicate-guide",
                             output_dir=self.scratch)
        self.assertEqual([r["slug"] for r in results], ["a"])

    def test_empty_aggregator_returns_empty(self):
        from agent.index import list_index
        results = list_index(output_dir=self.scratch)
        self.assertEqual(results, [])


class TestCLIBackfillSearchListEdges(unittest.TestCase):
    """Phase 12 D-01/D-04/D-05: CLI subprocess edge cases for the 3 new
    sub-subcommands (backfill / search / list)."""

    def setUp(self):
        self.scratch = (
            Path(__file__).parent / "_tmp_index"
            / f"cli_{self._testMethodName}"
        )
        if self.scratch.exists():
            import shutil
            shutil.rmtree(self.scratch)
        self.scratch.mkdir(parents=True)

    def _run(self, *args, expect_returncode=0):
        repo_root = Path(__file__).parent.parent
        result = subprocess.run(
            [sys.executable, "-m", "agent.tools", "index", *args],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(repo_root), timeout=30,
        )
        if expect_returncode is not None:
            self.assertEqual(
                result.returncode, expect_returncode,
                msg=f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )
        return result

    def _make_archive(self, slug, *, with_index=False):
        d = self.scratch / slug
        d.mkdir(parents=True, exist_ok=True)
        sm = d / ("summa" "ry.md")
        sm.write_text("# stub\n", encoding="utf-8")
        if with_index:
            (d / "index.json").write_text(
                '{"slug":"' + slug + '"}', encoding="utf-8",
            )

    def _seed_aggregator(self, entries):
        agg_path = self.scratch / ".index.json"
        agg_path.write_text(
            json.dumps(entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def test_backfill_all_json_happy_path(self):
        self._make_archive("bv001")
        self._make_archive("bv002")
        result = self._run(
            "backfill", "--all",
            "--output-dir", str(self.scratch), "--json",
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["action"], "scanned")
        self.assertEqual(data["total_slugs"], 2)
        self.assertEqual(data["to_backfill"], ["bv001", "bv002"])

    def test_backfill_force_overrides_skip_existing(self):
        self._make_archive("bv001", with_index=True)
        # Without force: skipped
        r1 = self._run(
            "backfill", "--all",
            "--output-dir", str(self.scratch), "--json",
        )
        self.assertEqual(json.loads(r1.stdout)["skipped_existing"], ["bv001"])
        # With force: in to_backfill
        r2 = self._run(
            "backfill", "--all", "--force",
            "--output-dir", str(self.scratch), "--json",
        )
        self.assertEqual(json.loads(r2.stdout)["to_backfill"], ["bv001"])

    def test_backfill_failure_returns_nonzero(self):
        self._make_archive("bv001")
        d = self.scratch / "bv002"
        d.mkdir()
        (d / ("summa" "ry.md")).write_bytes(b"\xff\xfe\xfd")
        result = self._run(
            "backfill", "--all",
            "--output-dir", str(self.scratch), "--json",
            expect_returncode=1,
        )
        data = json.loads(result.stdout)
        self.assertTrue(any(f["slug"] == "bv002" for f in data["failed"]))

    def test_backfill_requires_all_flag(self):
        # argparse exits 2 with the missing required arg error
        self._run(
            "backfill",
            "--output-dir", str(self.scratch),
            expect_returncode=2,
        )

    def test_search_json_match(self):
        self._seed_aggregator({
            "douyin_x": {
                "slug": "douyin_x", "title": "Karpathy 又被吹爆",
                "duration_s": 1.0, "mode": "interview-distillation",
                "topics": [], "keywords": [], "tldr_oneliner": "",
                "chapters": [],
            }
        })
        result = self._run(
            "search", "Karpathy",
            "--output-dir", str(self.scratch), "--json",
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["query"], "Karpathy")
        self.assertEqual(len(data["matches"]), 1)
        self.assertEqual(data["matches"][0]["slug"], "douyin_x")

    def test_search_plain_text_format(self):
        self._seed_aggregator({
            "bv001": {
                "slug": "bv001", "title": "ECS demo", "duration_s": 1.0,
                "mode": "concept-explanation", "topics": [],
                "keywords": ["ECS"], "tldr_oneliner": "x", "chapters": [],
            }
        })
        result = self._run(
            "search", "ECS",
            "--output-dir", str(self.scratch),
        )
        self.assertIn("bv001:", result.stdout)
        self.assertIn("[matched:", result.stdout)

    def test_list_topic_filter_json(self):
        self._seed_aggregator({
            "a": {"slug": "a", "title": "A", "duration_s": 1.0,
                  "mode": "replicate-guide", "topics": ["LLM-Wiki"],
                  "keywords": [], "tldr_oneliner": "", "chapters": []},
            "b": {"slug": "b", "title": "B", "duration_s": 1.0,
                  "mode": "replicate-guide", "topics": ["Game-Dev"],
                  "keywords": [], "tldr_oneliner": "", "chapters": []},
        })
        result = self._run(
            "list", "--topic", "LLM-Wiki",
            "--output-dir", str(self.scratch), "--json",
        )
        data = json.loads(result.stdout)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["slug"], "a")

    def test_list_no_filter_plain_text(self):
        self._seed_aggregator({
            "a": {"slug": "a", "title": "A", "duration_s": 1.0,
                  "mode": "replicate-guide", "topics": ["X", "Y"],
                  "keywords": [], "tldr_oneliner": "", "chapters": []},
        })
        result = self._run(
            "list", "--output-dir", str(self.scratch),
        )
        self.assertIn("a: A", result.stdout)
        self.assertIn("(mode=replicate-guide)", result.stdout)
        self.assertIn("topics=X,Y", result.stdout)


if __name__ == "__main__":
    unittest.main()
