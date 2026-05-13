"""Tests for validate_adapter_drift.py — Phase 22 runtime-portability work.

Coverage:
- test_validator_passes_on_live_repo           positive gold-master
- test_validator_passes_on_minimal_repo        positive minimal synthetic
- test_drift_co_detected                       AD-CO  core doc missing
- test_drift_ad_detected                       AD-AD  adapter SKILL.md missing
- test_drift_ls_detected                       AD-LS  legacy stub missing
- test_drift_fn_detected                       AD-FN  frontmatter name wrong
- test_drift_fm_detected                       AD-FM  frontmatter model mismatch
- test_drift_pt_detected                       AD-PT  pointer text missing
- test_drift_fb_detected                       AD-FB  frontmatter not byte-equal
- test_drift_ss_detected                       AD-SS  stub not shorter than adapter
- test_drift_s0p_detected                      AD-S0P section_0=true but block absent
- test_drift_s0a_detected                      AD-S0A section_0=false but block present
- test_drift_pe_detected                       AD-PE  spawn_target preamble missing
- test_drift_pa_detected                       AD-PA  spawn_target preamble in adapter dir
- test_drift_px_detected                       AD-PX  non-spawn has preamble
- test_drift_iv_detected                       AD-IV  ADAPTER_FOO_SRC= missing
- test_drift_ie_detected                       AD-IE  if/elif branch missing
- test_drift_io_detected                       AD-IO  preflight after for-loop
- test_json_output_is_valid                    --json flag emits parseable JSON
- test_json_output_contains_invariant_and_skill_fields  JSON violation shape
- test_unreadable_manifest_returns_65          bad manifest path → exit 65
- test_bad_cli_args_return_64                  unknown flag → exit 64
- test_validator_handles_missing_optional_fields  omitted section_0/spawn_target default=false
"""
import json
import subprocess
import sys
from pathlib import Path


# Module-scope repo root — the quoin/ git repo root (mirrors test_runtime_portability_docs.py line 6)
# parents[0]=tests/, parents[1]=dev/, parents[2]=quoin/ (package), parents[3]=quoin/ (git root)
REPO_ROOT = Path(__file__).resolve().parents[3]

# Canonical core script path (used by all subprocess calls)
# Script is at <repo_root>/quoin/core/scripts/validate_adapter_drift.py
SCRIPT = REPO_ROOT / "quoin" / "core" / "scripts" / "validate_adapter_drift.py"


# ---------------------------------------------------------------------------
# Minimal valid manifest for synthetic tests
# ---------------------------------------------------------------------------
_MINIMAL_MANIFEST = {
    "schema_version": 2,
    "skills": [
        {
            "name": "foo",
            "phase": "test",
            "effort": "low",
            "user_facing": True,
            "claude_model": "opus",
            "section_0": False,
            "spawn_target": False,
        }
    ],
}

# Minimal valid adapter SKILL.md for "foo" — frontmatter + pointer + body
_ADAPTER_FRONTMATTER = "\nname: foo\nmodel: opus\n"
_ADAPTER_BODY = (
    "*Portable intent doc: `quoin/core/skills/foo.md`*\n\n"
    "# Foo skill\n\n"
    "This is the adapter implementation. It is longer than the stub.\n"
    "More content here to ensure stub-shorter invariant is satisfied.\n"
    "Even more content to make this definitely longer than the stub.\n"
)
_ADAPTER_FULL = f"---{_ADAPTER_FRONTMATTER}---\n{_ADAPTER_BODY}"

# Minimal legacy stub — same frontmatter, shorter body
_STUB_FULL = f"---{_ADAPTER_FRONTMATTER}---\n*See adapter for full implementation.*\n"

# Minimal install.sh — ADAPTER_FOO_SRC= before the for-loop, with elif branch inside
_INSTALL_SH = (
    "#!/usr/bin/env bash\n"
    'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
    'ADAPTER_FOO_SRC="$SCRIPT_DIR/adapters/claude/skills/foo/SKILL.md"\n'
    "\n"
    'for skill_dir in "$SCRIPT_DIR/skills"/*/; do\n'
    '    skill_name=$(basename "$skill_dir")\n'
    '    if [ "$skill_name" = "capture_insight" ]; then\n'
    '        cp "$ADAPTER_CAPTURE_INSIGHT_SRC" "$skill_dir/SKILL.md"\n'
    '    elif [ "$skill_name" = "foo" ]; then\n'
    '        cp "$ADAPTER_FOO_SRC" "$skill_dir/SKILL.md"\n'
    "    fi\n"
    "done\n"
)


