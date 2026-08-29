# Agent Handoff Format

Quoin defines one envelope family for inter-agent handoff: a dispatch envelope
(orchestrator to subagent) and a return envelope (subagent to orchestrator),
sharing one version marker and validated by one canonical validator,
`quoin/core/scripts/handoff_validate.py` (portable wrapper at
`quoin/scripts/handoff_validate.py`). This file is the normative reference for
both directions; a reader of this file alone can determine the required and
optional fields, field ordering, delimiters, escaping, byte bounds, and
version-marker rules for either direction.

This is a payload format for the run orchestrator's phase-dispatch and
phase-return path. It is not the Codex session continuation handoff
(`quoin/adapters/codex/handoff.md`), which governs how one Codex session
hands off to its successor session via an artifact under
`.workflow_artifacts/memory/sessions/` — a different artifact from the
dispatch/return envelope this file defines.

## Envelope Placement

A payload carrying an envelope has three parts in order: a sentinel prefix
zone, the envelope, and free-text prose.

The sentinel zone is the maximal leading run of the payload consisting only
of whitespace and whitespace-separated bracket tokens matching `\[[^\]\n]*\]`
(for example `[no-redispatch]`, `[autonomous]`), computed without reference
to the envelope marker. The zone terminates at the first token whose text
begins `[quoin-handoff/` — that token is the open marker and is not part of
the zone — or at the first character that is neither whitespace nor part of
such a token.

The open marker is the first `[quoin-handoff/...]` token in the payload; the
close marker, `[/quoin-handoff]`, is its match. The envelope is everything
strictly between the two markers. Byte bounds on the envelope as a whole are
measured over this marker-to-marker span only, never over the whole payload.

The close marker is recognised only when it occupies an entire line of its
own — immediately preceded by the start of the payload or a newline, and
immediately followed by a newline or the end of the payload. A
close-marker-shaped substring appearing elsewhere on a line (for example
quoted inside a field value) is not a match and does not terminate the
envelope; the matching close marker is the first occurrence satisfying the
own-line condition after the open marker.

Placement is normative, not advisory: the text between the end of the
sentinel zone and the open marker must contain only whitespace (prose before
the envelope is a violation), and the open marker must begin at the start of
a line (a marker sharing a line with sentinel tokens is a violation). Both
conditions must hold.

## Version Marker

The marker is `quoin-handoff/<major>.<minor>`, never a bare major. Three
rules govern version and key tolerance:

- An unrecognised **major** means: ignore the envelope, fall back to
  free-form handling, and stop evaluating the payload as a handoff. This is
  fail-open — a handoff envelope is an optimization, never a correctness
  dependency.
- An unrecognised **minor** within a recognised major means: process the
  envelope normally. Evaluation continues, unlike the unrecognised-major
  case.
- Unknown **keys** within a recognised major and minor must be ignored, never
  rejected. Duplicate keys: the first occurrence wins.

A caller may pass an expected direction as an assertion. Omitted, the
marker's own direction keyword (`dispatch` or `return`) governs. Supplied and
disagreeing with the marker's keyword, that is its own violation — the
assertion never silently overrides the marker.

## Dispatch Envelope

Orchestrator to subagent. Required fields: `skill`, `task`, `task_dir`,
`project_root`, `return`. Optional fields: `profile`, `inputs`, `spec`,
`bundle[N]` (tabular sub-form, see Tabular Sub-form below). `return` states
the expected reply shape for the spawned subagent.

Canonical field order (see Field Ordering below): `skill`, `task`,
`task_dir`, `project_root`, `profile`, `inputs`, `return`, `spec`, `bundle`.
This same list is the dispatch known-key set.

```text
[no-redispatch] [autonomous] [quoin-onbehalf]
[quoin-handoff/1.0 dispatch]
skill: architect
task: agent-handoff-format
task_dir: .workflow_artifacts/agent-handoff-format/
project_root: /abs/path/to/project
profile: Large
inputs: spec.md | enriched-prompt.md | memory/repos-inventory.md
return: envelope
spec: __QUOIN_HOME__/core/workflow/handoff-format.md
[/quoin-handoff]
<task-specific prose, unchanged>
```

## Return Envelope

Subagent to orchestrator. `status` is the discriminating field and takes one
of four values: `COMPLETE`, `PARTIAL`, `NEEDS-DECISION`, `BLOCKED`. Each
status has its own required-field set — see Status Required Fields below.
`PARTIAL` is a `status` value of this same return envelope, not a separate
shape; a consumer distinguishes a partial return from a complete one solely
by reading `status`.

