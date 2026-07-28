"""T-04: behavior tests for backfill_cost_attribution.py (stage 5 of
ivg-111-cost-attribution: idempotent historical col-8 backfill).

Fixtures are authored as RAW ledger lines (never produced by a writer/flag),
per plan D-4. Loaded via spec_from_file_location + sys.modules registration
BEFORE exec_module (2026-06-17 lesson: direct package imports of an adapter
script raise ModuleNotFoundError when run against the deployed flat
~/.claude/scripts/ layout; the same-dir _load_sibling inside the module
resolves cost_from_jsonl/agent_transcript_cost/analyze_cost_ledger/cost_event
correctly at SOURCE without any extra plumbing here).

Cases (mirrors stage-5/current-plan.md T-04):
  (a) priceable unique-UUID row -> src=backfill_session, usd/tok match hand computation
  (b) unknown-* UUID -> bare src=unresolved, no usd
  (c) shared UUID across two rows -> BOTH bare src=unresolved (no double-count)
  (d) real-looking UUID with no jsonl on disk -> bare src=unresolved
  (e) row already carrying col 8 -> untouched
  (f) 6-col legacy row -> untouched (D-4)
  (g) header/blank/comment lines -> verbatim
  (h) CRIT-1 unpriceable-model row -> tok=<n>;src=unresolved, NEVER a usd
Plus: idempotency (byte-equality across two runs), label-don't-fabricate,
and --dry-run (no bytes written, counts still reported).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load backfill_cost_attribution.py via spec_from_file_location (adapter script)
# ---------------------------------------------------------------------------

_SCRIPTS_PATH = Path(__file__).resolve().parents[3] / "quoin" / "scripts"
_BCA_PATH = _SCRIPTS_PATH / "backfill_cost_attribution.py"

_MODULE_KEY = "_quoin_adapter_backfill_cost_attribution_test"
_SPEC = importlib.util.spec_from_file_location(_MODULE_KEY, _BCA_PATH)
_BCA = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_KEY] = _BCA
_SPEC.loader.exec_module(_BCA)

# Real prices per PRICES table (quoin/quoin/scripts/cost_from_jsonl.py):
#   claude-opus-4-8: input $5.00/1M, output $25.00/1M
OPUS_IN_TOK = 1000
OPUS_OUT_TOK = 200
EXPECTED_USD = round((OPUS_IN_TOK * 5.00 + OPUS_OUT_TOK * 25.00) / 1_000_000.0, 6)
EXPECTED_TOK = OPUS_IN_TOK + OPUS_OUT_TOK

UUID_PRICEABLE = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
UUID_UNKNOWN = "unknown-plan-123"
UUID_SHARED = "cccccccc-cccc-cccc-cccc-cccccccccccc"
UUID_NO_JSONL = "dddddddd-dddd-dddd-dddd-dddddddddddd"
UUID_ALREADY = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
UUID_SIXCOL = "ffffffff-ffff-ffff-ffff-ffffffffffff"
UUID_UNPRICEABLE = "88888888-8888-8888-8888-888888888888"
UNPRICEABLE_TOK = 321


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_jsonl(home: Path, proj_hash: str, uuid: str, model: str,
                 in_tok: int = 0, out_tok: int = 0) -> None:
    proj_dir = home / ".claude" / "projects" / proj_hash
    proj_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "message": {
            "model": model,
            "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
        }
    }
    (proj_dir / f"{uuid}.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


LEDGER_LINES = [
    "# Cost Ledger — my-task",
    "",
    f"{UUID_PRICEABLE} | 2026-07-27 | implement | sonnet | task | \"note a\" | 0",
    f"{UUID_UNKNOWN} | 2026-07-27 | implement | sonnet | task | \"note b\" | 0",
    f"{UUID_SHARED} | 2026-07-27 | plan | opus | task | \"note c1\" | 0",
    f"{UUID_SHARED} | 2026-07-27 | critic | opus | task | \"note c2\" | 0",
    f"{UUID_NO_JSONL} | 2026-07-27 | implement | sonnet | task | \"note d\" | 0",
    f"{UUID_ALREADY} | 2026-07-27 | implement | sonnet | task | \"note e\" | 0 | usd=0.01;tok=100;src=discover",
    f"{UUID_SIXCOL} | 2026-07-27 | implement | sonnet | task | \"note f\"",
    f"{UUID_UNPRICEABLE} | 2026-07-27 | implement | opus | task | \"note h\" | 0",
]


def _write_ledger(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Returns (project_root, home, ledger_path)."""
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    task_dir = project_root / ".workflow_artifacts" / "my-task"
    task_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = task_dir / "cost-ledger.md"
    ledger_path.write_text("\n".join(LEDGER_LINES) + "\n", encoding="utf-8")

    proj_hash = _BCA.project_hash(str(project_root))
    _make_jsonl(home, proj_hash, UUID_PRICEABLE, "claude-opus-4-8",
                OPUS_IN_TOK, OPUS_OUT_TOK)
    _make_jsonl(home, proj_hash, UUID_SHARED, "claude-opus-4-8",
                OPUS_IN_TOK, OPUS_OUT_TOK)
    _make_jsonl(home, proj_hash, UUID_UNPRICEABLE, "claude-opus-4-5-legacy",
                UNPRICEABLE_TOK, 0)
    return project_root, home, ledger_path


def _lines_by_uuid(text: str) -> dict:
    out = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        uuid = stripped.split("|")[0].strip()
        out[uuid] = stripped
    return out


