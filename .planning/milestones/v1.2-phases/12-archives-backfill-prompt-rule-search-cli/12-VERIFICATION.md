---
phase: 12-archives-backfill-prompt-rule-search-cli
verified: 2026-05-03T00:00:00Z
status: human_needed
score: 7/8 must-haves verified (1 deferred UAT requires real Claude session)
overrides_applied: 0
re_verification:
  previous_status: null
  previous_score: null
  gaps_closed: []
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "E2E natural-language recommendation behavior"
    expected: |
      In a NEW Claude Code session, type one of the 7 trigger phrases such as
      `推荐学习 LLM Wiki 范式相关的视频` or `我之前看过哪些 ECS 相关的视频`.
      Claude FIRST ACTION should `Read output/.index.json` (not grep, not ask
      clarification) and return top-3 recommendations in the byte-locked
      3-line format (slug+title+共享 signal / blockquote tldr /
      [HH:MM:SS] chapter entries). All recommended slugs must exist in the
      aggregator (no hallucinated slugs). For LLM-Wiki query, expect at
      minimum douyin_karpathy_llm_wiki + douyin_ai_kb + douyin_trae_ai
      to surface.
    why_human: |
      Recommendation behavior is prompt-driven on a real Claude Code
      session — cannot be unit-tested. Same pattern as v1.1 P-09 token
      budget gate and Phase 11 KB-02 E2E hook test. CONTEXT D-09.4
      explicitly classifies this as deferred manual UAT (not a
      phase-blocking gate) — `output/.index.json` ground truth confirms
      the data exists; only the prompt-following behavior remains to be
      observed in vivo.
---

# Phase 12: 17-archives-backfill-prompt-rule-search-cli Verification Report

**Phase Goal:** v1.2 收尾——把 Phase 11 的 generator 复用到 17 v1.0/v1.1 archives 上一次性 backfill 写 index.json，让 Claude 一开会话 Read 顶层 `.index.json` 就能看全 23 条；CLAUDE.md 加自然语言推荐 prompt rule（D-09 锁，不加 slash command，mirror v1.1 anti-hallucination 字面规则风格）；顺手 ship `index search/list` 兜底 CLI；末尾再跑一次 D-29 replay 确认 33/0/30。
**Verified:** 2026-05-03
**Status:** human_needed (7 of 8 must-haves automated-verified; 1 deferred manual UAT documented per CONTEXT D-09.4)
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria — 5)

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|---|---|---|
| 1 | 17+ v1.0/v1.1 archives 全部有 index.json + 顶层 .index.json 含 17+ 条 (KB-12 + KB-13) | VERIFIED | `output/.index.json` parses to dict with 33 entries (>>17). 33 per-slug `output/<slug>/index.json` files exist; all sample-validated against 8-field schema (`slug`/`title`/`duration_s`/`mode`/`topics`/`keywords`/`tldr_oneliner`/`chapters`). Idempotent re-scan returns `to_backfill=0, skipped_existing=33, failed=0`. Schema-valid sample douyin_karpathy_llm_wiki: mode=interview-distillation, 3 topics, 7 chapters, 7 keywords. |
| 2 | D-29 byte-equal 33/0/30 仍 PASS (post-backfill) | VERIFIED | `python scripts/replay_v10_archives.py` → `Summary: 33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)` + `AUTOMATED GATE PASSED`. The 30 SKIP are non-archive dirs lacking summary.md (in-progress / partial); the 33 PASS confirms 4 D-29 core artifacts (summary.md/segs.json/paragraphs.json/meta.json) are byte-equal across all complete archives after Phase 12. |
| 3 | CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 byte-locked (KB-14 + KB-15) | VERIFIED | H2 inserted at line 1625 between `## v1.1 校对自动化 (Phase 09)` (line 1415) and `## /summarize-video 完整工作流` (line 1689). All 5 sub-blocks present: 触发 phrase 锁 / FIRST ACTION / 推荐回复格式锁 / Byte-equal example / Anti-hallucination FORBIDDEN list (grep -c == 5). All 7 byte-equal trigger phrases present (`'推荐'`, `'相关'`, `'我之前看过'`, `'学过'`, `'找一下我'`, `'哪些视频'`, `'类似查询意图'` each grep ≥1). 15 `FORBIDDEN` occurrences (≥6 required). 3 `Read output/.index.json` references (≥2 required). Byte-equal example demonstrates douyin_karpathy_llm_wiki recommendation in 3-line locked format. |
| 4 | E2E 自然语言推荐行为可观测 (manual UAT) | NEEDS HUMAN | Ground truth verified: `output/.index.json` contains the data needed for the recommendation flow — `index search "Karpathy"` returns 2 hits (douyin_karpathy_llm_wiki + douyin_ai_kb); `index list --topic LLM-Wiki` returns 3 entries (douyin_ai_kb, douyin_karpathy_llm_wiki, douyin_trae_ai); CLAUDE.md prompt rule is byte-locked. Actual E2E recommendation behavior in a real Claude session cannot be unit-tested — deferred manual UAT per CONTEXT D-09.4 (same pattern as v1.1 P-09 + Phase 11 KB-02). See human_verification[0]. |
| 5 | `index search/list` 兜底 CLI 工作 (KB-MISC-01) | VERIFIED | `python -m agent.tools index --help` displays `{write,rebuild,backfill,search,list}` (5 sub-subcommands). `index search "Karpathy" --json` returns 2-match JSON; `index list --topic "LLM-Wiki" --json` returns 3-entry JSON; both READ-ONLY (K5 statically asserted by `test_K5_cmd_index_search_and_list_read_only` — 23 K5 tests pass). |

