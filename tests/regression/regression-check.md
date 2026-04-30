# Regression Baseline Runbook

**Purpose:** Verify that any milestone-v1 phase change still reproduces the
v1 regression baseline for the three reference videos. Human + Claude
operated, not CI. Run **before** merging any phase that touches `agent/` or
`src/`.

This is an executable runbook, not documentation. Imperative voice — copy
the commands, run them, paste the prompt, read Claude's verdict. Do not
skim; each step matters.

## Baselines (do NOT modify)

These three snapshots are frozen for the milestone (Phase 1 Plan 01-01,
D-13). Do not edit them. If a future phase intentionally drifts an output,
that phase commits the new snapshot and explains the drift in its commit
message.

| Slug             | Type                       | Source URL                                          |
| ---------------- | -------------------------- | --------------------------------------------------- |
| `BV132wizyEEB`   | Code / AI workflow         | https://www.bilibili.com/video/BV132wizyEEB         |
| `BV1C9QCBdE1U`   | Godot tutorial (code-dense) | https://www.bilibili.com/video/BV1C9QCBdE1U         |
| `douyin_trae_ai` | AI / UI demo (douyin path) | https://v.douyin.com/D4_5dfVmsIo/                   |

Each slug ships exactly four files under `tests/regression/<slug>/`:
`summary.md`, `meta.json`, `segs.json`, `paragraphs.json`. No frames, no
audio, no video — those are too large for git and recoverable from the
source URL above.

## Procedure

For each baseline slug, repeat the three steps below. Substitute `<slug>`
with `BV132wizyEEB`, `BV1C9QCBdE1U`, or `douyin_trae_ai`. Substitute
`<source-url>` with the URL from the table above.

### Step 1 — Stage the baseline JSONs into output/

The original `video.mp4` / `audio.wav` are not committed (size). Reuse your
local copy under `output/<slug>/` if present; otherwise re-download once.
Then overlay the four frozen artifacts on top, overwriting any cached
versions the WIP branch produced.

```bash
# Copy the four frozen artifacts INTO output/<slug>/, overwriting cached versions
cp -r tests/regression/<slug>/* output/<slug>/
```

If `output/<slug>/video.mp4` does not exist, recover via the standard flow:

```bash
# One-time recovery — re-download the original video using the source URL
python -m agent.tools download "<source-url>" --out output/<slug>
```

(After downloading, re-run the `cp -r tests/regression/<slug>/*` line so
the four frozen JSONs sit on top of any freshly produced ones.)

### Step 2 — Re-run only the stages whose code changed

Use `--force` to bypass the file-existence cache (`agent/tools.py:75-81`).
Re-run only the stages the WIP phase actually touches; skip the rest.

```bash
# If transcribe / asr layer changed:
python -m agent.tools transcribe output/<slug>/video.mp4 --out output/<slug> --force

# If aggregate / paragraphs layer changed (note: aggregate has no --force flag,
# so delete the existing paragraphs.json first):
rm output/<slug>/paragraphs.json
python -m agent.tools aggregate output/<slug>/segs.json --out output/<slug>/paragraphs.json

# If frame extraction layer changed: re-extract a representative range and
# regenerate summary.md by walking the standard /summarize-video workflow:
python -m agent.tools extract_frames output/<slug>/video.mp4 --out output/<slug>/frames --fps 0.3 --start 0 --end 60
# (Then rerun the /summarize-video workflow end-to-end to produce a fresh summary.md.)
```

### Step 3 — Manual eyeball diff (Claude as verifier)

Open Claude Code and paste the prompt template from the next section.
Claude reads both files in full and reports PASS or FAIL.

**Read tests/regression/`<slug>`/summary.md AND output/`<slug>`/summary.md
in the same conversation.** Then paste the prompt template below and let
Claude judge.

## Manual-diff prompt template (copy-paste-ready)

```
Compare two summary.md files for regression-baseline drift.

OLD (frozen baseline):  tests/regression/<slug>/summary.md
NEW (just regenerated):  output/<slug>/summary.md

Read both files in full. Then evaluate along five axes:

(1) STRUCTURE — Same number of top-level sections? Same ordering of
    subsections? Same overall narrative arc?

(2) TIMESTAMPS — For every [HH:MM:SS] in NEW: does that exact second exist
    in tests/regression/<slug>/segs.json? Read segs.json and verify.

(3) CODE — Compare code blocks line-by-line. Intentional improvements
    (more accurate transcription from frames) are PASS. Fabricated lines
    not justifiable from the video are FAIL.

(4) FRAME REFS — Every ![](frames/...) path follows
    seg_<start:04d>_<index:06d>.jpg grammar?

(5) RED-LINES — Any padding text? Any timestamp not in segs.json?
    Any "感谢观看" filler? Any made-up function/class names?

Output exactly one of:

  PASS — explainable diffs only:
    - <diff 1>: <why it's intentional>
    - <diff 2>: <why it's intentional>

  FAIL — surprise drift:
    - <delta 1>: <axis violated>
    - <delta 2>: <axis violated>
```

Treat Claude's verdict as authoritative — this project has decided the
verifier is Claude, not a script (per Phase 1 D-09).

## Pass / Fail criterion

- **PASS:** All three baselines diff cleanly OR every diff is an explainable
  improvement that the WIP phase intended (e.g., "Phase 5 raised抽帧 fps,
  so the new summary references finer frame indices — diff at line N
  reflects that improvement").
- **FAIL:** Any of —
  - Structural drift not explained by the phase's stated goals
  - Timestamp drift (a `[HH:MM:SS]` in NEW that does not exist in
    `tests/regression/<slug>/segs.json`)
  - Fabricated content (made-up code, made-up function names, padding prose)
  - Broken frame filename grammar (anything not matching
    `seg_<start:04d>_<index:06d>.jpg`)

The pass criterion is "no surprise drift" judgment, not byte-equality.
Intentional improvements are welcome; unexplained drift is the failure
mode.

## Cadence (per Phase 1 D-10)

Run this runbook on all three baselines **before merging any phase that
touches `agent/` or `src/`**. Record the verdict (PASS / FAIL with
explainable-diff list) in that phase's `VERIFICATION.md` under a
`## Regression Baseline` heading. A phase that fails the regression check
does not merge until it either:
1. fixes the underlying drift, or
2. updates `tests/regression/<slug>/` with a new snapshot and explains the
   drift in the commit message.

## Encoding Audit (PRE-04)

> See [encoding-audit.md](encoding-audit.md) — populated by Plan 01-03 of
> this phase.
