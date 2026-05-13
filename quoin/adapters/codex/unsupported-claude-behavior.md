# Unsupported Claude-Only Translations

Codex adapter files document Quoin's portable workflow behavior for Codex. They
do not translate Claude runtime mechanics into Codex behavior.

Unsupported translations:

- Claude slash-command invocation is not a Codex command system.
- Claude skill frontmatter and model tier names are not Codex packaging or model
  selection rules.
- Claude subagent dispatch prompts are not Codex adapter requirements.
- Claude prompt-cache preambles are not generated for Codex.
- Claude session-log, usage, and cost-capture plumbing are not implemented as
  Codex behavior.
- Claude installer routing is not reused for Codex.

Codex should use native planning, progress tracking, approvals, sandboxing,
repo-scoped instructions, and model or reasoning controls. If a Codex runtime
extension point is later verified, it should be added as a new adapter contract
instead of inferred from Claude behavior.
