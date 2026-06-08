"""Deploy quoin artifacts to ~/.claude/ (user mode) or <project>/.claude/ (project mode)."""
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
    # Added 2026-05-15: extracted verbose sections from CLAUDE.md
    "hooks-table.md",
    "dispatch-guide.md",
    "lifecycle-guide.md",
    "cost-ledger-format.md",
)

# T-05: canonical skill list — must match quoin/skills/ on disk exactly
CANONICAL_SKILLS = (
    "architect",
    "capture_insight",
    "checkpoint",
    "cleanup",
    "continue_work",
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
    "pr",
    "review",
    "revise",
    "revise-fast",
    "rollback",
    "run",
    "sleep",
    "start_of_day",
    "status",
    "thorough_plan",
    "triage",
    "weekly_review",
)

# T-05: canonical script list — adapter scripts deployed to ~/.claude/scripts/
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
    "git_root_for_dispatch.py",
    "dispatch_sidecar.py",
    "status_graph.py",
    "dashboard_cost.py",    # T-11: dashboard adapter cost provider (D-11)
    "dashboard_server.py",  # T-11: dashboard HTTP server (D-11)
    "branch_hygiene.py",   # IVG-70: branch hygiene check wrapper
)

# T-05: obsolete artifacts to remove from prior installs (mirrors install.sh lines 170-181)
OBSOLETE_SCRIPTS = ("summarize_for_human.py", "with_env.sh", "audit_corpus_coverage.py")
OBSOLETE_TESTS = ("test_summarize_for_human.py", "test_with_env_sh.py")

# Canonical skillOverrides tier list written to settings.json on install.
# "on" = full description in every session; "name-only" = invocable via /name, no auto-suggest description.
# Only keys in this dict are touched; user-added keys for other skills are preserved.
SKILL_OVERRIDES: dict[str, str] = {
    # Core workflow skills — always show full description
    "thorough_plan": "on",
    "plan": "on",
    "critic": "on",
    "review": "on",
    "implement": "on",
    "gate": "on",
    "triage": "on",
    "checkpoint": "on",
    # Lifecycle / one-shot skills — invocable by name, no description in auto-suggest
    "pr": "name-only",
    "init_workflow": "name-only",
    "init": "name-only",          # non-quoin skill; skillOverrides applies by name regardless
    "keybindings-help": "name-only",  # non-quoin skill; same
    "start_of_day": "name-only",
    "end_of_day": "name-only",
    # Internal / rarely-typed-directly skills — name-only to stay within skill listing budget
    "sleep": "name-only",
    "cleanup": "name-only",
    "expand": "name-only",
    "cost_snapshot": "name-only",
    "status": "name-only",
    "rollback": "name-only",
    "run": "name-only",
    "weekly_review": "name-only",
    "next_steps": "name-only",
    "continue_work": "name-only",
}

_MARKER_START = "# === DEV WORKFLOW START ==="
_MARKER_END = "# === DEV WORKFLOW END ==="
DEPRECATED_SKILL_MARKERS = ("DEPRECATED LOCATION", "deprecated stub")

# ── T-06: deploy-time path substitution ──────────────────────────────────────

# File extensions that may contain __QUOIN_HOME__ placeholders.
_SUBSTITUTE_EXTS = frozenset({".md", ".py", ".sh", ".yaml", ".json", ".txt"})

# Placeholder used in source files for load-bearing ~/.claude/ references.
# Documentation-only prose keeps literal ~/.claude/... and is NOT substituted.
QUOIN_HOME_PLACEHOLDER = "__QUOIN_HOME__"

# Subdirectories under dest_root that quoin deploys to.
# assert_no_placeholders scans ONLY these (positive allowlist) to avoid
# false positives from Claude Code internal directories (projects/, todos/, etc.).
_QUOIN_DEPLOYED_SUBDIRS = frozenset({"skills", "scripts", "core", "memory", "hooks"})


def substitute_quoin_home(text: str, dest_root: pathlib.Path) -> str:
    """Replace all __QUOIN_HOME__ occurrences with str(dest_root.resolve()).

    dest_root must be absolute. Substitution is verbatim — the caller is
    responsible for only tagging load-bearing references in source files
    (per D-03 / MAJ-2: documentation-only prose stays as literal ~/.claude/).
    """
    return text.replace(QUOIN_HOME_PLACEHOLDER, str(dest_root.resolve()))


