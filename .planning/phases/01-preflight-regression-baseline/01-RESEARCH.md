# Phase 1: Preflight & Regression Baseline — Research

**Researched:** 2026-04-30
**Domain:** Brownfield preflight — schema freeze, regression baseline, encoding audit, Windows zh-CN docs
**Confidence:** HIGH (codebase ground-truth verified; no external libraries to validate)

## Summary

This phase has zero new features. It commits a regression safety net before later phases touch schemas, schema-tolerant loaders so future `schema_version: 2` work doesn't break the 17-archive queue, an encoding-audit pass-evidence file, and a small CLAUDE.md addition documenting `chcp 65001` + `PYTHONUTF8=1`. The work is overwhelmingly *write three new files plus tweak six load sites* — no library research, no API decisions. The hard parts are: (a) deciding **where** the loader-tolerance helper lives so it's reused everywhere without monkey-patching anything, (b) the **exact** v1 field set documented retroactively (must match existing files byte-for-byte), and (c) writing a runbook that's actually useful to a future Claude+human pair, not a checkbox-compliance artifact.

Verified facts: all three baseline videos already have full SMTPF artifacts. The four committable files (summary.md + meta.json + segs.json + paragraphs.json) total **101,403 bytes across all three slugs combined** — well under any git-friendly threshold; no LFS needed [VERIFIED: `du`/`ls -l` on each dir]. The codebase already uses `encoding="utf-8"` on every text I/O — PRE-04 is *literally* a documentation task, not a code task [VERIFIED: grep across `agent/` + `src/`]. `tests/` directory does not exist; `.gitignore` does not contain a `tests/` glob, so `tests/regression/` will be tracked normally [VERIFIED: `.gitignore` read].

**Primary recommendation:** Create one new module `agent/io.py` exporting three loader functions (`load_meta`, `load_segs`, `load_paragraphs`) plus a `SCHEMA_VERSION = 1` constant. Patch the six existing load sites (`agent/tools.py:77,94`, `agent/prepare.py:77,92,114`, `src/pipeline.py:34,46`) to call those helpers. Land schema docs in a new `docs/schema-versions.md`. Use `tests/regression/<slug>/` as the snapshot location and `tests/regression/regression-check.md` as the runbook. Encoding audit evidence appends to `regression-check.md` (one combined doc keeps the runbook self-contained).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Baseline 视频选择 (PRE-01)**
- **D-01:** 三条基准视频锁定为 `BV132wizyEEB`（AI 美术工作流 — 代码/工作流类）+ `BV1C9QCBdE1U`（Godot 教程：伤害数字生成器 — Godot/代码密集类）+ `douyin_trae_ai`（TRAE AI 第二大脑 — AI/UI 演示类），覆盖 milestone 三大目标视频形态。
- **D-02:** **`BV1C9QCBdE1U` 替换掉 ROADMAP 原本提名的 `godot_brave`** — `output/godot_brave/` 实际只剩 `cookies.txt`，没有可冻结的 `summary.md` / 三件套 JSON。`BV1C9QCBdE1U` 是「Godot 教程：伤害数字生成器（暴击变色、随机漂浮、可复用）」，有完整 SMTPF 工件，且代码密集度比纯演示类视频更适合做代码抄录质量的回归。

**schema_version 追加策略 (PRE-03)**
- **D-03:** 采用 **loader-only 容忍** 方案 — **不修改任何已有 `output/<slug>/` 文件**。所有 17 条历史归档保持现状不动。
- **D-04:** loader 行为：读到 `dict` 类型工件时取 `obj.get("schema_version", 1)`，读到 `list` 类型工件时一律视为 `schema_version=1`（因为 `segs.json` / `paragraphs.json` 都是顶层 list，把它们改为 `{"schema_version":..., "items":[...]}` 包装即破坏向后兼容，违反 PROJECT.md K3）。
- **D-05:** 「retroactive 文档化」交付物是一段 `docs/schema-versions.md`（或在 CLAUDE.md/AGENT_DESIGN.md 内嵌一节，由 planner 决定具体落点），用文字记录三类工件 v1 的字段集合，作为后续 v2 升级的对照基准。
- **D-06:** 当未来确实需要 v2 schema 时，迁移代价由那个 phase 承担（包括是否做 wrapping、是否写 migration script），本 phase 只准备好 loader 接口与文档锚点。

**回归 diff 验证方法 (PRE-02)**
- **D-07:** 使用 **Claude 手工 eyeball diff** 作为回归验证方法 — 不写任何自动化断言脚本、不算结构化指纹、不做 md5 严格哈希。
- **D-08:** runbook (`tests/regression/regression-check.md`) 列出三步：(1) `git checkout` 某个 commit / branch；(2) 把 `tests/regression/<slug>/` 拷贝进 `output/<slug>/`，**只覆盖 JSON 三件套**（避免重新下载 30-200MB video.mp4），运行需要验证的 stage；(3) Claude `Read` 新生成的 `summary.md` 与 `tests/regression/<slug>/summary.md` 做语义对比。
- **D-09:** 「通过」标准是 Claude 判断「无 surprise drift」— 允许有意改进（更精确的代码抄录、更紧凑的章节），不允许结构、时间戳、章节数发生未声明的变化。哪怕 Phase 5 之后 prose 风格升级，runbook 也只要求「能解释每一处差异」，不要求字节级一致。
- **D-10:** 每次后续 phase merge 之前，跑 3 条基准（人工触发，不进 CI），把通过情况写在那个 phase 的 VERIFICATION.md 里。

**冻结范围 (PRE-01)**
- **D-11:** `tests/regression/<slug>/` 下提交 **`summary.md` + `meta.json` + `segs.json` + `paragraphs.json`** 四件，**不**提交 `frames/` / `audio.wav` / `video.mp4` / `video.info.json`。
- **D-12:** 三个 slug 的实际目录命名 `tests/regression/BV132wizyEEB/`、`tests/regression/BV1C9QCBdE1U/`、`tests/regression/douyin_trae_ai/`，与 `output/<slug>/` 子目录约定 1:1 映射，runbook 的 copy 命令直接 `cp -r tests/regression/<slug>/* output/<slug>/` 即可。
- **D-13:** 冻结这一步只跑一次（在本 phase 内），后续 phase 通过 `--force` 重跑各 stage 验证，但 `tests/regression/` 内的快照在本 milestone 内**不更新**。

**Encoding 审计 (PRE-04)**
- **D-14:** 审计范围 = `agent/` + `src/` 全部 `.py` 文件。已先行扫描确认现状：30+ 处 `read_text` / `write_text` 全部带 `encoding="utf-8"`；唯三的「裸 open」是 (a) `agent/douyin_downloader.py:194` 的 `open(video_path, "wb")`、(b) `agent/embed.py:79` `PILImage.open(p)`、(c) `agent/frames_v2.py:74` `Image.open(f.path)` — 三处都是正确的，**PRE-04 实际工作量约 0**。
- **D-15:** 即便如此，本 phase 仍要正式提交一份「audit pass」证据。
- **D-16:** 审计**包括** v2 模块（`frames_v2.py`、`pass1_classify.py`、`embed.py`、`frame_store.py`、`prepare.py`），尽管它们不在主 ¥0 路径上，但仍可被 import。

**Windows zh-CN 设置文档化 (PRE-05)**
- **D-17:** 在 `CLAUDE.md` 「环境变量」节之上或之后，新增一小节「Windows zh-CN 终端设置」，给出两条命令：`chcp 65001`、`PYTHONUTF8=1`。
- **D-18:** 文档措辞为「推荐而非必需」— 现有 `agent/tools.py:59` 的 `ensure_ascii=True` 兜底逻辑保留不动。

### Claude's Discretion

- `tests/regression/` 是放在 repo 根目录（`tests/regression/`）还是 `.planning/regression/` — 倾向 repo 根（标准约定）
- `regression-check.md` 是 Markdown 还是带 fenced shell 的复制粘贴 runbook — 凭 planner 判断
- loader-tolerance 改动究竟落在哪些文件里 — planner 决定，但要保持「轻接口」原则，不引入新依赖
- encoding-audit 证据是单文件还是 inline 在 regression-check.md — 凭 planner 判断
- `docs/schema-versions.md` 还是嵌入 CLAUDE.md / AGENT_DESIGN.md — 凭 planner 判断，但必须有一处可被 grep 到的「v1 字段集合」记录

### Deferred Ideas (OUT OF SCOPE)

