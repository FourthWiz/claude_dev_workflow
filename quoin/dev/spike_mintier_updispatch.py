#!/usr/bin/env python3
"""
spike_mintier_updispatch.py — Standalone spike: verify Agent up-dispatch to opus tier.

THIS IS NOT A COLLECTED PYTEST TEST.
Run manually from a Sonnet (or cheaper) session:
  python3 quoin/quoin/dev/spike_mintier_updispatch.py

The spike spawns Agent(model="opus") and asks the child to report its model name.
If the child reports "opus" (or similar), up-dispatch is confirmed → use Option A template.
If the child reports the same tier as the parent (sonnet/haiku), or errors → use Option B.

SPIKE RESULT 2026-06-16:
  Not run in this session (implement session runs on Sonnet; spike requires live API +
  Sonnet parent session to observe tier escalation). Defaulting to Option B
  (AskUserQuestion-only) per the plan's guidance for "spike not yet confirmed".
  To re-run: launch from a Sonnet Claude Code session and run this script.
  If up-dispatch is confirmed, update _MINTIER_BLOCK_TEMPLATE in
  inject_pollution_dispatch.py to use Option A (remove this note and add spike result date).

USAGE:
  python3 quoin/quoin/dev/spike_mintier_updispatch.py

REQUIREMENTS:
  - Must be run from within a Claude Code session (Agent tool available)
  - Parent session must be Sonnet or cheaper (to test UP-dispatch to opus)
  - Live Anthropic API credentials required

EXPECTED OUTPUT:
  If up-dispatch works:
    [spike] child model: claude-opus-...  (or "opus" / "Opus" substring)
    [spike] RESULT: UP-DISPATCH CONFIRMED — use Option A template
  If up-dispatch does NOT escalate:
    [spike] child model: claude-sonnet-...  (same as parent)
    [spike] RESULT: UP-DISPATCH NOT CONFIRMED — use Option B template
"""

import sys


def main():
    print("spike_mintier_updispatch.py — Minimum-tier up-dispatch spike")
    print()
    print("This spike verifies whether Agent(model='opus') actually escalates")
    print("when invoked from a cheaper parent session.")
    print()
    print("To run this spike properly:")
    print("  1. Open a Claude Code session (not this script directly)")
    print("  2. From that session, ask Claude to run:")
    print("     python3 quoin/quoin/dev/spike_mintier_updispatch.py")
    print("  3. Claude will use the Agent tool to spawn an opus child and")
    print("     ask it to report its model name")
    print()
    print("Current status: Spike not yet run.")
    print("Default: Option B (AskUserQuestion-only) is being used.")
    print()
    print("When you run this spike from a Claude Code Sonnet session:")
    print("  - Claude will call Agent(model='opus') with a probe prompt")
    print("  - The child should report its model as 'opus' or similar")
    print("  - If confirmed: update _MINTIER_BLOCK_TEMPLATE to Option A")
    print("  - If not confirmed: Option B remains correct")
    print()
    print("See quoin/quoin/scripts/inject_pollution_dispatch.py for")
    print("the _MINTIER_BLOCK_TEMPLATE and the spike result comment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
