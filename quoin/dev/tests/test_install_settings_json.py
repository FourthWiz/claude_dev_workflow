"""T-06 — pytest coverage for settings.json backup, validation, and restore behavior.

Tests for phase-31-settings-json-cleanup:
  - T-01: pre-merge backup of valid settings.json
  - T-02: post-merge JSON validation + auto-restore on failure + SystemExit(1)
  - T-05: init_workflow Step 4 snippet handles corrupt settings.json

All tests use tmp_path to isolate writes; never touch real ~/.claude.
"""
import ast
import json
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_MD = REPO_ROOT / "quoin" / "skills" / "init_workflow" / "SKILL.md"


def _fake_source_dir(tmp: Path) -> Path:
    """Return tmp/src with stub hook scripts under tmp/src/hooks/."""
    hooks_dir = tmp / "hooks"
    hooks_dir.mkdir(parents=True)
    for fname in (
        "userpromptsubmit.sh",
        "precompact.sh",
        "postcompact.sh",
        "sessionstart.sh",
        "sessionend.sh",
        "_lib.sh",
    ):
        (hooks_dir / fname).write_text("#!/bin/bash\n")
    return tmp


# ── T-01 tests ────────────────────────────────────────────────────────────────


def test_existing_valid_settings_backed_up_before_merge(tmp_path):
    """Pre-merge backup is created when settings.json already exists and is valid."""
    from quoin import installer  # noqa: PLC0415

    src = _fake_source_dir(tmp_path / "src")
    dest = tmp_path / ".claude"
    dest.mkdir(parents=True)

    original_content = json.dumps({"my-key": "my-value"})
    settings_path = dest / "settings.json"
    settings_path.write_text(original_content)

    installer.deploy_hooks(src, dest)

    bak_files = list(dest.glob("settings.json.bak-*"))
    assert len(bak_files) == 1, f"Expected 1 .bak-* file, found: {bak_files}"
    assert bak_files[0].read_text() == original_content, (
        "Backup does not contain the original settings.json content"
    )


def test_corrupt_settings_backed_up_and_merge_proceeds(tmp_path):
    """Corrupt settings.json is backed up and a fresh valid file is written."""
    from quoin import installer  # noqa: PLC0415

    src = _fake_source_dir(tmp_path / "src")
    dest = tmp_path / ".claude"
    dest.mkdir(parents=True)

    settings_path = dest / "settings.json"
    settings_path.write_text("{not valid json")

    installer.deploy_hooks(src, dest)

    bak_files = list(dest.glob("settings.json.bak-*"))
    assert len(bak_files) == 1, f"Expected 1 .bak-* file, found: {bak_files}"
    assert bak_files[0].read_text() == "{not valid json"

    # A new valid settings.json must have been written
    result = json.loads(settings_path.read_text())
    assert "hooks" in result, "New settings.json must contain hooks key"


def test_no_existing_settings_no_backup_no_error(tmp_path):
    """When settings.json doesn't exist, no backup is created and file is written."""
    from quoin import installer  # noqa: PLC0415

    src = _fake_source_dir(tmp_path / "src")
    dest = tmp_path / ".claude"

    installer.deploy_hooks(src, dest)

    bak_files = list(dest.glob("settings.json.bak-*"))
    assert len(bak_files) == 0, f"No backup expected for fresh install, found: {bak_files}"

    settings_path = dest / "settings.json"
    assert settings_path.exists(), "settings.json should be written on fresh install"
    result = json.loads(settings_path.read_text())
    assert "hooks" in result


# ── T-02 tests ────────────────────────────────────────────────────────────────


def test_post_merge_validation_smoke(tmp_path):
    """Two sequential deploy_hooks calls produce identical valid JSON (idempotency at bytes level)."""
    from quoin import installer  # noqa: PLC0415

    src = _fake_source_dir(tmp_path / "src")
    dest = tmp_path / ".claude"

    installer.deploy_hooks(src, dest)
    settings_path = dest / "settings.json"
    before = settings_path.read_text()

    installer.deploy_hooks(src, dest)
    after = settings_path.read_text()

    # Both runs must produce valid JSON
    json.loads(before)
    json.loads(after)

    assert before == after, (
        "deploy_hooks is not idempotent at bytes level — output changed on second run"
    )


