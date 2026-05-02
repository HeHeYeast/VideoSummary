---
phase: 06-multi-agent-parallelism
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - agent/_lock.py
  - agent/tools.py
  - agent/sources/douyin.py
  - agent/sources/youtube.py
  - agent/douyin_downloader.py
findings:
  critical: 0
  warning: 3
  info: 4
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-02T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 6 introduces a stdlib-only cross-platform `FileLock` primitive plus three
points of integration: per-slug `.resume.lock` wrapping in `agent/tools.py`,
vendor `config.yaml` lock in `agent/douyin_downloader.py`, and an in-memory
cookies cache in the two source modules. The implementation is solid:
`msvcrt.locking` sentinel-byte trick correctly avoids the Windows mandatory-lock
gotcha for the JSON payload, stale-PID takeover is implemented, all file I/O is
explicit `encoding="utf-8"`, no new dependencies were added, and the 4 critical
CLAUDE.md sections were not touched. Backward-compat (D-29) is preserved:
single-terminal acquires + releases transparently, and the `_log` helper only
adds a prefix to NEW lines.

Three warnings worth addressing before merge: a re-entrant lock self-deadlock
risk if `cmd_ingest`'s douyin path ever overlaps with another wrapped command
(unlikely today but easy to introduce); the `cookies_file` legacy path bypasses
the new vendor-config lock in the direct-CLI invocation; and the
`_pid_alive(0)` POSIX semantics could occasionally take over a live "PID 0"
situation on Windows. Info items cover dead code and a small inconsistency.

No Phase 3-5 issues are re-flagged; only Phase 6 surface area is in scope.

## Warnings

### WR-01: Vendor config lock NOT held when called via legacy `cookies_file` CLI path

**File:** `agent/douyin_downloader.py:185-195`
**Issue:** The new lock around `_patch_config_cookie` is only acquired when
`cookies_raw` is non-None — which is always true for the `DouyinSource` happy
path. However, the direct module CLI (`python -m agent.douyin_downloader <url>
<dir> [cookies_file]` at line 252-261) passes `cookies_file=` only, and goes
through the `if cookies_raw is None and cookies_file: cookies_raw = ...read_text()`
branch at line 186-187 — that read happens OUTSIDE any FileLock. Two simultaneous
invocations of the CLI could still race on `_CONFIG.read_text` /
`_CONFIG.write_text`, since the lock at line 192-195 only covers the
`_patch_config_cookie` call AFTER cookies are read. The read of `cookies_file`
itself is fine (no shared mutable state), but if a developer later adds any
pre-processing that touches `_CONFIG` outside the lock window, this pattern will
not catch it.
**Severity rationale:** PITFALLS P8.1 explicitly names config.yaml corruption as
the threat model. Current code is technically safe today (`_CONFIG` is only
touched inside `_patch_config_cookie`), but the lock scope is narrower than the
comment at line 181-184 suggests, and the gap is invisible without re-reading
the function carefully.
**Fix:** Move the lock acquisition up to enclose the entire cookie-handling
block, OR add a comment at line 186 noting "no _CONFIG access here, lock
intentionally deferred":
```python
if cookies_raw:
    cookie_header = _cookies_text_to_header(cookies_raw)
    if cookie_header:
        from agent._lock import FileLock
        lock_path = _CONFIG.parent / ".config.yaml.lock"
        # Lock covers ONLY _patch_config_cookie (the only _CONFIG mutator).
        # cookies_text -> header conversion is pure / no shared state.
        with FileLock(lock_path, timeout=0):
            _patch_config_cookie(cookie_header)
```

### WR-02: `_pid_alive(0)` returns False but Windows has no PID 0 — minor portability gap

**File:** `agent/_lock.py:64-65`
**Issue:** The early-return `if pid <= 0: return False` is correct on POSIX
(PID 0 is the swapper, never a user process). On Windows, `os.kill(0, 0)`
behaviour is undefined and `pid <= 0` is the right defensive guard. However, if
a corrupt holder JSON deserializes to `{"pid": 0, "ts": ...}` or
`{"pid": -1, ...}`, `_pid_alive` returns False → stale-PID takeover is
triggered. That's probably the right call (zero / negative PIDs are
nonsense), but the log message at line 152 will report `holder PID 0 dead`
which is misleading — PID 0 was never alive in the first place. This is a
log-quality bug, not a correctness bug.
**Fix:** Distinguish "no valid holder PID" from "stale dead PID" in the log:
```python
holder_pid, holder_ts = _read_holder(self.path)
if holder_pid <= 0:
    log.info("FileLock: corrupt or empty holder JSON at %s; taking over", self.path)
elif not _pid_alive(holder_pid):
    log.info("FileLock: stale lock at %s (holder PID %d dead since %s); taking over",
             self.path, holder_pid, holder_ts or "<unknown>")
```

### WR-03: `cmd_ingest` douyin path is NOT wrapped in `.resume.lock` — concurrent `ingest` can race

