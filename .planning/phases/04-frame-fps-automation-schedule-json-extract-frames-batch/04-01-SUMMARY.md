---
phase: 04-frame-fps-automation-schedule-json-extract-frames-batch
plan: 01
subsystem: frame-extraction
tags: [scheduler, ffmpeg, validation, dataclass, state-machine, segment-resume, fps-automation]

# Dependency graph
requires:
  - phase: 02-resume-infrastructure-cache-correctness
    provides: append_event / read_events / derived_state / params_hash / write_json_atomic
  - phase: 03-source-refactor-new-sources-youtube-local-mp4-generic
    provides: ffprobe_video duration probe / -vsync vfr argv pattern in cmd_extract_frames
provides:
  - "agent/scheduler.py: Schedule + Segment dataclasses + ScheduleValidationError + from_json/to_json/validate (5 D-05 checks + FPS-04 silence-coverage strict-OR-fallback)"
  - "agent/state.py: derived_segment_state additive helper (Phase 2 D-14 segment-level resume reducer 落地)"
  - "agent/tools.py: cmd_extract_frames_batch CLI with --schedule/--out/--force, segment-level state.jsonl events, resume-aware via derived_segment_state"
  - "Locked schedule.json shape (D-01): version, video, default_scale, default_quality, segments[start,end,fps|skip,label]"
  - "Locked FPS-04 fallback warning string for silence_map.json absence"
affects: [04-02-detect-scenes-detect-silence, 05-teaching-plan-md-multipass-refine]

# Tech tracking
tech-stack:
  added: []  # No new runtime deps; reuses ffprobe / ffmpeg / agent.io / agent.state from Phase 2/3
  patterns:
    - "Strict-OR-fallback validation gate (FPS-04): tight set-theoretic interval coverage (silence_map present) OR baseline-pass requirement (silence_map absent) — D-07/D-08"
    - "Boolean identity check for schema enforcement: type(d['skip']) is bool rejects 1/'true'/etc at parse time (D-05.4)"
    - "Set-theoretic interval coverage helper (_interval_covered): sweep cursor over sorted overlapping intervals — pure function, separately testable"
    - "Segment-level resume reducer: latest-status-wins per segment_index (failed-after-completed re-attempts; completed-after-failed re-includes)"
    - "K5 boundary verified by static-source assertion: cmd_extract_frames_batch source contains neither 'agent.scenes' nor 'scenes.json' (anti-auto-promotion enforced in tests)"

key-files:
  created:
    - agent/scheduler.py
    - tests/test_scheduler.py
    - tests/test_state.py
    - tests/test_extract_frames_batch.py
  modified:
    - agent/state.py
    - agent/tools.py
    - .gitignore

key-decisions:
  - "Used stdlib unittest (not pytest) — pytest is not in project deps; Phase 2 RESEARCH established the stdlib-only test precedent"
  - "Built ffmpeg argv inline inside cmd_extract_frames_batch (per CONTEXT D-10 + Discretion line 119) rather than refactoring a shared helper — keeps cmd_extract_frames body untouched (FPS-07)"
  - "Boolean identity check on `skip` happens at parse time in _load_segment, then re-checked in validate() for paranoia (defense in depth — type wrong inputs cannot smuggle past dataclass construction)"
  - "tests/_tmp_batch/ added to .gitignore as ASCII-safe per-test tmpdir; needed because zh-CN Windows %TEMP% (e.g., C:/Users/管啸野/AppData/Local/Temp) trips _validate_out_path's CJK rejection during test setUp"
  - "Schedule.to_json drops fps=None / skip=False / label=None to preserve symmetric input/output shape — supports forward-use roundtrip (test 1)"

patterns-established:
  - "Schedule dataclass with explicit .validate(duration_s=, silence_map=): no __post_init__ — caller controls timing"
  - "ScheduleValidationError subclasses ValueError with segment-index + field-name in message (D-06)"
  - "Resume reducer pattern: derived_segment_state(events, *, stage='extract_frames_batch') -> set[int]"
  - "K5 enforcement via inspect.getsource + substring assertion (test_10_no_scenes_module_in_source / test_10b / test_10c)"
  - "FPS-07 verification: git diff of agent/tools.py shows zero `^-` lines for cmd_extract_frames body (only additive insertions)"

