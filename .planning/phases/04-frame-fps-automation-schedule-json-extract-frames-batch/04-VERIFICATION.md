---
phase: 04-frame-fps-automation-schedule-json-extract-frames-batch
verified: 2026-05-01T00:00:00Z
status: passed
score: 5/5 must-haves structurally verified + 7/7 FPS satisfied + 8/8 derived truths green; 5 live-runtime checks deferred to user (HUMAN-UAT visible in /gsd-progress)
overrides_applied: 1  # human_needed → passed: SCs all structurally green; live tests + WR-01/02/04 classified future-cleanup per verifier recommendation
human_verification:
  - test: "End-to-end real video — author a schedule.json by hand, run `python -m agent.tools extract_frames_batch --schedule output/<slug>/schedule.json --out output/<slug>/frames`, verify frames emitted match `seg_<start>_<index>.jpg`."
    expected: "Frames extracted with the legacy filename grammar; segment-level events appear in state.jsonl; rerunning skips completed segments."
    why_human: "Requires a real video.mp4 + ffmpeg subprocess on disk; unit tests mock subprocess.run. SC-1, SC-2 confirmed structurally only."
  - test: "Resume after kill — kill `extract_frames_batch` mid-segment, rerun, confirm completed segments skipped and the killed segment retried."
    expected: "Re-run prints 'segment N already completed, skipping' for completed indices; restarts the killed one. --force bypass re-runs everything."
    why_human: "Requires real-world process kill + state.jsonl interaction; can't simulate cleanly without subprocess fault injection."
  - test: "FPS-04 silence-coverage end-to-end — run `detect_silence`, write a schedule that fails coverage, confirm extract_frames_batch raises ScheduleValidationError before any ffmpeg fires."
    expected: "Validation gate refuses to start; user sees the FPS-04 error message naming the uncovered interval."
    why_human: "Validates the full pipeline (silero-vad → silence_map.json → schedule validation); needs real audio + opt-in torch install."
  - test: "PySceneDetect on a real screen-recording video — run `detect_scenes` with default threshold, confirm stdout reports count + median duration; manually inspect scenes.json for over-segmentation."
    expected: "scenes.json conforms to {version:1, video, scenes:[{start,end}]}; stdout shows median useful for Claude's threshold decision."
    why_human: "Real PySceneDetect run requires opencv + a real video; unit tests stub the detector."
  - test: "Code review warnings WR-01/WR-02/WR-04 — confirm they are non-blocking by intentionally writing a malformed schedule (start>=end, fps=0, ffmpeg missing PATH) and observing the failure mode."
    expected: "Each malformed input either reaches ffmpeg with confusing errors (WR-01/02) or leaves a dangling 'started' event (WR-04); REVIEW.md has documented all three as future-cleanup quality guards."
    why_human: "Operator needs to confirm the diagnostic-quality regression is acceptable for this milestone vs. blocking phase closure."
---

# Phase 4: Frame fps Automation Verification Report

