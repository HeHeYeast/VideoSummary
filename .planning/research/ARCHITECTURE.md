# Architecture Research — v1.1 Summary-Quality Milestone

**Domain:** Brownfield extension of a Claude-orchestrated local video-to-tutorial pipeline (¥0). Focus: how 8 v1.1 candidate features (3 必做 + 1 必做 zero-baseline + 2 想做 + 2 顺手) plug into the v1.0 architecture WITHOUT modifying validated artifacts (D-29 byte-equal invariant).
**Researched:** 2026-05-03
**Confidence:** HIGH for integration points and K5 boundary preservation (grounded in actual v1.0 code at `agent/tools.py`, `agent/scheduler.py`, `agent/_lock.py`, `agent/sources/__init__.py`); MEDIUM for CORR-03 verifier agent mechanism (no precedent for sub-agent in this repo, derived from gsd patterns + Claude Task tool); LOW for cross-slug glossary race semantics (no real-world signal yet).

> This document does not re-survey the v1.0 system — that lives in `.planning/codebase/ARCHITECTURE.md` (commit `c20d425`). It only specifies how the 8 v1.1 features plug in without breaking the existing layout.

---

## North Star Constraints (inherited from v1.0, re-asserted here)

Every architectural choice below is subordinate to four non-negotiables, all of which v1.0 successfully held across Phases 1-6:

1. **¥0 cost** — no paid API at any layer (Claude Max already pays for cognition).
2. **K5: Claude is decider, tools are limbs** — new tools may emit *signals / suggestions / detections*, but never auto-promote them into `plan.md` / `schedule.json` / `summary.md`. Statically asserted in tests where applicable (see `cmd_detect_scenes` / `cmd_detect_silence` precedent in `agent/tools.py:798-887`).
3. **D-29 byte-equal backward-compat** — the 17 archived `output/<slug>/summary.md` files MUST regen byte-equal when re-run on v1.1 code paths *that they did not opt into*. Practical implication: never modify `segs.json` / `paragraphs.json` / `meta.json` / `plan.md` / `schedule.json` / archived `summary.md` shape; only ADD new sibling artifacts.
4. **Single-user author tool** — no multi-tenancy, no server, no cloud. Cross-terminal contention solved by `agent/_lock.py` `FileLock` precedent (Phase 6 PARA-01).

When a v1.1 capability could be either "smarter Python" or "smarter Claude prompting", **default to prompting**; add Python only when the operation is mechanical (a pure transform with no judgment).

---

## System Overview (v1.1 additions in **bold**)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                  Claude Code (Decision Layer — UNCHANGED)                 │
│                                                                           │
│  Reads transcripts, JPEGs, meta.json, plan.md, signals JSONs.             │
│  Decides: video type, fps schedule, outline, prose, term corrections.     │
│                                                                           │
│  v1.1 NEW responsibilities (prompt-driven, not coded):                    │
│   - Read transcribe_warnings.json (if exists) and write plan.md           │
│     "已自动修正的术语" section (CORR-01 L2/L3)                            │
│   - Inline-trace tokens [seg_NNNN_NNNNNN.jpg @ HH:MM:SS] in summary.md    │
│     (CORR-02 B-layer; pure prompt convention, optional linter)            │
│   - Self-rate confidence per claim, mark < 80% with [?] (CORR-02 A-layer) │
│   - Inline term annotations + per-summary glossary append (TEACH-A)       │
│   - Optional 5-min TL;DR section at top of summary.md (TEACH-B)           │
│                                                                           │
│  v1.1 NEW workflow extension:                                             │
│   - Spawn Task subagent (general-purpose) as "summary-verifier" (CORR-03) │
└────────────────────────┬─────────────────────────────────────────────────┘
                         │ Bash / Read / Task / Write
        ┌────────────────┴─────────────────────────────────────────┐
        │                                                           │
        ▼                                                           ▼
┌──────────────────────────────────────┐         ┌────────────────────────────┐
│   agent/tools.py (CLI Surface)       │         │  output/<slug>/            │
│                                      │         │  (per-video filesystem)    │
│   EXISTING v1.0 (UNCHANGED):         │         │                            │
│    download / ingest                 │         │  EXISTING v1.0 artifacts   │
│    transcribe / aggregate            │         │  (UNCHANGED):              │
│    extract_frames / batch            │         │    meta.json               │
│    detect_scenes / detect_silence    │         │    video.mp4 / audio.wav   │
│    diarize / cleanup_frames          │         │    segs.json               │
│    doctor / list_frames              │         │    paragraphs.json         │
│    classify_frame / ocr_frame        │         │    plan.md (+sidecar)      │
│                                      │         │    schedule.json           │
│   v1.1 NEW (additive, K5):           │         │    frames/seg_*.jpg        │
│    transcribe_lint   (CORR-01 L1)    │         │    scenes.json             │
│    summary_lint      (CORR-02 helper)│         │    silence_map.json        │
│    mode_signals      (TOOL-A)        │         │    diarization.json (opt)  │
│    schedule_suggest  (TOOL-B)        │         │    summary.md              │
│    queue add/list/                   │         │    state.jsonl + .json     │
│      next/done/skip  (MISC-02)       │         │    .resume.lock            │
│                                      │         │                            │
│                                      │         │  v1.1 NEW artifacts        │
│                                      │         │  (additive, all sibling):  │
│                                      │         │    transcribe_warnings.    │
│                                      │         │      json (CORR-01 L1)     │
│                                      │         │    summary_lint.json       │
│                                      │         │      (CORR-02 self-check)  │
│                                      │         │    REVIEW.md (CORR-03)     │
│                                      │         │    mode_signals.json       │
│                                      │         │      (TOOL-A)              │
│                                      │         │    schedule_suggestion.    │
│                                      │         │      json (TOOL-B)         │
└──────────────────────────────────────┘         └────────────────────────────┘
                                                              ▲
                          ┌───────────────────────────────────┤
                          │                                    │
                ┌─────────┴────────────┐         ┌─────────────┴────────────┐
                │ output/_glossary.md  │         │ ~/.videoSummary/         │
                │ (TEACH-A cross-slug  │         │   queue.json             │
                │  accumulator)        │         │ (MISC-02 cross-slug)     │
                │                      │         │                          │
                │ Lock:                │         │ Lock:                    │
                │  output/             │         │  ~/.videoSummary/        │
                │   _glossary.md.lock  │         │   .queue.lock            │
                │ (FileLock pattern)   │         │ (FileLock pattern)       │
                └──────────────────────┘         └──────────────────────────┘
