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

## Pyannote diarization 设置（首次设置，可选）

> 仅播客 / 访谈类视频需要；不打算处理这类视频可跳过。**Phase 5 spike 默认走 degrade 路径**（CLAUDE.md `## 视频类型变奏 → Podcast / interview 模式骨架` 让 Claude 从内容线索推断说话人）。本节是给愿意装 GPU + HF token 的进阶用户用的。

1. **安装 opt-in 依赖**（拉 ~700MB torch + pyannote 权重）：
   ```bash
   pip install -r requirements-optional.txt   # 包含 pyannote.audio + torch + silero-vad
   ```

2. **申请 HF token + 接受 community-1 协议**：
   - 注册 https://huggingface.co/
   - 接受 community-1 model 协议：https://huggingface.co/pyannote/speaker-diarization-community-1
   - 在 https://huggingface.co/settings/tokens 创建 read-only token
   - 写入项目根 `.env`：`HF_TOKEN=hf_xxxxxx`（**不要 commit `.env`**；`.gitignore` 已覆盖）

3. **CPU vs GPU**：
   - Windows 11 + CPU + 60min+ 音频预计 wall time 3-5h（参考 SPIKE.md 实测比例）
   - `diarize` CLI 启动会探测 ffprobe duration；> 60min AND 无 CUDA 时打 WARNING 提示，**默认 N 拒绝执行**——你必须显式输 `y` 才继续
   - 推荐：等 GPU 机器再跑 / 切片处理 / 直接用 `## 视频类型变奏 → Podcast / interview 模式骨架` 的内容线索推断兜底

4. **跑 diarization**：
   ```bash
   python -m agent.tools diarize output/<slug>/audio.wav --out output/<slug>/diarization.json
   ```
   产出 schema：`{"version": 1, "turns": [{"start": 0.0, "end": 12.5, "speaker_id": "SPEAKER_00"}, ...]}`。`speaker_id` 是 pyannote 抽象 ID（`SPEAKER_00` / `SPEAKER_01`），**不是**真实姓名（真实姓名解析留作 v2）。

5. **跑批自动化场景**（如 CI / cron）：加 `--allow-long` 跳过 60min+ CPU 提示门：
   ```bash
   python -m agent.tools diarize <audio.wav> --out <d.json> --allow-long
   ```
   仅在 GPU 机器或愿意接受 5h+ wall time 的批跑场景使用。

> **WARNING 字面**（D-16 锁定）：
>
> ```
> WARNING: 60min+ 音频在 CPU 上 pyannote 预计 3-5× wall time（约 3-5h）。建议 (1) 切片处理 (2) 跳过 diarization 让 Claude 从内容推断 (3) 等待 GPU 机器再跑。继续？(y/N)
> ```

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

## 多终端并行 (Phase 6)

> 这一节描述「两个 Claude Code 终端同时跑不同视频」的安全契约。**单终端流程不受影响**——锁是无声的，acquired+released 不留痕迹。

### 锁住了什么

1. **vendor `config.yaml` 写入** — `vendor/douyin_api/crawlers/douyin/web/config.yaml` 被 download_douyin 在每次抖音下载时 read-modify-write，两个终端同时跑会把同一个文件写花。Phase 6 加了 `vendor/douyin_api/crawlers/douyin/web/.config.yaml.lock` sibling 锁文件，第二个 invocation 要么排队，要么 fail-fast。

2. **per-slug `output/<slug>/.resume.lock`** — 同一个 slug 上同时跑 `transcribe` / `aggregate` / `extract_frames_batch`（任意两个，或同一个跑两次）会撕裂 `segs.json` / `paragraphs.json` / `state.jsonl`。锁住的是「同一 slug 的写操作」。第二个 invocation 立即 fail with: `LockContended: FileLock: output/<slug>/.resume.lock held by PID <N> since <ISO-timestamp>`。

3. **没锁的命令**（故意的）：
   - `extract_frames`（FPS-07 单段补抽）— 你想边跑 batch 边手动补抽某一段是合法用法
   - `download` / `ingest`（除了上面的 vendor config 那一段已经锁住）— 自身是幂等的，meta.json 用 atomic write
   - `detect_scenes` / `detect_silence` / `doctor` — 决策支持/只读工具
   - `diarize` — opt-in，长任务 user 自己负责不重复触发
   - `queue` 子命令（Phase 7 加入新锁域 `~/.videoSummary/.queue.lock`，详见下方 `## v1.1 opt-in marker + 4 K5 emitters (Phase 07)` 段的 "Multi-terminal lock 域扩展" 小节）

### per-slug isolation vs 跨 slug 并发

下表说明 per-slug isolation 的具体边界——同 slug 强制串行（锁拒绝第二个 invocation），跨 slug 由 user 自己评估 OOM 风险。

| 场景 | 安全？ | 备注 |
|---|---|---|
| 同 slug 同 stage 两次（e.g. transcribe BVxxx 两次） | 否 第二个 fail-fast | 这就是 lock 的目的 |
| 同 slug 不同 stage（e.g. transcribe BVxxx + aggregate BVxxx）| 否 第二个 fail-fast | 锁是 stage-agnostic，整个 slug 只允许一个长任务 |
| 不同 slug 同 stage（e.g. transcribe BVxxx + transcribe BVyyy）| user's risk | 锁不冲突，但 faster-whisper 是 CPU-bound + 显存敏感（小模型 ~1.5G、medium ~3G、large ~6G），两个并发可能 OOM |
| 不同 slug 不同 stage（e.g. transcribe BVxxx + extract_frames BVyyy）| 安全 | 完全独立 |
| download 抖音两个不同 URL 同时 | 安全 | vendor config.yaml 由 lock 串行化，每个 invocation 拿到自己的 cookie 配置 |

### 实操规则（faster-whisper CPU-bound）

- **CPU 推理（无 CUDA）**：建议同时跑的 transcribe 数量 ≤ `nproc - 1`（留一个核给 OS / 你的浏览器）。Windows 里看任务管理器 → 性能 → 逻辑处理器数。
- **GPU 推理（有 CUDA）**：单卡通常只够 1 个 medium / large。多卡可以并发，但 ProcessPoolExecutor 之类自己管。Phase 6 不提供调度器（PROJECT.md OOS row 4：personal tool）。
- **真撞上锁了怎么办**：
  - 等：另一个终端跑完了再来
  - kill：`Ctrl+C` 不会留下永久锁——`agent/_lock.py` 的 stale-PID detection 会让下一次 invocation 自动接管（PID 死了就接走 `.resume.lock`）
  - 永不要：`rm output/<slug>/.resume.lock`——非紧急情况下手动删锁文件没意义；要么等，要么让 stale-PID 接管

### Cookies 缓存（PARA-05）

- 抖音 cookies 在每个 Python 进程内只读一次（module-level `_COOKIES_CACHE`）。两个终端 = 两个进程 = 各自缓存，没有交叉污染。
- 重新导出 cookies 后想立刻生效：`python -m agent.tools download <url> --out <dir> --reload-cookies`。

### 日志格式（PARA-04）

- `transcribe` / `aggregate` / `extract_frames_batch` / `extract_frames` / `diarize` / `cleanup_frames` / `detect_scenes` / `detect_silence` 的状态行带 `[<slug>] <cmd>: ` 前缀。
- 两个终端 `tail -f` 合并输出时，`grep '\[BVxxx\]'` 就能筛出来。
- `download` / `ingest` 的 JSON 输出 + `doctor` 的 ASCII 表 + `list_frames` 故意不加前缀（结构化输出 / 单页报告 / 单纯列表，加前缀反而难读）。

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

### 格式锁定（无论哪个 mode，4+1 项不变量）

**这是 format-spec lock。不论 primary 是哪个 mode，summary.md 必须满足以下 4 项；违反一项就是质量退化（P1.2 退化路径）。第 5 项是 v1.1 opt-in 增强（仅 marker 启用 `inline_trace_tokens` 的 slug 必须满足）：**

1. **时间戳格式**：`[HH:MM:SS]`，必须 8 字符（`[01:23:45]` ✓ / `[1:23]` ✗ / `[83:45]` ✗ / `12:34` ✗）
2. **代码 fence 必带显式语言**：```` ```gdscript ```` / ```` ```python ```` / ```` ```bash ```` / ```` ```json ```` / ```` ```yaml ````。**不能裸 fence**（```` ``` ```` 后接代码）。即便是 shell 输出也写 ```` ```text ```` 或 ```` ```console ````
3. **图片嵌入**：`![](frames/seg_xxxx_xxxxxx.jpg)` 相对路径。**不能** absolute 路径（`![](D:/.../frames/...)` ✗）；**不能** 空 alt 含截图（OK 但放在 frames/ 目录下，非占位 placeholder）
4. **第二人称指令式**："你 + 动词"（"你打开 settings.json" ✓ / "我们打开 settings.json" ✗ / "settings.json 被打开" ✗）
5. **行内溯源 token (v1.1 opt-in，仅 `is_v11_enabled(slug, "inline_trace_tokens")` 时强制)**：每个 claim / 参数 / 截图引用句末加 `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` 或 `[para_NNNN @ HH:MM:SS]` token。**FORBIDDEN** 在 TL;DR / glossary inline 注解 / "你需要知道什么" prelude / 章节小结 transitions 中放 token。**REQUIRED** 在具体 claim / 参数 / 代码 / UI 引用句。**OPTIONAL** 在 narrative 连接句。密度目标 avg ≤ 1 citation per 3 sentences。完整规则见 § v1.1 自适应教学文档增强 (Phase 08) → CORR-02。

> **机械校验**：以上 4+1 项不变量由 `python -m agent.tools summary_lint <slug>/summary.md` 静态检查（CORR-03a，Phase 09 Plan 09-01）；Phase 7.5 verifier subagent（CORR-03b，Phase 09 Plan 09-02）读 `summary_lint.json` 后再做语义层校对（mode 规则一致性 / 引用 timestamp 真实性 / glossary term 漂移）。详见 § v1.1 校对自动化 (Phase 09)。

锁死语：**内容自适应；形式不变。** 前 4 项是 17 archived 已建立的"读起来是 videoSummary 出品"的视觉指纹。第 5 项是 v1.1 marker-gated 增强 — v1.0 archives 不强制（D-29 byte-equal preserved）。

### 4 模式 skeleton（exemplar prior）

> **使用方式**：你在 Phase 2 决定 mode 之后，写作时**参照对应 mode 的 2 份 skeleton 做章节切分 + 段落形态**。**不**复制粘贴。exemplar 是 prior（先验形态），不是模板（template）。每份 skeleton 都从已归档 corpus reshape，保留 4 项 format-spec 不变量。
>
> **每模式 2 份的设计原因**：单份 skeleton 容易让 Claude 锚定为"唯一正解"；2 份不同节奏（短 vs 长 / 步骤型 vs 概念型 / 单一线索 vs 多线索）能撑出真实变奏空间，避免 P1.3 "every video looks the same" 退化。

#### Mode: replicate-guide（复刻指南，17 archived 主流）

##### Skeleton 1：短小步骤型（节奏快、每节 1 操作 + 1 截图 + 1 行 why）

<!-- 来源: output/BV132wizyEEB/summary.md (reshape, 1:14 视频；典型"跟我做出来"节奏) -->

```markdown
# 1 分钟搞定全套像素风游戏美术：AI 绘画 + 自动抠图全流程

> UP主：今天又被Godot打了 | 时长：1:14 | [B站链接](https://www.bilibili.com/video/BV132wizyEEB)

---

## 一、用 Gemini 生成像素风场景地图

[00:00:06] **打开 Gemini，用提示词生成初始场景**

提示词的关键是先给 AI 设定角色，再描述要生成的地图类型。你直接复制下面这段：

> 你是一名资深的像素场景画师，你将根据描述的场景生成一个 topdown 类型的俯视视角的全景像素风场景，不会出现人物。帮我生成一个冒险家协会的内景

![](frames/seg_0005_000002.jpg)

*要点*：明确指定"像素场景画师"角色 + "topdown 俯视视角" + "全景像素风" + "不会出现人物" 4 个约束条件，缺一个出来的画面都会跑偏。

---

## 二、迭代修改场景细节

[00:00:19] **告诉 AI 具体修改需求，并禁止其他改变**

直接用自然语言描述要修改的内容。**关键技巧**：明确说"其余地方禁止改变"，防止 AI 在修改一处时把其他地方也改了。

第一轮修改提示词：

> 把左下角的门去掉，然后右上角的楼梯去掉，其余地方禁止改变

![](frames/seg_0015_000003.jpg)

*为什么这么做*：Gemini 在 image-edit 模式下默认会把整图重 generate；加"禁止改变"是把它锁定到 inpaint 行为。

---

## 三、提取场景中的物品素材

[00:00:33] **用提示词让 AI 将物品单独提取出来**

提示词：

> 请将场景中的物件单独提取（地板之上的家具），并有序排列，物件与物件之间保持一定距离，避免后期提取的时候混淆。物件的大小与原场景一致。并且用一个纯色的区别于物件颜色背景色填充。

![](frames/seg_0031_000002.jpg)

*关键*：要求 AI 使用**与物品不同颜色的纯色背景**，这样后期可以通过底色轻松抠图。

---

## 四、成果展示

[00:01:02] **将素材导入 Godot 引擎**

最终效果：所有 AI 生成的像素风素材直接导入 Godot 游戏引擎中使用。

![](frames/seg_0052_000004.jpg)
```

