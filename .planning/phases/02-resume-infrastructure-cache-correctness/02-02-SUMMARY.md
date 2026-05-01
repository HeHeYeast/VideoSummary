---
phase: 02-resume-infrastructure-cache-correctness
plan: 02
subsystem: agent.state / agent.tools
tags: [state-log, event-sourcing, jsonl, cache-correctness, infrastructure]
dependency_graph:
  requires:
    - "agent/io.py (Phase 2-01: write_json_atomic, read_sidecar, cache_decision, now_iso)"
    - "agent/tools.py (Phase 2-01: cmd_download/cmd_transcribe/cmd_aggregate already use _build_sidecar + write_json_atomic)"
  provides:
    - "agent.state.params_hash(sidecar) -> 16-hex sha256 prefix (Phase 2-03 doctor.last_state column reads this via read_events+derived_state)"
    - "agent.state.append_event(state_log, *, stage, status, params_hash, details) -> JSON Lines append, best-effort"
    - "agent.state.read_events(state_log) -> (events, status_str) where status in {ok, missing, corrupt}; session-cached suppression via _CORRUPT_PATHS"
    - "agent.state.derived_state(events) -> {stage: {status, last_completed_at, params_hash}} pure reducer (D-14 stage-level only on day 1; Phase 4 will add segment fields additively)"
    - "agent.tools._emit_event(out_dir, stage, status, *, sidecar, details) -> wraps append_event with params_hash computation; best-effort wrapper used by 5 cmd_*"
  affects:
    - "agent/tools.py:cmd_download/cmd_transcribe/cmd_aggregate/cmd_extract_frames/cmd_cleanup_frames (now emit started/completed/failed events around their work; happy-path behavior unchanged from 02-01)"
tech_stack:
  added:
    - "JSON Lines append-only event log at output/<slug>/state.jsonl (D-12)"
    - "hashlib.sha256 + sort_keys=True deterministic 16-hex params_hash (D-13)"
    - "module-level set[str] for process-lifetime corruption suppression (RESEARCH Pitfall 2)"
    - "try/finally event emission wrapper pattern in 5 cmd_* (D-13 stage taxonomy)"
  patterns:
    - "append-only JSON Lines (one event per line, newline-terminated)"
    - "open(p, 'a', encoding='utf-8') + flush (no os.fsync; risk model is locked-file not power-loss)"
    - "Pure reducer: events -> dict[stage, StageState] (no I/O, callable infinitely on same input)"
    - "Stage-level grain only on day 1 (D-14): one started + one completed per cmd_*; per-segment events deferred to Phase 4 with extract_frames_batch"
    - "Best-effort emit: OSError on append -> log.warning, never raises (event log is diagnostic, not blocking)"
key_files:
  created:
    - "agent/state.py (166 lines; 4 public helpers + 1 module-level _CORRUPT_PATHS set)"
  modified:
    - "agent/tools.py (363 -> 425 lines; +1 import + _emit_event helper + 5 cmd_* wrappers; 15 stage-event call sites)"
metrics:
  duration_seconds: 1080
  duration_minutes: 18
  completed_at: 2026-05-01T00:00:00Z
  tasks_completed: 3
  files_modified: 1
  files_created: 1
  commits: 2
---

# Phase 2 Plan 02: state.jsonl Event Log + Pure Reducer Summary

Added the append-only event log (`output/<slug>/state.jsonl`) and pure
`derived_state(events)` reducer that gives every Phase 2+ stage a recoverable,
queryable execution history. All 5 `cmd_*` handlers (download, transcribe,
aggregate, extract_frames, cleanup_frames) now emit `started`/`completed`/
`failed` events around their work via try/finally. When state.jsonl is missing
or corrupt, behavior degrades cleanly to 02-01's file-existence cache (zero
archive regression).

## What Changed

### agent/state.py (NEW, 166 lines)

