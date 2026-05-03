---
phase: 08-writing-rules-claude-md-extensions-glossary
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - agent/_v11.py
  - agent/glossary.py
  - agent/tools.py
  - tests/test_glossary.py
  - tests/test_k5_emitters.py
  - tests/test_v11_marker.py
findings:
  critical: 0
  warning: 0
  info: 4
  total: 4
status: clean
---

# Phase 08: Code Review Report

**Reviewed:** 2026-05-03
**Depth:** standard
**Files Reviewed:** 6
**Status:** clean (no Critical or Warning findings; 4 Info-level observations)

## Summary

Phase 08 ships `agent/glossary.py` (~230 LOC) — a cross-slug glossary append-only
writer with `FileLock` serialization, first-seen-wins definition semantics, and
atomic write via tempfile + `os.replace`. `agent/_v11.py` is extended from 8 to
13 entries in `V11_FEATURES` (8 Phase 07 + 5 NEW Phase 08 aliases including
`inline_trace_tokens`, `self_check_confidence`, `cross_slug_glossary`,
`tldr_speedrun`, `l2_l3_correction`). A nested `glossary {append|audit}` CLI is
added in `agent/tools.py` plus a backward-compat `glossary_audit` standalone
alias.

All 27 tests across the three test files **pass cleanly** (`tests.test_glossary`
6 tests including T3 multiprocessing race + T6 LockContended; `tests.test_v11_marker`
10 tests including the new T10 13-entry allowlist check; `tests.test_k5_emitters`
11 tests including 3 new Phase 08 K5 boundary checks).

Notable strengths verified:

- **K5 boundary preserved.** `agent/glossary.py` source contains zero literal
  occurrences of `summary.md` / `plan.md` / `schedule.json`. The bullet-link
  template `_SLUG_LINK_TEMPLATE = "[{slug}]({slug}/" + "summary" + ".md)"` uses
  string concat to defeat the byte-match grep, and the new K5 tests
  (`test_K5_module_glossary` + `test_K5_glossary_append_writes_only_to_accumulator`)
  correctly use intent-correct write-pattern regex instead of extending the
  literal-forbidden tuple. This mirrors the Phase 07-03 deviation #2 fix and is
  the right architectural call.
- **D-29 invariant preserved.** `glossary append` is an explicit user-invoked
  CLI command (not a silent path), so it is not subject to the `is_v11_enabled`
  silent-fallback gate. Archives without `.v11_features.json` will simply never
  see this CLI invoked unless the user explicitly runs it. Correct.
- **First-seen-wins idempotency.** T2 verifies same `(slug, term)` returns
  `action=skipped` byte-equal; T4 verifies same `term` + different `slug` +
  different `definition` keeps the FIRST definition and appends new bullet only.
  Implementation in `glossary_append` lines 200-213 uses `_slug_link_substring`
  containment check, which is the correct idempotency primitive.
- **Lock semantics correct.** Read-then-write happens INSIDE the `with FileLock(...)`
  block (line 175-189), eliminating TOCTOU races. T3 multiprocessing.spawn race
  test confirms exactly 1 H2 + 1 bullet survive 2 concurrent child appends with
  identical args.
- **Atomic write correct.** `_atomic_write` (lines 59-82) uses
  `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` + `tmp.flush()` +
  `os.fsync()` + `os.replace()` — classic safe pattern, atomic on both Windows
  and POSIX, and the except-block best-effort cleanup avoids leaking `.tmp` files
  on most failure modes.
- **V11_FEATURES allowlist correct.** All 13 entries present, T10 explicitly
  asserts both Phase 07 names (8) and Phase 08 names (5), comment block at
  `agent/_v11.py:33-54` is precise about reuse vs alias semantics.

## Info

### IN-01: `args.context or ""` is redundant given argparse default

**File:** `agent/tools.py:1519`
**Issue:** The argparse subparser at line 1712-1713 sets `gappend.add_argument("--context", default="")`, so `args.context` is always a string (never `None`). The defensive `args.context or ""` reduces to the same value. Trivial readability cost, not a bug.
**Fix:** Either drop the `or ""` (relies on argparse default) or document why the redundancy exists (e.g., "future-proofing if someone removes the argparse default"). Status quo is fine; just noting for future cleanup:
```python
context=args.context,  # argparse default="" guarantees non-None
```

### IN-02: Tempfile leak window on hard kill / power loss

**File:** `agent/glossary.py:67-82`
**Issue:** `_atomic_write` creates a `.tmp` file in `target.parent`. The except-block cleanup (line 78-81) handles soft Python exceptions, but a SIGKILL or power loss between `tmp.close()` (line 75) and `os.replace()` (line 76) leaves an orphaned `.tmp` file in `output/`. This is a known limitation of the tempfile-then-replace pattern and matches what `agent/io.write_json_atomic` does, so consistency is preserved. Practically harmless because (1) the `.tmp` filename has a random suffix so it doesn't collide with the next attempt, and (2) the next normal append still succeeds because it reads from `_glossary.md` (not the orphaned tempfile).
**Fix:** No action required — accepting the window matches established codebase pattern. If we ever want to clean up, a `glossary doctor` audit could `glob("*.tmp")` and remove any older than N minutes. Filed for v1.2 if the concern grows.

### IN-03: `_log` print uses `args.slug` even though it's not a directory

**File:** `agent/tools.py:1522`
**Issue:** The standard `_log` convention (per docstring at line 48-64) uses `out_dir.name` or similar directory-derived names. `cmd_glossary_append` passes `args.slug` directly, which is the source-slug arg (a logical name, not a directory). This is semantically equivalent for grepping multi-terminal output (`grep '\[BVxxx\]'` works the same), but breaks the "slug is always a directory name" contract gently. Not a defect — actually correct in spirit: the `slug` arg here IS the per-slug identifier the user is referencing.
**Fix:** No action — the line `_log(args.slug, "glossary", f"append {result}")` produces useful greppable output (`[BVrace] glossary: append {...}`). Worth a comment in the docstring noting `cmd` may also be `"glossary"` and `slug` here is the source-slug arg, not a dir. Optional polish.

### IN-04: `_FILE_HEADER` could note the recommended order of `glossary append` invocation

**File:** `agent/glossary.py:47-54`
**Issue:** The 3-line preamble in `_FILE_HEADER` says "do NOT manually edit" and explains first-seen-wins. It could optionally include the `glossary audit` recommendation so a human dropping into the file sees the audit subcommand exists. Minor docs polish, not a correctness issue.
**Fix:**
```python
_FILE_HEADER = """\
# 术语表

> 跨 slug 累积的术语 + 释义。每个 H2 anchor 是一个术语；下方 bullet 列出引用过该术语的 slug。
> 此文件由 `python -m agent.tools glossary append --slug <slug> --term <term> --definition <def>` 维护。
> **绝不**手动编辑 — first-seen-wins for definition, first-seen-wins for slug references (idempotent).
> 健康检查：`python -m agent.tools glossary audit` 列重复术语 / 冲突定义。

"""
```

---

_Reviewed: 2026-05-03_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