##### Skeleton 2：长流程多步骤型（节奏稳、章节带"为什么这么做"小段 + 完整代码尾节）

<!-- 来源: output/douyin_trae_ai/summary.md (reshape, 4:12 视频；TRAE SOLO 配置 → 命令创建 → 实操) -->

```markdown
# 搭建全网千万收藏的 AI 第二大脑：TRAE SOLO 实战教程

> 来源：抖音 @数字游牧人 Samuel · 时长 4:12 · [原视频](https://v.douyin.com/D4_5dfVmsIo/)
>
> 关键词：TRAE SOLO、Compound Engineering、MTC 模式、个人知识库

## 这篇教程讲什么

跟着 UP 主一步步在 TRAE SOLO 桌面端搭出一套「摄取 → 消化 → 输出」的 AI 第二大脑。学完你会得到 3 条可复用的自定义命令 + 装好的 4 个 skill。

---

## 一、先理解核心理念：Compound Engineering

[00:00:05] **什么是 Compound Engineering**

![](frames/seg_0000_000001.jpg)

四步循环：**Plan → Work → Review → Compound**。**关键一步**是 Compound——把这次经验写回系统，让下次更容易。

| 步骤 | 你做什么 |
| --- | --- |
| Plan | 先规划、拆解任务 |
| Work | 让 AI 完成执行 |
| Review | 人或 AI 把关质量 |
| Compound | 把判断写回系统 |

*为什么这么做*：复利不发生在模型里，复利发生在你有没有把判断留下来。

---

## 二、进入 TRAE SOLO 桌面端：打开命令面板

[00:01:28] **步骤 1：选本地文件夹作为 AI workspace**

![](frames/seg_0000_000008.jpg)

切换到 **MTC 模式**，新建项目（命名 `LLM Wiki`），**指定一个本地文件夹作为 AI workspace**——后面所有 `raw/`、`wiki/`、`outputs/` 都会写在这里。

[00:01:38] **步骤 2：进入设置 → 命令面板**

![](frames/seg_0088_000001.jpg)

点击左下角头像 → 设置 → 左侧菜单的 **命令** 项。初次进来右边是空的，要在这里创建三条命令：**摄取**、**消化**、**输出**。

*为什么用命令而不是每次手输 prompt*：命令可以保存指令、描述、技能绑定，下次在对话框里打 `/` 就能调出来。

---

## 三、创建三条自定义命令

[00:01:43] **步骤 3：编辑「输出-知识卡片」命令**

![](frames/seg_0088_000003.jpg)

重点字段：

- **命令名称**：`输出-知识卡片`
- **描述**：`用于基于 /wiki 中已沉淀的知识生成一张知识卡片。`
- **说明**（核心 prompt）：

```text
你负责围绕具体任务调用知识库内容进行输出，请先读取 /wiki 下相关条目，
再生成一张知识卡片。输出必须明确依赖了哪些知识条目；如果知识不足，
要指出缺口和补充内容，而不是硬编造。
```

*整段 prompt 的结构*：① 任务是什么 ② 读哪个目录 ③ 输出写到哪 ④ 不足要补缺口不准硬编造 ⑤ 跑完回写新笔记。

---

## 四、完整代码 / 配置（按文件列出）

### `commands/输出-知识卡片.md`

```text
你负责围绕具体任务调用知识库内容进行输出，请先读取 /wiki 下相关条目，再生成一张知识卡片...
```

### `commands/摄取.md`

```text
读入外部 URL/文件，抓取内容，按来源归档到 /raw 下，并把元数据写成 front-matter...
```
```

#### Mode: concept-explanation（原理讲解）

##### Skeleton 1：核心问题 → 反直觉答案 → 最小例证 → 应用边界

<!-- 来源: output/douyin_ai_kb/summary.md (reshape, 2:02 视频；Karpathy LLM Wiki 范式) -->

```markdown
# 复刻 Karpathy 的个人知识库管理范式：LLM Wiki

> 来源：抖音 @Bryan · 时长 2:02
>
> 一句话：把碎片知识**编译**成生产力系统，而不是囤在收藏夹里发霉。

---

## 核心问题：你的收藏夹为什么没救

[00:00:00] **现象：读过 1005 篇，转化率 0.1%**

![](frames/seg_0000_000001.jpg)

你的收藏夹里躺着无数深度好文，但真正遇到复杂 bug 或架构决策时，大脑里只能搜到一堆碎片。这不是因为你读得少，而是因为**碎片化阅读只带来"学到了"的虚假快感**。

> *核心问题*：没有体系，就没有生产力。

---

## 反直觉答案：编译，而非存储

[00:00:38] **一条公式看懂这套方法**

![](frames/seg_0000_000005.jpg)

传统知识管理是"**存储**"——PDF 混乱堆、链接收藏夹、笔记碎片全部堆在 L1 Raw 层，然后就没有然后了。

Karpathy 的范式是"**编译**"——让 LLM 把 L1 Raw 重新编写成 L2 Wiki 层的系统化文档，背后的公式：

```text
Knowledge = Σ(Fragments) × Compiler
```

*为什么这是反直觉*：单纯累加碎片（Σ Fragments）不会自动产生知识，必须乘上一个 Compiler（你 + LLM 组成的编译器），才能把它们织入**已有的逻辑网络**。

---

## 最小例证：三文件夹

[00:01:05] **物理隔离：建立 `~/llm-wiki` 三文件夹**

![](frames/seg_0000_000008.jpg)

```text
~/llm-wiki/
├── raw/     # 1. 高信号原始稿
├── wiki/    # 2. 系统化知识（双链）
└── lab/     # 3. 物理直觉复现
```

*为什么这么分*：`/raw` 把"收藏"门槛拉高，本身就是第一道过滤器；`/wiki` 是编译产物层；`/lab` 是动手区——把理论跑一遍手感才真正沉淀下来。

---

## 应用边界：什么时候这套方法不灵

- **企业级知识库**：体量大 + 多人维护 → RAG 仍是主力
- **给 AI 看的复杂场景**：AI 需要 git 快照式版本 wiki，不是单视图
- **临界复杂点**：到一定规模 agent 自己也维护不动了

*核心**判断**：个人和中等规模它打爆 RAG；超出这个范围请回 RAG。
```

##### Skeleton 2：从一份代码教程切片出"如果只讲原理会怎么写"

<!-- 来源: output/douyin_claude_code_hooks/summary.md 的概念部分 (reshape，剥离实操只留原理) -->

```markdown
# Claude Code Hooks 原理：为什么事件驱动比手动触发好得多

> 来源：抖音 @大东软件 (原视频是教程，本 skeleton 把它的"原理段"切片重写)

---

## 核心问题：写完代码忘记 lint，提交前没做安全扫描，怎么办？

[00:00:00] **手动触发的根本问题**

![](frames/seg_0000_000001.jpg)

很多开发流程里的麻烦事——lint、格式化、安全扫描、提交前检查——并不是忘了做，而是**每次都要手动记得**。靠自觉就一定会漏。

> *核心问题*：人脑不该承担"记得每次执行重复任务"的负担。

---

## 反直觉答案：把流程挂在事件上，而不是挂在意志上

[00:00:10] **事件驱动 vs 意志驱动**

![](frames/seg_0000_000002.jpg)

| 模型 | 触发方式 | 出错率 |
|---|---|---|
| 意志驱动 | "我记得 commit 前跑一下 scan" | 高（人会忘） |
| 事件驱动 | "Claude 每次写完文件 → 自动 scan" | 0（系统不忘） |

*为什么是反直觉的*：直觉上你会想"我得养成 commit 前 scan 的习惯"。但好流程不是练习记忆，而是**把记忆外包给系统**。

---

## 最小例证：4 类 hook × 4 类事件 = 16 种组合，最常用的就 1 种

[00:00:50] **PostToolUse + Write|Edit matcher**

![](frames/seg_0000_000008.jpg)

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{"type": "command", "command": "./scan-secrets.sh"}]
    }]
  }
}
```

*这就是"事件驱动"的最小落地形态*：3 行 JSON，0 行业务代码，永久生效。

---

## 应用边界：什么场景**不该**用 hook

- **一次性脚本**：写一个 hook 比手动跑一次还慢
- **需要语义理解的任务**：用 Prompt 类 hook 不用 Command 类
- **跨系统联动**：用 HTTP hook 调外部 webhook 而不是 Command

*核心判断*：hook 是给"重复 + 必做"的事用的，给"偶尔 + 可选"的事用 hook 是过度工程。
```

#### Mode: extension-applications（延展应用）

##### Skeleton 1：4 类工具横向罗列 + 各自适用边界 + 总评

<!-- 来源: output/douyin_claude_code_hooks/summary.md (reshape, 1:08 视频；4 hook 类型 × 4 触发事件横向对比) -->

```markdown
# Claude Code 系列教程第 6 期：Hooks 事件驱动自动化

> 来源：抖音 @大东软件 · 时长 1:08
>
> 同一个 Hook 系统在 4 类不同任务上的应用对比。

---

## 本期你将学到

- Hooks 在 4 类不同任务上各自怎么配
- 4 类工具（Command / Prompt / HTTP / Agent）各自的适用边界
- 如何在 1 分钟里挑对工具类型

---

## [00:00:10] 场景对比一览

![](frames/seg_0000_000003.jpg)

| 工具类型 | 适用场景 | 反例（不要用它） |
|---|---|---|
| **Command** | 跑 lint / 跑测试 / 跑 shell 脚本 | 需要语义理解的复杂判断 |
| **Prompt** | 让模型对变更做自我审查 | 单纯调外部 API（用 HTTP） |
| **HTTP** | 发 Slack 通知 / 写 CI / 调 webhook | 本地文件操作（直接 Command） |
| **Agent** | 让独立 agent 做复核 / 复杂决策 | 简单 lint（杀鸡用牛刀） |

*总评*：Command 占 80% 实战需求，剩下 20% 才需要 Prompt / HTTP / Agent。**先默认 Command，再按场景升级**。

---

## 场景 1：写完文件自动扫描敏感信息（Command + PostToolUse）

[00:00:50] **最经典的安全场景**

![](frames/seg_0000_000008.jpg)

```json
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Write|Edit",
      "hooks": [{"type": "command", "command": "./scan-secrets.sh"}]
    }]
  }
}
```

*边界*：只在 Write/Edit 后跑（Read 不会触发）；scan 时间 < 200ms 才适合，更慢就要异步化。

---

## 场景 2：让 AI 对自己写的代码做自我审查（Prompt + PostToolUse）

[00:01:00] **何时升级到 Prompt 类型**

```yaml
hooks:
  PostToolUse:
    - matcher: "Write|Edit"
      type: prompt
      prompt: "审视刚才写入的文件 $TOOL_FILE，列出 3 个可能的安全风险"
```

*边界*：只在改动核心文件时启用，否则每次写文件都被 LLM "审视"一遍 token 爆炸。

---

## 场景 3：任务完成后通知团队（HTTP + Stop）

[00:01:05] **跨系统场景**

```yaml
hooks:
  Stop:
    - type: http
      url: https://hooks.slack.com/services/XXX/YYY/ZZZ
      payload: {"text": "Claude Code 任务完成"}
```

*边界*：仅团队协作场景；个人使用 Stop hook 没意义。

---

## 场景 4：让另一个 agent 独立审稿（Agent + Stop）

```yaml
hooks:
  Stop:
    - type: agent
      agent: code-reviewer
      input: $LAST_DIFF
```

*边界*：成本最高（启动子 agent ~ 数秒 + 上下文 token），只用于 PR 级别复核。

---

## 4 场景总评：怎么挑？

```text
日常 80% — Command + PostToolUse
质量 15% — Prompt + PostToolUse  
通知  4% — HTTP + Stop
复核  1% — Agent + Stop（成本最高）
```

按"出现频率 × 单次成本"决策，不要 over-engineer。
```

##### Skeleton 2：同一概念在不同应用场景串讲

<!-- 来源: output/douyin_trae_ai/summary.md (reshape，TRAE SOLO 的 3 种命令分别支撑 3 个场景的横向罗列形态) -->

```markdown
# 一套 Compound Engineering 的 3 种落地：摄取 / 消化 / 输出

> 来源：抖音 @数字游牧人 Samuel · 时长 4:12
>
> 同一个理念在 3 个不同任务上的应用串讲。

---

## 共同底色：Compound Engineering 是什么

[00:00:05] **核心理念**

![](frames/seg_0000_000001.jpg)

四步循环 **Plan → Work → Review → Compound**。**关键**：每次任务都把经验沉淀成下一次任务的起点。

下面 3 个场景都是这个理念的具体落地，**注意它们的共性 + 各自的差异**。

---

## 场景 1：摄取（把 YouTube 视频扒成本地笔记）

[00:01:58] **MTC 模式 + youtube-transcript skill**

![](frames/seg_0088_000005.jpg)

```text
/摄取 https://www.youtube.com/watch?v=rmvDxxNuBlg
```

agent 自动做 3 件事：调用 `youtube-transcript` → 抓字幕 → 归档到 `/raw`。

*这一步的 Compound 是什么*：原始 transcript + UP 主自己的元数据 → 永久可复用资产。

---

