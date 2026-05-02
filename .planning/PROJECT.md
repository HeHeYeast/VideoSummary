# VideoSummary

## What This Is

videoSummary 是一个本地 ¥0 视频学习文档化工具。把 B 站 / 抖音 / YouTube 等视频，通过 Claude Code 的多模态能力，转换成具备真实教学价值的 Markdown 文档；面向想从教学、操作演示、访谈类视频里高效提炼知识的单用户作者（你自己）。Claude Code 是唯一决策者，所有"理解、抽帧、写作"步骤在 Claude 上下文内完成，无任何付费 API。

## Core Value

把视频提炼成对学习者真有教学价值的 Markdown 文档（不是字幕翻译），并保持全流程 ¥0。

## Requirements

### Validated

<!-- 已 ship 并在用的能力，源自现有 ¥0 流程。 -->

- ✓ B 站 URL 下载视频 + 元数据（yt-dlp，可注入 SESSDATA）— existing
- ✓ 抖音 URL 下载（a_bogus 签名 + cookies，走 vendor crawler）— existing
- ✓ 本地 ASR 转录（faster-whisper + VAD + 幻觉过滤）— existing
- ✓ 段落聚合（基于 silence gap / 句末标点 / 30s 上限）— existing
- ✓ 手工分段抽帧（ffmpeg，按 fps + start/end 裁剪）— existing
- ✓ Claude Code 多模态帧理解（直接 Read JPEG，无 OCR/Vision API）— existing
- ✓ Claude Code 主导的 /summarize-video 8 阶段工作流 — existing
- ✓ cleanup_frames 删除未引用帧 — existing
- ✓ 全流程 ¥0（无付费 API 依赖）— existing
- ✓ 文件级 idempotent 缓存（按 artifact 存在与否短路）— existing
- ✓ **参数感知 + 原子写 + 可恢复的 artifact 重用** — atomic-write (tempfile + os.replace) + `<artifact>.params.json` sidecar + `state.jsonl` 事件日志 + `derived_state` reducer + `doctor` 子命令 + Windows PermissionError 重试 — v1.0 Phase 2 (RES-01..RES-08 全部 satisfied)
- ✓ **新输入源** — YouTube + 通用 yt-dlp 平台 + 本地 mp4；agent/sources/ 注册表 + 5 source classes + 5-class YouTube preflight 分类器 + LocalSource ASCII-safe slug — v1.0 Phase 3 (SRC-01..SRC-13)
- ✓ **抽帧策略自动化** — Claude-written `schedule.json` + `extract_frames_batch` 段级 resume + FPS-04 silence 强制覆盖 + PySceneDetect/silero-vad 决策支持只读 CLI（K5）— v1.0 Phase 4 (FPS-01..FPS-07)
- ✓ **自适应教学文档** — 4-mode 分类（replicate-guide / concept-explanation / extension-applications / interview-distillation）+ 8 hand-authored exemplar skeletons + format-spec lock + plan.md/depth_plan.md schema — v1.0 Phase 5 (TEACH-01..TEACH-13)
- ✓ **新视频类型** — UI 操作演示 4 子规则 + Podcast/interview-distillation skeleton + `--profile podcast` (VAD + paragraph aggregation) + opt-in pyannote diarize CLI（degrade fast-path）+ whisper repetition guard — v1.0 Phase 5
- ✓ **现有路径 backward-compatible** — 17 archive re-runs byte-identical (D-29 invariant)；老 CLI 5 命令保留可用；新功能全部 opt-in/additive — v1.0 (持续验证 Phases 1-6)
- ✓ **多 agent 并行（Nice-to-have shipped）** — cross-platform stdlib FileLock + per-slug `.resume.lock` + vendor config 锁 + slug-prefix logs + cookies-in-memory cache — v1.0 Phase 6 (PARA-01..PARA-06)

### Active

<!-- v1.1 milestone Active requirements — 详见 .planning/REQUIREMENTS.md（traceability 在 ROADMAP 写完后回填）。 -->

- [ ] **Summary 正确性自动化** — 三层叠加校验（自检 + 行内溯源 + 第二 agent 复审）+ ASR 术语自动校正（L1 检测/L2 上下文/L3 多模态兜底） — v1.1
- [ ] **零基础自包含 summary** — 每篇术语 inline 注解 + `output/_glossary.md` 累积 + 顶部"你需要/不需要知道什么"段 + 长视频顶部 5 分钟速读版 — v1.1
- [ ] **Mode + 抽帧决策辅助信号** — `mode_signals.json` + `schedule_suggestion.json` 工具（K5 边界：仅出建议，Claude 仍决策） — v1.1
- [ ] **运维杂项打杂** — AV1 警告降级 + Video queue helper CLI — v1.1

