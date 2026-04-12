# Caching Audit — Stage 1

**Date:** 2026-04-12
**Data source:** `cost-reduction/stage-0-measure/thorough-plan-run.jsonl` (303-line JSONL from a 2-round `/thorough_plan` run)
**Session:** Plan Stage 1 caching hygiene, converged in 2 rounds, 90 API calls, $10.66 total

---

## Harness cache behavior (observed)

| Property | Value | Evidence |
|----------|-------|----------|
| TTL — root session | **1-hour ephemeral** | `cache_creation.ephemeral_1h_input_tokens > 0`, `ephemeral_5m = 0` for all orchestrator turns |
| TTL — subagents | **5-minute ephemeral** | `cache_creation.ephemeral_5m_input_tokens > 0`, `ephemeral_1h = 0` for all subagent turns |
| Cross-session hits (root) | Yes | Orchestrator turn 1 reads 17,932 tokens from cache (from prior CLI usage within 1h) |
| Cross-phase prefix sharing (subagents) | **Partial** | /critic R1, /revise R2, /critic R2 each share ~13,499 tokens on first turn. /plan R1 has **zero** cache reuse (cold start). |
| Within-phase hits | Excellent | 83–95% cache-read ratio after the first 1–2 turns of each phase |
| Breakpoint injection | Automatic | Harness injects `cache_control` breakpoints — confirmed by non-zero cache fields on every API call |

### Critical finding: dual TTL regime

The root session uses 1-hour TTL, but **all subagents spawned via the Task tool use 5-minute TTL**. This means:

- Within a phase's multi-turn conversation, cache hits work well (turns happen within seconds)
- Cross-phase prefix sharing works **only if** the gap between subagent spawns is under 5 minutes
- For a 56-minute `/thorough_plan` run with 5 phases, later phases cannot hit cache from early phases unless they share a common prefix that was recently written by an intermediate phase
- The 1-hour TTL reported in Stage 0 `instrumentation-notes.md` was measured on a standalone `-p` run (root session), not a subagent — **the Stage 0 TTL finding was partially incorrect**

### Why /plan R1 cold-starts but other subagents don't

| Phase | Turn 1 cache_read | Turn 1 cache_write | Explanation |
|-------|------------------:|-------------------:|-------------|
| /plan R1 | 0 | 19,514 | First subagent spawned — no prior subagent cache exists |
| /critic R1 | 13,499 | 5,808 | Shares ~13.5K prefix with /plan R1 (system prompt, CLAUDE.md); /plan's cache was written <5min ago |
| /revise R2 | 13,499 | 5,160 | Same shared prefix; /critic R1's cache still alive |
| /critic R2 | 13,499 | 5,802 | Same shared prefix; /revise's cache still alive |

The ~13,499 shared tokens represent the byte-identical prefix across all subagents: system prompt + harness chrome + CLAUDE.md. Each subagent then cache-writes its own unique content (SKILL.md, agent instructions, task-specific context).

---

## Stable prefix components

| Component | ~Tokens | Stable across turns? | Stable across phases? | Stable across skills? |
|-----------|--------:|:-------------------:|:--------------------:|:--------------------:|
| System prompt + harness chrome | ~13,500 | Yes | Yes | Yes |
| CLAUDE.md (global) | ~4,100 | Yes | Yes | Yes |
| Tool registry (built-in + MCP) | ~3,000–5,000 | Yes | Yes | Yes |
| SKILL.md (per-skill) | 693–2,779 | Yes | N/A | No (different per skill) |
| Agent spawn instructions | ~500–1,500 | Yes | N/A | Varies |
| **Shared prefix total** | **~13,500** | — | — | — |
| **Per-subagent unique content** | **~5,200–5,800** | — | — | — |
| **Full first-turn context** | **~19,300–19,500** | — | — | — |

Note: The ~13,500 shared tokens are lower than the ~32K measured in standalone `-p` mode because the standalone test includes tool definitions that may be deferred in subagent mode. The ~41K standalone overhead includes additional context not loaded in subagent spawns.

---

## Observed cache-hit rates

### Overall session

| Metric | Value |
|--------|------:|
| Total input tokens (all types) | 6,599,955 |
| Cache reads | 5,902,630 (89.4%) |
| Cache writes | 651,194 (9.9%) |
| Uncached input | 20,524 (0.3%) |
| **Effective cache-hit rate** | **87.5%** |

### Per-phase breakdown

