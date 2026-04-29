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

### Active

<!-- 本次里程碑要建的能力。所有项默认 opt-in，不破坏现有路径。 -->

- [ ] **自适应教学文档** — Claude 看完视频后自行判断这个选题适合哪些教学维度（复刻指南 / 原理讲解 / 延展应用），按视频性质自动调档，去掉"字幕翻译式"输出
- [ ] **抽帧策略自动化** — Claude 读完字幕直出"分段 fps schedule"由工具批量执行，去掉人工凭感觉算 start/end 的摩擦（决策仍 Claude，只是降低操作成本）
- [ ] **新输入源** — YouTube + 通用 yt-dlp 平台 + 本地 mp4 文件路径（不依赖 URL）
- [ ] **新视频类型** — 操作演示（非代码类软件 UI）+ 播客 / 访谈（画面价值低，依赖音频结构组织内容）
- [ ] **中间产物失败可复用** — 任一阶段失败 / 换参 / 换策略后重跑能复用前序 artifact，不丢工作
- [ ] **现有路径 backward-compatible** — 新增能力一律 opt-in 增量叠加；老 CLI、output/ 目录约定、/summarize-video 工作流仍可用，能"快速回退到当前方案"
- [ ] **多 agent 并行**（Nice-to-have） — 多 Claude Code 终端处理不同视频互不干扰，做不到不阻塞 v1

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
| ¥0 成本作为 hard constraint，优先于教学价值 | Claude Max 已覆盖；用户在 "如果只能保住一个性质" 里明确选 ¥0 而非教学价值 | — Pending |
| Claude 自适应单文档，而非多档输出（quick-ref/deep-dive 分离） | 用户认为 Claude 看完视频后判断侧重比固定模板合理；保留输出简洁 | — Pending |
| 老 CLI 与 output/ 目录约定保留，新能力 opt-in 叠加 | 队列里还有 17 条视频要走老路径，新方案不能砸现有归档 | — Pending |
| 多 agent 并行降级为 Nice-to-have | 用户表态"做不到也没关系"，不能阻塞 v1 | — Pending |
| Claude Code 决策权不外移（即使引入抽帧自动化） | 与 CLAUDE.md 既有原则一致：工具是肢体，Claude 是大脑 | — Pending |

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
*Last updated: 2026-04-29 after initialization*
