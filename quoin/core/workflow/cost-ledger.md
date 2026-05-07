# Cost Ledger

Quoin keeps an append-only cost ledger per task. The ledger shape is portable, but runtime-specific cost capture is adapter-owned.

## Location

The task ledger lives at:

```text
.workflow_artifacts/<task-name>/cost-ledger.md
```

For multi-stage tasks, the ledger remains at the task root and spans all stages.

## Row Shape

Writers should emit rows shaped like:

```text
UUID | DATE | PHASE | MODEL_OR_EFFORT | task | NOTE | FALLBACK_FIRES
```

The `FALLBACK_FIRES` column is optional for backward compatibility. Readers must tolerate both six-column and seven-column rows.

## Portable Semantics

- The ledger is append-only.
- Readers must not fail on older six-column rows.
- `PHASE` identifies the workflow phase.
- `MODEL_OR_EFFORT` may be runtime-specific today; runtime-portable adapters should prefer effort/capability vocabulary where possible.
- Runtime adapters own how they discover session IDs and calculate actual cost.

## Claude-Specific Capture

Claude currently records Claude session UUIDs and uses `ccusage` plus a JSONL fallback. That behavior belongs to the Claude adapter, not the portable core.
