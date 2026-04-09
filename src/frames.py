"""关键帧抽取: ffmpeg 1fps 抽帧 + pHash 去重 + 帧数硬上限.

为什么不用 ffmpeg scene detection: 调研发现它对 PPT/讲座类视频效果差.
1fps + pHash 是更鲁棒的选择.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image

log = logging.getLogger(__name__)


@dataclass
class Frame:
    timestamp: float
    path: str


def extract_frames_1fps(video_path: str | Path, out_dir: str | Path,
                        fps: float = 1.0) -> list[Frame]:
    """按固定 fps 抽帧."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame_%06d.jpg")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"fps={fps},scale=854:-1",
        "-q:v", "4", pattern,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    frames: list[Frame] = []
    files = sorted(out_dir.glob("frame_*.jpg"))
    for i, f in enumerate(files):
        ts = (i + 0.5) / fps  # 抽帧中点时间
        frames.append(Frame(timestamp=ts, path=str(f)))
    log.info("ffmpeg 抽帧: %d 张", len(frames))
    return frames


def dedupe_phash(frames: list[Frame], threshold: int = 5) -> list[Frame]:
    """pHash 去重: hamming 距离 <= threshold 视为相同帧."""
    kept: list[Frame] = []
    kept_hashes: list[imagehash.ImageHash] = []
    for f in frames:
        try:
            h = imagehash.phash(Image.open(f.path))
        except Exception as e:
            log.warning("hash 失败 %s: %s", f.path, e)
            continue
        if any(h - kh <= threshold for kh in kept_hashes):
            Path(f.path).unlink(missing_ok=True)  # 删去重后的冗余帧, 省磁盘
            continue
        kept.append(f)
        kept_hashes.append(h)
    log.info("pHash 去重: %d -> %d", len(frames), len(kept))
    return kept


def cap_frames(frames: list[Frame], cap: int) -> list[Frame]:
    """硬上限: 超过 cap 时按时间均匀降采样."""
    if len(frames) <= cap:
        return frames
    step = len(frames) / cap
    selected = [frames[int(i * step)] for i in range(cap)]
    # 删被裁掉的帧
    kept_paths = {f.path for f in selected}
    for f in frames:
        if f.path not in kept_paths:
            Path(f.path).unlink(missing_ok=True)
    log.info("帧数硬上限: %d -> %d", len(frames), len(selected))
    return selected


def extract_keyframes(video_path: str | Path, out_dir: str | Path,
                      cap: int, fps: float = 1.0) -> list[Frame]:
    """主入口: 1fps + pHash 去重 + 硬上限."""
    raw = extract_frames_1fps(video_path, out_dir, fps=fps)
    deduped = dedupe_phash(raw)
    capped = cap_frames(deduped, cap)
    return capped
