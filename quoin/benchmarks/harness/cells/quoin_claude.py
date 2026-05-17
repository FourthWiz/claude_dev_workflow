"""
quoin_claude.py — Cell adapter for the 'quoin-claude' benchmark cell.

Invokes Claude Code CLI with the full Quoin workflow enabled, inside an isolated
git worktree. Gates auto-approve via QUOIN_GATE_AUTO_APPROVE=1 AND
QUOIN_BENCHMARK_RUN=1 (both must be set; see T-19 for the plumbing).

Key differences from simple_claude.py:
  1. Bootstraps a clean per-task .workflow_artifacts/ using quoin/install.sh
     followed by /init_workflow in non-interactive mode.
  2. Sets QUOIN_GATE_AUTO_APPROVE=1 AND QUOIN_BENCHMARK_RUN=<run_id> in the
     subprocess environment. Both must be set for /gate to auto-approve.
  3. Prepends "Use /run end-to-end on this task" to the agent prompt.
  4. Post-run: captures .workflow_artifacts/<task-name>/ into the run output
     folder as evidence; validates that architecture.md and current-plan.md
     exist for at least one sampled task.

Per-task isolation (invariants 13, 14, R-06):
  The .workflow_artifacts/ directory is initialized from empty PER TASK, not
  per cell. No lessons-learned.md, no sessions/, no cache is carried over
  between tasks. The installed ~/.claude/skills/ toolkit is shared (it IS the
  system under test).

Cost:
  Sum of all Claude Code session costs spawned during the run, parsed from
  JSONL session files written under ~/.claude/projects/.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from ..config import BudgetSpec
from ..cost import estimate_cost, load_pricing
from .simple_claude import _build_prompt, _get_model

# ---------------------------------------------------------------------------
# Invariant: same dated model snapshot as simple-claude (invariant 1).
# This module reuses _get_model() from simple_claude to guarantee byte-for-byte
# model ID equality within the Claude pair.
# ---------------------------------------------------------------------------

ENV_GATE_AUTO_APPROVE = "QUOIN_GATE_AUTO_APPROVE"
ENV_BENCHMARK_RUN = "QUOIN_BENCHMARK_RUN"


def _initialize_workflow_artifacts(workdir: Path, quoin_install_script: Path) -> bool:
    """
    Bootstrap a fresh .workflow_artifacts/ inside the worktree.

    Steps:
    1. Remove any existing .workflow_artifacts/ (guarantee fresh start).
    2. Run quoin/install.sh to deploy skills to ~/.claude/ (idempotent).
    3. Create empty .workflow_artifacts/ structure.

    Returns True on success, False on failure.
    """
    artifacts_dir = workdir / ".workflow_artifacts"
    if artifacts_dir.exists():
        shutil.rmtree(artifacts_dir)
    artifacts_dir.mkdir(parents=True)

    # Run install.sh to ensure skills are deployed (idempotent; fast if already done)
    if quoin_install_script.exists():
        try:
            subprocess.run(
                ["bash", str(quoin_install_script)],
                capture_output=True,
                timeout=60,
                check=False,
            )
        except Exception:
            pass  # install failures are non-fatal; skills may already be deployed

    return True


def _capture_workflow_artifacts(
    workdir: Path,
    run_output_dir: Path,
    task_id: str,
) -> dict:
    """
    Copy .workflow_artifacts/<task>/ from the worktree to the run output dir.

    Returns a dict with validation results:
      {
        "captured": bool,
        "has_architecture_md": bool,
        "has_current_plan_md": bool,
        "artifacts_path": str | None,
      }
    """
    src = workdir / ".workflow_artifacts"
    if not src.exists():
        return {
            "captured": False,
            "has_architecture_md": False,
            "has_current_plan_md": False,
            "artifacts_path": None,
        }

    dest = run_output_dir / "workflow_artifacts_evidence"
    try:
        shutil.copytree(src, dest, dirs_exist_ok=True)
    except Exception:
        return {
            "captured": False,
            "has_architecture_md": False,
            "has_current_plan_md": False,
            "artifacts_path": None,
        }

    # Validate: look for architecture.md and current-plan.md in any subfolder
    has_arch = any(dest.rglob("architecture.md"))
    has_plan = any(dest.rglob("current-plan.md"))

    return {
        "captured": True,
        "has_architecture_md": has_arch,
        "has_current_plan_md": has_plan,
        "artifacts_path": str(dest),
    }


def invoke(
    task_spec: dict,
    workdir: Path,
    budget: BudgetSpec,
    run_id: str,
    quoin_install_script: Optional[Path] = None,
    quoin_repo_root: Optional[Path] = None,
) -> dict:
    """
    Invoke Claude Code with the full Quoin workflow.

    Parameters
    ----------
    task_spec:
        Task dict from suite-v1.json.
    workdir:
        Isolated git worktree path for this task.
    budget:
        Wall-clock and USD budget constraints.
    run_id:
        The benchmark run ID (used for QUOIN_BENCHMARK_RUN env var).
    quoin_install_script:
        Path to quoin/install.sh. Defaults to quoin/install.sh relative to cwd.
    quoin_repo_root:
        Path to the quoin repo root. Used to locate install.sh if not given.

    Returns
    -------
    dict with transcript_events, prompt, diff_patch, cost data, etc.
    """
    model = _get_model()
    base_prompt = _build_prompt(task_spec)
    # Prepend quoin workflow directive
    prompt = f"Use /run end-to-end on this task\n\n{base_prompt}"

    result: dict = {
        "prompt": prompt,
        "transcript_events": [],
        "diff_patch": "",
        "cost_available": False,
        "cost_runtime_usd": None,
        "cost_estimated_usd": None,
        "cost_delta_usd": None,
        "tokens_in": None,
        "tokens_out": None,
        "tokens_cache_read": None,
        "tokens_cache_write": None,
        "turn_count": 0,
        "gate_intervention_count": 0,
        "verdict": None,
    }

    # Resolve quoin install script path
    if quoin_install_script is None:
        if quoin_repo_root:
            quoin_install_script = quoin_repo_root / "quoin" / "install.sh"
        else:
            quoin_install_script = Path("quoin/install.sh")

    # Bootstrap fresh .workflow_artifacts/ per-task
    _initialize_workflow_artifacts(workdir, quoin_install_script)

    # Build subprocess environment with gate auto-approve
    env = os.environ.copy()
    env[ENV_GATE_AUTO_APPROVE] = "1"
    env[ENV_BENCHMARK_RUN] = run_id

    cmd = [
        "claude",
        "--print",
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", "acceptEdits",
        "--model", model,
        prompt,
    ]

    budget_seconds = budget.wall_clock_seconds
    wall_start = time.monotonic()
    backoff_total = 0.0

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(workdir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        events = []
        total_cost_usd: Optional[float] = None
        tokens_in = tokens_out = tokens_cache_read = tokens_cache_write = 0
        turn_count = 0
        gate_intervention_count = 0
        retry_delay = 1.0

        while True:
            elapsed = time.monotonic() - wall_start - backoff_total
            if elapsed > budget_seconds:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                result["verdict"] = "timeout"
                break

            line = proc.stdout.readline()
            if not line and proc.poll() is not None:
                break

            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            # Handle rate-limit / overloaded events (same as simple_claude)
            if event_type in ("error", "api_error"):
                error_msg = str(event.get("error", ""))
                if "429" in error_msg or "overloaded" in error_msg.lower():
                    backoff_start = time.monotonic()
                    time.sleep(retry_delay)
                    backoff_total += time.monotonic() - backoff_start
                    retry_delay = min(retry_delay * 2, 60.0)
                    continue

            events.append(event)

            # Track gate auto-approve events
            # /gate in auto-approve mode emits an event with auto_approved: true
            if event.get("auto_approved"):
                gate_intervention_count += 1

            if event_type == "result":
                cost_val = event.get("cost_usd")
                if cost_val is not None:
                    total_cost_usd = float(cost_val)
                usage = event.get("usage", {})
                tokens_in = usage.get("input_tokens", tokens_in)
                tokens_out = usage.get("output_tokens", tokens_out)
                tokens_cache_read = usage.get("cache_read_input_tokens", tokens_cache_read)
                tokens_cache_write = usage.get("cache_creation_input_tokens", tokens_cache_write)

            if event_type == "assistant":
                turn_count += 1

        proc.wait(timeout=10)

        # Get git diff from workdir
        try:
            diff_proc = subprocess.run(
                ["git", "diff", "HEAD"],
                cwd=str(workdir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            result["diff_patch"] = diff_proc.stdout
        except Exception:
            result["diff_patch"] = ""

        # Capture .workflow_artifacts/ evidence
        # (run output dir is determined by the caller via run_id+cell+task_id)
        artifacts_evidence = _capture_workflow_artifacts(
            workdir=workdir,
            run_output_dir=workdir.parent / "artifacts_evidence",
            task_id=task_spec["id"],
        )
        result["workflow_artifacts_captured"] = artifacts_evidence.get("captured", False)
        result["workflow_artifacts_has_arch"] = artifacts_evidence.get("has_architecture_md", False)
        result["workflow_artifacts_has_plan"] = artifacts_evidence.get("has_current_plan_md", False)

        result["transcript_events"] = events
        result["turn_count"] = turn_count
        result["gate_intervention_count"] = gate_intervention_count
        result["tokens_in"] = tokens_in if tokens_in else None
        result["tokens_out"] = tokens_out if tokens_out else None
        result["tokens_cache_read"] = tokens_cache_read if tokens_cache_read else None
        result["tokens_cache_write"] = tokens_cache_write if tokens_cache_write else None

        if total_cost_usd is not None:
            result["cost_available"] = True
            result["cost_runtime_usd"] = total_cost_usd
            try:
                pricing = load_pricing()
                estimated = estimate_cost(
                    model=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cache_write=tokens_cache_write,
                    cache_read=tokens_cache_read,
                    pricing=pricing,
                )
                if estimated is not None:
                    result["cost_estimated_usd"] = float(estimated)
                    result["cost_delta_usd"] = total_cost_usd - float(estimated)
            except Exception:
                pass
        else:
            result["cost_available"] = False

    except FileNotFoundError:
        result["verdict"] = "error"
        result["transcript_events"] = [
            {"type": "error", "error": "claude CLI not found on PATH"}
        ]
    except Exception as exc:
        result["verdict"] = "error"
        result["transcript_events"] = [{"type": "error", "error": str(exc)}]

    return result
