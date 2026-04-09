"""yt-dlp 下载封装. 优先抓字幕, 同时拿元数据."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import yt_dlp

log = logging.getLogger(__name__)


def download(url: str, out_dir: str | Path, skip_if_cached: bool = True) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_cache = out_dir / "meta.json"
    if skip_if_cached and meta_cache.exists():
        meta = json.loads(meta_cache.read_text(encoding="utf-8"))
        if meta.get("video_path") and Path(meta["video_path"]).exists():
            log.info("缓存命中, 跳过下载: %s", meta["video_path"])
            return meta

    sessdata = os.getenv("BILIBILI_SESSDATA", "").strip()
    cookies_path = None
    if sessdata:
        cookies_path = out_dir / "cookies.txt"
        cookies_path.write_text(
            "# Netscape HTTP Cookie File\n"
            f".bilibili.com\tTRUE\t/\tFALSE\t0\tSESSDATA\t{sessdata}\n",
            encoding="utf-8",
        )

    opts = {
        "format": "bv*[height<=720]+ba/b[height<=720]/best",
        "outtmpl": str(out_dir / "video.%(ext)s"),
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["zh-CN", "zh", "en"],
        "subtitlesformat": "vtt",
        "writeinfojson": True,
        "quiet": False,
        "no_warnings": False,
    }
    if cookies_path:
        opts["cookiefile"] = str(cookies_path)

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    # 找到下载后的视频文件
    video_file = None
    for ext in ("mp4", "mkv", "webm", "flv"):
        candidate = out_dir / f"video.{ext}"
        if candidate.exists():
            video_file = candidate
            break

    sub_file = None
    for f in out_dir.glob("video.*.vtt"):
        sub_file = f
        break

    meta = {
        "video_path": str(video_file) if video_file else None,
        "subtitle_path": str(sub_file) if sub_file else None,
        "title": info.get("title", ""),
        "uploader": info.get("uploader", ""),
        "duration": info.get("duration", 0),
        "description": info.get("description", "")[:500],
        "url": url,
    }
    meta_cache.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    return meta
