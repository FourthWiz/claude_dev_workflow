# ============================================================
# Agent Desk helpers
# Ghostty/Zellij + Claude default + Codex on demand
# ============================================================

_agentdesk_realpath() {
  python3 - "$1" <<'PY'
import os
import sys
print(os.path.realpath(os.path.abspath(os.path.expanduser(sys.argv[1]))))
PY
}

_agentdesk_session_name() {
  local root="$1"
  local name

  name="$(
    basename "$root" \
      | tr -c '[:alnum:]_.-' '-' \
      | sed 's/-\{2,\}/-/g' \
      | sed 's/^-//' \
      | sed 's/-$//'
  )"

  if [ -z "$name" ]; then
    name="agentdesk"
  fi

  echo "$name"
}

_sanitize_session_name() {
  local raw="$1"
  local name

  name="$(
    printf "%s" "$raw" \
      | tr -c '[:alnum:]_.-' '-' \
      | sed 's/-\{2,\}/-/g' \
      | sed 's/^-//' \
      | sed 's/-$//'
  )"

  echo "$name"
}

_zellij_session_exists() {
  local session_name="$1"

  zellij list-sessions 2>/dev/null \
    | sed 's/\x1b\[[0-9;]*m//g' \
    | awk '{print $1}' \
    | grep -Fxq "$session_name"
}

_detect_repos() {
  if [ -z "${PROJECT_ROOT:-}" ]; then
    export PROJECT_ROOT="$PWD"
  fi

  local root
  root="$(_agentdesk_realpath "$PROJECT_ROOT")"

  if [ -e "$root/.git" ]; then
    echo "."
  fi

  find "$root" -mindepth 2 -maxdepth 4 \( -name .git -type d -o -name .git -type f \) 2>/dev/null \
    | while read -r git_entry; do
        repo_dir="$(dirname "$git_entry")"
        rel="${repo_dir#$root/}"

        if [ "$rel" != "." ] && [ -n "$rel" ]; then
          echo "$rel"
        fi
      done \
    | sort -u
}

_repo_path() {
  local repo="$1"

  if [ -z "${PROJECT_ROOT:-}" ]; then
    export PROJECT_ROOT="$PWD"
  fi

  if [ "$repo" = "." ]; then
    printf "%s\n" "$PROJECT_ROOT"
  else
    printf "%s\n" "$PROJECT_ROOT/$repo"
  fi
}

# ============================================================
# _agentdesk_pane_cmd <token>
# Returns the zsh -lc command string for the given window type token.
# $PROJECT_ROOT and $HOME are NOT expanded here — they remain literal
# shell variable references for Zellij/zsh to evaluate at runtime.
# ============================================================
_agentdesk_pane_cmd() {
  local token="$1"
  case "$token" in
    claude)
      printf '%s' 'source "$HOME/.config/agentdesk/agentdesk.zsh" 2>/dev/null || true; cd "$PROJECT_ROOT" && echo '\''Claude Code - project root:'\'' "$PWD" && if command -v claude >/dev/null 2>&1; then claude; else echo '\''claude not found'\''; fi; zsh'
      ;;
    codex)
      printf '%s' 'source "$HOME/.config/agentdesk/agentdesk.zsh" 2>/dev/null || true; cd "$PROJECT_ROOT" && echo '\''Codex - project root:'\'' "$PWD" && if command -v codex >/dev/null 2>&1; then codex; else echo '\''codex not found'\''; fi; zsh'
      ;;
    shell)
      printf '%s' 'source "$HOME/.config/agentdesk/agentdesk.zsh" 2>/dev/null || true; cd "$PROJECT_ROOT" && echo '\''Shell'\''; zsh'
      ;;
  esac
}

# ============================================================
# _agentdesk_pane_name <token>
# Returns the display name for a KDL pane given a window type token.
# ============================================================
_agentdesk_pane_name() {
  local token="$1"
  case "$token" in
    claude) printf '%s' 'Claude Code' ;;
    codex)  printf '%s' 'Codex' ;;
    shell)  printf '%s' 'Shell' ;;
  esac
}