## 场景 2：消化（把 raw 编译成 wiki）

[00:02:30] **遍历 raw 提取知识点 → 写 wiki**

```text
/消化
```

agent 遍历 `/raw` 里最近变动的文件，抽取知识点，**按 Atomic Notes 拆分**写入 `/wiki`，互相建立反向链接。

*与场景 1 的差异*：
- 场景 1 是"抓"——读外部数据
- 场景 2 是"写"——产出结构化知识
- 共同点：都把这次产物保存为下次的输入

---

## 场景 3：输出（基于 wiki 生成知识卡片）

[00:03:15] **拉 wiki 拼回答 → 写 outputs**

```text
/输出-知识卡片 主题: Compound Engineering
```

agent 读取 `/wiki` 下相关条目，再生成一张知识卡片，要求**输出必须明确依赖了哪些知识条目**。

*与场景 1/2 的差异*：场景 3 是"消费"环节，但**它仍然 Compound**——回写新发现的缺口到 `/wiki`。

---

## 3 场景边界对比

| 场景 | 输入 | 输出 | Compound 形式 |
|---|---|---|---|
| 摄取 | 外部 URL | `/raw/*` | 元数据 + 来源标记 |
| 消化 | `/raw/*` | `/wiki/*` | atomic notes + 反向链接 |
| 输出 | 任务 + `/wiki/*` | `/outputs/*` | 缺口回写 wiki |

*整体判断*：3 个命令各自独立，但共享同一个底层 workspace（你的本地文件夹）。**这就是 Compound——状态共享 + 单向流动**。
```

#### Mode: interview-distillation（访谈萃取）

##### Skeleton 1：speaker turns + key claims + timestamp-navigable quotes（无 frames，blockquote 替代图片）

<!-- 来源: output/douyin_karpathy_llm_wiki/summary.md (reshape, 4:02 UP 主对 Karpathy gist 的判断+反方三连击；最贴合访谈萃取形态) -->

```markdown
# Karpathy 又被吹爆，但这次可能真不是炒作

> **视频信息**：抖音 @小宇玩 AI · 时长 4:02 · 中文解说 · 观点分享/技术判断
> **核心结论**：Karpathy 的 75 行 gist "LLM Wiki" 方法本身并不新——很多人已经跑了几个月。真正新的是他**第一次给它起了个名字**。

---

## [00:00:00] UP 主开场：方法不新，命名才新

> [00:00:00] UP 主："又火了、又颠覆了、又震惊了。"
>
> *他自己的判断*：这方法真不新，Karpathy 做的只是一件小事——第一次给它起了个名字。但起完名字 48 小时，三个开源项目抢着给它写实现。**这就是命名的力量。**

> [00:00:18] Karpathy 原话："Every query is rediscovering knowledge."
> （每次查询都在重新发现知识。）

*提炼*：UP 主把这条 gist 的爆点从"内容创新"改判为"命名创新"。这是判断他和其他"吹爆党"的分水岭。

---

## [00:00:28] 第一刀：RAG 的顺序搞反了

> [00:00:28] UP 主："RAG 老路的问题——你问 NotebookLM 一个问题，它的动作是临时去文件堆里捞段落，拼答案，问完就忘，下次又从零捞一遍。"

UP 主总结的"三层结构"正解：

| 层 | 内容 | LLM 的权限 |
|---|---|---|
| **Raw sources** | 论文、文章、报告，真理之源 | **只读不写** |
| **Wiki** | Markdown 页面 | **全权拥有** |
| **Schema** | `CLAUDE.md` 之类 | 告诉 LLM "你是 wiki 管理员" |

> [00:00:54] Karpathy gist 原文："The schema is the key configuration file — it's what makes the LLM a disciplined wiki maintainer rather than a generic chatbot."

---

## [00:01:25] 最狠的比方：新员工 vs 图书管理员

> [00:01:25] UP 主："RAG = 新员工。每次问问题都请一个新员工，现场翻文件柜。翻完他走了，啥都没留下。"
>
> [00:01:32] UP 主："LLM wiki = 图书管理员。他不会累。每来一本新书主动整理、交叉索引、标冲突。"

*独家证据*：UP 主补了一句 Karpathy 自己就跑了一个主题研究 wiki，**100 篇文章、40 万字**。

---

## [00:02:23] 反方三连击（UP 主"判断者人设"）

> [00:02:25] Hacker News @kubb（戳得最狠）："这方法不是无懈可击的。到一个临界复杂点就会崩——agent 维护不动了，开发者也看不懂了。"

> [00:02:35] Obsidian CEO @kepano（官方打补丁）："别直接在个人 vault 上跑 agents，会污染你真实的思考。给 agent 单独开一个'混乱 vault'玩。"
>
> 关键词：**mitigate contamination**。

> [00:02:48] B 站 11 赞本土吐槽："如果 wiki 的读者是 AI 不是人，AI 需要的是 git 快照式的版本 wiki，不是单一视图。"

**UP 主的最终判断**：

> [00:02:55] "这套真有效，但不是圣经。**个人和中等规模**它打爆 RAG。**企业级**和**给 AI 看的复杂场景**，RAG 还是主力。"

---

## [00:03:21] 收口：1945 年那个问题

> [00:03:21] UP 主："1945 年 Vannevar Bush 提出 Memex——一个个人知识网络。Bush 画出了方向，但他解决不了一个问题：谁来维护？过去 80 年这个位置是空的。"
>
> [00:03:42] UP 主结论："**LLM 终于补上了这一块。**"

---

## 关键引文速查（按时间戳跳转）

- `[00:00:18]` Karpathy: "Every query is rediscovering knowledge."
- `[00:00:54]` Karpathy: "Schema is what makes LLM a disciplined wiki maintainer."
- `[00:02:25]` @kubb: "到一个临界复杂点就会崩。"
- `[00:02:35]` @kepano: "Mitigate contamination."
- `[00:03:42]` UP 主: "LLM 终于补上了这一块。"
```

##### Skeleton 2：同一访谈按 chapters.json 切片（plan 03 引入 chapters.json 时的形态）

<!-- 来源: output/douyin_karpathy_llm_wiki/summary.md (reshape — 同一访谈按 chapters.json 4 章节而非 speaker turn 组织) -->

```markdown
# LLM Wiki 范式深入：4 章节版（chapters.json 驱动）

> **视频信息**：抖音 @小宇玩 AI · 时长 4:02
> **本 skeleton 演示**：当 `output/<slug>/chapters.json` 存在时，按章节而非按 speaker turn 组织
>
> **chapters.json 形态预览**（plan 03 落地）：
> ```json
> {"chapters":[
>   {"start":0,   "end":85,  "topic":"为什么 75 行 gist 突然炸了"},
>   {"start":85,  "end":170, "topic":"三层结构 + 三个动作"},
>   {"start":170, "end":260, "topic":"反方三连击"},
>   {"start":260, "end":242, "topic":"收口与判断"}
> ]}
> ```

---

## 第 1 章 [00:00:00–00:01:25]：为什么 75 行 gist 突然炸了

**核心命题**：方法不新，命名才新。

UP 主开场就抛出反共识立场：自己已经这么干了几个月，所以 Karpathy 这条 gist 的爆点不在"内容创新"而在"命名创新"。

> [00:00:18] Karpathy: "Every query is rediscovering knowledge."

*章节小结*：这一章回答的是"为什么这件事值得讲"，定下了 UP 主"判断者"的姿态——不吹不黑，看本质。

---

## 第 2 章 [00:01:25–00:02:23]：三层结构 + 三个动作

**核心命题**：RAG 是"新员工现查现忘"，LLM Wiki 是"图书管理员持续整理"。

| 层 | 角色 | LLM 权限 |
|---|---|---|
| Raw | 真理之源 | 只读 |
| Wiki | 编译产物 | 全权 |
| Schema | 行为规范 | LLM 自己读它 |

三个动作：**Ingest**（写入式更新而不是索引）/ **Query**（读编译好的 wiki）/ **Lint**（定期体检）。

*章节小结*：这一章是 UP 主对 Karpathy 原 gist 的核心论证压缩。**注意**：节奏快但每个概念都要在前一章基础上叠。

---

## 第 3 章 [00:02:23–00:04:20]：反方三连击

**核心命题**：UP 主特地把"判断者人设"立稳——他**不**做吹捧。

> [00:02:25] @kubb (Hacker News)："临界复杂点就会崩。"
>
> [00:02:35] @kepano (Obsidian CEO)："给 agent 单独开个'混乱 vault'。"
>
> [00:02:48] B 站 @某用户："Wiki 给 AI 读时需要 git 快照而非单一视图。"

UP 主立场：

> [00:02:55] "个人和中等规模它打爆 RAG；企业级 RAG 仍是主力。"

*章节小结*：这一章是全片"信息密度"最高的部分。如果只精读一章，选这章。

---

## 第 4 章 [00:04:20–00:04:02]：1945 年的旧问题与新答案

**核心命题**：Vannevar Bush 的 Memex 设想 1945 年就提出，缺的是"维护者"。LLM 是那个缺失的环。

> [00:03:42] UP 主结论："读一次，留一辈子。"

*章节小结*：传统知识管理软件 80 年里都没解决"持续维护"问题。LLM 改变的不是工具形态，是**自动化维护这件事终于变得可行**。

---

## 章节级关键判断

- 第 1 章：本质是命名学，不是方法学
- 第 2 章：编译 ≠ 索引，权限分层是关键
- 第 3 章：方法有清晰的边界，企业级请回 RAG
- 第 4 章：80 年缺口被 LLM 填上

*整体节奏*：UP 主用 4 章把"判断 → 论证 → 反驳 → 收口"四个动作压在 4 分钟内，节奏极紧。如果你做长访谈萃取，建议章节数 5-8 个，单章 5-15 分钟。
```

### UI 操作演示子规则（适用 replicate-guide / extension-applications 模式 — TEACH-09）

> 当 mode=`replicate-guide` 或 `extension-applications` 且视频内容是非代码类 UI 软件操作（如 Photoshop / Figma / Trae / Claude Code 桌面端 / Premiere 等），按以下 4 子规则增强写作精度。代码类视频（IDE 内 hands-on）**不**适用——代码 fence + 多模态精确抄录是更强的工具。

1. **Pixel-text 不确定引用** — UI 软件用 proportional 字体 + 抗锯齿，多模态识别准度低于 monospace 代码截图。
   - 指令 Claude `quote-with-uncertainty`：用 blockquote 加可信度备注
   - 写法示例：`> 该控件大致写着"图层不透明度"（多帧交叉验证后置信度中等）`
   - 不要伪造确定的引文（**不注水不编造**红线）；置信度低就明示 `（pixel-text 模糊，建议 user 在原视频对照）`

2. **Tooltip 遮挡检测**
   - 发现 tooltip 遮目标 → 用 `extract_frames --start <T-0.5> --end <T+0.5> --fps 4` 补抽前/后 0.5s 帧
   - 都遮 → 标 `*该值视图被 tooltip 遮挡，未取得*`，**不要猜值**
   - 例：滑块拖动时 tooltip 飘在数值上方 → 拿 tooltip 出现前 0.5s 的静态值

3. **光标不可见兜底**
   - 黑光标在黑 UI / 系统截屏不含光标 → 从前后帧 panel state diff 推点击位置
   - 命名一律按控件 label/icon（如"图层面板的眼睛图标" / "工具栏第 3 个钢笔图标"），**禁空间方位**（不写"屏幕左上角" / "中间偏右"）
   - 例：`你点击 [图层面板] 的 [小眼睛图标]，关闭该图层显示`

4. **`--width 1280/1920` 4K override**
   - 4K 录屏（3840×2160 或 2560×1440）抽 frame 时若 `default_scale: "854:-1"`（schedule.json 默认值）输出过小（< 800px 宽）会丢可读性
   - 解决：schedule.json 加 `"default_scale": "1280:-1"` 或 `"1920:-1"` 提示
   - 例：4K 屏录的 Photoshop UI：
     ```json
     {"version": 1, "default_scale": "1920:-1", "segments": [...]}
     ```

### Podcast / interview 模式骨架（适用 interview-distillation 模式 — TEACH-10 / TEACH-13）

> 当 mode=`interview-distillation` 时按以下骨架走，**不**改 `/summarize-video` 主流程 8 阶段（per D-21）。本骨架是 spike degrade 路径的形态：不依赖 `pyannote` diarization，由 Claude 从内容线索推断说话人。

#### Step 1: chapters.json 取代段落聚合作为结构单位

`silence-gap` 聚合（`agent/asr_v2.py:aggregate_paragraphs`）对 60min 闲聊体不灵；改用 Claude 直出 `output/<slug>/chapters.json`：

```json
{
  "version": 1,
  "video": "video.mp4",
  "chapters": [
    {"start": 0.0, "end": 540.0, "topic_title": "开场 + 嘉宾介绍",
     "summary_line": "Lex 介绍 Karpathy 在 OpenAI 的 history 与本期话题"},
    {"start": 540.0, "end": 1820.0, "topic_title": "ECS 之争",
     "summary_line": "OOP vs 数据导向; Karpathy 反对 ECS 是 over-engineering"}
  ]
}
```

字段说明：

- `start` / `end`：浮点秒，章节时间窗
- `topic_title`：章节主题（10-20 字，动词或名词短语；避免空泛 "讨论 X"）
- `summary_line`：一句话核心立场（10-30 字；提炼章节最关键的判断 / 引文 / 反差）
- `speaker_id?`：**可选** 字符串字段（degrade 路径不写；future GPU-diarization 路径填 pyannote 的 `SPEAKER_NN`）

Claude 通读 `paragraphs.json` 后判断章节切分（不是工具计算）；用 `Write` 工具写入 `output/<slug>/chapters.json`。**不**走 `python -m agent.tools chapters` 子命令——chapters.json 是 Claude-written artifact。

#### Step 2: 抽帧极少 — 每章节 1-2 帧（D-19 锁定）

不完全 skip frames（保留视觉锚点 — 讲者表情 / 嘉宾切换 / 屏幕分享）。schedule.json 形态：

```json
{
  "version": 1,
  "default_scale": "854:-1",
  "segments": [
    {"start": 0.0, "end": 540.0, "fps": 0.05, "label": "ch01-intro"},
    {"start": 540.0, "end": 1820.0, "fps": 0.005, "label": "ch02-ecs"}
  ]
}
```

按章节框定 `start`/`end`，每章节 1-2 帧由 `fps × duration` 自动控制（0.05 fps × 540s ≈ 27 帧；0.005 fps × 21min ≈ 6 帧覆盖 1280s）。完全 skip 留作 v2 `--no-frames` flag。

#### Step 3: 输出用 blockquote 替代图片嵌入

```markdown
## 第一章：ECS 之争

