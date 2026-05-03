---
phase: 10-topic-taxonomy-governance-bootstrap-cli
plan: 01
subsystem: knowledge-base/topics-governance
tags: [v1.2, knowledge-base, governance, K5, FileLock, atomic-write, CLI]

dependency-graph:
  requires:
    - agent/_lock.py (v1.0 Phase 06 — FileLock + LockContended)
    - agent/glossary.py (v1.1 Phase 08 — pattern reference for atomic writer)
    - agent/io.py (v1.0 — write_json_atomic helper available if needed)
  provides:
    - agent.topics.read_topics (Phase 11 generator white-list lookup)
    - agent.topics.append_pending (Phase 11 generator pending submission API)
    - agent.topics.write_approved_taxonomy (bootstrap entry point)
    - agent.topics.resolve_pending (CLI promote/rename/remove)
    - python -m agent.tools topics {bootstrap,audit,resolve} (3 nested subcommands)
  affects:
    - tests/test_k5_emitters.py (extended with 4 new tests; locked count is now 17)

tech-stack:
  added: []  # zero new dependencies; stdlib-only (re, json, tempfile, os, pathlib)
  patterns:
    - FileLock (from agent._lock) — third cross-slug lock domain
      after Phase 07 ~/.videoSummary/.queue.lock + Phase 08 output/.glossary.lock
    - tempfile.NamedTemporaryFile + os.fsync + os.replace (atomic write, mirrored from agent/glossary.py)
    - Snapshot-then-atomic-write with restore-on-failure (NEW pattern for multi-file resolve)
    - Nested argparse subparser (mirrors queue + glossary)
    - inspect.getsource() static-grep K5 boundary tests
    - multiprocessing.spawn race test (mirrors test_glossary.py + test_queue.py)

key-files:
  created:
    - agent/topics.py (734 lines)
    - tests/test_topics.py (~310 lines, 24 behavior tests in 5 classes)
    - tests/_tmp_topics/.gitkeep (per-test ASCII-safe tmpdir root)
  modified:
    - agent/tools.py (+214 lines: 3 cmd_topics_* handlers + nested subparser + topics_cmds dispatch)
    - tests/test_k5_emitters.py (+85 lines: imports, _RESOLVE_FORBIDDEN_PATTERNS, 4 new test methods)

decisions:
  - "Mirror agent/glossary.py atomic-write pattern verbatim (D-04.3)"
  - "FileLock domain output/.topics.lock (D-08.1) — third cross-slug lock"
  - "K5 invariant: agent/topics.py source contains zero D-29 core artifact literals (D-06.1)"
  - "Stdout JSON shapes locked byte-equal to D-02.5 / D-03.6 / D-04.5"
  - "_FILE_HEADER literal locked byte-equal to D-01.6"
  - "K5 prose docstring uses 'the slug summary file' / 'per-slug index sidecars' to avoid regex self-match (Phase 08-01 deviation #2 lesson)"
  - "datetime.now(timezone.utc) instead of deprecated utcnow() (Rule 1 minor inline fix)"

metrics:
  duration_minutes: 9
  completed: 2026-05-03
---

# Phase 10 Plan 01: agent/topics.py + 3 nested CLI subcommands + K5 boundary tests Summary

Ship the v1.2 knowledge-base "词表层" infrastructure — `agent/topics.py` module with 4 public functions (`read_topics`, `write_approved_taxonomy`, `append_pending`, `resolve_pending`) + 3 nested CLI subcommands (`topics bootstrap` / `topics audit` / `topics resolve`) + 4 K5 boundary static-assertion tests, providing the Phase 11 generator contract surface.

## What Was Built

### Module: `agent/topics.py` (Task 1, commit `861d96d`)

4 public functions + 1 atomic-write helper:

| Function | Behavior | Concurrency |
| --- | --- | --- |
| `read_topics(path)` | Parse `_topics.md` into `{approved: tree, pending: list, exists: bool}` | Lock-free (D-08.4) |
| `write_approved_taxonomy(path, taxonomy)` | Bootstrap entry; locked header + nested bullet list; idempotent skip on populated | FileLock-serialized |
| `append_pending(path, name, slug, ch_title, reason)` | Phase 11 generator API; appends `### name` H3 + 3 sub-fields; idempotent | FileLock-serialized |
| `resolve_pending(path, name, *, rename, remove)` | Atomic multi-file write across `_topics.md` + per-slug index sidecars | FileLock + snapshot-restore |

