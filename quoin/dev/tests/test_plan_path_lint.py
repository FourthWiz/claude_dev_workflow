"""Unit tests for plan_path_lint.py (IVG-143, T-02).

Golden synthetic tree mirroring this workspace's REAL nested-package ambiguity
(git root `quoin/`, source package `quoin/quoin/`, both-level `docs/`, nested-only
`core/ skills/ dev/`, git-root-only `src/`), plus first-class de-risk fixtures for
the whitespace guard (R-01) and the prefix-aware suppression (R-02 / D-01).
"""

import re
import sys
from pathlib import Path

import pytest

# Add core scripts dir so we import the portable implementation under test —
# mirrors test_nested_root_check.py's import pattern exactly.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core" / "scripts"))
import plan_path_lint as ppl  # noqa: E402
from plan_path_lint import (  # noqa: E402
    derive_git_root,
    derive_project_root,
    lint,
    main,
    path_like,
    resolves,
)


# Pinned whitespace character class (critic MINOR carry-over #2) — MUST stay in
# sync with plan_path_lint._WHITESPACE_RE byte-for-byte. A drift here would let
# the R-01 command+path vector silently regress without either test file noticing.
_WHITESPACE_RE = re.compile(r"[ \t]")


def _touch(path: Path, content: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


@pytest.fixture
def tree(tmp_path):
    """Golden synthetic project tree reproducing the real ambiguity on disk.

    proj = tmp_path
      .workflow_artifacts/sometask/current-plan.md   <- the artifact
      quoin/                                          <- git_root (has .git)
        .git/
        docs/architecture-diagram/.keep                <- git-root-level docs (NO hooks-guide.md here)
        src/quoin/installer.py                          <- git-root-ONLY src
        quoin/                                          <- nested source package
          docs/hooks-guide.md                            <- nested-level docs (the real AC1 target)
          core/scripts/validate_artifact.py               <- nested-ONLY core
          skills/plan/SKILL.md                             <- nested-ONLY skills
          dev/tests/test_x.py                               <- nested-ONLY dev
    """
    root = tmp_path
    artifact = _touch(root / ".workflow_artifacts" / "sometask" / "current-plan.md", "placeholder\n")

    git_root = root / "quoin"
    (git_root / ".git").mkdir(parents=True, exist_ok=True)

    _touch(git_root / "docs" / "architecture-diagram" / ".keep")
    _touch(git_root / "src" / "quoin" / "installer.py", "# installer\n")

    nested = git_root / "quoin"
    _touch(nested / "docs" / "hooks-guide.md", "# hooks guide\n")
    _touch(nested / "core" / "scripts" / "validate_artifact.py", "# validate\n")
    _touch(nested / "skills" / "plan" / "SKILL.md", "# plan skill\n")
    _touch(nested / "dev" / "tests" / "test_x.py", "# test\n")

    return {"proj": root, "git_root": git_root, "artifact": artifact}


def _write_plan(tree, body: str) -> Path:
    artifact = tree["artifact"]
    artifact.write_text(body)
    return artifact


# ---------------------------------------------------------------------------
# AC1 — off-by-one nesting: cited path missing a level, flagged with a hint
# ---------------------------------------------------------------------------

def test_ac1_off_by_one_flagged_with_hint(tree):
    artifact = _write_plan(tree, "See `quoin/docs/hooks-guide.md` for details.\n")
    result = lint(artifact, project_root=tree["proj"])
    assert result["checked"] == 1
    assert len(result["unresolved"]) == 1
    item = result["unresolved"][0]
    assert item["token"] == "quoin/docs/hooks-guide.md"
    assert item["line"] == 1
    assert item["hint"] == "quoin/quoin/docs/hooks-guide.md"


# ---------------------------------------------------------------------------
# AC2 — correctly-cited paths (proj-anchored and git-root-relative) not flagged
# ---------------------------------------------------------------------------

def test_ac2_nested_path_not_flagged(tree):
    artifact = _write_plan(
        tree, "Edit `quoin/quoin/core/scripts/validate_artifact.py` next.\n"
    )
    result = lint(artifact, project_root=tree["proj"])
    assert result["unresolved"] == []
    assert result["checked"] == 1


def test_ac2_git_root_relative_path_not_flagged(tree):
    artifact = _write_plan(tree, "Installer lives at `src/quoin/installer.py`.\n")
    result = lint(artifact, project_root=tree["proj"])
    assert result["unresolved"] == []
    assert result["checked"] == 1


# ---------------------------------------------------------------------------
# AC3 — exclusion classes E1-E5, zero flags each
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "line",
    [
        "See `__QUOIN_HOME__/memory/dispatch-guide.md` for the guide.",  # E1 dunder
        "Path is `.workflow_artifacts/<task-name>/spec.md`.",  # E2 angle span
        "Wired in `quoin/skills/*/SKILL.md` bodies.",  # E3 glob
        "Module has `__init__.py` at the top.",  # E4 bare basename (also dunder)
    ],
)
def test_ac3_exclusion_classes_zero_flags(tree, line):
    artifact = _write_plan(tree, line + "\n")
    result = lint(artifact, project_root=tree["proj"])
    assert result["unresolved"] == [], f"line {line!r} should not flag anything"


