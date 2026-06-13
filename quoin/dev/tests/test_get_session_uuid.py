"""IVG-74 T-08: Core logic tests for get_session_uuid.py.

Tests:
- test_project_hash_matches_cost_from_jsonl — parity between inline copy and original
- test_real_uuid_returned_when_jsonl_exists — happy path
- test_fallback_when_no_jsonl — no JSONL, returns unknown-* form
- test_fallback_with_phase_in_name — phase appears in fallback
- test_fallback_phase_slug_uses_underscores — dashes slugified
- test_main_cli_exits_zero_always — fail-open: exit 0 even with nonexistent path
- test_most_recent_jsonl_selected — mtime ordering
"""
import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]  # quoin/ repo root
CORE_SCRIPT = REPO_ROOT / "quoin" / "core" / "scripts" / "get_session_uuid.py"
ADAPTER_SCRIPT = REPO_ROOT / "quoin" / "scripts" / "cost_from_jsonl.py"


def _load_core():
    """Load get_session_uuid core module via importlib (no sys.path mutation)."""
    spec = importlib.util.spec_from_file_location("_test_get_session_uuid_core", CORE_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_cost_from_jsonl():
    """Load cost_from_jsonl adapter for parity testing (intentional adapter import)."""
    spec = importlib.util.spec_from_file_location("_test_cost_from_jsonl", ADAPTER_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_project_hash_matches_cost_from_jsonl():
    """project_hash() in core must produce identical output to the adapter copy.

    Intentional adapter import — this is a parity test only, not a production
    dependency. See D-01 in the plan: the function is an inline copy because
    cost_from_jsonl.py is CLAUDE-ADAPTER-OWNED and must not be imported from core.
    """
    core = _load_core()
    adapter = _load_cost_from_jsonl()

    test_paths = [
        "/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com/My Drive/Storage/Codex_workflow",
        "/Users/ivgo/.claude",
        "/path with spaces/and.dots/and@symbols",
    ]
    for path in test_paths:
        assert core.project_hash(path) == adapter.project_hash(path), (
            f"project_hash mismatch for {path!r}: "
            f"core={core.project_hash(path)!r} adapter={adapter.project_hash(path)!r}"
        )


def test_real_uuid_returned_when_jsonl_exists(tmp_path):
    """get_session_uuid() returns the stem of the most-recent JSONL file."""
    core = _load_core()

    # Create a fake project dir and JSONL file
    test_project = tmp_path / "test_project"
    test_project.mkdir()
    proj_hash = core.project_hash(str(test_project))
    fake_home = tmp_path / "home"
    proj_dir = fake_home / ".claude" / "projects" / proj_hash
    proj_dir.mkdir(parents=True)

    expected_uuid = "aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb"
    jsonl_file = proj_dir / f"{expected_uuid}.jsonl"
    jsonl_file.write_text('{"type":"summary"}\n')

    result = core.get_session_uuid(
        project_path=str(test_project),
        home=str(fake_home),
        phase="implement",
    )
    assert result == expected_uuid, (
        f"Expected UUID {expected_uuid!r}, got {result!r}"
    )


def test_fallback_when_no_jsonl(tmp_path):
    """get_session_uuid() returns unknown-* form when no JSONL exists."""
    core = _load_core()

    test_project = tmp_path / "test_project"
    test_project.mkdir()
    # home dir with empty projects
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    result = core.get_session_uuid(
        project_path=str(test_project),
        home=str(fake_home),
        phase="implement",
    )
    assert re.match(r'^unknown-[a-z_]+-\d{8}T\d{6}Z$', result), (
        f"Fallback UUID {result!r} does not match expected pattern "
        r"'unknown-<phase_slug>-<YYYYMMDD>T<HHMMSS>Z'"
    )


def test_fallback_with_phase_in_name(tmp_path):
    """Fallback UUID includes the phase slug when phase is provided."""
    core = _load_core()

    test_project = tmp_path / "test_project"
    test_project.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    result = core.get_session_uuid(
        project_path=str(test_project),
        home=str(fake_home),
        phase="implement",
    )
    assert "implement" in result, (
        f"Expected 'implement' in fallback UUID, got {result!r}"
    )


def test_fallback_phase_slug_uses_underscores(tmp_path):
    """Dashes in phase name are slugified to underscores in fallback UUID."""
    core = _load_core()

    test_project = tmp_path / "test_project"
    test_project.mkdir()
    fake_home = tmp_path / "home"
    fake_home.mkdir()

    result = core.get_session_uuid(
        project_path=str(test_project),
        home=str(fake_home),
        phase="end-of-task",
    )
    assert "end_of_task" in result, (
        f"Expected 'end_of_task' (underscores) in fallback UUID, got {result!r}. "
        "Phase dashes must be slugified to underscores."
    )
    assert "end-of-task" not in result, (
        f"Dashes should be replaced with underscores in fallback UUID, got {result!r}"
    )


def test_main_cli_exits_zero_always():
    """CLI exits 0 even when given a nonexistent project path (fail-open)."""
    result = subprocess.run(
        [sys.executable, str(CORE_SCRIPT), "--project-path", "/nonexistent/path/that/does/not/exist"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"CLI exited with rc={result.returncode} (expected 0 — fail-open). "
        f"stdout: {result.stdout!r}  stderr: {result.stderr!r}"
    )
    assert result.stdout.strip(), (
        "CLI must print a non-empty UUID to stdout even on fallback. "
        f"Got empty stdout. stderr: {result.stderr!r}"
    )


def test_most_recent_jsonl_selected(tmp_path):
    """get_session_uuid() returns the stem of the most-recently-modified JSONL."""
    core = _load_core()

    test_project = tmp_path / "test_project"
    test_project.mkdir()
    proj_hash = core.project_hash(str(test_project))
    fake_home = tmp_path / "home"
    proj_dir = fake_home / ".claude" / "projects" / proj_hash
    proj_dir.mkdir(parents=True)

    older_uuid = "11111111-1111-1111-1111-111111111111"
    newer_uuid = "22222222-2222-2222-2222-222222222222"

    older_file = proj_dir / f"{older_uuid}.jsonl"
    older_file.write_text('{"type":"summary"}\n')

    # Brief pause to ensure different mtime
    time.sleep(0.05)

    newer_file = proj_dir / f"{newer_uuid}.jsonl"
    newer_file.write_text('{"type":"summary"}\n')

    result = core.get_session_uuid(
        project_path=str(test_project),
        home=str(fake_home),
    )
    assert result == newer_uuid, (
        f"Expected most-recent JSONL stem {newer_uuid!r}, got {result!r}"
    )


def test_project_hash_special_chars():
    """project_hash handles paths with spaces, @, dots, underscores correctly."""
    core = _load_core()

    path = "/Users/my user/Google Drive-my@email.com/My Project_v2/code"
    result = core.project_hash(path)
    # All non-[A-Za-z0-9-] characters replaced with '-'
    assert re.match(r'^[A-Za-z0-9-]+$', result), (
        f"project_hash result {result!r} contains unexpected characters"
    )
    # Specific chars that must be replaced
    assert " " not in result
    assert "@" not in result
    assert "." not in result
    assert "_" not in result
