---
phase: 08-writing-rules-claude-md-extensions-glossary
plan: 02
subsystem: docs
tags: [claude-md, prompt-engineering, v11-marker, format-spec, k5-boundary, opt-in]

# Dependency graph
requires:
  - phase: 07-warm-up-k5-emitters-d-29-foundation
    provides: agent/_v11.py V11_FEATURES allowlist + agent/transcribe_lint.py warnings file (Phase 07 baseline)
  - phase: 08-writing-rules-claude-md-extensions-glossary
    provides: Plan 08-01 — agent/glossary.py glossary_append CLI + V11_FEATURES extended 8 → 13 entries (5 new Phase 08 explicit names)
provides:
  - CLAUDE.md `## v1.1 自适应教学文档增强 (Phase 08)` H2 section (~270 lines, 7 sub-rules)
  - CLAUDE.md `### 格式锁定` 5th invariant (trace-token format spec, gated on `inline_trace_tokens`)
  - CLAUDE.md `## /summarize-video 完整工作流` Phase 2/6/7/8 v1.1 cross-reference hooks
affects: [09 verifier consumes the inline trace token format + the self-check footer schema documented in this plan]

# Tech tracking
tech-stack:
  added: []  # zero new deps — pure CLAUDE.md prompt engineering, no Python touched
  patterns:
    - "Marker-gated prompt overlay: every v1.1 rule explicitly gates on `is_v11_enabled(slug, '<flag>')` so v1.0 archives silently skip (D-29 byte-equal preserved)"
    - "Cross-reference notes at workflow phase boundaries (/summarize-video Phase 2/6/7/8) point INTO the centralized v1.1 H2 anchor — DRY for prompt rules"
    - "Format-spec lock extended additively: `4 项` → `4+1 项`; the +1 is opt-in so it doesn't break existing 17 archived format conformance"

key-files:
  created:
    - .planning/phases/08-writing-rules-claude-md-extensions-glossary/08-02-SUMMARY.md
  modified:
    - CLAUDE.md  # +289 lines, -3 lines (new H2 section + 5th invariant + 4 cross-refs)

key-decisions:
  - "Insertion target chosen: AFTER Phase 07 marker section + BEFORE /summarize-video workflow. This co-locates Phase 07 + Phase 08 v1.1 cluster (marker schema → enhancement rules → workflow integration), per 08-CONTEXT.md specifics line 121."
  - "5th format-spec invariant added as opt-in (`inline_trace_tokens` gate) rather than mandatory — keeps v1.0 archives at '4 项' compliance + makes v1.1 trace-token enforcement marker-driven. `4 项` → `4+1 项` heading update + 锁死语 lower paragraph clarifies the v1.1 vs v1.0 distinction."
  - "Cross-reference notes at /summarize-video Phase 2.5 (NEW sub-step), Phase 6 (mode-tip blockquote pair), Phase 7 (TL;DR hook), Phase 8 (self-check + glossary audit hooks) — 4 v1.1 hook insertion points cover all marker-driven workflow divergences."
  - "Plan 08-02 introduces ZERO Python LOC (verified by `git diff --stat HEAD~2 HEAD` showing only CLAUDE.md). All v1.1 behavior changes are prompt rules; the gating runtime check is `is_v11_enabled(slug, '<flag>')` shipped in Plan 08-01."
  - "Hard caps stated explicitly in CLAUDE.md (not deferred to Phase 09 verifier): CORR-01b max 10 corrections + ≥ 2 evidence sources, CORR-01c ±0.5s window + max 5 frames/warning, TEACH-A2 ≤ 6 line header, TEACH-B 10-15 line TL;DR (max 20). Stating in prompt makes Claude self-enforce; Phase 09 verifier double-checks."

patterns-established:
  - "Marker-gated prompt block pattern: any v1.1 rule that overlays on top of an existing /summarize-video phase opens with a `> **v1.1 hook (opt-in)**:` blockquote naming the gating flag(s) and pointing to the centralized H2 anchor. Future Phase 09 prompt rules reuse this template."
  - "FORBIDDEN/REQUIRED/OPTIONAL three-category eligibility lists for prompt rules (CORR-02 引用资格规则, TEACH-A1 forbidden universal terms, TL;DR forbidden citations) — explicit categorization prevents Claude from drifting into ambiguous middle ground."