## Current Milestone: v1.1 summary-quality

**Goal:** 把 v1.0 工具链产出的 summary 从"读起来正确"升级为"自动可信、零基础读者也能学到东西"——所有错误自动检测/修复/复审，新读者不依赖外部知识也能读懂。

**Target features:**

- 🔴 必做 — CORR-01 ASR 术语自动校正（3 层）/ CORR-02 自检 + 行内溯源 / CORR-03 第二 agent 复审 / TEACH-A 零基础自包含
- 🟡 想做 — TEACH-B 长 summary 顶部速读版 / TOOL-A mode_signals.json / TOOL-B schedule_suggestion.json
- 🟢 顺手做 — MISC-01 AV1 警告降级 / MISC-02 video queue helper CLI

**Locked design decisions** (`v1.1-CANDIDATES.md` D-01/02/03，不再讨论)：

- D-01：每篇 summary 自包含、零基础视角（不假定阅读顺序，不假定阅读后理解）
- D-02：正确性校验三层叠加（自检 + 行内溯源 + 二次复审）
- D-03：自动化优先（任何"用户手动做"的方案先 reject）

**Continuity from v1.0:**

- D-29 backward-compat 仍守：未触发新 warning 的旧视频行为 byte-equal v1.0
- K5 决策权不外移：所有新 _signals 工具仅出建议，Claude 仍是决策者
- 老 5 CLI + `output/<slug>/` 目录约定保留

### Out of Scope

<!-- 显式排除项，附理由防止后续被重新拉进来。 -->

- 任何付费 API（LLM / ASR / OCR / Vision） — ¥0 是 hard constraint，Core Value 之外的最高优先级
- 把决策权交给脚本 — Claude Code 仍是唯一决策者，工具只能"减摩擦"不能"做判断"
- 一个视频出多份文档（quick-ref + deep-dive 多档输出） — 用户已选 "Claude 自适应单文档"，不做模板分裂
- 队列全自动无人值守批跑 — 手动一条条触发当前可接受，自动批跑不在 v1 范围
- 万能视频平台支持 — 不做下载器覆盖率竞赛，按真实需要扩展
- 重写或废弃现有 agent/ src/ 模块 — 老命令必须保留可用，避免砸队列里 17 条视频的归档路径
- 改变 output/&lt;slug&gt;/ 目录约定 — 已总结视频的目录结构不重排
- 多用户 / 账号 / SaaS 化 — 单用户作者工具，不做共享或部署

## Context

- **使用现状**：你（单用户作者）已用现有 ¥0 流程总结过 6+ 条视频，归档在 `output/` 下（`BV132wizyEEB`、`godot_brave`、`douyin_trae_ai` 等都有完整的 `summary.md`）；队列里还有 17 条游戏 / Godot / AI 像素相关视频待处理（详见 memory `project_video_queue.md`）。
- **代码双层结构**：`agent/` 是当前 ¥0 工具集（`python -m agent.tools` 暴露 5 个命令）；`src/` 是早期带 VectorEngine 付费 API 的 v1 端到端 pipeline，保留作 legacy fallback。两层共享 `src.download` / `src.asr` 这部分纯本地代码。
- **第三方 vendor**：`vendor/douyin_api/` 是 `Evil0ctal/Douyin_TikTok_Download_API` 的 clone，唯一目的是提供 yt-dlp 缺失的 `a_bogus` 签名算法。`vendor/` 在 `.gitignore` 中，要手动 clone。
- **抽帧约定**：`output/<slug>/frames/seg_<start>_<index>.jpg` 文件名带时间原点，多段抽帧不会互相覆盖，时间戳可从文件名重建（`agent/tools.py:122-124`）。
- **本机环境**：Windows 11，bash + PowerShell 双 shell 可用，已装 ffmpeg / Python / faster-whisper / yt-dlp。
- **痛点信号汇总**（来自本次 questioning）：fps 决策摩擦最重；文档教学性不足是主诉；输入源只有 B 站 / 抖音不够；并行能力是好奇但不阻塞；批处理手动可接受。
- **代码地图已完成**：`.planning/codebase/` 下有 ARCHITECTURE / STACK / CONCERNS / CONVENTIONS / INTEGRATIONS / STRUCTURE / TESTING 七份完整分析（commit `c20d425`），可作所有后续 phase 的 ground truth。

