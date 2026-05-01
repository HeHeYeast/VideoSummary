# Phase 5: Adaptive Output + UI Demos + Podcasts - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning
**Decision authority:** Claude 自决（user 明确："除了几个关键的其他全部你自动化来决策"；"phase3和6才有我需要决策的内容，其他的应该都不是真正会主要影响文档质量的"）。所有 8 个灰区均 [Claude 自决]，user 可事后通过编辑本文件否决。memory `feedback_phase_priority.md` 已同步更新偏好。

<domain>
## Phase Boundary

让 Claude 看完视频后自适应选择教学维度（4 模式：复刻指南 / 原理讲解 / 延展应用 / 访谈萃取）输出文档；ship UI demo + 播客两类新视频类型的写作骨架；Python 触点最小化——只新增 `aggregate --profile`、`diarize` opt-in 子命令、whisper 重复保护后处理、`chapters.json`（podcast）。其余 100% CLAUDE.md prompt engineering，零 LOC 业务逻辑变更。

不变（backward-compat）：
- `aggregate` 不带 `--profile` 时行为 byte-equal 于现状（对应 `--profile tutorial` 默认值，17 archived 不能砸）
- `transcribe` 不带 `--profile` 时行为 byte-equal 于现状
- `/summarize-video` 8 阶段工作流主干结构不变（mode 选择嵌入 Phase 2 的 paragraphs 通读步骤）
- `meta.json` / `paragraphs.json` / `segs.json` schema 不变
- 老命令/老路径 17 archived re-run 路径全部继续可用

</domain>

<decisions>
## Implementation Decisions

> 全部为 [Claude 自决]。user 事后否决方式：编辑本节对应 D-XX 行 + 在末尾加 `*否决 by user 2026-XX-XX：[新决策]*` 注释。

### 模式分类策略 (TEACH-01) — [Claude 自决]
- **D-01:** 4 模式标签（`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`）采用 **primary + optional secondary** 模型，写入 `plan.md` front-matter 顶部：
  ```yaml
  mode: replicate-guide
  secondary_mode: concept-explanation  # 可选，留空表示纯单模式
  ```
  Hybrid 软锁定（REQUIREMENTS "or hybrid" 措辞兑现）：避免 4 模式互斥导致的强分类副作用，同时不上"权重打分"等过设计。
- **D-02:** 分类提示词嵌入 **`/summarize-video` Phase 2 "理解内容"** 末尾（与现有 "判断视频类型" 步骤合并，不新增 Phase）。Claude 通读 paragraphs.json 后写出 4 行判断（每个 mode 一行：`replicate-guide: 70% 代码演示，UP 全程 hands-on coding`），再得出 primary + secondary 结论。
- **D-03:** **Fallback 策略**：判断模糊（4 模式无明显主导，例如 50/50 教学+演示）时默认 fallback 到 **`replicate-guide`** —— 与 17 archived 风格一致，user 已熟悉，是"最低惊讶"的安全选择。
- **D-04:** **Mode 切换允许在写作中途**：Claude 写到一半发现 mode 误判，可在 `plan.md` 改 mode 字段并附 `mode_switched_at: HH:MM:SS reason: ...`，重写已写部分。这是 P1.5 "wrong depth wastes tokens" 的兜底。
  - **Rationale:** REQUIREMENTS "or hybrid" 已软锁，replicate-guide fallback 与历史归档一致，prompt-only 实现保持 K2 "Claude is decider"。

