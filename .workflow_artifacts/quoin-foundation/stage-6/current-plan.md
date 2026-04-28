---
task: quoin-foundation
stage: 6
phase: plan
round: 2
date: 2026-04-27
model: claude-opus-4-7
class: B
---
## For human

Round 2 of stage 6 addresses all 12 critic issues from round 1 via surgical fixes to acceptance tests, sed procedures, fixture cleanup, and runtime string enumeration. The plan remains Large profile (strict mode) with all-Opus critic loop. Biggest risk: the doubled-phrase bug on CLAUDE.md line 393 is fixed by replacing broad sed with targeted Edits, but manual verification of the fix is required before proceeding. To progress, critic round 2 must verify all 12 fixes pass CRIT/MAJ/MIN criteria. Next step: run critic round 2; if PASS, the plan advances to gate then implement.

## State

```yaml
task: quoin-foundation
stage: 6 (Quoin rebrand + QUICKSTART relocation + fancy README)
profile: Large (strict — all-Opus, max 5 rounds)
session_uuid: 502995d0-feb9-4e5f-a2dd-095abc84570a
phase: plan (round 2 — post-critic-1)
prerequisites: stages 1 through 5 merged to main (verified)
parent_artifact: .workflow_artifacts/quoin-foundation/architecture.md (stage 6 of the parent architecture)
scope_count: 31 files / 140 `dev-workflow` occurrences (drift from arch's 26/103)
deliverables:
  - rename dev-workflow/ -> quoin/ (single git mv, ~31 internal refs swept)
  - rewrite top-level README.md (Quoin branding + hero image + diagrams)
  - new top-level CHANGELOG.md (v1.0 release notes)
  - move pictures_for_git/ -> quoin/docs/images/
  - /init_workflow Step 7 writes QUICKSTART to (project)/.workflow_artifacts/QUICKSTART.md
  - /init_workflow legacy detection for old (project)/dev-workflow/QUICKSTART.md
  - refresh quoin/QUICKSTART.md (source of truth) to enumerate the 21 canonical skills
  - 4 acceptance tests (residual-grep, seeded-CLAUDE.md upgrade, init_workflow legacy prompt, fresh-clone install)
exclusions:
  - install.sh `$SCRIPT_DIR`-relative logic (path-invariant; survives rename)
  - `~/.claude/CLAUDE.md` markers (`# === DEV WORKFLOW START ===` stays VERBATIM per the architecture's install.sh-marker-shift risk)
  - `.workflow_artifacts/` path conventions (no change)
  - diagnostic warning string `[quoin-stage-1: subagent dispatch unavailable; ...]` (stable identifier; 12 SKILL.md files retain verbatim)
  - hard-cap runtime string `Quoin self-dispatch hard-cap reached at N=` (stable identifier; 12 SKILL.md files retain verbatim — asserted by `test_quoin_stage1_recursion_abort.py:108`)
  - test/fixture filenames containing "quoin-stage-1" (stable historical IDs)
  - frozen v2 historical fixtures at `quoin/scripts/tests/fixtures/v2-historical/*.md` (consumed by `measure_v3_savings.py`; rewriting their `dev-workflow` content shifts the v2→v3 byte-size delta — see TR-09)
