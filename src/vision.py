"""关键帧视觉描述. 每帧调用一次视觉模型, 受 BudgetGuard 守护."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from .frames import Frame
from .llm_client import LLMClient
from .budget import BudgetExceeded

log = logging.getLogger(__name__)


VISION_PROMPT = """用中文极简描述这一帧画面内容, 严格控制在 80 字以内.
- 屏幕上的关键文字 (标题/菜单/重要正文)
- 如果是代码, 只截取最关键 3-5 行
- 如果是 UI 操作, 一句话说在做什么
- 不要写"这张图展示了"等废话, 直接给内容
- 严禁超过 80 字"""


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
                max_tokens=200,
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
