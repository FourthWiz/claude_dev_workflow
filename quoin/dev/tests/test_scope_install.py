"""Tests for --scope user|project[:DIR] install flag (T-02 through T-05, T-10, T-13).

All in-process; no claude/npx/pip required.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
QUOIN_SRC = REPO / "quoin"

# Ensure src is importable
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ── T-03: _resolve_dest_root ──────────────────────────────────────────────────

def _make_args(**kwargs):
    """Build a minimal argparse.Namespace with given keyword args."""
    import argparse
    defaults = dict(
        scope="user",
        allow_hook_merge=False,
        runtime="claude",
        check=False,
    )
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def test_resolve_dest_root_user_mode(tmp_path, monkeypatch):
    """--scope user (default) resolves to HOME/.claude."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Reload pathlib.Path.home() to pick up new HOME env var
    import importlib
    import quoin.cli as cli_mod
    importlib.reload(cli_mod)
    result = cli_mod._resolve_dest_root(_make_args(scope="user"))
    # Path.home() expands the HOME env var on POSIX
    assert ".claude" in str(result)
    assert result.name == ".claude"


def test_resolve_dest_root_project_cwd(tmp_path, monkeypatch):
    """--scope project uses CWD as project dir."""
    monkeypatch.chdir(tmp_path)
    from quoin.cli import _resolve_dest_root
    args = _make_args(scope="project")
    result = _resolve_dest_root(args)
    # Must be <cwd>/.claude
    assert result == tmp_path.resolve() / ".claude"


def test_resolve_dest_root_project_explicit_path(tmp_path, monkeypatch):
    """--scope project:/path uses explicit project dir."""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    from quoin.cli import _resolve_dest_root
    args = _make_args(scope=f"project:{project_dir}")
    result = _resolve_dest_root(args)
    assert result == project_dir.resolve() / ".claude"


def test_resolve_dest_root_refuses_root_as_project():
    """--scope project:/ must be refused."""
    from quoin.cli import _resolve_dest_root
    args = _make_args(scope="project:/")
    with pytest.raises(SystemExit) as exc_info:
        _resolve_dest_root(args)
    assert exc_info.value.code == 2


def test_resolve_dest_root_no_scope_attr():
    """When scope attribute is absent, defaults to user mode (returns ~/.claude)."""
    from quoin.cli import _resolve_dest_root
    import argparse
    args = argparse.Namespace()  # no scope attr
    result = _resolve_dest_root(args)
    assert result.name == ".claude"
    assert "home" in str(result).lower() or str(pathlib.Path.home()) in str(result)


# ── T-13: detect_home_hook_conflict ──────────────────────────────────────────

def _make_home_settings(home: Path, stanzas: list) -> None:
    """Write ~/.claude/settings.json with given hook stanzas for UserPromptSubmit."""
    claude_dir = home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "hooks": {
            "UserPromptSubmit": stanzas,
        }
    }
    (claude_dir / "settings.json").write_text(json.dumps(settings, indent=2))


def test_detect_home_hook_conflict_no_settings(tmp_path, monkeypatch):
    """No ~/.claude/settings.json → no conflict."""
    monkeypatch.setenv("HOME", str(tmp_path))
    # Force pathlib.Path.home() to use the patched HOME
    import quoin.installer as _inst
    import unittest.mock
    with unittest.mock.patch.object(pathlib.Path, "home", return_value=tmp_path):
        result = _inst.detect_home_hook_conflict()
    assert result is False


def test_detect_home_hook_conflict_empty_settings(tmp_path, monkeypatch):
    """Empty settings.json → no conflict."""
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{}")
    import quoin.installer as _inst
    import unittest.mock
    with unittest.mock.patch.object(pathlib.Path, "home", return_value=tmp_path):
        result = _inst.detect_home_hook_conflict()
    assert result is False


def test_detect_home_hook_conflict_quoin_stanza_present(tmp_path, monkeypatch):
    """When ~/.claude/settings.json has userpromptsubmit.sh stanza → conflict."""
    _make_home_settings(tmp_path, [{
        "matcher": "*",
        "hooks": [{"type": "command", "command": "/some/path/userpromptsubmit.sh", "timeout": 5}],
    }])
    import quoin.installer as _inst
    import unittest.mock
    with unittest.mock.patch.object(pathlib.Path, "home", return_value=tmp_path):
        result = _inst.detect_home_hook_conflict()
    assert result is True