def _copy_with_substitution(
    src: pathlib.Path,
    dst: pathlib.Path,
    dest_root: pathlib.Path,
) -> None:
    """Copy src to dst, performing __QUOIN_HOME__ substitution for text files.

    Non-text extensions are byte-copied without substitution.
    Sets +x for .py and .sh files.
    """
    if src.suffix in _SUBSTITUTE_EXTS:
        dst.write_text(
            substitute_quoin_home(src.read_text(encoding="utf-8"), dest_root),
            encoding="utf-8",
        )
    else:
        shutil.copyfile(src, dst)
    if src.suffix in (".py", ".sh"):
        os.chmod(dst, 0o755)


# ── T-13: home hook conflict detection ───────────────────────────────────────

# Canonical hook script basenames registered by quoin
_QUOIN_HOOK_BASENAMES = frozenset({
    "userpromptsubmit.sh",
    "precompact.sh",
    "postcompact.sh",
    "sessionstart.sh",
    "sessionend.sh",
})


def detect_home_hook_conflict() -> bool:
    """Return True if ~/.claude/settings.json already has quoin hook stanzas.

    Detection checks both basename AND that the command path contains
    '/.claude/hooks/' to avoid false-positives from non-quoin scripts that
    happen to share the same filename.
    """
    home_settings = pathlib.Path.home() / ".claude" / "settings.json"
    if not home_settings.exists():
        return False
    try:
        data = json.loads(home_settings.read_text(encoding="utf-8"))
        hooks = data.get("hooks", {})
        for stanzas in hooks.values():
            stanza_list = stanzas if isinstance(stanzas, list) else [stanzas]
            for stanza in stanza_list:
                if not isinstance(stanza, dict):
                    continue
                for hook in stanza.get("hooks", []):
                    if not isinstance(hook, dict):
                        continue
                    cmd = hook.get("command", "")
                    basename = cmd.rsplit("/", 1)[-1]
                    if basename in _QUOIN_HOOK_BASENAMES and "/.claude/hooks/" in cmd:
                        return True
    except (json.JSONDecodeError, KeyError, OSError):
        pass
    return False


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
        _copy_with_substitution(src, dst_mem / fname, dest_root)
        print(f"Copied {fname} to {dest_root}/memory/")


def deploy_quickstart(source_dir: pathlib.Path, dest_root: pathlib.Path) -> None:
    """Copy QUICKSTART.md to dest_root/ (not under memory/)."""
    src = source_dir / "QUICKSTART.md"
    if not src.exists():
        print(f"quoin: Expected QUICKSTART.md at {src} but not found", file=sys.stderr)
        sys.exit(1)
    dest_root.mkdir(parents=True, exist_ok=True)
    _copy_with_substitution(src, dest_root / "QUICKSTART.md", dest_root)
    print(f"QUICKSTART deployed to {dest_root}/QUICKSTART.md")


# ── T-05 ──────────────────────────────────────────────────────────────────────

def _assert_not_deprecated_skill(skill_name: str, skill_md: pathlib.Path) -> None:
    content = skill_md.read_text(encoding="utf-8")
    for marker in DEPRECATED_SKILL_MARKERS:
        if marker in content:
            print(
                f"quoin: Refusing to deploy deprecated Claude skill stub for "
                f"{skill_name}: {skill_md}",
                file=sys.stderr,
            )
            sys.exit(1)


