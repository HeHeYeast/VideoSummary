# External Integrations

**Analysis Date:** 2026-04-29

## APIs & External Services

**Video sources (download):**

- **B站 (bilibili.com)** - Primary supported source
  - Path: `src/download.py:14` (`yt-dlp` wrapper)
  - SDK/Client: `yt-dlp >=2024.10.0`
  - Format: `bv*[height<=720]+ba/b[height<=720]/best`, prefers VTT subtitles in `zh-CN, zh, en` (`src/download.py:35-45`)
  - Auth: optional `BILIBILI_SESSDATA` env var written to a temp Netscape `cookies.txt` for HD/member videos (`src/download.py:25-33`)
  - Output: `video.mp4` + `meta.json` (+ optional `video.<lang>.vtt` and yt-dlp `.info.json`)

- **抖音 (douyin.com)** - Custom-routed because yt-dlp's douyin extractor is broken
  - Path: `agent/douyin_downloader.py` (orchestrator) → `vendor/douyin_api/crawlers/douyin/web/web_crawler.py:DouyinWebCrawler` (vendor crawler)
  - Triggered when URL contains `douyin.com` (router in `agent/tools.py:42-52`)
  - SDK/Client: vendored Evil0ctal/Douyin_TikTok_Download_API (Apache-2.0), cloned via `git clone --depth 1 https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git vendor/douyin_api` (one-off, see `CLAUDE.md`)
  - Why custom: the vendor crawler implements the **`a_bogus` request signature** (Chinese national crypto in `vendor/douyin_api/crawlers/douyin/web/abogus.py`); yt-dlp does not. `agent/douyin_downloader.py:1-10` and `CLAUDE.md` both call this out as long-term broken in yt-dlp.
  - Auth: cookies from `www.douyin.com_cookies.txt` (Netscape format) parsed by `_cookies_txt_to_header()` and patched into the vendor's `config.yaml` at runtime (`agent/douyin_downloader.py:30-61`)
  - Cookie lifecycle: expire every few days; user re-exports via "Get cookies.txt LOCALLY" Chrome extension (`CLAUDE.md` 抖音支持 section)
  - URL handling: short links `v.douyin.com/xxx` and `iesdouyin.com/xxx` are resolved via `httpx.get(..., follow_redirects=True)` to extract the numeric `aweme_id` (`agent/douyin_downloader.py:64-80`)
  - Internal API call: `crawler.fetch_one_video(aweme_id=...)` returns a JSON detail blob; we pick `aweme_detail.video.play_addr.url_list[0]` as the no-watermark stream URL (`agent/douyin_downloader.py:96-125`)
  - Direct download: `httpx.stream("GET", video_url, ...)` with `Referer: https://www.douyin.com/` and a desktop Chrome UA (`agent/douyin_downloader.py:183-198`)

- **YouTube / generic** - Not the primary use case but reachable: any non-`douyin.com` URL falls through to yt-dlp (`agent/tools.py:53-56`). No special config.

**LLM / Vision (fallback only — not used in the main ¥0 flow):**

