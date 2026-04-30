---
phase: 01-preflight-regression-baseline
verified: 2026-04-30T00:00:00Z
status: passed
score: 15/15 truths verified (all 4 ROADMAP success criteria + 5 PRE requirements satisfied)
overrides_applied: 0
gaps:
  - truth: "tests/regression/encoding-audit.md serves as 'read-only evidence anyone can re-run' (audit's own claim) — but cited stale line numbers that no longer matched the live code"
    status: resolved
    resolved_at: 2026-04-30
    resolved_by: "commit 10934aa — fix(01-03): correct stale line numbers in encoding-audit.md (WR-01)"
    reason: "Plan 01-02 inserted `from agent.io import load_meta` at agent/douyin_downloader.py:23 (after Plan 01-03 wrote the audit), shifting subsequent line numbers down by 2. Audit doc cited the pre-shift positions (194/60) instead of current (196/62). Fixed inline: encoding-audit.md now cites :196 (twice) and :62 with variable `new_content`."
---

# Phase 1: Preflight & Regression Baseline Verification Report

**Phase Goal:** Freeze the legacy 17-archive re-run path and the `meta.json` / `segs.json` / `paragraphs.json` schemas as the regression target before any feature work touches them.
**Verified:** 2026-04-30
**Status:** passed (initial verification flagged WR-01 line-number drift; resolved by commit 10934aa)
**Re-verification:** Inline fix verified — `encoding-audit.md` now cites `agent/douyin_downloader.py:196` (×2) and `:62` with variable `new_content`, matching live `grep -n`.

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria + 3 PLAN must-haves merged)

