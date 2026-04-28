"""test_cost_from_jsonl.py — parity + structural tests for cost_from_jsonl.py.

Five test cases:
  1. test_parity_against_ccusage           — real JSONL vs ccusage, ≤1% delta
  2. test_missing_uuid_exit_code           — exit 2 + "not found" on stderr
  3. test_malformed_jsonl_does_not_crash   — valid rows counted, malformed skipped
  4. test_unknown_model_does_not_crash     — unknown model → costUSD=0, no crash
  5. test_project_hash_function            — empirical transform rule (spaces → '-')
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.parent  # project root
SCRIPTS_DIR = pathlib.Path(__file__).parent.parent              # quoin/scripts/
FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "cost_from_jsonl"
UUID_FIXTURE = FIXTURES_DIR / "uuids.txt"
SCRIPT = SCRIPTS_DIR / "cost_from_jsonl.py"

# Project path for --project-path (the real dev-machine project root)
PROJECT_PATH = str(REPO_ROOT)

sys.path.insert(0, str(SCRIPTS_DIR))
from cost_from_jsonl import project_hash, parse_session, cost_for_entry  # noqa: E402

# ---------------------------------------------------------------------------
# Load fixture UUIDs at module-import time (each becomes a parametrized case)
# ---------------------------------------------------------------------------
def _load_fixture_uuids():
    if not UUID_FIXTURE.exists():
        return []
    lines = UUID_FIXTURE.read_text().strip().splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


FIXTURE_UUIDS = _load_fixture_uuids()

# Compute the expected project hash once for reuse in parity checks
EXPECTED_HASH = project_hash(PROJECT_PATH)


# ---------------------------------------------------------------------------
# Helper: check if ccusage is available
# ---------------------------------------------------------------------------
def _ccusage_available() -> bool:
    if not _npx_available():
        return False
    result = subprocess.run(
        ["npx", "ccusage", "--version"],
        capture_output=True, timeout=15,
    )
    return result.returncode == 0


def _npx_available() -> bool:
    import shutil
    return shutil.which("npx") is not None


# ---------------------------------------------------------------------------
# Test 1: parity against ccusage (per-UUID parametrized, each independently skipable)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("uuid", FIXTURE_UUIDS)
def test_parity_against_ccusage(uuid):
    if not _npx_available():
        pytest.skip("ccusage not installed (npx not found)")
    if not _ccusage_available():
        pytest.skip("ccusage not installed or non-zero version exit")

    # Detect hash mismatch before silent-skip
    proj_hash = project_hash(PROJECT_PATH)
    projects_dir = pathlib.Path.home() / ".claude" / "projects"
    jsonl_path = projects_dir / proj_hash / f"{uuid}.jsonl"

    if not jsonl_path.exists():
        # Check whether the directory exists under a different hash (wrong hash function)
        hash_prefix = proj_hash[:10]
        if projects_dir.exists():
            for entry in projects_dir.iterdir():
                if entry.is_dir() and entry.name != proj_hash and entry.name.startswith(hash_prefix):
                    pytest.fail(
                        f"project_hash mismatch: expected {proj_hash!r}, "
                        f"found {entry.name!r} — hash function is wrong"
                    )
        pytest.skip(f"UUID jsonl not found locally: {jsonl_path}")

    # Run our script
    local_result = subprocess.run(
        [sys.executable, str(SCRIPT), "session", "-i", uuid, "--json",
         "--project-path", PROJECT_PATH],
        capture_output=True, text=True, timeout=30,
    )
    assert local_result.returncode == 0, (
        f"cost_from_jsonl.py exited {local_result.returncode}: {local_result.stderr}"
    )
    local_data = json.loads(local_result.stdout)
    local_cost = local_data["totalCost"]

    # Run ccusage
    ccusage_result = subprocess.run(
        ["npx", "ccusage", "session", "-i", uuid, "--json"],
        capture_output=True, text=True, timeout=30,
    )
    assert ccusage_result.returncode == 0, (
        f"ccusage exited {ccusage_result.returncode}: {ccusage_result.stderr}"
    )
    ccusage_data = json.loads(ccusage_result.stdout)
    ccusage_cost = ccusage_data["totalCost"]

    # Parity: ≤1% relative tolerance
    denom = max(ccusage_cost, 0.01)
    rel_diff = abs(local_cost - ccusage_cost) / denom
    local_entries = {e["model"]: e for e in local_data.get("entries", [])}
    ccusage_entries = {e["model"]: e for e in ccusage_data.get("entries", [])}
    assert rel_diff < 0.01, (
        f"UUID {uuid}: parity FAIL — "
        f"local={local_cost:.6f}, ccusage={ccusage_cost:.6f}, "
        f"rel_diff={rel_diff:.4%}\n"
        f"local entries: {local_entries}\n"
        f"ccusage entries: {ccusage_entries}"
    )


# ---------------------------------------------------------------------------
# Test 2: missing UUID exits with code 2 and stderr "not found"
# ---------------------------------------------------------------------------
def test_missing_uuid_exit_code():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "session",
         "-i", "00000000-0000-0000-0000-000000000000",
         "--json",
         "--project-path", PROJECT_PATH],
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 2, (
        f"Expected exit code 2, got {result.returncode}. stderr: {result.stderr!r}"
    )
    assert "not found" in result.stderr.lower(), (
        f"Expected 'not found' in stderr, got: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: malformed JSONL does not crash; valid rows are still counted
# ---------------------------------------------------------------------------
def test_malformed_jsonl_does_not_crash(capsys, tmp_path):
    import io
    from cost_from_jsonl import parse_session

    # Write a JSONL with one valid message row and one malformed line
    valid_row = {
        "message": {
            "model": "claude-sonnet-4-6",
            "usage": {
                "input_tokens": 1000,
                "output_tokens": 500,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }
    }
    jsonl_file = tmp_path / "00000000-0000-0000-0000-000000000001.jsonl"
    jsonl_file.write_text(
        json.dumps(valid_row) + "\n"
        "this is NOT valid json !!!!\n"
    )

    # Capture stderr
    import io as _io
    captured_stderr = _io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured_stderr
    try:
        result = parse_session(jsonl_file)
    finally:
        sys.stderr = old_stderr

    stderr_output = captured_stderr.getvalue()

    # Valid row was counted
    assert result["totalCost"] > 0, (
        f"Expected totalCost > 0 from the valid row; got {result['totalCost']}"
    )
    # Malformed line was warned about
    assert "malformed" in stderr_output.lower() or "skipping" in stderr_output.lower(), (
        f"Expected 'malformed' or 'skipping' warning in stderr; got: {stderr_output!r}"
    )


# ---------------------------------------------------------------------------
# Test 4: unknown model does not crash; costUSD=0, stderr warning
# ---------------------------------------------------------------------------
def test_unknown_model_does_not_crash(tmp_path):
    from cost_from_jsonl import parse_session

    row = {
        "message": {
            "model": "claude-future-99",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }
    }
    jsonl_file = tmp_path / "00000000-0000-0000-0000-000000000002.jsonl"
    jsonl_file.write_text(json.dumps(row) + "\n")

    import io as _io
    captured_stderr = _io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured_stderr
    try:
        result = parse_session(jsonl_file)
    finally:
        sys.stderr = old_stderr

    stderr_output = captured_stderr.getvalue()

    # The unknown model entry must be present with costUSD=0
    unknown_entries = [e for e in result["entries"] if e["model"] == "claude-future-99"]
    assert len(unknown_entries) == 1, (
        f"Expected one entry for 'claude-future-99'; got entries: {result['entries']}"
    )
    assert unknown_entries[0]["costUSD"] == 0.0, (
        f"Expected costUSD=0 for unknown model; got {unknown_entries[0]['costUSD']}"
    )
    # A stderr warning must have been emitted
    assert "unknown" in stderr_output.lower() or "claude-future-99" in stderr_output, (
        f"Expected unknown-model warning in stderr; got: {stderr_output!r}"
    )


# ---------------------------------------------------------------------------
# Test 5: project_hash empirical transform — spaces → '-', broader than slash-only
# ---------------------------------------------------------------------------
def test_project_hash_function():
    from cost_from_jsonl import project_hash

    # (a) Spaces are replaced with '-' (NOT preserved)
    # A slash-only implementation would return "-Users-x-My Drive" (space kept).
    # The correct empirical rule replaces ALL non-[A-Za-z0-9-] chars, including space.
    assert project_hash("/Users/x/My Drive") == "-Users-x-My-Drive", (
        "project_hash must replace spaces with '-' (empirical rule, not slash-only). "
        "Got: " + repr(project_hash("/Users/x/My Drive"))
    )

    # (b) Full developer-machine path — golden value verified 2026-04-27 by
    #     `ls ~/.claude/projects/ | grep Claude-workflow` on the dev machine.
    full_path = (
        "/Users/ivgo/Library/CloudStorage/"
        "GoogleDrive-ivan.gorban@gmail.com/"
        "My Drive/Storage/Claude_workflow"
    )
    expected = (
        "-Users-ivgo-Library-CloudStorage-"
        "GoogleDrive-ivan-gorban-gmail-com-"
        "My-Drive-Storage-Claude-workflow"
    )
    assert project_hash(full_path) == expected, (
        f"project_hash golden value mismatch.\n"
        f"  got:      {project_hash(full_path)!r}\n"
        f"  expected: {expected!r}"
    )
