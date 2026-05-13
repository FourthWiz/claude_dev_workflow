# Cost Ledger

Quoin keeps an append-only cost ledger per task. The ledger shape is portable, but runtime-specific cost capture is adapter-owned.

## Location

The task ledger lives at:

```text
.workflow_artifacts/<task-name>/cost-ledger.md
```

For multi-stage tasks, the ledger remains at the task root and spans all stages.

## Row Shape

Each row in the ledger has the following columns, delimited by the bare pipe character `|`. Fields are stripped (leading and trailing whitespace removed) after splitting.

| Column | Field name       | Type   | Description |
|--------|-----------------|--------|-------------|
| 1      | uuid            | str    | Session identifier; runtime-agnostic (not specific to any runtime's session format) |
| 2      | date            | str    | ISO date: YYYY-MM-DD |
| 3      | phase           | str    | Workflow phase (e.g. `plan`, `implement`, `review`, `gate`) |
| 4      | model_or_effort | str    | Claude model tier (`opus`, `sonnet`, `haiku`) or a runtime-neutral effort level (`high`, `medium`, `low`). Field name is neutral to support both. |
| 5      | category        | str    | Always `task` in current practice. Rows with any other value are skipped by readers. |
| 6      | note            | str    | Free-form note; double-quotes are preserved verbatim (reader does NOT strip surrounding quotes). |
| 7      | fallback_fires  | int    | Optional. Non-negative integer. Defaults to 0 when the column is absent (six-column rows). |

Delimiter discipline: split on bare `|` (not on the three-character sequence ` | `), then strip each resulting field. This is required for parity with existing reader implementations.

## Append-Only Invariant

Rows are append-only. Writers add new rows; they never delete or rewrite existing rows. Readers must not fail on older rows. Finalized-task ledgers are immutable (no new rows after the task is archived to `.workflow_artifacts/finalized/`). See `test_ledger_no_placeholder.py:_is_finalized` for the programmatic finalization check.

## Schema Mapping

The canonical typed representation of a ledger row is `CostEvent` in `quoin/core/scripts/cost_event.py`. The mapping from column position to field name is:

| Column | Ledger column name | `CostEvent` field  |
|--------|-------------------|--------------------|
| 1      | UUID              | `uuid`             |
| 2      | DATE              | `date`             |
| 3      | PHASE             | `phase`            |
| 4      | MODEL_OR_EFFORT   | `model_or_effort`  |
| 5      | category          | `category`         |
| 6      | NOTE              | `note`             |
| 7      | FALLBACK_FIRES    | `fallback_fires`   |

`quoin/core/scripts/cost_event.py` is the canonical typed shape. This table is kept content-aligned with that module's `CostEvent` dataclass.

## Tolerated Variations

Readers must handle the following without error:

- **Six-column rows** — the `fallback_fires` column is absent; parser yields `fallback_fires=0`.
- **Whitespace around pipes** — extra spaces before or after `|` separators are stripped; the resulting field values are identical to a tightly-formatted row.
- **Empty note field** — the note field may be an empty string after stripping; this is valid.
- **Comment lines** — lines starting with `#` (after stripping) are skipped; reader yields nothing for them.
- **Blank lines** — empty lines (after stripping) are skipped; reader yields nothing for them.
- **Non-task category** — rows whose `category` field is not exactly `task` are skipped; reader yields nothing for them (defensive guard).

## Malformed Inputs

The reader handles malformed inputs gracefully rather than raising exceptions:

- **Non-integer seventh column** — parser uses `fallback_fires=0` and emits a stderr warning prefixed `cost_snapshot.WARN: malformed fallback_fires column at <source>:<lineno>`.
- **More than seven columns** — parser takes the seventh column as `fallback_fires`, ignores subsequent columns, and emits a stderr warning prefixed `cost_snapshot.WARN: extra columns at <source>:<lineno>`.
- **Fewer than six columns** — parser returns `None` (skip-line semantics); no warning emitted.
- **Non-task category** — parser returns `None` (skip-line semantics); no warning emitted.

## Out Of Scope

The portable ledger contract does NOT cover:

- **Cost-resolution mechanism** — how to compute dollar amounts from ledger rows (CLI, API, library) is runtime-specific.
- **Model pricing tables** — per-model input/output/cache rates are adapter-owned.
- **Session-UUID acquisition strategy** — how to obtain the session identifier at write time is adapter-specific.
- **Per-runtime fallback chains** — the sequence of cost-lookup attempts (e.g., primary CLI → local fallback) is adapter behavior, not portable behavior.
- **On-disk row format changes** — this document does not authorize new columns. Any new column requires a separate decision and backward-compatibility analysis.

See also: `quoin/core/skills/cost_snapshot.md` § Out of scope for the consumer-side analogue.

## Codex-Specific Capture

Codex currently records repo-local cost events through
`quoin/adapters/codex/cost_event.py`. The writer uses the portable `CostEvent`
schema and appends the existing seven-column ledger row.

Because this repository has no verified Codex local telemetry interface, Codex
rows record available local values in the note field and mark unavailable
telemetry explicitly:

- `runtime=codex`
- `task=<task-name>`
- `timestamp=<ISO timestamp>`
- `session_id=<provided value or unknown>`
- `effort=<low|medium|high|max|unknown>`
- `input_tokens=not_available`
- `output_tokens=not_available`
- `cache_creation_input_tokens=not_available`
- `cache_read_input_tokens=not_available`
- `total_tokens=not_available`
- `cost_usd=not_available`
- `telemetry_source=not_available`

Codex writers must not infer token counts, dollar cost, or telemetry source
from unrelated local signals.

## Claude-Specific Capture

Claude currently records Claude session UUIDs and uses `ccusage` plus a JSONL fallback. That behavior belongs to the Claude adapter, not the portable core. Claude's collection details (ccusage CLI, JSONL parsing, model-tier prices) are documented in `quoin/adapters/claude/README.md` and implemented in `quoin/scripts/cost_from_jsonl.py`.
