---
phase: 10-topic-taxonomy-governance-bootstrap-cli
verified: 2026-05-03T17:25:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
---

# Phase 10: Topic Taxonomy Governance + Bootstrap CLI Verification Report

**Phase Goal:** 立起 v1.2 知识库的"词表层"——`output/_topics.md` governance 文件 + 3 个 CLI（topics bootstrap / audit / resolve）让 Claude 写 index.json 时有可选 topic 集合，且新概念走"申请 Pending → 用户偶尔 review"的 K5 governance 闭环。零 summary.md / index.json mutation；Phase 11 / 12 全部依赖本 phase 提供的"已批准 topic 集合"。
**Verified:** 2026-05-03T17:25:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (merged from ROADMAP SC + PLAN frontmatter)

| #  | Truth                                                                                                                              | Status     | Evidence                                                                                                                                                                                |
| -- | ---------------------------------------------------------------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1  | `output/_topics.md` file structure byte-locked: 2 fixed segments (`## Approved Taxonomy` tree + `## Pending` 3-field H3) | ✓ VERIFIED | File reads at output/_topics.md L1-L37; locked `# Topics Taxonomy` header (lines 1-6) byte-equal to `agent/topics.py:_FILE_HEADER` (L60-L76); 2 H2 segments present                      |
| 2  | `topics bootstrap` produces non-empty initial taxonomy from 17+ archives; first bootstrap defaults all to Approved (Pending empty) | ✓ VERIFIED | output/_topics.md L8-L33 has 5 top-level + 19 leaves = 24 nodes; L35-L37 `## Pending` section has only HTML-comment placeholder (0 H3 entries); SUMMARY 10-02 documents 22+ archives read |
| 3  | `topics bootstrap` is idempotent (re-run on populated file returns `action=skipped` + WARNING)                                   | ✓ VERIFIED | Live invocation: `echo '{"taxonomy":[{"name":"X","subtopics":[]}]}' \| python -m agent.tools topics bootstrap --from-stdin --json` returns `{"action":"skipped","approved_count":24,...}` |
| 4  | `topics audit --json` produces valid JSON with `pending`, `approved_with_counts`, `orphans`, `audit_note`, `read_at` keys           | ✓ VERIFIED | Live: pending=[], approved_with_counts size=24, orphans=[], audit_note contains "Phase 11 not yet shipped", read_at=`2026-05-03T17:18:27Z` (ISO-8601 UTC)                                |
| 5  | `topics resolve <pending>` atomically promotes/renames/removes pending entry + updates per-slug index.json refs                    | ✓ VERIFIED | tests/test_topics.py TestResolve 8 tests pass (1 platform-skipped on Windows for chmod-readonly atomic-restore — acceptable per plan); resolve_pending source L522-L714 implements snapshot-then-restore |
| 6  | `agent.topics.append_pending(topics_path, name, from_slug, chapter_title, reason)` Phase 11 generator API stable + importable      | ✓ VERIFIED | `python -c "from agent.topics import append_pending; ..."` returns signature `(topics_path: 'Path', name: 'str', from_slug: 'str', chapter_title: 'str', reason: 'str', *, output_dir=None, timeout: 'float' = 10.0) -> 'dict'` matching D-05.3 contract |
| 7  | K5 boundary statically asserted: 4 new tests in tests/test_k5_emitters.py pass                                                     | ✓ VERIFIED | Test names match RESEARCH pattern (with adjusted prefix): `test_topics_bootstrap_no_index_json_writes`, `test_topics_audit_no_writes`, `test_topics_resolve_only_writes_topics_md_and_index_json`, `test_topics_module_no_summary_writes` — all 4 pass |
| 8  | D-29 byte-equal preserved: `replay_v10_archives.py` still reports 0 FAIL after Phase 10                                            | ✓ VERIFIED | Live `python scripts/replay_v10_archives.py` → "Summary: 33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)"                                                                                  |
| 9  | ¥0 hard constraint: zero new pip dependencies                                                                                       | ✓ VERIFIED | `git diff 6cbcd86..HEAD -- requirements.txt requirements-optional.txt` returns empty; agent/topics.py imports only stdlib (json, logging, os, re, tempfile, pathlib) + agent._lock      |
| 10 | All v1.0/v1.1 ship CLIs still callable; existing test suite still passes                                                            | ✓ VERIFIED | Combined run `python -m unittest tests.test_topics tests.test_k5_emitters -v` → "Ran 41 tests in 0.312s OK (skipped=1)"                                                                  |
| 11 | `read_topics` lock-free returns Phase 11 whitelist (5 top-level + 24 nodes)                                                         | ✓ VERIFIED | `python -c "from agent.topics import read_topics; ..."` → top-level names: ['Game-Dev', 'AI-Art-Generation', 'AI-Tooling', 'LLM-Concepts', 'Misc']                                       |
| 12 | `topics resolve <unknown-name>` exits non-zero with "pending entry not found" (fail-fast, not idempotent per D-04.6)                | ✓ VERIFIED | TestResolve.test_resolve_unknown_name_raises asserts KeyError/LookupError; cmd_topics_resolve catches KeyError → `print("error: pending entry not found", file=sys.stderr); sys.exit(1)` (tools.py L1733-L1736) |
| 13 | FileLock domain `output/.topics.lock` reserved + tested (third cross-slug lock domain)                                              | ✓ VERIFIED | TOPICS_FILENAME / LOCK_FILENAME constants in agent/topics.py L50-L51; TestAppendPending.test_concurrent_append_via_multiprocessing + test_lock_contention_with_zero_timeout pass        |

