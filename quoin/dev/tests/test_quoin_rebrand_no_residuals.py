"""T-07: Verify no dev-workflow residuals remain post-rebrand.

Three test cases:
1. No lowercase 'dev-workflow' in quoin/ (excluding frozen v2-historical fixture).
2. No 'Quoin foundation Stage' prose-drift wording in skills or CLAUDE.md.
3. CHANGELOG.md documents the DEV WORKFLOW marker preservation.
"""
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
QUOIN_DIR = REPO_ROOT / "quoin"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"


def test_no_lowercase_dev_workflow_in_quoin_dir():
    """grep for 'dev-workflow' in quoin/, excluding v2-historical fixture and legitimate refs.

    Legitimate exceptions (allowlisted):
      - quoin/skills/init_workflow/SKILL.md — legacy-detection block intentionally
        references the old (project)/dev-workflow/QUICKSTART.md path.
      - quoin/scripts/tests/test_quoin_rebrand_no_residuals.py — this test file
        itself contains the search string.
      - quoin/scripts/tests/test_init_workflow_legacy_quickstart.py — tests assert
        the legacy-detection block contains the string.
    """
    allowlist_files = {
        "quoin/skills/init_workflow/SKILL.md",
        "quoin/scripts/tests/test_quoin_rebrand_no_residuals.py",
        "quoin/scripts/tests/test_init_workflow_legacy_quickstart.py",
    }
    result = subprocess.run(
        [
            "grep", "-rln", "--include=*.md", "--include=*.sh",
            "--include=*.py", "--include=*.json", "--include=*.html",
            "--exclude-dir=v2-historical",
            "dev-workflow",
            str(QUOIN_DIR),
        ],
        capture_output=True,
        text=True,
    )
    # grep -l returns one filename per line that contains the pattern
    matched_files = {
        str(Path(line).relative_to(REPO_ROOT))
        for line in result.stdout.splitlines()
        if line.strip()
    }
    unexpected = matched_files - allowlist_files
    assert not unexpected, (
        f"Unexpected files contain 'dev-workflow' (not in allowlist):\n"
        + "\n".join(sorted(unexpected))
    )


def test_no_quoin_foundation_stage_prose_in_skills():
    """No 'Quoin foundation Stage' prose-drift wording in skills or CLAUDE.md."""
    result = subprocess.run(
        [
            "grep", "-rn",
            "Quoin foundation Stage",
            str(QUOIN_DIR / "skills"),
            str(QUOIN_DIR / "CLAUDE.md"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, (
        f"Expected no 'Quoin foundation Stage' prose in skills/CLAUDE.md, but found:\n{result.stdout[:2000]}"
    )


def test_changelog_documents_marker_preservation():
    """CHANGELOG.md must contain the literal DEV WORKFLOW marker string."""
    assert CHANGELOG.exists(), f"CHANGELOG.md not found at {CHANGELOG}"
    content = CHANGELOG.read_text()
    marker = "# === DEV WORKFLOW START ==="
    assert marker in content, (
        f"CHANGELOG.md must document marker preservation with the literal string '{marker}'"
    )