@pytest.mark.parametrize(
    "line",
    [
        "Config lives at `~/.claude/config.md`.",  # E5 leading tilde
        "External file `/Users/x/.claude/y.md` referenced.",  # E5 external absolute
    ],
)
def test_ac3_e5_external_absolute_zero_flags(tree, line):
    artifact = _write_plan(tree, line + "\n")
    result = lint(artifact, project_root=tree["proj"])
    assert result["unresolved"] == [], f"line {line!r} should not flag anything (E5)"


# ---------------------------------------------------------------------------
# COMMAND-SPAN fixture (R-01, first-class) — whitespace guard must fire FIRST
# ---------------------------------------------------------------------------

def test_command_span_whitespace_guard_zero_flags(tree):
    """A backtick span wrapping a shell command with an embedded VALID path must
    not be treated as a bare path token. Fail-pre: without the whitespace guard
    this span would stat a nonexistent literal command-string and false-positive
    (the round-2 MAJOR / R-01 vector)."""
    span = 'grep -A12 "Step 2b" quoin/quoin/adapters/claude/skills/plan/SKILL.md'
    artifact = _write_plan(tree, f"Run `{span}` to check.\n")

    # Demonstrate the guard fires on this exact span (pinned character class).
    assert _WHITESPACE_RE.search(span) is not None

    result = lint(artifact, project_root=tree["proj"])
    assert result["unresolved"] == []
    assert result["checked"] == 0  # the whole span is rejected by path_like, never checked


def test_path_like_whitespace_guard_direct(tree):
    """Direct path_like() unit assertion — the pinned whitespace class rejects any
    span with internal space/tab before any other gate runs."""
    bases = [tree["proj"], tree["git_root"]]
    assert path_like("quoin/quoin/docs/hooks-guide.md", bases=bases) is True
    assert path_like('grep -A12 "x" quoin/quoin/docs/hooks-guide.md', bases=bases) is False
    assert path_like("has\ttab/inside.md", bases=bases) is False


# ---------------------------------------------------------------------------
# Prefix-suppression (R-02, first-class) — bidirectional resolves() unit test
# ---------------------------------------------------------------------------

def test_prefix_suppression_bidirectional(tree):
    proj = tree["proj"]
    git_root = tree["git_root"]
    git_dir = git_root.name
    assert git_dir == "quoin"

    # Proj-anchored two-level token resolves directly (no suppression needed).
    assert resolves(
        "quoin/quoin/docs/hooks-guide.md",
        project_root=proj, git_root=git_root, git_dir=git_dir, extra_bases=[],
    ) is True

    # git_dir-prefixed one-level token does NOT resolve — the git-root check is
    # suppressed for tokens already starting with "quoin/", even though
    # git_root/tok (== proj/quoin/quoin/docs/hooks-guide.md) DOES exist on disk.
    # This is the off-by-one tension D-01 exists to resolve correctly.
    assert resolves(
        "quoin/docs/hooks-guide.md",
        project_root=proj, git_root=git_root, git_dir=git_dir, extra_bases=[],
    ) is False

    # Sanity: without suppression this WOULD have resolved (proves the guard is
    # doing real work, not vacuously true).
    assert (git_root / "quoin" / "docs" / "hooks-guide.md").exists()


# ---------------------------------------------------------------------------
# AC4 — determinism across CWDs (R-10)
# ---------------------------------------------------------------------------

