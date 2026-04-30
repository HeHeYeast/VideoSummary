# Phase 1: Preflight & Regression Baseline - Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

在任何特性 phase 改动 schema / encoding / artifact 路径之前，把 17 条已归档视频的「重跑路径」+ `meta.json` / `segs.json` / `paragraphs.json` 的「schema 形状」冻结成可复现的回归基准。这是 PRE-01..PRE-05 的合订实现，是后续 5 个 phase 的安全网；本 phase 不引入任何新功能、不改任何用户路径。

</domain>

<decisions>
## Implementation Decisions

### Baseline 视频选择 (PRE-01)
- **D-01:** 三条基准视频锁定为 `BV132wizyEEB`（AI 美术工作流 — 代码/工作流类）+ `BV1C9QCBdE1U`（Godot 教程：伤害数字生成器 — Godot/代码密集类）+ `douyin_trae_ai`（TRAE AI 第二大脑 — AI/UI 演示类），覆盖 milestone 三大目标视频形态。
- **D-02:** **`BV1C9QCBdE1U` 替换掉 ROADMAP 原本提名的 `godot_brave`** — `output/godot_brave/` 实际只剩 `cookies.txt`，没有可冻结的 `summary.md` / 三件套 JSON。`BV1C9QCBdE1U` 是「Godot 教程：伤害数字生成器（暴击变色、随机漂浮、可复用）」，有完整 SMTPF 工件，且代码密集度比纯演示类视频更适合做代码抄录质量的回归。

### schema_version 追加策略 (PRE-03)
- **D-03:** 采用 **loader-only 容忍** 方案 — **不修改任何已有 `output/<slug>/` 文件**。所有 17 条历史归档保持现状不动。
- **D-04:** loader 行为：读到 `dict` 类型工件时取 `obj.get("schema_version", 1)`，读到 `list` 类型工件时一律视为 `schema_version=1`（因为 `segs.json` / `paragraphs.json` 都是顶层 list，把它们改为 `{"schema_version":..., "items":[...]}` 包装即破坏向后兼容，违反 PROJECT.md K3）。
- **D-05:** 「retroactive 文档化」交付物是一段 `docs/schema-versions.md`（或在 CLAUDE.md/AGENT_DESIGN.md 内嵌一节，由 planner 决定具体落点），用文字记录三类工件 v1 的字段集合，作为后续 v2 升级的对照基准。
- **D-06:** 当未来确实需要 v2 schema 时，迁移代价由那个 phase 承担（包括是否做 wrapping、是否写 migration script），本 phase 只准备好 loader 接口与文档锚点。

### 回归 diff 验证方法 (PRE-02)
- **D-07:** 使用 **Claude 手工 eyeball diff** 作为回归验证方法 — 不写任何自动化断言脚本、不算结构化指纹、不做 md5 严格哈希。
- **D-08:** runbook (`tests/regression/regression-check.md`) 列出三步：(1) `git checkout` 某个 commit / branch；(2) 把 `tests/regression/<slug>/` 拷贝进 `output/<slug>/`，**只覆盖 JSON 三件套**（避免重新下载 30-200MB video.mp4），运行需要验证的 stage；(3) Claude `Read` 新生成的 `summary.md` 与 `tests/regression/<slug>/summary.md` 做语义对比。
- **D-09:** 「通过」标准是 Claude 判断「无 surprise drift」— 允许有意改进（更精确的代码抄录、更紧凑的章节），不允许结构、时间戳、章节数发生未声明的变化。哪怕 Phase 5 之后 prose 风格升级，runbook 也只要求「能解释每一处差异」，不要求字节级一致。
- **D-10:** 每次后续 phase merge 之前，跑 3 条基准（人工触发，不进 CI），把通过情况写在那个 phase 的 VERIFICATION.md 里。

