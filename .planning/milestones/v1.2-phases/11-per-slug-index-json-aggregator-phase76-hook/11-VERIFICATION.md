---
phase: 11-per-slug-index-json-aggregator-phase76-hook
verified: 2026-05-04T00:00:00Z
status: human_needed
score: 11/11 must-haves verified (1 manual UAT deferred by design)
overrides_applied: 0
human_verification:
  - test: "KB-02 E2E — Claude follows the Phase 7.6 hook on a real new video"
    expected: "On a new `/summarize-video` invocation (post-Phase-7.5), Claude reads the 5 files (summary.md / meta.json / plan.md / _glossary.md / _topics.md), composes 8-field JSON, pipes to `python -m agent.tools index write --slug <slug> --from-stdin`, and the CLI returns `{action: written, ...}`; `output/<slug>/index.json` exists schema-valid; `output/.index.json` contains the slug as a key. Re-trigger Phase 7.6 → CLI returns `action: skipped` (byte-equal idempotent). If a `pending: <name>` topic was proposed, `output/_topics.md` `## Pending` segment grew by an H3 entry with 3 sub-fields."
    why_human: "Cannot unit-test 'Claude in a real session follows a prompt rule'; this is a behavioral check requiring a live Claude Code session on a real new video. Documented as deferred by design (mirror of v1.1 Phase 09 P-09 token-budget gate) per RESEARCH A6 + Q-F. Phase ship is NOT blocked on this UAT — recommended for the user's next video processing session."
---

# Phase 11: per-slug index.json + 顶层聚合 + Phase 7.6 hook Verification Report

**Phase Goal:** 落地 v1.2 知识库的"中颗粒索引层"——给每个 `output/<slug>/` 写 `index.json`（schema 锁死 8 字段），keywords 优先复用 `_glossary.md` H2 anchors 避免分裂，顶层 `output/.index.json` atomic rebuild 让 Claude 一次 Read 拿全 23+ 条概览。`/summarize-video` Phase 7.6 hook 让新视频自动同步生成；老归档 backfill 复用同一 generator（Phase 12 用）保证一致性。D-29 byte-equal 33/0/30 仍 PASS（index.json 是新 sidecar 不在 replay 比对范围）。

