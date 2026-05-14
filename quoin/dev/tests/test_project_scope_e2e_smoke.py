"""T-12: End-to-end smoke test for --scope project install.

Steps:
1. Create a tmp dir as a fake project root.
2. Run quoin install --scope project:<tmpdir> via the Python API (in-process).
3. Verify:
   - .claude/skills/ exists with at least one skill dir
   - .claude/settings.json exists with at least one hook stanza
   - CLAUDE.md exists at project root with quoin marker section
   - No literal ~/.claude/ refs remain in deployed skill files (all __QUOIN_HOME__
     placeholders were substituted to the actual project path)

Step 4 (launch Claude Code interactively) is MANUAL-ONLY — not automated here.
See quoin/dev/tests/manual-stage-5-smoke.md for the manual checklist.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
QUOIN_SRC = REPO / "quoin"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture
def fake_project(tmp_path):
    """Return a writable tmp dir acting as a project root."""
    return tmp_path


def _run_project_install(project_dir: Path) -> int:
    """Run quoin install --scope project:<project_dir> in-process.

    Uses --allow-hook-merge to bypass the home hook conflict guard,
    since developers typically have a home-level quoin install running alongside.
    The guard is tested separately in test_scope_install.py (T-13).
    """
    import argparse
    from quoin.cli import _cmd_install

    args = argparse.Namespace(
        runtime="claude",
        scope=f"project:{project_dir}",
        allow_hook_merge=True,  # bypass T-13 home hook conflict guard
        check=False,
        source_dir=str(QUOIN_SRC),
        force_merge=False,
        dev=False,
        use_pip=False,
    )
    return _cmd_install(args)


def test_project_scope_skills_dir_exists(fake_project):
    """After install --scope project, .claude/skills/ exists with skill subdirs."""
    rc = _run_project_install(fake_project)
    assert rc == 0, f"install returned non-zero: {rc}"

    skills_dir = fake_project / ".claude" / "skills"
    assert skills_dir.is_dir(), f".claude/skills/ not created at {skills_dir}"

    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir()]
    assert len(skill_dirs) > 0, ".claude/skills/ has no skill subdirectories"

    # Spot-check a few canonical skills
    for skill in ("plan", "implement", "review"):
        assert (skills_dir / skill).is_dir(), f"Expected skill dir: {skills_dir / skill}"


def test_project_scope_settings_json_has_hooks(fake_project):
    """After install --scope project, .claude/settings.json exists with hook stanzas."""
    rc = _run_project_install(fake_project)
    assert rc == 0

    settings_path = fake_project / ".claude" / "settings.json"
    assert settings_path.exists(), f"settings.json not created at {settings_path}"

    data = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks = data.get("hooks", {})
    assert hooks, "settings.json has no 'hooks' key"

    # Should have at least one hook event registered
    total_stanzas = sum(
        len(v) for v in hooks.values() if isinstance(v, list)
    )
    assert total_stanzas > 0, "settings.json has hooks key but no stanzas"


def test_project_scope_claude_md_at_project_root(fake_project):
    """After install --scope project, CLAUDE.md at project root contains quoin marker."""
    rc = _run_project_install(fake_project)
    assert rc == 0

    claude_md = fake_project / "CLAUDE.md"
    assert claude_md.exists(), f"CLAUDE.md not created at project root: {claude_md}"

    content = claude_md.read_text(encoding="utf-8")
    assert "# === DEV WORKFLOW START ===" in content, (
        "CLAUDE.md at project root is missing the quoin DEV WORKFLOW START marker"
    )
    assert "# === DEV WORKFLOW END ===" in content, (
        "CLAUDE.md at project root is missing the quoin DEV WORKFLOW END marker"
    )

    # Exactly one marker pair (idempotency check)
    assert content.count("# === DEV WORKFLOW START ===") == 1, (
        "CLAUDE.md has more than one DEV WORKFLOW START marker"
    )


def test_project_scope_no_tilde_claude_in_deployed_skills(fake_project):
    """Deployed skill files must not contain literal ~/.claude/ refs — all should be
    substituted to the actual project path by __QUOIN_HOME__ substitution."""
    rc = _run_project_install(fake_project)
    assert rc == 0

    skills_dir = fake_project / ".claude" / "skills"
    project_claude_str = str((fake_project / ".claude").resolve())

    violations = []
    for skill_file in skills_dir.rglob("*.md"):
        content = skill_file.read_text(encoding="utf-8")

        # Check for literal ~/.claude/ in load-bearing positions:
        # - Exclude ~/.claude/projects/ (Claude Code internal — not deployed by quoin)
        # - Exclude blockquote/comment lines (start with '>') — these are Category E docs
        lines_with_home = [
            ln for ln in content.splitlines()
            if "~/.claude/" in ln
            and "~/.claude/projects/" not in ln
            and not ln.lstrip().startswith(">")
            and not ln.lstrip().startswith("#")
        ]
        if lines_with_home:
            violations.append(str(skill_file))

        # Check that no __QUOIN_HOME__ placeholder survived (all should be substituted)
        if "__QUOIN_HOME__" in content:
            violations.append(
                f"{skill_file} still contains __QUOIN_HOME__ placeholder (not substituted)"
            )

    assert not violations, (
        f"Deployed skill files have bad path refs:\n" + "\n".join(f"  - {v}" for v in violations)
    )


# ── Manual-only step (not automated) ─────────────────────────────────────────
#
# Step 4: Launch Claude Code from the project root and verify:
#   - Skills tab shows project-scoped skills
#   - /plan command runs using project-scoped skills
#   - Hooks fire (check Claude Code developer console for hook output)
#   - CLAUDE.md rules are loaded (spot-check one rule in a new session)
#
# This step requires interactive Claude Code invocation and cannot be automated.
# See quoin/dev/tests/manual-stage-5-smoke.md for the full manual checklist.
