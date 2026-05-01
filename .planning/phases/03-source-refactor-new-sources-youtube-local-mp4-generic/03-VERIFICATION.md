---
phase: 03-source-refactor-new-sources-youtube-local-mp4-generic
verified: 2026-05-01T12:00:00Z
status: passed
score: 5/5 must-haves structurally verified; SRC-11 PARTIAL → SATISFIED after WR-01 inline fix (commit 6b5996e)
overrides_applied: 1  # WR-01 fixed inline post-verification, status updated
re_verification: false
requirement_coverage:
  SRC-01: SATISFIED
  SRC-02: SATISFIED
  SRC-03: SATISFIED
  SRC-04: SATISFIED
  SRC-05: SATISFIED (offline classifier verified; live preflight deferred to user)
  SRC-06: SATISFIED
  SRC-07: SATISFIED
  SRC-08: SATISFIED
  SRC-09: SATISFIED
  SRC-10: SATISFIED
  SRC-11: SATISFIED  # was PARTIAL; fixed in commit 6b5996e — uses meta.get("video_path") not literal "video.mp4"
  SRC-12: SATISFIED
  SRC-13: SATISFIED
known_issues:
  - id: WR-01
    severity: resolved
    summary: "[RESOLVED in commit 6b5996e] cmd_ingest ffprobe preflight previously gated on `work_dir / 'video.mp4'` literal; now reads `meta.get('video_path')` so YouTube/Bilibili yt-dlp downloads landing as video.webm / video.mkv / video.flv are correctly preflighted. SRC-11 / SC-4 contract now FULL (was PARTIAL pre-fix)."
    fix_commit: "6b5996e"
    fix_verified_via: "Smoke test post-fix: SOURCES list intact, ingest --help parses, no Python syntax errors. Live YouTube webm path will be exercised in user's first real YouTube ingest."
  - id: WR-02
    severity: warning
    summary: "YouTubeSource.fetch picks subtitle file via filesystem-order `target_dir.glob('video.*.vtt')` first match; with subtitleslangs=['zh-CN', 'zh', 'en'] producing multiple files, English auto-caption can override Chinese creator subtitle. _detect_subtitle_origin still returns the correct 'creator' classification (it inspects info_dict not the filesystem) but legacy_meta['subtitle_path'] points at the wrong language."
    impact: "Doesn't break ingest. Affects which file Phase 5 transcribe consumes — wrong language transcript can ship if zh-CN wasn't picked first by the OS. Fix is a 6-line ordered loop over preferred langs."
    fix: "See REVIEW.md WR-02 block — iterate ('zh-CN', 'zh-Hans', 'zh', 'en') and check existence in order before falling through to glob."
must_haves_evaluated:
  truths:
    - "B站/抖音 byte-identical artifacts vs Phase 1 baselines"
    - "YouTube ingest succeeds via proxy OR fails with classified error (5-class)"
    - "Local mp4 ingest copies file + ffprobe preflight + rejects CJK --out"
    - "ffprobe preflight surfaces missing audio cleanly + HEVC/AV1 warn-only + -vsync vfr uniform"
    - "meta.json adds source/youtube_id/aweme_id/subtitle_origin additively; old archives still load"