> [00:09:00] **Karpathy**："ECS 在 GPU shader 上有意义；但 game state 里你只是在重新发明一遍 OOP 的 dispatch table。"

Karpathy 反对的不是性能论点，而是抽象层次错位：游戏对象的生命周期模式是行为 + 状态强耦合的，硬拆数据层和系统层只是延迟了 dispatch 这件事。

> [00:11:30] **Lex**："但有些 high-perf engine 比如 Bevy 用得很彻底..."

> [00:11:45] **Karpathy**："那是 Rust 借用检查器的副产品，不是 ECS 的胜利。"
```

格式锁定（4 项不变量仍然适用 — 见 `### 格式锁定`）：

- `[HH:MM:SS]` 时间戳必须 8 字符
- 第二人称指令式（podcast 不强求——引文用第一人称、提炼用第二人称叙述也可）
- blockquote 引文 + 引号内是字面引文（不要改写嘉宾原话；改写的话用斜体提炼包裹，明示这是你提炼）
- 每章节标题下方可选 inline 一帧 `![](frames/seg_xxxx_xxxxxx.jpg)` 作为视觉切分参考——但**不在每段引文下嵌图**

#### Step 4: 从内容线索推断说话人（degrade 路径主流程 — D-14）

> **degrade 路径的核心**：Claude 多模态本身可从内容线索推断说话人切换，**不**依赖 pyannote diarization。除非 user 主动跑 `python -m agent.tools diarize` 并产出 diarization.json，否则 Claude 用以下 5 条线索推断：

1. **开场白**："欢迎来到 X 节目，今天嘉宾是 Y" → 主持人 = X 节目主，嘉宾 = Y
2. **谁问谁答**：句末是问号 / "你怎么看" / "可以聊聊..." → 提问者；句末是断言 / "我认为" / 数据陈述 → 回答者
3. **提问语气 vs 回答语气**：开放式问题 + 短句 = 主持人；展开 + 引用历史 + 长句 = 嘉宾
4. **嘉宾名 from intro**：开场 30s 内主持人通常会说 "今天我请到 X" — 把 X 锁定为嘉宾说话人
5. **blockquote attribution**：写出来时一律用 `> [HH:MM:SS] **嘉宾名**："..."` 形式标 attribution；**实在分不清**用 `> [HH:MM:SS] **speaker_id="?"**："..."` 占位（不要瞎猜身份）

degrade 路径示例（无 diarization.json）：

```markdown
> [00:00:18] **主持人 Lex**："Today I'm honored to talk to Andrej Karpathy."
> [00:00:25] **Karpathy**：（接话，长句展开他在 OpenAI 的早期经历）
> [00:01:42] **speaker_id="?"**："Wait, was that Slack bot you mentioned really running in production?"
> [00:01:48] **Karpathy**："Yeah, three weeks. Then we noticed the GPU bill."
```

第 3 行用 `speaker_id="?"` 是因为短打断不能确定是 Lex 还是另一位嘉宾——明示比瞎猜好。

#### Step 5（可选）: diarization.json 提供 speaker_id

> 如 user 已跑 `python -m agent.tools diarize <audio.wav> --out diarization.json`（pyannote opt-in），Claude 读取 `diarization.json` 后能把 `speaker_id` 与 `chapters.json` 时间窗对齐，更准确推断每段话谁说的。

匹配规则：对每个 blockquote 的 `[HH:MM:SS]` 时间戳，在 `diarization.json.turns[]` 中找包含该时间点的 turn，把 `speaker_id` 替换 `?` 占位 → 写出 `> [00:01:42] **SPEAKER_01**："..."`。然后由 Claude 根据上下文（第 4 步线索）把 `SPEAKER_01` 这种抽象 ID 进一步映射为真实姓名（Lex / Karpathy）——**真实姓名映射仍由 Claude 推断，pyannote 只给抽象 ID**。

#### VTT fold-in（D-32 — 与 Phase 3 subtitle_origin 联动）

> **如果 `meta.json.subtitle_origin == "creator"` 且 mode == "interview-distillation"**：VTT 字幕已是 creator-uploaded 高质量来源（YouTube 创作者上传的人工字幕，95%+ 准确度），**Claude 可直接信任引用，不需要 ASR 重跑**。直接读 `output/<slug>/video.<lang>.vtt`，按时间戳引文使用。这比 faster-whisper ASR 在长访谈上的 70-85% 准确度高得多（PITFALLS P3.3）。

VTT 优先级（locked at `agent/sources/youtube.py` Phase 5 D-31 / WR-02）：`zh-Hans > zh-Hant > zh > en > 任何 manual > 任何 auto-generated`。yt-dlp 按列表顺序匹配 manual subs 优先；manual 全无时按相同顺序匹配 auto-gen 兜底。

判别 origin（已落地 Phase 3 SRC-08）：

- `meta.json.subtitle_origin == "creator"` → manual / creator-uploaded VTT，**直接信任引用**
- `meta.json.subtitle_origin == "auto"` → auto-generated 字幕，与 ASR 同等可信度，照常 ASR 重跑
- `meta.json.subtitle_origin == "none"` → 无 VTT，必走 ASR 路径（faster-whisper + `--profile podcast`）

---

## v1.1 opt-in marker + 4 K5 emitters (Phase 07)

> 这一节是 v1.1 summary-quality milestone 的入口契约。**v1.0 archives 永远不被动升级** — 只有显式 opt-in 的 slug 才走 v1.1 路径。

### `.v11_features.json` opt-in marker

每个 slug 的 `output/<slug>/.v11_features.json` 是 v1.1 路径的开关。Schema：

```json
{
  "version": 1,
  "features_enabled": ["transcribe_lint", "mode_signals", "schedule_suggest", "trace_tokens", "self_contained_header", "glossary", "tldr", "verifier"],
  "marker_set_at": "<ISO-8601 UTC>"
}
```

- **缺失 marker**：silently 走 v1.0 path，所有 v1.1 sidecar 不写、prompt extension 不触发（D-29 byte-equal preserved）
- **显式 opt-in**：用 `python -c "from agent._v11 import set_v11_marker; set_v11_marker('output/<slug>', ['transcribe_lint', 'mode_signals'])"` 选择性开启
- **regression test**：每次 phase 07 / 08 / 09 close 前必跑 `python -m scripts.replay_v10_archives`；任一字节 diff = phase 不可 ship

### 4 个 K5 read-only signal emitters

Phase 07 ship 4 个工具，**只发信号、不写决策 artifact**。Claude 读完信号后仍是唯一决策者（K5 边界）。

| 命令 | 输出 | 用途 |
|---|---|---|
| `python -m agent.tools transcribe_lint output/<slug>` | `transcribe_lint_warnings.json` | L1 ASR 可疑词检测：5 strategies = title_token + frequency_variance + mixed_script + hapax + **homophone_cluster** (pypinyin 同音聚类，CORR-01a 4 mandated 之一)。Phase 08 L2 prompt 读它做上下文修复。**注意**：和 Phase 5 transcribe `--profile podcast` 的 `transcribe_warnings.json` 不同文件（CR-01 fix 隔离） |
| `python -m agent.tools mode_signals output/<slug>/paragraphs.json --out output/<slug>/mode_signals.json` | `mode_signals.json` | 5 个客观信号（code-fence rate / step markers / question density / speaker turns / cross-tool comparisons）+ raw evidence。**没有** `recommended_mode` 字段（K5 边界，PITFALLS P-07）。Claude 写 plan 时可参考 |
| `python -m agent.tools schedule_suggest output/<slug> [--duration <float>]` | `schedule_suggestion.json` | 组合 paragraphs + scenes + silence 输出建议 fps 段 + **强制 FPS-04 baseline**（fps ≤ 0.1 覆盖全片，避免 strict-only 触雷 D-08 fallback gate）。Claude 拿建议自己 author schedule artifact。`--duration` 用于 video.mp4 已清理的归档（W5 fix） |
| `python -m agent.tools glossary_audit` | stdout (or `--json`) | Read-only 审计 `output/_glossary.md`（Phase 08 TEACH-A3 落地）：报重复 term + 冲突定义。**永不**改 glossary 文件（K5） |

**Schema 锁死**：4 个 emitter 的输出 schema 在 `.planning/phases/07-warm-up-k5-emitters-d-29-foundation/07-03-PLAN.md` 的 interfaces section。Phase 08/09 读这些 sidecar 时按锁死的 key 名解析。

**K5 boundary 静态断言**：4 个 emitter 的源代码（含 docstring）**不允许**包含字面量 `summary.md` / `plan.md` / `schedule.json`。`tests/test_k5_emitters.py` 在 `inspect.getsource()` 上强校验（每个 cmd_* 函数 + 每个模块文件）。说明里改用 "the schedule artifact" / "the plan artifact" / "the summary artifact" 这种描述性短语。

### Token budget baseline

`output/<slug>/.token_budget.json` 在 3 个代表性 v1.0 archive 上落地（PRE-V11-03）：
- `output/BV132wizyEEB/.token_budget.json` — replicate-guide 基线
- `output/douyin_karpathy_llm_wiki/.token_budget.json` — interview-distillation 基线
- `output/douyin_claude_code_hooks/.token_budget.json` — extension-applications 基线

Phase 09 SC#4 断言：v1.1 全开 ≤ 2x baseline。超出则 phase verification fail。

### Multi-terminal lock 域扩展

`~/.videoSummary/.queue.lock` (Phase 07 MISC-02) 是 v1.1 第一个跨 terminal 锁域。复用 `agent/_lock.py:FileLock`，stale-PID 接管逻辑同 `.resume.lock`。Phase 08 TEACH-A3 会再加 `output/.glossary.lock`（cross-slug glossary append 串行化）。

---

## v1.1 自适应教学文档增强 (Phase 08)

> 这一节是 **opt-in 增强规则**。**只有** `output/<slug>/.v11_features.json` marker 显式启用对应 feature 的 slug 才走以下规则。无 marker 的 slug（包括 17 archived）继续按 v1.0 形态写 summary.md（D-29 byte-equal preserved）。
>
> **检查方式**：写每条 summary 之前，先用 `python -c "from agent._v11 import is_v11_enabled; print(is_v11_enabled('output/<slug>', '<feature_name>'))"` 检查 marker 是否启用对应 feature。返回 `False` 则该 feature 不触发，按 v1.0 path 写。
>
> **6 条 feature 一栏速查**（V11_FEATURES allowlist 中的对应 flag 名）：
>
> | Feature flag | 触发的规则 | 在 /summarize-video 哪个 phase 生效 |
> |---|---|---|
> | `l2_l3_correction` | CORR-01b/c — 读 `transcribe_lint_warnings.json` 做 L2 上下文修复 + L3 多模态兜底 | Phase 2（写 plan.md 时） |
> | `inline_trace_tokens` | CORR-02 — 每个 claim 后加 `[seg_*.jpg @ HH:MM:SS]` 行内溯源 token | Phase 6（写正文时） |
> | `self_check_confidence` | CORR-02 self-check pass — confidence < 80% 加 `[?]`，summary 末尾汇总 | Phase 8（收尾时） |
> | `self_contained_header` | TEACH-A1 + TEACH-A2 — 顶部"你需要知道什么"+"你不需要知道什么"+ 首次术语 inline 注解 | Phase 6（写正文起始时） |
> | `cross_slug_glossary` | TEACH-A3 — 首次术语用 `glossary append` CLI 写到 `output/_glossary.md` | Phase 6（每写完一个新术语时） |
> | `tldr_speedrun` | TEACH-B — 长视频顶部"5 分钟速读版"块 | Phase 7（写完正文后 LAST） |

### CORR-01b — L2 上下文修复（在 Phase 2 写 plan.md 时执行）

**触发条件**：`is_v11_enabled(slug, "l2_l3_correction")` 返回 True AND `output/<slug>/transcribe_lint_warnings.json` 存在且 `warnings` 数组非空。

