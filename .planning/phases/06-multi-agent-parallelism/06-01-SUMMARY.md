---
phase: 06-multi-agent-parallelism
plan: 01
subsystem: locks
tags: [phase-6, para-01, para-02, para-03, file-lock, stdlib, multi-terminal]
dependency_graph:
  requires:
    - agent/state.py (Phase 2 — append_event idiom)
    - agent/silence.py (Phase 4 — module-level docstring + lazy-import shape)
    - agent/io.py (Phase 2 — now_iso shape; duplicated locally to keep _lock independent)
    - agent/douyin_downloader.py (Phase 3 — _patch_config_cookie callsite)
    - agent/tools.py (Phase 2/4/5 — cmd_transcribe / cmd_aggregate / cmd_extract_frames_batch bodies)
  provides:
    - "agent/_lock.py: FileLock + LockContended (cross-platform stdlib advisory lock)"
    - "vendor config.yaml lock at vendor/douyin_api/crawlers/douyin/web/.config.yaml.lock"
    - "per-slug resume.lock at output/<slug>/.resume.lock"
  affects:
    - cmd_transcribe / cmd_aggregate / cmd_extract_frames_batch — bodies wrapped in resume.lock
    - download_douyin (vendor cookies-patch path) — wrapped in vendor config lock
tech_stack:
  added: []
  patterns:
    - "Stdlib-only file lock (msvcrt.locking on Windows + fcntl.flock on POSIX)"
    - "Sentinel-byte locking on Windows (offset 0x7FFF_FFFE) so JSON content at offset 0 stays readable"
    - "Stale-PID detection via os.kill(pid, 0) — survives process crash"
    - "JSON {pid, ts} content for diagnostic 'who holds the lock' error messages"
key_files:
  created:
    - agent/_lock.py
    - tests/test_lock.py
    - .planning/phases/06-multi-agent-parallelism/06-01-SUMMARY.md
  modified:
    - agent/tools.py (module-level FileLock import + 3 cmd body wraps)
    - agent/douyin_downloader.py (vendor config.yaml lock around _patch_config_cookie)
decisions:
  - "Stdlib-only (no filelock>=3.16 dep) per CONTEXT D supersedes REQUIREMENTS.md PARA-01"
  - "Lock file content = JSON {pid, ts} for actionable contention errors"
  - "Stale-PID takeover via os.kill(pid, 0) — covers Claude Code crash mid-transcribe"
  - "Windows sentinel byte at high offset (~2GB) so byte 0 content stays readable (msvcrt.locking is mandatory, not advisory)"
  - "Vendor config.yaml lock lives at the douyin_downloader callsite (not source layer) — closest to the read-modify-write race"
  - "cmd_extract_frames (FPS-07 single-segment top-up helper) intentionally NOT locked — different concurrency model than long-running batch stages"
metrics:
  duration_min: 12
  completed_at: "2026-05-02T17:20:10+08:00"
  commits: 3
  tasks: 3
  tests_added: 9
  tests_passing: 8  # 1 skipped (POSIX-branch on Windows host)
  lines_added_lock: 243
  lines_added_tests: 253
requirements:
  - PARA-01
  - PARA-02
  - PARA-03
---

# Phase 6 Plan 01: Lock Infrastructure Summary

Stdlib-only cross-platform `FileLock` (msvcrt + fcntl) with stale-PID takeover wires into vendor `config.yaml` race + per-slug `.resume.lock` so two Claude Code terminals never corrupt shared state.

## What Shipped

**1. `agent/_lock.py` — FileLock primitive (243 LOC, stdlib-only)**

Public surface:
- `class FileLock(path, *, timeout: float = 0.0)` — context manager
- `class LockContended(RuntimeError)` — raised when contended

Behavioral contract:
- **Default `timeout=0`** → fail fast on contention with clean error
  message: `FileLock: <path> held by PID <pid> since <iso8601>`.
- **`timeout > 0`** → poll every 0.1s up to deadline, then raise `LockContended`.
- **NOT re-entrant** — separate `FileLock` instances on the same path always
  contend, even within the same process. Re-entrance is a footgun with no
  legitimate use in this codebase.
- **Stale-PID takeover** — if the lock file's holder PID is dead
  (`os.kill(pid, 0)` raises `ProcessLookupError`), the new requester acquires
  cleanly. Covers the "Claude Code crashed mid-transcribe" scenario.
