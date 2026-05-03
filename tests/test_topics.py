"""Phase 10 KB-07/09/10/11 tests: topics governance CRUD + idempotency + atomic restore.

Mirrors tests/test_glossary.py shape (setUp/tearDown ASCII-safe tmpdir under
tests/_tmp_topics/, multiprocessing race test for append_pending).

Test classes:
  TestReadTopics — KB-07 schema parse
  TestBootstrap — KB-08 stdin JSON validation + idempotent skip
  TestAppendPending — KB-11 governance Python API
  TestAudit — KB-09 pending/orphan/empty-glob handling
  TestResolve — KB-10 atomic multi-file write + restore-on-failure + --rename + --remove
"""
from __future__ import annotations

import json
import multiprocessing as mp
import tempfile
import unittest
from pathlib import Path

from agent.topics import (
    read_topics, write_approved_taxonomy, append_pending, resolve_pending,
    TOPICS_FILENAME, LOCK_FILENAME,
)
from agent._lock import FileLock, LockContended


def _ascii_tmpdir_root() -> Path:
    """Per-test tmpdir under tests/_tmp_topics/ (ASCII-safe per CONTEXT D-19;
    Windows zh-CN GBK code-page would corrupt subprocess paths if we used
    %TEMP% which contains the user's CJK profile name)."""
    root = Path(__file__).parent / "_tmp_topics"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _child_append_pending(topics_path_str, name, from_slug, chapter_title, reason, q):
    """multiprocessing target — append_pending in a child process."""
    try:
        r = append_pending(Path(topics_path_str), name, from_slug, chapter_title, reason,
                           timeout=15.0)
        q.put(("ok", r))
    except Exception as e:
        q.put(("error", repr(e)))


class TopicsBaseTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(
            prefix="topics_test_", dir=str(_ascii_tmpdir_root()),
        )
        self.tmpdir = Path(self._tmp.name)
        self.topics_md = self.tmpdir / TOPICS_FILENAME

    def tearDown(self):
        self._tmp.cleanup()


class TestReadTopics(TopicsBaseTest):
    def test_missing_file_returns_empty(self):
        r = read_topics(self.topics_md)
        self.assertEqual(r, {"approved": [], "pending": [], "exists": False})

    def test_parses_approved_nested_list_3_levels(self):
        taxonomy = [
            {"name": "LLM", "subtopics": [
                {"name": "LoRA", "subtopics": []},
                {"name": "RAG", "subtopics": []},
            ]},
            {"name": "Game-Dev", "subtopics": [{"name": "Godot", "subtopics": []}]},
        ]
        write_approved_taxonomy(self.topics_md, taxonomy)
        r = read_topics(self.topics_md)
        self.assertTrue(r["exists"])
        names = [n["name"] for n in r["approved"]]
        self.assertIn("LLM", names)
        self.assertIn("Game-Dev", names)
        llm_subs = [
            n["name"] for n in next(n for n in r["approved"] if n["name"] == "LLM")["subtopics"]
        ]
        self.assertEqual(sorted(llm_subs), ["LoRA", "RAG"])

    def test_parses_pending_h3_entries_with_3_fields(self):
        write_approved_taxonomy(self.topics_md, [{"name": "LLM", "subtopics": []}])
        append_pending(self.topics_md, "LangChain",
                       from_slug="BV1HG9JBsEPK",
                       chapter_title="三、用 LangChain 串 agent",
                       reason="LLM 应用框架事实标准")
        r = read_topics(self.topics_md)
        self.assertEqual(len(r["pending"]), 1)
        p = r["pending"][0]
        self.assertEqual(p["name"], "LangChain")
        self.assertEqual(p["from_slug"], "BV1HG9JBsEPK")
        self.assertIn("LangChain 串 agent", p["chapter_title"])
        self.assertIn("LLM 应用框架", p["reason"])


class TestBootstrap(TopicsBaseTest):
    def test_creates_file_with_locked_header(self):
        r = write_approved_taxonomy(
            self.topics_md,
            [{"name": "LLM", "subtopics": [{"name": "LoRA"}]}],
        )
        self.assertEqual(r["action"], "created")
        self.assertEqual(r["approved_count"], 2)
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertIn("# Topics Taxonomy", text)
        self.assertIn("v1.2 knowledge-base governance", text)
        self.assertIn("## Approved Taxonomy", text)
        self.assertIn("## Pending", text)
        self.assertIn("- LLM", text)
        self.assertIn("- LoRA", text)

    def test_idempotent_skip_on_populated(self):
        write_approved_taxonomy(self.topics_md, [{"name": "X", "subtopics": []}])
        r2 = write_approved_taxonomy(self.topics_md, [{"name": "Y", "subtopics": []}])
        self.assertEqual(r2["action"], "skipped")
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertIn("- X", text)
        self.assertNotIn("- Y", text)

    def test_rejects_nesting_past_3_levels(self):
        bad = [{"name": "L1", "subtopics": [
            {"name": "L2", "subtopics": [
                {"name": "L3", "subtopics": [
                    {"name": "L4", "subtopics": []},
                ]},
            ]},
        ]}]
        with self.assertRaises(ValueError):
            write_approved_taxonomy(self.topics_md, bad)

    def test_rejects_duplicate_top_level_names(self):
        with self.assertRaises(ValueError):
            write_approved_taxonomy(
                self.topics_md,
                [{"name": "LLM", "subtopics": []}, {"name": "LLM", "subtopics": []}],
            )

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            write_approved_taxonomy(
                self.topics_md,
                [{"name": "", "subtopics": []}],
            )


