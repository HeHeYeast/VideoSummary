# Requirements: videoSummary

**Defined:** 2026-04-30
**Core Value:** 把视频提炼成对学习者真有教学价值的 Markdown 文档（不是字幕翻译），并保持全流程 ¥0。

> **Brownfield note:** This document scopes the **expansion milestone** only. Validated capabilities (B站/抖音 下载 / faster-whisper ASR / 段落聚合 / 手工抽帧 / Claude 多模态读帧 / /summarize-video 8 阶段流程) are documented in `PROJECT.md` and not re-listed here. Every v1 requirement below is **additive opt-in** — it must not break the existing 5-command CLI, the `output/<slug>/` directory layout, or the 17 archived tutorials' re-run path.

## v1 Requirements

Six categories matching the recommended phase structure from `.planning/research/SUMMARY.md`. Each requirement is testable and atomic.

### PRE — Preflight & Regression Baseline

- [ ] **PRE-01**: Project commits a `tests/regression/` directory with frozen `summary.md` baselines from 3 archived videos (`BV132wizyEEB` for code, `godot_brave` for game/Godot, `douyin_trae_ai` for AI/UI).
- [ ] **PRE-02**: Project includes a `regression-check.md` runbook describing how to re-run the new flow on the 3 baselines and manual-diff against committed `summary.md`.
- [ ] **PRE-03**: `meta.json` / `segs.json` / `paragraphs.json` schemas are documented as `schema_version: 1` retroactively; loaders default to `1` when the field is absent (forward-compat foundation).
- [ ] **PRE-04**: Every `open()` call in `agent/` and `src/` uses explicit `encoding="utf-8"` (audited and fixed where missing).
- [ ] **PRE-05**: `CLAUDE.md` documents `chcp 65001` and `PYTHONUTF8=1` as recommended Windows zh-CN setup steps.

### RES — Resume Infrastructure & Cache Correctness

- [ ] **RES-01**: Every artifact-writing function in `agent/tools.py` writes a sidecar `<artifact>.params.json` capturing the parameters used (e.g., `whisper_model`, `vad_settings`, `ffmpeg_version`, `profile`).
- [ ] **RES-02**: Loaders compare current params against `<artifact>.params.json`; mismatch triggers regeneration with a loud log line `"regenerating <artifact> because: <field> changed <old> -> <new>"`.
- [ ] **RES-03**: All artifact JSON writes use atomic-write pattern (`tempfile.NamedTemporaryFile(dir=target.parent)` + `os.replace`); same-volume constraint enforced.
- [ ] **RES-04**: All artifact writes retry up to 3 times with 0.5s backoff on `PermissionError` (Windows file-lock contention from Defender/OneDrive/Search).
- [ ] **RES-05**: `agent/state.py` provides an append-only `output/<slug>/state.json` event log with a pure `derived_state(events)` reducer; per-stage and per-segment-frame granularity.
- [ ] **RES-06**: When `state.json` is missing or corrupt, behavior degrades gracefully to current file-existence cache (no regressions on archived videos).
- [ ] **RES-07**: A `doctor` CLI subcommand prints a read-only scan of `output/<slug>/` showing each artifact's existence, mtime, and sidecar params.
- [ ] **RES-08**: A one-page schema-migration runbook (`docs/schema-migration.md` or similar) documents the version-bump pattern even though no migration is invoked yet.

### SRC — Source Refactor + New Sources

