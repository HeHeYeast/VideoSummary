---
phase: 05-adaptive-output-ui-demos-podcasts
verified: 2026-05-02T00:00:00Z
status: passed
score: 13/13 must-haves verified
overrides_applied: 0
spike_decision: degrade  # TEACH-08/13 ship infrastructure (CLI + opt-in pin); real diarization deferred to GPU machine
references:
  - .planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-VERIFY.md  # full 13/13 PASS table with grep evidence
  - .planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-SPIKE.md   # degrade fast-path decision
  - .planning/phases/05-adaptive-output-ui-demos-podcasts/05-REVIEW-FIX.md # 3/3 warnings fixed (commits f5347bb / 91a656e / 4244a0b)
---

# Phase 5: Adaptive Output (UI Demos + Podcasts) Verification

**Phase Goal:** Ship adaptive teaching output (4-mode classification: replicate-guide / concept-explanation / extension-applications / interview-distillation), UI-demo and podcast skeletons, and the single Python touch (`aggregate --profile podcast` + opt-in `diarize`).

**Verified:** 2026-05-02
**Status:** passed
**Re-verification:** No — initial verification

## Verification Approach

Lean spot-check mode: pre-existing `05-03-VERIFY.md` already documents a 13/13 PASS table with grep evidence for every TEACH-XX. This VERIFICATION.md cross-references that report and runs 9 independent spot-checks against the live codebase to catch any drift between the verify report and current files.

## TEACH Requirements Coverage (13/13)

| #  | Requirement | Status | Live Evidence (independent spot-check) |
|----|-------------|--------|----------------------------------------|
| 01 | mode tag in plan.md (4-mode classification) | PASS | `CLAUDE.md:154 ## 视频类型变奏`; 4 mode tags (`replicate-guide` / `concept-explanation` / `extension-applications` / `interview-distillation`) appear 26× total in CLAUDE.md, byte-equal |
| 02 | format-spec lock (4 invariants) | PASS | Verified in 05-03-VERIFY.md row 2 (timestamps × 6, 第二人称 × 3, frames path, fenced code w/ language) |
| 03 | 8 hand-authored skeletons (4 modes × 2) | PASS | `grep ^##### Skeleton CLAUDE.md` → 8; `grep ^#### Mode: CLAUDE.md` → 4 (lines 237/394/533/733) |
| 04 | plan.md classification_evidence field | PASS | Verified in 05-03-VERIFY.md row 4 |
| 05 | depth_plan.md optional checkpoint | PASS | Verified in 05-03-VERIFY.md row 5 |
| 06 | asr_v2.PROFILES + aggregate_paragraphs(profile=) | PASS | `agent/asr_v2.py:31 PROFILES: dict[str, dict[str, float]] = {` |
| 07 | --profile CLI flag for aggregate + transcribe | PASS | `agent/tools.py:1168, 1177 "--profile", choices=["tutorial", "podcast"]` (2 subparsers); `diarize` subcommand registered at line 1234 + dispatch at 1280 |
| 08 | diarize CLI + opt-in pyannote pin | PASS | `agent/diarize.py:27 def diarize_audio(...)`; `requirements-optional.txt:31 pyannote.audio>=4.0,<5.0`; SPIKE degrade-path ships CLI + dep pin without real bench (deliberate per 05-03-SPIKE.md) |
| 09 | UI demo 4 sub-rules byte-equal | PASS | Verified in 05-03-VERIFY.md row 9 (pixel-text uncertainty / Tooltip 遮挡 / 光标不可见 / 1280/1920 override) |
| 10 | podcast skeleton blockquote-form | PASS | Verified in 05-03-VERIFY.md row 10 (`Step 3: 输出用 blockquote 替代图片嵌入` + 每章节 1-2 帧 × 3) |
| 11 | whisper-repetition guard (no auto-delete) | PASS | `agent/tools.py:451 def whisper_repetition_guard(segs: list[dict]) -> list[dict]`; called at line 268; D-24 redline preserved (no input mutation) per REVIEW-FIX WR-02 |
| 12 | VAD per-profile tightened | PASS | `src/asr.py:50 PROFILES: dict[str, dict[str, float]] = {`; tutorial vad_min_silence_ms=500 / podcast 800 (verified 05-03-VERIFY.md) |
| 13 | chapters.json schema (podcast structural unit) | PASS | Schema documented in CLAUDE.md (`chapters.json` × 10 refs / `topic_title` × 3 / `summary_line` × 3 per 05-03-VERIFY.md); `## Pyannote diarization 设置（首次设置，可选）` setup section at CLAUDE.md:86 |

