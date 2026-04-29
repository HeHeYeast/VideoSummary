# Codebase Structure

Generated 2026-04-29 from a structured codebase audit (focus: arch).

## Directory Layout

```
videoSummary/
├── agent/                          # Primary first-party tool layer (¥0 CLI)
│   ├── __init__.py                 # Empty package marker
│   ├── tools.py                    # CLI entrypoint: `python -m agent.tools <cmd>`
│   ├── douyin_downloader.py        # 抖音 a_bogus download path (uses vendor/)
│   ├── asr_v2.py                   # Paragraph aggregation over Whisper segments
│   ├── pass1_classify.py           # [legacy/fallback] Frame classification via API
│   ├── frame_store.py              # [legacy/fallback] Frame metadata cache + DETAIL_PROMPTS
│   ├── frames_v2.py                # [legacy] Information-score frame selection
│   ├── embed.py                    # [legacy] CLIP embedding of frames
│   ├── prepare.py                  # [legacy] Offline data layer prep
│   └── smoke_test_fc.py            # [legacy] Function-calling smoke test
├── src/                            # Legacy v1 end-to-end pipeline (paid LLMs)
│   ├── cli.py                      # Entrypoint: `python -m src.cli <url>`
│   ├── pipeline.py                 # Stage orchestrator
│   ├── download.py                 # yt-dlp wrapper (also reused by agent layer)
│   ├── asr.py                      # faster-whisper + VAD (also reused by agent layer)
│   ├── frames.py                   # 1fps + pHash keyframe extraction
│   ├── vision.py                   # Frame description via VectorEngine
│   ├── summarize.py                # Outline → section → polish → assemble
│   ├── llm_client.py               # OpenAI-protocol HTTP client w/ budget guard
│   └── budget.py                   # BudgetGuard
├── vendor/                         # Third-party clones (gitignored)
│   └── douyin_api/                 # Evil0ctal/Douyin_TikTok_Download_API clone
│       └── crawlers/douyin/web/    # `DouyinWebCrawler`, `config.yaml` (cookies)
├── output/                         # Per-video work directories (gitignored)
│   ├── BV132wizyEEB/               # B站: BVID slug
│   │   ├── meta.json               # title/uploader/duration/url/video_path
│   │   ├── video.mp4
│   │   ├── video.info.json         # raw yt-dlp metadata
│   │   ├── cookies.txt             # per-video Netscape cookies (B站 SESSDATA)
│   │   ├── audio.wav               # 16 kHz mono PCM
│   │   ├── segs.json               # [{start, end, text}, ...]
│   │   ├── paragraphs.json         # [{para_id, start, end, text, seg_indices}, ...]
│   │   ├── frames/                 # JPEGs: seg_<start_sec>_<index>.jpg
│   │   └── summary.md              # Final tutorial output (Phase 7)
│   ├── douyin_trae_ai/             # 抖音: snake_case slug, same artifact set
│   ├── godot_brave/
│   └── ... (~58 video work dirs)
├── config/
│   ├── budget_prod.yaml            # USD limits per stage (legacy src/ only)
│   └── budget_test.yaml
├── .claude/settings.local.json     # Bash/WebFetch permission allowlist
├── .planning/codebase/             # GSD codebase analysis docs
├── CLAUDE.md                       # Project guide + /summarize-video workflow
├── AGENT_DESIGN.md, PROJECT_DESIGN.md, PIPELINE_CANDIDATES.md, COST_CONTROL.md, LLM_List.md
├── README.md
├── requirements.txt                # httpx==0.27.2 pinned for vendor compat
├── .env / .env.example
├── .gitignore                      # Excludes .env, output/, vendor/, *cookies*.txt
└── www.douyin.com_cookies.txt      # 抖音 cookies (gitignored)
```

## Directory Purposes

**`agent/`** — First-party ¥0 tool layer. Key files: `agent/tools.py`, `agent/douyin_downloader.py`, `agent/asr_v2.py`. Other agent files are legacy v2 modules retained for `classify_frame` / `ocr_frame` fallback subcommands.

