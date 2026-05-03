# Phase 10: Topic taxonomy governance + bootstrap CLI - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning
**Mode:** Auto (smart_discuss equivalent — infrastructure phase, all SC technical, 9 D-XX locked in v1.2-CANDIDATES.md)

<domain>
## Phase Boundary

立起 v1.2 知识库的"词表层"——`output/_topics.md` governance file + 3 read/write CLIs (`topics bootstrap` / `topics audit` / `topics resolve`)。这一 phase 落地完成后，Phase 11 的 per-slug `index.json` generator 才有可选 topic 集合可以从中选择；新概念走"申请 Pending → 用户偶尔 review"的 K5 governance 闭环。

**In-scope:**
- `output/_topics.md` 文件结构 + 首次创建逻辑
- `topics bootstrap` CLI（一次性扫 17 archives 提议初始 taxonomy）
- `topics audit [--json]` CLI（read-only：列 pending + 引用计数 + 孤儿）
- `topics resolve <pending-name> [--rename <new>]` CLI（promote pending → approved，atomic 跨多 index.json 引用更新）
- K5 边界 statically asserted（`topics` 三 cmd 不写 `index.json` / `summary.md` — `tests/test_k5_emitters.py` 模式扩展）
- FileLock 串行化（mirror v1.1 Phase 08 `output/.glossary.lock` 模式给 `output/.topics.lock`）

**Out-of-scope (Phase 11/12 territory):**
- per-slug `index.json` generator（Phase 11 KB-01..06）
- 顶层 `output/.index.json` rebuild 逻辑（Phase 11 KB-04..05）
- Claude 写 index.json 时如何申请新 topic（Phase 11 任务，本 phase 只确保 Pending 段可写）
- Auto-promote pending → approved（Out of Scope per D-04 K5 governance —— 用户 review 是必经步骤）
- Auto-cleanup orphan topics（KB-09 audit 报告，但不删，per Out of Scope item）

</domain>

<decisions>
## Implementation Decisions

### `output/_topics.md` File Structure (D-01)

- **D-01.1:** 文件路径 `output/_topics.md`（顶层 governance file，与 v1.1 Phase 08 ship 的 `output/_glossary.md` 同级，命名一致）
- **D-01.2:** 文件 schema = 2 段：顶部 `## Approved Taxonomy` + 底部 `## Pending`
- **D-01.3:** Approved Taxonomy 段用 markdown 嵌套 list 表达 category 树状（`- LLM` → `  - LoRA` → `  - RAG`），最多 3 层（`category > subcategory > topic`），避免过深
- **D-01.4:** Pending 段每条 = `### <pending-name>` H3 + 子 list 必填 3 字段：`- 申请来源 slug: <slug>` / `- chapter title: <title>` / `- 提议理由: <reason>`
- **D-01.5:** 文件首次创建由 `topics bootstrap` 触发；Phase 11 的 generator 在 _topics.md 不存在时 fail-fast（提示用户 `python -m agent.tools topics bootstrap` 先跑）
- **D-01.6:** 文件以 `# Topics Taxonomy\n\n> v1.2 knowledge-base governance — ...\n` header 开头（mirror `_glossary.md` 顶部说明段）

### `topics bootstrap` CLI (D-02)

- **D-02.1:** 命令 = `python -m agent.tools topics bootstrap` (no args, no flags first version)
- **D-02.2:** 行为 = 扫 17 v1.0/v1.1 archives 的 `output/<slug>/summary.md` + `output/_glossary.md` 已有 H2 anchors，由 Claude 多模态归纳出初始 taxonomy（**Claude is decider** — bootstrap 是 Claude 写入 _topics.md 的工具，不是脚本算法）
- **D-02.3:** Idempotent — 已存在 _topics.md（顶部 Approved Taxonomy 段非空）→ no-op + stderr 提示 "_topics.md already exists; rerun bootstrap by removing the file or use `topics resolve` to add individual topics"
- **D-02.4:** 首次 bootstrap 默认批（ground truth from 17 archives — 不进 Pending 段，直接写 Approved Taxonomy）
- **D-02.5:** stdout = JSON `{"action": "created" | "skipped", "approved_count": N, "_topics_path": "output/_topics.md"}` （machine-readable per K5 emitter convention）
- **D-02.6:** Implementation: bootstrap **不**自己生成 taxonomy（Claude is decider）— bootstrap 由 Claude 在 `/summarize-video` Phase 7.6 / 单独会话中提议 taxonomy 后调用 CLI 写入。CLI 提供 `--from-stdin` flag 读 stdin JSON `{"taxonomy": [...]}` 写入 _topics.md（mirror `glossary append` 的结构）。不读 stdin 时 fail-fast 报错（避免脚本臆造 taxonomy）

