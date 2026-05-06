"""T-10: Static test that end_of_task/SKILL.md is decomposed into 3 sub-phases.

Checks:
  - SKILL.md contains all 3 sub-phase headings (Sub-phase A, B, C)
  - 'eot-preflights.json' (fixed name, no date stamp) is mentioned
  - 'cost-summary.json' hand-off is mentioned (Sub-phase B output)
  - The literal "Write `eot-preflights" appears BEFORE "Dispatch Sub-phase A"
    in the SKILL.md prose (MIN-3: write-before-dispatch ordering enforced)
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EOT_SKILL = REPO_ROOT / "quoin" / "skills" / "end_of_task" / "SKILL.md"


def _text() -> str:
    assert EOT_SKILL.exists(), f"end_of_task/SKILL.md not found at {EOT_SKILL}"
    return EOT_SKILL.read_text()


class TestEndOfTaskDecomposed:
    """end_of_task decomposition static assertions (T-10)."""

    def test_has_sub_phase_a(self):
        """SKILL.md must contain 'Sub-phase A' heading."""
        text = _text()
        assert "Sub-phase A" in text, (
            "end_of_task/SKILL.md is missing 'Sub-phase A' section"
        )

    def test_has_sub_phase_b(self):
        """SKILL.md must contain 'Sub-phase B' heading."""
        text = _text()
        assert "Sub-phase B" in text, (
            "end_of_task/SKILL.md is missing 'Sub-phase B' section"
        )

    def test_has_sub_phase_c(self):
        """SKILL.md must contain 'Sub-phase C' heading."""
        text = _text()
        assert "Sub-phase C" in text, (
            "end_of_task/SKILL.md is missing 'Sub-phase C' section"
        )

    def test_has_eot_preflights_json(self):
        """SKILL.md must reference 'eot-preflights.json' (fixed name, no date stamp)."""
        text = _text()
        assert "eot-preflights.json" in text, (
            "end_of_task/SKILL.md does not reference 'eot-preflights.json' hand-off file"
        )
        # Ensure the old date-stamped name pattern is NOT present
        assert "eot-preflights-" not in text, (
            "end_of_task/SKILL.md still references a date-stamped 'eot-preflights-*.json' "
            "instead of the fixed name 'eot-preflights.json' (date race risk — MAJ-1)"
        )

    def test_has_cost_summary_json(self):
        """SKILL.md must reference 'cost-summary.json' as Sub-phase B output."""
        text = _text()
        assert "cost-summary.json" in text, (
            "end_of_task/SKILL.md does not reference 'cost-summary.json' (Sub-phase B output)"
        )

    def test_write_before_dispatch_ordering(self):
        """'Write eot-preflights' must appear BEFORE 'Dispatch Sub-phase A' in SKILL.md.

        MIN-3 enforcement: the orchestrator must write the hand-off file before
        dispatching any sub-phase (no race between write and read).
        """
        text = _text()
        lines = text.splitlines()

        write_line = None
        dispatch_line = None

        for i, line in enumerate(lines, start=1):
            if write_line is None and "Write `eot-preflights" in line:
                write_line = i
            if dispatch_line is None and "Dispatch Sub-phase A" in line:
                dispatch_line = i

        assert write_line is not None, (
            "end_of_task/SKILL.md does not contain 'Write `eot-preflights' text "
            "(orchestrator hand-off write instruction)"
        )
        assert dispatch_line is not None, (
            "end_of_task/SKILL.md does not contain 'Dispatch Sub-phase A' text"
        )
        assert write_line < dispatch_line, (
            f"'Write `eot-preflights' (line {write_line}) must appear BEFORE "
            f"'Dispatch Sub-phase A' (line {dispatch_line}) — MIN-3 ordering requirement"
        )
