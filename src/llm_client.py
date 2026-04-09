"""VectorEngine 中转站客户端 (OpenAI 协议).

封装两种调用:
- chat:   纯文本对话
- vision: 多模态(图像 + 文本)

每次调用都走 BudgetGuard 守护.
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

import tiktoken
from openai import OpenAI

from .budget import BudgetGuard, BudgetExceeded

log = logging.getLogger(__name__)

# 用 cl100k_base 估 token, 对所有非 OpenAI 模型也只是估算
_ENCODER = tiktoken.get_encoding("cl100k_base")


def _count_tokens(text: str) -> int:
    return len(_ENCODER.encode(text))


def _messages_tokens(messages: list[dict]) -> int:
    total = 0
    for m in messages:
        c = m.get("content", "")
        if isinstance(c, str):
            total += _count_tokens(c)
        elif isinstance(c, list):
            for part in c:
                if part.get("type") == "text":
                    total += _count_tokens(part.get("text", ""))
                elif part.get("type") == "image_url":
                    total += 800  # 单图按 800 token 粗估
    return total


class LLMClient:
    def __init__(self, base_url: str, key_cheap: str, key_quality: str,
                 budget: BudgetGuard):
        self.budget = budget
        # 中转站经常 429, 多 retry 一些
        self.client_cheap = OpenAI(base_url=base_url, api_key=key_cheap, max_retries=5)
        self.client_quality = OpenAI(base_url=base_url, api_key=key_quality, max_retries=5)

    def _client(self, group: str) -> OpenAI:
        return self.client_cheap if group == "cheap" else self.client_quality

    def chat(self, *, stage: str, model: str, messages: list[dict],
             group: str = "cheap", max_tokens: int | None = None,
             temperature: float = 0.3) -> str:
        max_tokens = max_tokens or self.budget.max_tokens_per_call
        n_in = _messages_tokens(messages)
        est = self.budget.estimate_chat_cost(model, n_in, max_tokens, group)
        self.budget.precheck(stage, est)

        resp = self._client(group).chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        usage = resp.usage
        actual = self.budget.estimate_chat_cost(
            model, usage.prompt_tokens, usage.completion_tokens, group
        )
        self.budget.commit(
            stage, actual,
            note=f"{model} in={usage.prompt_tokens} out={usage.completion_tokens}",
        )
        msg = resp.choices[0].message
        content = msg.content or ""
        # 部分模型 (glm/qwen 思考模式) 把正文放 reasoning_content, content 是空
        if not content.strip():
            content = getattr(msg, "reasoning_content", "") or ""
        if not content.strip():
            # 某些 OpenAI 兼容代理会把内容塞 model_extra
            extra = getattr(msg, "model_extra", None) or {}
            content = extra.get("reasoning_content") or extra.get("content") or ""
        if len(content.strip()) < 50:
            log.warning("[%s] %s 返回内容过短 (%d 字符), raw=%s",
                        stage, model, len(content), repr(content)[:200])
        return content

    def vision(self, *, stage: str, model: str, prompt: str,
               image_path: str | Path, group: str = "cheap",
               max_tokens: int | None = None) -> str:
        img_b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            ],
        }]
        return self.chat(
            stage=stage, model=model, messages=messages,
            group=group, max_tokens=max_tokens or 400,
        )


def make_client(budget: BudgetGuard) -> LLMClient:
    base = os.getenv("VE_BASE_URL", "https://api.vectorengine.ai/v1")
    cheap = os.getenv("VE_KEY_CHEAP")
    quality = os.getenv("VE_KEY_QUALITY") or cheap
    if not cheap:
        raise RuntimeError("环境变量 VE_KEY_CHEAP 未设置")
    return LLMClient(base, cheap, quality, budget)
