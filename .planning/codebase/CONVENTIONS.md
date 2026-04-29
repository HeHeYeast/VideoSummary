# Conventions

Generated 2026-04-29 from a structured codebase audit (focus: quality).

## Language & Version

**Language:** Python only (no JS/TS in app code). Sole language across `src/` and `agent/`.

**Version target:** Python 3.13 primary; tolerant of 3.11+.
- `src/asr.py:3-4` explicitly: "用 faster-whisper 因为它支持 Python 3.13. 若想换 SenseVoice/FunASR 需要 Python 3.11 venv".
- No `.python-version`, `pyproject.toml`, or `setup.py` pinning the version.
- `COST_CONTROL.md:272` references the same Python 3.11/3.13 split.

**Module layout:** Two flat application packages
- `src/` — v1 cloud-pipeline era (`pipeline.py`, `cli.py`, `summarize.py`, `vision.py`, `frames.py`, `asr.py`, `download.py`, `budget.py`, `llm_client.py`)
- `agent/` — v2 offline data layer + Claude Code tools (`tools.py`, `prepare.py`, `asr_v2.py`, `frames_v2.py`, `pass1_classify.py`, `frame_store.py`, `embed.py`, `douyin_downloader.py`, `smoke_test_fc.py`)
- `__init__.py` files in both packages are empty (1 line)
- `vendor/douyin_api/` — third-party fork (Evil0ctal 抖音 crawler), treat as read-only
- `config/` — YAML budget configs (`budget_test.yaml`, `budget_prod.yaml`)

## Formatting & Linting

**No tooling configured.**
- No `pyproject.toml`, `setup.cfg`, `.flake8`, `.editorconfig`, `.pre-commit-config.yaml`, `ruff.toml`.
- No `black`, `ruff`, `isort`, `mypy` in `requirements.txt`.
- No CI lint workflow (the `.github/workflows/` files belong to the vendored repo, ignore them).

**De-facto style** (uniformly applied):
- Indent: 4 spaces, no tabs.
- Line width: ~88-100 chars, soft-wrapped at logical boundaries.
- Trailing commas in multi-line literals (`src/budget.py:28-42` PRICE_TABLE, `agent/frames_v2.py:36-44` VOICE_ANCHOR_PATTERNS).
- Hanging indents for long argument lists (`src/asr.py:43-47`, `agent/douyin_downloader.py:184-189`).
- String quotes: double quotes everywhere; single quotes only nested.

## Naming

**Files / modules:** `snake_case.py`. Sibling v2 files suffix `_v2`: `src/asr.py` ↔ `agent/asr_v2.py`, `src/frames.py` ↔ `agent/frames_v2.py`. Pass-numbered modules: `agent/pass1_classify.py`.

**Functions:** `snake_case()`. Public has no leading underscore; module-private use `_` prefix:
- Public: `download()`, `transcribe()`, `aggregate_paragraphs()`, `extract_keyframes()`, `extract_smart_keyframes()`, `compute_embeddings()`.
- Private: `_cookies_txt_to_header`, `_extract_aweme_id`, `_compress_transcript_for_outline`, `_count_tokens`, `_messages_tokens`, `_parse_classification`, `_flush` (nested).
- CLI handlers prefix `cmd_`: `cmd_download`, `cmd_transcribe`, `cmd_aggregate`, `cmd_extract_frames`, `cmd_list_frames`, `cmd_cleanup_frames`, `cmd_classify_frame`, `cmd_ocr_frame` (`agent/tools.py:35-188`).

**CLI subcommands:** lowercase snake_case matching the `cmd_*` suffix; wired via dict literal in `agent/tools.py:241-250`:
```python
cmds = {"download": cmd_download, "transcribe": cmd_transcribe, ...}
cmds[args.command](args)
```

**Classes:** `PascalCase` — `BudgetGuard`, `LLMClient`, `Segment`, `Frame`, `Paragraph`, `CandidateFrame`, `FrameRecord`, `FrameStore`, `FrameDescription`, `FrameClassification`, `BudgetExceeded`.

