---
path: .workflow_artifacts/pipeline-efficiency-improvements/stage-2/current-plan.md
hash: HEAD
updated: 2026-04-29T14:00:00Z
updated_by: /revise-fast
tokens: 14400
plan_round: 3
stage_variant: alt-on-disk-read
---

## For human

Stage 2-alt re-plans subagent-preamble pre-compilation after v1's T-01 harness returned HARNESS-UNAVAILABLE (the Python subprocess cannot access the Claude Code Agent tool, so byte-transparency between parent prompt and child cannot be programmatically verified). The mechanism is now the **on-disk read approach** per the v1 audit doc `§Fork`: each of 7 child skills (critic, revise, revise-fast, plan, review, architect, gate — same membership as v1) gets ONE additive new bootstrap step that reads `~/.claude/skills/<skill>/preamble.md` if it exists. The preamble's bytes (format-kit §3 slice + full glossary, ~4000 bytes per "full" target; gate gets a ~200-byte stub) pre-warm the prompt cache for the existing format-kit/glossary reads later in bootstrap and at write-sites. **No parent-side prefix injection, no sentinel detection, no harness round-trip test.** Blast radius bounded to 7 child SKILL.md files + builder script + freshness CI test + install.sh deploy step + CLAUDE.md docs.

**8 tasks (T-01..T-08):** T-01 `quoin/scripts/build_preambles.py` builder (deterministic, idempotent, size-budget gate at 6144 bytes, exit codes 3/4/5/6/7); T-02 `quoin/dev/tests/test_preamble_freshness.py` CI gate (presence + freshness via per-source git-hash pinning + size-budget regression); T-03 generate the 7 `preamble.md` files via the builder; T-04 child SKILL.md additive edits across the 7 skills (with pre/post grep-count guard codified in `test_preamble_bootstrap_step.py`); T-05 install.sh deploy step (run builder before skill copy; conditional preamble.md copy in skill-copy loop); T-06 production soak measurement (5+ Medium-task spawns; acceptance: cache-read mean ≥ 5000 AND cache-creation drop ≥ 5000 — OR a documented inconclusive verdict); T-07 CLAUDE.md docs (Tier 1 carve-out for preamble.md as GENERATED; new `### Subagent preamble (Stage 2 of pipeline-efficiency-improvements)` sub-section); T-08 rollback rehearsal (delete one preamble.md, verify the soft-fail "if it exists" path works cleanly).

**Top risks:** R-3 over-eager editor deletes an existing format-kit/glossary reference during T-04 (highest blast radius — mitigated by D-06 additive-only principle + pre/post grep-count assertions + `test_preamble_bootstrap_step.py`). R-1 preamble drift after format-kit/glossary edit (mitigated by T-02 CI gate via per-source git-hash + install.sh always regenerates). R-5 soak measurement inconclusive due to harness compression or task-context noise (mechanism ships either way — correctness-neutral, reversible by deleting preamble.md files).

**What changed from v1:** v1 parent prefix-injection (v1 T-07 across thorough_plan/architect/run SKILL.md) is DELETED ENTIRELY. v1 child sentinel short-circuit H3 (v1 T-06) is REPLACED by a plain additive bootstrap step — no detection logic. v1 T-01 `verify_spawn_prompt_prefix.py` + tests + v1 T-02 audit doc remain shipped (commit e37fe64) as prior art for any future byte-transparency work.

**Out of scope:** parent-side prefix injection (deleted), sentinel detection in prompts, harness byte-transparency testing, lessons-learned phantom-path cleanup (audit `§Discrepancies` flagged it but it stays out-of-scope here), and any deletion/modification of EXISTING format-kit/glossary/lessons-learned references in the 7 child SKILL.md files.

**Open questions for /critic:** (a) T-06 TTL-safety window — is the 5-minute prompt-cache TTL sufficient, or should soak protocol pin spawns within a fixed sub-window? (b) does the harness apply a post-prompt compression pass that could distort `cache_read_input_tokens` reporting? (c) should gate ship a 200-byte stub or be skipped entirely from preamble generation (current choice: stub, for uniform install.sh / freshness-test handling — see D-04)?

## Convergence Summary