| Phase | Turns | Peak ctx | Cache read % | Cache write % | Uncached % | TTL |
|-------|------:|---------:|------------:|-------------:|----------:|----|
| Orchestrator | 45 | 76,652 | 95.2% | 4.8% | <0.1% | 1h |
| /plan R1 | 28 | 123,923 | 91.2% | 8.8% | <0.1% | 5m |
| /critic R1 | 28 | 98,361 | 86.3% | 12.3% | 1.3% | 5m |
| /revise R2 | 26 | 107,283 | 83.4% | 16.6% | <0.1% | 5m |
| /critic R2 | 23 | 78,891 | 88.1% | 9.9% | 2.1% | 5m |

### Per-phase first-turn cache reuse

| Phase | Shared prefix (cache read) | New content (cache write) | % reused |
|-------|---------------------------:|-------------------------:|---------:|
| Orchestrator | 17,932 | 10,644 | 63% |
| /plan R1 | 0 | 19,514 | 0% |
| /critic R1 | 13,499 | 5,808 | 70% |
| /revise R2 | 13,499 | 5,160 | 72% |
| /critic R2 | 13,499 | 5,802 | 70% |

### Context growth pattern

Each phase starts small (~19K) and grows linearly as tool results and conversation history accumulate:

```
/plan R1:   19K → 124K (6.3x growth over 28 turns)
/critic R1: 19K →  98K (5.1x growth over 28 turns)
/revise R2: 19K → 107K (5.7x growth over 26 turns)
/critic R2: 19K →  79K (4.1x growth over 23 turns)
```

The dominant cost driver is not the initial spawn overhead but the **cumulative context growth** from multi-turn tool-use conversations. Each turn cache-reads the entire prior conversation and cache-writes the new increment.

---

## Cache cost analysis

### What caching saves

| Scenario | Estimated cost |
|----------|---------------:|
| No caching (all at Opus input rate: $15/M) | ~$99 |
| Current caching (87.5% hit rate) | $10.66 |
| **Caching saves** | **~$88 (89%)** |

### Where cache misses occur

Cache writes (misses) happen in two situations:

1. **Phase boundaries** — each subagent spawn writes ~5–19.5K tokens of new prefix content
2. **New content within a phase** — each tool result, user message, and assistant response extends the conversation and gets cache-written

The phase-boundary misses are small (total ~36K across 4 subagent spawns). The within-phase growth is large (conversation expands by 60–104K per phase).

### Cache-write cost breakdown

| Source | Cache-write tokens | Cost at Opus 1.25x ($18.75/M) |
|--------|-------------------:|------------------------------:|
| Phase-boundary prefix writes | ~36,282 | $0.68 |
| Within-phase conversation growth | ~614,912 | $11.53 |
| **Total** | **651,194** | **$12.21** |

(Note: the $12.21 calculated cache-write cost exceeds the $10.66 reported session cost — this confirms the billing discount noted in baseline.md.)

---

## Recommendations for SKILL.md prompt structuring

### What would improve cache hits

1. **Keep CLAUDE.md content stable and front-loaded.** It's part of the ~13.5K shared prefix. Any edit to CLAUDE.md invalidates the cache prefix for all skills. Avoid frequent edits to CLAUDE.md during active work sessions.

2. **Order SKILL.md content with stable sections first.** Place instructions that rarely change (model requirement, process steps) before sections that reference task-specific paths or file names. This maximizes the cache-readable prefix within each skill.

3. **No action needed on cross-phase prefix ordering.** The harness controls the prompt structure — SKILL.md content is injected by the system, and we cannot reorder it relative to system chrome.

### What would NOT meaningfully improve cache hits

1. **Shrinking SKILL.md files.** Each SKILL.md is 693–2,779 tokens. Even eliminating all SKILL.md content would save only ~5.8K tokens per phase boundary (from cache-write to nothing). At $18.75/M cache-write rate, that's $0.11 per subagent spawn — negligible compared to the $10.66 total.

2. **Forcing longer TTLs.** The TTL is set by the harness (1h for root, 5m for subagents). We cannot change this from SKILL.md content.

3. **Reducing the number of subagent spawns.** The 4-spawn overhead (cache-write cost) is ~$0.68 — only 6.4% of total cost. Running fewer phases saves more in eliminated multi-turn context growth than in spawn overhead.

### Correction to Stage 0 findings

| Finding | Stage 0 report | Corrected value |
|---------|---------------|-----------------|
| Cache TTL | 1-hour ephemeral | **Root: 1h, Subagents: 5m** |
| Shared prefix size | ~32,500 tokens | **~13,500 tokens** (subagent context, not standalone) |
| /plan R1 cache reuse | Not specifically noted | **Zero** — first subagent always cold-starts |

---

## Raw data reference

- Session JSONL: `cost-reduction/stage-0-measure/thorough-plan-run.jsonl` (303 lines)
- Baseline document: `cost-reduction/baseline.md`
- Instrumentation method: `cost-reduction/stage-0-measure/instrumentation-notes.md`
