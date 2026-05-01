"""BilibiliSource: thin wrapper around src.download.download. Phase 3 SRC-01.

Per CONTEXT D-04: src/download.py is UNCHANGED. We delegate; we do not edit.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from agent.sources._common import append_phase3_fields


class BilibiliSource:
    name = "bilibili"
    # bilibili.com main + b23.tv short — per CONTEXT Discretion
    _PATTERN = re.compile(r"^https?://(?:www\.|m\.)?(?:bilibili\.com|b23\.tv)/", re.I)

    def match(self, url_or_path: str) -> bool:
        return bool(self._PATTERN.match(url_or_path))

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        # Add project root to sys.path so `from src.download import download` works
        # (existing pattern at agent/tools.py:85).
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from src.download import download
        legacy_meta = download(url_or_path, target_dir, skip_if_cached=skip_if_cached)
        # subtitle_origin detection deferred to 03-02 (YouTube does the heavy
        # lifting); Bilibili default = "none" because B站 yt-dlp returns danmaku
        # in `subtitles` which is comments not subs (RESEARCH §"Subtitle Origin Extraction").
        return append_phase3_fields(legacy_meta, source="bilibili", subtitle_origin="none")
