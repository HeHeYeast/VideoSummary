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
               language: str = "zh",
               initial_prompt: str | None = None) -> list[Segment]:
    """转录. model_size: tiny/base/small/medium/large-v3.

    8GB 显存默认 small (中文够用且快); 质量优先用 medium 或 large-v3.
    """
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
        vad_parameters={"min_silence_duration_ms": 500},
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
