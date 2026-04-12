# Stage 1 Implementation Plan — Caching Hygiene + Context Discipline + /architect Scan/Synthesize Split

**Date:** 2026-04-12
**Task folder:** `cost-reduction/stage-1-caching/`
**Parent architecture:** `cost-reduction/architecture.md` (Round 4, 2026-04-12)
**Stage 0 reference:** `cost-reduction/stage-0-measure/instrumentation-notes.md`


## Convergence Summary
- **Rounds:** 2
- **Final verdict:** PASS
- **Key revisions:** Round 1 critic found 2 MAJOR issues: (1) incorrect line-number references in Task 6 (C7 architect rewrite) — fixed by removing all line numbers and using section heading names as locators; (2) misleading "Phase 1b" naming in the architect split — fixed by folding web research into Phase 2 (Synthesize). All 6 MINOR issues (insertion point, raw session output path, entry counting, output size constraint, cost discipline wording, implementation note) were also addressed.
- **Remaining concerns:** 2 MINOR style issues noted in Round 2 (slight line-number imprecision in Task 3, nonstandard markdown structure in Task 4) — neither blocking.
---

## Executive summary

Stage 1 implements the "free-ish wins" from the cost-reduction architecture: caching hygiene, context discipline, and the `/architect` scan/synthesize split. No model changes, no plan-quality risk. Six levers (C1, C3, C4, C5, C6, C7), each modifying one or two SKILL.md files.

**Recommendation: split into 1a and 1b.** The architecture notes Stage 1 complexity as M-L and suggests the split. After reading all SKILL.md files and analyzing the changes, the split is justified:

- **Stage 1a (hygiene): C1, C3, C4, C5, C6.** Five small, independent edits to five SKILL.md files. Each is a few lines of text change. Low risk, fast to implement, easy to review. Complexity: S.
- **Stage 1b (architect split): C7.** A significant rewrite of `/architect`'s SKILL.md, introducing new subagent orchestration patterns. Requires careful design and testing. Complexity: M.

The split lets 1a ship immediately after this plan converges while 1b gets its own more careful implementation pass. The two are independent — 1b does not depend on 1a.

---

## Stage 0 findings that shape this plan

| Finding | Impact on Stage 1 |
|---------|-------------------|
| Per-spawn base overhead: **~41,000 tokens** (not 6,000) | C7's subagent approach pays ~41K per scan agent. Limits the number of scan agents that are cost-effective. Must ensure each scan agent does enough work to justify its overhead. |
| Cache TTL: **1-hour ephemeral** (not 5-minute) | Good news — the TTL is long enough to survive a full `/thorough_plan` run. Cross-round cache hits are feasible. |
| Cache hit/miss cost ratio: **~16x** ($0.016 vs $0.257) | Cache hits are extremely cheap. Worth structuring prompts for cache-friendliness even if the absolute savings are small per call. |
| Cross-session caching works within 1-hour TTL | Confirms C1's value — if we keep stable prefixes byte-identical, cache hits across subagent spawns within a loop are possible. |
| System prompt + harness chrome: **~31-33K tokens** | The vast majority of per-spawn overhead is harness chrome we cannot control. SKILL.md content (693-2,779 tokens) is a small fraction. |
| Built-in tools partially deferred, MCP tools persist | Tool registry cost is largely fixed — cannot be reduced from SKILL.md changes. |

### Critical implication for C7

Each Sonnet scan subagent in C7 pays ~41K tokens of base overhead. At Sonnet rates ($3/M input), that is ~$0.12 per scan agent just for overhead. If the scan agent reads and processes 20K tokens of actual file content on top of the overhead, total cost per agent is ~$0.18. An equivalent Opus read of those same 20K tokens within a unified session costs 20K * $15/M = $0.30, but pays no additional overhead (it is already in the session).

The break-even point: a scan subagent is cheaper than in-session Opus reading when the content it processes is large enough that the 5x Opus/Sonnet price ratio overcomes the $0.12 overhead. That break-even is:

```
0.12 + (content * $3/M) < content * $15/M
0.12 < content * $12/M
content > 10,000 tokens
```

**Each scan agent must process at least ~10K tokens of file content to justify its ~41K overhead cost.** For a typical repo scan reading 20-60K tokens of code, the economics work. For a tiny single-file read, they do not. This constrains C7's design: scan agents must be scoped per-repo (not per-file), and small repos should be batched.

---

## Stage 1a — Hygiene tasks (C1, C3, C4, C5, C6)

### Task 1: C1 — Caching audit and documentation ✅ completed

**What:** Document what the Claude Code harness caches, what is cacheable, and where stable prefixes exist. This is an investigation + documentation task, not a code change.

**Files to create:**
- `cost-reduction/caching-audit.md`

**Specific work:**

1. Run an instrumented `/thorough_plan` session (2 rounds) using `--verbose --output-format stream-json`. Save the raw session output to `cost-reduction/stage-1-caching/instrumented-thorough-plan.json` for reproducibility and future reference.
2. For each API call in the session, extract from `message.usage`:
   - `cache_read_input_tokens` — was there a cache hit?
   - `cache_creation_input_tokens` — was cache written?
   - `cache_creation.ephemeral_1h_input_tokens` — which TTL?
3. Map cache behavior across round boundaries:
   - Does `/critic` round 2 cache-hit against `/critic` round 1's prefix?
   - Does `/revise` cache-hit against `/plan`'s prefix?
   - What is the actual stable prefix size (byte-identical portion) between consecutive calls?
4. Document findings in `cost-reduction/caching-audit.md` with this structure:

