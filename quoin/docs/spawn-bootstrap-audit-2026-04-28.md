## State
stage: 2 | task: pipeline-efficiency-improvements | date: 2026-04-29 | generated_by: /implement T-02

## Purpose
Per-skill audit of spawn-target bootstrap reads. Identifies boilerplate vs task-specific reads to determine preamble eligibility. Source of truth for the 7-target membership list and per-skill preamble content.

## Skill audit table

### critic

| bootstrap-step | path-read | tag | preamble-eligible | rationale |
|---|---|---|---|---|
| 1. Read lessons-learned (round 1 only) | `.workflow_artifacts/memory/lessons-learned.md` | boilerplate | no (phantom) | Does not exist at deployed path; only source at `quoin/memory/lessons-learned.md`; install.sh does not deploy it; see §Discrepancies |
| 2a. Resolve task subfolder | `python3 ~/.claude/scripts/path_resolve.py` | task-specific | no | Depends on task name arg |
| 2b. Read current-plan | `<task_dir>/current-plan.md` | task-specific | no | Per-invocation |
| 2c. Read prior critic responses | `<task_dir>/critic-response-*.md` | task-specific | no | Per-invocation |
| 2d. Read architecture | `<task-root>/architecture.md` | task-specific | no | Per-invocation |
| 2e. Read cost-ledger | `<task-root>/cost-ledger.md` | task-specific | no | Per-invocation |
| 3. Read actual source code | various | task-specific | no | Varies by plan |
| 4. Append cost ledger | `<task-root>/cost-ledger.md` | task-specific | no | Write, not read |
| 5a. Read format-kit | `~/.claude/memory/format-kit.md` | boilerplate | yes | Fixed path, task-independent |
| 5b. Read glossary | `~/.claude/memory/glossary.md` | boilerplate | yes | Fixed path, task-independent |

**Per-skill aggregate — critic:** total reads: 10 | boilerplate-eligible: 2 (format-kit §3-slice + glossary) | task-specific: 8 | preamble bytes (estimated): ~4000 (1192 + 2819)

---

### revise

| bootstrap-step | path-read | tag | preamble-eligible | rationale |
|---|---|---|---|---|
| 1a. Resolve task subfolder | `python3 ~/.claude/scripts/path_resolve.py` | task-specific | no | Depends on task name arg |
| 1b. Read current-plan | `<task_dir>/current-plan.md` | task-specific | no | Per-invocation |
| 1c. Read latest critic-response | `<task_dir>/critic-response-*.md` | task-specific | no | Per-invocation |
| 1d. Read architecture | `<task-root>/architecture.md` | task-specific | no | Per-invocation |
| 1e. Read cost-ledger | `<task-root>/cost-ledger.md` | task-specific | no | Per-invocation |
| 2. Check knowledge cache | `.workflow_artifacts/cache/<repo>/...` | task-specific | no | Per-invocation |
| 3. Append cost ledger | `<task-root>/cost-ledger.md` | task-specific | no | Write |
| 4a. Read format-kit | `~/.claude/memory/format-kit.md` | boilerplate | yes | Fixed path, task-independent |
| 4b. Read glossary | `~/.claude/memory/glossary.md` | boilerplate | yes | Fixed path, task-independent |

**Per-skill aggregate — revise:** total reads: 9 | boilerplate-eligible: 2 | task-specific: 7 | preamble bytes (estimated): ~4000

---

### revise-fast

bootstrap steps identical to revise (SYNC contract per SKILL.md comment).

| bootstrap-step | path-read | tag | preamble-eligible | rationale |
|---|---|---|---|---|
| §0 dispatch check | system context | task-specific | no | Model detection, no file read |
| 1a. Resolve task subfolder | `python3 ~/.claude/scripts/path_resolve.py` | task-specific | no | Per-invocation |
| 1b. Read current-plan | `<task_dir>/current-plan.md` | task-specific | no | Per-invocation |
| 1c. Read latest critic-response | `<task_dir>/critic-response-*.md` | task-specific | no | Per-invocation |
| 1d. Read architecture | `<task-root>/architecture.md` | task-specific | no | Per-invocation |
| 1e. Read cost-ledger | `<task-root>/cost-ledger.md` | task-specific | no | Per-invocation |
| 2. Check knowledge cache | `.workflow_artifacts/cache/<repo>/...` | task-specific | no | Per-invocation |
| 3. Append cost ledger | `<task-root>/cost-ledger.md` | task-specific | no | Write |
| 4a. Read format-kit | `~/.claude/memory/format-kit.md` | boilerplate | yes | Fixed path, task-independent |
| 4b. Read glossary | `~/.claude/memory/glossary.md` | boilerplate | yes | Fixed path, task-independent |

**Per-skill aggregate — revise-fast:** total reads: 10 | boilerplate-eligible: 2 | task-specific: 8 | preamble bytes (estimated): ~4000

---

### plan

