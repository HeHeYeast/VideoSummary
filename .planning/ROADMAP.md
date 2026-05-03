# Roadmap: videoSummary

## Milestones

- ✅ **v1.0 — videoSummary v1.0** — Phases 01-06 (shipped 2026-05-02). Full archive: [`.planning/milestones/v1.0-ROADMAP.md`](milestones/v1.0-ROADMAP.md)
- 🔄 **v1.1 — summary-quality** — Phases 07-09 (started 2026-05-03). 18 v1.1 requirements, granularity=coarse.

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

### v1.1 — summary-quality

- [x] **Phase 07: Warm-up + K5 emitters + D-29 foundation** — Opt-in marker, 17-archive replay gate, token-budget baseline, 4 new K5 read-only signal CLIs, MISC打杂. Zero behavior change to summary.md. (completed 2026-05-03)
- [ ] **Phase 08: Writing rules — CLAUDE.md extensions + glossary** — L2/L3 ASR context correction prompts, inline-trace tokens, zero-baseline header, inline term annotation, cross-slug glossary CLI, TL;DR speedrun. New summaries diverge in shape.
- [ ] **Phase 09: Correctness automation — verifier subagent + auto-rewrite** — `summary_lint` mechanical checker + Phase 7.5 verifier subagent (`Task(general-purpose)`) + delta auto-rewrite (max-1) + UNRESOLVED fallback.

## Phase Details

### Phase 07: Warm-up + K5 emitters + D-29 foundation
**Goal**: Establish v1.1 opt-in foundation (D-29 byte-equal preserved on 17 archives), ship 4 new K5 read-only signal emitters that Claude can consult but never auto-promote, demote AV1 noise, and add a queue helper. Zero behavior change to any newly written `summary.md`.
**Depends on**: v1.0 Phase 06 (FileLock pattern reused; `agent/_lock.py` shipped)
**Requirements**: PRE-V11-01, PRE-V11-02, PRE-V11-03, MISC-01, MISC-02, TOOL-A, TOOL-B, CORR-01a
**Success Criteria** (what must be TRUE):
  1. **17-archive replay PASS gate (P-08)** — `scripts/replay_v10_archives.py` re-runs all 17 v1.0 archived slugs and produces byte-equal `summary.md` / `segs.json` / `paragraphs.json` / `meta.json`. Any single byte diff → phase NOT shippable. Replay invoked manually before phase close.
  2. **`.v11_features.json` opt-in marker controls all v1.1 paths** — slugs without the marker silently take v1.0 code branches (no `transcribe_warnings.json` written, no new event types in `state.jsonl`, no glossary append, no inline traces in summary.md, no new sidecar keys). User can verify by `git diff` on any archived `output/<slug>/` after phase 07 install.
  3. **`.token_budget.json` baseline measured on 3 representative archives** — replicate-guide / interview-distillation / extension-applications archives each get a `.token_budget.json` recording v1.0 baseline token cost per layer (transcribe / aggregate / plan / write / cleanup). Phase 08 + 09 success criteria assert ≤ 2x this baseline.
  4. **4 new K5 emitters land with statically-asserted source-grep tests** — `transcribe_lint`, `mode_signals`, `schedule_suggest`, `glossary_audit` (read-only audit) CLIs all callable from `python -m agent.tools <cmd>`. Static test: each tool's source MUST NOT reference `schedule.json` / `plan.md` / `summary.md` filenames (mirrors v1.0 `cmd_detect_scenes` K5 assertion). User can run each CLI on any v1.0 archive and get JSON output without modifying any v1.0-shape artifact.
  5. **MISC打杂 shipped** — AV1 codec WARNING demoted to INFO (single line change in `agent/sources/_common.py` ffprobe gate); `python -m agent.tools queue {add|list|next|done|skip}` CLI works against `~/.videoSummary/queue.json` with `~/.videoSummary/.queue.lock` FileLock (reuses `agent/_lock.py`). Two-terminal `queue add` race test passes (no JSON corruption); `queue next` marks `in_progress: <pid>` so the other terminal skips to the next free slug.
