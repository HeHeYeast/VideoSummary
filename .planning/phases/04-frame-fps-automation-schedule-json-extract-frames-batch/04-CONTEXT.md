# Phase 4: Frame fps Automation (`schedule.json` + `extract_frames_batch`) - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning
**Decision authority:** Claude 自决（user requested 尽可能不干预模式 — `gsd-discuss-phase --auto`）

<domain>
## Phase Boundary

让 Claude 看完字幕后用 Write 工具直出一份 `schedule.json`（per-segment fps 计划），工具读取这个 JSON 批量执行 ffmpeg 抽帧。保留现有的单段 `extract_frames` CLI（FPS-07 — 用于 Claude 看完第一轮帧后的补抽场景）。提供两条**只读决策支持** CLI（`detect_scenes` 给场景切换时间线，`detect_silence` 给静音区间图谱）让 Claude 写 schedule 时有更多 ground truth，**但工具绝不自动把 scenes / silence 转成 schedule**——那会越过"Claude is decider"红线（K5）。

不变：现有 `cmd_extract_frames` 单段调用接口 + `seg_<start>_<index>.jpg` 文件名约定（FPS-07 + Phase 1 D-04 / Phase 3 D-23 兼容）。

</domain>

<decisions>
## Implementation Decisions

### `schedule.json` schema（FPS-01 — schema 已在 .planning/research/SUMMARY.md 锁定，本 phase 实现它）
- **D-01:** Top-level shape:
  ```json
  {
    "version": 1,
    "video": "video.mp4",
    "default_scale": "854:-1",
    "default_quality": 4,
    "segments": [
      {"start": 0,   "end": 30,  "fps": 0.2, "label": "intro"},
      {"start": 30,  "end": 240, "fps": 0.4, "label": "code-demo-part1"},
      {"start": 240, "end": 245, "skip": true, "label": "filler-question"},
      {"start": 245, "end": 600, "fps": 0.3, "label": "code-demo-part2"}
    ]
  }
  ```
- **D-02:** `version: 1` 强制必填；未来升 v2 时 loader 走 schema_version 模式（Phase 1 D-05 + docs/schema-migration.md 有 runbook）。
- **D-03:** `default_scale` / `default_quality` 是 segment 级缺省，segment 内可 override（但本 phase 只实现 default 的，segment-级 override **不在 v1 范围**——加入会膨胀 schema，YAGNI）。
- **D-04:** `Schedule` dataclass 落 `agent/scheduler.py` 新模块；with `from_json(path)` / `to_json(path)` / `validate()` 方法。dataclass 字段镜像 D-01 schema。Segment 子结构也是 dataclass。复用 Phase 2 `agent/io.py:write_json_atomic` 写 schedule.json（如果将来工具反向写 schedule —— 当前只读，但接口留好）。

### Validation 严格度（FPS-02 — fail loud, never silent）
- **D-05:** 必检 5 项：
  1. `version == 1`（不匹配 raise，不静默接受其他值）
  2. **Full-duration coverage `[0, duration)` ± 2s tolerance** —— 即第一个 segment.start ≤ 2s 且最后一个 segment.end ≥ duration - 2s 且相邻 segment 无 gap > 0s。**Duration 来自 ffprobe 探出的 video duration**（Phase 3 D-21 已落地 ffprobe，可直接用）。如果 schedule 内的 video 字段指向的文件不存在 / ffprobe 探不出 duration，raise 明确错误。
  3. **No overlap**：相邻 segment `prev.end == curr.start` 严格相等（不允许 prev.end > curr.start）
  4. **fps XOR skip**：每个 segment 必须二选一，不能同时有 / 同时缺；`skip: true` 是 boolean 字面量必须为 `true`（不接受 `"true"` 字符串或 `1`）
  5. **No unknown keys** at top level OR per segment：未声明的键 raise 列出位置 + 键名（防止 typo silent ignore）
