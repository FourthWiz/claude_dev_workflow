# Implementation Plan: Stage 0 — Baseline Cost Measurement

## Convergence Summary
- **Rounds:** 2
- **Final verdict:** PASS
- **Key revisions:** Round 1 critic identified 2 critical issues (nested session blocker — plan must be manual protocol, not automatable; debug flag syntax errors) and 6 major issues (speculative `--tools ""`, no debug log parsing guidance, unverified cache fields, `-p` vs interactive mode parity, instrumented `/thorough_plan` invocation method, cache-aware cost formula). All were addressed in the R2 revision.
- **Remaining concerns:** 3 minor items — (1) token field arithmetic for `uncached_input = total - cache_read - cache_write` needs empirical verification; (2) `-p` vs interactive parity check heuristic is coarse; (3) capturing `claude --version` at measurement time would aid reproducibility. None block implementation.

**Revision:** R2 (addresses critic round 1 feedback)

## Objective

Produce `cost-reduction/baseline.md` — a per-skill, per-round cost table with a caching-and-spawn-overhead appendix — that replaces every illustrative number in the architecture document (Section 4) with measured data. Stage 0 is the prerequisite gate for all subsequent cost-reduction stages. Without it, Stage 1's caching hygiene has no hit-rate baseline to improve against, Stage 2's loop-discipline changes have no convergence-frequency data, and Stage 3's model-tiering savings estimates are guesswork.

## Scope

**In scope:**
- Measuring token usage (input, output, cache-read, cache-write) for one complete `/thorough_plan` run
- Measuring token usage for one `/architect` invocation
- Determining per-spawn base-prompt overhead (system prompt + CLAUDE.md + SKILL.md + tool registry)
- Determining whether `/plan` and `/revise` currently run inline or as subagents
- Documenting cache-hit ratios and TTL behavior observed
- Answering the architecture's open questions that gate Stages 1-3

**Out of scope:**
- Implementing any cost-reduction changes (that is Stages 1-5)
- Measuring `/review`, `/implement`, or state-management skills (can be done later if needed)
- Answering Open Question #1 (billing plan) — that is a user decision, not a measurement task

## Critical execution model

**This plan is a manual measurement protocol, not an automatable implementation.**

Claude Code blocks nested sessions — running `claude` inside a Claude Code session produces an error. Therefore:

- **Tasks 1-5 are executed by the user in a standalone terminal** (no active Claude Code session). Each task provides copy-paste-ready commands.
- **Tasks 6-7 (analysis and compilation) can be done inside a Claude Code session.** The user brings the raw debug logs and measurement notes back, and Claude analyzes the data.

Do NOT attempt to run these via `/implement`. The implementer (Claude Code) cannot execute `claude` commands. The user runs the measurement commands; Claude compiles the results.

## Pre-implementation checklist

- [ ] Identify a recently-completed feature task suitable for re-running `/thorough_plan` against, OR identify the next organic task to instrument
- [ ] Confirm access to Anthropic Console (console.anthropic.com) for post-run usage analysis
- [ ] Ensure the project workspace is in a clean git state before measurement runs
- [ ] Confirm the user has a standalone terminal available (not inside Claude Code) for running instrumented commands

## Tasks

### Task 1: Determine available measurement instrumentation

**Description:** Before running any measurement, establish what tools are actually available to capture per-call token data in this environment. The architecture document identifies three possible sources: (a) Anthropic Console usage view, (b) API response metadata via debug logging, (c) Claude Code session cost display. We also explore `--output-format stream-json` as a structured alternative. We need to know which ones work here.

**Execution model:** User runs these commands in a standalone terminal (no active Claude Code session).

**Steps:**

1. Run a minimal Claude Code invocation with debug logging:
   ```bash
   claude -p --debug api --debug-file /tmp/claude-debug-test.log "What is 2+2?"
   ```

2. Run the same invocation with stream-json output to check for structured usage data:
   ```bash
   claude -p --output-format stream-json "What is 2+2?" > /tmp/claude-stream-test.json 2>&1
   ```

3. Inspect the debug log for usage metadata:
   ```bash
   grep -i "input_tokens\|output_tokens\|cache_creation\|cache_read" /tmp/claude-debug-test.log
   ```
   - Look for `usage.input_tokens`, `usage.output_tokens`, `usage.cache_creation_input_tokens`, `usage.cache_read_input_tokens` fields in API responses.
   - **Verification gate:** If the literal string `input_tokens` appears with a numeric value, debug logging exposes usage metadata. If absent, this instrumentation path is not viable for token-level data.