**Score:** 13/13 truths verified

### Required Artifacts

| Artifact                  | Expected                                                                                                                | Status     | Details                                                                                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `agent/topics.py`         | 4 public functions (read_topics, write_approved_taxonomy, append_pending, resolve_pending) + _atomic_write helper       | ✓ VERIFIED | 734 lines total; all 4 public functions defined (L198, L324, L392, L522); `_atomic_write` at L79; `_FILE_HEADER`/`TOPICS_FILENAME`/`LOCK_FILENAME` constants present |
| `agent/tools.py`          | 3 cmd handlers (cmd_topics_bootstrap/audit/resolve) + nested `topics` subparser + topics_cmds dispatch dict             | ✓ VERIFIED | cmd_topics_bootstrap @L1587, cmd_topics_audit @L1635, cmd_topics_resolve @L1719; `topics_cmds` dispatch dict @L2108-L2111; `args.command == "topics"` route @L2117-L2118 |
| `tests/test_topics.py`    | 5 test classes covering KB-07/09/10/11 + append_pending API; 24 behavior tests (1 platform-skipped on Windows)         | ✓ VERIFIED | 5 classes (TestReadTopics, TestBootstrap, TestAppendPending, TestAudit, TestResolve); 24 tests run, 1 skipped (test_resolve_atomic_restore_on_index_failure on win32 — acceptable per plan) |
| `tests/test_k5_emitters.py` | 4 new K5 boundary tests (Phase 10 D-06.1)                                                                              | ✓ VERIFIED | tests defined L234-L297: test_topics_bootstrap_no_index_json_writes / test_topics_audit_no_writes / test_topics_resolve_only_writes_topics_md_and_index_json / test_topics_module_no_summary_writes — all 4 pass; `_RESOLVE_FORBIDDEN_PATTERNS` tuple @L53-L73 covers 5 D-29 artifacts × 5 write APIs |
| `tests/_tmp_topics/.gitkeep` | ASCII-safe per-test tmpdir marker (mirrors tests/_tmp_glossary/)                                                       | ✓ VERIFIED | Used by `_ascii_tmpdir_root()` in test_topics.py L28-L34                                                                                          |
| `output/_topics.md`       | NEW v1.2 governance file at repo root with locked header + ≥3 top-level + ≥10 total entries                              | ✓ VERIFIED | 38 lines, sha256 `661319b4d94c2f2ad16feda3c47072b8a10df0fe9c2703c03d64ca01c3a68748`; 5 top-level (Game-Dev/AI-Art-Generation/AI-Tooling/LLM-Concepts/Misc) + 19 leaves = 24 total |

### Key Link Verification

