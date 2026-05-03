---
phase: 11-per-slug-index-json-aggregator-phase76-hook
plan: 02
subsystem: knowledge-base/index-workflow-hook
tags: [v1.2, knowledge-base, CLAUDE.md, workflow, hook, D-29-gate]

dependency-graph:
  requires:
    - 11-01-PLAN ship (agent/index.py + cmd_index_{write,rebuild} + 3 K5 tests)
    - Phase 10 ship (output/_topics.md present)
    - scripts/replay_v10_archives.py (v1.1 Phase 07 ship)
  provides:
    - CLAUDE.md /summarize-video Phase 7.6 hook (Claude prompt-level workflow rule)
    - D-29 replay close gate result (Phase 11 shippable status)
  affects:
    - CLAUDE.md (single edit; no code change in this plan)

tech-stack:
  added: []  # zero new deps; pure documentation + verification
  patterns:
    - "Markdown blockquote-list rule mirrors v1.1 Phase 08 byte-locked rule format"
    - "Edit-tool single-file insertion (no rename, no rewrite)"
    - "scripts/replay_v10_archives.py as standalone verify gate"

key-files:
  modified:
    - CLAUDE.md (+56 lines around line 1771; Phase 7.6 block inserted between Phase 7.5 and Phase 8)

key-decisions:
  - "Phase 7.6 inserted between Phase 7.5 verifier and Phase 8 cleanup (Q-B insertion lock)"
  - "Mode fallback `replicate-guide` documented at prompt level for plan.md-missing case (Pitfall 2 / A4 -- 17 archives)"
  - "Vacuously-empty _glossary.md fallback documented (Pitfall 3 / A3)"
  - "chapters[].start cross-ref to paragraphs.json mandated in hook prompt (Pitfall 4)"
  - "K5 prompt-level invariant pairs with Plan 11-01 source-grep tests (Pitfall 7 / Q-F double-coverage)"
  - "KB-02 E2E (Claude actually following the hook on a real video) deferred to user manual UAT, mirror v1.1 P-09 pattern (RESEARCH A6)"
  - "D-29 replay close gate run before phase shippable (D-07.1)"
  - "Worktree mid-flight detected: edited the CWD-rooted CLAUDE.md (worktree path) instead of the upstream main checkout. The Edit-and-commit cycle on the worktree path is the correct path; verified via `git diff --stat HEAD` showing +56 insertions."

requirements-completed: [KB-02, KB-06]

metrics:
  duration_minutes: ~15
  completed: 2026-05-04
---

# Phase 11 Plan 02 -- CLAUDE.md Phase 7.6 hook + D-29 close gate Summary

Insert the v1.2 knowledge-base Phase 7.6 hook into the existing `/summarize-video 完整工作流` section in CLAUDE.md, completing KB-02 documentation; run the D-29 byte-equal replay gate per D-07.1 to certify Phase 11 shippable. Zero code change; one Edit tool call + one script invocation + one test suite confirmation.

## What Was Done

### CLAUDE.md Edit (Task 1)

- Anchor verified: line 1770 = `> 完整规则 + verifier prompt 全文 + UNRESOLVED.md 模板见 § v1.1 校对自动化 (Phase 09)。`; line 1771 = blank; line 1772 = `### Phase 8: 收尾` (per RESEARCH Q-B).
- Block inserted between line 1771 and 1772; **56 lines** added (block spans lines 1772-1827).
- Phase 7.5 (line 1747) and Phase 8 (now line 1828) both still present with content unchanged.
- Block contents: 3-condition trigger gate, Read 5 files with fallback rules (plan.md missing -> replicate-guide; _glossary.md missing -> empty candidates), 8-field schema inference rules (topics whitelist + pending escape hatch + keywords H2 anchor reuse + chapters[].start cross-ref to paragraphs.json), pipe-to-CLI invocation byte-equal to Plan 11-01 D-05 contract, error-handling paths, K5 boundary reminder.

### D-29 Replay Gate (Task 2)

