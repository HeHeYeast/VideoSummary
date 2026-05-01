---
phase: 03-source-refactor-new-sources-youtube-local-mp4-generic
plan: 02
subsystem: ingest
tags: [youtube, yt-dlp, preflight-classifier, gfw, sabr, po-token, https-proxy, subtitle-origin, version-staleness]

# Dependency graph
requires:
  - phase: 03-source-refactor-new-sources-youtube-local-mp4-generic
    plan: 01
    provides: Source Protocol + SOURCES list + agent/sources/_common.append_phase3_fields + cmd_ingest entry point
provides:
  - YouTubeSource class registered at SOURCES index 1 (between DouyinSource and BilibiliSource)
  - 5-class yt-dlp stderr classifier (po_token_required > cookies_stale > yt_dlp_outdated > gfw_blocked > other)
  - 5 locked Chinese hint strings from CONTEXT D-12 (verbatim)
  - HTTPS_PROXY > HTTP_PROXY env var forwarding via --proxy argv (Pitfall 3 — empty proxy never passed)
  - 2-second yt-dlp --simulate preflight; Windows timeout classified as gfw_blocked (Pitfall 4)
  - warn_if_yt_dlp_stale() helper — version drift warning at cmd_ingest startup; never auto-updates (D-15)
  - _detect_subtitle_origin returning creator/auto/none from yt-dlp info_dict
  - _extract_youtube_id covering watch?v= / youtu.be / shorts / embed URL forms
  - requirements.txt yt-dlp pin floor: >=2026.03.17 (D-16)
  - CLAUDE.md "## YouTube 支持（首次设置，可选）" section between 抖音 and Windows zh-CN sections
affects: [03-03-local-source, all future YouTube ingests]

# Tech tracking
tech-stack:
  added: []  # No new external deps; yt-dlp pin bumped only
  patterns:
    - "Two-stage YouTube fetch: subprocess --simulate preflight + Python API actual download"
    - "Most-specific-first regex classifier with locked Chinese hint dict"
    - "Lazy-import staleness check: cmd_ingest tolerates yt-dlp absence via try/except ImportError"
    - "Proxy URL redacted to host:port in logs (T-03-02-01); empty HTTPS_PROXY filtered with .strip() (T-03-02-03)"
    - "Windows subprocess timeout-as-gfw_blocked unification (Pitfall 4 — same actionable answer)"

key-files:
  created:
    - "agent/sources/youtube.py — YouTubeSource + classifier + preflight + version warn + subtitle origin"
  modified:
    - "agent/sources/__init__.py — insert YouTubeSource() at index 1; defensive ordering asserts updated"
    - "agent/tools.py — cmd_ingest gains warn_if_yt_dlp_stale lazy-imported call after work_dir.mkdir"
    - "requirements.txt — yt-dlp pin floor 2024.10.0 → 2026.03.17"
    - "CLAUDE.md — new ## YouTube 支持（首次设置，可选）section between 抖音 and Windows zh-CN"

key-decisions:
  - "Classifier ordering po_token_required FIRST (RESEARCH §Ordering Rationale): SABR videos co-emit 'Sign in to confirm' + 'PO Token'; PO Token is the actionable cause. Verified via _classify_stderr('Sign in to confirm. PO Token required.') == 'po_token_required'."
  - "gfw_blocked LAST among specific patterns: network errors are trailing symptoms of upstream issues; if a specific class matches we want it to win."
  - "Windows subprocess.TimeoutExpired classified as gfw_blocked (Pitfall 4): 2s timeout can extend to 8-15s wallclock on Windows due to non-SIGKILL terminate; same user-facing action ('set HTTPS_PROXY or fall back to local mp4') so unified."
  - "yt-dlp Python API used for actual download (NOT subprocess): preflight needs 5-class classification + cheap timeout, but real download needs info_dict for subtitle_origin extraction. Two binaries calling yt-dlp differently is fine — preflight is read-only on stderr; download produces sidecars."
  - "warn_if_yt_dlp_stale lazy-imported in cmd_ingest from agent.sources.youtube: the version helper conceptually belongs to the source most affected by yt-dlp drift; ImportError-tolerant so douyin-only ingests (which use vendor crawler) still work if yt-dlp is missing."
  - "Subtitle origin detector filters real_langs to {zh, zh-cn, zh-hans, zh-hant, en, ja, ko}: B站-style 'danmaku' entries appear in info_dict.subtitles but are comments not subs (RESEARCH §Subtitle Origin Extraction); whitelist avoids false 'creator' classification."
  - "Proxy URL redacted to host:port via urlparse before logging (T-03-02-01): credentials in HTTPS_PROXY (http://user:pass@proxy:7890) MUST NOT leak to logs; full URL never written, only hostname:port."
  - "_redacted_proxy_log returns None on parse failure (catches both ValueError and AttributeError): defensive against malformed env values; better silent log than crash on bogus user config."

