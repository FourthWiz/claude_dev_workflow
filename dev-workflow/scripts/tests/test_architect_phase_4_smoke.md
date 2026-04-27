# Architect Phase 4 Smoke Test — Hand-filled Grep Battery

**Date:** 2026-04-27
**Stage:** quoin-foundation stage-4 (T-09)
**Pattern:** Same as stage-1 verify-subagent-dispatch pilot and stage-3 T-09 grep battery.
**Not deployed to `~/.claude/scripts/`** (per stage-1 round-3 MIN-1 fix — one-shot diagnostic).

## A. Phase 4 heading present in architect/SKILL.md (expect 1)

```
grep -c '^### Phase 4:' dev-workflow/skills/architect/SKILL.md
```
**Result:** 1 ✓

## B. model: opus directive in Phase 4 section (expect ≥1)

```
sed -n '/^### Phase 4:/,/^## Save session state/p' dev-workflow/skills/architect/SKILL.md | grep -c 'model.*opus'
```
**Result:** 2 ✓

## C. Cost-guard verbatim string with em-dash (fixed-string, expect 1)

```
python3 -c "
with open('dev-workflow/skills/architect/SKILL.md') as f: content = f.read()
target = '[critic round 2 starting \u2014 ~\$10-30 estimated based on body size]'
print(content.count(target))
"
```
**Result:** 1 ✓ (em-dash U+2014 confirmed present)

## D. Recursive-self-critique guard: bare form in fixture (expect ≥1)

Fixture: `dev-workflow/scripts/tests/fixtures/architect-phase-4/architecture-fixture.md`

```
grep -cE 'architect/SKILL\.md|critic/SKILL\.md' <fixture>
```
**Result:** 4 ✓ (both bare forms present multiple times)

## E. Recursive-self-critique guard: dev-workflow prefixed form in fixture (expect ≥1)

```
grep -cE 'dev-workflow/skills/(architect|critic)/SKILL\.md' <fixture>
```
**Result:** 2 ✓

## F. Recursive-self-critique guard: tilde-prefixed (deployed-copy) form in fixture (expect ≥1)

```
grep -c '~/.claude/skills' <fixture>
```
**Result:** 2 ✓

## G. max_rounds in Phase 4 section (expect ≥1)

```
sed -n '/^### Phase 4:/,/^## Save session state/p' dev-workflow/skills/architect/SKILL.md | grep -c 'max_rounds'
```
**Result:** 12 ✓

## H. Convergence bullets present: PASS, Max rounds reached, Loop detected (expect 3)

```
sed -n '/^### Phase 4:/,/^## Save session state/p' dev-workflow/skills/architect/SKILL.md | grep -cE 'PASS.*done|Max rounds reached|Loop detected'
```
**Result:** 3 ✓

## I. No cache write-through note (T-08, expect 1)

```
grep -c 'no .workflow_artifacts/cache/ write-through' dev-workflow/skills/architect/SKILL.md
```
**Result:** 1 ✓

## J. T-02b: /architect Phase 4 in critic fresh-context rule (expect ≥1)

```
grep -nE 'architect.*Phase 4' dev-workflow/skills/critic/SKILL.md
```
**Result:** 2 hits (L27 fresh-context rule, L122 target contract) ✓

## K. T-03: architecture-critic-*.md in round detection (expect ≥2 hits)

```
grep -nE 'architecture-critic-\*' dev-workflow/skills/critic/SKILL.md
```
**Result:** 2 hits (L14 and L51) ✓

## L. T-07: Phase 4 critic loop in dev-workflow/CLAUDE.md (expect ≥1)

```
grep -n 'Phase 4 critic loop' dev-workflow/CLAUDE.md
```
**Result:** 2 hits ✓

## Fixture cleanup

Fixture `dev-workflow/scripts/tests/fixtures/architect-phase-4/architecture-fixture.md`
**Status:** Retained for reviewer inspection (per T-09 acceptance — cleanup after smoke completes).
Cleanup: `rm -rf dev-workflow/scripts/tests/fixtures/architect-phase-4/`

## Verdict

All 12 checks PASS. Phase 4 implementation verified by grep battery.