**步骤**：

1. Read `output/<slug>/transcribe_lint_warnings.json`（Phase 07 CORR-01a 产出；schema 见 `agent/transcribe_lint.py` 模块 docstring）
2. Read `output/<slug>/meta.json`（标题 + UP 主 + description）
3. 对每个 warning，按 evidence_source + 上下文交叉验证决定是否采纳：
   - **L2 evidence sources**（每个 source 算 1 条独立证据）：
     - meta.title 子串匹配 suggested_text
     - meta.uploader / channel name 子串匹配
     - meta.description 子串匹配
     - segs.json 同段或相邻段（±2 段）出现 suggested_text 的高频形式
     - 视频简介 / chapter 标题（如有）
   - **采纳门槛（HARD CAP，违反则跳过）**：≥ 2 条独立 evidence sources 同时支持 suggested_text，才采纳
4. **采纳上限**：max 10 auto-applied corrections per slug。超过 10 条候选时按 L1 confidence 降序取前 10。其余记入 plan.md "未采纳的候选" 段。
5. 把所有 **采纳的** corrections 写到 `output/<slug>/plan.md` 顶部新增 段（在 5 字段 YAML front-matter 之后、第一个章节标题之前）：

```markdown
## 已自动修正的术语 (CORR-01b L2)

| 错误形式 | 正确形式 | 出现段 | 证据来源 | L1 confidence |
|---|---|---|---|---|
| Lora | LoRA (Low-Rank Adaptation) | para_0003 / para_0017 | meta.title + segs.json (LoRA × 4) | 0.65 |
| 木下 | Mucha | para_0021 | meta.description + frequency_variance | 0.72 |

> 自动修正自 transcribe_lint_warnings.json 的 L1 候选；L2 上下文交叉验证 ≥ 2 sources 才采纳。
> 全文写作时按"正确形式"列引用；不再回头改 segs.json (D-29 invariant)。
```

6. **D-29 invariant**：**绝不**修改 `segs.json`。修正只发生在 plan.md（透明性表）+ summary.md 写作时（按 plan.md 的"正确形式"列引用）。`segs.json` 永远是 ASR 原始输出。

### CORR-01c — L3 多模态兜底（在 Phase 4 看帧时执行）

**触发条件**：`is_v11_enabled(slug, "l2_l3_correction")` 返回 True AND 某 warning 满足 `L1 confidence < 60% AND L2 evidence < 2 sources`（即 L2 不足以采纳）。

**步骤**：

1. 对每个触发 L3 的 warning：
   - 取 warning 的 `start` 时间戳（来自 transcribe_lint_warnings.json）
   - **时间窗 HARD CAP**：抽帧范围 `[start - 0.5s, start + 0.5s]`（共 1 秒窗口）
   - **帧数 HARD CAP**：max 5 frames per warning
2. 用 `python -m agent.tools extract_frames <video> --out output/<slug>/frames --fps 5 --start <start-0.5> --end <start+0.5>` 抽帧
3. Read 抽出的 ≤ 5 帧，看图片中是否出现 suspect_text 或 suggested_text 的视觉形态（标题板 / 工具 UI / 代码 fence 中的拼写）
4. 决策：
   - 帧中**清晰出现** suggested_text → 采纳，写入 plan.md "已自动修正的术语" 表（标 evidence_source = `multimodal_frame`）
   - 帧中**清晰出现** suspect_text 且与 suggested_text 不一致 → 拒绝采纳，标 `[?]` 在 summary 中（CORR-02 self-check 会汇总）
   - 帧中**都无清晰证据** → 拒绝采纳，标 `[?]`
5. **采纳上限**：L3 采纳计入 CORR-01b 的 10 条总额（不分开计算），避免 L3 绕过总上限

### CORR-02 — 行内溯源 token + 自检 pass

**触发条件 (token)**：`is_v11_enabled(slug, "inline_trace_tokens")` 返回 True
**触发条件 (self-check)**：`is_v11_enabled(slug, "self_check_confidence")` 返回 True

#### 行内溯源 token 格式（Phase 6 写正文时）

**Token 格式锁**（违反一项即 5th format-spec invariant 违规）：

- **图片引用 token**：`[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]`（HH:MM:SS 严格 8 字符，per 1st format-spec invariant）
- **段落引用 token**：`[para_NNNN @ HH:MM:SS]`（para_ID 来自 paragraphs.json，4 位补零）
- **位置**：紧跟 claim 句末，在句号 / 问号 / 感叹号**之前**插入；多个 token 用 ` + ` 分隔
- **示例**：
  - 单图：`这一步的 fps 设为 0.4 [seg_0030_000015.jpg @ 00:01:23]。`
  - 单段：`UP 反对 ECS 的核心论点是抽象层次错位 [para_0042 @ 00:09:00]。`
  - 多源：`Karpathy 在 OpenAI 待了 18 个月 [para_0007 @ 00:00:25] + [seg_0010_000003.jpg @ 00:00:25]。`

#### 引用资格规则（哪些句子需要 token）

**REQUIRED token 的句子类型**：
- 具体 claim（"UP 在 IDE 里输入了 X"）
- 具体参数值（"fps 设为 0.4 / context_window=4096 / temperature=0.7"）
- 代码片段引用（"以下代码来自 main.py，逐行抄录"——代码 fence 上方需 token）
- UI 操作引用（"点击工具栏第 3 个图标 / 按 Cmd+K 打开命令面板"）
- 截图引用（任何 `![](frames/seg_*.jpg)` 之前需 token；图片本身的 caption alt 不算 claim）

**FORBIDDEN token 的位置**（强制不放 token）：
- TL;DR 块内（`## 5 分钟速读版` — 用 `详见 §三、消化阶段` 的章节锚点替代）
- Glossary 内的 inline term annotation（`术语 (English / 中文释义)` 后不加 token）
- 顶部 "你需要知道什么" / "你不需要知道什么" prelude 段
- 章节末尾的 "*章节小结*" / "*为什么这么做*" transition 段（这些是 Claude 的提炼，不是字面 claim）

**OPTIONAL token 的位置**：
- Narrative 连接句（"接下来 UP 切换到了..."—— 可加可不加，看是否有时间戳锚点价值）
- Paraphrase 概述（"这一节核心论点是 X"——如果是 Claude 提炼，无字面 claim，可不加）

**密度目标**：avg ≤ 1 citation per 3 sentences（Phase 09 `summary_lint` 会量化校验）

#### 自检 pass（Phase 8 收尾时）

**触发条件**：`is_v11_enabled(slug, "self_check_confidence")` 返回 True

**步骤**：
1. 写完正文后，重读全文（第 2 遍）
2. 对每个带 token 的 claim 句，自评 confidence：
   - **≥ 80%**（基于字幕原文 + 帧截图 + meta，3 source 中至少 2 个直接支持）→ 不动
   - **< 80%**（仅 1 source 支持 / 部分推断 / 帧不清晰）→ 在句末 token 之后 + 句号之前插入 `[?]` 标记
   - **示例**：`这一步的 fps 设为 0.4 [seg_0030_000015.jpg @ 00:01:23][?]。`
3. 在 summary.md 末尾追加 `## 写作自检 (CORR-02)` 段：

```markdown
## 写作自检 (CORR-02)

- 总 claim 数（带 token 的句子）：47
- 低置信度标记 `[?]` 数：3
- 低置信度比例：6.4% (3/47)
- 修正历史 plan.md "已自动修正的术语" 表 → 7 条 L2 + 1 条 L3 共 8 条采纳

> 低置信度 `[?]` 句子的具体行号：
> - L142: "UP 提到 LangChain 的某个版本 [?]" — 帧中只看到 "LangChain" 字样未确认版本号
> - L257: "Tokenizer 在 GPT-4 上 vocab_size=100k [?]" — 字幕里只说"差不多十万"
> - L389: "训练用了大约 8000 步 [?]" — 字幕里说"8 千步左右"

详细引用资格规则见 § v1.1 自适应教学文档增强 → CORR-02 → 引用资格规则。
```

### TEACH-A1 — 首次术语 inline 注解

**触发条件**：`is_v11_enabled(slug, "self_contained_header")` 返回 True

**规则**：
- 每个**新术语第一次出现**时加 inline 注解：`术语 (English / 中文释义)`
- 后续出现可省略
- **FORBIDDEN 注解的术语**（普世术语，注解会显得 patronizing）：
  - 编程语言名：`Python` / `JavaScript` / `Go` / `Rust` / `Ruby` / `C++`
  - 数据格式：`JSON` / `YAML` / `XML` / `CSV` / `Markdown`
  - 工具基础：`Claude` / `Git` / `Docker` / `npm` / `pip`
  - HTTP 基础：`URL` / `API` / `HTTP` / `HTTPS`
  - 通用名词：`AI` / `ML` / `LLM`（除非视频专门讨论 LLM 内部机制）
- **REQUIRED 注解的术语类型**：
  - 领域专属概念：`LoRA (Low-Rank Adaptation)` / `ECS (Entity-Component-System)` / `RAG (Retrieval-Augmented Generation)`
  - 工具内部术语：`MCP (Model Context Protocol)` / `Compound Engineering (复利工程)`
  - 缩写首次出现：`SDXL (Stable Diffusion XL)`

**示例**：
- ✓ `本节用 LoRA (Low-Rank Adaptation) 微调，相比全参微调显存降到 1/10。后续段落直接说 LoRA，不再注解。`
- ✗ `打开 Python (一种编程语言)` — 普世术语注解会 patronizing

### TEACH-A2 — 自包含零基础 header（顶部固定结构）

**触发条件**：`is_v11_enabled(slug, "self_contained_header")` 返回 True

**结构（写在 summary.md 顶部，紧接标题之后）**：

```markdown
# <视频标题>

> UP / 来源：@xxx · 时长 MM:SS · [原视频链接](https://...)

## 读这篇前你需要知道

- <≤ 3 行先决条件>。每行写"知道什么 + 为什么需要"。
- <第 2 条>
- <第 3 条>

## 你不需要知道什么

- <≤ 3 行豁免>。每行写"不需要先学 X，文中会注解"。
- <第 2 条>
- <第 3 条>

[optional: ## 5 分钟速读版（TEACH-B 触发时插入这里，详见下文）]

---

# 一、<第一章正文标题>

...
```

**Hard caps**:
- "你需要知道什么" 段 ≤ 3 行
- "你不需要知道什么" 段 ≤ 3 行
- Header 总计 ≤ 6 行（不含 TL;DR 块）
- TL;DR 块（如有）独立 10-15 行 hard cap，不计入 header

**Tone constraints (anti-patronizing)**:
- **FORBIDDEN 短语**（违反则要 self-edit 重写该句）：
  - `简单来说` / `说白了` / `一言以蔽之` / `说人话就是`
  - `你可能不知道` / `相信很多人不清楚` / `你是不是觉得`
  - `通俗讲` / `打个比方` 单独使用（"打个比方" 后接具体类比 OK；空打比方禁用）
- **REQUIRED 语气**：直接陈述事实 + 第二人称指令式（"你需要先理解 X" 不是 "你可能没听说过 X"）

### TEACH-A3 — 跨 slug glossary 累积（在写正文遇到首次术语时执行）

**触发条件**：`is_v11_enabled(slug, "cross_slug_glossary")` 返回 True

**inline-first invariant (CRITICAL)**：每个首次出现的术语**必须**先按 TEACH-A1 加 inline 注解，**然后**再调用 glossary append。Glossary 是 fallback / 跨文档累积参考，**不是**首选阅读路径。**禁止**用"glossary 里有"作为跳过 inline 注解的理由。

**步骤**（每写完一个新术语的 inline 注解后立即执行）：

1. 调用 glossary append CLI（Plan 08-01 提供）：

```bash
python -m agent.tools glossary append \
  --slug <current_slug> \
  --term "LoRA (Low-Rank Adaptation)" \
  --definition "参数高效的微调技术 — 冻结预训练权重，只训练插入的低秩矩阵。" \
  --context "本视频用 LoRA 减少显存占用"
```

2. CLI 返回 `{"action": "appended"}` 或 `{"action": "skipped", "reason": "duplicate_slug_link"}`。两者都 OK，继续写作。
3. CLI 是 idempotent + FileLock 串行化（多个 terminal 并行写不同 slug 时不会撕裂）。
4. **绝不**在 summary.md 中嵌入 glossary 的链接（如 `详见 [output/_glossary.md](../../_glossary.md)`）—— glossary 是聚合视图，summary 应自包含可读。

**audit (Phase 7 收尾时建议跑一次)**：

```bash
python -m agent.tools glossary audit --json
```

报告 `duplicate_terms` / `conflicting_definitions` — 如有冲突（同一 term 不同 slug 给了不同 definition），由 Claude 决定是否手动统一（first-seen-wins 是默认 schema，但 audit 提示有歧义）。

### TEACH-B — 长视频 5 分钟速读版

**触发条件**：`is_v11_enabled(slug, "tldr_speedrun")` 返回 True AND（`paragraphs.json` 末尾段的 `end > 1200`（视频 > 20 分钟）OR plan.md front-matter `estimated_sections > 50`）

**位置**：在 TEACH-A2 header 之后、正文之前的 `## 5 分钟速读版` 段。

**结构（10-15 行 hard cap，max 20）**：