**Plans**: 3 plans
  - [x] 07-01-PLAN.md — D-29 foundation (PRE-V11-01/02/03): `agent/_v11.py` opt-in marker helpers + `scripts/replay_v10_archives.py` 17-archive byte-equal regression test + `scripts/measure_token_budget.py` baseline writer + 3 representative archive `.token_budget.json` files
  - [x] 07-02-PLAN.md — MISC chrome (MISC-01/02): AV1 WARNING→INFO single-line demote + `agent/queue.py` cross-terminal queue with `~/.videoSummary/.queue.lock` + 5 `queue {add|list|next|done|skip}` subcommands wired into `agent/tools.py`
  - [x] 07-03-PLAN.md — K5 emitters (CORR-01a, TOOL-A, TOOL-B + Phase-08-helper stub): `pypinyin>=0.55.0` install + `agent/transcribe_lint.py` + `agent/mode_signals.py` (no `recommended_mode` field) + `agent/schedule_suggestion.py` (mandatory FPS-04 baseline) + `agent/glossary_audit.py` stub + `tests/test_k5_emitters.py` source-grep K5 boundary assertions + CLAUDE.md "v1.1 opt-in marker + 4 K5 emitters" section

### Phase 08: Writing rules — CLAUDE.md extensions + glossary
**Goal**: Make new summaries (slugs with `.v11_features.json` marker) diverge in shape — inline ASR corrections via L2/L3 prompts, inline trace tokens after every load-bearing claim, zero-baseline self-contained header, first-mention inline term annotations, cross-slug `output/_glossary.md` accumulation with FileLock, optional 5-min TL;DR speedrun for long videos. All format changes are prompt + Markdown convention; only the glossary append needs new Python.
**Depends on**: Phase 07 (consumes `transcribe_warnings.json` from CORR-01a; uses `.v11_features.json` opt-in marker; runs under `.token_budget.json` ≤ 2x baseline assertion)
**Requirements**: CORR-01b, CORR-01c, CORR-02, TEACH-A1, TEACH-A2, TEACH-A3, TEACH-B
**Success Criteria** (what must be TRUE):
  1. **L2/L3 ASR corrections write to plan.md, never to segs.json (P-01)** — Claude reads `transcribe_warnings.json` in Phase 2, writes "已自动修正的术语" table to `plan.md` top, with per-correction evidence sources. Hard caps enforced by prompt: max 10 auto-applied corrections per slug; L2 requires ≥ 2 independent evidence sources (meta.title / description / adjacent paragraph); L3 multimodal verification limited to ≤ 5 frames per warning, ±0.5s window. `segs.json` NEVER mutated (D-29 invariant verified by replay).
  2. **Inline trace tokens enforced; citation pollution prevented (P-02)** — every concrete claim, parameter value, or screenshot reference in `summary.md` followed by `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` or `[para_ID @ HH:MM:SS]` token (8-char timestamp). Citation eligibility rules locked in CLAUDE.md: REQUIRED on specific claims/parameters/code/UI references; FORBIDDEN in TL;DR / glossary inline annotations / "你需要知道什么" prelude / 章节小结 transitions. Test summaries average ≤ 1 citation per 3 sentences (measured by Phase 09 `summary_lint`).
  3. **Self-contained zero-baseline header (D-01) renders correctly** — every new summary's top section: 标题 / UP / 时长 / 链接 → `## 读这篇前你需要知道` (≤ 3 行先决条件) → `## 你不需要知道什么` (≤ 3 行明确豁免) → optional `## 5 分钟速读版` (TEACH-B trigger) → 正文. Header hard cap ≤ 6 lines total (excluding TL;DR). Tone constraint: annotations never use "简单来说" / "说白了" / "你可能不知道" patterns (P-05 anti-patronizing).
  4. **Cross-slug glossary append works under FileLock without corruption (P-04)** — `output/_glossary.md` accepts append-only entries via `python -m agent.tools glossary append --slug <slug> --term "..." --definition "..."` CLI. `output/.glossary.lock` (reuses `agent/_lock.py`) serializes concurrent appends from two terminals; same (slug, term) pair is idempotent (skip if H2 anchor + slug-link exists). Inline-first invariant enforced by prompt: every first-mention term gets inline `术语 (English/中文释义)` REGARDLESS of glossary state — glossary is fallback-only, never excuses skipping inline annotation.
  5. **TL;DR drift prevented (P-06)** — `## 5 分钟速读版` block written LAST (after body + glossary appends), 10-15 lines hard cap (max 20), zero citations inside (uses section anchors `详见 §三、消化阶段` instead). Triggered by `paragraphs.json[-1].end > 1200` (20 min) OR `estimated_sections > 50`. Sync check (Claude self-verifies before phase close): TL;DR step count == body H2 step count for replicate-guide mode.