**Verified:** 2026-05-04
**Status:** human_needed (all automated checks pass; KB-02 E2E behavioral UAT deferred by design)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap SC + Plan must_haves merged)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | per-slug `output/<slug>/index.json` 8-field schema locked, all 8 fields filled | VERIFIED | `agent/index.py:60-62` REQUIRED_FIELDS = (slug, title, duration_s, mode, topics, keywords, tldr_oneliner, chapters); CHAPTER_FIELDS = (title, start, excerpt); validate_per_slug_index enforces all 8 + chapter shape |
| 2 | `/summarize-video` Phase 7.6 hook auto-generates index.json + immediately rebuilds top-level (documentation level) | VERIFIED | CLAUDE.md L1772 `### Phase 7.6: 知识库索引（v1.2 ship 后默认启用）` block (56 lines, L1772–1827) inserted between Phase 7.5 (L1747) and Phase 8 (L1828). Block prescribes 5 numbered steps + 3-condition trigger + Read 5 files + pipe to `python -m agent.tools index write --slug <slug> --from-stdin` + CLI auto-validates + atomic-writes per-slug + immediately rebuilds aggregator |
| 3 | Top-level `output/.index.json` auto-syncs + atomic rebuild + stale detection | VERIFIED | `agent/index.py:rebuild_aggregator` + `_rebuild_aggregator_inner` (L271–325) — lexicographic-ordered dict + atomic_write via tempfile+fsync+os.replace + stale_detected[] (per-slug mtime > aggregator mtime) + skip-on-malformed quarantine via slugs_skipped[]; `python -m agent.tools index rebuild` exits 0 with stdout JSON `{action: rebuilt, slugs_included, slugs_skipped, stale_detected, _index_path}` |
| 4 | keywords prefer reuse `_glossary.md` H2 anchors (byte-equal canonical) | VERIFIED | `agent/index.py:glossary_h2_anchors` (L248–268) returns canonical H2 anchor strings byte-equal; `_GLOSSARY_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)` mirrors `agent/glossary.py:_H2_RE`; vacuous-empty case returns `[]` when file missing (Pitfall 3); CLAUDE.md hook step 2 explicitly instructs "优先复用 `_glossary.md` H2 anchors 的 byte-equal canonical 形式" with concrete example `LoRA (Low-Rank Adaptation)` |
| 5 | D-29 byte-equal 33/0/30 PASS (index.json is new sidecar outside replay scope) | VERIFIED | `python scripts/replay_v10_archives.py` on main → `Summary: 33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)`. AUTOMATED GATE PASSED. 4 core artifacts (summary.md / segs.json / paragraphs.json / meta.json) byte-equal preserved |
| 6 | `agent/index.py` exposes 5 public functions + IndexValidationError importable without raising | VERIFIED | `python -c "import agent.index"` succeeds; exports include validate_per_slug_index, read_per_slug_index, write_per_slug_index, rebuild_aggregator, read_aggregator, glossary_h2_anchors, IndexValidationError, INDEX_FILENAME, AGGREGATOR_FILENAME, LOCK_FILENAME, VALID_MODES, REQUIRED_FIELDS, CHAPTER_FIELDS |
| 7 | CLI `index write` consumes 8-field JSON and emits locked stdout JSON | VERIFIED | `python -m agent.tools index write --help` lists `--slug --from-stdin --output-dir --force --timeout --json`; `cmd_index_write` (agent/tools.py:1779–1872) emits stdout JSON `{"action": "written"|"skipped", "slug", "_index_path", "_aggregator_path", "_topics_pending_appended"}` byte-equal to D-05.5 contract; slug-prefix log routed to stderr (PARA-04 fix) |
| 8 | CLI `index rebuild` scans, atomic-writes, emits locked stdout JSON | VERIFIED | `python -m agent.tools index rebuild --help` works; `cmd_index_rebuild` (agent/tools.py:1875–1916) emits `{"action": "rebuilt", "slugs_included", "slugs_skipped", "stale_detected", "_index_path"}` byte-equal to D-04.4 contract; tested live → `slugs_included: 0, slugs_skipped: [], stale_detected: []` (expected — Phase 11 ships only CLI; Phase 12 backfill writes per-slug index.json) |
| 9 | validate_per_slug_index rejects bad inputs + accepts all 4 modes | VERIFIED | `agent/index.py:118–201` validates type + presence + mode (4 valid: replicate-guide / concept-explanation / extension-applications / interview-distillation) + topic whitelist with `pending: ` prefix bypass + chapter shape + bool rejected for numeric (defensive); 42 tests in tests/test_index.py exercise all paths |
| 10 | Top-level keys are sorted lexicographic by slug name (Q-E lock) | VERIFIED | `agent/index.py:_rebuild_aggregator_inner` L318 `ordered = {k: aggregated[k] for k in sorted(aggregated.keys())}` — guaranteed reproducibility |
| 11 | Per-slug + aggregator writes inside single FileLock window (Pattern 2 invariant) | VERIFIED | `agent/index.py:write_per_slug_index` L448 `with FileLock(lock_path, timeout=timeout):` covers both atomic per-slug write (L465) AND `_rebuild_aggregator_inner(out_dir)` (L467) — readers always see consistent state |
| 12 | Three new K5 source-grep tests pass (count 17 → 20) | VERIFIED | `python -m unittest tests.test_k5_emitters -v` → 20 tests OK; new tests at lines 301/320/336: test_K5_module_index_no_summary_writes / test_K5_handler_cmd_index_write / test_K5_cmd_index_rebuild_read_only_per_slug all pass |
| 13 | cmd_index_rebuild source does NOT contain `write_per_slug_index` import (rebuild is read-only on per-slug) | VERIFIED | `agent/tools.py:cmd_index_rebuild` (L1875–1916) imports only `rebuild_aggregator` + `AGGREGATOR_FILENAME`; the K5 test test_K5_cmd_index_rebuild_read_only_per_slug asserts both no D-29 literals AND `assertNotIn("write_per_slug_index", src)` — passes |
| 14 | Phase 7.6 hook prescribes 5 D-29 core artifacts + plan.md as READ-ONLY | VERIFIED | CLAUDE.md L1781 explicitly: "**这 5 个文件全部 READ-ONLY**——D-29 invariant 锁死 4 核心文件 (summary.md / segs.json / paragraphs.json / meta.json) byte-equal 不破；不要用 Edit / Write 工具改动它们..."; CLAUDE.md L1826 K5 boundary reminder pairs prompt-level invariant with Plan 11-01 source-grep tests |
| 15 | Phase 7.6 hook prescribes glossary H2 anchor reuse + plan.md/glossary missing fallbacks | VERIFIED | L1782 plan.md missing → `mode = "replicate-guide"` per CLAUDE.md fallback; L1783 _glossary.md missing → `keywords` candidate set vacuously empty (Pitfall 3); L1791 keywords reuse instruction with byte-equal canonical example |
| 16 | Phase 7.6 hook prescribes chapters[].start cross-reference to paragraphs.json | VERIFIED | L1799 explicitly: "关键：cross-reference `paragraphs.json` 拿真实浮点 start——summary.md 的 `[HH:MM]` 是秒级 round (精度损失)，paragraphs.json 的 paragraphs[i].start 是浮点。...不要单纯 regex `summary.md`，而是把每个 H2 章节标题语义匹配到 paragraphs.json 中最接近的 paragraph，用其 `start` 浮点值。" |
| 17 | KB-02 E2E behavioral UAT achievable (single-slug smoke) | NEEDS_HUMAN | Documented at SUMMARY level; cannot test "Claude follows the prompt rule" via unit test. Deferred per RESEARCH A6 + Q-F (mirror v1.1 P-09 pattern). Phase shippable without this UAT being run. |