- **结构化回归脚本**（`verify_baseline.py` 算 line/frame/section count）— 推迟到证据显示手工 eyeball diff 不够用之后
- **`tests/regression/` snapshot 自动更新机制**（PR 触发时 diff、强制人工 ack）— 本 milestone 内人工触发足够
- **GoldenStorm / pytest-regressions 等 fixture 框架** — 不引入；与 ¥0 + 「Claude 是 verifier」哲学不符
- **Frame-level 回归**（验证抽帧确定性）— `output/<slug>/frames/` 不进 git
- **schema_version v2 真实迁移代码** — 等到第一个真正想升级 schema 的 phase 来承担
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PRE-01 | Project commits a `tests/regression/` directory with frozen `summary.md` baselines from 3 archived videos (`BV132wizyEEB` for code, `BV1C9QCBdE1U` for game/Godot, `douyin_trae_ai` for AI/UI). | §"Baseline Snapshot Inventory" enumerates the 12 exact files and verified byte sizes (101 KB total). §"Three Baseline JSON Sizes" confirms git-friendliness. §".gitignore Interaction" confirms `tests/` is not silently ignored. |
| PRE-02 | Project includes a `regression-check.md` runbook describing how to re-run the new flow on the 3 baselines and manual-diff against committed `summary.md`. | §"Regression Runbook Structure" gives the exact runbook skeleton with copy-paste commands. §"Manual-Diff Prompt Template" gives the eyeball-diff prompt verbatim. |
| PRE-03 | `meta.json` / `segs.json` / `paragraphs.json` schemas are documented as `schema_version: 1` retroactively; loaders default to `1` when the field is absent (forward-compat foundation). | §"JSON Shape Ground Truth" gives the exact v1 field set from real files. §"Loader-Tolerance Landing Point" recommends a single-module approach with line-numbered patch list. §"docs/schema-versions.md Skeleton" gives the doc template. |
| PRE-04 | Every `open()` call in `agent/` and `src/` uses explicit `encoding="utf-8"` (audited and fixed where missing). | §"Encoding Audit — Current State" verifies 100% compliance. §"Encoding Audit Grep Commands" gives the exact reproduction commands. §"Audit Pass Evidence Format" gives the document template. |
| PRE-05 | `CLAUDE.md` documents `chcp 65001` and `PYTHONUTF8=1` as recommended Windows zh-CN setup steps. | §"CLAUDE.md Insertion — Exact Wording" gives the verbatim Markdown to insert and the precise insertion point (between line 39 and line 41 — between 「抖音支持」section and 「环境变量」section). |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

| Constraint | Source | Implication for Phase 1 |
|------------|--------|-------------------------|
| 全流程 ¥0 成本（Claude Max 计划） | CLAUDE.md:4 | No paid CI, no diff service, no automated test runner — manual eyeball diff is correct per D-07 |
| Claude Code 是唯一决策者 | CLAUDE.md:5 | Runbook is for "Claude+human" not for an automated pipeline; "pass" criterion is Claude's judgment |
| 帧理解不需要 API — 直接 Read | CLAUDE.md:19 | summary.md regression compares prose+code accuracy, NOT frame-extraction determinism (frames not committed per D-11) |
| `--force` 标志触发 cache override | CLAUDE.md:7 (transcribe line) | Runbook's "rerun stage" instruction must use `--force` to bypass the file-existence cache |
| `output/<slug>/frames/seg_<start>_<index>.jpg` 命名约定 | CLAUDE.md:103 + agent/tools.py:114 | Frame filename grammar is part of v1 schema-as-convention; document in schema-versions.md even though frames aren't committed |
| 时间戳只用字幕里真实存在的 | CLAUDE.md:153 | Eyeball-diff prompt should specifically check that timestamps in regenerated summary.md still exist in segs.json |
| 不注水不编造 | CLAUDE.md:156 | Eyeball-diff "pass" criterion must distinguish "intentional improvement" from "fabrication" |

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| stdlib `pathlib` | py3.11+ | Path manipulation in `agent/io.py` loader helpers | Project-wide convention; `os.path` is forbidden per CONVENTIONS.md |
| stdlib `json` | py3.11+ | Read/write artifact JSON | Already used in 30+ sites; idiom locked |
| `git` | any | Commit baseline + runbook | Standard; no LFS per D-11 (files are tiny) |

### Supporting
*None* — this phase introduces no new dependencies. Honoring the 「轻接口」principle from CONTEXT.md Claude's Discretion.

### Alternatives Considered

| Instead of | Could Use | Why Rejected |
|------------|-----------|--------------|
| `agent/io.py` central module | In-place `if isinstance(obj, list): ...` patches at each load site | Six call sites means six places to update when v2 lands; contradicts "single landing point for v2 migration" goal in D-06 |
| `agent/io.py` central module | Helper inside `agent/asr_v2.py` (paragraphs producer) | `asr_v2.py` doesn't load `meta.json`; would still need a separate helper for meta — splitting hurts more than it helps |
| `docs/schema-versions.md` | Inline section in CLAUDE.md | CLAUDE.md is workflow-facing for `/summarize-video` users; schema reference is for developers — different audiences, mixing them dilutes both. CLAUDE.md grows monotonically (PRE-05 already adds Windows section); avoid extra bloat |
| `docs/schema-versions.md` | `tests/regression/schema-versions.md` | Coupling docs to tests dir conflates "regression evidence" with "schema reference" |
| Two files (regression-check.md + encoding-audit.md) | One combined runbook | Single runbook is self-contained; one fewer file to find. Encoding audit is short (~30 lines) so doesn't dwarf the runbook |
| Auto-diff script (e.g., `difflib`) | Manual eyeball diff | Locked OUT by D-07 |
| `pytest` fixture framework | Plain Markdown runbook | Locked OUT by Deferred Ideas |

**Installation:** None. Phase 1 introduces zero pip-installable dependencies.

**Version verification:** Not applicable — no new packages.

## Architecture Patterns

### Recommended Project Structure (post-Phase 1)

```
videoSummary/
├── agent/
│   ├── io.py                          # NEW — schema_version-tolerant loaders
│   ├── tools.py                       # MODIFIED — call agent.io helpers
│   ├── asr_v2.py                      # unchanged
│   ├── prepare.py                     # MODIFIED — call agent.io helpers
│   └── ... (rest unchanged)
├── src/
│   ├── pipeline.py                    # MODIFIED — call agent.io helpers
│   └── ... (rest unchanged)
├── docs/                              # NEW directory
│   └── schema-versions.md             # NEW — v1 field-set reference
├── tests/                             # NEW directory (first time in repo history)
│   └── regression/
│       ├── regression-check.md        # NEW — runbook + encoding-audit evidence
│       ├── BV132wizyEEB/
│       │   ├── meta.json
│       │   ├── segs.json
│       │   ├── paragraphs.json
│       │   └── summary.md
│       ├── BV1C9QCBdE1U/             # same four files
│       └── douyin_trae_ai/            # same four files
├── CLAUDE.md                          # MODIFIED — new "Windows zh-CN 终端设置" section
└── ... (rest unchanged)
```

### Pattern 1: Schema-Tolerant Loader Helper

**What:** Three pure functions in `agent/io.py` that wrap `json.loads(path.read_text(encoding="utf-8"))` with a schema-version normalization step, then return the parsed object.

**When to use:** Every code site that loads `meta.json`, `segs.json`, or `paragraphs.json`. Replaces six identical inline `json.loads(...read_text(...))` patterns.

**Example (recommended skeleton, agent/io.py):**

```python
"""Schema-tolerant loaders for output/<slug>/ artifacts.

PRE-03 (Phase 1): centralizes the schema_version normalization so future
v2 migrations have a single landing point. Today all artifacts are v1;
this module exists to make tomorrow's v2 add a single switch statement
instead of a codebase-wide edit.

Behavior:
- Dict-shaped artifacts (meta.json): obj.get("schema_version", 1) — absence == v1
- List-shaped artifacts (segs.json, paragraphs.json): always treated as v1
  (top-level list cannot carry a schema_version field without breaking
  backward-compat per PROJECT.md K3 / D-04)

When v2 lands, add a migrate_to_current(obj) call inside each loader and
update the SCHEMA_VERSION constant. No call site changes.
"""
from __future__ import annotations

import json
from pathlib import Path

SCHEMA_VERSION = 1  # current version for new artifacts; bump in v2 phase

# 三类工件的 v1 字段集合参考: docs/schema-versions.md


def load_meta(path: str | Path) -> dict:
    """加载 meta.json. Dict 工件支持 schema_version 字段 (缺失则视为 v1)."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    # v1: schema_version absent or == 1 → no migration needed
    # future v2: insert obj = _migrate_meta(obj) here
    return obj


def load_segs(path: str | Path) -> list[dict]:
    """加载 segs.json. 顶层 list 类型, 一律视为 schema_version=1.

    历史决定 (D-04): 把 segs.json 改成 wrapped dict 即破坏老归档, 故顶层
    list 是 v1 的稳定契约; 未来 v2 如需结构升级, 由那个 phase 决定是否
    引入 wrapping (并写 migration script).
    """
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(
            f"segs.json must be a list (v1); got {type(obj).__name__} at {path}"
        )
    return obj


def load_paragraphs(path: str | Path) -> list[dict]:
    """加载 paragraphs.json. 同 load_segs, 顶层 list 即 v1."""
    obj = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(obj, list):
        raise ValueError(
            f"paragraphs.json must be a list (v1); got {type(obj).__name__} at {path}"
        )
    return obj
```

