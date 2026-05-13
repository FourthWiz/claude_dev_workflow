"""Smoke-test the repo-local Codex workflow path for Quoin.

This is a deterministic repository check, not a live Codex runtime test. It
verifies the files, links, and runtime assumptions Codex needs to follow a
minimal Quoin workflow from repo-local setup docs to portable core artifacts.

Usage:
    python3 quoin/adapters/codex/smoke_codex_workflow.py --project-root .
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


SCRIPT_DIR = Path(__file__).resolve().parent
QUOIN_PKG_DIR = SCRIPT_DIR.parent.parent
REPO_ROOT = QUOIN_PKG_DIR.parent

SMOKE_SKILLS = ["architect", "plan", "review"]

CODEX_PATH_FILES = [
    "AGENTS.md",
    "quoin/adapters/codex/README.md",
    "quoin/adapters/codex/setup.md",
    "quoin/adapters/codex/installable-feature.md",
    "quoin/adapters/codex/feature-manifest.json",
    "quoin/adapters/codex/skills/README.md",
    "quoin/adapters/codex/unsupported-claude-behavior.md",
]

FORBIDDEN_CLAUDE_RUNTIME_PATTERNS = [
    "~/." + "claude",
    "$HOME/." + "claude",
    "." + "claude/",
]

FORBIDDEN_CODEX_GLOBAL_PATTERNS = [
    "~/." + "codex",
    "$HOME/." + "codex",
    "/usr/local/" + "codex",
    "/opt/" + "codex",
    "." + "codex/commands",
    "npm install" + " -g " + "codex",
]

FORBIDDEN_REQUIRED_DEPENDENCY_PATTERNS = [
    re.compile(r"\brequires?\s+ccusage\b", re.IGNORECASE),
    re.compile(r"\bdepends?\s+on\s+ccusage\b", re.IGNORECASE),
    re.compile(r"\binstall\s+ccusage\b", re.IGNORECASE),
]

FORBIDDEN_CLAUDE_INSTALL_ROUTING_PATTERNS = [
    re.compile(
        r"\b(use|run|invoke|execute)\s+(bash\s+)?quoin/install\.sh\b",
        re.IGNORECASE,
    ),
]

FORBIDDEN_SLASH_COMMAND_REQUIREMENT_PATTERNS = [
    re.compile(
        r"\b(use|run|invoke|call|execute|require|required)\s+/"
        r"(architect|plan|review|implement|gate|run|end_of_task|critic|revise)\b",
        re.IGNORECASE,
    ),
]


@dataclass
class SmokeResult:
    name: str
    ok: bool
    detail: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _missing(paths: Iterable[Path]) -> List[str]:
    return [_rel(path) for path in paths if not path.is_file()]


def _codex_smoke_files(project_root: Path) -> List[Path]:
    files = [project_root / rel for rel in CODEX_PATH_FILES]
    for skill in SMOKE_SKILLS:
        files.append(SCRIPT_DIR / "skills" / skill / "README.md")
    return files


def check_required_files(project_root: Path) -> SmokeResult:
    required = _codex_smoke_files(project_root) + [
        QUOIN_PKG_DIR / "core" / "workflow" / "rules.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "task-layout.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "session-state.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "cost-ledger.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "skills.json",
    ]
    for skill in SMOKE_SKILLS:
        required.append(QUOIN_PKG_DIR / "core" / "skills" / f"{skill}.md")

    missing = _missing(required)
    if missing:
        return SmokeResult("required-files", False, f"missing files: {missing}")
    return SmokeResult("required-files", True, "Codex smoke path files are present")


def check_setup_to_core_path(project_root: Path) -> SmokeResult:
    agents = _read(project_root / "AGENTS.md")
    setup = _read(SCRIPT_DIR / "setup.md")
    adapter = _read(SCRIPT_DIR / "README.md")
    skill_index = _read(SCRIPT_DIR / "skills" / "README.md")
    task_layout = _read(QUOIN_PKG_DIR / "core" / "workflow" / "task-layout.md")
    rules = _read(QUOIN_PKG_DIR / "core" / "workflow" / "rules.md")
    skills_data = json.loads(_read(QUOIN_PKG_DIR / "core" / "workflow" / "skills.json"))
    skill_names = {skill["name"] for skill in skills_data.get("skills", [])}

    requirements = {
        "AGENTS.md pins workflow artifacts": ".workflow_artifacts/" in agents,
        "AGENTS.md references portable skill metadata": "quoin/core/workflow/skills.json" in agents,
        "setup.md names AGENTS.md": "AGENTS.md" in setup,
        "setup.md references portable workflow docs": "quoin/core/workflow/" in setup,
        "adapter README references skill docs": "quoin/adapters/codex/skills/" in adapter,
        "skill index links plan adapter": "(plan/README.md)" in skill_index,
        "task layout documents stage folders": "stage-N/" in task_layout,
        "rules document runtime adapter ownership": "Runtime adapters own" in rules,
    }

    for skill in SMOKE_SKILLS:
        adapter_doc = _read(SCRIPT_DIR / "skills" / skill / "README.md")
        core_doc = _read(QUOIN_PKG_DIR / "core" / "skills" / f"{skill}.md")
        requirements[f"manifest includes {skill}"] = skill in skill_names
        requirements[f"{skill} adapter links core doc"] = f"quoin/core/skills/{skill}.md" in adapter_doc
        requirements[f"{skill} core doc uses workflow artifacts"] = ".workflow_artifacts/" in core_doc

    missing = [name for name, ok in requirements.items() if not ok]
    if missing:
        return SmokeResult("setup-to-core-path", False, f"failed requirements: {missing}")
    return SmokeResult(
        "setup-to-core-path",
        True,
        "AGENTS.md -> Codex adapter docs -> core skill docs -> workflow docs path is coherent",
    )


def check_minimal_workflow_artifacts() -> SmokeResult:
    task_layout = _read(QUOIN_PKG_DIR / "core" / "workflow" / "task-layout.md")
    core_docs = "\n".join(
        _read(QUOIN_PKG_DIR / "core" / "skills" / f"{skill}.md")
        for skill in SMOKE_SKILLS
    )
    required_artifacts = [
        ".workflow_artifacts/",
        "architecture.md",
        "current-plan.md",
        "review-1.md",
        "cost-ledger.md",
    ]
    combined = task_layout + "\n" + core_docs
    missing = [token for token in required_artifacts if token not in combined]
    if missing:
        return SmokeResult("minimal-workflow-artifacts", False, f"missing tokens: {missing}")
    return SmokeResult(
        "minimal-workflow-artifacts",
        True,
        "minimal architecture/plan/review artifacts are documented in the portable core",
    )


def check_runtime_assumption_boundaries(project_root: Path) -> SmokeResult:
    hits = []
    for path in _codex_smoke_files(project_root):
        if not path.is_file():
            continue
        text = _read(path)

        for pattern in FORBIDDEN_CLAUDE_RUNTIME_PATTERNS:
            if pattern in text:
                hits.append(f"{_rel(path)} contains Claude runtime path {pattern!r}")

        for pattern in FORBIDDEN_CODEX_GLOBAL_PATTERNS:
            if pattern in text:
                hits.append(f"{_rel(path)} contains guessed Codex global path {pattern!r}")

        for pattern in FORBIDDEN_REQUIRED_DEPENDENCY_PATTERNS:
            if pattern.search(text):
                hits.append(f"{_rel(path)} makes ccusage a required Codex dependency")

        for pattern in FORBIDDEN_CLAUDE_INSTALL_ROUTING_PATTERNS:
            if pattern.search(text):
                hits.append(f"{_rel(path)} routes Codex setup through the Claude installer")

        for pattern in FORBIDDEN_SLASH_COMMAND_REQUIREMENT_PATTERNS:
            if pattern.search(text):
                hits.append(f"{_rel(path)} requires a Claude slash-command style invocation")

    if hits:
        return SmokeResult("runtime-assumption-boundaries", False, "; ".join(hits))
    return SmokeResult(
        "runtime-assumption-boundaries",
        True,
        "Codex smoke path avoids Claude paths, slash-command requirements, global Codex paths, and ccusage requirements",
    )


def check_unsupported_claude_behavior_documented() -> SmokeResult:
    text = _read(SCRIPT_DIR / "unsupported-claude-behavior.md")
    required = [
        "Claude slash-command invocation",
        "Claude prompt-cache preambles",
        "Claude session-log",
        "Claude installer routing",
        "Unsupported",
    ]
    missing = [token for token in required if token not in text]
    if missing:
        return SmokeResult("unsupported-claude-behavior", False, f"missing tokens: {missing}")
    return SmokeResult(
        "unsupported-claude-behavior",
        True,
        "unsupported Claude-only behavior is documented rather than translated",
    )


def run_checks(project_root: Path) -> List[SmokeResult]:
    return [
        check_required_files(project_root),
        check_setup_to_core_path(project_root),
        check_minimal_workflow_artifacts(),
        check_runtime_assumption_boundaries(project_root),
        check_unsupported_claude_behavior_documented(),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        default=".",
        help="Repository root containing AGENTS.md; defaults to the current directory.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    results = run_checks(project_root)

    for result in results:
        status = "OK" if result.ok else "FAIL"
        print(f"{status}: {result.name}: {result.detail}")

    if all(result.ok for result in results):
        print("SMOKE PASS: repo-local Codex workflow path is coherent")
        return 0

    print("SMOKE FAIL: repo-local Codex workflow path is not coherent", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
