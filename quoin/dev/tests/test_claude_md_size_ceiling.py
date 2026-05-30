"""Regression guard: source quoin/CLAUDE.md must stay below the Claude Code 40k
warning threshold. Deploy overhead is ~600 chars (measured 2026-05-15: source 42357,
deployed 42961 = +604 chars from marker frame + __QUOIN_HOME__ substitution at ~30 sites).
Source ceiling 39000 leaves 1000-char margin before the 40000 deployed threshold (39000 + 600 = 39600 < 40000)."""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "CLAUDE.md"
# Source ceiling: 39000 chars. Deploy adds ~600 chars overhead (measured 2026-05-15).
# At source=39000, deployed=~39600, safely under the 40000 Claude Code warning threshold.
SOURCE_CEILING = 39000


def test_source_claude_md_below_size_ceiling():
    size = len(SOURCE.read_text(encoding="utf-8"))
    assert size <= SOURCE_CEILING, (
        f"quoin/CLAUDE.md is {size} chars; ceiling is {SOURCE_CEILING}. "
        "Re-extract verbose sections into quoin/memory/ pointer files."
    )
