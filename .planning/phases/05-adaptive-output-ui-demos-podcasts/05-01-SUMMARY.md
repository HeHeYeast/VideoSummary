---
phase: 05-adaptive-output-ui-demos-podcasts
plan: 01
subsystem: docs
tags: [claude-md, prompt-engineering, mode-classification, exemplar-skeleton, format-spec-lock, adaptive-output]

# Dependency graph
requires:
  - phase: 02-resume-infrastructure-cache-correctness
    provides: sidecar params.json pattern reused for plan.md (.params.json describing created_at + mode + secondary_mode)
  - phase: 04-frame-fps-automation-schedule-json-extract-frames-batch
    provides: schedule.json shape referenced by Phase 4 mode-hint blockquote (interview-distillation 1-2 frames/chapter via fps 0.05 windows)
provides:
  - "## 视频类型变奏 top-level CLAUDE.md section (D-18 — placed before /summarize-video workflow)"
  - "4 mode tag byte-equal lock (replicate-guide / concept-explanation / extension-applications / interview-distillation per D-01)"
  - "Phase 2 sub-step 2.4 — mode classification + plan.md write directive"
  - "Phase 4/5/6 single-line mode-hint blockquotes (D-21 — no parallel 8-phase forks)"
  - "plan.md schema documentation: 5-field YAML front-matter + free-form Markdown body (D-09)"
  - "depth_plan.md optional file documentation: > 30min OR > 50 sections trigger + .need_depth_plan force-enable (D-11/D-12)"
  - "Mode-switch in-progress rule: plan.md mode field edit + mode_switched_at marker (D-04)"
  - "Format-spec lock: 4 invariants (timestamp [HH:MM:SS] / fenced code w/ language / ![](frames/seg_xxxx_xxxxxx.jpg) / second-person imperative)"
  - "8 hand-authored exemplar skeletons (4 modes × 2) — P1.3 防线"
affects:
  - 05-02 (--profile flag + PROFILES + whisper repetition guard) — reads format-spec lock
  - 05-03 (UI demo 4 sub-rules + podcast diarize CLI + chapters.json + WR-02 VTT priority) — references skeleton placeholder for podcast-specific 1-2 frames/chapter and UI demo 4 sub-rules
  - All future /summarize-video runs — Phase 2 must now produce output/<slug>/plan.md

# Tech tracking
tech-stack:
  added: []  # zero LOC Python; 100% prompt engineering
  patterns:
    - "CLAUDE.md adaptive layer pattern — ## 视频类型变奏 sits beside (not inside) /summarize-video 8-phase trunk; reusable for future variant-bands"
    - "Skeleton-as-prompt-prior — 8 minimal markdown exemplars give Claude 4-mode form-vocabulary without compressing them to ellipsis"
    - "Format-spec lock via 4 invariants — separates form (locked) from content (adaptive), prevents P1.2 退化"
    - "Mode-switch in-progress (D-04) — Claude self-corrects mid-write via plan.md + mode_switched_at, no user-pause-confirm (K2)"

key-files:
  created: []
  modified:
    - "CLAUDE.md (226 → 989 lines, +763 net)"

key-decisions:
  - "D-01 / D-02 / D-03 / D-04 — 4 mode tags byte-equal + Phase 2 末尾 classification + replicate-guide fallback + mode-switch in-progress rule"
  - "D-05 / D-06 / D-07 / D-08 — exemplar from existing archive corpus (¥0) + 4 modes × 2 = 8 skeletons + 50-120 lines each + ≤ 1000 cap"
  - "D-09 / D-10 / D-12 — plan.md = 5-field YAML front-matter + free-form Markdown; mandatory in Phase 2 but missing-not-fatal (K3 backward-compat); .params.json sidecar for created_at/mode tracking only"
  - "D-11 — depth_plan.md optional, Claude self-judges (>30min OR >50 sections) + .need_depth_plan force-enable (no user-pause-confirm, K2)"
  - "D-18 — ## 视频类型变奏 placed BEFORE ## /summarize-video; main 8-phase trunk byte-equal except Phase 2 += sub-step 2.4 and Phase 4/5/6 += 1 mode-hint blockquote each"
  - "D-21 — no parallel 8-phase forks (no separate podcast workflow); mode picks at Phase 2, then Phase 3-7 自动按 mode-specific skeleton 走"
  - "TEACH-02 / P1.2 — content adaptive, form not (4 invariants enforce visual fingerprint of videoSummary 出品)"

