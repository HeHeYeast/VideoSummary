# Concerns

Technical debt, fragile areas, security risks, and gaps in the current `videoSummary` codebase. Generated 2026-04-29 from a structured codebase audit (focus: concerns).

---

## 1. Tech Debt

### 1.1 Three parallel frame-extraction implementations
- `src/frames.py` (88 lines) — v1: 1 fps + pHash dedupe + hard cap
- `agent/frames_v2.py` (264 lines) — v2: candidate + info-score + top-K
- `agent/tools.py:102-126` — third inline `ffmpeg` invocation used by the documented `¥0` workflow
- Three filename conventions (`frame_%06d.jpg` vs `seg_{start:04d}_%06d.jpg`), three timestamp-from-filename conventions, three `ffmpeg` argument styles. Future fixes must be made in all three places.

### 1.2 `agent/prepare.py` is largely orphaned
- `agent/prepare.py` (217 lines) implements a full v2 pipeline (Stages 1-6 with Pass1 classification + CLIP), but `CLAUDE.md` documents only the simpler `agent/tools.py` workflow.
- Pulls in ~700 LOC of orphaned code: `agent/pass1_classify.py` (122), `agent/embed.py` (149), `agent/frame_store.py` (190), `agent/prepare.py` (217).
- Recent commit `0357d0e 简化工具集: 去掉 VE API 依赖` suggests this layer was deliberately bypassed but not removed.

### 1.3 Two divergent download paths with different `meta.json` schemas
- B站 → `src/download.py` (yt-dlp) — basic schema
- 抖音 → `agent/douyin_downloader.py` — adds `aweme_id`, `source: "douyin"`
- Dispatch is a substring check at `agent/tools.py:42` (`"douyin.com" in url.lower()`). New hosts (TikTok, douyin.cn) require code edits.
- `src/download.py:51-59` still has dead 抖音 handling code, unreachable from the dispatcher.

### 1.4 Console-encoding workaround leaks into business logic
- `agent/tools.py:58-59` uses `ensure_ascii=True` "避免打印含 emoji 的 title 炸 gbk 终端".
- `agent/smoke_test_fc.py:87-88` rewraps `sys.stdout` with a UTF-8 encoder.
- Inconsistent — not all commands handle GBK terminals the same way.

### 1.5 `sys.path.insert` hacks throughout
- `agent/tools.py:37,64,91,152,172`, `agent/douyin_downloader.py:87`, `agent/prepare.py:51`.
- `agent/douyin_downloader.py:87` permanently injects `vendor/douyin_api/` into `sys.path`, polluting the namespace with `crawlers`, `app` packages.
- Project lacks `pyproject.toml` / proper package layout.

---

## 2. Known Bugs / Fragility

### 2.1 抖音 cookies expire every 2-7 days (documented)
- Code: `agent/douyin_downloader.py:128-213`. Cookie file: `www.douyin.com_cookies.txt`.
- Documented in `CLAUDE.md:24-29`. Manual re-export via Chrome plugin only. No expiry detection — failure surfaces as `RuntimeError("未能从响应中提取视频 URL")`.
- Caller can't distinguish "cookies stale" from "video deleted" from "douyin schema changed". No typed error.

### 2.2 Vendor `config.yaml` is mutated in place every download
- `agent/douyin_downloader.py:46-61` (`_patch_config_cookie`) rewrites `vendor/douyin_api/crawlers/douyin/web/config.yaml` via regex on each call.
- Race condition on concurrent calls. Vendor pulls / re-clones overwrite the patched cookies. If `vendor/` is ever un-`.gitignore`d (currently line 11), session cookies leak.

### 2.3 `yt-dlp` 抖音 path is dead but still present
- `src/download.py:51-59` checks `"douyin.com" in url.lower()`, sets `cookiefile` / `cookiesfrombrowser`, but the dispatcher in `agent/tools.py:42` routes 抖音 URLs away before this code runs.
- Anyone calling `src.download.download` directly (e.g. from `agent/prepare.py:80`) hits the broken path.

### 2.4 `_extract_aweme_id` URL parsing is brittle
- `agent/douyin_downloader.py:64-80` — three hardcoded regex forms.
- Variants like `iesdouyin.com/share/video/`, mobile-app share links with hash fragments, or new short-URL hosts return `None`.

