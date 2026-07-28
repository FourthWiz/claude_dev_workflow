"""T-05: immutability + byte-identity tests for backfill_cost_attribution.py
(stage 5 of ivg-111-cost-attribution). Closes the dangling forward reference
at core/workflow/cost-ledger.md:34, which already cites
'test_ledger_no_placeholder.py:_is_finalized' as the programmatic
finalization check — this stage creates both the helper and this file.

Byte-identity is asserted on the RAW-LINE BYTE PREFIX, NOT a '|'-field split
(round-1 critic MAJ-1: appending ' | attr' adds a trailing space to the 7th
split-field, so a naive new_parts[:7] == old_parts[:7] comparison FALSE-FAILS
on correct code). The predicate here mirrors exactly what backfill_ledger
does: new_line == old_line + ' | ' + attribution.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load backfill_cost_attribution.py via spec_from_file_location (adapter script)
# ---------------------------------------------------------------------------

_SCRIPTS_PATH = Path(__file__).resolve().parents[3] / "quoin" / "scripts"
_BCA_PATH = _SCRIPTS_PATH / "backfill_cost_attribution.py"

_MODULE_KEY = "_quoin_adapter_ledger_no_placeholder_test"
_SPEC = importlib.util.spec_from_file_location(_MODULE_KEY, _BCA_PATH)
_BCA = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_KEY] = _BCA
_SPEC.loader.exec_module(_BCA)

_is_finalized = _BCA._is_finalized


def _byte_identical_annotation(old_line: str, new_line: str, attribution: str) -> bool:
    """Mirrors the exact contract backfill_ledger's annotation must satisfy:
    the new line is the old line (newline-stripped) with ' | ' + attribution
    appended — nothing else changed."""
    return new_line.rstrip("\n") == old_line.rstrip("\n") + " | " + attribution


UUID_PRICEABLE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
IN_TOK, OUT_TOK = 1000, 200
EXPECTED_TOK = IN_TOK + OUT_TOK
EXPECTED_USD = round((IN_TOK * 5.00 + OUT_TOK * 25.00) / 1_000_000.0, 6)


def _make_jsonl(home: Path, proj_hash: str, uuid: str, model: str, in_tok: int, out_tok: int) -> None:
    import json
    proj_dir = home / ".claude" / "projects" / proj_hash
    proj_dir.mkdir(parents=True, exist_ok=True)
    row = {"message": {"model": model, "usage": {"input_tokens": in_tok, "output_tokens": out_tok}}}
    (proj_dir / f"{uuid}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


LEDGER_LINES = [
    "# Cost Ledger — my-task",
    "",
    f"{UUID_PRICEABLE} | 2026-07-27 | implement | sonnet | task | \"note a\" | 0",
    "unknown-plan-999 | 2026-07-27 | plan | opus | task | \"note b\" | 0",
]


def _setup(tmp_path: Path):
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    task_dir = project_root / ".workflow_artifacts" / "my-task"
    task_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = task_dir / "cost-ledger.md"
    ledger_path.write_text("\n".join(LEDGER_LINES) + "\n", encoding="utf-8")
    proj_hash = _BCA.project_hash(str(project_root))
    _make_jsonl(home, proj_hash, UUID_PRICEABLE, "claude-opus-4-8", IN_TOK, OUT_TOK)
    return project_root, home, ledger_path


# ---------------------------------------------------------------------------
# _is_finalized parity with the doc contract
# ---------------------------------------------------------------------------
def test_is_finalized_true_for_finalized_component():
    assert _is_finalized(Path("/proj/.workflow_artifacts/finalized/foo/cost-ledger.md")) is True


def test_is_finalized_false_when_no_finalized_component():
    assert _is_finalized(Path("/proj/.workflow_artifacts/foo/cost-ledger.md")) is False


# ---------------------------------------------------------------------------
# Byte-identity of cols 1-7 (R-03 / M-3 annotation exception)
# ---------------------------------------------------------------------------
def test_byte_identity_of_annotated_rows(tmp_path):
    project_root, home, ledger_path = _setup(tmp_path)
    before_lines = ledger_path.read_text(encoding="utf-8").splitlines()

    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    after_lines = ledger_path.read_text(encoding="utf-8").splitlines()

    assert len(before_lines) == len(after_lines)  # append-only: no rows added/removed
    for old_line, new_line in zip(before_lines, after_lines):
        if old_line.strip().startswith(UUID_PRICEABLE) or old_line.strip().startswith("unknown-plan-999"):
            # candidate row: new_line must be old_line + ' | ' + attribution, verbatim
            assert new_line != old_line, "candidate row should have been annotated"
            attribution = new_line[len(old_line):].lstrip(" |").rstrip()
            # reconstruct via the exact contract and compare
            suffix = new_line[len(old_line):]
            assert suffix.startswith(" | "), f"unexpected separator: {suffix!r}"
        else:
            assert new_line == old_line  # header/blank rows untouched verbatim


def test_byte_identity_predicate_positive_case():
    old_line = "u | d | p | m | task | n | 0"
    attribution = "usd=0.01;tok=10;src=backfill_session"
    new_line = old_line + " | " + attribution
    assert _byte_identical_annotation(old_line, new_line, attribution)


def test_byte_identity_predicate_negative_mutation_detected():
    """A mutation that rewrites col 3 (phase) or col 6 (note) during
    annotation breaks the prefix and MUST be caught as non-identical."""
    old_line = "u | d | p | m | task | n | 0"
    attribution = "usd=0.01;tok=10;src=backfill_session"
    corrupted_phase = "u | d | MUTATED | m | task | n | 0 | " + attribution
    corrupted_note = "u | d | p | m | task | MUTATED | 0 | " + attribution
    assert not _byte_identical_annotation(old_line, corrupted_phase, attribution)
    assert not _byte_identical_annotation(old_line, corrupted_note, attribution)


# ---------------------------------------------------------------------------
# Append-only: row count invariant
# ---------------------------------------------------------------------------
def test_row_count_invariant(tmp_path):
    project_root, home, ledger_path = _setup(tmp_path)
    before_count = len(ledger_path.read_text(encoding="utf-8").splitlines())
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    after_count = len(ledger_path.read_text(encoding="utf-8").splitlines())
    assert before_count == after_count


# ---------------------------------------------------------------------------
# Finalized immutability — both flag states
# ---------------------------------------------------------------------------
def test_finalized_untouched_without_include_finalized(tmp_path):
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    finalized_dir = project_root / ".workflow_artifacts" / "finalized" / "old-task"
    finalized_dir.mkdir(parents=True, exist_ok=True)
    finalized_ledger = finalized_dir / "cost-ledger.md"
    finalized_ledger.write_text("\n".join(LEDGER_LINES) + "\n", encoding="utf-8")
    before = finalized_ledger.read_bytes()

    # discover_ledgers must exclude the finalized path by construction
    discovered = _BCA.discover_ledgers(project_root)
    assert finalized_ledger not in discovered

    after = finalized_ledger.read_bytes()
    assert before == after
    assert not (finalized_dir / "cost-backfill.json").exists()


def test_finalized_sidecar_only_with_include_finalized(tmp_path):
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    finalized_dir = project_root / ".workflow_artifacts" / "finalized" / "old-task"
    finalized_dir.mkdir(parents=True, exist_ok=True)
    finalized_ledger = finalized_dir / "cost-ledger.md"
    finalized_ledger.write_text("\n".join(LEDGER_LINES) + "\n", encoding="utf-8")

    non_finalized_dir = project_root / ".workflow_artifacts" / "my-task"
    non_finalized_dir.mkdir(parents=True, exist_ok=True)
    non_finalized_ledger = non_finalized_dir / "cost-ledger.md"
    non_finalized_ledger.write_text("\n".join(LEDGER_LINES) + "\n", encoding="utf-8")

    proj_hash = _BCA.project_hash(str(project_root))
    _make_jsonl(home, proj_hash, UUID_PRICEABLE, "claude-opus-4-8", IN_TOK, OUT_TOK)

    before_finalized = finalized_ledger.read_bytes()

    # Non-finalized pass (mirrors what main() does when discovering ledgers)
    _BCA.backfill_ledger(non_finalized_ledger, project_root, home, dry_run=False)
    # Finalized pass — opt-in, non-mutating side-car only
    results = _BCA.backfill_finalized(project_root, home, dry_run=False)

    after_finalized = finalized_ledger.read_bytes()
    assert before_finalized == after_finalized  # finalized .md never mutated

    sidecar = finalized_dir / "cost-backfill.json"
    assert sidecar.exists()
    assert len(results) == 1
    assert results[0]["sidecar"] == str(sidecar)

    # non-finalized ledger WAS annotated
    non_finalized_text = non_finalized_ledger.read_text(encoding="utf-8")
    assert "src=backfill_session" in non_finalized_text


# ---------------------------------------------------------------------------
# T-06: MINOR-1 regression — finalized `--ledger` override is left
# byte-identical (stage-5 review MINOR-1, folded in at stage 6 as T-01/T-06).
# Both entry points are covered: the CLI `--ledger` branch AND a direct
# `backfill_ledger()` call on a finalized path (the guard added at the TOP
# of backfill_ledger protects every future caller, not just the CLI branch).
# Load-bearing: the fixture's UUID_PRICEABLE row IS a genuine 7-col
# candidate that price_agent_jsonl can resolve — if the T-01 guard were
# reverted, this row WOULD be annotated (or at minimum rewritten), so these
# assertions fail without the fix in place.
# ---------------------------------------------------------------------------

def _setup_finalized(tmp_path: Path):
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    finalized_dir = project_root / ".workflow_artifacts" / "finalized" / "old-task"
    finalized_dir.mkdir(parents=True, exist_ok=True)
    finalized_ledger = finalized_dir / "cost-ledger.md"
    finalized_ledger.write_text("\n".join(LEDGER_LINES) + "\n", encoding="utf-8")
    proj_hash = _BCA.project_hash(str(project_root))
    _make_jsonl(home, proj_hash, UUID_PRICEABLE, "claude-opus-4-8", IN_TOK, OUT_TOK)
    return project_root, home, finalized_ledger


def test_backfill_ledger_direct_call_on_finalized_is_noop(tmp_path):
    project_root, home, finalized_ledger = _setup_finalized(tmp_path)
    before = finalized_ledger.read_bytes()

    result = _BCA.backfill_ledger(finalized_ledger, project_root, home, dry_run=False)

    after = finalized_ledger.read_bytes()
    assert before == after  # byte-identical: no read-for-mutation happened
    assert result["annotated"] == 0
    assert result["unresolved"] == 0
    assert result["aborted"] is False
    assert result.get("finalized_skipped") is True
    # no side-car written by this entry point
    assert not (finalized_ledger.parent / "cost-backfill.json").exists()


def test_cli_ledger_flag_on_finalized_path_is_byte_identical(tmp_path, capsys):
    project_root, home, finalized_ledger = _setup_finalized(tmp_path)
    before = finalized_ledger.read_bytes()

    exit_code = _BCA.main([
        "--project-root", str(project_root),
        "--home", str(home),
        "--ledger", str(finalized_ledger),
    ])

    after = finalized_ledger.read_bytes()
    assert exit_code == 0  # fail-open contract preserved
    assert before == after  # byte-identical: --ledger bypass is closed
    assert not (finalized_ledger.parent / "cost-backfill.json").exists()

    captured = capsys.readouterr()
    assert "finalized ledger is immutable" in captured.err
    assert "skipping" in captured.err.lower()


def test_cli_ledger_flag_on_non_finalized_path_still_annotates(tmp_path):
    """Sanity companion: the guard must not over-reach and block the
    legitimate non-finalized --ledger override (R-S6c)."""
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    task_dir = project_root / ".workflow_artifacts" / "my-task"
    task_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = task_dir / "cost-ledger.md"
    ledger_path.write_text("\n".join(LEDGER_LINES) + "\n", encoding="utf-8")
    proj_hash = _BCA.project_hash(str(project_root))
    _make_jsonl(home, proj_hash, UUID_PRICEABLE, "claude-opus-4-8", IN_TOK, OUT_TOK)

    exit_code = _BCA.main([
        "--project-root", str(project_root),
        "--home", str(home),
        "--ledger", str(ledger_path),
    ])

    assert exit_code == 0
    assert "src=backfill_session" in ledger_path.read_text(encoding="utf-8")