**Score:** 13/13 TEACH requirements verified.

## Independent Spot-Checks (9/9 PASS)

All 9 spot-checks from the verification request executed independently of 05-03-VERIFY.md and confirm live-code consistency:

1. ✓ `^## 视频类型变奏` section present at CLAUDE.md:154
2. ✓ 4 mode tags byte-equal (26 total occurrences across CLAUDE.md)
3. ✓ `## Pyannote diarization 设置（首次设置，可选）` section at CLAUDE.md:86
4. ✓ `agent/diarize.py:27 def diarize_audio(...)`
5. ✓ `agent/asr_v2.py:31 PROFILES: dict[str, dict[str, float]] = {`
6. ✓ `src/asr.py:50 PROFILES: dict[str, dict[str, float]] = {`
7. ✓ `agent/tools.py` argparse: `--profile` for transcribe (1168) + aggregate (1177); `diarize` subcommand registered (1234) + dispatched (1280)
8. ✓ `agent/tools.py:451 def whisper_repetition_guard`; called at line 268
9. ✓ `requirements-optional.txt:31 pyannote.audio>=4.0,<5.0`

## Spike Decision Acknowledgment

Per `05-03-SPIKE.md` (`My decision: degrade`), TEACH-08 and TEACH-13 ship the **degrade-path infrastructure**:

- `agent/diarize.py` + `cmd_diarize` CLI wrapper present (one-cmd-away from real diarization)
- `requirements-optional.txt` pin documented (opt-in install, not in default requirements.txt)
- HF_TOKEN guard fires before pyannote import (verified in 05-03-VERIFY.md test 2/3)
- chapters.json schema includes optional `speaker_id?: string` (Claude infers from content cues in degrade path)
- 60min+ CPU WARNING gate present (D-16; `--allow-long` opt-out)

This was a deliberate user decision via `/gsd-autonomous AskUserQuestion` to avoid HF account friction + ~700 MB torch download + 12-20 min CPU bench. **Not a gap** — the upgrade path is one `pip install -r requirements-optional.txt` + HF token away.

## Code Review Status

`05-REVIEW.md` found 3 warnings; `05-REVIEW-FIX.md` reports `status: all_fixed`:

- WR-01 (VTT priority lock at file-picker) → fixed in commit `f5347bb`
- WR-02 (trigram repetition guard density detector) → fixed in commit `91a656e` + 15 unit tests
- WR-03 (cmd_diarize CJK validation on input audio path) → fixed in commit `4244a0b`

5 IN-* (Info) findings deferred per `fix_scope: critical_warning` policy. None block goal.

## Format-Spec Lock (4 Invariants — Goal-Critical)

The phase goal explicitly preserves the "form not changed" contract:

1. ✓ `[HH:MM:SS]` 8-char timestamps in all 8 skeletons
2. ✓ Code fences with explicit language (`gdscript` / `python` / `bash` / `json` / `yaml` / `text` / `console`)
3. ✓ `![](frames/seg_xxxx_xxxxxx.jpg)` relative-path image embeds (no absolute paths)
4. ✓ Second-person imperative voice ("你打开 settings.json")

Verified across all 8 skeletons in CLAUDE.md per 05-03-VERIFY.md row 2.

## Backward-Compatibility (5 Core Commands)

Per 05-03-VERIFY.md "5 Core Commands Backward-Compat" section:

- `download` / `transcribe` / `extract_frames` / `aggregate` / `cleanup_frames` all return exit 0
- `transcribe` and `aggregate` gained `--profile {tutorial,podcast}` but `tutorial` is default → byte-equal Phase 2 behavior
- 17 archived summaries remain re-runnable (plan.md missing emits WARNING, not fatal — K3 backward-compat preserved)

## Summary

All 13 TEACH requirements verified by both the pre-existing 05-03-VERIFY.md grep table AND 9 independent live-code spot-checks. The degrade-path spike decision (TEACH-08/13) ships the documented infrastructure without forcing a 700MB pyannote install on every user. Code review iteration 1 closed all 3 in-scope warnings. Format-spec lock + 5-core-cmd backward-compat both preserved.

**Phase 5 goal achieved: adaptive teaching output (4 modes × 2 skeletons), UI-demo + podcast skeletons, and single Python touch (`aggregate --profile podcast` + opt-in `diarize`) are all in place.**

---

_Verified: 2026-05-02_
_Verifier: Claude (gsd-verifier)_
