---
phase: 07-warm-up-k5-emitters-d-29-foundation
plan: 03
subsystem: emitters
tags: [k5, emitters, pypinyin, transcribe-lint, mode-signals, schedule-suggest, glossary-audit, source-grep-test, claude-md-update, homophone-cluster]

# Dependency graph
requires:
  - phase: 02-resume-infrastructure-cache-correctness
    provides: agent/io.write_json_atomic, load_segs, load_paragraphs (atomic JSON write + schema-tolerant loaders)
  - phase: 04-frame-extraction
    provides: cmd_detect_scenes K5 pattern + tests/test_scenes.py:TestK5Boundary template (mirror exactly)
  - phase: 07-warm-up-k5-emitters-d-29-foundation/07-01
    provides: agent/_v11.py opt-in marker library + scripts/replay_v10_archives.py D-29 gate
  - phase: 07-warm-up-k5-emitters-d-29-foundation/07-02
    provides: agent/queue.py FileLock-on-state pattern + nested cmd_queue_* dispatch idiom
provides:
  - "agent/transcribe_lint.py — L1 ASR suspect-token detector (CORR-01a; 5 strategies including pypinyin homophone_cluster)"
  - "agent/mode_signals.py — TOOL-A 5 objective signals emitter (NO recommended_mode field; K5 P-07)"
  - "agent/schedule_suggestion.py — TOOL-B fps-segment suggester with mandatory FPS-04 baseline (D-08)"
  - "agent/glossary_audit.py — Phase 08 TEACH-A3 helper stub (read-only audit of output/_glossary.md)"
  - "4 new top-level CLI subcommands wired into agent/tools.py (transcribe_lint, mode_signals, schedule_suggest, glossary_audit)"
  - "tests/test_k5_emitters.py — 8 source-grep static assertions for K5 boundary preservation"
  - "CLAUDE.md — new H2 section documenting v1.1 marker + 4 emitters + Phase 6 W2 amendment"
affects:
  - 08-prompts (will read transcribe_warnings.json + mode_signals.json sidecars in CORR-01b L2 + plan-authoring prompts)
  - 09-verifier (will read mode_signals.json + schedule_suggestion.json for plan-vs-content cross-checks)

# Tech tracking
tech-stack:
  added:
    - "pypinyin>=0.55.0 (pure-Python ~840KB; ONLY new pip dep for v1.1; concentrated use in transcribe_lint.detect_warnings homophone_cluster strategy)"
  patterns:
    - "K5 emitter pattern: lazy module import + _validate_out_path + _log slug-prefix + write_json_atomic (mirrors cmd_detect_scenes byte-for-byte)"
    - "K5 source-grep static assertion via inspect.getsource on cmd_* handlers + Path.read_text on module files (mirrors tests/test_scenes.py:TestK5Boundary)"
    - "CJK bigram extraction (no jieba dep needed — 2-char overlapping windows from CJK runs cover ~70% Modern Mandarin vocabulary; freq-ratio threshold 5x keeps signal high)"
    - "Phrasing convention: 'the schedule artifact' / 'the plan artifact' / 'the summary artifact' descriptive nouns instead of literal filenames in handler/module docstrings (K5 negative-grep compliance)"
    - "duration_source provenance arg ('ffprobe' | '--duration-override') for archives without retained video.mp4 (W5 fix)"

key-files:
  created:
    - agent/transcribe_lint.py
    - agent/mode_signals.py
    - agent/schedule_suggestion.py
    - agent/glossary_audit.py
    - tests/test_transcribe_lint.py
    - tests/test_mode_signals.py
    - tests/test_schedule_suggestion.py
    - tests/test_glossary_audit.py
    - tests/test_k5_emitters.py
    - .planning/phases/07-warm-up-k5-emitters-d-29-foundation/07-03-SUMMARY.md
  modified:
    - requirements.txt  # added pypinyin>=0.55.0
    - agent/tools.py    # 4 new cmd_* handlers + 4 subparsers + 4 dispatch entries
    - CLAUDE.md         # 2 insertions: new H2 section + W2 amendment in Phase 6 multi-terminal section
    - .gitignore        # added tests/_tmp_glossary/ ASCII-safe scratchpad