## Constraints

- **Cost**: ¥0 — Claude Max 计划内本地全跑；禁止任何付费 API（LLM、ASR、OCR、Vision、翻译都不行）
- **Decision authority**: Claude Code 是唯一决策者 — 自动化只能"减少操作摩擦"，不能"取代判断"；工具不预设抽帧策略 / 大纲结构 / 文档模板
- **Backward compatibility**: 新能力一律 opt-in — 老 CLI 命令、`output/<slug>/` 目录格式、`/summarize-video` 8 阶段工作流必须仍可用，必须能"快速回退到当前方案"
- **Platform**: Windows 11 本机优先 — 路径分隔符 / 编码 / shell 兼容性按 Windows 处理；不做跨平台 CI
- **Scope**: 单用户作者工具 — 无账号、无多人、无部署、无 SaaS
- **Stack inertia**: 现有 stack 不轻易换 — `yt-dlp` / `faster-whisper` / `ffmpeg` / `vendor douyin_api` 已稳定，新能力优先围绕它们扩展而非替换

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| ¥0 成本作为 hard constraint，优先于教学价值 | Claude Max 已覆盖；用户在 "如果只能保住一个性质" 里明确选 ¥0 而非教学价值 | ✓ Good — v1.0 全程未引入任何付费 API |
| Claude 自适应单文档，而非多档输出（quick-ref/deep-dive 分离） | 用户认为 Claude 看完视频后判断侧重比固定模板合理；保留输出简洁 | ✓ Good — v1.0 Phase 5 落地 4-mode 单文档自适应 |
| 老 CLI 与 output/ 目录约定保留，新能力 opt-in 叠加 | 队列里还有 17 条视频要走老路径，新方案不能砸现有归档 | ✓ Good — D-29 backward-compat 全程验证 byte-identical |
| 多 agent 并行降级为 Nice-to-have | 用户表态"做不到也没关系"，不能阻塞 v1 | ✓ Good — v1.0 末期决定 ship 该 NTH（Phase 6 完成）|
| Claude Code 决策权不外移（即使引入抽帧自动化） | 与 CLAUDE.md 既有原则一致：工具是肢体，Claude 是大脑 | ✓ Good — K5 boundary 在 detect_scenes/silence + chapters.json 全部守住 |
| Pyannote diarization spike 走 degrade fast-path | 用户在 /gsd-autonomous 中选择跳过 700MB pyannote install + HF token 申请；infrastructure ship 但实测 deferred | — Pending — GPU 机器可未来补 SPIKE.md 并升 accept |
| v1.1 锁死 D-01 自包含、D-02 三层校验、D-03 自动化优先 | 用户在 v1.0 实测 BV1HG9JBsEPK + BV1rsd7BsEnA 两份 summary 后给出原话："不能假定我的阅读顺序，也不能假定阅读后一定有理解" + "尽可能避免文档撰写中的人工参与" | — Active — v1.1 milestone 开启时锁定，详见 `.planning/v1.1-CANDIDATES.md` |
| v1.1 一次 ship 全部 8 候选（必做 4 + 想做 2 + 顺手 2） | 用户主动调 /gsd-new-milestone 时选 "全做"；v1.0 工具链已稳，质量铁律必须一次落地不分批 | — Active — 通过 ROADMAP 拆 phase |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-03 — v1.1 summary-quality milestone started (`/gsd-new-milestone`). 8 candidate requirements adopted from `.planning/v1.1-CANDIDATES.md` (4 必做 + 2 想做 + 2 顺手). Locked design decisions D-01/02/03 from user feedback after BV1HG9JBsEPK + BV1rsd7BsEnA summary实测. Phases TBD via `/gsd-new-milestone` roadmapper.*

*2026-05-02 — v1.0 milestone shipped. 6 phases / 16 plans / 31 tasks. All Active requirements moved to Validated. Audit: 52/52 requirements satisfied, 6/6 phases passed, 4/4 E2E flows verified. See `.planning/MILESTONES.md` and `.planning/milestones/v1.0-MILESTONE-AUDIT.md`.*

*Earlier evolution log:*

*2026-04-30 — Phase 1 complete (regression baseline frozen; agent.io schema-tolerant loaders landed; encoding audit + Windows zh-CN docs shipped). No Active requirements moved to Validated yet — Phase 1 is gating infrastructure that ENABLES "现有路径 backward-compatible" but does not tick it off until later phases land without breaking baselines.*

