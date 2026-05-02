# Phase 6: Multi-Agent Parallelism (Nice-to-Have, ship-or-skip) - Context

**Gathered:** 2026-05-02
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase, /gsd-autonomous Claude 自决)

<domain>
## Phase Boundary

Make two Claude Code terminals on different videos safely concurrent. In scope:

- Vendor `vendor/douyin_api/.../config.yaml` write race closed via file lock
- Per-slug `output/<slug>/resume.lock` so concurrent runs on the same slug fail fast
- All `agent.tools` log lines prefixed with `[<slug>]` for grep-ability
- Cookies file (`www.douyin.com_cookies.txt`, `youtube_cookies.txt`) read once into memory cache
- CLAUDE.md documents the parallelism contract: per-slug isolation works; cross-slug concurrent transcribes are user's-risk for OOM unless serialized explicitly

Out of scope:

- Distributed locks (single-machine only — `fcntl` / `msvcrt.locking` is sufficient)
- Cross-process queue / scheduler (user invokes terminals manually)
- GPU memory budgeting (out of milestone v1.0)
- Lock-free async — synchronous fail-fast is the design

</domain>

<decisions>
## Implementation Decisions

### Locking strategy

- **Cross-platform file lock library:** Use Python stdlib only — `msvcrt.locking` on Windows + `fcntl.flock` on POSIX. Wrap in `agent/_lock.py` with a `FileLock(path, timeout=None)` context manager. Keep the dependency surface at zero new packages (consistent with Phase 4 silero-vad / Phase 5 pyannote opt-in pattern).
- **Vendor config.yaml lock:** Hold for the duration of the read-modify-write cycle inside the douyin source. Lock file at `vendor/douyin_api/.config.yaml.lock` (sibling, not the file itself, so the lock survives even if the yaml is rewritten atomically).
- **Per-slug resume.lock:** Hold for the duration of `transcribe` / `extract_frames_batch` / `aggregate` execution. Path: `output/<slug>/.resume.lock`. Stale-lock detection: write PID + ISO timestamp into the lock file; if a held lock's PID is dead, take it over. **Reason:** crash recovery — if Claude Code itself crashes mid-transcribe, the lock would otherwise be permanent.
- **Lock contention:** Default `timeout=0` (immediate fail with clean message `"slug locked by PID 12345 since 2026-05-02T08:00:00"`). User can override via `--wait` flag if they want to queue.

### Log prefix

- Single helper `_log(slug, msg)` in `agent/tools.py` (or extracted to `agent/_log.py` if it grows). Prefix format: `[BV132wiz] transcribe: ...` byte-equal across all subcommands.
- **Backward-compat:** Existing test suites that grep stderr/stdout MUST keep working. Strategy: prefix is added to NEW lines only; the underlying log content (everything after `: `) stays byte-equal. If any test asserts the leading `[` character, that's a real regression to flag.
- Slug derivation: read from `out_dir.name` (e.g., `output/BV132wizyEEB` → `BV132wizyEEB`). Same logic the rest of the codebase already uses.

### Cookies-in-memory

- Lazy single-load with module-level cache in `agent/sources/douyin.py` and `agent/sources/youtube.py`. First call reads from disk; subsequent calls return cached bytes. `--reload-cookies` CLI flag forces re-read for the case "I just re-exported cookies, please pick them up".
- **Concurrency:** The cache is process-local (each Claude Code terminal has its own Python process), so no cross-process sync needed. Within-process re-entrance is single-threaded so no lock needed there either.

### Doc contract in CLAUDE.md

- New section `## 多终端并行 (Phase 6)` placed after `## 环境变量（.env）` and before `---` / `## 视频类型变奏`. 1-screen length: explain per-slug isolation contract, state cross-slug OOM is user's-risk, recommend `nproc -1` rule of thumb for concurrent transcribes (faster-whisper is CPU-bound).
- Don't disturb existing 4 critical sections (抖音 / YouTube / Windows zh-CN / 决策支持) — they stay byte-equal.

