---
phase: 07-warm-up-k5-emitters-d-29-foundation
fixed_at: 2026-05-03T08:30:57Z
review_path: .planning/phases/07-warm-up-k5-emitters-d-29-foundation/07-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 07: Code Review Fix Report

**Fixed at:** 2026-05-03T08:30:57Z
**Source review:** .planning/phases/07-warm-up-k5-emitters-d-29-foundation/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (1 Critical + 6 Warning)
- Fixed: 7
- Skipped: 0

All 7 in-scope findings landed cleanly with passing tests. Several drive-by Info items (IN-02 / IN-03 / IN-04 / IN-05) were folded into the Warning fixes where they touched the same lines, even though they were out of scope — noted in each fix below.

Test sweep after all fixes: 70 tests across 8 affected modules — all green.

## Fixed Issues

### CR-01: `transcribe_warnings.json` filename collision between Phase 5 repetition guard and Phase 07 transcribe_lint

**Files modified:** `agent/transcribe_lint.py`, `agent/tools.py`, `tests/test_transcribe_lint.py`
**Commit:** e47a0e1
**Applied fix:** Renamed `WARNINGS_FILENAME` constant in `agent/transcribe_lint.py` from `transcribe_warnings.json` to `transcribe_lint_warnings.json` (Option 1 in the review — byte-equal-safe for v1.0 archives, Phase 5 D-23 path unchanged). Updated argparse help text in `agent/tools.py:1597`. Updated `test_11_warnings_filename_constant` in `tests/test_transcribe_lint.py` to assert the new filename. Phase 5 `_emit_repetition_warnings` continues writing `transcribe_warnings.json` undisturbed; the two artifacts now coexist side-by-side. All 12 transcribe_lint tests pass; all 8 K5 boundary tests pass.

### WR-01: `cmd_schedule_suggest` video discovery misses non-mp4 extensions

**Files modified:** `agent/tools.py`
**Commit:** 018a855
**Applied fix:** Introduced an in-handler `_discover_video(slug_dir)` helper that prefers canonical `video.mp4` (via `.exists()`, IN-02 cosmetic) and falls back to the first match across `_VIDEO_EXTS = ("mp4", "webm", "mkv", "flv", "mov")` — extensions yt-dlp legitimately produces (per Phase 3 SRC-11). FileNotFoundError message updated to enumerate the searched extensions. Same commit applied WR-02 + IN-03 below; all 6 schedule_suggestion tests + 8 K5 boundary tests pass.

### WR-02: `cmd_schedule_suggest` does not validate `duration_s > 0`

**Files modified:** `agent/tools.py`
**Commit:** 018a855
**Applied fix:** Added two `duration_s <= 0` guards: (1) right after `float(args.duration)` parse for the `--duration` override branch with a clean ValueError pointing the user back to passing a positive float; (2) right after `ffprobe_video()` returns on the canonical branch with a ValueError naming the corrupt file and recommending `--duration` override. Same commit covered WR-01 + IN-03 (propagating actual video filename into the override branch via `_discover_video()`).

### WR-03: `cmd_transcribe_lint` crashes on corrupt `meta.json`

**Files modified:** `agent/tools.py`
**Commit:** e76e45f
**Applied fix:** Wrapped `json.loads(meta_path.read_text(...))` in a try/except for `(json.JSONDecodeError, OSError)`. On failure, logs WARNING and proceeds with `meta = {}`, matching the tolerant-of-corrupt pattern in `agent/_v11.py:62-64` and `agent/queue.py:75-80`. The title_token strategy gracefully no-ops on empty meta; the other 4 strategies still run. Same commit applied WR-04 below; all 12 transcribe_lint tests + 8 K5 boundary tests pass.

### WR-04: `cmd_transcribe_lint` lacks `_validate_out_path` CJK guard inconsistent with peer handlers

**Files modified:** `agent/tools.py`
**Commit:** e76e45f
**Applied fix:** Added `_validate_out_path(slug_dir)` call right after `Path(args.slug_dir)` in `cmd_transcribe_lint`, mirroring the peer K5 emitters (`cmd_mode_signals`, `cmd_schedule_suggest`). Forward-compat against any future word-segmenter / pypinyin shellout that would expose the same Windows-zh-CN GBK code-page hazard already documented in D-19.

### WR-05: `tests/test_queue.py` race tests pollute global `Path.home` permanently

**Files modified:** `tests/test_queue.py`
**Commit:** 109da38
**Applied fix:** In `TestQueueRace.setUp`, capture `self._orig_home = q.Path.home` BEFORE any worker / parent mutation. In `tearDown`, restore `q.Path.home = self._orig_home` BEFORE the temp dir cleanup. Also folded in IN-04: `os.environ.pop("_QUEUE_TEST_HOME", None)` for symmetry. The lambda-based monkeypatch inside the test bodies is preserved (the workers re-set it inside their subprocess regardless), but the parent process is no longer polluted across `python -m unittest discover` runs. All 14 queue tests pass.

### WR-06: `cmd_mode_signals` duplicates `_hash_paragraphs` logic instead of calling the helper

**Files modified:** `agent/tools.py`
**Commit:** 79943c9
**Applied fix:** Imported `_hash_paragraphs` from `agent.mode_signals` alongside `compute_signals` / `SIGNALS_FILENAME` and replaced the inlined `json.dumps(...) + hashlib.sha256(...)` block with a single `p_hash = _hash_paragraphs(paragraphs)` call. Dropped the in-function `import hashlib` (IN-05 folded in). Single source of truth for the staleness-detection contract documented in PITFALLS P-07. The leading-underscore name is kept as-is — already consumed by `tests/test_mode_signals.py:12`, established intra-package usage. All 12 mode_signals tests + 8 K5 boundary tests pass.

---

_Fixed: 2026-05-03T08:30:57Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