**Source:** Synthesized from CONVENTIONS.md (the `json.loads(path.read_text(encoding="utf-8"))` idiom is the locked codebase pattern, present at 30+ sites). The dict-vs-list branching follows D-04.

### Pattern 2: In-Place Loader Patch

**What:** Replace existing `json.loads(<path>.read_text(encoding="utf-8"))` with `load_meta(<path>)` / `load_segs(<path>)` / `load_paragraphs(<path>)`.

**When to use:** Each of the six load sites (enumerated below). Patch is one-line per site.

**Example (agent/tools.py:77 transformation):**

Before:
```python
segs_data = json.loads(segs_file.read_text(encoding="utf-8"))
```

After:
```python
from agent.io import load_segs
segs_data = load_segs(segs_file)
```

### Anti-Patterns to Avoid

- **Wrapping segs.json / paragraphs.json into `{"schema_version": 1, "items": [...]}` for "consistency"** — would break all 17 archived `output/<slug>/paragraphs.json`. Locked OUT by D-04 / PROJECT.md K3.
- **Modifying any file under existing `output/<slug>/`** — the freeze is strict. Locked OUT by D-03.
- **Adding a `schema_version` field when writing v1 artifacts** — would change the on-disk shape compared to the 17 archives. The constant `SCHEMA_VERSION = 1` exists in code but is **not** written to disk in this phase; that's a Phase 2 (RES) decision per the roadmap mapping (P7.4 lives in Phase 2).
- **Auto-promoting a regression failure into "update the snapshot"** — D-13 forbids in-milestone snapshot updates. If a future phase intentionally drifts the output, that phase commits the new snapshot with explanation in commit message.
- **Writing the runbook in present tense as if it's documentation** — it's an executable runbook. Use imperative second-person ("Copy this", "Run this", "Compare these two files").

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON load with explicit encoding | A new helper that re-implements `json.loads(path.read_text(encoding="utf-8"))` from scratch | The existing idiom — wrap it in `agent/io.py` thinly, do not reinvent | 30+ sites already use the idiom; consistency wins |
| Path normalization | `os.path.join` / string concatenation | `pathlib.Path` (already standard everywhere) | CONVENTIONS.md locks pathlib |
| Encoding-audit grep | A custom Python AST scanner | `ripgrep` / Grep tool with the exact patterns in §"Encoding Audit Grep Commands" | Audit is read-only evidence, not enforcement; grep output IS the evidence |
| Diff between summaries | A line-by-line diffing script | Claude reads both summary.md files in one session and judges semantically | D-07 explicitly forbids automation; eyeball diff is the design |
| Schema migration | A migration framework (e.g., `alembic`-style) | Phase 1 ships zero migration code — just the loader interface and one constant | Migration cost belongs to whichever phase actually bumps the version (D-06) |

**Key insight:** The phase's job is to *avoid building* infrastructure prematurely. Every line of code in Phase 1 should serve PRE-01..05's measurable conditions, not anticipate Phase 2+. The single new module (`agent/io.py`) is the absolute minimum needed to satisfy "loaders default to schema_version=1 when absent."

## Common Pitfalls

### Pitfall 1: Over-engineering the loader

**What goes wrong:** Implementing a full-blown migration registry (`MIGRATIONS = {1: migrate_v1_to_v2, ...}`) when there's no v2 to migrate to.

**Why it happens:** Schema-version code feels like infrastructure that needs "doing right."

**How to avoid:** Phase 1's loader is trivially small (~30 lines total). Insert a `# future v2: insert ...` comment at the migration point, but don't write the framework. D-06 explicitly defers migration cost to whoever needs v2.

**Warning signs:** `agent/io.py` exceeds 50 lines; introduces classes; imports anything beyond stdlib `json` + `pathlib`.

### Pitfall 2: Drifting the runbook from reality

**What goes wrong:** Runbook says `python -m agent.tools transcribe` but the codebase later renames the subcommand. Runbook becomes lying-but-not-flagged.

**Why it happens:** Runbook is in Markdown; not exercised on CI; rots silently.

**How to avoid:** D-10 mandates running the 3 baselines before each phase merge. That run-event IS the runbook validation — if a command in the runbook fails, the runbook gets updated as part of that phase's PR.

**Warning signs:** A future phase's VERIFICATION.md says "couldn't run runbook step 2 because subcommand changed" — the runbook should have been updated *as part of* that phase, not deferred.

### Pitfall 3: Encoding audit becomes "all files have utf-8 in the codebase"

**What goes wrong:** Audit grep matches against `encoding="utf-8"` strings inside Markdown docs or comments, not actual `open()`/`read_text()`/`write_text()` calls. Result is a meaningless "100% compliant" claim.

**Why it happens:** Lazy grep that catches the string anywhere.

**How to avoid:** §"Encoding Audit Grep Commands" specifies *targeted* patterns: `\bopen\s*\(` for bare opens (must be inspected manually for binary-vs-text), and `read_text|write_text|json\.load` paired with absence-of-`encoding=` regex.

**Warning signs:** Audit output is one line "all good" without the actual grep transcripts; or evidence file omits the bare-`open()` exceptions and their justifications.

### Pitfall 4: Putting schema-versions.md somewhere ungreppable

**What goes wrong:** Phase 2+ developer searches for "v1 fields of meta.json" and finds nothing. Schema docs become a tree falling in an empty forest.

**Why it happens:** Doc location chosen for filing-order convenience, not for discoverability.

**How to avoid:** D-05 says "必须有一处可被 grep 到的 v1 字段集合记录." Put it at `docs/schema-versions.md`. From `docs/schema-versions.md` link to `tests/regression/regression-check.md` (and vice versa) so each doc is one click from the other.

**Warning signs:** `grep -r "schema_version" docs/ tests/` returns nothing meaningful 6 months later.

### Pitfall 5: BV132wizyEEB meta.json has Windows backslashes; treating that as a bug

**What goes wrong:** `output/BV132wizyEEB/meta.json` has `"video_path": "output\\BV132wizyEEB\\video.mp4"` (Windows-style backslashes); a future contributor "fixes" it to forward slashes during PRE-01 commit.

**Why it happens:** That's how `Path(...) → str(...)` serialized the path on the day BV132wizyEEB was downloaded on Windows. Other slugs (BV1C9QCBdE1U) have forward slashes. Heterogeneity is reality.

**How to avoid:** Commit the files **byte-for-byte as they are**. The whole point is that loader-tolerance handles existing file shapes — don't normalize them on commit. Add a note to schema-versions.md: "v1 `video_path` is platform-dependent; loaders treat it as opaque string."

**Warning signs:** PR diff shows changes to file content of any baseline JSON file — STOP, that's a re-normalization, not a copy.

### Pitfall 6: Encoding audit grep catches `_CONFIG.write_text(...)` and flags it as a binary write

**What goes wrong:** Auditor sees `agent/douyin_downloader.py:60` writing to `config.yaml` and questions "should this be binary?"

**Why it happens:** Vendor `config.yaml` is text (YAML), encoding="utf-8" is correct, but vendor mutation is a CONCERNS §2.2 issue confused with encoding.

**How to avoid:** §"Encoding Audit Grep Commands" classifies the three bare `open()` calls explicitly: video write (binary, correct), PIL Image (handles encoding internally, correct), Image.open (same). The vendor `config.yaml` write is NOT a bare open — it uses `_CONFIG.write_text(content, encoding="utf-8")` (verified at `agent/douyin_downloader.py:60`). It's compliant; vendor-mutation hygiene is out of Phase 1 scope.

**Warning signs:** Audit conflates "encoding correctness" with "should this code exist at all" — those are separate concerns.

## Code Examples

Verified patterns from existing sources.

### Existing: JSON load idiom (the pattern we're wrapping)

```python
# Source: agent/tools.py:77 (verified)
segs_data = json.loads(segs_file.read_text(encoding="utf-8"))

# Source: src/pipeline.py:34 (verified)
meta = json.loads((work_dir / "meta.json").read_text(encoding="utf-8"))
```

### Existing: JSON write idiom (the pattern we keep)

```python
# Source: agent/tools.py:81 (verified)
segs_file.write_text(
    json.dumps(segs_data, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
```

### Existing: --force cache bypass pattern (used in runbook)

