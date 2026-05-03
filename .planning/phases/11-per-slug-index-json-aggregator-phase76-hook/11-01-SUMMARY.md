---
phase: 11-per-slug-index-json-aggregator-phase76-hook
plan: 01
subsystem: knowledge-base
tags: [v1.2, knowledge-base, index, K5, FileLock, atomic-write, CLI, agent-tools]

# Dependency graph
requires:
  - phase: 10-topic-taxonomy-governance-bootstrap-cli
    provides: agent.topics.read_topics + agent.topics.append_pending stable contracts; output/_topics.md Approved/Pending taxonomy
  - phase: 06-multi-terminal-parallel
    provides: agent/_lock.FileLock cross-platform advisory lock with stale-PID handover
  - phase: 02-cache-decision
    provides: atomic write via tempfile + os.fsync + os.replace pattern
provides:
  - agent/index.py module (5 public functions + IndexValidationError + module constants)
  - validate_per_slug_index — 8-field schema validator with optional whitelist enforcement
  - write_per_slug_index — atomic per-slug write + immediate aggregator rebuild inside single FileLock window
  - rebuild_aggregator — manual rebuild from all per-slug sidecars with stale detection + skip-on-malformed
  - read_per_slug_index / read_aggregator — corrupt-tolerant readers (None / {} on failure)
  - glossary_h2_anchors — vacuous-empty-tolerant H2 anchor extraction from cross-slug glossary
  - python -m agent.tools index write CLI (Phase 7.6 hook target — read --from-stdin JSON)
  - python -m agent.tools index rebuild CLI (manual aggregator rebuild)
  - 3 new K5 boundary tests (count 17 → 20)
  - tests/_tmp_index/ ASCII-safe per-test tmpdir root (Phase 10 D-19 lesson)
affects:
  - 11-02 (CLAUDE.md /summarize-video Phase 7.6 hook insertion — calls `index write --from-stdin`)
  - 12-knowledge-base-backfill-prompt (Phase 12 backfill reuses agent.index.write_per_slug_index with --force)

# Tech tracking
tech-stack:
  added: []  # Zero new third-party deps; pure stdlib + agent stack
  patterns:
    - "agent/index.py mirrors agent/topics.py shape ~75% (D-08.1..5)"
    - "FileLock(output/.index.lock) covers per-slug write + aggregator rebuild in single window (Pattern 2 invariant — readers always see consistent state)"
    - "Lexicographic dict ordering for output/.index.json reproducibility (Q-E lock)"
    - "Slug-prefix log line routed to STDERR for structured-JSON CLI commands (CLAUDE.md PARA-04 deviation Rule 1 fix)"
    - "Path-traversal hardening on --slug arg (defense-in-depth per RESEARCH §Security)"

key-files:
  created:
    - agent/index.py
    - tests/test_index.py
    - tests/_tmp_index/.gitkeep
    - .planning/phases/11-per-slug-index-json-aggregator-phase76-hook/11-01-SUMMARY.md
  modified:
    - agent/tools.py
    - tests/test_k5_emitters.py

key-decisions:
  - "Slug-prefix log line goes to STDERR (not stdout) for cmd_index_write so --json output stays byte-equal-parseable per D-05.5; CLAUDE.md PARA-04 design intent: structured-JSON output cmds (download/ingest/doctor) do not add slug prefix on stdout. Routing the prefix to stderr preserves both the multi-terminal grep affordance AND the JSON contract."
  - "Lexicographic dict ordering for output/.index.json (alphabetical by slug name) — only deterministic choice for reproducibility (Q-E)."
  - "validate_per_slug_index rejects bool for duration_s and chapters[i].start (defensive — bool is int subclass in Python)."
  - "Pending-topic append happens BEFORE the .index.lock window so concurrent index writes do not block on the (separate) .topics.lock."
  - "FileNotFoundError on _topics.md absent during pending-append is logged + skipped silently (caller can bootstrap taxonomy later); validate_per_slug_index already passed the whitelist enforcement step."

patterns-established:
  - "Multi-line FileLock window: lock acquires at write_per_slug_index entry, covers per-slug atomic write + aggregator rebuild call, releases after both. Readers (read_per_slug_index, read_aggregator) are lock-free per D-09.4."
  - "Subprocess-based CLI edge tests (TestCLIWriteEdges) using sys.executable + capture_output + ASCII-safe cwd mirror tests/test_topics.py pattern."
  - "K5 boundary tests use both `_check_module_file` (file content grep) AND `inspect.getsource()` (handler source) for double coverage of D-29 5-core literals + write-pattern regex."

