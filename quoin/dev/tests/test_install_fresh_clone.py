"""T-10: Fresh-clone install.sh end-to-end smoke test.

Skips on CI (no `claude` or `npx`). On a dev machine, verifies:
  - install.sh exits 0
  - All 21 SKILL.md files copied to ~/.claude/skills/
  - All v3 memory files deployed to ~/.claude/memory/
  - All v3 scripts deployed + executable
  - ~/.claude/CLAUDE.md has exactly one marker section
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"

CANONICAL_SKILLS = [
    "architect", "capture_insight", "cost_snapshot", "critic", "discover",
    "end_of_day", "end_of_task", "expand", "gate", "implement",
    "init_workflow", "plan", "review", "revise", "revise-fast",
    "rollback", "run", "start_of_day", "thorough_plan", "triage",
    "weekly_review",
]

V3_MEMORY_FILES = [
    "format-kit.md",
    "glossary.md",
    "format-kit.sections.json",
    "summary-prompt.md",
    "terse-rubric.md",
]

V3_SCRIPTS = [
    "validate_artifact.py",
    "path_resolve.py",
    "cost_from_jsonl.py",
]


pytestmark = pytest.mark.skipif(
    shutil.which("claude") is None or shutil.which("npx") is None,
    reason=(
        "install.sh requires `claude` (hard) and `npx` (soft); test is dev-machine only. "
        "install.sh aborts on missing claude (lines 46-48), so test cannot run on CI."
    ),
)


def test_fresh_clone_install_e2e():
    assert INSTALL_SH.exists(), f"quoin/install.sh not found at {INSTALL_SH}"

    with tempfile.TemporaryDirectory() as tmp_home_str:
        tmp_home = Path(tmp_home_str)
        env = {**os.environ, "HOME": str(tmp_home)}
        result = subprocess.run(
            ["bash", str(INSTALL_SH)],
            env=env,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"install.sh failed: returncode={result.returncode}\n"
            f"stdout: {result.stdout[:1500]}\nstderr: {result.stderr[:1500]}"
        )

        skills_dir = tmp_home / ".claude" / "skills"
        for skill in CANONICAL_SKILLS:
            skill_md = skills_dir / skill / "SKILL.md"
            assert skill_md.exists(), f"Missing skill SKILL.md: {skill_md}"

        memory_dir = tmp_home / ".claude" / "memory"
        for mem_file in V3_MEMORY_FILES:
            assert (memory_dir / mem_file).exists(), (
                f"Missing v3 memory file: {memory_dir / mem_file}"
            )

        scripts_dir = tmp_home / ".claude" / "scripts"
        for script in V3_SCRIPTS:
            script_path = scripts_dir / script
            assert script_path.exists(), f"Missing v3 script: {script_path}"
            assert os.access(script_path, os.X_OK), (
                f"v3 script not executable: {script_path}"
            )

        assert (tmp_home / ".claude" / "QUICKSTART.md").exists(), (
            "install.sh did not deploy QUICKSTART.md to ~/.claude/"
        )

        claude_md = tmp_home / ".claude" / "CLAUDE.md"
        assert claude_md.exists(), "install.sh did not create ~/.claude/CLAUDE.md"
        content = claude_md.read_text()
        marker_sections = re.findall(
            r"# === DEV WORKFLOW START ===.*?# === DEV WORKFLOW END ===",
            content,
            re.DOTALL,
        )
        assert len(marker_sections) == 1, (
            f"Expected exactly 1 marker section in fresh CLAUDE.md; got {len(marker_sections)}"
        )
