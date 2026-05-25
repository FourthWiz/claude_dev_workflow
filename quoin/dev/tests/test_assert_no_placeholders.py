"""Tests for installer.assert_no_placeholders (T-06 positive-allowlist fix)."""
import pathlib

import pytest

from quoin.installer import assert_no_placeholders, _QUOIN_DEPLOYED_SUBDIRS


def _write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_finds_violation_in_deployed_subdir(tmp_path):
    _write(tmp_path / "skills" / "foo" / "SKILL.md", "path: __QUOIN_HOME__/skills/foo")
    violations = assert_no_placeholders(tmp_path)
    assert len(violations) == 1
    assert "SKILL.md:1" in violations[0]


def test_finds_violation_in_root_file(tmp_path):
    _write(tmp_path / "CLAUDE.md", "see __QUOIN_HOME__/memory/lifecycle-guide.md\n")
    violations = assert_no_placeholders(tmp_path)
    assert len(violations) == 1
    assert "CLAUDE.md:1" in violations[0]


def test_ignores_non_deployed_subdir(tmp_path):
    _write(
        tmp_path / "projects" / "somehash" / "tool-results" / "abc.txt",
        "contains __QUOIN_HOME__ from a cached source read",
    )
    violations = assert_no_placeholders(tmp_path)
    assert violations == []


def test_ignores_non_matching_extension(tmp_path):
    # .pyc is not in check_exts — should be ignored even if in a deployed subdir
    p = tmp_path / "skills" / "foo.pyc"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"__QUOIN_HOME__")
    violations = assert_no_placeholders(tmp_path)
    assert violations == []


def test_clean_install_no_violations(tmp_path):
    _write(tmp_path / "CLAUDE.md", "# Rules\nAll paths are absolute.\n")
    _write(tmp_path / "skills" / "plan" / "SKILL.md", "# Plan\n")
    _write(tmp_path / "memory" / "glossary.md", "# Glossary\n")
    violations = assert_no_placeholders(tmp_path)
    assert violations == []


def test_all_deployed_subdirs_scanned(tmp_path):
    for subdir in _QUOIN_DEPLOYED_SUBDIRS:
        _write(
            tmp_path / subdir / "test.md",
            f"reference: __QUOIN_HOME__/{subdir}/something\n",
        )
    violations = assert_no_placeholders(tmp_path)
    assert len(violations) == len(_QUOIN_DEPLOYED_SUBDIRS)