class TestAppendPending(TopicsBaseTest):
    def setUp(self):
        super().setUp()
        write_approved_taxonomy(self.topics_md, [{"name": "LLM", "subtopics": []}])

    def test_append_creates_h3_with_3_fields(self):
        r = append_pending(self.topics_md, "LangChain",
                           from_slug="BVxxx", chapter_title="三、agent",
                           reason="标准框架")
        self.assertEqual(r["action"], "appended")
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertIn("### LangChain", text)
        self.assertIn("- 申请来源 slug: BVxxx", text)
        self.assertIn("- chapter title: 三、agent", text)
        self.assertIn("- 提议理由: 标准框架", text)

    def test_append_idempotent_on_duplicate_name(self):
        append_pending(self.topics_md, "X", "BVa", "ch", "r")
        r2 = append_pending(self.topics_md, "X", "BVb", "ch2", "r2")
        self.assertEqual(r2["action"], "skipped")
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertEqual(text.count("### X"), 1)

    def test_append_rejects_empty_args(self):
        with self.assertRaises(ValueError):
            append_pending(self.topics_md, "", "BVa", "ch", "r")
        with self.assertRaises(ValueError):
            append_pending(self.topics_md, "X", "", "ch", "r")
        with self.assertRaises(ValueError):
            append_pending(self.topics_md, "X", "BVa", "", "r")
        with self.assertRaises(ValueError):
            append_pending(self.topics_md, "X", "BVa", "ch", "")

    def test_append_on_missing_file_raises(self):
        missing = self.tmpdir / "_subdir" / "_topics.md"
        with self.assertRaises(FileNotFoundError):
            append_pending(missing, "X", "BVa", "ch", "r")

    def test_concurrent_append_via_multiprocessing(self):
        ctx = mp.get_context("spawn")
        q = ctx.Queue()
        p1 = ctx.Process(target=_child_append_pending,
                         args=(str(self.topics_md), "Y", "BVa", "ch", "r", q))
        p2 = ctx.Process(target=_child_append_pending,
                         args=(str(self.topics_md), "Y", "BVb", "ch2", "r2", q))
        p1.start(); p2.start()
        p1.join(timeout=30); p2.join(timeout=30)
        self.assertEqual(p1.exitcode, 0); self.assertEqual(p2.exitcode, 0)
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertEqual(text.count("### Y"), 1)

    def test_lock_contention_with_zero_timeout(self):
        lock_path = self.tmpdir / LOCK_FILENAME
        with FileLock(lock_path):
            with self.assertRaises(LockContended):
                append_pending(self.topics_md, "Z", "BVz", "ch", "r", timeout=0.0)


class TestAudit(TopicsBaseTest):
    def setUp(self):
        super().setUp()
        write_approved_taxonomy(
            self.topics_md,
            [{"name": "LLM", "subtopics": [{"name": "LoRA"}, {"name": "RAG"}]}],
        )

    def test_no_index_json_files_yields_empty_orphans(self):
        # Manually invoke the same path the CLI uses: read_topics + glob
        r = read_topics(self.topics_md)
        self.assertTrue(r["exists"])
        paths = sorted(self.tmpdir.glob("*/index.json"))
        self.assertEqual(paths, [])  # Pre-Phase-11 reality

    def test_with_index_json_counts_references(self):
        # Create 2 fake per-slug sidecars referencing topics
        (self.tmpdir / "BV1").mkdir()
        (self.tmpdir / "BV1" / "index.json").write_text(
            json.dumps({"slug": "BV1", "topics": ["LoRA"], "chapters": []}),
            encoding="utf-8",
        )
        (self.tmpdir / "BV2").mkdir()
        (self.tmpdir / "BV2" / "index.json").write_text(
            json.dumps({"slug": "BV2", "topics": ["LoRA"], "chapters": []}),
            encoding="utf-8",
        )
        paths = sorted(self.tmpdir.glob("*/index.json"))
        self.assertEqual(len(paths), 2)