```markdown
## 5 分钟速读版

**核心结论**：<1 句，整篇 summary 最重要的一个判断>

**工作流速查表**：
1. <动词短语，章节 1 的核心动作>（详见 §一、<章节 1 标题>）
2. <动词短语>（详见 §二、<章节 2 标题>）
3. <动词短语>（详见 §三、<章节 3 标题>）
[... 最多 5-7 步，超过则压缩到 5 步以内]

**必看时间戳**（3-5 个）：
- `[00:01:23]` <这个时间戳为什么必看>
- `[00:09:00]` <第 2 个>
- `[00:15:42]` <第 3 个>

**何时跳读**：如果你只关心 X，直接跳到 §四、<章节 4>。
```

**关键规则**：

1. **写在 LAST**：必须在写完正文 + glossary appends 后才生成 TL;DR。这是防 drift 的核心约束（per P-06）。先写 TL;DR 再写正文 → 正文偏离 TL;DR 承诺。
2. **零 citation 在内**：FORBIDDEN 在 TL;DR 块内放 `[seg_*.jpg @ HH:MM:SS]` 或 `[para_NNNN @ HH:MM:SS]` token。改用 markdown 章节锚点 `详见 §三、消化阶段`（per CORR-02 引用资格规则的 FORBIDDEN 列）。
3. **同步检查（写完后自检）**：
   - **replicate-guide mode**：TL;DR "工作流速查表" 步数 ≈ 正文一级 H2 章节数（差距 ≤ 20%）。差距 > 20% → 在 plan.md 末尾追加一行 `tldr_drift_warning: TL;DR steps=N, body H2=M, ratio=...`，**不**自动修复（Claude is decider，per K2）
   - **interview-distillation mode**：TL;DR "必看时间戳" 数 ≈ chapters.json `chapters` 数（差距 ≤ 30%）
   - 其他 mode：sync check 由 Claude 自定义判断
4. **行数硬上限**：10-15 行是目标，max 20 行。超 20 行 → 重写 TL;DR 压缩信息密度，不是放宽上限。

---

## v1.1 校对自动化 (Phase 09)

> 这一节是 v1.1 summary-quality 的最后一层 —— 把"读起来正确"升级到"机械可证 + 独立 agent 复审 + max-1 自动修订"。**只有** `output/<slug>/.v11_features.json` marker 显式启用 `summary_lint` 或 `verifier_phase_75` 的 slug 才走以下规则。无 marker 的 slug（包括 17 archived）不受影响（D-29 byte-equal preserved）。

> **降级开关**：环境变量 `VIDEOSUMMARY_SKIP_REVIEWER=1` 直接跳过整个 Phase 7.5 verifier subagent + rewrite cycle（low-quota fallback；P-09 token budget compounding 兜底）。`summary_lint` CLI 仍可被显式调用，不受降级开关影响。

### CORR-03a：`summary_lint` 机械校验 CLI

**触发条件**：用户/Claude 显式 invoke `python -m agent.tools summary_lint <slug>/summary.md`。**不**自动触发（K5：Claude 决策何时跑机械 lint）。

**检查项**（写入 `output/<slug>/summary_lint.json`）：

1. **5 项 format-spec 不变量**（CLAUDE.md `### 格式锁定` 4+1）：
   - `timestamp_format`：`[HH:MM:SS]` 必须 8 字符
   - `code_fence_language`：每个 fenced code block 必须显式声明语言（`gdscript` / `python` / `bash` / `json` / `yaml` / `text` / `console`）
   - `relative_frame_paths`：`![](frames/seg_xxxx_xxxxxx.jpg)` 相对路径，禁止 absolute / http
   - `second_person_imperative`：禁止 `我们打开` / `XXX 被打开`，必须 `你打开 XXX`
   - `trace_after_claim`：每个 load-bearing claim 行尾必须有 `[seg_*.jpg @ HH:MM:SS]` 或 `[para_NNNN @ HH:MM:SS]` token（仅当 marker `inline_trace_tokens` 启用）
2. **citation density 统计**（per CORR-02 引用资格规则）：`claims_total` / `claims_with_trace` / `claims_without_trace` (line + snippet) / `trace_density` / `uncertainty_markers` (`[?]` 计数)
3. **引用资格违规** (`citation_eligibility_violations`)：trace token 出现在 FORBIDDEN 段（TL;DR / 你需要知道什么 / 你不需要知道什么 / 章节小结 / 总评）→ 1 entry per 违规
4. **glossary 一致性漂移** (`glossary_inconsistencies`)：summary 内 `LoRA (Low-Rank Adaptation)` 与 `output/_glossary.md` 内 `## LoRA (Low-Rank Adaptation Model)` 定义不同 → drift_detected: true

**K5 边界**：summary_lint 是只读 CLI；它**不修改** summary 文件，**不**在 plan.md / schedule.json 上 dispatch 任何动作。`tests/test_k5_emitters.py` 用 `_WRITE_PATTERNS_FORBIDDEN` 正则静态断言。

**state.jsonl 事件**：每次 invoke 写一行 `{"stage":"summary_lint", "status":"completed", "details":{"claims_total":N, "claims_with_trace":M, "format_violations_count":K, ...}}`。事件类型名：`summary_lint_run`。

### CORR-03b：Phase 7.5 verifier subagent

**触发条件**：`/summarize-video` Phase 7 写完 summary.md 后，**且** 满足全部 3 条：
1. `is_v11_enabled('output/<slug>', 'verifier_phase_75')` 返回 True
2. `os.environ.get('VIDEOSUMMARY_SKIP_REVIEWER') != '1'`
3. Phase 7.5 之前 `python -m agent.tools summary_lint output/<slug>/summary.md` 已跑过（产出 `summary_lint.json`）

**执行**：Claude 在 `/summarize-video` Phase 7.5 子步骤中 spawn 一个独立的 `Task` subagent：

```python
Task(
    subagent_type="general-purpose",
    description="Phase 7.5 summary verifier (CORR-03b scope-locked)",
    prompt=<下方 Verifier Prompt 段，逐字 inline>,
)
```

Subagent 读以下 5 个文件 + 至多 10 帧：

- `output/<slug>/summary.md` — 待校对正文
- `output/<slug>/paragraphs.json` — 时间戳真实性 ground truth
- `output/<slug>/plan.md` — mode 规则 + 已校正术语清单
- `output/<slug>/transcribe_lint_warnings.json` — Phase 07 CORR-01a L1 warnings（如存在）
- `output/<slug>/summary_lint.json` — Phase 09 CORR-03a 机械校验结果
- `output/_glossary.md` — Phase 08 cross-slug glossary（如存在）
- **至多 10 帧** sampled from `summary_lint.json.citation_stats.claims_without_trace[]` 的 line snippet 中提到的 `frames/seg_*.jpg` 路径（P-09 token budget 硬上限）

**输出**：`output/<slug>/<slug>-REVIEW.md`，三级 finding（critical / warning / info）。

**state.jsonl 事件**：subagent 完成后由 caller 调用 `agent.verifier_events.emit_verifier_run(slug_dir, severity_counts={...}, output_path=..., duration_ms=...)`。事件类型名：`verifier_run`。

#### Verifier Prompt（逐字使用，不要改写）

```text
你是 summary 质量复审 agent。**严格 scope-locked**：你**只能**针对以下 4 类问题挑出 critical / warning / info 三级 finding。**任何超出 scope 的 finding（哪怕你觉得真的有问题）都必须丢弃，不写入 REVIEW.md。**

**REQUIRED scope（你能挑的问题）：**

1. **format-spec 4+1 项不变量**（参见 CLAUDE.md `### 格式锁定`）：
   - `[HH:MM:SS]` 必须 8 字符
   - 每个 fenced code block 必须有显式语言
   - 图片路径必须 `frames/...` 相对路径
   - 第二人称指令式（禁 `我们` / 禁被动语态）
   - load-bearing claim 必须带 `[seg_*.jpg @ HH:MM:SS]` 或 `[para_NNNN @ HH:MM:SS]` trace token
2. **plan.md mode 规则一致性**（参见 CLAUDE.md § 视频类型变奏 → 4 模式 skeleton）：
   - 如果 plan.md `mode: replicate-guide` → summary 应有按步骤的章节 + 每步带操作截图
   - 如果 plan.md `mode: interview-distillation` → summary 应有 blockquote 引文 + speaker turn 标注，**不**应有逐步 hands-on 代码
   - 如果 plan.md `mode: concept-explanation` → summary 应是"核心问题 → 反直觉答案 → 最小例证 → 应用边界"流
   - 如果 plan.md `mode: extension-applications` → summary 应是横向罗列 3-5 个场景 + 边界对比表
3. **inline trace token timestamp 真实性**：每个 `[para_NNNN @ HH:MM:SS]` 的 timestamp 必须存在于 `paragraphs.json` 某个 paragraph 的 `[start, end]` 区间。**逐个核对**——你拿到 paragraphs.json 全文，对每个 trace token 做窗口匹配；不在任何 paragraph 区间内的 timestamp = critical finding。
4. **glossary term 一致性**：每个 summary 内 inline `术语 (English/中文释义)` 注解，如果该 term 在 `output/_glossary.md` 也出现，定义必须 byte-equal（first-seen-wins 已经处理过 conflicts，所以你看到的就是 canonical 定义）。drift = warning，不是 critical（除非该术语是 plan.md 已记录的 L2 校正项 —— 那种是 critical）。

**FORBIDDEN scope（你绝对不能写进 REVIEW.md 的东西）：**

- "这段说不清楚" / "这里应该改写" / "语气不好" / "解释太啰嗦" / "新读者可能看不懂" / "可以加一个例子" —— 任何形式的**教学质量评判** ✗
- "这个步骤的顺序是不是反了" / "你应该先讲 X 再讲 Y" —— 任何形式的**章节结构建议** ✗
- "代码缩进不一致" / "标点符号能不能更统一" —— 任何**文字层 nit-pick**（这些是 summary_lint 的工作；如果 summary_lint 没报，就不关你事） ✗
- "frame seg_NNNN.jpg 看起来像是 Y 不是 X" —— 任何**事实层重新解读 frame 的内容**（你只校 timestamp 真实性，不重新解读 frame；多模态重读 frame 由 author 在 Phase 4 做过，你不再做） ✗

**每个 finding 必须给 EVIDENCE，不是主观意见：**

- critical：写明 `summary.md 第 N 行 / claim "<verbatim 原文>" / 违反规则: <REQUIRED scope 1-4 哪一条> / 证据: <paragraphs.json 区间 / glossary 定义 / format spec 字面规则>`
- warning：同上，但严重度低（e.g., trace_density < 0.3、UI 第二人称违规但稀疏）
- info：同上，severity 最低（e.g., glossary 一处轻微定义漂移）

**REVIEW.md 输出格式（markdown）：**

```markdown
# <slug>-REVIEW.md

> Phase 7.5 verifier subagent (CORR-03b) 报告。Scope 锁定 4 类：format-spec / mode 规则 / citation timestamp / glossary 一致性。

## Critical (N 项)

- [ ] **summary.md L42** (规则违反: trace_after_claim)
  - claim: "fps=0.3 抽帧"
  - 证据: 该行无 [seg_*.jpg @ HH:MM:SS] 或 [para_NNNN @ HH:MM:SS] token
  - 建议: 加 trace token 指向对应 paragraph 或 frame

## Warning (M 项)

...

## Info (K 项)

...
```

**Token budget hard caps：**

- 至多 read 10 帧（per `summary_lint.json.citation_stats.claims_without_trace[]` 的 line snippet 抽样；优先 critical 候选）
- 不要 read 任何 v1.0 archive 来"对比风格"——你只校当前 slug
- 不要 read CLAUDE.md 来"确认 mode 规则"——你已经在这个 prompt 里有了 4 个 mode 的判别要点

**完成后**返回结构化结果：`{critical_count: N, warning_count: M, info_count: K, output_path: "<slug>-REVIEW.md"}`，让 caller 决定是否触发 CORR-03c rewrite cycle。
```

### CORR-03c：max-1 delta rewrite cycle

**触发条件**：CORR-03b verifier 返回 `critical_count > 0`。`warning` / `info` 永不触发 rewrite —— 直接 ship。

**流程**：

1. **备份**：`cp output/<slug>/summary.md output/<slug>/summary.md.pre-review`（atomic copy；如果该备份已存在 → overwrite，因为 max-1 cap 意味着该备份只代表"本次 invocation 的 pre-rewrite 状态"，跨 invocation 不保留多版本）。
2. **delta 重写**：Claude **不**全量重写 summary.md；只对 REVIEW.md `## Critical` 段列出的具体行/段做 targeted edit。Edit 用 `Edit` tool，每条 critical finding 对应一次 Edit call。
3. **重新 lint + verify**：
   a. 重跑 `python -m agent.tools summary_lint output/<slug>/summary.md`（更新 summary_lint.json）
   b. 重 spawn 一个 verifier subagent（同样的 prompt，同样的 scope lock）
