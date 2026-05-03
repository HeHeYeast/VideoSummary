---
status: partial
phase: 12-archives-backfill-prompt-rule-search-cli
source: ["12-VERIFICATION.md"]
started: 2026-05-04T00:00:00Z
updated: 2026-05-04T00:00:00Z
---

## Current Test

[awaiting human testing — defer to next time user invokes natural-language recommendation in fresh Claude Code session]

## Tests

### 1. KB-14/KB-15 E2E natural-language recommendation behavior

expected: User opens fresh Claude Code session in this repo. User types a recommendation query containing one of the 7 byte-locked trigger phrases (e.g., "推荐学习 LLM Wiki 范式相关的视频" / "我之前看过哪些 ECS 相关的视频" / "找一下我学过 Godot 的"). Claude FIRST ACTION reads `output/.index.json`, then returns top-N推荐 in the locked 3-line format (slug+title+共享匹配信号 / blockquote tldr / 1-3 chapter 入口). Claude must NOT fabricate slugs not in `.index.json` (anti-hallucination FORBIDDEN list applied).

result: [pending — to be exercised on next real Claude Code session in this repo]

verification steps:
1. Open fresh Claude Code session in `D:\gxy_code\videoSummary` (or fresh /clear)
2. Type one of the 7 trigger phrases as a recommendation query
3. Observe FIRST ACTION = Claude reads `output/.index.json` (visible in tool calls)
4. Verify recommendation format: 3 lines per recommendation as specified in CLAUDE.md `## v1.2 知识库自然语言推荐入口` section
5. Verify all recommended slugs exist in `output/.index.json` (no fabricated slugs)
6. Verify Claude does NOT modify any of: summary.md / paragraphs.json / segs.json / meta.json (D-29 invariant)
7. Optional: verify Claude returns no more than 5 recommendations (FORBIDDEN: 推荐多于 N=5)

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