def test_ac4_determinism_across_cwds(tree, monkeypatch, capsys, tmp_path_factory):
    artifact = _write_plan(
        tree,
        "See `quoin/docs/hooks-guide.md` and `quoin/quoin/core/scripts/validate_artifact.py`.\n",
    )
    artifact_abs = str(artifact.resolve())

    cwd_a = tmp_path_factory.mktemp("cwd_a")
    monkeypatch.chdir(cwd_a)
    rc_a = main([artifact_abs])
    out_a = capsys.readouterr()

    cwd_b = tmp_path_factory.mktemp("cwd_b")
    monkeypatch.chdir(cwd_b)
    rc_b = main([artifact_abs])
    out_b = capsys.readouterr()

    assert rc_a == rc_b
    assert out_a.out == out_b.out
    assert out_a.err == out_b.err


# ---------------------------------------------------------------------------
# AC5 — exit codes
# ---------------------------------------------------------------------------

def test_exit_0_clean(tree):
    artifact = _write_plan(tree, "Nothing but `quoin/quoin/core/scripts/validate_artifact.py` here.\n")
    assert main([str(artifact), "--project-root", str(tree["proj"])]) == 0


def test_exit_1_unresolved(tree):
    artifact = _write_plan(tree, "See `quoin/docs/hooks-guide.md`.\n")
    assert main([str(artifact), "--project-root", str(tree["proj"])]) == 1


def test_exit_2_bad_args(tree):
    with pytest.raises(SystemExit) as exc:
        main(["--format", "bogus", str(tree["artifact"])])
    assert exc.value.code == 2


def test_exit_2_missing_artifact(tree):
    missing = tree["proj"] / "does-not-exist.md"
    assert main([str(missing), "--project-root", str(tree["proj"])]) == 2


def test_exit_2_unreadable_artifact_is_a_directory(tree):
    a_dir = tree["proj"] / "a-directory"
    a_dir.mkdir()
    assert main([str(a_dir), "--project-root", str(tree["proj"])]) == 2


# ---------------------------------------------------------------------------
# Default-invocation derivation (R-08) — no flags, derive git_root/git_dir
# ---------------------------------------------------------------------------

def test_default_invocation_derives_git_root(tree):
    proj = derive_project_root(tree["artifact"])
    assert proj == tree["proj"]
    git_root = derive_git_root(proj)
    assert git_root == tree["proj"] / "quoin"
    assert git_root.name == "quoin"


def test_default_invocation_end_to_end_via_main(tree, capsys):
    artifact = _write_plan(tree, "See `quoin/docs/hooks-guide.md`.\n")
    # NO --project-root / --git-root flags — full default-derivation path.
    rc = main([str(artifact), "--format", "json"])
    assert rc == 1
    out = capsys.readouterr().out
    assert '"quoin/quoin/docs/hooks-guide.md"' in out


# ---------------------------------------------------------------------------
# JSON format shape
# ---------------------------------------------------------------------------

def test_json_format_shape(tree, capsys):
    artifact = _write_plan(tree, "See `quoin/docs/hooks-guide.md`.\n")
    rc = main([str(artifact), "--project-root", str(tree["proj"]), "--format", "json"])
    assert rc == 1
    import json as _json
    payload = _json.loads(capsys.readouterr().out)
    assert payload["artifact"] == str(artifact.resolve())
    assert payload["checked"] == 1
    assert len(payload["unresolved"]) == 1
    entry = payload["unresolved"][0]
    assert entry["token"] == "quoin/docs/hooks-guide.md"
    assert entry["line"] == 1
    assert entry["hint"] == "quoin/quoin/docs/hooks-guide.md"


# ---------------------------------------------------------------------------
# main() importable module contract
# ---------------------------------------------------------------------------

def test_main_returns_int(tree):
    artifact = _write_plan(tree, "clean plan, no paths cited\n")
    rc = main([str(artifact), "--project-root", str(tree["proj"])])
    assert isinstance(rc, int)
    assert rc == 0


def test_module_has_expected_cli_shape():
    parser = ppl._build_parser()
    dest_names = {a.dest for a in parser._actions}
    assert {"artifact", "project_root", "git_root", "base", "include_prose", "format", "quiet"} <= dest_names