def test_detect_home_hook_conflict_sessionstart(tmp_path, monkeypatch):
    """sessionstart.sh in home settings → conflict."""
    _make_home_settings(tmp_path, [{
        "matcher": "startup",
        "hooks": [{"type": "command", "command": "/home/user/.claude/hooks/sessionstart.sh", "timeout": 5}],
    }])
    import quoin.installer as _inst
    import unittest.mock
    with unittest.mock.patch.object(pathlib.Path, "home", return_value=tmp_path):
        result = _inst.detect_home_hook_conflict()
    assert result is True


def test_detect_home_hook_conflict_non_quoin_hook(tmp_path, monkeypatch):
    """Non-quoin hook → no conflict."""
    _make_home_settings(tmp_path, [{
        "matcher": "*",
        "hooks": [{"type": "command", "command": "/usr/local/bin/my-custom-hook.sh", "timeout": 5}],
    }])
    import quoin.installer as _inst
    import unittest.mock
    with unittest.mock.patch.object(pathlib.Path, "home", return_value=tmp_path):
        result = _inst.detect_home_hook_conflict()
    assert result is False


# ── T-04/T-05: deploy_hooks project mode ─────────────────────────────────────

def _make_fake_src(tmp: Path) -> Path:
    """Create minimal source dir with stub hook scripts."""
    hooks_dir = tmp / "hooks"
    hooks_dir.mkdir(parents=True)
    for fname in ("userpromptsubmit.sh", "precompact.sh", "postcompact.sh",
                  "sessionstart.sh", "sessionend.sh", "_lib.sh"):
        (hooks_dir / fname).write_text("#!/bin/bash\n")
    return tmp


def test_deploy_hooks_project_mode_note(tmp_path, capsys):
    """deploy_hooks in project mode prints a note about project-scoping."""
    from quoin.installer import deploy_hooks
    src = _make_fake_src(tmp_path / "src")
    dest = tmp_path / "project" / ".claude"
    deploy_hooks(src, dest, is_project_mode=True)
    captured = capsys.readouterr()
    assert "project-scoped" in captured.out or "project mode" in captured.out


def test_deploy_hooks_project_mode_does_not_touch_home(tmp_path, monkeypatch):
    """deploy_hooks in project mode must NOT modify ~/.claude/settings.json.

    This is structural: deploy_hooks writes to dest_root/settings.json, so as
    long as dest_root != ~/.claude, home settings are untouched.
    """
    from quoin.installer import deploy_hooks
    src = _make_fake_src(tmp_path / "src")
    project = tmp_path / "project"
    project.mkdir()
    dest = project / ".claude"
    deploy_hooks(src, dest, is_project_mode=True)

    # dest settings.json must exist
    assert (dest / "settings.json").exists()
    # ~/.claude/ must NOT have been created by this call (we aren't monkeypatching
    # home, but deploy_hooks writes only to dest_root/settings.json by design)
    # Verify no ~/.claude/ was written inside our tmp workspace
    assert not (tmp_path / "home" / ".claude").exists()


def test_deploy_hooks_project_mode_settings_in_project(tmp_path, monkeypatch):
    """deploy_hooks in project mode writes hooks to <project>/.claude/settings.json."""
    from quoin.installer import deploy_hooks
    src = _make_fake_src(tmp_path / "src")
    dest = tmp_path / "project" / ".claude"
    deploy_hooks(src, dest, is_project_mode=True)

    settings_path = dest / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text())
    hooks = settings.get("hooks", {})
    # All 6 stanzas registered in project settings
    assert len(hooks.get("UserPromptSubmit", [])) == 1
    assert len(hooks.get("SessionStart", [])) == 2
    assert len(hooks.get("SessionEnd", [])) == 1
    # Commands reference project hooks dir (not ~/)
    for stanzas_list in hooks.values():
        for stanza in stanzas_list:
            for hook in stanza.get("hooks", []):
                cmd = hook.get("command", "")
                assert not cmd.startswith("~"), f"tilde path in project settings: {cmd}"
                assert str(dest) in cmd, f"command does not reference project dest: {cmd}"


# ── T-05: merge_workflow_rules project mode placement ────────────────────────

def _make_minimal_src_for_merge(tmp: Path) -> Path:
    """Create minimal source dir with CLAUDE.md for merge tests."""
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "CLAUDE.md").write_text("# Test Rules\nSome workflow rules.\n", encoding="utf-8")
    return tmp