```markdown
# Caching Audit — Stage 1

## Harness cache behavior (observed)
- TTL used: 1-hour ephemeral (confirmed by Stage 0)
- Cross-session hits: yes, when prefix is byte-identical within TTL
- Cross-round hits (same skill, consecutive rounds): [yes/no, with data]
- Cross-skill hits (e.g., /plan -> /critic): [yes/no, with data]

## Stable prefix components
| Component | ~Tokens | Stable across rounds? | Stable across skills? |
|-----------|---------|----------------------|----------------------|
| System prompt + harness chrome | ~31-33K | Yes | Yes |
| CLAUDE.md | ~4.1K | Yes | Yes |
| SKILL.md | 693-2.8K | N/A (different per skill) | No |
| lessons-learned.md | variable | Yes (within a run) | Yes |
| current-plan.md | variable | No (rewritten by /revise) | N/A |

## Observed cache-hit rates
[Table from instrumented run]

## Recommendations for SKILL.md prompt structuring
[If any stable-prefix ordering changes would improve hit rates]
```

**Acceptance criteria:**
- `caching-audit.md` exists with real data from at least one instrumented `/thorough_plan` run
- Cache-hit rates per call are documented
- Stable prefix components are identified with token counts
- Raw session JSON is preserved at `cost-reduction/stage-1-caching/instrumented-thorough-plan.json`
- Any prompt-ordering changes that would improve cache hits are identified (but NOT implemented yet — those go into future iterations)

**Risk:** Low. This is pure measurement and documentation — no behavior change.

**Cost/benefit:** The audit itself costs one instrumented run (~$5-10). The information it produces is required for all future caching work and validates/invalidates assumptions in the architecture document. High information value, no downside risk.

**Dependencies:** Requires Stage 0 instrumentation method (already established).

---

### Task 2: C3 — Skip lessons-learned re-read in critic rounds >= 2 ✅ completed

**What:** Update `critic/SKILL.md` so that on critic rounds 2 and above, the critic does NOT re-read `memory/lessons-learned.md`. The file cannot change mid-loop, so re-reading is wasted tokens.

**File to modify:**
- `dev-workflow/skills/critic/SKILL.md`

**Specific change:**

In the "Session bootstrap" section (lines 13-17), replace:

```markdown
## Session bootstrap

This skill ALWAYS runs in a fresh session (that's the whole point — unbiased review). On start:
1. Read `memory/lessons-learned.md` for past insights — check if past lessons apply to this plan's domain
2. Read the task subfolder: `current-plan.md` and any prior `critic-response-*.md`
3. Read the ACTUAL SOURCE CODE referenced by the plan (this is critical — don't trust the plan's claims)
4. Then proceed with critique
```

With:

```markdown
## Session bootstrap

This skill ALWAYS runs in a fresh session (that's the whole point — unbiased review). On start:
1. **Round 1 only:** Read `memory/lessons-learned.md` for past insights — check if past lessons apply to this plan's domain. **On rounds 2+, skip this step** — the file cannot change mid-loop, so re-reading it wastes tokens without adding information. (The round number is indicated by the existing `critic-response-*.md` files: if `critic-response-1.md` already exists, this is round 2 or later.)
2. Read the task subfolder: `current-plan.md` and any prior `critic-response-*.md`
3. Read the ACTUAL SOURCE CODE referenced by the plan (this is critical — don't trust the plan's claims)
4. Then proceed with critique
```

Also, in the "Process" section, step "1.5. Read lessons learned" (lines 33-35), replace:

```markdown
### 1.5. Read lessons learned

Read `memory/lessons-learned.md`. Check if any past lessons apply to this plan's domain — patterns that caused problems before, integration pitfalls, testing blind spots. Use these as extra evaluation criteria.
```

With:

```markdown
### 1.5. Read lessons learned (round 1 only)

**Skip this step on rounds 2+** — lessons-learned cannot change during a `/thorough_plan` loop. On round 1, read `memory/lessons-learned.md`. Check if any past lessons apply to this plan's domain — patterns that caused problems before, integration pitfalls, testing blind spots. Use these as extra evaluation criteria.

To detect the round: check for existing `critic-response-*.md` files in the task folder. If none exist, this is round 1. If `critic-response-1.md` exists, this is round 2 or later.
```

**Acceptance criteria:**
- Critic SKILL.md contains the round-detection logic (check for existing critic-response files)
- Round 1 behavior is unchanged — lessons-learned is still read
- Round 2+ explicitly skips the lessons-learned read
- The change is framed as correctness hygiene, not cost optimization

**Risk:** Near-zero. Lessons-learned is immutable during a `/thorough_plan` loop. The worst case is that a critic on round 2+ does not have lessons-learned in context — but it already read them on round 1, and the information is stable.

**Cost/benefit:** Saves ~693-2,000 tokens of input per critic round >= 2 (depending on lessons-learned file size). On a new project with an empty file, savings are negligible. On a mature project with 50+ lessons, this saves ~2-5K tokens per round at Opus rates (~$0.03-0.08 per round). Small but free.

**Dependencies:** None.

---

### Task 3: C4 — Diff-only review with full-file fallback ✅ completed

**What:** Update `review/SKILL.md` to read the diff FIRST, and only pull full files when the diff surfaces a structural concern. Currently the skill reads both the diff AND the full modified files unconditionally.

**File to modify:**
- `dev-workflow/skills/review/SKILL.md`

**Specific change:**

In "Step 1: Gather context" (lines 29-34), replace:

```markdown
### Step 1: Gather context

1. **Read the plan** — find and read `current-plan.md` in the task subfolder. This is your specification.
2. **Read the architecture** — if `architecture.md` exists, read it for the broader context.
3. **Read the critic responses** — understand what issues were identified during planning and verify they were addressed.
4. **Read the diff** — run `git diff <base-branch>...HEAD` to see all changes. Read every line.
5. **Read the full files** — don't just read the diff. Read the complete files that were modified to understand the context around changes.
```

