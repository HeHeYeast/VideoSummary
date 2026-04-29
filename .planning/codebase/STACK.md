# Technology Stack

**Analysis Date:** 2026-04-29

## Languages

**Primary:**
- Python 3.13 - All application code (`agent/`, `src/`, `vendor/douyin_api/`)
  - Note: `src/asr.py` explicitly notes Python 3.13 was the driver for choosing `faster-whisper` over SenseVoice/FunASR (the latter need 3.11)

**Secondary:**
- YAML - Budget configuration (`config/budget_test.yaml`, `config/budget_prod.yaml`) and vendor crawler config (`vendor/douyin_api/crawlers/douyin/web/config.yaml`)
- Markdown - Design docs and final tutorial output (`output/<BV>/summary.md`)

## Runtime

**Environment:**
- CPython 3.13.12 (current local interpreter)
- Type hints use PEP 604 (`X | None`) and `from __future__ import annotations` (e.g. `agent/tools.py:18`, `src/asr.py:11`)

**Package Manager:**
- pip - via `requirements.txt` at project root
- Lockfile: missing (only `requirements.txt` with `>=` pins; one strict pin `httpx==0.27.2` in `requirements.txt:13`)

**External Binaries (must be on PATH):**
- `ffmpeg` - audio extraction (`src/asr.py:42-49`) and frame extraction (`src/frames.py:31-36`, `agent/frames_v2.py:53-59`, `agent/tools.py:107-118`)
- `git` - one-off install of vendor crawler (`CLAUDE.md`: `git clone --depth 1 https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git vendor/douyin_api`)

## Frameworks

**Core (no web framework — CLI tool):**
- `argparse` (stdlib) - CLI parsing in `agent/tools.py:193`, `src/cli.py:21`, `agent/prepare.py:33`
- `dataclasses` (stdlib) - All record/result types (`Segment`, `Paragraph`, `FrameRecord`, `CandidateFrame`, `FrameClassification`)
- `pathlib.Path` (stdlib) - All filesystem ops (no `os.path`)
- `asyncio` (stdlib) - Only used to drive the vendor douyin crawler in `agent/douyin_downloader.py:169`

**ASR (local, primary):**
- `faster-whisper >=1.0.3` - CTranslate2-backed Whisper inference (`src/asr.py:60`)
  - Default model size: `small` (CLI default in `agent/tools.py:204`, `src/cli.py:25`)
  - Other supported sizes: `tiny / base / small / medium / large-v3` (`src/asr.py:55-58`)
  - Device selection via env `ASR_DEVICE` (default `cpu`/`int8`, set to `cuda` for `float16` GPU - `src/asr.py:64-65`)
  - VAD: built-in Silero VAD with `min_silence_duration_ms=500` (`src/asr.py:73`)
  - Anti-hallucination: `condition_on_previous_text=False` plus regex blocklist in `src/asr.py:22-31`

**Vision / multi-modal:**
- Primary path: NONE — Claude Code reads JPEG frames directly via `Read output/<BV>/frames/*.jpg` (`CLAUDE.md` "帧理解不需要 API")
- Fallback path: VectorEngine API via `openai>=1.50.0` SDK (`src/llm_client.py:17`) using OpenAI-compatible chat-completions with base64 image_url payload (`src/llm_client.py:93-108`)
- Optional CLIP semantic search: `open_clip_torch` (NOT in `requirements.txt`; lazy-imported with graceful fallback in `agent/embed.py:23-30`). Model: `ViT-B-32 / laion2b_s34b_b79k`

**Video download:**
- `yt-dlp >=2024.10.0` - B站 / YouTube / generic path (`src/download.py:9`)
  - Format: `bv*[height<=720]+ba/b[height<=720]/best`, writes auto+manual subs `zh-CN, zh, en` in `vtt`
- Vendor crawler `vendor/douyin_api/` - Evil0ctal/Douyin_TikTok_Download_API (Apache-2.0) used for 抖音 only, because yt-dlp's douyin extractor lacks `a_bogus` signing (`agent/douyin_downloader.py:1-10`)

**Image processing:**
- `Pillow >=10.0.0` - JPEG IO (`agent/frames_v2.py:18`, `agent/embed.py:71`)
- `imagehash >=4.3.1` - perceptual hash (pHash) for novelty / stability scoring (`agent/frames_v2.py:17`, `src/frames.py:13`)
- `numpy` - vectors for CLIP embeddings (`agent/embed.py:13`); pulled in by `vendor/douyin_api/requirements.txt:17`

**LLM-adjacent (only used by fallback paths, not the ¥0 main flow):**
- `openai >=1.50.0` - OpenAI Python SDK pointed at VectorEngine base URL (`src/llm_client.py:50-52`)
- `tiktoken >=0.7.0` - token estimation for budget pre-checks via `cl100k_base` encoder (`src/llm_client.py:24`)

**Testing:**
- Not detected. No `pytest`/`unittest` test suite exists. The only test file is `agent/smoke_test_fc.py` (smoke script, not a framework-driven test).

**Build/Dev:**
- No build system. No `pyproject.toml`, no `setup.py`, no `setup.cfg`. Project is run as `python -m <module>` directly from source.

## Key Dependencies

