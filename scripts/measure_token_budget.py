"""Per-archive token budget baseline writer (Phase 07 PRE-V11-03).

Writes `output/<slug>/.token_budget.json` recording the v1.0 baseline token cost
estimate per processing layer. Phase 09 asserts: end-to-end v1.1 token spend on
a marked slug <= 2x the baseline for the same mode.

Approximation: tokens ~ chars / 3.5 (Chinese-heavy text, matches faster-whisper
output character density). NOT exact -- we are proxying with file sizes because
Claude Code itself is not API-instrumented in this codebase. The 2x cap in
Phase 09 has enough headroom that ~10% approximation error doesn't matter.

Layers measured (all already-shipped v1.0 artifacts):
  transcribe: chars in segs.json (ASR output that Claude reads)
  aggregate:  chars in paragraphs.json (Claude reads when planning + writing)
  plan:       chars in plan.md if it exists, else 0 (some archives lack plan.md
              per CLAUDE.md "Missing 不强 fail" — pre-Phase-5 archives)
  write:      chars in summary.md (the output Claude generated)
  cleanup:    0 (cleanup_frames is mechanical; no Claude tokens)

Schema (locked):
    {
      "version": 1,
      "slug": "<slug>",
      "mode": "<replicate-guide|interview-distillation|extension-applications|unknown>",
      "measured_at": "<ISO-8601 UTC>",
      "approx_method": "chars/3.5 (Chinese-heavy proxy)",
      "layers": {
        "transcribe":  {"chars": N, "approx_tokens": N},
        "aggregate":   {"chars": N, "approx_tokens": N},
        "plan":        {"chars": N, "approx_tokens": N},
        "write":       {"chars": N, "approx_tokens": N},
        "cleanup":     {"chars": 0, "approx_tokens": 0}
      },
      "total_approx_tokens": N
    }

Usage:
    python -m scripts.measure_token_budget BV132wizyEEB
    python -m scripts.measure_token_budget BV132wizyEEB douyin_karpathy_llm_wiki douyin_claude_code_hooks
    python -m scripts.measure_token_budget --all
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent.io import write_json_atomic, now_iso

CHARS_PER_TOKEN = 3.5
LAYERS = ("transcribe", "aggregate", "plan", "write", "cleanup")
LAYER_FILES = {
    "transcribe": "segs.json",
    "aggregate": "paragraphs.json",
    "plan": "plan.md",
    "write": "summary.md",
    "cleanup": None,  # always 0
}

# Pre-classify the 3 representative slugs so the artifact records mode without
# Claude having to re-judge. These are LOCKED in CONTEXT (specifics section).
KNOWN_MODES = {
    "BV132wizyEEB": "replicate-guide",
    "douyin_karpathy_llm_wiki": "interview-distillation",
    "douyin_claude_code_hooks": "extension-applications",
}


def _measure_layer(slug_dir: Path, layer: str) -> dict:
    fname = LAYER_FILES[layer]
    if fname is None:
        return {"chars": 0, "approx_tokens": 0}
    p = slug_dir / fname
    if not p.exists():
        return {
            "chars": 0,
            "approx_tokens": 0,
            "note": f"{fname} missing (likely pre-Phase-5 archive)",
        }
    n_chars = len(p.read_text(encoding="utf-8"))
    return {"chars": n_chars, "approx_tokens": round(n_chars / CHARS_PER_TOKEN)}


def measure_one(slug_dir: Path) -> dict:
    slug = slug_dir.name
    layers = {layer: _measure_layer(slug_dir, layer) for layer in LAYERS}
    total = sum(d["approx_tokens"] for d in layers.values())
    return {
        "version": 1,
        "slug": slug,
        "mode": KNOWN_MODES.get(slug, "unknown"),
        "measured_at": now_iso(),
        "approx_method": f"chars/{CHARS_PER_TOKEN} (Chinese-heavy proxy)",
        "layers": layers,
        "total_approx_tokens": total,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.measure_token_budget",
        description=(
            "Write per-archive .token_budget.json recording v1.0 baseline token "
            "cost estimate per processing layer (transcribe/aggregate/plan/write/"
            "cleanup). Phase 09 asserts end-to-end v1.1 spend <= 2x this baseline."
        ),
    )
    parser.add_argument(
        "slugs",
        nargs="*",
        help="one or more slug names (default: 3 CONTEXT-locked representative archives)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="measure every dir under output/",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="root containing slug subdirs (default: output)",
    )
    args = parser.parse_args()

    output_root = Path(args.output_dir)
    if not output_root.is_dir():
        print(f"FATAL: output dir missing: {output_root}", file=sys.stderr)
        return 2

    if args.all:
        slugs = sorted(p.name for p in output_root.iterdir() if p.is_dir())
    elif args.slugs:
        slugs = args.slugs
    else:
        # Default: the 3 representative slugs from CONTEXT.md specifics
        slugs = list(KNOWN_MODES.keys())
        print(
            f"INFO: no slugs given -- measuring 3 representative archives: {slugs}",
            file=sys.stderr,
        )

    n_ok = 0
    for slug in slugs:
        slug_dir = output_root / slug
        if not slug_dir.is_dir():
            print(
                f"SKIP: {slug} (no such directory under {output_root})",
                file=sys.stderr,
            )
            continue
        if not (slug_dir / "segs.json").exists() and not (slug_dir / "summary.md").exists():
            print(
                f"SKIP: {slug} (no segs.json AND no summary.md -- not an archive)",
                file=sys.stderr,
            )
            continue
        obj = measure_one(slug_dir)
        target = slug_dir / ".token_budget.json"
        write_json_atomic(target, obj)
        print(
            f"WROTE: {target} (mode={obj['mode']}, "
            f"total_approx_tokens={obj['total_approx_tokens']})"
        )
        n_ok += 1
    return 0 if n_ok > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