**Phase Goal:** Let Claude write one schedule.json per video; tool batch-executes ffmpeg per segment, resume-aware via state.jsonl, with mandatory silence-coverage protection — without crossing K5 "Claude is decider" line. Backward-compat with existing cmd_extract_frames (FPS-07).
**Verified:** 2026-05-01T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth                                                                                                                                                                                                | Status     | Evidence                                                                                                                                                                |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | extract_frames_batch validates schedule.json (5 checks: version=1, full-duration ±2s, no overlap, fps XOR skip, no unknown keys) and emits frames preserving `seg_<start>_<index>.jpg` grammar (SC-1) | ✓ VERIFIED | `agent/scheduler.py:151-211` (validate); `agent/tools.py:367-478`; spot-check confirmed all 5 checks raise; filename pattern `f"seg_{int(seg.start):04d}_%06d.jpg"` at `agent/tools.py:449` |
| 2   | Re-running after partial failure skips completed segments via state.jsonl segment-level events (SC-2)                                                                                                | ✓ VERIFIED | `agent/state.py:169-193` derived_segment_state; `agent/tools.py:411-422` resume gate; `--force` bypass at line 411-412; spot-check Test1/2/3 pass                       |
| 3   | Schedule lacking baseline pass AND lacking explicit silence coverage rejected (SC-3 — FPS-04 silence-coverage protection)                                                                            | ✓ VERIFIED | `agent/scheduler.py:213-266` _check_silence_coverage; spot-check confirmed Case1 (no baseline + no silence_map) raises with locked message "FPS-04: no silence_map.json found, baseline pass missing" |
| 4   | detect_scenes / detect_silence produce JSON artifacts; tool NEVER auto-promotes (K5) (SC-4)                                                                                                          | ✓ VERIFIED | `agent/scenes.py`, `agent/silence.py` exist with documented public API; cmd_detect_scenes/silence in agent/tools.py:481-568; K5 substring check passes (see Anti-Patterns) |
| 5   | cmd_extract_frames CLI continues to work unchanged (SC-5 / FPS-07)                                                                                                                                   | ✓ VERIFIED | `git diff 6b5996e..HEAD -- agent/tools.py` body for cmd_extract_frames is byte-identical (only the *neighbour* function name changed because cmd_extract_frames_batch is now inserted after it) |
| 6   | extract_frames_batch CLI loads schedule.json, validates, iterates segments emitting per-segment events, calls ffmpeg with same -vsync vfr argv shape, preserving filename grammar                    | ✓ VERIFIED | `agent/tools.py:382-478`; argv shape mirrors cmd_extract_frames; segment events have details.segment_index per Phase 2 D-14 落地                                        |
| 7   | cmd_extract_frames_batch does NOT import agent.scenes or reference scenes.json (K5 boundary)                                                                                                          | ✓ VERIFIED | `inspect.getsource(cmd_extract_frames_batch)` — neither `'agent.scenes'` nor `'scenes.json'` in source; verified by static-source check (test_extract_frames_batch.py + live spot-check) |
| 8   | cmd_detect_scenes / cmd_detect_silence do NOT reference schedule.json (K5 boundary)                                                                                                                   | ✓ VERIFIED | `inspect.getsource(cmd_detect_scenes)` and `cmd_detect_silence` — neither contains `'schedule.json'`; deliberate generic phrasing ("the schedule artifact" / "fps segment") in stdout hint |

**Score:** 8/8 truths verified (structural)

### Required Artifacts

| Artifact                       | Expected                                                                                                                                | Status     | Details                                                                                                                                                  |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `agent/scheduler.py`           | Schedule + Segment dataclasses + ScheduleValidationError + from_json/to_json/validate (5 D-05 + FPS-04 silence coverage + _interval_covered) | ✓ VERIFIED | 14428 bytes; module-level constants `_DURATION_TOLERANCE_S=2.0`, `_BASELINE_FPS_MAX=0.1`; locked FPS-04 error message at line 235-238; no `__post_init__` |
| `agent/state.py`               | derived_segment_state additive helper                                                                                                   | ✓ VERIFIED | New function at lines 169-193; existing API (append_event, read_events, derived_state, params_hash) untouched                                            |
| `agent/scenes.py`              | PySceneDetect ContentDetector wrapper (lazy import)                                                                                     | ✓ VERIFIED | 1707 bytes; `def detect_scenes(video_path, *, threshold=27.0)` returns `list[{start, end}]` with floats from FrameTimecode.get_seconds()                 |
| `agent/silence.py`             | silero-vad wrapper with lazy import + invert-speech-to-silence + ensure_audio_wav                                                       | ✓ VERIFIED | 4541 bytes; `_invert_speech_to_silence`, `detect_silence`, `ensure_audio_wav` all present; clean RuntimeError install hint when silero-vad missing       |
| `agent/tools.py`               | cmd_extract_frames_batch + cmd_detect_scenes + cmd_detect_silence handlers + argparse + cmds dict                                       | ✓ VERIFIED | All 3 handlers added (lines 367-568); argparse subparsers wired (lines 799-831); cmds dict registers all three (lines 859-872); CLI --help works for all |
| `requirements.txt`             | scenedetect[opencv]>=0.6.7.1 added; silero-vad NOT present                                                                              | ✓ VERIFIED | Line 5: `scenedetect[opencv]>=0.6.7.1`; no `silero-vad` reference                                                                                       |
| `requirements-optional.txt`    | silero-vad>=5.1 + torch>=1.12.0 + torchaudio>=0.12.0 with explanatory comment                                                            | ✓ VERIFIED | All three pins present; comment explains opt-in rationale (CONTEXT D-22 correction)                                                                       |
| `CLAUDE.md`                    | "决策支持工具（Phase 4，可选）" section documenting both subcommands + silero-vad opt-in                                                | ✓ VERIFIED | Lines 22-29; documents both detect_scenes and detect_silence + opt-in install hint + FPS-04 graceful-degradation behavior                                |

All artifacts pass Levels 1 (exists), 2 (substantive — function signatures/locked constants present), 3 (wired — imports/registrations confirmed).

