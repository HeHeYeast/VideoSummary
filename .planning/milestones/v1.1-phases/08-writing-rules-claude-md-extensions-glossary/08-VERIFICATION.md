---
phase: 08-writing-rules-claude-md-extensions-glossary
verified: 2026-05-03T11:35:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 08: Writing rules — CLAUDE.md extensions + glossary Verification Report

**Phase Goal:** Make new summaries (slugs with `.v11_features.json` marker) diverge in shape — inline ASR corrections via L2/L3 prompts, inline trace tokens after every load-bearing claim, zero-baseline self-contained header, first-mention inline term annotations, cross-slug `output/_glossary.md` accumulation with FileLock, optional 5-min TL;DR speedrun for long videos.
**Verified:** 2026-05-03T11:35:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (mapped to 5 ROADMAP success criteria)

| # | Truth (ROADMAP SC) | Status | Evidence |
|---|--------------------|--------|----------|
| 1 | L2/L3 ASR corrections write to plan.md, never to segs.json (P-01) — max 10 corrections + L2 ≥ 2 evidence + L3 ≤ 5 frames + ±0.5s window. segs.json NEVER mutated. | VERIFIED | CLAUDE.md L1160-1191 (CORR-01b) + L1193-1209 (CORR-01c) state literal hard caps verbatim: "max 10 auto-applied corrections per slug" (L1176), "≥ 2 条独立 evidence sources" (L1175), "时间窗 HARD CAP：抽帧范围 [start - 0.5s, start + 0.5s]" (L1201), "max 5 frames per warning" (L1202). L1191 explicitly: "**绝不**修改 segs.json". L3 cap rolls up into CORR-01b's 10-total (L1209). Trigger gates on `is_v11_enabled(slug, "l2_l3_correction")`. |
| 2 | Inline trace tokens enforced; citation pollution prevented (P-02) — every concrete claim followed by `[seg_*.jpg @ HH:MM:SS]` or `[para_ID @ HH:MM:SS]`. 3-tier eligibility. avg ≤ 1 citation per 3 sentences. | VERIFIED | CLAUDE.md L1211-1275 (CORR-02). Token format L1220-1226 with examples. Three-tier eligibility explicit: REQUIRED list L1230-1235, FORBIDDEN list L1237-1241, OPTIONAL list L1243-1245. Density target stated L1247: "avg ≤ 1 citation per 3 sentences". Self-check pass with `[?]` < 80% confidence at L1253-1258 + footer schema L1262-1273. Both triggers gate on `is_v11_enabled` (L1213-1214, L1251). |
| 3 | Self-contained zero-baseline header (D-01) — top: 标题/UP/时长/链接 → 你需要知道 (≤ 3 行) → 你不需要知道 (≤ 3 行) → optional TL;DR → 正文. ≤ 6 lines hard cap. No "简单来说" / "说白了" / "你可能不知道". | VERIFIED | CLAUDE.md L1299-1342 (TEACH-A2). Locked structure L1305-1329 byte-equal to ROADMAP SC. Hard caps L1331-1335: ≤ 3 lines per section, ≤ 6 lines total header (excluding TL;DR). Anti-patronizing FORBIDDEN phrases at L1339-1341 include all three: "简单来说" / "说白了" / "你可能不知道", plus "一言以蔽之" / "说人话就是" / "相信很多人不清楚" / "你是不是觉得". Required tone L1342: 第二人称指令式. Trigger gates on `is_v11_enabled(slug, "self_contained_header")` (L1301). |
| 4 | Cross-slug glossary append works under FileLock without corruption (P-04) — `output/_glossary.md` append-only via `python -m agent.tools glossary append`. `output/.glossary.lock`. Same (slug, term) idempotent. Inline-first invariant. | VERIFIED | (a) **Code path:** `agent/glossary.py:175` `with FileLock(lock_path, timeout=timeout):` wraps the entire read-then-write region (L177-L221). LOCK_FILENAME = ".glossary.lock" (L38), GLOSSARY_FILENAME = "_glossary.md" (L37). Idempotency at L202-213 via `_slug_link_substring(slug)` containment check. (b) **Test evidence:** `tests/test_glossary.py:T2` (idempotency byte-equal), `T3` (multiprocessing race spawns 2 children → exactly 1 H2 + 1 bullet), `T6` (LockContended raised when held). All 6 tests pass in 0.289s. (c) **Inline-first invariant:** CLAUDE.md L1348 (CRITICAL): "每个首次出现的术语**必须**先按 TEACH-A1 加 inline 注解，**然后**再调用 glossary append... 禁止用'glossary 里有'作为跳过 inline 注解的理由". (d) **CLI smoke test:** behavioral spot-check produced `{"action": "appended", "term_h2_created": true, "slug_link_added": true}` with file containing locked header + H2 + bullet. |
| 5 | TL;DR drift prevented (P-06) — `## 5 分钟速读版` block written LAST, 10-15 lines hard cap, zero citations (use section anchors). Triggered by `paragraphs.json[-1].end > 1200` OR `estimated_sections > 50`. Sync check. | VERIFIED | CLAUDE.md L1374-1409 (TEACH-B). Trigger L1376 byte-equal to ROADMAP SC: "`paragraphs.json` 末尾段的 `end > 1200`（视频 > 20 分钟）OR plan.md front-matter `estimated_sections > 50`". "写在 LAST" invariant L1403 with explicit P-06 reference. Zero-citation rule L1404 with FORBIDDEN explicit + section-anchor replacement (`详见 §三、消化阶段`). 10-15 line hard cap L1380 + max 20 cap L1409. Sync check L1405-1408 covers replicate-guide (≤ 20% drift) and interview-distillation (≤ 30% drift) modes. Trigger gates on `is_v11_enabled(slug, "tldr_speedrun")` (L1376). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `agent/glossary.py` | NEW module with `glossary_append` + `GLOSSARY_FILENAME` + `LOCK_FILENAME`, FileLock-protected writes, ≥ 80 lines | VERIFIED | 231 lines. Exports `glossary_append` (L128), `GLOSSARY_FILENAME = "_glossary.md"` (L37), `LOCK_FILENAME = ".glossary.lock"` (L38). FileLock import at L33 + usage at L175. |
| `agent/_v11.py` | V11_FEATURES tuple = 13 entries (8 Phase 07 + 5 Phase 08); contains `inline_trace_tokens` | VERIFIED | `len(V11_FEATURES) == 13` confirmed at runtime. All 6 Phase-08-required flags present: `l2_l3_correction`, `inline_trace_tokens`, `self_check_confidence`, `self_contained_header`, `cross_slug_glossary`, `tldr_speedrun`. All 8 Phase-07 names preserved. |
| `agent/tools.py` | `cmd_glossary_append` handler + nested `glossary {append,audit}` subparser, wired into main() | VERIFIED | `cmd_glossary_append` at L1504, nested subparser `gsub = p.add_subparsers(dest="glossary_cmd", required=True)` at L1700, dispatch table `glossary_cmds = {"append": cmd_glossary_append, ...}` at L1784, dispatch `glossary_cmds[args.glossary_cmd](args)` at L1791. `python -m agent.tools glossary --help` exits 0 showing both subcommands. Legacy `glossary_audit` standalone alias preserved (backward-compat). |
| `tests/test_glossary.py` | 6 unittest tests (T1 schema / T2 idempotent / T3 race / T4 first-seen-wins / T5 audit forward-compat / T6 LockContended), ≥ 120 lines | VERIFIED | 192 lines. All 6 tests run + pass in 0.289s. T3 multiprocessing.spawn race test confirms exactly 1 H2 + 1 bullet survive 2 concurrent appends. |
| `tests/test_k5_emitters.py` | 3 NEW K5 boundary tests for `agent/glossary.py` using write-pattern regex | VERIFIED | 3 new tests at L104-165: `test_K5_handler_cmd_glossary_append`, `test_K5_module_glossary`, `test_K5_glossary_append_writes_only_to_accumulator`. `_WRITE_PATTERNS_FORBIDDEN` regex tuple at L33-46 covers `write_text` / `open(...,'w')` / `os.replace` / `_atomic_write` patterns against `summary.md` / `plan.md` / `schedule.json`. Behavioral test pre-creates fake `summary.md` / `plan.md` / `schedule.json` and asserts they're untouched after `glossary_append`. All 11 K5 tests pass. |
| `CLAUDE.md` | Extended with new H2 section "v1.1 自适应教学文档增强 (Phase 08)" containing 7 sub-rules; extended `### 格式锁定` with 5th invariant; 4 cross-references | VERIFIED | New H2 at L1143 (single occurrence). All 7 sub-rule headings present: CORR-01b (L1160), CORR-01c (L1193), CORR-02 (L1211), TEACH-A1 (L1277), TEACH-A2 (L1299), TEACH-A3 (L1344), TEACH-B (L1374). 5th invariant in `### 格式锁定` at L269/L277 (`4+1 项不变量`). 4 cross-references in /summarize-video at L1449 (Phase 2.5), L1515 (Phase 6), L1527 (Phase 7), L1534 (Phase 8). File size grew to 79,984 bytes (~78 KB). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `agent/glossary.py:glossary_append` | `agent/_lock.py:FileLock` | `with FileLock(lock_path, timeout=timeout):` | WIRED | L33 import + L175 usage. T6 test asserts `LockContended` raised when held externally. T3 race test asserts serialization works under contention. |
| `agent/glossary.py:glossary_append` | atomic write helper (NOT `write_json_atomic`) | tempfile + os.replace pattern | WIRED | `_atomic_write` at L59-82 uses `tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` + `tmp.flush()` + `os.fsync()` + `os.replace()`. Markdown is text not JSON, so write_json_atomic correctly NOT used. |
| `agent/tools.py:main()` | `cmd_glossary_append` | nested dispatch `glossary_cmds[args.glossary_cmd]` | WIRED | L1784 dispatch table + L1791 dispatch call. `python -m agent.tools glossary append --help` exits 0 showing all 7 args (--slug --term --definition --context --output-dir --timeout --json). |
| `tests/test_glossary.py:T3` | `multiprocessing.Process` | `mp.get_context("spawn")` for Windows compat | WIRED | T3 spawns 2 child processes hitting same (slug, term); both join cleanly within 30s, exit 0; final file contains exactly 1 `## Diffusion (扩散模型)` + 1 `[BVrace](BVrace/summary.md)`. |
| CLAUDE.md /summarize-video Phase 2.5 | CLAUDE.md v1.1 H2 → CORR-01b/c | "详见 § v1.1 自适应教学文档增强 (Phase 08) → CORR-01b/c" | WIRED | L1449. Refers to `l2_l3_correction` flag and points back to the v1.1 H2 anchor. |
| CLAUDE.md /summarize-video Phase 6 | CLAUDE.md v1.1 H2 → CORR-02 + TEACH-A1/A2/A3 | blockquote referencing `inline_trace_tokens` / `self_contained_header` / `cross_slug_glossary` | WIRED | L1515-1525. Three-flag blockquote with sub-bullets per flag pointing to the v1.1 H2 sub-rules. |
| CLAUDE.md /summarize-video Phase 7 | CLAUDE.md v1.1 H2 → TEACH-B | "tldr_speedrun AND（视频时长 > 20 min OR estimated_sections > 50）" | WIRED | L1527. Trigger condition byte-equal to ROADMAP SC; references back to TEACH-B. |
| CLAUDE.md /summarize-video Phase 8 | CLAUDE.md v1.1 H2 → CORR-02 self-check | `self_check_confidence` flag + glossary audit | WIRED | L1534. Two flags referenced (`self_check_confidence` + `cross_slug_glossary` audit recommendation). |
| CLAUDE.md TEACH-A3 prompt | `agent/tools.py glossary append CLI` (Plan 08-01) | literal CLI invocation in prompt at L1354-1360 | WIRED | Full literal command block: `python -m agent.tools glossary append --slug <current_slug> --term "..." --definition "..." --context "..."`. CLI surface from Plan 08-01 referenced verbatim. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `python -m agent.tools glossary --help` shows append+audit subcommands | `python -m agent.tools glossary --help` | Exit 0; lists both `append` and `audit` subcommands | PASS |
| `python -m agent.tools glossary append --help` shows 7 args | `python -m agent.tools glossary append --help` | Exit 0; shows --slug, --term, --definition, --context, --output-dir, --timeout, --json | PASS |
| Legacy `glossary_audit` standalone alias still works | `python -m agent.tools glossary_audit --json` | Exit 0; outputs `{"version": 1, "glossary_path": ..., "exists": false, "term_count": 0, ...}` | PASS |
| Behavioral CLI smoke: `glossary append` creates file with locked schema | `python -m agent.tools glossary append --slug BVsmoke --term "TestTerm (test)" --definition "A test definition." --output-dir <tmp> --json` | Exit 0; stdout `{"action": "appended", "term_h2_created": true, "slug_link_added": true}`; file contains `# 术语表` header + 3-line preamble + `## TestTerm (test)` + `- [BVsmoke](BVsmoke/summary.md)` | PASS |
| 27 Phase 08 tests pass (6 + 11 + 10) | `python -m unittest tests.test_glossary tests.test_k5_emitters tests.test_v11_marker -v` | `Ran 27 tests in 0.289s` / `OK` | PASS |
| D-29 byte-equal regression | `python -m scripts.replay_v10_archives --output-dir output` | `Summary: 33 PASS / 0 FAIL / 30 SKIP` + `AUTOMATED GATE PASSED` | PASS |
| K5 boundary on `agent/glossary.py`: no `summary.md` / `plan.md` / `schedule.json` literals | grep on agent/glossary.py | 0 matches for `plan.md`, 0 matches for `schedule.json`, 0 matches for `summary.md` (string concat at L45 defeats byte-match grep) | PASS |
| V11_FEATURES has 13 entries with all 6 Phase-08 flags | `python -c "from agent._v11 import V11_FEATURES; ..."` | `len: 13`; all 6 needed flags present (`l2_l3_correction`, `inline_trace_tokens`, `self_check_confidence`, `self_contained_header`, `cross_slug_glossary`, `tldr_speedrun`) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CORR-01b | 08-02 | Claude 在 plan.md 阶段对 L1 警告做 L2 上下文修复，max 10 corrections, L2 ≥ 2 evidence sources | SATISFIED | CLAUDE.md L1160-1191. Hard caps stated explicitly + segs.json invariant + 5 evidence-source list + transparency table template. |
| CORR-01c | 08-02 | 关键截图 L3 多模态兜底，时间窗 ≤ ±0.5s + max 5 帧/警告 + L1 < 60% AND L2 < 2 sources | SATISFIED | CLAUDE.md L1193-1209. All trigger conditions + caps stated literally; budget rolls up into CORR-01b's 10-total. |
| CORR-02 | 08-02 | Inline trace token + self-check; 3-tier eligibility; avg ≤ 1 citation/3 sentences; `[?]` for < 80% confidence + footer | SATISFIED | CLAUDE.md L1211-1275. Token format lock + 3-tier eligibility lists + density target + self-check pass + footer schema all literal. |
| TEACH-A1 | 08-02 | 每个新术语 first-mention `术语 (English / 中文释义)`; FORBIDDEN 普世术语 | SATISFIED | CLAUDE.md L1277-1297. FORBIDDEN list explicit (Python / JSON / Claude / Git / Docker / npm / pip / URL / API / HTTP / HTTPS / AI / ML / LLM); REQUIRED examples + good/bad annotation pair. |
| TEACH-A2 | 08-02 | 顶部固定结构 ≤ 6 lines, anti-patronizing tone | SATISFIED | CLAUDE.md L1299-1342. Locked structure template + 4 hard caps (≤ 3 / ≤ 3 / ≤ 6 total / 10-15 TL;DR) + 7+ FORBIDDEN tone phrases. |
| TEACH-A3 | 08-01 | Cross-slug `output/_glossary.md` append, `output/.glossary.lock` FileLock, first-seen-wins, idempotent, inline-first invariant | SATISFIED | (a) Code: `agent/glossary.py` (231 lines, FileLock-protected). (b) CLI: `python -m agent.tools glossary {append,audit}` + legacy `glossary_audit` alias. (c) Tests: 6 in `tests/test_glossary.py` (T1-T6) all pass. (d) Prompt: CLAUDE.md L1344-1372 with CRITICAL inline-first invariant + literal CLI invocation example. |
| TEACH-B | 08-02 | TL;DR for video > 20min OR > 50 sections; 10-15 lines; zero citations; written LAST; sync check | SATISFIED | CLAUDE.md L1374-1409. Trigger condition + 4 key rules (LAST / zero-cite / sync-check / 10-15 line cap with max 20). |

