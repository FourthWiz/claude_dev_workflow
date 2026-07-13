"""Unit tests for quoin.core.scripts.ci_mirror.

Tests are hermetic — no real npm, no network. Where a step needs npm to be
"available" (D-04 preflight), `shutil.which` is monkeypatched to a fake path
and correctness steps use plain shell builtins (`exit 0` / `exit 1`), never a
real `npm run ...` invocation.

Coverage (mirrors D-05 exit-code map + D-02 tier order — see plan T-06):
  (a) deliverable detection (D-01)
  (b) Python-only changeset -> exit 0 no-deliverable, runner not invoked
  (c) docs-only changeset -> exit 0 no-deliverable
  (d) Tier-1 manifest steps
  (e) Tier-2 workflow parse (packaging filtered) — requires PyYAML
  (f) Tier-2 YAML-absent degradation -> falls through to Tier-3 (not a silent pass)
  (g) Tier-3 package.json fallback
  (h) packaging filter (D-03)
  (i) failing step -> exit 1
  (j) passing step -> exit 0a
  (k) deliverable detected, zero steps derivable -> exit 3 no-steps-derived
  (l) npm missing preflight -> exit 3
  (m) QUOIN_DISABLE_CI_MIRROR=1 -> exit 3 + {"disabled": true}
  (n) exit 0c: --project-root clean tree -> exit 0, ran_steps=false, no-changes
  (o) exit 2: mutually-exclusive args; unreadable --files-from

Adaptation note (case f): the module imports `yaml` at import time inside a
try/except (`_YAML_AVAILABLE` module flag). Since the module is already
loaded by the time the test runs, "monkeypatch the yaml import to raise
ImportError" is implemented by monkeypatching the module-level
`_YAML_AVAILABLE` flag directly (the same effective behavior — `derive_steps`
branches on this flag, not on re-importing `yaml`).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helper: load the core module from its canonical source path (hermetic)
# ---------------------------------------------------------------------------

_CORE_PATH = Path(__file__).resolve().parents[2] / "core" / "scripts" / "ci_mirror.py"


def _load_core():
    spec = importlib.util.spec_from_file_location("_quoin_core_ci_mirror_test", _CORE_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_ci = _load_core()


def _git(*args, cwd):
    subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True)


def _cli_capture(args):
    """Run _ci.main(args), capturing stdout. Returns (rc, stdout_text)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _ci.main(args)
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# (a) D-01 deliverable detection
# ---------------------------------------------------------------------------

class TestDetectDeliverables:
    def test_detects_nearest_ancestor_with_package_json(self, tmp_path):
        ext_dir = tmp_path / "vscode-extension"
        ext_dir.mkdir()
        (ext_dir / "package.json").write_text("{}")
        (ext_dir / "src").mkdir()
        (ext_dir / "src" / "x.ts").write_text("// ts\n")

        deliverables = _ci.detect_deliverables(["vscode-extension/src/x.ts"], tmp_path)
        assert deliverables == ["vscode-extension"]

    def test_node_modules_paths_excluded(self, tmp_path):
        ext_dir = tmp_path / "vscode-extension"
        ext_dir.mkdir()
        (ext_dir / "package.json").write_text("{}")
        nm = ext_dir / "node_modules" / "some-pkg"
        nm.mkdir(parents=True)
        (nm / "package.json").write_text("{}")
        (nm / "index.js").write_text("// vendored\n")

        deliverables = _ci.detect_deliverables(
            ["vscode-extension/node_modules/some-pkg/index.js"], tmp_path
        )
        assert deliverables == []


# ---------------------------------------------------------------------------
# (b)/(c) no-deliverable path (0b) — Python-only / docs-only
# ---------------------------------------------------------------------------

class TestNoDeliverable:
    def test_python_only_no_deliverable(self, tmp_path):
        (tmp_path / "foo.py").write_text("# py\n")
        with mock.patch("subprocess.run") as mock_run:
            rc, out = _cli_capture(["--files", "foo.py", "--repo-root", str(tmp_path)])
            mock_run.assert_not_called()
        assert rc == 0
        data = json.loads(out)
        assert data["exit_reason"] == "no-deliverable"
        assert data["ran_steps"] is False

        # Same assertion in --format text (gate mapping keys on ran_steps).
        rc_text, out_text = _cli_capture(
            ["--files", "foo.py", "--repo-root", str(tmp_path), "--format", "text"]
        )
        assert rc_text == 0
        assert "exit_reason: no-deliverable" in out_text
        assert "ran_steps: False" in out_text

    def test_docs_only_no_deliverable(self, tmp_path):
        (tmp_path / "README.md").write_text("# docs\n")
        with mock.patch("subprocess.run") as mock_run:
            rc, out = _cli_capture(["--files", "README.md", "--repo-root", str(tmp_path)])
            mock_run.assert_not_called()
        assert rc == 0
        data = json.loads(out)
        assert data["exit_reason"] == "no-deliverable"
        assert data["ran_steps"] is False