4. **判定**：
   - 重 verifier 返回 `critical_count == 0` → **clean ship**：调用 `emit_rewrite_cycle_completed(slug_dir, critical_count_pre=N, critical_count_post=0, rewrite_path="summary.md.pre-review", duration_ms=...)`，正常进 Phase 8。
   - 重 verifier 返回 `critical_count > 0` → **UNRESOLVED**：调用 `agent.verifier_events.build_unresolved_md(slug, critical_findings)` 渲染模板，`Write` 到 `output/<slug>/<slug>-UNRESOLVED.md`；调用 `emit_rewrite_cycle_completed(slug_dir, critical_count_pre=N, critical_count_post=K, rewrite_path="summary.md.pre-review", duration_ms=..., unresolved_path="<slug>-UNRESOLVED.md")`；**ship summary.md as-is**（不回滚到 pre-review，因为 delta 修了一些 critical 至少不会更糟），exit cleanly。
5. **NO 2nd automatic rewrite cycle**（per .planning/research/SUMMARY.md "Self-Refine empirical max-1 cap" + REQUIREMENTS.md CORR-03c lock）。

**state.jsonl 事件**：rewrite cycle 完成后由 caller 调用 `agent.verifier_events.emit_rewrite_cycle_completed(...)`。事件类型名：`rewrite_cycle_completed`。Schema：

```json
{
  "stage": "rewrite_cycle",
  "status": "completed",
  "ts": "<ISO-8601 UTC>",
  "details": {
    "critical_count_pre": 3,
    "critical_count_post": 0,
    "rewrite_path": "summary.md.pre-review",
    "duration_ms": 12345,
    "unresolved_path": null
  }
}
```

注：`unresolved_path` 字段仅当 `critical_count_post > 0` 时存在；clean ship 时该字段省略（不写入 details dict）。

### UNRESOLVED.md 模板（`agent.verifier_events.build_unresolved_md` 渲染）

```markdown
# UNRESOLVED — <slug>

> 本文件由 Phase 7.5 verifier 在 max-1-rewrite 周期后仍存在 critical 问题时生成。
> Claude 已经做了一轮 delta 重写但无法消除以下 critical findings —— 需要人工介入。
> 备份：原始未修订版本保存在 `output/<slug>/summary.md.pre-review`。

## 人工介入清单

- [ ] **1. summary.md L42** (规则违反：`trace_after_claim`)
  - 证据：`fps=0.3 抽帧（缺少 [seg_*.jpg @ HH:MM:SS] token）`
  - 建议修复方向：

- [ ] **2. summary.md §三、消化阶段** (规则违反：`citation_timestamp_invalid`)
  - 证据：`[para_0042 @ 00:23:15] 不存在于 paragraphs.json`
  - 建议修复方向：

---

*生成时间：YYYY-MM-DDTHH:MM:SSZ*
```

### Token budget 校验（P-09，end-to-end manual gate）

**本 phase 的 SC#4** 断言："End-to-end `/summarize-video` on a marked slug (with all v1.1 features active) produces `.token_budget.json` showing total token spend ≤ 2x the Phase 07 measured baseline for the same mode."

这是**人工 gate**：

1. 选 1 条短 (~5 min) 测试视频，开 marker 启用全部 15 个 v1.1 features
2. 跑 `/summarize-video <url>`，让它跑完整 8 + 7.5 phases
3. 检查 `output/<slug>/.token_budget.json`，比对 Phase 07 baseline `.token_budget.json` 的 same mode（replicate-guide / interview-distillation / extension-applications）
4. 总 token 必须 ≤ 2x baseline；超出则人工调查（多半是 verifier subagent 失控读了过多 frame）
5. 失败时缓解：set `VIDEOSUMMARY_SKIP_REVIEWER=1`（降级关闭 Phase 7.5）跑 v1.1 minus verifier baseline，确认 Phase 7.5 是 token blow-up 的根因

**本 plan 的 orchestrator 不跑这个 gate**（需要真实 Claude session 跑 `/summarize-video`，不是 unit test 能模拟的）。该 gate 在 09-02-SUMMARY.md 的 "Known Stubs" 段标记为 `human_needed`，由用户/未来 milestone 实测验证。

### Phase 09 新增 state.jsonl event types 总览

| event 名 | 触发位置 | 写入者 | 关键 details |
|---|---|---|---|
| `summary_lint_run` | `cmd_summary_lint` | `agent/tools.py` (Plan 09-01) | claims_total, claims_with_trace, format_violations_count, citation_eligibility_violations_count, glossary_inconsistencies_count, lint_path |
| `verifier_run` | Phase 7.5 verifier subagent 完成后 | `agent/verifier_events.emit_verifier_run` (Plan 09-02) | severity_counts {critical/warning/info}, output_path, duration_ms |
| `rewrite_cycle_completed` | CORR-03c rewrite cycle 完成（无论 clean ship 还是 UNRESOLVED） | `agent/verifier_events.emit_rewrite_cycle_completed` (Plan 09-02) | critical_count_pre, critical_count_post, rewrite_path, duration_ms, unresolved_path? |

### 多终端并行注意事项（Phase 6 lock 域延续）

Phase 7.5 verifier + rewrite cycle 全程在 `output/<slug>/.resume.lock` 已持有的窗口内执行（because Phase 7.5 跑在 `/summarize-video` 主流程里，而 transcribe / aggregate / extract_frames_batch 已经持锁）。所以 Phase 09 **不**新增锁域。`<slug>-REVIEW.md` / `<slug>-UNRESOLVED.md` / `summary.md.pre-review` 三个新文件的写都受 `.resume.lock` 保护。

---

## v1.2 知识库自然语言推荐入口

> 这一节是 v1.2 知识库 milestone 的查询入口契约。当用户提以下意图时，Claude FIRST ACTION 读 `output/.index.json` 给出推荐。**触发 phrase 锁定 + 推荐格式锁 + anti-hallucination 锁** 三层保证一致体验。

### 触发 phrase 锁

用户消息中**明确包含**以下任一 phrase（byte-equal literal）→ 走推荐入口：

- '推荐'
- '相关'
- '我之前看过'
- '学过'
- '找一下我'
- '哪些视频'
- '类似查询意图'

仅当用户的查询意图**清楚指向**「在已总结的视频里找一些跟 X 主题/概念相关的内容」时触发；如果用户在讨论代码 / 主动问别的问题且只是顺带说"推荐"，不要强行匹配（per K2: Claude is decider）。

### FIRST ACTION

接到推荐意图 → 立即调用 `Read output/.index.json`（不要先 grep / 不要先问澄清；先 Read）。

- **文件存在**：解析 JSON dict，每个 key 是 slug，value 是 per-slug 8 字段索引（`slug / title / duration_s / mode / topics[] / keywords[] / tldr_oneliner / chapters[]`）。
- **文件不存在**：回复用户："索引未生成，请先跑 `python -m agent.tools index rebuild`"——不要尝试编造或扫 output/ 重建索引（rebuild 是 user 决策的恢复动作）。

### 推荐回复格式锁

返回 top-N（默认 N=3）推荐，每条**严格 3 行**结构（mirror v1.1 5th format-spec invariant 字面规则）：

- **第 1 行**：`**<slug>**: <title> — 共享 <匹配信号: keyword/topic>`
- **第 2 行**：`> <tldr_oneliner>`（blockquote 包裹 1 行）
- **第 3 行（可选）**：1-3 个 chapter 入口形如 `[HH:MM:SS] <chapter title>`，逗号分隔

匹配信号选择：从 `.index.json` 中拿到匹配命中的字段（比如 query 命中了 `topics: ["LLM-Wiki"]` → 写"共享 LLM-Wiki topic"；命中 `keywords: ["Karpathy"]` → 写"共享 Karpathy keyword"）。一条推荐可以有多个匹配信号合并写。

### Byte-equal example

用户："推荐学习 LLM Wiki 范式相关的视频"

Claude（先 Read output/.index.json，然后）：

```text
根据知识库匹配到 top-3 相关视频：

**douyin_karpathy_llm_wiki**: Karpathy 又被吹爆，但这次可能真不是炒作 — 共享 LLM-Wiki / RAG topics
> 75 行 Python gist 实现「个人知识库 = LLM 编译知识」的范式
- [00:00:18] Karpathy: "Every query is rediscovering knowledge."
- [00:01:25] 新员工 vs 图书管理员的比方
- [00:03:42] LLM 终于补上 Memex 缺失的「维护者」角色
```

### Anti-hallucination FORBIDDEN list

- **FORBIDDEN** 推荐 `output/.index.json` 中**不存在**的 slug（编造 slug = 致命错误，违反 v1.1 5th format-spec invariant 同等严重度）
- **FORBIDDEN** 编造视频内容 — `tldr_oneliner` / `keywords` / `chapters` / `title` 必须 byte-equal 来自 `.index.json`，不允许"提炼"或"改写"再展示给用户
- **FORBIDDEN** 修改 `summary.md` / `meta.json` / `paragraphs.json` / `segs.json`（D-29 invariant — 4 个 v1.0/v1.1 ship 后字节冻结的 archive 文件）
- **FORBIDDEN** 在推荐回复中加 `<thinking>` reasoning 段（直接给推荐；用户要看结果不看推理过程；如果用户后续问"为什么是这 3 条"再展开）
- **FORBIDDEN** 一次返回多于 N=5 条推荐（信息过载；如果用户说"列全部" / "show me everything"才允许 N>5；默认 N=3）
- **FORBIDDEN** 跳过 FIRST ACTION (Read output/.index.json) 直接根据 CLAUDE.md 上下文里能想到的 slug 编推荐——必须 Read 一次 .index.json，因为它是唯一权威源

如果 `.index.json` 中找不到与查询意图匹配的任何 slug → 直接告诉用户「在已总结的 N 个视频里没找到与「<query>」直接相关的内容；最接近的是 <slug>（共享 <weak signal>），但跟你想找的可能不太对路」。**不要硬凑无关推荐**。

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

**1.4** **自动启用 v1.1 全部能力**（D-29 safe，新视频默认全开；老归档因 summary.md 已存在会自动 refuse）：
```bash
python -m agent.tools v11_enable output/BVxxx
```
输出 JSON 三种 status 之一：`enabled` (新视频，写了 marker) / `preserved` (用户已手动设过 marker) / `v10_archive` (summary.md 已存在，跳过保 D-29 byte-equal)。后两种都是 idempotent 安全调用。

### Phase 2: 理解内容

**2.1** Read `meta.json` — 标题、时长、UP主

**2.2** Read `paragraphs.json`（或 `segs.json`）— **完整通读字幕**。不要跳过。

**2.3** 基于字幕判断：
- 视频类型（编程教程 / PPT 讲座 / 操作演示）
- 哪些时间段信息密集、哪些可以跳过
- 决定分段抽帧策略（下一步用）

**2.4** 输出模式判断 + 写 plan.md（详见 § 视频类型变奏 → 模式分类）。从 4 模式（`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`）选 primary + optional secondary，落到 `output/<slug>/plan.md` 顶部 5 字段 YAML front-matter；模糊 fallback 到 `replicate-guide`；写到一半误判可以改 mode 字段 + `mode_switched_at` 标记。

**2.5** **v1.1 hook (opt-in)**：如果 `is_v11_enabled('output/<slug>', 'l2_l3_correction')` 返回 True 且 `output/<slug>/transcribe_lint_warnings.json` 存在 → 走 § v1.1 自适应教学文档增强 → **CORR-01b L2 上下文修复**，把采纳的 corrections 写到 plan.md 的"已自动修正的术语"段。详见 § v1.1 自适应教学文档增强 (Phase 08) → CORR-01b/c。L3 多模态兜底在 Phase 4 看帧时执行（CORR-01c）。

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

> **mode 提示**：`interview-distillation` 时帧用量极少（每章节 1-2 帧，详见 § 视频类型变奏 → Podcast / interview 模式骨架 → Step 2）；`replicate-guide` / `extension-applications` 中 UI demo 类视频按 4 子规则增强写作精度（pixel-text 不确定性 / tooltip 遮挡 / 光标不可见 / 4K --width override，详见 § 视频类型变奏 → UI 操作演示子规则）。其余 mode 按本 phase 主流程。

### Phase 5: 规划大纲

基于字幕 + 帧理解，决定章节结构：
- 按自然教学步骤切分
- 每节标题用动词短语
- **输出大纲给用户确认**（子 agent 执行时可跳过直接写）

> **mode 提示**：`concept-explanation` 大纲走"核心问题 → 反直觉答案 → 最小例证 → 应用边界"流；`interview-distillation` 走 chapters.json + speaker turns（详见 § 视频类型变奏 → Podcast / interview 模式骨架 → Step 1 chapters.json schema）；`extension-applications` 大纲是横向罗列（场景 1 / 场景 2 / 场景 3 + 边界对比）。其余 mode 按本 phase 主流程。

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

> **v1.1 hook (opt-in)**：如果 marker 启用了 `inline_trace_tokens` / `self_contained_header` / `cross_slug_glossary` 中任一 → 写正文时叠加对应规则。具体：
> - `inline_trace_tokens` → 每个 claim 句末加 `[seg_*.jpg @ HH:MM:SS]` 或 `[para_NNNN @ HH:MM:SS]` token（CORR-02 引用资格规则）
> - `self_contained_header` → 顶部按 TEACH-A2 写 "标题/UP/时长/链接 → 你需要知道 / 你不需要知道 → 正文" 结构 + TEACH-A1 首次术语 inline 注解
> - `cross_slug_glossary` → 每个新术语 inline 注解后立即调用 `python -m agent.tools glossary append --slug <slug> --term "..." --definition "..."`
>
> 三条规则的完整定义在 § v1.1 自适应教学文档增强 (Phase 08)。

