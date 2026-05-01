# Phase 3: Source Refactor + New Sources (YouTube + Local mp4 + Generic) - Context

**Gathered:** 2026-05-01
**Status:** Ready for planning
**Decision authority:** Claude 自决（user requested 尽可能不干预模式 — `gsd-discuss-phase --auto` 自动选择 recommended）

<domain>
## Phase Boundary

把 `agent/tools.py:cmd_download` 那段 `if "douyin.com" in url else yt-dlp` 的硬编码替换成 `agent/sources/` 注册表，并新增 3 条 ingest 路径（YouTube + 通用 yt-dlp + 本地 mp4 文件）。**本地 mp4 是 YouTube 的优雅 fallback** —— 国内 GFW + SABR + PO Token 链路任意一环失败时，用户能立刻退回"自己下好放本地"的兜底路径。

不变的承诺：B 站 / 抖音的现有 `cmd_download` 调用方式 byte-identical 不变（Phase 1 的 3 条回归基准必须仍 pass eyeball diff），17 archive 老归档目录布局不动。

</domain>

<decisions>
## Implementation Decisions

### Source Protocol & 注册表（SRC-01, SRC-02）
- **D-01:** `agent/sources/` 包下一文件一平台：`bilibili.py / douyin.py / youtube.py / generic.py / local.py`。每个文件 export 一个实现 `Source` Protocol 的类：`match(url_or_path: str) -> bool` 判定是否处理；`fetch(target_dir: Path, *, skip_if_cached: bool = True) -> dict` 执行下载/拷贝并返回 meta dict。Protocol 定义在 `agent/sources/__init__.py`。
- **D-02:** 注册表 = `agent/sources/__init__.py` 顶层 `SOURCES: list[Source]`，**most-specific-first 顺序**：`[DouyinSource(), YouTubeSource(), BilibiliSource(), LocalSource(), GenericSource()]`。`agent/url_router.py:route(url_or_path)` 纯函数，遍历 SOURCES 返回第一个 `match()` 为真的实例；找不到 raise `RuntimeError(f"No source matched: {url_or_path!r}")`。
- **D-03:** GenericSource 是 catch-all yt-dlp fallback，永远最后；其 `match()` 总是返回 True，作为 sentinel。
- **D-04:** 现有 `agent/douyin_downloader.py` 和 `src/download.py` **保持原样不删**（PROJECT.md OOS "Rewrite or delete existing modules" 禁止）；新 source 类是它们的薄封装，内部委托调用。重构 = 添加新文件 + 改 dispatch；不重写 legacy。

### `ingest` CLI 与 `download` shim（SRC-03）
- **D-05:** 新增 `python -m agent.tools ingest <url-or-path> --out <dir>` 子命令，调用 `url_router.route()`。argparse 配置与现 `download` 子命令一致（positional URL/path + `--out`）。
- **D-06:** 现有 `download` 子命令变成薄 shim：`cmd_download(args)` 内部直接转 `cmd_ingest(args)`。**观察行为完全等价**——B 站和抖音 URL 跑出来 `meta.json` / `video.mp4` byte-identical（用 Phase 1 baseline `tests/regression/{BV132wizyEEB,BV1C9QCBdE1U,douyin_trae_ai}/` 验证）。
- **D-07:** `ingest` 是 canonical name；`download` 永久保留（K3 backward-compat 硬约束 + CLAUDE.md 文档化的 5 个核心命令之一）。CLAUDE.md 在适当位置加一条说明："`download` 现在是 `ingest` 的别名，行为相同"。

### `meta.json` source 字段（SRC-04, SRC-08）
- **D-08:** `meta.json` 增加可选字段（additive，不 bump schema_version 当 Phase 1 D-04 / D-05 先例）：
  - `source: "bilibili" | "douyin" | "youtube" | "generic" | "local"`
  - `youtube_id`（仅 YouTube；B站继续用 BVID 作 slug + url 字段）
  - `subtitle_origin: "creator" | "auto" | "asr" | "none"`（per SRC-08）
  - 抖音 `aweme_id` 字段保留现状（已是现状）
- **D-09:** Loader (`agent/io.py:load_meta`) 看到老归档 meta.json 缺 `source` 字段时**不自动填充**——保持 K3 "Phase 2 后写新 sidecar，老归档不动"原则。doctor 子命令显示 `source: —`。
- **D-10:** `subtitle_origin` 由 source 决定：yt-dlp 拿到 creator subtitles → `"creator"`；只能拿 auto-gen → `"auto"`；下游 `cmd_transcribe` 跑 ASR → loader 在 transcribe 完成后写回 `"asr"`；都没有 → `"none"`。本 phase 只负责 yt-dlp 那两类的写入；ASR 路径留 Phase 5 TEACH-08 整合。

