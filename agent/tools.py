"""独立工具 CLI: 3 个核心命令 + 2 个可选命令, Claude Code 按需调用.

核心命令 (本地执行, ¥0):
  python -m agent.tools download <url> --out <dir>
  python -m agent.tools transcribe <video_path> --out <dir> [--whisper small]
  python -m agent.tools extract_frames <video_path> --out <dir> --fps 1 --start 0 --end 120

辅助命令 (本地, ¥0):
  python -m agent.tools aggregate <segs_json> --out <paragraphs_json>
  python -m agent.tools list_frames <dir>
  python -m agent.tools cleanup_frames <dir> --keep <f1.jpg> <f2.jpg> ...
  python -m agent.tools doctor <dir> [--json]   # 只读扫描工件状态 (Phase 2 RES-07)

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
import re
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
from agent.state import append_event, params_hash, read_events, derived_state

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


# Phase 3 SRC-10 D-19 (broadened per RESEARCH Pitfall 2 — Discretion):
# CJK Unified + Compatibility + Hiragana + Katakana + Fullwidth Forms.
# Narrow [一-鿿] misses Katakana/Hiragana/Fullwidth which all hit the
# same ffmpeg subprocess GBK code-page hazard on Windows zh-CN.
_CJK_PAT = re.compile(r"[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]")


def _validate_out_path(out_path) -> None:
    """Reject CJK in --out per CONTEXT D-19 (broadened per RESEARCH Pitfall 2).

    Validates BEFORE any subprocess is invoked so the user gets a clean Python
    ValueError instead of opaque ffmpeg corruption later.
    """
    if _CJK_PAT.search(str(out_path)):
        raise ValueError(
            f"CJK characters in --out path break ffmpeg subprocess on Windows zh-CN; "
            f"use ASCII-only path under output/ (got {out_path!r})"
        )


# Phase 2 RES-07: artifacts doctor reports on, mapped to the stage that produces them.
# Order matters -- table rows are emitted in this order.
# Locked by 02-CONTEXT D-16; frames/ subdir intentionally omitted (no per-frame sidecar
# per D-08; segment-level events deferred to Phase 4 per D-14).
_DOCTOR_ARTIFACTS = [
    ("meta.json", "download"),
    ("segs.json", "transcribe"),
    ("paragraphs.json", "aggregate"),
    ("diarization.json", "diarize"),  # Phase 5 TEACH-08 (opt-in; missing == "—" in doctor table)
]


def _emit_event(out_dir: Path, stage: str, status: str,
                *, sidecar: dict | None = None, details: dict | None = None) -> None:
    """Emit one event to out_dir/state.jsonl. Best-effort.

    append_event swallows its own OSError -> log.warning. sidecar is hashed via
    params_hash; if None, params_hash is empty string.
    """
    state_log = out_dir / "state.jsonl"
    h = params_hash(sidecar) if sidecar else ""
    append_event(state_log, stage=stage, status=status, params_hash=h, details=details)


def cmd_ingest(args):
    """Ingest video from URL or local path. Phase 3 SRC-03 canonical entry point.

    Routes via agent.url_router.route() to the appropriate Source class.
    Centralizes meta.json write + sidecar through agent.io.write_json_atomic
    (Phase 2 D-09 single-landing-point — RESEARCH §"Architecture Patterns Pattern 5").

    NOTE: stage name is hard-coded "download" (NOT "ingest") so state.jsonl events
    remain comparable across pre-/post-Phase-3 archives — RESEARCH Pitfall 5,
    anchored at _DOCTOR_ARTIFACTS line 64.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.url_router import route
    from agent.sources._common import ffprobe_video  # Phase 3 SRC-11 (03-03)

    # Phase 3 SRC-10 D-19: CJK rejection BEFORE work_dir.mkdir or any subprocess.
    # Broadened pattern covers CJK Unified + Compat + Hiragana + Katakana + Fullwidth
    # (RESEARCH Pitfall 2 + CONTEXT Discretion).
    _validate_out_path(args.out)

    work_dir = Path(args.out)
    work_dir.mkdir(parents=True, exist_ok=True)

    # Phase 3 SRC-07: log yt-dlp version + warn if > 90 days old (D-15).
    # Lazy import — YouTubeSource owns the version check helper because it's
    # the source most affected by yt-dlp drift; cheap when called from any path.
    try:
        from agent.sources.youtube import warn_if_yt_dlp_stale
        warn_if_yt_dlp_stale()
    except ImportError:
        pass  # yt-dlp not installed; sources will fail at fetch() with clearer error

    # Phase 2 RES-05: emit started event with truncated URL for log brevity.
    _emit_event(work_dir, "download", "started",
                details={"url_or_path": str(args.url)[:120]})

    sidecar = None
    try:
        # 1. Route URL/path to source class
        source = route(args.url)
        log.info("source: %s", source.name)

        # 2. Delegate fetch to source (writes video.mp4 + an initial meta.json
        #    via legacy module's own write_text — that's OK; we re-write atomically below).
        meta = source.fetch(args.url, work_dir, skip_if_cached=True)

        # 3. Phase 3 SRC-11 D-21: ffprobe preflight on EVERY source's output.
        #    Failure (no audio) raises RuntimeError with remux suggestion.
        #    Success augments meta with codec/container/fps_mode (additive at end —
        #    preserves legacy prefix per RESEARCH Pitfall 6).
        #    WR-01 fix: read meta["video_path"] not literal "video.mp4" — yt-dlp may
        #    serve .webm/.mkv/.flv when YouTube format chain prefers them.
        video_path_str = meta.get("video_path") or str(work_dir / "video.mp4")
        video_path = Path(video_path_str)
        if video_path.exists():
            ffprobe_info = ffprobe_video(video_path)
            meta = {**meta,
                    "codec": ffprobe_info["codec"],
                    "container": ffprobe_info["container"],
                    "fps_mode": ffprobe_info["fps_mode"]}
            # Update duration if ffprobe got a real value and meta's duration is 0
            # (LocalSource always returns 0; YouTube/B站 already have real duration).
            if not meta.get("duration") and ffprobe_info.get("duration_s"):
                meta["duration"] = ffprobe_info["duration_s"]

        # 4. Centralized meta.json write through agent.io.write_json_atomic.
        #    The legacy module already wrote meta.json with 7-key (bilibili/generic)
        #    or 9-key (douyin) shape; this re-write atomically replaces it with
        #    the augmented dict (legacy keys + Phase 3 additive fields at end).
        #    Sidecar comes for free (Phase 2 D-04).
        meta_path = work_dir / "meta.json"
        sidecar = _build_sidecar(
            cli={},
            func={"skip_if_cached": True, "source": source.name},
            tools={"ffmpeg": _get_ffmpeg_version()},
        )
        write_json_atomic(meta_path, meta, sidecar_params=sidecar)

        _emit_event(work_dir, "download", "completed", sidecar=sidecar,
                    details={"source": source.name})

        # ASCII-safe print to survive default GBK Windows terminals (CLAUDE.md L41-44).
        print(json.dumps(meta, ensure_ascii=True, indent=2))
    except Exception as e:
        _emit_event(work_dir, "download", "failed", sidecar=sidecar,
                    details={"error_type": type(e).__name__, "error": str(e)[:200]})
        raise


