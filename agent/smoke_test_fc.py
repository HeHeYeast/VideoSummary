"""冒烟测试: VectorEngine 中转站的 function calling 是否正常.

测试方法: 给模型一个简单的 get_weather 工具, 看它能否正确返回 tool_calls.
对每个候选主 agent 模型都跑一次, 筛掉不稳的.

用法: python -m agent.smoke_test_fc
"""
import json
import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("VE_BASE_URL", "https://api.vectorengine.ai/v1")
# 用 quality key 测, 因为 agent 主模型会走 quality 组
API_KEY = os.getenv("VE_KEY_QUALITY") or os.getenv("VE_KEY_CHEAP")
if not API_KEY:
    print("❌ 需要设置 VE_KEY_QUALITY 或 VE_KEY_CHEAP")
    sys.exit(1)

client = OpenAI(base_url=BASE_URL, api_key=API_KEY, max_retries=1)

# 测试用工具定义
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "获取指定城市的天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                },
                "required": ["city"],
            },
        },
    }
]

MESSAGES = [
    {"role": "user", "content": "北京今天天气怎么样？"},
]

# 候选模型列表 — 按优先级排列
CANDIDATES = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "deepseek-v3.2",
    "gpt-4o-mini",
    "glm-4.5-air",
    "glm-4.6",
    "kimi-k2",
]


def test_model(model: str) -> dict:
    """测试一个模型的 function calling 能力. 返回结果 dict."""
    result = {"model": model, "ok": False, "error": None, "tool_calls": None}
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=MESSAGES,
            tools=TOOLS,
            tool_choice="auto",
            max_tokens=200,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            result["ok"] = True
            result["tool_calls"] = {
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
        else:
            result["error"] = f"未返回 tool_calls, content={msg.content[:100] if msg.content else '(空)'}"
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return result


def main():
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    print(f"VE base: {BASE_URL}")
    print(f"Key:     {API_KEY[:8]}...")
    print(f"testing {len(CANDIDATES)} models for function calling\n")
    print(f"{'model':<35} {'result':<8} {'detail'}")
    print("-" * 80)

    results = []
    for m in CANDIDATES:
        r = test_model(m)
        results.append(r)
        status = "OK" if r["ok"] else "FAIL"
        detail = json.dumps(r["tool_calls"], ensure_ascii=False) if r["ok"] else r["error"]
        print(f"{m:<35} {status:<8} {detail}")

    ok_models = [r["model"] for r in results if r["ok"]]
    print(f"\nusable: {ok_models}")
    if ok_models:
        print(f"recommended: {ok_models[0]}")


if __name__ == "__main__":
    main()
