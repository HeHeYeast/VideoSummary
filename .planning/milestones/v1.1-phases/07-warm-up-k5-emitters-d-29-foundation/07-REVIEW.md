---
phase: 07-warm-up-k5-emitters-d-29-foundation
reviewed: 2026-05-03T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - agent/_v11.py
  - agent/glossary_audit.py
  - agent/mode_signals.py
  - agent/queue.py
  - agent/schedule_suggestion.py
  - agent/sources/_common.py
  - agent/tools.py
  - agent/transcribe_lint.py
  - scripts/measure_token_budget.py
  - scripts/replay_v10_archives.py
  - tests/test_glossary_audit.py
  - tests/test_k5_emitters.py
  - tests/test_mode_signals.py
  - tests/test_queue.py
  - tests/test_replay_v10.py
  - tests/test_schedule_suggestion.py
  - tests/test_transcribe_lint.py
  - tests/test_v11_marker.py
findings:
  critical: 1
  warning: 6
  info: 7
  total: 14
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-05-03T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

The Phase 07 warm-up code is generally high quality with strong attention to the D-29 byte-equal invariant, K5 boundary preservation (statically asserted via grep tests), and Windows / cross-terminal correctness. The opt-in marker pattern in `agent/_v11.py` is clean and well-tested (10 tests, including corruption tolerance and atomic write). The 4 K5 emitters maintain the read-only contract: `transcribe_lint` writes only its sibling artifact, `mode_signals` deliberately omits `recommended_mode`, `schedule_suggest` includes the mandatory FPS-04 baseline, and `glossary_audit` is read-only. The cross-terminal queue (`agent/queue.py`) wraps every read-modify-write in `FileLock` with stale-PID takeover and has subprocess-based race tests (T12, T13).

However, **one Critical filename collision** exists: both `agent/tools.py:_emit_repetition_warnings` (Phase 5 TEACH-11) and `cmd_transcribe_lint` (Phase 07 CORR-01a) write to the same file `transcribe_warnings.json` with **incompatible inner schemas**. Whichever command runs second silently overwrites the other's output, destroying detection results. This is a real data-loss bug that needs resolution before Phase 07 ships v1.1 features to users.

Six Warnings flag schema/edge-case issues (duplicate hash computation, non-mp4 video discovery miss, missing `--duration` validation, missing CJK validation in one handler, test global-state pollution, corrupt-meta.json crash). Seven Info items capture nits like dead `flagged_silences` conditional and cosmetic glob choices.

## Critical Issues

### CR-01: `transcribe_warnings.json` filename collision between Phase 5 repetition guard and Phase 07 transcribe_lint

**File:** `agent/tools.py:624` (Phase 5 `_emit_repetition_warnings`) and `agent/tools.py:1313` + `agent/transcribe_lint.py:37` (Phase 07 `cmd_transcribe_lint`)

**Issue:** Both code paths write to `<slug_dir>/transcribe_warnings.json`:

- Phase 5 `_emit_repetition_warnings` (line 624) writes `{"version": 1, "warnings": [<repetition_warning>...]}` where each entry has keys `start, end, trigram, count, context_before, context_after, seg_indices`.
- Phase 07 `cmd_transcribe_lint` (line 1313, constant in `agent/transcribe_lint.py:37`) writes `{"version": 1, "warnings": [<suspect_token>...]}` where each entry has keys `para_id, seg_index, start, end, suspect_text, suggested_text, evidence_source, confidence, context_before, context_after`.

The two payload schemas are incompatible — only the top-level `{"version": 1, "warnings": [...]}` envelope matches. If `transcribe` runs and detects repetitions (writing `transcribe_warnings.json`), then a subsequent `python -m agent.tools transcribe_lint <slug_dir>` overwrites the file with suspect-token warnings, **silently destroying** the Phase 5 repetition data. Conversely, running `transcribe` after `transcribe_lint` overwrites the lint output. The two data sets cannot coexist.

This is doubly problematic given the v1.1 `--features transcribe_lint` workflow encourages running both in sequence (transcribe → transcribe_lint), making the collision the _common_ path, not a corner case.

**Fix:** Pick one of:

1. (Recommended) Rename Phase 07 output to a distinct filename, e.g.:
   ```python
   # agent/transcribe_lint.py
   WARNINGS_FILENAME = "transcribe_lint_warnings.json"  # was "transcribe_warnings.json"
   ```
   And update the help text in `agent/tools.py:1597`. This preserves the existing Phase 5 D-23 `transcribe_warnings.json` artifact (which is referenced in Phase 5 documentation) and ships the new artifact under a non-colliding name.

