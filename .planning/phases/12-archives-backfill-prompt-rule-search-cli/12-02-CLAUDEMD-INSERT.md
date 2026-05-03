# Plan 12-02 Task 2 — CLAUDE.md insertion content (auxiliary file)

This file contains the EXACT byte-equal content that Plan 12-02 Task 2 must insert
into CLAUDE.md. The executor should `Read` this file in its entirety, then use the
content between the two `<<< INSERTION BEGIN >>>` and `<<< INSERTION END >>>`
markers as the `new_string` argument to the `Edit` tool. The marker lines
themselves MUST NOT be inserted — they only delimit the byte-equal content for
this auxiliary file.

This file is split out of `12-02-PLAN.md` because the embedded markdown contains
literal `---` HR separators which collide with the frontmatter parser regex in
`get-shit-done/bin/lib/frontmatter.cjs` line 48. Keeping the example here lets
Plan 12-02 stay parseable while preserving byte-equal fidelity for the
executor.

## Edit tool arguments

`old_string` is the EXACT 3-line anchor currently in CLAUDE.md immediately
before the `## /summarize-video 完整工作流` H2 (verify by grep against
CLAUDE.md before editing — line numbers may shift):

The `old_string` is the 3-line sequence formed by:
1. one literal `---` HR line
2. one blank line
3. the line `## /summarize-video 完整工作流`

`new_string` is everything between the two `<<< ... >>>` markers below.

## new_string content (verbatim — between markers, NOT including markers)

<<< INSERTION BEGIN >>>
___HR___

## v1.2 知识库自然语言推荐入口

> 这一节是 v1.2 知识库 milestone 的查询入口契约。当用户提以下意图时，Claude FIRST ACTION 读 `output/.index.json` 给出推荐。**触发 phrase 锁定 + 推荐格式锁 + anti-hallucination 锁** 三层保证一致体验。

### 触发 phrase 锁

用户消息中**明确包含**以下任一 phrase（byte-equal literal）→ 走推荐入口：

- '推荐'
- '相关'
- '我之前看过'
- '学过'
- '找一下我'
- '哪些视频'
- '类似查询意图'

仅当用户的查询意图**清楚指向**「在已总结的视频里找一些跟 X 主题/概念相关的内容」时触发；如果用户在讨论代码 / 主动问别的问题且只是顺带说"推荐"，不要强行匹配（per K2: Claude is decider）。

### FIRST ACTION

接到推荐意图 → 立即调用 `Read output/.index.json`（不要先 grep / 不要先问澄清；先 Read）。

- **文件存在**：解析 JSON dict，每个 key 是 slug，value 是 per-slug 8 字段索引（`slug / title / duration_s / mode / topics[] / keywords[] / tldr_oneliner / chapters[]`）。
- **文件不存在**：回复用户："索引未生成，请先跑 `python -m agent.tools index rebuild`"——不要尝试编造或扫 output/ 重建索引（rebuild 是 user 决策的恢复动作）。

### 推荐回复格式锁

返回 top-N（默认 N=3）推荐，每条**严格 3 行**结构（mirror v1.1 5th format-spec invariant 字面规则）：

- **第 1 行**：`**<slug>**: <title> — 共享 <匹配信号: keyword/topic>`
- **第 2 行**：`> <tldr_oneliner>`（blockquote 包裹 1 行）
- **第 3 行（可选）**：1-3 个 chapter 入口形如 `[HH:MM:SS] <chapter title>`，逗号分隔

匹配信号选择：从 `.index.json` 中拿到匹配命中的字段（比如 query 命中了 `topics: ["LLM-Wiki"]` → 写"共享 LLM-Wiki topic"；命中 `keywords: ["Karpathy"]` → 写"共享 Karpathy keyword"）。一条推荐可以有多个匹配信号合并写。

### Byte-equal example

用户："推荐学习 LLM Wiki 范式相关的视频"

Claude（先 Read output/.index.json，然后）：

```text
根据知识库匹配到 top-3 相关视频：

**douyin_karpathy_llm_wiki**: Karpathy 又被吹爆，但这次可能真不是炒作 — 共享 LLM-Wiki / RAG topics
> 75 行 Python gist 实现「个人知识库 = LLM 编译知识」的范式
- [00:00:18] Karpathy: "Every query is rediscovering knowledge."
- [00:01:25] 新员工 vs 图书管理员的比方
- [00:03:42] LLM 终于补上 Memex 缺失的「维护者」角色
```

### Anti-hallucination FORBIDDEN list

- **FORBIDDEN** 推荐 `output/.index.json` 中**不存在**的 slug（编造 slug = 致命错误，违反 v1.1 5th format-spec invariant 同等严重度）
- **FORBIDDEN** 编造视频内容 — `tldr_oneliner` / `keywords` / `chapters` / `title` 必须 byte-equal 来自 `.index.json`，不允许"提炼"或"改写"再展示给用户
- **FORBIDDEN** 修改 `summary.md` / `meta.json` / `paragraphs.json` / `segs.json`（D-29 invariant — 4 个 v1.0/v1.1 ship 后字节冻结的 archive 文件）
- **FORBIDDEN** 在推荐回复中加 `<thinking>` reasoning 段（直接给推荐；用户要看结果不看推理过程；如果用户后续问"为什么是这 3 条"再展开）
- **FORBIDDEN** 一次返回多于 N=5 条推荐（信息过载；如果用户说"列全部" / "show me everything"才允许 N>5；默认 N=3）
- **FORBIDDEN** 跳过 FIRST ACTION (Read output/.index.json) 直接根据 CLAUDE.md 上下文里能想到的 slug 编推荐——必须 Read 一次 .index.json，因为它是唯一权威源

如果 `.index.json` 中找不到与查询意图匹配的任何 slug → 直接告诉用户「在已总结的 N 个视频里没找到与「<query>」直接相关的内容；最接近的是 <slug>（共享 <weak signal>），但跟你想找的可能不太对路」。**不要硬凑无关推荐**。

___HR___

<<< INSERTION END >>>

## CRITICAL: ___HR___ token replacement

Before passing the content above to `Edit` as `new_string`, you MUST replace
EVERY occurrence of the literal token `___HR___` with a literal three-hyphen
markdown HR (`---`). The auxiliary file uses `___HR___` instead of bare `---`
to avoid frontmatter-parser collision in this auxiliary file's host directory.

There are exactly 2 occurrences of `___HR___` in the marker-delimited content
above:
- One immediately after `<<< INSERTION BEGIN >>>` and one blank line
- One immediately before the blank line + `<<< INSERTION END >>>`

Both MUST be replaced with `---` (three hyphens) before the Edit call.

Verification check after substitution: the final `new_string` should start
with a newline + `---` + newline + blank + `## v1.2 ...`, and end with `---`
+ newline + (something — depending on whether you're including the
`## /summarize-video 完整工作流` anchor in old_string, the new_string ends
with `---\n\n## /summarize-video 完整工作流`).

The clean way to do the Edit:
- `old_string` = 3 lines: `---`, blank line, `## /summarize-video 完整工作流`
- `new_string` = (the substituted content above) + `---` + blank line + `## /summarize-video 完整工作流`

This way the trailing `---` of the new H2 section becomes the separator
before `## /summarize-video 完整工作流`, and the existing top `---` (which
was the separator after `## v1.1 校对自动化`) is preserved as the separator
INTRODUCING the new `## v1.2 ...` H2 section.
