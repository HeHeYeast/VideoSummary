# VideoSummary：让 Agent 拥有"看视频"能力

> 让 Claude Code / Agent 能够消化 B 站等学习类视频，输出高质量 Markdown 笔记，方便后续与 Agent 对话与检索。

---

## 一、项目目标

- **输入**：B 站（及其他主流平台）视频 URL
- **输出**：结构化 Markdown 笔记（含时间戳、关键帧截图、代码/公式提取、术语表、思考题）
- **形态**：CLI 工具 → 进一步封装为 MCP Server，供 Claude Code 直接调用
- **核心价值**：把"花 1 小时看视频"压缩为"花 5 分钟读笔记 + 随时与 Agent 对话追问"

---

## 二、可行性结论

**完全可行，技术栈成熟。** 核心思路不是让 AI 真的"看"视频，而是把视频转成 AI 能处理的文本 + 图像：

1. 音频通过 ASR（Whisper 系列）转成带时间戳的文本
2. 关键帧通过 ffmpeg + 感知哈希抽取后，喂给视觉模型做 OCR / 描述
3. 两路信息按时间轴对齐，再交给 LLM 分段总结、精修

---

## 三、整体工作流（路径：音频 + 关键帧）

```
┌─────────────────────────────────────────────────────────┐
│  Stage 1: 采集                                          │
│  B站URL → yt-dlp → video.mp4 + 元数据(标题/UP主/简介)   │
│         → 优先抓官方字幕/AI字幕（有则跳过 ASR）          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Stage 2: 并行处理                                       │
│                                                          │
│  音频支线:                  视觉支线:                    │
│  ffmpeg 抽音频              ffmpeg 抽关键帧              │
│       ↓                          ↓                       │
│  faster-whisper(GPU)        感知哈希去重                  │
│       ↓                          ↓                       │
│  带时间戳转录               帧图片 + 时间戳               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Stage 3: 时间轴对齐                                     │
│  把帧插入到转录文本的对应时间点                          │
│  [00:15] 今天讲迭代器                                    │
│  [00:18] <图: PPT "Iterator Pattern">                    │
│  [00:32] 看这段代码 ...                                  │
│  [00:33] <图: 代码截图>                                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Stage 4: 视觉理解                                       │
│  Claude Vision 对关键帧 OCR / 描述                       │
│  → 代码、公式、图表全部文字化                             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Stage 5: 分段总结                                       │
│  按章节 / 10~15min 切片 → 每段独立总结 → 合并             │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Stage 6: 生成 Markdown                                  │
│  概要 / 目录 / 分章节详解 / 术语表 / 思考题              │
└─────────────────────────────────────────────────────────┘
```

---

## 四、关键帧抽取策略

不能简单"每 N 秒一张"，否则大量重复且漏掉关键画面。三招组合：

1. **场景切换检测**：`ffmpeg -vf "select='gt(scene,0.3)'"` —— PPT 翻页、画面突变时才抽
2. **感知哈希去重**：用 `imagehash` 比较，相似的只保留一张
3. **语音锚点辅助**：转录里出现"看这张图 / 这段代码 / 如图所示"时，强制在该时间点抽帧

经验值：1 小时视频通常留下 **20~50 张真正有信息量**的帧。

---

## 五、文档质量保证（核心难点）

质量问题主要四类：**幻觉、遗漏、结构差、颗粒度错**。对应解法：

### 1. 抗幻觉：强制时间戳引用
让 Claude 总结时，每个论点必须带 `[时间戳]` 回指原文。好处：
- 能一键跳回视频验证
- 模型被"有据可依"约束，幻觉骤降

### 2. 抗遗漏：分段 + 覆盖率审查
- 长视频按 **10~15 分钟**切片，避免长上下文注意力稀释
- 最后做 **覆盖率审查**：把转录 + 总结一起喂给 Claude，问"哪些重要概念在转录里出现但总结里没有？"—— 这一步能捞回大量漏点

### 3. 结构化：固定模板
不让模型自由发挥，统一模板：

