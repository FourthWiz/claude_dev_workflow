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


# Matches: mv -f "$dash_tab_tmp" "${dash_tab_tmp}.kdl"
# Whitespace-tolerant; dollar signs and braces are literal in the shell assignment.
_DASH_KDL_MV = re.compile(r'mv\s+-f\s+"\$dash_tab_tmp"\s+"\$\{dash_tab_tmp\}\.kdl"')

# Matches: dash_tab_tmp="${dash_tab_tmp}.kdl"
_DASH_KDL_REASSIGN = re.compile(r'dash_tab_tmp="\$\{dash_tab_tmp\}\.kdl"')


def test_agentdesk_dash_layout_kdl_extension() -> None:
    """The dashboard layout temp file must be renamed to .kdl after mktemp.

    Zellij requires the .kdl extension to identify a file as a layout definition.
    Without the rename, Zellij silently falls back to its default single-pane layout
    (the IVG-88 follow-up bug: PR #160 fixed the BSD mktemp collision but missed
    adding the .kdl rename for the T-05 dashboard block).

    This test asserts that BOTH the mv rename and the variable reassignment are
    present on non-comment lines in the T-05 dashboard layout block.
    """
    assert AGENTDESK_ZSH.exists(), f"agentdesk.zsh not found at {AGENTDESK_ZSH}"

    lines = AGENTDESK_ZSH.read_text().splitlines()

    mv_found = False
    reassign_found = False
    for raw in lines:
        stripped = raw.lstrip()
        if stripped.startswith("#"):
            continue
        if _DASH_KDL_MV.search(raw):
            mv_found = True
        if _DASH_KDL_REASSIGN.search(raw):
            reassign_found = True

    assert mv_found, (
        "agentdesk.zsh is missing the .kdl rename for the dashboard layout temp file.\n"
        "Expected a non-comment line matching: mv -f \"$dash_tab_tmp\" \"${dash_tab_tmp}.kdl\"\n"
        "Zellij requires the .kdl extension; dropping the rename reverts to the default "
        "single-pane layout (IVG-88 follow-up bug)."
    )
    assert reassign_found, (
        "agentdesk.zsh is missing the variable reassignment after the .kdl rename.\n"
        "Expected a non-comment line matching: dash_tab_tmp=\"${dash_tab_tmp}.kdl\"\n"
        "Without the reassignment, subsequent references to dash_tab_tmp point to the "
        "old (non-.kdl) path, breaking the trap cleanup and sed write target."
    )
