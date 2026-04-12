# Cost Reduction Baseline — Measured Data

**Date:** 2026-04-12
**Environment:** Claude Code CLI v2.1.62 (sdk-cli entrypoint), model claude-opus-4-6
**Context window:** 200,000 tokens / **Max output:** 32,000 tokens
**Billing plan:** API metered (overage disabled — `out_of_credits`)
**Instrumentation:** `--verbose --output-format stream-json` (Tier A — full per-call structured data)

## 1. Per-Skill Cost Table — `/thorough_plan` Run

**Task:** Plan Stage 1 (caching hygiene) of the cost-reduction initiative
**Converged in:** 2 rounds (plan → critic R1 → revise → critic R2 → PASS)

| Phase | Skill | Model | Turns | Tool Calls | Peak Context (tokens) |
|-------|-------|-------|-------|------------|----------------------|
| Orchestrator | /thorough_plan | opus-4-6 | 24 | 28 | 76,652 |
| Subagent 1 | /plan (R1) | opus-4-6 | 19 | 28 | 123,923 |
| Subagent 2 | /critic (R1) | opus-4-6 | 15 | 28 | 98,361 |
| Subagent 3 | /revise (R2) | opus-4-6 | 17 | 26 | 107,283 |
| Subagent 4 | /critic (R2) | opus-4-6 | 15 | 23 | 78,891 |

### Session totals (from session result — authoritative)

| Model | Input (uncached) | Cache Read | Cache Write | Output | Cost |
|-------|-----------------|-----------|-------------|--------|------|
| claude-opus-4-6 | 8,144 | 5,902,630 | 651,194 | 142,029 | $10.61 |
| claude-haiku-4-5 | 12,380 | 0 | 25,607 | 867 | $0.05 |
| **Total** | **20,524** | **5,902,630** | **676,801** | **142,896** | **$10.66** |

**Wall-clock duration:** 56 minutes (3,389s), API time: 3,338s
**Total API calls:** 90 turns across 5 phases
**Total tokens processed:** 6,742,851 (input + cache_read + cache_write + output)

### Derived metrics

- **Cache-read fraction (overall):** 87.5% of all input tokens were cache reads (5,902,630 / 6,599,955)
- **Cache-write fraction:** 10.3% of input tokens were cache writes (676,801 / 6,599,955)
- **Uncached input fraction:** 0.3% of input tokens were truly new (20,524 / 6,599,955)
- **Output fraction:** 2.1% of total tokens were output (142,896 / 6,742,851)

### Per-phase cache-hit ratios

| Phase | Cache Read % | Cache Write % | Uncached % |
|-------|-------------|--------------|-----------|
| Orchestrator | 95.2% | 4.8% | <0.1% |
| /plan (R1) | 91.2% | 8.8% | <0.1% |
| /critic (R1) | 86.3% | 12.3% | 1.3% |
| /revise (R2) | 83.4% | 16.6% | <0.1% |
| /critic (R2) | 88.1% | 9.9% | 2.1% |

### Comparison to architecture estimates

| Metric | Architecture estimate | Measured | Ratio |
|--------|---------------------|----------|-------|
| Typical 2-round loop cost | ~$4.65 | **$10.66** | 2.3x higher |
| System overhead per spawn | ~6,000 tokens | **~41,000 tokens** | 6.8x higher |
| Stable prefix size | ~12,000 tokens | **~32,500 tokens** (cached) | 2.7x higher |

### Pricing discrepancy

The measured cost ($10.66) does not match standard published Anthropic API rates. At listed rates ($15/$75 per M in/out, 0.1x cache reads, 1.25x cache writes), the calculated cost would be ~$31.84. The 3x discrepancy suggests:
- The Claude Code billing tier may apply different rates
- Extended thinking output tokens may be billed at a different rate than standard output
- The `costUSD` field in the session result is the authoritative billed amount

**For cost reduction projections, use the reported $10.66 as the baseline, not the rate-calculated amount.**

## 2. Architect Cost Breakdown

**Not measured in this session.** Task 5 (instrumented `/architect` run) remains to be completed. The `/thorough_plan` run did not invoke `/architect`.

Estimated from the `/plan` subagent data (which does similar heavy file reading):
- `/plan` peak context: 123,923 tokens
- `/architect` likely similar or higher (it scans more broadly)
- Estimated cost: $2-4 per invocation (proportional to `/plan` phase)

## Appendix A: Spawn Overhead

### Measured values

| Run Configuration | Input | Cache Read | Cache Write | Total Context | Cost |
|-------------------|-------|-----------|-------------|--------------|------|
| Full tools (cache hit) | 3 | 32,515 | 0 | 32,518 | $0.016 |
| `--tools ""` (cache miss) | 3 | 0 | 41,172 | 41,175 | $0.257 |

**Best estimate for full base overhead: ~41,000 tokens** (from cache-write run).

### `--tools ""` behavior

- Disables built-in tools (Bash, Read, Edit, Grep, etc.) — dropped from 43 to 0
- MCP tools (33) remain loaded regardless of `--tools` flag
- Built-in tools appear partially deferred: debug log showed "Dynamic tool loading: 0/33 deferred tools included"
- Cannot cleanly isolate built-in tool registry cost via CLI flags