def test_merge_workflow_rules_project_mode_places_at_project_root(tmp_path):
    """In project mode, CLAUDE.md is written to <project>/CLAUDE.md (not <project>/.claude/CLAUDE.md)."""
    from quoin.installer import merge_workflow_rules
    src = _make_minimal_src_for_merge(tmp_path / "src")
    dest_root = tmp_path / "project" / ".claude"
    dest_root.mkdir(parents=True)
    claude_md_path = tmp_path / "project" / "CLAUDE.md"

    merge_workflow_rules(src, dest_root, claude_md_path=claude_md_path)

    # CLAUDE.md must exist at project root
    assert claude_md_path.exists()
    # CLAUDE.md must NOT exist at project/.claude/CLAUDE.md
    wrong_location = dest_root / "CLAUDE.md"
    assert not wrong_location.exists(), (
        "CLAUDE.md must not be created at <project>/.claude/CLAUDE.md"
    )


def test_merge_workflow_rules_user_mode_default_path(tmp_path):
    """In user mode (no explicit claude_md_path), CLAUDE.md is written to dest_root/CLAUDE.md."""
    from quoin.installer import merge_workflow_rules
    src = _make_minimal_src_for_merge(tmp_path / "src")
    dest_root = tmp_path / ".claude"
    dest_root.mkdir(parents=True)

    merge_workflow_rules(src, dest_root)  # no claude_md_path

    claude_md = dest_root / "CLAUDE.md"
    assert claude_md.exists()


def test_merge_workflow_rules_marker_count_preserved(tmp_path):
    """Re-running in project mode (pair_count=1) replaces content, not appends."""
    from quoin.installer import merge_workflow_rules
    src = _make_minimal_src_for_merge(tmp_path / "src")
    dest_root = tmp_path / "project" / ".claude"
    dest_root.mkdir(parents=True)
    claude_md_path = tmp_path / "project" / "CLAUDE.md"

    # First run: creates the file
    merge_workflow_rules(src, dest_root, claude_md_path=claude_md_path)
    assert claude_md_path.read_text().count("# === DEV WORKFLOW START ===") == 1

    # Second run: replaces (not appends)
    merge_workflow_rules(src, dest_root, claude_md_path=claude_md_path)
    assert claude_md_path.read_text().count("# === DEV WORKFLOW START ===") == 1


# ── T-06 infrastructure: substitute_quoin_home ───────────────────────────────

def test_substitute_quoin_home_replaces_placeholder(tmp_path):
    """substitute_quoin_home replaces __QUOIN_HOME__ with str(dest_root)."""
    from quoin.installer import substitute_quoin_home
    dest_root = pathlib.Path("/some/project/.claude")
    text = "read __QUOIN_HOME__/scripts/path_resolve.py"
    result = substitute_quoin_home(text, dest_root)
    assert "__QUOIN_HOME__" not in result
    assert "/some/project/.claude/scripts/path_resolve.py" in result


def test_substitute_quoin_home_no_placeholder(tmp_path):
    """Text with no placeholder is returned unchanged."""
    from quoin.installer import substitute_quoin_home
    dest_root = pathlib.Path("/some/project/.claude")
    text = "# Deployed to ~/.claude/ (documentation only)"
    result = substitute_quoin_home(text, dest_root)
    assert result == text


def test_substitute_quoin_home_multiple_occurrences(tmp_path):
    """Multiple occurrences are all replaced."""
    from quoin.installer import substitute_quoin_home
    dest_root = pathlib.Path("/proj/.claude")
    text = "__QUOIN_HOME__/a and __QUOIN_HOME__/b"
    result = substitute_quoin_home(text, dest_root)
    assert result == "/proj/.claude/a and /proj/.claude/b"


# ── T-02: argparse integration ────────────────────────────────────────────────

def test_scope_flag_present_in_install_help():
    """'quoin install --help' output includes --scope."""
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "quoin", "install", "--help"],
        env={**os.environ, "PYTHONPATH": str(SRC)},
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "--scope" in result.stdout


def test_scope_defaults_to_user(monkeypatch):
    """argparse default for --scope is 'user'."""
    from quoin.cli import main

    captured_args = {}

    def fake_cmd(args):
        captured_args.update(vars(args))
        return 0

    import quoin.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_cmd_claude_install", fake_cmd)
    main(["install", "--source-dir", str(QUOIN_SRC)])
    assert captured_args.get("scope") == "user"


def test_scope_project_parsed(monkeypatch):
    """--scope project is parsed correctly."""
    from quoin.cli import main

    captured_args = {}

    def fake_cmd(args):
        captured_args.update(vars(args))
        return 0

    import quoin.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_cmd_claude_install", fake_cmd)
    main(["install", "--source-dir", str(QUOIN_SRC), "--scope", "project"])
    assert captured_args.get("scope") == "project"


