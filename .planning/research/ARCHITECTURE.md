# Architecture Research

**Domain:** Claude-orchestrated local video-to-tutorial pipeline (¥0, brownfield expansion)
**Researched:** 2026-04-30
**Confidence:** HIGH for backward-compat strategy and module boundaries (grounded in actual code at `agent/tools.py`, `agent/asr_v2.py`, `agent/douyin_downloader.py` and `.planning/codebase/*`); MEDIUM for schedule format JSON shape and parallelism strategy (no precedent in repo, derived from existing conventions).

> This document does **not** re-survey the existing system — that lives in `.planning/codebase/ARCHITECTURE.md`. It only specifies how the 7 new capabilities **plug in** without breaking the existing layout.

---

## North Star Constraint

Every architectural choice below is subordinate to two non-negotiables:

1. **Claude is the decision-maker, the tool is the limb.** Tools may *reduce friction* (turn one ffmpeg call into ten via a schedule, route URLs to the right downloader) but must NEVER *make judgment calls* (pick fps, pick chapters, pick teaching depth, pick which frames matter).
2. **Backward-compatible: the existing 5 commands, the `output/<slug>/` layout, and the 8-phase `/summarize-video` workflow MUST keep working unchanged.** 17 queued videos depend on the old path.

When a capability could be implemented as either "smarter Python" or "smarter Claude prompting", we **default to prompting** and only add Python when the operation is mechanical (a pure transform with no judgment).

---

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       Claude Code (Decision Layer)                        │
│                                                                           │
│  Reads transcripts, JPEGs, meta.json. Decides:                            │
│    - Video type (code/UI/podcast/lecture)                                 │
│    - Teaching depth (replicate / explain / extend)                        │
│    - fps schedule (which segments deserve dense framing)                  │
│    - Outline + section structure + final prose                            │
│                                                                           │
│  Drives the tools layer via Bash + Read tool calls.                       │
└────────────────────────┬─────────────────────────────────────────────────┘
                         │ Bash / Read
        ┌────────────────┴─────────────────────────────────────────┐
        │                                                           │
        ▼                                                           ▼
┌──────────────────────┐                              ┌─────────────────────┐
│  agent/tools.py      │                              │  output/<slug>/     │
│  (CLI Surface)       │                              │  (Filesystem state) │
│                      │                              │                     │
│  EXISTING (kept):    │                              │  meta.json          │
│   download           │                              │  video.mp4          │
│   transcribe         │                              │  audio.wav          │
│   aggregate          │                              │  segs.json          │
│   extract_frames     │                              │  paragraphs.json    │
│   cleanup_frames     │                              │  frames/seg_*.jpg   │
│                      │                              │  summary.md         │
│  NEW (additive):     │     ─────reads/writes────▶   │                     │
│   ingest             │                              │  NEW (additive):    │
│     (multi-source)   │                              │  state.json         │
│   extract_frames_    │                              │  schedule.json      │
│     batch            │                              │  resume.lock        │
│   doctor             │                              │                     │
└──────────┬───────────┘                              └─────────────────────┘
           │
           ▼
┌────────────────────────────────────────────────────────────────────┐
│              Implementation Modules (agent/, src/, vendor/)         │
│                                                                     │
│  EXISTING (kept):                                                   │
│    src/download.py        — yt-dlp wrapper (B站, generic)           │
│    src/asr.py             — faster-whisper                          │
│    agent/asr_v2.py        — paragraph aggregation                   │
│    agent/douyin_downloader.py — vendor crawler glue                 │
│                                                                     │
│  NEW (additive):                                                    │
│    agent/sources/         — pluggable downloader registry           │
│      __init__.py          — Source protocol + dispatch              │
│      bilibili.py          — wraps src.download.download             │
│      douyin.py            — wraps agent.douyin_downloader           │
│      youtube.py           — yt-dlp w/ YT cookie support             │
│      generic.py           — yt-dlp fallback                         │
│      local.py             — local mp4 path → meta.json synthesis    │
│    agent/scheduler.py     — Schedule dataclass + JSON I/O           │
│    agent/state.py         — state.json read/write/checkpoint        │
│    agent/url_router.py    — URL → source name (pure function)       │
└────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Boundary Rule |
|-----------|----------------|---------------|
| `agent/tools.py` | CLI dispatch only — argparse → cmd_* handlers. Lazy imports. | Never grows business logic. New subcommand = new module. |
| `agent/sources/` (NEW) | One file per platform. Each exposes `match(url) -> bool` and `download(url, out_dir, **kw) -> meta_dict`. | Stateless. Output `meta.json` schema is identical regardless of source. |
| `agent/url_router.py` (NEW) | Pure function: `route(url_or_path) -> source_name`. Replaces the substring check in `cmd_download`. | No I/O. No side effects. ~30 LOC. |
| `agent/scheduler.py` (NEW) | `Schedule` dataclass, JSON serialize/deserialize, validation. **Does NOT decide fps** — only carries Claude's decision. | Pure data layer. No ffmpeg. No Claude calls. |
| `agent/state.py` (NEW) | `state.json` reader/writer with stage-completion checkpoints. Append-only event log model. | Idempotent. Safe under concurrent reads (writes are single-process per slug). |
| `agent/asr_v2.py` (existing) | Paragraph aggregation. **Add** podcast-tuned thresholds via parameter, not branch. | Thresholds are inputs, not constants. |
| `src/download.py`, `src/asr.py` | Untouched. Still imported by both layers. | These are the "stable bedrock". Don't refactor. |
| `vendor/douyin_api/` | Untouched. Cookie patching stays in `agent/douyin_downloader.py`. | Still gitignored. Still requires manual setup. |