| Helper | Purpose | Lock spec |
|---|---|---|
| `params_hash(sidecar)` | sha256-prefix-16-hex over (cli, func, tools); sort_keys=True; captured_at/schema_version excluded | D-13 |
| `append_event(state_log, *, stage, status, params_hash="", details=None)` | JSON Lines append; mkdir parents; OSError -> log.warning, never raises | D-12, RES-05 |
| `read_events(state_log) -> (events, status)` | status in {"ok", "missing", "corrupt"}; on corruption, marks path in `_CORRUPT_PATHS`, emits ONE warning, returns events parsed BEFORE bad line | D-03, RES-06, RESEARCH Pitfall 2 |
| `derived_state(events) -> dict[stage, StageState]` | Pure reducer: status (most-recent), last_completed_at (most-recent completed event ts), params_hash (most-recent non-empty); no I/O, no logging | D-14 |
| `_CORRUPT_PATHS: set[str]` (module-level) | Process-lifetime suppression set; once a path is corrupt, no further reads, no further warnings until process restart | RESEARCH Pitfall 2 |

Locked literals:
- Warning fragment: `state.jsonl corrupt at %s; degrading to file-existence cache for the rest of this session (no auto-repair)`
- Hash truncation: `hashlib.sha256(...).hexdigest()[:16]`
- JSON serialization: `ensure_ascii=False, sort_keys=True, separators=(",", ":")` (compact form for stable hashing)

### agent/tools.py (363 -> 425 lines)

Added at module top after the existing 02-01 import block:
```python
from agent.state import append_event, params_hash
```

New helper next to `_build_sidecar`:
```python
def _emit_event(out_dir: Path, stage: str, status: str,
                *, sidecar: dict | None = None, details: dict | None = None) -> None:
```
Computes `params_hash(sidecar)` (or `""` if no sidecar) and delegates to
`append_event(out_dir / "state.jsonl", ...)`. Best-effort: append failures
log a warning rather than propagating.

5 cmd_* handlers wrapped:

| Handler | state_dir | Sidecar passed? | Details captured |
|---|---|---|---|
| cmd_download | `Path(args.out)` | `None` on started, `sidecar` on completed | started: `{url[:120]}`; completed: `{platform}`; failed: `{error_type, error[:200]}` |
| cmd_transcribe | `Path(args.out)` | `current_sidecar` always | completed: `{segs_count, decision}`; failed: error info |
| cmd_aggregate | `Path(args.out).parent` (state.jsonl lives next to paragraphs.json) | `current_sidecar` always | completed: `{paragraphs_count, decision}`; failed: error info |
| cmd_extract_frames | `Path(args.out).parent` (frames/ is subdir) | `None` (frames/ has no sidecar per D-08) | started/completed: `{fps, start, end}`; completed adds `frames_count`; failed adds error info |
| cmd_cleanup_frames | `Path(args.dir).parent` | `None` (delete-only stage) | started: `{keep_count}`; completed: `{removed, kept}`; failed: error info |

Untouched (out of D-13 stage taxonomy or out of phase scope):
- `cmd_list_frames` — read-only inspection, no event needed
- `cmd_classify_frame`, `cmd_ocr_frame` — VE-API fallbacks, explicitly excluded by CONTEXT canonical_refs

Total event-emission call sites: 15 (5 commands x 3 statuses). Total
`_emit_event` references in file: 16 (1 helper def + 15 emissions).
`except Exception as e:` handlers: 5 (one per wrapped command).

## Verification (Task 3 Stages A-E)

### Stage A — Pure reducer (no I/O, no side effects) — PASS

```
Stage A: derived_state pure-reducer OK
```

Confirmed: input `[{stage:'transcribe', status:'started/completed', ...}, {stage:'aggregate', status:'failed', ...}]` returns the locked shape with `last_completed_at=None` for the never-completed `aggregate` stage.

### Stage B — Append round-trip in tempdir — PASS

```
Stage B: append+read round-trip OK
```

