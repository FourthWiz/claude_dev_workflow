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

SMOKE_SKILLS = ["discover", "plan", "implement", "review", "gate"]

CODEX_SOURCE_FILES = [
    "README.md",
    "setup.md",
    "installable-feature.md",
    "feature-manifest.json",
    "workflow.md",
    "handoff.md",
    "validate_codex_handoff.py",
    "fixtures/valid-handoff.md",
    "cost.md",
    "cost_event.py",
    "procedures/README.md",
    "procedures/discover.md",
    "procedures/plan.md",
    "procedures/implement.md",
    "procedures/review.md",
    "procedures/gate.md",
    "skills/README.md",
    "unsupported-claude-behavior.md",
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
    files = [project_root / "AGENTS.md"]
    files.extend(SCRIPT_DIR / rel for rel in CODEX_SOURCE_FILES)
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
    workflow = _read(SCRIPT_DIR / "workflow.md")
    procedures_index = _read(SCRIPT_DIR / "procedures" / "README.md")
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
        "adapter README references procedures": "quoin/adapters/codex/procedures/" in adapter,
        "workflow guide names core loop": "discover -> plan -> implement -> review -> gate" in workflow,
        "workflow guide references project artifacts": ".workflow_artifacts/" in workflow,
        "skill index links plan adapter": "(plan/README.md)" in skill_index,
        "procedure index links plan procedure": "(plan.md)" in procedures_index,
        "task layout documents stage folders": "stage-N/" in task_layout,
        "rules document runtime adapter ownership": "Runtime adapters own" in rules,
    }

    for skill in SMOKE_SKILLS:
        adapter_doc = _read(SCRIPT_DIR / "skills" / skill / "README.md")
        procedure_doc = _read(SCRIPT_DIR / "procedures" / f"{skill}.md")
        core_doc = _read(QUOIN_PKG_DIR / "core" / "skills" / f"{skill}.md")
        requirements[f"manifest includes {skill}"] = skill in skill_names
        requirements[f"{skill} adapter links core doc"] = f"quoin/core/skills/{skill}.md" in adapter_doc
        requirements[f"{skill} procedure links core doc"] = f"quoin/core/skills/{skill}.md" in procedure_doc
        requirements[f"{skill} procedure uses workflow artifacts"] = ".workflow_artifacts/" in procedure_doc
        requirements[f"{skill} core doc uses workflow artifacts"] = ".workflow_artifacts/" in core_doc

    missing = [name for name, ok in requirements.items() if not ok]
    if missing:
        return SmokeResult("setup-to-core-path", False, f"failed requirements: {missing}")
    return SmokeResult(
        "setup-to-core-path",
        True,
        "AGENTS.md -> Codex adapter docs -> core skill docs -> workflow docs path is coherent; AGENTS.md -> Codex workflow guide -> Codex procedure docs -> core skill docs -> workflow docs path is coherent",
    )


def check_minimal_workflow_artifacts() -> SmokeResult:
    task_layout = _read(QUOIN_PKG_DIR / "core" / "workflow" / "task-layout.md")
    core_docs = "\n".join(
        _read(QUOIN_PKG_DIR / "core" / "skills" / f"{skill}.md")
        for skill in SMOKE_SKILLS
    )
    required_artifacts = [
        ".workflow_artifacts/",
        "discovery-map.json",
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


def check_handoff_artifacts(project_root: Path) -> SmokeResult:
    agents = _read(project_root / "AGENTS.md")
    workflow = _read(SCRIPT_DIR / "workflow.md")
    handoff = _read(SCRIPT_DIR / "handoff.md")
    validator = _read(SCRIPT_DIR / "validate_codex_handoff.py")
    session_state = _read(QUOIN_PKG_DIR / "core" / "workflow" / "session-state.md")
    combined = "\n".join([agents, workflow, handoff, validator, session_state])

    required = [
        ".workflow_artifacts/memory/sessions/",
        "<YYYY-MM-DD>-<task-name>-codex.md",
        "quoin/core/workflow/session-state.md",
        "quoin/core/workflow/task-layout.md",
        "Continuation context",
        "Lessons learned candidates",
        "Finalized artifacts",
        "HANDOFF PASS",
    ]
    missing = [token for token in required if token not in combined]
    if missing:
        return SmokeResult("handoff-artifacts", False, f"missing tokens: {missing}")
    return SmokeResult(
        "handoff-artifacts",
        True,
        "Codex session handoff docs and validator cover repo-local continuation artifacts",
    )


def check_codex_cost_events(project_root: Path) -> SmokeResult:
    agents = _read(project_root / "AGENTS.md")
    workflow = _read(SCRIPT_DIR / "workflow.md")
    cost_doc = _read(SCRIPT_DIR / "cost.md")
    writer = _read(SCRIPT_DIR / "cost_event.py")
    cost_ledger = _read(QUOIN_PKG_DIR / "core" / "workflow" / "cost-ledger.md")
    combined = "\n".join([agents, workflow, cost_doc, writer, cost_ledger])

    required = [
        "quoin/adapters/codex/cost_event.py",
        "quoin/core/scripts/cost_event.py",
        "quoin/core/workflow/cost-ledger.md",
        "not_available",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_usd",
        "telemetry_source",
        "unknown-codex-",
        "CODEX COST PASS",
    ]
    missing = [token for token in required if token not in combined]
    if missing:
        return SmokeResult("codex-cost-events", False, f"missing tokens: {missing}")
    return SmokeResult(
        "codex-cost-events",
        True,
        "Codex cost events use portable ledger rows and explicit unavailable telemetry",
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
        check_handoff_artifacts(project_root),
        check_codex_cost_events(project_root),
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
