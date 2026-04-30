# Phase 2: Resume Infrastructure & Cache Correctness - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning
**Decision authority:** Claude 自决 — user 表态本 phase 属"基础设施边缘 phase"，不介入灰色决策（"合理即可"）。所有决策由 Claude 基于 PROJECT.md / Phase 1 决策 / 代码地图推导，planner & executor 可按需在合理范围内偏离，但偏离需在 PLAN.md / SUMMARY.md 中说明理由。

<domain>
## Phase Boundary

让 `output/<slug>/` 下每一个 artifact（meta.json / segs.json / paragraphs.json，未来还有 schedule.json / state.jsonl 等）满足三个性质：(1) **参数感知** — 参数变化触发明确重生而非静默复用过期产物；(2) **原子写** — 中途崩溃永远只看到旧版或新版完整文件，不会留半截 JSON；(3) **可恢复** — 任意阶段失败后重跑能跳过已完成步骤。同时**严格保持 17 条已归档视频的"快速回退"承诺**：archived 目录无 sidecar / 无 state.jsonl 时一律走 file-existence 老路径。

本 phase 不引入任何 user-visible feature，是 Phase 3-5 的 enabler — Phase 3 (SRC 多输入源) / Phase 4 (FPS schedule) / Phase 5 (TEACH profile=podcast) 都需要"换参数→自动重生"这条契约。

</domain>

<decisions>
## Implementation Decisions

### 归档兼容策略 — 这是 Phase 2 最关键的决策（RES-02 / RES-06）
- **D-01:** loader 看到 artifact 存在但**无 `<artifact>.params.json` sidecar**时，**不自动重生**，但**打 loud warning**：`log.warning("no params.json for %s; cannot validate cache freshness — pass --force to regenerate with sidecar capture", path)`，然后走原有 file-existence 老路径返回缓存。理由：17 archive 重跑零摩擦是 PROJECT.md K3 硬约束 + Phase 1 D-03 已锁定，强制重生会破坏 30-200MB video.mp4 + 长 ASR 的成本；视为静默匹配则永久遮蔽 P7.1 stale-reuse 隐患。loud + 不重生 = 既不破坏历史，又留可见信号，主动 `--force` 时即补写 sidecar。
- **D-02:** loader 看到 artifact 存在 + sidecar 存在但**字段不匹配**时，**强制重生 + 打 loud line**：`log.warning("regenerating %s because: %s changed %r -> %r", artifact, field, old, new)`（直接对应 RES-02 success criterion 的字面契约），重生后写新 sidecar。多字段不匹配时一行一字段；`--force` 同样触发重生但日志措辞改为 "forced regeneration"。
- **D-03:** state.jsonl 缺失或损坏时**降级到 D-01 的 file-existence cache 路径**（RES-06）。损坏检测 = 任一行 JSON parse 失败；触发后 log.warning 一次 + 当 session 内**不再读 state.jsonl**（避免 spam），但仍正常 append 后续事件。**绝不**自动 truncate / 删除 / "修复" state.jsonl —— 用户的损坏文件就是诊断信息。
- **D-04:** Phase 2 落地后**新写入**的 artifact 一律带 sidecar；archive 在用户主动 `--force` 重跑前永远是"无 sidecar 状态"，doctor 子命令的输出会清晰标注这种状态（详见 D-15）。

### params.json sidecar 字段范围（RES-01）
- **D-05:** 每个 artifact 的 sidecar 记录三类字段：(a) **CLI flag** — 用户命令行直接传的 (`--whisper`, `--gap`, `--profile` (Phase 5 引入))；(b) **函数级语义参数** — 影响输出但未必走 CLI 的 (`language=None`, `gap_threshold`, `max_para_duration`, `sentence_gap` 等 `aggregate_paragraphs` 默认值，VAD `min_silence_duration_ms` 等 `transcribe` 内部参数)；(c) **关键工具版本** — `faster_whisper.__version__`、`ffmpeg -version` 第一行的 version 字符串（正则提取，避免抓 build hash 引发伪 churn）。
- **D-06:** **不**记录的字段：`ASR_DEVICE`（cpu/cuda 输出语义一致，仅速度差异）、`PYTHONUTF8`、HTTP_PROXY、cookies 文件路径（与输出内容无关或会引入伪 churn）。理由：sidecar 的 truth 是"参数变了输出可能变"，不是"环境变了"；环境差异由 doctor 显示但不进 sidecar diff 触发器。
- **D-07:** sidecar 三类字段在 sidecar JSON 内**分组**，便于 `derived_state` 与 doctor 区分等级 — `{"cli": {...}, "func": {...}, "tools": {...}, "captured_at": <iso8601>, "schema_version": 1}`。`tools` 不匹配时打 warning 但不强制重生（用户可决定是否 `--force`）；`cli` / `func` 不匹配则严格触发重生。理由：whisper 大版本变可能改变结果但不一定（faster-whisper minor patch 通常等价），把这层留给用户判断比死规则合理。
- **D-08:** sidecar 物理形式：与 artifact **同目录 sibling 文件** `<artifact>.params.json`（不是嵌套 `.meta/` 目录）。理由：与 `agent/tools.py:cleanup_frames` glob 模式兼容（doctor 也走 glob）；与 frames/ 目录约定一致（per-frame 不存 sidecar，只 stage-级产物存）。