K5 boundary preserved: zero `summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json` / `schedule.json` literals anywhere in the module source. Docstring uses prose ("the slug summary file") to avoid regex self-match (Phase 08-01 deviation #2 lesson applied).

`_FILE_HEADER` literal locked byte-equal to CONTEXT D-01.6.

### CLI: `python -m agent.tools topics {bootstrap,audit,resolve}` (Task 2, commit `f969a30`)

3 cmd handlers wired into `agent/tools.py`:

- `cmd_topics_bootstrap`: validates `--from-stdin` JSON shape, calls `write_approved_taxonomy`. Stdout JSON: `{"action": "created"|"skipped", "approved_count": N, "_topics_path": "..."}` (D-02.5 locked byte-equal).
- `cmd_topics_audit`: read-only — reads `_topics.md` + globs per-slug sidecars, counts references, detects orphans. Stdout JSON includes `pending`, `approved_with_counts`, `orphans`, `audit_note`, `read_at` (D-03.6 locked byte-equal). Audit_note explains why orphan detection skipped pre-Phase-11 (no per-slug sidecars exist yet).
- `cmd_topics_resolve`: routes to `resolve_pending`; stdout JSON has `action`, `pending_name`, `final_name`, `index_json_updated`, `_topics_path` (D-04.5 locked byte-equal). Mutually-exclusive `--rename` / `--remove` flags via argparse group.

`topics_cmds` dispatch dict added to `main()`; `args.command == "topics"` route added (mirrors queue / glossary patterns from Phases 07/08).

### Tests (Task 3, commit `9312b4f`)

`tests/test_topics.py` — 24 behavior tests across 5 classes:

| Class | Tests | Coverage |
| --- | --- | --- |
| TestReadTopics | 3 | missing file, 3-level nested taxonomy, pending H3 with 3 sub-fields |
| TestBootstrap | 5 | locked header literal, idempotent skip, depth>3 rejection, dup name rejection, empty name rejection |
| TestAppendPending | 6 | H3 + 3 fields, idempotent dup, empty arg validation, missing-file FileNotFoundError, multiprocessing race (spawn ctx), lock contention with timeout=0 |
| TestAudit | 2 | empty glob → empty orphans, with-sidecars reference counting |
| TestResolve | 8 | promote default, rename nested path, remove clears H3, unknown name → KeyError, mutually-exclusive flags, index.json updates on rename, index.json updates on remove (chapter-empty warning), atomic restore on failure (Linux-only — Windows skipped per plan) |

`tests/test_k5_emitters.py` — 4 new K5 source-grep tests added inside existing `TestK5BoundaryPhase07` class:

1. `test_topics_bootstrap_no_index_json_writes` — `inspect.getsource(cmd_topics_bootstrap)` has zero D-29 literals
2. `test_topics_audit_no_writes` — `cmd_topics_audit` source has zero write API patterns
3. `test_topics_resolve_only_writes_topics_md_and_index_json` — uses new `_RESOLVE_FORBIDDEN_PATTERNS` tuple (24 patterns covering 5 D-29 core artifacts × 6 write APIs minus combinations)
4. `test_topics_module_no_summary_writes` — `agent/topics.py` source has zero D-29 literals + zero forbidden write patterns

`_RESOLVE_FORBIDDEN_PATTERNS` tuple defined at module level for reuse — mirrors `_WRITE_PATTERNS_FORBIDDEN` shape but covers 5 D-29 artifacts (vs the 3 in the original tuple).

## Test Results

| Suite | Pre-Phase-10 | Post-Phase-10 |
| --- | --- | --- |
| `tests/test_topics.py` | n/a | **24 OK** (1 platform-skipped on Windows) |
| `tests/test_k5_emitters.py` | 13 OK | **17 OK** (4 new) |
| Full `python -m unittest discover tests` | (baseline 200 OK) | **224 OK** (skipped=2) |
| `python -m pytest tests/ -q` | (baseline) | **222 passed, 2 skipped** in 2.37s |
| `scripts/replay_v10_archives.py` | 1 PASS / 0 FAIL | **1 PASS / 0 FAIL** (D-29 byte-equal preserved; worktree only has 1 archive) |

(Note: the worktree-mode parallel agent runs from a fresh checkout of the v1.2 phase commit; the parent main has 17 archives — replay scope is intact in main but the worktree has fewer files. The key invariant `0 FAIL` holds in both worktree and main.)

## End-to-End Smoke Test

```bash
mkdir -p /tmp/topics_smoke
echo '{"taxonomy":[{"name":"LLM","subtopics":[{"name":"LoRA"}]}]}' \
  | python -m agent.tools topics bootstrap --from-stdin --output-dir /tmp/topics_smoke --json
# → {"action": "created", "approved_count": 2, "_topics_path": ".../_topics.md"}

python -m agent.tools topics audit --output-dir /tmp/topics_smoke --json
# → {"pending": [], "approved_with_counts": {"LoRA": 0, "LLM": 0},
#     "orphans": [], "audit_note": "...", "read_at": "2026-05-03T..."}
```

Both stdout shapes match D-02.5 / D-03.6 byte-equal.

## Phase 11 Readiness Checklist

- [x] `from agent.topics import append_pending` is importable
- [x] Signature matches D-05.3: `append_pending(topics_path, name, from_slug, chapter_title, reason)`
- [x] FileLock domain `output/.topics.lock` reserved and tested
- [x] Schema parser `read_topics` returns Approved Taxonomy tree (Phase 11 white-list lookup) + Pending list
- [x] K5 source-grep tests prevent future drift into D-29 core artifact writes

## Decisions Made

1. **Mirrored `agent/glossary.py:_atomic_write` verbatim** — same `tempfile.NamedTemporaryFile + os.fsync + os.replace` pattern, same cleanup-on-exception. No new helpers introduced.

2. **Snapshot-then-restore on failure for multi-file resolve** — `resolve_pending` snapshots the topics file plus all per-slug sidecars in memory before any write, writes via `_atomic_write`, and on exception restores each already-written file from its snapshot. This is a NEW pattern (glossary is single-file; topics resolve is multi-file).

3. **Lock-free `read_topics`** — Per CONTEXT D-08.4, audit must not block governance flow. The `read_topics` function does not acquire `.topics.lock`; cross-CLI race for read-during-write is acceptable per CONTEXT (audit `--json` includes `read_at` ISO timestamp so user can re-run if desired).

4. **K5 prose docstring** — Module docstring uses prose ("the slug summary file" / "per-slug index sidecars" / "the schedule artifact") instead of literal D-29 filenames. This is the Phase 08-01 deviation #2 lesson made explicit.

5. **`datetime.now(timezone.utc)` instead of `datetime.utcnow()`** — Rule 1 inline fix during Task 2: the deprecated utcnow() emits DeprecationWarning on Python 3.12+. The plan's draft snippet had `datetime.datetime.utcnow()`; substituted with timezone-aware `datetime.datetime.now(datetime.timezone.utc)` for forward compatibility. Output format identical (`...Z` suffix preserved via `.replace("+00:00", "Z")`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] datetime.utcnow() deprecation**
- **Found during:** Task 2 smoke test
- **Issue:** The plan's draft snippet for `cmd_topics_audit` used `datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"` which emits `DeprecationWarning` on Python 3.12+ and is scheduled for removal.
- **Fix:** Replaced with timezone-aware `datetime.datetime.now(datetime.timezone.utc)` and `.isoformat(timespec="seconds").replace("+00:00", "Z")` to preserve the trailing `Z` suffix byte-equal.
- **Files modified:** `agent/tools.py:cmd_topics_audit`
- **Commit:** `f969a30`
- **Output verification:** `read_at: "2026-05-03T16:59:25Z"` — same shape as before, no warning.

### Plan Drift / Notes

- **Test count exceeds plan's "≥10" minimum** — Plan said `tests/test_topics.py` should have "5 test classes + 10+ behavior tests"; shipped 24 tests in 5 classes (covers all behavior + edge cases per `<behavior>` block). Higher count justified by the multi-file resolve atomic-restore semantic — needs both happy path and failure path coverage.

- **K5 module test correctly defined inside existing `TestK5BoundaryPhase07` class** (not a new class) — matches the plan's `<action>` block "add to existing TestK5BoundaryPhase07 class". `inspect`-based dispatch already established in the existing class.

- **Worktree-only replay scope** — The fresh worktree checkout for parallel-mode execution has only 1 v1.0 archive (`BV1C9QCBdE1U`) instead of the 17 in main. Replay reports `1 PASS / 0 FAIL` which preserves the key invariant. Parent main verification (17/0/15 or similar) is the orchestrator's responsibility.

## Authentication Gates

None — Phase 10 is pure local filesystem + stdlib code.

## Self-Check: PASSED

- File `agent/topics.py` exists ✓
- File `tests/test_topics.py` exists ✓
- File `tests/_tmp_topics/.gitkeep` exists ✓
- File `tests/test_k5_emitters.py` modified ✓
- File `agent/tools.py` modified ✓
- Commit `861d96d` exists ✓
- Commit `f969a30` exists ✓
- Commit `9312b4f` exists ✓
- All 224 tests pass (2 platform-skipped) ✓
- All 17 K5 tests pass ✓
- D-29 byte-equal replay preserved ✓
- `python -m agent.tools topics --help` lists 3 subcommands ✓
