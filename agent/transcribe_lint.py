"""L1 ASR suspect-token detector (Phase 07 CORR-01a).

K5 boundary: this module DETECTS suspicious tokens; it NEVER modifies
segs.json (D-29 invariant) and NEVER promotes suggestions into the plan
artifact (Claude is decider — L2/L3 corrections live in Phase 08).

Detection strategies (per .planning/research/PITFALLS.md P-01 — explicit
allowlist required to avoid false-positive cascade):

  1. mixed_script: Latin token of length >= 2 embedded in CJK-context paragraph
  2. hapax: token appears exactly once across all paragraphs AND not allowlisted
  3. frequency_variance: same case-insensitive lemma in multiple spellings;
     suggested = highest-freq form
  4. title_token: meta title contains Latin token T; segs contain T' that
     normalizes to same lemma but differs in case; suggested = T
  5. homophone_cluster: pypinyin lazy_pinyin matches between flagged token
     and a higher-confidence neighbor — sparse CJK tokens (freq < 3) get
     pinyin-signature lookup; if a same-pinyin candidate token exists with
     freq > 5x the suspect's freq, suggest the high-freq candidate as the
     correction. This is the strategy that justifies the pypinyin dep.

CORR-01a per REQUIREMENTS.md: "ASR 转录后 L1 检测可疑词（pypinyin homophone
+ 中英混杂异常 + 罕见字组合 + 高频但拼写不一致）" — the 4 mandated strategies
map to homophone_cluster + mixed_script + hapax + frequency_variance. The
title_token strategy is a bonus from CONTEXT specifics (Step 2 meta cross-reference).
"""
from __future__ import annotations

import logging
import re
from collections import Counter

from pypinyin import lazy_pinyin  # CORR-01a strategy #5: homophone_cluster

log = logging.getLogger(__name__)

WARNINGS_FILENAME = "transcribe_warnings.json"
ALLOWED_EVIDENCE_SOURCES = (
    "title_token",
    "frequency_variance",
    "mixed_script",
    "hapax",
    "homophone_cluster",
)

_STOPWORDS_ZH = frozenset([
    "你", "我", "他", "她", "它", "我们", "你们", "他们",
    "的", "了", "在", "是", "有", "和", "就", "也", "都",
    "这", "那", "这个", "那个", "什么", "怎么", "为什么",
    "可以", "可能", "需要", "应该", "如果", "因为", "所以",
])
_NUMERIC_RE = re.compile(r"^\d+(\.\d+)?$")
_PUNCT_RE = re.compile(r"^[\W_]+$", re.UNICODE)
_SINGLE_CJK_RE = re.compile(r"^[一-鿿㐀-䶿]$")
_LATIN_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]+")
# CJK token regex for homophone_cluster — multi-char CJK words only (single
# char already filtered by _SINGLE_CJK_RE allowlist via _is_allowed)
_CJK_TOKEN_RE = re.compile(r"[一-鿿㐀-䶿]{2,}")
_HOMOPHONE_SPARSE_THRESHOLD = 3   # tokens with freq < this are "sparse" -> candidates for homophone lookup
_HOMOPHONE_FREQ_RATIO = 5         # candidate's freq must be > this * suspect's freq
_HOMOPHONE_CONFIDENCE = 0.65      # locked confidence for homophone_cluster matches


def _is_allowed(token: str) -> bool:
    if not token or len(token.strip()) == 0:
        return True
    if _NUMERIC_RE.match(token):
        return True
    if _PUNCT_RE.match(token):
        return True
    if _SINGLE_CJK_RE.match(token):
        return True
    if token in _STOPWORDS_ZH:
        return True
    return False


def _extract_latin_tokens(text: str) -> list[str]:
    return _LATIN_TOKEN_RE.findall(text or "")