### 原子写 + Windows 重试（RES-03 / RES-04）
- **D-09:** atomic-write helper 落到 **`agent/io.py`** —— 与 Phase 1 PRE-03 的 schema 容忍 loader 同模块。函数命名 `write_json_atomic(path, obj, *, sidecar_params=None)`，签名让"写产物 + 写 sidecar"一次原子完成（要么两个文件都新、要么都旧）。理由：(a) 30+ 现有 `write_text(json.dumps(...))` 调用点逐处替换、保留 `encoding="utf-8"` + `ensure_ascii=False, indent=2` idiom；(b) 后续 phase 新增 schedule.json / state.jsonl 读写也复用此 helper；(c) 与 D-04 单点维护原则一致。
- **D-10:** 实现策略：`tempfile.NamedTemporaryFile(dir=target.parent, delete=False)` 写入 → `os.replace(tmp, target)` 提交 → sidecar 同样模式紧随。**强制 same-volume**（tempfile 用 `dir=target.parent` 即天然同卷）；如果 `target.parent` 不存在（罕见竞态），先 `mkdir(parents=True, exist_ok=True)` 再开 tempfile。失败时清理 tmp 文件（`unlink(missing_ok=True)`）但不吞异常，让上游决定。
- **D-11:** PermissionError 重试：**3 次 0.5s 线性 backoff**（直接对齐 RES-04 字面契约，不引入 exponential — Defender / OneDrive 扫描典型耗时 < 2s，线性已覆盖；exponential 反而引入"等等再试"的不确定感）。仅捕获 `PermissionError`，不扩到 `OSError`（避免遮蔽磁盘满 / 路径无效的 fail-fast 信号）。每次重试 log.info 一次（不是 warning，避免 noise）；3 次后 raise 原异常 + 加一行 hint：`原因可能是 Windows Defender / OneDrive / Search 索引短时持锁，重试 3 次后仍失败`。

### state.jsonl 设计（RES-05 / RES-06）
- **D-12:** 物理形式：**JSON Lines** 格式，文件名 `output/<slug>/state.jsonl`（**不是 state.json** — 后缀显式区分，避免 mid-write 用户用 `cat`/`Read` 看到 unclosed bracket 误以为损坏）。每行一个完整 JSON 事件，append-only，单行 corruption 可定位丢弃单行而不是整个文件。
- **D-13:** 事件 schema：`{"ts": <iso8601>, "stage": <str>, "status": "started|completed|failed", "params_hash": <str>, "details": {...optional}}`。`params_hash` = sidecar 三段拼接的 sha256 短前缀（16 hex），让 derived_state 能不读 sidecar 就判断"上次跑的就是当前参数"。`stage` 取 `download | transcribe | aggregate | extract_frames | extract_frames_batch | doctor`（doctor 只读不写，但仍记录 access 便于后续 phase 审计）。
- **D-14:** **粒度：Phase 2 day-1 只做 stage-level**；segment-级 frame 事件（如 `extract_frames_batch` 完成第 N 段）**延迟到 Phase 4** 与 `extract_frames_batch` 同 phase 引入。理由：现状 `agent/tools.py:cmd_extract_frames` 是单段调用，segment-级只在 batch 模式有意义，提前设计是 over-engineering。本 phase `derived_state(events)` reducer 只输出 `dict[stage_name, {status, last_completed_at, params_hash}]`；Phase 4 扩展 segment 事件时增 reducer 字段（schema_version 不需 bump，因为是 additive optional）。

