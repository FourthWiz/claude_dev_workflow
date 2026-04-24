"""
Black-box pytest tests for validate_artifact.py.

Tests call the validator via subprocess against synthetic .md fixtures in
dev-workflow/scripts/tests/fixtures/. Tests are hermetic: each test passes
--sections-json pointing at the test fixture sidecar (content-identical to
the production sidecar at test creation time).

No imports of validator internals — tests exercise the CLI contract only.
Run: pytest dev-workflow/scripts/tests/test_validate_artifact.py -v
"""

import os
import subprocess
import sys

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────

# Resolve from the location of this test file upward to the project root
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_DIR = os.path.join(TEST_DIR, 'fixtures')
SCRIPTS_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPTS_DIR))

VALIDATOR = os.path.join(SCRIPTS_DIR, 'validate_artifact.py')
TEST_SIDECAR = os.path.join(FIXTURES_DIR, 'format-kit.sections.json')


def run_validator(*extra_args, artifact=None, artifact_type=None):
    """Helper: run the validator and return (returncode, stderr_text)."""
    cmd = [sys.executable, VALIDATOR, '--sections-json', TEST_SIDECAR]
    if artifact_type:
        cmd += ['--type', artifact_type]
    cmd += list(extra_args)
    if artifact:
        cmd.append(artifact)
    result = subprocess.run(cmd, capture_output=True, cwd=PROJECT_ROOT)
    return result.returncode, result.stderr.decode('utf-8', errors='replace')


def fixture(name):
    return os.path.join(FIXTURES_DIR, name)


# ── V-01: Frontmatter YAML ────────────────────────────────────────────────────

def test_v01_pass_valid_frontmatter():
    rc, _ = run_validator(artifact=fixture('v01-pass.md'), artifact_type='default')
    assert rc == 0


def test_v01_fail_invalid_frontmatter():
    rc, stderr = run_validator(artifact=fixture('v01-fail-bad-yaml.md'), artifact_type='default')
    assert rc == 1
    assert 'FAIL V-01' in stderr


def test_v01_pass_no_frontmatter():
    rc, stderr = run_validator(artifact=fixture('v01-pass-no-frontmatter.md'), artifact_type='default')
    assert rc == 0
    assert 'FAIL V-01' not in stderr


# ── V-02: Allowed sections ────────────────────────────────────────────────────

def test_v02_pass_allowed_sections():
    rc, _ = run_validator(artifact=fixture('v02-pass.md'), artifact_type='current-plan')
    assert rc == 0


def test_v02_fail_unknown_section():
    rc, stderr = run_validator(artifact=fixture('v02-fail.md'), artifact_type='current-plan')
    assert rc == 1
    assert 'FAIL V-02' in stderr
    assert '## Made-Up Section' in stderr


# ── V-03: Table separator ─────────────────────────────────────────────────────

def test_v03_pass_well_formed_table():
    rc, _ = run_validator(artifact=fixture('v03-pass.md'), artifact_type='default')
    assert rc == 0


def test_v03_fail_missing_separator():
    rc, stderr = run_validator(artifact=fixture('v03-fail.md'), artifact_type='default')
    assert rc == 1
    assert 'FAIL V-03' in stderr
    assert 'table missing header separator' in stderr


# ── V-04: XML tag balance ─────────────────────────────────────────────────────

def test_v04_pass_balanced_xml():
    rc, _ = run_validator(artifact=fixture('v04-pass.md'), artifact_type='default')
    assert rc == 0


def test_v04_fail_orphan_open():
    rc, stderr = run_validator(artifact=fixture('v04-fail-open.md'), artifact_type='default')
    assert rc == 1
    assert 'FAIL V-04' in stderr
    assert '<verdict>' in stderr or 'verdict' in stderr


def test_v04_fail_orphan_close():
    rc, stderr = run_validator(artifact=fixture('v04-fail-close.md'), artifact_type='default')
    assert rc == 1
    assert 'FAIL V-04' in stderr
    assert 'verdict' in stderr