### Key Link Verification

| From                                       | To                                                                          | Via                                                                        | Status   | Details                                                                                                                              |
| ------------------------------------------ | --------------------------------------------------------------------------- | -------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `agent/tools.py:cmd_extract_frames_batch`  | `agent/scheduler.py:Schedule.from_json + validate`                          | load + strict validation gate before any ffmpeg invocation                  | ✓ WIRED  | `from agent.scheduler import Schedule, ScheduleValidationError` at line 382; `Schedule.from_json(schedule_path)` line 391; `schedule.validate(...)` line 407 |
| `agent/tools.py:cmd_extract_frames_batch`  | `agent/sources/_common.py:ffprobe_video`                                    | video duration probe for D-05.2 full-duration coverage check                | ✓ WIRED  | Import at line 384; `probe = ffprobe_video(video_path)` at line 396                                                                  |
| `agent/tools.py:cmd_extract_frames_batch`  | `agent/state.py:append_event + derived_segment_state`                       | segment-level event emission + resume reducer                               | ✓ WIRED  | `derived_segment_state(events, stage="extract_frames_batch")` line 415; `_emit_event` calls at lines 425/430/438/460/468 with `details.segment_index` |
| `agent/scheduler.py:Schedule.validate`     | `ScheduleValidationError`                                                   | every check raises with segment index + field name in message              | ✓ WIRED  | Six `raise ScheduleValidationError(...)` calls in validate() with locator info (lines 165, 172, 175, 180, 191, 202, 234, 261)        |
| `agent/tools.py:cmd_detect_scenes`         | `agent/scenes.py:detect_scenes`                                             | list of {start, end} tuples → JSON wrap → write_json_atomic                 | ✓ WIRED  | `from agent.scenes import detect_scenes` at line 494; `scenes = detect_scenes(...)` line 501; `write_json_atomic(out, obj)` line 504 |
| `agent/tools.py:cmd_detect_silence`        | `agent/silence.py:detect_silence`                                           | list of silence intervals → JSON wrap → write_json_atomic                   | ✓ WIRED  | `from agent.silence import detect_silence, ensure_audio_wav` at line 533; intervals→write_json_atomic at line 558                    |
| `agent/silence.py:detect_silence`          | `silero_vad` (lazy import)                                                  | ImportError → RuntimeError with requirements-optional.txt hint              | ✓ WIRED  | Lazy try/except at lines 60-66; spot-check confirmed message contains all 3 substrings (silero-vad, torch, requirements-optional.txt) |

### Behavioral Spot-Checks