```

## Tasks

1. ✓ T-01: Pre-flight & branch hygiene — DONE (commit 0a20b3d records cost ledger; branch `feat/quoin-stage-6` created from main)
   - **Scope:** Verify stages 1 through 5 merged to main; verify clean working tree; create branch `feat/quoin-stage-6`; verify `pictures_for_git/` is unstaged + untracked at toplevel; record session UUID in cost ledger if not done.
   - **Acceptance:**
     - `git log --oneline main | grep -E "stage-[1-5]"` shows all five end_of_task commits.
     - `git status --short` returns only the cost-ledger row already in flight (no other uncommitted changes outside `.workflow_artifacts/`).
     - `git branch --show-current` outputs `feat/quoin-stage-6`.
     - `ls pictures_for_git/*.png | wc -l` returns ≥1.
   - **Files:** none modified.
   - **Commit:** none (pre-flight only).

2. ✓ T-02: Rename `dev-workflow/` → `quoin/` + mass string substitution + install.sh banner update + CLAUDE.md self-ref update — DONE (commit 4eb52c2; 134 files renamed; mass-sub clean except v2-historical fixture preserved at 28 refs; both stable runtime strings preserved across 12 SKILL.md files; 5 surgical CLAUDE.md edits applied. Deviation note: `# === DEV WORKFLOW START ===` appears 2× in install.sh (bash variable + Python heredoc) — both correct; plan acceptance expected exactly 1 but grep counts both legitimate occurrences)
   - **Scope:** Single coherent commit so the diff is internally consistent (rename + every internal reference updated together).
     - `git mv dev-workflow quoin` (preserves history per file).
     - Mass `sed -i '' 's|dev-workflow|quoin|g'` over the 31 files identified, EXCLUDING the frozen v2-historical fixture path. See Procedures §proc-T02 for the exact `find` invocation that prunes the fixture path. Lesson 2026-04-22 (frozen historical baselines) applies — the v2-historical fixture content is a captured byte-size baseline for `measure_v3_savings.py`; rewriting `dev-workflow` → `quoin` inside the captured content shaves 7 bytes per occurrence and silently shifts the v2→v3 delta computed by the determinism test. See TR-09.
     - Update `quoin/scripts/measure_v3_savings.py`'s `FIXTURE_PAIRS` constants (lines 60–89) so v2 fixture paths read `quoin/scripts/tests/fixtures/v2-historical/...` (those ARE source-tree path strings the script uses to locate fixtures — not frozen content). Same for the v3 fixture path on line 89 and the prose pointers on lines 15, 148, 153, 231. The fixture FILE CONTENT stays untouched.
     - In `quoin/install.sh`: update banner text "Dev Workflow Installer" → "Quoin Installer" (lines 5, 35), banner box width if needed, log strings "Updated dev-workflow section" → "Updated quoin section" (lines 179, 188), the "tip" line on 203, the section comment on line 92 ("Step 2b: Copying terse-rubric and v3 reference files..."). The MARKER variables on lines 162–163 (`MARKER_START`/`MARKER_END` containing `# === DEV WORKFLOW START ===`/`# === DEV WORKFLOW END ===`) MUST stay VERBATIM — these are uppercase with spaces, so the lowercase-hyphen mass-sub naturally skips them.
     - In `quoin/CLAUDE.md` — surgical Edit-tool calls (NOT broad sed) for prose, to avoid the doubled "§0" phrase the round-1 plan would have produced. See Procedures §proc-T02 step 4 for the exact Edit-tool calls. The four touched lines + surgical phrasing:
       - **Subsection heading (line ~373):** `### §0 Model dispatch preamble (Quoin foundation Stage 1)` → `### §0 Model dispatch preamble`.
       - **Tier 1 entry, line 393:** `quoin-stage-1-preamble.md` (Quoin Stage 1 §0 preamble template; ...)` → `quoin-stage-1-preamble.md` (§0 preamble template; ...)`. (Drops "Quoin Stage 1 " prefix only — keeps the "§0 preamble template" phrasing intact, no doubling.)
       - **Tier 1 entry, line 394:** `verify_subagent_dispatch.md` (Quoin Stage 1 subagent-dispatch verification template; ...)` → `verify_subagent_dispatch.md` (§0 subagent-dispatch verification template; ...)`.
       - **Prose, line 434:** Remove the entire trailing parenthetical `(Note for the future Quoin-rebrand stage: this subsection's "Quoin foundation Stage 1" reference becomes stale post-rebrand — update the wording to a stage-tracker-stable reference at that time.)` — and rewrite the leading prose `Mechanical drift detection lives in ... and is captured in ... .` to drop "Quoin foundation Stage 1" / "of the stage-1 plan" wording. New text per §proc-T02.
       - **Prose, summary-prompt entries on lines (after sed) referencing "per Quoin Stage 5 architecture":** rewrite via Edit tool to "per stage 5 of the Quoin foundation work".
     - The Tier 1 list entries for `quoin/scripts/tests/fixtures/quoin-stage-1-preamble.md`, `quoin/scripts/verify_subagent_dispatch.md`, and `quoin/scripts/tests/fixtures/path_resolve/**` keep the fixture filenames intact; only the descriptive prose changes (drop "Quoin Stage 1" / "Stage 3" wording where it's a planning-task reference; preserve where it's a structural identifier).
   - **Acceptance:**
     - `[ -d quoin ] && [ ! -d dev-workflow ]` (rename succeeded).
     - `grep -rn 'dev-workflow' quoin/ 2>/dev/null` excluding `quoin/scripts/tests/fixtures/v2-historical/` returns `0` matches. Implementation: `grep -rn --exclude-dir=v2-historical 'dev-workflow' quoin/` returns 0.
     - `grep -rn 'dev-workflow' quoin/scripts/tests/fixtures/v2-historical/` returns ≥10 (frozen content preserved — sentinel that the prune worked).
     - `grep -n '# === DEV WORKFLOW START ===' quoin/install.sh` returns one match (marker preserved verbatim).
     - `grep -n '# === DEV WORKFLOW END ===' quoin/install.sh` returns one match.
     - `grep -c 'Quoin foundation Stage' quoin/CLAUDE.md quoin/skills/*/SKILL.md 2>/dev/null | awk -F: 'NR>0 {sum+=$NF} END {print sum}'` returns `0` (planning-task prose drift wording eliminated).
     - `grep -c 'future Quoin-rebrand stage' quoin/CLAUDE.md` returns `0` (in-flight parenthetical removed).
     - `grep -n '\[quoin-stage-1: subagent dispatch unavailable' quoin/skills/*/SKILL.md | wc -l` returns `12` (diagnostic strings preserved verbatim across the 12 cheap-tier skills).
     - `grep -l 'Quoin self-dispatch hard-cap reached at N=' quoin/skills/*/SKILL.md | wc -l` returns `12` (the second stable runtime string preserved verbatim — asserted by `test_quoin_stage1_recursion_abort.py:108`).
     - **CRIT-1 fix — hand-listed acceptance:** all four stable test/fixture filename references are present in `quoin/CLAUDE.md`. Implementation: `python3 -c "txt=open('quoin/CLAUDE.md').read(); names=['quoin-stage-1-preamble.md','test_quoin_stage1_preamble.py','test_quoin_stage1_recursion_abort.py','verify_subagent_dispatch.md']; missing=[n for n in names if n not in txt]; assert not missing, f'missing: {missing}'"`. (Note: the round-1 grep `>=4` was empirically wrong — actual count is 3 because three of the names co-occur on a single CLAUDE.md line. Hand-listing makes the assertion explicit and order-independent.)
     - **MAJ-1 fix — surgical phrasing acceptance:** verify the four CLAUDE.md prose lines were edited to the desired exact form. `grep -c '### §0 Model dispatch preamble$' quoin/CLAUDE.md` returns ≥1; `grep -c '§0 preamble template' quoin/CLAUDE.md` returns ≥1 (and NOT `§0 model-dispatch preamble §0 preamble template` — the doubled form sed would have produced); `grep -c '§0 model-dispatch preamble §0' quoin/CLAUDE.md` returns `0`.
     - `git log --follow --oneline -- quoin/CLAUDE.md | head -3` shows pre-rename history (verifies `git mv` carried history).
   - **Files modified:** all 31 source-tree files identified (mass sed); `quoin/install.sh` (banner+log additionally edited); `quoin/CLAUDE.md` (surgical Edit-tool calls); `quoin/scripts/measure_v3_savings.py` (fixture path strings only); `quoin/scripts/tests/fixtures/v2-historical/*.md` are EXPLICITLY UNTOUCHED.
   - **Commit:** `refactor(quoin-stage-6): rename dev-workflow/ -> quoin/ + sweep internal refs`. Body must explicitly note: (a) markers stay verbatim per the architecture's install.sh-marker-shift risk, (b) BOTH stable runtime strings preserved across the 12 cheap-tier SKILL.md files: `[quoin-stage-1: subagent dispatch unavailable; ...]` AND `Quoin self-dispatch hard-cap reached at N=` (asserted by `test_quoin_stage1_recursion_abort.py:108`), (c) test/fixture filenames retained as stable identifiers, (d) prose-only references to "Quoin foundation Stage 1" updated via surgical Edit-tool calls (NOT broad sed) to avoid doubled-phrase artifacts (lesson 2026-04-22), (e) v2-historical fixture content explicitly preserved as a frozen baseline for `measure_v3_savings.py` (lesson 2026-04-22 frozen-baseline territory) (lesson 2026-04-26 — document deliberate deviations in commit body).

3. ✓ T-03: Move pictures into the renamed source repo — DONE (commit aec97e9). Deviation: `git mv` not available because pictures were untracked; used `cp` + `git add` + `git rm` for removed sources. Pictures placed at `quoin/docs/images/quoin-hero.png` (logo) and `quoin/docs/images/quoin-architecture.png` (workflow diagram). `pictures_for_git/` directory remains as untracked at repo root because `rm -rf` was denied by the permission system; this is a manual user cleanup step (untracked files are not committed)
   - **Scope:** `mkdir -p quoin/docs/images && git mv pictures_for_git/*.png quoin/docs/images/ && rmdir pictures_for_git`. Pictures get rename-friendly names: rename the two existing files in the same commit (`git mv quoin/docs/images/'ChatGPT Image Apr 27, 2026, 08_07_01 AM.png' quoin/docs/images/quoin-hero.png` and the second to `quoin-architecture.png` — exact mapping decided by which image fits which README slot; if uncertain, rename to `quoin-image-1.png` / `quoin-image-2.png` and let T-05 README content drive the slot assignments).
   - **Acceptance:**
     - `[ -d quoin/docs/images ] && [ ! -d pictures_for_git ]` (move done).
     - `ls quoin/docs/images/*.png | wc -l` returns `≥2`.
     - `git log --follow --oneline -- 'quoin/docs/images/*.png' | head -3` shows pre-rename history (rename preserved history).
     - File names contain no spaces or commas (URL-safe in markdown).
   - **Files modified:** 2 PNG files (renamed + relocated); `pictures_for_git/` directory removed.
   - **Commit:** `chore(quoin-stage-6): move pictures into quoin/docs/images/ for README`.

4. ✓ T-04: `/init_workflow` Step 5 tree + Step 7 logic + legacy detection — single coherent skill update + Workflow-User-Guide reference fix — DONE (commit 74aba16; SKILL.md tree updated with .workflow_artifacts/QUICKSTART.md entry, source-clone sibling note added; Step 7 now has cp-from-source pattern with [m]/[d]/[k] legacy prompt and source-clone collision guard; Step 8 report updated; QUICKSTART.md grew from 17 → 21 skills with /plan, /critic, /revise, /revise-fast added; Workflow-User-Guide refs qualified)
   - **Scope:** Edit `quoin/skills/init_workflow/SKILL.md`:
     - Step 5 tree (lines ~158–175): remove the `dev-workflow/` subtree from the project structure diagram (it was an artifact of the old QUICKSTART location). Replace with a `.workflow_artifacts/QUICKSTART.md` entry under `.workflow_artifacts/`. Note in tree that the cloned source repo (now `quoin/`) is a sibling clone, not a project subdirectory. Also update the existing tree entry "Workflow-User-Guide.html" (~line 173) to clarify it lives in the source clone (`<your-quoin-clone>/Workflow-User-Guide.html`), not in the project root.
     - Step 7 (lines ~252–311): Replace the entire inline QUICKSTART template with a single Bash step: `cp <quoin-source-dir>/QUICKSTART.md .workflow_artifacts/QUICKSTART.md`. The skill must locate `<quoin-source-dir>` heuristically: (a) check if `$HOME/.claude/skills/init_workflow/SKILL.md` exists and infer source via `realpath` of any sibling repo clone OR (b) ask the user where the source clone is OR (c) fall back to embedding the QUICKSTART body inline in the skill (last resort — current behavior). Decision per Decisions §D-02: **(b) ask the user, with `(a)` as auto-suggestion**.
     - Step 7 also updates the legacy detection block: previously detected `(project)/dev-workflow/memory/` (Step 5 lines ~77–93). Add a new sub-block after the existing memory legacy detection: detect `(project)/dev-workflow/QUICKSTART.md` and present this prompt:
       ```
       Legacy QUICKSTART location detected: (project)/dev-workflow/QUICKSTART.md
            The new location is .workflow_artifacts/QUICKSTART.md.
            Options:
              [m] Move dev-workflow/QUICKSTART.md → .workflow_artifacts/QUICKSTART.md
              [d] Delete the legacy file (a fresh QUICKSTART will be generated below)
              [k] Keep it (you may have cloned the workflow source there — check first)
       ```
       The detection MUST be safe: do NOT auto-delete; if `(project)/dev-workflow/install.sh` or `(project)/dev-workflow/SETUP.md` is also present, the dir is the cloned source repo (rare layout) — print a warning and default to `[k]`.
     - Step 7 prose lines (~254, ~306, ~310, ~333) currently reference unqualified `Workflow-User-Guide.html`. Edit each to use the qualified source-relative pointer `<your-quoin-clone>/Workflow-User-Guide.html` so a user reading the skill output understands the file lives in the source clone, not in their project. Per MAJ-4 fix.
     - Step 8 report (line ~322): replace `Workflow-User-Guide.html (interactive guide)` with `<your-quoin-clone>/Workflow-User-Guide.html (interactive guide — in your cloned source)`. Replace `Workflow initialized in (project-root)/dev-workflow/` with `Workflow initialized in (project-root)/.workflow_artifacts/`. Per MAJ-4 fix.
   - **T-04b (folded into T-04):** Refresh `quoin/QUICKSTART.md` (source of truth, copied by Step 7) to enumerate the canonical 21 skills, one row per skill in a table identical-in-structure to the current QUICKSTART table but with all 21 commands (current source has 17). Use the canonical 21-skill list from `ls quoin/skills/`: architect, capture_insight, cost_snapshot, critic, discover, end_of_day, end_of_task, expand, gate, implement, init_workflow, plan, review, revise, revise-fast, rollback, run, start_of_day, thorough_plan, triage, weekly_review. Also: edit `quoin/QUICKSTART.md` lines 78 and 82 to use the qualified `<your-quoin-clone>/Workflow-User-Guide.html` pointer (eliminates dangling reference once the file is `cp`'d to `.workflow_artifacts/QUICKSTART.md` per Step 7). Per MAJ-4 + MIN-6 fix.
   - **Acceptance:**
     - `grep -n 'dev-workflow' quoin/skills/init_workflow/SKILL.md` returns matches ONLY in the legacy-detection block (where the legacy path is intentionally referenced) — verify by counting: `grep -c '^.*dev-workflow.*$' quoin/skills/init_workflow/SKILL.md` should equal the count of legacy-detection mentions (target: 4–8 matches in the legacy block).
     - `grep -n '.workflow_artifacts/QUICKSTART.md' quoin/skills/init_workflow/SKILL.md` returns ≥3 matches (Step 5 tree, Step 7 cp command, Step 7 prompt).
     - `grep -nE '\[m\]|\[d\]|\[k\]' quoin/skills/init_workflow/SKILL.md` returns ≥3 (the new legacy prompt's three options are textually present).
     - `grep -n 'cp.*QUICKSTART.md.*\.workflow_artifacts' quoin/skills/init_workflow/SKILL.md` returns ≥1 (the relocation cp command is encoded).
     - **MAJ-4 fix — no unqualified Workflow-User-Guide refs:** `grep -nE 'Workflow-User-Guide\.html' quoin/QUICKSTART.md | grep -v '<your-quoin-clone>/'` returns 0 lines (every reference is qualified). Same against `quoin/skills/init_workflow/SKILL.md` (Step 7 + Step 8 prose only — tree-diagram entries may show the bare filename in ASCII art; carve them out via `grep -v -E '│|├|└|---'` if needed, OR rewrite tree-diagram entries to also include the qualifier).
     - **MIN-6 fix — refreshed QUICKSTART has all 21 skills:** `python3 -c "import re; t=open('quoin/QUICKSTART.md').read(); needed=['architect','capture_insight','cost_snapshot','critic','discover','end_of_day','end_of_task','expand','gate','implement','init_workflow','plan','review','revise','revise-fast','rollback','run','start_of_day','thorough_plan','triage','weekly_review']; missing=[s for s in needed if f'/{s}' not in t]; assert not missing, f'missing in QUICKSTART: {missing}'"` succeeds.
   - **Files modified:** `quoin/skills/init_workflow/SKILL.md` (Step 5/7/8 update); `quoin/QUICKSTART.md` (refresh to 21 skills + qualify Workflow-User-Guide refs).
   - **Commit:** `feat(quoin-stage-6): /init_workflow Step 7 writes QUICKSTART to .workflow_artifacts/ + legacy-detection prompt + qualify Workflow-User-Guide refs + refresh QUICKSTART skill list`. Body cites the in-flight projects' migration story explicitly + the Workflow-User-Guide dangling-reference fix.

5. ✓ T-05: Rewrite top-level `README.md` with Quoin branding + hero image — DONE (commit 07aa600; 137 lines, 11 Quoin mentions, 0 "Claude Dev Workflow" refs, 0 dev-workflow refs, 2 image embeds, all 21 canonical skills present)
   - **Scope:** Rewrite `<repo-root>/README.md` (currently 13KB, 480 lines, "Claude Dev Workflow"-branded). Target structure:
     - Top: hero image (`![Quoin](quoin/docs/images/quoin-hero.png)`) + tagline.
     - Section 1: What is Quoin? (3-line elevator pitch).
     - Section 2: Why Quoin? (concrete value props — cost discipline, planning rigor, audit trail; cite the architecture's 6 stages briefly).
     - Section 3: Install (block-quote `git clone https://github.com/FourthWiz/quoin && cd quoin && bash quoin/install.sh`; note GitHub auto-redirect from `claude_dev_workflow`).
     - Section 4: 30-Second Start (the `/init_workflow` → `/architect` → `/thorough_plan` → `/implement` → `/review` → `/end_of_task` flow).
     - Section 5: Skills (the 21-skill table from current README, headed by phase). The 21 canonical skills are: architect, capture_insight, cost_snapshot, critic, discover, end_of_day, end_of_task, expand, gate, implement, init_workflow, plan, review, revise, revise-fast, rollback, run, start_of_day, thorough_plan, triage, weekly_review.
     - Section 6: Architecture diagram (`![Architecture](quoin/docs/images/quoin-architecture.png)`) + brief caption pointing to `quoin/CLAUDE.md` for full rules.
     - Section 7: Cost & Model Discipline (mention §0 dispatch preamble, ccusage fallback, Tier 1/2/3 v3 format).
     - Section 8: Examples / Typical Flows (Small/Medium/Large profile snippets).
     - Section 9: Documentation pointers (`quoin/QUICKSTART.md`, `<your-quoin-clone>/Workflow-User-Guide.html` qualified pointer, `quoin/CLAUDE.md`).
     - Section 10: Contributing + License (light — match existing tone).
   - **Acceptance:**
     - `grep -c 'Quoin' README.md` returns ≥10.
     - `grep -c 'Claude Dev Workflow' README.md` returns `0`.
     - `grep -c 'dev-workflow' README.md` returns `0` (case-sensitive).
     - `grep -nE '!\[.*\]\(quoin/docs/images/.*\.png\)' README.md` returns ≥2 (both pictures referenced).
     - `wc -l README.md` reports ≤600 lines (target: 350–500 — fancy but not bloated).
     - **CRIT-2 fix — hand-listed skill assertion:** all 21 canonical skills appear in the README. Implementation: `python3 -c "t=open('README.md').read(); skills=['architect','capture_insight','cost_snapshot','critic','discover','end_of_day','end_of_task','expand','gate','implement','init_workflow','plan','review','revise','revise-fast','rollback','run','start_of_day','thorough_plan','triage','weekly_review']; missing=[s for s in skills if f'/{s}' not in t]; assert not missing, f'missing skills in README: {missing}'"`. (Note: the round-1 grep `^\| `/[a-z_]+`` excluded hyphen and so missed `/revise-fast`. Also: today's README has 20 rows, missing `/expand` — the rewrite must add it. Hand-listing makes both gaps mechanically detected.)
   - **Files modified:** `README.md` (full rewrite).
   - **Commit:** `docs(quoin-stage-6): rewrite top-level README with Quoin branding + hero/architecture images`.

6. ✓ T-06: Create top-level `CHANGELOG.md` (v1.0 release notes) — DONE (commit 8cb1064; Keep-a-Changelog format; all 6 stages cited; auto-redirect documented twice; DEV WORKFLOW marker preservation documented; manual `git remote -v` verification step in upgrade notes)
   - **Scope:** New file `<repo-root>/CHANGELOG.md`. Format: Keep-a-Changelog convention. v1.0 entry summarizes the 6-stage Quoin foundation: stage 1 (§0 model dispatch preamble), stage 2 (ccusage fallback), stage 3 (stage-subfolder convention + path_resolve.py), stage 4 (architect Phase 4 critic), stage 5 (native Haiku summarizer), stage 6 (rebrand + QUICKSTART relocation + this README). Each stage line: 1–2 sentences with the user-visible benefit + a `quoin-foundation/finalized/stage-N/` reference.
     - Below v1.0: an "Upgrade notes" subsection covering: (a) GitHub auto-redirect from `FourthWiz/claude_dev_workflow` to `FourthWiz/quoin`; (b) `~/.claude/CLAUDE.md` marker stays `# === DEV WORKFLOW START ===` for backward compatibility (the architecture's install.sh-marker-shift risk); (c) old `(project)/dev-workflow/QUICKSTART.md` location is detected by `/init_workflow` and prompted for migration (T-04).
   - **Acceptance:**
     - `[ -f CHANGELOG.md ]` (file exists).
     - `grep -c '## \[1.0.0\]' CHANGELOG.md` returns `1`.
     - `grep -nE 'stage[ -]?[1-6]|S0[1-6]|stage [1-6]' CHANGELOG.md | wc -l` returns ≥6 (all six stages cited).
     - `grep -n 'auto-redirect\|GitHub.*redirect' CHANGELOG.md` returns ≥1 (the architecture's user-install-breakage risk mitigation documented).
     - `grep -n '# === DEV WORKFLOW START ===' CHANGELOG.md` returns ≥1 (marker preservation explicitly documented for users).
   - **Files modified:** `CHANGELOG.md` (new).
   - **Commit:** `docs(quoin-stage-6): add CHANGELOG.md for v1.0 Quoin release`.

7. ✓ T-07: Residual-grep test (`tests/test_quoin_rebrand_no_residuals.py`) — DONE (commit bb2ce23; 3 cases all PASS). Deviation: T-07 case 1 (`test_no_lowercase_dev_workflow_in_quoin_dir`) was refined to use an allowlist of 3 files that legitimately contain `dev-workflow` (the legacy-detection block in init_workflow/SKILL.md, plus the two test files that document the rebrand). The plan's strict "0 matches" criterion was unachievable because the legacy-detection logic itself MUST reference the old path string
   - **Scope:** New pytest at `quoin/scripts/tests/test_quoin_rebrand_no_residuals.py`. Three test cases:
     - `test_no_lowercase_dev_workflow_in_quoin_dir`: `subprocess.run(["grep", "-rn", "--exclude-dir=v2-historical", "dev-workflow", "quoin/"])` — assert returncode is 1 (grep "no matches") AND stdout is empty. The v2-historical fixture is excluded because its content is a frozen byte-size baseline for `measure_v3_savings.py` (TR-09).
     - `test_no_quoin_foundation_stage_prose_in_skills`: `grep -rn 'Quoin foundation Stage' quoin/skills/ quoin/CLAUDE.md` — assert empty (the prose drift wording is gone). Diagnostic strings (`[quoin-stage-1: ...]`) and filenames (`test_quoin_stage1_preamble.py`) are NOT matched by this pattern (different wording).
     - `test_changelog_documents_marker_preservation`: open `CHANGELOG.md`, assert it contains the literal string `# === DEV WORKFLOW START ===` (the architecture's install.sh-marker-shift risk mitigation visible to users).
   - **Acceptance:** `python3 -m pytest quoin/scripts/tests/test_quoin_rebrand_no_residuals.py -v` reports all 3 PASS.
   - **Files modified:** new test file.
   - **Commit:** included in T-10 test commit (see commit boundaries).

8. ✓ T-08: Seeded-CLAUDE.md upgrade test (`tests/test_install_seeded_claude_md.py`) — DONE (commit bb2ce23; 2 cases PASS, both cleanup loops actively exercised via 4 pre-seeded stubs)
   - **Scope:** New pytest at `quoin/scripts/tests/test_install_seeded_claude_md.py`. **Critical the architecture's install.sh-marker-shift risk mitigation test.** Test cases:
     - `test_seeded_claude_md_section_replaced_not_appended`:
       1. `tmp_home = tempfile.mkdtemp()` (fake `$HOME`).
       2. Pre-create `tmp_home/.claude/CLAUDE.md` with content: `[[USER PRELUDE]]\n\n# === DEV WORKFLOW START ===\n[[OLD STALE WORKFLOW RULES]]\n# === DEV WORKFLOW END ===\n\n[[USER POSTLUDE]]\n`.
       3. **Pre-create cleanup-loop stubs** (lesson 2026-04-27 Stage 5 lesson B): write empty files at `tmp_home/.claude/scripts/summarize_for_human.py`, `tmp_home/.claude/scripts/with_env.sh`, `tmp_home/.claude/scripts/tests/test_summarize_for_human.py`, AND `tmp_home/.claude/scripts/tests/test_with_env_sh.py` — exercise BOTH iteration targets of the auxiliary cleanup loop on install.sh lines 146–151 (the loop iterates over both `test_summarize_for_human.py` AND `test_with_env_sh.py`). Per MIN-1 fix.
       4. Run `subprocess.run(["bash", "quoin/install.sh"], env={**os.environ, "HOME": tmp_home})`.
       5. Read `tmp_home/.claude/CLAUDE.md` after install.
       6. Assert: file contains exactly ONE marker section (regex `# === DEV WORKFLOW START ===.*?# === DEV WORKFLOW END ===` matches once, not zero or two).
       7. Assert: `[[USER PRELUDE]]` and `[[USER POSTLUDE]]` are both still present (user content preserved).
       8. Assert: pre-created stub files (`summarize_for_human.py`, `with_env.sh`, `tests/test_summarize_for_human.py`, AND `tests/test_with_env_sh.py`) are GONE (cleanup loops fired — actively exercised, not passively skipped). Per MIN-1 fix.
     - `test_fresh_claude_md_section_appended`: same flow but `tmp_home/.claude/CLAUDE.md` does NOT exist beforehand. Assert install.sh creates it with exactly one marker section.
   - **Acceptance:** Both test cases PASS. Test runs in <30s. No real `$HOME` mutation (verified by checking real `~/.claude/` post-test).
   - **Files modified:** new test file.
   - **Commit:** included in T-10 test commit.

9. ✓ T-09: `/init_workflow` legacy-prompt static contract test (`tests/test_init_workflow_legacy_quickstart.py`) — DONE (commit bb2ce23; 4 cases PASS — legacy prompt phrases, Step 7 new path, safe default to [k], Workflow-User-Guide qualified)
   - **Scope:** New pytest. `/init_workflow` is interactive — direct runtime testing requires a Claude Code harness. We test the SKILL.md text contract instead (per architecture the architecture's rebrand-path-conflicts integration concern / lesson "structural contract over LLM replay"):
     - `test_skill_md_contains_legacy_quickstart_prompt`: open `quoin/skills/init_workflow/SKILL.md`, assert it contains the literal phrases: `Legacy QUICKSTART location detected`, `(project)/dev-workflow/QUICKSTART.md`, `[m] Move`, `[d] Delete`, `[k] Keep`.
     - `test_skill_md_step_7_writes_to_workflow_artifacts`: assert SKILL.md Step 7 references `.workflow_artifacts/QUICKSTART.md` (the new location) and does NOT instruct writing to `(project)/dev-workflow/QUICKSTART.md` (the old location) outside the legacy-detection block. Implementation: parse SKILL.md sections by `## ` heading; isolate the Step 7 body; assert the new path appears and the old path is ONLY in the legacy-detection sub-block.
     - `test_skill_md_safe_default_when_source_clone_present`: assert SKILL.md contains text instructing the skill to default to `[k]` when `(project)/dev-workflow/install.sh` or `(project)/dev-workflow/SETUP.md` is detected (collision-with-source-clone safety).
     - `test_skill_md_workflow_user_guide_qualified`: open `quoin/skills/init_workflow/SKILL.md`, assert that prose Step 7 / Step 8 references to `Workflow-User-Guide.html` are qualified (i.e., contain `<your-quoin-clone>/`). Per MAJ-4 fix.
   - **Acceptance:** All 4 PASS.
   - **Files modified:** new test file.
   - **Commit:** included in T-10 test commit.

10. ✓ T-10: Fresh-clone install smoke test (`tests/test_install_fresh_clone.py`) — DONE (commit bb2ce23; 1 case PASS on dev machine — install.sh exit 0, all 21 SKILL.md, 5 v3 memory files, 3 v3 scripts deployed; module-level skip on missing `claude`/`npx`)
    - **Scope:** New pytest (Python wrapping bash for cleanliness). Test case:
      - `test_fresh_clone_install_e2e`:
        1. Module-level skip: `pytest.mark.skipif(shutil.which('claude') is None or shutil.which('npx') is None, reason='install.sh requires claude (hard) and npx (soft); test is dev-machine only')`. Per MIN-3 fix — install.sh aborts if `claude` is missing (lines 46–48), which would cause the test to fail for the wrong reason on CI without Claude Code.
        2. `tmp_home = tempfile.mkdtemp()`.
        3. Verify `quoin/install.sh` exists in working tree.
        4. Run `subprocess.run(["bash", "quoin/install.sh"], env={**os.environ, "HOME": tmp_home}, capture_output=True)`.
        5. Assert returncode == 0.
        6. Assert all 21 skill SKILL.md files copied: `for s in [...21 names...]: assert (tmp_home/.claude/skills/{s}/SKILL.md).exists()`.
        7. Assert the 4 v3 memory files deployed: format-kit.md, glossary.md, format-kit.sections.json, summary-prompt.md, terse-rubric.md (5 actually).
        8. Assert the 3 v3 scripts deployed + executable: validate_artifact.py, path_resolve.py, cost_from_jsonl.py.
        9. Assert `tmp_home/.claude/CLAUDE.md` contains exactly one marker section (regex match).
    - **Acceptance:** Test PASSES in <30s on dev-machine. SKIPS cleanly on CI without `claude`/`npx`. No real `$HOME` mutation.
    - **Files modified:** new test file.
    - **Commit:** `test(quoin-stage-6): T-07..T-10 acceptance tests for rebrand, install upgrade, init_workflow legacy prompt, fresh-clone install` — single commit covers T-07, T-08, T-09, T-10 because they're a coherent acceptance bundle.

11. ✓ T-11: Final acceptance sweep + tooling smoke — DONE (commit f8a753a residual cleanup; full pytest run = 332 passed / 1 failed; the single failure is `test_revise_revise_fast_sync_contract` which fails on `main` too — pre-existing "above"/"below" wording diff between revise/SKILL.md and revise-fast/SKILL.md, NOT caused by stage-6. test_measure_v3_savings::test_deterministic_byte_identical PASSES — TR-09 evidence v2-historical fixture preserved verbatim. Final case-insensitive sweep yielded 1 retained match: triage SKILL.md trigger phrase "set up dev workflow" — intentional backward-compat alias)
    - **Scope:**
      - Run all stage 6 of the parent architecture tests (4 new files): `python3 -m pytest quoin/scripts/tests/test_quoin_rebrand_no_residuals.py quoin/scripts/tests/test_install_seeded_claude_md.py quoin/scripts/tests/test_init_workflow_legacy_quickstart.py quoin/scripts/tests/test_install_fresh_clone.py -v`.
      - Run the FULL existing test suite: `python3 -m pytest quoin/scripts/tests/ -v` to confirm stages 1–5 still pass post-rename. (Lesson 2026-04-27 Stage 5 lesson C — many existing tests likely embed `dev-workflow/` paths; expect failures and update them in this task.) Confirm `test_measure_v3_savings.py::test_deterministic_byte_identical` still passes (the v2-historical fixture is preserved, so byte-size deltas are unchanged from pre-rebrand) — TR-09 evidence.
      - Final residual sweep: `grep -rn --exclude-dir=v2-historical 'dev-workflow' quoin/ README.md CHANGELOG.md 2>/dev/null` returns NO matches (case-sensitive; CHANGELOG documents the marker `# === DEV WORKFLOW START ===` which is uppercase, so won't match).
      - Case-insensitive sweep with documented exception: `grep -rni --exclude-dir=v2-historical 'dev[ -]workflow' quoin/ README.md CHANGELOG.md 2>/dev/null | grep -v 'CHANGELOG.md\|=== DEV WORKFLOW'` returns NO matches.
      - Verify `verify_subagent_dispatch.md` and `verify_path_resolve_smoke.md` (one-shot diagnostic templates) still parse — open and skim for path-string drift.
    - **Acceptance:**
      - All tests PASS (existing + 4 new).
      - Both grep sweeps return empty (lowercase strict + case-insensitive with documented exclusions).
      - Manual: re-run a `/cost_snapshot` from this session and verify the ledger tail still parses (no path-resolution regression introduced).
    - **Files modified:** any existing test files needing path-string updates from `dev-workflow/` → `quoin/` (separate fix-up commit if changes are >5 lines).
    - **Commit:** if test fix-ups needed: `test(quoin-stage-6): update existing tests for quoin/ path post-rename`. If no fix-ups needed (because mass-sub in T-02 already swept tests/), no additional commit.

12. ✓ T-12: GitHub repo rename — manual user action (documented + verified) — DONE (documented in T-02 commit body 4eb52c2 and CHANGELOG.md upgrade notes commit 8cb1064; manual `git remote -v` + `git ls-remote origin` checklist included; opt-in test deferred — not necessary because verification is one-line manual)
    - **Scope:** This task is NOT performed by the implementer. Document in commit body of the rename commit (T-02) and in CHANGELOG.md (T-06) that the user must manually rename the GitHub repository: `FourthWiz/claude_dev_workflow` → `FourthWiz/quoin` via GitHub web UI. GitHub auto-redirects existing `git clone`/`git pull` operations from the old name to the new name (no SSH/HTTPS URL break). After rename, the local `git remote -v` will still show the OLD URL — the rename commit body should remind: `git remote set-url origin git@github.com:FourthWiz/quoin.git` (optional cleanup; auto-redirect makes it non-blocking).
    - **Verification (per MIN-5 fix):** Add a one-line manual checklist item that the user runs `git remote -v` post-rename and confirms the URL is either updated or auto-redirect-confirmed (resolved via `git ls-remote origin` — succeeds either way thanks to GitHub's auto-redirect). Optional opt-in test: `quoin/scripts/tests/test_github_remote_url.py` (skipped by default; runs only when env var `VERIFY_GITHUB_RENAME=1` is set) asserts `git remote -v | grep -c FourthWiz/quoin` returns ≥1 OR `git ls-remote origin` succeeds with returncode 0. Test contains a one-line module skip: `pytest.mark.skipif(os.environ.get('VERIFY_GITHUB_RENAME') != '1', reason='manual GitHub rename verification — opt-in via env var')`.
    - **Acceptance:** Manual checklist item documented in CHANGELOG.md "Upgrade notes" subsection. The opt-in test (if added) PASSES when `VERIFY_GITHUB_RENAME=1` is set after the user renames; SKIPS otherwise (default).
    - **Files modified:** optional new test file `quoin/scripts/tests/test_github_remote_url.py`.
    - **Commit:** if opt-in test added, fold into T-10 test commit; otherwise none.

## Decisions

D-01: **Mass-sub via `sed` (vs. per-file edits via Edit tool) — applies to source-tree text files only.**
The 31 files / 140 occurrences of the literal token `dev-workflow` (always meaning "the workflow source dir") are uniform mechanical work. A single `sed -i '' 's|dev-workflow|quoin|g' <file-list>` is mechanical, auditable in `git diff`, and avoids per-file drift. Edit-tool per-file would multiply LLM cost ~30× without quality gain. **Why:** lesson 2026-04-22 (Opus on docs-only is disproportionate); mechanical work belongs in mechanical tools. **How to apply:** T-02 uses `sed` for the bulk swap with a `-prune` exclusion of the v2-historical fixture path (per D-06); install.sh banner text and CLAUDE.md self-referential prose use surgical Edit-tool calls (those are nuanced — see D-07).

D-02: **`/init_workflow` Step 7 source-discovery: ask the user with auto-suggestion.**
The new Step 7 needs to locate `<quoin-source-dir>/QUICKSTART.md` to copy from. Three options were considered (see T-04 scope). Option (a) auto-resolve from `~/.claude/skills/` is fragile across non-standard layouts. Option (b) ask-the-user is reliable but adds friction. Option (c) embed inline duplicates content (current bug — drift between source and inline copy already observed: source QUICKSTART.md has 17 entries, inline template has only 13). **Decision:** ask the user with `(a)` as auto-suggestion. **Why:** keeps single source of truth (lesson 2026-04-23 caveman rubric) while gracefully handling non-standard installs. **How to apply:** T-04's Step 7 rewrite includes both auto-detection logic and a fallback prompt.

D-03: **Two stable runtime strings stay VERBATIM across the rebrand.**
The 12 cheap-tier SKILL.md files (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast) emit two stable runtime strings via the §0 model-dispatch preamble:
  1. `[quoin-stage-1: subagent dispatch unavailable; ...]` — emitted on fail-open dispatch failure (per architecture I-01).
  2. `Quoin self-dispatch hard-cap reached at N=<N> in <skill name>. This indicates a recursion bug; aborting before any tool calls. Re-invoke with [no-redispatch] (bare) to override.` — emitted on the hard-cap recursion abort path (asserted by `test_quoin_stage1_recursion_abort.py:108`).
Renaming either string would: (a) break user-side grep/log filters established during stages 1–5; (b) require updating the 12 SKILL.md files AND `test_quoin_stage1_*.py` AND `verify_subagent_dispatch.{md,py}`; (c) introduce drift between deployed `~/.claude/skills/` (live in user envs) and source. **Decision:** keep BOTH verbatim as stable diagnostic identifiers. The rebrand updates PROSE references to "Quoin foundation Stage 1" (the planning-task name) but leaves diagnostic strings, file names, and test names alone. **Why:** stable identifiers are cheaper than churn. **How to apply:** T-02 acceptance has two grep checks distinguishing the prose form from each stable runtime string; commit body explicitly enumerates both. (Round-1 plan only enumerated string #1; this round adds string #2 per critic MAJ-3.)

D-04: **Repo-internal layout: `quoin/quoin/` is acceptable; install path is `cd quoin && bash quoin/install.sh`.**
Post-rename, a fresh `git clone https://github.com/FourthWiz/quoin` creates a directory called `quoin/` (GitHub default) containing `quoin/` (the source — formerly `dev-workflow/`), README.md, CHANGELOG.md. The `quoin/quoin/` nesting is awkward but matches the architecture's "rename `dev-workflow/` → `quoin/`" mandate (no restructure). Alternative — flattening the repo root to absorb `dev-workflow/` contents — is out-of-scope. **Why:** architecture chose simple rename for low-risk rebrand (the architecture's user-install-breakage risk: "Low likelihood, Medium impact"); flattening would touch ~50% of paths that currently work fine. **How to apply:** README.md (T-05 Section 3) and CHANGELOG.md (T-06) standardize on the canonical install command `git clone https://github.com/FourthWiz/quoin && cd quoin && bash quoin/install.sh` — single `cd` step into the clone root, then `bash quoin/install.sh` against the inner source dir. Per MIN-4 fix — round 1 had `cd quoin/quoin && bash install.sh` in the prose, which contradicted the README's actual command; this round aligns the decision text with T-05's command.

D-05: **Pictures move into the renamed source (`quoin/docs/images/`), not project root.**
Versioned with the source repo so README path-references survive any future repo reorg. **Why:** `pictures_for_git/` at toplevel was a temporary holding pen; finalized assets belong in the source tree. **How to apply:** T-03 git-mv preserves history per file.

D-06: **Frozen v2-historical fixture content is preserved verbatim; only path strings in `measure_v3_savings.py` are rewritten.**
`quoin/scripts/tests/fixtures/v2-historical/{architecture,review,critic-response,current-plan,gate,session}.md` is a captured byte-size baseline consumed by `measure_v3_savings.py` to compute v2→v3 deltas. Each `dev-workflow` (12 chars) → `quoin` (5 chars) replacement inside the fixture content shaves 7 bytes per occurrence and silently shifts the computed `## Sensitivity` row dollar values without explanation. Worse: the fixture content is a CAPTURED HISTORICAL artifact, not a current source — rewriting violates the frozen-baseline principle (lesson 2026-04-22). **Decision:** the find-sweep in T-02 prunes `quoin/scripts/tests/fixtures/v2-historical/` from the mass-sed; the frozen content stays untouched. Separately, the FIXTURE_PATH constants in `quoin/scripts/measure_v3_savings.py` (lines 60–89, plus prose references on 15, 148, 153, 231) ARE rewritten — those are source-tree path strings the script uses to LOCATE fixtures, not frozen content. **Why:** preserving captured baselines while keeping locator paths consistent. **How to apply:** see Procedures §proc-T02 step 2 for the exact `find ... -path '...v2-historical' -prune -o ... -print0` invocation; verify with the T-02 acceptance grep that returns ≥10 inside the fixture (sentinel that the prune worked).

D-07: **CLAUDE.md prose edits: surgical Edit-tool, NOT broad sed.**
Round-1 plan used a broad `sed 's|Quoin Stage 1 |the §0 model-dispatch preamble |g' quoin/CLAUDE.md` substitution that would have produced doubled phrases on at least line 393 (`Quoin Stage 1 §0 preamble template` → `the §0 model-dispatch preamble §0 preamble template`). This is the lesson-2026-04-22 risk class (mass-sed false positives in nuanced prose). **Decision:** for the four touched CLAUDE.md prose lines (subsection heading, line 393, line 394, line 434), use surgical Edit-tool calls that produce the desired exact prose for each line. Each Edit's `old_string` and `new_string` are spelled out verbatim in §proc-T02 step 4. **Why:** surgical replacement guarantees the post-edit prose is exactly what we want, with no doubling or context-collision artifacts. **How to apply:** §proc-T02 step 4 enumerates one Edit-tool call per touched line; T-02 acceptance includes greps that the doubled phrase `§0 model-dispatch preamble §0` does NOT appear (the round-1 sed-bug sentinel). Per critic MAJ-1 fix.

## Risks

| ID | Risk | Likelihood | Impact | Mitigation | Rollback |
|----|------|-----------|--------|------------|----------|
| TR-01 | Mass `sed` substitution breaks a path the regex didn't anticipate (e.g., `dev-workflow-lite/` if it existed somewhere). | Low | Medium | Pre-T-02 dry-run: `grep -rn 'dev-workflow' dev-workflow/ \| grep -v 'dev-workflow$\|dev-workflow/'` — flag any context that's NOT the literal directory token. | Revert T-02 commit; re-do with surgical sed exclusions. |
| TR-02 | Existing tests under `quoin/scripts/tests/` break post-rename because they hardcode `dev-workflow/` paths. | High | Low | T-11 runs the full existing suite immediately after T-02 mass-sub; lesson 2026-04-27 Stage 5 lesson C demands that acceptance grep matches the implementation pattern, not the assumed pattern. Test fix-ups are budgeted as a sub-task of T-11. | Revert T-02; investigate which tests need surgical (non-mass-sub) handling. |
| TR-03 | The architecture's install.sh-marker-shift risk surfaced: install.sh marker accidentally rewritten despite mitigation. | Low | High | T-08 seeded-CLAUDE.md upgrade test is the primary contract test. T-02 acceptance step explicitly greps for the verbatim marker. CI-style: `grep -F '# === DEV WORKFLOW START ===' quoin/install.sh` MUST return ≥1 after T-02. | Revert T-02; re-run mass-sub with explicit `--exclude` for marker lines. |
| TR-04 | The architecture's user-install-breakage risk surfaced: existing user installs running `bash dev-workflow/install.sh` against a freshly-pulled rename break. | Low | Medium | CHANGELOG.md (T-06) documents the new path. install.sh's banner text instructs users on next steps. Crucially: `git pull` followed by `bash quoin/install.sh` works because GitHub auto-redirect handles the URL change. | User runs `git remote set-url origin git@github.com:FourthWiz/quoin.git` once. Worst-case: `mv quoin dev-workflow && bash dev-workflow/install.sh` is the rollback. |
| TR-05 | Pictures' filenames break markdown rendering (spaces, non-ASCII). | Low | Low | T-03 renames pictures to ASCII-safe slugs in the same git-mv commit. Acceptance: `[[ "$(basename "$f")" =~ ^[a-z0-9-]+\.png$ ]]` for every image. | Re-rename the offending file. |
| TR-06 | `/init_workflow` legacy-detection prompt is inconsistent with the existing memory-legacy block (Step 5), causing user confusion. | Medium | Low | T-04 modifies BOTH legacy blocks side-by-side and shares the same prompt format. T-09 static contract test asserts both blocks coexist. | Revert T-04; re-add only the new block with custom format. |
| TR-07 | Recursive self-reference in CLAUDE.md: the §0 preamble subsection's stage-tracker note (line 434) references "Quoin foundation Stage 1" — updating it requires care to avoid breaking the verbatim-diagnostic-string discipline (D-03). | Medium | Low | T-02 separates prose-mention edits (surgical Edit-tool per D-07) from diagnostic-string edits (untouched). Acceptance: `grep -c 'Quoin foundation Stage' quoin/CLAUDE.md` returns 0 (prose); `grep -c '\[quoin-stage-1:' quoin/skills/*/SKILL.md` returns 12 (diagnostic preserved); `grep -l 'Quoin self-dispatch hard-cap reached at N=' quoin/skills/*/SKILL.md \| wc -l` returns 12 (second runtime string preserved). | Revert just the CLAUDE.md edit; redo with finer surgical edits. |
| TR-08 | Fresh-clone install test (T-10) fails on CI environments lacking `claude` (hard dep) or `npx` (soft warn). | Low | Low | install.sh aborts if `claude` missing (lines 46–48); `npx` is a soft warning. Test case has module-level skip on either tool missing: `pytest.mark.skipif(shutil.which('claude') is None or shutil.which('npx') is None)`. Test runs in dev's machine env (both tools present); SKIPS cleanly on CI. Per MIN-3 fix — round 1 only handled npx. | Mark stricter — gate the skip on env var `RUN_FRESH_CLONE_INSTALL=1` if needed. |
| TR-09 | Mass-sed sweep mutates frozen v2-historical fixture, silently shifting the v2→v3 byte-size delta in `measure_v3_savings.py` and rotating the `## Sensitivity` dollar values without explanation. | Medium | Medium | Per D-06, T-02 explicitly prunes `quoin/scripts/tests/fixtures/v2-historical/` from the find-sweep. Acceptance grep `grep -rn 'dev-workflow' quoin/scripts/tests/fixtures/v2-historical/` returns ≥10 (sentinel that the prune worked). T-11 confirms `test_measure_v3_savings.py::test_deterministic_byte_identical` still passes (deltas unchanged from pre-rebrand). Lesson 2026-04-22 — frozen historical artifacts captured for regression baselines must not be rewritten when upstream input changes. Per critic MAJ-2 fix. | Revert just the v2-historical-fixture portion of T-02 (`git checkout HEAD~1 -- quoin/scripts/tests/fixtures/v2-historical/`). |

## Procedures

### proc-T02: T-02 mass substitution + sentinel preservation

```
# Step 0: dry-run audit
grep -rn 'dev-workflow' dev-workflow/ > /tmp/dw-refs-before.txt
wc -l /tmp/dw-refs-before.txt   # expect ~140 occurrences across 31 files

# Step 1: rename top-level dir (preserves git history)
git mv dev-workflow quoin

# Step 2: mass substitute in all text files under quoin/, EXCLUDING v2-historical
# Per D-06 / TR-09 — the v2-historical fixture is a frozen byte-size baseline.
# The -path/-prune branch of find prunes the entire v2-historical dir before -name filters apply.
find quoin \
  -type d -path 'quoin/scripts/tests/fixtures/v2-historical' -prune \
  -o -type f \( -name '*.md' -o -name '*.sh' -o -name '*.py' -o -name '*.json' -o -name '*.html' \) -print0 | \
  xargs -0 sed -i '' 's|dev-workflow|quoin|g'

# Sanity: verify the prune actually fired
grep -rn 'dev-workflow' quoin/scripts/tests/fixtures/v2-historical/ | wc -l   # expect ≥10 (frozen content untouched)

# Step 3: surgical edits to quoin/install.sh (banner + log lines, NOT marker variables)
# (sed step 2 already swept "dev-workflow" lowercase; what remains is the
#  banner text "Dev Workflow" mixed-case — handle separately:)
sed -i '' 's|Dev Workflow Installer|Quoin Installer|g; s|Dev Workflow|Quoin|g' quoin/install.sh

# Step 4: surgical edits to quoin/CLAUDE.md — Edit-tool calls, NOT sed (per D-07).
# Each Edit produces the exact desired prose. NO doubled-phrase artifacts.
#
# Edit 1 — subsection heading (~line 373 post-step-2):
#   old_string: "### §0 Model dispatch preamble (Quoin foundation Stage 1)"
#   new_string: "### §0 Model dispatch preamble"
#
# Edit 2 — Tier 1 entry, line 393 post-step-2:
#   old_string: "- `quoin/scripts/tests/fixtures/quoin-stage-1-preamble.md` (Quoin Stage 1 §0 preamble template; hand-edited Tier 1; source of truth for the 12 cheap-tier SKILL.md preambles)."
#   new_string: "- `quoin/scripts/tests/fixtures/quoin-stage-1-preamble.md` (§0 preamble template; hand-edited Tier 1; source of truth for the 12 cheap-tier SKILL.md preambles)."
#
# Edit 3 — Tier 1 entry, line 394 post-step-2:
#   old_string: "- `quoin/scripts/verify_subagent_dispatch.md` (Quoin Stage 1 subagent-dispatch verification template; hand-filled by user during T-00 pilot and T-09 smoke; lives at `quoin/scripts/` only — NOT deployed to `~/.claude/scripts/` per round-3 MIN-1 fix; one-shot diagnostic, not a runtime tool)."
#   new_string: "- `quoin/scripts/verify_subagent_dispatch.md` (§0 subagent-dispatch verification template; hand-filled by user during T-00 pilot and T-09 smoke; lives at `quoin/scripts/` only — NOT deployed to `~/.claude/scripts/` per round-3 MIN-1 fix; one-shot diagnostic, not a runtime tool)."
#
# Edit 4 — prose, line ~434 post-step-2 (rewrites both the leading prose AND removes the trailing parenthetical):
#   old_string: "Mechanical drift detection lives in `quoin/scripts/tests/test_quoin_stage1_preamble.py` and `quoin/scripts/tests/test_quoin_stage1_recursion_abort.py`; manual production-dispatch verification lives in T-00 (pilot, before T-02) and T-09 (full four-phase smoke after T-02 + install) of the stage-1 plan and is captured in `quoin/scripts/verify_subagent_dispatch.md`. (Note for the future Quoin-rebrand stage: this subsection's \"Quoin foundation Stage 1\" reference becomes stale post-rebrand — update the wording to a stage-tracker-stable reference at that time.)"
#   new_string: "Mechanical drift detection lives in `quoin/scripts/tests/test_quoin_stage1_preamble.py` and `quoin/scripts/tests/test_quoin_stage1_recursion_abort.py`; manual production-dispatch verification is captured in `quoin/scripts/verify_subagent_dispatch.md`."
#   (Removes "Quoin foundation Stage 1" / "of the stage-1 plan" planning-task references AND the trailing in-flight parenthetical, per MIN-2.)
#
# Edit 5 — prose, summary-prompt entries (any lines containing "per Quoin Stage 5 architecture"):
#   old_string: "per Quoin Stage 5 architecture"
#   new_string: "per stage 5 of the Quoin foundation work"
#   (Use replace_all=true since the phrase may appear on more than one line.)

# Step 5: verify (acceptance criteria)
grep -rn --exclude-dir=v2-historical 'dev-workflow' quoin/ | wc -l   # expect 0
grep -rn 'dev-workflow' quoin/scripts/tests/fixtures/v2-historical/ | wc -l   # expect ≥10 (frozen)
grep -F '# === DEV WORKFLOW START ===' quoin/install.sh | wc -l   # expect 1
grep -F '[quoin-stage-1: subagent dispatch unavailable' quoin/skills/*/SKILL.md | wc -l   # expect 12
grep -l 'Quoin self-dispatch hard-cap reached at N=' quoin/skills/*/SKILL.md | wc -l   # expect 12
grep -c 'Quoin foundation Stage' quoin/CLAUDE.md quoin/skills/*/SKILL.md   # expect all 0
grep -c 'future Quoin-rebrand stage' quoin/CLAUDE.md   # expect 0
grep -c '§0 model-dispatch preamble §0' quoin/CLAUDE.md   # expect 0 (round-1 sed-bug sentinel)
# Hand-listed CRIT-1 acceptance:
python3 -c "txt=open('quoin/CLAUDE.md').read(); names=['quoin-stage-1-preamble.md','test_quoin_stage1_preamble.py','test_quoin_stage1_recursion_abort.py','verify_subagent_dispatch.md']; missing=[n for n in names if n not in txt]; assert not missing, f'missing: {missing}'"
```

### proc-T08: T-08 seeded-CLAUDE.md upgrade test (cleanup-loop active exercise)

```
# Per lesson 2026-04-27 Stage 5 lesson B — pre-create stubs to actively exercise
# install.sh's cleanup loops. Passive verification (loop runs but finds nothing
# to delete) silently skips the branch under test.
#
# Per critic MIN-1 — install.sh's auxiliary cleanup loop on lines 146–151
# iterates over BOTH test_summarize_for_human.py AND test_with_env_sh.py;
# round-1 plan only seeded the first. This round seeds both.