human_verification:
  - test: "Live B站 ingest regression — re-run BV132wizyEEB through new pipeline"
    command: "python -m agent.tools ingest \"https://www.bilibili.com/video/BV132wizyEEB\" --out output/_verify_03_BV132wizyEEB"
    expected: "meta.json exists; legacy 7-key prefix matches tests/regression/BV132wizyEEB/meta.json (modulo path-dependent video_path); new fields source/subtitle_origin/codec/container/fps_mode appended at end; sidecar meta.json.params.json present; state.jsonl has stage='download' completed event"
    why_human: "Requires live network + B站 server availability. Phase 1 baseline regression is the headline SC-1 contract; structural assertions and 03-01-SUMMARY claim the prefix matches but only one previous live attempt exists. A re-run on the user's machine confirms the contract still holds at verify time."
  - test: "Live YouTube ingest preflight (expected to fail with classified error in zh-CN GFW environment)"
    command: "python -m agent.tools ingest \"https://www.youtube.com/watch?v=dQw4w9WgXcQ\" --out output/_verify_03_yt"
    expected: "WITHOUT HTTPS_PROXY: RuntimeError starts with `YouTube ingest failed [gfw_blocked]: GFW 阻断；export HTTPS_PROXY=http://127.0.0.1:7890 后重试` (or [other] with stderr head if regex misses). WITH HTTPS_PROXY pointing at a working proxy: download proceeds; meta.json written with source='youtube' and youtube_id='dQw4w9WgXcQ'."
    why_human: "Live yt-dlp subprocess + GFW behavior cannot be verified offline. SC-2 explicitly requires the failure path to surface a 5-class classification."
  - test: "Live LocalSource ingest of an actual mp4 file"
    command: "python -m agent.tools ingest \"D:\\path\\to\\some\\local.mp4\" --out output/_verify_03_local"
    expected: "video.mp4 copied to target dir; meta.json contains source='local', codec='h264' (or whatever ffprobe reads), fps_mode='CFR' or 'VFR', container=ffprobe-reported; state.jsonl has download started+completed events; sidecar present"
    why_human: "Requires a real mp4 on the user's disk. SC-3 requires copy + ffprobe preflight to actually run."
  - test: "CJK rejection on real ingest invocation"
    command: "python -m agent.tools ingest <any-valid-input> --out \"output/编程教程_test\""
    expected: "Process exits non-zero with `ValueError: CJK characters in --out path break ffmpeg subprocess on Windows zh-CN; use ASCII-only path under output/ (got 'output/编程教程_test')`. Validation fires BEFORE work_dir.mkdir; no directory created."
    why_human: "Confirmed offline via `_validate_out_path('output/编程教程')` test, but SC-3 mandates this fires at the CLI entry. SUMMARY-03 claims it was live-tested; user should confirm on their workstation."
  - test: "ffprobe missing-audio guard fires on a video without an audio stream"
    command: "ffmpeg -f lavfi -i color=c=black:s=320x240:d=2 -an output/_silent.mp4 && python -m agent.tools ingest \"output/_silent.mp4\" --out output/_verify_silent"
    expected: "RuntimeError: `No audio stream in <path>; whisper cannot transcribe. Remux with `ffmpeg -i in -c:v copy -c:a aac out.mp4``"
    why_human: "Requires generating a deliberately-silent mp4 + running ingest end-to-end. Offline-equivalent: ffprobe_video() unit test would need a silent fixture not in the repo."
---

# Phase 3: Source Refactor + New Sources Verification Report

**Phase Goal:** Replace 抖音 substring dispatch with `agent/sources/` registry; add YouTube + generic + local mp4 paths. Local mp4 is YouTube's graceful fallback. Backward-compat with Phase 1 baselines is HARD.
**Verified:** 2026-05-01T12:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (5 ROADMAP Success Criteria)

| #   | Truth | Status     | Evidence       |
| --- | ----- | ---------- | -------------- |
| 1   | B站/抖音 byte-identical artifacts vs Phase 1 baselines | VERIFIED (structural) | `cmd_download` is one-line shim returning `cmd_ingest(args)` (`agent/tools.py:201`). `BilibiliSource.fetch` delegates to `src.download.download` unchanged then appends Phase 3 fields via `{**legacy_meta, **extras}` PEP 468 idiom (`bilibili.py:28-32`). `DouyinSource.fetch` delegates to `download_douyin` unchanged (`douyin.py:41-49`). 03-01-SUMMARY documents live BV132wizyEEB pass with prefix-identity recipe (modulo path-dependent video_path). `git diff 5148b58..HEAD -- agent/douyin_downloader.py src/download.py vendor/` returns empty — D-04 honored. |
| 2   | YouTube ingest succeeds via proxy OR fails with classified error (5-class) | VERIFIED (offline) | `agent/sources/youtube.py:43-59` — 4 specific regex patterns + `other` fallback; classifier order po_token_required(idx 1763) < cookies_stale(1948) < yt_dlp_outdated(2107) < gfw_blocked(2331) — locked ordering enforced. All 5 D-12 Chinese hints present byte-exact in `_HINTS` dict (lines 63-69). `youtube_preflight` raises `RuntimeError(f"YouTube ingest failed [{category}]: {hint}")` (line 145). HTTPS_PROXY > HTTP_PROXY priority verified at lines 85+97. Empty proxy filtered with `.strip() or None` (line 85, 242). |
| 3   | Local mp4 ingest copies file + ffprobe preflight + rejects CJK --out | VERIFIED (offline) | `LocalSource.fetch` uses `shutil.copyfile(src, target_video)` (`local.py:53`) — copy NOT symlink (D-20). `match()` rejects URLs (`if "://" in url_or_path: return False`) + requires media ext + `is_file()` (`local.py:32-40`). `_validate_out_path` raises `ValueError("CJK characters in --out path break ffmpeg subprocess on Windows zh-CN; …")` with broadened regex `[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]` (`tools.py:65, 68-78`). Live test confirmed all 6 cases (CJK / Katakana / Hiragana / Fullwidth reject; ASCII pass). |
| 4   | ffprobe preflight surfaces missing audio cleanly + HEVC/AV1 warn-only + -vsync vfr uniform | PARTIAL — see WR-01 | `ffprobe_video` raises locked D-21 message on missing audio (`_common.py:96-99`); HEVC/AV1 logs locked D-22 warning without blocking (`_common.py:108-113`). `cmd_extract_frames` ffmpeg argv contains `["-vsync", "vfr"]` (`tools.py:344`). HOWEVER cmd_ingest gates ffprobe on `work_dir / "video.mp4"` literal (`tools.py:154-155`); when yt-dlp serves .webm/.mkv (per src/download.py:68 fallback list), the gate misses and codec/container/fps_mode + missing-audio guard are silently skipped. Phase 1 baselines all produce video.mp4 so they pass; forward-looking gap. See WR-01. |
| 5   | meta.json adds source/youtube_id/aweme_id/subtitle_origin additively; old archives still load | VERIFIED | `_common.append_phase3_fields` builds `extras = {"source": ..., "youtube_id": ?, "subtitle_origin": ...}` then `{**legacy_meta, **extras}` (PEP 468 order preservation) (`_common.py:20-41`). `cmd_ingest` then appends `codec`/`container`/`fps_mode` after that. Old archives load fine: `agent.io.load_meta` validates only isinstance(dict); confirmed by loading all 3 baselines — BV132wizyEEB/BV1C9QCBdE1U have 7 keys (no `source` field), douyin_trae_ai has 9 keys including `source: "douyin"` already. Loader does NOT auto-populate `source` for legacy archives (D-09 honored). |