With:

```markdown
### Step 1: Gather context

1. **Read the plan** — find and read `current-plan.md` in the task subfolder. This is your specification.
2. **Read the architecture** — if `architecture.md` exists, read it for the broader context.
3. **Read the critic responses** — understand what issues were identified during planning and verify they were addressed.
4. **Read the diff** — run `git diff <base-branch>...HEAD` to see all changes. Read every line carefully.
5. **Selectively read full files** — do NOT read all modified files unconditionally. Instead, use the diff to determine which files need full-context reading. Pull the full file only when:
   - The diff shows changes to function signatures, class hierarchies, or module exports (structural changes whose safety depends on how callers use them)
   - The diff modifies error handling, authentication, or authorization logic (security-sensitive areas need full surrounding context)
   - The diff touches code that interacts with external services, databases, or message queues (integration points need full trace)
   - The diff is a partial change to a complex function where the surrounding logic is not visible in the diff context
   - The critic responses flagged specific files as risky or requiring deep review

   For simple changes (config updates, string changes, straightforward additions, test files), the diff with its surrounding context lines is sufficient. When in doubt, read the full file — the cost of missing a bug far exceeds the cost of reading extra tokens.
```

Also, update the "Important behaviors" section (line 185). Replace:

```markdown
- **Read everything.** Partial reviews are worse than no review — they create false confidence. Read every changed file completely.
```

With:

```markdown
- **Read the diff thoroughly; read full files selectively.** Start with the complete diff and read every line. Then pull full files for any change that touches structure, security, or integrations. Simple, self-contained changes do not require full-file reads. When uncertain whether full context is needed, read the full file — a missed bug is far more expensive than extra input tokens.
```

**Implementation note:** The "before" text in the "Important behaviors" replacement contains an em dash character. When implementing, copy the "before" text directly from the actual file to ensure byte-identical matching, rather than relying on the plan's text which may have character-encoding differences.

**Acceptance criteria:**
- Review SKILL.md instructs to read the diff first, unconditionally
- Full-file reads are triggered only by specific criteria (structural changes, security, integrations, critic flags)
- The "when in doubt, read the full file" safety valve is present
- The "Important behaviors" section is updated to match the new approach

**Risk:** Low-medium. The risk is that a reviewer misses a bug hidden outside the diff context. Mitigated by:
1. The explicit criteria for when to pull full files covers the high-risk categories
2. The "when in doubt, read the full file" instruction preserves safety
3. `/review` still runs on Opus, so reasoning quality is unaffected
4. The criteria specifically call out security, integrations, and structural changes — the highest-risk categories

**Cost/benefit:** On a typical review with 5-10 modified files, if 3-5 of them are simple changes (test files, config, string updates), this saves reading ~15-30K tokens of file content at Opus input rates. That is ~$0.22-0.45 per review. Meaningful for frequent reviews, and the review quality should not degrade for the high-risk file categories.

**Dependencies:** None.

---

### Task 4: C5 — Skip /discover for unchanged repos ✅ completed

**What:** Update `discover/SKILL.md` to record `git rev-parse HEAD` per repo after scanning, and skip repos whose HEAD has not changed on subsequent runs.

**File to modify:**
- `dev-workflow/skills/discover/SKILL.md`

**Specific changes:**

**Change 1:** Add a new section between the `## What to scan` heading and the introductory paragraph ("Starting from the project root folder..."). The incremental scan logic decides WHICH repos to scan, so it must precede the instructions for HOW to scan each repo. Insert immediately after `## What to scan`:

```markdown
### Incremental scan — skip unchanged repos

Before scanning each repo, check if a previous scan recorded the repo's HEAD commit:

1. Read `memory/repo-heads.md` if it exists. This file maps repo names to their `git rev-parse HEAD` values from the last `/discover` run.
2. For each repo in the project folder, run `git rev-parse HEAD` and compare against the stored value.
3. **If HEAD matches the stored value: skip the full scan for that repo.** Its inventory, dependencies, and API surface have not changed. Report to the user: "Skipping <repo-name> — unchanged since last scan (HEAD: <short-hash>)."
4. **If HEAD differs or no stored value exists: perform the full scan** as described below.
5. After completing all scans, overwrite `memory/repo-heads.md` with the current HEAD values for all repos (including unchanged ones).

Format for `memory/repo-heads.md`:

| Repo | HEAD |
|------|------|
| <repo-name-1> | <full-sha> |
| <repo-name-2> | <full-sha> |

**Important:** When the user explicitly requests a full re-scan (e.g., "rescan everything", "force rediscover"), ignore the HEAD cache and scan all repos.
```

Then the existing introductory paragraph ("Starting from the project root folder, examine every top-level directory. For each repository/service found:") continues to flow naturally into `### Per-repo inventory`.

**Change 2:** Update the "## When to re-run" section at the end. Add a new bullet:

```markdown
- When you want to force a full re-scan regardless of HEAD changes (say "rescan all repos" or similar)
```

**Change 3:** Update the "## After scanning" section. Add after the existing bullets:

```markdown
- Which repos were skipped (unchanged since last scan) and which were re-scanned
```

**Acceptance criteria:**
- `discover/SKILL.md` instructs the skill to check `memory/repo-heads.md` before scanning
- Unchanged repos are skipped with a user-visible message
- The `repo-heads.md` file format is specified
- Force re-scan instruction is present
- After-scan report includes which repos were skipped
- The incremental scan section appears before the per-repo scan instructions (not between the intro paragraph and the first subsection)

**Risk:** Low. The worst case is a false skip — a repo changed in a way that `git rev-parse HEAD` does not capture (e.g., uncommitted changes). But `/discover` scans committed state, not working directory state, so HEAD is the correct indicator. If the user has uncommitted changes they want discovered, a force re-scan is available.

