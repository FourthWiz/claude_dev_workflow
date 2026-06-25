"""Regression guard: source quoin/CLAUDE.md must stay below the Claude Code 40k
warning threshold. Deploy overhead model (measured claude-md-trim 2026-06-25):
  deploy overhead = substitution(+5/placeholder × 17 sites = +85)
                  + marker frame(+56)
                  + variable user pre-marker block (budget 700 — current measured
                    474 chars for Python venv + open-model routing blocks; ~226
                    headroom; 700 chosen as deliberate over-budget for user-owned
                    variable content)
SOURCE_CEILING = 38500 chosen so that:
  SOURCE_CEILING + sub_delta(85) + frame(56) + PRE_MARKER_BUDGET(700) = 39341 < 40000
  giving a 659-char hard margin even on worst-case pre-marker growth.
Current trimmed source ~35011 chars leaves ample headroom for future growth."""
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "CLAUDE.md"
# Source ceiling lowered from 39300 → 38500 (claude-md-trim 2026-06-25: Tier-1
# catalog extracted into quoin/memory/tier1-files.md; source dropped from 39297
# to ~35011 chars).  Ceiling set to 38500 so the deploy-projection assertion
# below guards the actual 40000 threshold independently of this source guard.
SOURCE_CEILING = 38500

# Deployed-projection constants (environment-independent: fixed home-path stand-in,
# not os.path.expanduser — keeps the projection a true upper-bound guard regardless
# of which machine runs the test).
HOME_STANDIN = "/Users/ivgo/.claude"   # 19 chars; sub delta = (19 - 14) * 17 = +85
MARKER_FRAME = 56      # measured: opening + closing install-sh marker lines
PRE_MARKER_BUDGET = 700  # deliberately over-budgets user-owned variable pre-marker
                          # block (current measured: 474 chars; ~226 slack intentional)
PLACEHOLDER = "__QUOIN_HOME__"
DEPLOYED_CEILING = 40_000


def test_source_claude_md_below_size_ceiling():
    size = len(SOURCE.read_text(encoding="utf-8"))
    assert size <= SOURCE_CEILING, (
        f"quoin/CLAUDE.md is {size} chars; ceiling is {SOURCE_CEILING}. "
        "Re-extract verbose sections into quoin/memory/ pointer files."
    )


def test_deployed_projection_below_40k():
    """Simulate install.sh substitution and assert the deployed file stays < 40000.

    PRE_MARKER_BUDGET=700 deliberately over-budgets the user-owned variable
    pre-marker block (current measured: 474 chars for the Python venv + open-model
    routing blocks); the +226 slack is intentional headroom for user growth.
    HOME_STANDIN is fixed (not expanduser) to keep the projection
    environment-independent and a true upper-bound guard.
    """
    source_text = SOURCE.read_text(encoding="utf-8")
    substituted = source_text.replace(PLACEHOLDER, HOME_STANDIN)
    projected = PRE_MARKER_BUDGET + MARKER_FRAME + len(substituted)
    assert projected < DEPLOYED_CEILING, (
        f"Projected deployed size is {projected} chars "
        f"(source {len(source_text)} + sub_delta "
        f"{len(substituted) - len(source_text)} + frame {MARKER_FRAME} + "
        f"pre_marker_budget {PRE_MARKER_BUDGET}); "
        f"ceiling is {DEPLOYED_CEILING}. "
        "Re-extract more sections from quoin/CLAUDE.md or increase HOME_STANDIN budget."
    )
