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
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from agent.io import (
    write_json_atomic,
    read_sidecar,
    cache_decision,
    _get_ffmpeg_version,
    _get_faster_whisper_version,
    now_iso,
)
from agent.state import append_event, params_hash

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def _build_sidecar(*, cli: dict, func: dict, tools: dict) -> dict:
    """Construct the locked 3-segment sidecar shape (D-07).

    Schema includes cli, func, tools, captured_at, schema_version=1.
    """
    return {
        "cli": dict(cli),
        "func": dict(func),
        "tools": dict(tools),
        "captured_at": now_iso(),
        "schema_version": 1,
    }


def _emit_event(out_dir: Path, stage: str, status: str,
                *, sidecar: dict | None = None, details: dict | None = None) -> None:
    """Emit one event to out_dir/state.jsonl. Best-effort.

    append_event swallows its own OSError -> log.warning. sidecar is hashed via
    params_hash; if None, params_hash is empty string.
    """
    state_log = out_dir / "state.jsonl"
    h = params_hash(sidecar) if sidecar else ""
    append_event(state_log, stage=stage, status=status, params_hash=h, details=details)


def cmd_download(args):
    """下载视频. 自动识别 B 站 / 抖音."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.io import write_sidecar
    work_dir = Path(args.out)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Phase 2 RES-05: emit started event (sidecar not yet built -- empty params_hash).
    # Truncate URL for log brevity (avoid leaking long douyin tracking params).
    _emit_event(work_dir, "download", "started",
                details={"url": args.url[:120]})

    sidecar = None  # built only on success path so we can hash it for the completed event
    try:
        url = args.url.lower()
        if "douyin.com" in url:
            # 抖音走自建 downloader (a_bogus 签名)
            from agent.douyin_downloader import download_douyin
            # cookies 文件默认在项目根
            cookies_file = os.getenv("DOUYIN_COOKIES_FILE",
                                      str(Path(__file__).parent.parent / "www.douyin.com_cookies.txt"))
            if not Path(cookies_file).exists():
                log.warning("抖音 cookies 文件不存在: %s (可能导致下载失败)", cookies_file)
                cookies_file = None
            meta = download_douyin(args.url, work_dir,
                                   cookies_file=cookies_file, skip_if_cached=True)
            platform = "douyin"
        else:
            # B 站 / YouTube / 其他走 yt-dlp
            from src.download import download
            meta = download(args.url, work_dir, skip_if_cached=True)
            platform = "bilibili_or_other"

        # Phase 2 RES-01: write sidecar for meta.json (D-04 -- newly-written
        # artifacts always carry sidecars). meta.json itself is written by the
        # downloader; we only attach the sidecar here. Archive meta.json without
        # sidecar follows D-01 path (warn but don't regen).
        meta_path = work_dir / "meta.json"
        if meta_path.exists():
            sidecar = _build_sidecar(
                cli={},
                func={"skip_if_cached": True, "platform": platform},
                tools={"ffmpeg": _get_ffmpeg_version()},
            )
            try:
                write_sidecar(meta_path, sidecar)
            except OSError as e:
                log.warning("failed to write meta.json sidecar: %s", e)

        _emit_event(work_dir, "download", "completed", sidecar=sidecar,
                    details={"platform": platform})
        # 避免打印含 emoji 的 title 炸 gbk 终端
        print(json.dumps(meta, ensure_ascii=True, indent=2))
    except Exception as e:
        _emit_event(work_dir, "download", "failed", sidecar=sidecar,
                    details={"error_type": type(e).__name__, "error": str(e)[:200]})
        raise


def cmd_transcribe(args):
    """ASR 转录 (本地 faster-whisper)."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.asr import extract_audio, transcribe, Segment, _VAD_DEFAULTS
    from agent.io import load_segs

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    segs_file = out_dir / "segs.json"
    # Build current sidecar (this run params) per D-05 / D-07
    current_sidecar = _build_sidecar(
        cli={"whisper": args.whisper},
        func={
            "language": None,
            "vad_filter": True,
            "min_silence_duration_ms": _VAD_DEFAULTS["min_silence_duration_ms"],
            "condition_on_previous_text": False,
            "beam_size": 5,
        },
        tools={
            "faster_whisper": _get_faster_whisper_version(),
            "ffmpeg": _get_ffmpeg_version(),
        },
    )

    # Phase 2 RES-05: started event with current params hash so derived_state
    # can reason about "we attempted transcribe with params H even if it crashed".
    _emit_event(out_dir, "transcribe", "started", sidecar=current_sidecar)

    try:
        audio = out_dir / "audio.wav"
        if not audio.exists():
            extract_audio(args.video_path, audio)

        decision = "regen"  # default if file missing
        if segs_file.exists():
            old_sidecar = read_sidecar(segs_file)
            decision = cache_decision(
                old_sidecar, current_sidecar, "segs.json", forced=args.force,
            )

        if decision in ("reuse", "warn_then_reuse"):
            print(f"cached: {segs_file}")
            segs_data = load_segs(segs_file)
        else:
            # decision is regen or regen_forced
            segs = transcribe(audio, model_size=args.whisper, language=None)
            segs_data = [asdict(s) for s in segs]
            write_json_atomic(segs_file, segs_data, sidecar_params=current_sidecar)

        _emit_event(out_dir, "transcribe", "completed", sidecar=current_sidecar,
                    details={"segs_count": len(segs_data), "decision": decision})

        print(f"segments: {len(segs_data)}")
        if segs_data:
            print(f"time: {segs_data[0]['start']:.1f}s - {segs_data[-1]['end']:.1f}s")
        print(f"output: {segs_file}")
    except Exception as e:
        _emit_event(out_dir, "transcribe", "failed", sidecar=current_sidecar,
                    details={"error_type": type(e).__name__, "error": str(e)[:200]})
        raise


