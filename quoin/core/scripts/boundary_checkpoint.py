#!/usr/bin/env python3
"""boundary_checkpoint.py — Phase/task-boundary checkpoint writer (IVG-141).

Sibling of ``thorough_plan_checkpoint.py`` (IVG-98), which is left UNTOUCHED. This
writer is used by the ``/run``, ``/implement`` and ``/review`` boundary wirings to
save a durable, picker-selectable checkpoint when the on-demand context-budget
guard reports OVER budget, so resume is a single documented command.

``/thorough_plan`` does NOT use this writer — it reuses its own IVG-98
``thorough_plan_checkpoint.py`` (D-3). Hence the ``--skill`` enum is
``{run, implement, review}`` (thorough_plan excluded, review included).

Distinct filename prefix
------------------------
``checkpoints/boundary-progress-{skill}-{sid}.md`` — prefix ``boundary-progress-``
is DELIBERATELY distinct from ``thorough-plan-progress-`` so
``checkpoint_picker._classify_kind`` routes it as the generic ``/checkpoint`` kind
and ``/thorough_plan``'s §1b ``thorough-plan-progress-*.md`` glob never mis-picks
it (honors lessons 2026-07-24: a NEW sentinel/checkpoint must use a DISTINCT
filename; grep existing readers first).

Picker-selectable heading set
-----------------------------
Emits the FULL heading set ``checkpoint_picker`` consumes, each in the OWN-LINE
form ``## <Heading>\n<value>`` (heading alone on its line, value on the next
non-empty line). ``_extract_heading_value`` matches a line whose ``strip() ==
"## <Heading>"`` EXACTLY then returns the next non-empty line; the inline-colon
form ``## Heading: value`` yields "" and ``_collect_candidates`` DROPS the
candidate → restore silently broken. So we use the own-line form throughout.

Behaviour
---------
1. Resolve ``mem_dir = {project-root}/.workflow_artifacts/memory``;
   ``checkpoints_dir = mem_dir/checkpoints``; mkdir -p.
2. Write the checkpoint file atomically (.tmp + rename).
3. Write ``pending-restore-{sid}.txt`` sentinel LAST (first line = checkpoint
   path). SKIPPED when sid empty/``unknown`` (empty-SID orphan guard).
4. Print checkpoint path to stdout. Always exit 0 (fail-OPEN; call sites also
   ``|| true``).

Exit codes
----------
  0 — always (fail-OPEN design)
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path


VALID_SKILLS = ("run", "implement", "review")


def _atomic_write(path: Path, content: str) -> None:
    """Write content to path atomically via a .tmp sibling file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)


def _write_checkpoint(
    checkpoints_dir: Path,
    skill: str,
    sid: str,
    task: str,
    branch: str,
    phase_label: str,
    resume_command: str,
    plan_paths: list[str],
) -> Path:
    """Write (overwrite) the boundary checkpoint file with the FULL picker
    heading set. Fixed filename: ``boundary-progress-{skill}-{sid}.md``."""
    fname = f"boundary-progress-{skill}-{sid}.md"
    ckpt_path = checkpoints_dir / fname

    saved_ts = datetime.now(tz=timezone.utc).isoformat()

    # ## Last user intent MUST be present and non-empty (picker does not drop on
    # this, but continue_work / restore read it) — build a concrete re-entry string.
    last_user_intent = (
        f"{skill} {task}: over context budget at a phase boundary; boundary "
        f"checkpoint saved. Resume with: {resume_command}"
    )

    # ## In-flight artifacts: plan-path(s) + any provided paths (own-line list).
    if plan_paths:
        artifacts = "\n".join(f"- {p}" for p in plan_paths if p)
        if not artifacts:
            artifacts = "- (none provided)"
    else:
        artifacts = "- (none provided)"

    content = (
        f"## Active task\n{task}\n\n"
        f"## Session ID\n{sid}\n\n"
        f"## Current stage\n{phase_label}\n\n"
        f"## Status\nphase-boundary checkpoint\n\n"
        f"## Resume command\n{resume_command}\n\n"
        f"## Last user intent\n{last_user_intent}\n\n"
        f"## In-flight artifacts\n{artifacts}\n\n"
        f"## Saved\n{saved_ts}\n"
    )

    _atomic_write(ckpt_path, content)
    return ckpt_path


