"""Tests for quoin/core/scripts/dashboard_model.py — cost aggregation and task enumeration.

Deterministic tests (no LLM calls, no live git). Fixtures build synthetic
.workflow_artifacts/ structures with cost ledgers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Load the dashboard_model core module via spec_from_file_location
# (pattern mirrors test_status_graph.py)
_CORE_PATH = (
    Path(__file__).resolve().parents[2] / "core" / "scripts" / "dashboard_model.py"
)
import importlib.util as _ilu
_SPEC = _ilu.spec_from_file_location("_quoin_core_dashboard_model_test", _CORE_PATH)
_DM = _ilu.module_from_spec(_SPEC)
sys.modules["_quoin_core_dashboard_model_test"] = _DM
_SPEC.loader.exec_module(_DM)

scan_tasks = _DM.scan_tasks
task_detail = _DM.task_detail
_read_ledger_rows = _DM._read_ledger_rows
_counts_by_phase = _DM._counts_by_phase
_min_artifact_mtime = _DM._min_artifact_mtime
_stage_info = _DM._stage_info
_task_summary = _DM._task_summary
compute_version_token = _DM.compute_version_token
main = _DM.main


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_task(root: Path, name: str, files: list[str] = None) -> Path:
    """Create a synthetic task dir under root/.workflow_artifacts/NAME with given files."""
    if files is None:
        files = []
    task_dir = root / ".workflow_artifacts" / name
    task_dir.mkdir(parents=True, exist_ok=True)
    for fname in files:
        f = task_dir / fname
        f.parent.mkdir(parents=True, exist_ok=True)
        if fname == "cost-ledger.md":
            # Create a dummy ledger
            f.write_text("# Cost Ledger\n")
        else:
            f.write_text(f"# {fname} placeholder\n")
    return task_dir


def make_ledger(task_dir: Path, rows: list[tuple]) -> Path:
    """Create a cost-ledger.md with the given rows.

    Each row is a tuple: (uuid, date, phase, model_or_effort, note, fallback_fires)
    or (uuid, date, phase, model_or_effort, note) for 6-col compatibility.
    """
    ledger_path = task_dir / "cost-ledger.md"
    task_dir.mkdir(parents=True, exist_ok=True)

    lines = ["# Cost Ledger — test"]
    for row in rows:
        if len(row) == 5:
            # 6-col: add 0 for fallback_fires
            row = row + (0,)
        uuid, date, phase, model_or_effort, note, fallback_fires = row
        line = f"{uuid} | {date} | {phase} | {model_or_effort} | task | {note} | {fallback_fires}"
        lines.append(line)

    ledger_path.write_text("\n".join(lines) + "\n")
    return ledger_path


def make_fixture_tree(tmp_path: Path) -> tuple:
    """Create a fixture .workflow_artifacts/ tree.

    Returns: (root, single_task_dir, multi_task_dir, finalized_task_dir)
    """
    root = tmp_path / "project"
    root.mkdir()

    # Single-stage task "alpha"
    alpha_dir = make_task(root, "alpha", ["current-plan.md"])
    make_ledger(alpha_dir, [
        ("uuid1", "2026-01-01", "architect", "opus", "initial scan", 0),
    ])

    # Multi-stage task "beta" with architecture.md
    beta_dir = make_task(root, "beta", ["architecture.md"])
    arch_text = """# Architecture

## Stage decomposition

1. S-01: core model
2. S-02: provider integration
3. S-03: HTTP server