requirements-completed: [FPS-01, FPS-02, FPS-03, FPS-04, FPS-07]

# Metrics
duration: ~25min
completed: 2026-05-01
---

# Phase 04 Plan 01: schedule.json + extract_frames_batch CLI Summary

**Schedule + Segment dataclasses with strict 5-check validation, FPS-04 silence-coverage strict-OR-fallback gate, and segment-level resume-aware extract_frames_batch CLI — all reusing Phase 2/3 infrastructure with K5 (anti-auto-promotion) boundary statically asserted.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-01T03:04:00Z (approx, plan execution start)
- **Completed:** 2026-05-01T03:29:41Z
- **Tasks:** 3 / 3
- **Files modified:** 7 (3 created, 3 modified, 1 .gitignore tweak)
- **Tests:** 37 unit tests, all passing via stdlib unittest

## Accomplishments

- **`agent/scheduler.py`** — Schedule + Segment dataclasses, ScheduleValidationError, from_json/to_json, validate() implementing all 5 D-05 mandatory checks (version, full-duration coverage ±2s, no overlap/gap strict equality, fps XOR skip with bool identity, no unknown keys) plus FPS-04 silence-coverage strict-OR-fallback gate (D-07/D-08). `_interval_covered` set-theoretic helper (PITFALLS P3 tight interpretation).
- **`agent/state.py`** — `derived_segment_state(events, *, stage)` additive helper (Phase 2 D-14 落地). Latest-status-per-segment-index reducer; failed-after-completed semantics correct. Existing API untouched.
- **`agent/tools.py`** — `cmd_extract_frames_batch` handler reading schedule.json, ffprobing for duration, optionally reading silence_map.json (validation input only — never auto-promotes), strict-validating, then iterating segments with segment-level state.jsonl events. `--force` bypasses resume; per-segment ffmpeg failure raises RuntimeError and stops subsequent segments. Filename grammar `seg_<int(start):04d>_%06d.jpg` and `-vsync vfr` argv shape preserved (matches `cmd_extract_frames`).
- **K5 boundary asserted** via static-source check in tests: cmd_extract_frames_batch source contains neither `'agent.scenes'` nor `'scenes.json'` substring. silence_map.json IS read (allowed validation input).
- **FPS-07 verified:** `git diff HEAD -- agent/tools.py` shows zero `^-` deletions for cmd_extract_frames body — only additive insertions (new function + argparse subparser + cmds dict entry).

## Task Commits

Each task committed atomically (all `--no-verify`, executed on the worktree branch):

1. **Task 1: agent/scheduler.py + Schedule/Segment dataclasses + 5 D-05 checks + FPS-04 silence coverage** — `488850c` (feat)
2. **Task 2: derived_segment_state additive helper to agent/state.py** — `932a052` (feat)
3. **Task 3: cmd_extract_frames_batch handler + argparse + cmds dict + K5 boundary** — `9140793` (feat)

## Files Created/Modified

