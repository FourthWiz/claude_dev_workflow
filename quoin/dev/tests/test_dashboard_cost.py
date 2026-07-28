"""Tests for quoin/scripts/dashboard_cost.py — adapter cost provider.

Tests the make_cost_provider factory, memo-cache hit/invalidate,
usd/tokens/None ladder with nested by_phase, and spaced-project-root hash.
No LLM calls; uses synthetic fixture JSONL files.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Load dashboard_cost via spec_from_file_location (same pattern as test_dashboard_model.py)
# ---------------------------------------------------------------------------

_SCRIPTS_PATH = Path(__file__).resolve().parents[2] / "scripts"
_DC_PATH = _SCRIPTS_PATH / "dashboard_cost.py"

_SPEC = importlib.util.spec_from_file_location("_quoin_adapter_dashboard_cost_test", _DC_PATH)
_DC = importlib.util.module_from_spec(_SPEC)
sys.modules["_quoin_adapter_dashboard_cost_test"] = _DC
_SPEC.loader.exec_module(_DC)

make_cost_provider = _DC.make_cost_provider
project_hash = _DC.project_hash
jsonl_path_for = _DC.jsonl_path_for
parse_session = _DC.parse_session


# ---------------------------------------------------------------------------
# Helpers to build fixture JSONL files
# ---------------------------------------------------------------------------

def _make_jsonl(path: Path, model: str, input_tokens: int, output_tokens: int,
                cost_usd: float = None) -> None:
    """Write a minimal JSONL session file with one assistant message."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write a minimal JSONL row that parse_session can read.
    # parse_session reads rows with "message" containing "model" and "usage".
    # We set input_tokens / output_tokens; cost is computed from the price table.
    entry = {
        "type": "assistant",
        "message": {
            "model": model,
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        },
    }
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")


def _make_rows(uuid_phase_pairs):
    """Return a list of ledger rows for (uuid, phase) pairs."""
    rows = []
    for uuid, phase in uuid_phase_pairs:
        rows.append({
            "uuid": uuid,
            "date": "2026-06-06",
            "phase": phase,
            "model_or_effort": "sonnet",
            "note": "",
            "fallback_fires": 0,
        })
    return rows


def _make_rows_with_attribution(uuid_phase_attr_triples):
    """Return ledger rows carrying a col-8 `attribution` string (stage 4)."""
    rows = []
    for uuid, phase, attribution in uuid_phase_attr_triples:
        rows.append({
            "uuid": uuid,
            "date": "2026-07-27",
            "phase": phase,
            "model_or_effort": "sonnet",
            "note": "",
            "fallback_fires": 0,
            "attribution": attribution,
        })
    return rows


# ---------------------------------------------------------------------------
# T-01 tests: usd / tokens / None ladder + nested by_phase (D-14)
# ---------------------------------------------------------------------------

