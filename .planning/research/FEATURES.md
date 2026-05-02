# Feature Research — v1.1 Summary-Quality Milestone

**Domain:** Video → structured Markdown tutorials (subsequent milestone, quality-automation focus)
**Researched:** 2026-05-03
**Confidence:** MEDIUM-HIGH for industry patterns (LLM-as-judge / Whisper / Wikipedia / Perplexity citation are all well-published); MEDIUM for specific tuning numbers (per-sentence confidence threshold, max iterations); LOW for "what's the optimal fps for tutorial-vs-podcast" (no published research, all heuristic)

## Scope Note

v1.0 already shipped: 4-mode adaptive Markdown, 8 hand-authored skeletons, format-spec lock, schedule.json, params.json sidecars, FileLock parallelism. **The v1.0 FEATURES.md (now overwritten) was about "what video-→-notes tools do."** This v1.1 FEATURES.md is about **the next layer**: making the already-good summaries auto-correct, self-trace, peer-reviewed, and zero-baseline self-contained.

The reference frame shifts: instead of comparing to BibiGPT / NotebookLM / NoteGPT (none of which do correctness automation or self-trace at all), the relevant industry priors are:

- **Whisper ASR correction**: `initial_prompt` (decoding-time bias) vs. LLM post-edit
- **LLM-as-judge / Agent-as-a-Judge**: ICML 2025 evaluation patterns
- **Self-Refine / Reflexion**: iterative critique-then-rewrite, with diminishing returns past 2 rounds
- **Wikipedia Lead Section / BLUF**: self-contained-from-first-paragraph writing rules
- **Perplexity citation format**: inline numbered references, no end-bibliography
- **Hallucination detection**: per-sentence decomposition + self-consistency scoring

---

## Feature Landscape

### Table Stakes (Quality-tool baseline — the v1.1 goalposts)

