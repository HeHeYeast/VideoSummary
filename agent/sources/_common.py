"""Shared helpers for source classes. Phase 3 SRC-04.

Centralizes the "append new fields after legacy 7-key prefix" pattern so all
sources construct meta.json the same way. Key order preservation guaranteed by
PEP 468 (Python 3.7+ dict insertion order).
"""
from __future__ import annotations


def append_phase3_fields(legacy_meta: dict, *, source: str,
                         subtitle_origin: str = "none",
                         youtube_id: str | None = None) -> dict:
    """Append Phase 3 additive fields after legacy keys.

    Per RESEARCH §"Byte-Identical Regression Strategy": legacy 7 keys
    (or 9 for douyin) appear FIRST in their original order; new fields
    appear AT THE END. Uses {**a, ...} spread which preserves a's order
    (PEP 468 verified).

    Returns a NEW dict; does not mutate legacy_meta.

    NOTE: if legacy_meta already contains a key in the extras (e.g. douyin
    downloader writes "source": "douyin"), the {**a, **b} spread overwrites
    the value while preserving the ORIGINAL key position from legacy_meta.
    This is desired — keeps the douyin 9-key prefix shape stable.
    """
    extras: dict = {"source": source}
    if youtube_id is not None:
        extras["youtube_id"] = youtube_id
    extras["subtitle_origin"] = subtitle_origin
    return {**legacy_meta, **extras}