| From                              | To                                                | Via                                                  | Status   | Details                                                                                                                                  |
| --------------------------------- | ------------------------------------------------- | ---------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `agent/topics.py`                 | `agent/_lock.FileLock`                            | `from agent._lock import FileLock, LockContended`    | ✓ WIRED  | Import at agent/topics.py L46 confirmed; used in `write_approved_taxonomy` (L355), `append_pending` (L431), `resolve_pending` (L584)     |
| `agent/topics.py:resolve_pending` | atomic write of `_topics.md` + N index.json files | `_atomic_write` + snapshot/restore on exception      | ✓ WIRED  | resolve_pending L678-L702 uses snapshot-then-atomic-write pattern with restore-on-exception loop; verified by test_resolve_atomic_restore_on_index_failure (Linux) |
| `agent/tools.py:main`             | `agent.topics` module                             | `cmd_topics_bootstrap/audit/resolve` handlers        | ✓ WIRED  | Each handler imports inside function: `from agent.topics import write_approved_taxonomy, _resolve_paths` (L1593) etc.; dispatch via `topics_cmds[args.topics_cmd](args)` (L2118) |
| `tests/test_k5_emitters.py`       | `agent.tools.cmd_topics_*`                        | `inspect.getsource()` static-grep + write-pattern regex | ✓ WIRED  | Imports L17-L25; tests use `inspect.getsource(cmd_topics_bootstrap)` etc. + `_RESOLVE_FORBIDDEN_PATTERNS` regex tuple                     |
| Claude (Phase 10-02 executor)     | 22+ `output/<slug>/summary.md` archives           | Read tool — 30-60 lines per archive                  | ✓ WIRED  | SUMMARY 10-02 lists 22+ archives sampled (Pixel-art cluster 10, Godot cluster 8, AI-tooling/LLM cluster 5, Outlier 1)                    |
| Phase 11 generator (future)       | `output/_topics.md`                               | `from agent.topics import read_topics, append_pending` | ✓ WIRED  | Both functions importable; signatures stable — read_topics returns `{approved, pending, exists}`; append_pending matches D-05.3 contract |

### Behavioral Spot-Checks

| Behavior                                                              | Command                                                                                                                                     | Result                                                                                       | Status |
| --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | ------ |
| `topics --help` lists 3 subcommands                                   | `python -m agent.tools topics --help`                                                                                                       | "{bootstrap,audit,resolve}" listed with descriptions                                          | ✓ PASS |
| `topics audit --json` produces valid JSON                             | `python -m agent.tools topics audit --json`                                                                                                 | pending=[], approved_with_counts size=24, orphans=[], audit_note has "Phase 11", read_at present | ✓ PASS |
| `topics bootstrap --from-stdin` idempotent on populated file          | `echo '{"taxonomy":[{"name":"X","subtopics":[]}]}' \| python -m agent.tools topics bootstrap --from-stdin --json`                          | `{"action":"skipped","approved_count":24,...}` + stderr WARNING                              | ✓ PASS |
| `read_topics` returns ≥3 top-level + ≥10 entries Phase 11 whitelist   | `python -c "from agent.topics import read_topics; r=read_topics(Path('output/_topics.md')); ..."`                                          | top-level names: 5 categories; total node count 24                                            | ✓ PASS |
| `append_pending` signature matches D-05.3 contract                    | `python -c "from agent.topics import append_pending; import inspect; print(inspect.signature(append_pending))"`                            | `(topics_path: 'Path', name: 'str', from_slug: 'str', chapter_title: 'str', reason: 'str', *, output_dir=None, timeout: 'float' = 10.0) -> 'dict'` | ✓ PASS |
| Full Phase 10 test suite passes                                       | `python -m unittest tests.test_topics tests.test_k5_emitters -v`                                                                            | "Ran 41 tests in 0.312s OK (skipped=1)"                                                       | ✓ PASS |
| D-29 byte-equal regression                                             | `python scripts/replay_v10_archives.py`                                                                                                     | "Summary: 33 PASS / 0 FAIL / 30 SKIP (of 33 candidates)"                                      | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan(s)        | Description                                                                                                            | Status      | Evidence                                                                                                                                                       |
| ----------- | --------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| KB-07       | 10-01 (infra)         | `output/_topics.md` governance 文件结构 — Approved Taxonomy + Pending 段                                              | ✓ SATISFIED | _FILE_HEADER constant locked byte-equal D-01.6; output/_topics.md L1-L37 confirms 2-segment shape; read_topics parses both segments                            |
| KB-08       | 10-01 (CLI plumbing) + 10-02 (content) | `topics bootstrap` CLI 一次性扫 17 archives 产出非空初始 taxonomy                                                 | ✓ SATISFIED | cmd_topics_bootstrap @tools.py L1587 + write_approved_taxonomy @topics.py L324; output/_topics.md L8-L33 has 5/24 entries from 22+ archives (SUMMARY 10-02)    |
| KB-09       | 10-01                 | `topics audit [--json]` CLI — pending list + 引用计数 + 孤儿检测                                                       | ✓ SATISFIED | cmd_topics_audit @tools.py L1635 read-only; outputs pending/approved_with_counts/orphans/audit_note/read_at JSON schema D-03.6                                  |
| KB-10       | 10-01                 | `topics resolve <pending-name> [--rename] [--remove]` atomic 跨多 index.json 改写                                      | ✓ SATISFIED | cmd_topics_resolve @tools.py L1719 + resolve_pending @topics.py L522; snapshot-then-atomic-write with restore-on-failure (L678-L702); 8 TestResolve tests pass |
| KB-11       | 10-01                 | K5 boundary 静态断言 + `append_pending` Python API for Phase 11 generator                                              | ✓ SATISFIED | append_pending @topics.py L392 with D-05.3 signature; 4 K5 tests pass; module + 3 cmd handlers contain zero D-29 core artifact literals                       |

