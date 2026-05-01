# Phase 5 Plan 03 Final Verification

**Date:** 2026-05-02
**Verifier:** Claude (autonomous /gsd-execute-phase Task 6)
**Branch base:** c7126463 (post-SPIKE.md)
**Spike decision:** degrade (fast-path; see 05-03-SPIKE.md)

## Pass/Fail Summary

| Requirement / Check | PASS/FAIL | Evidence |
|---|---|---|
| **TEACH-01** 4 mode tags byte-equal | PASS | `grep -cE "^####? Mode: ..." CLAUDE.md` → 4 |
| **TEACH-02** format-spec 4 invariants | PASS | `[HH:MM:SS]` × 6 / 第二人称 × 3 / `![](frames/seg_xxxx_xxxxxx.jpg)` 引用 / fenced code w/ language present |
| **TEACH-03** 8 hand-authored skeletons | PASS | `grep -c "^##### Skeleton" CLAUDE.md` → 8 (4 modes × 2) |
| **TEACH-04** classification_evidence field | PASS | `classification_evidence: \|` in plan.md schema doc |
| **TEACH-05** depth_plan.md optional file | PASS | `### depth_plan.md 可选（仅 token-expensive 视频）` section in CLAUDE.md |
| **TEACH-06** asr_v2.PROFILES + aggregate_paragraphs(profile=) | PASS | `agent/asr_v2.py:PROFILES: dict[str, dict[str, float]] = {` |
| **TEACH-07** --profile CLI flag | PASS | `agent/tools.py` argparse `"--profile", choices=["tutorial", "podcast"]` (2 subparsers) |
| **TEACH-08** diarize CLI | PASS | `python -m agent.tools diarize --help` exit 0; usage line emitted; --allow-long flag present |
| **TEACH-09** UI demo 4 sub-rules byte-equal | PASS | `quote-with-uncertainty` × 1 / `Tooltip 遮挡` × 1 / `光标不可见` × 2 / `1280/1920` × 1 in CLAUDE.md |
| **TEACH-10** podcast skeleton blockquote-form | PASS | `### Podcast / interview 模式骨架` + `Step 3: 输出用 blockquote 替代图片嵌入` + `每章节 1-2 帧` × 3 |
| **TEACH-11** whisper-repetition guard (no auto-delete) | PASS | `def whisper_repetition_guard(segs: list[dict]) -> list[dict]` in agent/tools.py |
| **TEACH-12** VAD per-profile tightened | PASS | `vad_min_silence_ms: 500` (tutorial) / `vad_min_silence_ms: 800` (podcast) in src/asr.py PROFILES |
| **TEACH-13** chapters.json schema | PASS | `chapters.json` × 10 references / `topic_title` × 3 / `summary_line` × 3 in CLAUDE.md |
| **WR-02** VTT priority zh-Hans>zh-Hant>zh>en | PASS | `"subtitleslangs": ["zh-Hans", "zh-Hant", "zh", "en"]` in agent/sources/youtube.py; old `["zh-CN", ...]` count = 0 |
| **D-13** SPIKE.md decision recorded | PASS | `My decision: degrade` in 05-03-SPIKE.md |
| **D-15** Pyannote setup section | PASS | `## Pyannote diarization 设置（首次设置，可选）` at line 86 (between YouTube at 50 and Windows zh-CN at 124) |
| **D-16** 60min+ CPU WARNING verbatim | PASS | `WARNING: 60min+ 音频在 CPU 上 pyannote 预计 3-5×` byte-equal in CLAUDE.md + agent/tools.py |
| **D-17** pyannote.audio opt-in pin | PASS | `pyannote.audio>=4.0,<5.0` in requirements-optional.txt |
| **D-19** podcast 1-2 frames per chapter | PASS | `每章节 1-2 帧` × 3 / schedule.json fps 0.05 example in skeleton |
| **D-20** UI demo 4 sub-rules verbatim order | PASS | Pixel-text → Tooltip → 光标 → --width 1280/1920 (numbered 1-4 in CLAUDE.md) |
| **D-21** no parallel 8-phase fork | PASS | /summarize-video 主流程 8 阶段未变；mode 提示用 blockquote inline 嵌入 |
| **D-30..D-32** Phase 3 WR-02 fold-in | PASS | youtube.py subtitleslangs locked + CLAUDE.md interview-distillation 引用 subtitle_origin=='creator' |
| **5 core cmds backward-compat** | PASS | `git diff c7126463 -- CLAUDE.md \| grep -cE "^[-+].*python -m agent\.tools (download\|transcribe\|extract_frames\|aggregate\|cleanup_frames)"` → 0 |
| **CLAUDE.md ≤ 2000 lines (D-08)** | PASS | `wc -l CLAUDE.md` → 1161 |

