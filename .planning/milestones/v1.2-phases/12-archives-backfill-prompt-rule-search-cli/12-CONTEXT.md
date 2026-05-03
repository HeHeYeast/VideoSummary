# Phase 12: 17 archives backfill + CLAUDE.md 推荐 prompt rule + search/list CLI - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning
**Mode:** Auto (smart_discuss equivalent — autonomous workflow; mostly infrastructure with one user-visible E2E behavior — CLAUDE.md 推荐 prompt rule)

<domain>
## Phase Boundary

v1.2 收尾——把 Phase 11 的 generator 复用到 17 v1.0/v1.1 archives 上一次性 backfill 写 index.json，让 Claude 一开新会话 Read 顶层 `.index.json` 就能看全 23+ 条；CLAUDE.md 加自然语言推荐 prompt rule（D-09 锁，不加 slash command，mirror v1.1 anti-hallucination 字面规则风格）；顺手 ship `index search/list` 兜底 CLI；末尾再跑一次 D-29 replay 确认 33/0/30。E2E 用户行为：用户在新 Claude Code 会话说"推荐 LLM Wiki 相关的视频"→ Claude FIRST ACTION Read `.index.json` → 返回 top-N 带 chapter 入口。

**In-scope:**
- `python -m agent.tools index backfill --all [--force]` CLI（一次性 backfill 所有 archives）
- 17 v1.0/v1.1 archives 写入 index.json（Claude 一条条调用 backfill 工具，由 Phase 11 generator 实际写入）
- CLAUDE.md 加 `## v1.2 知识库自然语言推荐入口` H2 段（触发 phrase + FIRST ACTION + 推荐回复格式锁 + anti-hallucination FORBIDDEN list）
- `python -m agent.tools index search <query> [--json]` 兜底 CLI（keyword 子串匹配）
- `python -m agent.tools index list [--topic <topic>] [--mode <mode>] [--json]` 兜底 CLI（按 filter 列）
- D-29 replay close gate（mirror Phase 11 D-07）

**Out-of-scope (永久 / 未来):**
- 6 队列视频不需要 backfill — 它们 next 跑 `/summarize-video` 时通过 Phase 11 Phase 7.6 hook 同步生成（per D-06 in v1.2-CANDIDATES.md）
- Slash command 推荐入口 (`/recommend-videos`) — D-09 锁，永久 OOS（KB-FUT-03/04）
- Cross-summary backlinks — D-07 锁，永久 OOS（KB-FUT-01/02）
- Advanced search 功能（fuzzy match / 日期范围 / mode-specific scoring）— Future v1.3+（KB-FUT-05/06）
- Auto-promote pending topics — Phase 10 已锁 OOS

</domain>

<decisions>
## Implementation Decisions

### `index backfill` CLI (D-01)

- **D-01.1:** 命令 = `python -m agent.tools index backfill --all [--force]` (no positional args; flags only first version)
- **D-01.2:** 行为 = 扫 `output/*/summary.md` 找出所有 archive slugs（排除 `_*` / `.*` 非 archive 目录），然后**对每个 slug 输出一段 YAML/JSON-compatible "to-do" 列表给 stdout**——告诉 Claude **哪些 slug 需要写 index.json**（Claude is decider per K5；CLI 不算 keywords / topics / tldr）
- **D-01.3:** 实际 backfill 由 Claude 在 backfill phase 中**循环 reads each archive's summary.md + meta.json + plan.md** + 用 Phase 11 ship 的 `python -m agent.tools index write --slug <slug> --from-stdin --force` 一条条写。`--force` flag 关键：跳过白名单 fail-fast（部分老归档可能在 keywords 中含 `_glossary.md` 不存在的术语，per Phase 11 D-05.7）
- **D-01.4:** Idempotent — 已有 `output/<slug>/index.json` 默认 skip（不 overwrite）；`--force` flag 才 overwrite
- **D-01.5:** Error tolerance — 单 slug summary.md 损坏 / meta.json 缺失 → 该 slug 标 `failed: <reason>`；其他 slug 继续；最终 stdout 报告失败列表 + exit code 非 0 if 任意失败
- **D-01.6:** stdout = JSON `{"action": "scanned", "total_slugs": N, "to_backfill": [<slug>, ...], "skipped_existing": [<slug>, ...], "failed": [{"slug": ..., "reason": ...}], "_topics_path": "output/_topics.md", "_glossary_path": "output/_glossary.md or null"}` — Claude 读这个 stdout 决定下一步 backfill 顺序

