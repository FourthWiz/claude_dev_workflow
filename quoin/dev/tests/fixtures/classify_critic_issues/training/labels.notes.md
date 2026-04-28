# Labeling Notes — classify_critic_issues training corpus

**Labeler:** automated rubric pass (Sonnet, 2026-04-28)
**Total fixtures labeled:** 17
**Total CRIT+MAJ issues labeled:** 48

## Rubric

Structural issues concern design correctness, architecture, integration safety, or approach: a missing plan, a wrong algorithm, a broken control-flow branch, a missing integration surface, incorrect sequencing, or a de-risking gap that leaves a real production failure mode undetected. Mechanical issues concern format precision, enumeration completeness, regex/grep breadth, missing rows in a table, missing section content, naming conventions, or wording that can be fixed without changing the underlying design. The default when ambiguous is structural, matching the classifier's behavior: mechanical requires a clear keyword or pattern (tag, missing-row, regex breadth, prose/format); everything else is structural. Several issues sit on the boundary — in those cases the dominant concern drives the label: if the issue could ship broken code or leave an undetected failure mode, it is structural even when the surface manifestation is a missing acceptance line.

## Issue shape notes

Stages 1 and 3 use Shape C issue naming (`**Issue C1 — title**`, `**Issue M1 — title**`). The parser assigns IDs `C1`, `C2`, `M1`, etc. These are included in the labels file because they represent Critical and Major severity respectively. Stages 2, 4, and 5 use Shape A naming (`**[CRIT-1]**`, `**[MAJ-1]**`). Stage 5, round 2 has a single Shape D bullet (`**MAJOR — title**`), which receives the ID `MAJ`.

Fixture files with no CRIT-* or MAJ-* issues (stage-1-r3, stage-2-r3, stage-3-r5, stage-4-r3, stage-5-r3) appear in the JSON with empty objects `{}`.

## Ambiguous calls

- `stage-1-critic-response-1.md#M1`: Classified as `mechanical` because the core complaint is that the insertion-anchor table is missing per-file entries — this is a "missing rows in an enumeration" pattern. The consequence (implementer guessing anchors) is real but the fix is purely to add the table entries.

- `stage-1-critic-response-1.md#M4`: Classified as `mechanical` because the issue is about a missing cross-reference sentence in a documentation section — a missing prose/section element. No design change is required.

- `stage-1-critic-response-1.md#M5`: Classified as `structural` despite superficially looking like a test-acceptance wording issue. The substance is that the SYNC-WARNING acceptance criterion is unenforced — a passing-but-hollow check. The dominant concern is that the contract between revise and revise-fast is not mechanically guarded, which is a structural safety gap.

- `stage-1-critic-response-1.md#M6`: Classified as `structural` because the claim that the byte-equality mitigation is robust enough is actually slightly wrong — the issue is about an incorrect assumption in the risk analysis, not about formatting.

- `stage-1-critic-response-1.md#M7`: Classified as `structural` because the issue is about a wrong assertion contract in the test (the ordering check is brittle and the test deduplication strategy is wrong). The surface is test design but the substance is a correctness gap in what the test actually proves.

- `stage-3-critic-response-1.md#C3`: Classified as `mechanical` because the issue is anchor line numbers being off by one, critic/SKILL.md:113 pointing to the wrong line, and a grep regex not matching the prose form. These are precision/enumeration errors — the design is right, the line references and grep pattern are wrong.

- `stage-3-critic-response-1.md#M3`: Classified as `mechanical` because the issue is that the residual-hardcode grep has insufficient scope — an audit-grep that is too narrow. This is squarely in the "audit-grep too narrow / regex breadth" mechanical category.

- `stage-3-critic-response-1.md#M5`: Classified as `mechanical` because the issue is a missing entry in the CLAUDE.md Tier 1 carve-out list — a missing row/section in a documentation file.

- `stage-3-critic-response-2.md#C-A`: Classified as `mechanical` because the root cause is a missing row in the T-05 SKILL-edit enumeration table — the 11th skill file was not listed. This is the canonical "skill list misses an entry" pattern. The consequence is real (rollback would break), but the fix is purely additive: add the row.

- `stage-3-critic-response-2.md#MAJ-A`: Classified as `mechanical` because the issue is that promised verbatim rewrite text is absent — a missing prose/content section. The implementer is left to invent the text. The design decision about what the prose should say already exists; only the written-out text is missing.

- `stage-3-critic-response-3.md#MAJ-1`: Classified as `mechanical` because it is the same class as stage-3-r2#C-A — another missing row in the SKILL-edit enumeration table (end_of_task not listed). Third occurrence of "skill list misses an entry."

- `stage-4-critic-response-1.md#CRIT-2`: Classified as `mechanical` because the issue is that a recursive-self-critique grep uses too narrow an alternation — it will miss legitimate form variants. This is "audit-grep too narrow / broaden the pattern."

- `stage-4-critic-response-1.md#MAJ-2`: Classified as `mechanical` because the issue is a missing acceptance grep for the model:opus directive — an acceptance check that was not written. Missing row/check in the acceptance criteria.

- `stage-4-critic-response-1.md#MAJ-4`: Classified as `mechanical` because the issue is that the diff-check acceptance does not verify the allowed_sections keys — an acceptance criterion that is too narrow in what it checks. This is a missing verification step (format/section checking), not a design gap.

- `stage-4-critic-response-2.md#MAJ-1`: Classified as `mechanical` because the acceptance grep ">=3 hits" does not actually test what its prose claims (loop detection only in strict-mode). The issue is that the grep alternation is wrong — it does not match the token "loop detection" and the cardinality threshold is too loose. This is an audit-grep-too-narrow / wrong-grep-pattern mechanical issue.

- `stage-5-critic-response-1.md#CRIT-1`: Classified as `mechanical` because the T08 acceptance grep will match substring references in negative-instruction prose — a grep collision/breadth issue. The grep is too broad and picks up legitimate non-matching strings. Fix is to either narrow the grep or scrub the file. Core issue is grep pattern incorrectly matching.

## Shape D / multi-bullet disambiguations

stage-5-critic-response-2.md has a single Shape D bullet (`**MAJOR — byte-equality cross-check phase contradicts the canonical Step 2 procedure block's documented variable substitution**`). There is only one MAJOR bullet in this file, so no collision occurs. It is assigned key `MAJ`.

No multi-bullet Shape D collisions requiring a/b suffix were found in this corpus.
