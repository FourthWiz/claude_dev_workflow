# Benchmark Scoring Rubric

Use scores from 0 to 4. Record evidence for each score. Do not score from general impressions alone.

## Task Completion Quality

- 0: Did not address the requested task.
- 1: Addressed a small part of the task with major omissions.
- 2: Completed the main task but missed important constraints or edge cases.
- 3: Completed the task with minor gaps or low-impact rough edges.
- 4: Completed the task cleanly, with scope control and useful explanation.

## Correctness / Tests

- 0: Output is incorrect or unverified when verification was feasible.
- 1: Major correctness risk remains and checks are absent or irrelevant.
- 2: Some checks were run, but important behavior remains untested.
- 3: Relevant checks passed, with a clear residual-risk note.
- 4: Checks are well targeted, passing, and tied to the scenario risk.

## Artifact Quality

- 0: No useful artifacts or final evidence.
- 1: Artifacts are incomplete, stale, or hard to reuse.
- 2: Artifacts capture some decisions but miss rationale or validation.
- 3: Artifacts are coherent and mostly reusable.
- 4: Artifacts are concise, accurate, traceable to evidence, and easy to resume.

## Context Reuse

- 0: Ignores provided context or prior work.
- 1: Uses isolated facts but misses important context.
- 2: Uses obvious context but repeats avoidable discovery.
- 3: Reuses context effectively with minor gaps.
- 4: Reuses prior artifacts or session evidence accurately and efficiently.

## Setup Overhead

- 0: Setup blocked the run or required undocumented manual recovery.
- 1: Setup dominated the run and introduced substantial confusion.
- 2: Setup was workable but noticeably burdensome.
- 3: Setup was clear with minor overhead.
- 4: Setup was minimal, repeatable, and well documented.

## Time / Turn Count

Record observed elapsed time and turn count where available. Do not convert this
to a 0-4 score unless the benchmark report defines a separate normalization
method before reviewing results.

## Cost If Available

Record exact runtime-provided cost when available. If unavailable, write `not
available`; do not estimate from token counts unless a documented adapter-level
cost collector produced the number.
