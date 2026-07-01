# next_steps

Runtime-neutral intent for the next_steps skill. Any runtime adapter (Claude,
Codex, …) that implements this skill should match the contract described here.

## Purpose

Maintain an append-only queue of future work items so the team can capture ideas
and TODOs without immediately executing them. Items survive across sessions because
the queue lives in a file at the project root.

## When to use

- User says "/next-steps", "/next-steps add <text>", "add this to next steps",
  "/next-steps list", "/next-steps done N".
- When a task spawns follow-on work that can't be addressed immediately.

## Inputs

- `next-steps.md` at the project root (created on first add if absent).

## Subcommands

- (no args) — alias for `list`
- `add <text>` — append a new item to the queue
- `list` — show active (non-done) items
- `list --all` — show all items including done
- `done N` — mark item N as done

## Output

- Updated `next-steps.md` (on `add` and `done`).
- Rendered queue list presented to the user (on `list`).

## Behavior contract

- Append-only: items are never deleted, only marked done.
- Idempotent listing: `list` MUST NOT modify `next-steps.md`.
- File format: a `## Queue` section with numbered list items; done items prefixed `~~`.
- Never commit, never modify source files beyond `next-steps.md`.

## Out of scope

- Priority ordering, due dates, or labels — out of scope for v1.
- Model tier and §0 dispatch grammar — runtime adapter concerns.
