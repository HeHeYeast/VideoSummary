"""Topic taxonomy governance file accumulator (Phase 10 D-01..D-08).

Read-modify-write writer for `output/_topics.md`. Serialized via
`output/.topics.lock` (reuses agent/_lock.FileLock — third cross-slug lock
domain after Phase 07 ~/.videoSummary/.queue.lock and Phase 08
output/.glossary.lock).

K5 boundary:
  - This module WRITES to the top-level governance file ONLY (and to per-slug
    index sidecars during resolve, which is the sole exception).
  - It NEVER writes to per-slug decision artifacts (the slug summary file,
    the slug plan file, the slug schedule artifact, paragraphs, segs, meta).
  - Source-grep tests (tests/test_k5_emitters.py) verify no write calls
    target those filenames. Note: this module docstring deliberately uses
    prose ("the slug summary file") instead of literal filenames to avoid
    regex self-match on the K5 boundary tests (Phase 08-01 deviation #2
    lesson).

Schema (locked in 10-CONTEXT.md D-01.1..D-01.6):
  - File header: `# Topics Taxonomy` + 4-line preamble (written once on
    bootstrap)
  - `## Approved Taxonomy` segment: nested bullet list (max 3 levels deep,
    `- L1` / `  - L2` / `    - L3`)
  - `## Pending` segment: `### <name>` H3 entries with 3 mandatory bullet
    sub-fields (申请来源 slug / chapter title / 提议理由)

Idempotency:
  - write_approved_taxonomy on a populated file → action="skipped"
  - append_pending on a duplicate name → action="skipped" (idempotent)
  - resolve_pending on an unknown name → KeyError (fail-fast, not idempotent
    per D-04.6)

Concurrency:
  - All writers acquire output/.topics.lock via FileLock context manager.
  - read_topics is lock-free (D-08.4 — audit must not block governance flow).
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

TOPICS_FILENAME = "_topics.md"
LOCK_FILENAME = ".topics.lock"
DEFAULT_OUTPUT_DIR = "output"

# Regex constants — anchored at line start, MULTILINE.
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^(\s*)-\s+(.+?)\s*$", re.MULTILINE)

# D-01.6 locked file header — byte-equal across re-runs.
_FILE_HEADER = """\
# Topics Taxonomy

> v1.2 knowledge-base governance — `## Approved Taxonomy` 段是 Claude 写 index.json
> 时的 topic 白名单；`## Pending` 段是 Claude 申请的新 topic 待用户 review。
> 此文件由 `python -m agent.tools topics {bootstrap,audit,resolve}` CLI + Phase 11
> generator (`agent.topics.append_pending`) 共同维护。

## Approved Taxonomy

<!-- (initially empty until bootstrap runs) -->

## Pending

<!-- (Claude 申请新 topic 时由 Phase 11 generator 在此 append H3 entry) -->

"""


def _atomic_write(target: Path, content: str) -> None:
    """Write content to target atomically via tempfile + os.replace.

    Same pattern as agent/glossary.py:_atomic_write — tempfile created in
    target.parent so os.replace is cross-device atomic on Windows + POSIX.
    Tempfile cleaned up on exception.
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


def _resolve_paths(output_dir, topics_path) -> tuple[Path, Path]:
    """Return (topics_md_path, lock_path).

    Precedence: explicit topics_path > output_dir/_topics.md > "output/_topics.md".
    Lock file always sibling of topics file (same parent dir).
    """
    if topics_path:
        tp = Path(topics_path)
    else:
        base = Path(output_dir) if output_dir else Path(DEFAULT_OUTPUT_DIR)
        tp = base / TOPICS_FILENAME
    lock = tp.parent / LOCK_FILENAME
    return tp, lock


def _segment_bounds(text: str, h2_name: str) -> tuple[int, int] | None:
    """Find char offsets [start, end) of an H2 segment by name.

    start = char offset of next char AFTER the H2 header line (i.e., body start).
    end = char offset of the next H2 header line, or len(text) if last segment.
    Returns None if h2_name H2 not found.
    """
    matches = list(_H2_RE.finditer(text))
    for i, m in enumerate(matches):
        if m.group(1).strip() == h2_name:
            # body starts after the line containing the H2 header
            line_end = text.find("\n", m.end())
            body_start = (line_end + 1) if line_end != -1 else len(text)
            body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return body_start, body_end
    return None