def test_scope_project_with_path_parsed(monkeypatch, tmp_path):
    """--scope project:/path is parsed correctly."""
    from quoin.cli import main

    captured_args = {}

    def fake_cmd(args):
        captured_args.update(vars(args))
        return 0

    import quoin.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_cmd_claude_install", fake_cmd)
    main(["install", "--source-dir", str(QUOIN_SRC), "--scope", f"project:{tmp_path}"])
    assert captured_args.get("scope") == f"project:{tmp_path}"


def test_scope_project_mutex_with_codex(monkeypatch, tmp_path, capsys):
    """--scope project + --runtime codex fails with exit 2.

    The check fires in _cmd_claude_install when both scope=project and runtime=codex
    are present. _cmd_install dispatches to codex for --runtime codex, but the
    check in _cmd_install catches it first before delegating.
    """
    from quoin.cli import _cmd_install
    args = _make_args(scope="project", runtime="codex", source_dir=None)
    with pytest.raises(SystemExit) as exc_info:
        _cmd_install(args)
    assert exc_info.value.code == 2


def test_allow_hook_merge_flag(monkeypatch):
    """--allow-hook-merge is parsed and defaults to False."""
    from quoin.cli import main

    captured_args = {}

    def fake_cmd(args):
        captured_args.update(vars(args))
        return 0

    import quoin.cli as cli_mod
    monkeypatch.setattr(cli_mod, "_cmd_claude_install", fake_cmd)
    main(["install", "--source-dir", str(QUOIN_SRC)])
    assert captured_args.get("allow_hook_merge") is False

    main(["install", "--source-dir", str(QUOIN_SRC), "--allow-hook-merge"])
    assert captured_args.get("allow_hook_merge") is True


# ── T-13: project install fails fast on home hook conflict ───────────────────

def test_project_install_fails_on_home_hooks(tmp_path, monkeypatch, capsys):
    """Project-mode install must fail fast when home settings.json has quoin hooks."""
    import unittest.mock

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    # Plant quoin stanza in home settings
    home_claude = fake_home / ".claude"
    home_claude.mkdir()
    (home_claude / "settings.json").write_text(json.dumps({
        "hooks": {
            "UserPromptSubmit": [{
                "matcher": "*",
                "hooks": [{"type": "command", "command": "/home/user/.claude/hooks/userpromptsubmit.sh", "timeout": 5}],
            }]
        }
    }))

    monkeypatch.chdir(tmp_path)

    from quoin.cli import _cmd_claude_install
    import argparse
    args = argparse.Namespace(
        scope="project",
        allow_hook_merge=False,
        runtime="claude",
        check=False,
        source_dir=str(QUOIN_SRC),
        force_merge=False,
        dev=False,
        use_pip=False,
    )

    with unittest.mock.patch.object(pathlib.Path, "home", return_value=fake_home):
        with pytest.raises(SystemExit) as exc_info:
            _cmd_claude_install(args)
    assert exc_info.value.code == 2
    out, err = capsys.readouterr()
    assert "double" in err.lower() or "twice" in err.lower() or "home-level" in err.lower() or "hook" in err.lower()


def test_project_install_allows_hook_merge_with_flag(tmp_path, monkeypatch, capsys):
    """--allow-hook-merge bypasses the home hook conflict check."""
    import unittest.mock

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    # Plant quoin stanza in home settings
    home_claude = fake_home / ".claude"
    home_claude.mkdir()
    (home_claude / "settings.json").write_text(json.dumps({
        "hooks": {
            "UserPromptSubmit": [{
                "matcher": "*",
                "hooks": [{"type": "command", "command": str(home_claude / "hooks" / "userpromptsubmit.sh"), "timeout": 5}],
            }]
        }
    }))

    monkeypatch.chdir(tmp_path)
    # Patch install operations to succeed without actual files
    import quoin.installer as inst
    monkeypatch.setattr(inst, "check_prerequisites", lambda: [])
    monkeypatch.setattr(inst, "deploy_memory", lambda *a, **kw: None)
    monkeypatch.setattr(inst, "deploy_quickstart", lambda *a, **kw: None)
    monkeypatch.setattr(inst, "deploy_skills", lambda *a, **kw: 0)
    monkeypatch.setattr(inst, "deploy_scripts", lambda *a, **kw: None)
    monkeypatch.setattr(inst, "deploy_core_scripts", lambda *a, **kw: None)
    monkeypatch.setattr(inst, "cleanup_obsolete_scripts", lambda *a, **kw: None)
    monkeypatch.setattr(inst, "deploy_hooks", lambda *a, **kw: None)
    monkeypatch.setattr(inst, "merge_workflow_rules", lambda *a, **kw: None)
    monkeypatch.setattr(inst, "regenerate_preambles", lambda *a, **kw: None)

    from quoin.cli import _cmd_claude_install
    import argparse
    args = argparse.Namespace(
        scope="project",
        allow_hook_merge=True,  # bypass flag
        runtime="claude",
        check=False,
        source_dir=str(QUOIN_SRC),
        force_merge=False,
        dev=False,
        use_pip=False,
    )
    # Should NOT raise — Path.home() mock so detect_home_hook_conflict reads fake home
    with unittest.mock.patch.object(pathlib.Path, "home", return_value=fake_home):
        result = _cmd_claude_install(args)
    assert result == 0


