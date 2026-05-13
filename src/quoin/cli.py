"""quoin CLI entrypoint — argparse wrapper + data-tree resolution."""
from __future__ import annotations

import argparse
import importlib.resources
import os
import pathlib
import runpy
import sys
from typing import Optional

from quoin.__about__ import __version__


def _resolve_source_dir(explicit: Optional[str]) -> pathlib.Path:
    """Resolve the quoin data source directory (proc:T-03).

    Resolution order:
    1. Explicit --source-dir flag (always trusted if it has skills/).
    2. Editable-install detection: if __file__ is under src/quoin/, skip
       importlib.resources and jump straight to Tier 2.
    3. Tier 1 (wheel install): importlib.resources.files('quoin') / 'data'.
    4. Tier 2 (editable / src layout): walk __file__ up to repo/quoin/.
    5. Tier 3: abort with explicit error.
    """
    if explicit is not None:
        candidate = pathlib.Path(explicit).resolve()
        if not (candidate / "skills").is_dir():
            print(
                f"quoin: --source-dir {explicit!r} has no skills/ subdirectory",
                file=sys.stderr,
            )
            sys.exit(2)
        return candidate

    import quoin as _quoin_pkg

    pkg_file = pathlib.Path(_quoin_pkg.__file__).resolve()

    # Editable-install detection: src/quoin/__init__.py → parent is 'quoin', grandparent is 'src'
    is_editable = (
        pkg_file.parent.name == "quoin" and pkg_file.parent.parent.name == "src"
    )

    if not is_editable:
        # Tier 1: wheel install — data is bundled inside the package
        try:
            data_ref = importlib.resources.files("quoin") / "data"
            # Convert to a concrete path for is_dir() checks
            with importlib.resources.as_file(data_ref) as data_path:  # type: ignore[attr-defined]
                data_path = pathlib.Path(data_path)
                if (data_path / "skills").is_dir():
                    return data_path
        except (TypeError, AttributeError, FileNotFoundError):
            pass

    # Tier 2: editable or importlib fallback — walk from src/quoin/ up to repo/
    # pkg_file.parent = src/quoin/; two ".." reaches project root; then "quoin/"
    candidate = (pkg_file.parent / ".." / ".." / "quoin").resolve()
    if (candidate / "skills").is_dir():
        return candidate

    # Tier 3: abort
    print(
        "quoin: cannot resolve data tree; pass --source-dir <path> "
        "(typically <path-to-clone>/quoin)",
        file=sys.stderr,
    )
    sys.exit(2)


def _derive_allow_writes(source_dir: pathlib.Path, source_dir_explicit: bool) -> bool:
    """Five-conjunct guard (proc:T-07 / MAJ-1 round-4 fix).

    True iff ALL of:
    (a) --source-dir was explicitly passed
    (b) os.access(source_dir, os.W_OK) is True
    (c) (source_dir / "skills").is_dir() is True
    (d) source_dir.parent has .git/ OR pyproject.toml
    (e) source_dir.resolve() is NOT a descendant of the package directory
    """
    if not source_dir_explicit:
        return False

    # (b)
    if not os.access(source_dir, os.W_OK):
        return False

    # (c)
    if not (source_dir / "skills").is_dir():
        return False

    # (d)
    parent = source_dir.parent
    if not ((parent / ".git").is_dir() or (parent / "pyproject.toml").is_file()):
        return False

    # (e) — refuse if source_dir is inside the package directory
    import quoin as _quoin_pkg

    pkg_dir = pathlib.Path(_quoin_pkg.__file__).resolve().parent
    src_resolved = source_dir.resolve()
    try:
        src_resolved.relative_to(pkg_dir)
        # Succeeded → source_dir IS inside pkg_dir → refuse
        return False
    except ValueError:
        # ValueError means not a descendant → safe
        pass

    return True


