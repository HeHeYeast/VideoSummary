# Phase 11: per-slug index.json + 顶层聚合 + Phase 7.6 hook - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning
**Mode:** Auto (smart_discuss equivalent — infrastructure phase, all SC technical, 9 D-XX locked in v1.2-CANDIDATES.md, Phase 10 contracts stable)

<domain>
## Phase Boundary

落地 v1.2 知识库的"中颗粒索引层"——给每个 `output/<slug>/` 写 `index.json`（8 字段 schema 锁死），keywords 优先复用 v1.1 ship 的 `output/_glossary.md` H2 anchors 避免分裂；顶层聚合 `output/.index.json` atomic rebuild 让 Claude 一次 Read 拿全 23+ 条概览；`/summarize-video` Phase 7.6 hook 让新视频自动同步生成；老归档 backfill 复用同一 generator（Phase 12 用）保证一致性。D-29 byte-equal 33/0/30 仍 PASS（index.json 是新 sidecar 不在 replay 比对范围）。

**In-scope:**
- per-slug `output/<slug>/index.json` 8 字段 schema + generator
- 顶层 `output/.index.json` atomic rebuild + manual `index rebuild` CLI
- `/summarize-video` Phase 7.6 hook（CLAUDE.md 工作流改写）
- keywords 抽取复用 `output/_glossary.md` H2 anchors
- topics 抽取走 Phase 10 已 ship 的 `agent.topics.read_topics`（白名单） + `agent.topics.append_pending`（新概念走 Pending）
- D-29 byte-equal 主动 verify (`scripts/replay_v10_archives.py` 自动化 gate post-Phase-11)

**Out-of-scope (Phase 12 territory):**
- 17 archives backfill 一次性补齐（Phase 12 KB-12/KB-13）
- CLAUDE.md 自然语言推荐 prompt rule（Phase 12 KB-14/KB-15）
- search/list 兜底 CLI（Phase 12 KB-MISC-01）

</domain>

<decisions>
## Implementation Decisions

### per-slug `index.json` Schema (D-01)

- **D-01.1:** 文件路径 `output/<slug>/index.json`（每个 slug 自己一份；与 `summary.md` / `paragraphs.json` / `segs.json` / `meta.json` 同级）
- **D-01.2:** 8 字段 schema 锁死（缺一字段 = 生成失败 + 明确错误）：
  - `slug` (string) — 与目录名一致；写入时校验
  - `title` (string) — 从 meta.json 读取
  - `duration_s` (number) — 从 meta.json 读取（视频时长秒数，浮点）
  - `mode` (string) — 4 mode 之一（replicate-guide / concept-explanation / extension-applications / interview-distillation）；从 plan.md front-matter 读取，缺失 fallback 到 `replicate-guide`（per CLAUDE.md fallback 规则）
  - `topics` (array of strings) — 从 `agent.topics.read_topics()` 已批准白名单选；新概念走 `pending: <name>` + 调用 `agent.topics.append_pending`；空 array 合法
  - `keywords` (array of strings) — 优先复用 `output/_glossary.md` H2 anchors 的 canonical 形式；新概念才创造新 keyword；空 array 合法
  - `tldr_oneliner` (string) — 1 行视频核心，10-50 字；由 Claude 在 generator 中读 summary.md 提炼
  - `chapters` (array of objects) — 每项 = `{title: string, start: number, excerpt: string}`，excerpt 1-2 行（≤ 200 字）；**无独立 keywords 字段** per D-02
- **D-01.3:** `chapters[].start` 单位 = 浮点秒（与 segs.json / paragraphs.json 一致）
- **D-01.4:** Schema 校验 = `agent/index.py` 模块导出 `validate_per_slug_index(d: dict) -> None` 函数；缺字段 / 类型错 / mode 不在 4 之内 / topics 不在白名单 → raise `IndexValidationError`
- **D-01.5:** 生成器源 = Claude 多模态读 summary.md + meta.json + plan.md + paragraphs.json + _glossary.md 后 produce JSON pipe 给 CLI（同 Phase 10 bootstrap pattern；Claude is decider per K5）