**Cost/benefit:** In a multi-repo project where only 1 of 5 repos changed, this skips 80% of the per-repo scanning work. For a typical repo scan costing ~20-40K tokens of Opus input ($0.30-0.60), skipping 4 repos saves ~$1.20-2.40 per `/discover` run. High value for projects with many repos.

**Dependencies:** None, but naturally pairs with C7 (both optimize file-reading patterns).

---

### Task 5: C6 — Lessons-learned pruning in /end_of_day ✅ completed

**What:** Add a "prune lessons-learned" step to `/end_of_day` that triggers when the file exceeds a threshold number of entries.

**File to modify:**
- `dev-workflow/skills/end_of_day/SKILL.md`

**Specific change:**

Add a new step between the existing Step 3b (insights review) and Step 4 (prompt for lessons learned). Insert after Step 3b:

```markdown
### Step 3c: Prune lessons-learned if oversized

Check `memory/lessons-learned.md`. Count the number of lesson entries by matching lines that begin with `## ` followed by a date pattern (YYYY-MM-DD) — i.e., lines matching the regex `^## \d{4}-\d{2}-\d{2}`. Ignore any such patterns inside HTML comments (`<!-- -->`), code blocks, or template examples.

**If the count exceeds 30 entries**, present a pruning prompt to the user:

> "lessons-learned.md has grown to N entries (~X tokens). Large files add a fixed token cost to every /plan, /critic, and /architect session. Would you like to prune?"
>
> Options:
> 1. **Auto-prune** — I'll merge related entries, remove entries older than 90 days that haven't been referenced, and consolidate duplicates. You review before I save.
> 2. **Manual prune** — I'll list all entries with a 1-line summary; you pick which to keep.
> 3. **Skip** — keep the file as-is.

**Auto-prune rules** (if selected):
1. Group entries by `Applies to:` tag. If 3+ entries have the same tag and similar content, merge them into one consolidated entry preserving all unique information.
2. Entries older than 90 days that are generic advice (e.g., "always run tests", "check error handling") can be removed — the behavior should be internalized by now.
3. Entries that reference specific files or functions that no longer exist in the codebase can be removed (check with a quick file-existence test).
4. Always preserve: entries tagged as applying to `/architect` or `/critic` (highest-leverage skills), entries less than 30 days old, entries the user explicitly marked as important.
5. Show the proposed changes to the user in a before/after summary and wait for explicit confirmation before overwriting.

**If the count is 30 or fewer**, skip this step silently.
```

**Acceptance criteria:**
- `end_of_day/SKILL.md` has the pruning step between Step 3b and Step 4
- Threshold is 30 entries (configurable by changing the number in the text)
- Three pruning options are offered: auto, manual, skip
- Auto-prune has explicit rules (merge duplicates, remove stale, preserve recent/important)
- User confirmation is required before overwriting
- The pruning step is skipped silently when the threshold is not exceeded
- Entry detection uses the `^## \d{4}-\d{2}-\d{2}` regex pattern, excluding HTML comments and template examples

**Risk:** Low. The pruning is user-initiated (requires explicit selection), requires confirmation before saving, and has a "skip" option. The auto-prune rules are conservative — they preserve recent entries and high-leverage entries.

**Cost/benefit:** On a project with 50+ lessons-learned entries (~5-10K tokens), the file is read by every `/plan`, `/critic`, `/architect`, and `/review` session. At Opus rates, 10K tokens * $15/M = $0.15 per read. Over 20 skill invocations per week, that is $3/week of pure tax. Pruning to 30 entries (~3-6K tokens) saves ~$1-2/week. More importantly, it prevents unbounded growth that would eventually consume meaningful context window space.

**Dependencies:** None. Can be implemented and tested independently.

---

## Stage 1b — /architect scan/synthesize split (C7)

### Task 6: C7 — Rewrite /architect to use scan/synthesize phases

**What:** Restructure `/architect` from a single Opus session that does everything (file reading, web search, synthesis) into a two-phase approach:

- **Phase 1 (Scan):** Spawn narrow Sonnet read-only subagents — one per repo (or per small batch of repos) — in parallel. Each scan agent reads files, extracts structured findings, and returns them to the orchestrator.
- **Phase 2 (Synthesize):** The Opus `/architect` session reads the scan findings (not the raw files) and performs the architectural analysis, design, and writing.

**File to modify:**
- `dev-workflow/skills/architect/SKILL.md`

**Specific changes:**

All changes below identify target locations by section heading names, not line numbers. This is more robust — headings are stable identifiers even if the file is edited.

**Change 1:** Update the frontmatter description to reflect the new pattern.

Replace the existing `description:` field in the YAML frontmatter:
```
description: "Deep architectural analysis and planning using the strongest available model (Opus). Use this skill whenever the user needs to explore a complex system, understand how multiple repositories interact, design a new architecture, decompose a large problem into implementable stages, or answer hard cross-cutting questions about a codebase. Triggers on: /architect, architecture design, system design, technical exploration, cross-repo analysis, complex technical questions, 'how should we build this', 'what's the best approach for', deep code exploration, multi-service design. Even if the user just says 'I need to think through X' where X is technical — use this skill."
```

With:
```
description: "Deep architectural analysis and planning using the strongest available model (Opus), with a scan/synthesize split for efficiency. Spawns Sonnet subagents in parallel to read repos, then synthesizes findings on Opus. Use this skill whenever the user needs to explore a complex system, understand how multiple repositories interact, design a new architecture, decompose a large problem into implementable stages, or answer hard cross-cutting questions about a codebase. Triggers on: /architect, architecture design, system design, technical exploration, cross-repo analysis, complex technical questions, 'how should we build this', 'what's the best approach for', deep code exploration, multi-service design. Even if the user just says 'I need to think through X' where X is technical — use this skill."
```

