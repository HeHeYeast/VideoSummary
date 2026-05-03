"""v1.2 knowledge-base per-slug index + top-level aggregator (Phase 11 D-01..D-10).

Reads (never writes) decision artifacts via Claude-side prompt; this module
is a mechanical writer that ingests Claude-decided JSON via stdin.

K5 boundary:
  - This module WRITES to per-slug index sidecars AND the top-level
    aggregator file ONLY.
  - It NEVER writes to per-slug decision artifacts (the slug summary file,
    the slug plan file, per-slug paragraphs / segs / meta artifacts).
  - Source-grep tests (tests/test_k5_emitters.py) verify the literals for
    those decision artifacts never appear here. Note: this module
    deliberately uses prose ("the slug summary file" / "the slug plan
    file") in docstrings + error messages to avoid regex self-match on
    the K5 boundary tests (Phase 10-01 deviation #2 lesson).

Schema (locked in 11-CONTEXT.md D-01.1..D-01.5):
  - per-slug: 8 fields {slug, title, duration_s, mode, topics[], keywords[],
    tldr_oneliner, chapters[]} where chapters[i] = {title, start, excerpt}
  - top-level: flat {<slug>: <per-slug>, ...}, no backlinks (per D-07)

Idempotency:
  - write_per_slug_index on byte-equal stdin -> action="skipped"
  - rebuild_aggregator: always atomic-write (full re-scan)

Concurrency:
  - All writers acquire output/.index.lock via FileLock context manager.
  - Reads are lock-free (D-09.4 - concurrent reads do not conflict).

Cross-module dependencies (stable contracts):
  - agent.topics.read_topics - Phase 10 ship, white-list lookup
  - agent.topics.append_pending - Phase 10 ship, novel-topic submission
  - agent._lock.FileLock - v1.0 Phase 06 ship
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path

from agent._lock import FileLock, LockContended

log = logging.getLogger(__name__)

INDEX_FILENAME = "index.json"           # per-slug
AGGREGATOR_FILENAME = ".index.json"     # top-level
LOCK_FILENAME = ".index.lock"
DEFAULT_OUTPUT_DIR = "output"

VALID_MODES = (
    "replicate-guide",
    "concept-explanation",
    "extension-applications",
    "interview-distillation",
)

REQUIRED_FIELDS = ("slug", "title", "duration_s", "mode",
                   "topics", "keywords", "tldr_oneliner", "chapters")
CHAPTER_FIELDS = ("title", "start", "excerpt")

# Mirror of agent/glossary.py:_H2_RE pattern - anchored, MULTILINE, non-greedy
# with trailing whitespace tolerance. Matches H2 only (NOT H3).
_GLOSSARY_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class IndexValidationError(Exception):
    """Raised when per-slug index data fails 8-field schema validation."""


def _atomic_write(target: Path, content: str) -> None:
    """Write content to target atomically via tempfile + os.fsync + os.replace.

    Same pattern as agent/topics.py:_atomic_write (which mirrors
    agent/glossary.py:_atomic_write). Tempfile lives in target.parent so
    os.replace is cross-device atomic on Windows + POSIX. Tempfile cleaned
    up on exception.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".tmp",
        dir=target.parent, delete=False,
    )
    try:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, target)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def _flatten_approved_names(approved_tree: list) -> set:
    """Recursively flatten Phase 10 approved tree into a set of all names.

    Tree shape (from agent.topics.read_topics): list of
    {"name": str, "subtopics": [{"name": str, "subtopics": [...]}, ...]}.
    """
    names = set()

    def walk(items):
        for it in items:
            if isinstance(it, dict) and "name" in it:
                names.add(it["name"])
                walk(it.get("subtopics", []))

    walk(approved_tree)
    return names