### doctor 子命令（RES-07）
- **D-15:** 输出形式：**默认纯文本表格 + `--json` flag**（不加颜色、不加 `--diff`、不加 rich）。理由：(a) zh-CN Windows 终端颜色支持参差不齐（Phase 1 D-17 已为干净环境留位但仍是 opt-in）；(b) `--json` 为后续 phase / 用户脚本管道留口；(c) `--diff` 是 Phase 4-5 引入新 artifact 后才有意义的诊断，YAGNI。
- **D-16:** 表格列：`artifact | exists | mtime | params_hash_match | last_state` —— 五列覆盖 RES-07 的"existence、mtime、sidecar params"三项 + 加 sidecar diff 状态 + state.jsonl 视角的最后状态。`params_hash_match` 取值 `✓ / ✗ / —` (匹配 / 不匹配 / 无 sidecar)；`last_state` 取值 `completed / failed / started / —` (state.jsonl 内最后一次该 stage 的 status；无记录显 `—`)。
- **D-17:** 用法：`python -m agent.tools doctor output/<slug>`（**positional dir**，与 `cleanup_frames` 一致；不用 `--slug` flag）。`--json` 输出顶层 dict `{slug: <str>, artifacts: [{name, exists, mtime, params_hash_match, last_state, sidecar: {...}}, ...], state_log_status: "ok|missing|corrupt"}`。**只读** — 不修改任何文件，包括不补写缺失的 sidecar（补写由 D-01 的 `--force` 路径承担）。

### schema-migration runbook（RES-08）
- **D-18:** 落点：**`docs/schema-migration.md`**（首次创建 `docs/`；Phase 1 D-05 同时考虑过把 schema-versions 内容放这里）。理由：与 `docs/schema-versions.md`（Phase 1 已落 / 拟落）放同目录，未来 schema 类文档集中。备选 `tests/regression/schema-migration.md` 拒绝 — 这份文档是"未来开发参考"，不是回归测试输入。
- **D-19:** 内容深度：**中等**（1-2 页），包含三块：(a) **何时 bump** — 必填字段移除 / 字段重命名 / 字段类型变更 → 必须 bump；(b) **何时不 bump** — 添加可选字段 / 添加新 artifact 类型 → 不 bump（Phase 1 D-04 / D-05 已是先例，例如 SRC-04 给 meta.json 加 `source` 字段就不 bump）；(c) **最小可运行示例** — 用 `meta.json` 写一个伪 v1→v2 round-trip 函数（`_migrate_meta_v1_v2(obj)`），展示 `agent/io.py:load_meta` 如何插入 migration 调用而不破坏现有 call site；(d) **测试 checklist** — 每次 bump 前必须验证 17 archive 在新 loader 下仍可读取（即 Phase 1 D-08 的 regression-check 流程对 schema 升级 phase 的强制要求）。
- **D-20:** 选 `meta.json` 而非 `segs.json` 写示例 — 因为 segs.json 是顶层 list（Phase 1 D-04 已锁不可 wrap），不是好的迁移示例载体；meta.json 是 dict 天然支持 schema_version 字段，是后续真实 v2 升级最可能的第一例。

### Plans 拆分（与 ROADMAP.md 一致，3 plans）
- **D-21:** 02-01: atomic write + PermissionError 重试 + sidecar 读写 helper（D-05..11）— 落 `agent/io.py` 扩展 + 5 个 cmd_* 调用点替换。**先**做这个，因为 02-02 的 state.jsonl 读写本身也用这套 helper。
- **D-22:** 02-02: `agent/state.py` 新模块 + `state.jsonl` append + `derived_state(events)` reducer + 5 个 cmd_* 在合适时机记录事件（D-12..14）— 与 02-01 通过 io.py atomic-append helper 衔接。
- **D-23:** 02-03: `doctor` 子命令 + `docs/schema-migration.md`（D-15..20）— 最末，因为 doctor 需要 02-01 的 sidecar + 02-02 的 state.jsonl 才有完整数据展示；migration runbook 只读不依赖任何代码改动。

