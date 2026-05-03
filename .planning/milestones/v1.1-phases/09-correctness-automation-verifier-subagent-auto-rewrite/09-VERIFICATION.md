---
phase: 09-correctness-automation-verifier-subagent-auto-rewrite
verified: 2026-05-03T00:00:00Z
status: human_needed
score: 3/4 must-haves verified (SC#4 requires manual gate)
overrides_applied: 0
human_verification:
  - test: "End-to-end /summarize-video on a marked slug — token budget assertion"
    expected: "output/<slug>/.token_budget.json shows total token spend ≤ 2x Phase 07 baseline for the same mode (replicate-guide / interview-distillation / extension-applications)"
    why_human: "Cannot be run by automated orchestrator — requires real Claude session executing /summarize-video <url> end-to-end through Phase 8 + Phase 7.5 with all 15 v1.1 features active. Pure Python unit tests cannot simulate the LLM token cost of the Task(subagent_type='general-purpose') verifier invocation. Procedure documented verbatim in CLAUDE.md `## v1.1 校对自动化 (Phase 09) → Token budget 校验 (P-09, end-to-end manual gate)`."
  - test: "Phase 7.5 verifier subagent live-runtime scope-lock effectiveness"
    expected: "First ~2 verifier invocations on real summary.md files produce <slug>-REVIEW.md with ZERO pedagogical findings (no '这段说不清楚' / '这里应该改写' / etc)"
    why_human: "Task(subagent_type='general-purpose', prompt=<verifier_prompt>) runtime cannot be unit-tested — it requires Claude Code's Task primitive. The FORBIDDEN scope lock's effectiveness can only be empirically validated. If any pedagogical critique leaks, tighten FORBIDDEN list with the leaked phrase as new literal."
---

# Phase 09: Correctness automation — verifier subagent + auto-rewrite Verification Report

**Phase Goal:** Land highest-token-cost layer last. Mechanical `summary_lint` checks format-spec + traces + glossary; Phase 7.5 verifier subagent (`Task(general-purpose)`) does scope-locked correctness review; critical findings auto-trigger ONE delta rewrite with backup; max-1 cap enforced; UNRESOLVED fallback for unfixable.
**Verified:** 2026-05-03T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (4 ROADMAP Success Criteria)

| #   | Truth (ROADMAP SC)                                                                                          | Status     | Evidence                                                                                                                                                                                                                                                                                                                                                                            |
| --- | ----------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `summary_lint` mechanical checker (K5) — produces `summary_lint.json`; NEVER edits summary.md             | ✓ VERIFIED | `agent/summary_lint.py` (438 LOC) implements 5 format invariants + citation_stats + citation_eligibility_violations + glossary_inconsistencies. `cmd_summary_lint` in `agent/tools.py:1527` wires the CLI with `is_v11_enabled('summary_lint')` gate (WR-01 fix). 2 K5 source-grep tests in `tests/test_k5_emitters.py` (test_K5_handler_cmd_summary_lint + test_K5_module_summary_lint) statically assert NO write-patterns target summary.md/plan.md/schedule.json. CLI smoke verified: `python -m agent.tools summary_lint --help` exits 0. |
| 2   | Phase 7.5 verifier subagent scope-locked, never pedagogical (P-03)                                        | ✓ VERIFIED | CLAUDE.md `## v1.1 校对自动化 (Phase 09)` (line 1417) contains verbatim Verifier Prompt with REQUIRED scope (4 categories: format-spec / mode rules / citation timestamp / glossary) and FORBIDDEN scope including 6 literal pedagogical phrases ("这段说不清楚" / "这里应该改写" / "语气不好" / "解释太啰嗦" / "新读者可能看不懂" / "可以加一个例子" — all 1 grep hit each). Phase 7.5 hook gates on `is_v11_enabled('verifier_phase_75')` AND `VIDEOSUMMARY_SKIP_REVIEWER != '1'` AND summary_lint.json exists (line 1444-1448 + 1745-1747). VIDEOSUMMARY_SKIP_REVIEWER documented in 4 places (≥3 required). |
| 3   | Max-1-rewrite cap; pre-rewrite backup (P-03) — only critical triggers; pre-review backup; UNRESOLVED.md fallback | ✓ VERIFIED | CLAUDE.md `### CORR-03c：max-1 delta rewrite cycle` documents 5 steps including pre-rewrite backup `summary.md.pre-review`, NO 2nd automatic rewrite (2 grep hits), `<slug>-UNRESOLVED.md` fallback. `agent/verifier_events.py` (196 LOC) provides `emit_verifier_run` / `emit_rewrite_cycle_completed` (with `unresolved_path` field defensively dropped when critical_count_post == 0) / `build_unresolved_md` template renderer + 3 constants (REVIEW_FILENAME_TEMPLATE / UNRESOLVED_FILENAME_TEMPLATE / PRE_REVIEW_BACKUP_SUFFIX). 9 unit tests in `tests/test_verifier_events.py` PASS (≥6 required) covering clean ship + unresolved + UTF-8 CJK round-trip. `rewrite_cycle_completed` event referenced 6 times in CLAUDE.md (≥3 required). |
| 4   | Token budget ≤ 2x v1.0 baseline (P-09) — END-TO-END manual gate                                            | ? UNCERTAIN — needs human | Per ROADMAP SC#4: "MANUAL GATE — needs Claude session, flag as `human_needed`". CLAUDE.md `### Token budget 校验 (P-09, end-to-end manual gate)` (line 1601-1609) documents the 5-step manual procedure verbatim. Cannot be auto-tested by Python orchestrator — requires real Claude session running /summarize-video end-to-end. Both 09-02-SUMMARY.md "Known Stubs" section AND this VERIFICATION.md `human_verification` block flag this for user verification. |

**Score:** 3/4 truths verified by automation; 1/4 (SC#4) flagged human_needed by ROADMAP design.

### Required Artifacts

| Artifact                                            | Expected                                                                                  | Status     | Details                                                                                                                                                                                                                            |
| --------------------------------------------------- | ----------------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent/summary_lint.py`                             | Pure-stdlib K5 emitter; ≥200 lines; lint_summary + LINT_FILENAME                          | ✓ VERIFIED | 438 LOC; exports `lint_summary` + `LINT_FILENAME = "summary_lint.json"`. WR-01/WR-02/WR-03/WR-04 review fixes applied (REVIEW-FIX status: all_fixed). Module is read-only (no write_text/os.replace/_atomic_write to decision artifacts). |
| `agent/verifier_events.py`                          | 3 helpers + 3 constants; ≥100 lines                                                       | ✓ VERIFIED | 196 LOC; exports `emit_verifier_run`, `emit_rewrite_cycle_completed`, `build_unresolved_md`, `REVIEW_FILENAME_TEMPLATE`, `UNRESOLVED_FILENAME_TEMPLATE`, `PRE_REVIEW_BACKUP_SUFFIX`. Imports direct from `agent.state` (avoids circular import via agent.tools). |
| `agent/tools.py` — cmd_summary_lint handler         | Mirrors cmd_transcribe_lint shape with is_v11_enabled gate                                | ✓ VERIFIED | Handler at line 1527 includes `is_v11_enabled(slug_dir, "summary_lint")` defense-in-depth gate (WR-01 fix), lazy import of `lint_summary` + `LINT_FILENAME`, `_validate_out_path`, `write_json_atomic`, `_log`, `_emit_event`. Subparser at line 1801 + dispatch entry at line 1852. |
| `agent/_v11.py` — V11_FEATURES extended 13 → 15     | Adds `summary_lint` + `verifier_phase_75`                                                 | ✓ VERIFIED | Tuple has 15 entries; `summary_lint` (line 53) + `verifier_phase_75` (line 54) both present. `set_v11_marker(['summary_lint', 'verifier_phase_75'])` accepts both flags (verified live).                                              |
| `tests/test_summary_lint.py`                        | ≥12 unit tests covering all invariants + edge cases                                       | ✓ VERIFIED | 15 tests PASS (302 LOC); covers 5 format invariants + citation_stats + citation eligibility (TL;DR + prelude FORBIDDEN) + glossary drift + glossary_path=None + uncertainty markers + empty-summary edge case + schema version pin + UTF-8 CJK round-trip. |
| `tests/test_verifier_events.py`                     | ≥6 unit tests                                                                             | ✓ VERIFIED | 9 tests PASS (245 LOC); covers emit_verifier_run JSONL shape + emit_rewrite_cycle_completed clean ship + unresolved + defensive drop + build_unresolved_md with findings + empty + UTF-8 CJK round-trip + constants exported.    |
| `tests/test_k5_emitters.py` — 2 new tests           | test_K5_handler_cmd_summary_lint + test_K5_module_summary_lint using write-pattern regex  | ✓ VERIFIED | Both tests present at lines 174-204; use `_WRITE_PATTERNS_FORBIDDEN` regex (mirror Phase 08-01 glossary.py exception); also assert `plan.md` and `schedule.json` literals are absent from agent/summary_lint.py via `assertNotIn`. All tests PASS. |
| `CLAUDE.md` — `## v1.1 校对自动化 (Phase 09)` H2  | New ~280-line H2 with verbatim verifier prompt + scope lock + UNRESOLVED.md template + state.jsonl event types | ✓ VERIFIED | Section starts at line 1417; +237 lines added in commit `7b46e09`. Contains 降级开关 paragraph + CORR-03a CLI doc + CORR-03b Verifier Prompt verbatim + CORR-03c rewrite protocol + UNRESOLVED.md template + Token budget P-09 manual gate + 3-event-type table + multi-terminal lock note. |
| `CLAUDE.md` — `### Phase 7.5: 校对自动化` H3 hook  | Triple-gate hook in /summarize-video workflow                                             | ✓ VERIFIED | Hook starts at line 1739 (between Phase 7 line 1522 and Phase 8 line 1529). Triple-gate blockquote: marker + env-degrade + summary_lint.json prereq. 4 numbered steps + max-1 hard-cap reminder + cross-ref to canonical spec.   |

### Key Link Verification

| From                                                       | To                                                       | Via                                                              | Status     | Details                                                                                                                                                |
| ---------------------------------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `cmd_summary_lint(args)`                                  | `agent.summary_lint.lint_summary()`                      | Lazy import inside handler                                       | ✓ WIRED    | Line 1542: `from agent.summary_lint import lint_summary, LINT_FILENAME` followed by `result = lint_summary(...)` at line 1559                          |
| `cmd_summary_lint(args)`                                  | `is_v11_enabled(slug_dir, "summary_lint")`               | Lazy import + gate-check                                         | ✓ WIRED    | Line 1543: `from agent._v11 import is_v11_enabled` + line 1551: `if not is_v11_enabled(slug_dir, "summary_lint"): _log(...); return` (WR-01 fix)        |
| `cmd_summary_lint(args)`                                  | `_emit_event(slug_dir, "summary_lint", "completed", ...)` | `agent.tools._emit_event` helper                                 | ✓ WIRED    | Line 1577: `_emit_event(slug_dir, "summary_lint", "completed", details={...})` writes to state.jsonl                                                   |
| Phase 7.5 hook in CLAUDE.md                                | `Task(subagent_type='general-purpose', prompt=...)`      | Verbatim markdown blockquote in /summarize-video workflow        | ✓ WIRED    | Line 1751: `Task(subagent_type="general-purpose", description="Phase 7.5 summary verifier (CORR-03b scope-locked)", prompt=<下方 Verifier Prompt 段>)` |
| `agent.verifier_events.emit_rewrite_cycle_completed`      | state.jsonl `rewrite_cycle_completed` event              | `agent.state.append_event`                                       | ✓ WIRED    | Line 124: `append_event(state_log, stage="rewrite_cycle", status="completed", details=details)`                                                       |
| CLAUDE.md `### 格式锁定` block                             | Phase 09 H2 section reference                            | 1-line cross-ref note                                            | ✓ WIRED    | Cross-ref at line 279: "**机械校验**：以上 4+1 项不变量由 `python -m agent.tools summary_lint <slug>/summary.md` 静态检查（CORR-03a，Phase 09 Plan 09-01）..." |

### Data-Flow Trace (Level 4)

| Artifact                             | Data Variable          | Source                                              | Produces Real Data | Status      |
| ------------------------------------ | ---------------------- | --------------------------------------------------- | ------------------ | ----------- |
| `summary_lint.json` (sidecar)         | `result` dict          | `lint_summary(summary_path, glossary_path)`         | Yes — actual scan of summary lines | ✓ FLOWING   |
| `state.jsonl` summary_lint event     | `details` dict         | `_emit_event(slug_dir, "summary_lint", ...)`         | Yes — actual claim counts + violation counts | ✓ FLOWING   |
| `state.jsonl` verifier_run event     | `severity_counts` dict | `emit_verifier_run(severity_counts={...})`           | Yes — caller-supplied counts from Task subagent | ✓ FLOWING   |
| `state.jsonl` rewrite_cycle event    | `details` dict         | `emit_rewrite_cycle_completed(...)`                  | Yes — caller-supplied pre/post counts + paths | ✓ FLOWING   |
| `<slug>-UNRESOLVED.md` (caller-write) | rendered markdown string | `build_unresolved_md(slug, critical_findings)`       | Yes — actual finding location/evidence/rule | ✓ FLOWING   |

### Behavioral Spot-Checks

| Behavior                                                           | Command                                                                                          | Result                            | Status |
| ------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ | --------------------------------- | ------ |
| `summary_lint` CLI is wired                                        | `python -m agent.tools summary_lint --help`                                                      | Exit 0; usage shows summary_path positional + --glossary-path optional | ✓ PASS |
| `V11_FEATURES` has 15 entries with both Phase 09 flags             | `python -c "from agent._v11 import V11_FEATURES; assert 'summary_lint' in V11_FEATURES; assert 'verifier_phase_75' in V11_FEATURES; assert len(V11_FEATURES) == 15"` | OK (no AssertionError); printed `V11_FEATURES OK 15` | ✓ PASS |
| `set_v11_marker` accepts new flags                                 | `python -c "from agent._v11 import set_v11_marker; ...; set_v11_marker(td, ['summary_lint', 'verifier_phase_75'])"` | No ValueError; printed `marker accepts new flags` | ✓ PASS |
| `agent/verifier_events.py` exports all 3 helpers + 3 constants     | `python -c "from agent.verifier_events import emit_verifier_run, emit_rewrite_cycle_completed, build_unresolved_md, REVIEW_FILENAME_TEMPLATE, UNRESOLVED_FILENAME_TEMPLATE, PRE_REVIEW_BACKUP_SUFFIX"` | No ImportError | ✓ PASS |
| Phase 09 unit tests pass                                           | `python -m unittest tests.test_summary_lint tests.test_verifier_events tests.test_k5_emitters tests.test_v11_marker -v` | Ran 47 tests OK | ✓ PASS |
| Full unittest suite still green                                    | `python -m unittest discover tests`                                                              | Ran 196 tests OK (skipped=1, 0 failures) | ✓ PASS |
| D-29 byte-equal regression preserved                               | `python -m scripts.replay_v10_archives --output-dir D:/gxy_code/videoSummary/output`             | 33 PASS / 0 FAIL / 30 SKIP — AUTOMATED GATE PASSED | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                                      | Status      | Evidence                                                                                                                                          |
| ----------- | ----------- | ---------------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| CORR-03a    | 09-01       | `python -m agent.tools summary_lint <slug>/summary.md` 机械式 format-spec 检查 + 引用格式 + glossary 一致性；K5 边界仅检查不改写 | ✓ SATISFIED | `agent/summary_lint.py` (438 LOC) + `cmd_summary_lint` handler + 15 unit tests + 2 K5 boundary tests + V11_FEATURES extension. CLI smoke PASS.    |
| CORR-03b    | 09-02       | Phase 7.5 verifier subagent scope-locked (format-spec + mode + citation + glossary); FORBIDDEN pedagogical critique | ✓ SATISFIED | CLAUDE.md verbatim Verifier Prompt with REQUIRED scope (4 cats) + FORBIDDEN scope (6 literal phrases). VIDEOSUMMARY_SKIP_REVIEWER documented 4×. |
| CORR-03c    | 09-02       | Critical findings auto-trigger ONE delta rewrite; max-1 cap; UNRESOLVED.md fallback                              | ✓ SATISFIED | CLAUDE.md `### CORR-03c` 5-step protocol + agent/verifier_events.py 3 helpers + 9 unit tests. "NO 2nd automatic rewrite" stated 2× in CLAUDE.md. |

No orphaned requirements. All 3 CORR-03a/b/c IDs from plans match REQUIREMENTS.md mapping (lines 92-94).

### Anti-Patterns Found

Anti-pattern scan on Phase 09 modified files (`agent/summary_lint.py`, `agent/verifier_events.py`, `agent/tools.py:1527-1584`, `CLAUDE.md` Phase 09 sections, 4 test files):

| File                          | Line  | Pattern                              | Severity | Impact                                                                                                                              |
| ----------------------------- | ----- | ------------------------------------ | -------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `agent/summary_lint.py`       | 233   | `return False` (in `_is_load_bearing`) | ℹ️ Info | Legitimate guard for image-only lines; documented intent (image-only is visual anchor not prose claim). NOT a stub.                  |
| `agent/summary_lint.py`       | 339-340 | `return []` (in `_check_glossary_consistency`) | ℹ️ Info | Legitimate graceful degrade when glossary_path is None or non-existent. Documented contract (Test 11 asserts this behavior).         |
| `agent/verifier_events.py`    | 36    | `PRE_REVIEW_BACKUP_SUFFIX = ".pre-review"` constant | ℹ️ Info | Constant used by Phase 7.5 hook caller. IN-02 review note: a `make_pre_review_backup` helper was suggested but deliberately deferred (Phase 7.5 caller will inline-rename per plan); IN-02 is INFO severity, not blocking. |

**No 🛑 blockers, no ⚠️ warnings.** Code review (09-REVIEW.md) found 0 critical + 4 warnings; all 4 warnings fixed per 09-REVIEW-FIX.md (status: all_fixed). 6 info findings explicitly deferred per `fix_scope=critical_warning`.

### Human Verification Required

Two items require human verification — both are explicitly designed as manual gates in the plan and ROADMAP:

#### 1. SC#4 Token Budget End-to-End Gate

**Test:** Pick 1 short (~5 min) test video, set `.v11_features.json` with all 15 v1.1 features active, run `/summarize-video <url>` end-to-end through Phase 8 + Phase 7.5; check `output/<slug>/.token_budget.json` against Phase 07 baseline `.token_budget.json` for the same mode (replicate-guide / interview-distillation / extension-applications).

**Expected:** Total token spend ≤ 2x baseline. If exceeded, set `VIDEOSUMMARY_SKIP_REVIEWER=1` and rerun to confirm Phase 7.5 verifier is the blow-up source.

**Why human:** The orchestrator cannot run `/summarize-video` end-to-end — it requires a real Claude session executing the multi-phase workflow with the LLM-driven Task subagent. Pure Python unit tests cannot simulate the LLM token cost. ROADMAP SC#4 explicitly marks this as `MANUAL GATE — needs Claude session, flag as human_needed`. Procedure documented verbatim in CLAUDE.md `## v1.1 校对自动化 (Phase 09) → Token budget 校验 (P-09, end-to-end manual gate)`.

#### 2. Phase 7.5 Verifier Subagent Live-Runtime Scope-Lock Effectiveness

**Test:** Run Phase 7.5 on 1-2 marked slugs by invoking `/summarize-video` (or manually trigger the Task subagent block from CLAUDE.md). Read the produced `<slug>-REVIEW.md` and confirm zero pedagogical findings (no "这段说不清楚" / "这里应该改写" / "新读者可能看不懂" / etc).

**Expected:** REVIEW.md contains only critical/warning/info findings within the 4 REQUIRED scope categories (format-spec / mode / citation timestamp / glossary). NO pedagogical critique of teaching quality, narrative flow, or chapter structure.

**Why human:** The `Task(subagent_type='general-purpose', prompt=<verifier_prompt>)` runtime cannot be unit-tested — it requires Claude Code's Task primitive. The FORBIDDEN scope lock's effectiveness can only be empirically validated by running it on real summary.md files. If any pedagogical critique leaks, the FORBIDDEN list must be tightened with the leaked phrase as a new literal.

### Gaps Summary

**No automatable gaps.** All 3 ROADMAP success criteria that CAN be auto-verified are VERIFIED:
- SC#1 (`summary_lint` mechanical checker, K5 boundary) — verified via 15 summary_lint unit tests + 2 K5 source-grep tests + CLI smoke test
- SC#2 (Phase 7.5 verifier scope-lock + FORBIDDEN list + degrade env) — verified via 16 grep checks on CLAUDE.md (all literal phrases present)
- SC#3 (max-1 rewrite cap + pre-rewrite backup + UNRESOLVED.md fallback) — verified via 9 verifier_events unit tests + 6 CLAUDE.md references to `rewrite_cycle_completed`

The single non-auto-verifiable item (SC#4 token budget end-to-end gate) is correctly flagged `human_needed` per ROADMAP design.

**Key strengths observed:**
- D-29 byte-equal regression gate STILL PASS (33/0) — Phase 09 introduces zero side-effects on v1.0 archives. Achieved via (a) opt-in `is_v11_enabled` gate on cmd_summary_lint (WR-01 defense-in-depth fix), (b) Phase 7.5 hook triple-gate (marker + env + prereq), (c) CLAUDE.md additions are documentation-only.
- Code review (09-REVIEW.md) found 0 critical + 4 warnings; all 4 fixed per 09-REVIEW-FIX.md (status: all_fixed). 6 info findings deferred with explicit dispositions.
- Test count grew 170 → 196 (+26 net): +15 summary_lint + 9 verifier_events + 2 K5 boundary = 26 new tests; existing test_v11_marker count assertion updated from 13 → 15 (consistent pattern across phases).
- K5 boundary statically asserted via 2 distinct mechanisms: literal-substring (FORBIDDEN_LITERALS) for plan.md/schedule.json + write-pattern regex (_WRITE_PATTERNS_FORBIDDEN) for summary.md (legitimate input arg).

---

_Verified: 2026-05-03T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
