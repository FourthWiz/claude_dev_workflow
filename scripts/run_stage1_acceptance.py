"""
Stage 1 acceptance driver for caveman-token-optimization.

Orchestrates the two Stage 1 gates:
  1. Structural gate: single-artifact contract checks via caveman_fidelity_probe.run_checks
  2. Dollar gate: deterministic structural cost proxy via caveman_fidelity_probe.compute_cost_proxy

Usage:
  python scripts/run_stage1_acceptance.py [options]

Options:
  --post-rubric-since <commit-sha>
      Harvest post-rubric Tier 3 artifacts modified after this commit.
      Defaults to: git log --oneline --grep="Task 3" HEAD | head -1 (auto-detect).
  --reference-profile <name>
      Named reference task profile for dollar-gate denominator (default: medium).
  --output <path>
      Where to write the acceptance report (default: .workflow_artifacts/
      caveman-token-optimization/stage1-acceptance-<ISO-date>.md).
  --min-samples <N>
      Minimum post-rubric samples required per Tier 3 artifact type (default: 3).
  --dry-run
      Use .workflow_artifacts/finalized/ artifacts as pseudo-post-rubric samples.
      Useful for pipeline-wiring verification before any real post-rubric work exists.

Architecture ref: caveman-token-optimization/architecture.md §8.1 (structural gate),
§11 (dollar gate), CRIT-1 resolution (single-artifact contracts), CRIT-2 resolution
(deterministic structural cost proxy, 2026-04-23).

This script does NOT shell out to Claude or any skill. Stdlib only.
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Path setup — import probe as sibling in same scripts/ directory
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import caveman_fidelity_probe as probe

FINALIZED_DIR = PROJECT_ROOT / ".workflow_artifacts" / "finalized"
TASK_DIR = PROJECT_ROOT / ".workflow_artifacts" / "caveman-token-optimization"
COST_LEDGER_PATH = TASK_DIR / "cost-ledger.md"
JSONL_DIR = Path(os.environ.get(
    "CLAUDE_PROJECT_HASH_DIR",
    "~/.claude/projects/-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan-gorban-gmail-com-My-Drive-Storage-Claude-workflow"
)).expanduser()

# ---------------------------------------------------------------------------
# Harvest helpers
# ---------------------------------------------------------------------------

def _git_commit_timestamp(sha: str) -> float:
    """Return unix timestamp for a commit SHA, or 0.0 if unavailable."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct", sha],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        ts = result.stdout.strip()
        return float(ts) if ts else 0.0
    except Exception:
        return 0.0


def _detect_post_rubric_commit() -> str:
    """Try to auto-detect the Task 3 completion commit by grepping git log."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--grep=Task 3", "HEAD"],
            capture_output=True, text=True, cwd=PROJECT_ROOT
        )
        lines = result.stdout.strip().split("\n")
        if lines and lines[0]:
            return lines[0].split()[0]
    except Exception:
        pass
    return ""


def _find_artifacts_since(since_sha: str) -> Dict[str, List[Path]]:
    """
    Walk .workflow_artifacts/ for .md files modified after since_sha's commit timestamp.
    Returns {artifact_type: [Path, ...]} using probe's ARTIFACT_TYPE_PATTERNS.
    Excludes finalized/, caveman-token-optimization/, and cache/.
    """
    cutoff = _git_commit_timestamp(since_sha) if since_sha else 0.0
    wa = PROJECT_ROOT / ".workflow_artifacts"
    found: Dict[str, List[Path]] = {k: [] for k in probe.ARTIFACT_TYPE_PATTERNS}

    for path in wa.rglob("*.md"):
        rel = path.relative_to(wa)
        parts = rel.parts
        if not parts:
            continue
        if parts[0] in ("finalized", "caveman-token-optimization", "cache"):
            continue
        if cutoff and path.stat().st_mtime <= cutoff:
            continue
        for atype, pattern in probe.ARTIFACT_TYPE_PATTERNS.items():
            if re.search(pattern, str(path)):
                found[atype].append(path)
                break

    return found


def _collect_dry_run_artifacts() -> Dict[str, List[Path]]:
    """
    For --dry-run: treat .workflow_artifacts/finalized/ as pseudo-post-rubric.
    Returns {artifact_type: [Path, ...]} mapping.
    """
    found: Dict[str, List[Path]] = {k: [] for k in probe.ARTIFACT_TYPE_PATTERNS}
    for path in FINALIZED_DIR.rglob("*.md"):
        for atype, pattern in probe.ARTIFACT_TYPE_PATTERNS.items():
            if re.search(pattern, str(path)):
                found[atype].append(path)
                break
    return found


def _copy_samples_to_run_dir(artifacts: Dict[str, List[Path]], run_dir: Path) -> Path:
    """
    Copy harvested artifacts into the run dir for reproducibility.
    Returns run_dir (with files now present).
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    for atype, paths in artifacts.items():
        if not paths:
            continue
        type_dir = run_dir / atype
        type_dir.mkdir(exist_ok=True)
        for src in paths:
            dst = type_dir / src.name
            if dst.exists():
                dst = type_dir / f"{src.parent.name}_{src.name}"
            shutil.copy2(src, dst)
    return run_dir