- [ ] **SRC-01**: `agent/sources/` package contains one file per platform (`bilibili.py`, `douyin.py`, `youtube.py`, `generic.py`, `local.py`), each implementing a `Source` Protocol with `match(url|path)` and `fetch(target_dir)` methods.
- [ ] **SRC-02**: `agent/url_router.py` is a pure-function router that dispatches to the right source based on URL pattern or local path; `agent/tools.py:cmd_download` calls it instead of the existing 抖音 substring branch.
- [ ] **SRC-03**: An `ingest` CLI subcommand exposes the new router; the existing `download` subcommand becomes a thin shim that calls `ingest` with identical observable behavior on B站/抖音 URLs (verified via PRE-01 baseline).
- [ ] **SRC-04**: `meta.json` is extended with a `source` field (`bilibili|douyin|youtube|generic|local`) and platform-specific IDs (`youtube_id`, `aweme_id`, etc.) — additive, optional fields, default to `null` for archived videos.
- [ ] **SRC-05**: YouTube ingestion runs a 2-second `yt-dlp --simulate` preflight; failures classified as `gfw_blocked | cookies_stale | po_token_required | yt_dlp_outdated | other` with a clean error message naming the recovery action.
- [ ] **SRC-06**: `HTTPS_PROXY` / `HTTP_PROXY` (uppercase, Windows convention) are read from env and forwarded to yt-dlp via `--proxy`.
- [ ] **SRC-07**: At startup of any ingest involving yt-dlp, `yt-dlp.__version__` is logged; if older than 90 days, a one-line warning suggests `pip install -U yt-dlp` (no auto-update).
- [ ] **SRC-08**: `meta.json` records `subtitle_origin: auto | creator | asr | none` so downstream knows whether to trust embedded subs vs run faster-whisper.
- [ ] **SRC-09**: Local mp4 input accepts an absolute path; the file is copied (or symlinked) into `output/<slug>/video.mp4` where `<slug>` is normalized to ASCII-safe (e.g., hash-prefix + first 8 ASCII chars of stem).
- [ ] **SRC-10**: Local mp4 input rejects `--out` paths containing CJK characters with a clean error message (avoids ffmpeg subprocess GBK/UTF-8 corruption per PITFALLS P4.1).
- [ ] **SRC-11**: All sources run an `ffprobe` preflight that validates codec, presence of audio stream, container, and reports VFR; missing audio errors out cleanly; HEVC/AV1 logs a remux suggestion.
- [ ] **SRC-12**: `extract_frames` ffmpeg invocation includes `-vsync vfr` so VFR sources (OBS, iPhone) don't drop or duplicate frames silently. Applies uniformly to all sources.
- [ ] **SRC-13**: `requirements.txt` pins `yt-dlp >=2026.03.17`; Deno + `yt-dlp-get-pot` documented as opt-in YouTube extras (not in baseline `requirements.txt`).

### FPS — Frame fps Automation

- [ ] **FPS-01**: `agent/scheduler.py` defines a `Schedule` dataclass with JSON I/O matching the locked schema:
  ```json
  {"version": 1, "video": "...", "default_scale": "...", "default_quality": int,
   "segments": [{"start": float, "end": float, "fps": float, "label": "..."}, ...]}
  ```
- [ ] **FPS-02**: Schedule validation enforces (fail loud, never silent): full-duration coverage `[0, duration) ± 2s`, no segment overlap, each segment has either `fps` OR `skip:true` (mutually exclusive), no unknown keys at top level or per segment.
- [ ] **FPS-03**: An `extract_frames_batch` CLI consumes a `schedule.json` and emits frames preserving the existing `seg_<start>_<index>.jpg` filename grammar; resume-aware (skips segments already in `state.json`).
- [ ] **FPS-04**: Schedule validation requires either a low-rate baseline pass (e.g., `fps ≤ 0.1` whole-video segment) OR explicit per-segment coverage of all silence regions > 5s detected by silero-vad — protects against silent-visual-content blind spots (PITFALLS P2.1).
- [ ] **FPS-05**: A `detect_scenes` CLI subcommand emits `output/<slug>/scenes.json` via PySceneDetect; Claude reads it as decision support for `schedule.json` but the tool **never** auto-promotes scenes into a schedule.
- [ ] **FPS-06**: A `detect_silence` CLI subcommand emits `output/<slug>/silence_map.json` via silero-vad; gaps > 5s flagged so Claude can address each in the schedule.
- [ ] **FPS-07**: The existing single-segment `extract_frames` CLI remains unchanged — for补抽 corrections after first frame review.

### TEACH — Adaptive Output + UI Demo + Podcast

- [ ] **TEACH-01**: `CLAUDE.md` includes a Phase 2 video-classification step that emits a `mode` tag in `plan.md`: `replicate-guide | concept-explanation | extension-applications | interview-distillation` (or hybrid).
- [ ] **TEACH-02**: `CLAUDE.md` includes a format-spec lock — regardless of selected mode, conventions hold: timestamp `[HH:MM:SS]`, code fence with explicit language, image embed `![](frames/seg_xxxx_xxxxxx.jpg)`, second-person imperative voice. Content adaptive; form not.
- [ ] **TEACH-03**: `CLAUDE.md` includes 2-3 hand-authored minimal exemplar `summary.md` skeletons per teaching dimension (PITFALLS P1.3 — without these, T1 collapses to single-mode output).
- [ ] **TEACH-04**: `output/<slug>/plan.md` is written by Claude in Phase 2 of `/summarize-video`; free-form, captures classification + chosen mode + segment-level fps strategy reasoning.
- [ ] **TEACH-05**: `output/<slug>/depth_plan.md` (optional checkpoint) records depth-decision before any prose is written, so user can intervene before token-expensive writing.
- [ ] **TEACH-06**: `agent/asr_v2.py` exposes `aggregate_paragraphs(profile=...)` with a `PROFILES` constant; `tutorial` (default: `gap=1.5, max_dur=30, sentence_gap=0.8`) and `podcast` (`gap=2.5, max_dur=90, sentence_gap=1.5`).
- [ ] **TEACH-07**: `aggregate` CLI accepts `--profile {tutorial|podcast}`, defaulting to `tutorial` (backward-compat).
- [ ] **TEACH-08**: A `diarize` CLI subcommand (opt-in via `requirements-optional.txt` with `pyannote.audio`) emits `output/<slug>/diarization.json` keyed by speaker turn `[{start, end, speaker_id}]`.
- [ ] **TEACH-09**: `CLAUDE.md` includes a UI-demo writing skeleton with: (a) "quote with uncertainty" rule for pixel-text, (b) tooltip-blocking detection guideline, (c) cursor-invisibility fallback (infer click target from before/after diff), (d) `--width 1280/1920` override for 4K recordings.
- [ ] **TEACH-10**: `CLAUDE.md` includes a podcast/interview skeleton: skips `extract_frames` entirely (or 1-2 frames per chapter); structures output around speaker turns + key claims + timestamp-navigable quotes; replaces image embeds with blockquotes for quotes.
- [ ] **TEACH-11**: A whisper-repetition post-pass detector flags any 3-gram repeated >3× consecutively in `segs.json` for human review (does NOT auto-delete — `不注水不编造` redline).
- [ ] **TEACH-12**: VAD settings adjustable per profile — `min_silence_duration_ms=500` and tighter threshold for podcast profile to reduce hallucinations on long silences.
- [ ] **TEACH-13**: For podcast mode, Claude writes `output/<slug>/chapters.json` with `[{start, end, topic_title, summary_line}]` (replaces silence-gap aggregation as the structural unit).

