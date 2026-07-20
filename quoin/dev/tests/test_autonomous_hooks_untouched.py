"""Hooks-untouched guard for autonomous mode — IVG-153, T-20(b).

Autonomous mode (`--autonomous` on `/run`) cooperates with the existing
hooks-driven session-lifecycle machinery (context-utilization advisories,
sentinel sweeps, worktree isolation) — it never edits it. This test asserts
that claim two ways:

  1. No file under `quoin/hooks/**` was touched by the autonomous work: none
     of them mention "autonomous" at all (the autonomous plan's scope is
     entirely SKILL.md/scripts/memory files — the hooks dir is a read-only
     dependency, sourced via `. __QUOIN_HOME__/hooks/_lib.sh`, never written).
  2. The tunable `QUOIN_*_BPS` / threshold constants in `hooks/_lib.sh`
     (`read_constants()`) are byte-identical to their known pre-autonomous
     default values — a content check, not a hash, so a future intentional
     tuning of one constant fails loudly with a clear diff instead of a
     silent drift.

Also asserts no autonomous-related skill/script text instructs a WRITE
(as opposed to a read/source) against a path under `hooks/`.

FAILS-without-the-guard: if a future autonomous-mode change edited
`hooks/_lib.sh`'s thresholds (e.g. to silence advisories during unattended
runs instead of cooperating with them), this test would catch the changed
constant value or the new "autonomous" mention in the hooks dir.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
PKG_DIR = TESTS_DIR.parent.parent  # quoin/quoin/
HOOKS_DIR = PKG_DIR / "hooks"
LIB_SH = HOOKS_DIR / "_lib.sh"
ADAPTER_SKILLS_DIR = PKG_DIR / "adapters" / "claude" / "skills"
SCRIPTS_DIR = PKG_DIR / "scripts"
CORE_SKILLS_DIR = PKG_DIR / "core" / "skills"
MEMORY_DIR = PKG_DIR / "memory"

# Known pre-autonomous default values for hooks/_lib.sh:read_constants().
# Sourced from the read_constants() body — verified against source 2026-07-20,
# unchanged by this branch (git diff of quoin/hooks/ vs. the branch base is
# empty as of this writing).
EXPECTED_CONSTANTS = {
    "QUOIN_BYTES_PER_TOKEN": "8.0",
    "QUOIN_EFFECTIVE_CONTEXT_LIMIT": "150000",
    "QUOIN_STOP_BPS": "7000",
    "QUOIN_BLOCK_BPS": "9500",
    "QUOIN_COMPACT_FIRST_BPS": "9000",
    "QUOIN_PANIC_BPS": "10000",
}


@pytest.fixture(scope="module")
def lib_sh_text() -> str:
    assert LIB_SH.exists(), f"hooks/_lib.sh not found at {LIB_SH}"
    return LIB_SH.read_text(encoding="utf-8")


def test_hooks_dir_has_expected_files() -> None:
    """Sanity: the hooks dir exists and has the known 7-script roster (no new
    hook script was added by autonomous work, no existing one was removed).
    Non-script housekeeping files (e.g. `.keep`) are ignored."""
    assert HOOKS_DIR.is_dir()
    names = sorted(p.name for p in HOOKS_DIR.glob("*.sh"))
    expected = sorted(
        [
            "_lib.sh",
            "postcompact.sh",
            "precompact.sh",
            "sessionend.sh",
            "sessionstart.sh",
            "userpromptsubmit.sh",
            "worktreecreate.sh",
        ]
    )
    assert names == expected, f"hooks/ script roster changed: {names}"


def test_no_hook_file_mentions_autonomous() -> None:
    """No hook script was edited to add autonomous-specific logic — the
    autonomous plan's entire scope is SKILL.md/scripts/memory files."""
    offenders = []
    for path in sorted(HOOKS_DIR.glob("*.sh")):
        text = path.read_text(encoding="utf-8")
        if "autonomous" in text.lower():
            offenders.append(path.name)
    assert not offenders, (
        f"hooks file(s) mention 'autonomous' — hooks must never be edited by "
        f"autonomous-mode work: {offenders}"
    )