requirements-completed: [SRC-05, SRC-06, SRC-07, SRC-08, SRC-13]

# Metrics
duration: ~10min
completed: 2026-05-01
---

# Phase 03 Plan 02: YouTubeSource + Preflight Classifier Summary

**YouTubeSource adds 2-second yt-dlp --simulate preflight with 5-class stderr classifier (po_token_required > cookies_stale > yt_dlp_outdated > gfw_blocked > other), HTTPS_PROXY forwarding, version-staleness warning, and subtitle_origin detection — turning "莫名其妙连不上" into actionable Chinese hints; requirements.txt pin bumped to yt-dlp>=2026.03.17 with Deno/yt-dlp-get-pot documented as opt-in only.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-01T10:17:00Z
- **Completed:** 2026-05-01T10:30:00Z
- **Tasks:** 2
- **Files created:** 1 (agent/sources/youtube.py)
- **Files modified:** 4 (agent/sources/__init__.py, agent/tools.py, requirements.txt, CLAUDE.md)

## Accomplishments

- New `agent/sources/youtube.py` (~289 lines): YouTubeSource class implementing the Source Protocol with preflight classifier + 5 LOCKED Chinese hints from CONTEXT D-12 verbatim
- Classifier patterns ORDERED most-specific-first per RESEARCH §"Ordering Rationale": po_token_required (SABR override) > cookies_stale > yt_dlp_outdated > gfw_blocked (last among specific) > other (fallback)
- `_build_yt_dlp_argv()` reads HTTPS_PROXY > HTTP_PROXY > unset; `.strip()` filters empty strings so we never pass `--proxy ""` (Pitfall 3)
- Windows `subprocess.TimeoutExpired` caught and classified as `gfw_blocked` (Pitfall 4 — same actionable answer)
- `warn_if_yt_dlp_stale(threshold_days=90)` parses `yt_dlp.version.__version__` (format `2026.03.17`) and warns if older than threshold; never auto-updates (D-15)
- `_detect_subtitle_origin()` filters info_dict to text-bearing langs (zh/zh-CN/zh-Hans/zh-Hant/en/ja/ko) to skip B站-style danmaku entries
- `_extract_youtube_id()` handles watch?v= / youtu.be / shorts / embed URL forms; falls back to `info_dict["id"]`
- YouTubeSource.fetch(): preflight first (subprocess) → on success use yt-dlp Python API (needs info_dict) → build legacy 7-key meta → append Phase 3 fields via `_common.append_phase3_fields`
- agent/sources/__init__.py: `SOURCES = [DouyinSource(), YouTubeSource(), BilibiliSource(), GenericSource()]`; defensive ordering assertions extended to enforce `youtube < generic`
- agent/tools.py:cmd_ingest gains lazy-imported `warn_if_yt_dlp_stale()` call after `work_dir.mkdir()`; ImportError-tolerant for environments without yt-dlp
- requirements.txt: `yt-dlp>=2024.10.0` → `yt-dlp>=2026.03.17` (D-16); Deno + yt-dlp-get-pot deliberately NOT pinned (opt-in only via CLAUDE.md)
- CLAUDE.md: new `## YouTube 支持（首次设置，可选）` section inserted between 抖音 setup section and Windows zh-CN section, mirroring 抖音 4-step pattern (proxy → cookies → opt-in PO Token tooling → verify)

## Task Commits

Each task committed atomically with `--no-verify` per parallel executor instruction:

1. **Task 1: agent/sources/youtube.py + __init__.py SOURCES update** — `1820411` (feat)
2. **Task 2: cmd_ingest staleness warning + requirements.txt pin + CLAUDE.md section** — `2a4e7ff` (feat)

**Plan metadata commit:** to be created with this SUMMARY.md by orchestrator.

## Files Created/Modified

### Created (1 new file)

- `agent/sources/youtube.py` (~289 lines): module docstring documents 5 failure modes + RESEARCH ordering rationale + Pitfall 4 wallclock disclosure
  - Module constants: `_PREFLIGHT_TIMEOUT_S = 2.0`, `_VERSION_DATE_RE`, `_CATEGORY_PATTERNS` (4 specific + 'other' fallback), `_HINTS` (5 LOCKED D-12 strings)
  - Module functions: `_classify_stderr`, `_build_yt_dlp_argv`, `_redacted_proxy_log`, `youtube_preflight`, `_yt_dlp_release_date`, `warn_if_yt_dlp_stale`, `_extract_youtube_id`, `_detect_subtitle_origin`
  - `class YouTubeSource`: `name="youtube"`, `_PATTERN` matching youtube.com/youtu.be (+ www./m./music. subdomains), `match()` + `fetch()`

