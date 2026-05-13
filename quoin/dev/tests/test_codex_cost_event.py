"""Tests for the repo-local Codex cost event writer/checker."""

import importlib.util
import subprocess
import sys
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent
REPO_ROOT = PKG_DIR.parent
CODEX_COST_PATH = PKG_DIR / "adapters" / "codex" / "cost_event.py"
CORE_COST_PATH = PKG_DIR / "core" / "scripts" / "cost_event.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


codex_cost = _load_module(CODEX_COST_PATH, "_quoin_codex_cost_event_test")
core_cost = _load_module(CORE_COST_PATH, "_quoin_core_cost_event_for_codex_test")


def test_codex_cost_script_exists():
    assert CODEX_COST_PATH.is_file()


def test_codex_cost_self_test_passes():
    result = subprocess.run(
        [sys.executable, str(CODEX_COST_PATH), "--self-test"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "CODEX COST PASS" in result.stdout


def test_codex_writer_emits_valid_portable_cost_event(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(CODEX_COST_PATH),
            "write",
            "--project-root",
            str(tmp_path),
            "--task",
            "phase-35-codex-cost",
            "--phase",
            "implement",
            "--effort",
            "medium",
            "--timestamp",
            "2026-05-13T12:34:56Z",
            "--note",
            "repo-local writer test",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    ledger = tmp_path / ".workflow_artifacts" / "phase-35-codex-cost" / "cost-ledger.md"
    rows = [
        line for line in ledger.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    ]
    assert len(rows) == 1

    event = core_cost.parse_row(rows[0], source=str(ledger), lineno=2)
    assert event is not None
    assert event.uuid.startswith("unknown-codex-")
    assert event.date == "2026-05-13"
    assert event.phase == "implement"
    assert event.model_or_effort == "medium"
    assert event.category == "task"
    assert event.fallback_fires == 0
    assert "runtime=codex" in event.note
    assert "task=phase-35-codex-cost" in event.note
    assert "timestamp=2026-05-13T12:34:56Z" in event.note
    assert "session_id=unknown" in event.note
    assert "input_tokens=not_available" in event.note
    assert "output_tokens=not_available" in event.note
    assert "total_tokens=not_available" in event.note
    assert "cost_usd=not_available" in event.note
    assert "telemetry_source=not_available" in event.note

    validation = subprocess.run(
        [
            sys.executable,
            str(CODEX_COST_PATH),
            "validate",
            "--project-root",
            str(tmp_path),
            "--task",
            "phase-35-codex-cost",
            "--expect-codex",
        ],
        capture_output=True,
        text=True,
    )
    assert validation.returncode == 0, validation.stderr
    assert "CODEX COST PASS" in validation.stdout


def test_codex_validator_rejects_guessed_token_and_cost_fields(tmp_path):
    ledger = tmp_path / ".workflow_artifacts" / "bad-codex-cost" / "cost-ledger.md"
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        "# Cost Ledger - bad-codex-cost\n"
        "unknown-codex-bad | 2026-05-13 | plan | high | task | "
        "runtime=codex; task=bad-codex-cost; timestamp=2026-05-13T12:34:56Z; "
        "session_id=unknown; effort=high; input_tokens=123; output_tokens=456; "
        "cache_creation_input_tokens=not_available; cache_read_input_tokens=not_available; "
        "total_tokens=579; cost_usd=1.23; telemetry_source=not_available | 0\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(CODEX_COST_PATH),
            "validate",
            "--ledger",
            str(ledger),
            "--expect-codex",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "input_tokens must be not_available" in result.stderr
    assert "output_tokens must be not_available" in result.stderr
    assert "total_tokens must be not_available" in result.stderr
    assert "cost_usd must be not_available" in result.stderr


def test_codex_cost_adapter_has_no_claude_dependency_leakage():
    text = CODEX_COST_PATH.read_text(encoding="utf-8")
    forbidden = [
        "cost_from_jsonl",
        "ccusage",
        "~/." + "claude",
        "$HOME/." + "claude",
        "." + "claude/",
    ]
    hits = [token for token in forbidden if token in text]
    assert hits == []