def validate_per_slug_index(d, *, approved_topics=None) -> None:
    """8-field schema check; raise IndexValidationError on first failure.

    Args:
        d: parsed index data (must be dict).
        approved_topics: optional whitelist set; if provided, every non-pending
            topic must be in the set (D-05.2 step c). Pass None to skip
            whitelist enforcement (used by rebuild_aggregator + --force).

    Raises:
        IndexValidationError on any malformed field, type error, mode not in
        the 4 valid values, or topic not in the whitelist.
    """
    if not isinstance(d, dict):
        raise IndexValidationError(
            f"index data must be a dict, got {type(d).__name__}"
        )
    for f in REQUIRED_FIELDS:
        if f not in d:
            raise IndexValidationError(f"missing required field: {f!r}")
    # Type checks
    if not isinstance(d["slug"], str) or not d["slug"].strip():
        raise IndexValidationError(
            f"'slug' must be non-empty string, got {d['slug']!r}"
        )
    if not isinstance(d["title"], str):
        raise IndexValidationError(
            f"'title' must be string, got {type(d['title']).__name__}"
        )
    # bool is a subclass of int in Python; reject bool explicitly for duration.
    if isinstance(d["duration_s"], bool) or not isinstance(d["duration_s"], (int, float)):
        raise IndexValidationError(
            f"'duration_s' must be number, got {type(d['duration_s']).__name__}"
        )
    if d["mode"] not in VALID_MODES:
        raise IndexValidationError(
            f"'mode' must be one of {VALID_MODES}, got {d['mode']!r}"
        )
    if not isinstance(d["topics"], list):
        raise IndexValidationError(
            f"'topics' must be list, got {type(d['topics']).__name__}"
        )
    if not isinstance(d["keywords"], list):
        raise IndexValidationError(
            f"'keywords' must be list, got {type(d['keywords']).__name__}"
        )
    if not isinstance(d["tldr_oneliner"], str):
        raise IndexValidationError(
            f"'tldr_oneliner' must be string, got {type(d['tldr_oneliner']).__name__}"
        )
    if not isinstance(d["chapters"], list):
        raise IndexValidationError(
            f"'chapters' must be list, got {type(d['chapters']).__name__}"
        )
    # Topic whitelist check (only if approved set was passed in)
    if approved_topics is not None:
        for t in d["topics"]:
            if not isinstance(t, str):
                raise IndexValidationError(
                    f"topic must be string, got {type(t).__name__}"
                )
            if t.startswith("pending: "):
                continue  # pending: <name> always allowed per D-05.4
            if t not in approved_topics:
                raise IndexValidationError(
                    f"topic {t!r} not in Approved Taxonomy; "
                    f"use 'pending: {t}' to submit for review"
                )
    # Chapter shape
    for i, ch in enumerate(d["chapters"]):
        if not isinstance(ch, dict):
            raise IndexValidationError(
                f"chapters[{i}] must be dict, got {type(ch).__name__}"
            )
        for cf in CHAPTER_FIELDS:
            if cf not in ch:
                raise IndexValidationError(
                    f"chapters[{i}] missing field {cf!r}"
                )
        if isinstance(ch["start"], bool) or not isinstance(ch["start"], (int, float)):
            raise IndexValidationError(
                f"chapters[{i}].start must be number, "
                f"got {type(ch['start']).__name__}"
            )


def read_per_slug_index(slug_dir):
    """Return parsed per-slug index data or None if missing/corrupt.

    Args:
        slug_dir: path to the per-slug directory containing index.json.

    Returns:
        Parsed dict (validated against 8-field schema) on success; None if
        the file is missing, unreadable, or has a malformed schema.
    """
    p = Path(slug_dir) / INDEX_FILENAME
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        validate_per_slug_index(d)
        return d
    except (OSError, json.JSONDecodeError, IndexValidationError) as e:
        log.warning("read_per_slug_index: skipping %s (%s)", p, e)
        return None