**Plans**: 2 plans
  - [x] 08-01-PLAN.md — TEACH-A3 glossary append code (agent/glossary.py + agent/tools.py glossary CLI subcommand + V11_FEATURES extension + tests/test_glossary.py FileLock race + extended K5 source-grep)
  - [ ] 08-02-PLAN.md — CLAUDE.md prompt extensions (CORR-01b/c L2/L3 corrections + CORR-02 inline trace tokens & self-check + TEACH-A1 inline term annotation + TEACH-A2 zero-baseline header + TEACH-B 5-min TL;DR speedrun) + 5th format-spec invariant + cross-refs in /summarize-video Phase 2/6/7/8

### Phase 09: Correctness automation — verifier subagent + auto-rewrite
**Goal**: Land the highest-token-cost layer last, so Phase 07 + 08 production data can inform per-layer cap tuning. Mechanical `summary_lint` checks format-spec + traces + glossary; Phase 7.5 verifier subagent (`Task(general-purpose)`) does scope-locked correctness review; critical findings auto-trigger ONE delta rewrite with backup; max-1 cap enforced; UNRESOLVED fallback for unfixable cases.
**Depends on**: Phase 08 (verifier checks the format-spec extensions, inline trace tokens, glossary entries, and TL;DR sync introduced in Phase 08)
**Requirements**: CORR-03a, CORR-03b, CORR-03c
**Success Criteria** (what must be TRUE):
  1. **`summary_lint` mechanical checker enforces 4-invariant format spec + citations (K5)** — `python -m agent.tools summary_lint <slug>/summary.md` produces `output/<slug>/summary_lint.json` with claim count, traces present, claims-without-trace line numbers, `[?]` count, and format-spec violations (8-char timestamp / explicit code-fence language / relative `frames/` path / second-person imperative + 5th invariant: trace-after-claim). Tool NEVER edits `summary.md` (K5 source-grep test asserts `summary.md` referenced only as input filename, never as write target).
  2. **Phase 7.5 verifier subagent stays scope-locked, never does pedagogical judgment (P-03)** — `/summarize-video` Phase 7.5 spawns `Task(subagent_type=general-purpose)` reading summary.md + paragraphs.json + plan.md + transcribe_warnings.json + summary_lint.json + ≤ 10 frames sampled from `claims_without_trace`. Subagent writes `output/<slug>/<slug>-REVIEW.md` with critical / warning / info three-tier findings. Verifier prompt scope locked to: (a) format-spec 4 invariants, (b) plan.md mode rules, (c) inline citation timestamp validity, (d) glossary term consistency. FORBIDDEN: any "this explanation is unclear" / "this should be rephrased" pedagogical critique. `VIDEOSUMMARY_SKIP_REVIEWER=1` env var degrades the entire phase 7.5 (low-quota fallback).
  3. **Max-1-rewrite cap enforced; pre-rewrite backup preserved (P-03)** — only `critical` severity findings trigger rewrite; `warning` / `info` go to REVIEW.md only. Rewrite is delta (targeted edits to flagged sentences/paragraphs, NOT full re-write). Pre-rewrite copy saved to `output/<slug>/summary.md.pre-review`. Hard cap: 1 rewrite per `/summarize-video` invocation, recorded as `rewrite_cycle_completed` event in `state.jsonl`. If post-rewrite review still finds critical issues → write `output/<slug>/<slug>-UNRESOLVED.md` listing them, ship summary as-is, exit cleanly. NO 2nd rewrite attempt automatically.
  4. **Token budget ≤ 2x v1.0 baseline (P-09)** — End-to-end `/summarize-video` on a marked slug (with all v1.1 features active) produces `.token_budget.json` showing total token spend ≤ 2x the Phase 07 measured baseline for the same mode (replicate-guide / interview-distillation / extension-applications). Per-layer caps verified: CORR-01 L3 ≤ 5 frames/warning AND ≤ 10 entries triggering L3; CORR-03 verifier ≤ 10 frames/run; rewrite ≤ 1 cycle. Phase 09 verification step: run end-to-end on 1 short test video AND assert token-budget cap holds.
**Plans**: TBD

## Next Milestone

To start the next milestone cycle after v1.1 completes, run `/gsd-new-milestone`. This will:
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
| 07. Warm-up + K5 emitters + D-29 foundation | v1.1 | 3/3 | Complete    | 2026-05-03 |
| 08. Writing rules — CLAUDE.md + glossary | v1.1 | 1/2 | In Progress|  |
| 09. Correctness automation — verifier + auto-rewrite | v1.1 | 0/? | Not started | — |

