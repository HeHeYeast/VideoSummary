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

### Phase 5: 规划大纲

基于字幕 + 帧理解，决定章节结构：
- 按自然教学步骤切分
- 每节标题用动词短语
- **输出大纲给用户确认**（子 agent 执行时可跳过直接写）

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
