"""
Quoin benchmark harness.

Entry points:
  runner.py   — run_one_task(), run_cell()
  config.py   — BudgetSpec, HarnessConfig
  result_writer.py — write result files to the run output directory
  judge.py    — per-benchmark verdict computation
  aggregate.py — metrics aggregation and Markdown report
  isolation.py — worktree and .workflow_artifacts/ isolation
  cost.py     — cost estimation from pricing.json
  cells/      — per-cell agent adapters
"""