- **Task profile:** Medium (per architecture's Stage 2 designation)
- **Rounds:** 3
- **Final verdict:** PASS (round 3; verified by fresh Opus /critic subagent)
- **Key revisions across rounds:**
  - Round 1 → Round 2: 3 CRIT + 5 MAJ addressed. CRIT-1 broken BRE grep regex → fixed-string `-F` form. CRIT-2 self-contradicting parity assertion → step text drops literal path strings (paths replaced by bare words "format-kit / glossary"); parity grep is now mechanically valid. CRIT-3 within-spawn cache fallacy → D-01 rewritten with explicit cross-spawn semantics; T-06 acceptance computes mean over spawns 2..5; Notes Estimated-savings paragraph aligned. MAJ-1..MAJ-5: anchor-line drifts (revise-fast 48→54), wrong anchor text (revise/revise-fast 1a → "Read the task subfolder"), review off-by-one (1..8 → 1..9), gate prose-preserving paragraph insertion (no longer reformats existing prose), 5K vs 8K target rationale citing audit `§Discrepancies`.
  - Round 2 → Round 3: 1 NEW MAJ caught (Procedures pseudocode still had within-spawn cache annotations on 3 lines despite round-2's D-01 narrative correction) — fixed by adding cross-spawn-semantics header comment block and rewriting all three pseudocode annotations to be cross-spawn-correct. Verified via grep: `cache-hit` returns zero matches in pseudocode (was 3 pre-fix).
- **Remaining concerns:** 5 MIN findings deferred (documentation hygiene only; non-blocking for /implement). Carry-over from round 2: traceability-by-ID in deferred-MIN listing, `updated_by: /revise-fast` cosmetic inaccuracy (work was orchestrator-inline both rounds 2 and 3), pseudocode header comment density.
- **Process notes:** Round 2 and Round 3 revisions were both applied orchestrator-inline (after the Sonnet `/revise-fast` subagent stream-timed-out at 8m53s in round 2, and because round-3 fix was a single string substitution that did not benefit from a fresh agent context). All three /critic rounds ran as fresh Opus Agent subagents per /critic SKILL.md "fresh context" rule. The Round-3 critic-response-3.md required V-05-token-discipline cleanup post-validation (bare D-NN/T-NN/R-NN tokens → plain English) — minor mechanical-validation issue, fixed in place.

## State

```yaml
task: pipeline-efficiency-improvements
stage: 2
stage_name: subagent-preamble-on-disk-read
stage_variant: alt-on-disk-read
profile: Medium
mode: normal
model_plan: claude-opus-4-7
model_critic: claude-opus-4-7
model_revise: claude-sonnet-4-6
session_uuid: 0e58a4c8-dbf3-4a95-9619-77cc72222211
architecture_ref: ../architecture.md
audit_ref: ../../../quoin/docs/spawn-bootstrap-audit-2026-04-28.md
v1_plan_ref: ./v1-prefix-injection/current-plan.md
recursive_self_critique: no
spawn_targets:
  - critic
  - revise
  - revise-fast
  - plan
  - review
  - gate
  - architect
preamble_size_budget_bytes: 6144
slice_source: format-kit.md lines 189-207 inclusive (§3 Pick rules for ambiguous content; verified 1192 bytes)
glossary_source: glossary.md verbatim (~2819 bytes)
full_preamble_target_size_bytes: ~4000
gate_stub_target_size_bytes: ~200
historical_done:
  - v1 T-01 verify_spawn_prompt_prefix.py shipped (commit e37fe64); HARNESS-UNAVAILABLE verdict recorded
  - v1 T-02 spawn-bootstrap audit doc shipped at quoin/docs/spawn-bootstrap-audit-2026-04-28.md
```

## Tasks

1. ✅ T-01 — Preamble builder: `quoin/scripts/build_preambles.py`.
   - Depends on: nothing in this plan (audit doc already shipped as v1 T-02).
   - Acceptance:
     - File `quoin/scripts/build_preambles.py` exists, executable.
     - Reads two source files at fixed paths relative to script location: `quoin/memory/format-kit.md` (slice transform) and `quoin/memory/glossary.md` (verbatim transform). Path resolution: `SCRIPT_DIR = pathlib.Path(__file__).resolve().parent`; `REPO_ROOT = SCRIPT_DIR.parent.parent`; sources at `REPO_ROOT/memory/format-kit.md` and `REPO_ROOT/memory/glossary.md`.
     - Slice transform: extract `format-kit.md` lines 189 through 207 inclusive (the §3 H2 section "Pick rules for ambiguous content (the hard cases)" in full, with its closing `---` separator on line 207). Line range is fixed; do NOT search for `---` at runtime — the separator IS line 207 and is included in the slice as the end-marker (verified directly: `awk 'NR==189' format-kit.md` prints the §3 H2 heading; `awk 'NR==207' format-kit.md` prints `---`; `awk 'NR>=189 && NR<=207' format-kit.md | wc -c` returns exactly 1192).
     - Glossary transform: verbatim file content (~2819 bytes).
     - SPAWN_TARGETS dict literal (single source of truth for membership): `SPAWN_TARGETS = {"critic": "full", "revise": "full", "revise-fast": "full", "plan": "full", "review": "full", "architect": "full", "gate": "stub"}`. The 7-target membership matches `quoin/docs/spawn-bootstrap-audit-2026-04-28.md` aggregate (`total spawn targets: 7`); /implement is EXCLUDED (its bootstrap reads no boilerplate per audit `§Discrepancies`).
     - For each `(skill, kind)` in SPAWN_TARGETS:
       - kind `"full"`: write `quoin/skills/<skill>/preamble.md` containing YAML frontmatter + a `[format-kit-§3-slice]` marker + the §3 slice + a `[glossary]` marker + glossary content + trailing newline. The full-preamble content is target-INDEPENDENT (only the output path differs); per-skill output for full preambles is byte-identical except for frontmatter `path`.
       - kind `"stub"`: write `quoin/skills/<skill>/preamble.md` containing ONLY YAML frontmatter + a one-line note `# Stub preamble — gate has no boilerplate bootstrap reads; this file is kept for uniformity per spawn-bootstrap audit doc.` (~200 bytes total).
     - Frontmatter fields (every preamble.md, full or stub): `path` (the deployed target path `~/.claude/skills/<skill>/preamble.md`), `kind` (`full` | `stub`), `source_files` (YAML list of relative source paths from REPO_ROOT — empty list for stub), `source_hashes` (YAML map of `<source-relative-path>: <git-hash-object-of-source>`; empty map for stub), `generated_at` (ISO-8601 UTC timestamp), `generated_by` (`build_preambles.py`), `total_bytes` (int — full byte size of the file body excluding frontmatter).
     - Determinism: byte-stable output given identical sources. Two consecutive runs with no source changes produce byte-identical files EXCEPT for the `generated_at` field. T-02 freshness test compares `source_hashes` to current `git hash-object` of each source — that is the drift signal, not the timestamp.
     - Size-budget gate: if any generated full preamble exceeds 6144 bytes, builder exits 3 with `PREAMBLE OVERSIZE: <skill>/preamble.md is N bytes (budget: 6144 bytes)` and writes nothing for that skill. Per-skill atomic: write to `<dest>.tmp` then `os.replace()` — partial-write crash never leaves a half-written preamble.
     - Failure modes: missing source file → exit 4 (`MISSING SOURCE: <relative-path>`); SPAWN_TARGETS empty → exit 5 (`EMPTY SPAWN_TARGETS`).
     - CLI surface: `--help` (argparse standard) prints exit codes + the SPAWN_TARGETS membership; `--dry-run` writes one section per skill to stdout (separator `=== <skill> ===`) instead of disk; `--check` runs the freshness check (T-02) instead of writing. `--dry-run` and `--check` are mutually exclusive — script exits 6 on both.
     - Manual smoke at /implement T-01 close: `python3 quoin/scripts/build_preambles.py` produces 7 preamble.md files; `python3 quoin/scripts/build_preambles.py --dry-run` writes 7 sections to stdout; `python3 quoin/scripts/build_preambles.py --check` exits 0 immediately after a fresh write.
     - Test: `quoin/scripts/tests/test_build_preambles.py` — unit tests cover (a) two consecutive runs with identical sources produce byte-identical output (frontmatter `generated_at` field stripped before compare); (b) deliberately-oversized stub source (>6144 bytes) triggers exit 3; (c) missing source file triggers exit 4; (d) empty SPAWN_TARGETS triggers exit 5; (e) `--check` over an in-sync state exits 0; (f) `--check` over an out-of-sync state (modified source after build) exits 7 with stderr listing the stale skill; (g) `--dry-run` and `--check` together exit 6. Tests use a tmpdir-rooted virtual project layout — do NOT touch the real `quoin/skills/` tree.

2. ✅ T-02 — Preamble freshness test (CI gate): `quoin/dev/tests/test_preamble_freshness.py`.
   - Depends on: T-01 builder.
   - Acceptance:
     - Test file at `quoin/dev/tests/test_preamble_freshness.py`, pytest-discoverable.
     - Two parametrized test classes, both must pass.
       - Presence test (parametrized over the 7 targets): asserts `quoin/skills/<skill>/preamble.md` exists. Failure message: `Preamble for <skill> is missing — run python3 quoin/scripts/build_preambles.py`. No skip-on-absent.
       - Freshness test (parametrized over the same 7): only runs if file exists; parses YAML frontmatter `source_hashes` map; for each `(source-relative-path, expected-sha)` computes current git-sha via `git hash-object <repo-root>/<source-relative-path>` (NOT `git ls-files --stage` — the index can lag the working tree); asserts `current-sha == expected-sha`. Mismatch failure: `Preamble for <skill> is stale: source <path> changed (preamble has <expected>, current is <current>). Run: bash install.sh (or python3 quoin/scripts/build_preambles.py)`.
     - Test also asserts each preamble.md is < 6144 bytes (size-budget regression — duplicates T-01's check at test-time so a hand-edited oversized preamble fails CI even if it bypassed the builder).
     - Test asserts each preamble starts with `---\n` (frontmatter sanity check).
     - Test runs in CI on every PR via standard pytest discovery; no separate plumbing.
     - Stub-skill (gate) special case: empty `source_hashes` map → freshness check is vacuously true; presence + size-budget checks still apply.

3. ✅ T-03 — Generate the seven preamble.md files.
   - Depends on: T-01 builder, T-02 freshness test.
   - Acceptance:
     - The 7 files exist after running the builder: `quoin/skills/critic/preamble.md`, `quoin/skills/revise/preamble.md`, `quoin/skills/revise-fast/preamble.md`, `quoin/skills/plan/preamble.md`, `quoin/skills/review/preamble.md`, `quoin/skills/architect/preamble.md`, `quoin/skills/gate/preamble.md`. `quoin/skills/implement/preamble.md` is NOT generated (per audit `§Discrepancies` — implement bootstrap reads no boilerplate).
     - Generation: `python3 quoin/scripts/build_preambles.py` (no flags). /implement records per-skill bytes in the implementation log (e.g. `critic: 4015 bytes; revise: 4015; ...; gate: 198`).
     - Expected sizes (verified against the §3 slice = 1192 bytes and glossary ~2819 bytes): each full preamble ≈ 4000–4100 bytes (slice 1192 + markers ~40 + glossary ~2819 + frontmatter ~150 = ~4200 bytes; well below 6144 budget). Gate stub ≈ 200 bytes. Actual sizes recorded by /implement at T-03 close.
     - Files committed to git. /implement uses `git add -f quoin/skills/<skill>/preamble.md` defensively to avoid the gitignored-parent issue (lesson 2026-04-23 in source memory).
     - Manual sanity: `head -30 quoin/skills/critic/preamble.md` shows valid frontmatter then the `[format-kit-§3-slice]` marker on its own line; `wc -c` reports < 6144.

4. ✅ T-04 — Child SKILL.md edits: additive on-disk preamble read in bootstrap.
   - Depends on: T-03 preambles exist.
   - Acceptance:
     - For each of the 7 spawn targets (critic, revise, revise-fast, plan, review, gate, architect), edit `quoin/skills/<skill>/SKILL.md` to add ONE new bootstrap step. No other text in the existing `## Session bootstrap` section changes — additive only.
     - Insertion location, per skill (anchored to the literal text of the existing first-numbered bootstrap step; /implement does `grep -n` at edit time to confirm anchor BEFORE editing — line numbers in this plan are advisory):
       - critic: existing step 1 starts with `**Round 1 only:** Read \`.workflow_artifacts/memory/lessons-learned.md\``; insert NEW step BEFORE it, renumber existing steps 1..6 to 2..7. The numbered-step format makes renumbering trivial; line ~13.
       - revise: existing bootstrap step 1 begins with the literal text `Read the task subfolder: resolve the artifact path via`; insert NEW step 1 BEFORE this existing step and renumber existing steps 1..5 to 2..6. Line ~14 (advisory).
       - revise-fast: existing bootstrap step 1 begins with the same literal text `Read the task subfolder: resolve the artifact path via` (per the SYNC contract noted in revise-fast SKILL.md); insert NEW step 1 BEFORE this existing step. AFTER the §0 dispatch block ending at line 54 (`Otherwise (already at or below declared tier, OR prompt has [no-redispatch] sentinel, OR dispatch unavailable): proceed to §1 (skill body).`), and BEFORE the `## Session bootstrap` H2 at line 56. The existing first numbered step is at line 59. Renumber 1..5 to 2..6.
       - plan: existing step 1 starts with `Read \`.workflow_artifacts/memory/lessons-learned.md\``; insert NEW step BEFORE, renumber existing 1..6 to 2..7. Line ~13.
       - review: existing step 1 starts with `Read lessons-learned`; insert NEW step BEFORE, renumber 1..9 to 2..10 (verified review/SKILL.md has 9 numbered bootstrap steps, not 8 — round-1 MAJ-3). Line ~13.
       - architect: existing step 1 starts with `Read \`.workflow_artifacts/memory/lessons-learned.md\``; insert NEW step BEFORE, renumber 1..6 to 2..7. Line ~17.
       - gate: existing `## Session bootstrap` is a single prose paragraph (no numbered list — it only carries the cost-tracking note). Insert NEW step text as an unnumbered paragraph IMMEDIATELY AFTER the `## Session bootstrap` heading and BEFORE the existing `Cost tracking note:` paragraph. **DO NOT renumber, prefix, or reformat the existing prose paragraph** — the existing text stays verbatim (per round-1 MAJ-4: any structural reformatting would violate the additive-only principle in D-06). The result is two paragraphs under `## Session bootstrap`: the new preamble-read paragraph first, then the unchanged cost-tracking-note paragraph below. /implement records the gate edit shape in the implementation log.
     - New bootstrap step text (shared verbatim across all 7 skills, with `<skill>` substituted per-target). Note the deliberate omission of the literal strings `~/.claude/memory/format-kit.md` and `~/.claude/memory/glossary.md` — those literal paths must NOT appear in the new step (so the no-regression parity grep at acceptance below stays meaningful):

       ```
       Read `~/.claude/skills/<skill>/preamble.md` if it exists; if missing or empty, proceed normally. Purely additive cache-warming — every other read in this `## Session bootstrap` section, and every write-site format-kit / glossary reference (per §5.3 / §5.4 write-site instructions), stays in force unchanged. The intent is CROSS-SPAWN cache reuse: spawn N+1 of this skill with a byte-identical task fixture hits cache from spawn N's preamble.md tool_result, within the 5-minute prompt-cache TTL. Within a single spawn there is no cache benefit — savings only materialize on subsequent spawns whose prompt prefix is byte-identical through the preamble read. (Stage 2-alt of pipeline-efficiency-improvements.)
       ```

     - Insertion rule: the new step is inserted BEFORE any existing numbered bootstrap step so it runs FIRST — the cache-warming intent requires the read to land early in the prompt, before the parent's task-specific reads displace cache headroom.
     - Acceptance grep (per skill): `grep -nF '~/.claude/skills/<skill>/preamble.md' quoin/skills/<skill>/SKILL.md` returns ≥ 1 hit (the literal target path appears verbatim).
     - Acceptance grep (cross-skill): `grep -rnF 'preamble.md\` if it exists; if missing or empty' quoin/skills/` returns exactly 7 hits (one per target). Fixed-string `-F` is used deliberately — no regex metachars, so this matches verbatim regardless of shell/grep dialect (CRIT-1 round 1: prior BRE form `'.\*'` was a literal asterisk match, returning zero hits).
     - Acceptance grep (no-regression on existing reads): for each of the 7 skills, `grep -cF '~/.claude/memory/format-kit.md' quoin/skills/<skill>/SKILL.md` returns the SAME integer pre-edit and post-edit (verified pre-edit counts on disk: critic / revise / revise-fast / plan / review / architect = 2 each; gate = 1). Same for `'~/.claude/memory/glossary.md'`. Same for `'.workflow_artifacts/memory/lessons-learned.md'`. The new step text DOES NOT contain these literal path strings (per the design note above), so the parity assertion is mechanically valid — adding the new step does not inflate the count. /implement captures the pre-edit counts in the session log BEFORE applying any T-04 edit, then re-runs after editing to assert equality. This is the explicit "additive only" guard that prevents an over-eager editor from deleting an existing reference.
     - Test: `quoin/dev/tests/test_preamble_bootstrap_step.py` — for each of 7 skills, asserts (a) the new step text appears verbatim with the correct `<skill>` substitution; (b) the existing format-kit.md reference in `## Session bootstrap` is still present; (c) the existing glossary.md reference in `## Session bootstrap` is still present; (d) the existing format-kit.md reference at the write-site (lines that match the pattern `Reference files (apply HERE at the body-generation WRITE-SITE`) is still present for the 6 skills that have a write-site (gate has none); (e) the new step appears BEFORE every other bootstrap read in source order (grep `-n` ordering check).

5. ✅ T-05 — `install.sh` integration: build + deploy preambles.
   - Depends on: T-01 builder, T-03 preambles exist.
   - Acceptance:
     - Edit 1 (`quoin/install.sh` Step 2a, NEW): insert a new `header "Step 2a: Regenerating subagent preambles..."` block IMMEDIATELY AFTER the existing Step 1 (prerequisite check, ends ~line 82 `success "Prerequisites OK"`) and BEFORE Step 2 (skill copy starting ~line 84 `header "Step 2: Copying skills..."`). The block runs `python3 "$SCRIPT_DIR/scripts/build_preambles.py" || { error "build_preambles.py failed"; exit 1; }`. On success: `success "Regenerated 7 subagent preambles in $SCRIPT_DIR/skills/*/preamble.md"`. The Step-2a-BEFORE-Step-2 sequencing is REQUIRED — Step 2's skill copy loop (Edit 2 below) copies the just-built preambles, so the build must finish first.
     - Edit 2 (existing Step 2 skill-copy loop at lines 91-98): the loop currently copies `SKILL.md` only; extend to also copy `preamble.md` if it exists. Diff is one new line inside the `if [ -d "$skill_dir" ]; then` block, after the `cp "$skill_dir/SKILL.md" ...` line: `if [ -f "$skill_dir/preamble.md" ]; then cp "$skill_dir/preamble.md" "$USER_SKILLS_DIR/$skill_name/preamble.md"; fi`. The conditional handles "skill has no preamble" (the 14 non-spawn-target skills, including /implement which is excluded per audit `§Discrepancies`).
     - Edit 3 (existing Step 2b v3-scripts loop at lines 135-145): add `build_preambles.py` to the loop list. Change `for script_file in validate_artifact.py path_resolve.py cost_from_jsonl.py classify_critic_issues.py; do` to `for script_file in validate_artifact.py path_resolve.py cost_from_jsonl.py classify_critic_issues.py build_preambles.py; do`. Note: `verify_spawn_prompt_prefix.py` from v1 T-01 is NOT added to install.sh deploy — it is a one-shot diagnostic that lives at `quoin/scripts/` only (per CLAUDE.md Tier 1 "Source files" carve-out which already lists `quoin/dev/verify_subagent_dispatch.md` under the same precedent). /implement verifies this against CLAUDE.md before applying Edit 3.
     - Edit 4 (existing final summary line at lines 218-223): update the v3 scripts summary to enumerate `build_preambles.py` alongside the existing four. Change `(validate_artifact.py, path_resolve.py, cost_from_jsonl.py, classify_critic_issues.py)` to `(validate_artifact.py, path_resolve.py, cost_from_jsonl.py, classify_critic_issues.py, build_preambles.py)`.
     - Lesson 2026-04-27 dual-cleanup pattern: T-05 is purely additive; no cleanup loop entry needed (Stage 2-alt introduces the preamble.md file class for the first time deployed; v1's stage never reached deploy). The existing cleanup loops at lines 149-161 are byte-untouched.
     - Smoke acceptance (T-08 manual smoke): in a tmpdir-rooted `~/.claude/`, run `bash quoin/install.sh` and verify (a) `~/.claude/skills/critic/preamble.md` exists and is non-empty; (b) `~/.claude/skills/gate/preamble.md` exists and is ~200 bytes (frontmatter-only stub); (c) `~/.claude/scripts/build_preambles.py` exists and is +x; (d) all 7 spawn targets have a `preamble.md` deployed.

6. ⏳ T-06 — Soak / measurement: DEFERRED — see post-implement-soak-2026-04-29.md (requires live multi-spawn measurement in a separate session post-merge).
   - Depends on: T-01..T-05 all green.
   - Acceptance (soak runs DURING /implement; measurement is the empirical savings claim):
     - Methodology: after T-05 install.sh deploys preambles, /implement triggers 5 Medium-profile spawns of one fixed target (default: /critic — the spawn target with the largest expected cache effect after architecture's MAJ-3 added it). Each spawn runs against the same fixture task context (a tmpdir-rooted minimal `.workflow_artifacts/test-stage2-soak/stage-1/current-plan.md` plus a tiny `architecture.md`).
     - For each of the 5 spawns: extract the four token-accounting fields from the spawn's first-API-call event in `~/.claude/projects/<project-hash>/<uuid>.jsonl` via `~/.claude/scripts/cost_from_jsonl.py` (the existing helper already extracts `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`). Record per spawn: `<spawn-N> | input | output | cc_create | cc_read`.
     - Baseline: compute the same four fields from 5 PRIOR spawns of the same skill BEFORE the on-disk-read step was added. Source: most recent 5 `/critic` spawns in the project's JSONL history that predate this PR's merge (or that match `cache_read_input_tokens < 1000` as a proxy if pre/post cannot be cleanly separated). /implement records baseline in the soak log.
     - Acceptance gate (the savings claim — both must hold across the 5-spawn mean of spawns 2..5; spawn 1 establishes the cache and is excluded from the mean per CRIT-3 cross-spawn semantics):
       - (a) `mean(post_cache_read_input_tokens over spawns 2..5) >= 5000` — cache hits are the WIN signal; preamble bytes were served from cache, not regenerated.
       - (b) `mean(post_cache_creation_input_tokens over spawns 2..5) <= mean(baseline_cache_creation_input_tokens) - 5000` — less new content was cache-created on the post-deploy side than baseline.
       - **Threshold rationale (round-1 MAJ-5):** The parent architecture's headline target was ≥8K input-token drop per spawn, grounded in an assumed ~20 KB cc/spawn from boilerplate including CLAUDE.md (~14 KB). The audit doc `§Discrepancies` has since established that CLAUDE.md is harness-injected (system-side), NOT a skill-bootstrap read, and is therefore not reducible by the preamble mechanism. Realistic preamble bytes are ~4 KB (1.2 KB §3 slice + 2.8 KB glossary + frontmatter), so a 5K saving (cache_read ≥ 5K AND cache_creation drop ≥ 5K) is the empirical floor below which the mechanism does not pay off. The 5K target is a deliberate down-revision of the architecture's 8K headline based on the audit-confirmed scope reduction; /critic should treat the 5K ↔ 8K gap as resolved by audit `§Discrepancies`.
     - **TTL safety:** Anthropic prompt cache has a 5-minute TTL. The 5 post-deploy spawns MUST run within a single ~10-minute window so cache lifetime overlaps across spawns 2..5 (the parent's preamble.md read in spawn 1 caches; spawns 2..5 hit the cache). If wall-clock between any two consecutive spawns exceeds 4 minutes, /implement aborts the soak and re-runs from spawn 1.
     - **Negative threshold:** if either (a) or (b) is violated, soak FAILS (not skips). Falling short means the preamble file is bloated (R-1 from this plan's risk register) OR the parent never read preamble.md before spawning OR the harness applies separate compression that obscures the cache-read signal. /implement investigates root cause before the PR ships.
     - Soak result documented in `pipeline-efficiency-improvements/stage-2/post-implement-soak-2026-MM-DD.md` (Tier 3 ephemeral; terse-only on disk; no `## For human` block). Captures: chosen fixture task, baseline-spawn UUIDs (5), baseline mean cc_read + cc_create, post-deploy spawn UUIDs (5), post-deploy mean cc_read + cc_create, deltas, PASS/FAIL verdict.
     - Skip rule: if /implement cannot find 5 baseline spawns of /critic in JSONL history, soak switches to a paired-spawn protocol: spawn the fixture task twice with `[no-preamble-read]` env var set (skips T-04's new bootstrap step) for baseline, then twice without; same gate. /implement documents the protocol switch in the soak log.

7. ✅ T-07 — Documentation: update CLAUDE.md to reference the on-disk-read mechanism.
   - Depends on: T-04 child edits committed, T-05 install.sh edits committed.
   - Acceptance:
     - Edit 1 (`quoin/CLAUDE.md`, NEW sub-section under `## Common rules for all skills`): add `### Subagent preamble (Stage 2 of pipeline-efficiency-improvements)`. Content: "The 7 spawn-target skills (critic, revise, revise-fast, plan, review, gate, architect) read `~/.claude/skills/<skill>/preamble.md` as the FIRST step of their `## Session bootstrap`. This pre-warms the prompt cache for the §3 slice of `format-kit.md` plus `glossary.md`, so the explicit format-kit / glossary reads later in the same bootstrap (and the references at write-sites per `format-kit.md` §1 / lesson 2026-04-23) hit cache rather than cold-loading. The preamble is purely additive — every other bootstrap read remains in force, the write-site references remain in force, and a missing preamble.md falls through to today's behavior (no error). The mechanism is purely a token-cost optimization; it MUST NOT change skill outputs. The preamble is GENERATED by `quoin/scripts/build_preambles.py` at install time; never hand-edit; see `quoin/docs/spawn-bootstrap-audit-2026-04-28.md` for membership rationale and `§Discrepancies` for why /implement is not a target. The full-preamble target size is ~4 KB (1.2 KB §3 slice + 2.8 KB glossary + frontmatter); gate gets a ~200-byte uniformity stub."
     - Edit 2 (existing Tier 1 carve-out list under `### Tier 1 — files that always stay English`, "Source files" subsection): add a single line `quoin/skills/<skill>/preamble.md (any of the 7 spawn targets — critic, revise, revise-fast, plan, review, gate, architect) — GENERATED by quoin/scripts/build_preambles.py at install time; never hand-edit. The file is machine-generated English content; listed here only for disambiguation — it is NOT a Tier 1 hand-edited source file.`. The carve-out note IS the documentation; the file itself is not a Tier 1 entry — listing it makes the lookup table complete for a future reader who searches for `preamble.md` in CLAUDE.md.
     - Edit 3 (existing `### §0 Model dispatch preamble` section): no edit. The on-disk-read mechanism is unrelated to the §0 dispatch sentinel; no `[preamble-inlined]` sentinel exists in this plan. /implement verifies no edit is required by reading the existing §0 section before closing T-07.
     - Acceptance grep: `grep -nF 'Subagent preamble (Stage 2 of pipeline-efficiency-improvements)' quoin/CLAUDE.md` returns 1 hit; `grep -nF 'preamble.md (any of the 7 spawn targets' quoin/CLAUDE.md` returns 1 hit.
     - The CLAUDE.md edit propagates to the deployed copy via `bash install.sh` Step 3 (existing — no new install.sh edit needed for CLAUDE.md propagation; the Python sed-replace block at lines 187-200 already handles in-place updates).
     - Test: `quoin/dev/tests/test_claude_md_preamble_section.py` — asserts `quoin/CLAUDE.md` contains the new `### Subagent preamble (Stage 2 of pipeline-efficiency-improvements)` heading + the "purely additive" phrase + the "GENERATED by quoin/scripts/build_preambles.py" phrase + the explicit Tier 1 carve-out line.

8. ✅ T-08 — Smoke verification at /implement: end-to-end install + test pass + rollback rehearsal.
   - Depends on: T-01..T-07 complete.
   - Acceptance:
     - Manual step: `bash quoin/install.sh` against the development environment. Verify per T-05 acceptance bullets (preambles deployed, builder script deployed).
     - `pytest quoin/dev/tests/ quoin/scripts/tests/` runs to completion. Stage 2-alt tests (`test_build_preambles.py`, `test_preamble_freshness.py`, `test_preamble_bootstrap_step.py`, `test_claude_md_preamble_section.py`) all PASS. Pre-existing failures (per session-state file 2026-04-28-pipeline-efficiency-improvements.md) remain unchanged.
     - /implement records final pytest counts in the session log: `T-08 pytest: <P> passed, <F> failed, <S> skipped — Stage 2-alt tests: <P2> passed, <F2> failed, <S2> skipped`.
     - Rollback rehearsal (one-shot smoke; no commit): in a scratch git stash, delete `quoin/skills/<any-skill>/preamble.md` and re-run that skill's bootstrap with the deployed `~/.claude/skills/<skill>/SKILL.md`; verify the missing-file branch fires (the new step's "if it exists" clause holds — bootstrap proceeds via the existing format-kit / glossary reads). /implement documents the rehearsal in the session log: `T-08 rollback rehearsal: deleted quoin/skills/critic/preamble.md; re-ran critic bootstrap; verified existing format-kit + glossary reads still fire; PASS`.
     - Cost-ledger row appended for the smoke pass: `<session-uuid> | <YYYY-MM-DD> | implement | claude-sonnet-4-6 | task | T-08 Stage-2-alt smoke verification: install.sh + pytest <P>/<F>/<S> + rollback rehearsal PASS`.
     - This task ships nothing new — it is the gate that says "Stage 2-alt is structurally complete and passing".

## Decisions

D-01 — Transport mechanism: child reads `~/.claude/skills/<skill>/preamble.md` directly at bootstrap. The architecture's Stage 2 prerequisite test (v1 verify-spawn-prompt-prefix.py) returned HARNESS-UNAVAILABLE (exit 2): the Python subprocess cannot access the Claude Code harness Agent tool, so byte-transparency between parent prompt and child cannot be programmatically verified. Per architecture R-Q2 and the audit doc `§Fork`, the recommended alternate is the on-disk read approach (audit doc candidate 1, "lowest-risk alternate"). No parent injection, no sentinel detection in the prompt, no harness round-trip test required.

**Cache mental model (per round-1 CRIT-3):** Anthropic prompt cache hits on EXACT prompt-prefix bytes, not on content overlap. Within a SINGLE spawn, reading preamble.md and then reading format-kit.md produces two distinct tool_result blocks; the second is a novel-prefix and does NOT hit cache from the first. **The savings only materialize CROSS-SPAWN.** When the parent orchestrator (or any caller) spawns the same skill twice within the 5-minute prompt-cache TTL with byte-identical task fixtures, the second spawn's prompt prefix is byte-identical to the first through the preamble.md tool_result; the second spawn pays `cache_read` for the preamble bytes (and for the existing bootstrap reads that share the same prefix), not `cache_creation`. Within-spawn savings are zero. Consequences:
- Direct user invocations of a spawn-target skill (no parent orchestrator, single-shot) pay the full ~4 KB preamble read with NO cache benefit on that single spawn. Net direct-invocation cost: ~4 KB preamble read + ~410-byte new bootstrap step text in SKILL.md (read by harness as part of skill loading) ≈ 4.4 KB more input per single-shot vs. today. For workflow-orchestrator-driven spawn sequences (the common path), the preamble is amortized across spawns 2..N.
- The fail-OPEN behavior is automatic via the "if it exists" clause; no warning is needed because no parent injection happens.
- The mechanism is reversible by deleting the preamble.md files (rollback per R-1 below).
- Soak protocol (T-06) measures CROSS-SPAWN cache reuse — spawns 2..5 of a fixed-fixture sequence — not within-spawn warming. The fixed-fixture rule already implies this; the round-2 narrative makes it explicit.

D-02 — No parent protocol change. The v1 plan added prefix-injection edits to `quoin/skills/thorough_plan/SKILL.md`, `quoin/skills/architect/SKILL.md`, and `quoin/skills/run/SKILL.md` (v1 T-07). Stage 2-alt makes ZERO parent edits. Spawn prompts are unchanged. The orchestrators (/thorough_plan, /run, /architect Phase 4) emit the same `{P}` task prompt they emit today; only the children's bootstrap behavior changes. Consequences:
- The blast radius of Stage 2-alt is strictly bounded to the 7 child SKILL.md files plus the new builder + freshness test + install.sh deploy step + CLAUDE.md doc. /thorough_plan, /architect, /run are byte-untouched.
- No new sentinel parsing logic in any child. The §0 dispatch preamble (`[no-redispatch]` family) is untouched and continues to work identically.
- A future "true byte-transparent prompt injection" mechanism (v2-revisited) can be layered on top of D-01 without conflict — the on-disk read becomes the fallback, prompt injection becomes the optimization. That is OUT OF SCOPE for Stage 2-alt.

D-03 — Preamble target membership: 7 skills (critic, revise, revise-fast, plan, review, gate, architect). This is the same 7-target set as v1 (post round-3 MAJ-2 fix). Per `quoin/docs/spawn-bootstrap-audit-2026-04-28.md` aggregate: `total spawn targets: 7`. The 6 "full" targets all have a bootstrap that reads `~/.claude/memory/format-kit.md` and `~/.claude/memory/glossary.md` (cf. `## Skill audit table` per-skill rows in the audit doc, plus the `## Skill-list aggregate` section: "union boilerplate file set (deduplicated): {~/.claude/memory/format-kit.md, ~/.claude/memory/glossary.md}"). Gate has no boilerplate bootstrap reads (audit doc gate aggregate: "0 boilerplate reads") but is included for uniformity — the dict has a row for every spawn target, and the install.sh skill-copy loop's `if [ -f preamble.md ]` conditional fires uniformly. /implement is EXCLUDED for the same reason as in v1: its bootstrap reads only `lessons-learned.md` (a phantom file at deployed path; cleanup is OUT OF SCOPE per audit `§Discrepancies`) plus task-specific paths.

D-04 — Gate stub rationale. Gate's bootstrap reads no boilerplate; an empty preamble would suffice. We ship a frontmatter-only stub instead because (a) the SPAWN_TARGETS dict has a row for every spawn target — a "gate has no preamble" branch in the builder is more code than a 200-byte stub; (b) the install.sh skill-copy loop's `if [ -f preamble.md ]` conditional fires uniformly — no per-skill special case in install; (c) the freshness test's "preamble must exist" presence assertion fires uniformly — a missing gate preamble would be a false-positive failure; (d) future stage work that adds a gate-specific preamble does not need a builder change. Trade-off: 200 bytes of disk per skill we install. Acceptable.

D-05 — Graceful fallback for missing preamble.md. The new bootstrap step text reads "if it exists. ... if the file is missing or empty, proceed normally". This is a soft-fail: the child does not error, log, or warn — it simply proceeds with the existing format-kit / glossary reads. Rationale: the only correctness-relevant content (format-kit §3 slice + glossary content) is ALREADY read by the existing bootstrap; the preamble's job is solely to pre-warm the cache. A missing preamble loses the cache-warming benefit but preserves correctness. We deliberately do NOT add a one-line warning to keep the bootstrap clean of conditional log emissions in the common path. Consequences:
- Rollback by deleting all preamble.md files is safe: no warnings, no errors, just slightly higher per-spawn cost until the next install.sh run.
- A drift between source files and stale preamble.md (post-format-kit-edit, pre-rebuild) is caught by T-02 freshness test in CI, not at runtime.

D-06 — Additive-only edit principle for T-04. The single largest risk vector for this stage is an over-eager editor (human or AI) deleting an existing format-kit / glossary reference while adding the new preamble step. Per format-kit.md §1 / lesson 2026-04-23, the write-site references to format-kit and glossary MUST stay in place — they are the canonical reference for primitive selection at write time. The bootstrap reads are the canonical context-loading. The preamble is purely cache-warming, not a replacement for either. T-04's acceptance includes a pre/post grep-count assertion on each existing reference to make this guard mechanical: pre-edit count == post-edit count for every existing format-kit / glossary / lessons-learned reference in each of the 7 SKILL.md files. The test `test_preamble_bootstrap_step.py` codifies the same check.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation | Rollback |
|---|---|---|---|---|---|
| R-1 | Preamble drift: a source file (format-kit.md or glossary.md) updates without preamble regen → child's preamble.md is stale relative to current sources. The format-kit / glossary reads in the same bootstrap still fire and read current content, so correctness is preserved — but the cache-warming advantage flips: the cached preamble bytes do not match the current bytes, so the explicit reads cache-miss. | medium | low (correctness preserved; only cache benefit lost) | T-02 freshness test in CI (per-source git-hash pinned in preamble frontmatter; mismatch fails the test); install.sh always regenerates (T-05 Edit 1); per-skill source_hashes recorded at build time | delete the affected preamble.md OR run `python3 quoin/scripts/build_preambles.py` (or `bash install.sh`); freshness test passes again |
| R-2 | Preamble.md not found at runtime (deployment incomplete, missing from PR, install.sh failure, manual delete) → child cold-reads format-kit and glossary as today | low | low (cosmetic; no error; cache-warming benefit lost for one session) | the new bootstrap step text is `if it exists` — soft-fail by design; existing format-kit + glossary reads cover correctness | re-run `bash install.sh`; preamble.md re-deployed |
| R-3 | T-04 child SKILL.md edit accidentally deletes an existing format-kit / glossary / lessons-learned reference while adding the new preamble step (the over-eager-editor failure mode) | medium | medium (changes skill bootstrap semantics; a /critic round may miss format-kit content) | D-06 additive-only principle; T-04 acceptance includes pre/post grep-count assertion on every existing reference; `test_preamble_bootstrap_step.py` test asserts each existing reference is still present post-edit; /implement captures pre-edit grep counts in session log before editing | revert the affected SKILL.md per skill (one-file revert per skill); /implement reapplies the additive edit using the explicit grep-guarded protocol |
| R-4 | Preamble grows past 6144-byte budget (e.g. format-kit.md grows or a future stage decides to widen the slice) → builder exits 3, install.sh fails, deploy halts | low | medium (deploy-blocking) | T-01 builder exits 3 with a clear message; T-02 freshness test asserts < 6144 at test-time; current measured size ~4000 bytes is 33% below budget so leaves headroom; if the budget is hit, fallback option C (drop the §3 slice for the affected skill, glossary-only preamble at ~2900 bytes) is supported by the dict structure | trim the §3 slice (remove example code blocks if any are added); OR drop the slice for affected skills (glossary-only preamble) by adjusting the SPAWN_TARGETS dict; commit + re-run install.sh |
| R-5 | Soak measurement (T-06) inconclusive because cache-creation and cache-read deltas across 5 spawns are dominated by other variables (different task contexts, harness-side compression, time-of-day effects) | medium | low (the savings claim is unverifiable but the mechanism is correctness-preserving and reversible) | T-06 fixes the fixture task across all 5 spawns; TTL-safety window is enforced; baseline uses the same skill's prior spawns; if measurement is inconclusive, /implement reports the inconclusive verdict and ships the mechanism anyway (the change is correctness-neutral, the savings claim is informational) | flip Stage 2-alt to "deploy without measurement" — the mechanism shipping with no quantified savings is a valid outcome; the architecture's $1.30–2.60/spawn estimate becomes informational |
| R-6 | An over-eager future editor adds a per-skill SKILL.md edit that BLOCKS bootstrap on missing preamble.md (e.g. converts the soft-fail "if it exists" to a hard-fail "must exist") → a deploy-mid-window bug causes every spawn to fail | low | high (skill-execution-blocking) | The shared bootstrap step text in T-04 acceptance is verbatim "if it exists" — the test `test_preamble_bootstrap_step.py` asserts the literal string; CLAUDE.md edit (T-07 Edit 1) explicitly documents "purely additive" and "a missing preamble.md falls through to today's behavior (no error)" | revert the offending edit per skill |
| R-7 | T-04 line-anchor drift: another stage's intervening SKILL.md edit shifts line numbers between this plan's authoring and /implement time, causing /implement to insert the new bootstrap step at the wrong location (e.g. inside the §0 dispatch block instead of before `## Session bootstrap`) | low | medium | T-04 acceptance specifies STRING anchors as primary (the literal text of the existing step the new step is inserted before) and notes line numbers are advisory; /implement runs `grep -n` on the literal anchor text BEFORE editing each file and updates the plan's line numbers in place if drift is detected | per-skill revert + re-edit using the literal-text anchor |
| R-8 | Cache-read benefit is smaller than projected because the harness applies a separate compression pass on long prompts (the audit doc §Fork already flags this as an open question for soak verification) | low | low | T-06 soak captures the actual `cache_read_input_tokens` field directly from JSONL events (not a derived estimate); if the harness compresses, the JSONL field reports the post-compression count, which IS the billing-relevant number; if cache_read < 5000 mean, the soak fails and the architecture's savings claim is downgraded | downgrade the savings estimate in CLAUDE.md Edit 1 from "~$1.30–2.60/spawn" to "modest cache-warming"; the mechanism still ships because correctness is preserved |

## Procedures

```
# T-01 builder runtime sequence
on python3 quoin/scripts/build_preambles.py:
  resolve REPO_ROOT from script location
  read REPO_ROOT/memory/format-kit.md
  extract slice = lines 189-207 inclusive
  read REPO_ROOT/memory/glossary.md verbatim
  for skill, kind in SPAWN_TARGETS.items():
    if kind == "full":
      body = "[format-kit-§3-slice]\n" + slice + "\n[glossary]\n" + glossary
    else:  # stub
      body = "# Stub preamble — gate has no boilerplate bootstrap reads; this file is kept for uniformity per spawn-bootstrap audit doc.\n"
    frontmatter = compose_frontmatter(skill, kind, sources, hashes, now_utc)
    bytes = frontmatter + "\n" + body
    if len(bytes) > 6144 and kind == "full":
      print "PREAMBLE OVERSIZE: ..."
      exit 3
    write REPO_ROOT/skills/<skill>/preamble.md.tmp
    os.replace(... .tmp, ... preamble.md)  # atomic per skill
  exit 0

# T-04 child bootstrap sequence (each spawn target, fresh session)
# Cross-spawn cache semantics (per D-01): spawn 1 of this skill writes preamble.md
# bytes to cache. Spawn N+1, within the 5-minute prompt-cache TTL with a
# byte-identical task fixture, has a prompt prefix byte-identical to spawn 1's
# through the preamble.md tool_result block — and therefore pays cache_read
# (not cache_creation) for the preamble bytes plus any earlier prefix that
# aligns. Within a single spawn, all the reads below are independent
# tool_result blocks; there is NO within-spawn cache warming between them.
on session start:
  # NEW first step (T-04):
  if file_exists("~/.claude/skills/<skill>/preamble.md"):
    read it  # cache-creation on spawn 1; cache_read on spawns 2..N (cross-spawn only)
  else:
    # soft-fail: proceed without warning
    pass

  # EXISTING steps (unchanged by Stage 2-alt):
  read .workflow_artifacts/memory/lessons-learned.md (if applicable per skill)
  resolve task subfolder via path_resolve.py
  read task-specific files (current-plan.md, critic-response-*.md, architecture.md, cost-ledger.md)
  append cost-ledger row
  read ~/.claude/memory/format-kit.md   # independent tool_result; no within-spawn cache benefit from preamble read above
  read ~/.claude/memory/glossary.md     # independent tool_result; no within-spawn cache benefit from preamble read above
  proceed with skill body (write-site references to format-kit / glossary still fire normally)
```

## References

- ../architecture.md (Stage 2 section, Stage decomposition, Risks, Open questions — Question on harness spawn-prompt-prefix transparency was resolved by hoisting it to a Stage 2 BLOCKING prerequisite in round 1) — defines Stage 2 scope and prerequisites.
- ../../../quoin/docs/spawn-bootstrap-audit-2026-04-28.md (`§Skill audit table`, `§Skill-list aggregate`, `§Discrepancies`, `§Fork`) — single source of truth for 7-target membership, per-skill boilerplate eligibility, ~4000-byte-per-skill preamble estimate, gate ~200-byte stub, and the on-disk-read alternate-transport recommendation. Stage 2-alt's design IS this doc's `§Fork` §candidate-1 path.
- ./v1-prefix-injection/current-plan.md — the v1 plan; v1's harness round-trip verifier task (verify_spawn_prompt_prefix.py) is DONE (committed at e37fe64; HARNESS-UNAVAILABLE verdict). v1's audit-doc task is DONE. v1's builder task, freshness test task, preamble.md content/structure task, install.sh deploy task, soak task, CLAUDE.md docs task, and rollback task are reusable for shape/quality reference; this plan renumbers them as new T-01..T-08 and adapts the child-edit task (mechanism changes from short-circuit clause to additive bootstrap read). The parent-side prefix-injection task from v1 is DELETED ENTIRELY.
- ../../../quoin/scripts/verify_spawn_prompt_prefix.py + tests at ../../../quoin/scripts/tests/test_verify_spawn_prompt_prefix.py — already shipped as v1 T-01; treated as prior art for future similar work; not re-touched by Stage 2-alt.
- ../../../quoin/skills/critic/SKILL.md (lines 11-19 `## Session bootstrap`; line 14 lessons-skip rule) — anchor for T-04.
- ../../../quoin/skills/revise/SKILL.md (lines 11-18 `## Session bootstrap`) — anchor for T-04.
- ../../../quoin/skills/revise-fast/SKILL.md (lines 11-48 §0 dispatch + lines 50-60 `## Session bootstrap`) — anchor for T-04.
- ../../../quoin/skills/plan/SKILL.md (lines 11-19 `## Session bootstrap`) — anchor for T-04.
- ../../../quoin/skills/review/SKILL.md (lines 11-42 `## Session bootstrap`) — anchor for T-04.
- ../../../quoin/skills/architect/SKILL.md (lines 15-23 `## Session bootstrap`) — anchor for T-04.
- ../../../quoin/skills/gate/SKILL.md (lines 50-52 `## Session bootstrap` cost-tracking note) — anchor for T-04 special-case prose insertion.
- ../../../quoin/install.sh (lines 84-100 Step 2 skill copy; lines 135-145 v3-scripts loop; lines 218-223 final summary) — anchor for T-05 four-edit set.
- ../../../quoin/CLAUDE.md (`## Common rules for all skills`; `### Tier 1 — files that always stay English` "Source files" subsection; `### §0 Model dispatch preamble`) — anchor for T-07.
- ../../../quoin/memory/format-kit.md (lines 189-207 §3 slice; verified 1192 bytes) — slice source.
- ../../../quoin/memory/glossary.md (~2819 bytes) — glossary source.
- ../../memory/lessons-learned.md 2026-04-23 — gitignored-parent dirs and `git add -f` rationale for T-03 commit step; lesson 2026-04-23 also pins the `format-kit.md` / `glossary.md` write-site references (cited in the new bootstrap step text).
- ../../memory/lessons-learned.md 2026-04-27 Lesson B — install.sh dual-cleanup pattern; T-05 noted as purely additive (no cleanup loop entry needed).

## Notes

**Acceptance — global checklist (post-T-08, pre-/review):**
- (a) 7 preamble.md files exist under `quoin/skills/<skill>/preamble.md` for each of: critic, revise, revise-fast, plan, review, architect, gate.
- (b) Each full preamble (6 of 7) is < 6144 bytes; gate stub is ~200 bytes.
- (c) `quoin/scripts/build_preambles.py` exists, executable, deterministic per T-01 acceptance bullets.
- (d) `quoin/dev/tests/test_preamble_freshness.py` exists, runs in CI on every PR, has 7 presence parametrizations + 7 freshness parametrizations.
- (e) Each of 7 SKILL.md files has the new `Read ~/.claude/skills/<skill>/preamble.md if it exists` bootstrap step inserted as the FIRST bootstrap step.
- (f) Post-edit grep verification: for each of 7 SKILL.md files, the count of `~/.claude/memory/format-kit.md` references is identical pre-edit and post-edit; same for `~/.claude/memory/glossary.md`; same for `.workflow_artifacts/memory/lessons-learned.md`. NO existing reference was deleted.
- (g) `quoin/install.sh` Step 2a runs build_preambles.py before Step 2 skill copy; Step 2 skill copy includes the conditional preamble.md cp; Step 2b v3-scripts loop includes build_preambles.py in the deploy list; final summary line enumerates build_preambles.py.
- (h) `quoin/CLAUDE.md` `### Subagent preamble (Stage 2 of pipeline-efficiency-improvements)` sub-section exists; Tier 1 carve-out lists `preamble.md` with the GENERATED disambiguation note.
- (i) `pytest quoin/dev/tests/ quoin/scripts/tests/` runs to completion; new Stage 2-alt tests all PASS; pre-existing failures unchanged.
- (j) T-06 soak result documented in `pipeline-efficiency-improvements/stage-2/post-implement-soak-2026-MM-DD.md` (Tier 3); cache-read mean ≥ 5000 AND cache-creation drop ≥ 5000 OR a documented inconclusive verdict.
- (k) T-08 rollback rehearsal documented in session log: deleting one preamble.md and re-running the affected skill's bootstrap proceeds cleanly via the existing format-kit + glossary reads.

**Out of scope (explicit non-goals).**
- Parent-side prefix injection in `quoin/skills/thorough_plan/SKILL.md`, `quoin/skills/architect/SKILL.md`, or `quoin/skills/run/SKILL.md`. Deleted entirely from this stage variant. The `[preamble-inlined]` sentinel does NOT exist in Stage 2-alt; no child SKILL.md tests for it.
- Sentinel detection or short-circuit logic in any child SKILL.md. The v1 plan's "Preamble short-circuit" H3 is NOT used; the new step is a plain numbered bootstrap step inside `## Session bootstrap`.
- Harness byte-transparency testing or any new `verify_spawn_prompt_prefix.py`-like script. v1 T-01 is treated as prior art; Stage 2-alt does not depend on the prefix-injection mechanism.
- `lessons-learned.md` phantom-file cleanup (still flagged in the audit doc `§Discrepancies` as a follow-on candidate; see audit doc for either-or recommendation: deploy via install.sh OR remove the bootstrap-read instruction; both are out of scope here).
- Any deletion or modification of the EXISTING format-kit / glossary references in the 7 child SKILL.md files. T-04 is strictly additive; D-06 codifies this.
- Cost-ledger schema change (the v1 plan's deferred open question about a "preamble inlined Y/N" column). Stays deferred to Stage 4 of the parent architecture.

**Cache write-through (per CLAUDE.md Knowledge cache rule (b)).** /implement of T-04 (child SKILL.md edits), T-05 (install.sh), T-07 (CLAUDE.md edits) modifies source files; cache entries must be regenerated post-implement. Per-skill cache `_index.md` updates:
- `quoin/skills/<skill>/_index.md` (for each of the 7 targets) — note the new first bootstrap step (Read preamble.md additive).
- `quoin/_index.md` — note the new `### Subagent preamble (Stage 2 of pipeline-efficiency-improvements)` sub-section in CLAUDE.md.
- `quoin/scripts/_index.md` — note the new `build_preambles.py` script.
- New per-file cache entries for `quoin/scripts/build_preambles.py` and `quoin/dev/tests/test_preamble_freshness.py` (if cache covers tests).

**Estimated savings (informational; not a gate).** Per the parent architecture's Stage 2 section: ~$1.30–2.60/spawn via cross-spawn prompt-cache warming. Mechanism (per D-01 corrected cache mental model): the §3 slice (1192 bytes) + glossary (2819 bytes) ≈ 4011 bytes are written to cache on spawn 1's preamble.md read; spawns 2..N (within the 5-minute prompt-cache TTL, with byte-identical task fixtures) hit cache for the preamble bytes plus any earlier prefix that aligns. Cache-read pricing is ~10% of cache-write pricing, so the saving on a typical 7-spawn `/thorough_plan` Medium task accrues to spawns 2..7 against spawn 1's cache-creation cost. Within-spawn savings are zero (per CRIT-3 round-1 correction). Architecture's headline figure assumes ~5 sessions/day across the project; actual savings will be measured by T-06 soak (cross-spawn 2..5 mean).

**Process note.** This plan re-plans Stage 2 of pipeline-efficiency-improvements after v1's harness round-trip verifier returned HARNESS-UNAVAILABLE. The previous v1 plan ships under `./v1-prefix-injection/current-plan.md` (preserved for audit); Stage 2-alt's plan IS this file at `<task-root>/stage-2/current-plan.md`. Per CLAUDE.md "## Workflow conventions": v1's plan stays in its working location; Stage 2-alt's plan supersedes it for downstream `/critic`, `/implement`, `/review` reads. /implement of Stage 2-alt does NOT touch any v1 artifact (the v1 verify_spawn_prompt_prefix.py + its test are committed and remain in tree as prior art for any future similar harness-transparency test).

## Revision history

### Round 2 (2026-04-29)

**Critical findings addressed (round 1):**
- CRIT-1 (cross-skill grep regex broken): replaced BRE `'.\*'` form with fixed-string `-F` form in T-04 acceptance: `grep -rnF 'preamble.md\` if it exists; if missing or empty' quoin/skills/` returns exactly 7 hits (verified shape against the new step text).
- CRIT-2 (parity assertion self-contradicting): rewrote the new bootstrap step text to drop the literal strings `~/.claude/memory/format-kit.md` and `~/.claude/memory/glossary.md` (now uses the bare words "format-kit / glossary" without the path). The pre/post grep-count parity assertion is now mechanically valid — the new step contains zero occurrences of the path strings, so adding it does not inflate the count. Parity grep also bumped to fixed-string `-cF` form.
- CRIT-3 (cache mental model wrong): rewrote D-01 with explicit "cache mental model" sub-paragraph clarifying that Anthropic prompt cache hits on byte-identical prompt prefixes (NOT content overlap), so within-spawn "warming" is zero — savings are CROSS-SPAWN only. Updated T-06 acceptance gate to compute mean over spawns 2..5 (excluding spawn 1, which establishes cache). Updated step text to state cross-spawn semantics. Updated `## Notes` Estimated-savings paragraph for consistency.

**Major findings addressed:**
- MAJ-1 (revise-fast anchor lines off by 6): updated to lines 54 (§0 end) / 56 (`## Session bootstrap` H2) / 59 (existing first numbered step).
- MAJ-2 (revise/revise-fast anchor text wrong): replaced fictitious `1a. Resolve task subfolder` with the actual on-disk literal `Read the task subfolder: resolve the artifact path via`.
- MAJ-3 (review off-by-one): updated renumber spec from "1..8 to 2..9" to "1..9 to 2..10" — verified review/SKILL.md has 9 numbered bootstrap steps.
- MAJ-4 (gate edit violates additive-only): removed the prose-to-numbered-list reformatting. New step is now an unnumbered paragraph inserted before the existing prose paragraph; existing `Cost tracking note:` prose stays verbatim. The gate edit is now strictly additive.
- MAJ-5 (5K vs 8K target rationale): added explicit threshold-rationale bullet to T-06 acceptance citing audit `§Discrepancies` (CLAUDE.md is harness-injected, not bootstrap-read; realistic preamble bytes are ~4 KB, so 5K is the empirical floor).

**Minor findings — addressed inline (overlap with CRIT/MAJ fixes):**
- MIN-5 (direct-invocation cost): documented in D-01 ("~4.4 KB more input per single-shot vs. today").
- MIN-6 (step text 640 bytes too long vs savings): trimmed via CRIT-3 rewrite to ~410 bytes (~36% reduction).

**Minor findings — deferred (documentation hygiene; /implement absorbs as inline cleanups OR future MIN-only sweep):**
- MIN-1 (YAML key-order stability in builder), MIN-2 (stub byte estimate ~300 not ~200), MIN-3 (CI repo-root resolution mechanic), MIN-4 (baseline proxy threshold justification), MIN-7 (References parenthetical stale post-fork), MIN-8 (rollback rehearsal mechanics for direct-invocation).

**Round-2 process note:** Round 1 /critic ran as a fresh Opus Agent subagent per /critic SKILL.md "fresh context" rule (verdict REVISE; 3 CRIT, 5 MAJ, 8 MIN). Round-2 /revise-fast was attempted via a Sonnet Agent subagent (agentId ac1862d150dadc2d0) but stream-timed-out at 8m53s with zero writes completed (no `.body.tmp`, no plan changes, no cost-ledger row). Round 2 was finished orchestrator-inline via surgical Edits on the same Opus session that runs /thorough_plan. This deviation from a fresh-/revise-fast subagent is the same pattern documented in the v1 plan's round-2 inline-orchestrator continuation; round-3 critic should scrutinize the surgical edits for missed coverage. All 3 CRIT and 5 MAJ verified addressed by string presence in plan body; validator must PASS post-edit.

### Round 3 (2026-04-29)

**Major findings addressed (round 2):**
- MAJ-1 (round-2; integration class — cache mental model regression): the `## Procedures` pseudocode (T-04 child bootstrap sequence) still had within-spawn cache-hit annotations on the preamble-read line and on the format-kit/glossary read lines. These contradicted the round-2-corrected D-01 narrative (cross-spawn cache semantics; within-spawn savings are zero). Fixed by (a) adding a header comment block above the pseudocode that states the cross-spawn semantics explicitly; (b) replacing the preamble-read annotation with `# cache-creation on spawn 1; cache_read on spawns 2..N (cross-spawn only)`; (c) replacing both format-kit and glossary read annotations with `# independent tool_result; no within-spawn cache benefit from preamble read above`. Verified via grep: `grep -n "cache-hit" current-plan.md` returns zero matches in pseudocode; the only remaining "cache-hit" / "cache_read" prose is in D-01 / T-06 / Notes-Estimated-savings, all of which describe cross-spawn semantics.

**Minor findings — deferred (carried over from round 2):**
- All 5 round-2 MIN findings remain deferred (documentation hygiene — the round-2 critic explicitly classified them as `improvement, use judgment`; not blocking /implement).

**Round-3 process note:** Round 3 was a single mechanical surgical fix applied orchestrator-inline (same path as round 2). Round-2 critic ran as a fresh Opus Agent subagent (agentId a5952e54b85aac779) per the canonical fresh-context rule. Round-3 fix scope: 17 lines of pseudocode comments. No /revise(-fast) subagent was spawned for round 3 because the fix is a string substitution that does not benefit from a fresh agent context; the Round-3 process note is explicitly designed to make this deviation visible to the round-3 critic. Frontmatter bumped `plan_round: 2 → 3`, `updated` to 2026-04-29T14:00:00Z, `tokens` to 14400.

