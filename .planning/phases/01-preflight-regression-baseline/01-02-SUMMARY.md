---
phase: 01-preflight-regression-baseline
plan: 02
subsystem: artifact-loading
tags: [schema-versioning, loader-tolerance, single-landing-point, backward-compat, stdlib-only]

requires:
  - phase: 01-preflight-regression-baseline
    plan: 01
    provides: 12 frozen baseline artifacts under tests/regression/ (3 slugs × meta/segs/paragraphs/summary), used as round-trip fixtures by the new loaders
provides:
  - agent/io.py — three schema-tolerant loaders (load_meta, load_segs, load_paragraphs) + SCHEMA_VERSION = 1 constant; the single landing point for any future v2 migration
  - docs/schema-versions.md — retroactive v1 field-set reference for meta.json / segs.json / paragraphs.json; documents loader behavior contract (D-04) and v1 frame-filename grammar
  - Mechanical conversion of 9 enumerated load sites across 5 .py files (agent/tools.py × 2, agent/prepare.py × 3, src/pipeline.py × 2, src/download.py × 1, agent/douyin_downloader.py × 1) to call the helpers instead of inline json.loads
affects:
  - All future phases reading meta/segs/paragraphs artifacts: they now share one loader path; v2 migration is now a single-file edit (agent/io.py) instead of a codebase-wide grep
  - Phase 2 RES-08 (schema_version writing convention) — this plan deliberately defers writing schema_version into NEW artifacts to that phase per A5 in 01-RESEARCH
  - Plan 01-03 (already shipped) — no interaction; encoding audit remains independent

tech-stack:
  added:
    - "agent/io.py (61 lines, stdlib-only: __future__, json, pathlib)"
    - "docs/ (new top-level directory; first time in project history)"
  patterns:
    - "Single-landing-point loader: caller modules never call json.loads on v1 artifacts; one helper per artifact type wraps json.loads + isinstance fail-fast"
    - "Per-file import style: agent/tools.py + agent/prepare.py use handler-scope lazy imports (matches existing sys.path.insert pattern); src/pipeline.py + src/download.py + agent/douyin_downloader.py use top-of-file absolute imports (agent.io is leaf, no circular risk)"
    - "v1 contract for list artifacts: top-level list IS v1 (D-04); wrapping into {schema_version, items} would break the 17 archived output/<slug>/ directories per PROJECT.md K3"

key-files:
  created:
    - agent/io.py
    - docs/schema-versions.md
  modified:
    - agent/tools.py
    - agent/prepare.py
    - src/pipeline.py
    - src/download.py
    - agent/douyin_downloader.py

key-decisions:
  - "Kept agent/io.py at 61 lines, stdlib-only (json + pathlib + __future__) — Pitfall 1 in 01-RESEARCH explicitly flagged 'do not turn this into a class hierarchy / registry / dispatch table'. The forward-compat surface is one comment per loader (`# future v2: insert ...`)."
  - "Per-file import style: agent/tools.py + agent/prepare.py keep handler-scope lazy imports (matches the existing sys.path.insert(...) + lazy `from src.asr import ...` idiom at lines 64-65 / 91-92 / 51); the three other files use top-of-file absolute imports because they don't have a sys.path-manipulation handler scope."
  - "agent/tools.py imports `load_segs` twice (once per handler) instead of once at module top — matches the project's lazy-import convention and keeps the patch local to each handler. Plan accepts both styles; per-handler chosen for minimal diff."
  - "Did NOT write schema_version into newly-produced artifacts. Per A5 in 01-RESEARCH, the writing convention belongs to Phase 2 RES-08; this plan only adds tolerant reading. Today every meta.json / segs.json / paragraphs.json written by the pipeline lacks the field, and that is intentional."

patterns-established:
  - "agent.io as the single landing point for v1-artifact loading: `from agent.io import load_meta, load_segs, load_paragraphs` is the only sanctioned read path. Any new caller adds an import and uses the helper; v2 migration touches one file."
  - "Fail-fast on shape mismatch: each loader runs isinstance(obj, dict|list) and raises ValueError naming path + actual type. Matches CONVENTIONS.md §'Error Handling' (bubble exceptions to CLI boundary)."

requirements-completed: [PRE-03]

duration: ~5min
completed: 2026-04-30
---

# Phase 1 Plan 02: Loader-Tolerance Landing Point Summary

