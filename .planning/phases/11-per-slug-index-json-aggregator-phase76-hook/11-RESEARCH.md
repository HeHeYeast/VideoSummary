# Phase 11: per-slug index.json + 顶层聚合 + Phase 7.6 hook — Research

**Researched:** 2026-05-04
**Domain:** v1.2 knowledge-base index layer (new `agent/index.py` module + 2 nested CLI subcommands + CLAUDE.md `/summarize-video` Phase 7.6 hook insertion)
**Confidence:** HIGH

## Summary

Phase 11 is a tightly-bounded infrastructure phase that mirrors Phase 10's just-shipped `agent/topics.py` pattern almost 1:1 — same atomic-write, same FileLock domain shape, same nested-subparser CLI wiring, same K5 source-grep test pattern. All structural decisions are locked in 11-CONTEXT.md (D-01..D-10) with 8-field schema example + Phase 7.6 markdown verbatim. Phase 10 contracts (`from agent.topics import read_topics, append_pending`) are stable + verified; Phase 11 generator consumes them as the topic whitelist.

**Three real surprises** found during research that the planner MUST account for:

1. **17 archived slugs lack `plan.md`** — the canonical `mode` field in index.json schema must read plan.md when present and **fall back to `replicate-guide`** per CLAUDE.md when missing. Phase 7.6 hook will encounter plan.md (current-flow output of Phase 2); Phase 12 backfill will not (archives predate plan.md). Generator must handle both.
2. **Chapter heading conventions are NOT uniform across modes** — `interview-distillation` uses `## [HH:MM] topic`; `replicate-guide` uses `## 一、Chinese-numeral` with timestamps in inline `[HH:MM] **bold**` lines below; `extension-applications` mixes both. `chapters[].start` cannot be derived by regex alone — Claude inference is the source. This is a feature (K5: Claude-as-decider), not a bug.
3. **`output/_glossary.md` does not exist on this branch** — none of the 17 v1.0 archives nor the 16 douyin/BV samples have exercised `cross_slug_glossary` (v1.1 TEACH-A3 is opt-in). D-06 keyword-reuse must therefore handle the **vacuously-empty H2-anchor candidate set** gracefully: when `_glossary.md` is missing, `keywords[]` is whatever Claude proposes from the summary (no canonical reuse possible). This is exactly Phase 10 plan-02's conclusion — the canonicalization invariant holds forward, not retroactively.

**Primary recommendation:** Clone `agent/topics.py` skeleton verbatim → swap names (`topics`→`index`, `_topics.md`→`<slug>/index.json`, `.topics.lock`→`.index.lock`). Add 1 new public function (`rebuild_aggregator`) and 1 read helper (`read_aggregator`). Wire 2 nested CLI handlers in `agent/tools.py:cmds["index"]` mirroring `topics_cmds`. Add 3 K5 source-grep tests extending `tests/test_k5_emitters.py`'s already-shipped 17. Insert Phase 7.6 hook in CLAUDE.md between line 1770 and line 1772 verbatim from CONTEXT.md `<specifics>` block.

## User Constraints (from CONTEXT.md)

### Locked Decisions

> Per 11-CONTEXT.md `<decisions>` block. The planner MUST honor these verbatim. No alternatives are to be researched.

**D-01 — per-slug `index.json` schema**

- D-01.1: path = `output/<slug>/index.json` (per-slug sibling to summary.md / segs.json / paragraphs.json / meta.json — but a NEW sidecar, not a 4-core-artifact).
- D-01.2: 8 fields (locked, missing-any = fail): `slug` (str), `title` (str from meta.json), `duration_s` (number from meta.json `duration`), `mode` (one of 4 modes; from plan.md front-matter; missing → fallback `replicate-guide`), `topics[]` (strings, from `_topics.md` Approved tree; `pending: <name>` permitted), `keywords[]` (strings, optional reuse of `_glossary.md` H2 anchors), `tldr_oneliner` (str 10-50 字), `chapters[]` (array of `{title, start, excerpt}`; **no per-chapter keywords** per D-02).
- D-01.3: `chapters[].start` = float seconds (consistent with `segs.json` / `paragraphs.json`).
- D-01.4: schema validator = `agent/index.py:validate_per_slug_index(d) -> None`; raises `IndexValidationError` on missing field / type error / mode-not-in-4 / topic-not-in-whitelist.
- D-01.5: generator source = Claude reads `summary.md + meta.json + plan.md + paragraphs.json + _glossary.md` and produces JSON pipe → CLI (mirror Phase 10 bootstrap pattern; Claude is decider per K5).

**D-02 — `/summarize-video` Phase 7.6 hook**

- D-02.1: Insert in CLAUDE.md `## /summarize-video 完整工作流` between Phase 7.5 (verifier) and Phase 8 (cleanup).
- D-02.2: Hook step order = (1) Read 5 files; (2) infer 8 fields; (3) `python -m agent.tools index write --slug <slug> --from-stdin <<EOF ...`; (4) CLI validate + atomic write per-slug index.json; (5) CLI immediate rebuild of `output/.index.json`.
- D-02.3: User zero operation (per D-03 automation-first); `pending: <name>` auto-appended to `_topics.md` Pending if no approved topic fits.
- D-02.4: Workflow doc mirrors v1.1 Phase 8 5-min TL;DR insertion style.

**D-03 — top-level `output/.index.json` aggregator**

- D-03.1: path = `output/.index.json` (top-level dotfile sibling of `_topics.md` / `_glossary.md`).
- D-03.2: schema = flat dict `{"<slug>": <per-slug-index>, ...}`; **no backlink fields** (per D-07 in v1.2-CANDIDATES.md).
- D-03.3: auto rebuild = every per-slug `index write` triggers immediate rebuild via atomic `tempfile + os.replace`.
- D-03.4: size budget ~5-10 KB (23 entries × 100-300 字); negligible Read cost.
- D-03.5: stale detection = compare per-slug `mtime` vs `output/.index.json` mtime; newer per-slug → stdout warning + JSON `stale: [...]`.
- D-03.6: top-level `.index.json` is a NEW sidecar — not in D-29 replay scope.

**D-04 — `index rebuild` manual CLI**

- D-04.1: `python -m agent.tools index rebuild` (no args; idempotent).
- D-04.2: glob `output/*/index.json`, exclude `_*` / `.git` / `.*` hidden dirs.
- D-04.3: per-slug missing/invalid → stderr WARNING + skip; rest continue; exit 0 if ≥ 1 valid, else 1.
- D-04.4: stdout JSON `{"action": "rebuilt", "slugs_included": N, "slugs_skipped": [{"slug","reason"}], "stale_detected": [...], "_index_path": "output/.index.json"}`.
- D-04.5: stale detection per D-03.5 (warning, not blocking).
- D-04.6: atomic write via `tempfile.NamedTemporaryFile + os.fsync + os.replace` (mirror `agent/glossary.py:_atomic_write`).

**D-05 — `index write` CLI**

- D-05.1: `python -m agent.tools index write --slug <slug> --from-stdin`.
- D-05.2: behavior = (a) read stdin JSON; (b) `validate_per_slug_index`; (c) verify all non-pending topics in Approved set; (d) atomic write `output/<slug>/index.json`; (e) immediate rebuild of top-level.
- D-05.3: schema fail → stderr detailed error + exit 1; existing `output/<slug>/index.json` untouched (atomic semantic).
- D-05.4: `pending: <name>` topics → CLI calls `agent.topics.append_pending` (idempotent — duplicate-name returns `skipped`); plain strings must be in Approved (else fail-fast).
- D-05.5: stdout JSON `{"action": "written"|"skipped", "slug": "...", "_index_path": "...", "_aggregator_path": "...", "_topics_pending_appended": [<names>]}`.
- D-05.6: idempotent — existing index.json byte-equal stdin → no-op `skipped`; any field diff → overwrite.
- D-05.7: `--force` flag skips Approved-set strict check (Phase 12 backfill emergency only).

**D-06 — keywords reuse `_glossary.md` H2 anchors**

- D-06.1: parse all `^## ` lines from `_glossary.md` as candidate set.
- D-06.2: byte-equal canonical form for matched terms (e.g., `LoRA (Low-Rank Adaptation)`, never `Lora` / `low-rank adaptation`).
- D-06.3: novel terms allowed — generator does NOT auto-append new keyword to `_glossary.md` (different write timing).
- D-06.4: test = mock `_glossary.md` + mock `summary.md` → assert generated keyword is byte-equal canonical form.

**D-07 — D-29 byte-equal active verify**

- D-07.1: Phase 11 close gate = `python scripts/replay_v10_archives.py` → 33 PASS / 0 FAIL.
- D-07.2: any byte diff in 4 core files (summary.md / segs.json / paragraphs.json / meta.json) = phase NOT shippable.
- D-07.3: `output/<slug>/index.json` + `output/.index.json` are NEW sidecars — outside replay scope.
- D-07.4: any debug operation on archived slugs MUST backup 4 core files first; production backfill (Phase 12) pipes through generator (read-only on summary/meta/plan/paragraphs/glossary), so byte-equal is naturally preserved.

**D-08 — `agent/index.py` module layout**

- D-08.1: `agent/index.py` sibling of `agent/topics.py` / `agent/glossary.py` / `agent/_lock.py`.
- D-08.2: 5 public functions:
  - `validate_per_slug_index(d: dict) -> None`
  - `read_per_slug_index(slug_dir: Path) -> dict | None`
  - `write_per_slug_index(slug_dir: Path, index_data: dict, *, output_dir=None) -> dict`
  - `rebuild_aggregator(output_dir: Path = Path("output")) -> dict`
  - `read_aggregator(output_dir: Path = Path("output")) -> dict`
- D-08.3: CLI handlers `cmd_index_write` / `cmd_index_rebuild` in `agent/tools.py`.
- D-08.4: `cmds["index"]` nested-subparser dispatch (mirror Phase 10 `topics_cmds`).
- D-08.5: `IndexValidationError(Exception)` defined at top of `agent/index.py`.

**D-09 — FileLock serialization**

- D-09.1: lock path = `output/.index.lock` (4th cross-slug lock domain after `~/.videoSummary/.queue.lock` / `output/.glossary.lock` / `output/.topics.lock`).
- D-09.2: reuse `agent/_lock.py:FileLock` verbatim (stale-PID handover).
- D-09.3: lock writes only — `write_per_slug_index` (which triggers rebuild) + standalone `rebuild_aggregator`.
- D-09.4: reads (`read_per_slug_index` / `read_aggregator`) are lock-free.
- D-09.5: `.topics.lock` and `.index.lock` are independent — concurrent acquisition of both is a normal pattern (resolve_pending case).

**D-10 — K5 boundary static assertions**

Add 3 new tests to `tests/test_k5_emitters.py` (currently 17 tests):

- `test_K5_module_index_no_summary_writes` — `agent/index.py` source contains zero of `summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json` (5 D-29 core literals).
- `test_K5_cmd_index_write_no_d29_writes` — `cmd_index_write` source same forbidden 5.
- `test_K5_cmd_index_rebuild_read_only_per_slug` — `cmd_index_rebuild` source same forbidden 5 + must NOT contain write-pattern targeting `<slug>/index.json` (rebuild reads per-slug, writes only top-level).

