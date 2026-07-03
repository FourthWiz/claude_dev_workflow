"""Python contract tests for sessionstart.sh S-5 discovery-staleness step (IVG-106 T-02)."""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/
_HOOK = _REPO_ROOT / "quoin" / "hooks" / "sessionstart.sh"


def _hook_text() -> str:
    return _HOOK.read_text(encoding="utf-8")


def test_hook_contains_s5_label() -> None:
    assert "S-5" in _hook_text(), "sessionstart.sh must contain 'S-5' label"


def test_hook_references_discovery_staleness_script() -> None:
    text = _hook_text()
    assert "discovery_staleness" in text, (
        "sessionstart.sh must reference discovery_staleness script"
    )


def test_hook_uses_hook_relative_path() -> None:
    text = _hook_text()
    assert '$(dirname "$0")' in text, (
        "sessionstart.sh must use $(dirname \"$0\") for hook-relative path"
    )
    assert "../scripts/discovery_staleness.py" in text, (
        "sessionstart.sh must reference ../scripts/discovery_staleness.py"
    )


def test_hook_checks_disable_knob() -> None:
    text = _hook_text()
    assert "QUOIN_DISCOVERY_REFRESH_DISABLE" in text, (
        "sessionstart.sh must propagate QUOIN_DISCOVERY_REFRESH_DISABLE to child"
    )


def test_hook_has_fail_open_comment() -> None:
    text = _hook_text()
    # Must have some kind of fail-OPEN comment or logic for python absence
    assert "fail-OPEN" in text or "no python" in text.lower() or "fail-open" in text.lower(), (
        "sessionstart.sh S-5 block must document fail-OPEN behavior"
    )


def test_hook_uses_printf_json_pattern() -> None:
    """The banner must use printf '{"hookSpecificOutput"... pattern (not a phantom helper)."""
    text = _hook_text()
    assert 'printf \'{"hookSpecificOutput"' in text, (
        'sessionstart.sh must use printf \'{"hookSpecificOutput"...\' pattern for banner emission'
    )


def test_hook_does_not_use_phantom_helper() -> None:
    """emit_sessionstart_additionalContext must NOT appear (does not exist)."""
    assert "emit_sessionstart_additionalContext" not in _hook_text(), (
        "sessionstart.sh must NOT reference phantom helper emit_sessionstart_additionalContext"
    )


def test_hook_s5_section_has_no_literal_home_claude() -> None:
    """The S-5 block must not contain literal ~/.claude/ paths (doc comments excluded)."""
    text = _hook_text()
    # Find just the S-5 section
    start = text.find("=== S-5 discovery-staleness banner ===")
    end = text.find("=== end S-5 discovery-staleness banner ===")
    if start == -1 or end == -1:
        assert start != -1, "S-5 start marker not found in sessionstart.sh"
    s5_section = text[start:end]
    assert "~/.claude/" not in s5_section, (
        "S-5 section of sessionstart.sh must not contain literal ~/.claude/ paths"
    )