requirements-completed: [KB-01, KB-03, KB-04, KB-05]

# Metrics
duration: ~25 min
completed: 2026-05-04
---

# Phase 11 Plan 01: Per-Slug Index Sidecar + Top-Level Aggregator Summary

**v1.2 knowledge-base index layer shipped: `agent/index.py` 5-function module + `index write` / `index rebuild` nested CLI + 35 behavior tests + 3 K5 boundary tests; aggregator rebuilds atomically inside the same FileLock window as per-slug writes for consistent reader state, lexicographic ordering, vacuous-empty glossary tolerance, idempotent skip on byte-equal stdin.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-04 (worktree session)
- **Completed:** 2026-05-04
- **Tasks:** 2
- **Files created:** 4 (agent/index.py, tests/test_index.py, tests/_tmp_index/.gitkeep, this summary)
- **Files modified:** 2 (agent/tools.py, tests/test_k5_emitters.py)
- **Test count:** 224 (Phase 10 baseline) → 269 (+34 test_index + 8 CLI edges + 3 K5)
- **K5 boundary count:** 17 → 20

## Accomplishments

- `agent/index.py` module shipped with 5 public functions + IndexValidationError + 6 module constants. Source contains zero of the 5 D-29 core literals (verified by `test_K5_module_index_no_summary_writes`).
- 8-field schema validator (D-01.2 lock): `slug` / `title` / `duration_s` / `mode` / `topics[]` / `keywords[]` / `tldr_oneliner` / `chapters[]` with optional whitelist enforcement (`approved_topics=None` skips for rebuild + `--force` paths).
- `write_per_slug_index` atomically writes per-slug index sidecar AND rebuilds top-level aggregator inside a single `FileLock(output/.index.lock)` window — readers always see consistent state (Pattern 2 invariant).
- `rebuild_aggregator` does lexicographic-ordered atomic rebuild with stale detection (per-slug mtime > aggregator mtime → `stale_detected[]`) and skip-on-malformed quarantine (`slugs_skipped[]`).
- `glossary_h2_anchors` helper handles vacuously-empty `_glossary.md` (returns `[]` on missing file per Pitfall 3 — 17 archives + 16 douyin/BV samples lack glossary).
- `python -m agent.tools index write --slug X --from-stdin` Phase 7.6 hook target wired with stdin JSON validation, schema check, slug-mismatch detection, path-traversal hardening, lock-contention error path.
- `python -m agent.tools index rebuild` manual CLI with `--json` flag, plain-text fallback with stderr per-skip lines, exit code 1 if zero valid + non-empty skips (D-04.3).
- 3 new K5 boundary tests inside existing `TestK5BoundaryPhase07` class (count 17 → 20). One module-level + two handler-level. The rebuild handler test asserts both no D-29 literals AND no `write_per_slug_index` import (Q-D simpler-alternative recommendation — rebuild is read-only on per-slug, write-only on top-level).

## Task Commits

1. **Task 1: agent/index.py module + tests/test_index.py + tests/_tmp_index/.gitkeep + 1 K5 module test** — `be95000` (feat)
   - Wave 0 deliverable: agent/index.py (5 public functions + module constants), tests/test_index.py (5 classes / 34 behavior tests covering KB-01/03/04/05), tests/_tmp_index/.gitkeep (ASCII-safe tmpdir root), tests/test_k5_emitters.py +1 K5 module test (`test_K5_module_index_no_summary_writes`).

2. **Task 2: cmd_index_write + cmd_index_rebuild + cmds["index"] subparser + 2 K5 handler tests + TestCLIWriteEdges** — `142f326` (feat)
   - Wave 1 deliverable: 2 nested CLI handlers in agent/tools.py, `index` subparser registration with 6+3 args, `index_cmds` dispatch dict, dispatch chain elif clause, 2 new K5 handler tests (`test_K5_handler_cmd_index_write` + `test_K5_cmd_index_rebuild_read_only_per_slug` with simpler-alternative no-write_per_slug_index assertion), and TestCLIWriteEdges class with 8 subprocess-based edge case tests.

## Files Created/Modified

