# Terse-Artifact Writing Rubric

Purpose: This file is referenced by writer skills via path. Do not paraphrase or compress it. See architecture §3.2 Tier 1 — this file stays English forever (compressing the rubric recreates the v1 CRIT-2 circular dependency).

````markdown
### Terse-artifact writing rubric (reference from a skill; never write prose about this file)

When a skill's SKILL.md tells you to write an artifact in "terse style per quoin/memory/terse-rubric.md":

- Drop articles ("the", "a", "an") and filler verbs when meaning is unambiguous.
- Keep technical content **verbatim**: file paths, identifier names, code fences, shell
  commands, URLs, version numbers, error strings, quoted symbols, mermaid diagrams,
  JSON/YAML blocks.
- Keep **section headings and issue titles** in natural English — subsequent skills
  grep for them ("CRITICAL:", "MAJOR:", "PASS", "REVISE", "APPROVED", "BLOCKED").
- Prefer bullet lists over paragraphs.
- Keep one sentence per bullet; do not cram multiple facts into a single bullet.
- Never drop a negation, quantifier, or conditional ("not", "only", "at most N", "if X then Y").
- Never drop a file path, line number, or symbol reference.
- Never use abbreviations the reader might not expand correctly ("w/", "b/c", "cfg" are OK;
  "UT" for "unit test" is not).
````
