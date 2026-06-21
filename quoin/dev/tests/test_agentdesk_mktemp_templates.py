"""T-03 (IVG-88): Regression guard — no mktemp template has chars after XXXXXX.

On macOS (BSD mktemp), only *trailing* X's are randomized.  A suffix after the
X's (e.g. ".kdl") defeats randomization and creates the same literal path on
every call, causing "File exists" on the second run.  This test asserts that
every mktemp invocation in agentdesk.zsh ends its XXXXXX run immediately with
a closing quote — no hidden suffix.

Comment lines are explicitly excluded: a comment may mention the XXXXXX pattern
in explanatory text without constituting a broken template.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTDESK_ZSH = REPO_ROOT / "quoin" / "tools" / "agentdesk" / "agentdesk.zsh"

# Matches a mktemp template where XXXXXX is NOT the last char before the closing quote.
# Flags: `mktemp` on the line, then somewhere XXXXXX followed by a non-X, non-quote char.
_BROKEN_TEMPLATE = re.compile(r'XXXXXX[^X"]')


def test_no_mktemp_suffix_after_x_run() -> None:
    """Every mktemp call in agentdesk.zsh must have XXXXXX as the trailing part of its template."""
    assert AGENTDESK_ZSH.exists(), f"agentdesk.zsh not found at {AGENTDESK_ZSH}"

    violations: list[str] = []
    for lineno, raw in enumerate(AGENTDESK_ZSH.read_text().splitlines(), start=1):
        # Skip comment lines — they may mention XXXXXX in explanatory text.
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue
        if "mktemp" not in raw:
            continue
        if _BROKEN_TEMPLATE.search(raw):
            violations.append(f"  line {lineno}: {raw.rstrip()}")

    assert not violations, (
        "agentdesk.zsh has mktemp template(s) with chars after XXXXXX — "
        "on macOS BSD mktemp these suffixes defeat randomization and cause "
        "'File exists' collisions on the second call:\n" + "\n".join(violations)
    )
