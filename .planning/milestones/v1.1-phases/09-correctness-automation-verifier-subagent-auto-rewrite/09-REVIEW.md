---
phase: 09-correctness-automation-verifier-subagent-auto-rewrite
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - agent/_v11.py
  - agent/summary_lint.py
  - agent/tools.py
  - agent/verifier_events.py
  - tests/test_k5_emitters.py
  - tests/test_summary_lint.py
  - tests/test_v11_marker.py
  - tests/test_verifier_events.py
findings:
  critical: 0
  warning: 4
  info: 6
  total: 10
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-05-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Phase 09 ships two new modules (`agent/summary_lint.py` ~415 LOC mechanical
checker; `agent/verifier_events.py` ~196 LOC verifier event helpers + UNRESOLVED
template) plus the `cmd_summary_lint` CLI handler in `agent/tools.py`. Code
quality is high overall: K5 boundary is properly enforced (read-only on
decision artifacts; sibling-only writes via `write_json_atomic`); UTF-8 CJK
round-trip is consistently handled; `agent/_v11.py` allowlist has been
correctly extended 13 → 15 with the two new flags; the test suite covers all
documented contracts (15 tests for summary_lint, 6 for verifier_events, 10 for
v11 marker, 11 for K5 boundary).

The findings below are not blocking, but several deserve attention before
hand-off to Phase 7.5 runtime testing:

- **W-01** silently breaks the D-29 invariant guard: `cmd_summary_lint` does
  not gate on `is_v11_enabled(slug, "summary_lint")` even though the plan
  spec explicitly names this as a Phase 09 gate.
- **W-02 / W-03** identify two functional defects in `agent/summary_lint.py`
  (preamble claims escape detection; trailing-newline files generate a phantom
  empty line) that will produce wrong counts on real summaries.
- **W-04** flags an inconsistency in citation eligibility section labeling
  that breaks H2 heading parsing for headings without a trailing space.

## Warnings

### WR-01: cmd_summary_lint missing is_v11_enabled gate (D-29 invariant risk)

**File:** `agent/tools.py:1527-1573`
**Issue:** Per the phase context (`Phase 09 prompts gate on
is_v11_enabled(slug, "verifier_phase_75")`) and the D-29 byte-equal contract,
all v1.1 code paths must be gated on the per-slug `.v11_features.json`
marker so archives without the marker silently take the v1.0 path. The
`summary_lint` flag was added to `V11_FEATURES` (`agent/_v11.py:53`) but
`cmd_summary_lint` itself never calls `is_v11_enabled(slug_dir, "summary_lint")`.
Today the CLI is opt-in by virtue of being a separate sub-command (no v1.0
caller invokes it), so D-29 archive byte-equality is not actually broken
**right now**. But the plan explicitly named `summary_lint` as a v1.1 flag,
which implies callers (e.g., `/summarize-video` Phase 7) will eventually
auto-invoke it; without the gate, that auto-invocation would write a new
`summary_lint.json` sidecar into archive directories that do not have the
marker, breaking byte-equality.

**Fix:** Either (a) add the explicit gate for symmetry with the rest of v1.1
(matches `cmd_transcribe_lint` pattern from Phase 07):

```python
def cmd_summary_lint(args):
    from agent.summary_lint import lint_summary, LINT_FILENAME
    from agent._v11 import is_v11_enabled

    summary_path = Path(args.summary_path)
    _validate_out_path(summary_path)
    if not summary_path.exists():
        raise FileNotFoundError(f"input not found: {summary_path}")
    slug_dir = summary_path.parent
    slug = slug_dir.name
    if not is_v11_enabled(slug_dir, "summary_lint"):
        _log(slug, "summary_lint",
             "skip: .v11_features.json missing or summary_lint not enabled")
        return
    # ...rest unchanged
```

or (b) add a code comment + ADR note explicitly stating "this CLI is
self-gated by being an opt-in sub-command; auto-invokers MUST add their
own marker check." Option (a) is preferred — it matches the pattern in
`cmd_transcribe_lint` and removes the risk of a future caller accidentally
breaking D-29.

### WR-02: Empty / no-trailing-newline files inflate line count by 1

