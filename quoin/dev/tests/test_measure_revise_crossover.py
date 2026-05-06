"""Unit tests for measure_revise_crossover_cost.py using fixture task directories."""
import json
import math
import pathlib
import sys

import pytest

QUOIN_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = QUOIN_ROOT / "scripts"
FIXTURES_DIR = pathlib.Path(__file__).parent / "fixtures" / "measure_revise_crossover"

sys.path.insert(0, str(SCRIPTS_DIR))
from measure_revise_crossover_cost import analyse  # noqa: E402

# Fake project hash — JSONL won't exist so all costs will be 0.0
_FAKE_PROJ_HASH = "fake-proj"


def _run(fixture_name: str, max_tasks: int = 10) -> dict:
    task_dir = FIXTURES_DIR / fixture_name
    return analyse(task_dir, "medium", max_tasks, _FAKE_PROJ_HASH)


# ---------------------------------------------------------------------------
# Fixture: deprecate-recommended
# ---------------------------------------------------------------------------

def test_deprecate_recommended_verdict():
    """When opus tasks have fewer rounds than fast tasks, recommend DEPRECATE."""
    result = _run("deprecate-recommended")
    assert result["n_opus"] >= 3, f"Expected ≥3 opus tasks, got {result['n_opus']}"
    assert result["n_fast"] >= 3, f"Expected ≥3 fast tasks, got {result['n_fast']}"
    # opus tasks have 2 rounds each; fast tasks have 3 rounds each
    assert result["mean_opus_rounds"] < result["mean_fast_rounds"]
    # Costs are all 0 (no JSONL) so cost condition is also met (0 ≤ 0 + 0)
    assert "DEPRECATE" in result["recommendation"]


# ---------------------------------------------------------------------------
# Fixture: preserve-recommended
# ---------------------------------------------------------------------------

def test_preserve_recommended_verdict():
    """When opus tasks have MORE rounds than fast, recommend PRESERVE."""
    result = _run("preserve-recommended")
    assert result["n_opus"] >= 3
    assert result["n_fast"] >= 3
    # opus: 4 rounds, fast: 2 rounds → opus uses more rounds → PRESERVE
    assert result["mean_opus_rounds"] > result["mean_fast_rounds"]
    assert "PRESERVE" in result["recommendation"]


# ---------------------------------------------------------------------------
# Fixture: insufficient-fast
# ---------------------------------------------------------------------------

def test_insufficient_fast_data():
    """When fewer than 3 fast tasks, emit INSUFFICIENT DATA."""
    result = _run("insufficient-fast")
    assert result["n_fast"] < 3
    assert "INSUFFICIENT DATA" in result["recommendation"]
    # caveats explains the data gap
    assert "3" in result.get("caveats", "") or "Re-run" in result.get("caveats", "")


# ---------------------------------------------------------------------------
# Fixture: insufficient-opus
# ---------------------------------------------------------------------------

def test_insufficient_opus_data():
    """When fewer than 3 opus tasks, emit INSUFFICIENT DATA."""
    result = _run("insufficient-opus")
    assert result["n_opus"] < 3
    assert "INSUFFICIENT DATA" in result["recommendation"]


# ---------------------------------------------------------------------------
# Fixture: single-stage-task-shape
# ---------------------------------------------------------------------------

def test_single_stage_task_shape():
    """Single-stage tasks (root cost-ledger only) are counted as n_stages=1."""
    result = _run("single-stage-shape")
    for name, stages in result["n_stages_per_task"].items():
        assert stages == 1, f"Expected 1 stage for {name}, got {stages}"


# ---------------------------------------------------------------------------
# Fixture: multi-stage-task-shape (variants A + B)
# ---------------------------------------------------------------------------

def test_multi_stage_task_shape():
    """Multi-stage tasks (finalized/stage-N and stage-N layouts) aggregate all rows."""
    result = _run("multi-stage-shape")
    # multi-opus-task has 2 nested stages → n_stages should be > 1
    multi_opus = result["n_stages_per_task"].get("multi-opus-task")
    if multi_opus is not None:
        assert multi_opus > 1, f"Expected >1 stage for multi-opus-task, got {multi_opus}"
    # multi-fast-task has 2 flat stage dirs
    multi_fast = result["n_stages_per_task"].get("multi-fast-task")
    if multi_fast is not None:
        assert multi_fast > 1, f"Expected >1 stage for multi-fast-task, got {multi_fast}"


def test_multi_stage_row_aggregation():
    """Multi-stage tasks aggregate rows from ALL stage ledgers, not just root."""
    result = _run("multi-stage-shape")
    rounds = result["round_count_per_task"]
    # multi-opus-task: root (1 row) + finalized/stage-1 (1 row) + finalized/stage-2 (1 row) = 3 rounds.
    # If aggregation only read the root ledger this would be 1, not 3 — proving the test is meaningful.
    assert rounds.get("multi-opus-task") == 3, (
        f"Expected multi-opus-task round_count=3 (root + 2 nested stages), "
        f"got {rounds.get('multi-opus-task')}. Aggregation likely only reading root ledger."
    )
    # multi-fast-task: root (1) + stage-1 (1) + stage-2 (1) = 3 rounds (flat-stage variant B layout).
    assert rounds.get("multi-fast-task") == 3, (
        f"Expected multi-fast-task round_count=3 (root + 2 flat stages), "
        f"got {rounds.get('multi-fast-task')}. Variant B (flat stage-N/) layout not aggregated."
    )


# ---------------------------------------------------------------------------
# JSON output schema
# ---------------------------------------------------------------------------

def test_output_schema_complete():
    """Result dict must contain all documented keys."""
    result = _run("deprecate-recommended")
    required = {
        "n_opus", "n_fast", "mean_opus_cost", "mean_fast_cost",
        "stderr_opus", "stderr_fast", "mean_opus_rounds", "mean_fast_rounds",
        "recommendation", "caveats", "n_stages_per_task", "round_count_per_task",
    }
    missing = required - result.keys()
    assert not missing, f"Missing keys in output: {missing}"


def test_insufficient_data_schema():
    """INSUFFICIENT DATA path also emits all cost/round keys (may be 0)."""
    result = _run("insufficient-fast")
    for key in ("mean_opus_cost", "mean_fast_cost", "stderr_opus", "stderr_fast",
                "mean_opus_rounds", "mean_fast_rounds"):
        assert key in result, f"Missing key {key} in INSUFFICIENT DATA result"
