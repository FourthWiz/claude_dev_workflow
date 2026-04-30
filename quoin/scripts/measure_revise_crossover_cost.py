#!/usr/bin/env python3
"""measure_revise_crossover_cost.py — compare /revise (Opus) vs /revise-fast (Sonnet).

Discovery: scans .workflow_artifacts/finalized/<task>/cost-ledger.md for all
finalized tasks, filters to Medium profile, aggregates revise sessions per task.

Aggregation unit: "task" = root folder under finalized/, NOT stage. Multi-stage
tasks aggregate ALL stage cost-ledger rows for revise/revise-fast phases.

Decision rule (one-sided):
  RECOMMEND DEPRECATE /revise-fast if BOTH:
    mean(opus_total_cost) <= mean(fast_total_cost) + 1*stderr(fast)
    AND mean(opus_round_count) <= mean(fast_round_count)
  Otherwise: RECOMMEND PRESERVE /revise-fast.
"""
import argparse
import json
import math
import os
import pathlib
import re
import sys

# ---------------------------------------------------------------------------
# Import cost helpers from sibling script
# ---------------------------------------------------------------------------
_SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPT_DIR))
from cost_from_jsonl import project_hash, jsonl_path_for, parse_session  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_OPUS_MODELS = {"opus", "claude-opus-4-7", "claude-opus-4-6", "claude-opus"}
_SONNET_MODELS = {"sonnet", "claude-sonnet-4-6", "claude-sonnet-4-5", "claude-sonnet"}
_PROFILE_RE = re.compile(
    r"^\s*[-*]?\s*\*?\*?Task profile:\*?\*?\s*(Small|Medium|Large)", re.MULTILINE
)

# Derive project root from this file's location (quoin/scripts/ → project root)
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_FINALIZED_ROOT = _PROJECT_ROOT / ".workflow_artifacts" / "finalized"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_profile(task_root: pathlib.Path) -> "str | None":
    """Return 'Small', 'Medium', 'Large', or None if undetectable."""
    # Try root current-plan.md first
    for plan_path in [
        task_root / "current-plan.md",
        # Multi-stage: check stage subdirs
    ]:
        if plan_path.exists():
            m = _PROFILE_RE.search(plan_path.read_text(encoding="utf-8"))
            if m:
                return m.group(1)

    # Also check stage subdirs for multi-stage tasks
    for stage_dir in sorted(task_root.glob("stage-*/current-plan.md")):
        m = _PROFILE_RE.search(stage_dir.read_text(encoding="utf-8"))
        if m:
            return m.group(1)
    for nested in sorted(task_root.glob("finalized/stage-*/current-plan.md")):
        m = _PROFILE_RE.search(nested.read_text(encoding="utf-8"))
        if m:
            return m.group(1)

    # Fallback: check architecture.md
    arch = task_root / "architecture.md"
    if arch.exists():
        m = _PROFILE_RE.search(arch.read_text(encoding="utf-8"))
        if m:
            return m.group(1)

    return None


def _collect_ledger_rows(task_root: pathlib.Path) -> list:
    """Collect ALL cost-ledger rows from root + all nested stage ledgers."""
    rows = []
    ledger_paths = [
        task_root / "cost-ledger.md",
        *sorted(task_root.glob("stage-*/cost-ledger.md")),
        *sorted(task_root.glob("finalized/stage-*/cost-ledger.md")),
    ]
    for lpath in ledger_paths:
        if not lpath.exists():
            continue
        for line in lpath.read_text(encoding="utf-8").splitlines():
            parts = [p.strip() for p in line.split("|")]
            # Column contract: col 0=uuid, 1=date, 2=phase, 3=model, 4=category, 5=note, 6=fallback_fires (Stage 4+, optional). _collect_ledger_rows ignores cols 4+ — verify 7-column tolerance if you ever unpack them.
            if len(parts) < 4:
                continue
            uuid, _date, phase, model = parts[0], parts[1], parts[2], parts[3]
            if not uuid or uuid.startswith("#") or uuid.startswith("-"):
                continue
            rows.append({"uuid": uuid, "phase": phase, "model": model})
    return rows


def _variant_for_model(model: str) -> "str | None":
    """Return 'opus' or 'fast' for a model name, or None if unrecognized."""
    m = model.lower()
    if any(k in m for k in ("opus",)):
        return "opus"
    if any(k in m for k in ("sonnet", "haiku")):
        return "fast"
    return None


def _session_cost(uuid: str, proj_hash_val: str) -> float:
    """Return total cost for a session UUID; 0.0 if JSONL not found."""
    jpath = jsonl_path_for(uuid, proj_hash_val)
    if not jpath.exists():
        return 0.0
    result = parse_session(jpath)
    return result.get("totalCost", 0.0)