setup:
  tmp_home = tempfile.mkdtemp()
  os.makedirs(f"{tmp_home}/.claude/scripts/tests", exist_ok=True)
  # Seed CLAUDE.md with marker section
  with open(f"{tmp_home}/.claude/CLAUDE.md", "w") as f:
    f.write("USER PRELUDE\n\n# === DEV WORKFLOW START ===\nOLD STALE CONTENT\n# === DEV WORKFLOW END ===\n\nUSER POSTLUDE\n")
  # Seed Stage 5 obsolete cleanup stubs (active exercise) — primary loop
  for stub in ["summarize_for_human.py", "with_env.sh"]:
    open(f"{tmp_home}/.claude/scripts/{stub}", "w").close()
  # Seed Stage 5 obsolete TEST stubs (active exercise) — auxiliary loop, BOTH targets
  for stub in ["test_summarize_for_human.py", "test_with_env_sh.py"]:
    open(f"{tmp_home}/.claude/scripts/tests/{stub}", "w").close()

run:
  result = subprocess.run(["bash", "quoin/install.sh"],
                          env={**os.environ, "HOME": tmp_home},
                          capture_output=True, text=True)
  assert result.returncode == 0

assert:
  content = open(f"{tmp_home}/.claude/CLAUDE.md").read()
  marker_sections = re.findall(r"# === DEV WORKFLOW START ===.*?# === DEV WORKFLOW END ===",
                               content, re.DOTALL)
  assert len(marker_sections) == 1   # NOT two (would mean appended) and NOT zero
  assert "USER PRELUDE" in content   # user content preserved
  assert "USER POSTLUDE" in content
  assert "OLD STALE CONTENT" not in content   # marker section was REPLACED
  # Cleanup loops actively exercised (both primary + both auxiliary targets):
  assert not os.path.exists(f"{tmp_home}/.claude/scripts/summarize_for_human.py")
  assert not os.path.exists(f"{tmp_home}/.claude/scripts/with_env.sh")
  assert not os.path.exists(f"{tmp_home}/.claude/scripts/tests/test_summarize_for_human.py")
  assert not os.path.exists(f"{tmp_home}/.claude/scripts/tests/test_with_env_sh.py")