| bootstrap-step | path-read | tag | preamble-eligible | rationale |
|---|---|---|---|---|
| 1. Read lessons-learned | `.workflow_artifacts/memory/lessons-learned.md` | boilerplate | no (phantom) | Does not exist at deployed path; see §Discrepancies |
| 2. Read sessions | `.workflow_artifacts/memory/sessions/` | task-specific | no | Per-session |
| 3a. Resolve task subfolder | `python3 ~/.claude/scripts/path_resolve.py` | task-specific | no | Per-invocation |
| 3b. Read architecture | `<task-root>/architecture.md` | task-specific | no | Per-invocation |
| 3c. Read current-plan | `<task_dir>/current-plan.md` | task-specific | no | Per-invocation |
| 3d. Read cost-ledger | `<task-root>/cost-ledger.md` | task-specific | no | Per-invocation |
| 4. Append cost ledger | `<task-root>/cost-ledger.md` | task-specific | no | Write |
| 5a. Read format-kit | `~/.claude/memory/format-kit.md` | boilerplate | yes | Fixed path, task-independent |
| 5b. Read glossary | `~/.claude/memory/glossary.md` | boilerplate | yes | Fixed path, task-independent |

**Per-skill aggregate — plan:** total reads: 9 | boilerplate-eligible: 2 | task-specific: 7 | preamble bytes (estimated): ~4000

---

### review

| bootstrap-step | path-read | tag | preamble-eligible | rationale |
|---|---|---|---|---|
| 1. Read lessons-learned | `.workflow_artifacts/memory/lessons-learned.md` | boilerplate | no (phantom) | Does not exist at deployed path; see §Discrepancies |
| 2. Read current-plan | `<task_dir>/current-plan.md` | task-specific | no | Per-invocation |
| 3. Read architecture | `<task-root>/architecture.md` | task-specific | no | Per-invocation |
| 4. Read critic responses | `<task_dir>/critic-response-*.md` | task-specific | no | Per-invocation |
| 5a. Read staleness | `.workflow_artifacts/cache/_staleness.md` | task-specific | no | Project-specific |
| 5b. Read cache entries | `.workflow_artifacts/cache/<repo>/...` | task-specific | no | Per-invocation |
| 6. Read git diff | `git diff <base>...HEAD` | task-specific | no | Per-invocation |
| 7. Append cost ledger | `<task-root>/cost-ledger.md` | task-specific | no | Write |
| 8a. Read format-kit | `~/.claude/memory/format-kit.md` | boilerplate | yes | Fixed path, task-independent |
| 8b. Read glossary | `~/.claude/memory/glossary.md` | boilerplate | yes | Fixed path, task-independent |

**Per-skill aggregate — review:** total reads: 10 | boilerplate-eligible: 2 | task-specific: 8 | preamble bytes (estimated): ~4000

---

### gate

| bootstrap-step | path-read | tag | preamble-eligible | rationale |
|---|---|---|---|---|
| §0 dispatch check | system context | task-specific | no | Model detection, no file read |
| Cost ledger (conditional) | `.workflow_artifacts/<task>/cost-ledger.md` | task-specific | no | Conditional on task context |

**Per-skill aggregate — gate:** total reads: 0 boilerplate reads | boilerplate-eligible: 0 | task-specific: 0-1 | preamble bytes: ~200 (frontmatter-only stub; kept for uniformity)

---

### architect

| bootstrap-step | path-read | tag | preamble-eligible | rationale |
|---|---|---|---|---|
| 1. Read lessons-learned | `.workflow_artifacts/memory/lessons-learned.md` | boilerplate | no (phantom) | Does not exist at deployed path; see §Discrepancies |
| 2. Read sessions | `.workflow_artifacts/memory/sessions/` | task-specific | no | Per-session |
| 3a. Resolve task subfolder | `python3 ~/.claude/scripts/path_resolve.py` | task-specific | no | Per-invocation |
| 3b. Read architecture | `<task-root>/architecture.md` | task-specific | no | Per-invocation |
| 3c. Read cost-ledger | `<task-root>/cost-ledger.md` | task-specific | no | Per-invocation |
| 4. Append cost ledger | `<task-root>/cost-ledger.md` | task-specific | no | Write |
| 5a. Read format-kit | `~/.claude/memory/format-kit.md` | boilerplate | yes | Fixed path, task-independent |
| 5b. Read glossary | `~/.claude/memory/glossary.md` | boilerplate | yes | Fixed path, task-independent |

**Per-skill aggregate — architect:** total reads: 8 | boilerplate-eligible: 2 | task-specific: 6 | preamble bytes (estimated): ~4000

---

## Skill-list aggregate

total spawn targets: 7 (membership: critic, revise, revise-fast, plan, review, gate, architect)
union boilerplate file set (deduplicated): {~/.claude/memory/format-kit.md, ~/.claude/memory/glossary.md}
total preamble file count across all skills: 7

---

## §Discrepancies

