# Phase 3: Source Refactor + New Sources - Discussion Log

> **Audit trail only.** Decisions are captured in CONTEXT.md.

**Date:** 2026-05-01
**Phase:** 03-source-refactor-new-sources-youtube-local-mp4-generic
**Mode:** `gsd-discuss-phase --auto`（user-requested 尽可能不干预）

## User decision delegation

User said: "按 B 继续推，不过流程尽可能不需要我干预" — 所有灰色决策由 Claude 自决，仅在 (a) Phase 3 YouTube 环境失败 (gfw_blocked / cookies_stale / po_token_required) 和 (b) Phase 6 PARA ship-or-skip 节点时停下询问。

## Auto-resolved grey areas

Per `discuss-phase --auto` mode：所有 grey area 选 recommended option，逐条记入 CONTEXT.md `<decisions>` D-01..D-26。Claude 对每条做 trade-off 评估，选 recommended：

| Grey area | Recommended（locked in CONTEXT D-XX） | 备选（discarded） | 选择理由 |
|---|---|---|---|
| Source Protocol shape | `match()` + `fetch()` 两方法 | 单 `handle()` 方法 + branching | 双方法分离 dispatch / execute，url_router 测试更纯 |
| 注册表存放 | `agent/sources/__init__.py: SOURCES list` | 装饰器 `@register_source` | List 显式有序（most-specific-first），装饰器 hide order |
| Generic source 位置 | 列表末尾 sentinel `match() → True` | 单独 `default_handler` 字段 | sentinel 与 SOURCES 同质，url_router 单循环 |
| `ingest` vs `download` 命名 | `ingest` canonical，`download` 永久 alias | 完全替换 download | K3 backward-compat 硬约束，老 CLAUDE.md 文档不动 |
| `meta.json source` 表示 | enum 字符串 `"bilibili"` 等 | 嵌套 object `{platform: "...", id: "..."}` | enum 简单，平台 ID 单独字段（youtube_id / aweme_id）；不引入嵌套破坏 D-04（Phase 1）"top-level dict 兼容" |
| 老归档 source 字段 | loader **不**回填 | loader 自动写 `source: "unknown"` | K3 + Phase 1 D-03 "loader-only 容忍，归档不动" |
| YouTube preflight 是否带 proxy | 是（`--proxy $HTTPS_PROXY`） | 第二次 retry 才带 proxy | 国内默认场景就是 GFW，preflight 不带 proxy 等于必失败 |
| 失败分类粒度 | 5 类（gfw / cookies / po / outdated / other） | 3 类（network / auth / other） | 5 类 hint 字符串够具体，3 类用户得自己排查 |
| Auto-fallback YouTube → Local | **不做** | preflight fail 自动 prompt user 提供 local path | K5 "Claude is decider"——auto-fallback 偷决策；只 raise 分类错误让 caller 决定 |
| 本地 mp4 slug 形式 | `local_<8hex>_<ascii_stem>` | `local_<absolute_path_hash_full>` | 8hex 防碰撞 + ascii_stem 给人读，全 hash 反人类 |
| `--out` CJK 检查范围 | 只查 `--out`，不查输入文件路径 | 两个都查 | 输入文件只用作 metadata + 拷贝源；`--out` 才进 ffmpeg subprocess（PITFALLS P4.1） |
| LocalSource 复制 vs symlink | copy | symlink (faster) | Windows symlink 需 admin；copy 兼容性 100%，慢只在首次 |
| ffprobe 跑在哪 | 每个 source `fetch()` 内 | cmd_ingest 末尾统一 | 统一更 DRY，但 source-specific 错误（如 LocalSource 收到不存在文件）需要 source-内 raise；选 source 内 |
| HEVC/AV1 处理 | log warning 不阻塞 | 强制 raise 阻塞 | Whisper 走音频流；codec 仅影响抽帧速度。warn-only 让用户决定 |
| `-vsync vfr` 应用范围 | 现 cmd_extract_frames + Phase 4 batch 都加 | 仅 Phase 4 batch | 现存 cmd_extract_frames 老路径也受益（OBS/iPhone VFR 视频之前隐性丢帧） |
| yt-dlp 版本警告 | log warning 不自动升级 | 自动 `pip install -U` | 自动升级是 surprise；warn 让用户决定 |
| Deno + yt-dlp-get-pot | opt-in CLAUDE.md 文档 | 进 requirements.txt | Deno 装机非平凡（winget），把它强加进默认 deps 砸用户首跑 |
| 3-plan 拆分 | 03-01 sources / 03-02 YouTube / 03-03 Local+ffprobe | 单一大 plan 或 5+ 微 plan | 与 ROADMAP 严格对齐；YouTube 复杂度独占 plan，Local + ffprobe 互依 |

## Pause-points reserved for user

- 执行阶段如果 YouTube preflight 把 5 类失败抛出来——**不在 discuss / plan 阶段问**，在 execute 阶段如果触发了 YouTube cmd_ingest 测试用例时才 surface 给 user
- Phase 6 PARA ship-or-skip——单独节点

## Deferred ideas

详见 `03-CONTEXT.md` `<deferred>` 节。
