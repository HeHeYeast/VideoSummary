---
phase: 12-archives-backfill-prompt-rule-search-cli
plan: 02
subsystem: knowledge-base
tags: [v1.2, knowledge-base, capstone, backfill, prompt-rule, claude-md, K5]

# Dependency graph
requires:
  - phase: 12-archives-backfill-prompt-rule-search-cli
    plan: 01
    provides: index backfill / write / rebuild / search / list CLIs + scan_archives_for_backfill module fn
  - phase: 11-per-slug-index-json-aggregator-phase76-hook
    provides: agent.index module + 8-field schema lock + rebuild_aggregator + Phase 7.6 prompt hook
  - phase: 10-topic-taxonomy-governance-bootstrap-cli
    provides: output/_topics.md Approved Taxonomy whitelist (24 leaves across 5 categories)
provides:
  - 33 archive index.json sidecars (28 BV* + 5 douyin_*) ready for Read output/.index.json by future Claude sessions
  - Top-level output/.index.json aggregator (33 entries) — single-Read knowledge-base entry point
  - CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 prompt rule (5 sub-blocks, 7 trigger phrases, 6 FORBIDDEN entries)
  - v1.2 milestone capstone — KB-12 / KB-13 / KB-14 / KB-15 satisfied (KB-MISC-01 from Plan 12-01)
affects:
  - Future /summarize-video runs: Phase 7.6 hook keeps adding new index.json entries; aggregator stays in sync
  - User natural-language recommendations: byte-equal trigger phrase + FIRST ACTION + format lock + anti-hallucination FORBIDDEN list

# Tech tracking
tech-stack:
  added: []  # Pure data + documentation; zero new third-party deps
  patterns:
    - "33-archive batch backfill via scratch script (scripts/_p12_compose.py): single Python file holds dict-of-dicts of 8-field per-slug payloads, writes one JSON per slug to /tmp scratch, then a shell loop pipes each file through python -m agent.tools index write --from-stdin --force. Pattern lets the human Claude executor commit per-slug composition decisions as a literal artifact (not buried in shell history)."
    - "Belt-and-suspenders aggregator rebuild after batch: each per-slug write triggers an aggregator rebuild inside FileLock window (Phase 11 generator side-effect), but Plan 12-02 ALSO runs index rebuild explicitly after the loop — confirms aggregator state is consistent regardless of generator behavior."
    - "Idempotent re-scan as completion proof: the final assertion that index backfill --all reports to_backfill=[] (with all 33 in skipped_existing) is the strongest possible 'I'm done' check — stronger than counting files."
    - "Output dir gitignore pattern: index.json files live under output/ which is fully gitignored (same isolation as 4 D-29 core artifacts). The work is recorded on the local filesystem, not in git history. Only the historical composition script (scripts/_p12_compose.py) is committed."

key-files:
  created:
    - .planning/phases/12-archives-backfill-prompt-rule-search-cli/12-02-SUMMARY.md
    - scripts/_p12_compose.py  # Historical record of per-slug composition decisions
    - output/.index.json  # gitignored — 33-entry aggregator
    - output/<slug>/index.json  # 33 sidecars; gitignored
  modified:
    - CLAUDE.md  # +64 lines: ## v1.2 知识库自然语言推荐入口 H2