### YouTube 失败分类与 proxy（SRC-05, SRC-06, SRC-07, SRC-13）
- **D-11:** YouTubeSource.fetch() 第一步是 **2 秒 `yt-dlp --simulate --proxy $HTTPS_PROXY <url>` preflight**。失败时按 stderr 内容做 5 类分类：
  - `gfw_blocked`：网络不通 / DNS 失败 / `Unable to download webpage` / connection timeout
  - `cookies_stale`：`Sign in to confirm` / `Login required` / 403 with cookie context
  - `po_token_required`：`SABR` / `PO Token` / `requires PO Token`（YouTube 2026 SABR rollout）
  - `yt_dlp_outdated`：`extractor signature error` / 已知格式 hash 失败
  - `other`：catch-all
- **D-12:** 每类有 LOCKED 中文 hint 字符串（见 D-21 RESEARCH 起草表，planner 可微调）：
  - `gfw_blocked` → "GFW 阻断；export HTTPS_PROXY=http://127.0.0.1:7890 后重试，或下载到本地后用 `ingest <local-path>`"
  - `cookies_stale` → "Cookies 失效；浏览器登录 YouTube 后重新导出 cookies.txt"
  - `po_token_required` → "PO Token required；安装 Deno + `pip install yt-dlp-get-pot`，详见 CLAUDE.md"
  - `yt_dlp_outdated` → "yt-dlp 版本过旧；`pip install -U yt-dlp` 后重试"
  - `other` → 直接附 stderr 头 200 字符
- **D-13:** Preflight 失败 raise `RuntimeError(f"YouTube ingest failed [{category}]: {hint}")`。caller 可 catch 决定 retry / fall back；本 phase **不**做 auto-fallback 到 local mp4，避免"silent decision"违反 K5（Claude is decider）。

- **D-14:** `HTTPS_PROXY` / `HTTP_PROXY` env vars（uppercase Windows 约定）从 `os.environ` 读取，转 `--proxy` 传给 yt-dlp。优先级：`HTTPS_PROXY` > `HTTP_PROXY` > 无 proxy。
- **D-15:** 启动时 log `yt_dlp.__version__`；如果版本 < 当前日期 90 天前，log warning：`"yt-dlp version %s is %d days old; pip install -U yt-dlp recommended"`。**不**自动升级。
- **D-16:** `requirements.txt` pin `yt-dlp>=2026.03.17`（per SRC-13）。Deno + `yt-dlp-get-pot` 不进默认 requirements，仅在 CLAUDE.md "首次设置" 节文档化为 opt-in：`winget install DenoLand.Deno && pip install yt-dlp-get-pot`。

### 本地 mp4 路径（SRC-09, SRC-10, SRC-12）
- **D-17:** LocalSource.match() 判定：路径含 `://` 或 url 协议头 → False；其余情况 `Path(input).suffix.lower() in {".mp4", ".mkv", ".webm", ".flv", ".mov"}` AND `Path(input).is_file()` → True。
- **D-18:** **Slug 强制 ASCII-safe**（per PITFALLS P4.1，避免 ffmpeg subprocess GBK/UTF-8 corruption）：
  ```
  slug = f"local_{sha256(absolute_path)[:8]}_{ascii_stem(stem)}"
  # ascii_stem: 从 Path(input).stem 取前 8 个 [a-zA-Z0-9] 字符；
  # 没有任何 ASCII alnum → "unnamed"
  ```
  示例：`D:\videos\编程教程_我的录屏.mp4` → `local_a3f2b1c4_unnamed`；`D:\videos\demo2024_final.mp4` → `local_d8e1f9a0_demo2024`。
- **D-19:** **Reject `--out <path>` containing CJK** per PITFALLS P4.1：在 cmd_ingest 入口 `re.search(r"[一-鿿]", str(args.out))` 命中 → raise `ValueError("CJK characters in --out path break ffmpeg subprocess on Windows zh-CN; use ASCII-only path under output/")`。**只检查 --out**，不检查输入文件路径（输入路径只用作 metadata + 拷贝源，ffmpeg 在 stage 内只看 output/<slug>/video.mp4）。
- **D-20:** LocalSource.fetch() **拷贝（不 symlink）** 输入 mp4 到 `output/<slug>/video.mp4`。理由：Windows symlink 需要 admin；copy 只在第一次 ingest 慢一次（30-500MB），后续走 Phase 2 sidecar idempotent cache。

