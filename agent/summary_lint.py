"""Phase 09 CORR-03a — mechanical format-spec + citation + glossary checker.

K5 boundary: this module READS the input artifact (a slug-level summary file)
and produces a sibling lint report; it NEVER modifies the input artifact.
The literal substring naming the input file appears in this file ONLY as
part of the LINT_FILENAME naming context. The plan / schedule decision
artifact filenames have no legitimate use here and are absent entirely.

Statically asserted by tests/test_k5_emitters.py via _WRITE_PATTERNS_FORBIDDEN
regex (mirrors the Phase 08-01 agent/glossary.py exception: substring is
legitimate as a description / input arg path; what's forbidden is the WRITE
pattern targeting the decision artifact via write_text / open(...,'w') /
os.replace / _atomic_write).

Format-spec invariants checked (CLAUDE.md `### 格式锁定` 4+1 项):
  1. timestamp_format         — `[HH:MM:SS]` exactly 8 chars between brackets
  2. code_fence_language      — every opening ``` declares a language token
  3. relative_frame_paths     — image src must be `frames/...{jpg|jpeg|png|webp}`
  4. second_person_imperative — forbid `我们 + verb` and `noun + 被 + verb`
  5. trace_after_claim        — load-bearing claim lines in body must end
                                with `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` or
                                `[para_NNNN @ HH:MM:SS]`

Additional checks:
  - citation_stats              — claims_total / claims_with_trace / density / [?]
  - citation_eligibility_violations — trace tokens FORBIDDEN in TL;DR / 你需要
                                    prelude / 你不需要知道什么 / transitions
  - glossary_inconsistencies    — inline term `Foo (definition)` must agree
                                  with `## Foo (definition)` in glossary

Heuristic limits (documented for the Phase 09-02 verifier subagent):
  - second_person_imperative uses a small forbidden-action allowlist
    (打开/创建/配置/运行/执行/导入/启动) to keep false-positive rate low.
  - load-bearing detection uses lexical signals (numbers, units, fenced spans,
    paths, file extensions); paragraphs that are pure narrative (e.g. "这一节
    讲的是 X") may slip through and not be flagged — that is intentional, the
    verifier subagent provides semantic backstop.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

LINT_FILENAME = "summary_lint.json"

# ── Format invariant patterns (locked at CLAUDE.md `### 格式锁定` 4+1 项) ──

# Invariant 1: timestamps are EXACTLY [HH:MM:SS] = 8 chars between brackets
# (each part 2 digits). Detect any [...] that LOOKS like a timestamp (digits
# + colons) but does NOT match the strict 8-char form.
_VALID_TIMESTAMP_RE = re.compile(r"^\[(\d{2}):(\d{2}):(\d{2})\]$")
_LOOSE_TIMESTAMP_RE = re.compile(r"\[(\d{1,2}(?::\d{1,2}){1,2})\]")

# Invariant 2: every fenced code block must declare a language. A bare ```
# (whitespace-only after) at the start of an opening fence is a violation.
_CODE_FENCE_RE = re.compile(r"^```(\S*)\s*$")

# Invariant 3: relative `frames/` paths only. Disallow http/https, absolute
# paths starting with / or DRIVE: (Windows), or `..\frames`.
_FRAME_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_VALID_FRAME_PATH_RE = re.compile(r"^frames/[A-Za-z0-9_\-./]+\.(jpg|jpeg|png|webp)$")

# Invariant 4: 第二人称 imperative — forbid `我们 ... <action>` and
# `<noun> 被 <action>` where action ∈ {打开, 创建, 配置, 运行, 执行, 导入, 启动}.
_FORBIDDEN_FIRST_PERSON_RE = re.compile(
    r"(我们|让我们)[^。\n]{0,12}?(打开|创建|配置|运行|执行|导入|启动)"
)
_FORBIDDEN_PASSIVE_RE = re.compile(
    r"\S{1,12}\s*被\s*(打开|创建|配置|运行|执行|导入|启动)"
)

# Invariant 5: every load-bearing claim line in the body must end with a
# trace token. Trace token format:
#   [seg_NNNN_NNNNNN.jpg @ HH:MM:SS]  OR  [para_NNNN @ HH:MM:SS]
_TRACE_TOKEN_RE = re.compile(
    r"\[(?:seg_\d{4}_\d{6}\.jpg|para_\d{4})\s*@\s*\d{2}:\d{2}:\d{2}\]"
)
# A line is "load-bearing" if it contains at least one of:
#   - a fenced inline span `code`
#   - a numeric value (with or without unit suffix px/s/fps/%/x)
#   - an `fps=X` or `fps X` parameter
#   - a `frames/` path reference
#   - a file extension (.json/.md/.py/.sh/.yml/.yaml)
_LOAD_BEARING_HINT_RE = re.compile(
    r"(?:`[^`]+`"
    r"|\d+(?:\.\d+)?(?:px|s|fps|%|x)?"
    r"|fps\s*=\s*\d"
    r"|\bfps\b"
    r"|frames/"
    r"|\.(json|md|py|sh|yml|yaml)\b"
    r")"
)

# Sections in which trace tokens are FORBIDDEN (P-02 citation pollution rules,
# CLAUDE.md `## v1.1 自适应教学文档增强 (Phase 08)` → CORR-02 引用资格规则
# → FORBIDDEN list). Mapping: H2 heading substring → canonical section label.
_FORBIDDEN_CITATION_SECTIONS = (
    ("5 分钟速读版", "TL;DR"),
    ("读这篇前你需要知道", "你需要知道什么"),
    ("你不需要知道什么", "你不需要知道什么"),
    ("章节小结", "transition"),
    ("总评", "transition"),
)

# Inline term + parenthetical definition pattern (e.g. "LoRA (Low-Rank Adaptation)")
_GLOSSARY_INLINE_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9_-]{1,30})\s*\(([^)]{1,80})\)"
)
# Glossary H2 anchor with parenthetical definition
_GLOSSARY_H2_RE = re.compile(
    r"^##\s+([A-Z][A-Za-z0-9_-]{1,30})\s*\(([^)]{1,80})\)"
)

# WR-04 (Phase 09 review): H2 heading detector for section classification.
# Use regex `^##\s+(.+)$` instead of literal `startswith("## ")` so headings
# with tabs / multiple spaces / non-breaking-space variants still match.
# CommonMark requires at least one whitespace between `##` and the heading
# text, so `\s+` is the safer default (rejects `##速读版` zero-space form
# per spec; if that surfaces in real Claude output, switch to `\s*` later).
_H2_HEADING_RE = re.compile(r"^##\s+(.+)$")


def _now_iso() -> str:
    """ISO-8601 UTC timestamp ending with `Z` (matches schema contract)."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _classify_section(line: str, current_section: str | None) -> str | None:
    """Return the section label this line belongs to.

    H2 heading lines transition to a new section; non-heading lines inherit
    the current section. Returns None until the first H2 is seen (preamble
    counts as `body` for citation_eligibility purposes — actual TL;DR /
    prelude blocks always live under their dedicated H2).
    """
    m = _H2_HEADING_RE.match(line)
    if m:
        heading = m.group(1).strip()
        for substr, label in _FORBIDDEN_CITATION_SECTIONS:
            if substr in heading:
                return label
        return "body"
    return current_section