---

## How Each of the 7 Capabilities Plugs In

Each capability gets its own subsection: **What problem**, **Where the code lives**, **Where Claude's decision lives**, **Backward-compat impact**.

### Capability 1 — Adaptive Teaching Output

**What problem:** Current `/summarize-video` Phases 5-6 produce "字幕翻译式" output for some videos because the prompt prescribes a one-size-fits-all tutorial template. A code-heavy demo, a UI walkthrough, and a podcast all get the same step-numbered structure.

**Where the code lives:** **Nowhere new.** This is **pure prompt engineering**, not Python.

  - **NOT** in a Python module that probes the transcript. Probing is a judgment call — it must stay with Claude.
  - **NOT** a new CLI command. Claude makes the call inline.

**What changes:**
  - Augment `CLAUDE.md` Phase 2 ("Read & plan") with an explicit **classification step**: after reading paragraphs.json, Claude commits to a teaching mode (`replicate-guide`, `concept-explanation`, `extension-applications`, `interview-distillation`, or hybrid mix). The mode is recorded in a new optional artifact `output/<slug>/plan.md` (Claude-written, plaintext, no schema enforcement).
  - Augment Phase 5 with mode-specific output skeletons (still all in CLAUDE.md, not in Python). Each mode names its sections, time-stamp density, code-block expectations.
  - The user's **single-document** decision (PROJECT.md Key Decisions row 2) means **no template selector at the CLI level** — Claude picks the mode in-context and writes one `summary.md`.

**Backward-compat impact:** Zero. Old slugs that don't have `plan.md` still re-run cleanly under either old or new prompt. Old `summary.md` files are not regenerated.

**Why this is right:** Per the North Star — "tools don't make judgments". Adaptiveness IS judgment. If we put it in Python, we'd be hardcoding heuristics ("if word_count > X and code_lines_per_frame > Y → replicate-guide") that will be wrong for the next video. Claude reading the transcript end-to-end is strictly better.

### Capability 2 — Frame fps Automation (the meaty one)

**What problem:** Today Claude must mentally convert "this 4-min code segment deserves dense framing" into 8-12 separate Bash calls with `--start`, `--end`, `--fps` triples, often miscounting boundaries and re-running. High friction for the human reviewing the conversation, and high token cost for Claude doing arithmetic.

**Where the code lives:**
  - **NEW module:** `agent/scheduler.py` — defines the `Schedule` dataclass and JSON schema. Pure data layer. ~80 LOC.
  - **NEW CLI subcommand:** `extract_frames_batch` (better name than `extract_frames_planned` — "planned" implies the tool plans, which is wrong). Lives in `agent/tools.py` next to existing `cmd_extract_frames`. ~30 LOC.

**Where Claude's decision lives:**
  - Claude **writes** the schedule JSON file directly (using the `Write` tool) into `output/<slug>/schedule.json`. This is identical to how Claude already writes `summary.md` — file-as-API.
  - Claude does NOT invoke a "planner" Python module. There is no planner. Claude is the planner.
  - The tool only validates the JSON shape and executes ffmpeg N times.

**Schedule file format (proposal):**