**`src/`** — Legacy v1 fully-automated pipeline (paid LLMs). Two modules (`src/download.py`, `src/asr.py`) are still actively imported by the agent layer. Key files: `src/cli.py`, `src/pipeline.py`, `src/download.py`, `src/asr.py`.

**`vendor/`** — Third-party code mounted at runtime; not modified, not committed (gitignored). Only `vendor/douyin_api/crawlers/douyin/web/web_crawler.py` is imported by first-party code, and `vendor/douyin_api/crawlers/douyin/web/config.yaml` is runtime-patched with the user's 抖音 cookies.

**`output/`** — Per-video work directories; one subdirectory per video; all gitignored. Each is self-contained and independently deletable.

**`config/`** — Budget YAMLs consumed only by legacy `src/` pipeline (`src/budget.py:BudgetGuard.from_yaml`). Not used by `agent.tools`.

**`.claude/`** — Claude Code project-local settings. Contains only `settings.local.json` (Bash/WebFetch allowlist). **No `.claude/commands/` directory exists** — `/summarize-video` is documented in `CLAUDE.md`, not registered as a slash-command file.

**`.planning/codebase/`** — GSD codebase analysis docs (this directory).

## Key File Locations

**Entry points:**
- `agent/tools.py` — primary CLI; subparsers at lines 197-234, dispatcher at lines 241-251.
- `agent/douyin_downloader.py` — secondary CLI for 抖音 debugging (lines 216-225).
- `src/cli.py` — legacy full-pipeline entrypoint.

**Core logic:**
- `agent/tools.py:35-147` — five core `cmd_*` handlers (`cmd_download`, `cmd_transcribe`, `cmd_aggregate`, `cmd_extract_frames`, `cmd_cleanup_frames`).
- `agent/douyin_downloader.py:128-213` — `download_douyin()`.
- `agent/asr_v2.py:28-98` — `aggregate_paragraphs()` (split conditions: gap > 1.5 s, sentence-end + gap > 0.8 s, duration > 30 s).
- `src/asr.py:52-86` — `transcribe()` with VAD + hallucination filter, CPU/CUDA via `ASR_DEVICE`.
- `src/download.py:14-88` — yt-dlp wrapper.

**Configuration:**
- `.env` / `.env.example` — VectorEngine keys, `BILIBILI_SESSDATA`, `DOUYIN_COOKIES_FILE`, `ASR_DEVICE`.
- `www.douyin.com_cookies.txt` — Netscape cookie file at project root (overridable via `DOUYIN_COOKIES_FILE`).
- `requirements.txt` — `httpx==0.27.2` pinned because `vendor/douyin_api` uses the deprecated `proxies=` kwarg.

**Documentation:**
- `CLAUDE.md` lines 47-148 define the `/summarize-video` workflow Phase 1-8.
- `AGENT_DESIGN.md` — v2 design rationale.

## Naming Conventions

**Top-level packages:** `agent/`, `src/`, `vendor/` — flat single-level packages.

**Python files:** `snake_case`. `_v2` suffix (`asr_v2.py`, `frames_v2.py`) marks v2-redesigned modules that coexist with v1.

**Per-video output slugs (`output/<slug>/`):**
- B站: BVID exactly as in URL — `BV132wizyEEB`, `BV1mE421u7ZS`. `src/cli.py:49` derives this as last URL path segment.
- 抖音 / mixed: descriptive `snake_case` chosen by human/Claude — `douyin_trae_ai`, `godot_brave`, `wildfrost_demo`, `pengpeng_strategy`.
- The URL is recorded inside `output/<slug>/meta.json["url"]`.

**Artifact filenames within `output/<slug>/`:**
- `meta.json` — title/uploader/duration/url/video_path; 抖音 adds `aweme_id` and `source: "douyin"`.
- `video.mp4` (or `.mkv`/`.webm`/`.flv` per `src/download.py:66-69`).
- `video.info.json` — raw yt-dlp dump (B站 path only).
- `audio.wav` — 16 kHz mono PCM.
- `segs.json` — `[{start, end, text}, ...]`.
- `paragraphs.json` — `[{para_id, start, end, text, seg_indices}, ...]`; `para_id` follows `p%04d` (e.g. `p0000`).
- `cookies.txt` — per-video Netscape cookies (`src/download.py:28-33` when `BILIBILI_SESSDATA` is set).
- `summary.md` — final tutorial.
- `frames.json`, `frame_descs.json`, `budget_report.txt` — produced only by legacy `src/pipeline.py`.