---

## Rationale Notes

**Phase numbering continuation**: v1.0 ended at Phase 06; v1.1 starts at Phase 07 (no `--reset-phase-numbers` from user). All future milestones continue the same monotonic counter.

**3 phases (consensus from research SUMMARY.md)**: Phase 07/08/09 maps directly to the convergent dependency graph from ARCHITECTURE.md + FEATURES.md + PITFALLS.md. Order forced by data flow:
- Phase 08 reads `transcribe_warnings.json` (Phase 07 output) for L2/L3 corrections
- Phase 09 verifier reads inline trace tokens (Phase 08 convention) + format-spec extensions (Phase 08) + summary_lint output

**Granularity = coarse**: Three phases is appropriate for 18 requirements grouped into 5 categories. Splitting further would fragment the K5 emitter cluster (Phase 07) or the prompt-extension cluster (Phase 08); compression into 2 phases would entangle the gating opt-in foundation with feature work.

**Phase 07 plan structure (3 plans, 2 waves)**:
- Wave 1 (parallel): Plan 01 (D-29 foundation, only new files) + Plan 02 (MISC chrome — independent file scope from Plan 01)
- Wave 2: Plan 03 (K5 emitters + CLAUDE.md + tools.py wiring) — depends on Plan 02 because both modify `agent/tools.py` (subparser additions); sequencing avoids merge contention
- Total: 8 reqs covered 1:1 across 3 plans (PRE-V11-01/02/03 in Plan 01; MISC-01/02 in Plan 02; CORR-01a + TOOL-A + TOOL-B in Plan 03)

**Critical pitfall coverage** (research SUMMARY.md "Top 5"):
- P-08 D-29 byte-equal regression → Phase 07 SC#1 (17-archive replay PASS gate)
- P-09 Token budget multiplicative → Phase 07 SC#3 (baseline) + Phase 09 SC#4 (≤ 2x assertion)
- P-03 Reviewer feedback loop → Phase 09 SC#2 (scope lock) + SC#3 (max-1 rewrite)
- P-01 Correction runaway → Phase 08 SC#1 (L2 ≥ 2 evidence sources, max 10 auto-applied, segs.json never mutated)
- P-02 Citation pollution → Phase 08 SC#2 (eligibility rules + ≤ 1 per 3 sentences)

**Research flags for plan-phase**:
- Phase 07: empirical token-budget baseline measurement on 3 archives + pypinyin false-positive rate (decides default-on vs opt-in for L1 detection)
- Phase 08: pure prompt + CLAUDE.md edits + glossary CLI on shipped FileLock — low risk, can skip research-phase
- Phase 09: `Task` subagent token cost on 1000-line summaries (no in-repo precedent; informs whether diff-review lands in v1.1 or defers to v1.2)

**Backward-compat invariants encoded**:
- D-29 byte-equal: Phase 07 SC#1 (17-archive replay) + SC#2 (`.v11_features.json` opt-in marker)
- K5 boundary: Phase 07 SC#4 (source-grep test on 4 new emitters) + Phase 09 SC#1 (summary_lint never edits summary.md)
- ¥0 cost: zero new paid APIs across all 3 phases (only `pypinyin>=0.55.0` pure-Python ~2MB added in Phase 07)
- Existing 5 CLI + `output/<slug>/` format unchanged: all v1.1 artifacts are new sibling files; no schema mutations
- Two-terminal safety: Phase 07 adds `~/.videoSummary/.queue.lock` (queue), Phase 08 adds `output/.glossary.lock` (cross-slug glossary); both reuse `agent/_lock.py` stale-PID logic without breaking v1.0 `.resume.lock` semantics

---

*Last updated: 2026-05-03 — Phase 07 planned: 3 plans across 2 waves (Plan 01 D-29 foundation + Plan 02 MISC chrome wave 1 parallel; Plan 03 K5 emitters wave 2 sequential due to agent/tools.py file ownership). All 8 Phase 07 reqs (PRE-V11-01/02/03 + MISC-01/02 + TOOL-A/B + CORR-01a) covered 1:1 across 3 plans. v1.1 summary-quality phases 07-09 derived from REQUIREMENTS.md (18 reqs, 5 categories) + research SUMMARY.md (3-phase consensus + 11 pitfalls). Coverage: 18/18 requirements mapped 1:1.*
