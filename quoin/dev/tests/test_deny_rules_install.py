"""Unit tests for rm -rf deny-rules installation via deploy_hooks().

These tests run in CI (no `claude` or `npx` dependency). They verify that
`quoin install` writes the 4 rm-rf/rm-fr deny rules idempotently into
~/.claude/settings.json's permissions.deny list.
"""
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
QUOIN_SRC = REPO_ROOT / "quoin"

from quoin.installer import deploy_hooks  # noqa: E402

_EXPECTED_DENY_RULES = [
    "Bash(rm -rf:*)",
    "Bash(rm -rf *)",
    "Bash(rm -fr:*)",
    "Bash(rm -fr *)",
]


class TestDenyRulesInstall:
    """Deny-rules injection via deploy_hooks — no claude binary required."""

    def test_deny_rules_written_on_fresh_install(self, tmp_path):
        """deploy_hooks writes 4 rm-rf deny rules to a fresh settings.json."""
        dest = tmp_path / ".claude"
        dest.mkdir()
        deploy_hooks(QUOIN_SRC, dest)
        settings = json.loads((dest / "settings.json").read_text())
        deny = settings.get("permissions", {}).get("deny", [])
        for rule in _EXPECTED_DENY_RULES:
            assert rule in deny, f"Expected deny rule missing: {rule}"

    def test_deny_rules_idempotent_on_reinstall(self, tmp_path):
        """Running deploy_hooks twice does not duplicate deny rules."""
        dest = tmp_path / ".claude"
        dest.mkdir()
        deploy_hooks(QUOIN_SRC, dest)
        deploy_hooks(QUOIN_SRC, dest)
        settings = json.loads((dest / "settings.json").read_text())
        deny = settings.get("permissions", {}).get("deny", [])
        assert len(deny) == len(_EXPECTED_DENY_RULES), (
            f"Expected exactly {len(_EXPECTED_DENY_RULES)} deny entries after "
            f"two installs, got {len(deny)}: {deny}"
        )

    def test_deny_rules_preserved_alongside_user_rules(self, tmp_path):
        """User-defined allow/deny entries survive the quoin deny-rules merge."""
        dest = tmp_path / ".claude"
        dest.mkdir()
        existing = {
            "permissions": {
                "allow": ["Bash(git:*)"],
                "deny": ["Bash(curl:*)"],
            }
        }
        (dest / "settings.json").write_text(json.dumps(existing))
        deploy_hooks(QUOIN_SRC, dest)
        settings = json.loads((dest / "settings.json").read_text())
        allow = settings.get("permissions", {}).get("allow", [])
        deny = settings.get("permissions", {}).get("deny", [])
        assert "Bash(git:*)" in allow, "User allow rule was removed"
        assert "Bash(curl:*)" in deny, "User deny rule was removed"
        for rule in _EXPECTED_DENY_RULES:
            assert rule in deny, f"Quoin deny rule missing: {rule}"