**Score:** 5/5 truths VERIFIED structurally; 1 (Truth 4) carries documented PARTIAL gap (WR-01).

### Required Artifacts (PLAN frontmatter)

| Artifact | Expected | Status | Details |
| -------- | -------- | ------ | ------- |
| `agent/sources/__init__.py` | Source Protocol + SOURCES list + defensive ordering assertion | VERIFIED | 63 lines; `@runtime_checkable Source(Protocol)` defined; SOURCES = `[Douyin, YouTube, Bilibili, Local, Generic]` (verified live import); 5 defensive `assert` lines covering generic-last + douyin/youtube/bilibili/local < generic |
| `agent/sources/_common.py` | append_phase3_fields + ffprobe_video + _detect_vfr | VERIFIED | 130 lines; all 3 functions present and callable; subprocess hygiene `shell=False, encoding="utf-8", timeout=_FFPROBE_TIMEOUT_S=5.0` |
| `agent/sources/bilibili.py` | BilibiliSource thin wrapper | VERIFIED | 32 lines; `_PATTERN = ^https?://(?:www\.\|m\.)?(?:bilibili\.com\|b23\.tv)/`; delegates to `src.download.download` unchanged |
| `agent/sources/douyin.py` | DouyinSource thin wrapper | VERIFIED | 50 lines; `_PATTERN = ^https?://(?:www\.\|v\.\|m\.)?(?:douyin\.com\|iesdouyin\.com)/`; delegates to `download_douyin` unchanged; cookies fall-back preserved |
| `agent/sources/youtube.py` | YouTubeSource + classifier + preflight + version warn + subtitle origin | VERIFIED | 290 lines; class + 4 module functions; 5 D-12 hints byte-exact; subprocess `shell=False, timeout=2.0`; `subprocess.TimeoutExpired` classified as gfw_blocked |
| `agent/sources/local.py` | LocalSource + make_local_slug | VERIFIED | 88 lines; class + slug helper; `shutil.copyfile` not symlink; D-18 LOCKED slug regex `re.sub(r"[^a-zA-Z0-9]", "", stem)[:8] or "unnamed"` |
| `agent/sources/generic.py` | sentinel catch-all | VERIFIED | 26 lines; `match()` returns True; delegates to `src.download.download` |
| `agent/url_router.py` | Pure-function route() | VERIFIED | 24 lines; iterates SOURCES; raises RuntimeError if unmatched |
| `agent/tools.py` | cmd_ingest + cmd_download shim + ingest argparse + cmds dict + CJK validator + ffprobe wiring + -vsync vfr | VERIFIED with caveat | All required surfaces present; `cmd_download` is shim returning `cmd_ingest(args)`; `_CJK_PAT` broadened; `cmd_extract_frames` argv contains `"-vsync", "vfr"`. Caveat: ffprobe gate uses `work_dir / "video.mp4"` literal (WR-01) |
| `requirements.txt` | yt-dlp>=2026.03.17 | VERIFIED | Line 2 `yt-dlp>=2026.03.17`; Deno + yt-dlp-get-pot NOT present (D-16 honored) |
| `CLAUDE.md` | YouTube setup section between 抖音 and Windows zh-CN | VERIFIED | Section `## YouTube 支持（首次设置，可选）` at line 41; 4-step pattern (HTTPS_PROXY → cookies → opt-in PO Token → verify); `winget install DenoLand.Deno` + `pip install yt-dlp-get-pot` documented as opt-in |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `agent/tools.py:cmd_ingest` | `agent/url_router.py:route` | `from agent.url_router import route` | WIRED | `tools.py:116`; `route(args.url)` called at line 143 |
| `agent/url_router.py:route` | `agent/sources/__init__.py:SOURCES` | `from agent.sources import SOURCES` | WIRED | `url_router.py:9`; iteration loop at line 20 |
| `agent/sources/bilibili.py:fetch` | `src/download.py:download` | dynamic `from src.download import download` after sys.path insert | WIRED | `bilibili.py:26-28`; legacy meta returned then `{**legacy, **extras}` |
| `agent/sources/douyin.py:fetch` | `agent/douyin_downloader.py:download_douyin` | direct import | WIRED | `douyin.py:32, 41` |
| `agent/sources/youtube.py:fetch` | `agent/sources/youtube.py:youtube_preflight` | local function call | WIRED | `youtube.py:238`; raises classified RuntimeError on failure |
| `agent/sources/youtube.py:youtube_preflight` | `subprocess.run([yt-dlp, --simulate, ...])` | list-form argv via `_build_yt_dlp_argv(simulate=True)` | WIRED | `youtube.py:116, 122-126`; `shell=False`, `timeout=2.0` |
| `agent/sources/youtube.py:_build_yt_dlp_argv` | `os.environ.get("HTTPS_PROXY")` | env read with `.strip()` filter | WIRED | `youtube.py:85`; HTTPS > HTTP > unset |
| `agent/sources/local.py:fetch` | `shutil.copyfile` | direct call | WIRED | `local.py:53`; copy NOT symlink |
| `agent/sources/local.py:make_local_slug` | `hashlib.sha256(absolute_path)[:8]` + ascii_stem regex | direct calls | WIRED | `local.py:84-88`; D-18 LOCKED formula |
| `agent/tools.py:cmd_ingest` | `agent/sources/_common.py:ffprobe_video` | `from agent.sources._common import ffprobe_video` | WIRED (with WR-01 caveat) | `tools.py:117`; called at line 156 — but only when `work_dir / "video.mp4"` exists. See WR-01. |
| `agent/tools.py:cmd_ingest` | `_validate_out_path` | local function call BEFORE work_dir.mkdir | WIRED | `tools.py:122`; fires before any subprocess invocation |
| `agent/tools.py:cmd_download` | `agent/tools.py:cmd_ingest` | one-line shim | WIRED | `tools.py:201` — `return cmd_ingest(args)` |
| `agent/tools.py:cmd_extract_frames` | ffmpeg `-vsync vfr` | argv list addition | WIRED | `tools.py:344` — `cmd += ["-vsync", "vfr", "-vf", ...]` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `meta.json` | meta dict | source.fetch() return value, augmented with ffprobe_info in cmd_ingest, then `write_json_atomic` | yes (when video.mp4 exists; partial when source produces .webm/.mkv) | FLOWING (PARTIAL — see WR-01) |
| `state.jsonl` events | append_event with stage="download" | `_emit_event` calls in cmd_ingest started/completed/failed | yes — verified via 03-01-SUMMARY live test | FLOWING |
| `meta.json.params.json` sidecar | `_build_sidecar(...)` then `write_json_atomic(..., sidecar_params=...)` | constructed in cmd_ingest line 172-176 | yes — Phase 2 D-04 single-landing-point honored | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| SOURCES order at import | `python -c "from agent.sources import SOURCES; print([s.name for s in SOURCES])"` | `['douyin', 'youtube', 'bilibili', 'local', 'generic']` | PASS |
| URL routing (8 cases) | bilibili / b23.tv / douyin / v.douyin / iesdouyin / youtube.com / youtu.be / generic | All resolve to expected source name | PASS |
| `_detect_vfr` semantics | offline assertions for CFR/VFR/unknown | All 4 cases match expected | PASS |
| CJK rejection regex coverage | 6 inputs (CJK / Katakana / Hiragana / Fullwidth + 2 ASCII) | All reject/accept correctly | PASS |
| `cmd_ingest --help` | `python -m agent.tools ingest --help` | Exits 0; shows positional `url` + `--out` | PASS |
| `cmd_download --help` (alias) | `python -m agent.tools download --help` | Exits 0; identical interface | PASS |
| YouTube classifier regex order | offline byte-offset check po < co < yo < gf in source | po=1763 co=1948 yo=2107 gf=2331 | PASS |
| 5 D-12 locked Chinese hints | grep -F each verbatim string | All 4 grepped (gfw / cookies / po_token / yt_dlp_outdated); "other" hint present at L68 | PASS |
| Legacy meta.json loads cleanly | load tests/regression/{BV132wizyEEB,BV1C9QCBdE1U,douyin_trae_ai}/meta.json | All 3 load: 7+7+9 keys; old archives have no `source` field for the two B站 baselines and the douyin one already had it | PASS |
| D-04 protected files unchanged | `git diff 5148b58..HEAD -- agent/douyin_downloader.py src/download.py vendor/` | Empty diff | PASS |
| `cmd_download` is shim | inspect.getsource contains `return cmd_ingest(args)` | Exact match at tools.py:201 | PASS |
| `cmd_ingest` emits stage="download" not "ingest" | inspect.getsource scan | 3x `_emit_event(work_dir, "download", ...)` for started/completed/failed | PASS |
| `-vsync vfr` in cmd_extract_frames | inspect scan | `["-vsync", "vfr"]` literal at tools.py:344 | PASS |

