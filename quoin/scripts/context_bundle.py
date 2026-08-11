#!/usr/bin/env python3
"""context_bundle.py — context bundle helper for orchestrator spawn-prompt construction (IVG-164 stage 2 T-02).

Emits bundle lines for configured artifact members to stdout so orchestrator
SKILL.md spawn-prompt construction blocks can wrap them in a [quoin-bundle] block.

Per-member extraction rules (D-06):
  - architecture.md   → path + ## For human block verbatim
  - current-plan.md   → path + ## For human block when present, else path-only
  - spec.md           → ALWAYS path-only (Class A — no ## For human block by contract)

Named unit cases:
  - Missing block (v2 plan, no ## For human) → explicit path-only entry
  - Fast-route stub (provenance marker present) → same extraction; block absent → path-only

CLI:
  context_bundle.py --task <name> --stage <N> [--project-root <path>] [--wrap]

Output format (D-03): one member per line: <absolute-path> | <summary-excerpt>
  where summary-excerpt is the first line of the ## For human block,
  or the literal string "summary: absent (path-only)".

With --wrap: output wrapped in [quoin-bundle] / [/quoin-bundle] markers.
Without --wrap: raw member lines (caller adds markers via shell wrapper per D-04a).

Degradation-safe: exit 0 on all errors; empty output → caller's || true catches it.
"""

import argparse
import sys
from pathlib import Path


def resolve_project_root() -> Path:
    """Walk up from cwd to find nearest ancestor containing .workflow_artifacts/."""
    cwd = Path.cwd().resolve()
    for ancestor in [cwd, *cwd.parents]:
        if (ancestor / ".workflow_artifacts").is_dir():
            return ancestor
    return cwd


def extract_for_human_block(filepath: Path) -> str | None:
    """Extract the ## For human block text from a v3-format artifact.

    Returns the block body (text between ## For human and the next ## heading),
    or None if the block is absent.
    """
    if not filepath.exists():
        return None
    content = filepath.read_text()
    in_block = False
    lines_out = []
    for line in content.splitlines():
        if line.startswith("## For human"):
            in_block = True
            continue
        if in_block:
            if line.startswith("## "):
                break
            lines_out.append(line)
    if not lines_out:
        return None
    body = "\n".join(lines_out).strip()
    return body if body else None


def is_class_a_artifact(filepath: Path) -> bool:
    """Check if an artifact is Class A (no ## For human block by contract).

    Currently: spec.md is the only Class A artifact.
    """
    return filepath.name == "spec.md"


def build_bundle_lines(task_name: str, stage: str | None, project_root: Path) -> list[str]:
    """Build bundle member lines for the given task and stage.

    Returns a list of strings, each "<path> | <summary-excerpt>".
    """
    wf = project_root / ".workflow_artifacts" / task_name
    stage_dir = wf / f"stage-{stage}" if stage else wf

    members: list[tuple[Path, bool]] = [
        (wf / "architecture.md", False),
        (stage_dir / "current-plan.md", False),
        (wf / "spec.md", True),
    ]

    lines: list[str] = []
    for filepath, is_class_a in members:
        if is_class_a or is_class_a_artifact(filepath):
            lines.append(f"{filepath} | summary: absent (path-only)")
            continue

        summary = extract_for_human_block(filepath)
        if summary is None:
            lines.append(f"{filepath} | summary: absent (path-only)")
        else:
            first_line = summary.split("\n")[0].strip()
            lines.append(f"{filepath} | {first_line}")

    return lines


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Emit context bundle lines for orchestrator spawn-prompt construction"
    )
    parser.add_argument("--task", required=True, help="Task name (kebab-case)")
    parser.add_argument("--stage", type=int, default=None, help="Stage number (optional)")
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root path (default: auto-resolve from cwd)",
    )
    parser.add_argument(
        "--wrap",
        action="store_true",
        help="Wrap output in [quoin-bundle] / [/quoin-bundle] markers",
    )
    args = parser.parse_args()

    try:
        project_root = Path(args.project_root) if args.project_root else resolve_project_root()
    except Exception:
        return

    try:
        lines = build_bundle_lines(args.task, args.stage, project_root)
        if args.wrap:
            print("[quoin-bundle]")
        for line in lines:
            print(line)
        if args.wrap:
            print("[/quoin-bundle]")
    except Exception:
        return


if __name__ == "__main__":
    main()
