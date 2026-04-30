# Roadmap: videoSummary (Brownfield Expansion Milestone)

## Overview

This milestone expands the existing ¥0 video-to-tutorial pipeline along six dimensions (regression baseline, resume infrastructure, new sources, fps automation, adaptive teaching output, optional parallelism) without breaking the legacy 5-command CLI, the `output/<slug>/` directory layout, or the 17 archived tutorials' re-run path. Phases derive 1:1 from the six requirement categories (PRE / RES / SRC / FPS / TEACH / PARA) — research synthesis (`.planning/research/SUMMARY.md`) recommends this structure with explicit ordering rationale, and goal-backward analysis confirms it. Phase 1 (PRE) gates the rest by locking a golden-output regression baseline; Phase 2 (RES) carries cross-cutting infrastructure (atomic writes, params.json sidecars, schema_version, state.json, doctor) that benefits every later phase; Phases 3-5 deliver user-visible features in dependency order; Phase 6 (PARA) is genuinely Nice-to-Have and ships-or-skips cleanly per PROJECT.md Key Decision row 4.

## Phases

**Phase Numbering:**
- Integer phases (1-6): Planned milestone work
- Decimal phases (e.g., 2.1): Reserved for urgent insertions if discovered during execution

- [ ] **Phase 1: Preflight & Regression Baseline** - Lock the 17-archive re-run path before any feature changes the schema surface
- [ ] **Phase 2: Resume Infrastructure & Cache Correctness** - Make every artifact parameter-aware, atomic, and resumable so later phases can vary parameters safely
- [ ] **Phase 3: Source Refactor + New Sources (YouTube + Local mp4 + Generic)** - Replace the 抖音 substring dispatch with a pluggable `sources/` registry and add three new ingest paths
- [ ] **Phase 4: Frame fps Automation (`schedule.json` + `extract_frames_batch`)** - Let Claude write a per-segment fps schedule once, tool executes ffmpeg N times resume-aware
- [ ] **Phase 5: Adaptive Output + UI Demos + Podcasts** - Adaptive teaching output, UI-demo + podcast skeletons, opt-in diarization — same prompt-engineering workstream
- [ ] **Phase 6: Multi-Agent Parallelism (Nice-to-Have, ship-or-skip)** - File-locks + log prefixes so two terminals don't stomp each other

## Phase Details

### Phase 1: Preflight & Regression Baseline
**Goal**: Freeze the legacy 17-archive re-run path and the `meta.json` / `segs.json` / `paragraphs.json` schemas as the regression target before any feature work touches them.
**Depends on**: Nothing (gating preflight)
**Requirements**: PRE-01, PRE-02, PRE-03, PRE-04, PRE-05
**Success Criteria** (what must be TRUE):
  1. `tests/regression/` contains committed `summary.md` baselines for `BV132wizyEEB`, `BV1C9QCBdE1U`, and `douyin_trae_ai` plus a `regression-check.md` runbook describing how to re-run and manual-diff
  2. Loaders for `meta.json` / `segs.json` / `paragraphs.json` accept files lacking `schema_version` and treat them as v1 (archived videos remain re-runnable unchanged)
  3. Every `open()` call in `agent/` and `src/` uses explicit `encoding="utf-8"` (verified by audit)
  4. `CLAUDE.md` documents `chcp 65001` + `PYTHONUTF8=1` as the recommended Windows zh-CN setup so subsequent phases inherit a clean encoding baseline
**Plans**: 3 plans

Plans:
- [ ] 01-01: Commit golden-output regression baselines (PRE-01) + runbook (PRE-02)
- [ ] 01-02: Retroactive `schema_version: 1` documentation + loader-tolerance change (PRE-03)
- [ ] 01-03: Encoding audit (PRE-04) + Windows zh-CN setup docs in CLAUDE.md (PRE-05)
**UI hint**: no

