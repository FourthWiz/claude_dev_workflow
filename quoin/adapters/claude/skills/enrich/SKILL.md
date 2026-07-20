---
name: enrich
description: "Sharpens a raw task prompt into a clearer, better-grounded one before /specify — fills genuine gaps via a small set of targeted questions, writes enriched-prompt.md, and echoes it in chat. Use this skill for: /enrich, 'sharpen this prompt', 'tighten this task description', 'fill in the gaps before we spec this'. Distinct from /specify (which elicits a full structured spec) and /triage (which only routes); /enrich never writes a spec/plan and never invokes a downstream phase."
model: opus
---

# Enrich

*Portable intent doc: `quoin/core/skills/enrich.md`*

You sharpen a raw, loosely-worded task prompt into a clearer, better-grounded one — upstream of `/specify`. You do not write a structured spec, an architecture, or a plan; that is `/specify`'s and `/architect`'s job. Your only output is a single enriched-prompt artifact plus a chat echo. When the raw prompt is already clear and well-grounded, you say so and stop — enrichment is not busywork performed for its own sake.

## §0' Pollution dispatch (execute after §0 / §0c if present — before skill body)

This skill runs in the user's current session. If the session is polluted (high context from
prior work), self-dispatch as a fresh subagent to avoid paying the pollution tax.

Detection:
  - Read the most-recent session-state file: `.workflow_artifacts/memory/sessions/<today>-<task>.md`
    OR the fallback `.workflow_artifacts/memory/pollution-score-latest.txt`.
  - Parse the `pollution_score: N` field (integer).
  - If N >= POLLUTION_THRESHOLD (default: env QUOIN_POLLUTION_THRESHOLD or 5000):
    session is polluted.
  - Sentinel check: if the user's prompt starts with `[no-redispatch]`: skip dispatch.
  - If a prior §0 dispatch already fired in this session: already in fresh context, skip §0'.

Dispatch action (when pollution detected AND no sentinel AND no prior §0 dispatch):
  Determine dispatch contract fields:
    - Extract the raw task description/prompt from the user's invocation.
    - Resolve the task dir via path_resolve.py (no --stage — enriched-prompt.md is
      always at task root).
    - The enriched prompt is written to `.workflow_artifacts/<task>/enriched-prompt.md`.

  If task description cannot be determined:
    Emit: `[quoin-S-1: cannot extract per-skill dispatch contract; running in main]`
    Proceed with skill body.

  Otherwise spawn an Agent subagent:
    model: "opus"
    description: "enrich — pollution-isolated dispatch"
    prompt: "[no-redispatch]\n/enrich <task description>\nEnriched prompt output path: .workflow_artifacts/<task>/enriched-prompt.md"

  Wait for the subagent. Return its output as your final response. STOP.

Fail-OPEN path:
  If Agent tool unavailable or errors — classify the error first:
  - 1M-credit-class: if the error text contains the substring
      `Usage credits required for 1M context`:
      The §0' opus dispatch hit a 1M-context credit mismatch (IVG-89). Detection via
      model-name is impossible; this post-dispatch error string is the only reliable signal.
      Issue an `AskUserQuestion`:
        Question: "§0' opus dispatch failed with a 1M-context credit mismatch for /enrich.
        The parent session carries the 1M-context beta header which propagates to all
        subagent calls; Opus lacks 1M credits. How would you like to proceed?"
        Header: "1M credit mismatch"
        multiSelect: false
        Option 1:
          label: "Abort — I'll switch with /model first"
          description: "Stop here. Run /model in your terminal to switch to a
          standard-context model (e.g., /model opus), then re-invoke /enrich.
          The §0' dispatch will then land on standard Opus successfully."
        Option 2:
          label: "Proceed in-session at parent tier"
          description: "Skip the §0' dispatch this once. /enrich runs in the
          current session (may be polluted, but works). Emits a one-line advisory."
      On Option 1: print `[quoin: 1M-context credit mismatch; abort per user choice —
      switch with /model and re-invoke /enrich]` and STOP. Do NOT proceed to skill body.
      On Option 2: print `[quoin: 1M-context credit mismatch; proceeding in-session at
      parent tier — run /model to switch to standard context for a permanent fix]` and
      proceed with skill body.
  - Any other error (non-1M): Issue an `AskUserQuestion` (generic wording):
      Question: "§0' pollution dispatch failed for /enrich. Would you like to proceed
      in the current (polluted) session, or abort?"
      Header: "Dispatch error"
      multiSelect: false
      Option 1:
        label: "Abort — I'll diagnose and retry"
        description: "Stop here. Investigate the dispatch error, then re-invoke /enrich."
      Option 2:
        label: "Proceed in-session (polluted)"
        description: "Continue in the current session despite the dispatch failure.
        Performance may be degraded due to context pollution."
      On Option 1: print `[quoin-S-1: pollution dispatch unavailable; proceeding in current session]`
      and STOP. Do NOT proceed to skill body.
      On Option 2: print `[quoin-S-1: pollution dispatch unavailable; proceeding in current session]`
      and proceed with skill body.

