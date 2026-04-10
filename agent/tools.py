"""独立工具 CLI: 3 个核心命令 + 2 个可选命令, Claude Code 按需调用.

核心命令 (本地执行, ¥0):
  python -m agent.tools download <url> --out <dir>
  python -m agent.tools transcribe <video_path> --out <dir> [--whisper small]
  python -m agent.tools extract_frames <video_path> --out <dir> --fps 1 --start 0 --end 120

辅助命令 (本地, ¥0):
  python -m agent.tools aggregate <segs_json> --out <paragraphs_json>
  python -m agent.tools list_frames <dir>
  python -m agent.tools cleanup_frames <dir> --keep <f1.jpg> <f2.jpg> ...

帧理解/OCR 由 Claude Code 直接 Read 图片完成 (多模态, Max 计划 ¥0).
以下命令仅在 context 不够或需要批量预筛选时作为后备:
  python -m agent.tools classify_frame <frame_path> [--model qwen3-vl-plus]
  python -m agent.tools ocr_frame <frame_path> [--type code]
"""
from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def cmd_download(args):
    """下载 B 站视频."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.download import download
    work_dir = Path(args.out)
    work_dir.mkdir(parents=True, exist_ok=True)
    meta = download(args.url, work_dir, skip_if_cached=True)
    print(json.dumps(meta, ensure_ascii=False, indent=2))


def cmd_transcribe(args):
    """ASR 转录 (本地 faster-whisper)."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.asr import extract_audio, transcribe, Segment

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    audio = out_dir / "audio.wav"
    if not audio.exists():
        extract_audio(args.video_path, audio)

    segs_file = out_dir / "segs.json"
    if segs_file.exists() and not args.force:
        print(f"cached: {segs_file}")
        segs_data = json.loads(segs_file.read_text(encoding="utf-8"))
    else:
        segs = transcribe(audio, model_size=args.whisper, language=None)
        segs_data = [asdict(s) for s in segs]
        segs_file.write_text(json.dumps(segs_data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"segments: {len(segs_data)}")
    if segs_data:
        print(f"time: {segs_data[0]['start']:.1f}s - {segs_data[-1]['end']:.1f}s")
    print(f"output: {segs_file}")


def cmd_aggregate(args):
    """段落聚合."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.asr_v2 import aggregate_paragraphs, paragraphs_to_dicts

    segs = json.loads(Path(args.segs_json).read_text(encoding="utf-8"))
    paras = aggregate_paragraphs(segs, gap_threshold=args.gap)
    out = Path(args.out)
    out.write_text(json.dumps(paragraphs_to_dicts(paras), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(segs)} segments -> {len(paras)} paragraphs")
    print(f"output: {out}")


def cmd_extract_frames(args):
    """抽帧: ffmpeg 按指定参数提取. 参数由 Claude Code 根据视频内容决定."""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-y"]
    if args.start > 0:
        cmd += ["-ss", str(args.start)]
    cmd += ["-i", args.video_path]
    if args.end > 0:
        cmd += ["-t", str(args.end - max(args.start, 0))]

    prefix = f"seg_{int(args.start):04d}_"
    pattern = str(out_dir / f"{prefix}%06d.jpg")
    cmd += ["-vf", f"fps={args.fps},scale=854:-1", "-q:v", "4", pattern]

    subprocess.run(cmd, check=True, capture_output=True)

    files = sorted(out_dir.glob(f"{prefix}*.jpg"))
    print(f"extracted: {len(files)} frames ({args.start}s-{args.end}s, fps={args.fps})")
    for f in files[:5]:
        ts = args.start + (int(f.stem.split("_")[-1]) - 0.5) / args.fps
        print(f"  [{ts:.1f}s] {f.name}")
    if len(files) > 5:
        print(f"  ... and {len(files) - 5} more")


def cmd_list_frames(args):
    """列出帧文件."""
    d = Path(args.dir)
    files = sorted(d.glob("*.jpg"))
    print(f"{len(files)} frames in {d}")
    for f in files:
        print(f"  {f.name}")


def cmd_cleanup_frames(args):
    """删除未使用的帧, 只保留 --keep 列表中的."""
    d = Path(args.dir)
    keep = set(args.keep) if args.keep else set()
    removed = 0
    for f in sorted(d.glob("*.jpg")):
        if f.name not in keep:
            f.unlink()
            removed += 1
    print(f"removed {removed} frames, kept {len(keep)}")


def cmd_classify_frame(args):
    """[后备] 用 VE API 分类单帧. 通常不需要——Claude Code 直接看图更准."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    load_dotenv()
    from src.budget import BudgetGuard
    from src.llm_client import make_client
    from agent.pass1_classify import classify_frames

    budget = BudgetGuard(total_usd=0.01, stage_limits_usd={"vision": 0.01},
                         call_limits={"vision": 1}, max_tokens_per_call=200, frame_cap=1)
    client = make_client(budget)
    results = classify_frames(
        [{"frame_id": "single", "timestamp": 0, "path": args.frame_path}],
        client, model=args.model,
    )
    if results:
        r = results[0]
        print(f"type: {r.type}\nhas_text: {r.has_text}\nbrief: {r.brief}")


def cmd_ocr_frame(args):
    """[后备] 用 VE API OCR 单帧. 通常不需要——Claude Code 直接看图更准."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    load_dotenv()
    from src.budget import BudgetGuard
    from src.llm_client import make_client
    from agent.frame_store import DETAIL_PROMPTS

    budget = BudgetGuard(total_usd=0.02, stage_limits_usd={"vision": 0.02},
                         call_limits={"vision": 1}, max_tokens_per_call=600, frame_cap=1)
    client = make_client(budget)

    frame_type = args.type or "code"
    prompt = DETAIL_PROMPTS.get(frame_type, DETAIL_PROMPTS["_default"])
    result = client.vision(
        stage="vision", model=args.model, prompt=prompt,
        image_path=args.frame_path, group="cheap", max_tokens=500,
    )
    print(result.strip())


def main():
    load_dotenv()
    parser = argparse.ArgumentParser(prog="agent.tools", description="VideoSummary 工具集")
    sub = parser.add_subparsers(dest="command")

    # ── 核心命令 (本地, ¥0) ──
    p = sub.add_parser("download", help="下载视频")
    p.add_argument("url")
    p.add_argument("--out", required=True)

    p = sub.add_parser("transcribe", help="ASR 转录 (本地)")
    p.add_argument("video_path")
    p.add_argument("--out", required=True)
    p.add_argument("--whisper", default="small")
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("aggregate", help="段落聚合")
    p.add_argument("segs_json")
    p.add_argument("--out", required=True)
    p.add_argument("--gap", type=float, default=1.5)

    p = sub.add_parser("extract_frames", help="按参数抽帧 (fps/start/end 你决定)")
    p.add_argument("video_path")
    p.add_argument("--out", required=True)
    p.add_argument("--fps", type=float, default=1.0)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=0, help="0=到结尾")

    p = sub.add_parser("list_frames", help="列出帧文件")
    p.add_argument("dir")

    p = sub.add_parser("cleanup_frames", help="删除未使用的帧")
    p.add_argument("dir")
    p.add_argument("--keep", nargs="*", default=[])

    # ── 后备命令 (VE API, 通常不需要) ──
    p = sub.add_parser("classify_frame", help="[后备] API 分类单帧")
    p.add_argument("frame_path")
    p.add_argument("--model", default="qwen3-vl-plus")

    p = sub.add_parser("ocr_frame", help="[后备] API OCR 单帧")
    p.add_argument("frame_path")
    p.add_argument("--model", default="qwen3-vl-plus")
    p.add_argument("--type", default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cmds = {
        "download": cmd_download,
        "transcribe": cmd_transcribe,
        "aggregate": cmd_aggregate,
        "extract_frames": cmd_extract_frames,
        "list_frames": cmd_list_frames,
        "cleanup_frames": cmd_cleanup_frames,
        "classify_frame": cmd_classify_frame,
        "ocr_frame": cmd_ocr_frame,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
