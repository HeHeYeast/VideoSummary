---
phase: 02-resume-infrastructure-cache-correctness
reviewed: 2026-05-01T00:30:56Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - agent/asr_v2.py
  - agent/io.py
  - agent/state.py
  - agent/tools.py
  - docs/schema-migration.md
  - src/asr.py
findings:
  critical: 0
  warning: 6
  info: 6
  total: 12
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-05-01T00:30:56Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 2 ("Resume Infrastructure & Cache Correctness") rewires three CLI handlers
(`cmd_download`, `cmd_transcribe`, `cmd_aggregate`) for atomic writes + sidecars,
adds `agent/state.py` (event log + reducer), introduces `cmd_doctor`, and ships
`docs/schema-migration.md`. The locked decisions from `02-CONTEXT.md`
(D-01..D-20) are faithfully implemented: regex pitfall #1 is dodged, corruption
suppression works as specified, the 3-segment sidecar shape is correct, and the
doctor's read-only-on-sidecar contract holds.

No Critical issues found. The most consequential findings are:

- **WR-01** — `agent/io.py` regressed the pre-Phase-1 type hints AND Chinese
  docstrings on `load_meta` / `load_segs` / `load_paragraphs`. Convention
  violation; trivial fix but should land before Phase 3 imports any of these
  via `read_sidecar` paths that currently do not document `JSONDecodeError`.
- **WR-02** — `read_sidecar` can raise `json.JSONDecodeError` on a truncated /
  partially-written sidecar, but `cmd_transcribe` and `cmd_aggregate` invoke it
  unguarded. Doctor handles it; the cache-decision call sites do not. A crashed
  prior run that left a half-written sidecar (pre-atomic-write archive scenario)
  would crash subsequent transcribe/aggregate runs.
- **WR-03** — `cmd_aggregate` reads `args.force` via `getattr(..., "force", False)`
  but the argparse subparser never adds `--force`. The flag is permanently
  reachable only via the false default; users cannot force regen of
  `paragraphs.json` without manually deleting the artifact + sidecar.

The other warnings are smaller correctness/UX concerns. Info items are style
nits that should not block phase sign-off.

Backward-compat with the 17 archives (D-01) is preserved: `read_sidecar` returns
None when the sidecar file is missing, `cache_decision` emits the locked warning
line, and reuse is the default. The pitfall-1 ffmpeg regex is anchored
correctly (`^ffmpeg version (\d+\.\d+(?:\.\d+)?)`) so 8.1-essentials_build-... no
longer churns.

## Warnings

### WR-01: Type hints + Chinese docstrings regressed on the three loader functions

**File:** `agent/io.py:46-73`
**Issue:** Pre-Phase-2 (commit `496ef6d^`) the loaders read:
```python
def load_meta(path: str | Path) -> dict:
    """加载 meta.json. Dict 工件支持 schema_version 字段 (缺失则视为 v1)."""
def load_segs(path: str | Path) -> list[dict]:
    """加载 segs.json. 顶层 list 类型, 一律视为 schema_version=1. ..."""
def load_paragraphs(path: str | Path) -> list[dict]:
    """加载 paragraphs.json. 同 load_segs, 顶层 list 即 v1."""
```
Phase 2 dropped both the `str | Path` parameter type, the `-> dict` / `-> list[dict]`
return type, AND replaced the Chinese docstrings with English one-liners. This
violates two locked CONVENTIONS.md rules:
- "Public function signatures consistently typed; locals usually untyped."
  (`agent/io.py` is a public-API module imported across `agent/tools.py`,
  `agent/prepare.py`, `src/pipeline.py`.)
- "Language: Chinese for everything — every module/function/class docstring
  and inline comment is Chinese."

The new helpers added in Phase 2 (`write_json_atomic`, `read_sidecar`,
`compare_params`, `cache_decision`, `_replace_with_retry`, `_get_ffmpeg_version`,
`_get_faster_whisper_version`, `now_iso`) are also missing type annotations and
their docstrings are in English. The whole module is now stylistically split:
the Phase-1 contract was Chinese+typed, the Phase-2 additions are English+untyped.