Otherwise (score below threshold OR sentinel OR §0 dispatched OR session-state unreadable):
proceed to skill body.

## §0″ Minimum-tier guard (execute after §0 / §0c / §0’ if present — before skill body)
This skill is declared model: "opus". If the executing agent is running on a model
strictly CHEAPER than opus, it silently up-dispatches to an Opus subagent (mirrors §0 down-dispatch).

<!-- §0doubleprime-begin -->
Detection:
  - Read your current model from system context ("powered by the model named X").
  - Tier order: haiku < sonnet < opus. declared_tier = opus.
  - Disable switch: if env QUOIN_DISABLE_MINTIER_GUARD=1 → skip entirely, proceed to skill body
    (silent skip — no advisory; this is explicit opt-out behavior by design).
  - Sentinel: if the prompt starts with bare [no-redispatch] → skip, proceed to skill body.
  - Fire condition: current_tier < declared_tier AND no [no-redispatch] AND guard not disabled.

On fire (happy path — silent up-dispatch):
  spawn an Agent subagent:
    model: "opus"
    description: "enrich — min-tier up-dispatch"
    prompt: "[no-redispatch]\n<original user input verbatim>"
  Wait for the subagent. Return its output as your final response. STOP.

Fail-OPEN path (fires only when Agent dispatch fails):
  Classify the error text BEFORE proceeding:

  - 1M-credit-class: if error text contains `Usage credits required for 1M context`:
      Issue AskUserQuestion:
        Question: "§0″ up-dispatch to opus failed with a 1M-context credit mismatch for /enrich.
        The parent session carries the 1M-context beta header; Opus lacks 1M credits. How would you like to proceed?"
        Header: "1M credit mismatch"
        multiSelect: false
        Option 1:
          label: "Abort — I'll switch with /model first"
          description: "Stop here. Run /model in your terminal to switch to a standard-context
          model (e.g., /model opus), then re-invoke /enrich."
        Option 2:
          label: "Proceed in-session at parent tier"
          description: "Skip the up-dispatch this once. /enrich runs in the current session
          (below Opus, but works). Emits a one-line advisory."
      On Option 1: print `[quoin-mintier: 1M-context credit mismatch; abort per user choice —
      switch with /model and re-invoke /enrich]` and STOP.
      On Option 2: print `[quoin-mintier: 1M-context credit mismatch on opus up-dispatch;
      proceeding in-session at parent tier — run /model to switch to standard context]`
      and proceed to skill body (treat as bare [no-redispatch]).

  - Any other error: Issue AskUserQuestion (labels verbatim — drift relies on equality):
      Question: "/enrich requires Opus but this session is below Opus. Auto-dispatch to Opus failed. How would you like to proceed?"
      Header: "Min-tier"
      multiSelect: false
      Option 1:
        label: "Abort — run from an Opus session"
        description: "Stop here. Switch the session to Opus (/model opus) and re-invoke /enrich."
      Option 2:
        label: "Proceed at current tier (under-powered)"
        description: "Run /enrich on the current cheaper model. Quality may be reduced;
        emits a one-line advisory."
    Then:
      - Option 1: print `[quoin-mintier: aborted; re-invoke /enrich from an Opus session]` and STOP.
      - Option 2: print `[quoin-mintier: min-tier up-dispatch unavailable; proceeding at current tier per user choice]`, then proceed to skill body (treat as bare [no-redispatch]).
<!-- §0doubleprime-end -->

## Session bootstrap