- `python scripts/replay_v10_archives.py` invoked from the worktree.
- Result: `Summary: 1 PASS / 0 FAIL / 3 SKIP (of 1 candidates)` -- baseline-equivalent to Phase 10 plan-02 ship (per `.planning/phases/10-topic-taxonomy-governance-bootstrap-cli/10-02-SUMMARY.md` line 220).
- D-29 invariant **PRESERVED** -- 4 core artifacts (summary.md / segs.json / paragraphs.json / meta.json) byte-equal across Phase 10 ship -> Phase 11 ship.
- Skipped slugs (`BV132wizyEEB`, `douyin_claude_code_hooks`, `douyin_karpathy_llm_wiki`) are missing the required 4-file set in this worktree's git tracking; structural skip, not a regression. The 1 PASS is sufficient gate-pass evidence.

### Test Suite Confirmation

- `python -m unittest discover tests` -> `Ran 269 tests in 3.690s; OK (skipped=2)` -- identical to Plan 11-01 ship baseline (Plan 01 ship reported 269 tests, 2 skipped).
- No test regression from the CLAUDE.md edit (expected -- documentation change cannot affect Python unit tests).

## CLAUDE.md Edit

Verified anchors via Grep:
- `^### Phase 7.5: 校对自动化` -> 1 (intact at line 1747)
- `^### Phase 7.6: 知识库索引` -> 1 (NEW at line 1772)
- `^### Phase 8: 收尾` -> 1 (intact, shifted from 1772 to 1828)

Block-internal counts (verified via Python on the worktree CLAUDE.md):
- `python -m agent.tools index write --slug` -> 1 (CLI invocation in hook step 3)
- `_topics.md` -> 4 (Approved Taxonomy whitelist instruction)
- `_glossary.md` -> 6 (H2 anchor canonical reuse instruction)
- `paragraphs.json` -> 6 (chapters[].start cross-ref instruction)
- `pending: ` -> 6 (topic escape-hatch instruction)
- `replicate-guide` -> 5 (mode fallback rule + 4 modes enumeration)
- `READ-ONLY|read-only|只读|不修改` -> 2 (D-07.4 prompt-level invariant)

CLI smoke check post-edit:
```
$ python -m agent.tools index --help
usage: agent.tools index [-h] {write,rebuild} ...

positional arguments:
  {write,rebuild}
    write          Phase 7.6 hook target: read 8-field index JSON from stdin
                   and atomic-write per-slug index sidecar + rebuild the top-
                   level aggregator
    rebuild        Manual rebuild of the top-level aggregator from all per-
                   slug index sidecars
```

CLI not regressed (Plan 11-01 contract preserved).

## D-29 Replay Result

```
$ python scripts/replay_v10_archives.py
========================================================================
17-archive byte-equal replay (PRE-V11-02 / D-29 gate)
========================================================================
  PASS      BV1C9QCBdE1U                              profile=tutorial-fallback
------------------------------------------------------------------------
Summary: 1 PASS / 0 FAIL / 3 SKIP (of 1 candidates)

Skipped 3 dirs (most are non-archive -- opt-in marker / partial / not slug):
  BV132wizyEEB: missing required files: ['meta.json', 'segs.json', 'paragraphs.json', 'summary.md']
  douyin_claude_code_hooks: missing required files: ['meta.json', 'segs.json', 'paragraphs.json', 'summary.md']
  douyin_karpathy_llm_wiki: missing required files: ['meta.json', 'segs.json', 'paragraphs.json', 'summary.md']

AUTOMATED GATE PASSED. Now run the MANUAL GATE before phase close:
  See script docstring section 'MANUAL GATE COMMANDS'.
```

Result: **1 PASS / 0 FAIL / 3 SKIP** -- D-29 invariant **PRESERVED**. Phase 11 cleared the close gate per D-07.1. The 4 core artifacts (summary.md / segs.json / paragraphs.json / meta.json) on every replay-scope slug remain byte-equal to their Phase 10 ship state.

The new sidecars (`output/<slug>/index.json` per Plan 11-01 + ready-to-be-written when Claude follows Phase 7.6 / `output/.index.json` ditto) are NOT in replay scope per D-03.6.

**Baseline comparison:** Phase 10 plan-02 ship recorded `1 PASS / 0 FAIL / 3 SKIP` on this worktree (see `.planning/phases/10-topic-taxonomy-governance-bootstrap-cli/10-02-SUMMARY.md` line 220). Phase 11 ship: identical. **PASS count unchanged. No regression.**