# ============================================================
# _agentdesk_gen_layout <token> [<token> ...]
# Generates a single-tab Zellij KDL layout file for the given window tokens.
# Echoes the path to the temp file. Caller is responsible for cleanup
# (use trap "rm -f $layout_tmp" EXIT INT TERM in the caller).
# ============================================================
_agentdesk_gen_layout() {
  local tokens=("$@")
  local count="${#tokens[@]}"
  local layout_tmp
  layout_tmp="$(mktemp /tmp/agentdesk-layout-XXXXXX.kdl)"

  # Write the KDL with single-quoted heredoc so $PROJECT_ROOT/$HOME are NOT
  # expanded at write time — they remain shell variable refs for zsh at runtime.
  {
    cat <<'KDLHEADER'
layout {
    default_tab_template {
        pane size=1 borderless=true {
            plugin location="zellij:tab-bar"
        }

        children

        pane size=2 borderless=true {
            plugin location="zellij:status-bar"
        }
    }

KDLHEADER

    if [ "$count" -eq 1 ]; then
      local t="${tokens[1]}"
      local name cmd
      name="$(_agentdesk_pane_name "$t")"
      cmd="$(_agentdesk_pane_cmd "$t")"
      printf '    tab name="main" {\n'
      printf '        pane name="%s" {\n' "$name"
      printf '            command "zsh"\n'
      printf '            args "-lc" "%s"\n' "$cmd"
      printf '        }\n'
      printf '    }\n'
    elif [ "$count" -le 3 ]; then
      # side-by-side: split_direction="vertical" = vertical divider = side-by-side
      printf '    tab name="main" {\n'
      printf '        pane split_direction="vertical" {\n'
      local i
      for (( i=1; i<=count; i++ )); do
        local t="${tokens[$i]}"
        local name cmd
        name="$(_agentdesk_pane_name "$t")"
        cmd="$(_agentdesk_pane_cmd "$t")"
        printf '            pane name="%s" {\n' "$name"
        printf '                command "zsh"\n'
        printf '                args "-lc" "%s"\n' "$cmd"
        printf '            }\n'
      done
      printf '        }\n'
      printf '    }\n'
    else
      # >3 panes: stack horizontally
      printf '    tab name="main" {\n'
      printf '        pane split_direction="horizontal" {\n'
      local i
      for (( i=1; i<=count; i++ )); do
        local t="${tokens[$i]}"
        local name cmd
        name="$(_agentdesk_pane_name "$t")"
        cmd="$(_agentdesk_pane_cmd "$t")"
        printf '            pane name="%s" {\n' "$name"
        printf '                command "zsh"\n'
        printf '                args "-lc" "%s"\n' "$cmd"
        printf '            }\n'
      done
      printf '        }\n'
      printf '    }\n'
    fi

    printf '}\n'
  } > "$layout_tmp"

  printf '%s\n' "$layout_tmp"
}

# ============================================================
# _agentdesk_pick_layout
# Interactive layout picker. Prints a menu and reads user selection.
# Echoes space-separated tokens on stdout; echoes nothing for "fixed layout".
# Only call when stdin is a TTY ([ -t 0 ]).
# ============================================================
_agentdesk_pick_layout() {
  printf 'Select a layout:\n' >&2
  printf '  1) Standard (4 tabs: main / review / repos / shell)  [default]\n' >&2
  printf '  2) claude + shell\n' >&2
  printf '  3) claude + claude + shell\n' >&2
  printf '  4) claude + codex + shell\n' >&2
  printf '  5) Custom — type comma-separated: e.g. claude, codex, shell\n' >&2
  printf 'Choice [1]: ' >&2

  local choice
  read -r choice

  # Empty → option 1
  if [ -z "$choice" ] || [ "$choice" = "1" ]; then
    return 0  # echo nothing → caller uses fixed layout
  fi

  case "$choice" in
    2)
      printf 'claude shell\n'
      return 0
      ;;
    3)
      printf 'claude claude shell\n'
      return 0
      ;;
    4)
      printf 'claude codex shell\n'
      return 0
      ;;
    5)
      printf 'Type comma-separated tokens (claude, codex, shell): ' >&2
      read -r choice
      ;;
    *)
      # Treat any other input as direct comma-separated custom input
      ;;
  esac

  # Parse comma-separated input, strip whitespace, validate tokens
  _agentdesk_parse_custom_tokens "$choice"
}

