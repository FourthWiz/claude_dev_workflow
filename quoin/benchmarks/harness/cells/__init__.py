"""Cell adapters for the quoin benchmark harness.

Each adapter in this package implements:
    invoke(task_spec, workdir, budget, run_id) -> dict

Return dict fields:
    transcript_events: list[dict]  — JSONL events from the agent
    prompt: str                    — the prompt sent to the agent
    diff_patch: str                — git diff of the worktree after agent run
    cost_available: bool
    cost_runtime_usd: float | None
    cost_estimated_usd: float | None
    cost_delta_usd: float | None
    tokens_in: int | None
    tokens_out: int | None
    tokens_cache_read: int | None
    tokens_cache_write: int | None
    turn_count: int
    gate_intervention_count: int   — quoin cells only
    verdict: str | None            — 'timeout' if wall-clock exceeded
"""