**Phantom lessons-learned path.** Skills critic, plan, review, and architect instruct reading `.workflow_artifacts/memory/lessons-learned.md` at bootstrap. This file does NOT exist at the deployed path. Only `quoin/memory/lessons-learned.md` exists at the source (679 bytes of mostly empty template); `install.sh` does not deploy it to `.workflow_artifacts/memory/`. Skills attempting this read fail silently. This is NOT in the preamble.

Cleanup is OUT-OF-SCOPE for Stage 2. Recommended follow-on: either (a) deploy `lessons-learned.md` via `install.sh` Step 3 (alongside CLAUDE.md) and have it auto-populated from the source, or (b) remove the bootstrap-read instruction from each affected SKILL.md and rely on users manually seeding the file.

**CLAUDE.md is NOT a bootstrap read.** Claude Code injects `CLAUDE.md` system-side (as a system-reminder in the system prompt). It is NOT read by any skill's `## Session bootstrap` step via the Read tool. This was verified by inspecting all 7 spawn target SKILL.md files — none contains a bootstrap step to read `CLAUDE.md`. This confirms the savings estimate (~4000 bytes per preamble, not ~18000 bytes). The ~20K cc/spawn estimate from the parent architecture includes the harness-injected CLAUDE.md overhead, which is separate from and not reducible by the preamble mechanism.

**implement is NOT a preamble target.** Verified `quoin/skills/implement/SKILL.md:59-81` — /implement's bootstrap reads only `.workflow_artifacts/memory/lessons-learned.md` (phantom) and task-specific paths (`<task_dir>/current-plan.md`, `architecture.md`, etc.); no format-kit or glossary at bootstrap. Dropping /implement from preamble targets is correct per round-3 MAJ-2.

---

## §Fork

**T-01 verdict: HARNESS-UNAVAILABLE**

Smoke run: `python3 quoin/scripts/verify_spawn_prompt_prefix.py`
Exit code: 2
Harness error: "Agent dispatch unavailable: no spawn function configured. In the Claude Code harness, spawn is provided by the Agent tool. Outside the harness, set verify_spawn_prompt_prefix._SPAWN_FN before calling run()."

**Root cause:** The verify script was designed assuming the Claude Code harness Agent tool would be accessible as a Python callable via a `_SPAWN_FN` override. In practice, the Agent tool is ONLY accessible to the Claude model during inference — it cannot be imported or called from a Python subprocess. When the script is run via `python3 ...` (as a subprocess from within a Claude session), the harness agent capability is not available at the Python level.

**Consequence:** The byte-transparency test (does the harness transmit spawn-prompt bytes verbatim?) cannot be verified via the current script design. The harness DOES support Agent spawning (Claude Code's `Agent` tool works correctly in practice), but there is no way to get a Python-level confirmation of SHA equality because we cannot receive the child's text response and parse it programmatically in the same Python process that called the Agent.

**Per D-01:** HARNESS-UNAVAILABLE is treated as FAIL for Stage 2 purposes. Stage 2 production code (T-03 builder, T-05 preamble files, T-06 child SKILL.md edits, T-07 parent injection) is NOT shipped.

**Alternate transport candidates (in order of preference):**

1. **On-disk shared-prefix file** (recommended for Stage 2-alt): child reads `~/.claude/skills/<skill>/preamble.md` directly at bootstrap, without any parent injection or sentinel. Parent does nothing special. Child's `## Session bootstrap` gains one read: `~/.claude/skills/<skill>/preamble.md` (if exists). This avoids the spawn-prompt-prefix mechanism entirely. No harness round-trip test needed. Savings: same (child reads preamble from disk, caches it — second spawn hits the cache). Drawback: child reads preamble on EVERY fresh session even without a parent orchestrator (slight overhead for direct user invocations). This is the lowest-risk alternate.

2. **spawn-description field** (description-hash transport): parent writes the preamble SHA to the spawn description field. Child reads `~/.claude/skills/<skill>/preamble.md` from disk and verifies the hash. Parent and child coordinate on preamble identity without injecting bytes into the prompt. But: description field is typically short (~256 chars) and its availability to the child is unconfirmed. Requires a separate harness round-trip test (simpler than the byte-transparency test).

3. **Parent-managed in-memory file cache**: parent reads preamble.md once into memory, passes it to child via the prompt (the current mechanism without the byte-transparency concern). The fundamental question — does the harness transmit prompt bytes verbatim — remains unanswered. This IS the original design; the only question is whether it works. A simpler smoke test (have a child echo its prompt's first 50 bytes) might be sufficient without the full SHA machinery.

**Recommended path:** Implement Stage 2-alt using the on-disk read approach (candidate 1). The child's bootstrap reads `~/.claude/skills/<skill>/preamble.md` directly, caching on first read. This removes the need for any parent protocol change or harness round-trip test. The preamble builder (T-03) and freshness test (T-04) remain valid — only the parent injection (T-07) and child short-circuit (T-06) need redesign.
