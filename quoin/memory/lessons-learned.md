# Lessons Learned

This file accumulates patterns, surprises, and insights from completed tasks. Every skill can read it to avoid repeating mistakes. Updated by `/end_of_day` and after each merged task.

<!-- Append new entries at the top. Keep entries concise — 2-4 lines each. -->

## 2026-04-30 — pipeline-efficiency-improvements / stage-3 (inline-gate flip)
**What happened:** Stage 3 flipped the post-implement and post-review `/gate` boundaries from subagent dispatch to inline execution. The post-implement boundary covers three sites in `/run/SKILL.md`: the primary path (line ~151) and two recursive recovery paths (lines ~169, ~185). The manual (non-`/run`) post-review path was also missing a `/gate` invocation entirely — added by T-20 in `/review/SKILL.md`'s "After the review" APPROVED branch.
**Lesson:** When introducing a default-mode change to a skill, always grep ALL callers (not just the obvious one). `/run/SKILL.md` had three post-implement gate sites; two were missed in the architecture phase. And always check both the orchestrated path (`/run`) and the manual path (direct skill invocation) — they can diverge silently if only one is updated.
**Applies to:** /architect, /plan, /implement. Regression test: `quoin/dev/tests/test_inline_gate_audit_log.py` (structural-canary form, guards all four inline boundaries + audit-log MUST language).

<!-- Example entry:
## 2026-03-17 — auth-refactor
**What happened:** Critic kept flagging missing token refresh handling for 3 rounds because the plan didn't mention the refresh token flow in the auth service.
**Lesson:** When planning auth-related changes, always trace the full token lifecycle (issue → refresh → revoke) — not just the happy path.
**Applies to:** /plan, /critic
-->
