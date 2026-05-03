---
phase: 07-warm-up-k5-emitters-d-29-foundation
verified: 2026-05-03T09:00:00Z
status: human_needed
score: 5/5 ROADMAP success criteria + 8/8 requirement IDs satisfied (with one human-gated piece on SC#1)
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Manual /summarize-video re-run gate — D-29 byte-equal on summary.md (SC#1 Part 2)"
    expected: |
      Re-invoke `/summarize-video` from a FRESH Claude session on 2 archives:
        1) BV132wizyEEB (replicate-guide)
        2) douyin_karpathy_llm_wiki (interview-distillation)
      Write each to a temp slug dir (e.g., output/test_replay_<slug>/), then:
        git diff --no-index output/<slug>/summary.md output/test_replay_<slug>/summary.md
      Both diffs MUST be empty (byte-equal).
      After running, append `## Manual Gate Results` to 07-01-SUMMARY.md per the procedure on line 188+ of that file.
    why_human: |
      `/summarize-video` is a Claude slash command, not a Python function — the verifier cannot auto-invoke it.
      The Python automated gate (paragraphs.json regen byte-equal + segs/meta/summary mid-test mutation hash) PASSED 33/0/30
      on `python -m scripts.replay_v10_archives --output-dir output`, but the user-driven re-run gate is documented in
      07-01-SUMMARY.md "Phase Close — MANUAL GATE Procedure" and has NOT yet been performed (no `## Manual Gate Results`
      section appended). Phase plan calls this out as a phase-close requirement.
  - test: "CLAUDE.md line 1118 doc drift — references old `transcribe_warnings.json` instead of post-CR-01 `transcribe_lint_warnings.json`"
    expected: |
      Line 1118 currently documents the table cell as `transcribe_warnings.json`. The actual artifact written by
      `cmd_transcribe_lint` is `transcribe_lint_warnings.json` (per CR-01 fix to avoid collision with Phase 5
      `_emit_repetition_warnings` repetition guard). One-line edit:
        sed -i 's|`transcribe_warnings.json`|`transcribe_lint_warnings.json`|' CLAUDE.md  (line 1118 only)
      Or open CLAUDE.md and update line 1118 manually.
    why_human: |
      Cosmetic doc fix that should be confirmed by the developer (verifier will not edit CLAUDE.md autonomously). Code
      behaviour is correct — only the documentation table is stale. Phase 8 prompts read CLAUDE.md and could be misled
      into looking for a non-existent file.
---

# Phase 07: Warm-up + K5 emitters + D-29 foundation — Verification Report

