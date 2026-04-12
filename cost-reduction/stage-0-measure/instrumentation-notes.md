# Instrumentation Notes — Stage 0 Measurement

**Date:** 2026-04-12
**Claude Code version:** 2.1.62
**Model (default):** claude-opus-4-6
**Context window:** 200,000 tokens
**Max output:** 32,000 tokens

## Instrumentation Tier: A (per-call structured data available)

### Working method

```bash
claude -p --verbose --output-format stream-json "<prompt>" > output.json 2>&1
```

For interactive sessions (skill invocations):
```bash
claude --verbose --output-format stream-json  # then invoke skill inside
```

### What works

| Method | Token data | Cache data | Cost data | Per-call granularity |
|--------|-----------|-----------|-----------|---------------------|
| `--verbose --output-format stream-json` | **Yes** | **Yes** | **Yes** | **Yes** |
| `--debug api --debug-file <path>` | No | No | No | No (startup logs only) |
| `--output-format stream-json` (without `--verbose`) | N/A | N/A | N/A | Errors: requires `--verbose` with `-p` |
| Anthropic Console | Not tested | Not tested | Not tested | Unnecessary — stream-json provides everything |

### JSON output structure

Each session produces JSONL (one JSON object per line):

1. **`type: "system"` (init)** — lists tools, MCP servers, skills, model, version, agents
2. **`type: "assistant"` (per-message)** — contains `message.usage` with:
   - `input_tokens` — non-cached input tokens
   - `cache_creation_input_tokens` — tokens written to cache this call
   - `cache_read_input_tokens` — tokens read from cache this call
   - `output_tokens`
   - `cache_creation.ephemeral_5m_input_tokens` — 5-minute TTL cache writes
   - `cache_creation.ephemeral_1h_input_tokens` — 1-hour TTL cache writes
3. **`type: "result"` (session summary)** — contains:
   - `total_cost_usd` — total session cost
   - `duration_ms` / `duration_api_ms` — wall-clock and API time
   - `modelUsage.<model>` — per-model breakdown with `inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, `costUSD`

### How to identify skill boundaries in multi-turn sessions

For `/thorough_plan` runs that spawn subagents (`/critic`, potentially `/plan`, `/revise`):
- Look for multiple `type: "assistant"` messages — each API call produces one
- Subagent spawns will appear as tool-use calls (Agent tool) in the parent conversation
- Model changes between messages indicate a different skill (e.g., Opus → Sonnet or vice versa)
- New system prompts within a session indicate subagent boundaries
- The `parent_tool_use_id` field on assistant messages indicates whether the message is from a subagent (non-null) or the parent session (null)

**Key indicator:** `parent_tool_use_id` — if non-null, this message is from a subagent spawned by the parent.

### Parsing strategy

```bash
# Extract all usage data from a session
grep '"type":"assistant"' output.json | python3 -c "
import sys, json
for line in sys.stdin:
    msg = json.loads(line)
    u = msg['message']['usage']
    parent = msg.get('parent_tool_use_id', 'root')
    model = msg['message']['model']
    print(f'{model} | parent={parent} | in={u[\"input_tokens\"]} cache_read={u[\"cache_read_input_tokens\"]} cache_write={u[\"cache_creation_input_tokens\"]} out={u[\"output_tokens\"]}')
"

# Extract session summary
grep '"type":"result"' output.json | python3 -c "
import sys, json
r = json.loads(sys.stdin.readline())
print(f'Total cost: \${r[\"total_cost_usd\"]:.4f}')
print(f'Duration: {r[\"duration_ms\"]}ms (API: {r[\"duration_api_ms\"]}ms)')
for model, usage in r.get('modelUsage', {}).items():
    print(f'  {model}: in={usage[\"inputTokens\"]} out={usage[\"outputTokens\"]} cache_read={usage[\"cacheReadInputTokens\"]} cache_write={usage[\"cacheCreationInputTokens\"]} cost=\${usage[\"costUSD\"]:.4f}')
