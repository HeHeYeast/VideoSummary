"""CLI 入口.

用法:
  python -m src.cli <bilibili_url> [--mode test|prod] [--out OUT_DIR]
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from .budget import BudgetGuard, BudgetExceeded
from .pipeline import run


def main():
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--mode", choices=["test", "prod"], default="test")
    parser.add_argument("--out", default="output")
    parser.add_argument("--whisper", default="small",
                        help="tiny/base/small/medium/large-v3")
    parser.add_argument("--vision-model", default="qwen3-vl-plus")
    parser.add_argument("--outline-model", default="gpt-4o-mini")
    parser.add_argument("--writer-model", default="deepseek-v3.2")
    parser.add_argument("--polish-model", default="gpt-4o-mini")
    parser.add_argument("--skip-download", action="store_true",
                        help="跳过下载, 用缓存的 meta.json (调试用)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )

    cfg_path = Path(__file__).parent.parent / "config" / f"budget_{args.mode}.yaml"
    budget = BudgetGuard.from_yaml(cfg_path)

    work_dir = Path(args.out) / args.url.rstrip("/").split("/")[-1].split("?")[0]

    try:
        run(args.url, work_dir, budget,
            whisper_size=args.whisper,
            vision_model=args.vision_model,
            outline_model=args.outline_model,
            writer_model=args.writer_model,
            polish_model=args.polish_model,
            skip_download=args.skip_download)
    except BudgetExceeded as e:
        print(f"\n❌ 预算超限: {e}", file=sys.stderr)
        print(budget.report(), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