### ffprobe preflight & VFR 处理（SRC-11, SRC-12）
- **D-21:** **每个 source 的 fetch() 完成后**（拿到 video.mp4 后），统一跑：
  ```bash
  ffprobe -v error -print_format json -show_format -show_streams <video>
  ```
  解析：
  - 视频流 codec（h264 / hevc / av1 / vp9 等）→ 写 `meta.json:codec`
  - 音频流是否存在 → 不存在则 raise `RuntimeError("No audio stream in <path>; whisper cannot transcribe. Remux with `ffmpeg -i in -c:v copy -c:a aac out.mp4`")`
  - 容器格式 → `meta.json:container`
  - VFR 检测：`r_frame_rate != avg_frame_rate`（fraction 严格不等）→ `meta.json:fps_mode = "VFR"`，否则 `"CFR"`
- **D-22:** HEVC / AV1 → **log warning 不阻塞**："Codec %s detected; if extract_frames runs slow, remux to h264 first: `ffmpeg -i in -c:v libx264 -c:a copy out.mp4`"。Whisper 走音频流，不依赖视频 codec；只是抽帧速度受影响。
- **D-23:** **`-vsync vfr` 统一应用**（per SRC-12）：现有 `agent/tools.py:cmd_extract_frames` 的 ffmpeg 调用增加 `-vsync vfr` 参数；Phase 4 的 `extract_frames_batch` 同样应用。**所有 source 受益**——B 站/抖音视频里 OBS/iPhone 录制的 VFR 内容也不再丢帧（之前是隐性 bug）。

### Plans 拆分（与 ROADMAP 一致，3 plans）
- **D-24:** 03-01: `agent/sources/` 包 + `url_router.py` + `ingest` 子命令 + `download` shim + `meta.json` source/youtube_id/aweme_id 字段（SRC-01, 02, 03, 04）。包含 BilibiliSource / DouyinSource 重构（薄封装现有 `src.download` / `agent.douyin_downloader`），写 GenericSource sentinel。**先做这个**——后两 plan 都要在它的注册表里加新 source。
- **D-25:** 03-02: YouTubeSource 全套（SRC-05, 06, 07, 08, 13）—— preflight 分类器 + proxy 转发 + 版本警告 + subtitle_origin + yt-dlp pin + Deno 文档。**最重的 plan**（GFW 分类 + 5 类 stderr regex）。
- **D-26:** 03-03: LocalSource + ffprobe preflight 统一 + `-vsync vfr` 统一（SRC-09, 10, 11, 12）。**最小 plan**；ffprobe 和 vsync 改动追溯惠及 B 站/抖音老路径。

### Claude's Discretion（planner / executor 自决）
- ffprobe 命令的具体超时（建议 5s，但 planner 可调）
- 5 类 YouTube 失败的 stderr regex 精确写法（CONTEXT 给中文 hint 措辞，正则由 planner 在 RESEARCH 阶段定）
- meta.json 是否在 fetch() 写入还是统一 cmd_ingest 末尾写（建议后者，统一 atomic-write 入口）
- BilibiliSource.match() 的 url 模式（建议 `bilibili.com` / `b23.tv` 都识别）
- 是否提供 `--no-preflight` 跳过 ffprobe（YAGNI；如果有人需要再加）

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 项目级约束
- `.planning/PROJECT.md` — Constraints §"Backward compatibility"（K3 硬约束）+ K Decisions（不重写 legacy）+ §"Stack inertia"（yt-dlp / vendor 优先扩展不替换）
- `.planning/REQUIREMENTS.md` §"SRC — Source Refactor + New Sources" — SRC-01..SRC-13 全文 + Out of Scope（不做 Niconico / Vimeo / Twitter，SRC-V2-02 已记录）
- `.planning/ROADMAP.md` §"Phase 3" — 5 条 Success Criteria + 3-plan 拆分（D-24/D-25/D-26 严格对齐）

### Phase 1+2 已锁定决策（必读，决定本 phase 不踩雷区）
- `.planning/phases/01-preflight-regression-baseline/01-CONTEXT.md` — D-04（顶层 list 工件不可 wrap）、D-12（archive 子目录约定不变）、D-07..09（Claude eyeball diff 是验证方法）
- `.planning/phases/02-resume-infrastructure-cache-correctness/02-CONTEXT.md` — D-08（sidecar 同目录 sibling）、D-09/10（atomic-write 落 agent/io.py）、D-12（state.jsonl 格式）。**本 phase 新 source 写产物时必须复用 02-01 的 `write_json_atomic` + sidecar 机制**；不要绕开

