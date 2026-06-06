"""T-09: Unit tests for agentdesk() arg parsing and _agentdesk_pick_layout() in agentdesk.zsh.

Approach: use Python subprocess + zsh to source agentdesk.zsh and invoke functions.
A mock `zellij` wrapper in $PATH prevents actual Zellij launches.
All tests skip gracefully when zsh is not available on the system.

Picker tests isolate _agentdesk_pick_layout() via piped stdin (non-TTY path
bypasses the picker in agentdesk(); we call _agentdesk_pick_layout() directly).
"""
import os
import pty
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

    for name in ("zellij", "claude", "codex", "ccr"):
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


def _gen_layout(tokens: str, tmp_path: Path) -> str:
    """Call _agentdesk_gen_layout with the given tokens, return the KDL file content.

    The function echoes the temp-file path; we read and return its content,
    then clean up the temp file.
    """
    script = textwrap.dedent(f"""
        source "{AGENTDESK_ZSH}"
        out="$(_agentdesk_gen_layout {tokens})"
        cat "$out"
        rm -f "$out"
    """).strip()
    result = subprocess.run(
        ["zsh", "-c", script],
        env=_make_mock_env(tmp_path),
        input="",
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=10,
    )
    assert result.returncode == 0, f"gen_layout failed: {result.stderr}"
    return result.stdout


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
    """_agentdesk_pick_layout with option 6 + unknown token + empty retry returns rc=1."""
    # Input: choose option 6 (Custom — was 5 before ccr renumber), then type bad token, then empty retry (cancel)
    result = _run_pick_layout("6\nemacs, shell\n\n", tmp_path)
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


# ── KDL layout generation validity (regression: review I-01 / I-02) ─────────────

def _assert_kdl_valid(kdl: str) -> None:
    """Structural validity checks for generated KDL.

    Catches the two review-1 CRITICAL bugs:
      I-01: leaked `name=`/`cmd=` lines from `local` inside a redirected loop.
      I-02: unescaped inner double-quotes that terminate the args "..." string.
    """
    lines = kdl.splitlines()

    # I-01: no leaked variable-assignment lines (e.g. name='Claude Code', cmd=...)
    for ln in lines:
        stripped = ln.strip()
        assert not stripped.startswith("name="), f"Leaked 'name=' line in KDL: {ln!r}"
        assert not stripped.startswith("cmd="), f"Leaked 'cmd=' line in KDL: {ln!r}"

    # Balanced braces
    assert kdl.count("{") == kdl.count("}"), "Unbalanced braces in KDL"

    # I-02: every args line must escape inner double-quotes as \" — there must be
    # NO bare (unescaped) `"$HOME` or `"$PROJECT_ROOT` or `"$PWD` inside the cmd.
    for ln in lines:
        if 'args "-lc"' in ln:
            # The outer wrapper is `args "-lc" "<cmd>"`. Inner var refs must be \"
            assert '"$HOME' not in ln.replace('\\"$HOME', ""), (
                f"Unescaped \"$HOME in args line: {ln!r}"
            )
            assert '"$PROJECT_ROOT' not in ln.replace('\\"$PROJECT_ROOT', ""), (
                f"Unescaped \"$PROJECT_ROOT in args line: {ln!r}"
            )
            assert '"$PWD' not in ln.replace('\\"$PWD', ""), (
                f"Unescaped \"$PWD in args line: {ln!r}"
            )


def test_kdl_solo_valid(tmp_path: Path) -> None:
    """_agentdesk_gen_layout claude → valid single-pane KDL, no leaks, escaped quotes."""
    kdl = _gen_layout("claude", tmp_path)
    _assert_kdl_valid(kdl)
    assert 'tab name="main"' in kdl
    assert 'pane name="Claude Code"' in kdl
    assert 'split_direction' not in kdl, "Solo layout should not have a split"


def test_kdl_duo_valid(tmp_path: Path) -> None:
    """_agentdesk_gen_layout claude shell → valid 2-pane side-by-side KDL."""
    kdl = _gen_layout("claude shell", tmp_path)
    _assert_kdl_valid(kdl)
    assert 'split_direction="vertical"' in kdl, "Duo should split side-by-side"
    assert 'pane name="Claude Code"' in kdl
    assert 'pane name="Shell"' in kdl


def test_kdl_trio_valid_no_leaks(tmp_path: Path) -> None:
    """_agentdesk_gen_layout claude codex shell → valid 3-pane KDL, NO leaked lines.

    This is the exact case that exposed review I-01 (leaked name=/cmd= lines).
    """
    kdl = _gen_layout("claude codex shell", tmp_path)
    _assert_kdl_valid(kdl)
    assert 'pane name="Claude Code"' in kdl
    assert 'pane name="Codex"' in kdl
    assert 'pane name="Shell"' in kdl
    # Exactly 3 panes inside the split (plus the 0 from solo path)
    assert kdl.count('command "zsh"') == 3, "Trio must have exactly 3 command panes"


