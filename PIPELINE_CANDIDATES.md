# VideoSummary：分环节候选方案与失败模式

> 基于对 6 个同类开源项目的源码/文档调研，以及对 ASR、关键帧抽取、视觉理解三大环节的专项调研整理而成。
> 每个环节都给出**主选 / 备选 / 避坑**，并标注**何时切换**。

---

## 0. 调研核心结论（先看这个）

1. **同类项目无一做关键帧 + 视觉理解**（BibiGPT-v1、AI-Video-Transcriber、liang121/video-summarizer、302ai、martinopiaggi、Mattral 全部纯音频）。这是我们的差异点，但也意味着**这条路没有现成抄作业的对象**。
2. **原方案里两个环节确认有坑**：
   - `ffmpeg select=gt(scene,X)` 对 PPT 类讲座**效果差**（为电影硬切设计，对淡入淡出/动画/静态长画面表现都不好）
   - `faster-whisper large-v3` 裸用对中文有**幻觉问题**（v3 比 v2 幻觉率约 4×，常见伪造："请订阅"、"感谢观看"、"字幕由…"）
3. **中文 ASR 有更优解**：FunASR Paraformer-Large、SenseVoice 在中文 benchmark 上 CER 显著优于 Whisper。
4. **同类项目的长文本处理**：主流是 **map-reduce**（martinopiaggi 用 10k 字符并行 30 路），LangChain 的 stuff/refine/map-reduce 三选一里 **refine 质量最好但慢**。
5. **没有任何项目实现 critique-revise 精修闭环** —— 这也是我们的差异化。

---

## 1. 各环节候选方案

### Stage 1: 视频下载

| 方案 | 状态 | 说明 |
|---|---|---|
| **主选**：`yt-dlp` | 同类项目全部使用 | B 站支持好，1800+ 站点 |
| 备选：`bilix` | 备用 | B 站原生 BV 号支持更细致，断点续传强 |
| 避坑：Cobalt service | ❌ | 多一个外部服务依赖，无必要 |

**失败模式**：高清/会员视频需 cookie；B 站合集要 `-p` 参数；偶尔反爬升级导致失败 → 升级 yt-dlp 即可。

---

### Stage 2: 字幕优先抓取（很重要，省 ASR 算力）

| 方案 | 说明 |
|---|---|
| **主选**：yt-dlp `--write-auto-subs --write-subs` | 优先拿 UP 主上传字幕 |
| 备选：B 站 player API（`api.bilibili.com/x/player/v2`） | 直接拿 AI 字幕 JSON，比 yt-dlp 更稳 |

**失败模式**：B 站学习类视频**绝大多数没有字幕**——不要把字幕当主路径，把它当 bonus。**实际上 ASR 才是主路径。**

---

### Stage 3: ASR 转录（**这里是质量第一道关卡**）

> 调研发现：**bare faster-whisper large-v3 对中文不够稳，必须加 VAD + 反幻觉措施，或者直接换中文专用模型。**

| 方案 | 优势 | 劣势 | 何时用 |
|---|---|---|---|
| **主选 A**：**SenseVoice-Small** (FunAudioLLM) | 中文 SOTA 之一，比 Whisper-large **快 ~15×**，自带情感/事件标签 | 词级时间戳弱（影响关键帧对齐精度） | 纯中文讲座、不需要精确词级对齐 |
| **主选 B**：**Paraformer-Large** (FunASR) | WenetSpeech CER ~1.68（Whisper-v3 ~5.14） | 对中英混杂稍弱 | 纯中文技术讲座 |
| **备选**：**WhisperX** (faster-whisper + Silero VAD + forced alignment) | **词级时间戳精确**，自带 VAD 抑制幻觉，可加 pyannote 说话人分离 | 比 SenseVoice 慢 | 需要精确时间戳做关键帧对齐；中英混杂多的视频 |
| 备选：**FireRedASR** | 当前公开 Mandarin benchmark SOTA，支持方言 | 较新，工程化资料少 | 方言/口音重 |
| **避坑**：bare `faster-whisper` 不开 VAD | ❌ | 容易输出"请订阅/感谢观看"幻觉 |  |

**强制最佳实践（无论选哪个 Whisper 系）**：
- `vad_filter=True`（faster-whisper 内置）或外接 Silero VAD
- `condition_on_previous_text=False`（防止重复循环）
- `initial_prompt` 喂入领域术语表（框架名、人名、英文缩写）
- 后处理过滤已知幻觉字符串白名单

**切换条件**：
- 默认走 **SenseVoice**（快、中文强）
- 检测到中英混杂比例 > 20% → 切 **WhisperX**
- 需要精确做语音锚点对齐 → 用 **WhisperX**（词级时间戳）

