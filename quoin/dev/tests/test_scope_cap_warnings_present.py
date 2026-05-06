"""T-07: Static test that scope-cap warnings are present in all three skill files.

Checks:
  - implement/SKILL.md contains '## §0a Scope cap'
  - revise/SKILL.md contains '## Scope cap'
  - revise-fast/SKILL.md contains '## Scope cap'
  - All three contain '30-40 tool uses' (or '30–40' em-dash variant)
  - All three contain the standalone-no-retry note (substring: 'no automatic retry')
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
IMPLEMENT_SKILL = REPO_ROOT / "quoin" / "skills" / "implement" / "SKILL.md"
REVISE_SKILL = REPO_ROOT / "quoin" / "skills" / "revise" / "SKILL.md"
REVISE_FAST_SKILL = REPO_ROOT / "quoin" / "skills" / "revise-fast" / "SKILL.md"


def _read(path: Path) -> str:
    assert path.exists(), f"SKILL.md not found at {path}"
    return path.read_text()


class TestScopeCapWarningsPresent:
    """Scope-cap warning presence assertions (T-05/T-06/T-07)."""

    def test_implement_has_scope_cap_heading(self):
        """implement/SKILL.md must contain '## §0a Scope cap'."""
        text = _read(IMPLEMENT_SKILL)
        assert "## §0a Scope cap" in text, (
            "implement/SKILL.md is missing '## §0a Scope cap' heading"
        )

    def test_revise_has_scope_cap_heading(self):
        """revise/SKILL.md must contain '## Scope cap'."""
        text = _read(REVISE_SKILL)
        assert "## Scope cap" in text, (
            "revise/SKILL.md is missing '## Scope cap' heading"
        )

    def test_revise_fast_has_scope_cap_heading(self):
        """revise-fast/SKILL.md must contain '## Scope cap'."""
        text = _read(REVISE_FAST_SKILL)
        assert "## Scope cap" in text, (
            "revise-fast/SKILL.md is missing '## Scope cap' heading"
        )

    def test_all_have_30_40_tool_uses(self):
        """All three skill files must mention '30-40 tool uses' or '30–40 tool uses'."""
        files = [
            ("implement", IMPLEMENT_SKILL),
            ("revise", REVISE_SKILL),
            ("revise-fast", REVISE_FAST_SKILL),
        ]
        for name, path in files:
            text = _read(path)
            has_hyphen = "30-40 tool uses" in text
            has_emdash = "30–40 tool uses" in text  # em-dash variant
            assert has_hyphen or has_emdash, (
                f"{name}/SKILL.md is missing '30-40 tool uses' (or em-dash variant)"
            )

    def test_all_have_no_automatic_retry_note(self):
        """All three skill files must contain the standalone-no-retry note.

        Checks for 'automatic retry on stream-idle timeout' (case-insensitive),
        which is present in all three files regardless of line wrapping.
        """
        files = [
            ("implement", IMPLEMENT_SKILL),
            ("revise", REVISE_SKILL),
            ("revise-fast", REVISE_FAST_SKILL),
        ]
        for name, path in files:
            text = _read(path)
            assert "automatic retry on stream-idle timeout" in text.lower(), (
                f"{name}/SKILL.md is missing the standalone-no-retry note "
                f"(substring 'automatic retry on stream-idle timeout')"
            )
