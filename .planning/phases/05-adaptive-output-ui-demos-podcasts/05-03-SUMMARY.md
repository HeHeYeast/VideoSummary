---
phase: 05-adaptive-output-ui-demos-podcasts
plan: 03
subsystem: agent / docs
tags: [diarize-cli, pyannote-opt-in, ui-demo-rules, podcast-skeleton, chapters-json, vtt-priority, degrade-path, claude-md-extension, hf-token, backward-compat]

# Dependency graph
requires:
  - phase: 02-resume-infrastructure-cache-correctness
    provides: _build_sidecar / _emit_event / write_json_atomic — reused by cmd_diarize for sidecar capture + state.jsonl events + atomic JSON write
  - phase: 03-source-refactor-new-sources-youtube-local-mp4-generic
    provides: meta.json subtitle_origin field (Phase 3 SRC-08 D-10) — referenced by interview-distillation skeleton VTT fold-in (D-32)
  - phase: 04-frame-fps-automation-schedule-json-extract-frames-batch
    provides: requirements-optional.txt opt-in idiom (silero-vad / torch / torchaudio) + schedule.json default_scale field — pyannote.audio extends opt-in pattern; Podcast skeleton schedule.json fps 0.05 references existing schema
  - phase: 05-adaptive-output-ui-demos-podcasts (plan 01)
    provides: ## 视频类型变奏 chapter framework + 4 mode tag byte-equal lock + format-spec invariants — plan 03 appends UI demo / Podcast / VTT fold-in subsections without disturbing
  - phase: 05-adaptive-output-ui-demos-podcasts (plan 02)
    provides: PROFILES dict + --profile {tutorial,podcast} + whisper_repetition_guard — referenced by Podcast skeleton (use --profile podcast for ASR fallback)
provides:
  - "agent/diarize.py NEW module with diarize_audio() lazy-pyannote import + clean RuntimeError on missing dep (TEACH-08)"
  - "agent/tools.py cmd_diarize CLI subcommand + argparse + cmds dict + _DOCTOR_ARTIFACTS hook (TEACH-08)"
  - "requirements-optional.txt pyannote.audio>=4.0,<5.0 opt-in pin (D-17)"
  - "agent/sources/youtube.py subtitleslangs ['zh-Hans', 'zh-Hant', 'zh', 'en'] (D-31, WR-02 fold-in)"
  - "CLAUDE.md ## Pyannote diarization 设置（首次设置，可选）top-level section (D-15)"
  - "CLAUDE.md ### UI 操作演示子规则 with 4 sub-rules byte-equal D-20 (TEACH-09)"
  - "CLAUDE.md ### Podcast / interview 模式骨架 with chapters.json schema + 1-2 frames/chapter + blockquote replacement + content-cue speaker inference (TEACH-10 / TEACH-13 / D-19)"
  - "CLAUDE.md interview-distillation VTT fold-in: subtitle_origin=='creator' → 直接信任 VTT (D-32)"
  - ".planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-SPIKE.md (degrade fast-path decision, D-13)"
  - ".planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-VERIFY.md (final 13/13 TEACH PASS table)"
affects:
  - All future /summarize-video runs on interview-distillation videos — Claude reads CLAUDE.md Podcast skeleton and uses chapters.json + blockquote form (no diarization required)
  - Future GPU machine pyannote runs — opt-in install + HF_TOKEN already documented; diarize CLI ships ready to consume real audio
  - YouTube creator-uploaded VTT path (per Phase 3 SRC-08 D-10) — zh-Hans / zh-Hant 简繁体优先, manual subs > auto-gen; long-form interviews benefit most
  - Phase 3 deferred WR-02 closes (zero deferred warnings remain after 05-03)