- `agent/scheduler.py` *(created)* — Schedule + Segment dataclasses, ScheduleValidationError, validate() with 5 mandatory checks + FPS-04 silence-coverage gate, _interval_covered helper, _load_segment parser with bool-identity skip check, _segment_to_dict serializer.
- `agent/state.py` *(modified, additive only)* — Added `derived_segment_state(events, *, stage)` reducer at end of module; existing functions (append_event, read_events, derived_state, params_hash, _CORRUPT_PATHS) untouched.
- `agent/tools.py` *(modified, additive only)* — Added `cmd_extract_frames_batch` handler after `cmd_extract_frames`; added argparse subparser block; added cmds-dict entry. `cmd_extract_frames` body completely unchanged (FPS-07).
- `tests/test_scheduler.py` *(created)* — 18 unit tests covering parse/roundtrip, all 5 D-05 mandatory checks (Tests 2-9), all 4 FPS-04 silence-coverage paths (Tests 10-13), and direct `_interval_covered` helper smoke checks.
- `tests/test_state.py` *(created)* — 7 tests covering derived_segment_state edge cases (basic completed, failed-after-completed drops, completed-after-failed re-includes, started-only, different stage filtered, missing details ignored) + regression check that derived_state shape is unchanged.
- `tests/test_extract_frames_batch.py` *(created)* — 12 tests covering validation gate, resume skip, --force bypass, skip-segment no-ffmpeg, failure stops subsequent, event details shape, filename grammar, CJK rejection, function callable, K5 boundary (3 sub-checks).
- `.gitignore` *(modified)* — Added `tests/_tmp_batch/` (per-test ASCII-safe scratch dir to work around zh-CN Windows %TEMP% CJK-username path tripping `_validate_out_path`).

## Decisions Made

- **stdlib unittest over pytest** — pytest is not in project deps; Phase 2 RESEARCH established the stdlib-only test precedent. Tests are runnable via `python -m unittest tests.test_scheduler tests.test_state tests.test_extract_frames_batch`.
- **Inline ffmpeg argv in cmd_extract_frames_batch** (per CONTEXT D-10 + Discretion line 119) rather than refactoring a shared helper. Keeps cmd_extract_frames body untouched (FPS-07).
- **Defense in depth on `skip` boolean check** — `type(d['skip']) is bool` at parse time in `_load_segment`, then `seg.skip is True` at validate-time. Wrong-type inputs cannot smuggle past dataclass construction; validation can still inspect.
- **`Schedule.to_json` drops falsy/None fields** (fps=None, skip=False, label=None) to preserve symmetric input/output shape. Supports test 1's roundtrip claim.
- **ASCII-safe per-test tmpdir under `tests/_tmp_batch/`** — zh-CN Windows %TEMP% expands to `C:/Users/管啸野/AppData/Local/Temp/...` which trips `_validate_out_path`'s CJK rejection. Test uses `tempfile.TemporaryDirectory(dir=tests/_tmp_batch)`. Added to `.gitignore`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] CJK Windows %TEMP% breaks default tempfile.TemporaryDirectory in test_extract_frames_batch**
- **Found during:** Task 3 (running test suite)
- **Issue:** zh-CN Windows resolves `tempfile.gettempdir()` to `C:/Users/管啸野/AppData/Local/Temp`, which contains the user's CJK username. `cmd_extract_frames_batch._validate_out_path` (Phase 3 SRC-10 D-19) rejects CJK in `--out`, so 7 of 12 tests failed at `_validate_out_path` before the test code ran.
- **Fix:** Added `_ascii_tmpdir_root()` helper that creates `tests/_tmp_batch/` under the repo root (always ASCII because the repo path is ASCII) and threads `dir=...` into every `tempfile.TemporaryDirectory(...)` call.
- **Files modified:** tests/test_extract_frames_batch.py, .gitignore (added `tests/_tmp_batch/`)
- **Verification:** All 12 tests now pass; the dedicated `test_8_cjk_rejected` still verifies CJK rejection by injecting CJK into the args.out subpath manually.
- **Committed in:** 9140793 (Task 3 commit)

**2. [Rule 3 - Blocking] Initial K5 docstring contained the literal substring `scenes.json`**
- **Found during:** Task 3 (K5 enforcement static-source check)
- **Issue:** First-cut docstring read "this function does NOT read scenes.json or auto-promote scenes/silence into a schedule." The substring `scenes.json` appears in the docstring text, so the K5 check `'scenes.json' not in inspect.getsource(...)` fails — the locked acceptance criterion treats any literal match as a violation.
- **Fix:** Rewrote the docstring to use "the scene-cuts artifact" / "that artifact" / "the silence-map artifact" — preserving K5 messaging without literal forbidden substrings. Added a note in the docstring that the K5 check uses static-source substring matching, so the code intentionally avoids the forbidden tokens.
- **Files modified:** agent/tools.py
- **Verification:** `python -c "import inspect, agent.tools as t; src = inspect.getsource(t.cmd_extract_frames_batch); assert 'agent.scenes' not in src and 'scenes.json' not in src; print('K5 ok')"` — now exits 0.
- **Committed in:** 9140793 (Task 3 commit, after iteration)