# ---------------------------------------------------------------------------
# (a) priceable + hand-computation parity
# ---------------------------------------------------------------------------
def test_priceable_unique_uuid_backfilled(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    result = _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    assert result["aborted"] is False

    rows = _lines_by_uuid(ledger_path.read_text(encoding="utf-8"))
    assert rows[UUID_PRICEABLE].endswith(
        f"usd={EXPECTED_USD};tok={EXPECTED_TOK};src=backfill_session"
    )


# ---------------------------------------------------------------------------
# (b) unknown-* UUID
# ---------------------------------------------------------------------------
def test_unknown_uuid_bare_unresolved(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    rows = _lines_by_uuid(ledger_path.read_text(encoding="utf-8"))
    assert rows[UUID_UNKNOWN].endswith("| src=unresolved")
    assert "usd=" not in rows[UUID_UNKNOWN]


# ---------------------------------------------------------------------------
# (c) shared UUID across two candidate rows -> both unresolved
# ---------------------------------------------------------------------------
def test_shared_uuid_both_rows_unresolved(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    text = ledger_path.read_text(encoding="utf-8")
    shared_lines = [
        line for line in text.splitlines()
        if line.strip().startswith(UUID_SHARED)
    ]
    assert len(shared_lines) == 2
    for line in shared_lines:
        assert line.rstrip().endswith("| src=unresolved")
        assert "usd=" not in line


# ---------------------------------------------------------------------------
# (d) no jsonl on disk
# ---------------------------------------------------------------------------
def test_no_jsonl_bare_unresolved(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    rows = _lines_by_uuid(ledger_path.read_text(encoding="utf-8"))
    assert rows[UUID_NO_JSONL].endswith("| src=unresolved")
    assert "usd=" not in rows[UUID_NO_JSONL]


# ---------------------------------------------------------------------------
# (e) already-annotated row untouched
# ---------------------------------------------------------------------------
def test_already_annotated_row_untouched(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    before = [l for l in LEDGER_LINES if l.startswith(UUID_ALREADY)][0]
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    rows = _lines_by_uuid(ledger_path.read_text(encoding="utf-8"))
    assert rows[UUID_ALREADY] == before


# ---------------------------------------------------------------------------
# (f) 6-col legacy row untouched (D-4)
# ---------------------------------------------------------------------------
def test_six_col_row_untouched(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    before = [l for l in LEDGER_LINES if l.startswith(UUID_SIXCOL)][0]
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    rows = _lines_by_uuid(ledger_path.read_text(encoding="utf-8"))
    assert rows[UUID_SIXCOL] == before


# ---------------------------------------------------------------------------
# (g) header/blank/comment verbatim
# ---------------------------------------------------------------------------
def test_header_and_blank_lines_verbatim(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    after_lines = ledger_path.read_text(encoding="utf-8").splitlines()
    assert after_lines[0] == "# Cost Ledger — my-task"
    assert after_lines[1] == ""


# ---------------------------------------------------------------------------
# (h) CRIT-1 unpriceable-model row: never a fabricated usd
# ---------------------------------------------------------------------------
def test_unpriceable_model_keeps_tok_no_usd(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    rows = _lines_by_uuid(ledger_path.read_text(encoding="utf-8"))
    line = rows[UUID_UNPRICEABLE]
    assert line.endswith(f"tok={UNPRICEABLE_TOK};src=unresolved")
    assert "usd=" not in line
    # The load-bearing anti-fabrication assertion: a plain parse_session-based
    # implementation would emit "usd=0.0;src=backfill_session" here instead.
    assert "usd=0.0" not in line


# ---------------------------------------------------------------------------
# Idempotency (D-5): re-run is a strict byte no-op
# ---------------------------------------------------------------------------
def test_idempotent_rerun_is_byte_noop(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    bytes_after_run1 = ledger_path.read_bytes()

    result2 = _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    bytes_after_run2 = ledger_path.read_bytes()

    assert bytes_after_run1 == bytes_after_run2
    # Every row already carries col 8 now — nothing left to annotate.
    assert result2["annotated"] == 0
    assert result2["unresolved"] == 0


# ---------------------------------------------------------------------------
# Label-don't-fabricate: no unresolved row ever carries a usd token
# ---------------------------------------------------------------------------
def test_no_unresolved_row_carries_usd(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        if line.rstrip().endswith("src=unresolved") and "usd=" in line:
            pytest.fail(f"unresolved row unexpectedly carries usd: {line!r}")


def test_priceable_usd_matches_price_agent_jsonl(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    proj_hash = _BCA.project_hash(str(project_root))
    jf = _BCA.jsonl_path_for(UUID_PRICEABLE, proj_hash, home=home)
    hand = _BCA.price_agent_jsonl(jf)
    assert hand["priceable"] is True

    _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=False)
    rows = _lines_by_uuid(ledger_path.read_text(encoding="utf-8"))
    assert rows[UUID_PRICEABLE].endswith(
        f"usd={round(hand['usd'], 6)};tok={hand['tok']};src=backfill_session"
    )


# ---------------------------------------------------------------------------
# --dry-run: no bytes written
# ---------------------------------------------------------------------------
def test_dry_run_writes_nothing(tmp_path):
    project_root, home, ledger_path = _write_ledger(tmp_path)
    before = ledger_path.read_bytes()
    result = _BCA.backfill_ledger(ledger_path, project_root, home, dry_run=True)
    after = ledger_path.read_bytes()
    assert before == after
    # Counts are still computed and reported even though nothing was written.
    assert result["annotated"] + result["unresolved"] > 0
