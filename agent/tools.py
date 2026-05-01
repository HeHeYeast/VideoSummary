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
        "list_frames": cmd_list_frames,
        "cleanup_frames": cmd_cleanup_frames,
        "classify_frame": cmd_classify_frame,
        "ocr_frame": cmd_ocr_frame,
        "doctor": cmd_doctor,  # NEW (Phase 2 RES-07)
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
