# Milestones

## v1.2 knowledge-base (Shipped: 2026-05-03)

**Phases:** 3 (Phases 10-12) · **Plans:** 6 · **Tasks:** 11 · **Tests:** 297 (was 222 pre-v1.2; +75 net new) · **K5 boundary tests:** 17 → 23 (+6)

**Definition of Done:** 把 23+ 条已总结视频从"一摞独立 markdown"升级为 Claude-queryable 知识库——用户用自然语言提问 ("我之前看过哪些 LLM Wiki 相关的视频？")，Claude FIRST ACTION 读 `output/.index.json` 给出 top-N 推荐 + chapter 入口。所有索引自动生成、零用户手维操作。

**Locked design decisions** (9 D-XX from `.planning/v1.2-CANDIDATES.md`，all from v1.1 ship 后用户实测的明确意图):
- D-01: 知识库消费者 = Claude（不是用户 ad-hoc grep）→ 索引 JSON 优先, 不做 markdown index
- D-02: 颗粒度 = summary 一层 keywords/topics + chapter 只做导航锚点（chapter 内无独立 keywords 字段）
- D-03: keywords 来源 = Claude 自动抽 + `_glossary.md` 复用
- D-04: topic taxonomy = 预定义 + Claude 申请新增（K5 边界延伸到 governance）
- D-05: 初始 taxonomy = Claude bootstrap from 17 archives
- D-06: backfill = v1.2 ship 时一次性 17 archives + 6 队列走新流程
- D-07: drop backlinks (single-user 23 条规模 over-engineering)
- D-08: 顶层 `.index.json` 自动同步 + 手动 rebuild CLI 兜底
- D-09: Claude 推荐 entry = 自然语言（不加 slash command）

**Key accomplishments:**

1. **Topic taxonomy governance layer** — `output/_topics.md` governance file (顶部 Approved + 底部 Pending 段) + 3 nested CLIs (`topics bootstrap` / `audit` / `resolve`) + governance Pending 申请闭环。Phase 10 ship 24 nodes / 5 categories ground-truth taxonomy 由 Claude 一次扫 17+ archives 归纳；K5 边界 statically asserted（`tests/test_k5_emitters.py` 17 → 20 +3）；FileLock 序列化 (`output/.topics.lock`)。零 summary.md / index.json mutation。

2. **Per-slug index.json + 顶层聚合 + Phase 7.6 hook** — `agent/index.py` 5 public functions (`validate_per_slug_index` / `read_per_slug_index` / `write_per_slug_index` / `rebuild_aggregator` / `read_aggregator`) + `glossary_h2_anchors` helper + 8 字段 schema lock (slug/title/duration_s/mode/topics/keywords/tldr_oneliner/chapters)。`/summarize-video` Phase 7.6 hook 让新视频自动同步生成 (`### Phase 7.6` H3 in CLAUDE.md L1836); keywords 优先复用 `output/_glossary.md` H2 anchors byte-equal canonical 形式避免分裂。

3. **23-archive backfill + CLAUDE.md 推荐 prompt rule + search/list CLI** — 33 archives backfilled (扩展超出原 17 spec；28 BV* + 5 douyin_* archives) via `index backfill --all` + per-slug `index write --slug X --from-stdin --force` loop。`output/.index.json` aggregator 33 entries lex-sorted。CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 (L1625) ship 触发 phrase 锁 + FIRST ACTION + 推荐回复格式锁 + 6-entry FORBIDDEN list (anti-hallucination)。

4. **D-29 byte-equal invariant preserved** — `python scripts/replay_v10_archives.py` 报告 `33 PASS / 0 FAIL / 30 SKIP` after Phase 12 close gate。所有 v1.0/v1.1 archives 4 核心文件 (summary.md / segs.json / paragraphs.json / meta.json) byte-equal preserved。v1.2 引入的 3 个 sidecar artifact 类型 (`output/<slug>/index.json` / `output/.index.json` / `output/_topics.md`) 都是 NEW files，不破 replay。

5. **K5 Claude-is-decider boundary** — Phase 10/11/12 共 +6 K5 boundary tests (17 → 23 final count): `topics bootstrap/audit/resolve` 3 cmds + `agent/topics.py` module + `cmd_index_write/rebuild/backfill/search/list` 5 cmds + `agent/index.py` module 都不写 D-29 5 核心 literals。Topic governance 走"Claude 申请 → user偶尔 review"的 pattern（Phase 10 D-04），bootstrap is 0% script-derived（CLI 必须 `--from-stdin` pipe Claude 提议）。