**Fix:** Restore the three loader signatures verbatim and translate the new
helpers' docstrings to Chinese. Add return / parameter types to all new
helpers. Example for `load_meta`:
```python
def load_meta(path: str | Path) -> dict:
    """加载 meta.json. Dict 工件支持 schema_version 字段 (缺失则视为 v1)."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(
            f"meta.json must be a dict (v1); got {type(obj).__name__} at {path}"
        )
    return obj
```
And for the new helpers, add types like:
```python
def write_json_atomic(
    path: str | Path,
    obj: Any,
    *,
    sidecar_params: dict | None = None,
) -> None: ...

def read_sidecar(artifact_path: str | Path) -> dict | None: ...

def compare_params(
    old: dict | None, new: dict | None,
) -> list[tuple[str, Any, Any]]: ...

def cache_decision(
    old: dict | None,
    new: dict,
    artifact_name: str,
    *,
    forced: bool = False,
) -> str: ...
```
(Note: typing `Any` is already imported at line 33 — currently unused, see IN-01.)

### WR-02: `read_sidecar` can raise `JSONDecodeError`; `cmd_transcribe` / `cmd_aggregate` do not handle it

**File:** `agent/io.py:167-175` (definition); `agent/tools.py:179, 234` (callers)
**Issue:** `read_sidecar` is documented as returning "parsed sidecar dict, or None
if sidecar file does not exist." It does not document that `json.loads` on a
malformed sidecar raises `json.JSONDecodeError`. The doctor (`agent/tools.py:390-394`)
correctly catches `(json.JSONDecodeError, OSError)` around the read, but the
two production cache-decision sites do not:

```python
# agent/tools.py:178-182 (cmd_transcribe)
if segs_file.exists():
    old_sidecar = read_sidecar(segs_file)   # uncaught JSONDecodeError
    decision = cache_decision(...)

# agent/tools.py:233-236 (cmd_aggregate)
if out.exists():
    old_sidecar = read_sidecar(out)         # uncaught JSONDecodeError
    forced = bool(getattr(args, "force", False))
    decision = cache_decision(...)
```

A scenario that hits this: the user's previous run died mid-`write_sidecar`
BEFORE Phase 2's atomic write was in place (i.e. an archive directory that has
a partially-written `<artifact>.params.json` from any pre-Phase-2 manual edit).
Or: the user opens the JSON in an editor, saves a syntax error, and re-runs.
In both cases the run crashes loudly with `JSONDecodeError`, defeating the
"graceful degrade to file-existence cache" principle that drives D-01.

**Fix:** Either (a) catch `JSONDecodeError` inside `read_sidecar` and return
`None` + warn (mirrors D-01 missing-sidecar path), or (b) document the
exception and have callers wrap it. Option (a) is more consistent with the
rest of the corruption story (state.jsonl returns `(events, "corrupt")` rather
than raising):

```python
def read_sidecar(artifact_path: str | Path) -> dict | None:
    """返回解析后的 sidecar dict; 不存在或损坏则返回 None (D-01 路径).

    损坏的 sidecar 视同缺失 -- 调用方走 D-01 (warn + reuse) 而非崩溃, 与
    state.jsonl 的 corruption-tolerant 读取语义一致.
    """
    sidecar = Path(artifact_path).parent / (Path(artifact_path).name + ".params.json")
    if not sidecar.exists():
        return None
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        log.warning("sidecar %s is corrupt: %s; treating as missing", sidecar.name, e)
        return None
```
This also lets `cmd_doctor` drop its local try/except (or keep it, since
`OSError` is still possible on Windows file-locked reads).

### WR-03: `cmd_aggregate` reads `args.force` but `--force` is not registered on the subparser

**File:** `agent/tools.py:235` (read site); `agent/tools.py:511-514` (parser definition)
**Issue:** `cmd_aggregate` does:
```python
forced = bool(getattr(args, "force", False))
decision = cache_decision(old_sidecar, current_sidecar, out.name, forced=forced)
```
The `getattr(..., "force", False)` defensive default suggests the author
intended for `--force` to be available. But the subparser only adds:
```python
p = sub.add_parser("aggregate", help="段落聚合")
p.add_argument("segs_json")
p.add_argument("--out", required=True)
p.add_argument("--gap", type=float, default=1.5)
```
No `--force`. So `forced` is permanently `False`, and the only way to force a
regeneration of `paragraphs.json` is to manually delete both the artifact AND
its sidecar. (`cmd_transcribe` exposes `--force` correctly at line 509;
`cmd_aggregate` is the inconsistent one.)

**Fix:** Add the flag to the aggregate subparser, parallel to transcribe:
```python
p = sub.add_parser("aggregate", help="段落聚合")
p.add_argument("segs_json")
p.add_argument("--out", required=True)
p.add_argument("--gap", type=float, default=1.5)
p.add_argument("--force", action="store_true")
```
Then the existing `getattr(args, "force", False)` guard is no longer
necessary but doesn't hurt.

### WR-04: `_replace_with_retry`'s tmp-file cleanup can mask the original PermissionError