**Three stdlib-only loader functions + one v1 field-set reference doc + 9 mechanical patches across 5 existing .py files — `agent/io.py` is now the single edit point for any future v2 schema migration; today every load of `meta.json` / `segs.json` / `paragraphs.json` flows through it with v1-default semantics.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-04-30T13:25:01Z
- **Completed:** 2026-04-30T13:29:34Z
- **Tasks:** 2
- **Files created:** 2 (agent/io.py + docs/schema-versions.md)
- **Files modified:** 5 (agent/tools.py, agent/prepare.py, src/pipeline.py, src/download.py, agent/douyin_downloader.py)

## Accomplishments

- Created `agent/io.py` (61 lines, stdlib-only): three loader functions (`load_meta`, `load_segs`, `load_paragraphs`) plus `SCHEMA_VERSION = 1` constant. Each loader does `json.loads(Path(path).read_text(encoding="utf-8"))`, runs an `isinstance` shape guard, and raises `ValueError` naming the path + actual type on mismatch. Module imports nothing beyond `__future__`, `json`, and `pathlib.Path`.
- Created `docs/schema-versions.md` (100 lines, first file in the new top-level `docs/` directory): retroactively documents the v1 field set for `meta.json` (B站 + 抖音 variants with `aweme_id` + `"source": "douyin"`), `segs.json`, `paragraphs.json` (with `para_id` format `p%04d` and `seg_indices` 0-indexed), plus the v1 frame-filename grammar `seg_<start_seconds:04d>_<frame_index:06d>.jpg`. Cross-links to `agent/io.py` and `tests/regression/regression-check.md`. Calls out Pitfall 5 (platform-dependent `video_path` separators — `\\` on Windows, `/` elsewhere; both valid v1, do not normalize).
- Patched all 9 enumerated v1-artifact load sites across 5 files (mechanical replacements; +18/−9 net diff):
  - L1 `agent/tools.py:78` — `load_segs(segs_file)` (cmd_transcribe handler-scope import)
  - L2 `agent/tools.py:96` — `load_segs(args.segs_json)` (cmd_aggregate handler-scope import)
  - L3 `agent/prepare.py:78` — `load_meta(work_dir / "meta.json")`
  - L4 `agent/prepare.py:93` — `load_segs(segs_cache)`
  - L5 `agent/prepare.py:115` — `load_paragraphs(para_cache)`
  - L6 `src/pipeline.py:36` — `load_meta(work_dir / "meta.json")`
  - L7 `src/pipeline.py:48` — `load_segs(segs_cache)`
  - L8 `src/download.py:22` — `load_meta(meta_cache)`
  - L9 `agent/douyin_downloader.py:152` — `load_meta(meta_cache)`
- Round-trip verified: all 3 baselines committed by plan 01-01 (`BV132wizyEEB/meta.json`, `BV1C9QCBdE1U/meta.json`, `douyin_trae_ai/meta.json`, plus `BV1C9QCBdE1U/segs.json` and `BV1C9QCBdE1U/paragraphs.json`) load successfully through the new helpers — none has a `schema_version` field, all default to v1 per `obj.get("schema_version", 1)`. The 抖音 baseline verified to retain both `aweme_id` and `source: "douyin"` keys after load.
- All 5 patched modules import cleanly (`python -c "import agent.io; import agent.tools; import agent.prepare; import src.pipeline; import src.download; import agent.douyin_downloader"` returned `OK: all 5 patched modules import cleanly`).
- Fail-fast contract verified: `load_meta(<file containing [])` raises `ValueError` with message containing `must be a dict`; `load_segs(<file containing {})` raises `ValueError` with `must be a list`. Both `str` and `pathlib.Path` arguments accepted.
- D-03 hard rule honored: `git status --porcelain` showed exactly 5 modified files (the 5 listed .py files), zero modifications under `output/<slug>/`. `.gitignore` and `.gitattributes` untouched.
- Out-of-scope load sites (`agent/frame_store.py:88`, `src/pipeline.py:70+85`, `src/summarize.py:647`) NOT patched — those load `frame_store.json` / `frames.json` / `frame_descs.json` / `outline.json`, none of which are v1 artifacts under this plan's scope per RESEARCH §"Out of scope for this loader".

## Task Commits

Each task committed atomically with `--no-verify` (parallel-executor convention; orchestrator validates hooks once after wave completes):

