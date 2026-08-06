"""Tests for IVG-246 `run/SKILL.md` fast-path-triage prose (T-05 onward).

T-05 covers `fast:` tag parsing: the token must be documented as stripped in
the same "Parse input and determine task profile" block as `strict:` /
`small:`/`medium:`/`large:` / `max_rounds:`, ORTHOGONAL to (composable with)
the profile tags, and stripped before the derived task name — the same
non-pollution treatment already given to `--autonomous` and `strict:`.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/
_SOURCE_ROOT = _REPO_ROOT / "quoin"
_RUN_SKILL = _SOURCE_ROOT / "adapters" / "claude" / "skills" / "run" / "SKILL.md"


@pytest.fixture(scope="module")
def run_skill_text() -> str:
    assert _RUN_SKILL.exists(), f"run/SKILL.md not found at {_RUN_SKILL}"
    return _RUN_SKILL.read_text(encoding="utf-8")


def _parse_block(text: str) -> str:
    start = text.index("### Parse input and determine task profile")
    end = text.index("### Determine task name", start)
    return text[start:end]


def test_fast_tag_stripping(run_skill_text: str) -> None:
    block = _parse_block(run_skill_text)

    assert "`fast:`" in block, (
        "the 'fast:' tag must be documented in the same "
        "'Parse input and determine task profile' block as strict:/small:/"
        "medium:/large:/max_rounds:"
    )
    # It's documented alongside the other stripped tokens in this same block.
    assert "`strict:`" in block
    assert "`small:`" in block
    assert "`max_rounds:" in block

    # Explicitly stripped before profile classification / task-name
    # derivation — same non-pollution treatment as --autonomous / strict:.
    assert "Strip the token" in block or "Strip token" in block
    assert "task name" in block.lower(), (
        "the block must document that 'fast:' does not reach the derived "
        "task name (AC-3)"
    )

    # Orthogonal / composable with profile tags — not mutually exclusive.
    assert "ORTHOGONAL" in block or "orthogonal" in block


def test_fast_tag_composable_with_profile_example(run_skill_text: str) -> None:
    """The block must give a concrete composability example (a `fast:` +
    profile-tag combination) showing the profile tag still wins for
    profile purposes while `fast:` independently forces route evaluation."""
    block = _parse_block(run_skill_text)
    assert "fast: large:" in block or "fast:` `large:`" in block or (
        "fast:" in block and "large:" in block and "route" in block.lower()
    )
