# Phase 2: Resume Infrastructure & Cache Correctness - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-01
**Phase:** 02-resume-infrastructure-cache-correctness
**Areas discussed:** N/A — user 表态本 phase 属"基础设施边缘 phase"，不介入灰色决策。Claude 自决。

---

## User 决策权委托

**User 原话**:

> 我感觉第一个phase和当前phase都是我不关心的内容，我只关心你对当前工作流做了哪些改动来提高整体文档质量，但是当前两个phase都比较边缘。这些你都可以自己决定，合理即可

**解读**:
- User 的关注焦点是 `/summarize-video` 工作流输出文档的**教学质量**，对应 milestone 中的 Phase 5 TEACH（自适应教学输出）
- Phase 1 PRE / Phase 2 RES 在 user 视角是"前置基础设施"，不直接影响输出文档形态
- User 授权 Claude 自决 Phase 2 所有灰色决策，仅要求"合理即可"
- 这条偏好已记入 memory: `feedback_phase_priority.md`，未来对 Phase 6 PARA（Nice-to-have 并行）也按此模式处理

---

## 原本拟议的灰色决策（保留作 audit）

Claude 在分析阶段识别出 4 个值得用户介入的灰色决策，但 user 表态后全部由 Claude 自决：

### 1. 归档兼容策略（17 archives 无 sidecar 时的行为）

| Option | Pros | Cons | Selected |
|--------|------|------|----------|
| (a) 视为"匹配"补写 sidecar | 零摩擦 | 永久遮蔽 stale-reuse 隐患 | |
| (b) Loud log + 不重生 | 既不破坏历史，又留可见信号 | 用户首次重跑时会看到 warning | ✓ (CONTEXT.md D-01) |
| (c) 强制重生 | 所有 archive 立即合规 | 破坏 K3 backward-compat（30-200MB 重下载 + 长 ASR） | |
| (d) 标记 legacy 永不检查 | 最小变化 | 失去整个 sidecar 机制对历史产物的价值 | |

**Claude 选择**: (b) — `log.warning("no params.json for %s; cannot validate cache freshness — pass --force to regenerate with sidecar capture", path)`，走原 file-existence 路径返回缓存。
**理由**: 平衡 K3（17 archive 不可破坏）与 K5（Claude 决策权 — 不擅自重生）。

### 2. params.json 字段范围

| Option | Pros | Cons | Selected |
|--------|------|------|----------|
| (a) 仅 CLI flag | 最简单 | 漏掉 hard-coded 函数默认值（aggregate gap 等） | |
| (b) CLI flag + 函数关键参数 | 完整覆盖输出语义 | 需要把 hard-code 默认值暴露 | |
| (c) (b) + 工具版本 | 捕获 ffmpeg / faster-whisper 升级风险 | 引入"工具升级伪 churn" | ✓ (CONTEXT.md D-05/D-07) |
| (d) (c) + 环境变量 (ASR_DEVICE 等) | 最广 | ASR_DEVICE 改 cuda 输出语义不变，纯 churn | |

**Claude 选择**: (c) 但分组 — `cli` / `func` / `tools` 三段，前两段不匹配触发重生，`tools` 段不匹配仅 warning，由用户决定 `--force`。
**理由**: 工具版本对输出影响是概率性的，把硬规则留给确定性参数。

### 3. state.jsonl 设计

| 维度 | 选项 | Selected |
|------|------|----------|
| 物理形式 | (i) JSON Lines (.jsonl) / (ii) 顶层 list (.json) | (i) jsonl (D-12) |
| 粒度 day-1 | stage-only / stage + segment-frame | stage-only，segment 延 Phase 4 (D-14) |
| 损坏恢复 | 自动 truncate / 警告 + 不再读 / 阻塞 | 警告 + session 内不再读 (D-03) |

**理由**: jsonl 真 append-only 在 mid-write crash 时单行损坏可定位丢弃；segment 级提前是 over-engineering（当前无 batch 抽帧）。

### 4. doctor + schema-migration runbook 形态

| 维度 | 选项 | Selected |
|------|------|----------|
| doctor 输出 | 纯文本 / +--json / +--diff / +color | 纯文本 + --json (D-15) |
| doctor 列 | 3 列(基础) / 5 列(含 sidecar+state) | 5 列 (D-16) |
| migration 文档深度 | 占位 / 含示例 / 含示例+测试 checklist | 含示例 + 测试 checklist (D-19) |
| migration 落点 | docs/ / tests/regression/ / CLAUDE.md 嵌入 | docs/schema-migration.md (D-18) |

**理由**: 颜色 / `--diff` 都是 YAGNI；migration 文档如果不含示例就和不写一样（占位永远不会真的指导第一次迁移）。

---

## Claude's Discretion

User 授权 Claude 自决整个 Phase 2，下列细节是显式 Claude's Discretion：
- atomic-write helper 内部 tempfile 命名前缀
- params_hash sha256 截断长度（建议 16 hex）
- doctor 表格 ASCII 边框样式
- state.py reducer 是否提供 `__main__` 调试入口
- 第一次写 sidecar 时是否打印路径确认
- `aggregate_paragraphs` / `transcribe` 哪些内部 default 进入 sidecar `func` 段

详见 `02-CONTEXT.md` `<decisions>` §"Claude's Discretion"。

## Deferred Ideas

详见 `02-CONTEXT.md` `<deferred>` §"Deferred Ideas"。重点：`step_log.json` provenance、Whisper server 持久化、cache 含 video hash、segment-级 frame 事件、doctor `--diff` flag、真实 v1→v2 迁移代码 — 全部已记录推迟原因与重启触发条件。
