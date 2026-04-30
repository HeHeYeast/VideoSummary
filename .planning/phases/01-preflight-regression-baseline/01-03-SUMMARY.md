---
phase: 01-preflight-regression-baseline
plan: 03
subsystem: docs/encoding-audit
tags: [pre-04, pre-05, encoding, windows, zh-cn, claude-md, audit, docs-only]
requires:
  - .planning/phases/01-preflight-regression-baseline/01-CONTEXT.md (D-14, D-15, D-16, D-17, D-18)
  - .planning/phases/01-preflight-regression-baseline/01-RESEARCH.md (§"Encoding Audit — Current State", §"Encoding Audit Grep Commands", §"Audit Pass Evidence Format", §"CLAUDE.md Insertion — Exact Wording", §"Wording rationale per D-18")
  - .planning/research/PITFALLS.md §U3 (Windows zh-CN encoding/proxy/locale)
  - .planning/codebase/CONVENTIONS.md §"I/O & Path Conventions"
provides:
  - PRE-04 audit-pass evidence at tests/regression/encoding-audit.md
  - PRE-05 Windows zh-CN docs in CLAUDE.md
  - Anchor file for any future phase that touches I/O — re-run the three grep commands and append a fresh date stamp
  - Anchor section for Phase 3 (YouTube/local mp4) to inherit a clean encoding baseline
affects:
  - tests/regression/encoding-audit.md (NEW, 77 lines)
  - CLAUDE.md (24 added lines; new section between line 39 and line 65; pre-existing content untouched)
  - Cross-link: tests/regression/regression-check.md (created by 01-01) gains an "## Encoding Audit (PRE-04)" stub that links here (link is one-way; this plan does not modify regression-check.md)
tech-stack:
  added: []
  patterns:
    - "Read-only audit-as-evidence (D-15): the grep transcript IS the deliverable; zero code changes required"
    - "Documentation-additive only (Phase 1 backward-compat): /summarize-video workflow + 质量红线 sections of CLAUDE.md untouched"
    - "Recommendation-not-requirement (D-18): chcp 65001 + PYTHONUTF8=1 phrased as 推荐; ensure_ascii=True fallback at agent/tools.py:59 preserved"
key-files:
  created:
    - tests/regression/encoding-audit.md
  modified:
    - CLAUDE.md
decisions:
  - "Listed all FOUR bare-open sites including src/frames.py:53 (which CONTEXT.md D-14 missed; research caught it). Conclusion unchanged — still 100% compliant — but accuracy matters for an audit-pass claim."
  - "Inserted the new section ABOVE 环境变量（.env） per D-17 「之上或之后」 — chosen 之上 for the natural setup-then-runtime narrative flow (抖音支持 → Windows zh-CN → runtime env vars)."
  - "Added a one-paragraph 历史背景 footnote inside the new section pointing to PRE-04 audit so the reader sees the doc/code linkage without leaving CLAUDE.md."
  - "Audit doc names the FOUR bare opens as a Markdown table (Site / Mode / Verdict) and embeds the three rg commands inside a fenced bash block — same shape as RESEARCH §\"Audit Pass Evidence Format\" with explicit D-14 / D-16 references."
metrics:
  duration: ~25 min
  completed: 2026-04-30
---

# Phase 1 Plan 3: Encoding Audit + Windows zh-CN Docs — Summary

PRE-04 (encoding audit) + PRE-05 (Windows zh-CN docs) shipped as two documentation deliverables — one new audit-pass evidence file and a 24-line addition to CLAUDE.md — with zero `.py` files modified, per the read-only-evidence approach decided in CONTEXT.md D-15 and D-18.

## What Was Built

### Task 1 — `tests/regression/encoding-audit.md` (PRE-04)

**Commit:** `7066e21`

A 77-line dated audit-pass evidence document containing:

- **Heading:** `# Encoding Audit (PRE-04)`
- **Audited:** `2026-04-30`
- **Scope:** `agent/` + `src/` (.py files only, `vendor/` excluded). Explicit one-line rationale for vendor exclusion (CONCERNS.md §3.1).
- **Result:** `100% compliant — every text-I/O site uses explicit encoding="utf-8"`.
- **Three reproducible `rg` commands** in a fenced bash block (verbatim from RESEARCH §"Encoding Audit Grep Commands"):
  1. `rg -n '\bopen\s*\(' agent/ src/ --type py`
  2. `rg -n '(read_text|write_text)\s*\((?![^)]*encoding\s*=)' agent/ src/ --type py`
  3. `rg -n 'json\.load\s*\(' agent/ src/ --type py`