### Exemplar skeleton 来源 (TEACH-03) — [Claude 自决]
- **D-05:** 路径 **(b)+(c) 混合**：所有素材来自 **已归档 corpus**（`output/*/summary.md` 现存 25+ 条），不跑新视频，零 ¥0 成本。每个 mode × 2 = **8 份 minimal skeleton** 嵌入 CLAUDE.md。
- **D-06:** **Mode → 候选源视频**（plan execution 时由 Claude 在归档库挑最贴合的，不在 CONTEXT 硬绑定具体 BVid，避免选错时整 CONTEXT 改）：
  - `replicate-guide`：从代码/Godot/UI 操作密集型归档挑（BV132wizyEEB 是当然候选）
  - `concept-explanation`：从原理讲解型归档挑（用户队列里 ECS / Karpathy 类视频是天然候选；如归档库不够好，Claude 在 plan execution 时退回到从一份代码教程 reshape 出"如果只讲原理会怎么写"）
  - `extension-applications`：从应用整合型归档挑（douyin_ai_kb / douyin_claude_code_hooks 类是候选）
  - `interview-distillation`：直接用 `douyin_karpathy_llm_wiki`（已归档，访谈结构最贴合）
- **D-07:** **Skeleton 形态**：每份 50-120 行 minimal markdown，**仅展示 mode-specific 章节结构 + 1-2 个示例段落**（不是完整 summary.md）。例如 concept-explanation skeleton 不放完整代码块，只放"先抛核心问题 → 给出反直觉答案 → 用 1 个最小例证 → 引申应用边界"的章节流。
- **D-08:** **Reshape 工作量上限**：plan 03 内 8 份 skeleton 控制在累计 800-1000 行内（CLAUDE.md 单 file 不爆）。如某 mode 的 reshape 实际工作量 > 200 行，停下来 surface "skeleton 过长，建议人审" 给 user。
  - **Rationale:** 17 archived 全是 replicate-guide 偏置（PITFALLS P1.3 风险源），但 reshape 比"全新原创"成本低 10×，user 只需事后扫一眼校对，不需要从头写；在已知 corpus 里挑 + 改 也保持 ¥0。

### plan.md / depth_plan.md schema (TEACH-04, TEACH-05) — [Claude 自决]
- **D-09:** **plan.md = free-form Markdown + 顶部 YAML front-matter**（混合形态，front-matter 装 5 个结构化字段，正文随意）：
  ```yaml
  ---
  mode: replicate-guide
  secondary_mode: null
  classification_evidence: |
    70% 代码演示，30% 概念引入 ("ECS 是什么")，UP 全程 hands-on coding
  fps_strategy_summary: 代码段 fps 0.4 / UI 段 fps 0.2 / 闲聊跳过
  estimated_sections: 6
  ---
  # Phase 2 判断笔记
  （free-form）
  ```
  YAML front-matter 5 字段都是字符串/null，Claude 写错也不会让工具崩（free-form Markdown 不强 schema 校验，REQUIREMENTS 字面要求 "free-form, no schema enforcement"）。
- **D-10:** **plan.md mandatory** 在 `/summarize-video` Phase 2 末尾写入 `output/<slug>/plan.md`；不存在 → 后续阶段提示"建议先写 plan.md 但不强 fail"（保留 K3 backward-compat，老 17 archived 没 plan.md 不破坏 re-run）。
- **D-11:** **depth_plan.md 是独立可选文件**（不嵌入 plan.md），用于 token-expensive 视频（> 30min 或 > 50 章节预估）；Claude 自判是否需要，user 可手动 `touch output/<slug>/.need_depth_plan` 强制启用。不强制 user pause confirm（与 K2 一致：Claude 是 decider）。
- **D-12:** plan.md / depth_plan.md 都有 sidecar `<file>.params.json`（Phase 2 D-01 模式），但仅记录 `{"created_at": "...", "mode": "...", "secondary_mode": "..."}`——cache 层级不参与 regen 判断（plan 是 Claude 写的，无参数 hash 概念）。
  - **Rationale:** REQUIREMENTS 字面锁 "free-form, no schema enforcement"；front-matter 是装饰性结构化，方便 grep / 未来 doctor 子命令读 mode 但不强制校验。

