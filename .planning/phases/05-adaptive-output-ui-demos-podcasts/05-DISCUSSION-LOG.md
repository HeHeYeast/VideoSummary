# Phase 5: Adaptive Output + UI Demos + Podcasts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered and the user's explicit boundary signal.

**Date:** 2026-05-01
**Phase:** 05-adaptive-output-ui-demos-podcasts
**Mode:** Claude 自决（user 明确指令）
**Areas considered:** 8 个（4 关键 + 4 次要）

---

## 用户指令链路

### Turn 1: 初始 prompt
> "continue phase 5"

### Turn 2: Claude 提出 8 个灰区 multiSelect

Claude 提出的 8 个灰区：
1. 模式分类策略 (TEACH-01)
2. Exemplar skeleton 来源 (TEACH-03)
3. plan.md / depth_plan.md schema (TEACH-04, 05)
4. UI demo & 播客 skeleton 形态 (TEACH-09, 10)
5. Diarization rollout + spike (TEACH-08)
6. 重复保护严重度 (TEACH-11)
7. VAD per-profile 落点 (TEACH-12)
8. WR-02 VTT 优先级 fold-in

第一次 AskUserQuestion 因 4-option cap 报错，Claude 收敛到 4 个最关键灰区准备再问。

### Turn 3: User 反馈
> "我之前说过，除了几个关键的其他全部你自动化来决策。这里你清晰吗，还是说需要再跟我确认一下哪些是需要我来决策的"

### Turn 4: Claude 收敛建议
Claude 提议只拉 2 个灰区（TEACH-03 exemplar + TEACH-08 pyannote spike）作为"必须 user 拍板"，其他 6 个自决。

### Turn 5: User 进一步收紧偏好
> "之前好像有说过phase3和6才有我需要决策的内容，其他的应该都不是真正会主要影响文档质量的"

明确指令：**Phase 5 全部 Claude 自决**，包括 TEACH-03 和 TEACH-08。

### Turn 6: Claude 接受 + 给 8 个决策摘要
Claude 接受偏好，给出 8 个决策的紧凑摘要（见 CONTEXT.md），同步更新 memory feedback_phase_priority.md。

### Turn 7: User 要求决策边界 git-tracked
> "你需要将当前所有phase中需要我决策的挑出来写在文档中，方便后续运行。之前有一个比较明确的界定，但是我clear上下文之后你就不知道了"

Claude 创建 `.planning/DECISION-BOUNDARY.md` —— git-tracked 跨 session 持久化"用户拍板 vs Claude 自决"边界。

---

## 关键灰区（4 个）

### 1. 模式分类策略 (TEACH-01)

**讨论形态：** [Claude 自决]，未拉 user

| Option | Description | Selected |
|--------|-------------|----------|
| 互斥单选 | 4 模式只能 pick 1，结果可能强制选最像的 | |
| 主+辅 hybrid | primary mode + optional secondary tag | ✓ |
| 加权打分 | 4 模式各有 0-1 weight，过设计 | |

**自决方案：** 主+辅 hybrid（D-01 .. D-04）；分类提示放 /summarize-video Phase 2；fallback 到 replicate-guide。
**理由：** REQUIREMENTS "or hybrid" 已软锁；replicate-guide 与 17 archived 一致；保持 K2 "Claude is decider" 红线。

### 2. Exemplar skeleton 来源 (TEACH-03)

**讨论形态：** [Claude 自决]，未拉 user

| Option | Description | Selected |
|--------|-------------|----------|
| (a) 全新原创 | user 手写 8-12 份 skeleton，质量可控但工作量极重 | |
| (b) 17 archived 改 | 风险：全部偏 replicate-guide，4 mode 多样性差 | partial |
| (c) 跑当前 pipeline + reshape | 跑 4 条新视频再 reshape，¥0 但 user 时间成本高 | partial |
| **(b)+(c) 混合** | 全部从已归档 corpus 挑 + reshape，零 ¥0、零 user 时间成本 | ✓ |

**自决方案：** (b)+(c) 混合（D-05 .. D-08）；plan execution 时由 Claude 在归档库挑最贴合的 1 视频/mode reshape；CLAUDE.md 8 份 skeleton 总长 ≤ 1000 行。
**理由：** 路径 (a) 违反 user "我不愿手工写"；(b) 单独偏置；(c) 单独需跑新视频；混合最 ¥0 友好。

### 3. plan.md / depth_plan.md schema (TEACH-04, TEACH-05)

**讨论形态：** [Claude 自决]，未拉 user

| Option | Description | Selected |
|--------|-------------|----------|
| 纯 free-form Markdown | REQUIREMENTS 字面要求；但 mode 字段无结构化入口 | partial |
| 严格 JSON schema | 与 K2 自由度冲突，过设计 | |
| **YAML front-matter + free-form Markdown** | 5 字段 front-matter 装结构化字段，正文随意 | ✓ |