**File:** `agent/io.py:155-159`
**Issue:** When `_replace_with_retry(artifact_tmp, target)` exhausts its 3
retries, it raises `PermissionError("..., 重试 3 次后仍失败")`. Control then
runs the `finally` block in `write_json_atomic`:
```python
finally:
    if artifact_tmp is not None:
        artifact_tmp.unlink(missing_ok=True)
    ...
```
`Path.unlink(missing_ok=True)` only suppresses `FileNotFoundError`, NOT
`PermissionError`. If Windows Defender / OneDrive is still holding the lock
that caused the replace to fail (the very scenario the retry was designed
for), `unlink` itself raises `PermissionError`, replacing the helpful
"重试 3 次后仍失败" message in the propagated exception. The original error
survives only via `__context__`, which most users won't see.

**Fix:** Wrap the unlink in a try/except so the original error always wins:
```python
finally:
    for tmp in (artifact_tmp, sidecar_tmp):
        if tmp is not None:
            try:
                tmp.unlink(missing_ok=True)
            except OSError as cleanup_err:
                # Best-effort cleanup; the real error from the try block
                # must not be masked by a stale tmp file we couldn't remove.
                log.warning("failed to remove tmp file %s: %s", tmp, cleanup_err)
```

### WR-05: `extract_frames` / `cleanup_frames` assume `out_dir.parent` is the slug dir; CONVENTIONS hardcoded that to be true

