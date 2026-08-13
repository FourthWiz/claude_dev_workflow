"""quoin router — opt-in claude-code-router (CCR) setup and status commands.

This module must NOT import from installer.py (D-01 / D-02).
All handlers always return int; never call cli._abort or sys.exit (D-07).
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
from typing import Any

from quoin.ccr_config import (
    CcrConfigError,
    backup_config,
    ccr_config_path,
    load_config,
    merge_openrouter_provider,
    merge_router_keys,
    probe_service,
    read_openrouter_key,
    write_config,
)

# ── Default model table (editable via ~/.config/quoin/models.json) ─────────────
# Values are OpenRouter model slugs verified August 2026.
DEFAULT_MODELS: dict[str, str] = {
    "haiku": "deepseek/deepseek-v4-flash",
    "sonnet": "deepseek/deepseek-v4-pro",
    "opus": "z-ai/glm-5.2",
}

# CCR Router key mapping (request-classification keys, not Anthropic tiers — D-05).
# Values use the "provider,model" format CCR expects.
# Default snapshot only — _cmd_router_setup now builds its Router map from the
# effective (models.json-merged) table via models.build_router_map (D-02).
ROUTER_MAP: dict[str, str] = {
    "default": f"openrouter,{DEFAULT_MODELS['sonnet']}",
    "background": f"openrouter,{DEFAULT_MODELS['haiku']}",
    "think": f"openrouter,{DEFAULT_MODELS['opus']}",
    "longContext": f"openrouter,{DEFAULT_MODELS['sonnet']}",
}


def quoin_models_path(home: pathlib.Path | None = None) -> pathlib.Path:
    """Return ~/.config/quoin/models.json (agentdesk precedent; outside deploy tree)."""
    base = home if home is not None else pathlib.Path.home()
    return base / ".config" / "quoin" / "models.json"


def seed_models_file_if_absent(
    path: pathlib.Path,
    defaults: dict[str, str],
) -> bool:
    """Write defaults to path ONLY if it does not already exist.

    Never overwrites an existing file (user edits preserved).
    Writes slugs only — the OPENROUTER_API_KEY is never stored here.
    Returns True if the file was seeded, False if it already existed.
    """
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(defaults, f, indent=2)
        f.write("\n")
    return True


# ── Injectable seams (monkeypatched by tests so CI never shells to npm) ─────────

def _node_present() -> bool:
    """Return True if node or npx is on PATH."""
    return bool(shutil.which("node") or shutil.which("npx"))


def _install_ccr() -> int:
    """Run npm install -g @musistudio/claude-code-router. Return exit code."""
    result = subprocess.run(
        ["npm", "install", "-g", "@musistudio/claude-code-router"],
    )
    return result.returncode


def _verify_ccr() -> bool:
    """Return True if the ccr binary resolves and responds to a version query."""
    if not shutil.which("ccr"):
        return False
    # Try ccr -v, fall back to ccr version; both with capture_output=True to
    # prevent banner pollution in router status / doctor output.
    for cmd in (["ccr", "-v"], ["ccr", "version"]):
        try:
            result = subprocess.run(cmd, capture_output=True)
            if result.returncode == 0:
                return True
        except FileNotFoundError:
            return False
    return False


# ── Command handlers ───────────────────────────────────────────────────────────

def _cmd_router_setup(args: argparse.Namespace) -> int:
    """quoin router setup — install CCR and scaffold the OpenRouter config.

    Always returns int; never calls cli._abort or sys.exit (D-07).
    Implements proc:R-setup with probe-first install (D-06).
    """
    dry_run: bool = getattr(args, "dry_run", False)
    home_override: pathlib.Path | None = getattr(args, "_home_override", None)

    # ── Step 1: Node precheck ──────────────────────────────────────────────────
    if not _node_present():
        print(
            "quoin: Node.js is required to install claude-code-router.\n"
            "Install it from https://nodejs.org (LTS recommended), then re-run.",
            file=sys.stderr,
        )
        return 1

    # ── Step 2: Probe-first install (D-06) ────────────────────────────────────
    if not _verify_ccr():
        print("Installing claude-code-router globally...")
        rc = _install_ccr()
        if rc != 0:
            print(
                f"quoin: npm install failed (exit {rc}).\n"
                "If you see a permissions error, try:\n"
                "  sudo npm install -g @musistudio/claude-code-router\n"
                "or use a Node version manager (nvm, fnm) to avoid sudo.",
                file=sys.stderr,
            )
            return rc
        if not _verify_ccr():
            print(
                "quoin: ccr was installed but is not on PATH.\n"
                "Add npm's global bin directory to your PATH, then re-run.\n"
                "Tip: run `npm bin -g` to find the directory.",
                file=sys.stderr,
            )
            return 1
        print("claude-code-router installed successfully.")
    else:
        print("claude-code-router already installed — skipping npm install.")

    # ── Step 3: Read API key ───────────────────────────────────────────────────
    try:
        key = read_openrouter_key()
    except CcrConfigError as exc:
        print(f"quoin: {exc}", file=sys.stderr)
        return 1

    # ── Step 4: Backup, load, merge, write ────────────────────────────────────
    config_path = ccr_config_path(home=home_override)
    backup = backup_config(config_path)
    cfg = load_config(config_path)

    # Function-local import — a module-level import here creates a circular
    # ImportError, since models.py back-imports DEFAULT_MODELS from this
    # module at module scope (D-01).
    from quoin.models import build_router_map, read_effective_models

    effective = read_effective_models(home=home_override)
    models_list = list(effective.values())
    cfg, prov_changes = merge_openrouter_provider(cfg, key, models_list)
    cfg, rk_changes, rk_warnings = merge_router_keys(cfg, build_router_map(effective))

    # ── Step 5: Build summary ─────────────────────────────────────────────────
    summary_lines = ["", "quoin router setup — changes:"]
    for change in prov_changes + rk_changes:
        summary_lines.append(f"  + {change}")
    if backup:
        summary_lines.append(f"  Backed up existing config to: {backup}")
    for warning in rk_warnings:
        summary_lines.append(f"  ⚠ {warning}")
    for tier in ("haiku", "sonnet", "opus"):
        origin = "default" if effective[tier] == DEFAULT_MODELS.get(tier) else "user"
        summary_lines.append(f"  {tier}: {effective[tier]} ({origin})")
    summary_lines.append(f"  Config path: {config_path}")
    summary = "\n".join(summary_lines)

    if dry_run:
        print(summary)
        print("\n[dry-run] No files written.")
        return 0

    # ── Step 6: Write config ───────────────────────────────────────────────────
    write_config(config_path, cfg)

    # ── Step 7: Seed models file if absent ────────────────────────────────────
    models_path = quoin_models_path(home=home_override)
    seeded = seed_models_file_if_absent(models_path, DEFAULT_MODELS)

    print(summary)
    if seeded:
        print(f"  Seeded model defaults to: {models_path}")
    else:
        print(f"  Model defaults file already exists (user edits preserved): {models_path}")

    print(
        "\nTo use open models:  ccr code    (auto-starts the proxy; quoin skills work normally)"
        "\nTo use native models: claude"
        "\n\nSanity-check: inside a `ccr code` session, type /help — the quoin skill list should resolve."
    )
    return 0


def _cmd_router_status(args: argparse.Namespace) -> int:
    """quoin router status — read-only report. Always returns 0 (D-07).

    Implements proc:R-status: derives active launch mode from liveness + config,
    never from config alone.
    """
    home_override: pathlib.Path | None = getattr(args, "_home_override", None)

    installed = _verify_ccr() or bool(shutil.which("ccr"))
    config_path = ccr_config_path(home=home_override)
    cfg_present = config_path.exists()
    live = probe_service()
    key_set = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())

    if live and cfg_present:
        mode = "open via CCR (proxy running)"
    elif cfg_present and not live:
        mode = "native (CCR configured but proxy not running — run `ccr code` to start)"
    else:
        mode = "native"

    print("quoin router status:")
    print(f"  CCR installed:  {'yes' if installed else 'no'}")
    print(f"  Config present: {'yes' if cfg_present else 'no'}  ({config_path})")
    print(f"  Proxy running:  {'yes' if live else 'no'}  (127.0.0.1:3456)")
    print(f"  API key set:    {'yes' if key_set else 'no'}  (OPENROUTER_API_KEY)")
    print(f"  Active mode:    {mode}")
    return 0