### PARA — Multi-Agent Parallelism (Nice-to-Have, ship-or-skip)

> Per PROJECT.md Key Decision row 4: 用户表态"做不到也没关系". Roadmapper may scope this entire category as a single optional phase that ships cleanly or skips cleanly.

- [ ] **PARA-01**: `agent/_lock.py` provides a cross-platform advisory file-lock helper wrapping `filelock>=3.16`.
- [ ] **PARA-02**: Vendor `vendor/douyin_api/.../config.yaml` rewriting is wrapped in a process-level lock (resolves PITFALLS P8.1 race when two agents download 抖音 videos concurrently).
- [ ] **PARA-03**: Long-running stages (`transcribe`, `extract_frames_batch`) acquire `output/<slug>/resume.lock` for the duration; second invocation on same slug fails fast with a clean message.
- [ ] **PARA-04**: All log lines from `agent.tools` are prefixed with the slug (e.g., `[BV132wiz]`, `[godot_brave]`) so multi-terminal output is debuggable.
- [ ] **PARA-05**: Cookies files (douyin / youtube) are read into memory once at download start; not re-read mid-run.
- [ ] **PARA-06**: `CLAUDE.md` documents the parallelism contract: per-slug isolation works; running two `transcribe` concurrently is at user's risk (Whisper concurrent-load OOM hazard) unless an explicit serialization mechanism is added.

## v2 Requirements

Acknowledged but deferred to a future milestone. Tracked here so they're not re-debated at every replan.

### Future TEACH

- **TEACH-V2-01**: Multi-output documents per video (e.g., `quick-ref.md` + `deep-dive.md`) — explicitly NOT v1 per PROJECT.md K Decision row 2; revisit if single-doc adaptive mode proves too constrained after 5+ real videos.
- **TEACH-V2-02**: Quote-card extraction (shareable image cards from key moments) — only if user's queue trends toward shareable content.
- **TEACH-V2-03**: Cross-video knowledge index (e.g., search "ECS pattern across all summaries").

### Future SRC

- **SRC-V2-01**: Auto-fps-plan from `scenes.json` + `silence_map.json` without Claude intermediation — would cross the "Claude is decider" line, defer until evidence shows Claude's manual planning is the bottleneck.
- **SRC-V2-02**: Niconico / Twitter (X) / Vimeo extractor-specific quirks (only if user encounters them; current generic yt-dlp routing covers them functionally).

### Future RES

- **RES-V2-01**: Whisper-server pattern (persistent in-memory model across invocations) — defer until parallelism becomes a real workflow, not a curiosity.
- **RES-V2-02**: `step_log.json` per-run provenance with parameter hashes (PITFALLS U4) — useful but not blocking; current `state.json` + `params.json` covers most cases.

## Out of Scope

Explicit exclusions with reasoning. Anti-features cross-checked against `PROJECT.md` Out of Scope and `FEATURES.md` anti-features list — strict superset, no conflicts.