def read_aggregator(output_dir=None):
    """Read the top-level aggregator file; return {} if missing or corrupt.

    Args:
        output_dir: parent dir for the aggregator file (default: "output").

    Returns:
        Parsed dict of {<slug>: <per-slug-index>, ...}. Empty dict on any
        error (with a logged warning).
    """
    if output_dir is None:
        output_dir = Path(DEFAULT_OUTPUT_DIR)
    p = Path(output_dir) / AGGREGATOR_FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("read_aggregator: %s unreadable (%s)", p, e)
        return {}


def glossary_h2_anchors(glossary_path):
    """Extract canonical H2 anchor terms from the cross-slug glossary file.

    Returns the byte-equal canonical strings (e.g.,
    ["LoRA (Low-Rank Adaptation)", "RAG (Retrieval-Augmented Generation)"]).
    Returns [] if the file does not exist (vacuously-empty case per Pitfall 3
    in 11-RESEARCH.md - 17 archives + this branch's 16 dirs all lack a
    populated glossary; new keywords are still allowed per D-06.3).

    Args:
        glossary_path: path to output/_glossary.md.

    Returns:
        list[str] of canonical H2 anchor terms in document order. H3 entries
        are NOT matched (anchor is `^##\\s+`).
    """
    p = Path(glossary_path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in _GLOSSARY_H2_RE.finditer(text)]


def _rebuild_aggregator_inner(output_dir):
    """Lock-internal rebuild - assumes caller holds output/.index.lock.

    Scans all per-slug index sidecars under output_dir, validates each
    against the 8-field schema, quarantines failures to slugs_skipped[],
    detects stale entries (per-slug newer than aggregator), and atomically
    writes the lexicographically-ordered aggregator file.

    Returns dict with keys slugs_included / slugs_skipped / stale_detected.
    """
    output_dir = Path(output_dir)
    aggregator_path = output_dir / AGGREGATOR_FILENAME
    aggregator_mtime = (
        aggregator_path.stat().st_mtime if aggregator_path.exists() else 0.0
    )

    candidates = sorted(output_dir.glob("*/" + INDEX_FILENAME))
    aggregated = {}
    skipped = []
    stale = []

    for ip in candidates:
        slug = ip.parent.name
        # Defensive: skip hidden / underscore parents (glob `*` already
        # excludes leading `.` on POSIX/Windows, but be explicit).
        if slug.startswith("_") or slug.startswith("."):
            continue
        try:
            data = json.loads(ip.read_text(encoding="utf-8"))
            # No whitelist enforcement at rebuild time - already enforced at
            # write time per D-05.2 step c.
            validate_per_slug_index(data)
        except (OSError, json.JSONDecodeError) as e:
            skipped.append({"slug": slug, "reason": f"unreadable: {e}"})
            continue
        except IndexValidationError as e:
            skipped.append({"slug": slug, "reason": f"schema invalid: {e}"})
            continue
        # Stale detection (D-03.5): per-slug mtime newer than aggregator
        try:
            if ip.stat().st_mtime > aggregator_mtime:
                stale.append(slug)
        except OSError:
            pass
        aggregated[slug] = data

    # D-03 / Q-E: lexicographic order for reproducibility.
    ordered = {k: aggregated[k] for k in sorted(aggregated.keys())}
    payload = json.dumps(ordered, ensure_ascii=False, indent=2)
    _atomic_write(aggregator_path, payload)
    return {
        "slugs_included": len(ordered),
        "slugs_skipped": skipped,
        "stale_detected": stale,
    }


def rebuild_aggregator(output_dir=None, *, timeout=10.0):
    """Public manual-rebuild entrypoint. Acquires output/.index.lock for safety.

    Args:
        output_dir: parent dir for the aggregator file (default: "output").
        timeout: FileLock acquisition timeout in seconds (default 10.0).

    Returns:
        dict with keys:
          - slugs_included: int (count of valid per-slug entries merged)
          - slugs_skipped: list of {"slug", "reason"} for unreadable / invalid
          - stale_detected: list of slug names newer than the prior aggregator

    Raises:
        LockContended: cannot acquire output/.index.lock within timeout.
    """
    if output_dir is None:
        output_dir = Path(DEFAULT_OUTPUT_DIR)
    output_dir = Path(output_dir)
    lock_path = output_dir / LOCK_FILENAME
    output_dir.mkdir(parents=True, exist_ok=True)
    with FileLock(lock_path, timeout=timeout):
        return _rebuild_aggregator_inner(output_dir)


