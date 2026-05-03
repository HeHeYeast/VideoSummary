---
phase: 07-warm-up-k5-emitters-d-29-foundation
plan: 01
subsystem: infra
tags: [foundation, backward-compat, d-29, opt-in, replay-test, token-budget, k5-boundary]

# Dependency graph
requires:
  - phase: 02-resume-infrastructure-cache-correctness
    provides: agent/io.write_json_atomic + now_iso (atomic JSON write)
  - phase: 05-adaptive-teaching-doc
    provides: agent/asr_v2.PROFILES + paragraphs.json.params.json sidecar shape (D-27)
  - phase: 06-multi-agent-parallel
    provides: agent/_lock.FileLock (referenced as pattern; not used directly here)
provides:
  - "agent/_v11.py — opt-in marker library (.v11_features.json gate for all v1.1 paths)"
  - "scripts/replay_v10_archives.py — D-29 byte-equal regression test (paragraphs.json regen + segs/meta/summary mutation hash check)"
  - "scripts/measure_token_budget.py — per-archive token budget baseline writer (chars/3.5 proxy)"
  - "3 .token_budget.json baselines for Phase 09 2x cap reference"
  - "Locked V11_FEATURES allowlist (8 names, single source of truth Phase 08/09 will extend)"
affects: [07-02, 07-03, 08-*, 09-*]

# Tech tracking
tech-stack:
  added: []  # zero new pip deps; pure stdlib + existing agent.io / agent.asr_v2 reuse
  patterns:
    - "v1.1 opt-in marker pattern (.v11_features.json) — silent v1.0 fallback when missing (D-29)"
    - "Per-slug profile resolution from paragraphs.json.params.json sidecar (cli > func > tutorial fallback)"
    - "scripts/ package for one-shot regression / measurement scripts (NOT CI hooks)"
    - "Read-only K5 audit pattern: scripts that READ decision artifacts for measurement but never WRITE"

key-files:
  created:
    - agent/_v11.py
    - scripts/__init__.py
    - scripts/replay_v10_archives.py
    - scripts/measure_token_budget.py
    - tests/test_v11_marker.py
    - tests/test_replay_v10.py
    - output/BV132wizyEEB/.token_budget.json
    - output/douyin_karpathy_llm_wiki/.token_budget.json
    - output/douyin_claude_code_hooks/.token_budget.json
    - .planning/phases/07-warm-up-k5-emitters-d-29-foundation/07-01-SUMMARY.md
  modified:
    - .gitignore  # add tests/_tmp_v11/ + tests/_tmp_replay/ scratchpads

key-decisions:
  - "8-feature V11_FEATURES allowlist locked as single source of truth — Phase 08/09 extend by appending here, never by inventing parallel allowlists"
  - "Corrupt marker JSON returns None silently (logs WARNING) rather than raising — old archives with stray files must not crash the silent v1.0 path"
  - "summary.md byte-equal verification scoped to MANUAL GATE (Claude /summarize-video re-run) — Python script cannot auto-invoke a Claude slash command, so the script handles paragraphs.json byte-equal + summary.md mutation hash, and docstring documents the user-driven gate"
  - "Per-slug profile resolution from paragraphs.json.params.json sidecar (cli.profile > func.profile > tutorial fallback) — prevents false-FAIL on podcast-aggregated archives like douyin_karpathy_llm_wiki"
  - "Token budget proxied as chars/3.5 instead of tiktoken instrumentation — Phase 09 2x cap has enough headroom that ~10% approximation error doesn't matter; tiktoken would force a heavy dep for a measurement that runs ~3 times"
  - "Force-add (-f) the 3 .token_budget.json files despite output/ being gitignored — listed in plan files_modified, must be tracked as Phase 09 reference; future per-archive baselines remain gitignored unless explicitly force-added"

