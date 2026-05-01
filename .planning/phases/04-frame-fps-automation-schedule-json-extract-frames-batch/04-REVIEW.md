---
phase: 04-frame-fps-automation-schedule-json-extract-frames-batch
reviewed: 2026-05-01T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - agent/scheduler.py
  - agent/state.py
  - agent/scenes.py
  - agent/silence.py
  - agent/tools.py
  - requirements.txt
  - requirements-optional.txt
  - CLAUDE.md
findings:
  critical: 0
  warning: 4
  info: 6
  total: 10
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-05-01T00:00:00Z
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Reviewed Phase 4 deliverables: `Schedule`/`Segment` validation engine
(`agent/scheduler.py`), segment-level resume reducer extension
(`agent/state.py`), decision-support wrappers (`agent/scenes.py`,
`agent/silence.py`), CLI handlers in `agent/tools.py`
(`cmd_extract_frames_batch`, `cmd_detect_scenes`, `cmd_detect_silence`),
plus dependency manifests and `CLAUDE.md` updates.

Overall code quality is high: K5 (Claude-as-decider) is correctly enforced
both architecturally and via static-source tests; per-segment events use a
clean additive schema; the `ScheduleValidationError` discipline is solid;
CJK-rejection is consistently invoked before any subprocess. No security
issues, no hardcoded secrets, no `shell=True`, no `eval`/`exec`.

The findings below are about (a) a small set of validation gaps in
`Schedule.validate` that could let semantically-bad schedules slip past
parse-time and reach ffmpeg with confusing errors, (b) one resource-leak
pattern in `silence.ensure_audio_wav`, (c) one inconsistency in the
ffmpeg-failure exception scope between `cmd_extract_frames` and
`cmd_extract_frames_batch`, and (d) a few code-quality nits.

No Critical issues. 4 Warnings, 6 Info items.

## Warnings

### WR-01: `Schedule.validate` does not enforce `seg.start < seg.end` per segment

**File:** `agent/scheduler.py:151-211`
**Issue:** D-05.2 only checks `first.start <= 2s` and `last.end >= duration - 2s`; D-05.3 only checks `prev.end == curr.start` between consecutive pairs. A segment with `start=30, end=20` (or `start = end`) passes all five mandatory checks as long as its neighbors line up against `start=30` / `end=20` respectively. Such a segment then reaches ffmpeg as `-ss 30 -t -10` (negative duration — `seg.end - max(seg.start, 0) = -10`), which ffmpeg silently treats as "no `-t` constraint" or rejects depending on version. Result: a Claude-authored typo gets opaque ffmpeg behavior instead of a clear `ScheduleValidationError`.

**Fix:** Add a per-segment check inside the existing fps-XOR-skip loop:
```python
for i, seg in enumerate(self.segments):
    if seg.start >= seg.end:
        raise ScheduleValidationError(
            f"segment {i}: start ({seg.start}) must be < end ({seg.end}) "
            f"(D-05.x — degenerate or inverted segment)"
        )
    has_fps = seg.fps is not None
    has_skip = seg.skip is True
    ...
```
(Also covers `start == end` zero-length segments which currently slip through.)

### WR-02: `Schedule.validate` does not enforce `seg.fps > 0`

**File:** `agent/scheduler.py:198-205`
**Issue:** The fps-XOR-skip check accepts any `fps is not None` as "has fps", so `fps: 0` or `fps: -0.5` is treated as a valid fps segment (silence-coverage check at line 254 also accepts `seg.fps is not None and not seg.skip` without a positivity guard). `fps=0` then propagates into the ffmpeg `-vf "fps=0,scale=..."` filter at line 455, where ffmpeg either errors out or — worse, depending on version — produces undefined behavior. Same root cause as WR-01: a value error in Claude-authored JSON shouldn't reach ffmpeg.