### Phase 7: 完整代码 + 输出

- 文档末尾合并完整代码（分文件列出）
- Write 到 `output/BVxxx/summary.md`

> **v1.1 hook (opt-in)**：如果 marker 启用了 `tldr_speedrun` AND（视频时长 > 20 min OR plan.md `estimated_sections > 50`）→ 在 summary.md 顶部 header 之后、正文之前插入 `## 5 分钟速读版` 块。**写在 LAST**（写完正文 + glossary appends 后才生成，防 drift）。10-15 行 hard cap，零 citation 内容（用 `详见 §三、消化阶段` 章节锚点替代）。完整模板 + sync check 见 § v1.1 自适应教学文档增强 (Phase 08) → TEACH-B。

### Phase 7.5: 校对自动化（v1.1 校对自动化 — Phase 09）

> **v1.1 hook (opt-in, 三重 gate)**：满足以下**全部 3 条**才走 Phase 7.5 verifier subagent + rewrite cycle —— 任何一条不满足则 silently skip 直接进 Phase 8（v1.0 path）：
>
> 1. `is_v11_enabled('output/<slug>', 'verifier_phase_75')` 返回 True
> 2. 环境变量 `VIDEOSUMMARY_SKIP_REVIEWER != '1'`（降级开关；low-quota fallback）
> 3. `python -m agent.tools summary_lint output/<slug>/summary.md` 已跑过（`output/<slug>/summary_lint.json` 存在）—— 如果未跑则**先跑** summary_lint 再走 7.5
>
> **Phase 7.5 步骤**（按顺序）：
>
> 1. **Spawn verifier subagent**：执行 `Task(subagent_type='general-purpose', description='Phase 7.5 summary verifier', prompt=<§ v1.1 校对自动化 → CORR-03b → Verifier Prompt 段的逐字内容>)`。Subagent 输出 `output/<slug>/<slug>-REVIEW.md`。
> 2. **Emit verifier_run event**：`from agent.verifier_events import emit_verifier_run` → `emit_verifier_run(Path('output/<slug>'), severity_counts=<subagent 返回的 counts>, output_path='<slug>-REVIEW.md', duration_ms=<wall_ms>)`
> 3. **判定**：如果 subagent 返回 `critical_count == 0` → 直接进 Phase 8（warning/info 都只在 REVIEW.md 留档，不触发 rewrite）。
> 4. **如果 critical_count > 0**：走 CORR-03c max-1 rewrite cycle（详见 § v1.1 校对自动化 → CORR-03c）：
>    a. 备份 `cp output/<slug>/summary.md output/<slug>/summary.md.pre-review`
>    b. 用 `Edit` tool 对 REVIEW.md `## Critical` 段列出的每个 finding 做 targeted edit（**不**全量重写）
>    c. 重跑 `python -m agent.tools summary_lint output/<slug>/summary.md`
>    d. 重 spawn 一次 verifier subagent（同 prompt 同 scope lock）
>    e. 如果重 verifier 返回 `critical_count == 0` → emit `rewrite_cycle_completed` (clean ship)，进 Phase 8
>    f. 如果重 verifier 仍返回 `critical_count > 0` → 调用 `agent.verifier_events.build_unresolved_md(slug, critical_findings)`，`Write` 到 `output/<slug>/<slug>-UNRESOLVED.md`，emit `rewrite_cycle_completed` (with unresolved_path)，**ship summary.md as-is** 进 Phase 8。**绝不**做第 2 轮 rewrite。
>
> **NO 2nd automatic rewrite cycle** — max-1 是 hard cap（per .planning/research/SUMMARY.md "Self-Refine empirical max-1 cap" + REQUIREMENTS.md CORR-03c lock）。
>
> 完整规则 + verifier prompt 全文 + UNRESOLVED.md 模板见 § v1.1 校对自动化 (Phase 09)。

### Phase 7.6: 知识库索引（v1.2 ship 后默认启用）

> **v1.2 hook (默认)**：满足以下**全部 3 条**才走 Phase 7.6（Claude is decider）：
> 1. `output/_topics.md` 存在（v1.2 Phase 10 ship 后默认存在）
> 2. `output/<slug>/summary.md` 已写完（Phase 7 完成 + Phase 7.5 verifier 已通过）
> 3. `output/<slug>/index.json` 不存在 OR 用户显式要求重新生成

**Phase 7.6 步骤**（按顺序）：

1. **Read 5 个文件**：`output/<slug>/summary.md` / `output/<slug>/meta.json` / `output/<slug>/plan.md` / `output/_glossary.md` / `output/_topics.md`。**这 5 个文件全部 READ-ONLY**——D-29 invariant 锁死 4 核心文件（summary.md / segs.json / paragraphs.json / meta.json）byte-equal 不破；不要用 Edit / Write 工具改动它们，哪怕你读时发现 typo 也不改（K5 边界 + Plan 11-01 K5 source-grep 测试覆盖 CLI 侧；本节是 prompt 侧的对应锁）。
   - **`plan.md` 缺失情况**（17 v1.0/v1.1 archives 没有 plan.md — verified via `ls output/<slug>/`）→ `mode = "replicate-guide"` per CLAUDE.md `### 模式分类 (Phase 2 末尾步骤) → Fallback 规则`
   - **`_glossary.md` 缺失情况**（v1.1 TEACH-A3 cross_slug_glossary 是 opt-in；当前 branch + 17 archives + 16 douyin/BV 全部没有）→ `keywords` 候选集为空，由 Claude 直接从 `summary.md` 自由提议（`agent.index.glossary_h2_anchors` 在文件缺失时 silently 返回 `[]`，不抛异常）

2. **推断 8 字段** (`slug` / `title` / `duration_s` / `mode` / `topics[]` / `keywords[]` / `tldr_oneliner` / `chapters[]`)：
   - `slug` = 目录名（与 `--slug <slug>` arg 一致）
   - `title` = `meta.json["title"]`
   - `duration_s` = `meta.json["duration"]`（浮点秒；可能是 int 或 float — schema validator 都接受）
   - `mode` = `plan.md` front-matter 的 `mode` 字段；缺失时 fallback `"replicate-guide"`（4 modes 之一：`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`）
   - `topics[]` **必须从 `output/_topics.md` 的 `## Approved Taxonomy` 段选取**（白名单约束）。当前 ground truth 24 nodes / 5 categories（Phase 10 plan-02 ship）。**新概念**（不在 Approved 白名单内）→ 用 `"pending: <new-name>"` 字面形态（前缀 6 字节 `pending: ` 后跟新 topic 名）。CLI 收到后自动 append 到 `## Pending` 段（调用 `agent.topics.append_pending`）；普通 string topic 不在 Approved 集合 AND 没有 `pending: ` 前缀 → CLI fail-fast。
   - `keywords[]` **优先复用 `output/_glossary.md` H2 anchors 的 byte-equal canonical 形式**（如 `LoRA (Low-Rank Adaptation)` 是 canonical；不要写 `LoRA` / `Lora` / `low-rank adaptation` 散落形态）。`agent.index.glossary_h2_anchors(Path("output/_glossary.md"))` 给你 candidate set；先看 summary 里命中的 H2 anchor，命中即用 canonical 形态。新概念才创造新 keyword，不强制 append 回 `_glossary.md`（`_glossary.md` 由 v1.1 TEACH-A3 维护，写时机不同）。
   - `tldr_oneliner` = 1 行视频核心，10-50 字。每 mode 自然形态参考（仅 prior，不是 template）：
     - `replicate-guide`: "用 X 做 Y 的 N 步流程"
     - `concept-explanation`: "X 不是 Y，而是 Z"
     - `extension-applications`: "X 在 N 个场景里的应用对比"
     - `interview-distillation`: "嘉宾的核心判断 + 反共识立场"
   - `chapters[]` = `[{title, start, excerpt}, ...]`，**每项无独立 keywords 字段** per D-02。
     - `chapters[i].title` = summary.md 里对应 H2 章节的标题文字（去掉 `[HH:MM]` timestamp 前缀如有）
     - **`chapters[i].start` = 浮点秒**（与 segs.json / paragraphs.json 一致单位）。**关键：cross-reference `paragraphs.json` 拿真实浮点 start**——summary.md 的 `[HH:MM]` 是秒级 round（精度损失），`paragraphs.json` 的 `paragraphs[i].start` 是浮点。不同 mode 的章节 H2 约定不一致（`interview-distillation` 多用 `## [HH:MM] topic`，`replicate-guide` 多用 `## 一、Chinese-numeral`，`extension-applications` 混合）—**不要单纯 regex `summary.md`**，而是把每个 H2 章节标题语义匹配到 paragraphs.json 中最接近的 paragraph，用其 `start` 浮点值。
     - `chapters[i].excerpt` = 1-2 行（≤ 200 字）章节核心摘要；从该章节正文提炼，不要 verbatim 抄第一段

3. **Pipe JSON 给 CLI**：
   ```bash
   python -m agent.tools index write --slug <slug> --from-stdin <<EOF
   {"slug": "<slug>", "title": "...", "duration_s": ..., "mode": "...",
    "topics": [...], "keywords": [...], "tldr_oneliner": "...",
    "chapters": [{"title": "...", "start": ..., "excerpt": "..."}, ...]}
   EOF
   ```
   JSON 结构 = per-slug index.json 8 字段 verbatim（不需要 wrapping object）；CLI 会自动在 stdin 缺 `slug` 字段时从 `--slug` arg 注入；`slug` 字段值 mismatch `--slug` arg → CLI fail-fast。

4. **CLI 自动**：
   - 验证 8 字段 schema (`agent.index.validate_per_slug_index`) — 缺字段 / 类型错 / mode 不在 4 之内 / topic 不在白名单且非 `pending: ` 前缀 → `IndexValidationError` + stderr 详细错误 + exit 1
   - 持锁 `output/.index.lock`（Phase 11 D-09.1，第 4 个跨 slug 锁域）
   - atomic 写 `output/<slug>/index.json`（tempfile + os.fsync + os.replace）
   - 立刻 rebuild 顶层 `output/.index.json`（atomic write — sorted lexicographic by slug；扁平 dict `{"<slug>": <per-slug>, ...}`，无 backlinks per D-07）
   - 输出 stdout JSON: `{"action": "written" | "skipped", "slug": "...", "_index_path": "...", "_aggregator_path": "...", "_topics_pending_appended": [<names>, ...]}`
   - Idempotent: 已存在 `output/<slug>/index.json` AND stdin JSON byte-equal → no-op + `action: "skipped"`；任何字段不一致 → 覆盖（视为新版本）

5. **错误处理**：
   - schema 校验失败 → CLI exit 1 + stderr 详细错误（field name 显式）；Claude 修正 JSON 重试
   - topic 不在白名单 AND 非 `pending: <name>` 形态 → 同上 fail-fast；Claude 改写为 `pending: <name>` 后重试（CLI 会 append 到 `_topics.md` Pending 段）
   - lock contended（其他终端正在写 `output/.index.json`）→ exit 1 + stderr `lock contended`；Claude 等待 / 重试 / 检查孤儿 PID
   - slug dir 不存在 → exit 1 + stderr `slug dir not found`；Claude 检查 `--slug` arg 是否拼对、`--output-dir` 是否对

> **K5 边界提醒**：Phase 7.6 hook 的 5 个被 Read 的文件中，4 个核心文件（summary.md / segs.json [虽不在本 hook Read 列表但仍受保护] / paragraphs.json / meta.json）+ plan.md 永远 **READ-ONLY**。Plan 11-01 的 K5 source-grep 测试已经禁止 `agent/index.py` + `cmd_index_write` + `cmd_index_rebuild` 包含这 5 文件 literal；本 hook 是对应的 prompt-level invariant。Phase 11 close 前会跑 `python scripts/replay_v10_archives.py` 双重 verify 4 核心文件 byte-equal 不破（D-07.1 close gate）。

### Phase 8: 收尾

- 质量自检（时间戳真实？代码从截图抄？图片对应步骤？无废话？）
- 可选：`python -m agent.tools cleanup_frames <dir> --keep <用到的帧>` 清理未引用的帧

> **v1.1 hook (opt-in)**：如果 marker 启用了 `self_check_confidence` → 跑 CORR-02 自检 pass：重读全文，对每个带 token 的 claim 句自评 confidence，< 80% 在句末加 `[?]`，并在 summary.md 末尾追加 `## 写作自检 (CORR-02)` footer 段（总 claim 数 / `[?]` 数 / 比例 + 低置信度行号列表）。完整规则见 § v1.1 自适应教学文档增强 (Phase 08) → CORR-02 → 自检 pass。
>
> 如果 marker 启用了 `cross_slug_glossary` → 收尾时建议跑一次 `python -m agent.tools glossary audit --json` 检查 `output/_glossary.md` 是否有 `duplicate_terms` / `conflicting_definitions` 需要 Claude 决策（first-seen-wins 是默认 schema，audit 只报告不修改 — K5）。

---

## 质量红线

- **时间戳只用字幕里真实存在的**
- **代码从帧截图精确抄录** — 不确定就 Read 图片再看
- **图片紧跟操作步骤** — 没帧不硬插
- **不注水不编造**
- **完整代码可运行**