4. Inspect the stream-json output for usage data:
   ```bash
   grep -i "usage\|input_tokens\|output_tokens" /tmp/claude-stream-test.json
   ```
   - If `--output-format stream-json` includes per-message usage in a parseable JSON format, this may be a cleaner instrumentation path than debug log parsing.

5. **Document the debug log format.** Once the format is known, identify how to distinguish skill boundaries in the log. Look for: new system prompts (indicating a new subagent spawn), model name changes (Opus vs Sonnet), or conversation-reset markers. Write the parsing strategy so Tasks 4-5 have a concrete extraction methodology.

6. **Verify `-p` mode vs interactive mode parity.** Compare the debug output from Step 1 against an interactive session:
   ```bash
   claude --debug api --debug-file /tmp/claude-interactive-test.log
   ```
   Then inside the interactive session, type a trivial question and exit. Compare the system prompt and tool registry between the two logs:
   ```bash
   diff <(grep -c "tool" /tmp/claude-debug-test.log) <(grep -c "tool" /tmp/claude-interactive-test.log)
   ```
   If they differ materially, note which mode to use for which measurement. Interactive mode is what skills actually run in, so it is the ground truth for spawn-overhead measurement.

7. If debug logging does not expose per-call token metadata: check the Anthropic Console (console.anthropic.com -> Usage) for per-call visibility filterable by timestamp.

8. If neither works at per-call granularity: fall back to session-aggregate cost (visible at session end in Claude Code) with timestamp-delimited Console queries to attribute costs to skill invocations.

9. Document findings in `cost-reduction/stage-0-measure/instrumentation-notes.md`.

**Files:** Create `cost-reduction/stage-0-measure/instrumentation-notes.md`
**Acceptance criteria:**
- We know exactly which measurement source(s) to use for the remaining tasks
- We know whether per-call or only per-session granularity is available
- We know whether `cache_creation_input_tokens` and `cache_read_input_tokens` are present in the debug output — this is a binary yes/no finding, not an assumption
- If cache fields are not in debug output, we know whether the Anthropic Console shows cache metrics per API call
- If neither source provides cache data, document that cache behavior is unmeasurable from this environment and Task 6 should be marked as blocked (workaround: use a Python script with the Anthropic SDK to make direct API calls that expose the full response)
- We know whether `-p` mode and interactive mode produce the same system prompt and tool registry (or the nature of the difference)
- The debug log format is documented with a parsing strategy for identifying skill boundaries
- We have determined the instrumentation tier (see Task 7 for tier definitions)
**Effort:** small
**Depends on:** none

### Task 2: Measure per-spawn base-prompt overhead

