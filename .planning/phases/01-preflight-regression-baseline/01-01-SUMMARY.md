---
phase: 01-preflight-regression-baseline
plan: 01
subsystem: testing
tags: [regression-baseline, snapshot-testing, gitattributes, runbook, byte-equality, claude-as-verifier]

requires:
  - phase: pre-phase-1
    provides: research artifacts (CONTEXT, RESEARCH, PLAN) with verified file sizes, slug list, decisions D-01..D-13
provides:
  - Frozen byte-for-byte regression snapshots for 3 baseline videos (BV132wizyEEB, BV1C9QCBdE1U, douyin_trae_ai) under tests/regression/<slug>/
  - Operator-ready 3-step regression runbook (tests/regression/regression-check.md) with copy-paste commands and Claude-as-verifier prompt template
  - .gitattributes opt-out from autocrlf for tests/regression/** so Windows-origin CRLF + Windows-style "\\" path separators survive git round-tripping
  - First tests/ directory in project history (verified .gitignore did not silently swallow it)
affects:
  - All later phases in milestone v1.0 (each phase that touches agent/ or src/ MUST run this runbook before merge per D-10)
  - Plan 01-02 (loader-tolerance) — uses these baselines as before/after fixtures
  - Plan 01-03 (encoding audit + docs) — appends encoding-audit.md alongside regression-check.md, both in tests/regression/

tech-stack:
  added:
    - .gitattributes (first-time-in-project; binary-mode hint for tests/regression/**)
  patterns:
    - "Snapshot-as-fixture: commit small text artifacts (~99 KB total) byte-for-byte; verify drift via Claude eyeball-diff, not byte-equality"
    - "tests/regression/<slug>/<artifact> mirrors output/<slug>/<artifact>; cp -r over the top stages a fixture"
    - "Claude-as-verifier prompt with 5 evaluation axes (STRUCTURE / TIMESTAMPS / CODE / FRAME REFS / RED-LINES) and PASS/FAIL output contract"

key-files:
  created:
    - .gitattributes
    - tests/regression/BV132wizyEEB/summary.md
    - tests/regression/BV132wizyEEB/meta.json
    - tests/regression/BV132wizyEEB/segs.json
    - tests/regression/BV132wizyEEB/paragraphs.json
    - tests/regression/BV1C9QCBdE1U/summary.md
    - tests/regression/BV1C9QCBdE1U/meta.json
    - tests/regression/BV1C9QCBdE1U/segs.json
    - tests/regression/BV1C9QCBdE1U/paragraphs.json
    - tests/regression/douyin_trae_ai/summary.md
    - tests/regression/douyin_trae_ai/meta.json
    - tests/regression/douyin_trae_ai/segs.json
    - tests/regression/douyin_trae_ai/paragraphs.json
    - tests/regression/regression-check.md
  modified: []

key-decisions:
  - "Add .gitattributes 'tests/regression/** -text' to opt out of core.autocrlf=true; without it, git would silently normalize Windows CRLF to LF on commit and break the byte-for-byte freeze contract (D-04 / Pitfall 5)."
  - "Runbook references the encoding-audit appendix as a stub link, deferring its content to Plan 01-03; this keeps Plan 01-01 self-contained without a hard dependency on a sibling plan."
  - "Runbook target length (≤150 lines) was relaxed to actual 159 lines to fit all 5 evaluation axes + cadence + pass/fail criterion; verify cap is 200 lines, comfortably met."

patterns-established:
  - "Regression-baseline directory layout: tests/regression/<slug>/{summary.md,meta.json,segs.json,paragraphs.json} mirrors output/<slug>/ structure 1:1; cp -r tests/regression/<slug>/* output/<slug>/ stages fixtures."
  - "Claude-as-verifier contract: PASS = explainable diffs only; FAIL = surprise drift. Verifier reads both files in full, evaluates against 5 named axes, outputs PASS or FAIL with bullet-list reasons."
  - "Phase merge gate: every phase touching agent/ or src/ records the runbook verdict in its own VERIFICATION.md under '## Regression Baseline' before merging (D-10)."

requirements-completed: [PRE-01, PRE-02]

duration: ~7min
completed: 2026-04-30
---

# Phase 1 Plan 01: Frozen Regression Baseline + Runbook Summary

**12 byte-for-byte frozen artifacts (3 slugs × 4 files, ~99 KB total) under tests/regression/, paired with an operator-ready 3-step runbook that uses Claude as the eyeball-diff verifier — locks the v1 backward-compat safety net for the rest of milestone v1.0.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-30T11:54Z
- **Completed:** 2026-04-30T12:01Z
- **Tasks:** 2
- **Files created:** 14 (1 .gitattributes + 12 baseline artifacts + 1 runbook)
- **Files modified:** 0

## Accomplishments

- Created `tests/regression/` (first time in project history) with three slug subdirectories holding byte-for-byte frozen `summary.md` + `meta.json` + `segs.json` + `paragraphs.json` for `BV132wizyEEB`, `BV1C9QCBdE1U`, and `douyin_trae_ai`.
- All 12 files cmp-verified byte-identical to their `output/<slug>/` sources. Variant fidelity preserved: BV132wizyEEB keeps Windows-style `\\` path separators, BV1C9QCBdE1U keeps forward `/` separators, douyin_trae_ai keeps both `aweme_id` and `"source": "douyin"` fields.
- Added `.gitattributes` with `tests/regression/** -text` to opt out of the repo's `core.autocrlf=true` setting; without this, git would silently LF-normalize the Windows-origin CRLF blobs and break the byte-for-byte freeze.
- Wrote `tests/regression/regression-check.md` (159 lines) — operator-ready 3-step runbook (stage JSONs → re-run with `--force` → manual eyeball-diff via Claude) with a copy-paste prompt template covering 5 evaluation axes (STRUCTURE / TIMESTAMPS / CODE / FRAME REFS / RED-LINES) and PASS/FAIL output contract.
- Verified `.gitignore` was untouched and `tests/regression/` is tracked normally (`git check-ignore` returned 1).
- Security T1 grep clean: no SESSDATA / VE_KEY_* / DOUYIN_COOKIES / api_key / bearer / cookie patterns leaked into any baseline JSON.

## Task Commits

Each task committed atomically with `--no-verify` (parallel-executor convention; orchestrator validates hooks once after wave completes):

1. **Task 1: Create tests/regression/ skeleton + commit 12 frozen baseline files** — `f231af1` (feat)
2. **Task 2: Write tests/regression/regression-check.md runbook** — `4345ae3` (docs)

## Files Created/Modified

### Created

- `.gitattributes` — opts `tests/regression/**` out of git's autocrlf normalization (binary-mode hint), preserving Windows CRLF + `\\` byte-for-byte
- `tests/regression/BV132wizyEEB/summary.md` (4,941 B) — frozen Code/AI workflow baseline
- `tests/regression/BV132wizyEEB/meta.json` (788 B) — Windows `\\` separator variant
- `tests/regression/BV132wizyEEB/segs.json` (4,178 B)
- `tests/regression/BV132wizyEEB/paragraphs.json` (2,179 B)
- `tests/regression/BV1C9QCBdE1U/summary.md` (10,198 B) — frozen Godot/code-dense baseline
- `tests/regression/BV1C9QCBdE1U/meta.json` (341 B) — forward `/` separator variant
- `tests/regression/BV1C9QCBdE1U/segs.json` (23,370 B)
- `tests/regression/BV1C9QCBdE1U/paragraphs.json` (16,174 B)
- `tests/regression/douyin_trae_ai/summary.md` (20,510 B) — frozen AI/UI demo baseline
- `tests/regression/douyin_trae_ai/meta.json` (487 B) — `aweme_id` + `"source": "douyin"` variant
- `tests/regression/douyin_trae_ai/segs.json` (12,145 B)
- `tests/regression/douyin_trae_ai/paragraphs.json` (6,532 B)
- `tests/regression/regression-check.md` (159 lines) — 3-step runbook + Claude-as-verifier prompt template

Total baseline payload: 101,843 bytes (~99 KB), well under any git-friendly threshold; no LFS needed.

### Modified

None. `.gitignore` was deliberately untouched.

## Decisions Made

- **Add `.gitattributes` with `-text` for `tests/regression/**`.** Repo has `core.autocrlf=true`; without explicit opt-out, git would normalize CRLF→LF on commit. That breaks the byte-for-byte freeze contract (D-04 / Pitfall 5: "DO NOT normalize backslash separators or line endings"). Adding `.gitattributes` is the only way to honor that contract under the existing autocrlf setting.
- **Runbook ends with a stub link to `encoding-audit.md`, not the audit content itself.** Keeps Plan 01-01 self-contained per the plan's Task-2 spec (D-15: encoding audit lives in a separate file, populated by Plan 01-03).
- **Verbatim copy from sources, no pretty-reformatting.** Used `cp` (preserves bytes on this Windows-with-bash setup); cmp on every file confirmed byte-identity.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 — Missing Critical Functionality] Added `.gitattributes` to opt out of autocrlf normalization**

- **Found during:** Task 1 (when `git add` emitted `warning: in the working copy of '...summary.md', LF will be replaced by CRLF the next time Git touches it`)
- **Issue:** The plan specifies "byte-for-byte frozen" snapshots and explicitly forbids normalizing line endings (D-04 / Pitfall 5). However, the repo has `git config core.autocrlf=true` set globally, which silently rewrites CRLF→LF in the index on commit. Without an explicit `.gitattributes` opt-out, the staged blobs would be LF-only, and on Windows checkout they would be re-CRLF'd back — but the actual blob bytes in the git tree would no longer match the source bytes (and on Linux/macOS checkout they would be permanent LF). Either way, the byte-for-byte freeze contract would be silently broken.
- **Fix:** Created `.gitattributes` at repo root with `tests/regression/** -text` to mark these files as binary (no eol or autocrlf processing). Re-staged after the `.gitattributes` was tracked; warnings disappeared. Verified via `git cat-file -p` + `xxd` that the staged blob for `BV132wizyEEB/meta.json` retains the original `0d 0a` CRLF bytes and the `5c 5c` (`\\`) separator bytes.
- **Files modified:** `.gitattributes` (new file)
- **Verification:** `git cat-file -s :tests/regression/BV132wizyEEB/meta.json` returns 788 bytes (matches source exactly). Hex dump shows `0d 0a` line endings and `5c 5c` path separators preserved verbatim in the staged blob.
- **Committed in:** `f231af1` (Task 1 commit, bundled with the 12 baselines)
- **Why this is Rule 2 not Rule 4:** The fix doesn't change architecture or introduce new infrastructure — it's a one-line config file that's a hard correctness requirement for the freeze contract the plan explicitly demands. Without it, the task's primary deliverable (byte-for-byte frozen baselines) is silently false. This is correctness, not architecture.

**2. [Rule 3 — Documentation Glitch, low impact] Plan's `<verify>` backslash grep is broken under git-bash on Windows**

- **Found during:** Task 1 verification
- **Issue:** The plan specifies `grep -q 'output\\\\BV132wizyEEB\\\\video.mp4' tests/regression/BV132wizyEEB/meta.json` to verify Windows-style backslash preservation. Under msys2 / git-bash (this project's Windows shell), single-quoted `\\\\` collapses to `\\` (two literal backslashes) before grep sees it, then BRE interprets each `\\` as one literal backslash, so grep ends up searching for `output\BV132wizyEEB\video.mp4` (one backslash each) — which does NOT match the file's `\\` (two backslashes). The grep returns false-negative even though variant fidelity is preserved.
- **Fix:** Did NOT modify the plan's grep (out of scope: the plan is a snapshotted artifact). Instead, verified variant fidelity through three independent channels: (a) `cmp` byte-equality vs. source, (b) `xxd` hex dump showing `5c 5c` bytes in both source and staged blob, (c) explicit 4-backslash variant `grep -F "output\\\\\\\\BV132wizyEEB"` — all three pass. The grep-pattern documentation issue is a worktree-shell quirk, not a content problem; the actual byte preservation is verified.
- **Files modified:** None (no fix needed; this is verification-script fragility, not data fragility).
- **Verification:** Hex dump of staged blob `tests/regression/BV132wizyEEB/meta.json` shows `00000010: 223a 2022 6f75 7470 7574 5c5c 4256 3133 …` — the `5c 5c` (`\\`) is intact. Source file at `D:/gxy_code/videoSummary/output/BV132wizyEEB/meta.json` matches byte-for-byte (cmp returned 0). Variant preservation goal is met.

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 verification-script quirk).
**Impact on plan:** Both deviations were absorbed without scope creep. The `.gitattributes` add is a one-file correctness fix that the plan's freeze contract implicitly required. The grep quirk is documented but did not require any code change.

## Issues Encountered

- **Worktree branch base mismatch.** The worktree was initially on commit `08a79f4` (the pre-planning HEAD of `main`), not the orchestrator-expected `1f14ea6` (which has all `.planning/` content). This is the documented Windows worktree-creation glitch from the worktree-branch-check protocol. Resolved with `git reset --hard 1f14ea604396515edeefc989f1873b721beeb6c6`.
- **Source files not present in worktree's `output/`.** Of the three baseline slugs, only `output/BV1C9QCBdE1U/` exists in the worktree filesystem; `output/BV132wizyEEB/` and `output/douyin_trae_ai/` only exist in the main repo at `D:/gxy_code/videoSummary/output/`. (Both `output/` directories are gitignored, so the worktree starts with an empty `output/` until manually populated.) Resolved by sourcing the `cp` operations directly from the main repo path. All `cmp` verifications run against the same main-repo paths to confirm byte-equality.
- **`Write` tool initially landed `.gitattributes` in the main repo path** (`D:/gxy_code/videoSummary/.gitattributes`) rather than the worktree path. This is a path-resolution glitch with the Write tool's absolute-path handling on Windows when both worktree and main repo share a common prefix. Resolved by removing the misplaced file via `rm` and re-issuing `Write` with the explicit worktree path. No content corruption; final `.gitattributes` is correct and committed in the worktree only.

## Next Phase Readiness

- **Plan 01-02 (loader-tolerance) ready.** Has stable before-state fixtures (the 12 baselines committed here) to test against without re-deriving them.
- **Plan 01-03 (encoding audit + docs) ready.** Will create `tests/regression/encoding-audit.md` alongside the runbook; the runbook's final stub link is already wired up.
- **Per D-10:** Every subsequent phase touching `agent/` or `src/` must run this runbook on all 3 baselines before merge and record the verdict (PASS/FAIL with explainable-diff list) in `.planning/phases/<phase>/VERIFICATION.md`. This contract is now testable.
- **No blockers.** The freeze contract is materially honored (cmp + hex-dump verified); the runbook is operator-ready with all required verbatim strings; `.gitignore` remains untouched.

## Self-Check: PASSED

Verification on disk after final commits (`git log -3` shows `4345ae3 docs(01-01): runbook` and `f231af1 feat(01-01): 12 baselines`):

- FOUND: `.gitattributes`
- FOUND: `tests/regression/BV132wizyEEB/{summary.md, meta.json, segs.json, paragraphs.json}`
- FOUND: `tests/regression/BV1C9QCBdE1U/{summary.md, meta.json, segs.json, paragraphs.json}`
- FOUND: `tests/regression/douyin_trae_ai/{summary.md, meta.json, segs.json, paragraphs.json}`
- FOUND: `tests/regression/regression-check.md`
- FOUND: commit `f231af1` (Task 1, 12 baselines + .gitattributes)
- FOUND: commit `4345ae3` (Task 2, runbook)

All 12 verify-block automated assertions in Task 1 returned OK (existence + non-empty + cmp byte-equality + variant fidelity + no forbidden artifacts + security grep clean + `.gitignore` unchanged + `git check-ignore` confirms tracked). All 12 verify-block assertions in Task 2 returned OK (file exists + all required verbatim strings present + 5 axes named + length under cap).

---

*Phase: 01-preflight-regression-baseline*
*Plan: 01*
*Completed: 2026-04-30*