### Diarization rollout + spike (TEACH-08) — [Claude 自决]
- **D-13:** **Spike 推迟到 plan 03 第 1 个任务**（不阻塞 plan creation）：plan 03 task 列表第一条是 "user spike: 在自己的 Windows 11 + CPU 上对 1 条 30-60min 真实播客跑 pyannote 4.0 + community-1 model；记录 wall time / RAM peak / output 质量；填入 `.planning/phases/05-.../SPIKE.md`"。spike 失败/不可接受时 plan 03 后续任务降级为"podcast skeleton 不依赖 diarization，speaker_id 留空"。
- **D-14:** **不做 cheap heuristic 2-speaker fallback**（PITFALLS 提到的"VAD energy + spectral centroid"）。理由：(a) 工作量大；(b) Claude 多模态本身可从内容线索推断说话人切换（"现在让我请到嘉宾..." / 提问 vs 回答语气），优于启发式 audio-only 方案；(c) 失败也不阻塞——播客模式仍能写，只是不带 speaker label。
- **D-15:** **HF token UX**：通过 `.env` 文件读取 `HF_TOKEN`（与 douyin cookies + 现有 `VE_KEY_CHEAP` 一致 idiom）；CLAUDE.md 新增 "## Pyannote diarization 设置（首次设置，可选）" 章节文档化（与 douyin / YouTube 章节并列），含 token 申请 URL + `.env` 写入示例 + community-1 model 接受协议链接。
- **D-16:** **时长/RAM 上闸**：`diarize` CLI 启动时跑 ffprobe duration；`duration > 60min AND not torch.cuda.is_available()` 时 stdout 提示 `"WARNING: 60min+ 音频在 CPU 上 pyannote 预计 3-5× wall time（约 3-5h）。建议 (1) 切片处理 (2) 跳过 diarization 让 Claude 从内容推断 (3) 等待 GPU 机器再跑。继续？(y/N)"`，prompt 默认 N。
- **D-17:** `requirements-optional.txt` 加 `pyannote.audio>=4.0,<5.0`（复用 Phase 4 已建立的 opt-in 文件 + ~700MB torch 已经在那里 by silero-vad）。CLAUDE.md 在 setup 章节明确说"播客模式 opt-in"。
  - **Rationale:** SUMMARY.md 标 pyannote 是"单个最大 ships-or-doesn't 决策"，spike 必须由 user 在自己机器跑——但作为 plan task 不阻塞 plan creation；Claude 多模态推断说话人是更便宜兜底；时长闸防 user 误启动 5h 跑批。

### UI demo + podcast skeleton 形态 (TEACH-09, TEACH-10) — [Claude 自决]
- **D-18:** **CLAUDE.md 新增章节** "`## 视频类型变奏`" 放在现有 "`## /summarize-video 完整工作流`" 之前，不动现有 8 阶段流程主干。该节内含 4 个 mode skeleton（D-05..D-07）+ podcast 模式分支说明 + UI demo 写作 4 子规则。
- **D-19:** **Podcast 模式 frame 策略**：默认 **每章节 1-2 帧**（不完全 skip）。理由：保留视觉锚点（讲者表情 / 嘉宾切换 / 屏幕分享），文档读者扫文档时有视觉切分；schedule.json 每章节 fps 0.05 + start/end 框定章节时间窗。完全 skip 留作 `--no-frames` flag（非 v1 范围）。
- **D-20:** **UI demo 4 子规则**按 REQUIREMENTS 字面顺序写入 skeleton：
  1. **Pixel-text 不确定引用**：UI 软件用 proportional 字体 + 抗锯齿，多模态识别准度低于 monospace；指令 Claude `quote-with-uncertainty`，用 `> 该控件大致写着"XXX"（多帧交叉验证后置信度中等）`
  2. **Tooltip 遮挡检测**：发现 tooltip 遮目标 → 采前/后 0.5s 帧；都遮 → 标 `*该值视图被 tooltip 遮挡，未取得*`
  3. **光标不可见兜底**：黑光标在黑 UI / 截屏不含光标 → 从前后帧 panel state diff 推点击位置；命名一律按控件 label/icon，禁空间方位
  4. **`--width 1280/1920` 4K override**：4K 录屏抽 frame 时若 `default_scale: 854:-1` 输出过小（小于 800px 宽）丢可读性 → schedule.json 加 `default_scale: 1280:-1` 或 `1920:-1` 提示
