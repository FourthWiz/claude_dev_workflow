---
name: discover
description: "Scans all repositories in the project folder and saves a comprehensive inventory, architecture overview, and dependency map to memory. Use this skill for: /discover, 'scan my repos', 'map the codebase', 'what repos do I have', 'index the project', 'save the architecture', 'learn my codebase'. Run this when you first set up the workflow in a new project folder, or when repos have changed significantly. The output feeds into /architect, /plan, /critic, and /review so they have baseline context."
model: opus
---

# Discover

You scan all repositories in the project folder and produce a structured inventory that gets saved to memory. This is the "onboarding" step — run it once when you set up the workflow, and again whenever the repo landscape changes.

## Model requirement

Uses the strongest model (Opus) because understanding how services relate requires deep reasoning across multiple codebases.

## Session bootstrap

Cost tracking note: `/discover` can run standalone (no task context) or as part of a task via `/run`. Only append to the cost ledger if a task name was explicitly provided or is determinable from the invocation context. If running standalone, skip cost recording.

If a task context is active: append your session to `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `discover`.

## What to scan

### Incremental scan — skip unchanged repos

Before scanning each repo, check if a previous scan recorded the repo's HEAD commit:

1. Read `.workflow_artifacts/memory/repo-heads.md` if it exists. This file maps repo names to their `git rev-parse HEAD` values from the last `/discover` run.
2. For each repo in the project folder, run `git rev-parse HEAD` and compare against the stored value.
3. **If HEAD matches the stored value: skip the full scan for that repo.** Its inventory, dependencies, and API surface have not changed. Report to the user: "Skipping <repo-name> — unchanged since last scan (HEAD: <short-hash>)."
4. **If HEAD differs or no stored value exists: perform the full scan** as described below.
5. After completing all scans, overwrite `.workflow_artifacts/memory/repo-heads.md` with the current HEAD values for all repos (including unchanged ones).

Format for `.workflow_artifacts/memory/repo-heads.md`:

| Repo | HEAD |
|------|------|
| <repo-name-1> | <full-sha> |
| <repo-name-2> | <full-sha> |

**Important:** When the user explicitly requests a full re-scan (e.g., "rescan everything", "force rediscover"), ignore the HEAD cache and scan all repos.

Starting from the project root folder, examine every top-level directory. For each repository/service found:

### Per-repo inventory

1. **Identity**
   - Repo name (directory name)
   - Primary language(s) and framework(s) (detect from package.json, go.mod, Cargo.toml, requirements.txt, pom.xml, build.gradle, etc.)
   - Runtime/platform (Node.js, Go, Python, JVM, etc.)
   - Build system (npm, yarn, pnpm, make, gradle, maven, cargo, etc.)

2. **Structure**
   - Key directories and what they contain (src/, lib/, api/, cmd/, internal/, etc.)
   - Entry points (main files, index files, server startup)
   - Configuration files and what they control
   - Test structure (where tests live, test framework used)

3. **External dependencies**
   - Key libraries/frameworks (not every transitive dep — the important ones that define the architecture)
   - External services called (from config files, environment variables, API client code)
   - Database connections (type, connection strings patterns)
   - Message queues, event buses, cache systems

4. **API surface**
   - Exposed endpoints (REST routes, GraphQL schemas, gRPC protos)
   - Published events/messages
   - Shared libraries or packages exported

### Cross-repo analysis

After scanning individual repos, analyze how they connect:

1. **Service communication map**
   - Which service calls which (HTTP, gRPC, message queues)
   - Trace the connections by matching: API client code in one repo → endpoint definitions in another
   - Shared databases (multiple services reading/writing the same DB)
   - Shared message topics/queues (publishers and consumers)

2. **Dependency graph**
   - Shared internal libraries or packages
   - Common configuration or infrastructure patterns
   - Deployment dependencies (what must deploy before what)

3. **High-level architecture**
   - System purpose — what does this collection of services do together?
   - Request flow — how does a typical user request flow through the system?
   - Data flow — where does data enter, how is it transformed, where does it end up?
   - Key architectural patterns (microservices, monolith, event-driven, CQRS, etc.)

## How to scan

Use a combination of approaches for efficiency:

- **File patterns** — glob for known config files (package.json, go.mod, docker-compose.yml, etc.) to quickly identify repos and their tech stacks
- **Grep for connections** — search for HTTP client calls, database connection strings, queue publish/subscribe patterns, environment variable usage
- **Read key files** — entry points, route definitions, config files, README files, docker-compose, Makefiles
- **Don't read everything** — this is a survey, not a deep dive. Read enough to understand the architecture, not every line of business logic.

Use subagents to scan repos in parallel when possible.

## Output

Save all findings to `<project-folder>/.workflow_artifacts/memory/`:

### `repos-inventory.md`

```markdown
# Repository Inventory

