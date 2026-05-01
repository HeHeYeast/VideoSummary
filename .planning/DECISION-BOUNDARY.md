# Decision Boundary — 用户拍板 vs Claude 自决

**Created:** 2026-05-01 (Phase 5 discuss session)
**Purpose:** 跨 session 持久化"哪些决策需要 user 拍板、哪些 Claude 自决"。`/clear` 后 Claude 应当先读本文件再 discuss/plan/execute 任何 phase。
**Authority:** 本文件 > memory（memory 可能 stale）。user 可直接编辑修订。

---

## 默认规则

**Claude 自决一切**（discuss / plan / execute 阶段所有灰区），除非命中下方"User 决策点"列表中的某条。命中时拉用户拍板；未命中时直接给推荐方案 + 标 [Claude 自决] 写进对应 CONTEXT.md，user 事后可编辑否决。

User 原话（2026-05-01）：
> "除了几个关键的其他全部你自动化来决策"
> "phase3和6才有我需要决策的内容，其他的应该都不是真正会主要影响文档质量的"

理由：质量类决策 user 没有具体到"想要这种风格"的偏好；功能性 scope 决策（输入侧能处理什么 / 输出侧能并行多少）user 才有明确偏好。

---

## 需要用户决策的边界（命中 → 拉 user）

### 功能性 scope 决策（必拉）

- **新增/移除依赖体量大**（> 100MB 或需要 GPU/HF token/系统级安装）—— 例：pyannote.audio + ~700MB torch、Deno + yt-dlp-get-pot、CUDA 工具链
- **新增/移除支持的视频平台**（影响 user 能下载哪些来源）—— 例：是否加 Niconico / Twitter / Vimeo extractor
- **改变 user 工作流入口**（CLI 命令名/参数被砸 / `/summarize-video` 主干被改）—— 例：`download` 命令重命名 / 8 阶段流程被分叉
- **multi-terminal / 并行性契约**（影响 user 如何在多终端跑视频）—— Phase 6 PARA 全部决策
- **删除任何老 CLI / 改 `output/<slug>/` 目录约定**（17 archived re-run 路径触线）

### 不可回退决策（必拉）

- 删除 `agent/` 或 `src/` 的现有公开模块
- 改 `meta.json` / `paragraphs.json` / `segs.json` schema 非 additive 字段
- 引入需要 user 自己跑且耗时 > 30min 的 spike（如 pyannote on Windows CPU）—— 拉 user 但作为 plan 任务而非 plan-time 阻塞

### NTH ship-or-skip 决策（必拉）

- Phase 6 PARA 在 v1 是否真的 ship（PROJECT.md K Decision row 4: "做不到也没关系"）—— ship 的范围是什么，skip 的话彻底 skip 还是只 ship docs

---

## Claude 自决的边界（命中 → 自决 + 标 [Claude 自决]）

### 质量类决策

- 教学风格 / exemplar skeleton 来源 / 模式分类策略 / hybrid mode 形态
- prompt engineering 细节（CLAUDE.md 章节排版、措辞、示例段落）
- 新视频类型的写作骨架细节（podcast 章节结构、UI demo 4 子规则措辞）

### 技术实现细节

- 数据结构 schema（free-form / YAML front-matter / JSON 字段命名）
- CLI flag 名（`--profile` 还是 `--mode`，`--force` 还是 `--regen`）
- 模块拆分（新功能放 `agent/X.py` 还是 `src/X.py`）
- VAD / fps / threshold 等数值 tuning（除非要求 spike）
- Cache / sidecar / state.jsonl 集成模式
- Atomic write / retry / encoding 等基础设施 idiom

### 测试与文档

- 单元测试覆盖范围与 fixture 设计
- README / docstring 措辞
- commit message 风格（已锁 conventional commits）
- DISCUSSION-LOG / SUMMARY / VERIFICATION 等 GSD 工件

---

## 各 phase 决策状态（事后回顾）

| Phase | 状态 | User 实际决策的内容 | Claude 自决了什么 |
|-------|------|-----------------|-----------------|
| 01 PRE | ✅ 完成 | 无（user 表态"边缘 phase 我不关心，合理即可"） | 全部 |
| 02 RES | ✅ 完成 | 无（同上） | 全部 |
| 03 SRC | ✅ 完成 | **YouTube 设置体量**（Deno + PO Token + cookies 三层 opt-in 而非 mandatory）；**LocalSource 加入 SOURCES 列表顺序**；**抖音/YouTube/Local mp4 三平台都 ship**（user 拍板 scope） | sources/ 目录结构 / url_router 实现 / 5-class preflight 分类器细节 / -vsync vfr 加在哪 |
| 04 FPS | ✅ 完成 | 无（user 走 `--auto`） | 全部（schedule.json schema + extract_frames_batch CLI + scenes/silence 决策支持 + silero-vad opt-in） |
| 05 TEACH | ⏳ 进行中 | **无**（user 2026-05-01 明确"全部你自动化决策"） | 8 个灰区全部 [Claude 自决]，详见 `phases/05-.../05-CONTEXT.md` |
| 06 PARA | 待开始 | **NTH ship-or-skip**（user 拍板是否真的 ship Phase 6，scope 多大）；**multi-terminal 并行性契约**（slug-prefix log / cookies-in-memory / per-slug lock 三个能力分别要不要做） | filelock 实现细节 / 锁文件命名 / log prefix 格式 / 文档措辞 |

---

## 操作建议（给未来 session）

1. **/clear 后第一件事**：读本文件 + 当前 phase 的 CONTEXT.md（如已 gather）
2. **discuss 阶段**：扫"用户决策边界"列表，命中项才拉 AskUserQuestion；其余直接给推荐方案 + [Claude 自决] 标记
3. **plan / execute 阶段**：仅在命中"不可回退决策"或"功能性 scope"时拉 user；纯实现细节自决
4. **遇到边界模糊**：默认走自决，但在 CONTEXT.md / SUMMARY.md 末尾留一行 `*Boundary call: 自决 [X]，理由：...；user 可否决*`，让 user 一眼看见
5. **Memory `feedback_phase_priority.md`** 与本文件冲突时，**以本文件为准**（本文件 git-tracked，更新更可控；memory 是 per-machine cache）

---

*Last updated: 2026-05-01 (Phase 5 discuss session) — user 偏好从原 memory "Phase 5 详细讨论" 演化为"全部 Claude 自决，除非命中本文件列出的边界"。*
