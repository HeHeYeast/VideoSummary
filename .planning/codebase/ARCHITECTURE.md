# Architecture

**Analysis Date:** 2026-04-29

## Pattern Overview

**Overall:** CLI tool acting as a **staged data pipeline** orchestrated by Claude Code (the LLM is the controller, not a script). Each stage is a self-contained subprocess invocation that reads/writes files in a per-video working directory. The pipeline is deliberately **decision-free** — Claude Code chooses parameters (which URL, which fps, which time ranges, which frames to actually open) and performs all the "intelligence" steps (frame interpretation, outlining, writing) inside its own context using multimodal `Read` of JPEGs.

**Key Characteristics:**
- **¥0-cost design**: All five core CLI commands are fully local (yt-dlp / vendor crawler / faster-whisper / ffmpeg). No paid API is required for the documented `/summarize-video` workflow.
- **File-based stage handoff**: Stages communicate exclusively through JSON / WAV / MP4 / JPEG artifacts on disk inside `output/<slug>/`. There is no in-memory pipeline object; every stage can be re-run independently.
- **Caching by artifact existence**: Each command checks for its output file (`meta.json`, `segs.json`, `paragraphs.json`, frames matching a glob) and skips work if it already exists — re-invoking the workflow is idempotent.
- **Two parallel implementations coexist**:
  - `agent/` — current ¥0 toolset exposed as `python -m agent.tools <subcommand>`. This is what `CLAUDE.md` documents.
  - `src/` — earlier v1 end-to-end pipeline (`src.cli` → `src.pipeline.run`) that called paid LLMs for outline/section/polish via `VectorEngine`. Kept for backward compatibility and for the optional `classify_frame` / `ocr_frame` fallback commands. The agent layer reuses `src.download.download` and `src.asr.{extract_audio,transcribe,parse_vtt}` for the parts that are still pure-local.
- **Claude Code as the orchestrator**: The entire `Phase 2 → Phase 7` of `CLAUDE.md` (understanding subtitles, picking abstraction strategies, reading frames, deciding outline, writing prose) happens inside Claude's context — there is no Python code that performs those steps.

## Layers

**CLI / Entrypoint Layer:**
- Purpose: Expose stage operations as subprocess commands so Claude Code (or a human shell) can drive them one at a time.
- Location: `agent/tools.py` (primary), `src/cli.py` (legacy v1 pipeline entrypoint).
- Contains: `argparse` subparser definitions, dispatcher dict mapping subcommand name to `cmd_*` handler, `dotenv` loading.
- Depends on: First-party tool modules (`agent/asr_v2.py`, `agent/douyin_downloader.py`, `src/asr.py`, `src/download.py`).
- Used by: Claude Code (via `Bash` tool), users at the shell.

**First-party Tool Layer (`agent/`):**
- Purpose: ¥0 local primitives exposed by `agent/tools.py`.
- Location: `agent/`
- Contains:
  - `agent/tools.py` — the only module with CLI surface; thin handlers that import and call the ones below.
  - `agent/douyin_downloader.py` — Douyin-specific download path (a_bogus signing via vendor crawler), self-contained module that cookies-patches `vendor/douyin_api/crawlers/douyin/web/config.yaml` at runtime.
  - `agent/asr_v2.py` — pure-Python paragraph aggregator over Whisper segments (`aggregate_paragraphs`, `paragraphs_to_dicts`, `get_transcript_window`, `search_transcript`).
  - Legacy v2 modules retained for the optional fallback CLI commands: `agent/pass1_classify.py`, `agent/frame_store.py`, `agent/embed.py`, `agent/frames_v2.py`, `agent/prepare.py`.
- Depends on: `src/` (for `download`, `asr`), `vendor/douyin_api/` (for Douyin crawler), `ffmpeg` on `PATH`.
- Used by: `agent/tools.py` only.

