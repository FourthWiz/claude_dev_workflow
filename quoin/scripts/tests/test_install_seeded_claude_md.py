"""T-08: install.sh seeded-CLAUDE.md upgrade test.

Critical mitigation for the install.sh-marker-shift risk.
Tests that re-running install.sh against a seeded CLAUDE.md REPLACES
the marker section (not append) and preserves user content. Also actively
exercises the Stage 5 cleanup loops by pre-creating obsolete script stubs
and asserting they're removed.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
INSTALL_SH = REPO_ROOT / "quoin" / "install.sh"


pytestmark = pytest.mark.skipif(
    shutil.which("claude") is None,
    reason="install.sh requires `claude` CLI; test is dev-machine only",
)


def _seed_obsolete_stubs(tmp_home: Path) -> Dict[str, Path]:
    """Pre-create stubs that exercise BOTH cleanup loops (primary + auxiliary)."""
    scripts_dir = tmp_home / ".claude" / "scripts"
    tests_dir = scripts_dir / "tests"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    tests_dir.mkdir(parents=True, exist_ok=True)
    stubs = {
        "summarize_for_human.py": scripts_dir / "summarize_for_human.py",
        "with_env.sh": scripts_dir / "with_env.sh",
        "test_summarize_for_human.py": tests_dir / "test_summarize_for_human.py",
        "test_with_env_sh.py": tests_dir / "test_with_env_sh.py",
    }
    for path in stubs.values():
        path.touch()
    return stubs


def _run_install(tmp_home: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(tmp_home)}
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )


def test_seeded_claude_md_section_replaced_not_appended():
    """Re-run install.sh against seeded CLAUDE.md → marker section REPLACED, not appended.

    Also exercises both cleanup loops via pre-seeded obsolete stubs.
    """
    with tempfile.TemporaryDirectory() as tmp_home_str:
        tmp_home = Path(tmp_home_str)
        claude_dir = tmp_home / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        claude_md = claude_dir / "CLAUDE.md"
        claude_md.write_text(
            "[[USER PRELUDE]]\n\n"
            "# === DEV WORKFLOW START ===\n"
            "[[OLD STALE WORKFLOW RULES]]\n"
            "# === DEV WORKFLOW END ===\n\n"
            "[[USER POSTLUDE]]\n"
        )
        stubs = _seed_obsolete_stubs(tmp_home)

        result = _run_install(tmp_home)
        assert result.returncode == 0, (
            f"install.sh failed: returncode={result.returncode}\n"
            f"stdout: {result.stdout[:1000]}\nstderr: {result.stderr[:1000]}"
        )

        content = claude_md.read_text()
        marker_sections = re.findall(
            r"# === DEV WORKFLOW START ===.*?# === DEV WORKFLOW END ===",
            content,
            re.DOTALL,
        )
        assert len(marker_sections) == 1, (
            f"Expected exactly 1 marker section after install (replaced, not appended); "
            f"got {len(marker_sections)}"
        )
        assert "[[USER PRELUDE]]" in content, "User prelude was lost"
        assert "[[USER POSTLUDE]]" in content, "User postlude was lost"
        assert "[[OLD STALE WORKFLOW RULES]]" not in content, (
            "Old marker contents survived — section was not replaced"
        )

        for name, path in stubs.items():
            assert not path.exists(), (
                f"Cleanup loop did not remove {name} at {path} — install.sh cleanup loops "
                f"(lines ~138-151) are not actively exercised."
            )


def test_fresh_claude_md_section_appended():
    """Fresh ~/.claude/ (no CLAUDE.md beforehand) → install.sh creates it with one marker."""
    with tempfile.TemporaryDirectory() as tmp_home_str:
        tmp_home = Path(tmp_home_str)
        # Don't pre-create CLAUDE.md — let install.sh do it
        result = _run_install(tmp_home)
        assert result.returncode == 0, (
            f"install.sh failed: returncode={result.returncode}\n"
            f"stdout: {result.stdout[:1000]}\nstderr: {result.stderr[:1000]}"
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
