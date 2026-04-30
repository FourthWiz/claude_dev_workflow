#!/usr/bin/env python3
"""measure_v_trip_rate.py — V-04/V-05/V-06 trip-rate measurement script.

Stage 4 of pipeline-efficiency-improvements (T-14). NOT deployed to ~/.claude/scripts/
— this is an analysis tool (mirrors verify_subagent_dispatch.md carve-out).

Usage:
    python3 quoin/scripts/measure_v_trip_rate.py --since YYYY-MM-DD --until YYYY-MM-DD [--json]
    python3 quoin/scripts/measure_v_trip_rate.py --tasks task1,task2 [--json]
    python3 quoin/scripts/measure_v_trip_rate.py --cost-ledger PATH [--json]

Reads two surfaces for fallback_fires:
  Surface 1 (primary): session-state files at .workflow_artifacts/memory/sessions/{date}-{task}.md
  Surface 2 (cross-check): cost-ledger 7th column on session-end rows for each task

Reports per-task: {task, sessions, fallback_fires_after_stage4, total_b_writes, trip_rate}

NOTE: Per-V-NN breakdown (V-04 / V-05 / V-06 separately) is NOT available in the
session-state-increment design — the increment is V-NN-agnostic. Aggregate count only.

Accepts --cost-ledger PATH flag to specify a non-default ledger path (Q-2 from plan).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional


def find_project_root(start: Path = Path.cwd()) -> Optional[Path]:
    """Walk up to find the directory containing .workflow_artifacts/."""
    p = start.resolve()
    for candidate in [p, *p.parents]:
        if (candidate / ".workflow_artifacts").is_dir():
            return candidate
    return None


def collect_session_state_files(
    project_root: Path,
    tasks: Optional[list[str]] = None,
    since: Optional[date] = None,
    until: Optional[date] = None,
) -> dict[str, list[Path]]:
    """Return {task_name: [session_state_paths]} filtered by date range and task list."""
    sessions_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"
    if not sessions_dir.is_dir():
        return {}

    result: dict[str, list[Path]] = {}
    for f in sorted(sessions_dir.glob("*.md")):
        # Filename pattern: YYYY-MM-DD-{task-name}.md
        stem = f.stem
        match = re.match(r"^(\d{4}-\d{2}-\d{2})-(.+)$", stem)
        if not match:
            continue
        date_str, task_name = match.group(1), match.group(2)
        try:
            file_date = date.fromisoformat(date_str)
        except ValueError:
            continue

        if since and file_date < since:
            continue
        if until and file_date > until:
            continue
        if tasks and task_name not in tasks:
            continue

        result.setdefault(task_name, []).append(f)

    return result


def read_fallback_fires_from_session(path: Path) -> int:
    """Extract fallback_fires count from a session-state file's ## Cost block."""
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return 0

    match = re.search(r"^- fallback_fires:\s*(\d+)\s*$", content, re.MULTILINE)
    if match:
        return int(match.group(1))
    return 0  # Pre-Stage-4 sessions: treat as 0, no warning


def collect_ledger_col7(
    project_root: Path,
    tasks: Optional[list[str]] = None,
    cost_ledger_override: Optional[Path] = None,
) -> dict[str, int]:
    """Sum 7th-column fallback_fires from cost-ledger files per task."""
    result: dict[str, int] = {}

    if cost_ledger_override:
        ledger_files = [cost_ledger_override] if cost_ledger_override.exists() else []
        # Derive task name from parent directory name
        task_name = cost_ledger_override.parent.name
    else:
        wa = project_root / ".workflow_artifacts"
        ledger_files = list(wa.glob("*/cost-ledger.md")) + list(
            wa.glob("finalized/*/cost-ledger.md")
        )

    for ledger_path in ledger_files:
        if cost_ledger_override:
            lname = task_name
        else:
            lname = ledger_path.parent.name
            if tasks and lname not in tasks:
                continue

        fires_sum = 0
        try:
            for lineno, line in enumerate(
                ledger_path.read_text(encoding="utf-8").splitlines(), 1
            ):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                parts = [p.strip() for p in stripped.split("|")]
                if len(parts) < 6:
                    continue
                if len(parts) >= 7:
                    try:
                        fires_sum += int(parts[6])
                    except ValueError:
                        print(
                            f"measure_v_trip_rate.WARN: malformed col 7 at {ledger_path}:{lineno}",
                            file=sys.stderr,
                        )
        except OSError as e:
            print(f"measure_v_trip_rate.WARN: cannot read {ledger_path}: {e}", file=sys.stderr)

        result[lname] = result.get(lname, 0) + fires_sum

    return result