2. Merge the two schemas into one envelope with a `kind` discriminator and have both writers append rather than overwrite. Requires file-locking and schema migration — significantly more invasive.

Option 1 is byte-equal-safe for v1.0 archives (Phase 5 path unchanged) and prevents the silent data-loss bug. Add a test asserting both files can coexist after running both commands sequentially.

## Warnings

### WR-01: `cmd_schedule_suggest` video discovery misses non-mp4 extensions

**File:** `agent/tools.py:1404`

**Issue:** When `--duration` is not provided, the handler looks for the video via:
```python
video_files = list(slug_dir.glob("video.mp4")) or list(slug_dir.glob("*.mp4"))
```

This misses `video.webm`, `video.mkv`, `video.flv` — formats that yt-dlp legitimately produces (per Phase 3 SRC-11 WR-01 fix in `cmd_ingest`). The user gets a misleading `FileNotFoundError: no .mp4 in {slug_dir}` even when `video.webm` exists. The suggested escape hatch (`--duration` override) is opaque — users won't know to use it.

**Fix:**
```python
# agent/tools.py around line 1404
VIDEO_EXTS = ("mp4", "webm", "mkv", "flv", "mov")
video_files = list(slug_dir.glob("video.mp4"))  # prefer canonical name
if not video_files:
    for ext in VIDEO_EXTS:
        video_files.extend(slug_dir.glob(f"*.{ext}"))
if not video_files:
    raise FileNotFoundError(
        f"no video file in {slug_dir} (looked for *.{{{','.join(VIDEO_EXTS)}}}); "
        f"pass --duration <float> to skip ffprobe (W5 archive-without-video path)"
    )
```

### WR-02: `cmd_schedule_suggest` does not validate `duration_s > 0`

**File:** `agent/tools.py:1411` and `agent/schedule_suggestion.py:55-101`

**Issue:** `ffprobe_video` can legitimately return `duration_s = 0.0` for malformed or partial files (per `agent/sources/_common.py:127-128` which catches `TypeError, ValueError` and falls back to 0). When `duration_s = 0`, `compute_suggestion` produces segments `{"start": 0.0, "end": 0.0, "fps": ...}` for both `default-coverage` and `fps-04-baseline`. These zero-duration segments will pass through to a downstream `schedule.json` that fails strict validation — or worse, ffmpeg silently extracts no frames.

The `--duration` override path (line 1399) does `float(args.duration)` without checking it's positive — `--duration 0` or `--duration -10` is accepted.

**Fix:** Validate before calling `compute_suggestion`:
```python
# agent/tools.py around line 1414
if duration_s <= 0:
    raise ValueError(
        f"duration_s must be > 0; got {duration_s} from {duration_source}. "
        f"If ffprobe returned 0, the file may be corrupt; pass --duration explicitly."
    )
```

### WR-03: `cmd_transcribe_lint` crashes on corrupt `meta.json`

**File:** `agent/tools.py:1306-1307`

**Issue:**
```python
meta_path = slug_dir / "meta.json"
meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
```

If `meta.json` exists but contains malformed JSON (e.g., truncated download), `json.loads` raises `JSONDecodeError` and the user sees a stack trace instead of a friendly degrade. This contradicts the project's tolerant-of-corrupt-files pattern (see `agent/_v11.py:62-64`, `agent/queue.py:75-80` which both log a warning and continue).

**Fix:**
```python
meta_path = slug_dir / "meta.json"
meta: dict = {}
if meta_path.exists():
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("meta.json at %s unreadable (%s); proceeding without title cross-reference", meta_path, e)
```

This degrades cleanly: title_token strategy will not fire (since `meta == {}`), but the other 4 strategies still run.

### WR-04: `cmd_transcribe_lint` lacks `_validate_out_path` CJK guard inconsistent with peer handlers

**File:** `agent/tools.py:1290-1317`

**Issue:** Other Phase 07 K5 emitters call `_validate_out_path` on their output (`cmd_mode_signals` line 1332, `cmd_schedule_suggest` line 1375). `cmd_transcribe_lint` writes to `slug_dir / "transcribe_warnings.json"` but never validates that `slug_dir` is ASCII-clean. Today this is harmless because `cmd_transcribe_lint` invokes no subprocess (so no GBK code-page corruption hazard) — Python file I/O with `encoding="utf-8"` handles CJK paths correctly. But the inconsistency invites a future regression: if anyone adds a subprocess (e.g., wraps `pypinyin` in an external tool, or shells out for word segmentation), the missing guard becomes a real bug.