# ---------------------------------------------------------------------------
# (d)/(e)/(f)/(g) D-02 hybrid step derivation
# ---------------------------------------------------------------------------

class TestDeriveSteps:
    def test_tier1_manifest_steps(self, tmp_path):
        ext_dir = tmp_path / "vscode-extension"
        ext_dir.mkdir()
        (ext_dir / "package.json").write_text(json.dumps({"scripts": {}}))
        quoin_dir = tmp_path / ".quoin"
        quoin_dir.mkdir()
        manifest = {
            "deliverables": {
                "vscode-extension": {
                    "steps": [{"name": "lint", "run": "npm run lint"}],
                    "working-directory": "vscode-extension",
                    "install": "npm ci",
                }
            }
        }
        (quoin_dir / "gate-manifest.json").write_text(json.dumps(manifest))

        steps, install_cmd, note = _ci.derive_steps(
            "vscode-extension", tmp_path, ["vscode-extension/src/x.ts"]
        )
        assert [s.name for s in steps] == ["lint"]
        assert install_cmd == "npm ci"
        assert note is None

    def test_tier2_workflow_parse_filters_packaging(self, tmp_path):
        pytest.importorskip("yaml")
        ext_dir = tmp_path / "vscode-extension"
        ext_dir.mkdir()
        (ext_dir / "package.json").write_text(json.dumps({"scripts": {}}))
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "vscode-extension.yml").write_text(
            "on:\n"
            "  push:\n"
            "    paths:\n"
            "      - 'vscode-extension/**'\n"
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      - name: compile\n"
            "        run: npm run compile\n"
            "      - name: package\n"
            "        run: npm run package\n"
        )

        steps, install_cmd, note = _ci.derive_steps(
            "vscode-extension", tmp_path, ["vscode-extension/src/x.ts"]
        )
        names = [s.name for s in steps]
        assert "compile" in names
        assert "package" not in names
        assert note is None

    def test_tier2_yaml_unavailable_degrades_to_tier3(self, tmp_path, monkeypatch):
        # See module docstring "Adaptation note (case f)".
        monkeypatch.setattr(_ci, "_YAML_AVAILABLE", False)

        ext_dir = tmp_path / "vscode-extension"
        ext_dir.mkdir()
        (ext_dir / "package.json").write_text(
            json.dumps({"scripts": {"compile": "tsc", "lint": "eslint ."}})
        )
        wf_dir = tmp_path / ".github" / "workflows"
        wf_dir.mkdir(parents=True)
        (wf_dir / "vscode-extension.yml").write_text(
            "on:\n"
            "  push:\n"
            "    paths:\n"
            "      - 'vscode-extension/**'\n"
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      - run: npm run compile\n"
        )

        steps, install_cmd, note = _ci.derive_steps(
            "vscode-extension", tmp_path, ["vscode-extension/src/x.ts"]
        )
        # NOT a silent pass: Tier-3 still runs the correctness steps.
        assert {s.name for s in steps} == {"compile", "lint"}
        assert note is not None
        assert "PyYAML" in note

    def test_tier3_package_json_fallback(self, tmp_path):
        ext_dir = tmp_path / "vscode-extension"
        ext_dir.mkdir()
        (ext_dir / "package.json").write_text(
            json.dumps({"scripts": {"compile": "tsc", "test": "jest"}})
        )

        steps, install_cmd, note = _ci.derive_steps(
            "vscode-extension", tmp_path, ["vscode-extension/src/x.ts"]
        )
        # Order follows _TIER3_SCRIPT_NAMES (compile, typecheck, lint, test).
        assert [s.name for s in steps] == ["compile", "test"]
        assert install_cmd == "npm ci"


# ---------------------------------------------------------------------------
# (h) D-03 packaging + install filter
# ---------------------------------------------------------------------------

class TestPackagingFilter:
    def test_drops_vsce_and_package_and_install_commands(self):
        steps = [
            _ci.Step(name="compile", command="npm run compile", working_dir="vscode-extension"),
            _ci.Step(name="package", command="npm run package", working_dir="vscode-extension"),
            _ci.Step(name="publish", command="vsce publish", working_dir="vscode-extension"),
            _ci.Step(name="install", command="npm ci", working_dir="vscode-extension"),
        ]
        filtered = _ci.filter_packaging(steps)
        assert [s.name for s in filtered] == ["compile"]


# ---------------------------------------------------------------------------
# (i)/(j) step execution -> exit 1 / exit 0a
# ---------------------------------------------------------------------------

def _write_manifest_deliverable(tmp_path, run_cmd, node_modules_present=True):
    ext_dir = tmp_path / "vscode-extension"
    ext_dir.mkdir()
    (ext_dir / "package.json").write_text(json.dumps({"scripts": {}}))
    if node_modules_present:
        (ext_dir / "node_modules").mkdir()
    quoin_dir = tmp_path / ".quoin"
    quoin_dir.mkdir()
    manifest = {
        "deliverables": {
            "vscode-extension": {
                "steps": [{"name": "lint", "run": run_cmd}],
                "working-directory": "vscode-extension",
            }
        }
    }
    (quoin_dir / "gate-manifest.json").write_text(json.dumps(manifest))
    return ext_dir


