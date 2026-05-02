# Domain Pitfalls — videoSummary v1.1 summary-quality

**Domain:** Local LLM-driven video summarization tool adding correctness automation + zero-baseline self-contained output to a frozen v1.0 corpus
**Researched:** 2026-05-03
**Scope:** 11 pitfall categories specific to v1.1's 8 candidate features layered on top of v1.0's K5/D-29/¥0 invariants

---

## How To Read This Doc

Each pitfall lists:
- **Warning sign** — what you'll see in summary.md / output/<slug>/ / log when this is happening
- **Prevention** — concrete actionable rule (a phase plan can implement it, not "be careful")
- **Phase to address** — which v1.1 phase (CORR-01 / CORR-02 / CORR-03 / TEACH-A / TEACH-B / TOOL-A / TOOL-B / MISC) owns the fix
- **Severity** — Critical / Moderate / Minor

**Top 3 risks for v1.1 (read these first):**
1. P-08 D-29 byte-equal regression (1 wrong default = 17 archives invalidated)
2. P-03 Reviewer feedback loop (CORR-03 cost explosion + auto-rewrite makes worse)
3. P-09 Token budget explosion (3 layers compound multiplicatively, not additively)

---

## Critical Pitfalls

### P-01: Correction Runaway (CORR-01 L1/L2/L3 cascade)

**What goes wrong:**
- L1 "suspect word" detector flags legitimate dialect / proper noun ("木下" UP 主名 flagged as ASR error)
- L2 context-correction "fixes" 木下 → "Kishita" because meta.json title is romaji
- L3 multi-modal verification reads the WRONG frame (slide changed at the citation timestamp ±1s) and "confirms" the wrong fix
- All 3 layers agree on a wrong answer → user trusts it because "3-layer校验通过"
- Cascade: one false-positive in L1 propagates with HIGH confidence through L2/L3

**Warning signs:**
- `transcribe_warnings.json` lists > 5% of total tokens as "suspect"
- L2 corrections include common Chinese words (你/我/这/那) — a clean signal of detector overreach
- L3 confirmations reference frames > 2s away from the citation timestamp
- Same UP 主 keeps getting their name "corrected" across multiple summaries

**Prevention:**
- L1 detector MUST have explicit allowlist: numerals, common ZH stopwords, single-CJK characters not flagged
- L2 corrections require **2 independent evidence sources** (meta.json title AND description AND/OR adjacent paragraph context) — single-source correction logged as `confidence: low` and NOT auto-applied
- L3 frame matching: timestamp window ≤ ±0.5s; if no frame in window, L3 is `inconclusive`, NOT `confirms_l2`
- Hard cap: L2 auto-applies ≤ 10 corrections per video without user-visible diff; > 10 → write to `transcribe_warnings.json` only, do NOT mutate segs.json
- segs.json corrections produce `segs.json.corrections.jsonl` sidecar (append-only audit log) — original segs.json untouched in re-runs that don't trigger new warnings (D-29 spirit)

**Phase to address:** CORR-01 (all 3 layers); plan must include negative-test: a clean non-suspect video must produce empty `transcribe_warnings.json` (proves no false-flag)

**Severity:** Critical — silently wrong content with high-confidence stamp is worse than visibly wrong

---

### P-02: Citation Pollution (CORR-02 行内溯源 token noise)

**What goes wrong:**
- Every sentence ends with `[seg_0042_000003.jpg @ 00:01:23]` → unreadable wall of brackets
- Vague claims ("这个工具很好用") forced to cite the nearest frame even when no specific frame supports it ("citation theater")
- Claude games the metric by citing whichever frame is closest to the paragraph midpoint, regardless of relevance
- Long sections (concept explanation) where every sentence is paraphrasing get the same citation 5 times in a row
- TL;DR section / glossary entries / "你需要知道什么" prelude get cited too — creating fake precision for synthesized content

