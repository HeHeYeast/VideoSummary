"""silero-vad wrapper for FPS-06 decision support.

Phase 4 D-19..D-22 (with CONTEXT D-22 corrected per RESEARCH §"CRITICAL:
silero-vad's torch dependency"): the standalone `silero-vad` PyPI package
depends on torch>=1.12.0 + torchaudio>=0.12.0 (~700MB) and is NOT a
transitive dep of faster-whisper (faster-whisper bundles its own
SileroVADModel via onnxruntime, but does not surface speech_timestamps).
Therefore silero-vad lives in requirements-optional.txt; this module
lazy-imports and raises a clean RuntimeError with the install hint when
absent.

Decision-support only — Claude reads the silence-map artifact when authoring
the schedule artifact; the tool NEVER auto-promotes silence intervals into
segments (K5 — see CONTEXT line 10 + PROJECT.md "Decision authority").

K5 enforcement note: the cmd_detect_silence handler in agent/tools.py
must NOT contain the literal substring of the schedule artifact filename
(static-source check in tests). Discussions of FPS-04 coverage hints in
the stdout message do mention "the schedule artifact" / "fps segment"
generically, but never the literal filename.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)


def _invert_speech_to_silence(speech_ts: list[dict], duration_s: float) -> list[dict]:
    """Return silence intervals = gaps between speech intervals + leading + trailing.

    Pitfall P7-safe: handles both leading silence (before first speech) and
    trailing silence (after last speech) explicitly. Each returned dict has
    keys {start, end} as plain floats; caller adds duration + flag.
    """
    silences: list[dict] = []
    cursor = 0.0
    for s in speech_ts:
        if s["start"] > cursor:
            silences.append({"start": cursor, "end": s["start"]})
        cursor = max(cursor, s["end"])
    if cursor < duration_s:
        silences.append({"start": cursor, "end": duration_s})
    return silences


def detect_silence(audio_path: str | Path, *, duration_s: float,
                   flag_threshold_s: float = 5.0) -> list[dict]:
    """Run silero-vad on a 16kHz wav file. Return silence intervals.

    Each interval has keys {start, end, duration}; intervals with
    duration > flag_threshold_s additionally have flagged_for_review: true
    (per FPS-06 + D-20).

    Lazy-imports silero_vad — missing-package error gets a clean recovery hint.
    """
    try:
        from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
    except ImportError as e:
        raise RuntimeError(
            "detect_silence requires silero-vad (and torch ~700MB). "
            "Install with: pip install -r requirements-optional.txt"
        ) from e

    model = load_silero_vad()
    wav = read_audio(str(audio_path))
    speech_ts_raw = get_speech_timestamps(wav, model, return_seconds=True)
    # Normalize to dicts of float (silero may return tensors)
    speech_ts = [
        {"start": float(t["start"]), "end": float(t["end"])}
        for t in speech_ts_raw
    ]

    silences = _invert_speech_to_silence(speech_ts, duration_s)

    result: list[dict] = []
    for iv in silences:
        duration = iv["end"] - iv["start"]
        entry = {"start": iv["start"], "end": iv["end"], "duration": duration}
        if duration > flag_threshold_s:
            entry["flagged_for_review"] = True
        result.append(entry)
    return result


def ensure_audio_wav(video_path: str | Path, slug_dir: Path) -> Path:
    """Return path to a 16kHz mono wav extracted from the video.

    Pitfall P5: silero-vad accepts only 8kHz/16kHz. If output/<slug>/audio.wav
    exists (produced by cmd_transcribe), reuse it. Otherwise extract to a
    tempfile under slug_dir.
    """
    existing = Path(slug_dir) / "audio.wav"
    if existing.exists():
        log.info("reusing existing audio.wav at %s", existing)
        return existing

    fd, name = tempfile.mkstemp(
        suffix=".wav", dir=str(slug_dir),
        prefix=".tmp.detect_silence.",
    )
    # Close fd; ffmpeg writes via path. mkstemp returns an open fd we don't need.
    import os as _os
    _os.close(fd)
    tmp_path = Path(name)
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-ac", "1", "-ar", "16000", "-vn",
        "-c:a", "pcm_s16le", str(tmp_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return tmp_path
