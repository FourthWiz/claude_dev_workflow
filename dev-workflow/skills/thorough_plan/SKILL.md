---
name: thorough_plan
description: "Orchestrates the full plan→critic→revise cycle for thorough implementation planning using the strongest model (Opus). Use this skill for: /thorough_plan, 'plan this thoroughly', 'detailed plan with review', 'plan and critique', 'full planning cycle'. Runs /plan to create the initial plan, then /critic in a fresh session for unbiased review, then /revise to address issues — repeating up to 4 rounds until convergence (override with max_rounds: N). Use this when you want the highest-quality plan, not just a quick one."
model: opus
---

# Thorough Plan — Orchestrator

This skill orchestrates the planning convergence loop by invoking three sub-skills in sequence: `/plan`, `/critic`, and `/revise`. It does not do the planning, critiquing, or revising itself — it coordinates the agents that do.

## Setup

### 1. Determine the task subfolder

Before starting the loop, establish the working directory:

- Ask the user for a descriptive name if not obvious
- Use kebab-case: `auth-refactor`, `payment-migration`, `api-v2-endpoints`
- Create the folder: `<project-folder>/<task-name>/`

### 2. Gather initial context

Collect and pass to `/plan`:

- The user's description of what needs to be built
- Path to `architecture.md` if `/architect` was run first
- Paths to all relevant repositories in the project folder
- Any constraints, preferences, or context the user mentioned

### 3. Parse runtime overrides

Before starting the loop, scan the user's task description for runtime overrides:

- **`max_rounds: N`** (case-insensitive, N = positive integer): If found, use N as the maximum round cap for this run. Strip the `max_rounds: N` token from the description before passing it to `/plan`. If not found, use the default cap of 4. If the value is not a positive integer (e.g., zero, negative, or non-numeric), ignore the override and use the default.

Example: `/thorough_plan max_rounds: 6 this migration is gnarly, give it room` sets the cap to 6 and passes "this migration is gnarly, give it room" to `/plan`.

## The loop

```
Round 1:
  /plan    → produces current-plan.md
  /critic  → (FRESH SESSION) reads plan + code → produces critic-response-1.md

  If verdict = PASS → done
  If verdict = REVISE → continue

Round 2:
  /revise  → reads critic-response-1.md → updates current-plan.md
  /critic  → (FRESH SESSION) reads updated plan + code → produces critic-response-2.md

  If verdict = PASS → done
  If verdict = REVISE → continue

...repeat up to Round 4 (or max_rounds if overridden)
```

### Invoking each agent

**`/plan` (Round 1 only)**
- Invoke with the strongest model (Opus)
- Pass all context: architecture docs, user requirements, repo paths
- Output: `<task-folder>/current-plan.md`

**`/critic` (every round)**
- **MUST spawn as a new agent session** — fresh context is essential for unbiased critique
- Pass: path to `current-plan.md`, path to the project folder (so it can read actual code)
- Output: `<task-folder>/critic-response-<round>.md`

**`/revise` (rounds 2+)**
- **MUST spawn as a new agent session** (same mechanism used for /critic above) — fresh context prevents anchoring on prior orchestrator chatter. The plan document (`current-plan.md`) encodes the plan's intent; a fresh reviser reading it + critic feedback is strictly better than one carrying stale context.
- Pass: path to `current-plan.md`, path to latest `critic-response-<N>.md`, and paths to any files the critic flagged as needing re-examination
- Output: updated `current-plan.md` (in place)

### Convergence rules

The loop stops when ANY of these is true:

1. **Critic gives PASS** — no CRITICAL or MAJOR issues. Plan is ready.
2. **Max rounds reached (default: 4)** — inform the user of remaining issues. The plan may have inherent constraints.
3. **Stuck in a loop** — if round N's critic flags the same top-level issue category as round N-1 (same CRITICAL or MAJOR issue title reappearing despite revision), escalate to the user with the specific repeated issues and ask whether to continue or accept the plan as-is. This usually means a requirement is ambiguous or there's a genuine tradeoff to decide.

### Between rounds

After each critic round, before continuing:

- Read the critic response yourself (as orchestrator)
- Check if the same issues keep appearing (loop detection: compare round N's CRITICAL/MAJOR issue titles against round N-1's — if any title reappears, flag it)
- Briefly inform the user: "Round N complete — critic found X critical, Y major issues. Proceeding to revise." or "Round N complete — critic passed. Plan is ready."

## Final output

When converged, add a convergence summary to the top of `current-plan.md`:

```markdown
## Convergence Summary
- **Rounds:** <N>
- **Final verdict:** PASS
- **Key revisions:** <what the main themes of revision were across rounds>
- **Remaining concerns:** <any MINOR issues not addressed, or none>
```

Then run `/gate` to present automated checks and a summary to the user.

After the gate, inform the user:
- The plan is ready at `<task-folder>/current-plan.md`
- Summary of what was planned (high-level, 3-5 bullet points)
- How many rounds it took and what the main themes were
- Any remaining concerns or decisions the user needs to make

**STOP HERE.** Do NOT invoke `/implement`. Do NOT offer to start implementing. The user must explicitly type `/implement` to proceed. This is a hard rule — implementation requires a conscious human decision.

## File structure at completion

```
<project-folder>/<task-name>/
├── architecture.md          (from /architect, if exists)
├── current-plan.md          (final converged plan)
├── critic-response-1.md     (round 1 critic)
├── critic-response-2.md     (round 2 critic, if needed)
├── ...
└── critic-response-N.md     (final round critic)
```

## Important behaviors

- **You are the orchestrator, not the planner.** Don't produce plan content yourself — invoke `/plan`, `/critic`, `/revise`.
- **Critic MUST be a fresh session.** This is non-negotiable. Same-agent critique is biased and weak.
- **Keep the user informed.** Brief status updates between rounds. Don't go silent for 10 minutes.
- **Detect loops early.** After each critic round, compare CRITICAL/MAJOR issue titles against the previous round. If any title reappears, stop and present the repeated issues to the user — ask whether to continue revising or accept the plan as-is.
- **Pass context explicitly.** Each agent starts with limited knowledge. Give them the file paths and repo locations they need.
