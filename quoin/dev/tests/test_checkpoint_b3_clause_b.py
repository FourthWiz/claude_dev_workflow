"""Regression test: IVG-57 — checkpoint B3 Clause B uses max(ALL candidate mtimes).

When precompact.sh writes a checkpoint file but no sentinel (because skills are active),
the disk-only checkpoint must not be bypassed by B3 Clause B. The fix changes the mtime
reference from max(sentinel candidate mtimes) to max(ALL candidate mtimes).
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"


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

    # IVG-162 T-07 retired test_clause_b_uses_all_candidate_mtimes and
    # test_clause_b_mentions_disk_only: the "Clause B: ... max(ALL candidate mtimes)"
    # prose they pinned lived exclusively in the deleted "B3 session-state fallback"
    # trigger description inside `#### Fallback picker`. checkpoint_picker.py now
    # implements Clause B directly; module-boundary correctness (including the
    # disk-only-candidate inclusion this IVG-57 fix targeted) is verified by
    # test_b3_clause_b_all_candidates_older_than_freshest_session in
    # test_checkpoint_picker_roundtrip.py.