*2026-05-01 — Phase 2 complete (Resume Infrastructure & Cache Correctness). Validated 13/13 must-haves: 5 ROADMAP Success Criteria + 8 RES-XX requirements. Atomic JSON writes (tempfile + os.replace + 3×0.5s PermissionError retry), 3-segment sidecar (cli/func/tools) with severity-split cache decision, JSON Lines `state.jsonl` event log + corruption-tolerant `derived_state` reducer, `doctor` 5-column read-only subcommand + `--json` flag, and `docs/schema-migration.md` runbook. Active requirement "中间产物失败可复用" moved to Validated (live-tested whisper small→medium triggers loud regen). Code review found 0 critical / 6 warning / 6 info (advisory follow-ups, none invalidate goal achievement). 17-archive backward-compat preserved: missing-sidecar path → loud warning + reuse cache (D-01); state.jsonl absent → file-existence cache fallback (D-03).*

*2026-05-01 — Phase 3 complete (Source Refactor + New Sources). Validated 13/13 SRC-XX requirements + 5 ROADMAP Success Criteria. New `agent/sources/` package with Source Protocol + 5 source classes (Douyin / YouTube / Bilibili / Local / Generic) + pure-function `url_router.route()`; `ingest` CLI subcommand canonical, `download` shim preserved (K3 backward-compat). YouTube layer: 2-second `yt-dlp --simulate` preflight + 5-class stderr classifier (po_token_required > cookies_stale > yt_dlp_outdated > gfw_blocked > other) with locked Chinese hint strings VERBATIM. LocalSource: copy + ASCII-safe slug `local_<8hex>_<ascii_stem>` + broadened CJK rejection on `--out`. ffprobe preflight uniformly applied via `meta.get("video_path")` (covers .mp4/.webm/.mkv); HEVC/AV1 warn-only, missing audio raises clean error. `-vsync vfr` added to existing `cmd_extract_frames` so VFR sources stop dropping frames. requirements.txt yt-dlp pin `>=2026.03.17`; Deno + yt-dlp-get-pot opt-in via CLAUDE.md "首次设置 YouTube ingest（可选）" section. Active requirement "新输入源" moved to Validated. Code review found 0 critical / 2 warning / 5 info — WR-01 (ffprobe extension gate) fixed inline (commit 6b5996e); WR-02 (vtt language priority) deferred to Phase 5. 5 live-runtime checks (B站/YouTube/local mp4 ingest + CJK reject + missing-audio guard) deferred for user execution at convenience — they don't block downstream phases since Phase 4 inherits the unified meta.json contract.*

*2026-05-01 — Phase 4 complete (Frame fps Automation). Validated 7/7 FPS-XX requirements + 5 ROADMAP Success Criteria + 8/8 derived truths. New `agent/scheduler.py` with `Schedule` + `Segment` dataclasses + 5 strict validations (version=1 / full-duration±2s / no overlap / fps XOR skip / no unknown keys) + `ScheduleValidationError`. `extract_frames_batch` CLI consumes schedule.json, validates against ffprobe duration + silence_map.json (graceful fallback when absent — D-08), iterates segments with state.jsonl segment-level resume (Phase 2 D-14 deferred 落地点 via additive `derived_segment_state` helper). FPS-04 silence-coverage strict check uses set-theoretic union per RESEARCH A2; without silence_map falls back to baseline-pass-only. `detect_scenes` (PySceneDetect, default deps via `scenedetect[opencv]>=0.6.7.1`) + `detect_silence` (silero-vad opt-in via `requirements-optional.txt` with torch ~700MB — RESEARCH corrected CONTEXT D-22's incorrect "already in deps" claim) produce read-only JSON artifacts; tools NEVER auto-promote (K5 statically asserted). Existing `cmd_extract_frames` body byte-unchanged (FPS-07 — git diff verified). Active requirement "抽帧策略自动化" moved to Validated. 56+ stdlib unittest tests pass. Code review found 0 critical / 4 warning / 6 info — WR-01 (no start<end check), WR-02 (no fps>0 check), WR-04 (FileNotFoundError leaves dangling started event) classified as future-cleanup quality-guards per verifier recommendation (none violate the 5 SCs). 5 live-runtime checks (extract_frames_batch on real video / mid-segment kill resume / FPS-04 end-to-end / PySceneDetect on real video / WR-01-04 disposition) deferred to user; HUMAN-UAT visible in `/gsd-progress`.*
