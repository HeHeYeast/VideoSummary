"""v2 离线数据层: 下载 + ASR + 段落聚合 + 智能抽帧 + pass1 分类 + frame_store + CLIP embed.

产出文件 (work_dir/):
  meta.json          — 视频元数据
  segs.json          — 原始字幕 segments
  paragraphs.json    — 段落聚合结果
  frames/            — 关键帧图片
  frame_store.json   — 结构化帧存储 (含 pass1 分类 + info_score)
  embeddings.npy     — CLIP embeddings (可选, 装了 open_clip 才有)
  budget_report.txt  — 预算使用报告

用法:
  python -m agent.prepare <bilibili_url> [--mode test|prod] [--out output]
  python -m agent.prepare <bilibili_url> --skip-download

设计参考: AGENT_DESIGN.md §三 (离线数据层) + §六 Week 0
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="VideoSummary v2 离线数据准备")
    parser.add_argument("url", help="B站视频 URL")
    parser.add_argument("--mode", choices=["test", "prod"], default="prod")
    parser.add_argument("--out", default="output", help="输出根目录")
    parser.add_argument("--whisper", default="small", help="whisper 模型大小")
    parser.add_argument("--vision-model", default="qwen3-vl-plus")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-clip", action="store_true",
                        help="跳过 CLIP embedding (加速或缺依赖时)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    log = logging.getLogger(__name__)

    # 确保 src 模块可导入
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.asr import Segment, extract_audio, transcribe, parse_vtt
    from src.budget import BudgetGuard
    from src.download import download
    from src.llm_client import make_client

    from agent.asr_v2 import aggregate_paragraphs, paragraphs_to_dicts
    from agent.frames_v2 import extract_smart_keyframes
    from agent.pass1_classify import classify_frames
    from agent.frame_store import FrameStore, FrameRecord
    from agent.embed import compute_embeddings

    # 预算
    cfg_path = Path(__file__).parent.parent / "config" / f"budget_{args.mode}.yaml"
    budget = BudgetGuard.from_yaml(cfg_path)

    # work_dir
    bv = args.url.rstrip("/").split("/")[-1].split("?")[0]
    work_dir = Path(args.out) / bv
    work_dir.mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════════════
    # Stage 1: 下载
    # ═══════════════════════════════════════════════════════════
    log.info("=== Stage 1: 下载 ===")
    if args.skip_download and (work_dir / "meta.json").exists():
        meta = json.loads((work_dir / "meta.json").read_text(encoding="utf-8"))
        log.info("skip-download, 用缓存 meta")
    else:
        meta = download(args.url, work_dir, skip_if_cached=True)
    if not meta.get("video_path"):
        log.error("下载失败")
        sys.exit(1)

    # ═══════════════════════════════════════════════════════════
    # Stage 2: ASR
    # ═══════════════════════════════════════════════════════════
    log.info("=== Stage 2: ASR ===")
    segs_cache = work_dir / "segs.json"
    if segs_cache.exists():
        log.info("缓存命中: segs.json")
        segs_data = json.loads(segs_cache.read_text(encoding="utf-8"))
    else:
        if meta.get("subtitle_path"):
            log.info("使用已下载字幕: %s", meta["subtitle_path"])
            raw_segs = parse_vtt(meta["subtitle_path"])
        else:
            audio = work_dir / "audio.wav"
            extract_audio(meta["video_path"], audio)
            raw_segs = transcribe(audio, model_size=args.whisper, language=None)
        segs_data = [asdict(s) for s in raw_segs]
        segs_cache.write_text(
            json.dumps(segs_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ═══════════════════════════════════════════════════════════
    # Stage 3: 段落聚合 (v2 新增)
    # ═══════════════════════════════════════════════════════════
    log.info("=== Stage 3: 段落聚合 ===")
    para_cache = work_dir / "paragraphs.json"
    if para_cache.exists():
        log.info("缓存命中: paragraphs.json")
        paras_data = json.loads(para_cache.read_text(encoding="utf-8"))
    else:
        paras = aggregate_paragraphs(segs_data)
        paras_data = paragraphs_to_dicts(paras)
        para_cache.write_text(
            json.dumps(paras_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log.info("段落聚合: %d segments → %d paragraphs", len(segs_data), len(paras_data))

    # ═══════════════════════════════════════════════════════════
    # Stage 4: 智能抽帧 (v2: 信息量打分 + top-K)
    # ═══════════════════════════════════════════════════════════
    log.info("=== Stage 4: 智能抽帧 ===")
    frames_dir = work_dir / "frames"
    store_path = work_dir / "frame_store.json"
    store = FrameStore(store_path)

    if len(store) > 0:
        log.info("缓存命中: frame_store.json (%d 帧)", len(store))
    else:
        selected = extract_smart_keyframes(
            meta["video_path"], frames_dir,
            segs=segs_data,
            cap=budget.frame_cap,
        )
        log.info("智能抽帧完成: %d 帧入选", len(selected))

        # ═══════════════════════════════════════════════════════
        # Stage 5: Pass1 分类
        # ═══════════════════════════════════════════════════════
        log.info("=== Stage 5: Pass1 帧分类 ===")
        client = make_client(budget)
        frame_dicts = [
            {
                "frame_id": f"f{i:04d}",
                "timestamp": f.timestamp,
                "path": f.path,
            }
            for i, f in enumerate(selected)
        ]
        classifications = classify_frames(frame_dicts, client, model=args.vision_model)

        # 写入 frame_store
        for i, (sf, fc) in enumerate(zip(selected, classifications)):
            store.add(FrameRecord(
                frame_id=f"f{i:04d}",
                timestamp=sf.timestamp,
                path=sf.path,
                phash=sf.phash,
                info_score=sf.info_score,
                type=fc.type,
                has_text=fc.has_text,
                brief=fc.brief,
            ))
        store.save()
        log.info("frame_store 写入: %d 帧", len(store))

    # ═══════════════════════════════════════════════════════════
    # Stage 6: CLIP Embedding (可选)
    # ═══════════════════════════════════════════════════════════
    emb_path = work_dir / "embeddings.npy"
    if args.skip_clip:
        log.info("=== Stage 6: CLIP embedding (跳过: --skip-clip) ===")
    elif emb_path.exists():
        log.info("=== Stage 6: CLIP embedding (缓存命中) ===")
    else:
        log.info("=== Stage 6: CLIP embedding ===")
        frame_paths = [fr.path for fr in sorted(
            store.frames.values(), key=lambda f: f.timestamp
        )]
        embeddings = compute_embeddings(frame_paths, emb_path)
        if embeddings is None:
            log.info("CLIP 不可用, 跳过 (pip install open_clip_torch 安装)")
        else:
            log.info("CLIP embeddings: %s", embeddings.shape)

    # ═══════════════════════════════════════════════════════════
    # 完成报告
    # ═══════════════════════════════════════════════════════════
    (work_dir / "budget_report.txt").write_text(budget.report(), encoding="utf-8")

    # 汇总
    type_counts = {}
    for fr in store.frames.values():
        type_counts[fr.type] = type_counts.get(fr.type, 0) + 1

    log.info("=" * 60)
    log.info("数据准备完成: %s", work_dir)
    log.info("  字幕: %d segments → %d paragraphs", len(segs_data), len(paras_data))
    log.info("  帧: %d 张 (分类: %s)", len(store), type_counts)
    log.info("  CLIP: %s", "有" if emb_path.exists() else "无")
    log.info("=" * 60)

    print(f"\n数据目录: {work_dir}")
    print(f"字幕: {len(segs_data)} segments → {len(paras_data)} paragraphs")
    print(f"帧: {len(store)} 张 {type_counts}")
    print(f"CLIP: {'有' if emb_path.exists() else '无'}")
    print(f"\n接下来在 Claude Code 中说: 请总结视频 {work_dir}")
    print(budget.report())


if __name__ == "__main__":
    main()
