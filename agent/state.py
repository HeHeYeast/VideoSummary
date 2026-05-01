"""Append-only event log + pure event-sourcing reducer for output/<slug>/state.jsonl.

Phase 2 RES-05 / RES-06. Stage-level events only on day 1 (D-14); Phase 4
(extract_frames_batch) will add segment-level events without a schema bump.

Event schema (D-13):
    {"ts": <iso8601>, "stage": <str>, "status": "started|completed|failed",
     "params_hash": <str>, "details": {...optional}}

Corruption handling (D-03 / RESEARCH Pitfall 2):
- Any line that fails json.loads marks the file as corrupt for the rest of
  this Python process; subsequent read_events calls on the same path return
  ([], "corrupt") with no I/O and no warning. Caller (02-03 doctor / 02-01
  cmd_*) treats this as "degrade to file-existence cache" per RES-06.
- We NEVER auto-truncate, delete, or "repair" state.jsonl. Corruption is
  diagnostic information; the user's view of state.jsonl is what they wrote
  + whatever the kernel flushed before the crash.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from agent.io import now_iso

log = logging.getLogger(__name__)

# Process-lifetime suppression set for corrupt state.jsonl paths (D-03 / Pitfall 2).
# Resets between Python invocations; intentional -- a fresh process should warn
# once if the user hasn't fixed the corruption between runs.
_CORRUPT_PATHS: set[str] = set()


def params_hash(sidecar: dict) -> str:
    """sha256-prefix-16-hex of the (cli, func, tools) sub-dicts.

    Excludes captured_at (timestamp drift is normal) and schema_version
    (loader's job, not cache key). Uses sort_keys=True so dict insertion
    order does not affect the hash.

    Truncated to 16 hex chars (64 bits) -- sufficient for this scale (a slug
    typically accumulates <50 stage events ever; collision probability negligible).
    """
    payload = json.dumps(
        {
            "cli": sidecar.get("cli", {}),
            "func": sidecar.get("func", {}),
            "tools": sidecar.get("tools", {}),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def append_event(
    state_log: str | Path,
    *,
    stage: str,
    status: str,
    params_hash: str = "",
    details: dict | None = None,
) -> None:
    """Append one JSON line to state.jsonl (D-12).

    Best-effort: logs warning on OSError instead of raising. An event-log
    write failure MUST NOT break the pipeline (D-03 -- graceful degrade).

    status MUST be one of "started" | "completed" | "failed" but is not
    validated at runtime (caller's contract).
    """
    event: dict[str, Any] = {
        "ts": now_iso(),
        "stage": stage,
        "status": status,
        "params_hash": params_hash,
    }
    if details is not None:
        event["details"] = details

    log_path = Path(state_log)
    line = json.dumps(event, ensure_ascii=False) + "\n"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            # Belt-and-suspenders flush; no os.fsync (Phase 2 risk model is
            # "Defender briefly locks file", not power loss; fsync would add
            # 10-50ms per event for zero observable benefit).
    except OSError as e:
        log.warning("failed to append state event to %s: %s", log_path, e)


def read_events(state_log: str | Path) -> tuple[list[dict], str]:
    """Read all valid events from state.jsonl. Returns (events, status_str).

    status_str is one of:
        "ok"       -- file exists, all lines parse cleanly
        "missing"  -- file does not exist
        "corrupt"  -- at least one line failed json.loads (RESEARCH Pitfall 2)

    On corruption: returns the events parsed BEFORE the bad line, marks the
    path in _CORRUPT_PATHS, emits ONE warning. Subsequent calls within the
    same process return ([], "corrupt") with no I/O and no warning.
    """
    log_path = Path(state_log).resolve()
    key = str(log_path)
    if key in _CORRUPT_PATHS:
        return [], "corrupt"
    if not log_path.exists():
        return [], "missing"

    events: list[dict] = []
    status = "ok"
    raw = log_path.read_text(encoding="utf-8")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            status = "corrupt"
            break  # D-03: stop reading at first corruption; do not skip past
    if status == "corrupt":
        _CORRUPT_PATHS.add(key)
        log.warning(
            "state.jsonl corrupt at %s; degrading to file-existence cache "
            "for the rest of this session (no auto-repair)",
            log_path,
        )
    return events, status


def derived_state(events: list[dict]) -> dict[str, dict]:
    """Pure reducer: events -> {stage: {status, last_completed_at, params_hash}}.

    Phase 2 day-1 grain: stage-level only (D-14). Phase 4 will add segment
    events; the new "segments" key will be additive -- no schema bump.

    For each stage:
    - status: the most-recent event's status ("started" | "completed" | "failed")
    - last_completed_at: ts of the most-recent "completed" event (None if never completed)
    - params_hash: most-recent non-empty params_hash for that stage (carries forward
      so a "failed" event after a "completed" doesn't drop the hash)
    """
    state: dict[str, dict] = {}
    for ev in events:
        stage = ev.get("stage")
        if not stage:
            continue
        cur = state.setdefault(
            stage,
            {"status": None, "last_completed_at": None, "params_hash": None},
        )
        cur["status"] = ev.get("status")
        if ev.get("params_hash"):
            cur["params_hash"] = ev["params_hash"]
        if ev.get("status") == "completed":
            cur["last_completed_at"] = ev.get("ts")
    return state
