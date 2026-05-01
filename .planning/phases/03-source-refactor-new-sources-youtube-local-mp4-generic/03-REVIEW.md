---
phase: 03-source-refactor-new-sources-youtube-local-mp4-generic
reviewed: 2026-05-01T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - CLAUDE.md
  - agent/sources/__init__.py
  - agent/sources/_common.py
  - agent/sources/bilibili.py
  - agent/sources/douyin.py
  - agent/sources/generic.py
  - agent/sources/local.py
  - agent/sources/youtube.py
  - agent/tools.py
  - agent/url_router.py
  - requirements.txt
findings:
  critical: 0
  warning: 2
  info: 5
  total: 7
status: issues_found
---

# Phase 3: Code Review Report

**Reviewed:** 2026-05-01T00:00:00Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

The Phase 3 source refactor delivers a clean, well-structured registry: a `Source` Protocol, ordered `SOURCES` list with defensive load-time assertions, a pure-function router, and 5 source classes that delegate to existing legacy modules without modifying them (D-04 honored). The 5-class YouTube classifier is laid out in the locked priority order (po_token_required → cookies_stale → yt_dlp_outdated → gfw_blocked → other), regex patterns avoid catastrophic backtracking (no nested quantifiers), and proxy precedence (HTTPS_PROXY > HTTP_PROXY) matches D-14. Subprocess calls all use `shell=False` with list argv, ffprobe has a 5-second timeout, and the broadened CJK rejection regex (`[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]`) correctly covers Hiragana/Katakana/Fullwidth as the research noted. Sidecar/state.jsonl integration follows the Phase 2 single-landing-point pattern correctly, and the `{**legacy, **new}` idiom preserves byte-identical legacy meta.json key order.

Two correctness Warnings stand out:

1. **WR-01** — `cmd_ingest` only runs `ffprobe_video` when `work_dir / "video.mp4"` exists. YouTube (and the legacy `src.download.download` used by Bilibili/Generic) deliberately falls back to `mkv` / `webm` / `flv` extensions. When that fallback fires, the D-21 ffprobe preflight (and its no-audio guard) is silently skipped.
2. **WR-02** — YouTube subtitle selection (`for f in target_dir.glob("video.*.vtt"): sub_file = f; break`) picks filesystem-order, not language preference. With `subtitleslangs=["zh-CN", "zh", "en"]` configured, the user-meaningful "creator subtitle in their preferred language" can be silently overridden by an English auto-caption.

Five Info items cover dead/unused exports, edge cases around negative or fractional `--start`, and a defensive `except ImportError` that is unreachable. No security findings; no Critical issues. No backward-compat regressions detected (legacy 7/9-key prefix preserved via `{**a, **b}` per RESEARCH Pitfall 6; 17 archives can still re-run).

## Warnings

### WR-01: ffprobe preflight skipped for non-mp4 containers (D-21 hole)

**File:** `agent/tools.py:154-164`
**Issue:**
`cmd_ingest` runs the D-21 ffprobe preflight only when `work_dir / "video.mp4"` exists:

```python
video_path = work_dir / "video.mp4"
if video_path.exists():
    ffprobe_info = ffprobe_video(video_path)
    ...
```

But `agent/sources/youtube.py:262-266` and the legacy `src/download.py:67-72` both pick the first existing of `("mp4", "mkv", "webm", "flv")`, and both write the chosen path into `meta["video_path"]`. yt-dlp commonly returns `webm` (VP9) for YouTube and `mkv` for some Bilibili merges. When that happens:

- `video.mp4` does not exist → ffprobe block is skipped entirely
- `meta["codec"] / container / fps_mode` are NOT added
- The "no audio stream" guard (D-21 LOCKED message at `_common.py:96-99`) does not fire — a video.webm with no audio would silently move to transcribe and fail there with a non-actionable whisper error
- `-vsync vfr` extract_frames still runs fine, but the warn-only HEVC/AV1 hint (D-22) is also silently suppressed

