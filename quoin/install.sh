#!/usr/bin/env bash
# Quoin installer — offline-first thin wrapper that delegates to `quoin install`.
#
# Usage: bash install.sh [--dev] [--upgrade] [--use-pip] [--force-merge]
#                        [--scope user|project[:DIR]] [--allow-hook-merge] [-h]
#
# Tier 1 (fast, no network): installed version matches local → exec quoin install
# Tier 2 (offline stdlib):   quoin not installed → PYTHONPATH=src/ exec python -m quoin
# Tier 3 (network, opt-in):  version mismatch or --upgrade/--use-pip → pip install -e .
#
# Agentdesk: the Python installer (quoin install) deploys agentdesk tool files to
# ~/.config/agentdesk/ automatically for user-mode installs. After quoin install
# completes, it will print a hint to run setup-agentdesk.sh for the full setup
# (installs zellij, lazygit, fzf via Homebrew and patches ~/.zshrc). That step
# is intentionally NOT auto-run here — it modifies system state and requires
# explicit user consent.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Argument parsing ──────────────────────────────────────────────────────────
DEV_FLAG=""
FORCE_MERGE_FLAG=""
SCOPE_FLAG=""
ALLOW_HOOK_MERGE_FLAG=""
USE_PIP=0
PIP_UPGRADE_FLAG=""

# Two-pass arg loop: consume --scope value (which may be a separate token or
# combined as --scope=project:/path).  We collect non-consumed args in REST so
# that unknown flags still get the "ignored" warning.
REST=()
i=0
ARGS=("$@")
while [[ $i -lt ${#ARGS[@]} ]]; do
  arg="${ARGS[$i]}"
  case "$arg" in
    --dev)          DEV_FLAG="--dev" ;;
    --upgrade)      USE_PIP=1; PIP_UPGRADE_FLAG="--upgrade" ;;
    --use-pip)      USE_PIP=1 ;;
    --force-merge)  FORCE_MERGE_FLAG="--force-merge" ;;
    --allow-hook-merge) ALLOW_HOOK_MERGE_FLAG="--allow-hook-merge" ;;
    --scope=*)      SCOPE_FLAG="--scope ${arg#--scope=}" ;;
    --scope)
      i=$(( i + 1 ))
      if [[ $i -lt ${#ARGS[@]} ]]; then
        SCOPE_FLAG="--scope ${ARGS[$i]}"
      else
        echo "quoin: --scope requires a value (user or project[:DIR])" >&2
        exit 2
      fi
      ;;
    -h|--help)
      echo "Usage: bash install.sh [--dev] [--upgrade] [--use-pip] [--force-merge]"
      echo "                       [--scope user|project[:DIR]] [--allow-hook-merge]"
      echo "  --dev                Install dev dependencies (pyyaml, pytest)"
      echo "  --upgrade            Re-install via pip before deploying (alias: --use-pip)"
      echo "  --use-pip            Same as --upgrade"
      echo "  --force-merge        Keep first DEV WORKFLOW marker pair; remove extras"
      echo "  --scope user         Install globally under ~/.claude/"
      echo "  --scope project      Install under <CWD>/.claude/ instead of ~/.claude/."
      echo "                       All skills, scripts, hooks, and CLAUDE.md will be"
      echo "                       project-scoped. Hooks register in <project>/.claude/settings.json"
      echo "                       only. Note: for skills, Claude Code personal scope overrides"
      echo "                       project scope — a prior home install shadows project skills."
      echo "                       Run 'quoin doctor --scope project' to detect conflicts."
      echo "  --scope project:/path Install under /path/.claude/ (explicit project root)"
      echo "  --allow-hook-merge   Proceed even if home ~/.claude/settings.json has quoin"
      echo "                       hook stanzas (default: fail-fast to avoid double-fire)"
      exit 0
      ;;
    *)  REST+=("$arg") ;;
  esac
  i=$(( i + 1 ))
done

for unknown in "${REST[@]+"${REST[@]}"}"; do
  echo "Warning: unknown argument: $unknown (ignored)" >&2
done

# ── Find Python interpreter ───────────────────────────────────────────────────
# quoin requires Python 3.10+. Try versioned candidates first so a newer
# interpreter is preferred over an older default (e.g. pyenv global pointing
# to 3.8 when python3.12 is also available on PATH).
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    _ver=$("$candidate" -c \
      "import sys; v=sys.version_info; print(v.major * 1000 + v.minor)" \
      2>/dev/null || echo "0")
    if [[ "$_ver" -ge 3010 ]]; then
      PYTHON="$candidate"
      break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "quoin: Python 3.10+ required but not found." \
       "Install Python 3.10+ and ensure it appears in PATH." >&2
  exit 1
fi

# ── Interactive scope prompt (when --scope not provided) ─────────────────────
if [[ -z "$SCOPE_FLAG" ]]; then
  if [[ -t 0 ]]; then
    echo ""
    echo "Where should quoin install?"
    echo "  g) Global  — ~/.claude/  (all Claude Code sessions on this machine)"
    echo "  p) Project — ./.claude/  (this project only)"
    echo ""
    while true; do
      read -rp "Choose [g/p] (default: g): " _scope_answer
      case "${_scope_answer:-g}" in
        g|G|global|user)  SCOPE_FLAG="--scope user";    break ;;
        p|P|project)      SCOPE_FLAG="--scope project"; break ;;
        *) echo "Please enter 'g' for global or 'p' for project." ;;
      esac
    done
  else
    echo "quoin: non-interactive mode — defaulting to --scope user (global ~/.claude/)" >&2
    SCOPE_FLAG="--scope user"
  fi
