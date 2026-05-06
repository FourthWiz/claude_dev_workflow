#!/usr/bin/env bash
# Quoin installer — offline-first thin wrapper that delegates to `quoin install`.
#
# Usage: bash install.sh [--dev] [--upgrade] [--use-pip] [--force-merge] [-h]
#
# Tier 1 (fast, no network): installed version matches local → exec quoin install
# Tier 2 (offline stdlib):   quoin not installed → PYTHONPATH=src/ exec python -m quoin
# Tier 3 (network, opt-in):  version mismatch or --upgrade/--use-pip → pip install -e .
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ── Argument parsing ──────────────────────────────────────────────────────────
DEV_FLAG=""
FORCE_MERGE_FLAG=""
USE_PIP=0
PIP_UPGRADE_FLAG=""

for arg in "$@"; do
  case "$arg" in
    --dev)          DEV_FLAG="--dev" ;;
    --upgrade)      USE_PIP=1; PIP_UPGRADE_FLAG="--upgrade" ;;
    --use-pip)      USE_PIP=1 ;;
    --force-merge)  FORCE_MERGE_FLAG="--force-merge" ;;
    -h|--help)
      echo "Usage: bash install.sh [--dev] [--upgrade] [--use-pip] [--force-merge]"
      echo "  --dev          Install dev dependencies (pyyaml, pytest)"
      echo "  --upgrade      Re-install via pip before deploying (alias: --use-pip)"
      echo "  --use-pip      Same as --upgrade"
      echo "  --force-merge  Keep first DEV WORKFLOW marker pair; remove extras"
      exit 0
      ;;
    *)  echo "Warning: unknown argument: $arg (ignored)" >&2 ;;
  esac
done

# ── Find Python interpreter ───────────────────────────────────────────────────
PYTHON=""
for candidate in python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "quoin: No Python interpreter found (tried python3, python). Install Python 3.10+." >&2
  exit 1
fi

# Build forwarded args for `quoin install` (array preserves paths with spaces)
INSTALL_ARGS=("install" "--source-dir" "$SCRIPT_DIR")
[[ -n "$DEV_FLAG" ]]         && INSTALL_ARGS+=("$DEV_FLAG")
[[ -n "$FORCE_MERGE_FLAG" ]] && INSTALL_ARGS+=("$FORCE_MERGE_FLAG")

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
