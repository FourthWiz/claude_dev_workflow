"""T-06 (IVG-157): Unit tests for `cohort_attribution` in core/scripts/cost_event.py.

Loads cost_event.py via importlib.util.spec_from_file_location, matching the
established test pattern (see test_cost_core_no_claude_terms.py's REPO_ROOT
anchor and test_analyze_cost_ledger.py's sibling-load pattern).

Non-negotiables under test (see current-plan.md "Decisions locked"):
- Q-01 = LABELED BUCKET: a shared-UUID cohort (>=2 phases on one UUID) must
  show a single labeled `shared-session (multi-phase)` bucket, never a
  whole-session number folded onto any one phase, never a silent $0.
- Solo-UUID phases stay byte-identical (their cost/count show up in
  by_phase/by_model exactly as the pre-cohort code would have produced).
- D-03: checkpoint save/restore classification is exact-match on 'restore',
  not a substring test.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_CE_PATH = REPO_ROOT / "quoin" / "core" / "scripts" / "cost_event.py"

_SPEC = importlib.util.spec_from_file_location("_quoin_core_cost_event_cohort_test", _CE_PATH)
_CE = importlib.util.module_from_spec(_SPEC)
sys.modules["_quoin_core_cost_event_cohort_test"] = _CE
_SPEC.loader.exec_module(_CE)

cohort_attribution = _CE.cohort_attribution
CohortResult = _CE.CohortResult
checkpoint_op = _CE.checkpoint_op
CostEvent = _CE.CostEvent


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _row(uuid, phase, model="opus", note="", attribution=""):
    """Build a plain-dict ledger row (the shape used by analyze/dashboard
    readers) — cohort_attribution must accept this shape without requiring
    a CostEvent instance."""
    return {
        "uuid": uuid,
        "date_str": "2026-07-27",
        "phase": phase,
        "model": model,
        "note": note,
        "attribution": attribution,
    }


def _fixed_resolver(cost, has_cost=True, calls=None):
    """A resolver that always returns (cost, has_cost) and records every
    uuid it was called with (to assert 'at most once per uuid')."""
    def resolver(uuid):
        if calls is not None:
            calls.append(uuid)
        return (cost, has_cost)
    return resolver


# ---------------------------------------------------------------------------
# solo-UUID exact
# ---------------------------------------------------------------------------

def test_solo_uuid_exact_attribution():
    rows = [_row("uuid-solo", "plan")]
    calls = []
    result = cohort_attribution(rows, _fixed_resolver(5.0, True, calls))

    assert isinstance(result, CohortResult)
    assert result.by_phase["plan"]["cost"] == pytest.approx(5.0)
    assert result.by_phase["plan"]["count"] == 1
    assert result.shared_bucket == {}
    assert result.resolved_total == pytest.approx(5.0)
    assert calls == ["uuid-solo"]


# ---------------------------------------------------------------------------
# 2-cohort — shared UUID, resolver called ONCE
# ---------------------------------------------------------------------------

def test_two_row_cohort_shared_uuid_counted_once():
    rows = [
        _row("uuid-shared", "plan"),
        _row("uuid-shared", "checkpoint", note="save"),
    ]
    calls = []
    result = cohort_attribution(rows, _fixed_resolver(9.0, True, calls))

    assert calls == ["uuid-shared"]  # resolver called ONCE for the shared uuid
    assert "plan" not in result.by_phase
    assert "checkpoint" not in result.by_phase
    assert result.shared_bucket["cost"] == pytest.approx(9.0)
    assert result.shared_bucket["uuids"] == 1
    assert result.resolved_total == pytest.approx(9.0)  # NOT 2x


# ---------------------------------------------------------------------------
# 6-cohort golden — synthesized 53e84b7c-style cohort
# ---------------------------------------------------------------------------

def test_six_row_cohort_golden_53e84b7c_style():
    uuid = "53e84b7c-cohort"
    rows = [
        _row(uuid, "thorough-plan"),
        _row(uuid, "thorough-plan"),
        _row(uuid, "architect"),
        _row(uuid, "implement"),
        _row(uuid, "review"),
        _row(uuid, "checkpoint", note="save"),
    ]
    calls = []
    result = cohort_attribution(rows, _fixed_resolver(42.0, True, calls))

    assert calls == [uuid]  # exactly once, not 6x
    assert result.resolved_total == pytest.approx(42.0)  # NOT 6x
    assert "checkpoint" not in result.by_phase  # no whole-session dollar anywhere
    assert result.shared_bucket["cost"] == pytest.approx(42.0)
    assert result.shared_bucket["uuids"] == 1
    assert result.shared_bucket["phases"]["checkpoint"] == {
        "save": 1, "restore": 0, "count": 1,
    }
    assert result.shared_bucket["phases"]["thorough-plan"]["count"] == 2


# ---------------------------------------------------------------------------
# resolved-inline summed directly — resolver NOT called, not in any cohort
# ---------------------------------------------------------------------------

def test_resolved_inline_row_summed_directly_resolver_not_called():
    rows = [_row("uuid-8res", "implement", attribution="usd=1.5;tok=1000;src=nested_jsonl")]
    calls = []
    result = cohort_attribution(rows, _fixed_resolver(999.0, True, calls))

    assert calls == []  # resolver never invoked for a resolved-inline row
    assert result.by_phase["implement"]["cost"] == pytest.approx(1.5)
    assert result.resolved_total == pytest.approx(1.5)
    assert result.shared_bucket == {}


# ---------------------------------------------------------------------------
# unresolvable — counted, never folded to $0
# ---------------------------------------------------------------------------

def test_unresolvable_row_counted_never_zero():
    rows = [_row("uuid-8unres", "implement", attribution="tok=45;src=unresolved")]
    result = cohort_attribution(rows, _fixed_resolver(999.0, True))

    assert result.unresolvable_count == 1
    assert result.resolved_total == 0.0
    assert result.by_phase == {}


# ---------------------------------------------------------------------------
# solo-legacy no-cost-source — resolver returns has_cost=False
# ---------------------------------------------------------------------------

def test_solo_legacy_no_cost_source_never_silent_zero():
    rows = [_row("uuid-no-cost", "plan")]
    result = cohort_attribution(rows, _fixed_resolver(0.0, False))

    assert result.unresolvable_count == 1
    assert result.unpriced_count == 1
    assert result.by_phase == {}
    assert result.resolved_total == 0.0


# ---------------------------------------------------------------------------
# D-03 note classification
# ---------------------------------------------------------------------------

def test_checkpoint_op_classification():
    assert checkpoint_op("save (restore mode)") == "save"
    assert checkpoint_op("restore") == "restore"
    assert checkpoint_op("save") == "save"
    assert checkpoint_op(" restore ") == "restore"


# ---------------------------------------------------------------------------
# MIN-2 anti-inflation: by_model + top_sessions related invariants
# ---------------------------------------------------------------------------

def test_shared_cohort_never_inflates_by_model():
    uuid = "model-cohort"
    rows = [
        _row(uuid, "thorough-plan", model="opus"),
        _row(uuid, "checkpoint", model="opus", note="save"),
    ]
    result = cohort_attribution(rows, _fixed_resolver(10.0, True))

    # Shared rows contribute NEITHER cost NOR count to by_model.
    assert "opus" not in result.by_model
    assert result.shared_bucket["cost"] == pytest.approx(10.0)


def test_solo_and_shared_mixed_by_model_only_reflects_solo():
    shared_uuid = "shared-uuid-x"
    solo_uuid = "solo-uuid-y"
    rows = [
        _row(shared_uuid, "thorough-plan", model="opus"),
        _row(shared_uuid, "checkpoint", model="opus", note="save"),
        _row(solo_uuid, "implement", model="sonnet"),
    ]

    def resolver(uuid):
        return (10.0, True) if uuid == shared_uuid else (2.0, True)

    result = cohort_attribution(rows, resolver)

    assert result.by_model.get("sonnet", {}).get("cost") == pytest.approx(2.0)
    assert "opus" not in result.by_model
    assert result.resolved_total == pytest.approx(12.0)  # 10 (shared, once) + 2 (solo)


# ---------------------------------------------------------------------------
# core-purity guard: no WORDLIST term in the new symbols themselves
# ---------------------------------------------------------------------------

def test_new_core_symbols_carry_no_adapter_vocabulary():
    forbidden = ["jsonl", "ccusage", "claude-opus", "claude-sonnet", "claude-haiku"]
    for name in ("cohort_attribution", "CohortResult", "checkpoint_op"):
        obj = getattr(_CE, name)
        doc = (obj.__doc__ or "").lower()
        for term in forbidden:
            assert term not in doc, f"{name}.__doc__ contains forbidden term {term!r}"


# ---------------------------------------------------------------------------
# --since interaction: caller filters BEFORE calling; cohort forms over the
# filtered set only. This test documents/asserts that cohort_attribution
# itself performs no date filtering — it groups whatever it's given.
# ---------------------------------------------------------------------------

def test_since_filtered_cohort_only_groups_rows_it_is_given():
    uuid = "straddle-uuid"
    all_rows = [
        _row(uuid, "plan"),
        _row(uuid, "checkpoint", note="save"),
    ]
    # Simulate the caller applying --since and excluding the checkpoint row.
    in_window_rows = [all_rows[0]]

    calls = []
    result = cohort_attribution(in_window_rows, _fixed_resolver(7.0, True, calls))

    # Only one row in the filtered set => solo, not shared.
    assert result.shared_bucket == {}
    assert result.by_phase["plan"]["cost"] == pytest.approx(7.0)
    assert calls == [uuid]


# ---------------------------------------------------------------------------
# fail-open: resolver raises for a uuid => treated as (0.0, False), no crash
# ---------------------------------------------------------------------------

def test_resolver_raising_is_treated_as_no_cost_not_a_crash():
    def raising_resolver(uuid):
        raise RuntimeError("boom")

    rows = [_row("uuid-raises", "plan")]
    result = cohort_attribution(rows, raising_resolver)

    assert result is not None
    assert result.unresolvable_count == 1
    assert result.resolved_total == 0.0


def test_resolver_raising_inside_shared_cohort_is_treated_as_no_cost():
    uuid = "uuid-raises-shared"

    def raising_resolver(u):
        raise ValueError("nope")

    rows = [_row(uuid, "plan"), _row(uuid, "checkpoint", note="save")]
    result = cohort_attribution(rows, raising_resolver)

    assert result is not None
    assert result.shared_bucket == {}
    assert result.unresolvable_count == 1
    assert result.resolved_total == 0.0


# ---------------------------------------------------------------------------
# CostEvent-shaped rows (attribute access, not dict access) also work
# ---------------------------------------------------------------------------

def test_cost_event_instances_accepted_directly():
    events = [
        CostEvent(
            uuid="ce-uuid", date="2026-07-27", phase="plan",
            model_or_effort="opus", category="task", note="",
        ),
    ]
    result = cohort_attribution(events, _fixed_resolver(3.0, True))
    assert result.by_phase["plan"]["cost"] == pytest.approx(3.0)
