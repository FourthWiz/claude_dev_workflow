"""T-09: Unit tests for agentdesk() arg parsing and _agentdesk_pick_layout() in agentdesk.zsh.

Approach: use Python subprocess + zsh to source agentdesk.zsh and invoke functions.
A mock `zellij` wrapper in $PATH prevents actual Zellij launches.
All tests skip gracefully when zsh is not available on the system.

Picker tests isolate _agentdesk_pick_layout() via piped stdin (non-TTY path
bypasses the picker in agentdesk(); we call _agentdesk_pick_layout() directly).
"""
import os
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Optional, Union

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AGENTDESK_ZSH = REPO_ROOT / "quoin" / "tools" / "agentdesk" / "agentdesk.zsh"

ZSH_AVAILABLE = shutil.which("zsh") is not None
pytestmark = pytest.mark.skipif(
    not ZSH_AVAILABLE,
    reason="zsh not available on this system",
)


def _make_mock_env(tmp_path: Path) -> dict:
    """Build an env dict with a mock zellij wrapper in $PATH.

    The mock zellij exits 0 unconditionally (simulates successful launch)
    so arg-parsing errors (rc=1) are distinguishable from zellij being called.
    Also adds mock claude/codex so 'command -v' checks inside pane cmds pass.
    """
    mock_bin = tmp_path / "mock_bin"
    mock_bin.mkdir()

    for name in ("zellij", "claude", "codex"):
        stub = mock_bin / name
        stub.write_text("#!/bin/zsh\nexit 0\n")
        stub.chmod(0o755)

    env = {**os.environ, "PATH": f"{mock_bin}:{os.environ['PATH']}"}
    # Ensure PROJECT_ROOT is set to avoid _agentdesk_realpath issues
    env["PROJECT_ROOT"] = str(tmp_path)
    # Unset ZELLIJ so the "already inside Zellij" guard does not fire
    # (tests run from within a Zellij session on the dev machine)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    return env


