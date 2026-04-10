"""ASR 后处理: 段落聚合.

把 faster-whisper 输出的细粒度 segments 合并成"段落"(paragraph),
基于静音间隔 > gap_threshold 或句末标点切分.

设计参考: AGENT_DESIGN.md §3.1
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Paragraph:
    para_id: str
    start: float
    end: float
    text: str
    seg_indices: list[int] = field(default_factory=list)  # 原始 segment 的索引


# 英文句末标点 + 中文句末标点
_SENTENCE_END = re.compile(r"[.!?。！？…]+\s*$")


def aggregate_paragraphs(
    segs: list[dict],
    gap_threshold: float = 1.5,
    max_para_duration: float = 30.0,
) -> list[Paragraph]:
    """将原始 segments 聚合成段落.

    Args:
        segs: list of {start, end, text} dicts (从 segs.json 加载)
        gap_threshold: 两个 segment 之间静音间隔超过此值则切段落
        max_para_duration: 单个段落最大时长, 超过强制切分

    Returns:
        list of Paragraph
    """
    if not segs:
        return []

    paragraphs: list[Paragraph] = []
    current_texts: list[str] = []
    current_indices: list[int] = []
    current_start: float = segs[0]["start"]
    current_end: float = segs[0]["end"]

    def _flush():
        if not current_texts:
            return
        text = " ".join(current_texts).strip()
        if text:
            paragraphs.append(Paragraph(
                para_id=f"p{len(paragraphs):04d}",
                start=current_start,
                end=current_end,
                text=text,
                seg_indices=list(current_indices),
            ))

    for i, seg in enumerate(segs):
        s_start = seg["start"]
        s_end = seg["end"]
        s_text = seg["text"].strip()
        if not s_text:
            continue

        # 判断是否需要切分段落
        should_split = False
        if current_texts:
            gap = s_start - current_end
            duration = s_end - current_start
            # 条件1: 静音间隔超过阈值
            if gap > gap_threshold:
                should_split = True
            # 条件2: 前一句以句末标点结尾 且 间隔 > 0.8s
            elif gap > 0.8 and _SENTENCE_END.search(current_texts[-1]):
                should_split = True
            # 条件3: 段落时长超过上限
            elif duration > max_para_duration:
                should_split = True

        if should_split:
            _flush()
            current_texts = []
            current_indices = []
            current_start = s_start

        current_texts.append(s_text)
        current_indices.append(i)
        current_end = s_end

    _flush()
    return paragraphs


def paragraphs_to_dicts(paras: list[Paragraph]) -> list[dict]:
    """序列化为 JSON 友好的 dict list."""
    return [asdict(p) for p in paras]


def get_transcript_window(
    paras: list[Paragraph],
    start_sec: float,
    end_sec: float,
    max_chars: int = 3000,
) -> str:
    """获取指定时间段的段落文本, 自动对齐到段落边界.

    AGENT_DESIGN.md §4.1: get_transcript_window 按段落边界对齐返回.
    """
    window_paras = [
        p for p in paras
        if p.end > start_sec and p.start < end_sec
    ]
    lines = []
    total = 0
    for p in window_paras:
        m, s = divmod(int(p.start), 60)
        h, m = divmod(m, 60)
        line = f"[{h:02d}:{m:02d}:{s:02d}] {p.text}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)


def search_transcript(
    paras: list[Paragraph],
    keyword: str,
    max_results: int = 10,
) -> list[dict]:
    """在段落中搜索关键词, 返回匹配的时间段.

    AGENT_DESIGN.md §4.1: search_transcript 关键词检索.
    """
    results = []
    kw = keyword.lower()
    for p in paras:
        if kw in p.text.lower():
            results.append({
                "para_id": p.para_id,
                "start": p.start,
                "end": p.end,
                "text": p.text[:200],
            })
            if len(results) >= max_results:
                break
    return results
