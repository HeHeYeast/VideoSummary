"""端到端编排."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from .asr import Segment, extract_audio, transcribe, parse_vtt
from .budget import BudgetGuard
from .download import download
from .frames import Frame, extract_keyframes
from .llm_client import make_client
from .summarize import generate_document
from .vision import FrameDescription, describe_frames

log = logging.getLogger(__name__)


def run(url: str, work_dir: str | Path, budget: BudgetGuard,
        whisper_size: str = "small",
        vision_model: str = "qwen3-vl-plus",
        outline_model: str = "gpt-4o-mini",
        writer_model: str = "deepseek-v3.2",
        polish_model: str = "gpt-4o-mini",
        skip_download: bool = False,
        test_duration: int = 0) -> str:
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    # 1. 下载 (缓存)
    log.info("=== Stage 1: 下载 ===")
    if skip_download and (work_dir / "meta.json").exists():
        meta = json.loads((work_dir / "meta.json").read_text(encoding="utf-8"))
        log.info("--skip-download, 用缓存 meta")
    else:
        meta = download(url, work_dir, skip_if_cached=True)
    if not meta["video_path"]:
        raise RuntimeError("下载失败")

    # 2. ASR (缓存)
    log.info("=== Stage 2: ASR ===")
    segs_cache = work_dir / "segs.json"
    if segs_cache.exists():
        log.info("缓存命中: %s", segs_cache.name)
        data = json.loads(segs_cache.read_text(encoding="utf-8"))
        segs = [Segment(**d) for d in data]
    else:
        if meta["subtitle_path"]:
            log.info("使用已下载字幕: %s", meta["subtitle_path"])
            segs = parse_vtt(meta["subtitle_path"])
        else:
            audio = work_dir / "audio.wav"
            extract_audio(meta["video_path"], audio)
            # language=None → whisper 自动检测, 避免强制 zh 对英文音频产生幻觉
            segs = transcribe(audio, model_size=whisper_size, language=None)
        segs_cache.write_text(
            json.dumps([asdict(s) for s in segs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 3. 抽帧 (缓存)
    log.info("=== Stage 3: 关键帧 ===")
    frames_dir = work_dir / "frames"
    frames_cache = work_dir / "frames.json"
    if frames_cache.exists() and frames_dir.exists():
        log.info("缓存命中: %s", frames_cache.name)
        data = json.loads(frames_cache.read_text(encoding="utf-8"))
        frames = [Frame(**d) for d in data if Path(d["path"]).exists()]
    else:
        frames = extract_keyframes(meta["video_path"], frames_dir, cap=budget.frame_cap)
        frames_cache.write_text(
            json.dumps([asdict(f) for f in frames], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 4. 视觉描述 (缓存)
    log.info("=== Stage 4: 视觉描述 ===")
    client = make_client(budget)
    frame_descs_cache = work_dir / "frame_descs.json"
    if frame_descs_cache.exists():
        log.info("缓存命中: %s", frame_descs_cache.name)
        data = json.loads(frame_descs_cache.read_text(encoding="utf-8"))
        frame_descs = [FrameDescription(**d) for d in data]
    else:
        frame_descs = describe_frames(frames, client, model=vision_model)
        frame_descs_cache.write_text(
            json.dumps([asdict(f) for f in frame_descs], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 4.5 test 模式按时间窗裁剪 segs/frames/frame_descs, 让有限预算能跑完整 pipeline
    if test_duration and test_duration > 0:
        orig_segs, orig_frames, orig_fd = len(segs), len(frames), len(frame_descs)
        segs = [s for s in segs if s.start < test_duration]
        frames = [f for f in frames if f.timestamp < test_duration]
        frame_descs = [f for f in frame_descs if f.timestamp < test_duration]
        log.info("test_duration=%ds: segs %d→%d, frames %d→%d, descs %d→%d",
                 test_duration, orig_segs, len(segs), orig_frames, len(frames),
                 orig_fd, len(frame_descs))
        # 同时把 meta.duration 截短, outline 才不会规划视频后半部分
        meta = {**meta, "duration": min(meta.get("duration", test_duration), test_duration)}

    # 5. v4 文档生成: outline → section → polish → assemble
    log.info("=== Stage 5: 文档生成 (v4) ===")
    final_md = generate_document(
        segs, frame_descs, meta, client,
        outline_model=outline_model,
        writer_model=writer_model,
        polish_model=polish_model,
        work_dir=work_dir,
    )

    # 6. 输出
    out_md = work_dir / "summary.md"
    out_md.write_text(final_md, encoding="utf-8")
    (work_dir / "budget_report.txt").write_text(budget.report(), encoding="utf-8")
    log.info("输出: %s", out_md)
    print(budget.report())
    return str(out_md)
