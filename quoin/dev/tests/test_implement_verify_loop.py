"""IVG-126 T-04: Drift-test guard for the automated verify-fix loop.

Guards the `### Automated verify-fix loop (post-task)` subsection added to
the Claude adapter implement SKILL.md (T-01), the portable
`## Automated verify-fix loop` contract in the core intent doc (T-02), and
the Codex procedure extension (T-03).

Follows the `_region()` header-slice pattern from
test_gate_affected_area_tokens.py so tokens are asserted WITHIN the guarded
region — not merely anywhere in the file — and the path-helper style from
test_implement_adapter_pilot.py.

Round-3 plan defects (CRIT-1, MAJ-1, MIN-1, MIN-2) each get a dedicated
regression-guard test below, per the plan's strengthened T-04 acceptance
list: the guards assert the resolved-variable VALUE, not merely flag
presence, so a reintroduced defect fails loudly.
"""
from __future__ import annotations

import re
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/

ADAPTER_SKILL = PKG_DIR / "adapters" / "claude" / "skills" / "implement" / "SKILL.md"
CORE_DOC = PKG_DIR / "core" / "skills" / "implement.md"
CODEX_PROCEDURE = PKG_DIR / "adapters" / "codex" / "procedures" / "implement.md"

REGION_HEADER = "### Automated verify-fix loop (post-task)"


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _region(text: str, header: str) -> str:
    """Return text from header until the next H2/H3 markdown heading.

    Mirrors `_region()` in test_gate_affected_area_tokens.py: only lines
    starting with `## ` or `### ` end the region, so single-hash comment
    lines embedded in pseudocode (e.g. `# best-effort linter`) don't
    truncate it early.
    """
    start = text.find(header)
    assert start != -1, f"Region header not found: {header!r}"
    after = text[start + len(header):]
    m = re.search(r"^#{2,3} ", after, re.MULTILINE)
    if m:
        return after[: m.start()]
    return after


def _adapter_region() -> str:
    return _region(_load(ADAPTER_SKILL), REGION_HEADER)


# ── (a) Adapter SKILL.md — core token presence, scoped to the region ──────


def test_adapter_region_heading_present():
    text = _load(ADAPTER_SKILL)
    assert REGION_HEADER in text, (
        f"Adapter SKILL.md must contain heading {REGION_HEADER!r} (T-01 subsection missing)."
    )


def test_adapter_region_has_retry_knob_and_default():
    region = _adapter_region()
    assert "QUOIN_VERIFY_RETRIES" in region, (
        "Verify-loop region must document the QUOIN_VERIFY_RETRIES retry-bound knob (T-01)."
    )
    assert "default `3`" in region, (
        "Verify-loop region must state the QUOIN_VERIFY_RETRIES default of 3 (T-01)."
    )


def test_adapter_region_uses_affected_tests_script_no_literal_home():
    region = _adapter_region()
    assert "__QUOIN_HOME__/scripts/affected_tests.py" in region, (
        "Verify-loop region must invoke __QUOIN_HOME__/scripts/affected_tests.py (D-01: no new wrapped script)."
    )
    assert "~/.claude/" not in region, (
        "Verify-loop region must not contain a literal ~/.claude/ path — use __QUOIN_HOME__ (adapter/core boundary)."
    )


def test_adapter_region_exit_code_retry_vs_degrade_distinction():
    region = _adapter_region()
    assert "Exit `1`" in region and "the only code that enters the retry loop" in region, (
        "Verify-loop region must state that exit 1 is the ONLY code entering the retry loop (D-02)."
    )
    assert "Exit `2`/`3`/`4`" in region and "degrade" in region, (
        "Verify-loop region must state that exit 2/3/4 degrades without consuming a retry (D-02)."
    )


def test_adapter_region_fail_open_warning_present():
    region = _adapter_region()
    assert "fail-OPEN degrade path" in region, (
        "Verify-loop region must contain a fail-OPEN warning for the script-missing case (D-02/D-03)."
    )
    assert "no linter configured; skipping lint" in region, (
        "Verify-loop region must contain the fail-OPEN warning for the missing-linter case (D-03)."
    )


def test_adapter_region_cost_ledger_row_shape_tokens():
    region = _adapter_region()
    assert "implement | sonnet | task |" in region, (
        "Verify-loop region must document the D-08 7-column cost-ledger row shape "
        "(implement | sonnet | task | ...)."
    )


# ── (b) Core doc — contract present, adapter-specific tokens absent ───────