def _cmd_install(args: argparse.Namespace) -> int:
    from quoin import installer

    source_dir_explicit = args.source_dir is not None
    source_dir = _resolve_source_dir(args.source_dir)
    allow_writes = _derive_allow_writes(source_dir, source_dir_explicit)

    # T-07: prerequisites first
    missing = installer.check_prerequisites()
    if missing:
        print("quoin: Missing required tools:", file=sys.stderr)
        for tool in missing:
            print(f"       - {tool}", file=sys.stderr)
        print("\nInstall them and re-run this script.", file=sys.stderr)
        return 1
    print("Prerequisites OK")

    dest_root = pathlib.Path.home() / ".claude"

    # T-04
    installer.deploy_memory(source_dir, dest_root)
    installer.deploy_quickstart(source_dir, dest_root)

    # T-05
    installer.deploy_skills(source_dir, dest_root)
    installer.deploy_scripts(source_dir, dest_root)
    installer.deploy_core_scripts(source_dir, dest_root)
    installer.cleanup_obsolete_scripts(dest_root)

    # Hooks
    installer.deploy_hooks(source_dir, dest_root)

    # T-06
    installer.merge_workflow_rules(source_dir, dest_root, force_merge=args.force_merge)

    # T-07: preamble regeneration last
    installer.regenerate_preambles(source_dir, allow_writes=allow_writes)

    # Dev deps (if --dev)
    if args.dev:
        installer.install_dev_deps()

    # Warn if pyyaml absent (parity with install.sh lines 184-186)
    try:
        import yaml  # type: ignore[import]  # noqa: F401
    except ImportError:
        print(
            "Warning: Python package 'pyyaml' is not installed — "
            "validate_artifact.py V-01 frontmatter check will fail at runtime.",
            file=sys.stderr,
        )
        print("  Install with: pip install pyyaml", file=sys.stderr)

    return 0


def _codex_script(source_dir: pathlib.Path, name: str) -> pathlib.Path:
    script = source_dir / "adapters" / "codex" / name
    if not script.is_file():
        print(
            f"quoin: cannot find Codex adapter script {script}; "
            "pass --source-dir <path-to-clone>/quoin if needed",
            file=sys.stderr,
        )
        sys.exit(2)
    return script


