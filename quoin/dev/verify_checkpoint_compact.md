# Spike: Compact-then-checkpoint mechanics

**Date:** 2026-05-15
**Task:** T-02 (checkpoint-non-blocking-flow)
**Time-box:** 20 min
**Status:** INFORMATIONAL ONLY — plan commits to user-mediated path regardless of outcome (per D-01)

## Verification method

Analyzed the Claude Code harness model and skill invocation mechanisms. Three approaches tested conceptually:

## Tested approaches

### (a) Skill prints `/compact` literally to stdout

**Outcome: DOES NOT WORK.**
Claude Code skills communicate via tool calls (Read, Bash, Edit, etc.) and by returning text. A skill returning the text `/compact` does not cause the harness to execute the `/compact` command. The harness only interprets tool call structures, not text patterns in the skill's output.

### (b) Skill uses the Skill tool with name `compact`

**Outcome: DOES NOT WORK — `/compact` is not an invocable skill.**
The `/compact` command is a built-in harness command, not a skill. Skills are defined in `~/.claude/skills/*/SKILL.md`. There is no `~/.claude/skills/compact/SKILL.md`. The Skill tool only dispatches to named skills in the skills directory; it cannot invoke harness built-ins.

### (c) Skill spawns an Agent subagent with prompt `/compact`

**Outcome: UNCERTAIN but likely DOES NOT WORK for the autonomous path.**
An Agent subagent runs a fresh Claude instance with its own session context. Even if the subagent emits `/compact` in its response, the subagent's harness context is separate from the parent session. The `/compact` command would apply to the SUBAGENT's context (if it even works), not the parent session where compaction is needed.

Additionally, the subagent is a separate process context; it cannot trigger compaction of the parent session.

## Conclusion

**No autonomous compact-from-skill path exists** within the current Claude Code harness model.

The plan's commitment to the USER-MEDIATED PATH (D-01) is correct:
- `/checkpoint` detects high utilization via `COMPACT_FIRST_BPS` threshold
- Writes a `checkpoint-pending-compact-${session_id}.txt` marker
- Surfaces an instruction to the user: "Context is at PCT%. Please run `/compact`, then `/checkpoint --after-compact`."
- User types ONE command (`/compact`) manually
- On next invocation with `--after-compact`, the marker is consumed and save proceeds normally

**If a future harness version exposes a programmatic compact API**, the T-06 `COMPACT_FIRST_BPS` tunable and `checkpoint-pending-compact-*.txt` marker design remain valid entry points for automation. No architectural changes required — just wire up the API call in Step 1.5.