# ============================================================
# _agentdesk_parse_custom_tokens <comma-separated-string>
# Validates and echoes space-separated tokens.
# Returns 1 if any token is invalid.
# ============================================================
_agentdesk_parse_custom_tokens() {
  local input="$1"
  local -a parsed=()

  # Split on commas using zsh parameter expansion, then strip whitespace from each token.
  # ${(@s:,:)input} is zsh-specific: splits $input on ',' into an array.
  local -a raw_tokens=("${(@s:,:)input}")

  local tok
  for tok in "${raw_tokens[@]}"; do
    # Strip leading/trailing whitespace
    tok="${tok#"${tok%%[! ]*}"}"
    tok="${tok%"${tok##*[! ]}"}"
    [ -z "$tok" ] && continue

    case "$tok" in
      claude|codex|shell)
        parsed+=("$tok")
        ;;
      *)
        printf 'Unknown token: "%s". Valid tokens: claude, codex, shell\n' "$tok" >&2
        printf 'Re-enter comma-separated tokens (or press Enter to cancel): ' >&2
        local retry
        read -r retry
        if [ -z "$retry" ]; then
          return 1
        fi
        _agentdesk_parse_custom_tokens "$retry"
        return $?
        ;;
    esac
  done

  if [ "${#parsed[@]}" -eq 0 ]; then
    printf 'No valid tokens provided.\n' >&2
    return 1
  fi

  printf '%s\n' "${parsed[*]}"
  return 0
}

agentdesk() {
  local mode=""
  local custom_name=""
  local -a tokens=()

  # ── Arg parsing (BEFORE Zellij guard so --help always works) ──────────────
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --mode)
        shift
        if [ "$#" -eq 0 ]; then
          printf 'Error: --mode requires a value (solo, duo, trio).\n' >&2
          return 1
        fi
        case "$1" in
          solo|duo|trio)
            mode="$1"
            ;;
          *)
            printf 'Error: invalid mode "%s". Valid modes: solo, duo, trio\n' "$1" >&2
            return 1
            ;;
        esac
        ;;
      -n|--name)
        shift
        if [ "$#" -eq 0 ]; then
          printf 'Error: --name requires a value.\n' >&2
          return 1
        fi
        custom_name="$1"
        ;;
      -h|--help)
        cat <<'HELP'
Usage:
  agentdesk
  agentdesk <session-name>
  agentdesk --name <session-name>
  agentdesk --mode solo|duo|trio
  agentdesk claude [codex] [shell] [...]

Modes:
  solo   — one Claude pane full-width
  duo    — Claude + Shell side-by-side
  trio   — Claude + Codex + Shell side-by-side

Window types (positional):
  claude   start Claude Code in pane
  codex    start Codex in pane
  shell    plain zsh shell

Examples:
  agentdesk
  agentdesk pricing
  agentdesk --mode trio
  agentdesk claude codex shell
  agentdesk claude claude