def _parse_approved_tree(body_text: str) -> list[dict]:
    """Parse a markdown nested bullet list into a list of {name, subtopics}.

    Handles 2-space indent per level (D-01.3). Ignores HTML comment
    placeholders (`<!-- ... -->`).
    """
    items: list[dict] = []
    # Stack: list of (level, list-ref) — list-ref is the subtopics list at that level
    stack: list[tuple[int, list[dict]]] = [(-1, items)]
    for line in body_text.splitlines():
        m = _LIST_ITEM_RE.match(line)
        if not m:
            continue
        indent_str, name = m.group(1), m.group(2)
        # Skip HTML comments accidentally bullet-ed
        if name.startswith("<!--"):
            continue
        # Indent assumption: 2 spaces per level
        level = len(indent_str) // 2
        # Pop stack to the parent level (level-1)
        while stack and stack[-1][0] >= level:
            stack.pop()
        if not stack:
            # Defensive: malformed indent, attach to root
            stack = [(-1, items)]
        node: dict = {"name": name.strip(), "subtopics": []}
        stack[-1][1].append(node)
        stack.append((level, node["subtopics"]))
    return items


def _parse_pending_entries(body_text: str) -> list[dict]:
    """Parse `### <name>` H3 entries with 3 sub-fields each."""
    entries: list[dict] = []
    h3_matches = list(_H3_RE.finditer(body_text))
    for i, m in enumerate(h3_matches):
        name = m.group(1).strip()
        block_start = m.end()
        block_end = h3_matches[i + 1].start() if i + 1 < len(h3_matches) else len(body_text)
        block_body = body_text[block_start:block_end]
        from_slug = ""
        chapter_title = ""
        reason = ""
        for line in block_body.splitlines():
            line_stripped = line.lstrip()
            if line_stripped.startswith("- 申请来源 slug:"):
                from_slug = line_stripped[len("- 申请来源 slug:"):].strip()
            elif line_stripped.startswith("- chapter title:"):
                chapter_title = line_stripped[len("- chapter title:"):].strip()
            elif line_stripped.startswith("- 提议理由:"):
                reason = line_stripped[len("- 提议理由:"):].strip()
        entries.append({
            "name": name,
            "from_slug": from_slug,
            "chapter_title": chapter_title,
            "reason": reason,
        })
    return entries


def read_topics(topics_path: Path) -> dict:
    """Read and parse the topics governance file.

    Args:
        topics_path: path to `_topics.md`.

    Returns:
        dict with keys:
          - approved: list[dict] — nested taxonomy tree (each node has
                                   {name, subtopics})
          - pending:  list[dict] — pending H3 entries (each has
                                   {name, from_slug, chapter_title, reason})
          - exists: bool — True if the file exists; False if not.
    """
    topics_path = Path(topics_path)
    if not topics_path.exists():
        return {"approved": [], "pending": [], "exists": False}
    text = topics_path.read_text(encoding="utf-8")

    approved_bounds = _segment_bounds(text, "Approved Taxonomy")
    pending_bounds = _segment_bounds(text, "Pending")

    approved: list[dict] = []
    pending: list[dict] = []
    if approved_bounds:
        s, e = approved_bounds
        approved = _parse_approved_tree(text[s:e])
    if pending_bounds:
        s, e = pending_bounds
        pending = _parse_pending_entries(text[s:e])

    return {"approved": approved, "pending": pending, "exists": True}


def _validate_taxonomy(taxonomy: list, depth: int = 1, path: str = "") -> int:
    """Validate taxonomy tree. Returns flat count of all named nodes.

    Raises:
        ValueError on:
          - depth > 3
          - non-string / empty name
          - duplicate names at the same level
    """
    if depth > 3:
        raise ValueError(
            f"taxonomy nesting exceeds 3 levels at {path}; max 3 levels allowed"
        )
    if not isinstance(taxonomy, list):
        raise ValueError(
            f"each taxonomy level must be a list, got {type(taxonomy).__name__} at {path}"
        )
    seen_at_level: set[str] = set()
    flat_count = 0
    for entry in taxonomy:
        if not isinstance(entry, dict):
            raise ValueError(
                f"each taxonomy entry must be a dict, got {type(entry).__name__} at {path}"
            )
        name = entry.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(
                f"each taxonomy entry must have non-empty string 'name', got {name!r} at {path}"
            )
        name_stripped = name.strip()
        if name_stripped in seen_at_level:
            raise ValueError(
                f"duplicate category name in taxonomy: {name_stripped!r} at {path}"
            )
        seen_at_level.add(name_stripped)
        flat_count += 1
        subtopics = entry.get("subtopics", [])
        if subtopics:
            child_path = f"{path}/{name_stripped}" if path else name_stripped
            flat_count += _validate_taxonomy(subtopics, depth + 1, child_path)
    return flat_count