```json
{
  "version": 1,
  "video": "video.mp4",
  "default_scale": "854:-1",
  "default_quality": 4,
  "segments": [
    {
      "start": 0,
      "end": 30,
      "fps": 0.2,
      "label": "intro",
      "skip": false
    },
    {
      "start": 30,
      "end": 240,
      "fps": 0.4,
      "label": "code-demo-part1"
    },
    {
      "start": 240,
      "end": 245,
      "skip": true,
      "label": "filler-question"
    },
    {
      "start": 245,
      "end": 600,
      "fps": 0.3,
      "label": "code-demo-part2"
    }
  ]
}
```

  - `version: 1` — schema versioning so future changes don't break old slugs.
  - `video` — relative path inside the slug dir; defaults to `video.mp4`.
  - `default_scale` / `default_quality` — match current `agent/tools.py:113` defaults.
  - `segments[].skip` — first-class way to express "explicitly skip this range" (today Claude just doesn't emit a Bash call for it; making it explicit means the schedule is auditable).
  - `segments[].label` — human-readable tag, optional, surfaces in stdout for grep-ability (`stdout: extract seg start=30 end=240 fps=0.4 label=code-demo-part1`).
  - **No** `model_size`, `voice_anchor_score`, or other fields that would tempt the tool to "decide" anything.

**CLI invocation:**

```bash
python -m agent.tools extract_frames_batch \
  --schedule output/BVxxx/schedule.json \
  --out output/BVxxx/frames
```

Implementation: load JSON, validate shape, iterate `segments`, for each non-skip segment call the same ffmpeg block already used by `cmd_extract_frames`. Filename convention `seg_<start>_<index>.jpg` is preserved unchanged so frame-name conventions in `summary.md` and `cleanup_frames` keep working.

**Backward-compat impact:** Zero. `extract_frames` (single-segment) command stays. Claude can still call it when only one range is needed.

**Build-order dependency:** This blocks Capability 4 (local mp4) and Capability 5 (UI demos / podcasts) only loosely — those work with the old single-segment command too. But mid-failure resume (Capability 6) should know about schedules so it can re-run only the missing segments.

### Capability 3 — YouTube + Generic yt-dlp + Capability 4 — Local mp4 Input

**What problem:** Today `cmd_download` does `if "douyin.com" in url.lower(): ... else: src.download.download(url)`. Adding YouTube + generic + local would turn that into a 5-branch if-chain. Worse, "local mp4" isn't a download at all — it's a meta.json synthesis step, which doesn't fit the `download` semantics.

**Where the code lives:**
  - **NEW package:** `agent/sources/` — one file per platform.
  - **NEW pure module:** `agent/url_router.py` — replaces the substring check.
  - **NEW CLI subcommand:** `ingest` — semantically broader than `download` (handles both URLs and local paths).
  - **EXISTING `download` subcommand stays** as a backward-compat thin wrapper that calls `ingest` internally with auto-routing.

**Source protocol** (`agent/sources/__init__.py`):

```python
from typing import Protocol

class Source(Protocol):
    name: str  # "bilibili" | "douyin" | "youtube" | "generic" | "local"

    def match(self, url_or_path: str) -> bool:
        """Return True iff this source can handle the input."""

    def fetch(self, url_or_path: str, out_dir: Path, **opts) -> dict:
        """Materialize video.mp4 + meta.json into out_dir. Return meta dict."""
```

**Source files:**

| File | What it does | Reuses |
|------|--------------|--------|
| `agent/sources/bilibili.py` | Match `bilibili.com` / `b23.tv` / `BV` slug. Wraps `src.download.download`. | `src/download.py` (no change) |
| `agent/sources/douyin.py` | Match `douyin.com` / `iesdouyin.com` / `v.douyin.com`. Wraps `agent.douyin_downloader.download_douyin`. | `agent/douyin_downloader.py` (no change) |
| `agent/sources/youtube.py` | Match `youtube.com/watch` / `youtu.be`. Calls `src.download.download` with YT cookie envvars (`YOUTUBE_COOKIES_FILE` or `YOUTUBE_COOKIES_BROWSER`). | `src/download.py` |
| `agent/sources/generic.py` | Last-resort fallback for any other URL. Calls `src.download.download` (yt-dlp will try its 1500+ extractors). | `src/download.py` |
| `agent/sources/local.py` | Match `Path(input).is_file() and suffix in {.mp4, .mkv, .webm, .flv, .mov}`. **Does no download.** Copies (or symlinks where supported) the file into `out_dir/video.mp4`, runs `ffprobe` for duration, synthesizes `meta.json` with `source: "local"`, `title` defaulting to filename stem (Claude can override via `--title`). | ffprobe |

**Routing** (`agent/url_router.py`):

```python
from agent.sources import bilibili, douyin, youtube, local, generic

# Order matters — first match wins. Local before any URL-based matcher because
# a local file path is unambiguous and free to test.
SOURCES = [local, bilibili, douyin, youtube, generic]

def route(url_or_path: str):
    for src in SOURCES:
        if src.match(url_or_path):
            return src
    raise RuntimeError(f"no source matched: {url_or_path}")
```

Pure function. ~25 LOC. Trivially unit-testable (good first target for the test-coverage gap noted in CONCERNS §9).

**`ingest` subcommand:**

```bash
python -m agent.tools ingest <url-or-path> --out output/<slug> [--title "..."] [--source bilibili|douyin|youtube|generic|local]
```

`--source` overrides the router (useful when Claude knows the URL is mis-detected, e.g. a Bilibili re-upload of a Douyin video).

**`download` subcommand becomes:**

```python
def cmd_download(args):
    # Backward-compat shim. Old callers and CLAUDE.md unchanged.
    return cmd_ingest(args)
```

**`meta.json` schema, unified:**

```json
{
  "source": "bilibili|douyin|youtube|generic|local",
  "url": "<original URL or absolute local path>",
  "video_path": "<absolute path to video.mp4>",
  "title": "...",
  "uploader": "..." | null,
  "duration": 600.5,
  "aweme_id": "..." | null,   // 抖音 only
  "youtube_id": "..." | null  // YouTube only
}
```

Existing `meta.json` files (which lack `source` for old B站 ones) are still valid — readers must tolerate the absence and default to `source: "bilibili"` or `null`. Don't auto-rewrite old files.

**Backward-compat impact:** Zero. Old `download` calls work. Old `meta.json` files work. The substring-check dispatch in `agent/tools.py:42` is **deleted** but its behavior is exactly replicated by the routing table.

**Build-order dependency:** This is **foundational** for Capabilities 5 (new video types — UI demos and podcasts can come from any of these sources) and 6 (resume — needs to know which source to re-run from). Build first.

### Capability 5 — New Video Types (UI Demos, Podcasts/Interviews)

**What problem:** UI demos (non-code software walkthroughs) need slightly different framing strategies (more stable shots, less code-density emphasis). Podcasts/interviews are **画面价值低** — frames matter little, audio structure dominates.

**Architectural question:** Do podcasts get their own pipeline, sharing only `download` + `transcribe`? Do UI demos?

**Answer: NO new pipeline; YES different prompting.** Specifically:

  - **UI demos:** identical Python pipeline (download → transcribe → aggregate → schedule frames → write). The **only** difference is Claude's frame-density choices and the teaching mode (Capability 1). No code change required.

  - **Podcasts/Interviews:** identical Python pipeline up through `aggregate`. Then:
    - Frame extraction is **optional, sparse** — maybe 1 frame per 2-3 minutes, just for "who's talking" identification or visualizing slides if any. Claude makes the call inline.
    - The output skeleton (in CLAUDE.md as a teaching mode) emphasizes **speaker turns, key claims, timestamp navigation** rather than step-by-step instructions.
    - **No new CLI command** — `/summarize-podcast` is NOT warranted. The decision of "this is a podcast → use interview-distillation mode" is made by Claude in Phase 2.

**The boundary line for "warrants its own command":**

| Signal | Verdict |
|--------|---------|
| Different download path? | No → same `ingest` |
| Different transcription? | No → same `transcribe` (faster-whisper handles speech well regardless of code/UI/voice) |
| Different aggregation parameters? | **Yes for podcasts** — longer paragraphs, different gap threshold |
| Different frame strategy? | Yes but Claude already controls it via schedule.json |
| Different output structure? | Yes but that's prompting (CLAUDE.md teaching modes), not Python |

The only place that genuinely diverges is **paragraph aggregation thresholds**. Therefore:

**Code change:** Extend `cmd_aggregate` to accept `--profile {tutorial|podcast}` (default: `tutorial`). The profile selects the threshold tuple `(gap_threshold, max_para_duration, sentence_end_gap)`. Defaults stay at current `(1.5, 30.0, 0.8)` so no existing slug is affected. Podcast profile something like `(2.5, 90.0, 1.5)` (longer breath, longer paras).

**Where Claude decides which profile:** in Phase 2, Claude reads paragraphs.json (with default profile), realizes "this is interview pacing, paragraphs are too choppy", deletes paragraphs.json, re-runs `aggregate --profile podcast`. The decision is Claude's; the parameter is exposed to it.

**Anti-pattern avoided:** Auto-detecting "podcast vs tutorial" from segs.json features. That would be a tool making a judgment.

**Backward-compat impact:** Zero. Default profile = current behavior.

### Capability 6 — Mid-Artifact Failure Resume

**What problem:** Today's "cache by file existence" works great for the happy path but is lossy when:
  - A `transcribe` run crashes after writing 80% of segs (no partial file currently — `transcribe` is atomic, but a long ASR can be interrupted by Ctrl-C and produces nothing usable).
  - An `extract_frames_batch` schedule has 8 segments and crashes on the 5th (the first 4 frames are on disk; the next 3 are missing; re-running blindly would re-extract all 8).
  - The user re-tunes the schedule (changes fps for one segment) and wants to extract only the changed range.

**Where state lives:**

  - **NEW file per slug:** `output/<slug>/state.json` — append-only event log of completed stages and per-segment frame extraction status.
  - **NEW module:** `agent/state.py` — read/write/checkpoint helpers.

**state.json shape (proposal):**

```json
{
  "version": 1,
  "slug": "BVxxx",
  "events": [
    {"ts": "2026-04-30T10:00:00Z", "stage": "ingest", "status": "ok", "source": "bilibili"},
    {"ts": "2026-04-30T10:01:30Z", "stage": "transcribe", "status": "ok", "model": "small", "duration_s": 92.3},
    {"ts": "2026-04-30T10:01:45Z", "stage": "aggregate", "status": "ok", "profile": "tutorial"},
    {"ts": "2026-04-30T10:02:00Z", "stage": "extract_frames", "status": "ok", "segment": {"start": 0, "end": 30, "fps": 0.2, "label": "intro"}, "frames_count": 6},
    {"ts": "2026-04-30T10:02:30Z", "stage": "extract_frames", "status": "ok", "segment": {"start": 30, "end": 240, "fps": 0.4, "label": "code-demo-part1"}, "frames_count": 84},
    {"ts": "2026-04-30T10:03:00Z", "stage": "extract_frames", "status": "fail", "segment": {"start": 240, "end": 600, "fps": 0.3, "label": "code-demo-part2"}, "error": "ffmpeg exit 1"}
  ]
}
```

  - **Append-only.** Each stage handler appends a JSON object on completion. Crashes between writes mean we lose at most the in-flight stage's record (acceptable — re-running detects the missing record and re-does that stage).
  - **Reconstructable from events.** `derived_state(events)` returns the highest-watermark for each stage, so consumers ask "is `aggregate` done?" not "what's the latest event?".
  - **Per-segment granularity for frame extraction.** When `extract_frames_batch` runs against a schedule, it consults state.json to skip already-completed segments. Each segment is keyed by `(start, end, fps, label)` — if any of those change, it's a new segment, do the work.

**The boundary: "delete and rerun" is still acceptable**

  - For `meta.json`, `segs.json`, `paragraphs.json` (the small JSON artifacts that compute fast or already work as atomic-write): existing file-existence cache is sufficient. state.json adds an audit trail but no behavior change.
  - For frames (the only stage with batch-of-N execution and meaningful partial-progress cost): state.json is the truth, file existence is the fallback. If state.json is missing or corrupt, the tool falls back to current "skip if frame files match the segment's pattern" behavior.

**Resume semantics:**

```bash
# explicit
python -m agent.tools extract_frames_batch --schedule schedule.json --out frames/ --resume

# implicit (default new behavior — read state.json, skip done segments, do missing ones)
python -m agent.tools extract_frames_batch --schedule schedule.json --out frames/

# force redo
python -m agent.tools extract_frames_batch --schedule schedule.json --out frames/ --force
```

`transcribe`/`aggregate` already have `--force`; we extend the same idiom.

**Backward-compat impact:** Zero. Slugs without state.json are treated as "events list is empty" → current behavior. State.json is created on first new-CLI run for a slug.

**Build-order dependency:** Depends on Capability 2 (schedule format). Comes after sources (Cap 3-4) because state.json records the source.

### Capability 7 — Multi-Agent Parallelism (Nice-to-Have)

**What problem:** Two Claude Code terminals each running `/summarize-video` on different videos should not stomp each other.

**Per-slug isolation is mostly free:**
  - `output/<slug>/` is already isolated.
  - `state.json` is per-slug.
  - `schedule.json` is per-slug.
  - Whisper model load is per-process (each Claude session spawns its own Python process per command).

**Shared global state — actual hazards:**

| Resource | Hazard | Mitigation |
|----------|--------|-----------|
| `vendor/douyin_api/crawlers/douyin/web/config.yaml` | Two concurrent 抖音 downloads each rewrite the cookie line; race condition in `_patch_config_cookie`. (Already flagged in CONCERNS §2.2.) | Add a file-lock advisory lock in `agent/douyin_downloader.py`. Use Python's `portalocker` (cross-platform) or a simple `agent/_lock.py` wrapping `msvcrt.locking` on Windows. Lock the config.yaml during `_patch_config_cookie` + the entire crawler call. Document: "concurrent 抖音 downloads serialize". |
| `www.douyin.com_cookies.txt` | Read-only; no hazard from concurrent reads. | None. |
| `.env` | Read-only after `load_dotenv()`. | None. |
| ffmpeg | Each invocation is a fresh subprocess. CPU/memory contention is the real cost, not correctness. | Document: "concurrent ffmpeg jobs share CPU; expect 2x wall time, not 0.5x". |
| faster-whisper | Each call loads its own model instance. CPU/RAM contention; can OOM on `medium`/`large` models with two parallel runs. | Document RAM expectations. Optional: a `doctor` subcommand that checks free RAM before transcribe. |
| Windows file locks on `video.mp4` while ffmpeg reads it | None — multiple ffmpeg readers OK. The slug isolation prevents two writers. | None. |

**Lock file proposal (lightweight):**

`output/<slug>/resume.lock` — created by stage handlers that take >1 minute (`transcribe`, `extract_frames_batch`). Other processes attempting the same stage on the same slug see the lock and either wait, fail loudly, or (if the lock is stale per timestamp) take it. Explicitly **per-slug**, not global.

**Anti-pattern avoided:** Building a queue/scheduler/worker daemon. Per PROJECT.md Out-of-Scope: "队列全自动无人值守批跑" is excluded. Multi-agent here means "two human-driven sessions don't stomp each other", not "supervised batch processor".

**Backward-compat impact:** Zero. Locks are advisory; single-process runs ignore them.

**Build-order dependency:** Last. Skip cleanly if not done — single-agent mode keeps working.

---

## Backward-Compat Strategy (Explicit)

**The promise:** `git checkout` of an old commit, `pip install -r requirements.txt`, `python -m agent.tools download <BV-url> --out output/X` — works identically. No env var required, no flag required, no migration step.

**How that promise is kept:**

1. **No subcommand renamed or removed.** All 5 existing commands (`download`, `transcribe`, `aggregate`, `extract_frames`, `cleanup_frames`) keep their exact signatures. New commands are **added**: `ingest`, `extract_frames_batch`, `doctor`. The old `download` becomes a thin wrapper around `ingest` — observable behavior is identical for B站 and 抖音 URLs.

2. **No artifact format changed in a non-additive way.** `meta.json` gets new optional fields (`source`, `youtube_id`); old readers ignore them. `segs.json`, `paragraphs.json`, frame filenames: unchanged. New artifacts (`schedule.json`, `state.json`, `plan.md`) live alongside; their absence is silently handled.

3. **No directory layout changed.** `output/<slug>/` and `output/<slug>/frames/` are sacred. New files go inside the slug dir, never new top-level dirs in the slug.

4. **No CLAUDE.md instruction removed.** The 8-phase workflow stays. New phases or sub-steps are **inserted** with explicit "if not using adaptive mode, skip this" guards. Build a parallel block "v2 adaptive workflow" for users who opt in via prompt phrasing — there is no `/summarize-video-v2` slash command file; both flows live in CLAUDE.md.

5. **Feature flags via opt-in CLI flags, not env vars.** Env vars are global and cross-slug-contaminating. CLI flags scope cleanly:
   - `extract_frames_batch` exists alongside `extract_frames`. Old workflow uses old command.
   - `ingest --source local <path>` is opt-in for local mp4. Old workflow uses `download <url>`.
   - `aggregate --profile podcast` is opt-in. Default = old behavior.
   - `--resume` flag for state-aware reruns. Default = current "skip if exists" behavior.

6. **The "quick revert" path:** Set the orchestrator (CLAUDE.md) to use only the existing 5 commands. The new modules sit in `agent/` unused. Verifies that the new code is truly additive.

**What's explicitly NOT done (anti-patterns to avoid):**

  - **No `VERSION` env var or `MODE=v2` flag** controlling pipeline shape. Mode-switching globals are a maintenance trap.
  - **No deprecation warnings** on the old commands. They're not deprecated; they're parallel valid paths.
  - **No data migration** of existing `output/<slug>/` directories. The 17 queued + ~58 archived folders are touched by zero migration scripts.
  - **No removal of `src/`, `agent/prepare.py`, `agent/frames_v2.py`, `agent/embed.py`** etc. Per Out-of-Scope: "重写或废弃现有 agent/ src/ 模块". CONCERNS §1.2 flags these as orphaned, and they stay orphaned. Deletion happens in a separate cleanup milestone, not this one.

---

## Build Order (Dependency DAG)

```
                    ┌──────────────────────────────┐
                    │ 0. URL Router + Source       │
                    │    Protocol (foundation)     │
                    │    agent/url_router.py       │
                    │    agent/sources/__init__.py │
                    └──────────┬───────────────────┘
                               │
                ┌──────────────┴──────────────┐
                ▼                             ▼
    ┌───────────────────────┐    ┌────────────────────────┐
    │ 1. Source: bilibili,   │    │ 2. Source: youtube,    │
    │    douyin (refactor    │    │    generic, local      │
    │    existing into       │    │    (NEW capability)    │
    │    sources/)           │    │                        │
    └──────────┬─────────────┘    └────────────┬───────────┘
               │                                │
               └──────────────┬─────────────────┘
                              ▼
              ┌───────────────────────────────┐
              │ 3. ingest subcommand          │
              │    download → ingest shim     │
              │    (Caps 3 + 4 functional)    │
              └──────────────┬────────────────┘
                             │
              ┌──────────────┼──────────────────┐
              ▼              ▼                  ▼
   ┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐
   │ 4. Schedule      │ │ 5. aggregate   │ │ 6. CLAUDE.md     │
   │    format +      │ │    --profile   │ │    teaching      │
   │    extract_      │ │    podcast     │ │    modes         │
   │    frames_batch  │ │    (Cap 5      │ │    (Cap 1        │
   │    (Cap 2 core)  │ │     partial)   │ │     adaptive)    │
   └────────┬─────────┘ └────────────────┘ └──────────────────┘
            │
            ▼
   ┌──────────────────┐
   │ 7. state.json    │
   │    + resume      │
   │    semantics     │
   │    (Cap 6)       │
   └────────┬─────────┘
            │
            ▼
   ┌──────────────────┐
   │ 8. Locking +     │
   │    doctor        │
   │    subcommand    │
   │    (Cap 7,       │
   │     nice-to-     │
   │     have)        │
   └──────────────────┘
```

**Critical path observations:**

  - **0 → 3 unblocks Capabilities 3 + 4 in one shot.** Don't build YouTube without first refactoring the existing sources into the new pluggable shape, or you'll end up with a 4-way if-chain.
  - **Capability 1 (adaptive) is parallel.** It's just CLAUDE.md edits. Can ship before, after, or alongside any code work. Lowest risk, highest UX win — consider shipping first.
  - **Capability 2 (fps automation) and Capability 6 (resume) are coupled.** Resume needs to know about the schedule to skip done segments. Build schedule first, then state.json reads schedules.
  - **Capability 5 (new video types) splits in two:** the prompting half ships with Capability 1 (CLAUDE.md only); the aggregation-profile half ships independently as a small `cmd_aggregate` parameter.
  - **Capability 7 (parallelism) goes last and is genuinely nice-to-have.** Even without the file lock, two concurrent 抖音 downloads have a race window of milliseconds. Two concurrent transcribes on different videos work fine today (different slugs, different processes). The hazard is real but rare.

**Recommended phase grouping for the roadmap:**

  - **Phase A — Adaptive output (CLAUDE.md only).** Ship Capability 1. ~0 LOC Python, all prompting. Validates the "Claude as decision-maker" architecture works for teaching depth.
  - **Phase B — Source refactor + new sources.** Capabilities 3 + 4 + the aggregation-profile slice of 5. Foundational; everything depends on a unified `meta.json` source field eventually.
  - **Phase C — Schedule + batch frame extraction.** Capability 2. The biggest friction reducer.
  - **Phase D — Resume + state.json.** Capability 6. Builds on Phase C's schedule format.
  - **Phase E — Parallelism polish.** Capability 7. Optional.

---

## Data Flows for the 3 Most Novel Features

### Flow A: Adaptive Teaching Output

```
Phase 1: Bash → ingest, transcribe, aggregate         [unchanged]
Phase 2: Read meta.json + paragraphs.json
         ↓
         Claude classifies video type (in-context)
         ↓
         Claude commits to teaching mode + outline
         ↓
         Write output/<slug>/plan.md  ← NEW (free-form, optional)
Phase 3: Claude writes schedule.json (see Flow B)     [NEW for adaptive path]
Phase 4: Read frames                                  [unchanged]
Phase 5-6: Claude writes summary.md per chosen mode   [mode-aware prompting]
```

No Python module sees the teaching mode. It exists only in `plan.md` (audit trail) and in Claude's context. The mode does not affect any tool behavior except via the schedule (Claude chooses denser fps for replicate-guide vs sparser for podcast mode).

### Flow B: fps Automation

```
Phase 2: Claude reads paragraphs.json
         ↓
         Claude composes Schedule object in-context
         ↓
         Write output/<slug>/schedule.json
Phase 3: Bash → extract_frames_batch --schedule schedule.json --out frames/
         ↓
         agent/scheduler.py: load + validate JSON
         ↓
         For each non-skip segment:
           1. Read state.json (Flow D); skip if segment already done
           2. ffmpeg with the same filename pattern as existing extract_frames
           3. Append "extract_frames" event to state.json
         ↓
         Stdout: per-segment summary (start, end, fps, frames_count, label)
```

The tool is a loop over the existing `extract_frames` core. No new ffmpeg semantics. The novelty is the JSON shape and the per-segment state recording.

### Flow C: Podcast/Interview Pipeline

```
ingest:              [unchanged] — yt-dlp or local handles podcast video files identically
transcribe:          [unchanged] — faster-whisper handles speech regardless of content type
aggregate --profile podcast:
         ↓
         agent/asr_v2.py: aggregate_paragraphs(segs, gap=2.5, max_dur=90, sentence_gap=1.5)
         ↓
         paragraphs.json with longer, speaker-turn-shaped paragraphs
Phase 2: Claude reads → recognizes podcast → "interview-distillation" mode
Phase 3: Claude writes a sparse schedule.json (1 frame per ~2 min, just for slide/face capture)
         ↓
         extract_frames_batch (small N)
Phase 5-6: Claude writes summary.md in interview-distillation mode
         (timestamp-anchored claims, speaker turns, key takeaways)
```

The only Python divergence is the `--profile` parameter on `aggregate`. Everything else is prompting + Claude judgment.

### Flow D: Mid-Failure Resume

```
Any stage runs → on success, append event to state.json
              → on failure, append fail event with error string

Re-running a stage on the same slug:
   1. Read state.json
   2. Compute derived state: highest watermark per stage
   3. For atomic stages (ingest, transcribe, aggregate): if last event is "ok", skip (existing behavior); if "fail" or missing, redo (existing behavior)
   4. For batched stages (extract_frames_batch): per segment, check if a matching "ok" event exists; skip those, do missing ones
   5. If state.json is missing/corrupt: fall back to file-existence cache (current behavior)
```

state.json is **augmenting**, never **authoritative-alone**. File existence remains the ground truth — state.json is a richer index over it.

---

## Anti-Patterns (Domain-Specific)

### Anti-Pattern 1: Auto-Detecting Video Type in Python

**What people do:** Write a `agent/classifier.py` that probes paragraphs.json features (avg paragraph length, code-symbol density, named-entity ratio) and outputs `video_type: "tutorial"|"podcast"|"ui_demo"`.

**Why it's wrong:** This is judgment, not transformation. It will be wrong on edge cases (a podcast about coding, a tutorial that's mostly talking-head). Tuning the heuristics becomes the project. Claude reading the transcript handles ambiguity natively.