HELP
        return 0
        ;;
      claude|codex|shell)
        tokens+=("$1")
        ;;
      *)
        if [ "${#tokens[@]}" -eq 0 ] && [ -z "$mode" ]; then
          # Treat as session name (backward compat)
          custom_name="$1"
        else
          printf 'Error: unexpected argument "%s"\n' "$1" >&2
          return 1
        fi
        ;;
    esac
    shift
  done

  # ── Conflict checks (BEFORE Zellij guard) ─────────────────────────────────
  if [ -n "$mode" ] && [ "${#tokens[@]}" -gt 0 ]; then
    printf 'Error: --mode and positional window-type tokens are mutually exclusive.\n' >&2
    printf 'Use --mode for preset layouts or positional tokens for custom layouts.\n' >&2
    return 1
  fi

  if [ -n "$custom_name" ] && [ "${#tokens[@]}" -gt 0 ]; then
    printf 'Error: cannot mix session name with window-type tokens.\n' >&2
    printf 'Use --name for a named session with a mode/layout (e.g. agentdesk --mode trio --name my-session).\n' >&2
    return 1
  fi

  # ── Zellij guard (AFTER arg parsing) ──────────────────────────────────────
  if [ -n "${ZELLIJ:-}" ]; then
    echo "You are already inside a Zellij session."
    echo "Detach first with: Ctrl+o, then d"
    return 1
  fi

  # ── Resolve project root and session name ─────────────────────────────────
  local project_root session_name
  project_root="$(_agentdesk_realpath "$PWD")"
  export PROJECT_ROOT="$project_root"

  if [ -n "$custom_name" ]; then
    session_name="$(_sanitize_session_name "$custom_name")"
  else
    session_name="$(_agentdesk_session_name "$project_root")-agents"
  fi

  if [ -z "$session_name" ]; then
    echo "Error: empty session name after sanitization."
    return 1
  fi

  # ── Prepare workflow artifacts ─────────────────────────────────────────────
  mkdir -p "$project_root/.workflow_artifacts"

  touch "$project_root/.workflow_artifacts/current-plan.md"
  touch "$project_root/.workflow_artifacts/review.md"
  touch "$project_root/.workflow_artifacts/lessons-learned.md"
  touch "$project_root/.workflow_artifacts/repos.md"

  {
    echo "# Repositories"
    echo
    _detect_repos | while read -r repo; do
      [ -n "$repo" ] && echo "- $repo"
    done
  } > "$project_root/.workflow_artifacts/repos.md"

  local repo_count
  repo_count="$(_detect_repos | wc -l | tr -d ' ')"

  if [ "$repo_count" = "0" ]; then
    echo "No Git repo found at current folder or in child folders."
    echo "Starting anyway at project root: $project_root"
  fi

  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed. Install it with:"
    echo "  brew install zellij"
    return 1
  fi

  # ── Resolve layout ─────────────────────────────────────────────────────────
  local layout_path=""
  local layout_tmp=""

  if [ -n "$mode" ] || [ "${#tokens[@]}" -gt 0 ]; then
    # Explicit mode or tokens — generate KDL at runtime
    local -a effective_tokens=()
    if [ -n "$mode" ]; then
      case "$mode" in
        solo)  effective_tokens=(claude) ;;
        duo)   effective_tokens=(claude shell) ;;
        trio)  effective_tokens=(claude codex shell) ;;
      esac
    else
      effective_tokens=("${tokens[@]}")
    fi
    layout_tmp="$(_agentdesk_gen_layout "${effective_tokens[@]}")"
    layout_path="$layout_tmp"
    # Clean up temp file on exit, return, interrupt, or termination
    # shellcheck disable=SC2064
    trap "rm -f $layout_tmp" EXIT INT TERM
  elif [ -t 0 ]; then
    # Interactive TTY with no explicit layout — show picker
    local picked
    picked="$(_agentdesk_pick_layout)"
    local picker_rc=$?
    if [ $picker_rc -ne 0 ]; then
      printf 'Layout selection cancelled.\n' >&2
      return 1
    fi
    if [ -n "$picked" ]; then
      # Convert space-separated string to array and generate layout
      local -a picked_tokens=()
      read -rA picked_tokens <<< "$picked"
      layout_tmp="$(_agentdesk_gen_layout "${picked_tokens[@]}")"
      layout_path="$layout_tmp"
      # shellcheck disable=SC2064
      trap "rm -f $layout_tmp" EXIT INT TERM
    else
      # Option 1 or empty — use fixed layout
      layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
    fi
  else
    # Non-TTY (scripted/piped) — use fixed layout silently
    layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
  fi

  if [ ! -f "$layout_path" ]; then
    echo "Zellij layout not found:"
    echo "  $layout_path"
    return 1
  fi

  echo "Starting agent desk:"
  echo "  PROJECT_ROOT=$PROJECT_ROOT"
  echo "  SESSION=$session_name"
  echo "  REPOS:"
  cat "$project_root/.workflow_artifacts/repos.md"
  echo

  if _zellij_session_exists "$session_name"; then
    PROJECT_ROOT="$project_root" zellij attach "$session_name"
  else
    PROJECT_ROOT="$project_root" zellij --new-session-with-layout "$layout_path" --session "$session_name"
  fi
}

