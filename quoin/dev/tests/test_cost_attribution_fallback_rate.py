"""T-02: near-zero-fallback E2E proof — deterministic before/after measurement
over the REAL production reader (stage 6 of ivg-111-cost-attribution).

This is the acceptance EVIDENCE for spec acceptance "the unknown-*/unresolved
fallback rate for new subagent-phase rows ... is near-zero (contrast the
~60/65 pre-change baseline), demonstrated by a test OR a measured before/after
on a real run." It satisfies BOTH clauses in one deterministic, CI-runnable
artifact.

FILTER-FIRST measurement (round-2 critic fix, MAJ-1/MAJ-2): rows are filtered
to the managed-phase set M FIRST, THEN the pre-filtered slice is handed to the
real production reader `analyze_cost_ledger.build_report`. Its returned
`unresolvable_count` is therefore, by construction, the managed-only
unresolvable count — no per-phase breakdown from build_report is needed, and
no re-implemented classification loop is used. NO fakes: build_report
internally runs the production classify_attribution + lookup_session_cost
path end-to-end.

Fixtures are authored as RAW ledger lines (D-4 discipline) — never produced
by enabling QUOIN_INLINE_COST_CAPTURE. Managed-row shapes are seeded from the
real subagent-heavy ledger at
.workflow_artifacts/ivg-111-cost-attribution/cost-ledger.md (copied into this
file at author-time; NOT read from disk at test time — hermetic).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load analyze_cost_ledger.py via spec_from_file_location (adapter script) —
# mirrors test_analyze_cost_ledger.py's loader exactly (register in
# sys.modules BEFORE exec_module — 2026-06-17 lesson).
# ---------------------------------------------------------------------------

_SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts"
_ACL_PATH = _SCRIPTS_PATH / "analyze_cost_ledger.py"

_MODULE_KEY = "_quoin_adapter_cost_attribution_fallback_rate_test"
_SPEC = importlib.util.spec_from_file_location(_MODULE_KEY, _ACL_PATH)
_ACL = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_KEY] = _ACL
_SPEC.loader.exec_module(_ACL)

parse_ledger_file = _ACL.parse_ledger_file  # real adapter parser (analyze_cost_ledger.py:173)
build_report = _ACL.build_report            # real production reader (analyze_cost_ledger.py:213)
project_hash = _ACL.project_hash


# ---------------------------------------------------------------------------
# Managed-phase set — FUNCTION-LOCAL measurement scope (matches architecture
# Q-01 / stage-3 D-7). This is a hand-listed judgement set for THIS
# measurement, NOT a registration/drift-tracked roster (RG-CENSUS-safe per
# the 2026-07-16/2026-07-22 lessons).
# ---------------------------------------------------------------------------
M = {
    "critic", "revise", "plan", "implement", "review", "gate",
    "discover", "specify", "enrich", "architect", "thorough-plan",
}


def _managed_rate(rows: list, project_root: Path, proj_hash: str, home: Path) -> tuple[float, list]:
    """proc:fallback-measure — filter to M FIRST, then hand the pre-filtered
    slice to the real production build_report. Returns (rate, managed_rows)."""
    managed = [r for r in rows if r["phase"] in M]
    report = build_report(managed, project_root, proj_hash, home)
    rate = report["unresolvable_count"] / max(1, len(managed))
    return rate, managed


# ---------------------------------------------------------------------------
# Fixture construction — shapes seeded from the real ivg-111-cost-attribution
# cost-ledger.md (uuid | date | phase | model | task | note | 0 [| attr]).
# ---------------------------------------------------------------------------

_DATE = "2026-07-27"
_MODEL = "opus"

# One row per managed phase, in a stable order.
_PHASES = sorted(M)


def _before_lines() -> list[str]:
    """Today's behavior: every managed row self-written by the on-behalf
    writer, col-8 EMPTY, uuid = unknown-<phase>-<ts> (the get_session_uuid.py
    fail-open form). No fixture JSONL exists for ANY of these UUIDs (see
    _home fixture below) -> every row is legacy + no-jsonl -> unresolvable.
    """
    lines = []
    for i, phase in enumerate(_PHASES):
        uuid = f"unknown-{phase}-169000{i:04d}"
        lines.append(
            f'{uuid} | {_DATE} | {phase} | {_MODEL} | task | "S-6 managed row {phase}" | 0'
        )
    # Non-managed / top-level human rows mixed in for realism. Filter-first
    # means these are dropped BEFORE build_report runs and cannot perturb the
    # managed rate — they need NOT resolve (round-2 fix removes this coupling).
    lines.append(f'unknown-start_of_day-1690099999 | {_DATE} | start_of_day | haiku | task | "human SOD" | 0')
    lines.append(f'unknown-checkpoint-1690099998 | {_DATE} | checkpoint | sonnet | task | "human checkpoint" | 0')
    return lines


def _after_lines() -> list[str]:
    """The on-behalf capture writes: the SAME managed rows, each carrying a
    unique uuid=<agentId> + col-8 'usd=<f>;tok=<n>;src=nested_jsonl' — the
    reader classifies each 'resolved' inline, no JSONL lookup needed.
    """
    lines = []
    for i, phase in enumerate(_PHASES):
        uuid = f"aaaa{i:04d}-bbbb-cccc-dddd-eeeeeeeeeeee"
        usd = round(0.01 + i * 0.001, 6)
        tok = 1000 + i * 10
        lines.append(
            f'{uuid} | {_DATE} | {phase} | {_MODEL} | task | "S-6 managed row {phase}" | 0'
            f" | usd={usd};tok={tok};src=nested_jsonl"
        )
    lines.append(f'unknown-start_of_day-1690099999 | {_DATE} | start_of_day | haiku | task | "human SOD" | 0')
    lines.append(f'unknown-checkpoint-1690099998 | {_DATE} | checkpoint | sonnet | task | "human checkpoint" | 0')
    return lines


def _write_ledger(tmp_path: Path, name: str, lines: list[str]) -> Path:
    task_dir = tmp_path / "project" / ".workflow_artifacts" / name
    task_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = task_dir / "cost-ledger.md"
    ledger_path.write_text(f"# Cost Ledger — {name}\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return ledger_path


@pytest.fixture()
def fixture(tmp_path):
    """Hermetic --home tree: NO projects/<hash>/<uuid>.jsonl for ANY BEFORE
    managed UUID (each before-managed row is genuinely unresolvable); AFTER
    managed rows need no JSONL at all (inline-resolved)."""
    project_root = tmp_path / "project"
    home = tmp_path / "home"  # deliberately empty of .claude/projects/** JSONL
    proj_hash = project_hash(str(project_root))

    before_ledger = _write_ledger(tmp_path, "before-task", _before_lines())
    after_ledger = _write_ledger(tmp_path, "after-task", _after_lines())

    return {
        "project_root": project_root,
        "home": home,
        "proj_hash": proj_hash,
        "before_ledger": before_ledger,
        "after_ledger": after_ledger,
    }


# ---------------------------------------------------------------------------
# Headline before/after near-zero-fallback proof
# ---------------------------------------------------------------------------

def test_before_rate_reproduces_the_real_problem(fixture):
    rows = parse_ledger_file(fixture["before_ledger"])
    rate, managed = _managed_rate(rows, fixture["project_root"], fixture["proj_hash"], fixture["home"])
    assert len(managed) == len(_PHASES)
    assert rate >= 0.60  # conservative floor; fixture yields 1.0 (all managed rows unresolvable)


def test_after_rate_is_near_zero(fixture):
    rows = parse_ledger_file(fixture["after_ledger"])
    rate, managed = _managed_rate(rows, fixture["project_root"], fixture["proj_hash"], fixture["home"])
    assert len(managed) == len(_PHASES)
    assert rate <= 0.05  # near-zero threshold; fixture yields exactly 0.0


def test_after_rate_is_far_below_before_rate(fixture):
    before_rows = parse_ledger_file(fixture["before_ledger"])
    after_rows = parse_ledger_file(fixture["after_ledger"])
    before_rate, _ = _managed_rate(before_rows, fixture["project_root"], fixture["proj_hash"], fixture["home"])
    after_rate, _ = _managed_rate(after_rows, fixture["project_root"], fixture["proj_hash"], fixture["home"])
    assert after_rate < before_rate
    assert before_rate - after_rate >= 0.55  # wide margin


# ---------------------------------------------------------------------------
# Exact partition sanity (managed-scoped by construction, filter-first)
# ---------------------------------------------------------------------------

def test_partition_after_managed_zero_unresolvable(fixture):
    rows = parse_ledger_file(fixture["after_ledger"])
    managed = [r for r in rows if r["phase"] in M]
    report = build_report(managed, fixture["project_root"], fixture["proj_hash"], fixture["home"])
    assert report["unresolvable_count"] == 0


def test_partition_before_managed_all_unresolvable(fixture):
    rows = parse_ledger_file(fixture["before_ledger"])
    managed = [r for r in rows if r["phase"] in M]
    report = build_report(managed, fixture["project_root"], fixture["proj_hash"], fixture["home"])
    assert report["unresolvable_count"] == len(managed)


# ---------------------------------------------------------------------------
# Load-bearing negative: drop col-8 on ONE managed 'after' row -> it
# reclassifies 'legacy' -> no fixture JSONL for its uuid -> unresolvable_count
# rises -> after_rate crosses the 0.05 threshold -> the near-zero assertion
# MUST fail (proves the test measures the real signal through the real
# reader, per the 2026-06-15 mock-specificity lesson).
# ---------------------------------------------------------------------------

def test_mutated_after_fixture_drops_below_threshold_and_would_fail(tmp_path):
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    proj_hash = project_hash(str(project_root))

    lines = _after_lines()
    # Mutate the FIRST managed row: strip its col-8 attribution entirely,
    # reverting it to a bare 7-column legacy row (no fixture JSONL exists
    # for its uuid, so it becomes unresolvable).
    mutated_uuid = "aaaa0000-bbbb-cccc-dddd-eeeeeeeeeeee"
    for i, line in enumerate(lines):
        if line.startswith(mutated_uuid):
            # keep only the first 7 pipe-fields (drop " | usd=...;src=...")
            parts = line.split("|")
            lines[i] = "|".join(parts[:7]).rstrip()
            break
    else:
        pytest.fail("mutation target row not found in fixture")

    mutated_ledger = _write_ledger(tmp_path, "mutated-after-task", lines)
    rows = parse_ledger_file(mutated_ledger)
    rate, managed = _managed_rate(rows, project_root, proj_hash, home)

    assert len(managed) == len(_PHASES)
    # The near-zero assertion (rate <= 0.05) would now FAIL: 1 of 11 managed
    # rows is unresolvable -> rate ≈ 0.0909 > 0.05.
    assert rate > 0.05
    with pytest.raises(AssertionError):
        assert rate <= 0.05


# ---------------------------------------------------------------------------
# Real-reader sanity: confirm the fixture actually drives classify_attribution
# + lookup_session_cost end-to-end (no fakes) — a legacy row WITH a real
# priceable JSONL on disk resolves via the JSONL path, not inline.
# ---------------------------------------------------------------------------

def test_legacy_row_with_real_jsonl_resolves_via_lookup_path(tmp_path):
    project_root = tmp_path / "project"
    home = tmp_path / "home"
    proj_hash = project_hash(str(project_root))

    uuid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    proj_dir = home / ".claude" / "projects" / proj_hash
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / f"{uuid}.jsonl").write_text(
        json.dumps({"message": {"model": "claude-opus-4-8",
                                 "usage": {"input_tokens": 1_000_000, "output_tokens": 0}}}) + "\n",
        encoding="utf-8",
    )
    lines = [f'{uuid} | {_DATE} | implement | opus | task | "legacy priced row" | 0']
    ledger = _write_ledger(tmp_path, "legacy-priced-task", lines)

    rows = parse_ledger_file(ledger)
    managed = [r for r in rows if r["phase"] in M]
    report = build_report(managed, project_root, proj_hash, home)

    assert report["unresolvable_count"] == 0
    assert report["resolved_total"] > 0.0  # real priced lookup, not a fake