This violates the phase contract "Uniform ffprobe preflight on every source's fetch() output."

**Fix:** Use the `video_path` already returned by the source's `legacy_meta` instead of guessing the extension:

```python
# In cmd_ingest, after `meta = source.fetch(...)`:
video_path_str = meta.get("video_path")
if video_path_str:
    video_path = Path(video_path_str)
    if video_path.exists():
        ffprobe_info = ffprobe_video(video_path)
        meta = {**meta,
                "codec": ffprobe_info["codec"],
                "container": ffprobe_info["container"],
                "fps_mode": ffprobe_info["fps_mode"]}
        if not meta.get("duration") and ffprobe_info.get("duration_s"):
            meta["duration"] = ffprobe_info["duration_s"]
```

This also future-proofs against LocalSource accepting `.mkv` / `.webm` / `.flv` (already in `_MEDIA_EXTS` at `local.py:26`) — current LocalSource always copies to `video.mp4` so it happens to work, but the fragile coupling between extension assumption and source implementation is exactly what WR-01 captures.

---

### WR-02: YouTube subtitle file picked by filesystem order, not language preference

**File:** `agent/sources/youtube.py:267-270`
**Issue:**

```python
sub_file = None
for f in target_dir.glob("video.*.vtt"):
    sub_file = f
    break
```