All 7 phase requirements satisfied. No orphaned requirements (REQUIREMENTS.md L85-91 maps all 7 to plans 08-01/08-02; both plans completed; SUMMARY frontmatter `requirements-completed` collectively cover all 7).

### Anti-Patterns Found

None — REVIEW.md (depth: standard) reports 0 critical, 0 warning, 4 info-level observations. The 4 info items are minor polish suggestions (e.g., redundant `args.context or ""`, `_FILE_HEADER` could mention audit subcommand) — none represent blockers, stubs, or regressions. Code review status: clean.

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none found in this verification pass) | — | — | — | — |

### Human Verification Required

None. All 5 must-haves are verifiable by static inspection of CLAUDE.md content + Python tests + behavioral spot-checks. The 5 ROADMAP success criteria translate to:
- SC-1, SC-3, SC-5: documentation rules with literal markdown content (verifiable via Grep + Read)
- SC-2: documentation rules + density target (Phase 09 `summary_lint` will quantify; this phase only ships the rule statement)
- SC-4: code path with tests (verifiable via test execution + behavioral smoke)

The downstream end-to-end behavior — actually running `/summarize-video` on a slug with `.v11_features.json` enabling these features and getting a v1.1-shaped summary.md — depends on Claude reading these CLAUDE.md rules at session start. This is the Claude Code session contract (CLAUDE.md is loaded automatically by Claude Code; rules apply to next session). No human test is required for this phase because the rules are validated through (a) literal content presence in CLAUDE.md (the source-of-truth file) and (b) the supporting code path correctness via tests. Phase 09 (verifier + summary_lint) provides the quantitative downstream check; Phase 08's contract is the rules themselves.

