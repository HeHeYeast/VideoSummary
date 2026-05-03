# Milestone v1.1 Requirements — summary-quality

**Milestone:** v1.1 summary-quality
**Goal:** 把 v1.0 工具链产出的 summary 从"读起来正确"升级为"自动可信、零基础读者也能学到东西"——所有错误自动检测/修复/复审，新读者不依赖外部知识也能读懂。
**Source:** `.planning/v1.1-CANDIDATES.md` 8 候选 + research SUMMARY.md (3 phases / 1 new dep / 11 pitfalls)
**Locked design (D-01/02/03):** 自包含零基础视角 / 三层校验 / 自动化优先

**Coverage:** 18 v1.1 requirements grouped into 5 categories. Phase mapping (1:1) shown in Traceability table.

---

## v1.1 Active Requirements

### Correctness automation (CORR) — 7 reqs

- [ ] **CORR-01a**: ASR 转录后 L1 检测可疑词（pypinyin homophone + 中英混杂异常 + 罕见字组合 + 高频但拼写不一致），输出 `output/<slug>/transcribe_warnings.json`，**绝不修改 segs.json**（D-29 invariant）。Schema 锁：每 warning 含 `paragraph_id` / `suspect_text` / `suggested_text` / `confidence` / `evidence_source`。
- [ ] **CORR-01b**: Claude 在 plan.md 阶段对 L1 警告做 L2 上下文修复，使用 meta.json + 标题 + UP + description 作 prior。修复记录写 `plan.md` 顶部"已自动修正的术语"段（透明性）；max 10 auto-applied corrections per slug；L2 必须 ≥ 2 independent evidence sources 才采纳。
- [ ] **CORR-01c**: 关键截图 L3 多模态兜底（标题板 / 工具 UI）确认 L1+L2 仍不确定的术语。触发条件锁：时间窗 ≤ ±0.5s + 最多 5 帧/警告 + L1 confidence < 60% AND L2 evidence < 2 sources。
- [ ] **CORR-02**: Summary 行内溯源 token 强制 — 每 claim / 截图引用 / 具体参数后加 `[seg_*.jpg @ HH:MM:SS]` 或 `[para_ID @ HH:MM:SS]`。token 格式锁；写完 Claude 自检 confidence < 80% 加 `[?]`；末尾汇总 `[?]` 数 vs 总 claim 数。citation eligibility 锁：REQUIRED 在具体 claim/参数；FORBIDDEN 在 TL;DR/glossary/prelude/transitions；OPTIONAL 在 narrative 连接。avg ≤ 1 citation per 3 sentences.
- [ ] **CORR-03a**: `python -m agent.tools summary_lint <slug>/summary.md` 做机械式 format-spec 检查（4 项不变量：`[HH:MM:SS]` 8字符 / 代码 fence 显式语言 / 相对帧路径 / 第二人称指令式）+ 引用格式 + glossary 一致性，输出 `output/<slug>/summary_lint.json`。K5 边界：仅检查不改写。
- [ ] **CORR-03b**: Phase 7.5 verifier subagent (`Task(subagent_type=general-purpose)`) 拿 summary.md + paragraphs.json + 关键帧 + plan.md 跑校对，输出 `output/<slug>/<slug>-REVIEW.md`，列 critical/warning/info 三级问题。**Scope 锁死**：format-spec + mode 规则 + citation validity + glossary consistency；**禁止**做 pedagogical judgment（防 reviewer 幻觉问题）。
- [ ] **CORR-03c**: 高严重度 (critical) 自动触发 delta 重写最多 1 轮，pre-rewrite 备份到 `output/<slug>/summary.md.pre-review`；超 1 轮则写 `output/<slug>/<slug>-UNRESOLVED.md` fallback（人工介入清单）。`VIDEOSUMMARY_SKIP_REVIEWER=1` 环境变量降级关闭整个 Phase 7.5。

### Teaching quality (TEACH) — 4 reqs