`Path.glob` returns entries in directory-iteration order, which is filesystem-dependent (NTFS happens to be alphabetical on Windows, but that's not guaranteed and reverses on case-insensitive volumes). When `subtitleslangs=["zh-CN", "zh", "en"]` produces multiple files (`video.zh-CN.vtt`, `video.zh.vtt`, `video.en.vtt`), the loop may pick `video.en.vtt` first, leaving the Chinese creator subtitle unused even though the configured priority puts it first.

`_detect_subtitle_origin` (line 192) correctly returns `"creator"` based on the info_dict, but the actual `subtitle_path` in legacy_meta may point at the wrong language — Phase 5 transcribe will see `subtitle_path` set and skip ASR, producing the wrong-language transcript.

**Fix:** Iterate in declared preference order:

```python
sub_file = None
for lang in ("zh-CN", "zh-Hans", "zh", "en"):
    candidate = target_dir / f"video.{lang}.vtt"
    if candidate.exists():
        sub_file = candidate
        break
if sub_file is None:
    # fall through to any-language match
    sub_file = next(iter(target_dir.glob("video.*.vtt")), None)
```

Note: same non-determinism exists in `src/download.py:74-77` but is out of scope per D-04 (legacy file unchanged).

## Info

### IN-01: `make_local_slug` is exported but never called

**File:** `agent/sources/local.py:72-88`
**Issue:**
`make_local_slug(input_path)` implements the LOCKED D-18 formula (`local_<8hex>_<ascii_stem>`) but is not invoked anywhere in the runtime codebase — `cmd_ingest` uses the user-supplied `args.out` directly. The helper exists for documented external callers (planning artifacts reference it) but a `grep` of `agent/`, `src/`, and CLI commands confirms zero call sites. If the user follows the Phase 3 contract literally, they pick the slug themselves; if they don't, the D-18 invariant is unenforced.

**Fix:** Either (a) wire it in — when `--out` is omitted in `cmd_ingest` for a local file, default `args.out = Path("output") / make_local_slug(args.url)`, or (b) add a docstring banner declaring the helper as "external API for orchestrators; runtime CLI does not auto-apply" so its dead-call status is intentional.

---

### IN-02: Negative `--start` produces malformed seg prefix

**File:** `agent/tools.py:339`
**Issue:**

```python
prefix = f"seg_{int(args.start):04d}_"
```

`argparse` declares `--start` as `type=float, default=0` with no lower bound. Passing `--start -5` yields `int(-5):04d` → `"-005"` (5 characters, breaks the implicit 4-digit prefix contract). The `prefix` is then used in pattern globs (`f"{prefix}*.jpg"`) and parsed back by downstream tools that may assume `seg_NNNN_*` shape.

**Fix:** Validate at argparse layer:

```python
def _non_negative_float(s):
    v = float(s)
    if v < 0: raise argparse.ArgumentTypeError("must be >= 0")
    return v
p.add_argument("--start", type=_non_negative_float, default=0)
p.add_argument("--end",   type=_non_negative_float, default=0)
p.add_argument("--fps",   type=float, default=1.0)  # allow >0 only:
# (also reject fps<=0 — `ffmpeg -vf fps=0` errors out anyway, but a clean ValueError is friendlier)
```

---

### IN-03: Fractional `--start` collides with adjacent integer `--start` on prefix

**File:** `agent/tools.py:339`
**Issue:**
`int(args.start):04d` truncates `--start 1.7` to `0001`, identical to the prefix `--start 1` would produce. Re-running extract_frames on overlapping windows (e.g., `--start 1 --end 30` then `--start 1.7 --end 30`) inter-mixes outputs into the same `seg_0001_NNNNNN.jpg` series, and `cleanup_frames --keep` cannot disambiguate them.

**Fix:** Either round to 1ms granularity in the prefix (`f"seg_{int(args.start*1000):07d}_"`) or document in argparse help that `--start` should be integer seconds when running multiple extract_frames calls into the same dir.

---

### IN-04: Unreachable `except ImportError` around stale-version warning

**File:** `agent/tools.py:130-134`
**Issue:**

```python
try:
    from agent.sources.youtube import warn_if_yt_dlp_stale
    warn_if_yt_dlp_stale()
except ImportError:
    pass  # yt-dlp not installed; sources will fail at fetch() with clearer error
```

`warn_if_yt_dlp_stale` itself imports `yt_dlp` only inside the inner helper `_yt_dlp_release_date`, which already wraps with `try: import yt_dlp except ImportError: return None`. The outer `from agent.sources.youtube import warn_if_yt_dlp_stale` does not transitively import yt_dlp at module load time, so the `except ImportError` here cannot fire from yt_dlp absence. (It would only fire if `agent.sources.youtube` itself failed to import — a much louder problem.)

**Fix:** Either drop the try/except entirely (function is import-safe by construction), or broaden the comment to "defensive against future module-level yt_dlp import" if you anticipate that change. Current code reads as protecting against a condition that can't occur.

---

### IN-05: LocalSource.match() invokes `is_file()` on every URL string

**File:** `agent/sources/local.py:32-40`
**Issue:**
`route()` walks SOURCES top-to-bottom; for every Bilibili / YouTube / Douyin / Generic URL, by the time we reach LocalSource (index 3), all four prior sources have already either matched or rejected. `LocalSource.match()` then calls `p.is_file()` (a stat() syscall) on the URL string. On Windows for `https://www.youtube.com/...`, `Path("https://www.youtube.com/...").is_file()` returns False quickly, but it does perform a filesystem call — for typical CLI use this is irrelevant noise, but in any future bulk-routing scenario it becomes wasteful. The `if "://" in url_or_path: return False` guard already catches this — but only after the URL test, the regex check on `_MEDIA_EXTS` short-circuits earlier than `is_file()` for any URL ending in `.html`, `.json`, etc.

**Fix:** Reorder: check the URL prefix first, then the suffix, then `is_file()` last (current code does this correctly, so the issue is mostly self-resolved). Confirming current short-circuit works:

```python
if "://" in url_or_path:        # cheap: O(len(url))
    return False
try:
    p = Path(url_or_path)
except (ValueError, OSError):
    return False
return p.suffix.lower() in _MEDIA_EXTS and p.is_file()  # ext check short-circuits is_file()
```

This is correct as written. No fix needed; flagged only because the `is_file()` cost is non-obvious from reading `route()`. Consider adding a comment that the suffix check intentionally short-circuits.

---

_Reviewed: 2026-05-01T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
