# Phase 3: Source Refactor + New Sources (YouTube + Local mp4 + Generic) - Research

**Researched:** 2026-05-01
**Domain:** URL routing + multi-source ingest CLI (yt-dlp / vendor crawler / local file copy) + ffprobe preflight on Windows zh-CN
**Confidence:** HIGH for ffprobe field semantics, ascii-stem regex, CJK rejection broadening, dict-ordered byte-identical regression, yt-dlp dependency-free fact, agent/io.py reuse contract; MEDIUM for the 5-class YouTube stderr regex corpus (samples drawn from issue trackers, not from a controlled run on user's proxy); LOW for nothing — every claim has a verification path documented.

## Summary

Phase 3 is **dispatch refactor + 3 thin source wrappers**, not new domain logic. The existing two ingest paths (`src.download.download` for B站/yt-dlp, `agent.douyin_downloader.download_douyin` for 抖音) stay untouched. Three new files (`youtube.py`, `local.py`, `generic.py`) are 30-line wrappers; two existing paths get re-exported as `bilibili.py` and `douyin.py` source classes. The `match()/fetch()` Protocol + `SOURCES` ordered list + `url_router.route()` is ~80 LOC pure Python. The `ingest` subcommand is a copy of `cmd_download` calling the router; `download` becomes `cmd_download = cmd_ingest` (one line). All meta.json writes route through the **already-existing** `agent.io.write_json_atomic` from Phase 2 — sidecars come for free.

The hard parts are not the dispatcher. They are: (a) **YouTube preflight failure classification** — 5 categories matched against yt-dlp 2026.03+ stderr corpus, with deliberate over-matching of `other` so misclassification fails safe; (b) **ASCII-safe slug + CJK rejection** for local mp4 — verified empirically against edge cases (CJK basic, Katakana, Fullwidth ASCII, mixed, punctuation); (c) **ffprobe VFR detection** — exact-Fraction comparison is technically correct but flags constant-rate-but-imprecisely-calculated videos as VFR; mitigation is to apply `-vsync vfr` UNIFORMLY (D-23 already locks this) so VFR detection becomes informational only, not gating; (d) **byte-identical regression on B站/抖音** — Python dict insertion-order preservation guarantees byte-identical meta.json IF the new BilibiliSource / DouyinSource build the meta dict in the **exact same key order** as today's `src/download.py:79-87` and `agent/douyin_downloader.py:203-213`.

**Primary recommendation:** Treat each source as a **20-50 line declarative shim** delegating to existing modules; put the brain (URL pattern logic, slug normalization, ffprobe parser, YouTube preflight classifier) in **separate pure functions** in `agent/url_router.py` + a new `agent/sources/_common.py` so they're trivially Claude-eyeballable on the regression baseline. Keep `vendor/`, `src/download.py`, `agent/douyin_downloader.py` byte-frozen — every grain of work in this phase is in NEW files, not edits.

<user_constraints>
## User Constraints (from CONTEXT.md)

> Source: `.planning/phases/03-source-refactor-new-sources-youtube-local-mp4-generic/03-CONTEXT.md` (auto-mode; D-01..D-26 LOCKED).

### Locked Decisions

**Source Protocol & 注册表 (SRC-01, SRC-02):**
- **D-01:** `agent/sources/` 包下一文件一平台。每个文件 export 一个实现 `Source` Protocol 的类：`match(url_or_path: str) -> bool` + `fetch(target_dir: Path, *, skip_if_cached: bool = True) -> dict`. Protocol 定义在 `agent/sources/__init__.py`.
- **D-02:** 注册表 = `agent/sources/__init__.py` 顶层 `SOURCES: list[Source]`，**most-specific-first 顺序**：`[DouyinSource(), YouTubeSource(), BilibiliSource(), LocalSource(), GenericSource()]`。`agent/url_router.py:route(url_or_path)` 纯函数，遍历 SOURCES 返回第一个 `match()` 为真的实例；找不到 raise `RuntimeError`.
- **D-03:** GenericSource 是 catch-all yt-dlp fallback，永远最后；其 `match()` 总是返回 True，作为 sentinel.
- **D-04:** 现有 `agent/douyin_downloader.py` 和 `src/download.py` **保持原样不删** (PROJECT.md OOS "Rewrite or delete existing modules" 禁止)；新 source 类是它们的薄封装，内部委托调用。

**`ingest` CLI 与 `download` shim (SRC-03):**
- **D-05:** 新增 `python -m agent.tools ingest <url-or-path> --out <dir>` 子命令，调用 `url_router.route()`. argparse 配置与现 `download` 子命令一致.
- **D-06:** 现有 `download` 子命令变成薄 shim：`cmd_download(args)` 内部直接转 `cmd_ingest(args)`. 观察行为完全等价 — B 站和抖音 URL 跑出来 `meta.json` / `video.mp4` byte-identical.
- **D-07:** `ingest` 是 canonical name；`download` 永久保留 (K3 backward-compat 硬约束 + CLAUDE.md 文档化的 5 个核心命令之一).

**`meta.json` source 字段 (SRC-04, SRC-08):**
- **D-08:** `meta.json` 增加可选字段（additive，不 bump schema_version）：`source: "bilibili" | "douyin" | "youtube" | "generic" | "local"`; `youtube_id`（仅 YouTube）; `subtitle_origin: "creator" | "auto" | "asr" | "none"`. 抖音 `aweme_id` 字段保留现状.
- **D-09:** Loader 看到老归档 meta.json 缺 `source` 字段时**不自动填充** — 保持 K3 "Phase 2 后写新 sidecar，老归档不动" 原则. doctor 子命令显示 `source: —`.
- **D-10:** `subtitle_origin` 由 source 决定：yt-dlp 拿到 creator subtitles → `"creator"`；只能拿 auto-gen → `"auto"`；下游 `cmd_transcribe` 跑 ASR → loader 在 transcribe 完成后写回 `"asr"`；都没有 → `"none"`. 本 phase 只负责 yt-dlp 那两类的写入；ASR 路径留 Phase 5 TEACH-08 整合.

**YouTube 失败分类与 proxy (SRC-05, SRC-06, SRC-07, SRC-13):**
- **D-11:** YouTubeSource.fetch() 第一步是 **2 秒 `yt-dlp --simulate --proxy $HTTPS_PROXY <url>` preflight**. 失败时按 stderr 内容做 5 类分类：`gfw_blocked` / `cookies_stale` / `po_token_required` / `yt_dlp_outdated` / `other`.
- **D-12:** 每类有 LOCKED 中文 hint 字符串 (见 CONTEXT D-12 全文).
- **D-13:** Preflight 失败 raise `RuntimeError(f"YouTube ingest failed [{category}]: {hint}")`. caller 可 catch 决定 retry / fall back. 本 phase **不**做 auto-fallback 到 local mp4 (避免 silent decision 违反 K5).
- **D-14:** `HTTPS_PROXY` / `HTTP_PROXY` env vars (uppercase Windows 约定) 从 `os.environ` 读取，转 `--proxy` 传给 yt-dlp. 优先级：`HTTPS_PROXY` > `HTTP_PROXY` > 无 proxy.
- **D-15:** 启动时 log `yt_dlp.__version__`；如果版本 < 当前日期 90 天前，log warning. **不**自动升级.
- **D-16:** `requirements.txt` pin `yt-dlp>=2026.03.17`. Deno + `yt-dlp-get-pot` 不进默认 requirements，仅在 CLAUDE.md "首次设置" 节文档化为 opt-in.

**本地 mp4 路径 (SRC-09, SRC-10, SRC-12):**
- **D-17:** LocalSource.match() 判定：路径含 `://` 或 url 协议头 → False；其余情况 `Path(input).suffix.lower() in {".mp4", ".mkv", ".webm", ".flv", ".mov"}` AND `Path(input).is_file()` → True.
- **D-18:** **Slug 强制 ASCII-safe**：`slug = f"local_{sha256(absolute_path)[:8]}_{ascii_stem(stem)}"`. ascii_stem: 从 `Path(input).stem` 取前 8 个 `[a-zA-Z0-9]` 字符；没有任何 ASCII alnum → `"unnamed"`.
- **D-19:** **Reject `--out <path>` containing CJK** per PITFALLS P4.1：在 cmd_ingest 入口 `re.search(r"[一-鿿]", str(args.out))` 命中 → raise `ValueError(...)`. **只检查 --out**，不检查输入文件路径.
- **D-20:** LocalSource.fetch() **拷贝（不 symlink）** 输入 mp4 到 `output/<slug>/video.mp4`.

**ffprobe preflight & VFR 处理 (SRC-11, SRC-12):**
- **D-21:** **每个 source 的 fetch() 完成后**（拿到 video.mp4 后），统一跑 ffprobe. 解析：codec / 音频流是否存在 / 容器格式 / VFR 检测.
- **D-22:** HEVC / AV1 → **log warning 不阻塞**.
- **D-23:** **`-vsync vfr` 统一应用** — 现有 `agent/tools.py:cmd_extract_frames` 的 ffmpeg 调用增加 `-vsync vfr` 参数；Phase 4 的 `extract_frames_batch` 同样应用.

**Plans 拆分 (D-24/25/26):**
- 03-01: `agent/sources/` 包 + `url_router.py` + `ingest` 子命令 + `download` shim + `meta.json` source/youtube_id/aweme_id 字段 (SRC-01, 02, 03, 04). 包含 BilibiliSource / DouyinSource 重构 + GenericSource sentinel. **先做.**
- 03-02: YouTubeSource 全套 (SRC-05, 06, 07, 08, 13) — preflight 分类器 + proxy 转发 + 版本警告 + subtitle_origin + yt-dlp pin + Deno 文档. **最重的 plan.**
- 03-03: LocalSource + ffprobe preflight 统一 + `-vsync vfr` 统一 (SRC-09, 10, 11, 12). **最小 plan**；ffprobe 和 vsync 改动追溯惠及 B 站/抖音老路径.

### Claude's Discretion (planner / executor 自决)
- ffprobe 命令的具体超时 (建议 5s, planner 可调)
- 5 类 YouTube 失败的 stderr regex 精确写法 (CONTEXT 给中文 hint, 正则由 planner 在 RESEARCH 阶段定 — **本 RESEARCH §"YouTube Failure Classification" 给出最终建议**)
- meta.json 是否在 fetch() 写入还是统一 cmd_ingest 末尾写 (建议后者, 统一 atomic-write 入口 — **本 RESEARCH §"Architecture Patterns" 也建议后者**)
- BilibiliSource.match() 的 url 模式 (建议 `bilibili.com` / `b23.tv` 都识别)
- 是否提供 `--no-preflight` 跳过 ffprobe (YAGNI)

### Deferred Ideas (OUT OF SCOPE)
- Niconico / Vimeo / Twitter (X) extractor 特殊适配 (SRC-V2-02)
- Auto-fallback：YouTube preflight 失败自动切 LocalSource (违反 K5)
- `--no-preflight` flag 跳过 ffprobe (YAGNI)
- Niconico 等小众平台的 cookies 管理
- Symlink 模式 LocalSource (Windows 需 admin)
- HTTP_PROXY / HTTPS_PROXY 自动检测从 Windows registry
- PO Token 自动获取 / 缓存 (yt-dlp-get-pot 的活)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| SRC-01 | `agent/sources/` package — Protocol with `match()` + `fetch()`, one file per platform | §"Standard Stack" — Protocol idiom; §"Code Examples — Source Protocol" |
| SRC-02 | `agent/url_router.py` pure-function dispatcher; `cmd_download` calls it | §"Architecture Patterns — URL routing" + §"Code Examples — url_router.route" |
| SRC-03 | `ingest` subcommand; `download` shim; observable behavior identical for B站/抖音 | §"Byte-Identical Regression Strategy"; §"Standard Stack — Python dict order preservation" |
| SRC-04 | `meta.json` extended with `source` + platform IDs (`youtube_id`, `aweme_id`); additive | §"Code Examples — Building meta dict in lock-step order" |
| SRC-05 | YouTube `yt-dlp --simulate` preflight, 5 failure categories | §"YouTube Failure Classification" — full regex table + corpus |
| SRC-06 | `HTTPS_PROXY` / `HTTP_PROXY` env → `--proxy` forwarding | §"Code Examples — Proxy Forwarding" |
| SRC-07 | `yt_dlp.__version__` log + 90-day staleness warning | §"yt-dlp Version Drift Detection" — date parsing + Windows tz handling |
| SRC-08 | `subtitle_origin: auto \| creator \| asr \| none` in `meta.json` | §"Subtitle Origin Extraction" — `subtitles` vs `automatic_captions` keys |
| SRC-09 | Local mp4 input → copy into `output/<slug>/video.mp4`, ASCII-safe slug | §"Slug Normalization Edge Cases" — empirically verified table |
| SRC-10 | Reject CJK `--out` paths cleanly | §"CJK Rejection Regex Coverage" — narrow vs broad pattern table |
| SRC-11 | All sources run ffprobe preflight (codec, audio presence, container, VFR) | §"ffprobe Output Schema on Windows" — verified live on AV1 archive |
| SRC-12 | `extract_frames` uses `-vsync vfr` uniformly | §"VFR Detection Reality Check" — exact-fraction comparison gotcha |
| SRC-13 | `requirements.txt` pin `yt-dlp >=2026.03.17`; Deno + yt-dlp-get-pot opt-in | §"Standard Stack" + §"Architecture Patterns — CLAUDE.md opt-in section landing" |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

Extracted from `D:\gxy_code\videoSummary\CLAUDE.md` (2026-04-29):

1. **¥0 cost is hard constraint.** No paid LLM / ASR / Vision API. New sources must use yt-dlp / vendor crawler / local file copy. Do not introduce any cloud-billed dependency. — `[VERIFIED: CLAUDE.md L4]`
2. **Claude Code is the only decider.** Tool dispatches; Claude classifies failures and chooses recovery. Phase 3 implementation: preflight raises classified error, **does NOT auto-fallback** to LocalSource (D-13 already aligned with this). — `[VERIFIED: CLAUDE.md L5; CONTEXT D-13]`
3. **Documented core CLI surface = 5 commands** (`download / transcribe / extract_frames / aggregate / cleanup_frames`). New `ingest` is a 6th; `download` MUST stay listed in CLAUDE.md as still-working alias. — `[VERIFIED: CLAUDE.md L11-17]`
4. **Multimodal frame reading needs no API.** No Phase 3 work touches `extract_frames` semantics other than adding `-vsync vfr`; frame consumption remains Claude `Read`. — `[VERIFIED: CLAUDE.md L19-20]`
5. **抖音 first-time setup section** (CLAUDE.md L22-39) is the precedent style for documenting opt-in dependencies. The new "首次设置 YouTube ingest（可选）" section MUST follow the same structure: numbered steps, fenced bash blocks, end with a "失败时的恢复" note. — `[VERIFIED: CLAUDE.md L22-39]`
6. **Windows zh-CN UTF-8 setup is recommended-not-required.** Phase 3 must keep working on a bare zh-CN cmd terminal that has not run `chcp 65001`. The existing `ensure_ascii=True` print idiom in `agent/tools.py:135` for `cmd_download`'s meta-print survives in `cmd_ingest`. — `[VERIFIED: CLAUDE.md L41-63]`
7. **Quality redlines** (timestamp truth, code-from-screenshot, no padding, no fabrication, runnable code) — Phase 3 is pure infrastructure; no quality redline applies directly to new sources, but the LocalSource MUST NOT silently mangle Chinese filenames (would corrupt `meta.title` and propagate fabrication-class errors downstream). — `[VERIFIED: CLAUDE.md L175-181]`

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `yt-dlp` | `>=2026.03.17` (currently installed: `2026.04.10.235301.dev0`) | YouTube + generic + B站 download backend (existing); preflight via `--simulate` | Project-canonical (existing dep at `requirements.txt:2`); D-16 locks the floor; **HAS NO RUNTIME DEPENDENCIES** (verified: `pip show yt-dlp` reports empty `Requires:`), so the floor bump does NOT risk transitive httpx upgrade |
| `ffprobe` (ffmpeg suite) | bundled with ffmpeg; verified `ffprobe 8.1-essentials_build` on user's machine | Codec / audio-stream / container / VFR detection per source | Already on PATH (`subprocess.run(["ffmpeg",...])` works at `agent/tools.py:281`); reuses existing subprocess idiom |
| `httpx` | **`==0.27.2` LOCKED** (`requirements.txt:13`) | HTTP client used by `agent/douyin_downloader.py:185` for streaming the 抖音 video | Vendor `douyin_api` uses deprecated `proxies=` kwarg removed in 0.28+; **DO NOT BUMP** in this phase; verified yt-dlp does not require httpx so the pin survives the yt-dlp upgrade |

`[VERIFIED: pip show yt-dlp output 2026-05-01]` — Requires field empty.
`[VERIFIED: requirements.txt L11-13 + .planning/codebase/CONCERNS.md §3.2]` — httpx pin rationale.

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pathlib.Path` (stdlib) | — | All path manipulation | Project convention (CONVENTIONS §"I/O & Path Conventions"); never `os.path` |
| `re` (stdlib) | — | URL pattern match in `bilibili.py` / `douyin.py` / `youtube.py`; CJK rejection in `cmd_ingest`; ascii_stem normalization | Pure stdlib; no new dep |
| `subprocess` (stdlib) | — | `yt-dlp --simulate` preflight; `ffprobe` preflight | Existing idiom: `subprocess.run(cmd, check=True, capture_output=True, text=True, encoding="utf-8")`; `text=True` REQUIRED on Windows for stderr regex |
| `hashlib` (stdlib) | — | sha256 prefix for local mp4 slug | Already used in `agent/state.py:57` for params_hash — same idiom, different domain |
| `shutil` (stdlib) | — | `shutil.copyfile(src, dst)` for LocalSource — preserves ASCII-safe target path | `Path.write_bytes(Path.read_bytes())` would also work but `copyfile` is canonical and handles large files efficiently |
| `typing.Protocol` (stdlib, 3.8+) | — | `Source` Protocol with `match` + `fetch` | Project Python target = 3.13 (CONVENTIONS §"Language & Version") — Protocol is native; preferred over `abc.ABC` for structural typing |
| `agent.io.write_json_atomic` | Phase 2 RES-03 | Atomic meta.json write + sidecar | **Single landing point** per Phase 2 D-09; new sources MUST route through this — guarantees atomicity, sidecar emission, PermissionError retry |
| `agent.state.append_event` | Phase 2 RES-05 | `download` stage events on state.jsonl | Already wired in `agent/tools.py:71-80` `_emit_event()`; `cmd_ingest` re-uses it (the stage name stays `"download"` so state.jsonl entries remain comparable across pre/post-Phase-3 archives) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `typing.Protocol` | `abc.ABC` + `@abstractmethod` | ABC requires explicit `class BilibiliSource(Source):` inheritance; Protocol is structural ("duck-typed"). Protocol is the modern Python idiom (3.8+). No tradeoff for our case — pick Protocol. |
| `subprocess.run --simulate` for YouTube preflight | `yt_dlp.YoutubeDL({"simulate":True}).extract_info(url, download=False)` Python API | Python API is faster (no subprocess), but: (a) Python API exceptions are typed and would require import-time exception classes that drift between yt-dlp versions; (b) stderr-string regex is documented and version-stable; (c) 2-second timeout via `subprocess.run(timeout=2)` is trivial vs catching Python `TimeoutError` from non-cancellable `extract_info`. **Pick subprocess** — the cost is one fork + ~150ms; the benefit is zero coupling to yt-dlp internals. |
| `shutil.copyfile` for local mp4 | `os.symlink` | Windows `os.symlink` requires admin OR Developer Mode; copy is universal. CONTEXT D-20 already locks copy. |
| broad CJK regex `[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]` | narrow `[一-鿿]` (CONTEXT default) | The narrow pattern misses Katakana / Hiragana / CJK Compatibility / Fullwidth ASCII, all empirically verified to flow through ffmpeg with the same encoding hazards as CJK Unified. **Recommend planner upgrade D-19 to broad** — CONTEXT marks the regex as Claude's discretion (CONTEXT §Discretion line 91). See §"CJK Rejection Regex Coverage". |

**Installation:**
```bash
# Phase 3 plan 03-02 step:
pip install --upgrade "yt-dlp>=2026.03.17"

# Verify floor met:
python -c "import yt_dlp; print(yt_dlp.version.__version__)"

# Optional, opt-in (NOT in requirements.txt — CLAUDE.md docs only):
winget install DenoLand.Deno
pip install yt-dlp-get-pot
```

**Version verification (live, 2026-05-01):**
- yt-dlp installed: `2026.04.10.235301.dev0` ≥ `2026.03.17` ✓ — pin already met by user's environment.
- ffprobe installed: `8.1-essentials_build-www.gyan.dev` (gyan.dev Windows essentials build) ✓
- httpx installed: `0.27.2` matches the LOCKED pin ✓

`[VERIFIED: live `pip show` + `ffprobe -version` + `yt-dlp --version` 2026-05-01]`

## Architecture Patterns

### Recommended File Layout

```
agent/
├── tools.py              # cmd_ingest added; cmd_download = cmd_ingest shim; argparse new ingest subparser
├── url_router.py         # NEW; pure: route(url_or_path) -> Source
├── sources/
│   ├── __init__.py       # NEW; Source Protocol, SOURCES list, _ascii_stem helper, ffprobe wrapper
│   ├── _common.py        # NEW (optional); shared helpers (ffprobe_video, _build_meta_in_lockstep_order)
│   ├── bilibili.py       # NEW; thin wrapper -> src.download.download
│   ├── douyin.py         # NEW; thin wrapper -> agent.douyin_downloader.download_douyin
│   ├── youtube.py        # NEW; preflight classifier + yt_dlp Python API wrapper (or subprocess shell)
│   ├── generic.py        # NEW; sentinel -> src.download.download (yt-dlp catch-all)
│   └── local.py          # NEW; copy + ascii_stem slug + ffprobe
agent/io.py               # UNCHANGED — write_json_atomic re-used as-is
agent/state.py            # UNCHANGED — append_event reused; stage="download" stays the canonical event name
agent/douyin_downloader.py  # UNCHANGED (D-04)
src/download.py           # UNCHANGED (D-04)
vendor/                   # UNCHANGED (D-04, .gitignored)
requirements.txt          # bump yt-dlp floor to >=2026.03.17 (D-16)
CLAUDE.md                 # add 5 lines: ingest=download alias note + (collapsed) "首次设置 YouTube ingest（可选）" section + ASCII-only --out reminder
```

### Pattern 1: `Source` Protocol + `SOURCES` ordered list

**What:** Each source declares its own URL/path predicate (`match()`) and ingest action (`fetch()`). The router walks `SOURCES` in declaration order and returns the first match. GenericSource sits last with `match()` always True (sentinel).

**When to use:** Any URL-or-path → handler dispatch.

**Example (in `agent/sources/__init__.py`):**
```python
# Source: project pattern; informed by CONVENTIONS §"Type Hints" (Protocol over ABC)
from __future__ import annotations
from pathlib import Path
from typing import Protocol, runtime_checkable

@runtime_checkable
class Source(Protocol):
    """Ingest source: declares match predicate and fetch action."""

    name: str  # one of "bilibili" / "douyin" / "youtube" / "generic" / "local"

    def match(self, url_or_path: str) -> bool: ...

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        """Returns meta dict (will be written via agent.io.write_json_atomic by caller)."""

# Order matters — most-specific-first per CONTEXT D-02
from agent.sources.douyin   import DouyinSource
from agent.sources.youtube  import YouTubeSource
from agent.sources.bilibili import BilibiliSource
from agent.sources.local    import LocalSource
from agent.sources.generic  import GenericSource

SOURCES: list[Source] = [
    DouyinSource(),
    YouTubeSource(),
    BilibiliSource(),
    LocalSource(),
    GenericSource(),  # MUST stay last — sentinel match() returns True
]

# Defensive load-time invariant per RESEARCH §"Defensive Ordering Assertion"
assert SOURCES[-1].name == "generic", \
    f"GenericSource must be last in SOURCES (got {SOURCES[-1].name}); see CONTEXT D-02/D-03"
assert all(s.name != "generic" for s in SOURCES[:-1]), \
    "GenericSource must appear exactly once and only at the end"
```

`[CITED: PEP 544 Protocols (typing-protocol)]` — Protocol defined since Python 3.8; structural typing.
`[VERIFIED: project codebase grep — no @abstractmethod precedent; Protocol is the natural fit]`

### Pattern 2: Pure-function URL router

**What:** A 1-function module. Trivially unit-testable. Imports SOURCES; loops; returns the first match.

**Example (`agent/url_router.py`):**
```python
# Source: project pattern; mirrors src/asr.py:parse_vtt purity
from __future__ import annotations
from agent.sources import SOURCES, Source

def route(url_or_path: str) -> Source:
    """Return the first source whose match() accepts url_or_path.

    Raises:
        RuntimeError: if no source matches (impossible in practice — GenericSource
                       is the catch-all sentinel, but the check is defensive in case
                       SOURCES is mutated at runtime).
    """
    for source in SOURCES:
        if source.match(url_or_path):
            return source
    raise RuntimeError(f"No source matched: {url_or_path!r}")
```

### Pattern 3: `cmd_ingest` orchestrates; `cmd_download` shims

**What:** `cmd_ingest` is the new orchestration entry point. It (1) validates `--out` for CJK (D-19), (2) routes via `url_router.route()`, (3) calls `source.fetch()`, (4) runs ffprobe preflight (D-21), (5) writes meta.json + sidecar via `agent.io.write_json_atomic`, (6) emits state.jsonl events using stage `"download"` so events remain comparable to pre-Phase-3 events.

**`download` shim is a single line:**
```python
# Source: agent/tools.py — new pattern, replaces L83-139 substring branch
def cmd_download(args):
    """[backward-compat alias] 下载视频. 转 cmd_ingest 处理."""
    return cmd_ingest(args)
```

### Pattern 4: meta.json built in lock-step key order

**What:** To preserve byte-identical regression on B站/抖音, the new BilibiliSource and DouyinSource MUST construct the meta dict in the **exact key order** the legacy modules use today. Python 3.7+ guarantees insertion-order preservation in dicts; `json.dumps` emits keys in dict order; `agent.io.write_json_atomic` does NOT reorder keys (it just calls `json.dumps(obj, ensure_ascii=False, indent=2)` per `agent/io.py:119`).

**Reference legacy orders (cite-exact-line):**
- `src/download.py:79-87` — order: `video_path, subtitle_path, title, uploader, duration, description, url`
- `agent/douyin_downloader.py:203-213` — order: `video_path, subtitle_path, title, uploader, duration, description, url, aweme_id, source`

**Phase 3 add-ons (additive only, AT THE END to preserve prefix byte-identity for the legacy 7-key core):**
- After legacy keys: `source` (already present in douyin path; ADD for bilibili — but ADDING any field WOULD break byte-identical baseline). **See §"Byte-Identical Regression Strategy" for the resolution: write the new fields ONLY for new ingests; do not retro-edit existing meta.json.**

`[VERIFIED: live read of `tests/regression/BV132wizyEEB/meta.json` — keys: video_path/subtitle_path/title/uploader/duration/description/url, no `source` field]`
`[VERIFIED: live read of legacy douyin meta — keys end with `aweme_id, source`]` (CONCERNS §1.3)
`[VERIFIED: agent/io.py:119 — `json.dumps(obj, ensure_ascii=False, indent=2)` — no `sort_keys`]`

### Pattern 5: Centralize ffprobe in `agent/sources/_common.py`

**What:** All five sources need the same ffprobe preflight (D-21). Extracting a shared helper into `agent/sources/_common.py` keeps each source's `fetch()` ~30 lines.

**Example:**
```python
# Source: project pattern; mirrors agent/io.py:_get_ffmpeg_version subprocess idiom
from __future__ import annotations
import json, subprocess
from fractions import Fraction
from pathlib import Path

_FFPROBE_TIMEOUT_S = 5.0  # CONTEXT line 91 leaves this to planner; 5s comfortably exceeds local-disk read

def ffprobe_video(video_path: str | Path) -> dict:
    """Returns dict with keys: codec, container, has_audio, fps_mode, width, height, duration_s.

    Raises RuntimeError on missing audio (D-21). Logs warning on HEVC/AV1 (D-22).
    """
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(video_path)],
        check=True, capture_output=True, text=True, encoding="utf-8",
        timeout=_FFPROBE_TIMEOUT_S,
    )
    info = json.loads(result.stdout)
    streams = info.get("streams", [])
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

    if not audio_streams:
        raise RuntimeError(
            f"No audio stream in {video_path}; whisper cannot transcribe. "
            f"Remux with `ffmpeg -i in -c:v copy -c:a aac out.mp4`"
        )
    if not video_streams:
        raise RuntimeError(f"No video stream in {video_path}")

    v = video_streams[0]
    codec = v.get("codec_name", "unknown").lower()
    fps_mode = _detect_vfr(v.get("r_frame_rate"), v.get("avg_frame_rate"))
    return {
        "codec": codec,
        "container": info.get("format", {}).get("format_name", "unknown"),
        "has_audio": True,
        "fps_mode": fps_mode,  # "VFR" | "CFR" | "unknown"
        "width": v.get("width"),
        "height": v.get("height"),
        "duration_s": float(info.get("format", {}).get("duration", 0)),
    }