**Change 2:** Replace the entire `### Phase 1: Understand the landscape` section (from its heading through to the line before `### Phase 2: Research and explore`) with:

```markdown
### Phase 1: Scan — parallel repo exploration (Sonnet subagents)

The goal of Phase 1 is to gather structured facts from the codebase WITHOUT doing architectural reasoning. Reasoning is Phase 2's job. Phase 1 is read-only bulk extraction.

**Check for /discover output first.** Before spawning scan agents, check `memory/` for existing `/discover` output (`repos-inventory.md`, `architecture-overview.md`, `dependencies-map.md`). If these exist and are recent:
- Read them to understand the landscape baseline
- Use `memory/repo-heads.md` (if it exists) to identify repos that have changed since the last `/discover` run
- Only spawn scan agents for repos that are (a) changed since last scan, or (b) specifically relevant to the current task
- For unchanged repos, the `/discover` output IS the scan output — no need to re-scan

**If /discover output does not exist or is stale**, scan all repos.

#### Spawning scan agents

For each repo (or batch of small repos) that needs scanning, spawn a subagent with these parameters:

- **Model:** Sonnet (cheaper for bulk reading — this is the core cost win)
- **Scope:** One repo per agent (or batch 2-3 small repos into one agent if each has < 10 files)
- **Instructions to each scan agent:**

  > You are a read-only code scanner. Your job is to extract structured facts from this repository. Do NOT do architectural analysis or design — just report what you find.
  >
  > Repo path: <repo-path>
  > Task context: <brief description of what the /architect session is investigating>
  >
  > Scan and report:
  >
  > 1. IDENTITY
  >    - Repo name, primary language(s), framework(s), runtime, build system
  >    - Detected from: package.json, go.mod, Cargo.toml, requirements.txt, etc.
  >
  > 2. STRUCTURE
  >    - Key directories and what they contain
  >    - Entry points (main files, index files, server startup)
  >    - Configuration files and what they control
  >    - Test structure (where tests live, framework used)
  >
  > 3. EXTERNAL DEPENDENCIES
  >    - Key libraries/frameworks (the important ones, not every transitive dep)
  >    - External services called (from config, env vars, client code)
  >    - Database connections (type, patterns)
  >    - Message queues, event buses, cache systems
  >
  > 4. API SURFACE
  >    - Exposed endpoints (REST routes, GraphQL schemas, gRPC protos)
  >    - Published events/messages
  >    - Shared libraries or packages exported
  >
  > 5. TASK-RELEVANT CODE
  >    - Files, functions, and patterns specifically relevant to: <task context>
  >    - Include file paths and brief code summaries (not full file contents)
  >    - Flag any code that seems fragile, complex, or likely to interact with the task
  >
  > **Output constraint:** Keep your total output under ~3,000-5,000 tokens. Be concise — include file paths and brief summaries, not full code excerpts. The synthesis phase can do targeted reads of specific files if it needs more detail.
  >
  > Output format: structured markdown with the sections above. Be factual, not interpretive. Include file paths for everything you reference.

- **Parallelism:** Spawn all scan agents simultaneously. They are independent and read-only.
- **Minimum content threshold:** Only spawn a scan agent if the repo contains enough code to justify the ~41K token base overhead. For repos with fewer than ~5 source files, include them in a batch with another small repo, or read them directly in the main session during Phase 2.

#### Collecting scan results

Each scan agent returns its structured findings. Collect all findings into a combined document. Do NOT process or interpret them yet — that is Phase 2.
```

**Change 3:** Remove the entire `### Phase 2: Research and explore` section. Its content (web research) is folded into Phase 2 (Synthesize) below.

**Change 4:** Replace `### Phase 3: Architectural design` heading and its introductory line with:

```markdown
### Phase 2: Synthesize — architectural design (Opus)

**This is where Opus earns its keep.** You now have structured scan findings from every relevant repo (Phase 1). Your job is to reason across all of these inputs to produce the architectural design. You do NOT need to re-read the raw source files — the scan findings contain the facts you need. If a scan finding is ambiguous or insufficient, you can do targeted reads of specific files (not whole-repo reads).

**Web research:** When the problem requires knowledge beyond what's in the codebase, search the web for best practices, design patterns, and known pitfalls with specific technologies. Read external documentation for APIs, frameworks, or services involved. Look at how others have solved similar problems — open source examples, blog posts, conference talks. Check for existing internal patterns — if the codebase already has a way of doing things (error handling, logging, auth), the scan findings will have surfaced them. Web research happens here in the main Opus session because it benefits from the strongest model and is naturally interleaved with synthesis reasoning.

Produce a detailed architectural plan. The plan should include:
```

(The rest of the existing Phase 3 content — the numbered list of what to include in the architecture — remains unchanged.)

**Change 5:** Rename `### Phase 4: Decomposition into stages` to `### Phase 3: Decomposition into stages` (renumber only, content unchanged).

**Change 6:** Add a new section after `## Important behaviors` (the last section before the end of the file):

```markdown
## Cost discipline

The scan/synthesize split exists to avoid paying Opus rates for bulk file reading. Maintain this discipline:

- **Never read raw source files in the main Opus session for bulk exploration.** That is what scan agents are for. The only exception is targeted reads of specific files (fewer than ~50 lines, directly relevant to a specific synthesis question) during Phase 2.
- **Spawn scan agents per-repo, not per-file.** Each agent pays ~41K tokens of base overhead. A per-file agent for a 200-line file is pure waste.
- **Batch small repos.** If a repo has fewer than ~5 source files, batch it with another small repo into a single scan agent.
- **Use /discover output when available.** If `memory/repos-inventory.md` exists and the repo HEAD has not changed (check `memory/repo-heads.md`), the /discover output IS the scan. Do not re-scan.
- **Targeted re-scans during synthesis.** If Phase 2 reveals a gap in the scan findings (e.g., "I need to see the exact error handling in payment.service.ts"), read that specific file directly in the Opus session. Do NOT spawn a whole new scan agent for one file.
```

