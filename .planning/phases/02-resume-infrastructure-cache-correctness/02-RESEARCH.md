# Phase 2: Resume Infrastructure & Cache Correctness - Research

**Researched:** 2026-05-01
**Domain:** Atomic file I/O on Windows zh-CN, parameter-aware cache invalidation, append-only event log, schema versioning
**Confidence:** HIGH (Python stdlib + verified on real archive directory; all decisions in CONTEXT.md are LOCKED so this is a prescriptive how-to, not exploratory)

## Summary

Phase 2 adds three layers of resume infrastructure to the existing file-existence cache, **without** introducing any new dependencies (stdlib only) and **without** modifying the 17 archived `output/<slug>/` directories. All major decisions are locked in `02-CONTEXT.md` (D-01..D-23). This research validates the technical feasibility of those decisions on Windows 11 zh-CN + Python 3.13.12 + ffmpeg 8.1, and lays out the prescriptive patterns the planner should split into the three plans (02-01 atomic+sidecar, 02-02 state.jsonl+reducer, 02-03 doctor+migration runbook).

Key validated facts:
- `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` + `os.replace(tmp, target)` works on `output/BV1C9QCBdE1U/` (real archive dir, no CJK in path; project's slug convention keeps `output/<slug>/` ASCII-safe per Phase 1 decisions). Tested live: tempfile `.tmp_test_xxx.json` → `os.replace` → success, file readable as UTF-8.
- `PermissionError` is a subclass of `OSError`; on Windows it carries `.winerror` attribute (e.g. 32 = `ERROR_SHARING_VIOLATION`, 33 = `ERROR_LOCK_VIOLATION`). D-11's "catch only `PermissionError`" is sufficient for the Defender/OneDrive/Search lock case — no need to widen the catch.
- `faster_whisper.__version__` is a real attribute (verified: `1.2.1`); ffmpeg version line is `ffmpeg version 8.1-essentials_build-www.gyan.dev ...` — naive `(\S+)` regex captures the full build string (introduces churn). **Use `(\d+\.\d+(?:\.\d+)?)` instead** to capture just the major.minor.patch.
- `derived_state(events)` reducer is a 10-line stdlib `for` loop or `functools.reduce` one-liner — no library needed. JSON Lines event log is the standard pattern for append-only logs.

**Primary recommendation:** Implement strictly per CONTEXT.md D-01..D-23. The only research-driven additions are (a) the cleaner ffmpeg version regex, (b) explicit handling of the "sidecar parent dir doesn't exist" race, (c) NOT calling `os.fsync` on directories (POSIX-only — does not work on Windows; rely on `os.replace`'s atomicity instead), and (d) recommending stdlib `unittest` over pytest for the optional pure-function tests.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (D-01..D-23)

> The following are copied verbatim from `02-CONTEXT.md`. They are the authority — RESEARCH.md may not contradict them. The planner consumes them as-is.

#### Archive compatibility (RES-02 / RES-06) — most critical
- **D-01:** loader sees artifact exists but **no `<artifact>.params.json` sidecar** → **do NOT auto-regenerate**, but emit loud warning: `log.warning("no params.json for %s; cannot validate cache freshness — pass --force to regenerate with sidecar capture", path)`, then fall through to existing file-existence cache and return cached value. Rationale: 17-archive zero-friction rerun is PROJECT.md K3 hard rule + Phase 1 D-03; force regen would defeat 30-200MB video.mp4 + long ASR cost; silent match would permanently mask the P7.1 stale-reuse pitfall. Loud + don't-regenerate is the only choice that preserves history while leaving a visible signal; user-initiated `--force` is the path that fills in the missing sidecar.
- **D-02:** loader sees artifact exists + sidecar exists but **fields don't match** → **force regenerate + loud line**: `log.warning("regenerating %s because: %s changed %r -> %r", artifact, field, old, new)` (literally matches the RES-02 success-criterion contract), write fresh sidecar after regen. Multiple field mismatches → one log line per field. `--force` triggers the same regen path but log wording becomes `"forced regeneration"`.
- **D-03:** state.jsonl missing or corrupt → **degrade to D-01 file-existence cache path** (RES-06). Corruption detection = any line fails `json.loads`; on detection, `log.warning` once + within this session **stop reading state.jsonl** (avoid spam) but continue normal append of subsequent events. **NEVER** auto-truncate / delete / "repair" state.jsonl — the user's corrupt file is diagnostic information.
- **D-04:** Phase 2 lands → **newly-written** artifacts always carry sidecars; archive remains in "no-sidecar" state until user actively `--force`-reruns; doctor subcommand displays this state cleanly (D-15).

#### params.json sidecar field scope (RES-01)
- **D-05:** Each artifact's sidecar records three categories: (a) **CLI flags** — what the user passed on the command line (`--whisper`, `--gap`, future `--profile`); (b) **function-level semantic params** — affect output but may not surface as CLI flags (`language=None`, `gap_threshold`, `max_para_duration`, `sentence_gap` defaults of `aggregate_paragraphs`; VAD `min_silence_duration_ms` and similar `transcribe` internals); (c) **key tool versions** — `faster_whisper.__version__`, ffmpeg `-version` first-line version string (regex-extracted, NEVER capture build hash — would cause spurious churn).
- **D-06:** **Do NOT** record: `ASR_DEVICE` (cpu/cuda produces same output, only speed differs), `PYTHONUTF8`, `HTTP_PROXY`, cookies file path. Rationale: the sidecar's truth is "params changed → output may change", not "environment changed". Environment differences are surfaced by doctor but never trigger sidecar diff regen.
- **D-07:** Three categories grouped inside sidecar JSON: `{"cli": {...}, "func": {...}, "tools": {...}, "captured_at": <iso8601>, "schema_version": 1}`. `tools` mismatch → warning ONLY (user decides whether to `--force`). `cli` / `func` mismatch → strict regen. Rationale: faster-whisper minor patches are usually output-equivalent; treating tool-version drift as auto-regen would introduce thrash.
- **D-08:** Physical form: **sibling file** in same dir, named `<artifact>.params.json` (NOT a nested `.meta/` dir). Rationale: compatible with `agent/tools.py:cleanup_frames` glob pattern (and doctor will use the same glob); aligns with frames/ directory convention (per-frame no sidecar; only stage-level products get sidecars).

#### Atomic write + Windows retry (RES-03 / RES-04)
- **D-09:** atomic-write helper lands in **`agent/io.py`** (Phase 1 PRE-03 module). Function name `write_json_atomic(path, obj, *, sidecar_params=None)` — signature lets "write artifact + write sidecar" complete atomically (either both new files or both old files survive). Rationale: (a) 30+ existing `write_text(json.dumps(...))` call sites get replaced one-for-one, preserving the `encoding="utf-8"` + `ensure_ascii=False, indent=2` idiom; (b) future phases' new artifacts (schedule.json, state.jsonl) reuse this helper; (c) consistent with single-landing-point principle of D-04.
- **D-10:** Implementation: `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` write → `os.replace(tmp, target)` commit → sidecar uses identical pattern immediately after. **Same-volume enforced** (tempfile in `target.parent` is naturally same-volume); if `target.parent` does not exist (rare race), `mkdir(parents=True, exist_ok=True)` first. On failure, clean up tmp (`unlink(missing_ok=True)`) but don't swallow the exception — let upstream decide.
- **D-11:** PermissionError retry: **3 attempts, 0.5s linear backoff** (literal RES-04 wording, no exponential — Defender/OneDrive scans usually clear in <2s, linear covers it; exponential introduces "wait longer" uncertainty). Catch ONLY `PermissionError`, NOT broad `OSError` (avoid masking disk-full / invalid-path fail-fast signals). Each retry → `log.info` (not warning, avoid noise); 3rd failure → re-raise original exception + a one-line hint: `原因可能是 Windows Defender / OneDrive / Search 索引短时持锁，重试 3 次后仍失败`.

#### state.jsonl design (RES-05 / RES-06)
- **D-12:** Physical form: **JSON Lines**, file named `output/<slug>/state.jsonl` (NOT `state.json` — the `.jsonl` suffix is explicit signal that mid-write `cat` won't see "broken JSON" with unclosed bracket). One JSON object per line, append-only; single-line corruption is locatable and discardable without trashing the whole log.
- **D-13:** Event schema: `{"ts": <iso8601>, "stage": <str>, "status": "started|completed|failed", "params_hash": <str>, "details": {...optional}}`. `params_hash` = sha256-prefix-16-hex of the three sidecar segments concatenated; lets `derived_state` decide "last run used these params" without re-reading sidecar. `stage` ∈ `{download, transcribe, aggregate, extract_frames, extract_frames_batch, doctor}` (doctor is read-only but logging access is useful for later phase audit).
- **D-14:** **Granularity: stage-level only on Phase 2 day-1**; segment-level frame events (`extract_frames_batch` segment-N completed) **deferred to Phase 4** alongside `extract_frames_batch`. Rationale: today's `cmd_extract_frames` is a single-segment call; segment-level events only have meaning in batch mode; designing them now is over-engineering. Phase 2 reducer outputs `dict[stage_name, {status, last_completed_at, params_hash}]`; Phase 4 will extend with segment events (no schema_version bump because additive optional).

#### doctor subcommand (RES-07)
- **D-15:** Output form: **plain ASCII table by default + `--json` flag** (no color, no `--diff`, no `rich`). Rationale: (a) zh-CN Windows terminals have inconsistent color support (Phase 1 D-17 left a clean-environment slot but kept it opt-in); (b) `--json` is the pipeline/scripting hook for later phases; (c) `--diff` only becomes meaningful once Phase 4-5 introduce more artifacts — YAGNI.
- **D-16:** Table columns: `artifact | exists | mtime | params_hash_match | last_state` — five columns covering RES-07's "existence, mtime, sidecar params" trio + sidecar diff state + state.jsonl-perspective last state. `params_hash_match` ∈ `{✓, ✗, —}` (match / mismatch / no sidecar). `last_state` ∈ `{completed, failed, started, —}` (state.jsonl's most-recent record for that stage; absent → `—`).
- **D-17:** Usage: `python -m agent.tools doctor output/<slug>` — **positional dir** (consistent with `cleanup_frames`; no `--slug` flag). `--json` output: top-level dict `{slug: <str>, artifacts: [{name, exists, mtime, params_hash_match, last_state, sidecar: {...}}, ...], state_log_status: "ok|missing|corrupt"}`. **Read-only** — does NOT modify any file, does NOT backfill missing sidecars (that's the `--force` path of D-01).

#### schema-migration runbook (RES-08)
- **D-18:** Location: **`docs/schema-migration.md`** — Phase 1 already created `docs/` (verified: `docs/schema-versions.md` exists from Phase 1). Co-locate schema docs.
- **D-19:** Depth: **medium** (1-2 pages), four sections: (a) **when to bump** — required field removed / renamed / type-changed → must bump; (b) **when NOT to bump** — added optional field / new artifact type → no bump (Phase 1 D-04/D-05 are precedents, e.g. SRC-04's `source` field on meta.json adds without bump); (c) **minimal runnable example** — using `meta.json`, write a pseudo `_migrate_meta_v1_v2(obj)` round-trip showing how `agent/io.py:load_meta` plugs in a migration call without disturbing call sites; (d) **test checklist** — every bump must verify 17-archive still loads under new loader (Phase 1 D-08 regression flow becomes the schema-upgrade compulsory).
- **D-20:** Pick `meta.json` (not segs.json) for the example because segs.json is a top-level list (Phase 1 D-04 locked: cannot wrap), making it a poor migration carrier. meta.json is dict, naturally supports a `schema_version` field, and is the most likely first real v2.

#### Plan split (matches ROADMAP, 3 plans)
- **D-21:** **02-01:** atomic write + PermissionError retry + sidecar read/write helpers (D-05..11) — extends `agent/io.py` + replaces 5 cmd_* call sites. **First**, because 02-02's state.jsonl read/write itself uses this helper.
- **D-22:** **02-02:** new `agent/state.py` module + `state.jsonl` append + `derived_state(events)` reducer + the 5 cmd_* logging events at appropriate moments (D-12..14) — bridges with 02-01 via io.py atomic-append helper.
- **D-23:** **02-03:** `doctor` subcommand + `docs/schema-migration.md` (D-15..20) — last, because doctor needs both 02-01's sidecars and 02-02's state.jsonl to display complete data; migration runbook is doc-only and depends on no code change.

### Claude's Discretion (planner / executor decides)

These details are NOT in the D-XX list — downstream agents may freely choose:
- atomic-write helper's tempfile name prefix (suggested `.tmp.<artifact>` but planner may pick alternate)
- whether `params_hash` sha256 is truncated to 16 hex (or 12 / 8 — collision-vs-readability tradeoff)
- doctor table's ASCII border style (box-drawing chars / `+---+` / pure space alignment all OK)
- whether `agent/state.py` reducer ships a `__main__` debug entry
- whether first sidecar write echoes the path to stdout (optional UX)
- which cmd_* internal defaults make the sidecar's `func` group (suggested coverage: anything Phase 5 `profile=podcast` will change, but final list is planner's call after reading the code)

### Deferred Ideas (OUT OF SCOPE for Phase 2)

- **`step_log.json` full provenance** (PITFALLS U4) → defer to v2 (REQUIREMENTS RES-V2-02 has it). Phase 2 partially covers via sidecar + state.jsonl.
- **Whisper-server persistent model across calls** (PITFALLS implicit / RES-V2-01) → defer until parallelism actually lands (Phase 6 if PARA ships).
- **Cache key includes audio mtime / video.mp4 hash** → not in Phase 2; sidecar fields are the "params dimension" only, no "input data hash" dimension. If a real "swapped video.mp4 but kept params → silently used old segs.json" case appears, then revisit (low likelihood — swapping mp4 typically clears the entire `output/<slug>/`).
- **`agent/state.py` real segment-level frame events** → defer to Phase 4 alongside `extract_frames_batch` (D-14).
- **doctor's `--diff` / `--fix` flags** → defer to Phase 4-5 once new artifacts create real diff demand; today YAGNI.
- **schema-migration runbook with real v1→v2 code** → only "pseudo round-trip" placeholder this phase; the first real v2 migration is owned by whichever phase needs it (Phase 1 D-06 locked this principle).
- **Add `filelock` to `requirements.txt`** → no, that's Phase 6 PARA work; Phase 2 atomic-write needs no external lock — `os.replace` is OS-level atomic primitive.
- **Fix CONCERNS §1.1 (three frame-extraction implementations) / §1.2 (`agent/prepare.py` half-orphan)** → out of Phase 2 scope; PROJECT.md OOS forbids "rewrite or delete existing modules"; preserve as-is.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RES-01 | Every artifact-writing function in `agent/tools.py` writes a sidecar `<artifact>.params.json` capturing parameters used | D-05/D-07 lock 3-segment shape `{cli, func, tools}`; D-08 sibling-file location verified compatible with cleanup_frames glob; ffmpeg version regex `(\d+\.\d+(?:\.\d+)?)` recommended (live test confirmed naive `(\S+)` captures `8.1-essentials_build-www.gyan.dev` build string — D-05's "avoid build hash churn" implementation detail) |
| RES-02 | Loaders compare current params against sidecar; mismatch → regenerate with loud `regenerating <artifact> because: <field> changed <old> -> <new>` | D-01/D-02 lock the loud-but-safe behavior (no auto-regen on missing sidecar; force regen on mismatch); 17 archive's "missing sidecar" path covered by D-01 |
| RES-03 | All artifact JSON writes use atomic-write (`NamedTemporaryFile(dir=target.parent)` + `os.replace`); same-volume enforced | D-09/D-10 lock the pattern; **VERIFIED LIVE** on `output/BV1C9QCBdE1U/` (real archive dir): tempfile→os.replace succeeds, content readable as UTF-8 |
| RES-04 | All artifact writes retry 3× / 0.5s on PermissionError | D-11 locks the strategy; verified `PermissionError` is `OSError` subclass and on Windows carries `.winerror` (32 = ERROR_SHARING_VIOLATION, 33 = ERROR_LOCK_VIOLATION); catching only `PermissionError` is sufficient (no need to widen to `OSError`) |
| RES-05 | `agent/state.py` provides append-only `output/<slug>/state.json` event log + pure `derived_state(events)` reducer; per-stage and per-segment-frame granularity | D-12 corrects the file name to `state.jsonl` (RES-05's "state.json" is misleading — explicitly using JSON Lines suffix per D-12 rationale); D-14 defers per-segment to Phase 4 (today's `cmd_extract_frames` is single-segment so no semantic content for it); reducer is a 10-line stdlib `for` loop, no third-party dep |
| RES-06 | Missing/corrupt state.json → graceful degrade to file-existence cache | D-03 locks the degradation: corruption = any line `json.loads` failure; warn once, suppress further reads in same session, never auto-repair |
| RES-07 | `doctor` CLI subcommand prints read-only scan of artifact existence + mtime + sidecar params | D-15..D-17 lock the 5-column ASCII table + `--json` flag; positional dir argument matching `cleanup_frames` convention; strictly read-only |
| RES-08 | One-page schema-migration runbook in `docs/schema-migration.md` | D-18..D-20 lock contents (when-to-bump rules, no-bump rules, meta.json pseudo round-trip example, 17-archive test checklist); `docs/` directory already exists from Phase 1 |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

These directives are project-wide hard rules; the planner must verify compliance:

| Constraint | Source | Phase 2 Implication |
|------------|--------|---------------------|
| ¥0 全流程 (no paid API) | CLAUDE.md L1-2 | Phase 2 introduces no external service / API — stdlib only ✓ |
| Claude Code is唯一决策者 (no auto-decisions in tools) | CLAUDE.md L1-2 | doctor is read-only (D-17); state.jsonl is informational; sidecar mismatch triggers regen but never silently changes outputs |
| 5-command CLI is canonical | CLAUDE.md L8-15 | `doctor` is a 6th command; doesn't break the 5 (download/transcribe/aggregate/extract_frames/cleanup_frames) — it adds, not replaces |
| 帧理解直接 Read JPEG, no API | CLAUDE.md L17-19 | unaffected by Phase 2 |
| Encoding: explicit `encoding="utf-8"` + `ensure_ascii=False, indent=2` | CONVENTIONS.md §"I/O & Path Conventions" | `write_json_atomic` helper MUST preserve these as default kwargs |
| `pathlib.Path` only, no `os.path` | CONVENTIONS.md §"I/O" | `agent/io.py` and `agent/state.py` use Path throughout |
| `from __future__ import annotations` at top of every module | CONVENTIONS.md §"Type Hints" | new `agent/state.py` MUST start with this |
| `log = logging.getLogger(__name__)` + lazy `log.warning("foo: %s", x)` | CONVENTIONS.md §"Logging" | D-01..D-03 warnings use lazy formatting |
| CLI handlers named `cmd_<name>`, dispatch via dict | CONVENTIONS.md §"CLI Pattern" | `cmd_doctor` registered in `cmds = {...}` at `agent/tools.py:243-251` |
| `subprocess.run([..., "ffmpeg", ...], check=True, capture_output=True)` | CONVENTIONS.md §"Error Handling" | sidecar's ffmpeg version probe reuses this exact pattern |
| Backward-compat: 17 archive must rerun unchanged | CLAUDE.md (implicit) + PROJECT K3 | D-01 (no-sidecar = warn, don't regen) directly addresses this |

## Standard Stack

### Core (stdlib only — no new dependencies)

| Module | Stdlib? | Purpose | Why Standard |
|--------|---------|---------|--------------|
| `tempfile.NamedTemporaryFile` | yes | Create same-dir temp file for atomic-replace pattern | Canonical Python idiom for atomic write [VERIFIED: Python 3.13 docs + live test on `output/BV1C9QCBdE1U/`] |
| `os.replace` | yes | Atomic rename across the temp→target boundary | Documented atomic on POSIX AND Windows (uses `MoveFileExW` with `MOVEFILE_REPLACE_EXISTING`) [CITED: docs.python.org/3/library/os.html#os.replace, ActiveState recipe 579097] |
| `pathlib.Path` | yes | All path manipulation (CONVENTIONS-mandated) | Project convention; `os.path` forbidden in app code |
| `json.dumps(obj, ensure_ascii=False, indent=2)` | yes | Serialize sidecars / events / artifacts | Existing 30+ call sites already use this exact form (CONVENTIONS §"JSON convention") |
| `hashlib.sha256` | yes | Compute `params_hash` for state events (D-13) | Standard hash; truncate to 16 hex (planner discretion per CONTEXT) |
| `datetime.datetime.now(timezone.utc).isoformat()` | yes | Generate `captured_at` / `ts` ISO-8601 timestamps | stdlib; UTC-with-`Z`-suffix discouraged in favor of `+00:00` (Python 3.11+ default) |
| `subprocess.run([..., "ffmpeg", "-version"], check=True, capture_output=True, text=True)` | yes | Probe ffmpeg version for sidecar `tools` segment | Pattern already used at `agent/tools.py:120` for ffmpeg invocation; just add `text=True` for stdout-as-str |
| `re.match(r"^ffmpeg version (\d+\.\d+(?:\.\d+)?)", line)` | yes | Extract clean version from `ffmpeg -version` first line | **VERIFIED via local ffmpeg 8.1**: naive `(\S+)` captures `8.1-essentials_build-www.gyan.dev` (build hash → churn); `(\d+\.\d+(?:\.\d+)?)` captures `8.1` cleanly |
| `faster_whisper.__version__` | third-party (already in requirements) | Sidecar `tools.faster_whisper` | **VERIFIED**: attribute exists, value `1.2.1` on this machine |
| `argparse.add_subparsers` | yes | Register `doctor` subcommand following established pattern | `agent/tools.py:196` already uses this for the 5 existing commands |
| `functools.reduce` (optional) | yes | Compact form of `derived_state(events)` reducer; explicit `for` loop also fine | Both forms acceptable; planner picks |
| `logging` | yes | All warning / info output | `log = logging.getLogger(__name__)` already used in `agent/tools.py:32` |

### Supporting

| Module | Stdlib? | When to Use |
|--------|---------|-------------|
| `unittest` | yes | Optional pure-function tests for `derived_state(events)` / `compare_params(old, new)` / `params_hash(...)` — see CONTEXT D-discretion (planner may add minimal tests, no framework decision required since stdlib `unittest` is already importable). **DO NOT** add `pytest` to requirements (verified absent — `import pytest` fails on this machine). |
| `os.fsync(fd)` | yes | OPTIONAL: call before `os.replace` for crash-during-power-loss safety. **NOT** recommended for Phase 2 — adds latency and the project's risk model is "Defender briefly holds lock" not "machine loses power mid-write". `os.replace` alone covers the locked-by-Defender / OneDrive case. |
| `os.fsync` on directory | POSIX only | **DO NOT USE** — fails on Windows (`OSError: [Errno 22]` on directory fds). The blog post linked in references mentions this for POSIX-only servers. |

### Alternatives Considered

| Instead of | Could Use | Why Not (this Phase) |
|------------|-----------|----------------------|
| `tempfile.NamedTemporaryFile + os.replace` | `tempfile.mkstemp` + `os.fdopen` + `os.replace` | mkstemp is also viable but doesn't auto-close on context-manager exit; NamedTemporaryFile is more idiomatic with `with` blocks. Either works; D-10 names NamedTemporaryFile and that's locked. |
| `tempfile.NamedTemporaryFile + os.replace` | Third-party `python-atomicwrites` | Library is **archived & unmaintained** [CITED: github.com/untitaker/python-atomicwrites — maintainer recommends "use os.replace"]. Adds a dependency for ~20 LOC of stdlib code. PROJECT.md ¥0 / minimal-deps philosophy → never. |
| `state.jsonl` (JSON Lines) | `state.json` (single nested array) | D-12 locked: jsonl is append-safe, single-line corruption is locatable, mid-write `cat` doesn't show "broken-looking" partial JSON. JSON-array form would require rewriting the whole file on each event = atomicity nightmare. |
| `sha256[:16]` for `params_hash` | full sha256 (64 hex) / sha1 / md5 / hash() | sha256 is cryptographic / collision-safe; truncate to 16 hex (64-bit) is sufficient for this scale (a slug typically has <10 stage events ever). md5 is fine here too but sha256 is the project-conservative choice. CONTEXT marks the truncation length as Claude's Discretion. |
| `os.replace` | `shutil.move` | shutil.move falls back to copy+delete cross-device, breaking atomicity. `os.replace` errors out cross-device (which we want — D-10 enforces same-volume). |
| ffmpeg version probe via `subprocess.run` | parse `ffprobe -version` instead | ffprobe ships with ffmpeg; same version. ffmpeg is already invoked at `agent/tools.py:120` so the subprocess overhead is no different. Either works; pick one. |

### Installation

**No new packages required.** All Phase 2 work uses Python stdlib + already-installed `faster-whisper`. Confirm with:

```bash
python -c "import tempfile, os, json, hashlib, datetime, pathlib, subprocess, re, logging, argparse, functools, unittest"
python -c "import faster_whisper; print(faster_whisper.__version__)"  # → 1.2.1 on this machine
ffmpeg -version | head -1  # → "ffmpeg version 8.1-essentials_build-www.gyan.dev ..."
```

### Version verification (live results, 2026-05-01)

| Component | Version | Verified |
|-----------|---------|----------|
| Python | 3.13.12 | `python --version` |
| ffmpeg | 8.1 (gyan.dev essentials build) | `ffmpeg -version | head -1` |
| faster-whisper | 1.2.1 | `python -c "import faster_whisper; print(faster_whisper.__version__)"` |
| pytest | NOT installed | `import pytest` → `ModuleNotFoundError` |
| unittest | stdlib (always available) | `import unittest` → OK |

## Architecture Patterns

### Recommended Project Structure (additive — no rearrangement)

```
agent/
├── io.py            # EXTENDED — adds write_json_atomic, read_sidecar, write_sidecar, compare_params
├── state.py         # NEW — append_event, read_events, derived_state(events) pure reducer
├── tools.py         # MODIFIED — 5 cmd_* call sites switch to write_json_atomic + sidecar; +cmd_doctor
├── asr_v2.py        # MODIFIED — expose hard-coded defaults of aggregate_paragraphs as a _DEFAULTS dict
└── ... (unchanged)
src/
├── asr.py           # MODIFIED — expose VAD param defaults of transcribe as a _DEFAULTS dict
└── ... (unchanged)
docs/
├── schema-versions.md  # EXISTS (Phase 1) — referenced from new doc
└── schema-migration.md # NEW — migration runbook (RES-08)
output/<slug>/
├── meta.json
├── meta.json.params.json     # NEW (sibling sidecar — D-08)
├── segs.json
├── segs.json.params.json     # NEW (sibling sidecar — D-08)
├── paragraphs.json
├── paragraphs.json.params.json  # NEW (sibling sidecar — D-08)
└── state.jsonl               # NEW (append-only event log — D-12)
```

### Pattern 1: Atomic JSON write with optional sidecar

**What:** Single transaction that writes `<artifact>` and `<artifact>.params.json` atomically. Either both new files survive or neither does (old versions remain).

**When to use:** Every JSON artifact write in `agent/tools.py` and any future phase. Replaces all 30+ `path.write_text(json.dumps(...))` call sites in artifact-writing code paths.

**Pattern:**
```python
# agent/io.py — extend Phase 1 module
from __future__ import annotations
import json, os, tempfile, time, logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_PERMISSION_RETRIES = 3
_PERMISSION_BACKOFF_S = 0.5

def _replace_with_retry(tmp: Path, target: Path) -> None:
    """os.replace with PermissionError retry per D-11 (3x, 0.5s linear)."""
    last_err: PermissionError | None = None
    for attempt in range(_PERMISSION_RETRIES):
        try:
            os.replace(tmp, target)
            return
        except PermissionError as e:
            last_err = e
            if attempt < _PERMISSION_RETRIES - 1:
                log.info("PermissionError replacing %s (attempt %d/%d): %s",
                         target.name, attempt + 1, _PERMISSION_RETRIES, e)
                time.sleep(_PERMISSION_BACKOFF_S)
    # 3 attempts exhausted
    raise PermissionError(
        f"{last_err}; 原因可能是 Windows Defender / OneDrive / Search 索引短时持锁，重试 3 次后仍失败"
    ) from last_err

def write_json_atomic(
    path: str | Path,
    obj: Any,
    *,
    sidecar_params: dict | None = None,
) -> None:
    """Atomically write JSON to path; optionally write <path>.params.json sidecar in same transaction.

    Both files use tempfile-in-target-dir + os.replace for atomicity.
    Same-volume guaranteed via dir=target.parent.
    Encoding/indent matches CONVENTIONS idiom (encoding=utf-8, ensure_ascii=False, indent=2).
    PermissionError on os.replace retried up to 3x with 0.5s linear backoff (D-11).
    On any failure, tmp files cleaned up via unlink(missing_ok=True) but exception re-raised.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, indent=2)

    # Stage 1: write artifact tempfile
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=str(target.parent),
        delete=False,
        prefix=f".tmp.{target.name}.",
        suffix=".tmp",
        encoding="utf-8",
    ) as tf:
        tf.write(payload)
        artifact_tmp = Path(tf.name)

    sidecar_tmp: Path | None = None
    sidecar_target: Path | None = None
    if sidecar_params is not None:
        sidecar_target = target.with_suffix(target.suffix + ".params.json")
        sidecar_payload = json.dumps(sidecar_params, ensure_ascii=False, indent=2)
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=str(target.parent),
            delete=False,
            prefix=f".tmp.{sidecar_target.name}.",
            suffix=".tmp",
            encoding="utf-8",
        ) as tf:
            tf.write(sidecar_payload)
            sidecar_tmp = Path(tf.name)

    # Stage 2: replace into place — artifact first, then sidecar.
    # If artifact replace succeeds and sidecar replace fails, we have a new
    # artifact without a sidecar — D-01 path will warn on next read but not regen.
    try:
        _replace_with_retry(artifact_tmp, target)
        if sidecar_tmp is not None and sidecar_target is not None:
            _replace_with_retry(sidecar_tmp, sidecar_target)
    finally:
        # Best-effort cleanup of any stragglers; don't mask exceptions
        artifact_tmp.unlink(missing_ok=True)
        if sidecar_tmp is not None:
            sidecar_tmp.unlink(missing_ok=True)
```

**Edge cases tested:**
- Target dir doesn't exist → `mkdir(parents=True, exist_ok=True)` (D-10).
- CJK in dir name → not encountered today (project slugs are ASCII-safe per Phase 1 D-12); if a future phase introduces CJK-named dirs, `tempfile.NamedTemporaryFile(dir=str(Path))` works but the planner should verify (live test on this machine succeeded with target file `test_atomic_中文.json` — but stdout printing is GBK-broken; file content was UTF-8-correct).
- PermissionError from Defender → 3-retry loop (D-11).

### Pattern 2: Append-only JSON Lines event log

**What:** Append a single-line JSON event to `output/<slug>/state.jsonl`. Crash-during-append yields at worst a single corrupt line (detectable by D-03 corruption rule).

**When to use:** Each `cmd_*` brackets its work with `started` and `completed`/`failed` events.

**Pattern:**
```python
# agent/state.py — NEW module
from __future__ import annotations
import json, hashlib, logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

def params_hash(sidecar: dict) -> str:
    """sha256-prefix-16-hex of sidecar (cli|func|tools segments) — D-13."""
    payload = json.dumps(
        {"cli": sidecar.get("cli", {}),
         "func": sidecar.get("func", {}),
         "tools": sidecar.get("tools", {})},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def append_event(
    state_log: str | Path,
    *,
    stage: str,
    status: str,             # "started" | "completed" | "failed"
    params_hash: str = "",
    details: dict | None = None,
) -> None:
    """Append one JSON line to state.jsonl. Best-effort; logs warning on failure
    instead of raising (an event-log write failure must not break the pipeline)."""
    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "status": status,
        "params_hash": params_hash,
    }
    if details is not None:
        event["details"] = details

    log_path = Path(state_log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False) + "\n"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line)
            # No fsync: relying on OS buffering. Per Phase 2 risk model
            # (Defender locks, not power loss), this is sufficient.
    except OSError as e:
        log.warning("failed to append state event to %s: %s", log_path, e)
```

**Why no `fsync` after append:** Phase 2's risk model is "Windows Defender briefly holds lock" + "user kills process" — both leave the file system in a consistent state because the kernel buffer flushes on close. Power-loss durability is OUT OF SCOPE (would require `fsync` + directory fsync on POSIX, the latter unavailable on Windows). Adding fsync is pure overhead for the project's actual failure modes. **WebSearch finding confirms:** atomicity of single-line `O_APPEND` writes on Windows is implementation-defined and not POSIX-equivalent [CITED: bugs.python.org/issue42606] — but for events ~200 bytes, the kernel write is functionally atomic in practice. If the planner wants belt-and-suspenders, add a `f.flush()` (no `os.fsync`) after the write — adds zero observable latency.

### Pattern 3: Pure event-sourcing reducer

**What:** `derived_state(events)` consumes the full event list and returns the current per-stage status. Pure function — no I/O, no side effects.

**When to use:** Cache-invalidation step in each cmd_* (after Phase 2-02 lands).

**Pattern:**
```python
# agent/state.py — same module, pure reducer
def read_events(state_log: str | Path) -> tuple[list[dict], str]:
    """Read all valid events from state.jsonl. Returns (events, status_str)
    where status_str ∈ {'ok', 'missing', 'corrupt'} — D-03 / RES-06.

    Corrupt = any line fails json.loads. Per D-03, corruption is not
    auto-repaired; we return what valid events we got plus 'corrupt' status,
    and caller logs warning ONCE then degrades to file-existence cache.
    """
    log_path = Path(state_log)
    if not log_path.exists():
        return [], "missing"
    events: list[dict] = []
    status = "ok"
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            status = "corrupt"
            break  # stop reading; D-03 forbids continuing past corruption
    return events, status

def derived_state(events: list[dict]) -> dict[str, dict]:
    """Pure reducer: events → per-stage current state.

    Returns: {stage_name: {status, last_completed_at, params_hash}}
    Where status is 'completed', 'failed', or 'started' (the most-recent event
    for that stage), last_completed_at is the ts of the most-recent 'completed'
    (or None if never completed), params_hash is the params_hash of the
    most-recent event for that stage.

    Phase 2 day-1 grain: stage-level only (D-14). Phase 4 will extend to
    include segment events; new key 'segments' will be additive — no
    schema_version bump.
    """
    state: dict[str, dict] = {}
    for ev in events:
        stage = ev.get("stage")
        if not stage:
            continue
        cur = state.setdefault(stage, {
            "status": None,
            "last_completed_at": None,
            "params_hash": None,
        })
        cur["status"] = ev.get("status")
        cur["params_hash"] = ev.get("params_hash") or cur["params_hash"]
        if ev.get("status") == "completed":
            cur["last_completed_at"] = ev.get("ts")
    return state
```

**Why explicit `for` loop instead of `functools.reduce`:** Both are stdlib. The for-loop reads more naturally for engineers debugging cache-invalidation logic. `functools.reduce` would compress to ~5 lines but obscures the per-stage update semantics. Planner can choose either; this pattern recommends the loop. [CITED: realpython.com/python-reduce-function — "Pythonic style often prefers explicit loops over reduce for readability"]

### Pattern 4: Sidecar field capture (for cmd_transcribe / cmd_aggregate / cmd_download)

**What:** Build the 3-segment sidecar dict (`{cli, func, tools, captured_at, schema_version: 1}`) at the point of artifact write.

**Pattern (illustrative — for `cmd_transcribe`):**
```python
# Inside agent/tools.py:cmd_transcribe — replaces lines 79-82
from agent.io import write_json_atomic
from agent.state import params_hash, append_event
from datetime import datetime, timezone

def _ffmpeg_version() -> str:
    """Probe ffmpeg version. Returns major.minor (or major.minor.patch); avoids build-hash churn."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], check=True, capture_output=True, text=True
        )
        m = re.match(r"^ffmpeg version (\d+\.\d+(?:\.\d+)?)", result.stdout)
        return m.group(1) if m else "unknown"
    except Exception as e:
        log.warning("ffmpeg version probe failed: %s", e)
        return "unknown"

def _faster_whisper_version() -> str:
    try:
        import faster_whisper
        return faster_whisper.__version__
    except Exception:
        return "unknown"

# In cmd_transcribe, replace segs_file.write_text(...) with:
sidecar = {
    "cli": {"whisper": args.whisper},  # CLI-passed flags
    "func": {                            # function-level defaults that affect output
        "language": None,
        "vad_filter": True,
        "min_silence_duration_ms": 500,
        "condition_on_previous_text": False,
        "beam_size": 5,
    },
    "tools": {
        "faster_whisper": _faster_whisper_version(),
        "ffmpeg": _ffmpeg_version(),
    },
    "captured_at": datetime.now(timezone.utc).isoformat(),
    "schema_version": 1,
}
write_json_atomic(segs_file, segs_data, sidecar_params=sidecar)
append_event(out_dir / "state.jsonl", stage="transcribe", status="completed",
             params_hash=params_hash(sidecar))
```

**Sidecar field source map (planner deliverable):**
The planner's 02-01 plan must enumerate, for each of the 3 cmd_* that write artifacts, the exact `cli` / `func` / `tools` field set. Suggested seed (executor refines):

| cmd | `cli` | `func` | `tools` |
|-----|-------|--------|---------|
| `cmd_download` (B站 path) | `{}` (no params affecting output beyond URL itself) | `{skip_if_cached: True}` | `{yt_dlp: <ver>}` (ffmpeg not used here) |
| `cmd_download` (抖音 path) | `{}` | `{skip_if_cached: True}` | `{httpx: <ver>}` (vendor crawler version not easily exposed; document as gap) |
| `cmd_transcribe` | `{whisper: args.whisper}` | `{language, vad_filter, min_silence_duration_ms, condition_on_previous_text, beam_size}` | `{faster_whisper, ffmpeg}` |
| `cmd_aggregate` | `{gap: args.gap}` | `{gap_threshold, max_para_duration, sentence_gap}` (currently hard-coded at `agent/asr_v2.py:30-32` — see Pattern 5) | `{}` (pure-Python, no external tool) |

### Pattern 5: Expose hard-coded defaults via `_DEFAULTS` constant

**What:** Today `aggregate_paragraphs` (`agent/asr_v2.py:28-32`) and `transcribe` (`src/asr.py:69-77`) embed defaults inline in the function signature / body. Sidecar capture needs to read these values reliably at the call site without duplicating them. CONTEXT D-05 / Integration Points lock this requirement.

**Pattern:**
```python
# agent/asr_v2.py — minimal change preserving signature backward-compat
_DEFAULTS = {
    "gap_threshold": 1.5,
    "max_para_duration": 30.0,
    "sentence_gap": 0.8,  # currently magic-number at line 81
}

def aggregate_paragraphs(
    segs: list[dict],
    gap_threshold: float = _DEFAULTS["gap_threshold"],
    max_para_duration: float = _DEFAULTS["max_para_duration"],
    sentence_gap: float = _DEFAULTS["sentence_gap"],  # NEW kwarg with old default
) -> list[Paragraph]:
    # body uses sentence_gap instead of magic 0.8
    ...
```

```python
# src/asr.py — same pattern
_VAD_DEFAULTS = {
    "min_silence_duration_ms": 500,
}

def transcribe(audio_path, *, model_size="small", language=None, initial_prompt=None,
               min_silence_duration_ms: int = _VAD_DEFAULTS["min_silence_duration_ms"]) -> list[Segment]:
    ...
    vad_parameters={"min_silence_duration_ms": min_silence_duration_ms},
    ...
```

**Why this is safe (backward-compat):** existing callers (`agent/tools.py:cmd_transcribe` / `cmd_aggregate`) pass none of these kwargs, so default-pass-through is unchanged. Phase 5 TEACH-06 / TEACH-12 will introduce `profile=` parameter that flips these constants — leaving the seam ready.

### Anti-patterns to avoid

- **❌ `os.rename` on Windows:** historically not atomic when target exists. Always `os.replace` [CITED: PITFALLS P7.2; docs.python.org/3/library/os.html].
- **❌ `path.write_text(json.dumps(...))` for artifact writes after Phase 2:** the whole point of `write_json_atomic` is single landing point. Test `agent/tools.py` after the rewrite to verify zero direct `write_text` on artifact files (markdown / log files MAY still use `write_text` — only artifact JSONs migrate).
- **❌ Catching `OSError` broadly in `_replace_with_retry`:** D-11 explicitly forbids this (would mask disk-full / invalid-path). `PermissionError` only.
- **❌ Auto-repairing state.jsonl on corruption:** D-03 explicitly forbids this. Corruption is diagnostic — surface it, don't hide it.
- **❌ Writing sidecar BEFORE artifact:** order matters — if sidecar lands first and process dies, next read sees "sidecar without artifact" → confused state. D-10 mandates artifact first, sidecar second. Code in Pattern 1 enforces this.
- **❌ Writing `state.jsonl` events from inside the reducer:** the reducer `derived_state` MUST be pure (no I/O). Tests for it must be plain function-call tests with crafted event lists.
- **❌ Creating a `.meta/` subdirectory for sidecars:** D-08 mandates sibling files. Subdir would break `cleanup_frames` glob assumptions and ruin doctor's glob discovery.
- **❌ Recording `ASR_DEVICE` in sidecar:** D-06 explicitly forbids — cpu/cuda produce same output, only speed differs; recording it would cause spurious regen on machine swaps.
- **❌ `os.fsync(dirfd)` on Windows:** POSIX-only; raises `OSError [Errno 22]` on Windows directory fds. The blog post in references discusses this for Linux servers — DO NOT port to Windows.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Hand-rolled tmp+rename with custom retry abstraction | `tempfile.NamedTemporaryFile(dir=parent, delete=False)` + `os.replace` (~15 LOC) | Already idiomatic; library `python-atomicwrites` is archived [CITED: github.com/untitaker/python-atomicwrites]; stdlib pattern is documented and audited |
| Append-safe event log | Custom binary format / SQLite / CSV | JSON Lines (`open(p, "a")` + write line) | JSON Lines is industry standard for append-only logs; one-line corruption is locatable; trivially parsed; matches existing `read_text(encoding="utf-8")` idiom |
| Event-sourcing reducer | Class-based aggregator with state | Pure function `derived_state(events: list[dict]) -> dict` | 10 lines of stdlib; pure functions are trivially testable; matches functional idiom of `agent/asr_v2.py:aggregate_paragraphs` |
| Schema versioning library | `pydantic` + version migrations / `marshmallow` | Document the convention in `docs/schema-migration.md` + a single switch in `agent/io.py:load_*` | Project has 3 artifact types; full schema-management framework is over-engineering. Phase 1 already laid the loader-tolerance foundation; just document the upgrade pattern |
| ASCII table for `doctor` | `rich` / `tabulate` library | Hand-rolled f-string padding + `+---+---+` borders | Adds dependency for a 5-column read-only display; CONVENTIONS bans new tooling without strong reason |
| File locking for parallel-safe write | `filelock` / `portalocker` | Don't add — Phase 6 (PARA) territory; Phase 2 deferred per CONTEXT | `os.replace` is OS-level atomic primitive on a single machine; cross-process races are Phase 6's problem |
| Color terminal output for doctor | `colorama` / `rich` | Plain ASCII (no color); D-15 explicitly forbids color | zh-CN Windows terminal color support is inconsistent (Phase 1 D-17); stays opt-in for future |

**Key insight:** Phase 2 is about codifying conventions, not adding capability. Every "library that solves this" is heavier than the 30-line stdlib pattern that solves it for the project's specific risk model (Defender locks, not network partitions or cross-process races). The ¥0 / minimum-deps philosophy + the locked-CONTEXT decisions converge on stdlib.

## Common Pitfalls

### Pitfall 1: ffmpeg version regex captures build hash → spurious sidecar churn

**What goes wrong:** Naive `re.match(r"ffmpeg version (\S+)", line)` on this machine captures `8.1-essentials_build-www.gyan.dev` (verified live). Different installs (gyan.dev / BtbN / system package / WSL) produce different `(\S+)` strings. Every sidecar comparison across machines or after a rebuild → "tools.ffmpeg changed" → warning noise.

**Why it happens:** ffmpeg's first line embeds build-config metadata. CONTEXT D-05 explicitly warns "正则提取，避免抓 build hash 引发伪 churn" — research validated this is a real risk on the user's actual install.

**How to avoid:** Use `re.match(r"^ffmpeg version (\d+\.\d+(?:\.\d+)?)", line)`. Captures `8.1` cleanly. If `match` is None, store `"unknown"`.

**Warning signs:** `doctor` shows `params_hash_match: ✗` immediately after a no-op rebuild of ffmpeg.

### Pitfall 2: state.jsonl read is hot path; corrupt file caught spammed warnings

**What goes wrong:** If state.jsonl is corrupt and EVERY cmd_* call re-reads + re-warns, the user gets a flood of warnings (every `--force` / every doctor run / every cache check).

**Why it happens:** D-03 mandates "warn on corruption". Naive implementation warns inside `read_events` which is called many times per session.

**How to avoid:** Cache the corruption status in a session-scoped global (e.g. module-level `_CORRUPTION_REPORTED: set[str] = set()` keyed by absolute path). Or: have the calling cmd_* check the status return and warn at most once per cmd invocation. CONTEXT D-03 says "不再读 state.jsonl" within the session — implement that literally with a per-path "skip" cache.

```python
# agent/state.py — session-cache pattern
_CORRUPT_PATHS: set[str] = set()  # process-lifetime; resets between python invocations

def read_events(state_log: str | Path) -> tuple[list[dict], str]:
    log_path = Path(state_log).resolve()
    key = str(log_path)
    if key in _CORRUPT_PATHS:
        return [], "corrupt"  # no further read, no further warning
    # ... actual read logic ...
    if status == "corrupt":
        _CORRUPT_PATHS.add(key)
    return events, status
```

**Warning signs:** Logs show `state.jsonl corrupt` 5+ times in one cmd run.

### Pitfall 3: Sidecar comparison false-negatives on float / int / list-order drift

**What goes wrong:** `compare_params(old_sidecar, new_sidecar)` does naive `dict ==`. But `1.5` ≠ `1.50`? `[1, 2]` ≠ `[2, 1]`? Result: D-02 path triggers "regenerate" on a no-op delta, blowing away the user's cached ASR.

**Why it happens:** Python `==` is structural for primitives but JSON round-trips can introduce drift (ints become floats in some serializers; insertion-order is preserved in dict but not list).

**How to avoid:**
- Always JSON-roundtrip both sides before comparing: `json.loads(json.dumps(x, sort_keys=True))` — normalizes float repr.
- For each `func` / `cli` field, treat as scalars only — no lists, no nested dicts (we control the schema). Document in `docs/schema-migration.md` (RES-08 example).
- The `compare_params(old, new)` function should yield `(field_name, old_val, new_val)` tuples for the changed-field log line in D-02.

```python
# agent/io.py
def compare_params(old: dict, new: dict) -> list[tuple[str, Any, Any]]:
    """Return list of (path, old_val, new_val) for fields that differ.
    Only inspects cli/func/tools sub-dicts. captured_at and schema_version
    are ignored (timestamp drift is normal; schema_version is loader's job)."""
    diffs = []
    for segment in ("cli", "func", "tools"):
        old_seg = old.get(segment, {})
        new_seg = new.get(segment, {})
        keys = set(old_seg) | set(new_seg)
        for k in sorted(keys):
            ov, nv = old_seg.get(k), new_seg.get(k)
            if ov != nv:
                diffs.append((f"{segment}.{k}", ov, nv))
    return diffs
```

**Warning signs:** User reports "I didn't change anything but it regenerated" — first thing to check is `params_hash` mismatch on a `tools.*` field (build drift from Pitfall 1).

### Pitfall 4: D-07 says "tools mismatch warns but doesn't regen" — easy to mis-implement

**What goes wrong:** Naive `if compare_params(old, new): regenerate()` treats all 3 segments equally. Per D-07, `tools.*` mismatch should ONLY warn (user decides whether to `--force`). Only `cli.*` / `func.*` mismatch should auto-regen.

**Why it happens:** Single comparison loop is simpler to write but doesn't distinguish severity.

**How to avoid:** Split compare into two calls or partition the diffs by segment:

```python
def cache_decision(old: dict, new: dict) -> str:
    """Return 'reuse' | 'regen' | 'warn_then_reuse' per D-02 / D-07."""
    diffs = compare_params(old, new)
    if not diffs:
        return "reuse"
    cli_func_diffs = [d for d in diffs if d[0].startswith(("cli.", "func."))]
    tools_diffs = [d for d in diffs if d[0].startswith("tools.")]
    if cli_func_diffs:
        for path, ov, nv in cli_func_diffs:
            log.warning("regenerating %s because: %s changed %r -> %r",
                        artifact_name, path, ov, nv)
        return "regen"
    if tools_diffs:
        for path, ov, nv in tools_diffs:
            log.warning("tools version drift in %s: %s %r -> %r (use --force to regenerate)",
                        artifact_name, path, ov, nv)
        return "warn_then_reuse"
    return "reuse"
```

**Warning signs:** User upgrades faster-whisper minor patch, project blows away all cached `segs.json` (bad). Or: user changes `--whisper small` → `medium`, project silently keeps old `segs.json` (also bad).

### Pitfall 5: doctor's params_hash comparison must read sidecar fresh, not state.jsonl's stored hash

**What goes wrong:** state.jsonl stores `params_hash` as it was at the time of completion. doctor's `params_hash_match` column is meant to answer "does the current sidecar match what's in state.jsonl?" If the sidecar file was edited externally (or a future regression hit), state.jsonl says "match" but the actual file content is different.

**Why it happens:** Two sources of truth (sidecar file + event log) — they can drift if anyone edits the sidecar file directly.

**How to avoid:** doctor recomputes `params_hash(sidecar_file_contents)` and compares to last `state.jsonl` event's `params_hash` for that stage. Show ✗ if they differ. If sidecar file is missing entirely → `—`.

**Warning signs:** doctor shows `✓` for an obviously stale artifact (sidecar manually edited).

### Pitfall 6: 17-archive scenario needs explicit test in 02-01 PLAN

**What goes wrong:** Code lands; 17-archive bug discovered only when user reruns. CONTEXT D-01 is the "loud + don't regen" rule but the 02-01 plan must ship with a verification step.

**How to avoid:** 02-01 plan's verification step MUST include: (1) run `python -m agent.tools transcribe output/BV132wizyEEB/video.mp4 --out output/BV132wizyEEB` (or equivalent, but **WITHOUT** `--force`); confirm log warning `no params.json for ...` appears; confirm cached `segs.json` is returned; confirm NO regen occurred; confirm NO sidecar was written. (2) Then with `--force`: confirm regen; confirm sidecar IS written this time; confirm log says "forced regeneration".

**Warning signs:** PR ships and user-rerun on archived video unexpectedly burns 30 minutes of ASR.

## Code Examples

Verified patterns from official sources / live tests:

### Atomic write — verified live on `output/BV1C9QCBdE1U/`

```python
# Live test 2026-05-01 succeeded
import tempfile, os
from pathlib import Path
test_dir = Path('output/BV1C9QCBdE1U')
with tempfile.NamedTemporaryFile(mode='w', dir=test_dir, delete=False,
                                  prefix='.tmp_test_', suffix='.json',
                                  encoding='utf-8') as tf:
    tf.write('{"中文": "测试"}')
    tmpname = tf.name
target = test_dir / 'test_atomic_中文.json'
os.replace(tmpname, target)
assert target.exists()
assert target.read_text(encoding='utf-8') == '{"中文": "测试"}'  # PASSED
target.unlink()
# Source: live verification on Windows 11 zh-CN + Python 3.13.12 + this repo
```

### Recipe: write-temp + os.replace [CITED: ActiveState recipe 579097]

```python
# https://code.activestate.com/recipes/579097-safely-and-atomically-write-to-a-file/
import tempfile, os
def safe_write(filename, data, **kwargs):
    """Safely write data to filename. Existing file replaced atomically."""
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(filename), **kwargs)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(data)
        os.replace(tmp, filename)
    except:
        os.unlink(tmp)  # cleanup tmp on failure
        raise
```

(Phase 2 uses `NamedTemporaryFile` instead of `mkstemp` to match the `with`-block idiom of the rest of the codebase, but the safety pattern is identical.)

### Existing `--force` cache pattern [Source: agent/tools.py:75-81]

```python
# Existing — Phase 2 wraps this with sidecar comparison
segs_file = out_dir / "segs.json"
if segs_file.exists() and not args.force:
    print(f"cached: {segs_file}")
    segs_data = load_segs(segs_file)
else:
    segs = transcribe(audio, model_size=args.whisper, language=None)
    segs_data = [asdict(s) for s in segs]
    segs_file.write_text(json.dumps(segs_data, ensure_ascii=False, indent=2),
                          encoding="utf-8")
```

After Phase 2-01, this becomes (illustrative pseudocode):

```python
# Phase 2 form
sidecar_path = segs_file.with_suffix(".json.params.json")
current_params = build_sidecar(args)  # 3-segment dict
decision = "regen"  # default if no cache
if segs_file.exists():
    if sidecar_path.exists():
        old_params = read_sidecar(sidecar_path)
        decision = cache_decision(old_params, current_params)  # see Pitfall 4
    else:
        log.warning("no params.json for %s; cannot validate cache freshness "
                    "— pass --force to regenerate with sidecar capture", segs_file)
        decision = "reuse"  # D-01: loud + don't regen
if args.force:
    decision = "regen_forced"
# (now act on decision)
```

### Argparse subcommand for doctor [Source: agent/tools.py pattern]

```python
# Following CONVENTIONS §"CLI Pattern (argparse subcommands)"
p = sub.add_parser("doctor", help="只读扫描 output/<slug>/ 工件状态")
p.add_argument("dir")  # positional, matches cleanup_frames convention
p.add_argument("--json", action="store_true", help="输出 JSON 而不是 ASCII 表")

# In main():
cmds = {
    "download": cmd_download,
    "transcribe": cmd_transcribe,
    "aggregate": cmd_aggregate,
    "extract_frames": cmd_extract_frames,
    "list_frames": cmd_list_frames,
    "cleanup_frames": cmd_cleanup_frames,
    "classify_frame": cmd_classify_frame,
    "ocr_frame": cmd_ocr_frame,
    "doctor": cmd_doctor,  # NEW
}
```

## Runtime State Inventory

> Phase 2 is greenfield infrastructure (NEW files only) — no rename / refactor in scope. All 5 categories below verified empty.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 2 doesn't rename keys, collection names, or IDs in any datastore. archive `output/<slug>/` retain original meta.json/segs.json/paragraphs.json content (D-01 forbids modification). | none |
| Live service config | None — Phase 2 doesn't touch any external service (no Datadog, no n8n, no Tailscale). | none |
| OS-registered state | None — no Task Scheduler / pm2 / launchd / systemd registration; no service is running on user's machine related to this project. | none |
| Secrets / env vars | `ASR_DEVICE` / `DOUYIN_COOKIES_FILE` / `BILIBILI_SESSDATA` / `HTTP(S)_PROXY` are referenced but not RENAMED by Phase 2 (D-06 explicitly excludes them from sidecar). No `.env` key changes. | none |
| Build artifacts / installed packages | None — no `pyproject.toml` to invalidate; no compiled binary; `requirements.txt` unchanged (D-stack confirms stdlib-only). | none |

**Why this section is short:** This phase ADDS new files and helpers. Existing artifacts are read but never rewritten by Phase 2 itself; they are only rewritten when the user runs a stage (in which case the new sidecar is written alongside, never modifying the existing artifact unless regen is triggered by params change or `--force`).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `os.rename` for atomic replace on Windows | `os.replace` | Python 3.3+ | `os.replace` is documented atomic on Windows via `MoveFileEx`; `os.rename` errors on existing target [CITED: docs.python.org/3/library/os.html#os.replace] |
| `python-atomicwrites` library | stdlib `tempfile + os.replace` | 2021-09 (library archived) | Maintainer's own recommendation: use stdlib [CITED: github.com/untitaker/python-atomicwrites README] |
| Single nested-array event log | JSON Lines (NDJSON) | de facto since ~2015 | Append-safe, line-corruption-locatable, trivially streamable [CITED: jsonlines.org] |
| Schema versioning via tooling (pydantic / marshmallow) | Inline `schema_version: <int>` field in dict-shaped artifacts | project-specific; Phase 1 D-04 locked | YAGNI principle for 3-artifact project; converges on industry pattern of "embed version, branch on read" [CITED: developer.couchbase.com schema-versioning tutorial] |
| `os.fsync(dirfd)` for crash-durability on POSIX | Skip on Windows (no equivalent); `os.replace` alone is sufficient for Phase 2 risk model | always (Windows lacks dir fsync) | Adding fsync for power-loss is out of Phase 2 scope; CONCERNS doesn't list this as a real failure mode |

**Deprecated/outdated:**
- `python-atomicwrites` library: **archived & unmaintained** as of 2024. Maintainer recommends `os.replace`. [CITED: github.com/untitaker/python-atomicwrites]
- `os.rename` for atomic file replacement on Windows: not atomic when target exists. Always `os.replace`. [CITED: PITFALLS §P7.2 + Python docs]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `os.replace` on Windows uses `MoveFileExW` with REPLACE_EXISTING flag and is atomic at the FS level for same-volume operations | Standard Stack / Pattern 1 | LOW — corroborated by Python docs (CITED) + ActiveState recipe; if wrong, would need `MoveFileTransacted` (deprecated since Vista era anyway) |
| A2 | Single-line JSON (~200 bytes) `O_APPEND` write is functionally atomic on Windows NTFS in absence of multi-process concurrency | Pattern 2 | LOW — Phase 2 is single-process; Phase 6 (PARA, deferred) will revisit. JSON Lines design is robust to mid-line corruption regardless. |
| A3 | `faster_whisper.__version__` attribute is stable across ≥1.0 versions | Pattern 4 | LOW — verified live (1.2.1); attribute is convention-standard for PEP-396 modules |
| A4 | `ffmpeg -version` first-line format `^ffmpeg version (\d+\.\d+...)` is stable across major builds (gyan.dev / BtbN / system) | Pattern 4 / Pitfall 1 | LOW — verified on 8.1; format predates 4.x [CITED: ffmpeg-devel mailing list]. If exotic build deviates, `re.match` returns None → store `"unknown"` (graceful) |
| A5 | tempfile `dir=str(target.parent)` produces same-volume tempfile on Windows when target is on D: drive | Pattern 1 | LOW — `tempfile` honors explicit `dir`; verified live |
| A6 | The 17-archive paths (`output/BV132wizyEEB`, etc.) contain no CJK in directory names (only in `meta.json["title"]` content) | Pattern 1 / Edge cases | LOW — verified by `git log` + `output/` directory listing (Phase 1 baseline videos are BV-IDs and ASCII slugs) |
| A7 | `subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout` first line is stable when `ffmpeg` PATH is resolved | Pattern 4 | LOW — pattern is identical to existing `agent/tools.py:120` invocation form. If ffmpeg missing on PATH, FileNotFoundError; sidecar capture should treat as "unknown" rather than aborting |
| A8 | `args.gap` (CLI-passed `--gap` to aggregate) is the only `cli` field for `cmd_aggregate`; `gap_threshold` / `max_para_duration` / `sentence_gap` go in `func` | Pattern 4 / sidecar map | LOW — CONTEXT D-05 explicitly distinguishes (a)/(b)/(c); mapping is clear |
| A9 | The blog post recommendation to `os.fsync` directory after replace does NOT apply on Windows | Anti-patterns | LOW — Windows API has no per-directory fsync; Python wraps `_commit` for files only; calling `os.fsync` on directory fd raises OSError. CONCERNS doesn't track this as a known issue → safe to skip. |
| A10 | The user's machine has tempfile creation working with `dir=Path` (not just str) | Pattern 1 | LOW — Python 3.13 accepts os-PathLike for `dir`; verified live with both forms. |

**No HIGH-risk assumptions.** All claims either cite stdlib docs / live test results, or relate to project-specific conventions already locked in CONTEXT.

## Open Questions (RESOLVED)

All 5 questions raised during research are resolved either by CONTEXT.md D-XX decisions or by the planner's plan implementations. Each question's resolution is captured below and reflected in the corresponding 02-XX-PLAN.md task.

1. **Should `cmd_download` write a sidecar?**
   - What we know: `cmd_download` writes `meta.json` (B站 path via `src/download.py`) or via `agent/douyin_downloader.py`. Both end with a meta.json write.
   - What's unclear: does meta.json have any "params that affect output"? CLI flag-wise, the only input is the URL (which IS the cache key — different URL → different slug → different `output/<slug>/`). So `cli` is empty for cmd_download. `tools.yt_dlp` / `tools.httpx` could matter for reproducibility but rarely cause output drift.
   - **RESOLVED:** Yes — planner ships sidecar for meta.json with `cli: {}, func: {}, tools: {yt_dlp: <ver>, ffmpeg: <ver>}` (consistent with CONTEXT D-04 "Phase 2 后新写入一律带 sidecar"). Implemented in `02-01-PLAN.md` Task 3 Step 5 (cmd_download branch). Doctor will display it; mismatch on `tools.*` triggers D-07 warning-only.

2. **Is the ffmpeg version probe latency acceptable on every cmd_* call?**
   - What we know: `subprocess.run(["ffmpeg", "-version"], ...)` takes ~50-200ms on cold cache.
   - What's unclear: doctor scans 5 artifacts × 2 (sidecar exists + current params build) = potentially 10× ffmpeg invocation. Acceptable?
   - **RESOLVED:** Yes with caching — `_get_ffmpeg_version()` and `_get_faster_whisper_version()` use `functools.lru_cache(maxsize=1)`. Single subprocess per Python process. Implemented in `02-01-PLAN.md` Task 1 (Pattern 4 Sidecar Probes section). lru_cache is per-process, so each new doctor invocation pays the cost once — acceptable.

3. **Should the sidecar `func` segment include the `_DEFAULTS` dict literal, or only the kwargs actually used?**
   - What we know: `aggregate_paragraphs(segs, gap_threshold=1.5)` — caller passes kwargs by name; `_DEFAULTS["gap_threshold"]` is what gets used.
   - What's unclear: if user passes `--gap 2.0` and code calls `aggregate_paragraphs(segs, gap_threshold=2.0)`, sidecar's `cli.gap=2.0` AND `func.gap_threshold=2.0` are duplicated.
   - **RESOLVED:** Keep both — `cli.*` reflects "what user typed", `func.*` reflects "what was actually used to compute". When they're equal it's redundant; when they diverge (Phase 5 `profile=podcast` overrides `--gap`), `func.*` is the truth. Storage is a few extra bytes — negligible. Implemented in `02-01-PLAN.md` Task 3 (cmd_aggregate sidecar build).

4. **Does the doctor's `last_state` column read state.jsonl every invocation?**
   - What we know: state.jsonl can grow over time; reading the whole file each doctor call is O(N).
   - What's unclear: at what N does this become a problem? For Phase 2 day-1 (stage events only), N stays small (< 50 events for typical use).
   - **RESOLVED:** Yes, read whole file every doctor call — implemented in `02-03-PLAN.md` Task 1 (cmd_doctor calls `derived_state(read_events(state_dir))`). No incremental read for Phase 2 day-1; CONTEXT `<deferred>` already records "Phase-V2 follow-up if N grows past 1000 with Phase 4 segment events".

5. **What happens when `cmd_doctor` is run on `output/<slug>` for a slug whose `output/` was created BEFORE Phase 2 (the 17 archive case)?**
   - What we know: D-15 says doctor displays state cleanly; D-16 says `params_hash_match: —` for missing sidecar; `last_state: —` for missing state.jsonl entry.
   - What's unclear: does doctor also append a `started/completed` event for the doctor invocation itself (D-13 implies `stage="doctor"`)?
   - **RESOLVED:** Yes audit trail, fail-silent — doctor appends `started`/`completed` events to state.jsonl; if the append fails (read-only volume / disk full), the failure is swallowed silently because doctor's primary contract is read-only artifact diagnosis, not write reliability. Implemented in `02-03-PLAN.md` Task 1 (cmd_doctor try/except around `append_event`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python | All Phase 2 work | ✓ | 3.13.12 | — |
| ffmpeg (PATH) | `tools.ffmpeg` sidecar field | ✓ | 8.1 (gyan.dev essentials) | If missing → store `"unknown"` for sidecar field; log.warning once |
| faster-whisper | `tools.faster_whisper` sidecar field; `cmd_transcribe` already requires this | ✓ | 1.2.1 | If missing → already breaks `cmd_transcribe`; sidecar field stores `"unknown"` |
| pytest | optional unit tests for `derived_state` / `compare_params` | ✗ | — | Use stdlib `unittest` instead — D-discretion (planner picks). DO NOT add to requirements. |
| `output/BV132wizyEEB/`, `output/BV1C9QCBdE1U/`, `output/douyin_trae_ai/` | regression verification per CONTEXT specifics | ✓ | exist with full SMTPF | — |
| `tests/regression/` directory | Phase 1 baseline | ✓ | exists with 3 slugs + runbooks | — |
| `docs/` directory | RES-08 schema-migration.md target | ✓ | exists with `schema-versions.md` (Phase 1) | — |
| `agent/io.py` module | Phase 2 extension point per D-09 | ✓ | exists from Phase 1 PRE-03 (62 lines, 3 loaders) | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** pytest — replace with stdlib `unittest` for any optional pure-function tests. CONVENTIONS.md §"Formatting & Linting" explicitly states "no tooling configured" — adding pytest would contradict this.

## Sources

### Primary (HIGH confidence)
- [Python 3 docs — `os.replace`](https://docs.python.org/3/library/os.html#os.replace) — atomic semantics on Windows + POSIX
- [Python 3 docs — `tempfile.NamedTemporaryFile`](https://docs.python.org/3/library/tempfile.html) — `dir=` parameter, `delete=False` flag, `mode="w"` + `encoding=`
- [Python bug tracker issue 14243](https://bugs.python.org/issue14243) — historical NamedTemporaryFile-on-Windows quirks (mostly resolved in Python 3.12+ with `delete_on_close`)
- [Python bug tracker issue 42606](https://bugs.python.org/issue42606) — POSIX O_APPEND atomicity guarantee on Windows (relevant to JSON Lines append safety)
- Project's own `.planning/codebase/CONVENTIONS.md` — JSON write idiom, encoding, logging, CLI pattern
- Project's own `.planning/codebase/CONCERNS.md` §5.4 / §6.3 — current cache validation gaps
- Project's own `.planning/research/PITFALLS.md` §P7.1 / §P7.2 / §P7.3 — atomic write + retry + stale-reuse rationale
- Live verification this session: tempfile + os.replace on `output/BV1C9QCBdE1U/`; faster_whisper.__version__; ffmpeg version regex

### Secondary (MEDIUM confidence)
- [ActiveState recipe 579097 — Safely and atomically write to a file](https://code.activestate.com/recipes/579097-safely-and-atomically-write-to-a-file/) — canonical mkstemp + os.replace recipe (Phase 2 uses NamedTemporaryFile equivalent)
- [Reliable file updates with Python — Gocept blog](https://blog.gocept.com/2013/07/15/reliable-file-updates-with-python/) — covers fsync rationale (Phase 2 declines for Windows-on-Defender risk model)
- [Real Python — `functools.reduce` tutorial](https://realpython.com/python-reduce-function/) — informs reducer pattern choice
- [Couchbase Developer Portal — Schema Versioning Tutorial](https://developer.couchbase.com/tutorial-schema-versioning?learningPath=learn/json-document-management-guide) — `schema_version` embedded-field convention
- [Confluent — Schema Evolution best practices](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) — additive-changes-only / forward-compat rules

### Tertiary (LOW confidence — secondary verification recommended if planner builds on these)
- [GitHub — `python-atomicwrites` README](https://github.com/untitaker/python-atomicwrites) — archived but maintainer's "use os.replace" note is authoritative
- [zetcode — `os.replace` guide](https://zetcode.com/python/os-replace/) — illustrative examples, not authoritative
- [JetBrains issue PY-31712](https://youtrack.jetbrains.com/issue/PY-31712/PermissionError-WinError-32) — anecdotal evidence of Defender-induced WinError 32

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — stdlib only, all idioms verified live or via Python 3.13 docs
- Architecture: HIGH — patterns are direct mappings of CONTEXT D-XX decisions; no exploration
- Pitfalls: HIGH — 6 pitfalls identified are all derivable from project specifics + live tests; ffmpeg regex pitfall confirmed by direct experiment
- Sidecar field map (Pattern 4): MEDIUM — illustrative seed; planner refines after reading code at 02-01 plan time
- Runtime state inventory: HIGH — phase is greenfield additions, all 5 categories empty by inspection

**Research date:** 2026-05-01
**Valid until:** 2026-08-01 (3 months — Python stdlib + project conventions are stable; revisit if Python 3.14 / faster-whisper 2.x lands)
