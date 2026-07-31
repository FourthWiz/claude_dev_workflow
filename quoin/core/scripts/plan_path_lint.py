"""plan_path_lint.py — flag file-path-looking tokens in a plan artifact that don't
resolve to anything on disk (IVG-143).

Authors citing paths in `current-plan.md` (and similar planning artifacts) routinely
get the nested-package structure wrong — e.g. citing `quoin/docs/x.md` when the real
file lives at `quoin/quoin/docs/x.md` (git root `quoin/`, source package
`quoin/quoin/`). This scanner extracts backtick-quoted path-like tokens from an
artifact, checks each against the project root / git root / any extra bases, and
reports the ones that resolve nowhere — with a best-effort "did you mean" hint.

Portable-core: stdlib only (`argparse os re sys json pathlib`), no `import quoin`,
and — unlike its twin `nested_root_check.py` — no sibling-core import either. This
module is fully self-contained (D-P4): the wrapper still inserts the core/scripts dir
onto `sys.path` for pattern-parity with the twin, but nothing here actually needs it.

Exit codes (CLI):
  0 — clean: every checked token resolved
  1 — one or more cited tokens did not resolve to anything on disk
  2 — argparse / invocation error, or the artifact is missing/unreadable
  (any other unexpected exception is also caught and mapped to 2 — fail-OPEN: this
  tool must never crash a caller with a traceback)
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Layer 1 — extraction
# ---------------------------------------------------------------------------

# A fenced code block toggle — content between ``` lines is never scanned. Applied
# per-line so we can keep accurate 1-based line numbers for everything outside fences.
_FENCE_RE = re.compile(r"^\s*```")

# Single-backtick inline spans. No backtick or newline inside — backtick spans can't
# nest, and the line-by-line driver never hands this a string containing '\n'.
_BACKTICK_SPAN_RE = re.compile(r"`([^`\n]+)`")

# (a) WHITESPACE GUARD — pinned character class (critic MINOR carry-over #2): matches
# a literal space or tab. Backtick span content can never contain '\n' (excluded by
# _BACKTICK_SPAN_RE itself), so space/tab is the complete whitespace vector for the
# command+path false-positive class (R-01, e.g. `grep -A12 "x" some/real/path.md`).
# This exact class (` \t`, not bare `\s`) is mirrored verbatim in
# test_plan_path_lint.py — keep both in sync if this ever changes.
_WHITESPACE_RE = re.compile(r"[ \t]")

# ---------------------------------------------------------------------------
# Exclusion classes E1-E5
# ---------------------------------------------------------------------------

_DUNDER_RE = re.compile(r"__[A-Za-z0-9_]+__")  # E1 — e.g. __QUOIN_HOME__ (internal '_' allowed)
_ANGLE_RE = re.compile(r"<[^<>]*>")           # E2 — e.g. <task-name>
_GLOB_CHARS = frozenset("*?[]{}")             # E3 — shell glob metacharacters

_EXTENSIONS = frozenset({
    ".py", ".md", ".sh", ".json", ".txt", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".js", ".ts", ".html", ".css",
})

# Directories pruned during the bounded H4 basename walk (perf + noise, R-06).
# Twin's set (`.git .venv venv node_modules __pycache__ .idea .vscode .workspaces`)
# PLUS `.workflow_artifacts` — task folders are never a legitimate hint target.
_PRUNE_NAMES = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__",
    ".idea", ".vscode", ".workspaces", ".workflow_artifacts",
})

# Hard cap on basename-walk visits — the project may live on a slow Drive-mounted
# tree (R-06: a corpus grep timed out at 120s during review of this exact feature).
_WALK_CAP = 20000

_ENV_DISABLE = "QUOIN_DISABLE_PLAN_PATH_LINT"


def derive_project_root(artifact: Path) -> Path:
    """Walk UP from `artifact` to the first ancestor directory literally named
    `.workflow_artifacts`; the project root is that ancestor's PARENT.

    Fallback (no `.workflow_artifacts` ancestor found): the artifact's own parent
    directory. This is artifact-anchored, not cwd-anchored — deterministic
    regardless of the caller's working directory (R-10 / AC4).
    """
    for ancestor in artifact.resolve().parents:
        if ancestor.name == ".workflow_artifacts":
            return ancestor.parent
    return artifact.resolve().parent


def derive_git_root(project_root: Path):
    """Return the git root Path under `project_root`, or None.

    A quoin project root is not itself a git repo (multi-repo layout) — the git
    root is normally an immediate CHILD directory. Preference order:
      1. `project_root` itself, if it directly contains a `.git` entry.
      2. The first (sorted) immediate child directory containing a `.git` entry.
      3. None (undeterminable — callers degrade to project-root-only resolution).
    """
    try:
        if (project_root / ".git").exists():
            return project_root
        children = sorted(
            p for p in project_root.iterdir()
            if p.is_dir() and (p / ".git").exists()
        )
    except OSError:
        return None
    return children[0] if children else None


# ---------------------------------------------------------------------------
# Layer 1 (cont'd) — path_like gate
# ---------------------------------------------------------------------------

def _is_external_absolute(tok: str, project_root) -> bool:
    """E5: leading `~`, or a leading `/` whose prefix is NOT `project_root`."""
    if tok.startswith("~"):
        return True
    if tok.startswith("/"):
        if project_root is None:
            return True
        proj_str = str(project_root)
        return tok != proj_str and not tok.startswith(proj_str + "/")
    return False


def path_like(tok: str, *, bases) -> bool:
    """Fixed-order gate deciding whether a backtick span is worth resolving.

    Order (do not reorder — each stage is a documented, individually-tested
    de-risk target): (a) whitespace guard FIRST, then URL/anchor skips, (b) must
    contain '/', (c) exclusion classes E1-E5, (d) recognizable-file-component gate.
    """
    # (a) whitespace guard — command+path spans (R-01) must never reach resolution.
    if _WHITESPACE_RE.search(tok):
        return False
    # Extra guards: URL schemes and pure anchors/fragments are never file paths.
    if "://" in tok:
        return False
    if tok.startswith("#"):
        return False
    if not tok:
        return False

    # (b) must contain '/'
    if "/" not in tok:
        return False

    # (c) exclusion classes E1-E5
    if _DUNDER_RE.search(tok):          # E1
        return False
    if _ANGLE_RE.search(tok):           # E2
        return False
    if any(c in _GLOB_CHARS for c in tok):  # E3
        return False
    # E4 (no-'/' bare basename) is already guaranteed by gate (b) above — this is a
    # deliberate no-op kept for documentation parity with the architecture's E1-E5
    # enumeration; no token can reach this line without a '/'.
    project_root = bases[0] if bases else None
    if _is_external_absolute(tok, project_root):  # E5
        return False

    # (d) recognizable-file-component gate
    if tok.endswith("/"):
        return True
    last_seg = tok.rsplit("/", 1)[-1]
    if Path(last_seg).suffix in _EXTENSIONS:
        return True
    first_seg = tok.split("/", 1)[0]
    for base in bases:
        if base is None:
            continue
        try:
            if (base / first_seg).is_dir():
                return True
        except OSError:
            continue
    return False


def extract_tokens(text: str):
    """Yield (raw_span_content, 1_based_line_number) for every backtick span
    outside a fenced code block. Caller applies `path_like` filtering."""
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in _BACKTICK_SPAN_RE.finditer(line):
            yield m.group(1), lineno


# ---------------------------------------------------------------------------
# Layer 2 — resolution (prefix-aware, D-01)
# ---------------------------------------------------------------------------

def resolves(tok: str, *, project_root: Path, git_root, git_dir, extra_bases) -> bool:
    """True iff `tok` resolves against the project root, the (prefix-suppressed)
    git root, or any extra base.

    D-01 prefix-aware suppression: if `tok` already starts with `git_dir + "/"`,
    the git-root check is SKIPPED. Without this, a token like `quoin/docs/x.md`
    (missing one nesting level) would falsely resolve via
    `git_root/quoin/docs/x.md` == `project_root/quoin/quoin/docs/x.md` — which
    happens to be the REAL location one level over, not what a naive git-root-
    relative reading would mean. Suppressing the git-root check for
    already-prefixed tokens is what makes the AC1 off-by-one case correctly
    UNRESOLVED instead of silently (and misleadingly) resolving.
    """
    if (project_root / tok).exists():
        return True
    if git_root is not None and git_dir and not tok.startswith(git_dir + "/"):
        if (git_root / tok).exists():
            return True
    for base in extra_bases:
        if (base / tok).exists():
            return True
    return False


# ---------------------------------------------------------------------------
# Layer 3 — fuzzy hint (best-effort, at most one, never fabricated)
# ---------------------------------------------------------------------------

def _walk_basename_search(project_root: Path, basename: str):
    """Bounded, pruned basename search under `project_root`. Returns the
    lexicographically-first matching relative path (posix-style), or None.
    Deterministic: dirnames/filenames are sorted before comparison so repeated
    runs (and different CWDs, R-10) never depend on os.walk's raw iteration
    order."""
    visited = 0
    matches = []
    for dirpath, dirnames, filenames in os.walk(project_root, topdown=True):
        dirnames[:] = sorted(name for name in dirnames if name not in _PRUNE_NAMES)
        for name in sorted(filenames) + list(dirnames):
            visited += 1
            if name == basename:
                full = Path(dirpath) / name
                try:
                    rel = full.relative_to(project_root)
                except ValueError:
                    continue
                matches.append(str(rel).replace(os.sep, "/"))
            if visited > _WALK_CAP:
                break
        if visited > _WALK_CAP:
            break
    return sorted(matches)[0] if matches else None


def _hint(tok: str, *, project_root: Path, git_root, git_dir, extra_bases):
    """At most one hint, fixed strategy order, first on-disk hit wins. Never
    fabricates a suggestion — every candidate is verified to exist before it is
    returned."""
    # H1 — nested-insert: tok already reads as git-root-relative but is missing
    # one more level of the (git_dir-named) nested package.
    if git_dir and tok.startswith(git_dir + "/"):
        candidate = git_dir + "/" + tok
        if (project_root / candidate).exists():
            return candidate

    # H2 — de-double: tok accidentally repeats the git_dir segment twice in a row;
    # collapse one occurrence and see if THAT resolves (the inverse mistake of H1).
    if git_dir:
        doubled = f"{git_dir}/{git_dir}/"
        if tok.startswith(doubled):
            candidate = f"{git_dir}/" + tok[len(doubled):]
            if (project_root / candidate).exists():
                return candidate

    # H3 — git-root reframe: tok is NOT git_dir-prefixed at all; try reading it as
    # relative to the nested package by prefixing git_dir once.
    if git_dir and git_root is not None and not tok.startswith(git_dir + "/"):
        candidate = git_dir + "/" + tok
        if (project_root / candidate).exists():
            return candidate

    # H4 — bounded pruned basename walk, last resort.
    basename = tok.rstrip("/").rsplit("/", 1)[-1]
    if basename:
        try:
            hit = _walk_basename_search(project_root, basename)
        except OSError:
            hit = None
        if hit:
            return hit

    return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def lint(artifact: Path, *, project_root=None, git_root=None, extra_bases=None) -> dict:
    """Run all three layers over `artifact`. Returns the JSON-shaped result dict."""
    text = artifact.read_text(encoding="utf-8")
    extra_bases = list(extra_bases or [])

    proj = project_root if project_root is not None else derive_project_root(artifact)
    groot = git_root if git_root is not None else derive_git_root(proj)
    gdir = groot.name if groot is not None else None

    bases_for_path_like = [proj] + ([groot] if groot is not None else []) + extra_bases

    checked = 0
    unresolved = []
    seen = set()
    for tok, lineno in extract_tokens(text):
        if not path_like(tok, bases=bases_for_path_like):
            continue
        key = (tok, lineno)
        if key in seen:
            continue
        seen.add(key)
        checked += 1
        if resolves(tok, project_root=proj, git_root=groot, git_dir=gdir, extra_bases=extra_bases):
            continue
        hint = _hint(tok, project_root=proj, git_root=groot, git_dir=gdir, extra_bases=extra_bases)
        unresolved.append({"token": tok, "line": lineno, "hint": hint})

    return {
        "artifact": str(artifact),
        "bases": [str(b) for b in bases_for_path_like],
        "checked": checked,
        "unresolved": unresolved,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="plan_path_lint.py",
        description=(
            "Flag file-path-looking tokens in a plan artifact that don't resolve "
            "to anything on disk (IVG-143)."
        ),
    )
    parser.add_argument("artifact", metavar="ARTIFACT", help="Path to the artifact to lint.")
    parser.add_argument("--project-root", default=None, metavar="PATH")
    parser.add_argument("--git-root", default=None, metavar="PATH")
    parser.add_argument("--base", action="append", default=[], metavar="PATH",
                         help="Extra base directory to resolve tokens against (repeatable).")
    parser.add_argument("--include-prose", action="store_true", default=False,
                         help="Reserved for future prose-recall scanning; backtick-only for now.")
    parser.add_argument("--format", default="text", choices=("text", "json"))
    parser.add_argument("--quiet", action="store_true", default=False)
    return parser


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)  # argparse errors -> SystemExit(2), propagates as-is

    if os.environ.get(_ENV_DISABLE) == "1":
        if args.format == "json":
            print(json.dumps({"disabled": True, "unresolved": []}))
        else:
            print("plan_path_lint: disabled via " + _ENV_DISABLE)
        return 0

    try:
        artifact = Path(args.artifact)
        if not artifact.is_file():
            print(f"plan_path_lint: artifact not found or not a file: {artifact}", file=sys.stderr)
            return 2

        project_root = Path(args.project_root).resolve() if args.project_root else None
        git_root = Path(args.git_root).resolve() if args.git_root else None
        extra_bases = [Path(b).resolve() for b in (args.base or [])]

        result = lint(
            artifact.resolve(),
            project_root=project_root,
            git_root=git_root,
            extra_bases=extra_bases,
        )
    except OSError as exc:
        print(f"plan_path_lint: cannot read artifact — {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — fail-OPEN: never crash the caller
        print(f"plan_path_lint: undeterminable — {exc}", file=sys.stderr)
        return 2

    unresolved = result["unresolved"]

    if args.format == "json":
        print(json.dumps(result))
        return 1 if unresolved else 0

    if not unresolved:
        if not args.quiet:
            print(f"plan_path_lint: OK — {result['checked']}/{result['checked']} cited paths resolved")
        return 0

    if not args.quiet:
        for item in unresolved:
            print(f"UNRESOLVED: {item['token']} (line {item['line']})")
            if item["hint"]:
                print(f"    did you mean: {item['hint']}?")
    return 1


if __name__ == "__main__":
    sys.exit(main())