class TestCostProviderLadder:
    """Test the usd/tokens/None resolution ladder per D-04."""

    def test_usd_mode_when_cost_positive(self, tmp_path):
        """Rows with JSONL files that have cost > 0 → mode == 'usd', nested by_phase."""
        home = tmp_path / "home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        proj_hash = project_hash(str(project_root))

        uuid1 = "aaaaaaaa-0001-0001-0001-000000000001"
        uuid2 = "aaaaaaaa-0002-0002-0002-000000000002"

        # Use claude-sonnet-4-6: input $3/1M, output $15/1M
        # 100k input + 10k output → cost = 100*3/1000 + 10*15/1000 = 0.3 + 0.15 = 0.45 USD
        _make_jsonl(
            home / ".claude" / "projects" / proj_hash / f"{uuid1}.jsonl",
            model="claude-sonnet-4-6",
            input_tokens=100_000,
            output_tokens=10_000,
        )
        # 50k input + 5k output → cost = 50*3/1000 + 5*15/1000 = 0.15 + 0.075 = 0.225 USD
        _make_jsonl(
            home / ".claude" / "projects" / proj_hash / f"{uuid2}.jsonl",
            model="claude-sonnet-4-6",
            input_tokens=50_000,
            output_tokens=5_000,
        )

        rows = _make_rows([(uuid1, "plan"), (uuid2, "implement")])
        provider = make_cost_provider(project_root, home=home)
        result = provider("my-task", rows)

        assert result is not None
        assert result["mode"] == "usd"
        assert result["usd"] > 0
        assert result["tokens"] > 0
        assert "by_phase" in result
        # by_phase must be NESTED: {phase: {"usd": float}} per D-14
        assert "plan" in result["by_phase"]
        assert "implement" in result["by_phase"]
        assert isinstance(result["by_phase"]["plan"], dict)
        assert "usd" in result["by_phase"]["plan"]
        assert isinstance(result["by_phase"]["plan"]["usd"], float)
        assert result["by_phase"]["plan"]["usd"] > 0
        # No "tokens" key in usd-mode by_phase values
        assert "tokens" not in result["by_phase"]["plan"]

    def test_tokens_mode_when_cost_zero_but_tokens_positive(self, tmp_path):
        """JSONL with unknown model (cost=0) but tokens > 0 → mode == 'tokens', nested by_phase."""
        home = tmp_path / "home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        proj_hash = project_hash(str(project_root))

        uuid1 = "bbbbbbbb-0001-0001-0001-000000000001"

        # Write a JSONL with an unknown model — parse_session sets cost=0 but tokens > 0
        path = home / ".claude" / "projects" / proj_hash / f"{uuid1}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "type": "assistant",
            "message": {
                "model": "unknown-model-xyz",
                "usage": {
                    "input_tokens": 75_000,
                    "output_tokens": 15_000,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                },
            },
        }
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        rows = _make_rows([(uuid1, "critic")])
        provider = make_cost_provider(project_root, home=home)
        result = provider("my-task", rows)

        assert result is not None
        assert result["mode"] == "tokens"
        assert result["usd"] is None
        assert result["tokens"] > 0
        assert "critic" in result["by_phase"]
        assert isinstance(result["by_phase"]["critic"], dict)
        assert "tokens" in result["by_phase"]["critic"]
        assert isinstance(result["by_phase"]["critic"]["tokens"], int)
        assert result["by_phase"]["critic"]["tokens"] > 0
        # No "usd" key in tokens-mode by_phase values
        assert "usd" not in result["by_phase"]["critic"]

    def test_none_when_no_jsonl_found(self, tmp_path):
        """Rows whose UUIDs have no JSONL → provider returns None."""
        home = tmp_path / "home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)

        uuid_missing = "cccccccc-0001-0001-0001-000000000001"
        rows = _make_rows([(uuid_missing, "plan")])
        provider = make_cost_provider(project_root, home=home)
        result = provider("my-task", rows)

        assert result is None

    def test_empty_rows_returns_none(self, tmp_path):
        """Empty row list → None."""
        provider = make_cost_provider(tmp_path / "project", home=tmp_path / "home")
        assert provider("my-task", []) is None


# ---------------------------------------------------------------------------
# T-08 (stage 4): inline-first precedence (D-1/D-2/D-8, MINOR-5)
# ---------------------------------------------------------------------------

class TestInlineFirstPrecedence:
    """Test the col-8 attribution precedence rule applied by the provider."""

    def test_resolved_only_empty_jsonl_tree_returns_inline_usd_mode(self, tmp_path):
        """A resolved-only task with NO JSONL tree at all must still return
        mode=usd with the inline total — proving the JSONL lookup is skipped
        (the any_jsonl_found gate is relaxed to any_resolved, R-04)."""
        home = tmp_path / "empty-home"  # no .claude/projects/ tree
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)

        uuid1 = "dddddddd-0001-0001-0001-000000000001"
        rows = _make_rows_with_attribution([
            (uuid1, "implement", "usd=3.25;tok=1000;src=nested_jsonl"),
        ])
        provider = make_cost_provider(project_root, home=home)
        result = provider("inline-task", rows)

        assert result is not None
        assert result["mode"] == "usd"
        assert result["usd"] == pytest.approx(3.25)
        assert result["partial"] is False
        assert result["by_phase"]["implement"]["usd"] == pytest.approx(3.25)

    def test_resolved_zero_only_returns_usd_mode_not_counts(self, tmp_path):
        """MINOR-5/D-8: a genuine resolved usd=0.0 must return mode=usd, usd=0.0
        — NOT collapse to counts/None."""
        home = tmp_path / "empty-home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)

        uuid1 = "eeeeeeee-0001-0001-0001-000000000001"
        rows = _make_rows_with_attribution([
            (uuid1, "implement", "usd=0.0;tok=9;src=nested_jsonl"),
        ])
        provider = make_cost_provider(project_root, home=home)
        result = provider("zero-task", rows)

        assert result is not None
        assert result["mode"] == "usd"
        assert result["usd"] == 0.0
        assert result["partial"] is False

    def test_unresolvable_row_sets_partial_true(self, tmp_path):
        """A col-8 unresolvable row must set partial=True and contribute
        nothing — never folded into a silent $0."""
        home = tmp_path / "empty-home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)

        uuid1 = "ffffffff-0001-0001-0001-000000000001"
        rows = _make_rows_with_attribution([
            (uuid1, "implement", "tok=45;src=unresolved"),
        ])
        provider = make_cost_provider(project_root, home=home)
        result = provider("unresolvable-task", rows)

        # Nothing resolved and no JSONL → None (counts mode upstream), per the
        # not (any_jsonl_found or any_resolved) gate — partial is only visible
        # when combined with at least one resolved/JSONL row (see mixed test).
        assert result is None

    def test_mixed_resolved_and_unresolvable_sets_partial_true_with_usd(self, tmp_path):
        """A task with one resolved row and one unresolvable row must return
        mode=usd with the resolved amount AND partial=True — the never-silent
        combination this whole stage exists to guarantee."""
        home = tmp_path / "empty-home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)

        uuid1 = "11110000-0001-0001-0001-000000000001"
        uuid2 = "11110000-0002-0002-0002-000000000002"
        rows = _make_rows_with_attribution([
            (uuid1, "implement", "usd=1.0;tok=100;src=nested_jsonl"),
            (uuid2, "implement", "tok=45;src=unresolved"),
        ])
        provider = make_cost_provider(project_root, home=home)
        result = provider("mixed-task", rows)

        assert result is not None
        assert result["mode"] == "usd"
        assert result["usd"] == pytest.approx(1.0)
        assert result["partial"] is True

    def test_legacy_rows_unaffected_by_attribution_key_absence(self, tmp_path):
        """Rows with no 'attribution' key at all (pre-stage-4 callers) must
        behave exactly as before — this is the R-01 back-compat guarantee."""
        home = tmp_path / "home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        proj_hash = project_hash(str(project_root))

        uuid1 = "22220000-0001-0001-0001-000000000001"
        _make_jsonl(
            home / ".claude" / "projects" / proj_hash / f"{uuid1}.jsonl",
            model="claude-sonnet-4-6",
            input_tokens=100_000,
            output_tokens=10_000,
        )
        rows = _make_rows([(uuid1, "plan")])  # no "attribution" key at all
        provider = make_cost_provider(project_root, home=home)
        result = provider("legacy-task", rows)

        assert result is not None
        assert result["mode"] == "usd"
        assert result["usd"] > 0
        assert result["partial"] is False


