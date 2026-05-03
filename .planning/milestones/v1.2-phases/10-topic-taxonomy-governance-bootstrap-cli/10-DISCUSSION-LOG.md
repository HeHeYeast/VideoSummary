# Phase 10: Topic taxonomy governance + bootstrap CLI - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 10-topic-taxonomy-governance-bootstrap-cli
**Mode:** `--auto` (smart_discuss equivalent — autonomous workflow, infrastructure phase)
**Areas auto-resolved:** File Structure / Bootstrap CLI / Audit CLI / Resolve CLI / Governance Workflow / K5 Boundary / Module Layout / FileLock

---

## File Structure

| Option | Description | Selected |
|--------|-------------|----------|
| 2-section markdown (Approved + Pending) | 顶部树状 + 底部 H3 entries | ✓ |
| Single-section JSON | 全部 JSON 一文件 | |
| Multi-file (approved.md + pending.md) | 两个独立文件 | |

**Auto-selected rationale:** 2-section markdown mirror v1.1 ship 的 `output/_glossary.md` 形态；用户 review-friendly；K5 governance 设计意图（用户偶尔打开看）需要可读性优先于机器优先

---

## Bootstrap CLI

| Option | Description | Selected |
|--------|-------------|----------|
| Claude-driven (`--from-stdin` JSON) | Claude 归纳 taxonomy 后 pipe 给 CLI 写入 | ✓ |
| Script-driven (CLI 自己扫 archives 算 taxonomy) | CLI 用 keyword frequency 启发式产出 | |
| Hybrid (Claude 提议 + 脚本扩充) | 混合策略 | |

**Auto-selected rationale:** D-04 K5 boundary —— "工具不预设抽帧策略 / 大纲结构 / 文档模板"；taxonomy 归纳是 understanding-level decision，不是机械算法；脚本-driven 会破 K5；CLI 只做"写入" mechanical 部分

---

## Audit CLI

| Option | Description | Selected |
|--------|-------------|----------|
| Read-only with `--json` flag | 输出 stdout markdown 或 JSON，不写文件 | ✓ |
| Read-write (auto-cleanup orphans) | audit 时直接删孤儿 | |
| Read-only no `--json` (markdown only) | 只输出 markdown 给人看 | |

**Auto-selected rationale:** K5 boundary 必须严格 read-only（D-06 source-grep test 断言）；`--json` flag 给 Claude consumption（mirror v1.1 K5 emitter 风格）；auto-cleanup 破 D-04 governance 设计（用户决策必经）

---

## Resolve CLI

| Option | Description | Selected |
|--------|-------------|----------|
| Atomic 跨多文件改写 | 持锁 + snapshot + tempfile + os.replace | ✓ |
| Sequential (无 atomic 保证) | 单文件单文件改 | |
| Two-step (先 _topics.md, 再 index.json by separate cmd) | 拆 promote 和 update 为两个命令 | |

**Auto-selected rationale:** index.json 引用一致性是 invariant；中途失败导致 _topics.md promoted 但 index.json 还在 `pending: <name>` 形态会让 audit 报错；atomic 是单一正确解；FileLock + snapshot + atomic write 是 v1.0 Phase 02 ship 的成熟模式

---

## Governance Workflow (Phase 11 contract)

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 10 暴露 `agent.topics.append_pending` Python API | Phase 11 generator import + 调用 | ✓ |
| Phase 10 暴露 CLI subcommand `topics request <name> ...` | Phase 11 generator 走 subprocess | |
| Phase 10 不暴露写 Pending 接口（Claude 手动改文件） | 完全人工 | |

**Auto-selected rationale:** Python API 比 subprocess 高效（Phase 11 generator 在 Phase 7.6 hook 中跑，每次 /summarize-video 都触发）；K5 governance 是 Claude is decider，但写 Pending 段是机械操作不是判断；自然分层：Claude 判断 → 调用 helper → CLI 仅做用户 governance 工具

---

## K5 Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| 4 new tests in `test_k5_emitters.py` (intent-correct write-pattern regex) | mirror v1.1 Phase 07-03 deviation #2 lesson | ✓ |
| Single combined test (regex over `agent/topics.py`) | 一条总 test | |
| No K5 test (rely on review) | 信任 reviewer | |

**Auto-selected rationale:** v1.1 Phase 07-03 deviation #2 教训 — intent-correct regex 必须；4 tests 分别覆盖 bootstrap/audit/resolve/module-level；"信任 reviewer" 在 v1.1 已 ship 13 K5 tests 后是 regression（D-29 byte-equal foundation 的核心契约）

---

## Module Layout

| Option | Description | Selected |
|--------|-------------|----------|
| `agent/topics.py` 单模块 | 4 public functions | ✓ |
| `agent/topics/__init__.py` + 子模块 | 拆 read.py / write.py / resolve.py | |
| Inline 直接写 `agent/tools.py` | 不抽模块 | |

**Auto-selected rationale:** mirror v1.1 ship 的 `agent/_glossary.py` 单模块形态；4 functions 是 SRP-friendly 边界；拆子模块 over-engineer for 200 LOC；inline `tools.py` 破 module SRP

---

## FileLock

| Option | Description | Selected |
|--------|-------------|----------|
| `output/.topics.lock` (FileLock 复用) | mirror `output/.glossary.lock` | ✓ |
| 全局 `output/.governance.lock` (跨 _glossary + _topics) | 共用一个锁 | |
| 无锁（接受 race） | 单用户假设 | |

**Auto-selected rationale:** 单 lock 文件每 governance file 是 v1.1 Phase 08 ship 的明确契约（避免跨域死锁）；多终端并行场景下用户可能同时 `glossary append` + `topics resolve`；接受 race 在多终端 deferred 段已 OOS

---

## Claude's Discretion

- Bootstrap 出来的初始 taxonomy 具体 category 划分 — 由 Claude 在 Phase 10 execute 时 read 17 archives 后决定具体形态
- `topics audit` 的 stdout markdown 排版细节
- `topics resolve --remove` 警告文案具体措辞
- `bootstrap --from-stdin` 的 stdin JSON schema 详细字段（minimal viable 即可）

## Deferred Ideas

- Topic 树排序 / 重命名 CLI（v1.3+ if friction）
- Topic alias / synonyms（v1.3+）
- Topic 引用 health check 自动修复
- Topic 树 GUI / Web Viewer（OOS）
