"""Unit tests for quoin/dev/scripts/propagate_1m_s0_edit.py.

Covers:
  - patch_text() on a minimal fixture with all three anchors
  - Idempotency: calling patch_text() on already-patched text returns None
  - Anchor-uniqueness errors: missing or duplicated each of the three anchors
  - Line-ending preservation: no-newline WAIT line kept without trailing newline
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the module under test (in dev/scripts/, not on sys.path by default)
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "propagate_1m_s0_edit.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("propagate_1m_s0_edit", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None, f"Cannot load {_SCRIPT_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_MOD = _load_module()
patch_text = _MOD.patch_text
DECIDE_BEGIN = _MOD.DECIDE_BEGIN
DECIDE_END = _MOD.DECIDE_END
CACHEWRITE_BEGIN = _MOD.CACHEWRITE_BEGIN
CACHEWRITE_END = _MOD.CACHEWRITE_END
SPAWN_AGENT_ANCHOR = _MOD.SPAWN_AGENT_ANCHOR
WAIT_ANCHOR = _MOD.WAIT_ANCHOR
IVG89_THEN_PROCEED_ANCHOR = _MOD.IVG89_THEN_PROCEED_ANCHOR
DECIDE_BLOCK = _MOD.DECIDE_BLOCK
CACHEWRITE_SAFE_BLOCK = _MOD.CACHEWRITE_SAFE_BLOCK
CACHEWRITE_UNSAFE_BLOCK = _MOD.CACHEWRITE_UNSAFE_BLOCK


# ---------------------------------------------------------------------------
# Minimal §0 fixture (contains all three anchors, one occurrence each)
# ---------------------------------------------------------------------------

# The fixture mirrors the actual §0 SKILL.md file layout:
# dispatched-tier → Spawn → Wait → worktree-fallback (with IVG89 anchor inside).
# Worktree-fallback MUST come after Spawn/Wait so that after patching:
#   occurrence 0 of cachewrite = safe block (between split Wait and Return)
#   occurrence 1 of cachewrite = unsafe block (inside worktree-fallback before proceed anchor)
FIXTURE_TEMPLATE = """\
# Test Skill

## §0 Model dispatch

Some preamble text.
      dispatched-tier: sonnet.
      Spawn an Agent subagent with the following arguments:
        model: "sonnet"

      Wait for the subagent. Return its output as your final response. STOP.
      (Return the subagent output as your final response.)

<!-- §0-worktree-fallback-begin -->
Fail-graceful path content.
  - 1M-credit-class: if the error text contains the substring
      `Usage credits required for 1M context`:
      Emit verbatim:
        `[quoin: 1M-context credit mismatch on <tier> subagent dispatch; proceeding in-session at parent tier]`
      Then proceed to §1 at the current tier (treat as if [no-redispatch] were present).
      Do NOT call AskUserQuestion.
<!-- §0-worktree-fallback-end -->

## §1 Skill body