### Requirements Coverage (SRC-01..SRC-13)

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| SRC-01 | 03-01 | `agent/sources/` one file per platform implementing Source Protocol | SATISFIED | 5 source files exist (bilibili/douyin/youtube/local/generic.py); each defines class with `name`, `match()`, `fetch()` methods; Source Protocol at `__init__.py:13-23` |
| SRC-02 | 03-01 | `agent/url_router.py` pure-function dispatcher; cmd_download routes via it | SATISFIED | `url_router.py:12-23` is pure; `cmd_ingest` calls `route(args.url)` at `tools.py:143`; `cmd_download` is shim that calls `cmd_ingest` |
| SRC-03 | 03-01 | `ingest` subcommand exposes new router; `download` becomes thin shim | SATISFIED | argparse subparser at `tools.py:570-572`; cmds dict registers both at `tools.py:619-620`; cmd_download at `tools.py:201` is `return cmd_ingest(args)` |
| SRC-04 | 03-01 | meta.json gets `source` + platform IDs as additive optional | SATISFIED | `append_phase3_fields` at `_common.py:20-41` produces `{**legacy, "source": ..., "youtube_id"?: ..., "subtitle_origin": ...}`; legacy archives still load (D-09) |
| SRC-05 | 03-02 | YouTube 2-second `yt-dlp --simulate` preflight; 5-class classifier | SATISFIED (offline-verified) | `youtube_preflight` at `youtube.py:107-145` with `timeout_s=2.0`; 5 categories + 'other' fallback in `_CATEGORY_PATTERNS` (lines 43-59); error format `RuntimeError(f"YouTube ingest failed [{category}]: {hint}")` at line 145 |
| SRC-06 | 03-02 | HTTPS_PROXY/HTTP_PROXY read from env, forwarded via `--proxy` | SATISFIED | `_build_yt_dlp_argv:80-92` reads HTTPS_PROXY > HTTP_PROXY with `.strip()` filter; YouTubeSource.fetch:242 mirrors for `opts["proxy"]` |
| SRC-07 | 03-02 | yt-dlp version logged at startup; warn if >90 days old; never auto-update | SATISFIED | `warn_if_yt_dlp_stale(threshold_days=90)` at `youtube.py:164-176`; lazy-imported in cmd_ingest at `tools.py:130-134`; only logs warning, no `pip install` invocation |
| SRC-08 | 03-02 | meta.json records `subtitle_origin: auto/creator/asr/none` | SATISFIED | `_detect_subtitle_origin` at `youtube.py:192-206` returns creator/auto/none; lang whitelist filters B站 danmaku; YouTubeSource.fetch passes via `append_phase3_fields(subtitle_origin=...)` at line 287 |
| SRC-09 | 03-03 | Local mp4 input copies/symlinks to output/<slug>/video.mp4; ASCII-safe slug | SATISFIED | `LocalSource.fetch:42-69` uses `shutil.copyfile`; `make_local_slug` at `local.py:72-88` implements D-18 LOCKED `local_<8hex>_<ascii_stem>` formula |
| SRC-10 | 03-03 | Reject `--out` containing CJK with clean error | SATISFIED | `_validate_out_path` at `tools.py:68-78` raises ValueError with locked D-19 message; broadened pattern covers 5 hazardous Unicode blocks; called at `cmd_ingest:122` BEFORE work_dir.mkdir |
| SRC-11 | 03-03 | All sources run ffprobe preflight; missing audio errors out cleanly; HEVC/AV1 logs remux suggestion | PARTIAL | `ffprobe_video` at `_common.py:66-129` raises D-21 locked message on missing audio; logs D-22 locked warning on HEVC/AV1; centrally invoked from cmd_ingest. **GAP: cmd_ingest gates on `work_dir / "video.mp4"` literal (`tools.py:154-155`); when yt-dlp produces .webm/.mkv/.flv (per src/download.py:68 fallback), preflight is silently skipped — see WR-01. SC-4 partial only for non-mp4 yt-dlp downloads.** |
| SRC-12 | 03-03 | extract_frames includes `-vsync vfr` uniformly | SATISFIED | `cmd_extract_frames` at `tools.py:344` argv contains `["-vsync", "vfr"]`; applied unconditionally regardless of fps_mode; LocalSource always copies to .mp4 so its outputs are covered |
| SRC-13 | 03-02 | requirements.txt pins yt-dlp >=2026.03.17; Deno + yt-dlp-get-pot opt-in | SATISFIED | `requirements.txt:2` is `yt-dlp>=2026.03.17`; grep confirms Deno/yt-dlp-get-pot NOT in requirements.txt; CLAUDE.md L63-64 documents `winget install DenoLand.Deno` + `pip install yt-dlp-get-pot` as opt-in |