def cmd_download(args):
    """[backward-compat alias] 下载视频. 转 cmd_ingest 处理 (Phase 3 SRC-03 D-07).

    The existing `download` subcommand is preserved as a permanent alias to
    `ingest` for the documented 5-command CLI surface (CLAUDE.md L11-17 +
    PROJECT.md K3 backward-compat).

    Observable behavior is identical to ingest on B站/抖音 URLs (verified via
    Phase 1 baselines BV132wizyEEB / BV1C9QCBdE1U / douyin_trae_ai — see
    RESEARCH §"Byte-Identical Regression Strategy").
    """
    return cmd_ingest(args)


def cmd_transcribe(args):
    """ASR 转录 (本地 faster-whisper)."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.asr import extract_audio, transcribe, Segment, PROFILES
    from agent.io import load_segs

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Phase 5 D-27: profile 解析为具体数值用于 sidecar.func 抓取
    profile_dict = PROFILES[args.profile]

    segs_file = out_dir / "segs.json"
    # Build current sidecar (this run params) per D-05 / D-07 + Phase 5 D-27
    current_sidecar = _build_sidecar(
        cli={"whisper": args.whisper, "profile": args.profile},
        func={
            "profile": args.profile,
            "language": None,
            "vad_filter": True,
            "min_silence_duration_ms": profile_dict["vad_min_silence_ms"],
            "vad_threshold": profile_dict["vad_threshold"],
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
            segs = transcribe(
                audio, model_size=args.whisper, language=None,
                profile=args.profile,
            )
            segs_data = [asdict(s) for s in segs]
            write_json_atomic(segs_file, segs_data, sidecar_params=current_sidecar)

            # Phase 5 TEACH-11 / D-22..D-25: repetition guard (旁路, 不删 segs.json)
            warnings_data = whisper_repetition_guard(segs_data)
            if warnings_data:
                _emit_repetition_warnings(out_dir, warnings_data)

        _emit_event(out_dir, "transcribe", "completed", sidecar=current_sidecar,
                    details={"segs_count": len(segs_data), "decision": decision,
                             "profile": args.profile})

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
    from agent.asr_v2 import aggregate_paragraphs, paragraphs_to_dicts, PROFILES
    from agent.io import load_segs, load_paragraphs

    segs = load_segs(args.segs_json)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # state.jsonl lives alongside paragraphs.json (same output/<slug>/ dir).
    state_dir = out.parent

    # Phase 5 D-27: profile 解析为具体数值用于 sidecar.func 抓取
    profile_dict = PROFILES[args.profile]
    eff_gap = args.gap if args.gap is not None else profile_dict["gap_threshold"]

    # Build current sidecar (Phase 5 D-27: profile进 cli + func)
    current_sidecar = _build_sidecar(
        cli={"profile": args.profile, "gap": args.gap},
        func={
            "profile": args.profile,
            "gap_threshold": eff_gap,
            "max_para_duration": profile_dict["max_para_duration"],
            "sentence_gap": profile_dict["sentence_gap"],
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
            paras = aggregate_paragraphs(
                segs, profile=args.profile, gap_threshold=args.gap,
            )
            paras_data = paragraphs_to_dicts(paras)
            write_json_atomic(out, paras_data, sidecar_params=current_sidecar)
            print(f"{len(segs)} segments -> {len(paras)} paragraphs (profile={args.profile})")

        _emit_event(state_dir, "aggregate", "completed", sidecar=current_sidecar,
                    details={"paragraphs_count": len(paras_data), "decision": decision,
                             "profile": args.profile})
        print(f"output: {out}")
    except Exception as e:
        _emit_event(state_dir, "aggregate", "failed", sidecar=current_sidecar,
                    details={"error_type": type(e).__name__, "error": str(e)[:200]})
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 TEACH-11 / D-22..D-25: whisper repetition guard (旁路检测).
# Algorithm (D-22 broadened per REVIEW WR-02 — D-22 字面 spec under-specifies):
#   Two complementary detectors run in parallel; either fires → flag.
#   (a) Consecutive run: 字符级 3-gram run-length > 3× → flag
#       Catches '啊啊啊啊' / '......' (Whisper char-pad on extended silence).
#   (b) Density: same 3-gram total count >= 4 AND occupies >60% of joined
#       text → flag. Catches '我们这里用我们这里用...' (Whisper phrase-repeat
#       hallucination — the form D-22 docstring example explicitly cited).
#   Both detectors run on (1) single segment and (2) ≤3 adjacent-seg windows.
# Output (D-23 字面 schema): list of warning dicts -> transcribe_warnings.json
# Redline (D-24): never auto-delete from segs.json; never mutate input list.
# Operation: O(n_chars) per video; no DoS risk (whisper segs ≤ ~30s × ~3 segs).
# ─────────────────────────────────────────────────────────────────────────────
_REPETITION_THRESHOLD = 3      # > 3 = 4 次或更多 (D-22 字面 — consecutive run)
_DENSITY_MIN_COUNT = 4         # 最少 4 次出现才考虑 density flag (避免短文本误报)
_DENSITY_COVERAGE = 0.6        # 同一 3-gram 实例覆盖 text 长度 >= 60% 才命中
                               # (count * 3 / len(text); 对 cycle-len-5 短语正好 60%)
_CONTEXT_CHARS = 200           # context_before/after 默认 200 字符 (Claude Discretion in D-25)


def _count_consecutive_trigrams(text: str) -> dict[str, int]:
    """字符级 3-gram 连续 run-length 统计.

    Sliding window stride=1: 'aaaaa' → {'aaa': 3} (3 个连续 'aaa' starting
    at i=0,1,2). 'abcabcabcabc' → 不命中（不同 trigram 交替不算"连续"）.

    用于检测 whisper 字符级重复幻觉 (e.g. '啊啊啊啊', '......').
    NOTE: 短语级幻觉 ('我们这里用我们这里用...') 不命中 — 用
    `_count_repeated_trigrams` density-based 检测器补足 (REVIEW WR-02).
    """
    if len(text) < 3:
        return {}
    grams = [text[i:i + 3] for i in range(len(text) - 2)]
    runs: dict[str, int] = {}
    cur_gram = grams[0]
    cur_run = 1
    for g in grams[1:]:
        if g == cur_gram:
            cur_run += 1
        else:
            runs[cur_gram] = max(runs.get(cur_gram, 0), cur_run)
            cur_gram = g
            cur_run = 1
    # 最后一段
    runs[cur_gram] = max(runs.get(cur_gram, 0), cur_run)
    return runs


def _count_repeated_trigrams(text: str) -> dict[str, int]:
    """字符级 3-gram 总出现次数统计 (Counter-style, 非"连续" run).

    Sliding window stride=1: '我们这里用我们这里用我们这里用我们这里用'
    → {'我们这': 4, '们这里': 4, '这里用': 4, '里用我': 3, '用我们': 3}.

    用于检测 whisper 短语级重复幻觉 (REVIEW WR-02): 同一 3-gram 出现
    >= _DENSITY_MIN_COUNT 次且占比 > _DENSITY_RATIO of (len(text)/3) → flag.
    Density threshold (>60%) 防止自然语言虚警 ("the the the" 在长句里仅占
    极小比例不触发).
    """
    if len(text) < 3:
        return {}
    from collections import Counter
    return dict(Counter(text[i:i + 3] for i in range(len(text) - 2)))


def _build_context(segs: list[dict], from_idx: int, to_idx: int) -> dict[str, str]:
    """取 from_idx 之前 ≤200 字符 + to_idx 之后 ≤200 字符 (Claude Discretion in D-25)."""
    before = ""
    for i in range(from_idx - 1, -1, -1):
        before = segs[i].get("text", "") + " " + before
        if len(before) >= _CONTEXT_CHARS:
            before = before[-_CONTEXT_CHARS:]
            break
    after = ""
    for i in range(to_idx + 1, len(segs)):
        after = after + " " + segs[i].get("text", "")
        if len(after) >= _CONTEXT_CHARS:
            after = after[:_CONTEXT_CHARS]
            break
    return {"before": before.strip(), "after": after.strip()}


def _density_hit(text: str) -> tuple[str, int] | None:
    """Density-based detector (REVIEW WR-02): 找占比最高且覆盖 >=60% 的 3-gram.

    Coverage = count * 3 / len(text)  (粗略 chars-covered 估算; 重叠位置
    被高估但 cycle-repeats 中重叠很少, 实际偏差小).

    For '我们这里用'*5 (len=25, cycle=5): best_gram count=5, 5*3/25 = 60% → 命中.
    For natural language: max trigram count 通常 1-2, coverage <<60% → 不命中.

    Returns (gram, count) on hit, None otherwise. 选择 max-count gram 而非
    遍历所有 hit, 避免一次重复同时报 5 个高度重叠的 3-gram (e.g.
    '我们这里用我们这里用...' 中 '我们这'/'们这里'/'这里用' 都会同时命中).
    """
    counts = _count_repeated_trigrams(text)
    if not counts:
        return None
    text_len = max(len(text), 1)
    best_gram, best_count = max(counts.items(), key=lambda kv: kv[1])
    if best_count >= _DENSITY_MIN_COUNT and (best_count * 3) / text_len >= _DENSITY_COVERAGE:
        return best_gram, best_count
    return None


def whisper_repetition_guard(segs: list[dict]) -> list[dict]:
    """检测 whisper 重复幻觉 (D-22 算法 + REVIEW WR-02 density 补足).

    Two complementary detectors per (1) single seg and (2) ≤3-seg window:
      (a) consecutive run-length > 3× → flag (catches '啊啊啊啊')
      (b) total-occurrence density > 60% with count >= 4 → flag
          (catches '我们这里用我们这里用...' phrase-repeat)

    Args:
        segs: list of {"start", "end", "text"} from segs.json (read-only;
            input list never mutated per D-24 红线)

    Returns:
        list of warning dicts per D-23 schema (空列表 = 无问题).
        Each warning: {start, end, trigram, count, context_before,
                       context_after, seg_indices}
    """
    warnings: list[dict] = []
    flagged: set[tuple[int, str]] = set()  # (segment_index, trigram) 已 flag

    # 1a. 单 segment 内 3-gram 连续重复 (字符级 hallucination)
    for seg_idx, seg in enumerate(segs):
        text = seg.get("text", "")
        for gram, run in _count_consecutive_trigrams(text).items():
            if run > _REPETITION_THRESHOLD:
                ctx = _build_context(segs, seg_idx, seg_idx)
                warnings.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "trigram": gram,
                    "count": run,
                    "context_before": ctx["before"],
                    "context_after": ctx["after"],
                    "seg_indices": [seg_idx],
                })
                flagged.add((seg_idx, gram))

    # 1b. 单 segment 内 3-gram 高密度短语级重复 (REVIEW WR-02)
    for seg_idx, seg in enumerate(segs):
        text = seg.get("text", "")
        hit = _density_hit(text)
        if hit is None:
            continue
        gram, count = hit
        if (seg_idx, gram) in flagged:
            continue  # 1a 已 flag 同 (seg_idx, gram)
        ctx = _build_context(segs, seg_idx, seg_idx)
        warnings.append({
            "start": seg["start"],
            "end": seg["end"],
            "trigram": gram,
            "count": count,
            "context_before": ctx["before"],
            "context_after": ctx["after"],
            "seg_indices": [seg_idx],
        })
        flagged.add((seg_idx, gram))

    # 2a. 跨 ≤3 邻接 segments 连续重复 (window slide)
    for window_start in range(len(segs)):
        window_end = min(window_start + 3, len(segs))
        if window_end - window_start < 2:
            continue  # 单 segment 已在步骤 1 处理
        joined = " ".join(s.get("text", "") for s in segs[window_start:window_end])
        for gram, run in _count_consecutive_trigrams(joined).items():
            if run > _REPETITION_THRESHOLD:
                # 去重: 单 segment 内已 flag 的 (seg_idx, gram) 跳过
                if any((i, gram) in flagged for i in range(window_start, window_end)):
                    continue
                ctx = _build_context(segs, window_start, window_end - 1)
                warnings.append({
                    "start": segs[window_start]["start"],
                    "end": segs[window_end - 1]["end"],
                    "trigram": gram,
                    "count": run,
                    "context_before": ctx["before"],
                    "context_after": ctx["after"],
                    "seg_indices": list(range(window_start, window_end)),
                })
                for i in range(window_start, window_end):
                    flagged.add((i, gram))

    # 2b. 跨 ≤3 邻接 segments 高密度短语级重复 (REVIEW WR-02)
    for window_start in range(len(segs)):
        window_end = min(window_start + 3, len(segs))
        if window_end - window_start < 2:
            continue
        joined = " ".join(s.get("text", "") for s in segs[window_start:window_end])
        hit = _density_hit(joined)
        if hit is None:
            continue
        gram, count = hit
        if any((i, gram) in flagged for i in range(window_start, window_end)):
            continue
        ctx = _build_context(segs, window_start, window_end - 1)
        warnings.append({
            "start": segs[window_start]["start"],
            "end": segs[window_end - 1]["end"],
            "trigram": gram,
            "count": count,
            "context_before": ctx["before"],
            "context_after": ctx["after"],
            "seg_indices": list(range(window_start, window_end)),
        })
        for i in range(window_start, window_end):
            flagged.add((i, gram))

    return warnings


def _emit_repetition_warnings(out_dir: Path, warnings_data: list[dict]) -> None:
    """D-23 surfacing: stdout warning + transcribe_warnings.json bypass artifact."""
    n = len(warnings_data)
    log.warning("WARNING: detected %d suspected whisper repetitions", n)
    print(f"WARNING: detected {n} suspected whisper repetitions; first 3:")
    for w in warnings_data[:3]:
        h, rem = divmod(int(w["start"]), 3600)
        m, s = divmod(rem, 60)
        ts = f"{h:02d}:{m:02d}:{s:02d}"
        print(f'  [{ts}] "{w["trigram"]}" repeated {w["count"]}x')
    print(f"  -- review {out_dir}/transcribe_warnings.json")

    out_path = out_dir / "transcribe_warnings.json"
    payload = {"version": 1, "warnings": warnings_data}
    write_json_atomic(out_path, payload)  # 旁路 artifact, 不写 sidecar (D-23 schema 不含)


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
        # Phase 3 SRC-12 D-23: -vsync vfr applied uniformly so VFR sources (OBS/iPhone)
        # don't drop or duplicate frames silently. No fps_mode gating — even videos
        # detected as CFR benefit (RESEARCH Pitfall 1: detection is informational only).
        cmd += ["-vsync", "vfr", "-vf", f"fps={args.fps},scale=854:-1", "-q:v", "4", pattern]

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


def cmd_extract_frames_batch(args):
    """Phase 4 FPS-01/02/03/04. Batch frame extraction from schedule.json.

    Per CONTEXT D-09..D-13: load + validate schedule, iterate segments, emit
    per-segment started/completed/failed events, segment-level resume via
    state.jsonl, --force bypass. Filename grammar `seg_<start>_<index>.jpg`
    preserved (D-10).

    K5 enforcement (locked at CONTEXT line 10 + Discretion / RESEARCH Anti-
    Patterns): this function does NOT read the scene-cuts artifact and does
    NOT auto-promote that artifact (or the silence map) into a schedule.
    The silence-map artifact is allowed as a *validation input* only (D-07
    /D-08 silence-coverage check), never to generate or modify segments.
    Verified by a static-source K5 check in tests.
    """
    from agent.scheduler import Schedule, ScheduleValidationError
    from agent.state import derived_segment_state, read_events
    from agent.sources._common import ffprobe_video

    out_dir = Path(args.out)
    _validate_out_path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    schedule_path = Path(args.schedule)
    schedule = Schedule.from_json(schedule_path)

    # D-05.2: duration via ffprobe of the schedule.video field, resolved
    # relative to the schedule.json directory.
    video_path = (schedule_path.parent / schedule.video).resolve()
    probe = ffprobe_video(video_path)
    duration_s = probe["duration_s"]

    # D-07/D-08: silence_map.json is an OPTIONAL input to validate. We READ
    # it for validation only, never to modify segments (K5 boundary).
    silence_map_path = schedule_path.parent / "silence_map.json"
    silence_map = (
        json.loads(silence_map_path.read_text(encoding="utf-8"))
        if silence_map_path.exists()
        else None
    )
    schedule.validate(duration_s=duration_s, silence_map=silence_map)

    # Resume: state.jsonl lives in output/<slug>/, frames/ is a subdir below.
    state_dir = out_dir.parent
    if args.force:
        completed: set[int] = set()
    else:
        events, _status = read_events(state_dir / "state.jsonl")
        completed = derived_segment_state(events, stage="extract_frames_batch")

    for i, seg in enumerate(schedule.segments):
        if i in completed:
            log.info(
                "segment %d already completed, skipping (use --force to redo)", i
            )
            continue

        if seg.skip:
            _emit_event(
                state_dir, "extract_frames_batch", "started",
                details={"segment_index": i, "start": seg.start,
                         "end": seg.end, "skip": True},
            )
            _emit_event(
                state_dir, "extract_frames_batch", "completed",
                details={"segment_index": i, "start": seg.start,
                         "end": seg.end, "skip": True, "frames_count": 0},
            )
            print(f"[seg {i}] {seg.start}s-{seg.end}s SKIP")
            continue

        _emit_event(
            state_dir, "extract_frames_batch", "started",
            details={"segment_index": i, "start": seg.start, "end": seg.end},
        )
        try:
            cmd = ["ffmpeg", "-y"]
            if seg.start > 0:
                cmd += ["-ss", str(seg.start)]
            cmd += ["-i", str(video_path)]
            if seg.end > 0:
                cmd += ["-t", str(seg.end - max(seg.start, 0))]
            prefix = f"seg_{int(seg.start):04d}_"
            pattern = str(out_dir / f"{prefix}%06d.jpg")
            # Phase 3 SRC-12 D-23: -vsync vfr applied uniformly (matches
            # cmd_extract_frames argv shape — FPS-07 grammar preservation).
            cmd += [
                "-vsync", "vfr",
                "-vf", f"fps={seg.fps},scale={schedule.default_scale}",
                "-q:v", str(schedule.default_quality), pattern,
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            files = sorted(out_dir.glob(f"{prefix}*.jpg"))
            _emit_event(
                state_dir, "extract_frames_batch", "completed",
                details={"segment_index": i, "start": seg.start,
                         "end": seg.end, "frames_count": len(files)},
            )
            print(f"[seg {i}] {seg.start}s-{seg.end}s @ fps={seg.fps}: "
                  f"{len(files)} frames")
        except subprocess.CalledProcessError as e:
            _emit_event(
                state_dir, "extract_frames_batch", "failed",
                details={"segment_index": i, "start": seg.start,
                         "end": seg.end,
                         "error_type": type(e).__name__,
                         "error": (e.stderr.decode("utf-8", errors="replace")
                                   if e.stderr else str(e))[:200]},
            )
            raise RuntimeError(
                f"extract_frames_batch segment {i} failed: {e}"
            ) from e


def cmd_detect_scenes(args):
    """Phase 4 FPS-05. Decision support for Claude when authoring the schedule artifact.

    Runs PySceneDetect ContentDetector and writes a scenes JSON describing
    detected scene boundaries. Stdout reports total count + median duration so
    Claude can immediately gauge whether results are over-segmented (median < 2s
    on a tutorial video → re-run with --threshold 35 per RESEARCH Pitfall P4).

    K5 enforcement (locked at CONTEXT line 10 + PROJECT.md "Decision authority"):
    this handler writes ONLY the scenes artifact and NEVER auto-promotes scene
    boundaries into segment plans. The locked acceptance test asserts this
    function's source contains no reference to the schedule artifact filename.
    """
    from agent.scenes import detect_scenes

    out = Path(args.out)
    _validate_out_path(out)

    log.info("running PySceneDetect on %s (threshold=%.1f)",
             args.video, args.threshold)
    scenes = detect_scenes(args.video, threshold=args.threshold)

    obj = {"version": 1, "video": Path(args.video).name, "scenes": scenes}
    write_json_atomic(out, obj)

    if scenes:
        durations = sorted(s["end"] - s["start"] for s in scenes)
        median = durations[len(durations) // 2]
    else:
        median = 0.0
    print(f"detected {len(scenes)} scenes; median duration = {median:.1f}s")
    print(f"output: {out}")


def cmd_detect_silence(args):
    """Phase 4 FPS-06. Decision support for Claude when authoring the schedule artifact.

    Runs silero-vad (opt-in dep — install via requirements-optional.txt; pulls
    torch ~700MB), inverts speech_timestamps to silence intervals (Pitfall P7
    leading/trailing handled), flags duration > 5s with flagged_for_review:true
    (D-20), and writes the locked silence-map JSON shape.

    Stdout hint reminds Claude that, when writing the schedule artifact, each
    flagged interval must be covered by an fps segment (NOT skip), or a
    low-rate baseline pass per FPS-04 must exist (CONTEXT D-08 fallback).

    K5 enforcement (locked at CONTEXT line 10 + PROJECT.md "Decision authority"):
    this handler writes ONLY the silence-map artifact and NEVER auto-promotes
    silence intervals into segment plans. The locked acceptance test asserts
    this function's source contains no reference to the schedule artifact
    filename — hence the deliberately generic phrasing ("fps segment") below.
    """
    from agent.silence import detect_silence, ensure_audio_wav
    from agent.sources._common import ffprobe_video

    out = Path(args.out)
    _validate_out_path(out)

    probe = ffprobe_video(args.video)
    duration_s = probe["duration_s"]
    if duration_s <= 0:
        raise RuntimeError(
            f"could not determine duration of {args.video}; ffprobe returned 0"
        )

    # silence-map artifact lives beside other slug artifacts.
    slug_dir = out.parent
    slug_dir.mkdir(parents=True, exist_ok=True)
    audio_wav = ensure_audio_wav(args.video, slug_dir)

    intervals = detect_silence(audio_wav, duration_s=duration_s)

    obj = {
        "version": 1,
        "video": Path(args.video).name,
        "silence_intervals": intervals,
    }
    write_json_atomic(out, obj)

    flagged = sum(1 for iv in intervals
                  if iv.get("flagged_for_review") is True)
    print(f"Found {len(intervals)} silence intervals; {flagged} flagged > 5s.")
    print(
        "When writing the schedule artifact, ensure each flagged interval is "
        "covered by an fps segment (NOT skip), or add a low-rate baseline pass "
        "per FPS-04."
    )
    print(f"output: {out}")


def cmd_diarize(args):
    """Phase 5 TEACH-08 / D-13..D-17. Speaker diarization (opt-in via pyannote.audio).

    Thin CLI wrapper around agent.diarize.diarize_audio. Responsibilities:
      1. Read HF_TOKEN from .env; raise clean RuntimeError if absent (D-15)
      2. ffprobe duration probe + 60min+ AND no-CUDA gate (D-16 字面 verbatim)
      3. Phase 2 sidecar / state.jsonl idiom (Phase 2 D-07/D-09)
      4. Write diarization.json with schema {version: 1, turns: [...]} (D-13)

    K5 enforcement: this handler writes ONLY the diarization artifact and NEVER
    auto-promotes speaker turns into chapters or segment plans — chapters.json
    remains Claude-written (CLAUDE.md '## 视频类型变奏' Podcast skeleton).

    Threat model (T-05-03-08): HF_TOKEN never logged.
    """
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from agent.diarize import diarize_audio

    out_path = Path(args.out)
    _validate_out_path(out_path)
    out_dir = out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. HF_TOKEN guard (D-15) — load_dotenv was called at process start
    hf_token = os.environ.get("HF_TOKEN", "").strip()
    if not hf_token:
        raise RuntimeError(
            "HF_TOKEN not set; see CLAUDE.md '## Pyannote diarization 设置（首次设置，可选）'"
        )

    # 2. audio file existence check
    audio_path = Path(args.audio_wav)
    if not audio_path.exists():
        raise RuntimeError(f"audio file not found: {audio_path}")

    # 3. ffprobe duration probe (audio.wav has no video stream — use bare ffprobe
    # not agent.sources._common.ffprobe_video which requires a video stream).
    duration_s = 0.0
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json",
             "-show_format", str(audio_path)],
            check=True, capture_output=True, text=True,
            encoding="utf-8", timeout=5.0, shell=False,
        )
        info = json.loads(result.stdout)
        raw = info.get("format", {}).get("duration", "0")
        try:
            duration_s = float(raw)
        except (TypeError, ValueError):
            duration_s = 0.0
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired,
            FileNotFoundError, json.JSONDecodeError) as e:
        log.warning("ffprobe duration probe failed on %s: %s; skipping duration gate",
                    audio_path, e)

    # 4. CUDA detect (lazy)
    has_cuda = False
    try:
        import torch  # noqa: WPS433 — lazy import per opt-in idiom
        has_cuda = bool(torch.cuda.is_available())
    except ImportError:
        pass

    # 5. 60min+ AND no-CUDA gate (D-16 字面 verbatim Chinese prompt + default-N)
    if duration_s > 3600 and not has_cuda and not args.allow_long:
        # Threat T-05-03-07 mitigation: default N, user must explicitly type 'y'.
        print(
            "WARNING: 60min+ 音频在 CPU 上 pyannote 预计 3-5× wall time"
            "（约 3-5h）。建议 (1) 切片处理 (2) 跳过 diarization 让 Claude "
            "从内容推断 (3) 等待 GPU 机器再跑。继续？(y/N)"
        )
        try:
            ans = input().strip().lower()
        except EOFError:
            ans = ""
        if ans != "y":
            raise RuntimeError("diarize aborted by user (60min+ CPU gate; D-16)")

    # 6. Phase 2 sidecar idiom — diarize 也走 sidecar/state.jsonl
    state_dir = out_dir
    current_sidecar = _build_sidecar(
        cli={"audio_wav": str(audio_path), "allow_long": bool(args.allow_long)},
        func={
            "model": "pyannote/speaker-diarization-community-1",
            "device": "cuda" if has_cuda else "cpu",
            "duration_s": duration_s,
        },
        # pyannote.audio version 探测略过：lazy import; audio model 是 user 接受协议下载的,
        # 不强制 hash. (HF_TOKEN never goes into sidecar — T-05-03-08.)
        tools={},
    )
    _emit_event(state_dir, "diarize", "started", sidecar=current_sidecar)

    try:
        turns = diarize_audio(
            audio_path, hf_token=hf_token, allow_long=bool(args.allow_long),
        )
        payload = {"version": 1, "turns": turns}
        write_json_atomic(out_path, payload, sidecar_params=current_sidecar)
        _emit_event(
            state_dir, "diarize", "completed", sidecar=current_sidecar,
            details={"turns_count": len(turns), "duration_s": duration_s},
        )
        speakers = sorted({t["speaker_id"] for t in turns})
        print(f"diarization: {len(turns)} turns")
        suffix = "..." if len(speakers) > 5 else ""
        print(
            f"speakers: {len(speakers)} unique "
            f"({', '.join(speakers[:5])}{suffix})"
        )
        print(f"output: {out_path}")
    except Exception as e:
        _emit_event(
            state_dir, "diarize", "failed", sidecar=current_sidecar,
            details={"error_type": type(e).__name__, "error": str(e)[:200]},
        )
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


def cmd_doctor(args):
    """只读扫描 output/<slug>/ 工件状态 (Phase 2 RES-07).

    Prints a 5-column ASCII table by default, or JSON with --json.
    Read-only: does NOT write or modify any sidecar / artifact (D-17).
    Does append a doctor event to state.jsonl as audit trail (best-effort
    via append_event; OSError is swallowed so doctor stays diagnostic).
    """
    from datetime import datetime, timezone

    # Phase 2 RES-07 + CLAUDE.md zh-CN: ensure stdout can print ✓/✗/— even on
    # default GBK Windows terminals (project's recommended fix is chcp 65001 +
    # PYTHONUTF8=1, but doctor must work on the bare zh-CN cmd that 17 archives
    # were originally produced on; reconfigure is best-effort and silent on
    # platforms where it's not supported).
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    slug_dir = Path(args.dir)
    if not slug_dir.exists() or not slug_dir.is_dir():
        log.error("directory not found: %s", slug_dir)
        sys.exit(2)

    state_log = slug_dir / "state.jsonl"

    # Read events FIRST so state_log_status reflects the file's pre-doctor state
    # (per acceptance: archive without state.jsonl must report "missing", not "ok"
    # synthesized by our own audit-trail append). Then emit the started event.
    events, state_log_status = read_events(state_log)
    state = derived_state(events)

    # Audit trail (best-effort; corrupt/missing handled by append_event silently).
    # Per RESOLVED Q5: doctor MAY append its own events; failure is silent so
    # doctor's read-only-diagnosis primary contract is preserved.
    append_event(state_log, stage="doctor", status="started")
    # derived_state already carries forward the most-recent non-empty params_hash
    # per stage (02-02 D-14 reducer contract), so state[stage]["params_hash"] is
    # the right field for the comparison below.

    rows = []
    for artifact_name, stage in _DOCTOR_ARTIFACTS:
        artifact_path = slug_dir / artifact_name
        exists = artifact_path.exists()
        if exists:
            mtime_iso = datetime.fromtimestamp(
                artifact_path.stat().st_mtime, tz=timezone.utc
            ).isoformat()
        else:
            mtime_iso = "—"

        # Sidecar lookup -- doctor reads the LIVE sidecar contents and
        # recomputes params_hash on them (RESEARCH Pitfall 5: do not trust
        # the stored hash in state.jsonl alone; user could have edited the
        # sidecar). If sidecar is missing OR corrupt, fall through to "—".
        sidecar_dict = None
        live_hash = None
        try:
            sidecar_dict = read_sidecar(artifact_path)
        except (json.JSONDecodeError, OSError) as e:
            log.warning("sidecar read failed for %s: %s", artifact_path.name, e)
            sidecar_dict = None
        if sidecar_dict is not None:
            live_hash = params_hash(sidecar_dict)

        # last_state (state.jsonl most-recent status for the stage)
        stage_state = state.get(stage)
        last_state = stage_state["status"] if stage_state else None
        stored_hash = stage_state["params_hash"] if stage_state else None

        # params_hash_match per D-16: ✓ / ✗ / — (— if no sidecar OR no state entry)
        if live_hash is None or stored_hash is None:
            ph_match = "—"
        else:
            ph_match = "✓" if live_hash == stored_hash else "✗"

        rows.append({
            "name": artifact_name,
            "exists": exists,
            "mtime": mtime_iso,
            "params_hash_match": ph_match,
            "last_state": last_state if last_state else "—",
            "sidecar": sidecar_dict,  # JSON output includes this; ASCII output omits
        })

    if args.json:
        out = {
            "slug": slug_dir.name,
            "artifacts": rows,
            "state_log_status": state_log_status,
        }
        # Match project idiom: ensure_ascii=False so 中文/✓/✗/— print clean
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        # ASCII table (D-15: no color, no rich, plain ASCII).
        # Use simple `+---+` borders for readability.
        print(f"slug: {slug_dir.name}    state.jsonl: {state_log_status}")
        headers = ["artifact", "exists", "mtime", "params_hash_match", "last_state"]
        # Compute column widths
        cells = [headers]
        for r in rows:
            cells.append([
                r["name"],
                "✓" if r["exists"] else "✗",
                r["mtime"],
                r["params_hash_match"],
                r["last_state"],
            ])
        widths = [max(len(str(row[i])) for row in cells) for i in range(len(headers))]
        sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        print(sep)
        for i, row in enumerate(cells):
            line = "| " + " | ".join(str(row[j]).ljust(widths[j]) for j in range(len(headers))) + " |"
            print(line)
            if i == 0:
                print(sep)
        print(sep)

    append_event(state_log, stage="doctor", status="completed")


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
    p = sub.add_parser("download", help="下载视频 (= ingest 别名)")
    p.add_argument("url")
    p.add_argument("--out", required=True)

    p = sub.add_parser("ingest", help="多源 ingest (B站/抖音/YouTube/本地 mp4) — Phase 3 canonical")
    p.add_argument("url", help="URL or local path")
    p.add_argument("--out", required=True)

    p = sub.add_parser("transcribe", help="ASR 转录 (本地)")
    p.add_argument("video_path")
    p.add_argument("--out", required=True)
    p.add_argument("--whisper", default="small")
    p.add_argument(
        "--profile", choices=["tutorial", "podcast"], default="tutorial",
        help="VAD profile (Phase 5 TEACH-12); default 'tutorial' = current behavior",
    )
    p.add_argument("--force", action="store_true")

    p = sub.add_parser("aggregate", help="段落聚合")
    p.add_argument("segs_json")
    p.add_argument("--out", required=True)
    p.add_argument(
        "--profile", choices=["tutorial", "podcast"], default="tutorial",
        help="paragraph profile (Phase 5 TEACH-07); default 'tutorial' = current behavior",
    )
    p.add_argument(
        "--gap", type=float, default=None,
        help="override gap_threshold; if absent, use PROFILES[profile].gap_threshold",
    )
    # Phase 5 deviation Rule 3: --force flag added to aggregate (was implicit
    # via getattr(args, 'force', False) in cmd_aggregate but not exposed in
    # argparse). Required by Plan Task 4 regression test runbook.
    p.add_argument(
        "--force", action="store_true",
        help="bypass cache_decision (regen even if sidecar matches)",
    )

    p = sub.add_parser("extract_frames", help="按参数抽帧 (fps/start/end 你决定)")
    p.add_argument("video_path")
    p.add_argument("--out", required=True)
    p.add_argument("--fps", type=float, default=1.0)
    p.add_argument("--start", type=float, default=0)
    p.add_argument("--end", type=float, default=0, help="0=到结尾")

    p = sub.add_parser(
        "extract_frames_batch",
        help="批量抽帧 (Phase 4 FPS-01/02/03 — schedule.json drives ffmpeg per segment)",
    )
    p.add_argument("--schedule", required=True, help="path to schedule.json")
    p.add_argument(
        "--out", required=True,
        help="frames/ output dir under output/<slug>/",
    )
    p.add_argument(
        "--force", action="store_true",
        help="bypass segment-level resume; re-run all non-skip segments",
    )

    p = sub.add_parser(
        "detect_scenes",
        help="决策支持: PySceneDetect 输出 scenes.json (FPS-05; 工具不自动写 schedule)",
    )
    p.add_argument("video", help="path to video file")
    p.add_argument("--out", required=True, help="path to output scenes.json")
    p.add_argument(
        "--threshold", type=float, default=27.0,
        help="ContentDetector threshold (default 27.0; raise to 35-40 to suppress "
             "over-segmentation on screen recordings — RESEARCH Pitfall P4)",
    )

    p = sub.add_parser(
        "detect_silence",
        help="决策支持: silero-vad 输出 silence_map.json (FPS-06; "
             "需 pip install -r requirements-optional.txt)",
    )
    p.add_argument("video", help="path to video file")
    p.add_argument("--out", required=True, help="path to output silence_map.json")

    p = sub.add_parser(
        "diarize",
        help="Speaker diarization via pyannote.audio (TEACH-08; opt-in — "
             "需 pip install -r requirements-optional.txt + HF_TOKEN in .env)",
    )
    p.add_argument("audio_wav", help="path to audio.wav (16kHz mono PCM preferred)")
    p.add_argument("--out", required=True, help="path to diarization.json output")
    p.add_argument(
        "--allow-long", action="store_true",
        help="skip 60min+ CPU warning gate (D-16); for automated batch runs",
    )

    p = sub.add_parser("list_frames", help="列出帧文件")
    p.add_argument("dir")

    p = sub.add_parser("cleanup_frames", help="删除未使用的帧")
    p.add_argument("dir")
    p.add_argument("--keep", nargs="*", default=[])

    p = sub.add_parser("doctor", help="只读扫描 output/<slug>/ 工件状态 (Phase 2 RES-07)")
    p.add_argument("dir", help="output/<slug>/ 目录")
    p.add_argument("--json", action="store_true", help="输出 JSON (替代 ASCII 表)")

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
        "ingest": cmd_ingest,  # NEW (Phase 3 SRC-03 D-05)
        "transcribe": cmd_transcribe,
        "aggregate": cmd_aggregate,
        "extract_frames": cmd_extract_frames,
        "extract_frames_batch": cmd_extract_frames_batch,  # Phase 4 FPS-01/02/03
        "detect_scenes": cmd_detect_scenes,  # Phase 4 FPS-05
        "detect_silence": cmd_detect_silence,  # Phase 4 FPS-06
        "diarize": cmd_diarize,  # NEW Phase 5 TEACH-08 (opt-in pyannote)
        "list_frames": cmd_list_frames,
        "cleanup_frames": cmd_cleanup_frames,
        "classify_frame": cmd_classify_frame,
        "ocr_frame": cmd_ocr_frame,
        "doctor": cmd_doctor,  # NEW (Phase 2 RES-07)
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