### Overhead decomposition (estimated)

| Component | ~Tokens | Source |
|-----------|---------|--------|
| Full prompt (measured) | ~41,175 | `--tools ""` cache-write |
| CLAUDE.md (global) | ~4,118 | `wc -c` / 4 (16,471 chars) |
| Skill listing (system-reminder) | ~500-1,000 | Estimated from init JSON |
| MCP tool definitions (33 tools) | ~3,000-5,000 | Estimated |
| System prompt + harness chrome | ~31,000-33,000 | Remainder |

### SKILL.md sizes

| Skill | Chars | ~Tokens |
|-------|-------|---------|
| capture_insight | 2,773 | ~693 |
| start_of_day | 4,716 | ~1,179 |
| revise | 5,030 | ~1,258 |
| thorough_plan | 5,213 | ~1,303 |
| plan | 5,234 | ~1,309 |
| gate | 5,449 | ~1,362 |
| weekly_review | 5,571 | ~1,393 |
| rollback | 5,690 | ~1,423 |
| end_of_task | 5,881 | ~1,470 |
| critic | 6,801 | ~1,700 |
| implement | 7,690 | ~1,923 |
| discover | 8,142 | ~2,036 |
| review | 8,276 | ~2,069 |
| end_of_day | 8,475 | ~2,119 |
| architect | 8,682 | ~2,171 |
| init_workflow | 11,115 | ~2,779 |
| **Total all skills** | **104,738** | **~26,185** |

### E0 overhead calculation

- A 2-round loop with 4 subagent spawns (plan + 2x critic + revise): each starts with ~41K base overhead
- Cache-hit scenario: 4 × 32,518 = **130,072 tokens** in spawn overhead
- At measured cache-read rate: ~$0.20 in fixed overhead per loop
- Cache-miss scenario: 4 × 41,175 = **164,700 tokens** in spawn overhead
- At measured cache-write rate: ~$1.03 in fixed overhead per loop
- Architecture estimate was ~6,000 tokens per spawn → actual is **~41,000 (6.8x higher)**
- However, the measured total loop cost ($10.66) shows spawn overhead is a small fraction — the dominant cost is the growing conversation context across multi-turn interactions within each phase

## Appendix B: Harness Behavior

### Subagent spawning mechanism

All subagents (/plan, /critic, /revise) are spawned via the **Task tool** within the same session. There is only **one `system init` line** in the entire JSONL output. Subagents are distinguished by `parent_tool_use_id`:

| Phase | parent_tool_use_id | Mechanism |
|-------|-------------------|-----------|
| Orchestrator | `null` | Root session |
| /plan (R1) | `toolu_01W82J...` | Task tool spawn |
| /critic (R1) | `toolu_019s6J...` | Task tool spawn |
| /revise (R2) | `toolu_01WTTJ...` | Task tool spawn |
| /critic (R2) | `toolu_018rum...` | Task tool spawn |

### Inline vs. subagent status

- **`/plan`: runs as subagent** (has distinct `parent_tool_use_id`, own conversation context)
- **`/revise`: runs as subagent** (has distinct `parent_tool_use_id`, own conversation context)
- **`/critic`: runs as subagent** (confirmed — fresh context per SKILL.md design)
- **Evidence:** All skill invocations show non-null `parent_tool_use_id` in stream-json output. Each starts its own cache-write cycle (new context).

### Source-file contradiction resolution

- `thorough_plan/SKILL.md` says: invoke `/revise` "in the original session context"
- `revise/SKILL.md` says: "This skill may run in a fresh session"
- **Observed behavior:** `/revise` runs as a **subagent with its own context** (distinct parent_tool_use_id, fresh cache writes). It does NOT share the orchestrator's conversation context.
- **Implication for E0:** The "invoke in original session context" instruction in `thorough_plan/SKILL.md` is not followed in practice. E0's session-isolation fix would codify the existing behavior rather than changing it.

### Haiku usage

The session also used `claude-haiku-4-5` for 12,380 input + 867 output tokens ($0.05). This is likely used by the Claude Code harness for internal operations (auto-compact, tool search, etc.), not by any skill directly.

## Appendix C: Caching Behavior

### Cache breakpoint injection

- **Does the harness inject `cache_control` breakpoints?** Yes — confirmed by the presence of `cache_creation` and `cache_read` fields with non-zero values across all phases.
- **TTL in use: 1-hour ephemeral** — confirmed by `cache_creation.ephemeral_1h_input_tokens` being non-zero and `ephemeral_5m_input_tokens` being zero in all observed cache writes.

### Cross-phase cache behavior

Each subagent spawn starts a new conversation with a fresh cache-write cycle. However, within each phase's multi-turn conversation, cache hits are very high:

| Phase | First-turn cache state | Subsequent turns |
|-------|----------------------|-----------------|
| Orchestrator | Cache hit (from prior CLI usage) | 95%+ cache reads |
| /plan (R1) | Cache write (new context) | 91%+ cache reads |
| /critic (R1) | Cache write (new context) | 86%+ cache reads |
| /revise (R2) | Cache write (new context) | 83%+ cache reads |
| /critic (R2) | Cache write (new context) | 88%+ cache reads |