- [ ] **TEACH-A1**: 写作 prompt 强制 — 每个新术语第一次出现加 inline 注解 `术语 (English / 中文释义)`；first-mention only，后续可省。术语 eligibility 锁：FORBIDDEN 注解 Python / JSON / Claude 等普世术语（防 patronizing tone）。
- [ ] **TEACH-A2**: Summary 顶部固定结构 — 标题 / UP / 时长 / 链接 → "你需要知道什么"（≤ 3 行先决条件）→ "你不需要知道什么"（≤ 3 行明确豁免）→ "5 分钟速读版"（TEACH-B 触发时）→ 正文。Header hard cap 总计 ≤ 6 行（防 boilerplate noise）。
- [ ] **TEACH-A3**: 跨 slug 累积 `output/_glossary.md`，append-only schema，FileLock 串行化（`output/.glossary.lock` reuse `agent/_lock.py`），first-seen-wins 同名术语；**inline-first invariant**：annotate regardless of glossary（glossary 是 fallback 不是 primary，不让 author 跳过 inline 注解）。`python -m agent.tools glossary_audit` 只读 CLI 列出术语统计。
- [ ] **TEACH-B**: 长 summary（视频时长 > 20min OR `estimated_sections` > 50）顶部加"5 分钟速读版"块，10-15 行 hard cap，结构 = 核心结论 + 工作流速查表 + 必看时间戳 3-5 个。**写在 LAST**（写完正文再生成防 drift），写完做 sync-check（H2 数 vs TL;DR bullet 数）；**禁止**在 TL;DR 内放 citations（用锚点跳转代替）。

### K5 Decision-support tools (TOOL) — 2 reqs

- [ ] **TOOL-A**: `python -m agent.tools mode_signals <slug>/paragraphs.json --out <slug>/mode_signals.json` 输出客观信号（代码 fence 出现率 / 步骤词频 / 提问句占比 / speaker turn 信号 / 跨工具对比信号）+ raw evidence 行号。**K5 边界**：NO `recommended_mode` 字段，仅出 signals + evidence；Claude 仍是 mode 决策者。`paragraphs.json` hash stamping 防 stale。
- [ ] **TOOL-B**: `python -m agent.tools schedule_suggest <slug> --out <slug>/schedule_suggestion.json` 组合 paragraphs + scenes.json + silence_map.json 输出 fps 段建议（静音 → fps 0.05 或 skip / 场景密集 → fps 0.3-0.4 / 长讲解段 → fps 0.1）+ 自动加 FPS-04 silence-coverage 兜底。**K5 边界**：source-grep 静态断言禁止 mode_signals/schedule_suggest 源代码引用 `schedule.json` / `plan.md` / `summary.md` 文件名。

### Operational miscellanea (MISC) — 2 reqs

- [ ] **MISC-01**: AV1 codec WARNING 降级到 INFO 级（`agent/tools.py` 内 `WARNING | Codec av1 detected;...`）；其他重复噪音类似分级处理。
- [ ] **MISC-02**: `python -m agent.tools queue add/list/next/done <slug>` — 状态文件 `~/.videoSummary/queue.json` + `~/.videoSummary/.queue.lock` 跨 terminal 串行化（reuse `agent/_lock.py`）；entry 含 `in_progress: <pid>` marker 避免双跑同一条；schema 锁：`{"version": 1, "items": [{"slug", "url", "added_at", "status", "in_progress"}]}`。

### D-29 backward-compat foundation (PRE-V11) — 3 reqs

- [ ] **PRE-V11-01**: 每 slug `output/<slug>/.v11_features.json` opt-in marker；缺失 → 走 v1.0 path silently（17 archives 永不被动升级）。Schema 含 `{"version": 1, "features_enabled": [...], "marker_set_at": ISO}`。
- [ ] **PRE-V11-02**: 17-archive byte-equal replay 一次性脚本 `scripts/replay_v10_archives.py`（或类似）— Phase A 关闭前必跑 PASS；diff 任一字节即 phase 不可 ship。
- [ ] **PRE-V11-03**: `output/<slug>/.token_budget.json` baseline 在 3 个代表性 archive (replicate-guide / interview-distillation / extension-applications) 上测量；后续 phase 断言 v1.1 全开 ≤ 2x baseline；超出则 phase verification fail。

---

## Future Requirements (deferred to v1.2+)

