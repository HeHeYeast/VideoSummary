---
phase: 04-frame-fps-automation-schedule-json-extract-frames-batch
plan: 02
subsystem: frame-extraction
tags: [scenes, silence, decision-support, pyscenedetect, silero-vad, opt-in-deps, k5-boundary]

# Dependency graph
requires:
  - phase: 04-01-scheduler-extract-frames-batch
    provides: Schedule.validate(silence_map=...) consumes silence_map.json shape locked here; K5 enforcement pattern (inspect.getsource substring check) reused
  - phase: 02-resume-infrastructure-cache-correctness
    provides: write_json_atomic for both new artifacts
  - phase: 03-source-refactor-new-sources-youtube-local-mp4-generic
    provides: ffprobe_video duration probe (used by cmd_detect_silence to invert speech→silence properly)
provides:
  - "agent/scenes.py: detect_scenes(video_path, *, threshold=27.0) -> list[{start,end}] (PySceneDetect ContentDetector wrapper, lazy import)"
  - "agent/silence.py: detect_silence(audio_path, *, duration_s, flag_threshold_s=5.0) -> list[{start,end,duration,flagged_for_review?}] (silero-vad wrapper, lazy import + clean RuntimeError install hint)"
  - "agent/silence.py: _invert_speech_to_silence(speech_ts, duration_s) helper (Pitfall P7-safe with leading + trailing silence)"
  - "agent/silence.py: ensure_audio_wav(video_path, slug_dir) (Pitfall P5: reuse existing audio.wav else extract 16kHz mono via ffmpeg)"
  - "agent/tools.py: cmd_detect_scenes + cmd_detect_silence handlers + argparse subparsers + cmds dict entries"
  - "Locked scenes.json shape: {version:1, video, scenes:[{start,end}]} (D-16)"
  - "Locked silence_map.json shape: {version:1, video, silence_intervals:[{start,end,duration,flagged_for_review?}]} (D-20)"
  - "Locked stdout hint phrasing for cmd_detect_silence (FPS-04 reminder per D-21)"
  - "requirements-optional.txt convention for opt-in heavy deps (silero-vad + torch + torchaudio ~700MB)"
affects: [05-teaching-plan-md-multipass-refine]

# Tech tracking
tech-stack:
  added:
    - "scenedetect[opencv]>=0.6.7.1 in requirements.txt (~80MB; default install)"
    - "silero-vad>=5.1 + torch>=1.12.0 + torchaudio>=0.12.0 in requirements-optional.txt (~700MB; opt-in only)"
  patterns:
    - "Lazy-import-with-clean-RuntimeError pattern for opt-in heavy deps (silero-vad gates only the runtime call, not module import — --help still works without torch)"
    - "Stub-the-package-via-sys.modules test pattern for testing PySceneDetect/silero-vad wrappers without installing them (patch.dict(sys.modules, {'scenedetect': fake})) — clean since both modules use deferred imports"
    - "K5 boundary verified by inspect.getsource substring assertion: cmd_detect_scenes / cmd_detect_silence source contains no 'schedule.json' literal — same pattern established in 04-01 for cmd_extract_frames_batch"
    - "requirements-optional.txt convention (precedent: STACK.md pyannote opt-in pattern) — installed via 'pip install -r requirements-optional.txt'; consumer modules raise clean RuntimeError with this exact install hint when import fails"
    - "Audio resolution policy in cmd_detect_silence: prefer existing slug-dir audio.wav (Phase 2 transcribe artifact); fall back to ffmpeg extract under .tmp.detect_silence.* prefix in slug_dir"

key-files:
  created:
    - agent/scenes.py
    - agent/silence.py
    - requirements-optional.txt
    - tests/test_scenes.py
    - tests/test_silence.py
  modified:
    - agent/tools.py
    - requirements.txt
    - CLAUDE.md
    - .gitignore