### Claude's Discretion (planner / executor 自由裁量)
以下细节由下游自决，不进 D-XX 列表：
- atomic-write helper 内部的 tempfile 命名前缀（建议 `.tmp.<artifact>` 但planner 可选其他）
- `params_hash` 的 sha256 是否截到 16 hex（也可 12 / 8，权衡可读性 vs 碰撞）
- doctor 表格的 ASCII 边框样式（box-drawing chars / `+---+` / 仅空格对齐均可）
- `agent/state.py` 的 reducer 是否提供 `__main__` 调试入口
- 第一次写 sidecar 时是否在 stdout 打印路径确认（可选 UX）
- 哪些 cmd_* 的内部默认值列入 sidecar 的 `func` 段（建议覆盖所有"会被 Phase 5 profile=podcast 改变"的字段，但具体清单由 planner 实测）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级约束 (硬约束源头)
- `.planning/PROJECT.md` — 特别是 Constraints §"Backward compatibility" + Key Decisions K3（17 archive 不可破坏）、K5（Claude 决策权不外移 — sidecar 不该自动 `--force` 重生 archive 就是这条原则）
- `.planning/REQUIREMENTS.md` §"RES — Resume Infrastructure & Cache Correctness" — RES-01..RES-08 全文 + Out-of-Scope 表（解释为什么不引入 step_log.json provenance）
- `.planning/ROADMAP.md` §"Phase 2: Resume Infrastructure & Cache Correctness" — 5 条 Success Criteria（必须保持 TRUE）+ Plans 拆分

### Phase 1 已锁定决策（载入式继承）
- `.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md` — 重点：D-03 / D-04（顶层 list 工件不可 wrap → params.json 必须 sidecar 路径）、D-05（agent/io.py 是 schema 容忍 loader 的统一落点 → atomic-write helper 也落这里）、D-07..D-10（Claude eyeball diff 是回归方法 → 本 phase 不引入自动化断言 / CI）、D-12（archive 子目录约定 → doctor 输入路径形态）

### 代码地图（必读，已是 ground truth）
- `.planning/codebase/ARCHITECTURE.md` §"Artifact Layer" / §"Data Flow" — `output/<slug>/` 5 个核心 artifact 与 5 个 cmd_* 写入点的映射；§"State Management" — 当前"file-existence cache"的精确语义（D-01 / D-03 的 fallback 行为锚点）
- `.planning/codebase/CONVENTIONS.md` §"I/O & Path Conventions" — `encoding="utf-8"` / `json.dumps(..., ensure_ascii=False, indent=2)` / `pathlib.Path` 三大 idiom（atomic-write helper 必须保持）；§"CLI Pattern (argparse subcommands)" — doctor 子命令注册的 cmds dict + `cmd_doctor` 命名约定
- `.planning/codebase/STRUCTURE.md` §"Where to Add New Code" — 新子命令、新模块的落点指南（agent/state.py 是新模块，agent/io.py 扩展是已有模块）
- `.planning/codebase/CONCERNS.md` §5.4（"Cache validation is 'file exists' only"，本 phase 直接消除）、§6.3（"No retries / partial-download protection"，本 phase 通过 atomic-write 部分覆盖）、§7.1（cleanup_frames 不可逆 — doctor 设计要避免再造一个不可逆 surface）

### 风险与陷阱（直接对应本 phase）
- `.planning/research/PITFALLS.md` §P7.1 「Stale-artifact silent reuse when params change」— D-05..D-07 sidecar 字段范围的设计依据；severity = showstopper
- `.planning/research/PITFALLS.md` §P7.2 「Atomic-write Windows」— D-09..D-10 实现策略的依据（明确指出 `os.replace` 是 Windows 上唯一原子原语，不是 `os.rename`）
- `.planning/research/PITFALLS.md` §P7.3 「PermissionError on Windows」— D-11 重试策略的依据（典型来源 = Defender / OneDrive / Search）
- `.planning/research/PITFALLS.md` §U3 「Windows zh-CN encoding」— Phase 1 已覆盖编码部分，本 phase 仅需保持 idiom 不引入退化
- `.planning/research/PITFALLS.md` §U4 「No provenance on per-run failure」— 本 phase 用 state.jsonl + sidecar 部分覆盖；完整 step_log.json 推迟到 v2（REQUIREMENTS.md RES-V2-02 已记录）
- `.planning/research/SUMMARY.md` §"Phase 2: Resume Infrastructure & Cache Correctness" — 高层叙述与本 CONTEXT.md 对齐参考