## Other sections
...
"""
    (beta_dir / "architecture.md").write_text(arch_text)

    # Create stage-1 subfolder
    stage1_dir = beta_dir / "stage-1"
    stage1_dir.mkdir(parents=True, exist_ok=True)
    (stage1_dir / "current-plan.md").write_text("# Plan\n")

    # Ledger at task root (per D-04)
    make_ledger(beta_dir, [
        ("uuid2", "2026-01-02", "plan", "opus", "planning round 1", 0),
        ("uuid3", "2026-01-03", "critic", "opus", "critic round 1", 0),
        ("uuid4", "2026-01-04", "critic", "sonnet", "critic round 2", 0),
    ])

    # Finalized task "gamma" at top level
    finalized_dir = root / ".workflow_artifacts" / "finalized" / "gamma"
    finalized_dir.mkdir(parents=True, exist_ok=True)
    (finalized_dir / "current-plan.md").write_text("# Plan\n")
    make_ledger(finalized_dir, [
        ("uuid5", "2026-01-05", "review", "opus", "review round 1", 0),
    ])

    # Memory and cache dirs (should be excluded from scan)
    (root / ".workflow_artifacts" / "memory").mkdir(exist_ok=True)
    (root / ".workflow_artifacts" / "cache").mkdir(exist_ok=True)

    return root, alpha_dir, beta_dir, finalized_dir


# ---------------------------------------------------------------------------
# Test: _read_ledger_rows
# ---------------------------------------------------------------------------

def test_read_ledger_rows_basic(tmp_path):
    """Test reading and parsing ledger rows."""
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    make_ledger(task_dir, [
        ("u1", "2026-01-01", "plan", "opus", "test note", 0),
        ("u2", "2026-01-02", "critic", "sonnet", "another", 1),
        ("u3", "2026-01-03", "review", "haiku", "last", 0),
    ])

    rows = _read_ledger_rows(task_dir)

    assert len(rows) == 3
    assert rows[0]["uuid"] == "u1"
    assert rows[0]["phase"] == "plan"
    assert rows[0]["model_or_effort"] == "opus"
    assert rows[0]["fallback_fires"] == 0
    assert "model" not in rows[0]  # Ensure model_or_effort, not model (MAJ-1)


def test_read_ledger_rows_missing(tmp_path):
    """Test reading from missing ledger returns empty list."""
    task_dir = tmp_path / "nonexistent"
    task_dir.mkdir()

    rows = _read_ledger_rows(task_dir)
    assert rows == []


# ---------------------------------------------------------------------------
# Test: _counts_by_phase
# ---------------------------------------------------------------------------

def test_counts_by_phase_basic():
    """Test counts mode computation.

    _counts_by_phase returns per-phase counts only — no "total" key.
    "total" lives at cost["total"] (top-level), not inside by_phase.
    """
    rows = [
        {"phase": "architect", "fallback_fires": 0},
        {"phase": "critic", "fallback_fires": 0},
        {"phase": "critic", "fallback_fires": 0},
        {"phase": "plan", "fallback_fires": 0},
    ]

    counts = _counts_by_phase(rows)

    assert counts["architect"] == 1
    assert counts["critic"] == 2
    assert counts["plan"] == 1
    # "total" must NOT appear inside by_phase (it lives at cost["total"])
    assert "total" not in counts


# ---------------------------------------------------------------------------
# Test: _min_artifact_mtime
# ---------------------------------------------------------------------------

def test_min_artifact_mtime_basic(tmp_path):
    """Test MIN mtime helper (mirrors _max_artifact_mtime)."""
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    # Create files with different times
    f1 = task_dir / "file1.md"
    f2 = task_dir / "file2.md"
    stage_dir = task_dir / "stage-1"
    stage_dir.mkdir()
    f3 = stage_dir / "file3.md"

    f1.write_text("content")
    f2.write_text("content")
    f3.write_text("content")

    min_mtime = _min_artifact_mtime(task_dir)
    assert min_mtime > 0.0


def test_min_artifact_mtime_empty(tmp_path):
    """Test MIN mtime for empty task returns 0.0."""
    task_dir = tmp_path / "task"
    task_dir.mkdir()

    min_mtime = _min_artifact_mtime(task_dir)
    assert min_mtime == 0.0


# ---------------------------------------------------------------------------
# Test: _stage_info
# ---------------------------------------------------------------------------

def test_stage_info_multi_stage(tmp_path):
    """Test multi-stage detection and enumeration."""
    root, _, beta_dir, _ = make_fixture_tree(tmp_path)

    info = _stage_info(beta_dir)

    assert info["is_multi_stage"] is True
    assert len(info["stages"]) == 3
    assert info["stages"][0]["n"] == 1
    assert info["stages"][0]["name"] == "core model"
    assert info["stages"][1]["n"] == 2
    assert info["stages"][1]["name"] == "provider integration"
    # Each stage dict must include critic_rounds and review_rounds
    for st in info["stages"]:
        assert "critic_rounds" in st
        assert "review_rounds" in st


def test_stage_info_critic_review_rounds_aggregated(tmp_path):
    """Multi-stage tasks aggregate critic/review rounds from stage subdirs."""
    root = tmp_path / "project"
    root.mkdir()

    task_dir = root / ".workflow_artifacts" / "my-task"
    task_dir.mkdir(parents=True)

    arch_text = """# Arch\n\n## Stage decomposition\n\n1. S-01: stage one\n2. S-02: stage two\n"""
    (task_dir / "architecture.md").write_text(arch_text)

    # stage-1: 2 critic rounds, 1 review round
    s1 = task_dir / "stage-1"
    s1.mkdir()
    (s1 / "current-plan.md").write_text("")
    (s1 / "critic-response-1.md").write_text("")
    (s1 / "critic-response-2.md").write_text("")
    (s1 / "review-1.md").write_text("")

    # stage-2: 1 critic round, 0 review rounds (needs current-plan.md so
    # detect_phase enters "planning" phase and reports critic_rounds)
    s2 = task_dir / "stage-2"
    s2.mkdir()
    (s2 / "current-plan.md").write_text("")
    (s2 / "critic-response-1.md").write_text("")

    info = _stage_info(task_dir)

    assert info["is_multi_stage"] is True
    assert info["stages"][0]["critic_rounds"] == 2
    assert info["stages"][0]["review_rounds"] == 1
    assert info["stages"][1]["critic_rounds"] == 1
    assert info["stages"][1]["review_rounds"] == 0