---

### Stage 4: 关键帧抽取（**这里是第二道关卡，原方案被推翻**）

> 调研发现：**ffmpeg `select=gt(scene,X)` 对 PPT 讲座效果差**，必须换方案。

| 方案 | 原理 | 适合场景 | 劣势 |
|---|---|---|---|
| **主选**：**1 fps 采样 + pHash/CLIP 嵌入去重** | 每秒抽 1 帧，按图像哈希或 CLIP 特征余弦相似度去重（>0.95 视为同一张幻灯片） | **PPT 讲座最佳**，对动画/淡入淡出/摄像头叠加都鲁棒 | 需要写一点点代码，不是一行 ffmpeg |
| 备选 A：**PySceneDetect (`detect-content`)** | HSL 直方图差分，行业默认 | 通用 | 对淡入淡出弱 |
| 备选 B：**PySceneDetect → TransNetV2 兜底** | CNN 检测软切换，捞回 PySceneDetect 漏掉的 | 软切换多的视频 | 重 |
| 备选 C：**HHousen/lecture2notes 的 slide CNN 分类器** | 专门为讲座训练的"是否是 slide"分类器 | 板书 + 摄像头混合 | 老项目，pre-LLM |
| **避坑**：`ffmpeg select=gt(scene,X)` | ❌ | 不要用，对 PPT 类视频不可靠 |  |

**强制策略**：在抽帧后还要叠加**语音锚点**——转录里出现"看这张图/这段代码/如图所示/这里"时强制在该时间点抽一帧。这一招同类项目都没做，但对学习视频特别有效。

---

### Stage 5: 视觉理解（关键帧 → 文字）

| 方案 | 优势 | 劣势 |
|---|---|---|
| **主选**：**Claude Sonnet 4.6 vision** | 代码/公式/PPT 文字识别强 | 按帧调用，30~50 张/小时视频，¥1~2 |
| 备选：**GPT-4o vision** | 同级能力 | 同样按 token 收费 |
| 备选：**Qwen2-VL / InternVL 本地** | 免费、隐私 | 需要显存，效果略逊闭源模型 |
| 板书补充：**PaddleOCR** | 中文手写识别强 | 仅文字，不理解结构 |

**失败模式**：手写板书识别率显著低于印刷 PPT → 用 PaddleOCR 兜底。