patterns-established:
  - "Opt-in marker gate (.v11_features.json): is_v11_enabled(slug, feature?) returns False on missing/empty/corrupt — this is THE switch every v1.1 cmd_* will check"
  - "K5 read-only scripts pattern: scripts that READ decision artifacts (summary.md / plan.md) for measurement are allowed; the K5 invariant is no WRITE to those artifacts (verified by intent-correct grep, not literal text match)"
  - "Byte-equal regression test pattern: hash baseline + regen-in-tempdir + diff + mutation re-hash — extensible to any future v1.0 -> v1.x refactor"

requirements-completed: [PRE-V11-01, PRE-V11-02, PRE-V11-03]

# Metrics
duration: 9min
completed: 2026-05-03
---

# Phase 07 Plan 01: v1.1 Opt-in Foundation Summary

**Shipped agent/_v11.py opt-in marker library (.v11_features.json gates all v1.1 paths), scripts/replay_v10_archives.py D-29 strict byte-equal gate (33 PASS / 0 FAIL on actual archives), and scripts/measure_token_budget.py + 3 baselines (1917 / 5252 / 1906 tokens) for Phase 09 2x cap reference — zero existing files touched, zero v1.0 behavior changed.**

## Performance

- **Duration:** ~9 min (544s)
- **Started:** 2026-05-03T01:20:47Z
- **Completed:** 2026-05-03T01:29:51Z
- **Tasks:** 3 / 3 (TDD on Task 1; non-TDD on Tasks 2-3)
- **Files created:** 10
- **Files modified:** 1 (.gitignore)
- **Test count:** 16 stdlib unittest tests, all PASS

## Accomplishments

- `agent/_v11.py` opt-in marker library with locked 8-feature allowlist; silent v1.0 fallback when marker missing (D-29 invariant)
- `scripts/replay_v10_archives.py` 17-archive byte-equal D-29 strict gate — paragraphs.json regen via per-slug profile from sidecar (B2 fix prevents false-FAIL on podcast archives) + segs/meta/summary mutation hash check
- `scripts/measure_token_budget.py` with KNOWN_MODES pre-classification of 3 representative slugs; deterministic chars/3.5 proxy; 3 baseline `.token_budget.json` files committed for Phase 09 2x cap reference
- 16 stdlib unittest tests across `tests/test_v11_marker.py` (10) + `tests/test_replay_v10.py` (6 incl. T6 podcast sidecar resolution proving B2 fix wired)
- **D-29 STRICT GATE verified live:** `python -m scripts.replay_v10_archives --output-dir D:/gxy_code/videoSummary/output` -> `33 PASS / 0 FAIL / 30 SKIP` across all candidate archives in main repo

## Task Commits

Each task was committed atomically (with `--no-verify` per parallel-execution contract):

1. **Task 1: agent/_v11.py + tests/test_v11_marker.py (PRE-V11-01)** — `f3e3c81` (feat, TDD: RED test_v11_marker.py first, then GREEN agent/_v11.py)
2. **Task 2: scripts/replay_v10_archives.py + tests/test_replay_v10.py (PRE-V11-02)** — `7694d8b` (feat)
3. **Task 3: scripts/measure_token_budget.py + 3 baselines (PRE-V11-03)** — `ffab7ee` (feat; force-added 3 .token_budget.json under gitignored output/)

## Files Created/Modified

### Created