def cmd_aggregate(args):
    """段落聚合."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.asr_v2 import aggregate_paragraphs, paragraphs_to_dicts, _DEFAULTS
    from agent.io import load_segs, load_paragraphs

    segs = load_segs(args.segs_json)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # state.jsonl lives alongside paragraphs.json (same output/<slug>/ dir).
    state_dir = out.parent

    # Build current sidecar
    current_sidecar = _build_sidecar(
        cli={"gap": args.gap},
        func={
            "gap_threshold": args.gap,
            "max_para_duration": _DEFAULTS["max_para_duration"],
            "sentence_gap": _DEFAULTS["sentence_gap"],
        },
        tools={},  # pure Python, no external tool
    )

    _emit_event(state_dir, "aggregate", "started", sidecar=current_sidecar)

    try:
        decision = "regen"
        if out.exists():
            old_sidecar = read_sidecar(out)
            forced = bool(getattr(args, "force", False))
            decision = cache_decision(old_sidecar, current_sidecar, out.name, forced=forced)

        if decision in ("reuse", "warn_then_reuse"):
            print(f"cached: {out}")
            paras_data = load_paragraphs(out)
            print(f"{len(segs)} segments -> {len(paras_data)} paragraphs (cached)")
        else:
            paras = aggregate_paragraphs(segs, gap_threshold=args.gap)
            paras_data = paragraphs_to_dicts(paras)
            write_json_atomic(out, paras_data, sidecar_params=current_sidecar)
            print(f"{len(segs)} segments -> {len(paras)} paragraphs")

        _emit_event(state_dir, "aggregate", "completed", sidecar=current_sidecar,
                    details={"paragraphs_count": len(paras_data), "decision": decision})
        print(f"output: {out}")
    except Exception as e:
        _emit_event(state_dir, "aggregate", "failed", sidecar=current_sidecar,
                    details={"error_type": type(e).__name__, "error": str(e)[:200]})
        raise


def cmd_extract_frames(args):
    """抽帧: ffmpeg 按指定参数提取. 参数由 Claude Code 根据视频内容决定."""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # state.jsonl lives in output/<slug>/, frames/ is a subdir below it.
    # Per D-08 frames/ has no JSON sidecar; per D-14 segment-level events are
    # deferred to Phase 4. Day-1 grain: one started + one completed per call.
    state_dir = out_dir.parent
    details_in = {"fps": args.fps, "start": args.start, "end": args.end}
    _emit_event(state_dir, "extract_frames", "started", details=details_in)

    try:
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
        _emit_event(state_dir, "extract_frames", "completed",
                    details={**details_in, "frames_count": len(files)})

        print(f"extracted: {len(files)} frames ({args.start}s-{args.end}s, fps={args.fps})")
        for f in files[:5]:
            ts = args.start + (int(f.stem.split("_")[-1]) - 0.5) / args.fps
            print(f"  [{ts:.1f}s] {f.name}")
        if len(files) > 5:
            print(f"  ... and {len(files) - 5} more")
    except Exception as e:
        _emit_event(state_dir, "extract_frames", "failed",
                    details={**details_in, "error_type": type(e).__name__, "error": str(e)[:200]})
        raise


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
    # state.jsonl lives one level up from frames/ subdir.
    state_dir = d.parent
    keep = set(args.keep) if args.keep else set()
    _emit_event(state_dir, "cleanup_frames", "started",
                details={"keep_count": len(keep)})

    try:
        removed = 0
        for f in sorted(d.glob("*.jpg")):
            if f.name not in keep:
                f.unlink()
                removed += 1
        _emit_event(state_dir, "cleanup_frames", "completed",
                    details={"removed": removed, "kept": len(keep)})
        print(f"removed {removed} frames, kept {len(keep)}")
    except Exception as e:
        _emit_event(state_dir, "cleanup_frames", "failed",
                    details={"error_type": type(e).__name__, "error": str(e)[:200]})
        raise


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
