#!/usr/bin/env python3
"""
Quoin Stage 1 T-00 / T-09 Phase A — verify_subagent_dispatch.

Pure-stdlib documentation generator. Emits a markdown template at
`quoin/dev/verify_subagent_dispatch.md` with three sections:
## Procedure, ## Observed, ## Result. The user fills in ## Observed and
## Result during the HITL pilot (T-00) and re-confirmation (T-09 Phase A).

This script is one-shot diagnostic tooling — it is NOT deployed to
`~/.claude/scripts/` (per round-3 MIN-1 fix). Run directly from the
repo via `python3 quoin/dev/verify_subagent_dispatch.py`.
Exit 0 always.
"""
from __future__ import annotations

from pathlib import Path

TEMPLATE = """\
# Quoin Stage 1 — Subagent dispatch verification

## Procedure

Pre-merge HITL pilot (T-00) and post-install re-confirmation (T-09 Phase A).

1. Author the §0 fixture (T-01 acceptance must pass).
2. Insert §0 into ONLY `quoin/skills/triage/SKILL.md` per T-02
   per-file procedure (row "pilot" in the anchor table).
3. Run `bash install.sh` to deploy the modified `triage/SKILL.md`.
4. Open Claude Code on Opus 1M. Verify the model with `/model` or by
   reading the harness banner ("powered by the model named X").
5. Type: `/triage what should I run next?`
6. Observe ONE of three signals:
   (i)  "Spawning subagent" banner (or equivalent model-handoff signal)
        AND the cost-ledger row for the triage subagent records
        `claude-haiku` in the model column → DISPATCH VERIFIED.
   (ii) Fail-graceful warning
        `[quoin-stage-1: subagent dispatch unavailable; proceeding at current tier]`
        followed by triage's normal output on Opus → harness does not
        support `model` parameter on subagent spawn.
   (iii) NEITHER signal AND response generated on Opus (cost-ledger row
         records opus) → SILENT NO-OP. The §0 prose is mis-specified.
7. Record the observation below in ## Observed.
8. Set ## Result to one of: `verified`, `failed`, or `untested`.
9. T-09 Phase A re-confirmation (post-install, full-set deploy): repeat
   steps 4-7 with `/gate` (no arguments) instead of `/triage` and append
   a "Phase A re-confirmation" subsection under ## Observed.

## Observed

<!-- Fill in during the pilot run. -->

- Date / time of run:
- Harness banner string (from step 4):
- Signal seen (i / ii / iii):
- Cost-ledger row, model column for triage child:
- Tool-error message (if any):
- Notes / alternative-mechanism attempts:

## Result

<!--
One of: verified | failed | untested
T-02 batch insertion is gated on this being `verified`.
If `failed`, capture diagnostic detail above and STOP — stage-1 is
rewritten before any T-02 work proceeds.
-->

untested
"""


def main() -> int:
    target = Path(__file__).resolve().parent / "verify_subagent_dispatch.md"
    target.write_text(TEMPLATE, encoding="utf-8")
    print(f"Wrote template: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