6. **Self-contained natural-language recommendation entry** — 用户 fresh Claude Code session 说"推荐学习 LLM Wiki 范式相关的视频" → Claude FIRST ACTION = `Read output/.index.json` → 返回 top-N 推荐 (3-line lock format)。Mirror v1.1 5th format-spec invariant 字面规则风格 anti-hallucination FORBIDDEN list。

**Stack delta:** Zero new pip dependencies (¥0 hard constraint preserved). Cross-slug lock domains 4 total: `.queue.lock` (v1.1) + `.glossary.lock` (v1.1) + `.topics.lock` (v1.2) + `.index.lock` (v1.2).

**Cross-phase wiring:** 7/7 integration points verified PASS (Phase 11 imports `from agent.topics import read_topics, append_pending` → consumed by `validate_per_slug_index` topic whitelist; Phase 12 imports full Phase 11 contract surface 9 functions; backfill loop uses Phase 11 `index write --from-stdin --force` byte-equal; CLAUDE.md `### Phase 7.6` (L1836) + `## v1.2 知识库自然语言推荐入口` (L1625) coexist; aggregator state consistent 33 entries lex-sorted byte-equal to per-slug sidecars; CLI subcommand registration `index{write,rebuild,backfill,search,list}` + `topics{bootstrap,audit,resolve}` complete).

**Verification:** `.planning/milestones/v1.2-MILESTONE-AUDIT.md` — 16/16 requirements satisfied (100%), 3/3 phases verified, 7/7 integration points, 4/4 E2E flows complete, D-29 33/0/30 byte-equal preserved. **Status: tech_debt** — 2 manual UAT items deferred + 1 cosmetic finding (all inherent to v1.2 design — Python orchestrators cannot auto-invoke `/summarize-video` Claude slash command nor simulate fresh-session recommendation behavior).

**Pending manual UATs:**
- Phase 11 KB-02: Phase 7.6 hook E2E behavioral verification on real `/summarize-video` invocation
- Phase 12 KB-15: Natural-language recommendation behavior on fresh Claude Code session

Run `/gsd-verify-work 11` and `/gsd-verify-work 12` against representative real video sessions to mark resolved.

**Cosmetic finding:** `topics audit` reports `Misc` top-level category as orphan (umbrella category, only its child `Fitness` is referenced) — not a wiring break; user can `topics resolve Misc --remove` if undesired.

**Archives:**
- Roadmap: `.planning/milestones/v1.2-ROADMAP.md`
- Requirements: `.planning/milestones/v1.2-REQUIREMENTS.md`
- Audit: `.planning/milestones/v1.2-MILESTONE-AUDIT.md`

---

## v1.1 summary-quality (Shipped: 2026-05-03)

**Phases:** 3 (Phases 07-09) · **Plans:** 7 · **Tasks:** 19 · **Tests:** 196 (was 170 pre-v1.1; +26 net new)

**Definition of Done:** 把 v1.0 工具链产出的 summary 从"读起来正确"升级为"自动可信、零基础读者也能学到东西"——所有错误自动检测/修复/复审，新读者不依赖外部知识也能读懂。

**Locked design decisions** (D-01/02/03 user 铁律, from BV1HG9JBsEPK + BV1rsd7BsEnA real-use feedback):

- D-01: Each summary self-contained, zero-baseline reader perspective (不假定阅读顺序，不假定阅读后理解)
- D-02: 3-layer correctness check (self-check + inline trace + 2nd-agent review)
- D-03: Automation-first (任何"用户手动做"的方案先 reject)

**Key accomplishments:**

1. **D-29 byte-equal foundation** — `agent/_v11.py` opt-in marker pattern (`output/<slug>/.v11_features.json`, 8→13→15 entries across phases) gates ALL v1.1 paths; 17 v1.0 archives replay byte-equal (33 PASS / 0 FAIL via `scripts/replay_v10_archives.py` with per-slug profile resolution from sidecar). Slugs without marker silently take v1.0 branches — no transcribe_lint_warnings.json, no glossary append, no inline traces, no Phase 7.5 verifier. Per-slug `.token_budget.json` baselines on 3 representative archives establish Phase 09 SC#4 ≤ 2x cap reference.

