"""v1.1 opt-in marker helpers (Phase 07 PRE-V11-01).

Per-slug `output/<slug>/.v11_features.json` marker controls all v1.1 code paths.
Archives without marker silently take v1.0 path (D-29 byte-equal preserved).

Schema (locked CONTEXT specifics):
    {"version": 1,
     "features_enabled": ["transcribe_lint", "mode_signals", ...],
     "marker_set_at": "<ISO-8601 UTC>"}

This module is import-light (only stdlib + agent.io) so it can be cheaply
imported by every cmd_* in agent/tools.py without import-cycle risk. It
deliberately does NOT reference any of Claude's decision artifacts —
K5 boundary is a hard invariant for this file (verified by negative grep
in 07-01-PLAN.md acceptance criteria).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from agent.io import write_json_atomic, now_iso

log = logging.getLogger(__name__)

MARKER_FILENAME = ".v11_features.json"

# Locked allowlist of feature flags. Phase 07 ships emitter-related flags;
# Phase 08/09 will add their own flags as they ship (e.g., trace_tokens, glossary,
# tldr, verifier). Keep this list as the single source of truth — downstream
# phases extend by appending here, never by inventing parallel allowlists.
V11_FEATURES = (
    # Phase 07 locked (DO NOT REMOVE — backward-compat with any code already
    # using these names; cross-referenced by CLAUDE.md line 1103 example marker):
    "transcribe_lint",        # CORR-01a — Phase 07
    "mode_signals",           # TOOL-A   — Phase 07
    "schedule_suggest",       # TOOL-B   — Phase 07
    "trace_tokens",           # CORR-02  — Phase 07 reservation (Phase 08 alias: inline_trace_tokens)
    "self_contained_header",  # TEACH-A2 — Phase 07 reservation
    "glossary",               # TEACH-A3 — Phase 07 reservation (Phase 08 alias: cross_slug_glossary)
    "tldr",                   # TEACH-B  — Phase 07 reservation (Phase 08 alias: tldr_speedrun)
    "verifier",               # CORR-03  — Phase 07 reservation
    # Phase 08 ADD (per 08-CONTEXT.md specifics — explicit names that the
    # CLAUDE.md prompt extensions reference verbatim. The Phase 07 short
    # names remain valid synonyms; both sets pass set_v11_marker validation):
    "inline_trace_tokens",    # CORR-02 explicit (synonym of "trace_tokens")
    "self_check_confidence",  # CORR-02 self-check pass produces summary footer [?] count
    "cross_slug_glossary",    # TEACH-A3 explicit (synonym of "glossary")
    "tldr_speedrun",          # TEACH-B  explicit (synonym of "tldr")
    "l2_l3_correction",       # CORR-01b/c — Claude reading transcribe_lint_warnings.json + writing plan.md "已自动修正的术语"
)
# Total: 8 Phase 07 + 5 NEW Phase 08 = 13 entries.
# self_contained_header from Phase 07 is reused, NOT duplicated.


def _marker_path(slug_dir) -> Path:
    return Path(slug_dir) / MARKER_FILENAME


def get_v11_marker(slug_dir) -> dict | None:
    """Read marker JSON. Returns dict on success, None on missing or corrupt.

    Corrupt-file returns None silently (NOT raise) — an archive directory might
    have a stray file from manual experimentation; we don't want a stale marker
    to crash the v1.0 silent path. A WARNING is logged so the issue is visible
    to anyone running with -v / debug logging.
    """
    p = _marker_path(slug_dir)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        log.warning("v11 marker at %s unreadable (%s); treating as missing", p, e)
        return None


def is_v11_enabled(slug_dir, feature: str | None = None) -> bool:
    """Return True iff this slug has opted into v1.1 features.

    If `feature` is given, also requires that specific feature to be in the
    `features_enabled` list. Used by downstream code:

        if is_v11_enabled(slug_dir, "transcribe_lint"):
            run new path
        else:
            v1.0 silent fallback (D-29)
    """
    obj = get_v11_marker(slug_dir)
    if obj is None:
        return False
    enabled = obj.get("features_enabled") or []
    if not isinstance(enabled, list) or len(enabled) == 0:
        return False
    if feature is None:
        return True
    return feature in enabled


def set_v11_marker(slug_dir, features: list[str]) -> None:
    """Write `.v11_features.json` with given feature list. Atomic.

    Validates each feature against V11_FEATURES allowlist BEFORE writing —
    if any feature is unknown, raises ValueError and the marker file is NOT
    created. Overwrites any existing marker on success (idempotent on same
    input modulo the marker_set_at timestamp).
    """
    unknown = [f for f in features if f not in V11_FEATURES]
    if unknown:
        raise ValueError(
            f"unknown v11 features: {unknown}; "
            f"allowed: {list(V11_FEATURES)}"
        )
    target = _marker_path(slug_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    obj = {
        "version": 1,
        "features_enabled": list(features),
        "marker_set_at": now_iso(),
    }
    write_json_atomic(target, obj)