## Evidence Detail

### diarize CLI smoke tests

**Test 1: --help exits 0**
```
$ python -m agent.tools diarize --help
usage: agent.tools diarize [-h] --out OUT [--allow-long] audio_wav

positional arguments:
  audio_wav     path to audio.wav (16kHz mono PCM preferred)

options:
  -h, --help    show this help message and exit
  --out OUT     path to diarization.json output
  --allow-long  skip 60min+ CPU warning gate (D-16); for automated batch runs

exit code: 0
```

**Test 2: HF_TOKEN missing → clean RuntimeError**
```
$ unset HF_TOKEN
$ python -m agent.tools diarize /nonexistent.wav --out .test_artifacts/d.json
...
RuntimeError: HF_TOKEN not set; see CLAUDE.md '## Pyannote diarization 设置（首次设置，可选）'
```

**Test 3: HF_TOKEN set, audio missing → clean RuntimeError**
```
$ HF_TOKEN=fake python -m agent.tools diarize /nonexistent.wav --out .test_artifacts/d.json
...
RuntimeError: audio file not found: D:\Program Files\Git\nonexistent.wav
```

**Test 4: pyannote not installed (implicit on this machine — silero-vad-only opt-in install).** Without `pip install -r requirements-optional.txt`, the lazy import in `agent/diarize.py:diarize_audio` would raise `RuntimeError("pyannote.audio not installed; install via 'pip install -r requirements-optional.txt' (~700MB torch dep)")`. Lazy import means the test path stops at HF_TOKEN guard / audio existence guard before reaching pyannote — test 2 and 3 confirm those guards fire first.

### 5 Core Commands Backward-Compat

```
$ for cmd in download transcribe extract_frames aggregate cleanup_frames; do
    python -m agent.tools $cmd --help 2>&1 | head -3; echo "exit: $?"
  done
```

All 5 commands return exit 0 with proper usage strings. The `transcribe` and `aggregate` subparsers gained `--profile {tutorial,podcast}` (Plan 02 TEACH-07) but `tutorial` is the default → byte-equal Phase 2 baseline behavior preserved (verified in 05-02-REGRESSION.md).

### VTT Priority (WR-02 / D-31)

```
$ grep -F 'subtitleslangs' agent/sources/youtube.py
            "subtitleslangs": ["zh-Hans", "zh-Hant", "zh", "en"],
```

Old form `["zh-CN", "zh", "en"]` count = 0 (fully removed). `_detect_subtitle_origin` (line 192-206) still recognizes `zh-hans` / `zh-hant` keys for `subtitle_origin` field labeling (Phase 3 SRC-08 byte-equal preserved).

### CLAUDE.md Section Diff Summary

```
$ git diff c7126463 -- CLAUDE.md | grep -E "^[-+]## " | head
+## Pyannote diarization 设置（首次设置，可选）
+## 第一章：ECS 之争       # (markdown example INSIDE skeleton code-fence, not real top-level)
```

Only 1 new top-level section added (`## Pyannote diarization`); the second `##` is inside a fenced markdown example demonstrating Podcast skeleton output form. The 4 critical sections (抖音支持 / YouTube 支持 / Windows zh-CN / 决策支持工具) untouched.

## Deferred Items (v2 Candidates)

These are documented but explicitly NOT in Phase 5 scope:

- **`speakers.json` real-name resolution** (Karpathy / Lex from `SPEAKER_00` / `SPEAKER_01`) — Claude infers from content cues in degrade path; v2 may add automated mapping
- **`--no-frames` flag** — completely skip frame extraction for podcast mode; degrade path uses `fps 0.05` 1-2 frames/chapter as compromise
- **`chapters_check` bidirectional validator** — verify chapters.json topic alignment with paragraph content
- **Pyannote on GPU** — D-16 gate currently directs user to "等 GPU 机器再跑"; v2 may add `--device cuda` flag (pyannote 4.0 supports it)
- **`--width 1280/1920` auto-detect from ffprobe** — currently manual judgment in skeleton; v2 may probe video resolution and suggest

## Final Decision

**Phase 5 Plan 03: ALL CHECKS PASS.**

13/13 TEACH requirements verified. WR-02 fold-in complete. CLAUDE.md degrade-path skeletons land cleanly with 5-core-cmd byte-equal backward-compat preserved. Spike decision (degrade) ships supporting infrastructure (CLI + opt-in dep + doctor entry) for future GPU upgrade path.

Ready for orchestrator to advance plan counter and finalize phase.