2. **4 K5 read-only signal emitters** (statically asserted) — `transcribe_lint` (CORR-01a, 5 strategies including `pypinyin>=0.55.0` homophone_cluster), `mode_signals` (TOOL-A, no `recommended_mode` field), `schedule_suggest` (TOOL-B with `--duration` ffprobe-skip override), `glossary_audit` (read-only sibling). 13 K5 boundary tests use intent-correct write-pattern regex (after Phase 07-03 deviation #2 lesson). Plus `summary_lint` (Phase 09 CORR-03a) brings total to 6 emitters. Cross-terminal queue helper (`python -m agent.tools queue {add|list|next|done|skip}`) reuses `agent/_lock.py` FileLock pattern (Phase 06) at new domain `~/.videoSummary/.queue.lock`.

3. **Adaptive 3-layer ASR correction** — L1 detects suspicious tokens (5 strategies: title_token, frequency_variance, mixed_script, hapax, homophone_cluster) → `transcribe_lint_warnings.json`; L2 prompts in CLAUDE.md context-correct using meta + UP + description (max 10 corrections, ≥ 2 evidence sources); L3 multi-modal frame check (≤ 5 frames/warning, ±0.5s window). All corrections written to `plan.md` "已自动修正的术语" — `segs.json` NEVER mutated (D-29 invariant).

4. **Self-contained zero-baseline summaries (D-01)** — every new summary's top: 你需要知道什么 (≤ 3 行) + 你不需要知道什么 (≤ 3 行) + optional 5-min TL;DR speedrun (>20min OR >50 sections). FileLock-serialized append-only `output/_glossary.md` cross-slug accumulator with first-seen-wins (TEACH-A3); inline-first invariant ("annotate REGARDLESS of glossary state") prevents author skip. CLAUDE.md `## v1.1 自适应教学文档增强` H2 section + 5th format-spec invariant (trace token after load-bearing claim).

5. **Verifier subagent + delta auto-rewrite (D-02 三层校验)** — Phase 7.5 verifier `Task(subagent_type="general-purpose")` reads summary.md + paragraphs + plan + lint outputs + ≤ 10 sampled frames; scope-locked to format-spec / mode rules / citation validity / glossary consistency. Verbatim FORBIDDEN list ("这段说不清楚" / "这里应该改写" / "语气不好" / "解释太啰嗦" / "新读者可能看不懂" / "可以加一个例子") prevents pedagogical hallucination (P-03 mitigation). Delta auto-rewrite max-1 cap explicit "NO 2nd automatic rewrite"; pre-rewrite backup `summary.md.pre-review`; UNRESOLVED.md fallback. `VIDEOSUMMARY_SKIP_REVIEWER=1` env degrades phase 7.5 entirely.

6. **3-tier inline trace token discipline** — every concrete claim/parameter/screenshot reference followed by `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` or `[para_ID @ HH:MM:SS]` (CORR-02). Citation eligibility locked: REQUIRED on specific claims/parameters/code/UI; FORBIDDEN in TL;DR/glossary/prelude/transitions; OPTIONAL in narrative connectors. Self-check: confidence < 80% claims get `[?]`. avg ≤ 1 citation per 3 sentences (mechanical check by `summary_lint`).

**Stack delta:** 1 new pip dep (`pypinyin>=0.55.0`, ~2MB pure Python). Zero paid APIs.

**Cross-phase wiring:** 8 integration points verified PASS (V11_FEATURES progression 8→13→15 / `transcribe_lint_warnings.json` consumed by Phase 08+09 / `summary_lint.json` consumed by Phase 7.5 verifier / `output/_glossary.md` produced by Phase 08 + drift-checked by Phase 09 / Phase 7.5 hook correctly inserted between Phase 7 and Phase 8 in `/summarize-video` workflow).

**Verification:** `.planning/milestones/v1.1-MILESTONE-AUDIT.md` — 18/18 requirements (1 partial pending manual gate), 3/3 phases, 8/8 integration, 4/4 E2E flows, 196 tests pass, D-29 33/0/30 preserved. **Status: tech_debt** — 5 manual UAT items + 6 info findings deferred (all inherent to v1.1 design — Python orchestrators cannot auto-invoke `/summarize-video` Claude slash command for end-to-end token budget + verifier live-runtime measurement).

**Pending manual UATs:**

- D-29 byte-equal `summary.md` re-run gate on 2 archives (PRE-V11-02 Part 2)
- SC#4 token budget end-to-end (≤ 2x v1.0 baseline) on 1 short test video with all 15 v1.1 flags
- Phase 7.5 verifier subagent live-runtime scope-lock validation (no pedagogical findings)

Run `/gsd-verify-work 07` and `/gsd-verify-work 09` against representative real videos to mark resolved.

**Archives:**

- Roadmap: `.planning/milestones/v1.1-ROADMAP.md`
- Requirements: `.planning/milestones/v1.1-REQUIREMENTS.md`
- Audit: `.planning/milestones/v1.1-MILESTONE-AUDIT.md`

---

## v1.0 — videoSummary v1.0 (Shipped: 2026-05-02)

**Phases:** 6 · **Plans:** 16 · **Tasks:** 31

**Definition of Done:** B站 / 抖音 / YouTube 视频 → 结构化 Markdown 教程，全流程 ¥0 成本，Claude Code 是唯一决策者。

**Key accomplishments:**

1. **5-source ingest pipeline** — Pluggable `agent/sources/` registry (Douyin → YouTube → Bilibili → Local → Generic) with most-specific-first matching. YouTube ships with 2-second `yt-dlp --simulate` preflight + 5-class stderr classifier (`gfw_blocked / cookies_stale / po_token_required / yt_dlp_outdated / other`) turning "莫名其妙连不上" into actionable Chinese hints. Local mp4 fallback closes the GFW/SABR/PO-token gap.

2. **Adaptive 4-mode teaching output** — CLAUDE.md becomes the prompt-engineering decision center. Phase 2 末尾 mode classification (`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`) + 8 hand-authored exemplar skeletons (4 modes × 2 rhythms) + format-spec lock (4 invariants) + `plan.md` / `depth_plan.md` schema. Zero LOC Python — all prompt engineering.

3. **Resume + parameter-aware caching** — Atomic JSON writes via tempfile+rename, `<artifact>.params.json` sidecars with cli/func/system 3-segment hash, loud regen logs (`regenerating segs.json because: cli.profile changed 'tutorial' -> 'podcast'`), `state.jsonl` event log + `state.json` derived view. `doctor` CLI for introspection. 17 archive re-runs remain byte-identical (D-29 invariant).

4. **Frame fps automation** — Claude writes `schedule.json` once, tool batch-executes ffmpeg per segment, resumes via `state.jsonl` segment events. FPS-04 silence-coverage gate ensures no >5s silence drops below baseline. PySceneDetect (default) + silero-vad (opt-in) provide ground truth without ever touching `schedule.json` (K5 "Claude is decider" boundary).

5. **Podcast / interview-distillation support** — `aggregate --profile podcast` (gap 2.5s / max_dur 90s / sentence_gap 1.5) + `transcribe --profile podcast` (VAD min_silence 800ms / threshold 0.6). Whisper 3-gram + density-based phrase repetition guard (warn-only, never auto-deletes per D-24 红线). Opt-in `pyannote.audio` diarization CLI ships ready (degrade fast-path documented for users without GPU + HF token).

6. **Two-terminal parallelism (NTH delivered)** — Cross-platform stdlib `agent/_lock.py` (msvcrt + fcntl), per-slug `output/<slug>/.resume.lock` with stale PID takeover, vendor `config.yaml` race closed, slug-prefixed log lines (`[BV132wiz] transcribe: ...`), cookies-in-memory cache + `--reload-cookies` flag. Skip-cleanly NTH per PROJECT.md K4 — shipped in spite of the option.

**Verification:** `.planning/milestones/v1.0-MILESTONE-AUDIT.md` — 52/52 requirements satisfied, 6/6 phases passed, 4/4 E2E flows verified, 5 tech debt items (all bounded, documented, non-blocking).

**Archives:**

- Roadmap: `.planning/milestones/v1.0-ROADMAP.md`
- Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`
- Audit: `.planning/milestones/v1.0-MILESTONE-AUDIT.md`

---