**Frame filenames within `output/<slug>/frames/`:**
- Pattern: `seg_<start_seconds_zero_padded_4>_<frame_index_zero_padded_6>.jpg`.
- Examples: `seg_0005_000002.jpg`, `seg_0030_000015.jpg`.
- Generated by `agent/tools.py:114-116`: `prefix = f"seg_{int(args.start):04d}_"`, ffmpeg pattern `<prefix>%06d.jpg`.
- Encodes `--start` so multiple invocations don't overwrite each other.
- Timestamp reconstruction: `ts = start + (frame_index - 0.5) / fps` (`agent/tools.py:123`).
- Legacy `src/frames.py:30` uses the different pattern `frame_%06d.jpg`.

## Where to Add New Code

**A new ¥0 CLI subcommand:**
- Add `cmd_<name>(args)` in `agent/tools.py` (alongside lines 35-188).
- Register subparser in `main()` (lines 197-234).
- Add `"<name>": cmd_<name>` to `cmds` dict (line 241).
- Heavy logic goes in a new `agent/<name>.py`; import lazily after `sys.path.insert(0, project_root)` (pattern at `agent/tools.py:37, 64, 91, 152, 172`).

**A new download source:**
- Branch in `agent/tools.py:cmd_download` (lines 41-56) by URL substring before yt-dlp fallback.
- Implement in `agent/<source>_downloader.py` mirroring `agent/douyin_downloader.py`; normalize output to the shared `meta.json` schema.
- If a third-party crawler is needed, clone under `vendor/<source>/` and document setup in `CLAUDE.md`.

**A new ASR / paragraph post-processor:**
- Add to `agent/asr_v2.py` (already hosts `aggregate_paragraphs`, `get_transcript_window`, `search_transcript`).
- Expose via new subcommand in `agent/tools.py`.

**Project-level docs:** root markdown for design rationale, `.planning/codebase/` for GSD analysis.

**Per-video artifacts:** Always write to `output/<slug>/` to preserve caching/cleanup.

**Tests:** Legacy smoke test at `agent/smoke_test_fc.py`. No formal test directory or framework — see `TESTING.md`.

## Special Directories

**`vendor/`:** External code, runtime `sys.path` injection at `agent/douyin_downloader.py:86-87`. Gitignored. **Mutated at runtime** — `agent/douyin_downloader.py:_patch_config_cookie` rewrites `vendor/douyin_api/crawlers/douyin/web/config.yaml` Cookie line before each 抖音 download.

**`output/`:** Per-video artifacts. Gitignored. No shared state across slug directories.

**`__pycache__/`:** Bytecode cache in `agent/__pycache__/` and `src/__pycache__/`. Gitignored.

## How Skills/Commands Relate to Tools

The `/summarize-video` "skill" is **not a registered Claude Code slash-command file** — there is no `.claude/commands/summarize-video.md` or skill manifest in this repo. Instead:

1. `CLAUDE.md` is loaded into Claude Code's context as project memory at every session start.
2. When the user says "总结这个视频" or pastes a B站/抖音 URL, Claude Code recognizes the trigger described in `CLAUDE.md` line 49 and expands the eight-phase workflow (lines 51-148) inline.
3. Phases 1, 3, 7, 8 emit `Bash` calls of the form `python -m agent.tools <subcommand> ...` — these are the only Python-level operations.
4. Phases 2, 4, 5, 6 are pure-LLM operations: `Read meta.json`, `Read paragraphs.json`, `Read frames/seg_*.jpg` (multimodal), `Write summary.md`. No Python participates.
5. `.claude/settings.local.json` pre-authorizes the relevant Bash invocations (`Bash(python:*)`, `Bash(python -m src.cli ...)`, etc.).

In short: **`agent/tools.py` is the surface area of the "skill"**; the "skill" itself is the prompt in `CLAUDE.md` teaching Claude when and how to call those subcommands.

---
*Structure analysis: 2026-04-29*
