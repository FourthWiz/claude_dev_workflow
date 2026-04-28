# Changelog

All notable changes to Quoin are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] — 2026-04-27

### Added

The initial Quoin release consolidates six foundation stages built over the quoin-foundation task. Each stage added a concrete, user-visible capability:

- **Stage 1 — §0 Model dispatch preamble:** The 12 cheap-tier skills (gate, implement, rollback, etc.) self-dispatch to their declared model tier (Haiku or Sonnet) when invoked from a more expensive session. Fail-open: if dispatch is unavailable, the skill proceeds at the current tier with a one-line warning rather than aborting. Two stable runtime diagnostic strings are preserved verbatim across all 12 SKILL.md files as stable identifiers. See `.workflow_artifacts/quoin-foundation/finalized/stage-1/`.

- **Stage 2 — ccusage fallback for cost tracking:** `/cost_snapshot` and `/end_of_task` now call `cost_from_jsonl.py` when `npx ccusage` is unavailable. The script reads raw Claude session `.jsonl` files directly, so cost reporting works without the ccusage npm package. See `.workflow_artifacts/quoin-foundation/finalized/stage-2/`.

- **Stage 3 — Stage-subfolder convention + `path_resolve.py`:** Multi-stage tasks store per-stage artifacts under `<task>/stage-N/` subfolders. `path_resolve.py` resolves the correct subfolder from a plain-language invocation (`/implement stage 3 of my-task`). Covers 7 fixture cases including legacy grandfathering. See `.workflow_artifacts/quoin-foundation/finalized/stage-3/`.

- **Stage 4 — Architect Phase 4 critic loop:** `/architect` runs an internal critic loop (up to 2 rounds by default, 4 in strict mode) before returning `architecture.md` as final. The architecture is now a converged artifact, not a first draft. See `.workflow_artifacts/quoin-foundation/finalized/stage-4/`.

- **Stage 5 — Native Haiku summarizer:** The Class B v3 artifact writer uses a native Haiku Agent subagent (Step 2) instead of the deprecated `summarize_for_human.py` Python script. `summary-prompt.md` is a Tier 1 hand-edited prompt template deployed to `~/.claude/memory/`. The obsolete script and its test are removed from both the source tree and `install.sh`. See `.workflow_artifacts/quoin-foundation/finalized/stage-5/`.

- **Stage 6 — Quoin rebrand + QUICKSTART relocation + README:** `dev-workflow/` renamed to `quoin/` (140 internal references updated via mass-sed with v2-historical fixture excluded). `/init_workflow` Step 7 now copies `QUICKSTART.md` from the Quoin source clone to `.workflow_artifacts/QUICKSTART.md` (the new location); the old inline template is removed. `QUICKSTART.md` updated to enumerate all 21 canonical skills. Top-level `README.md` rewritten with Quoin branding and hero/architecture images. This CHANGELOG added. See `.workflow_artifacts/quoin-foundation/stage-6/`.

### Upgrade notes

**GitHub repository rename:**
The GitHub repository has been renamed from `FourthWiz/claude_dev_workflow` to `FourthWiz/quoin`.
GitHub automatically redirects all existing `git clone`, `git pull`, and `git fetch` operations from the old URL — your local clone continues to work without any changes.

Optional cleanup (non-blocking):
```bash
git remote set-url origin git@github.com:FourthWiz/quoin.git
```

Verify with `git ls-remote origin` — returns exit code 0 either way (auto-redirect or updated URL).

**`~/.claude/CLAUDE.md` markers stay unchanged:**
The install.sh markers used to inject workflow rules into `~/.claude/CLAUDE.md` remain:
```
# === DEV WORKFLOW START ===
# === DEV WORKFLOW END ===
```
These markers are intentionally preserved verbatim for backward compatibility with any tooling that scans for them. A seeded-upgrade test (`test_install_seeded_claude_md.py`) verifies that re-running `install.sh` replaces — never appends — the marker section.

**Old QUICKSTART location:**
If you have `(project)/dev-workflow/QUICKSTART.md` from a previous install, `/init_workflow` will detect it and prompt for migration with three options: move, delete, or keep. The new canonical location is `.workflow_artifacts/QUICKSTART.md` (copied from `<your-quoin-clone>/QUICKSTART.md` during `/init_workflow`).

**Manual verification step (post-rename):**
Run `git remote -v` after the rename to confirm your remote URL. Run `git ls-remote origin` to confirm GitHub auto-redirect is active (exit code 0 = working).