### Phase 7.6 Hook in `/summarize-video` (D-02)

- **D-02.1:** CLAUDE.md `## /summarize-video 完整工作流` 段加 Phase 7.6 子步骤（在 Phase 7 写完 summary.md 之后、Phase 7.5 verifier 之后、Phase 8 cleanup 之前）
- **D-02.2:** Phase 7.6 hook 行为顺序：
  1. Claude 读 `output/<slug>/summary.md` + meta.json + plan.md + paragraphs.json + `output/_glossary.md` + `output/_topics.md`
  2. Claude 推断 8 字段（topics 从 _topics.md Approved 选；keywords 从 _glossary.md H2 锚点选；tldr_oneliner / chapters 由 Claude 提炼）
  3. Claude pipe JSON 给 CLI: `python -m agent.tools index write --slug <slug> --from-stdin <<EOF ...`
  4. CLI 验证 schema → 写入 `output/<slug>/index.json`（atomic）
  5. CLI 立刻 rebuild 顶层 `output/.index.json`（扫所有 `output/*/index.json`）
- **D-02.3:** 用户零操作（D-03 自动化优先）— Claude 完全自动；如果 Claude 在某 chapter 选不出 approved topic，自动 append `pending: <name>` 到 `_topics.md` Pending 段
- **D-02.4:** `/summarize-video` 工作流文档加 byte-equal 段落（mirror v1.1 Phase 8 加 5-min TL;DR 段落的形态）

### 顶层 `output/.index.json` Aggregator (D-03)

- **D-03.1:** 文件路径 `output/.index.json`（顶层；与 `_topics.md` / `_glossary.md` 同级；点开头表示元数据）
- **D-03.2:** Schema = 扁平 dict `{"<slug>": <per-slug-index-json>, ...}`（无 backlink 字段 per D-07；mirror v1.1 Phase 07 ship 的 `.queue.lock` JSON 形态思路：machine-readable 给 Claude 一次 Read）
- **D-03.3:** 自动 rebuild 触发 = 每次 `index write` CLI 写入 per-slug index.json 后立刻扫所有 `output/*/index.json` rebuild 顶层（atomic write via tempfile + os.replace）
- **D-03.4:** 体积控制 = 23 条 × 100-300 字/条 ≈ 5-10 KB；Claude 一次 Read 无压力（v1.1 P-09 token budget compounding 兜底已验证 Read 5-10 KB 是 negligible）
- **D-03.5:** Stale detection = `index rebuild` CLI 比对每个 per-slug index.json mtime 与顶层 .index.json mtime；新于顶层者列出（stdout warning + JSON `stale: [<slug>, ...]` 字段）
- **D-03.6:** 顶层 .index.json 不在 D-29 replay 比对范围（mirror per-slug index.json sidecar 处理；4 核心文件只有 summary.md / segs.json / paragraphs.json / meta.json）

### `index rebuild` Manual CLI (D-04)

- **D-04.1:** 命令 = `python -m agent.tools index rebuild` (no args; idempotent)
- **D-04.2:** 行为 = 扫 `output/*/index.json`（glob 排除 `_*` / `.git` / `.*` 隐藏目录），合并到顶层 `.index.json` atomic write
- **D-04.3:** Per-slug index.json 缺失 / schema 不合规 → stderr WARNING（具体 slug + 原因）+ 跳过该 slug 不入顶层；其他 slug 继续；最终 exit code 0 if 至少 1 个 valid，else exit code 1
- **D-04.4:** stdout = JSON `{"action": "rebuilt", "slugs_included": N, "slugs_skipped": [{"slug": "...", "reason": "..."}, ...], "stale_detected": [...], "_index_path": "output/.index.json"}`
- **D-04.5:** Stale detection（D-03.5 实现）— 命令开始时先检查 mtime 关系，如果有 stale 则在 stdout JSON 中列出（仅 warning，不阻断 rebuild）
- **D-04.6:** Atomic write 使用 v1.0 Phase 02 ship 的 `tempfile.NamedTemporaryFile + os.fsync + os.replace` 模式（mirror agent/_glossary.py write_glossary 实现）