### 冻结范围 (PRE-01)
- **D-11:** `tests/regression/<slug>/` 下提交 **`summary.md` + `meta.json` + `segs.json` + `paragraphs.json`** 四件，**不**提交 `frames/` / `audio.wav` / `video.mp4` / `video.info.json`。理由：四件都是 stable JSON / Markdown 文本，~200-500KB/视频，3 条 ≈ 1MB；frames/audio/video 体积超 git 友好范围（git LFS 不在 ¥0 工具栈内）。
- **D-12:** 三个 slug 的实际目录命名 `tests/regression/BV132wizyEEB/`、`tests/regression/BV1C9QCBdE1U/`、`tests/regression/douyin_trae_ai/`，与 `output/<slug>/` 子目录约定 1:1 映射，runbook 的 copy 命令直接 `cp -r tests/regression/<slug>/* output/<slug>/` 即可。
- **D-13:** 冻结这一步只跑一次（在本 phase 内），后续 phase 通过 `--force` 重跑各 stage 验证，但 `tests/regression/` 内的快照在本 milestone 内**不更新**。如果某 phase 真的改进了 prose 质量并希望把新版作为新基线，那个 phase 自己负责更新 snapshot 并在 commit message 中解释 drift 原因。

### Encoding 审计 (PRE-04)
- **D-14:** 审计范围 = `agent/` + `src/` 全部 `.py` 文件。已先行扫描确认现状：30+ 处 `read_text` / `write_text` 全部带 `encoding="utf-8"`；唯三的「裸 open」是 (a) `agent/douyin_downloader.py:194` 的 `open(video_path, "wb")`（二进制 video 写入，不需要 encoding）、(b) `agent/embed.py:79` `PILImage.open(p)`（PIL 自处理）、(c) `agent/frames_v2.py:74` `Image.open(f.path)`（PIL）— 三处都是正确的，**PRE-04 实际工作量约 0**。
- **D-15:** 即便如此，本 phase 仍要正式提交一份「audit pass」证据 — 一段 `tests/regression/encoding-audit.md`（或附在 regression-check.md 末尾）记录 grep 命令 + 输出，作为后续 phase 改 I/O 时的对照锚点。
- **D-16:** 审计**包括** v2 模块（`frames_v2.py`、`pass1_classify.py`、`embed.py`、`frame_store.py`、`prepare.py`），尽管它们不在主 ¥0 路径上，但仍可被 import；防止后续 phase 误用导致编码问题。

### Windows zh-CN 设置文档化 (PRE-05)
- **D-17:** 在 `CLAUDE.md` 「环境变量」节之上或之后，新增一小节「Windows zh-CN 终端设置」，给出两条命令：
  - `chcp 65001`（每个 terminal session 跑一次）
  - 设置 `PYTHONUTF8=1` 环境变量（一次性，全局）
- **D-18:** 文档措辞为「推荐而非必需」— 现有 `agent/tools.py:59` 的 `ensure_ascii=True` 兜底逻辑保留不动，老路径仍要在没设置 codepage 的情况下能跑通。这条新文档主要为 Phase 3 (YouTube/local mp4) 预留干净环境基线。

### Claude's Discretion
以下细节由 planner / executor 自行决定，user 不在乎：
- `tests/regression/` 是放在 repo 根目录（`tests/regression/`）还是 `.planning/regression/` — 倾向 repo 根（标准约定，`tests/` 是 Python 项目最常见路径）
- `regression-check.md` 是 Markdown 还是带 fenced shell 的复制粘贴 runbook — 凭 planner 判断
- loader-tolerance 改动究竟落在哪些文件里（`src/asr.py` 的 `parse_vtt`？`agent/asr_v2.py` 的 paragraphs 加载？还是新建一个 `agent/io.py` 集中处理？）— planner 决定，但要保持「轻接口」原则，不引入新依赖
- encoding-audit 证据是单文件还是 inline 在 regression-check.md — 凭 planner 判断
- `docs/schema-versions.md` 还是嵌入 CLAUDE.md / AGENT_DESIGN.md — 凭 planner 判断，但必须有一处可被 grep 到的「v1 字段集合」记录

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级约束
- `.planning/PROJECT.md` — Core Value、Out of Scope、Key Decisions（特别是 K3 backward-compat 是本 phase 的硬约束源头）
- `.planning/REQUIREMENTS.md` §"PRE — Preflight & Regression Baseline" — PRE-01..PRE-05 的需求原文与可测条件
- `.planning/ROADMAP.md` §"Phase 1: Preflight & Regression Baseline" — 4 条 Success Criteria（必须保持 TRUE）
- `CLAUDE.md` — 当前 ¥0 工作流文档；PRE-05 直接修改这份文件