### Backfill Execution Strategy (D-02)

- **D-02.1:** Phase 12 plan 12-02 中由 Claude 实际逐个 backfill：先 invoke `index backfill --all` 拿到 to-do list，再循环对每个 slug：
  1. Read `output/<slug>/summary.md` + `meta.json` + `plan.md`（如有）
  2. 推断 8 字段（mode 缺失 fallback `replicate-guide`；keywords 优先复用 `_glossary.md` H2 anchors）
  3. Pipe JSON: `python -m agent.tools index write --slug <slug> --from-stdin --force <<EOF ... EOF`
- **D-02.2:** 不并行 backfill — 顺序处理（避免 K5 governance race；`output/_topics.md` Pending 段如果有新申请会串行 append）
- **D-02.3:** Backfill 结束后 Claude invoke `python -m agent.tools index rebuild` 强制 rebuild 顶层 `.index.json` 一次（虽然 Phase 11 generator 每次 write 都自动 rebuild，但批量后再一次 rebuild 是 belt-and-suspenders）
- **D-02.4:** 17 archives 实际 list（确认 `_topics.md` / `_glossary.md` / `.index.json` / `.index.lock` 等顶层非 archive 文件被排除）：
  - 13 BV* slugs（B 站）
  - 4 douyin_* slugs（抖音）
  - 实际 list 由 backfill CLI 扫描 `output/*/summary.md` 得出（动态，不硬编码）

### CLAUDE.md 推荐 Prompt Rule (D-03)

- **D-03.1:** CLAUDE.md 顶层加新 H2 段 `## v1.2 知识库自然语言推荐入口`（mirror v1.1 ship 的 `## v1.1 自适应教学文档增强` H2 形态）
- **D-03.2:** 段内容结构 = 4 个子段 + 1 anti-hallucination FORBIDDEN list:
  1. **触发 phrase 锁**（byte-locked literal list）：`'推荐'` / `'相关'` / `'我之前看过'` / `'学过'` / `'找一下我'` / `'哪些视频'` / `'类似查询意图'`
  2. **FIRST ACTION**: `Read output/.index.json`（如果文件不存在 → hint user 跑 `python -m agent.tools index rebuild`）
  3. **推荐格式锁**（每条推荐 = 1 行 slug+title+共享匹配信号 + 1 行 tldr + 1-3 个 chapter 入口；mirror v1.1 5th format-spec invariant 的字面规则风格）
  4. **回复格式 byte-equal example**（演示 1 条完整推荐看起来是什么样）
  5. **FORBIDDEN list (anti-hallucination)**:
     - FORBIDDEN 推荐 `.index.json` 里没有的 slug
     - FORBIDDEN 编造视频内容（必须基于 .index.json 中的 tldr / keywords / chapters）
     - FORBIDDEN 修改 4 D-29 核心文件
     - FORBIDDEN 在推荐回复中加 `<thinking>` 推理过程（直接给推荐）
- **D-03.3:** 段位置 = CLAUDE.md 中插入在 `## v1.1 校对自动化 (Phase 09)` H2 之后、`## /summarize-video 完整工作流` H2 之前（mirror v1.1 H2 段 placement 风格）
- **D-03.4:** 段头 ledger 与 v1.1 形态一致：
  ```
  ## v1.2 知识库自然语言推荐入口

  > 这一节是 v1.2 知识库 milestone 的查询入口契约。当用户提以下意图时，Claude FIRST ACTION 读 `output/.index.json` 给出推荐。**触发 phrase 锁定 + 推荐格式锁 + anti-hallucination 锁** 三层保证一致体验。
  ```

### `index search` CLI (D-04 — KB-MISC-01 兜底)