# Tech tracking
tech-stack:
  added:
    - "pyannote.audio>=4.0,<5.0 (opt-in via requirements-optional.txt; not pulled by default install)"
  patterns:
    - "Lazy-import opt-in CLI idiom — Phase 4 silero-vad / detect_silence pattern fully replicated for pyannote / diarize: import inside function, raise RuntimeError with install hint on ImportError"
    - "ffprobe duration gate + CUDA detect + default-N prompt — D-16 long-running confirmation pattern; threat T-05-03-07 mitigation"
    - "HF_TOKEN read via os.environ.get + load_dotenv (process-start) — never logged (T-05-03-08); stored only in .env (gitignored)"
    - "Spike → degrade fast-path — instead of blocking on a benchmark user can't easily run, ship infrastructure (CLI + opt-in dep) and skeleton fallback (content-cue inference); future re-run produces real numbers without re-architecture"
    - "CLAUDE.md adaptive-layer extension — append new ### subsections under ## 视频类型变奏 (Plan 01) without disturbing format-spec lock or main 8-phase trunk"
    - "VTT lang priority as data-only fix — change one list literal in YouTubeDL opts; let yt-dlp's existing manual>auto fallback chain handle the rest (no new code path)"
    - "Skeleton-fold-in for interview-distillation when VTT is creator-uploaded — reuse Phase 3 subtitle_origin field as a conditional gate, no new metadata"

key-files:
  created:
    - "agent/diarize.py (93 lines — NEW; diarize_audio function + lazy pyannote.audio import + clean RuntimeError on missing dep)"
    - ".planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-SPIKE.md (59 lines — degrade fast-path decision per D-13)"
    - ".planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-VERIFY.md (119 lines — 13/13 TEACH PASS table + smoke test evidence)"
  modified:
    - "CLAUDE.md (989 → 1161 lines, +172 / -2 net)"
    - "agent/tools.py (~+125 LOC — cmd_diarize handler + argparse subparser + cmds dict entry + _DOCTOR_ARTIFACTS row)"
    - "agent/sources/youtube.py (~+5 LOC docstring + 1 list literal change — subtitleslangs zh-Hans>zh-Hant>zh>en)"
    - "requirements-optional.txt (+11 LOC comment block + pyannote.audio>=4.0,<5.0 pin)"

key-decisions:
  - "D-13 SPIKE → degrade — User selected fast-path during /gsd-autonomous; ship infrastructure + skeleton fallback instead of blocking on user-run pyannote bench"
  - "D-14 No cheap-heuristic 2-speaker fallback — Claude multimodal content-cue inference is more reliable than VAD energy + spectral centroid heuristic"
  - "D-15 HF_TOKEN .env idiom — parallel to DOUYIN_COOKIES_FILE / VE_KEY_CHEAP; CLAUDE.md doc section parallel to YouTube/抖音 setup chapters"
  - "D-16 60min+ AND no-CUDA gate verbatim — `WARNING: 60min+ 音频在 CPU 上 pyannote 预计 3-5× wall time...继续？(y/N)` byte-equal in both code (agent/tools.py:cmd_diarize) and docs (CLAUDE.md Pyannote setup section)"
  - "D-17 pyannote.audio>=4.0,<5.0 opt-in pin — extends Phase 4 requirements-optional.txt pattern; no eager import"
  - "D-19 Podcast 1-2 frames/chapter (NOT zero) — preserves visual anchors via fps 0.05 schedule.json segments per chapter"
  - "D-20 UI demo 4 sub-rules verbatim order — pixel-text uncertainty / tooltip 遮挡 / 光标不可见 / --width 1280/1920"
  - "D-21 No parallel 8-phase fork — mode picks at Phase 2, /summarize-video trunk byte-equal; Podcast / UI demo are skeleton variants, not separate workflows"
  - "D-31 / WR-02 zh-Hans>zh-Hant>zh>en VTT priority — replaces non-standard zh-CN with BCP-47 标准 codes; benefits podcast/interview-distillation mode by trusting creator VTT directly"
  - "D-32 interview-distillation VTT fold-in — when subtitle_origin=='creator', skeleton instructs Claude to skip ASR re-run and trust VTT directly (95%+ accuracy vs 70-85% for whisper on long-form)"
  - "Spike fast-path: skip user-run pyannote benchmark to keep autonomous Phase 5 momentum; document re-run procedure in SPIKE.md so future GPU machine produces real numbers"
  - "speaker_id='?' placeholder convention — degrade path skeleton uses `> [HH:MM:SS] **speaker_id=\"?\"**: \"...\"` when Claude cannot infer speaker from content cues; better than guessing"