### 代码地图（必读，已是 ground truth）
- `.planning/codebase/ARCHITECTURE.md` §"Artifact Layer" / §"Data Flow" — `output/<slug>/` 目录约定与 stage 工件之间的关系（loader-tolerance 实现的关键背景）
- `.planning/codebase/CONVENTIONS.md` §"I/O & Path Conventions" — `encoding="utf-8"` 强制约定、JSON 读写 idiom、frame 命名规则
- `.planning/codebase/STRUCTURE.md` — `agent/` 与 `src/` 双层结构与共享模块（`src.download` / `src.asr`），影响 PRE-04 审计范围
- `.planning/codebase/CONCERNS.md` §1.4（GBK 终端）、§5.4（cache 验证）— 与 PRE-04 / PRE-05 直接相关的现存问题

### 风险与陷阱（必读，本 phase 直接对应）
- `.planning/research/PITFALLS.md` §U1 「YOLO 模式跳过验证」— 这条 pitfall 直接对应 PRE-01；本 phase 是它的前置闸门
- `.planning/research/PITFALLS.md` §U2 「17-video legacy queue 兼容性回归」— 本 phase 的根本动机
- `.planning/research/PITFALLS.md` §U3 「Windows zh-CN 编码 / proxy / locale」— PRE-04 / PRE-05 的依据
- `.planning/research/PITFALLS.md` §P7.4 「Schema drift between runs」— PRE-03 schema_version 设计依据
- `.planning/research/PITFALLS.md` §"Pitfall-to-Phase Mapping" 表 — 把 U1/U2/U3 标记为本 phase 的 prevention 来源
- `.planning/research/SUMMARY.md` — 6-phase 推荐结构与排序理由（本 phase 是 gating preflight）

### 实际基准视频（D-01 选定）
- `output/BV132wizyEEB/` — 完整 SMTPF；标题「【独立开发福音】1分钟搞定全套像素风游戏美术！AI绘画+自动抠图全流程」（AI 工作流 / 代码混合）
- `output/BV1C9QCBdE1U/` — 完整 SMTPF；标题「【Godot教程】伤害数字生成器：暴击变色、随机漂浮、可复用，一看就会」（Godot / 代码密集）
- `output/douyin_trae_ai/` — 完整 SMTPF；标题「搭建全网千万收藏的 AI 第二大脑，3分钟教会你！ #TRAE #TRAESOLO #AI新星计划」（AI / UI 演示）

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/tools.py:75-81` — `--force` flag pattern（cache check + override）；regression runbook 复用这个 idiom 来强制重跑 stage
- `agent/asr_v2.py:aggregate_paragraphs` 已是纯函数 — schema_version loader-tolerance 可作为薄包装加在调用前，不污染核心逻辑
- `src/asr.py:parse_vtt` 已经显式 `encoding="utf-8"` — 是「正确范式」的样板，loader-tolerance 改动学着写
- 现有 30+ 处 `read_text(encoding="utf-8")` / `write_text(..., ensure_ascii=False, indent=2)` 是写得最一致的 idiom，PRE-04 审计核对的就是它

### Established Patterns
- **JSON write idiom**: `path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")` — 30+ 调用点；新增任何 JSON 写都必须沿用
- **JSON read idiom**: `json.loads(path.read_text(encoding="utf-8"))` — `json.load(open(...))` 在本 codebase 里**绝不出现**
- **二进制 open 例外**: `open(path, "wb")` / `open(path, "rb")` 不要 `encoding=` — 这是正确做法，不需「修复」
- **Cache pattern**: `if path.exists() and not args.force: load else compute+write` — PRE-03 schema 容忍逻辑插在 load 这一步
- **CLI handler 命名**: `cmd_<subcommand>`，dispatch 通过字典 — 如有 doctor / regression 子命令需要新增，沿用此 pattern
- **路径处理**: `pathlib.Path` 全程，`os.path` 不出现；新增代码必须沿用

