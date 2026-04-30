# Stack Research

**Domain:** Local-first video-to-tutorial pipeline (brownfield expansion of an existing ¥0 stack)
**Researched:** 2026-04-30
**Confidence:** HIGH for the core additions; MEDIUM for the YouTube-from-China path (rapidly shifting); LOW only where explicitly flagged.

## Scope of This Research

The existing stack (`yt-dlp`, `vendor douyin_api`, `faster-whisper`, `ffmpeg`, `Pillow`, `imagehash`, Claude Code as multimodal layer) is **stable and not being replaced**. All recommendations below are about plugging the six concrete milestone gaps:

1. YouTube + generic yt-dlp platform support (China network reality)
2. Local mp4 file path input
3. Frame-extraction automation (transcript → fps schedule)
4. Adaptive teaching output (no new lib — pure prompting; out of stack scope)
5. New video types: software UI demos + podcasts/interviews
6. Mid-artifact failure resume
7. Multi-agent parallelism (Nice-to-have)

Rule: anything already in `.planning/codebase/STACK.md` that the milestone reuses is marked **"existing — keep"** and not re-justified.

## Recommended Stack (Additions Only)

### Core Additions

| Technology | Version | Purpose | Why Recommended (in this project) | Confidence |
|------------|---------|---------|-----------------------------------|------------|
| `yt-dlp` | `>=2026.03.17`, prefer pinning to a known-good monthly release | YouTube + generic platform support (gap #1) | Existing in stack — needs an **upgrade pin**. The YouTube extractor changed substantially in early 2026: SABR rollout, mandatory PO Tokens for some clients, JS runtime requirement. Pre-2025 yt-dlp will silently fail on YT. We keep yt-dlp (don't switch) because the same binary already works for B站/generic. | HIGH |
| `yt-dlp-get-pot` plugin | latest from PyPI | Auto-fetch YouTube PO Tokens per video-ID (required by some YT clients in 2026) | Manual PO Token extraction is no longer recommended — YouTube binds tokens to video-ID, so each video needs a fresh token. The plugin handles this transparently. Install opt-in (only needed if the user actually downloads YT). | MEDIUM (plugin churns; pin loosely, expect to re-evaluate every 6 months) |
| Deno (or Node) on PATH | latest stable | External JS runtime for yt-dlp's YouTube JS challenge solver | yt-dlp now requires an external JS runtime for full YouTube support. Deno is the project's official recommendation. Document in setup, not bundled. **Windows gotcha:** install via `winget install DenoLand.Deno` so it lands on PATH; manual zip extracts often miss PATH. | HIGH |
| `PySceneDetect` (`scenedetect`) | `0.6.7.1` | Generate a scene-cut timeline used as one input to Claude's fps schedule decision (gap #3) | The standard Python wrapper around content-aware scene detection. Outputs CSV timecodes — easy to load and feed Claude as JSON. We use it as **decision support for Claude**, not as a decision-maker (per the project's "工具是肢体, Claude 是大脑" rule). Default `detect-adaptive` works for screen-recorded tutorials with hard cuts; `detect-content` is fine for film-style cuts. Requires Python ≥ 3.10 (we have 3.13 ✓). | HIGH |
| `silero-vad` | `>=5.1` (PyPI) | Speech vs silence timeline for podcast/interview segmentation (gap #5b) and to feed the fps-schedule "is this segment talking head?" signal | Already implicitly used inside faster-whisper, but as a **standalone callable** it gives us a speech-density curve per second that Claude can read. ~2 MB JIT model, sub-1ms per 30 ms frame on CPU, no API. | HIGH |
| `filelock` | `>=3.16` | Cross-process advisory lock on `output/<slug>/.lock` for multi-agent parallelism (gap #7) | Pure-Python wrapper using `msvcrt` on Windows / `fcntl` on Unix; auto-releases on process crash; supports the `with` statement. Smaller scope than `portalocker`; no Redis dependency baggage; closer to the project's "minimum new deps" stance. | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| `imagehash` | existing — keep (`>=4.3.1`) | pHash for inter-frame similarity in the fps-automation step | When the schedule tool needs to **post-filter** Claude's plan: extract at high fps → pHash collapse near-duplicates → keep Claude's decided count. Fits the "tool reduces friction, doesn't decide" rule. | HIGH |
| `Pillow` | existing — keep (`>=10.0.0`) | JPEG IO | unchanged | HIGH |
| `numpy` | existing (transitive) | array math for pHash hamming-distance dedup | unchanged | HIGH |
| `pyannote.audio` | `4.0.x` + `pyannote/speaker-diarization-community-1` model | Speaker diarization for podcast/interview videos (gap #5b) | **OPT-IN, not default.** Only loaded when a video is classified by Claude as "podcast/interview". Requires a one-time HF token to download the pretrained model; once cached, runs offline. ~150 MB model; CPU-runnable. | MEDIUM (HF token gate is friction; document clearly) |
| `stable-ts` | `>=2.19` (PyPI) | Word-level timestamps when the existing segment-level granularity isn't enough for fps automation | **OPT-IN.** faster-whisper already emits word-level timestamps when called with `word_timestamps=True`; `stable-ts` adds a `refine()` pass that mutes-and-reprobes for tighter alignment. Use only if word-precision is needed (e.g. matching a code typing moment to a frame). | MEDIUM |
| `httpx` | existing — keep (strict pin `0.27.2`) | Already pinned for vendor douyin compatibility — **do not bump**. Any new tool that needs httpx must accept this pin. | unchanged | HIGH |

### Development / Operational Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `os.replace` (stdlib) | Atomic file replacement for safe artifact writes (gap #6) | Cross-platform atomic on Windows since Python 3.3. **Critical Windows rule:** the temp file MUST be on the same drive/filesystem as the target — otherwise it falls back to copy+delete (non-atomic). Pattern: `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` → write → `os.replace(tmp, target)`. No third-party dep needed. |
| `tempfile.NamedTemporaryFile(dir=...)` (stdlib) | Sibling-temp-file for the atomic-write pattern | Always pass `dir=target.parent` so the temp lands on the same filesystem. |
| `pathlib.Path` | existing — keep | Continue using `Path`, never `os.path`. **Windows extended-path note:** Paths > 260 chars only work if you (a) prefix with `\\?\` or (b) opt into Windows 10 long-path support via registry. Our `output/<slug>/...` paths can hit this if a slug + frame filename gets long; keep slugs ≤ 32 chars to stay safe. Python 3.13's pathlib does **not** auto-add `\\?\`. |
| `ffmpeg` | existing — keep | For local-mp4 input (gap #2): always run `ffprobe -v quiet -print_format json -show_format -show_streams <path>` first as a "probe-before-process" gate. It validates encoding, duration, codec, and surfaces "not actually a video" before whisper/scenedetect waste time. **Windows gotcha:** quote paths with spaces/CJK and pass via `subprocess.run(..., args_as_list)` — never via `shell=True`, which mis-handles CJK in PowerShell vs cmd. |
| `chardet` or `charset-normalizer` (already a transitive dep of httpx/requests) | Encoding-detection fallback for VTT subtitle files | Only needed if non-UTF-8 subs come back from non-Bilibili sources. **Note:** B站 yt-dlp output is reliably UTF-8; this is a defensive "in case YouTube auto-subs come in some weird encoding" safety net. LOW priority. |
| `argparse` (stdlib) | existing — keep | Same dispatch pattern as `agent/tools.py:241-251`; new subcommands (`probe_local`, `schedule_frames`, `diarize`) plug into the same `dict[str, callable]`. |

## Installation (only the new bits)

```bash
# Pin yt-dlp for YouTube reliability
pip install -U "yt-dlp>=2026.03.17"

# Optional YT PO Token plugin (only if you actually need YouTube)
pip install yt-dlp-get-pot

# Scene detection
pip install "scenedetect[opencv]==0.6.7.1"

# Standalone Silero VAD
pip install "silero-vad>=5.1"

# Cross-process lock
pip install "filelock>=3.16"

# Opt-in (podcast/interview videos)
pip install "pyannote.audio>=4.0"   # then accept HF model card + set HF_TOKEN

# Opt-in (word-level timestamp refinement)
pip install "stable-ts>=2.19"

# External JS runtime for YouTube — install once per machine, not per project
winget install DenoLand.Deno
```

Add to `requirements.txt` only the libs always needed; keep `pyannote.audio`, `stable-ts`, `yt-dlp-get-pot` in a separate `requirements-optional.txt` so the ¥0 main flow doesn't drag in 200+ MB of transformer/torch deps for users who only summarize B站.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative | Why Not as Default |
|-------------|-------------|-------------------------|--------------------|
| `yt-dlp` (keep) | `gallery-dl`, `you-get`, `lux` | If yt-dlp's YT extractor breaks for a specific platform you need | yt-dlp has the broadest active maintenance; switching mid-project means re-validating B站/抖音paths. Not worth it. |
| `PySceneDetect` | `ffmpeg -vf select='gt(scene\,0.4)'` raw filter | One-off shell scripts, no Python integration | The raw ffmpeg filter is fine but gives you stdout text to parse. PySceneDetect gives a proper Python list with frame timecodes already typed. We need it as JSON to feed Claude — PySceneDetect saves the parsing layer. |
| PySceneDetect | `scenecut-extractor` (PyPI) | If you only want a thin wrapper over the ffmpeg filter and don't need adaptive/hash detectors | Smaller, fewer detectors. PySceneDetect's `detect-adaptive` is meaningfully better on screen recordings (which is most of our queue: Godot tutorials, AI tools, etc.). |
| `silero-vad` standalone | Use VAD inside faster-whisper only | If you don't need a speech-density curve outside ASR | The whisper-internal VAD outputs are not exposed as a separate timeline; using `silero-vad` directly gets you a `[(start, end), ...]` list to plot/feed Claude. |
| `pyannote.audio` | `whisperx` diarization, `simple-diarizer`, `nemo-toolkit` | Already on whisperx; want a single tool | whisperx pulls in CTranslate2 GPU complications and word-alignment we don't need. `pyannote.audio` 4.0 community-1 model is the SOTA open-source option for diarization alone. |
| `stable-ts` | `whisper-timestamped`, `whisperx` forced alignment | Need confidence scores + DTW-based timestamps | `stable-ts` plugs into existing faster-whisper output directly via its `.refine()` method. The other two replace the transcription step, which would mean re-doing every cached `segs.json`. |
| `filelock` | `portalocker`, `fasteners` | If you need read/write locks (we don't) or distributed locks across machines (we don't) | `filelock` is the smallest, cleanest API for our case. `fasteners` uses `msvc _locking` on Windows which has historically had quirks; `filelock` uses `msvcrt.locking` directly with sane fallbacks. |
| `os.replace` (stdlib) | `python-atomicwrites` | If you need atomic writes for very small files with fsync guarantees | The stdlib is enough for JSON sidecars (which is all we write). `python-atomicwrites` is unmaintained and recommends rolling your own. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| OpenAI Whisper API, AssemblyAI, Deepgram, Speechmatics | Paid; violates ¥0 hard constraint | `faster-whisper` (existing) |
| OpenAI Vision / GPT-4V / Gemini Vision API for OCR | Paid; violates ¥0 | Claude Code reads JPEGs directly (existing) |
| Google Cloud Video Intelligence, AWS Rekognition Video, Azure Video Indexer | Paid SaaS, requires cloud upload of raw video | `PySceneDetect` + `silero-vad` locally |
| AssemblyAI's auto-chapters, OpenAI's chapter generation | Paid; we have Claude Code as the chapterer | Feed transcript + scene timeline to Claude, let it segment |
| `youtube-dl` | Effectively dead (YT extractor unmaintained); does not handle 2026 SABR/PO-Token regime | `yt-dlp` (existing) |
| `yt-dlp` **without** the JS runtime / PO Token plugin for YouTube | Will silently fail or return audio-only on many YT videos in 2026 | Install Deno + `yt-dlp-get-pot` |
| `whisperx` as a faster-whisper replacement | Would require reprocessing every cached `segs.json`; pulls heavier deps; Python 3.13 incompatibility reported in their issue tracker | Keep `faster-whisper` (existing); add `stable-ts` only if word-level alignment is needed |
| `imagededup` | Heavier (TF/Keras transitive); we already have `imagehash` doing the pHash job | `imagehash` (existing) |
| `videohash` | Hashes whole video; not what we want — we want per-frame novelty | per-frame `imagehash.phash()` then hamming-distance compare |
| `multiprocessing.Pool` invoking `faster-whisper` concurrently from one Python process | CTranslate2 has sequential encode/decode internals; multiple in-process instances contend on GPU memory and don't actually parallelize | Run **one whisper per Claude Code terminal** (separate Python processes, separate models). The OS scheduler handles it. Lock the `output/<slug>/` per video, not the whisper model. |
| Bumping `httpx` past `0.27.2` | Vendor douyin crawler uses the deprecated `proxies=` kwarg removed in 0.28+. Will break 抖音 path. | Keep the strict pin; new code that needs httpx adapts to 0.27 API. |
| Cursor-tracking via OpenCV for UI demos (gap #5a) | Adds OpenCV-full as a dep (~50 MB) for marginal gain — most UI demos don't show a system cursor in the recording, or it's already prominent enough that Claude reads it from the JPEG | Trust Claude's vision on the existing extracted frames. Only revisit if practice shows specific failures. |
| Recording mouse position from the source video via `mss` / `pyautogui` | `mss` records the **current** screen, not a historical recording. Wrong tool for post-hoc analysis. | N/A — drop this idea. |

## Stack Patterns by Variant

**If video source is a local mp4 path (gap #2):**
- Skip `download` stage entirely; create `meta.json` from `ffprobe` output (title from filename, duration from probe, source = `local`).
- Slug derived from `Path(input).stem` after sanitizing (drop CJK or transliterate via pinyin? — keep it simple: use `Path.stem` lowercased with `[^a-z0-9_-]` replaced by `_`, truncate to 32 chars).
- Everything downstream (`transcribe`, `aggregate`, `extract_frames`) is identical.

**If video is a podcast/interview (gap #5b):**
- Add a `diarize` stage (opt-in) that produces `diarization.json` keyed by speaker turn timecodes.
- Skip or down-weight frame extraction: extract one frame every 60 s as a sanity-check thumbnail, no more.
- Claude reads transcript + diarization + sparse thumbnails; output is structured around speaker turns and topics, not steps.

**If video is non-code UI demo (gap #5a):**
- Same pipeline as code tutorials — frames are still high-information.
- Higher base fps (0.5) since UI changes are more visual-only (less "narrate while changing").
- pHash dedup post-filter is more important here (UI often holds the same panel for 10+ s).

**If multiple Claude Code terminals (gap #7):**
- Each terminal works on a **different `output/<slug>/`**. The slug directory IS the unit of isolation.
- Acquire `filelock` on `output/<slug>/.lock` at the start of any tool that mutates that directory. Release on exit. Per-slug lock means cross-slug parallelism is unconstrained.
- Do NOT share faster-whisper model instances across processes — each Python process loads its own.
- `huggingface_hub` cache (`~/.cache/huggingface/hub`) is read-mostly and concurrent-read safe; the first process pays the download cost.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `httpx==0.27.2` | `vendor/douyin_api` (uses deprecated `proxies=`) | **Strict pin — do not bump.** This is the single most fragile compatibility constraint in the stack. |
| `faster-whisper>=1.0.3` | `ctranslate2>=4.5.0`, requires CUDA 12.3 + cuDNN 9 if using GPU | Existing CPU-`int8` path is unaffected; only matters if `ASR_DEVICE=cuda`. |
| `whisperx` | **incompatible with Python 3.13** as of issue m-bain/whisperX#1202 | Reason this research recommends `stable-ts` over `whisperx` for word-level timing. |
| `pyannote.audio` 4.0 | requires PyTorch ≥ 2.1, numpy < 2 in some sub-deps | Will pull torch ~700 MB. Acceptable as opt-in. |
| `scenedetect` 0.6.7.1 | Python ≥ 3.10, OpenCV optional but recommended | Install with `scenedetect[opencv]` extra for full detector set. |
| `silero-vad` 5.x | Pure PyTorch, no CUDA required | Same torch dep as pyannote — share the install. |
| `yt-dlp` 2026.03.17 | Python ≥ 3.9, optional Deno for YT JS challenges | Don't pin tighter than minor — yt-dlp ships fixes weekly. |
| Windows `os.replace` | Same volume / drive only for atomic semantics | Always create temp in `target.parent`. |

## Windows-Specific Gotchas (one per tool, per quality-gate requirement)

- **yt-dlp**: PowerShell mangles `&` and `?` in URLs unless URL is quoted with double-quotes. Existing code wraps URLs correctly; new tutorial CLIs must too. Also, `--cookies-from-browser chrome` works less reliably in 2026 due to DPAPI changes; prefer the existing Netscape cookies file pattern.
- **Deno**: `winget install DenoLand.Deno` puts it on PATH cleanly; standalone zip extracts often miss PATH and yt-dlp's "JS runtime not found" error is unhelpful.
- **PySceneDetect**: invokes `ffmpeg` for video decoding internally. If `ffmpeg` is in a non-standard location, set the `PATH` before invoking, not `cwd`.
- **silero-vad**: caches the JIT model under `%USERPROFILE%\.cache\torch\hub\snakers4_silero-vad_master\` — concurrent-read safe; first-process-pays download.
- **pyannote.audio**: model download from HF requires `HF_TOKEN` env var; on Windows, set in `.env` (don't use shell `export`-equivalents that don't persist).
- **filelock**: `msvcrt.locking` is **mandatory advisory** on Windows — file open with locking blocks other processes from open-for-write but NOT from open-for-read. Fine for our case (we lock the slug, not individual JSON files). Lock file should be a separate path (`<slug>/.lock`), not one of the artifact JSONs.
- **`os.replace`**: Windows holds an exclusive open handle longer than Linux. If another process has the target open for read, `os.replace` raises `PermissionError` on Windows where Linux wouldn't. Mitigation: short read windows; retry-with-backoff on `PermissionError`.
- **`pathlib.Path`** + CJK: When constructing paths with Chinese characters (the user's queue has CJK titles), keep the **slug** ASCII (existing convention `BVxxx` / `douyin_trae_ai` / `godot_brave` already does this) and let CJK live only inside `meta.json` payloads.
- **`ffmpeg`**: invoke as a list (`subprocess.run(["ffmpeg", "-i", str(path), ...])`), never with `shell=True`. The existing code follows this — keep it.
- **`faster-whisper`**: `ASR_DEVICE=cuda` requires cuDNN 9 + CUDA 12.3, which most Windows boxes don't have without manual install. Default `cpu / int8` is the right Windows default and the existing code chose it correctly. Do **not** auto-detect GPU — let the user opt in via env.
- **`stable-ts`** (opt-in): when running on Windows, set `device="cpu"` if you don't have CUDA — auto-detect can pick CUDA, then fail at first inference because the user has no cuDNN.

## Sources

**Verified via official docs / GitHub releases (HIGH confidence):**
- [yt-dlp Releases](https://github.com/yt-dlp/yt-dlp/releases) — confirmed 2026.03.17 is current stable; nightly 2026.04.10
- [yt-dlp PO Token Guide](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) — JS runtime + token-binding requirements
- [yt-dlp-get-pot on PyPI](https://pypi.org/project/yt-dlp-get-pot/) — auto-fetch plugin
- [PySceneDetect 0.6.7.1 docs](https://www.scenedetect.com/docs/latest/cli.html) — CSV output, detection algorithms, Python ≥ 3.10
- [silero-vad on PyPI](https://pypi.org/project/silero-vad/) and [GitHub](https://github.com/snakers4/silero-vad) — model size, perf, sampling rates
- [filelock docs](https://py-filelock.readthedocs.io/) — cross-platform `msvcrt`/`fcntl` semantics
- [Python `os.replace` reference](https://zetcode.com/python/os-replace/) and [issue python/cpython#62399](https://github.com/python/cpython/issues/62399) — Windows long-path + atomic semantics
- [Microsoft: MAX_PATH limitation](https://learn.microsoft.com/en-us/windows/win32/fileio/maximum-file-path-limitation) — Windows 10 1607+ extended-path opt-in

**Verified via official GitHub (HIGH confidence, but version churn — re-check at integration time):**
- [pyannote/speaker-diarization-community-1 on HF](https://huggingface.co/pyannote/speaker-diarization-community-1) — token gate, community-1 model
- [pyannote/pyannote-audio GitHub](https://github.com/pyannote/pyannote-audio) — 4.0 series
- [stable-ts on PyPI](https://pypi.org/project/stable-ts/) — `.refine()` method, word-level approach
- [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) — multiprocessing limits, sequential encode/decode
- [whisperX issue #1202](https://github.com/m-bain/whisperX/issues/1202) — Python 3.13 incompatibility (reason we don't recommend it)
- [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) — vendor still active in 2026; a_bogus implementation maintained

**MEDIUM confidence (community blogs / dev posts, cross-checked):**
- [DEV: 6 Ways to Get YouTube Cookies for yt-dlp in 2026](https://dev.to/osovsky/6-ways-to-get-youtube-cookies-for-yt-dlp-in-2026-only-1-works-2cnb) — DPAPI / `cookies-from-browser` fragility
- [DEV: Bypassing the 2026 YouTube "Great Wall"](https://dev.to/ali_ibrahim/bypassing-the-2026-youtube-great-wall-a-guide-to-yt-dlp-v2rayng-and-sabr-blocks-1dk8) — SABR + China proxy patterns
- [Modal: Choosing between Whisper variants](https://modal.com/blog/choosing-whisper-variants) — faster-whisper vs whisperx tradeoff narrative
- [BERTopic getting-started](https://maartengr.github.io/BERTopic/index.html) — considered, not recommended (overkill — Claude does the topic segmentation itself)

**LOW confidence (single source, treat as starting point):**
- [aiadoptionagency: Silero VAD 2026 guide](https://aiadoptionagency.com/silero-vad-voice-activity-detection/) — version-specific claims; cross-check at integration

---
*Stack research for: Claude-driven video-to-tutorial pipeline (¥0 brownfield expansion)*
*Researched: 2026-04-30*
*Existing stack from `.planning/codebase/STACK.md` is treated as load-bearing and unchanged unless explicitly noted.*