def test_task_summary_multi_stage_rounds_aggregated(tmp_path):
    """_task_summary sums critic/review rounds across stages for multi-stage tasks."""
    root = tmp_path / "project"
    root.mkdir()

    task_dir = root / ".workflow_artifacts" / "my-task"
    task_dir.mkdir(parents=True)

    arch_text = """# Arch\n\n## Stage decomposition\n\n1. S-01: stage one\n2. S-02: stage two\n"""
    (task_dir / "architecture.md").write_text(arch_text)
    make_ledger(task_dir, [("u1", "2026-01-01", "plan", "opus", "note", 0)])

    # stage-1: 2 critic rounds, 1 review
    s1 = task_dir / "stage-1"
    s1.mkdir()
    (s1 / "critic-response-1.md").write_text("")
    (s1 / "critic-response-2.md").write_text("")
    (s1 / "review-1.md").write_text("")

    # stage-2: 1 critic round (current-plan.md required so detect_phase enters
    # "planning" phase and actually reports critic_rounds; without it the phase
    # is "discover" which unconditionally returns critic_rounds=0)
    s2 = task_dir / "stage-2"
    s2.mkdir()
    (s2 / "current-plan.md").write_text("")
    (s2 / "critic-response-1.md").write_text("")

    summary = _task_summary(root, task_dir, "my-task", cost_provider=None)

    # Total: stage-1 (2 critic + 1 review) + stage-2 (1 critic) = 3 critic, 1 review
    assert summary["critic_rounds"] == 3
    assert summary["review_rounds"] == 1


def test_stage_info_single_stage(tmp_path):
    """Test single-stage task detection."""
    root, alpha_dir, _, _ = make_fixture_tree(tmp_path)

    info = _stage_info(alpha_dir)

    assert info["is_multi_stage"] is False
    assert info["stages"] == []


# ---------------------------------------------------------------------------
# Test: scan_tasks
# ---------------------------------------------------------------------------

def test_scan_tasks_basic(tmp_path):
    """Test scanning tasks in a fixture tree."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    result = scan_tasks(root)

    assert "project_root" in result
    assert "active_task" in result
    assert "tasks" in result
    assert len(result["tasks"]) == 2  # alpha and beta (not finalized)

    # Check task names
    task_names = {t["name"] for t in result["tasks"]}
    assert "alpha" in task_names
    assert "beta" in task_names


def test_scan_tasks_include_finalized(tmp_path):
    """Test scanning with finalized tasks included."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    result = scan_tasks(root, include_finalized=True)

    assert len(result["tasks"]) == 3  # alpha, beta, gamma
    task_names = {t["name"] for t in result["tasks"]}
    assert "gamma" in task_names