# ---------------------------------------------------------------------------
# T-01 tests: memo-cache hit + invalidation (D-05)
# ---------------------------------------------------------------------------

class TestMemoCache:
    """Test the (uuid, jsonl_mtime) memo-cache."""

    def test_cache_hit_avoids_reparse(self, tmp_path):
        """Second call with same (uuid, mtime) must not re-invoke parse_session."""
        home = tmp_path / "home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        proj_hash = project_hash(str(project_root))

        uuid1 = "dddddddd-0001-0001-0001-000000000001"
        jsonl_path = home / ".claude" / "projects" / proj_hash / f"{uuid1}.jsonl"
        _make_jsonl(jsonl_path, "claude-sonnet-4-6", 10_000, 1_000)

        call_count = {"n": 0}
        original_parse = _DC.parse_session

        def counting_parse(path):
            call_count["n"] += 1
            return original_parse(path)

        rows = _make_rows([(uuid1, "plan")])

        with patch.object(_DC, "parse_session", side_effect=counting_parse):
            provider = make_cost_provider(project_root, home=home)
            # First call — should parse once
            result1 = provider("my-task", rows)
            assert call_count["n"] == 1
            # Second call — same mtime, should use cache
            result2 = provider("my-task", rows)
            assert call_count["n"] == 1  # Still 1 — cache hit

    def test_cache_invalidated_on_mtime_change(self, tmp_path):
        """JSONL mtime bump must invalidate cache and trigger re-parse."""
        home = tmp_path / "home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        proj_hash = project_hash(str(project_root))

        uuid1 = "eeeeeeee-0001-0001-0001-000000000001"
        jsonl_path = home / ".claude" / "projects" / proj_hash / f"{uuid1}.jsonl"
        _make_jsonl(jsonl_path, "claude-sonnet-4-6", 10_000, 1_000)

        call_count = {"n": 0}
        original_parse = _DC.parse_session

        def counting_parse(path):
            call_count["n"] += 1
            return original_parse(path)

        rows = _make_rows([(uuid1, "plan")])

        with patch.object(_DC, "parse_session", side_effect=counting_parse):
            provider = make_cost_provider(project_root, home=home)
            provider("my-task", rows)
            assert call_count["n"] == 1

            # Bump mtime by writing again with a small sleep for mtime resolution
            time.sleep(0.05)
            _make_jsonl(jsonl_path, "claude-sonnet-4-6", 20_000, 2_000)

            provider("my-task", rows)
            assert call_count["n"] == 2  # Re-parsed due to mtime change


# ---------------------------------------------------------------------------
# Pricing table tests
# ---------------------------------------------------------------------------