### 2.5 `HALLUCINATION_PATTERNS` blocklist (`src/asr.py:22-30`)
- 7 hardcoded Chinese Whisper hallucinations. False-positive risk: legitimate video closings ("感谢观看") get dropped.
- New hallucinations from future Whisper models won't be caught.

### 2.6 Paragraph thresholds are tuning-locked
- `agent/asr_v2.py:28-32` — `gap_threshold=1.5`, `max_para_duration=30.0`, hidden `gap > 0.8` sentence-end heuristic.
- Tuned for tutorial pacing. Lectures or fast-paced demos produce poor segmentation.

### 2.7 Voice-anchor regex misses obvious cases
- `agent/frames_v2.py:36-44` — 19 hardcoded patterns (10 EN + 9 ZH).
- Misses common phrases like "看一下", "如下图", "你看", "这边". No tests.

---

## 3. Vendor / Supply Chain

### 3.1 `vendor/douyin_api/` is shallow clone, no version pin
- `CLAUDE.md:19` instructs `git clone --depth 1 https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git vendor/douyin_api`.
- Only one commit retained (`42784ff docs: Added README.en.md translation`). No commit pin in this repo.
- Different contributors get different upstream HEADs.
- No supply-chain audit. Vendor bundles `pycryptodomex`, `browser-cookie3`, custom `a_bogus`/`x_bogus` signature implementations at `vendor/douyin_api/crawlers/douyin/web/abogus.py` and `xbogus.py` — anti-bot evasion code that scrapes 抖音.
- Vendor is `.gitignore`d (line 11), so the repo doesn't even record which commit was used. Recovery from breakage requires luck.
- Over-vendored: only ~3 files in `crawlers/douyin/web/` are used; rest of ~30 MB project (FastAPI app, Docker, Procfile) is dead weight.
- License compliance: `vendor/douyin_api/LICENSE` not propagated.

### 3.2 `httpx==0.27.2` pin is a ticking clock
- `requirements.txt:12-13`: comment says "vendor/douyin_api 用了被弃用的 proxies= 参数".
- Vendor's own `vendor/douyin_api/requirements.txt` pins `httpx==0.27.0`.
- `httpx>=0.28` removed `proxies=`. Any future dependency (e.g. `openai` SDK) requiring `>=0.28` blocks `pip install`.

---

## 4. Security / Secrets

### 4.1 Secrets are correctly `.gitignore`d (verified)
- `git check-ignore` confirms `.env` and `www.douyin.com_cookies.txt` are ignored.
- `.gitignore`: line 1 `.env`, line 10 `*cookies*.txt`, line 11 `vendor/`.

### 4.2 Cookie ignore pattern has gaps
- `*cookies*.txt` (line 10) doesn't catch `.json` cookie exports or future browser-encrypted dumps.
- `src/download.py:28-33` writes a runtime `cookies.txt` into `out_dir/` (transitively safe because `output/` is ignored at line 9, but a future change to that ignore could expose them).

### 4.3 Cookies persisted into vendor config
- `agent/douyin_downloader.py:46-61` writes the cookie header into `vendor/douyin_api/crawlers/douyin/web/config.yaml`. Safe only because `vendor/` is `.gitignore`d. Any change to track vendor (recommended for supply-chain hygiene) leaks cookies.

### 4.4 `.env.example` is stale and incomplete
- `.env.example` (12 lines) documents `VE_BASE_URL`, `VE_KEY_CHEAP`, `VE_KEY_QUALITY`, `BILIBILI_SESSDATA`.
- Missing: `DOUYIN_COOKIES_FILE` (`agent/tools.py:46`), `DOUYIN_COOKIES_BROWSER` (`src/download.py:57`), `ASR_DEVICE` (`src/asr.py:64`).
- New contributors lack a source of truth.

---

## 5. Performance