# ---------------------------------------------------------------------------
# Helper: build a minimal synthetic repo under tmp_path
# ---------------------------------------------------------------------------

def _make_minimal_repo(tmp_path: Path) -> Path:
    """Create a minimal valid repo layout for skill 'foo' under tmp_path.

    Directory tree:
        <tmp>/quoin/core/skills/foo.md
        <tmp>/quoin/adapters/claude/skills/foo/SKILL.md
        <tmp>/quoin/skills/foo/SKILL.md
        <tmp>/quoin/core/workflow/skills.json
        <tmp>/quoin/install.sh
    """
    # Core skill doc
    core_dir = tmp_path / "quoin" / "core" / "skills"
    core_dir.mkdir(parents=True)
    (core_dir / "foo.md").write_text(
        "# Foo portable intent doc\n\nThis is the portable intent.\n",
        encoding="utf-8",
    )

    # Adapter SKILL.md
    adapter_dir = tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo"
    adapter_dir.mkdir(parents=True)
    (adapter_dir / "SKILL.md").write_text(_ADAPTER_FULL, encoding="utf-8")

    # Legacy stub SKILL.md
    stub_dir = tmp_path / "quoin" / "skills" / "foo"
    stub_dir.mkdir(parents=True)
    (stub_dir / "SKILL.md").write_text(_STUB_FULL, encoding="utf-8")

    # Manifest
    manifest_dir = tmp_path / "quoin" / "core" / "workflow"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "skills.json").write_text(
        json.dumps(_MINIMAL_MANIFEST, indent=2), encoding="utf-8"
    )

    # install.sh
    (tmp_path / "quoin" / "install.sh").write_text(_INSTALL_SH, encoding="utf-8")

    return tmp_path


