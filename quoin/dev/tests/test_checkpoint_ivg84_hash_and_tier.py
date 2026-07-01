"""IVG-84: Regression tests for checkpoint --restore project-hash derivation and tier bump.

Root causes fixed:
  RC-1: checkpoint/SKILL.md used `tr '/' '-'` to derive the project-hash for the
        ~/.claude/projects/<hash>/ JSONL directory.  The on-disk hash is produced
        by Claude Code using a broader transform (any char not in [A-Za-z0-9-] → '-'),
        so dots, @, underscores, and spaces were silently dropped, making the directory
        unreachable and leaving an orphan pending-restore-.txt sentinel.
  RC-2: checkpoint was declared model: haiku — too weak to execute the ~430-line restore
        body.  Bumped to model: sonnet.

Test (a): the real project path (containing '.', '@', '_', ' ') hashes correctly via
          project_hash() in the core helper.
Test (b): the naive `path.replace('/','/')` buggy transform produces a DIFFERENT result
          — documents why tr '/' '-' was wrong.
Test (c): the --print-hash CLI flag (wrapper script) returns the real on-disk hash and
          exits 0.  Also verifies the cwd-default (no --project-path) does not emit
          an empty string.
Test (d): checkpoint/SKILL.md contains NO `tr '/' '-'` and NO '/ replaced by -' phrasing
          (the two documentation-level bug sites, at the exact edit targets lines 406, 502).
Test (e): checkpoint/SKILL.md frontmatter reads `model: sonnet` and has zero
          `| checkpoint | haiku |` ledger-row templates.
"""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths — pin to SOURCE (not deployed ~/.claude copy)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_SCRIPT = REPO_ROOT / "quoin" / "core" / "scripts" / "get_session_uuid.py"
WRAPPER_SCRIPT = REPO_ROOT / "quoin" / "scripts" / "get_session_uuid.py"
CHECKPOINT_SKILL = REPO_ROOT / "quoin" / "adapters" / "claude" / "skills" / "checkpoint" / "SKILL.md"

# The real project path for this repo — contains '.', '@', '_', and ' '.
REAL_PATH = str(
    Path("/Users/ivgo/Library/CloudStorage/GoogleDrive-ivan.gorban@gmail.com")
    / "My Drive"
    / "Storage"
    / "Codex_workflow"
)
# The expected on-disk hash: all non-[A-Za-z0-9-] replaced with '-'.
EXPECTED_HASH = (
    "-Users-ivgo-Library-CloudStorage-GoogleDrive-ivan-gorban-gmail-com"
    "-My-Drive-Storage-Codex-workflow"
)


# ---------------------------------------------------------------------------
# Loader — VERBATIM from test_get_session_uuid.py (importlib, no dotted import)
# ---------------------------------------------------------------------------

def _load_core():
    """Load get_session_uuid core module via importlib (no sys.path mutation)."""
    spec = importlib.util.spec_from_file_location("_test_ivg84_hash_core", CORE_SCRIPT)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load core from {CORE_SCRIPT}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Test (a): project_hash() handles all four special char classes
# ---------------------------------------------------------------------------

def test_project_hash_handles_special_chars():
    """project_hash() must replace '/', '.', '@', '_', and ' ' with '-'.

    This is the load-bearing assertion that the transform covers all four
    special char classes present in the real Google Drive project path.
    FAILS before the RC-1 fix (tr '/' '-' only replaced '/').
    PASSES after the fix (broad regex replace via get_session_uuid.py helper).
    """
    mod = _load_core()
    result = mod.project_hash(REAL_PATH)
    assert result == EXPECTED_HASH, (
        f"project_hash({REAL_PATH!r})\n"
        f"  expected: {EXPECTED_HASH!r}\n"
        f"  actual:   {result!r}\n"
        "The broad-regex transform (any non-[A-Za-z0-9-] → '-') must cover "
        "'.', '@', '_', and ' ', not just '/'."
    )


# ---------------------------------------------------------------------------
# Test (b): the buggy naive tr-style transform produces a DIFFERENT result
# ---------------------------------------------------------------------------

def test_naive_slash_replace_is_wrong():
    """Prove that `path.replace('/','/')` does NOT equal the real on-disk hash.

    This documents WHY the old `tr '/' '-'` derivation was wrong: it only
    replaces '/' and leaves '.', '@', '_', and ' ' unchanged, producing a
    directory path that does not exist under ~/.claude/projects/.
    """
    buggy_hash = REAL_PATH.replace("/", "-")
    assert buggy_hash != EXPECTED_HASH, (
        "The buggy tr-style transform unexpectedly matches the real hash — "
        "the path must contain '.', '@', '_', or ' ' for this assertion to hold.\n"
        f"Path:       {REAL_PATH!r}\n"
        f"Buggy hash: {buggy_hash!r}\n"
        f"Real hash:  {EXPECTED_HASH!r}"
    )


# ---------------------------------------------------------------------------
# Test (c): --print-hash CLI (wrapper) returns the real hash and exits 0
# ---------------------------------------------------------------------------

