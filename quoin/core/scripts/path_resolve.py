"""path_resolve.py — Stage-subfolder path resolver for multi-stage workflow tasks.

Public API: task_path(task_name, stage=None, project_root=None) -> Path
Rules: Rule 1: int >= 1 → stage-N/; Rule 2: str → decomp lookup; Rule 3: None → task root.
See CLAUDE.md "Multi-stage tasks" for the full convention.

Exit codes (CLI only):
  0 — success
  2 — ValueError (bad task name, stage not found, ambiguous match)
  3 — nested root detected (--verify-root flag only)
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path


# Module-level regexes (T-04 case (o) introspects imports via AST)

SECTION_RE = re.compile(r"^## Stage decomposition\s*$", re.MULTILINE)
NEXT_H2_RE = re.compile(r"^## ", re.MULTILINE)
ROW_RE = re.compile(
    r"^[0-9]+\.\s+(?:[✅✓✗⏳⛔⚠️\s])*S-([0-9]+):\s*(.+?)\s*$",
    re.MULTILINE,
)

# IVG-158 S-02: marker-aware artifact-root resolution (D-02). Both stdlib
# additions (os, json) — see test_module_imports_stdlib_only allowlist widening.
_WORKSPACE_MARKER = ".quoin-workspace.json"
_ENV_ARTIFACT_ROOT = "QUOIN_ARTIFACT_ROOT"


def _find_nested_ancestor(project_root: Path):
    """Return nearest ancestor of project_root containing .workflow_artifacts/, else None."""
    cur = project_root.parent
    while cur != cur.parent:
        if (cur / ".workflow_artifacts").is_dir():
            return cur
        cur = cur.parent
    return None


def _find_self_or_ancestor_root(start: Path) -> Path:
    """Return the nearest self-or-ancestor dir containing .workflow_artifacts/.

    Self-inclusive walk-up: starts AT `start` (unlike _find_nested_ancestor, which
    starts at start.parent). Mirrors dispatch_config.find_project_root semantics.
    Falls back to `start` itself when no .workflow_artifacts/ ancestor is found, so
    callers always receive a usable path.
    """
    start = Path(start).resolve()
    cur = start
    while True:
        if (cur / ".workflow_artifacts").is_dir():
            return cur
        if cur == cur.parent:
            return start
        cur = cur.parent


def _valid_artifact_root(candidate) -> bool:
    """True iff candidate is a dir containing .workflow_artifacts/. Fail-OPEN."""
    try:
        return (Path(candidate) / ".workflow_artifacts").is_dir()
    except (OSError, TypeError):
        return False


def _marker_artifact_root(marker_path: Path):
    """Read + parse a .quoin-workspace.json marker; return its artifact_root as a
    resolved Path, or None on any missing key / invalid root / parse error
    (fail-OPEN — a corrupt or non-.workflow_artifacts marker is ignored, never fatal).
    """
    try:
        data = json.loads(marker_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            # Valid JSON that is not an object (list / number / string / null)
            # has no .get(...) — treat as an absent/invalid marker and fall
            # through, exactly like the corrupt-marker path (fail-OPEN).
            return None
        ar = data.get("artifact_root")
    except (OSError, ValueError, TypeError):
        return None
    if ar and _valid_artifact_root(ar):
        return Path(ar).resolve()
    return None


def resolve_artifact_root(start=None) -> Path:
    """Marker-aware, env-aware artifact-root resolution (IVG-158 S-02, D-02).

    Precedence: QUOIN_ARTIFACT_ROOT env override (if valid) > nearest
    .quoin-workspace.json marker's artifact_root (if valid) > the existing
    .workflow_artifacts/ walk-up (byte-identical to _find_self_or_ancestor_root
    when no marker/env is present — see test_resolve_artifact_root_byte_identity_no_marker).
    """
    start = Path(start or Path.cwd()).resolve()

    env = os.environ.get(_ENV_ARTIFACT_ROOT)
    if env and _valid_artifact_root(env):
        return Path(env).resolve()

    cur = start
    while True:
        marker = cur / _WORKSPACE_MARKER
        if marker.is_file():
            ar = _marker_artifact_root(marker)
            if ar is not None:
                return ar
        if (cur / ".workflow_artifacts").is_dir():
            return cur
        if cur == cur.parent:
            return start
        cur = cur.parent


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
        required=False,
        default=None,
        metavar="TASK_NAME",
        help="Kebab-case task identifier (e.g., quoin-foundation)",
    )
    parser.add_argument(
        "--print-project-root",
        action="store_true",
        default=False,
        help=(
            "Print the nearest self-or-ancestor project root (dir containing "
            ".workflow_artifacts/) for --start (default cwd) and exit 0. Mutually "
            "exclusive with --task."
        ),
    )
    parser.add_argument(
        "--start",
        default=None,
        metavar="PATH",
        help="Start directory for --print-project-root walk-up (default: cwd).",
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
    parser.add_argument(
        "--verify-root",
        action="store_true",
        default=False,
        help=(
            "Exit 3 if the given --project-root is nested inside an ancestor "
            ".workflow_artifacts/ tree. Prints offending ancestor path to stderr."
        ),
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

    # --print-project-root is handled FIRST, before any --task requirement, so it
    # never argparse-fails to empty stdout (MAJ-1). stdout is always a single clean
    # path line; the nested-root advisory goes to stderr only.
    if args.print_project_root:
        start = Path(args.start or Path.cwd()).resolve()
        root = resolve_artifact_root(start)
        print(str(root))
        ancestor = _find_nested_ancestor(root)
        if ancestor is not None:
            print(
                f"path_resolve: WARN — project root '{root}' is itself nested inside "
                f"ancestor '{ancestor}' that also contains .workflow_artifacts/.",
                file=sys.stderr,
            )
        sys.exit(0)

    # Exactly one of --task / --print-project-root is required.
    if not args.task:
        print(
            "path_resolve: exactly one of --task or --print-project-root is required",
            file=sys.stderr,
        )
        sys.exit(2)

    stage = _parse_stage_arg(args.stage)
    project_root = Path(args.project_root or Path.cwd()).resolve()

    try:
        result = task_path(
            task_name=args.task,
            stage=stage,
            project_root=project_root,
        )
        print(str(result))
        if args.verify_root:
            ancestor = _find_nested_ancestor(project_root)
            if ancestor is not None:
                print(
                    f"path_resolve: nested .workflow_artifacts/ detected — "
                    f"ancestor '{ancestor}' also contains .workflow_artifacts/. "
                    f"Use the ancestor as project root.",
                    file=sys.stderr,
                )
                sys.exit(3)
        sys.exit(0)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