**File:** `agent/summary_lint.py:377`
**Issue:** `lines = text.splitlines() or [""]` provides a defensive default
for empty input, but the construction is wrong: when `text == ""`,
`splitlines()` returns `[]`, so the `or [""]` kicks in and produces
`[""]` (one empty line). Test 13 (`test_13_empty_summary_no_crash`) covers
this case and passes because all violation checks correctly handle an empty
string. However, the same `lines or [""]` will NOT add an extra entry for
files with content (since `splitlines()` returns a non-empty list). The risk
is more subtle: when a summary file is edited in an IDE that strips
trailing newlines vs one that keeps them, line numbers reported in
violations will differ between the two. Since downstream consumers (verifier
subagent, UNRESOLVED.md template) use `line` as the location anchor, this
inconsistency could cause a fix to land on the wrong line in a later
revision of the file.

**Fix:** Drop the `or [""]` (it's unreachable in any meaningful path) and
let empty files yield empty `lines = []`:

```python
text = sp.read_text(encoding="utf-8") if sp.exists() else ""
lines = text.splitlines()
```

Then update Test 13 to verify schema fields are populated correctly even
with `lines = []`. All current `_check_*` helpers iterate `lines` and
return `[]` cleanly when given an empty list — no other change required.

### WR-03: Preamble (text before first H2) silently skipped from claim checks

**File:** `agent/summary_lint.py:125-139, 248-249, 270-274`
**Issue:** `_classify_section` returns `None` for all lines until the first
`## ` heading is encountered. Both `_check_trace_after_claim` (line 248-249:
`if section != "body": continue`) and `_compute_citation_stats` (line
272-274: `if (section == "body" and ...)`) explicitly skip non-`body`
sections. This means that any load-bearing claim in the document
**preamble** (between H1 and the first H2) is invisible to both invariant
checks AND the citation density stats. The docstring at line 130-131 says
"preamble counts as `body` for citation_eligibility purposes" — but the
implementation does the opposite: preamble is `None`, not `"body"`, so it
is skipped from citation_eligibility too (which is fine since preamble has
no FORBIDDEN section label, but the docstring is misleading).

In practice, summaries that put a "本期视频时长 / 链接 / UP主" header block
between H1 and the first chapter H2 may include load-bearing claims (e.g.,
"时长 12:34" with a trace token requirement) that are silently uncounted.

**Fix:** Either align implementation to docstring (preamble = body), or
document the actual behavior. Option 1 (align to docstring):

```python
def _classify_section(line: str, current_section: str | None) -> str | None:
    if line.startswith("## "):
        heading = line[3:].strip()
        for substr, label in _FORBIDDEN_CITATION_SECTIONS:
            if substr in heading:
                return label
        return "body"
    # Preamble (before first H2) defaults to "body" per docstring contract
    return current_section if current_section is not None else "body"
```

Then add a Test 16 covering "trace_after_claim violation in preamble line".
If the team prefers to keep preamble exempt (current behavior is arguably
correct — preamble is metadata, not a claim section), update the docstring
to: `"Returns None for the preamble; load-bearing claims in the preamble
are NOT checked. To check them, place the metadata under a dedicated H2."`

### WR-04: H2 heading detection requires trailing space — `## TL;DR` with no space won't match

**File:** `agent/summary_lint.py:133`
**Issue:** `if line.startswith("## "):` requires exactly the four-char
prefix `"## "` (hash, hash, space, content). But valid Markdown also
accepts `## TL;DR` with arbitrary inline whitespace and `##TL;DR` (no
space — non-CommonMark but commonly seen). Specifically, the project's
own examples in CLAUDE.md use `## 5 分钟速读版` (with space, OK), but if
a Claude-written summary slips out a `##速读版` (no space — Chinese input
methods sometimes elide the half-width space after `##`), the section
classifier returns `current_section` unchanged and the FORBIDDEN
citation check silently passes that section through. The same applies to
H1 (which is irrelevant here) but H2 is the critical case for this module.

**Fix:** Use a regex match instead of literal startswith:

```python
_H2_HEADING_RE = re.compile(r"^##\s+(.+)$")

def _classify_section(line: str, current_section: str | None) -> str | None:
    m = _H2_HEADING_RE.match(line)
    if m:
        heading = m.group(1).strip()
        for substr, label in _FORBIDDEN_CITATION_SECTIONS:
            if substr in heading:
                return label
        return "body"
    return current_section
```

Note: this still requires at least one space (`\s+`) between `##` and the
heading text — `##速读版` will not match. To be even more permissive, use
`r"^##\s*(.+)$"` (zero-or-more whitespace). Pick whichever matches the
Markdown dialect Claude actually emits; the CommonMark spec requires at
least one space, so `\s+` is the safer default.

## Info

### IN-01: Two parallel `_now_iso()` implementations with subtly different output

**File:** `agent/summary_lint.py:116-122` vs `agent/io.py:290-292`
**Issue:** `agent.io.now_iso()` returns
`datetime.now(timezone.utc).isoformat()`, which produces
`2026-05-03T10:30:00+00:00` (with offset). `agent.summary_lint._now_iso()`
strips the offset and appends `Z`:
`2026-05-03T10:30:00Z`. Test 14
(`test_14_schema_version_and_checked_at`) asserts
`result["checked_at"].endswith("Z")`. Both forms are valid ISO-8601 but
mixing them across the codebase makes timestamps non-comparable as strings.
The verifier_events module correctly uses
`time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())` (line 193) — also
`Z`-suffixed, so it agrees with summary_lint. But events emitted via
`agent.state.append_event` use `agent.io.now_iso()` (`+00:00` form).

**Fix:** Make `agent/io.now_iso()` the single source of truth for project-wide
ISO timestamps and add a `Z`-suffix variant if downstream callers want it:

```python
# agent/io.py
def now_iso() -> str:
    """ISO-8601 UTC with `Z` suffix (single project-wide format)."""
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
```

Then `agent/summary_lint.py` and `agent/verifier_events.py` both delegate:

```python
from agent.io import now_iso as _now_iso
```

This is mostly cosmetic, but it eliminates a class of "why are my timestamps
not sorting correctly" bugs.

### IN-02: `summary.md.pre-review` backup write logic not implemented anywhere

**File:** `agent/verifier_events.py:1-10` (docstring), `36`
(`PRE_REVIEW_BACKUP_SUFFIX`)
**Issue:** The module docstring (lines 5-9) lists
`output/<slug>/summary.md.pre-review` as a write target, and
`PRE_REVIEW_BACKUP_SUFFIX = ".pre-review"` is exported as a constant. But
no helper function in this module actually creates the backup. The phase
context notes that this is one of the "2 known stubs flagged human_needed"
(verifier subagent live-runtime testing), so the absence of a helper is
intentional — Claude in /summarize-video Phase 7.5 will do
`Path("output/<slug>/summary.md").rename(...)` manually before triggering
rewrite. Recommend adding a tiny helper to centralize the suffix and
ensure atomic semantics rather than letting Claude inline the rename.

**Fix:** Add a helper that does the rename atomically and emits a state
event:

```python
def make_pre_review_backup(summary_path) -> Path:
    """Atomic rename: <summary_path> -> <summary_path>.pre-review.

    Returns the backup path. Idempotent if backup already exists (no-op).
    Pure file move; never reads the summary content. K5: read-only on the
    decision artifact (the rename is structural, not content-mutating).
    """
    src = Path(summary_path)
    dst = src.with_suffix(src.suffix + PRE_REVIEW_BACKUP_SUFFIX)
    if not dst.exists():
        os.replace(src, dst)
    return dst
```

Note: a rename DOES count as mutating the decision artifact (it disappears
from its original path). The phase plan says K5 is preserved because the
content is preserved at a sibling path — that's defensible but worth
documenting in the helper docstring so reviewers don't trip on it.

### IN-03: build_unresolved_md uses time.strftime UTC but no timezone safety check

**File:** `agent/verifier_events.py:193`
**Issue:** `time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())` correctly
produces UTC, but if a future maintainer accidentally uses
`time.localtime()` or `time.strftime("%Z")` it could leak a wall-clock
local time with a `Z` suffix, which is a subtle correctness bug. Consider
delegating to `agent.io.now_iso()` (after IN-01 normalization) so there's
one place to audit.

**Fix:** After IN-01:

```python
from agent.io import now_iso
# ...
parts.append(f"*生成时间：{now_iso()}*")
```

### IN-04: `_FORBIDDEN_CITATION_SECTIONS` mapping uses substring match — false-positive risk

**File:** `agent/summary_lint.py:98-104, 135-137`
**Issue:** Section classification uses substring match:
`if substr in heading: return label`. This means a heading like
`## 总评章节小结` would map to `transition` (because both `章节小结` and
`总评` are substrings). For most realistic headings this is fine, but it's
fragile. Also, the substring `读这篇前你需要知道` and `你不需要知道什么`
overlap on the substring `不需要知道` — a heading like
`## 你需要知道什么 + 你不需要知道什么` (one combined H2) will return
`你需要知道什么` because it appears first in the tuple. Acceptable but
worth a short test that explicitly covers heading-collision scenarios.

**Fix:** Add a defensive test in `tests/test_summary_lint.py`:

```python
def test_16_section_classification_first_match_wins(self):
    body = (
        "## 你不需要知道什么\n"  # second in tuple
        "\n"
        "本段说参数 fps=0.4 [seg_0001_000005.jpg @ 00:01:23]。\n"
    )
    p = self._write_summary(body)
    result = lint_summary(p)
    violations = result["citation_eligibility_violations"]
    self.assertEqual(violations[0]["section"], "你不需要知道什么")
```

(Already implicitly covered by Tests 8-9; this just makes the substring
ordering explicit.)

### IN-05: cmd_summary_lint default glossary_path resolution is silent

**File:** `agent/tools.py:1544-1547`
**Issue:** When `--glossary-path` is omitted, the handler computes
`slug_dir.parent / "_glossary.md"` and passes it iff it exists. This is
correct behavior but provides no feedback to the user — if a user expects
glossary checking and the file is missing, they get
`glossary_inconsistencies: []` silently. A one-line `_log` would help
debugging:

```python
glossary_path = (
    Path(args.glossary_path) if args.glossary_path
    else slug_dir.parent / "_glossary.md"
)
glossary_used = glossary_path if glossary_path.exists() else None
if args.glossary_path and not glossary_path.exists():
    _log(slug, "summary_lint",
         f"WARNING: --glossary-path {glossary_path} not found; skipping drift check")
result = lint_summary(summary_path, glossary_path=glossary_used)
```

The implicit-default case (no flag, default file missing) intentionally
stays silent — this is consistent with the rest of the project's "graceful
degrade" pattern.

### IN-06: Concurrent state.jsonl emission relies on append-mode atomicity (POSIX) — Windows caveat

**File:** `agent/state.py:85-96`, used by all three Phase 09 emitters
**Issue:** `append_event` uses standard Python `open(log_path, "a", ...)`
+ single `f.write(line)`. On POSIX, writes < PIPE_BUF (typically 4 KB)
are atomic for `O_APPEND`. On Windows, append-mode writes are NOT
guaranteed atomic across processes — two processes appending
simultaneously to the same `state.jsonl` may interleave bytes. Phase 09
introduces a third concurrent producer (lint + verifier + rewrite_cycle
events from a single Claude session, plus any background reader), and
Phase 6 PARA-04 already documented multi-terminal concurrency. The risk
is low (single-line writes < 4 KB; single Claude session is sequential)
but documented behavior would help future debugging.

**Fix:** Either (a) document the assumption explicitly in
`agent/state.py:append_event` docstring, or (b) for high-concurrency
correctness, wrap with `agent/_lock.py` per-slug `.resume.lock` (already
exists for Phase 6). Option (a) is sufficient for v1.1 since events are
diagnostic-only and a single-line corrupt event is detected by
`read_events` (which marks the file `corrupt` and returns events parsed
before the bad line).

```python
def append_event(...) -> None:
    """...
    Concurrency: relies on OS-level append-mode atomicity. Safe on POSIX for
    writes < PIPE_BUF (~4 KB). On Windows, simultaneous writes from multiple
    processes may interleave; risk is mitigated by the per-slug
    .resume.lock (Phase 6 PARA-04) which serializes long-running stages.
    Best-effort: a corrupt line is detected by read_events and marked.
    """
```

---

_Reviewed: 2026-05-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