`index.json` literal IS allowed (Phase 11's own write target). The 5 D-29 core literals are forbidden.

### Claude's Discretion

Per 11-CONTEXT.md `<decisions>` final block — these are research areas where the planner has freedom. RESEARCH addresses each with a recommendation:

- `tldr_oneliner` 形态 — Claude proposes per-mode based on summary.md content
- `chapters[]` excerpt 形态 — Claude reads summary.md per chapter, picks 1-2 lines
- `_glossary.md` H2 anchor parsing regex — see § Code Examples → Pattern 4
- `index rebuild` stdout layout (text vs JSON) — recommend `--json` flag + plain-text default
- top-level `.index.json` dict ordering — see § Open Questions → Q-E recommendation (lexicographic)

### Deferred Ideas (OUT OF SCOPE)

Per 11-CONTEXT.md `<deferred>` block. Phase 11 MUST NOT plan these:

- per-slug index.json `version: 1` schema versioning (deferred to v1.3+ if breaking change needed)
- `index search` / `index list` CLI (Phase 12 KB-MISC-01)
- top-level `.index.json` incremental rebuild (full rebuild is < 1 ms at 23 entries)
- `.v12_features.json` opt-out marker (v1.2 has no archive byte-equal worry — index.json IS new sidecar; mirror v1.1 marker only if scale forces)
- top-level `.index.json` split strategy at > 50 KB (current ≈ 5-10 KB; v1.3+ if scale)
- per-slug index.json filename-rename tooling (v1.3+)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KB-01 | per-slug index.json 8-field schema lock | D-01 8 fields verbatim + § Code Examples Pattern 1 (validator) |
| KB-02 | `/summarize-video` Phase 7.6 auto-write + Phase 12 backfill reuses same generator | D-02 hook + § Open Questions Q-B insertion location |
| KB-03 | keywords reuse `_glossary.md` H2 anchors | D-06 + § Code Examples Pattern 4 (regex) + § Open Questions Q-A (vacuous-empty handling) |
| KB-04 | top-level `output/.index.json` atomic rebuild | D-03 + D-04.6 atomic-write + § Code Examples Pattern 5 (rebuild loop) |
| KB-05 | `python -m agent.tools index rebuild` manual CLI + stale detection | D-04 + § Code Examples Pattern 6 (stale-mtime check) |
| KB-06 | D-29 byte-equal 33/0/30 still passes | D-07 + § Verification Architecture (pre-close gate) |

## Standard Stack

### Core (already shipped — Phase 10 / v1.1 ship)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `agent.topics` | shipped Phase 10 | `read_topics` whitelist + `append_pending` for novel topics | Stable Phase 11 import contract per 11-CONTEXT.md `<canonical_refs>` |
| `agent._lock.FileLock` | shipped v1.0 Phase 06 | cross-platform advisory lock (msvcrt + fcntl) with stale-PID handover | Mature, 17 K5 tests cover usage; 3 lock domains already proven |
| `agent.io.write_json_atomic` | shipped v1.0 Phase 02 | tempfile + os.replace + PermissionError retry | Used by 30+ call sites; battle-tested on Windows/POSIX |
| `agent.glossary._atomic_write` | shipped v1.1 Phase 08 | tempfile + os.fsync + os.replace pattern (no retry, simpler) | Pattern reference for `agent/index.py:_atomic_write` |
| stdlib only | Python 3.11+ | `json` / `re` / `pathlib` / `tempfile` / `os` / `argparse` | Per CLAUDE.md ¥0 + zero-new-dep invariant |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `agent.state.append_event` | shipped Phase 02 | per-slug `state.jsonl` event log | Per CONTEXT D-08 NOT needed — `index write/rebuild` is ad-hoc, not pipeline stage |
| `tests.test_topics` | shipped Phase 10 | 24 behavior tests in 5 classes — shape reference for `tests.test_index` | Mirror class structure (TestRead* / TestWrite* / TestRebuild* / TestSchema* / TestAtomic*) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Module-level `agent/index.py` | `agent/_index.py` (private prefix like `_lock.py` / `_v11.py`) | `_lock` / `_v11` are private because internals; `topics` / `glossary` / `index` are public Claude-facing APIs (Phase 11 generator imports `read_per_slug_index`). Use `agent/index.py` (no underscore). |
| New top-level lockfile `~/.videoSummary/.index.lock` (cross-machine) | `output/.index.lock` (per-repo) | Knowledge base is single-user single-repo; cross-machine sync isn't a use case. Mirror `.glossary.lock` / `.topics.lock` (per-repo). |
| Auto-trigger rebuild on every `index write` AND emit state.jsonl event | rebuild + no event | state.jsonl is per-slug pipeline stage log. `index write/rebuild` is cross-slug ad-hoc. Skipping events is consistent with `glossary append` (which also doesn't emit). |
| Versioned schema with `"version": 1` field | naked 8-field schema | D-01.2 locks 8 fields fixed for v1; deferred to v1.3+ per CONTEXT `<deferred>`. |

**Installation:** No new packages; stdlib + agent stack only. **Version verification:** N/A — no third-party deps.

## Architecture Patterns

### Recommended Module Layout

```
agent/
├── index.py                          # NEW: Phase 11 module (5 public functions + IndexValidationError)
├── topics.py                         # SHIPPED Phase 10 — Phase 11 imports read_topics + append_pending
├── glossary.py                       # SHIPPED v1.1 Phase 08 — pattern reference for _atomic_write
├── _lock.py                          # SHIPPED v1.0 Phase 06 — FileLock reuse
├── io.py                             # SHIPPED v1.0 Phase 02 — write_json_atomic available if preferred over local _atomic_write
└── tools.py                          # MODIFIED: + cmd_index_write / cmd_index_rebuild + cmds["index"] nested subparser

tests/
├── test_index.py                     # NEW: 5 classes (TestRead/TestValidate/TestWrite/TestRebuild/TestAtomic)
└── test_k5_emitters.py               # MODIFIED: +3 tests (D-10.1) inside existing TestK5BoundaryPhase07

output/
├── .index.json                       # NEW top-level aggregator (auto + manual rebuild)
├── .index.lock                       # NEW FileLock sibling (gitignored, per .glossary.lock pattern)
├── _topics.md                        # SHIPPED Phase 10 — Phase 11 reads Approved + appends Pending
├── _glossary.md                      # SHIPPED v1.1 Phase 08 — Phase 11 reads H2 anchors (may be MISSING; see Q-A)
└── <slug>/
    ├── index.json                    # NEW per-slug sidecar (8 fields)
    ├── summary.md                    # READ-ONLY (D-29 invariant)
    ├── meta.json                     # READ-ONLY
    ├── paragraphs.json               # READ-ONLY
    ├── segs.json                     # READ-ONLY
    └── plan.md                       # READ-ONLY (may be MISSING on archives — see Q-C)

CLAUDE.md
└── ## /summarize-video 完整工作流    # MODIFIED: insert ### Phase 7.6 between line 1770 and 1772
└── ## v1.2 知识库索引层              # NEW H2 mirror of v1.1 H2 byte-locked rule format (deferred to Phase 12 prompt rule? — see Q-B)
```

### Pattern 1: Schema validator (D-01.4 / KB-01)

**What:** Mechanical 8-field check; raises `IndexValidationError` with specific field name on first failure.
**When:** Called by `write_per_slug_index` BEFORE atomic write; called by `rebuild_aggregator` BEFORE including a per-slug entry.
**Source:** Pattern derived from `agent/topics.py:_validate_taxonomy` shape.

```python
# agent/index.py — Pattern 1 (sketch; planner finalizes)
class IndexValidationError(Exception):
    """Raised when per-slug index.json schema (8 fields) fails validation."""

VALID_MODES = (
    "replicate-guide",
    "concept-explanation",
    "extension-applications",
    "interview-distillation",
)

REQUIRED_FIELDS = ("slug", "title", "duration_s", "mode",
                   "topics", "keywords", "tldr_oneliner", "chapters")

def validate_per_slug_index(d: dict, *, approved_topics: set[str] | None = None) -> None:
    if not isinstance(d, dict):
        raise IndexValidationError(f"index data must be a dict, got {type(d).__name__}")
    for f in REQUIRED_FIELDS:
        if f not in d:
            raise IndexValidationError(f"missing required field: {f!r}")
    # Type checks
    if not isinstance(d["slug"], str) or not d["slug"].strip():
        raise IndexValidationError(f"'slug' must be non-empty string, got {d['slug']!r}")
    if not isinstance(d["title"], str):
        raise IndexValidationError(f"'title' must be string, got {type(d['title']).__name__}")
    if not isinstance(d["duration_s"], (int, float)):
        raise IndexValidationError(f"'duration_s' must be number, got {type(d['duration_s']).__name__}")
    if d["mode"] not in VALID_MODES:
        raise IndexValidationError(f"'mode' must be one of {VALID_MODES}, got {d['mode']!r}")
    if not isinstance(d["topics"], list):
        raise IndexValidationError(f"'topics' must be list, got {type(d['topics']).__name__}")
    if not isinstance(d["keywords"], list):
        raise IndexValidationError(f"'keywords' must be list, got {type(d['keywords']).__name__}")
    if not isinstance(d["tldr_oneliner"], str):
        raise IndexValidationError(f"'tldr_oneliner' must be string, got {type(d['tldr_oneliner']).__name__}")
    if not isinstance(d["chapters"], list):
        raise IndexValidationError(f"'chapters' must be list, got {type(d['chapters']).__name__}")
    # Topic whitelist check (only if approved set passed in)
    if approved_topics is not None:
        for t in d["topics"]:
            if not isinstance(t, str):
                raise IndexValidationError(f"topic must be string, got {type(t).__name__}")
            if t.startswith("pending: "):
                continue  # pending: <name> is allowed per D-05.4
            if t not in approved_topics:
                raise IndexValidationError(
                    f"topic {t!r} not in Approved Taxonomy; "
                    f"use 'pending: {t}' to submit for review"
                )
    # Chapter shape
    for i, ch in enumerate(d["chapters"]):
        if not isinstance(ch, dict):
            raise IndexValidationError(f"chapters[{i}] must be dict, got {type(ch).__name__}")
        for cf in ("title", "start", "excerpt"):
            if cf not in ch:
                raise IndexValidationError(f"chapters[{i}] missing field {cf!r}")
        if not isinstance(ch["start"], (int, float)):
            raise IndexValidationError(f"chapters[{i}].start must be number")
```

### Pattern 2: Atomic per-slug write + immediate aggregator rebuild (D-05.2)

**Source:** Mirror `agent/topics.py:write_approved_taxonomy` + `agent/glossary.py:_atomic_write`.

```python
# agent/index.py — Pattern 2 (sketch)
def write_per_slug_index(
    slug_dir: Path,
    index_data: dict,
    *,
    output_dir: Path | None = None,
    timeout: float = 10.0,
    force: bool = False,
) -> dict:
    """Atomic write index.json + immediate aggregator rebuild.

    Locks output/.index.lock during write+rebuild window. Validates schema
    + topics whitelist before any disk write (no half-written state).
    """
    slug_dir = Path(slug_dir)
    out_dir = Path(output_dir) if output_dir else slug_dir.parent
    lock_path = out_dir / ".index.lock"

    # Schema check: load topic whitelist FIRST (so validation can flag bad topics).
    from agent.topics import read_topics
    topics_data = read_topics(out_dir / "_topics.md")
    approved = _flatten_approved_names(topics_data["approved"])

    validate_per_slug_index(
        index_data,
        approved_topics=None if force else approved,
    )

    target = slug_dir / "index.json"
    target.parent.mkdir(parents=True, exist_ok=True)

    # Pending-topic side-effect: append novel "pending: <name>" entries.
    pending_appended: list[str] = []
    for t in index_data["topics"]:
        if isinstance(t, str) and t.startswith("pending: "):
            name = t[len("pending: "):]
            from agent.topics import append_pending
            r = append_pending(
                out_dir / "_topics.md", name,
                from_slug=index_data["slug"],
                chapter_title="(全片)",
                reason="(Phase 11 generator auto-submitted)",
                output_dir=str(out_dir), timeout=timeout,
            )
            if r["action"] == "appended":
                pending_appended.append(name)

    payload = json.dumps(index_data, ensure_ascii=False, indent=2)

    with FileLock(lock_path, timeout=timeout):
        # Idempotent skip check
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing == payload:
                return {
                    "action": "skipped",
                    "slug": index_data["slug"],
                    "_index_path": str(target),
                    "_aggregator_path": str(out_dir / ".index.json"),
                    "_topics_pending_appended": pending_appended,
                }
        # Atomic per-slug write
        _atomic_write(target, payload)
        # Immediate aggregator rebuild (still inside the same lock window)
        rebuild_result = _rebuild_aggregator_inner(out_dir)
    return {
        "action": "written",
        "slug": index_data["slug"],
        "_index_path": str(target),
        "_aggregator_path": str(out_dir / ".index.json"),
        "_topics_pending_appended": pending_appended,
    }
```

**Key invariant:** the aggregator rebuild happens **inside the same lock window** as the per-slug write — readers always see consistent state.

### Pattern 3: Aggregator rebuild (D-04.2..D-04.5)

```python
# agent/index.py — Pattern 3 (sketch)
def _rebuild_aggregator_inner(output_dir: Path) -> dict:
    """Lock-internal rebuild — assumes caller holds output/.index.lock."""
    aggregator_path = output_dir / ".index.json"
    aggregator_mtime = (
        aggregator_path.stat().st_mtime if aggregator_path.exists() else 0.0
    )

    candidates = sorted(output_dir.glob("*/index.json"))
    # Exclude hidden / underscore dirs (D-04.2): _glossary.md / _topics.md don't
    # match `*/index.json` pattern anyway; but if user mkdir'd `_archive/index.json`
    # we'd skip. glob's `*` already excludes leading `.` on POSIX/Windows.
    aggregated: dict[str, dict] = {}
    skipped: list[dict] = []
    stale: list[str] = []

    for ip in candidates:
        slug = ip.parent.name
        if slug.startswith("_") or slug.startswith("."):
            continue
        try:
            data = json.loads(ip.read_text(encoding="utf-8"))
            validate_per_slug_index(data)  # No whitelist check at rebuild time (already enforced at write)
        except (OSError, json.JSONDecodeError) as e:
            skipped.append({"slug": slug, "reason": f"unreadable: {e}"})
            continue
        except IndexValidationError as e:
            skipped.append({"slug": slug, "reason": f"schema invalid: {e}"})
            continue
        # Stale detection
        if ip.stat().st_mtime > aggregator_mtime:
            stale.append(slug)
        aggregated[slug] = data

    # D-03 / Q-E: lexicographic order for reproducibility (recommendation).
    ordered = {k: aggregated[k] for k in sorted(aggregated.keys())}
    payload = json.dumps(ordered, ensure_ascii=False, indent=2)
    _atomic_write(aggregator_path, payload)
    return {
        "slugs_included": len(ordered),
        "slugs_skipped": skipped,
        "stale_detected": stale,
    }


def rebuild_aggregator(output_dir: Path = Path("output"), *, timeout: float = 10.0) -> dict:
    """Public manual-rebuild entrypoint. Acquires output/.index.lock for safety."""
    output_dir = Path(output_dir)
    lock_path = output_dir / ".index.lock"
    with FileLock(lock_path, timeout=timeout):
        return _rebuild_aggregator_inner(output_dir)
```

### Pattern 4: `_glossary.md` H2 anchor parsing (D-06.1 / KB-03)

**What:** Parse all `^## ` lines into a candidate set; match summary.md content against this set; output kept verbatim canonical form.
**Source:** Mirror `agent/glossary.py:_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)`.

```python
# agent/index.py — Pattern 4 (sketch)
_GLOSSARY_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)

def _glossary_h2_anchors(glossary_path: Path) -> list[str]:
    """Extract canonical H2 anchor terms from _glossary.md.

    Returns list of strings as they appear (e.g., ["LoRA (Low-Rank Adaptation)",
    "RAG (Retrieval-Augmented Generation)", "MCP (Model Context Protocol)"]).
    Returns [] if file doesn't exist (vacuously-empty case — no canonical reuse
    possible for this slug; new keywords are still allowed per D-06.3).
    """
    if not glossary_path.exists():
        return []  # Q-A vacuous-empty: 17 archives + this branch's 16 dirs all lack _glossary.md
    text = glossary_path.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in _GLOSSARY_H2_RE.finditer(text)]
```

**This function is read-only and is invoked by Claude when Claude composes the JSON before piping to `index write` — NOT by the CLI itself.** The CLI writes whatever JSON Claude pipes; the canonicalization invariant is enforced at composition time, NOT at validation time. (This matches D-01.5: generator source = Claude.) Phase 11 ships this regex helper exposed in `agent/index.py` for re-use; D-06.4 test exercises it.

### Pattern 5: nested CLI subparser (D-08.4)

**Source:** Mirror Phase 10 `topics_cmds` block (`agent/tools.py:2117-2118`).

```python
# agent/tools.py main() — Pattern 5 (sketch, additions only)
# At the cmds dict block (around line 2074):
index_cmds = {  # Phase 11 D-08.4 — nested dispatch for `index {write|rebuild}`
    "write":   cmd_index_write,
    "rebuild": cmd_index_rebuild,
}
# At the dispatch chain (around line 2117):
elif args.command == "index":  # NEW Phase 11
    index_cmds[args.index_cmd](args)

# At the subparser registration (around line 2017 — the `topics` subparser block):
p = sub.add_parser(
    "index",
    help="Knowledge-base index: write (Phase 7.6 hook target — read --from-stdin JSON) "
         "/ rebuild (manual top-level aggregator rebuild)",
)
isub = p.add_subparsers(dest="index_cmd", required=True)

iwrite = isub.add_parser(
    "write",
    help="Phase 7.6 hook target: read 8-field index JSON from stdin and atomic-write "
         "<slug>/index.json + rebuild output/.index.json",
)
iwrite.add_argument("--slug", required=True,
                    help="slug name (e.g., BV132wizyEEB) — must match dir under --output-dir")
iwrite.add_argument("--from-stdin", action="store_true",
                    help="REQUIRED: read 8-field index JSON from stdin")
iwrite.add_argument("--output-dir", default="output")
iwrite.add_argument("--force", action="store_true",
                    help="skip Approved Taxonomy strict whitelist (Phase 12 backfill emergency only)")
iwrite.add_argument("--timeout", type=float, default=10.0)
iwrite.add_argument("--json", action="store_true")

irebuild = isub.add_parser(
    "rebuild",
    help="Manual rebuild of output/.index.json from all output/<slug>/index.json files",
)
irebuild.add_argument("--output-dir", default="output")
irebuild.add_argument("--timeout", type=float, default=10.0)
irebuild.add_argument("--json", action="store_true")
```

### Pattern 6: stale detection by mtime (D-03.5 / D-04.5)

```python
# agent/index.py — Pattern 6 (already inlined in Pattern 3)
# Aggregator file mtime vs each per-slug index.json mtime.
# Per-slug newer → list in stale_detected[]; warn-not-block.
```

### Anti-Patterns to Avoid

- **Don't read summary.md / segs.json / paragraphs.json / meta.json INSIDE `agent/index.py`** — even though Claude reads them at composition time, the **module source must contain ZERO of those literals** (K5 boundary, D-10.1). Generator-side reads happen at Claude prompt level, NOT in CLI source code. The CLI ingests already-decided JSON via stdin. **Avoid:** even `# read summary.md` comments — `inspect.getsource()` test will FAIL.
- **Don't skip the FileLock for read-only operations** — but DO acquire it for the immediate aggregator rebuild that follows a per-slug write (per D-09.3). Reads are lock-free (D-09.4); writes hold the lock through the rebuild as well.
- **Don't auto-promote `pending: <name>` to Approved during `index write`** — that's `topics resolve` territory (per D-04 K5 governance + D-05.4). `index write` MAY append to Pending (allowed), but never promote.
- **Don't write `output/.index.json` outside the lock** — race window with concurrent `index write` from another terminal would corrupt JSON.
- **Don't skip the schema check on `rebuild_aggregator`** — corrupted per-slug index.json caused by manual editing should be quarantined to `slugs_skipped[]`, not silently included.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File-rename atomicity | Custom rename loop with `os.rename` + retry | `agent/glossary.py:_atomic_write` pattern (`tempfile.NamedTemporaryFile` in target dir + `os.fsync` + `os.replace`) | Cross-device atomic on Windows + POSIX; battle-tested in v1.0/v1.1 across 30+ call sites. Simpler than `agent/io.write_json_atomic` (no PermissionError retry), but you can use `write_json_atomic` if Windows Defender drift is a concern. |
| Cross-process locking | `flock` POSIX-only + Windows lockf hack | `agent/_lock.FileLock` | Already cross-platform (msvcrt + fcntl); already handles stale-PID handover; already 17 K5 tests cover edge cases. |
| Topic whitelist parsing | New regex on `_topics.md` | `from agent.topics import read_topics` | Phase 10 stable contract; returns `{"approved": [...], "pending": [...]}`. |
| Pending-topic submission | New write to `_topics.md` from `agent/index.py` | `from agent.topics import append_pending` | Stable Phase 10 API; idempotent on duplicate names; serialized via `output/.topics.lock` (separate from `.index.lock`). Keeps K5 boundary clean: `agent/index.py` doesn't touch `_topics.md` directly. |
| K5 source-grep test | Custom AST traversal | Extend existing `tests/test_k5_emitters.py:TestK5BoundaryPhase07` class with 3 new methods using `inspect.getsource()` | 17 K5 tests already shipped using this pattern; adding a 4th class fragments the test layout. |
| Atomic JSON write | Hand-rolled tempfile-then-rename | `agent/io.write_json_atomic` (option A — adds PermissionError retry for Defender) OR mirror `agent/glossary.py:_atomic_write` (option B — simpler, no retry) | Either is fine per CONVENTIONS.md. **Recommendation:** option B (mirror glossary) since `index.json` write happens inside FileLock window — concurrent Defender locks are very unlikely; simpler is better. |

**Key insight:** Phase 11 should be ~75% mechanical clone of Phase 10 + 25% net-new (the aggregator rebuild loop + Phase 7.6 hook insertion). Custom solutions for any of the above is a code smell.

## Runtime State Inventory

> Phase 11 introduces NEW sidecars; it does NOT rename or migrate existing artifacts. This section documents what state exists vs is created.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | None — verified by inspection of `output/<slug>/` (no Mem0 / ChromaDB / SQLite databases). The accumulator files (`output/_topics.md` / future `output/_glossary.md`) are markdown read-modify-write, NOT a DB. | **No action.** `output/<slug>/index.json` is a NEW per-slug sidecar; `output/.index.json` is a NEW top-level aggregator. Both are created fresh by Phase 11. |
| **Live service config** | None — VideoSummary is single-machine local CLI; no n8n / Datadog / Tailscale / Cloudflare. | **No action.** |
| **OS-registered state** | None — verified by inspection of `agent/` for Task Scheduler / pm2 / launchd patterns; none exist. The only OS interaction is ffmpeg / yt-dlp subprocess, neither of which registers persistent state. | **No action.** |
| **Secrets/env vars** | `VE_KEY_CHEAP` / `DOUYIN_COOKIES_FILE` / `HF_TOKEN` (all CLAUDE.md-documented) — none are referenced by `agent/index.py` (Phase 11 is pure-local index manipulation, no API). | **No action.** |
| **Build artifacts** | None — VideoSummary has no `egg-info` / build output (no `pyproject.toml` per CONVENTIONS.md). Phase 11 doesn't change packaging. | **No action.** Note: `tests/_tmp_topics/.gitkeep` was added Phase 10; Phase 11 will need `tests/_tmp_index/.gitkeep` for ASCII-safe tmpdir (mirror Phase 10 D-19 pattern). |

**Summary:** Phase 11 has **zero migration burden**. New sidecars only. The only forward-compat concern is Phase 12 backfill, which is explicitly out-of-scope for Phase 11.

## Common Pitfalls

### Pitfall 1: K5 source-grep self-match on docstrings

**What goes wrong:** The K5 test `test_K5_module_index_no_summary_writes` does `inspect.getsource()` and asserts no `summary.md` literal. If `agent/index.py` docstring says "Phase 7.6 hook reads `summary.md` and pipes JSON to this CLI", the test FAILS even though there's no actual write.
**Why it happens:** `inspect.getsource()` returns the entire source including comments + docstrings.
**How to avoid:** Use prose ("the slug summary file" / "per-slug summary artifact") in docstrings — Phase 10 plan-01 deviation #2 lesson, applied to `agent/topics.py` already (line 11-17 of agent/topics.py: "the slug summary file" / "the slug plan file" / "per-slug index sidecars"). Phase 11 MUST follow same convention.
**Warning signs:** Test failure: `K5 violation: agent/index.py contains forbidden literal 'summary.md'`.

### Pitfall 2: 17 archives lack plan.md → schema fail when generator runs without fallback

**What goes wrong:** Generator reads `output/<slug>/plan.md` → file missing → ValueError → `validate_per_slug_index` rejects empty `mode` field. Phase 12 backfill on 17 archives ALL fail.
**Why it happens:** plan.md is a Phase 5 D-21 artifact (mode classification, 5-field YAML front-matter). 17 v1.0 archives predate it. Of the 33 candidate archives this branch has, NONE have plan.md (verified via `ls output/<slug>/`).
**How to avoid:** Generator (Claude prompt side, NOT CLI) checks `plan.md` exists; if missing, `mode = "replicate-guide"` per CLAUDE.md fallback rule. This is a Claude-side concern (Phase 7.6 hook prompt instructs Claude to default), but Phase 11 unit test should cover the validator: `validate_per_slug_index({"mode": "replicate-guide", ...})` passes for all 4 modes.
**Warning signs:** Phase 12 dry-run: `IndexValidationError: 'mode' must be one of (...) got ''`.

### Pitfall 3: `_glossary.md` doesn't exist — empty H2 candidate set causes regex error

**What goes wrong:** `_glossary.md` is missing from this branch + 17 archives + 16 douyin/BV samples (verified via `Glob output/_glossary.md` → "No files found"). If Pattern 4 helper assumes file exists, FileNotFoundError.
**Why it happens:** v1.1 TEACH-A3 `cross_slug_glossary` is opt-in. No 17-archive slug nor any sample on this branch has the marker enabled.
**How to avoid:** Pattern 4 returns `[]` on missing file (NOT raise). Generator handles vacuously-empty candidate set: keywords[] becomes "whatever Claude thinks fits" (no canonical reuse possible for this slug). KB-03 / D-06.4 test must include "missing glossary" case.
**Warning signs:** `FileNotFoundError: output/_glossary.md` in unit test or Phase 7.6 first invocation.

### Pitfall 4: Chapter heading regex doesn't match across modes

**What goes wrong:** Tempting to derive `chapters[]` mechanically by regexing `^## \[(\d{2}:\d{2})\] (.+)$`. Works on `interview-distillation` (douyin_karpathy_llm_wiki: 9 timestamped H2). Fails on `replicate-guide` (BV132wizyEEB uses `## 一、Chinese-numeral`, no timestamp). Fails on mixed (`douyin_claude_code_hooks` has 6 with `[HH:MM]` and 2 without).
**Why it happens:** Mode skeletons in CLAUDE.md `### Mode: ...` blocks use different chapter heading conventions intentionally (each mode has a natural shape).
**How to avoid:** Generator (Claude side) infers `chapters[].start` per chapter — NOT a CLI regex. Phase 7.6 prompt instructs Claude to read summary.md + paragraphs.json (which has true `start`/`end` floats) + map H2 chapter heading to nearest paragraph's `start` value. K5 invariant — Claude is decider. CLI just validates the JSON has `chapters[i].start` as `(int, float)`, not the inference logic.
**Warning signs:** Hard-coded regex in `agent/index.py` parsing `summary.md` — automatic test failure (Pitfall 1) or wrong chapters on non-uniform headings.

### Pitfall 5: Aggregator drift — write per-slug but rebuild fails silently

**What goes wrong:** `cmd_index_write` writes per-slug atomically; then aggregator rebuild raises (e.g., another concurrent process holds `.index.lock` past timeout). User sees "written" but `output/.index.json` is stale.
**Why it happens:** D-05.2 step (e) "立刻 rebuild" is best-effort if not transactional with step (d).
**How to avoid:** Both per-slug write + aggregator rebuild happen INSIDE the SAME `FileLock(.index.lock)` context (per Pattern 2). On exception during rebuild, the per-slug index.json is already on-disk → next `index rebuild` invocation will pick it up + mark as `stale_detected`. **Acceptable degradation:** stale aggregator + per-slug fresh — Pattern 6 detects it. Don't try to roll back the per-slug write — that's a worse failure mode.
**Warning signs:** `stale_detected: ["BV..."]` in `index rebuild --json` output ≠ recently-written slug.

### Pitfall 6: Idempotency check using bytewise compare may differ from semantic-equal

**What goes wrong:** `index write --from-stdin` with same logical JSON but different key order or whitespace → bytewise compare says "differ" → overwrites unnecessarily.
**Why it happens:** Python `json.dumps(..., indent=2)` is deterministic for a given dict if you control key order, but stdin JSON might come from `jq` or hand-edited shell heredoc with different formatting.
**How to avoid:** D-05.6 says idempotent on byte-equal stdin (overwrite otherwise). This is acceptable — overwrite with identical content is a no-op semantically. Skip optimization is nice-to-have, not contract. **Recommendation:** parse stdin JSON, re-serialize via `json.dumps(parsed, ensure_ascii=False, indent=2)`, then bytewise compare. Avoids spurious "differ" from whitespace.
**Warning signs:** Phase 7.6 hook test: write same JSON 5x → all 5 say `action: "written"` (should be 4× `skipped`).

### Pitfall 7: D-29 byte-equal regression accidentally breaks because Phase 11 reads via dirty subprocess

**What goes wrong:** Phase 11 generator (Claude-side) accidentally writes to `output/<slug>/summary.md` via Edit tool (e.g., to "fix" a typo found while reading). Replay test FAILS.
**Why it happens:** Generator workflow involves multiple Read calls; if any tool call mutates a 4-core artifact, D-29 breaks.
**How to avoid:** Phase 11 close gate (D-07.1) = `python scripts/replay_v10_archives.py` → 33/0/30. Run BEFORE marking phase shippable. Phase 7.6 hook prompt explicitly forbids Edit on the 5 D-29 artifacts. K5 source-grep test catches CLI-side leak; only human discipline + replay gate catches Claude-side leak.
**Warning signs:** `replay_v10_archives.py` summary line: `Summary: 32 PASS / 1 FAIL` — investigate which slug + which artifact diff.

## Code Examples

Verified patterns from shipped codebase. **All examples are sketches** — the planner finalizes them.

### Example A: full `agent/index.py` skeleton (mirrors `agent/topics.py`)

```python
# agent/index.py
"""v1.2 knowledge-base per-slug index + top-level aggregator (Phase 11 D-01..D-10).

Reads (never writes) decision artifacts via Claude-side prompt; this module
is a mechanical writer that ingests Claude-decided JSON via stdin.

K5 boundary:
  - This module WRITES to per-slug index.json AND output/.index.json ONLY.
  - It NEVER writes to per-slug decision artifacts (the slug summary file /
    the slug plan file / paragraphs / segs / meta).
  - Source-grep tests (tests/test_k5_emitters.py) verify the literals
    summary.md / plan.md / paragraphs.json / segs.json / meta.json /
    schedule.json never appear here. Note: this docstring deliberately uses
    prose ("the slug summary file") to avoid regex self-match.

Schema (locked in 11-CONTEXT.md D-01.1..D-01.5):
  - per-slug: 8 fields {slug, title, duration_s, mode, topics[], keywords[],
    tldr_oneliner, chapters[]} where chapters[i] = {title, start, excerpt}
  - top-level: flat {<slug>: <per-slug>, ...}, no backlinks (per D-07)

Idempotency:
  - write_per_slug_index on byte-equal stdin → action="skipped"
  - rebuild_aggregator: always atomic-write (full re-scan)

Concurrency:
  - All writers acquire output/.index.lock via FileLock context manager.
  - Reads are lock-free (D-09.4 — concurrent reads don't conflict).

Cross-module dependencies (stable contracts):
  - agent.topics.read_topics — Phase 10 ship, white-list lookup
  - agent.topics.append_pending — Phase 10 ship, novel-topic submission
  - agent._lock.FileLock — v1.0 Phase 06 ship
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from pathlib import Path

from agent._lock import FileLock, LockContended

log = logging.getLogger(__name__)

INDEX_FILENAME = "index.json"           # per-slug
AGGREGATOR_FILENAME = ".index.json"     # top-level
LOCK_FILENAME = ".index.lock"
DEFAULT_OUTPUT_DIR = "output"

VALID_MODES = (
    "replicate-guide",
    "concept-explanation",
    "extension-applications",
    "interview-distillation",
)

REQUIRED_FIELDS = ("slug", "title", "duration_s", "mode",
                   "topics", "keywords", "tldr_oneliner", "chapters")
CHAPTER_FIELDS = ("title", "start", "excerpt")

_GLOSSARY_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


class IndexValidationError(Exception):
    """Raised when per-slug index data fails 8-field schema validation."""


def _atomic_write(target: Path, content: str) -> None:
    """tempfile + os.fsync + os.replace; mirror agent/glossary.py:_atomic_write."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".tmp",
        dir=target.parent, delete=False,
    )
    try:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, target)
    except Exception:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
        raise


def validate_per_slug_index(d: dict, *, approved_topics: set[str] | None = None) -> None:
    """8-field schema check; raise IndexValidationError on first failure.

    Args:
        d: parsed index data.
        approved_topics: optional whitelist set; if provided, every non-pending
            topic must be in the set (D-05.2 step c).

    Raises:
        IndexValidationError on any malformed field or topic-not-in-whitelist.
    """
    # ... [Pattern 1 body inlined — see § Architecture Patterns]


def read_per_slug_index(slug_dir: Path) -> dict | None:
    """Return parsed per-slug index data or None if missing/corrupt."""
    p = Path(slug_dir) / INDEX_FILENAME
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        validate_per_slug_index(d)
        return d
    except (OSError, json.JSONDecodeError, IndexValidationError) as e:
        log.warning("read_per_slug_index: skipping %s (%s)", p, e)
        return None


def write_per_slug_index(...) -> dict:
    # ... [Pattern 2 body — see § Architecture Patterns]


def rebuild_aggregator(...) -> dict:
    # ... [Pattern 3 body — see § Architecture Patterns]


def read_aggregator(output_dir: Path = Path("output")) -> dict:
    """Read output/.index.json; return {} if missing or corrupt."""
    p = Path(output_dir) / AGGREGATOR_FILENAME
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("read_aggregator: %s unreadable (%s)", p, e)
        return {}


def _flatten_approved_names(approved_tree: list[dict]) -> set[str]:
    """Recursively flatten {name, subtopics:[...]} tree into a set of all names."""
    names: set[str] = set()
    def walk(items):
        for it in items:
            names.add(it["name"])
            walk(it.get("subtopics", []))
    walk(approved_tree)
    return names


def glossary_h2_anchors(glossary_path: Path) -> list[str]:
    """Extract canonical H2 anchor terms from _glossary.md (D-06.1).

    Returns [] if the file doesn't exist (vacuously-empty case — see Q-A).
    """
    p = Path(glossary_path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8")
    return [m.group(1).strip() for m in _GLOSSARY_H2_RE.finditer(text)]
```

### Example B: CLI handler signatures (in `agent/tools.py`)

```python
def cmd_index_write(args):
    """Phase 11 D-05: write per-slug index.json + immediate aggregator rebuild.

    K5: this CLI ingests Claude-decided JSON via stdin. Module source contains
    zero of the literals for the slug summary / plan / paragraphs / segs /
    meta artifacts. The literal index dot json is the legitimate write target.

    Stdout JSON locked byte-equal to D-05.5.
    """
    from agent.index import write_per_slug_index, IndexValidationError, AGGREGATOR_FILENAME

    if not args.from_stdin:
        print("error: index write requires --from-stdin (8-field JSON on stdin)",
              file=sys.stderr)
        sys.exit(1)
    raw = sys.stdin.read()
    if not raw.strip():
        print("error: --from-stdin requires JSON input on stdin; got empty",
              file=sys.stderr)
        sys.exit(1)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: malformed JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)
    # Inject slug if stdin omitted (defense-in-depth — D-04 specifics example).
    if isinstance(payload, dict) and "slug" not in payload:
        payload["slug"] = args.slug
    elif isinstance(payload, dict) and payload.get("slug") != args.slug:
        print(f"error: stdin JSON slug={payload.get('slug')!r} does not match "
              f"--slug {args.slug!r}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    slug_dir = out_dir / args.slug
    if not slug_dir.exists():
        print(f"error: slug dir not found: {slug_dir}", file=sys.stderr)
        sys.exit(1)

    try:
        result = write_per_slug_index(
            slug_dir, payload,
            output_dir=out_dir, timeout=args.timeout,
            force=args.force,
        )
    except IndexValidationError as e:
        print(f"error: schema validation failed: {e}", file=sys.stderr)
        sys.exit(1)
    except LockContended as e:
        print(f"error: lock contended: {e}", file=sys.stderr)
        sys.exit(1)

    _log(args.slug, "index_write", f"{result['action']}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"{result['action']}: {result['_index_path']}")


def cmd_index_rebuild(args):
    """Phase 11 D-04: manual rebuild of output/.index.json from all
    output/<slug>/index.json files.

    K5: read-only on per-slug index sidecars; writes only the top-level
    aggregator. Module source contains zero of the literals for the slug
    summary / plan / paragraphs / segs / meta artifacts.

    Stdout JSON locked byte-equal to D-04.4.
    """
    from agent.index import rebuild_aggregator, AGGREGATOR_FILENAME

    out_dir = Path(args.output_dir)
    try:
        result = rebuild_aggregator(out_dir, timeout=args.timeout)
    except LockContended as e:
        print(f"error: lock contended: {e}", file=sys.stderr)
        sys.exit(1)

    aggregator = out_dir / AGGREGATOR_FILENAME
    out = {
        "action": "rebuilt",
        "slugs_included": result["slugs_included"],
        "slugs_skipped": result["slugs_skipped"],
        "stale_detected": result["stale_detected"],
        "_index_path": str(aggregator),
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"rebuilt: {result['slugs_included']} slugs included, "
              f"{len(result['slugs_skipped'])} skipped, "
              f"{len(result['stale_detected'])} stale")
        for s in result["slugs_skipped"]:
            print(f"  SKIPPED {s['slug']}: {s['reason']}", file=sys.stderr)

    # D-04.3 exit code: ≥1 valid → 0; else 1.
    if result["slugs_included"] == 0 and result["slugs_skipped"]:
        sys.exit(1)
```

### Example C: Phase 7.6 hook insertion in CLAUDE.md (verbatim from CONTEXT specifics)

**Insertion point:** between line 1770 (final `> 完整规则 + verifier prompt 全文 + UNRESOLVED.md 模板见 § v1.1 校对自动化 (Phase 09).` of Phase 7.5 block) and line 1772 (`### Phase 8: 收尾`).

**Content (verbatim from 11-CONTEXT.md `<specifics>` block, expanded):**

```markdown
### Phase 7.6: 知识库索引（v1.2 ship 后默认启用）

> **v1.2 hook (默认)**：满足以下全部 3 条才走 Phase 7.6（Claude is decider）：
> 1. `output/_topics.md` 存在（v1.2 Phase 10 ship 后默认存在）
> 2. `output/<slug>/summary.md` 已写完（Phase 7 完成 + Phase 7.5 verifier 已通过）
> 3. `output/<slug>/index.json` 不存在 OR 用户显式要求重新生成

**Phase 7.6 步骤**（按顺序）：

1. **Read 5 个文件**: `output/<slug>/summary.md` / `output/<slug>/meta.json` / `output/<slug>/plan.md` / `output/_glossary.md` / `output/_topics.md`
   - `plan.md` 缺失（17 archives 情况）→ `mode = "replicate-guide"` fallback per CLAUDE.md
   - `_glossary.md` 缺失（v1.1 marker 未启用）→ keywords 候选集为空，由 Claude 自由提议
2. **推断 8 字段** (slug/title/duration_s/mode/topics/keywords/tldr_oneliner/chapters):
   - `topics` 必须从 `_topics.md` Approved 段选；不合适 → 用 `pending: <new-name>` 形态（CLI 会自动 append 到 Pending）
   - `keywords` 优先复用 `_glossary.md` H2 anchors 的 canonical 形式（byte-equal 完整术语 e.g., `LoRA (Low-Rank Adaptation)` 不是 `LoRA`）
   - `chapters[].start` 来自 `paragraphs.json` 时间窗 — Claude 把 H2 章节标题映射到最接近的 paragraph `start`
3. **Pipe JSON 给 CLI**:
   ```bash
   python -m agent.tools index write --slug <slug> --from-stdin <<EOF
   {"slug": "<slug>", "title": "...", "duration_s": ..., "mode": "...",
    "topics": [...], "keywords": [...], "tldr_oneliner": "...",
    "chapters": [{"title": "...", "start": ..., "excerpt": "..."}, ...]}
   EOF
   ```
4. **CLI 自动**: 验证 schema → 写 `output/<slug>/index.json`（atomic）→ rebuild 顶层 `output/.index.json`（atomic）→ 输出 JSON `{"action": "written", ...}`
5. **错误处理**:
   - schema 校验失败 → CLI exit 1 + stderr 详细错误；Claude 修正 JSON 重试
   - topic 不在白名单 AND 非 `pending: <name>` 形态 → 同上 fail-fast；Claude 改写为 `pending: <name>` 后重试
```

**Why this insertion point:** Phase 7.5 ends with `> 完整规则 + verifier prompt 全文 + UNRESOLVED.md 模板见 § v1.1 校对自动化 (Phase 09).` (line 1770). Phase 8 starts with `### Phase 8: 收尾` (line 1772). Insert blank line + Phase 7.6 block + blank line. Indices all shift +N where N is the line count of the Phase 7.6 block — no other anchors change.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hand-rolled subprocess + flock POSIX-only | `agent/_lock.FileLock` (msvcrt + fcntl + stale-PID) | v1.0 Phase 06 (PARA-01) | Cross-platform; 17 K5 tests cover edges |
| Direct `Path.write_text` for JSON artifacts | `agent.io.write_json_atomic` (tempfile + retry) OR `agent/glossary.py:_atomic_write` (tempfile + fsync, no retry) | v1.0 Phase 02 (RES-03) | Crash-safe; PermissionError retry on Windows Defender drift; index.json should mirror simpler glossary pattern (writes always inside FileLock) |
| Topic taxonomy as ad-hoc tag set | `output/_topics.md` Approved + Pending two-segment governance | Phase 10 (D-01..D-08) | K5: Claude proposes → user reviews; novel topics auto-pending |
| Per-slug summary as the only artifact | per-slug index.json sidecar + top-level .index.json aggregator | Phase 11 (D-01..D-04) | Claude-queryable knowledge base at 5-10 KB Read cost |

**Deprecated/outdated:**
- None — Phase 11 is purely additive. No prior approach to deprecate. The 17 v1.0 / 16 douyin/BV archives become Phase 12's backfill targets, but their summary.md / segs.json / paragraphs.json / meta.json remain D-29 byte-equal.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib) — Phase 10's `tests/test_topics.py` shape |
| Config file | none — discoverable via `python -m unittest discover tests` |
| Quick run command | `python -m unittest tests.test_index -v` |
| Full suite command | `python -m unittest discover tests -v` |
| Phase gate | `python scripts/replay_v10_archives.py` → 33/0/30 PASS before Phase 11 close (D-07.1) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KB-01 | 8-field schema lock | unit | `python -m unittest tests.test_index.TestValidate -v` | ❌ Wave 0 (NEW: tests/test_index.py) |
| KB-01 | mode fallback `replicate-guide` accepted by validator | unit | `python -m unittest tests.test_index.TestValidate.test_all_4_modes_accepted -v` | ❌ Wave 0 |
| KB-02 | Phase 7.6 hook end-to-end (manual gate; Claude session) | manual | n/a — see § Open Questions Q-F | ❌ Wave 0 (manual UAT gate) |
| KB-03 | keywords reuse `_glossary.md` H2 anchors byte-equal canonical | unit | `python -m unittest tests.test_index.TestGlossaryH2 -v` | ❌ Wave 0 |
| KB-03 | empty `_glossary.md` (file missing) → glossary_h2_anchors returns [] | unit | `python -m unittest tests.test_index.TestGlossaryH2.test_missing_file_returns_empty -v` | ❌ Wave 0 |
| KB-04 | `output/.index.json` schema = flat dict, no backlinks | unit | `python -m unittest tests.test_index.TestRebuild.test_aggregator_schema -v` | ❌ Wave 0 |
| KB-04 | atomic rebuild idempotent | unit | `python -m unittest tests.test_index.TestRebuild.test_idempotent -v` | ❌ Wave 0 |
| KB-04 | concurrent rebuild + write race (multiprocessing.spawn) | unit | `python -m unittest tests.test_index.TestAtomic.test_concurrent_writes -v` | ❌ Wave 0 |
| KB-05 | `index rebuild` stale detection | unit | `python -m unittest tests.test_index.TestRebuild.test_stale_detection -v` | ❌ Wave 0 |
| KB-05 | `index rebuild` skip-on-malformed | unit | `python -m unittest tests.test_index.TestRebuild.test_skip_malformed -v` | ❌ Wave 0 |
| KB-05 | exit code 1 if 0 valid | unit | `python -m unittest tests.test_index.TestRebuild.test_exit_code_no_valid -v` | ❌ Wave 0 |
| KB-06 | D-29 replay 33/0/30 post-Phase-11 | integration | `python scripts/replay_v10_archives.py` | ✅ (script exists, ran during Phase 10) |
| D-10.1 | K5 source-grep `agent/index.py` no D-29 literals | unit | `python -m unittest tests.test_k5_emitters.TestK5BoundaryPhase07.test_K5_module_index_no_summary_writes -v` | ❌ Wave 0 (extend test_k5_emitters.py) |
| D-10.1 | K5 `cmd_index_write` no D-29 literals | unit | `python -m unittest tests.test_k5_emitters.TestK5BoundaryPhase07.test_K5_cmd_index_write_no_d29_writes -v` | ❌ Wave 0 |
| D-10.1 | K5 `cmd_index_rebuild` no per-slug write patterns | unit | `python -m unittest tests.test_k5_emitters.TestK5BoundaryPhase07.test_K5_cmd_index_rebuild_read_only_per_slug -v` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `python -m unittest tests.test_index tests.test_k5_emitters -v` (~ 2-3 s)
- **Per wave merge:** `python -m unittest discover tests -v` (~ 2.5 s based on Phase 10 baseline of 224 tests in 2.37 s)
- **Phase gate:** Full suite green + `python scripts/replay_v10_archives.py` 33/0/30 PASS before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_index.py` — covers KB-01, KB-03, KB-04, KB-05 (5 classes mirroring tests/test_topics.py shape: TestValidate / TestRead / TestWrite / TestRebuild / TestGlossaryH2 / TestAtomic)
- [ ] `tests/_tmp_index/.gitkeep` — ASCII-safe per-test tmpdir root (mirror Phase 10 D-19 lesson re: Windows zh-CN GBK code-page)
- [ ] `tests/test_k5_emitters.py` extension — 3 new tests inside existing `TestK5BoundaryPhase07` class (D-10.1)
- [ ] No framework install needed (stdlib `unittest`)

## Security Domain

> Per `.planning/config.json` — security_enforcement is implicit. Phase 11 ships pure local CLI + filesystem operations; ASVS surface is minimal.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | local CLI; no auth surface |
| V3 Session Management | no | no sessions |
| V4 Access Control | no | single-user single-machine |
| V5 Input Validation | yes | stdin JSON validation via `validate_per_slug_index` (Pattern 1); Approved-set whitelist for topics; mode enum check |
| V6 Cryptography | no | no crypto |
| V7 Error Handling | yes | structured stderr errors; no sensitive data in error messages (slug names + field names only) |
| V12 File & Resource | yes | atomic write + FileLock prevent partial-state corruption; `_validate_out_path` CJK rejection (already in `agent/tools.py`) covers Windows zh-CN subprocess hazard |

### Known Threat Patterns for Python CLI + filesystem

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stdin JSON injection (e.g., embedded ANSI escape in `tldr_oneliner` field) | Tampering | Validate string field types; output via `json.dumps(ensure_ascii=False)` already escapes control chars |
| Path traversal in `--slug` arg (e.g., `--slug ../etc/passwd`) | Tampering | `slug_dir = out_dir / args.slug` then `slug_dir.exists()` check; combined with `_validate_out_path` CJK reject. Recommended: also verify `slug_dir.parent == out_dir.resolve()` to prevent `--slug ../X` traversal |
| Symlink TOCTOU on `output/<slug>/index.json` | Tampering | Single-user single-machine; symlinks not in threat model. atomic write via `os.replace` is symlink-following on POSIX (acceptable). |
| Concurrent `index write` from 2 terminals | DoS | FileLock with stale-PID handover (`agent/_lock.FileLock`); 10s timeout default per D-09 |
| Forge per-slug index.json (manual edit between writes) | Integrity | `read_per_slug_index` calls validator; rebuild quarantines invalid as `slugs_skipped[]` (D-04.3) |

**Recommendation:** add path-traversal hardening to `cmd_index_write`:

```python
slug_dir = out_dir / args.slug
slug_dir_resolved = slug_dir.resolve()
out_dir_resolved = out_dir.resolve()
if not str(slug_dir_resolved).startswith(str(out_dir_resolved) + os.sep):
    print(f"error: --slug must be under --output-dir", file=sys.stderr)
    sys.exit(1)
```

This is defense-in-depth — primary mitigation is single-user trust boundary.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Phase 11 doesn't need `state.jsonl` events for `index write/rebuild` | Standard Stack → Supporting; Pitfall 5 | Low — `glossary append` (Phase 08) also doesn't emit. Adding events later is non-breaking. [ASSUMED based on CONTEXT.md `<code_context>` "State events: Phase 11 不需要 state.jsonl 事件"] |
| A2 | `agent/topics.py:_resolve_paths` is a stable internal helper safe to import from `cmd_topics_*` (mirror for index CLI) | Pattern 5 | Low — Phase 10 already does this (`from agent.topics import write_approved_taxonomy, _resolve_paths`); Phase 11 mirrors. [ASSUMED based on Phase 10 ship pattern] |
| A3 | `_glossary.md` may exist on machine A but not machine B; generator handles both | Pitfall 3; Pattern 4 | Low — covered by Pattern 4 vacuous-empty fallback. [VERIFIED: `Glob output/_glossary.md` returns "No files found" on this branch] |
| A4 | 17 archives lack `plan.md`; backfill MUST fall back to `replicate-guide` mode | Pitfall 2; KB-01 test row | Low — verified by `ls output/<slug>/`; CLAUDE.md explicit fallback rule. [VERIFIED via Bash: archived dirs contain only meta.json/segs.json/paragraphs.json/summary.md/audio.wav/frames/video.mp4] |
| A5 | `chapters[].start` is float seconds (D-01.3); but generator infers from paragraphs.json since H2 heading conventions vary across modes | Pitfall 4; Phase 7.6 step 2 | Medium — if Claude regex'es summary.md alone instead of cross-referencing paragraphs.json, chapters[].start will be wrong on `replicate-guide` mode. Mitigation: Phase 7.6 prompt explicitly instructs cross-ref. [ASSUMED based on chapter heading inspection of 3 modes; not yet verified by end-to-end test] |
| A6 | Manual UAT (KB-02 Phase 7.6 hook E2E) is acceptable as deferred-to-user gate | Validation Architecture; Q-F | Low — mirrors v1.1 phase 09 P-09 token budget gate (also manual UAT). Pattern is established. [ASSUMED based on Phase 09 SUMMARY.md ship pattern] |
| A7 | Lexicographic dict ordering for `output/.index.json` is acceptable (no contractual ordering required) | Pattern 3; Q-E | Low — CONTEXT.md explicitly says "Claude 选自然形态；测试不强约束". Lexicographic is the most reproducible default. [VERIFIED via 11-CONTEXT.md `<decisions>` Claude's Discretion bullet 5] |

## Open Questions

### Q-A. `_glossary.md` H2 anchor parsing edge cases

**What we know:** Phase 10 plan-02 confirmed `output/_glossary.md` does not yet exist on this branch (no v1.1 slug has exercised TEACH-A3). v1.1 spec example: `## LoRA (Low-Rank Adaptation)`. `agent/glossary.py:_H2_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)` is the established pattern (anchored, MULTILINE flag).

**What's unclear:**
- Edge cases when `_glossary.md` DOES eventually populate: are there any non-` ` whitespace characters between `##` and the term?
- Trailing whitespace handling (`## LoRA   ` with trailing spaces)?
- Sub-headings (`### sub-anchor`) — should they be excluded?

**Recommendation:** Use `_GLOSSARY_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)` (Pattern 4) with `re.MULTILINE` and non-greedy `.+?` + trailing `\s*` to swallow stray whitespace. Match `^##` strictly (NOT `^### `). Reuse `agent/glossary.py:_H2_RE` shape verbatim — same regex used by 17 K5 tests; no precedent breaks.

**Test coverage (KB-03 / D-06.4):**
- mock `_glossary.md` containing `## LoRA (Low-Rank Adaptation)\n- [BVxxx](BVxxx/summary.md)\n\n## RAG (Retrieval-Augmented Generation)\n` → `glossary_h2_anchors()` returns `["LoRA (Low-Rank Adaptation)", "RAG (Retrieval-Augmented Generation)"]`
- mock `_glossary.md` MISSING → returns `[]` (Pitfall 3 case)
- mock `_glossary.md` containing `### sub-section` H3 → NOT matched (anchored `^##\s+`)

**Verdict:** RESOLVED — pattern is identical to Phase 08 ship.

### Q-B. CLAUDE.md Phase 7.6 hook insertion exact spot

**What we know:**
- `### Phase 7: 完整代码 + 输出` starts at line 1740
- `### Phase 7.5: 校对自动化（v1.1 校对自动化 — Phase 09）` starts at line 1747
- Phase 7.5 block ends at line 1770 with `> 完整规则 + verifier prompt 全文 + UNRESOLVED.md 模板见 § v1.1 校对自动化 (Phase 09).`
- `### Phase 8: 收尾` starts at line 1772
- Line 1771 is a blank line separating Phase 7.5 from Phase 8.

**What's unclear:**
- Should Phase 7.6 also have a corresponding `## v1.2 知识库索引层` H2 (mirror v1.1 Phase 08's `## v1.1 自适应教学文档增强` at line 1145)?

**Recommendation:**
- **Insert Phase 7.6 between line 1771 (blank) and line 1772 (`### Phase 8`).** Specifically: replace line 1771 with `\n\n### Phase 7.6: 知识库索引（v1.2 ship 后默认启用）\n\n[block per § Code Examples Example C]\n\n` (Edit tool `old_string` = the line-1770-content + `\n\n### Phase 8: 收尾\n` and `new_string` = old_string but with Phase 7.6 block prepended after the blank line).
- **Defer the `## v1.2 知识库索引层` H2 to Phase 12** — Phase 12 KB-14 introduces the natural-language recommendation prompt rule which is the right home for the H2. Phase 11 only adds the workflow hook (no rule extension yet).

**Verdict:** RESOLVED for Phase 11 scope. The H2 deferral is a clarification of CONTEXT.md `<canonical_refs>` line "本 phase 加 `## v1.2 知识库索引层` H2 段" — recommendation: scope this to Phase 12 to avoid premature H2 with empty rule body. If planner disagrees, can ship empty H2 in Phase 11 with TODO marker pointing to Phase 12 (less clean).

### Q-C. tldr_oneliner / chapters[] feasibility check across 3 modes

**What we know (verified):**
- `BV132wizyEEB` (replicate-guide, 1:14, Chinese-numeral H2): 7 H2 chapters — `## 一、用 Gemini 生成像素风场景地图` ... `## 提示词速查表`. Inline `[HH:MM]` timestamps inside chapter bodies, NOT in H2 headings.
- `douyin_karpathy_llm_wiki` (interview-distillation, 4:02, timestamped H2): 12 H2 chapters; 9 with `## [HH:MM] topic` format. Includes opening `**一句话结论**` block.
- `douyin_claude_code_hooks` (extension-applications, 1:08, mixed H2): 8 H2 — 6 with `[HH:MM]`, 2 without (`## 本期你将学到`, `## 完整配置代码`, `## 小结`).

**What's unclear (in advance):** Can Claude infer `chapters[].start` (float seconds) reliably for each? Can `tldr_oneliner` (10-50 字) be derived per mode without churn?

**Sample inferred outputs (per Q-C of `<additional_context>`):**

`BV132wizyEEB` proposed index.json (already in CONTEXT specifics):
```json
{"slug":"BV132wizyEEB","title":"1 分钟搞定全套像素风游戏美术：AI 绘画 + 自动抠图全流程","duration_s":74.048,"mode":"replicate-guide","topics":["AI-Art-Generation","Pixel-Art","Nano-Banana"],"keywords":["topdown 视角","像素风","Gemini image-edit","纯色背景抠图"],"tldr_oneliner":"用 Gemini image-edit 生成像素风场景 + 提取物件的 4 步流程","chapters":[{"title":"用 Gemini 生成像素风场景地图","start":6.0,"excerpt":"明确指定'像素场景画师'角色 + 'topdown 俯视视角' + 全景像素风约束"},...]}
```

`douyin_karpathy_llm_wiki` proposed (interview-distillation):
```json
{"slug":"douyin_karpathy_llm_wiki","title":"Karpathy 又被吹爆，但这次可能真不是炒作","duration_s":242.027,"mode":"interview-distillation","topics":["LLM-Concepts","LLM-Wiki","RAG"],"keywords":["LLM Wiki","schema 文件","Compound Engineering","Memex"],"tldr_oneliner":"Karpathy 的 LLM Wiki gist 不是新方法，而是给"让 LLM 维护 wiki"这件事第一次起了名字","chapters":[{"title":"一个 75 行 gist 为什么突然炸了","start":0.0,"excerpt":"方法不新，命名才新——UP 主开场反共识立场"},{"title":"RAG 的顺序搞反了：三层结构才是正解","start":28.0,"excerpt":"Raw / Wiki / Schema 三层 + LLM 是 wiki 维护者而非聊天机器人"},...]}
```

`douyin_claude_code_hooks` proposed (extension-applications):
```json
{"slug":"douyin_claude_code_hooks","title":"Claude Code 系列教程第 6 期：Hooks 事件驱动自动化","duration_s":68.0,"mode":"extension-applications","topics":["AI-Tooling","Claude-Code"],"keywords":["PostToolUse","PreToolUse","Stop","Notification","scan-secrets"],"tldr_oneliner":"Claude Code Hooks 4 类型 × 4 触发事件，最常用的就是 PostToolUse + Command","chapters":[{"title":"什么是 Hooks","start":0.0,"excerpt":"事件驱动 vs 意志驱动 — 流程挂在事件上而不是挂在意志上"},...]}
```

**Recommendation:**
- `tldr_oneliner` 形态 (Claude's Discretion): 10-50 字 hard cap; per-mode tendency:
  - replicate-guide: "用 X 做 Y 的 N 步流程"
  - concept-explanation: "X 不是 Y，而是 Z"
  - extension-applications: "X 在 N 个场景里的应用对比"
  - interview-distillation: "Karpathy/嘉宾的核心判断 + 反共识立场"
- `chapters[].start` derivation: read summary.md H2 timestamps when present (`[HH:MM]` regex); fall back to first paragraph's `start` from paragraphs.json that semantically fits the chapter heading. **Always cross-reference paragraphs.json** for true float seconds (HH:MM is rounded to second).
- The CLI does NOT enforce this — it's Claude's job per K5. CLI just validates `chapters[i].start` is `(int, float)`.

**Verdict:** RESOLVED — feasibility confirmed via 3 sample summaries. Phase 7.6 prompt should explicitly instruct cross-ref of paragraphs.json for `start` precision (per Pitfall 4).

### Q-D. K5 boundary edge case — `cmd_index_rebuild` writes to `output/.index.json` but reads from `output/<slug>/index.json`

**What we know:**
- D-10.1 third test: `test_K5_cmd_index_rebuild_read_only_per_slug` — source must NOT contain write patterns targeting `<slug>/index.json` AND must NOT contain D-29 5 literals.
- `index.json` literal IS allowed (it's the legitimate write target for `output/.index.json`).

**What's unclear:** What's the exact regex distinguishing "write to per-slug" vs "write to top-level"?

**Recommendation:** the regex should target patterns where `<slug>` appears as a path prefix, not the literal string `index.json` alone. Concretely:

```python
# in tests/test_k5_emitters.py — D-10.1 third test
_REBUILD_FORBIDDEN_PER_SLUG_PATTERNS = (
    # Match write APIs whose path arg contains both a slug-like prefix AND index.json:
    # - tempfile.NamedTemporaryFile(... dir=<slug_var>...) → can't catch generically; rely on convention
    # - Path("<slug>") / "index.json" written to → grep for "/ \"index.json\"" or "/ INDEX_FILENAME"
    r"_atomic_write\([^,)]*INDEX_FILENAME",
    r"_atomic_write\([^,)]*[\"']index\.json[\"']",
    r"write_text\([^,)]*INDEX_FILENAME",
    r"os\.replace\([^,)]*INDEX_FILENAME",
)
# But ALLOW writes to AGGREGATOR_FILENAME:
# Test: assert no _REBUILD_FORBIDDEN_PER_SLUG matches AND assert AGGREGATOR_FILENAME literal IS present
```

**Simpler alternative:** test that `cmd_index_rebuild` does NOT contain the import name `write_per_slug_index` (the only function that writes per-slug). If `cmd_index_rebuild` only calls `rebuild_aggregator`, it cannot accidentally write per-slug.

```python
def test_K5_cmd_index_rebuild_read_only_per_slug(self):
    """D-10.1: cmd_index_rebuild must not write to per-slug sidecars; only top-level."""
    src = inspect.getsource(cmd_index_rebuild)
    self.assertNotIn(
        "write_per_slug_index", src,
        "K5 violation: cmd_index_rebuild must not call write_per_slug_index "
        "(rebuild is read-only on per-slug, write-only on top-level aggregator)",
    )
    # Also forbid the 5 D-29 core artifact literals
    for forbidden in ("summary.md", "plan.md", "paragraphs.json", "segs.json", "meta.json"):
        self.assertNotIn(
            forbidden, src,
            f"K5 violation: cmd_index_rebuild contains forbidden literal {forbidden!r}",
        )
```

**Verdict:** RESOLVED — recommend the simpler "no-write-per-slug-import" test. Combined with D-29 literals check, this gives full coverage without regex acrobatics.

### Q-E. Aggregator dict ordering

**What we know:** D-03 / Claude's Discretion bullet 5: "Claude 选自然形态；测试不强约束". CONTEXT.md doesn't lock an order.

**What's unclear:** Lexicographic vs mtime ascending vs insertion order.

**Recommendation:** **Lexicographic by slug name.** Rationale:
1. **Reproducibility** — same input always produces same output bytes. Two terminals running `index rebuild` on identical state produce byte-equal `output/.index.json`. mtime ordering would fail this.
2. **Diff-friendly** — `git diff output/.index.json` between rebuilds shows only true content changes, not reordering churn.
3. **Predictable in Claude consumption** — when Claude does `Read output/.index.json` during recommendation queries (Phase 12), entries appear in a stable order that matches `ls output/`.
4. **Trivial implementation** — `{k: aggregated[k] for k in sorted(aggregated.keys())}` (1 line; Pattern 3).

**Implementation decision:** lock this in 11-PLAN as it's the only deterministic choice. Test asserts: write 3 slugs in order BVc, BVa, BVb → `read_aggregator()` keys are `[BVa, BVb, BVc]`.

**Verdict:** RESOLVED — recommend lexicographic; planner locks this.

### Q-F. D-29 byte-equal verify gate (replay) integration

**What we know:**
- `scripts/replay_v10_archives.py` is shipped (v1.1 Phase 07 PRE-V11-02).
- Phase 10 plan-02 already ran it → 1 PASS / 0 FAIL on worktree (only 1 archive); main has 17 archives + 13 skip dirs = 33/30 total.
- D-07.1 Phase 11 close gate = 33/0/30 PASS.
- D-07.4 generator must NEVER write to summary.md / segs.json / paragraphs.json / meta.json.

**What's unclear:**
- Should the planner add a Wave 0 task that runs replay BEFORE Phase 11 work to capture baseline numbers?
- Should there be a CI/automated invocation, or is human gate sufficient?

**Recommendation:**
- **Pre-Phase-11 baseline capture:** add Wave 0 task `Capture pre-Phase-11 D-29 baseline: run scripts/replay_v10_archives.py and record N/0/M numbers in 11-RESEARCH.md§Verification Architecture comment` — this is defensive (verifies the Phase 10 work didn't break anything before we add Phase 11).
- **Post-Phase-11 close gate:** standard Phase verification step, mandated by D-07.1. Run script → assert 0 FAIL.
- **K5 source-grep tests** (D-10.1) catch CLI-side D-29 leaks at unit test time, complementing replay. The 3 K5 tests + 1 replay run = double coverage.
- **Phase 7.6 hook prompt** (Phase 11 deliverable) should include explicit "Read-only on summary.md / segs.json / paragraphs.json / meta.json" instruction to Claude. This is a prompt-level invariant, not unit-testable.

**Verdict:** RESOLVED — replay run = Phase 11 close gate; pre-Phase-11 baseline run = Wave 0 defensive task; K5 tests cover CLI-side; prompt covers Claude-side.

### Q-G. CLI `--from-stdin` JSON shape edge cases

**What we know:** Phase 10 `cmd_topics_bootstrap` handles 4 edge cases for stdin JSON:
1. Missing `--from-stdin` flag → `error: bootstrap requires --from-stdin` exit 1
2. Empty stdin → `error: --from-stdin requires JSON input on stdin; got empty` exit 1
3. Malformed JSON → `error: malformed JSON on stdin: <e>` exit 1
4. Missing top-level wrapping key (`taxonomy` for topics) → `error: stdin JSON must have top-level 'taxonomy' key` exit 1

**What's unclear (parallel for `index write`):**

1. **Empty stdin:** same as Phase 10 — `error: --from-stdin requires JSON input on stdin; got empty` exit 1.
2. **Malformed JSON:** same — `error: malformed JSON on stdin: <e>` exit 1.
3. **Missing `slug` field in stdin JSON:** D-05 specifics example says CLI auto-injects from `--slug` arg if missing — accept silently.
4. **`slug` field MISMATCH with `--slug` arg** (e.g., stdin says `"slug": "BVabc"` but `--slug BVxyz`): fail-fast with `error: stdin JSON slug={...} does not match --slug {...}` exit 1.
5. **Schema-invalid 8 fields** (e.g., `mode: "wrong-mode"`): caught by `validate_per_slug_index` → `IndexValidationError` → caught by `cmd_index_write` → `error: schema validation failed: <e>` exit 1.
6. **Topic not in whitelist** (no `pending: ` prefix, not in Approved): same as #5 path — `IndexValidationError` raised by validator → exit 1.
7. **Slug dir doesn't exist on disk** (`--slug NotARealSlug`): `error: slug dir not found: <path>` exit 1 (per cmd_index_write Example B).
8. **Wrapping object** (e.g., stdin `{"index": {...}}` instead of `{...}`): D-05 says no wrapping — treat as schema error (`missing required field: 'slug'` etc.). Could add explicit detection: if top-level dict has only `"index"` key, hint at "stdin should be unwrapped 8-field object".

**Recommendation:** match Phase 10's error message style verbatim — same prefix ("error: "), same stderr stream, same exit code 1. K5 boundary preserved. See § Code Examples Example B.

**Test coverage (KB-01 / KB-05):**
- `tests/test_index.py:TestCLIWriteEdges` class (5 cases above 1, 2, 3, 4, 7)
- Coverage of #5 / #6 happens at `TestValidate` class via direct unit test of `validate_per_slug_index`

**Verdict:** RESOLVED — pattern is established; Phase 11 mirrors Phase 10.

## Environment Availability

> Phase 11 has no external dependencies (pure stdlib + agent stack). Step 2.6 SKIPPED.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | runtime | ✓ | 3.13 (per CONVENTIONS.md primary) | — |
| `agent.topics` (Phase 10 ship) | Phase 11 generator import contract | ✓ | shipped 2026-05-03 | — |
| `agent._lock.FileLock` | `output/.index.lock` | ✓ | shipped v1.0 Phase 06 | — |
| `agent.glossary._atomic_write` (pattern reference) | `agent/index.py:_atomic_write` skeleton | ✓ | shipped v1.1 Phase 08 | — |
| `output/_topics.md` (Phase 10 ship) | topic whitelist | ✓ | shipped 2026-05-03; 24 nodes | — |
| `output/_glossary.md` | keywords canonical reuse | ✗ | not yet populated | empty H2 candidate set; Pattern 4 returns `[]`; Claude proposes new keywords (Q-A) |
| `scripts/replay_v10_archives.py` | D-29 close gate | ✓ | shipped v1.1 Phase 07 | — |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** `output/_glossary.md` (vacuously-empty handled in Pattern 4).

## Sources

### Primary (HIGH confidence)

- `.planning/phases/11-per-slug-index-json-aggregator-phase76-hook/11-CONTEXT.md` — 10 D-XX decisions verbatim
- `.planning/REQUIREMENTS.md` — KB-01..KB-06 atomic statements
- `.planning/ROADMAP.md` Phase 11 — 5 SC byte-level
- `.planning/v1.2-CANDIDATES.md` — D-01..D-08 architectural decisions
- `.planning/phases/10-topic-taxonomy-governance-bootstrap-cli/10-01-SUMMARY.md` — Phase 10 API surface
- `.planning/phases/10-topic-taxonomy-governance-bootstrap-cli/10-02-SUMMARY.md` — taxonomy ground truth (5 cat / 24 nodes)
- `agent/topics.py` — verified verbatim (read full source for pattern transfer)
- `agent/glossary.py` — verified verbatim (`_H2_RE` regex source-of-truth + `_atomic_write` pattern)
- `agent/_lock.py` — verified verbatim (FileLock semantics + stale-PID handover)
- `agent/io.py` — verified verbatim (`write_json_atomic` alternative + `_replace_with_retry` Defender retry)
- `agent/tools.py` — verified `cmd_topics_*` + `cmds["topics"]` dispatch + nested subparser pattern (lines 1587-1751, 2017-2057, 2074-2118)
- `tests/test_k5_emitters.py` — verified shipped 17 K5 tests (4 new from Phase 10) — D-10.1 mirrors verbatim
- `tests/test_topics.py` — verified 24-test 5-class shape — Phase 11 mirror
- `output/_topics.md` — verified ground truth Approved Taxonomy 5/19 nodes (24 flat)
- `CLAUDE.md` lines 1740-1779 — verified `/summarize-video` Phase 7.5 / 8 boundaries (Q-B insertion point)
- `CLAUDE.md` line 1145 — verified `## v1.1 自适应教学文档增强` H2 mirror reference
- `output/BV132wizyEEB/summary.md` (replicate-guide) + `output/douyin_karpathy_llm_wiki/summary.md` (interview-distillation) + `output/douyin_claude_code_hooks/summary.md` (extension-applications) — verified chapter heading conventions vary across modes (Q-C / Pitfall 4)
- `output/BV132wizyEEB/meta.json` + `output/douyin_karpathy_llm_wiki/meta.json` — verified meta.json `title` + `duration` + `uploader` shape (KB-01 source for `title` and `duration_s` fields)
- `output/BV132wizyEEB/paragraphs.json` — verified `para_id` shape (`p0000` 5-char) + `start` float field (chapters[].start derivation source)
- `scripts/replay_v10_archives.py` lines 1-100 — verified D-29 replay script comparison scope (4 core files; sidecars NOT compared)
- `.planning/codebase/CONVENTIONS.md` — verified Python 3.13 + snake_case + dataclasses + atomic write idioms
- Bash `ls output/<slug>/` — verified 17 archives lack plan.md (Pitfall 2 / A4)
- Bash `Glob output/_glossary.md` — verified "No files found" (Pitfall 3 / A3)
- Bash `grep '^## '` on 3 sample summaries — verified chapter heading convention divergence across modes (Q-C / Pitfall 4)

### Secondary (MEDIUM confidence)

- None — Phase 11 is fully grounded in shipped local code + locked CONTEXT decisions. No external WebSearch needed.

### Tertiary (LOW confidence)

- None — no claims rest on training-data-only knowledge.

## Project Constraints (from CLAUDE.md)

> Extracted from `D:\gxy_code\videoSummary\CLAUDE.md`. Phase 11 plan MUST honor these.

- **¥0 hard constraint:** zero new paid APIs; no LLM API for keyword extraction (KB-03 reuses local `_glossary.md`); no third-party dep added.
- **K5 boundary (Claude-as-decider):** `agent/index.py` source must contain ZERO of the 5 D-29 core artifact literals (`summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json`). The literal `index.json` is the legitimate write target. Source-grep test enforces.
- **D-29 invariant:** never modify `summary.md` / `segs.json` / `paragraphs.json` / `meta.json` on any slug. Phase 11 close gate runs `scripts/replay_v10_archives.py` → 33/0/30 PASS.
- **Atomic write:** `tempfile.NamedTemporaryFile + os.fsync + os.replace` (mirror `agent/glossary.py:_atomic_write`).
- **FileLock serialization:** all writes to `output/.index.json` and `output/<slug>/index.json` go through `agent/_lock.FileLock` on `output/.index.lock`.
- **CLI conventions (per `.planning/codebase/CONVENTIONS.md`):** snake_case modules; `cmd_*` handler names; argparse subparser dispatched via dict; `print()` for user-facing JSON, `log` (lazy `%s` format) for module logging; `from __future__ import annotations` at top; double quotes; UTF-8 encoding explicit.
- **K3 backward-compat:** v1.0 archives without index.json are not broken — missing index.json is silent skip in Phase 12 backfill (handled at backfill time, not Phase 11).
- **Multi-terminal safety (Phase 6):** mirrors Phase 6 PARA-01 — `output/.index.lock` is the 4th cross-slug lock domain. Reads are lock-free. Writes serialize via FileLock with stale-PID handover.
- **Slug-prefix log lines (Phase 6 PARA-04):** `cmd_index_write` uses `_log(slug, "index_write", ...)`; `cmd_index_rebuild` does NOT prefix (cross-slug operation).
- **Windows zh-CN GBK code-page hazard:** `_validate_out_path` already exists in `agent/tools.py:88` for CJK rejection. Use `tests/_tmp_index/.gitkeep` ASCII-safe tmpdir root for `tests/test_index.py` (mirror Phase 10 D-19 lesson).

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — Phase 10 shipped 2 days ago; all imports verified by reading source; zero new dependencies.
- Architecture: HIGH — every pattern is a 1:1 mirror of shipped Phase 10 / v1.1 Phase 08 patterns; no novel structure.
- Pitfalls: HIGH — all 7 pitfalls grounded in verified file inspection (no plan.md in archives, no _glossary.md on branch, divergent chapter headings) or Phase 10 ship learning (K5 self-match deviation #2).
- Open Questions: MEDIUM-HIGH — A through G all have concrete recommendations; Q-A vacuously empty case is the only one not yet exercised in production (will be verified at Phase 11 unit test time).
- Validation Architecture: HIGH — test layout mirrors Phase 10 (224 tests, 2.37 s); replay gate already shipped.

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30-day stable horizon — Phase 10 contracts are stable; v1.2 milestone is in flight; Python stdlib + agent module shapes don't drift on this timescale)