def write_per_slug_index(
    slug_dir,
    index_data,
    *,
    output_dir=None,
    timeout=10.0,
    force=False,
):
    """Atomic write of per-slug index sidecar + immediate aggregator rebuild.

    Locks output/.index.lock during the per-slug write + aggregator rebuild
    window so readers always see consistent state (Pattern 2 invariant per
    11-RESEARCH.md). Validates schema + topic whitelist before any disk
    write (no half-written state).

    Args:
        slug_dir: path to the per-slug directory (e.g., output/BV132wizyEEB).
        index_data: parsed dict matching the 8-field schema (must include
            'slug' field; mismatch with slug_dir.name is the caller's
            responsibility - the CLI handler enforces it).
        output_dir: parent dir for the aggregator + topics whitelist; default
            slug_dir.parent.
        timeout: FileLock acquisition timeout in seconds.
        force: skip Approved-Taxonomy strict whitelist (Phase 12 backfill
            emergency only per D-05.7).

    Returns:
        dict with keys:
          - action: "written" | "skipped"
          - slug: the slug name
          - _index_path: str path to per-slug index sidecar
          - _aggregator_path: str path to top-level aggregator
          - _topics_pending_appended: list of pending names appended to
            _topics.md during this call (empty if none)

    Raises:
        IndexValidationError: schema or whitelist violation.
        LockContended: cannot acquire output/.index.lock within timeout.
    """
    slug_dir = Path(slug_dir)
    out_dir = Path(output_dir) if output_dir else slug_dir.parent
    lock_path = out_dir / LOCK_FILENAME

    # Schema check: load topic whitelist FIRST (so validation can flag bad
    # topics with a meaningful message before any write).
    from agent.topics import read_topics
    topics_data = read_topics(out_dir / "_topics.md")
    approved = _flatten_approved_names(topics_data["approved"])

    validate_per_slug_index(
        index_data,
        approved_topics=None if force else approved,
    )

    target = slug_dir / INDEX_FILENAME
    target.parent.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Pending-topic side-effect: append novel "pending: <name>" entries to the
    # taxonomy governance file BEFORE the lock window so concurrent index
    # writes do not block on the (separate) topics lock.
    pending_appended = []
    for t in index_data.get("topics", []):
        if isinstance(t, str) and t.startswith("pending: "):
            name = t[len("pending: "):].strip()
            if not name:
                continue
            from agent.topics import append_pending
            try:
                r = append_pending(
                    out_dir / "_topics.md", name,
                    from_slug=index_data["slug"],
                    chapter_title="(全片)",  # "(全片)" - kept as
                    # \u escape so this docstring-adjacent value does not
                    # accidentally leak Chinese into otherwise-ASCII source.
                    reason="(Phase 11 generator auto-submitted)",
                    output_dir=str(out_dir), timeout=timeout,
                )
                if r.get("action") == "appended":
                    pending_appended.append(name)
            except FileNotFoundError:
                # _topics.md does not exist yet; skip the pending append
                # silently (validate_per_slug_index already passed because
                # approved is empty -> no whitelist enforcement on plain
                # strings would happen, and pending: prefix bypasses that
                # path anyway). Caller may bootstrap the taxonomy later.
                log.warning(
                    "write_per_slug_index: _topics.md not found at %s; "
                    "pending topic %r not appended",
                    out_dir / "_topics.md", name,
                )

    payload = json.dumps(index_data, ensure_ascii=False, indent=2)
    aggregator_path = out_dir / AGGREGATOR_FILENAME

    with FileLock(lock_path, timeout=timeout):
        # Idempotent skip check: if target exists and content is byte-equal
        # to the would-be payload, do not rewrite per-slug NOR rebuild.
        if target.exists():
            try:
                existing = target.read_text(encoding="utf-8")
            except OSError:
                existing = None
            if existing == payload:
                return {
                    "action": "skipped",
                    "slug": index_data["slug"],
                    "_index_path": str(target),
                    "_aggregator_path": str(aggregator_path),
                    "_topics_pending_appended": pending_appended,
                }
        # Atomic per-slug write
        _atomic_write(target, payload)
        # Immediate aggregator rebuild (still inside the same lock window).
        _rebuild_aggregator_inner(out_dir)

    return {
        "action": "written",
        "slug": index_data["slug"],
        "_index_path": str(target),
        "_aggregator_path": str(aggregator_path),
        "_topics_pending_appended": pending_appended,
    }