- **D-21:** **不分叉 /summarize-video**：mode 在 Phase 2 选完后，Phase 3-7 自动按 mode-specific skeleton 走（podcast 用 chapters.json + 1-2 帧/章节，UI demo 用 4 子规则，replicate-guide / concept-explanation 走主流程的两种偏向）。**不**为 podcast 单独写一个 8 阶段并列工作流——避免 CLAUDE.md 双倍膨胀。
  - **Rationale:** REQUIREMENTS 字面已锁 4 子规则；1-2 帧/章节比纯 skip 给读者更好导航；不分叉 8 阶段保持工作流简洁。

### Whisper 重复保护 surfacing (TEACH-11) — [Claude 自决]
- **D-22:** **算法**：3-gram 滑窗扫 segs.json，单 segment 内某 3-gram 连续重复 > 3× （即第 4 次出现），或跨 ≤ 3 相邻 segments 内 3-gram 连续重复 > 3× — 命中即 flag。3-gram 粒度避免误报短停顿词（"嗯啊呢"），跨段窗 3 兼顾 whisper 跨段幻觉。
- **D-23:** **Surfacing**：组合 (a)+(b) 两种：
  - **(a) stdout warning**: `transcribe` / `cmd_aggregate` 末尾打印 `WARNING: detected N suspected whisper repetitions; first 3: [time HH:MM:SS] "<3-gram>" repeated <K>× — review output/<slug>/transcribe_warnings.json`
  - **(b) 旁路 artifact**: `output/<slug>/transcribe_warnings.json` schema:
    ```json
    {
      "version": 1,
      "warnings": [
        {"start": 12.5, "end": 23.1, "trigram": "我们这里用", "count": 7,
         "context_before": "...", "context_after": "...", "seg_indices": [42, 43, 44]}
      ]
    }
    ```
- **D-24:** **绝不 auto-delete**（PROJECT.md 红线"不注水不编造"）。`segs.json` schema 不动；warnings 完全旁路。
- **D-25:** **不强 fail**：不引入 `--force-loose`；warning 是提示性的，不阻断 pipeline——user 看到 warning 后可手编 segs.json 或重跑 `transcribe --whisper medium` 换模型。
  - **Rationale:** 红线锁不删；旁路文件让 user 可见可审；不污染老 schema；不强 fail 保持自动化跑批顺畅。

### VAD per-profile 落点 (TEACH-12) — [Claude 自决]
- **D-26:** **落 transcribe**（`src/asr.py`），不落 aggregate。理由：whisper 幻觉源在 transcribe 阶段（VAD 设置直接影响 whisper 输入），aggregate 拿到 segs.json 后已无法 catch silent 幻觉。
- **D-27:** **`--profile` 参数沿 transcribe → aggregate 一路穿**：
  - `transcribe --profile {tutorial|podcast}`：默认 tutorial（VAD `min_silence_duration_ms=200`，现状）；podcast 设 `min_silence_duration_ms=500` + 略提 VAD threshold
  - `aggregate --profile {tutorial|podcast}`：默认 tutorial；语义对应 TEACH-06 PROFILES 数值
  - sidecar params.json 记录 profile 字段，profile 切换触发 cache 失效（Phase 2 D-XX cache 决策器自动处理）
- **D-28:** **`src/asr.py` 加 `PROFILES` dict**（与 `agent/asr_v2.py:_DEFAULTS` 平行，但仅 VAD 相关字段）：
  ```python
  PROFILES = {
      "tutorial": {"vad_min_silence_ms": 200, "vad_threshold": 0.5},
      "podcast":  {"vad_min_silence_ms": 500, "vad_threshold": 0.6},
  }
  ```
