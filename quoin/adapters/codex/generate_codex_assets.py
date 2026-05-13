"""Generate repo-local Codex assets for a Quoin project.

Produces AGENTS.md at <project-root>/AGENTS.md. All writes are repo-local.
No global Codex paths or install registries are touched.

Usage:
    python3 generate_codex_assets.py --project-root <path>
    python3 generate_codex_assets.py --project-root <path> --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List

SCRIPT_DIR = Path(__file__).resolve().parent
# quoin/quoin/adapters/codex/ → up 3 levels → quoin/ (git root)
QUOIN_PKG_DIR = SCRIPT_DIR.parent.parent  # quoin/quoin/
SKILLS_JSON = QUOIN_PKG_DIR / "core" / "workflow" / "skills.json"


def _load_skills() -> List[dict]:
    """Load portable skill metadata from skills.json."""
    with SKILLS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    return data.get("skills", [])


def _render_skill_table(skills: List[dict]) -> str:
    """Render a phase-grouped skill reference table."""
    rows = []
    for skill in skills:
        if not skill.get("user_facing", False):
            continue
        name = skill["name"]
        phase = skill.get("phase", "")
        effort = skill.get("effort", "")
        rows.append(f"| `{name}` | {phase} | {effort} |")
    table = "| Skill | Phase | Effort |\n|-------|-------|--------|\n"
    table += "\n".join(rows)
    return table


def render_agents_md(skills: List[dict]) -> str:
    """Render the AGENTS.md content from portable skill metadata."""
    skill_table = _render_skill_table(skills)
    return f"""\
## Purpose
This repository contains Quoin, a workflow-memory toolkit. Its core value is the
artifact-centric workflow system, not any single coding agent runtime.

## Architectural intent
- Maintain one repository with a shared portable core plus thin runtime adapters.
- Preserve shared workflow semantics: `.workflow_artifacts/`, planning/review
  artifacts, stage-aware task structure, lessons learned, session handoff, and
  cost ledger.
- Do not duplicate Codex-native functionality such as approvals, sandboxing, or
  repo-scoped instruction handling.
- Prefer configuration and adapter boundaries over vendor-specific branching
  scattered throughout the codebase.

## Workflow conventions
Quoin stores all planning and review artifacts under `.workflow_artifacts/` at the
project root. Use this layout:

```
.workflow_artifacts/
  <task-name>/
    architecture.md
    current-plan.md
    cost-ledger.md
    review-1.md
  memory/
    lessons-learned.md
    sessions/
    daily/
```

Ask for Quoin workflow phases in natural language, for example:
- "Use Quoin to create an architecture artifact for this task."
- "Use Quoin to write a current plan under `.workflow_artifacts/`."
- "Use Quoin to review this implementation against the current plan."
- "Update Quoin session handoff and lessons learned."

## Portable skill reference
User-facing workflow skills with effort levels (from `quoin/core/workflow/skills.json`):

{skill_table}

Codex performs each phase natively using its own planning and reasoning capabilities.
No Claude slash-command compatibility is required or implied.

## Refactor guidance
- Separate portable workflow logic from Claude-specific runtime integration.
- Keep Claude-specific assumptions isolated in the Claude adapter (`quoin/adapters/claude/`).
- Build only thin Codex adapter scaffolding unless repository evidence supports more.
- Do not invent unverified Codex local install paths or packaging details.
- If a runtime detail is uncertain, define an interface, placeholder, or documentation
  note instead of hardcoding a guess.

## Editing principles
- Prefer incremental refactors over broad renames.
- Preserve backward compatibility where reasonable.
- Minimize duplication of templates, scripts, and rules.
- Keep documentation honest about implemented vs planned behavior.

## Validation
- Run relevant checks after making changes.
- Report exactly which checks were run and which were not.
- Key validation commands:
  ```
  python3 -m pytest quoin/quoin/dev/tests/
  python3 quoin/quoin/scripts/build_preambles.py --check
  python3 quoin/quoin/adapters/codex/generate_codex_assets.py --project-root . --check
  ```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        required=True,
        help="Project root directory; AGENTS.md is written here.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Compare rendered output against existing AGENTS.md; exit nonzero on drift.",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        print(f"error: --project-root {project_root} is not a directory", file=sys.stderr)
        return 1

    skills = _load_skills()
    rendered = render_agents_md(skills)
    output_path = project_root / "AGENTS.md"

    if args.check:
        if not output_path.exists():
            print(f"FAIL: {output_path} does not exist (run without --check to generate)", file=sys.stderr)
            return 1
        current = output_path.read_text(encoding="utf-8")
        if current == rendered:
            print(f"OK: {output_path} is up to date")
            return 0
        else:
            print(f"FAIL: {output_path} is out of date (run without --check to regenerate)", file=sys.stderr)
            return 1

    output_path.write_text(rendered, encoding="utf-8")
    print(f"Written: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
