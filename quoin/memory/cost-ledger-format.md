# Cost ledger format — full reference

## Row format

**Ledger path:** `.workflow_artifacts/<task-name>/cost-ledger.md`. Create with header `# Cost Ledger — <task-name>` if new.

**Row format — executable one-liner (7-column form):**

```bash
uuid=$(python3 __QUOIN_HOME__/scripts/get_session_uuid.py --project-path "$(pwd)" --phase "PHASE" 2>/dev/null || echo "unknown-PHASE-$(date -u +%Y%m%dT%H%M%SZ)") && printf '%s | %s | %s | %s | task | %s | %s\n' \
  "$uuid" "$(date -u +%Y-%m-%d)" "PHASE" "MODEL" "NOTE" "FALLBACK_FIRES" \
  >> "$LEDGER"
```

Substitute the bareword placeholders `PHASE`, `MODEL`, `NOTE`, `FALLBACK_FIRES` with session-specific values before running. `LEDGER` must be set to the ledger path (e.g., `.workflow_artifacts/<task-name>/cost-ledger.md`) before invocation. `NOTE` MUST be quoted — unquoted values containing spaces or pipes will produce malformed rows. Columns: `UUID | DATE | PHASE | MODEL | task | NOTE | FALLBACK_FIRES`.

**6-column form** (for Conditional skills `/discover`, `/triage` that omit `fallback_fires`):

```bash
uuid=$(python3 __QUOIN_HOME__/scripts/get_session_uuid.py --project-path "$(pwd)" --phase "PHASE" 2>/dev/null || echo "unknown-PHASE-$(date -u +%Y%m%dT%H%M%SZ)") && printf '%s | %s | %s | %s | task | %s\n' \
  "$uuid" "$(date -u +%Y-%m-%d)" "PHASE" "MODEL" "NOTE" \
  >> "$LEDGER"
```

The 7th column (`fallback_fires`) is OPTIONAL. Existing 6-column rows are valid forever; readers MUST tolerate both shapes. When present, the value is a non-negative integer (`0` if no fires occurred during the session). When absent, parsers treat it as `0`. Writers SHOULD emit the 7th column on new rows; readers MUST NOT fail on a missing 7th column. Append-only ledger semantics are unchanged.

**Writer guidance:** Skills emitting a new ledger row SHOULD include the 7th column when they have a session-state `fallback_fires` value available (typically at session-end emits, not session-open). Skills MAY emit a 6-column row when no session-state exists (e.g., `/discover`, `/triage`) or when `fallback_fires` is 0; readers tolerate both shapes per the row-format spec.

**UUID acquisition:** Use `python3 __QUOIN_HOME__/scripts/get_session_uuid.py --project-path "$(pwd)" --phase "PHASE"` to obtain the session UUID. The script finds the most-recently-modified `<uuid>.jsonl` under `~/.claude/projects/<project-hash>/` (project-hash = project path with non-alphanumeric chars replaced by `-`) and returns its stem. Falls back to `unknown-<phase_slug>-<YYYYMMDD>T<HHMMSS>Z` if no JSONL is found or on any error (fail-open). The `unknown-*` prefix is recognized by the cost_snapshot skip filter — synthetic UUIDs are excluded from cost totals. Phase dashes are slugified to underscores in the fallback (e.g., `end-of-task` → `end_of_task`). The outer shell fallback in the one-liner (`|| echo "unknown-PHASE-$(date -u ...)"`) ensures a UUID is always set even if Python is unavailable. The script exits 0 always (fail-open design).

## Phase values

`discover`, `architect`, `plan`, `critic`, `revise`, `implement`, `review`, `gate`, `end-of-task`, `run-orchestrator`, `thorough-plan`, `rollback`, `init-workflow`, `start-of-day`, `end-of-day`, `weekly-review`, `capture-insight`, `triage`, `expand`, `checkpoint`, `sleep`, `session-close-hook`, `next-steps`, `ad-hoc`

## Category

Always write `task`. The ledger is append-only — never delete or rewrite rows.

## Portable shape

See also `quoin/core/workflow/cost-ledger.md` for the runtime-neutral specification.
