# Phase 07: Warm-up + K5 emitters + D-29 foundation - Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped per smart_discuss infra detection rule + user's `feedback_phase_priority.md` memory)

<domain>
## Phase Boundary

Establish v1.1 opt-in foundation (D-29 byte-equal preserved on 17 archives), ship 4 new K5 read-only signal emitters that Claude can consult but never auto-promote, demote AV1 noise, and add a queue helper. Zero behavior change to any newly written `summary.md`.

This phase is the **gating infrastructure** for v1.1 — Phases 08 and 09 cannot ship safely without:
- `.v11_features.json` opt-in marker pattern (controls all v1.1 paths)
- 17-archive byte-equal replay test (D-29 invariant gate)
- `.token_budget.json` baseline measurement (Phase 09 token-cap reference)
- 4 K5 emitters (Phase 08 prompts and Phase 09 verifier consume their JSON outputs)

8 requirements: PRE-V11-01, PRE-V11-02, PRE-V11-03, MISC-01, MISC-02, TOOL-A, TOOL-B, CORR-01a.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation choices at Claude's discretion — pure infrastructure phase per `feedback_phase_priority.md` memory ("infra phases Claude 自决；只在 user-visible / 影响文档质量的 phase 拉讨论"). Use ROADMAP.md Phase 07 success criteria + `.planning/research/SUMMARY.md` 3-phase consensus + v1.0 codebase patterns as ground truth:

- Reuse v1.0 patterns wherever possible: `agent/_lock.py` FileLock for new lock domains; `params.json` sidecar for new artifacts; `state.jsonl` events for new milestones; `cmd_detect_scenes` K5 source-grep test as static-assert template
- `pypinyin>=0.55.0` is the **only** new pip dep — pure-Python ~2MB, no native deps; add to `requirements.txt`
- 4 K5 emitters: `transcribe_lint` (CORR-01a) + `mode_signals` (TOOL-A) + `schedule_suggest` (TOOL-B) + `glossary_audit` (read-only audit, future TEACH-A3 helper)
- Replay test (PRE-V11-02) is one-shot script in `scripts/replay_v10_archives.py`; not a CI hook
- Token-budget baseline (PRE-V11-03) measures 3 representative v1.0 archives (one per common mode); writes per-archive `.token_budget.json` for Phase 09 reference
- pypinyin false-positive rate: ship opt-in initially; mid-phase pivot to default-on if rate < 5% on 3 test videos

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets (from `.planning/codebase/` v1.0 ground truth)
- `agent/_lock.py` — cross-platform FileLock (msvcrt + fcntl) with stale-PID takeover; reuse for `~/.videoSummary/.queue.lock`
- `agent/io.py` — schema-tolerant atomic JSON I/O (tempfile + os.replace + 3×0.5s PermissionError retry); reuse for new sidecars
- `agent/scheduler.py` — Schedule + Segment dataclasses + 5 strict validations + ScheduleValidationError; pattern for `mode_signals.json` / `schedule_suggestion.json` schema dataclasses
- `agent/sources/` registry pattern — most-specific-first matching; reference for any new pluggable component
- `cmd_detect_scenes` / `cmd_detect_silence` (in `agent/tools.py`) — K5-bounded read-only CLI pattern; copy structure for 4 new K5 emitters
- `state.jsonl` event log + `derived_state` reducer — extend with new event types

### Established Patterns
- 5-CLI dispatch in `agent/tools.py` via argparse subcommands
- `output/<slug>/<artifact>.params.json` sidecars for parameter-aware caching (cli/func/system 3-segment hash)
- `[<slug>] <cmd>: ` log prefix for parallel-terminal stdout demultiplexing
- All file I/O explicit `encoding="utf-8"` (Phase 1 PRE-04 audit pass)

### Integration Points
- `agent/tools.py` — add 4 new subparsers (transcribe_lint / mode_signals / schedule_suggest / glossary_audit / queue) + AV1 log demote
- `agent/_lock.py` — extend with named lock helpers (or reuse FileLock with new path)
- `requirements.txt` — add `pypinyin>=0.55.0`
- `scripts/` (NEW directory) — `replay_v10_archives.py` one-shot test
- `output/<slug>/` — new sibling artifacts: `transcribe_warnings.json`, `mode_signals.json`, `schedule_suggestion.json`, `.v11_features.json`, `.token_budget.json`
- `~/.videoSummary/` (NEW directory in $HOME) — `queue.json` + `.queue.lock`
- CLAUDE.md — add Phase 07 section ("v1.1 opt-in marker + 4 K5 emitters" usage docs)

</code_context>

<specifics>
## Specific Ideas

- **K5 source-grep static assertion template**: `git grep -L "schedule.json\|plan.md\|summary.md" agent/tools.py | grep -E "cmd_(transcribe_lint|mode_signals|schedule_suggest|glossary_audit)"` should return 0 (each new emitter must NOT reference Claude's decision artifacts in source). Failing this assertion is a phase-blocking error.
- **17-archive replay schema**: script iterates `output/*/` looking for archived slugs (those without `.v11_features.json` marker), re-runs `transcribe → aggregate → write summary` from cached inputs (whisper rerun avoided via segs.json cache hit), and diffs each `summary.md` / `segs.json` / `paragraphs.json` / `meta.json` byte-by-byte against committed v1.0 baseline. Any single byte diff prints loud failure + path.
- **Token-budget representative archive selection**: 1 replicate-guide (e.g., `BV132wizyEEB`) + 1 interview-distillation (e.g., `douyin_karpathy_llm_wiki`) + 1 extension-applications (e.g., `douyin_claude_code_hooks`). Selection criteria: each must have committed `summary.md` + complete `segs.json` / `paragraphs.json` / `frames/`.
- **`.v11_features.json` schema**: `{"version": 1, "features_enabled": ["transcribe_lint", "mode_signals", "schedule_suggest", "trace_tokens", "self_contained_header", "glossary", "tldr", "verifier"], "marker_set_at": "<ISO>"}`. Phase 07 ships emitter feature flags only; Phase 08/09 add their own flags as they ship.
- **Queue schema**: `{"version": 1, "items": [{"slug": "BVxxx", "url": "https://...", "added_at": "<ISO>", "status": "pending|in_progress|done", "in_progress_pid": <int|null>}]}`. `queue next` finds first `status=pending`, sets `status=in_progress` + `in_progress_pid=<this-pid>`, returns slug. `queue done <slug>` sets `status=done`.

</specifics>

<deferred>
## Deferred Ideas

- **L0 Whisper decode-time `initial_prompt` injection** — 17% relative WER reduction in Chinese ASR with mixed-tech transcripts; per research SUMMARY.md "Defer (v2+)". Out of scope for Phase 07.
- **Token-budget CI integration** — Phase 07 only measures + writes `.token_budget.json`; future v1.2 may add CI gate. Out of scope.
- **pypinyin default-on promotion** — depends on Phase 07 mid-phase false-positive measurement; if measurement defers, ship opt-in only.
- **`summary.md.v10.bak` auto-backup on re-run** — re-run UX nicety; per research SUMMARY.md "Defer (v2+)". Out of scope.

</deferred>