2 events written, 2 events read back; status `ok`; details dict preserved; each line is valid JSON; lines newline-terminated.

### Stage C — Corruption tolerance + session suppression — PASS

```
Stage C: corruption suppression OK (warnings: 1, events before corruption: 1)
```

Sequence: append 1 valid event -> append corrupt line `{not valid json` -> append another valid event. First `read_events` returns `(events_before_corrupt, "corrupt")` with exactly ONE valid event (D-03 stops at first corruption, never skips past). Second `read_events` returns `([], "corrupt")` with NO additional warning (RESEARCH Pitfall 2 session suppression via module-level `_CORRUPT_PATHS` set). Total warnings emitted: exactly 1. Append still works after corruption (RES-06: degrade reads but keep appending).

### Stage D — Missing state.jsonl degradation — PASS

```
Stage D: missing state.jsonl degrades to empty events / empty state OK
```

`read_events(non_existent_path)` returns `([], "missing")` without raising. `derived_state([])` returns `{}`.

### Stage E — Archive non-regression — PASS (with documented caveat)

#### E.1 — Archive loaders + state=missing assertion

```
SKIP BV132wizyEEB: only baseline at tests/regression/, no output/ copy on this worktree
BV1C9QCBdE1U: state=missing, segs/paras/meta load OK
SKIP douyin_trae_ai: only baseline at tests/regression/, no output/ copy on this worktree
```

The fresh worktree has only `output/BV1C9QCBdE1U/` populated (same as 02-01's
verification context). For the present baseline:
- `read_events(output/BV1C9QCBdE1U/state.jsonl)` returns `([], "missing")` —
  archive correctly does NOT yet have a state.jsonl file. Expected.
- `load_segs / load_paragraphs / load_meta` continue to function untouched.
- Archive mtimes verified unchanged: `meta.json / segs.json / paragraphs.json`
  still report `2026-05-01T08:00:00Z` (pre-Phase-2-02 timestamp).

The 2 SKIP slugs live exclusively under `tests/regression/<slug>/` per Phase 1
D-08; no `output/` copy exists in this worktree. Same situation as 02-01 SUMMARY
documented.

#### E.2 — Eyeball diff on summary.md

```
BV132wizyEEB: SKIP (baseline or output missing)
BV1C9QCBdE1U: DIFF FOUND (regression!)
douyin_trae_ai: SKIP (baseline or output missing)
```

The DIFF FOUND for BV1C9QCBdE1U was investigated and is **NOT a content
regression caused by Phase 2-02**. It is purely CRLF vs LF line endings,
identical to the caveat documented in 02-01 SUMMARY (output/ checked out with
core.autocrlf=true, tests/regression/ created via cp preserving LF). Verified:

```bash
diff <(tr -d '\r' < tests/regression/BV1C9QCBdE1U/summary.md) \
     <(tr -d '\r' < output/BV1C9QCBdE1U/summary.md)
# (empty output) -> byte-identical after CRLF normalization
```

Phase 1 D-09 acceptance ("no surprise drift") holds: zero content drift, only
Windows checkout line-ending normalization that pre-dates Phase 2.

### Overall verification block — PASS

All 6 commands from `<verification>` exit 0:

```
state ok
tools ok
hash ok
reducer ok
cli ok
events count >=15 ok
```

(`grep -c '_emit_event' agent/tools.py` = 16, well above the >=15 threshold.)

## Deviations from Plan

### None — plan executed exactly as written.

The verbatim implementation in `<action>` for Task 1 was copied with cosmetic
formatting only (consistent ASCII em-dash usage in docstrings). Task 2's 5 cmd_*
wrappers follow the action-block templates verbatim — same try/finally shape,
same details payload keys, same state_dir derivations.