class TestStepExecution:
    def test_failing_step_exit_1(self, tmp_path, monkeypatch):
        _write_manifest_deliverable(tmp_path, "exit 1")
        # node_modules/ present -> auto install skipped; npm preflight only
        # needs `which` to succeed, no real npm invocation happens.
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/npm")

        rc, out = _cli_capture(
            ["--files", "vscode-extension/src/x.ts", "--repo-root", str(tmp_path)]
        )
        assert rc == 1
        data = json.loads(out)
        assert data["exit_reason"] == "ci-mirror-red"
        assert data["failing_step"] == "lint"
        assert data["failing_returncode"] == 1

    def test_passing_step_exit_0a(self, tmp_path, monkeypatch):
        _write_manifest_deliverable(tmp_path, "exit 0")
        monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/npm")

        rc, out = _cli_capture(
            ["--files", "vscode-extension/src/x.ts", "--repo-root", str(tmp_path)]
        )
        assert rc == 0
        data = json.loads(out)
        assert data["exit_reason"] == "ci-mirror-green"
        assert data["ran_steps"] is True

        rc_text, out_text = _cli_capture(
            ["--files", "vscode-extension/src/x.ts", "--repo-root", str(tmp_path),
             "--format", "text"]
        )
        assert rc_text == 0
        assert "exit_reason: ci-mirror-green" in out_text
        assert "ran_steps: True" in out_text


# ---------------------------------------------------------------------------
# (k) zero steps derivable -> exit 3 no-steps-derived
# ---------------------------------------------------------------------------

def test_no_steps_derived_exit_3(tmp_path):
    ext_dir = tmp_path / "vscode-extension"
    ext_dir.mkdir()
    (ext_dir / "package.json").write_text(json.dumps({"scripts": {"foo": "bar"}}))

    rc, out = _cli_capture(["--files", "vscode-extension/src/x.ts", "--repo-root", str(tmp_path)])
    assert rc == 3
    data = json.loads(out)
    assert data["exit_reason"] == "no-steps-derived"


# ---------------------------------------------------------------------------
# (l) npm missing preflight -> exit 3
# ---------------------------------------------------------------------------

def test_npm_missing_exit_3(tmp_path, monkeypatch):
    ext_dir = tmp_path / "vscode-extension"
    ext_dir.mkdir()
    (ext_dir / "package.json").write_text(json.dumps({"scripts": {"compile": "tsc"}}))
    monkeypatch.setattr(shutil, "which", lambda name: None)

    rc, out = _cli_capture(["--files", "vscode-extension/src/x.ts", "--repo-root", str(tmp_path)])
    assert rc == 3
    data = json.loads(out)
    assert data["exit_reason"] == "npm-missing"


# ---------------------------------------------------------------------------
# (m) env opt-out
# ---------------------------------------------------------------------------

def test_disable_env_exit_3(monkeypatch):
    monkeypatch.setenv("QUOIN_DISABLE_CI_MIRROR", "1")
    rc, out = _cli_capture(["--files", "anything.py"])
    assert rc == 3
    data = json.loads(out)
    assert data.get("disabled") is True


# ---------------------------------------------------------------------------
# (n) exit 0c: --project-root clean tree
# ---------------------------------------------------------------------------

def test_exit_0c_clean_tree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@test.com", cwd=repo)
    _git("config", "user.name", "Test", cwd=repo)
    (repo / "base.py").write_text("# baseline\n")
    _git("add", "base.py", cwd=repo)
    _git("commit", "-m", "baseline", cwd=repo)

    with mock.patch("subprocess.run", wraps=subprocess.run) as spy:
        rc, out = _cli_capture(["--project-root", str(tmp_path)])
        # The runner (npm / step execution) must NOT be invoked — only git
        # subprocess calls (via the sibling affected_tests module) are allowed.
        for call in spy.call_args_list:
            call_args = call[0][0] if call[0] else call.args[0]
            assert "npm" not in str(call_args), (
                f"runner must not be invoked on a clean tree, got call: {call_args}"
            )

    assert rc == 0
    data = json.loads(out)
    assert data["exit_reason"] == "no-changes"
    assert data["ran_steps"] is False

    rc_text, out_text = _cli_capture(["--project-root", str(tmp_path), "--format", "text"])
    assert rc_text == 0
    assert "exit_reason: no-changes" in out_text
    assert "ran_steps: False" in out_text


# ---------------------------------------------------------------------------
# (o) exit 2: malformed invocation
# ---------------------------------------------------------------------------

class TestExitCode2:
    def test_mutually_exclusive_args_exit_2(self):
        rc, _ = _cli_capture(["--project-root", "/tmp", "--files", "foo.py"])
        assert rc == 2

    def test_unreadable_files_from_exit_2(self, tmp_path):
        missing = tmp_path / "does-not-exist.txt"
        rc = _ci.main(["--files-from", str(missing)])
        assert rc == 2