### `topics audit` CLI (D-03)

- **D-03.1:** 命令 = `python -m agent.tools topics audit [--json]` (no args; `--json` flag for Claude consumption)
- **D-03.2:** 行为 = 读 `output/_topics.md` + 扫所有 `output/<slug>/index.json`（如有），输出 3-段报告
- **D-03.3:** 输出段 a — `## Pending` 段所有 entry + 申请来源 slug + 申请理由（直接 markdown 复制 _topics.md 的 Pending 段）
- **D-03.4:** 输出段 b — 每个 approved topic 的引用计数（`# of slugs that reference this topic in their index.json`）
- **D-03.5:** 输出段 c — 孤儿 topic 检测（approved 但 0 slug 引用 — 用户 review 决定 keep / remove）
- **D-03.6:** `--json` 输出 schema = `{"pending": [{"name": ..., "from_slug": ..., "reason": ...}], "approved_with_counts": {"<topic>": N}, "orphans": ["<topic>", ...]}`
- **D-03.7:** Read-only — 永不写 _topics.md / index.json（K5 边界）

### `topics resolve` CLI (D-04)

- **D-04.1:** 命令 = `python -m agent.tools topics resolve <pending-name> [--rename <new-name>] [--remove]` (positional pending-name 必填; mutually exclusive flags: `--rename` 改名 promote / `--remove` 删除拒绝；都不带 = 直接 promote 同名)
- **D-04.2:** 行为 = atomic 跨多文件改写：(a) 在 _topics.md Approved Taxonomy 段插入 entry（按字母序在合适位置插入）；(b) 删除 _topics.md Pending 段中的 entry；(c) 扫所有 `output/<slug>/index.json` 中 `topics: [..., "pending: <name>"]` → 改为 `"<final-name>"`（rename 模式用 new name；plain promote 用同名）
- **D-04.3:** Atomic 实现 = (a) 持有 `output/.topics.lock` FileLock；(b) 读所有 will-modify 文件，构建 in-memory diff；(c) 用 atomic write 模式（tempfile + os.replace）依次写每个文件；(d) 任一步失败 → restore from snapshot（保 _topics.md + 所有 index.json 一起改完才落盘）
- **D-04.4:** `--remove` 模式 = atomic 删除 Pending entry + 把所有引用 `pending: <name>` 的 chapter 的 topics 字段改为空 array（`topics: []`），并在 stderr 警告这些 chapter 现在没有 topic 标签，建议用户 review
- **D-04.5:** stdout = JSON `{"action": "promoted" | "renamed" | "removed", "pending_name": "...", "final_name": "..." | null, "index_json_updated": [<slug>, ...], "_topics_path": "output/_topics.md"}`
- **D-04.6:** Pending entry 不存在 → fail-fast 报错（exit code 非 0），不创建空 promote

### Claude Governance Workflow (D-05 — Phase 11 contract)

- **D-05.1:** Phase 11 的 generator 写 per-slug `index.json` 时 `topics` 字段必须从 `_topics.md` 顶部 Approved Taxonomy 段选（白名单约束）
- **D-05.2:** 都不合适 → Claude 申请新 topic：append 到 `_topics.md` Pending 段（必填 3 字段：申请来源 slug / chapter title / 提议理由），并在该 chapter 的 index.json 中标 `topics: ["pending: <name>"]`
- **D-05.3:** Phase 10 提供"写 Pending 段"的 helper API（不是 CLI subcommand）— `agent/topics.py` 暴露 `append_pending(name: str, from_slug: str, chapter_title: str, reason: str)` Python 函数 + FileLock 串行化；Phase 11 的 generator import 它
- **D-05.4:** 用户 governance 节奏 = 偶尔（一周/一月）打开 `_topics.md` review Pending 段，跑 `topics audit --json` 看引用情况，再 `topics resolve` 批/拒/改

