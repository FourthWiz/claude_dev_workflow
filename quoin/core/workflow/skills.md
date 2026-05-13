# Skill Metadata

`skills.json` is the runtime-neutral skill catalog for Quoin.

It does not drive runtime behavior yet. Existing Claude skill frontmatter remains the active runtime source until a generator or adapter loader is introduced.

## Ownership

The portable core owns these fields:

- `schema_version` — version of the manifest shape.
- `skills` — list of skill metadata entries.
- `name` — stable skill identifier, matching the directory under `quoin/skills/`.
- `phase` — runtime-neutral workflow phase or responsibility.
- `effort` — runtime-neutral effort level from `quoin/docs/effort-levels.md`.
- `user_facing` — whether users should invoke or route to the skill directly.
- `claude_model` — compatibility metadata copied from current Claude `model:` frontmatter.

`effort` is the portable field. Runtime adapters should map effort to their own model or reasoning controls.

`claude_model` exists to keep the manifest auditable against current Claude behavior. It should not be used by non-Claude adapters.

## Current Constraints

- Every `quoin/skills/*/SKILL.md` file must have exactly one manifest entry.
- `claude_model` must match current skill frontmatter.
- `effort` must be one of `low`, `medium`, `high`, or `max`.
- `revise-fast` remains internal with `user_facing: false`.
- No Codex model names belong in this manifest.

## Future Use

Future adapter work may use this manifest to generate runtime-specific command tables, install manifests, or adapter overlays. Do not generate active Claude files from it until compatibility tests cover the generated output.