### `index write` CLI (D-05 — Phase 7.6 hook target)

- **D-05.1:** 命令 = `python -m agent.tools index write --slug <slug> --from-stdin` (slug 必填; stdin pipe JSON)
- **D-05.2:** 行为 = (a) 读 stdin JSON; (b) 验证 8 字段 schema (`validate_per_slug_index`); (c) 验证 `topics[]` 中所有 non-pending entry 在 `_topics.md` Approved 段（白名单约束）；(d) atomic write `output/<slug>/index.json`; (e) 立刻 rebuild 顶层 `output/.index.json`
- **D-05.3:** Schema 验证失败 → stderr 详细错误 + exit code 1；不破坏既有 `output/<slug>/index.json`（如有）
- **D-05.4:** Topics 不在白名单 → 默认 fail-fast；如果用户明确 stdin JSON 中带 `pending: <name>` 形态的 topics（`["pending: LangChain"]`）→ CLI 接受并 append 到 `_topics.md` Pending（调用 `agent.topics.append_pending`）；普通 string 必须严格在白名单
- **D-05.5:** stdout = JSON `{"action": "written" | "skipped", "slug": "...", "_index_path": "output/<slug>/index.json", "_aggregator_path": "output/.index.json", "_topics_pending_appended": [<name>, ...]}`
- **D-05.6:** Idempotent 行为 = 已存在 `output/<slug>/index.json` AND stdin JSON byte-equal → no-op + `action: skipped`；任何字段不一致 → 覆盖（视为新版本）
- **D-05.7:** `--force` flag 跳过白名单严格校验（仅用于 Phase 12 backfill 救急；正常 Phase 7.6 hook 不传）

### keywords 复用 `_glossary.md` H2 Anchors (D-06)

- **D-06.1:** Generator 在 Phase 7.6 hook 中读 `output/_glossary.md`，解析所有 H2 anchors（`^## ` 开头的 line）作 candidate set
- **D-06.2:** Claude 写 keywords 时先匹配 summary.md 命中的 H2 anchor term；命中者使用**字面 byte-equal** canonical 形式（如 `LoRA (Low-Rank Adaptation)` 不是 `LoRA` / `Lora` / `low-rank adaptation`）
- **D-06.3:** 新概念才创造新 keyword（不在 H2 anchor 集合中）；新 keyword 不强制 append 到 `_glossary.md`（_glossary.md 是 v1.1 自包含 inline 注解的 sidecar，写时机不同）
- **D-06.4:** 验证 = Phase 11 测试用 mock _glossary.md + mock summary.md 跑 generator，断言输出 keyword 是 byte-equal canonical 形式而不是 fragment

### D-29 Byte-Equal 主动 Verify (D-07)

- **D-07.1:** Phase 11 close 前必须跑 `python scripts/replay_v10_archives.py` 输出 33 PASS / 0 FAIL（4 核心文件比对）
- **D-07.2:** 任一字节 diff 在 4 核心文件（summary.md / segs.json / paragraphs.json / meta.json）→ phase NOT shippable + 立刻调查 generator 是否误改老 archive
- **D-07.3:** 新 sidecar (`output/<slug>/index.json` / `output/.index.json`) 不在 replay 比对范围 — 加多少都不破 replay
- **D-07.4:** Phase 11 generator 操作的 output/ 目录 = 17 archives 之一时（debug / 测试用），必须先 backup 4 核心文件再操作；正式 backfill 在 Phase 12 通过 generator pipe 不直接读写 4 核心文件，所以 byte-equal 自然守住

### `agent/index.py` Module Layout (D-08)