**Score:** 4/5 ROADMAP SCs VERIFIED; 1/5 NEEDS HUMAN (deferred UAT).

### PLAN must_haves Truths (Plans 12-01 + 12-02 — combined 12)

All 12 plan-frontmatter `must_haves.truths` map to the 5 ROADMAP SCs above and are verified by the same automated checks. The deferred manual UAT (truth #4) corresponds to ROADMAP SC#4.

---

### Required Artifacts (Phase 12 produced/modified)

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `agent/index.py` | +3 read-only public functions: `scan_archives_for_backfill` / `search_index` / `list_index` | VERIFIED | `def scan_archives_for_backfill` at line 480; `def search_index` at line 571; `def list_index` at line 643. K5 grep: zero D-29 5 core literals (summary.md / plan.md / paragraphs.json / segs.json / meta.json) in module source. |
| `agent/tools.py` | +3 CLI handlers: `cmd_index_backfill` / `cmd_index_search` / `cmd_index_list` + 3 nested subparsers + 3 dispatch entries | VERIFIED | `def cmd_index_backfill` at line 1919; `def cmd_index_search` at line 1964; `def cmd_index_list` at line 1987. Subparsers `ibackfill`/`isearch`/`ilist` registered at lines 2321/2338/2348. Dispatch dict entries: `"backfill": cmd_index_backfill` (2418), `"search": cmd_index_search` (2419), `"list": cmd_index_list` (2420). All 3 handlers import the corresponding module function: lines 1930/1969/1991. |
| `tests/test_index.py` | +4 test classes: `TestScanArchivesForBackfill` / `TestSearchIndex` / `TestListIndex` / `TestCLIBackfillSearchListEdges` (~25 new tests) | VERIFIED | `TestScanArchivesForBackfill` at line 574; `TestSearchIndex` at line 680; `TestListIndex` at line 777; `TestCLIBackfillSearchListEdges` at line 850. `python -m unittest tests.test_index.TestScanArchivesForBackfill TestSearchIndex TestListIndex TestCLIBackfillSearchListEdges` → 25 tests OK. |
| `tests/test_k5_emitters.py` | +3 K5 boundary tests: `test_K5_module_index_phase12_extensions_no_d29_writes` / `test_K5_cmd_index_backfill_no_d29_writes` / `test_K5_cmd_index_search_and_list_read_only` (count 20→23) | VERIFIED | All 3 tests exist (lines 365/395/418). `python -m unittest tests.test_k5_emitters.TestK5BoundaryPhase07` → 23 tests OK. K5 count grew from 20 (v1.0+v1.1+Phase 10+Phase 11 baseline) to 23 (Phase 12 D-07 target). |
| `output/.index.json` | Top-level aggregator with ≥17 entries lex-ordered by slug | VERIFIED | File exists (44541 bytes). Parses to dict with 33 entries (>>17 SC threshold). First 5 keys lex-ordered: BV11JQBByE13, BV132wizyEEB, BV15S9FBtEFm, BV17WQuBJEzZ, BV1C9QCBdE1U. Last 5: douyin_ai_kb, douyin_claude_code_hooks, douyin_karpathy_llm_wiki, douyin_trae_ai, douyin_zidan_bojirouxunlian. |
| `output/<slug>/index.json` (×33) | Per-slug 8-field index sidecars | VERIFIED | 33 per-slug index.json files exist (`ls output/*/index.json` → 33 hits). Sample BV132wizyEEB: 8 fields valid, mode=replicate-guide, 3 topics, duration=74.048s, 6 chapters with timestamps. Sample douyin_karpathy_llm_wiki: 8 fields valid, mode=interview-distillation, 3 topics (LLM-Wiki/LLM-Concepts/RAG), 7 chapters. |
| `CLAUDE.md` | +`## v1.2 知识库自然语言推荐入口` H2 (~64 lines) between Phase 09 v1.1 校对自动化 and `/summarize-video 完整工作流` | VERIFIED | H2 at line 1625 (between 1415 and 1689). All 5 sub-blocks (`### 触发 phrase 锁` / `### FIRST ACTION` / `### 推荐回复格式锁` / `### Byte-equal example` / `### Anti-hallucination FORBIDDEN list`) present. 7 trigger phrases byte-locked. 6+ FORBIDDEN entries byte-locked (15 occurrences across CLAUDE.md). |
| `output/_topics.md` | Approved Taxonomy unchanged; zero pending topics appended (per Phase 10 ship completeness) | VERIFIED | 845 bytes (Phase 10 baseline). 0 pending topics — all 33 archives' topic vectors fit existing 24-leaf approved taxonomy. Validates Phase 10 taxonomy completeness. |
| `scripts/_p12_compose.py` | Historical record of per-slug payload composition decisions (committed to git) | VERIFIED | 37636 bytes; committed at c9f9dfc; 73 lines containing import/json/topics/mode references. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `agent/tools.py:cmd_index_backfill` | `agent/index.py:scan_archives_for_backfill` | import + call | WIRED | Line 1930: `from agent.index import scan_archives_for_backfill`. Called inside handler. |
| `agent/tools.py:cmd_index_search` | `agent/index.py:search_index` | import + call | WIRED | Line 1969: `from agent.index import search_index`. |
| `agent/tools.py:cmd_index_list` | `agent/index.py:list_index` | import + call | WIRED | Line 1991: `from agent.index import list_index`. |
| `agent/tools.py:main()` | `cmds["index"]` nested subparser | `isub.add_parser` | WIRED | Lines 2321 (backfill), 2338 (search), 2348 (list) — 3 nested subparsers properly registered. |
| `agent/tools.py:main()` | `index_cmds` dispatch dict | key registration | WIRED | Lines 2418/2419/2420: `"backfill": cmd_index_backfill`, `"search": cmd_index_search`, `"list": cmd_index_list`. |
| `CLAUDE.md ## v1.2 知识库自然语言推荐入口` | `output/.index.json` | `Read output/.index.json` (FIRST ACTION) | WIRED | 3 grep hits in CLAUDE.md for `Read output/\.index\.json` — FIRST ACTION + FORBIDDEN list reference + missing-file fallback. |
| `output/.index.json` | `output/<slug>/index.json` (×33) | `rebuild_aggregator` (Phase 11 generator side-effect) | WIRED | Aggregator dict-of-dicts contains 33 keys, each value matching the corresponding per-slug index.json on disk. Idempotent re-scan confirms tight sync. |
| Plan 12-02 backfill loop | `agent/tools.py:cmd_index_write` | `python -m agent.tools index write --slug X --from-stdin --force` | WIRED | scripts/_p12_compose.py records 33 invocations; each archive's index.json matches the composed payload. |
| `CLAUDE.md FORBIDDEN list` | v1.1 5th format-spec invariant | literal byte-locked rule list | WIRED | FORBIDDEN list mentions "v1.1 5th format-spec invariant 同等严重度" explicitly (line 1678). Style mirrors v1.1 anti-hallucination pattern. |

All 9 key links WIRED.

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|---|---|---|---|---|
| `cmd_index_backfill` | `result` (to-do dict) | `scan_archives_for_backfill(out_dir, force=...)` reads `output/<slug>/summa+ry.md` files | Yes (33 real archives detected; idempotent re-scan returns 33 skipped_existing) | FLOWING |
| `cmd_index_search` | `matches` (list) | `search_index(query, output_dir=...)` reads `output/.index.json` aggregator | Yes ("Karpathy" → 2 real matches with non-empty matched_fields[]) | FLOWING |
| `cmd_index_list` | `entries` (filtered list) | `list_index(topic=..., mode=..., output_dir=...)` reads aggregator | Yes ("LLM-Wiki" → 3 real entries douyin_*) | FLOWING |
| `output/.index.json` | aggregator dict | Phase 11 `rebuild_aggregator` scans `output/*/index.json` | Yes (33 entries match 33 per-slug sidecars on disk) | FLOWING |

All artifacts that render dynamic data have verified data flow.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| `index --help` lists 5 sub-subcommands | `python -m agent.tools index --help` | stdout contains `{write,rebuild,backfill,search,list}` | PASS |
| `index backfill` returns idempotent JSON after backfill | `python -m agent.tools index backfill --all --output-dir output --json` | `action=scanned total=33 to_backfill=0 skipped=33 failed=0` | PASS |
| `index search "Karpathy"` returns ≥1 match | `python -m agent.tools index search "Karpathy" --output-dir output --json` | 2 matches: douyin_ai_kb + douyin_karpathy_llm_wiki | PASS |
| `index list --topic LLM-Wiki` returns ≥1 entry | `python -m agent.tools index list --topic "LLM-Wiki" --output-dir output --json` | 3 entries (douyin_ai_kb, douyin_karpathy_llm_wiki, douyin_trae_ai) | PASS |
| Aggregator schema validates | `python -c "import json; d=json.load(open('output/.index.json'))"` | 33 entries, each 8-field valid | PASS |
| Sample per-slug schema validates | `python -c "...douyin_karpathy_llm_wiki/index.json..."` | All 8 fields present, mode=interview-distillation, chapters=7 | PASS |
| K5 source-grep zero D-29 literals | inspect.getsource on cmd_index_backfill/search/list + agent/index.py | All 4 sources contain zero of {summary.md, plan.md, paragraphs.json, segs.json, meta.json} | PASS |
| K5 boundary test count 20 → 23 | `python -m unittest tests.test_k5_emitters.TestK5BoundaryPhase07` | `Ran 23 tests in 0.014s. OK` | PASS |
| D-29 byte-equal close gate | `python scripts/replay_v10_archives.py` | `Summary: 33 PASS / 0 FAIL / 30 SKIP. AUTOMATED GATE PASSED.` | PASS |
| Full test suite (no regressions) | `python -m unittest discover tests` | `Ran 297 tests in 4.407s. OK (skipped=2)` | PASS |

10/10 spot-checks PASS.

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| KB-12 | 12-01 + 12-02 | 17 v1.0/v1.1 archives 一次性 backfill — `index backfill --all` 写 index.json (idempotent + `--force` overwrite) | SATISFIED | `index backfill --all` CLI shipped (Plan 12-01); 33 archives backfilled (Plan 12-02 — exceeds 17 SC threshold). Idempotent: re-scan returns to_backfill=[]. `--force` flag tested in TestScanArchivesForBackfill.test_skip_existing_index_unless_force + TestCLIBackfillSearchListEdges.test_backfill_force_overrides_skip_existing. |
| KB-13 | 12-01 + 12-02 | backfill error tolerance — single-slug failures isolated, exit code non-zero on failure | SATISFIED | `failed[]` list returned in scan dict (verified by TestScanArchivesForBackfill.test_corrupt_summary_lists_in_failed_not_to_backfill); exit code non-zero on failure (verified by TestCLIBackfillSearchListEdges.test_backfill_failure_returns_nonzero). 0 failed slugs in actual 33-archive backfill (all archives healthy). 6-queue future videos handled by Phase 11 Phase 7.6 hook (out-of-scope per CONTEXT). |
| KB-14 | 12-02 | CLAUDE.md prompt rule — byte-locked trigger phrases + FIRST ACTION + recommendation format lock | SATISFIED | H2 `## v1.2 知识库自然语言推荐入口` at line 1625; 7 trigger phrases byte-equal-locked; FIRST ACTION = `Read output/.index.json` with missing-file fallback; recommendation format lock specifies 3-line strict structure (slug+title / blockquote tldr / chapter entries). |
| KB-15 | 12-02 | Anti-hallucination FORBIDDEN list — mirror v1.1 5th format-spec invariant style | SATISFIED | 6 explicit FORBIDDEN entries in `### Anti-hallucination FORBIDDEN list` sub-block: (a) FORBIDDEN 推荐不存在的 slug, (b) FORBIDDEN 编造视频内容, (c) FORBIDDEN 修改 D-29 4 核心文件, (d) FORBIDDEN `<thinking>` reasoning, (e) FORBIDDEN > N=5 推荐, (f) FORBIDDEN 跳过 FIRST ACTION. Style explicitly references "v1.1 5th format-spec invariant 同等严重度". |
| KB-MISC-01 | 12-01 | `index search/list` 兜底 CLI — read-only, K5 boundary asserted | SATISFIED | `cmd_index_search` + `cmd_index_list` both shipped + tested + K5-asserted (test_K5_cmd_index_search_and_list_read_only verifies zero D-29 literals + zero write API patterns in both handlers). Real-world smoke: search "Karpathy" → 2 hits; list --topic LLM-Wiki → 3 entries. |

**Coverage:** 5/5 Phase 12 requirements SATISFIED. No orphaned requirements (REQUIREMENTS.md Traceability table maps Phase 12 to exactly KB-12/13/14/15/MISC-01).

---

### Anti-Patterns Found

No blockers detected. Spot-checks for stub patterns:

| File | Line | Pattern | Severity | Impact |
|---|---|---|---|---|
| (none) | — | — | — | All Phase 12 code has real implementations and pass behavior tests; no `return null` / `TODO` / placeholder patterns introduced |

The .planning/STATE.md "Current focus: Phase 11" / "Status: Executing Phase 11" line is stale post-Phase-12 close — but this is informational state metadata, not Phase 12's own deliverable, and ROADMAP.md Phase 12 row correctly shows `Complete | 2026-05-03`.

---

### Human Verification Required

#### 1. E2E natural-language recommendation behavior (deferred manual UAT)

**Test:** In a NEW Claude Code session, type one of the 7 trigger phrases such as `推荐学习 LLM Wiki 范式相关的视频`, `我之前看过哪些 ECS 相关的视频`, `学习 Godot 的话推荐什么` (or any sentence containing one of the 7 byte-equal trigger phrases: `'推荐'`, `'相关'`, `'我之前看过'`, `'学过'`, `'找一下我'`, `'哪些视频'`, `'类似查询意图'`).

**Expected:**
1. Claude FIRST ACTION reads `output/.index.json` (no grep, no clarification ask)
2. Returns top-N (default N=3) matches in the byte-locked 3-line format:
   - **slug**: title — 共享 \<匹配信号\>
   - > tldr_oneliner (blockquote)
   - 1-3 chapter entries `[HH:MM:SS] <chapter title>`
3. All recommended slugs exist in `output/.index.json` (no hallucinated slugs)
4. For LLM-Wiki query: at minimum `douyin_karpathy_llm_wiki`, `douyin_ai_kb`, `douyin_trae_ai` should surface
5. No `<thinking>` reasoning block in the reply
6. ≤5 recommendations unless user explicitly asks "list everything"

**Why human:** Recommendation behavior is prompt-driven on a real Claude Code session — cannot be unit-tested. The data ground truth is verifiable (and verified above): `index search "Karpathy"` returns 2 hits; `index list --topic LLM-Wiki` returns 3 entries; CLAUDE.md prompt rule is byte-locked. But the prompt-following behavior in vivo can only be observed during a real session. CONTEXT D-09.4 explicitly classifies this as **NOT a phase-blocking gate** — same pattern as v1.1 P-09 token budget gate and Phase 11 KB-02 E2E hook test.

---

### Gaps Summary

No gaps. All 5 ROADMAP success criteria are satisfied at the automated/observable level. The single `human_needed` item is the deferred E2E behavioral UAT (CONTEXT D-09.4 — same deferred-manual-UAT pattern as v1.1 P-09 + Phase 11 KB-02), which by explicit Phase 12 contract is documented as a non-blocking gate. Phase 12 is shippable; the manual UAT is the milestone-close human-touch point.

**Acceptance gate per 12-02-SUMMARY.md:** all 11 listed criteria PASSED. K5 boundary count 20 → 23. Test count 269 → 297 (+28). D-29 replay 33/0/30 PASSED. Zero new pip dependencies (¥0 hard constraint preserved). CLAUDE.md byte-locked at 5 sub-blocks + 7 trigger phrases + 15 FORBIDDEN occurrences.

---

*Verified: 2026-05-03*
*Verifier: Claude (gsd-verifier, Opus 4.7 1M context)*