- **D-06:** 验证错误用 `ScheduleValidationError(ValueError)` 子类，包含具体 segment index + 字段名，便于 Claude 看到错误后定位修复 schedule.json。
- **D-07:** **Silence-coverage 强制条件 (FPS-04)**：schedule 必须满足以下二选一才能通过 validate：
  - (a) 整段视频有一个 fps ≤ 0.1 的 baseline pass（即存在某 segment `start <= 2 AND end >= duration - 2 AND fps <= 0.1`），**OR**
  - (b) **每个 silero-vad 检测出的 > 5s 静音区间都被 schedule 内的某 fps segment 显式覆盖**（不能是 skip segment）
  
  这条是 PITFALLS P2.1 "silent visual content undersampling" 的硬保护——纯讲解视频里 silence 区间常有 PPT 翻页等关键视觉，忘了抽帧就丢内容。
- **D-08:** 当 silence_map.json 不存在时（用户没跑 detect_silence），FPS-04 退化为只检 (a) baseline pass 必须存在。Loud warning：`"silence_map.json not found; FPS-04 enforces baseline-pass requirement only. Run detect_silence for tighter coverage."`

### `extract_frames_batch` CLI（FPS-03）
- **D-09:** 调用方式：`python -m agent.tools extract_frames_batch --schedule output/<slug>/schedule.json --out output/<slug>/frames`。`--schedule` positional 也可接受（与现有 cmd_aggregate 风格一致）。
- **D-10:** 内部实现：load + validate schedule → 遍历 segments → 对每个非 skip segment 调用现有的 `cmd_extract_frames` 单段逻辑（直接复用，不重写 ffmpeg argv 构建）→ 保留 `seg_<start>_<index>.jpg` 文件名 grammar 不变。
- **D-11:** **Resume-aware via state.jsonl** (FPS-03)：每个 segment 处理前 emit `extract_frames_batch` stage 的 segment-level event：
  ```json
  {"ts": "...", "stage": "extract_frames_batch", "status": "started", "details": {"segment_index": 0, "start": 0, "end": 30}}
  ```
  完成后 emit `completed` event with same details. 重跑时 derived_state 算出已完成 segments 集合，跳过它们。失败的 segment（`status: "failed"`）会重跑。这是 Phase 2 D-14 deferred-to-Phase-4 的 segment-level event 落地点。
- **D-12:** `--force` flag 跳过 resume，全量重跑（与 cmd_transcribe `--force` 一致 idiom）。
- **D-13:** 单 segment 内 ffmpeg 失败时：raise `RuntimeError(f"extract_frames_batch segment {idx} failed: ...")` 并 emit `failed` event；后续 segments **不**自动继续（fail-loud，让 Claude / user 看到 stderr 决定如何处理）。

### `cmd_extract_frames` 单段路径保留（FPS-07）
- **D-14:** **不动**现有 `agent/tools.py:cmd_extract_frames` 接口（除了 Phase 3 D-23 已加的 `-vsync vfr`）。它继续是"补抽"工具——Claude 看完第一轮 schedule 抽出的帧后，发现某关键瞬间没采到，用单段 cmd_extract_frames 在精确时间点补几帧。`extract_frames_batch` 是 first-pass 工具，`cmd_extract_frames` 是 finishing-pass 工具，两条路径互补共存。

### `detect_scenes` 决策支持（FPS-05）
- **D-15:** `python -m agent.tools detect_scenes <video> --out output/<slug>/scenes.json`。内部用 PySceneDetect (`scenedetect.detect_scenes`)，threshold 默认 27.0（PySceneDetect 默认值，已知对教学视频偏高灵敏，可能 over-segment；planner 可调或暴露 `--threshold` flag）。
- **D-16:** Output shape:
  ```json
  {
    "version": 1,
    "video": "video.mp4",
    "scenes": [
      {"start": 0.0, "end": 12.5},
      {"start": 12.5, "end": 47.2},
      ...
    ]
  }
  ```