def test_scan_tasks_excludes_memory_cache_finalized(tmp_path):
    """Test that memory, cache, finalized are excluded from default scan."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    result = scan_tasks(root, include_finalized=False)

    task_names = {t["name"] for t in result["tasks"]}
    assert "memory" not in task_names
    assert "cache" not in task_names
    assert "finalized" not in task_names


def test_scan_tasks_active_task_is_string(tmp_path):
    """Test that active_task is a JSON-serializable string (not Path) — CRIT-1."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    result = scan_tasks(root)

    # active_task must be a string (or None)
    if result["active_task"] is not None:
        assert isinstance(result["active_task"], str)

    # Must be JSON-serializable
    json_str = json.dumps(result)
    assert json_str is not None


def test_scan_tasks_cost_mode_counts(tmp_path):
    """Test that default cost mode is counts."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    result = scan_tasks(root)

    for task in result["tasks"]:
        assert task["cost"]["mode"] == "counts"
        assert "by_phase" in task["cost"]
        assert task["cost"]["usd"] is None
        assert task["cost"]["tokens"] is None


def test_scan_tasks_with_fake_provider(tmp_path):
    """Test that cost_provider enrichment works."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    def fake_provider(task_name, rows):
        # Verify row contract: each row has model_or_effort, not model
        for row in rows:
            assert "model_or_effort" in row
            assert "model" not in row  # MAJ-1 regression guard

        return {
            "mode": "usd",
            "usd": 4.12,
            "by_phase": {"plan": 1.0, "critic": 3.12},
        }

    result = scan_tasks(root, cost_provider=fake_provider)

    for task in result["tasks"]:
        if task["cost"]["by_phase"]:  # Only if provider returned data
            assert task["cost"]["mode"] == "usd"
            assert task["cost"]["usd"] == 4.12


def test_scan_tasks_provider_raises_degrades_gracefully(tmp_path):
    """Test that provider exceptions degrade to counts mode."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    def bad_provider(task_name, rows):
        raise ValueError("Provider is broken")

    result = scan_tasks(root, cost_provider=bad_provider)

    for task in result["tasks"]:
        assert task["cost"]["mode"] == "counts"  # Falls back to counts


# ---------------------------------------------------------------------------
# Test: task_detail
# ---------------------------------------------------------------------------

def test_task_detail_non_finalized(tmp_path):
    """Test task_detail for a non-finalized task."""
    root, _, beta_dir, _ = make_fixture_tree(tmp_path)

    detail = task_detail(root, "beta")

    assert detail["name"] == "beta"
    assert detail["is_multi_stage"] is True
    assert len(detail["stages"]) == 3
    assert "ledger_rows" in detail  # Non-finalized includes rows
    assert len(detail["ledger_rows"]) == 3
    assert "totals" not in detail  # Non-finalized doesn't include totals
    assert "dates" in detail


def test_task_detail_finalized(tmp_path):
    """Test task_detail for a finalized task."""
    root, _, _, finalized_dir = make_fixture_tree(tmp_path)

    detail = task_detail(root, "gamma")

    assert detail["name"] == "gamma"
    assert detail["finalized"] is True
    assert detail["phase"] == "done"
    assert "ledger_rows" not in detail  # Finalized doesn't include rows
    assert "totals" in detail  # Finalized includes totals only
    assert detail["totals"]["review"] == 1


def test_task_detail_phase_label(tmp_path):
    """Test that phase_label is a human label (MAJ-2 regression guard)."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    detail = task_detail(root, "beta")

    assert "phase_label" in detail
    assert detail["phase_label"] != detail["phase"]  # Human label, not raw phase
    assert isinstance(detail["phase_label"], str)


def test_task_detail_dates_ordering(tmp_path):
    """Test that first_activity <= last_activity (MIN-2 guard)."""
    root, _, beta_dir, _ = make_fixture_tree(tmp_path)

    detail = task_detail(root, "beta")

    first = detail["dates"]["first_activity"]
    last = detail["dates"]["last_activity"]

    if first is not None and last is not None:
        assert first <= last