- `agent/index.py` (NEW, 475 lines) — Phase 11 D-08 module: validate_per_slug_index / read_per_slug_index / write_per_slug_index / rebuild_aggregator / read_aggregator / glossary_h2_anchors / IndexValidationError / module constants.
- `agent/tools.py` (MODIFIED, +154 lines) — Added cmd_index_write + cmd_index_rebuild handlers + nested `index` subparser block + `index_cmds` dispatch dict + dispatch elif clause.
- `tests/test_index.py` (NEW, 575 lines) — 6 test classes / 42 tests covering schema validator + read/write round-trip + aggregator rebuild + glossary H2 anchors + concurrent writes (multiprocessing.spawn) + CLI subprocess edge cases.
- `tests/_tmp_index/.gitkeep` (NEW, empty file) — ASCII-safe per-test tmpdir root marker (Phase 10 D-19 lesson re: Windows zh-CN GBK code-page hazard).
- `tests/test_k5_emitters.py` (MODIFIED, 301 → 365 lines) — Added 3 K5 boundary tests inside existing `TestK5BoundaryPhase07` class.

## Decisions Made

1. **Stderr routing for slug-prefix log on cmd_index_write** (deviation Rule 1). The plan specified `_log(args.slug, "index_write", result["action"])` per Phase 6 PARA-04 invariant, but `_log()` writes to stdout via `print()`. With `--json` flag the JSON output also goes to stdout, breaking machine-parseable JSON contract per D-05.5. CLAUDE.md `### 日志格式 (PARA-04)` already says structured-JSON output cmds (download/ingest/doctor) do NOT add slug prefix on stdout. Resolution: route the slug-prefix log line to stderr via `print(..., file=sys.stderr)` so stdout JSON stays byte-equal AND multi-terminal grep affordance is preserved on stderr. This is documented inline in cmd_index_write source.

2. **Lexicographic aggregator dict ordering** (Q-E lock). CONTEXT D-03 / Claude's Discretion bullet 5 said "Claude 选自然形态；测试不强约束". Per RESEARCH Q-E recommendation, locked lexicographic-by-slug ordering for reproducibility (same input → byte-equal output, diff-friendly, predictable Claude consumption order). Test asserts: write 3 slugs in order BVc/BVa/BVb → `read_aggregator()` keys are `[BVa, BVb, BVc]`.

3. **Bool rejected for numeric fields** (defensive). Python `bool` is a subclass of `int`, so `isinstance(True, int) == True`. validate_per_slug_index explicitly rejects `bool` for `duration_s` and `chapters[i].start` to prevent accidental True/False sneaking through as 1/0 numbers.

4. **Pending-topic append happens BEFORE FileLock(.index.lock) window**. Two reasons: (a) `agent.topics.append_pending` acquires its own `.topics.lock`; nesting two lock acquisitions in the same call risks deadlock if a future code path inverts the order; (b) the schema-validation step that gates the .index.lock acquisition has already passed, so the pending append is "safe to lose" — if the .index.lock acquisition fails afterwards, the pending entry is harmless and idempotent on retry. D-09.5 supports this: `.topics.lock` and `.index.lock` are independent.

5. **FileNotFoundError on `_topics.md` during pending-append is logged + skipped silently**. `validate_per_slug_index` with `approved_topics=None` (force) or empty approved set already passed; the pending-append failure does not invalidate the per-slug write. Caller can bootstrap the taxonomy later via `python -m agent.tools topics bootstrap --from-stdin`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Slug-prefix `_log` line on stdout breaks `--json` parsing**

- **Found during:** Task 2 (cmd_index_write end-to-end smoke test)
- **Issue:** Plan Behavior 10 mandated `_log(args.slug, "index_write", result["action"])` per Phase 6 PARA-04. But `_log()` writes to stdout via `print()`, and the same handler also writes JSON to stdout when `--json` is set. The mixed stdout output broke `json.loads()` in the TestCLIWriteEdges happy-path test.
- **Root cause:** PARA-04 design intent (CLAUDE.md `### 日志格式 (PARA-04)`) explicitly says structured-JSON output cmds (download/ingest/doctor) do NOT add slug prefix on stdout — exactly to avoid this contamination. The plan's Behavior 10 conflicted with PARA-04's structured-output exception.
- **Fix:** Replaced `_log(...)` call with `print(f"[{args.slug}] index_write: {result['action']}", file=sys.stderr)` — preserves the multi-terminal grep affordance (stderr `tail -f` works the same way) AND the D-05.5 stdout JSON byte-equal contract.
- **Files modified:** agent/tools.py (cmd_index_write only; cmd_index_rebuild already had no `_log()` per spec since rebuild is cross-slug)
- **Verification:** End-to-end smoke test passes — stdout is parseable JSON, stderr has the slug-prefix log line. TestCLIWriteEdges.test_happy_path_writes_per_slug_and_aggregator passes after the fix.
- **Committed in:** `142f326` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 bug)
**Impact on plan:** Single line-level fix to preserve both contracts (PARA-04 + D-05.5). No scope creep; the fix is documented inline in cmd_index_write docstring/comment.

## Issues Encountered