patterns-established:
  - "Spike-to-degrade fast-path — when blocking benchmark is high-friction and infrastructure value is independent of bench result, ship infrastructure + degrade skeleton + document re-run procedure; bench becomes a reversible upgrade decision rather than a milestone-blocker"
  - "Threat-model-driven CLI gates — D-16 default-N prompt, T-05-03-07/08 token-not-logged + sidecar-strips-token, all wired via single cmd_diarize handler"
  - "Skeleton-as-prompt-prior + degrade-path = robust adaptive skeletons — Podcast skeleton documents BOTH ideal path (with diarization.json) AND degrade path (content-cue inference + speaker_id='?' placeholder); single source of truth for both states"
  - "Conditional VTT trust via existing metadata field — interview-distillation + subtitle_origin=='creator' branch reuses Phase 3 SRC-08 instead of introducing new gate; zero new code, pure documentation contract"
  - "Verify.md as PASS-table artifact — 13/13 TEACH-XX traceability with grep evidence + smoke test logs; serves as both verification record and onboarding doc for future plan dependencies"

requirements-completed: [TEACH-08, TEACH-09, TEACH-10, TEACH-13]

# Metrics
duration: ~25min
completed: 2026-05-02
---

# Phase 05 Plan 03: UI Demo + Podcast + Diarize Opt-In + VTT Priority Summary

**Phase 5 final plan: ships pyannote-opt-in `diarize` CLI infrastructure (agent/diarize.py + agent/tools.py + requirements-optional.txt) plus content-cue degrade-path skeletons in CLAUDE.md (UI demo 4 sub-rules + Podcast / interview chapters.json schema + blockquote form) plus Phase 3 deferred WR-02 fold-in (zh-Hans>zh-Hant>zh>en VTT priority). Spike decision: degrade fast-path — bench skipped, infrastructure ships ready for GPU upgrade.**

## Performance

- **Duration:** ~25 min (across 6 tasks)
- **Started:** 2026-05-02T00:45:54+08:00 (Task 2 first commit)
- **Completed:** 2026-05-02T01:10:47+08:00 (Task 6 verify commit)
- **Tasks:** 6 / 6
- **Files created:** 3 (agent/diarize.py, 05-03-SPIKE.md, 05-03-VERIFY.md)
- **Files modified:** 4 (CLAUDE.md, agent/tools.py, agent/sources/youtube.py, requirements-optional.txt)

## Task Commits

Each task committed atomically with `--no-verify` per parallel-execution protocol:

| # | Task | Commit | Type |
|---|------|--------|------|
| 1 | USER SPIKE: pyannote on Win11 + CPU (degrade fast-path) | `c712646` | docs |
| 2 | requirements-optional.txt + pyannote.audio>=4.0,<5.0 (D-17) | `82d0119` | feat |
| 3 | agent/sources/youtube.py VTT lang priority zh-Hans>zh-Hant>zh>en (D-31, WR-02) | `0fa2f3c` | feat |
| 4 | agent/diarize.py NEW + agent/tools.py cmd_diarize (TEACH-08, D-13..D-17) | `80975b7` | feat |
| 5 | CLAUDE.md degrade-path podcast/UI/interview skeletons + diarize opt-in docs (TEACH-09/10/13) | `6477eaa` | feat |
| 6 | Final verification — 13/13 TEACH-XX traceability + smoke tests | `2237d74` | docs |

## Accomplishments