def _mean(vals: list) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _stderr(vals: list) -> float:
    if len(vals) < 2:
        return 0.0
    n = len(vals)
    m = _mean(vals)
    variance = sum((v - m) ** 2 for v in vals) / (n - 1)
    return math.sqrt(variance / n)


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def analyse(
    task_dir: pathlib.Path,
    profile_filter: str,
    max_tasks: int,
    proj_hash_val: str,
    verbose: bool = False,
) -> dict:
    """Run the crossover analysis. Returns the result dict."""
    # 1. Discover finalized task roots
    # Skip backup dirs (*.bak) and dot-prefixed dirs (.git, .DS_Store, etc.) —
    # they are not real tasks and their cost ledgers (if any) would pollute the sample.
    task_roots = sorted(
        [
            d for d in task_dir.iterdir()
            if d.is_dir()
            and not d.name.startswith(".")
            and not d.name.endswith(".bak")
        ],
        key=lambda d: (d / "cost-ledger.md").stat().st_mtime
        if (d / "cost-ledger.md").exists()
        else 0,
        reverse=True,
    )

    # 2. Filter to requested profile
    medium_tasks = []
    for root in task_roots:
        profile = _detect_profile(root)
        if profile and profile.lower() == profile_filter.lower():
            medium_tasks.append(root)

    if verbose:
        print(f"Found {len(medium_tasks)} {profile_filter} tasks in {task_dir}:", file=sys.stderr)
        for t in medium_tasks:
            print(f"  {t.name}", file=sys.stderr)

    # Cap at max_tasks (most recent by root ledger mtime)
    medium_tasks = medium_tasks[:max_tasks]

    # 3. Per-task aggregation
    opus_tasks = []   # list of {name, total_cost, round_count, n_stages}
    fast_tasks = []

    for task_root in medium_tasks:
        rows = _collect_ledger_rows(task_root)
        revise_rows = [r for r in rows if r["phase"].strip() in ("revise", "revise-fast")]

        opus_rows = [r for r in revise_rows if _variant_for_model(r["model"]) == "opus"]
        fast_rows = [r for r in revise_rows if _variant_for_model(r["model"]) == "fast"]

        # Classify task
        if len(opus_rows) > len(fast_rows):
            track = "opus"
        elif fast_rows:
            track = "fast"
        elif opus_rows:
            track = "opus"
        else:
            continue  # no revise rows — skip

        active_rows = opus_rows if track == "opus" else fast_rows
        round_count = len(active_rows)

        # Compute total cost for this task's revise sessions
        total_cost = 0.0
        for row in active_rows:
            total_cost += _session_cost(row["uuid"].strip(), proj_hash_val)

        # Count stages
        stage_count = 1
        stage_dirs = list(task_root.glob("stage-*/")) + list(task_root.glob("finalized/stage-*/"))
        if stage_dirs:
            stage_count = len(stage_dirs)

        entry = {
            "name": task_root.name,
            "total_cost": total_cost,
            "round_count": round_count,
            "n_stages": stage_count,
        }

        if track == "opus":
            opus_tasks.append(entry)
        else:
            fast_tasks.append(entry)

    n_opus = len(opus_tasks)
    n_fast = len(fast_tasks)

    result = {
        "n_opus": n_opus,
        "n_fast": n_fast,
        "opus_tasks": [t["name"] for t in opus_tasks],
        "fast_tasks": [t["name"] for t in fast_tasks],
        "n_stages_per_task": {
            t["name"]: t["n_stages"] for t in (opus_tasks + fast_tasks)
        },
        "round_count_per_task": {
            t["name"]: t["round_count"] for t in (opus_tasks + fast_tasks)
        },
    }

    if n_opus < 3 or n_fast < 3:
        result["recommendation"] = "INSUFFICIENT DATA"
        result["caveats"] = (
            f"Need ≥3 tasks per track. Have {n_opus} opus, {n_fast} fast. "
            "Re-run after 5 more Medium tasks land."
        )
        result["mean_opus_cost"] = _mean([t["total_cost"] for t in opus_tasks])
        result["mean_fast_cost"] = _mean([t["total_cost"] for t in fast_tasks])
        result["stderr_opus"] = _stderr([t["total_cost"] for t in opus_tasks])
        result["stderr_fast"] = _stderr([t["total_cost"] for t in fast_tasks])
        result["mean_opus_rounds"] = _mean([t["round_count"] for t in opus_tasks])
        result["mean_fast_rounds"] = _mean([t["round_count"] for t in fast_tasks])
        return result

    opus_costs = [t["total_cost"] for t in opus_tasks]
    fast_costs = [t["total_cost"] for t in fast_tasks]
    opus_rounds = [float(t["round_count"]) for t in opus_tasks]
    fast_rounds = [float(t["round_count"]) for t in fast_tasks]

    mean_oc = _mean(opus_costs)
    mean_fc = _mean(fast_costs)
    se_fc = _stderr(fast_costs)
    mean_or = _mean(opus_rounds)
    mean_fr = _mean(fast_rounds)
    se_oc = _stderr(opus_costs)
    se_fr = _stderr(fast_rounds)

    cost_ok = mean_oc <= mean_fc + se_fc
    rounds_ok = mean_or <= mean_fr

    if cost_ok and rounds_ok:
        recommendation = "RECOMMEND DEPRECATE /revise-fast"
    else:
        recommendation = "RECOMMEND PRESERVE /revise-fast"

    caveats = []
    if not cost_ok:
        caveats.append(
            f"Cost: opus mean ${mean_oc:.4f} > fast mean ${mean_fc:.4f} + 1×stderr ${se_fc:.4f}"
        )
    if not rounds_ok:
        caveats.append(
            f"Rounds: opus mean {mean_or:.1f} > fast mean {mean_fr:.1f}"
        )
    if not caveats:
        caveats.append(
            f"Opus is cheaper (${mean_oc:.4f} vs ${mean_fc:.4f}) and uses fewer rounds "
            f"({mean_or:.1f} vs {mean_fr:.1f})."
        )

    result.update({
        "mean_opus_cost": mean_oc,
        "mean_fast_cost": mean_fc,
        "stderr_opus": se_oc,
        "stderr_fast": se_fc,
        "mean_opus_rounds": mean_or,
        "mean_fast_rounds": mean_fr,
        "recommendation": recommendation,
        "caveats": " ".join(caveats),
    })
    return result