**Description:** Determine how many tokens the Claude Code harness adds to each spawned subagent call (system prompt + `~/.claude/CLAUDE.md` + skill `SKILL.md` + tool registry). This is the load-bearing measurement for Risk R8 (whether E0's per-spawn overhead exceeds Stage 3 savings). The architecture estimates ~6,000 tokens; we need the real number.

**Execution model:** User runs these commands in a standalone terminal.

**Steps:**

1. Using the instrumentation from Task 1, run a minimal skill invocation that does as little work as possible — the goal is to isolate the fixed overhead from the variable work. Start an interactive session with debug logging:
   ```bash
   claude --debug api --debug-file /tmp/claude-spawn-overhead.log
   ```
   Inside the session, invoke `/capture_insight` with a one-line insight (it is the lightest skill). Exit the session.

2. Record `usage.input_tokens` for the first API call in the session. This represents: system prompt + CLAUDE.md + SKILL.md (capture_insight) + tool registry + the one-line user prompt.

3. **Measure SKILL.md sizes directly** rather than comparing skills. Count approximate tokens for each SKILL.md:
   ```bash
   wc -c ~/.claude/skills/*/SKILL.md | sort -n
   ```
   Divide character counts by 4 for approximate token counts. This gives the SKILL.md size range without requiring multiple expensive invocations.

4. Calculate: base overhead = input_tokens minus the user-supplied content (which is negligible in the minimal case).

5. **Attempt to isolate tool-registry cost.** First, validate whether `--tools ""` works:
   ```bash
   claude -p --tools "" --debug api --debug-file /tmp/claude-no-tools.log "What is 2+2?"
   ```
   - If this errors, try `--tools "Read"` (minimal single-tool set) and compare to a default-tools invocation.
   - If `--tools` variants all error or behave unexpectedly, estimate tool-registry size from the debug log instead — the tool definitions should be visible in the API request content blocks if the debug log is verbose enough.
   - Document the result either way.

6. Record results in the measurement table (see Task 7 output format).

**Files:** Results go into `cost-reduction/baseline.md` (Appendix A: Spawn Overhead)
**Acceptance criteria:**
- Per-spawn base-prompt overhead measured in tokens (total and broken down as far as instrumentation allows: system prompt, CLAUDE.md, SKILL.md, tool registry)
- SKILL.md sizes measured directly via character count for all skills
- Architecture's ~6,000 token estimate confirmed or corrected
- Can calculate: "for a 2-round loop with 4 subagent spawns, the fixed overhead is N tokens"
- `--tools` flag behavior documented (works / errors / alternative used)
**Effort:** medium
**Depends on:** Task 1

### Task 3: Determine inline vs. subagent status of `/plan` and `/revise`

**Description:** The architecture document notes a contradiction between `thorough_plan/SKILL.md` (says invoke `/revise` "in the original session context") and `revise/SKILL.md` (says "may run in a fresh session"). We need to observe what actually happens in practice.

**Execution model:** This is observed during the Task 4 measurement run (same physical session).

**Steps:**
1. Run `/thorough_plan` on a small, well-understood task (see Task 4 — this is combined with that measurement run).
2. During the run, observe (via debug logging from Task 1) how many separate API call chains are created:
   - If `/plan` runs inline: the orchestrator's session will show the plan-generation tokens in its own call chain (one continuous conversation with growing context)
   - If `/plan` is spawned: there will be a separate API call chain with its own system prompt for `/plan`
3. Same observation for `/revise` in round 2+.
4. The indicator is: does the debug log show a new conversation/session starting for `/plan` and `/revise`, or do those appear as continuations of the `/thorough_plan` conversation? Look for: new system prompts appearing in the log (signals a fresh subagent), model name changes, or conversation-reset markers as identified in Task 1's format documentation.
5. As a secondary sanity check (not primary evidence): at the end of the `/thorough_plan` run, check the session cost display. Note that subagent spawns within a single interactive session may still show as one aggregate session cost, so this indicator is unreliable on its own.
6. Document finding: "In this harness, `/plan` runs [inline/as subagent] and `/revise` runs [inline/as subagent]."

**Files:** Results go into `cost-reduction/baseline.md` (Appendix B: Harness Behavior)
**Acceptance criteria:**
- Binary answer: inline or subagent for each of `/plan` and `/revise` as currently configured
- Evidence documented (debug log excerpts or session count)
**Effort:** small (combined with Task 4)
**Depends on:** Task 1

### Task 4: Measure one complete `/thorough_plan` run

**Description:** This is the core measurement. Run `/thorough_plan` on a real (or representative) task and capture per-skill, per-round token usage. This produces the main cost table that replaces Section 4's illustrative numbers.

**Execution model:** User starts an interactive Claude Code session with debug logging in a standalone terminal. The user types `/thorough_plan` inside that session. This cannot be done via `-p` mode because `/thorough_plan` is an interactive skill.

**Steps:**
1. **Select the task.** Either:
   - (a) Re-run `/thorough_plan` against the cost-reduction architecture itself (meta but practical — we already know the task, and the architecture is fresh)
   - (b) Use the next organic task that needs `/thorough_plan`
   - (c) Pick a recently-completed feature and re-plan it
   - Option (a) is recommended because it requires no new context and the architecture document is a known-complexity artifact.

2. **Set up instrumentation.** Start an interactive Claude Code session with debug logging enabled:
   ```bash
   claude --debug api --debug-file cost-reduction/stage-0-measure/thorough-plan-debug.log
   ```
   Note the start timestamp (UTC) before invoking the skill. If also using Console-based measurement, note the timestamp window for post-hoc filtering.

3. **Run `/thorough_plan`.** Inside the interactive session, type the `/thorough_plan` command with the task description. Let it run to convergence naturally. Do not intervene to force more or fewer rounds — we want organic convergence behavior.

4. **After the run, extract per-step token data.** Using the parsing strategy documented in Task 1's instrumentation-notes.md, correlate debug log entries with specific skill invocations. For each step in the loop, record:
   - Skill name (orchestrator, `/plan`, `/critic` round N, `/revise` round N)
   - Model used
   - `input_tokens` (total)
   - `output_tokens` (total)
   - `cache_creation_input_tokens` (if available — may not be; see Task 1 findings)
   - `cache_read_input_tokens` (if available)
   - Approximate wall-clock duration (for TTL analysis)
   - Number of tool calls made (approximates file-read volume)

   **How to identify skill boundaries in the log:** Look for the markers identified in Task 1 — typically new system prompts (subagent spawns), model switches, or conversation resets. A `/critic` spawn will have a distinctly new system prompt since it must be a fresh session. `/plan` and `/revise` may or may not, depending on whether they run inline (this is what Task 3 determines).

5. **Note the round count.** How many rounds to convergence? What was the critic verdict each round?

6. **Calculate derived metrics** using the cache-aware cost formula:
   - For Opus: cost = (uncached_input_tokens * $15/M) + (cache_read_tokens * $1.50/M) + (cache_write_tokens * $18.75/M) + (output_tokens * $75/M)
   - For Sonnet: cost = (uncached_input_tokens * $3/M) + (cache_read_tokens * $0.30/M) + (cache_write_tokens * $3.75/M) + (output_tokens * $15/M)
   - Where uncached_input_tokens = input_tokens - cache_read_tokens - cache_write_tokens
   - **If cache token data is unavailable:** use the simpler formula (total input_tokens * per-M rate + output_tokens * per-M rate) and note this is an upper-bound approximation (actual cost is lower if caching is occurring)
   - Cache-hit ratio per step = `cache_read_input_tokens` / `input_tokens`
   - Codebase-read fraction = (tokens from file-read tool calls) / (total input_tokens) — if distinguishable from debug logs
   - Stable-prefix fraction = (system prompt + CLAUDE.md + SKILL.md + lessons-learned + architecture) / (total input_tokens)

**Files:**
- Raw data: `cost-reduction/stage-0-measure/thorough-plan-debug.log` (or Console screenshots)
- Parsed results: `cost-reduction/baseline.md` (Section 1: Per-Skill Cost Table)

**Acceptance criteria:**
- Per-step token table with all columns filled (or documented as "not available from this instrumentation" with the instrumentation tier noted)
- Rounds-to-convergence recorded
- Cache-hit ratios recorded (even if they are all zero — that is load-bearing data for C1)
- Total run cost calculated using the cache-aware formula (or the simplified formula with upper-bound noted) and compared to architecture's illustrative $4.65 estimate
**Effort:** large
**Depends on:** Tasks 1, 2, 3 (Task 3 is observed during this run)

### Task 5: Measure one `/architect` invocation

**Description:** `/architect` is the single heaviest skill per invocation. The architecture's C7 lever (scan/synthesize split) needs to know how much of the cost is file-reading vs. synthesis. This measurement provides that breakdown.

**Execution model:** User starts an interactive Claude Code session with debug logging in a standalone terminal.

**Note:** This measurement captures the Opus `/architect` cost, which is the normal operating mode per the skill's `model: opus` frontmatter. The existing `architecture.md` was produced by Sonnet (per its own Caveats section); the re-run will produce an Opus-quality output and the measurement reflects real Opus costs.

**Steps:**
1. **Select a task.** Either:
   - (a) Re-run `/architect` on the cost-reduction task itself (already done once by Sonnet — re-running on Opus gives a real-world measurement)
   - (b) Run `/architect` on the next organic task that needs architectural analysis
   - (c) Run `/architect` on a small, known task to get a lower-bound measurement
   - Option (a) is recommended for comparability with the existing architecture document.

2. **Set up instrumentation.** Start an interactive session:
   ```bash
   claude --debug api --debug-file cost-reduction/stage-0-measure/architect-debug.log
   ```

3. **Run `/architect`.** Inside the interactive session, invoke the skill. Let it complete naturally.

4. **After the run, extract:**
   - Total `input_tokens` and `output_tokens`
   - Number and approximate size of file-read tool calls (this is the "scan" cost that C7 would move to Sonnet)
   - Number and approximate size of web-search tool calls
   - The synthesis output size (the architecture.md content generated)
   - Cache-hit data if available
   - Wall-clock duration

5. **Calculate the scan/synthesize split:**
   - Scan cost = tokens consumed by file reads + web searches (input side) + tool-call overhead
   - Synthesize cost = remaining input (system prompt, context) + all output (the architecture document)
   - This split directly sizes C7: if scan is 70% of the bill, C7 moving scan to Sonnet saves ~70% * (1 - Sonnet/Opus ratio) = ~70% * 80% = ~56% of the `/architect` bill

6. **Calculate cost using the cache-aware formula** (same as Task 4 Step 6).

**Files:**
- Raw data: `cost-reduction/stage-0-measure/architect-debug.log` (or Console screenshots)
- Parsed results: `cost-reduction/baseline.md` (Section 2: Architect Cost Breakdown)

**Acceptance criteria:**
- Total cost of one `/architect` invocation measured (using cache-aware formula or simplified with upper-bound noted)
- Scan vs. synthesize cost split estimated (even if approximate)
- Comparison to `/thorough_plan` total cost (which is heavier overall?)
**Effort:** medium
**Depends on:** Task 1

### Task 6: Measure cache behavior across subagent boundaries

**Description:** The architecture's biggest open question for C1 is whether the Claude Code harness already does anything to enable prompt caching across orchestrator-to-subagent boundaries, and whether the 5-minute TTL holds across a multi-round loop. This task specifically investigates cache behavior.

**Execution model:** Pure analysis of data from Tasks 1 and 4. Can be done in a Claude Code session — no `claude` commands needed.

**Steps:**
1. **Check Task 1 findings first.** If Task 1 determined that cache fields (`cache_creation_input_tokens`, `cache_read_input_tokens`) are not available in any instrumentation source, document that cache behavior is unmeasurable and skip to Step 5 with estimated bounds.

2. From the Task 4 debug data, for each `/critic` spawn (which is known to be a fresh subagent):
   - Check `cache_read_input_tokens`. If > 0, something is being cached across boundaries.
   - Identify what portion was a cache read (compare to the system prompt + CLAUDE.md size from Task 2)
   - Check whether round-2 `/critic` has higher cache reads than round-1 (would indicate cross-round caching)

3. From Task 4, note the wall-clock time between:
   - Start of round 1 `/critic` and start of round 2 `/critic`
   - If > 5 minutes: the default TTL has expired; cache hits across rounds are impossible unless the harness sets the 1-hour TTL
   - If < 5 minutes: cache hits are possible if the prefix is byte-identical

4. Check whether the Claude Code harness sets `cache_control` breakpoints by examining debug logs for the `cache_control` field in API request content blocks.

5. Synthesize findings:
   - "The harness [does/does not] inject cache_control breakpoints"
   - "Cross-round cache-hit rate is [X%/zero/unmeasurable]"
   - "The TTL in use appears to be [5 min / 1 hour / unknown]"
   - "The realistic caching savings ceiling for this harness is [X%]"
   - If cache data is unmeasurable: estimate bounds based on what we can infer (e.g., "if caching is working, the maximum savings would be X% based on the stable-prefix fraction from Task 4; if caching is not working, the current cost is the upper bound and enabling caching would save approximately Y%")

**Files:** Results go into `cost-reduction/baseline.md` (Appendix C: Caching Behavior)
**Acceptance criteria:**
- Binary answer: does the harness do prompt caching across subagent boundaries? (yes/no/partial/unmeasurable)
- Cache-hit ratio for `/critic` round 1 and round 2 measured (or documented as unmeasurable with estimated bounds)
- TTL behavior characterized (or documented as unknown with implications stated)
- Realistic caching savings ceiling estimated (even if from indirect evidence)
**Effort:** small (data comes from Tasks 1 and 4; this is analysis)
**Depends on:** Tasks 1, 4

### Task 7: Compile baseline.md

**Description:** Assemble all measurements into the final deliverable: `cost-reduction/baseline.md`. This is the single artifact that all subsequent stages reference.

**Execution model:** Can be done in a Claude Code session — this is analysis and document compilation.

**Instrumentation tiers:** The template adapts to the level of data available from Task 1:

- **Tier A (per-call debug data with cache fields):** Full template with all columns populated.
- **Tier B (per-call debug data without cache fields, or Console timestamp correlation):** Template with per-skill token and cost data; cache columns marked "not available"; cache behavior estimated from indirect evidence.
- **Tier C (session aggregate only):** Minimal template with total-run costs and ratios estimated from file sizes and skill counts. Per-step breakdown estimated by proportional attribution.

Use the highest tier available. If Tier C, note that all per-step numbers are estimates and provide confidence ranges.

**Output format for `cost-reduction/baseline.md`:**

```markdown
# Cost Reduction Baseline — Measured Data

**Date:** <measurement date>
**Environment:** Claude Code CLI v<version>, model <model names used>
**Billing plan:** <metered API / Pro / Max / unknown — user to confirm>
**Instrumentation tier:** <A / B / C> (see definitions below)

### Instrumentation tier definitions
- **Tier A:** Per-call debug data with cache fields available. All columns populated with measured values.
- **Tier B:** Per-call debug data without cache fields, or Console timestamp correlation. Cache columns estimated or marked N/A.
- **Tier C:** Session aggregate only. Per-step breakdown estimated by proportional attribution. All numbers are estimates with confidence ranges.

## 1. Per-Skill Cost Table — `/thorough_plan` Run

| Step | Model | Input tokens | Output tokens | Cache read tokens | Cache write tokens | Cost ($) | Wall-clock (min) |
|------|-------|-------------|--------------|-------------------|-------------------|----------|-----------------|
| Orchestrator | <model> | <N> | <N> | <N> | <N> | <$N.NN> | <N> |
| /plan round 1 | <model> | <N> | <N> | <N> | <N> | <$N.NN> | <N> |
| /critic round 1 | <model> | <N> | <N> | <N> | <N> | <$N.NN> | <N> |
| /revise round 2 | <model> | <N> | <N> | <N> | <N> | <$N.NN> | <N> |
| /critic round 2 | <model> | <N> | <N> | <N> | <N> | <$N.NN> | <N> |
| ... | ... | ... | ... | ... | ... | ... | ... |
| **Total** | | **<N>** | **<N>** | **<N>** | **<N>** | **<$N.NN>** | **<N>** |

**Cost formula used:** cost = (uncached_input * rate) + (cache_read * 0.1 * rate) + (cache_write * 1.25 * rate) + (output * output_rate). If cache data unavailable, noted as upper-bound using total input * rate.

**Rounds to convergence:** <N>
**Critic verdicts:** Round 1: <PASS/REVISE>, Round 2: <PASS/REVISE>, ...

### Derived metrics
- **Codebase-read fraction:** <N>% of input tokens were file-read tool calls
- **Stable-prefix fraction:** <N>% of input tokens were system prompt + CLAUDE.md + SKILL.md + lessons-learned
- **Cache-hit ratio (overall):** <N>%
- **Cache-hit ratio (critic round 2 vs round 1):** <N>% vs <N>%

### Comparison to architecture estimates
| Metric | Architecture estimate (Section 4) | Measured |
|--------|----------------------------------|---------|
| Typical 2-round loop cost | ~$4.65 | $<N.NN> |
| Per-operation cost range | $0.24–$1.32 | $<N.NN>–$<N.NN> |
| Codebase read per session | ~40,000 tokens | <N> tokens |
| Stable prefix size | ~12,000 tokens | <N> tokens |
| System overhead per spawn | ~6,000 tokens | <N> tokens |

## 2. Architect Cost Breakdown

| Metric | Value |
|--------|-------|
| Total input tokens | <N> |
| Total output tokens | <N> |
| Total cost | $<N.NN> |
| Wall-clock duration | <N> min |
| File-read tool calls | <N> calls, ~<N> tokens |
| Web-search tool calls | <N> calls, ~<N> tokens |
| Scan cost (file reads + web + tool overhead) | ~$<N.NN> (<N>% of total) |
| Synthesize cost (remaining input + all output) | ~$<N.NN> (<N>% of total) |

**Note:** This measurement is of an Opus `/architect` run, which is the normal operating mode. The existing architecture.md was produced by Sonnet; this measurement reflects real Opus costs.

### C7 sizing
- Moving scan phase to Sonnet would save approximately $<N.NN> per /architect invocation (<N>% reduction)
- /architect total cost vs /thorough_plan total cost: $<N.NN> vs $<N.NN>

## Appendix A: Spawn Overhead

| Component | Tokens |
|-----------|--------|
| System prompt (Claude Code harness) | <N> |
| ~/.claude/CLAUDE.md | <N> |
| Skill SKILL.md (range across skills) | <N>–<N> |
| Tool registry | <N> |
| **Total per-spawn overhead** | **<N>** |

### SKILL.md sizes (measured via character count / 4)
| Skill | Approx. tokens |
|-------|---------------|
| /capture_insight | <N> |
| /plan | <N> |
| /critic | <N> |
| /revise | <N> |
| /thorough_plan | <N> |
| /architect | <N> |
| /discover | <N> |
| /review | <N> |
| /implement | <N> |
| ... | ... |

### `--tools` flag findings
- `--tools ""` behavior: <works / errors / N/A>
- Tool-registry token cost: <N tokens measured via flag comparison / estimated from debug log / unknown>

### E0 overhead calculation
- A 2-round loop with 4 subagent spawns (plan + 2x critic + revise) pays <N> * 4 = <N> tokens in spawn overhead
- At Opus rates: $<N.NN> in fixed overhead
- At Sonnet rates (for tiered spawns): $<N.NN> in fixed overhead
- Architecture estimate was ~6,000 tokens per spawn; measured is <N> tokens (<higher/lower/same>)

## Appendix B: Harness Behavior

### Inline vs. subagent status
- `/plan`: runs <inline / as subagent> in the current harness
- `/revise`: runs <inline / as subagent> in the current harness
- `/critic`: runs <as subagent> (confirmed — fresh session per SKILL.md design)
- **Evidence:** <brief description of how this was determined — e.g., "debug log shows new system prompt at timestamp X for /critic but /plan tokens appear in the orchestrator's conversation chain">

### `-p` mode vs interactive mode
- System prompt: <same / different — describe>
- Tool registry: <same / different — describe>
- Implication for Task 2 measurements: <whether -p mode measurements are representative>

### Source-file contradiction resolution
- `thorough_plan/SKILL.md` says: invoke `/revise` "in the original session context"
- `revise/SKILL.md` says: "This skill may run in a fresh session"
- **Observed behavior:** <what actually happens>
- **Implication for E0:** <whether E0's session-isolation fix changes current behavior or merely codifies it>

## Appendix C: Caching Behavior

### Cache breakpoint injection
- Does the harness inject `cache_control` breakpoints? <yes / no / unknown>
- Evidence: <debug log observation>

### Cross-round cache behavior
- Round-1 /critic cache_read_input_tokens: <N> (<N>% of input) [or "unmeasurable"]
- Round-2 /critic cache_read_input_tokens: <N> (<N>% of input) [or "unmeasurable"]
- Wall-clock between round 1 and round 2 critic spawns: <N> minutes
- TTL in use: <5 min / 1 hour / unknown>

### Caching savings ceiling
- Realistic per-loop caching savings: <N>% (architecture estimated 2-10%)
- Breakdown: <what is cacheable and what is not>
- If unmeasurable: estimated bounds based on stable-prefix fraction

## Appendix D: Convergence Behavior

- This run converged in <N> rounds
- Historical convergence data (if available from prior runs): <list>
- Does convergence-in-1 ever happen? <yes / no / insufficient data>
- Average rounds to convergence: <N> (or "insufficient data — single measurement")

## Open Questions Answered

| Question (from architecture) | Answer |
|------------------------------|--------|
| Per-spawn base-prompt overhead small or large? | <answer with number> |
| /plan and /revise inline or subagent? | <answer> |
| Cache-hit ratio across subagent boundaries? | <answer> |
| Which TTL does the harness use? | <answer> |
| How much of /architect cost is scan vs synthesize? | <answer with percentages> |
| Does convergence-in-1 ever happen? | <answer> |

## Implications for Subsequent Stages

### Stage 1 (Caching hygiene + context discipline)
- C1: <what the caching data means for C1's expected savings>
- C7: <what the /architect scan/synthesize split means for C7's expected savings>

### Stage 2 (Loop discipline)
- E0: <what the spawn overhead and inline/subagent findings mean for E0>
- B1: <what convergence data means for max_rounds cap>

### Stage 3 (Model tiering)
- <whether measured spawn overhead confirms or challenges Stage 3's net-positive economics>
- <whether Sonnet planner quality risk can be sized from this data>
```

**Files:** Create `cost-reduction/baseline.md`
**Acceptance criteria:**
- All sections filled with measured data (or explicitly marked with instrumentation tier and fallback)
- Every "Open Question" from the architecture has an answer or a documented reason why it could not be answered
- Implications section connects measurements to specific stage decisions
- Cost calculations use the cache-aware formula where cache data is available
**Effort:** medium (compilation and analysis of data from Tasks 1-6)
**Depends on:** Tasks 1, 2, 3, 4, 5, 6

## Integration analysis

### Measurement run impact
- **Current behavior:** No measurement infrastructure exists. Skill runs do not capture per-call token data by default.
- **New behavior:** One-time instrumented runs. No permanent changes to any skill files.
- **Failure modes:** Debug logging may not capture the fields we need. Console may not provide per-call granularity. `--output-format stream-json` may not include usage metadata.
- **Backward compatibility:** N/A — purely observational, no code changes.

### baseline.md as a contract
- **Downstream consumers:** Every subsequent stage's `/thorough_plan` should read `baseline.md` before planning.
- **Staleness risk:** Baseline becomes stale as models are updated, SKILL.md files change, or project complexity grows. The document should note its measurement date and conditions.
- **Format stability:** The table structure in Task 7 is the contract. Later stages reference specific sections (e.g., "Appendix A: Spawn Overhead" for E0 sizing).

### Execution model constraint
- **Nested session blocker:** Claude Code cannot spawn Claude Code. All measurement commands that invoke `claude` must be run by the user in a standalone terminal. Tasks 6-7 (analysis) can run inside Claude Code. This is a fundamental constraint of the harness, not a bug — plan accordingly.

## Risk analysis

| Risk | Likelihood | Impact | Mitigation | Rollback |
|------|-----------|--------|------------|----------|
| **Nested-session blocker prevents automated measurement** | Certain | High — Tasks 1-5 cannot run via `/implement` | Plan explicitly designates Tasks 1-5 as manual user steps with copy-paste-ready commands. Tasks 6-7 analysis runs in Claude Code. | N/A — this is a known constraint, not a failure |
| Debug logging does not expose per-call token metadata | Medium | Medium — falls back to coarser Console data or stream-json | Task 1 discovers this upfront via multiple instrumentation paths (debug, stream-json, Console); pivot to best available | N/A — no changes to roll back |
| Console does not provide per-call granularity for Claude Code CLI users | Medium | Medium — falls back to session-level cost display with timestamp correlation | Use session-aggregate cost + skill invocation timestamps to estimate per-skill costs | N/A |
| Cache-hit data is not visible in any available instrumentation | Medium | Low — we document "unmeasurable" with estimated bounds and Stage 1's C1 audit must include its own measurement | Task 1 checks all three sources explicitly. If none work, Task 6 provides estimated bounds from indirect evidence (stable-prefix fraction, file sizes). | N/A |
| `--tools ""` flag does not work for tool-registry isolation | Medium | Low — alternative approaches available | Task 2 Step 5 validates first, falls back to `--tools "Read"` comparison or debug-log estimation | N/A |
| Debug logs are too large or too noisy to parse manually | Medium | Medium — slows down Tasks 4-5 analysis | Task 1 documents the log format and parsing strategy upfront. Use `grep` and timestamp-based filtering. | N/A |
| The `/thorough_plan` measurement run converges in 1 round, providing minimal loop data | Low | Medium — single round means no cross-round caching data and no `/revise` measurement | If round 1 passes, run a second measurement on a more complex task, or artificially constrain the plan quality to force a REVISE | N/A |
| Measurement run is expensive (it is a real `/thorough_plan` on Opus) | Certain | Low — this is the cost of measurement, ~$5 based on architecture estimates | Use a small/medium task to minimize cost. The measurement run also produces a real, usable plan, so the cost is not pure waste. | N/A |
| `-p` mode differs from interactive mode, making Task 2 measurements unrepresentative | Low | Medium — spawn overhead numbers may not apply to real skill invocations | Task 1 Step 6 verifies parity. If they differ, use interactive mode for all measurements (slower but accurate). | N/A |

## Testing strategy

### Verification of instrumentation (Task 1)
- Run a minimal `claude -p` invocation and confirm token metadata is captured
- If debug logging: verify the log file contains `usage` fields with numeric values
- If stream-json: verify output contains structured usage data
- If Console: verify the timestamp filter shows the correct API calls
- Verify `-p` vs interactive mode parity

### Verification of measurements (Tasks 2-6)
- Cross-check: per-step costs should sum to approximately the session-aggregate cost shown by Claude Code
- Cross-check: input token counts should be roughly consistent with known file sizes (e.g., CLAUDE.md is ~X KB, SKILL.md files are 2-4 KB as measured by `wc -c`)
- Sanity check: per-spawn overhead should be at least 2,000 tokens (system prompt alone is non-trivial) and at most ~15,000 tokens

### Verification of baseline.md (Task 7)
- All "Open Questions Answered" cells are filled
- All table cells contain measured values or explicit "not measurable" notes with instrumentation tier stated
- Cost calculations use cache-aware formula where data is available (or note the upper-bound approximation)
- The "Implications for Subsequent Stages" section makes specific, actionable statements (not generic "we should measure more")
- A second reader (the user) can understand the document without access to raw debug logs

## Implementation order

1. **Task 1** — Determine instrumentation (must come first; everything else depends on knowing how to measure)
2. **Task 2** — Measure per-spawn overhead (quick, independent, informs Task 4 interpretation)
3. **Tasks 3 + 4** — Run `/thorough_plan` with instrumentation (Task 3 is observed during Task 4; these are one physical run)
4. **Task 5** — Run `/architect` with instrumentation (independent of Task 4; can run in parallel if desired)
5. **Task 6** — Analyze cache behavior from Tasks 1 and 4 data (pure analysis, no new runs)
6. **Task 7** — Compile baseline.md from all preceding data

**Estimated total effort:** 1-2 sessions. Tasks 1-5 are user-executed in standalone terminal sessions. Tasks 6-7 can be done in a Claude Code session. The measurement runs (Tasks 4 and 5) are the calendar-time bottleneck; each is a full skill invocation taking 10-30 minutes. The analysis and compilation (Tasks 6-7) are fast.

**Estimated measurement cost:** ~$5-10 total for the `/thorough_plan` and `/architect` runs, based on architecture estimates. This is the price of replacing guesses with data.
