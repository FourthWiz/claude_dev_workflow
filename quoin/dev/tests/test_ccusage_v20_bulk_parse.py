"""Regression test: IVG-58 — ccusage v20 bulk format parsing documented in SKILL.md files.

ccusage v20+ changed the bulk call response format:
  OLD (v18): bare array or {"sessions": [...]} with "sessionId" per element
  NEW (v20): {"session": [...], "totals": {...}} with "period" per element (UUID in "period")

Both cost_snapshot and end_of_task SKILL.md files must document the v20 shape
so Claude parses bulk responses correctly.
"""
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

COST_SNAPSHOT = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "cost_snapshot" / "SKILL.md"
END_OF_TASK = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "end_of_task" / "SKILL.md"


@pytest.fixture
def cost_snapshot_text():
    assert COST_SNAPSHOT.exists(), f"Missing: {COST_SNAPSHOT}"
    return COST_SNAPSHOT.read_text(encoding="utf-8")


@pytest.fixture
def end_of_task_text():
    assert END_OF_TASK.exists(), f"Missing: {END_OF_TASK}"
    return END_OF_TASK.read_text(encoding="utf-8")


class TestCostSnapshotV20Parse:
    """cost_snapshot bulk parse format — IVG-58."""

    def test_v20_session_wrapper_key_documented(self, cost_snapshot_text):
        """Step 2 must document the v20 top-level 'session' wrapper key."""
        assert '"session"' in cost_snapshot_text or "'session'" in cost_snapshot_text, (
            "cost_snapshot/SKILL.md Step 2 must document the ccusage v20 top-level "
            "'session' wrapper key in bulk responses."
        )

    def test_v20_period_field_documented(self, cost_snapshot_text):
        """Step 2 must document that UUIDs are in the 'period' field in v20."""
        assert '"period"' in cost_snapshot_text or "'period'" in cost_snapshot_text, (
            "cost_snapshot/SKILL.md Step 2 must document the ccusage v20 'period' "
            "field (UUID location in bulk responses)."
        )

    def test_v18_sessionid_fallback_retained(self, cost_snapshot_text):
        """Step 2 must retain the v18 sessionId fallback path."""
        assert "sessionId" in cost_snapshot_text, (
            "cost_snapshot/SKILL.md Step 2 must retain 'sessionId' for backward "
            "compatibility with ccusage v18 per-UUID responses."
        )

    def test_version_detection_logic_present(self, cost_snapshot_text):
        """Step 2 must describe a version-detection approach (v20 vs v18)."""
        has_version_detect = (
            "v20" in cost_snapshot_text
            or "Version-detection" in cost_snapshot_text
            or "version-detection" in cost_snapshot_text
        )
        assert has_version_detect, (
            "cost_snapshot/SKILL.md Step 2 must include version-detection logic "
            "for distinguishing ccusage v20 from v18 bulk response shapes."
        )


class TestEndOfTaskV20Parse:
    """end_of_task bulk parse format — IVG-58."""

    def test_v20_session_wrapper_key_documented(self, end_of_task_text):
        """Sub-phase B Step 4 must document the v20 'session' wrapper key."""
        assert '"session"' in end_of_task_text or "'session'" in end_of_task_text, (
            "end_of_task/SKILL.md Sub-phase B Step 4 must document the ccusage v20 "
            "top-level 'session' wrapper key in bulk responses."
        )

    def test_v20_period_field_documented(self, end_of_task_text):
        """Sub-phase B Step 4 must document the 'period' field for UUIDs."""
        assert '"period"' in end_of_task_text or "'period'" in end_of_task_text, (
            "end_of_task/SKILL.md Sub-phase B Step 4 must document the ccusage v20 "
            "'period' field."
        )

    def test_v18_sessionid_fallback_retained(self, end_of_task_text):
        """Sub-phase B Step 4 must retain the v18 sessionId fallback path."""
        assert "sessionId" in end_of_task_text, (
            "end_of_task/SKILL.md Sub-phase B Step 4 must retain 'sessionId' for "
            "backward compatibility with v18."
        )