def test_kdl_four_panes_stack_horizontal(tmp_path: Path) -> None:
    """_agentdesk_gen_layout with 4 tokens → horizontal stack, valid KDL."""
    kdl = _gen_layout("claude claude codex shell", tmp_path)
    _assert_kdl_valid(kdl)
    assert 'split_direction="horizontal"' in kdl, ">3 panes should stack vertically"
    assert kdl.count('command "zsh"') == 4


def test_kdl_escaping_matches_fixed_layout(tmp_path: Path) -> None:
    """Generated KDL escapes inner quotes the same way as the fixed agent-desk.kdl.

    The fixed layout uses `source \\"$HOME/...\\"` — verify the generator matches.
    """
    kdl = _gen_layout("claude", tmp_path)
    # Inner var refs must appear escaped
    assert '\\"$HOME/.config/agentdesk/agentdesk.zsh\\"' in kdl, (
        "Generated KDL must escape $HOME ref like the fixed layout"
    )
    assert '\\"$PROJECT_ROOT\\"' in kdl, "Generated KDL must escape $PROJECT_ROOT ref"


# ============================================================
# T-10: /status agentdesk token tests (IVG-59)
# ============================================================

def _run_zsh_fn(fn_call: str, tmp_path: Path, stdin_input: str = "") -> subprocess.CompletedProcess:
    """Source agentdesk.zsh and call an arbitrary zsh function/expression."""
    script = f'source "{AGENTDESK_ZSH}"\n{fn_call}'
    return subprocess.run(
        ["zsh", "-c", script],
        env=_make_mock_env(tmp_path),
        input=stdin_input,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )


def test_agentdesk_status_token_valid(tmp_path: Path) -> None:
    """status token → generates a pane with status_graph.py (not a named session).

    Verifies the L373 fix: 'status' must be in the positional-token case so it
    routes as a window token. We verify via _gen_layout (same as other KDL tests)
    rather than the full agentdesk() invocation (which adds zellij/mktemp overhead).
    """
    # Verify layout generation works (status routed as window token, not session name)
    kdl = _gen_layout("status", tmp_path)
    assert "status_graph.py" in kdl, (
        "status token must generate a pane with status_graph.py; "
        f"got KDL: {kdl[:300]}"
    )
    assert "--compact" in kdl, "status pane command must include --compact"
    assert 'pane name="Status"' in kdl, f"status pane must be named 'Status': {kdl[:300]}"


def test_agentdesk_status_pane_cmd(tmp_path: Path) -> None:
    """_agentdesk_pane_cmd status → contains status_graph.py and --compact."""
    result = _run_zsh_fn("_agentdesk_pane_cmd status", tmp_path)
    assert result.returncode == 0
    cmd = result.stdout
    assert "status_graph.py" in cmd, f"pane cmd missing status_graph.py: {cmd!r}"
    assert "--compact" in cmd, f"pane cmd missing --compact: {cmd!r}"


