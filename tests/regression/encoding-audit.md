# Encoding Audit (PRE-04)

**Audited:** 2026-04-30
**Scope:** agent/ + src/ (.py files only, vendor/ excluded; backtick-form: `agent/` + `src/`)
**Result:** 100% compliant — every text-I/O site uses explicit `encoding="utf-8"`.

> Per **D-14**, scope is the project's first-party Python: `agent/` (8 .py files) + `src/` (9 .py files). Per **D-16**, scope explicitly includes the orphaned v2 modules (`frames_v2.py`, `pass1_classify.py`, `embed.py`, `frame_store.py`, `prepare.py`) even though they are not on the main ¥0 path — they remain importable and any future regression must catch encoding drift in them too.
>
> `vendor/` (currently `vendor/douyin_api/`) is excluded — vendor encoding hygiene is tracked in CONCERNS.md §3.1, out of D-14 scope, and the directory is `.gitignore`d so it is not part of the audit surface.

## Commands run

The three reproducible grep commands. Run from repo root:

```bash
# 1. Find every bare `open()` call (must be classified manually as binary / PIL / text).
rg -n '\bopen\s*\(' agent/ src/ --type py

# 2. Find any read_text / write_text without explicit encoding= (must be ZERO).
rg -n '(read_text|write_text)\s*\((?![^)]*encoding\s*=)' agent/ src/ --type py

# 3. Find json.load(open(...)) — forbidden idiom per CONVENTIONS.md (must be ZERO functional hits).
rg -n 'json\.load\s*\(' agent/ src/ --type py
```

Per **Pitfall 3** in `01-RESEARCH.md`, these are *targeted* patterns. A lazy `grep -r encoding utf-8 .` is rejected because it catches strings inside Markdown / docstrings and produces false positives.

## Findings

### Command 1 — Bare `open()` calls (4)

```
agent/douyin_downloader.py:196:        with open(video_path, "wb") as f:
agent/embed.py:79:                img = PILImage.open(p).convert("RGB")
agent/frames_v2.py:74:            h = imagehash.phash(Image.open(f.path))
src/frames.py:53:            h = imagehash.phash(Image.open(f.path))
```

| Site | Mode | Verdict |
|------|------|---------|
| `agent/douyin_downloader.py:196` | `with open(video_path, "wb") as f:` — binary write (mp4) | OK — binary mode must NOT carry `encoding=`. |
| `agent/embed.py:79` | `PILImage.open(p)` — Pillow image read | OK — `PIL.Image.open` is not a text-I/O builtin; PIL handles bytes/encoding internally. |
| `agent/frames_v2.py:74` | `imagehash.phash(Image.open(f.path))` — Pillow image read via imagehash | OK — same reasoning; PIL handles encoding. |
| `src/frames.py:53` | `imagehash.phash(Image.open(f.path))` — Pillow image read via imagehash | OK — same reasoning; PIL handles encoding. |

> **Audit note (completeness):** CONTEXT.md D-14 lists *three* bare-open sites; live grep finds *four*. The fourth, `src/frames.py:53`, is a v1-pipeline counterpart of `agent/frames_v2.py:74` and uses the same PIL-via-imagehash pattern. The `01-RESEARCH.md` §"Encoding Audit — Current State" caught it; this audit-pass evidence file lists all four for full traceability. Conclusion is unchanged: 100% compliant.

> **Audit note (Pitfall 6):** Do NOT conflate "is this encoding correct?" with "should this code exist?" — `agent/douyin_downloader.py:62` `_CONFIG.write_text(new_content, encoding="utf-8")` is *encoding-correct* (it carries `encoding="utf-8"`); the vendor-mutation concern around that write is a CONCERNS.md §2.2 issue, out of PRE-04 scope.

### Command 2 — Text I/O without encoding

**Result:** empty output.

**Text I/O sites without encoding: 0.**

All `read_text` / `write_text` callsites in `agent/` and `src/` carry explicit `encoding="utf-8"` (13 reads + 18 writes, per the breakdown in `01-RESEARCH.md` §"Encoding Audit — Current State").

### Command 3 — `json.load` usage

**Result:** empty output.

**`json.load(open(...))` calls: 0** (the codebase exclusively uses `json.loads(path.read_text(encoding="utf-8"))` per `CONVENTIONS.md` §"I/O & Path Conventions").

## Re-running

This audit is **read-only evidence**. Anyone can re-run the three commands above and replicate the result. No code is modified by this audit; the artifact is the grep transcript itself.

**When future phases touch `agent/` or `src/`:** before merging, re-run the three commands above. If the outputs still match (4 bare opens classified the same way; zero text-I/O without encoding; zero functional `json.load`), append a fresh `**Audited:** YYYY-MM-DD` line above and call out which phase re-validated. If a new site appears that violates the rules, fix the offending code (add `encoding="utf-8"`) — do **not** silently relax the audit.

Per **D-15**, the audit-pass evidence file IS the deliverable for PRE-04 since the codebase already meets the criterion. Per **D-16**, scope persists across the v2 module group.

## Cross-references

- **Runbook stub:** `tests/regression/regression-check.md` contains an `## Encoding Audit (PRE-04)` heading that links here. The link is one-way (runbook → audit); this file is self-contained.
- **CLAUDE.md:** `## Windows zh-CN 终端设置（推荐）` (added by 01-03 Task 2) cites `agent/tools.py:59` `ensure_ascii=True` as the preserved fallback. The audit confirms that fallback line is the only place in `agent/`/`src/` that uses `ensure_ascii=True` deliberately for terminal-print safety; all *file* I/O paths use `ensure_ascii=False, encoding="utf-8"` per CONVENTIONS.
- **PROJECT.md K3** (backward-compat): this audit imposes zero code changes, so the legacy 17-archive replay path is unaffected.
- **PITFALLS.md §U3** (Windows zh-CN encoding/proxy/locale): the audit confirms the *file-system* layer is encoding-clean; the *terminal* layer is addressed by PRE-05 (the new `## Windows zh-CN 终端设置（推荐）` section in CLAUDE.md).