def _render_approved_tree(taxonomy: list[dict], indent_level: int = 0) -> str:
    """Render taxonomy tree as nested markdown bullet list (2-space indent)."""
    lines: list[str] = []
    for entry in taxonomy:
        name = entry["name"].strip()
        prefix = "  " * indent_level
        lines.append(f"{prefix}- {name}")
        subtopics = entry.get("subtopics", [])
        if subtopics:
            lines.append(_render_approved_tree(subtopics, indent_level + 1))
    return "\n".join(lines)


def _render_full_file(approved: list[dict], pending_block: str = "") -> str:
    """Render the full _topics.md file content from approved tree + pending block.

    The pending_block argument is the raw text of the `## Pending` section's
    body (everything between `## Pending\\n` and EOF, exclusive of the H2 line).
    """
    if approved:
        approved_body = _render_approved_tree(approved) + "\n"
    else:
        approved_body = "<!-- (initially empty until bootstrap runs) -->\n"
    if pending_block.strip():
        pending_body = pending_block
    else:
        pending_body = (
            "<!-- (Claude 申请新 topic 时由 Phase 11 generator 在此 append H3 entry) -->\n"
        )
    # Build top header lines (everything before `## Approved Taxonomy`).
    header_top = (
        "# Topics Taxonomy\n"
        "\n"
        "> v1.2 knowledge-base governance — `## Approved Taxonomy` 段是 Claude 写 index.json\n"
        "> 时的 topic 白名单；`## Pending` 段是 Claude 申请的新 topic 待用户 review。\n"
        "> 此文件由 `python -m agent.tools topics {bootstrap,audit,resolve}` CLI + Phase 11\n"
        "> generator (`agent.topics.append_pending`) 共同维护。\n"
        "\n"
    )
    return (
        header_top
        + "## Approved Taxonomy\n\n"
        + approved_body
        + "\n## Pending\n\n"
        + pending_body
        + ("\n" if not pending_body.endswith("\n") else "")
    )


def write_approved_taxonomy(
    topics_path: Path,
    taxonomy: list[dict],
    *,
    output_dir=None,
    timeout: float = 10.0,
) -> dict:
    """Write the Approved Taxonomy segment (bootstrap entry point).

    Idempotent skip if `_topics.md` already exists with non-empty Approved
    Taxonomy. Validates taxonomy structure (max 3 levels, non-empty string
    names, no same-level duplicates) before any disk write.

    Args:
        topics_path: path to `_topics.md` (or None to use default).
        taxonomy: list of {"name": str, "subtopics": [...]} (3 levels max).
        output_dir: parent dir for the topics file (default: "output").
        timeout: FileLock acquisition timeout in seconds.

    Returns:
        dict with keys:
          - action: "created" | "skipped"
          - approved_count: total flat node count (every node in tree)

    Raises:
        ValueError: malformed taxonomy structure.
        LockContended: cannot acquire `.topics.lock` within timeout.
    """
    topics_path, lock_path = _resolve_paths(output_dir, topics_path)
    flat_count = _validate_taxonomy(taxonomy)
    topics_path.parent.mkdir(parents=True, exist_ok=True)
    with FileLock(lock_path, timeout=timeout):
        if topics_path.exists():
            existing = read_topics(topics_path)
            if existing["approved"]:
                log.info(
                    "write_approved_taxonomy: skipped (already populated) at %s",
                    topics_path,
                )
                # Count existing flat node count for a meaningful return value.
                existing_count = _count_flat(existing["approved"])
                return {"action": "skipped", "approved_count": existing_count}
        # Compose the new file content. Preserve any existing Pending block
        # (rare on bootstrap but safe for forward-compat).
        existing_pending = ""
        if topics_path.exists():
            old_text = topics_path.read_text(encoding="utf-8")
            pb = _segment_bounds(old_text, "Pending")
            if pb:
                existing_pending = old_text[pb[0]:pb[1]]
        new_text = _render_full_file(taxonomy, existing_pending)
        _atomic_write(topics_path, new_text)
        log.info(
            "write_approved_taxonomy: created %s with %d approved nodes",
            topics_path, flat_count,
        )
        return {"action": "created", "approved_count": flat_count}