Return known-key set (the union over all four statuses plus the optional
fields) and canonical field order (identical list, in order — see Field
Ordering below): `status`, `artifact`, `verdict`, `summary`, `checkpoint`,
`phase`, `reason`, `remaining`, `resume_hint`, `artifacts`. The known-key set
is per direction, never per status — a `BLOCKED` return's `reason` is a known
key for that reason, not because `BLOCKED` alone declares it.

`NEEDS-DECISION` and `BLOCKED` are reserved for a subagent's own genuine
inability to proceed; a fail-closed hard stop reached by a spawned phase
emits the shipped `gate-result: NEEDS-DECISION` block INSTEAD of any
envelope on that return, never a `NEEDS-DECISION` envelope alongside or in
place of it — the orchestrator recognises only the gate-result token at that
site, so a `NEEDS-DECISION` envelope emitted there would go unrecognised.

Complete:

```text
[quoin-handoff/1.0 return]
status: COMPLETE
artifact: /abs/path/architecture.md
verdict: PASS
summary: <clamped, one line, <=600 B>
[/quoin-handoff]
```

Partial:

```text
[quoin-handoff/1.0 return]
status: PARTIAL
checkpoint: /abs/path/checkpoint-<sid>.md
phase: architect
remaining: <short, one line>
resume_hint: <short, one line>
[/quoin-handoff]
```

Needs-decision:

```text
[quoin-handoff/1.0 return]
status: NEEDS-DECISION
checkpoint: /abs/path/checkpoint-<sid>.md
phase: implement
reason: <short, one line>
resume_hint: <short, one line>
[/quoin-handoff]
```

Blocked:

```text
[quoin-handoff/1.0 return]
status: BLOCKED
phase: review
reason: <short, one line>
resume_hint: <short, one line>
[/quoin-handoff]
```

## Status Required Fields

The complete required- and optional-field matrix for both directions. This
table is the primary reference for what a conforming payload must and may
carry.

| Direction | Status | Required | Optional |
|---|---|---|---|
| dispatch | n/a | `skill`, `task`, `task_dir`, `project_root`, `return` | `profile`, `inputs`, `spec`, `bundle[N]` |
| return | `COMPLETE` | `status`, `artifact`, `verdict`, `summary` | `artifacts[N]` |
| return | `PARTIAL` | `status`, `checkpoint`, `phase`, `remaining`, `resume_hint` | `summary`, `artifacts[N]` |
| return | `NEEDS-DECISION` | `status`, `phase`, `reason`, `resume_hint`, and at least one of `checkpoint` or `artifact` | `summary`, `verdict`, `artifacts[N]` |
| return | `BLOCKED` | `status`, `phase`, `reason`, `resume_hint` | `artifact`, `checkpoint`, `summary`, `verdict`, `artifacts[N]` |

`verdict` is optional on every status that admits it and is checked only
when present — an omitted required field is a required-field violation, not
a verdict violation.

## Status And Verdict Vocabulary

`status` enum, exactly four members: `COMPLETE`, `PARTIAL`, `NEEDS-DECISION`,
`BLOCKED`.

`verdict` vocabulary, verbatim, exactly five members: `PASS`, `REVISE`,
`APPROVED`, `CHANGES_REQUESTED`, `BLOCKED`. These strings are load-bearing —
downstream grep contracts match them verbatim.

## Field Ordering

