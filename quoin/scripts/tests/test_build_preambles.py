"""
Unit tests for build_preambles.py.

Tests use a tmpdir-rooted virtual project layout to avoid touching the real quoin/skills/ tree.
"""

import os
import pathlib
import sys
import time

import pytest

# Make the scripts/ dir importable
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SCRIPT_DIR))

import build_preambles  # noqa: E402


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_virtual_project(tmp: pathlib.Path, fk_content: str = None, gl_content: str = None) -> pathlib.Path:
    """
    Set up a minimal virtual quoin/ tree under tmp.
    Returns the quoin_dir (tmp/quoin/).
    """
    quoin_dir = tmp / "quoin"
    memory_dir = quoin_dir / "memory"
    memory_dir.mkdir(parents=True)

    # Default format-kit.md: 250 lines, line 189 starts the §3 H2
    if fk_content is None:
        lines = []
        for i in range(1, 189):
            lines.append(f"line {i}\n")
        # Lines 189-207: the §3 slice (19 lines)
        lines.append("## §3 Pick rules for ambiguous content (the hard cases)\n")  # 189
        lines.append("Three rules...\n")  # 190
        lines.append("1. Rule one\n")  # 191
        lines.append("2. Rule two\n")  # 192
        lines.append("3. Rule three\n")  # 193
        for i in range(194, 207):
            lines.append(f"slice line {i}\n")
        lines.append("---\n")  # 207
        for i in range(208, 251):
            lines.append(f"post line {i}\n")
        fk_content = "".join(lines)

    if gl_content is None:
        gl_content = "# Glossary\nA: annotation\nB: body\n"

    (memory_dir / "format-kit.md").write_text(fk_content, encoding="utf-8")
    (memory_dir / "glossary.md").write_text(gl_content, encoding="utf-8")

    # Create skills dirs for all targets
    for skill in build_preambles.SPAWN_TARGETS:
        (quoin_dir / "skills" / skill).mkdir(parents=True, exist_ok=True)

    return quoin_dir


def _invoke_build(quoin_dir: pathlib.Path, dry_run: bool = False, check: bool = False):
    """
    Direct Python call to build_preambles.main() with QUOIN_DIR monkeypatched.
    Returns (exit_code, stdout, stderr) captured.
    """
    import io
    from contextlib import redirect_stdout, redirect_stderr
    import importlib

    # Monkeypatch module globals
    orig_quoin_dir = build_preambles.QUOIN_DIR
    orig_source_fk = build_preambles.SOURCE_FORMAT_KIT
    orig_source_gl = build_preambles.SOURCE_GLOSSARY

    build_preambles.QUOIN_DIR = quoin_dir
    build_preambles.SOURCE_FORMAT_KIT = quoin_dir / "memory" / "format-kit.md"
    build_preambles.SOURCE_GLOSSARY = quoin_dir / "memory" / "glossary.md"

    # Build a fake sys.argv
    argv_backup = sys.argv[:]
    sys.argv = ["build_preambles.py"]
    if dry_run:
        sys.argv.append("--dry-run")
    if check:
        sys.argv.append("--check")

    stdout_cap = io.StringIO()
    stderr_cap = io.StringIO()
    exit_code = None

    try:
        with redirect_stdout(stdout_cap), redirect_stderr(stderr_cap):
            exit_code = build_preambles.main()
    except SystemExit as e:
        exit_code = e.code
    finally:
        sys.argv = argv_backup
        build_preambles.QUOIN_DIR = orig_quoin_dir
        build_preambles.SOURCE_FORMAT_KIT = orig_source_fk
        build_preambles.SOURCE_GLOSSARY = orig_source_gl

    return exit_code, stdout_cap.getvalue(), stderr_cap.getvalue()


# ── tests ─────────────────────────────────────────────────────────────────────

class TestDeterminism:
    """Two consecutive runs produce byte-identical output."""

    def test_two_runs_byte_identical(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)

        def build_and_read():
            code, _, _ = _invoke_build(quoin_dir)
            assert code == 0, "builder should succeed"
            result = {}
            for skill in build_preambles.SPAWN_TARGETS:
                p = quoin_dir / "skills" / skill / "preamble.md"
                result[skill] = p.read_text(encoding="utf-8")
            return result

        run1 = build_and_read()
        # Advance wall-clock so any timestamp-derived field would differ across runs
        time.sleep(0.01)
        run2 = build_and_read()

        for skill in build_preambles.SPAWN_TARGETS:
            assert run1[skill] == run2[skill], (
                f"Preamble for {skill} differs between runs"
            )


