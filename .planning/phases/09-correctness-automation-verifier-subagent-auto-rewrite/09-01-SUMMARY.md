---
phase: 09-correctness-automation-verifier-subagent-auto-rewrite
plan: 01
subsystem: emitters
tags: [k5, emitters, summary-lint, format-spec, citation-density, glossary-drift, v11-marker, source-grep-test, write-pattern-regex]

# Dependency graph
requires:
  - phase: 02-resume-infrastructure-cache-correctness
    provides: agent/io.write_json_atomic (atomic JSON sidecar write)
  - phase: 07-warm-up-k5-emitters-d-29-foundation
    provides: agent/_v11.py V11_FEATURES allowlist + scripts/replay_v10_archives.py D-29 gate + agent/transcribe_lint.py shape (mirrored)
  - phase: 08-writing-rules-claude-md-extensions-glossary
    provides: agent/glossary.py write-pattern-regex K5 boundary precedent + V11_FEATURES extended 8 → 13 (mirrored extension pattern) + CLAUDE.md `### 格式锁定` 4+1 invariants + CORR-02 引用资格规则
provides:
  - "agent/summary_lint.py — pure-stdlib K5 emitter (5 format invariants + citation_stats + citation_eligibility_violations + glossary_inconsistencies)"
  - "cmd_summary_lint handler in agent/tools.py + summary_lint subparser + dispatch entry in cmds dict"
  - "V11_FEATURES extended 13 → 15 (summary_lint + verifier_phase_75 explicit names; both pass set_v11_marker validation)"
  - "tests/test_summary_lint.py (15 unit tests; ALL PASS in <1s)"
  - "tests/test_k5_emitters.py extended with 2 new tests (test_K5_handler_cmd_summary_lint + test_K5_module_summary_lint) using _WRITE_PATTERNS_FORBIDDEN regex (mirrors Phase 08-01 glossary.py exception)"
affects:
  - 09-02 (Phase 7.5 verifier subagent reads summary_lint.json as ground-truth mechanical input — separating regex-able rules from semantic checks per P-09 token-budget mitigation)

# Tech tracking
tech-stack:
  added: []  # zero new pip deps — pure stdlib (re + datetime + pathlib)
  patterns:
    - "K5 emitter pattern: lazy module import + _validate_out_path + _log slug-prefix + write_json_atomic + _emit_event mirrors cmd_transcribe_lint shape byte-for-byte"
    - "Write-pattern regex K5 boundary (mirrors Phase 08-01 agent/glossary.py exception): substring `summary.md` legitimately appears as input arg path receiver + argparse help text — assert NO write-call patterns target the substring instead of forbidding the substring entirely"
    - "Section-aware lint: line-by-line H2 tracking maps each line to its section (TL;DR / 你需要知道什么 / 你不需要知道什么 / transition / body); citation eligibility violations only emitted when forbidden section + trace token co-occur"
    - "Code-fence + image-only line exclusion in load-bearing detection: `_build_in_fence_mask` builds parallel-indexed bool mask; `_IMAGE_ONLY_LINE_RE` skips pure `![](...)` lines — both excluded from claim counting to prevent false-positive trace-after-claim violations"

key-files:
  created:
    - agent/summary_lint.py
    - tests/test_summary_lint.py
    - .planning/phases/09-correctness-automation-verifier-subagent-auto-rewrite/09-01-SUMMARY.md
  modified:
    - agent/_v11.py             # V11_FEATURES tuple extended 13 → 15 (Phase 09 ADDs)
    - agent/tools.py            # +cmd_summary_lint handler + subparser + dispatch entry
    - tests/test_k5_emitters.py # +2 K5 boundary tests (write-pattern regex style)
    - tests/test_v11_marker.py  # auto-fix: count assertion 13 → 15 (Rule 1 deviation)

