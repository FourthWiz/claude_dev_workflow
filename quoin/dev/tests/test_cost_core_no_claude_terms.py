"""Guard test: quoin/core/ cost files must not contain Claude-specific vocabulary.

Enforces the runtime-neutrality invariant for cost_event.py and cost-ledger.md
so future phases cannot silently drag Claude vocabulary into quoin/core/.

The guard excludes the '## Claude-Specific Capture' section of cost-ledger.md
(that section is explicitly allowed to reference ccusage and JSONL).
"""

import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Module-scope constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]

WORDLIST = [
    "ccusage",
    "jsonl",
    "claude-opus",
    "claude-sonnet",
    "claude-haiku",
    "npx ccusage",
]

EXCLUDED_SECTION = "## Claude-Specific Capture"

SCANNED_FILES = [
    REPO_ROOT / "quoin" / "core" / "scripts" / "cost_event.py",
    REPO_ROOT / "quoin" / "core" / "workflow" / "cost-ledger.md",
]

# Adapter-import terms whose presence in cost_event.py would mean the module
# is co-importing a Claude-adapter-owned helper.
IMPORT_BLACKLIST = [
    "cost_from_jsonl",
    "session_age_guard",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _scan_outside_excluded(path: Path) -> list:
    """Scan `path` for WORDLIST terms, skipping lines at/after EXCLUDED_SECTION.

    Returns a list of (lineno, matched_word, full_line) tuples for every hit
    found before the excluded section. Matching is case-insensitive.
    """
    hits = []
    in_excluded = False

    with open(path, encoding="utf-8") as fh:
        for lineno, raw_line in enumerate(fh, start=1):
            line = raw_line.rstrip("\n")
            if line.strip() == EXCLUDED_SECTION:
                in_excluded = True
            if in_excluded:
                continue
            for word in WORDLIST:
                if re.search(re.escape(word), line, re.IGNORECASE):
                    hits.append((lineno, word, line))
    return hits


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cost_event_py_has_no_claude_terms():
    """cost_event.py must contain no Claude-specific vocabulary."""
    path = REPO_ROOT / "quoin" / "core" / "scripts" / "cost_event.py"
    hits = _scan_outside_excluded(path)
    assert hits == [], (
        f"Claude vocabulary found in {path}:\n"
        + "\n".join(f"  line {ln}: {word!r} in {text!r}" for ln, word, text in hits)
    )


def test_cost_ledger_md_has_no_claude_terms_outside_excluded():
    """cost-ledger.md must contain no Claude vocabulary outside ## Claude-Specific Capture."""
    path = REPO_ROOT / "quoin" / "core" / "workflow" / "cost-ledger.md"
    hits = _scan_outside_excluded(path)
    assert hits == [], (
        f"Claude vocabulary found outside excluded section in {path}:\n"
        + "\n".join(f"  line {ln}: {word!r} in {text!r}" for ln, word, text in hits)
    )


def test_cost_ledger_md_excluded_section_exists():
    """The '## Claude-Specific Capture' heading must be present in cost-ledger.md.

    Without this heading, _scan_outside_excluded would never enter excluded mode
    and the entire file (including the Claude-vocabulary section) would be scanned,
    causing false failures. This test guards against the section being silently removed.
    """
    path = REPO_ROOT / "quoin" / "core" / "workflow" / "cost-ledger.md"
    with open(path, encoding="utf-8") as fh:
        lines = fh.readlines()
    heading_lines = [ln.strip() for ln in lines]
    assert EXCLUDED_SECTION in heading_lines, (
        f"Required heading '{EXCLUDED_SECTION}' not found in {path}. "
        "The exclusion guard would fail silently without it."
    )


def test_cost_event_py_has_no_adapter_imports():
    """cost_event.py must not import from Claude-adapter-owned modules.

    Checks for bare substrings that would appear in any import form:
        import cost_from_jsonl
        from cost_from_jsonl import ...
        from quoin.scripts.cost_from_jsonl import ...
    This enforces the module docstring's runtime-neutrality promise programmatically.
    """
    path = REPO_ROOT / "quoin" / "core" / "scripts" / "cost_event.py"
    with open(path, encoding="utf-8") as fh:
        source = fh.read()
    for term in IMPORT_BLACKLIST:
        assert term not in source, (
            f"Adapter-owned import term '{term}' found in {path}. "
            "cost_event.py must not import from Claude-adapter-owned modules."
        )
