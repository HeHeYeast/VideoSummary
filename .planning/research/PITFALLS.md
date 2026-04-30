# Pitfalls Research

**Domain:** Claude-driven video-to-tutorial pipeline (¥0 local, brownfield expansion)
**Researched:** 2026-04-30
**Confidence:** HIGH for documented integrations (yt-dlp / faster-whisper / ffmpeg / Windows / 抖音); MEDIUM for novel "Claude-as-decision-maker" failure modes (reasoned over the existing codebase + extrapolation)

> **NOTE:** This file was assembled from `gsd-project-researcher` agent output. The agent returned structured findings but did not write the file directly (mis-interpreted a system reminder). All content below is verbatim from the agent's research output, reorganized into the PITFALLS.md template.

> **Scope:** This file documents NEW pitfalls each target feature introduces, **layered on top of** `.planning/codebase/CONCERNS.md` — does not duplicate already-known existing-codebase concerns.

---

## Critical Pitfalls

### Pitfall P1.3: "Every video looks the same" — Claude lacks priors

**What goes wrong:**
Claude converges on a single comfortable mode (probably "step-by-step reproduction") and never produces principles-heavy or extensions-only modes. The slash-command prompt is the only signal Claude has about what "good" output looks like; without exemplar pins, the adaptive-output goal collapses.

