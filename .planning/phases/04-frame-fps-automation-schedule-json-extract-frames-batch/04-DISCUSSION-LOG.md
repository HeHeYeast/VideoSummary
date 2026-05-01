# Phase 4: Frame fps Automation - Discussion Log

> **Audit trail only.** Decisions in CONTEXT.md.

**Date:** 2026-05-01
**Phase:** 04-frame-fps-automation-schedule-json-extract-frames-batch
**Mode:** `gsd-discuss-phase --auto` (user requested 尽可能不干预)

## Auto-resolved grey areas (Claude self-decided per session-level user delegation)

| Grey area | Recommended (CONTEXT D-XX) | Rationale |
|---|---|---|
| schedule.json shape | dict with version/video/defaults/segments per .planning/research/SUMMARY.md | Schema already locked at research time; consistency across phases |
| validation strictness on coverage | full-duration ±2s tolerance; no overlap; fps XOR skip; no unknown keys | Loose tolerance avoids edge-case rejection (last segment ending at duration-1.8s should pass); strict on overlap/keys to catch typos |
| silence-coverage enforcement | required if silence_map.json exists; baseline-only fallback if absent | PITFALLS P2.1 showstopper — but FPS-04 requires "either-or", and 04-02 is wave 2; hard requirement on 04-01 alone needs fallback |
| segment-level override of default_scale/default_quality | NOT in v1 | YAGNI — schema bump if needed |
| extract_frames_batch resume granularity | segment-level events emit started/completed/failed per non-skip segment | This is Phase 2 D-14 deferred-to-Phase-4 落地点 |
| failure handling | fail-loud (raise + emit failed event), no auto-skip subsequent segments | Consistent with project's fail-loud idiom |
| --force flag | yes, skips resume | Mirror cmd_transcribe --force idiom |
| detect_scenes threshold | PySceneDetect default 27.0; expose --threshold | YAGNI to start; flag for future tuning |
| detect_silence output schema | silence_intervals + flagged_for_review:true on >5s | Self-documenting for Claude reading silence_map.json |
| auto-promote scenes/silence to schedule | NEVER (anti-feature per K5) | Hardcoded in plan acceptance: cmd_extract_frames_batch must not import scenes.py |
| schedule.json writer | Claude (Write tool) directly | No CLI subcommand for "generate schedule" — that would erode K5 |
| plan.md vs schedule.json relationship | independent; Phase 5 writes plan.md, Phase 4 writes schedule.json | Loose coupling; Phase 5 plan.md is natural language reasoning, Phase 4 schedule.json is machine spec |
| existing cmd_extract_frames | UNCHANGED (FPS-07) | Co-exists as 补抽 tool; batch is first-pass, single-segment is finishing-pass |
| 2-plan split | 04-01 batch + scheduler core; 04-02 detect_scenes + detect_silence | Per ROADMAP; 04-01 has fallback for silence_map.json absence so 04-02 can land second |

## Pause-points reserved

None for this phase. Phase 4 is pure tooling — no user environment dependency. Both 04-01 + 04-02 are fully autonomous.

## Deferred ideas

详见 `04-CONTEXT.md` `<deferred>` 节。重点：segment-级 default override / multi-pass schedule / auto-promote tools / threshold auto-tuning。