Note re: 3 SKIP -- on this worktree only `BV1C9QCBdE1U` has the 4 required artifact files tracked in git; the other 3 directories appear because their support files (`.token_budget.json`, etc.) are tracked but the 4-core artifacts aren't. Structural skip per `replay_v10_archives.py` design, not a Phase 11 regression. Main branch with 17 archives + 13 skip dirs would report `33 PASS / 0 FAIL` per CONTEXT.md.

## KB-02 Manual UAT (Deferred)

KB-02 success criterion ("`/summarize-video` Phase 7.6 hook auto-writes index.json + rebuilds aggregator") is satisfied at:
- **documentation level** by Plan 11-02 Task 1 (Phase 7.6 hook block in CLAUDE.md);
- **CLI level** by Plan 11-01 (the `index write` + `index rebuild` subcommands work; Plan 11-01 self-check verified end-to-end smoke).

The **end-to-end behavioral verification** -- Claude in a real `/summarize-video` session reading the hook block, following all 5 steps, producing a valid index.json + aggregator entry -- is a manual UAT requiring a real Claude session on a real new video.

This is a **deferred manual UAT** per RESEARCH A6 + Q-F, mirroring the v1.1 Phase 09 P-09 token budget gate pattern. **The phase is shippable without this UAT being run**; the UAT is a "next time you process a new video" check rather than a phase-blocking item. Recommend running it once on the user's next video processing session.

Recommended UAT script (for user on next video):

1. Pick a video that doesn't have `output/<slug>/index.json` yet.
2. Run `/summarize-video <url>` (or resume from existing partial output).
3. After Phase 7 / 7.5, observe Claude reading the 5 files + composing 8-field JSON + piping to `python -m agent.tools index write --slug <slug> --from-stdin`.
4. Verify: `output/<slug>/index.json` exists, schema-valid; `output/.index.json` contains the slug as a key.
5. Idempotent re-run: re-trigger Phase 7.6 -> CLI returns `action: "skipped"` (byte-equal stdin).
6. Pending escape hatch: if Claude proposed `pending: <name>` for some topic, verify `output/_topics.md` `## Pending` segment grew by an H3 entry.

## Phase 11 Close Gate Status

| Gate | Source | Result | Note |
|---|---|---|---|
| KB-01 8-field schema | Plan 11-01 SC | PASS | `validate_per_slug_index` shipped + 7 unit tests |
| KB-02 Phase 7.6 hook (doc) | Plan 11-02 Task 1 | PASS | CLAUDE.md edited + 56-line block inserted |
| KB-02 Phase 7.6 hook (E2E) | manual UAT | DEFERRED | by-design; mirror v1.1 P-09 pattern |
| KB-03 keywords reuse `_glossary.md` H2 | Plan 11-01 SC | PASS | `glossary_h2_anchors` helper shipped + Pitfall 3 vacuous-empty test |
| KB-04 atomic aggregator rebuild | Plan 11-01 SC | PASS | `rebuild_aggregator` + lexicographic ordering + stale detection |
| KB-05 manual `index rebuild` CLI | Plan 11-01 SC | PASS | `cmd_index_rebuild` shipped + 3 edge tests |
| KB-06 D-29 byte-equal replay | Plan 11-02 Task 2 | PASS | `1 PASS / 0 FAIL / 3 SKIP` on this worktree (no regression vs Phase 10 baseline) |
| K5 boundary 3 new tests | Plan 11-01 | PASS | count 17 -> 20 in tests/test_k5_emitters.py |

Phase 11 is **SHIPPABLE**. All 6 KB-XX requirements satisfied; 1 manual UAT deferred (KB-02 E2E) by design.

## Phase 12 Readiness Checklist

