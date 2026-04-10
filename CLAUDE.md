# VideoSummary 项目指南

## 项目概述
B站视频 → 结构化 Markdown 教程。两层架构：
- **离线数据层**：`python -m agent.prepare` 跑下载/ASR/段落聚合/智能抽帧/帧分类/CLIP embedding
- **写作层**：Claude Code 直接读缓存文件 + 看帧图片（多模态），写教程

## 代码结构
```
agent/              — v2 agent 方案 (离线数据层)
  prepare.py        — 编排全部离线处理
  asr_v2.py         — 段落聚合 (segs → paragraphs)
  frames_v2.py      — 信息量打分抽帧 (替代 v1 的 1fps+pHash)
  pass1_classify.py — 帧分类 (code/slide/diagram/ui_demo/talking_head/transition)
  frame_store.py    — 结构化帧存储 + pass2 懒加载详情
  embed.py          — CLIP embedding + 语义搜帧
src/                — v1 pipeline (底层模块被 agent/ 复用)
config/             — 预算配置
output/             — 运行产出
```

## 环境变量（.env）
- `VE_KEY_CHEAP` — VectorEngine 便宜组 API key
- `VE_KEY_QUALITY` — VectorEngine 质量组 API key（可选）
- `VE_BASE_URL` — 中转站地址（默认 https://api.vectorengine.ai/v1）

---

## /summarize-video skill 工作流

当用户说 "总结这个视频"、"/summarize-video" 或给出 B 站 URL 时，**严格按以下步骤执行，不要跳过任何一步**。

### 步骤 0：数据准备（离线层）

运行离线数据准备命令（如果用户给了 URL 且数据未就绪）：

```bash
python -m agent.prepare "<url>" --skip-download --skip-clip
```

如果首次运行（无缓存），去掉 `--skip-download`。等命令完成后继续。

数据目录通常是 `output/BVxxx/`，包含：
- `meta.json` — 标题/UP主/时长/URL
- `segs.json` — 原始字幕 segments
- `paragraphs.json` — 段落聚合结果 (v2 新增)
- `frames/` — 关键帧 JPG
- `frame_store.json` — 结构化帧存储 (含分类/info_score/brief)
- `embeddings.npy` — CLIP embeddings (可选)

### 步骤 1：读取全局信息

依次 Read：
1. `meta.json` — 获取标题、时长、UP主
2. `paragraphs.json` — 通读完整段落化字幕（比 segs.json 更可读）
3. `frame_store.json` — 看帧列表（关注 type/info_score/brief 字段）

**不要跳过通读字幕**。必须在写任何内容之前理解整个视频的完整内容。

### 步骤 2：看关键帧图片（多模态）

根据 frame_store.json 中 type 为 `code`、`slide`、`diagram` 的帧：
- 直接 Read 帧图片文件（如 `output/BVxxx/frames/frame_000031.jpg`）
- **代码截图逐行抄录**：函数名、参数名、类型、默认值必须精确
- 不要依赖 brief 字段的 30 字描述，那只是索引，不是真相
- `talking_head` 和 `transition` 类型的帧可以跳过不看

### 步骤 3：规划大纲

基于字幕 + 帧，自行决定章节划分：
- 按视频的自然教学步骤切分，不是固定时长
- 每节标题用动词短语（"创建自定义节点"、"添加漂浮动画"）
- **输出大纲给用户确认，确认后再写正文**

### 步骤 4：逐节写作

每节遵循教程风格，每个关键步骤格式：

```markdown
[HH:MM:SS] **步骤标题**

具体操作说明（第二人称指令式）。

![](frames/frame_xxx.jpg)

*为什么这么做*：解释原因（如果视频里说了）

```代码块（从截图精确抄录）```
```

规则：
- **时间戳必须真实**：只用 segs.json / paragraphs.json 里实际存在的时间点
- **代码必须从截图抄**：不确定就回去 Read 帧图片，不要猜
- **图片紧跟操作步骤**：不要全部堆在末尾
- **没帧的步骤不要硬插图**
- **不注水**：视频讲了多少就写多少
- **不编造**：视频没说的不要加

### 步骤 5：完整代码合集

在文档末尾，把所有散落的代码片段合并成一个完整的可运行脚本。
如果视频产出了多个文件，分文件名列出。

### 步骤 6：输出

Write 最终 markdown 到 `output/BVxxx/summary.md`。

### 质量自检清单（写完后过一遍）

- [ ] 时间戳都来自字幕真实时间？
- [ ] 代码都从截图抄录（不是猜的）？
- [ ] 每张引用的图片都对应正确的操作步骤？
- [ ] 没有"综上所述"/"接下来我们将"等废话？
- [ ] 完整代码合集能直接跑？