**File:** `agent/tools.py:125-221` (`cmd_ingest`); `agent/douyin_downloader.py:170-249`
**Issue:** Per the Phase 6 plan (`06-CONTEXT.md:34`), the per-slug
`.resume.lock` is documented as wrapping `transcribe / extract_frames_batch /
aggregate`. `cmd_ingest` is intentionally NOT wrapped, but it does
`work_dir.mkdir`, then atomically rewrites `output/<slug>/meta.json` and
appends to `output/<slug>/state.jsonl`. Two concurrent `python -m agent.tools
ingest <same-url> --out output/<same-slug>` calls would race on:
  - `meta.json` rewrite (atomic temp+rename → safe)
  - `state.jsonl` append (best-effort, append_event handles concurrent writes
    via `O_APPEND` per Phase 2)
  - `video.mp4` download (download_douyin's `httpx.stream` would race; second
    one overwrites first; both write to same `out_dir / "video.mp4"`)

Today this is "accepted risk" per the Phase 6 plan (locks only on the 3 specified
commands), but there's no defensive comment in `cmd_ingest` documenting the
deliberate omission. Future maintainers may not realize ingest was excluded by
design. Additionally, the douyin path's vendor config.yaml lock IS held during
download — that lock is global (per-process file path), not per-slug, so
concurrent ingests of DIFFERENT douyin slugs would serialize on the
config.yaml lock. That's correct but underdocumented.
**Severity rationale:** Documented gap, not a regression. CONTEXT D-29 only
covers single-terminal byte-equality.
**Fix:** Add a one-line comment at the top of `cmd_ingest` noting the lock
omission is deliberate:
```python
def cmd_ingest(args):
    """...
    NOTE (Phase 6 PARA-02): cmd_ingest is NOT wrapped in .resume.lock.
    Concurrent ingest of the same slug is a user-error case (the URL maps
    1:1 to a slug). Locks are scoped to transcribe/aggregate/extract_frames_batch
    where same-slug concurrency is the documented multi-terminal use case.
    Douyin-specific vendor config.yaml lock is held inside download_douyin.
    """
```

## Info

### IN-01: `_COOKIES_CACHE` in `agent/sources/youtube.py` is dead code

**File:** `agent/sources/youtube.py:46`
**Issue:** The module-level `_COOKIES_CACHE: dict[str, str] = {}` is declared
"for symmetry" with `agent/sources/douyin.py` but is never read or written
anywhere in `youtube.py`. Lines 41-46 explicitly document the rationale
("yt-dlp auto-discovers browser cookies"), but a future grep for
`_COOKIES_CACHE` would find a dead symbol. Either delete it or add a sentinel
test asserting the intentional emptiness.
**Fix:** Either remove the unused dict, OR convert the placeholder into a
docstring-only note (no actual variable) so static analyzers don't flag it.

### IN-02: `_read_cookies_cached` does not handle missing file

**File:** `agent/sources/douyin.py:26-43`
**Issue:** The docstring says "Raises: OSError: if file is unreadable on the
first uncached read." But the call site at line 69-75 already guards with
`Path(cookies_file).exists()` before invoking. The OSError catch at line 72
handles the inner `Path(cookies_path).read_text()` exception. This is fine,
but if `_read_cookies_cached` is ever called from a new site that does NOT
pre-check existence, the OSError will propagate. Consider whether the helper
should also tolerate missing files (return None or empty string), or whether
the contract should require existence.
**Fix:** Document the contract more explicitly, or catch FileNotFoundError
inside the helper and return `""`:
```python
def _read_cookies_cached(cookies_path, *, reload=False):
    """...
    Caller MUST verify Path(cookies_path).exists() before calling.
    OSError (incl. FileNotFoundError) propagates to caller.
    """
```

### IN-03: `_log` helper bypasses logging — no level filter, no test capture

**File:** `agent/tools.py:48-64`
**Issue:** `_log` uses `print()` directly (intentional, per docstring — to
avoid the `INFO | ...` log format). However, this means:
  - Pytest `caplog` fixture cannot capture these lines (test_lock.py:H suite
    doesn't try, so OK today).
  - There's no way to suppress these lines in CI/quiet mode (no `--quiet` flag).
  - The `[<slug>] <cmd>: ...` prefix is not greppable through the existing
    `INFO | ...` format used elsewhere in the same module.

This is a deliberate design choice per CONTEXT line 39-40, but mixing `print`
and `log.info` in the same module makes log output for a single command
appear in two distinct formats. Acceptable for v1 multi-terminal use case but
worth flagging.
**Fix:** No change needed; just be aware that `_log` is a separate channel
from the logging module. If future quiet mode is needed, route `_log` through
`logging.getLogger("user_visible")` with a custom format.

### IN-04: `--reload-cookies` is plumbed only on download/ingest, not on transcribe/aggregate

**File:** `agent/tools.py:1212-1226` (CLI registration)
**Issue:** The `--reload-cookies` flag is only on `download` and `ingest`
subcommands, which makes sense — only those touch cookies. But the
`cmd_ingest` `getattr(args, 'reload_cookies', False)` defensive read at
line 173 will always succeed because of how argparse works (the flag is on
the subparser). The `getattr(...)` defensive pattern is harmless but signals
uncertainty about subparser behavior. Consider direct attribute access
(`args.reload_cookies`) since the subparser guarantees the attribute exists.
**Fix:** Replace `getattr(args, "reload_cookies", False)` with
`args.reload_cookies` to remove the dead-code defensive path.

---

_Reviewed: 2026-05-02T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