```python
# Source: agent/tools.py:75-81 (verified)
if segs_file.exists() and not args.force:
    print(f"cached: {segs_file}")
    segs_data = json.loads(segs_file.read_text(encoding="utf-8"))
else:
    segs = transcribe(audio, model_size=args.whisper, language=None)
    segs_data = [asdict(s) for s in segs]
    segs_file.write_text(
        json.dumps(segs_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

This is why the runbook's "rerun stage" instruction must use `--force` — without it, the existing artifacts in `output/<slug>/` would be cache-hit and never regenerated.

### Existing: ensure_ascii=True terminal print (preserved per D-18)

```python
# Source: agent/tools.py:58-59 (verified)
# 避免打印含 emoji 的 title 炸 gbk 终端
print(json.dumps(meta, ensure_ascii=True, indent=2))
```

D-18 explicitly preserves this — PRE-05 documentation does NOT remove this fallback. The new section is recommendation, not enforcement.

## Loader-Tolerance Landing Point

### Survey: every load site for the three artifacts

Verified by Grep across `agent/` + `src/`. Site numbering is for cross-reference in the plan.

| # | File | Line | Code (current) | Artifact | Action |
|---|------|------|----------------|----------|--------|
| L1 | `agent/tools.py` | 77 | `segs_data = json.loads(segs_file.read_text(encoding="utf-8"))` | segs.json | Replace with `load_segs(segs_file)` |
| L2 | `agent/tools.py` | 94 | `segs = json.loads(Path(args.segs_json).read_text(encoding="utf-8"))` | segs.json | Replace with `load_segs(args.segs_json)` |
| L3 | `agent/prepare.py` | 77 | `meta = json.loads((work_dir / "meta.json").read_text(encoding="utf-8"))` | meta.json | Replace with `load_meta(work_dir / "meta.json")` |
| L4 | `agent/prepare.py` | 92 | `segs_data = json.loads(segs_cache.read_text(encoding="utf-8"))` | segs.json | Replace with `load_segs(segs_cache)` |
| L5 | `agent/prepare.py` | 114 | `paras_data = json.loads(para_cache.read_text(encoding="utf-8"))` | paragraphs.json | Replace with `load_paragraphs(para_cache)` |
| L6 | `src/pipeline.py` | 34 | `meta = json.loads((work_dir / "meta.json").read_text(encoding="utf-8"))` | meta.json | Replace with `load_meta(work_dir / "meta.json")` |
| L7 | `src/pipeline.py` | 46 | `data = json.loads(segs_cache.read_text(encoding="utf-8"))` | segs.json | Replace with `load_segs(segs_cache)` |
| L8 | `src/download.py` | 20 | `meta = json.loads(meta_cache.read_text(encoding="utf-8"))` | meta.json | Replace with `load_meta(meta_cache)` |
| L9 | `agent/douyin_downloader.py` | 150 | `meta = json.loads(meta_cache.read_text(encoding="utf-8"))` | meta.json | Replace with `load_meta(meta_cache)` |

**Total: 9 load sites across 5 files** (CONTEXT.md said "6 sites" — that count missed `src/download.py:20`, `agent/douyin_downloader.py:150`, and double-counted `agent/tools.py`. Honest count from grep: 9).

**Out of scope for this loader (do NOT patch):**
- `agent/frame_store.py:88` — loads `frame_store.json` (an orphaned v2 artifact, not in the three-artifact freeze list)
- `src/pipeline.py:68,83` — loads `frames.json` / `frame_descs.json` (legacy v1 cloud-pipeline artifacts, unused by ¥0 path)
- `src/summarize.py:647` — loads `outline.json` (legacy)
- `src/budget.py:81` — loads YAML, not JSON

### Three options compared

| Option | What it looks like | Pros | Cons | Verdict |
|--------|-------------------|------|------|---------|
| (a) New `agent/io.py` module everyone imports | One ~30-LOC module, `from agent.io import load_meta, load_segs, load_paragraphs` at each site | Single landing point for v2 migration (D-06); zero behavior change today; tiny surface area | One new file; one new import line per site (9 sites) | **RECOMMENDED** |
| (b) In-place patches at each load site | Add `if isinstance(obj, dict): v = obj.get("schema_version", 1)` inline at 9 sites | No new module; visible at point-of-use | 9 sites to update on v2 day instead of 1; pattern divergence guaranteed | Rejected — directly contradicts D-06 |
| (c) Hybrid (helper in `agent/asr_v2.py` for paragraphs since it's the producer) | Helper next to the producer; meta gets ad-hoc treatment | Ostensibly "modules-own-their-types" | `asr_v2.py` doesn't load meta.json; needs a second helper anyway; producer-vs-loader colocation isn't a meaningful pattern in this codebase | Rejected — introduces split for no benefit |

**Recommendation: Option (a).** Aligns best with K3 (loader-only, no file changes) — the single import line at each site is the visible signal that "loading this artifact goes through the version-aware path." When v2 lands, only `agent/io.py` changes.

### Where `agent/io.py` should be imported

Two acceptable styles; planner picks one and applies consistently:

1. **Top-of-file import** (preferred for `agent/prepare.py`, `agent/tools.py:cmd_aggregate` after the `sys.path.insert`): adds one line at the top, replaces the inline json.loads.
2. **Inside-handler lazy import** (matches existing `from src.asr import ...` lazy pattern at `agent/tools.py:65,92`): keeps consistency with the existing lazy-import style for handler-scope imports.

Both are fine; planner chooses based on which feels more like the surrounding code.

## JSON Shape Ground Truth

Verified by `Read` of actual files (BV1C9QCBdE1U primary, others cross-checked).

### `meta.json` v1 — top-level dict

**B站 path (`src/download.py:77-85` produces this):**

```json
{
  "video_path": "output/BV1C9QCBdE1U/video.mp4",
  "subtitle_path": null,
  "title": "【Godot教程】伤害数字生成器：暴击变色、随机漂浮、可复用，一看就会",
  "uploader": "xcount",
  "duration": 520,
  "description": "Godot 4.6 伤害数字系统教程",
  "url": "https://www.bilibili.com/video/BV1C9QCBdE1U"
}
```

Fields (all required, none nullable except `subtitle_path`):
- `video_path`: `str` — relative or absolute path; **may use either `/` or `\\` separators depending on OS at write time** [VERIFIED: BV132wizyEEB has `\\`, BV1C9QCBdE1U has `/`]
- `subtitle_path`: `str | null` — null if no VTT was downloaded
- `title`: `str` — UTF-8 video title (Chinese OK)
- `uploader`: `str` — UP主 / 作者 nickname
- `duration`: `int | float` — seconds; integer for some, float for others [VERIFIED: BV132wizyEEB=`74.048`, BV1C9QCBdE1U=`520`]
- `description`: `str` — first 500 chars of source description
- `url`: `str` — source URL

**抖音 path (`agent/douyin_downloader.py:201-211` produces this) adds two fields:**

```json
{
  "video_path": "output\\douyin_trae_ai\\video.mp4",
  "subtitle_path": null,
  "title": "搭建全网千万收藏的 AI 第二大脑，3分钟教会你！ #TRAE #TRAESOLO #AI新星计划",
  "uploader": "数字游牧人Samuel",
  "duration": 251.936,
  "description": "搭建全网千万收藏的 AI 第二大脑，3分钟教会你！ #TRAE #TRAESOLO #AI新星计划",
  "url": "https://v.douyin.com/D4_5dfVmsIo/",
  "aweme_id": "7626747241792802098",
  "source": "douyin"
}
```

Additional 抖音 fields:
- `aweme_id`: `str` — 抖音 video ID, numeric string
- `source`: `str` — value `"douyin"` (B站 path does NOT set this — `source` absence implies bilibili)

### `segs.json` v1 — top-level list

```json
[
  {"start": 0.0, "end": 2.56, "text": "You can download the R scene in the video for free, link in the description."},
  {"start": 2.56, "end": 6.0, "text": "But damage numbers that are simple and easy to add to any enemy in your game."}
]
```

Each element is `dict` with three required fields:
- `start`: `float` — seconds
- `end`: `float` — seconds
- `text`: `str` — recognized utterance (mixed-language possible — example file has English Whisper output despite Chinese host)

**Top-level list shape is the immovable v1 contract** (D-04). Any wrapping change ≡ a v2 schema bump.

### `paragraphs.json` v1 — top-level list

```json
[
  {
    "para_id": "p0000",
    "start": 0.0,
    "end": 29.6,
    "text": "...combined paragraph text...",
    "seg_indices": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
  }
]
```

Each element is `dict` with five required fields:
- `para_id`: `str` — format `p%04d` (zero-padded 4-digit, source: `agent/asr_v2.py:58`)
- `start`: `float` — seconds (paragraph start, == first member seg's start)
- `end`: `float` — seconds (paragraph end, == last member seg's end)
- `text`: `str` — concatenated text of all member segments, joined with `" "`
- `seg_indices`: `list[int]` — indices into the source segs.json list (0-indexed)

### Frame filename grammar (no JSON, but part of v1 conventions)

Pattern: `seg_<start_seconds_zero_padded_4>_<frame_index_zero_padded_6>.jpg`

- Source: `agent/tools.py:114-115`: `prefix = f"seg_{int(args.start):04d}_"`, ffmpeg pattern `<prefix>%06d.jpg`.
- Examples: `seg_0005_000002.jpg`, `seg_0030_000015.jpg`.
- Timestamp recovery: `ts = start + (frame_index - 0.5) / fps` per `agent/tools.py:123`.

Document this in schema-versions.md under "v1 frame conventions" even though frames don't ship in regression snapshots — future v2 schemes might affect filename grammar.

### `docs/schema-versions.md` skeleton

Recommend creating:

```markdown
# Artifact Schema Versions

