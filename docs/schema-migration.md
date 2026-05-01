# Schema Migration Runbook

**Status:** Reference. Phase 2 RES-08 (locked 2026-05-01).
**Companion:** [`docs/schema-versions.md`](./schema-versions.md) — current v1 field set per artifact.
**Owner:** Whichever future phase first needs to bump `schema_version` 1 → 2 (Phase 1 K-Decision: real migration cost is owned by the bumping phase).

This document is the lookup the next schema-changing phase will copy from. It does **not** describe an active migration — there is no v2 yet.

## When to bump

A bump (1 → 2) is **required** when any of:

- A required field is removed or renamed (`title` → `headline`)
- A required field's type changes (`duration: int` → `duration: float`)
- The semantic meaning of an existing field changes (e.g. `start: float` switches from "seconds since first segment" to "seconds since file start" — same shape, new contract)
- A field's allowed value range tightens (e.g. `whisper_model` was free-form, becomes enum)

A bump means the loader (`agent/io.py:load_meta` / `load_segs` / `load_paragraphs`) inserts a migration call so old artifacts continue to load without modification on disk.

## When NOT to bump

Bumps are expensive (they require running the full eyeball-diff regression below). Avoid bumping for:

- **Adding an optional field** with sensible default for missing values (precedent: SRC-04 in Phase 3 will add `meta.json["source"]: "bilibili"|"douyin"|...` defaulting to `null` for archives — no bump)
- **Adding a new artifact type** (e.g. Phase 4's `schedule.json` — entirely new file, no impact on existing loaders)
- Adding sidecar fields (e.g. extending `func` segment of `<artifact>.params.json` — sidecars themselves carry `schema_version: 1` but are diagnostic, not consumed by the pipeline today)
- Reordering fields within a dict (Python preserves dict-insertion order but JSON-readers don't depend on it)

The Phase 1 K-Decision (D-04) is precedent: `segs.json` and `paragraphs.json` are top-level lists, which cannot carry a `schema_version` field. They will only ever be migrated by introducing a NEW top-level shape (i.e. a new artifact name), not by mutating the list.

## Minimal example: meta.json v1 → v2 round-trip

When the day comes that `meta.json` needs a v2, the change set is:

1. Bump `SCHEMA_VERSION = 2` in `agent/io.py`.
2. Add a `_migrate_meta_v1_v2(obj)` function in `agent/io.py`.
3. Insert a migration dispatch into `load_meta`. Existing call sites in `agent/tools.py` and elsewhere remain unchanged.

Pseudocode (for illustration; do NOT add to the codebase today — only add when the real bump phase lands):

```python
# agent/io.py — illustrative, NOT to be added in Phase 2
SCHEMA_VERSION = 2  # bumped from 1

def _migrate_meta_v1_v2(obj: dict) -> dict:
    """Migrate meta.json v1 → v2.
    Real example: imagine v2 splits `title` into `title_zh` + `title_original`.
    """
    if "title" in obj and "title_zh" not in obj:
        obj["title_zh"] = obj.pop("title")
        obj["title_original"] = None  # unknown for archives
    obj["schema_version"] = 2
    return obj

def load_meta(path):
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"meta.json must be dict; got {type(obj).__name__}")
    v = obj.get("schema_version", 1)
    if v == 1:
        obj = _migrate_meta_v1_v2(obj)
    elif v != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version {v} in {path}")
    return obj
```

**Notes:**
- The migration is read-only on disk: `load_meta` returns the migrated dict in memory, but does NOT write it back to disk. The 17 archive `meta.json` files stay byte-identical until the user actively reruns `cmd_download` (or whichever stage produces the artifact). This preserves the Phase 1 D-03 backward-compat contract.
- Migrations are pure functions of the input dict. Test them with `unittest` (stdlib) over a captured archive `meta.json`.
- Do not chain migrations (`v1 → v2 → v3` should be `_migrate_meta_v1_v3`, not `v1 → v2` then `v2 → v3` lazily). Each bump owns its own migration.

## Test checklist

A bump phase MUST verify all of the following before merging:

- [ ] `tests/regression/<slug>/meta.json` for all 3 baselines (`BV132wizyEEB`, `BV1C9QCBdE1U`, `douyin_trae_ai`) loads cleanly via the new `load_meta` and produces a dict with `schema_version` equal to the new version. The DISK content remains byte-identical.
- [ ] Run the full Phase 1 eyeball-diff regression (per [`tests/regression/regression-check.md`](../tests/regression/regression-check.md)): re-run the affected stages on each of the 3 baselines, manually compare new `summary.md` against `tests/regression/<slug>/summary.md` for "no surprise drift" (Phase 1 D-09 contract).
- [ ] `python -m agent.tools doctor output/<slug>` shows `params_hash_match: —` for archives without sidecars (D-01 contract preserved — bump did not silently regenerate archive sidecars).
- [ ] `docs/schema-versions.md` is updated with the new field set under a `## Schema v2` section (the v1 section is preserved; do not delete history).
- [ ] The migration function has a stdlib `unittest` test asserting v1 → vN round-trip on a captured archive dict (no I/O; pure function test).

## References

- [`docs/schema-versions.md`](./schema-versions.md) — current v1 field reference per artifact
- [`tests/regression/regression-check.md`](../tests/regression/regression-check.md) — Phase 1 eyeball-diff runbook
- `.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md` D-03..D-06 — backward-compat contract
- `.planning/phases/02-resume-infrastructure-cache-correctness/02-CONTEXT.md` D-18..D-20 — this runbook's design
- [JSON Schema Evolution best practices](https://docs.confluent.io/platform/current/schema-registry/fundamentals/schema-evolution.html) — additive-only, forward-compat principles (informational)
