---
status: partial
phase: 09-correctness-automation-verifier-subagent-auto-rewrite
source: [09-VERIFICATION.md]
started: "2026-05-03T22:00:00.000Z"
updated: "2026-05-03T22:00:00.000Z"
---

## Current Test

[awaiting human testing — SC#4 token budget + Phase 7.5 verifier live-runtime test]

## Tests

### 1. SC#4 — End-to-end token budget ≤ 2x v1.0 baseline

expected: From a fresh Claude Code session, invoke `/summarize-video` on 1 short test video (e.g., a 5-10 min B站 / 抖音 video). BEFORE invocation, set the slug's `.v11_features.json` marker enabling ALL 15 v1.1 flags (Phase 07 → Phase 09). Measure total token cost via Claude Code session telemetry OR `state.jsonl` event aggregation. Compare against the 3 Phase 07 baselines in `output/<slug>/.token_budget.json` (replicate-guide / interview-distillation / extension-applications). Assert measured cost ≤ 2× the baseline for the same mode. **Per-layer cap verification**: CORR-01 L3 ≤ 5 frames/warning AND ≤ 10 entries triggering L3; CORR-03 verifier ≤ 10 frames/run; rewrite ≤ 1 cycle. Documented in CLAUDE.md `## v1.1 校对自动化 (Phase 09) → Token budget 校验` section.
result: [pending]

### 2. Phase 7.5 verifier subagent live-runtime test

expected: During Test 1 (or in a separate session), confirm Claude Code spawns `Task(subagent_type="general-purpose")` for Phase 7.5 verifier. Read the resulting `output/<slug>/<slug>-REVIEW.md` and verify:
- Findings are scope-locked (only format-spec / mode rules / citation validity / glossary consistency)
- ZERO pedagogical critique (no "这段说不清楚" / "这里应该改写" / "语气不好" / "解释太啰嗦" / "新读者可能看不懂" / "可以加一个例子" or similar)
- Critical findings (if any) trigger ONE delta rewrite + write `summary.md.pre-review` backup
- If post-rewrite still has critical → write `<slug>-UNRESOLVED.md` and ship summary as-is (no 2nd rewrite)
- `state.jsonl` records `verifier_run` + (if rewrite) `rewrite_cycle_completed` events
result: [pending]

### 3. Append "## Manual Gate Results" section to `09-02-SUMMARY.md`

expected: After Tests 1+2 complete, append a section to `09-02-SUMMARY.md` documenting:
- Test video slug + duration + mode
- Measured token cost vs baseline (PASS if ≤ 2x; FAIL otherwise)
- Verifier behavior (scope-lock honored / pedagogical findings count / rewrite cycle outcome)
- Confirmation that SC#4 is satisfied (or exact failure mode if not)
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

- SC#4 token budget end-to-end gate: Python orchestrator cannot auto-test `/summarize-video` invocation (it's a Claude slash command, not a CLI). User must run real Claude session to measure.
- Phase 7.5 verifier subagent live-runtime check: requires Claude Code's runtime `Task` primitive — verifier subagent semantics validated only when actually invoked. First 1-2 production runs are the implicit test.

## Resolution

Run `/gsd-verify-work 09` after manual testing on a real video to mark items resolved.

If token budget > 2x → file UAT failure → run `/gsd-debug` to investigate which layer overflowed (likely CORR-03 verifier if ≤ 10 frames cap not enforced, or rewrite-cycle if > 1).

If verifier produces pedagogical findings → revise CLAUDE.md FORBIDDEN list with the specific phrases that leaked through; re-test.