### Cross-phase prefix sharing

The system prompt + CLAUDE.md + tool registry (~32K tokens) is identical across all phases. With a 1-hour TTL, these tokens should be cache-readable by subsequent phases if the prefix is byte-identical. The high cache-read ratios (83-95%) confirm this is happening.

### Caching savings ceiling

- **Current cache-hit rate: 87.5%** (overall)
- **Cost with zero caching (all at input rate):** ~$99+ (6.6M tokens × $15/M)
- **Actual cost with caching:** $10.66
- **Caching already saves approximately 89% of what the full input cost would be**
- **Remaining optimization ceiling for C1:** Small — the harness already caches aggressively. C1's value would be in ensuring cache MISSES don't happen unnecessarily (e.g., ensuring prefix stability across phases).

## Appendix D: Convergence Behavior

- This run converged in **2 rounds** (plan → critic → revise → critic PASS)
- Critic R1 produced issues requiring revision
- Critic R2 passed
- This is the minimum non-trivial convergence (single revision round)
- **Convergence-in-1 (critic passes on first review):** Not observed in this run. Unknown if it occurs for simpler tasks.
- **Average rounds to convergence:** 2 (single measurement — insufficient for average)

## Open Questions Answered

| Question (from architecture) | Answer |
|------------------------------|--------|
| Per-spawn base-prompt overhead small or large? | **Large: ~41,000 tokens (6.8x the 6,000 estimate)** |
| /plan and /revise inline or subagent? | **Both run as subagents** (via Task tool, own context) |
| Cache-hit ratio across subagent boundaries? | **83-95% within phases; new cache-write at each phase boundary** |
| Which TTL does the harness use? | **1-hour ephemeral** |
| How much of /architect cost is scan vs synthesize? | **Not measured — Task 5 still needed** |
| Does convergence-in-1 ever happen? | **Unknown — this run took 2 rounds** |

## Implications for Subsequent Stages

### Stage 1 (Caching hygiene + context discipline)

- **C1 (prompt caching):** The harness already caches at 87.5% hit rate with 1-hour TTL. The ceiling for further caching improvement is small. C1's value shifts from "enable caching" to "ensure cache stability" — preventing unnecessary cache misses when prefixes change slightly between phases.
- **C7 (/architect scan/synthesize split):** Not yet measured. Needs Task 5 data. However, the /plan subagent shows peak context of 124K tokens with heavy file reading — C7 could reduce this if the scan phase runs on Sonnet.
- **Context discipline:** The /plan phase hit 124K tokens (62% of the 200K window). The /revise phase hit 107K. These are approaching the limit. Context discipline (aggressive file-read targeting, summary injection) has real value here.

### Stage 2 (Loop discipline)

- **E0 (session isolation):** The SKILL.md contradiction is moot — /revise already runs as a subagent in practice. E0 should update the SKILL.md to match observed behavior. No cost change expected from this fix.
- **B1 (max_rounds cap):** This run converged in 2 rounds. Lowering the cap from 5 to 4 would not have affected this run. The cost savings from B1 come from preventing rare 4-5 round loops, which we haven't observed yet.
- **Round economics:** Each additional round adds ~2 subagent spawns (/revise + /critic). Based on measured data, each round costs roughly $2-3 in additional context and output tokens. Preventing one unnecessary round saves $2-3.

### Stage 3 (Model tiering)

- **Spawn overhead is 41K tokens, not 6K.** This is 6.8x higher than the architecture assumed. At Opus cache-read rates ($1.50/M), each spawn costs ~$0.049 in overhead. At Sonnet rates ($0.30/M), it would cost ~$0.010 — an 80% reduction per spawn.
- **However, spawn overhead is a tiny fraction of total cost.** The 4-spawn overhead ($0.20 at cache-read rates) is only 1.9% of the total $10.66 run. The dominant cost is the multi-turn conversation growth within each phase.
- **Model tiering's main savings come from running entire phases on Sonnet**, not from reducing spawn overhead. Moving /plan and /revise to Sonnet would save on the 5.9M cache-read tokens and 651K cache-write tokens — the bulk of the cost.
- **The $10.66 measured cost vs the $31.84 calculated cost (at published rates) suggests a ~3x billing discount.** Stage 3's savings projections must use measured costs, not rate-calculated costs, or they will overestimate savings.

### Cost reduction priority reassessment

Based on measured data, the highest-impact levers are:
1. **Model tiering (Stage 3):** Moving /plan and /revise to Sonnet would reduce the largest cost components. The bulk of cost is in Opus cache reads across 90 API calls.
2. **Context discipline (Stage 1 partial):** Reducing peak context (124K for /plan) reduces both cache-write costs for new content and the growing per-turn cache reads.
3. **Round reduction (Stage 2):** Preventing unnecessary rounds saves $2-3 each. Moderate impact.
4. **Caching hygiene (Stage 1 partial):** Limited ceiling — already at 87.5% hit rate. Focus on preventing regressions rather than improving.