| #   | Truth                                                                                                                                                                                                              | Status     | Evidence                                                                                                                                                                                                   |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | `tests/regression/` contains committed `summary.md` baselines for `BV132wizyEEB`, `BV1C9QCBdE1U`, and `douyin_trae_ai` plus a `regression-check.md` runbook describing how to re-run and manual-diff (ROADMAP SC1) | VERIFIED   | All 12 files present (4 per slug × 3 slugs), `regression-check.md` exists at 159 lines with 3-step procedure; `git check-ignore` returned exit 1 = tracked.                                                |
| 2   | Loaders for `meta.json` / `segs.json` / `paragraphs.json` accept files lacking `schema_version` and treat them as v1 (archived videos remain re-runnable unchanged) (ROADMAP SC2)                                  | VERIFIED   | `agent/io.py` (61 lines, stdlib-only) exports `load_meta` / `load_segs` / `load_paragraphs` / `SCHEMA_VERSION = 1`; all 3 baselines round-trip through helpers; none has a `schema_version` key.           |
| 3   | Every `open()` call in `agent/` and `src/` uses explicit `encoding="utf-8"` (verified by audit) (ROADMAP SC3)                                                                                                      | VERIFIED   | Re-ran all 3 audit commands live: 4 bare opens (all binary/PIL — verdict OK); 0 `read_text`/`write_text` without `encoding=` (verified with multi-line aware Python regex); 0 functional `json.load(...)`. |
| 4   | `CLAUDE.md` documents `chcp 65001` + `PYTHONUTF8=1` as the recommended Windows zh-CN setup so subsequent phases inherit a clean encoding baseline (ROADMAP SC4)                                                    | VERIFIED   | New `## Windows zh-CN 终端设置（推荐）` section at CLAUDE.md:41-63, contains both commands + UTF-8-mode probe + reference to preserved `agent/tools.py:59` `ensure_ascii=True` fallback.                          |
| 5   | Three baseline slugs each have summary.md + meta.json + segs.json + paragraphs.json frozen byte-for-byte from `output/<slug>/` (Plan 01-01)                                                                        | VERIFIED   | `cmp` returned 0 for all 12 file pairs; sizes match SUMMARY (4941/788/4178/2179, 10198/341/23370/16174, 20510/487/12145/6532).                                                                              |
| 6   | All 9 enumerated load sites import from `agent.io` and call the helpers (no inline `json.loads` on the three artifacts) (Plan 01-02)                                                                               | VERIFIED   | grep counted 2/3/2/1/1 helper calls in agent/tools.py / agent/prepare.py / src/pipeline.py / src/download.py / agent/douyin_downloader.py = 9 total. All 5 modules import cleanly.                          |
| 7   | No file under existing `output/<slug>/` is modified (D-03 hard rule) (Plan 01-02)                                                                                                                                  | VERIFIED   | `cmp` of every committed baseline against its `output/<slug>/` source returned 0 — sources untouched.                                                                                                       |
| 8   | `docs/schema-versions.md` exists and grep-ably records the v1 field set (D-05) (Plan 01-02)                                                                                                                        | VERIFIED   | 100 lines, contains `schema_version: 1`, `video_path`, `aweme_id`, `"source": "douyin"`, `para_id`, `seg_indices`, frame filename grammar, K3 reference, cross-links to `agent/io.py` and runbook.            |
| 9   | `tests/regression/encoding-audit.md` exists, dated, lists the three exact grep commands plus their current outputs verbatim (Plan 01-03)                                                                           | VERIFIED   | 77 lines, dated 2026-04-30, all 3 `rg` commands present in fenced block, scope statement names `agent/` + `src/`, vendor exclusion noted, 100% compliant verdict, all 4 bare opens classified.              |
| 10  | Audit covers all 8 .py files in `agent/` + all 9 .py files in `src/` (D-14 + D-16) and lists all 4 bare `open()` calls (Plan 01-03)                                                                                | VERIFIED   | 4 bare opens listed: `agent/douyin_downloader.py:196`, `agent/embed.py:79`, `agent/frames_v2.py:74`, `src/frames.py:53`. Line numbers match live `grep -n` after WR-01 fix (commit 10934aa).                |
| 11  | encoding-audit.md serves as "read-only evidence anyone can re-run" with line numbers that currently match the live source                                                                                          | VERIFIED   | WR-01 (initial verification) flagged 2-line drift; fixed inline by commit 10934aa. `grep -n "open(" agent/douyin_downloader.py` now returns `196` (matches doc); `grep -n "write_text" agent/douyin_downloader.py` returns `62` with variable `new_content` (matches doc). |
| 12  | CLAUDE.md addition phrased as "推荐 (recommended), not required" per D-18; existing `ensure_ascii=True` fallback at agent/tools.py:59 preserved                                                                       | VERIFIED   | Heading `（推荐）`, body says "兜底保留不动，没设 codepage 的环境也能正常工作"; `sed -n '59p' agent/tools.py` confirms `ensure_ascii=True` unchanged.                                                                  |
| 13  | `agent/io.py` contains zero new dependencies beyond stdlib `json` + `pathlib`                                                                                                                                       | VERIFIED   | Only imports: `from __future__ import annotations`, `import json`, `from pathlib import Path`. 61 lines total.                                                                                              |
| 14  | Operator can copy-paste the runbook's commands without thinking about substitution (Plan 01-01)                                                                                                                    | VERIFIED   | `cp -r tests/regression/<slug>/* output/<slug>/`, `python -m agent.tools transcribe ... --force`, `Read tests/regression/<slug>/summary.md` all present verbatim with `<slug>` substitution explicit.       |
| 15  | Pass criterion is Claude's "no surprise drift" judgment, not byte-equality (per D-09)                                                                                                                              | VERIFIED   | `regression-check.md:141` states verbatim: "The pass criterion is 'no surprise drift' judgment, not byte-equality."                                                                                          |

**Score:** 15/15 truths verified (initial gap WR-01 resolved by inline fix, commit 10934aa)

### Required Artifacts

