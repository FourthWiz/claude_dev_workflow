"""dispatch_sidecar.py — Write the dispatch hint sidecar JSON for WorktreeCreate hook.

Called by source-mutating cheap-tier skills (/implement, /rollback, /end_of_task)
BEFORE invoking the Agent tool with isolation: "worktree". The WorktreeCreate hook
reads this sidecar to determine which nested git root to use for worktree isolation.

Sidecar path: <project_root>/.workflow_artifacts/.dispatch-hint.json
The file is overwritten on each call (single-shot, consumed by the hook).

Exit codes:
  0  — sidecar written successfully
  1  — missing required argument (--skill or --project-root)
  2  — write failure (e.g., permission error)

CLI:
  python3 dispatch_sidecar.py \\
      --skill SKILL_NAME \\
      --project-root ABS_PATH \\
      [--plan PATH_TO_PLAN] \\
      [--session-id ID]

  If --session-id is omitted, reads from $CLAUDE_CODE_SESSION_ID env var.
  If $CLAUDE_CODE_SESSION_ID is also unset, session_id is written as null.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


_SIDECAR_FILENAME = ".dispatch-hint.json"
_WORKFLOW_DIR = ".workflow_artifacts"


def write_sidecar(
    skill_name: str,
    project_root: Path,
    plan_path: str | None = None,
    session_id: str | None = None,
) -> int:
    """Write the dispatch hint sidecar to <project_root>/.workflow_artifacts/.dispatch-hint.json.

    Returns 0 on success, 2 on write failure.
    """
    sidecar_dir = project_root / _WORKFLOW_DIR
    try:
        sidecar_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(
            f"dispatch_sidecar: cannot create directory {sidecar_dir}: {e}",
            file=sys.stderr,
        )
        return 2

    sidecar_path = sidecar_dir / _SIDECAR_FILENAME
    payload = {
        "skill_name": skill_name,
        "project_root": str(project_root.resolve()),
        "plan_path": plan_path,
        "session_id": session_id,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        sidecar_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as e:
        print(
            f"dispatch_sidecar: cannot write sidecar to {sidecar_path}: {e}",
            file=sys.stderr,
        )
        return 2

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write the dispatch hint sidecar for the WorktreeCreate hook.",
    )
    parser.add_argument("--skill", required=True, metavar="NAME", help="Skill name (e.g. implement)")
    parser.add_argument(
        "--project-root",
        required=True,
        metavar="PATH",
        help="Absolute path to the project root",
    )
    parser.add_argument(
        "--plan",
        metavar="PATH",
        default=None,
        help="Path to the current plan file (optional)",
    )
    parser.add_argument(
        "--session-id",
        metavar="ID",
        default=None,
        help=(
            "Session ID (optional; falls back to $CLAUDE_CODE_SESSION_ID; "
            "null if both absent — degraded mode, hook still works)"
        ),
    )

    args = parser.parse_args()

    # Validate required args (argparse already requires --skill and --project-root,
    # but check project-root is non-empty)
    if not args.skill.strip():
        print("dispatch_sidecar: --skill must be non-empty", file=sys.stderr)
        return 1

    project_root = Path(args.project_root)

    # Resolve session_id: CLI arg → env var → None (degraded mode)
    session_id: str | None = args.session_id
    if session_id is None:
        session_id = os.environ.get("CLAUDE_CODE_SESSION_ID") or None

    return write_sidecar(
        skill_name=args.skill,
        project_root=project_root,
        plan_path=args.plan,
        session_id=session_id,
    )


if __name__ == "__main__":
    sys.exit(main())