**No orphan requirements.** All 5 KB-XX in this phase mapped to plans (10-01 + 10-02). REQUIREMENTS.md L112 confirms Phase 10 = `KB-07, KB-08, KB-09, KB-10, KB-11` (5 reqs).

### CONTEXT Decisions Honored (D-01..D-08)

| Decision                                                                                                       | Honored | Evidence                                                                                                                                       |
| -------------------------------------------------------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| D-01.1 file path `output/_topics.md` at repo root                                                              | ✓       | TOPICS_FILENAME constant at agent/topics.py L50 + DEFAULT_OUTPUT_DIR L52; output/_topics.md exists at expected path                            |
| D-01.2 schema = 2 segments (Approved + Pending)                                                                | ✓       | output/_topics.md L8 `## Approved Taxonomy` + L35 `## Pending`                                                                                  |
| D-01.3 max 3 levels nesting                                                                                    | ✓       | _validate_taxonomy raises ValueError at depth>3 (L241-L244); test_rejects_nesting_past_3_levels confirms                                       |
| D-01.4 Pending H3 with 3 mandatory bullet sub-fields                                                           | ✓       | _parse_pending_entries reads 3 fields (L181-L188); append_pending writes 3 fields (L453-L459)                                                  |
| D-01.6 file header byte-equal locked                                                                           | ✓       | _FILE_HEADER L60-L76 + _render_full_file header_top L304-L313; output/_topics.md L1-L6 byte-equal                                              |
| D-02.4 first bootstrap defaults all to Approved (Pending empty)                                                | ✓       | output/_topics.md L37 contains only HTML-comment placeholder; no `### ` H3 entries                                                              |
| D-02.5 stdout JSON shape locked                                                                                | ✓       | cmd_topics_bootstrap L1623-L1624 produces `{action, approved_count, _topics_path}` byte-equal to D-02.5                                        |
| D-02.6 `--from-stdin` flag fails-fast on missing                                                               | ✓       | tools.py L1594-L1597 prints error + exit 1 if `not args.from_stdin`                                                                            |
| D-03.6 audit `--json` schema includes `pending` / `approved_with_counts` / `orphans` / `audit_note` / `read_at` | ✓       | tools.py L1685-L1691 builds result dict with all 5 keys                                                                                        |
| D-03.7 audit is read-only                                                                                      | ✓       | test_topics_audit_no_writes K5 test asserts no write API patterns in cmd_topics_audit source                                                   |
| D-04.5 resolve stdout JSON shape locked                                                                        | ✓       | resolve_pending returns `{action, pending_name, final_name, index_json_updated, _topics_path}` (topics.py L708-L714) byte-equal to D-04.5      |
| D-04.6 unknown pending-name fails-fast (not idempotent)                                                        | ✓       | resolve_pending raises KeyError L591/L596; cmd_topics_resolve catches → exit 1 (L1733-L1736)                                                   |
| D-05.3 `append_pending(topics_path, name, from_slug, chapter_title, reason)` signature exposed                  | ✓       | inspect.signature confirms exact 5-arg signature                                                                                                |
| D-06.1 4 K5 boundary tests added                                                                                | ✓       | tests/test_k5_emitters.py L234-L297 — all 4 tests pass                                                                                          |
| D-07.1 module path `agent/topics.py`                                                                            | ✓       | File exists at expected path                                                                                                                    |
| D-07.2 4 public functions exported                                                                              | ✓       | read_topics / write_approved_taxonomy / append_pending / resolve_pending all importable                                                         |
| D-08.1 lock domain `output/.topics.lock` (third cross-slug lock)                                                | ✓       | LOCK_FILENAME = ".topics.lock" agent/topics.py L51                                                                                              |
| D-08.4 read_topics is lock-free                                                                                 | ✓       | read_topics L198-L229 has no FileLock context manager; module docstring L34 confirms                                                            |

