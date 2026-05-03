# Roadmap: videoSummary

## Milestones

- ✅ **v1.0 — videoSummary v1.0** — Phases 01-06 (shipped 2026-05-02). Full archive: [`.planning/milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 — summary-quality** — Phases 07-09 (shipped 2026-05-03). Full archive: [`.planning/milestones/v1.1-ROADMAP.md`](milestones/v1.1-ROADMAP.md)
- 🔄 **v1.2 — knowledge-base** — Phases 10-12 (started 2026-05-03). 16 v1.2 requirements (15 必做 + 1 顺手), granularity=coarse.

## Phases

<details>
<summary>✅ v1.0 (Phases 01-06) — SHIPPED 2026-05-02</summary>

- [x] Phase 01: Preflight & Regression Baseline (3/3 plans) — completed 2026
- [x] Phase 02: Resume Infrastructure & Cache Correctness (3/3 plans) — completed 2026
- [x] Phase 03: Source Refactor + new sources (YouTube + Local mp4 + Generic) (3/3 plans) — completed 2026
- [x] Phase 04: Frame fps Automation (`schedule.json` + `extract_frames_batch`) (2/2 plans) — completed 2026
- [x] Phase 05: Adaptive Output + UI Demos + Podcasts (3/3 plans) — completed 2026-05-02
- [x] Phase 06: Multi-Agent Parallelism (Nice-to-Have, shipped) (2/2 plans) — completed 2026-05-02

See archive for full phase details, plans, and verification.

</details>

<details>
<summary>✅ v1.1 (Phases 07-09) — SHIPPED 2026-05-03</summary>

- [x] Phase 07: Warm-up + K5 emitters + D-29 foundation (3/3 plans) — completed 2026-05-03
- [x] Phase 08: Writing rules — CLAUDE.md extensions + glossary (2/2 plans) — completed 2026-05-03
- [x] Phase 09: Correctness automation — verifier subagent + auto-rewrite (2/2 plans) — completed 2026-05-03

See archive for full phase details, plans, and verification.

</details>

### v1.2 — knowledge-base

- [x] **Phase 10: Topic taxonomy governance + bootstrap CLI** — `output/_topics.md` 顶部已批准 + 底部 `# Pending` 段；3 CLI（`topics bootstrap` 从 17 archives 归纳初始 taxonomy / `topics audit` 列 pending + 引用计数 + 孤儿 / `topics resolve` 把 pending 挪到正式段并自动更新 index.json 引用）；governance 闭环锁定（Claude 写 index.json 时只能从已批准段选；不合适 → append `# Pending`，K5 边界延伸到 governance）。零 summary.md mutation。 (completed 2026-05-03)
- [x] **Phase 11: per-slug index.json + 顶层聚合 + Phase 7.6 hook** — KB-01 schema 锁（`slug / title / duration_s / mode / topics[] / keywords[] / tldr_oneliner / chapters[]`，chapter 无独立 keywords 字段 per D-02）+ `/summarize-video` Phase 7.6 自动写（在 Phase 7 写完 summary.md 之后、Phase 8 cleanup 之前）+ keywords 优先复用 `_glossary.md` H2 anchors + 顶层 `output/.index.json` atomic rebuild + 手动 `index rebuild` CLI 兜底 + D-29 byte-equal 33/0/30 仍 PASS（index.json 是新 sidecar 不在 replay 比对范围）。 (completed 2026-05-03)
- [ ] **Phase 12: 17 archives backfill + CLAUDE.md 推荐 prompt rule + search/list CLI** — `index backfill --all` 一次性给 17 v1.0/v1.1 archives 写 index.json（idempotent；`--force` 覆盖；单 slug 失败不阻塞其他）+ CLAUDE.md `## v1.2 知识库自然语言推荐入口` 段（触发 phrase 锁定 + FIRST ACTION = `Read output/.index.json` + 推荐回复格式锁 + anti-hallucination FORBIDDEN list）+ `index search/list` 兜底 CLI（顺手做）+ 末尾再跑一次 D-29 replay 确认 33/0/30。

## Phase Details

### Phase 10: Topic taxonomy governance + bootstrap CLI
**Goal**: 立起 v1.2 知识库的"词表层"——`output/_topics.md` governance 文件 + 3 个 CLI 让 Claude 写 index.json 时有可选 topic 集合，且新概念走"申请 Pending → 用户偶尔 review"的 K5 governance 闭环。零 summary.md / index.json mutation；Phase 11 / 12 全部依赖本 phase 提供的"已批准 topic 集合"。
**Depends on**: v1.1 Phase 09（复用 `output/_glossary.md` 形态作 governance 文件参照；复用 `agent/_lock.py` FileLock 模式给 `_topics.md` 写串行化）
**Requirements**: KB-07, KB-08, KB-09, KB-10, KB-11
**Success Criteria** (what must be TRUE):
  1. **`output/_topics.md` 文件结构 byte-locked** — 文件包含 2 个固定段：顶部 `## Approved Taxonomy`（按 category 树状缩进）+ 底部 `## Pending`（每条带申请来源 slug + chapter title + 提议理由 3 字段）。文件存在与否 idempotent：CLI invoke 前不存在 → bootstrap 写；存在 → audit/resolve 读改写不破坏既有 approved 段。
  2. **`python -m agent.tools topics bootstrap` 一次性扫 17 archives 产出非空初始 taxonomy** — 跑 `topics bootstrap` 后 `output/_topics.md` 顶部 `## Approved Taxonomy` 段非空，包含从 17 archives summary.md / `_glossary.md` 归纳出的 category 树（如 `LLM / Game-Dev / Tooling / Agent / ...`）。首次 bootstrap 默认批（ground truth），不进 Pending 段。重复跑 idempotent（已存在 → no-op + 提示）。
  3. **`python -m agent.tools topics audit [--json]` 输出 pending 队列 + 引用计数 + 孤儿检测** — 命令读 `output/_topics.md` + 扫所有 `output/<slug>/index.json`（如有），输出三段报告：(a) `## Pending` 段所有 entry + 申请来源；(b) 每个 approved topic 的引用计数（# of slugs referencing it）；(c) 孤儿 topic 检测（approved 但 0 slug 引用）。`--json` flag 给 Claude consumption（结构化输出）。**只读** — 永不改 `_topics.md`（K5 边界）。
  4. **`python -m agent.tools topics resolve <pending-name> [--rename <new>]` 把 pending 挪到正式段并自动更新所有引用 index.json** — 命令把 `## Pending` 中的 entry 移到 `## Approved Taxonomy`（可选 rename）；同时扫 `output/<slug>/index.json` 中所有 `topics: ["pending: <name>"]` → 改为 `topics: ["<name>"]`（rename 时改成 new 名）。Atomic write 保证 _topics.md + 多个 index.json 一起改完才落盘。
  5. **Claude 申请新 topic 走 governance 闭环（K5 边界 statically asserted）** — Phase 11 写 index.json 时遇到现有 approved topic 都不合适 → 在 `## Pending` 段 append（必填 3 字段：申请来源 slug + chapter title + 提议理由），该 chapter `topics: ["pending: <name>"]`。Approved topics 从 `output/_topics.md` 顶部段读取作为白名单。CLI source-grep 测试断言 `topics bootstrap/audit/resolve` 三个 cmd 不写 `index.json` / `summary.md`（K5 boundary，mirror v1.1 K5 emitter 静态断言模式）。
**Plans**: 2 plans
- [x] 10-01-PLAN.md — agent/topics.py module + 3 nested CLI subcommands + 4 K5 boundary tests + behavior tests (Wave 1, autonomous)
- [x] 10-02-PLAN.md — first real `topics bootstrap` invocation: Claude reads 17+ archives, proposes JSON taxonomy, populates output/_topics.md (Wave 2, autonomous, depends_on 10-01)

### Phase 11: per-slug index.json + 顶层聚合 + Phase 7.6 hook
**Goal**: 落地 v1.2 知识库的"中颗粒索引层"——给每个 `output/<slug>/` 写 `index.json`（schema 锁死 8 字段），keywords 优先复用 `_glossary.md` H2 anchors 避免分裂，顶层 `output/.index.json` atomic rebuild 让 Claude 一次 Read 拿全 23+ 条概览。`/summarize-video` Phase 7.6 hook 让新视频自动同步生成；老归档 backfill 复用同一 generator（Phase 12 用）保证一致性。D-29 byte-equal 33/0/30 仍 PASS（index.json 是新 sidecar 不在 replay 比对范围）。
**Depends on**: Phase 10（必须先有 `output/_topics.md` 已批准段供 Claude 选 topic；新概念走 Pending 申请闭环）
**Requirements**: KB-01, KB-02, KB-03, KB-04, KB-05, KB-06
**Success Criteria** (what must be TRUE):
  1. **per-slug `output/<slug>/index.json` schema 锁死且 8 字段全填** — 处理一条新视频后，`output/<slug>/index.json` 存在，含 8 字段：`slug` (string) / `title` (string) / `duration_s` (number) / `mode` (4 modes 之一) / `topics[]` (array of approved topic names from `_topics.md`，可能含 `pending: <name>`) / `keywords[]` (array of strings，优先来自 `_glossary.md` H2 anchors) / `tldr_oneliner` (string，1 行视频核心) / `chapters[]` (array of `{title, start, excerpt}`，**每项无独立 keywords 字段** per D-02)。Schema 缺一字段 = 生成失败。
  2. **`/summarize-video` Phase 7.6 hook 自动生成 index.json + 立刻 rebuild 顶层** — `/summarize-video` 工作流在 Phase 7 写完 `summary.md` 之后、Phase 8 cleanup 之前，**自动**调用 generator 写 per-slug `index.json`，**然后立刻**扫所有 `output/*/index.json` rebuild 顶层 `output/.index.json`（atomic write）。CLAUDE.md `## /summarize-video 完整工作流` 段加 Phase 7.6 子步骤 + 自然位置（Phase 7.5 verifier 之后、Phase 8 cleanup 之前）。新视频用户零操作（D-03 自动化优先）。
  3. **顶层 `output/.index.json` 自动同步 + atomic rebuild + stale detection** — 顶层文件 schema = `{"<slug>": <per-slug-index>, ...}` 扁平合并（无 `related_slugs` 字段，per D-07）。每次 per-slug index.json 写入触发 rebuild；体积 ~5-10KB（23 条 × 100-300 字/条）让 Claude 一次 Read 拿全。`python -m agent.tools index rebuild` 手动兜底 CLI 跑出相同结果（idempotent）；命令具备 stale detection（per-slug index.json mtime 比顶层 .index.json 新时显式提示哪些 slug 待 rebuild）。
  4. **keywords 优先复用 `output/_glossary.md` H2 anchors 避免术语分裂** — generator 抽 keywords 时先读 `output/_glossary.md` 所有 H2 anchors（v1.1 已 ship 的 cross-slug 术语累积），把 summary.md 里命中的 H2 anchor term 作为 keyword 候选优先选；新概念才创造新 keyword。验证：跑 generator 在含 "LoRA" 术语的 archive 上，输出 keyword 必须 byte-equal `_glossary.md` 中的 canonical 形式（如 `LoRA (Low-Rank Adaptation)`），而不是 `Lora` / `low-rank adaptation` 散落形式。
  5. **D-29 byte-equal 33/0/30 仍 PASS（index.json 是新 sidecar 不在 replay 比对范围）** — Phase 11 ship 后跑 `python scripts/replay_v10_archives.py` 输出 33 PASS / 0 FAIL / 30 archives 比对 4 核心文件（summary.md / segs.json / paragraphs.json / meta.json）byte-equal。`index.json` 作为新 sidecar **不**进 replay 比对集；任一字节 diff 在 4 核心文件上 → phase NOT shippable。Phase 11 verification 主动跑一次确认。
**Plans**: 2 plans
- [x] 11-01-PLAN.md — agent/index.py module + cmd_index_{write,rebuild} + 3 K5 boundary tests + behavior tests (Wave 1, autonomous)
- [x] 11-02-PLAN.md — CLAUDE.md /summarize-video Phase 7.6 hook insertion + D-29 byte-equal close gate + 11-02-SUMMARY (Wave 2, autonomous, depends_on 11-01)

### Phase 12: 17 archives backfill + CLAUDE.md 推荐 prompt rule + search/list CLI
**Goal**: v1.2 收尾——把 Phase 11 的 generator 复用到 17 v1.0/v1.1 archives 上一次性 backfill 写 index.json，让 Claude 一开会话 Read 顶层 `.index.json` 就能看全 23 条；CLAUDE.md 加自然语言推荐 prompt rule（D-09 锁，不加 slash command，mirror v1.1 anti-hallucination 字面规则风格）；顺手 ship `index search/list` 兜底 CLI；末尾再跑一次 D-29 replay 确认 33/0/30。E2E 用户行为：用户在新会话说"推荐 LLM Wiki 相关的视频"→ Claude FIRST ACTION Read `.index.json` → 返回 top-N 带 chapter 入口。
**Depends on**: Phase 10（taxonomy 已 bootstrap）+ Phase 11（generator + 顶层 rebuild + Phase 7.6 hook 全部 ready）
**Requirements**: KB-12, KB-13, KB-14, KB-15, KB-MISC-01
**Success Criteria** (what must be TRUE):
  1. **17 v1.0/v1.1 archives 全部有 index.json + 顶层 .index.json 含 17 条** — 跑 `python -m agent.tools index backfill --all` 后，所有 17 个 `output/<slug>/` 目录下 `index.json` 存在并通过 schema 校验（8 字段全填 per Phase 11 SC#1）；顶层 `output/.index.json` 含 17 条扁平 entry。命令 idempotent（已有 index.json 默认 skip，`--force` 覆盖）；error tolerance（单 slug summary.md 损坏 → 该 slug 失败但其他继续，最后 stdout 报告失败列表 + exit code 非 0）。6 队列视频不需要 backfill（通过 Phase 11 hook 同步生成）。
  2. **D-29 byte-equal 33/0/30 仍 PASS（backfill 后再验证一次）** — 17 archives backfill 完后再跑 `python scripts/replay_v10_archives.py` 输出 33 PASS / 0 FAIL。`index.json` sidecar 不破 4 核心文件（summary.md / segs.json / paragraphs.json / meta.json）byte-equal 不变量。任一字节 diff → phase NOT shippable + 立刻回滚 backfill 产出物。
  3. **CLAUDE.md 推荐 prompt rule 段落 byte-locked（mirror v1.1 anti-hallucination 风格）** — CLAUDE.md 顶层加 `## v1.2 知识库自然语言推荐入口` 段，含 3 部分：(a) 触发 phrase 锁定（'推荐' / '相关' / '我之前看过' / '学过' / '找一下我' / '哪些视频' / 类似查询意图）；(b) FIRST ACTION = `Read output/.index.json`（missing 时 hint user 跑 `index rebuild`）；(c) 推荐回复格式锁（每条 = 1 行 slug+title+共享匹配信号 + 1 行 tldr + 1-3 个 chapter 入口）+ FORBIDDEN list（编造 .index.json 里没有的 slug / 推荐不存在的视频，mirror v1.1 5th format-spec invariant 的字面规则风格）。
  4. **E2E 自然语言推荐行为可观测（人工验证 gate）** — 用户在新 Claude Code 会话说 "推荐 LLM Wiki 相关的视频" / "我之前看过哪些 ECS 相关的视频" / "学习 Godot 的话推荐什么" → Claude FIRST ACTION Read `output/.index.json` → 输出符合 prompt rule 格式锁的 top-3 推荐（每条 slug+title+匹配信号 + tldr + 1-3 chapter 入口），且所有推荐的 slug 都真实存在于 `.index.json`（无幻觉）。Phase 12 verification 跑 1-2 次手工 query 确认行为锁。
  5. **`python -m agent.tools index search/list` 兜底 CLI 工作** — `index search <query>` keyword 子串匹配（text 输出 + `--json` flag）；`index list [--topic <topic>] [--mode <mode>]` 按 filter 列。两个命令都是 read-only（不改 .index.json / per-slug index.json，K5 边界）。可选低优先级（KB-MISC-01）：如本 phase 时间紧 Claude 决策 drop 给 v1.3，则不阻塞 phase close（其余 4 个 SC 全 PASS 即可 ship）。
**Plans**: 2 plans
- [ ] 12-01-PLAN.md — agent/index.py +3 read-only public functions (scan_archives_for_backfill / search_index / list_index) + cmd_index_{backfill,search,list} + 3 K5 boundary tests + behavior tests (Wave 1, autonomous, KB-12/KB-13/KB-MISC-01)
- [ ] 12-02-PLAN.md — 17 archives backfill execution + CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 section + D-29 byte-equal close gate (Wave 2, autonomous, depends_on 12-01, KB-12/KB-13/KB-14/KB-15)

## Next Milestone

To start the next milestone cycle after v1.2 completes, run `/gsd-new-milestone`. This will:
1. Update PROJECT.md with new direction
2. Define fresh REQUIREMENTS.md
3. Build a new ROADMAP for the next phase set

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 01. Preflight & Regression Baseline | v1.0 | 3/3 | ✅ Complete | 2026 |
| 02. Resume Infrastructure & Cache | v1.0 | 3/3 | ✅ Complete | 2026 |
| 03. Source Refactor + new sources | v1.0 | 3/3 | ✅ Complete | 2026 |
| 04. Frame fps Automation | v1.0 | 2/2 | ✅ Complete | 2026 |
| 05. Adaptive Output + UI Demos + Podcasts | v1.0 | 3/3 | ✅ Complete | 2026-05-02 |
| 06. Multi-Agent Parallelism | v1.0 | 2/2 | ✅ Complete | 2026-05-02 |
| 07. Warm-up + K5 emitters + D-29 foundation | v1.1 | 3/3 | ✅ Complete | 2026-05-03 |
| 08. Writing rules — CLAUDE.md + glossary | v1.1 | 2/2 | ✅ Complete | 2026-05-03 |
| 09. Correctness automation — verifier + auto-rewrite | v1.1 | 2/2 | ✅ Complete | 2026-05-03 |
| 10. Topic taxonomy governance + bootstrap CLI | v1.2 | 2/2 | Complete    | 2026-05-03 |
| 11. per-slug index.json + 顶层聚合 + Phase 7.6 hook | v1.2 | 2/2 | Complete    | 2026-05-03 |
| 12. 17 archives backfill + CLAUDE.md 推荐 prompt rule + search/list CLI | v1.2 | 0/2 | Planned | — |

---

## Rationale Notes

**Phase numbering continuation**: v1.0 ended at Phase 06; v1.1 ended at Phase 09; v1.2 starts at Phase 10. Monotonic counter unbroken (no `--reset-phase-numbers`).

**3 phases (granularity=coarse, mirror v1.1 rhythm)**: 16 reqs across 4 categories (INDEX 6 / TOPIC 5 / BACKFILL 2 / PROMPT 2 + 1 OPTIONAL). Phase order is **data-flow constrained**:
- Phase 11 KB-01 per-slug `index.json` requires `output/_topics.md` already containing approved taxonomy → Phase 10 必须先（KB-07..KB-11）
- Phase 12 KB-12 backfill replays Phase 11 generator across 17 archives → Phase 11 必须先（KB-01..KB-06）
- Phase 12 KB-14 CLAUDE.md prompt rule activates only after `output/.index.json` is populated → backfill must precede

**Compression rationale**: Splitting Phase 12 into 12a (backfill) + 12b (prompt rule) + 12c (search CLI) would fragment the natural "v1.2 收尾交付" boundary; compressing Phase 10 into Phase 11 would entangle governance file authoring with index.json generator (different K5 boundaries — `topics` CLI 写 _topics.md，`index` CLI 写 index.json，分开实现避免 file ownership 冲突)。3 phases hits coarse granularity sweet spot.

**Critical pitfall coverage** (inherited from v1.0/v1.1 design contracts):
- D-29 byte-equal regression → Phase 11 SC#5 (replay 33/0/30 PASS post-Phase-11) + Phase 12 SC#2 (replay 33/0/30 PASS post-backfill) — 双重 gate 保 v1.0/v1.1 archives 不破
- K5 boundary (Claude is decider) → Phase 10 SC#5 (CLI source-grep test asserts `topics bootstrap/audit/resolve` never write index.json/summary.md) + governance Pending 申请闭环（Claude 决策选 topic / 申请新 topic，但 user 决定批 Pending）
- Term fragmentation prevention → Phase 11 SC#4 (keywords 优先复用 `_glossary.md` H2 anchors，避免 LoRA / Lora / low-rank adaptation 分裂)
- Anti-hallucination → Phase 12 SC#3 (CLAUDE.md FORBIDDEN list mirror v1.1 5th format-spec invariant 字面规则风格)
- Backward-compat (老 5 CLI 仍可用) → Phase 11 + 12 全部 additive，新增 sidecar + 新增 CLI subcommand，零 schema mutation 在已有 artifact

**Backward-compat invariants encoded**:
- D-29 byte-equal: Phase 11 SC#5 + Phase 12 SC#2 (双重 replay gate)
- ¥0 cost: zero new paid APIs (无 LLM API for keyword extraction，KB-03 复用 `_glossary.md` 即足；零新 dep)
- K5 boundary: Phase 10 SC#5 (`topics` CLI source-grep) + Phase 12 SC#5 (`index search/list` read-only)
- 老 CLI 5 命令保留可用: 全部 v1.2 新 CLI 加在 `python -m agent.tools` 子命令下作 additive (`topics bootstrap/audit/resolve`, `index backfill/rebuild/search/list`)
- `output/<slug>/` 目录约定不破坏: index.json 是新 sidecar，不修改 summary.md / segs.json / paragraphs.json / meta.json 任一现有文件

**The single human-touch point** (per D-04 K5 governance): user 偶尔（一周/一月）打开 `output/_topics.md` review `## Pending` 段，批/拒/改后跑 `topics resolve`。Phase 10 ship 时首次 `topics bootstrap` 默认批（ground truth from 17 archives），用户可选择性 review；之后 Claude 写新视频 index.json 申请新 topic 时，进 Pending 等用户偶尔扫一眼。这是 v1.2 唯一一处用户必须做的操作；其他流程全自动（D-03 锁）。

---

*Last updated: 2026-05-03 — v1.2 knowledge-base milestone roadmap created. 3 phases (10-12) derived from REQUIREMENTS.md (16 reqs, 4 categories) + v1.2-CANDIDATES.md (9 D-XX locked decisions). Coverage: 16/16 requirements mapped 1:1. Phase order data-flow constrained: Phase 10 taxonomy → Phase 11 index generator → Phase 12 backfill + prompt rule. D-29 byte-equal 33/0/30 PASS gate baked into Phase 11 SC#5 + Phase 12 SC#2.*
