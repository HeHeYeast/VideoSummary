"""DouyinSource: thin wrapper around agent.douyin_downloader. Phase 3 SRC-01.

Per CONTEXT D-04: agent/douyin_downloader.py is UNCHANGED. We delegate.

Regex covers the union of patterns in agent/douyin_downloader._extract_aweme_id
(douyin.com / iesdouyin.com / v.douyin.com short links) — RESEARCH Open Q4.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from agent.sources._common import append_phase3_fields

log = logging.getLogger(__name__)


class DouyinSource:
    name = "douyin"
    # Mirror _extract_aweme_id corpus exactly: douyin.com, iesdouyin.com, v.douyin.com
    _PATTERN = re.compile(
        r"^https?://(?:www\.|v\.|m\.)?(?:douyin\.com|iesdouyin\.com)/", re.I
    )

    def match(self, url_or_path: str) -> bool:
        return bool(self._PATTERN.match(url_or_path))

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        from agent.douyin_downloader import download_douyin
        # Cookies fall-back logic preserved from cmd_download (agent/tools.py:101-106).
        cookies_file = os.getenv(
            "DOUYIN_COOKIES_FILE",
            str(Path(__file__).parent.parent.parent / "www.douyin.com_cookies.txt"),
        )
        if not Path(cookies_file).exists():
            log.warning("抖音 cookies 文件不存在: %s (可能导致下载失败)", cookies_file)
            cookies_file = None  # download_douyin tolerates None
        legacy_meta = download_douyin(
            url_or_path, target_dir,
            cookies_file=cookies_file, skip_if_cached=skip_if_cached,
        )
        # download_douyin already writes "source": "douyin" + "aweme_id" into legacy_meta
        # (agent/douyin_downloader.py:212-213). Append subtitle_origin only;
        # if "source" already present, {**legacy_meta, "source": "douyin"} just
        # overwrites in place (preserving original key position).
        return append_phase3_fields(legacy_meta, source="douyin", subtitle_origin="none")
