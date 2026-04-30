# Phase 1: Preflight & Regression Baseline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-30
**Phase:** 01-preflight-regression-baseline
**Areas discussed:** 冻结哪些文件 (用户主动选择)；其余 3 区由 Claude 用推荐默认敲定

---

## 区域 1：基准视频选择 (PRE-01) — Claude 用推荐默认敲定

**背景**：ROADMAP 提名 `BV132wizyEEB` + `godot_brave` + `douyin_trae_ai` 三条作为基准。代码 scout 发现 `output/godot_brave/` 实际只剩 `cookies.txt`，没有可冻结的 `summary.md` / 三件套 JSON，需要替换。

**Claude 评估的候选（均为完整 SMTPF）**：

| 候选 slug | 标题（已修正编码） | 类型 |
|----------|-------------------|------|
| BV1C9QCBdE1U | 【Godot教程】伤害数字生成器：暴击变色、随机漂浮、可复用 | Godot / 代码密集 |
| BV1fLoKBREAN | 【从零开始的Godot游戏开发】#01 引擎安装与瓦片系统基础 | Godot / 入门 |
| BV1x31TYUEbc | godot 如何构建完整的 2D 农场游戏，8小时教程系列 | Godot / 长篇 |
| BV1TrP6zHETD | Godot 4.7 重磅更新 | Godot / 更新报道 |
| BV1s6rDBpEvo | 2D 游戏中的雨天效果 DEV LOG.02 | Godot / DEV LOG |

**Claude 选择**：`BV132wizyEEB` (AI 工作流 / 代码混合) + **`BV1C9QCBdE1U` (Godot / 代码密集)** + `douyin_trae_ai` (AI / UI 演示)

**理由**：BV1C9QCBdE1U 代码密集度最高，最适合验证「代码精确抄录」这一质量红线；其他候选偏向操作演示或更新报道，对代码抄录回归的覆盖弱于 BV1C9QCBdE1U。

---

## 区域 2：schema_version 追加策略 (PRE-03) — Claude 用推荐默认敲定

**问题**：PRE-03 要求 `meta/segs/paragraphs.json` 退档为 `schema_version: 1` 且 loader 在缺字段时默认 1。但 `segs.json` 与 `paragraphs.json` 是顶层 list，无法直接插入字段。

| 选项 | 描述 | 权衡 |
|------|------|------|
| (a) In-place 改 JSON 结构 | 把 list 包成 `{"schema_version":1, "items":[...]}` | **breaking** — 砸 17 条老存档的 loader path，违反 PROJECT.md K3 |
| **(b) Loader-only 容忍** ✓ | 不改任何文件；loader 读 dict 时取 `obj.get("schema_version",1)`，读 list 时一律视作 v1 | 零文件改动，纯 forward-compat；推荐 |
| (c) Sidecar `.schema.json` 文件 | 每个 artifact 旁多一个 `<artifact>.schema.json` | 多一倍文件数；管理复杂 |

**Claude 选择**：(b) Loader-only 容忍

**理由**：与 PROJECT.md「opt-in 增量叠加」一致，与 PITFALLS U2 推荐做法一致，零回归风险。

---

## 区域 3：回归 diff 验证方法 (PRE-02) — Claude 用推荐默认敲定

| 选项 | 描述 | 权衡 |
|------|------|------|
| **(a) Claude 手工 eyeball diff** ✓ | Claude 读两份 summary 做语义对比 | 零脚本，零摩擦；与「Claude 是唯一决策者」一致 |
| (b) 结构化指纹脚本 | `verify_baseline.py` 算行数 / 帧数 / 章节数 | 引入维护成本；定义「通过」边界困难 |
| (c) md5 严格哈希 | 字节级一致 | 不现实 — Claude prose 不是确定性的 |

**Claude 选择**：(a) Claude 手工 eyeball diff

**理由**：与 PROJECT.md K5「Claude 是唯一决策者」哲学一致；Phase 1 不应引入额外脚本资产。

---

## 区域 4：冻结范围 (PRE-01) — 用户主动讨论

**Claude 提供的三个选项 + 体积估算**：

| 选项 | 描述 | 体积（3 视频合计） |
|------|------|-------------------|
| (a) 只 summary.md | 最小 / 仅输出层 | <500KB |
| **(b) summary.md + meta/segs/paragraphs.json** ✓ | 输入 + 输出 | ~1MB |
| (c) 加 frames/audio.wav/video.mp4 | 完整重跑 | 0.5-1GB（git LFS 范畴） |

**用户选择**：(b) summary.md + meta/segs/paragraphs.json

**用户理由（推断）**：体积可接受 (~1MB)；能验证 PRE-03 loader 容忍（git checkout 后直接拷贝 JSON 进 output/，跳过 transcribe/aggregate 重跑）；frames/audio/video 进 git 不可行。

---

## Claude's Discretion

以下细节用户没有特别要求，由 planner / executor 决定：
- `tests/` vs `.planning/regression/` 的位置选择
- `regression-check.md` 是 Markdown 还是带 fenced shell 命令的可粘贴 runbook
- Loader-tolerance 改动落点（集中到新模块 vs in-place patch）
- encoding-audit 证据是单文件还是嵌入 regression-check.md
- `docs/schema-versions.md` 是独立文件还是嵌入 CLAUDE.md / AGENT_DESIGN.md

## Deferred Ideas

讨论中没有出现 scope creep，所有 deferred items 均为 Claude 主动识别的「未来可能但本 milestone 不做」事项，已记录在 CONTEXT.md `<deferred>` 中：
- 结构化回归脚本（如 `verify_baseline.py`）
- `tests/regression/` snapshot 自动更新机制
- pytest-regressions / GoldenStorm fixture 框架
- Frame-level 回归
- schema_version v2 真实迁移代码

---

*Discussion log written: 2026-04-30*