Last scanned: <date>

## <repo-name-1>

- **Language:** TypeScript
- **Framework:** NestJS
- **Runtime:** Node.js 18
- **Build:** yarn
- **Purpose:** <1-2 sentence description>
- **Key directories:**
  - `src/modules/` — feature modules
  - `src/common/` — shared utilities
  - `test/` — Jest tests
- **Entry point:** `src/main.ts`
- **Key dependencies:** TypeORM, Redis (ioredis), Kafka (kafkajs)
- **Exposed APIs:** REST on port 3000 (see `src/modules/*/controller.ts`)
- **External calls:** Payment service (HTTP), User service (gRPC), PostgreSQL, Redis, Kafka

## <repo-name-2>
...
```

### `architecture-overview.md`

```markdown
# Architecture Overview

Last scanned: <date>

## System purpose
<What this system does, who uses it, 3-5 sentences>

## Service map

<ASCII diagram or structured description of how services connect>

Example:
```
[API Gateway] → [User Service] → [PostgreSQL]
                                → [Redis cache]
             → [Payment Service] → [Stripe API]
                                  → [PostgreSQL]
             → [Notification Service] ← Kafka ← [Payment Service]
                                     → [SendGrid API]
```

## Communication patterns

### Synchronous (HTTP/gRPC)
- <service A> → <service B>: <what for> (<protocol>)

### Asynchronous (queues/events)
- <topic/queue>: published by <service>, consumed by <service(s)> — <what for>

### Shared data stores
- <database/cache>: accessed by <services> — <what data>

## Request flows

### <Flow 1: e.g., User registration>
1. Client → API Gateway → ...
2. ...

### <Flow 2: e.g., Payment processing>
1. ...

## Key architectural decisions
- <Pattern or decision and why it was made, if apparent from the code>

## Deployment topology
- <What deploys where, if discoverable from docker-compose, k8s configs, CI files>
```

### `dependencies-map.md`

```markdown
# Cross-Service Dependencies

Last scanned: <date>

## Dependency graph

### <Service A>
- **Depends on:** <Service B> (HTTP, for auth), PostgreSQL, Redis
- **Depended on by:** <Service C> (Kafka events), <API Gateway> (HTTP)

### <Service B>
...

## Shared resources
- **PostgreSQL (main):** used by <services>
- **Redis:** used by <services> — <for what>
- **Kafka topics:**
  - `payment.completed`: published by Payment, consumed by Notification, Analytics
  - ...

## Deployment order constraints
- <Service B> must be available before <Service A> (hard dependency on auth endpoint)
- <Database migrations> must run before any service deployment

## Integration risks
- <Known fragile integration points, tight coupling, missing error handling observed>
```

### `git-log.md`

As part of discovery, also capture recent git activity across all repos. This gives every downstream skill context on what's been changing and why.

```bash
# For each repo
git -C <repo-path> log --all --oneline --date=short --format="%h %s — %ad" -20
```

For each commit, briefly describe the *logic* of the change (not just file names):
```bash
git -C <repo-path> diff-tree --no-commit-id --name-status -r <hash>
```

Format:

```markdown
# Recent Git Activity

Last updated: <datetime>

## <repo-name>
### <branch-name>
- `<short-hash>` <commit message> — <date>
  <1-line: what changed and why — the logic, not just files>
- `<short-hash>` ...

## <other-repo>
...
```

Keep the last ~50 commits across all repos, newest first. The goal is that any skill reading this file understands the recent momentum and direction of the project.

## After scanning

Tell the user:
- How many repos were found
- Brief summary of the architecture
- Recent git activity highlights (what's been actively worked on)
- Any interesting findings (tight coupling, missing tests, potential risks observed)
- These files are now available to `/architect`, `/plan`, `/critic`, `/review`, and `/start_of_day` as baseline context
- Which repos were skipped (unchanged since last scan) and which were re-scanned

## When to re-run

Suggest re-running `/discover` when:
- New repos are added to the project folder
- Major architectural changes happen (new services, new communication patterns)
- Before a large `/architect` session to ensure context is fresh
- `/start_of_day` finds the git-log.md is stale (it will suggest this)
- When you want to force a full re-scan regardless of HEAD changes (say "rescan all repos" or similar)
