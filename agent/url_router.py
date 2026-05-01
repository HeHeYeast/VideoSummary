"""Pure-function URL/path router. Phase 3 SRC-02.

Imports SOURCES from agent.sources; returns the first source whose match()
accepts the input. Trivially testable: `route(url) is route(url)` (idempotent),
`route("https://www.douyin.com/...").name == "douyin"`, etc.
"""
from __future__ import annotations

from agent.sources import SOURCES, Source


def route(url_or_path: str) -> Source:
    """Return the first source whose match() accepts url_or_path.

    Raises:
        RuntimeError: if no source matches. Practically unreachable since
                      GenericSource is the catch-all sentinel, but defensive
                      in case SOURCES is mutated at runtime.
    """
    for source in SOURCES:
        if source.match(url_or_path):
            return source
    raise RuntimeError(f"No source matched: {url_or_path!r}")