**Do this instead:** Claude reads paragraphs.json in Phase 2 and decides. The decision is recorded in `plan.md` for audit, not consumed by any tool.

### Anti-Pattern 2: A "Smart" extract_frames That Picks fps For You

**What people do:** Add `extract_frames_auto` that runs voice-anchor regex (`agent/frames_v2.py:VOICE_ANCHOR_PATTERNS`) over paragraphs.json and emits frames at "interesting" timestamps.

**Why it's wrong:** This is exactly what `agent/frames_v2.py` does and exactly why it was abandoned (CONCERNS §1.2). The 19-pattern regex misses obvious cues (CONCERNS §2.7). The score thresholds are tuning-locked. **The tool decided, and it decided badly.** Worse, when it decides poorly, Claude can't override gracefully.

**Do this instead:** `extract_frames_batch` consumes Claude's schedule. Claude is the only thing that "scores" segments — by reading the transcript with a brain.

### Anti-Pattern 3: A Unified `pipeline` Subcommand

**What people do:** Add `python -m agent.tools pipeline <url>` that does ingest → transcribe → aggregate → schedule → extract → write in one shot.

**Why it's wrong:** Removes Claude from the loop. The whole point of staged invocation is that Claude makes a decision **between** stages (which fps, which frames to read, which mode). A monolithic `pipeline` reverts to the v1 `src/cli.py` model that was abandoned.

