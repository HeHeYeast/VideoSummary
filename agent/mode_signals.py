"""K5 read-only mode-classification signal emitter (Phase 07 TOOL-A).

K5 boundary (PITFALLS P-07 locked): emits objective signals + raw evidence;
NO `recommended_mode` field. Claude maps signals -> mode in the plan
artifact, not this tool.

Source code MUST NOT reference the plan/summary/schedule artifact filenames
literally — phrase as "the plan artifact" / "the summary artifact" instead.
The K5 source-grep test (tests/test_k5_emitters.py) enforces this.
"""
from __future__ import annotations

import hashlib
import json
import re

SIGNALS_FILENAME = "mode_signals.json"

_CODE_FENCE_RE = re.compile(r"```\w*")
_STEP_MARKER_RE = re.compile(r"第[一二三四五六七八九十百\d]+步|步骤\s*\d+|Step\s*\d+", re.IGNORECASE)
_QUESTION_RE = re.compile(r"[？\?]")
_SENTENCE_SPLIT_RE = re.compile(r"[。!！?？]")
_INTRO_PHRASE_RE = re.compile(r"今天嘉宾|今天请到|有请|你怎么看|你认为")
_CROSS_TOOL_RE = re.compile(r"\bvs\b|对比|相比|区别", re.IGNORECASE)
_EVIDENCE_CAP = 5  # max evidence_paragraphs per signal


def _para_text(p) -> str:
    """Extract text from a paragraph dict (paragraphs.json shape).
    Tolerant: paragraphs may have 'text' or 'content' field across versions."""
    if isinstance(p, dict):
        return p.get("text") or p.get("content") or ""
    if isinstance(p, str):
        return p
    return ""


def _hash_paragraphs(paragraphs: list) -> str:
    payload = json.dumps(paragraphs, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def compute_signals(paragraphs: list) -> dict:
    """Compute the 5 mode-classification signals from paragraphs data.

    Returns dict matching the locked schema (see Phase 07 03-PLAN interfaces section).
    NEVER includes `recommended_mode` — Claude decides.
    """
    n = len(paragraphs)
    n_safe = max(n, 1)

    code_fence_evidence: list[int] = []
    code_fence_count = 0
    step_evidence: list[int] = []
    step_count = 0
    question_evidence: list[int] = []
    question_count = 0
    sentence_count = 0
    intro_evidence: list[int] = []
    intro_count = 0
    cross_tool_evidence: list[int] = []
    cross_tool_count = 0

    for idx, p in enumerate(paragraphs):
        text = _para_text(p)
        if not text:
            continue

        cf = len(_CODE_FENCE_RE.findall(text))
        if cf > 0:
            code_fence_count += cf
            if len(code_fence_evidence) < _EVIDENCE_CAP:
                code_fence_evidence.append(idx)

        sm = len(_STEP_MARKER_RE.findall(text))
        if sm > 0:
            step_count += sm
            if len(step_evidence) < _EVIDENCE_CAP:
                step_evidence.append(idx)

        q = len(_QUESTION_RE.findall(text))
        if q > 0:
            question_count += q
            if len(question_evidence) < _EVIDENCE_CAP:
                question_evidence.append(idx)
        sentence_count += len([s for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()])

        ip = len(_INTRO_PHRASE_RE.findall(text))
        if ip > 0:
            intro_count += ip
            if len(intro_evidence) < _EVIDENCE_CAP:
                intro_evidence.append(idx)

        ct = len(_CROSS_TOOL_RE.findall(text))
        if ct > 0:
            cross_tool_count += ct
            if len(cross_tool_evidence) < _EVIDENCE_CAP:
                cross_tool_evidence.append(idx)

    return {
        "code_fence_density": {
            "per_paragraph": round(code_fence_count / n_safe, 4),
            "raw_count": code_fence_count,
            "evidence_paragraphs": code_fence_evidence,
        },
        "step_marker_density": {
            "per_paragraph": round(step_count / n_safe, 4),
            "raw_count": step_count,
            "evidence_paragraphs": step_evidence,
        },
        "question_form_ratio": {
            "per_paragraph": round(question_count / n_safe, 4),
            "raw_count": question_count,
            "sentences_total": sentence_count,
            "evidence_paragraphs": question_evidence,
        },
        "speaker_turn_signals": {
            "intro_phrase_count": intro_count,
            "evidence_paragraphs": intro_evidence,
        },
        "cross_tool_comparison_count": {
            "count": cross_tool_count,
            "evidence_paragraphs": cross_tool_evidence,
        },
    }