patterns-established:
  - "Adaptive variant-band sits beside (not inside) main workflow — keeps trunk simple while allowing mode-specific variation downstream"
  - "Skeleton-pair-per-mode — 2 different rhythms per mode (短/长 / 步骤型/概念型) to avoid Claude锚定唯一正解"
  - "Mode lock + form lock 解耦 — mode 自适应 (4 选 1 + secondary)，form 不变 (4 invariants)"
  - "Free-form Markdown + 顶部 YAML front-matter — schema-tolerant 格式既能 grep 又不强校验，K3 (backward-compat) 与 K2 (Claude is decider) 同时满足"
  - "Skeleton 顶部统一 <!-- 来源: output/<slug>/summary.md (reshape) --> 注解 — 8/8 全部带源标注，便于未来维护回溯"

requirements-completed: [TEACH-01, TEACH-02, TEACH-03, TEACH-04, TEACH-05]

# Metrics
duration: 8min
completed: 2026-05-01
---

# Phase 05 Plan 01: 自适应教学文档 Prompt-Engineering 中心 Summary

**CLAUDE.md 升级为 4 模式自适应教学文档的决策中心：嵌入 ## 视频类型变奏 章节 + 8 份 hand-authored exemplar skeleton + format-spec lock + plan.md/depth_plan.md schema，零 LOC Python，全是 prompt engineering**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-01T04:56:53Z
- **Completed:** 2026-05-01T05:05:11Z
- **Tasks:** 2 / 2
- **Files modified:** 1 (CLAUDE.md only)

## Accomplishments

- 在 CLAUDE.md 现有 line 114 `---` 后插入 `## 视频类型变奏` 顶级章节（位于 `## /summarize-video 完整工作流` 之前），主干 8 阶段不分叉
- 4 mode 标签字面 byte-equal 锁定 (TEACH-01 / D-01)：`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`
- 4 项 format-spec 不变量锁定 (TEACH-02 / P1.2 / D-21)：`[HH:MM:SS]` 8 字符时间戳 + 代码 fence 带显式语言 + `![](frames/seg_xxxx_xxxxxx.jpg)` 相对路径 + 第二人称指令式
- 8 份 hand-authored exemplar skeleton 嵌入 (TEACH-03 / D-05..D-08)：4 modes × 2 each，全部从 6 份现有 archived corpus reshape (¥0)
- plan.md schema 文档化 (TEACH-04 / D-09 / D-10)：顶部 5 字段 YAML front-matter (`mode` / `secondary_mode` / `classification_evidence` / `fps_strategy_summary` / `estimated_sections`) + free-form Markdown 正文；mandatory 但 missing-not-fatal
- depth_plan.md schema 文档化 (TEACH-05 / D-11 / D-12)：可选独立文件，Claude 自判，`.need_depth_plan` 强制启用
- Phase 2 增加 2.4 子步 (mode 判断 + plan.md write)；Phase 4/5/6 各增加 1 行 mode-hint blockquote (D-21 不分叉主干)
- Mode-switch in-progress 规则 (D-04 / P1.5)：写到一半误判可改 plan.md mode 字段 + `mode_switched_at: HH:MM:SS reason: ...`，重写已写部分

## Task Commits

Each task was committed atomically:

1. **Task 1: 视频类型变奏 章节骨架 + 4 模式分类 + format-spec lock + plan.md/depth_plan.md/mode-switch 文档** - `e0b8fa1` (feat) — 91 net lines added (CLAUDE.md 226 → 317)
2. **Task 2: 嵌入 8 份 hand-authored skeleton (4 modes × 2)** - `f7cd4cd` (feat) — 673 net lines added (CLAUDE.md 317 → 989)

**Plan metadata:** (final commit pending — orchestrator will collect SUMMARY.md)

## Files Created/Modified

- `CLAUDE.md` (modified) — 226 → 989 lines (+763 net)
  - Lines 116-195：新增 `## 视频类型变奏` 章节（5 子节：模式分类 / plan.md 必写 / depth_plan.md 可选 / 格式锁定 / 4 模式 skeleton）
  - Lines 197-868：8 份 exemplar skeleton（含 mode subheaders）
  - Line 905：Phase 2 新增 2.4 子步
  - Lines 940 / 949 / 969：Phase 4 / 5 / 6 各 1 行 mode-hint blockquote

## Skeleton Sources & Line Budget

8 skeletons selected from 6 archived corpus directories (¥0 reshape, no new video runs):

