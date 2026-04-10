"""帧 Pass1 分类: 便宜视觉模型做快速分类 + 简述.

每帧产出:
  type: code | slide | diagram | ui_demo | talking_head | transition
  has_text: bool
  brief: ≤30 字简述

设计参考: AGENT_DESIGN.md §3.3
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from src.llm_client import LLMClient
from src.budget import BudgetExceeded

log = logging.getLogger(__name__)

CLASSIFY_PROMPT = """对这一帧画面做两件事:

1. 分类 (只输出一个类型标签):
   - code: 屏幕上显示代码/命令行/终端
   - slide: PPT/幻灯片/带标题的演示文稿
   - diagram: 图表/流程图/架构图
   - ui_demo: 软件界面操作演示(非代码编辑器)
   - talking_head: 讲师出镜/摄像头画面
   - transition: 转场/片头/片尾/无信息画面

2. 简述 (≤30字, 一句话说画面内容)

严格按以下格式输出, 不要加任何其他内容:
TYPE: <类型>
HAS_TEXT: <true|false>
BRIEF: <简述>"""


@dataclass
class FrameClassification:
    frame_id: str
    timestamp: float
    path: str
    type: str = "transition"
    has_text: bool = False
    brief: str = ""


def _parse_classification(raw: str) -> tuple[str, bool, str]:
    """从模型输出解析分类结果."""
    type_ = "transition"
    has_text = False
    brief = ""

    for line in raw.strip().splitlines():
        line = line.strip()
        if line.upper().startswith("TYPE:"):
            val = line.split(":", 1)[1].strip().lower()
            valid = {"code", "slide", "diagram", "ui_demo", "talking_head", "transition"}
            type_ = val if val in valid else "transition"
        elif line.upper().startswith("HAS_TEXT:"):
            val = line.split(":", 1)[1].strip().lower()
            has_text = val in ("true", "yes", "1")
        elif line.upper().startswith("BRIEF:"):
            brief = line.split(":", 1)[1].strip()[:60]

    return type_, has_text, brief


def classify_frames(
    frames: list[dict],
    client: LLMClient,
    model: str = "qwen3-vl-plus",
) -> list[FrameClassification]:
    """对所有帧做 pass1 分类.

    Args:
        frames: list of {frame_id, timestamp, path, ...}
        client: LLM 客户端 (走 vision 接口)
        model: 视觉模型名

    Returns:
        list of FrameClassification
    """
    results: list[FrameClassification] = []

    for f in frames:
        fc = FrameClassification(
            frame_id=f.get("frame_id", ""),
            timestamp=f["timestamp"],
            path=f["path"],
        )
        try:
            raw = client.vision(
                stage="vision",
                model=model,
                prompt=CLASSIFY_PROMPT,
                image_path=f["path"],
                group="cheap",
                max_tokens=100,  # 分类只需极少 token
            )
            fc.type, fc.has_text, fc.brief = _parse_classification(raw)
        except BudgetExceeded:
            log.warning("pass1 分类预算耗尽, 剩余帧标记为 transition")
            results.append(fc)
            # 剩余帧填默认值
            for f2 in frames[frames.index(f) + 1:]:
                results.append(FrameClassification(
                    frame_id=f2.get("frame_id", ""),
                    timestamp=f2["timestamp"],
                    path=f2["path"],
                ))
            break
        except Exception as e:
            log.warning("pass1 分类失败 %s: %s", f["path"], e)

        results.append(fc)

    log.info("pass1 分类完成: %d 帧 → %s",
             len(results),
             {t: sum(1 for r in results if r.type == t)
              for t in {"code", "slide", "diagram", "ui_demo", "talking_head", "transition"}})
    return results