### Plan partition (mirror ROADMAP)

- **Plan 06-01** — Locks (PARA-01 vendor config / PARA-02 per-slug / PARA-03 stale detection). Files: `agent/_lock.py` (NEW), `agent/sources/douyin.py` (vendor lock wrap), `agent/tools.py` (resume.lock wrap on transcribe/extract_frames_batch/aggregate). Wave 1.
- **Plan 06-02** — Slug-prefixed logs + cookies cache + CLAUDE.md docs (PARA-04/05/06). Files: `agent/tools.py` (log helper + apply across cmds), `agent/sources/douyin.py` + `agent/sources/youtube.py` (cookies cache), `CLAUDE.md` (parallelism contract section). Wave 2 (depends on 06-01 lock infrastructure for "concurrent terminals" smoke test).

### Testing

- New `tests/test_lock.py` — 6-8 unittest cases:
  - acquire / release happy path
  - timeout=0 contention raises clean error with PID + timestamp
  - stale PID lock takeover works
  - cross-platform smoke (skip POSIX-specific cases on Windows and vice versa)
  - resume.lock per-slug isolation: 2 different slugs lock independently
  - vendor config.yaml lock: write-modify-write under contention preserves yaml validity
- Concurrency real-world smoke: documented in SUMMARY (manual two-terminal test) — not asserted in CI because spawning 2 subprocesses with timing is flaky.

### Backward-compat (D-29 spirit, applied to v1.0 baseline)

- All 17 archived re-runs MUST stay byte-equal: aggregating / transcribing / extracting frames on existing baselines uses single-terminal mode → lock acquired → succeeds → released. No artifact diff.
- All `--help` outputs for the 5 core commands MUST exit 0 unchanged.

### Out of scope (deferred)

- GPU memory budgeting / scheduler
- Cross-machine / distributed lock
- Async / lock-free event loop
- Auto-queue when contended (user can chain `&&` themselves; we're not building a job system)

</decisions>

<code_context>
## Existing Code Insights

### Reusable assets

- `agent/sources/douyin.py` — already isolates vendor crawler invocation; lock wrap is a single context-manager addition around the config-write block
- `agent/tools.py` `_DOCTOR_ARTIFACTS` registry pattern — proven for adding new artifact types; resume.lock fits the same pattern
- `agent/silence.py` / `agent/diarize.py` opt-in lazy-import idiom — `agent/_lock.py` is NOT opt-in (it's mandatory infrastructure) but the module-level pattern is the same
- `agent/state.py` (Phase 4) — already does atomic JSON writes; resume.lock can sit beside it without conflict

### Established patterns

- Stdlib-only when possible (Phase 4 / Phase 5 both held this line — pyannote is opt-in for a reason)
- atomic write via tempfile + rename (already used; lock just wraps the read part)
- Each subcommand is its own `cmd_*` function in `agent/tools.py` — applies prefix logging at the call site, not as a global filter

### Integration points

- `cmd_download` (douyin path) → vendor config lock around the config.yaml read-modify-write
- `cmd_transcribe` / `cmd_extract_frames_batch` / `cmd_aggregate` → wrap entire body in `with FileLock(out_dir / ".resume.lock", timeout=0):`
- All `cmd_*` print statements → swap `print(...)` for `_log(slug, ...)` (slug derived from out_dir.name)

</code_context>

<specifics>
## Specific Ideas

No user-specified preferences — Claude 自决 per /gsd-autonomous user reply "继续完成". Refer to ROADMAP phase 6 success criteria as ground truth.

</specifics>

<deferred>
## Deferred Ideas

- GPU memory budget across concurrent transcribes — defer to milestone v2.0 if project goes that direction
- Auto-queue / job scheduler — out of "personal tool" scope per PROJECT.md
- Distributed lock for shared cloud workspace — same reason

</deferred>
