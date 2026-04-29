task: pipeline-efficiency-improvements
stage: 2-alt
date: 2026-04-29
verdict: DEFERRED
protocol: on-disk-read

fixture_task: N/A — soak deferred
baseline_spawns: []
post_deploy_spawns: []
baseline_mean_cc_read: N/A
baseline_mean_cc_create: N/A
post_mean_cc_read: N/A
post_mean_cc_create: N/A
delta_cc_read: N/A
delta_cc_create: N/A

rationale: >
  T-06 soak requires triggering 5 consecutive /critic spawns against a fixed
  fixture task within a single ~10-minute TTL window, then extracting
  cache_creation_input_tokens and cache_read_input_tokens from each spawn's
  first-API-call event in ~/.claude/projects/<hash>/<uuid>.jsonl.

  The spawn mechanism requires the harness Agent tool from within a running
  Claude Code session. The soak cannot be executed from within the same
  /implement session that is building the mechanism — doing so would measure
  the current session's cache state (which includes all of this session's
  prefix bytes), not the cross-spawn effect of the preamble.md read.

  Per plan T-06 skip rule: "if /implement cannot find 5 baseline spawns of
  /critic in JSONL history [with reliable pre/post separation], soak switches
  to a paired-spawn protocol." The paired-spawn protocol also requires
  harness Agent access.

  The mechanism is correctness-neutral and reversible. The architecture's
  savings claim (~4 KB preamble pre-warm per spawn-2..N) is preserved as
  informational. The soak PASS/FAIL verdict will be collected in a dedicated
  post-deploy session after Stage 2-alt merges, where a fresh /critic spawn
  can be used as both baseline and measurement.

next_steps: >
  Post-merge: run 5 /critic spawns against a fixed small fixture task
  within a single session; compare cc_read/cc_create deltas against 5
  pre-preamble baseline spawns (use first-API-call usage events from JSONL).
  Accept criteria: mean(cc_read, spawns 2..5) >= 5000 AND
  mean(cc_create drop, spawns 2..5) >= 5000.