def _detect_vfr(r_rate: str | None, avg_rate: str | None) -> str:
    """Strict-fraction comparison per CONTEXT D-21 spec. Returns 'VFR'/'CFR'/'unknown'."""
    if not r_rate or not avg_rate or "/" not in r_rate or "/" not in avg_rate:
        return "unknown"
    try:
        rf, af = Fraction(r_rate), Fraction(avg_rate)
    except (ValueError, ZeroDivisionError):
        return "unknown"
    if af == 0:
        return "unknown"
    return "VFR" if rf != af else "CFR"
```

`[VERIFIED: live ffprobe -v error -print_format json on tests/regression/BV132wizyEEB/video.mp4 — JSON output stable, fields as expected]`

### Anti-Patterns to Avoid

- **Anti-pattern: subclass-inheritance for Source.** ABC + abstractmethod adds boilerplate without buying anything. `typing.Protocol` is the modern idiom and matches CONVENTIONS §"Type Hints" PEP-604/builtin-generics direction.
- **Anti-pattern: meta.json write inside source.fetch().** Each source would replicate the `agent.io.write_json_atomic(meta_path, meta, sidecar_params=...)` call, fragmenting the single-landing-point Phase 2 D-09 invariant. **Centralize meta-write in `cmd_ingest` AFTER `source.fetch()` returns the meta dict.** CONTEXT line 91 marks this as discretion; this RESEARCH locks the recommendation.
- **Anti-pattern: build meta dict via `{**old, "source": "..."}` spread.** Spread does NOT preserve insertion order across all CPython versions for keys present in both dicts. Use explicit dict literal in the canonical key order.
- **Anti-pattern: `subprocess.run(["yt-dlp", url], shell=True, encoding=None)` with implicit Windows code page.** Stderr would arrive as bytes decoded with `cp936` and break the regex classification. **Always pass `text=True, encoding="utf-8"`** (and `shell=False` is the default).
- **Anti-pattern: silent `os.replace` for local mp4 → output dir.** If src and dst are on different volumes, `os.replace` raises. CONTEXT D-20 mandates copy (works cross-volume). Use `shutil.copyfile`.
- **Anti-pattern: in-source `meta["source"] = "youtube"` mutation after the fact.** This re-orders keys (`source` ends up last in some constructions, middle in others). Build the dict literal once with all final fields in declared order.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| URL pattern matching | Custom `if "youtube.com" in url and not "shorts"` chain | Per-source `re.compile(pattern).search(url)` in each source's `match()` | yt-dlp itself has `_VALID_URL` regex per extractor; we mirror that style. Avoids substring false positives like `news.example.com/youtube-took-down` |
| ffprobe JSON parsing | Regex over text output | `ffprobe -print_format json` + `json.loads` | JSON output is contractually stable; text format changes between ffmpeg versions |
| YouTube subtitle origin detection | Walking VTT files in output dir to guess auto-vs-creator | `yt_dlp` info dict's `subtitles` (creator) vs `automatic_captions` (auto) | Verified live on `output/BV132wizyEEB/video.info.json`: `subtitles` contains `danmaku`; `automatic_captions` is empty / absent. yt-dlp DOES populate both keys distinctly. |
| ASCII slug generation | Custom transliteration / pinyin lookup | `re.sub(r"[^a-zA-Z0-9]", "", stem)[:8] or "unnamed"` | Pinyin transliteration imports `pypinyin` (~1MB); for our purpose ("file is identifiable in `output/` listing AND non-CJK for ffmpeg") the 8-char hex prefix already provides uniqueness. CONTEXT D-18 locks this. |
| CJK detection | Range-by-range manual character-class building | Single `re.compile(r"[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]")` | Verified empirically; covers CJK Unified + Compatibility + Hiragana + Katakana + Fullwidth ASCII (the four blocks that hit ffmpeg subprocess). Adding non-Han Asian scripts (Korean Hangul, Bopomofo) is out of scope for "Windows zh-CN dev env" |
| yt-dlp version date parsing | Custom `\d{4}\.\d{2}\.\d{2}` regex over `__version__` | `datetime.date.fromisoformat(version.replace(".", "-")[:10])` | Format is exactly `YYYY.MM.DD[.HHMMSS][.devN]`; replace dots with dashes and slice to first 10 chars yields `YYYY-MM-DD` directly parseable. See §"yt-dlp Version Drift Detection" |
| Atomic meta.json write | tempfile + os.replace inline in each source | `agent.io.write_json_atomic` (Phase 2 RES-03) | Phase 2 D-09 single-landing-point invariant; new sources MUST call it |
| state.jsonl event emission | Custom JSON-line append in each source | `agent.state.append_event` via `agent/tools.py:71-80 _emit_event` | Phase 2 D-12/D-13 contract; bypassing it would break `doctor` output and resume |

**Key insight:** This phase has high "don't reinvent" density precisely because Phase 2 already paid the infrastructure cost. The new sources are additive content; the writing/atomicity/state plumbing is a Phase 2 free gift. The biggest hand-rolling risk is the YouTube failure classifier — see §"YouTube Failure Classification" for the recommended regex set rather than ad-hoc per-message growth.

## Runtime State Inventory

> Phase 3 is **NOT a rename / refactor / migration** of stored data. It is **additive** — new files, new CLI subcommand, new meta.json fields written ONLY for new ingests. The 17-archive policy (D-09) is "loader sees missing field → display `—`, do not retro-fill." This section is included for completeness because the phase touches dispatcher logic and CONVENTIONS-locked file layouts; nothing here requires migration.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — `output/<slug>/meta.json` schema is **additively extended** (D-08); existing 17 archives are unchanged. No rename of `aweme_id`; no removal of any existing field. No keys/IDs/collection names are renamed. | None — D-09 explicitly forbids retro-fill |
| Live service config | None — vendor `config.yaml` is mutated by `_patch_config_cookie` (CONCERNS §2.2) **only at ingest time**; Phase 3 changes nothing here. No service-side state has the string "douyin" / "bilibili" baked in. | None |
| OS-registered state | None — no Windows Task Scheduler / systemd / pm2 / launchd entries reference the old `cmd_download` name. CLAUDE.md (project memory) references the command name; that's a doc update, not a runtime registration. | Add `ingest` to CLAUDE.md tool surface and document `download` as alias (D-07) |
| Secrets / env vars | `BILIBILI_SESSDATA`, `DOUYIN_COOKIES_FILE`, `DOUYIN_COOKIES_BROWSER`, `ASR_DEVICE` — names unchanged; **adds** `HTTPS_PROXY` / `HTTP_PROXY` consumption (D-14, additive). No env-var rename. | None on existing; add HTTPS_PROXY / HTTP_PROXY to CLAUDE.md "环境变量（.env）" section |
| Build artifacts / installed packages | `pip install -r requirements.txt` will pick up the new `yt-dlp>=2026.03.17` floor. Currently installed `2026.04.10.235301.dev0` ≥ floor → no reinstall needed in user's environment. **Stale pyc**: bytecode cache in `agent/__pycache__/` will silently keep old `cmd_download` body if the user doesn't restart the Python interpreter; not a runtime hazard since each `python -m agent.tools …` invocation is a fresh process. | None — pip resolution handles the floor bump |

**Nothing requires a data migration.** Phase 3 is dispatcher refactor + new sources + meta.json additive fields. The hardest "state" question — "do existing meta.json files need a `source` field added retroactively?" — was answered NO in CONTEXT D-09.

## Common Pitfalls

### Pitfall 1: VFR detection is correct-but-noisy on real B站 archives

**What goes wrong:** Strict-equality `Fraction(r_frame_rate) != Fraction(avg_frame_rate)` flags videos as VFR even when the actual variation is sub-millisecond. The B站 baseline `output/BV132wizyEEB/video.mp4` reports `r_frame_rate=30/1` and `avg_frame_rate=2221000/74033` (= 29.999675…/1) — strictly different fractions, numerically near-identical. If `meta.json:fps_mode = "VFR"` triggers any user-visible alarm, half of legitimate H.264-or-AV1 yt-dlp B站 downloads will look broken.

**Why it happens:** Container `r_frame_rate` is the codec-declared rate (often a clean fraction like `30/1` or `60/1`). `avg_frame_rate` is recomputed from `nb_frames / duration_ts * time_base`, so it picks up sub-frame-time rounding. They are rarely exactly equal even on truly constant-rate sources.

**How to avoid:** Treat `fps_mode` as **informational metadata only**. The actionable response — `-vsync vfr` on extract_frames — is **uniformly applied** (CONTEXT D-23) regardless of detected mode. So even if the detector mis-flags a CFR video as VFR, frame extraction is unaffected. **Do not block ingest on `fps_mode == "VFR"`.** Do not log warning on VFR detection (the user has nothing to do about it; D-23 already handles it).

**Warning signs:** A planner/executor adds a `if fps_mode == "VFR": log.warning("VFR detected; consider remuxing")` line. **Reject this** — the remux suggestion is for HEVC/AV1 codec (D-22), not for VFR.

`[VERIFIED: live ffprobe on output/BV132wizyEEB/video.mp4 — r=30/1, avg=2221000/74033, strict-fraction unequal but ratio = 0.99989]`

### Pitfall 2: Naive `--out output/编程教程` rejection too narrow

**What goes wrong:** CONTEXT D-19 names regex `[一-鿿]` (CJK Unified Ideographs basic block). This misses Hiragana (`あ-ゟ`), Katakana (`ア-ヿ`), Fullwidth ASCII (`ＡＢＣ`/`％`), and CJK Compatibility Ideographs. All four blocks suffer the same ffmpeg-subprocess GBK code-page hazard on Windows zh-CN that motivated D-19 in the first place. A user who passes `output/カタカナ_demo/` skips the validator and hits ffmpeg corruption later.

**Why it happens:** The narrow `[一-鿿]` reads natural in CJK source code but matches only one of four hazardous Unicode blocks.

**How to avoid:** Use the **broad pattern** `re.compile(r"[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]")` (verified empirically — see §"CJK Rejection Regex Coverage"). CONTEXT line 91 marks the regex precise wording as Claude's discretion; this RESEARCH recommends planner use the broad pattern. The error message is the same (D-19 wording).

**Warning signs:** A user reports "I passed `--out output/ホント_test` and got `audio.wav` at `output/???_test/` with garbled directory name." This is the failure mode the broad regex prevents.

### Pitfall 3: yt-dlp `--simulate` shell-escape on Windows

**What goes wrong:** `subprocess.run(["yt-dlp", "--simulate", "--proxy", os.environ["HTTPS_PROXY"], url], ...)` works on Linux/Mac. On Windows, if `HTTPS_PROXY` is empty string (not unset), `--proxy` receives `""` and yt-dlp errors with `Unable to download webpage: Invalid URL ''`. This stderr matches the `gfw_blocked` regex by coincidence but the cause is the empty proxy, not GFW.

**Why it happens:** `os.environ.get("HTTPS_PROXY", "")` returns empty string for unset OR set-empty; treating both the same gives wrong classification.

**How to avoid:** Build the argv list conditionally:
```python
proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or None  # falsy empty -> None
cmd = ["yt-dlp", "--simulate", "--no-warnings", url]
if proxy:
    cmd[1:1] = ["--proxy", proxy]
