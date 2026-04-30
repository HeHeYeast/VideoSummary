# Feature Research

**Domain:** Video → structured Markdown tutorials, single-user, Claude-as-decision-maker, ¥0
**Researched:** 2026-04-30
**Confidence:** MEDIUM (ecosystem mapping based on WebSearch + product pages; pattern claims for niche workflows like "code-frame-aware abstraction" are LOW since no off-the-shelf competitor does what this project does)

## Ecosystem Snapshot (so categories make sense)

What "video → notes" tools actually do in 2026, by what surface they expose to the user:

| Tool / Class | Output Style | Frame Handling | Claude-Code-Like Decisions? |
|---|---|---|---|
| **BibiGPT** | Bullet summary + timestamps + mind map; "key frames" = a handful of stills slotted into the markdown; supports B站/YouTube/抖音/local file (30+ platforms) ([source](https://bibigpt.co/en)) | LLM-driven sampling, opaque heuristic, no per-segment fps control | No — fixed pipeline, fixed prompt template |
| **NoteGPT** | Bullets + chapter list + Q&A chat over transcript ([source](https://notegpt.io/)) | Sparse stills, mostly transcript-driven | No |
| **NotebookLM (Google)** | Now also generates *outbound* video overviews from sources (Cinematic / Explainer / Brief styles, "Steering Prompt") ([source](https://blog.google/innovation-and-ai/products/notebooklm/generate-your-own-cinematic-video-overviews-in-notebooklm/)) | Doesn't extract input-video frames as a primary feature; treats YouTube as another text source | Partial — Steering Prompt biases output but the structure is fixed |
| **Otter.ai / Notta** | Meeting-style summary, action items, speaker diarization ([source](https://www.notta.ai/en/blog/otter-ai-vs-descript)) | None / negligible | No |
| **Descript** | Editable transcript-as-script, video editing, overdub ([source](https://www.notta.ai/en/blog/otter-ai-vs-descript)) | All frames preserved (it IS the editor) | No — user is the decider |
| **BiliNote (open source)** | "AI 视频笔记生成工具" — markdown notes with selected frames embedded ([source](https://github.com/JefferyHcool/BiliNote)) | LLM-chosen "important moments", local-runnable | Partial — closest open-source analog, but still "one-shot generate" not multi-phase Claude-driven |
| **Podcast tools (Mapify, AskSia, ScreenApp)** | Speaker-attributed quotes, chapters, mind map ([source](https://www.podpak.co/blog/ai-podcast-summarizers-compared)) | N/A — audio only | No |
| **Screen-recorder UX tools (DemoCreator, FocuSee)** | Recording-time cursor highlight + auto-zoom, NOT post-hoc analysis of an arbitrary video ([source](https://democreator.wondershare.com/video-editor/add-mouse-effects.html)) | They emit highlighted videos, they don't read them | N/A |
| **PySceneDetect** | Library, not a product. detect-content ≈ histogram-diff frame scoring; recommended threshold 27 for cuts ([source](https://www.scenedetect.com/cli/)) | Detects shot changes / slide changes; fps-agnostic | N/A (it's a primitive) |

**Key takeaway:** Every general-purpose tool is "transcribe → LLM template-fill → embed a few frames." No mainstream tool varies output structure per video, treats the LLM as an iterating multimodal reader, or supports pause/resume/swap-strategy across pipeline stages. **The current videoSummary workflow already does things the ecosystem doesn't.** That changes what's table stakes vs differentiator.

---

## Feature Landscape

### Table Stakes (Users Expect These — Missing = Feels Broken)

These are baselines this user (and any reasonable user of a video-doc tool) will assume the new milestone delivers. Some are already shipped — listed for completeness so REQUIREMENTS.md doesn't accidentally drop them.

| Feature | Why Expected | Complexity | Target-Feature Tag | Notes |
|---|---|---|---|---|
| YouTube URL input | yt-dlp's flagship platform; not having it after B站/抖音 work feels like an omission | LOW | T3 (YouTube + generic) | Already supported by `src.download.download` (yt-dlp). Need: confirm `agent.tools download` routes YouTube without douyin code path; verify cookie/SESSDATA story for age-gated/region-locked. Likely a thin routing fix, not a build. |
| Local mp4 path input | Already-downloaded video should not require uploading to a URL or re-downloading | LOW | T4 (local file) | Skip download stage entirely; jump to transcribe. Trivial CLI plumbing — `agent.tools transcribe` already accepts a path. The "feature" is really `meta.json` synthesis from a local file (title from filename, no UP主, etc.) so downstream stages don't break. |
| Generic yt-dlp passthrough | Twitter/X video, Vimeo, niche game-dev sites — yt-dlp covers ~1500 sites; users expect "if yt-dlp can grab it, this can" | LOW | T3 | Already works via `src.download.download` for non-Douyin URLs. Mostly documentation + confirming meta.json shape stays consistent. |
| Re-run after partial failure without losing prior work | Current code already does this by artifact-existence caching, BUT it's silent — when something fails mid-frame-extraction, the user doesn't know what's safe to keep | LOW–MEDIUM | T6 (resume) | Today: `cmd_extract_frames` skips a segment only if the *exact glob* exists. Tomorrow: explicit "what artifacts exist" surface so Claude can plan the resume. See Differentiator: explicit pipeline state. |
| Backward-compat `output/<slug>/` layout | 17 queued videos, 6 already-archived. Breaking the directory convention = re-archiving past work | LOW (constraint, not build) | (constraint underlying T1–T7) | Hard line: any new artifact files (e.g. `frame_plan.json`, `pipeline_state.json`) live alongside existing `meta.json` / `segs.json` / `paragraphs.json` / `frames/` and don't displace them. |
| Speaker labels for podcast/interview | Otter, Notta, AskSia, Mapify all do this for podcasts; without it, podcast docs degenerate to "soup of statements" with no attribution ([source](https://www.podpak.co/blog/ai-podcast-summarizers-compared)) | MEDIUM | T5b (podcast) | faster-whisper has no diarization. Options: (a) `pyannote.audio` (Apache-2 weights but HF-hub gated, runs on CPU/GPU locally — meets ¥0 if license accepted); (b) `whisperx` (wraps faster-whisper + pyannote, well-trodden path); (c) skip diarization, let Claude attribute by content cues — works for 2-speaker interviews but not panels. **MUST resolve in PITFALLS / STACK.** |
| Timestamp accuracy preserved | Already ship; mention because all competitor tools advertise "click timestamp to jump" — file:// markdown doesn't get that, but timestamps must remain round-trippable to source video | LOW (already works) | (cross-cutting) | seg_<start>_<index>.jpg name encoding already does this (ARCHITECTURE.md §Data Flow). Don't break it. |
| Whisper-grade transcription on YouTube/local | Same ¥0 ASR pipeline must work regardless of source | LOW | T3, T4 | faster-whisper is source-agnostic; no work needed beyond `extract_audio` accepting any mp4. |

### Differentiators (Where This Project Beats Generic Tools)

The existing workflow's "Claude is the brain" model is already a differentiator — these features double down on it instead of regressing toward template-fill tools.

| Feature | Value Proposition | Complexity | Target-Feature Tag | Notes |
|---|---|---|---|---|
| **Claude-decided document shape** (no fixed template; per-video decision of "复刻指南 / 原理讲解 / 延展" mix) | Every competitor outputs the same shape every time. This is the *Core Value* — "real teaching value, not subtitle translation." User said quick-ref/deep-dive multi-output is OOS, so it MUST be one adaptive doc. ([PROJECT.md L46](.planning/PROJECT.md)) | MEDIUM | T1 (adaptive output) | Implementation = prompt/skill-level, not Python-level. CLAUDE.md gets a Phase 2.5 ("decide which teaching dimensions this video supports — argue for each"), Phase 5 outline gets a "structure rationale" header. The tooling change is zero; the workflow change is pedagogical. Verifying success: a code-tutorial → "复刻指南"-heavy doc; a podcast → "principles + key quotes" doc; a UI demo → "操作步骤 + 设计意图" doc. |
| **Per-segment fps schedule emitted by Claude, batch-executed by tool** | Today Claude shells out N times manually choosing fps/start/end per segment — friction is real even though Claude is the decider. A `frame_plan.json` ({start,end,fps}[]) consumed by one CLI call removes operator overhead without removing decision authority. | MEDIUM | T2 (frame fps automation) | New CLI: `extract_frames_plan <plan.json> --video V --out frames/`. Plan format: `[{"start":0,"end":30,"fps":0.2,"label":"intro"}, ...]`. Plan is written by Claude into `output/<slug>/frame_plan.json` and is itself an artifact (auditable, re-runnable). DOES NOT replace `extract_frames`; both coexist. **Anti-pattern to avoid:** auto-generating the plan from heuristics — that crosses the "Claude is decider" line (PROJECT.md K Decision: "Claude Code 决策权不外移"). |
| **Optional scene-change probe (decision aid, not decision)** | PySceneDetect detect-content gives "here are the moments where the picture changed" — Claude can read that as *evidence* for fps planning ("dense slide-change region → higher fps") without delegating decision. Maps to user's pain: "fps decision摩擦最重" | MEDIUM | T2 (supports T1 indirectly) | New CLI: `python -m agent.tools scene_probe <video> --out scenes.json` returning `[{t, score}]`. Local, ¥0 (PySceneDetect is BSD, opencv-python). Claude reads scenes.json + paragraphs.json, *then* writes frame_plan.json. **Anti-pattern guarded:** if scenes.json gets used as the plan directly without Claude inspecting it, this slides into "tool replaces judgment." Document the boundary explicitly. |
| **Explicit pipeline state surface** ("what artifacts exist for this slug, what's stale, what's missing") | Today resume works *implicitly* by artifact existence. When the user re-runs after a failure or wants to swap strategies, they have to mentally diff the directory. A `python -m agent.tools status output/<slug>` returning a table of stages / present / age / parameters used = enables Claude to plan resume confidently. | SMALL | T6 (mid-artifact resume) | Pure read-only command, scans for `meta.json` `segs.json` `paragraphs.json` `frames/seg_*` `frame_plan.json` `summary.md`, prints existence + mtime + (if available) the parameters that produced them. The `--force` flag already exists on `transcribe`; extending to other stages is the active build. The harder question: how to *invalidate* a downstream artifact when an upstream one was re-run with new params (e.g. re-aggregated paragraphs.json should mark `summary.md` stale). Recommendation: surface staleness, don't auto-delete — Claude decides. |
| **Multimodal frame reading by Claude (already shipped, name explicitly)** | This is the project's signature move. Every other tool stops at "embed thumbnail." Claude reading the JPEG and transcribing code line-by-line beats every consumer OCR API. | n/a (shipped) | (shipped, T1 amplifier) | Mentioned because future features must not regress this. E.g. if frame extraction gets aggressive auto-pruning, must preserve "Claude can re-extract a missed moment." |
| **Per-video-type writing modes inside one adaptive doc** | Code tutorial = step+code-block-from-frame; UI demo = step+screenshot+intent; podcast = quote-attributed-to-speaker + theme-grouped section + timeline. Generic tools have *one* output mode. | MEDIUM (prompt + skill work, no python) | T1 + T5a (UI) + T5b (podcast) | Implemented as additions to `/summarize-video` skill (or sibling skills), not as code. Each mode has its own quality red-line list (e.g. podcast: "every claim has a speaker", UI demo: "every step has a frame"). |
| **Speaker diarization for podcast/interview** (if added) | See table-stakes row above; the differentiator angle is *integration* — the diarization output flows into frame_plan.json (skip frames during low-signal back-and-forth) and into the writing mode (quote attribution). Generic podcast tools do diarization in isolation. | MEDIUM-HIGH | T5b | New artifact: `speakers.json` ({segment_id → speaker_label}). New aggregator: paragraphs become speaker-bounded. PITFALLS.md must address pyannote license, HF-hub auth, local-only constraint. |
| **Optional multi-agent parallelism via worktree-style isolation** | Different videos in different `output/<slug>/` dirs are already isolated; the gap is the user wanting *concurrent Claude Code sessions* without crosstalk. | LOW (mostly documentation + verifying no shared mutable state) | T7 (multi-agent) | The codebase already has no shared state (filesystem-per-slug). The "feature" is mostly: (a) confirming `vendor/douyin_api/config.yaml` patching is process-safe, (b) documenting "two terminals = OK", (c) maybe a `--lock` file per slug to prevent two agents touching the same video. **De-prioritize per PROJECT.md K Decision: "做不到也没关系".** |
| **`output/<slug>/` self-describing artifacts** (already; reaffirm) | Every artifact is reproducible from `video.mp4` + `meta.json`. Means: portable across machines, archivable, no DB to lose. Generic tools lock you into their cloud. | n/a (shipped) | (constraint underlying everything) | Reaffirm in REQUIREMENTS.md as a guardrail: any new feature MUST land its state on disk in this directory. No SQLite, no .cache/, no ~/.config. |

### Anti-Features (User Has Explicitly Said NO; Documenting So They Don't Sneak Back)

| Feature | Why Surface-Appealing | Why Wrong For This Project | Alternative |
|---|---|---|---|
| Multi-output document modes (separate quick-ref + deep-dive .md) | Every Notion / Obsidian power-user does this; "more output = more value" intuition | User explicitly chose Claude-adaptive single doc over template multi-output (PROJECT.md K Decision row 2) | Adaptive single doc — Claude picks emphasis per video |
| Fully automatic fps/scene/outline (zero human review) | "Just give me the doc" is the entire BibiGPT pitch | Defeats Core Value; user diagnosed BibiGPT-style as "字幕翻译式" — that *is* what fully-auto looks like at this complexity ceiling. Claude-as-decider is non-negotiable (PROJECT.md Constraints) | Reduce *operator* friction (frame_plan.json) without reducing *decision* surface |
| Queue auto-runner / batch-mode unattended ("process all 17 videos overnight") | Tempting given the queue exists; cron-job aesthetic | OOS per PROJECT.md ("队列全自动无人值守批跑"). Reasoning: each video needs its adaptive shape decision; batching forces template regression. Manual one-by-one trigger is acceptable. | Manual triggering remains; differentiator is the *speed* of one run, not the count |
| Web UI / dashboard / cloud sync | Every YC-style "video AI" startup ships this | OOS — single-user, local, ¥0. A web UI implies a server, auth, SaaS surface, all of which kill the cost guarantee | Markdown files in `output/`; user already opens them in their editor of choice |
| Multi-user / accounts / sharing | "What if your friend wants to use this" | OOS — single-user author tool (PROJECT.md Constraints). Adding auth = adding paid infra = breaks ¥0 | If sharing is needed, it's `git push` of `output/<slug>/`. Markdown is the share format. |
| Paid LLM/ASR/Vision API as fallback ("use cheap GPT-4o-mini for fast mode") | "Cheap" is tempting; existing `src/` codebase has a budget guard for this | OOS — ¥0 is hard constraint, ranked above teaching value (PROJECT.md Constraints + K Decision row 1) | `src/` legacy stays on disk for archaeological value but is not invoked by any new feature |
| Translation / multi-lang output | NotebookLM ships 50+ languages; perceived parity gap | Out of scope — Chinese/English mix is the actual user need, not internationalization. Markdown can hold both | If user wants English, ask Claude in English in the skill. |
| Cursor-highlight overlay on UI demo frames | Screen-recorder tools (DemoCreator etc.) do this; intuitive "make UI demos clearer" feature ([source](https://focusee.imobie.com/use-cases/mouse-pointer-highlight.htm)) | Those tools do it at *recording time*. Detecting and overlaying clicks on already-captured arbitrary video would require frame-by-frame mouse tracking (cursor-template matching or YOLO) — large complexity, ¥0-incompatible if it needs a vision API, and the user didn't ask for it | Claude can describe "click here on the X panel" from reading the frame; cursor visibility is upstream-recorder's problem |
| In-tool Markdown editor / preview | Convenient; competitor tools all have one | OOS — user has VS Code / Obsidian. Editor is not the moat | `output/<slug>/summary.md` opens in the editor of choice |
| Quote-extraction-as-shareable-card (sound bite generation) | Podcast tools ship this ([source](https://www.podpak.co/blog/ai-podcast-summarizers-compared)) | Adjacent to need but veers into "content marketing" use case, not "learning" use case | Quotes embedded inline in podcast-mode doc with timestamp; user can copy them out |
| Real-time / streaming summarization | "Live notes during a meeting" — Otter.ai's pitch | Use case mismatch — this project is for already-recorded learning content; live capture is a different product | Out of scope; mention only to forestall feature-envy |

---

## Feature Dependencies

```
T1 Adaptive Output (Claude-decided doc shape)
    ├── enhances ── T2 Frame fps automation
    │                   └── enhances ── (optional) Scene-change probe
    ├── enhances ── T5a UI demo writing mode
    └── enhances ── T5b Podcast writing mode
                        └── requires ── Speaker diarization (decision: pyannote vs content-cue heuristic)

T3 YouTube + generic yt-dlp ─── independent (uses src.download path that already handles it)
T4 Local mp4 input ────────── independent (uses agent.tools transcribe directly)

T6 Mid-artifact resume
    ├── requires ── Pipeline state surface (status command)
    └── enhances ── all other features (anything Claude re-decides leaves a stale tail)

T7 Multi-agent parallelism (NTH)
    └── requires ── per-slug isolation already holds; needs lock-file or explicit doc

Backward compat
    └── conflicts ── any change to output/<slug>/ layout
                       (mitigation: NEW artifacts only, never rename existing ones)
```

### Dependency Notes

- **T1 (Adaptive Output) is the umbrella feature.** Without it, T5a/T5b are just "more templates." With it, every other feature serves the per-video judgment. REQUIREMENTS.md should treat T1 as the primary deliverable; T2 is its operator-friction reducer; T3/T4 are inputs; T5a/T5b are output specializations; T6 is robustness; T7 is operator scaling.
- **T2 (frame fps automation) shouldn't fold the optional scene-probe into core.** Two artifacts (`frame_plan.json` written by Claude, `scenes.json` optionally produced by tool) keeps the decision boundary auditable. If the probe replaces the plan, you've shipped BibiGPT.
- **T5b (podcast) hard-depends on a diarization decision.** Three options; pick one in STACK.md and commit. Without diarization, podcast docs are noticeably worse than dedicated podcast tools — and the user's queue contains real podcast/interview content per the milestone context.
- **T6 (resume) is mostly a status-surface feature, not a pipeline-rewrite.** The existing artifact-cache implements the "skip-if-present" half; the build is the "tell me what's present" half.
- **T7 conflicts with vendor config patching.** `vendor/douyin_api/crawlers/douyin/web/config.yaml` is mutated at runtime by `agent/douyin_downloader.py`. Two parallel Douyin downloads = race condition. Mitigations: (a) lock around the patch + restore, (b) per-process config copy, (c) skip if the same slug. Document explicitly even though T7 is NTH.
- **Backward compat constraint applies pervasively.** New artifacts (`frame_plan.json`, `scenes.json`, `speakers.json`, `pipeline_state.json` if needed) live in `output/<slug>/` next to existing ones. No new top-level dirs. No renames. No format changes to `segs.json` / `paragraphs.json` / `meta.json`.

---

## MVP Definition

### Launch With (this milestone, "v1" of new capabilities)

- [ ] **T1 Adaptive output** (Core Value deliverable; mostly skill/prompt work, complexity MEDIUM, no python)
- [ ] **T2 Frame fps automation via `frame_plan.json`** (most-cited friction; complexity MEDIUM, new CLI subcommand)
- [ ] **T3 YouTube + generic yt-dlp** (low-cost parity; verify routing in `cmd_download` and that `meta.json` shape is consistent)
- [ ] **T4 Local mp4 path** (almost free; mostly `meta.json` synthesis from filename)
- [ ] **T6 Pipeline status command + explicit `--force` flags per stage** (small, large robustness payoff)
- [ ] **Backward-compat verification** — Re-run `/summarize-video` against an already-archived video (e.g. `BV132wizyEEB`) and confirm no regression

### Add After Validation (v1.x in same milestone if time, else next)

- [ ] **T5a UI demo writing mode** (skill addition; needs 1–2 real UI-demo videos in queue to validate)
- [ ] **T5b Podcast writing mode** (skill + diarization stack decision)
- [ ] **Optional scene-change probe** (`scenes.json`) (only if T2's `frame_plan.json` proves it would help — empirical, not speculative)
- [ ] **Stale-artifact detection** in status (currently surfaced as info; auto-detect if downstream is older than upstream)

### Future Consideration (defer to next milestone)

- [ ] **T7 Multi-agent parallelism** (NTH per user; document concurrency safety, lock-file if pressure rises)
- [ ] **Quote-card / sound-bite extraction** (only if user's actual queue trends toward shareable podcast clips, which it currently does not)
- [ ] **Auto-fps-plan from scenes + transcript** (would cross the "Claude is decider" line; reconsider only if the user explicitly relaxes that constraint)

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Target Tag |
|---|---|---|---|---|
| T1 Adaptive output (Claude-decided doc shape) | HIGH | MEDIUM | P1 | T1 |
| T2 frame_plan.json batch executor | HIGH | MEDIUM | P1 | T2 |
| T3 YouTube + generic yt-dlp routing | HIGH | LOW | P1 | T3 |
| T4 Local mp4 input | MEDIUM | LOW | P1 | T4 |
| T6 Pipeline status command + explicit --force | MEDIUM | LOW | P1 | T6 |
| Backward-compat re-run verification | HIGH (constraint) | LOW (test, not build) | P1 | (constraint) |
| T5a UI demo writing mode | MEDIUM | MEDIUM | P2 | T5a |
| T5b Podcast writing mode + diarization | MEDIUM-HIGH | MEDIUM-HIGH | P2 | T5b |
| Scene-change probe (`scenes.json`) | MEDIUM | MEDIUM | P2 | T2 amplifier |
| Stale-downstream auto-detect in status | LOW-MEDIUM | LOW | P2 | T6 amplifier |
| T7 Multi-agent parallelism + lock | LOW (per user) | LOW (mostly docs) | P3 | T7 |

**Priority key:**
- P1 = Must have for milestone close
- P2 = Should have, ship if T5b's diarization decision lands cleanly
- P3 = Nice-to-have, document only if v1 capacity remains

---

## Competitor Feature Analysis

| Feature | BibiGPT / NoteGPT | NotebookLM | Otter / Notta | This project |
|---|---|---|---|---|
| Output structure | Fixed bullet+chapter template | Fixed Explainer/Brief/Cinematic styles | Fixed meeting-note template | **Adaptive per-video, Claude-decided** (T1) |
| Frame embedding | Few stills, opaque selection | None for input video | None | **Per-segment fps Claude plans, batch-extracts, Claude reads multimodally** (T2 + shipped) |
| Code transcription quality | LLM-fills from transcript context (often hallucinates) | n/a | n/a | **Read JPEG line-by-line, no OCR** (shipped) |
| Platform coverage | 30+ via own backend | YouTube + uploads | None (audio focus) | yt-dlp's coverage + 抖音 + local file (T3 + T4) |
| Resume / pipeline state | None visible (cloud, opaque) | None visible | None visible | **Filesystem-as-state + status command** (T6) |
| Speaker awareness | Limited | n/a | Strong | Strong if T5b ships; gap if not |
| Cost | Freemium / paid | Free with Google account (rate-limited) | Freemium / paid | **¥0 hard constraint** |
| Decision authority | LLM template | LLM template + steering prompt | LLM template | **Claude Code throughout** (foundational) |
| Backward compat with archived past output | n/a (cloud, no local archive) | n/a | n/a | **Hard requirement** |

The competitive position: "the only video-doc tool where the model is the decision-maker, not the prompt template's decoration." Every feature in this milestone either widens the input surface (T3/T4), reduces operator friction without removing decisions (T2/T6), or differentiates output for content types where the generic template *can't* fit (T1/T5a/T5b).

---

## Sources

- BibiGPT product surface and platform claims — [BibiGPT.co](https://bibigpt.co/en); [BibiGPT vs NoteGPT alternatives 2026 (BibiGPT blog)](https://bibigpt.co/en/blog/posts/notegpt-alternatives-bibigpt-2026); [BibiGPT v1 GitHub](https://github.com/JimmyLv/BibiGPT-v1)
- BiliNote (closest open-source analog) — [JefferyHcool/BiliNote](https://github.com/JefferyHcool/BiliNote)
- NotebookLM Video Overviews features — [Google Blog: Cinematic Video Overviews](https://blog.google/innovation-and-ai/products/notebooklm/generate-your-own-cinematic-video-overviews-in-notebooklm/); [NotebookLM Help — Generate Video Overviews](https://support.google.com/notebooklm/answer/16454555?hl=en)
- Otter / Descript / Notta comparison — [Notta blog: Otter vs Descript](https://www.notta.ai/en/blog/otter-ai-vs-descript); [Notta blog: Otter alternatives 2026](https://www.notta.ai/en/blog/otter-ai-alternative)
- Podcast-summarizer feature set (diarization, chapters, quote extraction) — [Podpak: AI Podcast Summarizers Compared 2026](https://www.podpak.co/blog/ai-podcast-summarizers-compared); [MindMapAI: Best AI Podcast Summarizers 2026](https://mindmapai.app/blog/109/best-ai-podcast-summarizers); [SipSip: How AI processes podcast audio](https://sipsip.ai/blog/learn/how-ai-processes-podcast-audio)
- PySceneDetect content-aware detection (informs scene-probe option) — [PySceneDetect CLI docs](https://www.scenedetect.com/cli/); [Breakthrough/PySceneDetect on GitHub](https://github.com/Breakthrough/PySceneDetect); [arXiv 2506.00667 — Scene Detection Policies and Keyframe Extraction Strategies](https://arxiv.org/html/2506.00667v1)
- Cursor-highlight at recording-time (supports anti-feature: post-hoc cursor detection is not a thing in this ecosystem) — [Wondershare DemoCreator cursor effects](https://democreator.wondershare.com/video-editor/add-mouse-effects.html); [FocuSee mouse pointer highlight](https://focusee.imobie.com/use-cases/mouse-pointer-highlight.htm)
- Project context — `D:\gxy_code\videoSummary\.planning\PROJECT.md`; `D:\gxy_code\videoSummary\CLAUDE.md`; `D:\gxy_code\videoSummary\.planning\codebase\ARCHITECTURE.md`

**Confidence per claim:**
- HIGH — competitor feature presence/absence (multi-source, official product pages)
- HIGH — PySceneDetect capabilities (official docs)
- HIGH — videoSummary's existing capabilities (read directly from PROJECT.md, CLAUDE.md, ARCHITECTURE.md)
- MEDIUM — diarization-stack feasibility for ¥0 (pyannote.audio's HF-gated weights work for personal use but I haven't verified license fit for "single-user, local, no auth"; flag for STACK.md / PITFALLS.md)
- MEDIUM — claim that no mainstream tool has Claude-style multi-phase iterating decisions (based on surveying ~10 tool pages; possible niche tool exists I didn't find)
- LOW — exact complexity estimates (engineering judgment from reading existing code; treat as planning estimate, not commitment)

---
*Feature research for: Claude-driven video-to-tutorial pipeline (¥0 local, brownfield expansion)*
*Researched: 2026-04-30*
