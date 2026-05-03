"""Tests for agent/queue.py — Phase 07 MISC-02.

Coverage:
  TestQueuePrimitives (T1..T11 + T14): single-process CRUD primitives
  TestQueueRace (T12, T13): subprocess-based 2-terminal race tests
    T12: 5 concurrent queue_add → 5 distinct items (FileLock serialization)
    T13: 5 concurrent queue_next → 5 distinct slugs (in_progress: <pid>
         marker prevents double-pickup) — K-feature MISC-02 per PITFALLS P-10
"""
from __future__ import annotations
import json
import multiprocessing as mp
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add repo root for imports
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from agent import queue as q
from agent._lock import FileLock


def _ascii_tmpdir_root() -> str:
    """Mirror tests/test_lock.py: zh-CN Windows %TEMP% has CJK in username,
    which can clutter file paths. Pick an ASCII-safe location under tests/."""
    here = Path(__file__).parent.resolve()
    safe = here / "_tmp_queue"
    safe.mkdir(parents=True, exist_ok=True)
    return str(safe)


class TestQueuePrimitives(unittest.TestCase):
    """T1..T11 + T14 — single-process primitives."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.fake_home = Path(self._td.name)
        # Patch Path.home() so queue_dir() resolves under our tmpdir
        self._patcher = patch("agent.queue.Path.home", return_value=self.fake_home)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self._td.cleanup()

    # ── T1: queue_path() returns ~/.videoSummary/queue.json ────────────────
    def test_T1_queue_path_resolves_under_home(self):
        self.assertEqual(q.queue_path(), self.fake_home / ".videoSummary" / "queue.json")

    # ── T2: queue_lock_path() returns ~/.videoSummary/.queue.lock ──────────
    def test_T2_queue_lock_path_resolves_under_home(self):
        self.assertEqual(q.queue_lock_path(), self.fake_home / ".videoSummary" / ".queue.lock")

    # ── T3: First queue_add creates the file with correct schema ───────────
    def test_T3_first_add_creates_file_with_schema(self):
        added = q.queue_add(url="http://test/1", slug="slug1")
        self.assertTrue(added)
        self.assertTrue(q.queue_path().exists())
        state = json.loads(q.queue_path().read_text(encoding="utf-8"))
        self.assertEqual(state["version"], 1)
        self.assertEqual(len(state["items"]), 1)
        item = state["items"][0]
        self.assertEqual(item["slug"], "slug1")
        self.assertEqual(item["url"], "http://test/1")
        self.assertEqual(item["status"], "pending")
        self.assertIsNone(item["in_progress_pid"])
        self.assertIn("added_at", item)

    # ── T4: queue_add idempotent on (slug, url) — returns False on dup ─────
    def test_T4_add_idempotent_on_same_slug_url(self):
        first = q.queue_add(url="http://test/1", slug="slug1")
        second = q.queue_add(url="http://test/1", slug="slug1")
        self.assertTrue(first)
        self.assertFalse(second, "second add of identical (slug,url) should return False")
        items = q.queue_list()
        self.assertEqual(len(items), 1, f"duplicate entry created: {items}")

    # ── T5: slug collision with different URL → ValueError ────────────────
    def test_T5_slug_collision_different_url_raises(self):
        q.queue_add(url="http://test/1", slug="slug1")
        with self.assertRaises(ValueError) as ctx:
            q.queue_add(url="http://test/2", slug="slug1")
        self.assertIn("slug collision", str(ctx.exception))

    # ── T6: queue_list returns list of dicts (empty when no file) ──────────
    def test_T6_list_returns_list_of_dicts(self):
        # Empty case: queue file does not exist
        self.assertEqual(q.queue_list(), [])
        # After 2 adds:
        q.queue_add(url="http://test/1", slug="slug1")
        q.queue_add(url="http://test/2", slug="slug2")
        items = q.queue_list()
        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 2)
        self.assertIsInstance(items[0], dict)
        self.assertEqual({i["slug"] for i in items}, {"slug1", "slug2"})

    # ── T7: queue_next pops first pending, marks in_progress with PID ──────
    def test_T7_next_marks_in_progress_with_pid(self):
        q.queue_add(url="http://test/1", slug="slug1")
        item = q.queue_next()
        self.assertIsNotNone(item)
        self.assertEqual(item["slug"], "slug1")
        self.assertEqual(item["status"], "in_progress")
        self.assertEqual(item["in_progress_pid"], os.getpid())
        # And persisted to disk
        state = json.loads(q.queue_path().read_text(encoding="utf-8"))
        self.assertEqual(state["items"][0]["status"], "in_progress")
        self.assertEqual(state["items"][0]["in_progress_pid"], os.getpid())
        # No more pending → next returns None
        self.assertIsNone(q.queue_next())

    # ── T8: queue_next called twice in same process → 2 different items ────
    def test_T8_next_called_twice_returns_different_items(self):
        q.queue_add(url="http://test/1", slug="slug1")
        q.queue_add(url="http://test/2", slug="slug2")
        a = q.queue_next()
        b = q.queue_next()
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)
        self.assertNotEqual(a["slug"], b["slug"])
        self.assertEqual({a["slug"], b["slug"]}, {"slug1", "slug2"})
        # Both marked in_progress with same pid (same process — allowed by spec)
        self.assertEqual(a["in_progress_pid"], os.getpid())
        self.assertEqual(b["in_progress_pid"], os.getpid())

    # ── T9: queue_done flips status; KeyError on unknown slug ──────────────
    def test_T9_done_flips_status_clears_pid(self):
        q.queue_add(url="http://test/1", slug="slug1")
        q.queue_next()  # mark in_progress
        q.queue_done("slug1")
        items = q.queue_list()
        self.assertEqual(items[0]["status"], "done")
        self.assertIsNone(items[0]["in_progress_pid"])
        # Unknown slug raises KeyError
        with self.assertRaises(KeyError):
            q.queue_done("nonexistent")

    # ── T10: queue_skip flips status, stores reason; KeyError on unknown ──
    def test_T10_skip_flips_status_with_reason(self):
        q.queue_add(url="http://test/1", slug="slug1")
        q.queue_skip("slug1", reason="too long")
        items = q.queue_list()
        self.assertEqual(items[0]["status"], "skipped")
        self.assertEqual(items[0]["skip_reason"], "too long")
        self.assertIsNone(items[0]["in_progress_pid"])
        # Unknown slug raises KeyError
        with self.assertRaises(KeyError):
            q.queue_skip("nonexistent", reason="x")

    # ── T11: write ops acquire FileLock(queue_lock_path(), timeout=5.0) ────
    def test_T11_writes_acquire_filelock_with_correct_path(self):
        seen_calls: list = []
        real_FileLock = q.FileLock

        class CapturingLock:
            def __init__(self, path, *, timeout=0.0):
                seen_calls.append((Path(path), timeout))
                self._inner = real_FileLock(path, timeout=timeout)

            def __enter__(self):
                return self._inner.__enter__()

            def __exit__(self, *a):
                return self._inner.__exit__(*a)

        with patch("agent.queue.FileLock", CapturingLock):
            q.queue_add(url="http://test/1", slug="slug1")
            q.queue_next()
            q.queue_done("slug1")

        self.assertGreaterEqual(len(seen_calls), 3,
                                f"expected ≥3 FileLock acquires, got {seen_calls}")
        for path, timeout in seen_calls:
            self.assertEqual(path, q.queue_lock_path(),
                             f"FileLock acquired wrong path: {path}")
            self.assertEqual(timeout, q.LOCK_TIMEOUT_S,
                             f"FileLock acquired wrong timeout: {timeout}")

    # ── T14: corrupt queue.json → list returns empty + warn; add rebuilds ─
    def test_T14_corrupt_file_recovers_silently(self):
        # Write garbage to queue.json
        q.queue_path().parent.mkdir(parents=True, exist_ok=True)
        q.queue_path().write_text('"not json{', encoding="utf-8")
        # queue_list should NOT raise — returns empty list
        self.assertEqual(q.queue_list(), [])
        # queue_add after corruption rebuilds the file
        added = q.queue_add(url="http://test/1", slug="slug1")
        self.assertTrue(added)
        items = q.queue_list()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["slug"], "slug1")


# === Module-level subprocess workers (must be top-level for spawn pickling on Windows) ===

def _race_add_worker(home_str: str, idx: int) -> bool:
    """Subprocess entry: spawn-safe (must be top-level for pickling on Windows).

    Re-imports agent.queue inside the child process and monkeypatches Path.home
    via env var so queue_dir() resolves under the test's fake home.
    """
    os.environ["_QUEUE_TEST_HOME"] = home_str
    # In the child, monkeypatch Path.home before any queue operation
    import agent.queue as q
    q.Path.home = lambda: Path(os.environ["_QUEUE_TEST_HOME"])
    try:
        q.queue_add(url=f"http://test/{idx}", slug=f"slug{idx}")
        return True
    except Exception:
        return False


def _race_next_worker(home_str: str) -> str:
    """Subprocess entry: call queue_next() once and return the slug (or 'NONE').

    Re-imports the queue module fresh in the child; monkeypatches Path.home via
    env var. Returns the slug returned by queue_next, or the literal string
    'NONE' if no pending items remain (so the parent can detect underflow).
    """
    os.environ["_QUEUE_TEST_HOME"] = home_str
    import agent.queue as q
    q.Path.home = lambda: Path(os.environ["_QUEUE_TEST_HOME"])
    item = q.queue_next()
    return item["slug"] if item else "NONE"


class TestQueueRace(unittest.TestCase):
    """T12, T13 — 2-terminal race tests via multiprocessing.

    These tests verify the MISC-02 K-feature per PITFALLS P-10:
      T12: concurrent `queue add` -> no JSON corruption (FileLock serializes writes)
      T13: concurrent `queue next` -> no double-pickup (in_progress: <pid> marker
           written inside FileLock prevents two terminals claiming same item)
    """

    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
        self.fake_home = Path(self._td.name)
        # WR-05: capture original Path.home BEFORE any worker / parent mutation
        # so tearDown can restore it. Without this, pollution leaks into other
        # test modules loaded later in `python -m unittest discover` runs.
        self._orig_home = q.Path.home

    def tearDown(self):
        # WR-05: restore Path.home BEFORE cleaning the temp dir so subsequent
        # tests that call Path.home() don't get the lambda pointing to a
        # deleted tmpdir. Also pop the env var (IN-04) for symmetry.
        q.Path.home = self._orig_home
        os.environ.pop("_QUEUE_TEST_HOME", None)
        self._td.cleanup()

    def test_T12_concurrent_add_no_corruption(self):
        # spawn 5 subprocesses, each adds 1 distinct slug
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=5) as pool:
            results = pool.starmap(
                _race_add_worker,
                [(str(self.fake_home), i) for i in range(5)],
            )
        self.assertTrue(all(results), f"some workers failed: {results}")
        # Read final queue state in the parent process
        os.environ["_QUEUE_TEST_HOME"] = str(self.fake_home)
        q.Path.home = lambda: Path(os.environ["_QUEUE_TEST_HOME"])
        items = q.queue_list()
        self.assertEqual(
            len(items), 5,
            f"expected 5 items after 5 concurrent adds, got {len(items)}: {items}",
        )
        slugs = {i["slug"] for i in items}
        self.assertEqual(slugs, {f"slug{i}" for i in range(5)})

    def test_T13_concurrent_next_no_double_pickup(self):
        """K-feature MISC-02: 5 concurrent `queue next` -> 5 distinct slugs.

        Per PITFALLS P-10: the `in_progress: <pid>` write happens inside the
        FileLock-protected critical section; two terminals running `queue next`
        simultaneously must NOT both pick up the same pending item.
        """
        # Step 1: pre-populate queue with 5 pending items in the parent
        os.environ["_QUEUE_TEST_HOME"] = str(self.fake_home)
        q.Path.home = lambda: Path(os.environ["_QUEUE_TEST_HOME"])
        for i in range(5):
            q.queue_add(url=f"http://test/{i}", slug=f"slug{i}")

        # Sanity check: queue has 5 pending entries before race
        pre_state = q.queue_list()
        self.assertEqual(len(pre_state), 5)
        self.assertTrue(all(it["status"] == "pending" for it in pre_state))

        # Step 2: spawn 5 subprocesses, each calls queue_next() exactly once
        ctx = mp.get_context("spawn")
        with ctx.Pool(processes=5) as pool:
            results = pool.starmap(
                _race_next_worker,
                [(str(self.fake_home),)] * 5,
            )

        # Step 3: assert no double-pickup -> all 5 returned slugs are distinct
        # (excluding any "NONE" sentinel which would indicate queue underflow)
        non_none = [s for s in results if s != "NONE"]
        self.assertEqual(
            len(non_none), 5,
            f"expected 5 successful queue_next() returns, got {results}",
        )
        distinct_slugs = set(non_none)
        self.assertEqual(
            len(distinct_slugs), 5,
            f"DOUBLE-PICKUP DETECTED: 5 workers but only {len(distinct_slugs)} "
            f"distinct slugs returned: {results}. The in_progress: <pid> marker "
            f"inside FileLock failed to prevent same-item claim by two terminals.",
        )
        self.assertEqual(
            distinct_slugs, {f"slug{i}" for i in range(5)},
            "returned slugs do not match the 5 we enqueued",
        )

        # Step 4: assert final on-disk state shows all 5 marked in_progress
        # (proves the in_progress marker was persisted, not just returned)
        # Re-load via fresh disk read in the parent
        queue_file = self.fake_home / q.QUEUE_DIR_NAME / q.QUEUE_FILENAME
        final_state = json.loads(queue_file.read_text(encoding="utf-8"))
        in_progress_count = sum(
            1 for item in final_state["items"] if item["status"] == "in_progress"
        )
        self.assertEqual(
            in_progress_count, 5,
            f"expected 5 items in_progress after race, found {in_progress_count}: "
            f"{final_state['items']}",
        )
        # Each in_progress item should have a non-null in_progress_pid
        for item in final_state["items"]:
            self.assertEqual(item["status"], "in_progress")
            self.assertIsNotNone(
                item["in_progress_pid"],
                f"in_progress item {item['slug']} has null pid -- contract violation",
            )
            self.assertIsInstance(item["in_progress_pid"], int)


if __name__ == "__main__":
    unittest.main()