**Acceptance criteria:**
- `/architect` SKILL.md has a two-phase structure: scan (Sonnet subagents) then synthesize (Opus)
- Scan agent instructions are complete and specify structured output format
- Scan agent instructions include an output size constraint (~3,000-5,000 tokens)
- Scan agents are scoped per-repo (or per small-repo-batch), not per-file
- The minimum content threshold (~41K overhead justification) is documented
- /discover output integration is specified (check repo-heads, skip unchanged)
- Targeted re-scan fallback is documented
- Phase 2 (synthesis) instructs NOT to re-read raw files — use scan findings
- Web research is part of Phase 2 (synthesis), not a separate phase
- Cost discipline section exists with explicit rules
- No line-number references — all locations identified by section heading names

**Risk:** Medium. This is the largest change in Stage 1. Risks:

1. **Scan agents miss something a unified Opus pass would catch.** Mitigation: (a) scan agents are told to include task-relevant code specifically, (b) synthesis phase can do targeted reads if findings are ambiguous, (c) this only affects the scan — the critic still runs on Opus with full codebase access and will catch scan-phase misses.

2. **Subagent overhead eats the savings on small projects.** Mitigation: minimum content threshold — only spawn agents for repos with enough code. Small repos are read directly or batched.

3. **Scan output format is inconsistent across agents.** Mitigation: strict structured output template with numbered sections. Sonnet follows templates well.

4. **Latency increase from spawning parallel agents.** Mitigation: agents run in parallel, so wall-clock time is max(agent times), not sum. For typical repos, a Sonnet scan is faster than an Opus scan of the same content.

5. **Scan output too large, partially defeating the cost savings.** Mitigation: output size constraint (~3,000-5,000 tokens per agent) in the scan agent instructions. Combined findings for 5 repos should be ~15-25K tokens — significantly less than the 60-200K of raw file content.

**Cost/benefit:** This is Stage 1's largest lever. A typical `/architect` session reads 3-5 repos, consuming 60-200K tokens of file content at Opus rates ($0.90-3.00 in input alone). Moving the file reading to Sonnet subagents:

- **Overhead cost:** 3-5 scan agents * ~41K tokens * $3/M = ~$0.37-0.62
- **Scan content cost:** same 60-200K tokens at Sonnet rates = $0.18-0.60
- **Total Phase 1 cost:** ~$0.55-1.22
- **Versus today:** 60-200K tokens at Opus rates = $0.90-3.00

**Savings: ~$0.35-1.78 per /architect invocation** (39-59% reduction in file-reading cost). Plus the Opus synthesis phase reads structured findings (~10-20K tokens) instead of raw files (60-200K tokens), saving additional Opus input cost of ~$0.60-2.70.

**Net savings: ~$0.95-4.48 per /architect invocation.** For a project that runs /architect 2-3 times per week, this is ~$2-13 per week.

**Dependencies:** Benefits from C5 (Task 4) — if `repo-heads.md` exists, scan agents can skip unchanged repos. But does not require C5 to function.

---

## Integration analysis

### How do these changes interact with each other?

| Change A | Change B | Interaction | Risk |
|----------|----------|-------------|------|
| C3 (critic skip lessons) | C1 (caching audit) | C3 reduces tokens read, which could reduce cache-hit surface if lessons-learned was part of the stable prefix. But since C3 only affects rounds 2+, and round 1 still reads lessons-learned, the cache-write on round 1 is unchanged. Round 2+ saves tokens by not reading the file at all, which is better than a cache hit. | None — C3 is strictly better than caching lessons-learned on round 2+ |
| C4 (diff-only review) | None of the others | C4 modifies only /review, which runs after the plan loop. No interaction with C3 (critic), C5 (discover), C6 (end_of_day), or C7 (architect). | None |
| C5 (skip unchanged repos) | C7 (architect split) | Strong positive interaction. C7's scan agents use C5's `repo-heads.md` to skip unchanged repos entirely — not just skipping the scan agent, but avoiding the ~41K overhead of spawning one. This makes C7 much cheaper on subsequent runs. | Coordination needed: C7's Phase 1 must read `repo-heads.md` and match its format. Specified in Task 6. |
| C6 (prune lessons) | C3 (critic skip lessons) | C6 reduces lessons-learned size for ALL skills (plan, critic round 1, architect, review). C3 only affects critic rounds 2+. They are complementary — C6 makes the round-1 read cheaper, C3 eliminates the round-2+ reads entirely. | None |
| C7 (architect split) | Existing /discover | C7's scan agents overlap significantly with what /discover does. If /discover has been run recently, C7 should skip the scan and use /discover output. This is specified in Task 6 and requires the C5 HEAD-check integration. | If /discover output format changes in the future, C7's code for reading it needs to be updated. Low risk — format is defined in discover/SKILL.md and is stable. |

### How do these changes interact with the rest of the workflow?

| Stage 1 change | Downstream skill | Interaction | Risk |
|----------------|-----------------|-------------|------|
| C3 (critic) | /thorough_plan orchestrator | The orchestrator does not read lessons-learned itself — it just spawns /critic. No change needed to thorough_plan/SKILL.md for C3. | None |
| C4 (review) | /gate, /end_of_task | /gate runs before /review; /end_of_task runs after. Neither is affected by how /review reads files. | None |
| C5 (discover) | /architect, /plan, /critic | These skills read /discover's OUTPUT (the memory/ files), not /discover itself. The output format is unchanged — only which repos get re-scanned changes. | None |
| C6 (end_of_day) | /start_of_day, /plan, /critic | If lessons-learned is pruned, all skills that read it get a smaller file. This is the intended benefit. /start_of_day is unaffected (it reads session state, not lessons-learned). | Quality risk if aggressive pruning removes a valuable lesson. Mitigated by user confirmation requirement. |
| C7 (architect) | /plan, /critic (read architecture.md) | C7 changes HOW architecture.md is produced, not its format or content. Downstream skills read the output file, which has the same structure. | None — output format unchanged |