- **D-08.1:** 新模块路径 = `agent/index.py`（与 `agent/topics.py` / `agent/_glossary.py` / `agent/_lock.py` 同级）
- **D-08.2:** 模块导出 5 个 public functions:
  - `validate_per_slug_index(d: dict) -> None` — 8 字段 schema 校验，不合规 raise `IndexValidationError`
  - `read_per_slug_index(slug_dir: Path) -> dict | None` — 读 `<slug_dir>/index.json`，缺失 / schema 错返回 `None`
  - `write_per_slug_index(slug_dir: Path, index_data: dict, *, output_dir: Path | None = None) -> dict` — atomic write + rebuild 顶层；返回 `{"action": ..., "_topics_pending_appended": [...]}`
  - `rebuild_aggregator(output_dir: Path = Path("output")) -> dict` — 扫所有 per-slug index.json 写顶层 `.index.json`；返回 `{"slugs_included": N, "slugs_skipped": [...], "stale_detected": [...]}`
  - `read_aggregator(output_dir: Path = Path("output")) -> dict` — 读顶层 `.index.json`，返回 `{"<slug>": <per-slug-index>, ...}`；缺失返回 `{}`
- **D-08.3:** CLI handlers in `agent/tools.py`:
  - `cmd_index_write(args)` 调用 `agent.index.write_per_slug_index`
  - `cmd_index_rebuild(args)` 调用 `agent.index.rebuild_aggregator`
- **D-08.4:** Subcommand routing in `agent/tools.py:cmds dict` — 新增 keys `"index"` 走 nested subparser（`index write` / `index rebuild`）; mirror Phase 10 ship 的 `topics` 子命令模式
- **D-08.5:** 异常类 = `IndexValidationError(Exception)` 在 `agent/index.py` 顶部定义；`agent.topics.read_topics` import 走 stable contract（Phase 10 ship）

### FileLock Serialization (D-09)

- **D-09.1:** 锁文件路径 = `output/.index.lock`（mirror v1.1 Phase 08 `output/.glossary.lock` + Phase 10 `output/.topics.lock`）
- **D-09.2:** 复用 `agent/_lock.py:FileLock` 模式（v1.0 Phase 06 ship）— stale-PID detection 自动接管
- **D-09.3:** 锁住的操作 = 任何对 `output/.index.json` 的写（`write_per_slug_index` 内部触发的 rebuild + 显式 `rebuild_aggregator` 调用）+ 跨多 per-slug index.json 写（不会发生在 Phase 11，但 Phase 12 backfill 可能并行）
- **D-09.4:** 不锁 read（`read_per_slug_index` / `read_aggregator`）— 跨终端并行读不需要串行化
- **D-09.5:** Lock 域分离 — `.topics.lock` 和 `.index.lock` 是独立锁；同时持锁正常（一个写 _topics.md 一个写 .index.json，文件不冲突）

### K5 Boundary Static Assertion (D-10)

- **D-10.1:** `tests/test_k5_emitters.py` 已有 17 K5 boundary tests（v1.1 + Phase 10 ship）— 加 3 条 new test 给 `cmd_index_write/rebuild` + `agent/index.py` 模块：
  - `test_K5_module_index_no_summary_writes` — `inspect.getsource(agent.index)` 不含 literal `summary.md` / `plan.md` / `paragraphs.json` / `segs.json` / `meta.json`（5 D-29 核心文件）
  - `test_K5_cmd_index_write_no_d29_writes` — `cmd_index_write` 整个函数源码不含上述 5 D-29 核心文件 literal
  - `test_K5_cmd_index_rebuild_read_only_per_slug` — `cmd_index_rebuild` 函数源码不含 D-29 5 文件 literal AND 不含写 `output/<slug>/index.json` 模式（rebuild 只读 per-slug，写顶层）
