"""PySceneDetect wrapper for FPS-05 decision support.

Phase 4 D-15..D-18. Decision-support only — Claude reads the resulting
scenes artifact when authoring the schedule artifact; the tool NEVER
auto-promotes scenes into segments (K5 — see CONTEXT line 10 +
PROJECT.md "Decision authority").

K5 enforcement note: the cmd_detect_scenes handler in agent/tools.py
must NOT contain the literal substring of the schedule artifact filename
(static-source check in tests). This module is independent: it returns
the scenes list and the caller writes the JSON.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def detect_scenes(video_path: str | Path, *, threshold: float = 27.0) -> list[dict]:
    """Run PySceneDetect ContentDetector. Return list of {start, end} (seconds).

    Default threshold 27.0 per PySceneDetect docs. Tutorial / screen-recording
    videos may need 30-40 to suppress micro-changes (cursor blink, syntax
    highlight refresh) — RESEARCH Pitfall P4. Stdout in cmd_detect_scenes
    reports total count + median duration so Claude can immediately tell if
    results are over-segmented (median < 2s = re-run with --threshold 35).

    The scenedetect import is deferred so module import doesn't require
    PySceneDetect — tests that don't actually exercise the algorithm can
    monkey-patch sys.modules cleanly.
    """
    from scenedetect import detect, ContentDetector
    raw = detect(str(video_path), ContentDetector(threshold=threshold))
    return [
        {"start": float(start.get_seconds()), "end": float(end.get_seconds())}
        for start, end in raw
    ]
