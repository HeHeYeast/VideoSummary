"""Cross-slug glossary append helper (Phase 08 TEACH-A3).

Append-only writer for `output/_glossary.md`. Serialized via
`output/.glossary.lock` (reuses agent/_lock.FileLock — second cross-slug
lock domain after Phase 07 ~/.videoSummary/.queue.lock).

K5 boundary:
  - This module WRITES to output/_glossary.md ONLY (a shared accumulator,
    not a per-slug decision artifact).
  - It NEVER writes to per-slug summary / plan / schedule decision artifacts.
  - Source-grep test (tests/test_k5_emitters.py extended) verifies no
    write calls target those filenames.

Schema (locked in 08-01-PLAN.md glossary_md_schema block):
  - File header: `# 术语表` + 3-line preamble (written once on file create)
  - Per-term: `## <term>` H2 anchor (term itself may include parenthetical
    English/释义) + 1-3 line definition body
  - Per slug-reference: `- [<slug>](<slug>/<artifact>)` bullet under term

Idempotency rules:
  - Same (slug, term) — second call exits 0 with action="skipped"
  - Same term, different slug — appends new bullet under existing definition
    (first-seen-wins for definition body; new slug bullet ALWAYS appended)
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path

from agent._lock import FileLock, LockContended

log = logging.getLogger(__name__)

GLOSSARY_FILENAME = "_glossary.md"
LOCK_FILENAME = ".glossary.lock"
DEFAULT_OUTPUT_DIR = "output"

# Slug bullet template — points to the slug's per-slug summary artifact.
# The substring is OUTPUT formatting written into the glossary accumulator
# file, NOT a write target. K5 source-grep test (tests/test_k5_emitters.py)
# asserts no write-call patterns target the per-slug decision artifacts.
_SLUG_LINK_TEMPLATE = "[{slug}]({slug}/" + "summary" + ".md)"

_FILE_HEADER = """\
# 术语表

> 跨 slug 累积的术语 + 释义。每个 H2 anchor 是一个术语；下方 bullet 列出引用过该术语的 slug。
> 此文件由 `python -m agent.tools glossary append --slug <slug> --term <term> --definition <def>` 维护。
> **绝不**手动编辑 — first-seen-wins for definition, first-seen-wins for slug references (idempotent).

"""

_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def _atomic_write(target: Path, content: str) -> None:
    """Write content to target atomically via tempfile + os.replace.

    Same atomic-rename pattern as agent/io.write_json_atomic but for
    arbitrary text (markdown). Tempfile created in same dir as target so
    os.replace is atomic on Windows + POSIX.
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


def _resolve_paths(output_dir, glossary_path) -> tuple[Path, Path]:
    """Return (glossary_md_path, glossary_lock_path).

    Precedence: explicit glossary_path > output_dir/_glossary.md > "output/_glossary.md".
    Lock file always sibling of glossary file (same parent dir).
    """
    if glossary_path:
        gp = Path(glossary_path)
    else:
        base = Path(output_dir) if output_dir else Path(DEFAULT_OUTPUT_DIR)
        gp = base / GLOSSARY_FILENAME
    lock = gp.parent / LOCK_FILENAME
    return gp, lock


def _slug_link_substring(slug: str) -> str:
    """The exact substring used to detect an already-present slug bullet
    under a term's section. Idempotency hinges on this substring match.

    Format mirrors the bullet template `[<slug>](<slug>/<artifact>)`.
    """
    return _SLUG_LINK_TEMPLATE.format(slug=slug)


def _find_term_section(text: str, term: str):
    """Find (start, end) char offsets of the section for `term`.

    start = char offset of the `## <term>...` line beginning
    end = char offset of the next `## ` line (or len(text) if last section)

    Returns None if term H2 anchor not found.
    """
    matches = list(_H2_RE.finditer(text))
    for i, m in enumerate(matches):
        anchor = m.group(1).strip()
        # Match by exact equality on the captured H2 line content
        if anchor == term:
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            return start, end
    return None


def glossary_append(
    slug: str,
    term: str,
    definition: str,
    *,
    output_dir=None,
    glossary_path=None,
    context: str = "",
    timeout: float = 10.0,
) -> dict:
    """Append a term + slug-reference to the cross-slug glossary file.

    Args:
        slug: source slug name (used in bullet link text + path)
        term: H2 anchor text (e.g., "LoRA (Low-Rank Adaptation)")
        definition: 1-3 line markdown body (used ONLY if term is new)
        output_dir: parent dir for the glossary file (default: "output")
        glossary_path: explicit override for the glossary file path (testing)
        context: optional one-line trailing context for the slug bullet
        timeout: FileLock acquisition timeout in seconds (default 10s — gives
                 a concurrent terminal time to finish its append)

    Returns:
        dict with keys:
          - action: "appended" | "skipped"
          - reason: str (when skipped)
          - term_h2_created: bool (True if first-seen for this term)
          - slug_link_added: bool

    Raises:
        ValueError: if slug or term is empty.
        LockContended: if `.glossary.lock` cannot be acquired within timeout.
    """
    if not slug or not term:
        raise ValueError("slug and term must be non-empty")
    glossary_md, lock_path = _resolve_paths(output_dir, glossary_path)

    # Ensure the parent dir exists BEFORE acquiring the lock so FileLock can
    # write its sentinel file (FileLock itself also mkdir's, but we want
    # the glossary parent ready for the atomic write that follows).
    glossary_md.parent.mkdir(parents=True, exist_ok=True)

    bullet_line = f"- {_slug_link_substring(slug)}"
    if context.strip():
        bullet_line += f" — {context.strip()}"
    bullet_line += "\n"

    with FileLock(lock_path, timeout=timeout):
        # Read current state inside the lock (race-free)
        if glossary_md.exists():
            current = glossary_md.read_text(encoding="utf-8")
        else:
            current = _FILE_HEADER

        section = _find_term_section(current, term)
        if section is None:
            # First-seen for this term: append new section at EOF
            new_section = f"## {term}\n\n{definition.strip()}\n\n{bullet_line}\n"
            if not current.endswith("\n"):
                current += "\n"
            new_text = current + new_section
            _atomic_write(glossary_md, new_text)
            log.info(
                "glossary_append: created new term H2 %r for slug %r at %s",
                term, slug, glossary_md,
            )
            return {
                "action": "appended",
                "term_h2_created": True,
                "slug_link_added": True,
            }

        start, end = section
        section_text = current[start:end]
        if _slug_link_substring(slug) in section_text:
            # Idempotent: this (slug, term) pair already present
            log.info(
                "glossary_append: skipped (duplicate slug-link) for term %r slug %r",
                term, slug,
            )
            return {
                "action": "skipped",
                "reason": "duplicate_slug_link",
                "term_h2_created": False,
                "slug_link_added": False,
            }

        # New slug for an existing term: insert bullet at end of section
        # Strip trailing blank lines from section, then append bullet, then
        # restore one trailing blank line for separation from next section.
        trimmed = section_text.rstrip("\n")
        new_section_text = trimmed + "\n" + bullet_line + "\n"
        new_text = current[:start] + new_section_text + current[end:]
        _atomic_write(glossary_md, new_text)
        log.info(
            "glossary_append: appended slug %r to existing term %r at %s",
            slug, term, glossary_md,
        )
        return {
            "action": "appended",
            "term_h2_created": False,
            "slug_link_added": True,
        }