def _check_timestamp_format(lines: list[str]) -> list[dict]:
    """Invariant 1: any `[N:NN]` / `[NN:N]` / `[1:23:45]` etc is a violation."""
    violations: list[dict] = []
    for i, line in enumerate(lines, start=1):
        for m in _LOOSE_TIMESTAMP_RE.finditer(line):
            full = f"[{m.group(1)}]"
            if not _VALID_TIMESTAMP_RE.match(full):
                violations.append({
                    "line": i,
                    "snippet": line.strip()[:120],
                    "found": full,
                })
    return violations


def _check_code_fence_language(lines: list[str]) -> list[dict]:
    """Invariant 2: every ``` opening fence must have a lang token."""
    violations: list[dict] = []
    in_fence = False
    for i, line in enumerate(lines, start=1):
        m = _CODE_FENCE_RE.match(line)
        if m:
            if not in_fence:
                lang = m.group(1)
                if not lang:
                    violations.append({
                        "line": i,
                        "snippet": line.strip()[:120],
                    })
            in_fence = not in_fence
    return violations


def _check_relative_frame_paths(lines: list[str]) -> list[dict]:
    """Invariant 3: image src must be `frames/...{jpg|jpeg|png|webp}`."""
    violations: list[dict] = []
    for i, line in enumerate(lines, start=1):
        for m in _FRAME_LINK_RE.finditer(line):
            src = m.group(1).strip()
            if not _VALID_FRAME_PATH_RE.match(src):
                violations.append({
                    "line": i,
                    "snippet": line.strip()[:120],
                    "found": src,
                })
    return violations