def _render_markdown(result: dict, profile: str) -> str:
    """Render the auto-generated Section 1 of the decision write-up."""
    lines = [
        "## Section 1 — Measurement",
        "",
        f"Profile filter: {profile}",
        f"Tasks analysed — Opus track: {result['n_opus']}, Fast (Sonnet) track: {result['n_fast']}",
        "",
        "| Metric | Opus (/revise) | Fast (/revise-fast) |",
        "|--------|---------------|---------------------|",
        f"| Tasks  | {result['n_opus']} | {result['n_fast']} |",
        f"| Mean revise cost | ${result.get('mean_opus_cost', 0):.4f} | ${result.get('mean_fast_cost', 0):.4f} |",
        f"| Stderr revise cost | ${result.get('stderr_opus', 0):.4f} | ${result.get('stderr_fast', 0):.4f} |",
        f"| Mean round count | {result.get('mean_opus_rounds', 0):.1f} | {result.get('mean_fast_rounds', 0):.1f} |",
        "",
        "**Task name / stage count:**",
        "",
    ]
    for name in result.get("opus_tasks", []):
        stages = result.get("n_stages_per_task", {}).get(name, 1)
        lines.append(f"- {name} (Opus, {stages} stage(s))")
    for name in result.get("fast_tasks", []):
        stages = result.get("n_stages_per_task", {}).get(name, 1)
        lines.append(f"- {name} (Fast, {stages} stage(s))")

    lines += [
        "",
        f"**Recommendation:** {result.get('recommendation', 'N/A')}",
        "",
        f"**Caveats:** {result.get('caveats', '')}",
        "",
        "<!-- AUTO-GENERATED — do not edit below -->",
    ]
    return "\n".join(lines)


def _write_out(out_path: pathlib.Path, section1: str) -> None:
    """Write/update Section 1, preserving anything after the sentinel."""
    sentinel = "<!-- AUTO-GENERATED — do not edit below -->"
    if out_path.exists():
        existing = out_path.read_text(encoding="utf-8")
        if sentinel in existing:
            # Keep everything after the sentinel (Section 2)
            after = existing[existing.index(sentinel) + len(sentinel):]
            content = section1 + after
        else:
            content = section1
    else:
        content = section1 + "\n\n## Section 2 — Decision\n\n_(Hand-written. Replace this placeholder with the keep-or-deprecate verdict.)_\n"

    tmp = out_path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.rename(str(tmp), str(out_path))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task-dir", default=str(_FINALIZED_ROOT),
                    help="Root dir containing finalized task subfolders")
    ap.add_argument("--profile", default="medium",
                    help="Task profile to filter (default: medium)")
    ap.add_argument("--max-tasks", type=int, default=5,
                    help="Max tasks per analysis (default: 5)")
    ap.add_argument("--out", default=None,
                    help="Write markdown summary to this path")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    proj_hash_val = project_hash(str(_PROJECT_ROOT))
    task_dir = pathlib.Path(args.task_dir)

    result = analyse(task_dir, args.profile, args.max_tasks, proj_hash_val,
                     verbose=args.verbose)

    print(json.dumps(result, indent=2))

    if args.out:
        section1 = _render_markdown(result, args.profile)
        out_path = pathlib.Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _write_out(out_path, section1)
        print(f"\nMarkdown summary written to: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