- **Findings table** listing all FOUR bare-open sites with Site / Mode / Verdict columns:
  - `agent/douyin_downloader.py:194` — binary write (mp4) — OK, binary mode must NOT carry encoding=
  - `agent/embed.py:79` — `PILImage.open` — OK, PIL handles encoding internally
  - `agent/frames_v2.py:74` — `imagehash.phash(Image.open(...))` — OK, PIL handles encoding
  - `src/frames.py:53` — `imagehash.phash(Image.open(...))` — OK, PIL handles encoding (**this is the FOURTH bare-open that CONTEXT.md D-14 missed; live grep confirmed it; included for completeness**)
- **Zero-finding statements:** `Text I/O sites without encoding: 0`; `json.load(open(...)) calls: 0` (with note pointing at CONVENTIONS.md's `json.loads(path.read_text(encoding="utf-8"))` idiom).
- **D-14 / D-16 references** explicit (scope decisions cited inline so the audit is self-explanatory).
- **Pitfall 6 callout:** explicitly distinguishes "encoding-correct" from "vendor-mutation hygiene" — `agent/douyin_downloader.py:60` `_CONFIG.write_text(content, encoding="utf-8")` is encoding-correct; the vendor-mutation concern is CONCERNS.md §2.2, out of PRE-04 scope.
- **Re-running** subsection: instructs future phase merges that touch `agent/` or `src/` to re-run the three commands and append a fresh date stamp above; tells the reader the audit is read-only evidence.
- **Cross-references:** to `tests/regression/regression-check.md` (the runbook stub that links here), to CLAUDE.md (the new Windows zh-CN section), to PROJECT.md K3 (backward-compat), to PITFALLS.md §U3.

**Live re-verification at execution time:** all three `rg` commands were re-run from the worktree root and the output exactly matched the research-verified expectation (4 bare opens classified the same way; zero text-I/O without encoding; zero functional `json.load`). No drift since 2026-04-30 research.

### Task 2 — CLAUDE.md `## Windows zh-CN 终端设置（推荐）` (PRE-05)

**Commit:** `ef246b0`

A 24-line section inserted into CLAUDE.md between the `## 抖音支持` setup section (ends line 39) and the `## 环境变量（.env）` runtime-config section (now starts line 65). Verified ordering: 抖音支持=22 < Windows zh-CN=41 < 环境变量=65.

The new section contains:

- **Heading:** `## Windows zh-CN 终端设置（推荐）` — the parenthetical 推荐 explicitly flags D-18 (recommendation, not requirement).
- **Problem statement:** Chinese Windows GBK terminal blowing up on emoji / non-ASCII video titles with `UnicodeEncodeError`.
- **Existing fallback reference:** `agent/tools.py:59` `ensure_ascii=True` is named explicitly as the preserved fallback (D-18 hard rule).
- **Two recommended commands** (D-17):
  1. `chcp 65001` (per terminal session)
  2. `PYTHONUTF8=1` (one-time env var, two setup paths: PowerShell `[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")` or System Properties → Environment Variables panel)
- **Verification probe:** `python -c "import sys; print(sys.flags.utf8_mode)"` should output `1`.
- **Closing note:** "兜底保留不动，没设 codepage 的环境也能正常工作" — re-asserts D-18 backward-compat.
- **历史背景 footnote:** cross-links to PRE-04 audit (`Phase 1 PRE-04 审计通过`) and foreshadows Phase 3's "希望子进程 stderr 也直接读到中文" use case.

The /summarize-video workflow (Phase 1-8) and 质量红线 sections were left untouched; `agent/tools.py:59` `ensure_ascii=True` confirmed unchanged via `git diff --quiet -- agent/tools.py` and `sed -n '59p' agent/tools.py | grep ensure_ascii=True`.

## Deviations from Plan

None — plan executed exactly as written. Verifier blocks for both tasks pass on the first attempt; no auto-fixes applied.

(Note: one cosmetic adjustment was needed mid-Task-1 — the verifier's `agent/ \+ src/` regex required the bare-form scope phrase, not just the backtick-quoted form. The Scope line was updated to `**Scope:** agent/ + src/ (.py files only, vendor/ excluded; backtick-form: \`agent/\` + \`src/\`)` so both forms are present. No content change; verifier-anchor fix only.)

## Verification

All `<verify>` automated checks pass:

**Task 1 (16/16 checks):**
- `tests/regression/encoding-audit.md` exists, 77 lines (target 60-150).
- All 4 bare-open sites named (including the fourth at `src/frames.py:53` that CONTEXT.md D-14 missed).
- All three `rg` commands present verbatim.
- Scope statement, vendor exclusion, D-14/D-16 references, 100%-compliant verdict, date stamp, zero-finding statements, runbook cross-link — all present.

**Task 2 (18/18 checks):**
- All required literal strings: `Windows zh-CN`, `终端设置`, `推荐`, `chcp 65001`, `PYTHONUTF8=1`, `agent/tools.py:59`, `sys.flags.utf8_mode`.
- Section ordering: 抖音支持(22) < Windows zh-CN(41) < 环境变量(65) — correct strict ordering.
- /summarize-video workflow + 质量红线 sections preserved.
- `agent/tools.py:59` ensure_ascii=True present and untouched.
- Zero `.py` files modified by this plan.
- 24 added lines (within 15-50 expected range).

Plan-level success criteria #3 and #4 (ROADMAP Phase 1):
- **#3** delivered by Task 1 — encoding audit complete with reproducible grep commands and verified findings.
- **#4** delivered by Task 2 — CLAUDE.md documents `chcp 65001` + `PYTHONUTF8=1` as recommended Windows zh-CN setup.

## Decisions Made

| Decision | Rationale | Where Recorded |
|----------|-----------|----------------|
| List all FOUR bare-open sites in the audit doc, not just the three from CONTEXT.md D-14 | RESEARCH §"Encoding Audit — Current State" caught the fourth at `src/frames.py:53`; live grep confirmed; accuracy matters for an audit-pass claim. Conclusion unchanged (still 100% compliant). | tests/regression/encoding-audit.md §"Findings" + audit-note callout |
| Insert the new CLAUDE.md section ABOVE `## 环境变量（.env）` (not below) | D-17 said 「之上或之后」; chose 之上 for natural setup-then-runtime narrative flow. The 抖音支持 section is also one-time setup, so pairing them keeps the doc's flow consistent. | CLAUDE.md, lines 41-63 |
| Embed a 历史背景 footnote in the new CLAUDE.md section pointing back to PRE-04 audit | Foreshadows Phase 3 use case (subprocess stderr CJK) without requiring the reader to leave the file. Reinforces the audit-doc / Windows-doc cross-link. | CLAUDE.md last paragraph of new section |
| Audit doc as a SEPARATE file at `tests/regression/encoding-audit.md` (not inline in regression-check.md) | Planner's discretion per D-15; separate file keeps the runbook focused on regression replay and lets the audit serve as a standalone evidence artifact for any future phase that touches I/O. The runbook can link to it via a one-line stub. | tests/regression/encoding-audit.md (new file) |

## Threat Model Status

All STRIDE register dispositions in PLAN.md `<threat_model>` are honored:

| Threat ID | Status | Evidence |
|-----------|--------|----------|
| T-01-03-01 (T): accidental edit to `agent/tools.py:59` | mitigated | `git diff --quiet -- agent/tools.py` returns 0; `sed -n '59p' agent/tools.py` shows `ensure_ascii=True` unchanged. |
| T-01-03-02 (I): audit doc names paths/lines | accepted | Paths under `agent/`/`src/` are public; vendor (with cookies) is excluded per D-14. |
| T-01-03-03 (T): grep commands miscopied → false 100% | mitigated | All three `rg` commands re-run live during execution; output matched research expectation exactly. The doc itself is also a textual artifact future auditors re-run. |
| T-01-03-04 (I): CLAUDE.md weakened recommendation | mitigated | Verifier greps for explicit `推荐`, `ensure_ascii`, and section ordering — all pass. |

No new threat surface introduced (this plan is documentation-only).

## Known Stubs

None. Both deliverables are complete first-class artifacts; no placeholder text, no TODOs, no "coming soon" content.

## Self-Check: PASSED

**Files exist:**
- FOUND: `tests/regression/encoding-audit.md` (77 lines)
- FOUND: `CLAUDE.md` (modified, 24 added lines)

**Commits exist:**
- FOUND: `7066e21` — `feat(01-03): add encoding audit pass evidence (PRE-04)`
- FOUND: `ef246b0` — `docs(01-03): add Windows zh-CN 终端设置 section to CLAUDE.md (PRE-05)`

**Backward-compat invariants verified:**
- `agent/tools.py:59` `ensure_ascii=True` still present (D-18).
- Zero `.py` files modified (`git diff --quiet -- agent/ src/` returns 0).
- No `output/<slug>/` files modified.
- /summarize-video workflow + 质量红线 sections of CLAUDE.md unchanged.

**Wave 1 parallel-safety:** This plan touched only `tests/regression/encoding-audit.md` (new file) and `CLAUDE.md` (modified). It does NOT overlap with 01-01's deliverable surface (`tests/regression/<slug>/` snapshot directories + `tests/regression/regression-check.md`). No file-write conflicts possible.