key-decisions:
  - "Scope expanded from spec'd 17 to actual 33 archives discovered by index backfill --all. Plan spec said >=17; actual scan found 28 BV* + 5 douyin_* = 33 healthy archives (each has summary.md + meta.json present). Backfilled all 33 in a single pass — no reason to artificially limit to 17 when CLI emits the real list."
  - "Per-slug payload composition: Claude reads triage data (title + duration + first-line H2 headers) for ALL archives FIRST, THEN composes per-slug payloads in a single 33-entry dict in scripts/_p12_compose.py. The interface-first cadence (per Plan 12-02 Task 1 read_first.6) avoids per-slug topic drift where slug 1 picks AI-Tooling for Claude Code content but slug 2 picks Claude-Code for the same domain. All 33 payloads use exact-leaf names from output/_topics.md Approved Taxonomy."
  - "Mode inference fallback to replicate-guide when ambiguous (per CLAUDE.md ### 模式分类). 23/33 = 70% are replicate-guide which matches the 17-archive corpus distribution baseline UP-built has historically authored. Minority modes: 5 extension-applications (横向罗列 + 边界对比 / 比较多场景), 4 concept-explanation (无代码 hands-on / 原理为主), 1 interview-distillation (douyin_karpathy_llm_wiki — UP 主对 Karpathy gist 的判断 + 反方三连击)."
  - "Per-slug `start` timestamp policy: short videos (< 3 min, 17 of 33) often use [MM:SS] format which converts to seconds < 180 — but conversion is OK because chapter ordering is preserved. For deeper alignment, longer videos (> 30 min, e.g. BV1rsd7BsEnA LoRA tutorial 33:49) use the MM:SS extracted from H2 line directly. start=0 is used as fallback when summary.md H2 lacks an explicit timestamp prefix (per Plan 12-01 read_first guidance about Phase 11 D-04 chapter timestamp cross-ref)."
  - "Zero pending topics — all 33 archives' topic vectors fit existing _topics.md Approved Taxonomy (5 categories / 24 leaves shipped in Phase 10). This validates Phase 10's taxonomy completeness for the v1.0/v1.1 archive corpus. Future archive types (e.g. video editing tutorials, language learning) may need new topics added via Phase 11 generator's append_pending side-effect."

metrics:
  duration_human_minutes: ~25  # context read + 33-entry payload composition + CLAUDE.md edit + 2 atomic commits + verification
  completed_date: 2026-05-03
  archives_backfilled: 33  # spec >=17; actual 33
  total_aggregator_entries: 33
  pending_topics_appended: 0
  failed_slugs: 0
  d29_replay_pass: 33
  d29_replay_fail: 0
  d29_replay_skip: 30  # non-archive dirs lacking summary.md
  test_count: 297  # unchanged from Plan 12-01 (Plan 12-02 is data + docs only, no Python code change)
  claudemd_lines_added: 64
  commits_count: 3  # Task 1 + Task 2 + this SUMMARY commit
---

# Phase 12 Plan 02: 17-archives-backfill-prompt-rule-search-cli — v1.2 Capstone Summary

The v1.2 milestone capstone: 33 archive index.json sidecars + top-level aggregator + CLAUDE.md natural-language recommendation prompt rule. Future Claude sessions can `Read output/.index.json` once and have full knowledge-base concept overview; user queries containing one of 7 byte-equal trigger phrases ('推荐', '相关', '我之前看过', '学过', '找一下我', '哪些视频', '类似查询意图') route to a byte-locked recommendation flow with anti-hallucination guards.

## What Shipped

### 33 archive index.json sidecars

| | Count | Examples |
|---|---|---|
| Total backfilled | 33 | (full list below) |
| BV* (B 站) | 28 | BV132wizyEEB, BV1HG9JBsEPK, BV1rsd7BsEnA, ... |
| douyin_* | 5 | douyin_ai_kb, douyin_claude_code_hooks, douyin_karpathy_llm_wiki, douyin_trae_ai, douyin_zidan_bojirouxunlian |
| Pending topics | 0 | All matched output/_topics.md Approved Taxonomy |
| Failed slugs | 0 | All archives healthy (KB-13 error tolerance untriggered) |

**Mode distribution:**

| Mode | Count | % |
|---|---|---|
| replicate-guide | 23 | 70% |
| extension-applications | 5 | 15% |
| concept-explanation | 4 | 12% |
| interview-distillation | 1 | 3% |

**Topic distribution (top 10 most-referenced approved leaves):**

| Topic | Count |
|---|---|
| Godot | 15 |
| Pixel-Art | 12 |
| Game-Dev | 12 |
| AI-Art-Generation | 10 |
| AI-Tooling | 7 |
| TileMap | 4 |
| Sprite-Animation | 4 |
| FrameRonin | 3 |
| LLM-Wiki | 3 |
| Procedural-Generation | 2 |

