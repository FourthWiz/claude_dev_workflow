"""
Regression test: cost_from_jsonl.py parity with ccusage.

Two modes depending on ccusage availability:

Mode A (ccusage available + fixture injection works):
  Copy cost_parity_sample.jsonl into a temp project hash dir under
  ~/.claude/projects/test-stage-5-parity/, run ccusage against it,
  compare to cost_from_jsonl.parse_session(). Assert <0.01% difference.

Mode B (ccusage unavailable OR fixture injection rejected by ccusage):
  Fall back to static price-table cross-check: compute cost via
  cost_from_jsonl.py directly, assert the computed value matches the
  expected value derived independently from the same PRICES table.
  This is weaker (no live ccusage comparison) but still catches price-
  table drift in cost_from_jsonl.py itself.

Run from project root:
    python3 quoin/scripts/tests/test_cost_parity_with_ccusage.py

Exit 0 on pass, 1 on failure.
Skips (stderr message, exit 0) when ccusage unavailable and fixture
injection cannot be verified.
"""

import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    PROJECT_ROOT
    / "quoin"
    / "dev"
    / "tests"
    / "fixtures"
    / "cost_parity_sample.jsonl"
)
SCRIPTS_DIR = PROJECT_ROOT / "quoin" / "scripts"

# Expected cost from PRICES table in cost_from_jsonl.py (verified 2026-04-30):
#   Opus  1000 input + 200 output @  5.00/1M input, 25.00/1M output = 0.010000
#   Sonnet  500 input + 100 output @ 3.00/1M input, 15.00/1M output = 0.003000
#   Haiku   200 input +  50 output @ 1.00/1M input,  5.00/1M output = 0.000450
EXPECTED_TOTAL_COST = 0.013450  # USD


def _import_parse_session():
    """Import cost_from_jsonl.parse_session from the scripts directory."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "cost_from_jsonl",
        SCRIPTS_DIR / "cost_from_jsonl.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_session


def _ccusage_available():
    """Return True if npx ccusage can be invoked."""
    try:
        result = subprocess.run(
            ["npx", "ccusage", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _try_ccusage_fixture_injection(fixture_path):
    """
    Copy fixture JSONL into a temp project hash dir and run ccusage against it.
    Returns (ccusage_cost, ok_bool). ok_bool=False means fixture injection rejected.
    """
    test_uuid = "test-parity-00000000-0000-0000-0000-000000000099"
    parity_dir = pathlib.Path.home() / ".claude" / "projects" / "test-stage-5-parity"
    parity_dir.mkdir(parents=True, exist_ok=True)

    dest = parity_dir / f"{test_uuid}.jsonl"
    dest.write_text(fixture_path.read_text(encoding="utf-8"), encoding="utf-8")

    try:
        result = subprocess.run(
            ["npx", "ccusage", "session", "-i", test_uuid, "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return 0.0, False
        data = json.loads(result.stdout)
        ccusage_total = data.get("totalCost", 0.0)
        entries = data.get("entries", [])
        if not entries or ccusage_total == 0.0:
            # ccusage returned no entries — fixture injection rejected (R-13)
            return 0.0, False
        return ccusage_total, True
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        return 0.0, False
    finally:
        # Clean up temp fixture
        try:
            dest.unlink()
        except OSError:
            pass


def check_static_price_table():
    """
    Mode B: compare cost_from_jsonl.parse_session() output to the independently
    derived EXPECTED_TOTAL_COST. Catches price-table drift in cost_from_jsonl.py.
    Returns (ok, message).
    """
    parse_session = _import_parse_session()
    result = parse_session(FIXTURE_PATH)
    local_cost = result.get("totalCost", 0.0)

    tolerance = 0.0001  # 0.01%
    diff = abs(local_cost - EXPECTED_TOTAL_COST)
    denom = max(EXPECTED_TOTAL_COST, 1e-9)

    if diff / denom > tolerance:
        return False, (
            f"FAIL: cost_from_jsonl computed {local_cost:.6f}, "
            f"expected {EXPECTED_TOTAL_COST:.6f} "
            f"(diff {diff:.6f}, tolerance {tolerance*100:.2f}%). "
            f"Price-table drift in cost_from_jsonl.py?"
        )
    return True, (
        f"PASS (static mode): cost_from_jsonl={local_cost:.6f}, "
        f"expected={EXPECTED_TOTAL_COST:.6f}, diff={diff:.6f}"
    )


def check_ccusage_parity():
    """
    Mode A: live ccusage comparison.
    Returns (ok, mode, message).
    mode is 'live', 'static', or 'skip'.
    """
    if not FIXTURE_PATH.exists():
        return False, "skip", f"FAIL: fixture not found at {FIXTURE_PATH}"

    parse_session = _import_parse_session()
    local_result = parse_session(FIXTURE_PATH)
    local_cost = local_result.get("totalCost", 0.0)

    if not _ccusage_available():
        print(
            "[test_cost_parity: ccusage unavailable — skipping live comparison; "
            "install ccusage with 'npm install -g ccusage' or run via 'npx ccusage']",
            file=sys.stderr,
        )
        # Fall through to static check
        ok, msg = check_static_price_table()
        return ok, "static", msg

    ccusage_cost, injected = _try_ccusage_fixture_injection(FIXTURE_PATH)

    if not injected:
        # R-13: fixture injection rejected — fall back to static check
        print(
            "[test_cost_parity: ccusage fixture injection unavailable (R-13) — "
            "falling back to static price-table comparison]",
            file=sys.stderr,
        )
        ok, msg = check_static_price_table()
        return ok, "static", msg

    # Mode A: live comparison
    tolerance = 0.0001
    diff = abs(local_cost - ccusage_cost)
    denom = max(ccusage_cost, 1e-9)

    if diff / denom > tolerance:
        return False, "live", (
            f"FAIL: cost_from_jsonl={local_cost:.6f}, ccusage={ccusage_cost:.6f}, "
            f"diff={diff:.6f}, tolerance={tolerance*100:.2f}%"
        )
    return True, "live", (
        f"PASS (live mode): cost_from_jsonl={local_cost:.6f}, "
        f"ccusage={ccusage_cost:.6f}, diff={diff:.6f}"
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Parity test: cost_from_jsonl.py vs ccusage (or static price table). "
            "Verifies <0.01% cost difference for the cost_parity_sample.jsonl fixture. "
            "Skips (with warning) if ccusage is unavailable; "
            "falls back to static table check if fixture injection fails."
        )
    )
    parser.parse_args()

    ok, mode, msg = check_ccusage_parity()
    if ok:
        print(msg)
        return 0
    else:
        print(msg, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