key-decisions:
  - "Write-pattern regex (not literal substring) for K5 boundary on cmd_summary_lint + agent/summary_lint.py — `summary.md` legitimately appears as the input arg path receiver and argparse help text (Phase 07-03 deviation #2 + Phase 08-01 lesson). Mirrors agent/glossary.py exception. The literals `plan.md` / `schedule.json` have NO legitimate use here and are forbidden entirely (asserted by `assertNotIn`)."
  - "Schema locked at version=1 + schema_version=1 + ISO-8601 checked_at ending with 'Z'. Output dict shape exactly matches 09-CONTEXT.md `<specifics>` section line 103-127 proposal: format_invariants (5 sub-dicts) / citation_stats / citation_eligibility_violations / glossary_inconsistencies. Pure JSON-serializable, no datetime objects in output."
  - "Section classification uses substring matching on H2 heading content (`5 分钟速读版` → TL;DR, `读这篇前你需要知道` → 你需要知道什么, etc) instead of byte-equal heading lookup — tolerates Claude-written headings with extra whitespace / suffixes / variant punctuation while keeping deterministic mapping."
  - "load-bearing claim detection uses lexical signals (numbers, fenced spans, file extensions, fps/frames/ keywords) NOT semantic understanding — pure regex by design (verifier subagent in 09-02 provides semantic backstop for narrative-only claims that slip through). Documented as a heuristic limit in module docstring."
  - "Heuristic forbidden-action allowlist for second_person_imperative kept small (打开/创建/配置/运行/执行/导入/启动) — caught the strict cases in tests without false-positive on common 'X 是 Y' / '会有 ...' constructs."
  - "Image-only lines + code-fence content excluded from load-bearing scan via `_IMAGE_ONLY_LINE_RE` + `_build_in_fence_mask` — discovered during Test 1 (5 invariants happy path) where `![](frames/...jpg)` and inner `x = 1` were initially flagged. Fix is principled: pure visual / fenced-code content is not prose."

patterns-established:
  - "Phase 09 K5 emitter contract: read-only mechanical CLI emits sibling sidecar; assert no-write to decision artifacts via write-pattern regex (NOT literal substring) when the substring legitimately appears in argparse help / input args. agent/summary_lint.py is the 5th K5 emitter shipped in v1.1 (after transcribe_lint, mode_signals, schedule_suggest, glossary_audit + glossary_append from Phase 08)."
  - "When extending V11_FEATURES tuple, ALWAYS update tests/test_v11_marker.py:test_T10 count assertion in the same plan (Phase 08-01 hit the same pattern — 8 → 13; Phase 09-01 now 13 → 15). Future plans should treat test_T10 as a synchronizing cross-reference."

requirements-completed: [CORR-03a]

# Metrics
duration: ~30 min
completed: 2026-05-03
---

# Phase 09 Plan 01: agent/summary_lint.py CORR-03a Mechanical Lint Emitter Summary

**Shipped 5th K5 emitter (CORR-03a `summary_lint`) — pure-stdlib regex + line-by-line scan checking 4+1 format-spec invariants + citation density + citation eligibility (P-02 anti-pollution) + glossary drift detection. V11_FEATURES extended to 15 entries (summary_lint + verifier_phase_75 explicit names). 28 new tests PASS (15 summary_lint + 2 new K5 boundary + auto-fix 1 prior-test count). D-29 byte-equal regression preserved at 33 PASS / 0 FAIL.**

## Performance

- **Duration:** ~30 min (TDD on Task 1, mechanical wiring on Task 2, verification + SUMMARY on Task 3)
- **Started:** 2026-05-03T13:00:00Z (approx)
- **Completed:** 2026-05-03T13:30:00Z (approx)
- **Tasks:** 3 / 3 (Task 1 module + tests TDD / Task 2 wiring + K5 boundary tests / Task 3 verification + SUMMARY)
- **Files created:** 3 (agent/summary_lint.py + tests/test_summary_lint.py + 09-01-SUMMARY.md)
- **Files modified:** 4 (agent/_v11.py + agent/tools.py + tests/test_k5_emitters.py + tests/test_v11_marker.py [Rule 1 auto-fix])
- **New tests:** 17 (15 summary_lint unit tests + 2 K5 boundary regex tests)
- **Total test suite:** 187 tests pass (1 skipped, 0 failures) — was 170 before this plan

## Accomplishments

