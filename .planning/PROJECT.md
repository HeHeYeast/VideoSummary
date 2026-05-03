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
- ✓ **D-29 byte-equal 基础设施** — `agent/_v11.py` opt-in marker (`output/<slug>/.v11_features.json`，15 entries 跨 v1.1 三 phase) gates ALL v1.1 paths；`scripts/replay_v10_archives.py` 17-archive 字节相等 regression test (33 PASS / 0 FAIL)；3 representative archive `.token_budget.json` baselines — v1.1 Phase 07 (PRE-V11-01/02/03)
- ✓ **Summary 正确性自动化（D-02 三层校验）** — L1 ASR `transcribe_lint` (5 strategies inc. pypinyin homophone_cluster) + L2/L3 prompts in CLAUDE.md (max 10 corrections, ≥ 2 evidence sources, ≤ 5 frames/warning) + CORR-02 inline trace tokens with 3-tier eligibility + CORR-03b Phase 7.5 verifier subagent (`Task(general-purpose)` scope-locked, FORBIDDEN pedagogical critique) + CORR-03c delta auto-rewrite max-1 with `summary.md.pre-review` backup + UNRESOLVED.md fallback + `VIDEOSUMMARY_SKIP_REVIEWER=1` env degrade — v1.1 Phases 07+08+09 (CORR-01a/b/c, CORR-02, CORR-03a/b/c)
- ✓ **零基础自包含 summary（D-01）** — 每 summary 顶部 自包含 header (你需要 ≤ 3行 / 你不需要 ≤ 3行) + first-mention inline 术语注解 (FORBIDDEN universal terms Python/JSON/Claude) + cross-slug `output/_glossary.md` accumulator (FileLock 串行化 / first-seen-wins / inline-first invariant) + 长视频 5-min TL;DR speedrun (>20min OR >50 sections, write LAST, 10-15 line cap, zero citations) — v1.1 Phase 08 (TEACH-A1/A2/A3, TEACH-B)
- ✓ **K5 决策辅助 signal emitters** — `mode_signals.json` (5 objective signals, no `recommended_mode` field) + `schedule_suggestion.json` (combines paragraphs + scenes + silence_map, with `--duration` override) + `glossary_audit` (read-only) + `summary_lint` (4+1 format invariants + citation density + glossary drift). 13 K5 boundary static-asserted tests (intent-correct write-pattern regex per Phase 07-03 deviation #2 + Phase 08-01 lessons) — v1.1 Phases 07+09 (TOOL-A, TOOL-B, CORR-03a)
- ✓ **运维杂项打杂** — AV1 codec WARNING demoted to INFO；cross-terminal `python -m agent.tools queue {add\|list\|next\|done\|skip}` CLI with `~/.videoSummary/.queue.lock` 串行化 + `in_progress: <pid>` marker + 5-subprocess race test passes — v1.1 Phase 07 (MISC-01, MISC-02)
- ✓ **Topic taxonomy governance layer** — `output/_topics.md` governance 文件 (顶部 Approved + 底部 Pending 段) + 3 nested CLIs (`topics bootstrap` / `audit` / `resolve`) + governance Pending 申请闭环；24 nodes / 5 categories ground-truth taxonomy；K5 边界 statically asserted；FileLock 序列化 (`output/.topics.lock`) — v1.2 Phase 10 (KB-07..KB-11)
- ✓ **per-slug index.json + 顶层聚合 + Phase 7.6 hook** — `agent/index.py` 5 public functions + `glossary_h2_anchors` helper + 8 字段 schema lock；`/summarize-video` Phase 7.6 hook 让新视频自动同步生成 (`### Phase 7.6` H3 in CLAUDE.md L1836); keywords 优先复用 `_glossary.md` H2 anchors；顶层 `output/.index.json` atomic auto-rebuild — v1.2 Phase 11 (KB-01..KB-06)
- ✓ **23-archive backfill + 自然语言推荐 prompt rule + search/list CLI** — 33 archives backfilled via `index backfill --all` + per-slug `index write --from-stdin --force` loop；`output/.index.json` aggregator 33 entries lex-sorted；CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 (L1625) 触发 phrase 锁 + FIRST ACTION + 推荐回复格式锁 + 6-entry FORBIDDEN list (anti-hallucination)；`index search/list` 兜底 CLI — v1.2 Phase 12 (KB-12..KB-15, KB-MISC-01)

### Active

<!-- v1.2-knowledge-base milestone shipped 2026-05-03. 2 manual UAT items deferred (Phase 11 KB-02 + Phase 12 KB-15 — both inherent to design, mirror v1.1 P-09 pattern). v1.1 5 manual UAT 项仍 deferred. 下次里程碑通过 /gsd-new-milestone 重新规划。 -->

(none — v1.2 shipped; pending manual UATs tracked in 11-HUMAN-UAT.md + 12-HUMAN-UAT.md + v1.1 deferred items)

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
| v1.1 一次 ship 全部 8 候选（必做 4 + 想做 2 + 顺手 2） | 用户主动调 /gsd-new-milestone 时选 "全做"；v1.0 工具链已稳，质量铁律必须一次落地不分批 | ✓ Good — v1.1 shipped 2026-05-03，18/18 reqs delivered |
| v1.2 锁死 D-01..D-09（9 条架构决策） | v1.1 ship 后用户实测产生明确意图："开 claude code 会话，让他给我推荐我需要学习的视频" + "逐个遍历 chapter 不太合理" + "给一组预定义的 topic 让 claude 挑" + "backlink 先 drop 吧" + "推荐用自然语言不加 slash command" — 9 D-XX 是用户原话翻译为设计契约 | ✓ Good — v1.2 shipped 2026-05-03，16/16 reqs delivered，9 D-XX honored byte-equal |
| v1.2 知识库消费者 = Claude（D-01） | 用户原话："开 claude code 会话，说明需求，让他给我推荐"。索引格式优先 Claude 友好（结构化 JSON），不优先人类 grep 友好；markdown 索引一律不做（_glossary.md 已是术语索引） | ✓ Good — v1.2 KB-01 8 字段 JSON schema + 顶层 .index.json aggregator 33 entries |
| v1.2 颗粒度 = summary keywords + chapter 导航锚点（D-02） | 用户原话："逐个遍历 chapter 来获取关键词不太合理"。每 chapter 重新抽 keywords 是过度切碎；keywords 在 summary 维度匹配，chapter 只做"找到之后跳转"用 | ✓ Good — v1.2 index.json schema 中 chapter 无独立 keywords 字段（仅 title + start + excerpt） |
| v1.2 backlink drop（D-07） | 用户原话："先 drop 吧，我感觉作用也不大"。single-user 23 条规模 over-engineering；跨 summary 关联完全靠 Claude 在会话里 Read .index.json 即时计算即可 | ✓ Good — v1.2 index.json schema 不含 related_slugs；summary.md 不加 "## 相关推荐" 段 |
| v1.2 推荐入口 = 自然语言不加 slash command（D-09） | 用户原话："开 claude code 会话，说明我当前的需求"，已习惯自然语言；slash command 是 nice-to-have 不是必须；少加一个 phase 减低迭代成本 | ✓ Good — v1.2 KB-14 落地 CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 段，7 触发 phrase + FIRST ACTION + 3-line 推荐格式锁 + 6-entry FORBIDDEN anti-hallucination list |
| v1.2 topic taxonomy 走 K5 governance（D-04） | 用户原话："给出一组预定义的 topic，然后 claude 从中挑，如果 claude 需要新增主题关键词可以提出请求"。K5 边界延伸到 governance — Claude 决策选/申请，但用户决定批 Pending | ✓ Good — v1.2 Phase 10 ship `_topics.md` Approved + Pending 段 + 3 CLI；首次 bootstrap 默认批（24 nodes from 22+ archives ground truth） |

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
*Last updated: 2026-05-03 — v1.2 knowledge-base milestone shipped. 3 phases (10-12) / 6 plans / 11 tasks. All Active v1.2 requirements moved to Validated. Audit: 16/16 requirements satisfied (100%), 3/3 phases verified, 7/7 integration points, 4/4 E2E flows complete, 297 tests pass (+75 net new from v1.1 baseline 222), K5 boundary count 17→23 (+6), D-29 33/0/30 byte-equal preserved. **Status: tech_debt** — 2 manual UAT items deferred (Phase 11 KB-02 + Phase 12 KB-15, both inherent to v1.2 design — Python orchestrators cannot auto-invoke `/summarize-video` Claude slash command nor simulate fresh-session recommendation behavior) + 1 cosmetic finding (`topics audit` "Misc" orphan note). v1.1 5 manual UAT items still deferred (independent of v1.2). See `.planning/MILESTONES.md` and `.planning/milestones/v1.2-MILESTONE-AUDIT.md`. Next milestone via `/gsd-new-milestone`.*

*2026-05-03 — v1.1 summary-quality milestone shipped. 3 phases (07-09) / 7 plans / 19 tasks. All Active v1.1 requirements moved to Validated. Audit: 18/18 requirements (1 partial pending manual gate), 3/3 phases, 8/8 integration, 4/4 E2E flows verified, 196 tests pass, D-29 33/0/30 byte-equal preserved. **Status: tech_debt** — 5 manual UAT items + 6 info findings deferred (all inherent to v1.1 design — Python orchestrators cannot auto-invoke `/summarize-video` Claude slash command). See `.planning/MILESTONES.md` and `.planning/milestones/v1.1-MILESTONE-AUDIT.md`.*

*2026-05-02 — v1.0 milestone shipped. 6 phases / 16 plans / 31 tasks. All Active requirements moved to Validated. Audit: 52/52 requirements satisfied, 6/6 phases passed, 4/4 E2E flows verified. See `.planning/MILESTONES.md` and `.planning/milestones/v1.0-MILESTONE-AUDIT.md`.*

*Earlier evolution log:*

*2026-04-30 — Phase 1 complete (regression baseline frozen; agent.io schema-tolerant loaders landed; encoding audit + Windows zh-CN docs shipped). No Active requirements moved to Validated yet — Phase 1 is gating infrastructure that ENABLES "现有路径 backward-compatible" but does not tick it off until later phases land without breaking baselines.*

*2026-05-01 — Phase 2 complete (Resume Infrastructure & Cache Correctness). Validated 13/13 must-haves: 5 ROADMAP Success Criteria + 8 RES-XX requirements. Atomic JSON writes (tempfile + os.replace + 3×0.5s PermissionError retry), 3-segment sidecar (cli/func/tools) with severity-split cache decision, JSON Lines `state.jsonl` event log + corruption-tolerant `derived_state` reducer, `doctor` 5-column read-only subcommand + `--json` flag, and `docs/schema-migration.md` runbook. Active requirement "中间产物失败可复用" moved to Validated (live-tested whisper small→medium triggers loud regen). Code review found 0 critical / 6 warning / 6 info (advisory follow-ups, none invalidate goal achievement). 17-archive backward-compat preserved: missing-sidecar path → loud warning + reuse cache (D-01); state.jsonl absent → file-existence cache fallback (D-03).*

*2026-05-01 — Phase 3 complete (Source Refactor + New Sources). Validated 13/13 SRC-XX requirements + 5 ROADMAP Success Criteria. New `agent/sources/` package with Source Protocol + 5 source classes (Douyin / YouTube / Bilibili / Local / Generic) + pure-function `url_router.route()`; `ingest` CLI subcommand canonical, `download` shim preserved (K3 backward-compat). YouTube layer: 2-second `yt-dlp --simulate` preflight + 5-class stderr classifier (po_token_required > cookies_stale > yt_dlp_outdated > gfw_blocked > other) with locked Chinese hint strings VERBATIM. LocalSource: copy + ASCII-safe slug `local_<8hex>_<ascii_stem>` + broadened CJK rejection on `--out`. ffprobe preflight uniformly applied via `meta.get("video_path")` (covers .mp4/.webm/.mkv); HEVC/AV1 warn-only, missing audio raises clean error. `-vsync vfr` added to existing `cmd_extract_frames` so VFR sources stop dropping frames. requirements.txt yt-dlp pin `>=2026.03.17`; Deno + yt-dlp-get-pot opt-in via CLAUDE.md "首次设置 YouTube ingest（可选）" section. Active requirement "新输入源" moved to Validated. Code review found 0 critical / 2 warning / 5 info — WR-01 (ffprobe extension gate) fixed inline (commit 6b5996e); WR-02 (vtt language priority) deferred to Phase 5. 5 live-runtime checks (B站/YouTube/local mp4 ingest + CJK reject + missing-audio guard) deferred for user execution at convenience — they don't block downstream phases since Phase 4 inherits the unified meta.json contract.*

*2026-05-01 — Phase 4 complete (Frame fps Automation). Validated 7/7 FPS-XX requirements + 5 ROADMAP Success Criteria + 8/8 derived truths. New `agent/scheduler.py` with `Schedule` + `Segment` dataclasses + 5 strict validations (version=1 / full-duration±2s / no overlap / fps XOR skip / no unknown keys) + `ScheduleValidationError`. `extract_frames_batch` CLI consumes schedule.json, validates against ffprobe duration + silence_map.json (graceful fallback when absent — D-08), iterates segments with state.jsonl segment-level resume (Phase 2 D-14 deferred 落地点 via additive `derived_segment_state` helper). FPS-04 silence-coverage strict check uses set-theoretic union per RESEARCH A2; without silence_map falls back to baseline-pass-only. `detect_scenes` (PySceneDetect, default deps via `scenedetect[opencv]>=0.6.7.1`) + `detect_silence` (silero-vad opt-in via `requirements-optional.txt` with torch ~700MB — RESEARCH corrected CONTEXT D-22's incorrect "already in deps" claim) produce read-only JSON artifacts; tools NEVER auto-promote (K5 statically asserted). Existing `cmd_extract_frames` body byte-unchanged (FPS-07 — git diff verified). Active requirement "抽帧策略自动化" moved to Validated. 56+ stdlib unittest tests pass. Code review found 0 critical / 4 warning / 6 info — WR-01 (no start<end check), WR-02 (no fps>0 check), WR-04 (FileNotFoundError leaves dangling started event) classified as future-cleanup quality-guards per verifier recommendation (none violate the 5 SCs). 5 live-runtime checks (extract_frames_batch on real video / mid-segment kill resume / FPS-04 end-to-end / PySceneDetect on real video / WR-01-04 disposition) deferred to user; HUMAN-UAT visible in `/gsd-progress`.*
