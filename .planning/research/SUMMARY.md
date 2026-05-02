# Project Research Summary

**Project:** videoSummary — milestone v1.1 summary-quality
**Domain:** Local LLM-driven video-to-Markdown teaching tool (subsequent milestone, brownfield extension)
**Researched:** 2026-05-03
**Confidence:** HIGH

## Executive Summary

v1.1 is a **purely additive quality layer** on the v1.0 corpus. The 8 candidate requirements (4 必做 + 2 想做 + 2 顺手 from `.planning/v1.1-CANDIDATES.md`) collapse to a remarkably small footprint: **1 new pip dep (`pypinyin>=0.55.0`)** + **6 new K5 read-only signal emitters** + **2 new shared FileLock domains** + **~5 CLAUDE.md prompt extensions** + **1 new Phase 7.5 verifier subagent**. Zero existing artifacts change shape; D-29 byte-equal invariant survives via slug-level opt-in marker (`output/<slug>/.v11_features.json`) so the 17 archived summaries replay byte-equal.

Three convergent design principles emerged across all 4 research dimensions: **(1) prompt-first, code only when mechanical** — CORR-02/CORR-03/TEACH-A/TEACH-B carry zero new Python LOC; **(2) K5 boundary statically asserted** — every new tool forbidden by source-grep test from referencing `plan.md`/`schedule.json`/`summary.md` filenames, mirroring the v1.0 `cmd_detect_scenes` pattern; **(3) build order Warm-up + K5 emitters → Writing rules → Correctness automation** — Phase A's `.v11_features.json` opt-in pattern + replay test gates everything downstream; Phase C's verifier cannot land before Phase B's format-spec extensions exist to verify against.

Key risks: token budget compounds multiplicatively across 5 quality layers (could reach ~2.5x v1.0 cost without per-layer caps), and reviewer feedback loops can produce worse-than-original rewrites if scoped to pedagogical judgment. Both have concrete prevention strategies locked into Phase plans (per-layer hard caps + reviewer scope lock to format-spec/mode/citation/glossary only, max-1 rewrite, delta not full).

## Key Findings

### Recommended Stack

v1.1 demands the smallest stack delta possible — 1 single new dep, 7 of 8 candidates need zero new libraries (decompose to Claude prompt-engineering + stdlib file I/O + Markdown convention + new project-local subagent file). Existing stack is current as of May 2026 (`yt-dlp 2026.3.17`, `scenedetect 0.6.7.1`, `faster-whisper 1.2.1`, `pyannote.audio 4.0.4`); `httpx==0.27.2` strict pin must be preserved (vendor douyin_api uses deprecated `proxies=` kwarg).

**Core technologies:**
- `pypinyin>=0.55.0`: CORR-01 L1 ASR 术语校正 — pure-Python homophone detection, ~2 MB, 4 of 5 cited Chinese ASR error-correction papers use this pattern
- (no new lib): Claude Code subagent infrastructure for CORR-03 — `Task(subagent_type=general-purpose)` invocation, NOT a `.claude/agents/*.md` file (over-investment for one verifier; promote in v1.2 if signal warrants)
- (no new lib): `agent/_lock.py` FileLock pattern reused for 2 new lock domains (`output/.glossary.lock`, `~/.videoSummary/.queue.lock`)

**Explicit "do NOT add"**: `rich` (presentational scope-creep), `mdformat` (lint downstream of Claude — K5 inversion), `jieba` (regex sufficient for code-mixed transcripts), `dimsim` (pypinyin enough for "same pinyin?" check), SQLite for glossary (premature for single-user append log), any LLM API SDK (¥0 violation).

→ Detail: `.planning/research/STACK.md`

### Expected Features

8 candidates from v1.1-CANDIDATES.md classified by table-stake/differentiator/anti-feature with strong industry analogs (Wikipedia Manual of Style for TEACH-A, Self-Refine + Agent-as-a-Judge for CORR-02/03, BLUF executive-summary best practice for TEACH-B). 12 anti-features documented.

