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


# Phase 6 PARA-05: lazy module-level cache. Process-local — each Claude Code
# terminal has its own Python process so no cross-process sync needed.
# Keyed by absolute resolved path; value is the raw cookies file text.
_COOKIES_CACHE: dict[str, str] = {}


def _read_cookies_cached(cookies_path: str | Path, *, reload: bool = False) -> str:
    """Read cookies file, caching by resolved absolute path.

    Args:
        cookies_path: path to cookies.txt
        reload: if True, bypass cache + re-read from disk + update cache entry.
                Use case: 'I just re-exported cookies, please pick them up'.

    Returns:
        Raw cookies file text (Netscape format).

    Raises:
        OSError: if file is unreadable on the first uncached read.
    """
    key = str(Path(cookies_path).resolve())
    if reload or key not in _COOKIES_CACHE:
        _COOKIES_CACHE[key] = Path(cookies_path).read_text(encoding="utf-8")
    return _COOKIES_CACHE[key]


class DouyinSource:
    name = "douyin"
    # Mirror _extract_aweme_id corpus exactly: douyin.com, iesdouyin.com, v.douyin.com
    _PATTERN = re.compile(
        r"^https?://(?:www\.|v\.|m\.)?(?:douyin\.com|iesdouyin\.com)/", re.I
    )

    def match(self, url_or_path: str) -> bool:
        return bool(self._PATTERN.match(url_or_path))

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True,
              reload_cookies: bool = False) -> dict:
        from agent.douyin_downloader import download_douyin
        # Cookies fall-back logic preserved from cmd_download (agent/tools.py:101-106).
        # Phase 6 PARA-05: read cookies through _read_cookies_cached so subsequent
        # invocations within the same Python process don't re-hit disk; pass the
        # pre-read text to download_douyin via cookies_text kwarg.
        cookies_file = os.getenv(
            "DOUYIN_COOKIES_FILE",
            str(Path(__file__).parent.parent.parent / "www.douyin.com_cookies.txt"),
        )
        cookies_text: str | None = None
        if Path(cookies_file).exists():
            try:
                cookies_text = _read_cookies_cached(cookies_file, reload=reload_cookies)
            except OSError as e:
                log.warning("抖音 cookies 读取失败: %s (%s); 继续无 cookie 下载",
                            cookies_file, e)
                cookies_text = None
        else:
            log.warning("抖音 cookies 文件不存在: %s (可能导致下载失败)", cookies_file)

        legacy_meta = download_douyin(
            url_or_path, target_dir,
            cookies_text=cookies_text, skip_if_cached=skip_if_cached,
        )
        # download_douyin already writes "source": "douyin" + "aweme_id" into legacy_meta
        # (agent/douyin_downloader.py:212-213). Append subtitle_origin only;
        # if "source" already present, {**legacy_meta, "source": "douyin"} just
        # overwrites in place (preserving original key position).
        return append_phase3_fields(legacy_meta, source="douyin", subtitle_origin="none")
