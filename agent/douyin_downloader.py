"""抖音下载器: 基于 Evil0ctal/Douyin_TikTok_Download_API 的 a_bogus 签名算法.

yt-dlp 的抖音 extractor 长期 broken (需要 a_bogus 签名但 yt-dlp 没实现),
这个模块用 vendor/douyin_api 里的 crawler 绕开问题.

用法:
    from agent.douyin_downloader import download_douyin
    meta = download_douyin("https://v.douyin.com/xxx/", out_dir="output/xxx",
                          cookies_file="www.douyin.com_cookies.txt")
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import httpx

log = logging.getLogger(__name__)

# vendor 目录
_VENDOR = Path(__file__).parent.parent / "vendor" / "douyin_api"
_CONFIG = _VENDOR / "crawlers" / "douyin" / "web" / "config.yaml"


def _cookies_txt_to_header(cookies_file: str | Path) -> str:
    """从 netscape cookies.txt 构造 Cookie header 字符串."""
    lines = Path(cookies_file).read_text(encoding="utf-8").splitlines()
    pairs = []
    for line in lines:
        if line.startswith("#") or not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        domain, _, _, _, _, name, value = parts[:7]
        if "douyin" in domain.lower():
            pairs.append(f"{name}={value}")
    return "; ".join(pairs)


def _patch_config_cookie(cookie_header: str) -> None:
    """把 Cookie 写入 vendor 的 config.yaml.

    只替换 Cookie 一行, 保留其他配置不变.
    """
    content = _CONFIG.read_text(encoding="utf-8")
    # Cookie 行格式: "      Cookie: ..."
    new_content = re.sub(
        r"(^\s+Cookie:\s*).*$",
        lambda m: f"{m.group(1)}{cookie_header}",
        content,
        count=1,
        flags=re.MULTILINE,
    )
    _CONFIG.write_text(new_content, encoding="utf-8")
    log.info("已更新 %s 的 Cookie", _CONFIG)


def _extract_aweme_id(url: str) -> str | None:
    """从各种抖音 URL 中提取 aweme_id (视频 ID)."""
    # 已经是数字 ID
    if url.isdigit():
        return url
    # /video/{id}/
    m = re.search(r"/video/(\d+)", url)
    if m:
        return m.group(1)
    # 短链 v.douyin.com/xxx/ - 需要先 follow redirect
    if "v.douyin.com" in url or "iesdouyin.com" in url:
        try:
            resp = httpx.get(url, follow_redirects=True, timeout=10)
            return _extract_aweme_id(str(resp.url))
        except Exception as e:
            log.warning("解析短链失败: %s", e)
    return None


async def _fetch_video_detail(aweme_id: str) -> dict:
    """调用 vendor 的 DouyinWebCrawler 获取视频详情."""
    # 添加 vendor 到 sys.path
    if str(_VENDOR) not in sys.path:
        sys.path.insert(0, str(_VENDOR))

    # 延迟 import (在 sys.path 设置后)
    from crawlers.douyin.web.web_crawler import DouyinWebCrawler

    crawler = DouyinWebCrawler()
    return await crawler.fetch_one_video(aweme_id=aweme_id)


def _pick_download_url(detail: dict) -> tuple[str | None, dict]:
    """从详情响应中提取无水印视频直链.

    返回: (url, meta_dict)
    """
    aweme = (detail or {}).get("aweme_detail") or {}
    if not aweme:
        return None, {}

    # 视频 URL 优先级: video.play_addr.url_list[0] (无水印)
    video_obj = aweme.get("video") or {}
    play_addr = video_obj.get("play_addr") or {}
    url_list = play_addr.get("url_list") or []

    # url_list 通常有多个备用 CDN 链接
    video_url = None
    for u in url_list:
        if u and u.startswith("http"):
            video_url = u
            break

    # 元数据
    meta = {
        "title": (aweme.get("desc") or "")[:200],
        "uploader": ((aweme.get("author") or {}).get("nickname") or ""),
        "duration": (video_obj.get("duration") or 0) / 1000,  # ms → s
        "description": aweme.get("desc") or "",
        "aweme_id": aweme.get("aweme_id"),
    }
    return video_url, meta


def download_douyin(
    url: str,
    out_dir: str | Path,
    cookies_file: str | Path | None = None,
    skip_if_cached: bool = True,
) -> dict:
    """下载抖音视频.

    Args:
        url: 抖音视频 URL (支持短链 v.douyin.com/xxx 或 www.douyin.com/video/{id})
        out_dir: 输出目录
        cookies_file: 可选, cookies.txt 文件路径. 不传则用 vendor/config.yaml 里默认的
        skip_if_cached: 如果 meta.json 存在且视频文件存在, 跳过下载

    Returns:
        meta dict (video_path/title/duration/url/...)
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_cache = out_dir / "meta.json"
    if skip_if_cached and meta_cache.exists():
        meta = json.loads(meta_cache.read_text(encoding="utf-8"))
        if meta.get("video_path") and Path(meta["video_path"]).exists():
            log.info("缓存命中, 跳过下载: %s", meta["video_path"])
            return meta

    # 1. Patch cookies 到 vendor config (如果提供了文件)
    if cookies_file:
        cookie_header = _cookies_txt_to_header(cookies_file)
        if cookie_header:
            _patch_config_cookie(cookie_header)

    # 2. 解析 aweme_id
    log.info("解析 URL: %s", url)
    aweme_id = _extract_aweme_id(url)
    if not aweme_id:
        raise RuntimeError(f"无法从 URL 提取 aweme_id: {url}")
    log.info("aweme_id: %s", aweme_id)

    # 3. 调用 crawler 获取详情
    detail = asyncio.run(_fetch_video_detail(aweme_id))
    if not detail:
        raise RuntimeError("获取视频详情失败 (空响应)")

    # 4. 提取下载链接 + 元数据
    video_url, meta_extra = _pick_download_url(detail)
    if not video_url:
        raise RuntimeError(f"未能从响应中提取视频 URL. detail keys: {list(detail.keys())}")
    log.info("视频直链: %s", video_url[:100])
    log.info("标题: %s", meta_extra.get("title", "")[:80])

    # 5. 下载视频
    video_path = out_dir / "video.mp4"
    log.info("下载到: %s", video_path)
    with httpx.stream(
        "GET", video_url, follow_redirects=True, timeout=120,
        headers={
            "Referer": "https://www.douyin.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        },
    ) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(video_path, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 64):
                f.write(chunk)
                downloaded += len(chunk)
    log.info("下载完成: %d MB", downloaded // (1024 * 1024))

    # 6. 写 meta.json
    meta = {
        "video_path": str(video_path),
        "subtitle_path": None,
        "title": meta_extra["title"],
        "uploader": meta_extra["uploader"],
        "duration": meta_extra["duration"],
        "description": meta_extra["description"][:500],
        "url": url,
        "aweme_id": meta_extra["aweme_id"],
        "source": "douyin",
    }
    meta_cache.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


if __name__ == "__main__":
    # CLI 测试: python -m agent.douyin_downloader <url> <out_dir> [cookies_file]
    import sys as _sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    if len(_sys.argv) < 3:
        print("Usage: python -m agent.douyin_downloader <url> <out_dir> [cookies_file]")
        _sys.exit(1)
    cookies = _sys.argv[3] if len(_sys.argv) > 3 else None
    result = download_douyin(_sys.argv[1], _sys.argv[2], cookies_file=cookies)
    print(json.dumps(result, ensure_ascii=False, indent=2))