| Mode | Skeleton 1 | Skeleton 2 |
|---|---|---|
| replicate-guide | `output/BV132wizyEEB/summary.md` (1:14, 短小步骤型) | `output/douyin_trae_ai/summary.md` (4:12, 长流程多步型) |
| concept-explanation | `output/douyin_ai_kb/summary.md` (2:02, 反直觉问题→例证→边界) | `output/douyin_claude_code_hooks/summary.md` (剥离实操只留原理) |
| extension-applications | `output/douyin_claude_code_hooks/summary.md` (4 类工具横向罗列) | `output/douyin_trae_ai/summary.md` (3 命令同概念串讲) |
| interview-distillation | `output/douyin_karpathy_llm_wiki/summary.md` (speaker turns + key claims) | `output/douyin_karpathy_llm_wiki/summary.md` (按 chapters.json 4 章节切片) |

**Skeleton total budget**: 8 skeletons + framing 累计净增 763 lines（≤ D-08 1000-line cap）。
**CLAUDE.md final**: 989 lines（≤ D-08 1500-line hard cap）。

**Per-skeleton size (approximate)**:
- replicate-guide #1 (BV132wizyEEB) — 70 lines
- replicate-guide #2 (TRAE SOLO) — 95 lines
- concept-explanation #1 (LLM Wiki) — 60 lines
- concept-explanation #2 (Hooks 原理切片) — 70 lines
- extension-applications #1 (Hooks 4 工具对比) — 100 lines
- extension-applications #2 (TRAE 3 命令) — 80 lines
- interview-distillation #1 (speaker turns) — 80 lines
- interview-distillation #2 (chapters.json 切片) — 75 lines

All 8 within the 50-120 line per-skeleton range (D-07).

## Format-Spec Invariants Verification

| Invariant | Required | Achieved |
|---|---|---|
| `[HH:MM:SS]` 8-char timestamps | ≥ 8 | 54 ✓ |
| `![](frames/seg_*.jpg)` embeds | ≥ 4 | 20 ✓ |
| Code fence with explicit language | ≥ 1 per skeleton | gdscript / python / bash / json / yaml / text / markdown 均出现 ✓ |
| 第二人称指令式 | mention | 4 处明确说明 + 所有 skeleton 内例子 ✓ |
| Interview blockquote `> [HH:MM:SS]` | ≥ 1 (interview skeleton) | 18 ✓ |

## Decision Landing Points (D-XX → CLAUDE.md location)