agentdesk-attach() {
  local session_name=""

  if [ "$#" -eq 0 ]; then
    agentdesk-sessions
    echo
    echo "Usage: agentdesk-attach <session-name>"
    return 1
  fi

  session_name="$1"

  if ! _zellij_session_exists "$session_name"; then
    echo "No such active session: $session_name"
    echo
    echo "Existing sessions:"
    agentdesk-sessions
    return 1
  fi

  zellij attach "$session_name"
}

repos() {
  if [ -z "${PROJECT_ROOT:-}" ]; then
    export PROJECT_ROOT="$PWD"
  fi

  _detect_repos
}

crepo() {
  if [ -z "${PROJECT_ROOT:-}" ]; then
    export PROJECT_ROOT="$PWD"
  fi

  if ! command -v fzf >/dev/null 2>&1; then
    echo "fzf is not installed. Install it with:"
    echo "  brew install fzf"
    return 1
  fi

  local repo
  repo="$(repos | fzf)"

  [ -z "$repo" ] && return 1

  cd "$(_repo_path "$repo")" || return 1
}

grepos() {
  if [ -z "${PROJECT_ROOT:-}" ]; then
    export PROJECT_ROOT="$PWD"
  fi

  repos | while read -r repo; do
    [ -z "$repo" ] && continue

    echo

    if [ "$repo" = "." ]; then
      echo "===== . ====="
      git -C "$PROJECT_ROOT" status --short 2>/dev/null || true
    else
      echo "===== $repo ====="
      git -C "$PROJECT_ROOT/$repo" status --short 2>/dev/null || true
    fi
  done
}

gitreview() {
  if [ -z "${PROJECT_ROOT:-}" ]; then
    export PROJECT_ROOT="$PWD"
  fi

  if ! command -v fzf >/dev/null 2>&1; then
    echo "fzf is not installed. Install it with:"
    echo "  brew install fzf"
    return 1
  fi

  local repo repo_path
  repo="$(repos | fzf --prompt='Select repo for git review: ')"

  [ -z "$repo" ] && return 1

  repo_path="$(_repo_path "$repo")"

  echo "Opening git review for: $repo"
  echo "Path: $repo_path"

  if command -v lazygit >/dev/null 2>&1; then
    (cd "$repo_path" && lazygit)
  else
    git -C "$repo_path" status
  fi
}

gitrootreview() {
  if [ -z "${PROJECT_ROOT:-}" ]; then
    export PROJECT_ROOT="$PWD"
  fi

  if [ -e "$PROJECT_ROOT/.git" ]; then
    if command -v lazygit >/dev/null 2>&1; then
      (cd "$PROJECT_ROOT" && lazygit)
    else
      git -C "$PROJECT_ROOT" status
    fi
  else
    echo "Project root is not a Git repo."
    echo "Use gitreview to select a child repo."
  fi
}

croot() {
  if [ -n "${PROJECT_ROOT:-}" ] && [ -d "$PROJECT_ROOT" ]; then
    cd "$PROJECT_ROOT" || return 1
  else
    local top
    top="$(git rev-parse --show-toplevel 2>/dev/null)"
    if [ -n "$top" ]; then
      cd "$top" || return 1
    else
      echo "PROJECT_ROOT is not set and current folder is not inside a Git repo."
      return 1
    fi
  fi
}

agentdesk-sessions() {
  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed."
    return 1
  fi

  zellij list-sessions
}