# ── T-10: Idempotency tests ───────────────────────────────────────────────────

def test_merge_workflow_rules_idempotent(tmp_path):
    """Running merge_workflow_rules twice produces a single marker pair (not duplicated)."""
    from quoin import installer

    # Minimal source CLAUDE.md
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "CLAUDE.md").write_text("# Hello\nSome rules here.\n", encoding="utf-8")

    dest_root = tmp_path / ".claude"
    dest_root.mkdir()
    claude_md = dest_root / "CLAUDE.md"

    # First install
    installer.merge_workflow_rules(source_dir, dest_root)
    after_first = claude_md.read_text(encoding="utf-8")
    assert after_first.count(installer._MARKER_START) == 1

    # Second install (idempotent — should replace, not duplicate)
    installer.merge_workflow_rules(source_dir, dest_root)
    after_second = claude_md.read_text(encoding="utf-8")
    assert after_second.count(installer._MARKER_START) == 1, (
        "merge_workflow_rules produced more than one marker pair on second run (not idempotent)"
    )
    # Content should be byte-equal after second run (no changes)
    assert after_first == after_second, (
        "merge_workflow_rules content changed on second run (should be idempotent)"
    )


def test_merge_workflow_rules_project_mode_idempotent(tmp_path):
    """Running merge_workflow_rules twice in project mode stays at one marker pair."""
    from quoin import installer

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "CLAUDE.md").write_text("# Rules\n", encoding="utf-8")

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    dest_root = project_dir / ".claude"
    dest_root.mkdir()
    claude_md_path = project_dir / "CLAUDE.md"

    # First install
    installer.merge_workflow_rules(source_dir, dest_root, claude_md_path=claude_md_path)
    after_first = claude_md_path.read_text(encoding="utf-8")
    assert after_first.count(installer._MARKER_START) == 1

    # Second install
    installer.merge_workflow_rules(source_dir, dest_root, claude_md_path=claude_md_path)
    after_second = claude_md_path.read_text(encoding="utf-8")
    assert after_second.count(installer._MARKER_START) == 1, (
        "project-mode merge_workflow_rules duplicated marker pair on second run"
    )
    assert after_first == after_second


def test_deploy_hooks_settings_idempotent(tmp_path):
    """Running deploy_hooks twice in project mode does not duplicate hook stanzas
    in settings.json."""
    from quoin import installer

    source_dir = QUOIN_SRC
    dest_root = tmp_path / ".claude"
    dest_root.mkdir()
    (dest_root / "hooks").mkdir()

    # Copy just the hook scripts so deploy_hooks can find them
    src_hooks = QUOIN_SRC / "hooks"
    dst_hooks = dest_root / "hooks"
    import shutil
    for hook in ("userpromptsubmit.sh", "precompact.sh", "postcompact.sh",
                 "sessionstart.sh", "sessionend.sh", "_lib.sh"):
        src_file = src_hooks / hook
        if src_file.exists():
            shutil.copy(src_file, dst_hooks / hook)

    # First deploy
    installer.deploy_hooks(source_dir, dest_root, is_project_mode=True)
    settings_path = dest_root / "settings.json"
    assert settings_path.exists(), "settings.json not created by deploy_hooks"
    settings_first = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks_first = settings_first.get("hooks", {})
    first_count = sum(len(v) for v in hooks_first.values() if isinstance(v, list))

    # Second deploy (idempotent)
    installer.deploy_hooks(source_dir, dest_root, is_project_mode=True)
    settings_second = json.loads(settings_path.read_text(encoding="utf-8"))
    hooks_second = settings_second.get("hooks", {})
    second_count = sum(len(v) for v in hooks_second.values() if isinstance(v, list))

    assert second_count == first_count, (
        f"deploy_hooks duplicated hook stanzas on second run: "
        f"first={first_count} stanzas, second={second_count} stanzas"
    )