- **D-04.1:** 命令 = `python -m agent.tools index search <query> [--json]` (positional query 必填; `--json` flag for machine output)
- **D-04.2:** 行为 = 读顶层 `output/.index.json`，对每条 entry 在 `keywords[]` / `tldr_oneliner` / `chapters[*].title` / `chapters[*].excerpt` 中做 case-insensitive 子串匹配；返回命中的 slugs + 匹配字段
- **D-04.3:** stdout 默认 = human-readable plain text（`<slug>: <title> [matched: <field-list>]\n`）；`--json` flag 输出 `{"query": "...", "matches": [{"slug": ..., "title": ..., "matched_fields": [...], "tldr": "...", "chapter_hits": [{"title": ..., "start": ...}, ...]}]}`
- **D-04.4:** Read-only — 永不写文件（K5 边界 statically asserted）
- **D-04.5:** No fuzzy match in v1.2（v1.3+ 如需要再加 — KB-FUT-05）

### `index list` CLI (D-05 — KB-MISC-01 兜底)

- **D-05.1:** 命令 = `python -m agent.tools index list [--topic <topic>] [--mode <mode>] [--json]`
- **D-05.2:** 行为 = 读顶层 `output/.index.json`；按 `--topic` filter `topics[] contains <topic>`；按 `--mode` filter `mode == <mode>`；都不带 = list 全部
- **D-05.3:** stdout 默认 = human-readable plain text（`<slug>: <title> (mode=<mode>) topics=<topics-csv>\n`）；`--json` flag 输出 array
- **D-05.4:** Read-only
- **D-05.5:** Combined filter (`--topic X --mode Y`) = AND 逻辑

### Module Layout (D-06)

- **D-06.1:** 复用 Phase 11 ship 的 `agent/index.py` 模块；新增 3 函数:
  - `scan_archives_for_backfill(output_dir: Path) -> dict` — 扫 archives 找 to-backfill list
  - `search_index(query: str, output_dir: Path = Path("output")) -> list[dict]` — 顶层 .index.json 子串匹配
  - `list_index(*, topic: str | None = None, mode: str | None = None, output_dir: Path = Path("output")) -> list[dict]` — 顶层 .index.json filter
- **D-06.2:** CLI handlers in `agent/tools.py` (3 new):
  - `cmd_index_backfill(args)` 调用 `agent.index.scan_archives_for_backfill` + 输出 to-do list JSON
  - `cmd_index_search(args)` 调用 `agent.index.search_index`
  - `cmd_index_list(args)` 调用 `agent.index.list_index`
- **D-06.3:** Subcommand 加在 Phase 11 ship 的 `cmds["index"]` nested subparser — 现在有 5 个 sub-subcommands: `write` / `rebuild` / `backfill` / `search` / `list`

### K5 Boundary (D-07)

- **D-07.1:** `tests/test_k5_emitters.py` 已有 20 K5 boundary tests（v1.0 + v1.1 + Phase 10 + Phase 11 ship）— 加 3 条 new test 给 Phase 12 新 cmds:
  - `test_K5_cmd_index_backfill_no_d29_writes` — `cmd_index_backfill` 整个函数源码不含 D-29 5 文件 literal
  - `test_K5_cmd_index_search_no_writes` — `cmd_index_search` 整个函数源码不含任何 file write 模式
  - `test_K5_cmd_index_list_no_writes` — `cmd_index_list` 整个函数源码不含任何 file write 模式
- **D-07.2:** 新 functions in `agent/index.py` (search_index / list_index / scan_archives_for_backfill) 都是 read-only — 不需要新 module-level K5 test（已有 Phase 11 module-level K5 test cover module）

### D-29 Byte-Equal Close Gate (D-08)

- **D-08.1:** Phase 12 close 前必须跑 `python scripts/replay_v10_archives.py` 输出 33 PASS / 0 FAIL（mirror Phase 11 D-07.1）
- **D-08.2:** 17 archives backfill 操作的是新 sidecar `output/<slug>/index.json`；4 核心文件（summary.md / segs.json / paragraphs.json / meta.json）只 READ 不 WRITE；replay 不会触发
- **D-08.3:** 如果 Phase 12 中发现某个 archive 的 4 核心文件被误改 → 立刻回滚 + 调查 generator bug；这是 Phase 11 D-07.4 锁定的 invariant