- **D-17:** **工具绝不把 scenes 自动转成 schedule** (K5 + FPS-05 字面要求)。Claude 看 scenes.json 后**自己**写 schedule.json。stdout 打印 scenes 总数 + 中位 segment 时长，方便 Claude 心算"这些场景密度合理吗"。
- **D-18:** PySceneDetect 加入 `requirements.txt`：`PySceneDetect>=0.6.7.1`（per .planning/research/STACK.md）。

### `detect_silence` 决策支持（FPS-06）
- **D-19:** `python -m agent.tools detect_silence <video> --out output/<slug>/silence_map.json`。内部用 silero-vad（已是项目依赖，via faster-whisper VAD chain）。
- **D-20:** Output shape:
  ```json
  {
    "version": 1,
    "video": "video.mp4",
    "silence_intervals": [
      {"start": 0.0, "end": 1.2, "duration": 1.2},
      {"start": 47.2, "end": 53.8, "duration": 6.6, "flagged_for_review": true},
      ...
    ]
  }
  ```
  `flagged_for_review: true` 标记 duration > 5s 的间隔（per FPS-06 字面要求 + D-07 silence-coverage 检查所需信号）。
- **D-21:** stdout 提示 Claude："Found N silence intervals; M flagged > 5s. When writing schedule.json, ensure each flagged interval is covered by an fps segment (NOT skip), or add a low-rate baseline pass per FPS-04."
- **D-22:** silero-vad 已经在 requirements.txt（faster-whisper deps），不需新加。但 `detect_silence` 直接调用 silero-vad 的 model 而不是经过 faster-whisper，需 `silero-vad>=5.1` standalone（per STACK.md）。如果版本冲突，加显式 pin。

### Module 落点 + 文件结构
- **D-23:** `agent/scheduler.py` —— 新模块，`Schedule` / `Segment` dataclasses + `validate()` + `from_json` / `to_json` + `apply_silence_coverage_check(silence_map)` helper.
- **D-24:** `extract_frames_batch` / `detect_scenes` / `detect_silence` 都在 `agent/tools.py` cmds dict + argparse subparser 注册。CLI handler `cmd_extract_frames_batch` / `cmd_detect_scenes` / `cmd_detect_silence` 沿 CONVENTIONS.md `cmd_*` 命名。
- **D-25:** PySceneDetect 调用逻辑 + silero-vad 调用逻辑可单独放 `agent/scenes.py` / `agent/silence.py`（小模块），cmd_* handler 调用它们。Planner 决定是否分模块 vs inline 在 cmd_* 内（建议小模块，跟 agent/scheduler.py 分开关注点）。

### 与 Phase 5 的接口（forward-compat）
- **D-26:** Phase 5 TEACH-01 让 Claude 在 plan.md 里写 mode 分类 + 整体 fps 策略 reasoning。**plan.md 不是 schedule.json**——plan.md 是自然语言意图描述，schedule.json 是机器可读 spec。Phase 4 不假设 plan.md 存在；schedule.json 完全独立。Phase 5 落地后两者并存，互补不互依。

### Plans 拆分（与 ROADMAP 一致，2 plans）
- **D-27:** **04-01**: `agent/scheduler.py` + `extract_frames_batch` CLI + 严格 validation + resume 集成（FPS-01, FPS-02, FPS-03, FPS-04, FPS-07）。FPS-07 = "确认 cmd_extract_frames 单段接口无回归"，是验证任务不是改动任务。FPS-04 silence-coverage 检查在 silence_map.json 缺失时退化（D-08）。
- **D-28:** **04-02**: `detect_scenes` + `detect_silence` 决策支持子命令（FPS-05, FPS-06）。**后做**这个，因为 04-01 的 FPS-04 silence-coverage 检查需要 silence_map.json 形态约定 —— 04-02 落 D-20 schema 后，04-01 的检查器才能消费。但 04-01 也设计为 silence_map.json 缺失时退化（D-08），所以**两者不严格依赖**，可独立完成。Wave 安排为 wave 1 = 04-01, wave 2 = 04-02 主要因为 04-01 才是核心交付，04-02 是辅助。