**Project:** videoSummary
**Current schema_version:** 1 (locked retroactively in Phase 1, 2026-04-30)

This document records the field set of every `output/<slug>/` artifact at `schema_version: 1` so future v2 bumps have a baseline to migrate from.

## Loader Behavior (locked by Phase 1)

`agent/io.py` exports three loader functions: `load_meta(path)`, `load_segs(path)`, `load_paragraphs(path)`. All three honor:
- **Dict artifacts** (`meta.json`): `obj.get("schema_version", 1)` — absence == v1.
- **List artifacts** (`segs.json`, `paragraphs.json`): top-level list always treated as v1. Wrapping into `{"schema_version": ..., "items": [...]}` would break the 17 archived `output/<slug>/` directories and is forbidden by PROJECT.md K3.

When schema_version: 2 lands, the migration logic goes inside the loader; call sites do not change.

## v1 Field Set

### meta.json (dict)

Required for all sources:
| Field | Type | Notes |
|-------|------|-------|
| `video_path` | str | Path to video.mp4. **Platform-dependent separator** — may contain `/` or `\\`. Treat as opaque. |
| `subtitle_path` | str \| null | Path to .vtt file from yt-dlp; null if no subtitle. |
| `title` | str | UTF-8 video title. |
| `uploader` | str | Author / UP主 nickname. |
| `duration` | int \| float | Seconds. Integer or float, both valid. |
| `description` | str | First 500 chars of source description. |
| `url` | str | Source URL. |

抖音-only additions (B站 path omits both):
| Field | Type | Notes |
|-------|------|-------|
| `aweme_id` | str | Numeric 抖音 video ID. |
| `source` | str | Value `"douyin"`. Absence implies `"bilibili"`. |

### segs.json (list of dict)

Each element:
| Field | Type | Notes |
|-------|------|-------|
| `start` | float | Seconds. |
| `end` | float | Seconds. |
| `text` | str | Recognized text. Mixed-language possible. |

### paragraphs.json (list of dict)

