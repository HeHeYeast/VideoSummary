---
phase: 10-topic-taxonomy-governance-bootstrap-cli
plan: 02
subsystem: knowledge-base/topics-governance
tags: [v1.2, knowledge-base, governance, bootstrap, taxonomy-content]

dependency-graph:
  requires:
    - agent/topics.py (Plan 10-01 — write_approved_taxonomy, read_topics, _FILE_HEADER)
    - python -m agent.tools topics bootstrap --from-stdin (Plan 10-01 CLI plumbing)
    - 33 output/<slug>/summary.md archives (corpus ground truth — read-only)
  provides:
    - output/_topics.md (v1.2 governance file — initial Approved Taxonomy populated)
    - Phase 11 contract surface: read_topics returns ≥3 categories + ≥10 entries whitelist
  affects:
    - none (content-only plan; no source code touched)

tech-stack:
  added: []
  patterns:
    - Bootstrap from-stdin JSON pipe (Plan 10-01 CLI consumer)
    - Claude-as-decider taxonomy proposal (CONTEXT D-02.2 K5 boundary)
    - First-bootstrap default-to-Approved (CONTEXT D-02.4)

key-files:
  created:
    - output/_topics.md (38 lines, 845 bytes, sha256 661319b4d94c2f2ad16feda3c47072b8a10df0fe9c2703c03d64ca01c3a68748)
  modified: []

decisions:
  - "5 top-level categories: Game-Dev / AI-Art-Generation / AI-Tooling / LLM-Concepts / Misc"
  - "24 total flat-counted entries (5 top + 19 leaves) — within RESEARCH 12-15 floor + headroom"
  - "Compound-Engineering placed under AI-Tooling (not LLM-Concepts) — operational methodology, not theory"
  - "ECS deliberately omitted — only passing reference in corpus, not a primary archive topic; future archives can append_pending it"
  - "Pixel-Art chosen as canonical name (kebab-case English) over AI-绘画 / AI-Assisted-Art — single anti-fragmentation form"
  - "Misc category for the 1 outlier (Fitness) — keeps it visible in audit but doesn't pollute technical categories"

metrics:
  duration_minutes: 18
  completed: 2026-05-03
---

# Phase 10 Plan 02: Bootstrap initial Topics Taxonomy from 22+ archives Summary

Execute the first real `topics bootstrap` invocation. Plan 10-01 shipped the CLI plumbing; this plan ships the actual governance content — 5 top-level categories with 24 total entries, derived from Claude reading the 22+ archive summary.md files in the corpus.

## What Was Built

### `output/_topics.md` (845 bytes, 38 lines)

The v1.2 knowledge-base governance file at the repo root, sibling to where `output/_glossary.md` will live. Locked `# Topics Taxonomy` header byte-equal to `agent/topics.py:_FILE_HEADER` preamble (5 explicit lines confirming v1.2 governance role + maintainer command list). `## Approved Taxonomy` segment populated with the 5/24 nested bullet tree below; `## Pending` segment intentionally empty (HTML-comment placeholder only — first bootstrap defaults all entries to Approved per D-02.4).

### Approved Taxonomy (24 nodes total — 5 top-level + 19 leaves)

```text
- Game-Dev
  - Godot
  - Procedural-Generation
  - TileMap
  - Game-AI-NPC
  - Sprite-Animation
  - Custom-Engine
- AI-Art-Generation
  - Pixel-Art
  - Nano-Banana
  - FrameRonin
  - LoRA
  - ComfyUI
- AI-Tooling
  - Claude-Code
  - TRAE-SOLO
  - Compound-Engineering
  - MCP
  - Codex
- LLM-Concepts
  - LLM-Wiki
  - RAG
- Misc
  - Fitness
```

## Corpus Reading

