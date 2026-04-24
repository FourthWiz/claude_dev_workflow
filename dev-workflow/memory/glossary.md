# Glossary — v3 Workflow Abbreviation Whitelist

This file is the abbreviation whitelist for all dev-workflow skills. It extends `terse-rubric.md`'s "never use abbreviations the reader might not expand correctly" rule: entries here are the *approved* abbreviations; the rubric's rule prevents skills from inventing new ones inline.

**Architecture reference:** artifact-format-architecture v3 §5.2.
**Deployed copy:** `~/.claude/memory/glossary.md` — overwritten on re-install.
**Source:** `dev-workflow/memory/glossary.md` (hand-edited Tier 1; do not apply terse-style compression).

---

## Terms

- term: ack
  expand: acceptance criteria
  rule: use compressed form inside Tasks section bullets; full form on first mention in prose sections

- term: gate
  expand: /gate checkpoint
  rule: full form ("gate checkpoint") when first appearing in a section; compressed ("gate") thereafter

- term: PASS / REVISE / APPROVED / BLOCKED
  rule: VERBATIM — never compressed (downstream skills grep for these exact strings to extract verdicts; any substitution breaks grep-based state tracking)

- term: cfg, w/, b/c
  rule: OK per terse-rubric.md — common enough to be unambiguous; no glossary entry required beyond this acknowledgment

- term: ✓
  expand: done / completed
  rule: VERBATIM — status glyph for completed sequenced items per format-kit §1; downstream skills grep for it to extract task state; do not substitute ☑ or similar

- term: ✗
  expand: failed
  rule: VERBATIM — status glyph for failed items; downstream skills grep for it; do not substitute ✘ or similar

- term: ⏳
  expand: pending / in-progress
  rule: VERBATIM — status glyph for not-yet-started or in-flight items; downstream skills grep for it; do not substitute 🔄 or similar

- term: 🚫
  expand: blocked
  rule: VERBATIM — status glyph for blocked items (waiting on external dependency or explicit blocker); downstream skills grep for it; do not substitute ⛔ or similar

---

The four status glyphs (✓ ✗ ⏳ 🚫) are load-bearing for Class A and Class B "sequenced items with status" sections (per format-kit §1). Glossary entries ensure writers don't invent variant glyph semantics inline. Downstream skills (`/critic`, `/implement`, `/review`) may grep these glyphs to extract task state — VERBATIM-keep is required across all artifacts that use sequenced-item sections.