This skill may run in a fresh chat session with no prior context. On start:
1. Read `.workflow_artifacts/memory/lessons-learned.md` for insights relevant to prompt framing and past enrichment mistakes.
2. Read `.workflow_artifacts/memory/repos-inventory.md`, `architecture-overview.md`, and `dependencies-map.md` (if they exist) — this is your grounding context for judging whether the raw prompt has genuine gaps against the real codebase, not guessed ones.
3. Read `.workflow_artifacts/memory/sessions/` for any active session state for this task.
4. Resolve the task dir via `python3 __QUOIN_HOME__/scripts/path_resolve.py --task <task-name>` (no `--stage` flag — `enriched-prompt.md` is ALWAYS at the task root, mirroring `spec.md`). If exit code 2: display stderr verbatim, fall back to the task root, and ask the user to disambiguate. Read `<task-root>/spec.md` if it already exists — a prior spec is useful grounding context (do not duplicate it; enrichment is upstream of specify, not a replacement for it).
5. Append your session to the cost ledger: `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `enrich`.
6. Then proceed with the work below.

## Process

Analyze the raw prompt against the grounding context gathered above (real repo structure, real dependencies, any prior spec) — look for genuine gaps: missing target repo/file, ambiguous scope boundary, an assumption that contradicts what `/discover` found, an unstated constraint the codebase implies. Do not invent gaps that aren't there.

**If the prompt is already clear and well-grounded:** report "no material enrichment needed" and stop. Still write `enriched-prompt.md` (Output below) so downstream skills have a stable artifact to point at, but keep the Enriched prompt section nearly identical to the raw input and the Assumptions/Open questions sections empty or near-empty.

**If gaps exist:** use `AskUserQuestion` with a SMALL, focused set of questions (2-3 pointed questions, not a form) targeting only the genuine gaps found — never re-ask what the raw prompt already answers.

- **Interactive session:** fold the user's answers into the enriched prompt directly.
- **Non-interactive dispatch (no way to ask):** produce a best-effort rewrite of the prompt, explicitly flag every assumption you made to fill a gap, and list the exact questions you would have asked as a "questions I would have asked" section — never silently guess without flagging it.

## Output

Write a single artifact, `<task-root>/enriched-prompt.md`, as a **Class A** artifact (always-English; no terse body).

**Write mechanism:** compose the full file content and write to `<task-root>/enriched-prompt.md.tmp` via the Write tool, then atomically rename: `mv <task-root>/enriched-prompt.md.tmp <task-root>/enriched-prompt.md`. No validator schema exists for this filename (confirmed inert on `detect_type()` — falls through to `default`); this is a Class A always-English doc, not a Class B validated artifact.

Sections, in this order:
- `## Enriched prompt` — the sharpened task description, ready to feed into `/specify` or `/architect`.
- `## Assumptions` — every assumption made to fill a gap (non-interactive path), or "none" (interactive path / already-clear path).
- `## Open questions` — the "questions I would have asked" list (non-interactive path), or any genuinely unresolved ambiguity the user chose to defer, or "none".
- `## Grounding sources` — which discovery/memory files or prior spec.md informed the enrichment, or "none — prompt required no grounding lookup".

After writing, echo the full enriched prompt in chat so the user sees it immediately without needing to open the file.

## Important behaviors

- **Never auto-invoke downstream phases.** This skill writes `enriched-prompt.md` and stops. It does NOT invoke `/specify`, `/architect`, `/thorough_plan`, `/plan`, `/implement`, or any other skill on the user's behalf.
- **Never write a spec, architecture, or plan.** Those are `/specify`'s and `/architect`'s outputs; this skill's only artifact is `enriched-prompt.md`.
- **Ask only for genuine gaps.** Ground every question in real context (discovery output, prior spec, dependency map) — never ask a question the raw prompt already answers or that isn't backed by something concrete.
- **Degrade gracefully when non-interactive.** Never block on missing interactivity — produce the best-effort rewrite, flag assumptions, and list deferred questions instead.
- **Tolerate missing inputs.** No discovery output, no prior spec, no task folder yet — all fine starting conditions.

STOP after writing and echoing `enriched-prompt.md` — never invokes a downstream phase.

## Save session state

Before finishing, write or update `.workflow_artifacts/memory/sessions/<date>-<task-name>.md` with:
- **Status:** `completed` (enrichment is a single-pass skill; there is no partial state to resume)
- **Current stage:** `enrich`
- **Completed in this session:** whether material enrichment was needed, and a one-line summary of what changed
- **Unfinished work:** any open questions the user deferred
- **Cost:** YAML block with Session UUID, Phase (`enrich`), Recorded in cost ledger

This is what `/end_of_day` reads to consolidate the day's work. Without it, this session is invisible to the daily rollup.