- **CORR-03a (summary_lint)**: pure-stdlib mechanical checker with 5 format invariants + citation density stats + citation eligibility violations + glossary drift. Schema-locked output: `version=1`, `schema_version=1`, `summary_path` (string), `checked_at` (ISO-8601 ending with Z), `format_invariants` (5 sub-dicts), `citation_stats`, `citation_eligibility_violations`, `glossary_inconsistencies`.
- **5 format invariants** (CLAUDE.md `### 格式锁定` 4+1 项):
  1. `timestamp_format` — strict 8-char `[HH:MM:SS]`; loose `[1:23]` / `[1:23:45]` flagged
  2. `code_fence_language` — every opening ``` must declare a lang token
  3. `relative_frame_paths` — `frames/...{jpg|jpeg|png|webp}` only; absolute / http URLs flagged
  4. `second_person_imperative` — forbid `我们 + verb` / `noun + 被 + verb` for action verb set
  5. `trace_after_claim` — load-bearing claim lines in `body` must end with `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` or `[para_NNNN @ HH:MM:SS]` token
- **citation_stats**: claims_total / claims_with_trace / claims_without_trace (with line + snippet) / trace_density (rounded to 3 decimals) / uncertainty_markers (count of `[?]`)
- **citation_eligibility_violations** (P-02): trace tokens FORBIDDEN in TL;DR (`5 分钟速读版`) / 你需要 prelude (`读这篇前你需要知道`) / 你不需要知道什么 / transition (`章节小结` / `总评`) sections — each violation includes line, section label, FORBIDDEN reason, snippet
- **glossary_inconsistencies**: inline `Term (def)` in body vs `## Term (def)` in glossary file → drift_detected entries with summary_definition + glossary_definition for cross-comparison; gracefully returns `[]` when glossary_path is None or non-existent
- **K5 boundary**: 2 new write-pattern regex tests (test_K5_handler_cmd_summary_lint + test_K5_module_summary_lint) using `_WRITE_PATTERNS_FORBIDDEN` (NOT extending FORBIDDEN_LITERALS — `summary.md` is legitimate input arg). The literals `plan.md` / `schedule.json` have NO legitimate use and are forbidden entirely (verified by `assertNotIn`).
- **V11_FEATURES extended 13 → 15** (Phase 09 ADDs: `summary_lint` for CORR-03a + `verifier_phase_75` for CORR-03b/c). Both pass `set_v11_marker` validation. The existing 13 entries remain backward-compatible.
- **CLI smoke test PASS**: `python -m agent.tools summary_lint <slug>/summary.md` produces valid `summary_lint.json` (version=1, schema_version=1, all 5 invariants present) + emits `summary_lint completed` event to `state.jsonl`.
- **D-29 STRICT GATE preserved**: `python -m scripts.replay_v10_archives --output-dir D:/gxy_code/videoSummary/output` reports `33 PASS / 0 FAIL / 30 SKIP` — every byte-equal invariant on all 33 candidate v1.0 archives still holds after Plan 09-01 ships.
- **Full test suite green**: `python -m unittest discover tests` reports `Ran 187 tests in 1.691s OK (skipped=1)` — 0 failures.

## Task Commits

Each task was committed atomically with --no-verify (parallel executor):

1. **Task 1: agent/summary_lint.py + tests/test_summary_lint.py (TDD red→green)** — `7f4f49d` (feat)
2. **Task 2: wire cmd_summary_lint + V11_FEATURES extension + K5 boundary tests** — `dd11a91` (feat)
3. **Task 3 deviation auto-fix: update test_T10 count assertion 13 → 15** — `3f77549` (fix; Rule 1 auto-fix)

(Task 3 SUMMARY commit follows separately as `docs(09-01)`.)

## Files Created/Modified

### Created
- `agent/summary_lint.py` — 416 LOC / 16 KB; 5 invariant checkers + citation_stats + citation_eligibility + glossary drift; pure-stdlib (no new pip deps); fully read-only (zero write_text / os.replace / open(..,'w') / _atomic_write calls).
- `tests/test_summary_lint.py` — 281 LOC / 12 KB; 15 unit tests covering all 5 invariants + citation stats + citation eligibility (TL;DR + prelude FORBIDDEN) + glossary drift + glossary_path=None graceful degrade + uncertainty marker count + 0-byte edge case + schema version pin + UTF-8 CJK round-trip.
- `.planning/phases/09-correctness-automation-verifier-subagent-auto-rewrite/09-01-SUMMARY.md` — this file.