- `agent/_v11.py` — Opt-in marker helpers: `is_v11_enabled(slug, feature?)`, `set_v11_marker(slug, features)`, `get_v11_marker(slug)`, `V11_FEATURES` allowlist (8 names), `MARKER_FILENAME = ".v11_features.json"`
- `scripts/__init__.py` — empty package init so `python -m scripts.foo` works
- `scripts/replay_v10_archives.py` — D-29 strict gate; `_load_profile_for_slug` resolves per-archive profile from sidecar; `_replay_one` re-runs aggregate in tempdir + byte-diffs paragraphs.json + mid-test mutation hash check on segs/meta/summary; `--slug`/`--json`/`--output-dir` flags; exit 0=all PASS / 1=any FAIL / 2=output dir missing
- `scripts/measure_token_budget.py` — Per-archive `.token_budget.json` writer; KNOWN_MODES dict (BV132wizyEEB → replicate-guide; douyin_karpathy_llm_wiki → interview-distillation; douyin_claude_code_hooks → extension-applications); chars/3.5 deterministic proxy
- `tests/test_v11_marker.py` — 10 unittest tests (T01..T10) covering missing/present/empty/corrupt marker, allowlist validation, idempotency, exact filename, V11_FEATURES contents
- `tests/test_replay_v10.py` — 6 unittest tests (T1..T6) covering import sanity, nonexistent slug skip, synthetic archive PASS, 1-byte mutation FAIL, .v11_features.json marker SKIP, podcast sidecar resolution (B2 fix proof)
- `output/BV132wizyEEB/.token_budget.json` — replicate-guide baseline = 1917 tokens
- `output/douyin_karpathy_llm_wiki/.token_budget.json` — interview-distillation baseline = 5252 tokens
- `output/douyin_claude_code_hooks/.token_budget.json` — extension-applications baseline = 1906 tokens

### Modified

- `.gitignore` — added `tests/_tmp_v11/` + `tests/_tmp_replay/` per-test scratchpad pattern (mirrors Phase 4 `tests/_tmp_*` precedent)

## Decisions Made

See `key-decisions:` frontmatter for the 6 design decisions made during execution. Notable:

- **V11_FEATURES is a tuple, not a list** — immutability signals "single source of truth"; downstream phases extend by editing this file, not by passing parallel allowlists.
- **`_resolved_profile_name` is separated from `_load_profile_for_slug`** — the dict-returning helper is called inside the replay loop; the name-returning helper is for output transparency. Keeping them separate avoids returning a (dict, str) tuple from the hot path.
- **`measure_token_budget.py` reads summary.md / plan.md but does NOT write** — K5 boundary preserved as "no write to decision artifacts" (intent), even though literal text grep on these filenames would flag matches. Documented in deviation #2 below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan acceptance criterion `src.count('write_json_atomic') == 1` was off-by-1 (forgot import line)**

