"""结构化帧存储: JSON 持久化 + 懒加载 pass2 详情.

设计参考: AGENT_DESIGN.md §3.5

Schema per frame:
{
    "frame_id": "f0042",
    "timestamp": 327.5,
    "path": "frames/frame_000042.jpg",
    "phash": "a1b2c3d4...",
    "info_score": 8.7,
    "type": "code",
    "has_text": true,
    "brief": "GDScript 函数定义",
    "detail": null,              # pass2 懒加载
    "detail_model": null,
    "detail_cost_usd": null,
    "consumed_by": []            # 被哪些 section 引用过
}
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ── pass2 详细描述的 prompt (按类型分) ──
DETAIL_PROMPTS = {
    "code": """详细描述这一帧的代码内容 (300 字以内):
1. 完整抄录所有可见代码, 用 ``` 包裹, 逐行抄, 不要省略
2. 如果代码被截断, 标注哪里截断了
3. 注明文件名 (如果可见)
只输出描述, 不要写"这张图展示了".""",

    "slide": """详细描述这一帧的幻灯片内容 (300 字以内):
1. 提取所有可见文字 (标题、列表项、公式), 原样抄录
2. 描述版面布局
只输出描述.""",

    "diagram": """详细描述这一帧的图表内容 (300 字以内):
1. 图表类型 (流程图/架构图/时序图/...)
2. 所有节点和连线的文字标签
3. 关键数值
只输出描述.""",

    "ui_demo": """详细描述这一帧的界面操作 (200 字以内):
1. 哪个软件/面板
2. 正在做什么操作
3. 关键属性值
只输出描述.""",

    "_default": """用中文描述这一帧画面内容 (100 字以内).
屏幕上的关键文字原样抄录. 不要写废话.""",
}


@dataclass
class FrameRecord:
    frame_id: str
    timestamp: float
    path: str
    phash: str = ""
    info_score: float = 0.0
    type: str = "transition"
    has_text: bool = False
    brief: str = ""
    detail: str | None = None
    detail_model: str | None = None
    detail_cost_usd: float | None = None
    consumed_by: list[str] = field(default_factory=list)


class FrameStore:
    """JSON 持久化的帧存储."""

    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.frames: dict[str, FrameRecord] = {}
        if self.store_path.exists():
            self._load()

    def _load(self):
        data = json.loads(self.store_path.read_text(encoding="utf-8"))
        for d in data:
            fr = FrameRecord(**{k: v for k, v in d.items()
                                if k in FrameRecord.__dataclass_fields__})
            self.frames[fr.frame_id] = fr
        log.info("frame_store loaded: %d frames from %s",
                 len(self.frames), self.store_path)

    def save(self):
        """全量写回磁盘."""
        data = [asdict(fr) for fr in sorted(
            self.frames.values(), key=lambda f: f.timestamp
        )]
        self.store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add(self, fr: FrameRecord):
        self.frames[fr.frame_id] = fr

    def get(self, frame_id: str) -> FrameRecord | None:
        return self.frames.get(frame_id)

    def find_nearest(self, timestamp: float) -> FrameRecord | None:
        """找时间戳最接近的帧."""
        if not self.frames:
            return None
        return min(self.frames.values(),
                   key=lambda f: abs(f.timestamp - timestamp))

    def list_frames(self, type_filter: str | None = None,
                    time_range: tuple[float, float] | None = None,
                    exclude_types: set[str] | None = None,
                    ) -> list[dict]:
        """列出帧摘要 (id + ts + type + brief), 不返回 detail/path/embedding.

        AGENT_DESIGN.md §5.10: 工具返回要控制长度.
        """
        exclude = exclude_types or set()
        results = []
        for fr in sorted(self.frames.values(), key=lambda f: f.timestamp):
            if type_filter and fr.type != type_filter:
                continue
            if fr.type in exclude:
                continue
            if time_range:
                if fr.timestamp < time_range[0] or fr.timestamp > time_range[1]:
                    continue
            results.append({
                "frame_id": fr.frame_id,
                "timestamp": fr.timestamp,
                "type": fr.type,
                "has_text": fr.has_text,
                "brief": fr.brief,
                "has_detail": fr.detail is not None,
                "info_score": round(fr.info_score, 1),
            })
        return results

    def get_frame_detail(self, frame_id: str, client: Any = None,
                         model: str = "qwen3-vl-plus") -> str | None:
        """懒加载 pass2 详情. 首次调用花钱, 之后命中缓存.

        AGENT_DESIGN.md §5.1: get_frame_detail 的持久化缓存.
        """
        fr = self.frames.get(frame_id)
        if fr is None:
            return None
        if fr.detail is not None:
            return fr.detail

        # pass2: 调用视觉模型
        if client is None:
            log.warning("get_frame_detail: no client, cannot do pass2")
            return None

        prompt = DETAIL_PROMPTS.get(fr.type, DETAIL_PROMPTS["_default"])
        try:
            detail = client.vision(
                stage="vision",
                model=model,
                prompt=prompt,
                image_path=fr.path,
                group="cheap",
                max_tokens=500,
            )
            fr.detail = detail.strip()
            fr.detail_model = model
            self.save()  # 立即写回磁盘
            return fr.detail
        except Exception as e:
            log.warning("pass2 详情获取失败 %s: %s", fr.path, e)
            return None

    def mark_consumed(self, frame_id: str, section_id: str):
        """标记帧被某个 section 引用."""
        fr = self.frames.get(frame_id)
        if fr and section_id not in fr.consumed_by:
            fr.consumed_by.append(section_id)

    def __len__(self):
        return len(self.frames)