### Claude's Discretion（planner / executor 自决）
- PySceneDetect threshold 默认值 + 是否暴露 `--threshold` flag
- silence_intervals JSON 是否包含 `voice_activity` 反向区间（建议否，YAGNI）
- `Schedule` dataclass 是否提供 `__post_init__` validate（建议否——validate 是显式方法，让调用方决定时机）
- 单 segment 内 ffmpeg argv 是否提取成 helper 函数（cmd_extract_frames 已有逻辑，复用即可，不抽公共 helper）
- `extract_frames_batch` stdout 进度报告格式（每 segment 一行 vs 进度条；建议每 segment 一行简单 print，与项目 logging idiom 一致）
- detect_scenes / detect_silence 内部是否 cache 结果（YAGNI；ffprobe 等的 cache 由 sidecar 机制管，本 phase 工具是用户主动跑的诊断输出）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级约束
- `.planning/PROJECT.md` — Constraints §"Decision authority"（K5 Claude is decider — FPS-05/06 工具 NEVER auto-promote 是这条的具体形态）+ K3 backward-compat（FPS-07 cmd_extract_frames 不动）+ §"Stack inertia"
- `.planning/REQUIREMENTS.md` §"FPS — Frame fps Automation" — FPS-01..FPS-07 全文
- `.planning/ROADMAP.md` §"Phase 4" — 5 条 Success Criteria + 2-plan 拆分

### Phase 1+2+3 已锁定决策（必读）
- `.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md` — D-04（顶层 list 工件不可 wrap，但 schedule.json 是 dict，不受影响）
- `.planning/phases/02-resume-infrastructure-cache-correctness/02-CONTEXT.md` — D-09/D-10 atomic-write、D-12/D-13 state.jsonl 事件 schema、**D-14 deferred segment-level events** 是本 phase 的落地点
- `.planning/phases/03-source-refactor-new-sources-youtube-local-mp4-generic/03-CONTEXT.md` — D-21/D-22/D-23 ffprobe + `-vsync vfr`，本 phase 的 schedule validation 用 ffprobe duration

### 代码地图
- `.planning/codebase/ARCHITECTURE.md` §"Data Flow" / §"Artifact Layer" — schedule.json / scenes.json / silence_map.json 都是 `output/<slug>/` 下新增 artifact
- `.planning/codebase/CONVENTIONS.md` §"CLI Pattern" — cmd_* 命名 + dict dispatch + argparse；§"I/O & Path Conventions" — JSON write idiom
- `.planning/codebase/STRUCTURE.md` §"Where to Add New Code" - "A new ¥0 CLI subcommand" 章节直接对应

### 风险与陷阱（必读）
- `.planning/research/PITFALLS.md` §P2.1 「Silent visual content goes undersampled」— D-07/D-08 silence-coverage 强制保护的依据，showstopper severity
- `.planning/research/PITFALLS.md` §P2.3 「fail-loud parser for fps schedule」— D-05/D-06 严格 validation 的依据
- `.planning/research/PITFALLS.md` §P2.4 「Full-duration coverage」— D-05.2 的 ±2s tolerance 依据
- `.planning/research/SUMMARY.md` §"Phase 4" + §"Locked schedule.json schema" — D-01 schema 来源
- `.planning/research/STACK.md` — PySceneDetect / silero-vad pin 来源

### 现有代码（必读）
- `agent/tools.py:cmd_extract_frames` (line ~310) — 单段 ffmpeg 调用，`extract_frames_batch` 复用其逻辑（D-10）
- `agent/state.py` (Phase 2) — `append_event` / `derived_state`；本 phase 用它做 segment-level resume
- `agent/io.py:ffprobe_video` (Phase 3 D-21) — 拿 video duration 用于 schedule validation D-05.2
- `agent/sources/_common.py` — Phase 3 sources 模式参考