- **VectorEngine** (https://api.vectorengine.ai/v1) - OpenAI-compatible aggregator/proxy
  - SDK/Client: `openai >=1.50.0` (`src/llm_client.py:17`), constructed with custom `base_url` and `max_retries=1`
  - Two key tiers ("groups"): `cheap` and `quality`, mapped to separate `OpenAI` clients (`src/llm_client.py:50-55`)
  - Endpoints used: `chat.completions.create` only (text + multi-modal both go through chat-completions; images sent as base64 `data:image/jpeg;base64,...` URLs in `src/llm_client.py:96-104`)
  - Auth: `VE_KEY_CHEAP` / `VE_KEY_QUALITY` env vars (`src/llm_client.py:113-114`)
  - Models referenced (price table in `src/budget.py:28-42`):
    - Text: `gpt-4o-mini`, `glm-4.5-air`, `glm-4.6`, `deepseek-v3.2`, `kimi-k2`, `deepseek-v3.1`, `gemini-2.5-pro`
    - Vision: `gemini-2.5-flash`, `gemini-3-flash-preview-nothinking`, `qwen3-vl-plus` (default), `qwen-vl-max`
  - Quirks: some models (GLM/Qwen "thinking mode") return blank `content` and put text in `reasoning_content` or `model_extra`; handled in `src/llm_client.py:81-87`
  - Status: this entire integration is **fallback only**. The CLAUDE.md workflow has Claude Code read JPEG frames natively (multi-modal) and skip the API. The code paths `cmd_classify_frame` / `cmd_ocr_frame` in `agent/tools.py:150-188` exist as escape hatches.

## Data Storage

**Databases:**
- None. No SQL, no NoSQL, no ORM.

**File Storage:**
- Local filesystem only. Per-video work directory: `output/<BV-id-or-aweme-id>/`
- Files written per video:
  - `video.mp4` - downloaded source
  - `meta.json` - title, uploader, duration, url, video_path, subtitle_path, source (`src/download.py:77-86`, `agent/douyin_downloader.py:201-211`)
  - `audio.wav` - 16 kHz mono PCM extracted by ffmpeg (`src/asr.py:42-49`)
  - `segs.json` - raw faster-whisper segments
  - `paragraphs.json` - aggregated paragraphs (`agent/asr_v2.py:101`)
  - `frames/seg_<start>_<seq>.jpg` - extracted frames at 854px wide, q:v 4 (`agent/tools.py:114-118`)
  - `frame_store.json` - structured frame records (v2 path, `agent/frame_store.py:96-104`)
  - `embeddings.npy` - optional CLIP embeddings (`agent/embed.py:96-99`)
  - `summary.md` - final tutorial output
- Existing video work-dirs in `output/`: `BV11FckzjEkq`, `BV11JQBByE13`, `BV132wizyEEB`, `BV142FKzLE2j`, `BV15S9FBtEFm`, `BV17WQuBJEzZ`, `BV1bFk7BvEuL`, `BV1C9QCBdE1U`, `BV1dQPezJEmG`, `BV1dUDLBaEeb`, ...

**Caching:**
- File-existence caching only. Every stage (`download`, `transcribe`, `aggregate`, `prepare`) checks for the output JSON before regenerating; `--force` flag on `transcribe` bypasses (`agent/tools.py:75-77`).

**Model weights cache:**
- `faster-whisper` downloads CTranslate2 Whisper weights to `~/.cache/huggingface/hub` (HF default) on first use of a model size.
- `open_clip` (when used) downloads `ViT-B-32 / laion2b_s34b_b79k` weights similarly on first call (`agent/embed.py:42-46`).

## Authentication & Identity

**Outbound auth:**
- B站: optional `SESSDATA` cookie (`BILIBILI_SESSDATA` env)
- 抖音: required Netscape cookies file at `www.douyin.com_cookies.txt`
- VectorEngine: bearer-style API keys via `VE_KEY_CHEAP` / `VE_KEY_QUALITY`

**Inbound auth:** Not applicable — this project exposes no server.

## Monitoring & Observability

**Error Tracking:**
- None. No Sentry, no rollbar, no telemetry.

**Logs:**
- Python `logging` module, configured at each entrypoint with `logging.basicConfig(level=logging.INFO, ...)` (e.g. `agent/tools.py:31`, `src/cli.py:42-44`)
- Log destination: stderr only (no file handlers configured)
- Per-video budget report appended to `output/<BV>/budget_report.txt` by `agent/prepare.py:194` when the v2 paid pipeline runs

**Metrics:**
- Custom in-process: `src/budget.py:BudgetGuard` accumulates per-stage USD spend, call counts, and produces `report()` text. Not exported.

## CI/CD & Deployment

**Hosting:**
- None. This is a local CLI tool driven interactively from Claude Code.

**CI Pipeline:**
- None. No `.github/workflows/`, no `.gitlab-ci.yml`, no Jenkins/CircleCI config detected.

## Environment Configuration

**Required env vars:**
- For ¥0 main flow (Claude Code multi-modal): NONE required. `.env` may be entirely empty.
- For 抖音 downloads: presence of `www.douyin.com_cookies.txt` at project root (or `DOUYIN_COOKIES_FILE` pointing elsewhere)
- For fallback API path (`classify_frame`, `ocr_frame`): `VE_KEY_CHEAP` (and optionally `VE_KEY_QUALITY`); `make_client()` raises `RuntimeError("环境变量 VE_KEY_CHEAP 未设置")` if missing (`src/llm_client.py:115-116`)

**Optional env vars:**
- `VE_BASE_URL` - override VectorEngine endpoint (default `https://api.vectorengine.ai/v1`)
- `BILIBILI_SESSDATA` - HD / member videos
- `DOUYIN_COOKIES_FILE` - non-default path to cookies.txt
- `DOUYIN_COOKIES_BROWSER` - browser name for yt-dlp `cookiesfrombrowser` fallback (default `chrome`)
- `ASR_DEVICE` - `cpu` (default) or `cuda` for faster-whisper

**Secrets location:**
- `.env` at project root (gitignored implicitly via convention; the file exists on this machine but its contents are not read by this analysis)
- `www.douyin.com_cookies.txt` at project root (likely sensitive — contains live session cookies; not read by this analysis)
- `.env.example` at project root is the public template

## Webhooks & Callbacks

**Incoming:**
- None. No HTTP server is started by any entrypoint.

**Outgoing:**
- None. All external calls are synchronous request/response from CLI invocations.

## Integration Map (call sites)

**Where `yt-dlp` is invoked:**
- `src/download.py:9` (import), `src/download.py:61` (`yt_dlp.YoutubeDL(opts).extract_info(url, download=True)`)
- Routed from `agent/tools.py:53-56` (`from src.download import download`) for B站 / generic URLs

**Where vendor 抖音 crawler is invoked:**
- `agent/douyin_downloader.py:90` (`from crawlers.douyin.web.web_crawler import DouyinWebCrawler` — done after `sys.path.insert(0, str(_VENDOR))`)
- `agent/douyin_downloader.py:92-93` (`crawler.fetch_one_video(aweme_id=...)`)
- Routed from `agent/tools.py:42-52` (`from agent.douyin_downloader import download_douyin`)

**Where faster-whisper is loaded:**
- `src/asr.py:60` (`from faster_whisper import WhisperModel`) — lazy import inside `transcribe()` so the dependency is paid for only when ASR actually runs
- Called by `agent/tools.py:65` (CLI `transcribe` subcommand) and `src/pipeline.py` / `agent/prepare.py` (legacy pipelines)

**Where VectorEngine OpenAI client is built:**
- `src/llm_client.py:111-117` (`make_client(budget)`)
- Only called from fallback CLI paths `agent/tools.py:151-167` (`classify_frame`) and `agent/tools.py:170-188` (`ocr_frame`), plus the legacy v1/v2 pipelines (`src/pipeline.py`, `agent/prepare.py`).

**Where CLIP is loaded (optional):**
- `agent/embed.py:42-49` (`open_clip.create_model_and_transforms("ViT-B-32", pretrained="laion2b_s34b_b79k")`)
- Behind a `try/except ImportError` guard so `open_clip_torch` being missing degrades to no-op (`agent/embed.py:23-30`).

---

*Integration audit: 2026-04-29*