**Legacy Pipeline Layer (`src/`):**
- Purpose: Original v1 fully-automated end-to-end pipeline (download → ASR → keyframes → vision → outline → section → polish), still importable.
- Location: `src/`
- Contains: `src/cli.py`, `src/pipeline.py`, `src/download.py` (yt-dlp wrapper, used by both layers), `src/asr.py` (faster-whisper, used by both layers), `src/frames.py` (1fps + pHash dedup), `src/vision.py`, `src/summarize.py`, `src/budget.py` (budget guard), `src/llm_client.py`.
- Depends on: VectorEngine API key, paid LLM calls, `config/budget_*.yaml`.
- Used by: `src.cli` directly; `agent/tools.py` only reuses the no-cost subset (`src.download`, `src.asr`).

**Vendor Layer (`vendor/`):**
- Purpose: Third-party code mounted as-is, only required because yt-dlp's Douyin extractor cannot generate `a_bogus` signatures.
- Location: `vendor/douyin_api/` (clone of `Evil0ctal/Douyin_TikTok_Download_API`).
- Contains: Async `DouyinWebCrawler` (`vendor/douyin_api/crawlers/douyin/web/web_crawler.py`), config (`vendor/douyin_api/crawlers/douyin/web/config.yaml`).
- Depends on: `httpx==0.27.2` (the version pin exists specifically because vendor uses the deprecated `proxies=` kwarg), Douyin cookies in the patched `config.yaml`.
- Used by: `agent/douyin_downloader.py` only — it injects `vendor/douyin_api` into `sys.path` lazily at first call, then `from crawlers.douyin.web.web_crawler import DouyinWebCrawler`.
- Gitignored: `vendor/` is in `.gitignore`; the repo expects the user to clone it manually per `CLAUDE.md`.

**Artifact Layer (`output/`):**
- Purpose: One sub-directory per video, holding the entire stage history. Self-describing — every file in a slug directory is reproducible from `video.mp4` + `meta.json`.
- Location: `output/<slug>/`
- Slug convention: BVID for Bilibili (e.g. `output/BV132wizyEEB/`), human-readable English/pinyin for Douyin (e.g. `output/douyin_trae_ai/`, `output/godot_brave/`).
- Gitignored: yes (`output/` in `.gitignore`).

## Data Flow

**End-to-end `/summarize-video` flow (Claude Code drives this):**

1. **Phase 1 — Acquire raw data** (Bash subprocess calls):
   - `python -m agent.tools download <url> --out output/<slug>` → URL routed in `agent/tools.py:cmd_download` based on substring `"douyin.com"`. Branches to `agent.douyin_downloader.download_douyin` (cookie-patches vendor config, resolves short-link → `aweme_id`, calls `DouyinWebCrawler.fetch_one_video`, streams `play_addr.url_list[0]` to disk) or `src.download.download` (yt-dlp) for everything else. Both write `meta.json` + `video.mp4` (+ optional `cookies.txt`, `video.info.json`, VTT subtitle).
   - `python -m agent.tools transcribe video.mp4 --out output/<slug>` → `cmd_transcribe` calls `src.asr.extract_audio` (ffmpeg → `audio.wav` 16k mono) then `src.asr.transcribe` (faster-whisper with VAD, hallucination filter). Writes `segs.json` (list of `{start, end, text}`).
   - `python -m agent.tools aggregate segs.json --out paragraphs.json` → `cmd_aggregate` calls `agent.asr_v2.aggregate_paragraphs` to merge fine-grained segments into paragraphs based on silence gap > 1.5s, sentence-ending punctuation, or 30s max duration. Writes `paragraphs.json` (list of `{para_id, start, end, text, seg_indices}`).

2. **Phase 2 — Read & plan inside Claude's context**:
   - Claude `Read`s `meta.json` + `paragraphs.json` and decides what kind of video it is and which time ranges deserve dense framing. **No Python runs in this phase.**

