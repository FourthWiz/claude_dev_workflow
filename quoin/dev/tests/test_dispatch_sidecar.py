"""
Tests for dispatch_sidecar.py — dispatch hint sidecar writer.

Verifies that the sidecar is written to the canonical deterministic path,
overwrites on subsequent calls, handles missing session_id gracefully,
and fails appropriately on write errors.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent.parent / "core" / "scripts"
HELPER = SCRIPTS_DIR / "dispatch_sidecar.py"

# Import the module directly for unit testing write_sidecar()
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_dispatch_sidecar", HELPER)
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
write_sidecar = _mod.write_sidecar

import subprocess


def run_helper(*args, env=None, **kwargs):
    """Run the helper as a subprocess and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(HELPER)] + list(args)
    merged_env = os.environ.copy()
    merged_env.pop("CLAUDE_CODE_SESSION_ID", None)
    if env:
        merged_env.update(env)
    result = subprocess.run(cmd, capture_output=True, text=True, env=merged_env, **kwargs)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


SIDECAR_FILENAME = ".dispatch-hint.json"
WORKFLOW_DIR = ".workflow_artifacts"


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: write creates sidecar at exactly the canonical deterministic path
# ─────────────────────────────────────────────────────────────────────────────
def test_write_creates_sidecar_at_canonical_path(tmp_path):
    """write_sidecar creates .workflow_artifacts/.dispatch-hint.json."""
    rc = write_sidecar(
        skill_name="implement",
        project_root=tmp_path,
        plan_path="/some/plan.md",
        session_id="test-session-id",
    )
    assert rc == 0, f"Expected exit 0, got {rc}"
    expected = tmp_path / WORKFLOW_DIR / SIDECAR_FILENAME
    assert expected.exists(), f"Sidecar not found at {expected}"
    data = json.loads(expected.read_text())
    assert data["skill_name"] == "implement"
    assert data["project_root"] == str(tmp_path.resolve())
    assert data["plan_path"] == "/some/plan.md"
    assert data["session_id"] == "test-session-id"
    assert "written_at" in data


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: subsequent writes overwrite (no append)
# ─────────────────────────────────────────────────────────────────────────────
def test_write_overwrites(tmp_path):
    """Second call to write_sidecar overwrites the first sidecar."""
    write_sidecar("implement", tmp_path, plan_path="/old.md", session_id="old-id")
    write_sidecar("rollback", tmp_path, plan_path="/new.md", session_id="new-id")

    sidecar = tmp_path / WORKFLOW_DIR / SIDECAR_FILENAME
    data = json.loads(sidecar.read_text())
    assert data["skill_name"] == "rollback"
    assert data["plan_path"] == "/new.md"
    assert data["session_id"] == "new-id"
    # Verify it's valid JSON (no concatenation)
    assert isinstance(data, dict)


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: missing --session-id and no env var → session_id: null (degraded mode)
# ─────────────────────────────────────────────────────────────────────────────
def test_missing_session_id_degraded_mode(tmp_path):
    """Without --session-id or $CLAUDE_CODE_SESSION_ID, session_id is null."""
    rc, stdout, stderr = run_helper(
        "--skill", "implement",
        "--project-root", str(tmp_path),
        env={"CLAUDE_CODE_SESSION_ID": ""},  # clear it
    )
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {stderr}"
    sidecar = tmp_path / WORKFLOW_DIR / SIDECAR_FILENAME
    data = json.loads(sidecar.read_text())
    assert data["session_id"] is None, f"Expected null session_id, got {data['session_id']}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: CLAUDE_CODE_SESSION_ID env var is used when --session-id not given
# ─────────────────────────────────────────────────────────────────────────────
def test_session_id_from_env_var(tmp_path):
    """When $CLAUDE_CODE_SESSION_ID is set and --session-id omitted, env var is used."""
    rc, stdout, stderr = run_helper(
        "--skill", "implement",
        "--project-root", str(tmp_path),
        env={"CLAUDE_CODE_SESSION_ID": "env-session-123"},
    )
    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {stderr}"
    sidecar = tmp_path / WORKFLOW_DIR / SIDECAR_FILENAME
    data = json.loads(sidecar.read_text())
    assert data["session_id"] == "env-session-123"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: --plan is optional; omitting it writes plan_path: null
# ─────────────────────────────────────────────────────────────────────────────
def test_plan_path_is_optional(tmp_path):
    """Omitting --plan writes plan_path: null."""
    rc = write_sidecar("implement", tmp_path, plan_path=None, session_id="sid")
    assert rc == 0
    sidecar = tmp_path / WORKFLOW_DIR / SIDECAR_FILENAME
    data = json.loads(sidecar.read_text())
    assert data["plan_path"] is None


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: unwritable .workflow_artifacts/ → exit 2, warning on stderr
# ─────────────────────────────────────────────────────────────────────────────
@pytest.mark.skipif(os.geteuid() == 0, reason="root can write anywhere; skip permission test")
def test_unwritable_workflow_artifacts_dir(tmp_path):
    """Non-writable .workflow_artifacts/ dir → exit 2, warning on stderr."""
    wf_dir = tmp_path / WORKFLOW_DIR
    wf_dir.mkdir()
    # Make the directory non-writable
    wf_dir.chmod(0o444)
    try:
        rc, stdout, stderr = run_helper(
            "--skill", "implement",
            "--project-root", str(tmp_path),
        )
        assert rc == 2, f"Expected exit 2, got {rc}"
        assert stderr, "Expected warning on stderr"
    finally:
        wf_dir.chmod(0o755)  # restore for cleanup