key-decisions:
  - "CJK bigram extraction in transcribe_lint instead of jieba word-segmentation — original plan regex `[一-鿿]{2,}+` was greedy and matched whole CJK runs as single tokens (so '迅练' inside '我刚才说的是迅练而不是别的' was never a candidate). Switched to overlapping 2-char bigram extraction; covers ~70% Mandarin vocabulary; freq-ratio threshold 5x keeps signal high. No new dep needed."
  - "K5 source-grep test resolves module paths relative to repo root (Path(__file__).parent.parent / module_path) — needed because the test runs from tests/ but reads agent/*.py files; absolute path made the test brittle across worktrees"
  - "Cross-reference bullet in W2 amendment intentionally creates 2 grep hits for 'v1.1 opt-in marker + 4 K5 emitters' (one in Phase 6 list bullet pointing forward + one heading at line 1092) — plan acceptance said grep returns 1 but the W2 amendment necessitates 2 (cross-reference + heading); both insertions are present, K5 boundary preserved, this is desired UX"
  - "schedule_suggestion.py uses 'uses_scenes_json' field name (NOT 'schedule.json' literal!) — this is a meta dict KEY name; verified K5 source-grep finds zero forbidden literals in the module"

patterns-established:
  - "K5 emitter contract: emit signals/suggestions as sibling sidecars; never auto-mutate the plan/schedule/summary decision artifacts. Statically asserted by source-grep test that fails the build if a forbidden literal slips into a docstring or comment."
  - "pypinyin homophone_cluster: sparse CJK bigrams (freq < 3) get pinyin signature lookup; if a same-pinyin candidate exists with freq > 5x suspect's freq, suggest the high-freq candidate. Locked confidence 0.65; evidence_detail contains pinyin signature + candidate freq for traceability."
  - "K5 source-grep test target list — when adding new K5 emitters in Phase 08/09, register them in tests/test_k5_emitters.py FORBIDDEN_LITERALS check by adding a new test_K5_handler_* + test_K5_module_* pair."

requirements-completed: [CORR-01a, TOOL-A, TOOL-B]

# Metrics
duration: ~45min  # heavy spec-following + bigram refactor + K5 verification
completed: 2026-05-03
---

# Phase 07 Plan 03: 4 K5 Read-Only Signal Emitters Summary

**Shipped 4 K5 read-only emitters (transcribe_lint with 5 strategies including pypinyin homophone_cluster, mode_signals with no recommended_mode field, schedule_suggest with mandatory FPS-04 baseline + --duration W5 override, glossary_audit Phase 08 stub) + 8 K5 source-grep static assertions + CLAUDE.md documentation — D-29 byte-equal regression gate still passes 33/0 on all archives, 87/87 phase-07 tests green, pypinyin actually used (B1 fix verified by Test 12).**

## Performance

- **Duration:** ~45min (heavy spec-following + 1 bigram refactor + thorough K5 verification)
- **Started:** 2026-05-03 (post-Wave-1 consolidation)
- **Completed:** 2026-05-03
- **Tasks:** 3 / 3 (TDD on Tasks 1+2; integration on Task 3)
- **Files created:** 10
- **Files modified:** 4
- **Test count:** 40 new tests across 5 test files (12 + 10 + 6 + 4 + 8); 87 total when combined with prior phase-07 plan tests; all PASS

## Accomplishments

