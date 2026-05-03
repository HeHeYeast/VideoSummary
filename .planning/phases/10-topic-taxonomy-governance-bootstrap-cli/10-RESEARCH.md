# Phase 10: Topic taxonomy governance + bootstrap CLI - Research

**Researched:** 2026-05-04
**Domain:** Governance file authoring (markdown) + atomic multi-file CLI write + K5 source-grep boundary preservation
**Confidence:** HIGH (95%+ patterns are direct mirrors of v1.0/v1.1 ship code; verified by reading `agent/glossary.py`, `agent/_lock.py`, `agent/io.py`, `tests/test_k5_emitters.py`, `agent/tools.py`)

## Summary

Phase 10 ships a 4-public-function module (`agent/topics.py`) + 3 nested CLI subcommands (`topics bootstrap` / `topics audit` / `topics resolve`) + 4 new K5 boundary tests, mirroring patterns established by v1.1 Phase 08 (`agent/glossary.py`) and v1.1 Phase 07 (`queue` nested subparser, `tests/test_k5_emitters.py` write-pattern regex). Every research question A-F resolves to "extend or copy a documented v1.1 ship pattern" except for two genuine novelties:

1. **`topics resolve` atomic cross-file write** — extends v1.1's single-file atomic write (tempfile + os.replace) to N+1 files (1 `_topics.md` + N `index.json`s). Failure-mode contract is "snapshot in memory before any write, then write all-or-restore-from-snapshot". Critically, **N=0 is the expected case at Phase 10 ship time** (no `index.json` files exist until Phase 11).

2. **`output/_topics.md` schema is read-modify-write, not append-only** — `_glossary.md` is append-only H2 anchors; `_topics.md` has Approved + Pending two segments and `resolve` MOVES entries between them. The first-seen-wins / idempotent-append idioms from `agent/glossary.py` do not apply.

**Primary recommendation:** Plan as **2 plans, mirror Phase 08 cadence**:
- **Plan 10-01:** `agent/topics.py` (4 public functions: `read_topics` / `write_approved_taxonomy` / `append_pending` / `resolve_pending`) + nested CLI subparser + 4 K5 boundary tests + behavior tests (mirror Phase 08 `tests/test_glossary.py` 6-test pattern). All under one commit per task convention.
- **Plan 10-02:** End-to-end smoke test on a synthetic 3-archive corpus + first real bootstrap invocation (Claude reads 33 `output/*/summary.md` titles, proposes initial taxonomy, pipes `--from-stdin` to write `output/_topics.md`). Defers actual bootstrap content authoring to user-confirmable plan execution. CLAUDE.md NOT modified (per CONTEXT line 174 — Phase 11 owns `/summarize-video` Phase 7.6 hook; Phase 10 is pure infrastructure).

## Project Constraints (from CLAUDE.md)

These directives from `D:/gxy_code/videoSummary/CLAUDE.md` constrain all Phase 10 plans:

- **¥0 hard constraint** — no new paid APIs. Phase 10 is stdlib-only (no new packages); D-08 FileLock reuse + D-07 atomic write reuse cover the entire surface.
- **K5 (Claude is decider)** — `topics bootstrap` cannot algorithmically derive taxonomy; Claude reads archives + proposes via `--from-stdin` JSON. CLI is a mechanical writer, not a classifier. `topics audit` is read-only. `topics resolve` only acts on a pending-name explicitly named by user/Claude on the command line.
- **D-29 byte-equal preserved** — `_topics.md` is a NEW top-level governance file (not in any v1.0 archive's per-slug directory). Phase 10 does not touch any per-slug `summary.md` / `segs.json` / `paragraphs.json` / `meta.json`. The replay test (`scripts/replay_v10_archives.py`) compares only those 4 core files; `_topics.md` falls outside its scope. Phase 10 verification SHOULD include a confirmation `replay_v10_archives` reports 33/0/30 PASS post-Phase-10.
- **Single-user, multi-terminal-aware** — `output/.topics.lock` is the new lock domain (mirror `output/.glossary.lock`). FileLock with stale-PID takeover handles Claude Code crash mid-resolve.
- **Python conventions** (from `.planning/codebase/CONVENTIONS.md`):
  - `from __future__ import annotations` mandatory at top of `agent/topics.py`
  - PEP-604 unions (`str | None`, never `Optional[str]`)
  - Built-in generics (`list[dict]`, never `typing.List`)
  - `cmd_*` prefix for CLI handlers
  - `log = logging.getLogger(__name__)` named `log` (not `logger`)
  - `pathlib.Path` everywhere; `encoding="utf-8"` explicit on all text I/O
  - `json.dumps(obj, ensure_ascii=False, indent=2)` for JSON output (CJK-readable)
  - Chinese docstrings + Chinese inline comments (English only inside identifiers / code literals)

## User Constraints (from CONTEXT.md)

### Locked Decisions

#### `output/_topics.md` File Structure (D-01)

- **D-01.1:** 文件路径 `output/_topics.md`（顶层 governance file，与 v1.1 Phase 08 ship 的 `output/_glossary.md` 同级，命名一致）
- **D-01.2:** 文件 schema = 2 段：顶部 `## Approved Taxonomy` + 底部 `## Pending`
- **D-01.3:** Approved Taxonomy 段用 markdown 嵌套 list 表达 category 树状（`- LLM` → `  - LoRA` → `  - RAG`），最多 3 层（`category > subcategory > topic`），避免过深
- **D-01.4:** Pending 段每条 = `### <pending-name>` H3 + 子 list 必填 3 字段：`- 申请来源 slug: <slug>` / `- chapter title: <title>` / `- 提议理由: <reason>`
- **D-01.5:** 文件首次创建由 `topics bootstrap` 触发；Phase 11 的 generator 在 _topics.md 不存在时 fail-fast（提示用户 `python -m agent.tools topics bootstrap` 先跑）
- **D-01.6:** 文件以 `# Topics Taxonomy\n\n> v1.2 knowledge-base governance — ...\n` header 开头（mirror `_glossary.md` 顶部说明段）

#### `topics bootstrap` CLI (D-02)

- **D-02.1:** 命令 = `python -m agent.tools topics bootstrap` (no args, no flags first version)
- **D-02.2:** 行为 = 扫 17 v1.0/v1.1 archives 的 `output/<slug>/summary.md` + `output/_glossary.md` 已有 H2 anchors，由 Claude 多模态归纳出初始 taxonomy（**Claude is decider** — bootstrap 是 Claude 写入 _topics.md 的工具，不是脚本算法）
- **D-02.3:** Idempotent — 已存在 _topics.md（顶部 Approved Taxonomy 段非空）→ no-op + stderr 提示
- **D-02.4:** 首次 bootstrap 默认批（ground truth from 17 archives — 不进 Pending 段，直接写 Approved Taxonomy）
- **D-02.5:** stdout = JSON `{"action": "created" | "skipped", "approved_count": N, "_topics_path": "output/_topics.md"}`
- **D-02.6:** Implementation: bootstrap 读 stdin JSON `{"taxonomy": [...]}` 写入 _topics.md（mirror `glossary append` 的结构）。不读 stdin 时 fail-fast 报错（避免脚本臆造 taxonomy）

#### `topics audit` CLI (D-03)

- **D-03.1:** 命令 = `python -m agent.tools topics audit [--json]` (no args; `--json` flag for Claude consumption)
- **D-03.2:** 行为 = 读 `output/_topics.md` + 扫所有 `output/<slug>/index.json`（如有），输出 3-段报告
- **D-03.6:** `--json` 输出 schema = `{"pending": [{"name": ..., "from_slug": ..., "reason": ...}], "approved_with_counts": {"<topic>": N}, "orphans": ["<topic>", ...]}`
- **D-03.7:** Read-only — 永不写 _topics.md / index.json（K5 边界）

#### `topics resolve` CLI (D-04)

- **D-04.1:** 命令 = `python -m agent.tools topics resolve <pending-name> [--rename <new-name>] [--remove]`
- **D-04.2:** atomic 跨多文件改写：(a) 在 _topics.md Approved Taxonomy 段插入 entry（按字母序在合适位置插入）；(b) 删除 _topics.md Pending 段中的 entry；(c) 扫所有 `output/<slug>/index.json` 中 `topics: [..., "pending: <name>"]` → 改为 `"<final-name>"`
- **D-04.3:** Atomic 实现 = (a) 持有 `output/.topics.lock` FileLock；(b) 读所有 will-modify 文件构建 in-memory diff；(c) atomic write 模式（tempfile + os.replace）依次写每个文件；(d) 任一步失败 → restore from snapshot
- **D-04.4:** `--remove` 模式 atomic 删除 Pending entry + 引用改 `topics: []` + stderr 警告
- **D-04.5:** stdout = JSON `{"action": "promoted" | "renamed" | "removed", "pending_name": "...", "final_name": "..." | null, "index_json_updated": [<slug>, ...], "_topics_path": "output/_topics.md"}`
- **D-04.6:** Pending entry 不存在 → fail-fast

#### Claude Governance Workflow (D-05 — Phase 11 contract)

- **D-05.3:** Phase 10 暴露 `agent.topics.append_pending(name, from_slug, chapter_title, reason)` Python API（Phase 11 generator import）

#### K5 Boundary Static Assertion (D-06)

- 4 new tests extending `tests/test_k5_emitters.py`:
  - `test_topics_bootstrap_no_index_json_writes` — `cmd_topics_bootstrap` source 不含 `index.json` / `summary.md` / `plan.md` 字面
  - `test_topics_audit_no_writes` — `cmd_topics_audit` 不含任何 file write 模式
  - `test_topics_resolve_only_writes_topics_md_and_index_json` — `cmd_topics_resolve` 允许写 `_topics.md` 和 `index.json`，禁止写 `summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json`
  - `test_topics_module_no_summary_writes` — `agent/topics.py` 模块整体源码不含 `summary.md` literal

#### `agent/topics.py` Module Layout (D-07)

- 4 public functions: `read_topics` / `write_approved_taxonomy` / `append_pending` / `resolve_pending`
- 3 CLI handlers in `agent/tools.py`: `cmd_topics_bootstrap` / `cmd_topics_audit` / `cmd_topics_resolve`
- Subcommand routing mirrors v1.1 Phase 07 `queue` nested subparser pattern

#### FileLock Serialization (D-08)

- 锁文件 `output/.topics.lock`
- 复用 `agent/_lock.py:FileLock` (stale-PID takeover)
- 锁住所有写操作；不锁 read-only audit

### Claude's Discretion

- Bootstrap 出来的初始 taxonomy 具体 category 划分 — Claude 在 Phase 10 execute 时 read 17 archives 后决定具体形态，CONTEXT.md 不预设
- `topics audit` 的 stdout markdown 排版细节（emoji / 表格 / bullet list）
- `topics resolve --remove` 警告文案具体措辞
- `bootstrap --from-stdin` 的 stdin JSON schema 详细字段（minimal viable）

### Deferred Ideas (OUT OF SCOPE)

- Topic 树排序 / 重命名 CLI（`topics rename` / `topics reorder`）— v1.3+
- Topic alias / synonyms — v1.3+
- Topic 引用 health check 自动修复 — Phase 10 audit 报告但不修
- Topic 树 GUI / Web Viewer — OOS（single-user）
- Auto-promote pending → approved — OOS per D-04 K5 governance
- Auto-cleanup orphan topics — KB-09 audit 报告，不删

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| KB-07 | `output/_topics.md` 文件结构 — 顶部已批准 taxonomy（按 category 树状）+ 底部 `## Pending` 段 | D-01 6 sub-decisions all locked. File-shape mirror `output/_glossary.md`; `agent/glossary.py:_FILE_HEADER` provides exact template. Schema validation via `read_topics()` parser; markdown nested-list parsing solvable with stdlib `re` (no `markdown-it-py` dep needed). |
| KB-08 | `topics bootstrap` CLI — 一次性扫 17 archives, Claude 归纳出初始 taxonomy 写到顶部已批准段 | D-02 locked: `--from-stdin` JSON shape (`{"taxonomy": [{"name": "X", "subtopics": [...]}, ...]}`). CLI is mechanical writer; Claude is decider for content. Idempotent via "skip if Approved Taxonomy non-empty". stdin JSON parsing edge cases addressed in Question A below. |
| KB-09 | `topics audit [--json]` CLI — 列 pending + 引用计数 + 孤儿检测 | D-03 locked: read-only across `_topics.md` + glob `output/*/index.json`. Glob returns empty list at Phase 10 ship time (Phase 11 not yet shipped) — audit must handle 0-index.json case gracefully (`approved_with_counts: {topic: 0}`, `orphans: [all approved topics]`). |
| KB-10 | `topics resolve <pending-name>` CLI — atomic 跨多文件改写 | D-04 locked: snapshot-then-atomic-write. Failure modes addressed in Question B below. |
| KB-11 | Claude 申请新 topic 走 governance 闭环 + K5 边界 statically asserted | D-05.3 + D-06 locked. `agent.topics.append_pending` Python API (Phase 11 import). 4 K5 tests asserted in `tests/test_k5_emitters.py`. |

## Standard Stack

### Core (all stdlib — zero new deps)

| Module | Source | Purpose | Why Standard |
|--------|--------|---------|--------------|
| `pathlib.Path` | stdlib | All file paths | [VERIFIED: codebase grep] universal in `agent/` modules; CONVENTIONS.md "no `os.path` in app code" |
| `re` | stdlib | Markdown H2/H3/list parsing | [VERIFIED: agent/glossary.py:56 + agent/glossary_audit.py:22] `_H2_RE = re.compile(r"^##\\s+(.+)$", re.MULTILINE)` — exact pattern to mirror; extend with `_H3_RE = re.compile(r"^###\\s+(.+)$", re.MULTILINE)` for Pending entries |
| `tempfile.NamedTemporaryFile` + `os.replace` | stdlib | Atomic write | [VERIFIED: agent/glossary.py:59-82 `_atomic_write`] verbatim copy template |
| `json` | stdlib | `--from-stdin` parsing + JSON CLI output | [VERIFIED: agent/tools.py uses `json.dumps(..., ensure_ascii=False, indent=2)` per CONVENTIONS.md] |
| `argparse` | stdlib | CLI subparser routing | [VERIFIED: agent/tools.py:1734 nested subparser pattern for `queue`] |
| `agent._lock.FileLock` | v1.0 Phase 06 ship | Cross-platform file lock | [VERIFIED: agent/_lock.py + tests/test_lock.py] stale-PID takeover, msvcrt+fcntl, timeout=0 fail-fast |
| `agent.io.write_json_atomic` | v1.0 Phase 02 ship | Atomic JSON write (for index.json updates) | [VERIFIED: agent/io.py:106 `write_json_atomic(path, obj, *, sidecar_params=None)`] reuse for resolve's per-slug index.json updates |

### Supporting

| Module | Source | Purpose | When to Use |
|--------|--------|---------|-------------|
| `logging` | stdlib | `log = logging.getLogger(__name__)` | At module top, not inside functions |
| `dataclasses` | stdlib | If `read_topics` returns structured taxonomy | OPTIONAL — Phase 10 can return plain dict (`{"approved": [...], "pending": [...]}`) per D-07.2 signature |

### Alternatives Considered (and rejected)

| Instead of | Could Use | Tradeoff | Why Rejected |
|------------|-----------|----------|--------------|
| stdlib `re` for markdown parsing | `markdown-it-py` / `mistune` | Robust AST | New dep violates ¥0 + no ship precedent; v1.1 Phase 08 `agent/glossary.py` proved stdlib `re` is sufficient for the constrained `_glossary.md` schema. `_topics.md` schema is similarly constrained (Approved = nested bullet list ≤ 3 levels; Pending = H3 + 3 fixed sub-fields). |
| `filelock` PyPI package | `agent/_lock.py:FileLock` | Already shipped + stdlib-only | [CITED: agent/_lock.py:1-21 docstring "NO new dependency"] — supersedes earlier REQUIREMENTS.md PARA-01 mention of `filelock>=3.16` |
| Per-CLI separate JSON file (e.g., `_topics.json` + `_topics.md`) | Single `_topics.md` markdown only | User review-friendly | CONTEXT D-01.2 locked single-file 2-section markdown |
| Multiple lock files (`output/.topics-write.lock` + `output/.topics-resolve.lock`) | Single `output/.topics.lock` | Mirror `output/.glossary.lock` simplicity | CONTEXT D-08.1 locked single lock; cross-CLI serialization is desirable |

**Installation:** None — stdlib + already-shipped modules only.

**Version verification:** N/A — no new packages. Python version matches existing codebase: `>=3.11` tolerant, `3.13` primary [VERIFIED: .planning/codebase/STACK.md:7-12].

## Architecture Patterns

### Recommended Module Structure

```
agent/
├── topics.py            # NEW — 4 public functions; mirror agent/glossary.py shape (~210 LOC est)
├── _lock.py             # REUSE — FileLock + stale-PID takeover
├── _glossary.py         # (does not exist — module is named glossary.py)
├── glossary.py          # PATTERN REFERENCE — read_glossary / glossary_append idioms
├── glossary_audit.py    # PATTERN REFERENCE — read-only audit shape
├── tools.py             # EXTEND — add cmd_topics_* + nested subparser + topics_cmds dict
├── io.py                # REUSE — write_json_atomic for index.json updates
└── _v11.py              # NOT EXTENDED — Phase 10 is unconditional, no marker gating

tests/
├── test_topics.py           # NEW — 6+ behavior tests (mirror tests/test_glossary.py)
├── test_k5_emitters.py      # EXTEND — 4 new K5 boundary tests
└── _tmp_topics/             # NEW — ASCII-safe per-test tmpdir (mirror _tmp_glossary/)
```

### Pattern 1: Mirror `agent/glossary.py` Shape

**What:** `agent/topics.py` follows the same 6-section layout as `agent/glossary.py`:

```python
"""Topic taxonomy governance file accumulator (Phase 10 D-01..D-08).

Read-modify-write writer for `output/_topics.md`. Serialized via
`output/.topics.lock` (reuses agent/_lock.FileLock — third cross-slug lock
domain after Phase 07 ~/.videoSummary/.queue.lock and Phase 08
output/.glossary.lock).

K5 boundary:
  - This module WRITES to output/_topics.md ONLY (the governance file).
  - resolve_pending() ALSO writes to per-slug output/<slug>/index.json files
    when promoting a pending name (sole exception in this module).
  - It NEVER writes to per-slug summary / plan / schedule / paragraphs / segs /
    meta decision artifacts.
  - Source-grep tests (tests/test_k5_emitters.py) verify no write calls
    target those filenames.

Schema (locked in 10-CONTEXT.md D-01):
  - File header: `# Topics Taxonomy` + 1-line preamble (written once on bootstrap)
  - `## Approved Taxonomy` segment: nested markdown list, max 3 levels
  - `## Pending` segment: H3 entries with 3 required sub-fields each

Idempotency rules:
  - bootstrap: skip-if-non-empty Approved Taxonomy segment exists
  - append_pending: same (name, from_slug) — re-applies same content (overwrite ok)
  - resolve_pending: pending-name not found → fail-fast (caller bug, not idempotent no-op)
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

TOPICS_FILENAME = "_topics.md"
LOCK_FILENAME = ".topics.lock"
DEFAULT_OUTPUT_DIR = "output"

_FILE_HEADER = """\
# Topics Taxonomy

> v1.2 knowledge-base governance — `## Approved Taxonomy` 段是 Claude 写 index.json
> 时的 topic 白名单；`## Pending` 段是 Claude 申请的新 topic 待用户 review。
> 此文件由 `python -m agent.tools topics {bootstrap,audit,resolve}` CLI + Phase 11
> generator (`agent.topics.append_pending`) 共同维护。

## Approved Taxonomy

<!-- (initially empty until bootstrap runs) -->

## Pending

<!-- (Claude 申请新 topic 时由 Phase 11 generator 在此 append H3 entry) -->

"""

# (regex constants + 4 public functions follow)
```

**When to use:** ALL of `agent/topics.py`. This is not a "consider"; it is the locked pattern (CONTEXT D-07.1 + Discussion Log "mirror v1.1 ship 的 `agent/_glossary.py` 单模块形态").

### Pattern 2: K5 Source-Grep with `_WRITE_PATTERNS_FORBIDDEN` Regex

**What:** `tests/test_k5_emitters.py` has 13 tests using BOTH literal-substring (`FORBIDDEN_LITERALS`) AND write-pattern regex (`_WRITE_PATTERNS_FORBIDDEN`) approaches. The choice depends on whether the forbidden literal LEGITIMATELY appears in the source (e.g., as argparse help text, input arg path receiver, or output template).

**Decision matrix for Phase 10:**

| File / cmd | Has legitimate `index.json` substring? | Test approach |
|------------|---------------------------------------|---------------|
| `cmd_topics_bootstrap` | NO (writes only `_topics.md`) | Literal-substring: forbid `index.json` + `summary.md` + `plan.md` |
| `cmd_topics_audit` | YES (reads `index.json` files via glob) | Write-pattern regex: forbid `write_text` / `os.replace` / `_atomic_write` / `open(...,'w')` targeting `index.json` etc. |
| `cmd_topics_resolve` | YES (writes both `_topics.md` AND `index.json` files) | Write-pattern regex: forbid write patterns targeting `summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json`. ALLOW `index.json` writes. |
| `agent/topics.py` module | depends on what `read_topics` does — must read `output/<slug>/index.json` to detect orphans? Per CONTEXT D-03.2 yes (`audit` reads them). And `resolve_pending` writes them. | Write-pattern regex (mirror `agent/glossary.py` decision) — forbid writes to summary/plan/etc., allow `index.json` writes |

**Example:**

```python
# tests/test_k5_emitters.py addition
from agent.tools import (
    cmd_topics_bootstrap,
    cmd_topics_audit,
    cmd_topics_resolve,
)

# Phase 10 D-06: forbidden write targets EXCLUDING index.json (legitimate write target for cmd_topics_resolve)
_TOPICS_RESOLVE_WRITE_FORBIDDEN = (
    r"write_text\([^)]*summary\.md",
    r"write_text\([^)]*plan\.md",
    r"write_text\([^)]*paragraphs\.json",
    r"write_text\([^)]*segs\.json",
    r"write_text\([^)]*meta\.json",
    r"open\([^)]*summary\.md[^)]*['\"]w",
    r"open\([^)]*plan\.md[^)]*['\"]w",
    r"open\([^)]*paragraphs\.json[^)]*['\"]w",
    r"open\([^)]*segs\.json[^)]*['\"]w",
    r"open\([^)]*meta\.json[^)]*['\"]w",
    r"os\.replace\([^)]*summary\.md",
    r"os\.replace\([^)]*plan\.md",
    r"os\.replace\([^)]*paragraphs\.json",
    r"os\.replace\([^)]*segs\.json",
    r"os\.replace\([^)]*meta\.json",
    r"_atomic_write\([^)]*summary\.md",
    r"_atomic_write\([^)]*plan\.md",
    r"_atomic_write\([^)]*paragraphs\.json",
    r"_atomic_write\([^)]*segs\.json",
    r"_atomic_write\([^)]*meta\.json",
    r"write_json_atomic\([^)]*summary\.md",  # NEW pattern - write_json_atomic also writes
    r"write_json_atomic\([^)]*plan\.md",
    r"write_json_atomic\([^)]*paragraphs\.json",
    r"write_json_atomic\([^)]*segs\.json",
    r"write_json_atomic\([^)]*meta\.json",
)
```

**When to use:** All 4 new K5 tests. Without write-pattern regex, the comment at `agent/glossary.py:42-46` warns of self-matching false-positives (Phase 08 deviation #2 already fixed this for glossary).

### Pattern 3: Snapshot-Then-Atomic-Write for Multi-File Resolve

**What:** Atomic multi-file edits where any single failure must restore all files. `agent/topics.py:resolve_pending` reads ALL files into memory first, computes new contents, then writes via tempfile+os.replace serially.

**When to use:** `resolve_pending()` ONLY. Other functions touch single files.

**Example:**

```python
def resolve_pending(
    topics_path: Path,
    pending_name: str,
    *,
    rename: str | None = None,
    remove: bool = False,
    output_dir: Path | None = None,  # default: topics_path.parent
    timeout: float = 10.0,
) -> dict:
    """Promote / rename / remove a pending entry, atomically updating
    _topics.md AND any per-slug index.json files that reference it.

    Failure mode: any file write that fails causes ALL files to be restored
    from the in-memory snapshot taken before the first write. The snapshot is
    bytes-exact (no schema parsing), so restore is byte-equal even if the
    file was previously corrupted.
    """
    if rename and remove:
        raise ValueError("--rename and --remove are mutually exclusive")
    output_dir = output_dir or topics_path.parent
    lock_path = topics_path.parent / LOCK_FILENAME

    with FileLock(lock_path, timeout=timeout):
        # Step 1: Read _topics.md, parse Pending segment, find <pending-name>
        topics_md_orig = topics_path.read_text(encoding="utf-8")
        snapshot = {topics_path: topics_md_orig}

        # Step 2: Glob all output/<slug>/index.json (may be 0 at Phase 10 ship)
        index_paths = sorted(output_dir.glob("*/index.json"))
        for ip in index_paths:
            snapshot[ip] = ip.read_text(encoding="utf-8")

        # Step 3: Compute new contents in memory
        new_topics_md = _compute_resolved_topics_md(topics_md_orig, pending_name, rename, remove)
        new_index_jsons = {}  # path -> new JSON dict (or None to skip)
        affected_index_json = []
        final_name = (rename if rename else pending_name) if not remove else None
        old_marker = f"pending: {pending_name}"
        new_marker = final_name  # may be None for --remove
        for ip in index_paths:
            obj = json.loads(snapshot[ip])
            mutated = _replace_pending_in_index(obj, old_marker, new_marker)
            if mutated:
                new_index_jsons[ip] = obj
                affected_index_json.append(ip.parent.name)  # slug

        # Step 4: Write all files (atomic per-file). On any failure, restore from snapshot.
        written = []
        try:
            _atomic_write(topics_path, new_topics_md)
            written.append(topics_path)
            for ip, obj in new_index_jsons.items():
                payload = json.dumps(obj, ensure_ascii=False, indent=2)
                _atomic_write(ip, payload)
                written.append(ip)
        except Exception:
            # Restore from snapshot
            for p in written:
                try:
                    _atomic_write(p, snapshot[p])
                except Exception:
                    log.error("topics.resolve: restore failed for %s", p, exc_info=True)
            raise

        return {
            "action": "promoted" if not (rename or remove) else ("renamed" if rename else "removed"),
            "pending_name": pending_name,
            "final_name": final_name,
            "index_json_updated": affected_index_json,
            "_topics_path": str(topics_path),
        }
```

**Race-loss window:** Between `_atomic_write(topics_path, ...)` succeeding and the first index.json `_atomic_write` failing, _topics.md is briefly in the new state but index.json is in the old state. The `except` block then restores _topics.md to the old state. This race window is microseconds in the happy path; the failure path may leave files in old state if RESTORE itself fails (then `log.error` is the loud signal). Single-user multi-terminal context (CLAUDE.md PARA section) makes this acceptable — Phase 10 OOS includes "true distributed transaction" per the deferred ideas.

### Pattern 4: Nested Subparser Routing in `agent/tools.py`

**What:** Phase 07 ship's `queue` subcommand established the pattern; Phase 08 ship's `glossary` subcommand reused it. Phase 10's `topics` follows verbatim.

**Example (extending agent/tools.py:1867-1906):**

```python
# In main(), after the glossary subparser block:
# ── Phase 10 D-07: nested `topics` subparser (bootstrap + audit + resolve) ──
p = sub.add_parser(
    "topics",
    help="Topic taxonomy governance: bootstrap (init from archives) / audit "
         "(read-only pending+orphan report) / resolve (promote/rename/remove pending)",
)
tsub = p.add_subparsers(dest="topics_cmd", required=True)

tboot = tsub.add_parser(
    "bootstrap",
    help="One-shot init from Claude-proposed taxonomy (read --from-stdin JSON)",
)
tboot.add_argument("--from-stdin", action="store_true",
                   help="REQUIRED: read taxonomy JSON from stdin "
                        "(prevents script-driven taxonomy generation; K5 boundary)")
tboot.add_argument("--output-dir", default="output",
                   help="parent dir for _topics.md (default: output)")
tboot.add_argument("--json", action="store_true", help="emit JSON action result")

taudit = tsub.add_parser(
    "audit",
    help="K5 read-only: list pending + reference counts + orphan topics",
)
taudit.add_argument("--output-dir", default="output",
                    help="parent dir for _topics.md (default: output)")
taudit.add_argument("--json", action="store_true", help="emit JSON instead of markdown")

tresolve = tsub.add_parser(
    "resolve",
    help="Promote / rename / remove a pending name; atomically update _topics.md "
         "+ all output/<slug>/index.json references",
)
tresolve.add_argument("pending_name", help="exact name from _topics.md ## Pending segment")
group = tresolve.add_mutually_exclusive_group()
group.add_argument("--rename", default=None,
                   help="promote to a different canonical name (rename in flight)")
group.add_argument("--remove", action="store_true",
                   help="reject pending: remove H3 entry + clear index.json refs to []")
tresolve.add_argument("--output-dir", default="output")
tresolve.add_argument("--timeout", type=float, default=10.0)
tresolve.add_argument("--json", action="store_true", help="emit JSON action result")

# In dispatch (after glossary_cmds):
topics_cmds = {  # Phase 10 D-07 — nested dispatch for `topics {bootstrap|audit|resolve}`
    "bootstrap": cmd_topics_bootstrap,
    "audit": cmd_topics_audit,
    "resolve": cmd_topics_resolve,
}

# In main(), final dispatch block:
if args.command == "queue":
    queue_cmds[args.queue_cmd](args)
elif args.command == "glossary":
    glossary_cmds[args.glossary_cmd](args)
elif args.command == "topics":  # NEW Phase 10
    topics_cmds[args.topics_cmd](args)
else:
    cmds[args.command](args)
```

**Why ordered after glossary:** New subparsers go to bottom (additive append). Backward-compat preserved.

### Anti-Patterns to Avoid

- **Anti-pattern: Algorithmic taxonomy generation in `cmd_topics_bootstrap`** — Computing taxonomy via tf-idf / clustering / keyword frequency over 17 archives violates K5 (Claude is decider). The CLI must require `--from-stdin` JSON. CONTEXT D-02.2 + D-02.6 both lock this.
- **Anti-pattern: `Phase 10 modifies CLAUDE.md`** — Phase 11 owns the `/summarize-video` Phase 7.6 hook addition. Phase 10 is pure infrastructure. CONTEXT line 174 explicit: "No CLAUDE.md change". Cross-checking Phase 11 ROADMAP SC#2 confirms.
- **Anti-pattern: Per-CLI individual lock files** — `output/.topics.lock` is single domain. A second-level "Approved-only" or "Pending-only" lock fragments serialization without benefit; mirror Phase 08's single-domain approach.
- **Anti-pattern: state.jsonl events for topics CLIs** — CONTEXT line 167 explicit: "Phase 10 不需要 state.jsonl 事件" (governance is ad-hoc, not part of per-slug `/summarize-video` lifecycle). Following the v1.1 pattern of `download` / `ingest` / `doctor` (no state events).
- **Anti-pattern: Slug-prefix log lines** — CONTEXT line 168: topics CLI is not slug-scoped, so no `[<slug>] <cmd>:` prefix (mirror `download` / `ingest` / `doctor`).
- **Anti-pattern: Modifying V11_FEATURES tuple in agent/_v11.py** — Phase 10 is UNCONDITIONAL (no marker gating). v1.0 archives already exist before Phase 10 ships, but they don't have `index.json` either, so they don't conflict with `_topics.md` (which is top-level, not per-slug). Reading `agent/_v11.py:33-55` confirms the V11_FEATURES allowlist is for v1.1 quality features; v1.2 knowledge-base does not use markers (CONTEXT line 119 reaffirmed in `.planning/v1.2-CANDIDATES.md`).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform exclusive file lock | `os.O_EXCL` / `fcntl.flock` directly | `agent._lock.FileLock` (v1.0 Phase 06 ship) | Stale-PID takeover handles Claude Code crash. msvcrt+fcntl unified API. Already test-covered in `tests/test_lock.py`. |
| Atomic JSON write | `path.write_text(json.dumps(...))` | `agent.io.write_json_atomic` (v1.0 Phase 02 ship) | tempfile + os.replace + PermissionError retry on Windows Defender / OneDrive. Used for index.json updates in `resolve_pending`. |
| Atomic markdown write | manual tempfile dance | `agent/glossary.py:_atomic_write` template | Already tested via Phase 08 `tests/test_glossary.py`. Copy/adapt the 24-line function verbatim. The pattern needs `os.fsync(tmp.fileno())` BEFORE `os.replace` for Windows durability. |
| Markdown H2/H3 + nested-list parsing | `markdown-it-py` / `mistune` | stdlib `re` (mirror `_H2_RE` from glossary.py + new `_H3_RE` + `_LIST_ITEM_RE`) | Schema constrained per D-01 (max 3 levels nesting; only `- ` bullets). Phase 08 proved sufficient for `_glossary.md`. |
| Nested CLI subparser routing | New dispatch convention | dict-of-callables pattern from `queue_cmds` / `glossary_cmds` (lines 1890-1900) | Established convention; backward-compat-preserving. |
| stdin JSON shape validation | jsonschema dep | Inline `isinstance` checks + ValueError | Schema is 2-deep (`{"taxonomy": [{"name": str, "subtopics": [{"name": str}, ...]}, ...]}`). Hand-rolled validator is ~15 LOC, no dep. |
| FileLock domain naming | New convention | `output/.topics.lock` mirrors `output/.glossary.lock` | Phase 08 SUMMARY locked the convention "Cross-slug accumulator file pattern: shared filename + sibling .lock + first-seen-wins schema. Future additive accumulators follow this template." |

**Key insight:** Phase 10's surface is ~95% pattern-reuse from Phase 06/07/08 ship code. The novel parts are (a) the read-modify-write 2-segment markdown schema and (b) atomic multi-file write. Both have crisp 1-pattern solutions.

## Common Pitfalls

### Pitfall 1: K5 source-grep self-match (P-08-01 deviation #2 lesson)

**What goes wrong:** A docstring or comment in `agent/topics.py` quotes the K5-forbidden write pattern verbatim (e.g., `# This module never calls write_text(output/<slug>/summary.md, ...)`) and the regex `r"write_text\([^)]*summary\.md"` matches the COMMENT itself, failing `test_K5_module_topics`.

**Why it happens:** Documentation tries to describe the K5 boundary in concrete terms; the regex doesn't distinguish "actual call site" from "commented-out call".

**How to avoid:** Phase 08-01 SUMMARY line 121-128 documented the fix: "Rewrote the comment to describe the K5 invariant in prose without quoting the regex pattern verbatim." Use phrases like "the per-slug summary artifact" / "the plan artifact" / "the schedule artifact" instead of literal filenames in module docstrings + comments.

**Warning signs:** Test `test_topics_module_no_summary_writes` fails locally during plan execute step.

### Pitfall 2: Forgotten substring split (Phase 08-01 belt-and-braces)

**What goes wrong:** Even with regex tests passing, ad-hoc `grep summary.md agent/topics.py` may match a docstring example. This was acceptable for `agent/glossary.py` because the slug-link template `[{slug}](slug/summary.md)` was a legitimate output format.

**Why it happens:** Defense in depth. Phase 08-01 split `_SLUG_LINK_TEMPLATE = "[{slug}]({slug}/" + "summary" + ".md)"` so even the literal substring `summary.md` doesn't appear in the source.

**How to avoid:** For Phase 10, `agent/topics.py` has NO legitimate `summary.md` use (unlike glossary). DO NOT include `summary.md` in any docstring example. If you need to refer to the summary artifact, use prose: "the slug summary file". Make the K5 test stricter: `assertNotIn("summary.md", agent/topics.py source)` literal-substring check.

**Warning signs:** D-06.1 test names: `test_topics_module_no_summary_writes` — this asserts the literal substring; matches what's needed (no legitimate use case for `summary.md` in topics.py).

### Pitfall 3: Empty `output/<slug>/index.json` glob at Phase 10 ship time

**What goes wrong:** `cmd_topics_audit` calls `output_dir.glob("*/index.json")` and gets empty list (Phase 11 hasn't shipped). Resulting JSON: `{"approved_with_counts": {topic: 0 for topic in approved}, "orphans": [all approved topics], ...}`. This makes ALL approved topics appear orphan, which is misleading.

**Why it happens:** D-03 audit semantics: "approved topic with 0 references is orphan". Pre-Phase-11, ALL topics have 0 references trivially.

**How to avoid:** In `cmd_topics_audit` output, distinguish "no index.json files exist (Phase 11 not yet shipped)" from "index.json files exist but topic is unused":

```python
if not index_paths:
    # Pre-Phase-11 state — orphan detection is not meaningful yet
    result["audit_note"] = (
        "No output/<slug>/index.json files found (Phase 11 not yet shipped). "
        "Orphan detection skipped; all approved topics shown with count=0."
    )
    result["orphans"] = []  # Not [] of all approved topics — that's misleading
```

This makes the `--json` output stable for Claude consumption AND keeps audit useful when Phase 11 lands.

**Warning signs:** Phase 10 verification step "run `topics audit --json` after `topics bootstrap`" — output shows audit_note + orphans=[].

### Pitfall 4: stdin JSON edge cases (Question A)

**What goes wrong:** User pipes malformed JSON (`{"taxono"`) / empty stdin (`echo "" | ...`) / valid JSON with duplicate names (`{"taxonomy": [{"name": "LLM"}, {"name": "LLM"}]}`) / valid JSON with non-string names (`{"taxonomy": [{"name": 42}]}`).

**Why it happens:** stdin is unstructured; users / scripts can pipe anything.

**How to avoid:** Phase 10 plan should specify these cases explicitly in `cmd_topics_bootstrap`:

| Edge case | Behavior | Exit code |
|-----------|----------|-----------|
| Empty stdin | `ValueError: --from-stdin requires JSON input on stdin; got empty input` | 1 |
| Malformed JSON | `json.JSONDecodeError` propagates with line/col info | 1 |
| Missing `taxonomy` key | `ValueError: stdin JSON must have top-level 'taxonomy' key` | 1 |
| `taxonomy` not a list | `ValueError: 'taxonomy' must be a list, got <type>` | 1 |
| Duplicate top-level names | `ValueError: duplicate category name in taxonomy: <name>` | 1 |
| `name` not a string | `ValueError: each taxonomy entry must have string 'name', got <type>` | 1 |
| Nesting > 3 levels (D-01.3) | `ValueError: taxonomy nesting exceeds 3 levels at <path>` | 1 |
| Idempotent re-invocation (Approved Taxonomy non-empty) | `{"action": "skipped", "approved_count": <existing>, ...}` + stderr hint | 0 |

Empty Approved Taxonomy at first run = expected (file may already exist with `<!-- (initially empty until bootstrap runs) -->` placeholder). The check is "non-comment / non-empty bullet list under `## Approved Taxonomy`".

### Pitfall 5: Approved Taxonomy alphabetical insertion (Question C)

**What goes wrong:** D-04.2 says `topics resolve` inserts a promoted entry "按字母序在合适位置". But where? Top-level category? Subcategory? Leaf? D-01.3 says max 3 levels. D-04.2 is ambiguous.

**Why it happens:** CONTEXT.md doesn't specify which level; Discussion Log "Auto-selected" doesn't elaborate.

**How to avoid:** Pending H3 entries (D-01.4) have NO category info — only `name`, `from_slug`, `chapter title`, `reason`. So when resolving, the user must implicitly decide a category by either:
- (a) Using `--rename "category/subcategory/topic"` with slash-delimited path (e.g., `--rename "LLM/LangChain"`)
- (b) Defaulting to top-level (insert as a new top-level category if no `--rename`)
- (c) Adding a `--parent` flag

**Recommended Phase 10 solution (within Claude's Discretion per CONTEXT line 117-118):**

- **Default behavior (no `--rename` flag):** Promote the pending name as a NEW top-level category. Caveat: `topics resolve` then leaves the user to manually move it under the right parent by editing `_topics.md` (deferred / acceptable per "Topic 树排序 / 重命名 CLI" deferred to v1.3).
- **`--rename` extended syntax:** Accept slash-delimited paths: `--rename "LLM/LangChain"` means "insert LangChain as a subtopic under LLM (creating LLM if needed)". This is a minor extension to D-04.1 ("[--rename <new-name>]"), still within "rename to a different canonical name". Document this clearly in `--rename` help text.

**Insertion alphabetical logic:** Within whatever parent (top-level by default, or `LLM` per `--rename`), insert into the alphabetically-sorted bullet list. Re-sort the parent's children after insertion to maintain canonical ordering. This is also why bootstrap (D-02) should output already-sorted taxonomy (Claude's Discretion).

**Warning signs:** Phase 10 plan should call this out in test cases: "T-resolve: promote 'LangChain' default → top-level; promote 'LangChain' --rename 'LLM/LangChain' → nested; promote 'X' when 'X' already exists as approved → fail-fast."

### Pitfall 6: Cross-CLI lock contention with `glossary append`

**What goes wrong:** User runs `topics resolve` (holds `output/.topics.lock`). Claude in another terminal runs `glossary append` (holds `output/.glossary.lock`). No contention — different lock domains. BUT: if user then runs `topics audit` (read-only, no lock per D-08.4) while another `topics resolve` is in flight, audit may read a partially-written `_topics.md` (between `_atomic_write(topics_path, ...)` and the first `_atomic_write(ip, ...)`).

**Why it happens:** Read-only audit doesn't take the lock; resolve's atomic-per-file write doesn't preserve cross-file atomicity from a reader's viewpoint.

**How to avoid:** This is INHERENT to the design (D-08.4 explicit: "锁不锁住 read-only audit"). The mitigation: audit reads `_topics.md` ONCE at start; that snapshot is consistent (atomic per-file). Index.json globs read AFTER `_topics.md` may show stale references (still `pending: <name>`), causing audit to report "X is in Pending but referenced in N index.json files" — which is the TRUE state at that read instant. Phase 11 generators should be writing `topics: ["pending: <name>"]` then; resolve happens later. The race window is small (single-user multi-terminal), and stale audit output during resolve is a 1-time observable that resolves itself.

**Recommendation:** Document the race in `cmd_topics_audit` docstring + `--json` output add `read_at: <ISO-8601>` field so user can re-run audit if confused. Don't add a lock (would slow down ad-hoc Claude consumption).

### Pitfall 7: Atomic write fsync requirement on Windows

**What goes wrong:** `tempfile.NamedTemporaryFile(...).write(...)` + `os.replace` succeeds, but Windows defers physical disk write. A power loss between rename and OS sync could leave a stale on-disk file.

**Why it happens:** Windows file caching defers writes to disk.

**How to avoid:** `agent/glossary.py:_atomic_write` line 73-74 calls `tmp.flush() + os.fsync(tmp.fileno())` BEFORE `os.replace`. Phase 10 must do the same. Verify by reading the existing `agent/glossary.py:_atomic_write` template literally. (Power-loss durability is best-effort; we don't pursue full ACID — acceptable for a single-user tool.)

**Warning signs:** None observable in test suite; this is preemptive correctness.

## Code Examples

### Example 1: `read_topics()` parser

```python
# agent/topics.py
from __future__ import annotations
import re
from pathlib import Path

_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_H3_RE = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
_LIST_ITEM_RE = re.compile(r"^(\s*)-\s+(.+?)\s*$", re.MULTILINE)


def read_topics(topics_path: Path) -> dict:
    """Parse output/_topics.md into structured form.

    Returns:
        {
          "approved": [
            {"name": "LLM", "subtopics": [
              {"name": "LoRA", "subtopics": []},
              {"name": "RAG", "subtopics": []},
            ]},
            ...
          ],
          "pending": [
            {"name": "LangChain", "from_slug": "BV...", "chapter_title": "...", "reason": "..."},
            ...
          ],
        }

    File-not-exists → returns {"approved": [], "pending": [], "exists": False}
    Malformed segment → log.warning + returns best-effort partial parse
    """
    if not topics_path.exists():
        return {"approved": [], "pending": [], "exists": False}
    text = topics_path.read_text(encoding="utf-8")
    h2_matches = list(_H2_RE.finditer(text))
    # Find Approved Taxonomy + Pending segments
    approved_text = ""
    pending_text = ""
    for i, m in enumerate(h2_matches):
        anchor = m.group(1).strip()
        seg_start = m.end()
        seg_end = h2_matches[i+1].start() if i+1 < len(h2_matches) else len(text)
        body = text[seg_start:seg_end]
        if anchor == "Approved Taxonomy":
            approved_text = body
        elif anchor == "Pending":
            pending_text = body
    # ... parse nested list from approved_text via _LIST_ITEM_RE indent levels
    # ... parse H3 entries from pending_text via _H3_RE + sub-bullet field extraction
    return {
        "approved": _parse_nested_list(approved_text),
        "pending": _parse_pending_entries(pending_text),
        "exists": True,
    }
```

**Source:** Pattern adapted from `agent/glossary.py:_find_term_section` (`_H2_RE.finditer` segment-bracket pattern) + `agent/glossary_audit.py:audit_glossary` (segment-end via next-H2-start).

### Example 2: `topics bootstrap --from-stdin` happy path

```bash
# User / Claude pipes JSON to bootstrap
echo '{
  "taxonomy": [
    {"name": "LLM", "subtopics": [
      {"name": "LoRA"}, {"name": "RAG"}, {"name": "Tokenizer"}
    ]},
    {"name": "Game-Dev", "subtopics": [
      {"name": "Godot"}, {"name": "ECS"}, {"name": "Pixel-Art"}
    ]},
    {"name": "Tooling", "subtopics": [
      {"name": "Claude Code"}, {"name": "Cursor"}, {"name": "TRAE SOLO"}
    ]},
    {"name": "Agent", "subtopics": [
      {"name": "MCP"}, {"name": "Hooks"}
    ]}
  ]
}' | python -m agent.tools topics bootstrap --from-stdin --json

# stdout:
# {
#   "action": "created",
#   "approved_count": 13,
#   "_topics_path": "output/_topics.md"
# }

# Re-running with same / different JSON → idempotent skip:
echo '{...}' | python -m agent.tools topics bootstrap --from-stdin --json
# stdout:
# {
#   "action": "skipped",
#   "approved_count": 13,
#   "_topics_path": "output/_topics.md"
# }
# stderr:
# WARNING: _topics.md already exists with non-empty Approved Taxonomy. Re-bootstrap by removing the file or use `topics resolve` to add individual topics.
```

### Example 3: `topics resolve` happy + restore-on-failure

```python
# Plan task: write tests/test_topics.py:test_resolve_atomic_restore_on_index_failure
def test_resolve_restores_topics_md_when_index_write_fails(self):
    """If 2nd index.json write fails, _topics.md must restore to pre-resolve state."""
    # Arrange: bootstrap with one approved + one pending
    # Create 2 fake output/<slug>/index.json with topics: ["pending: LangChain"]
    # Make 2nd index.json read-only to force write failure

    # Act: call resolve_pending("LangChain")
    with self.assertRaises(PermissionError):
        resolve_pending(self.topics_path, "LangChain")

    # Assert: _topics.md is byte-equal to pre-resolve state
    self.assertEqual(
        self.topics_path.read_text(encoding="utf-8"),
        self.pre_resolve_topics_md,
    )
    # Assert: 1st index.json is byte-equal to pre-resolve state (was tentatively written then restored)
    self.assertEqual(
        (self.tmpdir / "BV1" / "index.json").read_text(encoding="utf-8"),
        self.pre_resolve_index_1,
    )
```

**Source:** Pattern from `tests/test_glossary.py:test_T3_multiprocessing_race` (acquire lock + assert state) + `tests/test_lock.py:test_stale_pid_takeover` (failure-mode assertions).

### Example 4: K5 boundary test extension (Question D)

```python
# tests/test_k5_emitters.py addition
from agent.tools import (
    cmd_topics_bootstrap,
    cmd_topics_audit,
    cmd_topics_resolve,
)

# Forbidden patterns for cmd_topics_resolve: includes 5 D-29 core artifacts
# (summary.md / plan.md / paragraphs.json / segs.json / meta.json) — index.json is ALLOWED.
_RESOLVE_FORBIDDEN_PATTERNS = (
    # write_text patterns
    r"write_text\([^)]*summary\.md", r"write_text\([^)]*plan\.md",
    r"write_text\([^)]*paragraphs\.json", r"write_text\([^)]*segs\.json",
    r"write_text\([^)]*meta\.json",
    # open(...,'w') patterns
    r"open\([^)]*summary\.md[^)]*['\"]w", r"open\([^)]*plan\.md[^)]*['\"]w",
    r"open\([^)]*paragraphs\.json[^)]*['\"]w", r"open\([^)]*segs\.json[^)]*['\"]w",
    r"open\([^)]*meta\.json[^)]*['\"]w",
    # os.replace patterns
    r"os\.replace\([^)]*summary\.md", r"os\.replace\([^)]*plan\.md",
    r"os\.replace\([^)]*paragraphs\.json", r"os\.replace\([^)]*segs\.json",
    r"os\.replace\([^)]*meta\.json",
    # _atomic_write / write_json_atomic patterns
    r"_atomic_write\([^)]*summary\.md", r"_atomic_write\([^)]*plan\.md",
    r"_atomic_write\([^)]*paragraphs\.json", r"_atomic_write\([^)]*segs\.json",
    r"_atomic_write\([^)]*meta\.json",
    r"write_json_atomic\([^)]*summary\.md", r"write_json_atomic\([^)]*plan\.md",
    r"write_json_atomic\([^)]*paragraphs\.json", r"write_json_atomic\([^)]*segs\.json",
    r"write_json_atomic\([^)]*meta\.json",
)


def test_topics_bootstrap_no_index_json_writes(self):
    """cmd_topics_bootstrap source: forbid `index.json` / `summary.md` / `plan.md` literals."""
    src = inspect.getsource(cmd_topics_bootstrap)
    for forbidden in ("index.json", "summary.md", "plan.md", "schedule.json"):
        self.assertNotIn(forbidden, src, f"K5 violation: cmd_topics_bootstrap mentions {forbidden!r}")


def test_topics_audit_no_writes(self):
    """cmd_topics_audit source: any write API targeting any artifact is forbidden."""
    import re as _re
    src = inspect.getsource(cmd_topics_audit)
    # Forbid any write pattern (audit is read-only, period)
    write_patterns = (
        r"\.write_text\(", r"\.write_bytes\(",
        r"open\([^)]*['\"][aw]",
        r"os\.replace\(",
        r"_atomic_write\(", r"write_json_atomic\(",
    )
    for pat in write_patterns:
        self.assertFalse(
            _re.search(pat, src),
            f"K5 violation: cmd_topics_audit must be read-only; pattern {pat!r} found",
        )


def test_topics_resolve_only_writes_topics_md_and_index_json(self):
    """cmd_topics_resolve source: write patterns to D-29 core artifacts forbidden;
    writes to _topics.md and index.json are allowed (legitimate)."""
    import re as _re
    src = inspect.getsource(cmd_topics_resolve)
    for pat in _RESOLVE_FORBIDDEN_PATTERNS:
        self.assertFalse(
            _re.search(pat, src),
            f"K5 violation: cmd_topics_resolve write pattern {pat!r} found",
        )


def test_topics_module_no_summary_writes(self):
    """agent/topics.py module source: forbid `summary.md` / `plan.md` / `paragraphs.json`
    / `segs.json` / `meta.json` substrings entirely (no legitimate use). The literals
    `_topics.md` and `index.json` are LEGITIMATE here. The substrings `schedule.json`
    has no legitimate use either; forbid."""
    here = Path(__file__).parent.parent
    src = (here / "agent" / "topics.py").read_text(encoding="utf-8")
    for forbidden in ("summary.md", "plan.md", "paragraphs.json", "segs.json", "meta.json", "schedule.json"):
        self.assertNotIn(
            forbidden, src,
            f"K5 violation: agent/topics.py contains forbidden literal {forbidden!r}",
        )
    # write-pattern regex defense (mirrors agent/glossary.py exception):
    import re as _re
    for pat in _RESOLVE_FORBIDDEN_PATTERNS:
        self.assertFalse(
            _re.search(pat, src),
            f"K5 violation: agent/topics.py write pattern {pat!r} found",
        )
```

**Source:** Verbatim adaptation of `tests/test_k5_emitters.py:test_K5_module_glossary` (lines 116-137) + `test_K5_module_summary_lint` (lines 185-204).

## Bootstrap Feasibility Assessment (Question E)

**Verified by reading 8 sample summary.md titles + 5 first-pages from the 33 archives.** The corpus splits naturally into ~4 categories:

- **Game-Dev (~22 archives)**: Godot tutorials, AI-assisted pixel art (FrameRonin / Gemini), tilemap/blob algorithms, sprite generation, NPC animation. Subcategories naturally emerge: Godot / Pixel-Art / Tilemap / AI-Assisted-Art.
- **AI-Tooling (~7 archives)**: Claude Code (Hooks, /commands), TRAE SOLO, Cursor, Trae internal model. Distinct from "Game-Dev with AI tools" — these are about the tools themselves, not their use as means to a game-dev end. Subcategories: Claude-Code / Trae / Cursor.
- **LLM Concepts (~3 archives)**: Karpathy LLM Wiki, Compound Engineering, RAG-related discussion. Subcategories: LLM-Wiki / Compound-Engineering / RAG.
- **Health/Fitness (1 archive: `douyin_zidan_bojirouxunlian`)**: outlier — fitness theory, not videoSummary's primary domain. Decision: include as a top-level "Misc" / "Health" or leave for Pending.

**Question E resolution:** Bootstrap is feasible AND the natural taxonomy is fairly clean (4 main categories with 2-4 subcategories each = ~12-15 leaf topics). Some genuine ambiguity:

1. "Compound Engineering" — is it `LLM > Compound-Engineering` or `Tooling > Compound-Engineering` or its own top-level? Three valid choices. Phase 10 plan should leave this to **bootstrap-time Claude judgment**, not pre-bake.
2. "ECS" — is it `Game-Dev > ECS` or `Software-Architecture > ECS`? It appears in podcast about Karpathy/Lex (LLM context) AND in Godot tutorials. Multi-category membership is OUT OF SCOPE per "Topic alias / synonyms" deferred. Phase 10 plan should pick one canonical placement.
3. "AI-Assisted-Art" vs "Pixel-Art" vs "AI-绘画" — same concept, three names in different summaries. This is exactly what `_glossary.md` solves; topic taxonomy can use `Pixel-Art` canonical and let chapters tag it.

**Phase 10 plan recommendation:** Bootstrap should be a separate plan from infrastructure (Plan 10-02 in the proposed split). The plan executes the bootstrap interactively — Claude reads all 33 summary.md titles + scans content, proposes a JSON taxonomy, pipes via `--from-stdin`. The plan does NOT pre-bake taxonomy in CONTEXT.md (CONTEXT line 117 explicitly defers to "Claude 在 Phase 10 execute 时").

## `agent/_glossary.py` Exact API Surface (Question F)

Re-confirming from `agent/glossary.py` source:

| Function | Signature | Use in topics.py? |
|----------|-----------|-------------------|
| `glossary_append(slug, term, definition, *, output_dir=None, glossary_path=None, context="", timeout=10.0)` | Public | NO — append-only; topics is read-modify-write |
| `_atomic_write(target, content)` | Private (module-level) | YES — copy verbatim |
| `_resolve_paths(output_dir, glossary_path)` | Private | YES — adapt for topics (`(_topics.md, .topics.lock)`) |
| `_slug_link_substring(slug)` | Private | NO — not relevant |
| `_find_term_section(text, term)` | Private | YES — adapt for `_find_h2_segment(text, anchor)` (returns segment offsets for "Approved Taxonomy" / "Pending") |
| Module constants `GLOSSARY_FILENAME, LOCK_FILENAME, DEFAULT_OUTPUT_DIR, _FILE_HEADER, _H2_RE` | Module-level | YES — mirror `TOPICS_FILENAME, LOCK_FILENAME, DEFAULT_OUTPUT_DIR, _FILE_HEADER, _H2_RE, _H3_RE` |

**Critical difference between glossary.py and topics.py:**

- `glossary_append` is APPEND-ONLY: never modifies existing content; new term → new H2 + bullet at EOF; existing term + new slug → bullet added to that term's section. No deletion. No "moves between segments". First-seen-wins for definition body.
- `topics.resolve_pending` is READ-MODIFY-WRITE: must DELETE H3 entry from Pending segment AND INSERT bullet into Approved Taxonomy nested list AND maintain alphabetical ordering. No idempotent "skip on duplicate" — duplicate = error.
- `topics.append_pending` is also append-only, BUT writes to a SEGMENT (not EOF). Must locate `## Pending` segment, append H3 entry at end of that segment, before the next H2 (none — Pending is the last segment) — so it's effectively still EOF-append.

**Pattern reuse summary:**
- ✅ Reuse: file path resolution, FileLock context manager, `_atomic_write`, H2-segment regex, file-header template style
- 🔧 Adapt: segment-finder (3-segment instead of 1-segment-per-term), nested list parser, H3 entry parser, alphabetical insertion logic
- ❌ New: snapshot-restore for multi-file resolve, stdin JSON parser/validator, audit segment formatter, orphan detection

## Runtime State Inventory

> Phase 10 is greenfield infrastructure — no rename/refactor/migration. Section included for completeness with all categories explicitly stated.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `output/_topics.md` is a NEW file. No DBs, ChromaDB collections, or Mem0 memories store anything namespaced "topic" / "_topics". | None |
| Live service config | None — no n8n / Datadog / Cloudflare topic-related state. | None |
| OS-registered state | None — no Windows Task Scheduler / pm2 / systemd unit references "topics" by name. | None |
| Secrets/env vars | None — no env vars consumed by topics CLI. `output/.topics.lock` content carries PID + ISO ts (diagnostic only, mirror `_lock.py`). | None |
| Build artifacts | None — `agent/topics.py` is new; no compiled artifacts (Python source). `pyproject.toml` does not exist; no egg-info to invalidate. | None — `pip install` not needed; CLI is invoked via `python -m agent.tools` from repo root. |

**The canonical question:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?* — **Nothing.** Phase 10 is purely additive: new module + new CLI subcommands + new lock domain + new test file + (eventually) new top-level `output/_topics.md` file. No existing strings rename.

## Environment Availability

> Phase 10 has no external dependencies (pure stdlib + already-shipped agent/ modules). Skipping per Step 2.6 condition.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `unittest` (stdlib) — [VERIFIED: tests/test_glossary.py:20] |
| Config file | None — direct `python -m unittest tests.test_<name>` invocation |
| Quick run command | `python -m unittest tests.test_topics` |
| Full suite command | `python -m unittest discover tests` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| KB-07 | `_topics.md` schema (Approved + Pending segments parseable; max 3 levels nesting) | unit | `python -m unittest tests.test_topics.TestReadTopics` | ❌ Wave 0 |
| KB-08 | `topics bootstrap --from-stdin` writes Approved Taxonomy; idempotent skip on re-invoke; rejects empty/malformed/duplicate-name JSON | unit + integration | `python -m unittest tests.test_topics.TestBootstrap` | ❌ Wave 0 |
| KB-09 | `topics audit [--json]` reads `_topics.md` + globs `output/*/index.json`; output schema matches D-03.6; orphan detection; works when 0 index.json files exist | unit | `python -m unittest tests.test_topics.TestAudit` | ❌ Wave 0 |
| KB-10 | `topics resolve` atomic multi-file write; restore on partial failure; `--rename` + `--remove` modes; fail-fast on unknown pending name | unit + multiprocessing race | `python -m unittest tests.test_topics.TestResolve` | ❌ Wave 0 |
| KB-11 | K5 boundary statically asserted via 4 new tests | unit (regex source-grep) | `python -m unittest tests.test_k5_emitters` | ✅ EXISTS — extend with 4 new tests |
| KB-11 | `agent.topics.append_pending` Python API for Phase 11 generator | unit | `python -m unittest tests.test_topics.TestAppendPending` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m unittest tests.test_topics tests.test_k5_emitters`
- **Per wave merge:** `python -m unittest discover tests`
- **Phase gate:** Full suite green + `python -m scripts.replay_v10_archives` reports 33/0/30 PASS before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_topics.py` — covers KB-07 through KB-11 behavioral tests (mirror `tests/test_glossary.py` shape: T1-T6+ pattern)
- [ ] `tests/_tmp_topics/` — ASCII-safe per-test tmpdir directory + `.gitignore` entry (mirror `tests/_tmp_glossary/`)
- [ ] `tests/test_k5_emitters.py` — extend with 4 new test methods + import `cmd_topics_*` (extension to existing file, not new)
- Framework install: NONE — stdlib `unittest`

## Security Domain

> `security_enforcement` not explicitly set in `.planning/config.json` (file unchecked). Phase 10 is infrastructure for a single-user local CLI tool with zero network surface, zero secrets, zero auth. ASVS application is minimal — including this section per default-enabled convention with explicit "not applicable" notes.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Single-user local tool; no auth boundary |
| V3 Session Management | no | No sessions |
| V4 Access Control | no | OS file permissions only (filesystem ACL) |
| V5 Input Validation | yes | stdin JSON validation in `topics bootstrap`; positional arg validation in `topics resolve <pending-name>`; `--output-dir` path validation |
| V6 Cryptography | no | No encryption / signing |

### Known Threat Patterns for stdlib-only CLI

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal in `--output-dir` (e.g., `../../etc/passwd`) | Tampering | Use `Path` + (optional) `.resolve()` and validate it stays within repo root. CONVENTIONS.md `_validate_out_path` exists for CJK rejection; reuse pattern |
| Malformed stdin JSON DoS (huge nested taxonomy → memory blow) | DoS | `json.loads` is bounded by stdin size; CLI is local-only; user-provided input. Acceptable per single-user assumption. |
| FileLock stale-PID race (PID reuse) | Tampering | Already mitigated in `agent/_lock.py:53-74` via `os.kill(pid, 0)` probe + ProcessLookupError handling |
| Symlink attack on `output/_topics.md` | Tampering | `tempfile.NamedTemporaryFile + os.replace` pattern is symlink-respecting on POSIX (overwrites the target the symlink points to); on Windows, `os.replace` on a symlink replaces the target. Acceptable for single-user local. |

**Phase 10 security posture:** No hardening tasks beyond reusing existing patterns. Plan should NOT add jsonschema validation library (overkill); inline `isinstance` + `len(taxonomy)` bound check is sufficient.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Per-emitter literal-substring K5 grep | Intent-correct write-pattern regex | v1.1 Phase 07-03 deviation #2 → Phase 08-01 systematized | Phase 10 inherits — must use both patterns based on file/cmd context |
| Single-file lock domains | Cross-slug lock domains (`output/.glossary.lock` Phase 08, `~/.videoSummary/.queue.lock` Phase 07) | v1.1 ship | Phase 10 adds 3rd cross-slug domain `output/.topics.lock` |
| Markdown index files (`output/.index.md`) | JSON index files (`output/.index.json` planned in Phase 11) | v1.2 D-01 lock | Phase 10 ships taxonomy file in markdown (governance file is review-friendly), not JSON. JSON is for index.json (Phase 11 ownership). |
| Append-only accumulators (`_glossary.md`) | Read-modify-write governance (`_topics.md`) | v1.2 D-04 lock | Phase 10 introduces this pattern. Future v1.3+ governance files may follow. |

**Deprecated/outdated:**
- `markdown-it-py` / `mistune` — NOT used; stdlib `re` proven sufficient through Phase 08
- Plain `path.write_text(...)` for governance files — NOT atomic; always use `tempfile + os.replace + fsync` pattern
- `filelock>=3.16` PyPI dep — historical CONTEXT REQUIREMENTS mention; superseded by stdlib `agent/_lock.py:FileLock`

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pre-Phase-11 there are 0 `output/<slug>/index.json` files; `cmd_topics_audit` glob returns empty list. | Pitfall 3 + KB-09 test plan | [VERIFIED: bash glob returned exit code 2 — no index.json files exist] — risk is 0% |
| A2 | `agent/glossary.py` patterns transfer cleanly to `agent/topics.py` modulo the read-modify-write difference. | Pattern 1 + Question F | [VERIFIED: read agent/glossary.py:1-231 in full] — risk is LOW; ~15% of agent/glossary.py logic (idempotent slug-link detection) does not apply, but is replaced by Pending-segment H3 parsing. |
| A3 | The 4 new K5 tests use a mix of literal-substring + write-pattern regex per file context (Pattern 2 decision matrix). | Pattern 2 + Question D | [VERIFIED: tests/test_k5_emitters.py read in full] — risk is LOW; matches Phase 08+09 ship convention. |
| A4 | stdin JSON edge cases (Question A) — empty / malformed / duplicate-name are user-correctable; Phase 10 plan should NOT silently accept any of these. | Pitfall 4 | [ASSUMED based on Python conventions] — risk is LOW; users / Claude will get clear error messages and re-pipe corrected JSON. |
| A5 | Approved Taxonomy alphabetical insertion (Question C) — top-level by default, `--rename "category/leaf"` for nested placement. | Pitfall 5 | [ASSUMED — within Claude's Discretion per CONTEXT line 117-118] — risk is MEDIUM (this extends D-04.1 syntax beyond its literal `[--rename <new-name>]`); plan reviewer should validate this fits user's mental model. ALTERNATIVE: drop nested-rename, leave manual editing of `_topics.md` as the v1.3 path. |
| A6 | Resolve atomic write race window (Pitfall 6) — read-only audit may see inconsistent state during in-flight resolve; acceptable per design. | Pitfall 6 | [VERIFIED: D-08.4 explicit "锁不锁住 read-only audit"] — risk is LOW; documented as inherent. |
| A7 | Phase 10 verification SHOULD run `scripts/replay_v10_archives.py` post-Phase-10 to confirm 33/0/30 PASS even though `_topics.md` is outside the replay scope (defensive). | Project Constraints + ROADMAP Phase 11 SC#5 + Phase 12 SC#2 | [ASSUMED based on v1.1 ship discipline] — risk is LOW; it's a 30-second sanity check; doing it is strictly safer than not. |
| A8 | The bootstrap feasibility assessment (Question E) found ~4 natural top-level categories with ~12-15 leaf topics. Phase 10 plan defers actual taxonomy authorship to plan-execute time. | Bootstrap Feasibility + Pitfall 5 | [VERIFIED: read 8 sample summary.md titles + 5 first-pages] — risk is LOW; the 4-category split is the floor, not the ceiling; Claude may propose 5-6 categories and that's still bounded. |
| A9 | Plan 10 splits into 2 plans (10-01 infrastructure + 10-02 first-bootstrap-execution); mirrors v1.1 Phase 08 cadence (1 module-creation plan + lightweight integration plan). | Summary | [ASSUMED based on Phase 08-01 + 08-02 split pattern] — risk is LOW; planner can also choose 1 plan with 2-3 tasks. The split is recommendation, not lock. |
| A10 | No state.jsonl events emitted by topics CLIs. | Anti-Pattern in Pattern 4 | [VERIFIED: CONTEXT line 167 explicit "Phase 10 不需要 state.jsonl 事件"] — risk is 0% |

**If this table is empty:** N/A — 10 entries above. Most are VERIFIED (read source code or grep evidence). 3 are ASSUMED (A4, A5, A7, A9): A4 and A7 are low-risk procedural assumptions; A5 is the genuine open design choice that the planner / discuss-phase may want to confirm with user before plan execute (whether `--rename "category/leaf"` slash syntax is acceptable, or whether manual edit is preferred).

## Open Questions (RESOLVED)

> All 3 questions below have been actioned in Plan 10-01 / Plan 10-02:
> - Q1 → Plan 10-01 implements `topics resolve --rename "category/leaf"` slash syntax + `TestResolve.test_resolve_rename_nested_path`
> - Q2 → Plan 10-01 cmd_topics_audit adds `read_at: <ISO-8601>` field to JSON output
> - Q3 → Plan 10-02 executes the first real bootstrap reading 17+ archives

1. **[RESOLVED]** Approved Taxonomy nested insertion syntax (Question C / Assumption A5)
   - **What we know:** D-04.2 says alphabetical insertion at "appropriate position"; D-01.3 caps at 3 levels. Pending entries have no parent-category info (only name + slug + chapter + reason).
   - **What's unclear:** Whether `topics resolve --rename "category/leaf"` slash-delimited syntax is the right UX, or whether to add a `--parent <category>` flag, or to just promote-as-top-level and let user manually re-organize `_topics.md` (v1.3 deferred).
   - **Recommendation:** Plan the simplest path (top-level promote by default; document manual re-organize as the path for nesting). Add `--parent <category>` flag if user requests during planning. Avoid scope creep beyond CONTEXT D-04.1's `[--rename <new-name>]`.

2. **What if user runs `topics audit` while resolve is in-flight (Question / Pitfall 6 outcome)**
   - **What we know:** D-08.4 explicit no-lock for audit. Resolve writes per-file atomic but cross-file is not transactional from reader's view.
   - **What's unclear:** Whether to add a `read_at: <ISO-8601>` timestamp to audit JSON output as a hint, or stay quiet about the race.
   - **Recommendation:** Add `read_at: <ISO-8601>` to `--json` output (negligible cost, enables Claude to spot inconsistency). Default markdown output mentions read time at the top.

3. **Bootstrap content in Plan 10-02 — Phase 10 plan or out-of-scope?**
   - **What we know:** CONTEXT D-02.2 says bootstrap is "Claude is decider — bootstrap 是 Claude 写入 _topics.md 的工具". The Phase 10 ROADMAP SC#2 says "跑 `topics bootstrap` 后 `output/_topics.md` 顶部 `## Approved Taxonomy` 段非空" — so the SC requires actual content.
   - **What's unclear:** Whether the actual bootstrap invocation is part of Phase 10 deliverable (Plan 10-02 executes it) or Phase 10 ships only the CLI + Phase 11 ships first-actual-content.
   - **Recommendation:** Plan 10-02 should execute the first bootstrap (Claude reads 33 summary.md, proposes JSON, pipes via `--from-stdin`). This satisfies SC#2 byte-level acceptance. Leaving content for Phase 11 risks Phase 10 close gate failing.

## Sources

### Primary (HIGH confidence)
- `agent/_lock.py` — full read; FileLock implementation + stale-PID takeover
- `agent/glossary.py` — full read (231 lines); pattern reference for `agent/topics.py`
- `agent/glossary_audit.py` — full read; read-only audit pattern
- `agent/queue.py` — full read; cross-slug lock domain pattern
- `agent/tools.py` lines 1-200, 1480-1600, 1614-1910 — CLI handler pattern + nested subparser
- `agent/io.py` lines 1-145 — atomic write helpers + `write_json_atomic`
- `agent/_v11.py` — full read; conventions for `_marker_path` / module style
- `agent/verifier_events.py` lines 1-50 — module docstring K5 boundary phrasing
- `agent/summary_lint.py` lines 1-40 — module docstring K5 boundary phrasing
- `tests/test_k5_emitters.py` — full read (208 lines); 13 K5 tests + write-pattern regex tuple
- `tests/test_glossary.py` lines 1-80 — test shape pattern
- `.planning/phases/10-topic-taxonomy-governance-bootstrap-cli/10-CONTEXT.md` — full read; locked decisions
- `.planning/phases/10-topic-taxonomy-governance-bootstrap-cli/10-DISCUSSION-LOG.md` — full read; auto-resolved alternatives
- `.planning/REQUIREMENTS.md` — full read; KB-07..KB-11 atomic statements
- `.planning/ROADMAP.md` — full read; Phase 10 SC #1-5 + Phase 11/12 dependencies
- `.planning/v1.2-CANDIDATES.md` — full read; D-01..D-09 architectural decisions
- `.planning/STATE.md` — full read; current phase position
- `.planning/codebase/CONVENTIONS.md` — full read; Python style + CLI conventions
- `.planning/codebase/STACK.md` lines 1-60 — Python version + stdlib/third-party split
- `.planning/milestones/v1.1-phases/08-writing-rules-claude-md-extensions-glossary/08-01-SUMMARY.md` — full read; deviation #2 lesson + intent-correct write-pattern regex precedent
- `output/BV132wizyEEB/summary.md`, `output/douyin_karpathy_llm_wiki/summary.md`, `output/douyin_claude_code_hooks/summary.md`, `output/BV1HG9JBsEPK/summary.md`, `output/douyin_zidan_bojirouxunlian/summary.md`, `output/BV1jXXaBQE1R/summary.md` — first 20-60 lines of 6 representative archives for taxonomy feasibility check
- 33 archive titles via bash glob (heads of all `output/*/summary.md`)

### Secondary (MEDIUM confidence)
- `.planning/milestones/v1.1-phases/09-correctness-automation-verifier-subagent-auto-rewrite/09-01-SUMMARY.md` — Phase 09-01 K5 boundary test extension lessons (literal `summary.md` may legitimately appear in argparse help)

### Tertiary (LOW confidence)
- None — Phase 10 patterns are entirely determined by codebase grep + CONTEXT decisions; no WebSearch needed.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every recommended module is verified by reading the source file
- Architecture: HIGH — patterns mirror Phase 06/07/08/09 ship code; verified by reading the precedent modules
- Pitfalls: HIGH — 5 of 7 pitfalls are documented v1.1 lessons (Phase 07-03 dev #2, Phase 08-01 belt-and-braces, Phase 08-01 stale-PID, Phase 09-01 module docstring); 2 are inferred from CONTEXT decisions (alphabetical insertion + read-only audit race window)
- Bootstrap feasibility: MEDIUM — based on titles + 6 first-pages; full corpus content not exhaustively read
- K5 test patterns: HIGH — verbatim adapted from Phase 08-01 + Phase 09-01 ship code

**Research date:** 2026-05-04
**Valid until:** 2026-06-04 (30 days; v1.2 milestone is in-flight — patterns may evolve via Phase 11 ship)

---

*Phase: 10-topic-taxonomy-governance-bootstrap-cli*
*Research completed: 2026-05-04*