---

**Total deviations:** 2 auto-fixed (2 Rule 3 - Blocking)
**Impact on plan:** Both auto-fixes were necessary to make the locked acceptance criteria executable. No scope creep — plan executed otherwise as written.

## Issues Encountered

- **None** beyond the two auto-fixed Rule-3 blockers above. Initial test run for Task 1 passed all 18 tests on first invocation; Task 2 passed all 7 on first invocation; Task 3 needed two iterations: (1) tmpdir ASCII fix, (2) docstring rewording for K5 substring check.

## User Setup Required

**None.** No new runtime dependencies, no environment variables, no external services. The new `extract_frames_batch` subcommand reuses ffmpeg/ffprobe (already required by Phase 1/3) and the existing schedule.json — which Claude authors directly via the Write tool per CONTEXT K5.

## Next Phase Readiness

**Plan 04-02 (detect_scenes / detect_silence)** can now be planned:
- silence_map.json schema (D-20) consumed by `Schedule.validate(silence_map=...)` is already documented and accepted as input.
- D-08 fallback path is already implemented and tested — 04-02 can ship later without breaking 04-01 users (graceful degradation).
- New artifacts go in `output/<slug>/` alongside meta.json/segs.json (consistent with Phase 2 D-15/D-16 doctor list).
- silero-vad's torch dependency (~700MB) — RESEARCH §"CRITICAL" recommends opt-in via `requirements-optional.txt`. 04-02 planner decides.

**Phase 5 (Teaching plan.md + multipass refine)** is unblocked from Phase 4's perspective: schedule.json is independent of plan.md per CONTEXT D-26.

**17-archive backward-compat:** Verified in plan VERIFICATION §"17-archive": extract_frames_batch is opt-in additive (requires schedule.json which archives don't have); cmd_extract_frames untouched (FPS-07 git diff = zero deletions); no schema_version bumps; no changes to existing artifacts.

## Self-Check

Verifying claims in this SUMMARY:

**Files exist:**
- agent/scheduler.py — `[ -f agent/scheduler.py ]` → FOUND
- agent/state.py — `[ -f agent/state.py ]` → FOUND (modified)
- agent/tools.py — `[ -f agent/tools.py ]` → FOUND (modified)
- tests/test_scheduler.py — FOUND
- tests/test_state.py — FOUND
- tests/test_extract_frames_batch.py — FOUND

**Commits exist:**
- 488850c — feat(04-01): add agent/scheduler.py — FOUND in `git log`
- 932a052 — feat(04-01): add derived_segment_state — FOUND
- 9140793 — feat(04-01): add cmd_extract_frames_batch — FOUND

**Acceptance criteria:**
- `python -c "from agent.scheduler import Schedule, ScheduleValidationError; print('ok')"` — exits 0
- `python -c "from agent.state import derived_segment_state; print('ok')"` — exits 0
- `python -m agent.tools extract_frames_batch --help` — exits 0
- K5 static check: `python -c "import inspect, agent.tools as t; src = inspect.getsource(t.cmd_extract_frames_batch); assert 'agent.scenes' not in src and 'scenes.json' not in src; print('K5 ok')"` — exits 0
- FPS-07: `git diff HEAD -- agent/tools.py | grep -E '^-' | grep -v '^---'` — zero output (cmd_extract_frames body unchanged)
- All 37 tests pass: `python -m unittest tests.test_scheduler tests.test_state tests.test_extract_frames_batch` — `Ran 37 tests in 0.034s OK`

## Self-Check: PASSED

---
*Phase: 04-frame-fps-automation-schedule-json-extract-frames-batch*
*Completed: 2026-05-01*
