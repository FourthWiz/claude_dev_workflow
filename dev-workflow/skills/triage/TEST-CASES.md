# /triage Test Cases

## Instructions for reviewer

Run each test case manually by invoking `/triage` with the prompt and the described state setup, then record what the skill actually did in the **Reviewer observed** column, mark **Pass/Fail**, and add notes.

**Success target: ≥ 15 of 18 test cases must Pass** for the implementation to be considered production-ready.

Column definitions:
- **#** — test case number
- **Prompt** — exact text to submit as the user message after `/triage` is invoked (or as the argument)
- **State setup** — describe filesystem/git state required; "default" means the current dev-workflow project state
- **Expected skill** — the skill `/triage` should propose
- **Expected side-effects** — what `/triage` must NOT do (e.g., no `Skill` tool call) and what it should output
- **Reviewer observed** — fill in during review
- **Pass/Fail** — P or F
- **Notes** — any deviation or clarification

---

| # | Prompt | State setup | Expected skill | Expected side-effects | Reviewer observed | Pass/Fail | Notes |
|---|--------|-------------|---------------|----------------------|-------------------|-----------|-------|
| 1 | "I want to plan a retry mechanism." | No task folder (or create a clean temp dir). No `current-plan.md` anywhere. | `/thorough_plan` | Proposes `/thorough_plan`; prints `→ Type /thorough_plan to proceed.` after confirmation; no `Skill` tool call. | | | Signal B: "plan" keyword + no plan exists → `/thorough_plan` boosted over `/plan`. |
| 2 | "can you check my implementation?" | `current-plan.md` found under active task folder (recursive). Recent commits on task branch (`git log --since=1.day` non-empty). No `review-*.md` in task dir. | `/review` | Proposes `/review`; prints `→ Type /review to proceed.` after confirmation; no `Skill` tool call. | | | Signal C: plan + recent commits + no review → `/review` +2. Disambiguation table: "check" + plan + commits → boost `/review`, suppress `/critic`. |
| 3 | "let's start writing the code." | Plan found recursively. No recent commits today. | `/implement` | Prints `→ Type /implement to proceed.` after confirmation; no `Skill` tool call at all — not even after affirmation. | | | **Propose-only verification.** Signal C: plan found → `/implement` +2. |
| 4 | "we're done, push it up." | Latest `review-*.md` in active task dir contains "APPROVED". | `/end_of_task` | Prints `→ Type /end_of_task to proceed.` after confirmation; no `Skill` tool call. | | | Signal C: APPROVED review → `/end_of_task` +2. Disambiguation: "push"/"done" + APPROVED → boost `/end_of_task`. |
| 5 | "plan this." | No task context. No `current-plan.md` anywhere. | Ambiguous: `/thorough_plan` and `/plan` ranked 1-2 | Ambiguous-candidate flow with both listed; no invocation until user picks; after picking, propose-only output. | | | Both score similar; `/thorough_plan` slightly higher from state boost. |
| 6 | "check the plan." | Plan exists at any depth. No recent commits. | `/critic` | Proposes `/critic`; disambiguation table: "check" + plan + no recent commits → `/critic` boosted; `/review` suppressed. | | | Signal B: "check the plan" → `/critic` trigger phrase. Signal C: plan found + no commits → critic over review. |
| 7a | "session stuff." | Today's daily cache exists: `.workflow_artifacts/memory/daily/<today>.md`. | `/end_of_day` | Proposes `/end_of_day`; Signal C: daily cache exists → `/end_of_day` +1, `/start_of_day` −1. | | | State A half of TC-7. |
| 7b | "session stuff." | No daily cache for today AND no session file for today. | `/start_of_day` | Proposes `/start_of_day`; Signal C: no cache + no session → `/start_of_day` +2. | | | State B half of TC-7. |
| 8 | "help." | Any state. | Decline flow | Decline flow triggered (vague single word); one clarifying question asked ("Are you planning new work, reviewing existing work, or wrapping up?"); if user responds "maybe" → hard exit: "I couldn't determine which skill fits..."; no skill invoked at any point. | | | Tests one-question cap and hard exit. |
| 9 | "do the thing and ship it." | `review-*.md` with "APPROVED" exists in active task dir. | `/end_of_task` | Proposes `/end_of_task`; after affirmation prints `→ Type /end_of_task to proceed.`; no `Skill` tool call — this is a **High-impact** skill and must still be propose-only. | | | Verifies universal propose-only for high-impact skills. |
| 10 | "/triage /plan something." | Any state. | `/plan` | Signal A fires on `/plan` token; score 3; single-candidate flow; proposes `/plan` with rationale; prints `→ Type /plan to proceed.` after confirmation. | | | Signal A short-circuit test. |
| 11 | "what do I do?" | No `.workflow_artifacts/` directory at project root. | `/init_workflow` | Proposes `/init_workflow`; Signal C: no `.workflow_artifacts/` → `/init_workflow` +2, all task-execution skills −1 each. | | | Tests no-workflow-artifacts state. |
| 12 | "let's wrap up the week." | Local date is Friday (`date +%u` == 5). | `/weekly_review` | Proposes `/weekly_review`; Signal C: Friday → +1 to `/weekly_review`. | | | Friday heuristic test. Must use local timezone (correct behavior of `date +%u`). |
| 13 | "what should I do next?" | Multiple active task folders exist (e.g., `triage/` and `memory-cache/`). Prompt does NOT name either. | Any reasonable skill; cost recording skipped | No cost-ledger row appended to any task's ledger. Skill proposal may be ambiguous or state-driven. | | | Tests explicit-only cost recording: no task named → no ledger write. |
| 14 | "/triage task=auth-refactor plan this." | `auth-refactor/` folder exists under `.workflow_artifacts/`. | `/thorough_plan` | One ledger row appended to `.workflow_artifacts/auth-refactor/cost-ledger.md`. Proposes `/thorough_plan`. | | | Tests explicit-only cost recording: task named → ledger row written. |
| 15 | "let's implement." | `current-plan.md` lives at `.workflow_artifacts/memory-cache/stage-2/current-plan.md` — NOT at task root. No plan at the task root level. | `/implement` | Plan-exists signal fires (recursive `find` detects nested plan); `/implement` boosted (+2); NOT routed to `/plan` or `/thorough_plan`. | | | Tests CRIT-3 fix: recursive plan detection via `find` maxdepth 4. |
| 16 | "I'm not sure what to do next, the tests failed after the last commit." | Any state with recent commits and an active task. | `/review` or `/implement` | Trigger phrase "I'm not sure what to do next" stripped before Signal B scoring. Remaining text "tests failed after the last commit" scored. State: recent commits + plan → `/review` or `/implement` proposed (either is acceptable). No `/init_workflow` or other unrelated skill. | | | Tests MAJ-8 trigger-phrase stripping. |
| 17 | "/triage /revise-fast." | Any state. | `/revise` (substituted) | Signal A fires on `/revise-fast`; router substitutes `/revise` in proposal; note printed: "`/revise-fast` is an internal variant; proposing `/revise` instead."; no `/revise-fast` in output. | | | Tests `revise-fast` hidden/substitution rule. |
| 18 | "hmm." (then user replies "maybe" to clarifying question) | Any state. | Hard exit after one clarifying question | `/triage` asks one clarifying question ("Are you planning new work, reviewing existing work, or wrapping up a completed task?"). User replies "maybe". `/triage` prints hard-exit message and stops. No second question. No skill invoked. | | | Tests one-clarification-question hard cap. |