3. **Phase 3 — Targeted frame extraction** (multiple Bash calls with chosen `--fps/--start/--end`):
   - `python -m agent.tools extract_frames video.mp4 --out output/<slug>/frames --fps F --start S --end E` → `cmd_extract_frames` invokes `ffmpeg -ss S -i video -t (E-S) -vf fps=F,scale=854:-1 -q:v 4 frames/seg_<S04d>_%06d.jpg`. The `--start` value is baked into the filename prefix so multiple invocations don't clobber each other and the time origin is recoverable from the filename.

4. **Phase 4 — Multimodal frame reading** (Claude reads JPEGs directly):
   - `Read output/<slug>/frames/seg_NNNN_NNNNNN.jpg` — Claude's vision is the OCR layer. No API.

5. **Phase 5–6 — Outline + write inside Claude's context**: pure cognition, no tooling.

6. **Phase 7 — Persist result**:
   - `Write output/<slug>/summary.md`.

7. **Phase 8 — Optional cleanup**:
   - `python -m agent.tools cleanup_frames output/<slug>/frames --keep f1.jpg f2.jpg ...` → `cmd_cleanup_frames` deletes any `.jpg` whose basename is not in `--keep`.

**State Management:**
- **Filesystem is the single source of truth.** No DB, no in-process state across stages, no message bus. Every stage's output is its complete state.
- **Caching is by file existence**, not by content hash. `meta.json` checks `video_path` exists; `segs.json` short-circuits unless `--force`; `paragraphs.json`/`frames/` are skipped when present per `CLAUDE.md` step 1.3.
- **Cross-stage temporal alignment** is implicit through the `start`/`end` floats stored in `segs.json` and `paragraphs.json`, and through the `seg_<start>_<index>.jpg` frame filenames whose timestamp can be reconstructed as `start + (index - 0.5) / fps` (see `agent/tools.py:122-124`).

## Key Abstractions

**`Segment` (whisper output unit):**
- Purpose: One ASR-recognized utterance with start/end seconds and text.
- Defined in: `src/asr.py:34-38` (`@dataclass`).
- Serialized as: list element in `output/<slug>/segs.json`.

**`Paragraph` (aggregated narrative unit):**
- Purpose: A coherent multi-segment block split on silence/punctuation/max-duration; the unit at which Claude reads narration.
- Defined in: `agent/asr_v2.py:15-22` (`@dataclass` with `para_id`, `start`, `end`, `text`, `seg_indices`).
- Serialized as: list element in `output/<slug>/paragraphs.json`.

**`Frame` (legacy keyframe handle):**
- Purpose: timestamped frame on disk; only used by the legacy `src/` pipeline.
- Defined in: `src/frames.py:19-22` (`@dataclass(timestamp, path)`).
- The current ¥0 workflow does not use this dataclass — frames are addressed purely by their on-disk filename.

**Per-video work directory (`output/<slug>/`):**
- Purpose: A self-contained, resumable workspace for one video.
- The slug is the last URL path segment after stripping query string (`src/cli.py:49`) when using legacy CLI, or chosen freely by the human/Claude when using the agent CLI (Claude tends to use BVID for Bilibili and a descriptive snake_case slug for Douyin).

**CLI subcommand handlers (`cmd_*` functions):**
- Purpose: One function per pipeline stage; each is a thin glue layer that imports its implementation lazily (after `sys.path.insert(0, project_root)`).
- Pattern: All live in `agent/tools.py` (lines 35-188); the dispatcher in `main()` (lines 241-251) is a plain `dict[str, callable]`.

## Entry Points

**`agent.tools` (primary, documented in `CLAUDE.md`):**
- Location: `agent/tools.py:191-255` (`main()`).
- Triggers: `python -m agent.tools <subcommand>` — invoked by Claude Code via `Bash`, or by humans.
- Responsibilities: Parse subcommand args, dispatch to `cmd_*`. Loads `.env` via `python-dotenv` at start.

