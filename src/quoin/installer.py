"""Deploy quoin artifacts to ~/.claude/."""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

# T-04: single source of truth for wheel-bundled memory files (8 Tier-1 files)
TIER1_MEMORY_FILES = (
    "terse-rubric.md",
    "format-kit.md",
    "glossary.md",
    "format-kit.sections.json",
    "summary-prompt.md",
    "format-kit-pitfalls.md",
    "sleep-signals.yaml",
    "cache-guide.md",
)

# T-05: canonical skill list — must match quoin/skills/ on disk exactly
CANONICAL_SKILLS = (
    "architect",
    "capture_insight",
    "checkpoint",
    "cost_snapshot",
    "critic",
    "discover",
    "end_of_day",
    "end_of_task",
    "expand",
    "gate",
    "implement",
    "init_workflow",
    "next_steps",
    "plan",
    "review",
    "revise",
    "revise-fast",
    "rollback",
    "run",
    "sleep",
    "start_of_day",
    "thorough_plan",
    "triage",
    "weekly_review",
)

# T-05: canonical script list — all 9 scripts deployed to ~/.claude/scripts/
DEPLOYED_SCRIPTS = (
    "validate_artifact.py",
    "path_resolve.py",
    "cost_from_jsonl.py",
    "classify_critic_issues.py",
    "build_preambles.py",
    "session_age_guard.py",
    "pidfile_helpers.sh",
    "sleep_score.py",
    "analyze_cost_ledger.py",
)

# T-05: obsolete artifacts to remove from prior installs (mirrors install.sh lines 170-181)
OBSOLETE_SCRIPTS = ("summarize_for_human.py", "with_env.sh", "audit_corpus_coverage.py")
OBSOLETE_TESTS = ("test_summarize_for_human.py", "test_with_env_sh.py")

_MARKER_START = "# === DEV WORKFLOW START ==="
_MARKER_END = "# === DEV WORKFLOW END ==="


# ── T-04 ──────────────────────────────────────────────────────────────────────

def deploy_memory(source_dir: pathlib.Path, dest_root: pathlib.Path) -> None:
    """Copy Tier-1 memory files from source_dir/memory/ to dest_root/memory/."""
    src_mem = source_dir / "memory"
    dst_mem = dest_root / "memory"
    dst_mem.mkdir(parents=True, exist_ok=True)
    for fname in TIER1_MEMORY_FILES:
        src = src_mem / fname
        if not src.exists():
            print(f"quoin: Expected {fname} at {src} but not found", file=sys.stderr)
            sys.exit(1)
        shutil.copyfile(src, dst_mem / fname)
        print(f"Copied {fname} to ~/.claude/memory/")


def deploy_quickstart(source_dir: pathlib.Path, dest_root: pathlib.Path) -> None:
    """Copy QUICKSTART.md to dest_root/ (not under memory/)."""
    src = source_dir / "QUICKSTART.md"
    if not src.exists():
        print(f"quoin: Expected QUICKSTART.md at {src} but not found", file=sys.stderr)
        sys.exit(1)
    dest_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest_root / "QUICKSTART.md")
    print("QUICKSTART deployed to ~/.claude/QUICKSTART.md")


# ── T-05 ──────────────────────────────────────────────────────────────────────

def deploy_skills(source_dir: pathlib.Path, dest_root: pathlib.Path) -> int:
    """Copy skills from source_dir/skills/ to dest_root/skills/. Returns count copied."""
    src_skills = source_dir / "skills"
    dst_skills = dest_root / "skills"
    count = 0
    for skill_dir in sorted(src_skills.iterdir()):
        if not skill_dir.is_dir():
            continue
        dst_skill = dst_skills / skill_dir.name
        dst_skill.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            print(f"quoin: Expected SKILL.md at {skill_md} but not found", file=sys.stderr)
            sys.exit(1)
        shutil.copyfile(skill_md, dst_skill / "SKILL.md")
        preamble = skill_dir / "preamble.md"
        if preamble.exists():
            shutil.copyfile(preamble, dst_skill / "preamble.md")
        count += 1
    print(f"Copied {count} skills to ~/.claude/skills/")
    return count


def deploy_scripts(source_dir: pathlib.Path, dest_root: pathlib.Path) -> None:
    """Copy scripts from source_dir/scripts/ to dest_root/scripts/."""
    src_scripts = source_dir / "scripts"
    dst_scripts = dest_root / "scripts"
    dst_scripts.mkdir(parents=True, exist_ok=True)
    for fname in DEPLOYED_SCRIPTS:
        src = src_scripts / fname
        if not src.exists():
            print(f"quoin: Expected {fname} at {src} but not found", file=sys.stderr)
            sys.exit(1)
        dst = dst_scripts / fname
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o755)
        print(f"Copied {fname} to ~/.claude/scripts/")