def _count_flat(taxonomy: list[dict]) -> int:
    """Recursive flat count of all nodes in a taxonomy tree."""
    n = 0
    for entry in taxonomy:
        n += 1
        n += _count_flat(entry.get("subtopics", []))
    return n


def append_pending(
    topics_path: Path,
    name: str,
    from_slug: str,
    chapter_title: str,
    reason: str,
    *,
    output_dir=None,
    timeout: float = 10.0,
) -> dict:
    """Append an H3 entry under `## Pending`. Phase 11 generator entry point.

    Args:
        topics_path: path to `_topics.md`.
        name: pending topic name (becomes `### <name>` H3 anchor).
        from_slug: slug that proposed this topic (e.g., 'BV1HG9JBsEPK').
        chapter_title: chapter heading where this topic was first needed.
        reason: 1-line justification why this should be approved.
        output_dir: parent dir for the topics file (default: "output").
        timeout: FileLock acquisition timeout in seconds.

    Returns:
        dict with keys:
          - action: "appended" | "skipped"
          - reason: str (when skipped, e.g., "duplicate_pending_name")
          - name: the pending name (for logging)

    Raises:
        ValueError: any of the 4 string args is empty.
        FileNotFoundError: topics_path does not exist (run bootstrap first).
        LockContended: cannot acquire `.topics.lock` within timeout.
    """
    if not (name and from_slug and chapter_title and reason):
        raise ValueError(
            "name, from_slug, chapter_title, reason must all be non-empty strings"
        )
    topics_path, lock_path = _resolve_paths(output_dir, topics_path)
    topics_path.parent.mkdir(parents=True, exist_ok=True)

    with FileLock(lock_path, timeout=timeout):
        if not topics_path.exists():
            raise FileNotFoundError(
                f"`{topics_path}` does not exist; run `python -m agent.tools topics "
                f"bootstrap --from-stdin` first"
            )
        text = topics_path.read_text(encoding="utf-8")
        pb = _segment_bounds(text, "Pending")
        if pb is None:
            raise ValueError(
                f"`{topics_path}` is malformed: no `## Pending` segment found"
            )
        body_start, body_end = pb
        pending_body = text[body_start:body_end]
        # Idempotent check: H3 with this exact name already there?
        existing_entries = _parse_pending_entries(pending_body)
        if any(e["name"] == name for e in existing_entries):
            log.info(
                "append_pending: skipped (duplicate name %r) in %s", name, topics_path,
            )
            return {"action": "skipped", "reason": "duplicate_pending_name", "name": name}
        # Build new H3 block.
        new_block = (
            f"### {name}\n"
            f"- 申请来源 slug: {from_slug}\n"
            f"- chapter title: {chapter_title}\n"
            f"- 提议理由: {reason}\n"
            f"\n"
        )
        # Strip the placeholder HTML comment if present (first append).
        cleaned_pending = re.sub(
            r"<!--\s*\(Claude.*?\)\s*-->\s*\n?",
            "",
            pending_body,
            count=1,
            flags=re.DOTALL,
        )
        # Make sure we end with a single trailing newline before appending.
        cleaned_pending = cleaned_pending.rstrip("\n")
        if cleaned_pending:
            new_pending_body = cleaned_pending + "\n\n" + new_block
        else:
            new_pending_body = new_block
        # Reassemble file.
        new_text = text[:body_start] + new_pending_body + text[body_end:]
        _atomic_write(topics_path, new_text)
        log.info(
            "append_pending: appended %r (from_slug=%r) to %s",
            name, from_slug, topics_path,
        )
        return {"action": "appended", "name": name}