**`agent.douyin_downloader` (secondary, callable as a script for testing):**
- Location: `agent/douyin_downloader.py:216-225` (`if __name__ == "__main__"`).
- Triggers: `python -m agent.douyin_downloader <url> <out_dir> [cookies_file]`.
- Responsibilities: Standalone Douyin download for debugging without going through `agent.tools download`.

**`src.cli` (legacy, full-pipeline):**
- Location: `src/cli.py:19-66` (`main()`).
- Triggers: `python -m src.cli <url> [--mode test|prod] [--out OUT_DIR]`.
- Responsibilities: Run the entire v1 pipeline `download → ASR → keyframes → vision → outline → section → polish → assemble` driven by `src/pipeline.py:run` with budget controlled by `config/budget_<mode>.yaml`.

**`/summarize-video` (Claude Code skill):**
- Location: Defined as the documented workflow inside `CLAUDE.md` (lines 47-148). There is **no Python file or `.claude/commands/` directory** for this — it is a prompt-level "command" that Claude expands into the eight phases by reading project memory.
- Triggers: User says "总结这个视频" or supplies a Bilibili/Douyin URL.
- Responsibilities: Drive the eight-phase workflow by issuing `Bash` calls to the `agent.tools` CLI and `Read` calls on the resulting artifacts.

## Error Handling

**Strategy:** Fail-fast at the stage boundary; no global try/except; let exceptions bubble out of the subprocess so Claude Code sees stderr in the Bash tool result and decides whether to retry/repair.

**Patterns:**
- `subprocess.run(cmd, check=True, capture_output=True)` for ffmpeg invocations (`agent/tools.py:118`, `src/asr.py:48`) — raises `CalledProcessError` on non-zero exit.
- `RuntimeError` with explicit Chinese message for unrecoverable Douyin cases: missing `aweme_id` (`agent/douyin_downloader.py:165`), empty crawler response (line 171), no extractable video URL (line 176).
- `log.warning(...)` for non-fatal degradation: missing Douyin cookies file (`agent/tools.py:49`), short-link resolution failure (`agent/douyin_downloader.py:79`).
- Whisper hallucination patterns are filtered at the source (`src/asr.py:22-31`, `_HALL_RE`) — bad data is suppressed, not raised.
- Encoding-safe printing: `cmd_download` uses `json.dumps(meta, ensure_ascii=True)` (`agent/tools.py:59`) to avoid GBK terminal explosions on Chinese/emoji titles.

## Cross-Cutting Concerns

**Logging:** Standard library `logging`, configured at the entry point (`agent/tools.py:31` and `src/cli.py:41-44`). Format: `%(levelname)s | %(message)s` for agent layer, full timestamped format for src layer. Module-level loggers via `log = logging.getLogger(__name__)`.

**Configuration:**
- `.env` (gitignored) loaded by `python-dotenv`'s `load_dotenv()` at every CLI entrypoint. Keys: `VE_KEY_CHEAP`, `VE_KEY_QUALITY`, `VE_BASE_URL`, `BILIBILI_SESSDATA`, `DOUYIN_COOKIES_FILE`, `DOUYIN_COOKIES_BROWSER`, `ASR_DEVICE`.
- `.env.example` checked in as a template.
- `config/budget_prod.yaml` and `config/budget_test.yaml` — only consumed by the legacy `src/` pipeline (per-stage USD ceilings, frame caps).
- `www.douyin.com_cookies.txt` (gitignored) — Netscape cookie file at the project root, parsed by `agent/douyin_downloader.py:_cookies_txt_to_header`.

**Authentication:**
- Bilibili: optional `BILIBILI_SESSDATA` cookie injected into a per-video `cookies.txt` for yt-dlp.
- Douyin: required cookie file → header string → patched into `vendor/douyin_api/crawlers/douyin/web/config.yaml` at runtime.
- No per-user account model; this is a single-user tool.

**Validation:** Minimal. Most stages assume the previous stage's artifact is well-formed and will raise (file-not-found, JSON decode error) on broken input.

---

*Architecture analysis: 2026-04-29*