- **D-10.2:** 注意 `index.json` literal 是合法的 — 它是 Phase 11 的 own write target；D-29 5 文件 literal 才是 K5 边界违规
- **D-10.3:** `agent/topics.py` 已 ship 的 K5 测试不动（Phase 10 ship 的 4 测试保留）

### Out of Scope for Phase 11 (Reaffirmation)

- 17 archives backfill — Phase 12 KB-12（用 `index write --from-stdin` 一条条写；本 phase 只 ship CLI + generator）
- CLAUDE.md 推荐 prompt rule — Phase 12 KB-14（推荐入口；本 phase 只加 Phase 7.6 hook 段）
- search/list CLI — Phase 12 KB-MISC-01
- topics auto-resolve / orphan 自动清理 — 永久 Out of Scope per D-04 K5 governance

### Claude's Discretion

- `tldr_oneliner` 具体形态（语气 / 句式 / 字数细节）— Claude 在 Phase 7.6 hook 中实测各 mode 提炼，CONTEXT.md 不预设
- `chapters[]` excerpt 具体形态（chapter 内多句话取 1-2 行的策略）— Claude 多模态读 summary.md 决定
- `_glossary.md` H2 anchor 解析 regex 细节（是否 trim 注解部分 / 是否区分大小写）— Claude 实现时选自然形态，acceptance 是 byte-equal canonical 输出即可
- `index rebuild` stale-detection 输出 stdout 排版细节（plain text vs JSON）— Claude 选 read-friendly 默认即可，`--json` flag 强制 structured
- 顶层 `.index.json` 的 dict 顺序（按 slug 字母序 / 按 mtime 顺序）— Claude 选自然形态；测试不强约束

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v1.2 Architecture (locked decisions)
- `.planning/v1.2-CANDIDATES.md` — 9 D-XX locked decisions; D-01..D-03 (索引层架构) / D-07 (drop backlinks) / D-08 (顶层聚合自动同步) 直接 Phase 11 输入
- `.planning/REQUIREMENTS.md` §INDEX — KB-01..KB-06 atomic 要求
- `.planning/ROADMAP.md` Phase 11 — 5 success criteria with byte-level acceptance

### Phase 10 Contract (just shipped)
- `agent/topics.py` (Phase 10 ship) — `read_topics(topics_path)` / `append_pending(topics_path, name, from_slug, chapter_title, reason, *, output_dir=None, timeout=10.0)` 是稳定 import 契约
- `output/_topics.md` (Phase 10 ship) — Approved Taxonomy 5 categories / 19 leaves / 24 nodes 是白名单源数据
- `.planning/phases/10-topic-taxonomy-governance-bootstrap-cli/10-01-SUMMARY.md` — agent.topics API surface verbatim

### v1.1 Patterns (reuse)
- `agent/_glossary.py` (v1.1 Phase 08 TEACH-A3) — atomic write + FileLock pattern reference
- `output/_glossary.md` — H2 anchor source for keyword reuse (D-06)
- `agent/_lock.py:FileLock` (v1.0 Phase 06) — reuse for `output/.index.lock`
- `tests/test_k5_emitters.py` — extend with 3 new tests per D-10.1

### CLI Routing
- `agent/tools.py` `cmds` dict — nested subparser pattern from Phase 10 ship `topics` 子命令；本 phase 加 `index write` / `index rebuild`

### `/summarize-video` Workflow
- `CLAUDE.md` `## /summarize-video 完整工作流` 段（v1.0 Phase 5 + v1.1 Phase 08/09 ship）— 本 phase 加 Phase 7.6 子步骤
- v1.1 Phase 08 ship 的 `## v1.1 自适应教学文档增强` H2 段 — Phase 11 加 `## v1.2 知识库索引层` H2 段（mirror byte-locked rule format）

### Codebase Maps
- `.planning/codebase/CONVENTIONS.md` — Python conventions (snake_case, dataclasses, atomic write, FileLock)
- `.planning/codebase/STRUCTURE.md` — `agent/` 模块 layout
- `.planning/codebase/STACK.md` — stdlib-only stack