requirements-completed: [CORR-01b, CORR-01c, CORR-02, TEACH-A1, TEACH-A2, TEACH-B]

# Metrics
duration: ~10 min
completed: 2026-05-03
---

# Phase 08 Plan 02: CLAUDE.md prompt extensions for v1.1 自适应教学文档增强 Summary

**Six v1.1 prompt rules + 5th format-spec invariant + 4 workflow cross-references inserted into CLAUDE.md as marker-gated overlays — zero Python LOC, D-29 byte-equal preserved.**

## Performance

- **Duration:** ~10 min (well under typical execute-plan budget; pure markdown insertion + verification)
- **Started:** 2026-05-03T10:01:00Z (approx)
- **Completed:** 2026-05-03T10:11:00Z (approx)
- **Tasks:** 3 (Task 1 H2 section insertion / Task 2 invariant + cross-refs / Task 3 verification gates)
- **Files modified:** 1 (CLAUDE.md only) + 1 NEW summary

## Accomplishments

- Inserted new H2 section `## v1.1 自适应教学文档增强 (Phase 08)` at line 1142 (between Phase 07 marker block and /summarize-video workflow) — ~270 lines of literal markdown rules
- 7 sub-rules documented with explicit `is_v11_enabled(slug, '<flag>')` gates: CORR-01b (L2 上下文修复), CORR-01c (L3 多模态兜底), CORR-02 (行内溯源 token + 自检 pass — 2 触发条件), TEACH-A1 (首次术语 inline 注解), TEACH-A2 (自包含零基础 header), TEACH-A3 (跨 slug glossary), TEACH-B (5 分钟速读版)
- 6 V11_FEATURES flags referenced verbatim in the new content match Plan 08-01's allowlist exactly: `l2_l3_correction` / `inline_trace_tokens` / `self_check_confidence` / `self_contained_header` / `cross_slug_glossary` / `tldr_speedrun`
- Hard caps stated explicitly: CORR-01b max 10 corrections + ≥ 2 evidence sources / CORR-01c ±0.5s window + max 5 frames per warning / TEACH-A2 ≤ 6 line header (excluding TL;DR) / TEACH-B 10-15 lines (max 20) / CORR-02 density target avg ≤ 1 citation per 3 sentences
- TEACH-A1 inline-first invariant explicit: "REGARDLESS of glossary state" + FORBIDDEN universal terms list (Python / JSON / Claude / Git / Docker / npm / pip / URL / API / HTTP / HTTPS / AI / ML / LLM)
- TEACH-A2 anti-patronizing tone constraints: FORBIDDEN phrases (`简单来说` / `说白了` / `你可能不知道` / `相信很多人不清楚`) + REQUIRED 第二人称指令式 tone
- TEACH-B sync check rules: replicate-guide TL;DR step count ≈ body H2 count (≤ 20% drift); interview-distillation TL;DR timestamps ≈ chapters.json count (≤ 30% drift); other modes Claude 自定义判断
- TEACH-B write-LAST invariant explicit (防 drift per P-06) + zero citation in TL;DR (use section anchors `详见 §三、消化阶段`)
- Extended `### 格式锁定` from "4 项不变量" to "4+1 项不变量" — added 5th invariant (trace tokens) gated on `inline_trace_tokens`, preserving v1.0 archives at 4-item compliance
- Added 4 v1.1 hook cross-references in `## /summarize-video 完整工作流`:
  - Phase 2.5 (NEW sub-step) → l2_l3_correction (CORR-01b/c)
  - Phase 6 mode-tip blockquote pair → inline_trace_tokens / self_contained_header / cross_slug_glossary (CORR-02 / TEACH-A1+A2 / TEACH-A3)
  - Phase 7 → tldr_speedrun (TEACH-B with > 20min OR > 50 sections trigger)
  - Phase 8 → self_check_confidence (CORR-02 self-check) + cross_slug_glossary audit