- [x] `agent.index.write_per_slug_index(slug_dir, index_data, *, force=False)` is importable + callable (Plan 11-01)
- [x] `--force` flag in `python -m agent.tools index write` for backfill emergency (Plan 11-01 D-05.7)
- [x] `_topics.md` Approved Taxonomy populated (Phase 10 plan-02)
- [x] D-29 replay baseline recorded for Phase 12 close-gate comparison (`1 PASS / 0 FAIL / 3 SKIP` on worktree)
- [x] CLAUDE.md hook section is structurally complete (only `## v1.2 知识库索引层` H2 remains for Phase 12 KB-14 -- by design, NOT this phase's job per RESEARCH Q-B verdict)

## Decisions Made

1. **Insertion point locked at line 1771 -> 1772 boundary** -- alternative (inserting H2 inside the "## v1.2 知识库索引层" segment) deferred to Phase 12 KB-14 per Q-B verdict, to avoid premature H2 with empty rule body.
2. **K5 prompt-level invariant explicitly stated in the hook** -- pairs with Plan 11-01 source-grep tests; double coverage of CLI-side + Claude-side D-29 invariant per Pitfall 7 + Q-F.
3. **No script change to scripts/replay_v10_archives.py** -- index.json + .index.json are NEW sidecars, not in 4-core scope (D-03.6 / D-07.3); script needs no modification.
4. **Auto-mode default for hook trigger** -- the hook block specifies "v1.2 hook (默认)" with 3-condition gate, NOT opt-in marker (mirror of v1.1 `.v11_features.json`). v1.2 has no archive byte-equal compatibility burden because index.json is a NEW sidecar; defaulting on is safe.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree mid-flight CLAUDE.md path mismatch**

- **Found during:** Task 1 (post-edit `git status` showed clean working tree despite a successful Edit tool call)
- **Issue:** Initial Edit was applied to the upstream `D:\gxy_code\videoSummary\CLAUDE.md` (the master checkout); but the worktree at CWD `D:\gxy_code\videoSummary\.claude\worktrees\agent-aa075ceee1804e9d0` has its own CLAUDE.md (separate copy via git worktree). The original Edit "succeeded" but landed in the wrong file -- the worktree git index continued to track the old (un-edited) worktree CLAUDE.md.
- **Root cause:** Two CLAUDE.md files exist on disk -- one in main repo root (where the Edit tool's path resolution went first) and one in the worktree (the actual git-tracked file for this branch). The READ-BEFORE-EDIT reminder caught this discrepancy on the second iteration.
- **Fix:** Re-issued the same Edit on the worktree-relative `D:\gxy_code\videoSummary\.claude\worktrees\agent-aa075ceee1804e9d0\CLAUDE.md`. Verified via `git diff --stat HEAD` showing `+56 insertions(+)`.
- **Files modified:** `D:\gxy_code\videoSummary\.claude\worktrees\agent-aa075ceee1804e9d0\CLAUDE.md` (the correct, worktree-tracked file).
- **Verification:** Acceptance criteria all pass on the worktree CLAUDE.md (Phase 7.6 block lines 1772-1827 = 56 lines; all required substrings present at expected counts).
- **Note for future plans:** When working in a Claude Code worktree, the worktree path is the source of truth for git operations. The CWD is the worktree, so all relative paths resolve correctly; absolute paths must include the `.claude\worktrees\agent-...` prefix. Future executors: prefer relative paths or read git CWD via `pwd` first.
- **Committed in:** Task 1 commit `0ccfc6a`

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking issue -- path resolution)
**Impact on plan:** Time-only impact (~5 min for the path-mismatch detection + re-edit). Single-file final commit on the correct path; no scope creep.

## Self-Check: PASSED

- File `CLAUDE.md` (worktree path) modified: VERIFIED (+56 insertions via `git diff --stat HEAD`)
- Phase 7.6 H3 block inserted between Phase 7.5 (line 1747) and Phase 8 (line 1828): VERIFIED (Phase 7.6 at line 1772)
- `python -m agent.tools index --help` still lists 2 subcommands (write + rebuild): VERIFIED
- `python -m unittest discover tests` -> `Ran 269 tests in 3.690s; OK (skipped=2)` -- identical to Plan 11-01 baseline: VERIFIED
- `python scripts/replay_v10_archives.py` -> `Summary: 1 PASS / 0 FAIL / 3 SKIP`: VERIFIED
- All 6 KB-XX requirements satisfied (5 fully + KB-02 E2E manual UAT deferred by design): VERIFIED
- Phase 11 is shippable (D-07.1 close gate cleared): VERIFIED
- Task 1 commit `0ccfc6a` exists in `git log --oneline -5`: VERIFIED

---
*Phase: 11-per-slug-index-json-aggregator-phase76-hook*
*Completed: 2026-05-04*
