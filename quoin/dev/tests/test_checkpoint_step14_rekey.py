"""Text-structural guard over `/checkpoint` Step 1.4's two-arm re-key — IVG-258 S-6, T-08.

Step 1.4's compact-already-ran skip check used to require BOTH sentinels
(`compact-happened-*` AND `pending-restore-*`). It now also skips when the
`compact-happened-*` sentinel exists, `pending-restore-*` is absent, AND
`run_state_probe` (`hooks/_lib.sh`) confirms no active run-state record
exists project-wide (Arm B). This is a text-structural check over the
Step 1.4 slice — it can prove the source line is present and ordered
correctly, not that sourcing actually succeeds at runtime or that the
function is defined by the sourced file; `test_stage6_checkpoint_probe_wiring_canary.sh`
Case B is the executable canary that proves the latter (T-12 states this
division of coverage explicitly).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/
CHECKPOINT_SKILL = PKG_DIR / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"

SLICE_START = "### Step 1.4"
SLICE_END = "### Step 1.45"


@pytest.fixture(scope="module")
def slice_text() -> str:
    assert CHECKPOINT_SKILL.exists(), f"checkpoint/SKILL.md not found at {CHECKPOINT_SKILL}"
    text = CHECKPOINT_SKILL.read_text(encoding="utf-8")
    start = text.index(SLICE_START)
    end = text.index(SLICE_END, start)
    return text[start:end]


# (a) the slice names run_state_probe
def test_slice_names_run_state_probe(slice_text: str) -> None:
    assert "run_state_probe" in slice_text


# (b) it contains both pending-restore- and an explicit OR-shaped alternative
def test_slice_has_pending_restore_and_or_alternative(slice_text: str) -> None:
    assert "pending-restore-" in slice_text
    assert re.search(r"\bOR\b", slice_text), (
        "condition must be restated with an explicit OR-shaped alternative, "
        "not silently reverted to the dual-sentinel conjunction"
    )


# (c) the Arm A message is present verbatim including
# "Auto-written checkpoint: ${_cp_path}"
def test_arm_a_message_verbatim(slice_text: str) -> None:
    assert (
        "Auto-compact already ran in this session; precompact.sh wrote a "
        "checkpoint automatically. No additional /checkpoint needed. "
        "Auto-written checkpoint: ${_cp_path}"
    ) in slice_text


# (d) the Arm B message is present, and its paragraph contains neither
# _cp_path nor checkpoints/
def test_arm_b_message_present_and_names_no_path(slice_text: str) -> None:
    marker = "A compaction already ran in this session and no automatic checkpoint was written."
    assert marker in slice_text
    idx = slice_text.index(marker)
    # Isolate the paragraph/bullet containing the marker (up to the next blank line).
    end = slice_text.find("\n\n", idx)
    if end == -1:
        end = len(slice_text)
    paragraph = slice_text[idx:end]
    assert "_cp_path" not in paragraph
    assert "checkpoints/" not in paragraph


# (e) the slice still contains pidfile_release checkpoint and the cost-ledger
# skip row
def test_slice_contains_pidfile_release_and_costledger_row(slice_text: str) -> None:
    assert "pidfile_release checkpoint" in slice_text
    assert '"skip (compact-already-ran)"' in slice_text


# (f) the slice contains command -v run_state_probe (or an equivalent
# availability check)
def test_slice_contains_availability_check(slice_text: str) -> None:
    assert "command -v run_state_probe" in slice_text


# (g) the line index of the source line is STRICTLY LESS than the line index
# of `command -v run_state_probe` (MAJ-1 regression guard)
def test_source_line_precedes_availability_guard(slice_text: str) -> None:
    lines = slice_text.splitlines()
    source_idx = next(
        (i for i, ln in enumerate(lines) if '. "__QUOIN_HOME__/hooks/_lib.sh"' in ln),
        None,
    )
    guard_idx = next(
        (i for i, ln in enumerate(lines) if "command -v run_state_probe" in ln),
        None,
    )
    assert source_idx is not None, "Step 1.4 slice must source _lib.sh"
    assert guard_idx is not None, "Step 1.4 slice must check command -v run_state_probe"
    assert source_idx < guard_idx, (
        "the _lib.sh source line must appear before the command -v guard — "
        "otherwise the new arm ships permanently inert with a green suite"
    )


# (h) the slice contains all three literal tokens inside the SAME fenced
# ```sh block as clauses (f)/(g), giving T-13's extraction step a stable,
# well-defined target
def test_probe_block_contains_all_three_tokens(slice_text: str) -> None:
    fences = re.findall(r"```sh\n(.*?)\n```", slice_text, re.DOTALL)
    probe_blocks = [b for b in fences if "command -v run_state_probe" in b]
    assert len(probe_blocks) == 1, (
        f"expected exactly one fenced ```sh block containing "
        f"'command -v run_state_probe', found {len(probe_blocks)}"
    )
    block = probe_blocks[0]
    for token in ("GUARD_UNAVAILABLE", "PROBE_ACTIVE", "PROBE_INACTIVE"):
        assert token in block, f"probe block missing token literal {token!r}"
    # source line, guard, and probe call live together as ONE fenced block —
    # not split across multiple fenced blocks, and not left as bare prose.
    assert '. "__QUOIN_HOME__/hooks/_lib.sh"' in block


def test_no_revert_to_conjunction_only_condition(slice_text: str) -> None:
    """Fails on a revert to the pre-stage-6 conjunction-only condition text."""
    assert "BOTH `_sentinel` AND `_pending` must exist for the skip to fire" not in slice_text
