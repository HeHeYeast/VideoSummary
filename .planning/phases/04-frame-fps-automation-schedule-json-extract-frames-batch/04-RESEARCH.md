# Phase 4: Frame fps Automation (`schedule.json` + `extract_frames_batch`) - Research

**Researched:** 2026-05-01
**Domain:** schedule-driven batch frame extraction + decision-support tools (PySceneDetect / silero-vad) for a ¥0 local Claude-Code-driven pipeline
**Confidence:** HIGH (libraries verified against PyPI/upstream source; integration shape locked by Phase 2/3 already-shipped code; one MEDIUM flag on torch dep cost for silero-vad)

## Summary

Phase 4 implements the locked `schedule.json` schema (already pinned by `.planning/research/SUMMARY.md` §"Locked schedule.json schema" and CONTEXT D-01..D-04), the `extract_frames_batch` CLI that consumes it (FPS-01/02/03), and two **decision-support read-only** subcommands (`detect_scenes`, `detect_silence` per FPS-05/06). All five validation rules in CONTEXT D-05 plus the silence-coverage strict-or-fallback rule in D-07/D-08 are mechanical: their semantics are settled at the CONTEXT layer; implementation is defensive parsing + ffprobe duration crosscheck.

The single biggest research finding is that **silero-vad >=5.1 hard-depends on `torch>=1.12.0` + `torchaudio>=0.12.0`** (~700MB install). The project today does NOT have torch installed (only `onnxruntime 1.24.4` from faster-whisper's bundled `SileroVADModel` path). Adding standalone `silero-vad` to default `requirements.txt` would multiply the project's install size by an order of magnitude. Recommend treating silero-vad as **opt-in via `requirements-optional.txt`** with `detect_silence` raising a clean `RuntimeError("install: pip install -r requirements-optional.txt")` when torch is absent — and CONTEXT D-08's "no silence_map.json present → degrade to baseline-pass-only" path becomes the de-facto default for users who haven't opted in. PySceneDetect 0.6.7.1 has no such cost (pure pip + ffmpeg backend already on the project's machine).

The second finding is that **the silence-coverage check (D-07.b) is exactly second-by-second resolution** — interpreting "every flagged interval is covered" as set-theoretic coverage of `[interval.start, interval.end]` by the union of fps-segment intervals. Round-trip-safe with float arithmetic since segment boundaries in schedule.json are typed `float` (CONTEXT D-01). Algorithm is straightforward and given verbatim in §"Code Examples".

**Primary recommendation:** Build 04-01 first (scheduler + extract_frames_batch + validation), then 04-02 (detect_scenes + detect_silence). Make `silero-vad` opt-in. Keep `PySceneDetect` in default `requirements.txt`. Reuse `cmd_extract_frames`'s ffmpeg argv block via in-process function call — do NOT shell out to `python -m agent.tools extract_frames`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**`schedule.json` schema (FPS-01):**
- **D-01:** Top-level shape:
  ```json
  {
    "version": 1,
    "video": "video.mp4",
    "default_scale": "854:-1",
    "default_quality": 4,
    "segments": [
      {"start": 0,   "end": 30,  "fps": 0.2, "label": "intro"},
      {"start": 30,  "end": 240, "fps": 0.4, "label": "code-demo-part1"},
      {"start": 240, "end": 245, "skip": true, "label": "filler-question"},
      {"start": 245, "end": 600, "fps": 0.3, "label": "code-demo-part2"}
    ]
  }
  ```
- **D-02:** `version: 1` 强制必填; future v2 bump goes through `docs/schema-migration.md` runbook (Phase 1 D-05).
- **D-03:** `default_scale` / `default_quality` are segment-level defaults; segment-level OVERRIDE is **out of v1 scope**.
- **D-04:** `Schedule` dataclass at `agent/scheduler.py` with `from_json(path)` / `to_json(path)` / `validate()`; both top-level and per-segment are dataclasses; reuse `agent/io.py:write_json_atomic`.

**Validation strictness (FPS-02):**
- **D-05:** 5 mandatory checks — (1) `version == 1`; (2) full-duration coverage `[0, duration)` ± 2s tolerance, with duration from `agent/sources/_common.py:ffprobe_video`; (3) no overlap (`prev.end == curr.start` strict equality); (4) `fps` XOR `skip:true` (boolean literal `True` only — reject `"true"`/`1`); (5) no unknown keys at top-level OR per segment.
- **D-06:** `ScheduleValidationError(ValueError)` with segment index + field name in message.
- **D-07:** Silence-coverage strict-OR-fallback (FPS-04): EITHER (a) baseline pass exists (some segment with `start≤2 AND end≥duration-2 AND fps≤0.1`) OR (b) every silero-vad `flagged_for_review:true` (>5s) interval is fully covered by fps segments (NOT skip).
- **D-08:** When `silence_map.json` is absent, FPS-04 degrades to (a) only with loud warning: `"silence_map.json not found; FPS-04 enforces baseline-pass requirement only. Run detect_silence for tighter coverage."`

**`extract_frames_batch` CLI (FPS-03):**
- **D-09:** `python -m agent.tools extract_frames_batch --schedule output/<slug>/schedule.json --out output/<slug>/frames`. `--schedule` may also be positional.
- **D-10:** Iterate segments → for each non-skip segment, call existing `cmd_extract_frames` ffmpeg argv (don't rewrite). Filename convention `seg_<start>_<index>.jpg` preserved unchanged.
- **D-11:** Per-segment state.jsonl events: `started` before, `completed` after, with `details: {segment_index, start, end}`. Resume = compute set of completed `segment_index` values, skip them on rerun.
- **D-12:** `--force` flag bypasses resume (matches `cmd_transcribe` idiom).
- **D-13:** Per-segment ffmpeg failure → raise `RuntimeError(f"extract_frames_batch segment {idx} failed: ...")` + emit `failed` event; subsequent segments do NOT auto-continue (fail-loud).

**`cmd_extract_frames` UNCHANGED (FPS-07):**
- **D-14:** Existing single-segment CLI is the "补抽" finishing tool, complementary to the batch first-pass tool. No interface changes (Phase 3 D-23 already added `-vsync vfr` — that's the only delta this milestone allows).

**`detect_scenes` (FPS-05):**
- **D-15:** `python -m agent.tools detect_scenes <video> --out output/<slug>/scenes.json`. PySceneDetect with default threshold 27.0; `--threshold` flag may be exposed at planner discretion.
- **D-16:** Output shape: `{version:1, video:"...", scenes:[{start:0.0, end:12.5}, ...]}`.
- **D-17:** Tool NEVER auto-promotes scenes to schedule (K5). stdout reports total scene count + median segment duration.
- **D-18:** Add `PySceneDetect>=0.6.7.1` to `requirements.txt`.

**`detect_silence` (FPS-06):**
- **D-19:** `python -m agent.tools detect_silence <video> --out output/<slug>/silence_map.json`. Standalone silero-vad (NOT via faster-whisper).
- **D-20:** Output shape: `{version:1, video:"...", silence_intervals:[{start, end, duration, flagged_for_review:true_if_>5s}]}`.
- **D-21:** stdout hint to Claude: "Found N silence intervals; M flagged > 5s. When writing schedule.json, ensure each flagged interval is covered by an fps segment (NOT skip), or add a low-rate baseline pass per FPS-04."
- **D-22:** May require explicit pin `silero-vad>=5.1` if version conflicts arise.

**Module structure:**
- **D-23:** `agent/scheduler.py` — Schedule + Segment dataclasses + validate + apply_silence_coverage_check helper.
- **D-24:** Three new cmd_* in `agent/tools.py` cmds dict + argparse subparser.
- **D-25:** PySceneDetect logic may live in optional `agent/scenes.py`; silero-vad in optional `agent/silence.py`. Planner decides modular vs. inline.

**Phase 5 forward-compat:**
- **D-26:** `plan.md` (Phase 5 TEACH-04) is natural-language reasoning, NOT machine-readable; `schedule.json` is independent. Phase 4 makes no assumption about plan.md existence.

**Plans split (locked):**
- **D-27:** **04-01**: scheduler + extract_frames_batch + validation + resume (FPS-01/02/03/04/07).
- **D-28:** **04-02**: detect_scenes + detect_silence (FPS-05/06). Independent of 04-01 because D-08 degrades gracefully when silence_map.json is absent.

### Claude's Discretion

- PySceneDetect threshold default value + whether to expose `--threshold` flag
- Whether `silence_intervals` JSON contains `voice_activity` reverse-intervals (recommend NO, YAGNI)
- Whether `Schedule` dataclass provides `__post_init__` validate (recommend NO — explicit `.validate()` only)
- Whether to extract per-segment ffmpeg argv as helper function (recommend reuse `cmd_extract_frames` directly, no helper)
- `extract_frames_batch` stdout progress format (per-segment line vs. progress bar; recommend simple per-segment print, project's tqdm-free idiom)
- Whether detect_scenes / detect_silence cache results (YAGNI; tool is user-driven, sidecar machinery is for produced artifacts not diagnostic outputs)

### Deferred Ideas (OUT OF SCOPE)

- Auto-fps-plan from scenes + silence (anti-feature per K5 — never)
- Segment-level override of `default_scale` / `default_quality` (YAGNI; bump to v2 if real demand)
- Schedule.json v2 schema (defer until first failure-to-express)
- Progress bar / tqdm UI (CONVENTIONS no-tqdm idiom)
- schedule.json validation triggered at Write time (Claude Code has no Write hook)
- detect_scenes / detect_silence auto-trigger after transcribe (tool never auto-runs — K5)
- PySceneDetect threshold adaptive selection by content type (use default; expose flag for tuning)
- Multi-pass schedule refine (use cmd_extract_frames单段补抽 instead — D-14 finishing-pass model)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FPS-01 | `agent/scheduler.py` Schedule dataclass with JSON I/O matching locked schema | §"Standard Stack" — dataclass pattern (Phase 2 precedent); §"Code Examples" Schedule.from_json idiom |
| FPS-02 | Validation enforces full-duration coverage / no overlap / fps XOR skip / no unknown keys (fail loud) | §"Code Examples" — validate() implementation; §"Common Pitfalls P1" fail-loud parser; ffprobe_video reuse for duration |
| FPS-03 | `extract_frames_batch` CLI consumes schedule.json, emits frames, resume-aware via state.jsonl | §"Architecture Patterns" — segment-level state event; §"Code Examples" — derived_segment_state helper |
| FPS-04 | Silence-coverage strict-OR-fallback (baseline pass OR per-interval coverage) | §"Code Examples" — apply_silence_coverage_check; §"Common Pitfalls P3" silent visual undersampling |
| FPS-05 | `detect_scenes` emits scenes.json via PySceneDetect; Claude reads as decision support; tool never auto-promotes | §"Standard Stack" — PySceneDetect 0.6.7.1; §"Code Examples" — detect() invocation |
| FPS-06 | `detect_silence` emits silence_map.json via silero-vad; >5s gaps flagged | §"Standard Stack" — silero-vad 6.2.1 (or pin to ≥5.1); §"Code Examples" — invert speech_timestamps; §"Don't Hand-Roll" |
| FPS-07 | `cmd_extract_frames` single-segment CLI unchanged | §"Architecture Patterns" — keep ffmpeg argv as-is; verification = no diff in cmd_extract_frames body |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **¥0 hard constraint** — no paid LLM/ASR/Vision/Translation API. PySceneDetect (local-only) and silero-vad (local-only, with torch caveat below) both satisfy. [VERIFIED: CLAUDE.md §"项目概述"]
- **Claude is the唯一决策者** — tools never auto-promote scenes or silence into schedule.json. [VERIFIED: CLAUDE.md §"项目概述" + CONTEXT D-17]
- **Windows zh-CN baseline** — `chcp 65001` + `PYTHONUTF8=1` recommended; existing `ensure_ascii=True` print fallback retained. New cmd_* must respect both. [VERIFIED: CLAUDE.md §"Windows zh-CN 终端设置"]
- **`encoding="utf-8"` everywhere** — Phase 1 PRE-04 audit shipped. New scheduler.py / scenes.py / silence.py must keep this. [VERIFIED: CLAUDE.md §"历史背景"]
- **Backward-compat hard** — 17 archived `output/<slug>/` directories must keep re-running. schedule.json is opt-in additive; archives without it fall through unchanged. [VERIFIED: CLAUDE.md §"项目概述" + PROJECT.md K3]
- **Available tools** — `python -m agent.tools download/transcribe/aggregate/extract_frames/cleanup_frames` is the canonical CLI surface. New subcommands extend this dict; don't replace existing entries. [VERIFIED: agent/tools.py:621-633]

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `scenedetect[opencv]` | `0.6.7.1` | Scene-cut detection emitting scenes.json | Standard Python wrapper for content-aware scene detection; default opencv backend; supports Python 3.13. [VERIFIED: pip index versions = 0.6.7.1; PyPI release date 2025-09-25; CONTEXT D-18] |
| `silero-vad` | `6.2.1` (current) or pin to `>=5.1` | Speech/silence timeline for `detect_silence` | Standalone callable returning per-segment timestamps; bundled VAD inside faster-whisper does NOT expose timeline as a separate artifact. [VERIFIED: pip index versions; STACK.md §"Core Additions"] |
| `agent/io.py:ffprobe_video` | existing (Phase 3 D-21) | Duration probe for full-duration validation (D-05.2) | Already in `agent/sources/_common.py`; returns `duration_s` field. Reuse, don't re-invoke ffprobe directly. [VERIFIED: agent/sources/_common.py:121-129] |
| `agent/io.py:write_json_atomic` | existing (Phase 2 D-09) | Atomic write for scenes.json / silence_map.json | tempfile-in-target-dir + os.replace; sidecar produced for free. [VERIFIED: agent/io.py:106-159] |
| `agent/state.py` | existing (Phase 2 RES-05/06) | Append-only state.jsonl + derived_state reducer | `append_event` handles segment-level events as additive `details.segment_index` (Phase 2 D-14 explicitly leaves this room). [VERIFIED: agent/state.py:60-167] |

### Supporting (already in stack — keep)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `ffmpeg` | system PATH | extract_frames_batch ffmpeg invocation per segment | Phase 3 D-23 added `-vsync vfr` uniformly; reuse same argv assembly via in-process function call. [VERIFIED: agent/tools.py:335-349] |
| `Pillow` / `imagehash` | existing | NOT needed in Phase 4 (post-filter would be a future refinement) | Out of scope; documented for completeness. [VERIFIED: requirements.txt:6-7] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PySceneDetect | `ffmpeg -vf select='gt(scene\,0.4)'` raw filter | Simpler but parses stdout text; PySceneDetect returns typed `FrameTimecode` pairs which serialize cleanly to JSON. Default. [CITED: STACK.md §"Alternatives Considered"] |
| PySceneDetect | `scenecut-extractor` PyPI | Smaller wrapper; lacks adaptive detector. Default rejects since adaptive helps screen-recordings. [CITED: STACK.md] |
| silero-vad standalone | faster-whisper internal SileroVADModel | faster-whisper wraps silero internally for ASR-time filtering; does NOT expose `(start,end)` list. We need the standalone API for the silence-map artifact. [VERIFIED: `from faster_whisper.vad import SileroVADModel` is bundled but its outputs are not surfaced; STACK.md §"silero-vad standalone vs internal"] |
| silero-vad | `webrtcvad` / `pyannote.audio` segmenter | webrtcvad = noisy on real-world audio; pyannote pulls 700MB torch+models for diarization. silero is the lightweight VAD-only option. [CITED: STACK.md] |
| `ffprobe_video` | `cv2.VideoCapture` for duration | OpenCV reads container header but is unreliable on VFR videos; ffprobe is the project's canonical duration source (Phase 3 D-21). [VERIFIED: agent/sources/_common.py:115-119] |

**Installation:**
```bash
# Core (always required for Phase 4 batch + scenes)
pip install "scenedetect[opencv]>=0.6.7.1"

# Opt-in (for detect_silence — pulls torch ~700MB; see CRITICAL NOTE below)
pip install "silero-vad>=5.1"
```

**Version verification (run before locking requirements.txt):**
```bash
pip index versions scenedetect    # confirm 0.6.7.1 is current stable
pip index versions silero-vad     # confirm >=5.1 is available; 6.2.1 = current
```
[VERIFIED 2026-05-01: scenedetect 0.6.7.1 (released 2025-09-25), silero-vad 6.2.1 (released 2026-02-24)]

### CRITICAL: silero-vad's torch dependency

silero-vad 6.x `pyproject.toml` declares `torch>=1.12.0` + `torchaudio>=0.12.0` + `onnxruntime>=1.16.1` as install_requires. **This project does NOT currently have torch installed.** Adding silero-vad to default `requirements.txt` triggers a torch+torchaudio install (~700MB-1.5GB).

[VERIFIED via `pip show torch torchaudio` → both ModuleNotFoundError; `pip show ctranslate2 onnxruntime` → ctranslate2 4.7.1, onnxruntime 1.24.4 already present (transitive via faster-whisper)]

[VERIFIED via WebFetch + WebSearch on pyproject.toml: torch is mandatory in default install; "if you plan to run the VAD using solely the onnx-runtime, it will run...though you will have to adapt the existing wrappers, examples, and post-processing for your use-case"]

**Recommendations to planner (4 options, ranked):**

1. **Recommended — opt-in via `requirements-optional.txt`:** Add `silero-vad>=5.1` to a new `requirements-optional.txt` file (precedent: STACK.md §"Installation" already proposes this for pyannote.audio). `cmd_detect_silence` lazy-imports and emits clean `RuntimeError("detect_silence requires silero-vad. Install with: pip install -r requirements-optional.txt (note: pulls torch ~700MB)")` if missing. CONTEXT D-08's "no silence_map.json present → degrade to baseline-pass-only" path becomes the de-facto default for users who haven't opted in. **This preserves the project's lightweight-by-default ethos while keeping the feature available.** [ASSUMED: matches PROJECT.md "minimum new deps" stance — verify with user]

2. **Maintain CONTEXT D-22 spirit — pin to default `requirements.txt`:** Accept the torch cost. Pro: simpler install path; CONTEXT line 101 says silero-vad "已经在 requirements.txt (faster-whisper deps)" — but this claim is INCORRECT (faster-whisper bundles `SileroVADModel` internally via ctranslate2/onnxruntime; it does NOT install the standalone `silero-vad` PyPI package). Adding standalone silero-vad is a NEW dep with NEW torch. [VERIFIED via `pip show silero-vad` → not installed]

3. **Use ONNX-only path:** Manually load the ~2MB ONNX model and call `onnxruntime` directly, bypassing the silero-vad Python wrapper. Pro: no torch. Con: project must own the wrapper code (snakers4 explicitly says "you will have to adapt the existing wrappers"); brittle to upstream changes. [CITED: WebSearch result on silero-vad GitHub Wiki "Examples and Dependencies"]

4. **Reuse faster-whisper's bundled SileroVADModel:** Possible but means re-implementing speech-timestamps logic since faster-whisper consumes VAD output internally and doesn't surface intervals. ~50 LOC of careful glue. [VERIFIED: `from faster_whisper.vad import SileroVADModel` works; surfacing intervals requires re-implementing the post-processing silero-vad's standalone wrapper does for free]

**Strong recommendation: Option 1.** It honors both PROJECT.md's lightweight-deps stance and CONTEXT D-08's already-built degradation path. CONTEXT D-22's claim about silero-vad already being in deps is factually incorrect and should be corrected — flag this to the planner.

## Architecture Patterns

### Recommended Module Structure

```
agent/
├── scheduler.py        # Phase 4-01: Schedule + Segment dataclasses + validate + silence-coverage helper
├── scenes.py           # Phase 4-02: PySceneDetect wrapper (recommended split per CONTEXT D-25)
├── silence.py          # Phase 4-02: silero-vad wrapper (recommended split per CONTEXT D-25)
├── state.py            # EXTEND: derived_segment_state helper for resume (Phase 2 D-14 落地)
└── tools.py            # EXTEND: cmd_extract_frames_batch / cmd_detect_scenes / cmd_detect_silence
```

### Pattern 1: Schedule dataclass with explicit validate()

**What:** Mirror Phase 2's `Segment` (`src/asr.py:34`), `Paragraph` (`agent/asr_v2.py:15`), `FrameClassification` (`agent/pass1_classify.py:38`) idiom. `from __future__ import annotations` at top; `@dataclass` decorator; `from_json` / `to_json` / `validate` classmethods/methods.

**When to use:** All schedule.json reads/writes go through `Schedule.from_json(path)`. Validation is explicit — never `__post_init__` (CONTEXT Discretion: callers control timing).

**Example:**
```python
# agent/scheduler.py
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import json

from agent.io import write_json_atomic

class ScheduleValidationError(ValueError):
    """Locked per CONTEXT D-06."""
    pass

@dataclass
class Segment:
    start: float
    end: float
    fps: float | None = None
    skip: bool = False
    label: str | None = None

@dataclass
class Schedule:
    version: int
    video: str
    default_scale: str
    default_quality: int
    segments: list[Segment] = field(default_factory=list)

    @classmethod
    def from_json(cls, path: str | Path) -> "Schedule":
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        # Strict shape: catch unknown top-level keys per D-05.5
        allowed_top = {"version", "video", "default_scale", "default_quality", "segments"}
        unknown = set(obj.keys()) - allowed_top
        if unknown:
            raise ScheduleValidationError(
                f"unknown top-level keys: {sorted(unknown)} (allowed: {sorted(allowed_top)})"
            )
        # ... segment-level shape check before constructing Segment(**d) ...
        segments = [_load_segment(d, i) for i, d in enumerate(obj["segments"])]
        return cls(
            version=obj["version"],
            video=obj["video"],
            default_scale=obj["default_scale"],
            default_quality=obj["default_quality"],
            segments=segments,
        )

    def to_json(self, path: str | Path) -> None:
        # Reuse Phase 2 atomic-write — sidecar optional (per CONTEXT D-04 we
        # don't write sidecar for schedule.json since Claude Write tool is
        # the canonical author, but the to_json method exists for forward use).
        obj = {
            "version": self.version,
            "video": self.video,
            "default_scale": self.default_scale,
            "default_quality": self.default_quality,
            "segments": [{k: v for k, v in asdict(s).items() if v is not None and v is not False}
                         for s in self.segments],
        }
        write_json_atomic(path, obj)

    def validate(self, *, duration_s: float, silence_map: dict | None = None) -> None:
        """Run all 5 mandatory checks (D-05) plus FPS-04 silence coverage (D-07/D-08).

        Raises ScheduleValidationError on first failure with segment index + field name.
        """
        # Implementation in §"Code Examples" below.
        ...
```

### Pattern 2: Reuse cmd_extract_frames ffmpeg argv via in-process function call

**What:** `cmd_extract_frames_batch` does NOT shell out to `python -m agent.tools extract_frames`; it imports nothing-new but builds the argv inline OR refactors a small helper. Per CONTEXT D-10 + Discretion line 119: "cmd_extract_frames 已有逻辑, 复用即可, 不抽公共 helper".

**When to use:** Inside the iteration loop in `cmd_extract_frames_batch`, build the same ffmpeg argv that `cmd_extract_frames` does, with per-segment `start` / `end` / `fps` taken from the `Segment` object and `default_scale` / `default_quality` from the `Schedule` top-level.

**Example:**
```python
# Inside cmd_extract_frames_batch, after loading + validating schedule:
for i, seg in enumerate(schedule.segments):
    if seg.skip:
        continue
    if i in completed_indices and not args.force:
        log.info("segment %d already completed, skipping (use --force to redo)", i)
        continue

    _emit_event(state_dir, "extract_frames_batch", "started",
                details={"segment_index": i, "start": seg.start, "end": seg.end})
    try:
        cmd = ["ffmpeg", "-y"]
        if seg.start > 0:
            cmd += ["-ss", str(seg.start)]
        cmd += ["-i", str(video_path)]
        if seg.end > 0:
            cmd += ["-t", str(seg.end - max(seg.start, 0))]
        prefix = f"seg_{int(seg.start):04d}_"
        pattern = str(out_dir / f"{prefix}%06d.jpg")
        cmd += ["-vsync", "vfr",
                "-vf", f"fps={seg.fps},scale={schedule.default_scale}",
                "-q:v", str(schedule.default_quality), pattern]
        subprocess.run(cmd, check=True, capture_output=True)
        files = sorted(out_dir.glob(f"{prefix}*.jpg"))
        _emit_event(state_dir, "extract_frames_batch", "completed",
                    details={"segment_index": i, "start": seg.start, "end": seg.end,
                             "frames_count": len(files)})
        print(f"[seg {i}] {seg.start}s-{seg.end}s @ fps={seg.fps}: {len(files)} frames")
    except subprocess.CalledProcessError as e:
        _emit_event(state_dir, "extract_frames_batch", "failed",
                    details={"segment_index": i, "start": seg.start, "end": seg.end,
                             "error_type": type(e).__name__,
                             "error": (e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e))[:200]})
        raise RuntimeError(f"extract_frames_batch segment {i} failed: {e}") from e
```

### Pattern 3: Segment-level resume via state.jsonl

**What:** Phase 2 D-14 explicitly leaves `details.segment_index` as the additive resume key for Phase 4. Build a small reducer in `agent/state.py` that returns the set of completed segment indices for the `extract_frames_batch` stage.

**Recommendation (CONTEXT line 165):** Extend `agent/state.py` with `derived_segment_state(events, *, stage)` returning `set[int]` of segment indices with most-recent status `"completed"`. Reusable by Phase 5 if multi-pass is ever added.

**Example:**
```python
# agent/state.py — ADDITIVE; existing derived_state untouched.
def derived_segment_state(events: list[dict], *, stage: str) -> set[int]:
    """Return set of segment_index values with most-recent status 'completed' for given stage.

    Phase 4 落地 of Phase 2 D-14. Additive — does not change derived_state's stage-level dict shape.
    Consumers: cmd_extract_frames_batch resume path (D-11).

    A segment_index is "completed" if its most-recent event is status='completed'.
    A 'failed' or 'started' (no completed follow-up) event after a previous 'completed'
    means the segment is being re-attempted — drop it from the completed set.
    """
    state: dict[int, str] = {}  # segment_index -> latest status
    for ev in events:
        if ev.get("stage") != stage:
            continue
        details = ev.get("details") or {}
        idx = details.get("segment_index")
        if idx is None:
            continue
        state[idx] = ev.get("status")
    return {i for i, status in state.items() if status == "completed"}
```

[VERIFIED: Phase 2 D-13 schema explicitly types `details` as optional dict; segment_index is purely additive and compatible with existing derived_state which ignores `details` entirely (agent/state.py:140-166)]

### Pattern 4: Silence coverage check — set-theoretic

**What:** D-07 condition (b) reads "every silero-vad-flagged > 5s silence interval is covered by some fps segment (NOT skip)". This is set-theoretic interval coverage at second-level resolution.

**Algorithm:** For each `flagged_for_review:true` interval `[a, b]`:
1. Collect fps segments overlapping `[a, b]`: those with `seg.start < b AND seg.end > a AND not seg.skip AND seg.fps is not None`.
2. Compute their union restricted to `[a, b]`.
3. If union ≠ `[a, b]` → fail.

Since segment boundaries are typed `float` and CONTEXT D-05.3 enforces strict `prev.end == curr.start` equality, no real-coordinate set arithmetic is needed; sequential interval merging is sufficient. See §"Code Examples" for verbatim implementation.

### Anti-Patterns to Avoid

- **Auto-promote scenes/silence into schedule.json:** Anti-feature per K5 + CONTEXT D-17. Verification step in plan: `grep "scenes.json\|silence_map.json" agent/tools.py` should NOT match anywhere inside `cmd_extract_frames_batch`.
- **Shell out to `python -m agent.tools extract_frames`:** Subprocess overhead + harder error propagation + breaks state.jsonl event sequencing. Use in-process argv (Pattern 2).
- **Validate inside `__post_init__`:** Couples construction with validation; planner can't construct partially-valid schedules for testing. Use explicit `.validate(duration_s=..., silence_map=...)`.
- **Silently degrade a missing `version` field to 1:** D-05.1 says fail. (Phase 1 D-04 + 02-CONTEXT D-09 set this precedent — top-level dict artifacts must declare schema_version explicitly when introduced.)
- **Treat `skip: 1` or `skip: "true"` as truthy:** D-05.4 requires literal boolean `True`. Use `seg["skip"] is True` (identity check) or check `type(seg.get("skip")) is bool and seg["skip"] is True`.
- **Re-extract frames for already-completed segments without `--force`:** wastes time; D-11 resume contract requires skipping by `segment_index`.
- **Accept ffprobe failure silently in validation:** D-05.2 says raise clearly when `ffprobe_video` fails (re-raise its `RuntimeError`/`CalledProcessError` with a wrap message identifying the schedule.json path).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Scene-cut detection | Custom histogram-difference frame-by-frame loop in OpenCV | `scenedetect.detect(path, ContentDetector(threshold=27.0))` | PySceneDetect handles flash filters, weighted HSV component analysis, kernel-based filtering. Default config covers 90% of cases including animation/screen-recordings. [VERIFIED via PySceneDetect content_detector.py source — DEFAULT_COMPONENT_WEIGHTS, FlashFilter.MERGE mode] |
| Speech vs silence detection | webrtcvad + post-processing or naive RMS-energy threshold | `silero_vad.get_speech_timestamps(audio, model)` | Silero handles non-speech (music, applause), short pauses, multilingual speech. ~2MB JIT model, sub-1ms per 30ms frame on CPU. [VERIFIED: GitHub README "JIT model is around two megabytes in size"] |
| Video duration probe | Parse ffmpeg stderr regex for `Duration:` line | `agent/sources/_common.py:ffprobe_video()["duration_s"]` | Already shipped in Phase 3 D-21; uses ffprobe's structured JSON; handles HEVC/AV1 warning + audio-stream check + VFR detection in one call. [VERIFIED: agent/sources/_common.py:66-129] |
| JSON write atomicity | Naive `path.write_text(json.dumps(...))` | `agent/io.py:write_json_atomic(path, obj, sidecar_params=...)` | Phase 2 D-09/D-10 single-landing-point; tempfile + os.replace + 3x PermissionError retry already shipped. [VERIFIED: agent/io.py:106-159] |
| Resume state aggregation | New module to track which segments completed | `agent/state.py:derived_segment_state(events, stage="extract_frames_batch")` (extension) | Phase 2 D-14 reserved this slot. Reducer is pure; testable; reusable by Phase 5. [VERIFIED: state.py:140-166 signature + Phase 2 D-14 line 39 of 02-CONTEXT.md] |
| Silero VAD model wrapping | Manual ONNX-runtime call to silero model | `from silero_vad import load_silero_vad, get_speech_timestamps` | snakers4 explicitly says "you will have to adapt the existing wrappers, examples, and post-processing for your use-case" if going ONNX-only. Stick with the official wrapper unless the torch dep is a blocker (see §"CRITICAL: silero-vad's torch dependency"). [VERIFIED via WebSearch on snakers4/silero-vad wiki] |

**Key insight:** Every problem in this phase has a Python library or already-shipped helper. The only new logic that's truly project-specific is (a) the schedule.json validate() rules (and these are mechanical given CONTEXT D-05) and (b) the silence-coverage check (Pattern 4 — also mechanical).

## Runtime State Inventory

> Phase 4 is greenfield (new artifacts: schedule.json, scenes.json, silence_map.json) — not a rename/refactor. This section is included for completeness; most categories are "None".

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — all new artifacts under `output/<slug>/`; archived 17 directories don't have schedule.json so they fall through to existing `cmd_extract_frames` path. | None |
| Live service config | None — no external services touched. | None |
| OS-registered state | None — pure Python module additions. | None |
| Secrets/env vars | None — neither PySceneDetect nor silero-vad need API keys (¥0 ✓). | None |
| Build artifacts | If user installs `silero-vad`, will pull torch into site-packages (~700MB). One-time cost; no project artifact churn. | Document in `requirements-optional.txt` README/comment |

## Common Pitfalls

### Pitfall P1: Fail-loud parser dilution

**What goes wrong:** Validation logic accepts "version: '1'" (string) as 1, or `skip: 1` as True, or accepts unknown segment keys silently — and Claude's later schedule.json mistakes get silently absorbed instead of surfaced.
**Why it happens:** Defensive coding instinct ("be lenient on input, strict on output") is wrong here — schedule.json is Claude-authored code, mistakes ARE the signal.
**How to avoid:** D-05/D-06 are explicit. Use `obj["version"] == 1` not `int(obj.get("version", 1)) == 1`. Use `seg["skip"] is True` not `bool(seg.get("skip"))`. Compare keys with set difference for unknown-key check, not "missing-key tolerance". Test with deliberately malformed input.
**Warning signs:** Any test passes when it shouldn't (e.g., "I forgot to add a segment but validation passed"). [CITED: PITFALLS P2.3 + CONTEXT D-05 + D-06]

### Pitfall P2: Full-duration coverage tolerance edge case

**What goes wrong:** D-05.2 says "first segment.start ≤ 2s AND last segment.end ≥ duration - 2s AND no gaps > 0s between adjacent segments". Edge cases:
- (a) Video has 30s of silence/music at end (uploader's sign-off): paragraphs.json's last text ends at duration - 30s but the schedule has segments to duration - 30s. Validation FAILS because last segment.end < duration - 2s.
- (b) Video has 5s pre-roll silence: schedule starts at second 5 (Claude trimmed), validation FAILS because first segment.start > 2s.

**Why it happens:** Schedule reflects content boundaries, not container duration. ±2s tolerance assumes ASR/silence-detection is a tight bound; on real videos the gap is often 5-30s.

**How to avoid (per CONTEXT D-05.2 strict reading):** ±2s is the locked tolerance. If users hit this in practice, the answer is to **add a baseline-pass segment** covering the gap with `fps: 0.05` or `skip: true` — not to relax validation. The fail-loud message should clearly list which side (start/end) of duration coverage failed and by how much.

**Warning signs:** Real-world videos with intro/outro silence raise validation errors despite being substantively complete. If this happens repeatedly, it's a Phase 4-V2 (or later) signal — for now, surface clearly + document workaround. **Do not relax tolerance silently.** [CITED: PITFALLS P2.4 + CONTEXT D-05.2 lines 41-42]

### Pitfall P3: Silence-coverage interpretation drift

**What goes wrong:** D-07.b reads "every silence interval covered by an fps segment". Three valid interpretations:
- (i) Loose: at least one fps segment overlaps the interval at all (e.g., overlaps by 1 second of a 30s interval) — passes.
- (ii) Tight: union of overlapping fps segments fully covers `[interval.start, interval.end]` — strictest.
- (iii) Mixed: overlapping fps segments must cover ≥ 95% of interval duration.

**Recommendation per CONTEXT D-07 line 49 + ADDITIONAL_CONTEXT.5:** Interpretation (ii), tight. The intent (PITFALLS P2.1) is to prevent dropped PPT-page-flips inside silence; loose coverage doesn't deliver that.

**How to avoid:** Implement coverage as set-theoretic union check (Pattern 4 + §"Code Examples"). Document the algorithm in scheduler.py docstring. Test with: silence interval `[100, 110]` + segments `[(80, 105, fps=0.3), (115, 200, skip=True)]` should FAIL (only [100, 105] covered, [105, 110] not).

**Warning signs:** Schedule passes validation but Claude later reports "I missed the slide change at second 108" — coverage check was too loose. [CITED: PITFALLS P2.1 (showstopper severity) + CONTEXT D-07]

### Pitfall P4: PySceneDetect over-segmentation on screen-recordings

**What goes wrong:** Default threshold 27.0 is calibrated for film-style cuts. Screen recordings of code editors / PPTs / IDEs have constant micro-changes (cursor blink, syntax highlighting refresh) that may produce 200+ "scenes" in a 10-min video — useless decision support for Claude.
**Why it happens:** ContentDetector uses weighted HSV component analysis; UI animations score similarly to real cuts.
**How to avoid:** Default 27.0 is the documented standard but expose `--threshold` flag for tuning (CONTEXT D-15 explicitly allows planner to expose). For first-pass behavior on tutorial videos, threshold 27.0 is fine. Stdout reports "scenes total + median duration" so Claude can immediately tell if results are over-segmented (median < 2s = re-run with higher threshold). Alternative: `AdaptiveDetector(adaptive_threshold=3.0)` is more robust on camera motion / continuous changes. [CITED: WebSearch result on PySceneDetect threshold ranges + scenedetect.com docs §"Detection Algorithms"]
**Warning signs:** Median scene duration < 2s on a tutorial video → Claude can't use scenes.json effectively → re-run with `--threshold 35` or switch to `AdaptiveDetector`. Plan should document this in stdout hint.

### Pitfall P5: silero-vad audio sample-rate mismatch

**What goes wrong:** silero-vad accepts only 8kHz or 16kHz audio. The project's `audio.wav` is 16kHz mono (Phase 2-friendly), but `detect_silence` accepting an arbitrary `<video>` path requires extracting audio first.
**Why it happens:** `cmd_detect_silence <video>` ergonomics — user shouldn't need to extract audio manually.
**How to avoid:** `cmd_detect_silence` first checks for existing `output/<slug>/audio.wav` (already produced by `cmd_transcribe`). If present, use it directly. If not, run a small ffmpeg extract step (same as `src/asr.py:extract_audio`) into a temp file. Pass the wav file to `silero_vad.read_audio()` which handles loading. [VERIFIED: silero-vad README "supports 8000 Hz and 16000 Hz sampling rates"; existing extract_audio in src/asr.py]
**Warning signs:** silero-vad raises `ValueError: invalid sample rate` or returns empty timestamps on a wrong-rate input.

### Pitfall P6: Re-running extract_frames_batch deletes other-segment frames

**What goes wrong:** ffmpeg with `-y` overwrites; if the `seg_<start>_<index>.jpg` filename collides between two segments (e.g., both happen to start at second 0030 due to misconfiguration), the second wipes the first.
**Why it happens:** Filename grammar uses `int(start):04d` as prefix. Two segments with `start=30.0` and `start=30.4` both produce prefix `seg_0030_`.
**How to avoid:** D-05.3 (no overlap, prev.end == curr.start strict) prevents this AT VALIDATION TIME — two segments cannot both start at second 30. Add a sanity check at the start of `cmd_extract_frames_batch` after validate(): assert all `int(seg.start)` values are distinct. Or use higher-resolution prefix (e.g., `int(seg.start * 10):05d`) — but that breaks the existing `seg_<start>_<index>.jpg` filename grammar (FPS-07 requirement).
**Warning signs:** Final frame count for two adjacent segments is way lower than expected — last segment overwrote previous segment's frames. [VERIFIED: existing pattern in agent/tools.py:342]

### Pitfall P7: silero-vad inversion off-by-one

**What goes wrong:** `get_speech_timestamps` returns SPEECH intervals; we want SILENCE. Naive inversion: silence = `[(speech[i].end, speech[i+1].start) for i in range(len(speech)-1)]`. This misses leading silence (before first speech) and trailing silence (after last speech).
**Why it happens:** Edge intervals are easy to forget.
**How to avoid:**
```python
def invert_speech_to_silence(speech_ts: list[dict], duration_s: float) -> list[dict]:
    """Return silence intervals = gaps between speech intervals + leading/trailing."""
    silences = []
    cursor = 0.0
    for s in speech_ts:
        if s["start"] > cursor:
            silences.append({"start": cursor, "end": s["start"]})
        cursor = max(cursor, s["end"])
    if cursor < duration_s:
        silences.append({"start": cursor, "end": duration_s})
    return silences
```
**Warning signs:** silence_map.json's first interval has `start: speech[0].end` instead of `start: 0.0` → leading silence dropped → first segment of video gets no `flagged_for_review` even when it's a 30s intro. [VERIFIED: pattern is standard interval-inversion logic]

### Pitfall P8: PySceneDetect ffmpeg subprocess CWD on Windows zh-CN

**What goes wrong:** PySceneDetect default backend (opencv) reads video directly via OpenCV's VideoCapture, BUT it shells out to ffmpeg internally for some operations. If ffmpeg path contains spaces or CJK, those operations fail.
**Why it happens:** Windows zh-CN locale + non-ASCII paths in cwd. Phase 3 already broadly addressed via SRC-10 (CJK-safe slug rejection at --out boundary) + ffmpeg argv-as-list pattern.
**How to avoid:** Phase 3's `_validate_out_path()` only guards `--out`; PySceneDetect is given `<video>` positional. As long as the user runs from `output/<slug>/` (ASCII-safe slug enforced by Phase 3 SRC-09/10), the input path stays ASCII. Document this in `cmd_detect_scenes` docstring: "video path must be ASCII-safe (use output/<slug>/video.mp4 written by cmd_ingest)".
**Warning signs:** PySceneDetect errors on CJK-named manually-placed video files. Documented mitigation: route through `cmd_ingest` which copies to ASCII-safe slug. [CITED: PITFALLS P4.1 + Phase 3 D-18/D-19]

## Code Examples

Verified patterns ready for the planner to lift into PLAN.md:

### Schedule.validate() — full implementation

```python
# agent/scheduler.py
def validate(self, *, duration_s: float, silence_map: dict | None = None) -> None:
    """5 mandatory checks (D-05) + FPS-04 silence-coverage (D-07/D-08).

    duration_s: from ffprobe_video(video_path)["duration_s"]
    silence_map: parsed silence_map.json content, or None when absent (D-08 fallback)
    """
    # D-05.1: version
    if self.version != 1:
        raise ScheduleValidationError(
            f"unsupported schedule version: {self.version!r} (only 1 supported in Phase 4; "
            f"future versions go through docs/schema-migration.md)"
        )

    # D-05.2: full-duration coverage ± 2s
    if not self.segments:
        raise ScheduleValidationError("schedule has no segments")
    first, last = self.segments[0], self.segments[-1]
    if first.start > 2.0:
        raise ScheduleValidationError(
            f"first segment must start ≤ 2s; got start={first.start} (D-05.2 ±2s tolerance)"
        )
    if last.end < duration_s - 2.0:
        raise ScheduleValidationError(
            f"last segment must end ≥ duration - 2s; got end={last.end}, "
            f"duration={duration_s} (D-05.2 ±2s tolerance)"
        )

    # D-05.3: no overlap, no gap (strict equality at boundaries)
    for i in range(len(self.segments) - 1):
        prev, curr = self.segments[i], self.segments[i + 1]
        if prev.end != curr.start:
            raise ScheduleValidationError(
                f"segment {i} (end={prev.end}) and segment {i+1} (start={curr.start}) "
                f"must have prev.end == curr.start; "
                f"{'overlap' if prev.end > curr.start else 'gap'} of {abs(prev.end - curr.start)}s "
                f"(D-05.3)"
            )

    # D-05.4: fps XOR skip — already enforced at parse time in _load_segment;
    # double-check here for paranoia.
    for i, seg in enumerate(self.segments):
        has_fps = seg.fps is not None
        has_skip = seg.skip is True  # identity check — reject 1, "true", etc.
        if has_fps == has_skip:  # both True or both False is a violation
            raise ScheduleValidationError(
                f"segment {i}: must have exactly one of `fps` or `skip:true` "
                f"(got fps={seg.fps!r}, skip={seg.skip!r}) — D-05.4"
            )

    # D-05.5: unknown keys — already enforced at parse time in from_json + _load_segment.

    # D-07/D-08: silence coverage (FPS-04)
    self._check_silence_coverage(duration_s, silence_map)

def _check_silence_coverage(self, duration_s: float, silence_map: dict | None) -> None:
    """FPS-04 strict-OR-fallback per D-07/D-08."""
    has_baseline_pass = any(
        seg.fps is not None and seg.fps <= 0.1
        and seg.start <= 2.0 and seg.end >= duration_s - 2.0
        for seg in self.segments
    )

    if silence_map is None:
        # D-08 degraded mode
        if not has_baseline_pass:
            raise ScheduleValidationError(
                "FPS-04: no silence_map.json found, baseline pass missing. "
                "Either run `python -m agent.tools detect_silence <video>` for tighter coverage, "
                "OR add a baseline segment with fps ≤ 0.1 spanning the full video."
            )
        log.warning(
            "silence_map.json not found; FPS-04 enforces baseline-pass requirement only. "
            "Run detect_silence for tighter coverage."
        )
        return

    if has_baseline_pass:
        return  # D-07 condition (a) satisfied

    # D-07 condition (b): every flagged interval covered by fps segments
    flagged = [iv for iv in silence_map.get("silence_intervals", [])
               if iv.get("flagged_for_review") is True]
    fps_segments = [seg for seg in self.segments
                    if seg.fps is not None and not seg.skip]

    for iv in flagged:
        if not _interval_covered(iv["start"], iv["end"], fps_segments):
            raise ScheduleValidationError(
                f"FPS-04: silence interval [{iv['start']}, {iv['end']}] (>5s) "
                f"is not fully covered by fps segments. Either add baseline pass "
                f"(fps ≤ 0.1 spanning full video) or extend an fps segment to cover it."
            )

def _interval_covered(a: float, b: float, fps_segments: list[Segment]) -> bool:
    """True iff union of fps_segments restricted to [a, b] equals [a, b]."""
    # Sort + collect overlapping segments
    overlapping = sorted(
        [(max(seg.start, a), min(seg.end, b))
         for seg in fps_segments
         if seg.start < b and seg.end > a],
        key=lambda x: x[0],
    )
    # Merge + check union covers [a, b]
    cursor = a
    for s, e in overlapping:
        if s > cursor:
            return False  # gap
        cursor = max(cursor, e)
    return cursor >= b
```

### detect_scenes implementation

```python
# agent/scenes.py (recommended split per CONTEXT D-25)
from __future__ import annotations
from pathlib import Path
import logging

from scenedetect import detect, ContentDetector

log = logging.getLogger(__name__)

def detect_scenes(video_path: str | Path, *, threshold: float = 27.0) -> list[dict]:
    """Run PySceneDetect ContentDetector. Returns list of {start, end} in seconds.

    Default threshold 27.0 per PySceneDetect documentation; tutorial / screen-recording
    videos may need 30-40 to suppress micro-changes. Expose via --threshold flag.
    """
    raw = detect(str(video_path), ContentDetector(threshold=threshold))
    return [
        {"start": float(start.get_seconds()), "end": float(end.get_seconds())}
        for start, end in raw
    ]
```

```python
# agent/tools.py — cmd_detect_scenes
def cmd_detect_scenes(args):
    """Phase 4-02 FPS-05. Decision support; tool NEVER auto-promotes scenes to schedule (K5)."""
    from agent.scenes import detect_scenes
    from agent.io import write_json_atomic

    out = Path(args.out)
    _validate_out_path(out)  # Phase 3 SRC-10 idiom

    log.info("running PySceneDetect on %s (threshold=%.1f)", args.video, args.threshold)
    scenes = detect_scenes(args.video, threshold=args.threshold)

    obj = {"version": 1, "video": Path(args.video).name, "scenes": scenes}
    write_json_atomic(out, obj)

    median = (
        sorted(s["end"] - s["start"] for s in scenes)[len(scenes) // 2]
        if scenes else 0.0
    )
    print(f"detected {len(scenes)} scenes; median duration = {median:.1f}s")
    print(f"output: {out}")
```

### detect_silence implementation

```python
# agent/silence.py (recommended split per CONTEXT D-25)
from __future__ import annotations
from pathlib import Path
import logging

log = logging.getLogger(__name__)

def detect_silence(audio_path: str | Path, *, duration_s: float,
                   flag_threshold_s: float = 5.0) -> list[dict]:
    """Run silero-vad. Returns silence intervals (gaps between speech).

    >flag_threshold_s seconds get flagged_for_review:true per D-20.

    Lazy-imports silero_vad so missing-package error has a clean recovery hint.
    """
    try:
        from silero_vad import load_silero_vad, read_audio, get_speech_timestamps
    except ImportError as e:
        raise RuntimeError(
            "detect_silence requires silero-vad. Install with: "
            "pip install -r requirements-optional.txt "
            "(note: pulls torch ~700MB)"
        ) from e

    model = load_silero_vad()
    wav = read_audio(str(audio_path))
    speech_ts = get_speech_timestamps(wav, model, return_seconds=True)
    # Normalize to dicts of float (silero may return tensors)
    speech_ts = [{"start": float(t["start"]), "end": float(t["end"])} for t in speech_ts]

    # Invert (Pitfall P7-safe)
    silences = []
    cursor = 0.0
    for s in speech_ts:
        if s["start"] > cursor:
            silences.append({"start": cursor, "end": s["start"]})
        cursor = max(cursor, s["end"])
    if cursor < duration_s:
        silences.append({"start": cursor, "end": duration_s})

    # Add duration + flag
    for iv in silences:
        iv["duration"] = iv["end"] - iv["start"]
        if iv["duration"] > flag_threshold_s:
            iv["flagged_for_review"] = True
    return silences
```

```python
# agent/tools.py — cmd_detect_silence
def cmd_detect_silence(args):
    """Phase 4-02 FPS-06. Decision support; emits silence_map.json for FPS-04 coverage check."""
    from agent.sources._common import ffprobe_video
    from agent.silence import detect_silence
    from agent.io import write_json_atomic

    out = Path(args.out)
    _validate_out_path(out)

    # Need duration to invert speech→silence properly
    info = ffprobe_video(args.video)
    duration_s = info["duration_s"]
    if duration_s <= 0:
        raise RuntimeError(f"could not determine duration of {args.video}; ffprobe returned 0")

    # Audio: prefer existing <slug>/audio.wav (Phase 2 transcribe artifact);
    # else extract on the fly.
    slug_dir = Path(args.video).parent
    audio_wav = slug_dir / "audio.wav"
    if not audio_wav.exists():
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from src.asr import extract_audio
        log.info("extracting audio for VAD (no audio.wav found)")
        extract_audio(args.video, audio_wav)

    intervals = detect_silence(audio_wav, duration_s=duration_s)
    flagged = [iv for iv in intervals if iv.get("flagged_for_review")]

    obj = {"version": 1, "video": Path(args.video).name, "silence_intervals": intervals}
    write_json_atomic(out, obj)

    # D-21 LOCKED stdout hint
    print(
        f"Found {len(intervals)} silence intervals; {len(flagged)} flagged > 5s. "
        f"When writing schedule.json, ensure each flagged interval is covered by an "
        f"fps segment (NOT skip), or add a low-rate baseline pass per FPS-04."
    )
    print(f"output: {out}")
```

### `cmd_extract_frames_batch` — top-level shape

```python
# agent/tools.py
def cmd_extract_frames_batch(args):
    """Phase 4-01 FPS-03. Resume-aware schedule-driven batch extractor."""
    from agent.scheduler import Schedule, ScheduleValidationError
    from agent.sources._common import ffprobe_video

    schedule_path = Path(args.schedule)
    out_dir = Path(args.out)
    _validate_out_path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    schedule = Schedule.from_json(schedule_path)
    # Resolve video path against schedule.json's parent (D-26 — relative path semantics)
    video_path = (schedule_path.parent / schedule.video).resolve()
    if not video_path.exists():
        raise RuntimeError(f"schedule.video {schedule.video!r} resolved to "
                           f"{video_path}, which does not exist")

    info = ffprobe_video(video_path)
    duration_s = info["duration_s"]

    # Optional silence_map.json sibling
    silence_map = None
    silence_path = schedule_path.parent / "silence_map.json"
    if silence_path.exists():
        silence_map = json.loads(silence_path.read_text(encoding="utf-8"))

    schedule.validate(duration_s=duration_s, silence_map=silence_map)

    # Resume: state.jsonl lives one level up from frames/
    state_dir = out_dir.parent
    events, status = read_events(state_dir / "state.jsonl")
    if args.force:
        completed = set()
        log.warning("--force specified: ignoring resume state, re-extracting all segments")
    else:
        from agent.state import derived_segment_state
        completed = derived_segment_state(events, stage="extract_frames_batch")
        if completed:
            log.info("resume: skipping %d already-completed segments: %s",
                     len(completed), sorted(completed))

    # Iteration loop — see Pattern 2 above for inner body.
    ...
```

### Schedule.json `video` field path resolution (Q10)

Per CONTEXT D-01 example uses `"video": "video.mp4"` (relative). cmd_extract_frames_batch resolves via `Path(schedule_path).parent / schedule.video`. Reasoning: Claude writes schedule.json adjacent to video.mp4 in `output/<slug>/`; relative path keeps slug directories self-contained and movable. Document this in scheduler.py docstring: "schedule.video is resolved relative to the schedule.json file's directory".

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-segment manual `extract_frames` calls per time range | `extract_frames_batch` reads schedule.json + iterates | This phase | First-pass batch extraction; single-segment retained for补抽 (D-14) |
| Claude reads paragraphs.json only when planning fps | Claude reads paragraphs.json + scenes.json + silence_map.json (decision support) | This phase | Fewer "I missed the slide change" failure modes (P2.1) |
| File-existence cache for resume | state.jsonl segment-level events + `derived_segment_state(events, stage)` reducer | This phase (落地 Phase 2 D-14) | Resume mid-batch without losing completed segments |
| `youtube-dl` for video sources | `yt-dlp >= 2026.03.17` (Phase 3) | Phase 3 | (Out of scope — already shipped) |

**Deprecated/outdated (none for Phase 4 — all libraries are current):**

- silero-vad 4.x had a slightly different API (`get_speech_timestamps` accepted `model.get_speech_ts` calls); 5.x+ is the current standalone wrapper. We pin `>=5.1`. [VERIFIED via WebFetch silero-vad pyproject + GitHub releases]
- PySceneDetect 0.5.x used different module paths (`scenedetect.detectors.ContentDetector` instead of top-level `from scenedetect import ContentDetector`). 0.6.x is current; the simple `detect()` API only exists in 0.6.x. [VERIFIED via WebFetch scenedetect.com docs]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Recommendation to make silero-vad opt-in (Option 1 in §"CRITICAL: silero-vad's torch dependency") aligns with PROJECT.md "minimum new deps" stance | §"Standard Stack" + §"CRITICAL" | If user prefers Option 2 (default install), ~700MB torch lands in default install path; should surface to user before locking requirements.txt structure |
| A2 | Silence-coverage interpretation is "tight" (set-theoretic union covers exactly) per Pitfall P3 interpretation (ii) | Pattern 4 + §"Code Examples" `_interval_covered` | If user wants loose coverage (≥95% / any-overlap), validation false-rejects valid schedules and Claude has to add unnecessary baseline pass; minor cost |
| A3 | Claude writes schedule.json relative to its own directory, so `schedule.video = "video.mp4"` resolves via `schedule_path.parent / schedule.video` | §"Code Examples" — schedule.json `video` field | If user expects absolute paths or `--video` CLI flag, command ergonomics differ; trivial fix |
| A4 | Single-segment ffmpeg failure cleanup is unnecessary because `seg_<start>_<index>.jpg` is deterministic — re-run overwrites with `-y` flag | Pitfall P6 + Q7 | If two segments share `int(start)`, second wipes first; D-05.3 prevents this AT VALIDATION TIME so risk is theoretical only |
| A5 | PySceneDetect default threshold 27.0 is acceptable for tutorial videos; expose `--threshold` flag at planner discretion | Pitfall P4 + CONTEXT D-15 | If 27.0 over-segments most videos in user's queue, planner reverts to higher default (35) before shipping |
| A6 | CONTEXT line 101's claim "silero-vad 已经在 requirements.txt (faster-whisper deps)" is factually incorrect | §"CRITICAL" + §"Standard Stack" | If accepted as-is by planner, planner adds silero-vad to default requirements.txt without flagging the torch cost; user surprise on first install |
| A7 | `Path(schedule_path).parent / schedule.video` is the right path-resolution model (matches schedule.json colocated with video.mp4) | §"Code Examples" + Q10 | If user has schedule.json elsewhere (e.g., in a separate planning dir), command needs a `--video <path>` override; trivial addition |

**Action for planner:** Surface A1 and A6 to user during plan-checker review. Both are decisions about whether silero-vad goes into default `requirements.txt` (CONTEXT D-22 spirit) or `requirements-optional.txt` (this research's recommendation). The right answer depends on user's stance toward project install size.

## Open Questions

1. **silero-vad: opt-in or default install?**
   - What we know: silero-vad >=5.1 hard-depends on torch (~700MB). Project currently has no torch.
   - What's unclear: whether user prefers a heavy default install (CONTEXT D-22) or lightweight default + opt-in (this research's Option 1).
   - Recommendation: bring this to plan-checker review. Default to Option 1 unless user objects.

2. **PySceneDetect threshold default for the project's video queue?**
   - What we know: 27.0 is the documented default; lower = more sensitive, higher = less.
   - What's unclear: whether the user's queue of game-tutorial / AI-UI videos behaves more like film or like UI animation.
   - Recommendation: ship 27.0 default + `--threshold` flag; reassess after 2-3 real videos.

3. **Should `_validate_out_path` apply to schedule.json's video field too?**
   - What we know: D-19 SRC-10 protects --out args; doesn't apply to JSON content fields.
   - What's unclear: whether a user could embed CJK in `schedule.video` and break ffmpeg subprocess.
   - Recommendation: rely on Phase 3 SRC-09's ASCII-safe slug enforcement. If `schedule.video` is relative within an ASCII-safe `output/<slug>/`, the resolved path is ASCII-safe. Document; don't re-validate.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | All | ✓ | 3.13.12 (Anaconda) | — |
| ffmpeg + ffprobe | extract_frames_batch (existing); detect_silence audio extract | ✓ (Phase 3) | system PATH | — |
| `faster-whisper` | extract_audio fallback path inside detect_silence | ✓ | 1.2.1 | — |
| `ctranslate2` | faster-whisper transitive | ✓ | 4.7.1 | — |
| `onnxruntime` | faster-whisper transitive | ✓ | 1.24.4 | — |
| `agent.io.write_json_atomic` | All new artifacts | ✓ | (Phase 2 shipped) | — |
| `agent.state.append_event/derived_state/read_events` | Resume infrastructure | ✓ | (Phase 2 shipped) | — |
| `agent.sources._common.ffprobe_video` | Schedule duration validation; detect_silence duration | ✓ | (Phase 3 shipped) | — |
| `scenedetect` (PyPI) | detect_scenes | ✗ | — | None — must `pip install scenedetect[opencv]>=0.6.7.1` |
| `silero-vad` (PyPI) | detect_silence | ✗ | — | If declined: D-08 fallback (baseline-pass-only validation); detect_silence cmd raises RuntimeError with install hint |
| `torch` (transitive of silero-vad) | detect_silence | ✗ | — | None on installed path; ~700MB cost on first install |

**Missing dependencies with no fallback:**
- `scenedetect[opencv]` — required for FPS-05; must be added to `requirements.txt` per CONTEXT D-18

**Missing dependencies with fallback:**
- `silero-vad` — without it, FPS-06's `detect_silence` raises clean install hint; FPS-04 silence-coverage degrades to baseline-pass-only path (D-08); user can still produce summaries with a baseline-pass-only schedule

**Note for planner:** First plan run on a fresh machine will need:
```bash
pip install "scenedetect[opencv]>=0.6.7.1"
# Optional, only if user wants silence detection:
pip install "silero-vad>=5.1"  # pulls torch + torchaudio
```

## Sources

### Primary (HIGH confidence)

- `D:\gxy_code\videoSummary\agent\tools.py` — current cmd_extract_frames body (lines 322-364) for argv reuse pattern; cmds dict (621-633) and argparse subparsers (568-614) for new cmd_* registration points
- `D:\gxy_code\videoSummary\agent\state.py` — append_event signature (60-96), derived_state contract (140-166), `details: dict | None` is additive
- `D:\gxy_code\videoSummary\agent\io.py` — write_json_atomic (106-159), read_sidecar (167-175), ffmpeg/faster-whisper version probes (260-287)
- `D:\gxy_code\videoSummary\agent\sources\_common.py` — ffprobe_video returns `duration_s` (66-129)
- `D:\gxy_code\videoSummary\.planning\phases\02-resume-infrastructure-cache-correctness\02-CONTEXT.md` — D-13 event schema, D-14 segment-level event reservation
- `D:\gxy_code\videoSummary\.planning\phases\03-source-refactor-new-sources-youtube-local-mp4-generic\03-CONTEXT.md` — D-21 ffprobe_video, D-23 -vsync vfr already applied
- `D:\gxy_code\videoSummary\.planning\research\STACK.md` — silero-vad standalone vs internal, PySceneDetect 0.6.7.1 pin, opt-in pattern for heavy deps
- `D:\gxy_code\videoSummary\.planning\research\PITFALLS.md` — P2.1 (silence undersampling), P2.3 (fail-loud parser), P2.4 (full-duration coverage)
- `D:\gxy_code\videoSummary\.planning\research\SUMMARY.md` — Locked schedule.json schema (lines 89-104) + Phase 4 validation rules (105-114)
- [PySceneDetect 0.6.7.1 ContentDetector source — GitHub](https://github.com/Breakthrough/PySceneDetect/blob/main/scenedetect/detectors/content_detector.py) — confirmed default threshold 27.0
- [PySceneDetect Python API docs — scenedetect.com](https://www.scenedetect.com/docs/latest/api.html) — confirmed `detect(path, ContentDetector())` returns `[(FrameTimecode, FrameTimecode)]`; `get_seconds()` method available
- [silero-vad GitHub utils_vad.py](https://github.com/snakers4/silero-vad/blob/master/src/silero_vad/utils_vad.py) — confirmed `get_speech_timestamps(audio, model, return_seconds=True)` returns `list[{"start", "end"}]`
- [silero-vad PyPI 6.2.1](https://pypi.org/project/silero-vad/) — confirmed current version + torch dependency

### Secondary (MEDIUM confidence)

- [PySceneDetect threshold range guidance — Detection Algorithms doc](https://www.scenedetect.com/docs/latest/api/detectors.html) — verified ContentDetector vs AdaptiveDetector; default 27.0; no explicit project-content recommendations
- [silero-vad ONNX-only path — GitHub Wiki](https://github.com/snakers4/silero-vad/wiki/Examples-and-Dependencies) — confirms torch dep is in default install; ONNX path requires user-owned wrapper code (non-trivial)
- [WebSearch result: PySceneDetect threshold 27.0 default + sensitivity ranges](https://github.com/Breakthrough/PySceneDetect/issues/153) — community guidance on threshold tuning for screen recordings

### Tertiary (LOW confidence)

- None — all critical claims are verified against source code or official docs.

## Metadata

**Confidence breakdown:**
- Standard stack (PySceneDetect / silero-vad versions + APIs): HIGH — verified against PyPI + upstream source code in this session
- Architecture (module split, state.py extension, io.py reuse): HIGH — Phase 2/3 already-shipped code is the ground truth
- Pitfalls (P1-P8): HIGH — locked by CONTEXT decisions + project-level PITFALLS.md research
- Silence-coverage interpretation: MEDIUM — three valid readings of D-07.b; I picked "tight" (set-theoretic union) as best aligned with PITFALLS P2.1 intent — flag in Q1/A2
- silero-vad torch cost: HIGH — verified via local `pip show torch` (not installed) + WebFetch on pyproject.toml + WebSearch on snakers4 wiki
- CONTEXT D-22's "silero-vad already in requirements.txt" claim being incorrect: HIGH — `pip show silero-vad` returns ModuleNotFoundError; `requirements.txt` has only faster-whisper which bundles `SileroVADModel` internally without installing the standalone package

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 (30 days; PySceneDetect is stable, silero-vad churns ~quarterly — re-verify silero-vad version + torch dep before integration)
