"""GenericSource: catch-all sentinel for any URL not matched by other sources.

Per CONTEXT D-03: match() always returns True; MUST be last in SOURCES list.
fetch() delegates to yt-dlp via src.download.download (the existing yt-dlp path).
"""
from __future__ import annotations

import sys
from pathlib import Path

from agent.sources._common import append_phase3_fields


class GenericSource:
    name = "generic"

    def match(self, url_or_path: str) -> bool:
        return True  # sentinel — must be last in SOURCES (asserted at import)

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.download import download
        legacy_meta = download(url_or_path, target_dir, skip_if_cached=skip_if_cached)
        return append_phase3_fields(legacy_meta, source="generic", subtitle_origin="none")
