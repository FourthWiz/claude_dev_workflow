"""IVG-258 stage-4 T-12: a third, deliberately narrower, no-`autonomous`-family
pin for the compact re-entry block in quoin/hooks/sessionstart.sh.

Two layers already exist and are NOT duplicated here:
  - `test_autonomous_hooks_untouched.py:105-116` scans every hook file, whole-file,
    for the literal token `autonomous` only.
  - That same file's `_FORBIDDEN` regex at `:274-285` (`autonomous|unattend|approv|
    silence`, four tokens, case-insensitive) applies only to ADDED lines of
    `git diff <merge-base> HEAD -- quoin/hooks/` — and that diff form goes
    permanently vacuous once this branch merges (the merge-base collapses to
    HEAD, so the diff against it is empty forever).

This file exists as a THIRD layer, scoped only to the text strictly between the
`# === IVG-258 post-compaction re-entry ===` / `# === end IVG-258 post-compaction
re-entry ===` block markers in `quoin/hooks/sessionstart.sh` — a form that keeps
discriminating after merge (unlike the diff-shaped alternative, which was
considered and rejected for exactly that reason). D-07 is the rationale: the
resume-command echo is the one place in this stage a plausible implementation
would write `--autonomous` or a nearby phrase ("an unattended run", "no approval
is needed"). The three pins (shipped whole-file, shipped added-lines, this
block-marker-scoped one) are meant to track each other, not replace one another.

The marker-presence assertion below exists because the block-marker-scoped scan
is vacuous — and passes — if either marker is ever renamed or dropped (an absent
region scans clean). It runs BEFORE the scoped scan so a missing marker fails
loudly instead of silently green-lighting an unscanned file.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SESSIONSTART = REPO_ROOT / "quoin" / "hooks" / "sessionstart.sh"

START_MARKER = "# === IVG-258 post-compaction re-entry ==="
END_MARKER = "# === end IVG-258 post-compaction re-entry ==="

# Same four-token alternation as test_autonomous_hooks_untouched.py's shipped
# _FORBIDDEN regex (:274-285), case-insensitive.
_FORBIDDEN = re.compile(r"autonomous|unattend|approv|silence", re.IGNORECASE)


def _read_sessionstart() -> str:
    assert SESSIONSTART.exists(), f"quoin/hooks/sessionstart.sh not found at {SESSIONSTART}"
    return SESSIONSTART.read_text(encoding="utf-8")


def _extract_block(text: str) -> str:
    start = text.index(START_MARKER) + len(START_MARKER)
    end = text.index(END_MARKER)
    assert start <= end, "IVG-258 block markers are out of order"
    return text[start:end]


def test_both_ivg258_block_markers_present_exactly_once():
    """Checked before the scoped scan runs — a missing/renamed marker must fail
    loudly, not silently pass a scan of an empty or wrong region."""
    text = _read_sessionstart()
    assert text.count(START_MARKER) == 1, (
        f"Expected exactly one '{START_MARKER}' marker in quoin/hooks/sessionstart.sh; "
        f"found {text.count(START_MARKER)}"
    )
    assert text.count(END_MARKER) == 1, (
        f"Expected exactly one '{END_MARKER}' marker in quoin/hooks/sessionstart.sh; "
        f"found {text.count(END_MARKER)}"
    )


def test_no_forbidden_token_between_ivg258_block_markers():
    """The compact re-entry block itself must carry none of the four forbidden
    tokens — this is the file where a plausible implementation would write
    `--autonomous` or a nearby phrase (D-07), so it gets the tightest pin."""
    text = _read_sessionstart()
    block = _extract_block(text)
    match = _FORBIDDEN.search(block)
    assert match is None, (
        f"Forbidden token '{match.group(0) if match else ''}' found inside the "
        "IVG-258 post-compaction re-entry block in quoin/hooks/sessionstart.sh. "
        "D-07: this is the one file where a plausible implementation would write "
        "'--autonomous' or a nearby phrase (unattended/approval/silence) — "
        "rephrase without any of the four forbidden tokens."
    )