class TestSizeBudget:
    """Oversized full preamble triggers exit 3."""

    def test_oversized_preamble_exits_3(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)
        # Make glossary huge (>6144 bytes)
        big_glossary = "X: " + "x" * 7000 + "\n"
        (quoin_dir / "memory" / "glossary.md").write_text(big_glossary, encoding="utf-8")

        code, out, err = _invoke_build(quoin_dir)
        assert code == 3, f"Expected exit 3 for oversize, got {code}; err={err}"
        assert "PREAMBLE OVERSIZE" in err


class TestMissingSource:
    """Missing source file triggers exit 4."""

    def test_missing_format_kit_exits_4(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)
        (quoin_dir / "memory" / "format-kit.md").unlink()

        code, out, err = _invoke_build(quoin_dir)
        assert code == 4, f"Expected exit 4 for missing source, got {code}; err={err}"
        assert "MISSING SOURCE" in err

    def test_missing_glossary_exits_4(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)
        (quoin_dir / "memory" / "glossary.md").unlink()

        code, out, err = _invoke_build(quoin_dir)
        assert code == 4, f"Expected exit 4 for missing source, got {code}; err={err}"
        assert "MISSING SOURCE" in err


class TestEmptySpawnTargets:
    """Empty SPAWN_TARGETS triggers exit 5."""

    def test_empty_targets_exits_5(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)
        orig = build_preambles.SPAWN_TARGETS.copy()
        build_preambles.SPAWN_TARGETS.clear()
        try:
            code, out, err = _invoke_build(quoin_dir)
            assert code == 5, f"Expected exit 5 for empty targets, got {code}"
        finally:
            build_preambles.SPAWN_TARGETS.update(orig)


class TestCheckMode:
    """--check mode: exit 0 when in-sync, exit 7 when stale."""

    def test_check_in_sync_exits_0(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)
        code, _, _ = _invoke_build(quoin_dir)
        assert code == 0

        code_check, _, err = _invoke_build(quoin_dir, check=True)
        assert code_check == 0, f"--check should exit 0 on in-sync preambles; err={err}"

    def test_check_stale_exits_7(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)
        code, _, _ = _invoke_build(quoin_dir)
        assert code == 0

        # Modify a source file after build
        fk = quoin_dir / "memory" / "format-kit.md"
        fk.write_text(fk.read_text() + "\n# modified\n")

        # Re-patch and run --check
        orig_quoin_dir = build_preambles.QUOIN_DIR
        orig_fk = build_preambles.SOURCE_FORMAT_KIT
        orig_gl = build_preambles.SOURCE_GLOSSARY
        build_preambles.QUOIN_DIR = quoin_dir
        build_preambles.SOURCE_FORMAT_KIT = quoin_dir / "memory" / "format-kit.md"
        build_preambles.SOURCE_GLOSSARY = quoin_dir / "memory" / "glossary.md"

        import io
        from contextlib import redirect_stdout, redirect_stderr
        argv_backup = sys.argv[:]
        sys.argv = ["build_preambles.py", "--check"]
        stderr_cap = io.StringIO()
        exit_code = None
        try:
            with redirect_stderr(stderr_cap):
                exit_code = build_preambles.main()
        except SystemExit as e:
            exit_code = e.code
        finally:
            sys.argv = argv_backup
            build_preambles.QUOIN_DIR = orig_quoin_dir
            build_preambles.SOURCE_FORMAT_KIT = orig_fk
            build_preambles.SOURCE_GLOSSARY = orig_gl

        assert exit_code == 7, f"Expected exit 7 for stale preamble, got {exit_code}"


class TestMutuallyExclusive:
    """--dry-run and --check together trigger exit 6."""

    def test_dry_run_and_check_exits_6(self, tmp_path):
        quoin_dir = _make_virtual_project(tmp_path)
        code, _, err = _invoke_build(quoin_dir, dry_run=True, check=True)
        assert code == 6, f"Expected exit 6 for --dry-run + --check, got {code}; err={err}"