**Do this instead:** Stages stay separate. Claude orchestrates. If batching multiple slugs is desired, that's a separate manual loop, not a pipeline command.

### Anti-Pattern 4: state.json as Authoritative Truth

**What people do:** Treat state.json as the cache key. If state.json says transcribe is done but segs.json is missing, trust state.json and skip transcribe.

**Why it's wrong:** state.json can be stale (manual file deletion, partial backup restore, copy-paste of slug dir). Files on disk are reality.

**Do this instead:** state.json is an index. File-existence checks are still authoritative. A stage runs if EITHER (state.json says undone) OR (artifact missing). A stage skips if BOTH (state.json says done) AND (artifact present).

### Anti-Pattern 5: Versioning the Pipeline via env Var

**What people do:** `VIDEOSUMMARY_VERSION=v2 python -m agent.tools download ...` to switch between old and new code paths.

**Why it's wrong:** Global mode switches contaminate every command. A v2 download that crashes mid-run leaves a v2-shaped meta.json that v1 transcribe might mis-parse. The combinatorial test surface explodes.

**Do this instead:** New behaviors get new subcommands or new flags. Old subcommands keep their old behavior. The CLI surface area grows; existing surface stays frozen.

---

## Specific File/Module Proposals (Concrete Names + Sketch LOC)