key-decisions:
  - "silero-vad in requirements-optional.txt, NOT requirements.txt — corrects CONTEXT D-22's incorrect claim that silero-vad is already a faster-whisper dep. RESEARCH §'CRITICAL: silero-vad's torch dependency' verified faster-whisper bundles SileroVADModel internally via onnxruntime; standalone silero-vad PyPI package hard-depends on torch>=1.12.0 + torchaudio>=0.12.0 (~700MB), which the project does NOT have. Default ¥0 workflow stays light; FPS-04 silence-coverage validation degrades gracefully to baseline-pass-only (CONTEXT D-08)."
  - "detect_silence is the public API name (matches PLAN.md interfaces + verification grep for '^def detect_silence'). Function signature includes duration_s as required keyword arg so caller (cmd_detect_silence) can ffprobe once and pass it down — keeps the wrapper pure (no ffprobe dep), and avoids re-probing in tests."
  - "cmd_detect_silence's stdout hint deliberately uses generic 'the schedule artifact' / 'fps segment' phrasing instead of the literal 'schedule.json' substring — required to pass the K5 inspect.getsource substring check while preserving the FPS-04 coverage reminder semantics (D-21)."
  - "scenedetect import deferred inside detect_scenes() body (not module-level) so tests that patch sys.modules['scenedetect'] before importing scenes.py work cleanly. Same pattern for silero-vad in detect_silence."
  - "ensure_audio_wav uses tempfile.mkstemp(dir=slug_dir, prefix='.tmp.detect_silence.') with explicit dir=slug_dir — same-volume guarantee for any future atomicity needs and matches the Phase 2 atomic-write tempfile-prefix idiom."
  - "Stdlib unittest (not pytest) — Phase 2 RESEARCH and 04-01 SUMMARY established this precedent. Tests run via 'python -m unittest tests.test_scenes tests.test_silence'."
  - "Per-test ASCII-safe tmpdirs (tests/_tmp_scenes/, tests/_tmp_silence/) — same workaround as 04-01 for zh-CN Windows %TEMP% containing CJK username (trips _validate_out_path)."

patterns-established:
  - "Opt-in heavy dependency pattern: requirements-optional.txt + lazy import inside function body + clean RuntimeError with exact 'pip install -r requirements-optional.txt' install hint. Baseline degraded mode (here: FPS-04 baseline-pass-only fallback per D-08) ensures the default workflow remains usable."
  - "K5 enforcement pattern (continued from 04-01): tools that produce decision-support artifacts MUST NOT contain the consuming-artifact filename (schedule.json) in their source. Verified at test time by inspect.getsource substring assertion. Documentation/messages use generic phrasing (e.g., 'the schedule artifact', 'fps segment')."
  - "Decision-support CLI shape: cmd_* writes its own locked-schema JSON via write_json_atomic, prints stdout summary (count + key metric for Claude's mental model), prints output path. Never reads or writes the consuming artifact."

requirements-completed: [FPS-05, FPS-06]

# Metrics
duration: ~20min
completed: 2026-05-01
---

# Phase 04 Plan 02: detect_scenes + detect_silence Decision Support Summary

**Two read-only decision-support CLIs for Phase 4: PySceneDetect-backed `detect_scenes` (FPS-05; default install) and silero-vad-backed `detect_silence` (FPS-06; opt-in install). Both produce locked-schema JSON artifacts (scenes.json + silence_map.json) that Claude reads when authoring schedule.json — tools NEVER auto-promote these into a schedule (K5 boundary statically asserted in tests). silero-vad correctly placed in `requirements-optional.txt` per RESEARCH correction of CONTEXT D-22 (~700MB torch dep is opt-in, not default).**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-01 (plan execution start, post 04-01 commit c3e895d)
- **Completed:** 2026-05-01
- **Tasks:** 2 / 2
- **Files modified:** 8 (5 created, 3 modified)
- **Tests:** 19 new unit tests (8 scenes + 11 silence), all passing via stdlib unittest
- **Total project tests:** 56 (37 from 04-01 + 19 new), all passing

## Accomplishments

- **`agent/scenes.py`** — PySceneDetect ContentDetector wrapper. `detect_scenes(video_path, *, threshold=27.0) -> list[{start,end}]`. Lazy `from scenedetect import detect, ContentDetector` inside function body (decoupling for clean test stubbing). Plain-float dict output (FrameTimecode unwrapped via `.get_seconds()`).

- **`agent/silence.py`** — silero-vad wrapper with three exports:
  - `_invert_speech_to_silence(speech_ts, duration_s)` — Pitfall P7-safe inversion handling leading + middle + trailing silence explicitly. Pure function, separately testable without silero-vad installed.
  - `detect_silence(audio_path, *, duration_s, flag_threshold_s=5.0)` — runs silero-vad, normalizes to plain floats, inverts via helper, attaches `duration` + `flagged_for_review:true` for >5s intervals. **Lazy-imports silero-vad** with `try/except ImportError` → clean `RuntimeError("detect_silence requires silero-vad (and torch ~700MB). Install with: pip install -r requirements-optional.txt")`.
  - `ensure_audio_wav(video_path, slug_dir)` — Pitfall P5 audio resolution: reuse existing `<slug>/audio.wav` if present (Phase 2 cmd_transcribe artifact); else `ffmpeg -ac 1 -ar 16000 -vn` extract to `.tmp.detect_silence.<random>.wav` under slug_dir.