### 代码地图
- `.planning/codebase/ARCHITECTURE.md` §"Layers" / §"Vendor Layer" — 双层结构 + vendor/douyin_api 边界
- `.planning/codebase/CONVENTIONS.md` §"CLI Pattern" — argparse subparser + cmds dict + cmd_<name> 命名（cmd_ingest 沿用）；§"Error Handling" — `RuntimeError` 中文消息惯例
- `.planning/codebase/STRUCTURE.md` §"Where to Add New Code" - "A new download source" 章节直接对应本 phase
- `.planning/codebase/CONCERNS.md` §1.3（"两条下载路径 schema 不同"，本 phase 直接消除）、§2.4（_extract_aweme_id brittle，新 source 重构不再依赖它）

### 风险与陷阱（直接对应本 phase）
- `.planning/research/PITFALLS.md` §P3.1 「YouTube GFW + SABR + PO Token + Cookies multiplicative failure」— D-11..D-13 5 类分类器的依据，severity = showstopper
- `.planning/research/PITFALLS.md` §P3.2 / P3.3 / P3.4 — yt-dlp 版本漂移、subtitle_origin 必要、generic metadata 需求
- `.planning/research/PITFALLS.md` §P4.1 「Chinese filenames in subprocess on Windows zh-CN」— D-18/D-19 ASCII-safe slug 的依据，severity = showstopper for local
- `.planning/research/PITFALLS.md` §P4.2 / P4.3 — ffprobe preflight + `-vsync vfr` uniform 的依据
- `.planning/research/SUMMARY.md` §"Phase 3" — 高层叙述与本 CONTEXT.md 对齐参考

### 现有代码（必读，决定如何"薄封装"）
- `agent/tools.py:cmd_download (line 35-59)` — 现有 substring 分支；本 phase 替换为 url_router 调用
- `agent/douyin_downloader.py:download_douyin` — DouyinSource 薄封装目标
- `src/download.py:download` — BilibiliSource / GenericSource 共享底层（yt-dlp）
- `agent/io.py` (Phase 2 后扩展) — `write_json_atomic` / `write_sidecar` —— 新 source 写 meta.json 必须走这个

### 待修改 / 新增文件
- `agent/sources/__init__.py` — **新**，Protocol + SOURCES list
- `agent/sources/{bilibili,douyin,youtube,generic,local}.py` — **5 个新文件**
- `agent/url_router.py` — **新**，纯函数 route()
- `agent/tools.py` — `cmd_ingest` 新增；`cmd_download` 改 shim；argparse + cmds dict 注册
- `requirements.txt` — pin `yt-dlp>=2026.03.17`
- `CLAUDE.md` — Deno + yt-dlp-get-pot opt-in 说明 + `download → ingest` 别名说明 + ASCII-safe `--out` 路径要求

### 不修改的文件
- `agent/douyin_downloader.py` 内部逻辑（薄封装它，不重写）
- `src/download.py` 内部逻辑（同上）
- `vendor/`、`output/` 下所有归档目录、`tests/regression/` 快照
- 任何 `src/pipeline.py` legacy v1 cloud 路径

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`agent/io.py:write_json_atomic`** (Phase 2-01) —— 5 个新 source 写 meta.json 必须经此入口，自动获得原子写 + sidecar
- **`agent/io.py:_get_ffmpeg_version` / `_get_faster_whisper_version`** —— ffprobe 的版本探测可以加一个并列的 `_get_ffprobe_version()` 复用 lru_cache 模式
- **`agent/state.py:append_event`** (Phase 2-02) —— 新 source 应该在 fetch() 完成后 emit `download` 阶段的 `started`/`completed`/`failed` 事件（已 wired 进 cmd_download，url_router 改完后自动延续）
- **`subprocess.run(["ffmpeg", ...], check=True, capture_output=True)`** idiom (现有 `agent/tools.py:120` / `src/asr.py:48`) —— ffprobe 用同形态调用
- **`agent/tools.py:cmd_doctor`** (Phase 2-03) —— 新 source 写的产物自动出现在 doctor 输出里（artifact 列表已含 meta.json）
- **`agent/tools.py:75-81` `--force` flag pattern** —— ingest 子命令同样支持 `--force` 跳过 cache（与 transcribe 一致）

