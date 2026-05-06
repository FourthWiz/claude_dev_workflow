# Canonical format reference: forgotten/<date>.md entry block

Each entry in a `forgotten/<date>.md` file uses this block format:

```
> Source: /abs/path/to/source-file.md:10..25
> Forgotten: 2026-03-15T10:00:00Z
> Score: forget=4, promote=1

<original entry text verbatim>

---
```

## Field specifications

- `> Source:` — absolute path to the original source file, colon-separated from the line range.
  Line range format: `<start_line>..<end_line>` (1-based, inclusive).
  This is the restore anchor for `/sleep --restore`.

- `> Forgotten:` — ISO 8601 timestamp (UTC) of when the entry was soft-forgotten.

- `> Score:` — the forget and promote scores at the time of soft-forgetting, for audit purposes.

- `<original entry text verbatim>` — the full text of the entry, exactly as it appeared in the source file.
  Includes the `### Insight N:` heading line if the entry was heading-based.

- `---` — block separator. Each forgotten entry ends with a `---` line followed by a blank line.

## Example (heading-based entry)

```
> Source: /Users/you/project/.workflow_artifacts/memory/daily/insights-2026-03-15.md:1..7
> Forgotten: 2026-03-15T10:00:00Z
> Score: forget=4, promote=1

### Insight 1: hook timeout calibration

The 5-second timeout for userpromptsubmit.sh is sufficient for jq parsing but tight for slow filesystems.

**Promote?:** maybe
**Applies to:** /implement

---
```

## Restore behavior

`/sleep --restore <pattern>` searches all `forgotten/<date>.md` files for entries whose text contains
`<pattern>` (substring match, case-insensitive). For each match, the `> Source:` anchor determines
the restore target (original file if it exists, else today's insights file).
