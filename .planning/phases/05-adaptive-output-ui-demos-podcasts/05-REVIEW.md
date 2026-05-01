---
phase: 05-adaptive-output-ui-demos-podcasts
reviewed: 2026-05-02T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - agent/asr_v2.py
  - src/asr.py
  - agent/tools.py
  - agent/diarize.py
  - agent/sources/youtube.py
  - requirements-optional.txt
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 5: Code Review Report

**Reviewed:** 2026-05-02
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Phase 5 introduces profile-aware ASR (`tutorial` / `podcast`) across `src/asr.py`
and `agent/asr_v2.py`, a whisper repetition guard with bypass-only artifact
output, an opt-in pyannote diarization module, a `cmd_diarize` CLI handler with
60min+/no-CUDA gate, and a YouTube VTT lang-priority lock. The architecture
respects the project's red lines:

- Repetition guard is **warn-only**; never auto-deletes (D-24 / "不注水不编造")
- `agent/diarize.py` is lazy-imported and raises a clean `RuntimeError` with
  install hint when pyannote is missing (matches `agent/silence.py` opt-in idiom)
- `HF_TOKEN` is never logged or stored in sidecar (T-05-03-08 mitigated)
- Backward-compat aliases (`_DEFAULTS`, `_VAD_DEFAULTS`) preserve Phase 2 import
  contracts when the dict shape changed under them
- `tutorial` profile preserves Phase 2 baseline values per Path C (D-29)

Three findings need attention before podcast mode rolls out to users:

1. **WR-01 / agent/sources/youtube.py:275-278** — VTT priority lock is
   implemented at yt-dlp's `subtitleslangs` list level, but the file picker
   uses `glob().__iter__` which returns files in filesystem order. On
   filesystems that return entries alphabetically (typical Windows NTFS),
   `video.en.vtt` is picked over `video.zh-Hans.vtt` — exactly the reverse of
   D-31 priority.
2. **WR-02 / agent/tools.py:358-381** — The 3-gram repetition algorithm only
   detects single-character repetition (`"啊啊啊啊"`, `"......"`). It does
   NOT detect the typical Whisper phrase-repeat hallucination
   (`"我们这里用我们这里用..."`) — yet the `_count_consecutive_trigrams`
   docstring explicitly cites that pattern as the target. Verified by direct
   execution: `_count_consecutive_trigrams("我们这里用我们这里用我们这里用我们这里用")`
   returns `{'我们这': 1, ...}` — max run = 1, never triggers the > 3 threshold.
3. **WR-03 / agent/tools.py:744-754** — `cmd_diarize` validates `out_path` for
   CJK characters but does NOT validate `audio_wav`. If user passes a CJK
   audio path, the ffprobe duration probe (subprocess) silently fails on
   Windows zh-CN, the gate is skipped, and pyannote may then receive a path
   that yields opaque errors deep in the model.

Five Info items document opportunities for future cleanup: dead code, log
verbosity, deprecated ffmpeg flags, proxy credential exposure via argv, and a
minor over-reporting case in step-2 of the repetition guard.

## Warnings

### WR-01: VTT priority lock broken at file-picker step

**File:** `agent/sources/youtube.py:275-278`
**Issue:** The `subtitleslangs` list `["zh-Hans", "zh-Hant", "zh", "en"]` tells
yt-dlp which manual subs to download (and yt-dlp downloads ALL that exist, not
just the highest-priority one). The downloaded files land at e.g.
`video.zh-Hans.vtt`, `video.en.vtt`, `video.zh.vtt`. Then this loop picks one:

```python
sub_file = None
for f in target_dir.glob("video.*.vtt"):
    sub_file = f
    break
```

`Path.glob` returns entries in filesystem order. On NTFS / typical sorted
filesystems, that is alphabetical — so `video.en.vtt` < `video.zh-Hans.vtt`
< `video.zh-Hant.vtt` < `video.zh.vtt`, meaning `en` wins over `zh-Hans`.
This directly contradicts D-31: "VTT lang priority zh-Hans>zh-Hant>zh>en".
The `subtitle_path` field in `meta.json` then points at the wrong file, which
breaks D-32's downstream rule (interview-distillation mode trusts VTT directly).

**Fix:** Pick the file in explicit priority order:

```python
sub_file = None
for lang in ("zh-Hans", "zh-Hant", "zh", "en"):
    candidate = target_dir / f"video.{lang}.vtt"
    if candidate.exists():
        sub_file = candidate
        break
# Fallback: any vtt (auto-captions land with .lang-orig or just .lang)
if sub_file is None:
    for f in sorted(target_dir.glob("video.*.vtt")):
        sub_file = f
        break
```

