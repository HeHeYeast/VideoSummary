"""智能关键帧抽取: 候选帧 + 信息量打分 + top-K.

替代 v1 的 1fps + pHash + 均匀 cap.
核心改进: 按信息量降采样, 不是均匀降采样.

设计参考: AGENT_DESIGN.md §3.2
"""
from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import imagehash
import numpy as np
from PIL import Image

log = logging.getLogger(__name__)


@dataclass
class CandidateFrame:
    timestamp: float
    path: str
    phash: str = ""
    info_score: float = 0.0
    # 打分子项 (调试用)
    novelty_score: float = 0.0
    anchor_score: float = 0.0
    stability_score: float = 0.0


# ── 语音锚点关键词 (中英文) ──
VOICE_ANCHOR_PATTERNS = [
    # 英文
    r"look at this", r"this code", r"as you can see", r"on the screen",
    r"here we", r"right here", r"this part", r"this function",
    r"this variable", r"notice that", r"pay attention",
    # 中文
    r"看这", r"这段代码", r"如图", r"注意这", r"这个函数", r"这里我们",
    r"屏幕上", r"这个变量", r"这一步",
]
_ANCHOR_RE = re.compile("|".join(VOICE_ANCHOR_PATTERNS), re.IGNORECASE)


def extract_candidates(video_path: str | Path, out_dir: str | Path,
                       fps: float = 1.0) -> list[CandidateFrame]:
    """Step 1: 按固定 fps 抽帧, 生成候选池."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame_%06d.jpg")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"fps={fps},scale=854:-1",
        "-q:v", "4", pattern,
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    frames: list[CandidateFrame] = []
    files = sorted(out_dir.glob("frame_*.jpg"))
    for i, f in enumerate(files):
        ts = (i + 0.5) / fps
        frames.append(CandidateFrame(timestamp=ts, path=str(f)))
    log.info("候选帧: %d 张", len(frames))
    return frames


def compute_phash(frames: list[CandidateFrame]) -> None:
    """计算每帧的 pHash (in-place)."""
    for f in frames:
        try:
            h = imagehash.phash(Image.open(f.path))
            f.phash = str(h)
        except Exception as e:
            log.warning("pHash 失败 %s: %s", f.path, e)
            f.phash = ""


def score_novelty(frames: list[CandidateFrame], threshold: int = 8) -> None:
    """信号1: 相对前帧的新增内容 (pHash hamming distance).

    距离越大 = 画面变化越大 = 信息量越高.
    归一化到 0-10 分.
    """
    prev_hash = None
    for f in frames:
        if not f.phash:
            f.novelty_score = 5.0  # 无 hash 给中间分
            continue
        h = imagehash.hex_to_hash(f.phash)
        if prev_hash is None:
            f.novelty_score = 10.0  # 第一帧满分
        else:
            dist = h - prev_hash
            # hamming distance 0-64, 通常 <5 很相似, >15 很不同
            f.novelty_score = min(dist / 6.4, 10.0)
        prev_hash = h


def score_voice_anchors(frames: list[CandidateFrame],
                        segs: list[dict],
                        boost: float = 10.0) -> None:
    """信号2: 语音锚点加成.

    字幕里出现"看这张图/这段代码"等关键词时, 该时间点的帧 +boost 分.
    """
    # 找出所有锚点时间
    anchor_times: list[float] = []
    for seg in segs:
        if _ANCHOR_RE.search(seg.get("text", "")):
            anchor_times.append(seg["start"])

    if not anchor_times:
        return

    for f in frames:
        # 找最近的锚点
        min_dist = min(abs(f.timestamp - t) for t in anchor_times)
        if min_dist < 2.0:  # 2 秒以内算命中
            f.anchor_score = boost
        elif min_dist < 5.0:
            f.anchor_score = boost * 0.5


def score_stability(frames: list[CandidateFrame]) -> None:
    """信号3: 画面稳定度.

    通过和前后帧的 pHash 差异判断. 如果前后帧都和自己很像 = 静止画面 = 稳定.
    动态模糊/快速运动的帧扣分.
    归一化到 0-5 分 (稳定=满分, 不稳定=0).
    """
    hashes = []
    for f in frames:
        if f.phash:
            hashes.append(imagehash.hex_to_hash(f.phash))
        else:
            hashes.append(None)

    for i, f in enumerate(frames):
        if hashes[i] is None:
            f.stability_score = 2.5
            continue
        dists = []
        for di in [-1, 1]:
            j = i + di
            if 0 <= j < len(hashes) and hashes[j] is not None:
                dists.append(hashes[i] - hashes[j])
        if not dists:
            f.stability_score = 2.5
            continue
        avg_dist = sum(dists) / len(dists)
        # 低距离 = 稳定 = 高分; 高距离 = 不稳定 = 低分但不是0 (场景切换帧还是有价值)
        f.stability_score = max(0, 5.0 - avg_dist / 3.0)


def compute_info_scores(frames: list[CandidateFrame],
                        segs: list[dict]) -> None:
    """Step 2: 综合打分. 调用所有信号函数, 汇总 info_score."""
    compute_phash(frames)
    score_novelty(frames)
    score_voice_anchors(frames, segs)
    score_stability(frames)

    for f in frames:
        f.info_score = f.novelty_score + f.anchor_score + f.stability_score


def select_top_k(frames: list[CandidateFrame], cap: int,
                 min_interval: float = 3.0,
                 n_buckets: int = 6) -> list[CandidateFrame]:
    """Step 3: 按 info_score 降序选 top-K, 带时间均匀性约束.

    策略: 先按时间分成 n_buckets 个桶, 每个桶保底分配 cap//n_buckets 帧;
    剩余配额全局按 info_score 补充. 这样保证视频后半段不会零帧.
    """
    if not frames:
        return []
    # 时间分桶
    t_min = frames[0].timestamp
    t_max = frames[-1].timestamp
    if t_max <= t_min:
        t_max = t_min + 1
    bucket_size = (t_max - t_min) / n_buckets
    buckets: list[list[CandidateFrame]] = [[] for _ in range(n_buckets)]
    for f in frames:
        idx = min(int((f.timestamp - t_min) / bucket_size), n_buckets - 1)
        buckets[idx].append(f)

    # 每桶按 info_score 降序排
    for b in buckets:
        b.sort(key=lambda f: f.info_score, reverse=True)

    # Phase 1: 每桶保底分配
    per_bucket = max(cap // n_buckets, 1)
    selected: list[CandidateFrame] = []
    selected_set: set[float] = set()

    for b in buckets:
        count = 0
        for f in b:
            if count >= per_bucket:
                break
            if any(abs(f.timestamp - t) < min_interval for t in selected_set):
                continue
            selected.append(f)
            selected_set.add(f.timestamp)
            count += 1

    # Phase 2: 剩余配额全局按 info_score 补充
    remaining = cap - len(selected)
    if remaining > 0:
        all_sorted = sorted(frames, key=lambda f: f.info_score, reverse=True)
        for f in all_sorted:
            if remaining <= 0:
                break
            if f.timestamp in selected_set:
                continue
            if any(abs(f.timestamp - t) < min_interval for t in selected_set):
                continue
            selected.append(f)
            selected_set.add(f.timestamp)
            remaining -= 1

    selected.sort(key=lambda f: f.timestamp)
    log.info("top-K 选帧: %d 候选 → %d 入选 (cap=%d, %d buckets)",
             len(frames), len(selected), cap, n_buckets)
    return selected


def cleanup_unselected(all_frames: list[CandidateFrame],
                       selected: list[CandidateFrame]) -> None:
    """删除未入选的帧文件, 节省磁盘."""
    kept = {f.path for f in selected}
    for f in all_frames:
        if f.path not in kept:
            Path(f.path).unlink(missing_ok=True)


def extract_smart_keyframes(
    video_path: str | Path,
    out_dir: str | Path,
    segs: list[dict],
    cap: int = 25,
    fps: float = 1.0,
) -> list[CandidateFrame]:
    """主入口: 候选帧 → 打分 → top-K.

    Args:
        video_path: 视频文件路径
        out_dir: 帧输出目录
        segs: 字幕 segments (list of {start, end, text})
        cap: 最大帧数
        fps: 候选帧采样率

    Returns:
        选中的帧列表 (按时间排序)
    """
    candidates = extract_candidates(video_path, out_dir, fps=fps)
    compute_info_scores(candidates, segs)
    selected = select_top_k(candidates, cap)
    cleanup_unselected(candidates, selected)
    return selected