Each element:
| Field | Type | Notes |
|-------|------|-------|
| `para_id` | str | Format `p%04d` per `agent/asr_v2.py:58`. |
| `start` | float | Paragraph start (== first member seg's `start`). |
| `end` | float | Paragraph end (== last member seg's `end`). |
| `text` | str | Concatenated member-seg text joined by `" "`. |
| `seg_indices` | list[int] | 0-indexed positions into the source segs.json list. |

## v1 Frame Conventions (filename, not JSON)

Generated by `agent/tools.py:114-115`:
- Pattern: `seg_<start_seconds:04d>_<frame_index:06d>.jpg` — e.g. `seg_0030_000015.jpg`.
- Timestamp recovery: `ts = start + (frame_index - 0.5) / fps` (see `agent/tools.py:123`).

Frames are not committed in `tests/regression/` per Phase 1 D-11.

## Reference

- Loader implementation: [`agent/io.py`](../agent/io.py)
- Regression baseline: [`tests/regression/regression-check.md`](../tests/regression/regression-check.md)
- Phase 1 context: `.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md`
```

## Baseline Snapshot Inventory

For PRE-01 commit. Verified by `ls -l` and `du -sh` on 2026-04-30.

| Slug | summary.md | meta.json | segs.json | paragraphs.json | Total per slug |
|------|-----------|-----------|-----------|-----------------|----------------|
| `BV132wizyEEB` | 4,941 B | 788 B | 4,178 B | 2,179 B | **12,086 B** |
| `BV1C9QCBdE1U` | 10,198 B | 341 B | 23,370 B | 16,174 B | **50,083 B** |
| `douyin_trae_ai` | 20,510 B | 487 B | 12,145 B | 6,532 B | **39,674 B** |
| **TOTAL** | 35,649 B | 1,616 B | 39,693 B | 24,885 B | **101,843 B (~99 KB)** |

CONTEXT.md estimated "~1MB total"; verified actual = ~99 KB total. **An order of magnitude under git-friendly limits.** No LFS needed; D-11 stands.

Line counts (for runbook orientation):
- segs.json: 216 / 851 / 606 lines
- paragraphs.json: 68 / 323 / 194 lines

These are small enough that Claude can read all six baseline JSONs into a single context window for the regression review.

## Three Baseline JSON Sizes — Confirmation

Per CONTEXT.md research question #6.

```
Per-slug totals (du -sh, includes audio.wav + video.mp4 + frames/ which we DO NOT commit):
6.9M    output/BV132wizyEEB
34M     output/BV1C9QCBdE1U
37M     output/douyin_trae_ai
```

The committed subset is just the 4 files per slug (table above). 99 KB total, easily under any threshold. **No git-LFS, no special storage handling — straight `git add` and `git commit`.**

## .gitignore Interaction

Verified contents (full file):
```
.env
.claude/
__pycache__/
*.pyc
*.pyo
.venv/
venv/
.DS_Store
output/
*cookies*.txt
vendor/
```

Findings:
- ✅ `output/` is gitignored — confirmed (line 9). The 17 archives stay out of git as intended.
- ✅ No `tests/` or `test/` glob — `tests/regression/` will be tracked normally.
- ⚠️ `*cookies*.txt` (line 10) is broad — won't affect this phase since we're not committing cookies, but worth noting that any future per-slug `cookies.txt` from yt-dlp lives under `output/` (already covered).
- ⚠️ `.claude/` is gitignored (line 2). If planner adds project skills under `.claude/skills/`, those would not be committed. Out of scope for Phase 1 (no skills referenced).

**No `.gitignore` changes needed for Phase 1.**

## Runtime State Inventory

This phase makes additive code/doc changes only — no rename, no refactor, no migration, no string replacement of identifiers used as keys in stored data. Most categories are N/A.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Phase 1 does not introduce or rename any persistent identifier. The three artifact JSONs being snapshotted are *read* and committed unchanged. No DB / Mem0 / ChromaDB in this project. | None |
| Live service config | None — no external services (Datadog / Tailscale / Cloudflare / n8n) integrate with this codebase. | None |
| OS-registered state | None — no Task Scheduler / systemd / launchd / pm2 entries. | None |
| Secrets/env vars | `DOUYIN_COOKIES_FILE`, `BILIBILI_SESSDATA`, `ASR_DEVICE`, `VE_KEY_CHEAP`, `VE_KEY_QUALITY`, `VE_BASE_URL`, `DOUYIN_COOKIES_BROWSER` — all unchanged by this phase. PRE-05 introduces a new *recommended* env var (`PYTHONUTF8=1`) but does not consume it from code (it's a Python interpreter flag honored by the interpreter itself). No `.env` change required. | None |
| Build artifacts / installed packages | None — no `pip install -e .` package, no compiled binary, no egg-info. The repo has no `pyproject.toml` or `setup.py` (verified). | None |

**Net assessment:** Phase 1 is a code-and-docs-only change with no runtime-state coupling. Safe to land.

## Regression Runbook Structure

Recommended skeleton for `tests/regression/regression-check.md`. Length target: ≤ 150 lines (operator-readable in one screen-pair).

```markdown
# Regression Baseline Runbook

**Purpose:** Verify that any milestone-2 phase change still reproduces the
v1 regression baseline for the three reference videos. This is human +
Claude operated, not CI. Run **before** merging any phase that touches
`agent/` or `src/`.

## Baselines (do NOT modify)

These are frozen for the milestone (Phase 1 D-13). If a future phase
intentionally drifts an output, that phase commits the new snapshot and
explains drift in its commit message.

| Slug | Type | Source URL |
|------|------|-----------|
| `BV132wizyEEB` | Code/AI workflow | https://www.bilibili.com/video/BV132wizyEEB |
| `BV1C9QCBdE1U` | Godot tutorial (code-dense) | https://www.bilibili.com/video/BV1C9QCBdE1U |
| `douyin_trae_ai` | AI/UI demo | https://v.douyin.com/D4_5dfVmsIo/ |

## Procedure

For each baseline slug, repeat:

### Step 1 — Stage the baseline JSONs into output/

The original `video.mp4` / `audio.wav` are NOT committed (size). Reuse
your local copy if present; otherwise re-download once via the standard
flow. Then overlay the frozen JSONs:

```bash
# Copy the four frozen artifacts INTO output/<slug>/, overwriting
# any cached versions that the WIP branch may have produced
cp -r tests/regression/<slug>/* output/<slug>/
```

If `output/<slug>/video.mp4` does not exist:

```bash
# One-time recovery — uses cached meta.json's URL via the source URL
python -m agent.tools download "<source-url-from-table-above>" --out output/<slug>
```

### Step 2 — Re-run the stages whose code changed

Use `--force` to bypass the file-existence cache. Only re-run stages
that the WIP phase actually touches; skip the rest.

```bash
# If transcribe / asr layer changed:
python -m agent.tools transcribe output/<slug>/video.mp4 --out output/<slug> --force

# If aggregate / paragraphs layer changed:
python -m agent.tools aggregate output/<slug>/segs.json --out output/<slug>/paragraphs.json
# (aggregate has no --force; delete paragraphs.json first if needed:
#  rm output/<slug>/paragraphs.json && rerun)

# If frame extraction layer changed: re-extract a sample range and
# generate a fresh summary.md following the standard /summarize-video
# workflow.
```

### Step 3 — Manual eyeball diff

Open both files in Claude Code and prompt with the template below:

```
Read tests/regression/<slug>/summary.md AND output/<slug>/summary.md.
Compare them along these axes ONLY:

1. STRUCTURE — same chapter count? same section ordering?
2. TIMESTAMPS — every [HH:MM:SS] in the new file exists in segs.json?
3. CODE BLOCKS — same code present? (intentional improvements OK; surprise drift NOT OK)
4. FRAME REFERENCES — image paths follow seg_<start>_<index>.jpg grammar?
5. RED-LINES — any "不注水" violation? (fabrication, padding, made-up timestamps)

Report:
- "PASS — no surprise drift; explainable diffs: [list each diff with one-line reason]"
- "FAIL — surprise drift: [list each unexplained delta]"
```

The runbook treats Claude's "PASS" judgment as authoritative. Record the
verdict in the merging phase's `VERIFICATION.md` (per D-10).

## Pass/Fail criterion

- **PASS:** All three baselines diff cleanly OR diffs are explainable
  improvements that the WIP phase intended (e.g., "phase X improved code
  抄录 accuracy by reading higher-fps frames — diff at line N reflects
  this").
- **FAIL:** Any of: structural drift not explained by the phase's stated
  goals; timestamp drift (not in segs.json); fabricated content; broken
  frame filename grammar.

## Encoding Audit Evidence

(See appendix below — re-run the grep to confirm 100% compliance is
preserved as of latest commit.)

[appendix follows]
```

### Manual-Diff Prompt Template

The exact prompt the operator pastes into Claude. Copy-paste-ready:

```
Compare two summary.md files for regression-baseline drift.

OLD (frozen baseline):  tests/regression/<slug>/summary.md
NEW (just regenerated):  output/<slug>/summary.md

Read both files in full. Then evaluate along five axes:

(1) STRUCTURE — Same number of top-level sections? Same ordering of
    subsections? Same overall narrative arc?

(2) TIMESTAMPS — For every [HH:MM:SS] in NEW: does that exact second exist
    in tests/regression/<slug>/segs.json? Read segs.json and verify.

(3) CODE — Compare code blocks line-by-line. Intentional improvements
    (more accurate transcription from frames) are PASS. Fabricated lines
    not justifiable from the video are FAIL.

(4) FRAME REFS — Every ![](frames/...) path follows
    seg_<start:04d>_<index:06d>.jpg grammar?

(5) RED-LINES — Any padding text? Any timestamp not in segs.json?
    Any "感谢观看" filler? Any made-up function/class names?

Output exactly one of:

  PASS — explainable diffs only:
    - <diff 1>: <why it's intentional>
    - <diff 2>: <why it's intentional>

  FAIL — surprise drift:
    - <delta 1>: <axis violated>
    - <delta 2>: <axis violated>
```

## Encoding Audit — Current State

Verified 2026-04-30 across `agent/` (8 files) + `src/` (9 files).

| Category | Count | Compliance |
|----------|-------|-----------|
| Text I/O via `Path.read_text(encoding="utf-8")` | 13 sites | 100% have explicit encoding |
| Text I/O via `Path.write_text(..., encoding="utf-8")` | 18 sites | 100% have explicit encoding |
| Bare `open()` calls | 3 sites | All 3 are correct (binary I/O — see below) |

**The three bare `open()` calls (verified at exact line numbers):**

| Site | Code | Type | Justification |
|------|------|------|---------------|
| `agent/douyin_downloader.py:194` | `with open(video_path, "wb") as f:` | Binary write (mp4) | Correct — binary mode must NOT have `encoding=` |
| `agent/embed.py:79` | `img = PILImage.open(p).convert("RGB")` | PIL Image read | Not a text-I/O `open()`; `PIL.Image.open` handles encoding internally |
| `agent/frames_v2.py:74` | `h = imagehash.phash(Image.open(f.path))` | PIL Image read (via imagehash) | Same as above; PIL handles internally |
| `src/frames.py:53` | `h = imagehash.phash(Image.open(f.path))` | PIL Image read (via imagehash) | Same; **CONTEXT.md missed this fourth case** — flag for the audit doc |

**Note for planner:** CONTEXT.md D-14 lists three bare opens, but grep finds a fourth in `src/frames.py:53` with the same PIL pattern. The audit-evidence file should list all four for completeness — it doesn't change the conclusion (still 100% compliant; PIL handles encoding internally), but accuracy matters for an "audit pass" claim.

## Encoding Audit Grep Commands

The exact commands to reproduce the audit. Run from repo root.

### Command set 1 — find every bare `open()` call

```bash
# Pattern: literal `open(` with optional whitespace, in agent/ + src/
rg -n '\bopen\s*\(' agent/ src/ --type py
```

Expected output (verified 2026-04-30):
```
agent/douyin_downloader.py:194:        with open(video_path, "wb") as f:
agent/embed.py:79:                img = PILImage.open(p).convert("RGB")
agent/frames_v2.py:74:            h = imagehash.phash(Image.open(f.path))
src/frames.py:53:            h = imagehash.phash(Image.open(f.path))
```

Each must be classified manually as:
- (a) binary I/O → must NOT have `encoding=` (correct as-is)
- (b) PIL/imagehash → handles encoding internally (correct as-is)
- (c) text I/O → MUST have `encoding="utf-8"` (would be a bug; none found)

### Command set 2 — confirm every text-I/O site has encoding

```bash
# read_text / write_text without explicit encoding — should produce ZERO matches
rg -n '(read_text|write_text)\s*\((?![^)]*encoding\s*=)' agent/ src/ --type py
```

Expected output: empty. If any match appears, that site needs an `encoding="utf-8"` patch.

### Command set 3 — confirm json.load is not used (idiom check)

```bash
# json.load(open(...)) is forbidden by CONVENTIONS.md
rg -n 'json\.load\s*\(' agent/ src/ --type py
```

Expected: only matches inside docstrings/comments/prompt strings (e.g., `src/summarize.py:34` mentions `json.loads` in a Chinese docstring, not as a call). Verify each hit is non-functional.

### Audit Pass Evidence Format

Append to `tests/regression/regression-check.md` as final section. Structure:

```markdown
## Encoding Audit (PRE-04)

**Audited:** YYYY-MM-DD
**Scope:** agent/ + src/ (.py files only, vendor/ excluded)
**Result:** 100% compliant — every text I/O site uses explicit `encoding="utf-8"`.

### Commands run

```bash
rg -n '\bopen\s*\(' agent/ src/ --type py
rg -n '(read_text|write_text)\s*\((?![^)]*encoding\s*=)' agent/ src/ --type py
rg -n 'json\.load\s*\(' agent/ src/ --type py
```

### Findings

**Bare `open()` calls (4):**
| Site | Mode | Verdict |
|------|------|---------|
| `agent/douyin_downloader.py:194` | `"wb"` (binary write) | OK — binary, no encoding needed |
| `agent/embed.py:79` | `PIL.Image.open` | OK — PIL handles encoding |
| `agent/frames_v2.py:74` | `imagehash.phash(Image.open(...))` | OK — PIL handles encoding |
| `src/frames.py:53` | `imagehash.phash(Image.open(...))` | OK — PIL handles encoding |

**Text I/O sites without encoding:** 0.

**`json.load(open(...))` calls:** 0 (the codebase exclusively uses
`json.loads(path.read_text(encoding="utf-8"))` per CONVENTIONS.md).

### Re-running

This audit is read-only. Anyone can re-run the three commands above
and replicate the result. Future phase merges should re-run this
audit if they touch `agent/` or `src/` and append a fresh date stamp
above.
```

## CLAUDE.md Insertion — Exact Wording

For PRE-05. Recommended insertion point: **between line 39 (end of "抖音支持" section) and line 41 (start of "环境变量" section)**.

Why between these two: the "抖音支持" section is a one-time setup recipe; "Windows zh-CN 终端设置" is also one-time setup; pairing them maintains the document's natural setup-then-runtime flow. Above 「环境变量」 because env vars are runtime knobs.

### Exact Markdown to insert (≤ 30 lines):

```markdown
## Windows zh-CN 终端设置（推荐）

中文 Windows 默认 GBK 终端会在打印含 emoji / 非 ASCII 的视频标题时炸出
`UnicodeEncodeError`。代码已在 `agent/tools.py:59` 留了 `ensure_ascii=True`
兜底，老路径不设置也能跑；但**推荐**把终端 + 解释器 都切成 UTF-8，让本仓库
所有路径行为一致：

1. **每个 terminal session 跑一次**（zh-CN cmd / PowerShell）：
   ```bash
   chcp 65001
   ```

2. **一次性设置 `PYTHONUTF8=1` 环境变量**（Windows 10+ 生效）：
   - PowerShell 永久：`[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")`
   - 或在「系统属性 → 环境变量」面板加 `PYTHONUTF8=1`
   - 设好后重启 terminal 验证：`python -c "import sys; print(sys.flags.utf8_mode)"` 应输出 `1`

设了之后 `print(meta)`、文件 I/O、子进程 stderr 全程 UTF-8；老的 `ensure_ascii`
兜底保留不动，没设 codepage 的环境也能正常工作。

> **历史背景：** 项目里所有 `read_text` / `write_text` 都已显式 `encoding="utf-8"`
> （Phase 1 PRE-04 审计通过），这一节是给「希望子进程 stderr 也直接读到中文」
> 的开发者准备的、可选的一致化设置。
```

### Verification of insertion point

Read CLAUDE.md as-is (verified 2026-04-30):

```
Line 39: 注意：抖音 cookies 每几天失效，失败时重新导出。yt-dlp 的 douyin extractor 长期 broken（不支持 a_bogus），所以必须走 vendor crawler。
Line 40: (blank)
Line 41: ## 环境变量（.env）
```

Insert the new `## Windows zh-CN 终端设置（推荐）` section as a new heading **between line 40 and line 41** (i.e., between the blank line ending 抖音支持 and the 环境变量 heading). One blank line above the new heading, one blank line below before 环境变量.

### Wording rationale (per D-18)

- **「推荐而非必需」** — explicit phrasing in the section title `（推荐）` and in the body "推荐把终端 + 解释器 都切成 UTF-8" / "老路径不设置也能跑".
- **Preserves `ensure_ascii=True` fallback** — the body explicitly references `agent/tools.py:59` and states "兜底保留不动".
- **Foreshadows Phase 3** — the closing note about "希望子进程 stderr 也直接读到中文" anticipates the YouTube + ffmpeg-on-CJK paths in Phase 3 (SRC-09/10/11) where this matters more.
- **Verifies the setting** — gives the operator a one-line probe (`python -c "import sys; print(sys.flags.utf8_mode)"`) so they can confirm the setting took effect, without needing to read Python docs.

## Files Executors Must Read (read_first lists)

For each PRE requirement, the exhaustive set of files the executor must `Read` before touching code/docs. The planner injects these into each task's `<read_first>` block. Better to over-list than miss a source-of-truth file.

### PRE-01 (commit baseline summaries)

```
.planning/PROJECT.md                                          # K3 backward-compat constraint
.planning/REQUIREMENTS.md                                     # PRE-01 measurable conditions
.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md   # D-01..D-13
.planning/phases/01-preflight-regression-baseline/01-RESEARCH.md  # this file (skim §"Baseline Snapshot Inventory")
.gitignore                                                    # confirm tests/ not silently excluded
output/BV132wizyEEB/summary.md                                # source — copy as-is
output/BV132wizyEEB/meta.json                                 # source — copy as-is (note: \\ separators in this one)
output/BV132wizyEEB/segs.json                                 # source — copy as-is
output/BV132wizyEEB/paragraphs.json                           # source — copy as-is
output/BV1C9QCBdE1U/summary.md                                # source — copy as-is
output/BV1C9QCBdE1U/meta.json                                 # source — copy as-is
output/BV1C9QCBdE1U/segs.json                                 # source — copy as-is
output/BV1C9QCBdE1U/paragraphs.json                           # source — copy as-is
output/douyin_trae_ai/summary.md                              # source — copy as-is
output/douyin_trae_ai/meta.json                               # source — copy as-is (note: source: "douyin")
output/douyin_trae_ai/segs.json                               # source — copy as-is
output/douyin_trae_ai/paragraphs.json                         # source — copy as-is
```

### PRE-02 (regression-check.md runbook)

```
.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md  # D-07..D-10
.planning/phases/01-preflight-regression-baseline/01-RESEARCH.md # §"Regression Runbook Structure", §"Manual-Diff Prompt Template"
CLAUDE.md                                                     # /summarize-video Phase 1-3 commands referenced in runbook
agent/tools.py                                                # --force flag pattern (lines 75-81)
.planning/codebase/CONVENTIONS.md                             # JSON write idiom — runbook references it implicitly
```

### PRE-03 (loader-tolerance + schema-versions doc)

```
.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md  # D-03..D-06
.planning/phases/01-preflight-regression-baseline/01-RESEARCH.md # §"JSON Shape Ground Truth", §"Loader-Tolerance Landing Point"
.planning/PROJECT.md                                          # K3 hard rule: do not modify existing output/<slug>/
.planning/codebase/CONVENTIONS.md                             # JSON read idiom (the pattern we're wrapping)
agent/tools.py                                                # L1, L2 (lines 77, 94) — patch sites
agent/prepare.py                                              # L3, L4, L5 (lines 77, 92, 114) — patch sites
src/pipeline.py                                               # L6, L7 (lines 34, 46) — patch sites
src/download.py                                               # L8 (line 20) — patch site
agent/douyin_downloader.py                                    # L9 (line 150) — patch site
output/BV1C9QCBdE1U/meta.json                                 # ground truth — verify field set matches docs
output/BV132wizyEEB/meta.json                                 # variant — note \\ separator
output/douyin_trae_ai/meta.json                               # variant — note source/aweme_id additions
output/BV1C9QCBdE1U/segs.json                                 # ground truth list shape
output/BV1C9QCBdE1U/paragraphs.json                           # ground truth list shape
agent/asr_v2.py                                               # paragraphs producer — para_id format reference
src/asr.py                                                    # segs producer (Segment dataclass)
src/download.py                                               # meta.json B站 producer (lines 77-87)
agent/douyin_downloader.py                                    # meta.json 抖音 producer (lines 201-211)
```

### PRE-04 (encoding audit + evidence file)

```
.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md  # D-14..D-16
.planning/phases/01-preflight-regression-baseline/01-RESEARCH.md # §"Encoding Audit — Current State", §"Encoding Audit Grep Commands"
.planning/codebase/CONVENTIONS.md                             # I/O conventions section
agent/douyin_downloader.py                                    # bare open() at line 194 (binary write — correct)
agent/embed.py                                                # PIL Image.open at line 79 (correct)
agent/frames_v2.py                                            # PIL Image.open at line 74 (correct)
src/frames.py                                                 # PIL Image.open at line 53 (correct — research caught this; CONTEXT missed it)
```

(Auditor must also re-run the three grep commands and paste output into the evidence section. Reading the four files above gives them context for classifying each bare `open()`.)

### PRE-05 (CLAUDE.md Windows zh-CN section)

```
.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md  # D-17, D-18
.planning/phases/01-preflight-regression-baseline/01-RESEARCH.md # §"CLAUDE.md Insertion — Exact Wording"
CLAUDE.md                                                     # entire file — confirm insertion point line numbers
agent/tools.py                                                # confirm line 59 ensure_ascii=True still preserved
.planning/codebase/CONCERNS.md                                # §1.4, §8.2 — context for why this section matters
.planning/research/PITFALLS.md                                # U3 (Windows/encoding/proxy/locale)
```

## State of the Art

This phase introduces no library decisions — nothing to track here.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| (n/a — no library research applies) | — | — | — |

**Deprecated/outdated:** None.

## Assumptions Log

Every claim in this RESEARCH.md is either `[VERIFIED]` (confirmed by tool: file Read, grep, du/ls) or follows directly from CONTEXT.md decisions. The few items below are flagged as `[ASSUMED]` because they involve operator preference rather than a hard constraint.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A single `agent/io.py` module is the best landing point for loader helpers (vs. `src/io.py` or in-place patches) | §"Loader-Tolerance Landing Point" | Low — `agent/io.py` is consistent with the layering convention (`agent/` is the active ¥0 toolset; `src/` is legacy). If user prefers `src/io.py`, migration is one move. |
| A2 | `docs/schema-versions.md` is the right location vs. embedding in CLAUDE.md | §"docs/schema-versions.md skeleton" | Low — D-05 left this to discretion. If user prefers CLAUDE.md, the content moves wholesale; URL updates needed in regression-check.md. |
| A3 | The CLAUDE.md insertion point is between line 39 and line 41 (between 抖音支持 and 环境变量 sections) | §"CLAUDE.md Insertion — Exact Wording" | Low — D-17 said "「环境变量」节之上或之后", and "之上" was chosen for narrative flow (setup-then-runtime). User may prefer "之后" — trivial to swap. |
| A4 | Encoding audit + runbook should be one file (`tests/regression/regression-check.md` with appendix) vs. two files | §"Architecture Patterns" | Low — D-15 left this to discretion; one-file recommendation is for self-contained-ness. Splitting is one PR away. |
| A5 | Phase 1 introduces NO `schema_version` field to *new* artifacts written this phase (only adds tolerant-reading) | §"Anti-Patterns to Avoid" | Medium — if Phase 2 (RES) reads this and decides "PRE-03 should have written `schema_version: 1` on writes too," that's a Phase 2 design choice, not a Phase 1 regression. Documented here to make the boundary explicit. |

**A5 is the most consequential.** The reading is: PRE-03 is **loader-only tolerance** (D-04 explicitly), so writing the field on new artifacts would (a) change the on-disk shape compared to existing 17 archives — making them visually different from new ones, and (b) be redundant since loaders default to 1 anyway. Phase 2 (RES-08 schema-migration runbook) is where the writing convention gets decided. If user wants Phase 1 to also start writing `schema_version: 1` to new files, that's a CONTEXT.md amendment.

## Open Questions

1. **Should `agent/io.py` validate the dict-vs-list shape, or just trust callers?**
   - What we know: `load_segs` / `load_paragraphs` raise `ValueError` if the loaded JSON isn't a list (per skeleton in §"Pattern 1").
   - What's unclear: Is that consistent with existing fail-fast philosophy, or is it over-eager for a "loader"?
   - Recommendation: Keep the `isinstance` check — fail-fast is project convention (CONVENTIONS.md §"Error Handling"). The check costs zero ops and makes "v2 wrapped paragraphs.json got fed to v1 loader" a clear error instead of a silent type error 5 frames deep.

2. **For the regression runbook step 2 (re-run stages), should the runbook list exact commands per stage, or just say "re-run the relevant stage"?**
   - What we know: There are only 3-4 stages (`download`, `transcribe`, `aggregate`, `extract_frames`), and `--force` semantics differ (only `transcribe` has it).
   - What's unclear: Whether listing all 3 commands verbatim is helpful or noisy.
   - Recommendation: List all 3 verbatim with the `--force` / "delete-and-rerun" caveat per stage. Operators come to runbooks to copy-paste, not to think.

3. **Does PRE-04 audit need to include `vendor/` (excluded by `.gitignore`)?**
   - What we know: D-14 says "agent/ + src/ 全部 .py 文件"; vendor is gitignored and not first-party.
   - What's unclear: If vendor is updated and breaks encoding hygiene, does it become our problem?
   - Recommendation: Vendor stays out of audit scope — D-14 is explicit. If vendor encoding ever becomes a problem, it's a CONCERNS §3.1 item (supply chain), not PRE-04. Document this in the audit-pass file: "Scope excludes vendor/ per D-14; vendor encoding hygiene tracked in CONCERNS.md §3.1."

4. **Should the loader emit a warning log when it sees an artifact with `schema_version` > 1 but no migration?**
   - What we know: Phase 1 has no v2; the question only arises when v2 lands.
   - What's unclear: Should v1 loader (`agent/io.py`) future-proof itself with a "I see schema_version: 2 but I only know v1; please update" warning?
   - Recommendation: No — keep loader minimal in Phase 1. The Phase 2/3+ that introduces v2 will write the appropriate version-mismatch handling. Adding speculative warnings now is anti-pattern (Pitfall §1).

## Environment Availability

This phase is code-and-docs only — no external tool dependencies. The only required tools are git (for commits), Python 3.11+ (already required by the project), and a working CLAUDE.md / Claude Code session for the manual-diff step. No new install gates.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `git` | PRE-01 commit | ✓ | any | — |
| `python` | PRE-03 patches (none invoked at runtime by phase, but loaders must import) | ✓ | 3.11+ (project standard) | — |
| `rg` (ripgrep) for audit | PRE-04 grep commands | available via Grep tool — confirmed in this research session | latest | `grep -rn` (slower, less precise) |
| Claude Code | PRE-02 manual-diff step | ✓ (this session) | — | n/a — D-07 locks "Claude is the verifier" |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None — `rg` works via the Grep tool; even on shells without ripgrep installed, the commands have plain-`grep` fallbacks.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md` — backward-compat hard constraint (K3); ¥0 + Claude-as-decider invariants
- `.planning/REQUIREMENTS.md` §"PRE — Preflight & Regression Baseline" — PRE-01..PRE-05 measurable conditions
- `.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md` — D-01..D-18 locked decisions
- `.planning/codebase/CONVENTIONS.md` — JSON read/write idioms, encoding="utf-8" convention, `--force` flag pattern
- `.planning/codebase/STRUCTURE.md` — `agent/` vs `src/` layering; load-site location reference
- `.planning/codebase/ARCHITECTURE.md` §"Artifact Layer" / §"Data Flow" — output/<slug>/ self-describing convention
- `.planning/codebase/CONCERNS.md` §1.4 (GBK terminal), §5.4 (cache), §8.2 (Windows assumptions) — PRE-04/05 context
- `.planning/research/PITFALLS.md` §U1, §U2, §U3, §P7.4 — phase rationale
- `.planning/research/SUMMARY.md` Phase 1 section — confirms scope

### Secondary (file Reads — verifying current state)
- `agent/tools.py` (255 lines, full file) — verified L1, L2, line 59 ensure_ascii, line 75-81 --force pattern
- `agent/asr_v2.py` (155 lines, full file) — verified Paragraph dataclass + para_id format
- `src/asr.py` (122 lines, full file) — verified Segment dataclass
- `agent/prepare.py` (218 lines, full file) — verified L3, L4, L5 load sites
- `src/pipeline.py` (121 lines, full file) — verified L6, L7 load sites
- `src/download.py` (88 lines, full file) — verified L8 + meta.json B站 producer
- `agent/douyin_downloader.py` (lines 1-220) — verified L9 + meta.json 抖音 producer + line 194 binary open
- `CLAUDE.md` (full file) — verified insertion-point line numbers (39/40/41)
- `.gitignore` (full file) — verified output/ ignored, no tests/ glob
- `output/BV132wizyEEB/{summary,meta,segs,paragraphs}.json` (sizes via ls -l) — 12,086 bytes total
- `output/BV1C9QCBdE1U/{summary,meta,segs,paragraphs}.json` — 50,083 bytes total
- `output/douyin_trae_ai/{summary,meta,segs,paragraphs}.json` — 39,674 bytes total
- `output/BV1C9QCBdE1U/{meta,segs,paragraphs}.json` — Read for shape ground truth
- `output/BV132wizyEEB/meta.json` — verified `\\` separator variant
- `output/douyin_trae_ai/meta.json` — verified `aweme_id` + `source: "douyin"`

### Grep audits (HIGH confidence — reproducible)
- `rg '\bopen\s*\(' agent/ src/ --type py` → 4 hits, all classified
- `rg 'json\.loads|read_text.*encoding|json\.load\(' agent/ src/` → 13 hits, all encoding-correct
- `rg 'write_text|json\.dumps' agent/ src/` → 18+ hits, all encoding-correct
- `wc -l output/<slug>/{segs,paragraphs}.json` → line counts as documented
- `du -sh output/<slug>` → 6.9M / 34M / 37M (full dirs); committed subset 99 KB

### Tertiary (none)
No web research needed — this phase is fully internal-codebase scoped.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; existing idioms verified by grep
- Architecture: HIGH — landing-point recommendation has explicit pros/cons; alternative options enumerated and rejected with reasons
- JSON shapes: HIGH — read directly from real files
- Encoding audit: HIGH — grep-reproducible
- Pitfalls: MEDIUM — codebase-specific (Pitfall #5 about backslash separators) is unique; standard "don't auto-update snapshot" / "don't over-engineer" pitfalls are HIGH

**Research date:** 2026-04-30
**Valid until:** Until `agent/`, `src/`, or `output/<slug>/` shapes change. Practically: valid through Phase 1 execution; should be re-validated at start of Phase 2 (RES-01..08 will write `<artifact>.params.json` sidecars and may bump `schema_version`).
