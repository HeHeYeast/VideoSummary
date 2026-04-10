# VideoSummary v2: Agent-based 架构设计

> 这份文档取代早期的刚性 pipeline 方案,采用"离线数据层 + Agent 写作层"的混合架构。
> 核心思路:**像人一样边看边记**——机械工作(下载/ASR/抽帧)离线做完,写作决策交给一个强模型 + 工具集,用滑动窗口 + 章节边界 compact 管理长视频注意力。

---

## 一、为什么推翻 v1 pipeline

v1 的根本问题不是某个环节没做好,而是**架构层面**的:

1. **错误单向级联**:outline 切错了时间段 → writer 拿到错字幕 → 写出垃圾 → polish 救不回来。中间任何一步没有"回头看"的权力。
2. **决策点全在弱模型手里**:gpt-4o-mini 做 outline、deepseek 做 writer,每一步都在凭残缺的局部视图拍板。
3. **写作被字数下限逼着编废话**:`min_words` 强制写够 400 字 → LLM 没得写只能填"这个生成器可以轻松地..."这种无信息句。
4. **预算耗尽静默截断**:6 节视频只写了 3 节,文档看起来完整但内容残缺。

**v2 的换方向**:决策权集中到一个强模型,工具只提供原始数据。这符合业界经验:**一个强模型 + 工具 通常打败 N 个弱模型串联**。Claude Code、STORM、GPT-Researcher 都在这个方向。

---

## 二、整体架构

```
┌─────────────────────────────────────────────────────┐
│  离线数据层 (Pipeline,一次性,可缓存)                  │
│                                                      │
│  下载 → ASR → 段落聚合 → 候选帧抽取                   │
│                         → 信息量打分 → pass1 分类     │
│                         → CLIP embedding              │
│                                                      │
│  产出: segs.json / frame_store / embeddings.npy      │
├─────────────────────────────────────────────────────┤
│  Agent 写作层 (主循环,强模型 + 工具)                  │
│                                                      │
│  ┌─ Working Memory (窗口内) ──────────┐              │
│  │ · 全局大纲(常驻)                    │              │
│  │ · 最近 1-2 节完整 md                │              │
│  │ · 当前节字幕窗口                    │              │
│  │ · 正在写的草稿                      │              │
│  └─────────────────────────────────────┘              │
│                                                       │
│  ┌─ Long-term Memory (窗口外,磁盘) ───┐              │
│  │ · 已完成章节的 200 字摘要           │              │
│  │ · 术语表 glossary.json               │              │
│  │ · frame_store(帧详情缓存)           │              │
│  │ · 已覆盖时间范围                    │              │
│  └─────────────────────────────────────┘              │
│                                                       │
│  触发: 章节边界 && token > 阈值 → compact             │
└─────────────────────────────────────────────────────┘
```

两层之间通过磁盘文件通信,agent 层完全不关心离线层怎么实现的,换 ASR 模型 / 换抽帧算法都不影响上层。

---

## 三、离线数据层设计

### 3.1 ASR + 段落聚合

继续用 faster-whisper,但必须开 VAD 反幻觉:
- `vad_filter=True`
- `condition_on_previous_text=False`
- `initial_prompt` 喂入领域术语
- 输出后过滤已知幻觉黑名单("请订阅"、"感谢观看")

**新增:段落聚合**。不要让 `get_transcript_window` 死板地按秒切——会切断半句话。离线阶段基于"静音 gap > 1.5s 或 句末标点"把相邻 segment 合并成 `paragraph`:

```python
{
  "para_id": "p0012",
  "start": 327.5, "end": 358.2,
  "text": "完整的一段话",
  "segs": [<原始 segment 列表>]
}
```

`get_transcript_window(start, end)` 返回时自动对齐到最近的段落边界。

### 3.2 抽帧:信息量优先,不是场景切换优先

这是 v2 的关键修正。**场景切换 ≠ 信息量**。

- 讲师走动 / 灯光变化 / 镜头拉近拉远 → 场景变了但**没有新信息**
- PPT 上逐步出现 bullet 的动画 → 场景没变但**有新信息**

所以抽帧分三步:

**Step 1 — 候选帧生成(宽松召回)**

用 PySceneDetect 或 1fps 先抽出一个"候选池",这里允许冗余,目的是不漏。

**Step 2 — 信息量打分**

每个候选帧算一个 `info_score`,由几个廉价信号组合:

| 信号 | 计算 | 含义 |
|---|---|---|
| 文字密度 | PaddleOCR 快速模式,统计字符数 | 幻灯片/代码 > 讲解镜头 |
| 相对前帧新增内容 | 和上一张保留帧的 pHash / CLIP 相似度 | 新增内容越多得分越高 |
| 语音锚点加成 | 转录里出现"看这张图/这段代码/如图所示"时,强制给该时刻 +10 分 | 捕捉讲师主动引导的关键帧 |
| 画面稳定度 | 前后 0.5s 的帧间差分 | 动态模糊的画面扣分 |

**Step 3 — 按分数降采样**

设定 `frame_cap`(比如 50 张/小时),选 top-K。这样同一张 PPT 停留 5 分钟只会抽 1-2 张(第一次出现 + 有大改动时),而一段密集代码演示会抽到所有关键状态。

这个方案比"1fps + pHash"和"纯场景切换"都好:前者漏掉了语音锚点,后者把灯光变化当成新信息。

### 3.3 帧 pass1 分类(离线批量,便宜模型)

所有入选帧过一遍便宜视觉模型做分类 + 简述:

```python
{
  "type": "code | slide | diagram | ui_demo | talking_head | transition",
  "has_text": true,
  "brief": "GDScript 函数定义"   # ≤30 字
}
```

- `talking_head / transition` 直接标记"不值得深读",agent 的 `list_frames` 可过滤掉
- 其他类型进入 frame_store,等 agent 按需调用 `get_frame_detail` 触发 pass2

### 3.4 CLIP embedding

每帧算一个 512 维 CLIP(或 BGE-Visual)embedding,存成 `embeddings.npy`。这是 `search_frames(query)` 的基础——让 agent 能按语义搜帧,不用在长列表里 scan。

### 3.5 frame_store schema

```python
{
  "frame_id": "f0042",
  "timestamp": 327.5,
  "path": "frames/frame_000042.jpg",
  "phash": "a1b2c3d4...",
  "info_score": 8.7,
  "type": "code",
  "brief": "GDScript 函数定义",
  "detail": null,              # pass2 懒加载
  "detail_model": null,
  "detail_cost_usd": null,
  "consumed_by": []            # 被哪些 section 引用过
}
```

规模大时用 sqlite,小规模 json 即可。embeddings 不要塞进 json。

---

## 四、Agent 写作层设计

### 4.1 工具箱(11 个,分 5 组)

**数据读取(免费,纯代码)**
- `get_transcript_window(start_sec, end_sec)` — 按段落边界对齐返回
- `search_transcript(keyword)` — 关键词检索,返回匹配时间段列表
- `list_frames(type_filter=None, time_range=None)` — 可按类型/时段过滤
- `search_frames(query)` — CLIP 图文检索,返回 top-k

**按需深读(付费,有持久化缓存)**
- `get_frame_detail(timestamp)` — 懒加载 pass2,首次调用才花钱,写回 frame_store

**校验(对抗幻觉)**
- `verify_code_against_frames(code, time_range)` — 字符级 substring 匹配,免费
- `verify_claim_against_transcript(claim, time_range)` — 语义级,一次小模型调用

**写作与记忆**
- `submit_section(id, title, markdown)` — 流式提交,落盘,不是最后统一 return
- `review_recent_sections(n=2)` — 主动回顾最近 n 节
- `update_glossary(term, definition, aliases)` — 术语表维护

**流程控制**
- `skip_window(start, end, reason)` — 显式跳过废话(开头"一键三连"、结尾"下期再见")

### 4.2 System prompt 硬约束

**必须写进 system prompt 的规则**:

1. 初始化阶段:先 `list_frames()` + 分段 `get_transcript_window` 建立全局理解,**期间不写任何正文,只输出大纲 JSON**
2. 写作阶段:每个章节**只能读自己时间范围**的字幕窗口,不能偷看其他章节
3. 含代码的章节提交前,**每段代码必须**调用 `verify_code_against_frames`
4. 每写完 2 节**必须**调用 `review_recent_sections`
5. 遇到疑似废话直接 `skip_window`,不要硬写
6. `submit_section` 后禁止再修改已提交章节(保证流式提交的不可变性)

### 4.3 Compact 机制

**触发条件**:`on_submit_section` 之后检查 token 数,超过阈值(建议 40k)才 compact。**绝不在一节中途触发**。

**自定义 compact prompt**(不要用默认),必须保留:
- 全局大纲(原样)
- 已交付章节列表(id + title + 200 字摘要)
- 术语表完整内容
- 已覆盖的时间范围
- 待验证问题列表

**防 thrashing**:compact 后新一轮对话的 system prompt 里必须有"已交付章节不能重写"的硬约束,否则 agent 可能因为"忘了写过"再写一次 s3。