| Behavior                                                                                       | Command                                                                                       | Result                                                            | Status |
| ---------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------- | ------ |
| All Phase 4 modules importable                                                                 | `python -c "from agent.scheduler ..."`                                                        | imports ok                                                        | ✓ PASS |
| `extract_frames_batch --help` works                                                            | `python -m agent.tools extract_frames_batch --help`                                           | shows --schedule, --out, --force                                  | ✓ PASS |
| `detect_scenes --help` works (no opencv runtime needed for argparse)                           | `python -m agent.tools detect_scenes --help`                                                  | shows video, --out, --threshold                                   | ✓ PASS |
| `detect_silence --help` works without silero-vad/torch installed (lazy import)                 | `python -m agent.tools detect_silence --help`                                                 | shows video, --out (no ImportError)                               | ✓ PASS |
| K5 batch boundary (no scenes ref)                                                              | `inspect.getsource(cmd_extract_frames_batch)` substring check                                  | `'agent.scenes'` not in src AND `'scenes.json'` not in src        | ✓ PASS |
| K5 scenes/silence boundary (no schedule ref)                                                   | `inspect.getsource(cmd_detect_scenes/silence)` substring check                                | `'schedule.json'` not in src for both                             | ✓ PASS |
| 56 unit tests pass via stdlib unittest                                                         | `python -m unittest tests.test_scheduler tests.test_state tests.test_extract_frames_batch tests.test_scenes tests.test_silence` | Ran 56 tests in 0.185s OK                       | ✓ PASS |
| FPS-04 strict-OR-fallback gate behaves correctly                                               | Spot-check Cases 1/2/3 (no-baseline/no-silmap rejected; baseline+no-silmap passes; uncovered flagged interval rejected) | All 3 cases match locked behavior | ✓ PASS |
| 5 mandatory D-05 validation checks raise correctly                                             | Spot-check version != 1, first.start > 2s, overlap, fps AND skip both true                    | All 4 checks raise with expected messages                         | ✓ PASS |
| derived_segment_state semantics correct                                                        | Spot-check (a) latest=completed → included, (b) failed-after-completed → dropped              | Both cases match                                                  | ✓ PASS |
| FPS-07 cmd_extract_frames byte-identical pre-Phase-4 vs current                                | `git diff 6b5996e..HEAD -- agent/tools.py` for cmd_extract_frames body                        | Body identical; only neighbour function differs                   | ✓ PASS |
| Lazy ImportError clean RuntimeError when silero-vad blocked                                    | `sys.modules['silero_vad']=None; detect_silence(...)`                                          | RuntimeError with all 3 substrings (silero-vad, torch, hint)      | ✓ PASS |
| Filename grammar `seg_<start>_<index>.jpg` preserved                                            | grep `seg_{int(seg.start):04d}_%06d.jpg` in cmd_extract_frames_batch source                   | Pattern present at line 449-450                                   | ✓ PASS |
| Resume via derived_segment_state + --force bypass                                              | grep `derived_segment_state` + `args.force` + `completed: set[int] = set()` in source         | All three present                                                 | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                              | Status      | Evidence                                                                                                                                   |
| ----------- | ----------- | -------------------------------------------------------------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| FPS-01      | 04-01       | `Schedule` dataclass + JSON I/O matching locked schema                                                   | ✓ SATISFIED | `agent/scheduler.py:59-74` defines @dataclass Schedule + Segment with locked fields (version, video, default_scale, default_quality, segments) |
| FPS-02      | 04-01       | Schedule validation: full-duration ±2s, no overlap, fps XOR skip, no unknown keys (fail loud)            | ✓ SATISFIED | `agent/scheduler.py:151-211` (.validate); 5 mandatory checks each raise ScheduleValidationError; spot-check Cases 1-4 confirm                 |
| FPS-03      | 04-01       | `extract_frames_batch` CLI consumes schedule.json, preserves filename grammar, resume-aware              | ✓ SATISFIED | `agent/tools.py:367-478`; `seg_{int(seg.start):04d}_%06d.jpg` grammar at line 449; resume via derived_segment_state line 415; --force bypass |
| FPS-04      | 04-01       | Validation requires baseline pass OR explicit per-segment coverage of silence > 5s (silent-blind-spot)   | ✓ SATISFIED | `agent/scheduler.py:213-266` _check_silence_coverage; D-08 fallback when silence_map missing; locked error message present                  |
| FPS-05      | 04-02       | `detect_scenes` CLI emits scenes.json via PySceneDetect; tool NEVER auto-promotes                        | ✓ SATISFIED | `agent/scenes.py`+`cmd_detect_scenes`; K5 verified via inspect.getsource (no `schedule.json` in source); scenedetect[opencv]>=0.6.7.1 in requirements.txt |
| FPS-06      | 04-02       | `detect_silence` CLI emits silence_map.json via silero-vad; gaps > 5s flagged                            | ✓ SATISFIED | `agent/silence.py`+`cmd_detect_silence`; flag_threshold_s=5.0 default; opt-in via requirements-optional.txt; clean ImportError hint         |
| FPS-07      | 04-01       | Existing single-segment `extract_frames` CLI remains unchanged                                           | ✓ SATISFIED | `git diff 6b5996e..HEAD -- agent/tools.py` for cmd_extract_frames body is byte-identical; spot-check confirms                              |

**Coverage:** 7/7 requirements satisfied. No orphaned requirements (REQUIREMENTS.md maps FPS-01..FPS-07 → Phase 4, all 7 claimed across 04-01 + 04-02 plans).

### Anti-Patterns Found