**Phase Goal:** Establish v1.1 opt-in foundation (D-29 byte-equal preserved on 17 archives), ship 4 new K5 read-only signal emitters that Claude can consult but never auto-promote, demote AV1 noise, and add a queue helper. Zero behavior change to any newly written summary.md.
**Verified:** 2026-05-03T09:00:00Z
**Status:** human_needed (automated checks all passed; one phase-close manual gate + one trivial doc-drift fix outstanding)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (5 ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 17-archive replay PASS gate (P-08) — byte-equal `summary.md / segs.json / paragraphs.json / meta.json` | ⚠️ PARTIAL — automated PASS / manual untaken | `python -m scripts.replay_v10_archives --output-dir output` ran live → **33 PASS / 0 FAIL / 30 SKIP**. Strict gate met for paragraphs.json byte-equal regen AND segs/meta/summary mid-test mutation hash check. Manual `/summarize-video` re-run gate (covers true summary.md byte-equal — Python can't invoke a Claude slash cmd) is **documented but NOT yet performed**; 07-01-SUMMARY.md "## Manual Gate Results" section is empty. |
| 2 | `.v11_features.json` opt-in marker controls all v1.1 paths; archives without marker silently take v1.0 branches | ✓ VERIFIED | `agent/_v11.py:is_v11_enabled` returns False on missing marker (verified live: `is_v11_enabled(Path('output/BV132wizyEEB')) → False`). 33 v1.0 archives passed byte-equal replay → no `transcribe_warnings.json` (Phase-7 variant) / `transcribe_lint_warnings.json` / glossary append / inline traces appeared on any archive. Marker filename locked at `.v11_features.json`; 8-feature `V11_FEATURES` allowlist tuple in `agent/_v11.py:33-42`. |
| 3 | `.token_budget.json` baseline measured on 3 representative archives | ✓ VERIFIED | All 3 files exist with valid v1 schema: `output/BV132wizyEEB/.token_budget.json` mode=replicate-guide total=1917 tokens; `output/douyin_karpathy_llm_wiki/.token_budget.json` mode=interview-distillation total=5252; `output/douyin_claude_code_hooks/.token_budget.json` mode=extension-applications total=1906. All 5 layers (transcribe / aggregate / plan / write / cleanup) populated; `chars/3.5` proxy method recorded. |
| 4 | 4 new K5 emitters with statically-asserted source-grep tests (transcribe_lint, mode_signals, schedule_suggest, glossary_audit) | ✓ VERIFIED | All 4 modules exist + CLI subparsers present + 8 source-grep static assertions in `tests/test_k5_emitters.py` (4 handler `inspect.getsource` + 4 module `Path.read_text`). Live re-run: `python -m unittest tests.test_k5_emitters -v` → 8/8 PASS. `FORBIDDEN_LITERALS = ("summary.md", "plan.md", "schedule.json")` enforced on every cmd_* AND module file. Schedule suggest `--duration` W5 override flag visibly present in `--help`. mode_signals correctly omits `recommended_mode` (P-07 K5). |
| 5 | MISC打杂 shipped — AV1 demoted to INFO; `queue {add\|list\|next\|done\|skip}` works under FileLock; two-terminal race tests pass; `queue next` marks `in_progress: <pid>` | ✓ VERIFIED | `agent/sources/_common.py:111` HEVC stays `log.warning`; `agent/sources/_common.py:117` AV1 split to `log.info`; message text byte-equal across both branches (P-08 spirit on log strings preserved). `python -m agent.tools queue --help` shows 5 subcommands. End-to-end smoke test passed (add → list → next → done → cleanup). T13 race test (5-way subprocess `queue_next` → 5 distinct slugs + 5 in_progress in final state) PASSES live. T12 add-race PASSES (5 concurrent adds → 5 distinct items, no JSON corruption). |

**Score:** 5/5 truths verified (1 with documented partial / outstanding human action — see human_verification block).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent/_v11.py` | Opt-in marker library; exports `is_v11_enabled` / `set_v11_marker` / `get_v11_marker` / `V11_FEATURES` / `MARKER_FILENAME` | ✓ VERIFIED | 4137 bytes; live import + `len(V11_FEATURES) == 8`; corrupt-file returns None silently; atomic write via `agent.io.write_json_atomic` |
| `scripts/replay_v10_archives.py` | 17-archive byte-equal regression test with per-slug profile resolution | ✓ VERIFIED | 14371 bytes; `_load_profile_for_slug` (B2 fix) reads `paragraphs.json.params.json` sidecar (cli > func > tutorial fallback); `_replay_one` regens paragraphs.json in tempdir + byte-diffs + mutation-hash-checks segs/meta/summary; `--slug` / `--json` / `--output-dir` flags; live exit 0 with strict 0 FAIL gate |
| `scripts/measure_token_budget.py` | Per-archive `.token_budget.json` writer | ✓ VERIFIED | 6224 bytes; `KNOWN_MODES` pre-classification of 3 representative slugs; chars/3.5 deterministic proxy; 3 baseline files committed under gitignored `output/` (force-added per Plan 01 key-decisions) |
| `agent/queue.py` | Queue CRUD with FileLock | ✓ VERIFIED | 6047 bytes; reuses `agent/_lock.FileLock` via `from agent._lock import FileLock`; every R-M-W wrapped in `FileLock(queue_lock_path(), timeout=5.0)`; `queue_dir() == Path.home() / '.videoSummary'`; per-PID `in_progress` marker prevents double-pickup |
| `agent/transcribe_lint.py` | L1 ASR suspect-token detector with 5 strategies including pypinyin homophone_cluster | ✓ VERIFIED | 12999 bytes; `from pypinyin import lazy_pinyin` (line 33); `_pinyin_signature()` calls `lazy_pinyin()`; Pass 4 emits `evidence_source="homophone_cluster"` warnings. Live test on synthetic '训练' (8x) + '迅练' (1x) → emits 1 warning with `suggested_text='训练'`, `evidence_source='homophone_cluster'`, `confidence=0.65`, `evidence_detail='pinyin=xunlian, candidate freq=8'` ✓ pypinyin NOT dead weight. Bigram extraction fix (Plan 03 deviation #1) wired correctly. WARNINGS_FILENAME=`transcribe_lint_warnings.json` (CR-01 fix avoids collision with Phase 5 `transcribe_warnings.json`). |
| `agent/mode_signals.py` | 5 objective signals; NO `recommended_mode` field | ✓ VERIFIED | 4475 bytes; `compute_signals()` returns 5 keys (code_fence_density, step_marker_density, question_form_ratio, speaker_turn_signals, cross_tool_comparison_count); explicit absence of `recommended_mode` field (P-07 K5); `_hash_paragraphs()` for staleness detection; CLI handler reuses helper (WR-06 fix) |
| `agent/schedule_suggestion.py` | fps-segment generator + mandatory FPS-04 baseline + `--duration` W5 override | ✓ VERIFIED | 4705 bytes; `compute_suggestion()` always appends `{label: "fps-04-baseline", fps: 0.05, start: 0, end: duration}` (D-08 strict-OR-fallback gate); `duration_source` provenance recorded ('ffprobe' or '--duration-override'); `--duration` flag visible in CLI help (W5 fix) |
| `agent/glossary_audit.py` | Read-only audit of `output/_glossary.md` (Phase 08 stub) | ✓ VERIFIED | 2831 bytes; `audit_glossary(path?)` parses H2 anchors → reports duplicate_terms + conflicting_definitions; missing-file path returns schema-stable shape (`exists: False`, all empties); never writes to glossary file |
| `agent/tools.py` | 5 queue subparsers + 4 K5 emitter subparsers + dispatch | ✓ VERIFIED | All 9 cmd_* handlers present (cmd_queue_add/list/next/done/skip + cmd_transcribe_lint/mode_signals/schedule_suggest/glossary_audit); existing 14 v1.0 subcommands untouched (regression-safe nested dispatch via `if args.command == "queue":`) |
| `tests/test_k5_emitters.py` | 8 source-grep static assertions | ✓ VERIFIED | 2759 bytes; `TestK5BoundaryPhase07` class with exactly 8 test methods (4 `test_K5_handler_*` + 4 `test_K5_module_*`); each iterates `FORBIDDEN_LITERALS = ("summary.md", "plan.md", "schedule.json")`; live run 8/8 PASS |
| `output/BV132wizyEEB/.token_budget.json` | Replicate-guide baseline | ✓ VERIFIED | total_approx_tokens=1917; mode=replicate-guide; all 5 layers populated |
| `output/douyin_karpathy_llm_wiki/.token_budget.json` | Interview-distillation baseline | ✓ VERIFIED | total_approx_tokens=5252; mode=interview-distillation; all 5 layers populated |
| `output/douyin_claude_code_hooks/.token_budget.json` | Extension-applications baseline | ✓ VERIFIED | total_approx_tokens=1906; mode=extension-applications; all 5 layers populated |
| `requirements.txt` line for pypinyin | `pypinyin>=0.55.0` present | ✓ VERIFIED | Line 7: `pypinyin>=0.55.0`; live `from pypinyin import lazy_pinyin; lazy_pinyin('训练') → ['xun', 'lian']` succeeds |
| CLAUDE.md Phase 07 section | New H2 section + Phase 6 amendment | ⚠️ MOSTLY VERIFIED | Line 1092 H2 heading `## v1.1 opt-in marker + 4 K5 emitters (Phase 07)` ✓; Line 167 Phase 6 cross-reference bullet ✓; Line 1138 `~/.videoSummary/.queue.lock` Multi-terminal lock 域扩展 ✓. **Drift:** Line 1118 documents emitter output as `transcribe_warnings.json` but actual code writes to `transcribe_lint_warnings.json` (post-CR-01). One-line cosmetic fix needed (see human_verification). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `agent/_v11.py` | `output/<slug>/.v11_features.json` | `write_json_atomic` + `now_iso` from `agent.io` | ✓ WIRED | `set_v11_marker` calls `write_json_atomic(target, obj)`; `get_v11_marker` reads via `p.read_text(encoding='utf-8')`; tolerant of missing/corrupt |
| `scripts/replay_v10_archives.py` | `output/<slug>/segs.json + paragraphs.json + summary.md + meta.json` | `hashlib.sha256` byte-equal comparison | ✓ WIRED | `_sha256_file(p)` baselines all 4 required files at start; `_replay_one()` regens paragraphs in tempdir + byte-diffs; mid-test mutation hash check on segs/meta/summary; live run 33 PASS / 0 FAIL |
| `scripts/replay_v10_archives.py` | `output/<slug>/paragraphs.json.params.json` sidecar | `_load_profile_for_slug` cli.profile → func.profile → tutorial fallback | ✓ WIRED | Live verified per Plan 01 evidence (B2 fix prevents false-FAIL on podcast-aggregated archives like douyin_karpathy_llm_wiki) |
| `agent/queue.py` | `~/.videoSummary/queue.json` | `FileLock(queue_lock_path(), timeout=5.0)` wraps every R-M-W | ✓ WIRED | All 4 mutating functions (queue_add/next/done/skip) acquire the lock; `_save()` calls `write_json_atomic` |
| `agent/queue.py` | `agent/_lock.FileLock` | `from agent._lock import FileLock` | ✓ WIRED | Line 36 import; reused (NOT re-implemented); Phase 6 PARA-01 stale-PID takeover applies |
| `agent/transcribe_lint.py` | `pypinyin.lazy_pinyin` | homophone_cluster Pass 4 — sparse CJK bigrams (freq < 3) get pinyin signature lookup | ✓ WIRED | Live test: synthetic '训练' (8x) + '迅练' (1x) → 1 warning with `suspect_text='迅练'`, `suggested_text='训练'`, `evidence_source='homophone_cluster'`, `confidence=0.65`, `evidence_detail='pinyin=xunlian, candidate freq=8'`. pypinyin NOT dead weight. |
| `agent/tools.py` | `agent/{transcribe_lint,mode_signals,schedule_suggestion,glossary_audit}.py` | Lazy import in cmd_* handlers (mirrors cmd_detect_scenes) | ✓ WIRED | All 4 subcommands callable via `python -m agent.tools <cmd> --help`; lazy imports preserve agent.tools import-light contract |
| `agent/tools.py:cmd_schedule_suggest` | `args.duration` override | If `--duration` flag provided, skip ffprobe (W5 archive-without-video.mp4 path) | ✓ WIRED | `--help` exposes flag with explanatory text; W5 fix verified per Plan 03 |
| `tests/test_k5_emitters.py` | 4 cmd_* handlers + 4 module files | `inspect.getsource()` + `Path.read_text()` + `assertNotIn` | ✓ WIRED | 8 tests run; all PASS; FORBIDDEN_LITERALS = `('summary.md', 'plan.md', 'schedule.json')` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `transcribe_lint` warnings list | `warnings` (list of dicts) | `detect_warnings(segs, meta)` Pass 1-4 over real segs.json input | Yes — live test produced exactly 1 homophone_cluster warning on synthetic data with correct evidence_detail | ✓ FLOWING |
| `mode_signals.json` 5 signals | `signals` dict (5 keys) | `compute_signals(paragraphs)` regex-driven scan over real paragraphs input | Yes — pure regex over input list, deterministic output | ✓ FLOWING |
| `schedule_suggestion.json` segments | `suggested_segments` list | `compute_suggestion(paragraphs, scenes, silence_map, duration_s)` always emits ≥ 1 default-coverage segment + 1 fps-04-baseline segment regardless of input | Yes — mandatory FPS-04 baseline guarantees non-empty output | ✓ FLOWING |
| `glossary_audit` JSON | `term_count`, `duplicate_terms`, `conflicting_definitions` | `audit_glossary(path)` parses H2 anchors via regex | Yes — falls back to `exists: False` empties on missing file (intentional schema-stable behavior, not a stub of an actual computation) | ✓ FLOWING |
| Queue items | `state["items"]` list of dicts | `_load_or_init()` from `~/.videoSummary/queue.json` | Yes — live smoke test added 1 entry, listed it, marked next, marked done; all state changes persisted | ✓ FLOWING |
| `.token_budget.json` per-layer | `layers` dict + `total_approx_tokens` | `_measure_layer(slug_dir, layer)` reads char counts from segs.json/paragraphs.json/plan.md/summary.md | Yes — 3 representative archive files contain real numbers (1917 / 5252 / 1906 tokens) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| _v11 module imports + V11_FEATURES tuple length | `python -c "from agent._v11 import V11_FEATURES; print(len(V11_FEATURES))"` | `8` | ✓ PASS |
| pypinyin works | `python -c "from pypinyin import lazy_pinyin; print(lazy_pinyin('训练'))"` | `['xun', 'lian']` | ✓ PASS |
| Replay script strict gate | `python -m scripts.replay_v10_archives --output-dir output` | `33 PASS / 0 FAIL / 30 SKIP` | ✓ PASS |
| Queue CLI end-to-end | `queue add → list → next → done → cleanup` | All 4 commands exit 0; entry persisted then cleared | ✓ PASS |
| 4 K5 emitter CLIs callable | `python -m agent.tools {transcribe_lint,mode_signals,schedule_suggest,glossary_audit} --help` | All print usage; schedule_suggest exposes `--duration` flag | ✓ PASS |
| Phase 5 vs Phase 7 transcribe artifact filename collision avoided (CR-01) | `python -c "from agent.transcribe_lint import WARNINGS_FILENAME; print(WARNINGS_FILENAME)"` | `transcribe_lint_warnings.json` (distinct from Phase 5's `transcribe_warnings.json`) | ✓ PASS |
| All Phase 07 unit tests | `python -m unittest tests.test_v11_marker tests.test_replay_v10 tests.test_queue tests.test_transcribe_lint tests.test_mode_signals tests.test_schedule_suggestion tests.test_glossary_audit tests.test_k5_emitters` | `Ran 70 tests in 0.687s — OK` | ✓ PASS |
| K5 source-grep static assertions | `python -m unittest tests.test_k5_emitters -v` | `Ran 8 tests in 0.004s — OK` | ✓ PASS |
| AV1 demoted to INFO; HEVC unchanged | `grep "codec == \"av1\"" agent/sources/_common.py` + `grep "codec == \"hevc\"" agent/sources/_common.py` | AV1 → `log.info`; HEVC → `log.warning`; message text byte-equal | ✓ PASS |
| homophone_cluster live (B1 proof of pypinyin use) | Synthetic '训练' (8x) + '迅练' (1x) → `detect_warnings` | 1 warning emitted with `evidence_source='homophone_cluster'`, `evidence_detail='pinyin=xunlian, candidate freq=8'` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| **PRE-V11-01** | 07-01 | Per-slug `.v11_features.json` opt-in marker; missing → silent v1.0 path | ✓ SATISFIED | `agent/_v11.py` ships `is_v11_enabled` / `set_v11_marker` / `get_v11_marker` + locked 8-feature `V11_FEATURES` tuple; corrupt-file silent recovery; 10 unit tests pass; live verified on `BV132wizyEEB` (no marker → False) |
| **PRE-V11-02** | 07-01 | 17-archive byte-equal replay one-shot script; phase-close gate | ✓ SATISFIED (automated) / ⚠️ MANUAL gate untaken | `scripts/replay_v10_archives.py` shipped with per-slug profile resolution; live run **33 PASS / 0 FAIL / 30 SKIP** (strict gate); manual `/summarize-video` re-run gate documented in 07-01-SUMMARY.md "Phase Close — MANUAL GATE Procedure" but `## Manual Gate Results` section not yet appended |
| **PRE-V11-03** | 07-01 | `.token_budget.json` baseline on 3 representative archives | ✓ SATISFIED | 3 files exist with valid v1 schema; total tokens = 1917 / 5252 / 1906; mode field correctly classified; deterministic chars/3.5 proxy; force-added under gitignored `output/` |
| **MISC-01** | 07-02 | AV1 codec WARNING demoted to INFO (HEVC unchanged) | ✓ SATISFIED | `agent/sources/_common.py:111-122` split codec block; AV1 → `log.info`, HEVC → `log.warning`; message text byte-equal across both branches (P-08 spirit on log strings) |
| **MISC-02** | 07-02 | `python -m agent.tools queue {add\|list\|next\|done\|skip}` + FileLock + `in_progress: <pid>` marker | ✓ SATISFIED | `agent/queue.py` shipped; 5 CLI subcommands wired; FileLock from `agent/_lock.py` reused; per-PID in_progress marker; T12 add-race + T13 next-race PASS (5-way subprocess concurrency); end-to-end smoke test PASS |
| **TOOL-A** | 07-03 | `mode_signals` emitter with NO `recommended_mode` field; raw evidence | ✓ SATISFIED | `agent/mode_signals.py:compute_signals()` returns 5 keys; explicit absence of `recommended_mode` (verified by reading source + K5 test); evidence_paragraphs capped at 5; paragraphs_hash for staleness detection |
| **TOOL-B** | 07-03 | `schedule_suggest` emitter with mandatory FPS-04 baseline + K5 source-grep test | ✓ SATISFIED | `agent/schedule_suggestion.py:compute_suggestion()` always appends `fps-04-baseline` segment with `fps=0.05` covering full duration; `--duration` W5 override flag wired in CLI; K5 source-grep test PASSES (no `summary.md` / `plan.md` / `schedule.json` literal in source) |
| **CORR-01a** | 07-03 | L1 ASR suspect-token detector: 4 mandated strategies (pypinyin homophone + 中英混杂 + 罕见字 + 高频拼写不一致) → mapped to homophone_cluster + mixed_script + hapax + frequency_variance + bonus title_token | ✓ SATISFIED | `agent/transcribe_lint.py:detect_warnings()` ships 5 strategies; Test 12 (homophone_cluster proof of work) PASSES live with synthetic '训练'/'迅练' → emits expected warning with pinyin signature evidence_detail; `pypinyin>=0.55.0` in requirements.txt; CR-01 filename collision with Phase 5 fixed (artifact = `transcribe_lint_warnings.json`) |

**Coverage:** 8/8 requirement IDs satisfied (PRE-V11-02 has automated PASS but documented manual gate outstanding).

**No orphans:** REQUIREMENTS.md Traceability table maps PRE-V11-01/02/03 + MISC-01/02 + TOOL-A/B + CORR-01a to Phase 07. All 8 IDs claimed by 3 plans (01: 3 reqs / 02: 2 reqs / 03: 3 reqs); no extra Phase-07-mapped IDs found in REQUIREMENTS.md not appearing in plans.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `CLAUDE.md` | 1118 | Documentation drift — references `transcribe_warnings.json` but actual artifact is `transcribe_lint_warnings.json` (post-CR-01) | ⚠️ Warning | Phase 8 prompts reading CLAUDE.md to find the L2 input filename will look for the wrong file. Cosmetic 1-character edit (insert `_lint` in line 1118 cell). Recorded in human_verification block. |
| `agent/queue.py` | n/a (intentional) | `from agent._lock import FileLock, LockContended` imports `LockContended` but doesn't use it | ℹ️ Info | Re-export by intent (downstream tooling may catch it); harmless. Not a stub. |

No 🛑 Blockers. No stubs flagged (glossary_audit's "missing-file → empty shape" return is intentional Phase 08 forward-compat schema, NOT a hollow implementation — it's a complete read-only auditor that just gracefully handles the no-file case).

### Human Verification Required

See `human_verification:` frontmatter block above. Two items:

1. **Manual `/summarize-video` re-run gate (PRE-V11-02 Part 2 / SC#1 Part 2)** — Phase 07's plan explicitly documents this as a phase-close requirement that Python cannot automate (slash command vs Python function). The user must, from a fresh Claude session, re-invoke `/summarize-video` on `BV132wizyEEB` and `douyin_karpathy_llm_wiki`, write to test slug dirs, and `git diff --no-index` against the committed baseline summaries. Both diffs MUST be empty. Results then logged in `07-01-SUMMARY.md` "## Manual Gate Results" section (currently absent).

2. **CLAUDE.md line 1118 doc drift fix** — One-character edit: change `transcribe_warnings.json` to `transcribe_lint_warnings.json` in the Phase 07 emitter table. The actual code (post-CR-01) writes to the new distinct filename, but the documentation table still references the old name. Code is correct; only docs are stale.

### Gaps Summary

**No code-blocking gaps.** All 5 ROADMAP success criteria + all 8 requirement IDs are satisfied at the code level:

- **D-29 byte-equal invariant** preserved on 33/33 candidate v1.0 archives (live replay)
- **Opt-in marker** correctly silent on un-marked archives; 8-feature allowlist locked
- **Token budget baselines** in place for Phase 09 2x cap reference
- **4 K5 emitters** all callable + statically asserted to never reference decision artifact filenames
- **MISC chrome** (AV1 demote + queue helper) ships with full race-test coverage

The two outstanding items are explicitly **non-code**: (a) a human-driven manual gate that Python *cannot* automate by design (Claude slash command), and (b) a one-line documentation drift in CLAUDE.md from the post-fix filename rename. Both are tracked as `human_needed` items rather than `gaps_found` because the underlying work is complete — only user actions (re-run + edit) remain.

**Critical-level confidence:** All `gsd-code-reviewer` Critical (CR-01) and Warning (WR-01..WR-06) findings from `07-REVIEW.md` were resolved per `07-REVIEW-FIX.md` (status: all_fixed, 7/7 in-scope). Verified live: post-CR-01 distinct filenames coexist; Phase 5's `_emit_repetition_warnings` and Phase 7's `cmd_transcribe_lint` no longer collide.

---

_Verified: 2026-05-03T09:00:00Z_
_Verifier: Claude (gsd-verifier)_