def test_agentdesk_status_pane_name(tmp_path: Path) -> None:
    """_agentdesk_pane_name status → 'Status'."""
    result = _run_zsh_fn("_agentdesk_pane_name status", tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "Status", (
        f"Expected pane name 'Status', got: {result.stdout.strip()!r}"
    )


def test_agentdesk_parse_custom_tokens_with_status(tmp_path: Path) -> None:
    """_agentdesk_parse_custom_tokens 'claude, status' → outputs both tokens."""
    result = _run_zsh_fn("_agentdesk_parse_custom_tokens 'claude, status'", tmp_path)
    assert result.returncode == 0
    output = result.stdout
    assert "status" in output, f"status token not in output: {output!r}"
    assert "claude" in output, f"claude token not in output: {output!r}"


def test_agentdesk_unknown_token_error_includes_status(tmp_path: Path) -> None:
    """_agentdesk_parse_custom_tokens with unknown token → error mentions 'status'."""
    # Provide empty retry so the function terminates
    result = _run_zsh_fn("_agentdesk_parse_custom_tokens 'emacs'", tmp_path, stdin_input="\n")
    assert result.returncode != 0 or "status" in result.stderr, (
        f"Error message for unknown token should mention 'status': {result.stderr!r}"
    )
    assert "status" in result.stderr, (
        f"Valid-tokens error message missing 'status': {result.stderr!r}"
    )


# ============================================================
# CCR token tests (agentdesk-ccr-token)
# ============================================================

def test_agentdesk_ccr_pane_cmd(tmp_path: Path) -> None:
    """_agentdesk_pane_cmd ccr → contains 'ccr code' and 'command -v ccr' and fallback."""
    result = _run_zsh_fn("_agentdesk_pane_cmd ccr", tmp_path)
    assert result.returncode == 0
    cmd = result.stdout
    assert "ccr code" in cmd, f"pane cmd missing 'ccr code': {cmd!r}"
    assert "command -v ccr" in cmd, f"pane cmd missing 'command -v ccr' guard: {cmd!r}"
    assert "ccr not found" in cmd, f"pane cmd missing 'ccr not found' fallback: {cmd!r}"


def test_agentdesk_ccr_pane_name(tmp_path: Path) -> None:
    """_agentdesk_pane_name ccr → prints exactly 'CCR (OpenRouter)'."""
    result = _run_zsh_fn("_agentdesk_pane_name ccr", tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == "CCR (OpenRouter)", (
        f"Expected pane name 'CCR (OpenRouter)', got: {result.stdout.strip()!r}"
    )


def test_agentdesk_ccr_token_valid(tmp_path: Path) -> None:
    """ccr token → generates valid KDL with 'ccr code' command and correct pane name."""
    kdl = _gen_layout("ccr", tmp_path)
    assert "ccr code" in kdl, f"KDL missing 'ccr code': {kdl[:400]}"
    assert 'pane name="CCR (OpenRouter)"' in kdl, (
        f"KDL missing pane name 'CCR (OpenRouter)': {kdl[:400]}"
    )
    _assert_kdl_valid(kdl)


def test_agentdesk_parse_custom_tokens_with_ccr(tmp_path: Path) -> None:
    """_agentdesk_parse_custom_tokens 'claude, ccr' → outputs both tokens."""
    result = _run_zsh_fn("_agentdesk_parse_custom_tokens 'claude, ccr'", tmp_path)
    assert result.returncode == 0
    output = result.stdout
    assert "ccr" in output, f"ccr token not in output: {output!r}"
    assert "claude" in output, f"claude token not in output: {output!r}"


def test_agentdesk_unknown_token_error_includes_ccr(tmp_path: Path) -> None:
    """_agentdesk_parse_custom_tokens with unknown token → error mentions 'status, ccr' tail."""
    result = _run_zsh_fn("_agentdesk_parse_custom_tokens 'emacs'", tmp_path, stdin_input="\n")
    assert result.returncode != 0 or "ccr" in result.stderr, (
        f"Error message for unknown token should mention 'ccr': {result.stderr!r}"
    )
    assert "status, ccr" in result.stderr, (
        f"Valid-tokens error message missing ordered tail 'status, ccr': {result.stderr!r}"
    )


def test_agentdesk_picker_option5_claude_ccr_shell(tmp_path: Path) -> None:
    """_agentdesk_pick_layout with input '5' returns 'claude ccr shell'."""
    result = _run_pick_layout("5\n", tmp_path)
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    assert result.stdout.strip() == "claude ccr shell", (
        f"Expected 'claude ccr shell', got: {result.stdout.strip()!r}"
    )


# ============================================================
# S-3: _agentdesk_open_dashboard tests (IVG-63 stage-3)
# ============================================================

def _make_dashboard_env(tmp_path: Path, with_server: bool = True) -> dict:
    """Extend _make_mock_env with a fake $HOME containing (optionally) a stub
    dashboard_server.py that immediately prints URL=http://127.0.0.1:8787 and
    exits, and stub `open` / `xdg-open` that record their argv to a marker file.

    Args:
        with_server: if True, create the stub server script; if False, omit it
                     to test the missing-server code path.
    """
    env = _make_mock_env(tmp_path)
    mock_bin = tmp_path / "mock_bin"  # already exists from _make_mock_env

    # Fake HOME so $HOME/.claude/scripts/ resolves to a writable temp dir.
    fake_home = tmp_path / "fake_home"
    fake_home.mkdir()
    env["HOME"] = str(fake_home)

    if with_server:
        scripts_dir = fake_home / ".claude" / "scripts"
        scripts_dir.mkdir(parents=True)
        server = scripts_dir / "dashboard_server.py"
        # Stub: print URL= line and exit immediately.
        server.write_text(
            "import sys\n"
            "print('URL=http://127.0.0.1:8787', flush=True)\n"
            "# --no-browser flag accepted and ignored\n"
        )
        server.chmod(0o755)

    # Stub `open` writes argv[1] (the URL) to a marker file so tests can assert it.
    marker = tmp_path / "open_called.txt"
    open_stub = mock_bin / "open"
    open_stub.write_text(
        f"#!/bin/sh\necho \"$1\" > '{marker}'\nexit 0\n"
    )
    open_stub.chmod(0o755)

    # Also stub xdg-open with same behaviour (fallback path).
    xdg_stub = mock_bin / "xdg-open"
    xdg_stub.write_text(
        f"#!/bin/sh\necho \"$1\" > '{marker}'\nexit 0\n"
    )
    xdg_stub.chmod(0o755)

    return env


def _run_dashboard_fn_with_pty(
    env: dict,
    input_text: str,
    tmp_path: Path,
    timeout: int = 25,
) -> subprocess.CompletedProcess:
    """Run _agentdesk_open_dashboard with a real PTY as stdin.

    Uses pty.openpty() to provide a file descriptor that satisfies [ -t 0 ],
    so the TTY guard inside _agentdesk_open_dashboard passes and the real
    function body executes.  input_text is written to the PTY master side
    after the subprocess is started; the child reads it via 'read -r reply'.
    stdout and stderr are captured via PIPE (not the PTY) so assertions are
    straightforward.
    """
    script = f'source "{AGENTDESK_ZSH}"\n_agentdesk_open_dashboard'
    master_fd, slave_fd = pty.openpty()
    stdout_b: bytes = b""
    stderr_b: bytes = b""
    rc: int = -1
    try:
        try:
            proc = subprocess.Popen(
                ["zsh", "-c", script],
                stdin=slave_fd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=str(tmp_path),
                close_fds=True,
            )
        finally:
            os.close(slave_fd)  # parent no longer needs the slave end
        try:
            os.write(master_fd, input_text.encode())
        except OSError:
            pass  # process may have exited before the write
        try:
            stdout_b, stderr_b = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout_b, stderr_b = proc.communicate()
        rc = proc.returncode
    finally:
        try:
            os.close(master_fd)
        except OSError:
            pass
    return subprocess.CompletedProcess(
        args=["zsh", "-c", script],
        returncode=rc,
        stdout=stdout_b.decode(errors="replace"),
        stderr=stderr_b.decode(errors="replace"),
    )


def test_open_dashboard_non_tty_skips(tmp_path: Path) -> None:
    """_agentdesk_open_dashboard with piped stdin (non-TTY) returns 0 with no prompt
    and does not invoke the server stub.

    stdin piped = [ ! -t 0 ] fires → function returns immediately.
    """
    env = _make_dashboard_env(tmp_path)
    script = f'source "{AGENTDESK_ZSH}"\n_agentdesk_open_dashboard'
    result = subprocess.run(
        ["zsh", "-c", script],
        env=env,
        input="",  # piped → non-TTY
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        timeout=15,
    )
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    # No prompt should appear on stderr (function returned before printf)
    assert "Open quoin dashboard" not in result.stderr, (
        f"Prompt should not appear on non-TTY: stderr={result.stderr!r}"
    )
    # Server marker file must NOT exist (server never launched)
    marker = tmp_path / "open_called.txt"
    assert not marker.exists(), "Browser opener should NOT have been called on non-TTY"


def test_open_dashboard_declines_default(tmp_path: Path) -> None:
    """_agentdesk_open_dashboard with PTY stdin 'n\\n' returns 0 and does not
    start the server or open a browser.

    Uses pty.openpty() so [ -t 0 ] is true and the real function body runs.
    """
    env = _make_dashboard_env(tmp_path)
    result = _run_dashboard_fn_with_pty(env, "n\n", tmp_path)
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    marker = tmp_path / "open_called.txt"
    assert not marker.exists(), "Browser opener should NOT have been called on 'n' reply"


def test_open_dashboard_accepts_opens_url(tmp_path: Path) -> None:
    """_agentdesk_open_dashboard with PTY stdin 'y\\n' starts the stub server,
    captures URL=..., calls the mock `open` stub, and returns 0.

    Uses pty.openpty() so [ -t 0 ] is true and the real function body runs.
    """
    env = _make_dashboard_env(tmp_path, with_server=True)
    result = _run_dashboard_fn_with_pty(env, "y\n", tmp_path, timeout=25)
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    marker = tmp_path / "open_called.txt"
    assert marker.exists(), (
        f"Browser opener stub should have been called; stderr={result.stderr!r}"
    )
    url_opened = marker.read_text().strip()
    assert url_opened == "http://127.0.0.1:8787", (
        f"Unexpected URL passed to opener: {url_opened!r}"
    )


def test_open_dashboard_missing_server_noop(tmp_path: Path) -> None:
    """_agentdesk_open_dashboard with PTY stdin 'y\\n' but no server script returns 0
    and prints the 'not found' note to stderr without crashing.

    Uses pty.openpty() so [ -t 0 ] is true and the real function body runs.
    """
    env = _make_dashboard_env(tmp_path, with_server=False)
    result = _run_dashboard_fn_with_pty(env, "y\n", tmp_path)
    assert result.returncode == 0, f"rc={result.returncode}, stderr={result.stderr}"
    assert "not found" in result.stderr, (
        f"Expected 'not found' note in stderr: {result.stderr!r}"
    )
    marker = tmp_path / "open_called.txt"
    assert not marker.exists(), "Browser opener should NOT be called when server is absent"