def test_idempotent_six_stanzas(tmp_path):
    """Two deploy_hooks calls produce exactly 6 stanzas (no duplication)."""
    from quoin import installer  # noqa: PLC0415

    src = _fake_source_dir(tmp_path / "src")
    dest = tmp_path / ".claude"

    installer.deploy_hooks(src, dest)
    installer.deploy_hooks(src, dest)

    settings = json.loads((dest / "settings.json").read_text())
    hooks = settings.get("hooks", {})

    # Expected stanza counts per event key
    assert len(hooks.get("UserPromptSubmit", [])) == 1, "Expected 1 UserPromptSubmit stanza"
    assert len(hooks.get("PreCompact", [])) == 1, "Expected 1 PreCompact stanza"
    assert len(hooks.get("PostCompact", [])) == 1, "Expected 1 PostCompact stanza"
    assert len(hooks.get("SessionStart", [])) == 2, "Expected 2 SessionStart stanzas (startup+resume)"
    assert len(hooks.get("SessionEnd", [])) == 1, "Expected 1 SessionEnd stanza"

    # Total count across all events: 1+1+1+2+1 = 6
    total = sum(len(v) for v in hooks.values())
    assert total == 6, f"Expected 6 total stanzas across all events, got {total}"


def test_post_merge_validation_failure_restores_backup(tmp_path, monkeypatch):
    """When json.dump writes garbage, SystemExit(1) is raised and backup is restored."""
    from quoin import installer  # noqa: PLC0415

    src = _fake_source_dir(tmp_path / "src")
    dest = tmp_path / ".claude"
    dest.mkdir(parents=True)

    original_content = json.dumps({"existing-key": "preserved-value"}) + "\n"
    settings_path = dest / "settings.json"
    settings_path.write_text(original_content)

    # Monkeypatch json.dump at the module attribute so T-01 backup runs first,
    # then the write produces invalid JSON that fails T-02 validation.
    monkeypatch.setattr(
        "quoin.installer.json.dump",
        lambda obj, f, **kw: f.write("{not json"),
    )

    with pytest.raises(SystemExit) as exc_info:
        installer.deploy_hooks(src, dest)

    assert exc_info.value.code == 1, (
        f"Expected SystemExit(1), got SystemExit({exc_info.value.code})"
    )

    # File must be restored to original content
    restored = settings_path.read_text()
    assert restored == original_content, (
        f"settings.json was not restored from backup.\nGot: {restored!r}\nExpected: {original_content!r}"
    )

    # The timestamped backup must still exist
    bak_files = list(dest.glob("settings.json.bak-*"))
    assert len(bak_files) == 1, f"Expected backup to survive, found: {bak_files}"


# ── T-05 tests ────────────────────────────────────────────────────────────────


def _extract_python_snippet_from_init_workflow() -> str:
    """Extract the python-fenced code block from init_workflow/SKILL.md Step 4."""
    text = SKILL_MD.read_text()
    match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
    assert match is not None, (
        f"Could not find a ```python...``` fenced block in {SKILL_MD}. "
        "Step 4 must contain a python-fenced snippet."
    )
    return match.group(1)


def test_init_workflow_snippet_handles_corrupt_settings(tmp_path):
    """The Step 4 python snippet is syntactically valid and handles corrupt settings.json."""
    snippet = _extract_python_snippet_from_init_workflow()

    # Assert syntactic validity first (fast, no side-effects)
    try:
        ast.parse(snippet)
    except SyntaxError as exc:
        pytest.fail(f"Step 4 python snippet has a syntax error: {exc}\nSnippet:\n{snippet}")

    # Set up a tmp_path with a corrupt .claude/settings.json
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir(parents=True)
    settings_path = claude_dir / "settings.json"
    settings_path.write_text("{not json")

    # exec the snippet with path pointing into our tmp_path
    exec_globals: dict = {}
    exec_locals: dict = {"__builtins__": __builtins__}

    # The snippet uses relative path ".claude/settings.json"; run from tmp_path
    import os

    orig_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        exec(snippet, exec_globals, exec_locals)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            f"Step 4 snippet raised an unexpected exception on corrupt settings.json: {exc}"
        )
    finally:
        os.chdir(orig_cwd)

    # (a) No exception propagated (handled above)

    # (b) A backup file must exist alongside settings.json
    bak_files = list(claude_dir.glob("settings.json.bak-*"))
    assert len(bak_files) == 1, (
        f"Expected 1 settings.json.bak-* backup after corrupt-load, found: {bak_files}"
    )

    # (c) A new valid settings.json must have been written
    assert settings_path.exists(), "settings.json must be (re)written after corrupt-load"
    try:
        written = json.loads(settings_path.read_text())
    except json.JSONDecodeError as exc:
        pytest.fail(f"Step 4 wrote invalid JSON to settings.json: {exc}")

    assert "permissions" in written, (
        "Expected 'permissions' key in settings.json written by Step 4 snippet"
    )