- **CORR-01a (transcribe_lint)**: 5 detection strategies wired with explicit allowlist (PITFALLS P-01 false-positive guard). Strategy #5 `homophone_cluster` is the pypinyin justification — sparse CJK bigrams (freq < 3) get pinyin signature lookup; if a same-pinyin candidate has freq > 5x suspect's freq, suggest the high-freq candidate. **Test 12 (B1 fix) verified live**: '训练' 8x + '迅练' 1x synthetic data correctly emits warning with `suggested_text="训练"`, `evidence_source="homophone_cluster"`, `evidence_detail="pinyin=xunlian, candidate freq=8"`.
- **TOOL-A (mode_signals)**: 5 objective signals (code_fence_density, step_marker_density, question_form_ratio, speaker_turn_signals, cross_tool_comparison_count) with raw_count + per_paragraph + capped evidence_paragraphs. **NO recommended_mode field** (P-07 K5 boundary verified by Test M2).
- **TOOL-B (schedule_suggest)**: combines paragraphs + scenes + silence into suggested fps segments + mandatory FPS-04 baseline (fps ≤ 0.1 covering full duration; D-08 strict-OR-fallback gate). **W5 fix verified**: `--duration <float>` override flag bypasses ffprobe entirely for archives without retained video.mp4. `duration_source` provenance recorded in suggestion_meta ('ffprobe' or '--duration-override').
- **glossary_audit (Phase 08 helper stub)**: read-only audit of `output/_glossary.md` parsing H2 anchors; reports `duplicate_terms` + `conflicting_definitions`. Returns schema-stable shape on missing file (forward-compat — Phase 08 TEACH-A3 will add cross-summary frequency tracking).
- **K5 boundary preserved**: 8 static source-grep assertions across 4 cmd_* handlers (`inspect.getsource`) + 4 module files (`Path.read_text`). Zero references to `summary.md` / `plan.md` / `schedule.json` literals — phrasing uses descriptive nouns ("the schedule artifact" etc).
- **CLI smoke tests pass**: all 4 new subcommands respond correctly to `--help`; `glossary_audit --json` returns valid JSON on missing file (stub shape); `schedule_suggest --help` shows `--duration` option visibly.
- **CLAUDE.md updated (2 insertions)**: new H2 section "## v1.1 opt-in marker + 4 K5 emitters (Phase 07)" inserted before /summarize-video heading documents marker schema + 4 emitter usage table + token budget baseline + multi-terminal lock domain extension. W2 amendment adds 1 forward-pointer bullet in Phase 6 multi-terminal section's "没锁的命令" subsection mentioning the queue subcommand + queue.lock.
- **D-29 STRICT GATE preserved**: `python -m scripts.replay_v10_archives --output-dir D:/gxy_code/videoSummary/output` reports `33 PASS / 0 FAIL / 30 SKIP` — every byte-equal invariant on all 33 candidate v1.0 archives still holds after Plan 03 ships.

## Task Commits

Each task was committed atomically with `--no-verify` (parallel-executor flag):

1. **Task 1: pypinyin + transcribe_lint + 12 tests (CORR-01a)** — `673333e` (feat; TDD: wrote tests + module + bigram refactor on Test 12 fail)
2. **Task 2: 3 K5 emitters + 20 tests (TOOL-A + TOOL-B + glossary stub)** — `00f0b65` (feat; sequential per-module TDD as per Plan 03 W4 execution_note)
3. **Task 3: CLI wiring + K5 source-grep tests + CLAUDE.md update (W2 + W5)** — `19e06c2` (feat)

**Plan metadata commit:** _(this commit, after SUMMARY write)_

## pypinyin Verification (B1 acceptance)

**Installed:** `pypinyin-0.55.0` (pure-Python wheel; pip user-install path on Windows 11 zh-CN; ~840KB).

**Used in:**
- `agent/transcribe_lint.py:24` — `from pypinyin import lazy_pinyin` (literal import line present)
- `agent/transcribe_lint.py:_pinyin_signature()` — calls `lazy_pinyin(token)` to compute lowercase joined pinyin signature for homophone clustering
- `agent/transcribe_lint.py:detect_warnings()` Pass 4 — uses pinyin signatures to find sparse-token homophone candidates with freq > 5x ratio

**Test 12 (homophone_cluster proof of work)**: synthetic data with '训练' (xunlian) appearing 8 times + '迅练' (xunlian) appearing 1 time → `detect_warnings` correctly emits 1 warning with `suspect_text="迅练"`, `suggested_text="训练"`, `evidence_source="homophone_cluster"`, `confidence=0.65`, `evidence_detail="pinyin=xunlian, candidate freq=8"`. **PASS** — pypinyin is NOT dead weight.