### E2E 推荐行为 Verification (D-09)

- **D-09.1:** Phase 12 verification 中 Claude 主动跑 1-2 次 mock query 测试推荐行为（手动模拟用户说"推荐 LLM Wiki 相关的视频"等触发 phrase）
- **D-09.2:** Mock query 期望行为：Claude FIRST ACTION 读 `output/.index.json` → 命中包含 `LLM-Wiki` topic 或 `Karpathy` keyword 的 entries → 返回 top-3 推荐 + 每条 1-3 chapter 入口；不编造 slug；不绕过格式锁
- **D-09.3:** 实测 expected: `output/.index.json` 中至少 1 条 entry topics 含 `LLM-Wiki`（来自 douyin_karpathy_llm_wiki archive；Phase 10 ship 的 `_topics.md` 已 ship 该 topic）
- **D-09.4:** E2E behavioral UAT 不可 unit-test（Claude 是 prompt-driven）— 同 Phase 11 KB-02 + v1.1 P-09 pattern；Phase 12 verifier 接受 deferred manual UAT

### Out of Scope for Phase 12 (Reaffirmation)

- 6 队列视频 backfill（per D-06 v1.2-CANDIDATES.md — 跑 /summarize-video 时同步生成）
- Slash command 推荐入口（OOS per D-09 v1.2-CANDIDATES.md）
- Cross-summary backlinks（OOS per D-07）
- Advanced search 功能（v1.3+ deferred）
- Auto-promote pending topics（Phase 10 OOS）
- 索引 build 进度条 / verbose log（minimal viable，纯 stdout JSON 即可）

### Claude's Discretion

- 推荐回复格式锁的具体排版细节（用 emoji / 表格 / bullet list）— Claude 在 Phase 12 plan 12-02 中实现 + CLAUDE.md byte-locked 后自然形态
- `index search` 子串匹配是否包含 chapter excerpt（CONTEXT.md D-04.2 包含；可保留如执行时发现匹配过多噪音再调）
- `index list` plain text 排版（多列对齐 / sort key）
- backfill 顺序（按字母序 / mtime / 视频时长）— Claude 选自然形态；test 不强约束
- 17 archives 中 keywords / topics 的具体推断策略（每个 archive Claude 多模态读 summary.md 后判断；不 pre-bake）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.2 Architecture (locked)
- `.planning/v1.2-CANDIDATES.md` — D-06 (backfill 一次性) / D-09 (推荐入口自然语言) / D-07 (drop backlinks) 直接 Phase 12 输入
- `.planning/REQUIREMENTS.md` §BACKFILL + §PROMPT + §OPTIONAL — KB-12 / KB-13 / KB-14 / KB-15 / KB-MISC-01 atomic 要求
- `.planning/ROADMAP.md` Phase 12 — 5 success criteria

### Phase 10 + 11 Contracts (just shipped)
- `agent/topics.py` (Phase 10 ship) — `read_topics` / `append_pending` 稳定 import
- `agent/index.py` (Phase 11 ship) — `validate_per_slug_index` / `read_per_slug_index` / `write_per_slug_index` / `rebuild_aggregator` / `read_aggregator` / `glossary_h2_anchors` 稳定 import
- `agent/tools.py:cmds["index"]` (Phase 11 ship) — nested subparser；本 phase 加 3 个新 sub-subcommands
- `output/_topics.md` (Phase 10 ship — 5 categories / 19 leaves / 24 nodes) — backfill 时 topics 白名单源
- CLAUDE.md `### Phase 7.6` 段 (Phase 11 ship) — 新视频流程；本 phase 加 H2 推荐入口段

### v1.1 Patterns
- `## v1.1 自适应教学文档增强` H2 段 (v1.1 Phase 08 ship) — H2 段 placement + byte-locked rule format reference
- v1.1 5th format-spec invariant — anti-hallucination FORBIDDEN list literal style reference

### CLI Routing
- `agent/tools.py` `cmds["index"]` nested subparser (Phase 11 ship) — 加 3 个新 subcommands
- `agent/tools.py` `cmds["topics"]` (Phase 10 ship) — pattern model

