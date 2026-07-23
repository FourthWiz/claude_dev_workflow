#!/usr/bin/env python3
"""Portable core implementation of affected-area test selection and runner.

Given a set of changed files (via --project-root, --files-from, or --files),
this helper maps the changed files to affected test files and runs them.
The result is used by /gate and /review as a HARD PRECONDITION for APPROVED.

Exit-code semantics intentionally INVERT branch_hygiene's convention:
  0  — APPROVABLE (two sub-cases disambiguated by the `ran_pytest` output field):
       0a: affected-area suite GREEN (`ran_pytest=true`, `exit_reason="affected-green"`)
           pytest ran on a non-empty selector set and returned 0;
           `unmatched_sources` is empty (or --allow-unmatched was passed).
       0b: docs-only / no selectors (`ran_pytest=false`,
           `exit_reason="docs-only-no-selectors"`)
           ALL changed files are non-.py (docs/SKILL.md/JSON) so there is
           legitimately nothing to test.  pytest is NOT invoked (HARD GUARD).
       0c: clean tree (`ran_pytest=false`, `exit_reason="no-changes"`)
           git ran cleanly and the working tree is genuinely unchanged.
  1  — affected-area suite RED: pytest ran and returned non-zero. BLOCKING.
  2  — argparse / malformed input.
  3  — UNDETERMINABLE (fail-CLOSED): git-root resolution failed, git error,
       `unmatched_sources` non-empty without --allow-unmatched, or pytest
       binary missing.  Treat as "cannot confirm green → do NOT auto-approve."
       NOTE: QUOIN_DISABLE_AFFECTED_TESTS=1 also exits 3 (not 0) because
       disabling detection must not silently green-light an APPROVE — this
       is the OPPOSITE of branch_hygiene's env opt-out which exits 0.
  4  — a .py source changed AND its selectors resolved to the empty set
       (changed source with nothing to run).  Distinct from 3 so the gate
       message can say "no affected tests found for changed sources."
       gate/review treat 3 and 4 identically (both blocking-surface).
  5  — NO active quoin task context (NON-approving, NON-blocking).  Reachable
       ONLY with --require-task-context in --project-root mode when
       QUOIN_REQUIRE_TASK_CONTEXT!=0 and no active task folder is found at or
       above the project root (IVG-151).  Distinct from 0/1/2/3/4: it is a
       CLEAN-SKIP / N/A signal for a non-quoin session, never a WARN or a gate
       FAIL.  With an active task context this code can NEVER be returned — the
       real check runs and the existing 0/1/3/4 matrix is byte-for-byte intact.

Env:
  QUOIN_DISABLE_AFFECTED_TESTS=1 — exit 3 immediately (fail-CLOSED opt-out)
  QUOIN_REQUIRE_TASK_CONTEXT — literal "0" ONLY forces legacy always-run even
      when --require-task-context is passed (disarms the exit-5 branch); unset
      or any other value honors the flag (IVG-151).
  QUOIN_BASE_BRANCH — override the base branch probe order (default: tries
      origin/main, origin/master, main, master in order).
  QUOIN_SUBPROCESS_TIMEOUT — seconds, default 30; bounds every SHORT git
      subprocess run by this module (see _subprocess_timeout()). The pytest
      subprocess gets a generous DERIVED bound max(600, QUOIN_SUBPROCESS_TIMEOUT)
      instead (D-05) — a TimeoutExpired there maps to exit 3 with
      exit_reason="pytest-timeout" (BLOCKING-SURFACE, never a silent GREEN,
      never a hard-RED false block; see proc P-03).
  QUOIN_DISABLE_CHILD_REPO_SCAN=1 — skip the depth-1 child-.git discovery scan
      in discover_repos(); single-repo view only. Distinct from
      QUOIN_DISABLE_DISPATCH_CWD (a different concern, see D-08).

Git-root resolution note (CRIT-1 / IVG-70 remedy):
  The outer quoin project root is NOT a git repo; only the quoin/ subtree is.
  When given --project-root, this helper resolves the git repo itself via a
  depth-1 discover_repos-style scan (mirroring branch_hygiene.py), then runs
  all git commands INSIDE that repo.  The caller (gate/review) NEVER runs git
  directly — the helper owns the resolution + diff-basis fallback.

Diff-basis fallback chain (F-01 fix — no-upstream committed-branch gap):
  1. If upstream exists: git -C <repo> diff --name-only @{u}...HEAD (three-dot).
  2. If empty / no upstream: resolve the base branch (try origin/main,
     origin/master, main, master — or QUOIN_BASE_BRANCH override) and run
     git -C <repo> diff --name-only <merge_base>...HEAD (three-dot merge-base).
     This is the critical step for the committed-clean no-upstream case
     (the normal state during /review and both /gate invocations before
     /end_of_task pushes the branch).
  3. If still empty: worktree + staged fallback:
     git diff --name-only HEAD ∪ --name-only --cached.
  4. If STILL empty AND git ran cleanly: exit 0c (no-changes).
  5. On any git error: exit 3 (undeterminable).
  Fail-CLOSED note: if no base branch resolves AND there is no upstream AND
  the tree is committed-clean, prefer exit 3 (undeterminable) over silently
  approving with no-changes — because there may well be committed changes
  that simply cannot be diffed without a reference point.

Untracked-file blind spot (MIN-2):
  The worktree fallback (HEAD ∪ cached) does NOT list untracked (never-added)
  files.  This is NOT a false-green hole because the gate's separate
  "No uncommitted changes" check runs FIRST and blocks on any untracked file,
  so the helper never sees a state with untracked .py sources.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Directories to exclude from depth-1 repo scan (mirrors branch_hygiene._EXCLUDE_NAMES)
_EXCLUDE_NAMES: frozenset[str] = frozenset({
    ".workflow_artifacts",
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".idea",
    ".vscode",
})

# Special-case mapping: certain docs/source files that are not .py themselves
# must trigger specific test files when changed.  Each entry is a
# (src_suffix, test_rel) pair where:
#   src_suffix — posix suffix that must appear at the END of the changed path
#                (with a leading "/" guard to avoid matching bare basenames from
#                 other repos, e.g. bare "CLAUDE.md" does NOT match "quoin/CLAUDE.md").
#   test_rel   — path of the test file, relative to the quoin/ git repo root.
# The guard is applied as: posix == src_suffix OR posix.endswith("/" + src_suffix).
_DOCS_TO_TESTS: tuple[tuple[str, str], ...] = (
    (
        "quoin/CLAUDE.md",
        "quoin/dev/tests/test_claude_md_size_ceiling.py",
    ),
    (
        "quoin/memory/format-kit.md",
        "quoin/dev/tests/test_preamble_freshness.py",
    ),
    (
        "quoin/memory/glossary.md",
        "quoin/dev/tests/test_preamble_freshness.py",
    ),
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class Selection:
    """Result of mapping changed files to test selectors."""
    changed: list[str]
    selectors: list[str]          # sorted, deduplicated test file paths
    unmatched_sources: list[str]  # .py sources with zero matched test
    ignored: list[str]            # non-.py files (docs, JSON, SKILL.md, ...)
    ran_pytest: bool
    pytest_returncode: int | None
    exit_reason: str              # see exit code doc above
    unmatched_warning: bool = False  # set when --allow-unmatched in use

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "changed": self.changed,
            "selectors": self.selectors,
            "unmatched_sources": self.unmatched_sources,
            "ignored": self.ignored,
            "ran_pytest": self.ran_pytest,
            "pytest_returncode": self.pytest_returncode,
            "exit_reason": self.exit_reason,
        }
        if self.unmatched_warning:
            d["unmatched_warning"] = True
        return d


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def _subprocess_timeout() -> int:
    """Read QUOIN_SUBPROCESS_TIMEOUT (seconds); default 30; bad values fall back to 30.

    Self-contained local copy (D-06) — do NOT cross-import; each touched core
    script owns its own copy per the repo's copy-not-import convention.
    """
    try:
        return int(os.environ.get("QUOIN_SUBPROCESS_TIMEOUT", "30"))
    except (TypeError, ValueError):
        return 30


def _run(args: list[str]) -> tuple[str, str, int]:
    """Run a subprocess and return (stdout, stderr, returncode)."""
    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=_subprocess_timeout(),
        )
        return proc.stdout.strip(), proc.stderr.strip(), proc.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except FileNotFoundError:
        return "", "git not found", 1
    except Exception as exc:  # noqa: BLE001
        return "", str(exc), 1


def discover_repos(project_root: Path) -> list[Path]:
    """Discover git repositories under project_root (depth-1 scan).

    Mirrors branch_hygiene.discover_repos exactly.
    - If project_root/.git exists, include project_root.resolve().
    - Iterate depth-1 children; include any child dir with .git not in _EXCLUDE_NAMES.
    - Returns sorted, deduplicated absolute Path list.
    - On OSError, returns [].

    D-08 / T-08: when QUOIN_DISABLE_CHILD_REPO_SCAN=1, the depth-1 per-child
    .git stat loop is skipped entirely and this returns a single-repo view
    ([root] if root/.git exists, else []). Distinct from
    QUOIN_DISABLE_DISPATCH_CWD; default (unset) is byte-identical to the
    pre-existing behavior below.
    """
    if os.environ.get("QUOIN_DISABLE_CHILD_REPO_SCAN") == "1":
        try:
            root = project_root.resolve()
        except OSError:
            return []
        return [root] if (root / ".git").exists() else []

    repos: list[Path] = []
    seen: set[str] = set()

    def _add(p: Path) -> None:
        canonical = str(p.resolve())
        if canonical not in seen:
            seen.add(canonical)
            repos.append(p.resolve())

    try:
        root = project_root.resolve()
        if (root / ".git").exists():
            _add(root)
        try:
            children = sorted(root.iterdir())
        except OSError:
            children = []
        for child in children:
            if child.name in _EXCLUDE_NAMES:
                continue
            if child.is_dir() and (child / ".git").exists():
                _add(child)
    except OSError:
        return []

    return sorted(repos, key=lambda p: str(p))


def resolve_repo(project_root: Path) -> Path | None:
    """Resolve the single git repo under project_root via depth-1 scan.

    Returns the repo Path when exactly one repo is found.
    Returns None when zero repos found (caller should exit 3).
    Raises RuntimeError with a message when >1 repos found (caller should exit 3).
    """
    repos = discover_repos(project_root)
    if len(repos) == 0:
        return None
    if len(repos) > 1:
        paths = ", ".join(str(r) for r in repos)
        raise RuntimeError(
            f"Multiple git repos found under {project_root}; "
            f"pass --repo-root explicitly to disambiguate: {paths}"
        )
    return repos[0]


# Infra folders under .workflow_artifacts/ that do NOT count as an active task
# context — they exist regardless of whether any task is in flight (IVG-151).
_TASK_CONTEXT_INFRA: frozenset[str] = frozenset({"memory", "cache", "finalized", "trash"})


def has_active_task_context(project_root: Path) -> bool:
    """Return True if an active quoin task context is detectable at/above project_root.

    Git-free detector (lives in the Git-helpers region for locality only).
    Walks UP from project_root to the filesystem root looking for a
    ``.workflow_artifacts/`` directory that contains at least one REAL task
    folder — a child directory whose name is NOT dot-prefixed and is NOT one of
    the infra folders (memory / cache / finalized / trash).

    Direction invariants (the only never-false-green-safe choices — IVG-151
    architecture R-01 / R-06 / R-07):
      - Walk-up only ADDS context: a ``.workflow_artifacts/`` with no qualifying
        task child does NOT short-circuit to False; the walk keeps going upward.
        This is the subdir-safety guarantee — e.g. a check run from inside
        ``quoin/`` still finds the workflow root one level up.
      - OSError degrades to context-PRESENT (return True): an unreadable
        ``.workflow_artifacts/`` must fail toward RUNNING the real check, never
        toward silently skipping it, and never toward a crash.
    Both directions fail toward RUNNING the real check — a false-skip of a real
    red suite is the one outcome this design forbids.
    """
    try:
        cur = project_root.resolve()
        while True:
            wa = cur / ".workflow_artifacts"
            if wa.is_dir():
                for child in wa.iterdir():
                    if (
                        child.is_dir()
                        and not child.name.startswith(".")
                        and child.name not in _TASK_CONTEXT_INFRA
                    ):
                        return True
                # WA present but no qualifying task child — keep walking up
                # (do NOT early-return False here — walk-up only adds context).
            if cur.parent == cur:  # reached the filesystem root
                return False
            cur = cur.parent
    except OSError:
        # Degrade to context-PRESENT: fail toward RUNNING the real check.
        return True


def _resolve_base_branch(repo_str: str) -> str | None:
    """Probe candidate base branches in order and return the first that resolves.

    Probe order:
      1. QUOIN_BASE_BRANCH env var (if set and non-empty)
      2. origin/main
      3. origin/master
      4. main
      5. master

    Returns the ref name string if resolvable, None if none resolve.
    """
    env_override = os.environ.get("QUOIN_BASE_BRANCH", "").strip()
    candidates: list[str] = []
    if env_override:
        candidates.append(env_override)
    candidates.extend(["origin/main", "origin/master", "main", "master"])

    for ref in candidates:
        out, err, rc = _run(
            ["git", "-C", repo_str, "rev-parse", "--verify", ref]
        )
        if rc == 0 and out.strip():
            return ref
    return None


def changed_files(repo: Path) -> tuple[list[str], str]:
    """Compute the set of changed files in repo using the diff-basis fallback chain.

    Returns (files, exit_reason) where exit_reason is one of:
      "upstream-diff"    — obtained from @{u}...HEAD (three-dot, merge-base diff)
      "base-branch-diff" — obtained from <base>...HEAD (merge-base diff vs base branch)
      "worktree-diff"    — obtained from HEAD ∪ cached diff
      "no-changes"       — git ran cleanly, tree is genuinely clean
      "git-error"        — git command failed (caller should exit 3)

    Fallback chain (F-01 fix):
      1. Upstream @{u}...HEAD (if upstream exists and yields non-empty diff)
      2. Base-branch merge-base: <base>...HEAD where <base> is resolved via
         _resolve_base_branch() — this handles the committed-clean no-upstream
         case (the canonical /review + /gate state before /end_of_task push).
      3. Worktree + staged fallback (handles uncommitted dirty trees)
      4. no-changes (genuinely clean)
      Fail-CLOSED: if no base resolves AND no upstream AND tree is clean but
      HEAD has commits (i.e. is not the root), we still return no-changes
      (the git state is genuinely unambiguous at that point — an initial commit
      on a brand-new repo truly has nothing to diff against).

    NOTE: Three-dot @{u}...HEAD shares the @{u} ANCHOR with review Step 6a's
    two-dot @{u}..HEAD rev-list count, but uses the merge-base operator — they
    agree on a feature branch strictly ahead of an unmoved upstream and diverge
    only if upstream advanced past the branch point.  Three-dot is correct here
    (we want "what changed on this branch"), so Step 6a is left unchanged (MIN-1).

    NOTE: worktree fallback intentionally excludes untracked files — the gate's
    "No uncommitted changes" check is the backstop that prevents false-greens
    from untracked new .py sources (MIN-2 documented in module docstring).
    """
    repo_str = str(repo.resolve())

    # Step 1: try upstream three-dot diff
    ups_out, ups_err, ups_rc = _run(
        ["git", "-C", repo_str, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
    )
    if ups_rc == 0 and ups_out:
        diff_out, diff_err, diff_rc = _run(
            ["git", "-C", repo_str, "diff", "--name-only", "@{u}...HEAD"]
        )
        if diff_rc != 0:
            return [], "git-error"
        files = [f for f in diff_out.splitlines() if f.strip()]
        if files:
            return files, "upstream-diff"
        # Empty upstream diff — fall through to base-branch step

    # Step 2 (F-01 fix): base-branch merge-base diff — handles the committed-clean
    # no-upstream case (feature branch created with `git switch -c`, not yet pushed).
    # This is the NORMAL state during /review and both /gate invocations.
    base_ref = _resolve_base_branch(repo_str)
    if base_ref is not None:
        # Compute the merge-base between <base> and HEAD
        merge_base_out, mb_err, mb_rc = _run(
            ["git", "-C", repo_str, "merge-base", base_ref, "HEAD"]
        )
        if mb_rc == 0 and merge_base_out.strip():
            merge_base = merge_base_out.strip()
            diff_out, diff_err, diff_rc = _run(
                ["git", "-C", repo_str, "diff", "--name-only", f"{merge_base}...HEAD"]
            )
            if diff_rc != 0:
                return [], "git-error"
            files = [f for f in diff_out.splitlines() if f.strip()]
            if files:
                return files, "base-branch-diff"
            # Empty base-branch diff — fall through to worktree fallback

    # Step 3: worktree + staged fallback
    head_out, head_err, head_rc = _run(
        ["git", "-C", repo_str, "diff", "--name-only", "HEAD"]
    )
    if head_rc != 0:
        return [], "git-error"
    cached_out, cached_err, cached_rc = _run(
        ["git", "-C", repo_str, "diff", "--name-only", "--cached"]
    )
    if cached_rc != 0:
        return [], "git-error"

    combined: set[str] = set()
    for line in head_out.splitlines():
        if line.strip():
            combined.add(line.strip())
    for line in cached_out.splitlines():
        if line.strip():
            combined.add(line.strip())

    if not combined:
        # Step 4: genuinely clean tree
        return [], "no-changes"

    return sorted(combined), "worktree-diff"


# ---------------------------------------------------------------------------
# Detection algorithm
# ---------------------------------------------------------------------------

def _collect_test_files(repo_root: Path) -> list[Path]:
    """Return all test_*.py / *_test.py files under repo_root."""
    results: list[Path] = []
    for p in repo_root.rglob("*.py"):
        name = p.name
        if name.startswith("test_") or name.endswith("_test.py"):
            results.append(p)
    return results


def map_changed_to_tests(
    changed: list[str],
    repo_root: Path,
) -> tuple[list[str], list[str], list[str]]:
    """Map a list of changed file paths to test selectors.

    Returns (selectors, unmatched_sources, ignored) where:
      selectors         — sorted, deduped absolute-or-relative test file paths to run
      unmatched_sources — .py sources with ZERO matched tests (fail-CLOSED signal)
      ignored           — non-.py files (docs, JSON, SKILL.md, ...) — excluded from
                          unmatched_sources; a changeset of ONLY ignored files is
                          a docs-only changeset (exit 0b, not exit 4).
                          Exception: files listed in _DOCS_TO_TESTS are mapped to
                          a specific test file and do NOT land in ignored.

    Detection algorithm:
      1. Changed test files → included directly as selectors.
      2. Changed non-test .py files with stem S → name-match: any test file whose
         basename matches test_{S}*.py or {S}_test.py (PRIMARY signal).
      3. Import-graph grep (BEST-EFFORT supplement): whole-word \\b{S}\\b match
         anywhere in each test file — catches spec_from_file_location paths,
         string literals, _CORE_PATH assignments, _quoin_core_{S} aliases.
         More false-positives → SAFE (runs more tests, never fewer).
      4. If a .py source has ZERO selectors after steps 1-3 → unmatched_source.
         Non-.py files → ignored.
    """
    test_files = _collect_test_files(repo_root)
    selectors: set[str] = set()
    unmatched_sources: list[str] = []
    ignored: list[str] = []

    for changed_file in changed:
        fpath = Path(changed_file)
        name = fpath.name

        # Is this file itself a Python test file?
        # Guard on .py suffix to avoid selecting non-Python test files (e.g., .sh)
        # as pytest selectors — pytest would fail to collect them (exit 4).
        if fpath.suffix == ".py" and (name.startswith("test_") or name.endswith("_test.py")):
            # Include directly as a selector; resolve against repo_root if relative
            full = (repo_root / changed_file).resolve() if not fpath.is_absolute() else fpath.resolve()
            if full.exists():
                selectors.add(str(full))
            else:
                # File may be staged/deleted; add as-is
                selectors.add(str(repo_root / changed_file))
            continue

        # Special-case: certain non-.py docs/source files map to specific tests.
        # Runs BEFORE the generic non-.py "ignored" fallback so these files
        # are treated as selector sources (exit 0a) rather than docs-only (exit 0b).
        if fpath.suffix != ".py":
            posix = PurePosixPath(changed_file).as_posix()
            mapped_any = False
            for src_suffix, test_rel in _DOCS_TO_TESTS:
                if posix == src_suffix or posix.endswith("/" + src_suffix):
                    test_path = repo_root / test_rel
                    if test_path.exists():
                        selectors.add(str(test_path))
                    mapped_any = True
            if mapped_any:
                continue
            # Generic non-.py file → ignored
            ignored.append(changed_file)
            continue

        # .py non-test source → attempt name-match + import-graph grep
        stem = fpath.stem
        matched: set[str] = set()

        # Step 2: name-match
        for tf in test_files:
            tfname = tf.name
            if tfname.startswith(f"test_{stem}") or tfname == f"{stem}_test.py":
                matched.add(str(tf))

        # Step 3: whole-word grep in test file content (BEST-EFFORT)
        if stem:
            pattern = re.compile(r"\b" + re.escape(stem) + r"\b")
            for tf in test_files:
                if str(tf) in matched:
                    continue  # already matched
                try:
                    content = tf.read_text(encoding="utf-8", errors="ignore")
                    if pattern.search(content):
                        matched.add(str(tf))
                except OSError:
                    pass  # unreadable test file — skip

        if matched:
            selectors.update(matched)
        else:
            unmatched_sources.append(changed_file)

    return sorted(selectors), unmatched_sources, ignored


# ---------------------------------------------------------------------------
# Text formatter (T-02)
# ---------------------------------------------------------------------------

def _format_text(sel: Selection) -> str:
    """Human-readable text summary of a Selection."""
    lines: list[str] = []
    lines.append(f"exit_reason: {sel.exit_reason}")
    lines.append(f"ran_pytest: {sel.ran_pytest}")
    if sel.pytest_returncode is not None:
        lines.append(f"pytest_returncode: {sel.pytest_returncode}")
    lines.append(f"changed ({len(sel.changed)}): {', '.join(sel.changed) or '(none)'}")
    lines.append(f"selectors ({len(sel.selectors)}): {', '.join(sel.selectors) or '(none)'}")
    if sel.unmatched_sources:
        lines.append(f"unmatched_sources ({len(sel.unmatched_sources)}): {', '.join(sel.unmatched_sources)}")
    if sel.ignored:
        lines.append(f"ignored ({len(sel.ignored)}): {', '.join(sel.ignored)}")
    if sel.unmatched_warning:
        lines.append("unmatched_warning: true (--allow-unmatched in use)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns exit code:
      0 — APPROVABLE (affected-area green, docs-only, or clean tree)
      1 — affected-area suite RED (pytest returned non-zero)
      2 — argparse / malformed input
      3 — UNDETERMINABLE (fail-CLOSED): git-root failure, git error, unmatched
          sources, pytest missing, or QUOIN_DISABLE_AFFECTED_TESTS=1
      4 — .py source changed but selectors resolved to empty set
      5 — no active quoin task context (NON-approving, NON-blocking); reachable
          only with --require-task-context in --project-root mode when
          QUOIN_REQUIRE_TASK_CONTEXT!=0 (IVG-151)
    """
    # Env opt-out — exits 3 (NOT 0) so disabling cannot silently green-light APPROVE
    if os.environ.get("QUOIN_DISABLE_AFFECTED_TESTS", "").strip() == "1":
        print(json.dumps({"disabled": True}))
        return 3

    parser = argparse.ArgumentParser(
        description=(
            "Map changed files to affected test files and run them. "
            "A GREEN result is a hard precondition for APPROVED in /gate and /review."
        ),
        add_help=True,
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--project-root",
        type=Path,
        metavar="PATH",
        help=(
            "PRIMARY workflow path.  The helper resolves the git repo under PATH "
            "and computes the changed-file set itself (CRIT-1/CRIT-2 fix).  "
            "The caller never runs git directly."
        ),
    )
    mode.add_argument(
        "--files-from",
        metavar="PATH",
        help=(
            "Newline-delimited list of changed files from PATH (use '-' for stdin).  "
            "Portable override — no git dependency; used by unit tests."
        ),
    )
    mode.add_argument(
        "--files",
        nargs="+",
        metavar="FILE",
        help="Changed files passed inline.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        metavar="PATH",
        default=None,
        help=(
            "Root for test-file discovery and the pytest invocation.  "
            "In --project-root mode this is set automatically to the resolved git repo.  "
            "Optional override for --files-from / --files modes."
        ),
    )
    parser.add_argument(
        "--select-only",
        action="store_true",
        help="Print resolved test selectors as JSON and exit WITHOUT running pytest.",
    )
    parser.add_argument(
        "--allow-unmatched",
        action="store_true",
        help=(
            "When set, unmatched_sources being non-empty does NOT force exit 3 — "
            "it adds unmatched_warning=true and the exit code is driven by pytest. "
            "Default OFF (fail-CLOSED)."
        ),
    )
    parser.add_argument(
        "--require-task-context",
        action="store_true",
        dest="require_task_context",
        help=(
            "Opt-in: in --project-root mode, if no active quoin task context is "
            "found (and QUOIN_REQUIRE_TASK_CONTEXT!=0), exit 5 (no-quoin-task-context) "
            "WITHOUT running pytest. Inert in --files/--files-from modes."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json).",
    )
    parser.add_argument(
        "--pytest-arg",
        action="append",
        dest="pytest_args",
        metavar="ARG",
        default=[],
        help="Extra argument appended to the pytest invocation (repeatable).",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 2

    fmt = args.format

    # ------------------------------------------------------------------
    # Step 1: resolve changed files
    # ------------------------------------------------------------------
    changed: list[str] = []
    repo_root: Path | None = args.repo_root

    if args.project_root is not None:
        # IVG-151: opt-in early exit-5 when NO active quoin task context is
        # found. This is the FIRST statement in the --project-root block,
        # BEFORE resolve_repo(), so a non-quoin session never resolves a
        # foreign git root or runs any git subprocess (that noise is exactly
        # what the ticket removes).
        # Precedence invariants (pin — do NOT reorder):
        #   - QUOIN_DISABLE_AFFECTED_TESTS=1 already returned 3 at the very top
        #     of main() (before argparse), so disable NATURALLY wins over this.
        #   - QUOIN_REQUIRE_TASK_CONTEXT literal "0" forces legacy always-run
        #     (mirrors the QUOIN_DISABLE_* literal-value parsing convention).
        if (
            args.require_task_context
            and os.environ.get("QUOIN_REQUIRE_TASK_CONTEXT", "").strip() != "0"
            and not has_active_task_context(args.project_root)
        ):
            sel = Selection(
                changed=[],
                selectors=[],
                unmatched_sources=[],
                ignored=[],
                ran_pytest=False,
                pytest_returncode=None,
                exit_reason="no-quoin-task-context",
            )
            if fmt == "text":
                print(_format_text(sel))
            else:
                print(json.dumps(sel.to_dict(), indent=2))
            return 5
        # --project-root mode: resolve git repo, compute diff
        try:
            repo = resolve_repo(args.project_root)
        except RuntimeError as exc:
            print(json.dumps({
                "error": str(exc),
                "exit_reason": "undeterminable-multiple-repos",
                "ran_pytest": False,
                "pytest_returncode": None,
                "changed": [],
                "selectors": [],
                "unmatched_sources": [],
                "ignored": [],
            }), file=sys.stderr)
            return 3
        if repo is None:
            print(json.dumps({
                "error": f"No git repo found under --project-root {args.project_root}",
                "exit_reason": "undeterminable-no-repo",
                "ran_pytest": False,
                "pytest_returncode": None,
                "changed": [],
                "selectors": [],
                "unmatched_sources": [],
                "ignored": [],
            }), file=sys.stderr)
            return 3

        # Set repo_root if not explicitly overridden
        if repo_root is None:
            repo_root = repo

        files, reason = changed_files(repo)
        if reason == "git-error":
            print(json.dumps({
                "error": "git error while computing changed files",
                "exit_reason": "undeterminable-git-error",
                "ran_pytest": False,
                "pytest_returncode": None,
                "changed": [],
                "selectors": [],
                "unmatched_sources": [],
                "ignored": [],
            }), file=sys.stderr)
            return 3
        if reason == "no-changes":
            sel = Selection(
                changed=[],
                selectors=[],
                unmatched_sources=[],
                ignored=[],
                ran_pytest=False,
                pytest_returncode=None,
                exit_reason="no-changes",
            )
            if fmt == "text":
                print(_format_text(sel))
            else:
                print(json.dumps(sel.to_dict(), indent=2))
            return 0
        # Paths from git are relative to repo; keep them as-is for map_changed_to_tests
        changed = files

    elif args.files_from is not None:
        # --files-from mode
        if args.files_from == "-":
            raw = sys.stdin.read()
        else:
            try:
                raw = Path(args.files_from).read_text(encoding="utf-8")
            except OSError as exc:
                print(f"error: cannot read --files-from {args.files_from}: {exc}", file=sys.stderr)
                return 2
        changed = [l.strip() for l in raw.splitlines() if l.strip()]

    else:
        # --files mode
        changed = list(args.files)

    # ------------------------------------------------------------------
    # Step 2: map changed files to selectors
    # ------------------------------------------------------------------
    if repo_root is None:
        repo_root = Path.cwd()

    selectors, unmatched_sources, ignored = map_changed_to_tests(changed, repo_root)

    # ------------------------------------------------------------------
    # Step 3: --select-only path — print and exit without running pytest
    # ------------------------------------------------------------------
    if args.select_only:
        sel = Selection(
            changed=changed,
            selectors=selectors,
            unmatched_sources=unmatched_sources,
            ignored=ignored,
            ran_pytest=False,
            pytest_returncode=None,
            exit_reason="select-only",
            unmatched_warning=bool(unmatched_sources and args.allow_unmatched),
        )
        if fmt == "text":
            print(_format_text(sel))
        else:
            print(json.dumps(sel.to_dict(), indent=2))
        return 0

    # ------------------------------------------------------------------
    # Step 4: post-selection routing (MAJ-1 — BEFORE any pytest call)
    # ------------------------------------------------------------------

    # 4a: unmatched sources without --allow-unmatched → exit 3 (fail-CLOSED)
    if unmatched_sources and not args.allow_unmatched:
        sel = Selection(
            changed=changed,
            selectors=selectors,
            unmatched_sources=unmatched_sources,
            ignored=ignored,
            ran_pytest=False,
            pytest_returncode=None,
            exit_reason="unmatched-sources",
        )
        if fmt == "text":
            print(_format_text(sel))
        else:
            print(json.dumps(sel.to_dict(), indent=2))
        return 3

    # 4b: empty selectors branch — determine WHY and exit BEFORE touching pytest
    if not selectors:
        # Use the already-computed unmatched_sources to determine why selectors is empty.
        # F-02 fix: with --allow-unmatched, the escape-hatch contract yields exit 0 (not 4)
        # even when all .py sources were unmatched — the flag means "I know tests are
        # missing; don't block me."  Exit 4 is only reachable without --allow-unmatched,
        # but that path is handled in 4a above (unmatched_sources + no flag → exit 3).
        # Therefore the only remaining empty-selector cases here are:
        #   - unmatched_sources non-empty AND --allow-unmatched set → exit 0b (warn)
        #   - unmatched_sources empty → truly docs-only → exit 0b
        if unmatched_sources and args.allow_unmatched:
            # --allow-unmatched with all sources unmatched and no selectors:
            # exit 0 with unmatched_warning — consistent with escape-hatch contract.
            sel = Selection(
                changed=changed,
                selectors=[],
                unmatched_sources=unmatched_sources,
                ignored=ignored,
                ran_pytest=False,
                pytest_returncode=None,
                exit_reason="docs-only-no-selectors",
                unmatched_warning=True,
            )
            if fmt == "text":
                print(_format_text(sel))
            else:
                print(json.dumps(sel.to_dict(), indent=2))
            return 0

        # Docs-only: zero changed .py sources → exit 0b
        # (also catches genuinely-empty changed list when called via --files [])
        sel = Selection(
            changed=changed,
            selectors=[],
            unmatched_sources=[],
            ignored=ignored,
            ran_pytest=False,
            pytest_returncode=None,
            exit_reason="docs-only-no-selectors",
        )
        if fmt == "text":
            print(_format_text(sel))
        else:
            print(json.dumps(sel.to_dict(), indent=2))
        return 0

    # ------------------------------------------------------------------
    # Step 5: run pytest on the resolved selectors (GUARDED — selectors non-empty)
    # ------------------------------------------------------------------
    # HARD GUARD: this line is only reachable when selectors is non-empty.
    assert selectors, "BUG: pytest invocation reached with empty selectors"

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *selectors, *args.pytest_args],
            cwd=str(repo_root),
            timeout=max(600, _subprocess_timeout()),
        )
        rc = proc.returncode
    except FileNotFoundError:
        # pytest binary missing → exit 3 (undeterminable, non-blocking warn)
        sel = Selection(
            changed=changed,
            selectors=selectors,
            unmatched_sources=unmatched_sources,
            ignored=ignored,
            ran_pytest=False,
            pytest_returncode=None,
            exit_reason="pytest-missing",
            unmatched_warning=bool(unmatched_sources and args.allow_unmatched),
        )
        if fmt == "text":
            print(_format_text(sel))
        else:
            print(json.dumps(sel.to_dict(), indent=2))
        return 3
    except subprocess.TimeoutExpired:
        # pytest subprocess exceeded the derived bound → exit 3 (undeterminable,
        # BLOCKING-SURFACE at the gate). NEITHER a false-GREEN (exit 0) NOR a
        # hard false-RED (exit 1) — the human decides (MAJ-3 / D-05 / proc P-03).
        sel = Selection(
            changed=changed,
            selectors=selectors,
            unmatched_sources=unmatched_sources,
            ignored=ignored,
            ran_pytest=False,
            pytest_returncode=None,
            exit_reason="pytest-timeout",
            unmatched_warning=bool(unmatched_sources and args.allow_unmatched),
        )
        if fmt == "text":
            print(_format_text(sel))
        else:
            print(json.dumps(sel.to_dict(), indent=2))
        return 3

    exit_reason = "affected-green" if rc == 0 else "affected-red"
    sel = Selection(
        changed=changed,
        selectors=selectors,
        unmatched_sources=unmatched_sources,
        ignored=ignored,
        ran_pytest=True,
        pytest_returncode=rc,
        exit_reason=exit_reason,
        unmatched_warning=bool(unmatched_sources and args.allow_unmatched),
    )
    if fmt == "text":
        print(_format_text(sel))
    else:
        print(json.dumps(sel.to_dict(), indent=2))
    return 0 if rc == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