```

**Key insight:** v1.1 is **purely additive at the artifact layer**. Every new feature either (a) adds a new `output/<slug>/<artifact>.json` sibling, (b) adds a new `python -m agent.tools <subcommand>` (registered in the same `cmds` dict at `tools.py:1344`), or (c) adds a Claude prompt convention enforced inside `CLAUDE.md` `/summarize-video` workflow. **No existing artifact shape changes.** Two new shared artifacts (`output/_glossary.md`, `~/.videoSummary/queue.json`) live OUTSIDE per-slug directories and reuse `agent/_lock.py` for concurrency.

---

## Per-Feature Integration Plan

### CORR-01: ASR Term Correction (3 layers)

**Problem:** `Flux→Flox`, `LoRA→Lora/LOL/Laura`, etc. — ASR mis-spellings poison the entire summary downstream.

**Decision: split into 3 distinct integration points, layered.**

#### L1 — Detection: NEW CLI subcommand `transcribe_lint`

| Property | Value |
|----------|-------|
| Where | NEW `agent/transcribe_lint.py` + NEW handler `cmd_transcribe_lint` in `agent/tools.py` |
| Input | `output/<slug>/segs.json` (read-only), `output/<slug>/meta.json` (for title/uploader/description hints) |
| Output | NEW sibling `output/<slug>/transcribe_warnings.json` |
| K5 | Tool only **detects** suspicious tokens; never modifies `segs.json` |
| D-29 | Old videos that don't opt-in produce no warnings → no behavior change |
| Sidecar | `transcribe_warnings.json.params.json` per Phase 2 RES-01 (params: detection thresholds) |
| Lock | Wrapped in same `FileLock(out_dir / ".resume.lock", timeout=0)` as `cmd_transcribe`/`cmd_aggregate` (per-slug serialization) |

**Why a new CLI rather than a Claude prompt instruction?**
- Detection IS mechanical (hapax legomena scan, mixed-script detection, frequency-vs-form-variance Levenshtein clustering, comparison against `meta.title` token-set). It's a pure transform with **no judgment** — passes K5.
- Reusable: Claude can also read `transcribe_warnings.json` straight from disk in Phase 2 (cheap context).
- Cacheable: with sidecar, re-runs on same `segs.json` short-circuit (Phase 2 cache pattern).
- Verifier (CORR-03 sub-agent) can also read it without re-running detection.

**Schema (locked early in PHASE-CONTEXT, not finalized here):**

```json
{
  "version": 1,
  "warnings": [
    {
      "para_id": "p0023",                  // Reference into paragraphs.json (or seg_index)
      "seg_index": 142,                    // Index into segs.json
      "start": 387.5,
      "end": 391.2,
      "suspect_text": "Lora",              // Verbatim ASR token
      "suggested_text": "LoRA",            // Optional — empty if L1 can't suggest
      "evidence_source": "title_token",    // One of: title_token, frequency_variance, mixed_script, hapax
      "confidence": 0.85,                  // L1 detector confidence
      "context_before": "...用",
      "context_after": "训练..."
    }
  ]
}
```

**Important:** Schema is **NOT identical** to `agent/tools.py` Phase 5 `whisper_repetition_guard` warnings (which uses `trigram` + `count`); the two artifacts coexist (one per file, both written to the same `output/<slug>/`).

#### L2 — Context correction: pure Claude prompt action (no new code)

Claude reads `transcribe_warnings.json` + `meta.json` during Phase 2. For each warning, Claude infers true spelling using global context and writes a "已自动修正的术语" table to `plan.md`. Subsequent prose generation in Phase 6 uses the corrected forms.

**Why not modify `segs.json` directly?** D-29 violation. `segs.json` is parameter-hashed in `state.jsonl` and consumed by `aggregate`; mutating it would invalidate cache and break old re-runs. Recording corrections in `plan.md` (Claude-authored, additive) preserves the invariant.

#### L3 — Multimodal fallback: prompt instruction in Phase 4

When Phase 4 (frame reading) detects a UI element / title board / code keyword that bears on a CORR-01 warning, Claude prefers the visual reading over the ASR text. This is documented in `CLAUDE.md` `/summarize-video → Phase 4`. **No new artifact**; Claude updates `plan.md` "已自动修正的术语" inline.

#### Build order

```
CORR-01a (L1 cmd_transcribe_lint + transcribe_warnings.json) →
CORR-01b (CLAUDE.md prompt for L2/L3 + "已自动修正的术语" plan.md convention) →
                                                             ↓
                                                  CORR-03 verifier consumes transcribe_warnings.json
```

L1 must land before L2 (L2 reads L1's output). L3 is a Phase 4 prompt-only patch that can land independently.

---

### CORR-02: In-line Source Trace + Self-Check

**Problem:** Each claim in `summary.md` should be traceable to a specific frame OR paragraph; uncertain claims should be marked `[?]`.

**Decision: prompt-first, optional linter second.**

#### B-layer (in-line tracing): pure prompt convention

`CLAUDE.md` `/summarize-video → Phase 6` adds a writing rule:

```
Every concrete claim, parameter value, or screenshot reference MUST be followed by:
  - Frame trace:  [<frame_filename> @ HH:MM:SS]
  - Paragraph trace: [<para_id> @ HH:MM:SS]

The trace token is positioned immediately after the claim (before period), e.g.:
  "Click the [图层面板] eye icon [seg_0152_000010.jpg @ 00:02:32]."
```

**No new code needed for B-layer to function.** The format-spec lock's 4 invariants (timestamp `[HH:MM:SS]` 8-char, code-fence with language, relative `frames/` path, second-person imperative) are extended to a 5th invariant: **trace token after claim**.

#### A-layer (self-check + confidence): NEW CLI subcommand `summary_lint`

| Property | Value |
|----------|-------|
| Where | NEW `agent/summary_lint.py` + `cmd_summary_lint` |
| Input | `output/<slug>/summary.md` (read-only) |
| Output | NEW sibling `output/<slug>/summary_lint.json` |
| K5 | Tool only **counts** trace tokens, `[?]` markers, and detects claims-without-traces; never edits `summary.md` |
| Job | Mechanical regex/parser checks: total claim count, traces present, `[?]` count, format-spec 4 invariants statically checkable |
| D-29 | Old `summary.md` files that don't have trace tokens → linter reports "missing trace" warnings but never modifies the file |
| Sidecar | None (it's a one-shot lint, no params worth caching) |
| Lock | Read-only on `summary.md`; no lock needed (single-summary, single-author) |

**Why a linter rather than Claude self-rates only?**
- Self-rating is the A-layer per D-02. The linter **measures** what was self-rated (e.g., "5 of 47 claims marked `[?]`, 3 lack any trace token"). This produces the structured signal CORR-03 verifier needs to compute its critical/warning/info delta.
- Static checks (e.g., bare ```` ``` ```` fence) are pure text — Claude shouldn't waste tokens on them.

**Schema:**