- **L0 Whisper decode-time `initial_prompt` 注入** — 17% relative WER reduction in domain runs（free additional layer, scope creep for v1.1）
- **Diff-based reviewer re-review** — initial CORR-03 是 full re-read（~80% summary write cost）；diff-only 等 v1.1 production 数据后决定
- **`summary.md.v10.bak` 自动备份** — re-run on archived slug UX nicety；defer
- **`gsd-summary-verifier` 升级为 registered subagent** — `.claude/agents/*.md` 形态，等 v1.1 信号验证 ROI 后促进
- **CORR-01 L4 user 字典 fallback** — 如 v1.1 自动校正率 < 70% 再考虑

## Out of Scope (continued from v1.0)

- **任何付费 API**（LLM / ASR / OCR / Vision / translation）— ¥0 hard constraint
- **把决策权交给脚本** — Claude Code 仍是唯一决策者，工具只能"减摩擦"不能"做判断"（K5）
- **一个视频出多份文档**（quick-ref + deep-dive 分离）— Claude 自适应单文档
- **队列全自动无人值守批跑** — MISC-02 是 helper（add/list/next/done），不是 scheduler
- **多用户 / 账号 / SaaS 化** — 单用户作者工具
- **重写或废弃现有 agent/ src/ 模块** — 老 5 CLI + output/<slug>/ 约定保留
- **改变 output/<slug>/ 目录约定** — v1.1 只 add 新 sibling artifacts
- **任何"用户提供 X"的方案** — 违反 D-03 自动化优先（用户字典 / 用户对齐时间戳 / 用户挑下一条都不行）
- **Reviewer 做 pedagogical judgment** — CORR-03b scope 锁死 format-spec + mode + citation + glossary，不评 teaching quality（防 hallucinated critique）

---

## Traceability

Phase mapping populated by ROADMAP.md (1:1, 18/18 covered, no orphans, no double-mapping).

| REQ-ID | Phase | Plan |
|--------|-------|------|
| PRE-V11-01 | Phase 07 | 07-01 |
| PRE-V11-02 | Phase 07 | 07-01 |
| PRE-V11-03 | Phase 07 | 07-01 |
| MISC-01 | Phase 07 | 07-02 |
| MISC-02 | Phase 07 | 07-02 |
| TOOL-A | Phase 07 | 07-03 |
| TOOL-B | Phase 07 | 07-03 |
| CORR-01a | Phase 07 | 07-03 |
| CORR-01b | Phase 08 | 08-02 |
| CORR-01c | Phase 08 | 08-02 |
| CORR-02 | Phase 08 | 08-02 |
| TEACH-A1 | Phase 08 | 08-02 |
| TEACH-A2 | Phase 08 | 08-02 |
| TEACH-A3 | Phase 08 | 08-01 |
| TEACH-B | Phase 08 | 08-02 |
| CORR-03a | Phase 09 | TBD |
| CORR-03b | Phase 09 | TBD |
| CORR-03c | Phase 09 | TBD |

**Total: 18 v1.1 requirements** (7 CORR + 4 TEACH + 2 TOOL + 2 MISC + 3 PRE-V11) — all mapped 1:1 to phases. **Coverage: 18/18 ✓ — no orphans, no double-mapping.**

**Per-phase distribution:**
- Phase 07: 8 reqs (PRE-V11-01/02/03 + MISC-01/02 + TOOL-A/B + CORR-01a) — **all mapped to specific plans (07-01/02/03)**
- Phase 08: 7 reqs (CORR-01b/c + CORR-02 + TEACH-A1/A2/A3 + TEACH-B) — **all mapped to specific plans (08-01 = TEACH-A3 code; 08-02 = 6 prompt extensions)**
- Phase 09: 3 reqs (CORR-03a/b/c)

---
*Last updated: 2026-05-03 — Phase 07 plans (07-01/02/03) shipped; Phase 08 plans (08-01/02) created and mapped 1:1 to all 7 Phase 08 reqs (TEACH-A3 → 08-01 code, all 6 others → 08-02 CLAUDE.md prompt extensions). Phase 09 plans pending. Source: v1.1-CANDIDATES.md (D-01/02/03 locked) + .planning/research/SUMMARY.md (3 phases / 1 new dep / 11 pitfalls). Phases 07-09 (numbering continues from v1.0 Phase 06).*
