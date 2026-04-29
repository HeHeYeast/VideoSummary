# Testing

Generated 2026-04-29 from a structured codebase audit (focus: quality).

## Test Framework

**None. No automated test suite exists.**

Verified by exhaustive search:
- No `tests/` or `test/` directory in the project root.
- No `test_*.py` or `*_test.py` files anywhere in app code (`pytest` collection patterns).
- No `conftest.py` anywhere in the repo.
- `pytest`, `unittest`, `nose`, `tox` not present in `requirements.txt`.
- No `[tool.pytest]`, `[tool.tox]`, `[testenv]` config — there is no `pyproject.toml` or `setup.cfg` at all.
- No `.github/workflows/` at the project root that runs tests (the `.github/workflows/` files in `vendor/douyin_api/.github/workflows/` belong to the vendored upstream repo: `codeql-analysis.yml`, `docker-image.yml`, `readme.yml`).
- The single file matching `def test_` pattern is `agent/smoke_test_fc.py`, but its `def test_model(model: str) -> dict:` is a one-off script function — not a pytest test (see *Smoke test scripts* below).

## Verification Approach

**Manual end-to-end runs against real videos.**

The project is verified by running the pipeline against real B站 / 抖音 URLs and inspecting the produced `output/<BVxxx>/summary.md`. The recent commit history is the closest thing to a test log:
- `f03ed73` — "¥0 流程验证通过: 307 行教程, 17 帧, 全部本地+多模态"
- `08a79f4` — "支持抖音视频下载 (a_bogus 签名, ¥0 路径)"
- `416b849` — "v4 修复批 1+2: 字幕/帧/writer/装配多处缺陷"
- `0357d0e` — "简化工具集: 去掉 VE API 依赖, 全流程 ¥0"
- `ac7add4` — "v2 agent 架构: 离线数据层 + Claude Code skill 写作"

These commits reference verification by inspection of artifacts (line counts, frame counts, real outputs) rather than by an automated CI signal.

## Why No Tests

The project's quality model relies on **Claude Code as a multimodal verifier** rather than unit tests:

1. **Claude is the executor, not just the generator.** Per `CLAUDE.md`, the workflow has Claude Code drive the pipeline (download → ASR → 抽帧 → multimodal frame reading → write tutorial). Each stage's correctness is judged by what comes out the other end and whether Claude can read the frames it produced.
2. **Frames are visually inspected by Claude.** Section 4 of `CLAUDE.md` ("看帧（多模态，核心步骤）") instructs Claude to `Read output/xxx/frames/seg_xxxx_xxxxxx.jpg` directly — the multimodal model is the OCR/classifier, replacing what would otherwise be assertion-style tests on classify/OCR functions.
3. **The "质量红线" (quality redlines)** at the end of `CLAUDE.md` are checklist-style human assertions, not automated:
   - Timestamps must come from real subtitles
   - Code must be transcribed from frame screenshots, not invented
   - Images must follow corresponding steps
   - No filler, no fabrication
   - Final code must run

These are validated by re-running the pipeline against past videos and reading the resulting `summary.md`.

## Smoke Test Scripts

**`agent/smoke_test_fc.py`** — the only file with "test" in its name.

Despite the name and a `def test_model(...)` function, this is **not a pytest test**. It is a standalone script you run as `python -m agent.smoke_test_fc` (line 7 docstring) that:
- Iterates a hard-coded list of candidate models (`CANDIDATES` list, line 49-57).
- Sends each one a `get_weather` function-calling probe (`TOOLS`, `MESSAGES` constants, lines 27-46).
- Prints a pass/fail table to stdout (`def main()`, lines 86-107).

It exits 1 only if `VE_KEY_QUALITY` / `VE_KEY_CHEAP` are missing (line 20-22). It does not assert anything; the human reads the table and picks a usable model.

There is no equivalent script for the local pipeline because the local pipeline has no API surface to probe — the verification is the produced markdown.