Other leaves used at least once: Nano-Banana / Claude-Code / LLM-Concepts / Codex / MCP / Game-AI-NPC / ComfyUI / Custom-Engine / LoRA / RAG / TRAE-SOLO / Compound-Engineering / Fitness.

**Full slug list (lex-sorted):**

```
BV11JQBByE13              | mode=replicate-guide        | topics=[Pixel-Art, AI-Art-Generation]
BV132wizyEEB              | mode=replicate-guide        | topics=[Pixel-Art, AI-Art-Generation, Godot]
BV15S9FBtEFm              | mode=extension-applications | topics=[Game-Dev, Godot]
BV17WQuBJEzZ              | mode=replicate-guide        | topics=[Pixel-Art, FrameRonin, AI-Art-Generation]
BV1C9QCBdE1U              | mode=replicate-guide        | topics=[Godot, Game-Dev]
BV1EWwXzvE23              | mode=replicate-guide        | topics=[Pixel-Art, AI-Art-Generation, Godot]
BV1HG9JBsEPK              | mode=replicate-guide        | topics=[TileMap, Procedural-Generation, Pixel-Art, Godot]
BV1Kk9MBNEgV              | mode=replicate-guide        | topics=[AI-Art-Generation, Pixel-Art]
BV1RA9uBSEh3              | mode=extension-applications | topics=[Game-Dev, Codex, AI-Tooling]
BV1RXdZBtEKN              | mode=replicate-guide        | topics=[Pixel-Art, FrameRonin, Godot]
BV1SPB6BxE2t              | mode=replicate-guide        | topics=[Nano-Banana, AI-Art-Generation, Game-Dev]
BV1TrP6zHETD              | mode=extension-applications | topics=[Godot, Game-Dev]
BV1W3PyztE4q              | mode=replicate-guide        | topics=[MCP, Godot, AI-Tooling]
BV1YTQQBcEWs              | mode=replicate-guide        | topics=[Game-AI-NPC, Godot, Game-Dev]
BV1dQPezJEmG              | mode=replicate-guide        | topics=[Sprite-Animation, Pixel-Art, AI-Art-Generation]
BV1dUDLBaEeb              | mode=concept-explanation    | topics=[Procedural-Generation, TileMap, Game-Dev, Godot]
BV1f1Q2BfEoN              | mode=replicate-guide        | topics=[Sprite-Animation, Pixel-Art, AI-Art-Generation]
BV1f2WZzzEMp              | mode=replicate-guide        | topics=[Nano-Banana, ComfyUI, AI-Art-Generation]
BV1fLoKBREAN              | mode=replicate-guide        | topics=[Godot, TileMap, Game-Dev]
BV1hUAMzYEc8              | mode=replicate-guide        | topics=[FrameRonin, Pixel-Art]
BV1jXXaBQE1R              | mode=concept-explanation    | topics=[Custom-Engine, Game-Dev]
BV1p2c6zTEn2              | mode=replicate-guide        | topics=[Sprite-Animation, Pixel-Art, Godot]
BV1qQPeznE5H              | mode=replicate-guide        | topics=[Godot, Pixel-Art, Sprite-Animation]
BV1rsd7BsEnA              | mode=replicate-guide        | topics=[LoRA, AI-Art-Generation]
BV1s6rDBpEvo              | mode=replicate-guide        | topics=[Godot, Game-Dev]
BV1sXcqziE4W              | mode=extension-applications | topics=[AI-Tooling, Game-Dev, Claude-Code]
BV1wu9MBZEbU              | mode=replicate-guide        | topics=[AI-Tooling]
BV1x31TYUEbc              | mode=replicate-guide        | topics=[Godot, Game-Dev, TileMap]
douyin_ai_kb              | mode=concept-explanation    | topics=[LLM-Wiki, LLM-Concepts, AI-Tooling]
douyin_claude_code_hooks  | mode=extension-applications | topics=[Claude-Code, AI-Tooling]
douyin_karpathy_llm_wiki  | mode=interview-distillation | topics=[LLM-Wiki, LLM-Concepts, RAG]
douyin_trae_ai            | mode=replicate-guide        | topics=[TRAE-SOLO, Compound-Engineering, AI-Tooling, LLM-Wiki]
douyin_zidan_bojirouxunlian | mode=concept-explanation  | topics=[Fitness]
```

### CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2

Inserted between `## v1.1 校对自动化 (Phase 09)` and `## /summarize-video 完整工作流`. 64 lines added. Structure:

| Sub-block | Purpose |
|---|---|
| `### 触发 phrase 锁` | 7 byte-equal literal phrases route to recommendation flow |
| `### FIRST ACTION` | `Read output/.index.json` mandate; missing-file fallback to user hint |
| `### 推荐回复格式锁` | 3-line strict structure per recommendation (slug+title / tldr blockquote / chapter entries) |
| `### Byte-equal example` | Concrete example for "推荐学习 LLM Wiki 范式相关的视频" → recommends douyin_karpathy_llm_wiki + douyin_trae_ai |
| `### Anti-hallucination FORBIDDEN list` | 6 FORBIDDEN entries: no fake slugs / no fabricated content / no D-29 core file edits / no `<thinking>` / max 5 / must Read first |

Trigger phrases byte-equal verified (each grep returns >= 1):
- `'推荐'` / `'相关'` / `'我之前看过'` / `'学过'` / `'找一下我'` / `'哪些视频'` / `'类似查询意图'`

## Smoke Tests (Step D)

```bash
# 1. Aggregator integrity
$ python -c "import json; print(len(json.load(open('output/.index.json'))))"
33

# 2. Karpathy search
$ python -m agent.tools index search "Karpathy" --output-dir output --json
{
  "query": "Karpathy",
  "matches": [
    {"slug": "douyin_ai_kb", "matched_fields": ["title", "keywords", "tldr_oneliner", "chapters[1].title", "chapters[1].excerpt"], ...},
    {"slug": "douyin_karpathy_llm_wiki", "matched_fields": ["title", "keywords", "tldr_oneliner", "chapters[5].title"], ...}
  ]
}

# 3. LLM-Wiki topic filter
$ python -m agent.tools index list --topic "LLM-Wiki" --output-dir output --json
[douyin_ai_kb, douyin_karpathy_llm_wiki, douyin_trae_ai]   # 3 entries

# 4. Idempotent re-scan
$ python -m agent.tools index backfill --all --output-dir output --json
to_backfill=0 skipped_existing=33 failed=0
```

## Key Decisions

1. **Scope expanded from 17 to 33.** The plan said `>= 17` but the actual `index backfill --all` scan found 33 healthy archives (28 BV* + 5 douyin_*). Backfilled all 33 in one pass — no reason to artificially limit when each is individually 1-2 minutes of payload composition.

2. **Interface-first cadence: triage all 33 archives BEFORE composing any single payload.** Read titles + first H2 headers + duration for ALL archives in 3 batched commands first, building a global topic-distribution mental map. THEN compose 33-entry dict-of-dicts in a single Python script `scripts/_p12_compose.py`. This avoids per-slug topic drift (where slug 1 picks AI-Tooling for Claude Code content but slug 2 picks Claude-Code for the same domain — instead, the global view fixes "Claude-Code is the Claude Code Code-related content leaf, AI-Tooling is the broader category, prefer the leaf").