### 需修改的实际代码文件
- `agent/io.py` — Phase 1 PRE-03 已建；本 phase 扩展 `write_json_atomic` / `read_sidecar` / `write_sidecar` / `compare_params` helper
- `agent/tools.py:35-147` — 5 个 cmd_* 中 3 个写产物点（cmd_download / cmd_transcribe / cmd_aggregate）替换为 atomic-write 调用 + sidecar 写入
- `agent/tools.py:75-81` — `--force` flag pattern 是 sidecar 不匹配时重生路径的复用蓝本
- `agent/tools.py:241-251` — cmds dict 添加 `"doctor": cmd_doctor`
- `agent/tools.py:191-235` — argparse subparser 添加 doctor 子命令
- `agent/state.py` — **新文件**，append-only 事件 + derived_state reducer
- `agent/asr_v2.py:aggregate_paragraphs` — 暴露 `gap_threshold` / `max_para_duration` / `sentence_gap` 给 sidecar 捕获（Phase 5 TEACH-06 会再扩展为 profile）
- `src/asr.py:transcribe` — 暴露 VAD 参数给 sidecar 捕获（Phase 5 TEACH-12 会扩展）
- `docs/schema-migration.md` — **新文件**

### 不修改的文件（明确划界）
- `agent/douyin_downloader.py` — 抖音下载路径与 cmd_download 逻辑解耦；其内部不直接写 artifact，由 cmd_download 负责（atomic-write 在 cmd_download 层即可）
- `vendor/`、`output/` 下所有归档目录、`tests/regression/<slug>/` 快照
- 任何 `src/pipeline.py` / `src/summarize.py` 等 legacy v1 cloud 路径 — 与本 phase 无关

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent/io.py`** (Phase 1 PRE-03 落地) — schema-tolerant loader 的统一入口；本 phase 在此扩展 atomic-write + sidecar helper，保持单点维护原则
- **`agent/tools.py:75-81` `--force` flag idiom** — `if cache.exists() and not args.force: load else compute+write` 是 D-02 强制重生路径的语法蓝本；新 sidecar-mismatch 路径直接复用此结构
- **`json.dumps(obj, ensure_ascii=False, indent=2)` + `Path.write_text(..., encoding="utf-8")` idiom** — 30+ 调用点已一致；`write_json_atomic` 必须保持这两个参数原样，仅替换"write 时机"为 tempfile + os.replace
- **`pathlib.Path.unlink(missing_ok=True)` 清理 idiom** — `src/frames.py:58, 76`、`agent/frames_v2.py:238` 已用；atomic-write 失败时清理 tmp 文件用同一 idiom
- **`subprocess.run([..., "ffmpeg", "-version"], check=True, capture_output=True)` pattern** — `agent/tools.py:120` 已用；提取 ffmpeg version 字符串可复用此调用形态
- **CLI handler 命名 `cmd_<name>`** + dict dispatch — `agent/tools.py:241-251`；新增 `cmd_doctor` 沿用

### Established Patterns
- **JSON write atomicity 当前为零** — 30+ `write_text(...)` 直接覆盖；本 phase 全量替换为 `write_json_atomic`，但保留 `write_text(encoding="utf-8")` 用于 markdown / 非 artifact 文件
- **Cache 当前仅 file-existence** — `agent/tools.py:75-81` 是唯一显式 cache check；`cmd_aggregate` 完全没 cache（CONCERNS §5.4）。本 phase 引入"sidecar diff"作为新 cache 失效维度，但不增加新 cache 路径（仍是同一个 path.exists() 检查）
- **CLI 路径处理**：positional dir / file，`--out` 表 output dir，flag 用 `--lower-with-dashes`（CONVENTIONS §"CLI Pattern"）— doctor 子命令沿用
- **Logging idiom**：`log = logging.getLogger(__name__)` + lazy `log.warning("foo: %s", x)`；本 phase 大量使用 warning level（D-01 / D-02 / D-03），保持 lazy formatting

### Integration Points
- **`agent/tools.py` 主调度器** — 5 个 cmd_* 写产物点 + 1 个新 cmd_doctor + 5 个 cmd_* 读 cache 时的 sidecar 比对（D-01/D-02 触发点）
- **`agent/io.py`** — Phase 1 已建模块，本 phase 扩展（不重构、不分模块 — 保持 single-landing-point）
- **`agent/state.py`** — 新模块，纯函数 reducer + I/O；不引入新依赖（stdlib only：`json`, `pathlib`, `datetime`, `hashlib`）
- **`agent/asr_v2.py:aggregate_paragraphs` 函数签名** — 当前默认值 hard-code 在函数内（asr_v2.py:28-32）；本 phase 必须把它们暴露为可读参数（即使签名不变，至少加一个 `_DEFAULTS` 常量），让 sidecar 能记录"实际生效的"参数。Phase 5 TEACH-06 会进一步扩展为 `profile=` 参数 — 本 phase 留好接口
- **`src/asr.py:transcribe` 函数签名** — 类似 aggregate_paragraphs，VAD 参数当前 hard-code，本 phase 暴露为可读 default
- **`docs/`** — Phase 1 已可能创建（Phase 1 D-05 由 planner 选择）；本 phase 必创 `docs/schema-migration.md`，与 schema-versions.md 同目录
- **`.gitignore`** — 检查不要把 `state.jsonl` / `*.params.json` ignored 掉（grep 现状：只 ignore `output/`，所以归档下的 sidecar 跟 artifact 一起 gitignore 是正确的；不需要改 .gitignore）

### 现状测试覆盖（CONCERNS §9.1）
- 当前**零单测**；本 phase 是引入新基础设施的好时机，但**不强制**写 unit test —— 与 PROJECT.md 整体哲学一致 + Phase 1 D-07 「Claude eyeball diff」回归方法已是测试承担方
- planner 可自由选择写少量纯函数 unit test（候选：`derived_state(events)` reducer、`compare_params(old, new)` 比对函数、`params_hash` 计算）；这些纯函数测试不依赖 I/O，写起来零成本
- 集成层验证 = 跑 Phase 1 三条 regression 基准（BV132wizyEEB / BV1C9QCBdE1U / douyin_trae_ai）应在本 phase 完成后**仍 pass eyeball diff**

</code_context>

<specifics>
## Specific Ideas

- **用户表态**：本 phase + Phase 1 都属"基础设施边缘"，user 不介入灰色决策（"合理即可"），关注点是 Phase 5 TEACH 的文档质量提升。本 CONTEXT.md 所有 D-XX 决策均由 Claude 自决，planner / executor 可在 PLAN.md 中标注偏离理由后调整。
- **设计哲学锚点**："loud + 不破坏" 是 D-01 / D-02 / D-03 的共同主题 — 看到 stale 状态就喊出来，但绝不擅自破坏 17 archive 已有产物。这是 PROJECT.md K3 + K5 在本 phase 的具体形态。
- **本 phase 的成功 = Phase 3 / 4 / 5 不会"踩坑"**：换 whisper model / VAD 阈值 / fps schedule / aggregate profile 时不再静默复用过期产物；mid-write 崩溃不再留半截 JSON；任何 stage 都能从上次中断点 resume。如果本 phase 留下隐患，下游 phase 会以 "为什么我的 fix 不起作用" 的形式付费。

</specifics>

<deferred>
## Deferred Ideas

- **`step_log.json` 全 provenance**（PITFALLS U4） — 推迟到 v2（REQUIREMENTS.md RES-V2-02 已记录）；本 phase 用 sidecar + state.jsonl 部分覆盖
- **Whisper-server 持久化 model 跨调用**（PITFALLS 隐含 / RES-V2-01） — 推迟到并行能真正落地（Phase 6 PARA 真做时再考虑）
- **Cache key 含 audio mtime / video.mp4 hash** — 本 phase 不做；sidecar 字段是"参数维度"，不引入"输入数据 hash"维度。如果未来出现"换了 video.mp4 但参数不变 → 静默用了旧 segs.json"的真实案例，再考虑（实际可能性低，因为换 mp4 通常会清空 output/<slug>/）
- **`agent/state.py` 真正的 segment-级 frame 事件** — 推迟到 Phase 4 与 `extract_frames_batch` 同 phase 引入（D-14）
- **doctor 的 `--diff` / `--fix` flag** — 推迟到 Phase 4-5 引入新 artifact 后真有 diff 需求时再加；现在 YAGNI
- **schema-migration runbook 含真实 v1→v2 迁移代码** — 本 phase 只写"伪 round-trip 示例"占位；首次真实 v2 迁移由那个 phase 承担（Phase 1 D-06 已锁此原则）
- **`requirements.txt` 加 `filelock`** — 不做，那是 Phase 6 PARA 的事；本 phase 的 atomic-write 不需要外部锁，`os.replace` 已是 OS 级原子原语
- **修复 CONCERNS §1.1（三套 frame 抽取实现并存）/ §1.2（agent/prepare.py 半孤儿）** — 与 Phase 2 范围无关，PROJECT.md OOS "Rewrite or delete existing modules" 明确禁止；继续保留

</deferred>

---

*Phase: 02-resume-infrastructure-cache-correctness*
*Context gathered: 2026-05-01*
*Decision authority: Claude self-decided (user explicitly opted out for infra phase)*