### Modified (4 files)

- `agent/sources/__init__.py`:
  - Added `from agent.sources.youtube import YouTubeSource` at top
  - SOURCES list: inserted `YouTubeSource()` at index 1 (between Douyin and Bilibili — most-specific position)
  - 2 new defensive assertions: `"youtube" in _SEEN_NAMES` + `_SEEN_NAMES.index("youtube") < _SEEN_NAMES.index("generic")`
- `agent/tools.py`:
  - cmd_ingest (lines 100-107): inserted lazy import + `warn_if_yt_dlp_stale()` call right after `work_dir.mkdir()` and before the started `_emit_event`. ImportError-tolerant.
- `requirements.txt`:
  - line 2: `yt-dlp>=2024.10.0` → `yt-dlp>=2026.03.17`
- `CLAUDE.md`:
  - 32 lines inserted between line 39 (抖音 vendor crawler note) and line 41 (Windows zh-CN heading)
  - Heading: `## YouTube 支持（首次设置，可选）`
  - 4-step setup mirroring 抖音 pattern: HTTPS_PROXY config (PowerShell + permanent variants) → cookies export → opt-in Deno + yt-dlp-get-pot install → verification command
  - Section closes with 5-class failure-class reference + LocalSource fallback advisory + SOURCES ordering invariant footnote

## Decisions Made

1. **Classifier ordering po_token_required FIRST.** SABR videos co-emit "Sign in to confirm you are not a bot" AND "PO Token required" simultaneously. If we put cookies_stale first, users would re-export cookies fruitlessly. PO Token is the actionable cause for SABR — verified via test `_classify_stderr('Sign in to confirm. PO Token required.') == 'po_token_required'`. Order: `po_token_required > cookies_stale > yt_dlp_outdated > gfw_blocked > other`.

2. **Windows subprocess.TimeoutExpired = gfw_blocked.** RESEARCH Pitfall 4 documents `proc.kill()` not being SIGKILL on Windows; 2s timeout can extend to 8-15s wallclock. Both slow-network-but-completes (Connection timed out caught by gfw_blocked regex) and TimeoutExpired (preflight took >2s) point to the same user action: "set HTTPS_PROXY or fall back to local mp4". Unified to `gfw_blocked` for clean UX.

3. **yt-dlp Python API for actual download (NOT subprocess).** Preflight uses subprocess for cheap 2s --simulate + classifier-friendly stderr. Actual download uses `yt_dlp.YoutubeDL(opts).extract_info(url, download=True)` because we need `info_dict` for subtitle_origin detection. Two yt-dlp invocations is fine — preflight is read-only stderr; download produces video.mp4 + .vtt + .info.json sidecars.

4. **warn_if_yt_dlp_stale lives in agent/sources/youtube.py.** Conceptually it's a yt-dlp helper, but YouTubeSource is the source most affected by yt-dlp drift (B站/抖音's downloader.py path is more stable). Lazy-imported from cmd_ingest with `try/except ImportError` so douyin-only ingests still work if yt-dlp is missing or pinned out.

5. **Subtitle origin lang whitelist.** Filters to `{zh, zh-cn, zh-hans, zh-hant, en, ja, ko}` because B站 yt-dlp returns "danmaku" (弹幕 = comments) under `info_dict.subtitles` which would otherwise be misclassified as creator subtitles. RESEARCH §"Subtitle Origin Extraction" documents this failure mode.

6. **Proxy URL redaction.** `_redacted_proxy_log()` returns `host:port` via `urlparse` (no credentials). Threat T-03-02-01 prevents leaking `http://user:pass@proxy:7890` to logs. Returns `None` on parse failure (defensive against malformed env values; better silent log than crash).

7. **Empty HTTPS_PROXY filtered with `.strip()`.** Threat T-03-02-03 / Pitfall 3: yt-dlp interprets `--proxy ""` ambiguously and may emit "Unable to download webpage" misclassified as gfw_blocked when the user actually meant "no proxy". `.strip() or None` collapses empty/whitespace to falsy; `if proxy:` then conditionally appends `--proxy <value>` argv.

