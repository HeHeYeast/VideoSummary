"""Schema-tolerant loaders + atomic-write + sidecar helpers for output/<slug>/ artifacts.

Phase 1 (PRE-03): centralizes schema_version normalization for v1->v2 migrations.
Phase 2 (RES-01..RES-04): adds atomic JSON write, sidecar (`<artifact>.params.json`)
read/write, parameter comparison, cache-decision policy, tool-version probes, and
PermissionError retry for Windows Defender / OneDrive / Search lock contention.

Behavior:
- Dict-shaped artifacts (meta.json): obj.get("schema_version", 1) -- absence == v1
- List-shaped artifacts (segs.json, paragraphs.json): always treated as v1
  (top-level list cannot carry a schema_version field without breaking
  backward-compat per PROJECT.md K3 / D-04)
- Atomic writes: tempfile in target.parent + os.replace (D-09/D-10).
  PermissionError retried 3x at 0.5s linear (D-11).
- Sidecars: sibling file <artifact>.params.json.
  Mismatch policy: cli/func diff -> regen; tools-only diff -> warn + reuse;
  missing sidecar -> warn + reuse (17-archive backward-compat, D-01).

References: docs/schema-versions.md, .planning/phases/02-*/02-CONTEXT.md
"""
from __future__ import annotations

import functools
import json
import logging
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1  # current version for new artifacts; bump in v2 phase

_PERMISSION_RETRIES = 3
_PERMISSION_BACKOFF_S = 0.5
# RESEARCH Pitfall 1: naive (\S+) captures 8.1-essentials_build-www.gyan.dev
# which causes spurious tools-version churn. Capture only major.minor(.patch).
_FFMPEG_VERSION_RE = re.compile(r"^ffmpeg version (\d+\.\d+(?:\.\d+)?)")


def load_meta(path):
    """Load meta.json. Dict artifact, schema_version-tolerant."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(
            f"meta.json must be a dict (v1); got {type(obj).__name__} at {path}"
        )
    return obj


def load_segs(path):
    """Load segs.json. Top-level list, always v1."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(
            f"segs.json must be a list (v1); got {type(obj).__name__} at {path}"
        )
    return obj


def load_paragraphs(path):
    """Load paragraphs.json. Top-level list, always v1."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(
            f"paragraphs.json must be a list (v1); got {type(obj).__name__} at {path}"
        )
    return obj


# ---------------------------------------------------------------------------
# Phase 2 RES-03 / RES-04: atomic write + PermissionError retry
# ---------------------------------------------------------------------------


def _replace_with_retry(tmp, target):
    """os.replace with PermissionError retry per D-11 (3 attempts, 0.5s linear).

    Catches ONLY PermissionError (not broad OSError) -- disk-full / invalid-path
    must still fail fast. After 3 failures, re-raises with hint about Defender/OneDrive.
    """
    last_err = None
    for attempt in range(_PERMISSION_RETRIES):
        try:
            os.replace(tmp, target)
            return
        except PermissionError as e:
            last_err = e
            if attempt < _PERMISSION_RETRIES - 1:
                log.info(
                    "PermissionError replacing %s (attempt %d/%d): %s",
                    target.name, attempt + 1, _PERMISSION_RETRIES, e,
                )
                time.sleep(_PERMISSION_BACKOFF_S)
    assert last_err is not None
    raise PermissionError(
        f"{last_err}; 原因可能是 Windows Defender / OneDrive / Search 索引短时持锁，重试 3 次后仍失败"
    ) from last_err


def write_json_atomic(path, obj, *, sidecar_params=None):
    """Atomically write JSON to path; optionally write <path>.params.json sidecar.

    Both files use tempfile-in-target-dir + os.replace for atomicity (D-09/D-10).
    Same-volume guaranteed via dir=target.parent. Encoding/indent preserves the
    project idiom (encoding=utf-8, ensure_ascii=False, indent=2).
    Artifact is replaced FIRST then sidecar -- if process dies between, next read
    sees a new artifact without sidecar and falls into D-01 (loud-but-don't-regen).

    Sidecar path: target.parent / (target.name + ".params.json").
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(obj, ensure_ascii=False, indent=2)

    artifact_tmp = None
    sidecar_tmp = None
    sidecar_target = None
    try:
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

        if sidecar_params is not None:
            sidecar_target = target.parent / (target.name + ".params.json")
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

        _replace_with_retry(artifact_tmp, target)
        artifact_tmp = None
        if sidecar_tmp is not None and sidecar_target is not None:
            _replace_with_retry(sidecar_tmp, sidecar_target)
            sidecar_tmp = None
    finally:
        if artifact_tmp is not None:
            artifact_tmp.unlink(missing_ok=True)
        if sidecar_tmp is not None:
            sidecar_tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Phase 2 RES-01: sidecar read / write / compare / cache-decision
# ---------------------------------------------------------------------------


def read_sidecar(artifact_path):
    """Return parsed sidecar dict, or None if sidecar file does not exist.

    Sidecar lives at <artifact_path>.params.json (sibling, same dir -- D-08).
    """
    sidecar = Path(artifact_path).parent / (Path(artifact_path).name + ".params.json")
    if not sidecar.exists():
        return None
    return json.loads(sidecar.read_text(encoding="utf-8"))


def write_sidecar(artifact_path, sidecar_params):
    """Write a sidecar standalone (used by --force regen path)."""
    target = Path(artifact_path)
    sidecar_path = target.parent / (target.name + ".params.json")
    payload = json.dumps(sidecar_params, ensure_ascii=False, indent=2)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", dir=str(target.parent), delete=False,
        prefix=f".tmp.{sidecar_path.name}.", suffix=".tmp", encoding="utf-8",
    ) as tf:
        tf.write(payload)
        tmp = Path(tf.name)
    try:
        _replace_with_retry(tmp, sidecar_path)
    finally:
        tmp.unlink(missing_ok=True)