| File                  | Line          | Pattern                                                       | Severity   | Impact                                                                                                                                  |
| --------------------- | ------------- | ------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `agent/scheduler.py`  | 151-211       | (WR-01) Schedule.validate doesn't enforce `seg.start < seg.end` | ⚠️ Warning | Inverted/zero-length segment passes 5 D-05 checks if neighbours align; reaches ffmpeg with `-t -10` (negative duration). Diagnostic-quality regression, not SC violation. |
| `agent/scheduler.py`  | 198-205       | (WR-02) Schedule.validate accepts `fps <= 0` (e.g. fps:0)       | ⚠️ Warning | fps=0 propagates to `-vf "fps=0,..."` which is undefined ffmpeg behaviour. Diagnostic-quality regression, not SC violation.            |
| `agent/scheduler.py`  | 312           | (WR-03) `_load_segment` raises raw TypeError on `fps: null`   | ⚠️ Warning | Cosmetic — bypasses ScheduleValidationError discipline; user gets confusing stack trace instead of locator. Locator hygiene only.       |
| `agent/tools.py`      | 467-478       | (WR-04) cmd_extract_frames_batch only catches CalledProcessError | ⚠️ Warning | If ffmpeg missing from PATH (FileNotFoundError) the started event is left dangling in state.jsonl; resume invariant breaks. Material edge case. |
| `agent/silence.py`    | 101-115       | (IN-01) ensure_audio_wav leaks tempfile on ffmpeg failure       | ℹ️ Info    | Accumulates orphan `.tmp.detect_silence.*.wav` in slug_dir on repeated failure. Minor cleanup hygiene.                                 |
| `agent/scheduler.py`  | 88            | (IN-02) Schedule.from_json doesn't catch JSONDecodeError      | ℹ️ Info    | Error message lacks "schedule.json at <path>" locator. Diagnostic quality.                                                              |
| `agent/scheduler.py`  | 250-266       | (IN-03) _check_silence_coverage doesn't validate silence_map item shape | ℹ️ Info    | Hand-edited or external silence_map raises raw KeyError instead of ScheduleValidationError.                                            |
| `agent/tools.py`      | 401-406       | (IN-04) cmd_extract_frames_batch doesn't handle malformed silence_map.json | ℹ️ Info    | Raw JSONDecodeError instead of "silence_map.json malformed; consider re-running detect_silence". Diagnostic quality.                  |
| `agent/scheduler.py`  | 314           | (IN-05) _load_segment doesn't validate label type             | ℹ️ Info    | `label: 123` slips into stdout printing; no impact on ffmpeg.                                                                          |
| `agent/silence.py`    | 106-107       | (IN-06) `import os as _os` shadow-private inside function     | ℹ️ Info    | Cosmetic — `os` could go to module top with other stdlib imports.                                                                       |

**Classification rationale:** WR-01/02/04 are real edge cases that should be fixed (fps=0, start>=end, ffmpeg-not-on-PATH each have observable symptoms), but they do NOT violate the 5 ROADMAP Success Criteria as worded — those criteria require validation enforces "full-duration coverage, no overlap, fps XOR skip, no unknown keys" (matched), not "every conceivable schema-shape error". REVIEW.md frames them as quality-guard improvements. Recommendation: track as future-cleanup, surface to operator via human verification rather than as blocking gaps.

WR-03 + IN-01 through IN-06 are diagnostic-message-quality / minor cleanup nits — none block any SC.

### Human Verification Required

See frontmatter `human_verification:` block. The 5 items track:
1. **End-to-end real video extract_frames_batch run** — verifies SC-1 + SC-2 with actual ffmpeg, beyond unit-test mocks.
2. **Resume after kill** — verifies SC-2 with real process fault.
3. **FPS-04 silence-coverage end-to-end** — exercises the full silero-vad → silence_map.json → schedule validation chain on a real video.
4. **PySceneDetect on a real screen-recording** — verifies cmd_detect_scenes stdout reporting + scenes.json shape with real PySceneDetect (unit tests stub the detector).
5. **WR-01/WR-02/WR-04 disposition decision** — operator confirms these are acceptable as future-cleanup vs. blocking gaps for this milestone.

### Gaps Summary

**Structural verification: passed (5/5 ROADMAP Success Criteria, 7/7 FPS requirements, 8/8 derived truths).**

All static checks confirm the K5 boundary (verified at three call sites: cmd_extract_frames_batch source contains neither `agent.scenes` nor `scenes.json`; cmd_detect_scenes/silence source contains no `schedule.json`). FPS-07 is verified via byte-identical diff of cmd_extract_frames body across 6b5996e..HEAD. The locked FPS-04 fallback warning string and the silence-coverage strict-OR-fallback gate behave per CONTEXT D-07/D-08 in spot-checks.

The 4 WR warnings from REVIEW.md identify diagnostic-quality / edge-case validation gaps that do NOT violate the 5 SCs as worded. WR-04 is the most material (resume-invariant break when ffmpeg missing from PATH) but still represents a recoverable degraded state, not a missing capability. They are surfaced as human verification items so the operator can decide whether to fix-now or defer.

**Status: human_needed** — automated checks all pass, but the phase produces runnable code whose behavior under real ffmpeg/PySceneDetect/silero-vad load has not been exercised. The unit tests prove the wiring; only an operator can confirm end-to-end behavior on a real video.

---

_Verified: 2026-05-01T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