**参考工作**：
- [HHousen/lecture2notes](https://github.com/HHousen/lecture2notes) — slide 提取流程可复用
- [microsoft/MM-Vid](https://multimodal-vid.github.io/) — GPT-4V 时间戳 + 帧描述 + 转录的提示模式直接可借鉴
- [byjlw/video-analyzer](https://github.com/byjlw/video-analyzer) — Whisper + 帧采样 + VLM 的通用 pipeline

---

### Stage 6: 长文本切分（chunking）

| 方案 | 同类项目用例 | 适合场景 |
|---|---|---|
| **主选**：**章节感知切分** + **map-reduce** | YouTube 章节 / B 站分 P / 静音 gap 检测出章节，每章独立总结后合并 | 我们的主路径 |
| 备选：**字符 map-reduce** (10k 字符并行) | martinopiaggi/summarize | 无章节信息时兜底 |
| 备选：**LangChain refine** | Mattral 项目 | 质量优先、不在乎慢 |
| **避坑**：**stuff（一次塞全部）** | ❌ for 20min+ | Claude 1M 上下文虽然能塞，但实测注意力稀释、漏点严重 |

---

### Stage 7: 总结生成与精修（**第三道关卡**）

> 同类项目全部止步于"单次生成"。我们的差异化在这里。

**三步策略**：

1. **Draft**（Sonnet 4.6）：每章独立生成初稿，强制带 `[时间戳]` 引用
2. **Critique**（Sonnet 4.6，换 prompt 扮演挑刺老师）：把转录 + 初稿一起喂回，输出问题清单
   - 漏掉的关键概念
   - 时间戳引用是否对应
   - 代码/公式是否完整
   - 章节衔接是否突兀
3. **Revise**（Opus 4.6）：根据 critique 重写

**质量闸门**：
- 覆盖率审查：转录里的术语/代码块在总结里是否都出现
- Whisper 低置信度句子在最终文档标灰
- 首次运行人工 review，把反馈沉淀为 few-shot 例子

---

## 2. 同类项目对比速查表

| 项目 | 下载 | 转录 | 切分 | 视觉 | 精修 | 备注 |
|---|---|---|---|---|---|---|
| BibiGPT-v1 | 平台 API | 依赖现有字幕，无 ASR | 单次 | ❌ | ❌ | v1 已基本归档 |
| AI-Video-Transcriber | yt-dlp | 字幕优先 + faster-whisper | 全文 | ❌ | ❌ | 无切分，长视频会爆 |
| liang121/video-summarizer | yt-dlp | faster-whisper + 静音切分并行 | 音频级切分 | ❌ | ❌ | 已是 Claude Code skill，思路最近 |
| 302ai | 闭源 | 闭源 | 闭源 | ❌ | ❌ | 仅 UI 参考价值 |
| martinopiaggi | yt-dlp + Cobalt | Groq Whisper / 本地 openai-whisper | **map-reduce 10k 字符 × 30 并行** | ❌ | ❌ | 长文本工程最完整 |
| Mattral | yt_dlp | openai-whisper base | LangChain stuff/map-reduce/refine 三种 | ❌ | ❌ | 教程级 demo |

**结论**：长文本切分抄 martinopiaggi，时间戳保留参考 liang121，视觉 + 精修我们自己加。

---

## 3. 推荐的最终选型（v2）

| 环节 | 主选 | 失败时切换 |
|---|---|---|
| 下载 | yt-dlp | bilix |
| 字幕 | yt-dlp `--write-auto-subs` + B 站 player API | — |
| **ASR** | **SenseVoice-Small** (FunASR) | 中英混杂多 → **WhisperX** |
| **关键帧** | **1 fps + pHash/CLIP 去重** + 语音锚点强制抽帧 | PySceneDetect → TransNetV2 |
| 视觉 | Claude Sonnet 4.6 vision | 手写板书 → PaddleOCR 兜底 |
| 切分 | 章节感知 + map-reduce | 字符 map-reduce |
| 总结 | Draft (Sonnet) → Critique → Revise (Opus) | — |
| 集成 | MCP Server | CLI |

---

## 4. 风险与缓解一览

| 风险 | 缓解 |
|---|---|
| Whisper 中文幻觉 | VAD + `condition_on_previous_text=False` + 幻觉黑名单 + 优先 SenseVoice/Paraformer |
| 关键帧抽不准 / 漏帧 | 1 fps + pHash 去重，叠加语音锚点强制抽帧 |
| 时间戳对不上关键帧 | 用 WhisperX 拿词级时间戳；或在 SenseVoice 输出后用 forced alignment 后处理 |
| 总结遗漏 | critique 阶段做覆盖率审查 |
| 总结幻觉 | 强制 [时间戳] 引用 |
| 长视频 token 爆 | 章节切分 + map-reduce |
| 手写板书识别差 | PaddleOCR 兜底 |
| B 站反爬 / cookie 失效 | 升级 yt-dlp + 用户传 cookie |

---

## 5. 验证策略（在 M1 阶段就做）

为了**尽早发现哪个环节会翻车**，M1 不要一次跑通整条流水线，而是**逐环节用一个真实视频做对照测试**：

1. 选 **2~3 个有代表性的 B 站视频**（一个纯讲解、一个 PPT 重、一个代码演示）
2. **ASR 对照**：同一视频分别跑 SenseVoice / Paraformer / WhisperX，人工抽查 5 段，记 CER
3. **关键帧对照**：同一视频分别跑 ffmpeg scene / PySceneDetect / 1fps+pHash，人工看哪个抽出来的帧最有信息量
4. **总结对照**：同一转录分别走"单次 stuff" vs "map-reduce" vs "map-reduce + critique"，人工评分
5. 把测试结果记到 `experiments/` 目录，每个环节的选型有依据

这一步做完，整条 pipeline 的不确定性就基本消掉了。

---

## 参考资料

- [Whisper-v3 幻觉测评 — Deepgram](https://deepgram.com/learn/whisper-v3-results)
- [Whisper hallucinations 分析 — Memo AI](https://memo.ac/blog/whisper-hallucinations)
- [FunASR (Paraformer)](https://github.com/modelscope/FunASR)
- [SenseVoice](https://github.com/FunAudioLLM/SenseVoice)
- [FireRedASR](https://github.com/FireRedTeam/FireRedASR)
- [WhisperX](https://github.com/m-bain/whisperX)
- [PySceneDetect](https://github.com/Breakthrough/PySceneDetect)
- [TransNetV2 论文](https://www.researchgate.net/publication/385306316)
- [HHousen/lecture2notes](https://github.com/HHousen/lecture2notes)
- [MM-Vid](https://multimodal-vid.github.io/)
- [byjlw/video-analyzer](https://github.com/byjlw/video-analyzer)
- [AKS - Adaptive Keyframe Sampling, CVPR 2025](https://github.com/ncTimTang/AKS)
- [liang121/video-summarizer](https://github.com/liang121/video-summarizer)
- [martinopiaggi/summarize](https://github.com/martinopiaggi/summarize)