fi

# Build forwarded args for `quoin install` (array preserves paths with spaces)
INSTALL_ARGS=("install" "--source-dir" "$SCRIPT_DIR")
[[ -n "$DEV_FLAG" ]]              && INSTALL_ARGS+=("$DEV_FLAG")
[[ -n "$FORCE_MERGE_FLAG" ]]      && INSTALL_ARGS+=("$FORCE_MERGE_FLAG")
# Forward --scope flag (stored as "--scope value" string; split into two tokens)
if [[ -n "$SCOPE_FLAG" ]]; then
  # Split "--scope value" into separate array elements (handles project:/path with colon)
  read -r _scope_key _scope_val <<< "$SCOPE_FLAG"
  INSTALL_ARGS+=("$_scope_key" "$_scope_val")
fi
[[ -n "$ALLOW_HOOK_MERGE_FLAG" ]] && INSTALL_ARGS+=("$ALLOW_HOOK_MERGE_FLAG")

# ── Get versions ──────────────────────────────────────────────────────────────
LOCAL_VERSION="$(PYTHONPATH="$PROJECT_ROOT/src" "$PYTHON" -c \
  'from quoin.__about__ import __version__; print(__version__)' 2>/dev/null || true)"

INSTALLED_VERSION="$("$PYTHON" -m quoin --version 2>/dev/null | \
  awk '{print $2}' || true)"

# ── Tier 1: installed version matches local — no pip needed ───────────────────
if [[ -n "$INSTALLED_VERSION" && -n "$LOCAL_VERSION" \
      && "$INSTALLED_VERSION" == "$LOCAL_VERSION" && "$USE_PIP" -eq 0 ]]; then
  exec "$PYTHON" -m quoin "${INSTALL_ARGS[@]}"
fi

# ── Tier 2: quoin not normally importable — use PYTHONPATH src/ fallback ─────
if ! "$PYTHON" -c 'import quoin' 2>/dev/null; then
  if PYTHONPATH="$PROJECT_ROOT/src" "$PYTHON" -c 'import quoin' 2>/dev/null; then
    exec env PYTHONPATH="$PROJECT_ROOT/src" "$PYTHON" -m quoin "${INSTALL_ARGS[@]}"
  fi
fi

# ── Tier 3: pip install (version mismatch, empty install, or explicit --upgrade)
if [[ "$USE_PIP" -eq 1 ]] \
   || [[ -z "$INSTALLED_VERSION" ]] \
   || [[ "$INSTALLED_VERSION" != "$LOCAL_VERSION" ]]; then
  "$PYTHON" -m pip install --user $PIP_UPGRADE_FLAG -e "$PROJECT_ROOT"

  # Post-pip import gate (MAJ-2 round-4 fix)
  if ! "$PYTHON" -c 'import quoin' 2>/dev/null; then
    IMPORTABLE=no
    echo "wrapper logic error — INSTALLED_VERSION=$INSTALLED_VERSION, LOCAL_VERSION=$LOCAL_VERSION, src/quoin importable=$IMPORTABLE; please file an issue with this output" >&2
    exit 1
  fi

  exec "$PYTHON" -m quoin "${INSTALL_ARGS[@]}"
fi

# ── Defensive abort (should be unreachable) ──────────────────────────────────
IMPORTABLE="$(PYTHONPATH="$PROJECT_ROOT/src" "$PYTHON" -c 'import quoin' 2>/dev/null \
  && echo yes || echo no)"
echo "wrapper logic error — INSTALLED_VERSION=$INSTALLED_VERSION, LOCAL_VERSION=$LOCAL_VERSION, src/quoin importable=$IMPORTABLE; please file an issue with this output" >&2
exit 1
