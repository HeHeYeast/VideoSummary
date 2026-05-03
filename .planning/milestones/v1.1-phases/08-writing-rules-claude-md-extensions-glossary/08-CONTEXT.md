# Phase 08: Writing rules — CLAUDE.md extensions + glossary - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Smart-discuss accepted all defaults — D-01/02/03 user 铁律 + per-req must-haves in REQUIREMENTS.md govern all tactical choices

<domain>
## Phase Boundary

Make new summaries (slugs with `.v11_features.json` marker enabled) diverge in shape:
- L2/L3 ASR corrections via prompts (Claude reads `transcribe_lint_warnings.json` from Phase 07)
- Inline trace tokens after every load-bearing claim
- Zero-baseline self-contained header (你需要/你不需要)
- First-mention inline term annotations
- Cross-slug `output/_glossary.md` accumulation with FileLock
- Optional 5-min TL;DR speedrun for long videos (>20min OR >50 sections)

All format changes are **prompt + Markdown convention** (no Python LOC for CORR-01b/c, CORR-02, TEACH-A1/A2, TEACH-B); only `output/_glossary.md` append helper + `output/.glossary.lock` need new code (TEACH-A3).

**7 requirements**: CORR-01b, CORR-01c, CORR-02, TEACH-A1, TEACH-A2, TEACH-A3, TEACH-B.

**Phase 08 Cannot Run In Parallel With Phase 07** because:
- Phase 08 L2/L3 prompts consume `transcribe_lint_warnings.json` (Phase 07 CORR-01a output)
- Phase 08 uses `.v11_features.json` opt-in marker pattern (Phase 07 PRE-V11-01)
- Phase 08 runs under `.token_budget.json` ≤ 2x baseline assertion (Phase 07 PRE-V11-03 reference)

</domain>

<decisions>
## Implementation Decisions

### Locked from REQUIREMENTS.md (user铁律 D-01/02/03 govern)

**TEACH-A1 — Inline term annotation**:
- Format: `术语 (English / 中文释义)` first-mention only
- FORBIDDEN annotations on universal terms (Python / JSON / Claude — anti-patronizing)
- Eligibility rule lives in CLAUDE.md prompt extension; Claude self-enforces

**TEACH-A2 — Self-contained zero-baseline header**:
- Structure: 标题 / UP / 时长 / 链接 → "你需要知道什么" (≤ 3 行) → "你不需要知道什么" (≤ 3 行) → optional "5 分钟速读版" (TEACH-B trigger) → 正文
- Header hard cap: ≤ 6 lines total (excluding TL;DR block)
- Tone constraints: no "简单来说" / "说白了" / "你可能不知道" patterns

**TEACH-A3 — Cross-slug glossary**:
- Path: `output/_glossary.md` (cross-slug accumulator, NOT per-slug — D-01 跨文档术语累积动机)
- Lock: `output/.glossary.lock` (reuse `agent/_lock.py` FileLock)
- Schema: append-only, first-seen-wins for same (slug, term) pair (idempotent skip if H2 anchor + slug-link exists)
- New CLI: `python -m agent.tools glossary {append|audit}` (audit was shipped in Phase 07-03; append is new)
- **Inline-first invariant** (CRITICAL — D-01): every first-mention term MUST get inline annotation REGARDLESS of glossary state. Glossary is fallback-only, never excuses skipping inline annotation.

**TEACH-B — TL;DR speedrun**:
- Trigger: video duration > 20 min (read from `paragraphs.json[-1].end > 1200`) OR `estimated_sections > 50` (from plan.md front-matter)
- Length cap: 10-15 lines hard cap (max 20)
- Position: TOP of summary.md (after header, before main body)
- Order: written LAST (after body + glossary appends) to prevent drift
- Structure: 核心结论 + 工作流速查表 + 必看时间戳 3-5 个
- Zero citations inside (use section anchors `详见 §三、消化阶段` instead)
- Sync check before phase close: TL;DR step count ≈ body H2 count for replicate-guide mode

**CORR-01b — L2 context-correction**:
- Reads `transcribe_lint_warnings.json` from Phase 07 CORR-01a
- Uses meta.json title + UP + description as prior
- Records corrections in `plan.md` "已自动修正的术语" section (transparency)
- Hard caps: max 10 auto-applied corrections per slug; L2 needs ≥ 2 independent evidence sources
- **NEVER mutates `segs.json`** (D-29 invariant — corrections are derived, not source-of-truth)

**CORR-01c — L3 multi-modal fallback**:
- Triggers when L1 confidence < 60% AND L2 evidence < 2 sources
- Time window: ≤ ±0.5s around suspect token timestamp
- Frame budget: max 5 frames per warning
- If L3 also inconclusive → annotate in summary as `[?]` per CORR-02

**CORR-02 — Inline trace tokens + self-check**:
- Token format lock: `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` or `[para_ID @ HH:MM:SS]`
- Citation eligibility (3 categories):
  - REQUIRED: specific claims, parameters, code excerpts, UI references
  - FORBIDDEN: TL;DR, glossary inline annotations, "你需要知道什么" prelude, 章节小结 transitions
  - OPTIONAL: narrative connectors / paraphrases
- Density target: avg ≤ 1 citation per 3 sentences (measured by `summary_lint` Phase 09)
- Self-check pass: confidence < 80% claims get `[?]`; summary末尾 footer reports `[?]` count vs total claim count

### Claude's Discretion