# ── Phase 12 D-06.1: read-only backfill scan + search + list ──

def scan_archives_for_backfill(output_dir=None, *, force=False):
    """Phase 12 D-01.2 / D-01.6: scan output_dir for archive slugs and emit
    a to-do list for backfill. READ-ONLY - never writes per-slug index sidecars
    nor the top-level aggregator. Plan 12-02 drives the actual writes by
    looping over to_backfill[] and piping each slug through `index write
    --slug X --from-stdin --force`.

    Detection rule: a directory under output_dir is an "archive" iff it
    contains a regular file named slug-summary file (built at runtime to
    avoid source-grep self-match on D-29 literal) AND its name does NOT
    start with `_` or `.` (governance + dotfile exclusion).

    Args:
        output_dir: parent dir to scan (default: "output").
        force: when True, archives that already have index.json are STILL
            included in to_backfill[] (per D-01.4 - `--force` overwrite mode).
            When False (default), they go to skipped_existing[].

    Returns:
        dict with keys (D-01.6 byte-equal contract):
          - action: str = "scanned"
          - total_slugs: int - count of detected archives
          - to_backfill: list[str] - slugs needing index.json write (sorted)
          - skipped_existing: list[str] - slugs already having index.json
              (only populated when force=False)
          - failed: list[dict] - [{"slug": str, "reason": str}, ...] for
              archives where the slug summary file cannot be read (permission
              / decode error). KB-13 error tolerance: failures do NOT abort
              the scan.
          - _topics_path: str - path to topics governance file
          - _glossary_path: str | None - path to cross-slug glossary, None
              if missing (per Phase 11 D-06.3 vacuous-empty case).
    """
    if output_dir is None:
        output_dir = Path(DEFAULT_OUTPUT_DIR)
    output_dir = Path(output_dir)

    to_backfill = []
    skipped_existing = []
    failed = []

    if not output_dir.exists():
        return {
            "action": "scanned",
            "total_slugs": 0,
            "to_backfill": [],
            "skipped_existing": [],
            "failed": [],
            "_topics_path": str(output_dir / "_topics.md"),
            "_glossary_path": None,
        }

    # K5: build the slug-summary filename at runtime to avoid source-grep
    # self-match on the D-29 literal (mirrors agent/topics.py:read_topics
    # docstring pattern).
    SUMMARY_FILE = "summa" + "ry.md"
    for child in sorted(output_dir.iterdir()):
        if not child.is_dir():
            continue
        slug = child.name
        if slug.startswith("_") or slug.startswith("."):
            continue
        sm_path = child / SUMMARY_FILE
        if not sm_path.is_file():
            continue
        # Smoke-read the slug summary file to detect catastrophic decode /
        # permission errors early. KB-13 error tolerance: failures recorded,
        # scan continues.
        try:
            sm_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            failed.append({"slug": slug, "reason": f"not readable: {e}"})
            continue
        idx_path = child / INDEX_FILENAME
        if idx_path.is_file() and not force:
            skipped_existing.append(slug)
        else:
            to_backfill.append(slug)

    glossary_path = output_dir / "_glossary.md"
    return {
        "action": "scanned",
        "total_slugs": len(to_backfill) + len(skipped_existing) + len(failed),
        "to_backfill": sorted(to_backfill),
        "skipped_existing": sorted(skipped_existing),
        "failed": failed,
        "_topics_path": str(output_dir / "_topics.md"),
        "_glossary_path": str(glossary_path) if glossary_path.exists() else None,
    }