def _insert_into_approved(taxonomy: list[dict], path: list[str]) -> list[dict]:
    """Return a NEW taxonomy with `path` inserted alphabetically.

    `path` is a list of names (e.g., ["LangChain"] or ["LLM", "LangChain"]).
    For nested paths, the parent must exist OR will be created.
    """
    if not path:
        return taxonomy
    head, *rest = path
    new_taxonomy = [dict(e, subtopics=list(e.get("subtopics", []))) for e in taxonomy]
    # Find existing entry with this head name
    existing_idx = None
    for i, entry in enumerate(new_taxonomy):
        if entry["name"] == head:
            existing_idx = i
            break
    if existing_idx is None:
        # Create new entry; insert alphabetically
        new_entry = {"name": head, "subtopics": []}
        if rest:
            new_entry["subtopics"] = _insert_into_approved([], rest)
        # Find insertion index (alphabetical, case-insensitive on first char)
        insert_at = len(new_taxonomy)
        for i, entry in enumerate(new_taxonomy):
            if head.lower() < entry["name"].lower():
                insert_at = i
                break
        new_taxonomy.insert(insert_at, new_entry)
    else:
        # Recurse into existing entry's subtopics
        if rest:
            new_taxonomy[existing_idx]["subtopics"] = _insert_into_approved(
                new_taxonomy[existing_idx]["subtopics"], rest,
            )
        # else: head is leaf and already present; no-op (idempotent)
    return new_taxonomy