### Phase 2: Resume Infrastructure & Cache Correctness
**Goal**: Make artifact reuse parameter-aware and crash-safe so any subsequent phase can vary parameters (whisper model, VAD threshold, fps schedule, profile) without silently reusing stale upstream results.
**Depends on**: Phase 1 (schemas frozen, encoding clean)
**Requirements**: RES-01, RES-02, RES-03, RES-04, RES-05, RES-06, RES-07, RES-08
**Success Criteria** (what must be TRUE):
  1. Re-running any stage with a changed parameter (e.g., `--whisper small` → `medium`) regenerates the artifact and prints `regenerating <artifact> because: <field> changed <old> -> <new>`
  2. Killing a write mid-flight leaves either the previous valid file on disk or no file (never a half-written JSON), and a retry succeeds even when Defender/OneDrive briefly holds the lock
  3. `output/<slug>/state.json` records each completed stage and per-segment frame extraction; deleting the file falls back gracefully to the existing file-existence cache (archived videos don't break)
  4. `python -m agent.tools doctor output/<slug>` prints a read-only table of every artifact's existence, mtime, and sidecar params for any slug
  5. A schema-migration runbook (`docs/schema-migration.md`) documents the version-bump pattern, ready for the first real migration
**Plans**: 3 plans

Plans:
- [ ] 02-01: Atomic writes + PermissionError retry + `<artifact>.params.json` sidecar pattern (RES-01, RES-02, RES-03, RES-04)
- [ ] 02-02: `agent/state.py` append-only event log + `derived_state(events)` reducer + file-existence fallback (RES-05, RES-06)
- [ ] 02-03: `doctor` subcommand + schema-migration runbook (RES-07, RES-08)
**UI hint**: no

### Phase 3: Source Refactor + New Sources (YouTube + Local mp4 + Generic)
**Goal**: Replace the 抖音 substring dispatch with a pluggable `agent/sources/` registry and ship three new ingest paths (YouTube + generic yt-dlp + local mp4) where local mp4 is YouTube's graceful fallback when the GFW/SABR/PO-token chain fails.
**Depends on**: Phase 2 (params.json sidecars + atomic writes apply to new ingest paths from day one)
**Requirements**: SRC-01, SRC-02, SRC-03, SRC-04, SRC-05, SRC-06, SRC-07, SRC-08, SRC-09, SRC-10, SRC-11, SRC-12, SRC-13
**Success Criteria** (what must be TRUE):
  1. `python -m agent.tools download <bilibili-url>` and `<douyin-url>` produce byte-identical artifacts to the Phase 1 regression baselines (the `download` shim preserves observable behavior)
  2. `python -m agent.tools ingest <youtube-url> --out output/<slug>` succeeds via proxy or fails with a classified, actionable error (one of: `gfw_blocked`, `cookies_stale`, `po_token_required`, `yt_dlp_outdated`, `other`)
  3. `python -m agent.tools ingest "D:\videos\local.mp4" --out output/local_xxx` copies the file in, runs ffprobe preflight, rejects CJK `--out` paths cleanly, and produces a `meta.json` with `source: "local"`
  4. ffprobe preflight for any source surfaces missing audio as a clean error and logs a remux suggestion for HEVC/AV1; `-vsync vfr` is applied uniformly so OBS/iPhone VFR sources don't drop frames silently
  5. `meta.json` is extended with `source` and platform-specific IDs (`youtube_id`, `aweme_id`) as additive optional fields; old archived videos still load
**Plans**: 3 plans

Plans:
- [ ] 03-01: `agent/sources/` package + `url_router.py` + `ingest` subcommand + `download` shim + `meta.json` source field (SRC-01, SRC-02, SRC-03, SRC-04)
- [ ] 03-02: YouTube layer — preflight classifier, proxy forwarding, version warning, subtitle_origin, yt-dlp pin, Deno docs (SRC-05, SRC-06, SRC-07, SRC-08, SRC-13)
- [ ] 03-03: Local mp4 + ffprobe preflight + uniform `-vsync vfr` (SRC-09, SRC-10, SRC-11, SRC-12)
**UI hint**: no

### Phase 4: Frame fps Automation (`schedule.json` + `extract_frames_batch`)
**Goal**: Let Claude write one `schedule.json` per video and have the tool batch-execute ffmpeg per segment, resume-aware via `state.json`, with mandatory silence-coverage protection — without ever crossing the "Claude is decider" line.
**Depends on**: Phase 2 (state.json for resume) + Phase 3 (unified `meta.json` source field)
**Requirements**: FPS-01, FPS-02, FPS-03, FPS-04, FPS-05, FPS-06, FPS-07
**Success Criteria** (what must be TRUE):
  1. `python -m agent.tools extract_frames_batch --schedule output/<slug>/schedule.json --out output/<slug>/frames` validates the schema (full-duration coverage, no overlap, fps XOR skip, no unknown keys) and emits frames preserving the existing `seg_<start>_<index>.jpg` filename grammar
  2. Re-running the same command after a partial failure skips already-completed segments via `state.json` and only re-extracts the missing ones
  3. A schedule that lacks both a low-rate baseline pass AND explicit coverage of all silence regions > 5s is rejected with a clear validation error (silence-blind-spot protection)
  4. `python -m agent.tools detect_scenes <video>` and `detect_silence <video>` produce `scenes.json` / `silence_map.json` artifacts that Claude reads as decision support; the tool never auto-promotes them into a schedule
  5. The single-segment `extract_frames` CLI continues to work unchanged for 补抽 corrections after first frame review
**Plans**: 2 plans

Plans:
- [ ] 04-01: `agent/scheduler.py` + `extract_frames_batch` CLI + strict validation + resume integration (FPS-01, FPS-02, FPS-03, FPS-04, FPS-07)
- [ ] 04-02: `detect_scenes` + `detect_silence` decision-support subcommands (FPS-05, FPS-06)
**UI hint**: no

### Phase 5: Adaptive Output + UI Demos + Podcasts
**Goal**: Ship adaptive teaching output (Claude classifies video type and picks one of replicate-guide / concept-explanation / extension-applications / interview-distillation), UI-demo and podcast writing skeletons, and the single Python touch (`aggregate --profile podcast` + opt-in `diarize`) — all in the same prompt-engineering workstream.
**Depends on**: Phase 4 (per-mode fps strategy demos in CLAUDE.md need a working schedule format)
**Requirements**: TEACH-01, TEACH-02, TEACH-03, TEACH-04, TEACH-05, TEACH-06, TEACH-07, TEACH-08, TEACH-09, TEACH-10, TEACH-11, TEACH-12, TEACH-13
**Success Criteria** (what must be TRUE):
  1. CLAUDE.md commits Phase 2 to a `mode` tag in `plan.md` (one of `replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`, possibly hybrid) and locks the format spec (timestamp `[HH:MM:SS]`, code-fence-with-lang, image embeds, second-person imperative) regardless of selected mode
  2. CLAUDE.md ships 2-3 hand-authored exemplar `summary.md` skeletons per teaching dimension; running `/summarize-video` on a deliberately principles-heavy video produces concept-explanation output, not the default reproduction guide
  3. `python -m agent.tools aggregate segs.json --profile podcast --out paragraphs.json` produces longer, breath-shaped paragraphs (gap=2.5, max_dur=90, sentence_gap=1.5); `--profile tutorial` is the default and matches current behavior byte-for-byte
  4. `python -m agent.tools diarize <audio>` (opt-in via `requirements-optional.txt`) emits `diarization.json` keyed by speaker turn so podcast docs distinguish speakers; without pyannote installed, the rest of the milestone still works
  5. The whisper-repetition post-pass detector flags any 3-gram repeated >3× consecutively in `segs.json` for human review without auto-deleting (preserves the `不注水不编造` redline)
**Plans**: 3 plans

Plans:
- [ ] 05-01: CLAUDE.md classification + format-spec lock + exemplar skeletons + plan.md/depth_plan.md artifacts (TEACH-01, TEACH-02, TEACH-03, TEACH-04, TEACH-05)
- [ ] 05-02: `aggregate --profile` + `PROFILES` constant + whisper repetition guard + per-profile VAD tuning (TEACH-06, TEACH-07, TEACH-11, TEACH-12)
- [ ] 05-03: `diarize` opt-in subcommand + UI-demo & podcast CLAUDE.md skeletons + `chapters.json` (TEACH-08, TEACH-09, TEACH-10, TEACH-13)
**UI hint**: no

### Phase 6: Multi-Agent Parallelism (Nice-to-Have, ship-or-skip)
**Goal**: Make two Claude Code terminals on different videos safely concurrent — vendor `config.yaml` race closed, long stages locked per-slug, log lines slug-prefixed, cookies read once. Skip cleanly if scope pressure dictates (PROJECT.md K Decision row 4).
**Depends on**: Phase 5 (none of Phases 1-5 require this; only ships if 1-5 land with capacity remaining)
**Requirements**: PARA-01, PARA-02, PARA-03, PARA-04, PARA-05, PARA-06
**Success Criteria** (what must be TRUE):
  1. Running two `python -m agent.tools download <douyin-url>` invocations concurrently no longer corrupts `vendor/douyin_api/.../config.yaml`; the second invocation either serializes cleanly or fails fast with a clear lock message
  2. Running two `transcribe` or `extract_frames_batch` invocations on the same slug fails fast with a clean "slug locked" message instead of producing torn artifacts
  3. Log lines from `agent.tools` are prefixed with the slug (e.g., `[BV132wiz] transcribe: ...`) so two-terminal output is grep-able
  4. CLAUDE.md documents the parallelism contract: per-slug isolation works; concurrent transcribes on different slugs are user's-risk for OOM unless serialized explicitly
**Plans**: 2 plans

Plans:
- [ ] 06-01: `agent/_lock.py` + vendor `config.yaml` lock + per-slug `resume.lock` (PARA-01, PARA-02, PARA-03)
- [ ] 06-02: Slug-prefixed log lines + cookies-in-memory + parallelism contract docs in CLAUDE.md (PARA-04, PARA-05, PARA-06)
**UI hint**: no

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Preflight & Regression Baseline | 0/3 | Not started | - |
| 2. Resume Infrastructure & Cache Correctness | 0/3 | Not started | - |
| 3. Source Refactor + New Sources | 0/3 | Not started | - |
| 4. Frame fps Automation | 0/2 | Not started | - |
| 5. Adaptive Output + UI Demos + Podcasts | 0/3 | Not started | - |
| 6. Multi-Agent Parallelism (NTH) | 0/2 | Not started | - |