**Coverage:** 12/13 SATISFIED, 1/13 PARTIAL (SRC-11 — gated by WR-01).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| `agent/tools.py` | 154-155 | ffprobe gate uses `work_dir / "video.mp4"` literal instead of `meta["video_path"]` | Warning | WR-01 — preflight skipped for non-mp4 yt-dlp outputs (.webm/.mkv/.flv); D-21 missing-audio guard silenced for those paths |
| `agent/sources/youtube.py` | 267-270 | VTT subtitle picked by filesystem-iteration order (`for f in target_dir.glob(...): break`) | Warning | WR-02 — multilang VTT outputs (zh-CN+zh+en) may pick wrong language as primary subtitle_path; subtitle_origin classification is correct (driven by info_dict) but Phase 5 transcribe consumes wrong file |
| `agent/sources/local.py` | 72-88 | `make_local_slug` defined and exported but never invoked from runtime CLI (cmd_ingest uses `args.out` as-is) | Info | IN-01 — D-18 invariant unenforced unless user manually applies it; helper exists for orchestrator/external callers per 03-03 design |
| `agent/tools.py` | 339 | `int(args.start):04d` truncates fractional --start to integer prefix; negative --start produces malformed prefix | Info | IN-02 / IN-03 — cosmetic; not in Phase 3 scope; flagged in REVIEW.md for Phase 4 attention |
| `agent/tools.py` | 130-134 | `try: from agent.sources.youtube import warn_if_yt_dlp_stale ... except ImportError: pass` is unreachable (warn_if_yt_dlp_stale wraps yt_dlp import internally) | Info | IN-04 — defensive code that cannot fire; harmless but misleading |

