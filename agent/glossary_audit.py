"""K5 read-only glossary auditor (Phase 07 — Phase 08 TEACH-A3 helper stub).

Audits `output/_glossary.md` for duplicate term entries and conflicting
definitions. NEVER edits the glossary file (K5 read-only).

Phase 07 ships a stub that:
  - Returns the schema shape on missing file (exists=False, all empties)
  - On existing file: parses H2 anchors and reports duplicates
  - Future Phase 08 TEACH-A3 will plug in cross-summary frequency tracking

Source code MUST NOT reference the summary/plan artifact filenames — phrase
as "the summary artifact" / "the plan artifact" instead. K5 source-grep
test enforces this.
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

DEFAULT_GLOSSARY_PATH = "output/_glossary.md"
_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


def audit_glossary(path: str | Path | None = None) -> dict:
    """Audit a glossary file. Returns schema-stable dict.

    If `path` is None, defaults to "output/_glossary.md" (Phase 08 TEACH-A3 location).
    Missing file is NOT an error — returns exists=False shape.
    """
    target = Path(path) if path else Path(DEFAULT_GLOSSARY_PATH)
    if not target.exists():
        return {
            "version": 1,
            "glossary_path": str(target),
            "exists": False,
            "term_count": 0,
            "duplicate_terms": [],
            "conflicting_definitions": [],
        }

    text = target.read_text(encoding="utf-8")
    # Find all H2 term anchors
    matches = list(_H2_RE.finditer(text))
    term_count = len(matches)

    # Bucket terms -> list of (definition_text)
    term_defs: dict[str, list[str]] = defaultdict(list)
    for i, m in enumerate(matches):
        term = m.group(1).strip()
        # Definition body is from end-of-this-h2 to start-of-next-h2 (or EOF)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        term_defs[term].append(body)

    duplicate_terms = sorted(t for t, defs in term_defs.items() if len(defs) > 1)
    conflicting_definitions: list[dict] = []
    for term in duplicate_terms:
        defs = term_defs[term]
        # "Conflicting" = the definitions are not identical (modulo whitespace)
        normalized = {re.sub(r"\s+", " ", d).strip() for d in defs}
        if len(normalized) > 1:
            conflicting_definitions.append({
                "term": term,
                "definitions": defs,
            })

    return {
        "version": 1,
        "glossary_path": str(target),
        "exists": True,
        "term_count": term_count,
        "duplicate_terms": duplicate_terms,
        "conflicting_definitions": conflicting_definitions,
    }