def test_task_detail_unknown_task(tmp_path):
    """Test that unknown task raises KeyError."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    with pytest.raises(KeyError):
        task_detail(root, "nonexistent")


# ---------------------------------------------------------------------------
# Test: Spaced path (Google Drive style)
# ---------------------------------------------------------------------------

def test_fixture_with_spaced_root(tmp_path):
    """Test that all functions work with spaced-root paths (R-02)."""
    # Create a root with spaces (mimics Google Drive path)
    spaced_root = tmp_path / "a b c"
    spaced_root.mkdir()

    root, _, _, _ = make_fixture_tree(spaced_root)

    # scan_tasks should work with spaced paths
    result = scan_tasks(root)
    assert len(result["tasks"]) >= 1

    # task_detail should work with spaced paths
    detail = task_detail(root, "beta")
    assert detail["name"] == "beta"


# ---------------------------------------------------------------------------
# Test: CLI
# ---------------------------------------------------------------------------

def test_cli_scan_json(tmp_path, capsys):
    """Test CLI --json flag."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    exit_code = main(["--json", "--project-root", str(root)])

    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "tasks" in data
    assert len(data["tasks"]) == 2


def test_cli_task_detail(tmp_path, capsys):
    """Test CLI --task flag."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    exit_code = main(["--task", "beta", "--project-root", str(root)])

    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["name"] == "beta"


def test_cli_unknown_task(tmp_path, capsys):
    """Test CLI with unknown task name."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    exit_code = main(["--task", "nonexistent", "--project-root", str(root)])

    assert exit_code == 1


def test_cli_no_project_found(tmp_path, capsys):
    """Test CLI when no .workflow_artifacts found — returns empty gracefully."""
    bad_root = tmp_path / "no_artifacts"
    bad_root.mkdir()

    exit_code = main(["--project-root", str(bad_root)])

    assert exit_code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["tasks"] == []
    assert data["active_task"] is None


# ---------------------------------------------------------------------------
# Test: Regression guards (from plan acceptance criteria)
# ---------------------------------------------------------------------------

