# VideoSummary 项目指南

## 项目概述
B站 / 抖音视频 → 结构化 Markdown 教程。全流程 **¥0 成本**（Claude Max 计划）。
Claude Code 是唯一决策者：抽帧策略、帧理解、章节结构、写作全部由你自己完成。

## 可用工具

3 个核心命令（本地执行，¥0）+ 2 个辅助命令：

```
python -m agent.tools download <url> --out <dir>          # B 站 / 抖音自动识别
python -m agent.tools transcribe <video_path> --out <dir> [--whisper small] [--force]
python -m agent.tools extract_frames <video_path> --out <dir> --fps N --start S --end E
python -m agent.tools aggregate <segs.json> --out <path> [--gap 1.5]
python -m agent.tools cleanup_frames <dir> --keep f1.jpg f2.jpg ...
```

**帧理解不需要 API** — 直接 `Read output/xxx/frames/xxx.jpg` 看图片。
你是多模态模型，能精确读取代码截图中的每一行。这比任何 OCR API 都准确。

## 决策支持工具（Phase 4，可选）

两条只读工具，给 Claude 写 `schedule.json` 时提供 ground truth — **工具不自动改 schedule**（K5「Claude is decider」原则）：

- `python -m agent.tools detect_scenes <video> --out output/<slug>/scenes.json` — PySceneDetect 输出场景切换时间线（默认依赖，~80MB）
- `python -m agent.tools detect_silence <video> --out output/<slug>/silence_map.json` — silero-vad 输出静音区间，>5s 标 `flagged_for_review:true`（opt-in 依赖）

`detect_silence` 需要 `pip install -r requirements-optional.txt`（拉 torch ~700MB）。不安装也能用 `extract_frames_batch`：FPS-04 退化为只检 baseline pass（schedule 必须包含一个覆盖全片的 `fps ≤ 0.1` 段，详见 Phase 4 CONTEXT D-08）。

## 抖音支持（首次设置）

抖音 URL 的下载链路和 B 站不同，需要一次性设置：

1. **克隆 Evil0ctal 的 crawler**（提供 a_bogus 签名算法）：
   ```bash
   git clone --depth 1 https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git vendor/douyin_api
   ```
2. **安装依赖**（requirements.txt 已包含所需项）：
   ```bash
   pip install -r requirements.txt
   ```
3. **导出抖音 cookies** 到项目根目录 `www.douyin.com_cookies.txt`：
   - 装 Chrome 插件 "Get cookies.txt LOCALLY"
   - 访问 https://www.douyin.com/ 后点插件 → Export → 另存为项目根的 `www.douyin.com_cookies.txt`
4. 之后 `python -m agent.tools download "https://v.douyin.com/xxx/" --out output/xxx` 会自动识别抖音路径

注意：抖音 cookies 每几天失效，失败时重新导出。yt-dlp 的 douyin extractor 长期 broken（不支持 a_bogus），所以必须走 vendor crawler。

## YouTube 支持（首次设置，可选）

> 首次设置 YouTube ingest 时按本节配置；不需要 YouTube 直接抓取的话，跳过本节，直接用本地 mp4 兜底（见末尾）。

YouTube ingest 在国内默认连不通（GFW + 2026 SABR + PO Token 三重阻断）。如果需要从 YouTube 直接 ingest，按以下步骤设置；否则用 LocalSource 兜底（自己下载到本地后跑 `python -m agent.tools ingest "D:\videos\local.mp4" --out output/xxx`）。

1. **配置 HTTPS_PROXY**（必须）：
   ```bash
   # PowerShell（当前 session）
   $env:HTTPS_PROXY = "http://127.0.0.1:7890"
   # 或永久（Windows）
   [Environment]::SetEnvironmentVariable("HTTPS_PROXY", "http://127.0.0.1:7890", "User")
   ```
   ingest 时会自动按 HTTPS_PROXY > HTTP_PROXY 优先级转发给 yt-dlp（empty string 不会传）。

2. **导出 YouTube cookies**（推荐）：
   - 装 Chrome 插件 "Get cookies.txt LOCALLY"
   - 访问 https://www.youtube.com/ 后点插件 → Export → 另存为 `youtube_cookies.txt`
   - 之后 yt-dlp 自动从浏览器/cookies 文件读取（具体路径优先级见 src/download.py）

3. **PO Token 支持**（YouTube 2026 SABR 之后部分视频强制要求；可选）：
   ```bash
   winget install DenoLand.Deno
   pip install yt-dlp-get-pot
   ```
   `Deno` 和 `yt-dlp-get-pot` 不进 `requirements.txt`，是 opt-in。装完之后 yt-dlp 会自动检测。

4. **验证**：
   ```bash
   python -m agent.tools ingest "https://www.youtube.com/watch?v=<id>" --out output/test_yt
   ```