### K5 Boundary Static Assertion (D-06)

- **D-06.1:** `tests/test_k5_emitters.py` 已有 13 K5 boundary tests（v1.1 Phase 07/09 ship）— 加 4 条 new test 给 `topics bootstrap/audit/resolve` 三 cmd + `agent/topics.py` 模块：
  - `test_topics_bootstrap_no_index_json_writes` — `inspect.getsource(cmd_topics_bootstrap)` 不含 literal `index.json` / `summary.md` / `plan.md`
  - `test_topics_audit_no_writes` — `cmd_topics_audit` 整个函数不含任何 file write 模式（`Write` / `tempfile.NamedTemp` / `os.replace` / `open(.., "w")` 等）
  - `test_topics_resolve_only_writes_topics_md_and_index_json` — `cmd_topics_resolve` 允许写 `_topics.md` 和 `index.json`，但**禁止**写 `summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json`（4 核心 D-29 文件）
  - `test_topics_module_no_summary_writes` — `agent/topics.py` 模块整体源码不含 `summary.md` literal
- **D-06.2:** Source-grep 模式 = mirror v1.1 Phase 07-03 deviation #2 lesson（intent-correct write-pattern regex），不只查文件名 literal，也查 write API 调用模式

### `agent/topics.py` Module Layout (D-07)

- **D-07.1:** 新模块路径 = `agent/topics.py`（与 v1.1 ship 的 `agent/_glossary.py` / `agent/_v11.py` 同级）
- **D-07.2:** 模块导出 4 个 public functions:
  - `read_topics(topics_path: Path) -> dict` — 读 _topics.md，返回 `{"approved": [...tree...], "pending": [...]}`
  - `write_approved_taxonomy(topics_path: Path, taxonomy: list[dict]) -> None` — bootstrap 用，atomic write
  - `append_pending(topics_path: Path, name: str, from_slug: str, chapter_title: str, reason: str) -> None` — Phase 11 generator 调用
  - `resolve_pending(topics_path: Path, pending_name: str, *, rename: str | None = None, remove: bool = False) -> dict` — `topics resolve` CLI 调用，返回 `{"final_name": ..., "affected_index_json": [...]}`
- **D-07.3:** CLI handlers in `agent/tools.py`:
  - `cmd_topics_bootstrap(args)` 调用 `agent.topics.write_approved_taxonomy`
  - `cmd_topics_audit(args)` 调用 `agent.topics.read_topics` + 扫 `output/*/index.json`
  - `cmd_topics_resolve(args)` 调用 `agent.topics.resolve_pending`
- **D-07.4:** Subcommand routing in `agent/tools.py:241-250` cmds dict — 新增 keys `"topics"` 走 nested subparser（`topics bootstrap` / `topics audit` / `topics resolve`），mirror v1.1 Phase 07 ship 的 `queue` 子命令模式

### FileLock Serialization (D-08)

- **D-08.1:** 锁文件路径 = `output/.topics.lock`（mirror v1.1 Phase 08 `output/.glossary.lock`）
- **D-08.2:** 复用 `agent/_lock.py:FileLock` 模式（v1.0 Phase 06 ship）— stale-PID detection 自动接管
- **D-08.3:** 锁住的操作 = 任何对 `_topics.md` 的写（bootstrap / append_pending / resolve_pending）+ resolve 时跨 index.json 改写
- **D-08.4:** 锁不锁住 read-only audit（`cmd_topics_audit` 用 read-only file open，不要锁 — 避免 audit 卡 governance 流）

### Out of Scope for Phase 10 (Reaffirmation)

- Auto-promote pending → approved（Out of Scope per D-04 K5）
- Auto-cleanup orphan topics（audit 报告，不删）
- Topic 重排序 / 树结构编辑 CLI（v1.3+ if needed; Phase 10 接受 user 直接编辑 _topics.md）
- Cross-language topic alias / synonyms（"LoRA" === "low-rank-adaptation"）— Phase 10 一律用 canonical name；alias 走 v1.3+

### Claude's Discretion