**Warning signs:**
- > 60% of sentences have inline citations (target: 30-50% — only specific claims)
- Same `[seg_xxxx_xxxxxx.jpg @ HH:MM:SS]` appears > 3 times in same section
- Citations on paragraphs 0-50 (top-of-doc structural content like "你需要知道什么")
- Reader feedback: "感觉被脚注淹没了"

**Prevention:**
- **Citation eligibility rules** (hard scoping):
  - REQUIRED on: code blocks, specific parameter values (fps, seconds, file paths), direct quotes, UI element references ("点击 X 按钮")
  - FORBIDDEN on: TL;DR section, "你需要/不需要知道什么" prelude, glossary inline annotations, 章节小结/总评 segments, transition sentences
  - OPTIONAL on: conceptual explanation, "为什么这么做" 小段
- Format-spec extension (locked): citation immediately after the load-bearing token, NOT after every period — `点击 [设置图标](frames/seg_0042_000003.jpg @ 00:01:23) 进入命令面板。然后切换到 MTC 模式。` (one citation, two sentences)
- Reviewer (CORR-03) MUST flag "vague claim with citation" as a warning — citation theater is worse than no citation
- Token budget cap: average ≤ 1 citation per 3 sentences across whole doc (CORR-02 self-check measures this; > 1 per 2 sentences triggers WARNING in summary footer)

**Phase to address:** CORR-02 (定 citation eligibility + format placement); CORR-03 (verifier checks for theater)

**Severity:** Critical — kills D-01 readability, the whole point of v1.1

---

### P-03: Reviewer Feedback Loop (CORR-03 verifier × writer dance)

**What goes wrong:**
- Reviewer hallucinates problems ("这个步骤不清晰") → writer rewrites perfectly clear section
- Writer + reviewer agree on wrong (both saw the same wrong frame, both miscount steps) → high-confidence wrong output
- Auto-rewrite makes things worse (reviewer flagged wording, writer rewrites the technical claim too)
- Cost explosion: review pass = 80-100% of original write pass; with rewrite-on-critical = 200% cost worst case
- Infinite loop avoided by max-1-rewrite cap, but max-1 means: if rewrite is worse, you ship the worse version

**Warning signs:**
- `<slug>-REVIEW.md` lists > 30 critical issues on a clean summary (reviewer overreach)
- Rewrite triggered but post-rewrite REVIEW.md has NEW critical issues (regression)
- Same issue re-appears in reviewer's own re-review of the rewrite
- Token spend per video > 2.5x v1.0 baseline