One minor structural improvement applied transparently: in `cmd_transcribe`, the
`extract_audio` call was moved INSIDE the `try:` block (originally outside the
try in 02-01 but the plan's pseudo-code put it inside). Rationale: if ffmpeg's
audio extract crashes, we want the `failed` event to record it. This matches
the plan's literal pseudo-code (`try: if not audio.exists(): extract_audio(...)`).

### Tool-environment caveat (informational, not a code deviation)

The runtime PreToolUse READ-BEFORE-EDIT hook fired after each Edit tool call
even though the file had been Read earlier in the session. Each Edit succeeded
on the first attempt — the hook's reminder appears to be advisory rather than
blocking. No fallback to bash heredoc was needed; Write/Edit tools worked
normally. This contrasts with 02-01's experience where the hook actually
rejected writes; the difference may be a runtime-version change between waves.

### Worktree base reset (mechanical)

The worktree branch was originally based on `08a79f4` (main pre-Phase-2-01)
instead of the expected base `e54cabc` (post-Phase-2-01). Per the
`<worktree_branch_check>` protocol, I ran `git reset --hard e54cabc` on the
clean working tree to bring Wave 1's `agent/io.py` extensions and
`agent/tools.py` rewiring into scope. No code changes were made by this reset.

## Auth Gates

None.

## Known Stubs

None. All 5 cmd_* event-emission paths are wired to real code paths; no UI
components, no placeholder data sources, no TODO markers. The reducer's
`StageState` shape is the canonical day-1 output; Phase 4 will extend it
additively (no schema bump).

## Threat Flags

None — Phase 2-02 is pure local infrastructure (no network, no untrusted input,
no schema changes at trust boundaries). Threat register T-02-02 disposition
`accept` from the plan stands. The corruption-tolerant reader does NOT
auto-repair / truncate / delete (D-03 explicit), so an attacker who somehow
corrupted state.jsonl could not exploit a self-modifying recovery path. The
reducer is pure (no I/O) so no injection surface. ¥0 hard constraint preserved
(stdlib only — `json`, `hashlib`, `pathlib`, `logging` + reuse of `agent.io.now_iso`).

## Commit Trail

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 14ca4d9 | feat(02-02): add agent/state.py event log + pure derived_state reducer |
| 2 | b468048 | feat(02-02): wire 5 cmd_* with started/completed/failed events |
| 3 | (verification only) | Task 3 Stages A-E executed; no code changes |

## Self-Check

### Self-Check: PASSED

- **Created files exist:**
  - `agent/state.py` (166 lines) — FOUND
  - `.planning/phases/02-resume-infrastructure-cache-correctness/02-02-SUMMARY.md` — FOUND
- **Modified files exist:**
  - `agent/tools.py` (425 lines, was 363 in 02-01) — FOUND
- **Commits exist in history:**
  - `14ca4d9` (Task 1: agent/state.py) — FOUND
  - `b468048` (Task 2: 5 cmd_* event wrappers) — FOUND
- **Import smoke tests:**
  - All 5 public symbols importable from `agent.state`: `params_hash`, `append_event`, `read_events`, `derived_state`, `_CORRUPT_PATHS` — OK
  - `agent.tools._emit_event` callable — OK
  - `agent.tools.cmd_transcribe` callable — OK
- **Phase 2-01 contracts preserved:**
  - `agent/io.py` untouched (still 293 lines from 02-01)
  - `agent/asr_v2.py._DEFAULTS` and `src/asr.py._VAD_DEFAULTS` untouched
  - All 02-01 cache-decision behavior preserved (Stage E archive load test)
- **CLI integrity:**
  - `python -m agent.tools` prints help with "VideoSummary" prefix — OK
  - `python -m agent.tools transcribe --help` shows `--force` flag — OK
- **Stage event taxonomy (D-13):**
  - 5 of 6 D-13 stages emitted: `download`, `transcribe`, `aggregate`, `extract_frames`, `cleanup_frames`
  - `extract_frames_batch` reserved for Phase 4 (not yet a CLI command); `doctor` reserved for Phase 2-03