def _check_second_person_imperative(lines: list[str]) -> list[dict]:
    """Invariant 4: forbid 我们/passive constructions for the action verb set."""
    violations: list[dict] = []
    for i, line in enumerate(lines, start=1):
        if (_FORBIDDEN_FIRST_PERSON_RE.search(line)
                or _FORBIDDEN_PASSIVE_RE.search(line)):
            violations.append({
                "line": i,
                "snippet": line.strip()[:120],
            })
    return violations


# Image-only lines (`![](...)` with optional surrounding whitespace) are
# visual anchors, NOT prose claims — exclude from load-bearing scan.
_IMAGE_ONLY_LINE_RE = re.compile(r"^\s*!\[[^\]]*\]\([^)]+\)\s*$")
# Code-fence opening / closing lines — exclude from load-bearing scan along
# with everything between them (handled via in_fence state in callers).
_FENCE_LINE_RE = re.compile(r"^```")


def _is_load_bearing(line: str) -> bool:
    if _IMAGE_ONLY_LINE_RE.match(line):
        return False
    return bool(_LOAD_BEARING_HINT_RE.search(line))


def _has_trace_token(line: str) -> bool:
    return bool(_TRACE_TOKEN_RE.search(line))


def _build_in_fence_mask(lines: list[str]) -> list[bool]:
    """Return parallel-indexed list[bool]; True iff line is inside a fenced
    block (including the fence delimiter lines themselves).
    """
    mask: list[bool] = []
    in_fence = False
    for line in lines:
        is_delim = bool(_FENCE_LINE_RE.match(line))
        if is_delim:
            mask.append(True)  # the delimiter itself counts as inside-fence
            in_fence = not in_fence
        else:
            mask.append(in_fence)
    return mask


def _check_trace_after_claim(
    lines: list[str], section_map: list[str | None],
) -> list[dict]:
    """Invariant 5: load-bearing claim lines in `body` must end with trace token.

    Lines inside fenced code blocks and pure image-embed lines are excluded
    (they are not prose claims).
    """
    violations: list[dict] = []
    in_fence_mask = _build_in_fence_mask(lines)
    for i, line in enumerate(lines, start=1):
        section = section_map[i - 1]
        if section != "body":
            continue
        if in_fence_mask[i - 1]:
            continue
        if _is_load_bearing(line) and not _has_trace_token(line):
            violations.append({
                "line": i,
                "snippet": line.strip()[:120],
            })
    return violations


def _compute_citation_stats(
    lines: list[str], section_map: list[str | None],
) -> dict:
    """Aggregate claim counts + trace density + uncertainty markers."""
    claims_total = 0
    claims_with_trace = 0
    claims_without_trace: list[dict] = []
    uncertainty = 0
    in_fence_mask = _build_in_fence_mask(lines)
    for i, line in enumerate(lines, start=1):
        section = section_map[i - 1]
        if (section == "body"
                and not in_fence_mask[i - 1]
                and _is_load_bearing(line)):
            claims_total += 1
            if _has_trace_token(line):
                claims_with_trace += 1
            else:
                claims_without_trace.append({
                    "line": i,
                    "snippet": line.strip()[:120],
                })
        uncertainty += line.count("[?]")
    density = (claims_with_trace / claims_total) if claims_total else 0.0
    return {
        "claims_total": claims_total,
        "claims_with_trace": claims_with_trace,
        "claims_without_trace": claims_without_trace,
        "trace_density": round(density, 3),
        "uncertainty_markers": uncertainty,
    }


