"""
T-02 CI gate: Preamble freshness tests.

Parametrized over the 7 spawn targets:
  - Presence test: quoin/skills/<skill>/preamble.md exists.
  - Freshness test: source_hashes in frontmatter match current git hash-object of each source.
  - Size-budget test: each preamble is < 6144 bytes.
  - Frontmatter sanity: each preamble starts with '---\\n'.

Run via:
  pytest quoin/dev/tests/test_preamble_freshness.py
"""

import pathlib
import subprocess
import sys

import pytest
import yaml

# Locate repo root and quoin dir
HERE = pathlib.Path(__file__).resolve().parent
QUOIN_DIR = HERE.parent.parent  # quoin/dev/tests/ -> quoin/dev/ -> quoin/
REPO_ROOT = QUOIN_DIR.parent    # quoin/ -> project root

# Import SPAWN_TARGETS from the builder (single source of truth)
sys.path.insert(0, str(QUOIN_DIR / "scripts"))
from build_preambles import SPAWN_TARGETS  # noqa: E402

PREAMBLE_SIZE_BUDGET = 6144


def _preamble_path(skill: str) -> pathlib.Path:
    return QUOIN_DIR / "skills" / skill / "preamble.md"


def _git_hash_object(path: pathlib.Path) -> str:
    """Return git hash-object SHA for a file (working tree, not index)."""
    result = subprocess.run(
        ["git", "hash-object", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _parse_frontmatter(content: str) -> dict:
    """Parse YAML frontmatter from a preamble.md file."""
    if not content.startswith("---\n"):
        raise ValueError("Preamble does not start with '---\\n'")
    end = content.index("\n---\n", 4)
    fm_text = content[4:end]
    return yaml.safe_load(fm_text)


class TestPresence:
    """Each of the 7 spawn targets must have a preamble.md on disk."""

    @pytest.mark.parametrize("skill", list(SPAWN_TARGETS.keys()))
    def test_preamble_exists(self, skill):
        p = _preamble_path(skill)
        assert p.exists(), (
            f"Preamble for {skill} is missing — "
            f"run python3 quoin/scripts/build_preambles.py"
        )


class TestFreshness:
    """Each preamble's source_hashes must match current git hash-object of the source files."""

    @pytest.mark.parametrize("skill", list(SPAWN_TARGETS.keys()))
    def test_preamble_fresh(self, skill):
        p = _preamble_path(skill)
        if not p.exists():
            pytest.skip(f"Preamble for {skill} not present — presence test will catch this")

        content = p.read_text(encoding="utf-8")

        # Frontmatter sanity
        assert content.startswith("---\n"), (
            f"Preamble for {skill} does not start with '---\\n' (malformed frontmatter)"
        )

        fm = _parse_frontmatter(content)
        source_hashes = fm.get("source_hashes") or {}

        kind = SPAWN_TARGETS[skill]
        # Gate stub: empty source_hashes is vacuously true freshness
        if kind == "stub" or not source_hashes:
            return

        for rel_path, expected_sha in source_hashes.items():
            abs_path = REPO_ROOT / rel_path
            assert abs_path.exists(), (
                f"Preamble for {skill} references source {rel_path} which does not exist"
            )
            current_sha = _git_hash_object(abs_path)
            assert current_sha == expected_sha, (
                f"Preamble for {skill} is stale: source {rel_path} changed "
                f"(preamble has {expected_sha}, current is {current_sha}). "
                f"Run: bash install.sh (or python3 quoin/scripts/build_preambles.py)"
            )


class TestSizeBudget:
    """Each preamble must be under 6144 bytes (size-budget regression guard)."""

    @pytest.mark.parametrize("skill", list(SPAWN_TARGETS.keys()))
    def test_preamble_size(self, skill):
        p = _preamble_path(skill)
        if not p.exists():
            pytest.skip(f"Preamble for {skill} not present — presence test will catch this")

        size = len(p.read_bytes())
        assert size < PREAMBLE_SIZE_BUDGET, (
            f"Preamble for {skill} is {size} bytes, exceeds budget of {PREAMBLE_SIZE_BUDGET} bytes. "
            f"Trim the §3 slice or reduce glossary content."
        )