## 4 Emitter Signature Surfaces

```
python -m agent.tools transcribe_lint <slug_dir>
  → output/<slug>/transcribe_warnings.json
  Schema: {"version":1, "warnings":[{para_id, seg_index, start, end,
           suspect_text, suggested_text, evidence_source, confidence,
           context_before, context_after, evidence_detail?}]}

python -m agent.tools mode_signals <paragraphs_json> --out <out>
  → mode_signals.json
  Schema: {"version":1, "video", "paragraphs_hash", "signals":{...5 keys}}
  K5 INVARIANT: NO `recommended_mode` field

python -m agent.tools schedule_suggest <slug_dir> [--out <path>] [--duration <float>]
  → output/<slug>/schedule_suggestion.json (default)
  Schema: {"version":1, "video", "duration_s", "suggested_segments":[...],
           "suggestion_meta":{scene_cut_count, flagged_silences,
                              uses_silence_map, uses_scenes_json,
                              duration_source}}
  K5 INVARIANT: ALWAYS includes a "fps-04-baseline" segment with fps≤0.1
                covering full duration (D-08 fallback gate)
  W5 FIX: --duration <float> bypasses ffprobe; required for archives
                without retained video.mp4

python -m agent.tools glossary_audit [--glossary-path <path>] [--json]
  → stdout (or --json structured output)
  Schema: {"version":1, "glossary_path", "exists", "term_count",
           "duplicate_terms", "conflicting_definitions"}
  K5 INVARIANT: read-only; never mutates the glossary file
```

## K5 Source-Grep Test Coverage (8 tests)

`tests/test_k5_emitters.py:TestK5BoundaryPhase07`:

| Test method | Target | Verification |
|---|---|---|
| test_K5_handler_cmd_transcribe_lint | `inspect.getsource(cmd_transcribe_lint)` | no forbidden literal |
| test_K5_handler_cmd_mode_signals | `inspect.getsource(cmd_mode_signals)` | no forbidden literal |
| test_K5_handler_cmd_schedule_suggest | `inspect.getsource(cmd_schedule_suggest)` | no forbidden literal |
| test_K5_handler_cmd_glossary_audit | `inspect.getsource(cmd_glossary_audit)` | no forbidden literal |
| test_K5_module_transcribe_lint | `agent/transcribe_lint.py` file content | no forbidden literal |
| test_K5_module_mode_signals | `agent/mode_signals.py` file content | no forbidden literal |
| test_K5_module_schedule_suggestion | `agent/schedule_suggestion.py` file content | no forbidden literal |
| test_K5_module_glossary_audit | `agent/glossary_audit.py` file content | no forbidden literal |

`FORBIDDEN_LITERALS = ("summary.md", "plan.md", "schedule.json")` — failing this assertion is a phase-blocking error.

## Decisions Made

See `key-decisions:` frontmatter for the 4 design decisions made during execution. Notable:

- **CJK bigram extraction over jieba** — Plan code originally used `_CJK_TOKEN_RE = re.compile(r"[一-鿿]{2,}")` which is greedy; CJK has no whitespace, so the regex matches ENTIRE CJK runs as single tokens. Test 12 failed because '迅练' was never an extracted token (it was inside the run '我刚才说的是迅练而不是别的'). Switched to overlapping 2-char bigram windows from each CJK run. 2-char words dominate Modern Mandarin (~70%), so bigrams catch most real ASR substitution targets. The freq-ratio 5x threshold + sparse-threshold 3 keeps false-positives low. No new pip dep.
- **W2 amendment cross-reference creates 2 grep hits intentionally** — plan acceptance criteria expected `grep -c "v1.1 opt-in marker + 4 K5 emitters" CLAUDE.md` to return 1, but the W2 amendment EXPLICITLY references the new section by its full heading name in a forward-pointer bullet. So 2 hits are correct (1 reference + 1 heading). Both insertions exist; this is desired documentation UX.
- **K5 source-grep test uses repo-root resolution for module paths** — `Path(__file__).parent.parent / module_path` instead of relying on `os.getcwd()`, so the test passes regardless of where pytest/unittest is invoked from (worktree, main repo, CI runner).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] CJK regex matched whole runs (greedy) instead of word-level tokens — Test 12 fails to extract '迅练'**