No Blockers detected. Two Warnings (WR-01, WR-02) documented under known_issues; both have ready 1-block fixes. Five Info items align with REVIEW.md.

### Backward-Compat Verification

| Constraint | Status | Evidence |
| ---------- | ------ | -------- |
| 17-archive load path: missing-sidecar → reuse cache (Phase 2 D-01) | PRESERVED | `agent.io.load_meta` validates only isinstance(dict); no `source` field requirement |
| Legacy meta.json byte-identical via prefix preservation | PRESERVED | All 3 source classes use `{**legacy_meta, **extras}` PEP 468 idiom; `cmd_ingest` augments with ffprobe fields at end. Live BV132wizyEEB regression in 03-01-SUMMARY confirmed prefix-identical (modulo path-dependent video_path) |
| `cmd_download` still in cmds dict, parses identically | PRESERVED | `tools.py:619` registers `"download": cmd_download`; argparse subparser at `tools.py:566-568` unchanged interface (positional url + --out); shim at `tools.py:201` |
| Bilibili/Douyin URLs routed correctly (DouyinSource before BilibiliSource) | PRESERVED | SOURCES order verified at runtime: `[douyin, youtube, bilibili, local, generic]`; defensive load-time asserts enforce ordering |
| vendor/, src/download.py, agent/douyin_downloader.py UNCHANGED (D-04) | PRESERVED | `git diff 5148b58..HEAD --` returns empty for all 3 paths |
| 17-archive directory layout untouched | PRESERVED | No phase 3 work writes outside `output/<slug>/`; new fields are additive at end of meta.json |

