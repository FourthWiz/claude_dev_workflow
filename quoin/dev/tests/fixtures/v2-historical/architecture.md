# Architecture: Workflow Cost Reduction

**Date:** 2026-04-11
**Author:** /architect (running on Sonnet 4.6 — see "Caveats" at bottom)
**Task folder:** [cost-reduction/](.)

---

## 1. Context and problem statement

The dev-workflow is high-touch on Opus: 7 of 16 skills run on the strongest model, and the heaviest of them — `/architect`, `/discover`, and the `/thorough_plan` loop (`/plan` + N×`/critic` + N×`/revise`) — are exactly the ones that consume the largest token contexts (whole-codebase reads, lessons-learned, prior critic responses, full plans). Goal: cut cost without giving up the qualities that make the workflow useful (rigorous critique, integration safety, plan correctness).

The user has proposed one specific path and is asking what alternatives exist. The goal of this architecture document is to lay out the full cost-reduction design space, evaluate the user's proposal against it, and recommend a path that captures most of the savings without measurably hurting plan quality.

### 1.0 Billing-plan gate (read this before everything else)

**The rest of this document assumes metered API billing (pay per token).** If you are on a flat-rate Pro or Max plan, the optimization target inverts:

- **Metered billing (assumed below):** cost = dollars per token. Every lever in Sections 3–5 applies. Model downgrades and caching both translate directly to money saved.
- **Flat-rate Pro/Max plan:** cost = rate-limit headroom and context-window pressure. The A-series (model downgrades), Section 4's dollar table, and most of Stage 3 become irrelevant — you are not paying per Opus token, you are paying in throttling events. What *does* still matter on a flat-rate plan is:
  - Stage 1 (caching hygiene, `/architect` split, context discipline) — slightly faster wall-clock for warm-prefix calls (latency, not rate-limit headroom; the caching savings are ~2% of tokens and too small to meaningfully move the rate-limit needle). C7's `/architect` scan/synthesize split is the one piece of Stage 1 that matters on flat-rate plans for real reasons — latency and context-window pressure.
  - Stage 2 (loop discipline, lower `max_rounds`) — caps worst-case throttling on a hard task.
  - The E-series quality argument for subagent isolation — purely a quality/hygiene lever, independent of billing.
  - Stage 4 (task triage) — still useful for latency.