**Must have (table stakes for quality automation):**
- CORR-02 inline trace tokens — load-bearing dependency (must land before CORR-03 can verify mechanically)
- CORR-03 reviewer subagent — Agent-as-a-Judge ICML 2025 validates 90% human-evaluator agreement vs 70% self-judge
- TEACH-A inline term annotation + glossary — Wikipedia/Obsidian-glossary pattern verified
- CORR-01 L1+L2+L3 ASR correction — 3-layer redundancy is industry pattern (Self-Refine empirically caps at max-1 rewrite, aligning with user's lock)

**Should have (differentiators):**
- TEACH-B 5-min速读版 — BLUF pattern, 10-15 line cap is opinionated tuning
- TOOL-A mode_signals.json — generic NLP feature engineering (no project-domain-specific prior)
- TOOL-B schedule_suggestion.json — LOW research backing (no published "fps by content type" rule), accept honestly as project-specific lore

**Defer (v2+ candidates):**
- Whisper decode-time `initial_prompt` (free additional layer, scope creep for v1.1)
- diff-based reviewer re-review (initial impl is full re-read; defer once token-cost data exists)
- pre-Phase-1 archive `summary.md.v10.bak` backup (UX nicety, defer)

→ Detail: `.planning/research/FEATURES.md`

### Architecture Approach

v1.1 is a **brownfield additive overlay** on v1.0 architecture. New artifacts are siblings under `output/<slug>/` (or shared at `output/_glossary.md` / `~/.videoSummary/queue.json`); new CLI subcommands sit alongside v1.0 commands in `agent/tools.py`; new prompt rules extend CLAUDE.md without rewriting existing 4-mode skeletons. Per-feature audit confirms only `summary.md` shape evolves on NEW writes; archived files never touched.

**Major components:**
1. **D-29 opt-in marker**: `output/<slug>/.v11_features.json` per-slug sentinel — Claude tooling reads this; if absent, runs v1.0 path silently (preserves byte-equal for 17 archives)
2. **6 new K5 emitters** (read-only signals, statically asserted not to write decision artifacts): `transcribe_lint`, `summary_lint`, `mode_signals`, `schedule_suggest` + 2 more
3. **CORR-03 verifier subagent** (Phase 7.5 in `/summarize-video`): `Task(general-purpose)` invocation, scope locked to format-spec + mode rules + citation validity + glossary consistency, NOT pedagogical judgment; max-1 rewrite final; delta-not-full rewrites; `.pre-review.md` backup; `<slug>-UNRESOLVED.md` fallback
4. **2 new FileLock domains**: `output/.glossary.lock` (cross-slug) + `~/.videoSummary/.queue.lock` (cross-slug, cross-project) — reuse `agent/_lock.py` pattern, same stale-PID logic
5. **CLAUDE.md prompt extensions** (no Python LOC): inline annotation rule + 你需要/你不需要 header + TL;DR LAST + citation eligibility + reviewer scope

→ Detail: `.planning/research/ARCHITECTURE.md`

### Critical Pitfalls

11 pitfalls identified (5 Critical, 5 Moderate, 1 Minor) with concrete prevention. Top 5 for roadmap to surface as phase constraints:

1. **P-08 D-29 byte-equal regression (Critical, gating)** — Phase A MUST include 17-archive replay test before any feature work; new artifacts in NEW filenames; `prompt_version` lock in CLAUDE.md
2. **P-09 Token budget multiplicative compounding (Critical)** — per-layer hard caps locked in PLANs (L3 ≤ 5 frames/warning, verifier ≤ 10 frames, max 10 auto-applied L1 corrections); `VIDEOSUMMARY_SKIP_REVIEWER=1` degrade env var; L1 in pure Python (free); `.token_budget.json` per-slug + assertion ≤ 2x baseline
3. **P-03 Reviewer feedback loop (Critical)** — reviewer scope lock (format-spec + mode + citation + glossary; NO pedagogical judgment); only `critical` severity triggers rewrite; max-1 rewrite final; `.pre-review.md` backup
4. **P-01 Correction runaway (Critical)** — L1 allowlist + L2 needs 2 independent evidence sources + L3 timestamp window ≤ ±0.5s + max 10 auto-applied corrections + `segs.json.corrections.jsonl` audit log (NEVER mutate `segs.json`)
5. **P-02 Citation pollution (Critical)** — REQUIRED/FORBIDDEN/OPTIONAL eligibility rules; ≤ 1 citation per 3 sentences avg; FORBIDDEN in TL;DR/glossary/prelude/transitions

**Cross-cutting patterns:** "additive but not really" trap (every retroactive sidecar key change cascades through cache invalidation); K5 erosion via convenience (gentle "follow tool's recommendation by default" drift); citation theater > no citation; D-01 violations are quiet; token budget compounds multiplicatively.

→ Detail: `.planning/research/PITFALLS.md`

## Implications for Roadmap

Based on convergent dependency graphs from ARCHITECTURE.md + FEATURES.md + PITFALLS.md, **3 phases** suggested:

### Phase A: Warm-up + K5 emitters + D-29 foundation
**Rationale:** Zero behavior change to `summary.md`. Establishes opt-in pattern + replay test + token-budget baseline that gates everything downstream. Mirrors v1.0 Phase 1 PRE pattern (gating preflight before feature work).
**Delivers:** `.v11_features.json` opt-in pattern + 17-archive byte-equal replay test (one-shot script) + `.token_budget.json` baseline + MISC-01 (AV1 log demote) + MISC-02 (queue helper CLI + `.queue.lock`) + TOOL-A (`mode_signals` CLI) + TOOL-B (`schedule_suggest` CLI) + CORR-01a (`transcribe_lint` CLI with `pypinyin` L1 detection)
**Addresses:** MISC-01 / MISC-02 / TOOL-A / TOOL-B / CORR-01 L1
**Avoids:** P-08 (replay test catches regression at gate), P-10 (lock domains established before features need them), P-11 (sidecar fallback path validated)

### Phase B: Writing rules — CLAUDE.md extensions + glossary
**Rationale:** Pure prompt + Markdown convention + stdlib append. New summaries diverge in shape; verifier in Phase C makes shape mandatory. Cannot run in parallel with Phase A's CORR-01a because Phase B's L2/L3 prompts consume `transcribe_warnings.json` from Phase A.
**Delivers:** CORR-01b/c prompts (L2 context-correction in `plan.md`, L3 multi-modal verify) + TEACH-A.1 (inline term annotation rule) + TEACH-A.2 (你需要/你不需要 header) + TEACH-A.3 (`output/_glossary.md` CLI + `output/.glossary.lock`) + TEACH-B (TL;DR LAST, 10-15 line cap) + CORR-02 inline trace token convention
**Uses:** Claude prompt-engineering (no new Python LOC), `agent/_lock.py` (TEACH-A.3 only)
**Implements:** Component 5 (CLAUDE.md extensions) + Component 4 partial (glossary lock)
**Avoids:** P-04 (lock + first-seen-wins), P-05 (inline-first invariant + 3+3 cap), P-06 (TL;DR LAST + sync check)

### Phase C: Correctness automation — verifier subagent + auto-rewrite
**Rationale:** Consumes Phase A+B (verifier needs format-spec extensions to check, needs trace tokens to validate). Highest token-cost feature; lands last so token-budget data from Phase A+B production runs informs cap tuning.
**Delivers:** `cmd_summary_lint` (mechanical format-spec check) + CORR-03 verifier subagent (Phase 7.5 in `/summarize-video`, `Task(general-purpose)`, scope-locked) + delta rewrite (max-1, `.pre-review.md` backup, `<slug>-UNRESOLVED.md` fallback) + `<slug>-REVIEW.md` output
**Uses:** Claude Code Task subagent infra (no new pip dep)
**Implements:** Component 3 (verifier subagent)
**Avoids:** P-03 (scope lock + critical-only trigger), P-09 (per-layer caps + skip env var)

### Phase Ordering Rationale

- **A → B → C is forced by data flow**: Phase B's L2/L3 prompts read `transcribe_warnings.json` (Phase A output); Phase C verifier reads inline trace tokens (Phase B convention) + format-spec (Phase B extensions)
- **Phase A is safest first** — entirely opt-in, old `/summarize-video` runs unaffected, replay test catches D-29 regression at the gate
- **Phase C is highest-cost and highest-risk** — needs Phase A's `.token_budget.json` baseline + Phase B's stable shape before per-layer caps can be tuned empirically

### Research Flags

Phases likely needing deeper research during planning:
- **Phase A:** empirical token-budget baseline measurement on 3 v1.0 archives + pypinyin false-positive rate measurement (decides default-on vs opt-in for L1 detection)
- **Phase C:** `Task` subagent token cost on 1000-line summaries (no in-repo precedent; decides if diff-review lands in v1.1 or defers to v1.2)

Phases with standard patterns (skip research-phase):
- **Phase A:** K5 + sidecar + FileLock all directly mirror v1.0 (cmd_detect_scenes, params.json sidecar, Phase 6 PARA-XX patterns)
- **Phase B:** pure CLAUDE.md prompt edits + glossary CLI on shipped FileLock — no novel architecture

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 9 packages verified on PyPI May 2026; `pypinyin` cited in 4 of 5 academic Chinese ASR error-correction papers |
| Features | MEDIUM-HIGH | CORR-* / TEACH-A / Cross-candidate-deps HIGH (Self-Refine + Agent-as-a-Judge + Wikipedia MoS); TOOL-A/B MEDIUM-LOW (no domain-specific prior) |
| Architecture | HIGH | Integration points grounded in v1.0 code; K5 boundary preserved by static-test pattern; D-29 risk audit per-feature |
| Pitfalls | HIGH | All 11 pitfalls specific to v1.1 features (not generic); D-29 + token budget addressed thoroughly; prevention is actionable per phase |

**Overall confidence:** HIGH — strong consensus across all 4 research files, no contradictions, brownfield extension where v1.0 is ground truth.

### Gaps to Address

- **Empirical token-budget baseline** (Phase A prerequisite): blocks Phase C cost ceiling tuning. Handle: Phase A includes a one-shot script measuring token cost on 3 representative v1.0 archives (replicate-guide / interview-distillation / extension-applications); writes `.token_budget.json` baseline.
- **pypinyin false-positive rate** (Phase A decision point): decides default-on vs opt-in. Handle: Phase A plan ships pypinyin opt-in initially; if false-positive rate < 5% on 3 test videos, promote to default-on in mid-phase pivot.
- **`Task` subagent cost on long summaries** (Phase C decision point): decides if diff-review lands in v1.1 or v1.2. Handle: Phase C plan instruments first 2 reviewer runs with token-cost logging; if > 120% of summary-write cost, summary-length cap or partial-review mode kicks in.
- **Re-run UX nit** (Phase A or B): should `/summarize-video` re-run on archived slug preserve old `summary.md.v10.bak`? Pure UX call; defer to phase planning.

## Sources

### Primary (HIGH confidence)
- pypinyin · PyPI — `pypinyin>=0.55.0` for L1 homophone detection
- faster-whisper 1.2.1 · PyPI — current pin works, optional bump for cleaner JSON
- yt-dlp 2026.3.17 · PyPI — current
- scenedetect 0.6.7.1 · PyPI — current (default dep for `detect_scenes`)
- pyannote.audio 4.0.4 · PyPI — current (opt-in)
- Anthropic Claude Code subagent docs — verified `Task(general-purpose)` semantics for CORR-03
- arxiv 2407.01909 (Pinyin Regularization in Chinese ASR Error Correction with LLMs) — validates CORR-01 L1+L2 design
- arxiv 2410.10934 (Agent-as-a-Judge ICML 2025) — 90% human-eval agreement for independent reviewer
- arxiv 2604.10508 (Self-Refine) — max-1 rewrite cap empirically correct
- Wikipedia Manual of Style — first-paragraph self-contained pattern for TEACH-A

### Secondary (MEDIUM confidence)
- Obsidian glossary plugin patterns — append-only cross-document term accumulation
- BLUF executive summary best practice — TEACH-B 5-10% length, 10-15 lines is opinionated tuning
- NLTK ch6 NLP feature engineering — TOOL-A signal extraction patterns

### Tertiary (LOW confidence)
- TOOL-B schedule_suggestion fps-by-content-type — no published rule-based heuristics; honestly disclosed as project-specific lore; Phase A prototype validates empirically

---
*Research completed: 2026-05-03*
*Ready for roadmap: yes*