注意：失败时 ingest 会按 5 类分类报错（`gfw_blocked` / `cookies_stale` / `po_token_required` / `yt_dlp_outdated` / `other`），照着中文 hint 修复对应环节即可。如果 5 类都搞不定，最稳的兜底是「自己用浏览器/IDM 下到本地，然后 `ingest <local-path>`」。

> **注意：** `agent/sources/__init__.py` 的 `SOURCES` 列表顺序是 most-specific-first：DouyinSource → YouTubeSource → BilibiliSource → LocalSource → GenericSource（LocalSource 在 03-03 加入）。**不要改动顺序** — 抖音 URL 必须先匹配 DouyinSource（走 vendor crawler），否则会路由到 yt-dlp 的 broken 抖音路径。

## Windows zh-CN 终端设置（推荐）

中文 Windows 默认 GBK 终端会在打印含 emoji / 非 ASCII 的视频标题时炸出
`UnicodeEncodeError`。代码已在 `agent/tools.py:59` 留了 `ensure_ascii=True`
兜底，老路径不设置也能跑；但**推荐**把终端 + 解释器 都切成 UTF-8，让本仓库
所有路径行为一致：

1. **每个 terminal session 跑一次**（zh-CN cmd / PowerShell）：
   ```bash
   chcp 65001
   ```

2. **一次性设置 `PYTHONUTF8=1` 环境变量**（Windows 10+ 生效）：
   - PowerShell 永久：`[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "User")`
   - 或在「系统属性 → 环境变量」面板加 `PYTHONUTF8=1`
   - 设好后重启 terminal 验证：`python -c "import sys; print(sys.flags.utf8_mode)"` 应输出 `1`

设了之后 `print(meta)`、文件 I/O、子进程 stderr 全程 UTF-8；老的 `ensure_ascii`
兜底保留不动，没设 codepage 的环境也能正常工作。

> **历史背景：** 项目里所有 `read_text` / `write_text` 都已显式 `encoding="utf-8"`
> （Phase 1 PRE-04 审计通过），这一节是给「希望子进程 stderr 也直接读到中文」
> 的开发者准备的、可选的一致化设置。

## 环境变量（.env）
- `VE_KEY_CHEAP` — VectorEngine API key（仅后备 classify/ocr 命令需要，正常流程不用）
- `DOUYIN_COOKIES_FILE` — 抖音 cookies 文件路径（默认 `www.douyin.com_cookies.txt`）

---

## 视频类型变奏

> 这一节是 `/summarize-video` 8 阶段主干的**变奏带（adaptive layer）**，不是替代品。Phase 1 / 3 / 7 / 8 不分叉；只有 Phase 2 末尾要选 mode、Phase 4-6 写作时按 mode 微调形态。**核心原则：内容自适应，形式不变。**

### 模式分类（Phase 2 末尾步骤）

读完 `paragraphs.json` 之后，你必须在 `output/<slug>/plan.md` 顶端写出 4 行模式判断 + primary + optional secondary 结论。**4 个 mode 标签 byte-equal**（不允许改名、不允许省略下划线、不允许新增）：

- `replicate-guide` — 复刻指南（17 archived 主流；UP 全程 hands-on 教你"跟我做出来"）
- `concept-explanation` — 原理讲解（"为什么是这样" / 反直觉答案 / 核心问题 → 最小例证）
- `extension-applications` — 延展应用（同一工具 / 同一概念在 3-5 个场景里横向罗列 + 边界对比）
- `interview-distillation` — 访谈萃取（播客 / 嘉宾对话 / speaker turns + 关键引文 + 时间戳导航）

判断格式（写在 plan.md 正文里，front-matter 之外）：

```
replicate-guide:        70%  — UP 全程在 IDE 里 hands-on coding
concept-explanation:    20%  — 开头 30s 讲了"ECS 是什么"
extension-applications: 5%   — 没有跨工具对比
interview-distillation: 5%   — 单人，无嘉宾

primary: replicate-guide
secondary: concept-explanation
```

**Fallback 规则**（**必须** 默认走，避免分类瘫痪）：4 模式百分比无明显主导（最高 < 50%）或无法分清 → primary 写 `replicate-guide`。理由：与 17 archived 风格一致，user 已熟悉，是"最低惊讶"安全选择。

**Mode 切换允许在写作中途**：写到 Phase 6 一半发现 mode 误判 → 编辑 `plan.md` 把 mode 字段改掉，并加一行 `mode_switched_at: HH:MM:SS reason: <为什么改>`，重写已写部分。这是 P1.5 "wrong depth wastes tokens" 的兜底。**不**走 user-pause-confirm 流程（K2：Claude is decider）。

### plan.md 必写（Phase 2 末尾产物）