These are non-optional if "summary 质量铁律" + D-01/02/03 are taken seriously. Each maps directly to a 必做 candidate.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **CORR-01a: ASR suspect-word detection (L1)** | faster-whisper already exposes `avg_logprob`, `no_speech_prob`, `compression_ratio`; not using them when their sole job is "tell you when transcription is shaky" is leaving money on the table. Industry baseline: `logprob_threshold = -1.0`, `no_speech_threshold = 0.6` ([source](https://whisper-api.com/docs/transcription-options/)). | LOW | Read existing per-segment `avg_logprob` from `segs.json`; flag segments < -0.7 + cross-check rare 4+ char tokens against meta.json title tokens. **Pure-data filter, no new model.** |
| **CORR-01b: ASR context-aware correction (L2)** | Title + UP name + description used as priors is industry-standard. Whisper's own `initial_prompt` does this at decode-time and yields 17% relative WER reduction in domain-specific runs ([source](https://arxiv.org/html/2602.18966)). v1.0 doesn't pass `initial_prompt`. **Two cheap interventions stack.** | LOW-MEDIUM | (a) Pass `meta.title + uploader + description[:300]` as `initial_prompt` to faster-whisper (decode-time fix); (b) Claude reads `transcribe_warnings.json` + meta during plan.md and writes correction table (post-edit fix). Both are independently useful. |
| **CORR-01c: Multi-modal frame fallback (L3)** | When same suspect word recurs across multiple paragraphs, the truth is often visible on-screen (title slide, IDE tab, VS Code title bar). Claude's existing multimodal frame-Read is the cheapest verification possible — no API call, no OCR. Restricting to **frames at suspect-word timestamp ±5s** keeps it bounded. | LOW | Already capable; just needs the prompt instruction in plan.md phase: "when L2 confidence < 80%, Read frame at `floor(timestamp / fps_segment_start)` ±5s, look for the suspect string." Anti-feature: scrubbing all frames. |
| **CORR-02a: Inline source-trace tokens** | Industry pattern is well-defined. Perplexity uses `[N]` inline + numbered source list ([source](https://www.unusual.ai/blog/perplexity-platform-guide-design-for-citation-forward-answers)). Pandoc/Wikipedia use `[^N]` footnotes or `[@key]` ([source](https://www.timlrx.com/blog/streamlining-citations-in-markdown/)). **Direct path tokens** (`[seg_0030_000015.jpg @ 00:30]`) are the right pick here because (1) you already have unique identifiers, (2) no separate bibliography needed, (3) single-click-to-jump in any markdown viewer that resolves relative paths. | LOW-MEDIUM | Token format already proposed in CORR-02 candidate: `[seg_NNNN_NNNNNN.jpg @ HH:MM:SS]` and `[para_ID @ HH:MM:SS]`. Lock the byte-format identical to existing `frames/seg_NNNN_NNNNNN.jpg` filenames so trace tokens can be grepped. |
| **CORR-02b: Self-check pass with confidence scoring** | Self-Refine (Madaan 2023) and recent hallucination-detection literature both decompose long-form text per-sentence/claim and score each ([source](https://arxiv.org/html/2511.12236), [source](https://mbrenndoerfer.com/writing/hallucination-detection)). Threshold 80% in CORR-02 candidate aligns with common practice (typical hallucination-detection thresholds 70-85%; user pre-locked 80%). | MEDIUM | Two-pass architecture: write summary → re-read → emit per-sentence confidence as `[?]` marks. Footer summary count: "X / Y claims marked uncertain." |
| **CORR-03: Independent reviewer agent (Agent-as-a-Judge)** | Agent-as-a-Judge (ICML 2025, [source](https://arxiv.org/html/2410.10934v2)) shows independent agent gets 90% agreement with human evaluators vs 70% for single-agent self-judge. **Independence > self-critique.** Critic-fix loop is standard ([source](https://aibuddy.software/how-llms-judge-4-essential-patterns-for-smarter-agent-workflows/)). | MEDIUM-HIGH | Spawn separate `gsd-summary-verifier`-class agent with paragraphs.json + plan.md + summary.md + key frames; emit `<slug>-REVIEW.md` with critical/warning/info three tiers. Critical → trigger 1 rewrite. **Cap at 1 rewrite** — Self-Refine research confirms diminishing returns past 2 rounds ([source](https://learnprompting.org/docs/advanced/self_criticism/self_refine), [source](https://arxiv.org/html/2604.10508)). |
| **TEACH-A1: First-occurrence inline glossary expansion** | Wikipedia Lead Section explicitly mandates "the lead should stand on its own as a concise overview" and requires plain-English first sentence ([source](https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Lead_section)). Your D-01 lock ("不能假定我的阅读顺序") = same principle, applied per-summary. | LOW | Inline pattern: `术语 (English/中文释义)` on first occurrence within each summary. Append to per-summary glossary at end. |
| **TEACH-A2: Top-of-doc "你需要知道什么 / 你不需要知道什么"** | Industry-standard Prerequisites pattern in technical tutorial documentation ([source](https://www.42coffeecups.com/blog/technical-documentation-best-practices), [source](https://gitbook.com/docs/guides/docs-best-practices/documentation-structure-tips)). The "你不需要" inverse is rarer but a smart usability move — it cuts the "do I need to read X first?" anxiety upfront. | LOW | Front-matter section, 3-5 lines each. Anti-feature: long preflight that becomes its own tutorial. |
| **TEACH-A3: `output/_glossary.md` cross-summary accumulation** | Obsidian glossary plugins (`obsidian-glossary`, Dataview-based) confirm this is a valid solo-vault pattern ([source](https://github.com/nevir/obsidian-glossary), [source](https://forum.obsidian.md/t/creating-a-glossary/43593)). **Critical**: it's an *append-only sink*, not a runtime dependency. Each summary stays self-contained (D-01) — glossary is bonus context for someone who reads many. | LOW | File-append on summary completion. No reads, no validation, no ordering. Anti-feature: making glossary lookup mandatory for reading any single summary. |

### Differentiators (You'd be early adopter — high-value, defensible)

These are where v1.1 shipping early puts the project ahead of the BibiGPT / NoteGPT / NotebookLM crowd, none of whom do quality-automation or zero-baseline.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **TEACH-B: Top-of-doc 5-min speed-read block** | BLUF (bottom-line up front) is documented best practice but rarely executed in AI summary tools — they put the bullets at the bottom or scatter them. Length: 5-10% of doc body is industry standard for executive summaries ([source](https://lettercounter.org/blog/executive-summary-length-guide/)). For 1000-line summaries that's 50-100 lines, but **practical sweet spot is 10-15 lines** because past that you've recreated the doc. Structure: 3 lines core conclusion / 5 lines workflow speedrun / 3-5 must-watch timestamps. | LOW-MEDIUM | Auto-generated from existing summary, written *after* main body. Lives between header front-matter and "你需要知道什么". Anti-feature: making it itself a summary that needs its own summary. |
| **TOOL-A: `mode_signals.json` heuristic classifier** | The 4-mode classification in v1.0 is Claude-judgment-only. Heuristic priors are well-known in NLP — code-fence rate, question-mark density, speaker-turn detection, comparative-phrase frequency are all standard text-feature engineering ([source](https://www.nltk.org/book/ch06.html)). **None published as "tutorial-vs-podcast classifier" specifically** — this is hand-engineered with sensible defaults, not citing standardized research. | MEDIUM | Read paragraphs.json, compute 5-7 signals, output JSON: `{"signals": {...}, "mode_recommendation": "replicate-guide", "mode_confidences": {...}}`. **K5 hard line: tool emits suggestion only; Claude in plan.md still decides.** |
| **TOOL-B: `schedule_suggestion.json` from scenes+silence+paragraphs** | This combines 3 existing data sources (Phase 4 already has `detect_scenes` + `detect_silence`; Phase 1 has paragraphs.json). Adaptive frame sampling is an active 2025 research area (CVPR 2025 AKS, NAACL 2024 Sealing — [source](https://arxiv.org/abs/2502.21271), [source](https://arxiv.org/pdf/2507.15491)) but those are ML-trained samplers; **a simple rule-based combiner is not yet standard**. **Honest LOW confidence**: there's no published "tutorial fps = 0.3, podcast fps = 0.05" research; CONTEXT D-22-style heuristics are project-specific lore. | MEDIUM | Combiner rules: silence > 5s → fps 0.05 / scene-change density > 1/min → fps 0.4 / static lecture region → fps 0.1 / compose with FPS-04 silence-coverage guarantee. Output `schedule_suggestion.json`; **Claude still writes the final schedule.json**. |
| **TEACH-A4: "Self-contained per-mode" enforcement during reviewer pass** | Most v1.0 summaries pass D-01 by Claude-discipline; v1.1 reviewer can mechanically check ("does first occurrence of every all-caps acronym have an inline explanation?"). Cross-product with CORR-03 — reviewer agent already loaded with full context. | LOW (riding CORR-03) | Adds checklist item to reviewer's rubric. Doesn't need its own phase. |

### Anti-Features (Surface-appealing, known to backfire)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Auto-rewrite ASR text in segs.json** | "Just fix the wrong words inline" sounds great | Loses provenance — you can't tell which segments were corrected later, and a wrong correction permanently destroys ground truth. Breaks 17-archive byte-equal D-29 invariant since old runs would re-emit different segs.json on re-transcribe. | Always emit corrections as `transcribe_warnings.json` *additive* file. plan.md notes which corrections apply. segs.json stays raw ASR output. |
| **Over-correction of legit dialect / non-dictionary speech** | "Fix all unusual words" sounds thorough | Penalizes correctly-transcribed regional terms, internet slang, character names, technical neologisms. False-positive cost is high — destroys voice. Whisper-LM paper notes WER occasionally *increases* after LLM post-correction at low initial-WER ([source](https://arxiv.org/html/2503.23542v1)). | L1 confidence-flag only; L2 corrects only if title/description corroborates; L3 corrects only if frame-OCR confirms. **Three converging signals before write.** |
| **Auto-correct numbers, dates, version strings** | "Numbers are facts, fix them" | Numbers in tech tutorials often *are* the truth (URL paths, version `0.6.7.1`, port `8080`). Wrong correction is silent and catastrophic ("install v0.6 instead of v0.7"). | Skip rule: never modify any token containing digits. |
| **Forced citation token after every sentence** | "More citations = more rigorous" | Pollutes prose into unreadable line-noise. Perplexity convention: 5-10 citations per answer, not per-sentence ([source](https://www.unusual.ai/blog/perplexity-platform-guide-design-for-citation-forward-answers)). Wikipedia explicit guidance: don't over-cite obvious things. | Cite per-claim, not per-sentence. Specific numbers, code blocks, direct quotes, novel claims get tokens. Connective prose doesn't. |
| **Confidence-score everything paraphrase** | "Score every sentence so reviewer can grade" | Confidence theater — paraphrased synthesis can't really be confidence-scored, you're measuring rewording fidelity not factual accuracy. Floods doc with `[?]` on harmless transitions. | Score only verifiable claims (specific values, names, version numbers, code, direct quotes). Skip transitions, transitions, framing sentences. |
| **N-pass reviewer-debate (3+ rounds)** | "More reviews = more correct" | Self-Refine research is unambiguous: 2 rounds capture bulk of benefit, more = diminishing returns at linear cost ([source](https://arxiv.org/html/2604.10508)). Multi-agent debate gains exist but at quadratic cost ([source](https://arxiv.org/html/2508.02994v1)). | Cap at 1 reviewer pass + max 1 rewrite (already in CORR-03 must-have). Document the budget; don't loop. |
| **Reviewer-bias: same agent reviews itself** | "Save tokens by re-prompting same instance" | Agent-as-a-Judge data: self-judge agreement with humans = 70%, independent-agent = 90% ([source](https://arxiv.org/html/2410.10934v2)). Same-agent review misses its own systematic errors. | Spawn fresh agent for CORR-03 with **only** paragraphs.json + plan.md + summary.md + frames — no chat history. Independence is the whole point. |
| **Auto-grow per-summary glossary into runtime dependency** | "Reuse glossary across summaries" | Breaks D-01 self-containment. New reader must hop to glossary to read a summary. Defeats the entire purpose of zero-baseline. | `output/_glossary.md` is **append-only sink** for users who read many summaries. Each summary remains independently readable. |
| **Glossary entry for every term** | "Comprehensive coverage" | Glossary explosion — entries for "function", "variable", "video", etc. become noise. Wikipedia rule: lead introduces *the topic*, not every word. | Glossary entries only for: (a) jargon used 2+ times, (b) acronyms, (c) project/tool names. Skip generic terms. |
| **Over-explaining when context is clear** | "Be safe, explain everything" | Treats reader as incapable. Wikipedia explicit: "state facts that may be obvious to you, but are not necessarily obvious to the reader" — *not* "state every fact regardless." | Inline-explain only acronyms, project names, jargon on first occurrence. Trust reader on syntax/structure cues from code blocks. |
| **Video queue auto-runs unattended** | "Queue should just process while I sleep" | Already locked OoS in PROJECT.md ("队列全自动无人值守批跑"). Single-user tool — supervised batches are fine. Auto-running CORR-03 on 17 videos creates massive token cost with no human in the loop to catch upstream issues. | MISC-02 just *tracks* queue (add/list/next/done). User triggers each summary manually. |
| **mode_signals overrides Claude's judgment** | "Just trust the heuristic" | Violates K5 — Claude is decision-maker. Heuristic gets "step 1 / 第一步" wrong on extension-applications videos that happen to be sequential. Fixed-script classifier was the v0 era; v1 explicitly chose Claude-decides. | mode_signals.json is **suggestion only**. Output goes into Claude's plan.md context. Claude can ignore it. plan.md must show signal → decision rationale. |

---

## Feature Dependencies

```
[CORR-01a L1 detection]
    └──feeds──> [CORR-01b L2 context-correction]
                     └──optionally feeds──> [CORR-01c L3 multi-modal verify]
                              └──output──> transcribe_warnings.json + plan.md correction table

[CORR-02a inline trace tokens]
    └──required by──> [CORR-02b self-check confidence scoring]
                         └──MUST land before──> [CORR-03 reviewer agent]
                                                    └──can cite──> CORR-02a tokens to flag specific claims
                                                    └──can trigger──> 1 rewrite pass

[TEACH-A1 inline glossary]
    └──feeds──> [TEACH-A3 _glossary.md append]
[TEACH-A2 prerequisites header]
    └──independent──> (no deps, pure prompt change)
[TEACH-B speed-read]
    └──depends on──> all of TEACH-A landing first (otherwise speed-read references undefined terms)

[TOOL-A mode_signals.json]
    └──enhances──> Phase 2 plan.md mode classification (still Claude-decides)
[TOOL-B schedule_suggestion.json]
    └──depends on──> existing v1.0 detect_scenes + detect_silence + paragraphs.json
    └──enhances──> Phase 3 schedule.json writing (still Claude-decides)

[MISC-01 AV1 warning] ──pure cosmetic, zero deps
[MISC-02 queue CLI]   ──pure tooling, zero deps to summary pipeline
```

### Dependency Notes

- **CORR-02a (inline trace tokens) MUST land before CORR-03 (reviewer agent)**: reviewer's job is to flag low-confidence claims; without trace tokens it can't say "claim X cites frame Y at 00:30, frame doesn't show this." Without provenance the reviewer becomes another opinion not a verifier. **This is the load-bearing dependency** for the entire 3-layer correctness story.
- **CORR-01b (L2 context correction) requires CORR-01a (L1 detection) output**: L2 only acts on flagged segments; without L1's `transcribe_warnings.json` schema there's no input. They can be in same phase (mechanical sequence) but L1 is the gate.
- **TEACH-B (speed-read) depends on TEACH-A all landing first**: speed-read necessarily mentions terms that the body explains. If body doesn't have inline glossary, speed-read either repeats the explanation (noise) or assumes external knowledge (violates D-01).
- **TOOL-A and TOOL-B are independent of CORR-* and TEACH-***: pure decision-support tools. Can land in any order. **K5 boundary is the constraint, not deps.**
- **MISC-01 / MISC-02 are zero-dep wrap-up**: 顺手做 phase, last.

### Mode-coupling note (TEACH-A interacts with v1.0 4-mode skeletons)

v1.0 locked the 4 modes with byte-equal labels and 8 hand-authored skeletons. TEACH-A's "你需要知道什么" + inline glossary changes the front-matter of every output. **Format-spec lock (4 invariants) is not violated** — the 4 invariants are about timestamp / code-fence / image-path / 第二人称 — but the visual identity of summary headers changes for new outputs. **D-29 backward-compat is preserved** because: (1) old archives don't get re-written; (2) re-runs of old slugs would technically emit new headers, but plan.md absence falls through to v1.0 path per existing handling.

---

## MVP Definition (v1.1 Scope)

### Launch With (v1.1 必做 — 4 Active requirements collapse to these features)

Minimum viable for milestone: all four 必做 candidates, in dependency order.

- [ ] **CORR-01 (3 layers ASR correction)** — L1 detect into transcribe_warnings.json + L2 context correction in plan.md + L3 multi-modal frame verify. **Why essential:** D-02 layer 0 (without correct text, every other layer is correcting wrong source).
- [ ] **CORR-02 (self-check + inline trace)** — `[seg_*.jpg @ HH:MM:SS]` token + `[?]` confidence marks + footer count. **Why essential:** load-bearing prerequisite for CORR-03; standalone valuable as transparency.
- [ ] **CORR-03 (reviewer agent)** — independent agent emits `<slug>-REVIEW.md`, max 1 rewrite. **Why essential:** D-02 third layer; the "automation" half of D-03.
- [ ] **TEACH-A (zero-baseline self-contained)** — inline glossary + prerequisites header + cross-doc `_glossary.md`. **Why essential:** D-01 entire scope; user's pre-locked feedback.

### Add After Validation (v1.1 想做 — same milestone, second phase)

These should ship in v1.1 but not block 必做:

- [ ] **TEACH-B (top-of-doc speed-read)** — trigger when first 30+ min video summary lands and proves to be 1000+ lines unreadable.
- [ ] **TOOL-A (mode_signals.json)** — trigger when first wrong-mode misclassification of v1.1 era happens (or proactively if 必做 phases finish ahead).
- [ ] **TOOL-B (schedule_suggestion.json)** — trigger when first user complaint about "I had to think about fps for 10 min." Lower priority — current friction tolerable per PROJECT.md痛点信号.

### Nice-to-have / Wrap-up (v1.1 顺手做)

- [ ] **MISC-01 (AV1 warning to INFO)** — 5-line config change, batch with other log-noise cleanups.
- [ ] **MISC-02 (queue CLI)** — `add/list/next/done` + `~/.videoSummary/queue.json` state file. Local todo.txt-CLI pattern ([source](https://github.com/todotxt/todo.txt-cli)). Trigger to upgrade to 想做 if queue ≥ 15 (per CANDIDATES note).

### Future Consideration (v2+)

- [ ] **Reviewer N-pass debate** — only if 1-pass reviewer + 1 rewrite proves insufficient on real videos. Diminishing returns are documented; don't preemptively add.
- [ ] **`--initial_prompt` integrated into transcribe CLI** — currently CORR-01b uses post-edit only; if WER on tech terms remains high after L1+L2+L3, add decode-time fix as v1.2.
- [ ] **L4 user dictionary fallback** — explicitly listed in CANDIDATES "信号" section; only add if L1+L2+L3 measured fix-rate < 80%.
- [ ] **Per-mode reviewer rubric** — currently CORR-03 uses single rubric; per-mode (replicate-guide checks code-fences, interview-distillation checks speaker attributions) deferred until single rubric proves too coarse.
- [ ] **Multi-archive glossary search UI** — append-only `_glossary.md` works for solo author. If queue grows to 100+ summaries, search/dedup tool may be needed.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority | Reasoning |
|---------|------------|---------------------|----------|-----------|
| CORR-01a L1 detection | HIGH | LOW | P1 | Reuses existing per-segment logprobs; pure-data filter; gates entire L2/L3 chain |
| CORR-01b L2 context correction | HIGH | LOW-MEDIUM | P1 | meta.json + plan.md prompt change; biggest single accuracy lift |
| CORR-01c L3 multi-modal verify | MEDIUM | LOW | P1 | Cheap (Claude already reading frames); high precision when triggered |
| CORR-02a inline trace tokens | HIGH | LOW-MEDIUM | P1 | Format-lock + writing-prompt change; **gate for CORR-03** |
| CORR-02b self-check confidence | HIGH | MEDIUM | P1 | Two-pass write→re-read prompt; transparency for reader |
| CORR-03 reviewer agent | HIGH | MEDIUM-HIGH | P1 | Highest token cost (~80-100% of summary write); biggest correctness payoff |
| TEACH-A1 inline glossary | HIGH | LOW | P1 | Writing-prompt change; D-01 core |
| TEACH-A2 prerequisites header | HIGH | LOW | P1 | Writing-prompt change; D-01 core |
| TEACH-A3 _glossary.md sink | MEDIUM | LOW | P1 | File-append on completion; bonus context |
| TEACH-B speed-read top block | MEDIUM-HIGH | LOW-MEDIUM | P2 | Auto-generated post-summary; impact scales with summary length |
| TOOL-A mode_signals.json | MEDIUM | MEDIUM | P2 | Heuristics + JSON output; K5 boundary discipline |
| TOOL-B schedule_suggestion.json | MEDIUM | MEDIUM | P2 | Combiner over existing data; lower friction signal per user feedback |
| MISC-01 AV1 warning level | LOW | LOW | P3 | 5-min config edit |
| MISC-02 queue CLI | LOW-MEDIUM | LOW | P3 | New small CLI module; doesn't touch summary pipeline |

**Priority key:**
- P1: Must have for v1.1 (necessary to claim "summary 质量铁律 shipped")
- P2: Should have, ship within v1.1 if time/tokens permit; defer to v1.2 if not
- P3: Nice to have, last phase wrap-up

---

## Industry Pattern Cross-Reference (per-feature what's the prior)

| v1.1 Feature | Industry Analog | Source |
|---|---|---|
| CORR-01b L2 context correction | Whisper `initial_prompt` decode-bias; LLM post-edit | [Whisper Courtside](https://arxiv.org/html/2602.18966) (17% WER reduction with prompt injection); [Whisper-LM](https://arxiv.org/html/2503.23542v1) (LLM post-edit gains, with caveats at low WER) |
| CORR-02a inline trace tokens | Perplexity inline `[N]` references | [Perplexity Platform Guide](https://www.unusual.ai/blog/perplexity-platform-guide-design-for-citation-forward-answers) |
| CORR-02b per-claim confidence scoring | SelfElicit / sentence-level decomposition for hallucination detection | [Hallucination detection survey](https://mbrenndoerfer.com/writing/hallucination-detection); [Consistency-key paper](https://arxiv.org/html/2511.12236) |
| CORR-03 reviewer agent | Agent-as-a-Judge (90% human agreement vs 70% self-judge); Self-Refine | [Agent-as-a-Judge ICML 2025](https://arxiv.org/html/2410.10934v2); [Self-Refine](https://arxiv.org/abs/2303.17651); [How many tries](https://arxiv.org/html/2604.10508) (2 rounds = bulk of benefit) |
| CORR-03 max 1 rewrite cap | Self-Refine diminishing-returns finding | [Self-Refine](https://learnprompting.org/docs/advanced/self_criticism/self_refine) |
| TEACH-A1 inline glossary | Wikipedia Lead Section "stand on its own" + plain-English first sentence | [WP:LEAD](https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Lead_section) |
| TEACH-A2 prerequisites header | Tutorial-doc "Prerequisites" pattern | [42coffeecups Best Practices](https://www.42coffeecups.com/blog/technical-documentation-best-practices); [GitBook info-architecture](https://gitbook.com/docs/guides/docs-best-practices/documentation-structure-tips) |
| TEACH-A3 _glossary.md sink | Obsidian glossary plugins | [obsidian-glossary](https://github.com/nevir/obsidian-glossary); [Obsidian forum](https://forum.obsidian.md/t/creating-a-glossary/43593) |
| TEACH-B speed-read top block | BLUF (bottom-line-up-front); executive-summary length 5-10% of doc | [Lucid executive summary](https://lucid.co/blog/executive-summary); [Letter Counter length guide](https://lettercounter.org/blog/executive-summary-length-guide/) |
| TOOL-A mode signals | Generic NLP text-feature engineering (no specific "tutorial classifier" prior) | [NLTK ch6](https://www.nltk.org/book/ch06.html) |
| TOOL-B schedule suggestion | Adaptive frame sampling research (CVPR 2025 AKS — but ML-trained, not heuristic) | [AKS CVPR 2025](https://arxiv.org/abs/2502.21271); honest LOW confidence — no rule-based prior |
| MISC-02 queue CLI | todo.txt-CLI single-file state pattern | [todo.txt-cli](https://github.com/todotxt/todo.txt-cli) |

---

## Sources

**Whisper / ASR correction:**
- [Whisper Courtside Edition: LLM-Driven Context Generation](https://arxiv.org/html/2602.18966) — `initial_prompt` decode-bias 17% WER reduction in domain runs
- [Whisper-LM: Improving ASR Models with Language Models](https://arxiv.org/html/2503.23542v1) — LLM post-correction tradeoffs at low WER
- [faster-whisper #1358 sentence-level confidence](https://github.com/SYSTRAN/faster-whisper/issues/1358) — per-segment + per-word logprob access
- [Whisper API config docs](https://whisper-api.com/docs/transcription-options/) — `logprob_threshold`, `no_speech_threshold` defaults

**LLM-as-judge / Self-Refine:**
- [Agent-as-a-Judge: Evaluate Agents with Agents (ICML 2025)](https://arxiv.org/html/2410.10934v2) — 90% vs 70% agreement
- [When AIs Judge AIs (2508.02994)](https://arxiv.org/html/2508.02994v1) — survey of agent-judge architectures
- [Self-Refine: Iterative Refinement with Self-Feedback](https://arxiv.org/abs/2303.17651) — original framework
- [How Many Tries Does It Take?](https://arxiv.org/html/2604.10508) — 2 rounds capture bulk of benefit
- [LLM-as-a-Judge guide (Evidently AI)](https://www.evidentlyai.com/llm-guide/llm-as-a-judge) — practical eval patterns
- [4 essential agent-judge patterns](https://aibuddy.software/how-llms-judge-4-essential-patterns-for-smarter-agent-workflows/) — critic-revise-pattern overview

**Hallucination detection / per-sentence confidence:**
- [Hallucination Detection: NLI, Self-Consistency](https://mbrenndoerfer.com/writing/hallucination-detection)
- [Consistency Is the Key (2511.12236)](https://arxiv.org/html/2511.12236) — sentence-level decomposition

**Citation / inline-trace formats:**
- [Perplexity Platform Guide: citation-forward](https://www.unusual.ai/blog/perplexity-platform-guide-design-for-citation-forward-answers) — inline `[N]` no end-bibliography
- [Streamlining Citations in Markdown](https://www.timlrx.com/blog/streamlining-citations-in-markdown/) — Pandoc `[@key]` format
- [Markdown Citations Guide](https://blog.markdowntools.com/posts/markdown-citations-and-references-guide)

**Self-contained / first-paragraph / prerequisites patterns:**
- [Wikipedia:Manual of Style/Lead section](https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Lead_section) — "stand on its own" rule
- [Wikipedia:Manual of Style/Clarity](https://en.wikipedia.org/wiki/Wikipedia:Manual_of_Style/Clarity)
- [Tech docs best practices (42coffeecups)](https://www.42coffeecups.com/blog/technical-documentation-best-practices) — Prerequisites pattern
- [GitBook documentation structure](https://gitbook.com/docs/guides/docs-best-practices/documentation-structure-tips)

**Glossary patterns:**
- [obsidian-glossary plugin](https://github.com/nevir/obsidian-glossary)
- [Obsidian forum: Creating a Glossary](https://forum.obsidian.md/t/creating-a-glossary/43593)
- [Dataview plugin](https://blacksmithgu.github.io/obsidian-dataview/)

**Executive summary / BLUF:**
- [Engineering Tech Comm: Executive Summary](https://ohiostate.pressbooks.pub/feptechcomm/chapter/5-2-executive-summary-abstract/)
- [Letter Counter: Executive Summary Length](https://lettercounter.org/blog/executive-summary-length-guide/) — 5-10% of doc, 1-2 pages typical
- [Lucid: How to write an executive summary](https://lucid.co/blog/executive-summary)
- [Recommended technical documentation practices (BLUF)](https://wellshapedwords.com/essentials/practices/)

**Adaptive frame sampling (TOOL-B context):**
- [Adaptive Keyframe Sampling for Long Video Understanding (CVPR 2025)](https://arxiv.org/abs/2502.21271)
- [Self-Adaptive Sampling for VQA (NAACL 2024)](https://aclanthology.org/2024.findings-naacl.162.pdf)
- [PySceneDetect docs](https://www.scenedetect.com/cli/) — detection algorithms
- [silero-vad](https://github.com/snakers4/silero-vad)

**Queue CLI prior:**
- [todo.txt-cli](https://github.com/todotxt/todo.txt-cli) — single state-file pattern

---

*v1.1 features research for: video → structured Markdown tutorials (correctness automation + zero-baseline self-contained)*
*Researched: 2026-05-03*
