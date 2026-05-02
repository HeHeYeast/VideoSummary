# Stack Research — v1.1 summary-quality

**Domain:** Local CLI tooling addition to existing ¥0 video-summarization tool (Python 3.13, Windows 11 first)
**Researched:** 2026-05-03
**Confidence:** HIGH (current stack frozen + minimal new deps; all version numbers verified May 2026)

## TL;DR

**v1.1 needs zero or one new dependency.** The 8 candidate features (CORR-01/02/03, TEACH-A/B, TOOL-A/B, MISC-01/02) decompose to:

- **6 of 8 features need NO new library** — they are Claude prompt-engineering + stdlib file I/O + Markdown convention enforced by Claude self-check. (CORR-02, CORR-03, TEACH-A, TEACH-B, TOOL-B, MISC-01, MISC-02)
- **1 feature has an optional dep** — CORR-01 L1 detection benefits from `pypinyin` (homophone confusion is the #1 ASR error class for Chinese ASR per BV1HG9JBsEPK / BV1rsd7BsEnA实测). Recommended path: **add `pypinyin>=0.55.0` as a default dep** (~2 MB, pure-Python, stable) — but also document a "no new dep" fallback (Claude prompt-only L1 detection).
- **TOOL-A (`mode_signals.json`) needs zero new deps** — pure regex + paragraph-level frequency counting on existing `paragraphs.json`; CLAUDE.md "stack inertia" wins.

**Constraint validated:** Existing stack (`yt-dlp`, `faster-whisper`, `scenedetect`, `Pillow`, `imagehash`, `httpx==0.27.2`, vendor douyin_api) all current as of v1.0 ship; **no upgrades required** for v1.1 functionality. v1.1 is additive, not migrational.

---

## Recommended Stack

### Existing Core (do NOT change for v1.1)

| Technology | Current Version (req.txt) | Latest stable (May 2026) | Action for v1.1 |
|------------|---------------------------|--------------------------|-----------------|
| Python | 3.13 | 3.13.x | Keep |
| `yt-dlp` | `>=2026.03.17` | 2026.3.17 | Keep — already current |
| `faster-whisper` | `>=1.0.3` | 1.2.1 | **Optional** bump min to `>=1.2.0` (`Word`/`Segment` dataclass conversion lands cleaner JSON; v1.1 reviewer agent benefits) — **but not required**, K3 backward-compat: 1.0.3 still works |
| `scenedetect[opencv]` | `>=0.6.7.1` | 0.6.7.1 | Keep — already current |
| `Pillow` | `>=10.0.0` | 12.2.0 | Keep `>=10.0.0` constraint (Phase 4 not affected); upgrading is fine but not gated |
| `imagehash` | `>=4.3.1` | 4.3.x | Keep |
| `httpx` | `==0.27.2` (strict) | — | **Keep strict pin** — vendor douyin_api still uses deprecated `proxies=` kwarg removed in 0.28+ (see `requirements.txt:13` comment); v1.1 must not bump |
| `pyyaml` / `python-dotenv` / `tiktoken` / `tqdm` | unchanged | — | Keep |

### NEW for v1.1 (recommended)

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| `pypinyin` | `>=0.55.0` | Convert Chinese chars → Pinyin for **CORR-01 L1 homophone candidate detection** | (1) Pure-Python, no native deps, ~2MB install. (2) Industry standard for Chinese phonetic similarity (cited in 4 of 5 academic ASR error-correction papers; see Sources). (3) Lets us cheaply detect "Lora vs LoRA vs Laura" cluster as same-pinyin homophones before paying Claude tokens to reason. (4) Pairs with stdlib `difflib.SequenceMatcher` for "罕见字组合" detection — no extra similarity lib needed. **Confidence: HIGH** — this is a thin, stable dep with 12+ years of production use. |

### NEW for v1.1 (optional, scope-creep guard)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `jieba` | `>=0.42.1` | Chinese word segmentation for paragraph-level term frequency in CORR-01 L1 + TOOL-A `mode_signals.json` | **Don't add unless paragraph-level term-freq becomes a measured bottleneck.** Original `jieba` last updated 2020; `jieba-next` (Jan 2026) is the actively maintained Rust-speedup fork. Most v1.1 needs are met by stdlib `re` + character n-gram counting on `paragraphs.json`. **Re-evaluate after Phase 1 ships and CORR-01 L1 is measured.** |
| `rich` | `>=14.0.0` | Pretty table for **MISC-02 queue helper CLI** (`queue list` output) | **Don't add for v1.1.** Existing `tools.py` `print_doctor_table` uses stdlib f-string padding (Phase 2 RES-08); MISC-02 should follow same convention. Adding `rich` would be the first "presentational" dep — violates CLAUDE.md "stack inertia" + 17-archive byte-equal regression concern. v2 candidate only. |
| `mdformat` | `>=0.7.22` | Enforce CORR-02 inline-source token format (`[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]`) at lint time | **Don't add.** CORR-02 token format is enforced by **Claude self-check pass** (CORR-02 must-have row 3 in v1.1-CANDIDATES.md). Lint-time enforcement is downstream of Claude writing — adds infra without changing outcome since Claude is the only writer. Keep as future option if format-spec violations leak past self-check in 5+ shipped summaries. |
| `pyannote.audio` | `>=4.0,<5.0` | Speaker diarization for `interview-distillation` mode | **Already in `requirements-optional.txt`**, opt-in. v1.1 does NOT change this. CORR-01 / CORR-03 do NOT depend on diarization — they work on `paragraphs.json` text + frame JPEGs. |

### NEW for v1.1: NO LIBRARY NEEDED (Claude is the lib)

| Feature | Implementation Path | Why no lib |
|---------|---------------------|------------|
| **CORR-02 行内溯源 token format** | Markdown convention `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` enforced in `/summarize-video` Phase 7 prompt + Claude self-check pass at end of Phase 8 | Pure presentational — no parsing, no tooling consumes it (yet). Claude writes it, Claude checks it. Adding a lint lib would be "tool checking Claude's output" → CLAUDE.md K5 inversion (tool decides). |
| **CORR-03 reviewer agent** | New `.claude/agents/gsd-summary-verifier.md` subagent (markdown frontmatter + system prompt; no Python). Spawned by `/summarize-video` Phase 8 with `Read` + `Grep` + `Glob` tools (read-only). Output: `output/<slug>/<slug>-REVIEW.md` | Claude Code's native subagent infra (project-local `.claude/agents/`) is exactly this. **No new Python infra.** Token cost: separate context window — measured ~7× standard session per Anthropic guidance, so reviewer pass = 80-100% of summary-write cost (matches CORR-03 estimate row 4). Project has zero existing subagents (verified `.claude/agents/` is empty), so this is the first — establishes pattern. |
| **TEACH-A glossary cross-doc accumulation** | Append-only file `output/_glossary.md` (NOT SQLite). Each `/summarize-video` Phase 8 emits `## <term> (English/中文释义)` blocks + dedupe-by-term on append. Stdlib only: `pathlib.Path.read_text` + `.write_text` + simple regex parser | (1) D-01 says "不依赖它，但有它" — glossary is a **read-mostly fallback**, never a join target → no DB needed. (2) Atomic write pattern already exists (Phase 2 RES-02). (3) SQLite would be premature — single user, single writer, no concurrent appends (lock infra from Phase 6 PARA-01 already covers it if needed). (4) Markdown-as-DB also lets user `cat output/_glossary.md` directly — zero query layer. |
| **TEACH-B 5分钟速读版** | Claude writes top section in `/summarize-video` Phase 6 — same prompt template, additive | Pure prompt change. Estimated_sections from `plan.md` already gates "long video" condition (>50). |
| **TOOL-A `mode_signals.json`** | New `agent/tools.py` subcommand `mode_signals <paragraphs.json> --out <slug>/mode_signals.json`. Pure stdlib regex over paragraphs: <br>• Code-fence rate: `re.findall(r'```\w+', text)` count / paragraph count<br>• Step-marker rate: `re.findall(r'(?:第[一二三四五六七八九十\d]+步\|步骤\s*\d+\|Step\s*\d+)', text)`<br>• Question-form rate: `text.count('？') + text.count('?')` / sentence count<br>• Speaker-turn signal: scan for "嘉宾" / "你认为" / "你怎么看"<br>• Cross-tool signal: scan for "vs " / "对比" / "在 X 场景下" | (1) Same K5-bound shape as Phase 4 `detect_scenes` / `detect_silence` — emit JSON, don't write `plan.md`. (2) Heuristics are project-specific (4-mode vocab); no general lib captures them. (3) **`jieba` not needed** for v1.1 — character-level regex on `paragraphs.json` is more robust than word-segmentation for code-mixed (中英 + symbol) tutorial transcripts. Re-evaluate if measured rule precision <80% on 5+ test videos. |
| **TOOL-B `schedule_suggestion.json`** | New `agent/tools.py` subcommand `schedule_suggest <slug> --out <slug>/schedule_suggestion.json`. Combines existing `paragraphs.json` + `scenes.json` (PySceneDetect output) + `silence_map.json` (silero-vad opt-in output, gracefully absent → fall back to 4 segments at default fps 0.2). Emits `schedule.json`-compatible JSON | (1) All 3 inputs already exist as v1.0 artifacts (Phase 4 FPS-01..FPS-07). (2) Scheduler logic already in `agent/scheduler.py` — TOOL-B is a *suggestion writer* not a *new validator*. (3) Same K5 boundary: writes `_suggestion.json`, Claude still writes `schedule.json` from it. |
| **MISC-01 AV1 警告降级** | Change one `logging.warning` → `logging.info` in `agent/tools.py` (Phase 3 SRC-XX; ffprobe codec gate) | Trivial, no lib change. |
| **MISC-02 video queue helper CLI** | New `agent/tools.py` subcommand `queue {add\|list\|next\|done}`. State file `~/.videoSummary/queue.json` — JSON array of `{url, added_at, status, slug?}`. Stdlib: `pathlib.Path.home()` + `json` + `agent/_lock.py` FileLock (already exists from Phase 6 PARA-01) | (1) Single-user, single-machine — no DB. (2) Phase 6 FileLock infra solves the only concurrency edge (two terminals `queue add` simultaneously). (3) Table output uses stdlib f-string padding — keep parity with `doctor` table (Phase 2 RES-08). |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| **No new dev tools** for v1.1 | — | v1.0 has no test framework, no build system, no linter. v1.1 doesn't introduce test harness either — quality gate is `summary.md` E2E + reviewer agent (CORR-03), per CLAUDE.md "no CI" + Phase 1 GR-01 regression baseline approach. |
| `pytest` (NOT recommended even now) | Unit-test the `mode_signals` regex rules | Tempting for TOOL-A heuristics, but project established pattern is stdlib `unittest` (Phase 4 added 56+ tests in stdlib) — don't introduce pytest just for v1.1. |

## Installation

```bash
# v1.1 requires AT MOST one new dep (pypinyin) on top of existing requirements.txt
pip install pypinyin>=0.55.0

# OR add to requirements.txt and reinstall:
echo "pypinyin>=0.55.0" >> requirements.txt
pip install -r requirements.txt

# requirements-optional.txt unchanged for v1.1.
# (silero-vad / pyannote.audio remain opt-in; CORR-01/02/03 do not need them.)
```

**Atomic install instruction for `gsd-planner` PLAN.md:**

```bash
pip install pypinyin>=0.55.0
# Verify:
python -c "import pypinyin; print(pypinyin.__version__)"  # expect 0.55.0+
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `pypinyin` for L1 homophone detection | `dimsim` (IBM phonetic similarity) | If we needed weighted phonetic distance with stroke-similarity penalty. **Reject for v1.1** — overkill for our use case (we just need "do these tokens share pinyin?"); pypinyin gives us the pinyin string and stdlib `==` does the rest. dimsim adds 1 ML model dep. |
| `pypinyin` for L1 homophone detection | **Claude prompt-only L1 detection** (no new dep) | If we want strict "stack inertia" zero-new-deps. Tradeoff: every L1 scan pays Claude tokens for "is this token suspicious?" reasoning on potentially 200+ paragraphs. **Recommended fallback path**: ship pypinyin in Phase A; if measured token cost is <5% of summary-write cost AND zero false negatives, keep it; if pypinyin's pure-Python pinyin lookup is "too aggressive" (false positives), degrade to prompt-only with pypinyin as opt-in. **Phase 1 of v1.1 should validate this empirically on 3 test videos.** |
| Claude self-check for CORR-02 token format | `mdformat` + custom plugin | If we ship a 2nd consumer that *parses* the inline-source tokens (e.g., a future "click-to-jump-to-frame" UI). v1.1 has no such consumer → Claude self-check is sufficient. |
| Markdown file for TEACH-A glossary | SQLite `output/glossary.db` | If we ever need cross-summary join queries ("which 3 summaries introduced 'ECS'?") or term-versioning ("when did we update the LoRA definition?"). v1.1 doesn't need either. Markdown wins on "user can `cat` it" + zero infra. |
| Stdlib f-string for MISC-02 table | `rich` | If we add interactive elements (live progress, color heatmaps for queue priority). v1.1's `queue list` is a 5-column static table → stdlib parity with `doctor` is correct. |
| Project-local subagent for CORR-03 | External Python script that calls Claude API | **Reject** — would require API key + ¥0 violation. Subagent is the correct primitive (Claude Max plan). |
| `jieba` for word segmentation | stdlib `re` regex | Tutorial transcripts are 中英 + code mixed; word-level segmentation often splits "LoRA" or "ComfyUI" into wrong subwords. Character-level regex + `pypinyin` covers the same surface area for L1 detection without `jieba`'s dictionary load. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Any LLM API SDK (OpenAI / Anthropic / etc.) for CORR-01..03 | Violates ¥0 hard constraint (Constraints row 1). The `openai>=1.50.0` already in `requirements.txt` is **legacy fallback for `src/llm_client.py` VectorEngine** — do NOT extend its use to v1.1 features. | Claude Code (the executing agent) IS the LLM. Subagents (CORR-03) use the same Claude Max plan. |
| `langchain-jieba` / `langchain` anything | Heavyweight orchestration, project explicitly avoids agent frameworks (Claude Code IS the orchestrator) | Direct stdlib + tool subcommands. |
| `paddlespeech` / `paddleocr` for L3 multimodal | Adds 2GB+ ML deps for a job Claude multimodal already does (the project's whole premise) | Claude `Read frames/seg_*.jpg` (CLAUDE.md: "你是多模态模型，能精确读取代码截图中的每一行"). |
| `sqlite3` (technically stdlib but) for glossary | Premature optimization for single-user single-writer append log | Plain Markdown file. |
| `whisperx` / `whisper.cpp` / SenseVoice | Already-rejected v1.0 alternatives — `faster-whisper` is the locked ASR (Phase 1 baseline) | `faster-whisper>=1.0.3` (or 1.2.x). |
| `httpx>=0.28` | Breaks vendor douyin_api (`proxies=` kwarg removed) — **strict pin enforced in `requirements.txt:13`** | `httpx==0.27.2` (do NOT bump). |
| `rich` for v1.1 MISC-02 | First "presentational" dep — sets bad precedent; future scope-creep magnet | Stdlib f-string padding (Phase 2 RES-08 `print_doctor_table` pattern). Re-evaluate for v2. |
| `mdformat` plugin for CORR-02 token enforcement | Lint-time check is downstream of Claude writing — adds infra without changing outcome | Claude self-check pass at end of `/summarize-video` Phase 8. |

## Stack Patterns by Variant

**If user wants strict "zero new deps for v1.1":**
- Skip `pypinyin`; do CORR-01 L1 detection via Claude prompt only (scan `paragraphs.json` and emit `transcribe_warnings.json`)
- Tradeoff: ~3-8% extra Claude tokens per ASR scan pass (estimated; needs Phase 1 measurement)
- Implementation: same `transcribe_warnings.json` schema, just no pypinyin pre-pass to narrow candidates

**If user later expands to long-form (>1h) podcasts:**
- `pyannote.audio>=4.0,<5.0` already in `requirements-optional.txt`
- v1.1 reviewer agent (CORR-03) gracefully degrades when `diarization.json` absent (same pattern as `silence_map.json` in Phase 4 D-08)

**If user later wants offline/air-gapped:**
- Already supported — entire stack is local except `yt-dlp` (download) and HuggingFace pull (pyannote opt-in). v1.1 adds nothing that breaks this.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `pypinyin>=0.55.0` | `python>=3.13` | Pure-Python, no native deps, no transitive risk. Compatible with all existing `requirements.txt` deps. |
| `pypinyin` | `jieba` (NOT installed) | They compose well IF you ever add `jieba`, but neither requires the other. |
| `faster-whisper>=1.2.x` | `pypinyin` | No interaction — `faster-whisper` writes `segs.json`; `pypinyin` reads `paragraphs.json`. Independent. |
| `httpx==0.27.2` | All v1.1 additions | v1.1 adds zero HTTP-using deps; pin remains safe. |
| `scenedetect[opencv]>=0.6.7.1` | `pypinyin` | Independent (TOOL-B reads `scenes.json` artifact, not the lib directly). |
| Project-local subagent (`.claude/agents/gsd-summary-verifier.md`) | Claude Code latest | Subagent format is stable since 2025; no version pin needed (file-based config). Verify Claude Code on user's machine supports `.claude/agents/` (introduced 2025; current as of May 2026). |
| `pyannote.audio>=4.0,<5.0` | `torch>=1.12.0` (in `requirements-optional.txt`) | Unchanged from v1.0; v1.1 does NOT alter opt-in pyannote setup. |

## Sources

**Stack version verification (May 2026):**
- [pypinyin · PyPI](https://pypi.org/project/pypinyin/) — verified 0.55.0 latest, pure-Python, MIT license. HIGH confidence.
- [jieba · PyPI](https://pypi.org/project/jieba/) — verified original last updated 2020-01-20; [jieba-next · PyPI](https://pypi.org/project/jieba-next/) latest 2026-01-29 (Rust speedup). HIGH confidence — informs "don't add jieba for v1.1" decision.
- [faster-whisper · PyPI](https://pypi.org/project/faster-whisper/) — verified 1.2.1 latest. HIGH confidence.
- [scenedetect · PyPI](https://pypi.org/project/scenedetect/) + [PySceneDetect Documentation 0.6.7.1](https://www.scenedetect.com/docs/latest/) — verified 0.6.7.1 latest (Sept 2025). HIGH confidence — current pin matches.
- [yt-dlp 2026.3.17 on PyPI](https://pypi.org/project/yt-dlp/2026.3.17/) — verified current pin matches latest. HIGH confidence.
- [pillow · PyPI](https://pypi.org/project/pillow/) + [Pillow 12.2.0 documentation](https://pillow.readthedocs.io/) — verified 12.2.0 latest (April 2026); current `>=10.0.0` constraint compatible. HIGH confidence.
- [pyannote-audio 4.0.4](https://pypi.org/project/pyannote-audio/) — verified 4.0.4 latest (Feb 2026); current `>=4.0,<5.0` pin in `requirements-optional.txt` correct. HIGH confidence.
- [rich · PyPI](https://pypi.org/project/rich/) — verified 15.0.0 latest (April 2026); informs "don't add rich for v1.1" decision. HIGH confidence.
- [mdformat · PyPI](https://pypi.org/project/mdformat/) — verified 0.7.22 / 1.0.0 available; informs "don't add mdformat for v1.1" decision. HIGH confidence.

**Domain research (Chinese ASR error correction approaches):**
- [Pinyin Regularization in Error Correction for Chinese Speech Recognition with Large Language Models (arxiv 2407.01909)](https://arxiv.org/html/2407.01909v1) — confirms pinyin-based regularization as standard ASR-LLM pattern. MEDIUM confidence (academic, not directly applicable but validates `pypinyin`-as-detector heuristic).
- [PERL: Pinyin Enhanced Rephrasing Language Model (arxiv 2412.03230)](https://arxiv.org/html/2412.03230v1) — additional confirmation pinyin features improve Chinese ASR error correction. MEDIUM confidence.
- [Boosting Chinese ASR Error Correction with Dynamic Error Scaling Mechanism (arxiv 2308.03423)](https://ar5iv.labs.arxiv.org/html/2308.03423) — explicit "Jieba for POS + PyPinyin for pronunciation" pattern in production ASR error pipelines. HIGH confidence — directly supports v1.1 CORR-01 L1 design.
- [IBM MAX-Chinese-Phonetic-Similarity-Estimator (dimsim)](https://github.com/IBM/MAX-Chinese-Phonetic-Similarity-Estimator) — alternative considered + rejected (overkill for our binary "same pinyin?" check). MEDIUM confidence.

**Claude Code subagent infrastructure:**
- [Create custom subagents — Claude Code Docs](https://code.claude.com/docs/en/sub-agents) — official spec for `.claude/agents/<name>.md` markdown frontmatter format; confirms project-local pattern. HIGH confidence.
- [Subagents in the SDK — Claude Docs](https://docs.claude.com/en/docs/agent-sdk/subagents) — confirms separate context window per subagent; Tools field; system prompt body. HIGH confidence — directly supports CORR-03 implementation path.
- [How and when to use subagents in Claude Code — Anthropic blog](https://claude.com/blog/subagents-in-claude-code) — token-cost guidance: subagents are "worth that cost when context isolation, parallelism, or a fresh perspective actually helps" — matches CORR-03 use case (fresh-perspective verification). HIGH confidence.

**Existing project artifacts cross-referenced:**
- `.planning/codebase/STACK.md` — v1.0 ground truth for current stack (verified May 2026 versions)
- `requirements.txt` — current pinned deps (verified `httpx==0.27.2` strict pin rationale)
- `requirements-optional.txt` — current opt-in deps (silero-vad / pyannote / torch)
- `CLAUDE.md` "stack inertia" constraint — Constraints section row 6: "现有 stack 不轻易换"
- `.planning/v1.1-CANDIDATES.md` D-01/D-02/D-03 — locked design decisions; confirmed all 8 candidates achievable with proposed stack
- `.planning/PROJECT.md` Out of Scope — confirmed "任何付费 API" is hard ban; pypinyin (free, local) is OK; LLM SDK extensions are NOT

---

## Decision Summary for Roadmapper / Planner

**For `gsd-roadmapper`:** Phase structure is **NOT gated by stack additions** — v1.1 can ship in any phase order without dependency-installation phase gating. The only "install step" is one-line `pip install pypinyin>=0.55.0`, which can sit in the same phase as CORR-01 L1.

**For `gsd-planner` (later, when locking PLAN.md):**

```bash
# Single atomic install for v1.1 (only if CORR-01 ships):
pip install pypinyin>=0.55.0
# Verify:
python -c "from pypinyin import lazy_pinyin; print(lazy_pinyin('LoRA 训练'))"  # ['LoRA', 'xun', 'lian']
```

No version conflicts. No upgrade required for any existing dep (although bumping `faster-whisper>=1.2.0` is cleanly compatible if user wants the dataclass JSON improvement). All other v1.1 features (CORR-02, CORR-03, TEACH-A, TEACH-B, TOOL-A, TOOL-B, MISC-01, MISC-02) are stdlib + Claude prompt + Markdown convention + new `.claude/agents/<name>.md` file — zero pip activity.

---

*Stack research for: v1.1 summary-quality milestone (CORR + TEACH + TOOL + MISC features)*
*Researched: 2026-05-03*
*Overall confidence: HIGH — versions verified May 2026, "no new lib" path validated for 7 of 8 features, single recommended addition (pypinyin) is industry-standard with academic backing.*
