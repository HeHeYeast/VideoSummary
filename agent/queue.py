"""Cross-terminal video queue helper (Phase 07 MISC-02).

State file: `~/.videoSummary/queue.json` — JSON {version, items: [...]}
Lock file: `~/.videoSummary/.queue.lock` — FileLock from agent/_lock.py

Per K5 (decision authority): `queue next` does NOT auto-trigger
`/summarize-video`. User manually invokes summarize-video on the slug
returned by `queue next`. Queue is a tracking helper, not a scheduler.

Schema (locked CONTEXT.md specifics):
    {
      "version": 1,
      "items": [
        {
          "slug": "BV1xxx",       # required; unique per queue
          "url": "https://...",   # required
          "added_at": "<ISO>",
          "status": "pending|in_progress|done|skipped",
          "in_progress_pid": null,  # int when in_progress, else null
          "skip_reason": null       # set when status=skipped
        }
      ]
    }

Two-terminal safety: every read-modify-write happens inside
`FileLock(queue_lock_path(), timeout=5.0)`. Stale-PID takeover from
agent/_lock.py applies — Claude Code crash mid-write is recoverable.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from agent._lock import FileLock, LockContended
from agent.io import write_json_atomic, now_iso

log = logging.getLogger(__name__)

QUEUE_DIR_NAME = ".videoSummary"
QUEUE_FILENAME = "queue.json"
LOCK_FILENAME = ".queue.lock"
LOCK_TIMEOUT_S = 5.0  # tolerable wait for cross-terminal serialization
ALLOWED_STATUSES = ("pending", "in_progress", "done", "skipped")


def queue_dir() -> Path:
    """`~/.videoSummary/` — created on first use."""
    return Path.home() / QUEUE_DIR_NAME


def queue_path() -> Path:
    return queue_dir() / QUEUE_FILENAME


def queue_lock_path() -> Path:
    return queue_dir() / LOCK_FILENAME


def _ensure_dir() -> None:
    queue_dir().mkdir(parents=True, exist_ok=True)


def _load_or_init() -> dict:
    """Read queue.json or return a fresh empty queue. Tolerant of corrupt files."""
    p = queue_path()
    if not p.exists():
        return {"version": 1, "items": []}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, dict) or "items" not in obj:
            raise ValueError(f"queue.json is not a v1 dict: {type(obj).__name__}")
        return obj
    except (json.JSONDecodeError, ValueError, OSError) as e:
        log.warning(
            "queue.json at %s unreadable (%s); treating as empty (will overwrite on next write)",
            p, e,
        )
        return {"version": 1, "items": []}


def _save(state: dict) -> None:
    write_json_atomic(queue_path(), state)


def queue_list() -> list[dict]:
    """Return items as list of dicts. Empty when queue file missing/corrupt."""
    _ensure_dir()
    return list(_load_or_init()["items"])


def queue_add(url: str, slug: str) -> bool:
    """Append a new entry. Returns True if added, False if already in queue
    (same slug + same url). Raises ValueError on slug collision with different URL.
    """
    _ensure_dir()
    with FileLock(queue_lock_path(), timeout=LOCK_TIMEOUT_S):
        state = _load_or_init()
        for item in state["items"]:
            if item["slug"] == slug:
                if item["url"] == url:
                    return False  # idempotent no-op
                raise ValueError(
                    f"slug collision: {slug!r} already queued with different URL "
                    f"({item['url']!r}); pick a unique slug"
                )
        state["items"].append({
            "slug": slug,
            "url": url,
            "added_at": now_iso(),
            "status": "pending",
            "in_progress_pid": None,
            "skip_reason": None,
        })
        _save(state)
    return True


def queue_next() -> dict | None:
    """Find first pending item, mark it in_progress with current PID, persist,
    return it. Returns None when no pending items.
    """
    _ensure_dir()
    with FileLock(queue_lock_path(), timeout=LOCK_TIMEOUT_S):
        state = _load_or_init()
        for item in state["items"]:
            if item["status"] == "pending":
                item["status"] = "in_progress"
                item["in_progress_pid"] = os.getpid()
                _save(state)
                return dict(item)  # caller gets a copy
        return None


def queue_done(slug: str) -> None:
    """Flip a slug's status to done; clear in_progress_pid. KeyError if not found."""
    _ensure_dir()
    with FileLock(queue_lock_path(), timeout=LOCK_TIMEOUT_S):
        state = _load_or_init()
        for item in state["items"]:
            if item["slug"] == slug:
                item["status"] = "done"
                item["in_progress_pid"] = None
                _save(state)
                return
        raise KeyError(f"slug not in queue: {slug!r}")


def queue_skip(slug: str, *, reason: str = "") -> None:
    """Flip a slug's status to skipped with reason. KeyError if not found."""
    _ensure_dir()
    with FileLock(queue_lock_path(), timeout=LOCK_TIMEOUT_S):
        state = _load_or_init()
        for item in state["items"]:
            if item["slug"] == slug:
                item["status"] = "skipped"
                item["in_progress_pid"] = None
                item["skip_reason"] = reason or None
                _save(state)
                return
        raise KeyError(f"slug not in queue: {slug!r}")


# Optional convenience for stats display in `queue list` output formatter
class QueueState:
    """Snapshot of queue state for stats display. Read-only convenience wrapper."""

    def __init__(self, items: list[dict]):
        self.items = items

    @classmethod
    def load(cls) -> "QueueState":
        return cls(queue_list())

    def count_by_status(self) -> dict[str, int]:
        return {s: sum(1 for i in self.items if i["status"] == s) for s in ALLOWED_STATUSES}