**File:** `agent/tools.py:265, 312`
**Issue:**
```python
# cmd_extract_frames
state_dir = out_dir.parent  # assumes out is output/<slug>/frames

# cmd_cleanup_frames
state_dir = d.parent  # assumes d is output/<slug>/frames
```
Per CONVENTIONS.md the canonical layout is `output/<slug>/frames/*.jpg`, so
`out_dir.parent == output/<slug>/` is correct in the happy path. But:
1. The CLI's `--out` is user-supplied; nothing enforces `frames` as the leaf
   directory. The phase locked decision D-08 ("frames/ subdir intentionally
   omitted") presumes the `output/<slug>/frames/` layout but Phase 2 doesn't
   validate it.
2. If a user invokes `extract_frames video.mp4 --out output/myslug/` (no
   trailing `frames/`), `state_dir` becomes `output/`, and `state.jsonl` is
   written one level too high — pollution of the parent directory and silent
   drift between archive and state.

This is a foot-gun for users following the README literally vs. picking their
own path. The CLAUDE.md example is `--out output/BVxxx/frames` which is
correct, but no runtime guardrail.

**Fix:** Either (a) document the `--out must be output/<slug>/frames/`
contract in the help string, or (b) verify and warn:
```python
state_dir = out_dir.parent
if not (state_dir / "meta.json").exists():
    log.warning(
        "extract_frames out=%s: parent does not look like an output/<slug>/ "
        "directory (no meta.json found). state.jsonl will be written to %s.",
        out_dir, state_dir,
    )
```
Light-touch (b) preferred — preserves the day-1 contract while protecting
users who pass the wrong path.

### WR-06: ASCII table column widths use `len()` which mis-counts CJK / box-drawing glyphs

**File:** `agent/tools.py:441-446`
**Issue:**
```python
widths = [max(len(str(row[i])) for row in cells) for i in range(len(headers))]
```
`len()` returns code points, not display columns. The doctor's value cells
include `✓` (U+2713), `✗` (U+2717), and `—` (U+2014, em-dash). On a CJK
terminal these render as 2 display columns each, but `len()` returns 1, so
`ljust` under-pads those cells and the right-side `|` borders no longer line
up. Mtime cells (ISO timestamps with `+00:00`) are pure ASCII so they align;
the asymmetry makes only the `params_hash_match` and `last_state` columns
mis-rendered.

This is cosmetic only — the doctor still reports correct data — but on a
zh-CN Windows cmd (the project's primary target host per CLAUDE.md) the
table looks broken, which undermines the phase's "diagnostic UX" goal.

**Fix:** For the small set of glyphs this code uses, the simplest correct
solution is to keep `len()` but pad an extra space for known-wide chars:
```python
def _vis_width(s: str) -> int:
    """Display width: CJK + east-asian-wide chars count 2 columns."""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(c) in ("F", "W") else 1 for c in s)

widths = [max(_vis_width(str(row[i])) for row in cells) for i in range(len(headers))]
# and in the row formatter use a custom ljust that pads by display width:
def _ljust(s: str, w: int) -> str:
    return s + " " * (w - _vis_width(s))
line = "| " + " | ".join(_ljust(str(row[j]), widths[j]) for j in range(len(headers))) + " |"
```
Or accept the misalignment — `unicodedata` is stdlib so the fix is cheap.
Either way is fine; flagging because the doctor's whole purpose is human-
readable diagnosis.

## Info

### IN-01: Unused `Any` import in `agent/io.py`

**File:** `agent/io.py:33`
**Issue:** `from typing import Any` is imported but never referenced in the
module. (`agent/state.py:25` also imports `Any` but DOES use it at line 76.)
**Fix:** Remove the unused import, OR — better — use `Any` in the proposed
type signatures from WR-01 (`compare_params` returns `list[tuple[str, Any, Any]]`,
`write_json_atomic` takes `obj: Any`).

### IN-02: `append_event` parameter name `params_hash` shadows the module-level function

**File:** `agent/state.py:60-65, 80`
**Issue:**
```python
def append_event(
    state_log: str | Path,
    *,
    stage: str,
    status: str,
    params_hash: str = "",   # shadows module-level params_hash() function
    details: dict | None = None,
) -> None:
    ...
    "params_hash": params_hash,
```
Inside `append_event` you cannot call the module-level `params_hash(sidecar)`
helper — the parameter shadows it. Today nothing in the body needs to. But
if a future hand edit (Phase 4 segment events, say) tries to compute the
hash in-line, it'll silently get the str argument as a callable and `TypeError`.
Pre-existing footgun, not a bug today.
**Fix:** Rename the parameter to `params_hash_value` or `phash`, or document
the shadow with a comment. Lowest-risk option: rename the function to
`compute_params_hash` (its only call site is `agent/tools.py:79`).

### IN-03: Bare `except Exception` in `_get_faster_whisper_version`

**File:** `agent/io.py:286`
**Issue:**
```python
@functools.lru_cache(maxsize=1)
def _get_faster_whisper_version():
    try:
        import faster_whisper
        return getattr(faster_whisper, "__version__", "unknown")
    except Exception:
        return "unknown"
```
Project convention (CONVENTIONS.md "Error Handling") is narrow exception
catches — `pHash on bad image: warn + skip` style. Here only
`ImportError` / `ModuleNotFoundError` is realistic; nothing else can come from
the body.
**Fix:**
```python
except (ImportError, ModuleNotFoundError):
    return "unknown"
```

### IN-04: Inline `from datetime import datetime, timezone` inside `cmd_doctor` is redundant

**File:** `agent/tools.py:340`
**Issue:** `cmd_doctor` does `from datetime import datetime, timezone` inside
the function. The module already imports `now_iso` from `agent.io` (which
itself uses `datetime`). The inline import is only needed for
`datetime.fromtimestamp(...)` at line 378, which could be moved to a
top-of-file import for consistency with project style (the only other
deferred import in this file is `from src.asr import ...` and `from
agent.douyin_downloader import ...` which legitimately need `sys.path`
patching first).
**Fix:** Move to the top of the file with the other stdlib imports.

### IN-05: `agent/state.py` uses bare `open()` instead of `Path.open()`

**File:** `agent/state.py:89`
**Issue:**
```python
with open(log_path, "a", encoding="utf-8") as f:
```
Project convention is `pathlib.Path` everywhere; `os.path` is forbidden.
Bare `open()` is technically allowed (it's stdlib, not `os.path`), but
`log_path.open("a", encoding="utf-8")` is the more idiomatic equivalent
matching the rest of the codebase.
**Fix:**
```python
with log_path.open("a", encoding="utf-8") as f:
```

### IN-06: `cmd_doctor` has no `failed` event path

**File:** `agent/tools.py:368, 451`
**Issue:** Doctor emits `started` then `completed` unconditionally. If the
table-rendering or row-collection loop raises (e.g. a `ValueError` from a
malformed sidecar that escapes the existing try/except), there's no `failed`
event. The audit trail therefore can't distinguish "doctor crashed" from
"doctor was killed by Ctrl-C". Diagnostic-only impact.
**Fix:** Wrap the body in try/except that emits a `failed` event before
re-raising:
```python
try:
    # ... existing body ...
    append_event(state_log, stage="doctor", status="completed")
except Exception as e:
    append_event(state_log, stage="doctor", status="failed",
                 details={"error_type": type(e).__name__, "error": str(e)[:200]})
    raise
```
This mirrors the started/completed/failed pattern used by the other 5
`cmd_*` handlers (transcribe, aggregate, download, extract_frames,
cleanup_frames). Symmetry is the only argument; doctor is read-mostly and
a crash is unlikely.

---

_Reviewed: 2026-05-01T00:30:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
