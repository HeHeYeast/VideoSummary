---
status: partial
phase: 11-per-slug-index-json-aggregator-phase76-hook
source: ["11-VERIFICATION.md"]
started: 2026-05-04T00:00:00Z
updated: 2026-05-04T00:00:00Z
---

## Current Test

[awaiting human testing — defer to next time `/summarize-video <url>` is run on a real new video]

## Tests

### 1. KB-02 E2E Phase 7.6 hook on real video

expected: User runs `/summarize-video <url>` on a fresh new video. After Phase 7.5 verifier passes and before Phase 8 cleanup, Claude reads 5 files (`output/<slug>/summary.md`, `meta.json`, `plan.md`, `output/_glossary.md`, `output/_topics.md`), composes 8-field JSON (slug/title/duration_s/mode/topics/keywords/tldr_oneliner/chapters), and pipes via stdin to `python -m agent.tools index write --slug <slug> --from-stdin`. CLI auto-rebuilds top-level `output/.index.json`. Subsequent re-trigger of Phase 7.6 on the same slug should be idempotent (CLI returns `action: skipped` if byte-equal).

result: [pending — to be exercised when next processing a real new video]

verification steps:
1. Pick a test video (~5 min length recommended) and run `/summarize-video <url>` end-to-end
2. After workflow completes, check `output/<slug>/index.json` exists with valid 8-field schema
3. Check `output/.index.json` aggregator includes the new slug
4. Re-run `/summarize-video <url>` on same URL; confirm `index.json` byte-equal (action: skipped)
5. If Claude proposes new topic via `pending: <name>` form, verify `output/_topics.md` `## Pending` segment got the entry
6. Optional: verify `_glossary.md` H2 anchor reuse — if summary mentions e.g. "LoRA", check `keywords[]` byte-equal canonical form (`LoRA (Low-Rank Adaptation)`)

## Summary

total: 1
passed: 0
issues: 0
pending: 1
skipped: 0
blocked: 0

## Gaps