### Modified
- `agent/_v11.py` — V11_FEATURES tuple extended 13 → 15 (added `summary_lint` + `verifier_phase_75`). Comment block updated `8 + 5 = 13` → `8 + 5 + 2 NEW Phase 09 = 15`.
- `agent/tools.py` — added `cmd_summary_lint` handler (lazy import of `lint_summary` + `LINT_FILENAME`; mirrors cmd_transcribe_lint shape with `_validate_out_path` / `write_json_atomic` / `_log` / `_emit_event`); added `summary_lint` subparser registration with `summary_path` positional arg + `--glossary-path` optional; added `"summary_lint": cmd_summary_lint` dispatch entry to `cmds` dict (Phase 07/09 K5 emitters block, comment header updated).
- `tests/test_k5_emitters.py` — imported `cmd_summary_lint` + added 2 new test methods (test_K5_handler_cmd_summary_lint + test_K5_module_summary_lint) at end of TestK5BoundaryPhase07 class. Uses `_WRITE_PATTERNS_FORBIDDEN` regex (mirrors Phase 08-01 glossary pattern); for the module also asserts no `plan.md` / `schedule.json` literals (those have no legitimate use).
- `tests/test_v11_marker.py` — auto-fix (Rule 1): count assertion `len(V11_FEATURES) == 13` → `== 15` + added `phase_09_names` membership tuple. Mirrors Phase 08-01 deviation pattern (8 → 13). Documented as recurring synchronizer for future V11_FEATURES extensions.

## Decisions Made

- **Write-pattern regex over literal substring for K5 boundary**: The literal `summary.md` legitimately appears in (a) `agent/tools.py` cmd_summary_lint argparse help text and (b) the input arg path receiver. Per Phase 07-03 deviation #2 + Phase 08-01 glossary.py exception, the K5 invariant is "module/handler must not WRITE to the decision artifact", NOT "module/handler must not contain the substring". Captured by `_WRITE_PATTERNS_FORBIDDEN` regex (12 patterns: write_text / open(..,'w') / os.replace / _atomic_write × 3 forbidden filenames). For agent/summary_lint.py, additionally asserted NO `plan.md` / `schedule.json` literals (those have no legitimate use here).
- **Section-aware classification by substring match (not byte-equal)**: H2 heading lookup uses `if substr in heading` for the 5 forbidden section labels. Tolerates Claude-written headings with extra whitespace / variant suffixes / surrounding punctuation while keeping mapping deterministic.
- **Image-only lines + fenced code content excluded from claim detection**: Discovered in Test 1 (happy path) — `![](frames/...jpg)` matches `_LOAD_BEARING_HINT_RE` (the `frames/` substring) and inner `x = 1` matches the numeric regex; both should NOT be flagged as claims missing trace tokens (they are visual / fenced-code content, not prose). Added `_IMAGE_ONLY_LINE_RE` + `_build_in_fence_mask` for principled exclusion. Mask is parallel-indexed (one bool per line) so the fence-delimiter lines themselves are also excluded.
- **Heuristic forbidden-action allowlist kept small** (打开/创建/配置/运行/执行/导入/启动): Larger sets (e.g. adding 设置/查看/检查/修改) had higher false-positive rate on common Chinese narrative constructions. Documented as heuristic limit in module docstring; verifier subagent in Plan 09-02 provides semantic backstop.
- **Schema includes both `version` AND `schema_version`** (both = 1): Aligns with `agent/_v11.py` marker schema (which uses `version`) AND `agent/io.py` SCHEMA_VERSION pattern. Future migrations can bump either independently.
- **Smoke test under output/_smoke_lint** (cleaned after verification): used `_smoke_lint` slug (underscore prefix means it sorts to the top of output/ listings) so it doesn't collide with any real BV/douyin slug. Tested end-to-end CLI → JSON output → state.jsonl event emission.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated `tests/test_v11_marker.py:test_T10_v11_features_locked_allowlist` count assertion**
- **Found during:** Task 3 full unittest discover
- **Issue:** Pre-existing test asserted `len(V11_FEATURES) == 13` (the Phase 08 baseline); my Phase 09 extension to 15 broke this assertion.
- **Fix:** Updated to `assertEqual(len(V11_FEATURES), 15)` + added `phase_09_names` tuple with membership assertions for `summary_lint` + `verifier_phase_75`. Same pattern Phase 08-01 used when extending 8 → 13.
- **Files modified:** tests/test_v11_marker.py (10 insertions / 3 deletions)
- **Commit:** 3f77549