**Critical (declared in `requirements.txt`):**
- `openai >=1.50.0` - VectorEngine fallback client
- `yt-dlp >=2024.10.0` - B站 download
- `faster-whisper >=1.0.3` - local ASR (the ¥0 backbone)
- `imagehash >=4.3.1` - pHash for frame novelty/stability
- `Pillow >=10.0.0` - image IO
- `pyyaml >=6.0` - budget config + vendor crawler config
- `python-dotenv >=1.0.0` - loads `.env` into `os.environ` (called in every entrypoint: `agent/tools.py:192`, `src/cli.py:20`, `agent/prepare.py:31`)
- `tiktoken >=0.7.0` - token counting for budget guard
- `tqdm >=4.66.0` - progress bars

**抖音 vendor support (declared in `requirements.txt:11-19`):**
- `httpx==0.27.2` - **strict pin** because `vendor/douyin_api` uses the deprecated `proxies=` kwarg removed in httpx 0.28+
- `gmssl >=3.2.0` - Chinese national crypto used by `a_bogus` signing
- `qrcode >=7.4` - vendor login flow (unused in our code path)
- `browser_cookie3 >=0.19` - vendor cookie loader
- `importlib_resources >=6.4` - vendor resource loading
- `pyfiglet >=1.0` - vendor banner
- `user-agents >=2.2` - vendor UA parsing

**Optional (not in `requirements.txt`):**
- `open_clip_torch` + `torch` - CLIP embeddings; lazy-imported in `agent/embed.py:24-26`. The `prepare.py --skip-clip` flag exists for when these are missing.

**Vendored, not pip-installed:**
- `vendor/douyin_api/` - cloned from `https://github.com/Evil0ctal/Douyin_TikTok_Download_API` (Apache-2.0). Contains its own `requirements.txt` with `fastapi 0.110.2`, `pydantic 2.7.0`, `pycryptodomex 3.20.0`, `tornado 6.4`, `uvicorn 0.29.0`, `pywebio 1.8.3` — **none of these are needed** by our code path. We only import `crawlers.douyin.web.web_crawler.DouyinWebCrawler` (`agent/douyin_downloader.py:90`).

## Configuration

**Environment loading:**
- `.env` at project root, loaded via `dotenv.load_dotenv()` in every CLI entrypoint
- Template: `.env.example` (5 lines, lists `VE_BASE_URL`, `VE_KEY_CHEAP`, `VE_KEY_QUALITY`, `BILIBILI_SESSDATA`)

**Environment variables consumed (from code grep):**
- `VE_BASE_URL` - default `https://api.vectorengine.ai/v1` (`src/llm_client.py:112`)
- `VE_KEY_CHEAP` - VectorEngine cheap-tier API key; required only for fallback `classify_frame`/`ocr_frame` (`src/llm_client.py:113-116`)
- `VE_KEY_QUALITY` - quality-tier key; falls back to `VE_KEY_CHEAP` if unset (`src/llm_client.py:114`)
- `BILIBILI_SESSDATA` - optional B站 session cookie for high-res / member videos (`src/download.py:25-33`)
- `DOUYIN_COOKIES_FILE` - path to Netscape cookies.txt for 抖音; default `www.douyin.com_cookies.txt` (`agent/tools.py:46-47`, `src/download.py:52`)
- `DOUYIN_COOKIES_BROWSER` - alternative cookie source (browser name like `chrome`); default `chrome` (`src/download.py:57`)
- `ASR_DEVICE` - `cpu` (default) or `cuda` for faster-whisper (`src/asr.py:64`)

**Cookie files (existence noted, contents NOT read):**
- `www.douyin.com_cookies.txt` at project root — Netscape-format cookies exported via "Get cookies.txt LOCALLY" Chrome extension. Required for 抖音 download. Cookies expire every few days per `CLAUDE.md`.
- `.env` and `.env.example` exist at project root.

**Budget config (YAML):**
- `config/budget_test.yaml` - `total_budget_cny: 0.40`, `frame_cap: 15`, `chapter_cap: 3`
- `config/budget_prod.yaml` - `total_budget_cny: 0.80`, `frame_cap: 30`, `chapter_cap: 8`
- Both have per-stage `stage_limits` (USD, internally converted from CNY at `CNY_PER_USD = 7.2` in `src/budget.py:23`) and `call_limits` keyed by stage (`type_detect/vision/ocr/anchor/outline/section/polish/critique/revise/map/reduce`)

**Vendor crawler config:**
- `vendor/douyin_api/crawlers/douyin/web/config.yaml` - has its `Cookie:` line patched at runtime by `agent/douyin_downloader.py:46-61` from the project-root cookies file

## Platform Requirements

**Development:**
- Python 3.13 interpreter
- ffmpeg on PATH
- Disk space: `output/<BV>/` per video holds `video.mp4` + `audio.wav` + 30-50 frame jpegs + JSON sidecars (typically 50-200 MB / video)
- For GPU ASR: CUDA + cuBLAS + cuDNN (Windows users default to CPU-`int8` because Windows commonly lacks cuDNN — explicitly noted in `src/asr.py:62-64`)
- For optional semantic search: `pip install open_clip_torch torch` (downloads `ViT-B-32` weights ~600 MB on first call)

**Production:**
- Same as development. There is no deployment target — this is a local CLI driven by Claude Code on the developer's workstation. No Docker, no CI, no hosting platform.

**Operating system notes:**
- Windows is a first-class target: `agent/tools.py:59` deliberately uses `ensure_ascii=True` for `json.dumps` to avoid emoji breaking GBK terminals; `CLAUDE.md` setup mentions `pip install` and Windows ffmpeg builds.

---

*Stack analysis: 2026-04-29*