**Fix:** Add the validation for consistency with peers and forward-compat:
```python
# agent/tools.py around line 1300
slug_dir = Path(args.slug_dir)
_validate_out_path(slug_dir)
if not slug_dir.is_dir():
    raise FileNotFoundError(f"slug dir not found: {slug_dir}")
```

### WR-05: `tests/test_queue.py` race tests pollute global `Path.home` permanently

**File:** `tests/test_queue.py:260, 278` (`TestQueueRace.test_T12_*` and `test_T13_*`)

**Issue:** The race tests do `q.Path.home = lambda: Path(...)` to redirect `Path.home()` to the temp dir. Since `q.Path` is the same class object as `pathlib.Path` (just imported under a different name), this monkeypatches the `Path` class **process-globally**. Unlike `TestQueuePrimitives` (lines 44-48) which uses `unittest.mock.patch(...)` with proper `tearDown` restoration, `TestQueueRace.tearDown` does not restore `Path.home`. After these tests run, any subsequent code in the same Python process that calls `Path.home()` (e.g., another test module loading `~/.config/...`) gets the lambda pointing to a deleted temp dir.

When run via `python -m unittest discover`, this can cause intermittent failures in unrelated tests depending on load order.

**Fix:** Save and restore the original in `setUp`/`tearDown`:
```python
def setUp(self):
    self._td = tempfile.TemporaryDirectory(dir=_ascii_tmpdir_root())
    self.fake_home = Path(self._td.name)
    self._orig_home = q.Path.home  # capture for restore

def tearDown(self):
    q.Path.home = self._orig_home  # restore BEFORE temp dir cleanup
    self._td.cleanup()
```

Or better, use the same `unittest.mock.patch("agent.queue.Path.home", ...)` pattern as `TestQueuePrimitives` and pass the resolved home into the worker via env var only (the workers already use the env var, so the parent's `q.Path.home` mutation isn't needed for the race assertions themselves).

### WR-06: `cmd_mode_signals` duplicates `_hash_paragraphs` logic instead of calling the helper

**File:** `agent/tools.py:1339-1340` vs `agent/mode_signals.py:38-40`

**Issue:** `cmd_mode_signals` recomputes the paragraphs hash:
```python
# agent/tools.py:1339-1340
payload = json.dumps(paragraphs, ensure_ascii=False, sort_keys=True)
p_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

But `agent/mode_signals.py` already exports a `_hash_paragraphs` helper that does exactly this. The handler also imports `hashlib` directly to do the hashing, when it could just call the helper. If anyone changes the hash spec (algorithm, prefix length, sort_keys behavior) in `mode_signals.py`, the handler silently drifts and the `paragraphs_hash` field in the artifact no longer matches the staleness-detection contract documented in PITFALLS P-07.

**Fix:**
```python
# agent/tools.py
from agent.mode_signals import compute_signals, SIGNALS_FILENAME, _hash_paragraphs
# (drop `import hashlib` and the `payload = ...; p_hash = ...` block)

# Then:
p_hash = _hash_paragraphs(paragraphs)
```

The leading underscore in `_hash_paragraphs` is a soft "internal" hint, but consumed by tests already (`tests/test_mode_signals.py:12`). Either rename to `hash_paragraphs` (drop the underscore) or accept the established intra-package usage.

## Info

### IN-01: `agent/schedule_suggestion.py` redundant conditional in `flagged_silences` count

**File:** `agent/schedule_suggestion.py:49-52`

**Issue:**
```python
flagged_silences = (
    sum(1 for iv in (silence_map or []) if iv.get("flagged_for_review"))
    if silence_map else 0
)
```

The outer `if silence_map else 0` is redundant because `sum(1 for iv in [] if ...)` is already `0`. Simplify to:
```python
flagged_silences = sum(
    1 for iv in (silence_map or []) if iv.get("flagged_for_review")
)
```

### IN-02: `cmd_schedule_suggest` uses `glob("video.mp4")` for an exact filename match

**File:** `agent/tools.py:1404`

**Issue:** `slug_dir.glob("video.mp4")` returns at most 1 file (since "video.mp4" has no glob metacharacters). `(slug_dir / "video.mp4").exists()` is more idiomatic and avoids the implicit list-creation. Cosmetic.

**Fix:** When implementing WR-01 above, also collapse this:
```python
canonical = slug_dir / "video.mp4"
if canonical.exists():
    video_files = [canonical]