- D-29 byte-equal regression gate still PASS (33/0) after CLAUDE.md edits — confirms no Python import side-effects affected v1.0 archive replay

## Task Commits

Each task was committed atomically with --no-verify (parallel executor):

1. **Task 1: Insert v1.1 自适应教学文档增强 H2 section into CLAUDE.md** — `8ea0612` (feat)
2. **Task 2: Extend 格式锁定 with 5th invariant + 4 cross-references in /summarize-video** — `4c6c73d` (feat)
3. **Task 3: Verification gates** — no commit needed (verification only, no file changes; results documented in this SUMMARY)

## Files Created/Modified

- `CLAUDE.md` — +289 insertions / -3 deletions across 2 commits. Three regions touched:
  - Lines 269-278: 4-invariant block extended to 4+1 invariants (Task 2)
  - Lines 1140-1410 (post-Task-1): NEW `## v1.1 自适应教学文档增强 (Phase 08)` H2 section + 7 ### sub-sections (Task 1)
  - Lines 1447-1535 (post-Task-2): 4 cross-reference blockquotes inserted at /summarize-video Phase 2/6/7/8 (Task 2)
- `.planning/phases/08-writing-rules-claude-md-extensions-glossary/08-02-SUMMARY.md` — NEW (this file)

## Decisions Made

- **Marker-gated overlay pattern preserved across the H2 section**: every sub-rule's "触发条件" line opens with `is_v11_enabled(slug, "<flag>")`. This is the load-bearing D-29 invariant — old archives without marker silently fall back to v1.0 path. The pattern is recursively applied to CORR-02 (which has 2 separate triggers — `inline_trace_tokens` for tokens AND `self_check_confidence` for self-check pass — documented as two distinct conditions).
- **Hard caps stated in CLAUDE.md, not deferred to Phase 09 verifier**: rather than rely on the future verifier to reject violations, the prompt itself instructs Claude to self-enforce caps (e.g., "采纳上限：max 10 auto-applied corrections per slug"). This makes the prompt self-sufficient even before Phase 09 ships, and gives the future verifier a concrete thresholds list.
- **5th invariant marked opt-in in heading, not lower body**: the section header changes from "4 项不变量" to "4+1 项不变量" + the intro paragraph carries the marker-gate clarification. This makes the opt-in nature visible at a glance — readers don't have to scan to item 5 to discover it doesn't apply to v1.0 archives.
- **Phase 6 v1.1 hook covers 3 flags in one blockquote (not 3 separate blockquotes)**: `inline_trace_tokens` + `self_contained_header` + `cross_slug_glossary` all trigger during正文 writing, so a single blockquote with sub-bullets (one per flag) reads better than 3 separate blockquotes. Phase 7 / Phase 8 use single-flag hooks because their gating logic is simpler (one trigger each).
- **TEACH-A3 inline-first invariant placed CRITICAL**: the prompt explicitly states "**禁止**用'glossary 里有'作为跳过 inline 注解的理由" — D-01 self-contained reading rule means glossary is fallback, not first reference. The CRITICAL marker prevents Claude from optimizing the inline annotation away when it sees the same term already in glossary.
- **No commit for Task 3**: Task 3 is verification-only (no files modified). Per `git diff --stat HEAD~2 HEAD` only CLAUDE.md changed across the 2 task commits — verification results are captured here in SUMMARY.md without needing an empty commit.

## Deviations from Plan

None — plan was extremely well-specified (the entire ~270-line H2 insertion was a literal markdown block in the plan's `<action>` block; the 5th invariant + 4 cross-refs were Edit-tool-ready old/new pairs). Worth noting: I initially edited the wrong CLAUDE.md path (main repo at `D:/gxy_code/videoSummary/CLAUDE.md` instead of the worktree at `D:/gxy_code/videoSummary/.claude/worktrees/agent-ab7cd9b63ab02abce/CLAUDE.md`); recovered by re-applying the edits to the worktree (the main repo's stale modification is harmless because the orchestrator merges from the worktree, not the main repo). No plan change.

## Issues Encountered

