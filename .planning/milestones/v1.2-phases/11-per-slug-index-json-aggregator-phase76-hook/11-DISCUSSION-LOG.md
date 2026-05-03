# Phase 11: per-slug index.json + 顶层聚合 + Phase 7.6 hook - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-05-04
**Mode:** `--auto` (smart_discuss equivalent — autonomous workflow, infrastructure phase, all SC technical, Phase 10 contracts stable)
**Areas auto-resolved:** 8 categories of decisions (D-01..D-10) — schema lock / Phase 7.6 hook / aggregator / rebuild CLI / write CLI / keyword reuse / D-29 verify / module layout / FileLock / K5 boundary

---

## Schema Lock (D-01)

| Option | Description | Selected |
|--------|-------------|----------|
| 8 字段 fixed schema (per CONTEXT) | slug/title/duration_s/mode/topics/keywords/tldr_oneliner/chapters | ✓ |
| 9+ 字段 (添加 created_at / updated_at / version) | 加 metadata 字段 | |
| Free-form schema | 不严格校验 | |

**Auto-selected rationale:** v1.2-CANDIDATES.md KB-01 必做项明确锁 8 字段；version 字段 deferred 到 v1.3 (CONTEXT Deferred Ideas)；free-form 破"中颗粒" intent (D-02 颗粒度决策)

---

## Phase 7.6 Hook Insertion Point (D-02)

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 7.5 之后、Phase 8 之前 | 在 verifier 通过后 cleanup 前 | ✓ |
| Phase 7 之后、Phase 7.5 之前 | 在 verifier 之前 | |
| Phase 8 cleanup 之后 | 最后 | |

**Auto-selected rationale:** index.json 写入需要 summary.md 已经稳定（Phase 7.5 verifier 通过后）；cleanup 之前是因为 index.json 用到 frames 引用信息（cleanup 删未引用 frames 不影响 index.json，但顺序自然）

---

## Aggregator Schema (D-03)

| Option | Description | Selected |
|--------|-------------|----------|
| 扁平 dict {slug: per-slug-index} | 无 backlink, machine-readable | ✓ |
| Array of objects | [{...}, {...}] | |
| Backlink-augmented dict | 加 related_slugs 字段 | |

**Auto-selected rationale:** D-07 锁 backlinks dropped；扁平 dict 让 Claude 一次 Read 直接 access by slug；array 不便 lookup；mirror v1.1 K5 emitter JSON output 风格

---

## Rebuild Trigger (D-04)

| Option | Description | Selected |
|--------|-------------|----------|
| 自动同步 + 手动兜底 CLI | 写 per-slug 立刻 rebuild + manual rebuild 兜底 | ✓ |
| 仅手动 (no auto-rebuild) | 用户必须显式触发 | |
| 仅自动 (no manual CLI) | 没有 backfill / debug 兜底 | |

**Auto-selected rationale:** D-08 v1.2-CANDIDATES.md 锁"自动同步 + 手动 rebuild"；自动符合 D-03 自动化优先；手动是 Phase 12 backfill 必需的兜底

---

## CLI Subcommand Layout (D-05/D-08)

| Option | Description | Selected |
|--------|-------------|----------|
| nested subparser `index write/rebuild` | mirror Phase 10 `topics` pattern | ✓ |
| flat commands `index_write` / `index_rebuild` | 顶层独立 cmd | |
| Single `index` cmd with `--mode` flag | 复杂 flag-based dispatch | |

**Auto-selected rationale:** Phase 10 ship 的 `topics bootstrap/audit/resolve` nested 模式已 validated；保持 CLI 一致性；Python argparse nested subparser 是惯用法

---

## Keywords Source (D-06)

| Option | Description | Selected |
|--------|-------------|----------|
| 优先复用 _glossary.md H2 anchors (D-03) | byte-equal canonical form | ✓ |
| 从 summary.md 自由抽取 | 不约束 | |
| 强制从 _topics.md 选 | 与 topics 共用源 | |

**Auto-selected rationale:** D-03 v1.2-CANDIDATES.md 锁"keywords 来源 = Claude 自动抽 + glossary 复用"；防止"LoRA / Lora / low-rank adaptation"分裂；强制从 _topics.md 选会破 keywords / topics 维度区分

---

## Module Layout (D-08)

| Option | Description | Selected |
|--------|-------------|----------|
| `agent/index.py` 单模块 | 5 public functions | ✓ |
| `agent/index/__init__.py` + 子模块 | 拆 reader / writer / aggregator | |
| Inline `agent/tools.py` | 不抽模块 | |

**Auto-selected rationale:** mirror Phase 10 `agent/topics.py` 单模块；5 functions 是 SRP-friendly 边界；拆子模块 over-engineer for ~600 LOC 估算

---

## FileLock Strategy (D-09)

| Option | Description | Selected |
|--------|-------------|----------|
| 独立锁 `output/.index.lock` | 与 .topics.lock / .glossary.lock 分离 | ✓ |
| 共享锁 `output/.governance.lock` | 跨多 governance file | |
| 无锁 | 接受 race | |

**Auto-selected rationale:** Phase 10 D-08 + v1.1 Phase 08 `.glossary.lock` 已建立"per-governance-file lock"惯例；共享锁会让 _topics.md 写卡 _index.json 写；race 在多终端场景已 OOS

---

## K5 Boundary Tests (D-10)

| Option | Description | Selected |
|--------|-------------|----------|
| 3 new tests (module + 2 cmd) | 与 Phase 10 4 测试形态一致 | ✓ |
| 1 综合 test | 单条 regex over module | |
| 0 测试 (信任 reviewer) | 无静态断言 | |

**Auto-selected rationale:** v1.1 + Phase 10 17 个 K5 tests 是稳定模式；3 new test 分别覆盖 module / cmd_write / cmd_rebuild；K5 是 D-29 byte-equal 的核心契约（违反 → byte-equal regression）

---

## Claude's Discretion

- `tldr_oneliner` 具体语气 / 句式
- `chapters[]` excerpt 多句话取 1-2 行的策略
- `_glossary.md` H2 anchor 解析 regex 细节
- `index rebuild` stale-detection stdout 排版
- 顶层 `.index.json` 的 dict 顺序

## Deferred Ideas

- Per-slug index.json schema versioning（v1.3+）
- `index search/list` CLI（Phase 12 KB-MISC-01）
- 顶层 .index.json 增量 rebuild（v1.3+ if scale > 100）
- `.v12_features.json` opt-out marker（不需要 — v1.2 是新 sidecar 不破 D-29）
- 顶层 .index.json split 策略（v1.3+ if > 50KB）
- per-slug rename 工具（v1.3+）