| Path | Status | Purpose | Est. LOC |
|------|--------|---------|----------|
| `agent/url_router.py` | NEW | Pure routing function `route(url_or_path) -> Source`. | 25 |
| `agent/sources/__init__.py` | NEW | `Source` Protocol, registry list, `route()` re-export. | 30 |
| `agent/sources/bilibili.py` | NEW | Match B站 URLs; thin wrapper over `src.download.download`. | 25 |
| `agent/sources/douyin.py` | NEW | Match 抖音 URLs; thin wrapper over `agent.douyin_downloader`. | 20 |
| `agent/sources/youtube.py` | NEW | Match YT URLs; yt-dlp w/ YT cookie envvars. | 50 |
| `agent/sources/generic.py` | NEW | Fallback yt-dlp call. | 20 |
| `agent/sources/local.py` | NEW | Match local paths; copy + ffprobe + meta synth. | 60 |
| `agent/scheduler.py` | NEW | `Schedule` dataclass, JSON load/save, validate. | 80 |
| `agent/state.py` | NEW | state.json append-event + derived-state. | 100 |
| `agent/_lock.py` | NEW (Cap 7) | Cross-platform file lock helper. | 40 |
| `agent/tools.py` | EXTEND | Add `cmd_ingest`, `cmd_extract_frames_batch`, `cmd_doctor`. Keep `cmd_download` as shim. | +120 |
| `agent/asr_v2.py` | EXTEND | `aggregate_paragraphs` accepts profile dict; expose `PROFILES` constant. | +30 |
| `agent/douyin_downloader.py` | EXTEND | Wrap `_patch_config_cookie` + crawler call in advisory file lock. | +20 |
| `CLAUDE.md` | EXTEND | Add Phase 2 classification step, Phase 3 schedule.json step, teaching modes section, podcast workflow note. | +150 lines |
| `tests/` (new dir) | NEW | First unit tests: `test_url_router.py`, `test_scheduler.py`, `test_state.py`. Targets the pure-function modules. | 200 |
| `output/<slug>/schedule.json` | NEW artifact | Per-slug, written by Claude. | (data) |
| `output/<slug>/state.json` | NEW artifact | Per-slug, written by tools. | (data) |
| `output/<slug>/plan.md` | NEW artifact | Per-slug, written by Claude in Phase 2. Optional. | (data) |
| `output/<slug>/resume.lock` | NEW artifact | Per-slug, advisory; auto-removed on stage end. | (data) |

