"""
test_audit_corpus_coverage.py — Unit tests for audit_corpus_coverage.py (T-13).

Tests the script against 3 synthetic fixtures:
  1. all-known shapes (residual=0, exit=0)
  2. one unknown shape (residual=1, exit=1)
  3. empty file (residual=0, exit=0)
"""

import os
import subprocess
import sys
import tempfile

import pytest

SCRIPT = os.path.join(
    os.path.dirname(__file__), '..', 'audit_corpus_coverage.py'
)
PYTHON = sys.executable

# ── Fixture content helpers ────────────────────────────────────────────────────

_ALL_KNOWN_SHAPES = """\
---
round: 1
date: 2026-01-01
---

## Issues

### Critical (blocks implementation)
- **[CRIT-1] Shape A bracket form title**
  - What: something
  - Suggestion: fix it

- **CRIT-2 — Shape B no-bracket em-dash title**
  - What: something

### Major (significant gap)
- **Issue C1 — Shape C issue-prefix title**
  - What: something

- **MAJOR — Shape D full-word severity title.**
  - What: something
"""

_ONE_UNKNOWN_SHAPE = """\
## Issues

### Critical (blocks implementation)
- **[CRIT-1] Shape A bullet**
  - What: something

- **unrecognized plain bullet without severity marker**
  - What: something
"""

_EMPTY_FILE = ""


# ── Helper: run audit_corpus_coverage against a tmpdir with given fixtures ─────

def _run_audit(fixtures):  # type: (dict) -> subprocess.CompletedProcess
    """
    Create a temp training dir with the given fixtures (filename → content),
    invoke audit_corpus_coverage.py, and return the CompletedProcess.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        for fname, content in fixtures.items():
            path = os.path.join(tmpdir, fname)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)
        result = subprocess.run(
            [PYTHON, SCRIPT, '--training-dir', tmpdir],
            capture_output=True,
            text=True,
        )
    return result


# ── Tests ──────────────────────────────────────────────────────────────────────

def test_all_known_shapes_residual_zero():
    """All-known shapes fixture: residual=0, exit=0."""
    result = _run_audit({'all-known.md': _ALL_KNOWN_SHAPES})
    assert result.returncode == 0, (
        f'Expected exit 0 but got {result.returncode}.\n'
        f'stdout: {result.stdout}\nstderr: {result.stderr}'
    )
    assert result.stdout.strip() == '', (
        f'Expected empty stdout but got:\n{result.stdout}'
    )


def test_one_unknown_shape_residual_one():
    """One unknown shape fixture: residual=1, exit=1, output has that bullet."""
    result = _run_audit({'unknown-shape.md': _ONE_UNKNOWN_SHAPE})
    assert result.returncode == 1, (
        f'Expected exit 1 but got {result.returncode}.\n'
        f'stdout: {result.stdout}\nstderr: {result.stderr}'
    )
    assert 'unrecognized plain bullet' in result.stdout, (
        f'Expected residual bullet in stdout but got:\n{result.stdout}'
    )
    # Should be exactly one residual line
    lines = [l for l in result.stdout.strip().splitlines() if l]
    assert len(lines) == 1, f'Expected 1 residual line, got {len(lines)}: {lines}'


def test_empty_file_residual_zero():
    """Empty file fixture: residual=0, exit=0."""
    result = _run_audit({'empty.md': _EMPTY_FILE})
    assert result.returncode == 0, (
        f'Expected exit 0 but got {result.returncode}.\n'
        f'stdout: {result.stdout}\nstderr: {result.stderr}'
    )
    assert result.stdout.strip() == '', (
        f'Expected empty stdout but got:\n{result.stdout}'
    )


def test_output_format_filename_lineno():
    """Residual output has form: <filename>:<lineno>: <text>."""
    result = _run_audit({'unknown-shape.md': _ONE_UNKNOWN_SHAPE})
    assert result.returncode == 1
    line = result.stdout.strip().splitlines()[0]
    parts = line.split(':', 2)
    assert len(parts) == 3, f'Expected <file>:<line>:<text> but got: {line!r}'
    assert parts[0] == 'unknown-shape.md', f'Wrong filename in output: {parts[0]!r}'
    assert parts[1].isdigit(), f'Line number not a digit: {parts[1]!r}'