- Bootstrap 出来的初始 taxonomy 具体 category 划分（按 LLM / Game-Dev / Tooling / Agent / ... 分？还是按主题域？）— Claude 实测在 Phase 10 execute 时 read 17 archives 后决定具体形态，CONTEXT.md 不预设 taxonomy
- `topics audit` 的 stdout markdown 排版细节（是否用 emoji / 表格 / bullet list）— Claude 选 read-friendly 默认即可
- `topics resolve --remove` 警告文案具体措辞 — Claude 选自然中文即可
- `bootstrap --from-stdin` 的 stdin JSON schema 详细字段（minimal viable 即可，extra fields 忽略）— Claude 选简单形态：`{"taxonomy": [{"name": "LLM", "subtopics": [{"name": "LoRA"}, ...]}, ...]}`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.2 Architecture (locked decisions)
- `.planning/v1.2-CANDIDATES.md` — 9 D-XX locked decisions (D-01..D-09); D-04 (taxonomy governance) and D-05 (bootstrap from 17 archives) are direct Phase 10 inputs
- `.planning/REQUIREMENTS.md` §INDEX + §TOPIC — KB-07 / KB-08 / KB-09 / KB-10 / KB-11 atomic requirement statements
- `.planning/ROADMAP.md` Phase 10 — 5 success criteria with byte-level acceptance tests

### v1.1 Patterns (reuse)
- `agent/_glossary.py` (v1.1 Phase 08 TEACH-A3) — append-only cross-slug accumulator with FileLock; mirror this pattern for `agent/topics.py`
- `output/_glossary.md` — file shape reference for `output/_topics.md` (header style, governance section pattern, single-file ownership)
- `agent/_v11.py` — opt-in marker pattern (NOT used in v1.2 — v1.2 is unconditional, no marker); referenced for module style consistency
- `agent/_lock.py:FileLock` (v1.0 Phase 06) — stale-PID detection, msvcrt + fcntl cross-platform; reuse verbatim for `output/.topics.lock`
- `tests/test_k5_emitters.py` — 13 existing K5 boundary tests (v1.1 Phase 07/09); extend with 4 new tests for topics CLI per D-06.1

### CLI Routing
- `agent/tools.py:241-250` cmds dict — top-level subcommand routing; v1.1 ship 的 `queue` 子命令是 nested subparser 范例（`queue add` / `queue list` / `queue next` / `queue done` / `queue skip`）；本 phase 加 `topics bootstrap` / `topics audit` / `topics resolve` 模式相同

### Codebase Maps
- `.planning/codebase/CONVENTIONS.md` — Python conventions (snake_case, dataclasses, `from __future__ import annotations`, PEP-604 unions, `cmd_*` CLI handler prefix); Phase 10 严格遵循
- `.planning/codebase/STRUCTURE.md` — `agent/` 模块 layout（与 `src/` 分层），`output/<slug>/` artifact 集合
- `.planning/codebase/STACK.md` — 现有 stack（Python 3.11/3.13, stdlib-only for `_lock` / `_glossary` / `topics`）

### Project-level
- `CLAUDE.md` — `/summarize-video` 8 阶段工作流（Phase 7.6 hook 在 Phase 11 加，本 phase 不动 CLAUDE.md）
- `.planning/PROJECT.md` Key Decisions — D-04 K5 governance、¥0 hard constraint、单用户作者工具

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`agent/_lock.py:FileLock`** — cross-platform stdlib (msvcrt + fcntl) FileLock with stale-PID takeover, ship 在 v1.0 Phase 06；Phase 10 直接 import for `output/.topics.lock` 串行化
- **`agent/_glossary.py`** — v1.1 Phase 08 ship 的 cross-slug accumulator 模式：read → modify → atomic-write with FileLock；`agent/topics.py` 模式克隆但 schema 不同（_glossary.md 是术语 H2 anchors append-only；_topics.md 有 Approved + Pending 双段 read-modify-write）
- **`agent/tools.py:cmd_*` 模式** — 统一 CLI handler 签名 `def cmd_xxx(args: argparse.Namespace) -> None`；`cmds = {"topics": cmd_topics_router, ...}` dict + nested subparser 给 `topics bootstrap/audit/resolve`
- **`tests/test_k5_emitters.py`** — `inspect.getsource()` static-assert 模式 + write-pattern regex；mirror to add 4 new tests per D-06.1