**Fix:** Tighten the check at the existing per-segment loop:
```python
has_fps = seg.fps is not None
has_skip = seg.skip is True
if has_fps == has_skip:
    raise ScheduleValidationError(...)
if has_fps and seg.fps <= 0:
    raise ScheduleValidationError(
        f"segment {i}: `fps` must be > 0 (got {seg.fps!r})"
    )
```

### WR-03: `_load_segment` raises raw `TypeError` for `fps: null` in JSON

**File:** `agent/scheduler.py:312`
**Issue:** `fps = float(d["fps"]) if "fps" in d else None` — when the JSON contains `"fps": null`, the membership test `"fps" in d` is True, so the parser tries `float(None)` and raises a bare `TypeError: float() argument must be a string or a real number, not 'NoneType'`. This bypasses the `ScheduleValidationError` discipline (D-06): the user gets a confusing stack trace instead of a "segment N: ..." locator. The `start`/`end` block above is wrapped in try/except for exactly this reason; `fps` should be too.

**Fix:**
```python
if "fps" in d:
    raw_fps = d["fps"]
    if raw_fps is None:
        fps = None  # treat null same as omitted — let D-05.4 catch missing fps + missing skip
    else:
        try:
            fps = float(raw_fps)
        except (TypeError, ValueError) as e:
            raise ScheduleValidationError(
                f"segment {idx}: `fps` must be numeric (got {raw_fps!r}): {e}"
            ) from e
else:
    fps = None
```
Or, if `null` should be rejected outright (probably preferable for parse-strictness symmetry with the boolean-identity rule on `skip`), raise `ScheduleValidationError` for `null`.

### WR-04: `cmd_extract_frames_batch` only catches `subprocess.CalledProcessError`, not generic exceptions

**File:** `agent/tools.py:467-478`
**Issue:** The per-segment try block emits the `failed` event and re-raises only when ffmpeg exits non-zero. If `subprocess.run(["ffmpeg", ...])` raises `FileNotFoundError` (ffmpeg not on PATH), `PermissionError`, or any other exception, no `failed` event is recorded and `state.jsonl` is left with a dangling `started` event. This breaks the segment-level resume invariant: a re-run will treat the segment as in-flight, not as a clean "needs retry". Compare `cmd_extract_frames` at line 361 which catches `except Exception` (the looser scope is correct here too).

**Fix:** Broaden the except clause and preserve the `RuntimeError` translation only for ffmpeg's own failures:
```python
except subprocess.CalledProcessError as e:
    _emit_event(state_dir, "extract_frames_batch", "failed", details={...})
    raise RuntimeError(f"extract_frames_batch segment {i} failed: {e}") from e
except Exception as e:
    _emit_event(
        state_dir, "extract_frames_batch", "failed",
        details={"segment_index": i, "start": seg.start, "end": seg.end,
                 "error_type": type(e).__name__, "error": str(e)[:200]},
    )
    raise
```

## Info

### IN-01: `silence.ensure_audio_wav` leaks the temp wav on ffmpeg failure

**File:** `agent/silence.py:101-115`
**Issue:** `tempfile.mkstemp(...)` creates `tmp_path` on disk before `subprocess.run(cmd, check=True, ...)` is invoked. If ffmpeg fails, `subprocess.run` raises `CalledProcessError` and the (now-empty or partial) `.tmp.detect_silence.*.wav` file remains in `slug_dir`. Repeated failures accumulate clutter alongside legitimate slug artifacts, and a successful retry creates a fresh tempfile rather than reusing the old one.

**Fix:** Wrap the subprocess in try/except and unlink on failure:
```python
tmp_path = Path(name)
try:
    subprocess.run(cmd, check=True, capture_output=True)
except subprocess.CalledProcessError:
    tmp_path.unlink(missing_ok=True)
    raise
return tmp_path
```

### IN-02: `Schedule.from_json` does not catch `JSONDecodeError`

