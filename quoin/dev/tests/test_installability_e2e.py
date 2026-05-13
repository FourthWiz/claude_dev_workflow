"""End-to-end installability checks for Claude and Codex runtime paths."""
from __future__ import annotations

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
QUOIN_SRC = REPO / "quoin"

try:
    import build  # noqa: F401

    _BUILD_AVAILABLE = True
except ImportError:
    _BUILD_AVAILABLE = False

_requires_build = pytest.mark.skipif(
    not _BUILD_AVAILABLE,
    reason="python 'build' package not installed",
)

_FORBIDDEN_PACKAGE_PARTS = (
    ".workflow_artifacts/",
    ".pytest_cache/",
    "__pycache__/",
    ".pyc",
    "benchmark-results/",
    "quoin/benchmarks/",
)

_FORBIDDEN_CODEX_INSTALL_CLAIMS = (
    "~/.codex",
    "$HOME/.codex",
    "/usr/local/codex",
    "/opt/codex",
    ".codex/commands",
    "npm install -g codex",
    "global Codex install is supported",
    "Codex command files are implemented",
)


def _fake_claude_path(tmp_path: Path) -> str:
    fake_bin = tmp_path / "fake-bin"
    fake_bin.mkdir()
    for name in ("claude", "git"):
        tool = fake_bin / name
        tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        tool.chmod(0o755)
    return f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}"


def _source_env(*, home: Path | None = None, path: str | None = None) -> dict[str, str]:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    if home is not None:
        env["HOME"] = str(home)
    if path is not None:
        env["PATH"] = path
    return env


def _wheel_env(install_target: Path, *, home: Path | None = None, path: str | None = None) -> dict[str, str]:
    env = {**os.environ, "PYTHONPATH": str(install_target)}
    if home is not None:
        env["HOME"] = str(home)
    if path is not None:
        env["PATH"] = path
    return env


def _run_quoin(env: dict[str, str], *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "quoin", *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )


def _assert_claude_install(home: Path) -> None:
    from quoin.installer import (  # noqa: PLC0415
        CANONICAL_SKILLS,
        DEPRECATED_SKILL_MARKERS,
        TIER1_MEMORY_FILES,
    )

    claude_dir = home / ".claude"
    assert claude_dir.is_dir()
    assert (claude_dir / "CLAUDE.md").is_file()
    assert (claude_dir / "CLAUDE.md").read_text(encoding="utf-8").count(
        "# === DEV WORKFLOW START ==="
    ) == 1

    for name in TIER1_MEMORY_FILES:
        assert (claude_dir / "memory" / name).is_file(), name

    for skill in CANONICAL_SKILLS:
        deployed = claude_dir / "skills" / skill / "SKILL.md"
        assert deployed.is_file(), skill
        content = deployed.read_text(encoding="utf-8")
        for marker in DEPRECATED_SKILL_MARKERS:
            assert marker not in content, f"{skill} deployed deprecated stub marker {marker!r}"

        adapter_skill = QUOIN_SRC / "adapters" / "claude" / "skills" / skill / "SKILL.md"
        if adapter_skill.is_file():
            assert deployed.read_bytes() == adapter_skill.read_bytes(), (
                f"{skill} must deploy active Claude adapter content"
            )


def _assert_codex_install(project_root: Path) -> None:
    agents = project_root / "AGENTS.md"
    assert agents.is_file()
    assert sorted(path.name for path in project_root.iterdir()) == ["AGENTS.md"]

    content = agents.read_text(encoding="utf-8")
    assert ".workflow_artifacts/" in content
    assert "validate_codex_handoff.py" in content
    assert "cost_event.py" in content
    for token in _FORBIDDEN_CODEX_INSTALL_CLAIMS:
        assert token not in content


def _assert_codex_checks_pass(env: dict[str, str], project_root: Path) -> None:
    check = _run_quoin(
        env,
        "install",
        "--runtime",
        "codex",
        "--project-root",
        str(project_root),
        "--check",
    )
    assert check.returncode == 0, (
        f"Codex install --check failed:\nstdout={check.stdout}\nstderr={check.stderr}"
    )

    doctor = _run_quoin(
        env,
        "doctor",
        "--runtime",
        "codex",
        "--project-root",
        str(project_root),
        "--smoke",
    )
    assert doctor.returncode == 0, (
        f"Codex doctor --smoke failed:\nstdout={doctor.stdout}\nstderr={doctor.stderr}"
    )
    assert "READY: repo-local Codex setup contract is satisfied" in doctor.stdout
    assert "SMOKE PASS: repo-local Codex workflow path is coherent" in doctor.stdout


@pytest.fixture(scope="module")
def built_dists(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    dist_dir = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(dist_dir), str(REPO)],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if result.returncode != 0:
        pytest.skip(f"package build failed:\n{result.stderr[:800]}")

    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))
    assert len(wheels) == 1, wheels
    assert len(sdists) == 1, sdists
    return wheels[0], sdists[0]


@pytest.fixture()
def installed_wheel(tmp_path: Path, built_dists: tuple[Path, Path]) -> Path:
    wheel, _sdist = built_dists
    target = tmp_path / "installed-wheel"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(target),
            str(wheel),
        ],
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode != 0:
        pytest.skip(f"pip install of wheel failed:\n{result.stderr[:800]}")
    return target


def test_source_install_claude_with_temporary_home(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _source_env(home=home, path=_fake_claude_path(tmp_path))

    result = _run_quoin(env, "install", "--runtime", "claude")

    assert result.returncode == 0, (
        f"source Claude install failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    _assert_claude_install(home)


@_requires_build
def test_wheel_install_claude_with_temporary_home(tmp_path: Path, installed_wheel: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _wheel_env(installed_wheel, home=home, path=_fake_claude_path(tmp_path))

    result = _run_quoin(env, "install", "--runtime", "claude")

    assert result.returncode == 0, (
        f"wheel Claude install failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    _assert_claude_install(home)


def test_source_install_codex_into_temporary_project_root(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    env = _source_env(home=tmp_path / "home")

    result = _run_quoin(
        env,
        "install",
        "--runtime",
        "codex",
        "--project-root",
        str(project_root),
    )

    assert result.returncode == 0, (
        f"source Codex install failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    _assert_codex_install(project_root)
    _assert_codex_checks_pass(env, project_root)
    assert not (Path(env["HOME"]) / ".codex").exists()


@_requires_build
def test_wheel_install_codex_into_temporary_project_root(
    tmp_path: Path,
    installed_wheel: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    env = _wheel_env(installed_wheel, home=tmp_path / "home")

    result = _run_quoin(
        env,
        "install",
        "--runtime",
        "codex",
        "--project-root",
        str(project_root),
    )

    assert result.returncode == 0, (
        f"wheel Codex install failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    _assert_codex_install(project_root)
    _assert_codex_checks_pass(env, project_root)
    assert not (Path(env["HOME"]) / ".codex").exists()


@_requires_build
def test_package_artifacts_exclude_generated_caches_and_results(
    built_dists: tuple[Path, Path],
) -> None:
    wheel, sdist = built_dists

    with zipfile.ZipFile(wheel) as whl:
        wheel_names = whl.namelist()
    with tarfile.open(sdist, "r:gz") as tar:
        sdist_names = tar.getnames()

    for label, names in (("wheel", wheel_names), ("sdist", sdist_names)):
        for forbidden in _FORBIDDEN_PACKAGE_PARTS:
            hits = [name for name in names if forbidden in name]
            assert not hits, f"{label} contains forbidden package artifact {forbidden}: {hits[:5]}"