### Established Patterns
- **CLI 子命令注册**：argparse subparser + `cmds = {...}` dict —— `cmd_ingest` 添加到现有 dict
- **延迟导入**：`agent/tools.py:37` `sys.path.insert(0, ...)` 后再 `import` legacy 模块 —— 5 个 source 类的 lazy import 沿用此模式
- **抛异常 fail-loud**：`raise RuntimeError(f"...{path}")` 中文消息（CONVENTIONS §"Error Handling"）—— 5 类 YouTube 错误 + ffprobe 错误用此 idiom
- **encoding="utf-8"** + **`json.dumps(..., ensure_ascii=False, indent=2)`** —— 新 meta.json 写入必须保持
- **`pathlib.Path` 全程**，`os.path` 不出现

### Integration Points
- **`agent/tools.py` cmds dict** (line 241-251) — `"ingest": cmd_ingest` 在 `"download"` 之后插入；`"download"` 保留指向 `cmd_download`（shim）
- **`agent/tools.py` argparse subparsers** (line 197-234) — 新增 `ingest` parser，参数与 `download` 一致
- **`requirements.txt`** — line ~2 `yt-dlp>=2024.10.0` 改为 `yt-dlp>=2026.03.17`
- **`CLAUDE.md`** — 在 "环境变量（.env）" 节后或 "首次设置" 节末尾加一段 "首次设置 YouTube ingest（可选）"，文档化 Deno + yt-dlp-get-pot
- **`.gitignore`** — `output/` 已 gitignored；新 sources 写产物不需要改

### 不能动的现有约定
- 17 archive 目录布局（`output/<slug>/{meta.json,video.mp4,audio.wav,segs.json,paragraphs.json,frames/,summary.md}`）—— 老归档不动
- 帧文件名 `seg_<start>_<index>.jpg` —— 不在本 phase 改动范围（Phase 4 territory）
- `cmd_download` argparse 接口 —— shim 后行为完全等价

</code_context>

<specifics>
## Specific Ideas

- **本地 mp4 是 YouTube 的 graceful fallback**：5 类失败任一发生时，hint 字符串第一句都告诉用户"下载到本地后用 `ingest <local-path>`"。这条 mental model 在 RESEARCH 和 plan-checker 必须保持一致。
- **"复用现有，不重写"**：DouyinSource 是 `agent.douyin_downloader.download_douyin` 的 30-line wrapper；BilibiliSource 是 `src.download.download` 的 30-line wrapper（保留它现有 yt-dlp 调用）。**不动 vendor/、不动 src/download.py、不动 agent/douyin_downloader.py 内部**。
- **ffprobe 是 Phase 3 的隐藏价值**：抓 audio-stream 缺失（Whisper 跑不动的 root cause）+ codec warning + VFR 检测；本来可以等到 Phase 4 抽帧时才做，但放在 ingest 阶段意味着"下载完立刻知道这视频能不能用"，节省错误 path 的 token。
- **`-vsync vfr` 是 retroactive fix**：现有 cmd_extract_frames 也加上，B 站/抖音老视频如果是 VFR 录屏（OBS / iPhone），未来 re-run 抽帧时不再丢帧。Phase 1 baseline 用这条命令重抽不会改变现有 archive（已抽好的 frames/ 目录不动）。
- **YouTube 国内首跑大概率失败**：5 类分类器的存在 = 用户第一次跑 `ingest <youtube-url>` 大概率得到一条明确的中文 hint，照着配 proxy / cookies / Deno 即可。比"莫名其妙连不上"友好 10 倍。

</specifics>

<deferred>
## Deferred Ideas

- **Niconico / Vimeo / Twitter (X) extractor 特殊适配**（REQUIREMENTS.md SRC-V2-02）—— 本 phase 不做；GenericSource yt-dlp catch-all 已能 functional 处理
- **Auto-fallback：YouTube preflight 失败自动切 LocalSource**（违反 K5 Claude is decider）—— 本 phase 只 raise 分类后的错误，由 caller 决定下一步
- **`--no-preflight` flag 跳过 ffprobe**（YAGNI）—— 默认 always-on；真有用户痛点再加
- **Niconico 等小众平台的 cookies 管理**（贴现有 douyin / bilibili cookies idiom）—— SRC-V2 territory
- **Symlink 模式 LocalSource**（Windows 需 admin）—— 不做；copy 兼容性更好
- **HTTP_PROXY / HTTPS_PROXY 自动检测从 Windows registry**（注册表读 IE proxy 设置）—— 不做；env var 是标准约定
- **PO Token 自动获取 / 缓存**（yt-dlp-get-pot 的活）—— 用户自己安装 Deno + 这个包；本 phase 只在 hint 字符串里指路

</deferred>

---

*Phase: 03-source-refactor-new-sources-youtube-local-mp4-generic*
*Context gathered: 2026-05-01*
*Mode: auto (gsd-discuss-phase --auto, all grey areas auto-resolved with recommended answers)*
