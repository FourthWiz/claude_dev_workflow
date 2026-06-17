"""Regression guard: source quoin/CLAUDE.md must stay below the Claude Code 40k
warning threshold. Deploy overhead is ~600 chars (measured 2026-05-15: source 42357,
deployed 42961 = +604 chars from marker frame + __QUOIN_HOME__ substitution at ~30 sites).
Source ceiling 39300 leaves ~700-char margin before the 40000 deployed threshold (39300 + 600 = 39900 < 40000).
Ceiling bumped from 39000 → 39300 on 2026-06-17 (IVG-77: added branch-recovery.md pointer
sentence to the 'enforced at three layers' paragraph; ~163 char addition; safe margin preserved)."""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "CLAUDE.md"
# Source ceiling: 39300 chars. Deploy adds ~600 chars overhead (measured 2026-05-15).
# At source=39300, deployed=~39900, safely under the 40000 Claude Code warning threshold.
# Bumped from 39000 → 39300 on 2026-06-17 (IVG-77: branch-recovery.md pointer added).
SOURCE_CEILING = 39300


def test_source_claude_md_below_size_ceiling():
    size = len(SOURCE.read_text(encoding="utf-8"))
    assert size <= SOURCE_CEILING, (
        f"quoin/CLAUDE.md is {size} chars; ceiling is {SOURCE_CEILING}. "
        "Re-extract verbose sections into quoin/memory/ pointer files."
    )