```markdown
# {标题}
> UP主 | 时长 | 原链接

## TL;DR（3 句话）
## 核心概念
## 章节详解
  ### [00:00-05:30] 章节名
  - 要点
  - ![关键帧](frame_01.jpg)
  - 代码 / 公式（从帧 OCR 出来）
## 术语表
## 我应该思考的问题
## 延伸阅读
```

### 4. 多轮精修：generate → critique → revise
单次生成 ≠ 终稿。三步：
- **Draft**：先出初稿（Sonnet）
- **Critique**：换 prompt 让 Claude 扮演挑刺的老师，列出问题
- **Revise**：根据批评意见重写（Opus）

代价是 token 翻 2~3 倍，但学习笔记值得。

### 5. 人机协同闸门
- **置信度标注**：Whisper 低置信度的句子在文档里标灰
- **专业术语词表**：通过 Whisper 的 `initial_prompt` 喂入框架名 / 人名，识别率显著提升
- **首次审阅**：你审一下结果，把反馈沉淀成 prompt 的 few-shot 例子

---

## 六、技术选型（有 GPU 的情况）

| 环节 | 推荐方案 | 备注 |
|---|---|---|
| 下载 | `yt-dlp` | B 站支持好，需 cookie 拿高清/会员 |
| 音频抽取 | `ffmpeg` | 标配 |
| 转录 | `faster-whisper` large-v3 | GPU 跑 1h 视频约 2~5 分钟，中文顶级 |
| 字幕优先 | yt-dlp 原生字幕接口 | 有则跳过 ASR |
| 抽帧 | `ffmpeg` 场景检测 + `imagehash` 去重 | |
| 视觉理解 | Claude Sonnet 4.6（vision） | 代码/公式 OCR 强 |
| 分段总结 | Claude Sonnet 4.6 | 性价比 |
| 精修 / Critique | Claude Opus 4.6 | 质量天花板 |
| 集成 | MCP Server | 与 Claude Code 无缝 |

### 各环节模型能力评估

- **Whisper large-v3**：当前开源 ASR 中文 SOTA，对带口音的技术讲座足够。GPU 显存 ≥ 6GB 即可。
- **Claude Vision**：能稳定识别 PPT 文字、代码截图、数学公式（LaTeX）、流程图描述。对手写板书识别率较低，可补 PaddleOCR。
- **Claude Sonnet/Opus 4.6（1M context）**：1M token 上下文意味着即使一个 4 小时课程的完整转录也能一次塞进去——但出于质量考虑仍建议分段。
- **结论**：**当前模型能力完全胜任**这个 pipeline，瓶颈不在模型，而在工程编排和 prompt 设计。

---

## 七、相关工作调研

社区已有不少类似项目，但**带关键帧视觉理解 + 多轮精修 + MCP 集成的组合较少**，这是我们的差异化空间。

### 已有项目