def test_v04_pass_inline_code():
    """V-04 must NOT fire on XML-looking strings inside backtick inline-code spans."""
    rc, stderr = run_validator(artifact=fixture('v04-pass-inline-code.md'), artifact_type='default')
    assert rc == 0
    assert 'FAIL V-04' not in stderr


# ── V-05: ID references resolve ───────────────────────────────────────────────

def test_v05_pass_resolved_ids():
    rc, _ = run_validator(artifact=fixture('v05-pass.md'), artifact_type='default')
    assert rc == 0


def test_v05_pass_table_defined_ids():
    """IDs defined as markdown table rows must resolve."""
    rc, stderr = run_validator(artifact=fixture('v05-pass-table.md'), artifact_type='default')
    assert rc == 0
    assert 'FAIL V-05' not in stderr


def test_v05_pass_bullet_defined_ids():
    """IDs defined as bullet list items must resolve."""
    rc, stderr = run_validator(artifact=fixture('v05-pass-bullet.md'), artifact_type='default')
    assert rc == 0
    assert 'FAIL V-05' not in stderr


def test_v05_pass_heading_defined_ids():
    """IDs defined as ### heading lines must resolve."""
    rc, stderr = run_validator(artifact=fixture('v05-pass-heading.md'), artifact_type='default')
    assert rc == 0
    assert 'FAIL V-05' not in stderr


def test_v05_pass_numbered_defined_ids():
    """IDs defined as numbered-list items (1. T-01: …) must resolve."""
    rc, stderr = run_validator(artifact=fixture('v05-pass-numbered.md'), artifact_type='default')
    assert rc == 0
    assert 'FAIL V-05' not in stderr


def test_v05_pass_self_ref_on_def_line():
    """Cross-refs on def lines are skipped (interpretation (a) per MIN-2-R2)."""
    rc, stderr = run_validator(
        artifact=fixture('v05-pass-self-ref-on-def-line.md'), artifact_type='default'
    )
    assert rc == 0
    assert 'FAIL V-05' not in stderr


def test_v05_fail_undefined_ref():
    rc, stderr = run_validator(artifact=fixture('v05-fail.md'), artifact_type='default')
    assert rc == 1
    assert 'FAIL V-05' in stderr
    assert 'T-99' in stderr


# ── V-06: ## For human section ────────────────────────────────────────────────

def test_v06_pass_class_b_with_summary():
    rc, _ = run_validator(artifact=fixture('v06-pass.md'), artifact_type='current-plan')
    assert rc == 0


def test_v06_fail_class_b_missing_summary():
    rc, stderr = run_validator(artifact=fixture('v06-fail-missing.md'), artifact_type='current-plan')
    assert rc == 1
    assert 'FAIL V-06' in stderr
    assert '## For human' in stderr


def test_v06_fail_class_b_summary_too_long():
    rc, stderr = run_validator(artifact=fixture('v06-fail-long.md'), artifact_type='current-plan')
    assert rc == 1
    assert 'FAIL V-06' in stderr
    assert 'exceeds 12 non-blank lines' in stderr


def test_v06_skip_class_a():
    """Class A artifacts must not be checked for ## For human."""
    rc, stderr = run_validator(artifact=fixture('v06-class-a.md'), artifact_type='critic-response')
    assert rc == 0
    assert 'FAIL V-06' not in stderr


# ── V-07: Required sections present ──────────────────────────────────────────

def test_v07_pass_required_sections_present():
    rc, _ = run_validator(artifact=fixture('v07-pass.md'), artifact_type='current-plan')
    assert rc == 0


def test_v07_fail_missing_required_section():
    rc, stderr = run_validator(artifact=fixture('v07-fail.md'), artifact_type='current-plan')
    assert rc == 1
    assert 'FAIL V-07' in stderr
    assert '## Tasks' in stderr


# ── Invocation errors ─────────────────────────────────────────────────────────