def _extract_cjk_tokens(text: str) -> list[str]:
    """Extract candidate multi-char CJK tokens for homophone clustering.

    Without a Chinese word-segmenter (jieba would be a heavy new dep), we
    extract overlapping 2-char bigrams from each contiguous CJK run. 2-char
    words dominate Modern Mandarin vocabulary (~70%), so bigrams catch most
    real ASR substitution targets. Bigram-level clustering produces some
    nonsense candidates (e.g., '今天'/'jintian' bigram from '今天讲'), but
    the freq-ratio threshold (_HOMOPHONE_FREQ_RATIO=5x) keeps signal high.
    """
    if not text:
        return []
    bigrams: list[str] = []
    for run in _CJK_TOKEN_RE.findall(text):
        if len(run) < 2:
            continue
        for i in range(len(run) - 1):
            bigrams.append(run[i:i + 2])
    return bigrams


def _normalize_for_clustering(token: str) -> str:
    return re.sub(r"[\W_]+", "", token).lower()


def _pinyin_signature(token: str) -> str:
    """Compute pinyin signature for homophone clustering.

    Uses pypinyin.lazy_pinyin (Style.NORMAL, no tones) — sufficient for
    same-sound matching. Returns lowercase joined string e.g. "xunlian".
    Returns empty string if token has no pinyin (defensive — pypinyin
    falls back to original char for non-CJK).
    """
    try:
        parts = lazy_pinyin(token)
        return "".join(p.lower() for p in parts if p)
    except Exception as e:
        log.warning("lazy_pinyin failed for %r: %s", token, e)
        return ""