Add a regression test that drops three dummy `.vtt` files in a tmpdir and
asserts `zh-Hans` wins over `en`.

### WR-02: Trigram repetition guard does not detect typical phrase-level whisper hallucinations

**File:** `agent/tools.py:358-381` (`_count_consecutive_trigrams`)
**Issue:** The function counts only **adjacent** sliding-window trigram
repetitions (`text[i:i+3] == text[i+1:i+4]`). This catches `"aaaaaa"`
(`{'aaa': 4}`) and `"......"` (`{'...': 4}`) but completely misses the canonical
phrase-repeat hallucination form. Direct verification:

```python
>>> _count_consecutive_trigrams("我们这里用我们这里用我们这里用我们这里用")
{'我们这': 1, '们这里': 1, '这里用': 1, '里用我': 1, '用我们': 1}
>>> _count_consecutive_trigrams("haha haha haha haha")
{'hah': 1, 'aha': 1, 'ha ': 1, 'a h': 1, ' ha': 1}
```

Max run = 1 in both cases — never crosses the > 3 threshold. Yet the
function's own docstring advertises this exact use case
(line 364: `"用于检测 whisper 重复幻觉典型形态 (e.g. '我们这里用我们这里用...')"`).

The guard does fire on character-pad hallucinations (the form Whisper produces
on extended silences), so it is not useless — but the user-visible promise
("warn on whisper repetition hallucinations") is only partially delivered.

**Fix:** Two options, in order of preference:

1. **Spec is correct, docstring is wrong** — if D-22 truly only targets
   character-level repetition, fix the docstring example to use `"啊啊啊啊啊啊"`
   and document the limitation explicitly. Cheapest fix; preserves D-29
   regression byte-equality.
2. **Spec under-specifies; broaden algorithm** — switch to "trigram appearance
   count" (not consecutive-run count) and threshold on density per joined-text
   length:

```python
def _count_repeated_trigrams(text: str) -> dict[str, int]:
    """Total occurrences of each 3-gram (not consecutive run)."""
    if len(text) < 3:
        return {}
    from collections import Counter
    return Counter(text[i:i+3] for i in range(len(text) - 2))
```

   Then flag when `count >= 4 AND count / (len(text)/3) > 0.6` (i.e. > 60% of
   the segment is one trigram). This catches phrase-repeat without false-firing
   on natural language.

Either fix is acceptable. Pick (1) if you want zero behavior change and just
correct documentation; pick (2) if you want the guard to live up to its
advertised purpose. Whichever you choose, add a unit test that asserts the
chosen behavior on `"我们这里用" * 5`.

### WR-03: cmd_diarize does not validate CJK in audio_wav path

**File:** `agent/tools.py:744-770`
**Issue:** `_validate_out_path(out_path)` is called on `args.out` (line 745)
but not on `args.audio_wav`. If the user passes a CJK audio path
(e.g. `output/中文测试/audio.wav`), the ffprobe subprocess on Windows zh-CN
will hit the same GBK code-page hazard that motivated D-19. Concretely:

- ffprobe at line 765 receives a CJK path argument
- subprocess on Windows passes argv through GBK code-page
- ffprobe fails to find the file (path mojibake)
- `subprocess.CalledProcessError` is caught at line 777, logged as warning
- duration_s stays at 0.0, so the 60min+ gate is silently bypassed
- pyannote then gets the CJK path and fails opaquely deep in the model

The user sees "ffprobe duration probe failed; skipping duration gate" and then
a confusing pyannote stack trace, instead of the clean ValueError they would
get on `args.out`.

**Fix:** Validate audio_wav too:

```python
out_path = Path(args.out)
_validate_out_path(out_path)
audio_path = Path(args.audio_wav)
_validate_out_path(audio_path)  # Same hazard; same fix
out_dir = out_path.parent
out_dir.mkdir(parents=True, exist_ok=True)
```

Note: `_validate_out_path` is misnamed for this use case (it's validating an
*input* path here), but the function's actual contract — "raise ValueError on
CJK in any path before subprocess runs" — applies identically. Consider
renaming to `_validate_subprocess_path` in a future cleanup.

## Info

### IN-01: `_VAD_DEFAULTS` is dead code