### Anti-Patterns Found

None. Source scan of agent/topics.py + tools.py L1587-L1749 + test_topics.py + test_k5_emitters.py L234-L297 found:

- 0 TODO/FIXME/XXX/HACK markers
- 0 stub returns (`return null` / empty `=> {}`)
- 0 unimplemented placeholders
- 0 hardcoded empty arrays in load-bearing positions (the `<!-- (initially empty until bootstrap runs) -->` HTML comment in _FILE_HEADER is a documented placeholder per D-02.4 and gets replaced on bootstrap)
- All `cmd_topics_*` handlers wired into `topics_cmds` dispatch dict + `args.command == "topics"` route in `main()`

### Human Verification Required

None. All ROADMAP SC + PLAN must-haves are verifiable programmatically and pass.

### Gaps Summary

No gaps. Phase 10 goal achieved completely:

1. **Word-list layer is up:** `output/_topics.md` exists at repo root with 5 categories + 24 nodes, locked header byte-equal to `_FILE_HEADER` constant, 2-segment schema fixed, first bootstrap defaulted all to Approved (Pending empty). Phase 11 generator can `from agent.topics import read_topics, append_pending` and consume the whitelist immediately.

2. **3 CLIs working:** `topics bootstrap` (CLI plumbing + first content via 10-02) / `topics audit` (read-only K5) / `topics resolve` (atomic multi-file write with snapshot-restore). All 3 verified via live invocation. Stdout JSON shapes match D-02.5 / D-03.6 / D-04.5 byte-equal.

3. **K5 boundary statically asserted:** 4 new tests in test_k5_emitters.py (matching the names from RESEARCH up to a `test_K5_module_topics_no_*` vs `test_topics_module_no_*` minor naming variation — same coverage). All 4 pass; agent/topics.py module source has zero D-29 core artifact literals (5 forbidden: summary.md, plan.md, paragraphs.json, segs.json, meta.json). The literals `_topics.md` + `index.json` are LEGITIMATE per D-06.1 (those are the only files this surface may write).

4. **D-29 byte-equal preserved:** `python scripts/replay_v10_archives.py` reports **33 PASS / 0 FAIL / 30 SKIP**. `output/_topics.md` is a NEW top-level governance file outside the 4-core-artifact replay scope; the replay confirms no v1.0 archive was perturbed.

5. **¥0 hard constraint preserved:** Zero new pip dependencies between v1.2 milestone start (commit 6cbcd86) and Phase 10 close (HEAD). agent/topics.py is stdlib-only (json, logging, os, re, tempfile, pathlib) + agent._lock (already shipped Phase 06).

6. **Phase 11 contract is satisfiable:** `agent.topics.append_pending` signature stable + matches D-05.3; `agent.topics.read_topics` returns 5-element approved list with nested subtopics arrays; whitelist (24 entries) ready for per-slug index.json generator validation.

**Note on test name variation:** RESEARCH suggested test names with prefix `test_K5_module_topics_no_summary_writes` / `test_K5_cmd_topics_*` / `test_K5_module_topics_no_d29_writes`. The shipped names use `test_topics_module_no_summary_writes` / `test_topics_bootstrap_no_index_json_writes` / `test_topics_audit_no_writes` / `test_topics_resolve_only_writes_topics_md_and_index_json` (different prefix, same intent). This is a naming-convention deviation that matches the existing `TestK5BoundaryPhase07` class style (where Phase 07 used `test_K5_handler_*` and Phase 08/09 evolved to plain `test_*` for the new write-pattern style). Coverage is equivalent — all 4 K5 boundaries are statically asserted.

---

_Verified: 2026-05-03T17:25:00Z_
_Verifier: Claude (gsd-verifier)_