def test_core_doc_has_verify_fix_loop_section():
    text = _load(CORE_DOC)
    assert "## Automated verify-fix loop" in text, (
        "core/skills/implement.md must contain '## Automated verify-fix loop' (T-02)."
    )


def test_core_doc_verify_fix_loop_stays_portable():
    text = _load(CORE_DOC)
    for token in ("affected_tests.py", "__QUOIN_HOME__", "QUOIN_VERIFY_RETRIES"):
        assert token not in text, (
            f"core/skills/implement.md must NOT contain adapter-specific token {token!r} "
            "(T-02 core/adapter boundary — mirrors test_implement_core_doc_no_branch_hygiene_script_refs)."
        )


# ── (c) Codex procedure — verify/fix-loop token present ───────────────────


def test_codex_procedure_mentions_verify_fix_loop():
    text = _load(CODEX_PROCEDURE)
    assert "verify-fix loop" in text, (
        "Codex adapter procedure must mention a bounded verify-fix loop (T-03)."
    )
    assert "quoin/core/skills/implement.md" in text, (
        "Codex adapter procedure must reference the portable contract path (T-03)."
    )


# ── (d) CRIT-1 regression guard (round 3, strengthened) ────────────────────


def test_repo_root_is_the_literal_affected_tests_repo_root_argument():
    """CRIT-1 (round 3): the affected_tests.py invocation's --repo-root value
    must be the literal $REPO_ROOT variable, never $PROJECT_ROOT.

    Ties the guard to the resolved-variable VALUE (not merely flag
    presence) — the round-2 guard would have stayed green under the wrong
    --repo-root value (MIN-3).
    """
    region = _adapter_region()
    assert '--repo-root "$REPO_ROOT"' in region, (
        "Verify-loop region's affected_tests.py invocation must pass --repo-root \"$REPO_ROOT\" "
        "(D-09/CRIT-1 regression guard)."
    )
    assert '--repo-root "$PROJECT_ROOT"' not in region, (
        "Verify-loop region must NEVER anchor --repo-root to $PROJECT_ROOT — "
        "PROJECT_ROOT is not a git repo on this nested layout (D-09/CRIT-1 regression guard)."
    )


def test_touched_files_diff_anchored_to_repo_root():
    region = _adapter_region()
    assert 'git -C "$REPO_ROOT" diff --name-only HEAD' in region, (
        "Verify-loop region must compute the tracked touched-files diff via "
        'git -C "$REPO_ROOT" diff --name-only HEAD (D-07/D-09), not a bare unanchored git diff.'
    )
    assert 'git -C "$REPO_ROOT" diff --name-only --cached' in region, (
        "Verify-loop region must include the staged-files diff anchored to REPO_ROOT (D-07)."
    )


def test_no_bare_project_root_flag_for_verify_step():
    region = _adapter_region()
    assert "--project-root" not in region, (
        "Verify-loop region must invoke affected_tests.py in --files/--repo-root mode, "
        "never bare --project-root (D-07 CRIT-1 regression guard)."
    )


# ── (e) MAJ-1 regression guard (round 3) ───────────────────────────────────


def test_untracked_files_included_in_touched_set():
    region = _adapter_region()
    assert "ls-files --others --exclude-standard" in region, (
        "Verify-loop region must union in `git ls-files --others --exclude-standard` "
        "so a task that ADDS a new untracked file is not silently invisible to the loop (D-07/MAJ-1)."
    )


# ── (f) MIN-1 regression guard (round 3) ───────────────────────────────────


def test_empty_touched_set_skip_note_distinct_from_degrade_warning():
    region = _adapter_region()
    assert "no touched files detected; skipping" in region, (
        "Verify-loop region must contain an explicit empty-touched-set skip note, "
        "distinct from the degrade-warning wording (D-07/MIN-1)."
    )
    assert "degrading to current behavior" in region, (
        "Verify-loop region must contain the (separate) degrade-warning wording (D-02/D-03)."
    )
    # The two notes must be genuinely distinct wording, not the same phrase reused.
    assert "no touched files detected; skipping" != "degrading to current behavior", (
        "sanity: skip-note and degrade-warning wording must be distinct phrases (MIN-1)"
    )


# ── (g) MIN-2 regression guard (round 3) ───────────────────────────────────


def test_session_uuid_project_path_pinned_explicitly():
    region = _adapter_region()
    assert '--project-path "$PROJECT_ROOT"' in region, (
        "Verify-loop region must pin get_session_uuid.py --project-path explicitly to "
        '"$PROJECT_ROOT" rather than defaulting to $(pwd) (D-08/MIN-2 regression guard).'
    )