### Established Patterns

- **Atomic write** — `tempfile.NamedTemporaryFile + os.replace` (v1.0 Phase 02 RES-01..08 ship)；`agent/topics.py:write_approved_taxonomy` + `resolve_pending` 都用此模式
- **JSON stdout for K5 emitters** — `cmd_topics_bootstrap/audit/resolve` 输出 JSON `{"action": "...", ...}` 给 Claude consumption（mirror v1.1 K5 emitter 输出风格）
- **State events** — v1.0 Phase 02 ship 的 `state.jsonl` event log；Phase 10 不需要 state.jsonl 事件（topics CLI 是 governance 操作，不是 per-slug `/summarize-video` 阶段；audit / resolve 由用户 ad-hoc 触发）
- **Slug-prefix log lines** — v1.0 Phase 06 ship 的 `[<slug>] <cmd>:` 前缀；topics CLI 不针对单 slug，**不**加前缀（mirror `download` / `ingest` JSON 输出）

### Integration Points

- **Phase 11 dependency** — Phase 11 generator import `agent.topics.read_topics` 读 Approved Taxonomy（白名单）+ `agent.topics.append_pending` 申请新 topic；本 phase 暴露稳定 API
- **CLI subcommand entry** — `agent/tools.py:cmds` dict 加 `"topics"` key + nested subparser
- **No CLAUDE.md change** — Phase 10 不改 `/summarize-video` 工作流；Phase 11 在 Phase 7.6 hook 中加 generator + governance 触发；Phase 12 加自然语言推荐 prompt rule

</code_context>

<specifics>
## Specific Ideas

- **Bootstrap from-stdin JSON shape** — minimal viable schema 让 Claude 在会话中 `python -c "import json, sys; ..." | python -m agent.tools topics bootstrap --from-stdin`；schema：
  ```json
  {
    "taxonomy": [
      {"name": "LLM", "subtopics": [
        {"name": "LoRA"}, {"name": "RAG"}, {"name": "Tokenizer"}
      ]},
      {"name": "Game-Dev", "subtopics": [{"name": "Godot"}, {"name": "ECS"}]}
    ]
  }
  ```
- **Pending H3 entry shape**:
  ```markdown
  ### LangChain
  - 申请来源 slug: BV1HG9JBsEPK
  - chapter title: 三、用 LangChain 串 agent 工作流
  - 提议理由: LangChain 是 LLM 应用开发框架的事实标准之一，已在 3 个 archives 出现；建议加入 LLM 类目
  ```
- **Approved Taxonomy 范例（来自 D-05 bootstrap from 17 archives 的预期形态，由 Claude 实际产出后写入；这只是预期形态参考）**:
  ```markdown
  ## Approved Taxonomy

  - LLM
    - LoRA
    - RAG
    - Tokenizer
    - Compound Engineering
  - Game-Dev
    - Godot
    - ECS
    - Pixel-Art
  - Tooling
    - Claude Code
    - Cursor
    - TRAE SOLO
  - Agent
    - MCP
    - Hooks
  ```
- **resolve atomic write order** — 先 _topics.md，再 index.json 们；任一失败 → restore（snapshot 读所有 will-modify 文件先 to memory）

</specifics>

<deferred>
## Deferred Ideas

- **Topic 树排序 / 重命名 CLI** — `topics rename <old> <new>` / `topics reorder` 等高级编辑工具 — Phase 10 接受用户直接编辑 `_topics.md`，CLI 仅做 promote/reject pending；高级编辑 v1.3+ 如果实际遇到 friction 再加
- **Topic alias / synonyms** — `_topics.md` 加 `aliases: [low-rank-adaptation]` 字段 → audit 把 "Lora" 自动归到 "LoRA" — v1.3+；Phase 10 一律 canonical name + Pending 申请新概念
- **Topic 引用 health check 自动修复** — orphan topic 自动归档到归档段、`pending: <name>` chapter 自动报告 — Phase 10 audit 报告但不修；自动修复 v1.3+
- **Topic 树 GUI / Web Viewer** — 可视化 governance 工具 — 完全 out of scope（single-user 工具）

</deferred>

---

*Phase: 10-topic-taxonomy-governance-bootstrap-cli*
*Context gathered: 2026-05-04*
