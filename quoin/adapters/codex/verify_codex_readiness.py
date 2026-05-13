"""Verify repo-local Codex readiness for Quoin.

This is not a Codex installer. It checks the repo-local contract Quoin can
verify today: root AGENTS.md instructions, portable workflow docs, Codex adapter
docs, repo-local manifest scope, and Claude install isolation.

Usage:
    python3 quoin/adapters/codex/verify_codex_readiness.py --project-root .
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


SCRIPT_DIR = Path(__file__).resolve().parent
QUOIN_PKG_DIR = SCRIPT_DIR.parent.parent
REPO_ROOT = QUOIN_PKG_DIR.parent

FORBIDDEN_GLOBAL_CODEX_PATTERNS = [
    "~/." + "codex",
    "$HOME/." + "codex",
    "/usr/local/" + "codex",
    "/opt/" + "codex",
    "." + "codex/commands",
    "npm install" + " -g " + "codex",
]

CORE_WORKFLOW_PHASES = ["discover", "plan", "implement", "review", "gate"]


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _required_files(paths: Iterable[Path]) -> List[Path]:
    return [path for path in paths if not path.is_file()]


def _codex_adapter_text_files() -> List[Path]:
    suffixes = {".md", ".json", ".py"}
    return [
        path for path in SCRIPT_DIR.rglob("*")
        if path.is_file()
        and path.suffix in suffixes
        and "__pycache__" not in path.parts
    ]


def check_project_root(project_root: Path) -> CheckResult:
    if not project_root.is_dir():
        return CheckResult("project-root", False, f"{project_root} is not a directory")
    return CheckResult("project-root", True, str(project_root))


def check_agents_md(project_root: Path) -> CheckResult:
    agents_md = project_root / "AGENTS.md"
    if not agents_md.is_file():
        return CheckResult("agents-md", False, f"missing {agents_md}")

    text = _read(agents_md).lower()
    required = [
        ".workflow_artifacts/",
        "project root",
        "native codex",
        "do not",
    ]
    missing = [token for token in required if token not in text]
    if missing:
        return CheckResult(
            "agents-md",
            False,
            f"{agents_md} is missing required Codex setup terms: {missing}",
        )
    return CheckResult("agents-md", True, f"{agents_md} contains repo-local guidance")


def check_portable_core() -> CheckResult:
    required = [
        QUOIN_PKG_DIR / "core" / "workflow" / "rules.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "task-layout.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "session-state.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "cost-ledger.md",
        QUOIN_PKG_DIR / "core" / "workflow" / "skills.json",
    ]
    missing = _required_files(required)
    if missing:
        return CheckResult("portable-core", False, f"missing files: {missing}")

    skills = json.loads(_read(QUOIN_PKG_DIR / "core" / "workflow" / "skills.json"))
    if not skills.get("skills"):
        return CheckResult("portable-core", False, "skills.json has no skills")
    return CheckResult("portable-core", True, "portable workflow docs and skills metadata found")


def check_codex_adapter_docs() -> CheckResult:
    required = [
        SCRIPT_DIR / "README.md",
        SCRIPT_DIR / "setup.md",
        SCRIPT_DIR / "installable-feature.md",
        SCRIPT_DIR / "feature-manifest.json",
        SCRIPT_DIR / "generate_codex_assets.py",
        SCRIPT_DIR / "smoke_codex_workflow.py",
        SCRIPT_DIR / "handoff.md",
        SCRIPT_DIR / "validate_codex_handoff.py",
        SCRIPT_DIR / "fixtures" / "valid-handoff.md",
        SCRIPT_DIR / "cost.md",
        SCRIPT_DIR / "cost_event.py",
        SCRIPT_DIR / "workflow.md",
        SCRIPT_DIR / "procedures" / "README.md",
        SCRIPT_DIR / "skills" / "README.md",
        SCRIPT_DIR / "unsupported-claude-behavior.md",
    ]
    for phase in CORE_WORKFLOW_PHASES:
        required.append(SCRIPT_DIR / "procedures" / f"{phase}.md")
    missing = _required_files(required)
    if missing:
        return CheckResult("codex-adapter-docs", False, f"missing files: {missing}")
    return CheckResult("codex-adapter-docs", True, "Codex adapter docs and generator found")


def check_codex_workflow_procedures() -> CheckResult:
    workflow = SCRIPT_DIR / "workflow.md"
    procedures_index = SCRIPT_DIR / "procedures" / "README.md"
    issues = []

    workflow_text = _read(workflow) if workflow.is_file() else ""
    for token in [
        ".workflow_artifacts/",
        "discover -> plan -> implement -> review -> gate",
        "quoin/core/workflow/rules.md",
        "quoin/core/workflow/task-layout.md",
        "quoin/core/workflow/session-state.md",
        "quoin/core/workflow/cost-ledger.md",
    ]:
        if token not in workflow_text:
            issues.append(f"workflow.md missing {token!r}")

    index_text = _read(procedures_index) if procedures_index.is_file() else ""
    for phase in CORE_WORKFLOW_PHASES:
        procedure = SCRIPT_DIR / "procedures" / f"{phase}.md"
        core_ref = f"quoin/core/skills/{phase}.md"
        if f"| `{phase}` |" not in index_text or f"({phase}.md)" not in index_text or core_ref not in index_text:
            issues.append(f"procedures/README.md missing {phase} entry")
        if not procedure.is_file():
            issues.append(f"{phase}: missing procedure doc")
            continue

        text = _read(procedure)
        required_tokens = [
            f"Portable contract: `{core_ref}`",
            ".workflow_artifacts/",
            "quoin/core/workflow/rules.md",
            "quoin/core/workflow/task-layout.md",
            "quoin/core/workflow/session-state.md",
            "quoin/core/workflow/cost-ledger.md",
            "## Codex Procedure",
            "## Codex Native Notes",
        ]
        missing = [token for token in required_tokens if token not in text]
        if missing:
            issues.append(f"{phase}: procedure doc missing tokens {missing}")

    if issues:
        return CheckResult("codex-workflow-procedures", False, "; ".join(issues))
    return CheckResult(
        "codex-workflow-procedures",
        True,
        "Codex procedures cover discover, plan, implement, review, and gate",
    )


def check_codex_handoff_contract() -> CheckResult:
    handoff = SCRIPT_DIR / "handoff.md"
    validator = SCRIPT_DIR / "validate_codex_handoff.py"
    fixture = SCRIPT_DIR / "fixtures" / "valid-handoff.md"
    issues = []

    handoff_text = _read(handoff) if handoff.is_file() else ""
    for token in [
        ".workflow_artifacts/memory/sessions/",
        "<YYYY-MM-DD>-<task-name>-codex.md",
        "quoin/core/workflow/session-state.md",
        "quoin/core/workflow/task-layout.md",
        "quoin/core/workflow/rules.md",
        "quoin/core/skills/end_of_day.md",
        "validate_codex_handoff.py",
        "not a live Codex hook",
    ]:
        if token not in handoff_text:
            issues.append(f"handoff.md missing {token!r}")

    validator_text = _read(validator) if validator.is_file() else ""
    for token in [
        "REQUIRED_SECTIONS",
        "REQUIRED_METADATA",
        ".workflow_artifacts",
        "HANDOFF PASS",
        "HANDOFF FAIL",
        "FIXTURE_PATH",
    ]:
        if token not in validator_text:
            issues.append(f"validate_codex_handoff.py missing {token!r}")

    fixture_text = _read(fixture) if fixture.is_file() else ""
    for token in [
        "# Codex Session Handoff:",
        ".workflow_artifacts/memory/sessions/",
        "## Continuation context",
        "## Cost",
    ]:
        if token not in fixture_text:
            issues.append(f"fixtures/valid-handoff.md missing {token!r}")

    if issues:
        return CheckResult("codex-handoff-contract", False, "; ".join(issues))
    return CheckResult(
        "codex-handoff-contract",
        True,
        "Codex handoff docs and validator are grounded in portable session contracts",
    )


def check_codex_cost_contract() -> CheckResult:
    cost_doc = SCRIPT_DIR / "cost.md"
    writer = SCRIPT_DIR / "cost_event.py"
    manifest = SCRIPT_DIR / "feature-manifest.json"
    issues = []

    cost_text = _read(cost_doc) if cost_doc.is_file() else ""
    for token in [
        "not_available",
        "quoin/core/scripts/cost_event.py",
        "quoin/core/workflow/cost-ledger.md",
        "input_tokens",
        "cost_usd",
        "telemetry_source",
        "unknown-codex-",
    ]:
        if token not in cost_text:
            issues.append(f"cost.md missing {token!r}")

    writer_text = _read(writer) if writer.is_file() else ""
    for token in [
        "build_codex_event",
        "validate_ledger",
        "not_available",
        "format_row",
        "parse_row",
        "CODEX COST PASS",
        "unknown-codex-",
    ]:
        if token not in writer_text:
            issues.append(f"cost_event.py missing {token!r}")

    manifest_text = _read(manifest) if manifest.is_file() else ""
    for token in [
        "quoin/adapters/codex/cost.md",
        "quoin/adapters/codex/cost_event.py",
        "quoin/core/scripts/cost_event.py",
    ]:
        if token not in manifest_text:
            issues.append(f"feature-manifest.json missing {token!r}")

    if issues:
        return CheckResult("codex-cost-contract", False, "; ".join(issues))
    return CheckResult(
        "codex-cost-contract",
        True,
        "Codex cost writer records unavailable telemetry explicitly through portable cost events",
    )


def check_codex_skill_adapter_coverage() -> CheckResult:
    skills_path = QUOIN_PKG_DIR / "core" / "workflow" / "skills.json"
    skills = json.loads(_read(skills_path)).get("skills", [])

    issues = []
    for skill in skills:
        name = skill["name"]
        core_doc = QUOIN_PKG_DIR / "core" / "skills" / f"{name}.md"
        adapter_doc = SCRIPT_DIR / "skills" / name / "README.md"

        if not core_doc.is_file():
            issues.append(f"{name}: missing portable core doc")
            continue
        if not adapter_doc.is_file():
            issues.append(f"{name}: missing Codex adapter doc")
            continue

        text = _read(adapter_doc)
        required_tokens = [
            f"quoin/core/skills/{name}.md",
            "## Codex invocation",
            "## Portable workflow contract",
            "## Unsupported Claude-only translations",
            "does not get a generated",
            "Do not create a Codex global install",
        ]
        missing = [token for token in required_tokens if token not in text]
        if missing:
            issues.append(f"{name}: adapter doc missing tokens {missing}")

    if issues:
        return CheckResult("codex-skill-adapter-coverage", False, "; ".join(issues))
    return CheckResult(
        "codex-skill-adapter-coverage",
        True,
        f"Codex adapter docs cover {len(skills)} portable skills",
    )


def check_manifest_scope() -> CheckResult:
    manifest_path = SCRIPT_DIR / "feature-manifest.json"
    manifest = json.loads(_read(manifest_path))

    generated = manifest.get("generated_outputs", [])
    non_repo_local = [
        entry for entry in generated if entry.get("scope") != "repo-local"
    ]
    if non_repo_local:
        return CheckResult(
            "manifest-scope",
            False,
            f"generated outputs must be repo-local: {non_repo_local}",
        )

    unsupported = manifest.get("unsupported_outputs", [])
    names = " ".join(entry.get("name", "") for entry in unsupported).lower()
    if "global" not in names or "command" not in names:
        return CheckResult(
            "manifest-scope",
            False,
            "manifest must mark global install and command files as unsupported",
        )

    return CheckResult("manifest-scope", True, "manifest is scoped to repo-local outputs")


def check_no_guessed_global_paths(project_root: Path) -> CheckResult:
    docs = [
        project_root / "AGENTS.md",
        QUOIN_PKG_DIR / "docs" / "runtime-portability.md",
        QUOIN_PKG_DIR / "docs" / "runtime-portability-status.md",
        QUOIN_PKG_DIR / "docs" / "effort-levels.md",
    ] + _codex_adapter_text_files()
    hits = []
    for path in docs:
        if not path.is_file():
            continue
        text = _read(path)
        for pattern in FORBIDDEN_GLOBAL_CODEX_PATTERNS:
            if pattern in text:
                hits.append(f"{path}: {pattern}")

    if hits:
        return CheckResult("no-guessed-global-paths", False, "; ".join(hits))
    return CheckResult("no-guessed-global-paths", True, "no guessed Codex global paths found")


def check_claude_install_isolated() -> CheckResult:
    install_sh = QUOIN_PKG_DIR / "install.sh"
    if not install_sh.is_file():
        return CheckResult("claude-install-isolated", False, f"missing {install_sh}")

    text = _read(install_sh).lower()
    if "codex" in text:
        return CheckResult(
            "claude-install-isolated",
            False,
            "quoin/install.sh must remain Claude-only and not mention Codex",
        )
    if '"install"' not in text or "source-dir" not in text or "python" not in text:
        return CheckResult(
            "claude-install-isolated",
            False,
            "quoin/install.sh no longer appears to delegate to the Quoin installer",
        )
    return CheckResult("claude-install-isolated", True, "Claude installer remains isolated")


def run_checks(project_root: Path) -> List[CheckResult]:
    return [
        check_project_root(project_root),
        check_agents_md(project_root),
        check_portable_core(),
        check_codex_adapter_docs(),
        check_codex_skill_adapter_coverage(),
        check_codex_workflow_procedures(),
        check_codex_handoff_contract(),
        check_codex_cost_contract(),
        check_manifest_scope(),
        check_no_guessed_global_paths(project_root),
        check_claude_install_isolated(),
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
        print("READY: repo-local Codex setup contract is satisfied")
        return 0

    print("NOT READY: repo-local Codex setup contract is not satisfied", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
