"""Test pins for the checkpoint timestamped filename format and three-shape picker detection.

IVG-48 follow-up from checkpoint-timestamp-session-link review-1 MINOR-2 / R-02:
the new <YYYY-MM-DD>T<HHMM>-<task-name>.md format and the picker's three-shape
detection regex had no automated coverage.  These tests catch documentation drift
(text-pin) and regex logic errors (executable classification).

The executable classification test extracts the regex *from* the SKILL.md text so
that the doc-pin and logic-pin cannot drift apart silently.
"""
from pathlib import Path

# Mirrors test_checkpoint.sh:150 — pin the source copy, not the deployed ~/.claude copy.
REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"


def _text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T-01 — doc-pin assertions
# ---------------------------------------------------------------------------

class TestFilenameFormatDocumented:
    """Verify the SKILL.md documents the timestamped filename format and derivation."""

    def test_filename_template_documented(self):
        """Literal filename template must appear in SKILL.md."""
        assert "<YYYY-MM-DD>T<HHMM>-<task-name>.md" in _text(), (
            "checkpoint/SKILL.md must document the timestamped filename template "
            "'<YYYY-MM-DD>T<HHMM>-<task-name>.md'. "
            "Failure means the format was removed or renamed without updating tests."
        )

    def test_utc_derivation_documented(self):
        """Both the %H%M format token and the single-epoch snippet must be present.

        The single-epoch form (_now=$(date -u +%Y-%m-%dT%H%M)) prevents date/time
        rollover skew at midnight UTC — pinning it ensures the anti-rollover rule
        is not silently dropped from the spec.
        """
        text = _text()
        assert "+%H%M" in text, (
            "checkpoint/SKILL.md must document '+%H%M' as the UTC minute token used "
            "to derive the <HHMM> segment of the checkpoint filename."
        )
        assert "date -u +%Y-%m-%dT%H%M" in text, (
            "checkpoint/SKILL.md must document the single-epoch derivation snippet "
            "'date -u +%Y-%m-%dT%H%M' to prevent date/time rollover skew at midnight UTC."
        )

    # IVG-162 T-07 retired test_three_shapes_enumerated and test_detection_regex_documented:
    # the picker-display "YYYY-MM-DD HH:MM UTC" / "(legacy)" / "(precompact)" three-shape
    # distinction, and the POSIX detection regex that drove it, lived exclusively in the
    # deleted "Saved-time extraction" doc inside `#### Fallback picker`. checkpoint_picker.py
    # (the sole restore-decision path now) does NOT reproduce this three-shape distinction —
    # it uniformly formats every candidate's `saved_time` from mtime via a single
    # `time.strftime("%Y-%m-%d %H:%M UTC", ...)` call (core/scripts/checkpoint_picker.py),
    # so the shape-sniffing logic these tests guarded is a retired feature of the deleted
    # prose, not a surviving behavior with a module-boundary equivalent to re-target at.


# ---------------------------------------------------------------------------
# T-02 — executable three-shape classification
#
# Retired (IVG-162 T-07): this class extracted its regex from the SKILL.md
# "Saved-time extraction" doc (now deleted with the rest of `#### Fallback
# picker`) and classified filenames against it. checkpoint_picker.py — the
# sole restore-decision path now — does not reproduce this three-shape
# distinction at all (it uniformly formats every candidate's `saved_time`
# from mtime; see core/scripts/checkpoint_picker.py's
# `time.strftime("%Y-%m-%d %H:%M UTC", ...)` call). Re-targeting this class at
# the module's `_filename_task` regex (`^\d{4}-\d{2}-\d{2}(T\d{2}:?\d{2})?-`)
# would test a DIFFERENT, non-equivalent pattern (task-name stripping, not
# shape classification) — that would misrepresent what is actually verified,
# so the class is retired rather than reattached to an unrelated regex.
# ---------------------------------------------------------------------------