def compare_params(old, new):
    """Return list of (field_path, old_value, new_value) for fields that differ.

    Inspects only cli/func/tools sub-dicts; ignores captured_at and schema_version
    (timestamp drift is normal; schema_version is the loader job).
    Comparison is per-field !=, not whole-dict equality, to avoid false negatives
    from key-order or unrelated drift (RESEARCH Pitfall 3).
    """
    diffs = []
    for segment in ("cli", "func", "tools"):
        old_seg = old.get(segment, {}) if old else {}
        new_seg = new.get(segment, {}) if new else {}
        keys = set(old_seg) | set(new_seg)
        for k in sorted(keys):
            ov = old_seg.get(k)
            nv = new_seg.get(k)
            if ov != nv:
                diffs.append((f"{segment}.{k}", ov, nv))
    return diffs


def cache_decision(old, new, artifact_name, *, forced=False):
    """Decide cache action based on sidecar comparison. Returns one of:
        reuse | regen | warn_then_reuse | regen_forced

    Emits the literal log lines locked in CONTEXT D-01 / D-02 / D-07.
    """
    if forced:
        log.warning("forced regeneration of %s", artifact_name)
        return "regen_forced"
    if old is None:
        log.warning(
            "no params.json for %s; cannot validate cache freshness "
            "— pass --force to regenerate with sidecar capture",
            artifact_name,
        )
        return "reuse"
    diffs = compare_params(old, new)
    if not diffs:
        return "reuse"
    cli_func_diffs = [d for d in diffs if d[0].startswith(("cli.", "func."))]
    tools_diffs = [d for d in diffs if d[0].startswith("tools.")]
    if cli_func_diffs:
        for path_, ov, nv in cli_func_diffs:
            log.warning(
                "regenerating %s because: %s changed %r -> %r",
                artifact_name, path_, ov, nv,
            )
        return "regen"
    if tools_diffs:
        for path_, ov, nv in tools_diffs:
            log.warning(
                "tools version drift in %s: %s %r -> %r (use --force to regenerate)",
                artifact_name, path_, ov, nv,
            )
        return "warn_then_reuse"
    return "reuse"


# ---------------------------------------------------------------------------
# Phase 2 RES-01: tool version probes (per RESEARCH Pattern 4 + Pitfall 1)
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _get_ffmpeg_version():
    """Return ffmpeg major.minor(.patch) extracted from ffmpeg -version first line.

    Per RESEARCH Pitfall 1: naive backslash-S-plus regex would capture 8.1-essentials_build-www.gyan.dev
    causing build-hash churn. Regex captures bare version cleanly.
    Returns "unknown" if probe fails. Cached per-process via lru_cache.
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], check=True, capture_output=True, text=True
        )
        first_line = result.stdout.splitlines()[0] if result.stdout else ""
        m = _FFMPEG_VERSION_RE.match(first_line)
        return m.group(1) if m else "unknown"
    except (FileNotFoundError, subprocess.CalledProcessError, OSError) as e:
        log.warning("ffmpeg version probe failed: %s", e)
        return "unknown"


@functools.lru_cache(maxsize=1)
def _get_faster_whisper_version():
    """Return faster_whisper.__version__ or unknown if package missing/unreadable."""
    try:
        import faster_whisper
        return getattr(faster_whisper, "__version__", "unknown")
    except Exception:
        return "unknown"


def now_iso():
    """ISO-8601 UTC timestamp for sidecar captured_at and event ts fields."""
    return datetime.now(timezone.utc).isoformat()