**Modules NOT touched:** `src/download.py`, `src/asr.py`, `src/cli.py`, `src/pipeline.py`, `src/budget.py`, `vendor/douyin_api/*`. Touching them would risk the legacy fallback path and put us in a refactor that PROJECT.md Out-of-Scope explicitly forbids.

**Tests-first opportunity:** `agent/url_router.py`, `agent/scheduler.py`, `agent/state.py`, `agent/asr_v2.py:aggregate_paragraphs` are all pure functions or pure-data layers. They are tractable for the codebase's first real unit tests (closing CONCERNS §9.1's "zero unit tests" gap) without requiring fixture videos.

---

## Sources

- `.planning/codebase/ARCHITECTURE.md` — existing system design (read before this doc; not duplicated)
- `.planning/codebase/STRUCTURE.md` — file layout conventions (`output/<slug>/` schema, frame naming `seg_<start>_<index>.jpg`)
- `.planning/codebase/CONCERNS.md` — orphan modules (§1.2), 抖音 cookie race (§2.2), substring dispatch fragility (§1.3), zero test coverage (§9.1), no frame caching (§5.3)
- `.planning/codebase/CONVENTIONS.md` — `cmd_*` pattern, dispatch dict, `--force` idiom, `pathlib.Path` discipline, lazy imports for heavy deps
- `.planning/PROJECT.md` — backward-compat hard requirement, "Claude is decision-maker" constraint, Out-of-Scope list (no rewrite, no batch automation, no multi-template output)
- `CLAUDE.md` — current `/summarize-video` 8-phase workflow (Phase 2 + 4-6 are pure Claude, no Python)

---

*Architecture research for: Claude-orchestrated local video-to-tutorial pipeline (brownfield)*
*Researched: 2026-04-30*