### D-29 Replay
- `scripts/replay_v10_archives.py` (v1.1 Phase 07 ship) — Phase 12 close gate

### Codebase Maps
- `.planning/codebase/CONVENTIONS.md` — Python conventions
- `.planning/codebase/STRUCTURE.md` — `agent/` 模块 layout

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`agent/index.py:write_per_slug_index`** — Phase 11 ship；backfill 调用 CLI wrapper `index write --slug X --from-stdin --force`
- **`agent/index.py:rebuild_aggregator`** — Phase 11 ship；backfill 结束后调用 `index rebuild` belt-and-suspenders
- **`agent/index.py:read_aggregator`** — Phase 11 ship；`search_index` / `list_index` 复用读顶层 `.index.json`
- **`agent/index.py:glossary_h2_anchors`** — Phase 11 ship；backfill 时 keywords 优先复用 H2 anchors
- **`agent/topics.py:read_topics`** — Phase 10 ship；backfill 时 topics 白名单
- **`agent/_lock.py:FileLock`** — Phase 12 不需要新锁（search / list 是 read-only；backfill 是 write 但走 Phase 11 的 `.index.lock`）
- **CLI nested subparser pattern** — Phase 10/11 ship 的 `cmds["topics"]` / `cmds["index"]` 模式；本 phase 加 `cmds["index"]` 的 3 个新 sub-subcommand

### Established Patterns

- **JSON stdout** — `cmd_index_backfill / search / list` 都支持 `--json` flag
- **Read-only K5** — `cmd_index_search / list` 是 read-only；`cmd_index_backfill` 也是 read-only（实际写入由 Claude 调用 `index write` CLI）
- **Slug-prefix log lines** — Phase 12 cmds 都不针对单 slug 操作（backfill 跨 slug, search/list 跨 slug）— 不加前缀

### Integration Points

- **CLAUDE.md** — Phase 12 加 `## v1.2 知识库自然语言推荐入口` H2 段（在 `## v1.1 校对自动化` 之后、`## /summarize-video 完整工作流` 之前）
- **Phase 11 module reuse** — `agent/index.py` 加 3 个新函数（不创新 module）
- **CLI entry** — `cmds["index"]` 已在 Phase 11 ship；本 phase 在 nested subparser 加 3 sub-subcommands

</code_context>

<specifics>
## Specific Ideas

- **`index backfill --all` to-do list JSON 范例**:
  ```json
  {
    "action": "scanned",
    "total_slugs": 22,
    "to_backfill": [
      "BV132wizyEEB", "BV1HG9JBsEPK", "BV1rsd7BsEnA", "BV1aGXNYLE2D",
      "BV1Q1XNYNECP", "BV1FoXNYTEvR", "BV1V8LLzRECs", "BV1RYP9zPESu",
      "BV1QrXKYbE5p", "BV1cVTKzWEFi", "BV13K4yzeEMD", "BV1DwL7zKEdY",
      "BV1Pp4yzqEPq",
      "douyin_ai_kb", "douyin_claude_code_hooks", "douyin_karpathy_llm_wiki",
      "douyin_trae_ai", "godot_brave"
    ],
    "skipped_existing": [],
    "failed": [],
    "_topics_path": "output/_topics.md",
    "_glossary_path": null
  }
  ```