def deploy_hooks(source_dir: pathlib.Path, dest_root: pathlib.Path) -> None:
    """Copy hook scripts and merge 5 stanzas into dest_root/../settings.json.

    Mirrors install.sh install_hooks() function. When jq is absent, writes
    HOOK_MERGE_TODO.md and returns without modifying settings.json.
    """
    hook_scripts = ("userpromptsubmit.sh", "precompact.sh", "sessionstart.sh", "sessionend.sh", "_lib.sh")
    src_hooks = source_dir / "hooks"
    dst_hooks = dest_root / "hooks"
    dst_hooks.mkdir(parents=True, exist_ok=True)

    # Copy hook scripts
    for fname in hook_scripts:
        src = src_hooks / fname
        if not src.exists():
            print(f"quoin: Expected hook {fname} at {src} but not found", file=sys.stderr)
            sys.exit(1)
        dst = dst_hooks / fname
        shutil.copyfile(src, dst)
        os.chmod(dst, 0o755)
        print(f"Copied hook {fname} to ~/.claude/hooks/")

    # Merge 5 hook stanzas into settings.json using Python json module
    # settings.json lives inside dest_root (~/.claude/settings.json)
    settings_path = dest_root / "settings.json"

    # Load existing settings or start fresh
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            # Back up the broken file with a timestamp so prior backups are preserved
            ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            backup = settings_path.parent / f"{settings_path.name}.bak-{ts}"
            shutil.copyfile(settings_path, backup)
            print(
                f"quoin: settings.json parse error ({exc}); backed up to {backup} and starting fresh",
                file=sys.stderr,
            )
            settings = {}
    else:
        settings = {}

    hooks = settings.setdefault("hooks", {})

    # Helper: append a stanza, replacing any existing entry for the same
    # (matcher, script-filename) pair — mirrors install.sh jq dedup semantics.
    def _append_stanza(event: str, matcher: str, command: str, timeout: int) -> None:
        stanza = {
            "matcher": matcher,
            "hooks": [{"type": "command", "command": command, "timeout": timeout}],
        }
        event_list = hooks.setdefault(event, [])
        script_name = command.rsplit("/", 1)[-1]
        # Remove stale entries for the same matcher + script filename (handles path changes)
        event_list[:] = [
            s for s in event_list
            if not (
                s.get("matcher") == matcher
                and any(
                    h.get("command", "").endswith(script_name)
                    for h in s.get("hooks", [])
                )
            )
        ]
        event_list.append(stanza)

    hooks_dir = str(dest_root.resolve() / "hooks")
    _append_stanza("UserPromptSubmit", "*",       f"{hooks_dir}/userpromptsubmit.sh", 5)
    _append_stanza("PreCompact",       "auto",    f"{hooks_dir}/precompact.sh",       10)
    _append_stanza("SessionStart",     "startup", f"{hooks_dir}/sessionstart.sh",     5)
    _append_stanza("SessionStart",     "resume",  f"{hooks_dir}/sessionstart.sh",     5)
    _append_stanza("SessionEnd",       "*",       f"{hooks_dir}/sessionend.sh",       5)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print("Merged 5 hook stanzas into ~/.claude/settings.json")


def cleanup_obsolete_scripts(dest_root: pathlib.Path) -> None:
    """Remove obsolete scripts from dest_root/scripts/ if present."""
    dst_scripts = dest_root / "scripts"
    for fname in OBSOLETE_SCRIPTS:
        target = dst_scripts / fname
        if target.exists():
            target.unlink()
            print(f"Removed obsolete {fname} from ~/.claude/scripts/ (Stage 5 cleanup)")
    dst_tests = dst_scripts / "tests"
    for fname in OBSOLETE_TESTS:
        target = dst_tests / fname
        if target.exists():
            target.unlink()
            print(f"Removed obsolete {fname} from ~/.claude/scripts/tests/ (Stage 5 cleanup)")


# ── T-06 ──────────────────────────────────────────────────────────────────────