**配合 Tool Result Clearing**:已读过的 transcript_window 和 frame_detail 在 compact 时替换成占位符 `[已折叠: 见 frame_store f0042]`,因为 frame_store 在磁盘上,agent 再要可以重新调工具取,不丢数据。

### 4.4 模型分档原则

| 任务 | 模型档位 |
|---|---|
| 帧 pass1 分类 | 最便宜视觉模型(qwen-vl-plus 最便宜档 / gemini-flash) |
| 帧 pass2 深读 | 强视觉模型,按类型分 prompt |
| **Agent 主写手** | **强文本模型,全程固定不换** |
| verify_claim 小模型 | gpt-4o-mini 档 |
| compact summarization | 中档模型 |

**绝对原则**:主 agent 只能有一个模型,全程不换。换模型会丢对话状态和 tool use 上下文。省钱要在工具内部省,不在 agent 本身省。

### 4.5 Budget self-awareness

把剩余预算暴露给 agent,写进 system prompt:

```
当前状态: 已写 3/8 节, 已花 ¥0.28 / ¥1.00, 剩 ¥0.72
```

每次 submit_section 后更新。agent 可以基于剩余预算主动调整策略(比如发现预算不够时跳过详细的 verify_code)。

---

## 五、实现上需要特别注意的细节

### 5.1 帧-理解对的持久化是系统脊梁

`get_frame_detail` 的行为:
```python
def get_frame_detail(timestamp):
    frame = frame_store.find_nearest(timestamp)
    if frame.detail is None:
        frame.detail = vlm.describe(frame.path, prompt_for(frame.type))
        frame_store.save(frame)   # 立即写回磁盘
    return frame.detail
```

好处:
- 同一帧多次查询只付一次费
- 跨 session 有效,明天重跑命中缓存
- 让 compact 时的激进清理变得安全——清了还能重取

### 5.2 verify 必须分两层,不能只用字符 diff

- **代码 / 精确字符串**:字符级 substring 匹配(帧 OCR 或 transcript 里必须能找到),免费
- **语义断言 / 事实陈述**:小模型判断,一次调用

字符 diff 会把"讲师口述 + 屏幕显示"这种语义一致但表述不同的正确内容误判成幻觉。

### 5.3 时间戳幻觉的事后校验

writer 写出的 `[HH:MM:SS]` 时间戳必须和真实 segs 对齐(±2s 容差)。在 `submit_section` 里做 regex 抽取 + 校验,找不到对应的直接删掉或标红。这是对抗时间戳编造最便宜的手段,必做。

### 5.4 术语表的实体消歧

agent 每次提到一个可能的新术语,如果已经在 glossary 里(或者是某个 term 的 alias),自动替换成 canonical 形式。这保证"K8s"和"Kubernetes"不会在同一份文档里混用。

`update_glossary` 是写操作,agent 主动调用;但**读操作是自动的**——每次 writer prompt 会自动附带一份"本节可能相关的术语子集"(基于关键词匹配)。

### 5.5 预算耗尽不能静默

v1 最大的教训之一。必须:
- 事前估算:outline + N 节 + verify + compact 的总预算是否够,不够直接拒绝启动
- 事中预警:每次 submit_section 后检查剩余预算,剩余 < 20% 时 agent 进入"省电模式"(跳过 verify、缩短描述)
- 事后报警:如果中途确实超预算,文档**顶部**必须有大横幅 `⚠️ 文档不完整: 停止于第 X/Y 节`,未写章节列出来

### 5.6 test 模式要能真的跑完

v1 的 ¥0.10 测试预算在数学上跑不完完整 pipeline。v2 的 test 模式应该是:**只处理前 2 分钟视频**(截断 segs 和 frames),而不是"限制预算"。这样能端到端验证流程,又省钱。

### 5.7 Initializer pass 和 Coding agent 分开

第一次 agent 调用用**专用 system prompt**,只做:读 transcript → 出大纲 → 建初始术语表 → 不写正文。第二次开始才是章节写作循环。这避免 agent 一上来急着写 s1 但没有全局观。

这是 Anthropic 在 long-running agent 博客里明确推荐的模式。

### 5.8 Checkpoint / 可回滚

每次 `submit_section` 后落盘一份 snapshot:
```
work_dir/checkpoints/
  after_s1.json    # working memory + sections_md 全量
  after_s2.json
  after_s3.json
```

如果后面发现 s3 写崩了或 verify 反复失败,可以回滚到 `after_s2` 重跑。对应 Claude Code 的 session snapshot。