- **Found during:** Task 2 + Task 3 verification (`python -c` acceptance check)
- **Issue:** Plan asserted `write_json_atomic` appears exactly 1× in `scripts/replay_v10_archives.py` and `scripts/measure_token_budget.py`. Actual count is 2 (1 import line + 1 call site). The plan author forgot the import line counts toward the textual match. Plan intent was "only ONE write call (not two writes mutating archive)".
- **Fix:** Verified intent more precisely with a Python check that (a) excludes the import line and (b) confirms the single call site sits inside a `tempfile.TemporaryDirectory(...)` block (replay) or writes only to a `.token_budget.json` artifact path (measure). Both pass.
- **Files modified:** None (the source code already satisfied the intent; the plan's grep spec was incomplete)
- **Verification:** Refined intent-correct check passes for both scripts; replay's only call writes to `Path(td) / "paragraphs.json"` (tempdir); measure's only call writes to `slug_dir / ".token_budget.json"` (the explicit artifact, not a decision artifact).
- **Committed in:** N/A — no source change; documented here per Rule 1.

**2. [Rule 1 - Bug] K5 source-grep negative assertion in plan verification step #6 missed `scripts/measure_token_budget.py` exception**

- **Found during:** End-to-end verification step #6
- **Issue:** Plan's K5 grep listed `replay_v10_archives.py` as the explicit exception that may legitimately mention `summary.md` (it READS the file for hashing). It did NOT list `measure_token_budget.py`, even though that script also legitimately READS `summary.md` AND `plan.md` for char-count budget measurement (read-only).
- **Fix:** Refined the K5 check to verify INTENT (no WRITE to decision artifacts) rather than literal text presence. Used a regex-based check for write patterns (`write_text.*summary\.md`, `write_json_atomic.*summary\.md`, `os.replace.*summary\.md`, etc.) — all return zero matches. Confirmed all references to `summary.md` / `plan.md` in `measure_token_budget.py` are inside `LAYER_FILES` dict (read-only metadata table) and `p.read_text()` calls (read-only access).
- **Files modified:** None (the source code already preserves K5 read-only intent; the plan's literal grep was over-strict)
- **Verification:** Intent-correct grep passes; no write calls to decision artifacts in any of the 3 new modules.
- **Committed in:** N/A — no source change; documented here per Rule 1.

**3. [Rule 3 - Blocking] Worktree's `output/` only contains 1 tracked archive (BV1C9QCBdE1U); 60+ untracked archives only exist in main repo's `output/`**

- **Found during:** Task 2 (D-29 strict gate run)
- **Issue:** The worktree was checked out from a base commit where most `output/` archives are gitignored and not present in the worktree. Running `python -m scripts.replay_v10_archives` in the worktree alone would only test 1 archive (the tracked one), not the 60+ archives the spec references.
- **Fix:** Ran the replay script with `--output-dir D:/gxy_code/videoSummary/output` pointing at the main repo's working directory, which has all 60+ archives. This is a NORMAL use of the `--output-dir` flag (already designed into the script). Result: `33 PASS / 0 FAIL / 30 SKIP` — STRICT D-29 GATE PASSED across all candidate archives.
- **Files modified:** None
- **Verification:** Recorded the JSON summary; main repo's `git status output/` shows clean working tree (D-29 mutation invariant preserved across the test run).
- **Committed in:** N/A — operational workaround, no source change.

---

**Total deviations:** 3 auto-fixed (2× Rule 1 plan-spec bug, 1× Rule 3 worktree environment workaround)
**Impact on plan:** Zero functional impact. All deviations are plan-author or environment artifacts, not source code issues. Source code matches plan intent exactly. No scope creep.

## Issues Encountered

- **Worktree checked out from base commit `08a79f4` instead of `ceb21be` (the expected feature branch HEAD)** — Resolved at execution start by `git reset --hard ceb21bea06631f873d83001a672dfd3d2c8d051d`. The `<worktree_branch_check>` block in the executor prompt explicitly handled this case.
- **Token budget for `douyin_karpathy_llm_wiki` (5252 tokens) is ~2.7× larger than the other 2 archives (~1900 each)** — This is expected and informative: the interview-distillation mode produces a longer summary.md (long-form blockquote-heavy podcast distillation) and a podcast-aggregated paragraphs.json (longer paragraphs per the `--profile=podcast` D-27 thresholds). Phase 09's 2x cap is per-mode, so this disparity does not concern this plan.

## Authentication Gates

None — no external services or APIs touched in this plan.

## Self-Check

### Files exist
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\agent\_v11.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\scripts\__init__.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\scripts\replay_v10_archives.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\scripts\measure_token_budget.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\tests\test_v11_marker.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\tests\test_replay_v10.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\output\BV132wizyEEB\.token_budget.json` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\output\douyin_karpathy_llm_wiki\.token_budget.json` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1820c0946610f0d7\output\douyin_claude_code_hooks\.token_budget.json` ✓ FOUND

### Commits exist (verified via `git log --oneline | grep`)
- `f3e3c81` ✓ FOUND (Task 1: agent/_v11.py + tests/test_v11_marker.py)
- `7694d8b` ✓ FOUND (Task 2: scripts/replay_v10_archives.py + tests/test_replay_v10.py)
- `ffab7ee` ✓ FOUND (Task 3: scripts/measure_token_budget.py + 3 baselines)

## Self-Check: PASSED

## Phase Close — MANUAL GATE Procedure (per B3 fix Truth #6)

**The following manual procedure MUST be performed by the user before phase 07 close.** This closes the gap that Python scripts cannot auto-re-invoke `/summarize-video` (a Claude slash command, not a Python function). Documented in `scripts/replay_v10_archives.py` docstring section "MANUAL GATE COMMANDS".

### Step 1: Run automated gate (already verified during this plan execution)

```bash
python -m scripts.replay_v10_archives
# Verified during this plan: 33 PASS / 0 FAIL / 30 SKIP (against main repo's output/)
# MUST show fail=0 (strict byte-equal gate; any FAIL = phase NOT shippable)
```

### Step 2: Manual `/summarize-video` re-run on 2 representative archives

Pick 2 archives WITHOUT `.v11_features.json` marker:

| Archive | Mode | Source URL (locate from meta.json) |
|---------|------|------------------------------------|
| `BV132wizyEEB` | replicate-guide | `https://www.bilibili.com/video/BV132wizyEEB` |
| `douyin_karpathy_llm_wiki` | interview-distillation | (see meta.json source_url field) |

For EACH archive:

1. From a **fresh** Claude Code session (no v1.1 tool calls in current context — start a new session), run `/summarize-video <source-url>` against the source URL
2. **Critical:** Let Claude write to a TEST slug dir (e.g., `output/test_replay_BV132wizyEEB/`) — DO NOT overwrite the committed baseline
3. Run byte-diff:
   ```bash
   git diff --no-index output/BV132wizyEEB/summary.md output/test_replay_BV132wizyEEB/summary.md
   git diff --no-index output/douyin_karpathy_llm_wiki/summary.md output/test_replay_douyin_karpathy_llm_wiki/summary.md
   ```
4. **EXPECTED:** zero output (byte-equal). Any diff = phase 07 NOT shippable; investigate which v1.1 module's import side-effect leaked into the v1.0 path.

### Step 3: Log results

After running Steps 1 + 2, append a `## Manual Gate Results` section to THIS file with:
- Date/time of each re-run
- Outcome of each `git diff --no-index` (zero diff = PASS; any diff = FAIL with details)
- Which Claude session was used (timestamp, model)

If FAIL: phase 07 is NOT shippable. Open an investigation: which v1.1 import was added between the committed baseline and the re-run that produced a different summary.md?

## Threat Flags

None — this plan introduces zero new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The 4 new files are:

- `agent/_v11.py` (read/write to one explicit `.v11_features.json` per slug, atomic)
- `scripts/replay_v10_archives.py` (read-only on archive files; writes only to tempdir)
- `scripts/measure_token_budget.py` (read-only on segs.json/paragraphs.json/plan.md/summary.md; writes only to `.token_budget.json` artifact path)
- 3 `.token_budget.json` baselines (data files, no schema migration)

## Known Stubs

None — all functions implemented and tested. The MANUAL GATE procedure (Step 2 above) is documented as user-driven, not a stub: it intentionally requires Claude session re-invocation that Python cannot automate.

## Next Plan Readiness

Plan 07-02 (next in wave) and Plan 07-03 (subsequent waves) can now consume:

- `from agent._v11 import is_v11_enabled, set_v11_marker, get_v11_marker, V11_FEATURES` — to gate any new cmd_* on `.v11_features.json` opt-in
- `python -m scripts.replay_v10_archives` — D-29 regression test before any merge
- `output/<slug>/.token_budget.json` baselines — for Phase 09 to compute the 2x cap

**Locked allowlist for Phase 08/09 to extend:** `V11_FEATURES = ("transcribe_lint", "mode_signals", "schedule_suggest", "trace_tokens", "self_contained_header", "glossary", "tldr", "verifier")`. Phase 08 will activate `trace_tokens` / `self_contained_header` / `glossary` / `tldr`; Phase 09 will activate `verifier`.

---
*Phase: 07-warm-up-k5-emitters-d-29-foundation*
*Plan: 01*
*Completed: 2026-05-03*