"
```

## Cache behavior

### TTL
- The harness uses **1-hour ephemeral TTL** (not 5-minute)
- Confirmed by `cache_creation.ephemeral_1h_input_tokens: 41172` in the no-tools test
- `ephemeral_5m_input_tokens: 0` in all tests

### Cache hit/miss pattern
- First call after a fresh session or prompt change: full cache write (~41K tokens at 1.25x input rate)
- Subsequent calls with identical prefix: cache read (~32.5K tokens at 0.1x input rate)
- **Cache read vs write cost difference: ~16x** ($0.016 vs $0.257 for the same prompt)

### Cross-session caching
- The first `-p` test (with debug logging) wrote to cache
- The second `-p` test (with stream-json, ~3 min later) hit cache (32,515 cache-read tokens)
- This confirms cross-session cache hits work when the prompt prefix is byte-identical and within the 1-hour TTL

## Per-spawn base-prompt overhead

### Measured values

| Run | input_tokens | cache_read | cache_write | Total context | Cost |
|-----|-------------|-----------|-------------|--------------|------|
| With tools (cache hit) | 3 | 32,515 | 0 | 32,518 | $0.016 |
| `--tools ""` (cache miss) | 3 | 0 | 41,172 | 41,175 | $0.257 |

### Discrepancy analysis

The cache-hit run shows 32,518 total tokens; the cache-miss run shows 41,175. The 8,657-token difference is likely due to:
1. The cache-hit run read from a cache built by the earlier `--debug api` run, which may have had a slightly different prompt structure
2. Dynamic tool loading / deferred tool schemas may alter the cached prefix
3. The `--tools ""` flag changes prompt structure (removes built-in tool definitions but adds different instructions)

**Best estimate for full base overhead: ~41,000 tokens** (from the cache-write run, which represents the complete prompt without any caching).

### `--tools ""` behavior

- `--tools ""` disables built-in tools (Bash, Read, Edit, Grep, Glob, Write, etc.)
- MCP tools (33) remain loaded regardless of `--tools` flag
- Built-in tools appear to be partially deferred (debug log: "Dynamic tool loading: 0/33 deferred tools included")
- Cannot cleanly isolate built-in tool registry cost via `--tools` flag because MCP tools persist

### Overhead decomposition (estimated)

| Component | ~Tokens | Method |
|-----------|---------|--------|
| Full prompt (measured) | ~41,175 | `--tools ""` cache-write run |
| CLAUDE.md (global) | ~4,118 | `wc -c` / 4 |
| Skill listing (system-reminder) | ~500-1,000 | Estimated from init JSON |
| MCP tool definitions (33 tools) | ~3,000-5,000 | Estimated |
| System prompt + harness chrome | ~31,000-33,000 | Remainder |

### Architecture estimate comparison

| Metric | Architecture estimate | Measured |
|--------|---------------------|----------|
| Per-spawn base overhead | ~6,000 tokens | **~41,000 tokens** |
| Ratio | 1x | **~6.8x higher** |

This is the single most important finding so far. The per-spawn overhead is dramatically higher than estimated. For a 2-round `/thorough_plan` loop with 4 subagent spawns, the fixed overhead is:
- Cache-hit scenario: 4 × 32,518 = **130,072 tokens** (at cache-read rate: ~$0.20)
- Cache-miss scenario: 4 × 41,175 = **164,700 tokens** (at cache-write rate: ~$0.77)

## SKILL.md sizes

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

SKILL.md content adds 693–2,779 tokens per skill invocation on top of the base overhead.

## `-p` mode vs interactive mode

### Parity check

Both modes load:
- Same model (claude-opus-4-6)
- Same MCP servers (8)
- Same skills (19 listed)
- Same agents (4: general-purpose, statusline-setup, Explore, Plan)

The `-p` mode (with `--verbose --output-format stream-json`) provides full structured usage data and is sufficient for measurement. Interactive mode measurements can use the same `--verbose --output-format stream-json` flags.

**Note:** The `--debug api` flag does NOT expose API usage data — it only shows startup, MCP connection, and config logs. Use `--verbose --output-format stream-json` exclusively for measurement.

## Cost formula

### Cache-aware (Tier A — when cache fields are available)

**Opus (claude-opus-4-6):**
```
cost = (input_tokens × $15/M) + (cache_read_tokens × $1.50/M) + (cache_creation_tokens × $18.75/M) + (output_tokens × $75/M)
```

**Sonnet (claude-sonnet-4-6):**
```
cost = (input_tokens × $3/M) + (cache_read_tokens × $0.30/M) + (cache_creation_tokens × $3.75/M) + (output_tokens × $15/M)
```

### Simplified (when cache fields unavailable)

```
cost = (total_input_tokens × input_rate) + (output_tokens × output_rate)
```
This is an upper-bound approximation — actual cost will be lower if cache hits occur.

## Open questions resolved by Task 1

| Question | Answer |
|----------|--------|
| Which instrumentation to use? | `--verbose --output-format stream-json` (Tier A) |
| Per-call or per-session granularity? | Per-call (each assistant message has usage) |
| Cache fields visible? | Yes — full breakdown including TTL type |
| Which TTL does the harness use? | **1-hour ephemeral** (not 5-minute) |
| Can we identify subagent boundaries? | Yes — via `parent_tool_use_id` field |

## Remaining tasks

- **Task 3+4:** Instrumented `/thorough_plan` run (interactive session with `--verbose --output-format stream-json`)
- **Task 5:** Instrumented `/architect` run
- **Task 6:** Cache behavior analysis (from Task 4 data)
- **Task 7:** Compile baseline.md