### 5.1 ASR is CPU-only by default
- `src/asr.py:62-67` — `device="cpu"`, `compute_type="int8"`.
- 10-min video on faster-whisper `small` CPU = 15-30 min wall time.
- GPU path documented as broken on Windows ("缺 cuBLAS/cuDNN 时 CUDA 推理会炸"); no setup guide.
- Default `--whisper small` is conservative; users will retry with `medium` and re-pay full ASR cost (cache key doesn't include model size).

### 5.2 Whisper model reloaded every call
- `src/asr.py:60-67` instantiates `WhisperModel(...)` fresh on each invocation. Batch processing pays the load cost N times.

### 5.3 Frame extraction has no caching
- `agent/tools.py:cmd_extract_frames` (102-126) re-runs `ffmpeg` every call. No `(start, end, fps)` skip-if-cached logic.

### 5.4 Cache validation is "file exists" only
- `agent/tools.py:74-86` skips ASR if `segs.json` exists; never validates `model_size`, audio mtime, or whisper version.
- `cmd_aggregate` has no cache logic at all.

### 5.5 No frame-budget enforcement in active workflow
- `BudgetGuard.frame_cap` (default 50, `src/budget.py:71`) only used by orphaned `agent/prepare.py`.
- `agent/tools.py:cmd_extract_frames` has no cap. `fps=10` on a 10-min video → 6000 frames.

---

## 6. Reliability — Subprocess Wrappers

### 6.1 ffmpeg dependency is implicit and silent
- `agent/tools.py:107-118`, `agent/frames_v2.py:54-59`, `src/asr.py:43-48`, `src/frames.py:31-36`.
- All use `subprocess.run(["ffmpeg", ...], check=True, capture_output=True)`. No preflight check.
- Missing `ffmpeg` → `FileNotFoundError: [WinError 2]` with no install guidance.
- `CLAUDE.md` doesn't mention `ffmpeg` as a system requirement.

### 6.2 `capture_output=True` swallows ffmpeg stderr
- Same files. Failure raises `CalledProcessError` but stderr is buried in `e.stderr`. Default exception print loses it.

### 6.3 No retries / partial-download protection
- `agent/douyin_downloader.py:183-198` streams video in a single `httpx` connection with `timeout=120`. Network blip → full re-download.
- Partial `video.mp4` still gets `meta.json` written → false cache hit on re-run.

---

## 7. Data Loss Risk

### 7.1 `cleanup_frames` is irreversible
- `agent/tools.py:138-147` deletes every `.jpg` not in `--keep`. No dry-run, no trash, no confirmation.
- `args.keep` defaults to `[]` (`agent/tools.py:224`) — running `cleanup_frames <dir>` with no `--keep` deletes ALL frames.
- If Claude misnames a kept frame, the original is gone (re-extraction is slow and may produce different filenames if `--start` differs).

### 7.2 Other in-pipeline deletes
- `agent/frames_v2.py:232-238` (`cleanup_unselected`)
- `src/frames.py:54-58` (`dedupe_phash`)
- `src/frames.py:70-77` (`cap_frames`)
- All use `Path(f.path).unlink(missing_ok=True)`. Internal to single runs, but no recovery path.

---

## 8. Cross-Platform

### 8.1 Path handling is correct
- All 32 occurrences of `pathlib`/`Path()` across `agent/*.py` and `src/*.py` use `pathlib.Path`. No string concatenation.

### 8.2 Windows-specific assumptions exist
- `ASR_DEVICE=cpu` default with a Windows-specific comment (`src/asr.py:64-65`); Linux/Mac CUDA users silently default to CPU.
- `ensure_ascii=True` JSON workaround (`agent/tools.py:59`) for Windows GBK terminals.
- `ffmpeg` PATH lookup; common Windows installs (`C:\ffmpeg\bin\`) often not on PATH.

### 8.3 No CI matrix
- No `.github/workflows/`, no `.gitlab-ci.yml`. Cross-platform behavior untested.

---

## 9. Test Coverage

### 9.1 Zero unit/integration tests
- No `test_*.py` or `*_test.py` files anywhere except in `vendor/`.
- The only "test" is `agent/smoke_test_fc.py` (111 lines), a one-shot probe of vector-engine API function-calling.
- Each commit "tested" by manual end-to-end runs (commit `f03ed73 ¥0 流程验证通过: 307 行教程, 17 帧`).
- High-value targets for unit tests (pure functions): `agent/asr_v2.py:aggregate_paragraphs`, `agent/frames_v2.py:select_top_k`, `agent/pass1_classify.py:_parse_classification`, `agent/douyin_downloader.py:_extract_aweme_id`, `agent/douyin_downloader.py:_cookies_txt_to_header`.

### 9.2 No fixture data
- No checked-in sample `segs.json`, no synthetic video. New contributors can't run anything end-to-end without first downloading a real video.

---

## 10. Cost Claim — "¥0"

### 10.1 "¥0 全流程" is conditional, not absolute
- `CLAUDE.md:1-4` claims `全流程 **¥0 成本**（Claude Max 计划）`.
- True only for Anthropic Max-plan subscribers. API-billing / Pro / Free users pay non-trivially: 30-50 frame Reads × ~1500-3000 image tokens each + paragraph reasoning ≈ $0.50-$2 per 10-min video on the API tier.
- `COST_CONTROL.md` discusses budgets but the active workflow bypasses `BudgetGuard` entirely.
- Recommendation: reword as "¥0 marginal cost on Claude Max" and add an API-tier cost estimate.

### 10.2 No accounting of compute costs
- Local faster-whisper consumes CPU-hours and 4-8 GB RAM. `ffmpeg` consumes CPU. Disk consumes 50-500 MB per video. Not "free" in the absolute sense.

---

## 11. Storage / Output Growth

### 11.1 `output/` has no eviction strategy (verified live)
- 58 folders totaling **4.5 GB** currently. Largest: `BV1inBoBSE23` (1.7 GB), `BV1x31TYUEbc` (1.6 GB).
- Each folder retains: `video.mp4` (50-500 MB), `audio.wav` (uncompressed PCM ~110 MB per 10 min), `frames/*.jpg`, JSON files.
- `output/` is `.gitignore`d (line 9). No `cleanup` CLI command. No documented retention policy.

### 11.2 `audio.wav` is uncompressed PCM and never deleted
- `src/asr.py:43-48` extracts to `pcm_s16le` 16 kHz mono ≈ 32 KB/s ≈ 115 MB per audio-hour.
- Once `segs.json` is written, `audio.wav` is dead weight.
- Fix: auto-delete after successful transcribe; or use `flac`/`opus` codec (5-10× smaller, same Whisper quality).

### 11.3 `video.mp4` retained after `summary.md` is generated
- No cleanup of source video after pipeline completes.

---

## 12. Logging / Observability

### 12.1 Inconsistent logging config
- `agent/tools.py:31`, `agent/prepare.py:44-47`, and `agent/douyin_downloader.py:23,219` each set their own logging format.
- Output style varies per command.

### 12.2 No progress reporting for long-running ASR
- `src/asr.py:79-86` iterates `segments_iter` without `tqdm`. 30-min CPU transcription appears hung.

### 12.3 No structured exit codes
- Failures from `subprocess.run(check=True)` propagate as Python tracebacks. Bad for shell scripting.

### 12.4 No batch processing entrypoint
- `MEMORY.md` references "6 条待总结视频队列" but no `agent/batch.py`. All processing is interactive one-at-a-time.

---

## 13. Dependencies at Risk

### 13.1 `yt-dlp>=2024.10.0` floor doesn't enforce updates
- `requirements.txt:2`. B站 changes its API every few months; old yt-dlp breaks silently.

### 13.2 `faster-whisper` Python/CUDA coupling
- `requirements.txt:3`, `src/asr.py:1-9`. Tight binding to PyTorch versions.

### 13.3 `open_clip_torch` is optional but undeclared
- `agent/embed.py:23-30` does graceful import. Not in `requirements.txt`. `agent/prepare.py` Stage 6 silently no-ops if missing.

---

## Reference — Key Files

| Path | Lines | Status |
|---|---|---|
| `.gitignore` | 11 | active |
| `.env.example` | 12 | stale |
| `CLAUDE.md` | 157 | active |
| `requirements.txt` | 20 | `httpx` pinned at L12-13 |
| `agent/tools.py` | 255 | active CLI |
| `agent/douyin_downloader.py` | 225 | active |
| `agent/asr_v2.py` | 154 | active |
| `agent/frames_v2.py` | 264 | orphaned |
| `agent/prepare.py` | 217 | orphaned |
| `agent/pass1_classify.py` | 122 | orphaned |
| `agent/frame_store.py` | 190 | orphaned |
| `agent/embed.py` | 149 | orphaned |
| `agent/smoke_test_fc.py` | 111 | sole "test" |
| `src/download.py` | 88 | active |
| `src/asr.py` | 121 | active |
| `src/frames.py` | 88 | v1 (alongside v2) |
| `src/budget.py` | 154 | mostly unused in active flow |
| `vendor/douyin_api/` | — | shallow clone, unpinned |
| `vendor/douyin_api/crawlers/douyin/web/config.yaml` | — | mutated in place |
| `www.douyin.com_cookies.txt` | — | gitignored, expires every few days |
