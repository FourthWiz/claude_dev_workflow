"""checkpoint-spec-harness: doc-lint + memory-deploy tests for checkpoint-spec.md.

checkpoint-spec.md (quoin/memory/checkpoint-spec.md) is a Tier-1 hand-edited
behavioral characterization of the /checkpoint subsystem. These tests guard
against the spec silently drifting from the real source it characterizes.

Anti-circularity discipline: every assertion below derives its "expected"
value from a REAL source file (hooks/_lib.sh, the deployed adapter SKILL.md,
thorough_plan_checkpoint.py) — never from checkpoint-spec.md's own prose. The
doc is always the thing being checked, never the oracle.
"""
from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path constants (parents[3] form — matches test_branch_recovery_recipe.py /
# test_install_branch_hygiene_deployed.py)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
PKG_DIR = REPO_ROOT / "quoin"  # quoin/quoin/ — the source package root

assert (PKG_DIR / "memory").is_dir(), (
    f"path math wrong: PKG_DIR/memory does not exist at {PKG_DIR / 'memory'}."
)

SPEC_FILE = PKG_DIR / "memory" / "checkpoint-spec.md"
LIB_SH = PKG_DIR / "hooks" / "_lib.sh"
CHECKPOINT_SKILL_MD = PKG_DIR / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"
THOROUGH_PLAN_CHECKPOINT_PY = PKG_DIR / "core" / "scripts" / "thorough_plan_checkpoint.py"
PYPROJECT_TOML = REPO_ROOT / "pyproject.toml"

EXPECTED_FORCE_INCLUDE_LINE = '"quoin/memory" = "src/quoin/data/memory"'


# ---------------------------------------------------------------------------
# importlib loader pattern (mirrors test_get_session_uuid.py::_load_core) —
# used so a future test needing to import thorough_plan_checkpoint.py's
# internals doesn't have to fight sys.path. Not strictly required by the
# assertions below (which only regex the .py source as text), but kept here
# per the task brief's instruction to use the loader idiom for any import
# from quoin/core/scripts/.
# ---------------------------------------------------------------------------


def _load_thorough_plan_checkpoint():
    spec = importlib.util.spec_from_file_location(
        "_test_thorough_plan_checkpoint", THOROUGH_PLAN_CHECKPOINT_PY
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {THOROUGH_PLAN_CHECKPOINT_PY}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Section-extraction helper for checkpoint-spec.md
# ---------------------------------------------------------------------------


def _extract_section(text: str, heading: str) -> str:
    """Return the body of an H2 section (from '## <heading>' up to the next
    '## ' heading, or end of file), NOT including the heading line itself."""
    pattern = re.compile(
        rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        raise AssertionError(
            f"checkpoint-spec.md has no '## {heading}' section (searched {SPEC_FILE})"
        )
    return m.group(1)


@pytest.fixture(scope="module")
def spec_text() -> str:
    assert SPEC_FILE.exists(), f"checkpoint-spec.md not found at {SPEC_FILE}"
    return SPEC_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Assertion 1 — Sentinel families: 9 globs from _lib.sh::sentinel_globs()
# must all appear verbatim in checkpoint-spec.md's "## Sentinel families"
# section.
# ---------------------------------------------------------------------------


def _extract_sentinel_globs_from_lib_sh() -> list[str]:
    """Parse hooks/_lib.sh's sentinel_globs() function body and extract the
    real glob strings, in order. Re-derived here independently of
    test_sentinel_family_parity.py — do not hardcode the count."""
    content = LIB_SH.read_text(encoding="utf-8")
    match = re.search(r"sentinel_globs\(\)\s*\{(.*?)\n\}", content, re.DOTALL)
    if not match:
        raise AssertionError(f"sentinel_globs() function not found in {LIB_SH}")
    body = match.group(1)
    globs: list[str] = []
    for line in body.splitlines():
        for g in re.findall(r"""['"]([a-z-]+\*\.[a-z]+)['"]""", line):
            if g not in globs:
                globs.append(g)
    return globs


def test_sentinel_globs_extracted_from_source_are_nonempty():
    """Sanity: the source-derived glob list must actually contain entries —
    otherwise assertion 1 below would be vacuously true."""
    globs = _extract_sentinel_globs_from_lib_sh()
    assert len(globs) > 0, f"Extracted zero sentinel globs from {LIB_SH} — extraction regex broken?"


def test_sentinel_families_section_contains_every_lib_sh_glob(spec_text):
    """Every glob emitted by hooks/_lib.sh::sentinel_globs() (source of truth,
    re-derived here — NOT assumed to be 9) must appear verbatim in
    checkpoint-spec.md's '## Sentinel families' table."""
    globs = _extract_sentinel_globs_from_lib_sh()
    section = _extract_section(spec_text, "Sentinel families")

    missing = [g for g in globs if g not in section]
    assert not missing, (
        f"checkpoint-spec.md's '## Sentinel families' section is missing these "
        f"glob(s) present in hooks/_lib.sh::sentinel_globs(): {missing}"
    )


# ---------------------------------------------------------------------------
# Assertion 2 — Picker tiers: literal '**Tier N — ...**' headings in the
# DEPLOYED adapter SKILL.md must all be enumerated in checkpoint-spec.md's
# "## Picker tiers" section.
# ---------------------------------------------------------------------------


def _extract_tier_headings_from_skill_md() -> list[str]:
    """Parse the deployed adapter SKILL.md for '**Tier N — <title>**'-style
    headings and return the literal 'Tier N — <title>' strings (trailing
    colon, if any, stripped) in the order they appear."""
    content = CHECKPOINT_SKILL_MD.read_text(encoding="utf-8")
    tiers: list[str] = []
    for m in re.finditer(r"\*\*Tier (\d+) — ([^*]+?)\*\*", content):
        num, title = m.group(1), m.group(2)
        title = title.rstrip(":").strip()
        heading = f"Tier {num} — {title}"
        if heading not in tiers:
            tiers.append(heading)
    return tiers


def test_tier_headings_extracted_from_skill_md_are_nonempty():
    """Sanity: extraction must actually find tier headings in the deployed
    SKILL.md, otherwise the drift assertion below is vacuous."""
    tiers = _extract_tier_headings_from_skill_md()
    assert len(tiers) > 0, (
        f"Extracted zero '**Tier N —**' headings from {CHECKPOINT_SKILL_MD} — "
        "extraction regex broken, or the deployed SKILL.md no longer uses this heading style?"
    )


def test_picker_tiers_section_enumerates_same_tiers_as_skill_md(spec_text):
    """checkpoint-spec.md's '## Picker tiers' section must name the same set
    of tier numbers/titles as the DEPLOYED adapter SKILL.md (source of
    truth) — not the reverse."""
    skill_tiers = _extract_tier_headings_from_skill_md()
    section = _extract_section(spec_text, "Picker tiers")

    missing = [t for t in skill_tiers if t not in section]
    assert not missing, (
        f"checkpoint-spec.md's '## Picker tiers' section does not enumerate these tier "
        f"heading(s) found in the deployed SKILL.md ({CHECKPOINT_SKILL_MD}): {missing}"
    )


# ---------------------------------------------------------------------------
# Assertion 3 — Checkpoints writers: the literal filename prefix used by
# thorough_plan_checkpoint.py must be named in checkpoint-spec.md's
# "## Checkpoints writers" section.
# ---------------------------------------------------------------------------


def _extract_thorough_plan_filename_prefix() -> str:
    """Parse thorough_plan_checkpoint.py's source for the f-string filename
    assignment (`fname = f"thorough-plan-progress-{sid}.md"`) and return the
    literal prefix before the first '{' placeholder."""
    content = THOROUGH_PLAN_CHECKPOINT_PY.read_text(encoding="utf-8")
    m = re.search(r'fname\s*=\s*f"([^"]+)"', content)
    if not m:
        raise AssertionError(
            f"Could not find `fname = f\"...\"` assignment in {THOROUGH_PLAN_CHECKPOINT_PY}"
        )
    fstring_body = m.group(1)
    prefix_match = re.match(r"^([^{]+)\{", fstring_body)
    if not prefix_match:
        raise AssertionError(
            f"Could not extract a literal prefix (text before '{{') from f-string body "
            f"{fstring_body!r} in {THOROUGH_PLAN_CHECKPOINT_PY}"
        )
    return prefix_match.group(1)


def test_thorough_plan_filename_prefix_extracted_is_nonempty():
    """Sanity: the extracted prefix must be non-trivial (not just an empty
    string), otherwise the drift assertion below is vacuous."""
    prefix = _extract_thorough_plan_filename_prefix()
    assert prefix and len(prefix) > 5, (
        f"Extracted an implausibly short/empty prefix {prefix!r} from "
        f"{THOROUGH_PLAN_CHECKPOINT_PY} — extraction regex broken?"
    )


def test_checkpoints_writers_section_names_thorough_plan_prefix(spec_text):
    """checkpoint-spec.md's '## Checkpoints writers' section must name the
    exact filename prefix used by thorough_plan_checkpoint.py (source of
    truth), not a paraphrase or a different string."""
    prefix = _extract_thorough_plan_filename_prefix()
    section = _extract_section(spec_text, "Checkpoints writers")

    assert prefix in section, (
        f"checkpoint-spec.md's '## Checkpoints writers' section does not contain the "
        f"literal filename prefix {prefix!r} extracted from "
        f"{THOROUGH_PLAN_CHECKPOINT_PY}."
    )


# ---------------------------------------------------------------------------
# Memory-deploy assertions (mirrors test_branch_recovery_recipe.py pattern)
# ---------------------------------------------------------------------------


def test_checkpoint_spec_file_exists():
    """checkpoint-spec.md must exist in quoin/memory/."""
    assert SPEC_FILE.exists(), f"Expected checkpoint-spec.md at {SPEC_FILE} — file not found."


def test_checkpoint_spec_in_tier1_memory_files():
    """checkpoint-spec.md must appear in TIER1_MEMORY_FILES in installer.py."""
    from quoin.installer import TIER1_MEMORY_FILES  # noqa: PLC0415

    assert "checkpoint-spec.md" in TIER1_MEMORY_FILES, (
        "'checkpoint-spec.md' not found in TIER1_MEMORY_FILES in src/quoin/installer.py. "
        "Add it to the tuple so install.sh deploys it to ~/.claude/memory/checkpoint-spec.md."
    )


def test_pyproject_force_includes_memory_directory():
    """pyproject.toml must map the whole quoin/memory/ directory into the
    wheel (the directory force-include, not a per-file line) — this is what
    ships checkpoint-spec.md, given the source file exists in quoin/memory/."""
    assert PYPROJECT_TOML.exists(), f"pyproject.toml not found at {PYPROJECT_TOML}"
    text = PYPROJECT_TOML.read_text(encoding="utf-8")
    assert EXPECTED_FORCE_INCLUDE_LINE in text, (
        f"pyproject.toml must contain the directory force-include line:\n"
        f"  {EXPECTED_FORCE_INCLUDE_LINE}\n"
        "Without it, no memory files ship and quoin install aborts."
    )
    assert SPEC_FILE.exists(), (
        f"checkpoint-spec.md source missing at {SPEC_FILE}; the directory force-include "
        "can only ship a file that exists in quoin/memory/."
    )