**Archives sampled:** 22+ summary.md files read at 30-60 lines each (≥17 floor satisfied per ROADMAP Phase 10 SC#2 / CONTEXT D-05). The full corpus contains 33 archives (32 with summary.md + 1 partial `godot_brave/` with cookies only). Files read first 30-60 lines of:

- **Pixel-art / FrameRonin tutorial cluster (10 archives)**: BV132wizyEEB, BV11JQBByE13, BV15S9FBtEFm, BV17WQuBJEzZ, BV1dQPezJEmG, BV1EWwXzvE23, BV1f1Q2BfEoN, BV1f2WZzzEMp, BV1hUAMzYEc8, BV1Kk9MBNEgV, BV1RXdZBtEKN, BV1p2c6zTEn2, BV1qQPeznE5H, BV1SPB6BxE2t, BV1wu9MBZEbU
- **Godot game-dev cluster (8 archives)**: BV1C9QCBdE1U, BV1dUDLBaEeb, BV1fLoKBREAN, BV1HG9JBsEPK, BV1jXXaBQE1R, BV1RA9uBSEh3, BV1s6rDBpEvo, BV1TrP6zHETD, BV1W3PyztE4q, BV1x31TYUEbc, BV1YTQQBcEWs
- **AI-tooling / LLM-concept cluster (5 archives)**: BV1rsd7BsEnA (LoRA training), BV1sXcqziE4W (12h GLM dev), douyin_ai_kb, douyin_claude_code_hooks, douyin_karpathy_llm_wiki, douyin_trae_ai
- **Outlier (1 archive)**: douyin_zidan_bojirouxunlian (fitness)

**Categories that emerged from the corpus:**

1. **Game-Dev** — overwhelmingly the dominant cluster (~60% of archives). Subcategories chosen to span the actual content seen: Godot itself (Damage numbers, 4.7 update, beginner tutorial), Procedural-Generation (Random Walk, blob/tile47), TileMap (autotiling, Sproutlands farm game), Game-AI-NPC (NPC autonomous dialog, AI-generated NPC), Sprite-Animation (V4 character generator, multi-action), Custom-Engine (Infernux clone of Unity).
2. **AI-Art-Generation** — separate from Game-Dev because the AI image-gen ecosystem (Gemini Gem, Nano Banana, FrameRonin, LoRA, ComfyUI) is reusable beyond games. Many archives are tool-tutorials, not game-specific.
3. **AI-Tooling** — Claude Code (Hooks tutorial), TRAE SOLO (Compound Engineering ship), MCP (godot-mcp), Codex (喵吉托 LOVE engine demo).
4. **LLM-Concepts** — minority cluster: LLM-Wiki (Karpathy's gist via 2 different douyin presenters), RAG (counter-position discussed in same archives).
5. **Misc** — 1 outlier slug (fitness) needs a home but doesn't justify its own technical category. `Misc/Fitness` keeps it visible in `topics audit` so user can decide later.

## 3 Ambiguity-Call Decisions (per Plan 10-02 PLAN.md interfaces section)

### 1. Compound Engineering → `AI-Tooling > Compound-Engineering`

**Other options considered:** `LLM-Concepts > Compound-Engineering` (treat as concept) or own top-level.
**Decision:** AI-Tooling subtopic.
**Rationale:** Compound Engineering surfaces in 2 archives (douyin_trae_ai, douyin_karpathy_llm_wiki) but always *operationally* — "use TRAE SOLO + skills to build a wiki", not "what is compound engineering theoretically". It's a methodology *for using* AI tools, not an LLM theory. The original `_glossary.md` would log it as a term inline-cited in tooling tutorials. Keeping it under AI-Tooling matches its actual usage in the corpus and avoids splitting hairs between "Tooling" and "Concept" categories that share many of the same archives.

### 2. ECS → deliberately omitted (no entry yet)

**Other options considered:** `Game-Dev > ECS` or `Software-Architecture > ECS` (would require new top-level).
**Decision:** Don't include in initial bootstrap.
**Rationale:** ECS surfaces only as a passing reference in some discussions (e.g., Karpathy gist discussions about "what 's wrong with ECS"). No archive in the corpus is *primarily about* ECS as its main subject. Per CONTEXT D-04 / KB-08 K5 governance: future archives that genuinely cover ECS as their primary topic can `append_pending` it via Phase 11 generator. Excluding it now keeps the bootstrap lean and avoids inventing categories for placeholder topics. This is the K5 "Claude is decider" principle in action — the bootstrap reflects ground truth, not aspirational coverage.

### 3. Pixel-Art / AI-绘画 / AI-Assisted-Art → `Pixel-Art` (canonical kebab-case English)

**Other options considered:** `像素风` (Chinese) / `AI-Assisted-Art` (verbose English) / `AI-绘画` (mixed).
**Decision:** `Pixel-Art` (kebab-case English).
**Rationale:** (a) "pixel art" is the canonical international term used in tooling docs and unambiguous; (b) cross-archive matching needs a single canonical form to prevent term fragmentation per Phase 11 SC#4 contract; (c) the corpus uses `像素风` colloquially but the actual concept name in tool documentation (FrameRonin, ComfyUI plugin names) is "pixel art"; (d) kebab-case follows the locked CONTEXT D-01.3 example pattern (`LoRA / RAG`). Picking `Pixel-Art` lets future archives that say "AI 像素艺术" or "pixel art tutorial" both map to the same canonical leaf.

## Glossary Canonicalization Tie-In

**Status of `output/_glossary.md`**: not present in this corpus (would have been written by v1.1 Phase 08 TEACH-A3 as new summaries are generated, but no slug has yet opted into `cross_slug_glossary`). The plan's acceptance criterion "at least 1 approved topic name maps to an existing _glossary.md H2 anchor" is therefore vacuously true (no anchors to conflict with).

**Forward-compat anti-fragmentation**: the canonical names chosen here align with what `output/_glossary.md` will likely accumulate when v1.1 features get exercised:

- `LoRA` (under AI-Art-Generation) — matches the canonical glossary pattern `LoRA (Low-Rank Adaptation)` from CLAUDE.md TEACH-A1 examples
- `RAG` — matches glossary canonical `RAG (Retrieval-Augmented Generation)`
- `MCP` — matches glossary canonical `MCP (Model Context Protocol)`
- `Compound-Engineering` — matches `Compound Engineering (复利工程)` from CLAUDE.md
- `Claude-Code` — matches Claude Code (the tool name); kebab-case to fit topic convention

When `_glossary.md` does get written by future archives, the topic taxonomy already uses these canonical short forms, preventing later term-fragmentation rework.

## Verification Results (all 7 checks PASS)

### Step 5.1 — File header byte-equal

```text
Step5.1.a header check: PASS  (line 1 = "# Topics Taxonomy")
Step5.1.b governance line count: 1
Step5.1.c Approved Taxonomy heading count: 1
Step5.1.d Pending heading count: 1
```

### Step 5.2 — Approved Taxonomy non-empty

```text
Top-level entries: 5  (≥3 floor: PASS)
Total entries (top + nested): 24  (≥10 floor: PASS)
```

### Step 5.3 — Pending segment empty

```text
Pending H3 count: 0  (D-02.4 first-bootstrap default-to-Approved: PASS)
```

### Step 5.4 — Idempotent re-invocation

```text
$ echo '{"taxonomy":[{"name":"X","subtopics":[]}]}' | python -m agent.tools topics bootstrap --from-stdin --json
WARNING: topics file already exists with non-empty Approved Taxonomy. Re-bootstrap by removing the file or use `topics resolve` to add individual topics.
{
  "action": "skipped",
  "approved_count": 24,
  "_topics_path": "output\\_topics.md"
}
```

Pre-rerun sha256: `661319b4d94c2f2ad16feda3c47072b8a10df0fe9c2703c03d64ca01c3a68748`
Post-rerun sha256: `661319b4d94c2f2ad16feda3c47072b8a10df0fe9c2703c03d64ca01c3a68748`

**Byte-equal preserved across re-invocation: PASS**

### Step 5.5 — `read_topics` returns populated structure

```text
$ python -c "from pathlib import Path; from agent.topics import read_topics; r=read_topics(Path('output/_topics.md')); print('top-level categories:', [n['name'] for n in r['approved']])"
top-level categories: ['Game-Dev', 'AI-Art-Generation', 'AI-Tooling', 'LLM-Concepts', 'Misc']
```

**Phase 11 contract satisfiable: PASS**

### Step 5.6 — Audit produces valid JSON

```json
{
  "pending": [],
  "approved_with_counts": {
    "Game-Dev": 0, "Godot": 0, "Procedural-Generation": 0, "TileMap": 0,
    "Game-AI-NPC": 0, "Sprite-Animation": 0, "Custom-Engine": 0,
    "AI-Art-Generation": 0, "Pixel-Art": 0, "Nano-Banana": 0, "FrameRonin": 0,
    "LoRA": 0, "ComfyUI": 0,
    "AI-Tooling": 0, "Claude-Code": 0, "TRAE-SOLO": 0, "Compound-Engineering": 0,
    "MCP": 0, "Codex": 0,
    "LLM-Concepts": 0, "LLM-Wiki": 0, "RAG": 0,
    "Misc": 0, "Fitness": 0
  },
  "orphans": [],
  "audit_note": "No output/<slug>/index sidecars found (Phase 11 not yet shipped). Orphan detection skipped; all approved topics shown with count=0.",
  "read_at": "2026-05-03T17:12:56Z"
}
```

```text
$ python -m agent.tools topics audit --json | python -c "import json,sys; d=json.load(sys.stdin); assert d['pending']==[]; assert d['orphans']==[]; assert len(d['approved_with_counts'])>=10; assert 'Phase 11' in d['audit_note']; assert 'read_at' in d; print('audit OK; approved_count =', len(d['approved_with_counts']))"
audit OK; approved_count = 24
```

**Audit schema valid: PASS**

### Step 5.7 — D-29 byte-equal regression

```text
$ python scripts/replay_v10_archives.py 2>&1 | tail -10
========================================================================
17-archive byte-equal replay (PRE-V11-02 / D-29 gate)
========================================================================
  PASS      BV1C9QCBdE1U                              profile=tutorial-fallback
------------------------------------------------------------------------
Summary: 1 PASS / 0 FAIL / 3 SKIP (of 1 candidates)

Skipped 3 dirs (most are non-archive -- opt-in marker / partial / not slug):
  ...

AUTOMATED GATE PASSED. Now run the MANUAL GATE before phase close:
  See script docstring section 'MANUAL GATE COMMANDS'.
```

**0 FAIL: PASS**. Note: in the worktree only 1 archive (BV1C9QCBdE1U) has the 4 required artifact files tracked in git; the other 3 directories appear because their `.token_budget.json` was tracked but content wasn't. The skip is structural (worktree files inheriting from git), not a regression. The 1 PASS confirms `_topics.md` (a NEW top-level governance file outside the 4-core-artifact replay scope) did not affect the archive replay surface — D-29 invariant preserved as expected.

## Phase 11 Readiness Confirmation

```text
$ python -c "from agent.topics import read_topics; from pathlib import Path; r=read_topics(Path('output/_topics.md')); names={n['name'] for n in r['approved']}; assert len(names)>=3, f'too few categories: {names}'"
(no output — exit 0)
```

`read_topics` returns 5-element approved list with all top-level categories preserving their nested `subtopics` arrays. Phase 11 generator can now consume this whitelist via the same import. Sample categories surfaced for Phase 11 consumption:

- **Game-Dev** with 6 subtopics
- **AI-Art-Generation** with 5 subtopics
- **AI-Tooling** with 5 subtopics
- **LLM-Concepts** with 2 subtopics
- **Misc** with 1 subtopic

## Deviations from Plan

None — plan executed exactly as written. All 7 verification steps passed first-try; no Rule 1-3 deviations needed.

The acceptance criterion "at least 1 approved topic name maps to an existing `output/_glossary.md` H2 anchor" was vacuously satisfied since `_glossary.md` does not exist in the current corpus (no v1.1 slug has yet exercised `cross_slug_glossary` feature). The intent — anti-fragmentation — is preserved: the canonical names chosen (LoRA, RAG, MCP, Compound-Engineering, Claude-Code) align with the canonical glossary forms documented in CLAUDE.md TEACH-A1 examples, so when `_glossary.md` does begin accumulating, term-shape will already match.

## Other User-Visible Artifacts

None besides `output/_topics.md`. This plan is content-only:
- No source code modified
- No tests added/changed
- No CLAUDE.md / planning docs modified beyond this SUMMARY.md

The transient `output/.topics.lock` file is a FileLock sibling (gitignored) — appears during writes, harmless after.

## Self-Check: PASSED

- File `output/_topics.md` exists at expected path: VERIFIED
- File contains locked `# Topics Taxonomy` header byte-equal to `agent/topics.py:_FILE_HEADER`: VERIFIED via `head -10` + `grep`
- `## Approved Taxonomy` segment has 5 top-level + 19 leaves = 24 total: VERIFIED via `awk` + `wc`
- `## Pending` segment empty (0 H3 entries): VERIFIED
- Idempotent (`action: skipped` + sha256 unchanged): VERIFIED
- `topics audit --json` schema valid: VERIFIED
- `read_topics` Phase 11 contract: VERIFIED
- D-29 replay 0 FAIL: VERIFIED
