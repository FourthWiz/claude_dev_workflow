"""
Unit tests for path_resolve.py — 22 deterministic cases, no LLM, no subprocess
except case (p/q/r) which call the CLI.

All cases use the T-01 fixture corpus under fixtures/path_resolve/.
"""

import ast
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Add scripts dir so `from path_resolve import ...` works without packaging
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from path_resolve import task_path, _lookup_stage_by_name

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "path_resolve"
SCRIPT_PATH = Path(__file__).parent.parent.parent / "scripts" / "path_resolve.py"


# ---------------------------------------------------------------------------
# Shared corpus fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def corpus(tmp_path, request):
    """Copy the named fixture subdir into tmp_path/.workflow_artifacts/ for isolation.

    The resolver expects project_root/.workflow_artifacts/<task>/ so we mount the
    fixture tree under tmp_path/.workflow_artifacts/ and return tmp_path as the
    project_root (the 'corpus' variable used by tests as project_root).
    """
    subdir_name = request.param
    src = FIXTURES_DIR / subdir_name
    dst = tmp_path / ".workflow_artifacts"
    # Copy the fixture's task-* subdirs into tmp_path/.workflow_artifacts/
    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    return tmp_path


# ---------------------------------------------------------------------------
# Test cases (22 total)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("corpus", ["legacy"], indirect=True)
def test_legacy_default_returns_task_root(corpus):
    """Rule 3: stage=None → task root even when arch.md exists."""
    result = task_path("task-a", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-a"


@pytest.mark.parametrize("corpus", ["legacy"], indirect=True)
def test_legacy_explicit_int_returns_stage_path_even_when_absent(corpus):
    """Rule 1: explicit int returns path even when stage dir doesn't exist."""
    result = task_path("task-a", stage=1, project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-a" / "stage-1"
    # Directory must NOT exist on disk (caller's job to mkdir)
    assert not result.exists()


@pytest.mark.parametrize("corpus", ["multi-stage"], indirect=True)
def test_multi_stage_explicit_int(corpus):
    """Rule 1: explicit int → stage-2/ directory."""
    result = task_path("task-b", stage=2, project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-b" / "stage-2"


@pytest.mark.parametrize("corpus", ["multi-stage"], indirect=True)
def test_multi_stage_default_returns_task_root(corpus):
    """Rule 3 (I-05 grandfathering): stage=None → task root even with arch+decomp."""
    result = task_path("task-b", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-b"


@pytest.mark.parametrize("corpus", ["multi-stage"], indirect=True)
def test_multi_stage_name_lookup_first_token(corpus):
    """Rule 2: exact stage name match via architecture.md decomposition."""
    result = task_path("task-b", stage="stage-two-name", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-b" / "stage-2"


@pytest.mark.parametrize("corpus", ["multi-stage"], indirect=True)
def test_multi_stage_name_lookup_normalized(corpus):
    """Rule 2: underscores normalized to spaces for lookup."""
    result = task_path("task-b", stage="stage_two_name", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-b" / "stage-2"


@pytest.mark.parametrize("corpus", ["multi-stage"], indirect=True)
def test_multi_stage_name_lookup_substring(corpus):
    """Rule 2: substring match — 'two' matches 'stage-two-name'."""
    result = task_path("task-b", stage="two", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-b" / "stage-2"


@pytest.mark.parametrize("corpus", ["multi-stage"], indirect=True)
def test_multi_stage_name_lookup_miss_raises(corpus):
    """Rule 2b: stage name not found → ValueError."""
    with pytest.raises(ValueError, match="not found in architecture.md"):
        task_path("task-b", stage="nonexistent-stage", project_root=corpus)


@pytest.mark.parametrize("corpus", ["mixed-with-decomp-only"], indirect=True)
def test_mixed_layout_default_returns_root_per_I05(corpus):
    """Rule 3 (I-05): stage=None → root even when stage-1/ folder exists."""
    result = task_path("task-c", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-c"


@pytest.mark.parametrize("corpus", ["no-arch"], indirect=True)
def test_no_arch_default_returns_root(corpus):
    """Rule 3: no architecture.md → task root without error."""
    result = task_path("task-d", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-d"


@pytest.mark.parametrize("corpus", ["no-arch"], indirect=True)
def test_no_arch_name_lookup_raises(corpus):
    """Rule 2a: stage str + no architecture.md → ValueError."""
    with pytest.raises(ValueError, match="architecture.md missing"):
        task_path("task-d", stage="anything", project_root=corpus)


@pytest.mark.parametrize("corpus", ["decomp-only"], indirect=True)
def test_decomp_only_name_lookup_constructs_absent_path(corpus):
    """Rule 2: resolver constructs path even when stage-1/ doesn't exist."""
    result = task_path("task-e", stage="stage-one-name", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-e" / "stage-1"
    # The stage-1 directory must NOT exist on disk
    assert not result.exists()


def test_explicit_int_zero_raises():
    """Rule 1 defensive: stage=0 raises ValueError."""
    with pytest.raises(ValueError, match="must be >= 1"):
        task_path("task-a", stage=0)


def test_explicit_int_negative_raises():
    """Rule 1 defensive: stage=-1 raises ValueError."""
    with pytest.raises(ValueError, match="must be >= 1"):
        task_path("task-a", stage=-1)


def test_module_imports_stdlib_only():
    """T-04 case (o): assert no non-stdlib imports in path_resolve.py."""
    allowed = {"pathlib", "re", "argparse", "sys"}
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top in allowed, (
                    f"path_resolve.py imports non-stdlib module '{alias.name}'. "
                    f"Only stdlib imports allowed: {sorted(allowed)}"
                )
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                assert top in allowed, (
                    f"path_resolve.py imports non-stdlib module '{node.module}'. "
                    f"Only stdlib imports allowed: {sorted(allowed)}"
                )


@pytest.mark.parametrize("corpus", ["legacy"], indirect=True)
def test_cli_default_prints_root(corpus):
    """CLI: no --stage prints task root path."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--task", "task-a",
         "--project-root", str(corpus)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    expected = str(corpus / ".workflow_artifacts" / "task-a")
    assert result.stdout.strip() == expected


@pytest.mark.parametrize("corpus", ["legacy"], indirect=True)
def test_cli_explicit_int(corpus):
    """CLI: --stage 1 prints stage-1 path."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--task", "task-a",
         "--stage", "1", "--project-root", str(corpus)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    expected = str(corpus / ".workflow_artifacts" / "task-a" / "stage-1")
    assert result.stdout.strip() == expected


@pytest.mark.parametrize("corpus", ["multi-stage"], indirect=True)
def test_cli_name_miss_exits_2(corpus):
    """CLI: bad stage name → exit 2 + 'not found' in stderr."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--task", "task-b",
         "--stage", "nonexistent", "--project-root", str(corpus)],
        capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "not found" in result.stderr


def test_inflight_task_grandfathering_real_repo():
    """T-04 case (s): live filesystem snapshot hard-assert for in-flight tasks."""
    repo_root = Path(__file__).parents[3]
    snapshot_file = FIXTURES_DIR / "_inflight-snapshot.txt"
    assert snapshot_file.exists(), f"Snapshot file missing: {snapshot_file}"

    rows = [
        line.strip()
        for line in snapshot_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    for row in rows:
        parts = [p.strip() for p in row.split("|")]
        assert len(parts) == 4, f"Bad snapshot row: {row!r}"
        name, arch_status, plan_status, stage_list = parts

        task_folder = repo_root / ".workflow_artifacts" / name

        # Hard-assert: if the folder doesn't exist, the snapshot must be updated
        assert task_folder.exists(), (
            f"Expected in-flight task '{name}' at {task_folder} but not found. "
            f"If this task was finalized via /end_of_task, REMOVE this row from "
            f"_inflight-snapshot.txt — do NOT silently skip."
        )

        # Verify architecture.md status
        arch_md = task_folder / "architecture.md"
        live_arch_status: str
        if not arch_md.exists():
            live_arch_status = "absent"
        else:
            has_decomp = "## Stage decomposition" in arch_md.read_text(encoding="utf-8")
            live_arch_status = "present-with-decomp" if has_decomp else "present-without-decomp"

        assert live_arch_status == arch_status, (
            f"In-flight task '{name}' snapshot mismatch: expected arch_status "
            f"'{arch_status}' but found '{live_arch_status}'. "
            f"Was this task finalized? If so, REMOVE this row from _inflight-snapshot.txt "
            f"— do NOT mask the regression with a silent skip."
        )

        # Verify current-plan.md status
        plan_md = task_folder / "current-plan.md"
        live_plan_status = "present" if plan_md.exists() else "absent"
        assert live_plan_status == plan_status, (
            f"In-flight task '{name}' snapshot mismatch: expected plan_status "
            f"'{plan_status}' but found '{live_plan_status}'."
        )

        # Verify stage folders
        live_stages = sorted(
            p.name for p in task_folder.iterdir()
            if p.is_dir() and p.name.startswith("stage-")
        )
        if stage_list == "(none)":
            expected_stages: list = []
        else:
            expected_stages = sorted(stage_list.split(","))

        live_stage_str = ",".join(live_stages) if live_stages else "(none)"
        expected_stage_str = ",".join(expected_stages) if expected_stages else "(none)"
        assert live_stage_str == expected_stage_str, (
            f"In-flight task '{name}' snapshot mismatch: expected stages "
            f"'{expected_stage_str}' but found '{live_stage_str}'."
        )

        # Load-bearing R-09 / I-05 assertion: rule-3 default must return task root
        resolved = task_path(name, project_root=repo_root)
        assert resolved == repo_root / ".workflow_artifacts" / name, (
            f"task_path('{name}') returned '{resolved}', expected task root. "
            f"Rule-3 OPT-IN grandfathering broken."
        )


@pytest.mark.parametrize("corpus", ["arch-no-decomp"], indirect=True)
def test_explicit_arch_no_decomp_default_returns_root(corpus):
    """Production-shape: arch.md without decomp → task root (caveman shape)."""
    result = task_path("task-f", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-f"


@pytest.mark.parametrize("corpus", ["arch-absent-with-stage-folder"], indirect=True)
def test_arch_absent_with_stage_folder_default_returns_root(corpus):
    """Production-shape: no arch.md + stage-5/ present → task root NOT stage-5/."""
    result = task_path("task-g", project_root=corpus)
    assert result == corpus / ".workflow_artifacts" / "task-g"


def test_substring_multimatch_raises(tmp_path):
    """T-04 case (v): multi-match on stage name → ValueError with diagnostics."""
    # Build a synthetic fixture with two stages sharing 'data' as substring
    arch_dir = tmp_path / ".workflow_artifacts" / "task-x"
    arch_dir.mkdir(parents=True)
    arch_file = arch_dir / "architecture.md"
    arch_file.write_text(
        "---\ntask: task-x\n---\n"
        "## Stage decomposition\n\n"
        "1. ⏳ S-01: data-migration\n"
        "2. ⏳ S-02: data-cleanup\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        task_path("task-x", stage="data", project_root=tmp_path)

    msg = str(exc_info.value)
    assert "matches 2 stages" in msg, f"Expected 'matches 2 stages' in: {msg}"
    assert "disambiguate by using --stage <integer>" in msg, (
        f"Expected disambiguation hint in: {msg}"
    )