### 5.9 VectorEngine function calling 冒烟测试

动手之前先跑一个 5 行的最小 function calling 测试,确认中转站在选定模型上参数能正确返回。中转对 tool use 的支持质量参差不齐,这一步不做就写大量代码会浪费时间。

### 5.10 工具返回要控制长度

- `get_transcript_window` 硬上限 3000 字
- `get_frame_detail` 硬上限 1000 字
- `list_frames` 每帧只返回 id + ts + type + brief(30 字),不返回 path 或 embedding
- `search_frames` / `search_transcript` 只返回 top-10,不要全量

单个工具返回超过 2000 token 就是在炸 context,必须在工具实现里截断。

### 5.11 工具调用轮数硬上限

`max_tool_calls = 30`。超过就强制结束,输出当前已有内容 + 警告。防止 agent 陷入"我再看一眼"的过度探索循环。

### 5.12 视频类型预判(为未来扩展留口)

Initializer pass 多做一步:判断视频类型(`tutorial / talk / vlog / documentary`),对应加载不同的 system prompt 模板。v1 只实现 `tutorial`,其他类型默认降级到 `tutorial`。但字段要留好,未来加新类型时不动架构。

---

## 六、落地路线图

### Week 0 — 离线数据层升级(1-2 天)

完全不涉及 agent,只升级数据质量:
- [ ] 段落聚合加进 `asr.py`
- [ ] `frames.py` 改成"候选帧 + 信息量打分 + top-K"
- [ ] 新增 `pass1_classify.py`(便宜视觉模型分类)
- [ ] 新增 `embed.py`(CLIP embedding)
- [ ] 新增 `frame_store.py`(sqlite or json 持久化)

这一步做完,**哪怕不跑 agent**,光看 frame_store 的 brief 列表就能肉眼看出质量提升。

### Week 1 — Agent 冒烟测试(2 天)

- [ ] VectorEngine function calling 最小测试(5 行)
- [ ] 新增 `agent_writer.py`,只实现 `get_transcript_window` + `submit_section` 两个工具
- [ ] 固定模型 gemini-2.5-pro(或可用的最强文本模型)
- [ ] 目标:能跑完一个短视频、格式正确、不评质量

### Week 2 — 完整工具集 + 滑动窗口(4 天)

- [ ] 补齐 11 个工具
- [ ] Compact 机制 + 自定义 compact prompt
- [ ] Budget self-awareness 写进 prompt
- [ ] 用 Godot 视频跑一次,对比 v1 的三项硬指标

### Week 3 — 回顾 + 校验 + 鲁棒性(3 天)

- [ ] `review_recent_sections` + `verify_code_against_frames` + `verify_claim_against_transcript`
- [ ] 时间戳事后校验
- [ ] Checkpoint 机制
- [ ] 预算耗尽报警
- [ ] 用 3 种不同类型视频测试(讲解/PPT/代码)

---

## 七、评判指标(硬指标,不能靠感觉)

每次版本迭代必须填这张表:

| 指标 | 度量方法 | 及格线 |
|---|---|---|
| 时间戳一致性 | 抽样 10 个 `[HH:MM:SS]`,人工对照视频 | ≥ 9/10 |
| 代码完整性 | 视频中出现的每个函数/代码块是否完整出现 | 100% |
| 无废话率 | 抽 10 段,数填充句数量 | ≤ 2/10 |
| 章节完整率 | 实际写出的节数 / 计划节数 | 100% |
| 术语一致性 | 同一概念是否用统一命名 | ≥ 95% |
| 单条视频成本 | 总 USD / CNY | 目标 ¥3-7 / 小时视频 |

记录到 `experiments/` 目录,每次架构改动都重跑一次。

---

## 八、待决策事项

1. 主 agent 模型选什么?gemini-2.5-pro / deepseek-v3.2 / glm-4.6——先跑 function calling 冒烟测试筛掉不稳的
2. frame_store 用 json 还是 sqlite?<500 帧用 json 够,大规模用 sqlite + sqlite-vec
3. 语义段落聚合的 gap 阈值?建议 1.5s 起步,实测再调
4. `info_score` 各信号的权重?先等权重,跑一个视频后人工看 top-K 结果再调

---

## 参考

- Anthropic: [Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- Anthropic: [Context engineering: memory, compaction, and tool clearing](https://platform.claude.com/cookbook/tool-use-context-engineering-context-engineering-tools)
- Claude Code 架构逆向分析(多篇)
- Stanford STORM / LongWriter AgentWrite(v1 的部分 prompt 参考)