def _check_citation_eligibility(
    lines: list[str], section_map: list[str | None],
) -> list[dict]:
    """P-02 citation pollution: trace tokens FORBIDDEN in TL;DR / prelude / transitions."""
    violations: list[dict] = []
    forbidden_sections = {
        "TL;DR",
        "你需要知道什么",
        "你不需要知道什么",
        "transition",
    }
    for i, line in enumerate(lines, start=1):
        section = section_map[i - 1]
        if section in forbidden_sections and _has_trace_token(line):
            violations.append({
                "line": i,
                "section": section,
                "reason": f"FORBIDDEN — {section} section contains trace token",
                "snippet": line.strip()[:120],
            })
    return violations


def _check_glossary_consistency(
    lines: list[str], glossary_path,
) -> list[dict]:
    """Drift: inline `Term (def)` in body vs `## Term (def)` in glossary file."""
    if glossary_path is None:
        return []
    gp = Path(glossary_path)
    if not gp.exists():
        return []

    glossary_defs: dict[str, str] = {}
    for gline in gp.read_text(encoding="utf-8").splitlines():
        m = _GLOSSARY_H2_RE.match(gline)
        if m:
            term = m.group(1)
            definition = m.group(2).strip()
            # First-seen-wins (matches agent/glossary.py contract)
            glossary_defs.setdefault(term, definition)

    drifts: list[dict] = []
    seen_terms: set[str] = set()
    for line in lines:
        for m in _GLOSSARY_INLINE_RE.finditer(line):
            term = m.group(1)
            inline_def = m.group(2).strip()
            if term in seen_terms:
                continue
            if term in glossary_defs and inline_def != glossary_defs[term]:
                drifts.append({
                    "term": term,
                    "summary_definition": inline_def,
                    "glossary_definition": glossary_defs[term],
                    "drift_detected": True,
                })
                seen_terms.add(term)
    return drifts


def lint_summary(summary_path, glossary_path=None) -> dict:
    """Mechanical lint of the slug-level summary artifact.

    Args:
        summary_path: path to the input artifact (typically
            `output/<slug>/summary.md` but any file path works — this is a
            general-purpose mechanical checker).
        glossary_path: optional path to a glossary file (typically
            `output/_glossary.md`). When None or non-existent, the
            `glossary_inconsistencies` field gracefully returns [].

    Returns:
        Schema-locked dict with keys: version, schema_version, summary_path,
        checked_at, format_invariants (5 sub-dicts), citation_stats,
        citation_eligibility_violations, glossary_inconsistencies.

    Read-only: this function NEVER mutates the input artifact and NEVER
    writes to disk on its own — the caller (cmd_summary_lint in agent/tools.py)
    handles the sibling sidecar write.
    """
    sp = Path(summary_path)
    text = sp.read_text(encoding="utf-8") if sp.exists() else ""
    # WR-02 (Phase 09 review): drop the `or [""]` defensive default — it
    # creates a phantom empty line for 0-byte files. All `_check_*` helpers
    # iterate `lines` and return [] cleanly when given []; the citation
    # eligibility / trace-after-claim checks handle the empty-section case
    # via in_fence_mask / section_map (both empty when lines == []).
    lines = text.splitlines()

    # Build section map (one entry per line, parallel index)
    section_map: list[str | None] = []
    current: str | None = None
    for line in lines:
        current = _classify_section(line, current)
        section_map.append(current)

    return {
        "version": 1,
        "schema_version": 1,
        "summary_path": str(sp),
        "checked_at": _now_iso(),
        "format_invariants": {
            "timestamp_format": {
                "violations": _check_timestamp_format(lines),
            },
            "code_fence_language": {
                "violations": _check_code_fence_language(lines),
            },
            "relative_frame_paths": {
                "violations": _check_relative_frame_paths(lines),
            },
            "second_person_imperative": {
                "violations": _check_second_person_imperative(lines),
            },
            "trace_after_claim": {
                "violations": _check_trace_after_claim(lines, section_map),
            },
        },
        "citation_stats": _compute_citation_stats(lines, section_map),
        "citation_eligibility_violations": _check_citation_eligibility(
            lines, section_map,
        ),
        "glossary_inconsistencies": _check_glossary_consistency(
            lines, glossary_path,
        ),
    }
