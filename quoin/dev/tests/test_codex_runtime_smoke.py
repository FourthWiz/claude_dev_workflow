import subprocess
import sys
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent
REPO_ROOT = PKG_DIR.parent
SMOKE_PATH = PKG_DIR / "adapters" / "codex" / "smoke_codex_workflow.py"


def test_codex_runtime_smoke_script_exists():
    assert SMOKE_PATH.is_file(), f"Missing {SMOKE_PATH}"


def test_codex_runtime_smoke_passes_for_repo_root():
    result = subprocess.run(
        [sys.executable, str(SMOKE_PATH), "--project-root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Codex workflow smoke failed:\nstdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "SMOKE PASS: repo-local Codex workflow path is coherent" in result.stdout
    assert "setup-to-core-path" in result.stdout
    assert "minimal-workflow-artifacts" in result.stdout
    assert "runtime-assumption-boundaries" in result.stdout


def test_codex_runtime_smoke_covers_minimal_workflow_path():
    text = SMOKE_PATH.read_text(encoding="utf-8")
    for token in [
        "AGENTS.md -> Codex adapter docs -> core skill docs -> workflow docs",
        "architecture.md",
        "current-plan.md",
        "review-1.md",
        "cost-ledger.md",
        "ccusage",
    ]:
        assert token in text