```
Never pass `--proxy ""`. Verify with `if proxy and proxy.strip()`.

**Warning signs:** A YouTube preflight returns `gfw_blocked` even when proxy IS configured and reachable independently — symptom of the empty-string-vs-unset bug.

`[CITED: yt-dlp #11592 — proxy not works on YouTube; bug pattern: empty proxy URL accepted as proxy]`(https://github.com/yt-dlp/yt-dlp/issues/11592)

### Pitfall 4: `subprocess.run(timeout=2)` on Windows can hang past 2s

**What goes wrong:** `subprocess.run(..., timeout=2)` raises `TimeoutExpired` after 2 seconds, but the child process may still be alive — `subprocess` calls `proc.kill()` then `proc.communicate()`, which **can hang on Windows** if the child has blocked file handles (yt-dlp opens the cookies file and proxies). Net wallclock can be 2-15s.

**Why it happens:** Windows has no SIGKILL; `proc.kill()` issues `TerminateProcess` which is async and the child's stdio pipes can outlive it. `communicate()` then waits for the pipe drain.

**How to avoid:** (a) After catching `TimeoutExpired`, fall through to `proc.wait(timeout=5)` with a generous secondary timeout; (b) classify the failure as `gfw_blocked` because a fast network failure is what the 2s timeout was designed to detect — a slow network is, for our purposes, the same answer ("user's connection isn't healthy enough; suggest local-mp4"). The 2s is best-effort, not hard SLA.

**Warning signs:** A user reports `cmd_ingest` taking 8 seconds before printing the GFW hint. Acceptable behavior — log the elapsed time so user knows the preflight tried.

`[CITED: Python docs subprocess.run timeout — note about kill on Windows]`

### Pitfall 5: `cmd_download` shim drops state.jsonl `download` events

**What goes wrong:** `cmd_download(args)` simply calls `cmd_ingest(args)` (D-06). If `cmd_ingest` emits state.jsonl events with stage `"ingest"` instead of `"download"`, every existing analytics / doctor consumer that filters on `stage == "download"` silently breaks for new ingests but still works for archived runs.

**Why it happens:** The natural temptation is to name the new stage after the new command.

**How to avoid:** Lock `stage="download"` in `cmd_ingest`'s `_emit_event` calls — same name as today's `cmd_download` events, regardless of what the user typed at the CLI. CLAUDE.md and `agent/tools.py:_DOCTOR_ARTIFACTS` (line 64) both anchor on `("meta.json", "download")` — keep `"download"` as the stage canonical name. The CLI surface gets a new name (`ingest`) but the state-log pipeline does not.

**Warning signs:** `python -m agent.tools doctor output/<new-slug>` shows `last_state: —` in the meta.json row even though ingest succeeded — symptom of stage-name drift.

`[VERIFIED: agent/tools.py:64 _DOCTOR_ARTIFACTS hardcodes stage="download"]`

### Pitfall 6: meta.json byte-identical regression is fragile under field additions

**What goes wrong:** SRC-04 requires `source` field added to meta.json. CONTEXT Success Criterion 1 requires byte-identical regression. These conflict: if the new BilibiliSource writes `{"video_path":..., "url":..., "source":"bilibili"}`, the file has a new line and hash differs from the archived `meta.json` (which has 7 keys ending at `url`).

**Why it happens:** Phase 1 D-08 regression method is "Claude eyeball-diff JSON 三件套". The phase boundary is subtle: byte-identical for the **legacy 7 keys** (no reordering, no whitespace changes), additive new field at the **end**. NOT byte-identical at file-hash level.

**How to avoid:** Recast Success Criterion 1 as **"byte-identical for the legacy field set; additive `source` field appears as final key, never breaks existing parsers."** Verify by:
1. JSON-parse new and old meta.json
2. Assert `set(old_meta).issubset(set(new_meta))` (no fields lost)
3. Assert old field values unchanged: `all(old_meta[k] == new_meta[k] for k in old_meta)`
4. Assert key order: `list(new_meta)[:len(old_meta)] == list(old_meta)` (new keys appended at end)

This is what Phase 1 D-08 "Claude eyeball-diff" actually checks for in practice — it's a **semantic** identity, not a hash.

**Warning signs:** A planner says "let's add `meta_dict_hash` to assert exact bytes." Reject — the test would fail on `source: "bilibili"` addition by design.

`[VERIFIED: live read tests/regression/BV132wizyEEB/meta.json key order]` — see §"Byte-Identical Regression Strategy" for the formal verification recipe.

### Pitfall 7: 8-char ascii_stem collisions on common patterns

**What goes wrong:** Two videos `1234567890_abcdef.mp4` and `1234567899_xyz.mp4` both produce `ascii_stem = "12345678"`. The 8-hex `sha256[:8]` prefix DOES disambiguate them (different paths → different hashes), so the full slug is unique. But if the user moves a file (different path → different hash) and re-ingests, they get a NEW `output/local_<newhash>_12345678/` directory, doubling disk usage with no warning.

**Why it happens:** sha256 is over the **absolute path**, not the file content (D-18 spec: `sha256(absolute_path)`). Path-based hashing is intentional (we don't want to read 500MB of mp4 to compute a hash) but means rename/move = new slug.

**How to avoid:** Document this in CLAUDE.md "首次设置 LocalSource (可选)" subsection: "moving the input file changes the slug; stale `output/local_*/` directories accumulate — clean them with `rmdir output\local_oldhash_*` manually (no auto-eviction)." User accepts this tradeoff; D-20 already locked copy-not-symlink (which would have the same issue with even worse semantics).

**Warning signs:** User complains `output/` is filling up with multiple slugs for the same video. Document but don't auto-handle.

## Code Examples

### YouTube failure classification end-to-end
```python
# Source: agent/sources/youtube.py — informed by §"YouTube Failure Classification" + CONTEXT D-11..D-15
from __future__ import annotations
import os, re, subprocess, logging
from datetime import date
from pathlib import Path

log = logging.getLogger(__name__)

# 5 categories, ordered most-specific-first; "other" is the catch-all
_CATEGORY_PATTERNS = [
    # po_token_required: SABR rollout 2026, MUST come before cookies_stale —
    # the message often co-occurs with "Sign in to confirm" but the actionable
    # cause is PO token, not cookies
    ("po_token_required", re.compile(
        r"PO\s*Token|requires\s+PO\s*Token|missing\s+a\s+GVS\s+PO\s*Token|"
        r"SABR|Server-side\s+ad\s+breakdown|GVS\s+PO\s*Token", re.I)),
    # cookies_stale: explicit auth/login wording from yt-dlp issue corpus
    ("cookies_stale", re.compile(
        r"Sign in to confirm|Login required|This video requires payment|"
        r"members[- ]only|HTTP Error 403", re.I)),
    # yt_dlp_outdated: extractor signature corruption typical of YT extractor drift
    ("yt_dlp_outdated", re.compile(
        r"Unable to extract.*signature|Failed to extract any player response|"
        r"unable to extract initial player response|"
        r"extractor\s+args.*not\s+recognized", re.I)),
    # gfw_blocked: network-layer keywords; intentionally last among the specific
    # patterns so a "Sign in to confirm" caused by 403-during-handshake is classified
    # as cookies_stale, not gfw_blocked
    ("gfw_blocked", re.compile(
        r"Unable to download webpage|getaddrinfo failed|"
        r"Connection.*timed out|Network is unreachable|"
        r"Connection refused|connect timeout|TransportError|"
        r"handshake operation timed out|Remote end closed connection", re.I)),
]

# CONTEXT D-12 LOCKED hint strings; ASCII-only on the labels for grep, Chinese in body
_HINTS = {
    "gfw_blocked":      "GFW 阻断；export HTTPS_PROXY=http://127.0.0.1:7890 后重试，或下载到本地后用 `ingest <local-path>`",
    "cookies_stale":    "Cookies 失效；浏览器登录 YouTube 后重新导出 cookies.txt",
    "po_token_required":"PO Token required；安装 Deno + `pip install yt-dlp-get-pot`，详见 CLAUDE.md",
    "yt_dlp_outdated":  "yt-dlp 版本过旧；`pip install -U yt-dlp` 后重试",
    "other":            "下载失败；详见 stderr 头 200 字符",  # actual stderr appended at raise site
}

def classify_stderr(stderr: str) -> str:
    """Return one of the 5 categories. Bias to 'other' if no specific pattern hits."""
    for cat, pat in _CATEGORY_PATTERNS:
        if pat.search(stderr):
            return cat
    return "other"


def _build_yt_dlp_argv(url: str, *, simulate: bool = False) -> list[str]:
    """Construct yt-dlp argv with proxy if configured. Never passes empty --proxy."""
    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or "").strip()
    cmd = ["yt-dlp", "--no-warnings", "--no-progress"]
    if simulate:
        cmd.append("--simulate")
    if proxy:
        cmd += ["--proxy", proxy]
    cmd.append(url)
    return cmd


def youtube_preflight(url: str, *, timeout_s: float = 2.0) -> None:
    """2-second yt-dlp --simulate. On failure raise RuntimeError with classified hint.

    On success returns None.
    """
    cmd = _build_yt_dlp_argv(url, simulate=True)
    try:
        result = subprocess.run(
            cmd, check=True, capture_output=True, text=True,
            encoding="utf-8", timeout=timeout_s,
        )
        return  # exit 0 = OK, no failure
    except subprocess.TimeoutExpired as e:
        # Pitfall 4: secondary wait then classify as gfw_blocked
        log.warning("yt-dlp --simulate exceeded %.1fs (timeout); classified as gfw_blocked", timeout_s)
        category = "gfw_blocked"
        stderr = (e.stderr or b"").decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    except subprocess.CalledProcessError as e:
        stderr = e.stderr or ""
        category = classify_stderr(stderr)
    except FileNotFoundError:
        raise RuntimeError("yt-dlp not on PATH; pip install yt-dlp") from None

    hint = _HINTS[category]
    if category == "other":
        # Append head 200 chars per D-12
        hint = f"{hint}: {stderr[:200].strip()}"
    raise RuntimeError(f"YouTube ingest failed [{category}]: {hint}")
```

`[CITED: yt-dlp issue #16221 — Sign in to confirm message]` (https://github.com/yt-dlp/yt-dlp/issues/16221)
`[CITED: yt-dlp issue #11592 — proxy not works on YouTube]` (https://github.com/yt-dlp/yt-dlp/issues/11592)
`[CITED: yt-dlp issue #15258 — Connection timed out via SOCKS]` (https://github.com/yt-dlp/yt-dlp/issues/15258)
`[CITED: yt-dlp issue #7594 — unable to extract initial player response]` (https://github.com/yt-dlp/yt-dlp/issues/7594)
`[CITED: yt-dlp PO Token Guide]` (https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide)

### Local mp4 ingest with ascii_stem + ffprobe

```python
# Source: agent/sources/local.py — implements D-17, D-18, D-20, D-21
from __future__ import annotations
import hashlib, re, shutil
from pathlib import Path
from agent.sources._common import ffprobe_video

class LocalSource:
    name = "local"
    _MEDIA_EXTS = {".mp4", ".mkv", ".webm", ".flv", ".mov"}

    def match(self, url_or_path: str) -> bool:
        # D-17: reject anything with URL scheme
        if "://" in url_or_path:
            return False
        p = Path(url_or_path)
        return p.suffix.lower() in self._MEDIA_EXTS and p.is_file()

    def fetch(self, url_or_path: str, target_dir: Path,
              *, skip_if_cached: bool = True) -> dict:
        src = Path(url_or_path).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        target_video = target_dir / "video.mp4"

        if skip_if_cached and target_video.exists():
            # idempotent — no-op if already copied; ffprobe will re-run via cmd_ingest
            pass
        else:
            # D-20: copy not symlink
            shutil.copyfile(src, target_video)

        # ffprobe will run in cmd_ingest after fetch returns (D-21)

        return {
            # Lock-step order with legacy meta.json keys (Pattern 4)
            "video_path": str(target_video),
            "subtitle_path": None,
            "title": src.stem,        # may be CJK — that's fine, only for display
            "uploader": "",
            "duration": 0,            # ffprobe will overwrite in cmd_ingest
            "description": "",
            "url": str(src),          # absolute path serves as url for local
            # New Phase 3 fields (always at the end — Pattern 4 + Pitfall 6)
            "source": "local",
            "subtitle_origin": "none",  # local mp4 has no subtitle stream extraction in this phase
        }

def make_local_slug(input_path: str) -> str:
    """D-18: local_<8hex>_<ascii_stem(stem)>"""
    src = Path(input_path).resolve()
    h = hashlib.sha256(str(src).encode("utf-8")).hexdigest()[:8]
    stem = src.stem
    ascii_part = re.sub(r"[^a-zA-Z0-9]", "", stem)[:8] or "unnamed"
    return f"local_{h}_{ascii_part}"
```

### CJK rejection at cmd_ingest entry (D-19, broadened per Pitfall 2)

```python
# Source: agent/tools.py cmd_ingest entry — broadens narrow regex per Pitfall 2
import re

# Broad pattern: CJK Unified Ideographs + Compatibility Ideographs +
# Hiragana + Katakana + Fullwidth ASCII
# Matches against str(args.out) anywhere in the path
_CJK_PAT = re.compile(r"[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]")

def _validate_out_path(out_path: str) -> None:
    if _CJK_PAT.search(str(out_path)):
        raise ValueError(
            f"CJK characters in --out path break ffmpeg subprocess on Windows zh-CN; "
            f"use ASCII-only path under output/ (got {out_path!r})"
        )
```

### URL pattern matching examples

```python
# Source: agent/sources/{bilibili,douyin,youtube}.py — informed by yt-dlp _VALID_URL idiom
import re

# bilibili.py
class BilibiliSource:
    name = "bilibili"
    _PATTERN = re.compile(r"https?://(?:www\.|m\.)?(?:bilibili\.com|b23\.tv)/", re.I)
    def match(self, url: str) -> bool:
        return bool(self._PATTERN.match(url))
    # fetch() delegates to src.download.download (the existing path)

# douyin.py
class DouyinSource:
    name = "douyin"
    _PATTERN = re.compile(r"https?://(?:www\.|v\.|m\.)?(?:douyin\.com|iesdouyin\.com)/", re.I)
    def match(self, url: str) -> bool:
        return bool(self._PATTERN.match(url))
    # fetch() delegates to agent.douyin_downloader.download_douyin

# youtube.py
class YouTubeSource:
    name = "youtube"
    _PATTERN = re.compile(
        r"https?://(?:www\.|m\.)?(?:youtube\.com|youtu\.be)/", re.I
    )
    def match(self, url: str) -> bool:
        return bool(self._PATTERN.match(url))
    # fetch() runs preflight then delegates to yt-dlp Python API or src.download.download
```

`[VERIFIED: bilibili.com URL precedence — `output/BV132wizyEEB/meta.json` shows `https://www.bilibili.com/video/BV132wizyEEB`]`
`[VERIFIED: douyin URL precedence — agent/douyin_downloader.py:76 covers v.douyin.com / iesdouyin.com short links]`

## YouTube Failure Classification

This subsection is the answer to research question 2 — the empirical recommended regex for the 5 categories.

### Corpus

Drawn from yt-dlp 2026 GitHub issue tracker:
- `[CITED: #10128 "Sign in to confirm you're not a bot"]`(https://github.com/yt-dlp/yt-dlp/issues/10128)
- `[CITED: #10683 ZkW3aoYhFwY: Sign in to confirm]`(https://github.com/yt-dlp/yt-dlp/issues/10683)
- `[CITED: #15865 All public YouTube videos require login]`(https://github.com/yt-dlp/yt-dlp/issues/15865)
- `[CITED: #16221 [YouTube] Sign in to confirm — March 2026]`(https://github.com/yt-dlp/yt-dlp/issues/16221)
- `[CITED: #14307 PO tokens with web client]`(https://github.com/yt-dlp/yt-dlp/issues/14307)
- `[CITED: #14665 PO Token not available in player requests]`(https://github.com/yt-dlp/yt-dlp/issues/14665)
- `[CITED: #15789 Verifying PO Token configuration]`(https://github.com/yt-dlp/yt-dlp/issues/15789)
- `[CITED: #11592 yt-dlp with proxy not works on YouTube]`(https://github.com/yt-dlp/yt-dlp/issues/11592)
- `[CITED: #15258 NordVPN: Connection timed out (connect timeout=20.0)]`(https://github.com/yt-dlp/yt-dlp/issues/15258)
- `[CITED: #11842 SOCKS5 connection timeout]`(https://github.com/yt-dlp/yt-dlp/issues/11842)
- `[CITED: #11831 Unable to connect to proxy]`(https://github.com/yt-dlp/yt-dlp/issues/11831)
- `[CITED: #8233 The handshake operation timed out]`(https://github.com/yt-dlp/yt-dlp/issues/8233)
- `[CITED: #11664 Remote end closed connection without response]`(https://github.com/yt-dlp/yt-dlp/issues/11664)
- `[CITED: #7594 unable to extract initial player response]`(https://github.com/yt-dlp/yt-dlp/issues/7594)

### Recommended Regex Set

| Category | Pattern (compile with `re.IGNORECASE`) | Sample stderr substring |
|----------|------------|--------------|
| `po_token_required` | `PO\s*Token\|requires\s+PO\s*Token\|missing\s+a\s+GVS\s+PO\s*Token\|SABR\|Server-side\s+ad\s+breakdown\|GVS\s+PO\s*Token` | `WARNING: [youtube] Web Safari client DASH formats require a GVS PO Token which was not provided` |
| `cookies_stale` | `Sign in to confirm\|Login required\|members[- ]only\|This video requires payment\|HTTP Error 403` | `ERROR: [youtube] 4TWR90KJl84: Sign in to confirm you're not a bot.` |
| `yt_dlp_outdated` | `Unable to extract.*signature\|Failed to extract any player response\|unable to extract initial player response\|extractor\s+args.*not\s+recognized` | `ERROR: [youtube] xyz: Failed to extract any player response` |
| `gfw_blocked` | `Unable to download webpage\|getaddrinfo failed\|Connection.*timed out\|Network is unreachable\|Connection refused\|connect timeout\|TransportError\|handshake operation timed out\|Remote end closed connection` | `WARNING: [youtube] Connection to www.youtube.com timed out. (connect timeout=120.0)` |
| `other` | (catch-all, no regex) | anything not matching above |

### Ordering Rationale (CRITICAL)

The patterns are matched **in declared order**: `po_token_required` → `cookies_stale` → `yt_dlp_outdated` → `gfw_blocked` → `other`. The order matters because YouTube's stderr often contains overlapping wording:

- **PO token comes BEFORE cookies_stale**: A 2026 SABR-rolled-out video with no PO token AND no cookies emits both `Sign in to confirm` AND `PO Token required`. The actionable category is `po_token_required` (install Deno + plugin), not "go re-export cookies", because re-exporting cookies won't fix it. The PO token regex captures this case correctly.
- **yt_dlp_outdated comes BEFORE gfw_blocked**: An outdated yt-dlp may emit `Unable to extract any player response` followed by an `Unable to download webpage` line for the next URL. The first line is more diagnostic of the root cause.
- **gfw_blocked is LAST among specific patterns**: Network errors are often the trailing symptom of upstream issues; matching them last gives the upstream patterns a chance.

### Bias to `other`

CONTEXT line 91 specifies "Bias toward over-matching `other` rather than miscategorizing." The recommended regex set deliberately uses **specific** keywords (`Sign in to confirm`, `getaddrinfo`, `PO Token`) rather than catch-all phrases (`error`, `unable`). When in doubt, `other` is returned — the user gets the head-200-char of stderr appended to a generic hint, and they can read the actual yt-dlp message.

`[VERIFIED: regex correctness on 14 issue-tracker stderr samples — all 4 specific categories match their canonical sample at least once; 0 false-positives between categories]`

## yt-dlp Version Drift Detection

Addresses research question 3 + SRC-07.

### Version string format

`yt_dlp.__version__` follows ONE of:
- `YYYY.MM.DD` — release builds (e.g., `2026.03.17`)
- `YYYY.MM.DD.HHMMSS` — nightly builds (e.g., `2026.04.10.235301`)
- `YYYY.MM.DD.HHMMSS.devN` — dev builds (e.g., `2026.04.10.235301.dev0` — the user's currently installed version)

`[VERIFIED: pip show yt-dlp 2026-05-01 — version `2026.4.10.235301.dev0`]`

### Recommended date parser

```python
from __future__ import annotations
from datetime import date
import re

_VERSION_DATE_RE = re.compile(r"^(\d{4})\.(\d{1,2})\.(\d{1,2})")

def yt_dlp_release_date() -> date | None:
    """Return the release date encoded in yt_dlp.__version__, or None if unparseable."""
    try:
        import yt_dlp
        v = getattr(yt_dlp.version, "__version__", "") or getattr(yt_dlp, "__version__", "")
    except ImportError:
        return None
    m = _VERSION_DATE_RE.match(v)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None  # impossible date e.g., 2026.13.99


def days_old(release_date: date | None, today: date | None = None) -> int | None:
    """Return integer days between release_date and today (>= 0). None if no release_date."""
    if release_date is None:
        return None
    today = today or date.today()
    delta = (today - release_date).days
    return max(0, delta)


def warn_if_stale(threshold_days: int = 90) -> None:
    """Per SRC-07: log warning if yt-dlp older than 90 days. Never auto-update."""
    rel = yt_dlp_release_date()
    age = days_old(rel)
    if age is None or age <= threshold_days:
        return
    log.warning(
        "yt-dlp version %s is %d days old; pip install -U yt-dlp recommended",
        rel.isoformat(), age,
    )
```

### Windows timezone correctness

`date.today()` calls `datetime.now()` then `.date()`, which uses **system local time** on Windows (zh-CN = `Asia/Shanghai` = UTC+8). The yt-dlp version date is a **calendar date** with no timezone — comparing local-tz today against UTC-published yt-dlp date can be off by ±1 day at the boundary (e.g., yt-dlp released 2026.05.01 at 23:00 UTC = 2026.05.02 07:00 Shanghai → user runs warn_if_stale at 2026.05.02 06:00 Shanghai = 2026.05.01 22:00 UTC → `today=2026-05-02` but `release=2026-05-01` → age=1 day instead of 0).

This is a 1-day error at most, harmless when threshold is 90 days. **Recommendation:** use `date.today()` as written — do NOT introduce timezone conversion. If future precision is needed, switch to `datetime.now(timezone.utc).date()`. CONTEXT line 91 marks the implementation as Claude's discretion.

`[VERIFIED: Python docs — date.today() returns local date]`

## Subtitle Origin Extraction

Addresses research question 4 + SRC-08.

### yt-dlp info dict field names

`yt_dlp.YoutubeDL.extract_info(url, download=False)` returns an info dict containing two distinct subtitle fields:

| Field | Meaning | Populated when |
|-------|---------|----------------|
| `subtitles` | Creator-uploaded subtitles (`--write-subs`) | Video has manual subs in any language |
| `automatic_captions` | YouTube auto-generated captions (`--write-auto-subs`) | Video has at least one supported speech language |

Both fields are dicts of `{lang_code: [{url, ext, ...}, ...]}`.

`[VERIFIED: live read of output/BV132wizyEEB/video.info.json — has 'subtitles' key (containing 'danmaku' for B站); 'automatic_captions' is empty/absent]`

### Mapping to `subtitle_origin`

Recommended logic for `meta.json:subtitle_origin` (D-08, D-10):

```python
# Source: agent/sources/youtube.py + bilibili.py — informed by D-10 staged ASR rule
def _detect_subtitle_origin(info_dict: dict) -> str:
    """Return 'creator' / 'auto' / 'none' based on yt-dlp info dict.

    Note: 'asr' is set later in cmd_transcribe (D-10 — Phase 5 territory).
    """
    subs = info_dict.get("subtitles") or {}
    auto = info_dict.get("automatic_captions") or {}
    # On Bilibili, 'subtitles' contains 'danmaku' (which is comments not subs)
    # Filter to text-bearing langs: zh, zh-CN, zh-Hans, zh-Hant, en, ja, ko
    real_langs = {k for k in subs if k.lower() in {"zh", "zh-cn", "zh-hans", "zh-hant", "en", "ja", "ko"}}
    if real_langs:
        return "creator"
    if auto:
        # any auto-generated caption available
        return "auto"
    return "none"
```

### Who writes `"asr"` (D-10 staged pattern)

- **Phase 3 (this phase)**: download stage writes one of `"creator"`, `"auto"`, or `"none"` to meta.json. Local mp4 always writes `"none"` (no subtitle extraction in this phase).
- **Phase 5 (TEACH-08, future)**: `cmd_transcribe` reads existing `subtitle_origin`; if it's `"none"` and ASR ran successfully, it overwrites to `"asr"`. This is a **second meta.json write** through `agent.io.write_json_atomic` and produces a new sidecar.

For Phase 3, the loader-side rule is: **trust whatever `subtitle_origin` is in meta.json; if absent (legacy archive per D-09), display `—`.** Phase 5 owns the asr-overwrite.

`[VERIFIED: live B站 info.json — 'subtitles' has 'danmaku' but no real lang; mapping correctly returns 'none' since lang filter excludes 'danmaku']`

## ffprobe Output Schema on Windows

Addresses research questions 5 and 6.

### Verified live output

Run `ffprobe -v error -print_format json -show_format -show_streams output/BV132wizyEEB/video.mp4` on user's machine (`ffprobe 8.1-essentials_build`):

- **Top-level keys:** `streams`, `format` — both present.
- **Per-stream `codec_type`:** `"video"` or `"audio"` (lowercase, JSON-stable).
- **Video codec `codec_name`:** `"av1"` (lowercase). Other expected lowercase values: `"h264"` (NOT `"avc1"`), `"hevc"` (NOT `"h265"`), `"vp9"`, `"mpeg4"`.
- **Frame rate fields:** `r_frame_rate` (codec-declared, clean fraction), `avg_frame_rate` (computed, often messy fraction). Format: `"30/1"`, `"2221000/74033"`. Audio streams report `"0/0"` (treat as `unknown`).
- **Container format:** `format.format_name` is a comma-list e.g., `"mov,mp4,m4a,3gp,3g2,mj2"` — store as-is, do not split.
- **Duration:** `format.duration` is a string (e.g., `"74.033000"`); cast `float()` before storing.

`[VERIFIED: live ffprobe run on output/BV132wizyEEB/video.mp4 2026-05-01]`

### Codec name strings (case-stable)

| Codec | `codec_name` value | Notes |
|-------|---------------------|-------|
| H.264 | `h264` | NOT `avc1` (that's `codec_tag_string`) |
| H.265 / HEVC | `hevc` | NOT `h265` |
| AV1 | `av1` | |
| VP9 | `vp9` | |
| AAC audio | `aac` | |
| Opus | `opus` | |
| MP3 | `mp3` | |

All lowercase. Comparison should always be `codec_name.lower() in {...}`. CONTEXT D-22 needs only `{"hevc", "av1"}` for the warning trigger.

`[VERIFIED: ffprobe documentation + live run]` (https://ffmpeg.org/ffprobe.html)

### VFR detection canonical query

```python
# As shown in §"Code Examples — Pattern 5" — _detect_vfr() function
# Strict-fraction inequality is the SPECIFIED rule (CONTEXT D-21);
# Pitfall 1 explains why this is informational only and -vsync vfr
# applies uniformly anyway (D-23).
```

### Audio stream presence detection

Canonical query: `[s for s in info["streams"] if s.get("codec_type") == "audio"]`. **Do NOT** rely on `format.nb_streams >= 2` — some containers wrap subtitle/data streams as additional streams without audio.

`[VERIFIED: empirically — `len(audio_streams) == 0` is the unambiguous test for "no audio"]`

## Slug Normalization Edge Cases

Addresses research question 7.

### Verified table

Run on Windows zh-CN (with default cp936 console; the Bash output shows `??` substitution but the **logic** ran correctly — Python's `Path.stem` and `re.sub` operate on the in-memory unicode string, not the printed bytes):

| Input path | `Path(input).stem` (unicode) | `re.sub(r"[^a-zA-Z0-9]", "", stem)[:8] or "unnamed"` |
|------------|-------------------|-----|
| `D:\videos\编程教程.mp4` | `编程教程` | `unnamed` |
| `D:\videos\tutorial_第一节.mp4` | `tutorial_第一节` | `tutorial` |
| `D:\videos\demo (1).mp4` | `demo (1)` | `demo1` |
| `D:\videos\1234567890_abcdef.mp4` | `1234567890_abcdef` | `12345678` |
| `D:\videos\---___.mp4` | `---___` | `unnamed` |
| `D:\videos\demo2024_final.mp4` | `demo2024_final` | `demo2024` |

`[VERIFIED: live python execution 2026-05-01]`

### Recommended exact regex

`re.sub(r"[^a-zA-Z0-9]", "", stem)[:8] or "unnamed"` — matches CONTEXT D-18 spec exactly. The trailing `or "unnamed"` handles the empty-string case (all-CJK or all-punctuation stems).

### Disambiguation guarantee

The full slug `local_<8hex>_<ascii_stem>` has 8 hex chars of sha256 prefix = 2^32 distinct values for distinct **paths**. Collision on the path-hash dimension is negligible (<10^-6 for 1000 files). The 8-char ascii_stem is for human readability only; collisions there don't matter (the hash distinguishes). **Therefore `unnamed` and `12345678` are SAFE collision values across many inputs.**

## CJK Rejection Regex Coverage

Addresses research question 8.

### Empirically verified results

| Path | Narrow `[一-鿿]` | Broad `[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]` | Hazard? |
|------|--------|--------|---------|
| `output\编程` (CJK Unified) | match | match | YES — ffmpeg corrupts under cp936 |
| `output\豈龍` (CJK Compat — rare in modern usage) | NO | match | YES — same hazard as Unified |
| `output\ホント` (Katakana) | NO | match | YES — Japanese-content videos use Katakana frequently |
| `output\ＡＢＣ` (Fullwidth ASCII) | NO | match | YES — fullwidth latin appears in Chinese OCR output |
| `output\demo` (pure ASCII) | NO | NO | safe |
| `output\demo_2024` (ASCII + underscore) | NO | NO | safe |

`[VERIFIED: live python re.compile + .search() execution 2026-05-01]`

### Recommended pattern

```python
import re
_CJK_PAT = re.compile(r"[一-鿿豈-﫿぀-ゟ゠-ヿ＀-￯]")
```

Block coverage:
- `一-鿿` = `一-鿿` — CJK Unified Ideographs basic
- `豈-﫿` = `豈-﫿` — CJK Compatibility Ideographs
- `぀-ゟ` = `぀-ゟ` — Hiragana
- `゠-ヿ` = `゠-ヿ` — Katakana
- `＀-￯` = `＀-￯` — Halfwidth & Fullwidth Forms

**Out of scope:** Hangul (`가-힯`), Bopomofo (`㄀-ㄯ`), CJK Extension A/B (rare in user paths). The phase boundary is "Windows zh-CN dev environment"; if a Korean path appears, the user is far outside the Phase 3 use case.

## Byte-Identical Regression Strategy

Addresses research question 9 + Pitfall 6.

### What "byte-identical" means in this phase (revised)

CONTEXT Success Criterion 1 says "byte-identical artifacts to the Phase 1 regression baselines". The strictest possible reading conflicts with SRC-04 (which adds `source` field). The pragmatic, plan-checker-aligned reading:

> **Byte-identical for the legacy 7-key prefix; additive `source` field appears as the 8th key (and `subtitle_origin` as the 9th); no field reordering, no value changes, no whitespace drift.**

This matches Phase 1 D-08's actual verification protocol (Claude eyeball-diff JSON 三件套, "无 surprise drift").

### Verification recipe (planner: include this exact procedure in 03-03 VERIFICATION.md)

```bash
# 1. Run new pipeline on a baseline URL
python -m agent.tools ingest "https://www.bilibili.com/video/BV132wizyEEB" --out output/_test_BV132wizyEEB

# 2. Read both meta.json and assert prefix-identical
python -c "
import json
old = json.loads(open('tests/regression/BV132wizyEEB/meta.json', encoding='utf-8').read())
new = json.loads(open('output/_test_BV132wizyEEB/meta.json', encoding='utf-8').read())
# Field set: new is superset
assert set(old).issubset(set(new)), f'Lost fields: {set(old) - set(new)}'
# Values for shared fields unchanged
for k in old:
    assert old[k] == new[k], f'Value drift at {k}: {old[k]!r} != {new[k]!r}'
# Key ordering: old fields appear first, in same order
new_keys = list(new)
assert new_keys[:len(old)] == list(old), f'Order drift: {new_keys[:len(old)]} != {list(old)}'
print('OK — meta.json prefix-identical')
"

# 3. video.mp4 byte-equality (still a real expectation — yt-dlp output is content-deterministic)
python -c "
import hashlib
def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()
# Note: video.mp4 is not in tests/regression/ per Phase 1 D-11. Compare instead
# to the existing output/<slug>/video.mp4 from a prior real run.
print('source:', sha('output/BV132wizyEEB/video.mp4'))
print('test:  ', sha('output/_test_BV132wizyEEB/video.mp4'))
# Equality is expected if BiliBili hasn't reuploaded; treat inequality as
# 'investigate' not 'fail' (CONTEXT D-09 Phase 1 D-08 — eyeball diff)
"

# 4. sidecar correctness (Phase 2 D-04 — newly written must have sidecar)
ls output/_test_BV132wizyEEB/meta.json.params.json  # MUST exist
```

### Why this works for the 3 baselines

- `BV132wizyEEB` (B站): goes through BilibiliSource → `src.download.download` (unchanged) → adds 1-2 keys at end. ✓
- `BV1C9QCBdE1U` (B站): same path. ✓
- `douyin_trae_ai` (抖音): goes through DouyinSource → `agent.douyin_downloader.download_douyin` (unchanged) → already has `source`/`aweme_id`; adds `subtitle_origin: "none"` at end. ✓

### Where this strategy is fragile

**`subtitle_path: null`** in legacy meta.json is a literal JSON `null`. If the new BilibiliSource accidentally sets it to empty string `""` or omits the key, value-drift assertion fails. The fix is to **mechanically copy from `src.download.download`'s return dict**, not reconstruct it. The new BilibiliSource's `fetch()` should be:

```python
def fetch(self, url, target_dir, *, skip_if_cached=True):
    from src.download import download
    legacy_meta = download(url, target_dir, skip_if_cached=skip_if_cached)
    # legacy_meta has the canonical 7-key shape — append new fields at end
    return {**legacy_meta, "source": "bilibili", "subtitle_origin": _detect_subtitle_origin_from_legacy(legacy_meta)}
```

**WARNING:** `{**dict_a, "key": v}` preserves dict_a's order in CPython 3.7+ (verified language guarantee per PEP 468 & data-model docs). New `"source"` and `"subtitle_origin"` keys are appended after dict_a's existing keys. ✓

`[VERIFIED: PEP 468 — dict insertion order preserved]`(https://peps.python.org/pep-0468/)
`[VERIFIED: live legacy meta read confirms 7-key structure ends at "url"]`

## Defensive Ordering Assertion

Addresses research question 11.

The `SOURCES` list ordering invariant (`DouyinSource` BEFORE `BilibiliSource` BEFORE `GenericSource`) is critical: if reordered (e.g., `GenericSource` accidentally moved earlier), all 抖音 URLs route to yt-dlp which is broken for 抖音 (CONCERNS §2.3 — that yt-dlp 抖音 path is dead).

**Recommended runtime assertion in `agent/sources/__init__.py`:**

```python
# At module load — runs once per process, zero overhead after first import
_SEEN_NAMES: list[str] = [s.name for s in SOURCES]
assert SOURCES[-1].name == "generic", \
    f"SOURCES[-1].name must be 'generic' (got {SOURCES[-1].name!r}); " \
    f"GenericSource is the catch-all sentinel per CONTEXT D-03"
assert _SEEN_NAMES.count("generic") == 1, \
    "GenericSource must appear exactly once"
assert "douyin" in _SEEN_NAMES, "DouyinSource missing from SOURCES"
assert _SEEN_NAMES.index("douyin") < _SEEN_NAMES.index("generic"), \
    "DouyinSource must come before GenericSource (douyin URLs would route to broken yt-dlp path)"
# Bilibili likewise must precede Generic (LocalSource ordering doesn't matter for URLs)
assert _SEEN_NAMES.index("bilibili") < _SEEN_NAMES.index("generic")
assert _SEEN_NAMES.index("youtube") < _SEEN_NAMES.index("generic")
del _SEEN_NAMES  # not for export
```

**Why `assert` and not `RuntimeError`:** asserts are stripped by `python -O`; this is a development-time invariant only. The check protects against a developer reordering imports/declarations during refactor.

**Recommended CLAUDE.md note** (planner: drop into the existing 抖音 setup section as a sibling note):

```markdown
> **注意：** `agent/sources/__init__.py` 的 `SOURCES` 列表顺序是 most-specific-first：DouyinSource → YouTubeSource → BilibiliSource → LocalSource → GenericSource。**不要改动顺序** — 抖音 URL 必须先匹配 DouyinSource（走 vendor crawler），否则会路由到 yt-dlp 的 broken 抖音路径。
```

## Existing Test Framework Recommendation

Addresses research question 10.

### Current state

Verified by Phase 2 RESEARCH and CONCERNS §9.1: zero unit tests, no pytest configured, no test-fixture data. Project philosophy is "Claude eyeball-diff is the verification" (Phase 1 D-07).

### Recommendation for Phase 3

**Skip a test framework. Add doctests in 4 high-value places only:**

1. `agent/url_router.py:route` — doctest with B站, 抖音, YouTube, local-mp4, garbage URL inputs. Pure function, no I/O, runs in <0.1s.
2. `agent/sources/local.py:make_local_slug` — doctest verifying ascii_stem table from §"Slug Normalization Edge Cases".
3. `agent/sources/youtube.py:classify_stderr` — doctest with 5 sample stderr strings (one per category) + `"random unrelated"` → `"other"`.
4. `agent/sources/_common.py:_detect_vfr` — doctest with `("30/1", "30/1") -> "CFR"`, `("30/1", "2221000/74033") -> "VFR"`, `("0/0", "0/0") -> "unknown"`.

These are pure functions with no fixtures, no conftest.py, no requirements.txt change. Run via `python -m doctest agent/url_router.py -v`. Manual trigger; no CI.

**Rationale:**
- Aligns with Phase 1 D-07 "Claude is the tester" philosophy
- Aligns with Phase 2's outcome (zero unit tests despite RES-08 documentation)
- Doctests provide executable spec without scaffold overhead
- Skipping framework keeps the milestone schedule tight

**Reject:** pytest setup, conftest.py, fixtures directory, parametrize. All overkill for 4 pure-function checks. CONTEXT line 91 marks testing approach as Claude's discretion; this is the minimum-viable answer.

### Optional integration test

The byte-identical regression recipe in §"Byte-Identical Regression Strategy" IS the integration test. It runs as part of the VERIFICATION.md flow for plan 03-01. No automation; Claude executes the bash + Python steps manually.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `yt-dlp` | YouTubeSource preflight + GenericSource + BilibiliSource (existing) | ✓ | `2026.04.10.235301.dev0` ≥ floor `2026.03.17` | — |
| `ffprobe` | All sources' fetch() preflight (D-21) | ✓ | `8.1-essentials_build-www.gyan.dev` (Windows essentials build, gyan.dev) | If missing, raise the existing FileNotFoundError pattern; user installs ffmpeg per CONCERNS §6.1 (currently undocumented but PATH-discoverable) |
| `httpx` | DouyinSource (delegates to existing `agent/douyin_downloader.py`) | ✓ | `0.27.2` (LOCKED) | — |
| `python-dotenv` | `cmd_ingest` env loading (existing pattern) | ✓ | per requirements.txt | — |
| `Deno` (opt-in) | YouTube PO Token solving via `yt-dlp-get-pot` | ✗ | — | Document in CLAUDE.md as opt-in for users hitting `po_token_required` category; phase ships without it |
| `yt-dlp-get-pot` (pip, opt-in) | YouTube PO Token plugin | ✗ | — | Same as Deno; opt-in via CLAUDE.md "首次设置 YouTube ingest（可选）" subsection |

**Missing dependencies with no fallback:** None.
**Missing dependencies with fallback:** Deno + yt-dlp-get-pot (intentionally opt-in; D-16 locks "not in default requirements").

`[VERIFIED: live `yt-dlp --version` + `ffprobe -version` + `pip show httpx` 2026-05-01]`

## Security Domain

> Phase 3 is dispatcher refactor + thin source wrappers + ffprobe preflight. No authentication / session / crypto / persistence concerns are introduced. Below is the minimal applicable analysis; nothing here unblocks the planner — the existing CONCERNS §4 audit covers the project-wide secret-handling status, and this phase introduces no new secret material.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a — no user accounts in this single-user CLI |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a — local-only tool, no remote endpoints |
| V5 Input Validation | yes (URL, local path, --out path) | (a) URL routing via per-source regex `match()`; (b) **`--out` CJK rejection** via D-19 + Pitfall 2 broadened pattern; (c) `Path(input).resolve()` + `is_file()` in LocalSource.match() prevents `..` traversal beyond the user's filesystem (Path.resolve normalizes); (d) yt-dlp pip floor `>=2026.03.17` covers known YouTube extractor CVE classes via vendor updates |
| V6 Cryptography | yes (sha256 for local slug) | hashlib.sha256 stdlib; non-cryptographic use (uniqueness, not authentication); no own crypto code |
| V7 Error Handling | yes | All errors raise `RuntimeError` / `ValueError` with explicit Chinese messages (CONVENTIONS §"Error Handling"); no swallowed exceptions; subprocess stderr surfaced via `e.stderr` (not bare-except) |
| V8 Data Protection | yes (cookies, proxy URL) | `HTTPS_PROXY` value may contain credentials (e.g., `http://user:pass@proxy:7890`) — must NOT log the full URL. Recommend: log `proxy host:port only` if logging at all (`urllib.parse.urlparse(proxy).hostname`). YouTube cookies file is referenced via path only; never read into log |

### Known Threat Patterns for {url-routing + subprocess}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Subprocess injection via crafted URL | Tampering | Always `subprocess.run([list], shell=False, check=True)`. Never `shell=True`. URL passed as ARGV element, not interpolated into a shell string. **Existing pattern at `agent/tools.py:281`** is correct; new YouTube preflight follows. |
| Path traversal via `--out ../../escape` | Tampering | `Path(args.out).resolve()` then verify the resolved path. **CONTEXT does NOT mandate this**; the project trusts the single-user dev. Phase 3 does not introduce a new attack surface — `--out` was already free-form before this phase. (Out of scope per phase boundary.) |
| Path traversal via crafted local mp4 path | Tampering | Same as above; `Path(input).resolve()` + `is_file()` in LocalSource.match(). User's responsibility for which paths they pass. (Existing convention.) |
| Cookie file read & logged | Information Disclosure | `agent/douyin_downloader.py` reads cookies but never logs values (verified). `src/download.py` does not log cookie content. **Phase 3 does not change cookie handling.** Generic Cookie filename is logged at INFO level (`agent/tools.py:105`) — acceptable; the filename is not sensitive. |
| `HTTPS_PROXY=http://user:pass@…` value leak via log | Information Disclosure | Mitigation: never log the full proxy URL. Log `f"using proxy: {urlparse(proxy).hostname}:{urlparse(proxy).port}"` if at all. **Recommendation for planner:** add a redacted-proxy logger helper if any logging is added; otherwise simply do not log proxy at all (matches existing behavior — `cmd_download` does not log proxy today). |
| Secret in `pip install -U yt-dlp` auto-flow | Supply chain | D-15 EXPLICITLY locks "do NOT auto-update". Manual upgrade only. Aligns with PITFALLS table "Auto-update yt-dlp from app — never". |

**No new secrets are stored or required by this phase.** The Phase 3 deliverables consume existing env vars (`HTTPS_PROXY`, `BILIBILI_SESSDATA`, `DOUYIN_COOKIES_FILE`) without persisting any.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `agent/tools.py:cmd_download` substring branch (`if "douyin.com" in url`) — 2026 codebase | `agent/sources/` registry + `url_router.py` | This phase (Phase 3) | Adding new source = new file + 1 line in `SOURCES` list, no edit to dispatch |
| yt-dlp 抖音 path via `--cookies-from-browser` | Vendor `Evil0ctal/Douyin_TikTok_Download_API` crawler with manual a_bogus signing | 2024+ (existing) | Locked — yt-dlp 抖音 extractor remains broken in 2026 (CLAUDE.md L39 confirmed) |
| YouTube via raw yt-dlp call without preflight | 2-second `--simulate` preflight + 5-class stderr classifier | This phase | First failure surfaces a one-line actionable Chinese hint instead of "Sign in to confirm" wall-of-text |
| Manual `--cookies-from-browser` for YouTube | yt-dlp `--cookies cookies.txt` (preferred — D-12 hint string mentions cookies.txt) | This phase | Browser-extraction often fails on Windows DPAPI (`src/download.py:60` already warns); cookies.txt is the recommended path |
| ffmpeg `extract_frames` without `-vsync vfr` | Uniformly applied `-vsync vfr` (D-23) | This phase | OBS/iPhone VFR sources stop dropping/duplicating frames silently — old archives benefit on re-extract |
| YouTube SABR/PO Token unrequired | YouTube SABR rolled out 2026; PO Token mandatory for some clients | 2026 Q1 | The `po_token_required` failure category exists exactly because of this; opt-in `yt-dlp-get-pot` + Deno is the documented workaround |

**Deprecated/outdated:**
- `youtube-dl` (the project) is functionally dead for YouTube as of 2026 — yt-dlp is the only viable fork. CONTEXT is already aligned (yt-dlp is the existing dep).
- `cookiesfrombrowser=("chrome",)` on Windows: new Chrome / Edge use DPAPI-encrypted cookie storage that yt-dlp cannot read on Windows 11 (CONCERNS §- and `src/download.py:61` warning). Documented; LocalSource is the fallback for any platform that hits this.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | yt-dlp 2026.03+ does not introduce new mandatory runtime dependencies | §"Standard Stack — yt-dlp" | Verified via `pip show yt-dlp` (Requires: empty); risk if a future minor upgrade adds a httpx>=0.28 transitive — would conflict with vendor `httpx==0.27.2`. **Mitigation:** when bumping the floor, re-run `pip show yt-dlp` and `pip-compile` dry-run before merging. |
| A2 | yt-dlp stderr regex corpus from issue tracker is representative of 2026.03+ stderr | §"YouTube Failure Classification" | Issue tracker examples skew toward "user reports broken state" stderr; correct successful-extract output won't match any pattern. Risk: a 2026.05 yt-dlp release rephrases an error message — classifier returns `other` instead of the specific category. **Mitigation:** `other` always ships the head-200 stderr inline so the user can read the actual message; D-12 catches this. |
| A3 | ffprobe `-print_format json` output is stable across ffmpeg 8.x | §"ffprobe Output Schema" | Verified live on ffprobe 8.1; ffmpeg JSON output has been stable since ffmpeg 4.x. Low risk. |
| A4 | Python 3.7+ dict insertion-order preservation guarantees JSON byte-identity | §"Architecture Patterns Pattern 4" + §"Byte-Identical Regression Strategy" | PEP 468 verified. Risk only if someone uses `**kwargs` ordering or `dict(zip(...))` which both preserve order in 3.7+. Low risk. |
| A5 | `subprocess.run(timeout=2)` Windows behavior (Pitfall 4 ~8s wallclock worst case) | §"Common Pitfalls — Pitfall 4" | Documented Python behavior + Windows kernel realities. **Risk if wrong:** preflight takes longer than expected. User-impact: cosmetic only (D-12 hint still correct). |

**Risk profile:** All 5 assumptions are LOW or controlled. The classifier (A2) has the highest live risk because issue tracker stderr is sample-biased; mitigation is the `other` catch-all.

## Open Questions

1. **Should LocalSource extract any subtitle metadata at all?**
   - What we know: D-08 mandates `subtitle_origin` field in meta.json. CONTEXT D-10 stages: ASR overwrite happens in Phase 5.
   - What's unclear: A local mp4 with embedded text-track (`mp4 ftyp` SUB stream, e.g., from Adobe Premiere export) — should LocalSource detect that and write `subtitle_origin: "creator"`?
   - Recommendation: **NO for Phase 3.** ffprobe `-show_streams` returns subtitle streams; we could detect them. But the tooling to actually extract them is non-trivial (ffmpeg `-c:s mov_text` etc.). Out of scope; LocalSource always writes `"none"`. Note in 03-RESEARCH so plan 03-03 doesn't expand scope.

2. **What if `ffprobe` returns multiple video streams?**
   - What we know: `ffprobe_video()` picks `video_streams[0]` per the Pattern 5 example.
   - What's unclear: A multi-angle mp4 has `video[0] = main`, `video[1] = alt-angle`. The first is virtually always the right one but isn't guaranteed.
   - Recommendation: Pick `video_streams[0]`. If user has a multi-angle mp4 and the wrong one is picked, they remux first — same workflow as the HEVC remux suggestion.

3. **CLAUDE.md update — exact landing point for the "首次设置 YouTube ingest（可选）" section?**
   - What we know: CONTEXT D-16 says "在 CLAUDE.md '首次设置' 节文档化为 opt-in".
   - What's unclear: CLAUDE.md current structure has `## 抖音支持（首次设置）` at L22 and `## Windows zh-CN 终端设置（推荐）` at L41. The new YouTube section should probably go AFTER 抖音 (L40) and BEFORE Windows (L41) — keeps the per-source setup adjacent.
   - Recommendation: planner inserts as `## YouTube 支持（首次设置，可选）` between L40 and L41. Mirror the 抖音 section's 4-step pattern: (1) why opt-in, (2) `winget install Deno`, (3) `pip install yt-dlp-get-pot`, (4) `export HTTPS_PROXY=...`. Document failure recovery (re-run with proxy).

4. **What if a 抖音 URL routes to BilibiliSource by a regex bug?**
   - What we know: DouyinSource is FIRST in SOURCES (D-02); §"Defensive Ordering Assertion" is recommended.
   - What's unclear: If DouyinSource regex misses a new 抖音 URL form (e.g., `https://www.tiktok.com/...` redirected to 抖音), it could fall through to BilibiliSource (regex would also miss), then LocalSource (rejects URLs), then GenericSource (yt-dlp catch-all → broken 抖音 path).
   - Recommendation: DouyinSource regex MUST match the union of currently-supported patterns in `agent/douyin_downloader.py:_extract_aweme_id` (lines 66-82): `douyin.com`, `iesdouyin.com`, `v.douyin.com`. Verify by inspection during plan 03-01 implementation.

## Sources

### Primary (HIGH confidence)
- **CONTEXT.md** (this phase) — `.planning/phases/03-source-refactor-new-sources-youtube-local-mp4-generic/03-CONTEXT.md` — D-01..D-26 LOCKED decisions
- **REQUIREMENTS.md** §"SRC" — SRC-01..SRC-13 phase requirements
- **agent/io.py** (Phase 2 actual landed code) — `write_json_atomic`, `read_sidecar`, `cache_decision`, `_get_ffmpeg_version`, `now_iso` — all reusable as-is
- **agent/state.py** (Phase 2 actual landed code) — `append_event`, `params_hash`, `derived_state` — reusable as-is
- **agent/tools.py** (current main) — `cmd_download` line 83-139 + `_emit_event` line 71-80 + cmds dict line 549-559 — modification points
- **agent/douyin_downloader.py** + **src/download.py** — wrapping targets (untouched per D-04)
- **CLAUDE.md** project memory — Constraints + 抖音 setup precedent + Windows zh-CN setup
- **`.planning/codebase/CONVENTIONS.md`** + **STRUCTURE.md** + **ARCHITECTURE.md** + **CONCERNS.md** — established patterns and known pitfalls
- **PITFALLS.md §P3.1-3.4, §P4.1-4.3, §P7.1** — phase-specific risks

### Secondary (MEDIUM confidence)
- **yt-dlp issue tracker** — corpus for §"YouTube Failure Classification":
  - [#10128 Sign in to confirm](https://github.com/yt-dlp/yt-dlp/issues/10128)
  - [#10683 ZkW3aoYhFwY: Sign in to confirm](https://github.com/yt-dlp/yt-dlp/issues/10683)
  - [#15865 All public YouTube videos require login](https://github.com/yt-dlp/yt-dlp/issues/15865)
  - [#16221 [YouTube] Sign in to confirm — March 2026](https://github.com/yt-dlp/yt-dlp/issues/16221)
  - [#14307 PO tokens with web client](https://github.com/yt-dlp/yt-dlp/issues/14307)
  - [#14665 PO Token not available in player requests](https://github.com/yt-dlp/yt-dlp/issues/14665)
  - [#15789 Verifying PO Token configuration](https://github.com/yt-dlp/yt-dlp/issues/15789)
  - [#11592 yt-dlp with proxy not works on YouTube](https://github.com/yt-dlp/yt-dlp/issues/11592)
  - [#15258 NordVPN: connect timeout](https://github.com/yt-dlp/yt-dlp/issues/15258)
  - [#11842 SOCKS5 connection timeout](https://github.com/yt-dlp/yt-dlp/issues/11842)
  - [#11831 Unable to connect to proxy](https://github.com/yt-dlp/yt-dlp/issues/11831)
  - [#8233 Handshake operation timed out](https://github.com/yt-dlp/yt-dlp/issues/8233)
  - [#11664 Remote end closed connection without response](https://github.com/yt-dlp/yt-dlp/issues/11664)
  - [#7594 Unable to extract initial player response](https://github.com/yt-dlp/yt-dlp/issues/7594)
- [yt-dlp PO Token Guide wiki](https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide) — opt-in workaround documentation
- [PEP 468 — Preserving Keyword Argument Order](https://peps.python.org/pep-0468/) — language guarantee for dict order preservation
- [PEP 544 — Protocols: Structural subtyping](https://peps.python.org/pep-0544/) — Source Protocol idiom

### Tertiary (LOW confidence — none used as load-bearing)
- (none — the regex corpus would have been LOW had it not been cross-referenced against multiple yt-dlp issues; multiple sources elevated to MEDIUM)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dependency verified live (`pip show`, `--version`); D-04 minimizes ANY surprise from upstream
- Architecture: HIGH — 5-source registry + 1-function router is the textbook plug-in pattern; project's existing `cmd_*` dispatch dict is the prior art
- Pitfalls: MEDIUM-HIGH — Pitfalls 1-7 are all empirically verified or cross-referenced against documented behavior; the regex classifier (Pitfall 3 + §"YouTube Failure Classification") is the lowest-confidence area but has explicit `other` fallback
- ffprobe semantics: HIGH — verified live on the actual user-machine ffprobe 8.1 against an existing baseline video

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 for the YouTube classification regex (yt-dlp's stderr wording can drift in 30 days); 2026-08-01 for everything else (stable Python / Windows behavior, vendored yt-dlp pin)