### Changes that interact with Stage 2

Stage 2 modifies `thorough_plan/SKILL.md` (B1, B3, E0 fix). Stage 1 does NOT modify `thorough_plan/SKILL.md`. No merge conflicts. The two stages can be implemented in either order.

---

## Risk assessment

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|-----------|--------|------------|
| S1-R1 | C1 audit shows no actionable caching opportunities | Medium | Low — we learn what the harness does, which is valuable regardless | Audit is documentation, not code change. Information is valuable even if findings are "harness already handles this well." |
| S1-R2 | C4 reviewer misses a bug hidden outside the diff | Low | Medium | Five explicit triggers for full-file reads (structural, security, integration, complex, critic-flagged). "When in doubt, read" safety valve. /review is still Opus. |
| S1-R3 | C5 incorrectly skips a repo that had meaningful changes | Very low | Low | HEAD captures all committed changes. Uncommitted changes are not in /discover's scope. Force re-scan available. |
| S1-R4 | C7 scan agents miss important context that Opus would have caught | Medium | Medium | Scan agents include task-relevant code. Synthesis can do targeted reads. /critic (Opus) still reads the full codebase and will catch scan-phase misses. |
| S1-R5 | C7 subagent overhead exceeds savings on small projects (< 3 repos) | Medium | Low | Minimum content threshold in the SKILL.md. For very small projects (1-2 repos), the overhead may exceed savings — but the scan still runs on Sonnet, saving on model cost even if base overhead is a fixed tax. |
| S1-R6 | C6 auto-prune removes a valuable lesson | Low | Low | User must confirm before save. Conservative rules (preserve recent, preserve high-leverage tags). |
| S1-R7 | C7 scan output too verbose, reducing synthesis savings | Low | Medium | Output size constraint (~3K-5K tokens per agent) in scan instructions. Combined findings for 5 repos: ~15-25K vs 60-200K raw. |

---

## Testing strategy

### Task 1 (C1 — Caching audit)
- **Test:** Run an instrumented `/thorough_plan` session and verify the audit document is produced with real data.
- **Pass criteria:** `caching-audit.md` contains per-call cache-hit data with token counts. Raw JSON is saved to `cost-reduction/stage-1-caching/instrumented-thorough-plan.json`.