- **Lock file content** = `{"pid": <int>, "ts": <iso8601>}` JSON; diagnostic
  only, used for the contention error message. Best-effort write; if the write
  fails the lock is still held (correctness doesn't depend on the JSON).
- **Lock file is NOT deleted on release** — left on disk as a forensic record
  of the last holder; stale-PID detection handles re-acquisition cleanly.

**2. Lock file conventions (where each lock lives)**

| Lock | Path | Lifetime | Held by |
|------|------|----------|---------|
| Vendor cookies | `vendor/douyin_api/crawlers/douyin/web/.config.yaml.lock` | Read-modify-write of `config.yaml` | `download_douyin()` while `_patch_config_cookie` runs |
| Per-slug resume | `output/<slug>/.resume.lock` | Whole body of long-running stage | `cmd_transcribe` / `cmd_aggregate` / `cmd_extract_frames_batch` |

Both files are dotfile-prefixed → not picked up by `*.json` globbing.

**3. `tests/test_lock.py` — 9 unittest cases**

| Test | What it verifies |
|------|------------------|
| `test_A_acquire_release_happy_path` | JSON content has `pid=os.getpid()` + `ts` field |
| `test_B_timeout_zero_contended_raises_with_holder_info` | `LockContended` msg contains `"PID"` + `"since"` |
| `test_C_stale_pid_takeover` | Pre-write dead PID 999999 → next acquire takes over + overwrites |
| `test_D_timeout_positive_polls_then_raises` | `timeout=0.3` waits ≥0.25s then raises |
| `test_E_release_idempotent` | `release()` twice = no error |
| `test_F_windows_branch_uses_msvcrt` | Windows-only: msvcrt is loaded + lock works |
| `test_F_posix_branch_uses_fcntl` | POSIX-only: fcntl is loaded + lock works (skipped on Windows) |
| `test_G_resume_lock_path_per_command` | Each cmd locks the EXACT slug-derived `.resume.lock` path |
| `test_H_concurrent_same_slug_fails_fast` | External lock holder → `cmd_transcribe` raises `LockContended` |

Run: `python -m unittest tests.test_lock -v`
Result on Windows host: 9 tests, 8 passed, 1 skipped (POSIX-branch — expected).

## Why `cmd_extract_frames` is intentionally unlocked

The single-segment `extract_frames` helper (FPS-07 top-up tool) has a
fundamentally different concurrency model than the batch stages:

- **Long-running stages** (`transcribe` / `aggregate` / `extract_frames_batch`)
  hold heavy resources (GPU/CPU + state.jsonl writes + atomic JSON writes
  on multi-segment loops). Two of these on the same slug WILL torn-write
  artifacts.
- **`extract_frames`** runs ffmpeg on ONE start/end window with one fps.
  Output filenames are namespaced by `seg_<start>_<index>.jpg` so two parallel
  invocations on disjoint windows produce non-overlapping files. A user
  legitimately runs `extract_frames` in parallel with a batch run to test fps
  parameters before committing to the schedule. Locking it would force the
  user to wait an hour for batch to finish before fixing a single segment.

Per CONTEXT integration_points list — only `cmd_transcribe / cmd_extract_frames_batch / cmd_aggregate` are in scope.

## Decision support / diagnostic helpers also intentionally unlocked

`cmd_diarize`, `cmd_detect_silence`, `cmd_detect_scenes`, `cmd_doctor`,
`cmd_download`, `cmd_ingest` — short-lived or already idempotent. Not in PARA-02 scope.

## Stale-PID detection edge cases

`_pid_alive(pid)` uses `os.kill(pid, 0)` (signal 0 is a no-op probe — works
on both Windows and POSIX since Python 3.2):

| Case | Outcome | Rationale |
|------|---------|-----------|
| `pid <= 0` | not alive | PID 0 = kernel scheduler on POSIX (not userspace); negative is nonsense |
| `os.kill(pid, 0)` succeeds | alive | Process exists and we have permission |
| `ProcessLookupError` | not alive | No process with this PID |
| `PermissionError` | **alive** (treated as such) | Process exists but isn't ours — we can't signal it but it IS running |
| `OSError` (other) | not alive | Conservative — defaults to "let new process take over" |

The `PermissionError = alive` case prevents a stale takeover when another
user owns the lock holder. In a single-user local tool (PROJECT.md OOS row 4)
this is rare but defensively handled.

## Windows-specific implementation note: sentinel-byte locking

`msvcrt.locking` is **mandatory** (not advisory like POSIX `fcntl.flock`).
Locking byte 0 would block all readers — including our own `_read_holder`
diagnostic and any external observer trying to peek at the lock file.

Solution: lock 1 sentinel byte at offset `0x7FFF_FFFE` (~2GB), which is far
beyond the actual JSON content (~80 bytes). The lock claim survives even when
the file is truncated to 0 (we truncate before writing the holder JSON), and
content reads at offset 0 are unaffected. Pattern borrowed from `py-filelock`
/ `portalocker`.

`fcntl.flock` on POSIX is advisory and locks the inode regardless of
position, so the sentinel offset is irrelevant there.

## Backward-compat (D-29 spirit applied to v1.0 baseline)

Single-terminal mode (one process at a time) acquires + releases the lock
transparently. 17 archived re-runs see no behavioral change other than the
`.resume.lock` file appearing/disappearing in `output/<slug>/`. Verified:

- All 71 existing tests in tests/ (test_state, test_silence,
  test_extract_frames_batch, test_scheduler, test_scenes,
  test_repetition_guard) pass after the FileLock integration.
- All 6 CLI commands (`download`, `ingest`, `transcribe`, `aggregate`,
  `extract_frames_batch`, `extract_frames`) expose `--help` and exit 0.

## Two-terminal manual smoke (documented for plan 06-02 docs section)

Per CONTEXT D-Testing line 67 — concurrency real-world smoke is documented but
NOT asserted in CI because spawning 2 subprocesses with timing is flaky.

**Same-slug contention (expected: B fails fast):**

Terminal A:
```bash
python -m agent.tools transcribe output/BV132wizyEEB/video.mp4 --out output/BV132wizyEEB
```

Terminal B (within ~3s of A starting):
```bash
python -m agent.tools transcribe output/BV132wizyEEB/video.mp4 --out output/BV132wizyEEB
```

Expected B output:
```
agent._lock.LockContended: FileLock: output/BV132wizyEEB/.resume.lock held by PID <A's PID> since <ISO timestamp> (msvcrt: ...)
```
Terminal A continues unaffected; B exits with traceback.

**Different-slug parallelism (expected: both succeed):**

Terminal A: `transcribe output/BV132wizyEEB/...`
Terminal B: `transcribe output/BV1C9QCBdE1U/...`

Both run concurrently, no contention, no artifact corruption. Per-slug isolation works.

**Vendor config.yaml race (expected: serialized + clean yaml after):**

Two simultaneous `download <douyin-url>` calls on different slugs both
patch `vendor/douyin_api/.../config.yaml`. The lock at
`vendor/douyin_api/.../crawlers/douyin/web/.config.yaml.lock` serializes
the two writes. The yaml stays valid (no half-written torn state).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Windows msvcrt.locking on byte 0 blocks readers**

- **Found during:** Task 1 smoke test (after writing initial `_try_acquire_once`)
- **Issue:** Plan's test_A locks byte 0 of the file, then calls
  `p.read_text(encoding="utf-8")` while holding the lock. On Windows
  `msvcrt.locking` is mandatory (not advisory like POSIX `fcntl`), so byte 0
  is unreadable from any handle while held — the read raises
  `PermissionError: [Errno 13]`. As-written, test_A could never pass on Windows.
- **Fix:** Lock 1 sentinel byte at offset `0x7FFF_FFFE` (high offset, ~2GB)
  instead of byte 0. JSON content at byte 0 stays freely readable from other
  handles. Pattern borrowed from `py-filelock` / `portalocker`. Also requires
  `release()` to seek to the same offset before unlocking. Documented inline
  with `_WIN_LOCK_OFFSET` class constant + comment.
- **Files modified:** `agent/_lock.py` (added `_WIN_LOCK_OFFSET`, updated
  `_try_acquire_once` Windows branch to seek + lock at high offset, updated
  `release()` Windows branch to seek + unlock at high offset)
- **Commit:** 623b860
- **Verification:** Smoke test (4 cases) passes on Windows; test_A green.

### Auth Gates

None — Phase 6 plan 01 is pure-stdlib infrastructure; no external API,
secrets, or network calls.

## Threat Flags

None — no new network endpoints, no new auth paths, no schema changes at
trust boundaries. The `.resume.lock` and `.config.yaml.lock` files contain
local-host metadata only (PID + ISO timestamp), accepted per
T-06-01-06 (PROJECT.md OOS row 4 "single-user local tool").

## Self-Check: PASSED

**Files exist:**
- `agent/_lock.py` — FOUND (243 lines, ≥60 ✓)
- `tests/test_lock.py` — FOUND (253 lines, ≥100 ✓)
- `agent/tools.py` — MODIFIED (module-level FileLock import + 3 cmd wraps)
- `agent/douyin_downloader.py` — MODIFIED (vendor config.yaml lock wrap)

**Commits exist:**
- `623b860` — FOUND (feat(06-01): add cross-platform FileLock primitive)
- `9084388` — FOUND (feat(06-01): wire FileLock into vendor config + 3 per-slug stages)
- `fc175fa` — FOUND (test(06-01): add 9 unittest cases for FileLock primitive + integration)

**Acceptance criteria from PLAN.md success_criteria:**
- [x] `agent/_lock.py` exists, ≥60 LOC (243 actual), exports FileLock + LockContended, stdlib-only
- [x] Stale-PID detection via `os.kill(pid, 0)` works (test_C passes)
- [x] Vendor config.yaml lock wrap at `agent/douyin_downloader.py` line 158-167
- [x] Per-slug resume.lock wrap on cmd_transcribe + cmd_aggregate + cmd_extract_frames_batch
- [x] cmd_extract_frames intentionally NOT locked (`grep -c FileLock agent/tools.py` = 4)
- [x] `tests/test_lock.py` ≥8 tests (9 actual), all pass on host OS (1 skipped on Windows is platform-correct)
- [x] No regression in existing tests (test_state, test_silence + 71 others — all pass)
- [x] All 6 CLI commands expose `--help` and exit 0
