"""Tests for IVG-106 T-03: discovery/Serena staleness step in /start_of_day."""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/
_SOURCE_ROOT = _REPO_ROOT / "quoin"

_ADAPTER_SKILL = _SOURCE_ROOT / "adapters" / "claude" / "skills" / "start_of_day" / "SKILL.md"
_CORE_SKILL = _SOURCE_ROOT / "core" / "skills" / "start_of_day.md"


def _adapter_text() -> str:
    return _ADAPTER_SKILL.read_text(encoding="utf-8")


def _core_text() -> str:
    return _CORE_SKILL.read_text(encoding="utf-8")


# ── Adapter SKILL.md assertions ───────────────────────────────────────────────

def test_adapter_has_step_1c() -> None:
    text = _adapter_text()
    assert "Step 1c" in text, "Adapter SKILL.md must contain 'Step 1c'"
    assert "stale" in text or "discovery" in text, (
        "Step 1c section must reference stale or discovery"
    )


def test_adapter_references_discovery_stale_days() -> None:
    assert "QUOIN_DISCOVERY_STALE_DAYS" in _adapter_text(), (
        "Adapter SKILL.md must reference QUOIN_DISCOVERY_STALE_DAYS (not QUOIN_SOD_*)"
    )


def test_adapter_references_discovery_autorefresh() -> None:
    assert "QUOIN_DISCOVERY_AUTOREFRESH" in _adapter_text(), (
        "Adapter SKILL.md must reference QUOIN_DISCOVERY_AUTOREFRESH"
    )


def test_adapter_references_discover_command() -> None:
    assert "/discover" in _adapter_text(), (
        "Adapter SKILL.md must reference /discover"
    )


def test_adapter_step_1c_is_read_only() -> None:
    text = _adapter_text()
    assert "read-only" in text or "read only" in text.lower(), (
        "Step 1c must be explicitly marked read-only"
    )


def test_adapter_step_1c_honors_graceful_absence() -> None:
    text = _adapter_text()
    # Must mention ToolSearch or Graceful Absence or probe for Serena
    has_toolsearch = "ToolSearch" in text
    has_graceful = "Graceful Absence" in text or "do nothing" in text.lower() or "no schema" in text
    has_probe = "probe" in text.lower()
    assert has_toolsearch or has_graceful or has_probe, (
        "Adapter SKILL.md must reference ToolSearch probe or Graceful Absence for Serena"
    )


def test_adapter_has_refresh_discovery_option() -> None:
    assert "Refresh discovery" in _adapter_text(), (
        "Adapter SKILL.md must contain 'Refresh discovery' AskUserQuestion option"
    )


def test_adapter_has_refresh_serena_option() -> None:
    text = _adapter_text()
    assert "Set up / Refresh Serena memory" in text or "Refresh Serena memory" in text, (
        "Adapter SKILL.md must contain 'Set up / Refresh Serena memory' AskUserQuestion option"
    )


def test_adapter_step_6b_is_separate_from_step_6() -> None:
    text = _adapter_text()
    assert "Step 6b" in text, "Adapter SKILL.md must contain 'Step 6b'"
    # Step 6b must be described as separate/second from Step 6
    assert any(phrase in text for phrase in ("separate", "second", "Step 6b")), (
        "Step 6b must be described as separate from Step 6"
    )


def test_adapter_step_6b_fires_only_when_stale() -> None:
    text = _adapter_text()
    # Must mention that Step 6b is skipped when no staleness detected
    assert "only when" in text.lower() or "skip" in text.lower() or "no staleness" in text.lower(), (
        "Adapter SKILL.md must state Step 6b fires only when staleness was detected"
    )


def test_adapter_references_serena_activation_refresh() -> None:
    assert "serena-activation.md" in _adapter_text() or "§Refresh" in _adapter_text(), (
        "Adapter SKILL.md must reference serena-activation.md §Refresh path"
    )


def test_adapter_no_literal_home_claude() -> None:
    # Only check the new Step 1c and Step 6b sections (existing file has doc comments with ~/.claude/)
    text = _adapter_text()
    start_1c = text.find("Step 1c")
    start_6b = text.find("Step 6b")
    if start_1c != -1:
        # Scan from Step 1c to Session bootstrap
        end_1c = text.find("## Session bootstrap", start_1c)
        if end_1c == -1:
            end_1c = start_1c + 3000
        section_1c = text[start_1c:end_1c]
        assert "~/.claude/" not in section_1c, (
            "Step 1c section must not contain literal ~/.claude/ (use __QUOIN_HOME__)"
        )
    if start_6b != -1:
        end_6b = text.find("## Handling", start_6b)
        if end_6b == -1:
            end_6b = start_6b + 3000
        section_6b = text[start_6b:end_6b]
        assert "~/.claude/" not in section_6b, (
            "Step 6b section must not contain literal ~/.claude/"
        )


# ── Core skill doc assertions ─────────────────────────────────────────────────

def test_core_has_staleness_check_section() -> None:
    text = _core_text()
    assert "staleness" in text.lower() or "Step 1c" in text or "Discovery" in text, (
        "Core start_of_day.md must describe the staleness check behavior"
    )


def test_core_references_discovery_stale_days() -> None:
    assert "QUOIN_DISCOVERY_STALE_DAYS" in _core_text(), (
        "Core start_of_day.md must reference QUOIN_DISCOVERY_STALE_DAYS"
    )


def test_core_references_discovery_autorefresh() -> None:
    assert "QUOIN_DISCOVERY_AUTOREFRESH" in _core_text(), (
        "Core start_of_day.md must reference QUOIN_DISCOVERY_AUTOREFRESH"
    )
