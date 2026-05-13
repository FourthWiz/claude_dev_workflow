# Codex Cost Events

Codex cost handling is repo-local and ledger-based. The adapter writes portable
`CostEvent` rows to the task ledger using
`quoin/core/scripts/cost_event.py`; it does not inspect runtime-global state or
claim a live telemetry API.

## Known Locally

A Codex workflow session can record these values when the event is written:

- runtime: `codex`
- task name and task ledger path
- phase
- portable effort level: `low`, `medium`, `high`, `max`, or `unknown`
- timestamp
- session id when the caller provides one, otherwise `unknown`
- fallback fires, normally `0`

## Not Available

This repository has no verified Codex interface for token or dollar telemetry.
The Codex writer therefore records the following fields explicitly as
`not_available` in the ledger note:

- `input_tokens`
- `output_tokens`
- `cache_creation_input_tokens`
- `cache_read_input_tokens`
- `total_tokens`
- `cost_usd`
- `telemetry_source`

Do not infer token counts from chat length, transcript size, model name, elapsed
time, or file changes. If Codex later exposes a stable local telemetry contract,
add that as a new adapter behavior and keep the existing `not_available` rows
valid forever.

## Ledger Row

The writer appends the existing seven-column portable ledger row:

```text
<uuid> | <date> | <phase> | <effort> | task | <note> | <fallback_fires>
```

For Codex, the `uuid` column starts with `unknown-codex-` so existing cost
summary readers treat the row as an unresolved cost source instead of trying to
resolve it through another runtime. The original Codex session id, when known,
is recorded in the note as `session_id=<value>`.

The note is a semicolon-delimited key-value list, for example:

```text
runtime=codex; task=my-task; timestamp=2026-05-13T12:34:56Z; session_id=unknown; effort=high; input_tokens=not_available; output_tokens=not_available; cache_creation_input_tokens=not_available; cache_read_input_tokens=not_available; total_tokens=not_available; cost_usd=not_available; telemetry_source=not_available
```

## Usage

Append a row for a task:

```text
python3 quoin/adapters/codex/cost_event.py write --project-root . --task <task-name> --phase <phase> --effort <low|medium|high|max|unknown>
```

Validate a task ledger:

```text
python3 quoin/adapters/codex/cost_event.py validate --project-root . --task <task-name> --expect-codex
```

Run the bundled self-test:

```text
python3 quoin/adapters/codex/cost_event.py --self-test
```

## Boundaries

- This is not a global Codex install or command file.
- This is not live runtime telemetry collection.
- This does not price Codex usage.
- This does not change Claude cost collection.
- This uses the portable ledger row shape from
  `quoin/core/workflow/cost-ledger.md`.
