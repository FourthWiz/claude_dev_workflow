"""Retired (IVG-162 T-07): the Tier-1 fast-path prose this file pinned lived
exclusively inside the `#### Fallback picker` section of checkpoint/SKILL.md,
which was deleted per the approved IVG-162 plan (Stage 3) — the section
self-labelled itself "This prose duplicates `checkpoint_picker.py:select_restore`;
the module is authoritative... slated for removal one release after S3 per Q-02"
and `checkpoint_picker.py` is now the sole restore-decision path (Step 1.0a
delegation), with the fail-OPEN path degrading to the graceful "no checkpoints
found" flow rather than a duplicated prose fallback.

The cross-task guard this file originally regression-tested (2026-06-04 incident:
the Tier-1 fast path returning a stale/cross-task checkpoint without validation)
is NOT lost — it is verified directly against the checkpoint_picker.py MODULE
(the actual runtime implementation) in `test_checkpoint_picker_roundtrip.py`:
  - test_tier1_same_task_fastpath_hit
  - test_cross_task_rejection_no_anchor
  - test_staleness_not_applied_at_tier1_fastpath
  - test_empty_and_unknown_sid_skips_tier1
These exercise `checkpoint_picker.select_restore()` itself, which is a stronger
guard than the retired prose-contract assertions here (which could only assert
on SKILL.md wording, since the picker runs inside the Claude model at runtime).

Nothing in this file is executed at collection time; it deliberately carries
zero test functions.
"""
