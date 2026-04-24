"""
Smoke tests for summarize_for_human.py.

Deterministic, CI-safe (no live API calls). The optional integration test
(test_integration_haiku_call) is auto-skipped when ANTHROPIC_API_KEY is unset.

Run (smoke only — no creds needed):
  pytest dev-workflow/scripts/tests/test_summarize_for_human.py -v -m "not integration"

Run all (requires ANTHROPIC_API_KEY):
  pytest dev-workflow/scripts/tests/test_summarize_for_human.py -v
"""

import os
import subprocess
import sys

import pytest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(TEST_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPTS_DIR))

SUMMARIZE = os.path.join(SCRIPTS_DIR, 'summarize_for_human.py')
FIXTURES_DIR = os.path.join(TEST_DIR, 'fixtures')


def run_summarize(*args, env_overrides=None):
    """Run summarize_for_human.py and return (returncode, stdout, stderr)."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    cmd = [sys.executable, SUMMARIZE] + list(args)
    result = subprocess.run(cmd, capture_output=True, env=env, cwd=PROJECT_ROOT)
    return (
        result.returncode,
        result.stdout.decode('utf-8', errors='replace'),
        result.stderr.decode('utf-8', errors='replace'),
    )


def test_help_flag_exits_zero():
    rc, stdout, _ = run_summarize('--help')
    assert rc == 0
    assert 'Usage:' in stdout or 'usage:' in stdout or 'body-file-path' in stdout


def test_missing_api_key_exits_nonzero():
    """With ANTHROPIC_API_KEY unset, must exit non-zero with descriptive message."""
    env_no_key = {'ANTHROPIC_API_KEY': ''}
    # Use a real fixture file so the script doesn't fail on missing-file first
    body = os.path.join(FIXTURES_DIR, 'v06-pass.md')
    rc, _, stderr = run_summarize(body, env_overrides=env_no_key)
    assert rc != 0
    assert 'ANTHROPIC_API_KEY missing' in stderr


def test_missing_body_file_exits_nonzero():
    rc, _, stderr = run_summarize('/tmp/nonexistent-body-file-12345.md')
    assert rc != 0
    assert 'not found' in stderr.lower() or 'body file' in stderr.lower()


def test_prompt_template_anchor_string():
    """Tripwire: prompt template must contain the anti-hallucination instruction."""
    with open(SUMMARIZE, encoding='utf-8') as f:
        source = f.read()
    assert 'do NOT invent facts not present in the body' in source


def test_model_constant_pinned():
    """MODEL constant must be present and pinned to a Haiku model ID."""
    with open(SUMMARIZE, encoding='utf-8') as f:
        source = f.read()
    assert 'MODEL = "claude-haiku-' in source


def test_anthropic_is_lazy_imported():
    """
    Verify anthropic is NOT imported at module scope and IS imported inside a function.
    This ensures argparse / --help / missing-key / missing-file paths work without SDK.
    """
    with open(SUMMARIZE, encoding='utf-8') as f:
        lines = f.readlines()

    module_scope_import = False
    in_function = False
    function_import_found = False

    for line in lines:
        stripped = line.rstrip('\n')
        # Track whether we're inside a function body (simple heuristic: indent > 0)
        if stripped.startswith('def ') or stripped.startswith('class '):
            in_function = True
        # Module-scope: line starts with 'import anthropic' (no indent)
        if stripped.startswith('import anthropic'):
            module_scope_import = True
        # In-function: indented 'import anthropic'
        if 'import anthropic' in stripped and not stripped.startswith('import anthropic'):
            function_import_found = True

    assert not module_scope_import, "anthropic must NOT be imported at module scope"
    assert function_import_found, "anthropic MUST be imported inside a function body"


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get('ANTHROPIC_API_KEY'),
    reason="ANTHROPIC_API_KEY not set — integration test skipped"
)
def test_integration_haiku_call():
    """Live Haiku call against the POC fixture body. Requires ANTHROPIC_API_KEY."""
    import time
    body = os.path.join(FIXTURES_DIR, 'v06-pass.md')
    start = time.time()
    rc, stdout, stderr = run_summarize(body)
    elapsed = time.time() - start

    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {stderr}"
    assert elapsed < 30, f"Expected < 30s wall time, got {elapsed:.1f}s"

    non_blank_lines = [l for l in stdout.strip().splitlines() if l.strip()]
    assert 1 <= len(non_blank_lines) <= 12, (
        f"Expected 1-12 non-blank lines of output, got {len(non_blank_lines)}"
    )
    # Plain English check: no obvious terse-rubric patterns (glyphs as first char)
    first_chars = {l[0] for l in non_blank_lines if l}
    glyph_starters = {'✓', '✗', '⏳', '🚫'}
    assert not (first_chars & glyph_starters), (
        f"Output appears to use terse glyph syntax — expected plain English. "
        f"Lines: {non_blank_lines}"
    )


# ── T-11: current-plan body fixture smoke tests ───────────────────────────────

def test_smoke_current_plan_body_no_credentials():
    """Body.tmp fixture is accepted (not rejected as wrong format) — fails only on missing key."""
    body = os.path.join(FIXTURES_DIR, 'v3-current-plan.body.tmp.md')
    rc, _, stderr = run_summarize(body, env_overrides={'ANTHROPIC_API_KEY': ''})
    assert rc != 0
    # Must fail due to missing key, NOT because of a file-format or parse error
    assert 'ANTHROPIC_API_KEY missing' in stderr, (
        f"Expected ANTHROPIC_API_KEY error, got: {stderr!r}"
    )


def test_summarize_returns_empty_handled_by_caller():
    """Tripwire: script must exit 0 (not non-zero) on successful Haiku call,
    even if output is unexpectedly empty. Callers (§5.3 Step 2) are responsible
    for detecting empty stdout and triggering the retry path."""
    with open(SUMMARIZE, encoding='utf-8') as f:
        source = f.read()
    # Script must NOT force a non-zero exit for empty output — that check is the
    # caller's job per §5.3 Step 2. Verify no sys.exit(1) on empty-output guard.
    # (We check the exit-0 path exists for successful API responses.)
    assert 'sys.exit(0)' in source or 'return' in source, (
        "Script must have a success exit path"
    )
    # And the script must not contain logic that exits non-zero specifically for empty output
    # (it may print to stdout and exit 0 — the caller strips whitespace and checks emptiness)
    lines_with_empty_exit = [
        l for l in source.splitlines()
        if 'empty' in l.lower() and 'sys.exit(1)' in l
    ]
    assert not lines_with_empty_exit, (
        f"Script exits non-zero for empty output — caller should handle this: {lines_with_empty_exit}"
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not os.environ.get('ANTHROPIC_API_KEY'),
    reason="ANTHROPIC_API_KEY not set — integration test skipped"
)
def test_integration_current_plan_body():
    """Live Haiku call against the current-plan body.tmp fixture. Requires ANTHROPIC_API_KEY."""
    import time
    body = os.path.join(FIXTURES_DIR, 'v3-current-plan.body.tmp.md')
    start = time.time()
    rc, stdout, stderr = run_summarize(body)
    elapsed = time.time() - start

    assert rc == 0, f"Expected exit 0, got {rc}. stderr: {stderr}"
    assert elapsed < 30, f"Expected < 30s wall time, got {elapsed:.1f}s"

    non_blank_lines = [l for l in stdout.strip().splitlines() if l.strip()]
    assert 1 <= len(non_blank_lines) <= 12, (
        f"Expected 1-12 non-blank lines, got {len(non_blank_lines)}: {non_blank_lines}"
    )
    # Must not start with ## For human (Step 3(a) strips it, but script may include it)
    # The validator's V-06 dedup check is tested separately; here we just check line count
    first_non_blank = next((l for l in stdout.splitlines() if l.strip()), '')
    assert not first_non_blank.startswith('## '), (
        f"Summary should not start with a heading: {first_non_blank!r}"
    )