| Decision | Where it landed |
|---|---|
| D-01 (4 mode tag byte-equal) | Lines 122-127 (mode list) + 233 (Phase 2.4 reference) + skeleton headers (lines 197, 297, 469, 575) |
| D-03 (replicate-guide fallback) | Line 141 |
| D-04 (mode-switch in-progress + mode_switched_at) | Line 143 + 233 (Phase 2.4) |
| D-09 (5-field YAML front-matter) | Lines 149-162 (full block) |
| D-10 (mandatory in Phase 2 + missing-not-fatal) | Lines 164-166 |
| D-11 (depth_plan.md trigger conditions) | Lines 170-180 |
| D-12 (.params.json sidecar for plan.md) | Line 168 |
| D-18 (## 视频类型变奏 placement before /summarize-video) | Lines 116 (section start) vs 871 (workflow start) |
| D-21 (no parallel 8-phase forks) | Phase 2.4 single sub-step (line 905) + 3 mode-hint blockquotes (lines 940/949/969) |
| TEACH-02 / P1.2 (content adaptive, form not) | Lines 182-191 (4 invariants) + line 191 (锁死语) |

## Backward-Compat Verification (K3)

| Check | Result |
|---|---|
| `## 视频类型变奏` 在 `/summarize-video` 之前 | ✓ (line 116 < 871) |
| 5 条核心命令 (download/transcribe/extract_frames/aggregate/cleanup_frames) byte-equal | ✓ (grep 0 hits in diff for command-line modifications) |
| `## 抖音支持` / `## YouTube 支持` / `## Windows zh-CN 终端设置` / `## 决策支持工具` 整段无修改 | ✓ (lines 22 / 31 / 50 / 86 — content unchanged) |
| Phase 1 / 3 / 7 / 8 整段不动 | ✓ (only Phase 2 +1 sub-step, Phase 4/5/6 +1 blockquote each) |
| 17 archive 没 plan.md → 老 re-run 不 fatal | ✓ (D-10 documented warning-not-fail at line 166) |

## Decisions Made

None beyond CONTEXT.md D-01..D-12 / D-18 / D-21 — all decisions inherited from 05-CONTEXT.md and landed verbatim. Executor's discretion was limited to:

- **Skeleton ordering inside `## 视频类型变奏`**: chosen as `模式分类 → plan.md → depth_plan.md → 格式锁定 → 4 模式 skeleton` (per D-18 readability heuristic)
- **Per-skeleton archive selection from D-06 candidate range**: picked 6 distinct sources to maximize node-rhythm diversity (避免 P1.3 单 mode 塌缩)
- **Skeleton 内时间戳 `[HH:MM:SS]` 改写自源 archive 的 `[MM:SS]` 格式** — source archives 用 `[00:06]` 等 5-char 格式（pre-Phase-5 archive），skeleton 升级为 8-char `[00:00:06]` 形态以对齐新的 format-spec invariant 1

## Deviations from Plan

None - plan executed exactly as written. All 7 verification checkbox items in the plan's `<verification>` block pass; all 5 success_criteria are 100% covered by the artifacts.

The 8th-skeleton source comment was momentarily inconsistent (`<!-- 来源: 同一份 douyin_karpathy_llm_wiki...` lacked the `output/` prefix), corrected inline before commit; not a deviation per Rule 1 since the verification regex `<!-- 来源: output/` was the intended invariant from task 2 verify block.

## Issues Encountered

- **Hook re-read prompts**: Each Edit tool call triggered a `READ-BEFORE-EDIT REMINDER` system reminder despite a single Read at session start. Resolved by re-reading the relevant slice between each Edit; no semantic impact, only some extra tool calls.
- **STATE.md modified on disk by orchestrator init**: orchestrator's `gsd-tools init execute-phase` mutated STATE.md at start; per plan instructions ("Do NOT update STATE.md") I left it untouched and committed only CLAUDE.md.

## User Setup Required

None - no external service configuration required. This plan is 100% prompt engineering on a tracked file (CLAUDE.md). No new dependencies, no env vars, no auth gates.

## Next Phase Readiness

**Ready for plan 05-02** (`--profile` flag + PROFILES + whisper repetition guard):
- TEACH-02 format-spec lock provides the invariants any future writer (including the 05-02 stdout warning artifacts and 05-03 chapters.json schema) must respect
- Mode 4 标签锁 + plan.md schema 让 05-02 / 05-03 的 sidecar `<artifact>.params.json` 可以记录 mode/profile 字段而无需新 schema 设计

**Ready for plan 05-03** (UI demo 4 sub-rules + podcast diarize + chapters.json + WR-02 VTT):
- 4 mode skeleton 中 `extension-applications` Skeleton 1（UI demo 候选基底）和 `interview-distillation` 两份 skeleton 已就位，05-03 的 UI demo 4 sub-rules 与 podcast 1-2 frames/chapter 详细规则补在 skeleton 内即可，无需重新铺设章节框架
- Phase 4 mode-hint blockquote 已 forward-reference UI demo 4 sub-rules（pixel-text / tooltip / cursor / --width）和 chapters.json，05-03 落地时只要 fill-in 这两处 placeholder

**Hooks for 05-03**:
- Skeleton interview-distillation #2 已展示 chapters.json 4-章节切片形态作为 preview；05-03 写 chapters.json schema 时直接对齐这个示意 JSON 即可
- Phase 4 mode 提示 line 940 "由后续 plan 03 落地" 字符串是 05-03 的明确 entry point

**No blockers / no concerns** for downstream phases.

## Self-Check: PASSED

Verified outputs exist on disk:
- `D:/gxy_code/videoSummary/CLAUDE.md` ✓ (989 lines, contains `## 视频类型变奏`, all 4 mode tags, all 8 skeleton headers, all 4 format invariants, 4 sub-section headers within 视频类型变奏)
- `D:/gxy_code/videoSummary/.planning/phases/05-adaptive-output-ui-demos-podcasts/05-01-PLAN.md` (input, untouched) ✓

Verified commits exist in git log:
- `e0b8fa1` (Task 1) ✓
- `f7cd4cd` (Task 2) ✓

All requirement IDs in plan frontmatter (`requirements: [TEACH-01, TEACH-02, TEACH-03, TEACH-04, TEACH-05]`) covered:
- TEACH-01 ✓ (4-tag classification step in Phase 2.4)
- TEACH-02 ✓ (4-invariant format-spec lock at lines 182-191)
- TEACH-03 ✓ (8 hand-authored exemplar skeletons)
- TEACH-04 ✓ (plan.md 5-field YAML front-matter docs at lines 145-168)
- TEACH-05 ✓ (depth_plan.md docs at lines 170-180)

---
*Phase: 05-adaptive-output-ui-demos-podcasts*
*Plan: 01*
*Completed: 2026-05-01*