def merge_workflow_rules(
    source_dir: pathlib.Path,
    dest_root: pathlib.Path,
    *,
    force_merge: bool = False,
) -> None:
    """Merge quoin workflow rules into dest_root/CLAUDE.md."""
    source_claude = source_dir / "CLAUDE.md"
    if not source_claude.exists():
        print(f"quoin: Expected CLAUDE.md at {source_claude} but not found", file=sys.stderr)
        sys.exit(1)

    new_rules = source_claude.read_text()
    new_section = f"{_MARKER_START}\n{new_rules}\n{_MARKER_END}"

    dest_claude = dest_root / "CLAUDE.md"
    content = dest_claude.read_text() if dest_claude.exists() else ""

    pair_count = content.count(_MARKER_START)

    if pair_count == 0:
        # behavior B: append
        dest_root.mkdir(parents=True, exist_ok=True)
        with open(dest_claude, "a") as f:
            f.write(f"\n{_MARKER_START}\n{new_rules}\n{_MARKER_END}\n")
        print("Appended quoin rules to ~/.claude/CLAUDE.md")

    elif pair_count == 1:
        # behavior A: replace (DOTALL — spans newlines)
        updated = re.sub(
            rf"{re.escape(_MARKER_START)}.*?{re.escape(_MARKER_END)}",
            new_section,
            content,
            flags=re.DOTALL,
        )
        dest_claude.write_text(updated)
        print("Updated quoin section in ~/.claude/CLAUDE.md")

    else:
        # pair_count > 1
        if not force_merge:
            # behavior C: abort with recovery hint
            print(
                f"quoin: ~/.claude/CLAUDE.md contains {pair_count} '# === DEV WORKFLOW' marker pairs "
                f"(expected 0 or 1); run 'quoin doctor' to inspect, OR re-run "
                f"'quoin install --force-merge' to keep the first pair and remove the rest",
                file=sys.stderr,
            )
            sys.exit(2)
        else:
            # behavior D: keep first pair (with new content), delete the rest
            pattern = re.compile(
                rf"{re.escape(_MARKER_START)}.*?{re.escape(_MARKER_END)}",
                re.DOTALL,
            )
            matches = list(pattern.finditer(content))
            extra_count = len(matches) - 1

            # Emit per-deletion stderr warnings (compute line numbers before modifying)
            for m in matches[1:]:
                line_no = content[: m.start()].count("\n") + 1
                print(
                    f"quoin: removed extra '# === DEV WORKFLOW' marker pair at line {line_no}",
                    file=sys.stderr,
                )

            # Remove extra pairs from end to preserve earlier positions
            result = content
            for m in reversed(matches[1:]):
                result = result[: m.start()] + result[m.end() :]

            # Replace the first pair (now the only one) with new content
            result = re.sub(
                rf"{re.escape(_MARKER_START)}.*?{re.escape(_MARKER_END)}",
                new_section,
                result,
                count=1,
                flags=re.DOTALL,
            )
            dest_claude.write_text(result)
            print(
                f"Updated quoin section in ~/.claude/CLAUDE.md "
                f"(--force-merge: removed {extra_count} extra marker pairs)"
            )


# ── T-07 ──────────────────────────────────────────────────────────────────────

def check_prerequisites() -> list[str]:
    """Return list of missing required tools; warn about optional ones."""
    missing: list[str] = []
    if shutil.which("claude") is None:
        missing.append("claude (Claude Code CLI)")
    if shutil.which("git") is None:
        missing.append("git")
    if shutil.which("gh") is None:
        print(
            "Warning: gh (GitHub CLI) not found — /end_of_task push will still work, but PR creation won't.",
            file=sys.stderr,
        )
    if shutil.which("npx") is None:
        print(
            "Warning: npx not found — cost tracking in /end_of_task requires npx "
            "(install Node.js from https://nodejs.org).",
            file=sys.stderr,
        )
    return missing


def regenerate_preambles(source_dir: pathlib.Path, *, allow_writes: bool) -> None:
    """Regenerate subagent preambles if running from a writable working tree."""
    if not allow_writes:
        print("Skipping preamble regeneration (wheel install — using preambles shipped in package)")
        return
    import runpy

    script = source_dir / "scripts" / "build_preambles.py"
    # Isolate sys.argv so build_preambles.py's argparse sees only its own script name
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(script)]
        runpy.run_path(str(script), run_name="__main__")
    finally:
        sys.argv = old_argv
    print(f"Regenerated 7 subagent preambles in {source_dir}/skills/*/preamble.md")


def install_dev_deps() -> None:
    """Install dev Python dependencies via pip (uses quoin[dev] extras)."""
    if shutil.which("pip3") is None and shutil.which("pip") is None:
        print(
            "Warning: pip not found — install quoin[dev] manually for dev tests",
            file=sys.stderr,
        )
        return
    pip_cmd = shutil.which("pip3") or shutil.which("pip")
    result = subprocess.run(
        [pip_cmd, "install", "--user", "--upgrade", "quoin[dev]"],
    )
    if result.returncode != 0:
        print(
            "Warning: pip install failed; install quoin[dev] manually for dev tests",
            file=sys.stderr,
        )