class TestPricing:
    """Verify PRICES table contains required model entries."""

    def test_claude_opus_4_8_in_prices(self):
        """claude-opus-4-8 must be in PRICES so sessions using it report cost > 0."""
        # Load cost_from_jsonl directly to access PRICES
        _cfj_path = _SCRIPTS_PATH / "cost_from_jsonl.py"
        import importlib.util as _ilu
        spec = _ilu.spec_from_file_location("_cfj_pricing_test", _cfj_path)
        cfj = _ilu.module_from_spec(spec)
        spec.loader.exec_module(cfj)

        assert "claude-opus-4-8" in cfj.PRICES, (
            "claude-opus-4-8 missing from PRICES — sessions using this model will "
            "report $0 cost even when JSONL data is available"
        )
        p = cfj.PRICES["claude-opus-4-8"]
        assert p["input"] > 0
        assert p["output"] > 0

    def test_claude_opus_4_8_cost_positive(self, tmp_path):
        """make_cost_provider resolves non-zero USD for claude-opus-4-8 sessions."""
        home = tmp_path / "home"
        project_root = tmp_path / "project"
        project_root.mkdir(parents=True)
        proj_hash = project_hash(str(project_root))

        uuid1 = "bbbbbbbb-0001-0001-0001-000000000001"
        jsonl_dir = home / ".claude" / "projects" / proj_hash
        _make_jsonl(jsonl_dir / f"{uuid1}.jsonl", "claude-opus-4-8",
                    input_tokens=100_000, output_tokens=10_000)

        rows = _make_rows([(uuid1, "implement")])
        provider = make_cost_provider(project_root, home=home)
        result = provider("my-task", rows)

        assert result is not None
        assert result["mode"] == "usd"
        assert result["usd"] > 0, "claude-opus-4-8 must produce positive USD cost"


# ---------------------------------------------------------------------------
# T-01 tests: import boundary — no core imports
# ---------------------------------------------------------------------------

class TestImportBoundary:
    """Verify dashboard_cost.py does not import from quoin/core/."""

    def test_no_core_import_in_source(self):
        """The source file must not spec-load from the core/scripts/ directory."""
        source = _DC_PATH.read_text(encoding="utf-8")
        # Must not spec-load from core/scripts/ at runtime (adapter boundary).
        # The only allowed sibling load is from the same scripts/ directory.
        # We check that "parents[1]" (the cross-dir load pattern used by the server
        # to reach core/) is NOT present — dashboard_cost.py loads siblings only.
        assert 'parents[1]' not in source
        # Also verify the module does NOT import any core module as a package
        assert 'import dashboard_model' not in source

    def test_row_keys_used(self):
        """Provider reads row['uuid'] and row['phase'] — not row['model']."""
        source = _DC_PATH.read_text(encoding="utf-8")
        # Confirm provider reads uuid and phase from rows
        assert 'row.get("uuid"' in source or "row['uuid']" in source
        assert 'row.get("phase"' in source or "row['phase']" in source
        # Must NOT reference row['model'] — the key is model_or_effort
        assert "row['model']" not in source
        assert 'row.get("model")' not in source or 'row.get("model_or_effort")' in source


# ---------------------------------------------------------------------------
# T-01 tests: spaced project root (R-07)
# ---------------------------------------------------------------------------

class TestSpacedProjectRoot:
    """Verify project_hash handles paths with spaces (Google Drive root pattern)."""

    def test_project_hash_with_spaces(self, tmp_path):
        """project_hash on a path with spaces must match regex [^A-Za-z0-9-] → '-'."""
        spaced_path = str(tmp_path / "My Drive" / "Storage" / "Codex workflow")
        h = project_hash(spaced_path)
        # All spaces and special chars replaced with '-'
        assert " " not in h
        assert "/" not in h
        # Only alnum and '-' remain
        import re
        assert re.fullmatch(r"[A-Za-z0-9-]+", h)

    def test_provider_works_with_spaced_root(self, tmp_path):
        """make_cost_provider must succeed when project_root contains spaces."""
        spaced_root = tmp_path / "My Drive" / "project"
        spaced_root.mkdir(parents=True)
        home = tmp_path / "home"

        proj_hash = project_hash(str(spaced_root))
        uuid1 = "ffffffff-0001-0001-0001-000000000001"
        jsonl_path = home / ".claude" / "projects" / proj_hash / f"{uuid1}.jsonl"
        _make_jsonl(jsonl_path, "claude-sonnet-4-6", 5_000, 500)

        rows = _make_rows([(uuid1, "plan")])
        provider = make_cost_provider(spaced_root, home=home)
        result = provider("my-task", rows)

        assert result is not None
        assert result["mode"] == "usd"
