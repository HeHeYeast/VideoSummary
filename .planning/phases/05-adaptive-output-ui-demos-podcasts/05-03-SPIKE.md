# Phase 5 Plan 03 Spike: pyannote 4.0 community-1 on Windows 11 + CPU

**Date:** 2026-05-02
**Hardware:** Windows 11 Home, CPU only (machine-specific bench skipped)
**Audio source:** N/A — fast-path opt-out per orchestrator decision (autonomous mode)

## Decision rationale (fast-path)

User selected the recommended `degrade` fast-path during /gsd-autonomous Phase 5 execution. The full pyannote benchmark was deliberately skipped to avoid:

- HuggingFace account registration + community-1 license acceptance friction
- ~700 MB of additional torch / pyannote weight downloads on top of existing silero-vad install
- 12-20 min CPU bench on a 4-min podcast audio (per SUMMARY.md L317 expected ratio)

This trades real diarization quality data for milestone velocity. The degrade path still ships:

- `cmd_diarize` CLI wrapper (committed in Task 4 — `agent/diarize.py` + `agent/tools.py`) so a future GPU machine can run diarization without re-implementation
- `requirements-optional.txt` pyannote pin (Task 2) so opt-in install path is documented
- Podcast / interview-distillation skeleton in CLAUDE.md uses `speaker_id="?"` placeholders + Claude infers speakers from content cues (开场白 / 谁问谁答 / 提问 vs 回答语气 / blockquote attribution)

## Measurements

deferred-spike: skipping pyannote run; defaulting to degrade path so podcast mode ships without diarization, Claude infers speakers from content cues.

- wall_time: N/A
- ram_peak: N/A
- speaker_turns_emitted: N/A
- diarization output sample: N/A

## Subjective Quality Assessment

N/A — bench skipped.

## Decision: degrade

**My decision:** degrade
**Rationale:** User opted for fast-path during /gsd-autonomous to keep milestone moving. pyannote infrastructure (CLI + opt-in dep + doctor entry) still ships so the upgrade path is one `pip install -r requirements-optional.txt` + HF token away. CLAUDE.md interview-distillation skeleton already uses blockquote-with-speaker-attribution form (Plan 01 Skeleton 1, e.g. `> [00:02:25] @kubb (Hacker News): "..."`) which is robust to missing diarization; degrade path formalizes the `speaker_id="?"` placeholder rule for cases where Claude cannot infer.

## Implications for Plan 03 task 5

CLAUDE.md updates ship the **degrade-path** podcast / interview-distillation skeletons:

- Skeleton uses `speaker_id="?"` placeholder OR named blockquote attribution (`> [HH:MM:SS] @speaker_name: "..."`) where the name is inferred from content cues
- Add explicit "Claude 从内容线索推断说话人" guidance section: 开场白 / 谁问谁答 / 提问语气 vs 回答语气 / blockquote attribution / 嘉宾名 from intro
- chapters.json schema lands without `speaker_id` fields (or with optional `speaker_id?: string` field for future GPU-machine diarization to populate)
- diarize CLI documented in CLAUDE.md as **opt-in for users with GPU + HF token**, not part of default Phase 5 flow

## Re-running the spike later

If user later wants real diarization:

1. `pip install -r requirements-optional.txt` (pulls pyannote.audio + torch)
2. Apply for HF token + accept https://huggingface.co/pyannote/speaker-diarization-community-1 license
3. Write `HF_TOKEN=hf_...` to project root `.env`
4. Run `python -m agent.tools diarize <audio.wav> --out <slug>/diarization.json`
5. Update CLAUDE.md skeleton to consume diarization.json speaker_id values (replace `?` with `SPEAKER_NN`)

This SPIKE.md should be replaced with real bench data at that point.
