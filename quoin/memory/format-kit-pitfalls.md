# Format-Kit Pitfalls — Pre-Write Reminders

Read FIRST at Step 1 body generation. Do NOT pass to Step 2 Haiku prompt.

## V-04

Checks `<word>` / `</word>` balance. Backtick spans and fenced blocks stripped before scan; HTML-void and `<tag/>` forms exempt.

- GOOD: `UUID_PLACEHOLDER` or `` `<uuid>` `` or `<uuid>...</uuid>`
- BAD: `<uuid>` bare on a line (unmatched open tag)

Before composing this artifact's body: wrap bare `<word>` tokens in backticks.

## V-05

`[DTRFQS]-NN` tokens are file-local; must resolve to a definition here. Use plain English for cross-file refs.

- GOOD: "the parent plan's task four"
- BAD: a bare T-NN token when that ID is defined in another file

Before composing this artifact's body: confirm every T-NN/D-NN/R-NN/Q-NN/S-NN/F-NN is defined here.

## V-06

Class B artifacts must start (after frontmatter) with `## For human` as first H2; 1–12 non-blank lines. Class A artifacts (critic-response, gate, insights) skip this check.

- GOOD: `## For human` first H2, ≤12 non-blank lines
- BAD: heading absent or >12 non-blank lines

Before composing this artifact's body, IF this artifact is Class B: verify `## For human` is first H2, ≤12 non-blank lines.