8. **Deno + yt-dlp-get-pot opt-in only.** D-16 explicitly forbids them in requirements.txt (Deno is a winget install on Windows; Python users on Linux would need separate `deno install`). Documented in CLAUDE.md step 3 with `winget install DenoLand.Deno && pip install yt-dlp-get-pot` for the subset of SABR videos that hard-require PO Tokens.

9. **CLAUDE.md insertion includes forward reference to LocalSource.** The trailing blockquote mentions `DouyinSource → YouTubeSource → BilibiliSource → LocalSource → GenericSource`. LocalSource is plan 03-03 territory but documenting the full target SOURCES order now gives the user the complete mental model — one less round trip when 03-03 lands.

## Deviations from Plan

**[Rule 2 - Missing critical functionality] Acceptance criteria substring `首次设置 YouTube` not literally in section body.**

- **Found during:** Task 2 verification (plan-level grep -F "首次设置 YouTube" CLAUDE.md must match)
- **Issue:** The plan's example section heading is `## YouTube 支持（首次设置，可选）` which contains "首次设置" then "可选" — the literal substring "首次设置 YouTube" never appears. The plan also requires the substring in an acceptance check.
- **Fix:** Added a one-line blockquote summary BELOW the heading: `> 首次设置 YouTube ingest 时按本节配置；不需要 YouTube 直接抓取的话，跳过本节，直接用本地 mp4 兜底（见末尾）。` This satisfies the acceptance grep without altering the heading text or section structure.
- **Files modified:** CLAUDE.md
- **Commit:** `2a4e7ff` (Task 2 commit, includes this addition)
- **Rationale:** Acceptance criteria explicitly grep for `首次设置 YouTube` substring. Adding a contextually-natural blockquote that mentions "首次设置 YouTube ingest 时按本节配置" is the minimal change to satisfy both the heading template (`## YouTube 支持（首次设置，可选）`) AND the acceptance grep. Otherwise the user would need to manually scan whether the section is "the right one" — explicit is better.

## Issues Encountered

