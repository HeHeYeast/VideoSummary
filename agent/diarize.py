"""Speaker diarization via pyannote.audio (opt-in via requirements-optional.txt).

Phase 5 TEACH-08 / D-13..D-17.

Lazy-imports pyannote.audio so missing dep raises a clean RuntimeError with
install hint (matches Phase 4 detect_silence opt-in idiom — see
agent/silence.py + agent/tools.py:cmd_detect_silence).

NOTE: pyannote 4.0 model `pyannote/speaker-diarization-community-1` requires:
  1. user accept license at HF model card
     https://huggingface.co/pyannote/speaker-diarization-community-1
  2. HF_TOKEN env var (read by caller from .env via load_dotenv())

Output schema (D-13):
  [{"start": <float>, "end": <float>, "speaker_id": "SPEAKER_NN"}, ...]

Threat model (T-05-03-08): never log hf_token value; only log presence.
"""
from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


def diarize_audio(
    audio_path: str | Path,
    *,
    hf_token: str,
    allow_long: bool = False,
) -> list[dict]:
    """Run pyannote speaker diarization on a wav file.

    Args:
        audio_path: path to audio.wav (16kHz mono PCM preferred)
        hf_token: HuggingFace API token (read by caller from .env HF_TOKEN)
        allow_long: passthrough flag (caller should have already gated on duration)

    Returns:
        list of {"start": float, "end": float, "speaker_id": str} dicts
        (sorted by start time, schema-locked at D-13)

    Raises:
        RuntimeError: pyannote.audio not installed (clean install hint)
        RuntimeError: audio file not found
        RuntimeError: HF model load failed (license not accepted / token invalid)
    """
    try:
        # Lazy import — keep agent/diarize.py importable even when pyannote not installed.
        # Mirrors Phase 4 silero-vad opt-in idiom in agent/silence.py.
        from pyannote.audio import Pipeline
    except ImportError as e:
        raise RuntimeError(
            "pyannote.audio not installed; install via "
            "`pip install -r requirements-optional.txt` (~700MB torch dep)"
        ) from e

    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise RuntimeError(f"audio file not found: {audio_path}")

    # T-05-03-08 mitigation: never log hf_token value; only log whether it's set.
    log.info(
        "loading pyannote/speaker-diarization-community-1 (HF_TOKEN: %s)",
        "<set>" if hf_token else "<empty>",
    )

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1",
            use_auth_token=hf_token,
        )
    except Exception as e:
        raise RuntimeError(
            "failed to load pyannote model; verify HF token + community-1 license accepted "
            "at https://huggingface.co/pyannote/speaker-diarization-community-1: "
            f"{e}"
        ) from e

    log.info("running diarization on %s (allow_long=%s)", audio_path, allow_long)
    diarization = pipeline(str(audio_path))

    turns: list[dict] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append({
            "start": float(turn.start),
            "end": float(turn.end),
            "speaker_id": str(speaker),
        })
    log.info("diarization complete: %d turns", len(turns))
    return turns