### D-29 Replay
- `scripts/replay_v10_archives.py` (v1.1 Phase 07 ship) — Phase 11 close 前必跑

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`agent/topics.py:read_topics`** — Phase 10 ship；返回 `{"approved": [...], "pending": [...]}`；Phase 11 generator 用 `read_topics(Path("output/_topics.md"))["approved"]` 拿白名单
- **`agent/topics.py:append_pending`** — Phase 10 ship；Phase 11 generator 在遇到 `pending: <name>` topic 时调用
- **`agent/_lock.py:FileLock`** — Phase 06 ship；reuse 为 `output/.index.lock`
- **`agent/_glossary.py`** — atomic write 模式参考；`agent/index.py` 复用相同模式
- **`agent/tools.py:cmd_topics_*`** — nested subparser pattern；`cmd_index_*` 克隆相同形态
- **`tests/test_k5_emitters.py`** — `inspect.getsource()` static-grep 模式；3 个新 test 跟 v1.1 + Phase 10 17 个已有 test 一致

### Established Patterns

- **Atomic write** — `tempfile.NamedTemporaryFile + os.fsync + os.replace`（v1.0 Phase 02 ship）
- **JSON stdout** — `cmd_index_write/rebuild` 输出 JSON 给 Claude consumption
- **State events** — Phase 11 不需要 state.jsonl 事件（index.json 不是 per-slug `/summarize-video` 阶段；rebuild / write 都是 ad-hoc 触发或 Phase 7.6 hook 的同步操作；不需要 resume）
- **Slug-prefix log lines** — `cmd_index_write` 加 `[<slug>] index_write: ...`（mirror v1.0 Phase 06 PARA-04）；`cmd_index_rebuild` 不加前缀（跨 slug 操作）

### Integration Points

- **CLAUDE.md `/summarize-video` 工作流** — Phase 7.6 hook 段加在 Phase 7.5 verifier 之后、Phase 8 cleanup 之前；详见 D-02
- **CLI subcommand entry** — `agent/tools.py:cmds` dict 加 `"index"` key + nested subparser
- **Phase 12 dependency** — Phase 12 backfill 复用 `agent.index.write_per_slug_index`（外加 `--force` flag 跳过白名单严格校验，per D-05.7）
- **Phase 10 contract** — `from agent.topics import read_topics, append_pending` 必须保持稳定（Phase 10 ship 已 verify）

</code_context>

<specifics>
## Specific Ideas

- **Per-slug index.json 范例**：
  ```json
  {
    "slug": "BV132wizyEEB",
    "title": "1 分钟搞定全套像素风游戏美术：AI 绘画 + 自动抠图全流程",
    "duration_s": 74.0,
    "mode": "replicate-guide",
    "topics": ["AI-Art-Generation", "Pixel-Art", "Nano-Banana"],
    "keywords": ["topdown 视角", "像素风", "Gemini image-edit", "纯色背景抠图"],
    "tldr_oneliner": "用 Gemini image-edit 生成像素风场景 + 提取物件的 4 步流程",
    "chapters": [
      {"title": "用 Gemini 生成像素风场景地图", "start": 6.0, "excerpt": "明确指定'像素场景画师'角色 + 'topdown 俯视视角' + 全景像素风约束"},
      {"title": "迭代修改场景细节", "start": 19.0, "excerpt": "禁止 AI 改动其他区域：'其余地方禁止改变'"},
      {"title": "提取场景中的物品素材", "start": 33.0, "excerpt": "用纯色背景填充，便于抠图"},
      {"title": "导入 Godot 引擎", "start": 62.0, "excerpt": "AI 素材直接进游戏引擎"}
    ]
  }
  ```

- **顶层 `output/.index.json` 范例**：
  ```json
  {
    "BV132wizyEEB": { ... per-slug index.json verbatim ... },
    "douyin_karpathy_llm_wiki": { ... },
    "godot_brave": { ... },
    ...
  }
  ```