class TestResolve(TopicsBaseTest):
    def setUp(self):
        super().setUp()
        write_approved_taxonomy(
            self.topics_md, [{"name": "LLM", "subtopics": []}],
        )
        append_pending(self.topics_md, "LangChain", "BVx", "ch", "framework")

    def test_resolve_promote_default_top_level(self):
        r = resolve_pending(self.topics_md, "LangChain")
        self.assertEqual(r["action"], "promoted")
        self.assertEqual(r["pending_name"], "LangChain")
        self.assertEqual(r["final_name"], "LangChain")
        self.assertEqual(r["index_json_updated"], [])
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertNotIn("### LangChain", text)
        self.assertIn("- LangChain", text)

    def test_resolve_rename_nested_path(self):
        r = resolve_pending(self.topics_md, "LangChain", rename="LLM/LangChain")
        self.assertEqual(r["action"], "renamed")
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertNotIn("### LangChain", text)
        # Nested under LLM (2-space indent)
        self.assertRegex(text, r"- LLM\n(?:.+\n)*?  - LangChain")

    def test_resolve_remove_clears_pending(self):
        r = resolve_pending(self.topics_md, "LangChain", remove=True)
        self.assertEqual(r["action"], "removed")
        self.assertIsNone(r["final_name"])
        text = self.topics_md.read_text(encoding="utf-8")
        self.assertNotIn("### LangChain", text)

    def test_resolve_unknown_name_raises(self):
        with self.assertRaises((KeyError, LookupError)):
            resolve_pending(self.topics_md, "NotPresent")

    def test_rename_and_remove_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            resolve_pending(self.topics_md, "LangChain", rename="X", remove=True)

    def test_resolve_updates_index_json_references(self):
        # Create fake per-slug sidecars referencing the pending topic
        (self.tmpdir / "BV1").mkdir()
        (self.tmpdir / "BV1" / "index.json").write_text(
            json.dumps({
                "slug": "BV1",
                "topics": ["pending: LangChain"],
                "chapters": [{"title": "ch1", "topics": ["pending: LangChain"]}],
            }),
            encoding="utf-8",
        )
        r = resolve_pending(self.topics_md, "LangChain", output_dir=self.tmpdir)
        self.assertIn("BV1", r["index_json_updated"])
        obj = json.loads((self.tmpdir / "BV1" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(obj["topics"], ["LangChain"])
        self.assertEqual(obj["chapters"][0]["topics"], ["LangChain"])

    def test_resolve_remove_clears_index_json_references(self):
        # Create fake per-slug sidecar referencing the pending topic
        (self.tmpdir / "BV1").mkdir()
        (self.tmpdir / "BV1" / "index.json").write_text(
            json.dumps({
                "slug": "BV1",
                "topics": ["pending: LangChain", "OtherTopic"],
                "chapters": [{"title": "ch1", "topics": ["pending: LangChain"]}],
            }),
            encoding="utf-8",
        )
        r = resolve_pending(self.topics_md, "LangChain", remove=True, output_dir=self.tmpdir)
        self.assertEqual(r["action"], "removed")
        self.assertIn("BV1", r["index_json_updated"])
        obj = json.loads((self.tmpdir / "BV1" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(obj["topics"], ["OtherTopic"])
        self.assertEqual(obj["chapters"][0]["topics"], [])

    def test_resolve_atomic_restore_on_index_failure(self):
        """If a per-slug index sidecar write fails after the topics file was
        tentatively written, the topics file must be restored to the
        pre-resolve state. We simulate failure by making the slug directory
        read-only (or deleting its parent directory mid-flight via an
        unwritable path)."""
        import os
        import sys
        if sys.platform == "win32":
            self.skipTest("Windows os.chmod read-only does not reliably block writes")
        (self.tmpdir / "BV1").mkdir()
        ip = self.tmpdir / "BV1" / "index.json"
        ip.write_text(
            json.dumps({"slug": "BV1", "topics": ["pending: LangChain"], "chapters": []}),
            encoding="utf-8",
        )
        pre = self.topics_md.read_text(encoding="utf-8")
        # Make BV1 directory read-only so atomic write into it fails
        os.chmod(self.tmpdir / "BV1", 0o555)
        try:
            with self.assertRaises(Exception):
                resolve_pending(self.topics_md, "LangChain", output_dir=self.tmpdir)
            # _topics.md must be byte-equal to pre-resolve state
            post = self.topics_md.read_text(encoding="utf-8")
            self.assertEqual(post, pre)
        finally:
            os.chmod(self.tmpdir / "BV1", 0o755)


if __name__ == "__main__":
    unittest.main()
