# Phase 09: Correctness automation — verifier subagent + auto-rewrite - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Smart-discuss accepted all defaults — D-02 三层校验 (user铁律) governs scope; ROADMAP/PITFALLS/research SUMMARY have all caps locked

<domain>
## Phase Boundary

Land the highest-token-cost layer last (after Phase 07/08 production data informs per-layer cap tuning):

- **CORR-03a**: `python -m agent.tools summary_lint <slug>/summary.md` — mechanical format-spec checker (4 invariants from Phase 5 + 5th trace-token invariant added Phase 08), produces `summary_lint.json`. K5 boundary: read-only, NEVER edits summary.md.
- **CORR-03b**: Phase 7.5 verifier subagent — `Task(subagent_type="general-purpose")` invocation in `/summarize-video` workflow, scope-locked to format-spec + mode rules + citation validity + glossary consistency (NOT pedagogical judgment). Outputs `<slug>-REVIEW.md` with critical/warning/info findings. `VIDEOSUMMARY_SKIP_REVIEWER=1` env var degrades the entire phase.
- **CORR-03c**: Delta auto-rewrite cycle — only `critical` severity findings trigger rewrite; max-1-rewrite hard cap; pre-rewrite backup to `summary.md.pre-review`; if post-rewrite review still finds critical issues → write `<slug>-UNRESOLVED.md` (人工介入清单), ship summary as-is.

**3 requirements**: CORR-03a, CORR-03b, CORR-03c.

**Phase 09 Cannot Run Before Phase 08** because:
- Verifier checks Phase 08's format-spec extensions (5th invariant: trace tokens)
- Verifier validates Phase 08's inline trace tokens (CORR-02)
- Verifier validates Phase 08's glossary consistency (TEACH-A3)
- Verifier reads `transcribe_lint_warnings.json` (Phase 07 CORR-01a)

</domain>

<decisions>
## Implementation Decisions

### Locked from REQUIREMENTS.md + research SUMMARY.md (D-02 governs)

**CORR-03a — `summary_lint` mechanical CLI**:
- Path: `python -m agent.tools summary_lint <slug>/summary.md` → writes `output/<slug>/summary_lint.json`
- Checks: 4 format-spec invariants from Phase 5 (timestamp [HH:MM:SS] / explicit code-fence language / relative frame paths / 第二人称 imperative) + 5th invariant from Phase 08 (trace token after every load-bearing claim)
- Additional checks: citation eligibility (REQUIRED/FORBIDDEN/OPTIONAL) + glossary term consistency
- K5 boundary: source-grep static assertion forbids `summary.md` write patterns (only reads)
- Output schema: `{"version": 1, "claims_total": N, "claims_with_trace": N, "claims_without_trace": [{"line", "snippet"}], "format_violations": [...], "citation_eligibility_violations": [...], "glossary_inconsistencies": [...], "uncertainty_markers_count": N}`

**CORR-03b — Phase 7.5 verifier subagent**:
- Invocation: `Task(subagent_type="general-purpose", prompt=<verifier_prompt>)` from inside `/summarize-video` workflow Phase 7.5
- Reads: summary.md + paragraphs.json + plan.md + `transcribe_lint_warnings.json` + `summary_lint.json` + ≤ 10 frames sampled from `claims_without_trace`
- **Scope LOCK** (CRITICAL — anti-hallucination per P-03):
  - REQUIRED scope: format-spec 4 invariants + 5th trace invariant + plan.md mode rules + citation timestamp validity + glossary term consistency
  - FORBIDDEN scope: any "this explanation is unclear" / "this should be rephrased" / "tone could be better" pedagogical critique
- Output: `output/<slug>/<slug>-REVIEW.md` with critical/warning/info three-tier findings (each finding cites WHICH claim/line + EVIDENCE not subjective opinion)
- Token budget cap: ≤ 10 frames per run; instrument first 2 runs with token-cost logging
- Degrade env: `VIDEOSUMMARY_SKIP_REVIEWER=1` — entire Phase 7.5 silently skipped (low-quota fallback)
- **NOT** a registered `.claude/agents/*.md` subagent — kept inline; promotion deferred to v1.2 if signal warrants (per research SUMMARY.md "Defer (v2+)")

**CORR-03c — Delta auto-rewrite (max-1)**:
- Trigger: only `critical` severity findings (warning/info → REVIEW.md only, no rewrite)
- Rewrite type: delta (targeted edits to flagged sentences/paragraphs, NOT full re-write)
- Pre-rewrite backup: copy summary.md → `output/<slug>/summary.md.pre-review` BEFORE rewrite
- Hard cap: 1 rewrite per `/summarize-video` invocation, recorded as `rewrite_cycle_completed` event in `state.jsonl`
- Post-rewrite re-verification: re-run verifier subagent ONCE
  - If post-rewrite review = clean OR only warning/info → ship rewritten summary, done
  - If post-rewrite review still has critical → write `output/<slug>/<slug>-UNRESOLVED.md` (人工介入清单), ship summary as-is, exit cleanly
- NO 2nd automatic rewrite

### Claude's Discretion