### Integration Points
- **CLAUDE.md** — PRE-05 直接修改，新增「Windows zh-CN 终端设置」节；PRE-03 schema_version 文档化也可能落在这里
- **Loader 入口** — 现状 loader 散落在 `agent/tools.py:75,77,94`、`src/pipeline.py:34,46`、`agent/prepare.py:77,92,114`；planner 需决定是集中到一个新模块还是 in-place patch（推荐集中，便于后续 v2 迁移）
- **`tests/` 目录** — 当前**不存在**（参见 `.planning/codebase/TESTING.md`「No `tests/` or `test/` directory」），本 phase 是项目历史上首次创建 `tests/`
- **`docs/`** — 当前不存在；如果选 `docs/schema-versions.md`，本 phase 也会首次创建 `docs/`（也可选 `tests/regression/schema-versions.md` 共用一个目录）
- **`.gitignore`** — `output/` 已 gitignored；`tests/regression/` 不应被 ignore，需检查 `.gitignore` 不包含 `tests/` 通配

### 编码审计当前状态（已扫）
- `agent/` 5 个核心模块：100% 合规
- `src/` 9 个模块：100% 合规
- 二进制 open（PIL Image / video write）：3 处，全部正确
- **PRE-04 实际工作量预测：写一份 audit-pass 证据文件，可能修零行代码**

</code_context>

<specifics>
## Specific Ideas

- 用户多次强调「快速回退到当前方案」是 milestone 级承诺；本 phase 是这个承诺的物质形态。不要把它做成「形式合规」的伪基准（比如只 commit 一份 README 写「已审计」却不附实际可运行 runbook）。
- 用户对 PRE-04 「encoding 审计」预期不高 — 已经先行 grep 过；提交一份 audit pass 证据即可，无需为合规而合规去重写正确的代码。
- 「Claude 是唯一决策者」延续到回归验证：不要写自动化断言或 CI 钩子；runbook 是给「Claude + user 一起读」的，不是给 GitHub Actions 跑的。

</specifics>

<deferred>
## Deferred Ideas

- **结构化回归脚本**（`verify_baseline.py` 算 line/frame/section count）— 推迟到证据显示手工 eyeball diff 不够用之后；可能永远不需要
- **`tests/regression/` snapshot 自动更新机制**（PR 触发时 diff、强制人工 ack）— 本 milestone 内人工触发足够；如果 milestone 2 引入持续 CI，再考虑
- **GoldenStorm / pytest-regressions 等 fixture 框架** — 不引入；与 ¥0 + 「Claude 是 verifier」哲学不符
- **Frame-level 回归（验证抽帧确定性）** — `output/<slug>/frames/` 不进 git；如果未来发现 frame extraction 出现漂移，再考虑增量记录 frame 数 + 文件名集合作为 metadata
- **schema_version v2 真实迁移代码** — 等到第一个真正想升级 schema 的 phase 来承担；本 phase 只准备 loader 接口与文档锚点

</deferred>

---

*Phase: 01-preflight-regression-baseline*
*Context gathered: 2026-04-30*