def _run_agentdesk(args: str, tmp_path: Path, stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    """Source agentdesk.zsh and call agentdesk with the given args string.

    Runs with cwd=tmp_path so _detect_repos scans only the (empty) tmp dir,
    not the quoin repo — avoids slow find traversals that cause timeouts.
    """
    script = textwrap.dedent(f"""
        source "{AGENTDESK_ZSH}"
        agentdesk {args}
    """).strip()
    # Pass input="" when no stdin provided so subprocess.PIPE closes immediately,
    # preventing hangs on interactive reads inside the zsh script.
    return subprocess.run(
        ["zsh", "-c", script],
        env=_make_mock_env(tmp_path),
        input=stdin if stdin is not None else "",
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )


def _run_pick_layout(stdin_input: str, tmp_path: Path) -> subprocess.CompletedProcess:
    """Source agentdesk.zsh and call _agentdesk_pick_layout() directly with piped stdin."""
    script = textwrap.dedent(f"""
        source "{AGENTDESK_ZSH}"
        _agentdesk_pick_layout
    """).strip()
    return subprocess.run(
        ["zsh", "-c", script],
        env=_make_mock_env(tmp_path),
        input=stdin_input,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=10,
    )


# ── Arg parsing tests ──────────────────────────────────────────────────────────

def test_agentdesk_zsh_exists() -> None:
    """Sanity: agentdesk.zsh exists at expected path."""
    assert AGENTDESK_ZSH.exists(), f"agentdesk.zsh not found at {AGENTDESK_ZSH}"


def test_agentdesk_zsh_syntax(tmp_path: Path) -> None:
    """zsh -n agentdesk.zsh passes (no syntax errors)."""
    result = subprocess.run(
        ["zsh", "-n", str(AGENTDESK_ZSH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Syntax error in agentdesk.zsh:\n{result.stderr}"


def test_agentdesk_help_exits_zero(tmp_path: Path) -> None:
    """agentdesk --help returns rc=0 and includes 'Usage:'.

    Verifies ZELLIJ guard is ordered AFTER --help (T-02 requirement).
    """
    result = _run_agentdesk("--help", tmp_path)
    assert result.returncode == 0, (
        f"--help must return 0 (rc={result.returncode})\nstderr: {result.stderr}"
    )
    assert "Usage:" in result.stdout, f"Expected 'Usage:' in help output:\n{result.stdout}"


def test_agentdesk_invalid_mode_exits_nonzero(tmp_path: Path) -> None:
    """agentdesk --mode quad returns rc=1 with an error about invalid mode."""
    result = _run_agentdesk("--mode quad", tmp_path)
    assert result.returncode != 0, "Invalid mode should return non-zero"
    combined = result.stdout + result.stderr
    assert "invalid mode" in combined.lower() or "valid modes" in combined.lower(), (
        f"Expected 'invalid mode' error:\n{combined}"
    )


def test_agentdesk_mode_plus_tokens_conflict(tmp_path: Path) -> None:
    """agentdesk --mode duo claude returns rc=1 (mutually exclusive)."""
    result = _run_agentdesk("--mode duo claude", tmp_path)
    assert result.returncode != 0, "--mode + positional tokens should conflict (rc!=0)"


def test_agentdesk_unknown_token_exits_nonzero(tmp_path: Path) -> None:
    """agentdesk emacs claude returns rc=1 (session name + window token mixed)."""
    result = _run_agentdesk("emacs claude", tmp_path)
    assert result.returncode != 0, "Session name + window token should be an error"


def test_agentdesk_mode_name_combo_allowed(tmp_path: Path) -> None:
    """agentdesk --mode duo --name mysession is valid (--mode + --name allowed)."""
    result = _run_agentdesk("--mode duo --name mysession", tmp_path)
    # rc=0 means arg parsing succeeded (mock zellij exits 0)
    assert result.returncode == 0, (
        f"--mode + --name should be allowed (rc={result.returncode})\nstderr: {result.stderr}"
    )


def test_agentdesk_valid_tokens_succeed(tmp_path: Path) -> None:
    """agentdesk claude shell succeeds (rc=0 via mock zellij)."""
    result = _run_agentdesk("claude shell", tmp_path)
    assert result.returncode == 0, (
        f"claude shell tokens should succeed (rc={result.returncode})\nstderr: {result.stderr}"
    )


# ── Picker tests ───────────────────────────────────────────────────────────────

def test_agentdesk_non_tty_skips_picker(tmp_path: Path) -> None:
    """agentdesk with stdin piped (non-TTY) skips picker and uses fixed layout."""
    # Piped stdin means [ -t 0 ] is false → fixed layout path
    # Fixed layout file won't exist, so it errors with "layout not found" (rc=1).
    # That's fine — the point is it didn't call _agentdesk_pick_layout (no menu output).
    result = _run_agentdesk("", tmp_path, stdin="1\n")
    # No picker menu should appear in stderr
    assert "Select a layout" not in result.stderr, (
        "Picker menu should NOT appear when stdin is not a TTY"
    )


def test_agentdesk_picker_option2_claude_shell(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with input '2' returns 'claude shell'."""
    result = _run_pick_layout("2\n", tmp_path)
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    assert result.stdout.strip() == "claude shell", (
        f"Expected 'claude shell', got: {result.stdout.strip()!r}"
    )


def test_agentdesk_picker_option3_two_claude_shell(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with input '3' returns 'claude claude shell'."""
    result = _run_pick_layout("3\n", tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "claude claude shell", (
        f"Expected 'claude claude shell', got: {result.stdout.strip()!r}"
    )


def test_agentdesk_picker_option4_claude_codex_shell(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with input '4' returns 'claude codex shell'."""
    result = _run_pick_layout("4\n", tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "claude codex shell", (
        f"Expected 'claude codex shell', got: {result.stdout.strip()!r}"
    )


def test_agentdesk_picker_custom_comma_input(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with 'claude, codex, shell' (direct) returns 'claude codex shell'."""
    result = _run_pick_layout("claude, codex, shell\n", tmp_path)
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    assert result.stdout.strip() == "claude codex shell", (
        f"Expected 'claude codex shell', got: {result.stdout.strip()!r}"
    )


def test_agentdesk_picker_custom_no_spaces(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with 'claude,shell,shell' returns 'claude shell shell'."""
    result = _run_pick_layout("claude,shell,shell\n", tmp_path)
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    assert result.stdout.strip() == "claude shell shell", (
        f"Expected 'claude shell shell', got: {result.stdout.strip()!r}"
    )


def test_agentdesk_picker_unknown_token_in_custom(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with option 5 + unknown token + empty retry returns rc=1."""
    # Input: choose option 5, then type bad token, then empty retry (cancel)
    result = _run_pick_layout("5\nemacs, shell\n\n", tmp_path)
    assert result.returncode != 0, (
        f"Unknown token in custom input should return non-zero after re-prompt (rc={result.returncode})"
    )


def test_agentdesk_picker_option1_returns_empty(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with '1' echoes nothing (caller uses fixed layout)."""
    result = _run_pick_layout("1\n", tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "", (
        f"Option 1 should produce empty output, got: {result.stdout.strip()!r}"
    )


def test_agentdesk_picker_empty_input_returns_empty(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with empty Enter echoes nothing (same as option 1)."""
    result = _run_pick_layout("\n", tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "", (
        f"Empty input should produce empty output, got: {result.stdout.strip()!r}"
    )