| Feature | Reason |
|---------|--------|
| Any paid LLM / ASR / Vision / Translation API | ¥0 hard constraint (PROJECT.md Core Value); breaking it defeats project purpose |
| Decision-making by tool (auto-outline, auto-fps-without-Claude) | Violates "Claude Code is唯一决策者" Constraint; relives the abandoned `agent/frames_v2.py` mistake |
| Multi-output documents per video | PROJECT.md K Decision row 2: user explicitly chose "Claude 自适应单文档"; multi-output is a different product |
| Queue auto-runner / fully unattended batch | PROJECT.md OOS row 4: user said "手动一条条触发当前可接受" |
| Web UI / dashboard / cloud sync | PROJECT.md OOS: single-user local tool, no SaaS direction |
| Multi-user / authentication / accounts | PROJECT.md OOS: single-user; out of product scope |
| Cursor-highlight overlay on UI demo frames (post-hoc) | FEATURES anti-feature: cursor effects are a recording-time feature (DemoCreator/FocuSee); post-hoc detection requires vision-model frame tracking → ¥0-incompatible |
| Translation / multi-language output | FEATURES anti-feature: not the actual user need; user produces zh-CN content for zh-CN learners |
| Real-time streaming summarization | FEATURES anti-feature: requires entirely different pipeline; out of scope for the file-based stage handoff design |
| Mobile app | PROJECT.md OOS: Windows-first, no mobile direction |
| In-tool MD editor / `summary.md` editing UI | FEATURES anti-feature: user edits in their own editor; tool just writes |
| Rewrite or delete existing `agent/` or `src/` modules | PROJECT.md OOS: backward-compat hard requirement; legacy 17-video queue depends on stable old paths |
| Change `output/<slug>/` directory layout convention | PROJECT.md OOS + PITFALLS U2: archived dirs depend on it |

## Traceability

Populated by `/gsd-roadmapper` 2026-04-30. Phases derived 1:1 from requirement categories per `.planning/research/SUMMARY.md`.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PRE-01 | Phase 1 | Pending |
| PRE-02 | Phase 1 | Pending |
| PRE-03 | Phase 1 | Pending |
| PRE-04 | Phase 1 | Pending |
| PRE-05 | Phase 1 | Pending |
| RES-01 | Phase 2 | Pending |
| RES-02 | Phase 2 | Pending |
| RES-03 | Phase 2 | Pending |
| RES-04 | Phase 2 | Pending |
| RES-05 | Phase 2 | Pending |
| RES-06 | Phase 2 | Pending |
| RES-07 | Phase 2 | Pending |
| RES-08 | Phase 2 | Pending |
| SRC-01 | Phase 3 | Pending |
| SRC-02 | Phase 3 | Pending |
| SRC-03 | Phase 3 | Pending |
| SRC-04 | Phase 3 | Pending |
| SRC-05 | Phase 3 | Pending |
| SRC-06 | Phase 3 | Pending |
| SRC-07 | Phase 3 | Pending |
| SRC-08 | Phase 3 | Pending |
| SRC-09 | Phase 3 | Pending |
| SRC-10 | Phase 3 | Pending |
| SRC-11 | Phase 3 | Pending |
| SRC-12 | Phase 3 | Pending |
| SRC-13 | Phase 3 | Pending |
| FPS-01 | Phase 4 | Pending |
| FPS-02 | Phase 4 | Pending |
| FPS-03 | Phase 4 | Pending |
| FPS-04 | Phase 4 | Pending |
| FPS-05 | Phase 4 | Pending |
| FPS-06 | Phase 4 | Pending |
| FPS-07 | Phase 4 | Pending |
| TEACH-01 | Phase 5 | Pending |
| TEACH-02 | Phase 5 | Pending |
| TEACH-03 | Phase 5 | Pending |
| TEACH-04 | Phase 5 | Pending |
| TEACH-05 | Phase 5 | Pending |
| TEACH-06 | Phase 5 | Pending |
| TEACH-07 | Phase 5 | Pending |
| TEACH-08 | Phase 5 | Pending |
| TEACH-09 | Phase 5 | Pending |
| TEACH-10 | Phase 5 | Pending |
| TEACH-11 | Phase 5 | Pending |
| TEACH-12 | Phase 5 | Pending |
| TEACH-13 | Phase 5 | Pending |
| PARA-01 | Phase 6 | Pending |
| PARA-02 | Phase 6 | Pending |
| PARA-03 | Phase 6 | Pending |
| PARA-04 | Phase 6 | Pending |
| PARA-05 | Phase 6 | Pending |
| PARA-06 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 52 total (5 PRE + 8 RES + 13 SRC + 7 FPS + 13 TEACH + 6 PARA)
- Mapped to phases: 52 (100%) ✓
- Unmapped: 0 ✓

> Note: The earlier "51 total" stat was an arithmetic miscount (sum of category subtotals = 52). Corrected here on roadmap creation.

---
*Requirements defined: 2026-04-30*
*Last updated: 2026-04-30 — traceability populated by gsd-roadmapper (52 reqs → 6 phases, 100% coverage)*