```

## References

- Architecture: `.workflow_artifacts/quoin-foundation/architecture.md` — stage 6 of the parent architecture; the architecture's user-install-breakage risk, install.sh-marker-shift risk, rebrand-path-conflicts integration concern, and install.sh-idempotency integration concern govern this plan.
- Lessons: `.workflow_artifacts/memory/lessons-learned.md` — 2026-04-13 (cross-skill SKILL.md updates), 2026-04-22 (Opus-on-docs cost discipline; frozen historical baselines), 2026-04-26 (commit-message documentation discipline), 2026-04-27 Stage 5 lessons A/B/C (rc-hang risk class closure, install.sh dual-cleanup pattern, acceptance grep matches implementation pattern).
- v3 format kit: `~/.claude/memory/format-kit.md` — Class B writer 6-step mechanism + standard sections for `current-plan.md`.
- Glossary: `~/.claude/memory/glossary.md` — abbreviation whitelist + status glyph rules.
- Source files audited (round 1 + round 2 verifications):
  - `dev-workflow/install.sh` (210 lines — markers on lines 162–163; primary cleanup loop on lines 137–145; auxiliary test cleanup loop on lines 146–151 with TWO targets per MIN-1).
  - `dev-workflow/CLAUDE.md` (434 lines — §0 preamble subsection at line ~373; Tier 1 fixture entries on lines 393, 394; in-flight rebrand note at line 434; verified round 2: 4 stable test/fixture filenames present, 3 distinct CLAUDE.md lines reference them — round-1 grep `>=4` was wrong, hand-listed assertion adopted).
  - `dev-workflow/skills/init_workflow/SKILL.md` (~340 lines — Step 5 tree at lines 158–175; Step 7 at lines 252–311; existing memory-legacy detection at lines 77–93; Workflow-User-Guide refs on lines 173, 254, 306, 310, 322, 333 per MAJ-4).
  - `dev-workflow/QUICKSTART.md` (82 lines — current source of truth; verified round 2: contains 17 skill rows; lines 78 and 82 reference unqualified `Workflow-User-Guide.html` per MAJ-4 + MIN-6).
  - `README.md` at repo root (480 lines, 13KB — full rewrite; verified round 2: 20 skill rows present, missing `/expand`; rewrite must include all 21).
  - `dev-workflow/scripts/measure_v3_savings.py` (250+ lines — `FIXTURE_PAIRS` constants on lines 60–89; prose pointers on 15, 148, 153, 231 — these ARE source paths and must be updated per D-06).
  - `dev-workflow/scripts/tests/fixtures/v2-historical/{architecture.md, review.md, ...}` — verified round 2: contains many `dev-workflow` references; frozen-baseline status confirmed; pruned from T-02 mass-sed per D-06 / TR-09.
  - 12 cheap-tier SKILL.md files (gate, end_of_day, start_of_day, triage, capture_insight, cost_snapshot, weekly_review, end_of_task, implement, rollback, expand, revise-fast — each carries §0 preamble + diagnostic warning string + hard-cap runtime string per MAJ-3).
- Test fixtures retained verbatim (D-03 + D-06):
  - `dev-workflow/scripts/tests/fixtures/quoin-stage-1-preamble.md` → `quoin/scripts/tests/fixtures/quoin-stage-1-preamble.md` (filename preserved; only path-prefix changes via git mv).
  - `dev-workflow/scripts/verify_subagent_dispatch.{md,py}` → `quoin/scripts/verify_subagent_dispatch.{md,py}` (same pattern).
  - `dev-workflow/scripts/tests/test_quoin_stage1_{preamble,recursion_abort}.py` → `quoin/scripts/tests/...` (same pattern).
  - `dev-workflow/scripts/tests/fixtures/v2-historical/*.md` → `quoin/scripts/tests/fixtures/v2-historical/*.md` (path renamed; CONTENT preserved verbatim per D-06).
- GitHub remote: currently `git@github.com:FourthWiz/claude_dev_workflow.git`; manual repo rename to `FourthWiz/quoin` is documented in T-12 + CHANGELOG.md, with optional opt-in test per MIN-5.

## Notes

**Commit boundaries summary:**
1. T-02 commit — rename + mass-sub (with v2-historical prune) + install.sh banners + CLAUDE.md surgical Edits + measure_v3_savings.py path constants (single coherent diff; broken intermediate states avoided)
2. T-03 commit — pictures move
3. T-04 commit — /init_workflow Step 5/7/legacy-detection + qualify Workflow-User-Guide refs + refresh QUICKSTART.md to 21 skills
4. T-05 commit — README rewrite
5. T-06 commit — CHANGELOG creation
6. T-10 commit — 4 acceptance tests bundled (T-07 + T-08 + T-09 + T-10), optionally including the T-12 opt-in GitHub-remote test
7. (Conditional) T-11 commit — existing-test fix-ups, only if mass-sub didn't sweep them clean

**Total commits expected: 6–7.** All on branch `feat/quoin-stage-6`. No push during plan/implement; push happens at `/end_of_task`.

**`/implement` & `/end_of_task` rule:** This plan does NOT auto-invoke either. After `/thorough_plan` converges and the gate passes, the user explicitly types `/implement`.

**Out-of-scope confirmation (per architecture exclusions):**
- install.sh `$SCRIPT_DIR`-relative path logic — untouched (path-invariant; the rename is transparent to it).
- `~/.claude/CLAUDE.md` markers — untouched; T-02 verifies preservation.
- `.workflow_artifacts/` path conventions — untouched.
- GitHub repo rename (the actual click in GitHub web UI) — manual user action documented in T-12.
- Frozen v2-historical fixture content — untouched (per D-06).

## Revision history

1. **Round 1 — 2026-04-27** — initial plan drafted: 12 implementation tasks, 8 risks, 5 decisions, 2 procedures. Class B v3 format with `## For human` summary + format-aware body.
2. **Round 2 — 2026-04-27** — addressed critic-response-1 (REVISE; 2 CRIT, 4 MAJ, 6 MIN).
   - **[CRIT-1]** T-02 acceptance grep `>=4` was empirically `3` against `dev-workflow/CLAUDE.md` (verified). Replaced with hand-listed Python assertion: `for name in [4 filenames]: assert name in claude_md_text`. Order-independent, count-explicit.
   - **[CRIT-2]** T-05 acceptance grep `^\| `/[a-z_]+`` excluded hyphen so `revise-fast` failed to match (verified: regex returns 19 against current README; total table has 20 rows). Replaced with hand-listed Python assertion enumerating the 21 canonical skills (architect…weekly_review). Mechanically detects both today's `/expand` gap AND the round-1 hyphen bug.
   - **[MAJ-1]** proc-T02 step 4 broad sed `s|Quoin Stage 1 |the §0 model-dispatch preamble |g` would have produced `the §0 model-dispatch preamble §0 preamble template` on CLAUDE.md line 393 (doubled `§0`). Replaced with five surgical Edit-tool calls (one per touched line); added D-07 codifying the surgical-Edit-not-sed rule; added acceptance grep `grep -c '§0 model-dispatch preamble §0' quoin/CLAUDE.md` returns `0` as round-1 sed-bug sentinel.
   - **[MAJ-2]** Mass-sed swept `quoin/scripts/tests/fixtures/v2-historical/architecture.md` and `review.md`, both frozen byte-size baselines for `measure_v3_savings.py`; rewriting their content silently shifts the v2→v3 delta. Added D-06 + TR-09; rewrote proc-T02 step 2 to prune the v2-historical path via `find -path ... -prune`; added FIXTURE_PATH constants update in `measure_v3_savings.py` (path strings rewritten — those ARE source paths, NOT frozen content); added sentinel acceptance grep that v2-historical content still has ≥10 `dev-workflow` references.
   - **[MAJ-3]** D-03 only enumerated `[quoin-stage-1: ...]` as the stable runtime string but missed `Quoin self-dispatch hard-cap reached at N=` (lives in all 12 cheap-tier SKILL.md files; asserted by `test_quoin_stage1_recursion_abort.py:108`). Extended D-03 to enumerate BOTH stable runtime strings; added T-02 acceptance `grep -l 'Quoin self-dispatch hard-cap reached at N=' quoin/skills/*/SKILL.md | wc -l` returns `12`; updated TR-07 mitigation to track both strings; updated T-02 commit body requirement.
   - **[MAJ-4]** T-04 QUICKSTART relocation orphaned `Workflow-User-Guide.html` references on lines 78 and 82 of source `dev-workflow/QUICKSTART.md`; same problem in `init_workflow/SKILL.md` lines 254, 306, 310, 322, 333. Picked option (a) — qualify all references with `<your-quoin-clone>/`; added T-04 step rewriting both QUICKSTART.md and SKILL.md prose; added T-09 fourth test case `test_skill_md_workflow_user_guide_qualified`; added T-04 acceptance grep that no unqualified references survive.
   - **[MIN-1]** T-08 only seeded one of two auxiliary cleanup loop targets (`test_summarize_for_human.py` but not `test_with_env_sh.py`). Extended seeding in proc-T08 + T-08 step 3 + T-08 step 8 to seed and assert removal of BOTH targets. Per lesson 2026-04-27 Stage 5 lesson B (active exercise of both branches).
   - **[MIN-2]** proc-T02 step 4 mentioned the in-flight parenthetical at CLAUDE.md line 434 ("Note for the future Quoin-rebrand stage: ...") only as a comment, not as an actionable Edit step. Folded the parenthetical removal into Edit 4 of proc-T02 (covers both the leading prose rewrite AND the trailing parenthetical removal in a single Edit call); added T-02 acceptance `grep -c 'future Quoin-rebrand stage' quoin/CLAUDE.md` returns `0`.
   - **[MIN-3]** TR-08 mitigation only handled `npx`, not the hard `claude` CLI dependency in install.sh (lines 46–48 abort if missing). Extended TR-08 + T-10 to skip on either missing: `pytest.mark.skipif(shutil.which('claude') is None or shutil.which('npx') is None)`.
   - **[MIN-4]** D-04 prose said `cd quoin/quoin && bash install.sh` but T-05's README install line said `cd quoin && bash quoin/install.sh`. Rewrote D-04 last paragraph to match T-05's canonical command; D-04 now explicitly cites T-05's command as the canonical install path.
   - **[MIN-5]** T-12 (manual GitHub repo rename) had no verification step. Added a one-line manual checklist item (run `git remote -v` post-rename) + optional opt-in test `quoin/scripts/tests/test_github_remote_url.py` gated by env var `VERIFY_GITHUB_RENAME=1`.
   - **[MIN-6]** Source `dev-workflow/QUICKSTART.md` had 17 skill entries (not the canonical 21); after T-04 the cp becomes source-of-truth, drift carries forward. Folded into T-04 (called out as T-04b sub-step) a refresh of `quoin/QUICKSTART.md` to the canonical 21-skill list; added T-04 acceptance `python3 -c "..."` asserting all 21 skill commands appear.
   - **Net changes:** State block adds two new exclusions (hard-cap runtime string, frozen v2-historical fixtures) + new deliverable (refresh QUICKSTART.md to 21 skills); new D-06 (frozen-fixture preservation), D-07 (surgical-Edit-not-sed); new TR-09 (frozen-fixture-rot risk); proc-T02 rewritten (find-prune; five surgical Edits replace broad sed); proc-T08 extended (4 stubs not 3); T-04 grows by ~2 sub-steps (Workflow-User-Guide qualification + QUICKSTART refresh); T-09 grows by 1 test case; T-10 gains skip-condition; T-12 gains verification step. Plan stays surgical — no other sections rewritten.

## Convergence Summary

```yaml
task_profile: Large (strict mode — all-Opus, max 5 rounds)
rounds: 2
final_verdict: PASS
key_revisions:
  - round 1 -> round 2: addressed 2 CRIT (T-02 grep count off-by-one; T-05 regex hyphen exclusion) + 4 MAJ (proc-T02 sed doubled-phrase collision; v2-historical fixture mass-sed mutation; D-03 incomplete enumeration of stable runtime strings; T-04 dangling Workflow-User-Guide.html refs) + 6 MIN (cleanup-loop dual-target seeding; in-flight parenthetical surgical edit; TR-08 claude-CLI skip; D-04/T-05 prose alignment; T-12 verification step; QUICKSTART canonical 21-skill refresh)
remaining_concerns: none — critic-response-2 verified all 12 round-1 issues empirically resolved against actual codebase; no new CRIT/MAJ surfaced
```
