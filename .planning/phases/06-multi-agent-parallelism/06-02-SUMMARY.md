---
phase: 06-multi-agent-parallelism
plan: 02
subsystem: multi-terminal-ergonomics
tags: [phase-6, para-04, para-05, para-06, slug-prefix-logs, cookies-cache, claude-md-docs]
dependency_graph:
  requires:
    - agent/_lock.py (Phase 6 plan 01 — referenced from CLAUDE.md docs section)
    - agent/tools.py (Phase 2/4/5 — module-level FileLock import added by 06-01)
    - agent/sources/douyin.py (Phase 3 — DouyinSource.fetch signature)
    - agent/sources/youtube.py (Phase 3 — YouTubeSource.fetch signature)
    - agent/douyin_downloader.py (Phase 3 — download_douyin signature; 06-01 added vendor lock)
    - CLAUDE.md (Phase 5 anchor: ## 环境变量（.env） + ## 视频类型变奏 anchor stable)
  provides:
    - "agent/tools.py: _log(slug, cmd, msg) helper printing '[<slug>] <cmd>: <msg>'"
    - "agent/sources/douyin.py: _COOKIES_CACHE + _read_cookies_cached(reload=False)"
    - "agent/sources/youtube.py: _COOKIES_CACHE placeholder dict (symmetry)"
    - "agent/douyin_downloader.py: download_douyin(cookies_text=...) kwarg + _cookies_text_to_header"
    - "agent/tools.py: --reload-cookies CLI flag on download + ingest"
    - "CLAUDE.md: ## 多终端并行 (Phase 6) section between ## 环境变量 and ## 视频类型变奏"
  affects:
    - cmd_transcribe / cmd_aggregate / cmd_extract_frames / cmd_extract_frames_batch /
      cmd_diarize / cmd_cleanup_frames / cmd_detect_scenes / cmd_detect_silence — status
      lines now prefixed
    - cmd_ingest / cmd_download — argparse exposes --reload-cookies (forward to source.fetch via TypeError fallback)
tech_stack:
  added: []
  patterns:
    - "Stdlib-only print() for slug-prefixed status lines (separate from logging.INFO format)"
    - "Lazy module-level dict cache for cookies (process-local; no cross-process sync)"
    - "**kwargs threading via try/except TypeError for forward-compat across heterogeneous source signatures"
    - "Helper-extraction refactor (cookies parser): file-path takes string-content delegation"
key_files:
  created:
    - tests/test_log_prefix_and_cookies_cache.py
    - .planning/phases/06-multi-agent-parallelism/06-02-SUMMARY.md
  modified:
    - agent/tools.py (_log helper + 8 cmd_* prefix applications + --reload-cookies argparse + cmd_ingest TypeError fallback)
    - agent/sources/douyin.py (_COOKIES_CACHE + _read_cookies_cached + reload_cookies kwarg in fetch)
    - agent/sources/youtube.py (_COOKIES_CACHE placeholder)
    - agent/douyin_downloader.py (cookies_text kwarg + _cookies_text_to_header refactor)
    - CLAUDE.md (## 多终端并行 (Phase 6) section, ~50 lines)
decisions:
  - "_log goes to stdout via print() (not logging.info) to avoid 'INFO | ' double-format and stay greppable as-is"
  - "Status lines prefixed in 8 cmds (long-running pipeline stages); JSON dump + ASCII table + read-only helpers + interactive prompts intentionally NOT prefixed"
  - "Cookies cache is process-local (D-46) — no cross-process sync needed; each Claude Code terminal = own Python process = own cache"
  - "Cache invalidation only via --reload-cookies flag (no automatic mtime-checking — that would silently re-read and defeat the cache)"
  - "YouTube _COOKIES_CACHE is a no-op placeholder; YouTube uses yt-dlp browser-cookie auto-discovery, not a single file we read directly"
  - "TypeError fallback in cmd_ingest threading reload_cookies — only DouyinSource implements PARA-05 cache today; other sources silently drop the kwarg"
  - "_cookies_txt_to_header retained for backward-compat (delegates to _cookies_text_to_header); CLI invocation `python -m agent.douyin_downloader` still works"
  - "CLAUDE.md section anchored AFTER ## 环境变量 and BEFORE the --- separator that precedes ## 视频类型变奏 (per CONTEXT D-49 placement spec)"
metrics:
  duration_min: 8
  completed_at: "2026-05-02T18:00:00+08:00"
  commits: 4
  tasks: 3
  tests_added: 11
  tests_passing: 91  # 1 skipped (POSIX-branch on Windows host)
  lines_added_log_prefix: 60  # net +60 in agent/tools.py for _log + 8 cmd applications + slug derivations
  lines_added_cookies_cache: 49  # douyin.py +28 + youtube.py +9 + downloader.py +12
  lines_added_argparse_flag: 15  # --reload-cookies on download + ingest + TypeError fallback in cmd_ingest
  lines_added_claude_md: 48
  lines_added_tests: 217
requirements:
  - PARA-04
  - PARA-05
  - PARA-06
---

# Phase 6 Plan 02: User-Facing Layer Summary

Slug-prefixed status logs, cookies-in-memory cache + `--reload-cookies` flag, and the
CLAUDE.md `## 多终端并行 (Phase 6)` documentation contract complete the Phase 6 user-
facing layer on top of plan 01's lock infrastructure.

## What Shipped

**1. `_log(slug, cmd, msg)` helper in `agent/tools.py`** — prints `[<slug>] <cmd>: <msg>`
to stdout via `print()` (not `logging.info`) so the line is greppable without
competing with the `INFO | ...` log format. Backward-compat: prefix is added at the
front; the underlying msg content stays byte-equal after `: ` separator.

**2. Slug-prefix applied to 8 long-running cmd handlers** — the cmds that emit status
lines for tail-able multi-terminal output:

| cmd | Status lines prefixed | Slug derivation |
|-----|----------------------|-----------------|
| `transcribe` | 4 (cached/segments/time/output) | `out_dir.name` |
| `aggregate` | 4 (cached / N segs→M paras x2 / output) | `state_dir.name` (= out.parent.name) |
| `extract_frames` | 1 (extracted N frames) | `out_dir.parent.name` |
| `extract_frames_batch` | 2 (per-segment SKIP + per-segment @ fps) | `state_dir.name` (= out_dir.parent.name) |
| `diarize` | 3 (turns/speakers/output) | `out_dir.name` |
| `cleanup_frames` | 1 (removed/kept) | `state_dir.name` (= dir.parent.name) |
| `detect_scenes` | 2 (detected/output) | `Path(args.out).parent.name` |
| `detect_silence` | 3 (Found/When writing.../output) | `Path(args.out).parent.name` |

**Intentionally NOT prefixed** (per acceptance discretion documented in plan + CONTEXT D-41):

| cmd | Why not prefixed |
|-----|------------------|
| `ingest` / `download` JSON dump | Structured artifact for jq/parsers; prefix would break parsing |
| `doctor` ASCII table | Multi-line block; first row already names slug; prefixing every row hurts readability |
| `list_frames` | Read-only helper, not a pipeline stage |
| `classify_frame` / `ocr_frame` | Backup single-frame diagnostic tools |
| `diarize` 60min CPU gate WARNING + interactive `(y/N)` | Interactive prompt, not status — prefix breaks dialog UX |
| Per-frame iteration lines in `extract_frames` (e.g. `  [<ts>] <fname>`) | List iteration under the prefixed status header |
| `_emit_repetition_warnings` lines | Multi-line cohesive warning block |

**3. `_COOKIES_CACHE` + `_read_cookies_cached(reload=False)` in `agent/sources/douyin.py`** —
lazy module-level dict keyed by absolute resolved path. First call reads from disk
into memory; subsequent calls return cached bytes. `reload=True` invalidates the
entry and re-reads. `_COOKIES_CACHE` placeholder also added to `agent/sources/youtube.py`
for cross-source symmetry (YouTube uses yt-dlp browser-cookie auto-discovery, not
a file we read directly — placeholder is the cache key store for any future change).

**4. `download_douyin(cookies_text=...)` kwarg + `_cookies_text_to_header` refactor**
in `agent/douyin_downloader.py` — caller passes pre-read cookies content (string)
instead of a file path. Old `cookies_file` path retained as backward-compat shim
that delegates to `_cookies_text_to_header(Path(cookies_file).read_text(...))`.
Direct module CLI invocation `python -m agent.douyin_downloader` still works.

**5. `--reload-cookies` CLI flag on `download` + `ingest` argparse** in
`agent/tools.py`. Threaded into `cmd_ingest` via `fetch_kwargs` + `try/except TypeError`
fallback so sources whose `fetch()` doesn't declare `reload_cookies` (Bilibili /
Local / Generic / YouTube today) silently drop the kwarg without breaking. Only
`DouyinSource.fetch()` accepts it currently.

**6. `## 多终端并行 (Phase 6)` section in `CLAUDE.md`** — placed AFTER `## 环境变量（.env）`
(line 148) and BEFORE the `---` separator (now line 200) that precedes
`## 视频类型变奏` (line 202). 5 subsections, ~48 lines:

- **锁住了什么** — vendor `config.yaml` + per-slug `.resume.lock` + intentional
  non-locks (extract_frames / download / detect_* / doctor / diarize)
- **per-slug isolation vs 跨 slug 并发** — 5-row table covering same/different
  slug × same/different stage combinations, with OOM as user's-risk for
  cross-slug concurrent transcribes
- **实操规则 (faster-whisper CPU-bound)** — `nproc - 1` rule for CPU,
  single-card 1-slot for GPU, kill/wait/no-rm guidance for stale locks
- **Cookies 缓存 (PARA-05)** — per-process cache + `--reload-cookies` invalidation
- **日志格式 (PARA-04)** — which cmds are prefixed + which intentionally aren't

**4+1 critical sections preserved byte-equal** in their stable signatures
(verified by `TestClaudeMdDocs.test_3b_critical_sections_intact`):

- `## 抖音支持（首次设置）` → signature: `抖音 URL 的下载链路和 B 站不同`
- `## YouTube 支持（首次设置，可选）` → signature: `ingest 时会自动按 HTTPS_PROXY > HTTP_PROXY`
- `## Pyannote diarization 设置（首次设置，可选）` → signature: `pyannote`
- `## Windows zh-CN 终端设置（推荐）` → signature: `chcp 65001`
- `## 决策支持工具（Phase 4，可选）` → signature: `PySceneDetect`

**7. `tests/test_log_prefix_and_cookies_cache.py` — 11 unittest cases**

| Class | Test | What it verifies |
|------|------|------------------|
| TestLogPrefix | `test_3e_helper_format` | `_log("BVtest","transcribe","segments: 42")` → `[BVtest] transcribe: segments: 42` |
| TestLogPrefix | `test_3e_aggregate_status_prefixed` | `cmd_aggregate` status lines start with `[BVtest] aggregate: ` |
| TestLogPrefix | `test_3e_existing_substring_preserved` | `cmd_detect_silence` source still contains `FPS-04` (test_silence::test_5 still passes) |
| TestCookiesCache | `test_3f_cached_on_second_call` | `Path.read_text` called exactly once across 2 `_read_cookies_cached` calls |
| TestCookiesCache | `test_3g_reload_forces_re_read` | `reload=True` invalidates cache → `Path.read_text` called twice |
| TestCookiesCache | `test_3f_different_paths_separate_entries` | 2 unique paths → 2 reads (each path's first call); 3rd & 4th repeat calls hit cache |
| TestCookiesCache | `test_youtube_cache_module_attr_exists` | `agent.sources.youtube._COOKIES_CACHE` exists as `dict` |
| TestClaudeMdDocs | `test_3a_new_section_exists` | `## 多终端并行 (Phase 6)` heading appears exactly once |
| TestClaudeMdDocs | `test_3c_placement` | line(`## 环境变量`) < line(`## 多终端并行`) < line(`## 视频类型变奏`) |
| TestClaudeMdDocs | `test_3d_section_mentions_contract_terms` | new section contains `per-slug isolation`, `OOM`, `nproc`, `.resume.lock`, `vendor` |
| TestClaudeMdDocs | `test_3b_critical_sections_intact` | 4+1 critical sections present + stable signatures byte-equal |

Run: `python -m unittest tests.test_log_prefix_and_cookies_cache -v`
Result: 11 tests, all pass on Windows host.

## Concurrency Model

Cache is **process-local**. Each Claude Code terminal has its own Python
process so no cross-process sync needed (CONTEXT D-46). Within-process
re-entrance is single-threaded so no lock needed there either. Two terminals
running `download` on different abetting slugs each have their own
`_COOKIES_CACHE` dict — no cross-pollution.

Vendor `config.yaml` patching is still serialized via `FileLock` (Phase 6
plan 01) at `vendor/douyin_api/crawlers/douyin/web/.config.yaml.lock` —
the cache change does NOT relax the lock contract; it only avoids
re-reading the cookies file inside the locked region on every invocation.

## Backward-compat (D-29 spirit applied to v1.0 baseline)

- All 17 archived re-runs MUST stay byte-equal in artifact bytes:
  `transcribe` / `aggregate` / `extract_frames_batch` write the same
  segs.json / paragraphs.json / frame files as before. Only stdout adds
  the `[<slug>] <cmd>: ` prefix at the front of status lines; the
  underlying msg content (e.g., `"FPS-04"` substring) stays byte-equal.
- Existing `python -m agent.tools transcribe --help` etc. all exit 0
  unchanged. New `--reload-cookies` flag is additive on `download` +
  `ingest`.
- `python -m agent.douyin_downloader <url> <out_dir> [cookies_file]`
  CLI invocation still works (the `cookies_file` path arg is preserved
  as backward-compat shim; `_cookies_txt_to_header` delegates to the
  new `_cookies_text_to_header` after reading the file).
- 91 tests across 8 suites pass (test_state, test_silence, test_lock,
  test_repetition_guard, test_extract_frames_batch, test_scenes,
  test_scheduler, test_log_prefix_and_cookies_cache). 1 skipped is the
  POSIX-branch test in test_lock on Windows host (platform-correct).

## Two-terminal manual smoke (referenced from CLAUDE.md docs section)

Per CONTEXT D-Testing line 67 — concurrency real-world smoke is documented
but NOT asserted in CI. The CLAUDE.md `## 多终端并行 (Phase 6)` section
is the user-facing equivalent.

**Same-slug contention (expected: B fails fast):** still works exactly
as documented in plan 06-01 (`LockContended: FileLock: ...`).

**Different-slug parallelism (expected: both succeed + greppable):**
two terminals, each with its own slug. Combined `tail -f`:

```text
[BVxxx] transcribe: segments: 132
[BVyyy] transcribe: segments: 87
[BVxxx] transcribe: time: 0.0s - 245.3s
[BVyyy] transcribe: time: 0.0s - 158.1s
```

Filter by slug: `tail -f /tmp/all.log | grep '\[BVxxx\]'`.

**Vendor config.yaml race + cookies cache:** two simultaneous
`download <douyin-url>` on different slugs both serialize the
`config.yaml` patch. Each process's first call reads
`www.douyin.com_cookies.txt` into its own `_COOKIES_CACHE`; subsequent
calls (e.g., re-trying after stale cookies) within the same process
hit the cache. `--reload-cookies` flag forces a re-read after manual
re-export of cookies.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — Bug] Section heading capitalization broke the `per-slug isolation` test assertion**

- **Found during:** Task 3 first test run after writing CLAUDE.md section
- **Issue:** I wrote `### Per-slug isolation vs 跨 slug 并发` (capitalized) as
  the subsection heading, but `test_3d_section_mentions_contract_terms`
  asserts the literal lowercase substring `per-slug isolation` (the actual
  contract phrase from CONTEXT D-50). The capitalized heading didn't satisfy
  the literal-substring grep.
- **Fix:** Lowercased the heading to `### per-slug isolation vs 跨 slug 并发`
  AND added an inline sentence below it:
  `下表说明 per-slug isolation 的具体边界——同 slug 强制串行...` so the
  contract phrase appears both in heading and in body text. Better
  documentation outcome — the heading itself names the contract.
- **Files modified:** `CLAUDE.md` (subsection heading + 1 added sentence)
- **Commit:** `e4c478f` (folded into the docs commit; not a separate commit
  since the test was authored in the same task as the docs)
- **Verification:** All 11 TestClaudeMdDocs cases pass.

### Auth Gates

None — Phase 6 plan 02 is pure-stdlib + local-file infrastructure; no
external API, secrets, or network calls.

## Threat Flags

None — no new network endpoints, no new auth paths, no schema changes
at trust boundaries. The cookies-in-memory cache holds the same bytes
as the file on disk, in process memory, for the lifetime of the Python
process. Same exposure surface as the existing `read_text` path; we
just hold the bytes longer (T-06-02-01 disposition `accept` per plan).

## Self-Check: PASSED

**Files exist:**
- `tests/test_log_prefix_and_cookies_cache.py` — FOUND (217 lines, ≥100 ✓)
- `agent/tools.py` — MODIFIED (_log helper + 8 cmd_* prefix applications + --reload-cookies argparse)
- `agent/sources/douyin.py` — MODIFIED (_COOKIES_CACHE + _read_cookies_cached + reload_cookies kwarg)
- `agent/sources/youtube.py` — MODIFIED (_COOKIES_CACHE placeholder)
- `agent/douyin_downloader.py` — MODIFIED (cookies_text kwarg + _cookies_text_to_header)
- `CLAUDE.md` — MODIFIED (## 多终端并行 (Phase 6) section, 48 lines)
- `.planning/phases/06-multi-agent-parallelism/06-02-SUMMARY.md` — FOUND (this file)

**Commits exist:**
- `2d6bcdb` — FOUND (test(06-02): add failing tests for log prefix + cookies cache + CLAUDE.md docs)
- `8694b81` — FOUND (feat(06-02): add _log slug-prefix helper + apply to 8 cmd_* status lines)
- `df8601b` — FOUND (feat(06-02): add cookies-in-memory cache + --reload-cookies CLI flag)
- `e4c478f` — FOUND (docs(06-02): add ## 多终端并行 (Phase 6) section to CLAUDE.md)

**Acceptance criteria from PLAN.md success_criteria:**
- [x] `_log(slug, cmd, msg)` helper exists in agent/tools.py (1 def + 20 call sites)
- [x] Applied to status-line prints in 8 cmds (transcribe, aggregate, extract_frames, extract_frames_batch, diarize, cleanup_frames, detect_scenes, detect_silence)
- [x] `_COOKIES_CACHE` dict + `_read_cookies_cached` helper in agent/sources/douyin.py with reload kwarg
- [x] `_COOKIES_CACHE` placeholder dict in agent/sources/youtube.py
- [x] `download_douyin` accepts `cookies_text` kwarg (pre-read content) alongside backward-compat `cookies_file` path
- [x] `--reload-cookies` flag wired through `download` and `ingest` argparse subparsers + threaded into source.fetch via try/except TypeError fallback
- [x] CLAUDE.md has new `## 多终端并行 (Phase 6)` section between `## 环境变量（.env）` and `## 视频类型变奏` (line 152, between 148 and 202)
- [x] CLAUDE.md 4+1 critical sections (抖音 / YouTube / Pyannote / Windows zh-CN / 决策支持) byte-equal in stable signatures (test 3b)
- [x] `tests/test_log_prefix_and_cookies_cache.py` ≥5 tests (11 actual), all pass
- [x] `python -m unittest tests.test_lock tests.test_state tests.test_silence` still passes (no regression of plan 06-01 + earlier-phase tests — 27 tests)
- [x] All 5 core CLI commands still expose --help and exit 0 (download/ingest now also expose --reload-cookies)

## Phase 6 Milestone Close-out

PARA-01..06 all green. Phase 6 ships:

- **Plan 06-01** (Wave 1): Lock infrastructure (PARA-01/02/03) — `agent/_lock.py` +
  vendor config.yaml lock + per-slug resume.lock + 9 unittest cases
- **Plan 06-02** (Wave 2, this plan): User-facing layer (PARA-04/05/06) —
  slug-prefix logs + cookies-in-memory cache + `--reload-cookies` flag + CLAUDE.md
  parallelism contract + 11 unittest cases

**Total Phase 6 metrics:**
- 4 modified source files + 2 new infrastructure files (`_lock.py` + `test_lock.py`)
  + 1 new test file (`test_log_prefix_and_cookies_cache.py`) + 1 modified docs file
- 20 unittest cases added (9 lock + 11 prefix/cache/docs)
- 91 total tests pass (1 skipped on Windows host — POSIX branch)

Recommend `/gsd-verify-phase 6` next.