`output/<slug>/plan.md` = **顶部 5 字段 YAML front-matter + free-form Markdown 正文**。Phase 2 末尾必写。

```yaml
---
mode: replicate-guide                    # 4 模式之一，byte-equal
secondary_mode: concept-explanation      # 4 模式之一 或 null
classification_evidence: |               # 多行字符串，4 模式各自占比的依据
  70% 代码演示，30% 概念引入 ("ECS 是什么")，UP 全程 hands-on coding
fps_strategy_summary: 代码段 fps 0.4 / UI 段 fps 0.2 / 闲聊跳过   # 自由字符串
estimated_sections: 6                    # 整数，预估章节数（含引言/收尾）
---

# Phase 2 判断笔记

（free-form Markdown 正文：可以写"这条视频值得抽哪些段、哪些段可以跳、为什么选这个 mode、有没有什么坑要小心"——不强 schema，写错也不让工具崩。）
```

**特殊规则**：
- **Mandatory in Phase 2**：写完 Phase 2 必须 `output/<slug>/plan.md` 存在
- **Missing 不强 fail**（K3 backward-compat）：17 archived 没有 plan.md，老 re-run 路径打 `WARNING: plan.md missing — pre-Phase-5 archive，跳过 mode-aware 写作` 但**不 fatal**
- **Free-form, no schema enforcement**：5 字段写错（拼错 mode 名 / estimated_sections 写成字符串）→ 工具不强校验；下游写作时你自己 sanity-check
- **`<plan.md>.params.json` sidecar**：Phase 2 RES-01 模式自动生成，仅记录 `{"created_at": ..., "mode": ..., "secondary_mode": ...}`。cache 层级不参与 regen 判断（plan 是 Claude 写的，无参数 hash 概念）

### depth_plan.md 可选（仅 token-expensive 视频）

`output/<slug>/depth_plan.md` 是**独立可选文件**，触发条件：

1. **视频时长 > 30 min**，或
2. **estimated_sections > 50**，或
3. user 手动 `touch output/<slug>/.need_depth_plan` 强制启用（无需 user-pause-confirm，Claude is decider）

depth_plan.md 内容是**章节级 token 预算 + 重点段落标记**，目的是写正文之前先确认"哪些段值得花 token，哪些段一笔带过"。Schema 同 plan.md（free-form Markdown + 顶部 YAML），不强校验。

**判断标准**（Claude 自判）：你在 Phase 2 通读 paragraphs.json 后觉得"这条视频写满会爆 context"或"重点 / 闲聊比例严重失衡需要预算"——写一份 depth_plan.md。否则跳过。

### 格式锁定（无论哪个 mode，4 项不变量）

**这是 format-spec lock。不论 primary 是哪个 mode，summary.md 必须满足以下 4 项；违反一项就是质量退化（P1.2 退化路径）：**

1. **时间戳格式**：`[HH:MM:SS]`，必须 8 字符（`[01:23:45]` ✓ / `[1:23]` ✗ / `[83:45]` ✗ / `12:34` ✗）
2. **代码 fence 必带显式语言**：```` ```gdscript ```` / ```` ```python ```` / ```` ```bash ```` / ```` ```json ```` / ```` ```yaml ````。**不能裸 fence**（```` ``` ```` 后接代码）。即便是 shell 输出也写 ```` ```text ```` 或 ```` ```console ````
3. **图片嵌入**：`![](frames/seg_xxxx_xxxxxx.jpg)` 相对路径。**不能** absolute 路径（`![](D:/.../frames/...)` ✗）；**不能** 空 alt 含截图（OK 但放在 frames/ 目录下，非占位 placeholder）
4. **第二人称指令式**："你 + 动词"（"你打开 settings.json" ✓ / "我们打开 settings.json" ✗ / "settings.json 被打开" ✗）

锁死语：**内容自适应；形式不变。** 这 4 项是 17 archived 已建立的"读起来是 videoSummary 出品"的视觉指纹。

### 4 模式 skeleton（exemplar prior）

> 此处为 placeholder。具体 8 份 skeleton（4 模式 × 2 份）由 plan 05-01 task 2 嵌入。

---

## /summarize-video 完整工作流

当用户说"总结这个视频"或给出 B 站 URL 时，**严格按以下步骤执行**。

### Phase 1: 获取原始数据

**1.1** 如果 `output/BVxxx/` 不存在，下载视频：
```bash
python -m agent.tools download "<url>" --out output/BVxxx
```

**1.2** ASR 转录（本地 faster-whisper，¥0）：
```bash
python -m agent.tools transcribe output/BVxxx/video.mp4 --out output/BVxxx
```

**1.3** 段落聚合：
```bash
python -m agent.tools aggregate output/BVxxx/segs.json --out output/BVxxx/paragraphs.json
```

如果 segs.json / paragraphs.json 已存在，跳过对应步骤。