| Artifact                                                                                                                                                                                                                                                                                | Expected                                                       | Status                          | Details                                                                                                                                                       |
| ---- | --------------------------------------------------------------------- | ----------------- | ------------------------------------------------------------------- |
| 12 baseline files under `tests/regression/<slug>/` (3 × 4)                                                                                                                                                                                                                              | byte-identical to `output/<slug>/` source                       | VERIFIED                        | All 12 `cmp` returned 0; sizes match SUMMARY exactly. Variant fidelity: `\\` separator preserved in BV132wizyEEB; `/` in BV1C9QCBdE1U; `aweme_id`+`source: "douyin"` in douyin_trae_ai. |
| `tests/regression/regression-check.md`                                                                                                                                                                                                                                                  | 3-step manual runbook + eyeball-diff prompt template            | VERIFIED                        | 159 lines (under 200-line cap). Contains `cp -r tests/regression/`, `python -m agent.tools`, `--force`, `Read tests/regression/`, all 3 slugs, all 3 source URLs, PASS/FAIL verdict labels, 5 evaluation axes (STRUCTURE / TIMESTAMPS / CODE / FRAME REFS / RED-LINES). |
| `agent/io.py`                                                                                                                                                                                                                                                                            | 3 loaders + SCHEMA_VERSION                                      | VERIFIED                        | 61 lines, stdlib-only, all 4 patterns present (def load_meta, def load_segs, def load_paragraphs, SCHEMA_VERSION = 1).                                       |
| `docs/schema-versions.md`                                                                                                                                                                                                                                                                | v1 field-set + loader contract + frame grammar                  | VERIFIED                        | 100 lines. All 5 expected patterns present. Cross-links to agent/io.py and regression-check.md.                                                              |
| `agent/tools.py`                                                                                                                                                                                                                                                                          | L1 + L2 sites converted to `load_segs()`                        | VERIFIED                        | Lines 78 + 96 use `load_segs(...)`; 2 `from agent.io import load_segs` at handler scope (lines 66, 94).                                                       |
| `agent/prepare.py`                                                                                                                                                                                                                                                                        | L3+L4+L5 sites converted                                        | VERIFIED                        | Lines 78/93/115 use `load_meta`/`load_segs`/`load_paragraphs`; 1 import at line 62.                                                                           |
| `src/pipeline.py`                                                                                                                                                                                                                                                                         | L6+L7 sites converted                                           | VERIFIED                        | Lines 36/48 use helpers; 1 top-of-file import at line 9.                                                                                                       |
| `src/download.py`                                                                                                                                                                                                                                                                         | L8 site converted                                                | VERIFIED                        | Line 22 uses `load_meta`; 1 top-of-file import at line 11.                                                                                                     |
| `agent/douyin_downloader.py`                                                                                                                                                                                                                                                              | L9 site converted                                                | VERIFIED                        | Line 152 uses `load_meta`; 1 top-of-file import at line 23.                                                                                                    |
| `tests/regression/encoding-audit.md`                                                                                                                                                                                                                                                     | PRE-04 audit-pass evidence                                      | VERIFIED (with WR-01 line drift)| 77 lines, all 4 bare-open sites listed, all 3 rg commands verbatim. Line-number citations are stale by 2 lines (gap #11).                                     |
| `CLAUDE.md`                                                                                                                                                                                                                                                                              | Windows zh-CN section between 抖音支持 and 环境变量              | VERIFIED                        | New section at lines 41-63. Contains chcp 65001, PYTHONUTF8=1, sys.flags.utf8_mode probe, agent/tools.py:59 reference. Section ordering correct (22 < 41 < 65). |
| `.gitattributes`                                                                                                                                                                                                                                                                          | `tests/regression/** -text` opt-out                              | VERIFIED                        | 5 lines; correct glob; preserves CRLF + `\\` byte-for-byte.                                                                                                    |

### Key Link Verification

| From                                | To                                                  | Via                                                | Status   | Details                                                                                                                                          |
| ----------------------------------- | --------------------------------------------------- | -------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| regression-check.md                 | tests/regression/<slug>/summary.md                  | step-3 manual diff prompt                          | WIRED    | Manual grep found `Read tests/regression/<slug>/summary.md` at line 83 and `tests/regression/<slug>/summary.md` at line 92 (gsd-tools tool quirk reported false-negative). |
| regression-check.md                 | agent/tools.py --force flag                         | step-2 stage re-run command                        | WIRED    | gsd-tools verified.                                                                                                                              |
| .gitignore                          | tests/regression/                                   | verified non-overlap (tests/ NOT in gitignore)     | WIRED    | `cat .gitignore` confirms tests/ glob is absent; `git check-ignore` returns exit 1.                                                              |
| 5 .py files                         | agent.io                                            | imports replacing inline json.loads                | WIRED    | All 5 files have `from agent.io import ...` (2/1/1/1/1 = 6 imports total: agent/tools.py uses 2 handler-scope imports).                            |
| docs/schema-versions.md             | agent/io.py + regression-check.md                   | cross-link in 'Reference' section                  | WIRED    | Lines 11+97 reference agent/io.py; line 98 references regression-check.md.                                                                         |
| CLAUDE.md (new section)             | agent/tools.py:59 ensure_ascii=True fallback        | explicit reference '兜底保留不动'                  | WIRED    | Line 44 cites `agent/tools.py:59` and `ensure_ascii=True`; line 58 says 老的 `ensure_ascii` 兜底保留不动.                                          |
| encoding-audit.md                   | regression-check.md                                 | runbook stub section heading                       | WIRED    | encoding-audit.md:74 references regression-check.md; regression-check.md:158 links back to encoding-audit.md.                                      |
| encoding-audit.md                   | 4 bare-open lines                                   | verbatim citation                                  | WIRED    | All 4 cited (douyin:194, embed:79, frames_v2:74, frames:53). NOTE: 194 is now stale (gap #11), but the file path + classification is correct.       |

### Behavioral Spot-Checks

| Behavior                                              | Command                                                                            | Result                                              | Status |
| ----------------------------------------------------- | ---------------------------------------------------------------------------------- | --------------------------------------------------- | ------ |
| All 3 baselines load through agent.io                 | `python -c "from agent.io import load_meta; load_meta('tests/regression/...meta.json')"` | 3/3 dicts loaded; douyin variant has aweme_id+source | PASS   |
| segs.json loads as 170-element list                   | `load_segs('tests/regression/BV1C9QCBdE1U/segs.json')`                              | 170 segments, all dicts with start/end/text         | PASS   |
| paragraphs.json loads as 19-element list              | `load_paragraphs('tests/regression/BV1C9QCBdE1U/paragraphs.json')`                  | 19 paragraphs, each has para_id/start/end/text/seg_indices | PASS |
| Path argument polymorphism                            | `load_meta(Path('tests/regression/BV132wizyEEB/meta.json'))`                        | dict returned                                        | PASS   |
| Fail-fast on wrong shape                              | `load_meta(file containing [])` ; `load_segs(file containing {})`                  | ValueError with `must be a dict` / `must be a list` | PASS   |
| All 5 patched modules import cleanly                  | `python -c "import agent.io; import agent.tools; import agent.prepare; import src.pipeline; import src.download; import agent.douyin_downloader"` | OK                                       | PASS   |
| All 3 audit grep commands re-run                      | rg/grep × 3                                                                          | Cmd 1: 4 bare opens (matches doc); Cmd 2: 0 violations (multi-line aware); Cmd 3: 0 functional | PASS |
| ensure_ascii=True still on agent/tools.py:59 (D-18)   | `sed -n '59p' agent/tools.py`                                                       | `print(json.dumps(meta, ensure_ascii=True, indent=2))` | PASS |
| .gitignore unchanged (D-03)                           | `git diff --quiet -- .gitignore`                                                    | exit 0                                              | PASS   |
| All 12 baselines byte-identical to source             | `cmp output/<slug>/<f> tests/regression/<slug>/<f>` × 12                            | All exit 0                                           | PASS   |

### Requirements Coverage

| Requirement | Source Plan | Description                                                                                                                            | Status     | Evidence                                                                                                                                                                  |
| ----------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| PRE-01      | 01-01       | Project commits a `tests/regression/` directory with frozen `summary.md` baselines from 3 archived videos                              | SATISFIED  | 12 files (3 slugs × 4 files); summary.md byte-identical to source for all 3 slugs.                                                                                       |
| PRE-02      | 01-01       | Project includes a `regression-check.md` runbook describing how to re-run the new flow on the 3 baselines and manual-diff             | SATISFIED  | tests/regression/regression-check.md (159 lines): 3-step procedure + Claude-as-verifier prompt template + 5 evaluation axes + PASS/FAIL contract + cadence (D-10).        |
| PRE-03      | 01-02       | `meta.json` / `segs.json` / `paragraphs.json` schemas documented as `schema_version: 1` retroactively; loaders default to 1 when absent | SATISFIED  | docs/schema-versions.md documents v1 field set; agent/io.py uses `obj.get("schema_version", 1)` for dict, treats list-shape as v1 unconditionally. All 3 baselines load. |
| PRE-04      | 01-03       | Every `open()` call in `agent/` and `src/` uses explicit `encoding="utf-8"` (audited and fixed where missing)                          | SATISFIED  | tests/regression/encoding-audit.md documents 100% compliance; 4 bare opens are PIL/binary (no encoding= needed); 0 text-I/O without encoding (verified live, multi-line aware). |
| PRE-05      | 01-03       | `CLAUDE.md` documents `chcp 65001` and `PYTHONUTF8=1` as recommended Windows zh-CN setup steps                                          | SATISFIED  | CLAUDE.md:41-63 new section `## Windows zh-CN 终端设置（推荐）` with both commands and UTF-8-mode verification probe.                                                       |

**Coverage:** 5/5 requirements (PRE-01 through PRE-05). Zero orphaned requirements — REQUIREMENTS.md maps PRE-01..PRE-05 to Phase 1, all 5 are claimed across the 3 plans.

### Anti-Patterns Found

| File                                | Line     | Pattern                              | Severity   | Impact                                                                                                                                                  |
| ----------------------------------- | -------- | ------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| tests/regression/encoding-audit.md  | 33,41,48 | Stale line numbers (194→196, 60→62)  | Warning    | Documentation accuracy in a freshly-minted artifact. Re-running the rg commands still produces the documented findings, but the table cites pre-shift positions. |

No TODO/FIXME/PLACEHOLDER patterns in any file modified by this phase.
No credentials in any baseline JSON (security T1 grep clean).
No hardcoded empty data, no console.log-only implementations, no empty handlers.

### Human Verification Required

None. All verification is programmatic: file existence, byte-equality (`cmp`), grep patterns, Python imports, regex re-runs of the 3 audit commands, manual diff is itself the documented future regression step (not blocking Phase 1 acceptance — this phase ships the runbook, doesn't run it).

### Gaps Summary

**One documentation accuracy gap (Warning, not blocker):**

WR-01 (already filed in 01-REVIEW.md): `tests/regression/encoding-audit.md` cites `agent/douyin_downloader.py:194` for the binary write and `agent/douyin_downloader.py:60` for the `_CONFIG.write_text` audit-note. After Plan 01-02 inserted `from agent.io import load_meta` at line 23 of that file, all subsequent line numbers shifted down by 2: actual current locations are `:196` and `:62` (with variable name `new_content`, not `content`).

The audit's classifications (binary write OK; encoding-correct write_text OK) remain accurate; running the live `rg` commands today still produces the documented findings (4 bare opens, all classified the same way). What's stale is only the line-number anchors. Per the audit's own value proposition ("read-only evidence anyone can re-run and replicate the result"), the line numbers are part of the deliverable's contract.

**Suggested fix paths (in 01-REVIEW.md):**
1. Update line 33 to `:196`, line 41 to `:196`, line 48 to `:62` with variable `new_content`
2. OR drop line numbers from the findings table and let the live grep transcript carry them (more sustainable — survives all future code shifts)

The phase otherwise meets every must-have:
- 4/4 ROADMAP success criteria verified
- 5/5 PRE requirements satisfied
- 12/12 baselines byte-identical to source
- 9/9 load sites converted
- All 5 patched modules import cleanly
- D-03 hard rule (no output/ modifications) honored
- D-18 hard rule (ensure_ascii=True at agent/tools.py:59 preserved) honored
- All key links wired (gsd-tools reported false-negatives due to comma-separated `contains` patterns being treated as literals; manual verification confirms every pattern is present)

The line-drift gap is a low-impact accuracy defect in documentation; it does not break the freeze contract, the loader-tolerance contract, or the encoding-cleanliness contract. Phase 2 can proceed in parallel with the gap closure.

---

_Verified: 2026-04-30_
_Verifier: Claude (gsd-verifier)_