- **D-29:** **Backward-compat**：`transcribe` 不带 `--profile` → 行为等价 `--profile tutorial`，sidecar 写 `"profile": "tutorial"`（17 archived re-run 不破坏）。
  - **Rationale:** 幻觉源头在 transcribe；sidecar 自动 cache 失效；`--profile` 是 user-facing knob 必须从一头穿到另一头才能闭环。

### WR-02 VTT 优先级 fold-in (Phase 3 deferred) — [Claude 自决]
- **D-30:** **Fold 进 plan 03**（与 podcast 同 plan）。理由：podcast 模式直接受益（YouTube 创作者上传的 VTT 通常是人工字幕，> 95% 准确，比 ASR 更可信）；scope 极小（修 `agent/sources/youtube.py` 内一段 vtt 语言优先级逻辑 + meta.json `subtitle_origin` 联动）；不 fold 需要单开 phase 7 不划算。
- **D-31:** **行为**：`agent/sources/youtube.py` 抓 VTT 时优先级改为 `zh-Hans > zh-Hant > zh > en > 任何 manual > 任何 auto-generated`；`subtitle_origin` 字段已存在（Phase 3 SRC-08）—— `creator` 标记走优先链顶端，`auto` 沦为兜底。
- **D-32:** **Podcast 模式联动**：当 `meta.json.subtitle_origin == "creator"` 且 mode 为 `interview-distillation` 时，CLAUDE.md skeleton 提示 Claude "VTT 字幕已是 creator-uploaded 高质量来源，可直接信任引用，不需要 ASR 重跑"。
  - **Rationale:** scope 小；与 podcast 模式天然耦合；不 fold 反而需要单开一个孤立 phase。

### Claude's Discretion
- 每个 mode 具体 8 个 skeleton 选哪条归档视频做素材源（D-06 给了候选范围，plan execution 时由 Claude 挑最贴合的）
- transcribe_warnings.json 里 `context_before` / `context_after` 各取多少字符（默认 200 字符，Claude 可在实现时按可读性调）
- CLAUDE.md "## 视频类型变奏" 章节内部小标题排序（plan execution 时按可读性排）

### Folded Todos
（无：cross_reference_todos 返回 0 matches）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 5 直接来源
- `.planning/REQUIREMENTS.md` §TEACH (TEACH-01 .. TEACH-13) — 13 reqs 字面定义
- `.planning/ROADMAP.md` §"Phase 5: Adaptive Output + UI Demos + Podcasts" — 5 Success Criteria 验收标准
- `.planning/PROJECT.md` §"Active" + §"Key Decisions" — 自适应教学文档 / 新视频类型 / Claude 是 decider 红线
- `.planning/research/SUMMARY.md` §"Phase 5: Adaptive Output + New Video Types" — 5b pyannote 决策 / exemplar 必要性 / chapters.json
- `.planning/research/PITFALLS.md` §"Pitfall P1.3" + §"P6.1 / P6.2 / P6.3 / P6.4" + §"P5.1 / P5.2 / P5.3" — 教学 / 播客 / UI demo 三类 pitfall

### 上游 phase 决策（继承）
- `.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md` — schema_version=1 兼容协议
- `.planning/phases/02-resume-infrastructure-cache-correctness/02-CONTEXT.md` — sidecar 模式 / atomic write / state.jsonl
- `.planning/phases/03-source-refactor-new-sources-youtube-local-mp4-generic/03-CONTEXT.md` — meta.json `subtitle_origin` 字段（D-32 fold-in 复用）
- `.planning/phases/04-frame-fps-automation-schedule-json-extract-frames-batch/04-CONTEXT.md` — schedule.json 形态（D-19 podcast 1-2 帧/章节复用）

### 代码地图
- `.planning/codebase/CONVENTIONS.md` — Python 风格 / dataclass 模式 / CLI 约定
- `.planning/codebase/STRUCTURE.md` — agent/ vs src/ 分层