```json
{
  "version": 1,
  "summary_path": "output/BV1xxx/summary.md",
  "claim_count": 142,
  "claims_with_trace": 135,
  "claims_without_trace": [{"line": 89, "snippet": "..."}, ...],
  "uncertainty_markers": 7,                      // count of "[?]" in body
  "format_spec_violations": [
    {"rule": "bare_code_fence", "line": 217, "snippet": "..."},
    {"rule": "absolute_image_path", "line": 304, "snippet": "..."}
  ]
}
```

#### Build order

```
CORR-02 prompt rule (CLAUDE.md update) → CORR-02 cmd_summary_lint → consumed by CORR-03
```

---

### CORR-03: Second Verifier Agent

**Problem:** Even after self-check, Claude may have systematic blind spots in its own writing. A fresh agent rereads with paragraphs + frames + plan and flags discrepancies.

**Decision: a Claude-spawned `Task` subagent (general-purpose), NOT a registered gsd-* agent type.**

| Property | Value |
|----------|-------|
| Mechanism | `/summarize-video → Phase 7.5` (NEW phase) calls `Task` tool with `subagent_type: general-purpose` |
| Subagent prompt | Lives inline in `CLAUDE.md` (or a new file `prompts/summary-verifier.md` referenced by `CLAUDE.md`); contains role + reading list + output format |
| Subagent reads | `summary.md`, `paragraphs.json`, `plan.md`, `transcribe_warnings.json`, `summary_lint.json`, sample of `frames/*.jpg` (chosen by the subagent based on `summary_lint.json`'s claims-without-trace rows) |
| Subagent writes | `output/<slug>/REVIEW.md` (Markdown — easy human + Claude diff-friendly) |
| Auto-rewrite | Parent agent reads `REVIEW.md`, if `critical: N > 0` → triggers ONE rewrite cycle, updates `summary.md` in place |
| Loop control | Hard cap: **1** rewrite per `/summarize-video` invocation. `state.jsonl` event `rewrite_cycle_completed` records the cap was used; 2nd run requires user to re-issue `/summarize-video` |
| Token cost | Verifier reads ~80% of writing context (paragraphs + summary + frames sample). Diff-only re-review on 2nd cycle deferred to v1.2 (initial impl: full re-review) |

**Why NOT a registered `.claude/agents/*.md` (gsd-style)?**

This repo has **NO `.claude/agents/`** directory and **NO `.claude/commands/`** directory (verified — `.claude/` contains only `settings.local.json` + worktrees). `/summarize-video` is documented in `CLAUDE.md` and recognized by Claude on the trigger phrase. Adding a registered agent infrastructure JUST for one verifier is over-investment relative to a `Task` invocation. If usage proves the verifier needs richer harness (e.g., dedicated tool allowlist), promote to registered agent in v1.2.

**Output schema (Markdown, but structured for diff):**

```markdown
# Summary Review: <slug>

**Reviewer:** general-purpose Task subagent
**Date:** YYYY-MM-DD
**Source:** summary.md (claim_count=142 from summary_lint.json)

## Critical (blocks ship)
- [Line 89] Claim "ECS 比 OOP 性能高 10x" not supported by paragraphs.json or any frame trace.
  - Suggested fix: remove or trace to source.

## Warning (should fix before ship)
- [Line 217] Code fence missing language tag.

## Info (style nit)
- [Line 12] Term "LoRA" first appears without inline annotation per TEACH-A convention.
```

#### Build order

```
CORR-02 (linter + traces) → CORR-03 (verifier reads linter output) → REVIEW.md → optional rewrite
                                                                            ↑
                                                                  TEACH-A glossary checks fold into Critical/Warning categorization
```

---

### TEACH-A: Zero-baseline Self-contained Summary

**Problem:** No assumed reading order, no assumed prior knowledge.

**Decision: 3 components, all prompt-first; only the cross-slug `_glossary.md` requires concurrency code.**

#### Component 1: Inline term annotation

Pure prompt convention in `CLAUDE.md` `/summarize-video → Phase 6`:

```
First mention of any non-trivial term: 术语 (English/中文释义).
Subsequent mentions: bare 术语, with optional "(详见 output/_glossary.md)".
```

No new code.

#### Component 2: Per-summary "你需要知道什么" header

Embedded in `summary.md` (NOT a separate file). New mandatory Phase 6 section before the body:

```markdown
> ## 读这篇前你需要知道什么
> - [3-5 prerequisites]
> ## 你不需要知道什么
> - [things this video does NOT require despite seeming relevant]
```

No new code; format-spec extension only.

#### Component 3: Cross-slug `output/_glossary.md` accumulator

| Property | Value |
|----------|-------|
| Location | `output/_glossary.md` (top-level under `output/`, NOT inside any slug dir) |
| Schema | Append-only Markdown; one H2 per term, body = definition + first-seen-in slug |
| Lock | NEW `output/_glossary.md.lock` via existing `agent/_lock.py:FileLock` |
| Writer | NEW CLI subcommand `glossary append --slug <slug> --term "LoRA" --definition "..."` (cmd_glossary_append) — Claude calls in Phase 6 once per new term |
| K5 | Tool just appends; never decides what's a term (Claude decides) |
| Race condition | Two terminals writing different terms simultaneously → FileLock serializes. Same slug + same term twice → idempotency: append checks "if H2 anchor for slug+term exists, skip" |
| D-29 | Pure additive top-level file; old slugs without entries unaffected |

**Schema design:**

```markdown
# Glossary

<!-- Auto-managed by `python -m agent.tools glossary append`. Hand-edit OK between runs. -->

## LoRA

> Low-Rank Adaptation. 用少量参数微调大模型的方法。
>
> First seen in: [BV1xxx](BV1xxx/summary.md) (2026-05-04)

## 47-tile autotile

> 8-邻接二值组合去对称后唯一的 47 张图块拼接算法。
>
> First seen in: [BV1HG9JBsEPK](BV1HG9JBsEPK/summary.md) (2026-04-30)
```

Append-only schema preserves human edit history; `glossary append` is **idempotent on duplicate (slug, term)** by checking for existing H2 anchor + slug-link before write.

**Why not full rewrite each time?** Append-only avoids losing manual edits; lock contention is minimized (locks only the append, not the whole file scan).

#### Build order

```
TEACH-A.1 (inline annotation prompt) — independent, no code
TEACH-A.2 (header section prompt) — independent, no code
TEACH-A.3 (cmd_glossary_append + _glossary.md + lock) — has code, depends on agent/_lock.py (already shipped Phase 6 PARA-01)
```

---

### TEACH-B: 5-min TL;DR Block

**Decision: embedded in same `summary.md` (mandatory NEW section), NOT separate file.**

| Question | Answer |
|----------|--------|
| Where in summary.md? | Right after the H1 + "读这篇前你需要知道" block, before "## 一、" body |
| Format | NEW format-spec invariant: `## 5 分钟速读版` H2 mandatory if `paragraphs.json[-1].end > 1800` (30 min) |
| Schema | Markdown bullets: 核心结论 (1-3 lines) / 工作流速查表 / 必看时间戳 (3-5 anchors) |
| Why not separate file? | Single-file rule: "find one file, get the whole thing." Splitting into `summary_tldr.md` violates D-01 self-contained spirit. |
| Trigger threshold | Duration-driven: long videos (≥ 30 min) MUST have it; shorter videos optional. Encoded in CLAUDE.md prompt, NOT a tool gate. |

**No new code.** Pure CLAUDE.md prompt extension. Verifier (CORR-03) checks the section exists when duration warrants.

---

### TOOL-A: `mode_signals.json` (Mode Classification Helper)

**Problem:** Claude eyeballs paragraphs + intuits primary mode. Wrong → expensive rewrite.

**Decision: NEW CLI subcommand modeled exactly on `cmd_detect_scenes` (the K5 precedent at `agent/tools.py:798-832`).**

| Property | Value |
|----------|-------|
| Where | NEW `agent/mode_signals.py` + `cmd_mode_signals` |
| Input | `output/<slug>/paragraphs.json` (read-only) |
| Output | NEW sibling `output/<slug>/mode_signals.json` |
| K5 | Tool emits **signals + suggested mode**; Claude still decides and writes `plan.md`. Statically asserted: source contains no reference to `plan.md` filename (mirrors `cmd_detect_scenes` K5 assertion) |
| Sidecar | `mode_signals.json.params.json` — params: which signals computed, which version of regex patterns |
| Lock | Wrapped in `FileLock(state_dir / ".resume.lock", timeout=0)` — same per-slug serialization as detect_scenes/silence |
| D-29 | Old slugs that don't run this never get the artifact |

**Schema:**

```json
{
  "version": 1,
  "video": "video.mp4",
  "signals": {
    "code_fence_density":        {"per_paragraph": 0.42, "interpretation": "high → replicate-guide"},
    "step_marker_density":       {"per_paragraph": 0.31, "interpretation": "high → replicate-guide"},
    "question_form_ratio":       {"per_paragraph": 0.05, "interpretation": "low → not interview"},
    "speaker_turn_signals":      {"intro_phrase_count": 0, "interpretation": "no guest intro"},
    "cross_tool_comparison_count": {"count": 0, "interpretation": "no extension-applications signal"}
  },
  "suggested_primary": "replicate-guide",
  "suggested_secondary": null,
  "confidence": 0.78,
  "rationale": "code_fence_density 0.42 + step_marker_density 0.31 dominate; no podcast or comparison signals"
}
```

**Where Claude consumes:** Phase 2 (after `aggregate`, before writing `plan.md`). Read it, sanity-check against own intuition, write `plan.md` with mode decision (which may agree or override).

#### Build order

```
TOOL-A is independent of CORR-* and TEACH-* — can land in any phase.
However: pairs naturally with TOOL-B (both K5 read-only signal emitters; same testing scaffold).
```

---

### TOOL-B: `schedule_suggestion.json` (FPS Strategy Helper)

**Problem:** Claude hand-writes `schedule.json` from `paragraphs.json` + `scenes.json` + `silence_map.json`. Mechanical wiring.

**Decision: NEW CLI subcommand modeled exactly on `cmd_detect_scenes`.**

| Property | Value |
|----------|-------|
| Where | NEW `agent/schedule_suggestion.py` + `cmd_schedule_suggest` |
| Input | `output/<slug>/paragraphs.json` + (optional) `output/<slug>/scenes.json` + (optional) `output/<slug>/silence_map.json` |
| Output | NEW sibling `output/<slug>/schedule_suggestion.json` |
| K5 | Tool emits **suggested segments**; Claude reads, edits, writes `schedule.json`. **Statically asserted via test:** `agent/schedule_suggestion.py` source MUST NOT reference filename `schedule.json` (only `schedule_suggestion.json`). Mirrors the existing K5 assertion in `cmd_detect_scenes` test. |
| Sidecar | `schedule_suggestion.json.params.json` (Phase 2 RES-01) |
| FPS-04 baseline | Suggestion ALWAYS includes a baseline `fps ≤ 0.1` segment spanning full duration (FPS-04 fallback path). Claude can override but shouldn't accidentally violate the strict-OR-fallback gate. |
| Lock | per-slug `.resume.lock` |
| D-29 | Additive |

**Schema:**

```json
{
  "version": 1,
  "video": "video.mp4",
  "suggested_segments": [
    {"start": 0.0, "end": 30.0, "fps": 0.1, "label": "intro", "rationale": "no scene cuts, low signal"},
    {"start": 30.0, "end": 360.0, "fps": 0.4, "label": "code-demo", "rationale": "8 scene cuts in 5 min + paragraph density high"},
    {"start": 360.0, "end": 600.0, "fps": 0.05, "label": "talkthrough", "rationale": "silence > 5s spans, mostly verbal"},
    {"start": 0.0, "end": 600.0, "fps": 0.05, "label": "fps-04-baseline", "rationale": "mandatory FPS-04 baseline"}
  ],
  "suggestion_meta": {
    "scene_cut_count": 14,
    "flagged_silences": 2,
    "uses_silence_map": true,
    "uses_scenes_json": true
  }
}
```

> **Note:** Suggestion segments may overlap (e.g. baseline + targeted). The actual `schedule.json` Claude writes must conform to non-overlap (D-05.3); Claude resolves overlaps when authoring the final.

---

### MISC-01: AV1 Warning Downgrade

**Problem:** `WARNING | Codec av1 detected; ...` is noisy false alarm.

**Decision:** Trivial. Change in `agent/sources/_common.py` (where `ffprobe_video` warns on codec) — `log.warning(...)` → `log.info(...)`. **Single-line change, no architecture impact.**

Other repeated noisy warnings (e.g., "vendor douyin config patched" — already INFO per `_log` pattern) audited in same plan.

---

### MISC-02: Video Queue Helper CLI

**Problem:** 17-video queue tracked in user memory file.

**Decision: NEW CLI subcommand suite + cross-slug state file with FileLock.**

| Property | Value |
|----------|-------|
| Where | NEW `agent/queue.py` + `cmd_queue_*` handlers in `tools.py` |
| State file | `~/.videoSummary/queue.json` (per CANDIDATES — keeps queue invariant across all repo clones / worktrees; if user has multi-worktree workflow, single source of truth) |
| Subcommands | `queue add <url> [--label X]` / `queue list` / `queue next` (peek+show next) / `queue done <slug>` / `queue skip <slug> [--reason X]` |
| Schema | `{"version": 1, "items": [{"url": "...", "slug": "...", "added_at": "...", "status": "queued|done|skipped", "label": "..."}]}` |
| Lock | NEW `~/.videoSummary/.queue.lock` via `agent/_lock.py:FileLock` |
| K5 | `queue next` doesn't auto-trigger `/summarize-video`; user manually invokes per CANDIDATES "Out of Scope row 4" |
| Cross-terminal | Two terminals doing `queue add` simultaneously → FileLock serializes; `queue list` reads under shared lock (or no-lock + tolerant retry on JSON decode error per `agent/io.py` precedent) |
| D-29 | New file in $HOME, doesn't touch any `output/<slug>/` |
| Git/IPython | `~/.videoSummary/` should appear in `.gitignore` of HOME (not the project) — document in CLAUDE.md `## Multi-terminal parallel` section |

**No new dependency.** stdlib + existing FileLock.

#### Build order

```
MISC-02 is fully independent — no upstream/downstream dependency on other v1.1 features.
Can land first as warm-up, since it exercises FileLock pattern (already shipped) on a new cross-host artifact.
```

---

## Component Responsibilities (v1.1 NEW only)

| Component | Responsibility | Model |
|-----------|----------------|-------|
| `agent/transcribe_lint.py` | Pure-function L1 detector: scan segs.json + meta.json → suspicious tokens | Mirrors `agent/scenes.py` (scene detector wrapper) |
| `agent/summary_lint.py` | Pure-function checker: parse summary.md → trace counts, format violations | New, no precedent — pure regex/parser |
| `agent/mode_signals.py` | Pure-function classifier: paragraphs → signal map + suggested mode | Mirrors `agent/silence.py` (signal emitter) |
| `agent/schedule_suggestion.py` | Pure-function planner: paragraphs + scenes + silence → suggested fps segments | Mirrors `agent/silence.py` |
| `agent/queue.py` | State-file CRUD on `~/.videoSummary/queue.json` w/ lock | Mirrors `agent/_lock.py` usage in `tools.py` |
| `agent/glossary.py` | Append-only writer to `output/_glossary.md` w/ lock + idempotency | New, lock pattern from `_lock.py` |
| (No code) Phase 7.5 verifier subagent | Spawned by parent Claude via `Task` tool | New phase in `/summarize-video` |
| (No code) `transcribe_warnings.json` consumer | Claude reads in Phase 2, writes corrections to `plan.md` | Prompt convention only |
| (No code) Inline trace tokens, `[?]` markers, TL;DR section, inline annotations | Format-spec extensions in `CLAUDE.md` Phase 6 | Prompt convention only |

---

## Architectural Patterns

### Pattern 1: K5 Read-Only Signal Emitter (REUSED from v1.0 Phase 4)

**What:** A new CLI command that reads existing artifacts, computes mechanical signals, writes a NEW sibling JSON, and **never** writes/edits the artifact Claude uses for decisions.

**When:** Any time a v1.1 feature wants to "help Claude decide X" without taking the decision.

**v1.0 precedent (`agent/tools.py:798-887`):**

```python
def cmd_detect_scenes(args):
    """K5 enforcement: this handler writes ONLY the scenes artifact and NEVER
    auto-promotes scene boundaries into segment plans. The locked acceptance
    test asserts this function's source contains no reference to the schedule
    artifact filename."""
    ...
    obj = {"version": 1, "video": ..., "scenes": scenes}
    write_json_atomic(out, obj)  # writes scenes.json — never schedule.json
```

**v1.1 reuses for:** TOOL-A `mode_signals`, TOOL-B `schedule_suggest`, CORR-01 L1 `transcribe_lint`, CORR-02 `summary_lint`.

**Static K5 test pattern** (locks the boundary in CI / unittest):

```python
def test_K5_mode_signals_does_not_touch_plan():
    src = Path("agent/mode_signals.py").read_text()
    assert "plan.md" not in src
    src2 = Path("agent/tools.py").read_text()
    fn = inspect.getsource(cmd_mode_signals)
    assert "plan.md" not in fn
```

### Pattern 2: Sidecar-Cached Artifact (REUSED from v1.0 Phase 2)

**What:** Each derived JSON gets a `<artifact>.json.params.json` sidecar storing input params hash + tool versions. Re-runs short-circuit when sidecar matches.

**Used by:** All new K5 tools that take a `--out` flag.

**Reference:** `agent/io.py:write_json_atomic(..., sidecar_params=current_sidecar)`, `cache_decision()`.

### Pattern 3: FileLock-Serialized Cross-Slug Artifact (REUSED from v1.0 Phase 6)

**What:** Cross-terminal mutation of a shared file (outside per-slug dir) goes through `agent/_lock.py:FileLock`.

**v1.1 uses for:** `output/_glossary.md`, `~/.videoSummary/queue.json`, `vendor/douyin_api/*/config.yaml` (already shipped).

**Race semantics for `_glossary.md`:**
- Two terminals: Terminal A appends "LoRA", Terminal B appends "ECS". FileLock serializes appends; final file has both.
- Same term twice: Idempotency check inside `cmd_glossary_append` — if H2 anchor `## <term>` AND link to `<slug>/summary.md` both exist, no-op.
- User hand-edits between runs: Append-only preserves edits.

### Pattern 4: Claude-Authored Artifact (REUSED from v1.0 Phase 5)

**What:** Some artifacts are written by Claude (`plan.md`, `schedule.json`, `chapters.json`), not by tools. They have a `.params.json` sidecar recording who-asked but no params hash.

**v1.1 uses for:** `REVIEW.md` (CORR-03 sub-agent's output) — written by the verifier subagent via `Write` tool.

### Pattern 5: Subagent-as-Phase (NEW)

**What:** A `/summarize-video` phase delegates a chunk of work to a `Task(subagent_type=general-purpose)` invocation with its own prompt + reading list.

**Why new:** v1.0's `/summarize-video` was monolithic — one Claude reads everything. v1.1 introduces the verifier as a separate Claude with fresh context to escape the writer's blind spots.

**Trade-offs:**
- (+) Fresh perspective, no anchoring to writer's prose
- (+) Token-isolated (verifier doesn't share writer's context)
- (-) Roughly doubles tokens vs single-pass
- (-) `Task` tool spawns sub-instance — single-process, no IPC needed beyond filesystem

**Loop control:** Hard cap of 1 rewrite per `/summarize-video` invocation; `state.jsonl` records `rewrite_cycle_completed`. 2nd invocation needed to retry.

---

## Data Flow (v1.1 NEW paths)

### CORR-01 + CORR-02 + CORR-03 Combined Flow

```
[Phase 1 download/transcribe/aggregate] → segs.json + paragraphs.json + meta.json
        ↓
[NEW] python -m agent.tools transcribe_lint <slug>
        → transcribe_warnings.json (sidecar cached)
        ↓
[Phase 2] Claude reads transcribe_warnings.json + meta.json
        → writes plan.md (with "已自动修正的术语" table for L2/L3)
        ↓
[Phase 3-5: extract_frames + frame reading + outline] (UNCHANGED)
        ↓
[Phase 6] Claude writes summary.md WITH inline traces [seg_xxx.jpg @ HH:MM:SS] + [?] markers + glossary terms + TL;DR (if duration warrants)
        ↓ (also calls)
[NEW] python -m agent.tools glossary append <slug> --term ... (per new term)
        → output/_glossary.md (lock-serialized)
        ↓
[NEW] python -m agent.tools summary_lint <slug>
        → summary_lint.json (claim count, traces, format violations)
        ↓
[NEW Phase 7.5] Claude spawns Task subagent (general-purpose)
        Subagent reads: summary.md + paragraphs.json + plan.md +
                        transcribe_warnings.json + summary_lint.json + frames sample
        Subagent writes: REVIEW.md
        ↓
[Parent Claude] reads REVIEW.md
        IF critical_count > 0 AND rewrite_cycle == 0:
            rewrite summary.md (max 1 cycle)
            re-run summary_lint.json
            log state.jsonl: rewrite_cycle_completed
        ↓
[Phase 8 cleanup_frames] (UNCHANGED)
```

### TOOL-A + TOOL-B Combined Flow

```
[Phase 1 download/transcribe/aggregate] → paragraphs.json
        ↓
[NEW, optional] python -m agent.tools mode_signals <slug>
        → mode_signals.json
        ↓
[NEW, optional] python -m agent.tools detect_scenes / detect_silence (UNCHANGED)
        → scenes.json + silence_map.json
        ↓
[NEW, optional] python -m agent.tools schedule_suggest <slug>
        → schedule_suggestion.json
        ↓
[Phase 2] Claude reads mode_signals.json (override own intuition or confirm) → plan.md
        ↓
[Phase 3] Claude reads schedule_suggestion.json (edits, removes overlaps, finalizes) → schedule.json
        ↓
[NEW Phase 3 invocation] python -m agent.tools extract_frames_batch (UNCHANGED — consumes Claude's final schedule.json)
```

### MISC-02 Queue Flow (out-of-band, single-user)

```
$ python -m agent.tools queue add https://www.bilibili.com/video/BV1xxx
  → ~/.videoSummary/queue.json (lock-serialized add)

$ python -m agent.tools queue next
  → prints next queued URL + slug

$ /summarize-video <url>  (manual user trigger; queue does NOT auto-invoke)
  → output/<slug>/ pipeline runs

$ python -m agent.tools queue done <slug>
  → marks status: done in queue.json
```

---

## Recommended Project Structure (v1.1)

```
agent/                                  # UNCHANGED layout, NEW files added
├── tools.py                            # MODIFIED: new cmd_* + new subparsers (~150 LOC delta)
├── _lock.py                            # UNCHANGED (Phase 6)
├── io.py                               # UNCHANGED
├── scheduler.py                        # UNCHANGED
├── state.py                            # UNCHANGED
├── transcribe_lint.py                  # NEW (CORR-01 L1)
├── summary_lint.py                     # NEW (CORR-02 helper)
├── mode_signals.py                     # NEW (TOOL-A)
├── schedule_suggestion.py              # NEW (TOOL-B)
├── queue.py                            # NEW (MISC-02)
├── glossary.py                         # NEW (TEACH-A.3)
├── sources/                            # UNCHANGED
└── ...

prompts/                                # NEW dir (optional; alternative is inline in CLAUDE.md)
└── summary-verifier.md                 # NEW: subagent prompt for CORR-03

output/                                 # UNCHANGED per-slug layout, NEW shared file at top
├── _glossary.md                        # NEW (TEACH-A.3 cross-slug accumulator)
├── _glossary.md.lock                   # NEW (FileLock sentinel; never deleted)
├── BV1xxx/                             # UNCHANGED structure, NEW siblings:
│   ├── transcribe_warnings.json        # NEW (CORR-01 L1)
│   ├── transcribe_warnings.json.params.json
│   ├── summary_lint.json               # NEW (CORR-02 helper)
│   ├── REVIEW.md                       # NEW (CORR-03 verifier output)
│   ├── mode_signals.json               # NEW (TOOL-A)
│   ├── mode_signals.json.params.json
│   ├── schedule_suggestion.json        # NEW (TOOL-B)
│   ├── schedule_suggestion.json.params.json
│   └── ... (all v1.0 artifacts unchanged)
└── ... (17+ archived slugs unchanged — D-29)

~/.videoSummary/                        # NEW (cross-host shared state)
├── queue.json                          # NEW (MISC-02)
└── .queue.lock                         # NEW (FileLock sentinel)

CLAUDE.md                               # MODIFIED: 5 new prompt extensions
                                        # - Phase 2: read transcribe_warnings.json + write plan.md "已自动修正的术语"
                                        # - Phase 4: prefer multimodal reading over ASR for warned terms
                                        # - Phase 6: inline traces + confidence + inline annotations + TL;DR
                                        # - Phase 7.5: spawn verifier Task subagent
                                        # - "## 多终端并行" subsection: queue + glossary lock semantics

.planning/                              # GSD planning docs (unchanged structure)
└── ... (v1.1 milestone phase docs land here)
```

### Structure Rationale

- **`agent/<feature>.py` per new feature:** mirrors v1.0 convention (`agent/scenes.py`, `agent/silence.py`, `agent/diarize.py`). Pure-function module + lazy import via `cmd_*` keeps `tools.py` slim.
- **`output/_glossary.md` at top of `output/`:** intentionally outside any slug dir to express cross-slug semantics. Alternative `~/.videoSummary/glossary.md` rejected because user wants glossary linked from per-slug summaries (relative paths simpler within `output/`).
- **`~/.videoSummary/queue.json`:** queue is **per-user**, not per-repo. Survives `git clone` of repo into a new worktree.
- **`prompts/summary-verifier.md` optional:** can be inline in CLAUDE.md for v1.1; promote to file if it grows beyond ~50 lines.

---

## D-29 Risk Audit (modified vs additive)

| Feature | New artifacts (additive) | Modified artifacts (D-29 risk) | Mitigation |
|---------|--------------------------|--------------------------------|------------|
| CORR-01 L1 | `transcribe_warnings.json` | NONE | — |
| CORR-01 L2/L3 | NONE (writes into plan.md only on opt-in) | `plan.md` (Claude-authored) | plan.md is per-run regenerable; not a v1.0-frozen artifact |
| CORR-02 prompt | NONE | `summary.md` (NEW writes only; old not retroactively rewritten) | Old summaries stay byte-equal; new summaries get traces |
| CORR-02 linter | `summary_lint.json` | NONE | — |
| CORR-03 verifier | `REVIEW.md` | `summary.md` (only if rewrite triggered, only on NEW summaries) | Old summaries never rewritten; rewrite only fires when CORR-02 traces opted-in |
| TEACH-A.1/2 | NONE | `summary.md` (NEW writes only) | Same as above |
| TEACH-A.3 | `output/_glossary.md` | NONE | top-level new file |
| TEACH-B | NONE | `summary.md` (NEW writes only) | Same as above |
| TOOL-A | `mode_signals.json` | NONE | — |
| TOOL-B | `schedule_suggestion.json` | NONE | — |
| MISC-01 | NONE | `agent/sources/_common.py` log level (1-line change) | Behavior change is log severity only; no artifact diff |
| MISC-02 | `~/.videoSummary/queue.json` | NONE | Lives outside repo |

**Aggregate D-29 risk: LOW.** Only `summary.md` shape evolves, and only for newly written summaries. v1.0 archived `summary.md` files are NEVER touched by v1.1 commands. Re-running `/summarize-video` on an archived slug WILL produce a v1.1-shape summary, but the old file stays on disk; user can compare and decide. Acceptance test: re-run `/summarize-video BV1HG9JBsEPK` → old `summary.md` overwritten by new shape (this is intended; user opts in by re-running).

> **Open question for ROADMAP:** should re-running `/summarize-video` on archived slugs preserve old `summary.md` to `summary.md.v10.bak`? This is a UX nit; defer to phase planning.

---

## Build-Order Dependency Graph

```
                          ┌──────────────────────────────┐
                          │ MISC-01 AV1 warning downgrade │ (independent, trivial)
                          └──────────────────────────────┘

                          ┌──────────────────────────────┐
                          │ MISC-02 queue helper CLI      │ (independent; warm-up FileLock)
                          └──────────────────────────────┘

                          ┌──────────────────────────────┐
                          │ TOOL-A mode_signals          │ (independent K5 emitter)
                          └──────────────────────────────┘
                          ┌──────────────────────────────┐
                          │ TOOL-B schedule_suggest      │ (independent K5 emitter; pairs w/ TOOL-A)
                          └──────────────────────────────┘

  ┌────────────────────────┐
  │ CORR-01a transcribe_lint│ ─────┐
  └────────────────────────┘       │
                                   ▼
                        ┌──────────────────────┐
                        │ CORR-01b CLAUDE.md  │ (Claude reads warnings → plan.md L2/L3)
                        │ Phase 2 prompt       │
                        └──────────┬───────────┘
                                   │
                                   ▼
            ┌─────────────────────────────────────────────┐
            │ TEACH-A.1/2/3 (inline annotation, header,   │ (parallel-able with CORR-02)
            │  glossary tool + lock)                       │
            └─────────────────────┬───────────────────────┘
                                  │
                                  │       ┌─────────────────────────────────────┐
                                  │       │ TEACH-B 5-min TL;DR (prompt only)   │
                                  │       └────────────┬────────────────────────┘
                                  │                    │
                                  └────────────────────┴────────────┐
                                                                    │
            ┌──────────────────────────────────────────────┐        │
            │ CORR-02 inline traces + confidence (prompt)  │        │
            │ + summary_lint CLI                            │        │
            └──────────────────┬───────────────────────────┘        │
                               │                                     │
                               │   ┌─────────────────────────────────┘
                               ▼   ▼
                  ┌─────────────────────────────────────┐
                  │ CORR-03 verifier subagent (Phase 7.5)│ (depends on lint output + format-spec)
                  │ + REVIEW.md + max-1 rewrite cycle    │
                  └─────────────────────────────────────┘
```

**Suggested phase carving (purely from dependency graph; ROADMAP will refine):**

1. **Phase A — Warm-up + independent tooling (no behavior change to summary.md):**
   - MISC-01 (AV1 log level)
   - MISC-02 (queue CLI)
   - TOOL-A + TOOL-B (mode_signals + schedule_suggest)
   - CORR-01a (transcribe_lint CLI)

2. **Phase B — Self-contained writing rules (CLAUDE.md changes; new summaries diverge):**
   - CORR-01b (L2/L3 prompts)
   - TEACH-A.1/2 (inline annotation + header sections)
   - TEACH-A.3 (glossary CLI + lock)
   - TEACH-B (TL;DR section)

3. **Phase C — Correctness automation (consumes Phase A+B):**
   - CORR-02 (inline traces prompt + summary_lint CLI)
   - CORR-03 (verifier subagent + REVIEW.md + rewrite control)

This carving respects:
- Phase A is **opt-in** (Claude has to invoke new CLIs); old re-runs unaffected
- Phase B changes new summaries' shape but doesn't enforce; verifier in Phase C makes shape mandatory by lint+rewrite
- Phase C cannot land before B (verifier checks B's traces / glossary / TL;DR)

---

## Anti-Patterns

### Anti-Pattern 1: Modifying `segs.json` to "fix" ASR errors

**What people would do:** L2 corrects "Lora→LoRA" by editing `segs.json` directly.
**Why wrong:** Breaks D-29 (`segs.json` is parameter-hashed; cache invalidates; `state.jsonl` event hash drifts). Old slugs would mass-regen on next CI.
**Do instead:** Record corrections in Claude-authored `plan.md` (a regenerable artifact); writing prose pulls from plan.md's correction table.

### Anti-Pattern 2: Tool auto-promotes signals into decisions

**What people would do:** `mode_signals.json` writes the chosen mode directly into `plan.md`. Or `schedule_suggest` writes `schedule.json` and skips Claude.
**Why wrong:** Violates K5. Tools cannot make judgment calls; wrong mode → entire summary wrong shape.
**Do instead:** Tools emit `*_signals.json` / `*_suggestion.json`; Claude reads, weighs, decides. Statically asserted in tests (no `plan.md` / `schedule.json` references in tool source).

### Anti-Pattern 3: Verifier as separate registered agent prematurely

**What people would do:** Create `.claude/agents/summary-verifier.md` with custom tool allowlist + system prompt.
**Why wrong:** Repo has no `.claude/agents/` infrastructure; building it for one verifier is over-investment. Iteration on verifier prompt is harder than editing inline CLAUDE.md.
**Do instead:** Use `Task(subagent_type=general-purpose)` with prompt inline in CLAUDE.md (or `prompts/summary-verifier.md` referenced from CLAUDE.md). Promote to registered agent in v1.2 if usage proves the harness is needed.

### Anti-Pattern 4: Glossary as full-rewrite-on-each-write

**What people would do:** `glossary append` reads entire `_glossary.md`, parses Markdown, rewrites with new term inserted.
**Why wrong:** Loses manual edits; lock contention spans the whole rewrite (slow); Markdown parsers are heavyweight.
**Do instead:** Append-only with idempotency check (search for `## <term>` H2 + slug-link before append). Lock held only during the append. User edits between runs preserved.

### Anti-Pattern 5: Verifier infinite loop

**What people would do:** Verifier finds Critical issues → rewrite → verifier re-runs → still finds Critical → rewrite → ...
**Why wrong:** Token budget explodes; bug in writer or verifier could spin indefinitely.
**Do instead:** Hard cap **1 rewrite per `/summarize-video` invocation**, recorded in `state.jsonl`. 2nd cycle requires user re-trigger. CORR-03 spec says "高严重度问题自动触发 summary 重写（最多 1 轮，避免无限循环）" — explicit lock.

### Anti-Pattern 6: Splitting summary.md into TL;DR + body files

**What people would do:** `summary.md` is the body; `summary_tldr.md` is the 5-min block.
**Why wrong:** Violates D-01 self-contained ("no assumed reading order"). Reader has to find two files.
**Do instead:** TL;DR is a mandatory H2 section at the top of `summary.md` for ≥30min videos.

---

## Integration Points

### External (no change from v1.0)

| Service | Integration | Notes |
|---------|-------------|-------|
| yt-dlp / vendor douyin / faster-whisper / ffmpeg / PySceneDetect / silero-vad / pyannote | Inherited from v1.0 | v1.1 adds NO external dependencies |

### Internal Boundaries (NEW)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `tools.py` ↔ `agent/transcribe_lint.py` | Function call from `cmd_transcribe_lint`; lazy import | Mirrors `agent/scenes.py` pattern |
| `tools.py` ↔ `agent/summary_lint.py` | Same | — |
| `tools.py` ↔ `agent/mode_signals.py` | Same | — |
| `tools.py` ↔ `agent/schedule_suggestion.py` | Same | — |
| `tools.py` ↔ `agent/queue.py` | Same | Plus FileLock on `~/.videoSummary/.queue.lock` |
| `tools.py` ↔ `agent/glossary.py` | Same | Plus FileLock on `output/_glossary.md.lock` |
| Parent Claude ↔ Verifier subagent | `Task` tool invocation; filesystem hand-off via `REVIEW.md` | NEW pattern |
| Phase 6 prompt ↔ Phase 7.5 prompt | Sequential within `/summarize-video` | NEW phase 7.5 between write + cleanup |
| Two terminals ↔ `_glossary.md` | FileLock serialization | per Phase 6 PARA-XX precedent |
| Two terminals ↔ `~/.videoSummary/queue.json` | FileLock serialization | per Phase 6 PARA-XX precedent |

### State Management (additive only)

| State location | Owner | Mutation discipline |
|----------------|-------|---------------------|
| `output/<slug>/state.jsonl` | All `cmd_*` (existing) + `cmd_transcribe_lint`, `cmd_summary_lint`, `cmd_mode_signals`, `cmd_schedule_suggest` (new) | Append-only events; new stages: `transcribe_lint`, `summary_lint`, `mode_signals`, `schedule_suggest`, `verifier_completed`, `rewrite_cycle_completed` |
| `output/<slug>/.resume.lock` | All write-stage `cmd_*` | New tools acquire same lock; per-slug serialization preserved |
| `output/_glossary.md.lock` | `cmd_glossary_append` (new) | NEW lock — cross-slug, top-level |
| `~/.videoSummary/.queue.lock` | `cmd_queue_*` (new) | NEW lock — cross-host, $HOME |

---

## Scaling Considerations

| Scale | v1.1 Impact | Adjustment |
|-------|-------------|------------|
| 1 video | All v1.1 features run sequentially within `/summarize-video`; verifier adds ~80% writing tokens | None — Claude Max budget covers |
| 1 user × 17 queued videos | Queue helper makes manual triggering ergonomic; glossary accumulates terms across the queue | None — sequential; no parallelism needed |
| 2 terminals (Phase 6 NTH-shipped path) | Glossary + queue locks serialize concurrent appends; per-slug locks unchanged | All new locks reuse `agent/_lock.py` — already cross-platform tested |
| Many terminals (3+) | Glossary append lock contention possible if all 3 finish summaries simultaneously; queue too | FileLock has timeout=0 fail-fast; CLAUDE.md "## 多终端并行" should document `--retry` flag if added in v1.2 |

**No DB. No cloud. No multi-tenancy.** Single-user tool stays single-user.

### Scaling Priorities (if real signal emerges)

1. **First bottleneck:** verifier token cost on long summaries (1000+ lines × 80% re-read). Mitigation: diff-based re-review on rewrite cycle (read only changed sections from `summary_lint.json`'s `claims_without_trace`). Defer to v1.2 once empirical data exists.
2. **Second bottleneck:** glossary scan on extremely large `_glossary.md` (>500 terms). Mitigation: split by first letter (e.g., `_glossary_A.md` … `_glossary_Z.md`). Defer indefinitely (single user unlikely to hit).

---

## Sources

- `D:/gxy_code/videoSummary/.planning/PROJECT.md` (v1.1 milestone goals + locked design decisions D-01/02/03)
- `D:/gxy_code/videoSummary/.planning/v1.1-CANDIDATES.md` (8 candidate requirements + their must-haves)
- `D:/gxy_code/videoSummary/.planning/codebase/ARCHITECTURE.md` (v1.0 system as ground truth)
- `D:/gxy_code/videoSummary/.planning/codebase/STRUCTURE.md` (v1.0 file layout)
- `D:/gxy_code/videoSummary/.planning/codebase/INTEGRATIONS.md` (v1.0 external integrations baseline)
- `D:/gxy_code/videoSummary/CLAUDE.md` (`/summarize-video` 8 phases, format-spec lock, 4-mode skeletons, multi-terminal parallel section)
- `D:/gxy_code/videoSummary/agent/tools.py` (v1.0 CLI surface — lines 798-887 for K5 detect_scenes/silence precedent; lines 1214-1360 for argparse + dispatch pattern; lines 502-609 for whisper_repetition_guard precedent for warning-artifact emit)
- `D:/gxy_code/videoSummary/agent/sources/__init__.py` (Source Protocol + SOURCES list pattern with load-time invariants — model for any future cross-feature registry)
- `D:/gxy_code/videoSummary/agent/scheduler.py` (Schedule + Segment dataclass + 5 strict validations — model for new schema-validated artifacts)
- `D:/gxy_code/videoSummary/agent/_lock.py` (FileLock cross-platform stdlib advisory lock — required for `_glossary.md` and `queue.json`)
- `D:/gxy_code/videoSummary/agent/io.py:106` (`write_json_atomic` + sidecar pattern — required for all new artifacts with cacheable params)
- `D:/gxy_code/videoSummary/output/BV1HG9JBsEPK/summary.md` (v1.0 reference summary — format-spec invariants validated against)

---

*v1.1 architecture research: 2026-05-03 — for v1.1-summary-quality milestone roadmap.*