### 待新增 / 修改文件
- `agent/scheduler.py` — **新**，Schedule + Segment dataclasses + validate
- `agent/scenes.py` — **新**（可选，PySceneDetect 调用 + 输出 scenes.json）
- `agent/silence.py` — **新**（可选，silero-vad 调用 + 输出 silence_map.json）
- `agent/tools.py` — 新增 `cmd_extract_frames_batch` / `cmd_detect_scenes` / `cmd_detect_silence`；argparse + cmds dict
- `requirements.txt` — `PySceneDetect>=0.6.7.1` 加入；可能 `silero-vad>=5.1` 显式 pin
- `agent/state.py` — 可能扩展 `derived_state` 处理 segment-level events（D-14 落地）；建议添加 helper `derived_segment_state(events, stage="extract_frames_batch") -> set[int]` 返回已完成 segment indices

### 不修改的文件
- `agent/tools.py:cmd_extract_frames` 单段接口（FPS-07 + D-14 — `-vsync vfr` 已在 Phase 3 加了，本 phase 不再改）
- `agent/sources/`（Phase 3 territory）
- `vendor/`、老归档目录
- 现有 `seg_<start>_<index>.jpg` 文件名 grammar

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent/io.py:write_json_atomic`** + sidecar (Phase 2) — 当前 schedule.json 由 Claude 直接 Write 工具写入，**不**走 atomic-write（用户/Claude 主动手写的产物）；scenes.json / silence_map.json 由工具产生，走 atomic-write
- **`agent/io.py:ffprobe_video`** (Phase 3) — D-05.2 校验 full-duration coverage 时拿 duration
- **`agent/state.py:append_event` + `derived_state`** (Phase 2) — segment-level events 落地点（D-11）；可能需要扩展 reducer
- **`agent/tools.py:cmd_extract_frames`** ffmpeg argv (含 -vsync vfr from Phase 3 D-23) — extract_frames_batch 直接调用其内部逻辑，不重复实现
- **`agent/tools.py:75-81` --force flag pattern** — extract_frames_batch 复用此 idiom（D-12）
- **dict dispatch + argparse subparser**（CONVENTIONS）— 3 个新 cmd_* 都按此 pattern 注册

### Established Patterns
- **dataclass for data containers**（Phase 1 / Phase 2 多次） — Schedule / Segment 沿用
- **JSON write idiom** — schedule.json 由 Claude 写时也建议 `json.dumps(..., ensure_ascii=False, indent=2, encoding="utf-8")` 形态，便于人类编辑
- **Validation 抛 dedicated 异常** — `ScheduleValidationError(ValueError)` 类似 `BudgetExceeded(RuntimeError)` (src/budget.py:60)
- **fail-loud subprocess** — `subprocess.run([..., "ffprobe"], check=True, capture_output=True)`（PySceneDetect / silero-vad 同形态）

### Integration Points
- **`agent/tools.py` cmds dict** — 加 3 个新条目：`extract_frames_batch / detect_scenes / detect_silence`
- **`agent/tools.py` argparse subparsers** — 新增 3 个 parser
- **`requirements.txt`** — PySceneDetect 新加；silero-vad 显式 pin（如果 faster-whisper 间接依赖版本不够）
- **`agent/state.py:derived_state`** — 当前只输出 stage-level dict；本 phase **可能**需要新 helper 来按 segment_index 聚合 events（D-14 落地）
- **`output/<slug>/`** — 新加 schedule.json / scenes.json / silence_map.json 三个 artifact；都纳入 doctor 子命令的 `_DOCTOR_ARTIFACTS` 列表？建议是的（Phase 2 D-15/D-16 doctor 列表是开放扩展），但本 phase 落 doctor 显示这件事是 Claude's Discretion（planner 决定）

### State.jsonl 事件 schema 扩展
当前 `agent/state.py` 的 Event 定义没有 `details.segment_index`。需要核对 Phase 2 schema 是否允许任意 details dict。回顾 Phase 2 D-13 schema：
```json
{"ts": "...", "stage": "...", "status": "...", "params_hash": "...", "details": {...optional}}
```
`details` 是 optional dict，所以加 `segment_index` 字段是 additive，不破坏 schema_version 1。**Phase 2 D-14 字面禁止 day-1 segment 级 events** —— 本 phase 是 Phase 4 落地点，所以现在是合法时机。

</code_context>

<specifics>
## Specific Ideas

- **核心哲学锚点：FPS-05 / FPS-06 工具 NEVER auto-promote**。这是 K5 "Claude is decider" 在本 phase 的具体形态。哪怕 detect_scenes 跑出来明显的 12 个段落，工具也不能自动写 schedule.json —— 必须 Claude 看完 scenes.json 后用 Write 工具自己写 schedule。这条在 plan / executor 的 acceptance criteria 里要强制：grep `scenes.json` 在 cmd_extract_frames_batch 里**不出现**（说明 batch 不读 scenes，只读 schedule）。
- **silence-coverage 是 Phase 4 的隐藏价值**：纯讲解视频 / 慢节奏教程里有大量 PPT 翻页 / 屏幕示意图等"安静但有视觉"的内容，没有 silence 检测时 Claude 倾向于写 fps 0.05 + 高频代码段，把 PPT 翻页全 skip 掉。FPS-04 强制覆盖让这个失败模式完全消失。
- **resume-aware via state.jsonl** 是 Phase 2 D-14 deferred-to-Phase-4 的兑现。10 分钟视频可能切 8-10 个 segments，跑到第 7 段 ffmpeg 崩了，重跑应该跳过前 6 段。这个是 D-09 D-10 D-11 共同实现的能力。
- **schedule.json 由 Claude Write 工具直接写**——不需要 CLI 子命令"生成 schedule"。Claude 看完字幕（Phase 5 plan.md 给出的策略 reasoning）+ scenes/silence 决策支持后，直接 Write 到 `output/<slug>/schedule.json`。工具的工作只是"读这个 JSON、严格 validate、跑 ffmpeg"。这对应 K5 决策权不外移。

</specifics>

<deferred>
## Deferred Ideas

- **Auto-fps-plan from scenes + silence**（REQUIREMENTS.md SRC-V2-01 — wait, that's source v2; correct ref is "auto-promote scenes to schedule" which is anti-feature per FPS-05）—— 永久不做，违反 K5
- **Segment-级 override of `default_scale` / `default_quality`** — 不在 v1 范围；YAGNI（D-03）
- **Schedule.json 多版本（v2 with 更多 metadata）** —— 等真实需要时（首次 fail to express）再 bump，docs/schema-migration.md runbook 已有 pattern
- **进度条 / tqdm UI** —— stdout 简单 print 即可（CONVENTIONS no tqdm in cmd_* idiom）
- **schedule.json validation 在写入时就触发**（即 Claude Write 时 hook 一下校验） —— Claude Code 主流程不支持这种 hook；让 cmd_extract_frames_batch 启动时 validate 就够了
- **detect_scenes / detect_silence 自动 trigger 在 transcribe 之后** —— 工具不主动；用户/Claude 显式跑（与 K5 一致）
- **PySceneDetect 的 content-type / threshold 自适应** —— v1 用默认；planner 可暴露 --threshold flag 给后续调优用
- **Multi-pass schedule (一次抽帧后 Claude 看一轮，再写第二份 schedule.json refine 去细抽)** —— 用户当前用 cmd_extract_frames 单段补抽就足够；schedule.json 是 first-pass 工具，refine 走 cmd_extract_frames（FPS-07 + D-14 共存模型）

</deferred>

---

*Phase: 04-frame-fps-automation-schedule-json-extract-frames-batch*
*Context gathered: 2026-05-01*
*Mode: auto (gsd-discuss-phase --auto, all grey areas auto-resolved with recommended answers)*