**Score:** 16/17 truths VERIFIED + 1 deferred-by-design human UAT (KB-02 E2E)

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `agent/index.py` | 5 public functions + IndexValidationError + module constants | VERIFIED | 475 lines; exports validate_per_slug_index / read_per_slug_index / write_per_slug_index / rebuild_aggregator / read_aggregator / glossary_h2_anchors / IndexValidationError + INDEX_FILENAME/AGGREGATOR_FILENAME/LOCK_FILENAME/VALID_MODES/REQUIRED_FIELDS/CHAPTER_FIELDS constants |
| `agent/tools.py` | +cmd_index_write + cmd_index_rebuild + cmds["index"] subparser + index_cmds dispatch | VERIFIED | cmd_index_write @ L1779; cmd_index_rebuild @ L1875; nested `index` subparser @ L2200–2228; index_cmds dispatch dict @ L2284; dispatch elif @ L2294 |
| `tests/test_index.py` | 5+ test classes / 20+ behavior tests | VERIFIED | 575 lines; 6 test classes (TestValidate / TestReadWrite / TestRebuild / TestGlossaryH2 / TestAtomic / TestCLIWriteEdges); 42 tests run, all pass |
| `tests/_tmp_index/.gitkeep` | ASCII-safe per-test tmpdir root | VERIFIED | empty file present (Phase 10 D-19 lesson re Windows zh-CN GBK code-page) |
| `tests/test_k5_emitters.py` | +3 K5 boundary tests inside TestK5BoundaryPhase07 (17 → 20) | VERIFIED | new tests at L301 (test_K5_module_index_no_summary_writes) / L320 (test_K5_handler_cmd_index_write) / L336 (test_K5_cmd_index_rebuild_read_only_per_slug); all 20 K5 tests pass |
| `CLAUDE.md` | +~50-70 line Phase 7.6 hook block between Phase 7.5 (L1747) and Phase 8 (L1828) | VERIFIED | 56 lines added at L1772-L1827 ; Phase 7.5 intact at L1747; Phase 8 intact at L1828 |
| `.planning/phases/.../11-01-SUMMARY.md` | Plan 01 completion record | VERIFIED | exists; documents agent/index.py + cmd_index_* + 3 K5 tests + 1 auto-fixed deviation (Rule 1 stderr routing fix) |
| `.planning/phases/.../11-02-SUMMARY.md` | Plan 02 completion record + D-29 replay result + KB-02 manual UAT note | VERIFIED | exists; records `1 PASS / 0 FAIL / 3 SKIP` from worktree replay + KB-02 E2E manual UAT deferred + Phase 11 SHIPPABLE; main-branch replay (post-merge) shows canonical 33/0/30 |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `agent/index.py:write_per_slug_index` | `agent.topics.read_topics` | import + flatten Approved tree → set | WIRED | L398 `from agent.topics import read_topics`; L399–400 read + flatten; L402–405 validate w/ approved set |
| `agent/index.py:write_per_slug_index` | `agent.topics.append_pending` | called for each `pending: <name>` topic | WIRED | L420 `from agent.topics import append_pending`; L422–430 invocation per pending topic |
| `agent/index.py:write_per_slug_index` | `agent._lock.FileLock(output/.index.lock)` | single context window covers per-slug + rebuild | WIRED | L44 import; L448 `with FileLock(lock_path, timeout=timeout):` covers L465 atomic write + L467 rebuild call |
| `agent/tools.py:cmds dispatch` | `index_cmds[args.index_cmd]` | elif args.command == "index" | WIRED | L2284–2287 dispatch dict; L2294–2295 elif clause |
| `CLAUDE.md /summarize-video` workflow | `agent/index.py → cmd_index_write → write_per_slug_index → rebuild_aggregator` | Phase 7.6 hook prescribes `python -m agent.tools index write --slug <slug> --from-stdin <<EOF` | WIRED | CLAUDE.md L1804 verbatim invocation matches L2207–2220 CLI surface byte-equal (--slug + --from-stdin + --output-dir + --force + --timeout + --json) |
| CLAUDE.md Phase 7.6 hook | `output/_topics.md` (whitelist) + `output/_glossary.md` (H2 anchor reuse) + `paragraphs.json` (chapters[].start cross-ref) | Hook step 1 prescribes Read 5 files; CLI internally calls agent.topics.read_topics + agent.index.glossary_h2_anchors | WIRED | L1781 list; L1790 _topics.md whitelist + pending escape hatch; L1791 _glossary.md H2 reuse with byte-equal canonical example; L1799 paragraphs.json cross-ref instruction |
| Phase 11 close gate | `scripts/replay_v10_archives.py` | Per D-07.1: must run before phase shippable; expected `33 PASS / 0 FAIL` | WIRED | Live run on main: `Summary: 33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)` AUTOMATED GATE PASSED |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| `agent.index` module imports without error | `python -c "import agent.index"` | success | PASS |
| CLI `index --help` lists 2 subcommands | `python -m agent.tools index --help` | usage shows `{write,rebuild}` + helps | PASS |
| CLI `index write --help` exposes --slug / --from-stdin / --force | `python -m agent.tools index write --help` | all 6 args present including `--force` | PASS |
| CLI `index rebuild --help` works | `python -m agent.tools index rebuild --help` | 3 args present | PASS |
| Live `index rebuild` on real `output/` writes aggregator | `python -m agent.tools index rebuild --json` | `{"action": "rebuilt", "slugs_included": 0, ...}`; `output/.index.json` created with `{}` content (no per-slug index.json yet — Phase 12 will backfill) | PASS |
| K5 boundary tests (20 total) green | `python -m unittest tests.test_k5_emitters` | Ran 20 tests in 0.012s — OK | PASS |
| Index module behavior tests (42) green | `python -m unittest tests.test_index` | Ran 42 tests in 1.256s — OK | PASS |
| Full test suite green (no regression) | `python -m unittest discover tests` | Ran 269 tests in 3.754s — OK (skipped=2) | PASS |
| D-29 replay gate on main branch | `python scripts/replay_v10_archives.py` | `Summary: 33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)` AUTOMATED GATE PASSED | PASS |
| Zero new pip deps | `git diff be95000^ HEAD -- requirements.txt requirements-optional.txt` | empty diff (zero changes) | PASS |
| Phase 7.6 hook content checks | grep on CLAUDE.md | `### Phase 7.6: 知识库索引` x1, `### Phase 7.5: 校对自动化` x1, `### Phase 8: 收尾` x1, `python -m agent.tools index write --slug` x1 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| KB-01 | 11-01-PLAN | per-slug 8-field schema lock | SATISFIED | REQUIRED_FIELDS / CHAPTER_FIELDS constants + validate_per_slug_index + 7+ unit tests in test_index.py:TestValidate |
| KB-02 | 11-02-PLAN | index.json auto-generated in `/summarize-video` Phase 7.6 + reused for backfill | SATISFIED (doc + CLI), NEEDS HUMAN (E2E behavioral UAT) | CLAUDE.md L1772–1827 Phase 7.6 hook block (5-step workflow); `python -m agent.tools index write --slug X --from-stdin` CLI works; `agent.index.write_per_slug_index` is the canonical generator entry point Phase 12 backfill will reuse |
| KB-03 | 11-01-PLAN | keywords reuse `_glossary.md` H2 anchors | SATISFIED | `agent/index.py:glossary_h2_anchors` returns byte-equal canonical strings; vacuous-empty fallback returns `[]`; CLAUDE.md hook step 2 explicitly mandates byte-equal canonical reuse |
| KB-04 | 11-01-PLAN | top-level aggregator atomic rebuild | SATISFIED | `_rebuild_aggregator_inner` w/ atomic_write + lexicographic ordering + stale detection + flat dict (no backlinks per D-07); FileLock single-window covers per-slug + rebuild |
| KB-05 | 11-01-PLAN | manual `index rebuild` CLI | SATISFIED | `cmd_index_rebuild` (agent/tools.py:1875) + 3 edge tests in test_index.py:TestCLIWriteEdges; stale detection + skip-on-malformed + exit code 1 if zero valid |
| KB-06 | 11-02-PLAN | D-29 byte-equal 33/0/30 still PASS | SATISFIED | `Summary: 33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)` from `scripts/replay_v10_archives.py` on main; index.json is new sidecar outside replay scope per D-03.6 |