def test_print_hash_cli_explicit_path():
    """--print-hash with explicit --project-path returns the on-disk hash, exit 0."""
    result = subprocess.run(
        [sys.executable, str(WRAPPER_SCRIPT), "--print-hash", "--project-path", REAL_PATH],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, (
        f"--print-hash exited with rc={result.returncode} (expected 0 — fail-open). "
        f"stdout: {result.stdout!r}  stderr: {result.stderr!r}"
    )
    assert result.stdout.strip() == EXPECTED_HASH, (
        f"--print-hash stdout: {result.stdout.strip()!r}\n"
        f"expected:            {EXPECTED_HASH!r}"
    )


def test_print_hash_cli_cwd_default():
    """--print-hash with NO --project-path defaults to cwd — must NOT emit empty string.

    This tests the `args.project_path or str(Path.cwd())` fallback (MIN-3 from critic).
    Invoked with cwd=REAL_PATH; must produce the same hash as explicit --project-path.
    FAILS if --print-hash passes '' to project_hash() (reproduces the RC-1 class of bug).
    """
    result = subprocess.run(
        [sys.executable, str(WRAPPER_SCRIPT), "--print-hash"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REAL_PATH,
    )
    assert result.returncode == 0, (
        f"--print-hash (cwd default) exited with rc={result.returncode}. "
        f"stdout: {result.stdout!r}  stderr: {result.stderr!r}"
    )
    out = result.stdout.strip()
    assert out, (
        "cwd-default --print-hash emitted an EMPTY string — "
        "the args.project_path or str(Path.cwd()) fallback did not fire. "
        "This reproduces the RC-1 class of bug (empty hash → non-existent directory)."
    )
    assert out == EXPECTED_HASH, (
        f"cwd-default --print-hash stdout: {out!r}\n"
        f"expected:                        {EXPECTED_HASH!r}"
    )


# ---------------------------------------------------------------------------
# Test (d): checkpoint/SKILL.md contains no buggy-transform prose
# ---------------------------------------------------------------------------

def test_checkpoint_no_tr_slash_replace():
    """checkpoint/SKILL.md must NOT contain `tr '/' '-'` anywhere.

    Acceptance criterion from T-02: after replacing lines 406 and 502,
    grep -c "tr '/' '-'" in checkpoint/SKILL.md == 0.
    """
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    text = CHECKPOINT_SKILL.read_text(encoding="utf-8")
    matches = [
        (i + 1, line.rstrip())
        for i, line in enumerate(text.splitlines())
        if "tr '/' '-'" in line
    ]
    assert not matches, (
        "checkpoint/SKILL.md still contains `tr '/' '-'` at:\n"
        + "\n".join(f"  line {ln}: {content}" for ln, content in matches)
        + "\nEdit targets are lines 406 and 502 (the buggy transform sites). "
        "Lines 175 and 684 are MUST-NOT-TOUCH EXCEPTION notes."
    )


def test_checkpoint_no_slash_replaced_by_dash_prose():
    """checkpoint/SKILL.md must NOT contain '/ replaced by -' phrasing.

    Acceptance criterion from T-02: grep -c '/ replaced by' in checkpoint/SKILL.md == 0.
    """
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    text = CHECKPOINT_SKILL.read_text(encoding="utf-8")
    # Match the misleading '`/` replaced by `-`' phrase in any surrounding context.
    # The actual text uses backtick-quoted chars: `/` replaced by `-`
    matches = [
        (i + 1, line.rstrip())
        for i, line in enumerate(text.splitlines())
        if "`/` replaced by `-`" in line
    ]
    assert not matches, (
        "checkpoint/SKILL.md still contains '/ replaced by -' phrasing at:\n"
        + "\n".join(f"  line {ln}: {content}" for ln, content in matches)
        + "\nReplace both occurrences (lines 406 and 502) with the helper-based derivation."
    )


# ---------------------------------------------------------------------------
# Test (e): model bump — frontmatter and ledger-row templates
# ---------------------------------------------------------------------------

def test_checkpoint_frontmatter_model_sonnet():
    """checkpoint/SKILL.md frontmatter must declare `model: sonnet` (RC-2 fix)."""
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    text = CHECKPOINT_SKILL.read_text(encoding="utf-8")
    # Frontmatter block is between the first two '---' delimiters.
    fm_match = re.match(r'^---\n(.*?\n)---\n', text, re.DOTALL)
    assert fm_match, "checkpoint/SKILL.md does not start with a valid YAML frontmatter block."
    frontmatter = fm_match.group(1)
    assert "model: sonnet" in frontmatter, (
        f"Frontmatter does not contain `model: sonnet`:\n{frontmatter}"
    )
    assert "model: haiku" not in frontmatter, (
        f"Frontmatter still contains `model: haiku` (should be sonnet):\n{frontmatter}"
    )


def test_checkpoint_no_haiku_ledger_row_templates():
    """checkpoint/SKILL.md must have zero `| checkpoint | haiku |` ledger row templates.

    Acceptance criterion from T-04: all four ledger-row template sites (lines 237, 271,
    533, 1099) must be updated to `| checkpoint | sonnet |`.
    """
    assert CHECKPOINT_SKILL.exists(), f"Missing: {CHECKPOINT_SKILL}"
    text = CHECKPOINT_SKILL.read_text(encoding="utf-8")
    matches = [
        (i + 1, line.rstrip())
        for i, line in enumerate(text.splitlines())
        if "| checkpoint | haiku |" in line
    ]
    assert not matches, (
        "checkpoint/SKILL.md still contains `| checkpoint | haiku |` at:\n"
        + "\n".join(f"  line {ln}: {content}" for ln, content in matches)
        + "\nAll four ledger-row templates must read `| checkpoint | sonnet |`."
    )