### 现有 Python 接入点
- `agent/asr_v2.py:30-35` — `_DEFAULTS` dict（D-09 podcast 数值已锁；D-28 在 `src/asr.py` 平行加 `PROFILES`）
- `agent/tools.py:271-319` — `cmd_aggregate` 现状（D-27 加 `--profile` 入口）
- `agent/tools.py:787-790` — argparse `aggregate` subcommand（D-27 加 flag）
- `src/asr.py` — `transcribe()` + VAD 设置入口（D-26..D-28 改动点）
- `agent/sources/youtube.py` — VTT 抓取逻辑（D-31 改动点）
- `CLAUDE.md` — 顶层指南文件（D-18 新增"## 视频类型变奏"节）

### 外部参考（plan 03 spike 时读）
- pyannote.audio 4.0 docs — https://github.com/pyannote/pyannote-audio
- pyannote/speaker-diarization-community-1 model card — HuggingFace
- silero-vad threshold/min_silence_duration 文档 — https://github.com/snakers4/silero-vad

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent/asr_v2.py:_DEFAULTS` dict (line 30-35)** — Phase 2 已埋下 PROFILES 升级的 hook（注释明确说 "Phase 5 TEACH-06 will introduce a PROFILES dict that flips these"）。D-26..D-28 直接 fulfill this hint，把 `_DEFAULTS` 升级为 `PROFILES` dict。
- **`agent/io.py:write_json_atomic` + sidecar 模式** — Phase 2 RES 基础设施完整可用，plan.md / depth_plan.md / chapters.json / diarization.json / transcribe_warnings.json 全走该模式（`output/<slug>/state.jsonl` 也复用现有事件格式）。
- **`agent/tools.py:_emit_event`** — Phase 4 已有 segment-level 事件机制；diarize / aggregate --profile / 重复保护检测都直接 emit `{stage, status, details}` 事件。
- **`requirements-optional.txt`** — Phase 4 已建立的 opt-in 依赖文件（torch ~700MB 已在）；D-17 加 pyannote 不引入新文件，sustained user-experience。
- **`agent/sources/youtube.py` 5-class preflight** — Phase 3 已落地；D-30..D-32 修 VTT 优先级是局部增强，不动 5-class 分类器。
- **17+ archived `output/*/summary.md`** — D-05..D-08 reshape 素材源，避免跑新视频。

### Established Patterns
- **CLI flag 一路穿到 sidecar**：Phase 2 已确立"params 进 sidecar，cache_decision 自动失效"（D-27 `--profile` 沿用此模式无新机制）。
- **CLAUDE.md 章节并列扩展**：Phase 3 加了 "## 抖音支持" / "## YouTube 支持"，D-15 / D-18 加 "## Pyannote diarization 设置" + "## 视频类型变奏" 沿用此模式（不重排，不动主干）。
- **Skeleton-as-prompt-prior**：CLAUDE.md 现存 "Phase 6: 逐节写作" 节已是 skeleton 模式（带 ![](frames/...)、代码 fence、第二人称指令）；D-05..D-07 的 8 份新 skeleton 沿用相同 markdown 形态。

### Integration Points
- `/summarize-video` Phase 2（CLAUDE.md 当前 line 139-148）— D-02 mode 分类提示词嵌入点；D-10 plan.md 写入点
- `/summarize-video` Phase 4（line 166-181）— D-21 mode-specific skeleton 引用点（podcast 走 1-2 帧/章节，UI demo 走 4 子规则）
- `/summarize-video` Phase 6（line 190-207）— D-21 mode-specific writing 主体引用点
- `requirements.txt` vs `requirements-optional.txt` — D-17 pyannote 加在 optional；D-30..D-32 VTT 修复不引入新依赖
- `src/asr.py` — D-26..D-28 加 PROFILES + `--profile` 参数；transcribe 内 VAD 设置 site
- `.env` — D-15 加 `HF_TOKEN` env var（与 `DOUYIN_COOKIES_FILE` / `VE_KEY_CHEAP` 并列）

</code_context>

<specifics>
## Specific Ideas

### 用户的明确指令（2026-05-01 discuss session）
- "除了几个关键的其他全部你自动化来决策"
- "phase3和6才有我需要决策的内容，其他的应该都不是真正会主要影响文档质量的"
- 隐含偏好：质量类决策 Claude 主导（user 没有具体到"想要这种风格"的偏好），功能性 scope 决策 user 才介入

### 整体策略
- **Plan 01**：CLAUDE.md classification + format-spec lock + exemplar skeletons + plan.md/depth_plan.md（TEACH-01, 02, 03, 04, 05）→ 纯 prompt engineering，零 Python
- **Plan 02**：aggregate `--profile` + transcribe `--profile` + PROFILES + 重复保护 + 旁路 warning artifact（TEACH-06, 07, 11, 12）→ 小量 Python，复用 Phase 2 sidecar 机制
- **Plan 03**：pyannote spike（user task）+ diarize CLI + UI demo / podcast CLAUDE.md skeleton + chapters.json + WR-02 VTT 优先级 fold-in（TEACH-08, 09, 10, 13 + WR-02）→ opt-in 依赖 + skeleton + 小量 Python

### Plan 03 Spike 任务说明（提示 planner 留好该任务）
Plan 03 第 1 个任务是 "user spike" 任务，必须由 user 在自己的 Windows 11 机器上跑：
1. 安装 `pip install -r requirements-optional.txt`（含 pyannote）
2. 申请 HF token + accept community-1 model 协议
3. 选 1 条已归档 podcast 类视频（推荐 douyin_karpathy_llm_wiki，已存在）
4. 跑 `python -m agent.tools diarize output/douyin_karpathy_llm_wiki/audio.wav`
5. 写 `.planning/phases/05-.../SPIKE.md`：wall_time / RAM_peak / 输出质量主观评价 / 是否可接受
6. user 决定继续（plan 03 后续任务正常 ship diarize 集成）or 降级（plan 03 后续 ship 但 podcast skeleton 不依赖 diarization，speaker_id 留空走 Claude 内容线索推断）

</specifics>

<deferred>
## Deferred Ideas

- **Mode 自动重试机制**：`/summarize-video` Phase 6 写到一半发现 mode 误判时，目前靠 D-04 手动改 plan.md 重写。自动 mode-switch detector（基于已写章节 vs paragraphs 内容偏离度）—— v2 considered，v1 不做。
- **Speaker name resolution**：pyannote 给 `speaker_0/1/2` 抽象 ID，user 想看到 "Lex / Karpathy" 名字。v1 不做（Claude 写作时从开场白 / 内容线索推断填名）；v2 考虑加 `speakers.json` 让 user 手动 map ID → name。
- **chapters.json 双向编辑**：user 看完 chapters.json 想改章节切分。v1 chapters.json 是 Claude 单向输出，user 编辑后无 round-trip 校验；v2 加 `chapters_check` CLI。
- **UI demo 分辨率自动检测**：D-20 #4 `--width 1280/1920` 是 user 手动判断 4K 录屏。v2 加 ffprobe 自动建议（属于 SRC-V2-XX）。
- **pyannote on GPU 路径**：D-16 闸口提示 "等 GPU 机器再跑"。v2 加 `--device cuda` flag（pyannote 4.0 已支持），但 user 单机 setup 暂无 NVIDIA GPU，留作 v2。

### Reviewed Todos (not folded)
（无：cross_reference_todos 返回 0 matches）

</deferred>

---

*Phase: 05-adaptive-output-ui-demos-podcasts*
*Context gathered: 2026-05-01*
*Decision authority: Claude 自决（per user feedback "除了几个关键的其他全部你自动化来决策"）*
*All 8 grey areas marked [Claude 自决]; user can override by editing this file*