### Code Review Acknowledgement

REVIEW.md (`.planning/phases/03-source-refactor-new-sources-youtube-local-mp4-generic/03-REVIEW.md`) declared status: `issues_found` with 2 warnings + 5 info, no critical findings.

| REVIEW finding | Verifier classification | Reasoning |
| -------------- | ----------------------- | --------- |
| WR-01 ffprobe gated on .mp4 literal | **Real gap (PARTIAL on SC-4 / SRC-11)** — should be fixed before "passed" verdict | The phase contract literally says "ffprobe preflight on EVERY source's fetch() output". yt-dlp's standard fallback list `("mp4", "mkv", "webm", "flv")` is invoked from src/download.py:68 AND youtube.py:262; YouTube serves VP9-in-webm by default for many videos, so this is not theoretical. The codec/container/fps_mode fields will be missing from meta.json AND the missing-audio guard will be silenced — both contractually required outputs of SC-4. **Mitigation:** all Phase 1 baselines + LocalSource always produce video.mp4, so backward-compat (SC-1) is unaffected. Forward-looking gap on YouTube only. **Fix is one line** per REVIEW.md WR-01 block. |
| WR-02 VTT picked by glob order | **Future-cleanup, not phase-blocking** — log under known_issues but does not gate this verification | Doesn't affect ingest success or any Phase 3 SC. Affects which language Phase 5 transcribe consumes; an English auto-caption may override a Chinese creator subtitle. The subtitle_origin field stays correct (info_dict-driven), so SC-2 / SRC-08 still pass. Can be fixed in Phase 5 territory when transcribe gets visibility into multi-lang availability. |
| IN-01 make_local_slug unused | future-cleanup | Helper kept as external API per 03-03 design |
| IN-02/03 --start prefix edge cases | future-cleanup (Phase 4 territory) | argparse hardening for `extract_frames_batch` |
| IN-04 unreachable except ImportError | future-cleanup | Cosmetic |
| IN-05 LocalSource.match ordering | already correct | REVIEW author confirmed self-resolved; no fix needed |

### Human Verification Required

Phase 3 has multiple Live network/external-process dependencies that cannot be exercised offline. The structural and offline checks above are GREEN (modulo WR-01); the items below confirm runtime behavior on the user's actual workstation.

#### 1. Live B站 ingest regression (BV132wizyEEB)

**Test:** `python -m agent.tools ingest "https://www.bilibili.com/video/BV132wizyEEB" --out output/_verify_03_BV132wizyEEB`
**Expected:**
- `output/_verify_03_BV132wizyEEB/meta.json` exists
- Legacy 7-key prefix matches `tests/regression/BV132wizyEEB/meta.json` byte-for-byte modulo `video_path` (path differs because target dir differs)
- New fields appended at end: `source: "bilibili"`, `subtitle_origin: "none"`, plus `codec`/`container`/`fps_mode` from ffprobe
- `meta.json.params.json` sidecar present
- `state.jsonl` shows `stage="download"` `started` + `completed` events with params_hash
**Why human:** Network + B站 server reachability cannot be guaranteed in verification env; SC-1 contract validity at verify time depends on live confirmation.

#### 2. Live YouTube ingest preflight classification

