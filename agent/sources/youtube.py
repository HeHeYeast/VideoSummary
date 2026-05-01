"""YouTubeSource: 2-second yt-dlp --simulate preflight + 5-class stderr classifier
+ HTTPS_PROXY forwarding + version-staleness warning + subtitle_origin detection.

Phase 3 SRC-05 / SRC-06 / SRC-07 / SRC-08 / SRC-13.

Phase 5 D-31 / WR-02: VTT lang priority zh-Hans > zh-Hant > zh > en (folded
from Phase 3 deferred WR-02 — fix isolated; podcast mode benefits per CONTEXT
D-32: when subtitle_origin == 'creator' AND mode == 'interview-distillation',
CLAUDE.md skeleton instructs Claude to trust VTT directly without ASR re-run).

Failure modes (ordered by classifier priority — see RESEARCH §"Ordering Rationale"):
  1. po_token_required — SABR rollout 2026; install Deno + yt-dlp-get-pot
  2. cookies_stale     — re-export YouTube cookies.txt
  3. yt_dlp_outdated   — `pip install -U yt-dlp`
  4. gfw_blocked       — set HTTPS_PROXY or fall back to local mp4 ingest
  5. other             — head-200-char stderr appended to generic hint

Each category raises RuntimeError(f"YouTube ingest failed [{category}]: {hint}")
so caller (cmd_ingest) can catch + decide. Per CONTEXT D-13 we do NOT auto-fall
back to LocalSource — Claude is the decider (PROJECT.md K5).

Note (RESEARCH Pitfall 4): on Windows, subprocess.run(timeout=2) wallclock
can extend to 8-15s due to `proc.kill()` not being SIGKILL. Acceptable —
timeout-classified-as-gfw_blocked still gives the user the right action.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from agent.sources._common import append_phase3_fields

log = logging.getLogger(__name__)

_PREFLIGHT_TIMEOUT_S = 2.0
_VERSION_DATE_RE = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})")

# 5 categories, ordered most-specific-first.
# CRITICAL ORDER (RESEARCH §"Ordering Rationale"):
#   po_token_required BEFORE cookies_stale (SABR videos co-emit both messages
#   but PO Token is the actionable cause)
#   gfw_blocked LAST among specific patterns (network errors are trailing symptoms)
_CATEGORY_PATTERNS = [
    ("po_token_required", re.compile(
        r"PO\s*Token|requires\s+PO\s*Token|missing\s+a\s+GVS\s+PO\s*Token|"
        r"SABR|Server-side\s+ad\s+breakdown|GVS\s+PO\s*Token", re.I)),
    ("cookies_stale", re.compile(
        r"Sign in to confirm|Login required|This video requires payment|"
        r"members[- ]only|HTTP Error 403", re.I)),
    ("yt_dlp_outdated", re.compile(
        r"Unable to extract.*signature|Failed to extract any player response|"
        r"unable to extract initial player response|"
        r"extractor\s+args.*not\s+recognized", re.I)),
    ("gfw_blocked", re.compile(
        r"Unable to download webpage|getaddrinfo failed|"
        r"Connection.*timed out|Network is unreachable|"
        r"Connection refused|connect timeout|TransportError|"
        r"handshake operation timed out|Remote end closed connection", re.I)),
]

# CONTEXT D-12 LOCKED hints — DO NOT paraphrase. Acceptance criteria grep -F
# byte-exact match these. Order is preserved for human readability only.
_HINTS = {
    "gfw_blocked":      "GFW 阻断；export HTTPS_PROXY=http://127.0.0.1:7890 后重试，或下载到本地后用 `ingest <local-path>`",
    "cookies_stale":    "Cookies 失效；浏览器登录 YouTube 后重新导出 cookies.txt",
    "po_token_required": "PO Token required；安装 Deno + `pip install yt-dlp-get-pot`，详见 CLAUDE.md",
    "yt_dlp_outdated":  "yt-dlp 版本过旧；`pip install -U yt-dlp` 后重试",
    "other":            "下载失败；详见 stderr 头 200 字符",
}


def _classify_stderr(stderr: str) -> str:
    """Return one of the 5 category names. Bias to 'other' if no specific pattern hits."""
    for cat, pat in _CATEGORY_PATTERNS:
        if pat.search(stderr):
            return cat
    return "other"


def _build_yt_dlp_argv(url: str, *, simulate: bool = False) -> list[str]:
    """Construct yt-dlp argv with proxy if configured. NEVER passes empty --proxy
    (RESEARCH Pitfall 3 — empty proxy yields misclassified gfw_blocked).
    """
    # HTTPS_PROXY > HTTP_PROXY > unset (D-14 priority)
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "").strip()
    cmd = ["yt-dlp", "--no-warnings", "--no-progress"]
    if simulate:
        cmd.append("--simulate")
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(url)
    return cmd


def _redacted_proxy_log() -> str | None:
    """Return 'host:port' (no creds) for log; None if no proxy. Threat T-03-02-01."""
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "").strip()
    if not proxy:
        return None
    try:
        u = urlparse(proxy)
        return f"{u.hostname}:{u.port}" if u.hostname else None
    except (ValueError, AttributeError):
        return None


def youtube_preflight(url: str, *, timeout_s: float = _PREFLIGHT_TIMEOUT_S) -> None:
    """2-second yt-dlp --simulate. On failure raise RuntimeError with classified hint.

    On success returns None.

    Note (RESEARCH Pitfall 4): on Windows, subprocess.run(timeout=2) wallclock
    can extend to 8-15s due to `proc.kill()` not being SIGKILL. Acceptable —
    timeout-classified-as-gfw_blocked still gives the user the right action.
    """
    cmd = _build_yt_dlp_argv(url, simulate=True)
    proxy_label = _redacted_proxy_log()
    log.info("yt-dlp preflight: simulate (proxy=%s)", proxy_label or "<none>")

    stderr = ""
    category = "other"
    try:
        subprocess.run(
            cmd, check=True, capture_output=True, text=True,
            encoding="utf-8", timeout=timeout_s, shell=False,
        )
        return  # exit 0 = preflight OK
    except subprocess.TimeoutExpired as e:
        # Pitfall 4: classify timeout as gfw_blocked (slow network = same answer)
        log.warning("yt-dlp --simulate exceeded %.1fs (timeout); classified as gfw_blocked",
                    timeout_s)
        category = "gfw_blocked"
        if e.stderr is not None:
            stderr = e.stderr if isinstance(e.stderr, str) else e.stderr.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        category = _classify_stderr(stderr)
    except FileNotFoundError:
        raise RuntimeError("yt-dlp not on PATH; pip install yt-dlp") from None

    hint = _HINTS[category]
    if category == "other":
        # D-12: append head-200 chars of stderr
        hint = f"{hint}: {stderr[:200].strip()}"
    raise RuntimeError(f"YouTube ingest failed [{category}]: {hint}")


def _yt_dlp_release_date():
    """Return date encoded in yt_dlp.__version__, or None if unparseable."""
    try:
        import yt_dlp
        v = getattr(getattr(yt_dlp, "version", None), "__version__", "") or getattr(yt_dlp, "__version__", "")
    except ImportError:
        return None
    m = _VERSION_DATE_RE.match(v)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def warn_if_yt_dlp_stale(threshold_days: int = 90) -> None:
    """SRC-07: log warning if yt-dlp older than 90 days. NEVER auto-update (D-15)."""
    rel = _yt_dlp_release_date()
    if rel is None:
        return
    age = max(0, (date.today() - rel).days)
    if age <= threshold_days:
        log.info("yt-dlp version: %s (%d days old)", rel.isoformat(), age)
        return
    log.warning(
        "yt-dlp version %s is %d days old; pip install -U yt-dlp recommended",
        rel.isoformat(), age,
    )


def _extract_youtube_id(url: str) -> str | None:
    """Extract 11-char YouTube video ID from common URL forms.

    Handles: youtube.com/watch?v=ID, youtu.be/ID, youtube.com/shorts/ID, youtube.com/embed/ID
    """
    pat = re.compile(
        r"(?:youtube\.com/watch\?(?:[^&]+&)*v=|youtu\.be/|youtube\.com/(?:shorts|embed)/)"
        r"([A-Za-z0-9_-]{11})"
    )
    m = pat.search(url)
    return m.group(1) if m else None


def _detect_subtitle_origin(info_dict: dict) -> str:
    """Return 'creator' / 'auto' / 'none' from yt-dlp info dict.

    Per RESEARCH §"Subtitle Origin Extraction": filter to text-bearing langs
    to skip B站-style 'danmaku' entries (which are comments, not subs).
    'asr' is set later by Phase 5 cmd_transcribe (D-10).
    """
    subs = info_dict.get("subtitles") or {}
    auto = info_dict.get("automatic_captions") or {}
    real_langs = {k for k in subs if k.lower() in {"zh", "zh-cn", "zh-hans", "zh-hant", "en", "ja", "ko"}}
    if real_langs:
        return "creator"
    if auto:
        return "auto"
    return "none"


class YouTubeSource:
    name = "youtube"
    # most-specific match — youtube.com / youtu.be (+ www. / m. / music. subdomain)
    _PATTERN = re.compile(
        r"^https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/", re.I
    )

    def match(self, url_or_path: str) -> bool:
        return bool(self._PATTERN.match(url_or_path))

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        """Preflight first; on success run yt-dlp Python API for actual download."""
        target_dir = Path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        meta_cache = target_dir / "meta.json"

        # Cache check (parity with src.download.download)
        if skip_if_cached and meta_cache.exists():
            from agent.io import load_meta
            try:
                cached = load_meta(meta_cache)
                if cached.get("video_path") and Path(cached["video_path"]).exists():
                    log.info("缓存命中, 跳过下载: %s", cached["video_path"])
                    return cached
            except (OSError, ValueError):
                pass  # fall through to fresh fetch

        # 1. Preflight (raises classified RuntimeError on failure)
        youtube_preflight(url_or_path)

        # 2. Actual download via yt-dlp Python API (NOT subprocess — we need info_dict)
        import yt_dlp
        proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "").strip() or None
        opts = {
            "format": "bv*[height<=720]+ba/b[height<=720]/best",
            "outtmpl": str(target_dir / "video.%(ext)s"),
            "writesubtitles": True,             # manual subs 优先
            "writeautomaticsub": True,          # auto-gen 兜底
            # Phase 5 D-31 / WR-02: 优先级 zh-Hans > zh-Hant > zh > en > manual-any > auto-any
            # yt-dlp 按 list 顺序匹配 manual; 若 manual 全无, 按相同顺序匹配 auto.
            # 'zh-CN' 是非标准 alias, 改为标准 BCP-47 'zh-Hans' (简体中文); 'zh-Hant' 是繁体.
            "subtitleslangs": ["zh-Hans", "zh-Hant", "zh", "en"],
            "subtitlesformat": "vtt",
            "writeinfojson": True,
            "quiet": False,
            "no_warnings": False,
        }
        if proxy:
            opts["proxy"] = proxy

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url_or_path, download=True)

        # 3. Locate downloaded files (mirrors src/download.py:67-77)
        video_file = None
        for ext in ("mp4", "mkv", "webm", "flv"):
            candidate = target_dir / f"video.{ext}"
            if candidate.exists():
                video_file = candidate
                break
        # D-31 explicit-priority loop: fs glob order (NTFS alphabetical) puts
        # 'video.en.vtt' before 'video.zh-Hans.vtt' — that reverses the lang
        # priority. Pick by exact name in priority order, fall back to sorted
        # glob for auto-caption variants (e.g. 'video.zh-Hans-orig.vtt').
        sub_file = None
        for lang in ("zh-Hans", "zh-Hant", "zh", "en"):
            candidate = target_dir / f"video.{lang}.vtt"
            if candidate.exists():
                sub_file = candidate
                break
        if sub_file is None:
            for f in sorted(target_dir.glob("video.*.vtt")):
                sub_file = f
                break

        # 4. Build legacy 7-key meta in canonical order (same shape as src/download.py)
        legacy_meta = {
            "video_path": str(video_file) if video_file else None,
            "subtitle_path": str(sub_file) if sub_file else None,
            "title": info.get("title", ""),
            "uploader": info.get("uploader", ""),
            "duration": info.get("duration", 0),
            "description": (info.get("description") or "")[:500],
            "url": url_or_path,
        }

        # 5. Append Phase 3 fields with youtube_id + detected subtitle_origin
        return append_phase3_fields(
            legacy_meta,
            source="youtube",
            subtitle_origin=_detect_subtitle_origin(info),
            youtube_id=_extract_youtube_id(url_or_path) or info.get("id"),
        )
