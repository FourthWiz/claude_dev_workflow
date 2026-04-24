# Manual Summarize POC — Stage 1 implement record

**Date:** 2026-04-24
**Script:** `dev-workflow/scripts/summarize_for_human.py`
**Model pin:** `claude-haiku-4-5-20251001`

## Attempted run

```
python3 dev-workflow/scripts/summarize_for_human.py /tmp/poc-body.md
```

**Result:** `ANTHROPIC_API_KEY missing` — exit 1 (expected code path per T-07 test).

ANTHROPIC_API_KEY was not available in the bash subprocess context at `/implement` time
(Claude Code VSCode extension does not expose the session key to shell commands).

## What was verified

- `--help` exits 0 with usage line ✓
- Missing-API-key path: exits 1 with correct stderr `ANTHROPIC_API_KEY missing — set it in your shell...` ✓
- No module-scope `import anthropic` (grep confirmed) ✓
- `MODEL = "claude-haiku-4-5-20251001"` constant present ✓
- Prompt template anchor `do NOT invent facts not present in the body` present ✓

## To run the live integration test

```bash
export ANTHROPIC_API_KEY=<your-key>
python3 dev-workflow/scripts/summarize_for_human.py /tmp/poc-body.md
# Expected: 5-8 lines of plain English output, exit 0, < 30s wall time
```

The `test_integration_haiku_call` test in `test_summarize_for_human.py` exercises this
path when `ANTHROPIC_API_KEY` is set. Run with:
```bash
pytest dev-workflow/scripts/tests/test_summarize_for_human.py -v
```
(Integration test auto-skips when key is absent; no FAIL when running in CI without creds.)

## POC status

Smoke-test-only at implement time per architecture §5.3.1 — live API confirmation
deferred to Stage 2 wire-in when `ANTHROPIC_API_KEY` is available in test context.
The `test_integration_haiku_call` integration test provides the live verification path.