Field order is one canonical list per direction (given above with each
direction's known-key set), evaluated over recognised keys' first
occurrences only. Unknown keys are ignored for ordering purposes, consistent
with the must-ignore rule above. Duplicate keys are likewise ignored for
ordering beyond their first occurrence. A conforming payload's recognised
fields therefore appear as a subsequence of the canonical list for its
direction — it need not carry every field, but the fields it does carry must
appear in that relative order.

## Tabular Sub-form

A single dispatch or return record is non-uniform, so it stays in the
`key: value` form used everywhere above. Where a payload carries **repeated
rows sharing a field set**, the envelope uses a tabular sub-form instead.

A tabular block opens on a column-0 key line whose key matches
`^[a-z_][a-z0-9_]*\[\d+\]$` (for example `artifacts[3]`) and whose value is a
header naming the block's fields in fixed order, separated by the list
delimiter (see Delimiter And Escape below). The block's rows are the
immediately following consecutive lines; each row must begin with at least
one space — indentation is the discriminator between a row and the next
column-0 key — and carries the same field count as the header, separated by
the same delimiter. The block closes at the first subsequent column-0
`key: value` line, or at the close marker.

```text
artifacts[3]: path | kind | status
  /abs/current-plan.md | plan | COMPLETE
  /abs/review-1.md | review | COMPLETE
  /abs/gate-implement.md | gate | NEEDS-DECISION
```

The bracketed count is normative, not decorative: it is the declared row
count, and it must agree with the number of rows actually present. It is
stripped before the known-key lookup and before the field-ordering lookup, so
`artifacts[3]` and `artifacts[5]` are both the single known key `artifacts`
and occupy one slot in the canonical order; only the declared-count check
itself reads the bracketed integer.

Tabular keys are known keys of their direction, not unknown ones. The return
direction declares the optional `artifacts[N]` block, header
`path | kind | status`. The dispatch direction declares the optional
`bundle[N]` block, header `path | summary`, matching the bundle convention's
own one-member-per-line output.

The list delimiter inside a tabular header or a tabular row is the
structural field separator, not a list-value delimiter — see Delimiter And
Escape below.

## Clamps

Every free-text value, including `summary`, is clamped to 600 bytes. The
whole envelope — measured over the marker-to-marker span defined in Envelope
Placement — is clamped to 1,024 bytes. Both are design bounds on envelope
content; they are not derived from any pre-migration payload size.

## Delimiter And Escape

The field delimiter is `: ` on its first occurrence only, so a value may
itself contain colons. List values use the list delimiter (a pipe surrounded
by single spaces) with a one-way escape (a broken-bar character surrounded
by single spaces) for a literal occurrence of the delimiter inside a value.
Consumers split on the delimiter's first occurrence, never on every
occurrence.

Not every known key is scalar. Dispatch `inputs` is the only list-valued key
in either direction today; its declared delimiter is the list delimiter
above, and that delimiter is never escape-checked inside `inputs`. Every
other known key in both directions is scalar. A tabular header line (for
example `artifacts[3]: path | kind | status`) is a third case — a field-name
header, neither a scalar value nor a list value — and is exempted the same
way a tabular row is: the list delimiter inside a tabular header or row is
the structural field separator, out of scope for escape checking.

Escape conformance is otherwise checked: an unescaped occurrence of the list
delimiter inside a value whose key is not list-valued and which is neither a
tabular header nor a tabular row is a conformance violation, as is a value
carrying a literal occurrence of the escape sequence itself (the escape is
one-way, so that sequence can never legitimately appear in source text).

Values are control-character-free; control characters are stripped. Every
free-text value is checked against the sentinel-token probe reused from the
bundle convention — a value must not itself contain a sentinel-style bracket
token. The envelope's own markers count as sentinel-style tokens for this
probe: a value quoting either the version-marker prefix (`[quoin-handoff/`)
or the close marker (`[/quoin-handoff]`) is rejected the same way any other
sentinel token is — a marker literal may never appear inside a value. All of
this — the list delimiter, the one-way escape, the
split-on-first-delimiter consumer rule, control-character stripping, and the
sentinel-token probe — is reused by reference from
`quoin/scripts/context_bundle.py` rather than reinvented; only that script's
own byte clamp is not reused (see Clamps above for the values used here).

## Checkable Rules

Every checkable rule has a named ID, `H-01` through `H-21`, and a fixed
severity. `FATAL` rules reject a payload (exit 1); `ADVISORY` rules warn on a
conforming-but-suboptimal payload (exit 0); `RECOMMENDED` rules describe a
consumer-side obligation that no payload can violate, so they carry no
validator function and no test.

| Rule | Severity | Description |
|---|---|---|
| H-01 | FATAL | Marker well-formedness: an open marker matching the version-marker shape, with a matching close marker. A payload with no open marker at all is `FAIL H-01` (fail-closed) — this is the one case where "no marker" is itself the violation, rather than falling back per the unrecognised-major rule. |
| H-02 | ADVISORY | Unrecognised major version. Warns and stops further envelope evaluation for this payload (fail-open). |
| H-03 | ADVISORY | Unrecognised minor version within a recognised major. Warns; evaluation continues. |
| H-04 | FATAL | Direction keyword: the marker's trailing word must be `dispatch` or `return`. |
| H-05 | FATAL | Required-field presence, evaluated per (direction, status) against the Status Required Fields table above. |
| H-06 | FATAL | `status` enum membership: the value must be one of the four members in Status And Verdict Vocabulary. |
| H-07 | FATAL | `verdict` vocabulary membership, checked only when `verdict` is present. |
| H-08 | FATAL | Per-value byte bound: no free-text value exceeds the clamp in Clamps above. |
| H-09 | FATAL | Envelope byte bound: the marker-to-marker span does not exceed the clamp in Clamps above. |
| H-10 | FATAL | Control characters: no value contains a control character. |
| H-11 | FATAL | Sentinel token inside a field value. |
| H-12 | ADVISORY | Duplicate key: warns; the first occurrence wins per Version Marker above. |
| H-13 | FATAL | Envelope placement relative to the sentinel zone, per Envelope Placement above. |
| H-14 | ADVISORY | Unknown key: warns; the key is ignored per Version Marker above. |
| H-15 | FATAL | Tabular per-row arity: a row's field count must match its block's header field count. |
| H-16 | FATAL | Field ordering, per Field Ordering above. |
| H-17 | ADVISORY | Escape conformance, per Delimiter And Escape above. |
| H-18 | FATAL | An explicit direction assertion that disagrees with the marker's own direction keyword. |
| H-19 | FATAL | Tabular declared-count agreement: a block's bracketed count must agree with its actual row count, distinct from H-15's per-row arity. |
| H-20 | FATAL | Envelope line shape: every line strictly between the two markers is a column-0 `key: value` line, an indented row of a currently open tabular block, or the close marker itself; blank lines are rejected. |
| H-21 | RECOMMENDED | Consumers should split each envelope line on the delimiter's first occurrence when parsing. Not checkable by any payload; no validator function, no fixture. |

## Rule Interaction Cascade

Some rules remove the domain of other rules when they fire — a validator
must know which rules to skip, or a payload constructed to isolate one
violation will spuriously trip others. Five rule-firings are gating: an open
marker missing entirely (`H-01`, no marker at all); an open marker with no
matching close (`H-01`, unmatched); an unrecognised major version (`H-02`);
an invalid direction keyword (`H-04`); an invalid `status` value (`H-06`).
Every other rule is non-gating — its firing changes no other rule's domain.

A rule is skipped exactly when an input its predicate reads is undefined.
The three such inputs are the envelope span (both markers located), the
version (readable from a well-formed open marker), and the direction-keyed
key table (known-key set, canonical order, and per-status required sets —
all three looked up by direction keyword).

| Rule | No open marker | No close marker | Unknown major | Bad direction | Bad status |
|---|---|---|---|---|---|
| H-01 marker shape | FIRES | FIRES | runs, passes | runs, passes | runs, passes |
| H-02 unknown major | skip (no version) | runs | FIRES, stops | runs | runs |
| H-03 unknown minor | skip (no version) | runs | skip (stopped) | runs | runs |
| H-04 direction keyword | skip (no marker) | runs | skip (stopped) | FIRES | runs |
| H-05 required fields | skip (no span) | skip (no span) | skip (stopped) | skip (no key table) | degrades to direction-level set; per-status branch skipped |
| H-06 status enum | skip (no span) | skip (no span) | skip (stopped) | skip (no key table) | FIRES |
| H-07 verdict verbatim | skip (no span) | skip (no span) | skip (stopped) | skip (no key table) | runs (present-only) |
| H-08 value byte bound | skip (no span) | skip (no span) | skip (stopped) | runs | runs |
| H-09 envelope byte bound | skip (no span) | skip (no span) | skip (stopped) | runs | runs |
| H-10 control characters | skip (no span) | skip (no span) | skip (stopped) | runs | runs |
| H-11 sentinel in value | skip (no span) | skip (no span) | skip (stopped) | runs | runs |
| H-12 duplicate key | skip (no span) | skip (no span) | skip (stopped) | runs (lexical) | runs |
| H-13 envelope placement | skip (no marker) | runs (open-marker-only) | skip (stopped) | runs | runs |
| H-14 unknown key | skip (no span) | skip (no span) | skip (stopped) | skip (no key table) | runs |
| H-15 tabular row arity | skip (no span) | skip (no span) | skip (stopped) | runs (header-relative) | runs |
| H-16 field ordering | skip (no span) | skip (no span) | skip (stopped) | skip (no key table) | runs |
| H-17 escape conformance | skip (no span) | skip (no span) | skip (stopped) | runs (lexical) | runs |
| H-18 direction disagreement | skip (no marker) | runs | skip (stopped) | skip (no marker direction) | runs |
| H-19 tabular declared count | skip (no span) | skip (no span) | skip (stopped) | runs (lexical) | runs |
| H-20 envelope line shape | skip (no span) | skip (no span) | skip (stopped) | runs (lexical) | runs |
| H-21 consumer split rule | n/a — RECOMMENDED, no validator function, never runs | n/a | n/a | n/a | n/a |

A rule that fires still runs to completion; skipping is never partial. The
one exception is `H-05` under an invalid `status`, which degrades to the
direction-level required set rather than either firing or running its full
per-status branch — every other cell in this table is either a plain skip or
a plain run.