- Specific verifier prompt wording (CLAUDE.md Phase 7.5 section — Claude writes prompt achieving locked scope)
- summary_lint.py implementation algorithm (regex / line-by-line scan / AST — Claude picks pragmatic approach)
- REVIEW.md format detail (markdown table vs structured list — Claude picks readable form)
- Exact frame sampling strategy from claims_without_trace (random / first-N / proximity-weighted — Claude decides)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/_v11.py` — extend V11_FEATURES with 2 new flags (`summary_lint_enabled`, `verifier_phase_75`) for opt-in gating; OR fold into existing flags. Probably no new flags needed if Phase 7.5 is implicit when other v1.1 features active.
- `agent/_lock.py` — no new lock needed (per-slug `.resume.lock` covers REVIEW.md + UNRESOLVED.md writes)
- `agent/io.py.write_json_atomic()` — for `summary_lint.json` atomic write
- `agent/glossary.py` (Phase 08) — verifier reads `output/_glossary.md` for consistency checks
- `agent/transcribe_lint.py` (Phase 07) — verifier reads `transcribe_lint_warnings.json`
- `state.jsonl` event log — add `rewrite_cycle_completed` event type
- Phase 07 K5 source-grep test pattern (`tests/test_k5_emitters.py`) — extend with `cmd_summary_lint` boundary assertion

### Established Patterns
- 4 K5 emitters precedent (Phase 07) — `cmd_summary_lint` mirrors that shape (read-only, statically-asserted no-write to decision artifacts)
- `Task(subagent_type=...)` invocation — Claude Code primitive; verifier uses general-purpose since no in-repo precedent for registered subagents
- CLAUDE.md prompt-engineering decision center — Phase 7.5 verifier prompt + scope lock embedded in CLAUDE.md (NOT a separate prompt file)
- Atomic JSON write + state.jsonl event log (Phase 2) for new artifacts

### Integration Points
- `agent/tools.py` — add `cmd_summary_lint` subparser (new K5 emitter)
- `agent/summary_lint.py` (NEW) — module impl
- CLAUDE.md — extend `/summarize-video 完整工作流` with Phase 7.5 verifier sub-step + verifier prompt block
- `output/<slug>/summary_lint.json` (NEW sibling artifact)
- `output/<slug>/<slug>-REVIEW.md` (NEW per-slug artifact)
- `output/<slug>/<slug>-UNRESOLVED.md` (NEW per-slug fallback)
- `output/<slug>/summary.md.pre-review` (NEW backup file)
- `output/<slug>/.token_budget.json` (Phase 07 PRE-V11-03 baseline reference) — Phase 09 verification asserts ≤ 2x
- `state.jsonl` — new event types: `summary_lint_run`, `verifier_run`, `rewrite_cycle_completed`
- Tests — `tests/test_summary_lint.py` (new), extend `tests/test_k5_emitters.py` for boundary assertion

</code_context>

<specifics>
## Specific Ideas

- **summary_lint.json schema concrete proposal**:
  ```json
  {
    "version": 1,
    "schema_version": 1,
    "summary_path": "output/BV132wizyEEB/summary.md",
    "checked_at": "2026-05-03T...",
    "format_invariants": {
      "timestamp_format": {"violations": []},
      "code_fence_language": {"violations": []},
      "relative_frame_paths": {"violations": []},
      "second_person_imperative": {"violations": []},
      "trace_after_claim": {"violations": [{"line": 42, "snippet": "..."}]}
    },
    "citation_stats": {
      "total_claims": 87,
      "claims_with_trace": 79,
      "claims_without_trace": [{"line": 42, "snippet": "..."}],
      "trace_density": 0.91,
      "uncertainty_markers": 3
    },
    "citation_eligibility_violations": [{"line": 105, "section": "TL;DR", "reason": "FORBIDDEN — TL;DR contains [seg_*.jpg @ ...] citation"}],
    "glossary_inconsistencies": [{"term": "LoRA", "summary_definition": "...", "glossary_definition": "...", "drift_detected": true}]
  }
  ```
- **Verifier prompt scope lock template** (CLAUDE.md insertion):
  ```markdown
  你是 summary 质量复审 agent。仅在以下 4 类问题里挑 critical/warning/info：
  1. format-spec 4 invariants violation
  2. plan.md mode rules violation
  3. inline trace token timestamp invalid (timestamp 不存在于 paragraphs.json)
  4. glossary term consistency drift

  **禁止做** pedagogical judgment ("这段说不清楚" / "这里应该改写" / "语气不好" / "解释太啰嗦")
  **必须**给 EVIDENCE (which line / which claim / which paragraph timestamp), 不要主观意见
  ```
- **CORR-03c rewrite-cycle event semantics**:
  ```json
  {"event": "rewrite_cycle_completed", "ts": "...", "slug": "BVxxx", "critical_count_pre": 3, "critical_count_post": 0, "rewrite_path": "summary.md.pre-review", "duration_ms": 12345}
  ```
- **Token budget assertion implementation**:
  - End-to-end script: run `/summarize-video` on 1 short test video with all v1.1 features active
  - Compare measured token cost vs Phase 07 baseline `.token_budget.json` for same mode
  - Assert ≤ 2x baseline; FAIL phase if exceeded
  - This is a manual verification (Phase 09 verifier subagent + Phase 07/08 features = needs real LLM call to measure)

</specifics>

<deferred>
## Deferred Ideas

- **Diff-based reviewer re-review** (defer to v1.2 once production token-cost data exists per research SUMMARY.md)
- **`.claude/agents/gsd-summary-verifier.md` registered subagent** (defer to v1.2 once usage signal warrants — see smart-discuss decision)
- **2-rewrite cycles** (defer — locked at max-1 per CORR-03c must-haves + research SUMMARY.md "Self-Refine empirical max-1 cap")
- **Pedagogical judgment by verifier** (PERMANENTLY out-of-scope per REQUIREMENTS.md "Out of Scope: Reviewer 做 pedagogical judgment")
- **Auto-promote findings to plan.md** (out-of-scope; verifier writes REVIEW.md only)

</deferred>