- **`agent/tools.py`** — Two new handlers added after `cmd_extract_frames_batch`:
  - `cmd_detect_scenes` — `_validate_out_path` (CJK guard) → `detect_scenes` → `write_json_atomic({version:1, video, scenes:[...]})` → stdout `"detected N scenes; median duration = X.Xs"`. Median in stdout helps Claude immediately spot over-segmentation (median < 2s on tutorial video → re-run with `--threshold 35`).
  - `cmd_detect_silence` — `_validate_out_path` → `ffprobe_video` for duration → `ensure_audio_wav` → `detect_silence` → `write_json_atomic({version:1, video, silence_intervals:[...]})` → stdout `"Found N silence intervals; M flagged > 5s"` + locked FPS-04 reminder per D-21 (using "the schedule artifact" generic phrasing for K5).
  - argparse subparsers wired (with `--threshold` flag for detect_scenes, default 27.0).
  - cmds dict registrations: `detect_scenes`, `detect_silence`.

- **`requirements.txt`** — Added `scenedetect[opencv]>=0.6.7.1` (default install, ~80MB).

- **`requirements-optional.txt`** — New file with `silero-vad>=5.1` + `torch>=1.12.0` + `torchaudio>=0.12.0` and explanatory comment block. Establishes the opt-in heavy-dep convention (precedent: STACK.md pyannote pattern). The default `requirements.txt` deliberately excludes silero-vad — corrects CONTEXT D-22's incorrect claim.

- **`CLAUDE.md`** — New 「决策支持工具（Phase 4，可选）」 section between 「可用工具」 and 「抖音支持」 documenting both subcommands, the opt-in install for detect_silence, and the FPS-04 graceful-degradation behavior when silence_map.json is absent.

- **K5 boundary statically asserted** — Both `cmd_detect_scenes` and `cmd_detect_silence` source contains no `schedule.json` literal substring. Verified by `inspect.getsource()` substring assertion in tests/test_scenes.py + tests/test_silence.py + final smoke check.

## Task Commits

Each task committed atomically (all `--no-verify` per parallel-execution flag, executed on the worktree branch):

1. **Task 1: agent/scenes.py + cmd_detect_scenes + scenedetect dep (FPS-05)** — `4c8a38c` (feat)
2. **Task 2: agent/silence.py + cmd_detect_silence + opt-in deps (FPS-06)** — `aa31a98` (feat)

## Files Created/Modified

