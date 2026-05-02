# Milestones

## v1.0 — videoSummary v1.0 (Shipped: 2026-05-02)

**Phases:** 6 · **Plans:** 16 · **Tasks:** 31

**Definition of Done:** B站 / 抖音 / YouTube 视频 → 结构化 Markdown 教程，全流程 ¥0 成本，Claude Code 是唯一决策者。

**Key accomplishments:**

1. **5-source ingest pipeline** — Pluggable `agent/sources/` registry (Douyin → YouTube → Bilibili → Local → Generic) with most-specific-first matching. YouTube ships with 2-second `yt-dlp --simulate` preflight + 5-class stderr classifier (`gfw_blocked / cookies_stale / po_token_required / yt_dlp_outdated / other`) turning "莫名其妙连不上" into actionable Chinese hints. Local mp4 fallback closes the GFW/SABR/PO-token gap.

2. **Adaptive 4-mode teaching output** — CLAUDE.md becomes the prompt-engineering decision center. Phase 2 末尾 mode classification (`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`) + 8 hand-authored exemplar skeletons (4 modes × 2 rhythms) + format-spec lock (4 invariants) + `plan.md` / `depth_plan.md` schema. Zero LOC Python — all prompt engineering.

3. **Resume + parameter-aware caching** — Atomic JSON writes via tempfile+rename, `<artifact>.params.json` sidecars with cli/func/system 3-segment hash, loud regen logs (`regenerating segs.json because: cli.profile changed 'tutorial' -> 'podcast'`), `state.jsonl` event log + `state.json` derived view. `doctor` CLI for introspection. 17 archive re-runs remain byte-identical (D-29 invariant).

4. **Frame fps automation** — Claude writes `schedule.json` once, tool batch-executes ffmpeg per segment, resumes via `state.jsonl` segment events. FPS-04 silence-coverage gate ensures no >5s silence drops below baseline. PySceneDetect (default) + silero-vad (opt-in) provide ground truth without ever touching `schedule.json` (K5 "Claude is decider" boundary).

5. **Podcast / interview-distillation support** — `aggregate --profile podcast` (gap 2.5s / max_dur 90s / sentence_gap 1.5) + `transcribe --profile podcast` (VAD min_silence 800ms / threshold 0.6). Whisper 3-gram + density-based phrase repetition guard (warn-only, never auto-deletes per D-24 红线). Opt-in `pyannote.audio` diarization CLI ships ready (degrade fast-path documented for users without GPU + HF token).

6. **Two-terminal parallelism (NTH delivered)** — Cross-platform stdlib `agent/_lock.py` (msvcrt + fcntl), per-slug `output/<slug>/.resume.lock` with stale PID takeover, vendor `config.yaml` race closed, slug-prefixed log lines (`[BV132wiz] transcribe: ...`), cookies-in-memory cache + `--reload-cookies` flag. Skip-cleanly NTH per PROJECT.md K4 — shipped in spite of the option.

**Verification:** `.planning/milestones/v1.0-MILESTONE-AUDIT.md` — 52/52 requirements satisfied, 6/6 phases passed, 4/4 E2E flows verified, 5 tech debt items (all bounded, documented, non-blocking).

**Archives:**
- Roadmap: `.planning/milestones/v1.0-ROADMAP.md`
- Requirements: `.planning/milestones/v1.0-REQUIREMENTS.md`
- Audit: `.planning/milestones/v1.0-MILESTONE-AUDIT.md`

---