- **TEACH-08** (diarize CLI): `python -m agent.tools diarize <audio.wav> --out <d.json>` ships with HF_TOKEN guard + ffprobe duration probe + 60min+ AND no-CUDA gate (D-16 verbatim) + sidecar/state.jsonl events + diarization.json {version: 1, turns: [...]} schema
- **TEACH-09** (UI demo 4 sub-rules): CLAUDE.md `### UI 操作演示子规则` with byte-equal D-20 verbatim — pixel-text quote-with-uncertainty / tooltip 遮挡检测 / 光标不可见兜底 / `--width 1280/1920` 4K override
- **TEACH-10** (podcast skeleton): CLAUDE.md `### Podcast / interview 模式骨架` with 5 steps — chapters.json取代silence-gap聚合 / fps 0.05 1-2 frames per chapter / blockquote replaces image embeds / content-cue speaker inference (degrade path) / optional Step 5 diarization.json fold-in
- **TEACH-13** (chapters.json schema): documented in CLAUDE.md as `{version, video, chapters: [{start, end, topic_title, summary_line, speaker_id?}]}`; Claude-written via Write tool (no cmd_chapters subcommand — K5 "Claude is decider")
- **D-15** Pyannote setup section: CLAUDE.md `## Pyannote diarization 设置（首次设置，可选）` lands between YouTube section and Windows zh-CN section; documents pip install + HF token + community-1 license URL + CPU vs GPU + --allow-long flag
- **D-31 / WR-02** VTT priority fold-in: `agent/sources/youtube.py` subtitleslangs locked at `["zh-Hans", "zh-Hant", "zh", "en"]` (BCP-47 standard codes; old `zh-CN` form removed); Phase 3 deferred warning closes
- **D-32** interview-distillation VTT fold-in: skeleton instructs Claude to trust VTT directly when `meta.json.subtitle_origin == "creator"` AND mode == "interview-distillation" (95%+ accuracy vs 70-85% whisper on long-form per PITFALLS P3.3)
- **D-13 spike fast-path**: SPIKE.md records degrade decision with rationale (skip ~700MB pyannote weights download + HF account friction + 12-20min CPU bench); infrastructure ships ready for future GPU re-run
- **Threat mitigations**: T-05-03-07 (default-N prompt for 60min+ CPU) + T-05-03-08 (HF_TOKEN never logged; sidecar omits token) implemented in cmd_diarize and agent/diarize.py

## D-XX Decision Landing Points

| Decision | Where it landed |
|----------|-----------------|
| D-13 (spike → degrade) | SPIKE.md "My decision: degrade" line; degrade path skeletons live in CLAUDE.md Podcast skeleton |
| D-14 (no cheap-heuristic fallback) | CLAUDE.md Step 4 "5 条说话人内容线索推断" replaces VAD energy heuristic |
| D-15 (HF_TOKEN .env idiom) | CLAUDE.md `## Pyannote diarization 设置` step 2; agent/tools.py:cmd_diarize reads via os.environ.get |
| D-16 (60min+ AND no-CUDA gate verbatim) | agent/tools.py:cmd_diarize lines 791-803 + CLAUDE.md Pyannote setup section blockquote |
| D-17 (pyannote opt-in pin) | requirements-optional.txt L21-31 |
| D-19 (1-2 frames/chapter NOT zero) | CLAUDE.md Podcast skeleton Step 2 with fps 0.05 schedule.json example |
| D-20 (UI demo 4 sub-rules verbatim order) | CLAUDE.md `### UI 操作演示子规则` numbered list 1-4 byte-equal |
| D-21 (no parallel 8-phase fork) | /summarize-video trunk byte-equal; mode hints inline blockquotes only |
| D-30..D-31 (WR-02 fold-in) | agent/sources/youtube.py L256 subtitleslangs literal |
| D-32 (interview-distillation VTT fold-in) | CLAUDE.md `#### VTT fold-in（D-32 — 与 Phase 3 subtitle_origin 联动）` subsection |

## Spike Decision: degrade (Fast-Path)

User selected `degrade` fast-path during /gsd-autonomous to maintain Phase 5 milestone velocity. The full pyannote 4.0 + community-1 model benchmark on real podcast audio was deliberately skipped (see 05-03-SPIKE.md for full rationale). Trade-offs:

**Skipped:**
- HF account registration + community-1 license acceptance
- ~700 MB pyannote weights download on top of existing silero-vad
- 12-20 min CPU bench on 4-min podcast audio

**Still shipped:**
- `agent/diarize.py` + `cmd_diarize` CLI wrapper (Task 4)
- `requirements-optional.txt` pyannote pin (Task 2)
- CLAUDE.md degrade-path Podcast / interview-distillation skeleton (Task 5) — uses `speaker_id="?"` placeholder OR named blockquote attribution where Claude infers speaker from content cues
- Re-run procedure documented in SPIKE.md for future GPU machine

**Implication for Plan 03 task 5 ship form:**