**Why it happens:**
The 17 archived `output/` directories all look like step-by-step reproductions (because they're all game-dev tutorials). Claude infers "this is what good output looks like" from those — even when given a podcast or principles-heavy lecture.

**How to avoid:**
Hand-author **2-3 minimal exemplar `summary.md` skeletons in CLAUDE.md**, one per teaching dimension (reproduction / principles / extensions). The slash command then reads: "if mostly demo → format like exemplar A; if mostly explanation → format like exemplar B."

**Warning signs:**
Test on a deliberately principles-heavy video (e.g., "why ECS over OOP for game state"); Claude outputs a step-by-step reproduction guide because that's what existing `output/` looks like.

**Phase to address:** Adaptive-Teaching-Output, Phase 0 (before tool changes).
**Severity:** Showstopper

---

### Pitfall P2.1: Silent visual content goes undersampled

**What goes wrong:**
Claude emits the fps schedule from the *transcript*, but the transcript has nothing to say about: (a) silent code-typing demos, (b) UI navigation done while the host pauses, (c) build/load/compile waits where the screen content changes meaningfully (compile errors appear), (d) edited cuts where a new artifact appears mid-sentence. Result: the multimodal step silently misses material.

**Why it happens:**
Single source of truth (transcript) covers only the audio dimension. The current `agent/frames_v2.py:36-44` voice-anchor regex (CONCERNS §2.7) is the v2-pipeline analog of this and already misses common phrases.

**How to avoid (three layers):**
1. Tool emits **silence map** alongside transcript: any audio gap > 5s in `paragraphs.json` is flagged. Claude must explicitly handle each gap in the schedule (skip / sample at fallback fps 0.2 / mark for second-pass).
2. **Always include a low-rate baseline pass** (e.g. fps 0.05 across the whole video as cheap safety net). ~30 frames for a 10-min video — negligible cost, catches anything the smart schedule missed. One-line addition in batch executor.
3. **Recovery story:** make the existing 补充抽帧 step in CLAUDE.md a documented step: "after first frame review, if any segment has < N frames or frames look uninformative, emit a 补抽 fps schedule."

**Warning signs:**
Run on a known-good video, compare emitted fps schedule to the human-tuned schedule that produced the committed `summary.md`. Segments where the schedule recommends `fps: 0.1` ("just talking") but human used `fps: 0.3` are blind spots.

**Phase to address:** fps-Automation phase, must land *with* the feature, not after.
**Severity:** Showstopper

---

### Pitfall P3.1: GFW + SABR YouTube double-block

**What goes wrong:**
YouTube is blocked in mainland China AND yt-dlp is in an active anti-bot war (SABR / PO-token). User needs proxy *and* fresh yt-dlp *and* valid YouTube cookie *and* PO-token support — any one going stale silently fails with uninformative "Sign in to confirm" error.

**Why it happens:**
Multiplicative failure surface from independent moving parts (GFW, YouTube anti-bot, yt-dlp version, cookies, proxy).

**How to avoid (don't try to "make it work everywhere", make failure legible):**
1. Detect platform from URL early in `agent/tools.py` dispatcher. If YouTube, run a 2-second preflight (`yt-dlp --simulate <url>`) and classify failure: network unreachable → "GFW: configure HTTPS_PROXY"; HTTP 403/429 → "rate-limited / cookies stale"; "Sign in to confirm" → "needs `--cookies-from-browser` or fresh PO token"; else → "yt-dlp version may be stale, run `pip install -U yt-dlp`."
2. Read `HTTPS_PROXY`/`HTTP_PROXY` from env (Windows convention) and pass through to yt-dlp via `--proxy`.
3. Document expected setup in CLAUDE.md alongside the douyin-cookies section.
4. Have a **graceful manual fallback**: if download fails, accept a local file path drag-and-drop pointing at a manually-downloaded mp4 (dovetails with Local-mp4 feature).

**Warning signs:**
"Sign in to confirm you're not a bot" error that could be GFW *or* anti-bot *or* expired cookie *or* outdated yt-dlp.

**Phase to address:** YouTube-support phase, dispatcher and docs.
**Severity:** Showstopper for the feature; not for the project (graceful fallback to local mp4 path keeps user productive).

---

### Pitfall P4.1: Chinese filenames in subprocess args on Windows

**What goes wrong:**
`subprocess.run(["ffmpeg", "-i", "我的视频.mp4", ...])` may fail or silently mangle. Subprocess args go through current code page (GBK on zh-CN Windows). Existing `agent/tools.py:107-118` and `src/asr.py:43-48` call ffmpeg without explicit unicode handling. Current pipeline ducks this because `output/<BVxxx>/video.mp4` is always ASCII; local mp4 input changes that.

**Why it happens:**
Windows zh-CN locale defaults to GBK code page; subprocess args don't get UTF-8 unless explicitly handled.

**How to avoid (three-step):**
1. **Always copy/symlink the input mp4 into `output/<slug>/video.mp4` first**, where `<slug>` is generated ASCII-safe (e.g., hash of original filename + first 8 ASCII chars). Existing pipeline assumes this layout — preserve it.
2. Pass paths to ffmpeg via `pathlib.Path.as_posix()` and ensure `subprocess.run(..., text=True, encoding="utf-8")` where capturing output.
3. As a guard, validate `out_dir` is ASCII-only (paths under `output/`); raise a clean error if user redirects `--out` to a Chinese path.

**Warning signs:**
User passes `D:\videos\Godot 2D 教程.mp4` → ffmpeg returns `No such file or directory`; or audio extraction succeeds but `audio.wav` ends up at `D:\videos\Godot 2D ??.wav` (replacement chars).

**Phase to address:** Local-mp4-input phase.
**Severity:** Showstopper

---

### Pitfall P6.1: Speaker diarization is a separate problem from ASR

**What goes wrong:**
faster-whisper does not do diarization. Transcript is a single linear stream. For a 2-person interview, the resulting `paragraphs.json` looks like a single voice — Claude cannot distinguish who said what without explicit speaker labels.

**Why it happens:**
ASR and speaker-diarization are different ML tasks. faster-whisper bundles only ASR.

**How to avoid:**
Integrate `pyannote.audio` (Apache-2.0, requires HF token for model download but inference is free and offline thereafter); produce `diarization.json` alongside `segs.json` with `[{start, end, speaker_id}]`; in `aggregate`, merge speaker_id into paragraphs. Tradeoff: pyannote 3.1 needs ~1 GB more RAM and ~25% extra wall time. For Windows + CPU + no CUDA setup, this is a real cost.

Cheap-and-cheerful alternative: heuristic 2-speaker split by VAD energy + spectral centroid (works on conversational podcasts with one mic each, fails on shared-mic interviews).

**Warning signs:**
`summary.md` for an interview reads as a monologue; quotes attributed to "the speaker" instead of named guest/host.

**Phase to address:** Podcast-mode phase. Likely the most code-heavy single addition in the milestone.
**Severity:** Showstopper for podcast mode

---

### Pitfall P7.1: Stale-artifact silent reuse when params change

**What goes wrong:**
Already partially flagged in CONCERNS §5.4: cache validation is `path.exists()` only. Once Claude is emitting fps schedules and choosing whisper model sizes, the same `output/<slug>/` may have artifacts produced under different parameter sets. Resume "from where we left off" silently uses the wrong upstream artifact.

**Why it happens:**
File-existence cache is parameter-blind. New variability (whisper model, vad threshold, fps schedule) makes this insufficient.

**How to avoid (extend the existing cache, don't replace it):**
1. Each artifact gets a sidecar `<artifact>.params.json` with the parameters that produced it (whisper_model, vad_settings, fps_schedule, ffmpeg_version, etc.).
2. On every step, validate `<artifact>.params.json` matches current params; mismatch → skip cache, regenerate, log "regenerating because: whisper_model changed small → medium."
3. `--force` flag at the workflow level remains as the nuclear option.

**Warning signs:**
User re-runs with `--whisper medium` to fix transcription quality, but `segs.json` from the previous `small` run is reused; user is confused why output didn't improve.

**Phase to address:** Resume phase. Land first if possible — every other feature benefits.
**Severity:** Showstopper

---

### Pitfall P8.1: Vendor `config.yaml` race (parallel douyin)

**What goes wrong:**
CONCERNS §2.2: `agent/douyin_downloader.py:46-61` rewrites the global `vendor/douyin_api/crawlers/douyin/web/config.yaml` on each call. Two parallel agents downloading two douyin videos = race, last-writer wins, one or both downloads fail with cryptic error.

**Why it happens:**
Vendor crawler reads global config from disk; no per-process isolation.

**How to avoid:**
Either (a) **per-process config patching** — fork the vendor's config-load to accept an explicit dict instead of reading `config.yaml`, or (b) **process-level lock** on the config file with `fcntl`/`msvcrt` for the duration of a single download. (b) is cheaper but serializes douyin downloads. (a) is the proper fix.

**Warning signs:**
Parallel douyin downloads succeed individually but fail when run concurrently; intermittent.

**Phase to address:** Parallel phase. If parallel ships, this must ship with it.
**Severity:** Showstopper for parallel douyin

---

### Pitfall P8.2: Whisper concurrent model loads → RAM OOM

**What goes wrong:**
CONCERNS §5.2: Whisper model is reloaded per call (no global cache). Two parallel `transcribe` invocations each instantiate a `WhisperModel(...)` — `medium` is ~1.5 GB on int8, two copies = 3 GB plus working memory. On 16 GB Windows machine with browser open, that's the threshold for OOM.

**Why it happens:**
No model warm cache; parallel invocations can't share weights.

**How to avoid:**
Introduce a `whisper_server` process that holds the model in memory and accepts transcription jobs over a local socket / file queue. Heavy but right. Cheap alternative: serialize transcription steps via a file lock so only one transcribe runs at a time even if user launches multiple agents. The codebase already supports the cheap version with no changes — document it.

**Warning signs:**
Parallel transcribes; one or both die silently or with `MemoryError`. Or system gets paged out and slows to a crawl.

**Phase to address:** Parallel phase, decide upfront whether to ship server pattern or just document constraint.
**Severity:** Showstopper for parallel whisper

---

### Pitfall U1: YOLO / Coarse mode skips the validation step

**What goes wrong:**
When user picks "ship fast, coarse granularity," temptation is to skip: (a) run on known-good archived video first to confirm no regression; (b) sidecar `params.json` schema for cache validation; (c) explicit fail-loud parser for the fps schedule. Each is "infrastructure that doesn't move the demo forward" and dies first.

**Why it happens:**
YOLO mode optimizes velocity; preflight checks feel like overhead until something breaks at video #3 in queue.

**How to avoid:**
Before any feature is built, freeze a **golden-output regression suite**: pick 3 representative archived videos (e.g., `BV132wizyEEB` for code, `godot_brave` for game/Godot demo, `douyin_trae_ai` for AI/UI), commit current `summary.md` for each as the regression baseline. Every milestone-2 change must reproduce these (allowing intentional improvements, but no surprise drift). Cost: zero new code, ~30min one-time.

**Warning signs:**
New feature ships, works on the demo video, breaks on video #3 in queue.

**Phase to address:** Milestone preflight, before phase 1.
**Severity:** Meta-showstopper

---

### Pitfall U2: 17-video legacy queue compatibility regressions

**What goes wrong:**
17 archived `output/<slug>/` directories were produced under current `meta.json` schema, current `paragraphs.json` schema, current `frames/seg_<start>_<index>.jpg` filename convention. Any milestone change to those schemas / filenames silently breaks resume / re-run on legacy archives.

**Why it happens:**
PROJECT.md hard-locked "保留当前方案 / 快速回退" but new features will inevitably want schema additions.

**How to avoid:**
Lock existing schemas as **frozen** with `schema_version: "1"` retroactively; new fields opt-in additive only; old files load with defaults for missing fields. Run regression suite (U1) on at least 3 archived dirs before merging any code change. Specifically watch:
- `output/<slug>/` directory layout (CLAUDE.md hard-codes path conventions)
- `frames/seg_<start>_<index>.jpg` filename grammar (referenced by `agent/tools.py:122-124`)
- `meta.json` field set (`title`, `uploader`, `duration`, `url`, `video_path`, `subtitle_path`, `source`)
- `paragraphs.json` shape (`{paragraphs: [{start, end, text}]}`)

**Warning signs:**
`python -m agent.tools transcribe output/BV1C9QCBdE1U/video.mp4 --out output/BV1C9QCBdE1U` fails post-update because `transcribe` now expects a field that didn't exist in old `meta.json`.

**Phase to address:** Every phase touching tools or schemas.
**Severity:** Showstopper

---

### Pitfall U3: Single-user Windows 11 China — proxy / network / encoding / locale

**What goes wrong:**
Compounds with P3.1, P4.1. Specifically:
- **Proxy:** GBK terminal can't print emoji titles (CONCERNS §1.4). UTF-8 codepage (`chcp 65001`) helps but breaks some legacy tools. Windows-native `HTTP_PROXY` env var convention vs Unix `http_proxy` differs by case.
- **Network:** Bilibili occasionally rate-limits CN IPs (yes, even from CN). YouTube via proxy + GFW is fragile; latency to YouTube via Singapore proxy ≈ 200ms baseline.
- **Encoding:** zh-CN Windows defaults to GBK code page. ffmpeg subprocess args (P4.1), `print(json.dumps(meta))` (handled in `agent/tools.py:58-59`), Python file I/O without explicit `encoding="utf-8"` all hit this.
- **Locale:** `locale.getpreferredencoding()` returns `cp936`. Anywhere in code that calls `open(path)` without `encoding="utf-8"` reads files as GBK by accident; will crash on any UTF-8 file.

**Why it happens:**
Default Windows zh-CN locale is GBK; user's environment is multi-protocol (GFW + proxy + UTF-8 vs GBK).

**How to avoid (do once, save the rest of the milestone):**
1. Enforce `encoding="utf-8"` on every `open()` call in the codebase (audit `agent/` and `src/`). Current code is mostly correct but inconsistent.
2. Document in CLAUDE.md: "Run `chcp 65001` once per terminal session before invoking `python -m agent.tools`."
3. Set `PYTHONUTF8=1` env var globally (Windows 10+). Document.
4. `HTTPS_PROXY` and `HTTP_PROXY` (uppercase) read by `agent/tools.py` and forwarded to yt-dlp as `--proxy`.

**Warning signs:**
Intermittent encoding errors on different files; `UnicodeDecodeError: 'gbk' codec can't decode byte 0x... in position ...`.

**Phase to address:** Cross-cutting; address in any phase that touches I/O or subprocess.
**Severity:** Showstopper for YouTube; annoying for everything else.

---

## Annoying-Tier Pitfalls (Reference)

### Adaptive Output

**P1.1 First-segment anchoring:** Claude reads `paragraphs.json` top-to-bottom; whatever the video opens with biases the depth decision. **Fix:** force the depth-decision step to read all paragraphs and emit explicit "video-shape" classification (time-percentages per mode: talking-head / code-demo / UI / slide / silence).

**P1.2 Output format drift:** "Claude decides whether to include reproduction guide" + zero schema pin = next run produces different section ordering / heading depth. The 17 archived `summary.md` were each written under current Phase 6 template. **Fix:** keep a stable output-format spec as CLAUDE.md sub-section ("regardless of dimensions, conventions hold: timestamp `[HH:MM:SS]`, code fence with explicit lang, image embed `![](frames/seg_xxxx_xxxxxx.jpg)`, second-person imperative voice"). Content adaptive; form not.

**P1.5 Wrong depth decision wastes tokens:** mid-write Claude realizes chosen depth is wrong. **Fix:** depth-decision step writes a commit artifact `output/<slug>/depth_plan.md`; user reviews before any prose is written. Also a resume checkpoint.

### fps Automation

**P2.2 Sudden cuts straddle segment boundaries:** edited tutorials with jump-cuts every 5-10s get sampled at fps 0.3, missing 30% of cuts. **Fix:** `detect_scenes <video> --threshold 0.4` preflight emits `scenes.json`; fps-schedule prompt includes "always sample within 0.5s of every detected cut."

**P2.3 Schedule format drift:** Claude emits prose fps recommendations; tool regex-parses; brittle. **Fix:** strict JSON schema for schedule; tool validates with explicit error on unknown keys / missing fields / overlapping segments. (Precedent: `agent/pass1_classify.py:_parse_classification` parser fragility — CONCERNS §1.2.)

### YouTube

**P3.2 yt-dlp version drift:** YouTube extractor breaks roughly monthly in 2026. **Fix:** at startup, log `yt-dlp.__version__`; if older than 90 days, print one-line "consider running `pip install -U yt-dlp`." Don't auto-update.

**P3.3 VTT vs auto-generated subs vs ASR:** YouTube auto-subs are 70-85% accurate. **Fix:** default to running faster-whisper even if VTT exists for YouTube; only skip ASR when `.vtt` is `--write-subs` (creator-uploaded), not `--write-auto-subs`. Mark `subtitle_origin` in `meta.json`.

**P3.4 Generic platform metadata gaps:** new platforms may not populate `uploader` or `duration`. **Fix:** introduce `meta.json` schema validation; missing fields → null + warning, not silent failure.

### Local mp4

**P4.2 Codec / container variability:** HEVC, AV1, MKV, no audio track. **Fix:** ffprobe preflight; clear error if no audio; optional remux to H.264 mp4 for non-mp4 containers. Surface ffprobe output in `meta.json`.

**P4.3 Variable framerate (VFR):** OBS/iPhone recordings; ffmpeg `-vf fps=N` against VFR drops/duplicates frames silently. **Fix:** add `-vsync vfr` to extract_frames invocation. Apply uniformly to all sources.

### UI Demo

**P5.1 Pixel-text vs code-text accuracy:** UI software uses proportional fonts + anti-aliasing; multimodal accuracy lower than monospace. **Fix:** for UI-mode, instruct Claude to "quote-with-uncertainty"; lower confidence floor; cross-frame triangulation.

**P5.2 Tooltip blocking:** transient tooltips cover the value being demoed. **Fix:** "if frame has tooltip obscuring target, sample 0.5s earlier or later; if still obscured, mark 'value not visible' rather than guessing."

**P5.3 Cursor invisibility:** dark cursor on dark UI; cursor not captured. **Fix:** "if cursor invisible across frames, infer click target from before/after panel state diff. Always name control by label or icon, never spatial position."

### Podcast

**P6.2 Whisper hallucinations on silence:** 30s+ files + silence patches → repetition. Existing `HALLUCINATION_PATTERNS` blocklist (~7 strings) too narrow for 60-min podcast. **Fix:** tighten VAD (`min_silence_duration_ms=500`, raise threshold for podcasts); post-pass repetition detector flags any 3-gram repeated >3× consecutive for human review (don't auto-delete — `不注水不编造` redline).

**P6.3 Topic chaptering on rambling content:** current `aggregate` is silence-gap-driven, useless on 60-min banter. **Fix:** for podcast-mode, Claude reads transcript and emits `chapters.json` with `[{start, end, topic_title, summary_line}]`. Pure Claude-decides step; rely on Claude to do structural cut, not silence heuristic.

**P6.4 Frames useless but workflow assumes them:** `/summarize-video` Phase 3-4 built around 抽帧+看帧; podcast = static thumbnail or talking-head webcams. **Fix:** podcast-mode skips `extract_frames` entirely (or 1-2 frames per chapter for visual variety); writing template substitutes blockquotes for image embeds.

### Resume

**P7.2 Atomic-write Windows:** `os.rename` historically not atomic on Windows; `os.replace` is the right primitive. **Fix:** wrap all artifact writes in `tmp_path = path + ".tmp"; write(tmp_path); os.replace(tmp_path, path)`. ~15 LOC.

**P7.3 Permission errors from prior locked file handle:** Windows Search / Defender / OneDrive may hold lock. **Fix:** retry-with-backoff on `PermissionError` (3 retries, 0.5s delay) before failing.

**P7.4 Schema drift between runs:** milestone-2 changes `paragraphs.json` schema; archived dirs break post-update. **Fix:** every artifact gets `schema_version` field; loaders check and migrate-or-skip.

### Parallel

**P8.3 Cookies file race:** read per download, no lock. **Fix:** read cookies into memory at download start; don't re-read mid-run.

**P8.4 Terminal output interleaving:** two agents in two terminals print confusingly. **Fix:** prefix every log line with slug `[BV132wiz]` / `[godot_brave]`. One-line `logging.basicConfig` change.

**U4 No provenance on per-run failure:** every bug bubbles back to user. **Fix:** every step writes `step_log.json` with parameters used and artifact hashes produced; resume reads log; failures point at *which step* and *what params*.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip params.json sidecars | Saves a few hours of plumbing | Stale-cache silent reuse causes "why didn't my output improve?" debugging | Never (P7.1 is showstopper) |
| Skip golden regression baseline | 30 min savings | YOLO mode silently breaks legacy queue path | Never (U1 is meta-showstopper) |
| Regex-parse Claude prose for fps schedule | Saves writing JSON schema | Mirror of `pass1_classify` parser fragility — silent dropped entries | Never |
| Skip atomic writes on Windows | Saves 15 LOC | Truncated JSON breaks resume mid-pipeline | Never |
| Skip subtitle_origin tagging | Saves 10 LOC | Silent ASR-skip on auto-generated YouTube subs (70% accuracy substituted for 95%) | Never on YouTube |
| Auto-delete repeated whisper hallucinations | Cleaner output | Crosses `不注水不编造` redline; false positives delete real content | Never (PROJECT.md redline) |
| Skip local-mp4 ASCII slug normalization | Saves a hash function | ffmpeg subprocess fails on Chinese filenames | Never on Windows zh-CN |
| Skip vendor config.yaml lock | Saves 1-day dev | Silent race on parallel douyin downloads | Acceptable while parallelism is NTH; must add if parallel ships |
| Defer pyannote integration | Saves 2-3 days; avoids HF gate | Podcast mode ships visibly worse than dedicated tools (transcript reads as monologue) | Acceptable in Phase 1; not in podcast phase |
| Skip yt-dlp version warning | Saves 5 LOC | User debugs YouTube extractor failures that aren't really code bugs | Acceptable until YouTube ships |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| yt-dlp YouTube | Pin `>=2024.10.0` and assume forward-compat | Verify version monthly; expect SABR/PO-token changes; surface failure category (GFW vs auth vs version) |
| yt-dlp YouTube subs | Trust `--write-auto-subs` quality | Auto-generated 70-85% accurate; default to ASR for YouTube even if VTT exists |
| yt-dlp generic platforms | Assume `meta.json` always populated | Validate schema; null-fill missing fields with warning |
| ffmpeg subprocess on Windows | Use default subprocess encoding | Pass paths via `Path.as_posix()`; `text=True, encoding="utf-8"` for capture |
| ffmpeg fps extraction | Run on VFR source without `-vsync vfr` | Always set `-vsync vfr` (no downside on CFR) |
| pyannote diarization | Bundle in `requirements.txt` | Opt-in `requirements-optional.txt`; only loaded when video classified as podcast |
| faster-whisper VAD | Default settings on long podcasts | Tighten `min_silence_duration_ms=500`; raise threshold; post-pass repetition detector |
| vendor douyin_api | Per-call rewrite of `config.yaml` | Per-process patch (fork) or file lock during download (CONCERNS §2.2) |
| Whisper concurrent loads | Two parallel transcribe = 2× model RAM | Whisper-server pattern OR file-lock to serialize transcribe |
| Cookies file refresh | Re-read mid-run | Read into memory at start; don't re-read |
| Windows long paths | Assume `LongPathsEnabled` | Reject UNC/long paths with clear error; never `shell=True` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Whisper model reload per call | Each `transcribe` invocation pays ~5s init cost | Whisper-server with persistent model (deferred) OR accept the cost (current design) | Already broken; tolerable until podcast mode (longer files amortize the init cost) |
| Parallel Whisper OOM | `MemoryError` or system swap hammer | Serialize transcribes via file lock; or whisper-server | 2+ concurrent invocations on 16 GB RAM |
| 4K UI screen recording downscaled to 854px | "Text too small to read" reports from Claude | Allow `--width 1280`/`1920` override for UI-mode | Any UI demo from 4K recording |
| pyannote diarization on CPU | 3-5× wall time of audio length | Spike measurement before committing; document CPU cost | 60+ min podcast on CPU-only laptop |
| Multi-agent shared whisper instance | Both agents stall on model contention | One process per agent; no shared model | NTH parallelism phase |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Commit cookies file (`www.douyin.com_cookies.txt`, `youtube_cookies.txt`) | Account takeover via leaked session | `.gitignore` already covers; verify before each commit |
| Log full URLs with private tokens | Token leak in commit history | Redact query strings in log output |
| Subprocess injection via filename | Arbitrary code execution if filename comes from URL | Slug normalization to ASCII-safe; never `shell=True` |
| Trust local mp4 path without validation | Path traversal into other dirs | `Path(input).resolve()`; reject `..` in path |
| Auto-update yt-dlp from app | Supply chain attack vector | Manual `pip install -U yt-dlp` — never auto-update |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Sign in to confirm" on YouTube | User stuck, error tells nothing | Preflight + classify failure ("GFW" / "cookies stale" / "yt-dlp version" / "PO token") |
| Stale-cache silent reuse | "Why didn't my fix work?" debugging cycles | params.json sidecar; loud "regenerating because: X changed" log |
| Adaptive output drift | "Why does this video's doc look so different from yesterday's?" | Lock form (timestamp format / code fence / image embed); content adaptive |
| Frame extraction zero output | Pipeline succeeds but no frames | ffmpeg stderr surface (CONCERNS §6.2); `-vsync vfr`; sanity-check frame count |
| Podcast frames embedded | "Why is my podcast doc full of host's face?" | Podcast-mode skips `extract_frames` entirely |
| Tooltip blocks UI value | Claude guesses or makes up the value | "If obscured, mark 'value not visible'" — `不注水不编造` redline |

## "Looks Done But Isn't" Checklist

Verify during each phase execution:

- [ ] **Adaptive output:** Does the format spec lock survive across runs? — Re-run on `output/godot_brave/` and diff `summary.md`; should match modulo intentional improvements.
- [ ] **Adaptive output:** Are exemplars committed in CLAUDE.md? — Without 2-3 skeleton examples, Claude regresses to one mode.
- [ ] **fps automation:** Does the schedule cover full duration? — Validate union of segments == `[0, duration)` ± 2s.
- [ ] **fps automation:** Is silence-map / baseline-pass actually emitted? — Check for 0.05 fps fallback in schedule.
- [ ] **fps automation:** Does parser fail loud on malformed Claude output? — Test with `0:30 - 1:00` style timestamp; should error, not silent-drop.
- [ ] **YouTube:** Does preflight classify failures? — Test with offline / wrong cookies / old yt-dlp; each should produce distinct error.
- [ ] **YouTube:** Is `subtitle_origin` recorded in meta.json? — Differentiate auto/creator/asr/none.
- [ ] **Local mp4:** Does Chinese filename input still work? — Test with `D:\videos\我的教程.mp4`.
- [ ] **Local mp4:** Does ffprobe preflight catch missing audio? — Test with video-only mp4.
- [ ] **Local mp4:** Is `-vsync vfr` applied uniformly? — Test on OBS-recorded source.
- [ ] **UI demo mode:** Does Claude downgrade pixel-text confidence? — Test on Photoshop UI capture.
- [ ] **Podcast mode:** Is diarization emitting speaker_id labels? — Test on 2-person interview; speakers attributed.
- [ ] **Podcast mode:** Does Whisper repetition post-pass flag hallucinations? — Test on 60-min podcast.
- [ ] **Resume:** Does params.json sidecar trigger regen on whisper model change? — Test small → medium switch.
- [ ] **Resume:** Are atomic writes used everywhere? — Audit codebase for `.write()` of artifacts.
- [ ] **Resume:** Do loaders handle `schema_version` migration? — Test on archived `output/BV132wizyEEB/`.
- [ ] **Parallel (if shipped):** Does vendor `config.yaml` race break under load? — Test 2 concurrent douyin downloads.
- [ ] **Parallel (if shipped):** Do log lines have slug prefix? — Test 2 concurrent invocations.
- [ ] **U1 regression:** Does the new milestone reproduce all 3 baselines? — Run new flow on `output/BV132wizyEEB/`, `godot_brave/`, `douyin_trae_ai/`; diff against committed `summary.md`.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| P1.3 "Every video looks the same" | LOW | Add 2 more exemplars to CLAUDE.md; re-run /summarize-video on the affected video |
| P2.1 Silent visual content missed | LOW | Run 补抽 fps schedule on the missed segment; baseline 0.05 fps pass usually catches |
| P3.1 YouTube failure | MEDIUM | Local mp4 fallback (download manually, drop into pipeline) |
| P4.1 Chinese filename ffmpeg crash | LOW | Slug-normalize on copy-into-output; one retry |
| P6.1 No diarization | HIGH | Re-run with pyannote enabled; expensive but works |
| P7.1 Stale-cache wrong output | LOW | `--force` flag; rerun the affected stage |
| P7.2 Truncated JSON | LOW | Delete artifact; rerun stage (cache-miss now produces fresh) |
| P8.1 Vendor config.yaml race | MEDIUM | File lock retroactively; serialize affected downloads |
| U1 / U2 regression on legacy video | HIGH | Revert milestone changes touching schemas; re-test golden baseline |

## Pitfall-to-Phase Mapping

| Pitfall | Severity | Prevention Phase | Verification |
|---------|----------|------------------|--------------|
| U1 Golden regression suite | Showstopper-meta | Phase 0 (Preflight) | Commit baselines for 3 videos before any feature |
| U2 Schema freeze | Showstopper | Phase 1 (Resume) + every phase touching schemas | Loader test on archived `output/BV132wiz/` |
| U3 Encoding/proxy/locale | Showstopper for YT | Cross-cutting; first-touch in Resume phase | `chcp 65001`; PYTHONUTF8=1; `encoding="utf-8"` audit |
| P7.1 params.json sidecars | Showstopper | Phase 1 (Resume) — land first | Re-run with whisper small → medium triggers regen |
| P7.2 Atomic writes | Annoying | Phase 1 (Resume) | Kill mid-write; resume sees clean state |
| P7.4 schema_version | Annoying | Phase 1 (Resume) | Loader handles version: 1 → 2 |
| P2.1 Silence map + baseline | Showstopper | Phase 2 (fps Automation) | Schedule covers all silence segments OR has 0.05 baseline |
| P2.3 Strict schedule schema | Annoying | Phase 2 (fps Automation) | Malformed input fails loudly |
| P2.4 Duration coverage | Cosmetic | Phase 2 (fps Automation) | Validation step asserts coverage |
| P1.3 CLAUDE.md exemplars | Showstopper | Phase 3 (Adaptive Output) | Test on principles-heavy + reproduction-heavy videos |
| P1.2 Format spec lock | Annoying | Phase 3 (Adaptive Output) | Diff regression against archived summary.md |
| P1.1 Full-transcript anchor | Annoying | Phase 3 (Adaptive Output) | Two videos with similar arcs but different opens get same depth verdict |
| P1.5 depth_plan.md artifact | Annoying | Phase 3 (Adaptive Output) | Plan committed before prose writing |
| P4.1 Chinese filename slug | Showstopper | Phase 4 (New Sources / local mp4) | Test with Chinese path input |
| P4.2 ffprobe preflight | Annoying | Phase 4 (Local mp4) | Test no-audio mp4 |
| P4.3 -vsync vfr | Annoying | Phase 4 (Local mp4 + uniform) | Test OBS recording |
| P3.1 YouTube failure classifier | Showstopper for YT | Phase 4 (YouTube layer) | Test offline / stale-cookie / old-yt-dlp |
| P3.3 subtitle_origin | Annoying | Phase 4 (YouTube layer) | Auto vs creator subs distinguished |
| P5.1-5.3 UI demo guidelines | Annoying | Phase 5 (UI demo) — slash command only, no code | Test on Photoshop UI capture |
| P6.1 pyannote diarization | Showstopper for podcast | Phase 5 (Podcast) | 2-speaker interview gets speaker_id labels |
| P6.2 Whisper repetition guard | Annoying | Phase 5 (Podcast) | 60-min podcast post-pass flags |
| P6.3 chapters.json | Annoying | Phase 5 (Podcast, slash command) | Rambling content gets meaningful chapters |
| P6.4 Skip frames in podcast | Annoying | Phase 5 (Podcast, slash command) | Podcast summary has no irrelevant face embeds |
| P8.1 Vendor config lock | Showstopper-if-parallel | Phase 6 (Parallel — NTH) | 2 concurrent douyin downloads |
| P8.2 Whisper serialize lock | Showstopper-if-parallel | Phase 6 (Parallel — NTH) | 2 concurrent transcribe — no OOM |

## Sources

**yt-dlp / YouTube anti-bot reality 2026:**
- [yt-dlp #15865 — All public YouTube videos require login](https://github.com/yt-dlp/yt-dlp/issues/15865)
- [yt-dlp #16221 — March 2026 "Sign in to confirm" breakage](https://github.com/yt-dlp/yt-dlp/issues/16221)
- [yt-dlp #13067 — YouTube bot detection issue](https://github.com/yt-dlp/yt-dlp/issues/13067)
- [yt-dlp #10128 — Sign in to confirm you're not a bot](https://github.com/yt-dlp/yt-dlp/issues/10128)
- [yt-dlp #1734 — Fix YouTube's autogenerated subtitles](https://github.com/yt-dlp/yt-dlp/issues/1734)
- [yt-dlp #5792 — Auto-translation subtitle leading blanks](https://github.com/yt-dlp/yt-dlp/issues/5792)
- [yt-dlp #11592 — yt-dlp with proxy not works on YouTube](https://github.com/yt-dlp/yt-dlp/issues/11592)
- [Bypassing the 2026 YouTube "Great Wall": yt-dlp + v2rayNG + SABR — dev.to](https://dev.to/ali_ibrahim/bypassing-the-2026-youtube-great-wall-a-guide-to-yt-dlp-v2rayng-and-sabr-blocks-1dk8)
- [How to Unblock YouTube in China (2026 Guide)](https://fastestvpn.com/resources/how-to-unblock-youtube-in-china/)
- [YouTube Blocked in China — BitJoy Global eSIM](https://thebitjoy.com/blogs/blog/youtube-blocked-in-china-what-travelers-need-to-know-before-you-go)
- [How to Download YouTube Subtitles 2026 — screenapp.io](https://screenapp.io/blog/download-youtube-subtitles-complete-guide)

**faster-whisper hallucinations:**
- [Investigation of Whisper ASR Hallucinations Induced by Non-Speech Audio (arXiv 2501.11378)](https://arxiv.org/html/2501.11378v1)
- [Calm-Whisper: Reduce Whisper Hallucination on Non-Speech (arXiv 2505.12969)](https://arxiv.org/html/2505.12969v1)
- [Solutions to Repeated Output Issues with Whisper — Memo AI](https://memo.ac/blog/whisper-hallucinations)
- [whisper.cpp #1724 — Hallucination on silence](https://github.com/ggml-org/whisper.cpp/issues/1724)

**pyannote diarization:**
- [pyannote/speaker-diarization-3.1 — Hugging Face](https://huggingface.co/pyannote/speaker-diarization-3.1)
- [Best Speaker Diarization Models Compared 2026 — Brass Transcripts](https://brasstranscripts.com/blog/speaker-diarization-models-comparison)
- [pyannote.ai community-1: open-source diarization](https://www.pyannote.ai/blog/community-1)

**Windows + ffmpeg + unicode subprocess:**
- [ffmpeg-python #90 — Fails on non-ASCII filename on Windows](https://github.com/kkroening/ffmpeg-python/issues/90)
- [ffmpeg-normalize #76 — handle utf8 character in Windows](https://github.com/slhck/ffmpeg-normalize/issues/76)
- [FFmpeg-devel — Unicode filenames support on Windows regression (2012)](https://ffmpeg.org/pipermail/ffmpeg-devel/2012-April/123449.html)
- [Variable Frame Rate — stoyanovgeorge ffmpeg wiki](https://github.com/stoyanovgeorge/ffmpeg/wiki/Variable-Frame-Rate)
- [trac.ffmpeg.org #10150 — Variable framerate with maximum value](https://trac.ffmpeg.org/ticket/10150)
- [How to Extract Time-Accurate Video Segments with FFmpeg — codestudy.net](https://www.codestudy.net/blog/how-to-extract-time-accurate-video-segments-with-ffmpeg/)

**Atomic-write Windows:**
- [Python bugs.python.org issue 8828 — Atomic function to rename a file](https://bugs.python.org/issue8828)
- [Hacker News — pain of atomic writing on Windows](https://news.ycombinator.com/item?id=16573770)

**Existing project (referenced not duplicated):**
- `.planning/codebase/CONCERNS.md` (§1.2, §1.4, §2.2, §2.5, §2.6, §2.7, §5.2, §5.4, §6.2, §6.3, §8.3, §9.1, §13.1)
- `.planning/codebase/INTEGRATIONS.md`
- `.planning/codebase/TESTING.md`

---
*Pitfalls research for: Claude-driven video-to-tutorial pipeline (¥0 local, brownfield expansion)*
*Researched: 2026-04-30*
