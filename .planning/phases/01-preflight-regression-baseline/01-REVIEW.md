---
phase: 01-preflight-regression-baseline
reviewed: 2026-04-30T00:00:00Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - .gitattributes
  - CLAUDE.md
  - agent/douyin_downloader.py
  - agent/io.py
  - agent/prepare.py
  - agent/tools.py
  - docs/schema-versions.md
  - src/download.py
  - src/pipeline.py
  - tests/regression/encoding-audit.md
  - tests/regression/regression-check.md
findings:
  critical: 0
  warning: 1
  info: 4
  total: 5
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-04-30
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 01 (Preflight & Regression Baseline) lands three deliverables: (a)
the byte-frozen `tests/regression/` baselines + `.gitattributes` opt-out,
(b) a new minimal stdlib-only `agent/io.py` plus 9 routing-site edits, and
(c) the `encoding-audit.md` evidence file plus a `CLAUDE.md` Windows
zh-CN section.

The plans have been faithfully executed:

- **agent/io.py (61 lines, stdlib-only)** is appropriately minimal and
  respects the "no class hierarchy / registry / dispatch table" pitfall
  from 01-RESEARCH. Dict vs list shape validation is present; `meta.json`
  honors `obj.get("schema_version", 1)`; list-shaped artifacts are
  intentionally treated as v1 by structural contract. SCHEMA_VERSION = 1
  constant is exported.
- **9/9 enumerated routing sites converted** — verified by grep. After
  the change, the only remaining `json.loads` call sites in `agent/`
  + `src/` are non-v1-artifact loads (`frame_store.py:88`,
  `src/pipeline.py:70/85`, `src/summarize.py:237/245/647`), which are
  out of scope per the 01-02 plan. The diff is purely mechanical
  replacement; no behavioral changes were introduced.
- **`.gitattributes`** correctly applies `-text` to `tests/regression/**`
  to preserve byte-for-byte CRLF + Windows `\\` separators. The path
  glob is correct.
- **All `read_text` / `write_text` calls in scope carry explicit
  `encoding="utf-8"`** — this matches the audit claim and the project
  CONVENTIONS rule. `agent/tools.py:59` `ensure_ascii=True` for
  terminal-print safety is preserved per CLAUDE.md guidance.
- **Docs (`docs/schema-versions.md`)** field-set tables for meta /
  segs / paragraphs match the live structures produced by `download()`
  (yt-dlp path) and `download_douyin()`. `aweme_id` / `source: "douyin"`
  are correctly flagged as 抖音-only.

The findings below are all minor — one Warning (line-number drift
between `encoding-audit.md` and the live source) and four Info items.
None block the phase.

## Warnings

### WR-01: encoding-audit.md cites stale line numbers in agent/douyin_downloader.py

**File:** `tests/regression/encoding-audit.md:33,41,48`
**Issue:** The audit table cites two specific lines in
`agent/douyin_downloader.py` that no longer match the current file
because Plan 01-02 inserted `from agent.io import load_meta` near the
top of that file, shifting subsequent line numbers down by 2.

Specifically:
- The audit says `agent/douyin_downloader.py:194:        with open(video_path, "wb") as f:` (lines 33 and 41) — actual location is **line 196**.
- The audit says `agent/douyin_downloader.py:60` for `_CONFIG.write_text(content, encoding="utf-8")` (line 48 audit-note) — actual location is **line 62**, and the variable name is `new_content`, not `content`.

This is a real defect in a freshly-minted Phase 1 deliverable whose
explicit value proposition ("read-only evidence", "anyone can re-run")
depends on the line numbers being correct. A future engineer running the
three documented grep commands will get matches at lines 196 / 62 / 74
/ 79 / 53, then look up `194`/`60` in the table and see drift.

**Fix:**
```diff
-agent/douyin_downloader.py:194:        with open(video_path, "wb") as f:
+agent/douyin_downloader.py:196:        with open(video_path, "wb") as f:

-| `agent/douyin_downloader.py:194` | `with open(video_path, "wb") as f:` — binary write (mp4) | OK — binary mode must NOT carry `encoding=`. |
+| `agent/douyin_downloader.py:196` | `with open(video_path, "wb") as f:` — binary write (mp4) | OK — binary mode must NOT carry `encoding=`. |

-> **Audit note (Pitfall 6):** Do NOT conflate "is this encoding correct?" with "should this code exist?" — `agent/douyin_downloader.py:60` `_CONFIG.write_text(content, encoding="utf-8")` is *encoding-correct* ...
+> **Audit note (Pitfall 6):** Do NOT conflate "is this encoding correct?" with "should this code exist?" — `agent/douyin_downloader.py:62` `_CONFIG.write_text(new_content, encoding="utf-8")` is *encoding-correct* ...
```

The simplest sustainable fix is to drop the line numbers from the audit
table entirely and let the live grep transcript carry that information
(since it is what re-runs reproduce anyway). If line numbers are kept,
add a note that they are accurate as of commit `<short-sha>` so future
drift has an obvious culprit.

## Info

### IN-01: Inner-element shape NOT validated in load_segs / load_paragraphs

**File:** `agent/io.py:39-61`
**Issue:** `load_segs` and `load_paragraphs` validate the top-level
container is a `list` but do not validate that elements are dicts with
the expected v1 fields. A malformed `segs.json` containing
`[1, 2, 3]` would pass `load_segs` and crash with an unhelpful
`AttributeError: 'int' object has no attribute 'get'` deep inside
`aggregate_paragraphs`.

