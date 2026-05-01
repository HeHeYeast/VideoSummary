"""LocalSource: ingest a local mp4 by ASCII-safe slug + copy. Phase 3 SRC-09/SRC-10/SRC-12.

Per CONTEXT D-20: COPY (not symlink) — Windows symlink requires admin. Idempotent
via Phase 2 sidecar; first-run cost is one disk copy (30-500MB), subsequent runs
short-circuit on cache hit.

Per CONTEXT D-18: slug = `local_<8hex>_<ascii_stem(stem)>`. ascii_stem strips
non-[a-zA-Z0-9] from filename stem; takes first 8 chars; defaults to `unnamed`
on empty result.

Per CONTEXT D-17: match() rejects URLs (`://` present); requires media extension
+ `is_file()` check.
"""
from __future__ import annotations

import hashlib
import logging
import re
import shutil
from pathlib import Path

from agent.sources._common import append_phase3_fields

log = logging.getLogger(__name__)

_MEDIA_EXTS = {".mp4", ".mkv", ".webm", ".flv", ".mov"}


class LocalSource:
    name = "local"

    def match(self, url_or_path: str) -> bool:
        # D-17: reject URL schemes
        if "://" in url_or_path:
            return False
        try:
            p = Path(url_or_path)
        except (ValueError, OSError):
            return False
        return p.suffix.lower() in _MEDIA_EXTS and p.is_file()

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        src = Path(url_or_path).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        target_video = target_dir / "video.mp4"

        if skip_if_cached and target_video.exists():
            log.info("缓存命中, 跳过本地拷贝: %s", target_video)
        else:
            log.info("拷贝 %s -> %s", src, target_video)
            # D-20: shutil.copyfile (NOT shutil.copy / NOT os.symlink)
            shutil.copyfile(src, target_video)

        # Lock-step legacy 7-key order (Pattern 4)
        legacy_meta = {
            "video_path": str(target_video),
            "subtitle_path": None,
            "title": src.stem,         # may be CJK — used for display only
            "uploader": "",
            "duration": 0,             # ffprobe will populate via cmd_ingest re-write (informational)
            "description": "",
            "url": str(src),           # absolute path serves as 'url' for local
        }
        return append_phase3_fields(
            legacy_meta,
            source="local",
            subtitle_origin="none",  # local mp4 sub-stream extraction is OOS for Phase 3 (RESEARCH Open Q1)
        )


def make_local_slug(input_path: str) -> str:
    """D-18 LOCKED: local_<sha256(absolute_path)[:8]>_<ascii_stem(stem)>.

    ascii_stem: re.sub(r"[^a-zA-Z0-9]", "", stem)[:8] or "unnamed"

    Examples (RESEARCH §"Slug Normalization Edge Cases" — verified table):
        D:\\videos\\编程教程.mp4         -> local_<8hex>_unnamed
        D:\\videos\\tutorial_第一节.mp4  -> local_<8hex>_tutorial
        D:\\videos\\demo (1).mp4         -> local_<8hex>_demo1
        D:\\videos\\demo2024_final.mp4   -> local_<8hex>_demo2024
        D:\\videos\\---___.mp4           -> local_<8hex>_unnamed
    """
    src = Path(input_path).resolve()
    h = hashlib.sha256(str(src).encode("utf-8")).hexdigest()[:8]
    stem = src.stem
    ascii_part = re.sub(r"[^a-zA-Z0-9]", "", stem)[:8] or "unnamed"
    return f"local_{h}_{ascii_part}"