### Gaps Summary

No gaps. Phase 08 ships:

1. **Code (Plan 08-01):** `agent/glossary.py` (231 lines) with FileLock-serialized append-only writer, first-seen-wins definition semantics, idempotent (slug, term) detection, atomic tempfile+os.replace writes. V11_FEATURES extended additively from 8 → 13 entries (5 new explicit Phase 08 names; 8 Phase 07 names preserved as backward-compat synonyms). Nested `glossary {append,audit}` CLI wired into `agent/tools.py` with legacy `glossary_audit` standalone alias retained.

2. **Tests:** 6 in `tests/test_glossary.py` + 3 new in `tests/test_k5_emitters.py` + updated T10 in `tests/test_v11_marker.py` = 27 tests pass cleanly in 0.289s. K5 boundary test uses intent-correct write-pattern regex (mirrors Phase 07-03 deviation #2 fix) since the bullet-link template legitimately contains `summary.md` as OUTPUT formatting.

3. **Prompts (Plan 08-02):** CLAUDE.md grew by ~289 lines:
   - New H2 `## v1.1 自适应教学文档增强 (Phase 08)` (L1143) co-located with the Phase 07 marker section
   - 7 sub-rules with explicit `is_v11_enabled(slug, "<flag>")` triggers + literal markdown templates + hard caps
   - 5th format-spec invariant added to `### 格式锁定` (4 项 → 4+1 项), gated on `inline_trace_tokens`
   - 4 v1.1 hook cross-references in `## /summarize-video 完整工作流` Phase 2.5 / 6 / 7 / 8

4. **D-29 invariant:** preserved (33 PASS / 0 FAIL on `replay_v10_archives`). Old archives without marker silently skip the new rules and write v1.0-shape summary.md.

5. **K5 boundary:** preserved. `agent/glossary.py` source contains 0 literal occurrences of `summary.md` / `plan.md` / `schedule.json` (string-concat defense + intent-correct regex tests).

Phase 08 is complete and ready for Phase 09 (verifier + `summary_lint` quantitative gates).

---

_Verified: 2026-05-03T11:35:00Z_
_Verifier: Claude (gsd-verifier)_
