"""Cross-platform advisory file-lock helper for multi-terminal safety (Phase 6 PARA-01).

Stdlib-only — `msvcrt.locking` on Windows + `fcntl.flock` on POSIX.
NO new dependency (CONTEXT D — supersedes REQUIREMENTS.md PARA-01 'filelock>=3.16'
mention; rationale: 'Keep dependency surface at zero new packages, consistent
with Phase 4 silero-vad / Phase 5 pyannote opt-in pattern').

Design constraints:
  - timeout=0 default → fail-fast (Phase 6 K-spec: 'second invocation fails fast
    with clean message')
  - Lock file content = JSON {"pid": <int>, "ts": <iso8601>} so contention errors
    name WHO holds the lock + WHEN
  - Stale-PID takeover: if holder PID is dead (os.kill(pid, 0) raises OSError /
    ProcessLookupError), the new requester takes over — covers Claude Code crash
    mid-transcribe (CONTEXT D 'crash recovery' rationale)
  - NOT re-entrant: a single process attempting to acquire the same path twice
    via separate FileLock instances raises LockContended

Single-terminal mode (one process at a time) acquires + releases transparently —
17 archived re-runs produce byte-equal artifacts (D-29 spirit, v1.0 baseline).
"""
from __future__ import annotations

import json
import logging
import os
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Platform-conditional imports — each branch only loads what the current OS has.
_IS_WINDOWS = platform.system() == "Windows"
if _IS_WINDOWS:
    import msvcrt
else:
    import fcntl


class LockContended(RuntimeError):
    """Raised when a FileLock cannot be acquired within the timeout window."""


def _now_iso() -> str:
    """ISO 8601 with UTC tz (matches agent/io.now_iso shape — duplicated here
    to keep agent/_lock.py independent of agent.io's import chain)."""
    return datetime.now(timezone.utc).isoformat()


