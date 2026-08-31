"""Guard test: quoin/core/workflow/*.md must stay runtime-neutral.

Enforces the portability invariant (D-08) that core/workflow/ — the
runtime-neutral extraction of shared workflow semantics — never reintroduces
Claude-specific vocabulary or Claude Code slash-command syntax. Population is
an unconditional glob over core/workflow/*.md: no exemption set, so a file
added to that directory later is covered automatically without an edit here.

Distinct from the per-skill `*_adapter_pilot.py` tests: those cover
quoin/core/skills/<name>.md one skill at a time; this covers the shared
workflow docs (one entry per markdown file in the installer's registration
tuple, minus the non-markdown `skills.json` member) as one directory-wide
population.
"""

import re
from pathlib import Path

import quoin.installer as _inst

THIS_FILE = Path(__file__).resolve()
TESTS_DIR = THIS_FILE.parent
PKG_DIR = TESTS_DIR.parent.parent

CORE_WORKFLOW_DIR = PKG_DIR / "core" / "workflow"
CORE_SKILLS_DIR = PKG_DIR / "core" / "skills"

# Bare "Agent" is deliberately omitted: the domain noun collides with the
# "orchestrator" / "subagent" vocabulary core/workflow/ legitimately uses.
FORBIDDEN_TOKENS = ("~/.claude", "Haiku", "Sonnet", "Opus", "gh CLI")

EXPECTED_FILENAMES = set(_inst.CORE_WORKFLOW_FILES) - {"skills.json"}


def _slash_regex(name: str) -> re.Pattern:
    """Word-boundary regex for a slash-command token.

    Matches /name only when:
    - NOT preceded by an alphanumeric char or [-_] (avoids matching path
      components like 'skills/run.md')
    - NOT followed by an alphanumeric char or [-_] (avoids matching
      'run-2026-05-11.md')
    """
    return re.compile(
        r"(?<![a-zA-Z0-9_\-])"
        + re.escape("/" + name.lstrip("/"))
        + r"(?=[^a-zA-Z0-9_\-]|$)"
    )


def _core_workflow_files():
    return sorted(CORE_WORKFLOW_DIR.glob("*.md"))


def _skill_names():
    return sorted(p.stem for p in CORE_SKILLS_DIR.glob("*.md"))


def _scan_forbidden_tokens(path: Path) -> list:
    """Return (lineno, token, line) tuples for every FORBIDDEN_TOKENS hit in path."""
    hits = []
    with open(path, encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.rstrip("\n")
            for token in FORBIDDEN_TOKENS:
                if token in line:
                    hits.append((lineno, token, line))
    return hits


def test_core_workflow_population_matches_installer_registration():
    """Guards the population itself, not just the scan: a missing OR an
    unregistered file would silently break deployment rather than fail
    loudly. Anchored to the installer's own CORE_WORKFLOW_FILES tuple (the
    thing that actually gates deployment), not a test-local filename set —
    a set-equality guard here catches both directions: a file added to
    core/workflow/ without a matching installer row, and an installer row
    with no matching file on disk."""
    files = _core_workflow_files()
    names = {p.name for p in files}
    assert files, f"expected at least one *.md file under {CORE_WORKFLOW_DIR}"
    assert names == EXPECTED_FILENAMES, (
        f"core/workflow/*.md does not match quoin.installer.CORE_WORKFLOW_FILES "
        f"(minus skills.json): missing {sorted(EXPECTED_FILENAMES - names)}, "
        f"unregistered {sorted(names - EXPECTED_FILENAMES)} "
        f"(found: {sorted(names)})"
    )


def test_core_workflow_population_guard_catches_unrostered_file(tmp_path):
    """Mutation guard: an extra *.md file dropped into a copy of the real
    population, with no matching installer row, must fail the set-equality
    predicate the test above asserts — proving the guard actually bites
    rather than vacuously passing on today's population."""
    real_names = {p.name for p in _core_workflow_files()}
    assert real_names == EXPECTED_FILENAMES, "population already out of sync; fix that first"

    mutated_names = real_names | {"unrostered-doc.md"}
    assert mutated_names != EXPECTED_FILENAMES, (
        "expected an unrostered file to break the set-equality guard"
    )


def test_core_workflow_docs_have_no_forbidden_tokens():
    offenses = []
    for path in _core_workflow_files():
        for lineno, token, line in _scan_forbidden_tokens(path):
            offenses.append((path.name, lineno, token, line))
    assert offenses == [], (
        "Forbidden Claude-specific token(s) found in core/workflow/*.md:\n"
        + "\n".join(f"  {f}:{ln}: {tok!r} in {text!r}" for f, ln, tok, text in offenses)
    )


def test_core_workflow_docs_have_no_slash_command_forms_of_skill_names():
    """core/workflow/ docs must reference skills by bare name, never by
    Claude Code slash-command syntax (e.g. '/implement') — that syntax is
    adapter-owned UX, not a runtime-neutral concept."""
    skill_names = _skill_names()
    assert skill_names, f"expected skill docs under {CORE_SKILLS_DIR}"
    offenses = []
    for path in _core_workflow_files():
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for name in skill_names:
            regex = _slash_regex(name)
            for lineno, line in enumerate(lines, start=1):
                if regex.search(line):
                    offenses.append((path.name, lineno, name, line))
    assert offenses == [], (
        "Slash-command form of a skill name found in core/workflow/*.md:\n"
        + "\n".join(f"  {f}:{ln}: /{name} in {text!r}" for f, ln, name, text in offenses)
    )


def test_forbidden_token_scan_catches_injected_offense(tmp_path):
    """Mutation guard: an injected token in a copy of a real file must be
    detected by _scan_forbidden_tokens, proving the scan is not vacuously
    passing on the real population."""
    files = _core_workflow_files()
    assert files
    sample = files[0]
    mutated = tmp_path / sample.name
    mutated.write_text(
        sample.read_text(encoding="utf-8") + "\nOpus\n", encoding="utf-8"
    )

    hits = _scan_forbidden_tokens(mutated)
    assert hits, "expected the injected 'Opus' token to be detected by the scan"
    assert any(token == "Opus" for _, token, _ in hits)