- **Worktree initial state mismatch.** The worktree started at commit 08a79f4 (much older snapshot, before milestone v1.0/v1.1/Phase 10 ship) instead of expected base d2a7392. Recovered via `git reset --mixed d2a739276... && git checkout -- . && git clean -fd`. Working tree now matches the expected base; all Phase 10 ship artifacts (agent/topics.py, output/_topics.md, _tmp_topics/.gitkeep) confirmed present before starting Task 1.
- **Missing test scratch dirs.** Several gitignored test scratch dirs (`tests/_tmp_glossary`, `tests/_tmp_v11`, `tests/_tmp_replay`, `tests/_tmp_lock`, `tests/_tmp_queue`, `tests/_tmp_batch`, `tests/_tmp_scenes`, `tests/_tmp_silence`) didn't exist; some tests fail with FileNotFoundError until `mkdir -p` runs. Created them once; they get auto-populated by setUp() afterwards. This is pre-existing, not Phase 11-specific.
- **CRLF warnings on commit.** Git config defaults converted LF → CRLF for new files on Windows. Warning only; commit succeeded.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Plan 11-02 readiness:**
- `python -m agent.tools index write --slug X --from-stdin` CLI is ready to be invoked from CLAUDE.md `/summarize-video` Phase 7.6 hook.
- D-05.5 stdout JSON shape locked byte-equal: `{"action": "written"|"skipped", "slug", "_index_path", "_aggregator_path", "_topics_pending_appended"}`.
- D-04.4 stdout JSON shape locked byte-equal for `index rebuild --json`: `{"action": "rebuilt", "slugs_included", "slugs_skipped", "stale_detected", "_index_path"}`.
- agent.index.write_per_slug_index public API ready for Phase 12 backfill reuse with `force=True` flag.
- D-29 byte-equal automated gate still PASSED (informationally — Plan 11-02 SC#5 owns the formal close gate). agent/index.py + cmd_index_write + cmd_index_rebuild contain zero of the 5 D-29 core artifact literals; tests/test_k5_emitters.py 3 new boundary tests verify this statically.

**Test coverage growth:**
- `python -m unittest discover tests` reports 269 tests (was 224 baseline) — all OK with 2 skipped.
- 3 new K5 boundary tests bring count to 20 (locked baseline for Phase 11).
- TestCLIWriteEdges subprocess-based tests cover Q-G edge cases (missing --from-stdin / empty stdin / malformed JSON / slug mismatch / slug dir not found / happy path / rebuild empty dir / rebuild zero-valid returncode 1).

## D-29 Replay Status

**Pre-plan baseline:** AUTOMATED GATE PASSED (33/0/30 manual + automated baseline; on this worktree branch with limited archives present, archives marked as "missing required files" rather than failing — that's the script's intended behavior for missing slugs).

**Post-plan status:** AUTOMATED GATE PASSED (identical to pre-plan; no changes to 4 core artifacts). Plan 11-01 ships only NEW sidecars (per-slug index.json + top-level .index.json + .index.lock) outside replay scope per D-07.3.

**Plan 11-02 owns the formal close gate** (`python scripts/replay_v10_archives.py` → 33/0/30) per D-07.1. This plan does not touch summary.md / segs.json / paragraphs.json / meta.json on any archive.

## Self-Check: PASSED

- agent/index.py: FOUND
- tests/test_index.py: FOUND (5 + 1 = 6 classes, 42 test_ methods)
- tests/_tmp_index/.gitkeep: FOUND (empty file)
- tests/test_k5_emitters.py: MODIFIED (3 new tests added inside TestK5BoundaryPhase07; total 20 K5 tests)
- agent/tools.py: MODIFIED (cmd_index_write + cmd_index_rebuild handlers + index subparser + index_cmds dispatch)
- Commits: be95000 + 142f326 both verified in `git log --oneline -5`
- K5 invariant: agent/index.py contains 0 of 5 D-29 core literals (verified)
- K5 invariant: cmd_index_write contains 0 of 5 D-29 core literals (verified)
- K5 invariant: cmd_index_rebuild contains 0 of 5 D-29 core literals AND no `write_per_slug_index` import (verified)
- All tests green: 269 tests OK with 2 skipped (was 224 baseline → +45)
- D-29 replay automated gate: PASSED (informational; Plan 11-02 owns formal gate)
- End-to-end smoke test: PASSED (write → JSON parses → aggregator contains slug → idempotent skip on byte-equal stdin → rebuild reports stale=[] / skipped=[] / included=1)

---
*Phase: 11-per-slug-index-json-aggregator-phase76-hook*
*Completed: 2026-05-04*