**Constants:** `UPPER_SNAKE_CASE` at module top:
- `CNY_PER_USD`, `PRICE_TABLE`, `ASR_PRICE_PER_1M`, `GROUP_MULTIPLIER` in `src/budget.py`.
- `HALLUCINATION_PATTERNS` / `_HALL_RE` in `src/asr.py`, `VOICE_ANCHOR_PATTERNS` / `_ANCHOR_RE` in `agent/frames_v2.py`.
- Prompt strings: `CLASSIFY_PROMPT` (`agent/pass1_classify.py:20`), `OUTLINE_PROMPT` (`src/summarize.py:33`), `VISION_PROMPT` (`src/vision.py:14`), `DETAIL_PROMPTS` dict (`agent/frame_store.py:33`).
- Compiled regexes prefixed `_` to mark private: `_HALL_RE`, `_ANCHOR_RE`, `_SENTENCE_END`, `_VENDOR`, `_CONFIG`.

**Output dir id:** B站 BV id used directly as folder name. Extracted via `args.url.rstrip("/").split("/")[-1].split("?")[0]` (`src/cli.py:49`, `agent/prepare.py:68`). About 58 such dirs in `output/`. For 抖音 the meta records `aweme_id` / `source: "douyin"` but the folder name is user-supplied via `--out`.

## Type Hints

**Required idiom:** `from __future__ import annotations` at the top of every application module. Verified present in all 17 application files (8 in `agent/`, 9 in `src/`).

**Coverage:** Public function signatures consistently typed; locals usually untyped.
- Path args canonical signature is `str | Path`, immediately coerced via `Path(x)` on entry — see `src/download.py:14`, `agent/douyin_downloader.py:128-133`, `agent/frame_store.py:81`.
- PEP-604 union: `str | None`, **not** `Optional[str]` (one stale `Optional` import in `src/budget.py:18` is unused).
- Built-in generics: `list[Frame]`, `dict[str, float]`, `tuple[str, bool, str]` — never `typing.List/Dict/Tuple`.

**Dataclasses for data containers** (preferred over `TypedDict` or plain dicts). 8 modules use `@dataclass`:
- `src/asr.py:34` `Segment`, `src/frames.py:19` `Frame`, `src/vision.py:25` `FrameDescription`, `src/budget.py:64` `BudgetGuard`.
- `agent/asr_v2.py:15` `Paragraph`, `agent/frames_v2.py:23` `CandidateFrame`, `agent/frame_store.py:62` `FrameRecord`, `agent/pass1_classify.py:38` `FrameClassification`.
- Mutable defaults via `field(default_factory=...)`: `Paragraph.seg_indices` (`agent/asr_v2.py:21`), `BudgetGuard.spent_per_stage` (`src/budget.py:75`), `FrameRecord.consumed_by` (`agent/frame_store.py:75`).
- Serialize via `dataclasses.asdict()`: `[asdict(s) for s in segs]` is the canonical JSON conversion (`agent/tools.py:80`, `src/pipeline.py:58`, `agent/prepare.py:101`).
- Reload via splat: `Segment(**d)` (`src/pipeline.py:47`); `FrameStore._load` defensively filters keys against `__dataclass_fields__` (`agent/frame_store.py:90`).

## Imports & Module Boundaries

**Order** (consistent though not isort-enforced):
1. `from __future__ import annotations`
2. stdlib (`argparse`, `json`, `logging`, `os`, `re`, `subprocess`, `sys`, `pathlib`, `dataclasses`)
3. blank line
4. third-party (`yaml`, `tiktoken`, `openai`, `httpx`, `imagehash`, `PIL`, `numpy`, `dotenv`)
5. blank line
6. local: relative in `src/` (`from .budget import ...`), absolute in `agent/` (`from src.budget import ...`, `from agent.asr_v2 import ...`).

**`sys.path` bootstrap pattern** in `agent/tools.py` cmd handlers and `agent/prepare.py:51`:
```python
sys.path.insert(0, str(Path(__file__).parent.parent))
```
Inserted before importing `src.*`. Repeated at `agent/tools.py:37,64,91,152,172`.

