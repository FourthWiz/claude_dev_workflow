"""T-20 — pytest CI wrapper for install.sh hooks-deploy idempotency.

Shells out to quoin/dev/spikes/idempotency_spike.sh and asserts a PASS result.

Run:
  python3 -m pytest quoin/dev/tests/test_install_idempotency.py -v

Skip conditions:
  - jq not on PATH (spike script requires it; test marks xfail with reason)
  - spike script not found (unexpected — always fail if the source file is missing)

The test is deliberately thin: all scenario logic lives in the spike script itself,
which was manually verified (T-02). This wrapper's job is to catch future regressions
when the spike is re-run as part of the CI suite.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SPIKE_SCRIPT = REPO_ROOT / "quoin" / "dev" / "spikes" / "idempotency_spike.sh"


def _jq_available() -> bool:
    return shutil.which("jq") is not None


class TestInstallIdempotency:
    """Idempotency regression gate for install.sh hooks-deploy logic."""

    def test_spike_script_exists(self):
        """The spike driver must be checked in (prerequisite for all other assertions)."""
        assert SPIKE_SCRIPT.exists(), (
            f"idempotency_spike.sh not found at {SPIKE_SCRIPT}. "
            "This file must be present in the repo — T-02 checked it in."
        )

    @pytest.mark.skipif(not _jq_available(), reason="jq not on PATH — idempotency spike requires jq")
    def test_idempotency_spike_passes(self, tmp_path):
        """Run the idempotency spike and assert it exits 0 with no FAIL lines."""
        result = subprocess.run(
            ["sh", str(SPIKE_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        stdout = result.stdout
        stderr = result.stderr

        # Exit 0 means the spike driver reported no failures.
        assert result.returncode == 0, (
            f"idempotency_spike.sh exited {result.returncode}\n"
            f"--- stdout ---\n{stdout}\n"
            f"--- stderr ---\n{stderr}"
        )

        # Extra guard: look for explicit FAIL lines in output.
        fail_lines = [line for line in stdout.splitlines() if "FAIL" in line]
        assert not fail_lines, (
            f"idempotency_spike.sh printed FAIL lines despite exit 0:\n"
            + "\n".join(fail_lines)
        )

        # Confirm at least one PASS line present (smoke — output not totally empty).
        pass_lines = [line for line in stdout.splitlines() if "PASS" in line]
        assert pass_lines, (
            "idempotency_spike.sh produced no PASS output — something went wrong "
            "silently.\n--- stdout ---\n" + stdout
        )

    @pytest.mark.skipif(not _jq_available(), reason="jq not on PATH — idempotency spike requires jq")
    def test_all_scenarios_covered(self):
        """The spike output must mention all four scenario labels."""
        result = subprocess.run(
            ["sh", str(SPIKE_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        stdout = result.stdout
        for scenario in ["A-clean-settings", "B-user-defined-hook", "C-stale-quoin-entry", "D-no-hooks-block"]:
            assert scenario in stdout, (
                f"Scenario '{scenario}' not found in spike output — "
                "spike script may be out of sync with the expected scenario list."
            )
