# Lessons Learned

<!-- Add entries using the format:
## <date> — <task-name>
**What happened:** <the surprise, failure, or insight>
**Lesson:** <the reusable takeaway>
**Applies to:** <which skills should pay attention — /plan, /critic, /implement, etc.>
-->

## 2026-01-10 — jsonl-cost-parsing
**What happened:** When adding a "today" filter to JSONL cost parsing, the filter must be applied per-row at parse time, not as a pre-filter on ledger rows, because each JSONL file accumulates lifetime data.
**Lesson:** Apply date filters per-row in JSONL cost parsing; pre-filtering over ledger rows silently sums all-time costs.
**Applies to:** /implement — any task involving JSONL cost parsing or stacked branches.

## 2026-01-11 — stacked-branch-upstream
**What happened:** Stacked branch (feature-A on feature-B) causes affected_tests.py exit 1 due to no configured upstream — sweeps in unrelated scripts; not a real test failure.
**Lesson:** Always configure upstream on stacked branches to avoid affected_tests.py false exits.
**Applies to:** /gate — stacked branch workflows.

## 2026-01-12 — database-migration
**What happened:** Running migrations without a backup on a shared development database caused an outage affecting three teams for two hours.
**Lesson:** Always back up databases before running migrations, even in development environments.
**Applies to:** /rollback — database migration tasks.

## 2026-01-13 — react-component-refactor
**What happened:** Inline CSS styles were scattered across 47 components, making theming changes require touching every file.
**Lesson:** Centralize theme values in a design token file from the start; retrofitting is costly.
**Applies to:** /end_of_task — frontend tasks involving components or theming.

## 2026-01-14 — api-rate-limiting
**What happened:** Third-party API rate limits were not tested under load; the service degraded silently in production when limits were hit.
**Lesson:** Test rate limiting behavior explicitly under load; implement exponential backoff and circuit breakers.
**Applies to:** /end_of_day — tasks involving external API integration.

## 2026-01-15 — cost-ledger-row-format
**What happened:** The cost ledger parser failed silently on rows with missing FALLBACK_FIRES column (6-col vs 7-col format mismatch).
**Lesson:** Parsers must tolerate both 6-col and 7-col cost ledger row formats; use a column-count check before accessing index 6.
**Applies to:** /implement — any task touching the cost ledger parser or JSONL cost data.

## 2026-01-16 — session-uuid-capture
**What happened:** Session UUIDs were captured via an environment variable that was set too late in the hook lifecycle, causing spurious empty-UUID rows in the cost ledger.
**Lesson:** Capture session UUID at the start of each skill session, before any ledger writes; validate non-empty before appending.
**Applies to:** /start_of_day — tasks involving session-state or cost ledger writes.

## 2026-01-17 — git-worktree-dispatch
**What happened:** WorktreeCreate command hooks must actually run git worktree add themselves and print the created path to stdout. Early plan assumed output was JSON with a worktreePath key.
**Lesson:** Before designing a hook mechanism, verify the exact I/O contract from the official docs; plain path to stdout, not JSON.
**Applies to:** /end_of_day — future hook-driven dispatch design.

## 2026-01-18 — installer-script-lists
**What happened:** A new wrapper script was added to DEPLOYED_SCRIPTS but not CORE_SCRIPTS; the wrapper's parents[1]/core/scripts/ resolution fails at runtime.
**Lesson:** When adding a new wrapped Python script, always update both DEPLOYED_SCRIPTS and CORE_SCRIPTS in installer.py.
**Applies to:** /end_of_task — any task adding a new wrapped Python script to quoin installer.

## 2026-01-19 — memory-index-drift
**What happened:** A generated MEMORY-INDEX.md became stale after a lesson was appended but the index was not regenerated.
**Lesson:** Staleness of a generated index is advisory, not a hard error; selection falls back to tag-filter then wholesale.
**Applies to:** /end_of_day — tasks involving generated index artifacts.

## 2026-01-20 — test-fixture-sizing
**What happened:** A superset gate test used a 10-entry fixture; with MIN_RESULTS=5 and MAX_FRACTION=0.6, the wholesale fallback triggered on any select() returning 6+ entries.
**Lesson:** Size test fixtures large enough (at least 14 entries) that the matcher path is exercised, not the wholesale fallback.
**Applies to:** /gate — tasks that include non-regression superset gate tests for selection algorithms.

## 2026-01-21 — cli-argument-parsing
**What happened:** argparse's add_subparsers without required=True silently swallowed unknown subcommands, returning success with no action taken.
**Lesson:** Always set subparsers required=True in Python CLI tools to catch unrecognized subcommands at parse time.
**Applies to:** /rollback — CLI tooling tasks using argparse with subcommands.

## 2026-01-22 — dockerfile-layer-caching
**What happened:** Placing COPY . . before RUN pip install invalidated the pip cache layer on every source file change, slowing CI by 4 minutes per build.
**Lesson:** Copy requirements files first, run install, then copy source to maximize Docker layer cache hits.
**Applies to:** /pr — tasks involving Docker image builds.

## 2026-01-23 — preamble-quoin-home-token
**What happened:** The __QUOIN_HOME__ token was used correctly in the main SKILL.md body but missed inside a pseudocode block in a proc: section.
**Lesson:** Use __QUOIN_HOME__ in ALL shell source paths in SKILL.md, including pseudocode inside proc: blocks.
**Applies to:** /gate — skills involved in SKILL.md modifications.

## 2026-01-24 — branch-hygiene-enforcement
**What happened:** Three critic rounds were needed because the exact trigger placement for the guard block was not specified precisely enough in the plan.
**Lesson:** When adding enforcement blocks, specify the condition exactly in the plan; vague language leads to critic findings.
**Applies to:** /end_of_task — tasks adding enforcement blocks or guard conditions.

## 2026-01-25 — kubernetes-networking
**What happened:** Pod-to-pod communication failed intermittently because the NetworkPolicy was too restrictive and blocked health check traffic from the kubelet.
**Lesson:** Always include kubelet health check CIDR ranges in NetworkPolicy ingress rules; test health checks explicitly.
**Applies to:** /pr — Kubernetes networking tasks.
