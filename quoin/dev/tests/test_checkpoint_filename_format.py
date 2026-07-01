"""Test pins for the checkpoint timestamped filename format and three-shape picker detection.

IVG-48 follow-up from checkpoint-timestamp-session-link review-1 MINOR-2 / R-02:
the new <YYYY-MM-DD>T<HHMM>-<task-name>.md format and the picker's three-shape
detection regex had no automated coverage.  These tests catch documentation drift
(text-pin) and regex logic errors (executable classification).

The executable classification test extracts the regex *from* the SKILL.md text so
that the doc-pin and logic-pin cannot drift apart silently.
"""
import re
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

    def test_three_shapes_enumerated(self):
        """All three picker display strings must be present in SKILL.md."""
        text = _text()
        assert "YYYY-MM-DD HH:MM UTC" in text, (
            "checkpoint/SKILL.md picker must document 'YYYY-MM-DD HH:MM UTC' as the "
            "display format for timestamped checkpoints."
        )
        assert "(legacy)" in text, (
            "checkpoint/SKILL.md picker must document '(legacy)' as the display label "
            "for non-timestamped legacy checkpoints."
        )
        assert "(precompact)" in text, (
            "checkpoint/SKILL.md picker must document '(precompact)' as the display "
            "label for precompact-hook checkpoints."
        )

    def test_detection_regex_documented(self):
        """The POSIX detection regex must be present verbatim in SKILL.md."""
        assert "^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{4}-" in _text(), (
            "checkpoint/SKILL.md must document the detection regex "
            "'^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{4}-' for classifying timestamped "
            "checkpoint filenames. Failure means the regex was removed or changed."
        )


# ---------------------------------------------------------------------------
# T-02 — executable three-shape classification
# ---------------------------------------------------------------------------

def _build_pattern():
    """Extract and compile the detection regex directly from SKILL.md.

    By extracting from the doc rather than hardcoding, the executable test
    cannot drift from the specification silently — if the SKILL.md regex
    changes, the compiled pattern changes too, and the classification
    assertions re-validate the updated regex against representative filenames.
    """
    text = _text()
    # The exact string as it appears in SKILL.md (escaped for re.search):
    match = re.search(r"\^\[0-9\]\{4\}-\[0-9\]\{2\}-\[0-9\]\{2\}T\[0-9\]\{4\}-", text)
    assert match is not None, (
        "Could not extract the detection regex from checkpoint/SKILL.md. "
        "The regex '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{4}-' may have drifted. "
        "Update this test's extraction pattern to match the new SKILL.md regex."
    )
    return re.compile(match.group(0))


# Build once at module scope — avoids re-parsing on every parameterised call.
_PAT = None


def _pat():
    global _PAT
    if _PAT is None:
        _PAT = _build_pattern()
    return _PAT


def is_timestamped(basename: str) -> bool:
    """True iff the basename matches the new timestamped form per SKILL.md detection regex."""
    return _pat().match(basename) is not None


def is_precompact(basename: str) -> bool:
    """True iff the basename (before .md) ends with '-precompact'.

    Per SKILL.md line 690: the -precompact suffix is detected separately on the
    basename *before* extension stripping.
    """
    return basename[:-3].endswith("-precompact")


class TestThreeShapeClassification:
    """Verify the extracted regex correctly classifies all three filename shapes."""

    def test_classify_three_shapes(self):
        """Representative filename for each shape must classify correctly."""
        cases = [
            # (basename, expect_timestamped, expect_precompact)
            ("2026-05-30T1423-my-task.md",          True,  False),
            ("2026-05-30-my-task.md",                False, False),
            ("2026-05-30-my-task-precompact.md",     False, True),
        ]
        for basename, want_ts, want_pc in cases:
            assert is_timestamped(basename) == want_ts, (
                f"{basename!r}: expected is_timestamped={want_ts}, "
                f"got {is_timestamped(basename)}"
            )
            assert is_precompact(basename) == want_pc, (
                f"{basename!r}: expected is_precompact={want_pc}, "
                f"got {is_precompact(basename)}"
            )

    def test_classify_negative_cases(self):
        """Malformed basenames must NOT match as timestamped."""
        negative_cases = [
            # (basename, description)
            ("2026-05-30T142-my-task.md",         "only 3 time digits"),
            ("2026-05-30T14235-my-task.md",        "5-digit time: trailing '-' in regex requires exactly 4"),
            ("26-05-30T1423-my-task.md",           "2-digit year"),
            ("2026-5-30T1423-my-task.md",          "1-digit month"),
            ("2026-05-30-T1423-task.md",           "hyphen before T — '-T' does not match 'T[0-9]{4}'"),
            ("something-2026-05-30T1423-task.md",  "prefix junk — ^ anchor fails"),
        ]
        for basename, desc in negative_cases:
            assert not is_timestamped(basename), (
                f"{basename!r} ({desc}) should NOT match as timestamped. "
                f"Regex: '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}T[0-9]{{4}}-'"
            )

    def test_regex_requires_exactly_four_time_digits(self):
        """The trailing '-' in the regex means exactly 4 time digits are required.

        '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{4}-' ends with a literal '-', so
        re.match() requires that character to appear immediately after the 4th time
        digit.  A 5th digit occupies that position, causing the match to fail.
        This is the correct strictness — only valid HHMM-formatted names match.
        """
        assert not is_timestamped("2026-05-30T14235-my-task.md"), (
            "A 5-digit time segment 'T14235' must NOT match: the trailing '-' in the "
            "detection regex ('^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{4}-') requires the "
            "character after the 4th time digit to be '-', so a 5th digit fails."
        )