**Lazy / deferred imports** for heavy or optional dependencies:
- `from faster_whisper import WhisperModel` inside `transcribe()` (`src/asr.py:60`) avoids slow startup.
- `open_clip` wrapped in `try/except ImportError` with `_HAS_CLIP` flag and graceful fallback (`agent/embed.py:23-30`); model loaded lazily in `_ensure_model()` (`agent/embed.py:33-53`).
- vendor `crawlers.douyin.web.web_crawler` imported inside `_fetch_video_detail()` after `sys.path` patch (`agent/douyin_downloader.py:86-90`).

## CLI Pattern (argparse subcommands)

**Three CLI entry points:**
- `agent/tools.py:191-251` — multi-subcommand CLI (canonical).
- `src/cli.py` — single-command end-to-end pipeline.
- `agent/prepare.py:30-213` — single-command v2 offline data prep.

**Conventions:**
- Positional arg first (`url`, `video_path`, `segs_json`, `frame_path`, `dir`).
- Output dirs always via required `--out`: `p.add_argument("--out", required=True)`.
- `--lower-with-dashes` exposed as `args.lower_with_dashes` (`--skip-download`, `--skip-clip`, `--test-duration`, `--vision-model`).
- Booleans via `action="store_true"`: `--force`, `--skip-download`, `--skip-clip`.
- Variadic via `nargs="*"`: `--keep` (`agent/tools.py:224`).
- `type=float` / `type=int` explicit for numerics.
- Sentinel `0` means "no upper bound" instead of `None`: `--end` defaults to `0` meaning "to end of video" (`agent/tools.py:217`).
- Dispatch via dict, not `if/elif` (`agent/tools.py:241-250`).
- `if not args.command: parser.print_help(); sys.exit(1)` (`agent/tools.py:237-239`).
- `load_dotenv()` is the first call in every `main()` (`agent/tools.py:192`, `src/cli.py:20`, `agent/prepare.py:31`).

## Logging

**Standard module-level logger** (in 15/17 files):
```python
import logging
log = logging.getLogger(__name__)
```
Named `log`, not `logger`.

**`basicConfig` only at entry points**, never in libraries:
- `agent/tools.py:31` (top-level): `format="%(levelname)s | %(message)s"` — terse for tool output.
- `src/cli.py:41-44`: `format="%(asctime)s %(levelname)s %(name)s | %(message)s"`.
- `agent/prepare.py:44-47`: same verbose form.

**Lazy formatting** universally: `log.info("foo: %s", x)`, never `log.info(f"foo: {x}")`. No `log.debug` calls anywhere — debug info goes through `print()` in CLI handlers.

**`print()` is for user-facing CLI output**, separate from logging — emits JSON / counts for piping (`agent/tools.py:59,83,98,121-126`). On Windows, `ensure_ascii=True` is used for terminal output to avoid GBK crash on emoji titles (`agent/tools.py:59`, with explanatory comment).

## Comments & Docstrings

**Language:** Chinese for everything — every module/function/class docstring and inline comment is Chinese. English appears only in identifiers, code literals, and English keywords inside prompt templates.

**Module docstrings:** Required, multi-line, often referencing `AGENT_DESIGN.md` section number. See `agent/asr_v2.py:1-7`, `agent/frames_v2.py:1-7`, `agent/frame_store.py:1-19`, `agent/pass1_classify.py:1-9`. Frequently include a `用法:` block with concrete CLI example (`agent/prepare.py:12-16`, `agent/douyin_downloader.py:6-10`).

**Function docstrings:** One-line for trivial; longer functions get an `Args:` / `Returns:` block in informal Google style (no types repeated — types live in the signature). Examples: `aggregate_paragraphs` (`agent/asr_v2.py:33-42`), `download_douyin` (`agent/douyin_downloader.py:134-143`), `compute_embeddings` (`agent/embed.py:60-65`).

**Inline comments justify *why*, not what** — particularly dense in `src/budget.py` (price table sourcing, magic multipliers) and `src/asr.py` (anti-hallucination rationale).