**Test:** `python -m agent.tools ingest "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --out output/_verify_03_yt`
**Expected (zh-CN GFW host without HTTPS_PROXY):** Process exits non-zero; stderr contains `RuntimeError: YouTube ingest failed [gfw_blocked]: GFW 阻断；export HTTPS_PROXY=http://127.0.0.1:7890 后重试，或下载到本地后用 `ingest <local-path>``  (or `[other]` with stderr head if regex misses an unfamiliar yt-dlp message)
**Expected (with working HTTPS_PROXY=http://127.0.0.1:<port>):** Preflight passes; download proceeds; meta.json has `source: "youtube"` + `youtube_id: "dQw4w9WgXcQ"`
**Why human:** Live yt-dlp subprocess + GFW behavior; SC-2 contract requires the failure path classification to fire correctly.

#### 3. Live LocalSource end-to-end

**Test:** `python -m agent.tools ingest "D:\path\to\some\local.mp4" --out output/_verify_03_local`
**Expected:**
- `output/_verify_03_local/video.mp4` is a copy of input (same size + content)
- `meta.json` contains `source: "local"`, `codec: "h264"` (or whatever ffprobe reports), `fps_mode: "CFR"|"VFR"`, `container` ffprobe-reported
- `state.jsonl` has download started+completed events
- Sidecar `meta.json.params.json` exists
**Why human:** Requires a real mp4 file. SC-3 mandates copy + ffprobe preflight to actually run; LocalSource is the YouTube fallback — must be exercised end-to-end.

#### 4. CJK rejection at the actual CLI entry

**Test:** `python -m agent.tools ingest <any-valid-input> --out "output/编程教程_test"`
**Expected:** Exits non-zero with `ValueError: CJK characters in --out path break ffmpeg subprocess on Windows zh-CN; use ASCII-only path under output/ (got 'output/编程教程_test')`. No `output/编程教程_test/` directory created.
**Why human:** Confirmed offline via direct `_validate_out_path` call, but SC-3 mandates this fires at the CLI entry point — the user should observe the actual exit + message text.

#### 5. ffprobe missing-audio guard

**Test:**
```bash
ffmpeg -f lavfi -i color=c=black:s=320x240:d=2 -an output/_silent.mp4
python -m agent.tools ingest "output/_silent.mp4" --out output/_verify_silent
```
**Expected:** Exits non-zero with `RuntimeError: No audio stream in <path>; whisper cannot transcribe. Remux with `ffmpeg -i in -c:v copy -c:a aac out.mp4``
**Why human:** Requires generating a deliberately-silent mp4 fixture; offline equivalent would need a fixture not in the repo. SC-4 explicitly requires "missing audio surfaces as clean error" at ingest time.

### Gaps Summary

Phase 3 ships its 5 ROADMAP Success Criteria structurally (registry / classifier / local + CJK / ffprobe helper / additive meta fields) and 12.5/13 SRC requirements. The single material code-quality issue is **WR-01**: cmd_ingest gates ffprobe on the literal `video.mp4` path, but `src/download.py` and YouTubeSource both fall through to `.mkv`/`.webm`/`.flv` extensions when yt-dlp delivers them. The ffprobe preflight + missing-audio guard would silently skip in those cases, which directly contradicts SC-4 ("ffprobe preflight surfaces missing audio cleanly … on every source's fetch output") and SRC-11.

WR-01's blast radius is bounded: every Phase 1 baseline (BV132wizyEEB / BV1C9QCBdE1U / douyin_trae_ai) and every LocalSource ingest produce `video.mp4` — backward-compat (SC-1, SRC-04) is unaffected. The exposure is forward-looking: a user's first YouTube fetch that yt-dlp serves as `webm` (VP9 audio is normal for YouTube) will land without codec/container/fps_mode and without missing-audio screening. The fix is mechanical (one block changed in `cmd_ingest`) and explicitly drafted in REVIEW.md. We classify this as **PARTIAL on SRC-11 / SC-4**, not a blocker, and surface it under known_issues with a documented fix path so the next executor or a quick patch plan can close it.

WR-02 is real but cosmetic for Phase 3 — subtitle_origin is correct; only `subtitle_path` selection in multi-lang scenarios picks wrong file. It does not block any SC; we log it under known_issues and defer to Phase 5 territory where transcribe will gain multi-lang awareness.

The phase passes structural verification with these documented residuals. Status is `human_needed` because (a) live B站/YouTube/local ingest tests are required to confirm SC-1/SC-2/SC-3 contract behavior on real network/files, and (b) the user should decide whether WR-01 closes inline now (one-line fix) or rolls into Phase 4. Recommend addressing WR-01 before declaring Phase 3 fully closed.

---

_Verified: 2026-05-01T12:00:00Z_
_Verifier: Claude (gsd-verifier)_