- **`index write --from-stdin` JSON shape** = per-slug index.json 8 字段 verbatim（不需要 wrapping object）；CLI 会 inject `slug` 字段如果 stdin 没带（防 typo）

- **Phase 7.6 hook CLAUDE.md 加段** = mirror v1.1 Phase 08 ship 的 `## v1.1 自适应教学文档增强` H2 byte-locked 写法：
  ```markdown
  ### Phase 7.6: 知识库索引（v1.2 ship 后默认启用）

  > **v1.2 hook (默认)**：满足以下全部 3 条才走 Phase 7.6（Claude is decider）：
  > 1. `output/_topics.md` 存在（v1.2 Phase 10 ship 后默认存在）
  > 2. `output/<slug>/summary.md` 已写完（Phase 7 完成 + Phase 7.5 verifier 已通过）
  > 3. `output/<slug>/index.json` 不存在 OR 用户显式要求重新生成

  **Phase 7.6 步骤**（按顺序）：

  1. **Read 5 个文件**: `output/<slug>/summary.md` / `output/<slug>/meta.json` / `output/<slug>/plan.md` / `output/_glossary.md` / `output/_topics.md`
  2. **推断 8 字段** (slug/title/duration_s/mode/topics/keywords/tldr_oneliner/chapters):
     - `topics` 必须从 `_topics.md` Approved 段选；不合适 → 用 `pending: <new-name>` 形态（CLI 会自动 append 到 Pending）
     - `keywords` 优先复用 `_glossary.md` H2 anchors 的 canonical 形式
  3. **Pipe JSON 给 CLI**:
     ```bash
     python -m agent.tools index write --slug <slug> --from-stdin <<EOF
     {"slug": "<slug>", "title": "...", "duration_s": ..., "mode": "...", "topics": [...], "keywords": [...], "tldr_oneliner": "...", "chapters": [...]}
     EOF
     ```
  4. **CLI 自动**: 验证 schema → 写 `output/<slug>/index.json` → rebuild 顶层 `output/.index.json` → 输出 JSON `{"action": "written", ...}`
  ```

- **`index rebuild` stale detection 输出范例**:
  ```json
  {
    "action": "rebuilt",
    "slugs_included": 18,
    "slugs_skipped": [{"slug": "BV1xxx", "reason": "schema invalid: missing field 'tldr_oneliner'"}],
    "stale_detected": ["BV1yyy"],
    "_index_path": "output/.index.json"
  }
  ```

</specifics>

<deferred>
## Deferred Ideas

- **Per-slug index.json schema 版本化**（添加 `version: 1` 字段 + migration 工具）— Phase 11 v1 schema 锁；如果 v1.3+ 需要加字段再考虑 versioning。当前仅 8 字段 fixed schema。
- **`index search` / `index list` CLI** — Phase 12 KB-MISC-01；Phase 11 不 ship
- **顶层 `.index.json` 增量 rebuild**（只更新变化的 slug）— Phase 11 全量 rebuild 即可（5-10 KB 体积，全量 << 1ms 写）；增量 v1.3+ if scale > 100 slugs
- **`/summarize-video` 工作流可选 disable Phase 7.6 hook 的 marker**（mirror v1.1 `.v11_features.json` opt-in 模式）— Phase 11 默认全开（v1.2 没有 archive byte-equal 包袱，因为 index.json 是新 sidecar）。如果用户特殊场景需要 disable，可未来加 `.v12_features.json` opt-out marker
- **顶层 .index.json 体积超过 50 KB 时的 split 策略** — 当前 23 条 ≈ 5-10 KB；scale 到 200+ 条才需要 split。v1.3+ 处理
- **per-slug index.json 命名规范化** — 完全独立的 v1.3+ rename 工具（如果 user 想把所有 slug 改成统一 prefix）

</deferred>

---

*Phase: 11-per-slug-index-json-aggregator-phase76-hook*
*Context gathered: 2026-05-04*
