---
phase: 06-multi-agent-parallelism
fixed_at: 2026-05-02T00:00:00Z
review_path: .planning/phases/06-multi-agent-parallelism/06-REVIEW.md
iteration: 1
findings_in_scope: 3
fixed: 3
skipped: 0
status: all_fixed
---

# Phase 6: Code Review Fix Report

**Fixed at:** 2026-05-02T00:00:00Z
**Source review:** .planning/phases/06-multi-agent-parallelism/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 3 (3 warnings, 0 critical, info excluded by scope)
- Fixed: 3
- Skipped: 0

All three Phase 6 review warnings fixed. None of the fixes change runtime
behavior — they are scope-tightening + log-quality + documentation-only edits.
D-29 backward-compat (single-terminal byte-equality) preserved: the lock
acquisition flow, takeover logic, and `cmd_ingest` dispatch are unchanged.

## Fixed Issues

### WR-01: Vendor config lock NOT held when called via legacy `cookies_file` CLI path

**Files modified:** `agent/douyin_downloader.py`
**Commit:** e0e6172
**Applied fix:** Per the user-supplied directive ("tighten the comment to
accurately reflect what the lock currently protects — only the
`_patch_config_cookie` call. Don't widen the lock window — current scope is
sufficient because no other writer mutates `_CONFIG`"), the comment block at
`douyin_downloader.py:180-201` is rewritten:
- Removed the misleading old line that said the lock covers the
  read-modify-write cycle (it doesn't — it only covers the writer).
- Added explicit note that the pre-conversion + `cookies_file` read sit
  outside the lock window because they don't touch `_CONFIG`.
- Added explicit "widen-on-new-writer" instruction for future maintainers
  so the narrow scope cannot silently become unsafe if someone adds a new
  `_CONFIG` mutator path.
- The lock window itself was NOT widened (per the directive); only the
  comment changed.

### WR-02: `_pid_alive(0)` returns False but Windows has no PID 0 — minor portability gap

**Files modified:** `agent/_lock.py`
**Commit:** 46fbf85
**Applied fix:** At `agent/_lock.py:148-164`, the previous single-branch
`if holder_pid > 0 and not _pid_alive(holder_pid):` was already silently
guarded against `pid <= 0`, but on the corrupt-JSON path `_read_holder`
returns `(0, "")` and the takeover proceeded silently with no log line.
Split it into two branches:
- `if holder_pid <= 0` → log
  `"FileLock: lock file at <path> corrupt or stale (no valid PID); taking over"`
  (per the user-supplied directive option "change message to 'lock file
  corrupt or stale (no valid PID)'").
- `elif not _pid_alive(holder_pid)` → existing
  `"stale lock at <path> (holder PID N dead since <ts>); taking over"`.
- Both branches still fall through to `open + lock`, so takeover semantics
  are unchanged. No misleading "PID 0 dead" log can be produced.

### WR-03: `cmd_ingest` douyin path is NOT wrapped in `.resume.lock` — concurrent `ingest` can race

**Files modified:** `agent/tools.py`
**Commit:** d2a4fe3
**Applied fix:** Per the directive ("add a one-line inline comment in
cmd_ingest documenting why it's NOT wrapped"), added a `NOTE (Phase 6
PARA-02 / WR-03)` block to `cmd_ingest`'s docstring at `tools.py:136-142`
explaining:
- `cmd_ingest` is intentionally NOT wrapped in `.resume.lock` because it
  dispatches to per-source subprocess handlers (yt-dlp / vendor crawler /
  httpx).
- A wrap here would be too coarse OR duplicate the per-slug lock that
  downstream `cmd_transcribe` / `cmd_aggregate` / `cmd_extract_frames_batch`
  already acquire.
- Douyin's vendor `config.yaml` is still protected by a global `FileLock`
  inside `download_douyin` (PARA-02).
- No code change — documentation-only.

---

_Fixed: 2026-05-02T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