agentdesk-delete() {
  local force=""
  local session_name=""

  while [ "$#" -gt 0 ]; do
    case "$1" in
      --force|-f)
        force="--force"
        ;;
      -h|--help)
        cat <<'HELP'
Usage:
  agentdesk-delete <session-name>
  agentdesk-delete --force <session-name>
  agentdesk-delete <session-name> --force

Aliases:
  agentdesk-kill
HELP
        return 0
        ;;
      *)
        if [ -z "$session_name" ]; then
          session_name="$1"
        else
          echo "Unexpected argument: $1"
          return 1
        fi
        ;;
    esac
    shift
  done

  if [ -z "$session_name" ]; then
    echo "Please specify the session name to delete."
    echo
    echo "Existing sessions:"
    zellij list-sessions 2>/dev/null || true
    return 1
  fi

  if [ -n "$force" ]; then
    zellij delete-session "$session_name" --force
  else
    zellij delete-session "$session_name"
  fi
}

agentdesk-kill() {
  agentdesk-delete "$@"
}

codexpane() {
  local root="${PROJECT_ROOT:-$PWD}"

  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed."
    return 1
  fi

  if ! command -v codex >/dev/null 2>&1; then
    echo "codex command not found."
    return 1
  fi

  zellij run \
    --name "Codex" \
    --floating \
    --width "45%" \
    --height "85%" \
    --x "55%" \
    --y "5%" \
    -- zsh -lc "source \"\$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$root\" && echo 'Codex - project root:' \"\$PWD\" && codex"
}

codexright() {
  local root="${PROJECT_ROOT:-$PWD}"

  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed."
    return 1
  fi

  if ! command -v codex >/dev/null 2>&1; then
    echo "codex command not found."
    return 1
  fi

  zellij run \
    --name "Codex" \
    --direction right \
    -- zsh -lc "source \"\$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$root\" && echo 'Codex - project root:' \"\$PWD\" && codex"
}

codexcritic() {
  local root="${PROJECT_ROOT:-$PWD}"

  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed."
    return 1
  fi

  if ! command -v codex >/dev/null 2>&1; then
    echo "codex command not found."
    return 1
  fi

  zellij run \
    --name "Codex Critic" \
    --floating \
    --width "50%" \
    --height "85%" \
    --x "50%" \
    --y "5%" \
    -- zsh -lc "source \"\$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$root\" && echo 'Codex Critic - project root:' \"\$PWD\" && codex"
}

claudepane() {
  local root="${PROJECT_ROOT:-$PWD}"

  if ! command -v zellij >/dev/null 2>&1; then
    echo "zellij is not installed."
    return 1
  fi

  if ! command -v claude >/dev/null 2>&1; then
    echo "claude command not found."
    return 1
  fi

  zellij run \
    --name "Claude" \
    --direction right \
    -- zsh -lc "source \"\$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$root\" && echo 'Claude Code - project root:' \"\$PWD\" && claude"
}

agentprompt() {
  cat <<'PROMPT'
You are working from a project root that may either be a Git repo itself or may contain several child Git repositories.

First read:
- .workflow_artifacts/repos.md
- .workflow_artifacts/current-plan.md if present
- .workflow_artifacts/lessons-learned.md if relevant

Repository convention:
- If repos.md contains ".", the project root itself is the repo.
- If repos.md contains child paths, choose the relevant child repo before editing.

Before editing, identify which repo contains the relevant code.

For every task, maintain:
- the current plan in .workflow_artifacts/current-plan.md
- important review notes in .workflow_artifacts/review.md
- durable lessons in .workflow_artifacts/lessons-learned.md

When making changes, report:
- repo path
- files changed
- tests run from that repo
- cross-repo assumptions
PROMPT
}

codexcriticprompt() {
  cat <<'PROMPT'
You are the critic agent, not the primary implementation agent.

Read:
- .workflow_artifacts/current-plan.md
- .workflow_artifacts/repos.md
- current git diff across relevant repos

Do not edit files unless explicitly asked.

Return:
- critical risks
- likely bugs
- missing tests
- cross-repo assumptions
- suggested minimal changes
PROMPT
}