else:
    video_files = []
    for ext in VIDEO_EXTS:
        video_files.extend(slug_dir.glob(f"*.{ext}"))
```

### IN-03: `compute_suggestion` `video_filename` default is misleading

**File:** `agent/schedule_suggestion.py:31` and `agent/tools.py:1344`

**Issue:** `compute_suggestion(..., video_filename: str = "video.mp4")` and `cmd_mode_signals` constructs `"video": Path(args.paragraphs_json).parent.name + ".mp4"` — both hardcode `.mp4`. For YouTube downloads served as `.webm` (per Phase 3 SRC-11 WR-01), the suggestion artifact's `video` field misleads downstream consumers.

The K5 caller in `cmd_schedule_suggest` does pass through the actual filename (`video_filename = video_files[0].name`) when ffprobe is used (good!), but the `--duration` override branch (line 1401) hardcodes `"video.mp4"` again.

**Fix:** When implementing WR-01, also propagate the actual video name into the `--duration` branch by scanning for any video extension first, then falling back to `"video.mp4"` only when truly absent. Same for `cmd_mode_signals:1344` — consider `video_path` from `meta.json` instead of synthesizing from slug.

### IN-04: `tests/test_queue.py` workers leave `_QUEUE_TEST_HOME` env var set in parent

**File:** `tests/test_queue.py:259, 277`

**Issue:** `os.environ["_QUEUE_TEST_HOME"] = str(self.fake_home)` is set in the parent process inside test methods but never unset in `tearDown`. When tests run in sequence within one process, the env var leaks. Not a correctness issue (each test sets it fresh), but worth cleaning up.

**Fix:** In `TestQueueRace.tearDown`, add `os.environ.pop("_QUEUE_TEST_HOME", None)`.

### IN-05: `cmd_mode_signals` imports `hashlib` inside function instead of at module top

**File:** `agent/tools.py:1329`

**Issue:** `import hashlib` lives inside `cmd_mode_signals` because of the duplicated hash logic flagged in WR-06. Once WR-06 is fixed, this in-function import disappears. Mentioned here for completeness.

**Fix:** Subsumed by WR-06.

### IN-06: `agent/_v11.py:set_v11_marker` is not lock-protected

**File:** `agent/_v11.py:89-110`

**Issue:** `set_v11_marker` does an atomic write but no FileLock. If two terminals call `set_v11_marker(slug, [...])` concurrently with **different** feature lists, the last writer wins (silently). For Phase 07 this is acceptable because marker management is documented as a one-time setup operation, but a doc comment noting "concurrent set_v11_marker → last-writer-wins; readers see one of the two writes atomically" would help future maintainers.

**Fix:** Add docstring note:
```python
def set_v11_marker(slug_dir, features: list[str]) -> None:
    """Write `.v11_features.json` with given feature list. Atomic.

    Concurrency note: NOT FileLock-protected — concurrent set_v11_marker
    calls with different feature lists exhibit last-writer-wins. Acceptable
    for the documented one-time-setup pattern; if future workflows require
    atomic feature-flag toggling under concurrency, wrap in FileLock at
    the call site.

    [...rest of existing docstring...]
    """
```

### IN-07: `_extract_cjk_tokens` bigram-only extraction is documented but worth re-validating

**File:** `agent/transcribe_lint.py:82-100`

**Issue:** The docstring acknowledges this is a known limitation: "2-char words dominate Modern Mandarin vocabulary (~70%)" — so 30% of substitution targets are missed. The B1 fix (test_12) proves the 2-char path works, but real-world ASR may produce 3+ char homophone errors (e.g., `深度学习` mis-heard as `审度学习`) that won't be caught.

This is by-design for v1.1 (avoiding `jieba` dep), and acceptable given the strategy is one of 5 fallbacks. No fix needed for Phase 07 ship — but worth tracking as a known limitation in PITFALLS.md so Phase 08+ can revisit if real-world corpus shows misses concentrated on tri-grams.

**Fix:** Documentation-only — log this in PITFALLS as a v1.1 known-limitation entry referencing this file.

---

_Reviewed: 2026-05-03T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