None for the actual prompt content. The only environmental friction was sandbox permission boundaries that prevented running `git diff --stat HEAD~1 HEAD` against the main repo — verified Task 1 / Task 2 progress via Read/Grep/Edit tools instead.

## Verification Results

All 5 plan-level verification checks pass:

| # | Check | Result |
|---|-------|--------|
| 1 | D-29 byte-equal regression (`scripts.replay_v10_archives`) | PASS — 33 PASS / 0 FAIL |
| 2 | All 6 V11_FEATURES flag names referenced by CLAUDE.md exist in `agent._v11.V11_FEATURES` | PASS — `l2_l3_correction`, `inline_trace_tokens`, `self_check_confidence`, `self_contained_header`, `cross_slug_glossary`, `tldr_speedrun` all in 13-entry tuple |
| 3 | All 7 expected subsection markers present in v1.1 H2 block | PASS — CORR-01b, CORR-01c, CORR-02, TEACH-A1, TEACH-A2, TEACH-A3, TEACH-B all found |
| 4 | CLAUDE.md size sanity check | PASS — 51,045 bytes (was ~38KB pre-Phase-08, now +13KB) |
| 5 | Phase 07/08 unittest suites still pass | PASS — 37 tests, 0 failures (test_glossary + test_k5_emitters + test_v11_marker + test_glossary_audit + test_replay_v10) |

Additional spot-checks:

- `git diff --stat HEAD~2 HEAD` confirms only `CLAUDE.md` changed (1 file, +289/-3) — no Python files touched
- New H2 section ordering verified: Phase 07 marker block (line 1092) < new Phase 08 H2 (line 1142) < /summarize-video workflow (line 1412)
- Phase 07 marker section `## v1.1 opt-in marker + 4 K5 emitters (Phase 07)` byte-equal preserved (D-29 spirit for documentation)
- `## 视频类型变奏` 4-mode classification + 8 skeletons block byte-equal preserved (Plan 08-02 only added cross-refs to /summarize-video, not to 视频类型变奏)

## User Setup Required

None — CLAUDE.md is loaded automatically by Claude Code at session start. Next time `/summarize-video` runs on a slug with `.v11_features.json` enabling any of the 6 new flags, the new prompt rules take effect immediately. No external service, no environment variable, no opt-in dependency install.

## Next Phase Readiness

Ready for **Phase 09** (verifier — CORR-03 second-agent diff review + summary_lint citation density check). The CLAUDE.md content this plan ships is the source-of-truth for what the verifier needs to assert:

- Phase 09 `summary_lint` reads the citation density target (avg ≤ 1 per 3 sentences) from this plan's CORR-02 引用资格规则 sub-section
- Phase 09 verifier reads the format-spec invariant list (now 4+1) from `### 格式锁定` to know what to assert against marker-enabled summaries
- Phase 09 verifier reads the TL;DR sync-check rules (TEACH-B step 3) to know how to detect drift
- Phase 09 reviewer reads the FORBIDDEN/REQUIRED/OPTIONAL eligibility categories (CORR-02 引用资格规则, TEACH-A1 forbidden universal terms) to know what counts as a violation

No blockers. No deferred items.

## Self-Check: PASSED

Verified the following claims after writing this SUMMARY:

- Commit `8ea0612` exists: `feat(08-02): insert v1.1 自适应教学文档增强 H2 section into CLAUDE.md`
- Commit `4c6c73d` exists: `feat(08-02): extend 格式锁定 with 5th invariant + 4 cross-references in /summarize-video`
- `## v1.1 自适应教学文档增强 (Phase 08)` exists in CLAUDE.md exactly once (verified via Grep)
- 6 prompt-referenced flags all in V11_FEATURES (verified via Python import)
- D-29 replay reports 33 PASS / 0 FAIL (verified via `python -m scripts.replay_v10_archives`)
- All 37 Phase 07/08 unittest tests pass (verified via `python -m unittest`)
- `git diff --stat HEAD~2 HEAD` shows only CLAUDE.md modified (1 file, +289/-3) — no Python files touched

---
*Phase: 08-writing-rules-claude-md-extensions-glossary*
*Completed: 2026-05-03*