**Recommendation: LEAVE AS-IS for v1.** Adding an `all(isinstance(x, dict) for x in obj)` check
costs 2 lines but pulls io.py one step closer to "schema enforcement",
which is exactly what 01-RESEARCH Pitfall 1 warns against. The current
v1 contract is "trust the producer" because every producer is in this
repo and every existing artifact under `output/<slug>/` already
conforms. If a future phase actually hits this surface (e.g., a user
hand-edits `segs.json`), revisit then; do not add the check
prophylactically. Filed as Info purely so future readers see the
trade-off was considered, not overlooked.

**No fix needed unless v2 introduces external producers.**

### IN-02: src/ now imports from agent/ — directional change

**File:** `src/download.py:11`, `src/pipeline.py:9`
**Issue:** Both `src/download.py` and `src/pipeline.py` now do
`from agent.io import ...`. Historically the project layered `agent/`
above `src/` (cf. `agent/prepare.py:54-55` doing
`from src.asr import ...`), so this introduces a `src → agent`
edge that creates a bidirectional dependency at the package level
(`agent/prepare.py → src/download.py → agent/io.py`).

Per `agent/io.py`'s docstring intent ("SINGLE landing point"), this is
deliberate — the loader has to live somewhere both layers can reach,
and `agent/io.py` has zero project imports of its own (only stdlib),
so there is no actual cycle in code-execution terms. But the directory
naming now slightly misleads: `agent/io.py` is conceptually a
foundational utility that both layers depend on, not an `agent`-layer
construct.

**Recommendation:** Document the directional inversion in a short
comment at the top of `agent/io.py` (e.g., "imported by both `agent/`
and `src/`; keep stdlib-only to avoid circular imports") or, if a
future phase touches the layering, consider relocating to a
`shared/io.py` or `src/io.py` package. Not a defect today; flagging so
the next person to add an import knows the rule.

### IN-03: frame_store.json load is NOT routed through agent/io.py

**File:** `agent/frame_store.py:88`
**Issue:** `frame_store.py:88` reads `frame_store.json` via
`json.loads(self.store_path.read_text(encoding="utf-8"))` — the same
v1-anti-pattern that 01-02 set out to centralize. Because
`frame_store.json` is not on the regression-baseline freeze list (only
meta / segs / paragraphs are), it falls outside the 9 enumerated
routing sites and was correctly not in scope for this phase.

**Recommendation: LEAVE AS-IS for now.** The 01-02 plan's enumeration
is intentional and matches the v1 baseline contract. But future readers
may scan io.py, see "single landing point", and wonder why
frame_store.py is exempt. A one-line `docs/schema-versions.md` note
clarifying that frame_store is a separate (richer) artifact not
governed by io.py would help. The same applies to `frames.json` /
`frame_descs.json` loaded in `src/pipeline.py:70/85` — these load
dataclass-shaped lists that are pipeline-internal, not v1 artifacts.

**Optional doc clarification:**
```diff
 ## Loader Behavior (locked by Phase 1)
+
+`agent/io.py` covers the three v1-frozen artifacts only
+(`meta.json`, `segs.json`, `paragraphs.json`). Pipeline-internal
+caches (`frame_store.json`, `frames.json`, `frame_descs.json`)
+intentionally remain on direct `json.loads` because their schemas are
+governed by their consuming dataclass — not by the v1 baseline
+contract — and Phase 1 freezes only the latter.
```

### IN-04: Unused imports in agent/douyin_downloader.py

**File:** `agent/douyin_downloader.py:19`
**Issue:** `from urllib.parse import urlparse, parse_qs` — neither
`urlparse` nor `parse_qs` is used in the file. This is pre-existing
(not introduced by Phase 1), but the file is in review scope.

**Fix:**
```diff
-from urllib.parse import urlparse, parse_qs
```

Standalone, low-risk one-line cleanup. Fine to defer to a later
janitor pass — flagging only because every Phase 1 reader will load
this file fresh and may notice.

---

## Notes (not findings)

The following are intentional design decisions verified during review
and called out so they are not re-litigated by future readers:

- **`agent/io.py:24` `SCHEMA_VERSION = 1` is a constant for *new*
  writers, not a write-time enforcement.** The docstring is explicit
  ("current version for new artifacts; bump in v2 phase"). Phase 1 does
  not write `schema_version` into any artifact; that decision is
  deferred to Phase 2 (RES-08). `docs/schema-versions.md:23-27`
  documents this boundary correctly.

- **`docs/schema-versions.md` Pitfall 5 about path-separator variance
  (`\\` vs `/` in `video_path`)** is correctly captured. `load_meta`
  treats the field as opaque — it does not normalize separators, which
  is what preserves byte-fidelity for `BV132wizyEEB` (CRLF + `\\`)
  versus `BV1C9QCBdE1U` (LF + `/`).

- **`tests/regression/regression-check.md` correctly mandates `--force`
  for `transcribe`** to bypass the `agent/tools.py:75-81` cache check,
  and explicitly documents that `aggregate` has no `--force` flag
  (so the runbook says `rm output/<slug>/paragraphs.json` first). Both
  match the actual code.

- **`agent/tools.py:59` `ensure_ascii=True`** is preserved as the
  zh-CN-cmd fallback. CLAUDE.md `## Windows zh-CN 终端设置（推荐）`
  documents the recommended-but-optional `chcp 65001` + `PYTHONUTF8=1`
  upgrade path. Both files cross-reference each other correctly.

- **`.gitattributes` glob `tests/regression/** -text`** is the right
  scope. It does not affect any other path. Verified by inspection.

---

_Reviewed: 2026-04-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