- `agent/scenes.py` *(created)* — 39 lines. PySceneDetect wrapper with lazy import + threshold-tunable + plain-float dict output. K5 docstring callout.
- `agent/silence.py` *(created)* — 113 lines. silero-vad wrapper with `_invert_speech_to_silence`, `detect_silence`, `ensure_audio_wav`. Lazy import + clean RuntimeError install hint. K5 docstring callout.
- `agent/tools.py` *(modified, additive only)* — Added `cmd_detect_scenes` + `cmd_detect_silence` handlers (after `cmd_extract_frames_batch`); added 2 argparse subparser blocks (after `extract_frames_batch`); added 2 cmds-dict entries. Existing handlers + argparse + cmds dict shape preserved (no diff to 04-01 cmd_extract_frames_batch body).
- `requirements.txt` *(modified)* — Added `scenedetect[opencv]>=0.6.7.1` after `imagehash`.
- `requirements-optional.txt` *(created)* — New file: `silero-vad>=5.1` + `torch>=1.12.0` + `torchaudio>=0.12.0` + explanatory comment block.
- `CLAUDE.md` *(modified)* — Added 「决策支持工具（Phase 4，可选）」 section (8 lines) between 「可用工具」 and 「抖音支持」.
- `.gitignore` *(modified)* — Added `tests/_tmp_scenes/` + `tests/_tmp_silence/` (per-test ASCII-safe tmpdirs, same rationale as 04-01's `tests/_tmp_batch/`).
- `tests/test_scenes.py` *(created)* — 8 unit tests covering wrapper conversion (FT → plain float dicts), default+custom threshold, locked JSON shape, stdout count + median, CJK rejection, --help works, K5 substring assertion.
- `tests/test_silence.py` *(created)* — 11 unit tests covering lazy-import RuntimeError + 3 substring requirements (`silero-vad`, `torch`, `requirements-optional.txt`), Pitfall P7 leading+middle+trailing inversion (Test 2), >5s flagging (Test 3), locked JSON shape (Test 4), stdout hint format with FPS-04 mention (Test 5), CJK rejection (Test 6), audio.wav reuse (Test 7a) vs ffmpeg extract path (Test 7b), --help works without silero-vad (Test 8), K5 substring assertion.

## Decisions Made

- **silero-vad correctly placed in requirements-optional.txt** — Corrects CONTEXT D-22's incorrect claim that silero-vad is already a faster-whisper dep. RESEARCH verified faster-whisper bundles `SileroVADModel` internally via onnxruntime/ctranslate2 but does NOT pull the standalone `silero-vad` PyPI package. silero-vad >=5 hard-depends on `torch>=1.12.0` + `torchaudio>=0.12.0` (~700MB), which the project does not have. Honors PROJECT.md "minimum new deps" and CONTEXT D-08 graceful-degradation paths.
- **`def detect_silence` (not `detect_silence_intervals`)** — Followed PLAN.md interfaces and verification grep (`^def detect_silence`) as the authoritative naming. Call site uses keyword-arg `duration_s` so wrapper stays pure (no ffprobe inside) — caller's responsibility, easier testing.
- **Stdout hint uses generic phrasing** — "the schedule artifact" / "fps segment" rather than literal "schedule.json". Required for K5 substring-check pass while preserving FPS-04 coverage-reminder semantics.
- **Deferred imports for both wrappers** — `from scenedetect import ...` inside `detect_scenes`, `from silero_vad import ...` inside `detect_silence`. Allows tests to monkey-patch `sys.modules['scenedetect']` / `sys.modules['silero_vad']` BEFORE importing the wrappers, and ensures `--help` for both subcommands works on machines without these deps (lazy-fail at runtime call only).
- **Per-test ASCII-safe tmpdirs** — `tests/_tmp_scenes/` + `tests/_tmp_silence/` mirror 04-01's `tests/_tmp_batch/` workaround for zh-CN Windows `%TEMP%` containing the CJK username. Added to `.gitignore`.
- **Stdlib unittest** — Continues 04-01's stdlib-only test precedent. No pytest dependency added.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Read tool path mismatch (worktree vs main repo)**
- **Found during:** Task 1 (initial test_scenes.py write)
- **Issue:** First `Write` of `tests/test_scenes.py` resolved to the main repo path `D:\gxy_code\videoSummary\tests\` instead of the worktree at `D:\gxy_code\videoSummary\.claude\worktrees\agent-a2b3698e6b91d15c8\tests\`. The bash CWD is the worktree (verified via `pwd`), so `git status` didn't see the new file.
- **Fix:** Removed the misplaced file from the main repo (`rm /d/gxy_code/videoSummary/tests/test_scenes.py`) and re-wrote with the explicit absolute worktree path.
- **Files affected:** `tests/test_scenes.py` (relocated to worktree)
- **Committed in:** 4c8a38c (Task 1 commit, post-relocation)

**2. [Rule 3 - Blocking] CJK %TEMP% same workaround as 04-01 needed for new tests**
- **Found during:** Task 1 + Task 2 (test setup)
- **Issue:** `tempfile.TemporaryDirectory()` defaults to `%TEMP%` which on zh-CN Windows is `C:/Users/管啸野/AppData/Local/Temp` — trips `_validate_out_path` CJK rejection in cmd_detect_scenes / cmd_detect_silence.
- **Fix:** Added `_ascii_tmpdir_root()` helper in both new test files (mirrors 04-01's pattern), creating `tests/_tmp_scenes/` and `tests/_tmp_silence/`. Added both to `.gitignore`.
- **Files affected:** `tests/test_scenes.py`, `tests/test_silence.py`, `.gitignore`
- **Verification:** All 8 + 11 tests now pass; CJK rejection still verified in `test_6_cjk_out_rejected` via explicit CJK injection in `args.out` subpath.
- **Committed in:** 4c8a38c (Task 1) + aa31a98 (Task 2) + .gitignore in 4c8a38c

---

**Total deviations:** 2 auto-fixed (both Rule 3 - Blocking; both environmental, expected for this Windows zh-CN repo).
**Impact on plan:** None — both auto-fixes were necessary scaffolding to make the locked acceptance criteria executable. No scope creep; plan executed otherwise as written.

## Issues Encountered

- **None** beyond the two auto-fixed Rule-3 blockers above. Both tasks went green on first test invocation after the test fixtures were correctly located. Initial run for Task 1 (8 tests): all passed. Initial run for Task 2 (11 tests): all passed. Combined re-run with Task 1+2+pre-existing 04-01: 56/56 passed.

## User Setup Required

**For default workflow:** Run `pip install -r requirements.txt` once to pull in the new `scenedetect[opencv]>=0.6.7.1` (~80MB). After that, `python -m agent.tools detect_scenes <video> --out <path>` works.

**For detect_silence (opt-in, ~700MB):** Run `pip install -r requirements-optional.txt`. Without this, `detect_silence` raises a clean `RuntimeError("detect_silence requires silero-vad (and torch ~700MB). Install with: pip install -r requirements-optional.txt")` and `extract_frames_batch` continues to work via the FPS-04 baseline-pass-only fallback (CONTEXT D-08).

No environment variables or external services required. silero-vad on first call may download a small ~20MB ONNX model into the user's torch.hub cache (one-time, local-only).

## Next Phase Readiness

- **Phase 4 fully complete** — Plans 04-01 + 04-02 ship: `Schedule.validate(silence_map=...)` (04-01) consumes the silence_map.json shape locked in 04-02 (D-20). Default-install users get `detect_scenes` + `extract_frames_batch` immediately; opt-in users add `detect_silence` for tighter FPS-04 coverage.
- **Phase 5 (Teaching plan.md + multipass refine)** unblocked — schedule.json is independent of plan.md per CONTEXT D-26; both decision-support artifacts (scenes.json + silence_map.json) are inputs Claude can reference when authoring plan.md's mode-classification + fps-strategy reasoning.
- **17-archive backward compatibility** — Both new subcommands are additive opt-in (no schema bumps; archives don't have video.mp4 in standard locations and don't auto-trigger these tools). cmd_extract_frames untouched (FPS-07 from 04-01); cmd_extract_frames_batch untouched (only the new handlers + subparsers added).

## Self-Check

Verifying claims in this SUMMARY:

**Files exist:**
- agent/scenes.py — `[ -f agent/scenes.py ]` → FOUND
- agent/silence.py — `[ -f agent/silence.py ]` → FOUND
- agent/tools.py (modified) — FOUND
- requirements.txt (modified, has scenedetect[opencv]) — FOUND
- requirements-optional.txt — FOUND
- CLAUDE.md (with 决策支持工具 section) — FOUND
- tests/test_scenes.py — FOUND
- tests/test_silence.py — FOUND
- .gitignore (with tests/_tmp_scenes/ + tests/_tmp_silence/) — FOUND

**Commits exist (verified via git log):**
- 4c8a38c — feat(04-02): add agent/scenes.py + cmd_detect_scenes — FOUND
- aa31a98 — feat(04-02): add agent/silence.py + cmd_detect_silence — FOUND

**Acceptance criteria:**
- `python -c "from agent.scenes import detect_scenes; print('ok')"` — exits 0
- `python -c "from agent.silence import detect_silence; print('ok')"` — exits 0 (lazy import works without torch)
- `python -m agent.tools detect_scenes --help` — exits 0; mentions `--threshold`
- `python -m agent.tools detect_silence --help` — exits 0 (works without silero-vad/torch installed)
- `grep -E "^scenedetect\\[opencv\\]>=0\\.6\\.7\\.1" requirements.txt` — matches
- `grep -E "silero-vad" requirements.txt` — does NOT match (D-22 correction enforced)
- `grep -E "^silero-vad>=5\\.1" requirements-optional.txt` — matches
- `grep -E "^torch>=1\\.12\\.0" requirements-optional.txt` — matches
- `grep -E "^torchaudio>=0\\.12\\.0" requirements-optional.txt` — matches
- `grep -E "决策支持工具" CLAUDE.md` — matches
- K5 static check: `python -c "import inspect; from agent.tools import cmd_detect_scenes, cmd_detect_silence; assert 'schedule.json' not in inspect.getsource(cmd_detect_scenes); assert 'schedule.json' not in inspect.getsource(cmd_detect_silence); print('K5 ok')"` — exits 0
- RuntimeError install hint: with silero_vad import blocked, `detect_silence(...)` raises `RuntimeError` whose message contains all three substrings: `requirements-optional.txt`, `silero-vad`, `torch` — verified.
- All 56 tests pass: `python -m unittest tests.test_scheduler tests.test_state tests.test_extract_frames_batch tests.test_scenes tests.test_silence` — `Ran 56 tests in 0.187s OK`

## Self-Check: PASSED

---
*Phase: 04-frame-fps-automation-schedule-json-extract-frames-batch*
*Completed: 2026-05-01*