**Coverage:** 6/6 KB-XX requirements satisfied at the documentation/CLI/test level; KB-02 has a deferred-by-design E2E behavioral UAT.

No orphaned requirements (all KB-01..KB-06 mapped to either Plan 11-01 or Plan 11-02).

### CONTEXT D-XX Decisions Verified

| D-XX | Decision | Status | Evidence |
|---|---|---|---|
| D-01 (per-slug schema) | 8 fields locked + chapter shape `{title, start, excerpt}` no independent keywords | VERIFIED | REQUIRED_FIELDS + CHAPTER_FIELDS constants exact match |
| D-02 (Phase 7.6 hook) | Inserted between Phase 7.5 and Phase 8 in CLAUDE.md `/summarize-video` | VERIFIED | L1747 → L1772 → L1828 exact ordering |
| D-03 (top-level aggregator) | Flat dict `{<slug>: <per-slug>, ...}` no backlinks; lexicographic ordering | VERIFIED | _rebuild_aggregator_inner L318 sorted; no backlink fields |
| D-04 (`index rebuild` CLI) | Idempotent + skip-on-malformed + stderr WARNING + exit 1 if zero valid | VERIFIED | cmd_index_rebuild L1914–1916 exit code logic; stderr per-skip lines |
| D-05 (`index write` CLI) | --slug + --from-stdin + schema check + atomic write + immediate aggregator rebuild + stdout JSON contract | VERIFIED | cmd_index_write byte-equal D-05.5 contract; --force flag wired (D-05.7) |
| D-06 (keywords reuse glossary H2) | byte-equal canonical strings; vacuous-empty tolerant | VERIFIED | glossary_h2_anchors helper + CLAUDE.md hook explicit reuse instruction |
| D-07 (D-29 byte-equal verify) | Phase 11 close gate runs replay → 33/0/30 PASS | VERIFIED | live replay on main: 33/0/30 |
| D-08 (`agent/index.py` module layout) | 5 public functions + IndexValidationError + module constants | VERIFIED | matches D-08.2 surface byte-equal |
| D-09 (FileLock serialization) | `output/.index.lock` lock file + reuse `agent/_lock.FileLock` + lock-free reads | VERIFIED | LOCK_FILENAME = ".index.lock" + FileLock import + lock-only-on-write |
| D-10 (K5 boundary static assertion) | 3 new tests added; count 17 → 20 | VERIFIED | tests/test_k5_emitters.py L301/320/336; all 20 K5 tests pass |

