"""Phase 09 CORR-03b/c — verifier subagent state.jsonl event helpers + UNRESOLVED.md template renderer.

K5 boundary: this module emits state.jsonl events and renders a markdown
template; it NEVER edits the summary artifact, the plan artifact, or the
schedule artifact. The Phase 7.5 verifier writes to:
  - output/<slug>/<slug>-REVIEW.md  (subagent OUTPUT — not a decision artifact)
  - output/<slug>/<slug>-UNRESOLVED.md  (fallback — human triage list)
  - output/<slug>/summary.md.pre-review  (pre-rewrite backup — read-only afterwards)
  - output/<slug>/state.jsonl  (event audit trail)

This module provides the 2 NEW Phase 09 event emitters + the UNRESOLVED.md
template. The cmd_summary_lint handler (Plan 09-01) emits the 3rd event
(`summary_lint_run`) directly via agent.tools._emit_event.

Imported by /summarize-video Phase 7.5 (manually, by Claude in-session — this
module is not auto-loaded by any v1.0 path; D-29 byte-equal preserved).

NB: import direct from agent.state (NOT agent.tools) to avoid pulling the
heavy CLI surface into a Phase 7.5 hook. This keeps the helper import-light.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from agent.state import append_event

log = logging.getLogger(__name__)

# Filename template constants. Caller substitutes {slug} when constructing
# the per-slug artifact path. Kept as module-level so /summarize-video Phase 7.5
# hooks reference the same canonical names that the SUMMARY documents.
REVIEW_FILENAME_TEMPLATE = "{slug}-REVIEW.md"
UNRESOLVED_FILENAME_TEMPLATE = "{slug}-UNRESOLVED.md"
PRE_REVIEW_BACKUP_SUFFIX = ".pre-review"  # appended to summary artifact filename


def emit_verifier_run(slug_dir,
                      *,
                      severity_counts: dict,
                      output_path: str,
                      duration_ms: int) -> None:
    """Phase 7.5 verifier subagent run completion event.

    Args:
        slug_dir: path to the per-slug directory (typically `output/<slug>`).
            Either str or pathlib.Path. Tolerates either form.
        severity_counts: e.g. {"critical": 0, "warning": 2, "info": 5}.
            Copied (not aliased) into the event payload so caller mutations
            after emit do not affect the recorded JSON.
        output_path: relative or absolute path to the REVIEW.md the verifier
            wrote (e.g. "<slug>-REVIEW.md").
        duration_ms: wall-clock duration of the Task subagent invocation.

    Best-effort: agent.state.append_event swallows OSError -> log.warning.
    A state.jsonl write failure MUST NOT break the verifier flow (D-03 graceful
    degrade — same contract Phase 2 RES-05 established).

    Side-effects:
        Appends one JSON line to <slug_dir>/state.jsonl with shape:
            {"ts": <iso>, "stage": "verifier", "status": "completed",
             "params_hash": "", "details": {"severity_counts": {...},
             "output_path": <str>, "duration_ms": <int>}}
    """
    state_log = Path(slug_dir) / "state.jsonl"
    append_event(
        state_log,
        stage="verifier",
        status="completed",
        details={
            "severity_counts": dict(severity_counts),
            "output_path": str(output_path),
            "duration_ms": int(duration_ms),
        },
    )


def emit_rewrite_cycle_completed(slug_dir,
                                 *,
                                 critical_count_pre: int,
                                 critical_count_post: int,
                                 rewrite_path: str,
                                 duration_ms: int,
                                 unresolved_path: str | None = None) -> None:
    """CORR-03c max-1 rewrite cycle completion event.

    Args:
        slug_dir: per-slug directory (str or Path).
        critical_count_pre: critical finding count BEFORE the rewrite. Must be > 0
            for this function to be called at all (rewrite is only triggered when
            verifier reports critical findings); we do NOT validate this — caller
            owns the precondition.
        critical_count_post: critical finding count AFTER rewrite + re-verify.
            0 = clean ship; > 0 = some criticals remain → caller writes
            <slug>-UNRESOLVED.md and passes its path as `unresolved_path`.
        rewrite_path: path to the pre-rewrite backup (typically
            "summary.md.pre-review").
        duration_ms: wall-clock duration of the rewrite + re-verify cycle.
        unresolved_path: ONLY recorded when critical_count_post > 0. If passed
            with critical_count_post == 0 the path is silently dropped (defensive
            — clean ship semantics: no unresolved file should be referenced).

    Side-effects:
        Appends one JSON line to <slug_dir>/state.jsonl with shape:
            {"ts": <iso>, "stage": "rewrite_cycle", "status": "completed",
             "params_hash": "", "details": {
                 "critical_count_pre": <int>,
                 "critical_count_post": <int>,
                 "rewrite_path": <str>,
                 "duration_ms": <int>,
                 "unresolved_path": <str>?  # only when critical_count_post > 0
             }}
    """
    state_log = Path(slug_dir) / "state.jsonl"
    details: dict = {
        "critical_count_pre": int(critical_count_pre),
        "critical_count_post": int(critical_count_post),
        "rewrite_path": str(rewrite_path),
        "duration_ms": int(duration_ms),
    }
    if int(critical_count_post) > 0 and unresolved_path:
        details["unresolved_path"] = str(unresolved_path)
    append_event(
        state_log,
        stage="rewrite_cycle",
        status="completed",
        details=details,
    )


def build_unresolved_md(slug: str, critical_findings: list) -> str:
    """Render the UNRESOLVED.md template (人工介入清单).

    Args:
        slug: per-slug identifier (e.g. "BV132wizyEEB" or "douyin_xxx").
        critical_findings: list of dicts, each shaped:
            {"location": str (e.g. "summary.md L42" or "summary.md §三、消化阶段"),
             "evidence": str (verbatim quote / line snippet showing the issue),
             "rule": str (which scope-locked rule was violated:
                 trace_after_claim / citation_timestamp_invalid /
                 mode_inconsistency / glossary_drift / ...)}

    Returns:
        Markdown string suitable for direct write to
        `output/<slug>/<slug>-UNRESOLVED.md`. UTF-8 safe (no escape characters).

    Side-effects: NONE. Pure function — the caller is responsible for writing
    the returned string to disk via Path.write_text(..., encoding="utf-8").

    Defensive behavior: when `critical_findings` is empty, the returned string
    contains a "should not be triggered" note. The file is still written if
    the caller persists, so a reader can spot the bug in the Phase 7.5 hook.
    """
    parts: list[str] = []
    parts.append(f"# UNRESOLVED — {slug}")
    parts.append("")
    parts.append(
        "> 本文件由 Phase 7.5 verifier 在 max-1-rewrite 周期后仍存在 critical "
        "问题时生成。"
    )
    parts.append(
        "> Claude 已经做了一轮 delta 重写但无法消除以下 critical findings —— "
        "需要人工介入。"
    )
    parts.append(
        f"> 备份：原始未修订版本保存在 `output/{slug}/summary.md.pre-review`。"
    )
    parts.append("")
    parts.append("## 人工介入清单")
    parts.append("")
    if not critical_findings:
        parts.append(
            "> ✓ 无 critical 残余 — 不应触发本文件。如果你看到这个，说明 "
            "verifier 调用 build_unresolved_md 时传了空列表，请检查 "
            "Phase 7.5 hook 逻辑。"
        )
        parts.append("")
    else:
        for i, f in enumerate(critical_findings, start=1):
            location = f.get("location", "<location missing>")
            evidence = f.get("evidence", "<evidence missing>")
            rule = f.get("rule", "<rule missing>")
            parts.append(
                f"- [ ] **{i}. {location}** (规则违反：`{rule}`)"
            )
            parts.append(f"  - 证据：`{evidence}`")
            parts.append("  - 建议修复方向：")
            parts.append("")
    parts.append("---")
    parts.append("")
    parts.append(
        f"*生成时间：{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}*"
    )
    parts.append("")
    return "\n".join(parts)