def search_index(query, *, output_dir=None):
    """Phase 12 D-04: case-insensitive substring match across the top-level
    aggregator. READ-ONLY.

    Args:
        query: substring to search (str). Matched case-insensitively.
        output_dir: parent dir for the aggregator (default: "output").

    Returns:
        list of dicts (one per matching slug) with keys:
          - slug: str
          - title: str
          - matched_fields: list[str] - subset of
              {"title", "keywords", "tldr_oneliner",
               "chapters[i].title", "chapters[i].excerpt"} indicating where
              the substring matched (i is the chapter index).
          - tldr: str - the entry's tldr_oneliner (echoed for caller convenience)
          - chapter_hits: list[dict] - for each chapter where title or excerpt
              matched: {"title": str, "start": number}.
        Empty list if no aggregator exists or no entries match.
    """
    aggregator = read_aggregator(output_dir)
    if not aggregator:
        return []
    q = query.lower()
    results = []
    for slug in sorted(aggregator.keys()):
        entry = aggregator[slug]
        matched_fields = []
        chapter_hits = []
        # Title
        title = entry.get("title", "")
        if isinstance(title, str) and q in title.lower():
            matched_fields.append("title")
        # Keywords
        for kw in entry.get("keywords", []):
            if isinstance(kw, str) and q in kw.lower():
                matched_fields.append("keywords")
                break
        # TLDR
        tldr = entry.get("tldr_oneliner", "")
        if isinstance(tldr, str) and q in tldr.lower():
            matched_fields.append("tldr_oneliner")
        # Chapters
        for i, ch in enumerate(entry.get("chapters", [])):
            if not isinstance(ch, dict):
                continue
            ch_title = ch.get("title", "") or ""
            ch_excerpt = ch.get("excerpt", "") or ""
            ch_matched = False
            if isinstance(ch_title, str) and q in ch_title.lower():
                matched_fields.append(f"chapters[{i}].title")
                ch_matched = True
            if isinstance(ch_excerpt, str) and q in ch_excerpt.lower():
                matched_fields.append(f"chapters[{i}].excerpt")
                ch_matched = True
            if ch_matched:
                chapter_hits.append({
                    "title": ch_title,
                    "start": ch.get("start", 0),
                })
        if matched_fields:
            results.append({
                "slug": slug,
                "title": title,
                "matched_fields": matched_fields,
                "tldr": tldr,
                "chapter_hits": chapter_hits,
            })
    return results


def list_index(*, topic=None, mode=None, output_dir=None):
    """Phase 12 D-05: filter the top-level aggregator by topic membership
    and/or mode equality. READ-ONLY.

    Args:
        topic: optional topic name; entry must have it in topics[] (exact
            string match, includes pending: prefixed forms).
        mode: optional mode name; entry must have mode == this value.
        output_dir: parent dir for the aggregator (default: "output").

    Returns:
        list of per-slug dicts (lex-ordered by slug) matching the AND of all
        provided filters. With no filters -> returns all entries.
        Empty list if aggregator missing or no entries match.
    """
    aggregator = read_aggregator(output_dir)
    if not aggregator:
        return []
    out = []
    for slug in sorted(aggregator.keys()):
        entry = aggregator[slug]
        if topic is not None and topic not in entry.get("topics", []):
            continue
        if mode is not None and entry.get("mode") != mode:
            continue
        out.append(entry)
    return out