def resolve_pending(
    topics_path: Path,
    pending_name: str,
    *,
    rename: str | None = None,
    remove: bool = False,
    output_dir: Path | None = None,
    timeout: float = 10.0,
) -> dict:
    """Promote / rename / remove a pending H3 entry, atomically.

    `rename` supports a slash-delimited path like `"LLM/LangChain"` to place
    the new entry under a parent category (creating the parent if absent).

    Atomic semantics:
      - Snapshot the topics file plus all per-slug index sidecars referencing
        the pending name.
      - Compute new content for each in memory.
      - Write all files via _atomic_write.
      - On any exception during write, restore each already-written file
        from its snapshot.

    Args:
        topics_path: path to `_topics.md` (or None to use default).
        pending_name: exact `### <name>` from the Pending segment.
        rename: optional new canonical name (supports nested `parent/leaf`).
        remove: if True, reject pending: drop the H3 + clear refs in indexes.
        output_dir: parent dir for `_topics.md` and per-slug index sidecars.
        timeout: FileLock acquisition timeout in seconds.

    Returns:
        dict with keys: action, pending_name, final_name, index_json_updated,
        and a `_topics_path` string.

    Raises:
        ValueError: rename + remove both given (mutually exclusive); empty name.
        KeyError: pending_name not found in `## Pending` segment.
        LockContended: cannot acquire `.topics.lock` within timeout.
    """
    if rename and remove:
        raise ValueError("--rename and --remove are mutually exclusive")
    if not pending_name or not isinstance(pending_name, str):
        raise ValueError("pending_name must be a non-empty string")

    topics_path, lock_path = _resolve_paths(output_dir, topics_path)
    out_dir = Path(output_dir) if output_dir else topics_path.parent

    # Decide final_name semantics
    if remove:
        final_name = None
        action = "removed"
    elif rename:
        # For nested rename like "LLM/LangChain", final canonical leaf name
        # is the last path segment. (CLI / API consumers may want full path
        # back; we surface the full rename string in `final_name` to
        # preserve the locked stdout schema D-04.5.)
        final_name = rename
        action = "renamed"
    else:
        final_name = pending_name
        action = "promoted"

    with FileLock(lock_path, timeout=timeout):
        if not topics_path.exists():
            raise FileNotFoundError(f"`{topics_path}` does not exist")
        topics_text_orig = topics_path.read_text(encoding="utf-8")
        # Verify pending_name is present
        pb = _segment_bounds(topics_text_orig, "Pending")
        if pb is None:
            raise KeyError(f"pending entry not found: {pending_name}")
        pending_body = topics_text_orig[pb[0]:pb[1]]
        existing_entries = _parse_pending_entries(pending_body)
        names = {e["name"] for e in existing_entries}
        if pending_name not in names:
            raise KeyError(f"pending entry not found: {pending_name}")

        # Compose new pending body (without the resolved H3)
        new_pending_body = _strip_pending_h3(pending_body, pending_name)

        # Compose new approved taxonomy
        existing_topics = read_topics(topics_path)
        approved = existing_topics["approved"]
        if remove:
            new_approved = approved
        else:
            # Determine insertion path
            insert_path = (rename or pending_name).split("/")
            # Strip empty path segments
            insert_path = [p.strip() for p in insert_path if p.strip()]
            new_approved = _insert_into_approved(approved, insert_path)

        new_topics_text = _render_full_file(new_approved, new_pending_body)

        # Scan per-slug index sidecars referencing the pending name
        index_paths = sorted(out_dir.glob("*/index.json"))
        index_snapshots: dict[Path, str] = {}
        index_new_contents: dict[Path, str] = {}
        affected_slugs: list[str] = []
        pending_token = f"pending: {pending_name}"
        replacement_token = final_name if not remove else None
        for ip in index_paths:
            try:
                orig_text = ip.read_text(encoding="utf-8")
                obj = json.loads(orig_text)
            except (OSError, json.JSONDecodeError) as e:
                log.warning(
                    "resolve_pending: skipping unreadable %s (%s)", ip, e,
                )
                continue
            modified = False
            # Top-level topics array
            top_topics = obj.get("topics")
            if isinstance(top_topics, list):
                new_top = []
                for t in top_topics:
                    if isinstance(t, str) and t == pending_token:
                        modified = True
                        if not remove:
                            new_top.append(replacement_token)
                        # else drop it
                    else:
                        new_top.append(t)
                if modified:
                    obj["topics"] = new_top
            # Per-chapter topics
            chapters = obj.get("chapters")
            if isinstance(chapters, list):
                for ch in chapters:
                    if not isinstance(ch, dict):
                        continue
                    ch_topics = ch.get("topics")
                    if not isinstance(ch_topics, list):
                        continue
                    new_ch = []
                    chapter_modified = False
                    for t in ch_topics:
                        if isinstance(t, str) and t == pending_token:
                            chapter_modified = True
                            modified = True
                            if not remove:
                                new_ch.append(replacement_token)
                        else:
                            new_ch.append(t)
                    if chapter_modified:
                        ch["topics"] = new_ch
                        if not new_ch and remove:
                            log.warning(
                                "resolve_pending --remove: chapter %r in %s now "
                                "has no topics; review and re-tag if needed",
                                ch.get("title", "<untitled>"), ip,
                            )
            if modified:
                index_snapshots[ip] = orig_text
                index_new_contents[ip] = json.dumps(obj, ensure_ascii=False, indent=2)
                affected_slugs.append(ip.parent.name)

        # Atomic multi-file write with snapshot restore on failure
        written: list[Path] = []
        try:
            _atomic_write(topics_path, new_topics_text)
            written.append(topics_path)
            for ip, new_text in index_new_contents.items():
                _atomic_write(ip, new_text)
                written.append(ip)
        except Exception:
            log.error(
                "resolve_pending: write failed; restoring %d already-written files",
                len(written), exc_info=True,
            )
            # Restore in-memory snapshots for everything we wrote
            for p in written:
                try:
                    if p == topics_path:
                        _atomic_write(p, topics_text_orig)
                    elif p in index_snapshots:
                        _atomic_write(p, index_snapshots[p])
                except Exception:
                    log.error(
                        "resolve_pending: restore failed for %s", p, exc_info=True,
                    )
            raise

        log.info(
            "resolve_pending: %s %r -> %r (updated %d index sidecars) at %s",
            action, pending_name, final_name, len(affected_slugs), topics_path,
        )
        return {
            "action": action,
            "pending_name": pending_name,
            "final_name": final_name,
            "index_json_updated": affected_slugs,
            "_topics_path": str(topics_path),
        }


def _strip_pending_h3(pending_body: str, name: str) -> str:
    """Remove an H3 block named `name` from a Pending segment body."""
    h3_pattern = re.compile(
        r"^###\s+" + re.escape(name) + r"\s*$",
        re.MULTILINE,
    )
    m = h3_pattern.search(pending_body)
    if not m:
        return pending_body
    # Find the block end: the next `### ` line or end of body.
    next_h3 = _H3_RE.search(pending_body, m.end())
    block_end = next_h3.start() if next_h3 else len(pending_body)
    # Trim trailing blank lines before the next H3 / end
    new_body = pending_body[:m.start()] + pending_body[block_end:]
    # Collapse runs of >2 blank lines that may now appear
    new_body = re.sub(r"\n{3,}", "\n\n", new_body)
    return new_body