### Phase 12 Readiness Contract

The downstream Phase 12 backfill (KB-12) reuses `agent.index.write_per_slug_index` as the canonical generator entry point. This contract is verified stable:

| Phase 12 Dependency | Status | Evidence |
|---|---|---|
| `agent.index.write_per_slug_index(slug_dir, index_data, *, output_dir=None, timeout=10.0, force=False)` importable + callable | VERIFIED | `inspect.signature` matches expected D-08.2 contract byte-equal |
| `--force` flag in `python -m agent.tools index write` for backfill emergency | VERIFIED | agent/tools.py L2217 `iwrite.add_argument("--force", action="store_true", help="...Phase 12 backfill emergency only")` |
| `agent.index.glossary_h2_anchors` vacuous-empty tolerant | VERIFIED | returns `[]` when file missing |
| `_topics.md` Approved Taxonomy populated (Phase 10 dependency) | VERIFIED | Phase 10 plan-02 ship populated 5 categories / 19 leaves / 24 nodes |
| Phase 7.6 hook content references CLI byte-equal | VERIFIED | CLAUDE.md L1804 invocation matches `cmds["index"]["write"]` arg parser byte-equal |
| D-29 replay baseline recorded for Phase 12 close-gate comparison | VERIFIED | 33 PASS / 0 FAIL on main per replay_v10_archives.py |