### Task 2 (C3 — Skip lessons-learned)
- **Test 1:** Run `/thorough_plan` on a task with a non-empty `lessons-learned.md`. Verify that the round-1 critic reads lessons-learned (look for it in the critic's context or output).
- **Test 2:** Verify that the round-2 critic does NOT read lessons-learned (it should not reference the file or its contents beyond what round 1 already established in the plan).
- **Test 3:** Confirm the round-detection logic works — create a task folder with an existing `critic-response-1.md` and run `/critic` standalone. It should detect round 2 and skip lessons-learned.
- **Pass criteria:** Round 1 reads lessons-learned; round 2+ does not.

### Task 3 (C4 — Diff-only review)
- **Test 1:** Create a branch with a simple string-change commit. Run `/review`. Verify it reads the diff but does NOT read the full modified file (unless the file is flagged by the criteria).
- **Test 2:** Create a branch with a commit that changes a function signature. Run `/review`. Verify it reads the full file for that change.
- **Test 3:** Verify the "when in doubt" behavior — a moderately complex change should trigger a full-file read.
- **Pass criteria:** Simple changes use diff only; structural changes trigger full-file reads.

### Task 4 (C5 — Skip unchanged repos)
- **Test 1:** Run `/discover` on a multi-repo project. Verify `memory/repo-heads.md` is created with HEAD values.
- **Test 2:** Without changing any repo, run `/discover` again. Verify all repos are skipped.
- **Test 3:** Make a commit in one repo. Run `/discover` again. Verify the changed repo is re-scanned and the unchanged repos are skipped.
- **Test 4:** Use "force rescan" language. Verify all repos are scanned regardless of HEAD.
- **Pass criteria:** HEAD cache is created, unchanged repos are skipped, changed repos are re-scanned, force override works.

### Task 5 (C6 — Lessons-learned pruning)
- **Test 1:** Create a `lessons-learned.md` with 35 entries (above the 30-entry threshold). Run `/end_of_day`. Verify the pruning prompt appears.
- **Test 2:** Create a `lessons-learned.md` with 25 entries (below threshold). Run `/end_of_day`. Verify the pruning step is silently skipped.
- **Test 3:** Select "auto-prune" and verify the proposed changes are shown to the user before saving.
- **Test 4:** Create a `lessons-learned.md` that includes an HTML comment with a `## 2026-01-01` example line inside the comment. Verify the entry counter does NOT count it as a real entry.
- **Pass criteria:** Threshold triggers correctly, options are presented, user confirmation required, comment-embedded patterns are not miscounted.

### Task 6 (C7 — Architect scan/synthesize)
- **Test 1:** Run `/architect` on a project with 3+ repos. Verify that Sonnet scan agents are spawned (check `--verbose` output for model changes between messages).
- **Test 2:** Verify scan agents produce structured output matching the template, each within the ~3K-5K token output constraint.
- **Test 3:** Verify the synthesis phase (Phase 2) does NOT read raw source files for repos that were scanned.
- **Test 4:** Verify that when `/discover` output exists and repo HEADs are unchanged, scan agents are NOT spawned for those repos.
- **Test 5:** Verify quality — compare the resulting `architecture.md` against one produced by the old unified approach on the same project. Look for missing information.
- **Pass criteria:** Scan agents spawn on Sonnet, findings are structured and concise, synthesis uses findings not raw files, /discover integration works, architecture quality is comparable.

---

## Implementation order

```
Task 1 (C1 — caching audit)     +
Task 2 (C3 — critic skip)       |
Task 3 (C4 — diff-only review)  +-- Stage 1a: implement in any order (all independent)
Task 4 (C5 — discover skip)     |
Task 5 (C6 — lessons pruning)   +

Task 6 (C7 — architect split)   --- Stage 1b: implement after 1a ships, or in parallel
```

**Recommended order within 1a:** Tasks 2-5 are all simple SKILL.md text edits. Implement them in a single commit. Task 1 (caching audit) is different — it is an investigation that produces a document, not a code change. Run it first or in parallel with the SKILL.md edits, since the audit findings may inform future work but do not block 1a's implementation.

**Recommended approach:**
1. Branch from main for Stage 1a.
2. Implement Tasks 2, 3, 4, 5 as SKILL.md text edits. Single commit.
3. Run Task 1 (caching audit) as an instrumented session. Commit the resulting document.
4. `/review` the branch. `/end_of_task`.
5. Branch from main for Stage 1b.
6. Implement Task 6 (architect split).
7. Test with a real `/architect` run on a multi-repo project.
8. `/review` the branch. `/end_of_task`.

---

## Cost/benefit summary

| Task | Lever | Savings per invocation | Frequency | Weekly savings estimate |
|------|-------|----------------------|-----------|------------------------|
| Task 1 | C1 (audit) | $0 (informational) | Once | $0 (but enables future optimizations) |
| Task 2 | C3 (critic skip) | ~$0.03-0.08 per round 2+ | 2-4x/week | ~$0.06-0.32 |
| Task 3 | C4 (diff-only review) | ~$0.22-0.45 per review | 3-5x/week | ~$0.66-2.25 |
| Task 4 | C5 (discover skip) | ~$1.20-2.40 per discover run (multi-repo) | 1-2x/week | ~$1.20-4.80 |
| Task 5 | C6 (lessons pruning) | ~$0.05-0.15 per skill invocation (once pruned) | 15-25x/week | ~$0.75-3.75 |
| Task 6 | C7 (architect split) | ~$0.95-4.48 per architect run | 2-3x/week | ~$1.90-13.44 |
| **Total** | | | | **~$4.57-24.56/week** |

The dominant lever is C7 (architect split), contributing 40-55% of the total weekly savings. C5 (discover skip) and C4 (diff-only review) are the next most valuable. C3 (critic skip) and C6 (lessons pruning) are small but free — they are hygiene items worth doing for correctness as much as cost.

**Important caveat:** These estimates use the architecture document's illustrative token counts (40K codebase, 12K stable prefix, etc.) which have NOT been replaced by real measurements. The Stage 0 instrumented runs established per-spawn overhead and cache behavior but did not produce per-skill token breakdowns for a full `/thorough_plan` or `/architect` run. Task 1 (C1 audit) will produce the first real numbers. Actual savings will differ — potentially significantly — from these estimates.

---

## Revision history

### Round 2 — 2026-04-12
**Critic verdict (Round 1):** REVISE (0 CRITICAL, 2 MAJOR, 6 MINOR)

**Issues addressed:**
- [MAJ-1] Removed all line-number references from Task 6 (C7). All target locations now identified solely by section heading names, which are more robust against future edits. Added explicit note: "All changes below identify target locations by section heading names, not line numbers."
- [MAJ-2] Eliminated the awkward "Phase 1b" naming for the web research step. Instead of a separate "Phase 1b: Research and explore" section, web research is now folded directly into Phase 2 (Synthesize) as a "Web research" paragraph. This produces a clean Phase 1 (Scan/Sonnet) -> Phase 2 (Synthesize/Opus, including web research) -> Phase 3 (Decompose) structure with no ambiguous sub-phases. The old Phase 2 (Research) and Phase 3 (Design) are merged into a single Phase 2 (Synthesize).
- [MIN-1] Fixed Task 4 (C5) insertion point. The incremental scan section is now inserted immediately after the `## What to scan` heading, before the introductory paragraph ("Starting from the project root folder..."). This avoids breaking the flow where that paragraph's trailing colon previously pointed directly at `### Per-repo inventory`.
- [MIN-2] Added raw session output storage path to Task 1 (C1). Step 1 now specifies saving to `cost-reduction/stage-1-caching/instrumented-thorough-plan.json`. Added to acceptance criteria.
- [MIN-3] Improved entry-counting method in Task 5 (C6). Now specifies the regex `^## \d{4}-\d{2}-\d{2}` and explicitly excludes matches inside HTML comments, code blocks, or template examples. Added Test 4 to verify comment-embedded patterns are not miscounted.
- [MIN-4] Added output size constraint to Task 6 (C7) scan agent instructions: "Keep your total output under ~3,000-5,000 tokens." Added corresponding risk (S1-R7) and updated Test 2 and acceptance criteria.
- [MIN-5] Reworded the first bullet in Task 6's "Cost discipline" section. Changed from "Never read raw source files in the main Opus session during Phase 1" (confusing since Phase 1 does not run in the main session) to "Never read raw source files in the main Opus session for bulk exploration." Exception clause now references Phase 2 specifically.
- [MIN-6] Added implementation note to Task 3 (C4) about em dash character encoding. Instructs implementer to copy "before" text from the actual file to avoid byte-mismatch issues with the Edit tool.

**Issues noted but deferred:**
- None — all issues addressed.