**File:** `agent/scheduler.py:88`
**Issue:** `obj = json.loads(Path(path).read_text(encoding="utf-8"))` propagates a raw `json.JSONDecodeError` for malformed JSON, breaking the `ScheduleValidationError` contract documented in D-06 ("locator + segment index"). Users see a low-level "Expecting value: line X column Y" without the `schedule.json at <path>` locator the rest of the validator provides.

**Fix:**
```python
try:
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
except json.JSONDecodeError as e:
    raise ScheduleValidationError(
        f"schedule.json at {path} is not valid JSON: {e}"
    ) from e
```

### IN-03: `_check_silence_coverage` doesn't validate silence_map item shape

**File:** `agent/scheduler.py:250-266`
**Issue:** The flagged-interval list comprehension passes through any dict and then accesses `iv["start"]` / `iv["end"]` at line 260 without guarding. A malformed `silence_map.json` (e.g., `{"flagged_for_review": true, "begin": 100, "stop": 110}`) raises a raw `KeyError("start")` instead of a `ScheduleValidationError` with the "silence_map.json is malformed" diagnostic. Low-impact because the artifact is tool-generated by `cmd_detect_silence`, but if a user hand-edits or imports an external silence map, the error message is unfriendly.

**Fix:** Validate keys before use, or wrap the key access:
```python
for iv in flagged:
    try:
        s, e = iv["start"], iv["end"]
    except KeyError as exc:
        raise ScheduleValidationError(
            f"silence_map.json: flagged interval missing key {exc}: {iv!r}"
        ) from exc
    if not _interval_covered(s, e, fps_segments):
        raise ScheduleValidationError(...)
```

### IN-04: `cmd_extract_frames_batch` doesn't handle malformed `silence_map.json`

**File:** `agent/tools.py:401-406`
**Issue:** `silence_map = json.loads(silence_map_path.read_text(encoding="utf-8"))` propagates raw `JSONDecodeError`. If the silence_map artifact got corrupted (partial write, manual edit), the user sees a JSON parse error rather than "silence_map.json malformed; consider re-running detect_silence or removing the file to fall back to baseline-pass". Same nature as IN-02 — diagnostic quality, not correctness.

**Fix:**
```python
silence_map = None
if silence_map_path.exists():
    try:
        silence_map = json.loads(silence_map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"silence_map.json at {silence_map_path} is malformed: {e}. "
            f"Re-run `python -m agent.tools detect_silence ...` or delete the "
            f"file to fall back to baseline-pass-only validation (D-08)."
        ) from e
```

### IN-05: `_load_segment` doesn't validate `label` type

**File:** `agent/scheduler.py:314`
**Issue:** `label = d.get("label")` — accepts any JSON value (`123`, `[]`, `{}`, etc.) without type-checking, even though the documented schema is `label: str | None`. Won't break ffmpeg (label isn't passed to subprocess), but a `label: 123` slips into stdout printing at line 466 as `[seg 0] 0s-300s @ fps=0.05: ...` with no warning. Consistent with the unknown-keys philosophy (catch typos / wrong shape) which would suggest enforcing.

**Fix:** Add a type-check after the unknown-keys block:
```python
if "label" in d and not (d["label"] is None or isinstance(d["label"], str)):
    raise ScheduleValidationError(
        f"segment {idx}: `label` must be a string or null "
        f"(got {d['label']!r} of type {type(d['label']).__name__})"
    )
```

### IN-06: `import os as _os` inside `silence.ensure_audio_wav`

**File:** `agent/silence.py:106-107`
**Issue:** `import os as _os` is shadowed-as-private inside the function body. The module already imports `subprocess` and `tempfile` at the top; `os` is a stdlib import with no side-effects, no reason to defer or alias it. Hurts readability and breaks the project's "imports at top" convention used elsewhere in `agent/`.

**Fix:** Move `import os` to the module top with the other stdlib imports, and use `os.close(fd)` directly.

---

_Reviewed: 2026-05-01T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
