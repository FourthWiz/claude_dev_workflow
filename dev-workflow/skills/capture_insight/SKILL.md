---
name: capture_insight
description: "Captures a quick insight, pattern, or discovery to the daily insights scratchpad without interrupting the current task. Use for: /capture_insight, 'note this', 'remember this pattern', 'log this decision', 'save this as a lesson', 'note that', 'remember that'. Appends a structured entry to .workflow_artifacts/memory/daily/insights-<date>.md."
model: haiku
---

# Capture Insight

You log a single insight to the daily scratchpad immediately and return control to the user.

## Session bootstrap

Cost tracking note: `/capture_insight` is a lightweight note-taking skill. Append to the cost ledger only if a task context is clearly active. If in doubt, skip cost recording.

If a task context is active: append your session to `.workflow_artifacts/<task-name>/cost-ledger.md` (see cost tracking rules in CLAUDE.md) — phase: `capture-insight`.

## Process

### Step 1: Determine the insight

The insight is whatever the user just described, or what you just noticed during task work. If the user invoked this explicitly (e.g., `/capture_insight "this API returns 200 on auth failure"`), use that. If invoked from context (e.g., the user said "note that"), extract the key point.

### Step 2: Classify it

Choose the most fitting type:
- **pattern** — a recurring structure in this codebase worth remembering
- **gotcha** — something that caused confusion or wasted time; a trap to avoid
- **decision-rationale** — a choice made whose "why" will be forgotten by tomorrow
- **surprise** — something that behaved unexpectedly
- **workflow-friction** — something about the workflow process itself that felt wrong or slow (Tier 3 candidate)

And set `Promote?`:
- `yes` — clearly reusable across future sessions or tasks
- `maybe` — worth reviewing at end of day
- `no` — local/ephemeral, not worth carrying forward

For **workflow-friction** type, always set `Promote?: yes` — these are surfaced as Tier 3 suggestions at `/end_of_day`.

### Step 3: Write to scratchpad

Write `daily/insights-{date}.md` appends in v3 format per the §5.4 Class A writer mechanism. Reference files (apply HERE at the body-generation write-site, per format-kit.md §1 / lesson 2026-04-23): `~/.claude/memory/format-kit.md` (primitives + section set), `~/.claude/memory/glossary.md` (status glyphs + abbreviation whitelist), `~/.claude/memory/terse-rubric.md` (prose discipline inside the Insight body). Entry structure: each insight is a `## {HH:MM} — {task-context or "ad-hoc"}` heading followed by a YAML-style key/value block (Type / Insight / Applies to / Promote?) per the template below. The terse-rubric applies inside the multi-sentence Insight value only (caveman prose for "why" content). After appending, run `python3 ~/.claude/scripts/validate_artifact.py {insights-path}` (auto-detection — file does not match a named-type prefix, falls through to `default`). On V-failure (rare for append-only structured entries): log a `format-kit-skipped` warning and continue (capture_insight is Haiku, must not block). No retry — append-only file already has the new entry.

Append to `.workflow_artifacts/memory/daily/insights-<YYYY-MM-DD>.md` (today's date). Create the file with a header if it doesn't exist yet:

```markdown
# Daily Insights — <YYYY-MM-DD>

Scratchpad for patterns, gotchas, and decisions captured during task work.
Reviewed and promoted by /end_of_day.

---
```

Then append the entry:

```markdown
## <HH:MM> — <task-context or "ad-hoc">
**Type:** <pattern | gotcha | decision-rationale | surprise | workflow-friction>
**Insight:** <the observation, 1-3 sentences>
**Applies to:** <skill names, technology, or "general" — or "workflow" for Tier 3>
**Promote?:** <yes | maybe | no>
```

### Step 4: Confirm

Reply with one short sentence confirming what was captured. Then stop — don't elaborate.

Example: "Noted: API silently returns 200 on auth failure (gotcha, promote: yes)."

## Important behaviors

- **Fast.** This skill should complete in seconds. No analysis, no follow-up questions.
- **Don't ask for clarification.** Make a reasonable judgment about type and Promote? and proceed. The user can always delete or edit the entry.
- **Don't break the user's flow.** One-line confirmation only.