def deploy_skills(source_dir: pathlib.Path, dest_root: pathlib.Path) -> int:
    """Copy skills from source_dir/skills/ to dest_root/skills/. Returns count copied.

    When a Claude adapter SKILL.md exists at
    source_dir/adapters/claude/skills/<name>/SKILL.md, it takes precedence over
    the legacy stub at source_dir/skills/<name>/SKILL.md. This supports the
    runtime-portability migration where real skill content moves to the adapter
    path and the skills/ entry becomes a thin stub.
    """
    src_skills = source_dir / "skills"
    src_adapter = source_dir / "adapters" / "claude" / "skills"
    dst_skills = dest_root / "skills"
    count = 0
    for skill_dir in sorted(src_skills.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_name = skill_dir.name
        # Skip directories not in CANONICAL_SKILLS (e.g. Drive sync artifacts like "next_steps 2")
        if skill_name not in CANONICAL_SKILLS:
            continue
        dst_skill = dst_skills / skill_name
        dst_skill.mkdir(parents=True, exist_ok=True)
        # Prefer Claude adapter path when available (runtime-portability migration).
        adapter_md = src_adapter / skill_name / "SKILL.md"
        skill_md = adapter_md if adapter_md.exists() else skill_dir / "SKILL.md"
        if not skill_md.exists():
            print(f"quoin: Expected SKILL.md at {skill_md} but not found", file=sys.stderr)
            sys.exit(1)
        _assert_not_deprecated_skill(skill_name, skill_md)
        _copy_with_substitution(skill_md, dst_skill / "SKILL.md", dest_root)
        if adapter_md.exists():
            print(f"Deploying {skill_name} from Claude adapter path")
        preamble = skill_dir / "preamble.md"
        if preamble.exists():
            _copy_with_substitution(preamble, dst_skill / "preamble.md", dest_root)
        count += 1
    print(f"Copied {count} skills to {dest_root}/skills/")
    return count


# Portable core scripts deployed alongside the adapter wrappers in ~/.claude/scripts/.
CORE_SCRIPTS = (
    "validate_artifact.py",
    "path_resolve.py",
    "classify_critic_issues.py",
    "status_graph.py",
    "cost_event.py",              # required by dashboard_model.py (sibling core load)
    "dashboard_model.py",         # T-11: deferred from stage 1 — added here (D-11)
    "dispatch_sidecar.py",        # wrapped impl; required by ~/.claude/scripts/dispatch_sidecar.py parents[1] loader
    "git_root_for_dispatch.py",   # wrapped impl; required by ~/.claude/scripts/git_root_for_dispatch.py parents[1] loader
    "branch_hygiene.py",          # wrapped impl; required by ~/.claude/scripts/branch_hygiene.py parents[1] loader
)


def deploy_core_scripts(source_dir: pathlib.Path, dest_root: pathlib.Path) -> None:
    """Copy portable core scripts from source_dir/core/scripts/ to dest_root/core/scripts/."""
    src_core = source_dir / "core" / "scripts"
    dst_core = dest_root / "core" / "scripts"
    dst_core.mkdir(parents=True, exist_ok=True)
    for fname in CORE_SCRIPTS:
        src = src_core / fname
        if not src.exists():
            print(f"quoin: Expected core script {fname} at {src} but not found", file=sys.stderr)
            sys.exit(1)
        dst = dst_core / fname
        _copy_with_substitution(src, dst, dest_root)
        print(f"Copied core {fname} to {dest_root}/core/scripts/")


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
        _copy_with_substitution(src, dst, dest_root)
        print(f"Copied {fname} to {dest_root}/scripts/")


# T-12: Dashboard asset directory — fixed set of SPA files
_DASHBOARD_ASSETS = ("index.html", "dashboard.css", "app.js")


def deploy_dashboard_assets(source_dir: pathlib.Path, dest_root: pathlib.Path) -> None:
    """Copy the dashboard SPA assets from source_dir/core/scripts/dashboard_assets/
    to dest_root/core/scripts/dashboard_assets/.

    (a) Creates the destination directory with parents=True before copying
        (fresh-install safety — _copy_with_substitution does not mkdir).
    (b) Copies index.html, dashboard.css, app.js via _copy_with_substitution
        (no __QUOIN_HOME__ placeholders in these files; byte-copy harmless).
    (c) Fails with clear stderr + sys.exit(1) if a source asset is missing.

    Per D-11 (arch R-06): caller is _cmd_claude_install, after deploy_core_scripts.
    """
    src_assets = source_dir / "core" / "scripts" / "dashboard_assets"
    dst_assets = dest_root / "core" / "scripts" / "dashboard_assets"
    # (a) mkdir before any copy
    dst_assets.mkdir(parents=True, exist_ok=True)
    # (b) copy each asset
    for fname in _DASHBOARD_ASSETS:
        src = src_assets / fname
        if not src.exists():
            print(
                f"quoin: Expected dashboard asset {fname} at {src} but not found; "
                "ensure quoin/core/scripts/dashboard_assets/ is present in the source tree",
                file=sys.stderr,
            )
            sys.exit(1)
        dst = dst_assets / fname
        _copy_with_substitution(src, dst, dest_root)
        print(f"Copied dashboard asset {fname} to {dst_assets}/")


def _merge_skill_overrides(settings: dict) -> int:
    """Merge SKILL_OVERRIDES into settings['skillOverrides'].

    Only touches keys in SKILL_OVERRIDES. User-added keys for skills not in
    our canonical list are preserved untouched. Canonical keys are always
    set to the canonical value (user changes to canonical keys are reset on reinstall).

    Returns count of keys added or changed.
    """
    overrides = settings.setdefault("skillOverrides", {})
    changed = 0
    for skill, tier in SKILL_OVERRIDES.items():
        if overrides.get(skill) != tier:
            overrides[skill] = tier
            changed += 1
    return changed


def deploy_hooks(
    source_dir: pathlib.Path,
    dest_root: pathlib.Path,
    *,
    is_project_mode: bool = False,
) -> None:
    """Copy hook scripts and merge 7 stanzas into dest_root/settings.json.

    In project mode, hooks are scoped to <project>/.claude/settings.json only.
    Home ~/.claude/settings.json is NOT modified.

    Mirrors install.sh install_hooks() function.
    """
    hook_scripts = ("userpromptsubmit.sh", "precompact.sh", "postcompact.sh", "sessionstart.sh", "sessionend.sh", "_lib.sh", "worktreecreate.sh")
    src_hooks = source_dir / "hooks"
    dst_hooks = dest_root / "hooks"
    dst_hooks.mkdir(parents=True, exist_ok=True)

    # Copy hook scripts (with __QUOIN_HOME__ substitution for .sh files)
    for fname in hook_scripts:
        src = src_hooks / fname
        if not src.exists():
            print(f"quoin: Expected hook {fname} at {src} but not found", file=sys.stderr)
            sys.exit(1)
        dst = dst_hooks / fname
        _copy_with_substitution(src, dst, dest_root)
        print(f"Copied hook {fname} to {dest_root}/hooks/")

    # Merge 6 hook stanzas into settings.json using Python json module
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
    _append_stanza("PostCompact",      "auto",    f"{hooks_dir}/postcompact.sh",      5)
    _append_stanza("SessionStart",     "startup", f"{hooks_dir}/sessionstart.sh",     5)
    _append_stanza("SessionStart",     "resume",  f"{hooks_dir}/sessionstart.sh",     5)
    _append_stanza("SessionEnd",       "*",       f"{hooks_dir}/sessionend.sh",       5)
    _append_stanza("WorktreeCreate",   "*",       f"{hooks_dir}/worktreecreate.sh",   10)

    # Merge rm -rf / rm -fr deny rules into permissions.deny (idempotent).
    # These prevent accidental recursive deletes while still allowing plain rm.
    _DENY_RULES = [
        "Bash(rm -rf:*)",
        "Bash(rm -rf *)",
        "Bash(rm -fr:*)",
        "Bash(rm -fr *)",
    ]
    permissions = settings.setdefault("permissions", {})
    deny_list = permissions.setdefault("deny", [])
    added = 0
    for rule in _DENY_RULES:
        if rule not in deny_list:
            deny_list.append(rule)
            added += 1

    # Merge skillOverrides (idempotent — only canonical keys, user keys preserved).
    _merge_skill_overrides(settings)

    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")
    print(f"Merged 7 hook stanzas into {settings_path}")
    if added:
        print(f"Added {added} rm -rf/rm -fr deny rule(s) to {settings_path}")
    print(f"Set {len(SKILL_OVERRIDES)} skill overrides in {settings_path}")
    if is_project_mode:
        print(
            f"Hooks registered in {settings_path} (project-scoped). "
            "Home hooks (if any) are NOT removed by this install — see T-13."
        )


def cleanup_obsolete_scripts(dest_root: pathlib.Path) -> None:
    """Remove obsolete scripts from dest_root/scripts/ if present."""
    dst_scripts = dest_root / "scripts"
    for fname in OBSOLETE_SCRIPTS:
        target = dst_scripts / fname
        if target.exists():
            target.unlink()
            print(f"Removed obsolete {fname} from {dest_root}/scripts/ (Stage 5 cleanup)")
    dst_tests = dst_scripts / "tests"
    for fname in OBSOLETE_TESTS:
        target = dst_tests / fname
        if target.exists():
            target.unlink()
            print(f"Removed obsolete {fname} from {dest_root}/scripts/tests/ (Stage 5 cleanup)")


# ── T-06 ──────────────────────────────────────────────────────────────────────

def merge_workflow_rules(
    source_dir: pathlib.Path,
    dest_root: pathlib.Path,
    *,
    force_merge: bool = False,
    claude_md_path: pathlib.Path | None = None,
) -> None:
    """Merge quoin workflow rules into the target CLAUDE.md file.

    In user mode: target is dest_root/CLAUDE.md (i.e. ~/.claude/CLAUDE.md).
    In project mode (D-02): caller passes claude_md_path = dest_root.parent/CLAUDE.md
    (i.e. <project>/CLAUDE.md, NOT <project>/.claude/CLAUDE.md).

    T-05 / CRIT-4: in project mode, __QUOIN_HOME__ placeholders in the source
    CLAUDE.md are substituted with the actual dest_root before writing, so that
    the deployed rules refer to the correct project-scoped paths.
    """
    source_claude = source_dir / "CLAUDE.md"
    if not source_claude.exists():
        print(f"quoin: Expected CLAUDE.md at {source_claude} but not found", file=sys.stderr)
        sys.exit(1)

    raw_rules = source_claude.read_text(encoding="utf-8")
    # CRIT-4: substitute __QUOIN_HOME__ before embedding in the marker section
    new_rules = substitute_quoin_home(raw_rules, dest_root)
    new_section = f"{_MARKER_START}\n{new_rules}\n{_MARKER_END}"

    # Resolve target CLAUDE.md path (explicit > user-mode default)
    if claude_md_path is None:
        claude_md_path = dest_root / "CLAUDE.md"

    dest_claude = claude_md_path
    content = dest_claude.read_text(encoding="utf-8") if dest_claude.exists() else ""

    pair_count = content.count(_MARKER_START)

    if pair_count == 0:
        # behavior B: append
        dest_claude.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_claude, "a", encoding="utf-8") as f:
            f.write(f"\n{_MARKER_START}\n{new_rules}\n{_MARKER_END}\n")
        print(f"Appended quoin rules to {dest_claude}")

    elif pair_count == 1:
        # behavior A: replace (DOTALL — spans newlines)
        updated = re.sub(
            rf"{re.escape(_MARKER_START)}.*?{re.escape(_MARKER_END)}",
            new_section,
            content,
            flags=re.DOTALL,
        )
        dest_claude.write_text(updated, encoding="utf-8")
        print(f"Updated quoin section in {dest_claude}")

    else:
        # pair_count > 1
        if not force_merge:
            # behavior C: abort with recovery hint
            print(
                f"quoin: {dest_claude} contains {pair_count} '# === DEV WORKFLOW' marker pairs "
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
            dest_claude.write_text(result, encoding="utf-8")
            print(
                f"Updated quoin section in {dest_claude} "
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


def deploy_agentdesk(source_dir: pathlib.Path, dest_agentdesk_dir: pathlib.Path) -> None:
    """Copy agentdesk tool files to dest_agentdesk_dir (~/.config/agentdesk/).

    If source files are missing, logs a warning and returns without error.
    agentdesk is an optional user-level tool; its absence must not abort install.
    """
    src_agentdesk = source_dir / "tools" / "agentdesk"
    if not src_agentdesk.exists():
        print(f"[warn] agentdesk source not found: {src_agentdesk}", file=sys.stderr)
        return

    dest_agentdesk_dir.mkdir(parents=True, exist_ok=True)

    # Copy agentdesk.zsh — _copy_with_substitution only sets +x for .py/.sh,
    # so we call os.chmod explicitly for the .zsh file.
    _copy_with_substitution(
        src_agentdesk / "agentdesk.zsh",
        dest_agentdesk_dir / "agentdesk.zsh",
        dest_agentdesk_dir,
    )
    os.chmod(dest_agentdesk_dir / "agentdesk.zsh", 0o755)

    # Copy setup-agentdesk.sh — .sh extension, _copy_with_substitution sets +x.
    _copy_with_substitution(
        src_agentdesk / "setup-agentdesk.sh",
        dest_agentdesk_dir / "setup-agentdesk.sh",
        dest_agentdesk_dir,
    )

    print(f"Deployed agentdesk to {dest_agentdesk_dir}")


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
    print(f"Regenerated subagent preambles in {source_dir}/skills/*/preamble.md")


def assert_no_placeholders(dest_root: pathlib.Path) -> list[str]:
    """Return list of 'path:line_no' strings where __QUOIN_HOME__ was found after deploy.

    Call this after all deploy functions complete to verify substitution was fully applied.
    Only scans quoin-deployed paths (root-level files + _QUOIN_DEPLOYED_SUBDIRS) to avoid
    false positives from Claude Code internal directories (projects/, todos/, etc.).
    """
    violations: list[str] = []
    check_exts = (".md", ".sh", ".py", ".json", ".yaml", ".txt")

    def _scan_file(p: pathlib.Path) -> None:
        if p.is_file() and p.suffix in check_exts:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if "__QUOIN_HOME__" in line:
                        violations.append(f"{p}:{i}")
            except Exception:
                pass

    # 1. Root-level files only (CLAUDE.md, QUICKSTART.md, settings.json, etc.)
    for entry in dest_root.iterdir():
        if entry.is_file():
            _scan_file(entry)

    # 2. Quoin-deployed subdirectories only
    for subdir_name in _QUOIN_DEPLOYED_SUBDIRS:
        subdir = dest_root / subdir_name
        if subdir.is_dir():
            for p in subdir.rglob("*"):
                _scan_file(p)

    return violations


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