**Action item for the user:** confirm which plan you are on (Open Question #1 in Section 10 is load-bearing — it decides whether most of this document applies). If you are on Pro/Max, skip Section 4 and Stage 3 and treat Section 5 as "Stage 1 + Stage 2 + Stage 4 are the rollout; the rest is deferred."

### 1.1 Constraints and non-negotiables

- **Critic must remain unbiased.** Fresh sessions for `/critic` are non-negotiable per [dev-workflow/skills/thorough_plan/SKILL.md](dev-workflow/skills/thorough_plan/SKILL.md). This rule applies to *session isolation*, not to model choice — tiering the critic model is a separate question (see Section 5, Stage 3).
- **`/implement` and `/end_of_task` stay explicit.** Cost optimizations cannot remove the human-in-the-loop gates.
- **Plan correctness > plan throughput.** A cheaper plan that misses an integration bug costs far more downstream than the Opus tokens it saved.
- **No new tooling required.** Optimizations should be expressible as edits to `SKILL.md` files and (optionally) `~/.claude/CLAUDE.md`. No new infra.

---

## 2. Current state — where the money goes

### 2.1 Model assignment baseline

| Skill | Model | Cost class | Why expensive |
|---|---|---|---|
| `/discover` | Opus | High (rare) | Full repo scan, parallel reads |
| `/architect` | Opus | **Highest** | Cross-repo exploration, web search, deep file reads — the single most expensive skill per invocation |
| `/thorough_plan` | Opus | Orchestrator overhead | Coordinates the loop; **carries its own per-round token cost** that is easy to overlook (see 2.2) |
| `/plan` | Opus | High | Reads lessons-learned + architecture + codebase + writes long plan |
| `/critic` | Opus | High × N rounds | **Fresh session each round**, re-reads lessons-learned + plan + actual code |
| `/revise` | Opus | High × (N−1) rounds | Reads plan + critic-response + re-reads code where flagged |
| `/review` | Opus | High | Reads diff + full modified files + plan + architecture + prior critic responses |
| `/init_workflow` | Opus | One-time | Mostly file scaffolding; auto-invokes `/discover` |
| `/implement` | Sonnet | Medium | Reads plan + code, writes code |
| `/gate`, `/rollback`, `/end_of_task`, `/end_of_day`, `/start_of_day`, `/weekly_review`, `/capture_insight` | Sonnet | Low | State management, file ops |

**Approximate price per million tokens (Anthropic API list, April 2026 — confirm at time of rollout):**
- Opus 4.x: ~$15 input / ~$75 output
- Sonnet 4.x: ~$3 input / ~$15 output
- Haiku 4.x: ~$0.80 input / ~$4 output

→ **Sonnet is ~5× cheaper than Opus on both axes.** Haiku is ~4× cheaper than Sonnet.

**`/architect` deserves its own call-out:** of all the skills above, it is the single heaviest per-invocation. It does cross-repo file reads, web searches, and long-form synthesis all at Opus rates. Section 3's C-series has several levers aimed at it specifically (C7, below). It is also the skill most under-served by the "critic loop" framing of this document, because `/architect` has no loop — every invocation is one heavy Opus run.

### 2.2 Loop economics

A typical `/thorough_plan` run that converges in 2 rounds, today:

| Step | Model | Reads | Writes |
|---|---|---|---|
| `/thorough_plan` orchestrator | Opus | CLAUDE.md + its own SKILL.md + round bookkeeping | round state |
| `/plan` (round 1) | Opus | lessons-learned + architecture + codebase | current-plan.md (long) |
| `/critic` (round 1, fresh) | Opus | lessons-learned + current-plan.md + **codebase again** | critic-response-1.md |
| `/revise` (round 2) | Opus | current-plan.md + critic-response-1.md + targeted code | current-plan.md (updated) |
| `/critic` (round 2, fresh) | Opus | lessons-learned + current-plan.md + **codebase again** | critic-response-2.md |

**Five expensive Opus operations** (four loop steps plus the orchestrator session itself), of which three re-read substantial code/context. The codebase reads are the dominant input cost. The orchestrator row is easy to forget but real: every round, the orchestrator's own session pays its own system prompt and any accumulated context it's holding — that is one of the motivations for E0 (reframed in Section 3.E) which pushes the orchestrator to stay thin. The convergence rule allows up to 5 rounds, which means the worst case is much worse.

### 2.3 The three biggest cost drivers (in order)

1. **Re-reading the same context across fresh sessions.** Each fresh `/critic` agent re-pays input cost for lessons-learned + plan + the actual source files. Across 2-3 critic rounds this is the dominant line item.
2. **Opus on every planner step.** The plan/revise side of the loop is on Opus even though most plan revisions are mechanical (apply critic feedback, tighten wording).
3. **Worst-case loop length.** `max_rounds = 5` is a long tail. Rare, but when it happens, it's expensive.

Anything that does not attack one of these three is not a meaningful saving — **with one exception:** `/architect` runs outside the loop, pays no critic tax, but is the heaviest single skill. It deserves its own lever set (C7 below) independent of the loop.

---

## 3. Design space — every cost-reduction lever

Numbered for cross-reference. Mix-and-match.

### A. Model downgrades

- **A1. Sonnet across the board for the loop.** Move `/plan`, `/critic`, `/revise` all to Sonnet. ~5× cost cut on those skills. **Risk:** weaker critic = missed issues = production incidents downstream. The leverage role of the critic argues against this.
- **A2. Sonnet planner, Opus critic.** Move `/plan` and `/revise` to Sonnet, keep `/critic` on Opus. The critic is the highest-leverage role per token; the planner side is more mechanical. (User's proposal is a variant of this.)
- **A3. Tiered escalation on the planner side only.** Round 1 `/plan` on Sonnet; if `/critic` (still Opus) returns REVISE, round 2 `/revise` can stay Sonnet; only escalate the planner side to Opus on the final round. The critic never leaves Opus. Captures the easy-task fast path without touching the quality-critical role.
- **A4. Haiku for state-management Sonnet skills.** `/end_of_day`, `/start_of_day`, `/capture_insight`, `/weekly_review` are mostly file I/O + light reasoning. Most could run on Haiku. Small savings per call but high call frequency → adds up. **Risk:** `/gate` does light reasoning about test output and risk; keep it on Sonnet. `/end_of_task` and `/rollback` similarly stay on Sonnet (they touch git state).
- **A5. Per-project model overrides.** Make the model assignment configurable so the user can dial cost vs quality per project (large-blast-radius repos stay on Opus; experimental side projects use Sonnet).

### B. Loop / iteration changes

- **B1. Lower default `max_rounds` from 5 → 4.** Single-line change in [dev-workflow/skills/thorough_plan/SKILL.md](dev-workflow/skills/thorough_plan/SKILL.md) — trims the worst-case tail by one round while leaving headroom for a hard task that genuinely needs a 4th round before escalation. Convergence-driven termination is preserved — the loop still stops early when a round returns PASS. Paired with a simple inline override rule (see Stage 2): users can append `max_rounds: N` anywhere in the task description to raise the cap back to 5 (or higher) without editing SKILL.md.
- **B2. (Dropped.)** A "PASS if only MAJORs remain, because `/review` will catch them" rule was considered and rejected. Reason: it weakens the critic's value without a measurement to prove `/review` actually catches the same issue classes that a round-N+1 critic would have. If Stage 0's baseline ever shows that `/review` reliably catches MAJORs that critic round-N+1 would have flagged, revisit. Until then, no rule change.
- **B3. Cap on equivalent regressions.** If round N's critic flags the same issue family as round N−1, escalate to user instead of paying for round N+1. (Loop-detection clause already exists in spirit; tighten it.)

### C. Context / token reduction (the biggest lever and the most under-used)

#### Verified Anthropic prompt-caching facts (confirmed April 2026 via platform.claude.com docs)

- **`cache_control` is an API-level field,** set on content blocks in the JSON request. You cannot attach it from SKILL.md markdown — it is inserted by the *client* (in our case, the Claude Code harness) before the request is sent.
- **Cache reads are 0.1× the normal input price** (90% discount). Cache writes are 1.25× (25% surcharge for the first write).
- **Minimum cacheable prefix:** ~4096 tokens for Opus 4, ~2048 for Sonnet 4. Below the minimum, caching has no effect.
- **Prefix must be 100% byte-identical** to hit. Any drift (a changed timestamp, a reordered section) invalidates.
- **TTL:** 5 minutes (default) or 1 hour (explicit). **TTL may be a real constraint for heavy runs.** A single `/plan` invocation against a large codebase with web search can take 10–25 minutes, and a full two-round loop on a hard task can run 30–60+ minutes — that blows past the 5-minute default, silently turning cache writes into wasted surcharge. Whether the Claude Code harness sets the 1-hour TTL is unknown from inside the harness. **Stage 0's C1 audit must specifically check (a) which TTL the harness uses and (b) whether cross-round cache-hit rates are actually non-zero on real runs.** Without that check, Stage 1's C1 work may have no measurable effect.
- **Max 4 cache breakpoints per request.** Enough for [system prompt] + [lessons-learned] + [architecture] + [current-plan], which is exactly the structure we'd want.
- **Critically: subagents do NOT automatically inherit the parent's cache.** Each spawned subagent is a separate API call with its own system prompt and its own cache lookup. A cache hit happens only if the spawned agent's prefix is byte-identical to a prefix that was already warm on *that agent's* call chain within the TTL.

**What this means for our workflow:**

- The orchestrator → subagent boundary is exactly where the most expensive re-reads happen (fresh `/critic` sessions), AND exactly where caching does NOT automatically propagate. This is the biggest missed opportunity and also the biggest open question: **whether Claude Code's harness already injects `cache_control` on the system prompt and any file-read results — we do not know from inside the harness.** Stage 1's first job is to answer that via a measurement.
- Even if the harness does cache the system prompt, it cannot cache the file reads that `/critic` performs, because those are tool calls returning fresh content each round, not part of the system prompt prefix.
- The savings ceiling from caching is bounded by "what fraction of the critic's input is a byte-identical stable prefix" — which is lessons-learned (stable during the run) and the plan being critiqued (stable within a round). The codebase re-reads are not cacheable via system-prompt caching at all; they would need C2 or C3-style context manipulation.

#### C levers (revised with real facts)

- **C1. Prompt-caching audit + hints where possible.** Before claiming savings, verify what the harness already does. Then, where stable prefixes exist (lessons-learned, architecture.md, current-plan.md within a round), structure the prompts so the harness's caching (if any) can hit. Expected savings are **much smaller than "up to 90%"** because: (a) the 90% discount only applies to the input part of the prefix that is actually cached, (b) subagents do not auto-inherit cache, and (c) file-read tool calls are not part of the cacheable prefix. A realistic ceiling is **~15–25% of the total loop bill**, concentrated on lessons-learned and stable-prefix reads. Stage 0 baseline measurement is required to confirm.
- **C2. (Dropped.)** A "targeted critic on round 2+ that only re-reads files the previous critic flagged" rule was considered and rejected. Reason: it is a blind-spot amplifier. If round 1 missed a class of issues (say, a security regression in a file it didn't flag), round 2 by construction never looks at it either. The very point of multiple critic rounds is to catch what an earlier round missed. The savings goal that motivated C2 is better served by caching (where possible) and by lowering `max_rounds` (B1).
- **C3. Don't re-read lessons-learned mid-loop — but expect small savings.** Lessons-learned on a new project starts empty and grows by ~2–4 lines per task. Even after a year of heavy use it is a few KB. The value of C3 is **correctness and cleanliness** (don't re-pay for content that cannot have changed), not meaningful cost savings. Keep it as a tidy rule, not a headline lever.
- **C4. Diff-only review.** `/review` reads the full modified files in addition to the diff. For most reviews, the diff plus the immediately surrounding context is enough; only fall back to the full file when the diff suggests a structural concern. Real lever, worth including in Stage 1.
- **C5. Skip `/discover` for unchanged repos.** Cache `git rev-parse HEAD` per repo from the last `/discover` run; skip repos whose HEAD hasn't moved.
- **C6. Lessons-learned pruning.** As the file grows it becomes a fixed tax on every planning skill. Add a periodic prune step to `/end_of_day` or `/weekly_review`.
- **C7. `/architect`-specific: split scan and synthesize.** `/architect` currently does file reading, web search, *and* long-form synthesis in a single Opus session. Split into a "scan" phase (narrow read-only subagents on Sonnet, parallel across repos, emit structured findings) feeding a "synthesize" phase (Opus, serial, reads the findings not the files). Most of the token volume is in the scan — paying Opus rates for bulk file reading is pure waste. Pair with C5 to skip unchanged repos entirely. Cache the final `architecture.md` so downstream skills reading it get the cached-read discount.

### D. Skip / shortcut paths (task triage)

- **D1. Explicit task-size triage.** At the start of `/thorough_plan`, classify the task as Small / Medium / Large (either by user tag or by Claude's judgment). Each tier picks a different model+rounds profile. The CLAUDE.md already hints at this ("small changes can skip /architect"); make it operational with concrete profiles.
- **D2. Single-pass plan mode.** For trivial tasks: `/plan` (Sonnet) → `/implement` → `/review`. No critic loop. User opts in via `/plan` instead of `/thorough_plan`. **Mechanism: this already exists** — `/plan` is a separate skill from `/thorough_plan`. The change is documentation + triage prompt, not new infra.
- **D3. Cheap gates by default, heavy gates on demand.** `/gate` between phases doesn't need to run a full test+lint+typecheck for every transition. A "smoke gate" (lint + the affected tests) before `/implement` and a "full gate" before `/end_of_task` is sufficient.

### E. Subagent strategy

The current design already mandates that `/critic` runs in a fresh subagent session. Whether `/plan` and `/revise` should also run as dedicated subagents is the question of this section.

**Framing correction (the honest reason):** In Round 1 of this document I argued that moving `/plan` and `/revise` out of the orchestrator session would be a *direct cost win* because "the orchestrator currently carries the full planning context across all rounds." That framing was wrong — or at least unverified. After reading the Anthropic caching docs:

- Subagents are separate API calls. Each re-pays its own system prompt, its own `~/.claude/CLAUDE.md`, its own tool registry overhead.
- Subagents do not automatically inherit the parent's cache. A spawned `/plan` pays its base-prompt cost fresh every time.
- In a 2-round loop that spawns `/plan` + 2×`/critic` + `/revise`, we'd pay 4× the base-prompt overhead instead of amortizing it inline once.

So the naive "isolate everything, save tokens" claim is backwards at first order: isolation costs more tokens per round, not fewer. The question is whether the *quality* and *tiering* benefits of isolation are worth the per-spawn overhead. I now think they are, but for different reasons than I first stated. The E-series is reframed below.

- **E0. Full role isolation — critic, planner, reviser each as their own subagent. (Quality + enabling architecture, NOT direct cost win.)** Today `/thorough_plan` runs `/plan` and `/revise` inline and spawns only `/critic` as a fresh agent. The correct shape is:
  - `/plan` (round 1) → spawned as a dedicated subagent. Output: `current-plan.md`.
  - `/critic` (every round) → spawned as a fresh subagent. **Already the design; make it explicit that it must NEVER run inline.**
  - `/revise` (rounds 2+) → spawned as its own subagent, receiving only `(current-plan.md, critic-response-N.md, targeted files)`.
  - `/thorough_plan` orchestrator stays thin: reads output files between rounds and decides whether to continue. Never accumulates planning context itself.

  **Why this matters for quality (the real reason):** Fresh context for the planner is almost as valuable as fresh context for the critic. An orchestrator that has been accumulating critic feedback for 3 rounds will unconsciously anchor its revisions to that history — exactly the cognitive contamination the critic isolation rule was designed to prevent. Isolation preserves the planner's ability to take the critic's feedback at face value without anchoring on "what I was told in round 1."

  **Why this matters as enabling architecture:** **Stage 3 (model tiering) requires subagent isolation.** You cannot "run round-1 `/plan` on Sonnet and round-3 `/plan` on Opus" from within a single inline orchestrator session — skill frontmatter pins one `model:` per skill file. The way to tier per round is to spawn a subagent and pass it the model to use (or spawn a different skill file per tier, see Section 5 / Stage 3 for the concrete mechanism). E0 is the enabler; the savings come from Stage 3.

  **Honest token economics:** E0 costs more tokens per round than inline (4× base-prompt overhead instead of 1×), but unlocks Stage 3's model tiering, which saves more tokens than E0 costs. Net win only in combination with Stage 3 — not on its own.

  **Unresolved source-file contradiction:** [dev-workflow/skills/thorough_plan/SKILL.md](dev-workflow/skills/thorough_plan/SKILL.md) tells the orchestrator to invoke `/revise` "in the original session context (it needs to understand the plan's intent)." [dev-workflow/skills/revise/SKILL.md](dev-workflow/skills/revise/SKILL.md) says "This skill may run in a fresh session." The source contradicts itself. The implied concern in thorough_plan's wording — "/revise needs to understand the plan's intent" — is addressed by the fact that **`current-plan.md` IS the plan intent**. The plan document, by construction, is the artifact that encodes the intent; if it doesn't, the plan is deficient and the critic should have flagged it. A freshly-spawned `/revise` that reads `current-plan.md` + the latest critic response is strictly better-informed than an inline reviser carrying stale orchestrator chatter. **Resolution:** update thorough_plan/SKILL.md to drop the "invoke in original session context" language; spawn `/revise` as a subagent passing only `(current-plan.md, critic-response-N.md, any files the critic flagged)`. If future experience shows this is insufficient, the right fix is to require `/plan` to emit an explicit `intent.md` handoff artifact — not to revert to inline reviser.

- **E1. Tighten subagent system prompts.** Each subagent re-pays its system prompt input cost. The current SKILL.md files range from 2–4 KB; many contain lengthy "important behaviors" lists that duplicate rules already in `~/.claude/CLAUDE.md` (which is auto-loaded into every session). Removing duplicated content from SKILL.md files and trusting the CLAUDE.md base layer saves one system-prompt-read per subagent spawn. With 4+ spawns per `/thorough_plan` run, this directly offsets the E0 overhead.

- **E2. Parallelize independent reads.** Where the orchestrator needs to read many files before dispatching a subagent (e.g., in `/discover` or `/architect`), fork narrow read-only subagents in parallel rather than reading serially in the main session. Net win when main-context accumulation savings exceed the system-prompt cost per forked agent — usually true for reads across ≥ 3 files. This is the mechanism behind C7 (`/architect` scan phase).

- **E3. Explicit context manifests per subagent.** Each spawned agent should receive an explicit, scoped list of what to read — not a broad instruction like "read the codebase." The orchestrator, having already read the relevant files to decide what to spawn, writes this manifest. This prevents agents from re-discovering files the orchestrator already knows about and from over-reading. Pair with E0 to make the orchestrator a thin coordinator that never accumulates domain knowledge itself.

- **E4. Context-reset on session overflow.** Long `/implement` runs on large plans can fill the context window. When approaching the limit, spawn a summarizer subagent that produces a compact handoff file (`memory/sessions/<date>-<task>-checkpoint.md`), then start a fresh implementation agent from that checkpoint. Today this is ad-hoc; making it explicit in the `/implement` skill prevents silent quality degradation when the context window is nearly full.

### F. Process changes

- **F1. Batch related tasks into one plan.** `/thorough_plan` per individual sub-task amortizes badly. Plan a set of related tasks together; one critic loop covers the lot.
- **F2. Reusable plan templates.** Common task shapes (add an endpoint, add a migration, add a feature flag) can have skeleton plans the planner adapts rather than writes from scratch.

---

## 4. Evaluation: the user's proposal

**Restated:** "Move `/plan` and `/revise` (rounds 1-2) to Sonnet, leave `/critic` on Opus, run up to 4 rounds, with the final round upgrading both `/revise` and `/critic` back to Opus." (The Round 1 version of this restatement said "up to 3 rounds" — Round 3 softens the cap to 4 at the user's direction, to leave room for a genuinely hard task that needs an extra round before the safety net.)

This is essentially **A2 + a partial A3 + B1**, with one regression I'd push back on.

### What's good
- **Critic stays on Opus.** Correct call. The critic is the highest-leverage role per token.
- **Reduces `max_rounds` from 5 to 4.** Captures most of the B1 worst-case savings while leaving one extra round of headroom for hard tasks.
- **Final round is full Opus.** Provides a quality safety net before declaring convergence.
- Conceptually simple — easy to roll out and easy to roll back.

### What I'd push back on
- **"Increase to 3 rounds"** — phrased as a guarantee (always run all 3). Today the loop *can* converge in 1 round and stop. Padding the loop to a fixed 3 rounds eliminates that fast path. If the round-1 plan is already good, paying for two more rounds is pure waste. The fix: keep convergence-driven termination, just lower the cap from 5 to 4. **Same intent, no padding.** (Caveat: I don't know how often plans converge in 1 round in practice. If Stage 0 measurement shows "always ≥ 2," then the fast-path critique loses force — but we should measure, not assume.)
- **Sonnet planner may produce more critic findings → more rounds.** Net cost is unclear without measurement. It is plausible this path *increases* total cost on hard tasks because Sonnet plans require more rounds to converge. Needs a measurement step.
- **No escape valve for trivial tasks** — a 1-task bug fix still pays for orchestration + critic loop. The D-series (triage / single-pass) is missing.
- **No mention of `/architect` or `/review`** — the two Opus-class skills outside the loop. C7 (`/architect` scan/synthesize split) and C4 (diff-only `/review`) aren't in the user's proposal, and `/architect` is the single most expensive skill per invocation.

### Cost sketch — real dollars, real tokens

**Assumptions (clearly illustrative, must be replaced by Stage 0 measurement):**

| Quantity | Value |
|---|---|
| Fresh codebase read (per session, the dominant input line item) | ~40,000 tokens in |
| Lessons-learned + architecture + current-plan combined | ~12,000 tokens in |
| System prompt + CLAUDE.md + skill SKILL.md per spawn | ~6,000 tokens in |
| Plan or revise output (long document) | ~6,000 tokens out |
| Critic output (long document) | ~4,000 tokens out |
| Opus price: ~$15 / M input, ~$75 / M output |  |
| Sonnet price: ~$3 / M input, ~$15 / M output |  |
| Cache-read discount (when the prefix actually hits): 0.1× input price = $1.50 / M on Opus |  |

So one Opus `/plan` round 1 operation costs approximately:
- input: (40k codebase + 12k stable prefix + 6k system) = 58k tokens × $15/M = **$0.87**
- output: 6k × $75/M = **$0.45**
- total: **~$1.32** per Opus `/plan` operation

One Opus `/critic` round 1 operation:
- input: same 58k × $15/M = **$0.87**
- output: 4k × $75/M = **$0.30**
- total: **~$1.17**

#### Today's typical 2-round loop cost (all Opus)

| Step | Input $ | Output $ | Total $ |
|---|---|---|---|
| Orchestrator overhead | 0.09 | 0.15 | 0.24 |
| `/plan` round 1 (Opus) | 0.87 | 0.45 | 1.32 |
| `/critic` round 1 (Opus, fresh) | 0.87 | 0.30 | 1.17 |
| `/revise` round 2 (Opus) | 0.30 | 0.45 | 0.75 |
| `/critic` round 2 (Opus, fresh) | 0.87 | 0.30 | 1.17 |
| **Total** |  |  | **~$4.65** |

#### Proposal A (user's original, Round-3 updated): Sonnet plan/revise for rounds 1–3, Opus critic every round, max 4, convergence-driven

Typical 2-round case:

| Step | Input $ | Output $ | Total $ |
|---|---|---|---|
| Orchestrator overhead | 0.09 | 0.15 | 0.24 |
| `/plan` round 1 (Sonnet) | 0.17 | 0.09 | 0.26 |
| `/critic` round 1 (Opus) | 0.87 | 0.30 | 1.17 |
| `/revise` round 2 (Sonnet) | 0.06 | 0.09 | 0.15 |
| `/critic` round 2 (Opus) | 0.87 | 0.30 | 1.17 |
| **Total** |  |  | **~$2.99** |

**Savings vs today: ~36%.** Most of the saving comes from the Sonnet planner. The critic is untouched — which is why this proposal is *safer* than aggressive Sonnet-everywhere variants. Assumes Sonnet plans don't force extra rounds.

#### Proposal D: today's models unchanged, just add caching where possible

Expected behavior: within a single round, the ~12k stable prefix (lessons-learned + architecture + current-plan) can be a cache read if the same call re-reads it. **Across critic round boundaries, only ~6–8k of that prefix is actually byte-identical** — specifically the system prompt + `CLAUDE.md` + lessons-learned. The `current-plan.md` portion is *not* stable across round boundaries because `/revise` rewrites it between rounds, so a cross-round cache hit cannot include the plan itself. The codebase 40k read is *not* cacheable via system-prompt caching at all (it's tool output); C3-style context handling can skip it on round 2+ but that's a separate lever.

| Step | Input $ | Output $ | Total $ |
|---|---|---|---|
| Orchestrator overhead | 0.09 | 0.15 | 0.24 |
| `/plan` round 1 (Opus, cache write) | 0.87 + 0.05 (write surcharge on 12k) | 0.45 | 1.37 |
| `/critic` round 1 (Opus, cache write on critic's own prefix) | 0.87 | 0.30 | 1.17 |
| `/revise` round 2 (Opus, 12k now cached read) | 0.22 + 0.018 | 0.45 | 0.69 |
| `/critic` round 2 (Opus, 12k cached read from round-1 critic) | 0.80 | 0.30 | 1.10 |
| **Total** |  |  | **~$4.57** |

**Savings vs today: ~1–2%.** Even smaller than I claimed in Round 1. Four reasons:

1. The codebase 40k read is not cacheable via system-prompt caching — it's the content of tool calls.
2. The 12k "stable prefix" is only fully stable *within* a single round. Across critic-round boundaries, only ~6–8k (system prompt + lessons-learned) is byte-identical; `current-plan.md` is rewritten by `/revise` between rounds. The cross-round cache hit is thus smaller than Round 1's math implied.
3. A 90% discount on ~6–8k of the ~58k input bill is ~10% of input, which is ~5–6% of the total call once output at Opus rates is included — and the cache-write surcharge eats some of that back.
4. Subagents do not auto-inherit cache across agents — `/critic` round 2 only caches against `/critic` round 1's own prefix, not against the orchestrator's or `/plan`'s.

C3-style handling (skip lessons-learned re-read on round 2+) adds a small correctness win but not much money. **Proposal D is worth doing only as part of Stage 1's general hygiene, not as a headline "free lunch."**

#### Proposal B: escalation ladder (A3 variant — planner-side tiering, critic stays Opus)

Round 1: `/plan` Sonnet. Round 1 `/critic` Opus (always). If REVISE: round 2 `/revise` Sonnet, round 2 `/critic` Opus. If REVISE again: round 3 `/revise` Sonnet, round 3 `/critic` Opus. If REVISE *again* (the rare hard case): round 4 `/revise` Opus, round 4 `/critic` Opus. Max 4 rounds, convergence-driven. Note: round 3+ never runs a fresh `/plan` — the planner action for every round after 1 is `/revise` against the accumulated plan, because re-running `/plan` from scratch would throw away the round-1–2 work.

Typical 2-round case:

| Step | Input $ | Output $ | Total $ |
|---|---|---|---|
| Orchestrator overhead | 0.09 | 0.15 | 0.24 |
| `/plan` round 1 (Sonnet) | 0.17 | 0.09 | 0.26 |
| `/critic` round 1 (Opus) | 0.87 | 0.30 | 1.17 |
| `/revise` round 2 (Sonnet) | 0.06 | 0.09 | 0.15 |
| `/critic` round 2 (Opus) | 0.87 | 0.30 | 1.17 |
| **Total** |  |  | **~$2.99** |

In the typical 2-round case this matches Proposal A exactly — because the critic is Opus on both rounds and the planner is Sonnet on both rounds. The difference shows up on a hard 3-round run (Proposal B escalates the planner back to Opus on the final round; Proposal A does the same). **Proposal A and Proposal B are effectively equivalent in dollar terms for the typical case.** I retract my Round 1 claim that Proposal B is "strictly better" in cost — it is equivalent; the real advantage is that B has an explicit escalation ladder that makes the behavior on hard tasks legible, while A's "final round is Opus" rule is a fence rather than an escalation.

#### Proposal B + Stage 1 caching hygiene

Same as Proposal B but with the ~2% caching hygiene. **~$2.93, a ~37% saving vs today.** This is what Stage 3 on top of Stage 1 looks like.

### Reading the numbers

- **The dominant lever is the Sonnet planner (Proposal A or B).** ~36% savings on a 2-round case, all from moving `/plan` and `/revise` off Opus.
- **Caching alone is ~2–5% on a short loop.** Not a free lunch; a hygiene item. Worth doing because it's near-zero effort, not because it's a headline number.
- **Caching becomes more valuable on 3+ round loops** where the stable-prefix cache gets more read hits — but 3+ round loops are rare, and B1 (lower `max_rounds`) caps them.
- **The single biggest line item on hard tasks is the fresh codebase re-read per `/critic` round** — which is neither cacheable (tool output) nor safe to skip (C2 was rejected as a blind-spot amplifier). The only way to attack it is B1 (fewer rounds) and better plans up front.
- **`/architect` is not in this table** and is the heaviest single skill. C7 (scan/synthesize split) is the lever there and should be sized separately in Stage 0.

The qualitative conclusion from Round 1 survives: **model tiering is a bigger win than caching.** But I was wrong about *how much bigger* caching was — it's smaller than I initially implied, not larger. Both levers are still worth shipping; neither is a "free lunch." Stage 0 measurement on the user's real runs must replace every number in this section before any irreversible change is made.

---

## 5. Proposed architecture — recommended path

A staged rollout that captures the safe wins first and only takes plan-quality risk after measurement.

**Note on flat-rate plans:** if the user is on Pro/Max (Section 1.0), skip Stage 3 entirely. Stages 0, 1, 2, 4, 5 still apply; Stage 3's value is entirely in dollar savings that don't exist on a flat-rate plan.

### Stage 0 — Measure (prerequisite, not optional)

Without baseline numbers, every other stage is guesswork. Stage 0 produces a single-page cost report for one representative `/thorough_plan` run on a real task.

- Pick one recently-completed feature (any size).
- Re-run `/thorough_plan` against it (or instrument the next real run).
- Capture: tokens in/out per skill invocation, model used, **cache-hit ratio per call** (this is the load-bearing measurement that C1 hinges on), rounds-to-converge.
- Capture: **per-spawn base-prompt cost in this harness** (how many tokens does the system prompt + CLAUDE.md + skill SKILL.md + tool registry add to *each* spawned subagent call). This answers whether E0's per-spawn overhead is small or large, which is the CRIT-1 concern from the Round 1 critic.
- Capture: **whether `/plan` and `/revise` are currently run inline or as subagents in this harness.** (The source files contradict themselves; observation answers the question.)
- Capture: also run Stage 0 on one `/architect` invocation specifically — `/architect` is the heaviest single skill and sizing C7 requires knowing how much of its bill is file-reading vs synthesis.
- Output: `cost-reduction/baseline.md` with a per-skill, per-round cost table plus a caching-and-spawn-overhead appendix.
- **Measurement methodology:** Token counts and cache-hit ratios can be obtained from the Anthropic Console's usage view (console.anthropic.com → Usage) after the run, filtering by timestamp and model to correlate API calls with skill invocations. If running through a proxy or custom client, API response metadata (`usage.input_tokens`, `usage.output_tokens`, `usage.cache_creation_input_tokens`, `usage.cache_read_input_tokens`) provides per-call detail. Claude Code's own session cost display (visible at session end) gives aggregate totals but not per-skill breakdowns — the Console view or API metadata is needed for the per-skill granularity Stage 0 requires.

**This is the de-risking spike.** Every later stage is gated on what Stage 0 reveals. In particular, the Round 1 critic correctly noted that "Stage 3 cannot be safely scoped until Stage 0 answers the harness-behavior questions the document defers" — the bullets above are the list that Stage 0 must answer before Stage 3 is committed.

### Stage 1 — Free-ish wins (caching hygiene + context discipline)

Implements C1 (verified-facts version), C3 (as correctness), C4, C5, C6 — no model changes, no plan-quality risk. Expected savings: **~2–10% on a typical 2-round loop, more on longer loops, more on `/architect` once C5+C7 are rolled out**. Smaller than I initially claimed, but still positive-ROI.

- **C1 audit.** Using the Stage 0 measurement, verify exactly what the harness caches across `/thorough_plan` → `/critic` spawns. Document findings in `cost-reduction/caching-audit.md`. If there are gaps we can influence from SKILL.md (e.g., by making stable prefixes byte-identical across rounds so hash-based caching can hit), apply those changes. Do NOT claim dollar savings until the audit confirms hit rates.
- **C3.** Update [dev-workflow/skills/critic/SKILL.md](dev-workflow/skills/critic/SKILL.md): on rounds ≥ 2, skip the lessons-learned re-read. Framed as correctness hygiene, not a cost lever.
- **C4.** Update [dev-workflow/skills/review/SKILL.md](dev-workflow/skills/review/SKILL.md): read diff first, pull full files only when the diff surfaces a structural concern.
- **C5.** Update [dev-workflow/skills/discover/SKILL.md](dev-workflow/skills/discover/SKILL.md): record `git rev-parse HEAD` per repo; skip repos whose HEAD is unchanged.
- **C6.** Add a "prune lessons-learned" prompt to `/end_of_day` once the file exceeds N entries.
- **C7 — `/architect` scan/synthesize split.** Update [dev-workflow/skills/architect/SKILL.md](dev-workflow/skills/architect/SKILL.md) to: (a) spawn narrow Sonnet read-only subagents for bulk file exploration (one per repo, in parallel), (b) collect structured findings, (c) run the synthesis pass on Opus serially against the findings (not the raw files). This is Stage 1's biggest single lever. Sizing depends on Stage 0's `/architect`-specific measurement.

### Stage 2 — Loop discipline

Implements B1, B3, and the E0 session-isolation fix — risk-free configuration changes, all in [dev-workflow/skills/thorough_plan/SKILL.md](dev-workflow/skills/thorough_plan/SKILL.md).

- **E0 prerequisite fix.** Update `thorough_plan/SKILL.md` to remove the "Invoke in the original session context (it needs to understand the plan's intent)" instruction for `/revise` (line 63). Replace with: "Spawn `/revise` as its own agent, passing only `(current-plan.md, critic-response-N.md, any files the critic flagged)`." This resolves the source-file contradiction between `thorough_plan/SKILL.md` (says inline) and `revise/SKILL.md` (says fresh session). The fix is independent of Stage 3's model tiering — it is a session-isolation correctness change that ships early. See Section 3, E0 for the full rationale.

- **B1.** Lower default `max_rounds` in [dev-workflow/skills/thorough_plan/SKILL.md](dev-workflow/skills/thorough_plan/SKILL.md) from 5 → 4. Convergence-driven termination is preserved — the loop still stops early when a round returns PASS. The one-round reduction trims the worst-case tail without foreclosing a genuinely hard 4-round task.

  **Inline `max_rounds: N` override (Stage-2–native escape hatch — MAJ-1 fix).** To honor the "override remains available" promise *without* depending on Stage 3's `strict:` protocol, `/thorough_plan`'s SKILL.md gains a one-paragraph parsing rule: before starting the loop, scan the user's task description for the literal pattern `max_rounds: N` (where N is a positive integer, case-insensitive, anywhere in the description). If found, the orchestrator uses that N as the cap for this run (strip the token from the description before invoking `/plan`). If not found, use the default (4). Example: `/thorough_plan max_rounds: 6 this migration is gnarly, give it room`. This is a handful of lines in `/thorough_plan/SKILL.md` — no new skill files, no two-file infrastructure, no dependency on Stage 3. Stage 2 ships independently with a working user-facing override; if Stage 3 also ships later, the `strict:` protocol coexists (a `strict:`-prefixed run also defaults max_rounds to 5, which the user can still override upward via `max_rounds: N`).

- **B3.** Tighten the loop-detection clause: if round N's critic flags the same top-level issue category as round N−1, escalate to the user with the diff and ask whether to continue.

### Stage 3 — Planner-side model tiering (Proposal A, revised)

The model-swap risk, gated on Stage 0 baseline + Stages 1–2 in production for at least one real task. **Critic stays on Opus every round** — this preserves Section 1.1's "critic is the highest-leverage role" constraint, which Round 1's version of this stage violated.

- Update `/thorough_plan` to invoke `/plan` (round 1 only) and `/revise` (rounds 2 and 3) on Sonnet by default.
- **Round 4 (final allowed):** `/revise` escalates to Opus. Note: round 4 never runs a fresh `/plan` — the round-1 plan carries forward and `/revise` updates it. Re-running `/plan` from scratch in a late round would discard the accumulated work; the loop's semantics are "one `/plan`, many `/revise`s," not "fresh `/plan` every round."
- `/critic` stays on Opus for every round. Never tiered.
- Convergence-driven termination — cap lowered from 5 to 4, don't pad to a fixed round count. (The same inline `max_rounds: N` override introduced in Stage 2 continues to work in Stage 3; `strict:` mode defaults the cap to 5, overridable by `max_rounds: N` as usual — `max_rounds: N` is always the single cap-control mechanism; `strict:` controls model selection only.)

**"strict mode" escape hatch (concrete protocol — MAJ-7 fix):**

Skills take user prompts, not CLI flags, so the escape hatch must be a prompt convention. The rule: **if the user's `/thorough_plan` invocation begins with the literal token `strict:` (case-insensitive), the orchestrator forces all-Opus for every role and defaults `max_rounds` to 5** (the user can still raise or lower the cap via `max_rounds: N` in the same invocation). Example: `/thorough_plan strict: handle the auth migration carefully`. `/thorough_plan` parses the leading `strict:` token, sets the "strict mode" flag, strips the token from the task description, and proceeds. If the token is not present, the default tiered behavior applies.

**Per-round model tiering mechanism (MAJ-8 fix):**

SKILL.md frontmatter pins one `model:` per skill file. There is no documented mechanism in this workflow for "spawn `/plan` on Sonnet for round 1, Opus for round 3" from a single skill file. The concrete approach is **two skill files per tiered role**:

- [dev-workflow/skills/plan/SKILL.md](dev-workflow/skills/plan/SKILL.md) — `model: opus` (the existing file, unchanged in content; used only when `strict:` mode forces Opus on round 1, which is rare — round 1 is the one round that runs `/plan` rather than `/revise`, and in default tiered mode it uses `/plan-fast`).
- `dev-workflow/skills/plan-fast/SKILL.md` — new file, `model: sonnet`. Body is a content copy of `plan/SKILL.md` with the model frontmatter changed to `model: sonnet`. Used for round 1 in default tiered mode.
- [dev-workflow/skills/revise/SKILL.md](dev-workflow/skills/revise/SKILL.md) — `model: opus` (the existing file). Used for round 4 (the final allowed round) and for strict-mode runs of every round.
- `dev-workflow/skills/revise-fast/SKILL.md` — new file, `model: sonnet`. Used for rounds 2 and 3 in default tiered mode.
- `/thorough_plan` selects which skill to spawn based on (round number, strict flag). The selection rule is: strict mode → always Opus variant; non-strict → `/plan-fast` for round 1, `/revise-fast` for rounds 2 and 3, `/revise` (Opus) for round 4.
- `/critic` is not split — always Opus, always the existing skill file.

This is explicit infrastructure that does not exist today and must be created as part of Stage 3's implementation. The Round 1 critic was correct that Round 1's description glossed over this — it is not a one-line config change, it is a new skill file per tiered role plus orchestrator changes.

**Why not tier the critic:** Section 1.1 says "the critic is the highest-leverage role per token." Section 3.A says "moving the critic off Opus is the biggest quality risk in the whole design space." Round 1 of this document then contradicted both by putting the round-1 critic on Sonnet in Stage 3. The Round 1 critic was correct to flag this as incoherent. Stage 3 reverts to "critic is always Opus"; the user's original Proposal A was right about this. If the team later decides they want to try a Sonnet round-1 critic to capture more savings, that is a separate future stage that should be explicitly labeled "Stage 3b — risky critic tiering experiment" and gated on its own measurement, not smuggled into the main rollout.

### Stage 4 — Task triage and shortcut paths

Implements D1, D2, D3 once Stages 0-3 are in production and there's confidence in the cheap defaults.

- Add a "task profile" prompt at the top of `/thorough_plan`: Small / Medium / Large.
- Small → `/plan` (Sonnet) + `/implement` + `/review` (Sonnet, smoke gate). No critic loop.
- Medium → Stage-3 escalation (Sonnet planners, Opus critic, max 4, convergence-driven).
- Large → `strict:` mode (all Opus, max 5).
- Document the triage criteria in [dev-workflow/CLAUDE.md](dev-workflow/CLAUDE.md).
- **Update `dev-workflow/CLAUDE.md`'s workflow sequence section** to reflect that Small-profile tasks use `/plan` → `/implement` → `/review` without `/thorough_plan`. Today CLAUDE.md says small tasks "can skip `/architect` and go straight to `/thorough_plan`" — Stage 4's Small profile skips `/thorough_plan` entirely, which is a meaningful change to the stated workflow. Without this update, CLAUDE.md and the triage profiles would contradict each other.

### Stage 5 — Haiku for state-management skills (A4)

Lowest priority because Sonnet state skills are already cheap; the absolute savings are small.

- Move `/start_of_day`, `/end_of_day`, `/capture_insight`, `/weekly_review` to Haiku.
- Keep `/gate`, `/rollback`, `/end_of_task` on Sonnet (more reasoning / more safety-critical).
- Validate by running each skill on Haiku for a week and comparing output quality to the Sonnet version.

---

## 6. Integration analysis

Each stage modifies one or more `SKILL.md` files. The integrations to worry about:

| Change | Affects | Failure mode | Mitigation |
|---|---|---|---|
| C1 caching audit + hints | All loop skills | Cache miss → silent cost regression (or no regression, just no win) | Stage 0 baseline establishes hit-rate floor; post-Stage-1 re-measurement confirms direction |
| C3 skip lessons-learned mid-loop | `/critic`, `/revise` | None — lessons can't change mid-loop | None needed |
| C4 diff-only review | `/review` | Reviewer misses a structural bug hidden outside the diff | Keep the "pull full file on structural concern" fallback; `/review` is still Opus |
| C7 `/architect` scan/synthesize split | `/architect` | Scan subagents miss something a unified Opus pass would have caught | Synthesize pass can request a targeted re-scan of a specific repo; gated on Stage 0 `/architect` measurement |
| B1 max_rounds 5→4 | `/thorough_plan` | Hard tasks don't converge in 4 rounds | Escalate to user at cap; inline `max_rounds: N` override lifts the cap per-run (Stage 2); `strict:` prefix raises to 5 (Stage 3) |
| B3 tighter loop detection | `/thorough_plan` | False positive — escalates to user when round would have converged | Cost of a false positive is one user prompt; cheap |
| E0 session-isolation fix (Stage 2) | `/thorough_plan`, `/revise` | `/revise` in a fresh session loses context the inline version had (mitigated: `current-plan.md` IS the plan intent — see E0) | Ships in Stage 2 as a correctness fix; if quality degrades, revert the line change in `thorough_plan/SKILL.md` |
| E0 full subagent isolation (Stage 3) | `/thorough_plan`, `/plan`, `/revise` | Per-spawn overhead eats the Stage-3 savings (CRIT-1 from Round 1 critic) | Stage 0 measurement sizes per-spawn cost before Stage 3 commits; E1 (tighten SKILL.md) offsets |
| Stage 3 planner tiering via two-skill mechanism | `/plan`, `/plan-fast`, `/revise`, `/revise-fast`, `/thorough_plan` | Sonnet plans force more rounds → net cost neutral or worse; two-skill-file drift | Stage 0 baseline + post-rollout measurement; `strict:` escape hatch; add a CI/lint rule that the -fast variant stays in content-sync with the Opus version |
| Stage 3 `strict:` prefix protocol | `/thorough_plan` | User forgets prefix on a high-stakes task → gets cheap path silently | Document in QUICKSTART; triage prompt (Stage 4) asks explicitly |
| Stage 4 task triage | `/thorough_plan` | Wrong size classification → wrong profile | User confirms classification at the start of each task |
| Stage 5 Haiku for state skills | `/end_of_day`, `/start_of_day`, etc. | Output quality regression | Side-by-side comparison for one week before committing |

The most fragile change is **Stage 3** (model tiering — new two-skill infrastructure plus unverified plan-quality assumptions). The most likely to be a quality win is **Stage 1's C7** (`/architect` split). Ordering respects both: measurement first, safe edits before risky edits, Stage 3 last among the quality-risky items.

---

## 7. Risk register

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Sonnet planner produces lower-quality plans → critic finds more issues → loop runs longer → net cost is **higher** than today | Medium | High | Stage 0 baseline before Stage 3; post-Stage-3 re-measurement; `strict:` escape hatch |
| R2 | Caching gives smaller savings than expected because the harness doesn't actually cache across subagent boundaries (or does in a way we can't influence) | **High** (now the expected case given Anthropic docs) | Low (positive — our expectation is already set low) | Stage 0 audit establishes the real baseline; Stage 1 only claims savings it measures |
| R3 | (Was: reduced critic context causes missed bug. C2 was dropped — risk no longer applies to the plan) | N/A | N/A | N/A |
| R4 | `max_rounds` 5→4 causes some hard plans to ship un-converged | Low | Medium | Loop already escalates to the user at the cap; `/review` catches issues; inline `max_rounds: N` override (Stage 2) lifts the cap per-run; `strict:` (Stage 3) raises the cap to 5 |
| R5 | Task triage misclassifies a Large task as Small → no critic loop → bug ships | Medium | High | User confirms classification; Medium is the safe default; `/review` safety net |
| R6 | Haiku for state skills produces lower-quality daily caches → context loss across sessions | Low | Medium | One-week side-by-side validation before committing |
| R7 | (Was: workflow drift between source and `~/.claude/skills/`. This is a general workflow concern, not specific to cost reduction. Tracked elsewhere.) | N/A | N/A | N/A |
| R8 | **E0's per-spawn base-prompt overhead exceeds the Stage-3 model-tiering savings** (the CRIT-1 concern — "spawning four subagents per run pays 4× base-prompt overhead, which can plausibly exceed the inline savings on short tasks") | Medium | Medium | Stage 0 measures per-spawn cost; E1 (tighten SKILL.md to remove duplication with CLAUDE.md) mitigates; if measurement shows net negative, fall back to keeping `/plan` and `/revise` inline and achieve tiering a different way (e.g., a single `/thorough_plan` that reads an env var and branches model selection) |
| R9 | **Two-skill-file drift between `/plan` and `/plan-fast`.** Over time the fast variant lags the Opus version in content updates, producing silently worse plans | Medium | Medium | CI/lint rule that diffs `/plan-fast/SKILL.md` against `/plan/SKILL.md` on commit and fails if they diverge beyond the model frontmatter line; documented in dev-workflow README |

---

## 8. De-risking strategy

1. **Measure before changing.** Stage 0 is non-negotiable. Without it, every cost claim in this document is a guess. The Round 1 critic was right that Stage 0 must answer harness-behavior questions (per-spawn overhead, current caching behavior, current inline-vs-subagent status for `/plan`/`/revise`) before any later stage is safely scoped.
2. **Stage the rollout.** Caching hygiene + `/architect` split + loop discipline before risky model tiering. Each stage validated on one real task before moving on.
3. **Keep escape hatches.** `strict:` prefix (force Opus everywhere), `max_rounds` override, manual triage override. The defaults get cheaper; the maximums stay available.
4. **`/review` is the second safety net.** Whatever the planner loop misses, the `/review` step (still on Opus, still full plan) is supposed to catch. Cost optimizations of the planner loop are partially insured by leaving `/review` strong.
5. **Re-measure after each stage.** Cost should drop monotonically. If it doesn't, the stage is rolled back.
6. **For Stage 3 specifically:** before committing the two-skill-file infrastructure, prototype the smallest version — one `/plan-fast` file that is a content-sync copy of `/plan` with the model pinned to Sonnet, and `/thorough_plan` branching on round number. Run it once, compare plan quality end-to-end against an all-Opus run on the same task. Only commit to the rollout if the comparison passes a human sanity check.

---

## 9. Stage Summary Table

| Stage | Description | Complexity | Dependencies | Key Risk |
|-------|-------------|-----------|--------------|----------|
| 0 | Measure baseline cost on one real `/thorough_plan` run AND one `/architect` run; answer harness-behavior questions (per-spawn overhead, actual caching, inline-vs-subagent today); produce `cost-reduction/baseline.md` | S | None | None — pure measurement |
| 1 | Caching audit + hygiene (C1), context discipline (C3, C4, C5, C6), `/architect` scan/synthesize split (C7) | M-L (C7 alone is M-L — real new subagent infra in `/architect`; consider splitting into 1a = C1/C3/C4/C5/C6 hygiene and 1b = C7 `/architect` split if planning shows the combined scope is too large) | Stage 0 | C7 missing something a unified pass would catch (mitigated: targeted re-scan) |
| 2 | Loop discipline + `/revise` session-isolation fix: max_rounds 5→4, inline `max_rounds: N` override, tighter loop detection (B1, B3), E0 prerequisite fix (drop inline `/revise` instruction from `thorough_plan/SKILL.md`) | S | Stage 0 | Hard plans don't converge in 4 rounds (mitigated: inline override; `strict:` when Stage 3 ships); `/revise` quality regression from fresh session (mitigated: `current-plan.md` is the plan intent) |
| 3 | Planner-side model tiering via two-skill-file mechanism (`/plan` + `/plan-fast`, `/revise` + `/revise-fast`), critic stays all-Opus, `strict:` escape hatch, convergence-driven max-4 | M-L | Stages 0, 1, 2 in prod for ≥ 1 task; Stage 0 must have sized E0/E1 spawn overhead | Sonnet plans slow convergence (R1); per-spawn overhead eats savings (R8); two-skill-file drift (R9) |
| 4 | Task triage — Small/Medium/Large profiles, single-pass mode for Small | M | Stage 3 stable | Misclassification (R5) |
| 5 | Haiku for low-risk state skills (A4) | S | None hard, but lowest priority | Output quality regression (R6) |

---

## 10. Next Steps

**Ready for `/thorough_plan` in this order:**

1. **Stage 0 — Baseline measurement.** Tiny scope, high information value. Plan this first; it informs every subsequent stage. Scope must include the harness-behavior questions (per-spawn overhead, actual caching, current inline-vs-subagent status) and a separate `/architect` measurement pass.
2. **Stage 1 — Caching hygiene + `/architect` split + context discipline.** The biggest expected win now sits in C7 (`/architect` scan/synthesize), not C1 (caching). Worth a dedicated `/thorough_plan`.
3. **Stage 2 — Loop discipline.** Small enough to bundle into Stage 1's plan or to do as a quick standalone `/plan` (no critic loop needed for a config change).

**Wait on:**

- **Stage 3 (model tiering)** until Stage 0 numbers exist, Stages 1–2 have shipped, and the E0/E1 spawn-overhead numbers confirm the direction. Also wait on a Stage-3 prototype pass comparing plan quality end-to-end before committing the two-skill-file infrastructure.
- **Stage 4 (task triage)** until Stage 3 is stable.
- **Stage 5 (Haiku for state skills)** is independent — schedule whenever convenient.

**Open questions for the user (Q1 is load-bearing for this whole document):**

1. **Billing plan.** Already promoted to Section 1.0 as the gate. The user must confirm metered API vs flat-rate Pro/Max; the answer decides whether Stage 3 and Section 4 apply at all.
2. **`strict:` prefix protocol on `/thorough_plan` vs up-front task triage via Stage 4** — is the one-word prefix acceptable as the interim escape hatch, or do you want Stage 4 (triage prompt) pulled forward ahead of Stage 3?
3. **Plan-quality regression tolerance.** "Same quality, cheaper" is Stage 1. "Slightly noisier planners on early rounds, same critic quality" is Stage 3. "Skip the critic loop entirely for trivial tasks" is Stage 4. Which are in scope?

---

## Caveats

- This `/architect` session ran on **Sonnet 4.6**, not Opus. The skill specifies Opus. The Round 1 critic's primary concern (CRIT-1: subagent-economics and per-spawn-overhead reasoning in E0) has now been reviewed across three rounds of Opus critique, validating the direction: E0 is correctly framed as a quality/enabling lever (not a direct cost win), and Stage 0 gates the empirical per-spawn overhead measurement before Stage 3 commits. The conceptual direction is Opus-validated; the remaining caveat is that no empirical measurement exists yet — Stage 0 must still confirm the numbers before any irreversible infrastructure (two-skill files, subagent spawning changes) is built.
- All cost numbers in Section 4 are **illustrative**, not measured. Stage 0 exists precisely to replace them with real numbers before any risky change is made. The token-count assumptions (40k codebase, 12k stable prefix, 6k system) are rough estimates that will be wrong in specific directions for specific runs.
- Whether Claude Code already does prompt caching across orchestrator → subagent boundaries is **unknown from inside the harness**. Verified Anthropic documentation (April 2026) says subagents do NOT automatically inherit parent-cache; whether the Claude Code harness does anything clever on top of that is what Stage 0's C1 audit is for. The Round 1 architecture optimistically assumed a ~90% caching discount across the entire loop; Round 2 corrects this to a more realistic ~2–10% based on the actual cacheable-prefix surface.
- The **source files for `/revise` contradict each other** ([dev-workflow/skills/thorough_plan/SKILL.md](dev-workflow/skills/thorough_plan/SKILL.md) says inline; [dev-workflow/skills/revise/SKILL.md](dev-workflow/skills/revise/SKILL.md) says fresh session). This is now assigned to **Stage 2** as a prerequisite fix: remove the inline instruction from `thorough_plan/SKILL.md` and spawn `/revise` as a fresh subagent, treating `current-plan.md` as the plan intent (see E0 for the full rationale). Shipping this in Stage 2 means it lands early and doesn't wait for Stage 3's riskier model-tiering changes.
- **Section 4's table is a model, not a measurement.** Even after the Round 2 rewrite using real dollar figures, it is built on illustrative assumptions. Replace with Stage 0 output before making decisions that matter.

---

## Revision history

### Round 2 — 2026-04-11

**Critic verdict (Round 1):** REVISE (4 CRITICAL, 8 MAJOR, 8 MINOR — fresh Opus session)

**CRITICAL issues addressed:**

- **[CRIT-1]** E0 economics rewritten. The claim that subagent isolation is a direct token-cost win was retracted — per Anthropic docs, subagents do not auto-inherit parent cache and pay full base-prompt cost per spawn. E0 is now framed as a **quality lever** (fresh planner context) and an **enabling architecture** (required for Stage 3's per-round model tiering), not as a cost saving on its own. Stage 0 must size per-spawn overhead explicitly before Stage 3 commits. Added R8 to the risk register to make the failure mode explicit.
- **[CRIT-2]** The `/revise` source-file contradiction (thorough_plan says inline, revise/SKILL.md says fresh session) is now acknowledged directly in E0 and in Caveats. The recommendation engages with the "revise needs plan intent" rationale by arguing **`current-plan.md` IS the plan intent** — a fresh `/revise` that reads the plan is strictly better-informed than an inline reviser carrying orchestrator chatter. If future experience shows this insufficient, the escalation is an explicit `intent.md` artifact, not a return to inline reviser.
- **[CRIT-3]** Section 4 cost table completely rewritten with **real dollar figures** based on token counts, input/output split, and the verified Anthropic price ratios. Caching's savings dropped from the original "~40%" claim to a realistic **~2–10%** because (a) codebase tool-call reads aren't cacheable via system-prompt caching, (b) the stable prefix is ~20% of input, (c) subagent cache doesn't auto-propagate. The qualitative ranking (model tiering > caching) survives; the specific percentages changed substantially. The original "Proposal D is a free lunch" framing is retracted.
- **[CRIT-4]** Stage 3 reverted so that **`/critic` stays on Opus on every round**, preserving Section 1.1's "critic is the highest-leverage role" constraint. Round 1's Stage 3 had quietly demoted the round-1 critic to Sonnet, contradicting Section 1. The user's original Proposal A was correct about this; the rollout now matches. If a future team wants to experiment with a Sonnet round-1 critic, that is a separate Stage 3b and must be gated on its own measurement.

**MAJOR issues addressed:**

- **[MAJ-1]** Flat-rate billing promoted from Open Question #1 to **Section 1.0 — "Billing-plan gate"**, with an explicit alternate framing for the Pro/Max case. Most of Section 4 and Stage 3 become inapplicable on a flat-rate plan; Section 1.0 says so directly.
- **[MAJ-2]** C1 rewritten with **verified Anthropic prompt-caching facts** (fetched from platform.claude.com docs): 5-min/1-hour TTL, cache_control client-side-only, 100% byte-identical prefix requirement, 0.1× read discount, 1.25× write surcharge, ~4096-token minimum for Opus 4, no auto-inheritance across subagents. C1's claimed ceiling dropped from "up to ~90%" to a realistic **~15–25% of stable-prefix input, translating to ~2–10% of the whole loop bill**.
- **[MAJ-3]** C2 ("targeted critic on rounds 2+") dropped entirely. The Round 1 critic was correct that this is a blind-spot amplifier — round 2 by construction never sees files round 1 missed. Documented the rejection in the C-series. The savings goal is now served by caching where possible and by B1 (lower `max_rounds`).
- **[MAJ-4]** B2 ("PASS if only MAJORs remain because /review will catch them") dropped, with an explicit "until Stage 0 shows /review catches the same issue classes, no rule change" revisit trigger.
- **[MAJ-5]** C3 reframed as a **correctness/hygiene item**, not a headline cost lever. Lessons-learned is a few KB; the value is "don't re-pay for content that can't have changed," not meaningful money.
- **[MAJ-6]** Added **C7** — `/architect`-specific scan/synthesize split — as a lever in Stage 1. `/architect` is now called out in Section 2.1 as the single heaviest skill per invocation, in Section 2.3 as an exception to the three-biggest-cost-drivers frame, and in Stage 0 as a separate measurement target.
- **[MAJ-7]** `--strict` replaced with a concrete `strict:` prefix protocol: if the user's `/thorough_plan` invocation begins with the literal token `strict:` (case-insensitive), the orchestrator forces all-Opus and `max_rounds = 5`. Documented in Stage 3.
- **[MAJ-8]** Stage 3's per-round model tiering mechanism specified concretely as **two skill files per tiered role** (`/plan` + `/plan-fast`, `/revise` + `/revise-fast`), with `/thorough_plan` selecting by round number and strict-mode flag. Added R9 to the risk register for two-skill-file drift, and added a pre-commit CI/lint-rule mitigation.

**MINOR issues addressed:**

- **[MIN-1]** Section 2.2 now includes an **orchestrator row** in the loop economics table and calls out that the orchestrator pays its own per-round cost.
- **[MIN-3]** Caveats now specifically names **CRIT-1** as the item most in need of an Opus re-validation, not just "Stage 3" generically.
- **[MIN-4]** R7 ("workflow drift between source and `~/.claude/skills/`") marked as a general workflow concern, not specific to cost reduction; removed as active risk in this document.
- **[MIN-7]** `/review` is now covered by **C4** in Stage 1 (diff-only review with full-file fallback). Previously C4 was listed in Section 3 and then dropped from the stages; it is now back.
- **[MIN-8]** Stage 5 heading corrected: **"Haiku for state-management skills (A4)"** (previously said "Sonnet" in the heading but Haiku in the body).

**MINOR issues noted but deferred:**

- **[MIN-2]** Inline link-with-line-range syntax (`[file](file#L54-L58)`) — partially cleaned up (removed from a few places), not globally. Low-value cosmetic.
- **[MIN-5]** Anthropic pricing date-stamp. Captured in Section 2.1 ("Anthropic API list, April 2026 — confirm at time of rollout") but not in the Section 4 table headers. The table is entirely illustrative anyway; Stage 0 replaces it.
- **[MIN-6]** "How often does convergence-in-1 actually happen?" — acknowledged in Section 4 as an assumption Stage 0 must answer, not resolved in this document.

**Changes summary:** The Round 1 document was directionally right but got two big things wrong — it overclaimed caching's impact (CRIT-3, MAJ-2) and it built an incoherent critic-tiering story into Stage 3 (CRIT-4). Round 2 grounds the caching claims in verified Anthropic facts (caching is now a hygiene item, not a headline lever), reverts Stage 3 to a critic-stays-Opus design matching the user's original Proposal A, reframes E0 as a quality/enabling lever with real per-spawn overhead sized by Stage 0, adds C7 for the `/architect` blind spot, and promotes the flat-rate billing gate to Section 1.0 so the whole document is correctly scoped. Net effect: the rollout is less optimistic, more grounded, and more explicit about what Stage 0 must answer before any irreversible change.

### Round 3 — 2026-04-11

**Critic verdict (Round 2):** REVISE (0 CRITICAL, 1 MAJOR, 5 MINOR — fresh Opus session)

**User direction this round:** "we can avoid lowering to 3 max rounds, may do more if needed up to 4" — the cap lowers from 5 to 4 instead of 5 to 3. This softens (but does not eliminate) MAJ-1's gap-window concern, because a 4-round cap leaves more headroom for a genuinely hard task before the override hatch is even needed.

**MAJOR issue addressed:**

- **[MAJ-1]** Stage 2 now ships its own user-facing override *without* depending on Stage 3. The chosen fix is Round 2 critic's Option (a): `/thorough_plan`'s SKILL.md gains a simple parsing rule — if the task description contains `max_rounds: N` anywhere, use that as the cap (strip the token before invoking `/plan`). This is a few lines of logic in one file, no new skill files, no dependency on Stage 3's two-skill-file infrastructure. Stage 2 is now genuinely independently deployable with a working escape hatch. Stage 3's `strict:` protocol continues to coexist for the "all-Opus, max 5" case. The integration-analysis table and R4 mitigation were updated to reflect the new override path.

**MINOR issues addressed:**

- **[MIN-1]** Section 3.C TTL bullet corrected: heavy `/thorough_plan` runs can take 30–60+ minutes, so the 5-minute default TTL may expire between rounds and silently turn cache writes into wasted surcharge. Whether the harness uses the 1-hour TTL is unknown from inside the harness. Stage 0's C1 audit now explicitly must check (a) which TTL the harness sets and (b) whether cross-round cache-hit rates are actually non-zero on real runs.
- **[MIN-2]** Proposal D math corrected in two places. Section 4's Proposal D explanation now says the byte-identical cross-round prefix is ~6–8k (system prompt + lessons-learned), not the full 12k, because `current-plan.md` is rewritten by `/revise` between rounds. The "Savings vs today" breakdown bullets were updated from 3 reasons to 4, and the headline savings dropped from "~2%" to "~1–2%" to reflect the smaller cacheable surface.
- **[MIN-3]** Round 3 / late-round terminology fixed in both Proposal B (Section 4) and Stage 3 (Section 5). Late rounds run `/revise` only — they do NOT re-run `/plan` from scratch, because that would discard the accumulated plan. Proposal B's escalation ladder and Stage 3's round-4 description now say `/revise` (not `/plan`/`/revise`). The two-skill-file mechanism section was updated to note that `/plan-fast` is only used in round 1 (the one round that runs `/plan`), while `/revise-fast` is used in rounds 2–3.
- **[MIN-4]** Stage 1's complexity rating in the Stage Summary Table changed from "M" to "M-L", with a parenthetical noting that C7 alone is M-L and Stage 1 can be split into 1a (hygiene: C1/C3/C4/C5/C6) and 1b (`/architect` split: C7) if combined scope proves too large during Stage 1's `/thorough_plan`.
- **[MIN-5]** Section 1.0's flat-rate bullet corrected: Stage 1's caching hygiene produces ~2% token savings, far too small to meaningfully move Pro/Max rate limits. The honest framing for flat-rate plans is latency and context-window pressure (C7), not rate-limit headroom.

**User instruction rippled through:**

- Section 3.B1: "5 → 3" → "5 → 4".
- Section 4 Proposal A restated text: "up to 3 rounds" → "up to 4 rounds" (plus a note that round-3+ planners are `/revise`, not `/plan`).
- Section 4 "What's good" bullet on Proposal A: "5 to 3" → "5 to 4".
- Section 4 "What I'd push back on": "5 to 3" → "5 to 4".
- Section 5 Stage 2: default cap 5 → 4, plus the new inline `max_rounds: N` override paragraph.
- Section 5 Stage 3: default cap 5 → 4; round 4 is the final allowed round; `/plan` runs only in round 1 (`/plan-fast` by default, `/plan` under strict); `/revise-fast` covers rounds 2–3; Opus `/revise` covers round 4 and strict-mode runs.
- Section 5 Stage 4 (triage): Medium profile's "max 3" → "max 4".
- Section 6 integration-analysis table: B1 row updated to "5→4" and the mitigation now names the inline-override and `strict:` escape hatches.
- Section 7 R4: updated cap from 5→3 to 5→4; mitigation now includes the inline override.
- Section 9 Stage Summary Table: Stage 1 complexity "M" → "M-L" (MIN-4 fix); Stage 2 description gains "inline `max_rounds: N` override"; Stage 3 description gains "convergence-driven max-4".

**Issues noted but deferred:** None from Round 2 — all 1 MAJOR + 5 MINORs were addressed.

**Changes summary:** Round 3 is surgical, not structural. The user's direction to cap at 4 (not 3) plus the Round 2 critic's MAJ-1 together drove a Stage-2 override mechanism that is now truly independent of Stage 3. All 5 Round-2 minors were corrected in place: TTL claim, Proposal D math, round-3 "/plan vs /revise" terminology (both locations), Stage 1 complexity rating, and the flat-rate caching framing. The architecture's shape and recommended stages are unchanged; the numbers and mechanisms are now honest and internally consistent.

### Round 4 — 2026-04-12

**Critic verdict (Round 3):** REVISE (0 CRITICAL, 1 MAJOR, 5 MINOR — fresh session)

**MAJOR issue addressed:**

- **[MAJ-1]** The `thorough_plan/SKILL.md:63` inline-revise fix (E0's recommendation to drop "invoke in original session context" and spawn `/revise` as a subagent) was described in E0 but not assigned to any stage. Now explicitly assigned to **Stage 2** as a prerequisite fix, since Stage 2 already touches `thorough_plan/SKILL.md` for the `max_rounds` change. This decouples the session-isolation correctness fix from Stage 3's riskier model-tiering changes, shipping it earlier. Updated: Stage 2 description, integration-analysis table (new E0 session-isolation row), Stage Summary Table, and the `/revise` contradiction Caveats bullet.

**MINOR issues addressed:**

- **[MIN-1]** `strict:` "unconditionally" wording fixed. Stage 3's convergence line now says "`strict:` mode defaults the cap to 5, overridable by `max_rounds: N` as usual." The `strict:` protocol description now says `strict:` "defaults `max_rounds` to 5 (the user can still raise or lower the cap via `max_rounds: N`)." `max_rounds: N` is now the single cap-control mechanism throughout; `strict:` controls model selection only.
- **[MIN-2]** Caveats section updated: the "most needing Opus re-validation" note for CRIT-1 is replaced with an acknowledgment that E0's direction has been validated across three Opus critic rounds. The remaining caveat is empirical: Stage 0 must still confirm per-spawn overhead numbers before Stage 3 commits.
- **[MIN-3]** Stage 0 gains a **measurement methodology** paragraph: token counts and cache-hit ratios from Anthropic Console usage view or API response metadata (`usage.input_tokens`, `usage.cache_read_input_tokens`, etc.); Claude Code's session cost display gives aggregates but not per-skill breakdowns.
- **[MIN-4]** `plan-fast` "sources the Opus version's content" language replaced with "content copy of `plan/SKILL.md` with the model frontmatter changed to `model: sonnet`." R9's mitigation updated to match: "CI/lint rule that diffs `/plan-fast/SKILL.md` against `/plan/SKILL.md` on commit and fails if they diverge beyond the model frontmatter line."
- **[MIN-5]** Stage 4 gains an explicit bullet: "Update `dev-workflow/CLAUDE.md`'s workflow sequence section to reflect that Small-profile tasks skip `/thorough_plan`." Notes the contradiction between CLAUDE.md's current "small tasks go to `/thorough_plan`" and Stage 4's "Small → no critic loop."

**Issues noted but deferred:** None — all 1 MAJOR + 5 MINORs were addressed.

**Changes summary:** Round 4 is the smallest revision yet: one structural change (E0 fix moved from unassigned to Stage 2) and five wording/completeness fixes. The architecture's shape, staging order, and cost analysis are unchanged. The document is now internally consistent on all cross-references checked by the Round 3 critic.
