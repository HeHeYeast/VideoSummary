# Project Research Summary

**Project:** videoSummary — Claude-driven video-to-tutorial pipeline (¥0 brownfield expansion)
**Domain:** Local-first multimodal video documentation (single-user, Windows 11 zh-CN host)
**Researched:** 2026-04-30
**Confidence:** HIGH for backward-compat architecture and known integrations; MEDIUM for YouTube-from-China path and pyannote diarization stack; LOW only for novel "Claude-as-decision-maker" failure modes that have no precedent in the wild.

## Executive Summary

This milestone is a **brownfield expansion** of an already-shipped ¥0 video-to-tutorial pipeline. The existing 5-command CLI (`download / transcribe / aggregate / extract_frames / cleanup_frames`), the `output/<slug>/` directory layout, and the 8-phase `/summarize-video` workflow are **load-bearing** — 17 archived tutorials in the queue depend on them and must keep running unchanged. Every new capability ships as **additive opt-in** (new subcommands, new sidecar JSON files, new CLAUDE.md teaching modes) — never as schema changes, never as flag-gated mode switches, never as renames.

The architecture research lands a strong, opinionated cut: **adaptiveness is prompt engineering, not Python.** The "let Claude decide what kind of teaching this video deserves" feature has zero LOC of new code — it's CLAUDE.md edits plus optional `plan.md` audit artifacts. Per-segment fps automation gets a small `agent/scheduler.py` data layer + `extract_frames_batch` CLI that *executes* a Claude-written `schedule.json` but *never decides* fps. New sources (YouTube / generic / local mp4) refactor the existing `if douyin_url else ...` substring dispatch into a clean `agent/sources/` registry — foundational because Capabilities 5/6 depend on a unified `meta.json` source field. Mid-failure resume layers an append-only `state.json` event log on top of the existing file-existence cache, plus mandatory `<artifact>.params.json` sidecars so cache reuse becomes parameter-aware (today's silent stale-reuse hazard).

Three risks dominate. **(1) Regression on the legacy queue** — if any milestone change drifts the `meta.json` / `paragraphs.json` / `frames/seg_*.jpg` schemas, the 17 archived dirs break re-run; mitigation is a **Phase 1 golden-output regression suite** locked before any feature lands. **(2) "Every video looks the same"** — without exemplar pins in CLAUDE.md, Claude collapses to step-by-step reproduction (the shape of all 17 existing archives) even on principles-heavy or podcast content; mitigation is hand-authored skeletons per teaching mode. **(3) Diarization gate for podcast mode** — faster-whisper has no speaker labels, so podcast docs read as monologues without `pyannote.audio`; pyannote is opt-in (HF token + ~700 MB torch dep) and is the single biggest "ships-or-doesn't" call for Capability 5b. We ship the rest of the milestone without it; podcast mode lights up only when pyannote is installed.

## Key Findings

### Recommended Stack

The existing stack (`yt-dlp`, vendor `douyin_api`, `faster-whisper`, `ffmpeg`, `Pillow`, `imagehash`, Claude Code as multimodal layer) is **stable and not being replaced**. All additions are surgical, scoped to the 7 milestone gaps. See `.planning/research/STACK.md` for full version-compat matrix and Windows-specific gotchas.

**Core additions (always-on, in `requirements.txt`):**
- **`yt-dlp >=2026.03.17`** (upgrade pin from existing) — YouTube extractor changed substantially in early 2026 (SABR rollout, mandatory PO Tokens for some clients).
- **`PySceneDetect 0.6.7.1`** — scene-cut timeline that Claude reads as **decision support** for fps planning. Tool emits `scenes.json`; Claude reads + decides + writes `schedule.json`.
- **`silero-vad >=5.1`** standalone — speech-density timeline for podcast/interview segmentation.
- **`filelock >=3.16`** — cross-platform advisory lock for parallelism (Phase 6 only).

**Opt-in (`requirements-optional.txt`, only loaded when needed):**
- **`pyannote.audio 4.0.x`** + `pyannote/speaker-diarization-community-1` — speaker diarization for podcasts. HF token + ~150 MB model + ~700 MB torch dep. Gates podcast mode shipping cleanly.
- **`stable-ts >=2.19`** — word-level timestamp refinement (only if word-precision needed).
- **`yt-dlp-get-pot`** — auto-fetch YouTube PO Tokens.
- **Deno** (system PATH, `winget install DenoLand.Deno`) — yt-dlp's YouTube JS challenge solver.

