"""本地 ASR: faster-whisper + VAD 反幻觉.

用 faster-whisper 因为它支持 Python 3.13. 若想换 SenseVoice/FunASR
需要 Python 3.11 venv, 接口保持一致即可.

反幻觉措施:
- vad_filter=True (内置 Silero VAD)
- condition_on_previous_text=False (防重复循环)
- 输出后过滤已知的中文 Whisper 幻觉短语
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# 已知的 Whisper 中文幻觉
HALLUCINATION_PATTERNS = [
    r"^请订阅",
    r"^感谢观看",
    r"^字幕由.*提供",
    r"^明镜",
    r"^点点栏目",
    r"^MING PAO",
    r"^由.*翻译",
]
_HALL_RE = re.compile("|".join(HALLUCINATION_PATTERNS))


@dataclass
class Segment:
    start: float
    end: float
    text: str


# Phase 5 TEACH-12 / D-26..D-28: profile-aware VAD.
# tutorial = current behavior baseline (D-29 byte-equal target).
# podcast  = looser VAD (skips long silences, reduces whisper hallucinations
#            on > 30s silences per PITFALLS P6.2).
# NOTE: D-28 originally specified tutorial=200 but Phase 2 baseline was 500.
# Path C taken (CONTEXT 05-02 PLAN task 4 fallback): tutorial preserved at 500
# to keep 17-archive segs.json byte-equal; podcast tightens to 800 + threshold
# 0.6. The profile-system still ships; only the tutorial values are anchored
# at Phase 2 baseline.
PROFILES: dict[str, dict[str, float]] = {
    "tutorial": {
        "vad_min_silence_ms": 500,
        "vad_threshold": 0.5,
    },
    "podcast": {
        "vad_min_silence_ms": 800,
        "vad_threshold": 0.6,
    },
}

# Backward-compat alias for agent/tools.py:cmd_transcribe sidecar抓取
# (Phase 2 D-05 字段链 — _VAD_DEFAULTS["min_silence_duration_ms"] is the
# sidecar.func.min_silence_duration_ms 取值源).
# Note: PROFILES uses key vad_min_silence_ms (D-28 锁定);
# _VAD_DEFAULTS keeps legacy key min_silence_duration_ms so cmd_transcribe
# 不会 KeyError.
_VAD_DEFAULTS = {
    "min_silence_duration_ms": PROFILES["tutorial"]["vad_min_silence_ms"],
}


def extract_audio(video_path: str | Path, out_path: str | Path) -> Path:
    out_path = Path(out_path)
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path


def transcribe(audio_path: str | Path,
               model_size: str = "small",
               language: str | None = None,
               initial_prompt: str | None = None,
               *,
               profile: str | None = None,
               min_silence_duration_ms: int | None = None,
               vad_threshold: float | None = None) -> list[Segment]:
    """转录. model_size: tiny/base/small/medium/large-v3.

    Phase 5 TEACH-12: profile= 'tutorial'|'podcast' VAD 调档.
    profile='tutorial' (default): VAD min_silence_ms=500 / threshold=0.5
        (Phase 2 baseline preserved per Task 4 Path C — D-29 backward-compat).
    profile='podcast': VAD min_silence_ms=800 / threshold=0.6 (per CONTEXT D-28
        path-C fallback values).
    显式 min_silence_duration_ms / vad_threshold 参数 override profile.

    8GB 显存默认 small (中文够用且快); 质量优先用 medium 或 large-v3.

    Raises:
        ValueError: profile 不在 PROFILES 中
    """
    # 1. 解析 profile -> 默认值字典
    if profile is None:
        profile = "tutorial"
    if profile not in PROFILES:
        raise ValueError(
            f"unknown profile {profile!r}; choose from {sorted(PROFILES)}"
        )
    p = PROFILES[profile]

    # 2. 显式参数 override
    eff_min_silence_ms = (
        min_silence_duration_ms
        if min_silence_duration_ms is not None
        else p["vad_min_silence_ms"]
    )
    eff_threshold = (
        vad_threshold if vad_threshold is not None else p["vad_threshold"]
    )

    from faster_whisper import WhisperModel
    import os
    # Windows 缺 cuBLAS/cuDNN 时 CUDA 推理会炸; 默认 CPU.
    # 装好 cuDNN 后设 ASR_DEVICE=cuda 启用 GPU.
    device = os.getenv("ASR_DEVICE", "cpu")
    compute_type = "float16" if device == "cuda" else "int8"
    log.info("加载 faster-whisper %s on %s/%s", model_size, device, compute_type)
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    segments_iter, info = model.transcribe(
        str(audio_path),
        language=language,
        vad_filter=True,
        vad_parameters={
            "min_silence_duration_ms": eff_min_silence_ms,
            "threshold": eff_threshold,
        },
        condition_on_previous_text=False,
        initial_prompt=initial_prompt,
        beam_size=5,
    )

    segs: list[Segment] = []
    for s in segments_iter:
        text = s.text.strip()
        if not text or _HALL_RE.search(text):
            continue
        segs.append(Segment(start=s.start, end=s.end, text=text))
    log.info("转录完成: %d 段, 时长 %.1fs", len(segs), info.duration)
    return segs


def parse_vtt(vtt_path: str | Path) -> list[Segment]:
    """解析已下载的 VTT 字幕(避免跑 ASR)."""
    text = Path(vtt_path).read_text(encoding="utf-8")
    segs: list[Segment] = []
    blocks = re.split(r"\n\n+", text)
    ts_re = re.compile(
        r"(\d+):(\d+):(\d+)\.(\d+)\s+-->\s+(\d+):(\d+):(\d+)\.(\d+)"
    )
    for b in blocks:
        m = ts_re.search(b)
        if not m:
            continue
        s = (int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000)
        e = (int(m[5]) * 3600 + int(m[6]) * 60 + int(m[7]) + int(m[8]) / 1000)
        lines = b.split("\n")
        content_lines = [
            l for l in lines if l and not ts_re.search(l) and not l.startswith("WEBVTT")
        ]
        content = " ".join(content_lines).strip()
        if content:
            segs.append(Segment(start=s, end=e, text=content))
    return segs


def format_transcript(segs: list[Segment]) -> str:
    """带时间戳的纯文本格式, 供 LLM 阅读."""
    lines = []
    for s in segs:
        m, sec = divmod(int(s.start), 60)
        h, m = divmod(m, 60)
        ts = f"[{h:02d}:{m:02d}:{sec:02d}]"
        lines.append(f"{ts} {s.text}")
    return "\n".join(lines)