**Decorative section dividers** in long files:
- `# ── 核心命令 (本地, ¥0) ──` (`agent/tools.py:196`).
- `# ────────────────────────────────────────────────────────────` then `# Stage 1: Outline` (`src/summarize.py:29-31`).
- `# ═══════════════════════════════════════════════════════════` for stage banners (`agent/prepare.py:72-74`).

## Error Handling

**Subprocess (ffmpeg / yt-dlp) — fail loud:**
- Canonical: `subprocess.run(cmd, check=True, capture_output=True)` — at `src/asr.py:48`, `src/frames.py:36`, `agent/frames_v2.py:59`, `agent/tools.py:118`.
- `check=True` lets `CalledProcessError` propagate; `capture_output=True` keeps stdout/stderr off the user terminal until something goes wrong.
- No retry around ffmpeg.

**`yt-dlp`:** exceptions propagate from `download()` (`src/download.py:61-62`). Pipeline reports `RuntimeError("下载失败")` only when `meta["video_path"]` is None (`src/pipeline.py:39`).

**External HTTP / API — narrow `try/except Exception` with warning + degraded path:**
- httpx redirect: `agent/douyin_downloader.py:75-80` (warn + return `None`).
- pHash on bad image: `src/frames.py:51-55`, `agent/frames_v2.py:73-77` (warn + skip).
- CLIP image preprocess: `agent/embed.py:78-84` (warn + zero-vector fallback).
- Vision API: `src/vision.py:51-52`, `agent/pass1_classify.py:113-114` (warn + skip frame, do **not** abort batch).

**Custom domain exception:** `BudgetExceeded(RuntimeError)` (`src/budget.py:60`)
- Raised by `BudgetGuard.precheck()` when stage/total caps are exceeded.
- Boundary catch: `src/cli.py:60-63` prints budget report and `sys.exit(2)`.
- Inner catches abort gracefully: `agent/pass1_classify.py:102-112` (mark remaining frames default), `src/vision.py:48-50` (`break` loop).

**Generic `RuntimeError` for invariant violations** with informative messages:
- `agent/douyin_downloader.py:165` `无法从 URL 提取 aweme_id: {url}`
- `agent/douyin_downloader.py:171` `获取视频详情失败 (空响应)`
- `src/llm_client.py:116` `环境变量 VE_KEY_CHEAP 未设置`

**`--force` flag pattern:** Only on `transcribe` (`agent/tools.py:205`). Idiom:
```python
if segs_file.exists() and not args.force:
    print(f"cached: {segs_file}")
    segs_data = json.loads(segs_file.read_text(encoding="utf-8"))
else:
    segs = transcribe(...)
    segs_file.write_text(...)
```
(`agent/tools.py:75-81`)

**Cookie-expiry recovery:** No automatic retry — design is *fail loud, ask the human*. `agent/douyin_downloader.py` patches the vendor `config.yaml` Cookie line each call (`_patch_config_cookie`, lines 46-61); when cookies are stale, `crawler.fetch_one_video` returns empty and we `raise RuntimeError("获取视频详情失败 (空响应)")` (line 171). `CLAUDE.md` documents the manual fix: re-export `www.douyin.com_cookies.txt`.

**Retry policy:** `OpenAI(..., max_retries=1)` (`src/llm_client.py:51-52`) — minimal because budget guard accounts for each call. The outline parser (`src/summarize.py:93-116`) is the only place with custom retry logic — 2 attempts, second prepends a corrective system message about JSON syntax.

## I/O & Path Conventions

**`pathlib.Path` everywhere.** `os.path` is not used in app code. Strings coerced on entry: `out_dir = Path(out_dir)`. Canonical signature for any path is `str | Path`.

**Encoding always explicit `encoding="utf-8"`** for text I/O — never bare `open()`. 30+ call sites, idiom:
```python
segs_file.write_text(json.dumps(segs_data, ensure_ascii=False, indent=2), encoding="utf-8")
data = json.loads(segs_cache.read_text(encoding="utf-8"))
```