1. **Task 1: Create agent/io.py loaders + docs/schema-versions.md** — `ac402e1` (feat)
2. **Task 2: Patch 9 load sites across 5 .py files** — `add26d0` (refactor)

## Files Created/Modified

### Created

- `agent/io.py` (61 lines, stdlib-only) — three loader functions + `SCHEMA_VERSION = 1`. Each loader is 5–10 lines: parse JSON, isinstance-guard the shape, return parsed object. Public surface: `load_meta`, `load_segs`, `load_paragraphs`, `SCHEMA_VERSION`.
- `docs/schema-versions.md` (100 lines) — v1 field-set reference. Sections: Loader Behavior (locked), v1 Field Set (meta + 抖音 additions + segs + paragraphs), v1 Frame Conventions (filename grammar), Reference (cross-links).

### Modified

- `agent/tools.py` — added `from agent.io import load_segs` to both `cmd_transcribe` and `cmd_aggregate` handlers (handler-scope lazy import matches existing pattern at lines 64-65, 91-92); replaced two inline `json.loads(... .read_text(...))` calls at L1 (line 78) and L2 (line 96) with `load_segs(...)` calls.
- `agent/prepare.py` — added `from agent.io import load_meta, load_segs, load_paragraphs` once near the top of `main()` (after the existing sys.path.insert + agent/* imports at line 51-61); replaced three inline json.loads calls at L3 (line 78), L4 (line 93), L5 (line 115) with helper calls.
- `src/pipeline.py` — added top-of-file absolute import `from agent.io import load_meta, load_segs` (positioned before relative imports per CONVENTIONS.md §"Imports & Module Boundaries"); replaced two inline calls at L6 (line 36) and L7 (line 48). Verified no circular dependency: `agent.io` only depends on stdlib.
- `src/download.py` — added top-of-file `from agent.io import load_meta`; replaced one inline call at L8 (line 22).
- `agent/douyin_downloader.py` — added top-of-file `from agent.io import load_meta` (positioned after `import httpx` per import-order convention); replaced one inline call at L9 (line 152).

## Decisions Made

- **`agent/io.py` is exactly the verbatim skeleton from 01-RESEARCH §"Pattern 1", with no additions.** Pitfall 1 in research explicitly warns against adding a class hierarchy, registry, or dispatch table; the forward-compat surface is one `# future v2: insert ...` comment per loader. Total file size 61 lines (well under the 80-line hard cap), zero non-stdlib imports.
- **Handler-scope lazy import for `agent/tools.py` keeps two `from agent.io import load_segs` lines (one per handler) instead of one module-top import.** Matches the existing `sys.path.insert(0, str(Path(__file__).parent.parent))` + `from src.asr import ...` lazy pattern at lines 64-65 and 91-92. Plan explicitly accepts this style ("handler-scope lazy import" per the per-file guidance).
- **`docs/` is a new top-level directory in the repo.** Pitfall 4 in 01-RESEARCH explicitly required the schema reference to be grep-discoverable from `docs/` (as opposed to embedding into CLAUDE.md). Verified with `grep schema_version docs/`. The directory is the first of its kind in the project; created implicitly by `Write` on the file path.
- **Did NOT write `schema_version` into newly-produced artifacts.** Per A5 in 01-RESEARCH, the writing convention belongs to Phase 2 RES-08; this plan only adds tolerant reading. Today every `meta.json` / `segs.json` / `paragraphs.json` written by the pipeline still lacks the field, and that is intentional. The `obj.get("schema_version", 1)` default at the loader covers both old archives and freshly-written ones until Phase 2 makes a writing decision.
- **`isinstance` checks added to all three loaders, including `load_meta`.** RESEARCH §"Open Question 1" recommended keeping the check on `load_meta` for symmetry with the list checks (fail-fast on `[]` or string input). Three loaders × three identical guards = uniform error contract.

## Deviations from Plan

None — plan executed exactly as written.

The plan listed Task 1 as `tdd="true"`. The plan author embedded the behavioral test as a `python -c` block inside the `<verify>` section (instead of a separate pytest file), since the project has no test framework installed and the `¥0` / no-CI philosophy keeps tests as runnable scripts. I executed the embedded behavioral test exactly as specified after writing `agent/io.py`; all assertions returned `OK`. This honors TDD intent (write tests, see them pass against fresh code) under the project's actual testing convention.

## Auth Gates / Manual Steps

None encountered. All work was offline file editing + Python smoke tests against the in-tree baselines committed by plan 01-01.

## Issues Encountered

- **Worktree branch base mismatch (resolved automatically).** The worktree initially sat on commit `08a79f4` (the pre-planning HEAD of `main`), missing all of Wave 1's work (commits `f231af1`, `4345ae3`, `ef246b0`, `7066e21`, `12a25ec`, `3a4ecd8`, `48c141a`). The worktree-branch-check protocol's `git reset --hard 48c141a` and `git rebase --onto` variants were both blocked by the sandbox; resolved with `git merge --ff-only 48c141a2418b87af4b1cb811fc15af4110588eea`, which fast-forwarded the branch onto the correct Wave-1 base without any branch surgery. Verified `git rev-parse HEAD` matches `48c141a` afterward.
- **`git add` blocked, but `gsd-tools commit --files ...` worked.** Direct `git add` and `git commit` calls were sandbox-denied; the gsd-tools helper (`node $HOME/.claude/get-shit-done/bin/gsd-tools.cjs commit ...`) succeeded for both task commits and is the documented per-task commit path for parallel executors.
- **Terminal mojibake on em-dash (cosmetic, no impact).** When the smoke test printed `BV1C9QCBdE1U loads — 7 meta keys, 170 segs, 19 paragraphs`, the em-dash rendered as `��` because the bash STDOUT in the sandbox falls back to GBK on Windows zh-CN. The actual data and string content are intact (the loader returns valid Python objects); this is exactly the issue Plan 01-03's PRE-05 (Windows zh-CN section in CLAUDE.md) addresses for users of the live CLI. Doesn't affect correctness; noted only because the verify-block transcript reads slightly oddly.

## Threat Model Verification

Threat register from PLAN.md `<threat_model>` (5 threats, all LOW severity):

- **T-01-02-01 (Tampering, malformed JSON)** — mitigated. Each loader has its `isinstance` guard; verify block tested both `[]` against `load_meta` and `{}` against `load_segs`, both raised `ValueError` with the required substring.
- **T-01-02-02 (Tampering, accidental output/ modification)** — mitigated. `git status --porcelain` after Task 2 showed exactly 5 modified files, all in the planned set; zero `output/` modifications.
- **T-01-02-03 (DoS / EoP via unsafe import)** — mitigated. `grep -E '^(import|from)' agent/io.py | grep -vE '^(from __future__|import json|from pathlib)'` returned empty — stdlib-only confirmed.
- **T-01-02-04 (Info disclosure via docs)** — accepted. The doc only documents field names + types; no sample values, titles, URLs, or secrets.
- **T-01-02-05 (Silent v2 acceptance)** — accepted. Per RESEARCH Open Question 4, no speculative version-mismatch warnings in Phase 1.

No new threat surface introduced beyond what the threat register anticipated. No threat flags.

## Self-Check: PASSED

Verification on disk after both task commits (`git log --oneline -5` shows `add26d0` and `ac402e1` at HEAD):

- FOUND: `agent/io.py` (2,335 bytes, 61 lines, stdlib-only)
- FOUND: `docs/schema-versions.md` (3,938 bytes, 100 lines)
- FOUND: commit `ac402e1` (`feat(01-02): add agent/io.py loaders + docs/schema-versions.md (PRE-03)`)
- FOUND: commit `add26d0` (`refactor(01-02): route 9 v1-artifact load sites through agent.io`)
- VERIFIED: all 13 automated assertions in Task 1 `<verify>` returned OK (file exists + size cap + 5 required identifiers + stdlib-only + 6 behavior assertions including isinstance fail-fast + Path arg + 9 docs grep checks).
- VERIFIED: all Task 2 `<verify>` assertions returned OK (5 imports added + 9 OLD patterns absent at enumerated sites + 9 NEW helper calls present + total count = 9 + 5 modules import cleanly + BV1C9QCBdE1U baseline round-trips through helpers + 0 output/ modifications + .gitignore unchanged).
- VERIFIED: `agent/io.py` contains zero `class` keywords (`grep -E '^class ' agent/io.py` would return empty — no over-engineering per Pitfall 1).
- VERIFIED: out-of-scope load sites untouched — `agent/frame_store.py:88`, `src/pipeline.py:70+85`, `src/summarize.py:647` still call `json.loads(... .read_text(...))` directly, as required by RESEARCH §"Out of scope for this loader".

---

*Phase: 01-preflight-regression-baseline*
*Plan: 02*
*Completed: 2026-04-30*