def _run_codex_script(script: pathlib.Path, argv: list[str]) -> int:
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(script), *argv]
        try:
            runpy.run_path(str(script), run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            if code is None:
                return 0
            if isinstance(code, int):
                return code
            print(code, file=sys.stderr)
            return 1
    finally:
        sys.argv = old_argv
    return 0


def _cmd_codex_doctor(args: argparse.Namespace) -> int:
    source_dir = _resolve_source_dir(args.source_dir)
    project_root = pathlib.Path(args.project_root).resolve()

    readiness = _codex_script(source_dir, "verify_codex_readiness.py")
    print(f"Codex readiness: {project_root}")
    readiness_rc = _run_codex_script(
        readiness,
        ["--project-root", str(project_root)],
    )
    if readiness_rc != 0:
        return readiness_rc

    if args.smoke:
        smoke = _codex_script(source_dir, "smoke_codex_workflow.py")
        print()
        print(f"Codex smoke: {project_root}")
        return _run_codex_script(smoke, ["--project-root", str(project_root)])

    return 0


def _cmd_codex_init(args: argparse.Namespace) -> int:
    source_dir = _resolve_source_dir(args.source_dir)
    project_root = pathlib.Path(args.project_root).resolve()
    generator = _codex_script(source_dir, "generate_codex_assets.py")

    script_args = ["--project-root", str(project_root)]
    if args.check:
        script_args.append("--check")

    return _run_codex_script(generator, script_args)


def _cmd_doctor(args: argparse.Namespace) -> int:
    if args.runtime == "codex":
        return _cmd_codex_doctor(args)

    from quoin import installer
    import shutil

    errors: list[str] = []

    print(f"quoin version: {__version__}")
    print(f"Python: {sys.version.split()[0]}")
    print()

    # Prerequisites
    for tool in ("claude", "git", "gh", "npx"):
        found = shutil.which(tool) is not None
        status = "✓" if found else "✗"
        print(f"  {status} {tool}")
        if tool in ("claude", "git") and not found:
            errors.append(f"Required tool missing: {tool}")

    print()

    # Tier-1 memory files
    dest_root = pathlib.Path.home() / ".claude"
    print("Memory files (~/.claude/memory/):")
    for fname in installer.TIER1_MEMORY_FILES:
        p = dest_root / "memory" / fname
        found = p.exists()
        status = "✓" if found else "✗"
        print(f"  {status} {fname}")
        if not found:
            errors.append(f"Missing memory file: {fname}")

    print()

    # Scripts
    print("Scripts (~/.claude/scripts/):")
    for fname in installer.DEPLOYED_SCRIPTS:
        p = dest_root / "scripts" / fname
        found = p.exists()
        status = "✓" if found else "✗"
        print(f"  {status} {fname}")
        if not found:
            errors.append(f"Missing script: {fname}")

    print()

    # Skills
    print("Skills (~/.claude/skills/):")
    for skill in installer.CANONICAL_SKILLS:
        p = dest_root / "skills" / skill
        found = p.is_dir()
        status = "✓" if found else "✗"
        print(f"  {status} {skill}")
        if not found:
            errors.append(f"Missing skill: {skill}")

    print()

    # CLAUDE.md marker count
    claude_md = dest_root / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()
        marker_count = content.count("# === DEV WORKFLOW START ===")
        status = "✓" if marker_count == 1 else "✗"
        print(f"  {status} ~/.claude/CLAUDE.md — {marker_count} DEV WORKFLOW marker pair(s)")
        if marker_count != 1:
            errors.append(
                f"CLAUDE.md has {marker_count} marker pairs (expected 1); "
                "run 'quoin install --force-merge' to fix"
            )
    else:
        print("  ✗ ~/.claude/CLAUDE.md — not found")
        errors.append("CLAUDE.md not found; run 'quoin install'")

    print()
    if errors:
        print(f"doctor: {len(errors)} issue(s) found:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("doctor: all checks passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="quoin",
        description="Quoin — workflow state for stateless coding agents",
    )
    parser.add_argument("--version", action="version", version=f"quoin {__version__}")

    sub = parser.add_subparsers(dest="command")

    install_p = sub.add_parser("install", help="Deploy quoin to ~/.claude/")
    install_p.add_argument("--dev", action="store_true", help="Install dev dependencies")
    install_p.add_argument("--source-dir", metavar="PATH", help="Override data source directory")
    install_p.add_argument(
        "--upgrade",
        "--use-pip",
        dest="use_pip",
        action="store_true",
        help="Force pip reinstall before install",
    )
    install_p.add_argument(
        "--force-merge",
        action="store_true",
        help="Keep first DEV WORKFLOW marker pair; remove extra pairs",
    )

    doctor_p = sub.add_parser("doctor", help="Check quoin installation health (read-only)")
    doctor_p.add_argument(
        "--runtime",
        choices=("claude", "codex"),
        default="claude",
        help="Runtime to check; defaults to claude.",
    )
    doctor_p.add_argument(
        "--project-root",
        default=".",
        help="Project root for Codex readiness checks; defaults to the current directory.",
    )
    doctor_p.add_argument(
        "--source-dir",
        metavar="PATH",
        help="Override quoin data source directory for Codex adapter scripts.",
    )
    doctor_p.add_argument(
        "--smoke",
        action="store_true",
        help="For --runtime codex, also run the deterministic repo-local smoke check.",
    )

    codex_p = sub.add_parser("codex", help="Repo-local Codex setup helpers")
    codex_sub = codex_p.add_subparsers(dest="codex_command")

    codex_init_p = codex_sub.add_parser(
        "init",
        help="Generate or check repo-local Codex AGENTS.md",
    )
    codex_init_p.add_argument(
        "--project-root",
        default=".",
        help="Project root where AGENTS.md is generated or checked.",
    )
    codex_init_p.add_argument(
        "--check",
        action="store_true",
        help="Check AGENTS.md without writing files.",
    )
    codex_init_p.add_argument(
        "--source-dir",
        metavar="PATH",
        help="Override quoin data source directory for Codex adapter scripts.",
    )

    args = parser.parse_args(argv)

    if args.command == "install" or args.command is None:
        if args.command is None:
            # bare 'quoin' with no subcommand → install with no args
            args = install_p.parse_args([])
        return _cmd_install(args)
    elif args.command == "doctor":
        return _cmd_doctor(args)
    elif args.command == "codex":
        if args.codex_command == "init":
            return _cmd_codex_init(args)
        codex_p.print_help()
        return 1

    parser.print_help()
    return 1