- **CLAUDE.md 推荐 prompt rule 段范例**:
  ```markdown
  ## v1.2 知识库自然语言推荐入口

  > 这一节是 v1.2 知识库 milestone 的查询入口契约。当用户提以下意图时，Claude FIRST ACTION 读 `output/.index.json` 给出推荐。**触发 phrase 锁定 + 推荐格式锁 + anti-hallucination 锁** 三层保证一致体验。

  ### 触发 phrase 锁

  用户消息中**明确包含**以下任一 phrase（byte-equal literal）→ 走推荐入口：
  - '推荐'、'相关'、'我之前看过'、'学过'、'找一下我'、'哪些视频'、'类似查询意图'

  ### FIRST ACTION

  接到推荐意图 → 立即调用 `Read output/.index.json`（不要先 grep / 不要先问澄清；先 Read）。
  - 文件存在 → 解析 JSON dict，每个 key 是 slug，value 是 per-slug 8 字段索引
  - 文件不存在 → 回复用户："索引未生成，请先跑 `python -m agent.tools index rebuild`"

  ### 推荐回复格式锁

  返回 top-N（默认 N=3）推荐，每条**严格 3 行**结构（mirror v1.1 5th format-spec invariant 字面规则）：

  - 第 1 行: `**<slug>**: <title> — 共享 <匹配信号: keyword/topic>`
  - 第 2 行: `> <tldr_oneliner>`（blockquote 包裹 1 行）
  - 第 3 行（可选）: 1-3 个 chapter 入口形如 `[HH:MM:SS] <chapter title>`，逗号分隔

  ### Byte-equal example

  用户："推荐学习 LLM Wiki 范式相关的视频"

  Claude（先 Read output/.index.json，然后）：
  ```
  根据知识库匹配到 top-3 相关视频：

  **douyin_karpathy_llm_wiki**: Karpathy 的 LLM Wiki 范式（4:02 video）— 共享 LLM-Wiki / RAG topics
  > 75 行 Python gist 实现"个人知识库 = LLM 编译知识"的范式
  - [00:00:18] Karpathy: "Every query is rediscovering knowledge."
  - [00:01:25] 新员工 vs 图书管理员的比方
  - [00:03:42] LLM 终于补上 Memex 缺失的"维护者"角色
  ```

  ### Anti-hallucination FORBIDDEN list

  - **FORBIDDEN** 推荐 `output/.index.json` 中**不存在**的 slug（编造 slug = 致命错误）
  - **FORBIDDEN** 编造视频内容 — tldr / keywords / chapters 必须 byte-equal 来自 .index.json
  - **FORBIDDEN** 修改 `summary.md` / `meta.json` / `paragraphs.json` / `segs.json`（D-29 invariant）
  - **FORBIDDEN** 在推荐回复中加 `<thinking>` reasoning（直接给推荐；用户要看结果不看推理过程）
  - **FORBIDDEN** 推荐多于 N=5 条（信息过载；如用户要更多让他显式说"列全部"）
  ```

- **`index search` 范例**:
  ```bash
  $ python -m agent.tools index search "Karpathy"
  douyin_karpathy_llm_wiki: Karpathy 的 LLM Wiki 范式 [matched: title, keywords, tldr_oneliner]

  $ python -m agent.tools index search "ECS" --json
  {"query": "ECS", "matches": [{"slug": "...", "title": "...", "matched_fields": ["chapters[0].title"], "tldr": "...", "chapter_hits": [{"title": "三、ECS 之争", "start": 540.0}]}]}
  ```

- **`index list` 范例**:
  ```bash
  $ python -m agent.tools index list --topic "LLM-Wiki"
  douyin_karpathy_llm_wiki: Karpathy 的 LLM Wiki 范式 (mode=interview-distillation) topics=LLM-Wiki,LLM-Concepts

  $ python -m agent.tools index list --mode "replicate-guide" --json
  [{"slug": "BV132wizyEEB", "title": "...", "mode": "replicate-guide", "topics": [...]}, ...]
  ```

</specifics>

<deferred>
## Deferred Ideas

- **Slash command 推荐入口** (`/recommend-videos <query>`) — D-09 永久 OOS；自然语言已足够
- **Cross-summary backlinks** — D-07 永久 OOS；single-user 23 条规模不需要
- **Advanced search**（fuzzy match / 日期范围 / mode-specific scoring / SQLite-backed） — v1.3+
- **6 队列视频 backfill** — Phase 11 Phase 7.6 hook 同步生成；不需要 explicit backfill
- **Auto-promote pending topics** — Phase 10 OOS（governance design intent）
- **Top-level .index.json split / pagination** — v1.3+ if scale > 200 entries
- **per-slug index.json schema versioning** — v1.3+ Deferred from Phase 11

</deferred>

---

*Phase: 12-archives-backfill-prompt-rule-search-cli*
*Context gathered: 2026-05-04*