Content here.
"""


def _make_fixture() -> str:
    return FIXTURE_TEMPLATE


def _make_patched_fixture() -> str:
    result = patch_text(_make_fixture(), "test_skill")
    assert result is not None
    return result


# ---------------------------------------------------------------------------
# TestPatchTextBasic
# ---------------------------------------------------------------------------

class TestPatchTextBasic:

    def test_returns_string_on_clean_fixture(self) -> None:
        result = patch_text(_make_fixture(), "test_skill")
        assert result is not None
        assert isinstance(result, str)

    def test_decide_block_present_in_output(self) -> None:
        result = patch_text(_make_fixture(), "test_skill")
        assert DECIDE_BEGIN in result
        assert DECIDE_END in result

    def test_two_cachewrite_blocks_in_output(self) -> None:
        result = patch_text(_make_fixture(), "test_skill")
        assert result.count(CACHEWRITE_BEGIN) == 2
        assert result.count(CACHEWRITE_END) == 2

    def test_decide_block_precedes_spawn_anchor(self) -> None:
        result = patch_text(_make_fixture(), "test_skill")
        pos_decide = result.find(DECIDE_BEGIN)
        pos_spawn = result.find(SPAWN_AGENT_ANCHOR)
        assert pos_decide != -1
        assert pos_spawn != -1
        assert pos_decide < pos_spawn

    def test_compound_wait_line_split(self) -> None:
        """The original compound 'Wait... Return... STOP.' line must be gone."""
        result = patch_text(_make_fixture(), "test_skill")
        assert WAIT_ANCHOR not in result

    def test_cachewrite_safe_between_wait_and_return(self) -> None:
        """Occurrence 0 (safe) must be between 'Wait for the subagent.' and 'Return its output...'."""
        result = patch_text(_make_fixture(), "test_skill")
        pos_wait = result.find("      Wait for the subagent.\n")
        pos_cw_begin = result.find(CACHEWRITE_BEGIN)
        pos_return = result.find("      Return its output as your final response. STOP.")
        assert pos_wait != -1, "'Wait for the subagent.' standalone line not found"
        assert pos_cw_begin != -1
        assert pos_return != -1
        assert pos_wait < pos_cw_begin < pos_return

    def test_cachewrite_unsafe_precedes_proceed_anchor(self) -> None:
        """Occurrence 1 (unsafe) must be before the IVG-89 proceed anchor."""
        result = patch_text(_make_fixture(), "test_skill")
        # Both cachewrite-begin markers; find the second one
        first = result.find(CACHEWRITE_BEGIN)
        second = result.find(CACHEWRITE_BEGIN, first + 1)
        pos_proceed = result.find(IVG89_THEN_PROCEED_ANCHOR)
        assert second != -1
        assert pos_proceed != -1
        assert second < pos_proceed

    def test_cachewrite_safe_has_result_safe(self) -> None:
        result = patch_text(_make_fixture(), "test_skill")
        first_cw_begin = result.find(CACHEWRITE_BEGIN)
        first_cw_end = result.find(CACHEWRITE_END, first_cw_begin)
        block0 = result[first_cw_begin:first_cw_end]
        assert "--result safe" in block0

    def test_cachewrite_unsafe_has_result_unsafe(self) -> None:
        result = patch_text(_make_fixture(), "test_skill")
        first_cw_begin = result.find(CACHEWRITE_BEGIN)
        second_cw_begin = result.find(CACHEWRITE_BEGIN, first_cw_begin + 1)
        second_cw_end = result.find(CACHEWRITE_END, second_cw_begin)
        block1 = result[second_cw_begin:second_cw_end]
        assert "--result unsafe" in block1

    def test_quoin_home_placeholder_not_tilde(self) -> None:
        """The inserted blocks must use __QUOIN_HOME__ not ~/.claude/."""
        result = patch_text(_make_fixture(), "test_skill")
        # Only check the inserted regions, not the original fixture content
        decide_start = result.find(DECIDE_BEGIN)
        decide_end = result.find(DECIDE_END) + len(DECIDE_END)
        decide_region = result[decide_start:decide_end]
        assert "~/.claude/" not in decide_region
        assert "__QUOIN_HOME__" in decide_region


# ---------------------------------------------------------------------------
# TestIdempotency
# ---------------------------------------------------------------------------

class TestIdempotency:

    def test_patch_text_on_already_patched_returns_none(self) -> None:
        """patch_text on an already-patched file returns None (idempotent skip)."""
        already_patched = _make_patched_fixture()
        result = patch_text(already_patched, "test_skill")
        assert result is None

    def test_patch_text_on_already_patched_does_not_double_insert(self) -> None:
        """Applying patch twice (if None were ignored) would double the blocks.
        Verify the idempotent path never produces two decide blocks."""
        already_patched = _make_patched_fixture()
        # Simulate a caller that ignores None and tries to patch again
        if patch_text(already_patched, "test_skill") is None:
            # Correct — no mutation happened; the patched text has exactly one decide block
            assert already_patched.count(DECIDE_BEGIN) == 1

    def test_decide_begin_triggers_idempotent_skip(self) -> None:
        """Any file containing DECIDE_BEGIN is considered already-patched."""
        text_with_decide = "some content\n" + DECIDE_BEGIN + "\ncontent\n"
        result = patch_text(text_with_decide, "test_skill")
        assert result is None


# ---------------------------------------------------------------------------
# TestAnchorUniquenessErrors
# ---------------------------------------------------------------------------

class TestAnchorUniquenessErrors:

    # --- SPAWN_AGENT_ANCHOR ---

    def test_missing_spawn_anchor_raises_value_error(self) -> None:
        text = _make_fixture().replace(SPAWN_AGENT_ANCHOR, "")
        with pytest.raises(ValueError, match="SPAWN_AGENT_ANCHOR"):
            patch_text(text, "my_skill")

    def test_duplicate_spawn_anchor_raises_value_error(self) -> None:
        extra = SPAWN_AGENT_ANCHOR + "\n"
        text = _make_fixture().replace(
            SPAWN_AGENT_ANCHOR,
            SPAWN_AGENT_ANCHOR + "\n" + extra,
        )
        with pytest.raises(ValueError, match="SPAWN_AGENT_ANCHOR"):
            patch_text(text, "my_skill")

    def test_spawn_anchor_error_includes_skill_name(self) -> None:
        text = _make_fixture().replace(SPAWN_AGENT_ANCHOR, "")
        with pytest.raises(ValueError, match="my_skill"):
            patch_text(text, "my_skill")

    # --- WAIT_ANCHOR ---

    def test_missing_wait_anchor_raises_value_error(self) -> None:
        text = _make_fixture().replace(WAIT_ANCHOR, "")
        with pytest.raises(ValueError, match="WAIT_ANCHOR"):
            patch_text(text, "my_skill")

    def test_duplicate_wait_anchor_raises_value_error(self) -> None:
        extra = WAIT_ANCHOR + "\n"
        text = _make_fixture().replace(
            WAIT_ANCHOR,
            WAIT_ANCHOR + "\n" + extra,
        )
        with pytest.raises(ValueError, match="WAIT_ANCHOR"):
            patch_text(text, "my_skill")

    def test_wait_anchor_error_includes_skill_name(self) -> None:
        text = _make_fixture().replace(WAIT_ANCHOR, "")
        with pytest.raises(ValueError, match="my_skill"):
            patch_text(text, "my_skill")

    # --- IVG89_THEN_PROCEED_ANCHOR ---

    def test_missing_proceed_anchor_raises_value_error(self) -> None:
        text = _make_fixture().replace(IVG89_THEN_PROCEED_ANCHOR, "")
        with pytest.raises(ValueError, match="IVG89_THEN_PROCEED_ANCHOR"):
            patch_text(text, "my_skill")

    def test_duplicate_proceed_anchor_raises_value_error(self) -> None:
        extra = IVG89_THEN_PROCEED_ANCHOR + "\n"
        text = _make_fixture().replace(
            IVG89_THEN_PROCEED_ANCHOR,
            IVG89_THEN_PROCEED_ANCHOR + "\n" + extra,
        )
        with pytest.raises(ValueError, match="IVG89_THEN_PROCEED_ANCHOR"):
            patch_text(text, "my_skill")

    def test_proceed_anchor_error_includes_skill_name(self) -> None:
        text = _make_fixture().replace(IVG89_THEN_PROCEED_ANCHOR, "")
        with pytest.raises(ValueError, match="my_skill"):
            patch_text(text, "my_skill")


# ---------------------------------------------------------------------------
# TestLineEndingPreservation
# ---------------------------------------------------------------------------

class TestLineEndingPreservation:

    def test_wait_line_with_trailing_newline_preserved(self) -> None:
        """Standard case: WAIT line has a trailing newline; the split
        replacement's final line ('Return...STOP.') also has a newline."""
        fixture = _make_fixture()
        # Verify fixture has a newline-terminated WAIT_ANCHOR line
        assert WAIT_ANCHOR + "\n" in fixture
        result = patch_text(fixture, "test_skill")
        assert result is not None
        # The Return line should end with newline (standard)
        return_line_start = result.find("      Return its output as your final response. STOP.")
        assert return_line_start != -1
        char_after = result[return_line_start + len("      Return its output as your final response. STOP."):]
        assert char_after.startswith("\n") or char_after == ""

    def test_wait_line_without_trailing_newline_preserved(self) -> None:
        """Edge case: if the WAIT line has no trailing newline (EOF), the split
        replacement's final line ('Return...STOP.') must also have no trailing newline.

        Uses a special fixture with reversed block order (worktree-fallback before
        spawn/wait) so WAIT_ANCHOR can appear as the last byte while all three
        required anchors are still present.
        """
        # Build a fixture where WAIT_ANCHOR is truly the last byte in the file.
        # Order: worktree-fallback (with IVG89 anchor) → Spawn → Wait (EOF, no newline).
        fixture_no_newline = (
            "# Test Skill\n\n"
            "<!-- §0-worktree-fallback-begin -->\n"
            "Fallback content.\n"
            "  - 1M-credit-class: `Usage credits required for 1M context`\n"
            "      Then proceed to §1 at the current tier (treat as if [no-redispatch] were present).\n"
            "      Do NOT call AskUserQuestion.\n"
            "<!-- §0-worktree-fallback-end -->\n\n"
            + SPAWN_AGENT_ANCHOR + "\n"
            + "        model: \"sonnet\"\n\n"
            + WAIT_ANCHOR  # no trailing newline — this is the EOF test
        )
        assert not fixture_no_newline.endswith("\n"), "fixture must end without newline for this test"
        result = patch_text(fixture_no_newline, "test_skill")
        assert result is not None
        # The result must end without a trailing newline on the Return line
        assert not result.endswith("\n")

    def test_output_is_valid_string_not_bytes(self) -> None:
        result = patch_text(_make_fixture(), "test_skill")
        assert isinstance(result, str)