- **Found during:** Task 1 verification (`python -m unittest tests.test_transcribe_lint.test_12_homophone_cluster_pinyin_match`)
- **Issue:** Plan code used `_CJK_TOKEN_RE = re.compile(r"[一-鿿㐀-䶿]{2,}")` to extract CJK tokens. Without whitespace boundaries (Chinese has none), the regex matched ENTIRE CJK runs. So in `"我刚才说的是迅练而不是别的"`, the only extracted token was the whole 12-char string — '迅练' (the actual ASR typo) was never a candidate for homophone lookup. Test 12 failed: `0 != 1` (expected exactly 1 homophone_cluster warning for '迅练', got 0).
- **Fix:** Refactored `_extract_cjk_tokens` to extract overlapping 2-char bigrams from each CJK run. Covers ~70% Modern Mandarin vocabulary (2-char words dominate). Freq-ratio threshold (5x) + sparse-threshold (3) keep signal high despite the wider candidate net. No new dep needed (jieba would be ~30MB+).
- **Files modified:** `agent/transcribe_lint.py:_extract_cjk_tokens` only
- **Verification:** Test 12 + remaining 11 tests all PASS after refactor; K5 source-grep still PASSES (no forbidden literal added).
- **Committed in:** `673333e` (Task 1 commit includes the bigram fix)

**2. [Rule 1 - Bug] W2 amendment cross-reference creates 2 grep hits, but plan acceptance expected 1**

- **Found during:** Task 3 verification (`grep -c "v1.1 opt-in marker + 4 K5 emitters" CLAUDE.md` returned 2)
- **Issue:** Plan acceptance criterion `grep -c "v1.1 opt-in marker + 4 K5 emitters" CLAUDE.md` returns 1 — but the W2 amendment instructions in Step 5b told us to add a forward-pointer bullet that EXPLICITLY mentions the new section's full heading. So the criterion as written is internally inconsistent: the W2 fix necessarily produces 2 hits.
- **Fix:** Documented as desired UX. Both occurrences are correct (one cross-reference + one heading). The intent of the criterion was "the heading exists" — and it does (line 1092). The W2 cross-reference at line 167 is a feature, not a bug.
- **Files modified:** None (CLAUDE.md is correct as-is)
- **Verification:** `grep -n "v1.1 opt-in marker + 4 K5 emitters" CLAUDE.md` reports both expected lines (167 = forward-pointer; 1092 = heading).
- **Committed in:** N/A — no source change; documented here per Rule 1.

---

**Total deviations:** 2 (1 Rule 1 bigram refactor — necessary for Test 12 to pass; 1 Rule 1 documented plan-spec inconsistency about grep count).
**Impact on plan:** Zero functional impact. The bigram refactor preserves K5 boundary, makes pypinyin actually useful, and uses no new deps. The grep-count clarification is a documentation note about CLAUDE.md being more thorough than the plan acceptance literally specified.

## Issues Encountered

