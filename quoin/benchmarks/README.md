# Cross-Runtime Benchmarks

Phase 29 defines a small benchmark framework for comparing Quoin-assisted
workflows with simple Claude and Codex workflows. The suite evaluates workflow
usefulness: quality of decisions, correctness, reusable artifacts, continuity,
and overhead.

This directory contains benchmark design only. It does not contain measured results,
rankings, or claims that Quoin improves outcomes. A result exists only after a
human or automated run fills out `templates/result-template.md` with run
evidence.

## Comparison Modes

Run each scenario in the same fixture repository under four modes:

- `simple-claude` - Claude Code used normally, without Quoin phases or Quoin
  workflow artifacts.
- `quoin-claude` - Claude Code with the supported Claude adapter and Quoin
  artifacts under `.workflow_artifacts/`.
- `simple-codex` - Codex used normally with native planning, approvals,
  sandboxing, and repo-scoped instructions, without Quoin artifacts.
- `quoin-codex` - Codex with repo-local Quoin guidance and portable artifacts,
  without Codex global install assumptions or generated command files.

Simple modes may still keep ordinary notes or final answers, but they should
not be prompted to create Quoin-specific artifacts. Quoin modes should use the
same portable artifact contract documented in `quoin/core/workflow/`.

## Scenario Suite

The suite is intentionally small:

- Fresh repo discovery: orientation and useful first-pass repository map.
- Planning a medium refactor: risk discovery, staging, and validation strategy.
- Implementing a scoped code change: bounded implementation plus relevant checks.
- Reviewing changes: concrete findings, test gaps, and plan mismatch detection.
- Session handoff / memory reuse: continuation quality after prior-session context.

The machine-readable source of truth is `benchmark-suite.json`. Human scenario
instructions live under `scenarios/`.

## Metrics

The required scoring dimensions are:

- Task completion quality.
- Correctness / tests.
- Artifact quality.
- Context reuse.
- Time / turn count.
- Setup overhead.

Cost is optional because runtime cost capture is not equally implemented across
Claude and Codex. When cost is unavailable, record `not available` instead of
estimating it.

## Running A Benchmark

1. Choose a fixture repository and reset it to the same starting revision for
   every mode.
2. Select one scenario from `benchmark-suite.json`.
3. Copy `templates/run-sheet.md` into the run evidence folder and fill in the
   runtime, model or effort setting, start time, and setup steps.
4. Execute the scenario prompt exactly once per mode unless the run sheet
   records a restart.
5. Record raw evidence: final response, transcript or turn count, changed files,
   tests/checks, relevant Quoin artifacts for Quoin modes, and cost if the
   runtime exposes it.
6. Fill out `templates/result-template.md` after the run. Keep observations and
   scores separate from the design files in this directory.
7. Compare modes only after all four mode results for the same scenario and
   fixture are complete.

## Validation

Run the deterministic structure check from the repository root:

```bash
python3 quoin/benchmarks/scripts/validate_benchmarks.py --project-root .
```

This check validates the manifest, scenario files, templates, comparison modes,
and metric coverage. It does not execute benchmark tasks or infer results.

## Quantitative Benchmark Harness (v1)

The `harness/` directory and `scripts/run_benchmark.py` implement an automated,
quantitative benchmark for measuring quoin's effect on coding-agent pass-rate-per-dollar
against external benchmarks (EvalPlus HumanEval+ and SWE-bench Lite).

See `methodology.md` for the full benchmark design.

### Running a v1 Benchmark

**Prerequisites:**
- Claude Code CLI installed and authenticated (`claude --version`)
- Codex CLI installed if running Codex cells (`codex --version`)
- evalplus and swebench installed (`pip install evalplus swebench`)
- Docker available for judge evaluation (SWE-bench Lite)
- statsmodels installed for CI computation (`pip install statsmodels`)

**Step 1: Dry-run to estimate costs (required before any real run)**

```bash
python3 quoin/benchmarks/scripts/run_benchmark.py \
    --suite quoin/benchmarks/suite-v1.json \
    --cells simple-claude,quoin-claude \
    --run-id v1 \
    --dry-run
```

The dry-run prints the planned task × cell matrix and cost estimates without
invoking any agent.

**Step 2: Smoke run (3 tasks, simple-claude only)**

```bash
python3 quoin/benchmarks/scripts/run_benchmark.py \
    --suite quoin/benchmarks/suite-v1.json \
    --cells simple-claude \
    --run-id v0-smoke \
    --max-parallel 1
```

Requires explicit user budget approval (T-14) before proceeding to larger runs.

**Step 3: Calibration run (T-15)**

After budget approval from T-14:
```bash
python3 quoin/benchmarks/scripts/run_benchmark.py \
    --suite quoin/benchmarks/suite-v1.json \
    --cells simple-claude,quoin-claude \
    --run-id v05-calibration \
    --max-parallel 2
```

**Step 4: Full v1 run (T-17, requires T-16 budget gate approval)**

```bash
python3 quoin/benchmarks/scripts/run_benchmark.py \
    --suite quoin/benchmarks/suite-v1.json \
    --cells simple-claude,quoin-claude,simple-codex,quoin-codex \
    --run-id v1 \
    --max-parallel 4 \
    --resume
```

Use `--resume` to continue an interrupted run without re-running completed tasks.

**Step 5: Check invariants and view results**

```bash
python3 quoin/benchmarks/scripts/check_invariants.py --run-id v1
cat .workflow_artifacts/quoin-benchmarks/runs/v1/summary.md
```

### Output Files

Each completed run produces:
```
.workflow_artifacts/quoin-benchmarks/runs/<run-id>/
    run-manifest.yaml              — pinned config + git SHA
    summary.json                   — machine-readable aggregated metrics
    summary.md                     — human-readable Markdown report
    invariants-report.md           — fair-comparison invariant check results
    <cell>/<task-id>/
        prompt.txt                 — prompt sent to agent
        transcript.jsonl           — full agent session transcript
        diff.patch                 — git diff of worktree after agent run
        judge.json                 — verdict (pass/fail/error/timeout)
        metrics.json               — timing and token metrics
        cost.json                  — cost data (or not_available for Codex)
```

### Benchmark Auto-Approve (QUOIN_GATE_AUTO_APPROVE)

For unattended benchmark runs, the `quoin-claude` cell sets both:
- `QUOIN_GATE_AUTO_APPROVE=1`
- `QUOIN_BENCHMARK_RUN=<run-id>`

When BOTH are set, `/gate` auto-approves without human input and records
`auto_approved: true` in the gate audit log. This requires the gate plumbing
implemented in T-19. See `methodology.md` for the auto-mode caveats.