3. **Mode inference fallback to replicate-guide.** 23/33 = 70% replicate-guide matches the 17-archive baseline. Concept-explanation only when "为什么 X" / no code fences / no step numbers (douyin_ai_kb LLM Wiki concept; BV1jXXaBQE1R 引擎设计; BV1dUDLBaEeb 程序化算法概念; BV1zidan 健身概念). Extension-applications when 3+ scenarios in parallel + comparison table (BV1TrP6zHETD Godot 4.7 9 features; BV1RA9uBSEh3 Codex/Skill 4 stages; BV1sXcqziE4W 12hr 多 Agent stack; BV15S9FBtEFm 30day 复盘; douyin_claude_code_hooks 4 hook types). Interview-distillation only for douyin_karpathy_llm_wiki (UP 对 Karpathy gist 的判断 + 反方三连击 + 引文 heavy).

4. **Zero pending topics validates Phase 10 taxonomy completeness.** All 33 archives' topic vectors fit the 24-leaf approved taxonomy (Phase 10 ship). Future archive types may need new topics added via the Phase 11 generator's `pending: <name>` side-effect.

5. **Per-slug `start` timestamp uses MM:SS-as-seconds for short videos.** Short videos (< 3 min, ~50% of corpus) use [MM:SS] format which the conversion treats as MM*60+SS — preserves chapter ordering even though the absolute scale is < 180. For longer videos (LoRA tutorial 33:49, douyin_karpathy_llm_wiki 4:02, douyin_trae_ai 4:12), MM:SS is extracted directly. `start=0` fallback for archives where summary.md H2 lacks an explicit timestamp prefix (covers ~60% of the index entries — H2-only summaries that don't prefix with timestamps).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking] /tmp path resolves to D:\\tmp on Windows Python**

- **Found during:** Task 1 first batch CLI loop
- **Issue:** Python's `Path('/tmp/p12_payloads')` on Windows resolves to `D:\\tmp\\p12_payloads` (cwd drive root + literal tmp). But Bash's `for slug in ...; do ... < /tmp/p12_payloads/$slug.json; done` reads `/tmp/p12_payloads/` literal which is cygwin/MSYS POSIX root, not the same path. First batch failed with `No such file or directory`.
- **Fix:** Switched the shell loop to use `D:/tmp/p12_payloads/$slug.json` (cross-tool resolved Windows path). Files were on disk; only the Bash path needed adjustment.
- **Files modified:** None (in-session command fix only)
- **Commit:** N/A (no file change required)

**2. [Rule 3 — Scope clarification] Plan said `git add output/...` but output/ is fully gitignored**

- **Found during:** Task 1 commit prep
- **Issue:** Plan task 1 spec said `git add output/.index.json output/*/index.json output/_topics.md`. But `output/` is fully gitignored per `.gitignore` (with exceptions only for `.token_budget.json` files added with `-f` historically and `_topics.md` whitelisted explicitly). The 33 new index.json files cannot be added without `-f`.
- **Resolution:** This is correct by-design — index.json files share the gitignore isolation pattern as 4 D-29 core artifacts (summary.md / segs.json / paragraphs.json / meta.json all gitignored). The work is recorded on the local filesystem, not in git history. Only `scripts/_p12_compose.py` (the historical record of payload composition decisions) was committed.
- **Files modified:** scripts/_p12_compose.py (committed); _topics.md unchanged (zero pending appends)
- **Commit:** c9f9dfc (Task 1)

### Auth Gates

None.

## Self-Check Results

- **Aggregator entry count:** `python -c "import json; print(len(json.load(open('output/.index.json',encoding='utf-8'))))"` → 33 ✓
- **Idempotent re-scan:** `index backfill --all --json` → `to_backfill=0 skipped_existing=33 failed=0` ✓
- **Karpathy search hits 2 archives:** `index search "Karpathy"` → 2 matches (douyin_ai_kb + douyin_karpathy_llm_wiki) ✓
- **LLM-Wiki topic filter hits 3 archives:** `index list --topic "LLM-Wiki"` → 3 entries (douyin_ai_kb + douyin_karpathy_llm_wiki + douyin_trae_ai) ✓
- **CLAUDE.md H2 anchor:** `grep -c "^## v1.2 知识库自然语言推荐入口" CLAUDE.md` → 1 ✓
- **CLAUDE.md 5 sub-blocks:** 5 ### sub-headers grep'd ✓
- **CLAUDE.md 7 trigger phrases:** all 7 byte-equal literals grep'd, each count >= 1 ✓
- **CLAUDE.md FORBIDDEN list:** 15 FORBIDDEN occurrences (>=6 required) ✓
- **D-29 byte-equal close gate:** `python scripts/replay_v10_archives.py` → `Summary: 33 PASS / 0 FAIL / 30 SKIP` ✓
- **Full test suite:** `python -m unittest discover tests` → `Ran 297 tests, OK (skipped=2)` ✓

## Self-Check: PASSED

All claims in this SUMMARY verified:

- 33 entries in output/.index.json (filesystem check)
- All 33 per-slug index.json sidecars exist (filesystem checks during write loop confirmed `action: written` for each)
- CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 in place (grep)
- 5 sub-blocks present in new H2 (grep)
- 7 byte-equal trigger phrases present (grep)
- D-29 33 PASS / 0 FAIL preserved (replay output)
- 297 tests pass, 0 regressions from Plan 12-01 baseline (test runner output)

## Phase 12 Acceptance Gate

| Criterion | Status |
|---|---|
| Backfill produces ≥ 17 entries | PASSED (33 entries) |
| CLAUDE.md `## v1.2 知识库自然语言推荐入口` H2 inserted | PASSED |
| 5 sub-blocks present (触发 phrase 锁 / FIRST ACTION / 推荐回复格式锁 / Byte-equal example / Anti-hallucination FORBIDDEN list) | PASSED (grep -c == 5) |
| 7 byte-equal trigger phrases present | PASSED |
| 6+ FORBIDDEN entries in anti-hallucination list | PASSED (15 occurrences total in CLAUDE.md, 6 unique in new H2) |
| D-29 byte-equal replay 0 FAIL | PASSED (33 PASS / 0 FAIL / 30 SKIP) |
| All 297 tests pass | PASSED (no regressions) |
| KB-12 (backfill --all) | SATISFIED |
| KB-13 (error tolerance + 6 队列 left to Phase 7.6) | SATISFIED (0 failed in healthy 33; 6-queue Phase 7.6 hook from Plan 11-02) |
| KB-14 (CLAUDE.md prompt rule) | SATISFIED |
| KB-15 (anti-hallucination FORBIDDEN list) | SATISFIED |

## Deferred Manual UAT (per CONTEXT D-09)

E2E recommendation behavior verification requires a real Claude session — cannot be unit-tested. Same pattern as v1.1 KB-02 + P-09 token budget gate. Defer to milestone close gate or future user session:

```
User: "推荐学习 LLM Wiki 范式相关的视频"
Expected behavior:
  1. Claude reads output/.index.json FIRST (no grep, no clarification ask)
  2. Returns top-3 matches: douyin_karpathy_llm_wiki, douyin_ai_kb, douyin_trae_ai
  3. Each recommendation in 3-line locked format:
     - **<slug>**: <title> — 共享 <signal>
     - > <tldr_oneliner>
     - 1-3 chapter entries [HH:MM:SS] <title>
  4. No fabricated slugs / no <thinking> / no D-29 core file edits
  5. If query has no match: tells user "在已总结的 33 个视频里没找到与 X 直接相关的内容"
```

This UAT is documented in CONTEXT D-09 and is **NOT** a phase-blocking gate (per D-09.4 — same pattern as v1.1 P-09 token budget which was also deferred manual UAT).

## Commits

- `c9f9dfc` — feat(12-02): backfill 33 archives with index.json (KB-12, KB-13)
- `13bba44` — feat(12-02): CLAUDE.md /v1.2 知识库自然语言推荐入口/ H2 prompt rule (KB-14, KB-15)
- (this commit) — docs(12-02): complete v1.2 capstone — backfill + prompt rule + close gate

Plan 12-02 duration: ~25 minutes. 3 atomic commits, 2 deviations both Rule 3 (blocking, no architectural change).