def count_session_writes(session_files: list[Path]) -> int:
    """Estimate total Class B write attempts from session files (proxy: session count)."""
    return len(session_files)


def measure(
    project_root: Path,
    tasks: Optional[list[str]] = None,
    since: Optional[date] = None,
    until: Optional[date] = None,
    cost_ledger_override: Optional[Path] = None,
) -> list[dict]:
    """Collect metrics and return per-task result dicts."""
    session_map = collect_session_state_files(project_root, tasks=tasks, since=since, until=until)
    col7_map = collect_ledger_col7(project_root, tasks=tasks, cost_ledger_override=cost_ledger_override)

    # Union of all known task names
    all_tasks: set[str] = set(session_map.keys()) | set(col7_map.keys())
    if tasks:
        all_tasks &= set(tasks)

    results = []
    for task in sorted(all_tasks):
        files = session_map.get(task, [])
        s1_sum = sum(read_fallback_fires_from_session(f) for f in files)
        s2_sum = col7_map.get(task, 0)

        # Cross-check: warn if surfaces disagree by > 1
        if s2_sum > 0 and abs(s1_sum - s2_sum) > 1:
            print(
                f"measure_v_trip_rate.WARN: surface mismatch for task {task}: "
                f"session-state sum={s1_sum}, ledger col-7 sum={s2_sum}; investigate.",
                file=sys.stderr,
            )

        total_sessions = len(files)
        trip_rate = (s1_sum / total_sessions) if total_sessions > 0 else 0.0

        results.append(
            {
                "task": task,
                "sessions": total_sessions,
                "fallback_fires_after_stage4": s1_sum,
                "total_b_writes": total_sessions,  # proxy; each session = 1 Class B write
                "trip_rate": round(trip_rate, 4),
                "_surface2_col7_sum": s2_sum,  # informational
            }
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure V-04/V-05/V-06 trip rate from session-state and cost-ledger data."
    )
    parser.add_argument("--since", type=date.fromisoformat, help="Start date YYYY-MM-DD")
    parser.add_argument("--until", type=date.fromisoformat, help="End date YYYY-MM-DD")
    parser.add_argument("--tasks", type=lambda s: s.split(","), help="Comma-separated task names")
    parser.add_argument("--cost-ledger", type=Path, dest="cost_ledger", help="Override ledger path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    project_root = find_project_root()
    if not project_root:
        print("ERROR: .workflow_artifacts/ not found in current directory or parents.", file=sys.stderr)
        sys.exit(1)

    results = measure(
        project_root,
        tasks=args.tasks,
        since=args.since,
        until=args.until,
        cost_ledger_override=args.cost_ledger,
    )

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print("No session data found for the specified filters.")
            return
        print(f"V-trip-rate measurement — {date.today()}")
        print(f"{'Task':<40} {'Sessions':>8} {'Fires':>6} {'Rate':>8}")
        print("-" * 66)
        for r in results:
            print(
                f"{r['task']:<40} {r['sessions']:>8} {r['fallback_fires_after_stage4']:>6} {r['trip_rate']:>8.1%}"
            )
        print()
        print("NOTE: Pre-Stage-4 sessions always read as 0 fires (expected for baseline runs).")
        print("      BEFORE baseline uses manual hand-count from finalized critic-response/review artifacts.")


if __name__ == "__main__":
    main()
