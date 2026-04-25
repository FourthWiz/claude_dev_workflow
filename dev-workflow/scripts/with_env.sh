#!/usr/bin/env bash
# with_env.sh — load shell rc files for non-interactive subshells, then exec.
#
# Claude Code spawns non-interactive bash subshells that skip ~/.zshrc / ~/.bashrc,
# so ANTHROPIC_API_KEY (and other user env vars) are not available to summarize_for_human.py.
# This wrapper detects the user's $SHELL, sources the matching rc file idempotently,
# then execs the rest of argv.
#
# Idempotent: if ANTHROPIC_API_KEY is already set, skips sourcing.
#
# Note: neither `set -e` nor `set -u` is used.
#
# - `set -u` would abort on rc files that reference unset variables (`$NVM_DIR`,
#   theme vars, plugin-manager guards) — very common in real-world rc files.
# - `set -e` would abort when bash sources a zsh-targeted rc file: zsh-specific
#   commands like `autoload`, `zmodload`, `compdef` are command-not-found in
#   bash and exit 127, killing the wrapper before it can `exec` the real
#   command. (Observed in the Stage 4 smoke against a typical zsh setup with
#   google-cloud-sdk completions.)
#
# Both `set` modes were tried in earlier revisions and caused deterministic
# hangs. The wrapper's own logic is trivial enough that neither flag is needed
# for safety: every variable reference uses `${var:-default}`, and `exec` at
# the end propagates command-not-found via its own exit code (127) anyway.

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  case "${SHELL:-/bin/sh}" in
    */zsh)
      # shellcheck source=/dev/null
      [ -f "$HOME/.zshrc" ] && . "$HOME/.zshrc" >/dev/null 2>&1
      ;;
    */bash)
      # shellcheck source=/dev/null
      [ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc" >/dev/null 2>&1
      ;;
    *)
      # shellcheck source=/dev/null
      [ -f "$HOME/.profile" ] && . "$HOME/.profile" >/dev/null 2>&1
      ;;
  esac
fi

exec "$@"
