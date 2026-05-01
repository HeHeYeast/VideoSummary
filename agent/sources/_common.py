"""Shared helpers for source classes. Phase 3 SRC-04 + SRC-11.

- append_phase3_fields: lock-step key-order builder (03-01)
- ffprobe_video: codec / container / audio / VFR detection (03-03)
- _detect_vfr: strict-fraction comparison (informational only — see RESEARCH Pitfall 1)
"""
from __future__ import annotations

import json
import logging
import subprocess
from fractions import Fraction
from pathlib import Path

log = logging.getLogger(__name__)

_FFPROBE_TIMEOUT_S = 5.0  # CONTEXT line 91 — Discretion; 5s comfortably exceeds local-disk read


def append_phase3_fields(legacy_meta: dict, *, source: str,
                         subtitle_origin: str = "none",
                         youtube_id: str | None = None) -> dict:
    """Append Phase 3 additive fields after legacy keys.

    Per RESEARCH §"Byte-Identical Regression Strategy": legacy 7 keys
    (or 9 for douyin) appear FIRST in their original order; new fields
    appear AT THE END. Uses {**a, ...} spread which preserves a's order
    (PEP 468 verified).

    Returns a NEW dict; does not mutate legacy_meta.

    NOTE: if legacy_meta already contains a key in the extras (e.g. douyin
    downloader writes "source": "douyin"), the {**a, **b} spread overwrites
    the value while preserving the ORIGINAL key position from legacy_meta.
    This is desired — keeps the douyin 9-key prefix shape stable.
    """
    extras: dict = {"source": source}
    if youtube_id is not None:
        extras["youtube_id"] = youtube_id
    extras["subtitle_origin"] = subtitle_origin
    return {**legacy_meta, **extras}


def _detect_vfr(r_rate: str | None, avg_rate: str | None) -> str:
    """Strict-fraction comparison per CONTEXT D-21 spec. Returns 'VFR'/'CFR'/'unknown'.

    Per RESEARCH Pitfall 1: this is INFORMATIONAL ONLY. The actionable response
    (`-vsync vfr` on extract_frames) is uniformly applied (D-23) regardless of
    detected mode, so misclassification (e.g., B站 archive with r=30/1 and
    avg=2221000/74033 differing by <1ppm) is harmless.

    DO NOT add a `if fps_mode == "VFR": log.warning(...)` line — the user has
    nothing to do about it; the remux suggestion is for HEVC/AV1 (D-22), not VFR.
    """
    if not r_rate or not avg_rate or "/" not in r_rate or "/" not in avg_rate:
        return "unknown"
    try:
        rf, af = Fraction(r_rate), Fraction(avg_rate)
    except (ValueError, ZeroDivisionError):
        return "unknown"
    if af == 0:
        return "unknown"
    return "VFR" if rf != af else "CFR"


def ffprobe_video(video_path: str | Path) -> dict:
    """Run ffprobe and return dict with codec / container / has_audio / fps_mode.

    Returns:
        {"codec": "h264", "container": "mov,mp4,m4a,3gp,3g2,mj2",
         "has_audio": True, "fps_mode": "CFR" | "VFR" | "unknown",
         "width": 1280, "height": 720, "duration_s": 74.033}

    Raises:
        RuntimeError: if no audio stream (D-21 — whisper cannot transcribe)
                      or no video stream
        subprocess.CalledProcessError: if ffprobe exits non-zero (e.g., corrupt file)
        subprocess.TimeoutExpired: if ffprobe hangs > 5s

    Side effects:
        Logs warning if codec is HEVC/AV1 (D-22 — not blocking; user can choose remux).
    """
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(video_path)],
        check=True, capture_output=True, text=True,
        encoding="utf-8", timeout=_FFPROBE_TIMEOUT_S, shell=False,
    )
    info = json.loads(result.stdout)
    streams = info.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not audio_streams:
        # D-21 LOCKED message
        raise RuntimeError(
            f"No audio stream in {video_path}; whisper cannot transcribe. "
            f"Remux with `ffmpeg -i in -c:v copy -c:a aac out.mp4`"
        )
    if not video_streams:
        raise RuntimeError(f"No video stream in {video_path}")

    v = video_streams[0]
    codec = (v.get("codec_name") or "unknown").lower()
    fps_mode = _detect_vfr(v.get("r_frame_rate"), v.get("avg_frame_rate"))

    # D-22: HEVC/AV1 warn-but-do-not-block
    if codec in {"hevc", "av1"}:
        log.warning(
            "Codec %s detected; if extract_frames runs slow, remux to h264 first: "
            "`ffmpeg -i in -c:v libx264 -c:a copy out.mp4`",
            codec,
        )

    duration_raw = info.get("format", {}).get("duration", 0)
    try:
        duration_s = float(duration_raw)
    except (TypeError, ValueError):
        duration_s = 0.0

    return {
        "codec": codec,
        "container": info.get("format", {}).get("format_name", "unknown"),
        "has_audio": True,
        "fps_mode": fps_mode,
        "width": v.get("width"),
        "height": v.get("height"),
        "duration_s": duration_s,
    }
