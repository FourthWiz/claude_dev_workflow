#!/usr/bin/env python3
"""Shared fail-closed decision-gate guard (IVG-150).

A decision-gating skill that reaches a REQUIRED decision it cannot surface to a
human (Agent-tool subagent or headless `claude -p`, with no `[autonomous]`
pre-authorization) must NEVER treat "cannot ask" as "user approved." Its only
safe degrade is to FAIL CLOSED: hard-stop, record the pending decision durably,
and hand a structured signal back to the caller.

This helper performs BOTH fail-closed actions in one call via the `fail-closed`
subcommand:
  (a) writes a durable `needs-decision-{task}.md` sentinel under
      `.workflow_artifacts/memory/` (atomic write; survives the /end_of_task
      archive move because it lives OUTSIDE the task folder);
  (b) prints the structured `gate-result: NEEDS-DECISION` block to stdout for the
      skill to echo as its final message (the /run orchestrator routes it like a
      review-BLOCKED / gate-FAIL hard stop);
  (c) exits with code 3 — distinct from 0/1 so callers can branch on it.

DISTINCT FILENAME (R-03 / architecture Q-01): the sentinel is
`needs-decision-{task}.md`, NOT `autonomous-halt-{task}.md`. The live supervisor
(`src/quoin/supervisor.py:read_halt`) HALTs whenever `autonomous-halt-{task}.md`
merely EXISTS, so reusing that name would silently poison a later
`quoin run --autonomous {task}`. `needs-decision-*` is a same-CONTRACT sibling of
the halt family (memory/ location, atomic write, survives-archive, schema shape)
that the supervisor never reads.

Stdlib-only and core-pure: no import from `quoin/quoin/scripts/` (the adapter
layer) — the core-adapter import boundary (lesson 2026-06-15).
"""
from __future__ import annotations

import argparse
import datetime
import os
import sys
from pathlib import Path

# Sentinel filename template — DISTINCT from autonomous-halt-{task}.md by design.
SENTINEL_TEMPLATE = "needs-decision-{task}.md"
HALT_TEMPLATE = "autonomous-halt-{task}.md"  # for reference/assertions only; never written here

# The fixed trigger value recorded in every needs-decision sentinel.
TRIGGER = "non-interactive-decision-gate"

# Ordered schema field names (7 fields). Kept in lockstep with decision-gate-guard.md.
SENTINEL_FIELDS = (
    "task",
    "trigger",
    "skill",
    "site",
    "reason",
    "timestamp",
    "resume_hint",
)


def utc_timestamp() -> str:
    """Return the current time as a UTC ISO8601 string (seconds precision, Z-suffixed)."""
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _one_line(value: str) -> str:
    """Collapse any embedded newlines so a field can never break the 7-line schema."""
    return " ".join(value.splitlines()).strip()


def sentinel_path(task: str, memory_dir: Path) -> Path:
    """Return the absolute path of the needs-decision sentinel for ``task``."""
    return memory_dir / SENTINEL_TEMPLATE.format(task=task)


def render_sentinel(
    *, task: str, skill: str, site: str, reason: str, resume_hint: str, timestamp: str
) -> str:
    """Render the 7-line sentinel body."""
    values = {
        "task": task,
        "trigger": TRIGGER,
        "skill": skill,
        "site": site,
        "reason": _one_line(reason),
        "timestamp": timestamp,
        "resume_hint": _one_line(resume_hint),
    }
    return "".join(f"{field}: {values[field]}\n" for field in SENTINEL_FIELDS)


def write_sentinel(path: Path, body: str) -> None:
    """Atomically write ``body`` to ``path`` (write to a temp file, then os.replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def render_return_block(
    *, skill: str, site: str, task: str, sentinel_display: str, resume_hint: str
) -> str:
    """Render the machine-extractable NEEDS-DECISION block echoed to the caller."""
    return (
        "gate-result: NEEDS-DECISION\n"
        "needs-decision:\n"
        f"  skill: {skill}\n"
        f"  site: {site}\n"
        f"  task: {task}\n"
        f"  sentinel: {sentinel_display}\n"
        f"  resume_hint: {_one_line(resume_hint)}\n"
    )


def _display_path(path: Path, project_root: Path) -> str:
    """Return ``path`` relative to project_root when possible, else absolute."""
    try:
        return str(path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(path)


def cmd_fail_closed(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).resolve()
    memory_dir = (
        Path(args.memory_dir).resolve()
        if args.memory_dir
        else project_root / ".workflow_artifacts" / "memory"
    )
    path = sentinel_path(args.task, memory_dir)
    body = render_sentinel(
        task=args.task,
        skill=args.skill,
        site=args.site,
        reason=args.reason,
        resume_hint=args.resume_hint,
        timestamp=utc_timestamp(),
    )
    write_sentinel(path, body)
    block = render_return_block(
        skill=args.skill,
        site=args.site,
        task=args.task,
        sentinel_display=_display_path(path, project_root),
        resume_hint=args.resume_hint,
    )
    sys.stdout.write(block)
    return 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="decision_gate_guard.py",
        description="Fail-closed guard for decision-gating skills reached non-interactively.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    fc = sub.add_parser(
        "fail-closed",
        help="Write the needs-decision sentinel, emit the NEEDS-DECISION block, exit 3.",
    )
    fc.add_argument("--task", required=True, help="Task name (kebab-case).")
    fc.add_argument("--skill", required=True, help="Skill that hit the gate (e.g. end_of_task).")
    fc.add_argument("--site", required=True, help="Decision-site id (e.g. commit-decision).")
    fc.add_argument("--reason", required=True, help="One line: which decision, why unsurfaceable.")
    fc.add_argument("--resume-hint", required=True, dest="resume_hint", help="One line resume hint.")
    fc.add_argument(
        "--project-root",
        default=os.getcwd(),
        help="Project root (default: cwd). Sentinel default location is derived from it.",
    )
    fc.add_argument(
        "--memory-dir",
        default="",
        help="Override the memory dir (default: <project-root>/.workflow_artifacts/memory).",
    )
    fc.set_defaults(func=cmd_fail_closed)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
