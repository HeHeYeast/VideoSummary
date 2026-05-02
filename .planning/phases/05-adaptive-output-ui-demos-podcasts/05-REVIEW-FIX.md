---
phase: 05-adaptive-output-ui-demos-podcasts
fixed_at: 2026-05-02T00:00:00Z
review_path: .planning/phases/05-adaptive-output-ui-demos-podcasts/05-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 5: Code Review Fix Report

**Fixed at:** 2026-05-02
**Source review:** `.planning/phases/05-adaptive-output-ui-demos-podcasts/05-REVIEW.md`
**Iteration:** 1
**Scope:** critical_warning (CR + WR; 3 findings)

**Summary:**
- Findings in scope: 3 (0 critical, 3 warning)
- Fixed: 3
- Skipped: 0

All three warnings from REVIEW.md resolved with atomic commits. D-29 backward-compat
preserved: paragraphs.json + segs.json baselines untouched. D-24 redline preserved:
repetition guard remains warn-only and never mutates input segs.

## Fixed Issues

### WR-01: VTT priority lock broken at file-picker step

**Files modified:** `agent/sources/youtube.py`
**Commit:** `f5347bb`
**Applied fix:** Replaced `target_dir.glob("video.*.vtt")` with explicit lang-priority
loop. Iterate `("zh-Hans", "zh-Hant", "zh", "en")` and pick the first existing
`video.{lang}.vtt`. If none found (auto-caption variants like
`video.zh-Hans-orig.vtt`), fall back to `sorted(target_dir.glob(...))` to give
deterministic ordering across filesystems.

This restores D-31's "VTT lang priority zh-Hans>zh-Hant>zh>en" contract that
was broken by NTFS alphabetical glob order ('en' < 'zh-Hans').

**Verification:** Tier 1 re-read + Tier 2 `python -c "import ast; ast.parse(...)"`.

---

### WR-02: Trigram repetition guard does not detect typical phrase-level whisper hallucinations

**Files modified:** `agent/tools.py`, `tests/test_repetition_guard.py` (new)
**Commit:** `91a656e`
**Applied fix:** Per user instruction, took **option 2 (broaden the algorithm)**.
Added a complementary density-based detector running in parallel with the existing
consecutive-run detector:

1. New helper `_count_repeated_trigrams` — Counter-style total occurrence count
   (vs the existing `_count_consecutive_trigrams` run-length).
2. New helper `_density_hit(text)` — returns `(gram, count)` if the most-common
   3-gram has `count >= 4` AND `count * 3 / len(text) >= 0.6` (chars-covered
   density). For `'我们这里用' * 5` (cycle-len-5), coverage = 5*3/25 = 60% → hits.
3. `whisper_repetition_guard` now runs FOUR detection passes per (a)/(b) ×
   (single-seg / cross-seg-window): consecutive + density. Same `(seg_idx, gram)`
   dedup set as before.
4. Constants added: `_DENSITY_MIN_COUNT = 4`, `_DENSITY_COVERAGE = 0.6`.

**Threshold rationale:** The reviewer's literal formula `count / (len(text)/3) > 0.6`
was mathematically wrong for cyclic phrase-repeats (max single-trigram density ≈
1/cycle-length, capping at ~33% for 3-char cycles). Switched to the
cleaner "chars covered by gram instances / text length" formulation, which
matches the reviewer's intent ("occupies >60% of joined text") and fires correctly
on the canonical `'我们这里用' * 5` example.

**D-29 backward-compat:** PRESERVED — `whisper_repetition_guard` only writes the
NEW Phase 5 `transcribe_warnings.json` artifact (no archived baseline exists).
`paragraphs.json` and `segs.json` baselines are untouched (verified by reading
the function — it reads input segs read-only and never mutates).

**D-24 redline:** PRESERVED — input `segs` list never mutated (asserted by
`test_d24_input_not_mutated` unit test).

**Tests added:** `tests/test_repetition_guard.py` — 15 stdlib unittest cases
covering both detectors, D-24 no-mutation, D-23 schema, and edge cases. All pass.

**Verification:** Tier 1 re-read + Tier 2 `python -c "import ast"` syntax check
+ Tier 3 functional test (`python -m unittest tests.test_repetition_guard -v` → 15/15 OK)
+ canonical `'我们这里用' * 5` now triggers (was returning 0 warnings before fix).

---

### WR-03: cmd_diarize does not validate CJK in audio_wav path

**Files modified:** `agent/tools.py`
**Commit:** `4244a0b`
**Applied fix:** Added `_validate_out_path(audio_path)` immediately after the
existing `_validate_out_path(out_path)` call, BEFORE `out_dir.mkdir(...)` so
the validation fails fast. Wrapped in a comment block referencing REVIEW WR-03 and
D-19 (the original CJK-on-zh-CN-Windows hazard).

The function `_validate_out_path` is misnamed for this use case (validates an
INPUT path here), but as the review noted, its actual contract — "raise
ValueError on CJK in any path before subprocess runs" — applies identically.
A future cleanup could rename to `_validate_subprocess_path`; deferred per the
review's note (not in Phase 5 scope).

**Verification:** Tier 1 re-read + Tier 2 `python -c "import ast"` syntax check
+ Tier 3 functional test:
- CJK audio path (`output/中文测试/audio.wav`) → raises `ValueError` (was: silently
  bypassing duration gate then opaque pyannote stack trace)
- ASCII audio path → passes validation, hits expected downstream `RuntimeError`
  (HF_TOKEN absent on test machine — confirms validation step is non-fatal for
  legitimate paths).

---

## Skipped Issues

None — all 3 in-scope findings were successfully fixed.

## Out-of-Scope Findings (Info-level, not addressed this iteration)

The following IN-* findings from REVIEW.md were NOT addressed (fix_scope =
critical_warning excludes Info):

- **IN-01**: Dead code (`_VAD_DEFAULTS` in src/asr.py and `_DEFAULTS` in
  agent/asr_v2.py) — cleanup, no functional impact.
- **IN-02**: HF_TOKEN log line treats whitespace-only as `<set>` — purely
  cosmetic, defense-in-depth only.
- **IN-03**: Repetition guard step 2 over-reports on long mono-trigram runs —
  doctor-grade code quality, not a correctness bug.
- **IN-04**: Proxy credentials visible in subprocess argv — yt-dlp limitation;
  threat surface is low (multi-user shell).
- **IN-05**: ffmpeg `-vsync vfr` deprecated — Phase 3 code, deferred to future
  ffmpeg-flags audit.

To address these in a follow-up pass, re-run `/gsd-code-review-fix` with
`fix_scope: all`.

---

_Fixed: 2026-05-02_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
