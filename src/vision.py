"""关键帧视觉描述. 每帧调用一次视觉模型, 受 BudgetGuard 守护."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .frames import Frame
from .llm_client import LLMClient
from .budget import BudgetExceeded

log = logging.getLogger(__name__)


VISION_PROMPT = """用中文描述这一帧画面内容 (300 字以内).

按以下优先级描述:
1. **代码/命令行**: 完整抄录所有可见代码, 用 ``` 包裹. 不要概括, 不要省略, 逐行抄.
2. **PPT/幻灯片**: 提取所有可见文字 (标题、列表项、公式).
3. **UI 操作**: 具体描述在哪个面板/菜单做了什么操作, 涉及哪些属性值.
4. **普通画面**: 一句话说在做什么即可.

不要写"这张图展示了"等废话, 直接给内容."""


@dataclass
class FrameDescription:
    timestamp: float
    path: str
    description: str


def describe_frames(frames: list[Frame], client: LLMClient,
                    model: str = "qwen3-vl-plus") -> list[FrameDescription]:
    out: list[FrameDescription] = []
    for f in frames:
        try:
            desc = client.vision(
                stage="vision",
                model=model,
                prompt=VISION_PROMPT,
                image_path=f.path,
                group="cheap",
                max_tokens=500,
            )
            out.append(FrameDescription(
                timestamp=f.timestamp, path=f.path, description=desc.strip()
            ))
        except BudgetExceeded as e:
            log.warning("视觉预算耗尽, 提前停止: %s", e)
            break
        except Exception as e:
            log.error("视觉调用失败 %s: %s", f.path, e)
    log.info("视觉描述完成: %d/%d", len(out), len(frames))
    return out
