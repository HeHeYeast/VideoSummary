"""K5 read-only fps-segment suggestion emitter (Phase 07 TOOL-B).

K5 boundary: emits suggested segments + meta; Claude reads, edits overlaps,
and writes the final schedule artifact. The mandatory FPS-04 silence-coverage
baseline (a low-fps pass covering full duration) is included in suggestions
so Claude doesn't accidentally violate the strict-OR-fallback gate.

Source code MUST NOT reference the schedule artifact filename literally —
phrase as "the schedule artifact" instead. K5 source-grep test enforces this.
"""
from __future__ import annotations

import logging

log = logging.getLogger(__name__)

SUGGESTION_FILENAME = "schedule_suggestion.json"

_BASELINE_FPS = 0.05            # FPS-04 baseline (must be <= 0.1)
_DEFAULT_FPS = 0.1               # fallback for talkthrough segments
_DENSE_CUTS_FPS = 0.4            # when scenes input has many cuts in a window
_FLAGGED_SILENCE_FPS = 0.05      # when silence_map flags a span


def compute_suggestion(
    paragraphs: list,
    *,
    scenes: list | None = None,
    silence_map: list | None = None,
    duration_s: float,
    video_filename: str = "video.mp4",
    duration_source: str = "ffprobe",
) -> dict:
    """Generate suggested fps-segments + mandatory FPS-04 baseline.

    Args:
        paragraphs: parsed paragraphs (top-level list)
        scenes:     parsed scenes input ("scenes" array; optional)
        silence_map: parsed silence intervals (optional)
        duration_s:  full video duration in seconds
        video_filename: filename for the suggestion artifact's `video` key
        duration_source: provenance string for suggestion_meta
                         ("ffprobe" or "--duration-override")

    Returns dict matching the locked schema (see Phase 07 03-PLAN interfaces section).
    """
    suggested: list[dict] = []
    scene_cut_count = len(scenes) if scenes else 0
    flagged_silences = (
        sum(1 for iv in (silence_map or []) if iv.get("flagged_for_review"))
        if silence_map else 0
    )

    # 1. Coarse default segment covering full duration at default fps
    suggested.append({
        "start": 0.0,
        "end": float(duration_s),
        "fps": _DEFAULT_FPS,
        "label": "default-coverage",
        "rationale": "fallback default coverage; Claude will refine into denser/sparser segments",
    })

    # 2. Dense-cut windows from scenes (if available) — naive: bucket scene cuts
    #    into 60s windows; any window with >= 4 cuts -> suggest fps 0.4
    if scenes:
        windows: dict[int, int] = {}
        for sc in scenes:
            window_idx = int(sc.get("start", 0) // 60)
            windows[window_idx] = windows.get(window_idx, 0) + 1
        for window_idx, cnt in sorted(windows.items()):
            if cnt >= 4:
                suggested.append({
                    "start": float(window_idx * 60),
                    "end": float(min((window_idx + 1) * 60, duration_s)),
                    "fps": _DENSE_CUTS_FPS,
                    "label": "code-demo",
                    "rationale": f"{cnt} scene cuts in this 60s window — likely code/UI demo",
                })

    # 3. Flagged silence segments (silence input opt-in)
    if silence_map:
        for iv in silence_map:
            if iv.get("flagged_for_review"):
                suggested.append({
                    "start": float(iv.get("start", 0.0)),
                    "end": float(iv.get("end", 0.0)),
                    "fps": _FLAGGED_SILENCE_FPS,
                    "label": "talkthrough",
                    "rationale": "silence > 5s — likely talkthrough/explanation",
                })

    # 4. MANDATORY FPS-04 baseline — covers full duration at low fps so Claude
    #    cannot accidentally produce a strict-only schedule artifact that fails
    #    the silence-coverage gate (CONTEXT D-08 strict-OR-fallback).
    suggested.append({
        "start": 0.0,
        "end": float(duration_s),
        "fps": _BASELINE_FPS,
        "label": "fps-04-baseline",
        "rationale": "mandatory FPS-04 silence-coverage fallback (Claude may keep this OR replace with strict per-segment coverage)",
    })

    return {
        "version": 1,
        "video": video_filename,
        "duration_s": float(duration_s),
        "suggested_segments": suggested,
        "suggestion_meta": {
            "scene_cut_count": scene_cut_count,
            "flagged_silences": flagged_silences,
            "uses_silence_map": silence_map is not None,
            "uses_scenes_json": scenes is not None,
            "duration_source": duration_source,
        },
    }
