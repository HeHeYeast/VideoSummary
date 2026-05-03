"""17-archive byte-equal replay test (Phase 07 PRE-V11-02 / P-08 D-29 gate).

Purpose: prove that v1.1 code changes have NOT altered how
`transcribe -> aggregate -> write summary` produces the canonical
artifacts on slugs WITHOUT `.v11_features.json` marker.

SCOPE — what this script verifies (automated):
  1. paragraphs.json BYTE-EQUAL — re-runs `aggregate_paragraphs()` from
     segs.json using the per-slug profile resolved from
     `paragraphs.json.params.json` sidecar (cli.profile -> func.profile ->
     PROFILES["tutorial"] fallback for missing sidecar). Compares re-generated
     paragraphs.json against on-disk baseline byte-by-byte.
  2. segs.json + meta.json + summary.md mid-test mutation hash check —
     captures sha256 at start of test, re-checks at end. Catches v1.1 import
     side-effects that accidentally write to archive (D-29 hard violation).

OUT OF SCOPE (must be verified by MANUAL GATE — see done block):
  - summary.md byte-equal — Claude Code cannot auto-re-invoke `/summarize-video`
    from a Python script (the slash command is a Claude prompt, not a Python
    function). Therefore: BEFORE phase 07 close, the user MUST manually re-run
    `/summarize-video` on 2 representative archives WITHOUT `.v11_features.json`
    marker (1 replicate-guide + 1 interview-distillation), and verify the
    resulting summary.md is byte-equal to the committed v1.0 baseline using
    `git diff --no-index <baseline> <regen>`. This script's docstring lists
    the exact commands to run.

Iterates every `output/<slug>/` directory that:
  (a) contains all 4 of: meta.json, segs.json, paragraphs.json, summary.md
  (b) does NOT have `.v11_features.json` marker (would imply v1.1 opt-in)

For each candidate slug:
  1. Hash the current on-disk segs.json + meta.json + paragraphs.json + summary.md
     (these are the v1.0 baseline — committed to git).
  2. Resolve the slug's aggregation profile from `paragraphs.json.params.json`
     sidecar (cli.profile preferred, func.profile fallback, "tutorial" default
     for missing sidecar).
  3. Re-run `aggregate` from segs.json using the resolved profile -> produce
     candidate paragraphs.json in a temp dir; do NOT touch the on-disk file.
  4. Compare temp paragraphs.json byte-by-byte against on-disk one.
  5. Mid-test mutation check: re-hash segs.json + meta.json + summary.md
     (these are NOT regenerated; just confirming v1.1 imports didn't side-effect
     mutate them).

Loud failure on any single byte diff: print slug + file + first diff offset.

NOT a CI hook — manual run before phase 07 close (and before phase 08 / 09 ship).

MANUAL GATE COMMANDS (run before phase 07 close):
  # 1. Run automated replay (this script):
  python -m scripts.replay_v10_archives
  # MUST show: fail=0 (strict byte-equal gate; any FAIL = phase NOT shippable)

  # 2. Manual /summarize-video re-run gate (Claude session, NOT a script):
  #    Pick 2 archives without .v11_features.json marker:
  #      - 1 replicate-guide:        BV132wizyEEB (or any in 17 archives)
  #      - 1 interview-distillation: douyin_karpathy_llm_wiki
  #    For each: re-invoke `/summarize-video` from a fresh Claude session,
  #    let it write to a temp slug dir (e.g., output/test_replay_<slug>),
  #    then diff:
  #      git diff --no-index output/<slug>/summary.md output/test_replay_<slug>/summary.md
  #    EXPECTED: zero output (byte-equal). Any diff = phase 07 NOT shippable.

Usage:
    python -m scripts.replay_v10_archives                       # check all candidates
    python -m scripts.replay_v10_archives --slug BV1HG9JBsEPK   # check one
    python -m scripts.replay_v10_archives --json                # machine-readable output

Exit codes:
    0 = all PASS
    1 = at least one FAIL
    2 = no candidates found (likely run from wrong dir)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

# Defensive sys.path setup so script works run as `python scripts/replay_v10_archives.py`
# OR `python -m scripts.replay_v10_archives` from repo root.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent._v11 import is_v11_enabled
from agent.io import load_segs, write_json_atomic
from agent.asr_v2 import aggregate_paragraphs, paragraphs_to_dicts, PROFILES

REQUIRED_FILES = ("meta.json", "segs.json", "paragraphs.json", "summary.md")
# segs.json + meta.json + summary.md are mid-test mutation-checked (NOT regenerated).
# paragraphs.json IS regenerated and byte-compared.
# summary.md byte-equal regen is verified by the MANUAL GATE documented in the
# docstring (Claude must re-invoke `/summarize-video` since it's a slash command,
# not a Python function).
MUTATION_CHECK_FILES = ("meta.json", "segs.json", "summary.md")


def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _load_profile_for_slug(slug_dir: Path) -> dict:
    """Resolve the profile dict for this slug's paragraphs.json regen.

    Reads `<slug_dir>/paragraphs.json.params.json` sidecar (Phase 5 D-27).
    Preference order: cli.profile -> func.profile -> "tutorial" fallback.

    Why this matters: interview-distillation slugs (e.g.,
    douyin_karpathy_llm_wiki) were aggregated with --profile=podcast.
    Hardcoding "tutorial" yields a false FAIL on those archives.
    Backward-compat: pre-Phase-5 archives have NO sidecar -> fall back to
    "tutorial" (which equals D-29 backward-compat alias for profile=None
    in aggregate_paragraphs).
    """
    sidecar = slug_dir / "paragraphs.json.params.json"
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            profile = (
                (data.get("cli") or {}).get("profile")
                or (data.get("func") or {}).get("profile")
            )
            if profile in PROFILES:
                return PROFILES[profile]
        except (json.JSONDecodeError, OSError):
            pass  # fall through to tutorial default
    return PROFILES["tutorial"]  # D-29 backward-compat alias


def _resolved_profile_name(slug_dir: Path) -> str | None:
    """Return the profile name string actually resolved (for result transparency).

    Returns one of: "tutorial", "podcast", "tutorial-fallback" (sidecar missing
    or unreadable), or "<sidecar-corrupt>" (sidecar exists but is malformed).
    """
    sidecar = slug_dir / "paragraphs.json.params.json"
    if not sidecar.exists():
        return "tutorial-fallback"
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        profile = (
            (data.get("cli") or {}).get("profile")
            or (data.get("func") or {}).get("profile")
        )
        if profile in PROFILES:
            return profile
        return "tutorial-fallback"
    except (json.JSONDecodeError, OSError):
        return "<sidecar-corrupt>"


def _is_candidate(slug_dir: Path) -> tuple[bool, str]:
    """Return (is_candidate, reason_if_not)."""
    if not slug_dir.is_dir():
        return False, "not a directory"
    if is_v11_enabled(slug_dir):
        return False, "has .v11_features.json marker (v1.1 opt-in; not a v1.0 archive)"
    missing = [f for f in REQUIRED_FILES if not (slug_dir / f).exists()]
    if missing:
        return False, f"missing required files: {missing}"
    return True, ""


def _replay_one(slug_dir: Path) -> dict:
    """Returns result dict: {slug, status: PASS|FAIL, profile, diffs: [...]}"""
    slug = slug_dir.name
    segs_path = slug_dir / "segs.json"

    # Step 1: Capture baseline hashes for the canonical artifacts.
    baseline_hashes = {f: _sha256_file(slug_dir / f) for f in REQUIRED_FILES}

    # Step 2: Resolve per-slug profile from sidecar (D-27 / fixes false-FAIL on
    # podcast-aggregated archives like douyin_karpathy_llm_wiki).
    profile_dict = _load_profile_for_slug(slug_dir)
    profile_name = _resolved_profile_name(slug_dir)

    # Step 3: Re-run aggregate in temp dir using the resolved profile.
    diffs: list[dict] = []
    try:
        segs = load_segs(segs_path)
        paragraphs = aggregate_paragraphs(
            segs,
            gap_threshold=profile_dict["gap_threshold"],
            max_para_duration=profile_dict["max_para_duration"],
            sentence_gap=profile_dict["sentence_gap"],
        )
        paras_data = paragraphs_to_dicts(paragraphs)

        with tempfile.TemporaryDirectory() as td:
            tmp_paragraphs = Path(td) / "paragraphs.json"
            write_json_atomic(tmp_paragraphs, paras_data)
            replayed_hash = _sha256_file(tmp_paragraphs)
    except Exception as e:
        return {
            "slug": slug,
            "status": "FAIL",
            "profile": profile_name,
            "diffs": [{
                "file": "paragraphs.json",
                "reason": f"aggregate raised: {type(e).__name__}: {e}",
            }],
        }

    # Step 4: Compare paragraphs.json (the regenerated artifact).
    if replayed_hash != baseline_hashes["paragraphs.json"]:
        diffs.append({
            "file": "paragraphs.json",
            "baseline_sha256": baseline_hashes["paragraphs.json"],
            "replayed_sha256": replayed_hash,
            "reason": (
                f"byte mismatch -- aggregate output (profile={profile_name}) "
                f"differs from v1.0 baseline. D-29 regression: investigate "
                f"agent/asr_v2.py:aggregate_paragraphs changes since v1.0."
            ),
        })

    # Step 5: Mid-test mutation check on segs.json + meta.json + summary.md
    # (sanity check -- the test process shouldn't have written to them).
    for f in MUTATION_CHECK_FILES:
        current = _sha256_file(slug_dir / f)
        if current != baseline_hashes[f]:
            diffs.append({
                "file": f,
                "baseline_sha256": baseline_hashes[f],
                "current_sha256": current,
                "reason": (
                    "on-disk file changed during test -- D-29 violation: "
                    "v1.1 import side-effects mutated archive"
                ),
            })

    return {
        "slug": slug,
        "status": "PASS" if not diffs else "FAIL",
        "profile": profile_name,
        "diffs": diffs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.replay_v10_archives",
        description=(
            "17-archive byte-equal replay (Phase 07 PRE-V11-02 / P-08 D-29 gate). "
            "Re-runs aggregate from segs.json using per-slug profile and diffs "
            "paragraphs.json byte-by-byte against committed baseline. Strict gate: "
            "any single byte diff = FAIL = phase NOT shippable. See module docstring "
            "for MANUAL GATE COMMANDS that complete the summary.md byte-equal proof."
        ),
    )
    parser.add_argument(
        "--slug",
        default=None,
        help="check only this slug (default: all candidates under output/)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of human-readable text",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="root directory containing slug subdirs (default: output)",
    )
    args = parser.parse_args()

    output_root = Path(args.output_dir)
    if not output_root.is_dir():
        print(f"FATAL: output directory not found: {output_root}", file=sys.stderr)
        return 2

    if args.slug:
        candidates = [output_root / args.slug]
    else:
        candidates = sorted(p for p in output_root.iterdir() if p.is_dir())

    results: list[dict] = []
    skipped: list[dict] = []
    for slug_dir in candidates:
        ok, reason = _is_candidate(slug_dir)
        if not ok:
            skipped.append({"slug": slug_dir.name, "reason": reason})
            continue
        results.append(_replay_one(slug_dir))

    n_pass = sum(1 for r in results if r["status"] == "PASS")
    n_fail = sum(1 for r in results if r["status"] == "FAIL")
    n_skip = len(skipped)

    if args.json:
        print(json.dumps({
            "summary": {
                "pass": n_pass,
                "fail": n_fail,
                "skip": n_skip,
                "total_candidates": len(results),
            },
            "results": results,
            "skipped": skipped,
        }, ensure_ascii=False, indent=2))
    else:
        print("=" * 72)
        print("17-archive byte-equal replay (PRE-V11-02 / D-29 gate)")
        print("=" * 72)
        for r in results:
            status_marker = "PASS" if r["status"] == "PASS" else "**FAIL**"
            print(f"  {status_marker:8s}  {r['slug']:40s}  profile={r.get('profile', '?')}")
            for d in r["diffs"]:
                print(f"             -> {d['file']}: {d['reason']}")
        print("-" * 72)
        print(
            f"Summary: {n_pass} PASS / {n_fail} FAIL / {n_skip} SKIP "
            f"(of {len(results)} candidates)"
        )
        if skipped:
            print(
                f"\nSkipped {n_skip} dirs (most are non-archive -- "
                f"opt-in marker / partial / not slug):"
            )
            for s in skipped[:10]:
                print(f"  {s['slug']}: {s['reason']}")
            if len(skipped) > 10:
                print(f"  ... ({len(skipped) - 10} more -- use --json for full list)")
        if n_fail > 0:
            print("\n*** D-29 BYTE-EQUAL REGRESSION ***")
            print("Phase 07 is NOT shippable until ALL FAIL slugs PASS (strict gate).")
            print("Run with --json | python -m json.tool for machine-readable diff output.")
        else:
            print("\nAUTOMATED GATE PASSED. Now run the MANUAL GATE before phase close:")
            print("  See script docstring section 'MANUAL GATE COMMANDS'.")

    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