def _run(repo_root: Path, *extra_args: str) -> subprocess.CompletedProcess:
    """Run the validator against the given repo root."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(repo_root), *extra_args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Positive tests
# ---------------------------------------------------------------------------

def test_validator_passes_on_live_repo():
    """Gold-master test: validator exits 0 against the real live repo.

    This also validates:
    - AD-IE relaxed check handles capture_insight's leading 'if' form
    - AD-PT substring check handles revise-fast's See-also form
    """
    result = _run(REPO_ROOT)
    assert result.returncode == 0, (
        f"Validator failed on live repo (exit {result.returncode}):\n{result.stderr}"
    )
    assert result.stderr == "", (
        f"Validator emitted unexpected stderr on live repo:\n{result.stderr}"
    )


def test_validator_passes_on_minimal_repo(tmp_path):
    """Validator exits 0 on a correctly constructed minimal synthetic repo."""
    _make_minimal_repo(tmp_path)
    result = _run(tmp_path)
    assert result.returncode == 0, (
        f"Validator failed on minimal repo (exit {result.returncode}):\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Negative tests — one invariant violation per test
# ---------------------------------------------------------------------------

def test_drift_co_detected(tmp_path):
    """AD-CO: missing core doc is detected."""
    _make_minimal_repo(tmp_path)
    (tmp_path / "quoin" / "core" / "skills" / "foo.md").unlink()
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-CO foo:" in result.stderr


def test_drift_ad_detected(tmp_path):
    """AD-AD: missing adapter SKILL.md is detected."""
    _make_minimal_repo(tmp_path)
    (tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo" / "SKILL.md").unlink()
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-AD foo:" in result.stderr


def test_drift_ls_detected(tmp_path):
    """AD-LS: missing legacy stub is detected."""
    _make_minimal_repo(tmp_path)
    (tmp_path / "quoin" / "skills" / "foo" / "SKILL.md").unlink()
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-LS foo:" in result.stderr


def test_drift_fn_detected(tmp_path):
    """AD-FN: adapter frontmatter name mismatch is detected."""
    _make_minimal_repo(tmp_path)
    adapter_path = tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo" / "SKILL.md"
    content = adapter_path.read_text(encoding="utf-8")
    # Change name field to wrong value — stub still has original so FB will also fire
    # but we assert AD-FN specifically
    adapter_path.write_text(content.replace("name: foo", "name: wrong"), encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-FN foo:" in result.stderr


def test_drift_fm_detected(tmp_path):
    """AD-FM: adapter frontmatter model mismatch is detected."""
    _make_minimal_repo(tmp_path)
    adapter_path = tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo" / "SKILL.md"
    content = adapter_path.read_text(encoding="utf-8")
    # Change model from 'opus' to 'haiku' — mismatches manifest's claude_model=opus
    adapter_path.write_text(content.replace("model: opus", "model: haiku"), encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-FM foo:" in result.stderr


def test_drift_pt_detected(tmp_path):
    """AD-PT: missing pointer text substring is detected."""
    _make_minimal_repo(tmp_path)
    adapter_path = tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo" / "SKILL.md"
    content = adapter_path.read_text(encoding="utf-8")
    # Remove the pointer text so 'quoin/core/skills/foo.md' no longer appears
    adapter_path.write_text(
        content.replace("quoin/core/skills/foo.md", "quoin/core/skills/other.md"),
        encoding="utf-8",
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-PT foo:" in result.stderr


def test_drift_fb_detected(tmp_path):
    """AD-FB: stub frontmatter not byte-equal to adapter frontmatter is detected."""
    _make_minimal_repo(tmp_path)
    stub_path = tmp_path / "quoin" / "skills" / "foo" / "SKILL.md"
    # Change stub frontmatter so it no longer byte-equals adapter frontmatter
    stub_path.write_text(
        f"---\nname: foo\nmodel: opus\nextra_field: added\n---\n"
        "*See adapter for full implementation.*\n",
        encoding="utf-8",
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-FB foo:" in result.stderr


def test_drift_ss_detected(tmp_path):
    """AD-SS: stub longer than adapter is detected."""
    _make_minimal_repo(tmp_path)
    stub_path = tmp_path / "quoin" / "skills" / "foo" / "SKILL.md"
    adapter_path = tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo" / "SKILL.md"
    adapter_size = len(adapter_path.read_text(encoding="utf-8"))
    # Write a stub that is larger than the adapter
    big_stub = _STUB_FULL + ("x" * (adapter_size + 100))
    stub_path.write_text(big_stub, encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-SS foo:" in result.stderr


def test_drift_s0p_detected(tmp_path):
    """AD-S0P: manifest declares section_0=true but adapter lacks §0 block."""
    _make_minimal_repo(tmp_path)
    # Set section_0=true in manifest for foo
    manifest_path = tmp_path / "quoin" / "core" / "workflow" / "skills.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["skills"][0]["section_0"] = True
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Adapter does NOT have the §0 block (minimal adapter has none)
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-S0P foo:" in result.stderr


def test_drift_s0a_detected(tmp_path):
    """AD-S0A: manifest declares section_0=false but adapter HAS §0 block."""
    _make_minimal_repo(tmp_path)
    # Add §0 block to adapter while manifest says section_0=false (default)
    adapter_path = tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo" / "SKILL.md"
    content = adapter_path.read_text(encoding="utf-8")
    adapter_path.write_text(
        content + "\n## §0 Model dispatch (FIRST STEP — execute before anything else)\n\nDispatch block.\n",
        encoding="utf-8",
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-S0A foo:" in result.stderr


def test_drift_pe_detected(tmp_path):
    """AD-PE: spawn_target=true but no preamble.md in legacy stub dir."""
    _make_minimal_repo(tmp_path)
    # Mark foo as spawn_target=true in manifest
    manifest_path = tmp_path / "quoin" / "core" / "workflow" / "skills.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["skills"][0]["spawn_target"] = True
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # No preamble.md in stub dir
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-PE foo:" in result.stderr


def test_drift_pa_detected(tmp_path):
    """AD-PA: spawn_target=true and preamble.md also in adapter folder."""
    _make_minimal_repo(tmp_path)
    # Mark foo as spawn_target=true
    manifest_path = tmp_path / "quoin" / "core" / "workflow" / "skills.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    data["skills"][0]["spawn_target"] = True
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    # Put preamble.md in stub dir (so AD-PE passes)
    (tmp_path / "quoin" / "skills" / "foo" / "preamble.md").write_text(
        "# preamble\n", encoding="utf-8"
    )
    # Also put preamble.md in adapter dir (violates AD-PA)
    (tmp_path / "quoin" / "adapters" / "claude" / "skills" / "foo" / "preamble.md").write_text(
        "# preamble\n", encoding="utf-8"
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-PA foo:" in result.stderr


def test_drift_px_detected(tmp_path):
    """AD-PX: spawn_target=false but preamble.md exists in legacy stub dir."""
    _make_minimal_repo(tmp_path)
    # foo is spawn_target=false (default); add preamble.md in stub dir anyway
    (tmp_path / "quoin" / "skills" / "foo" / "preamble.md").write_text(
        "# preamble\n", encoding="utf-8"
    )
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-PX foo:" in result.stderr


def test_drift_iv_detected(tmp_path):
    """AD-IV: ADAPTER_FOO_SRC= missing from install.sh."""
    _make_minimal_repo(tmp_path)
    install_path = tmp_path / "quoin" / "install.sh"
    content = install_path.read_text(encoding="utf-8")
    # Remove the ADAPTER_FOO_SRC= line
    new_content = "\n".join(
        line for line in content.splitlines()
        if "ADAPTER_FOO_SRC=" not in line
    )
    install_path.write_text(new_content, encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-IV foo:" in result.stderr


def test_drift_ie_detected(tmp_path):
    """AD-IE: if/elif branch for 'foo' removed from install.sh entirely."""
    _make_minimal_repo(tmp_path)
    install_path = tmp_path / "quoin" / "install.sh"
    content = install_path.read_text(encoding="utf-8")
    # Remove the elif branch for foo entirely
    new_content = "\n".join(
        line for line in content.splitlines()
        if '"foo"' not in line and "ADAPTER_FOO_SRC" not in line
    )
    install_path.write_text(new_content, encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-IE foo:" in result.stderr


def test_drift_io_detected(tmp_path):
    """AD-IO: ADAPTER_FOO_SRC= placed after the for-loop start."""
    _make_minimal_repo(tmp_path)
    install_path = tmp_path / "quoin" / "install.sh"
    # Rearrange so ADAPTER_FOO_SRC= comes after the for-loop
    reordered = (
        "#!/usr/bin/env bash\n"
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        "\n"
        'for skill_dir in "$SCRIPT_DIR/skills"/*/; do\n'
        '    skill_name=$(basename "$skill_dir")\n'
        '    if [ "$skill_name" = "capture_insight" ]; then\n'
        '        cp "$ADAPTER_CAPTURE_INSIGHT_SRC" "$skill_dir/SKILL.md"\n'
        '    elif [ "$skill_name" = "foo" ]; then\n'
        '        cp "$ADAPTER_FOO_SRC" "$skill_dir/SKILL.md"\n'
        "    fi\n"
        "done\n"
        "\n"
        '# Preflight after for-loop (wrong position)\n'
        'ADAPTER_FOO_SRC="$SCRIPT_DIR/adapters/claude/skills/foo/SKILL.md"\n'
    )
    install_path.write_text(reordered, encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 2
    assert "DRIFT AD-IO foo:" in result.stderr


# ---------------------------------------------------------------------------
# JSON output tests
# ---------------------------------------------------------------------------

def test_json_output_is_valid(tmp_path):
    """--json flag produces valid JSON with a 'violations' key."""
    _make_minimal_repo(tmp_path)
    # Delete core doc to force a violation
    (tmp_path / "quoin" / "core" / "skills" / "foo.md").unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    parsed = json.loads(result.stdout)
    assert "violations" in parsed
    assert isinstance(parsed["violations"], list)


def test_json_output_contains_invariant_and_skill_fields(tmp_path):
    """Each violation object has 'invariant', 'skill', and 'detail' keys."""
    _make_minimal_repo(tmp_path)
    (tmp_path / "quoin" / "core" / "skills" / "foo.md").unlink()
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo-root", str(tmp_path), "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    parsed = json.loads(result.stdout)
    assert len(parsed["violations"]) > 0
    for v in parsed["violations"]:
        assert "invariant" in v, f"Missing 'invariant' key in violation: {v}"
        assert "skill" in v, f"Missing 'skill' key in violation: {v}"
        assert "detail" in v, f"Missing 'detail' key in violation: {v}"


# ---------------------------------------------------------------------------
# Error-handling tests
# ---------------------------------------------------------------------------

def test_unreadable_manifest_returns_65():
    """Non-existent manifest path causes exit 65 (DATA error)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--manifest", "/nonexistent/path/skills.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 65


def test_bad_cli_args_return_64():
    """Unknown CLI flag causes exit 64 (USAGE error)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--frobnicate"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 64


def test_validator_handles_missing_optional_fields(tmp_path):
    """Skills.json entries without section_0/spawn_target default to false; no exception raised."""
    _make_minimal_repo(tmp_path)
    # Remove optional fields from manifest
    manifest_path = tmp_path / "quoin" / "core" / "workflow" / "skills.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    for skill in data["skills"]:
        skill.pop("section_0", None)
        skill.pop("spawn_target", None)
    manifest_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    result = _run(tmp_path)
    # Should pass (defaults to false for both, which matches the minimal adapter)
    assert result.returncode == 0, (
        f"Validator raised with missing optional fields (exit {result.returncode}):\n{result.stderr}"
    )
