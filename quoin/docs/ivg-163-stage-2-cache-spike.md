# IVG-163 stage 2 — preamble prompt-cache measurement spike: documented analytic NULL

Verdict: both candidate cache-gated edits were analytically foreclosed before any
live-spawn spend, with a corrected derivation.

- **T-07(a)** (architect spawn-prompt prefix stabilization): NULL — the full
  stabilizable literal is 54 chars (~16 tokens), foreclosed on materiality
  (~$0.00002/spawn at cache-read rates) and breakpoint placement (quoin does not
  control `cache_control` placement; all 7 sampled `cache-break-state` files read
  `globalCacheStrategy: "none"`). Not by a 16-vs-512-token comparison — the
  provider minimum governs the total prefix, not an increment.
- **T-06** (specify/enrich bootstrap-wording unification): not executed — the nine
  spawn-target SKILL.md files share only a 10-byte common prefix (`---\nname: `),
  so no cache benefit is possible; the wording-consistency rationale awaits its own
  explicit consent in a future stage.
- **T-07(b)** (run/thorough_plan sentinel-order documentation): cut per the
  architecture's excludes clause ("spawn-site edits unsupported by the spike result").

Evidence artifacts (retained outside the repo, under the project's
`.workflow_artifacts/ivg-163-token-optimization-wave2/stage-2/`): `measurement-note.md`
(ceiling derivations, provider-doc citations, retrospective transcript numbers),
`cache_probe.py` (measurement harness), `cache-probe-report.json`, `freeze-list.md`.

This file exists solely as the stage's PR-visible pointer (per the stage plan's Q-08
minimal-pointer-commit decision); no source or generated file changed in this stage.