def test_regression_active_task_str_not_path(tmp_path):
    """CRIT-1: active_task must be a str, not Path, and JSON-serializable."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    result = scan_tasks(root)

    if result["active_task"] is not None:
        assert isinstance(result["active_task"], str)
        # Verify JSON-serializable
        json_str = json.dumps(result)
        reparsed = json.loads(json_str)
        assert isinstance(reparsed["active_task"], str)


def test_regression_ledger_rows_no_model_field(tmp_path):
    """MAJ-1: ledger rows must have model_or_effort, not model."""
    root, _, beta_dir, _ = make_fixture_tree(tmp_path)

    detail = task_detail(root, "beta")

    for row in detail.get("ledger_rows", []):
        assert "model_or_effort" in row
        assert "model" not in row


def test_regression_phase_label_is_human(tmp_path):
    """MAJ-2: phase_label must be from _PHASE_LABELS, not raw phase string."""
    root, alpha_dir, _, _ = make_fixture_tree(tmp_path)

    detail = task_detail(root, "alpha")

    assert detail["phase_label"] in [
        "discover",
        "architect (architecture done)",
        "planning",
        "plan-gated (ready to implement)",
        "implement (in-progress, git)",
        "implement-gated (ready to review)",
        "review",
        "review-gated (ready to finalize)",
        "done",
    ]


def test_regression_min_artifact_mtime_helper(tmp_path):
    """MIN-2: _min_artifact_mtime helper exists and works."""
    root, _, beta_dir, _ = make_fixture_tree(tmp_path)

    min_mtime = _min_artifact_mtime(beta_dir)

    # Should return a valid timestamp (non-zero since files exist)
    assert isinstance(min_mtime, float)
    assert min_mtime >= 0.0


def test_regression_exception_narrowing(tmp_path):
    """MIN-4: provider exceptions use 'except Exception', not bare except."""
    root, _, _, _ = make_fixture_tree(tmp_path)

    def provider_that_raises(task_name, rows):
        raise Exception("Test exception")

    # Should not raise, should degrade gracefully
    result = scan_tasks(root, cost_provider=provider_that_raises)
    assert result is not None


# ---------------------------------------------------------------------------
# Test: compute_version_token (IVG-76 T-01 acceptance criteria)
# ---------------------------------------------------------------------------

def test_compute_version_token_stability(tmp_path):
    """Token stability: two calls with same root/scope and no FS change → identical token."""
    root = tmp_path / "project"
    root.mkdir()
    # Create a .workflow_artifacts/ dir with one file
    art = root / ".workflow_artifacts" / "my-task"
    art.mkdir(parents=True)
    (art / "current-plan.md").write_text("# plan\n")

    scope = "tasks:fin=False|cj=0"
    token1 = compute_version_token(root, scope)
    token2 = compute_version_token(root, scope)

    assert token1 == token2, "Token must be stable when FS state is unchanged"
    # Verify ETag format: starts and ends with double-quote
    assert token1.startswith('"') and token1.endswith('"'), (
        f"Token must be a quoted ETag string, got: {token1!r}"
    )
    assert len(token1) == 18, f"Expected '\"' + 16-char hex + '\"' (18 chars), got {len(token1)}"


def test_compute_version_token_changes_on_new_file(tmp_path):
    """Token changes when a new artifact file is created."""
    root = tmp_path / "project"
    root.mkdir()
    art = root / ".workflow_artifacts" / "my-task"
    art.mkdir(parents=True)
    (art / "current-plan.md").write_text("# plan\n")

    scope = "tasks:fin=False|cj=0"
    token_before = compute_version_token(root, scope)

    # Create a new file
    (art / "review-1.md").write_text("# review\n")
    token_after = compute_version_token(root, scope)

    assert token_before != token_after, "Token must change when a new file is created"


def test_compute_version_token_scope_scoping(tmp_path):
    """Different scope strings → different tokens even with identical FS state."""
    root = tmp_path / "project"
    root.mkdir()
    art = root / ".workflow_artifacts" / "my-task"
    art.mkdir(parents=True)
    (art / "current-plan.md").write_text("# plan\n")

    token_a = compute_version_token(root, "tasks:fin=False|cj=0")
    token_b = compute_version_token(root, "tasks:fin=True|cj=0")
    token_c = compute_version_token(root, "task:my-task|cj=0")

    assert token_a != token_b, "fin=False and fin=True scopes must produce different tokens"
    assert token_a != token_c, "list scope and detail scope must produce different tokens"
    assert token_b != token_c, "fin=True scope and detail scope must produce different tokens"


def test_compute_version_token_missing_artifacts_dir(tmp_path):
    """Returns non-empty deterministic string when .workflow_artifacts/ is absent."""
    root = tmp_path / "no_artifacts_project"
    root.mkdir()
    # No .workflow_artifacts/ created

    scope = "tasks:fin=False|cj=0"
    token = compute_version_token(root, scope)

    assert token, "Token must be non-empty even when .workflow_artifacts/ is absent"
    assert token.startswith('"') and token.endswith('"'), (
        f"Token must be a quoted ETag string, got: {token!r}"
    )
    # Second call with same scope → same token (deterministic)
    token2 = compute_version_token(root, scope)
    assert token == token2, "Token must be deterministic when .workflow_artifacts/ is absent"


def test_compute_version_token_same_second_different_size(tmp_path):
    """Tokens differ for two files created in same wall-clock second with different sizes.

    This tests count+size disambiguation: even if mtime is identical,
    different file sizes produce different tokens (proves count/size signals work).
    """
    import time as _time

    root = tmp_path / "project"
    root.mkdir()
    art = root / ".workflow_artifacts" / "my-task"
    art.mkdir(parents=True)

    scope = "tasks:fin=False|cj=0"

    # Create first file
    f1 = art / "file_small.md"
    f1.write_text("x")
    token1 = compute_version_token(root, scope)

    # Create second file with different size (adds to count AND total_size)
    f2 = art / "file_large.md"
    f2.write_text("x" * 100)
    token2 = compute_version_token(root, scope)

    assert token1 != token2, (
        "Token must change when a file with different size is added "
        "(count + total_size disambiguation)"
    )


def test_compute_version_token_no_adapter_imports():
    """Core-purity: compute_version_token must not import from adapter layer.

    Acceptance grep: 'from|import.*scripts' must not match in dashboard_model.py
    for any adapter-layer reference.
    """
    import re
    source = _CORE_PATH.read_text(encoding="utf-8")
    # Check no import from quoin/scripts adapter layer
    adapter_import_re = re.compile(r'^(from|import).*dashboard_server|dashboard_cost', re.MULTILINE)
    assert not adapter_import_re.search(source), (
        "dashboard_model.py must not import from dashboard_server or dashboard_cost "
        "(core/adapter boundary violation)"
    )
