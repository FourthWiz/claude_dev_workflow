"""Validate a repo-local Codex session handoff artifact.

This is a deterministic repository check, not live Codex runtime automation.
It validates the markdown shape documented in quoin/adapters/codex/handoff.md.

Usage:
    python3 quoin/adapters/codex/validate_codex_handoff.py --self-test
    python3 quoin/adapters/codex/validate_codex_handoff.py --project-root . --file .workflow_artifacts/memory/sessions/2026-05-13-example-codex.md
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
FIXTURE_PATH = SCRIPT_DIR / "fixtures" / "valid-handoff.md"

REQUIRED_SECTIONS = [
    "Metadata",
    "Status",
    "Current stage",
    "Completed in this session",
    "Unfinished work",
    "Decisions made",
    "Finalized artifacts",
    "Continuation context",
    "Lessons learned candidates",
    "Cost",
]

REQUIRED_METADATA = {
    "runtime",
    "handoff_version",
    "task",
    "task_path",
    "artifact_root",
    "session_date",
    "last_phase",
    "end_of_day_due",
}

ALLOWED_STATUS = {"in_progress", "completed", "blocked"}
ALLOWED_LAST_PHASE = {
    "discover",
    "plan",
    "implement",
    "review",
    "gate",
    "handoff",
    "end_of_day",
    "end_of_task",
    "other",
}
ALLOWED_END_OF_DAY_DUE = {"yes", "no"}
ALLOWED_COST_RECORDED = {"yes", "no", "not-available"}

FORBIDDEN_PATTERNS = [
    "~/." + "claude",
    "$HOME/." + "claude",
    "." + "claude/",
    "~/." + "codex",
    "$HOME/." + "codex",
    "/usr/local/" + "codex",
    "/opt/" + "codex",
    "." + "codex/commands",
]


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str]


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _parse_sections(text: str) -> Dict[str, str]:
    sections: Dict[str, List[str]] = {}
    current: str | None = None

    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*:?\s*$", line)
        if match:
            current = match.group(1).strip().rstrip(":")
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line)

    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def _parse_bullets(section: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for line in section.splitlines():
        match = re.match(r"^\s*-\s+([A-Za-z0-9_-]+):\s*(.+?)\s*$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values


def _has_real_content(section: str) -> bool:
    stripped = section.strip()
    if not stripped:
        return False
    placeholders = {"<none>", "<todo>", "todo", "tbd", "..."}
    return stripped.lower() not in placeholders and "<" not in stripped


def _paths_in_section(section: str) -> List[str]:
    paths: List[str] = []
    for match in re.finditer(r"(?<![\w/.-])(\.workflow_artifacts/[^\s,)]+)", section):
        paths.append(match.group(1).rstrip(".,;:"))
    return paths


def validate_handoff(project_root: Path, handoff_file: Path) -> ValidationResult:
    errors: List[str] = []
    project_root = project_root.resolve()
    handoff_file = handoff_file.resolve()
    sessions_dir = project_root / ".workflow_artifacts" / "memory" / "sessions"

    if not handoff_file.is_file():
        return ValidationResult(False, [f"handoff file does not exist: {handoff_file}"])

    if not _is_relative_to(handoff_file, sessions_dir):
        errors.append(
            "handoff file must live under project-root .workflow_artifacts/memory/sessions/"
        )

    text = handoff_file.read_text(encoding="utf-8")
    for pattern in FORBIDDEN_PATTERNS:
        if pattern in text:
            errors.append(f"handoff contains unsupported runtime path pattern {pattern!r}")

    if not re.search(r"^#\s+Codex Session Handoff:", text, re.MULTILINE):
        errors.append("missing H1 '# Codex Session Handoff: <task-name>'")

    sections = _parse_sections(text)
    for section in REQUIRED_SECTIONS:
        body = sections.get(section)
        if body is None:
            errors.append(f"missing required section: ## {section}")
        elif not _has_real_content(body):
            errors.append(f"section has no concrete content: ## {section}")

    metadata = _parse_bullets(sections.get("Metadata", ""))
    missing_metadata = sorted(REQUIRED_METADATA - metadata.keys())
    if missing_metadata:
        errors.append(f"metadata missing required keys: {missing_metadata}")

    if metadata.get("runtime") != "codex":
        errors.append("metadata runtime must be 'codex'")
    if metadata.get("handoff_version") != "1":
        errors.append("metadata handoff_version must be '1'")
    if metadata.get("artifact_root") != ".workflow_artifacts/":
        errors.append("metadata artifact_root must be '.workflow_artifacts/'")
    if metadata.get("task_path", "").startswith(".workflow_artifacts/") is False:
        errors.append("metadata task_path must be repo-relative under .workflow_artifacts/")
    if metadata.get("task_path") == ".workflow_artifacts/memory/":
        errors.append("metadata task_path must identify a task path, not memory/")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", metadata.get("session_date", "")):
        errors.append("metadata session_date must use YYYY-MM-DD")
    if metadata.get("last_phase") not in ALLOWED_LAST_PHASE:
        errors.append(f"metadata last_phase must be one of {sorted(ALLOWED_LAST_PHASE)}")
    if metadata.get("end_of_day_due") not in ALLOWED_END_OF_DAY_DUE:
        errors.append("metadata end_of_day_due must be 'yes' or 'no'")

    status = sections.get("Status", "").strip()
    if status and status not in ALLOWED_STATUS:
        errors.append(f"Status must be one of {sorted(ALLOWED_STATUS)}")

    continuation = sections.get("Continuation context", "")
    for token in ["Next step:", "Resume from:", "Open risks:", "Checks run:"]:
        if token not in continuation:
            errors.append(f"Continuation context missing '{token}'")

    finalized = sections.get("Finalized artifacts", "")
    if finalized and "None" not in finalized:
        finalized_paths = _paths_in_section(finalized)
        if not finalized_paths:
            errors.append(
                "Finalized artifacts must list .workflow_artifacts/ paths or 'None'"
            )
        for path in finalized_paths:
            if not path.startswith(".workflow_artifacts/"):
                errors.append(f"Finalized artifact path is not repo-local: {path}")

    cost = _parse_bullets(sections.get("Cost", ""))
    for key in ["cost_ledger", "recorded", "fallback_fires"]:
        if key not in cost:
            errors.append(f"Cost section missing '{key}'")
    if "cost_ledger" in cost and not cost["cost_ledger"].startswith(".workflow_artifacts/"):
        errors.append("Cost cost_ledger must be repo-relative under .workflow_artifacts/")
    if cost.get("recorded") not in ALLOWED_COST_RECORDED:
        errors.append(f"Cost recorded must be one of {sorted(ALLOWED_COST_RECORDED)}")
    if "fallback_fires" in cost and not re.fullmatch(r"\d+", cost["fallback_fires"]):
        errors.append("Cost fallback_fires must be an integer")

    return ValidationResult(not errors, errors)


def run_self_test() -> ValidationResult:
    if not FIXTURE_PATH.is_file():
        return ValidationResult(False, [f"missing fixture: {FIXTURE_PATH}"])

    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        handoff_file = (
            project_root
            / ".workflow_artifacts"
            / "memory"
            / "sessions"
            / "2026-05-13-phase-34-codex.md"
        )
        handoff_file.parent.mkdir(parents=True, exist_ok=True)
        handoff_file.write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        return validate_handoff(project_root, handoff_file)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root containing AGENTS.md; defaults to the current directory.",
    )
    parser.add_argument(
        "--file",
        help="Handoff file to validate. Relative paths are resolved from project root.",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Validate the bundled fixture by copying it into a temporary project root.",
    )
    args = parser.parse_args()

    if args.self_test:
        result = run_self_test()
        if result.ok:
            print("HANDOFF PASS: bundled fixture")
            return 0
        print("HANDOFF FAIL: bundled fixture", file=sys.stderr)
        for error in result.errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    if not args.file:
        parser.error("--file is required unless --self-test is used")

    project_root = Path(args.project_root).resolve()
    handoff_file = Path(args.file)
    if not handoff_file.is_absolute():
        handoff_file = project_root / handoff_file

    result = validate_handoff(project_root, handoff_file)
    if result.ok:
        print(f"HANDOFF PASS: {_rel(handoff_file, project_root)}")
        return 0

    print(f"HANDOFF FAIL: {_rel(handoff_file, project_root)}", file=sys.stderr)
    for error in result.errors:
        print(f"- {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