# ---------------------------------------------------------------------------
# Structural gate
# ---------------------------------------------------------------------------

def run_structural_checks(artifacts: Dict[str, List[Path]]) -> Tuple[dict, bool]:
    """
    Run probe.run_checks on each artifact file.
    Returns (results_by_type, structural_pass).
    """
    results_by_type: Dict[str, List] = {}
    structural_pass = True

    for atype, paths in artifacts.items():
        if not paths:
            continue
        type_results = []
        for path in paths:
            if not path.exists():
                continue
            sr = probe.run_checks(atype, path)
            type_results.append(sr)

        if not type_results:
            continue
        results_by_type[atype] = type_results

        # Gate: ≥1 PASS, 0 FAIL, 0 INVALID per type
        pass_count = sum(1 for r in type_results if r.verdict == "PASS")
        fail_count = sum(1 for r in type_results if r.verdict == "FAIL")
        invalid_count = sum(1 for r in type_results if r.verdict == "INVALID")
        if fail_count > 0 or invalid_count > 0 or pass_count == 0:
            structural_pass = False

    return results_by_type, structural_pass


# ---------------------------------------------------------------------------
# Dollar gate (delegates to probe)
# ---------------------------------------------------------------------------

def run_dollar_gate(post_sample_dir: Optional[Path]) -> Tuple[list, bool, float]:
    """
    Compute structural cost proxy via probe.compute_cost_proxy.
    Returns (proxy_results, dollar_gate_pass, total_usd).
    """
    artifact_types = list(probe.ARTIFACT_TYPE_PATTERNS.keys())
    proxy_results = probe.compute_cost_proxy(artifact_types, post_sample_dir=post_sample_dir)
    verdict, total_usd = probe.dollar_gate_verdict(proxy_results)
    return proxy_results, verdict == "PASS", total_usd


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    output_path: Path,
    harvest_source: str,
    since_sha: str,
    min_samples: int,
    dry_run: bool,
    structural_results: dict,
    structural_pass: bool,
    proxy_results: list,
    dollar_gate_pass: bool,
    total_usd: float,
    reference_profile: str,
    jsonl_note: str = "",
) -> None:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    pc = probe.PROXY_CONSTANTS
    lines = []

    lines += [
        "# Stage 1 Acceptance Report",
        "",
        f"**Generated:** {now}",
        f"**Mode:** {'dry-run (finalized/ as pseudo-post-rubric)' if dry_run else 'live harvest'}",
        f"**Post-rubric since:** `{since_sha or '(none — dry-run)'}`",
        f"**Harvest source:** {harvest_source}",
        f"**Reference profile:** {reference_profile}",
        f"**Min samples required:** {min_samples}",
        "",
        "---",
        "",
    ]

    # Structural gate table
    lines += [
        "## Structural Gate",
        "",
        "| Artifact type | Samples | PASS | FAIL | INVALID | Verdict |",
        "|---------------|---------|------|------|---------|---------|",
    ]
    for atype, results in structural_results.items():
        p = sum(1 for r in results if r.verdict == "PASS")
        f = sum(1 for r in results if r.verdict == "FAIL")
        inv = sum(1 for r in results if r.verdict == "INVALID")
        v = "PASS" if f == 0 and inv == 0 and p > 0 else "FAIL"
        lines.append(f"| {atype} | {len(results)} | {p} | {f} | {inv} | {v} |")
    lines += [
        "",
        f"**Structural gate: {'PASS' if structural_pass else 'FAIL'}**",
        "",
    ]

    # Per-sample detail (non-N/A checks only)
    if structural_results:
        lines.append("### Per-sample check detail")
        lines.append("")
        for atype, results in structural_results.items():
            lines.append(f"#### {atype}")
            for sr in results:
                lines.append(f"- `{sr.sample_path.name}` → **{sr.verdict}**")
                for cr in sr.checks:
                    if cr.status != "N/A":
                        suffix = f" ({cr.reason})" if cr.reason else ""
                        lines.append(f"  - {cr.name}: {cr.status}{suffix}")
        lines.append("")

    # Dollar gate
    lines += [
        "## Dollar Gate (structural cost proxy)",
        "",
        "Formula: `(S_pre_mean − S_post_mean) × tokens_per_byte × cache_read_price_per_Mtok × est_reads_per_task / 1_000_000`",
        "",
    ]
    if proxy_results:
        lines += [
            "| Artifact type | S_pre (B) | S_post (B) | Δ bytes | est_reads | Projected Δ USD |",
            "|---------------|-----------|------------|---------|-----------|-----------------|",
        ]
        for pr in proxy_results:
            lines.append(
                f"| {pr.artifact_type} | {pr.s_pre_mean} | {pr.s_post_mean} "
                f"| {pr.delta_bytes} | {pr.est_reads_per_task} "
                f"| ${pr.projected_delta_usd:.4f} |"
            )
        lines += [
            "",
            f"**Total projected Δ USD per task:** ${total_usd:.4f}",
            f"**Dollar-gate threshold:** $1.00/task (reference: {reference_profile} profile)",
            f"**Dollar gate: {'PASS' if dollar_gate_pass else 'FAIL (below $1.00 threshold)'}**",
        ]
    else:
        lines += [
            "No overlapping pre/post-rubric samples found for cost proxy.",
            "**Dollar gate: FAIL (insufficient data)**",
        ]
    lines.append("")

    # PROXY_CONSTANTS audit dump
    lines += [
        "### PROXY_CONSTANTS (audit)",
        "",
        "```",
        f"tokens_per_byte = {pc['tokens_per_byte']}",
        f"cache_read_price_per_mtok_opus = {pc['cache_read_price_per_mtok_opus']}",
        f"est_reads_per_task_per_type = {pc['est_reads_per_task_per_type']}",
        "```",
        "",
    ]

    # Optional JSONL historical note
    if jsonl_note:
        lines += [
            "## JSONL historical anchor (informational only — not a gate)",
            "",
            jsonl_note,
            "",
        ]

    # Final verdict
    combined_pass = structural_pass and dollar_gate_pass
    lines += ["---", ""]
    if combined_pass:
        lines.append("**Stage 1 acceptance: PASS**")
    else:
        reasons = []
        if not structural_pass:
            reasons.append("structural gate failed (FAIL or INVALID checks present)")
        if not dollar_gate_pass:
            reasons.append(f"dollar gate failed (total ${total_usd:.4f} < $1.00 threshold)")
        lines.append(f"**Stage 1 acceptance: FAIL — REASON: {'; '.join(reasons)}**")
    lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Report written to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage 1 acceptance driver for caveman-token-optimization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--post-rubric-since", metavar="COMMIT_SHA",
        help="Harvest artifacts modified after this commit. Auto-detected from git log if omitted.",
    )
    parser.add_argument(
        "--reference-profile", default="medium",
        help="Named reference task profile for dollar-gate denominator (default: medium).",
    )
    parser.add_argument(
        "--output", metavar="PATH",
        help="Output report path.",
    )
    parser.add_argument(
        "--min-samples", type=int, default=3, metavar="N",
        help="Minimum post-rubric samples required per Tier 3 artifact type (default: 3).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Use .workflow_artifacts/finalized/ as pseudo-post-rubric samples.",
    )
    args = parser.parse_args()

    iso_date = datetime.date.today().isoformat()
    output_path = Path(args.output) if args.output else (
        TASK_DIR / f"stage1-acceptance-{iso_date}.md"
    )

    print("Stage 1 acceptance driver — caveman-token-optimization")
    print(f"Reference profile: {args.reference_profile}")
    print(f"Min samples per type: {args.min_samples}")
    print(f"Dry-run: {args.dry_run}")
    print()

    # Determine since SHA
    since_sha = args.post_rubric_since or ""
    if not args.dry_run and not since_sha:
        since_sha = _detect_post_rubric_commit()
        if since_sha:
            print(f"Auto-detected post-rubric since: {since_sha}")
        else:
            print(
                "WARNING: Could not auto-detect Task 3 completion commit. "
                "Pass --post-rubric-since <sha> to specify. "
                "Falling back to all non-finalized artifacts."
            )

    # Harvest samples
    print("Harvesting post-rubric samples...")
    if args.dry_run:
        raw_artifacts = _collect_dry_run_artifacts()
        harvest_source = f"dry-run: {FINALIZED_DIR}"
        post_sample_dir: Optional[Path] = FINALIZED_DIR
    else:
        raw_artifacts = _find_artifacts_since(since_sha)
        harvest_source = (
            f"Harvested from .workflow_artifacts/ since commit {since_sha}"
            if since_sha else
            "Harvested from .workflow_artifacts/ (no since-commit)"
        )
        post_sample_dir = None

    # Report counts and check minimums
    found_any = False
    for atype, paths in raw_artifacts.items():
        if paths:
            found_any = True
            print(f"  {atype}: {len(paths)} sample(s)")
            if not args.dry_run and len(paths) < args.min_samples:
                print(
                    f"  WARNING: {atype} has only {len(paths)} sample(s), "
                    f"need ≥{args.min_samples}. Gates may show partial coverage."
                )

    if not found_any:
        print(
            f"\nNo post-rubric samples found. "
            f"Run one more real {args.reference_profile.capitalize()}-profile task "
            f"after Task 3 completes, then re-invoke."
        )
        if not args.dry_run:
            return 1

    # Copy samples to run dir (live mode only — keeps artifacts for reproducibility)
    if not args.dry_run and found_any:
        ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        run_dir = TASK_DIR / f"stage1-post-rubric-samples-{ts}"
        run_dir = _copy_samples_to_run_dir(raw_artifacts, run_dir)
        post_sample_dir = run_dir
        print(f"Samples copied to: {run_dir}")

    print()

    # Gate 1: structural
    print("Running structural gate (single-artifact contract checks)...")
    structural_results, structural_pass = run_structural_checks(raw_artifacts)
    print(f"Structural gate: {'PASS' if structural_pass else 'FAIL'}")
    print()

    # Gate 2: cost proxy
    print("Running dollar gate (structural cost proxy)...")
    proxy_results, dollar_gate_pass, total_usd = run_dollar_gate(post_sample_dir)
    print(f"Total projected Δ USD/task: ${total_usd:.4f}")
    print(f"Dollar gate: {'PASS' if dollar_gate_pass else 'FAIL (below $1.00)'}")
    print()

    # JSONL historical anchor (informational)
    jsonl_note = ""
    try:
        hist = probe.scan_jsonl_historical(COST_LEDGER_PATH, JSONL_DIR)
        if hist:
            jsonl_note = (
                f"JSONL historical scan (task: {hist.task}): "
                f"total ${hist.total_usd:.2f} "
                f"(cache_read ${hist.cache_read_usd:.2f}, "
                f"input ${hist.input_usd:.2f}, "
                f"output ${hist.output_usd:.2f}). "
                f"Informational only — not a gate."
            )
    except Exception as e:
        jsonl_note = f"JSONL historical scan skipped: {e}"

    # Write report
    write_report(
        output_path=output_path,
        harvest_source=harvest_source,
        since_sha=since_sha,
        min_samples=args.min_samples,
        dry_run=args.dry_run,
        structural_results=structural_results,
        structural_pass=structural_pass,
        proxy_results=proxy_results,
        dollar_gate_pass=dollar_gate_pass,
        total_usd=total_usd,
        reference_profile=args.reference_profile,
        jsonl_note=jsonl_note,
    )

    combined = structural_pass and dollar_gate_pass
    print(f"\nStage 1 acceptance: {'PASS' if combined else 'FAIL'}")
    return 0 if combined else 1


if __name__ == "__main__":
    sys.exit(main())
