"""path_resolve.py — Stage-subfolder path resolver for multi-stage workflow tasks.

Public API: task_path(task_name, stage=None, project_root=None) -> Path
Rules: Rule 1: int >= 1 → stage-N/; Rule 2: str → decomp lookup; Rule 3: None → task root.
See CLAUDE.md "Multi-stage tasks" for the full convention.
"""

import re
import sys
import argparse
from pathlib import Path


# Module-level regexes (T-04 case (o) introspects imports via AST)

SECTION_RE = re.compile(r"^## Stage decomposition\s*$", re.MULTILINE)
NEXT_H2_RE = re.compile(r"^## ", re.MULTILINE)
ROW_RE = re.compile(
    r"^[0-9]+\.\s+(?:[✅✓✗⏳⛔⚠️\s])*S-([0-9]+):\s*(.+?)\s*$",
    re.MULTILINE,
)


def _lookup_stage_by_name(arch_text: str, name: str):
    """Return stage number for the given name, or None if not found.

    Raises ValueError if name matches 2+ stages (round-2 MAJ-6 / D-04).
    """
    m = SECTION_RE.search(arch_text)
    if not m:
        return None
    section_start = m.end()
    next_h2 = NEXT_H2_RE.search(arch_text, section_start)
    section_end = next_h2.start() if next_h2 else len(arch_text)
    section_body = arch_text[section_start:section_end]

    # Normalize caller's name: hyphens/underscores → spaces, collapse whitespace,
    # lower-case (D-04 substring-match with normalization).
    name_lower = name.lower().strip()
    norm_name = re.sub(r"[-_]", " ", name_lower)
    norm_name = re.sub(r"\s+", " ", norm_name).strip()

    matches = []  # list of (stage_n, original_desc)
    for row_match in ROW_RE.finditer(section_body):
        stage_n = int(row_match.group(1))
        desc = row_match.group(2)
        norm_desc = re.sub(r"[-_]", " ", desc.lower())
        norm_desc = re.sub(r"\s+", " ", norm_desc).strip()
        if norm_name in norm_desc:
            matches.append((stage_n, desc.strip()))

    if len(matches) == 0:
        return None
    if len(matches) == 1:
        return matches[0][0]

    # Multi-match — raise per round-2 MAJ-6 / D-04
    listed = "; ".join(f"S-{n:02d}: {d}" for n, d in matches)
    raise ValueError(
        f"path_resolve: stage name '{name}' matches {len(matches)} stages: {listed} "
        f"— disambiguate by using --stage <integer>"
    )


def task_path(task_name, stage=None, project_root=None) -> Path:
    """Resolve the artifact directory for a workflow task.

    Returns absolute Path; caller does mkdir if needed.
    Raises ValueError on rule-1 int < 1, rule-2 missing arch/stage-name issues,
    rule-2d invalid task_name.
    """
    # Defensive: task_name must be a non-empty string (rule-2d)
    if not task_name or not isinstance(task_name, str) or not task_name.strip():
        raise ValueError("path_resolve: task_name must be a non-empty string")

    project_root = Path(project_root or Path.cwd()).resolve()
    base = project_root / ".workflow_artifacts" / task_name

    # Rule 1: explicit integer stage
    if isinstance(stage, int):
        if stage < 1:
            raise ValueError(
                f"path_resolve: stage int must be >= 1, got {stage}"
            )
        return base / f"stage-{stage}"

    # Rule 2: stage name lookup via architecture.md ## Stage decomposition
    if isinstance(stage, str):
        arch = base / "architecture.md"
        if not arch.exists():
            raise ValueError(
                f"path_resolve: ambiguous stage '{stage}' — "
                f"architecture.md missing at {arch}"
            )
        arch_text = arch.read_text(encoding="utf-8")
        n = _lookup_stage_by_name(arch_text, stage)
        if n is None:
            raise ValueError(
                f"path_resolve: ambiguous stage '{stage}' — "
                f"not found in architecture.md ## Stage decomposition"
            )
        return base / f"stage-{n}"

    # Rule 3 (stage is None): default — task root.
    # Per architecture I-05 + R-09: do NOT auto-route to stage-N/ even if such a
    # subfolder exists on disk. Multi-stage routing is OPT-IN via explicit stage=
    # argument. Existing in-flight tasks with mixed shapes stay on root-level paths
    # until their next /thorough_plan invocation explicitly passes stage=N.
    return base


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="path_resolve.py",
        description="Resolve the artifact directory path for a workflow task.",
    )
    parser.add_argument(
        "--task",
        required=True,
        metavar="TASK_NAME",
        help="Kebab-case task identifier (e.g., quoin-foundation)",
    )
    parser.add_argument(
        "--stage",
        default=None,
        metavar="N_OR_NAME",
        help=(
            "Stage specifier: integer (e.g., 3) or descriptive name "
            "(e.g., model-dispatch). Omit for legacy/default-root tasks."
        ),
    )
    parser.add_argument(
        "--project-root",
        default=None,
        metavar="PATH",
        help="Project root directory (default: cwd)",
    )
    return parser


def _parse_stage_arg(raw: str):
    """Convert raw --stage CLI string to int or str."""
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return raw  # treat as stage name string


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    stage = _parse_stage_arg(args.stage)

    try:
        result = task_path(
            task_name=args.task,
            stage=stage,
            project_root=args.project_root,
        )
        print(str(result))
        sys.exit(0)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