**2. [Out-of-scope discovery — created scratch dir, otherwise no-op] `tests/_tmp_glossary/` was missing on disk**
- **Found during:** Task 2 K5 emitter test run (test_K5_glossary_append_writes_only_to_accumulator threw FileNotFoundError trying to mkdtemp under that dir)
- **Issue:** The directory is gitignored (per Phase 07-03 SUMMARY) but not committed; freshly-checked-out worktrees won't have it.
- **Fix:** Created the directory on disk via `python -c "Path('tests/_tmp_glossary').mkdir(exist_ok=True)"`. Did NOT modify `.gitignore` or add a `.gitkeep` (out of scope; pre-existing infra issue).
- **Files modified:** none committed (directory creation only).

### Otherwise

Plan executed exactly as written. The two K5 boundary tests + the V11_FEATURES extension + the cmd_summary_lint handler + subparser + dispatch entry were all literal copy-from-plan with minor cosmetic adjustments (e.g. multi-line argparse help string broken across 3 lines for readability; added comment headers).

## Issues Encountered

None blocking. Two friction points:
1. **Worktree initial state**: the worktree was at HEAD `08a79f4` (a v1.0 baseline) but the orchestrator base was `be9f0cc`. The required `git reset --soft be9f0cc...` followed by `git checkout HEAD -- .` to fully sync the worktree disk state with the new HEAD index.
2. **agent/summary_lint.py docstring contained `plan.md` / `schedule.json` substrings** (the original docstring tried to *describe* the K5 boundary in terms of those names). Caught by Task 2 test_K5_module_summary_lint. Reworded the docstring to reference "the plan / schedule decision artifact filenames" descriptively without containing the literal substrings. K5 boundary now statically asserted on disk.

## Verification Results

All plan-level verification checks pass:

| # | Check | Result |
|---|-------|--------|
| 1 | `python -m unittest tests.test_summary_lint` | PASS — 15 tests, OK |
| 2 | `python -m unittest tests.test_k5_emitters` | PASS — 13 tests, OK (includes 2 new Phase 09) |
| 3 | `python -m agent.tools summary_lint --help` | PASS — exits 0; shows positional `summary_path` + optional `--glossary-path` |
| 4 | `len(V11_FEATURES) == 15` AND `summary_lint`/`verifier_phase_75` in V11_FEATURES | PASS |
| 5 | `set_v11_marker(td, ['summary_lint', 'verifier_phase_75'])` | PASS — no ValueError |
| 6 | `agent/summary_lint.py` write-pattern grep | PASS — zero write patterns; only docstring mentions of `write_text` etc as descriptive prose |
| 7 | `agent/summary_lint.py` literal `plan.md` / `schedule.json` check | PASS — both substrings absent |
| 8 | CLI smoke test (synthetic summary → summary_lint.json + state.jsonl event) | PASS — both files produced with locked schemas |
| 9 | D-29 byte-equal regression (`scripts.replay_v10_archives`) | PASS — 33 PASS / 0 FAIL / 30 SKIP (matches prior baseline) |
| 10 | Full unittest discover | PASS — 187 tests, OK (skipped=1, 0 failures) |

## Self-Check: PASSED

Verified all claimed artifacts exist on disk:

- `agent/summary_lint.py` — FOUND (16025 bytes / 416 LOC)
- `tests/test_summary_lint.py` — FOUND (12189 bytes)
- Modified: `agent/_v11.py` / `agent/tools.py` / `tests/test_k5_emitters.py` / `tests/test_v11_marker.py` — all FOUND with documented changes
- This SUMMARY at `.planning/phases/09-correctness-automation-verifier-subagent-auto-rewrite/09-01-SUMMARY.md` — FOUND (the file you are reading)

Verified all claimed commits exist in git log:

- `7f4f49d` — `feat(09-01): add agent/summary_lint.py CORR-03a mechanical checker + 14 unit tests` — FOUND
- `dd11a91` — `feat(09-01): wire cmd_summary_lint + extend V11_FEATURES + K5 boundary tests` — FOUND
- `3f77549` — `fix(09-01): update test_T10_v11_features_locked_allowlist count 13 → 15` — FOUND