**JSON convention:**
- Write: `json.dumps(obj, ensure_ascii=False, indent=2)` to keep Chinese readable + diff-friendly.
- One exception: `agent/tools.py:59` uses `ensure_ascii=True` *only* for Windows terminal print of meta to avoid GBK crash on emoji titles.
- Read: `json.loads(path.read_text(encoding="utf-8"))` not `json.load(open(...))`.

**Output directory layout:** `output/<video_id>/`. Each contains:
- `meta.json` — title, uploader, duration, video_path, subtitle_path, url (and `aweme_id`/`source: "douyin"` for 抖音).
- `video.mp4` — downloaded source.
- `video.info.json` — yt-dlp info dump.
- `audio.wav` — extracted by ffmpeg, 16 kHz mono PCM s16le (`src/asr.py:43-49`).
- `segs.json` — list of `{start, end, text}` from faster-whisper.
- `paragraphs.json` — list of `{para_id, start, end, text, seg_indices}`.
- `frames/` — directory of jpegs.
- `summary.md` — final tutorial output (only after `/summarize-video` runs).
- v2 pipeline (`agent/prepare.py`) additionally writes: `frame_store.json`, `embeddings.npy` (optional), `budget_report.txt`, `outline_raw_0.txt` / `outline_raw_1.txt` (debug).

**Frame naming:**
- v1 / `agent/embed.py` / `agent/frames_v2.py`: `frame_NNNNNN.jpg` (six-digit ffmpeg sequence). Pattern `out_dir / "frame_%06d.jpg"` (`src/frames.py:30`, `agent/frames_v2.py:53`).
- v2 segmented (`extract_frames` CLI subcommand): `seg_SSSS_NNNNNN.jpg` where `SSSS = int(start_seconds):04d` and `NNNNNN` is ffmpeg's `%06d` index *within that segment*. Defined at `agent/tools.py:114-115`:
  ```python
  prefix = f"seg_{int(args.start):04d}_"
  pattern = str(out_dir / f"{prefix}%06d.jpg")
  ```
- Real examples: `seg_0012_000002.jpg`, `seg_0068_000005.jpg`, `seg_0260_000006.jpg`.
- Timestamp recovery: `ts = start + (int(stem.split("_")[-1]) - 0.5) / fps` (`agent/tools.py:123`).

**Cache convention:** Every stage checks `if cache_path.exists(): load else compute + write`. Flag named `skip_if_cached: bool = True` on download (`src/download.py:14`, `agent/douyin_downloader.py:132`). Opposite is `--force`. For caches that reference files, also verify `Path(d["path"]).exists()` (`src/pipeline.py:69`).

**`mkdir(parents=True, exist_ok=True)`** is the universal directory-creation idiom; `os.makedirs` never appears.

**`unlink(missing_ok=True)`** for cleanup (`src/frames.py:58,76`, `agent/frames_v2.py:238`).

## Function Design

**Size:** Most ~10-50 lines. Larger orchestration entries (`run` in `src/pipeline.py`, `main` in `agent/prepare.py`, `download_douyin` in `agent/douyin_downloader.py`) explicitly split with `log.info("=== Stage N: ... ===")` banners.

**Parameters:**
- Required positional first, then defaults.
- `LLMClient.chat` and `.vision` use **keyword-only** args via `*`: `def chat(self, *, stage: str, model: str, ...)` (`src/llm_client.py:57-67, 93-95`).

**Return values:**
- Single object preferred; tuples only when truly paired (`_pick_download_url` → `(url, meta_dict)`).
- `None` for "not found" instead of raising (`FrameStore.get`, `_extract_aweme_id`).
- Functions that mutate in place return `None`; docstring says "in-place" — the `score_*` family in `agent/frames_v2.py:81-155` follows this.

## Module Design

**Exports:** No `__all__` declared anywhere. Public surface = everything not prefixed with `_`.

**Barrel files:** None. `__init__.py` files are empty. Imports always go to the concrete module: `from src.asr import Segment`, never `from src import Segment`.

**No side-effect modules.** Closest is `agent/smoke_test_fc.py` which does `load_dotenv()` and constant setup at module load — but that file is a standalone test script, not a library.