**Hard locks (do NOT bump):**
- **`httpx==0.27.2`** — vendor `douyin_api` uses deprecated `proxies=` kwarg removed in 0.28+. Single most fragile compat constraint in the stack.

**What NOT to use:** any paid API (¥0 violation); `youtube-dl` (dead for YT in 2026); `whisperx` as faster-whisper replacement (Python 3.13 incompat per m-bain/whisperX#1202); cursor-tracking via OpenCV (~50 MB OpenCV-full for marginal gain); `multiprocessing.Pool` invoking faster-whisper concurrently from one process (CTranslate2 sequential internals).

### Expected Features

See `.planning/research/FEATURES.md`. Competitive position: **"the only video-doc tool where the model is the decision-maker, not the prompt template's decoration."** Every BibiGPT / NoteGPT / NotebookLM / Otter / Notta is "transcribe → LLM template-fill → embed a few frames" with one fixed output shape.

**Must have (P1, table stakes — feels broken without):**
- **YouTube + generic yt-dlp routing** (T3) — yt-dlp's flagship platform.
- **Local mp4 path input** (T4) — already-downloaded videos shouldn't require re-downloading.
- **Backward-compat `output/<slug>/` layout** — 17 archived + 17 queued videos. Constraint, not a build.
- **Re-run after partial failure without losing work** (T6).
- **Adaptive single-document teaching output** (T1) — Core Value deliverable.
- **Per-segment fps schedule batch-executed by tool** (T2) — most-cited friction.

**Should have (P2):**
- **UI-demo writing mode** (T5a).
- **Podcast/interview writing mode + diarization** (T5b) — gated on pyannote stack decision.
- **Optional scene-change probe (`scenes.json`)** — only ship if Phase 4 validation shows it would help.
- **Stale-downstream auto-detect in pipeline status.**

**Defer (P3, NTH or future milestone):**
- **Multi-agent parallelism** (T7) — per PROJECT.md K Decision: "做不到也没关系".
- **Quote-card extraction** (only if user's queue trends shareable).
- **Auto-fps-plan from scenes + transcript** (would cross "Claude is decider" line).

**Anti-features (explicit NO):**
- Multi-output document modes — PROJECT.md K Decision row 2.
- Fully automatic fps/scene/outline (zero human review) — defeats Core Value.
- Queue auto-runner / batch-mode unattended — PROJECT.md OOS.
- Web UI / dashboard / cloud sync — single-user, ¥0; OOS.
- Paid LLM/ASR/Vision API as fallback — ¥0 hard constraint.
- Cursor-highlight overlay on UI demo frames — recording-time feature, not post-hoc.
- Translation / multi-lang output — not the actual user need.

**Cross-check vs PROJECT.md Out of Scope:** No conflicts. FEATURES anti-features are a strict superset.

### Architecture Approach

Two non-negotiable invariants from `.planning/research/ARCHITECTURE.md`:

1. **Claude is the decision-maker, the tool is the limb.** Tools may *reduce friction* but must NEVER *make judgment calls*. When a capability could be implemented as either "smarter Python" or "smarter Claude prompting", we **default to prompting**.
2. **Backward-compatible: existing 5 commands, `output/<slug>/` layout, 8-phase `/summarize-video` workflow MUST keep working unchanged.** No subcommand renamed or removed. No artifact format changed in non-additive ways. No directory layout changed.

**Major components (all NEW, all additive):**

1. **`agent/sources/` package** + **`agent/url_router.py`** — One file per platform (`bilibili.py` / `douyin.py` / `youtube.py` / `generic.py` / `local.py`); `Source` Protocol with `match()` + `fetch()`. Pure-function routing. Replaces 2-branch substring check at `agent/tools.py:42`. Foundational.
2. **`agent/scheduler.py`** + **`extract_frames_batch` CLI** — `Schedule` dataclass + JSON I/O + validation. Claude **writes** `schedule.json` directly via Write tool. Tool only validates shape and executes ffmpeg N times. Existing single-segment `extract_frames` stays.
3. **`agent/state.py`** + **`output/<slug>/state.json`** — Append-only event log, per-stage and per-segment-frame granularity. Augmenting, never authoritative-alone.
4. **`agent/asr_v2.py` extension** — `aggregate_paragraphs(profile=...)` accepts `tutorial` (default `gap=1.5, max_dur=30, sentence_gap=0.8`) or `podcast` (`gap=2.5, max_dur=90, sentence_gap=1.5`).
5. **CLAUDE.md teaching modes** — Phase 2 classification step + Phase 5 mode-specific output skeletons + format-spec lock + 2-3 hand-authored exemplar skeletons per dimension. **Zero LOC of Python.**
6. **`agent/_lock.py` + per-slug `resume.lock`** (Capability 7, last) — `filelock` wrapper around vendor `config.yaml` patching and long-running stages.

**Locked schedule.json schema** (synthesized from ARCHITECTURE proposal + PITFALLS validation requirements):

```json
{
  "version": 1,
  "video": "video.mp4",
  "default_scale": "854:-1",
  "default_quality": 4,
  "segments": [
    {"start": 0,   "end": 30,  "fps": 0.2, "label": "intro"},
    {"start": 30,  "end": 240, "fps": 0.4, "label": "code-demo-part1"},
    {"start": 240, "end": 245, "skip": true, "label": "filler-question"},
    {"start": 245, "end": 600, "fps": 0.3, "label": "code-demo-part2"}
  ]
}
```

**Validation rules** (`agent/scheduler.py` enforces; fail loud, never silent):
- `version: 1` mandatory; future schema bumps add migration logic, not flag-gated parsing.
- Segments MUST cover `[0, duration)` ± 2s (P2.4). Gaps in coverage = error. Implies a low-rate baseline (e.g. fps 0.05) MUST be present somewhere.
- Segments MUST NOT overlap.
- Each segment requires either `fps: float` OR `skip: true` (mutually exclusive).
- `label` optional, surfaces in stdout for grep-ability.
- Unknown top-level or per-segment keys = error.
- Filename convention `seg_<start>_<index>.jpg` preserved unchanged.

### Critical Pitfalls

Top 5 showstoppers from `.planning/research/PITFALLS.md` mapped to recommended phases:

1. **U1 / U2: Legacy regression on the 17-archive queue.** Avoidance: **Phase 1 commits a 3-video golden-output baseline** (`BV132wizyEEB`, `godot_brave`, `douyin_trae_ai`). Every milestone change must reproduce these. Cost: ~30 min one-time. **Severity: meta-showstopper.**
2. **P7.1: Stale-cache silent reuse when params change.** Avoidance: **every artifact gets `<artifact>.params.json` sidecar; loaders compare current params; mismatch → regenerate with loud "regenerating because: X changed" log.** Phase 2 deliverable.
3. **P1.3: "Every video looks the same" — Claude lacks priors.** Avoidance: **hand-author 2-3 minimal exemplar `summary.md` skeletons in CLAUDE.md** per teaching dimension. Phase 5 — without this, the entire T1 deliverable is at risk.
4. **P2.1: Silent visual content goes undersampled.** Three layers: (a) silence map flagging gaps > 5s, (b) **mandatory low-rate baseline pass (fps 0.05)** in every schedule, (c) documented 补抽 step in CLAUDE.md. Lands **with** Phase 4, not after.
5. **P4.1: Chinese filenames in subprocess args on Windows zh-CN.** Avoidance: **always copy/symlink local mp4 input into `output/<slug>/video.mp4` first**, with ASCII-safe slug normalization (hash + first 8 ASCII chars). Reject CJK paths in `--out`. Phase 3 deliverable.

**Cross-cutting U3 (Windows/encoding/proxy/locale)** — multiplicative failure surface from GBK + UTF-8 + GFW + proxy + zh-CN locale. Mitigation is **infrastructure, not a phase**: enforce `encoding="utf-8"` on every `open()` (Phase 1 audit), set `PYTHONUTF8=1`, document `chcp 65001` per terminal, forward `HTTPS_PROXY`/`HTTP_PROXY` to yt-dlp.

**P3.1 (YouTube GFW + SABR + PO-token + cookies multiplicative failure)** — 2-second `yt-dlp --simulate` preflight that classifies failure category. Graceful fallback: any YouTube failure suggests local-mp4 path. **YouTube and local-mp4 ship in the same phase** (Phase 3) — they're each other's safety net.

**P6.1 (pyannote diarization)** — single biggest "ships-or-doesn't" call for podcast. **Opt-in via `requirements-optional.txt`, podcast mode lights up only when installed**. Phase 5 prerequisite, not deliverable — rest of milestone ships independent.

## Implications for Roadmap

**5 phases (+ NTH 6th), with cross-cutting infrastructure woven into Phase 2 rather than its own phase.**

The ordering reconciles three competing pulls:
- STACK suggests "local mp4 before YouTube" (lower-risk validation of source-refactor).
- ARCHITECTURE suggests "Adaptive parallelizable / C+D coupled / E last" (dependency DAG).
- PITFALLS demands "Phase 0 Preflight (golden suite) → Phase 1 Resume infrastructure FIRST" (every other feature benefits from params.json + atomic writes + schema_version).

**Synthesis: Preflight → Resume infrastructure → Source refactor (with local-mp4 + YouTube together) → fps automation → Adaptive output + new video types → Parallelism (NTH).**

### Phase 1: Preflight & Regression Baseline

**Rationale:** YOLO-coarse mode predictably skips infrastructure that doesn't move the demo forward. Lock the regression suite *before* any feature lands or risk silent drift catching us at video #3 in queue.

**Delivers:**
- `tests/regression/` directory with committed baseline `summary.md` snapshots from `BV132wizyEEB` (code), `godot_brave` (game/Godot), `douyin_trae_ai` (AI/UI tool).
- `regression-check.md` runbook for re-running new flow + manual diff.
- `schema_version: 1` retroactively documented for `meta.json` / `segs.json` / `paragraphs.json` (loaders default to v1 when field absent).
- Encoding audit: every `open()` in `agent/` + `src/` has explicit `encoding="utf-8"`. `PYTHONUTF8=1` documented in CLAUDE.md alongside `chcp 65001`.

**Addresses pitfalls:** U1 (golden regression — meta-showstopper), U2 (schema freeze), U3 (encoding audit, partial).

**Does NOT deliver:** any new feature. Pure preflight. ~30 min - 1 day.

### Phase 2: Resume Infrastructure & Cache Correctness

**Rationale:** Every subsequent phase varies parameters. Building resume *first* means features in Phase 3-5 can swap whisper model / VAD threshold / fps schedule without silently reusing stale upstream artifacts.

**Delivers:**
- **`<artifact>.params.json` sidecar pattern** — every artifact-writing function in `agent/tools.py` writes a sidecar capturing the parameters that produced it (whisper_model, vad_settings, ffmpeg_version, profile). Loaders compare; mismatch → regenerate with loud log.
- **Atomic writes via `tempfile.NamedTemporaryFile(dir=target.parent) → os.replace(tmp, target)`** — wraps all artifact JSON writes. Same-volume-only constraint enforced. Retry-with-backoff on `PermissionError` (Windows Search / Defender / OneDrive may hold lock).
- **`agent/state.py`** — append-only `state.json` event log with `derived_state(events)` reducer. Per-stage and per-segment-frame granularity. File-existence fallback if state.json missing/corrupt.
- **`schema_version` field** on every artifact going forward, with loader migration logic (currently no-op pass-through — sets the precedent).
- **`doctor` CLI subcommand** — read-only scan showing existence + mtime + sidecar params per artifact.

**Addresses pitfalls:** P7.1 (params.json sidecars — showstopper), P7.2 (atomic writes), P7.3 (PermissionError retry), P7.4 (schema_version), U3 (final encoding/locale).

**Backward-compat:** Slugs without state.json or sidecars treated as "events list empty" / "params unknown but accepted" — current behavior preserved.

**Stack:** stdlib only (`tempfile`, `os.replace`).

### Phase 3: Source Refactor + New Sources (YouTube + Local mp4 + Generic)

**Rationale:** Foundational per ARCHITECTURE's build DAG — Capabilities 3 (YouTube/generic) and 4 (local mp4) are independent of 1/2/5/6 except via the unified `meta.json source` field. **Local-mp4 is YouTube's graceful fallback** when GFW/SABR/PO-token chain fails.

**Delivers:**
- `agent/sources/` package: `__init__.py` (Protocol + registry), `bilibili.py`, `douyin.py`, `youtube.py`, `generic.py`, `local.py`.
- `agent/url_router.py` — pure routing function. First test target (closes CONCERNS §9.1 zero-coverage gap).
- `ingest` subcommand. `download` becomes thin shim — backward-compat, observable behavior identical for B站/抖音.
- `meta.json` extended with `source`, `youtube_id`, `aweme_id` (additive, optional).
- YouTube layer: 2-second `yt-dlp --simulate` preflight classifying failure (GFW / cookies stale / PO-token / version too old). `HTTPS_PROXY` / `HTTP_PROXY` forwarded as `--proxy`. yt-dlp version warning if older than 90 days. `subtitle_origin: auto|creator|asr|none` recorded.
- Local-mp4 layer: copy/symlink to `output/<slug>/video.mp4` with ASCII-safe slug normalization. Reject CJK paths with clean error. ffprobe preflight for codec/audio-track/VFR validation. `-vsync vfr` applied uniformly.
- Pin `yt-dlp >=2026.03.17` in `requirements.txt`. Document Deno + `yt-dlp-get-pot` as opt-in.

**Addresses pitfalls:** P3.1 (YouTube failure classifier — showstopper for YT), P3.2-3.4 (version drift, subtitle_origin, generic metadata), P4.1 (Chinese filename slug — showstopper for local), P4.2-4.3 (ffprobe preflight, `-vsync vfr`).

**Stack:** `yt-dlp >=2026.03.17` (upgrade pin), opt-in `yt-dlp-get-pot` + Deno.

### Phase 4: Frame fps Automation (`schedule.json` + `extract_frames_batch`)

**Rationale:** Most-cited friction (P1, MEDIUM complexity). Builds on Phase 2's state.json (resume needs to skip done segments) and Phase 3's unified `meta.json` (any source feeds same fps pipeline). Lands before Phase 5 because Phase 5's teaching modes need to *use* schedules to demonstrate per-mode fps strategies.

**Delivers:**
- `agent/scheduler.py` — `Schedule` dataclass + JSON I/O + strict validation (full-duration coverage, no overlap, no unknown keys, fail-loud parser per P2.3).
- `extract_frames_batch` CLI — loads `schedule.json`, validates, iterates segments, calls existing `extract_frames` core per segment. `seg_<start>_<index>.jpg` filename convention preserved. Resume-aware via state.json.
- **Mandatory low-rate baseline pass** — schedule validation requires either fps 0.05-ish whole-video segment OR explicit per-segment coverage of all silence regions (P2.1).
- Optional `scenes.json` artifact via PySceneDetect — Claude reads as decision support, never auto-promoted to schedule.
- Optional `silence_map.json` from silero-vad — gaps > 5s flagged.
- `extract_frames` (single-segment) CLI **stays** — for补抽 corrections.

**Addresses pitfalls:** P2.1 (silent visual content + baseline pass — showstopper), P2.2 (sudden cuts via scene_probe), P2.3 (strict schedule schema), P2.4 (duration coverage).

**Stack:** PySceneDetect 0.6.7.1, silero-vad >=5.1, Pillow + imagehash (existing) for optional pHash dedup.

### Phase 5: Adaptive Output + New Video Types (UI Demos + Podcasts)

**Rationale:** ARCHITECTURE locks adaptiveness as **prompt engineering, not Python**. T1 (adaptive doc), T5a (UI demos), T5b (podcasts) all live in CLAUDE.md as teaching modes. Same prompt-engineering workstream — ship together. Single Python touch is `aggregate --profile podcast`. **Pyannote opt-in via `requirements-optional.txt`** — podcast mode lights up only when installed.

**Delivers:**
- **CLAUDE.md teaching modes** — Phase 2 classification step (`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`); Phase 5 mode-specific output skeletons; format-spec lock (timestamp `[HH:MM:SS]`, code fence with explicit lang, image embed `![](frames/...)`, second-person imperative — content adaptive, form not, P1.2).
- **Hand-authored exemplar skeletons** in CLAUDE.md (P1.3) — 2-3 per dimension. **Without these, T1 is at risk.**
- `output/<slug>/plan.md` artifact — Claude writes in Phase 2; free-form, no schema enforcement.
- `output/<slug>/depth_plan.md` (optional) — Claude commits depth decision before any prose; resume checkpoint (P1.5).
- `agent/asr_v2.py` extension — `aggregate_paragraphs(profile=...)` with `PROFILES` constant.
- `aggregate --profile {tutorial|podcast}` CLI flag — default = current behavior.
- **Pyannote integration (opt-in)** — `diarize` subcommand emits `diarization.json` keyed by speaker turn. HF token gate documented in CLAUDE.md alongside douyin-cookies setup. Spike before Phase 5 commits.
- **Podcast-mode skeleton** in CLAUDE.md skips `extract_frames` (or 1-2 frames per chapter). Output emphasizes speaker turns + key claims + timestamp navigation.
- **UI-demo skeleton**: pixel-text quote-with-uncertainty rule, tooltip-blocking, cursor-invisibility fallback, 1280/1920px override for 4K recordings.
- **Whisper repetition guard** for long podcasts — post-pass detector flags any 3-gram repeated >3× consecutive for human review (don't auto-delete — `不注水不编造` redline). Tightened VAD `min_silence_duration_ms=500`.
- `chapters.json` (Claude-written, podcast-mode) — `[{start, end, topic_title, summary_line}]` for rambling content.

**Addresses pitfalls:** P1.1-1.5 (adaptive output failure modes), P5.1-5.3 (UI demo accuracy), P6.1 (diarization — showstopper for podcast), P6.2-6.4 (whisper repetition guard, chapters.json, skip frames in podcast).

**Stack:** opt-in `pyannote.audio 4.0.x` + community-1 model + HF token. Optional `stable-ts`.

### Phase 6: Multi-Agent Parallelism (Nice-to-Have)

**Rationale:** PROJECT.md K Decision row 4: "做不到也没关系". Mostly docs + opt-in lock files. Per-slug isolation already holds; actual hazards are vendor `config.yaml` race (CONCERNS §2.2) and whisper concurrent-load OOM. Skip cleanly if not done.

**Delivers:**
- `agent/_lock.py` — `filelock`-based cross-platform advisory lock helper.
- Vendor `config.yaml` lock — wraps `_patch_config_cookie` + crawler call. Concurrent 抖音 downloads serialize.
- `output/<slug>/resume.lock` — for stages > 1 minute (`transcribe`, `extract_frames_batch`).
- Whisper concurrent-load guidance — document RAM expectations; optional file-lock to serialize transcribes.
- Log line slug prefix `[BV132wiz]` / `[godot_brave]` (P8.4).
- Cookies file read-into-memory at download start (P8.3).

**Addresses pitfalls:** P8.1-8.4 (vendor config race, whisper OOM, cookies race, log interleaving — all showstoppers IF parallel ships).

**Stack:** `filelock >=3.16`.

### Phase Ordering Rationale

- **Preflight first** — YOLO-coarse mode skips it and pays at video #3. 30-min cost, highest ROI.
- **Resume infrastructure second** — every subsequent feature varies parameters; sidecars MUST exist before parameter variation.
- **Source refactor third** — user-visible Phase-1 wins; unblocks downstream by establishing unified `meta.json source` field; local-mp4 is YouTube's safety net.
- **fps automation fourth** — most-cited friction; feeds Phase 5's per-mode fps demos.
- **Adaptive output + new video types fifth** — same CLAUDE.md prompt-engineering workstream. Pyannote opt-in here.
- **Parallelism last** — PROJECT.md downgraded to NTH; per-slug isolation already holds for casual use.

**Cross-cutting infrastructure (NOT a separate phase):** Atomic writes, params.json sidecars, schema_version, encoding="utf-8" audit, slug normalization — all **Phase 2 deliverables**. Roadmapper should NOT spin into separate phase.

### Research Flags

**Phases likely needing deeper `/gsd-research-phase`:**
- **Phase 5:** pyannote spike on Windows CPU + HF token UX flow + CLAUDE.md exemplar authoring (subjective, iterate against real videos).
- **Phase 3:** YouTube anti-bot landscape changed Q1 2026; re-verify yt-dlp + plugin landscape at integration; test failure-classifier on user's actual proxy.

**Phases with standard patterns (skip research):**
- **Phase 1:** Pure ops.
- **Phase 2:** stdlib (`os.replace`, `tempfile`, append-only event log).
- **Phase 4:** PySceneDetect + silero-vad APIs documented; schedule-validation is data-layer.
- **Phase 6:** `filelock` documented; vendor config-lock straightforward.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing stack empirically stable. Additions verified against official docs. MEDIUM only on YouTube-from-China path. |
| Features | HIGH | Existing capabilities from PROJECT.md / CLAUDE.md / `.planning/codebase/`. Competitor matrix surveyed ~10 tools. Anti-features cross-checked vs PROJECT.md OOS — no conflicts. MEDIUM only on diarization-stack feasibility for ¥0 single-user. |
| Architecture | HIGH | Grounded in actual code + `.planning/codebase/*` (commit `c20d425`). MEDIUM only on schedule.json shape and parallelism (no precedent in repo). |
| Pitfalls | HIGH | Documented integrations all have GitHub issues / official docs as sources. MEDIUM on novel "Claude-as-decision-maker" failure modes (P1.x family) — extrapolated. |

**Overall confidence:** HIGH — strong consensus across 4 research files, no major contradictions, brownfield expansion (existing system is ground truth).

### Gaps to Address

- **Pyannote diarization spike (Phase 5 prerequisite).** Run on real 30-60 min podcast on user's Windows machine; measure wall time + RAM. If 3-5× audio length intolerable, fall back to "Claude attributes by content cues". **Resolution: spike in early Phase 5 planning.**
- **YouTube end-to-end on user's proxy setup (Phase 3).** 5-variable chain. Validate with one real YT URL during Phase 3 implementation; if any silently fails, fall back to local-mp4.
- **CLAUDE.md exemplar authoring (Phase 5).** Subjective; benefits from iteration against real videos. **Resolution: Phase 5 planning identifies 1 representative video per dimension; exemplars written + reviewed before rest of Phase 5 lands.**
- **state.json + schedule.json schema migration story (Phase 2 + 4).** Pattern needs documenting in Phase 2 even if not invoked. **Resolution: Phase 2 deliverables include one-page "schema migration runbook".**
- **No unit-test precedent in codebase** (CONCERNS §9.1). 4 first targets are obvious (`url_router.py`, `scheduler.py`, `state.py`, `aggregate_paragraphs`) — all pure functions. **Resolution: not a research gap, planning note.**

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` (Core Value, Constraints, Active, Key Decisions, Out of Scope) — anchor for backward-compat / ¥0 / Claude-as-decider invariants.
- `.planning/codebase/` (ARCHITECTURE / STACK / CONCERNS / CONVENTIONS / INTEGRATIONS / STRUCTURE / TESTING, commit `c20d425`) — ground truth for existing system.
- `.planning/research/STACK.md` — version-compat matrix, Windows gotchas, alternatives.
- `.planning/research/FEATURES.md` — ecosystem comparison, competitor matrix, anti-features.
- `.planning/research/ARCHITECTURE.md` — component boundaries, build-order DAG, schedule.json + state.json proposals.
- `.planning/research/PITFALLS.md` — severity-mapped failure modes, phase-mapping table.

### Secondary (MEDIUM confidence)
- yt-dlp 2026 reality (SABR / PO-token / GFW): wiki + GitHub issues #15865 #16221 #13067 #10128 — re-check at Phase 3.
- pyannote.audio 4.0 + community-1 model: HF model card + GitHub — UX needs Phase 5 spike.
- BibiGPT / NoteGPT / NotebookLM / Otter / Notta product surfaces — confirms competitor tools all use fixed templates.

### Tertiary (LOW confidence)
- aiadoptionagency.com Silero VAD 2026 guide — single-source; cross-check at Phase 4.
- Estimated complexity per feature (LOW/MEDIUM/HIGH labels in FEATURES) — engineering judgment, treat as planning estimate.

---
*Research completed: 2026-04-30*
*Ready for roadmap: yes*