**Prevention:**
- **Reviewer prompt scoping** (locked, byte-equal): reviewer judges ONLY against (a) format-spec 4 invariants, (b) plan.md mode rules, (c) inline citation timestamp validity, (d) glossary term consistency. Reviewer is FORBIDDEN from second-guessing pedagogical choices ("这个解释方式不好")
- **Severity gate**: only `critical` (factually wrong: timestamp doesn't exist / code differs from frame / cited frame missing) triggers rewrite. `warning` and `info` go to REVIEW.md only, no rewrite
- **Rewrite is delta, not full**: rewrite ONLY the flagged sentences/paragraphs, not the whole doc. Implementation: reviewer outputs `{section_anchor, original_text, suggested_text, evidence}` — writer applies as targeted edits
- **Max-1 rewrite cap is final**: if post-rewrite review still has critical issues, append `<slug>-UNRESOLVED.md` listing them, ship summary as-is, alert user. NO 2nd rewrite — D-03 automation-first does NOT mean "automate until perfect"
- **Cost ceiling**: rewrite triggered only if `critical_count > 3 OR contains_factual_error`; ≤ 3 isolated criticals → REVIEW.md only
- **A/B safety**: if rewrite happens, keep `summary.md.pre-review.md` until next run (auto-deleted on next `summarize-video` invocation) — user-recoverable mistake

**Phase to address:** CORR-03 (entire pitfall is this phase's design space)

**Severity:** Critical — gets the cost economics of v1.1 wrong AND can ship worse content than v1.0

---

### P-08: D-29 Byte-Equal Regression (the #1 v1.0 invariant)

**What goes wrong:**
- New writing prompt added in v1.1 → re-running 17 archives produces different summary.md
- New default artifact (`transcribe_warnings.json`, `_glossary.md`, `<slug>-REVIEW.md`) writes to old slugs on first re-run → cache cascade invalidation (sidecar params hash changes → segs.json regen → paragraphs.json regen → summary.md regen)
- Even if re-run is BETTER, byte-equality is broken — cannot prove v1.1 is purely additive
- TEACH-A "你需要知道什么" header retroactively prepended to old summaries
- Inline citations CORR-02 inserted into existing summary text on re-run

**Warning signs:**
- `git diff --stat output/<old_slug>/` after v1.1 install shows non-zero changes
- `state.jsonl` of old archives has new event types
- `<artifact>.params.json` sidecar has new keys for archives last touched in v1.0

**Prevention:**
- **Opt-in flag for ALL v1.1 features** at the slug level: `output/<slug>/.v11_features.json` opt-in marker. Without this marker, code paths take v1.0 branch byte-equal. Default for new slugs in v1.1+: marker created at ingest time
- **No retroactive artifact creation**: re-running an old slug WITHOUT marker MUST NOT write `transcribe_warnings.json` / `_glossary.md` updates / REVIEW.md / new sidecar keys
- **17-archive replay test**: phase 1 of v1.1 milestone is to record byte-hash of all 17 summary.md files; CI/manual test re-runs each and checks hash equality. ANY hash mismatch on a non-marked slug = phase block
- **New artifacts in NEW filenames**: don't extend `meta.json` schema — write `meta.v11.json` sidecar. Don't extend `params.json` sidecar — add `params.v11.json` sibling. Old code reads only old files
- **Glossary append is gated**: TEACH-A's `_glossary.md` append happens only if slug has `.v11_features.json` marker; old slug's terms aren't auto-extracted
- **Writing prompt versioning**: hash the writing prompt; if slug `plan.md` has `prompt_version: v10`, use v1.0 prompt verbatim regardless of current code

**Phase to address:** Phase 1 of v1.1 (foundation phase, before any feature work). Must include:
- baseline-replay test infrastructure
- `.v11_features.json` opt-in pattern
- `prompt_version` lock

**Severity:** Critical — invalidating 17 archives = re-doing the entire v1.0 corpus = milestone failure regardless of feature quality

---

### P-09: Token Budget Explosion (3 layers compound multiplicatively)

**What goes wrong:**
- L1 ASR scan = 1x paragraphs.json read
- L2 context-correction = 1x paragraphs.json + 1x meta.json + iteration over warnings
- L3 multi-modal = N frame Reads (potentially 10-30 frames for term verification)
- CORR-02 self-check = re-read entire summary.md + paragraphs.json
- CORR-03 verifier = read summary.md + paragraphs.json + key frames + plan.md (and may rewrite)
- Sum: 2.5-3x per-video Claude context usage vs v1.0
- Claude Max plan has rate limits — heavy v1.1 workflow can hit "session-context-too-long" or daily quota

**Warning signs:**
- Single video processing wall-clock 2.5x+ vs v1.0 baseline
- Hitting Claude session context window limits mid-summary
- Daily quota exhaustion after 3-4 videos (vs v1.0's 8-10)
- Empirical token count (if measurable) > 200K per video for 30-min source

**Prevention:**
- **Hard caps with measurable budgets**:
  - CORR-01 L3 (multi-modal verification): max 5 frames per `transcribe_warnings.json` entry; warnings beyond 10 entries skip L3
  - CORR-03 verifier: read paragraphs.json + summary.md + plan.md ONLY. Frames read on-demand for `critical` checks only (max 10 frames)
  - CORR-03 rewrite: max-1-rewrite cap (already locked)
  - TEACH-A glossary lookup: NO read of `_glossary.md` during writing (it's append-only per P-04)
- **Layer budget reporting**: each phase emits `output/<slug>/.token_budget.json` with estimated tokens per layer; CI test asserts total ≤ 2x v1.0 baseline
- **Skip-able layers on cost pressure**: env var `VIDEOSUMMARY_SKIP_REVIEWER=1` skips CORR-03 entirely (degrade path: ship CORR-01 + CORR-02 only). Documented as "low-quota mode"
- **L1 detection cheap-path first**: L1 is grep-based regex/heuristic (NOT Claude reading), only L2/L3 use Claude context. Implement L1 as pure Python in agent.tools so it's free
- **Frame Read deduplication**: if CORR-03 needs same frame as CORR-01 L3, cache per-session (within same `/summarize-video` invocation, frame contents reused)
- **Empirical baseline phase**: pick 3 v1.0 archives, measure token spend; v1.1 implementation MUST stay under 2x measured baseline. Phase Done = empirical pass, not just functional pass

**Phase to address:** All correctness phases (CORR-01/02/03) plus Phase 1 foundation must include budget infrastructure (`.token_budget.json` schema + CI assertion)

**Severity:** Critical for ¥0 constraint sustainability — could make v1.1 functionally great but practically unusable on Max plan

---

## Moderate Pitfalls

### P-04: Glossary Drift (TEACH-A `output/_glossary.md`)

**What goes wrong:**
- Two terminals append to `_glossary.md` simultaneously → file corruption (interleaved lines)
- Same term "ECS" gets 3 different definitions across summaries (each Claude write defines it from local context)
- Unbounded growth: after 50 videos, `_glossary.md` is 5000 lines, no curation
- Author skips inline annotation in summary.md because "_glossary.md covers it" — directly violates D-01 "self-contained, don't assume reader read other files"
- Glossary entry says "see summary X" — D-01 violation (assumes reading order)

**Warning signs:**
- `_glossary.md` has duplicate term entries with different definitions (grep `^## `)
- summary.md skips inline annotation for terms that ARE in glossary
- glossary entries reference other slugs by path
- `_glossary.md` line count grows linearly with videos (no consolidation)

**Prevention:**
- **Lock _glossary.md writes**: extend the per-slug FileLock pattern (v1.0 PARA-04) to a project-level `output/.glossary.lock`. Acquire when appending entries
- **Inline-first invariant** (D-01 enforcement): TEACH-A writing prompt says "EVERY first-occurrence term in summary.md gets inline annotation, REGARDLESS of glossary state". Glossary is an append-only log, NOT a consultation source for the reader
- **Glossary entry schema**: `## 术语 (English/中文释义)` + 1-line definition + `首次出现: <slug>` (one slug only — first-seen wins; later slugs DO NOT update existing entry, append new entry suffixed `_2` / `_3` if conflicting definition)
- **No cross-references**: glossary entries MAY NOT contain `[详见 output/<other_slug>/summary.md]` — D-01 forbids
- **Bounded growth via index file**: `_glossary.md` is just a flat append log; reading is via `output/_glossary_INDEX.md` (auto-rebuilt every N appends, dedupes, links definitions). Writers never read glossary; only the rebuild step consolidates
- **Drift-detection report**: a separate `python -m agent.tools glossary_audit` lists terms with conflicting definitions across summaries (read-only, K5 — surfaces drift, doesn't auto-fix)

**Phase to address:** TEACH-A (inline-first rule + lock infrastructure); MISC phase or TEACH-A末尾 for `glossary_audit` tool

**Severity:** Moderate — drift accumulates slowly; lock race is a real bug but easy fix

---

### P-05: Self-Contained Over-Explanation (TEACH-A patronizing tone)

**What goes wrong:**
- Every term annotated, including obvious ones ("Python (一种编程语言)" / "JSON (一种数据格式)")
- "你需要知道什么 / 你不需要知道什么" header is 30 lines, ranking trivial preconditions
- Annotation tone reads condescending — explaining everything to a "零基础" reader becomes noise to mid-level readers
- Every video has the same opener boilerplate; reading 10 summaries in a row means reading the same intro 10 times
- "你需要" header becomes its own format-spec invariant, with no actual differentiation between videos

**Warning signs:**
- summary.md > 50% of pre-Phase-1 lines are annotation/preamble rather than content
- "你需要知道什么" lists > 5 items
- annotations explain terms that are explained in other annotations (recursive over-explanation)
- subjective: reading two summaries back-to-back feels repetitive in the opener

**Prevention:**
- **Annotation eligibility rules** (locked):
  - REQUIRED: domain-specific tools (Trae SOLO / Godot ECS / pyannote / faster-whisper), proper nouns, acronyms, technical concepts NOT in CS undergraduate curriculum
  - FORBIDDEN: programming languages by name (Python/JS), general formats (JSON/YAML/Markdown), Claude/ChatGPT/Cursor by name (assume audience knows AI tools), basic operations ("点击" / "保存")
  - OPTIONAL: framework names (React/Vue/Bevy), industry-specific jargon (LoRA, embedding)
- **"你需要知道什么" cap**: max 3 prerequisites + max 3 "你不需要" items. > 3 → reviewer flags as bloat
- **Tone constraint** (CORR-03 verifier check): annotation must read "neutral definition", NOT "explainer talking to a child". Forbidden patterns: "你可能不知道..." / "简单来说..." / "说白了..."
- **Per-summary novelty check**: if `_glossary.md` already has entry for term X with same definition, summary.md inline annotation can be shorter ("X (见上下文为 [definition])") — annotation present but compressed
- **A/B with v1.0 sample**: pick 3 summaries from 17 archives, manually re-write with TEACH-A rules, user-review tone. Lock annotation style from this sample before v1.1 ships

**Phase to address:** TEACH-A (eligibility rules + tone constraint); CORR-03 (tone enforcement in verifier)

**Severity:** Moderate — degrades reading experience, but doesn't cause factual errors

---

### P-06: TL;DR Drift (TEACH-B 5-min speedrun)

**What goes wrong:**
- TL;DR contradicts main body (TL;DR says "5 steps", body has 7 steps after writer revised)
- Skimmer reads ONLY TL;DR, never main body → defeats D-01 self-contained (TL;DR isn't itself self-contained)
- TL;DR length creep: starts as 10-15 lines, drifts to 50 lines on long videos
- TL;DR contains citations — meta-noise for skimmer
- TL;DR generated FIRST, then body diverges, no sync check

**Warning signs:**
- TL;DR step count ≠ body H2 count
- TL;DR > 20 lines on any video
- TL;DR contains `[seg_xxxx @ HH:MM:SS]` tokens
- TL;DR mentions a tool/term not in glossary or annotated in body

**Prevention:**
- **Write TL;DR LAST** (after body + after CORR-03 verifier pass + after rewrite if any). TL;DR derives from final body, never the other way around
- **TL;DR length lock**: 10-15 lines, hard cap 20. Line count enforced by CORR-03 verifier
- **No citations in TL;DR**: format-spec extension. TL;DR sentences point to section anchors instead — `详见 §三、消化阶段`
- **TL;DR-body sync check** (verifier rule): every claim in TL;DR maps to a section in body. If body has 7 steps, TL;DR steps == body H2 count for steps-mode summaries
- **TL;DR is OPTIONAL**: only generated for videos > 20 min OR summary.md > 600 lines. Short summaries get no TL;DR (avoids ratio drift where TL;DR is half the doc)
- **Skimmer-defense framing**: TL;DR opening line says "本节是导览，不替代正文 — 复刻请读正文章节"

**Phase to address:** TEACH-B (entire pitfall is this phase's design space)

**Severity:** Moderate — TEACH-B is 🟡 want-to-do, can defer if pitfall too costly to address

---

### P-07: Heuristic Over-Trust (TOOL-A / TOOL-B vs K5 boundary)

**What goes wrong:**
- Claude blindly accepts `mode_signals.json` recommendation → mode判错 → integral re-write
- `schedule_suggestion.json` is wrong (silence detection missed dialog, scene detection over-segmented) → Claude follows it → bad抽帧
- Tool runs once at Phase 2; signals stale by Phase 5 (Claude revised plan.md but didn't re-run tools)
- K5 spirit silently violated: tool says "recommend mode = X" → Claude rubber-stamps without re-judging
- New users grok the tools as "decision-makers" rather than "signal providers"

**Warning signs:**
- plan.md mode field byte-equal to mode_signals.json's `recommended_mode` for > 80% of videos (no Claude judgment override)
- schedule.json segments byte-equal to schedule_suggestion.json (no Claude refinement)
- Mode mis-classifications correlate with mode_signals.json wrongness (Claude not catching tool errors)
- Tool output mentioned in plan.md "evidence" section instead of paragraphs.json text

**Prevention:**
- **Tool output schema makes K5 explicit**: every signal field paired with `evidence: <text excerpt>` — Claude must cite raw evidence, not the recommendation. Output uses `signals: [...]` not `recommendation: X`
- **Plan.md must cite raw paragraphs**: TEACH-A writing prompt requires `classification_evidence` field reference paragraphs.json text, NOT mode_signals.json. Tool helps Claude find evidence faster, doesn't substitute for it
- **No `recommended_mode` field in mode_signals.json**: output is `signals: {code_fence_density: 0.7, question_density: 0.05, ...}` only. Claude maps signals → mode in plan.md, NOT the tool
- **schedule_suggestion.json is OPT-IN consultation**: Claude must `Read` it explicitly (not auto-loaded). plan.md notes "已参考 schedule_suggestion.json" if used; default Phase 4 flow does NOT pre-include it
- **Verifier (CORR-03) cross-check**: if plan.md mode field disagrees with mode_signals.json `dominant_signal`, verifier asks "explain divergence" — divergence is HEALTHY (proves Claude judging), not a flag
- **Tool output stamps timestamp + paragraphs.json hash**: if plan.md was written when paragraphs.json had hash X but mode_signals.json was generated at hash Y ≠ X, signal is stale, Claude must re-run tool or ignore

**Phase to address:** TOOL-A and TOOL-B (entire pitfall); CORR-03 (divergence acceptance check)

**Severity:** Moderate — TOOL-A/B are 🟡 want-to-do, can defer; but if shipped, K5 erosion is the v1.0 invariant most at risk

---

### P-10: Two-Terminal Regressions (NEW lock domains)

**What goes wrong:**
- `output/_glossary.md` is project-wide write target — two slugs being summarized in parallel both append → race
- `~/.videoSummary/queue.json` (MISC-02) is single-file global state — two terminals running `queue next` get same slug → both work on same video
- `<slug>-REVIEW.md` re-write race (writer rewriting per CORR-03 while user manually inspects)
- v1.0 PARA-XX work assumed all writes were per-slug; v1.1 introduces project-global writes that break this assumption

**Warning signs:**
- `_glossary.md` has interleaved partial lines (corrupted entry mid-line)
- Two different `output/<slug>/` directories show same `queue_position` from queue.json
- `.resume.lock` works fine but data corruption appears in `_glossary.md` only

**Prevention:**
- **Project-level lock infrastructure**: extend v1.0's `_lock.py` to support `output/.glossary.lock` and `~/.videoSummary/.queue.lock`. Same stale-PID detection logic
- **Glossary lock acquisition**: any `_glossary.md` append acquires `output/.glossary.lock`; held only for duration of append (ms-scale, not full summary write). Lock release atomic
- **Queue lock semantics**: `queue next` acquires lock, marks slug `in_progress: <pid>`, releases lock. Other terminal `queue next` sees `in_progress` slug, skips it (returns next free slug)
- **REVIEW.md per-slug lock**: REVIEW.md write piggybacks on existing `output/<slug>/.resume.lock` (already in v1.0). New writes go through same path
- **Lock test matrix**: phase plan includes test "2 terminals, 2 different slugs, glossary appends interleave correctly". Existing `tests/test_locking.py` extended
- **Documentation**: CLAUDE.md `## 多终端并行` section gets new sub-section for v1.1 lock domains. Same table format as v1.0

**Phase to address:** Phase 1 v1.1 foundation (lock infrastructure); TEACH-A (glossary lock); MISC-02 (queue lock)

**Severity:** Moderate — v1.0 already learned the lock pattern, v1.1 extension is mechanical, but missing means data corruption

---

## Minor Pitfalls

### P-11: Backward-Incompat on 17 Archives (cache cascade on retroactive artifacts)

**What goes wrong:**
- Re-processing old slug pollutes summary with v1.1 features without opt-in
- `transcribe_warnings.json` added retroactively to old slug → triggers re-aggregation cascade
- Old paragraphs.json sidecar `params.json` doesn't have new keys → looks "stale" → re-runs ASR
- User runs `python -m agent.tools doctor` on old slug, sees "v1.1 features missing" warnings, "fixes" → corrupts archive

**Warning signs:**
- After v1.1 install, `doctor` subcommand on old slug says "stale cache: missing v11 fields"
- `state.jsonl` of old slug grows after v1.1 install (new event types appended)
- `params.json` files in old slugs touched after v1.1 install (mtime change)

**Prevention:**
- **Sidecar key detection**: missing v1.1 keys in old `params.json` → use v1.0 defaults SILENTLY, do not warn, do not trigger regen (treat as "v1.0 cache valid", not "stale")
- **Doctor subcommand v1.1 changes are additive only**: new column "v11_status" reads "n/a (pre-v11 archive)" for old slugs, never "stale" or "missing"
- **No retroactive `transcribe_warnings.json`**: covered in P-08, restated here for cache cascade
- **Migration runbook**: `docs/v11-migration.md` documents "if you want to upgrade old slug to v1.1 features, here's the explicit opt-in: `touch output/<slug>/.v11_features.json && python -m agent.tools rebuild <slug>`". Default behavior: no migration
- **17-archive verification at v1.1 phase 1 closeout**: re-run `doctor` on all 17, expected output is byte-equal to pre-v1.1 doctor output. Phase block on any diff

**Phase to address:** Phase 1 v1.1 foundation (covers most of P-08 + P-11 together)

**Severity:** Moderate — overlaps significantly with P-08 but distinct in mechanism (P-08 is about NEW feature contamination; P-11 is about CACHE INVALIDATION cascade)

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|---|---|---|
| Phase 1 (v1.1 foundation: opt-in flag, lock infra, baseline replay) | P-08 byte-equal regression / P-10 lock domains / P-11 cache cascade | Phase 1 is gating: 17-archive replay test must pass before any feature phase starts. `.v11_features.json` opt-in pattern + lock infra + sidecar versioning all implemented here |
| CORR-01 (3-layer ASR correction) | P-01 correction runaway / P-09 token budget | L1 in pure Python (no Claude tokens); L2 requires 2 evidence sources; L3 timestamp window ≤ ±0.5s; max 5 frames per warning; `segs.json.corrections.jsonl` audit log |
| CORR-02 (self-check + 行内溯源) | P-02 citation pollution / P-09 token budget | Citation eligibility rules locked (required/forbidden/optional sets); average ≤ 1 citation per 3 sentences; FORBIDDEN in TL;DR / glossary / prelude |
| CORR-03 (verifier sub-agent) | P-03 reviewer feedback loop / P-09 token budget | Reviewer scope locked to format-spec + mode rules + citation validity + glossary consistency (NOT pedagogical judgment); severity gate = `critical` only triggers rewrite; max-1-rewrite final; `.pre-review.md` backup |
| TEACH-A (零基础自包含 + glossary) | P-04 glossary drift / P-05 over-explanation / P-10 lock | Inline-first invariant (annotation regardless of glossary state); annotation eligibility rules locked; project-level `_glossary.lock`; "你需要知道什么" cap = 3+3 |
| TEACH-B (TL;DR speedrun) | P-06 TL;DR drift | Write LAST; 10-15 lines hard cap; no citations; sync check vs body section count; only for > 20min videos |
| TOOL-A (mode_signals.json) | P-07 heuristic over-trust | No `recommended_mode` field — only raw signals + evidence excerpts; CORR-03 accepts plan.md/signals divergence as healthy |
| TOOL-B (schedule_suggestion.json) | P-07 heuristic over-trust | Opt-in consultation only (not auto-loaded); paragraphs.json hash stamping for staleness detection |
| MISC-01 (AV1 warning demote) | (none significant) | Pure log-level change; ensure warning text byte-equal so old log-grepping doesn't break |
| MISC-02 (queue helper CLI) | P-10 queue file lock race | `.queue.lock` with same stale-PID logic as v1.0 `.resume.lock`; `in_progress: <pid>` marker prevents same-slug pickup |

---

## Cross-Cutting Patterns (read once, apply everywhere)

These are NOT individual pitfalls but recurring failure modes that touch multiple phases:

1. **"Additive but not really" trap** — Every v1.1 artifact swears it's additive. Test: `git diff` after re-running 17 archives must show 0 changes. If you can't pass that test, the additive claim is false. Apply to: every new file, every prompt change, every sidecar key.

2. **K5 erosion via convenience** — Every tool that outputs a "recommendation" rather than "evidence" weakens K5. Even if Claude formally re-judges, the recommendation primes. Apply to: TOOL-A, TOOL-B, mode_signals output schema, even REVIEW.md severity labels.

3. **Citation theater is worse than no citation** — A wrong citation (cited frame doesn't actually show the claim) is a confidence weapon for misinformation. Apply to: CORR-02 (don't cite when no source); CORR-03 (flag as critical, not warning).

4. **D-01 violations are quiet** — "see glossary" / "see other summary" / "as mentioned earlier" all break self-containment without obvious symptoms. Apply to: TEACH-A (inline-first), TEACH-B (TL;DR can't replace body), CORR-02 (citations are anchors not deferrals).

5. **Token budget compounds, not adds** — L1 → L2 → L3 → CORR-02 → CORR-03 → maybe-rewrite is a multiplicative chain. 1.2x per layer = 2.5x total for 5 layers. Apply: budget per-layer caps, not just total.

---

## Sources

- v1.0 PROJECT.md Validated requirements + Key Decisions table (D-29 / K5 / ¥0 invariants)
- v1.1-CANDIDATES.md (D-01 / D-02 / D-03 locked decisions + 8 candidate must-haves)
- codebase/CONCERNS.md (existing tech debt context: §1.1 three frame impls / §5.4 cache validation / §11 storage growth — same patterns CORR-01 cache must avoid)
- CLAUDE.md `## 视频类型变奏` § format-spec lock (4 invariants TEACH-A and CORR-03 verifier must preserve)
- CLAUDE.md `## 多终端并行` § (v1.0 lock pattern that v1.1 extends)
- 17 archive corpus (`output/<slug>/`) — empirical byte-equal regression test ground truth

**Confidence levels:**
- HIGH: P-08 (D-29 mechanism well-understood from v1.0 Phase 6 spec), P-10 (v1.0 PARA-XX taught the lock pattern), P-04/P-11 (cache cascade and lock race are direct extensions of known v1.0 patterns)
- MEDIUM: P-01/P-02/P-03/P-05/P-06 (LLM agent design pitfalls observed in similar tools — Roo Cline reviewer loops, Cursor self-check fatigue — but specific to videoSummary's 3-layer + 4-mode arch unverified empirically)
- MEDIUM-LOW: P-07 (TOOL-A/B not yet built; K5 erosion mechanism analogical from v1.0's experience with detect_scenes/detect_silence which DID hold the line)
- MEDIUM: P-09 (token budget compounding mathematically certain; specific 2.5x figure inferred from layer count, not measured — Phase 1 must produce empirical baseline)
