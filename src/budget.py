"""预算守护与价格表。

设计要点:
- 平台结算单位是 USD; PRICE_TABLE 全部用 USD per 1M tokens.
- 用户配置的预算单位是 CNY (更直观); 加载时按 CNY_PER_USD 转成 USD.
- 每次 LLM 调用前 precheck (按 tiktoken 估算), 调用后 commit (按真实 usage).
- 超限立刻抛 BudgetExceeded, 由上层决定继续还是退出.

价格全部为估算值, 偏保守(略偏高 ~20%). 首次跑完应去后台对账校准.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)

CNY_PER_USD = 7.2  # 估算汇率, 可在 .env 覆盖

# USD per 1M tokens, 形如 (input_price, output_price)
# 数据来源: 用户从 https://api.vectorengine.ai/pricing 抄来 (2026-04)
# 取每个模型"最便宜的那一档" (假设 cheap key 命中该档; 实际若不命中, 测试时校准)
PRICE_TABLE: dict[str, tuple[float, float]] = {
    # ── 文本 ─────────────────────────────────────
    "gpt-4o-mini":             (0.09, 0.36),    # ⭐ 最便宜文本, map/reduce 主力
    "glm-4.5-air":             (0.60, 2.40),    # critique 用 (换家族)
    "glm-4.6":                 (1.20, 4.80),
    "deepseek-v3.2":           (1.20, 1.80),    # 比直觉贵很多, 备选
    "deepseek-v3.1":           (2.40, 7.20),    # 比 v3.2 还贵, 不推荐
    "gemini-2.5-pro":          (1.00, 8.00),    # 精修档
    # ── 视觉 (按 token 计) ───────────────────────
    "gemini-2.5-flash":        (0.24, 2.002),   # 思考模式下输出会超 max_tokens
    "gemini-3-flash-preview-nothinking": (0.24, 2.002),  # 估算同 2.5-flash, 跑完校准
    "qwen3-vl-plus":           (0.60, 6.00),    # 视觉备选
    "qwen-vl-max":             (0.96, 2.40),    # output 便宜, 长描述场景备用
}

# ASR 单价 (来自 vectorengine 实际价格, 按 token 计)
# 注: 在该平台 ASR 也按 1M tokens 计费而非分钟; 这里给的是每 1M tokens USD
ASR_PRICE_PER_1M = {
    "whisper-1":            18.0,    # 不推荐, 贵
    "gpt-4o-transcribe":    1.5,     # input 价
    "gpt-4o-mini-transcribe": 0.75,  # 估算
}

# 倍率: 已经把"最便宜档"写进 PRICE_TABLE, 所以这里都用 1.0
# 若以后区分 cheap / quality key 实际命中的档位, 再启用
GROUP_MULTIPLIER = {
    "cheap":   1.0,
    "quality": 1.0,
}


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class BudgetGuard:
    total_usd: float
    stage_limits_usd: dict[str, float]
    call_limits: dict[str, int]
    fail_fast: bool = True
    max_tokens_per_call: int = 2000
    frame_cap: int = 50
    chapter_cap: int = 8

    spent_usd: float = 0.0
    spent_per_stage: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    calls_per_stage: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    log_lines: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "BudgetGuard":
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        total_usd = cfg["total_budget_cny"] / CNY_PER_USD
        stage_usd = {k: v / CNY_PER_USD for k, v in cfg["stage_limits"].items()}
        return cls(
            total_usd=total_usd,
            stage_limits_usd=stage_usd,
            call_limits=cfg["call_limits"],
            fail_fast=cfg.get("fail_fast", True),
            max_tokens_per_call=cfg.get("max_tokens_per_call", 2000),
            frame_cap=cfg.get("frame_cap", 50),
            chapter_cap=cfg.get("chapter_cap", 8),
        )

    # ---------- 估算 ----------
    @staticmethod
    def estimate_chat_cost(model: str, n_input_tokens: int, n_output_tokens: int,
                           group: str = "cheap") -> float:
        if model not in PRICE_TABLE:
            log.warning("未知模型 %s, 按 1.0/3.0 USD/M 估算", model)
            pin, pout = 1.0, 3.0
        else:
            pin, pout = PRICE_TABLE[model]
        mult = GROUP_MULTIPLIER.get(group, 1.0)
        return (n_input_tokens * pin + n_output_tokens * pout) * mult / 1_000_000

    @staticmethod
    def estimate_asr_cost(model: str, audio_minutes: float) -> float:
        return ASR_PRICE_PER_MIN.get(model, 0.006) * audio_minutes

    # ---------- 守护 ----------
    def precheck(self, stage: str, est_cost_usd: float) -> None:
        if self.calls_per_stage[stage] >= self.call_limits.get(stage, 0):
            raise BudgetExceeded(
                f"[{stage}] 调用次数已达上限 {self.call_limits.get(stage, 0)}"
            )
        if self.spent_per_stage[stage] + est_cost_usd > self.stage_limits_usd.get(stage, 0):
            raise BudgetExceeded(
                f"[{stage}] 阶段预算超出: "
                f"已花 ${self.spent_per_stage[stage]:.4f} + 估 ${est_cost_usd:.4f} "
                f"> 上限 ${self.stage_limits_usd.get(stage, 0):.4f}"
            )
        if self.spent_usd + est_cost_usd > self.total_usd:
            raise BudgetExceeded(
                f"总预算超出: 已花 ${self.spent_usd:.4f} + 估 ${est_cost_usd:.4f} "
                f"> 上限 ${self.total_usd:.4f}"
            )

    def commit(self, stage: str, actual_cost_usd: float, note: str = "") -> None:
        self.spent_usd += actual_cost_usd
        self.spent_per_stage[stage] += actual_cost_usd
        self.calls_per_stage[stage] += 1
        line = (f"[{stage}] +${actual_cost_usd:.5f}  total=${self.spent_usd:.5f} "
                f"(RMB{self.spent_usd * CNY_PER_USD:.4f})  {note}")
        log.info(line)
        self.log_lines.append(line)

    def report(self) -> str:
        lines = [
            f"=== 预算报告 ===",
            f"总花费: ${self.spent_usd:.5f}  (RMB{self.spent_usd * CNY_PER_USD:.4f})",
            f"总上限: ${self.total_usd:.5f}  (RMB{self.total_usd * CNY_PER_USD:.4f})",
            f"--- 分阶段 ---",
        ]
        for stage, spent in self.spent_per_stage.items():
            cap = self.stage_limits_usd.get(stage, 0)
            n = self.calls_per_stage[stage]
            lines.append(
                f"  {stage:12s} ${spent:.5f} / ${cap:.5f}  ({n} 次)"
            )
        return "\n".join(lines)