**自决方案：** YAML front-matter + free-form 混合（D-09 .. D-12）；plan.md mandatory；depth_plan.md 独立 optional 文件，Claude 自判触发；不强制 user pause confirm。
**理由：** REQUIREMENTS 字面锁 "no schema enforcement"；front-matter 装饰性，方便 grep / future doctor 子命令读 mode 不强校验。

### 4. Diarization rollout + spike (TEACH-08)

**讨论形态：** [Claude 自决]，未拉 user

| Option | Description | Selected |
|--------|-------------|----------|
| Plan-time spike（阻塞 plan） | 让 user 立刻跑 spike，plan creation 卡住 | |
| **Plan 03 第 1 任务 spike** | 不阻塞 plan creation；user 在 plan 03 execution 时跑 | ✓ |
| 不 spike，直接 ship | 风险：Windows CPU 上 5h+ 跑批 user 不知情 | |

| Option (fallback) | Description | Selected |
|-------------------|-------------|----------|
| Cheap heuristic 2-speaker | 工作量大，质量不如 Claude 内容线索推断 | |
| **无 fallback，pyannote 失败时 speaker_id 留空** | Claude 多模态 + 内容线索可推断说话人 | ✓ |

| Option (HF token) | Description | Selected |
|-------------------|-------------|----------|
| **`.env` 文件读 `HF_TOKEN`** | 与 douyin cookies / VE_KEY_CHEAP idiom 一致 | ✓ |
| Prompt-on-demand | 每次跑都问，体验差 | |

**自决方案：** Spike 推迟到 plan 03 第 1 任务（D-13）；不做 cheap fallback（D-14）；HF token 走 `.env`（D-15）；> 60min CPU-only 时长闸（D-16）。
**理由：** SUMMARY.md 标 pyannote 是"单个最大 ships-or-doesn't 决策"；user 必须自己实测；但作为 plan task 不阻塞。

---

## 次要灰区（4 个）

### 5. UI demo + podcast skeleton 形态 (TEACH-09, TEACH-10) — [Claude 自决]
- Podcast 帧策略：1-2 帧/章节（不完全 skip，保留视觉锚点）
- UI demo 4 子规则按 REQUIREMENTS 字面顺序
- 不分叉 /summarize-video（mode 选完自动走对应 skeleton）

### 6. 重复保护 surfacing (TEACH-11) — [Claude 自决]
- (a) stdout warning + (b) 旁路 `transcribe_warnings.json` 组合
- 3-gram 滑窗，单段 >3× 或跨 ≤3 段重复 >3× 命中
- 绝不 auto-delete，绝不阻断 pipeline

### 7. VAD per-profile 落点 (TEACH-12) — [Claude 自决]
- 落 transcribe（src/asr.py），不落 aggregate
- `--profile` 参数沿 transcribe → aggregate 一路穿
- src/asr.py 加 PROFILES dict（与 agent/asr_v2.py 平行）

### 8. WR-02 VTT 优先级 fold-in — [Claude 自决]
- Fold 进 plan 03（与 podcast 同 plan）
- VTT 语言优先级 zh-Hans > zh-Hant > zh > en > manual > auto
- Podcast 模式当 subtitle_origin=creator 时直接信任 VTT

---

## Claude's Discretion

User 直接放权所有教学/技术细节决策（per 2026-05-01 偏好演化）。具体 Claude 自决的"软选择"包括：
- 每个 mode 的 8 份 skeleton 实际选哪条归档视频做 reshape 素材
- transcribe_warnings.json `context_before` / `context_after` 字符数（默认 200）
- CLAUDE.md "## 视频类型变奏" 章节内部小标题排序
- 4 mode 各自在 CLAUDE.md 中的展开顺序

## Deferred Ideas

- Mode 自动重试机制（auto mode-switch detector）—— v2
- Speaker name resolution（speaker_0/1 → 实名 mapping）—— v2 加 speakers.json
- chapters.json 双向编辑校验 —— v2 加 chapters_check CLI
- UI demo 分辨率自动检测（ffprobe 建议 --width）—— v2
- pyannote on GPU 路径（`--device cuda`）—— v2

## 边界文档

本次 discuss 同时创建 `.planning/DECISION-BOUNDARY.md`（git-tracked），记录跨 session 持久化"用户拍板 vs Claude 自决"边界，覆盖 6 个 phase 的回顾性 + 前瞻性决策状态。

---

*Discussion completed: 2026-05-01*
*Decision authority: Claude 自决（per user feedback）*
*Output: 05-CONTEXT.md (32 decisions across 8 grey areas) + DECISION-BOUNDARY.md (project-level boundary)*