def _pid_alive(pid: int) -> bool:
    """Return True if a process with this PID currently exists.

    On POSIX: os.kill(pid, 0) — sends signal 0 (no-op probe). Raises OSError if
    no such process; raises PermissionError if the process exists but isn't ours.
    Both are conclusive: PermissionError means the process IS alive (we just
    can't signal it).

    On Windows: same os.kill API but signal 0 is implemented by checking the
    process handle. Returns True iff the process is alive.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # alive but owned by another user
    except OSError:
        return False


def _read_holder(lock_path: Path) -> tuple[int, str]:
    """Read the JSON {pid, ts} from an existing lock file.

    Returns (pid=0, ts="") if the file is missing, empty, or corrupt — caller
    treats either as 'no valid holder' and proceeds to acquire.
    """
    try:
        raw = lock_path.read_text(encoding="utf-8")
        obj = json.loads(raw) if raw.strip() else {}
        return int(obj.get("pid", 0)), str(obj.get("ts", ""))
    except (OSError, ValueError, TypeError):
        return 0, ""


class FileLock:
    """Advisory exclusive file lock.

    Usage:
        with FileLock(slug_dir / ".resume.lock"):
            ...do critical section...
        # released on context exit (incl. exception)

    Args:
        path: Lock file path. Parent dir must exist OR will be created.
        timeout: Seconds to wait for acquisition. 0 = immediate fail (default).
                 Positive value = poll every 0.1s up to timeout.

    Raises:
        LockContended: cannot acquire (with holder PID + ISO timestamp in msg).
    """

    _POLL_S = 0.1

    # Windows msvcrt.locking is a MANDATORY (kernel-enforced) lock; locking byte 0
    # would block all reads of the file content (incl. read_text from the same
    # process). Trick: lock a sentinel byte at a very high offset (beyond any
    # plausible JSON payload) so the lock blocks ONLY other lock attempts, not
    # readers of the JSON holder content. POSIX fcntl.flock is whole-file advisory
    # and unaffected by this offset; we still seek there for parity / clarity.
    _LOCK_OFFSET = 0x40000000  # 1 GiB — never reached by holder JSON
    _LOCK_NBYTES = 1

    def __init__(self, path: "str | Path", *, timeout: float = 0.0) -> None:
        self.path = Path(path)
        self.timeout = max(0.0, float(timeout))
        self._fh: Optional[object] = None  # file handle while held
        self._acquired: bool = False

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    def acquire(self) -> None:
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                self._try_acquire_once()
                return
            except LockContended:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(self._POLL_S)

    def _try_acquire_once(self) -> None:
        """One acquisition attempt. Raises LockContended on failure."""
        # 1. Stale-PID detection — if the lock file exists with a dead PID,
        #    overwrite content first so any race-loser sees our PID, not the dead one.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            holder_pid, holder_ts = _read_holder(self.path)
            if holder_pid > 0 and not _pid_alive(holder_pid):
                log.info(
                    "FileLock: stale lock at %s (holder PID %d dead since %s); taking over",
                    self.path, holder_pid, holder_ts or "<unknown>",
                )
                # Fall through to open + lock; holder content gets overwritten below.

        # 2. Open file in a+ — created if missing, kept open for OS-level lock.
        try:
            fh = open(self.path, "a+", encoding="utf-8")
        except OSError as e:
            raise LockContended(f"FileLock: cannot open {self.path}: {e}") from e

        # 3. Try non-blocking OS lock.
        if _IS_WINDOWS:
            # msvcrt.locking is MANDATORY (kernel-enforced) byte-range lock.
            # Locking byte 0 would block read_text() of holder JSON from any
            # process. Trick: seek to a high sentinel offset (1 GiB) and lock
            # 1 byte THERE. The JSON payload lives at offset 0 (well below
            # 1 GiB) and is freely readable. Other lock attempts hit the same
            # sentinel byte and contend correctly.
            fh.seek(self._LOCK_OFFSET)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, self._LOCK_NBYTES)
            except OSError as e:
                fh.close()
                holder_pid, holder_ts = _read_holder(self.path)
                raise LockContended(
                    f"FileLock: {self.path} held by PID {holder_pid or '<unknown>'} "
                    f"since {holder_ts or '<unknown>'} (msvcrt: {e})"
                ) from e
        else:
            # POSIX fcntl.flock is whole-file advisory; offset is irrelevant.
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as e:
                fh.close()
                holder_pid, holder_ts = _read_holder(self.path)
                raise LockContended(
                    f"FileLock: {self.path} held by PID {holder_pid or '<unknown>'} "
                    f"since {holder_ts or '<unknown>'} (fcntl: {e})"
                ) from e

        # 4. Write our content (PID + ISO timestamp). seek(0)+truncate replaces
        #    any stale holder JSON with ours. Best-effort flush; lock content is
        #    diagnostic (used only for error messages), not load-bearing.
        try:
            fh.seek(0)
            fh.truncate()
            fh.write(json.dumps({"pid": os.getpid(), "ts": _now_iso()}))
            fh.flush()
        except OSError as e:
            log.warning("FileLock: failed to write holder content to %s: %s", self.path, e)

        self._fh = fh
        self._acquired = True

    def release(self) -> None:
        if not self._acquired or self._fh is None:
            return
        try:
            if _IS_WINDOWS:
                # Mirror acquire's high sentinel offset.
                self._fh.seek(self._LOCK_OFFSET)
                try:
                    msvcrt.locking(
                        self._fh.fileno(), msvcrt.LK_UNLCK, self._LOCK_NBYTES
                    )
                except OSError as e:
                    log.warning("FileLock: msvcrt unlock failed on %s: %s", self.path, e)
            else:
                try:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                except OSError as e:
                    log.warning("FileLock: fcntl unlock failed on %s: %s", self.path, e)
        finally:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None
            self._acquired = False
            # We deliberately do NOT delete the lock file. Reasons:
            # (a) On Windows, deleting an open file is fragile.
            # (b) The lock file is diagnostic — leaving it shows last-known holder
            #     for post-mortem if a future process crashes.
            # (c) Stale-PID detection handles re-acquisition cleanly.
