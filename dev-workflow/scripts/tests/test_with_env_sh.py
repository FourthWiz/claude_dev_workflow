"""
Tests for dev-workflow/scripts/with_env.sh.

The wrapper loads shell rc files in non-interactive subshells so ANTHROPIC_API_KEY
is available to summarize_for_human.py. Tests verify idempotent (already-set) and
sourcing (rc file contains the key) paths.
"""

import os
import subprocess
import sys
import tempfile

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.dirname(TEST_DIR)
WITH_ENV = os.path.join(SCRIPTS_DIR, 'with_env.sh')


def run_with_env(env=None, extra_env=None):
    """Run `bash with_env.sh env` and return stdout lines."""
    run_env = os.environ.copy()
    # Strip ANTHROPIC_API_KEY from base env so tests control it explicitly
    run_env.pop('ANTHROPIC_API_KEY', None)
    if env:
        run_env.update(env)
    if extra_env:
        run_env.update(extra_env)
    result = subprocess.run(
        ['bash', WITH_ENV, 'env'],
        capture_output=True,
        env=run_env,
    )
    return result.returncode, result.stdout.decode('utf-8', errors='replace')


def test_idempotent_when_key_already_set():
    """When ANTHROPIC_API_KEY is already set, wrapper must not overwrite it."""
    rc, stdout = run_with_env(env={'ANTHROPIC_API_KEY': 'dummy'})
    assert rc == 0
    assert 'ANTHROPIC_API_KEY=dummy' in stdout


def test_sources_rc_file_when_key_missing():
    """When ANTHROPIC_API_KEY is absent, wrapper sources $HOME/.zshrc to find it."""
    with tempfile.TemporaryDirectory() as mock_home:
        zshrc = os.path.join(mock_home, '.zshrc')
        with open(zshrc, 'w') as f:
            f.write('export ANTHROPIC_API_KEY=test123\n')
        rc, stdout = run_with_env(
            env={'HOME': mock_home, 'SHELL': '/bin/zsh'}
        )
        assert rc == 0, f'with_env.sh exited {rc}'
        assert 'ANTHROPIC_API_KEY=test123' in stdout


def test_handles_messy_rc_file_with_unset_var_references():
    """Wrapper must tolerate rc files that reference unset variables (real-world case).

    Pre-fix the wrapper used `set -eu`, and rc files referencing unset vars
    (e.g., $NVM_DIR, theme vars) caused the wrapper to abort before exec.
    Stage 4 smoke documented this as a deterministic hang. Post-fix the
    wrapper uses `set -e` only, so unset-var references in rc files are
    tolerated.
    """
    with tempfile.TemporaryDirectory() as mock_home:
        zshrc = os.path.join(mock_home, '.zshrc')
        # Real-world rc-file pattern: reference an unset variable. The bare
        # `$UNSET_NVM_DIR` reference would abort with `set -u`. The
        # `[ -z "${OTHER_UNSET-}" ]` test is a softer pattern that's still
        # common in plugin-manager guards. Both must pass.
        with open(zshrc, 'w') as f:
            f.write('# messy rc file simulating real-world plugin guards\n')
            f.write('echo "NVM_DIR=$UNSET_NVM_DIR" >&2\n')
            f.write('[ -z "$UNSET_PLUGIN_GUARD" ] && true\n')
            f.write('export ANTHROPIC_API_KEY=test-from-messy-rc\n')
        rc, stdout = run_with_env(
            env={'HOME': mock_home, 'SHELL': '/bin/zsh'}
        )
        assert rc == 0, (
            f'with_env.sh aborted on messy rc file (set -u regression?); '
            f'rc={rc}, stdout: {stdout[:200]}'
        )
        assert 'ANTHROPIC_API_KEY=test-from-messy-rc' in stdout
