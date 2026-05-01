"""Schedule + Segment dataclasses + strict validation for schedule.json.

Phase 4 FPS-01/02/04 落地. Implements the locked schema (D-01..D-04), the 5
mandatory validation checks (D-05/D-06), and the silence-coverage strict-OR-
fallback gate (D-07/D-08).

Schedule.json is Claude-authored (per CONTEXT.md K5: "Claude is decider"). The
tool's job is to load + strict-validate + run ffmpeg per segment — never to
generate or modify segments. detect_scenes / detect_silence emit decision-
support artifacts; this module accepts silence_map.json as a *validation input*
only (never to auto-promote).

Validation philosophy (PITFALLS P2.3, locked at D-05/D-06):
- Fail loud on every malformed input. schedule.json is Claude-authored code;
  silent acceptance hides Claude's mistakes.
- No __post_init__ — validation is explicit `.validate(duration_s=, silence_map=)`
  so callers control timing (e.g., constructing partially-valid schedules in
  tests is allowed; running ffmpeg on them is not).

References:
- .planning/phases/04-frame-fps-automation-schedule-json-extract-frames-batch/04-CONTEXT.md
  (D-01 schema, D-05 mandatory checks, D-06 ScheduleValidationError, D-07/D-08
  silence-coverage strict-OR-fallback)
- .planning/phases/04-frame-fps-automation-schedule-json-extract-frames-batch/04-RESEARCH.md
  (Pattern 1, Pattern 4, Pitfalls P1/P2/P3/P6)
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path

from agent.io import write_json_atomic

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (locked by CONTEXT D-05/D-07)
# ---------------------------------------------------------------------------

_ALLOWED_TOP_KEYS = frozenset({"version", "video", "default_scale", "default_quality", "segments"})
_ALLOWED_SEG_KEYS = frozenset({"start", "end", "fps", "skip", "label"})
_DURATION_TOLERANCE_S = 2.0  # D-05.2 ±2s coverage tolerance
_BASELINE_FPS_MAX = 0.1  # D-07.a baseline pass max fps


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class ScheduleValidationError(ValueError):
    """Locked per CONTEXT D-06; carries segment index + field name in message."""
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

    # ---- I/O ----

    @classmethod
    def from_json(cls, path: str | Path) -> "Schedule":
        """Load + strict shape-check schedule.json. Raises ScheduleValidationError
        on unknown top-level or per-segment keys (D-05.5) or fps XOR skip parse-
        time violations (D-05.4 identity check on `skip`).

        Note: full validation (duration coverage, silence coverage, version
        check) lives in `.validate()` and is explicit (per CONTEXT Discretion
        line 119: no __post_init__).
        """
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ScheduleValidationError(
                f"schedule.json must be a dict; got {type(obj).__name__} at {path}"
            )

        # D-05.5: top-level unknown keys (catch typos / wrong shape)
        unknown_top = set(obj) - _ALLOWED_TOP_KEYS
        if unknown_top:
            raise ScheduleValidationError(
                f"unknown top-level keys: {sorted(unknown_top)} "
                f"(allowed: {sorted(_ALLOWED_TOP_KEYS)})"
            )

        # Required fields — KeyError -> ScheduleValidationError with locator
        try:
            version = obj["version"]
            video = obj["video"]
            default_scale = obj["default_scale"]
            default_quality = obj["default_quality"]
            segments_raw = obj["segments"]
        except KeyError as e:
            raise ScheduleValidationError(
                f"schedule.json missing required top-level key: {e.args[0]!r} "
                f"(required: {sorted(_ALLOWED_TOP_KEYS)})"
            ) from e

        if not isinstance(segments_raw, list):
            raise ScheduleValidationError(
                f"`segments` must be a list; got {type(segments_raw).__name__}"
            )

        segments = [_load_segment(d, i) for i, d in enumerate(segments_raw)]
        return cls(
            version=version,
            video=video,
            default_scale=default_scale,
            default_quality=default_quality,
            segments=segments,
        )

    def to_json(self, path: str | Path) -> None:
        """Write schedule.json via atomic-write (Phase 2 D-09).

        No sidecar — schedule.json is Claude-authored per CONTEXT D-04, not a
        derived artifact subject to cache-decision logic. The to_json method
        exists for forward use (e.g., test fixtures generating schedules
        programmatically).

        Optional / falsy fields (`fps=None`, `skip=False`, `label=None`) are
        omitted to keep output symmetric with the documented input shape.
        """
        obj = {
            "version": self.version,
            "video": self.video,
            "default_scale": self.default_scale,
            "default_quality": self.default_quality,
            "segments": [_segment_to_dict(s) for s in self.segments],
        }
        write_json_atomic(path, obj)

    # ---- Validation ----

    def validate(self, *, duration_s: float, silence_map: dict | None = None) -> None:
        """Run all 5 mandatory checks (D-05) + FPS-04 silence coverage (D-07/D-08).

        Raises ScheduleValidationError on the first failure with segment index +
        field name in the message (D-06). Caller controls when to invoke (tests
        can construct partially-valid schedules; running ffmpeg gates on this).

        Args:
            duration_s: video duration from `agent.sources._common.ffprobe_video`.
            silence_map: parsed silence_map.json content (D-20 schema), or None
                when the artifact is absent (D-08 fallback path).
        """
        # D-05.1: version must be exactly 1
        if self.version != 1:
            raise ScheduleValidationError(
                f"unsupported schedule version: {self.version!r} (only 1 supported "
                f"in Phase 4; future versions go through docs/schema-migration.md)"
            )

        # D-05.2: full-duration coverage ± 2s
        if not self.segments:
            raise ScheduleValidationError("schedule has no segments")
        first, last = self.segments[0], self.segments[-1]
        if first.start > _DURATION_TOLERANCE_S:
            raise ScheduleValidationError(
                f"first segment must start <= {_DURATION_TOLERANCE_S}s; "
                f"got start={first.start} (D-05.2 +/-{_DURATION_TOLERANCE_S}s tolerance)"
            )
        if last.end < duration_s - _DURATION_TOLERANCE_S:
            raise ScheduleValidationError(
                f"last segment must end >= duration - {_DURATION_TOLERANCE_S}s; "
                f"got end={last.end}, duration={duration_s} "
                f"(D-05.2 +/-{_DURATION_TOLERANCE_S}s tolerance)"
            )

        # D-05.3: no overlap, no gap (strict equality at boundaries)
        for i in range(len(self.segments) - 1):
            prev, curr = self.segments[i], self.segments[i + 1]
            if prev.end != curr.start:
                kind = "overlap" if prev.end > curr.start else "gap"
                raise ScheduleValidationError(
                    f"segment {i} (end={prev.end}) and segment {i + 1} "
                    f"(start={curr.start}) must have prev.end == curr.start; "
                    f"{kind} of {abs(prev.end - curr.start)}s (D-05.3)"
                )

        # D-05.4: fps XOR skip — re-check (also enforced at parse time)
        for i, seg in enumerate(self.segments):
            has_fps = seg.fps is not None
            has_skip = seg.skip is True  # identity — reject 1, "true", etc.
            if has_fps == has_skip:  # both True or both False is invalid
                raise ScheduleValidationError(
                    f"segment {i}: must have exactly one of `fps` or `skip:true` "
                    f"(got fps={seg.fps!r}, skip={seg.skip!r}) — D-05.4"
                )

        # D-05.5 unknown keys: already enforced at parse time in from_json +
        # _load_segment, no-op here.

        # D-07/D-08: silence coverage (FPS-04)
        self._check_silence_coverage(duration_s, silence_map)

    def _check_silence_coverage(self, duration_s: float, silence_map: dict | None) -> None:
        """FPS-04 strict-OR-fallback per D-07/D-08.

        EITHER (a) baseline pass exists (segment with fps <= 0.1 spanning full
        duration ±2s) OR (b) every flagged_for_review:true silence interval is
        fully covered by union of fps (non-skip) segments.

        When silence_map is None (artifact absent), degrade to (a) only with
        loud warning (D-08).
        """
        has_baseline_pass = any(
            seg.fps is not None
            and seg.fps <= _BASELINE_FPS_MAX
            and seg.start <= _DURATION_TOLERANCE_S
            and seg.end >= duration_s - _DURATION_TOLERANCE_S
            for seg in self.segments
        )

        if silence_map is None:
            # D-08 fallback: baseline-pass requirement only, with loud warning
            if not has_baseline_pass:
                raise ScheduleValidationError(
                    "FPS-04: no silence_map.json found, baseline pass missing. "
                    "Either run `python -m agent.tools detect_silence <video>` "
                    "for tighter coverage, OR add a baseline segment with "
                    "fps <= 0.1 spanning the full video."
                )
            log.warning(
                "silence_map.json not found; FPS-04 enforces baseline-pass "
                "requirement only. Run detect_silence for tighter coverage."
            )
            return

        if has_baseline_pass:
            return  # D-07 (a) satisfied — tighter (b) check not needed

        # D-07 (b): every flagged_for_review interval fully covered by fps segments
        flagged = [
            iv for iv in silence_map.get("silence_intervals", [])
            if iv.get("flagged_for_review") is True
        ]
        fps_segments = [
            seg for seg in self.segments
            if seg.fps is not None and not seg.skip
        ]

        for iv in flagged:
            if not _interval_covered(iv["start"], iv["end"], fps_segments):
                raise ScheduleValidationError(
                    f"FPS-04: silence interval [{iv['start']}, {iv['end']}] "
                    f"(>5s) is not fully covered by fps segments. Either add "
                    f"baseline pass (fps <= 0.1 spanning full video) or extend "
                    f"an fps segment to cover it."
                )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _load_segment(d: dict, idx: int) -> Segment:
    """Parse one segment dict into a Segment.

    Enforces D-05.5 (unknown keys) and the boolean-identity half of D-05.4
    (`skip` must be literal True/False, not 1, "true", etc) at parse time so
    constructing the dataclass cannot smuggle wrong types past validate().
    """
    if not isinstance(d, dict):
        raise ScheduleValidationError(
            f"segment {idx}: must be a dict; got {type(d).__name__}"
        )

    unknown = set(d) - _ALLOWED_SEG_KEYS
    if unknown:
        raise ScheduleValidationError(
            f"segment {idx}: unknown keys {sorted(unknown)} "
            f"(allowed: {sorted(_ALLOWED_SEG_KEYS)})"
        )

    # `skip` must be a literal Python bool — reject 1, 0, "true", "false"
    if "skip" in d:
        if type(d["skip"]) is not bool:
            raise ScheduleValidationError(
                f"segment {idx}: `skip` must be a boolean literal "
                f"(got {d['skip']!r} of type {type(d['skip']).__name__}); "
                f"D-05.4 rejects 1 / \"true\" / etc."
            )

    # Required start/end
    try:
        start = float(d["start"])
        end = float(d["end"])
    except (KeyError, TypeError, ValueError) as e:
        raise ScheduleValidationError(
            f"segment {idx}: `start` and `end` are required and must be numeric "
            f"(got {d!r}): {e}"
        ) from e

    fps = float(d["fps"]) if "fps" in d else None
    skip = bool(d.get("skip", False))
    label = d.get("label")

    return Segment(start=start, end=end, fps=fps, skip=skip, label=label)


def _segment_to_dict(seg: Segment) -> dict:
    """Serialize Segment dropping None / False fields (symmetric with input shape)."""
    out: dict = {"start": seg.start, "end": seg.end}
    if seg.fps is not None:
        out["fps"] = seg.fps
    if seg.skip is True:
        out["skip"] = True
    if seg.label is not None:
        out["label"] = seg.label
    return out


def _interval_covered(a: float, b: float, fps_segments: list[Segment]) -> bool:
    """True iff union of fps_segments restricted to [a, b] fully covers [a, b].

    Set-theoretic interval coverage (PITFALLS P3 — tight interpretation per
    CONTEXT D-07.b). Sort overlapping segments by start, sweep cursor.
    """
    overlapping = sorted(
        [
            (max(seg.start, a), min(seg.end, b))
            for seg in fps_segments
            if seg.start < b and seg.end > a
        ],
        key=lambda x: x[0],
    )
    cursor = a
    for s, e in overlapping:
        if s > cursor:
            return False  # gap — not covered
        cursor = max(cursor, e)
        if cursor >= b:
            return True
    return cursor >= b
