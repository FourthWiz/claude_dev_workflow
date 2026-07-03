"""Tests for IVG-106 T-07: installer wiring for discovery_staleness.py + discovery-refresh-routine.md.

Mirrors test_install_session_age_guard_deployed.py pattern.
"""
from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/
_INSTALLER = _REPO_ROOT / "src" / "quoin" / "installer.py"


def _parse_tuple(node: ast.Assign, name: str) -> list[str]:
    """Extract a tuple of string constants from an assignment node."""
    for target in node.targets:
        if isinstance(target, ast.Name) and target.id == name:
            if isinstance(node.value, ast.Tuple):
                return [
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
    return []


def _get_list(name: str) -> list[str]:
    source = _INSTALLER.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            result = _parse_tuple(node, name)
            if result:
                return result
    return []


def test_discovery_staleness_in_deployed_scripts() -> None:
    """discovery_staleness.py (wrapper) must be in DEPLOYED_SCRIPTS."""
    deployed = _get_list("DEPLOYED_SCRIPTS")
    assert "discovery_staleness.py" in deployed, (
        "'discovery_staleness.py' not found in DEPLOYED_SCRIPTS in installer.py"
    )


def test_discovery_staleness_in_core_scripts() -> None:
    """discovery_staleness.py (core impl) must be in CORE_SCRIPTS."""
    core = _get_list("CORE_SCRIPTS")
    assert "discovery_staleness.py" in core, (
        "'discovery_staleness.py' not found in CORE_SCRIPTS in installer.py — "
        "the wrapper's parents[1]/core/scripts/ resolution will fail at runtime"
    )


def test_discovery_refresh_routine_in_tier1_memory_files() -> None:
    """discovery-refresh-routine.md must be in TIER1_MEMORY_FILES."""
    tier1 = _get_list("TIER1_MEMORY_FILES")
    assert "discovery-refresh-routine.md" in tier1, (
        "'discovery-refresh-routine.md' not found in TIER1_MEMORY_FILES in installer.py"
    )
