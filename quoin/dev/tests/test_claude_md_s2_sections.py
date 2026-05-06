"""T-21 — pytest CI wrapper for quoin/CLAUDE.md S-2 section correctness.

Verifies the three structural additions made by Stage 2:
  (a) `checkpoint` appears in the Phase values enumeration line
  (b) The `### Hooks deployed by quoin` section exists (hook event/matcher table)
  (c) The `### Lifecycle skills (checkpoint / end_of_day / sleep)` section exists

These are regression guards: they catch future edits to CLAUDE.md that accidentally
remove the S-2 additions (e.g., a merge conflict resolution that drops a section,
or a rebase that loses the T-03 Phase-values edit).

Run:
  python3 -m pytest quoin/dev/tests/test_claude_md_s2_sections.py -v
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE_MD = REPO_ROOT / "quoin" / "CLAUDE.md"


def _read_claude_md() -> str:
    assert CLAUDE_MD.exists(), f"quoin/CLAUDE.md not found at {CLAUDE_MD}"
    return CLAUDE_MD.read_text(encoding="utf-8")


class TestClaudeMdS2Sections:
    """Regression guards for S-2 additions to quoin/CLAUDE.md."""

    def test_claude_md_exists(self):
        """quoin/CLAUDE.md must be present in the repo."""
        assert CLAUDE_MD.exists(), f"quoin/CLAUDE.md not found at {CLAUDE_MD}"

    def test_checkpoint_in_phase_values(self):
        """T-03: `checkpoint` must appear in the Phase values enumeration.

        The line looks like:
          **Phase values:** `discover`, `architect`, ..., `checkpoint`, `ad-hoc`
        """
        content = _read_claude_md()
        # Find the Phase values line
        phase_line = None
        for line in content.splitlines():
            if "**Phase values:**" in line:
                phase_line = line
                break
        assert phase_line is not None, (
            "Could not find a line containing '**Phase values:**' in quoin/CLAUDE.md. "
            "The Phase values enumeration was removed or reformatted."
        )
        assert "checkpoint" in phase_line, (
            f"'checkpoint' not found in Phase values line:\n  {phase_line}\n\n"
            "T-03 added `checkpoint` to the enumeration — this assertion catches "
            "accidental removal."
        )

    def test_hooks_deployed_section_exists(self):
        """T-05: `### Hooks deployed by quoin` section must exist.

        This section documents the four (event, matcher) tuples deployed by install.sh
        and the event/timeout table. Its presence confirms the hooks-deploy documentation
        is in place.
        """
        content = _read_claude_md()
        assert "### Hooks deployed by quoin" in content, (
            "'### Hooks deployed by quoin' section not found in quoin/CLAUDE.md. "
            "T-05 added this section — it may have been accidentally removed."
        )

    def test_lifecycle_skills_section_exists(self):
        """T-22 doc: `### Lifecycle skills (checkpoint / end_of_day / sleep)` section must exist.

        This section defines the boundary between /checkpoint, /end_of_day, and /sleep.
        """
        content = _read_claude_md()
        assert "### Lifecycle skills" in content, (
            "'### Lifecycle skills' section not found in quoin/CLAUDE.md. "
            "The lifecycle-skills section was added in S-2 — it may have been removed."
        )

    def test_hooks_table_has_four_events(self):
        """The hooks-deployed table must register exactly the four canonical (event, matcher) tuples.

        Expected tuples:
          - UserPromptSubmit / *
          - PreCompact / auto
          - SessionStart / startup
          - SessionStart / resume
        """
        content = _read_claude_md()
        expected = [
            ("UserPromptSubmit", "*"),
            ("PreCompact", "auto"),
            ("SessionStart", "startup"),
            ("SessionStart", "resume"),
        ]
        for event, matcher in expected:
            assert event in content and matcher in content, (
                f"Expected event '{event}' with matcher '{matcher}' not found in "
                "quoin/CLAUDE.md hooks table. The hooks-deploy table may be incomplete."
            )

    def test_checkpoint_phase_value_is_backtick_quoted(self):
        """The `checkpoint` phase value must be quoted with backticks (style consistency)."""
        content = _read_claude_md()
        # Find the Phase values line and check backtick form
        for line in content.splitlines():
            if "**Phase values:**" in line:
                # Should contain `checkpoint` (with backticks)
                assert "`checkpoint`" in line, (
                    f"Phase values line found but `checkpoint` not backtick-quoted:\n  {line}"
                )
                return
        pytest.fail("No **Phase values:** line found in quoin/CLAUDE.md")

    def test_userpromptsubmit_section_exists(self):
        """userpromptsubmit.sh contract documentation must exist in CLAUDE.md."""
        content = _read_claude_md()
        assert "userpromptsubmit.sh" in content, (
            "'userpromptsubmit.sh' not found in quoin/CLAUDE.md — "
            "the hooks section may be missing or the filename was changed."
        )

    def test_basis_points_convention_documented(self):
        """The basis-points convention must be documented (prevents floating-point comparison regressions)."""
        content = _read_claude_md()
        assert "basis-points" in content.lower() or "basis_points" in content.lower(), (
            "Basis-points convention not found in quoin/CLAUDE.md. "
            "This documents the integer arithmetic used in hook threshold comparisons."
        )

    def test_tunable_constants_table_exists(self):
        """The tunable constants table (QUOIN_* env vars) must be documented."""
        content = _read_claude_md()
        assert "QUOIN_BYTES_PER_TOKEN" in content, (
            "'QUOIN_BYTES_PER_TOKEN' not found in quoin/CLAUDE.md — "
            "the tunable constants table may be missing."
        )
        assert "QUOIN_EFFECTIVE_CONTEXT_LIMIT" in content, (
            "'QUOIN_EFFECTIVE_CONTEXT_LIMIT' not found in quoin/CLAUDE.md — "
            "the tunable constants table may be missing."
        )