- **Worktree path mismatch on initial Write:** First Write of `agent/sources/youtube.py` and Edit of `agent/sources/__init__.py` landed in the parent repo (`D:\gxy_code\videoSummary\agent\sources\`) instead of the worktree (`D:\gxy_code\videoSummary\.claude\worktrees\agent-a1a24245fd0715e80\agent\sources\`). Detected via Python import test failing with FileNotFoundError. Fixed by `cp` from parent → worktree, then `git checkout` + `rm` to revert parent repo. All subsequent edits explicitly used the worktree absolute path. No data lost; no commits affected.
- **READ-BEFORE-EDIT hook fired on each new file path:** Each first edit to a worktree file triggered a "you must Read this file first" reminder. The hook accepts that the same logical file (e.g. `__init__.py`) was Read at the parent path; reads at the worktree path additionally satisfy the hook for subsequent edits. Re-Read on each path was the workaround.

## Live Test Status

**Live YouTube ingest NOT attempted in this execution** per environment_note in the executor prompt: "Live YouTube preflight (2s yt-dlp --simulate) won't run during execution — acceptance criteria use offline assertions on the classifier function, not actual network calls. So no GFW issues during execute."

User-side verification path (post-execution, when user wants to actually try a YouTube URL):

1. `python -m agent.tools ingest "https://www.youtube.com/watch?v=<id>" --out output/test_yt`
2. Without HTTPS_PROXY set on a zh-CN Windows host, expect `RuntimeError: YouTube ingest failed [gfw_blocked]: GFW 阻断；export HTTPS_PROXY=...` — that's the EXPECTED CONTEXT D-13 behavior.
3. Set HTTPS_PROXY per CLAUDE.md step 1, retry. If preflight passes, actual yt-dlp download proceeds.
4. If a video requires PO Token (SABR rollout), expect `[po_token_required]` classification; install Deno + yt-dlp-get-pot per CLAUDE.md step 3 to recover.

## User Setup Required

For YouTube ingests to succeed, follow the new CLAUDE.md `## YouTube 支持（首次设置，可选）` section:

1. **HTTPS_PROXY** — required to bypass GFW
2. **YouTube cookies** — recommended (re-export when stale)
3. **Deno + yt-dlp-get-pot** — opt-in, only for SABR videos that hard-require PO Tokens

If any link in the chain fails, the 5-class classifier prints a localized hint pointing to the corrective step. Final fallback (per LocalSource in plan 03-03): manually download the video via browser/IDM and run `python -m agent.tools ingest "D:\videos\local.mp4" --out output/xxx`.

## Next Phase Readiness

**Ready for plan 03-03 (LocalSource + ffprobe preflight + -vsync vfr unification):**

- Insertion point for `LocalSource()` in SOURCES: between `BilibiliSource()` and `GenericSource()` (just before sentinel). Defensive ordering assertion pattern already established at agent/sources/__init__.py — copy the existing 2-line block.
- ffprobe preflight per CONTEXT D-21 will append `codec` / `container` / `fps_mode` fields to meta.json — `_common.append_phase3_fields` is positional-arg friendly; LocalSource can extend it OR cmd_ingest can do post-fetch ffprobe in a uniform place (CONTEXT Discretion).
- CJK rejection per D-19 to be added at cmd_ingest entry (only checks `args.out`, not input path) before `work_dir.mkdir()`. Suggest: `if re.search(r"[一-鿿]", str(args.out)): raise ValueError(...)`. Place BEFORE `warn_if_yt_dlp_stale` call.
- `-vsync vfr` per D-23 will modify cmd_extract_frames ffmpeg argv — separate from this YouTube plan but on the 03-03 task list.

**Ready for `/summarize-video` workflow:**

- YouTube URLs now route to YouTubeSource — no behavioral change to B站/抖音.
- New CLAUDE.md "YouTube 支持" section is opt-in; existing 抖音 + Windows zh-CN sections preserved verbatim.
- requirements.txt `pip install -r requirements.txt` will pull yt-dlp 2026.03.17+ on next install (existing installs unaffected unless user re-installs).

## Threat Flags

None — threats T-03-02-01 through T-03-02-06 from the plan threat model are all mitigated in code:

- **T-03-02-01 (proxy creds leak):** `_redacted_proxy_log()` returns `host:port` via urlparse; full URL never logged.
- **T-03-02-02 (URL injection):** `subprocess.run([list], shell=False)` — list-form argv, URL is positional element.
- **T-03-02-03 (empty --proxy ''):** `.strip()` filters whitespace; `if proxy:` conditionally appends.
- **T-03-02-04 (Windows timeout 2-15s):** documented in YouTubeSource.fetch docstring; classified as gfw_blocked (same action).
- **T-03-02-05 (auto-update):** `warn_if_yt_dlp_stale` only logs; no `pip install` ever invoked from code.
- **T-03-02-06 (stderr leak):** `_HINTS["other"]` truncates to `stderr[:200]` head before raising.

No new persistent secrets stored; all env vars read on-demand via `os.environ.get`.

## Self-Check: PASSED

**Files created (verified via worktree git status + ls):**
- FOUND: agent/sources/youtube.py (289 lines)

**Files modified (verified via `git diff --stat HEAD~2 HEAD`):**
- FOUND: agent/sources/__init__.py (+9 −2)
- FOUND: agent/tools.py (+9)
- FOUND: requirements.txt (+1 −1)
- FOUND: CLAUDE.md (+36)

**Commits (verified via `git log --oneline`):**
- FOUND: 1820411 feat(03-02): add YouTubeSource with 5-class preflight classifier
- FOUND: 2a4e7ff feat(03-02): wire yt-dlp staleness warning + bump pin + add YouTube setup docs

**Acceptance criteria (verified via plan-level verification block):**
- SOURCES order = ['douyin', 'youtube', 'bilibili', 'generic']: VERIFIED
- youtube routing (youtube.com / youtu.be / m. / music.): VERIFIED
- All 4 D-12 locked Chinese hints byte-exact via grep -F: VERIFIED
- Regex order po_token_required < cookies_stale < yt_dlp_outdated < gfw_blocked: VERIFIED (1763 < 1948 < 2107 < 2331)
- requirements.txt yt-dlp>=2026.03.17: VERIFIED
- requirements.txt does NOT contain Deno or yt-dlp-get-pot: VERIFIED
- CLAUDE.md "首次设置 YouTube" substring + "## YouTube 支持（首次设置，可选）" header: VERIFIED
- CLAUDE.md insertion order (douyin_end < youtube < windows_zh_cn): VERIFIED
- cmd_ingest source contains warn_if_yt_dlp_stale: VERIFIED
- agent/douyin_downloader.py + src/download.py + vendor/ + tests/regression/ UNCHANGED: VERIFIED via empty `git diff HEAD~2 HEAD --` for those paths
- Classifier offline assertions (5 stderr inputs → 5 categories + SABR override): VERIFIED
- Subtitle origin (creator/auto/none + danmaku-as-none edge case): VERIFIED
- youtube_id extraction (4 URL forms): VERIFIED

---

*Phase: 03-source-refactor-new-sources-youtube-local-mp4-generic*
*Plan: 02*
*Completed: 2026-05-01*
