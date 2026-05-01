"""Pluggable ingest source registry. Phase 3 SRC-01/SRC-02.

Each source declares match(url_or_path) and fetch(url, target_dir). The router
walks SOURCES in declaration order; first match wins. GenericSource is the
catch-all sentinel and MUST stay last.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class Source(Protocol):
    """Ingest source: declares match predicate and fetch action."""

    name: str  # one of "bilibili" / "douyin" / "youtube" / "generic" / "local"

    def match(self, url_or_path: str) -> bool: ...

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        """Returns meta dict (caller writes via agent.io.write_json_atomic)."""


# Order matters — most-specific-first per CONTEXT D-02
# Plan 03-01 registers: Douyin, Bilibili, Generic.
# Plan 03-02 will append YouTubeSource (between Douyin and Bilibili — most-specific position).
# Plan 03-03 will append LocalSource (between Bilibili and Generic).
from agent.sources.douyin   import DouyinSource
from agent.sources.bilibili import BilibiliSource
from agent.sources.generic  import GenericSource

SOURCES: list[Source] = [
    DouyinSource(),
    BilibiliSource(),
    GenericSource(),  # MUST stay last — sentinel match() returns True
]

# Defensive load-time invariants per RESEARCH §"Defensive Ordering Assertion".
# Asserts are stripped by `python -O`; this is a development-time guardrail.
_SEEN_NAMES = [s.name for s in SOURCES]
assert SOURCES[-1].name == "generic", \
    f"GenericSource must be last in SOURCES (got {SOURCES[-1].name!r}); see CONTEXT D-02/D-03"
assert _SEEN_NAMES.count("generic") == 1, \
    "GenericSource must appear exactly once and only at the end"
assert "douyin" in _SEEN_NAMES, "DouyinSource missing from SOURCES"
assert _SEEN_NAMES.index("douyin") < _SEEN_NAMES.index("generic"), \
    "DouyinSource must come before GenericSource (douyin URLs would route to broken yt-dlp path)"
assert _SEEN_NAMES.index("bilibili") < _SEEN_NAMES.index("generic"), \
    "BilibiliSource must come before GenericSource"
del _SEEN_NAMES