def detect_warnings(segs: list[dict], meta: dict | None = None) -> list[dict]:
    """Scan segs for suspect ASR tokens. Return list of warning dicts.

    Returns empty list if no suspects (proves no false-flag per PITFALLS P-01).

    Strategy order: title_token > frequency_variance > homophone_cluster (CJK only)
    > hapax (Latin) > mixed_script (Latin fallback). Each token gets at most one
    warning; first matching strategy wins.
    """
    warnings: list[dict] = []
    if not segs:
        return warnings

    # === Pass 1: collect Latin token frequencies + lemma -> forms map ===
    token_freq: Counter[str] = Counter()
    token_lemma_to_forms: dict[str, Counter[str]] = {}
    seg_tokens: list[list[str]] = []
    for seg in segs:
        tokens = _extract_latin_tokens(seg.get("text", ""))
        seg_tokens.append(tokens)
        for t in tokens:
            if _is_allowed(t):
                continue
            token_freq[t] += 1
            lemma = _normalize_for_clustering(t)
            if lemma:
                token_lemma_to_forms.setdefault(lemma, Counter())[t] += 1

    # === Pass 1b: collect CJK multi-char token frequencies + pinyin signatures
    # for homophone_cluster (B1 fix — proves pypinyin dep is not dead weight) ===
    cjk_token_freq: Counter[str] = Counter()
    seg_cjk_tokens: list[list[str]] = []
    for seg in segs:
        cjk_toks = _extract_cjk_tokens(seg.get("text", ""))
        seg_cjk_tokens.append(cjk_toks)
        for t in cjk_toks:
            cjk_token_freq[t] += 1

    # Build pinyin -> {token: freq} index for same-pinyin neighbor lookup
    pinyin_to_forms: dict[str, Counter[str]] = {}
    for tok, freq in cjk_token_freq.items():
        sig = _pinyin_signature(tok)
        if sig:
            pinyin_to_forms.setdefault(sig, Counter())[tok] = freq

    # === Pass 2: title token cross-reference ===
    title_tokens: set[str] = set()
    if meta and isinstance(meta, dict):
        title = meta.get("title", "") or ""
        title_tokens = set(_extract_latin_tokens(title))

    # === Pass 3: emit warnings — Latin tokens first ===
    seen_pairs: set[tuple[int, str]] = set()
    for seg_idx, seg in enumerate(segs):
        tokens = seg_tokens[seg_idx]
        text = seg.get("text", "") or ""
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        para_id = f"p{seg_idx:04d}"

        for t in tokens:
            if _is_allowed(t):
                continue
            if (seg_idx, t) in seen_pairs:
                continue
            seen_pairs.add((seg_idx, t))

            evidence_source: str | None = None
            evidence_detail: str | None = None
            suggested_text = ""
            confidence = 0.0
            lemma = _normalize_for_clustering(t)

            # Strategy 1: title_token
            for tt in title_tokens:
                if _normalize_for_clustering(tt) == lemma and tt != t:
                    evidence_source = "title_token"
                    suggested_text = tt
                    confidence = 0.9
                    break

            # Strategy 2: frequency_variance
            if evidence_source is None and lemma in token_lemma_to_forms:
                forms = token_lemma_to_forms[lemma]
                if len(forms) > 1:
                    canonical = forms.most_common(1)[0][0]
                    if canonical != t:
                        evidence_source = "frequency_variance"
                        suggested_text = canonical
                        confidence = min(0.85, 0.5 + 0.1 * (forms[canonical] - forms[t]))

            # Strategy 4 (Latin only — hapax)
            if evidence_source is None and token_freq[t] == 1:
                evidence_source = "hapax"
                suggested_text = ""
                confidence = 0.3

            # Strategy 1 fallback — mixed_script
            if evidence_source is None:
                if any('一' <= c <= '鿿' for c in text):
                    evidence_source = "mixed_script"
                    suggested_text = ""
                    confidence = 0.2
                else:
                    continue

            try:
                tok_pos = text.index(t)
                ctx_before = text[max(0, tok_pos - 50):tok_pos]
                ctx_after = text[tok_pos + len(t):tok_pos + len(t) + 50]
            except ValueError:
                ctx_before = ""
                ctx_after = ""

            warning = {
                "para_id": para_id,
                "seg_index": seg_idx,
                "start": start,
                "end": end,
                "suspect_text": t,
                "suggested_text": suggested_text,
                "evidence_source": evidence_source,
                "confidence": round(confidence, 2),
                "context_before": ctx_before,
                "context_after": ctx_after,
            }
            if evidence_detail:
                warning["evidence_detail"] = evidence_detail
            warnings.append(warning)

    # === Pass 4: emit homophone_cluster warnings for sparse CJK tokens ===
    # B1 fix — implements CORR-01a strategy #5 (pypinyin homophone). For each
    # CJK token appearing < _HOMOPHONE_SPARSE_THRESHOLD times, look up its
    # pinyin signature; if a same-pinyin candidate exists with freq >
    # _HOMOPHONE_FREQ_RATIO * suspect_freq, emit a warning suggesting the
    # high-freq candidate. This is the strategy that justifies pypinyin in
    # requirements.txt — without it, pypinyin would be dead weight.
    cjk_seen_pairs: set[tuple[int, str]] = set()
    for seg_idx, seg in enumerate(segs):
        cjk_toks = seg_cjk_tokens[seg_idx]
        text = seg.get("text", "") or ""
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        para_id = f"p{seg_idx:04d}"

        for tok in cjk_toks:
            if (seg_idx, tok) in cjk_seen_pairs:
                continue
            cjk_seen_pairs.add((seg_idx, tok))

            suspect_freq = cjk_token_freq[tok]
            if suspect_freq >= _HOMOPHONE_SPARSE_THRESHOLD:
                continue  # token is too common to be a typo candidate

            sig = _pinyin_signature(tok)
            if not sig or sig not in pinyin_to_forms:
                continue

            # Find best (highest-freq) same-pinyin candidate that is NOT this token
            forms = pinyin_to_forms[sig]
            candidates = [(t, f) for t, f in forms.items() if t != tok]
            if not candidates:
                continue
            candidates.sort(key=lambda kv: kv[1], reverse=True)
            best_tok, best_freq = candidates[0]

            if best_freq <= _HOMOPHONE_FREQ_RATIO * suspect_freq:
                continue  # candidate isn't dominant enough

            # Compute context window around the suspect token in this seg
            try:
                tok_pos = text.index(tok)
                ctx_before = text[max(0, tok_pos - 50):tok_pos]
                ctx_after = text[tok_pos + len(tok):tok_pos + len(tok) + 50]
            except ValueError:
                ctx_before = ""
                ctx_after = ""

            warnings.append({
                "para_id": para_id,
                "seg_index": seg_idx,
                "start": start,
                "end": end,
                "suspect_text": tok,
                "suggested_text": best_tok,
                "evidence_source": "homophone_cluster",
                "confidence": _HOMOPHONE_CONFIDENCE,
                "context_before": ctx_before,
                "context_after": ctx_after,
                "evidence_detail": f"pinyin={sig}, candidate freq={best_freq}",
            })

    return warnings
