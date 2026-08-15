# review

Runtime-neutral intent for the review skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Verify that an implementation matches its plan and is safe for production. The
skill reads the converged plan, the architecture (when present), prior critic
responses, and the implementation diff, then writes a single review artifact
recording verdict, plan-compliance findings, integration-safety analysis,
test-coverage assessment, and risk assessment. The skill never edits source
code, never pushes to a remote, and never invokes a downstream workflow phase.

## When to use

- After implementation completes and a plan exists at
  `.workflow_artifacts/<task-name>/current-plan.md`.
- When validating that committed code matches the converged plan.
- Before invoking the post-review gate or finalization phase.
- When prior `review-*.md` exists with `CHANGES_REQUESTED` or `BLOCKED` and a
  follow-up review is needed.

## Inputs

- The converged plan at `.workflow_artifacts/<task-name>/current-plan.md`
  (required; all other inputs are optional-tolerant).
- `architecture.md` at the task root (always at `<task-root>/architecture.md`;
  missing file = no-op).
- Prior `critic-response-*.md` files in the resolved task path (used to verify
  issues were addressed; missing files = no-op).
- The task feature spec at `.workflow_artifacts/<task-name>/spec.md` (always at
  the task root; read-if-exists — absence is a normal, non-blocking outcome).
- The version-control diff against the merge base — the exact set of files
  changed by the implementation.
- Prior `review-*.md` siblings for context on earlier verdicts.
- Optional knowledge-cache entries under `.workflow_artifacts/cache/`; absence
  is a non-fatal skip.

All reads MUST tolerate missing files except the plan, which is required.

## Output

A single artifact under `.workflow_artifacts/<task-name>/`, named with the
pattern `review-N.md` where N is the round number starting at 1 (path resolved
by the runtime adapter's path resolver). Closed section set: Summary, Verdict,
Plan Compliance, Spec Compliance, Issues Found, Integration Safety, Test
Coverage, Risk Assessment, Recommendations, and the optional Dimension
Verdicts (present only on a merged multi-dimension review — see Fan-out
below). The skill also updates a session-state file under
`.workflow_artifacts/memory/sessions/`.

Verdict is one of three closed values: `APPROVED`, `CHANGES_REQUESTED`,
`BLOCKED`.

## Fan-out (profile-conditional)

The skill reads the task profile (from the plan's convergence summary, or the
session state). A Small task runs a single-pass review — one artifact write,
no additional subagents. A Medium or Large task (or an undetermined profile,
which defaults to Medium — more review, not less) fans out into three
parallel dimension passes — security, performance, architecture/integration —
each returning a verdict and dimension-tagged issues; the runtime adapter
merges these into one artifact with a worst-of verdict
(`BLOCKED` > `CHANGES_REQUESTED` > `APPROVED`) and an optional Dimension
Verdicts table. On a Large task, the security dimension is delegated to the
standalone security-review skill's fan-out contract rather than an inline
security pass. The dimension subagents never synthesize the artifact's For
human, Summary, Plan Compliance, Spec Compliance, or Test Coverage sections —
those remain owned by the parent review session in every profile.

A plan may carry a review-shape override recorded by an upstream fast route
(a `Review shape: single-pass (fast-path)` marker). When present, the
override takes precedence over both profile inference and the
undetermined-profile default above: a Small, Medium, or undetermined profile
carrying the override runs the single-pass path instead of fanning out. A
Large profile carrying the override is the one exception — it still runs the
single-pass path for the performance and architecture/integration
dimensions, but the security dimension stays on the standalone security-review
skill's fan-out contract unconditionally, exactly as on a plain Large task; a
route override never suppresses the Large security guarantee.

## Behavior contract

- Shipped authored content (comments, commit messages, PR descriptions) MUST follow the clean-authored-content rule: plain engineering language, no plan/decision/finding IDs, severities, review-round narration, gate verdicts, or planning-artifact paths.
- The diff MUST be read in full; full files are read selectively when
  structural, security, integration, or prior-critic-flagged signals fire.
- Tests MUST be executed, not just read.
- The skill MUST NOT auto-create a pull request, push to a remote, or invoke a
  finalization phase.
- Each issue MUST cite a specific file:line reference and propose a fix.
- The skill produces a Spec Compliance assessment checking the implementation
  against the task feature spec's acceptance criteria; when no spec exists, it
  records that verification was against the plan only (grandfather). The skill
  reads `.workflow_artifacts/<task-name>/spec.md` at bootstrap when present.
- Verdict-conditional behavior: on `APPROVED`, the skill yields control to the
  post-review gate via the runtime adapter's mechanism; on `CHANGES_REQUESTED`
  or `BLOCKED`, control returns to the implementation phase.
- Cost-ledger writes are mandatory when a task context is active.
- After the phase completes, the skill MUST emit a concise human-readable
  summary of the step's outcome to the user as its final message, independent
  of any gate rendering; the summary restates the artifact's substance in
  plain language because the stored artifact may be in a compressed format.
- The review MUST flag, as at least a MAJOR issue, any task commits found on a
  protected branch (a placement backstop computed independently of the review
  diff basis — earlier phases should have caught it; if they didn't, this is the
  last line of defense). The MAJOR issue writeup MUST include a pointer to the
  canonical safe reset-to-origin recovery recipe at `memory/branch-recovery.md`
  (deployed Tier-1 memory file).

## Out of scope

- Code edits of any kind.
- Remote push or pull-request creation.
- Auto-invocation of the implementation phase.
- Auto-invocation of the finalization phase.
- Any dependency on a specific runtime, model tier, or dispatch mechanism.

## v3-format detection rule

The format of `current-plan.md` is determined by the following verbatim rule.
Every runtime adapter that reads a v3 plan MUST apply this rule identically.

# v3-format detection (architecture.md §5.7.1 — copy verbatim)
# A file is v3-format iff:
#   - the first 50 lines following the closing `---` of the YAML frontmatter
#     contain a heading matching the regex ^## For human\s*$
# Otherwise the file is v2-format.
# On v3-format detection: read sections per format-kit.md for this artifact type.
# On v2-format (or no frontmatter): read the whole file as legacy v2.
# Detection MUST be string-comparison only — no LLM call (per lesson 2026-04-23
# on LLM-replay non-determinism).

## Notes

- The set of verdict values is closed (`APPROVED` / `CHANGES_REQUESTED` /
  `BLOCKED`); a runtime adapter must not silently introduce new values.
- The closed section set above mirrors what runtime adapters serialize as the
  review artifact's body.
- The decision of which subagent dispatch mechanism to use is runtime-specific
  and lives in the runtime adapter's own skill definition, not in this contract
  doc.
- The post-review gate invocation mechanism (inline vs subagent) is
  runtime-specific and lives in the runtime adapter's own skill definition.
- The runtime adapter uses the runtime adapter's strongest model tier for
  review; the specific model name and dispatch mechanism are out of scope for
  this contract doc.