def _write_sentinel(mem_dir: Path, sid: str, ckpt_path: Path) -> None:
    """Write pending-restore-{sid}.txt sentinel (last, newer mtime).

    Skipped when sid is empty or ``unknown`` (empty-SID orphan guard) — a
    sentinel with no resolvable SID would poison future restore picks.
    """
    if not sid or sid == "unknown":
        print(
            "[boundary_checkpoint] WARNING: session UUID empty/unknown; "
            "refusing to write pending-restore sentinel (would create orphan). "
            "Checkpoint file kept; use /checkpoint --restore direct scan to resume.",
            file=sys.stderr,
        )
        return
    sentinel_path = mem_dir / f"pending-restore-{sid}.txt"
    _atomic_write(sentinel_path, str(ckpt_path) + "\n")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Always exits 0 (fail-OPEN)."""
    parser = argparse.ArgumentParser(
        description=(
            "Write a phase/task-boundary checkpoint for /run, /implement, /review "
            "(IVG-141). Always exits 0."
        ),
        add_help=True,
    )
    parser.add_argument("--project-root", required=True, metavar="PATH",
                        help="Absolute path to the project root.")
    parser.add_argument("--task", required=True, metavar="NAME",
                        help="Task name (kebab-case).")
    parser.add_argument("--skill", required=True, choices=list(VALID_SKILLS),
                        help="Boundary skill: run, implement, or review "
                             "(thorough_plan excluded — it reuses its IVG-98 writer).")
    parser.add_argument("--sid", default="unknown", metavar="UUID",
                        help="Session UUID (may be 'unknown' or empty).")
    parser.add_argument("--branch", default="unknown", metavar="NAME",
                        help="Current git branch name.")
    parser.add_argument("--resume-command", default="", metavar="CMD",
                        dest="resume_command",
                        help="Single documented resume command (e.g. '/run --resume <task>').")
    parser.add_argument("--phase-label", default="", metavar="LABEL",
                        dest="phase_label",
                        help="Human-readable boundary label → ## Current stage.")
    parser.add_argument("--plan-path", default=None, metavar="PATH",
                        dest="plan_path", action="append",
                        help="In-flight artifact path (repeatable).")

    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # Even on arg-parse errors, exit 0 (fail-OPEN)
        return 0

    try:
        # Normalise SID: treat empty string as "unknown".
        sid = args.sid.strip() if args.sid else "unknown"
        task = args.task.strip() if args.task else ""
        phase_label = args.phase_label.strip() or f"{args.skill} phase boundary"
        resume_command = args.resume_command.strip() or f"re-invoke /{args.skill}"

        # 1. Resolve memory dir + checkpoints subdir.
        mem_dir = Path(args.project_root) / ".workflow_artifacts" / "memory"
        checkpoints_dir = mem_dir / "checkpoints"
        checkpoints_dir.mkdir(parents=True, exist_ok=True)

        # 2. Write checkpoint file (picker-selectable heading set).
        ckpt_path = _write_checkpoint(
            checkpoints_dir=checkpoints_dir,
            skill=args.skill,
            sid=sid,
            task=task,
            branch=args.branch,
            phase_label=phase_label,
            resume_command=resume_command,
            plan_paths=args.plan_path or [],
        )

        # 3. Write pending-restore sentinel LAST (skipped for empty/unknown SID).
        _write_sentinel(mem_dir, sid, ckpt_path)

        # 4. Print checkpoint path to stdout.
        print(str(ckpt_path))

    except Exception as exc:  # noqa: BLE001
        print(
            f"[boundary_checkpoint] WARNING: unexpected error: {exc}; "
            "checkpoint skipped (fail-OPEN).",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