- Specific prompt wording in CLAUDE.md (no D-XX decision required — Claude writes prompt that achieves the locked behaviors)
- L2 evidence-source matching algorithm (regex / fuzzy match — Claude picks pragmatic approach in plan)
- Glossary file format (Markdown H2 anchors per term + slug-link list — schema TBD in plan)
- TL;DR template structure detail (3 sub-blocks listed above; ordering/visual style is Claude's discretion)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/_lock.py` FileLock — reuse for `output/.glossary.lock` (Phase 06 + 07 precedent)
- `agent/_v11.py.is_v11_enabled()` — gate for all Phase 08 paths; absent marker = silent v1.0 fallback (D-29)
- `agent/glossary_audit.py` (shipped Phase 07-03) — read-only audit; this phase ADDS the `append` write helper using same module
- `agent/transcribe_lint.py.detect_warnings()` (shipped Phase 07-03) — produces `transcribe_lint_warnings.json` consumed by Phase 08 L2 prompts
- `agent/io.py.write_json_atomic()` — atomic JSON write for new `_glossary.md` updates

### Established Patterns
- CLAUDE.md is the prompt-engineering decision center (no Python LOC needed for prompt changes)
- 4-mode classification + 8 hand-authored skeletons (Phase 5) — Phase 08 prompt extensions OVERLAY (not replace) the existing 4-mode skeletons
- format-spec lock 4 invariants (Phase 5 D-25): timestamp [HH:MM:SS] / explicit code-fence / relative frame paths / 第二人称 imperative — Phase 08 ADDS 5th invariant (trace-token-after-load-bearing-claim)
- `<artifact>.params.json` sidecar pattern (Phase 2) — could apply to glossary writes if param-aware caching needed; LIKELY NOT NEEDED for glossary (write is append-only, idempotent)

### Integration Points
- CLAUDE.md — extend `## /summarize-video 完整工作流` section with Phase 8 instructions (8 phases → maybe 10 sub-steps to embed CORR-01b/c, CORR-02, TEACH-A*, TEACH-B at appropriate workflow phase)
- CLAUDE.md — extend `### 格式锁定` section with new 5th invariant (trace tokens)
- CLAUDE.md — extend each of 8 mode skeletons with TEACH-A2 header inline (or factor into a shared "format spec" reference)
- `agent/glossary.py` (NEW or extend `agent/glossary_audit.py`) — `glossary_append(slug, term, definition)` with FileLock
- `agent/tools.py` — add `cmd_glossary_append` subparser
- `output/_glossary.md` (NEW shared artifact)
- `output/.glossary.lock` (NEW lock domain — second cross-slug lock domain after Phase 07 queue.lock)

</code_context>

<specifics>
## Specific Ideas

- **CLAUDE.md extension placement**: insert Phase 8 prompt extensions as a new H2 section "v1.1 自适应教学文档增强" right after the existing "## 视频类型变奏" section so the 4-mode classification + Phase 8 quality rules are read together. Mode rules + format rules + correctness rules form one coherent prompt block.
- **Glossary schema concrete proposal** (open to plan-phase refinement):
  ```markdown
  ## 术语 (English Term)

  中文释义 1-3 行。

  - [BV132wizyEEB](output/BV132wizyEEB/summary.md#term-anchor) — slug 1 引用上下文
  - [douyin_karpathy_llm_wiki](output/douyin_karpathy_llm_wiki/summary.md#term-anchor) — slug 2 引用上下文
  ```
  Each term is a `## H2` heading. Sub-bullets are append-only slug references. First-seen-wins for definition (subsequent slugs append references but don't overwrite释义).
- **TL;DR + sync-check workflow**: Claude generates TL;DR LAST (after body), then runs internal H2 count vs TL;DR bullet count; if mismatch >20% logs warning in plan.md but doesn't auto-fix (Claude is decider).
- **L2 evidence-source matching**: simple substring check is fine for v1.1 (e.g., warning suspect_text "Lora" — check if meta.title or description contains literal "LoRA"). Fuzzy match deferred to v1.2 if false-positive rate too high.
- **`.v11_features.json` features array additions**: Phase 08 ADDS these flags to the marker schema (extending Phase 07's set):
  - `inline_trace_tokens` (CORR-02)
  - `self_check_confidence` (CORR-02)
  - `self_contained_header` (TEACH-A1+A2)
  - `cross_slug_glossary` (TEACH-A3)
  - `tldr_speedrun` (TEACH-B)
  - `l2_l3_correction` (CORR-01b/c)

</specifics>

<deferred>
## Deferred Ideas

- **Per-slug glossary path** (rejected per smart-discuss user choice) — would violate D-01 cross-document accumulation motive
- **TL;DR for ALL summaries** (rejected per smart-discuss user choice) — short videos don't need it; >20min/>50sections threshold is right
- **Citation density soft enforcement** (rejected per smart-discuss user choice) — keep avg ≤ 1/3 sentences strict per CORR-02 must-haves
- **L2 fuzzy match algorithm** (deferred to v1.2 if substring miss rate >10% empirically)
- **Glossary versioning / migration runbook** (deferred — append-only schema is forward-compat by design)
- **TL;DR multi-language support** (deferred — Chinese only for v1.1)
- **Diff-based reviewer in Phase 09** depends on token cost data from Phase 08 production runs
- **Whisper decode-time `initial_prompt` injection** (per research SUMMARY.md "v2+ defer")

</deferred>