- **Worktree initially based on `08a79f4` (pre-v1.1 codebase) instead of expected `69c99e3` (post-Wave-1 base)** — Resolved at execution start by `git reset --hard 69c99e31bb5e9708592d69086d8d594abc9dfac8`. The `<worktree_branch_check>` block in the executor prompt explicitly handled this case.
- **Smoke test (`mode_signals output/BV132wizyEEB/paragraphs.json --out ...`) failed with FileNotFoundError** — Reason: this worktree's `output/` directory doesn't contain the actual archive files (only the `.token_budget.json` baselines were force-added in Plan 01; the archives themselves are gitignored in this worktree). Smoke test on real archive is informational per plan output spec; the unit tests (`tests/test_mode_signals.py:M1-M10`) verify schema correctness on synthetic data, which is sufficient. The D-29 replay gate (which DOES run on the main repo's `output/` via `--output-dir`) passes 33/0/30, demonstrating that the `mode_signals` import path doesn't break v1.0 byte-equal output.

## Authentication Gates

None — no external services or APIs touched in this plan. pypinyin install was a one-time `pip install` (user-install path on zh-CN Windows due to read-only conda site-packages); after install, all module loads work without network access.

## Self-Check

### Files exist
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\agent\transcribe_lint.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\agent\mode_signals.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\agent\schedule_suggestion.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\agent\glossary_audit.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\tests\test_transcribe_lint.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\tests\test_mode_signals.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\tests\test_schedule_suggestion.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\tests\test_glossary_audit.py` ✓ FOUND
- `D:\gxy_code\videoSummary\.claude\worktrees\agent-a1705da08a09bc9cc\tests\test_k5_emitters.py` ✓ FOUND

### Commits exist (verified via `git log --oneline | grep`)
- `673333e` ✓ FOUND (Task 1: requirements + transcribe_lint + 12 tests)
- `00f0b65` ✓ FOUND (Task 2: 3 K5 emitters + 20 tests)
- `19e06c2` ✓ FOUND (Task 3: CLI wiring + K5 source-grep tests + CLAUDE.md)

### CLAUDE.md insertions
- Line 1092: `## v1.1 opt-in marker + 4 K5 emitters (Phase 07)` heading ✓ FOUND
- Line 167: `queue` subcommand bullet in Phase 6 multi-terminal section ✓ FOUND

### D-29 gate
- `python -m scripts.replay_v10_archives --output-dir D:/gxy_code/videoSummary/output` → `33 PASS / 0 FAIL / 30 SKIP` ✓ PASSED

## Self-Check: PASSED

## Threat Flags

None — this plan introduces zero new network endpoints, auth paths, file access patterns, or schema changes at trust boundaries. The 4 new emitter modules are pure functions with explicit input/output contracts; their CLI wrappers all use `_validate_out_path` (which rejects paths with CJK chars or symlinks per Phase 4 precedent) and `write_json_atomic` (Phase 2 RES-03/04 pattern). pypinyin is a pure-Python lookup table dep with no native code or network access.

## Known Stubs

- **`agent/glossary_audit.py`** — Phase 07 ships a STUB that parses H2 anchors and reports duplicates. Phase 08 TEACH-A3 will plug in cross-summary frequency tracking. The schema is forward-compat: extra keys can be added without breaking Phase 08 readers; existing keys (`version`, `glossary_path`, `exists`, `term_count`, `duplicate_terms`, `conflicting_definitions`) are stable. Test G4 asserts the schema-stable shape.
- **homophone_cluster on real ASR data** — informational. The synthetic Test 12 is the canonical proof-of-work; running on real archives requires the archive files to be present in the worktree (this worktree's `output/` is mostly empty per Plan 01 SUMMARY note). Phase 08's L2 prompt will exercise this on real warnings.

## Next Plan Readiness

Phase 08 (Prompt-driven v1.1 features) and Phase 09 (verifier) can now consume:

- `output/<slug>/transcribe_warnings.json` — read by CORR-01b L2 prompt for context-aware corrections
- `output/<slug>/mode_signals.json` — read by Phase 09 verifier for plan-vs-content cross-checks
- `output/<slug>/schedule_suggestion.json` — read by Claude when authoring the final schedule artifact
- `output/_glossary.md` audit — read by Phase 08 TEACH-A3 to detect cross-summary glossary drift

All 4 emitters are CLI-callable with stable schemas locked in `.planning/phases/07-warm-up-k5-emitters-d-29-foundation/07-03-PLAN.md` interfaces section. K5 boundary is statically asserted by `tests/test_k5_emitters.py` — adding new K5 emitters in Phase 08/09 should follow the same pattern (register in FORBIDDEN_LITERALS check by adding new test_K5_handler_* + test_K5_module_* pair).

---
*Phase: 07-warm-up-k5-emitters-d-29-foundation*
*Plan: 03*
*Completed: 2026-05-03*