| 项目 | 特点 | 与本项目差异 |
|---|---|---|
| [JimmyLv/BibiGPT-v1](https://github.com/JimmyLv/BibiGPT-v1) | 最知名的 B 站一键总结工具，Web 形态，覆盖 B站/YouTube/抖音/小红书等 | 纯字幕 → LLM，无视觉帧理解；非本地工具链 |
| [wendy7756/AI-Video-Transcriber](https://github.com/wendy7756/AI-Video-Transcriber) | 支持 YouTube/B站，字幕优先，无字幕回退 Whisper | 无关键帧、无质量精修闭环 |
| [liang121/video-summarizer](https://github.com/liang121/video-summarizer) | **已实现为 Claude Code skill**，支持 1800+ 平台 | 思路最接近，但仍以转录为主，无视觉帧 |
| [302ai/302_video_summary](https://github.com/302ai/302_video_summary) | 支持 B站/抖音/小红书，能生成思维导图 | SaaS 形态，闭源依赖 |
| [Yuiffy/BiliGPT](https://github.com/Yuiffy/BiliGPT) | B 站视频内容一键总结 | 早期项目，纯字幕 |
| [martinopiaggi/summarize](https://github.com/martinopiaggi/summarize) | 多源、兼容任意 OpenAI 协议 LLM（含本地） | 纯转录摘要 |
| [AIAnytime/YouTube-Video-Summarization-App](https://github.com/AIAnytime/YouTube-Video-Summarization-App) | Llama2 + Haystack + Whisper + Streamlit | YouTube 为主，CPU 友好 |
| [Mattral/YouTube-Video-Summarizer-Using-Whisper-and-LangChain](https://github.com/Mattral/YouTube-Video-Summarizer-Using-Whisper-and-LangChain) | LangChain stuff/refine/map_reduce 三种长文本策略 | 可借鉴长文本总结策略 |
| [BibiGPT × OpenClaw skill (2026)](https://bibigpt.co/en/blog/posts/openclaw-bibigpt-skill-ai-agent-video-2026-en) | 已用 Claude Sonnet 4.6 做 B 站中文总结 | 闭源服务，但验证了模型选型方向 |

### 我们的差异化定位

1. **关键帧 + 视觉理解**：保留 PPT、代码、公式等"非语音信息"，这是上面绝大多数项目缺失的
2. **质量闭环**：覆盖率审查 + critique-revise 双轮精修
3. **本地优先**：GPU Whisper + 本地存储，隐私可控、可离线转录
4. **MCP 原生**：直接成为 Claude Code 的能力，而不是又一个独立 Web App
5. **笔记是"对话基座"**：输出文档的结构是为了后续与 Agent 对话而设计，不只是给人读

---

## 八、推进路线图

分 3 个里程碑，每步独立可用：

### M1 — 跑通 baseline
- yt-dlp 下载 + 元数据
- faster-whisper 转录（优先抓字幕）
- 单次 Claude 调用 → 模板化 Markdown
- **交付物**：CLI `videosum <url>`，输出纯文本笔记

### M2 — 加入视觉
- ffmpeg 场景检测抽帧 + imagehash 去重
- Claude Vision 处理关键帧
- 时间轴对齐，帧嵌入 Markdown
- **交付物**：图文混排笔记

### M3 — 质量与集成
- 分段总结 + 覆盖率审查
- critique-revise 多轮精修
- 封装为 MCP Server
- 可选：本地向量库做跨视频 RAG
- **交付物**：Claude Code 中 `/summarize-bilibili <url>` 一键可用

---

## 九、成本估算（单条 1 小时视频）

- 下载 + 转录（本地 GPU）：免费，约 5 分钟
- 关键帧视觉理解：30~50 张图 × Sonnet ≈ ¥1~2
- 分段总结 + 精修：≈ ¥2~5
- **合计：¥3~7 / 小时视频**

---

## 十、待确认事项

1. Python 版本？是否已装 `ffmpeg`？
2. GPU 型号 / 显存？（决定 Whisper large-v3 还是 medium）
3. Claude API key 是否就绪？
4. 是否从 M1 起步？

---

## 十一、实施现状（v4，2026-04-09 更新）

> 这部分记录落地过程中与原设计的偏差、已知问题和正在做的修复。原设计部分保留不动。

### 1. 实际落地的 pipeline

与原设计基本一致，但有以下偏差：

| 环节 | 原设计 | 实际 | 原因 |
|---|---|---|---|
| ASR | GPU faster-whisper large-v3 | **CPU** faster-whisper **small** | Windows cuBLAS/cuDNN 没装好, CUDA 推理崩溃 |
| 视觉 | Claude Sonnet 4.6 vision | **qwen3-vl-plus** (via VectorEngine 中转) | 项目决定用中转避免 Claude Code 依赖; gemini 系列不听 max_tokens |
| 抽帧 | 场景切换 + 语音锚点 + 哈希去重 | 只有 **1fps + pHash 去重 + 硬上限** | 场景检测和语音锚点未实现, 欠债 |
| 分段总结 | Claude Sonnet | **gpt-4o-mini / deepseek-v3.2 / kimi-k2** fallback 链 | 成本控制, 但 deepseek/kimi 长期被中转站限流, 实际全落到 gpt-4o-mini |
| 精修 | critique-revise 双轮 | **仅 polish 一次**, 只做衔接建议 | M3 目标未到 |
| 覆盖率审查 | 有 | **未实现** | 欠债 |
| MCP Server | 有 | **未实现** | M3 目标未到 |

### 2. 当前代码结构

```
src/
├── cli.py          # 入口, --mode test|prod, --test-duration 截断
├── pipeline.py     # 6 stage 编排 + 缓存
├── download.py     # yt-dlp
├── asr.py          # faster-whisper + VAD + 幻觉过滤
├── frames.py       # 1fps + pHash + cap
├── vision.py       # 单帧 → 文本描述
├── llm_client.py   # VectorEngine 中转, cheap/quality 双 key
├── budget.py       # BudgetGuard precheck/commit + PRICE_TABLE
└── summarize.py    # v4 文档生成: outline → write_section → polish → assemble
config/
├── budget_test.yaml  # 总预算 ¥0.40, 前 2 分钟截断, frame_cap=15
└── budget_prod.yaml  # 总预算 ¥0.80 (尚未跑过)
```

### 3. 已知问题与修复进度

记录首次跑通后暴露的所有问题:

| # | 问题 | 严重性 | 状态 |
|---|---|---|---|
| 1 | **ASR 对英文音频产生中文幻觉**: `language="zh"` 强制参数 + 视频实际是英文 → 00:29 之后字幕全是 "许多的许多" 类乱码 | 🔴 致命 | ✅ 已修: `language=None` 自动检测 |
| 2 | **outline 时间戳全挤在视频开头 13%**: `transcript[:20000]` 对 1 小时视频丢后 2/3, 模型只看到开头 | 🔴 致命 | ✅ 已修: `_compress_transcript_for_outline` 均匀抽样 |
| 3 | **writer 注水编造**: `min_words=200` 下限逼 gpt-4o-mini 凑字数生成废话 | 🔴 致命 | ✅ 已修: 删 min_words, 只保留 max_words |
| 4 | **时间戳幻觉无校验**: writer 输出的 [HH:MM:SS] 凭空生成, 均匀分布暴露编造 | 🔴 致命 | ✅ 已修: `validate_timestamps` 8s 容差删除整行 |
| 5 | **LLM 分配 frame_ids 错漏**: outline 让模型输出帧归属, 经常漏分重分 | 🟠 高 | ✅ 已修: `assign_frames_to_sections` 代码按时间几何确定性分配 |
| 6 | **帧与字幕两份割裂输入**: writer 自己对齐对不上 | 🟠 高 | ✅ 已修: 按时间戳 merge 成统一时间线 (含 📺 标记) |
| 7 | **预算耗尽静默截断**: 6 节只写 3 节, 用户看不到警告 | 🟠 高 | ✅ 已修: assemble 顶部 ⚠️ banner + TOC 未生成节标红 |
| 8 | **frame_cap=5 对 8:40 视频太少**: 平均每 100s 才一帧 | 🟠 高 | ✅ 已修: test 模式 5→15 |
| 9 | **完整代码合集是碎片拼接**: 7 个 fenced block 顺序粘贴, 没拼成可运行函数 | 🟠 高 | ✅ 已修: writer 强制在 section 末尾输出 `### 本节完整代码` 整块, assemble 优先取这些块 |
| 10 | **图片路径是 Windows 绝对路径反斜杠**: `![](output\...\frame_000001.jpg)` 在 md 里不显示 | 🟠 高 | ✅ 已修: writer 拿到的是相对路径 `frames/frame_000001.jpg` |
| 11 | **writer 偷懒所有节都引用同一张帧**: 没帧的节也硬插第一张 | 🟠 高 | ✅ 已修: prompt 加 "本节没帧时不要插图" + `validate_timestamps` 收尾 |
| 12 | **test 模式预算数学不可行**: ¥0.10 总预算 < 6 节 writer 单独调用成本 | 🟠 高 | ✅ 已修: 总预算 ¥0.10 → ¥0.40 + 默认截取前 120 秒 |
| 13 | **budget.py `estimate_asr_cost` 笔误**: 引用了不存在的 `ASR_PRICE_PER_MIN` | 🟡 定时炸弹 | ✅ 已修: 改为 `ASR_PRICE_PER_1M` 按 token 估算 |
| 14 | **kimi-k2 / deepseek-v3.2 中转站长期 429**: 所有请求走到 gpt-4o-mini fallback, 中文写作质量打折 | 🟡 中 | ❌ 未解决: 待换时段/quality 组 key/切换主模型 |
| 15 | **polish 只做衔接标注, 不做覆盖率审查, 不改写正文** | 🟡 中 | ❌ 未做: 排第二批 |
| 16 | **writer 上下文稀薄**: 没有上一节摘要 + 全局视频意图 | 🟡 中 | ❌ 未做: 排第二批 |
| 17 | **视觉 80 字上限对代码/PPT 太紧**: 代码截图无法完整 OCR → writer 只能编代码 | 🟡 中 | ❌ 未做: 排第二批 (分层 TINY/DETAIL) |
| 18 | **1fps+pHash 对教学视频不够鲁棒**: 静态画面浪费配额, 快切段漏帧 | 🟡 中 | ❌ 未做: 排 v5 (语音锚点 + 场景检测) |
| 19 | **whisper CPU + small**: 长视频慢, 对专有名词识别差 | 🟢 低 | ❌ 未做: 待装 cuDNN 或换 medium |
| 20 | **prod 模式从未跑过**: budget_prod.yaml 是纸面配置 | 🟢 低 | ❌ 未做: 等 test 质量达标 |

### 4. 第一批修复 (已完成, 本次提交)

- `summarize.py`: 删 min_words + validate_timestamps + assign_frames_to_sections + merge_transcript_with_frames + _compress_transcript_for_outline + assemble banner + 完整代码合并 + 相对路径插图
- `pipeline.py`: `language=None` + test_duration 截断 segs/frames/meta
- `cli.py`: `--test-duration` 参数 (test 默认 120s, prod 默认 0)
- `budget.py`: ASR_PRICE_PER_1M 修复 + kimi-k2 价格条目
- `config/budget_test.yaml`: total ¥0.20→¥0.40, frame_cap 5→15, vision call 5→15, section call 3→8, vision stage ¥0.05→¥0.15

### 5. 第二批 (待做)

- 视觉分层 prompt: 先 TINY (5 字类型标签 + 30 字) 再对 code/PPT 帧二次 DETAIL (200 字 + 完整 OCR)
- outline transcript 压缩: 从均匀抽样升级为 "便宜模型每段压成一行 → 再喂 outline 模型" (B 方案)
- polish 覆盖率审查: 让 polish 模型对照原始字幕指出遗漏要点
- 跨章节上下文注入: 写手拿到上一节结尾 + 下一节标题列表
- 语音锚点抽帧: 字幕里出现 "看这里/这段代码" 时强制在该时间点抽帧
- 字幕健康检查: 检测幻觉特征 (n-gram 重复 / 填充词高频)

### 6. 留到 v5

- 多信号加权抽帧 (场景检测 + OCR 变化 + 语音锚点 + 均匀)
- 模型 A/B 测试框架
- 优雅降级预算策略 (guaranteed / elastic / priority_order)
- MCP Server 封装
- 本地向量库跨视频 RAG

---

## 参考资料

- [JimmyLv/BibiGPT-v1](https://github.com/JimmyLv/BibiGPT-v1)
- [wendy7756/AI-Video-Transcriber](https://github.com/wendy7756/AI-Video-Transcriber)
- [liang121/video-summarizer (Claude Code skill)](https://github.com/liang121/video-summarizer)
- [302ai/302_video_summary](https://github.com/302ai/302_video_summary)
- [Yuiffy/BiliGPT](https://github.com/Yuiffy/BiliGPT)
- [martinopiaggi/summarize](https://github.com/martinopiaggi/summarize)
- [AIAnytime/YouTube-Video-Summarization-App](https://github.com/AIAnytime/YouTube-Video-Summarization-App)
- [Mattral/YouTube-Video-Summarizer-Using-Whisper-and-LangChain](https://github.com/Mattral/YouTube-Video-Summarizer-Using-Whisper-and-LangChain)
- [BibiGPT × OpenClaw 2026 Skill](https://bibigpt.co/en/blog/posts/openclaw-bibigpt-skill-ai-agent-video-2026-en)
