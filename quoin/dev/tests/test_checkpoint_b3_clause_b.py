"""Regression test: IVG-57 — checkpoint B3 Clause B uses max(ALL candidate mtimes).

When precompact.sh writes a checkpoint file but no sentinel (because skills are active),
the disk-only checkpoint must not be bypassed by B3 Clause B. The fix changes the mtime
reference from max(sentinel candidate mtimes) to max(ALL candidate mtimes).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "skills" / "checkpoint" / "SKILL.md"


def _text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    return CHECKPOINT_SKILL.read_text(encoding="utf-8")


class TestCheckpointB3ClauseB:
    """B3 Clause B mtime reference fix — IVG-57."""

    def test_clause_b_does_not_use_sentinel_only_mtime(self):
        """Clause B must NOT reference 'sentinel candidate mtimes' (old, broken wording)."""
        text = _text()
        assert "max(sentinel candidate mtimes)" not in text, (
            "checkpoint/SKILL.md B3 Clause B still uses 'max(sentinel candidate mtimes)'. "
            "Fix IVG-57: change to 'max(ALL candidate mtimes)' so disk-only checkpoints "
            "are included in the mtime comparison."
        )

    def test_clause_b_uses_all_candidate_mtimes(self):
        """Clause B must use 'max(ALL candidate mtimes)' (fixed wording)."""
        text = _text()
        assert "max(ALL candidate mtimes)" in text, (
            "checkpoint/SKILL.md B3 Clause B must use 'max(ALL candidate mtimes)' "
            "(IVG-57 fix). Current text does not contain this string."
        )

    def test_clause_b_mentions_disk_only(self):
        """Clause B explanation must mention 'disk-only' candidates."""
        text = _text()
        # Extract the region around Clause B for a focused check
        idx = text.find("Clause B")
        assert idx != -1, "checkpoint/SKILL.md missing 'Clause B' entirely"
        # Check within 500 chars after the first Clause B occurrence
        region = text[idx : idx + 500]
        assert "disk-only" in region, (
            "checkpoint/SKILL.md B3 Clause B explanation must mention 'disk-only' "
            "to document why ALL candidates are used (IVG-57)."
        )