Task 5 CLAUDE.md updates use the **degrade-path** skeleton form throughout:
- Step 4 "从内容线索推断说话人" is the primary path (5 inference cues: 开场白 / 谁问谁答 / 提问语气 vs 回答语气 / blockquote attribution / 嘉宾名 from intro)
- Step 5 (optional diarization.json) is the upgrade path documented for future GPU users
- chapters.json schema includes optional `speaker_id?: string` field for forward compatibility (degrade path doesn't fill it; future GPU diarization populates it)

## 13/13 TEACH-XX Phase 5 Traceability

Full evidence in `05-03-VERIFY.md`:

| Req | Phase | Status | Where |
|-----|-------|--------|-------|
| TEACH-01 | 5/01 | PASS | CLAUDE.md `#### Mode: <4-mode-tag>` × 4 byte-equal |
| TEACH-02 | 5/01 | PASS | format-spec lock 4 invariants in CLAUDE.md `### 格式锁定` |
| TEACH-03 | 5/01 | PASS | 8 hand-authored skeletons (4 modes × 2) |
| TEACH-04 | 5/01 | PASS | plan.md `classification_evidence` field |
| TEACH-05 | 5/01 | PASS | depth_plan.md optional rule documented |
| TEACH-06 | 5/02 | PASS | agent/asr_v2.py PROFILES dict |
| TEACH-07 | 5/02 | PASS | agent/tools.py argparse `--profile {tutorial,podcast}` (2 subparsers) |
| TEACH-08 | **5/03** | **PASS** | agent/diarize.py + agent/tools.py cmd_diarize + requirements-optional.txt |
| TEACH-09 | **5/03** | **PASS** | CLAUDE.md UI demo 4 sub-rules verbatim |
| TEACH-10 | **5/03** | **PASS** | CLAUDE.md Podcast skeleton (chapters.json + 1-2 frames + blockquote) |
| TEACH-11 | 5/02 | PASS | agent/tools.py whisper_repetition_guard + transcribe_warnings.json |
| TEACH-12 | 5/02 | PASS | src/asr.py PROFILES VAD per-profile (tutorial 500/0.5, podcast 800/0.6) |
| TEACH-13 | **5/03** | **PASS** | CLAUDE.md chapters.json schema (`{start, end, topic_title, summary_line, speaker_id?}`) |

## ROADMAP Success Criteria Mapping

| SC | Source | Status |
|----|--------|--------|
| SC1 (mode tags + format lock) | Plan 01 | PASS |
| SC2 (8 hand-authored exemplars) | Plan 01 | PASS |
| SC3 (--profile podcast longer paragraphs) | Plan 02 | PASS |
| SC4 (diarize CLI opt-in working) | **Plan 03 (this)** | PASS (CLI ships; bench deferred per spike fast-path) |
| SC5 (whisper-repetition guard, no auto-delete) | Plan 02 | PASS |

## Backward-Compat Verification (K3)

`05-03-VERIFY.md` records evidence:

- **5 core commands** (`download / transcribe / extract_frames / aggregate / cleanup_frames`) all `--help` exit 0 byte-equal — no flags removed, only `transcribe` and `aggregate` gained `--profile` (Plan 02) which defaults to `tutorial` = byte-equal Phase 2 behavior
- **CLAUDE.md 4 critical sections** (抖音 / YouTube / Windows zh-CN / 决策支持) `git diff c7126463 -- CLAUDE.md` count = 0 (zero touches)
- **17 archived baselines** still re-runnable byte-equal (sample BV1C9QCBdE1U: 170 segs preserved per Plan 02 REGRESSION.md; aggregate produces same byte-output without `--profile` flag)
- **agent/sources/youtube.py 8 helper functions** preserved (Phase 3 5-class preflight + match + fetch + _classify_stderr + _detect_subtitle_origin + _build_yt_dlp_argv + _redacted_proxy_log + warn_if_yt_dlp_stale + youtube_preflight)
- **WR-02 closed** — Phase 3 deferred warning resolves; zero deferred items remain after 05-03

## Deferred Items (v2 Candidates)

These remain documented but explicitly out-of-scope for Phase 5:

- **`speakers.json` real-name resolution** — map pyannote abstract `SPEAKER_NN` → real names (Karpathy / Lex); v2 may automate via voice-fingerprint corpus
- **`--no-frames` flag for podcast mode** — Phase 5 lands at 1-2 frames/chapter compromise; complete-skip is v2
- **`chapters_check` bidirectional validator** — verify chapters.json topic alignment with paragraph content; Phase 5 trusts Claude's judgment
- **Pyannote on GPU `--device cuda` flag** — D-16 gate currently directs user to "等 GPU 机器再跑"; pyannote 4.0 supports CUDA, just not exposed yet via CLI
- **`--width 1280/1920` auto-detect** — currently manual judgment in skeleton; v2 may probe video resolution via ffprobe and suggest

## Decisions Made

Beyond CONTEXT.md D-13..D-17, D-19..D-21, D-30..D-32 / TEACH-08/09/10/13:

1. **Spike fast-path adoption** (vs blocking on user pyannote bench) — keeps autonomous /gsd-autonomous momentum; SPIKE.md documents re-run procedure so future GPU result is straightforward upgrade, not re-architecture
2. **`speaker_id="?"` placeholder convention** in degrade path — explicit "I don't know" beats fabricated speaker labels (CLAUDE.md quality red line: 不注水不编造)
3. **CLAUDE.md ## Pyannote setup placement at line 86** (between YouTube and Windows zh-CN) — parallels existing 抖音 / YouTube opt-in setup chapter convention, avoids reordering
4. **chapters.json `speaker_id?: string` optional field** — forward-compat for future GPU diarization without breaking degrade-path schemas
5. **interview-distillation skeleton VTT fold-in as conditional gate** (not new metadata field) — reuses Phase 3 `subtitle_origin` instead of introducing `trust_vtt: bool`; zero new code path
6. **Test verification gates the artifacts not the bench** — VERIFY.md confirms TEACH-08 by `--help` exit 0 + 2 error-path RuntimeError smoke tests, not by full pyannote run; consistent with spike fast-path

## Threat Mitigations Implemented

Per 05-03-PLAN.md threat_model:

- **T-05-03-01** (HF_TOKEN to git): `.env` already gitignored; CLAUDE.md doc explicitly says "不要 commit `.env`"
- **T-05-03-02** (pyannote model hash): accept (single-user offline ¥0; HF supply chain out-of-scope)
- **T-05-03-03** (spike self-report): accept (K2 "user is final reviewer")
- **T-05-03-04** (diarization.json sensitive): accept (output/ gitignored; sole consumer)
- **T-05-03-05** (DoS via 60min+ CPU): mitigated via D-16 default-N prompt
- **T-05-03-06** (malicious VTT XSS): existing src/asr.py:parse_vtt re.split + utf-8 + no eval; lang priority change doesn't introduce new parsing
- **T-05-03-07** (auto-yes on long-running): mitigated — input() defaults to N; `y` required explicit
- **T-05-03-08** (HF_TOKEN in logs): mitigated — agent/diarize.py logs only `<set>` / `<empty>` placeholder; sidecar.tools doesn't include token

## Self-Check: PASSED

All claimed artifacts verified to exist:

- ✓ `agent/diarize.py` (93 lines, NEW)
- ✓ `agent/tools.py` cmd_diarize at line 726 + diarize subparser at line 1127 + cmds dict at line 1173
- ✓ `requirements-optional.txt` pyannote.audio>=4.0,<5.0 at line 31
- ✓ `agent/sources/youtube.py` subtitleslangs ["zh-Hans", "zh-Hant", "zh", "en"] at line 256
- ✓ `CLAUDE.md` ## Pyannote diarization 设置 at line 86 + ### UI 操作演示子规则 + ### Podcast / interview 模式骨架
- ✓ `.planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-SPIKE.md` (degrade decision)
- ✓ `.planning/phases/05-adaptive-output-ui-demos-podcasts/05-03-VERIFY.md` (13/13 TEACH PASS table)

All claimed commits verified to exist via `git log c7126463^..HEAD --oneline`:
- ✓ 82d0119 (Task 2)
- ✓ 0fa2f3c (Task 3)
- ✓ 80975b7 (Task 4)
- ✓ c712646 (Task 1 SPIKE)
- ✓ 6477eaa (Task 5)
- ✓ 2237d74 (Task 6)