def test_bps_threshold_constants_unchanged(lib_sh_text: str) -> None:
    """Every QUOIN_*_BPS / threshold constant in read_constants() is
    byte-identical to its known pre-autonomous default."""
    text = lib_sh_text
    for name, expected_default in EXPECTED_CONSTANTS.items():
        # Constants are consumed as `<VAR>=${QUOIN_FOO_BAR:-<default>}`, e.g.
        # `BPT=${QUOIN_BYTES_PER_TOKEN:-8.0}` — the QUOIN_* name is the env-var
        # override token inside `${...:-...}`, not the local shell variable.
        pattern = re.compile(r"\$\{" + re.escape(name) + r":-([^}]+)\}")
        match = pattern.search(text)
        assert match, f"constant {name} not found (or its shape changed) in hooks/_lib.sh"
        actual_default = match.group(1)
        assert actual_default == expected_default, (
            f"hooks/_lib.sh constant {name} default changed: "
            f"expected {expected_default!r}, found {actual_default!r} — "
            "autonomous mode must never modify hook thresholds"
        )


def test_read_constants_function_present_and_unmodified_shape(lib_sh_text: str) -> None:
    """The read_constants() function itself still exists with its documented
    export line — a coarse structural check that the function wasn't
    restructured (e.g. to bypass env-var overrides) by autonomous work."""
    text = lib_sh_text
    assert "read_constants() {" in text
    assert (
        "export BPT LIMIT STOP_BPS BLOCK_BPS STALE_DAYS SESSIONSTART_SWEEP_DAYS "
        "COMPACT_FIRST_BPS PANIC_BPS DISCOVERY_STALE_DAYS SERENA_STALE_DAYS" in text
    )


# ─── No autonomous-tagged text co-occurs with a hooks/ reference ────────────

# Files in scope for the autonomous plan (the 15-skill transitive spawn set
# plus the generator scripts and memory doc T-20 is meant to guard).
AUTONOMOUS_TAGGED_ROOTS = [ADAPTER_SKILLS_DIR, SCRIPTS_DIR, CORE_SKILLS_DIR, MEMORY_DIR]


def test_no_autonomous_line_references_hooks_dir() -> None:
    """Line-level co-occurrence check: no line that mentions "autonomous"
    (the sentinel, the state flag, or prose describing autonomous behavior)
    also mentions `hooks/` anywhere in the autonomous-tagged surface. This is
    deliberately coarse (co-occurrence, not just writes) — the autonomous
    plan's entire scope is SKILL.md/scripts/memory text, and it should never
    even DISCUSS touching hooks/, let alone write to it. Pre-existing hooks/
    references in these files (e.g. `. __QUOIN_HOME__/hooks/_lib.sh` sourcing
    in checkpoint/cleanup/implement/end_of_task, or hooks-table.md doc links)
    are unrelated to autonomous mode and never share a line with
    "autonomous" — verified true as of this writing."""
    offenders: list[str] = []
    for root in AUTONOMOUS_TAGGED_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")) + sorted(root.rglob("*.py")):
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if "autonomous" in line.lower() and "hooks/" in line:
                    offenders.append(f"{path.relative_to(PKG_DIR)}:{lineno}: {line.strip()!r}")
    assert not offenders, (
        f"found autonomous-tagged line(s) that also reference hooks/ — "
        f"autonomous mode must never touch the hooks dir: {offenders}"
    )


def test_hooks_dir_untouched_git_diff_if_available() -> None:
    """Best-effort structural corroboration: if this checkout is a git repo
    with a resolvable merge-base against origin/main or main, confirm
    quoin/hooks/ has zero diff vs. that base. Skips (does not fail) when git
    or a base ref is unavailable — the content-check tests above are the
    primary, environment-independent guard."""
    import subprocess

    repo_root = PKG_DIR.parent  # quoin/ (git root)
    try:
        base = None
        for ref in ("origin/main", "main", "origin/master", "master"):
            probe = subprocess.run(
                ["git", "merge-base", "HEAD", ref],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0 and probe.stdout.strip():
                base = probe.stdout.strip()
                break
        if base is None:
            pytest.skip("no resolvable base ref for git diff corroboration")

        diff = subprocess.run(
            ["git", "diff", "--stat", base, "HEAD", "--", "quoin/hooks/"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if diff.returncode != 0:
            pytest.skip("git diff failed; skipping best-effort corroboration")
        assert diff.stdout.strip() == "", (
            f"quoin/hooks/ has uncommitted-since-base changes on this branch:\n{diff.stdout}"
        )
    except FileNotFoundError:
        pytest.skip("git binary not available")