### Phase 2: 理解内容

**2.1** Read `meta.json` — 标题、时长、UP主

**2.2** Read `paragraphs.json`（或 `segs.json`）— **完整通读字幕**。不要跳过。

**2.3** 基于字幕判断：
- 视频类型（编程教程 / PPT 讲座 / 操作演示）
- 哪些时间段信息密集、哪些可以跳过
- 决定分段抽帧策略（下一步用）

**2.4** 输出模式判断 + 写 plan.md（详见 § 视频类型变奏 → 模式分类）。从 4 模式（`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`）选 primary + optional secondary，落到 `output/<slug>/plan.md` 顶部 5 字段 YAML front-matter；模糊 fallback 到 `replicate-guide`；写到一半误判可以改 mode 字段 + `mode_switched_at` 标记。

### Phase 3: 智能抽帧（你决定参数）

**根据 Phase 2 的判断分段抽帧**。关键原则：
- **代码演示段**：fps 0.3-0.5（每 2-3 秒一帧，捕捉代码变化）
- **UI 操作段**：fps 0.2-0.3
- **纯讲解/闲聊**：fps 0.1 或直接跳过
- **片头片尾**：跳过

示例（你根据实际内容调整）：
```bash
python -m agent.tools extract_frames video.mp4 --out output/BVxxx/frames --fps 0.2 --start 0 --end 30
python -m agent.tools extract_frames video.mp4 --out output/BVxxx/frames --fps 0.3 --start 30 --end 300
```

**控制总帧数**：一条 10 分钟视频通常 30-50 帧就够。不需要太多，你后面会直接看图挑选。

### Phase 4: 看帧（多模态，核心步骤）

**直接 Read 帧图片**。这是你最大的优势 — 不需要 OCR 中间层。

```
Read output/BVxxx/frames/seg_0030_000015.jpg
```

重点看：
- **代码截图**：逐行精确抄录。函数名、参数、类型、默认值一个都不能错
- **UI 界面**：哪个面板、做了什么操作、属性值是什么
- **PPT/幻灯片**：标题、列表项、公式

**选择性看**：不需要看所有帧。先看每个时间段的第一帧和最后一帧判断内容变化，再针对性看中间帧。

**补充抽帧**：如果发现某个关键操作没有截图，可以对那个时间点重新抽帧（更高 fps 或更精确的 start/end）。

> **mode 提示**：`interview-distillation` 时帧用量极少（每章节 1-2 帧，详见 § 视频类型变奏）；`extension-applications` 中 UI demo 子规则有 4 项（pixel-text 不确定性 / tooltip 遮挡 / 光标不可见 / 4K --width override），由后续 plan 03 落地（详见 § 视频类型变奏 → skeleton 内的 mode-specific 章节）。其余 mode 按本 phase 主流程。

### Phase 5: 规划大纲

基于字幕 + 帧理解，决定章节结构：
- 按自然教学步骤切分
- 每节标题用动词短语
- **输出大纲给用户确认**（子 agent 执行时可跳过直接写）

> **mode 提示**：`concept-explanation` 大纲走"核心问题 → 反直觉答案 → 最小例证 → 应用边界"流；`interview-distillation` 走 chapters.json + speaker turns（plan 03 引入 chapters.json schema）；`extension-applications` 大纲是横向罗列（场景 1 / 场景 2 / 场景 3 + 边界对比）。其余 mode 按本 phase 主流程。

### Phase 6: 逐节写作

教程风格，每个步骤格式：

```markdown
[HH:MM:SS] **步骤标题**

操作说明（第二人称指令式）。

![](frames/seg_xxxx_xxxxxx.jpg)

*为什么这么做*：原因

​```gdscript
// 从截图精确抄录
​```
```

> **mode 提示**：`replicate-guide` 是默认风格（17 archived 主流，本 phase 上方 markdown 模板就是它）。`concept-explanation` 不放完整代码块，只放概念图和最小例证；`extension-applications` 按场景横向罗列；`interview-distillation` 用 blockquote 替代图片（`> [HH:MM:SS] 嘉宾名："核心引文"`）。具体形态见 § 视频类型变奏 → 4 模式 skeleton。

### Phase 7: 完整代码 + 输出

- 文档末尾合并完整代码（分文件列出）
- Write 到 `output/BVxxx/summary.md`

### Phase 8: 收尾

- 质量自检（时间戳真实？代码从截图抄？图片对应步骤？无废话？）
- 可选：`python -m agent.tools cleanup_frames <dir> --keep <用到的帧>` 清理未引用的帧

---

## 质量红线

- **时间戳只用字幕里真实存在的**
- **代码从帧截图精确抄录** — 不确定就 Read 图片再看
- **图片紧跟操作步骤** — 没帧不硬插
- **不注水不编造**
- **完整代码可运行**