## Mocking, Fixtures, Coverage

**None.**
- No mocking framework (`unittest.mock`, `pytest-mock`, `responses`, `vcrpy`) installed or used.
- No fixtures folder, no `tests/data/`, no checked-in stub videos.
- No coverage tooling (`coverage.py`, `pytest-cov`) — there's nothing to cover.

The closest thing to fixtures: real outputs under `output/` (~58 BVxxx directories, e.g. `BV1C9QCBdE1U/` containing `meta.json`, `segs.json`, `paragraphs.json`, `frames/seg_0012_000002.jpg`, …, `summary.md`). These are *outputs*, not test fixtures, but they double as regression references — re-running a stage on an existing `output/BVxxx/` will reuse cached `segs.json` / `paragraphs.json` and you can diff the new `summary.md` against the previously committed one.

## Test Types

- **Unit tests:** None.
- **Integration tests:** None automated. The integration test is "run the full pipeline against a real BV id and look at `output/BVxxx/summary.md`."
- **E2E tests:** None automated; same as above. The Phase 8 self-check in `CLAUDE.md` ("时间戳真实？代码从截图抄？图片对应步骤？无废话？") is the manual E2E pass.
- **Smoke tests:** `agent/smoke_test_fc.py` only — and it tests the cloud LLM provider's function-calling support, not this codebase's logic.

## How to Verify a Change

When modifying any tool in `agent/tools.py` or stages in `src/pipeline.py` / `agent/prepare.py`:

1. **Re-run the affected stage on an existing fixture directory** under `output/<BVxxx>/`. Caches will be reused for upstream stages, so iteration is cheap.
   ```bash
   python -m agent.tools transcribe output/BV11FckzjEkq/video.mp4 --out output/BV11FckzjEkq --force
   python -m agent.tools aggregate output/BV11FckzjEkq/segs.json --out output/BV11FckzjEkq/paragraphs.json
   python -m agent.tools extract_frames output/BV11FckzjEkq/video.mp4 --out output/BV11FckzjEkq/frames --fps 0.3 --start 30 --end 60
   ```
2. **Diff the JSON outputs** (`segs.json`, `paragraphs.json`, `frame_store.json`) against the previously committed copies — they are pretty-printed (`indent=2`) specifically for human/diff readability.
3. **Inspect frame jpegs visually** (since you are Claude, just `Read output/<BVxxx>/frames/seg_*.jpg`).
4. **For full pipeline regressions**, re-run `/summarize-video` on a video already in the queue (see `MEMORY.md` reference to "6 条待总结视频队列") and compare the new `summary.md` to the committed one.
5. **For 抖音-specific changes**, expect cookies to expire in days (per `CLAUDE.md`); if download tests fail, refresh `www.douyin.com_cookies.txt` first before assuming code regression.

## When Adding Tests Becomes Worthwhile

The codebase deliberately has no test suite, but if test infrastructure is ever added the lowest-hanging fruit (pure functions, easy to test, no external IO):
- `agent/asr_v2.py:_SENTENCE_END`, `aggregate_paragraphs`, `get_transcript_window`, `search_transcript`
- `src/asr.py:_HALL_RE`, `parse_vtt`, `format_transcript`
- `agent/frames_v2.py:_ANCHOR_RE`, `score_novelty`, `score_voice_anchors`, `score_stability`, `select_top_k`
- `src/budget.py:BudgetGuard.estimate_chat_cost`, `precheck`, `commit`
- `agent/pass1_classify.py:_parse_classification`
- `agent/douyin_downloader.py:_cookies_txt_to_header`, `_extract_aweme_id`, `_pick_download_url`
- `agent/frame_store.py:FrameStore.list_frames`, `find_nearest`, `mark_consumed`

These are all deterministic, dependency-light, and have well-defined inputs (dataclass instances, JSON dicts).