**File:** `src/asr.py:67-69`
**Issue:** `_VAD_DEFAULTS` is declared as "backward-compat alias for
agent/tools.py:cmd_transcribe sidecar抓取" but a project-wide grep confirms
NO file imports `_VAD_DEFAULTS` from `src.asr`. `cmd_transcribe` reads from
`PROFILES[args.profile]` directly (line 218), not `_VAD_DEFAULTS`. The
backward-compat justification in the comment is incorrect.

**Fix:** Either:
- Delete `_VAD_DEFAULTS` and its 4-line comment block (cleanest), or
- Keep it but rewrite the comment to "Reserved for downstream callers; not
  used internally" so the dead-code aspect is explicit.

By contrast, `agent/asr_v2.py:_DEFAULTS` (line 47) IS dead code by the same
test (no importer). Same fix applies — delete or relabel.

### IN-02: HF_TOKEN logging shows `<set>` even for whitespace-only tokens

**File:** `agent/diarize.py:64-67`
**Issue:** The caller (`cmd_diarize` line 750) strips the token before passing
it in: `hf_token = os.environ.get("HF_TOKEN", "").strip()` and rejects empty.
But `agent/diarize.py:diarize_audio` could in principle be called directly
with a whitespace-only token. The log line `"<set>" if hf_token else "<empty>"`
treats `"   "` as truthy.

This is purely cosmetic (the actual auth call would fail with a clearer
HF error), and the public contract is "caller is responsible for passing a
real token", but if you want defense-in-depth:

**Fix:**
```python
"<set>" if hf_token.strip() else "<empty>",
```

### IN-03: Repetition guard step 2 over-reports on long mono-trigram runs

**File:** `agent/tools.py:434-455`
**Issue:** Sliding 3-segment windows can re-flag the same continuous repetition
when the run spans more than 3 segments. Example: 6 consecutive segments all
containing `"aaaaa"`. Window [0,1,2] flags it, marks segs {0,1,2} as flagged
for `"aaa"`. Window [1,2,3] is dedupd (intersection with flagged). Window
[3,4,5] is NOT dedupd (no intersection with flagged for `"aaa"` because we
never added 3,4,5 from window [0,1,2]) → second warning for the same run.

This produces redundant entries in `transcribe_warnings.json` but does not
cause auto-deletion or other red-line violations. Doctor-grade code quality
issue, not a correctness bug.

**Fix:** When dedupping, also mark all segments in the window as flagged for
that gram even if not warned (so a sliding window past the flagged region
still suppresses):

```python
if any((i, gram) in flagged for i in range(window_start, window_end)):
    # Also propagate the flag forward to suppress sliding-overlap re-warnings
    for i in range(window_start, window_end):
        flagged.add((i, gram))
    continue
```

### IN-04: Proxy credentials in argv are visible to other processes

**File:** `agent/sources/youtube.py:90-96`
**Issue:** If the user sets `HTTPS_PROXY=http://user:pass@proxy:7890`, the
credentials are passed in subprocess argv (`yt-dlp --proxy http://user:pass@proxy:7890`)
which is visible via `Get-Process` / `ps aux` on multi-user systems. The
`_redacted_proxy_log` helper redacts only the LOG line, not the actual argv.

This is a yt-dlp limitation (the `--proxy` flag is the standard way) and the
threat surface is "another local user with shell access" which most users
don't face. Marked Info, not Warning.

**Fix (optional):** Document the risk in `CLAUDE.md` proxy section, or — for
defense-in-depth — set the proxy via env var passed to subprocess (yt-dlp
honors `HTTPS_PROXY` from environment too):

```python
env = {**os.environ}  # already has HTTPS_PROXY
# Drop --proxy from argv; let yt-dlp pick up env
cmd = ["yt-dlp", "--no-warnings", "--no-progress"]
if simulate: cmd.append("--simulate")
cmd.append(url)
subprocess.run(cmd, env=env, ...)
```

This keeps credentials out of argv. Verify yt-dlp env-var precedence first
before changing.

### IN-05: ffmpeg `-vsync vfr` is deprecated

**File:** `agent/tools.py:502, 609` (NOT Phase 5 code, but in scope per file list)
**Issue:** ffmpeg 5.1+ deprecated `-vsync vfr` in favor of `-fps_mode vfr`. The
old flag still works but emits a deprecation warning. This is Phase 3 code
(SRC-12 D-23), not a Phase 5 regression — flagging only because the file is
in scope per `<files_to_read>`.

**Fix:** Defer to a future ffmpeg-flags audit. No action needed for Phase 5.

---

_Reviewed: 2026-05-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