def test_invocation_error_no_file():
    rc, stderr = run_validator(artifact='/tmp/missing-fixture-file-9999.md', artifact_type='default')
    assert rc == 2
    assert 'file not found' in stderr.lower() or 'not found' in stderr.lower()


# ── Multiple failures reported ────────────────────────────────────────────────

def test_multiple_failures_reported():
    """Both V-02 (unknown section) and V-05 (unresolved ref) must appear in stderr."""
    rc, stderr = run_validator(artifact=fixture('multi-fail.md'), artifact_type='current-plan')
    assert rc == 1
    assert 'FAIL V-02' in stderr
    assert 'FAIL V-05' in stderr


# ── T-10: current-plan v2/v3 fixture tests ────────────────────────────────────

def test_v3_current_plan_fixture_passes():
    """v3-current-plan.md must pass all validator checks (auto-detected as current-plan)."""
    rc, stderr = run_validator(artifact=fixture('v3-current-plan.md'))
    assert rc == 0, f"v3 fixture failed:\n{stderr}"


def test_v2_current_plan_fixture_fails_v02_v06_v07():
    """current-plan-v2.md must fail V-02, V-06, and V-07 (auto-detected as current-plan)."""
    rc, stderr = run_validator(artifact=fixture('current-plan-v2.md'))
    assert rc == 1
    assert 'FAIL V-02' in stderr, f"Expected V-02 in:\n{stderr}"
    assert 'FAIL V-06' in stderr, f"Expected V-06 in:\n{stderr}"
    assert 'FAIL V-07' in stderr, f"Expected V-07 in:\n{stderr}"


def test_v3_current_plan_summary_block_position():
    """## For human must appear within the first 50 lines after frontmatter."""
    import pathlib
    content = pathlib.Path(fixture('v3-current-plan.md')).read_text()
    lines = content.splitlines()
    # Skip frontmatter (between first and second ---)
    in_frontmatter = False
    body_start = 0
    fence_count = 0
    for i, line in enumerate(lines):
        if line.strip() == '---':
            fence_count += 1
            if fence_count == 2:
                body_start = i + 1
                break
    body_lines = lines[body_start:]
    for_human_pos = next(
        (i for i, l in enumerate(body_lines) if l.strip() == '## For human'),
        None
    )
    assert for_human_pos is not None, "## For human heading not found"
    assert for_human_pos < 50, (
        f"## For human appears at body line {for_human_pos} (must be < 50)"
    )


def test_v3_current_plan_summary_length_at_boundary():
    """Exactly 12 non-blank summary lines PASS; 13 non-blank lines FAIL V-06."""
    rc12, stderr12 = run_validator(artifact=fixture('current-plan-summary-12.md'))
    assert rc12 == 0, f"12-line summary should pass:\n{stderr12}"

    rc13, stderr13 = run_validator(artifact=fixture('current-plan-summary-13.md'))
    assert rc13 == 1, "13-line summary should fail V-06"
    assert 'FAIL V-06' in stderr13
    assert 'exceeds 12 non-blank lines' in stderr13


def test_assembled_file_no_duplicate_for_human_heading():
    """A correctly assembled v3 file has exactly one ## For human heading.
    The body.tmp has zero. This confirms the §5.3 Step 3(a) dedup is needed."""
    import pathlib, re
    v3 = pathlib.Path(fixture('v3-current-plan.md')).read_text()
    body = pathlib.Path(fixture('v3-current-plan.body.tmp.md')).read_text()

    pattern = re.compile(r'^## For human\s*$', re.MULTILINE)
    v3_count = len(pattern.findall(v3))
    body_count = len(pattern.findall(body))

    assert v3_count == 1, (
        f"Assembled v3 file must have exactly one '## For human', found {v3_count}"
    )
    assert body_count == 0, (
        f"Body.tmp must have zero '## For human' headings (it has {body_count}); "
        "Step 3(a) dedup is critical to prevent duplication on assembly"
    )