### Anti-Patterns Found

None. Source-grep + behavioral verification + K5 static assertions all clean. The K5 source-grep tests (3 new + 17 existing) statically prove that `agent/index.py` + `cmd_index_write` + `cmd_index_rebuild` contain zero of the 5 D-29 core literals (`summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json`) — the K5 boundary holds at the prompt level (CLAUDE.md L1781 + L1826) AND at the source level (test_k5_emitters.py L301/320/336).

One auto-fixed deviation noted in Plan 11-01 SUMMARY (Rule 1 stderr routing for slug-prefix log to preserve --json stdout byte-equal contract per PARA-04). The fix is documented inline in cmd_index_write source.

### Human Verification Required

#### 1. KB-02 E2E — Phase 7.6 hook on a real new video

**Test:**
1. Pick a video that doesn't have `output/<slug>/index.json` yet.
2. Run `/summarize-video <url>` (or resume from existing partial output).
3. After Phase 7 / Phase 7.5 complete, observe Claude executing Phase 7.6:
   - Reads the 5 files (summary.md / meta.json / plan.md / _glossary.md / _topics.md)
   - Composes 8-field JSON
   - Pipes to `python -m agent.tools index write --slug <slug> --from-stdin`

**Expected:**
- `output/<slug>/index.json` exists, schema-valid (8 fields all present)
- `output/.index.json` contains `<slug>` as a key
- Re-trigger Phase 7.6 → CLI returns `action: "skipped"` (idempotent on byte-equal stdin)
- If a `pending: <name>` topic was proposed, `output/_topics.md` `## Pending` segment grew by an H3 entry with 3 sub-fields (申请来源 slug + chapter title + 提议理由)

**Why human:** Cannot unit-test "Claude in a real Claude Code session follows a documented prompt rule." The prompt-following behavior is a Claude-in-context thing that requires a live session on a real video. Documented as deferred by design (mirror v1.1 Phase 09 P-09 token-budget gate pattern) per RESEARCH A6 + Q-F. **Phase 11 ship is NOT blocked on this UAT** — recommended for the user's next video processing session.

### Gaps Summary

No blocking gaps. All 6 KB-XX requirements satisfied at the documentation + CLI + unit-test level; the only deferred item is the KB-02 E2E behavioral UAT, which mirrors the v1.1 Phase 09 P-09 deferred-manual-gate pattern explicitly endorsed in RESEARCH A6 + Q-F.

The 11-02-SUMMARY.md notes that the worktree replay output recorded `1 PASS / 0 FAIL / 3 SKIP` (limited by which slugs the worktree had committed); the canonical post-merge main-branch replay (verified live during this verification) reports `33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)` — D-29 invariant **PRESERVED**.

---

*Verified: 2026-05-04*
*Verifier: Claude (gsd-verifier)*
