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

_agentdesk_next_session_name() {
  local base="$1"
  local existing
  existing="$(zellij list-sessions 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' | awk '{print $1}')"
  if ! printf '%s\n' "$existing" | grep -Fxq "$base"; then
    echo "$base"; return 0
  fi
  local n=1 candidate
  while [ "$n" -le 9999 ]; do
    candidate="${base}_${n}"
    if ! printf '%s\n' "$existing" | grep -Fxq "$candidate"; then
      echo "$candidate"; return 0
    fi
    n=$((n+1))
  done
  # bound exhausted — fall back to base_EPOCH so we never collide/hang
  echo "${base}_$(date +%s)"; return 0
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
# IVG-82: Layout persistence helpers
# State store: $HOME/.config/agentdesk/last-layout
# Key format: name:<sanitized-name> or proj:<percent-encoded-root>
# Value format: __FIXED__ (standard layout) or token1+token2+... (custom)
# ============================================================

_agentdesk_state_file() {
  printf '%s\n' "$HOME/.config/agentdesk/last-layout"
}

# Percent-encode every byte NOT in [A-Za-z0-9].
# Two-step: (1) urllib.parse.quote(safe="") encodes everything except alphanumerics;
# (2) post-process .replace(".","%2E").replace("~","%7E") force-encodes . and ~
# which Python's _ALWAYS_SAFE frozenset would otherwise leave unencoded regardless
# of safe=. Resulting charset: [A-Za-z0-9%_-] — no raw dots, tildes, or backslashes.
# Keys must be backslash-free (awk -v interprets C-escapes; this encoder guarantees it).
_agentdesk_encode_key() {
  local raw="$1"
  python3 -c 'import sys,urllib.parse; s=urllib.parse.quote(sys.argv[1],safe=""); print(s.replace(".","%2E").replace("~","%7E"))' "$raw"
}

# Derive the persistence key for a layout lookup/save.
# custom_name non-empty → name:<sanitized-name> namespace
# else               → proj:<encoded-project-root> namespace
# These are INDEPENDENT namespaces: a name: save never matches a proj: lookup.
_agentdesk_layout_key() {
  local custom_name="$1"
  local project_root="$2"
  if [ -n "$custom_name" ]; then
    printf 'name:%s\n' "$(_sanitize_session_name "$custom_name")"
  else
    printf 'proj:%s\n' "$(_agentdesk_encode_key "$project_root")"
  fi
}

# Save a layout value for a key to the state file.
# Atomic write via temp file in same directory (same filesystem → atomic mv rename).
# Fail-open: any error → return 0.
# Keys must be backslash-free (guaranteed by encoder); awk -v interprets C-escapes.
_agentdesk_save_layout() {
  local key="$1"
  local value="$2"
  local state_file
  state_file="$(_agentdesk_state_file)"
  local state_dir
  state_dir="$(dirname "$state_file")"

  mkdir -p "$state_dir" 2>/dev/null || return 0

  # Read existing content, filtering out any old line for this key (exact first-field match).
  local existing=""
  if [ -f "$state_file" ]; then
    # key must be backslash-free (guaranteed by encoder); awk -v interprets C-escapes.
    existing="$(awk -F'=' -v k="$key" '$1 != k' "$state_file" 2>/dev/null)" || existing=""
  fi

  # Write atomically: temp file in same dir so mv is atomic across same filesystem.
  local tmp_file
  tmp_file="$(mktemp "$state_dir/.last-layout.tmp.XXXXXX" 2>/dev/null)" || return 0

  {
    if [ -n "$existing" ]; then
      printf '%s\n' "$existing"
    fi
    printf '%s=%s\n' "$key" "$value"
  } > "$tmp_file" 2>/dev/null || { rm -f "$tmp_file" 2>/dev/null; return 0; }

  mv "$tmp_file" "$state_file" 2>/dev/null || { rm -f "$tmp_file" 2>/dev/null; return 0; }
  return 0
}

# Load a saved layout value for a key from the state file.
# Fail-open: file missing or key absent → echo nothing, return 1.
# key must be backslash-free (guaranteed by encoder); awk -v interprets C-escapes.
# Values may contain '='; sub() strips only the first '=' so values round-trip correctly.
_agentdesk_load_layout() {
  local key="$1"
  local state_file
  state_file="$(_agentdesk_state_file)"

  if [ ! -f "$state_file" ]; then
    return 1
  fi

  local value
  # key must be backslash-free (guaranteed by encoder); value may contain '=';
  # sub(/^[^=]*=/,"") strips only up to the first '=', so a=b=c values round-trip correctly.
  value="$(awk -F'=' -v k="$key" '$1==k{sub(/^[^=]*=/,""); print; exit}' "$state_file" 2>/dev/null)"

  if [ -z "$value" ]; then
    return 1
  fi

  printf '%s\n' "$value"
  return 0
}

# Restore a saved layout value to a layout_path.
# __FIXED__ → echoes fixed agent-desk.kdl path, rc=0; caller must NOT rm.
# token+token+... → validates tokens against whitelist, generates temp KDL, echoes path, rc=0.
# Invalid/empty → rc=1.
_agentdesk_layout_from_value() {
  local value="$1"

  if [ "$value" = "__FIXED__" ]; then
    printf '%s\n' "$HOME/.config/zellij/layouts/agent-desk.kdl"
    return 0
  fi

  # Split on '+' using zsh parameter expansion (NOT read -rA which splits on whitespace).
  # Token whitelist: claude|codex|shell|status|ccr|spend; '+' is a safe separator.
  local -a arr=("${(@s:+:)value}")

  if [ "${#arr[@]}" -eq 0 ]; then
    return 1
  fi

  local tok
  for tok in "${arr[@]}"; do
    case "$tok" in
      claude|codex|shell|status|ccr|spend) ;;
      *)
        return 1
        ;;
    esac
  done

  local gen_path
  gen_path="$(_agentdesk_gen_layout "${arr[@]}")" || return 1
  printf '%s\n' "$gen_path"
  return 0
}

# ============================================================
# _agentdesk_pane_cmd <token>
# Returns the zsh -lc command string for the given window type token.
# $PROJECT_ROOT and $HOME are NOT expanded here — they remain literal
# shell variable references for Zellij/zsh to evaluate at runtime.
# Inner double-quotes are emitted as \" so the string survives embedding
# in the KDL `args "-lc" "..."` field (matches the fixed agent-desk.kdl
# escaping). Single-quoted echo strings stay as literal single quotes.
# ============================================================
_agentdesk_pane_cmd() {
  local token="$1"
  case "$token" in
    claude)
      printf '%s' 'source \"$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$PROJECT_ROOT\" && echo '\''Claude Code - project root:'\'' \"$PWD\" && if command -v claude >/dev/null 2>&1; then claude; else echo '\''claude not found'\''; fi; zsh'
      ;;
    codex)
      printf '%s' 'source \"$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$PROJECT_ROOT\" && echo '\''Codex - project root:'\'' \"$PWD\" && if command -v codex >/dev/null 2>&1; then codex; else echo '\''codex not found'\''; fi; zsh'
      ;;
    shell)
      printf '%s' 'source \"$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$PROJECT_ROOT\" && echo '\''Shell'\''; zsh'
      ;;
    status)
      printf '%s' 'source \"$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$PROJECT_ROOT\" && python3 \"$HOME/.claude/scripts/status_graph.py\" --compact --watch'
      ;;
    spend)
      printf '%s' 'source \"$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$PROJECT_ROOT\" && python3 \"$HOME/.claude/scripts/spend_monitor.py\" --compact --watch'
      ;;
    ccr)
      printf '%s' 'source \"$HOME/.config/agentdesk/agentdesk.zsh\" 2>/dev/null || true; cd \"$PROJECT_ROOT\" && echo '\''CCR (OpenRouter) - project root:'\'' \"$PWD\" && if command -v ccr >/dev/null 2>&1; then ccr code; else echo '\''ccr not found'\''; fi; zsh'
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
    status) printf '%s' 'Status' ;;
    spend)  printf '%s' 'Token Spend' ;;
    ccr)    printf '%s' 'CCR (OpenRouter)' ;;
  esac
}

# ============================================================
# _agentdesk_gen_layout <token> [<token> ...]
# Generates a single-tab Zellij KDL layout file for the given window tokens.
# Echoes the path to the temp file. Caller is responsible for cleanup
# (use trap "rm -f $layout_tmp" EXIT INT TERM in the caller).
# ============================================================
_agentdesk_gen_layout() {
  local layout_tmp
  # mktemp only randomizes *trailing* X's on macOS (BSD mktemp). A suffix after
  # the X's prevents randomisation, creating the same literal path every time and
  # failing with "File exists" on the second call. Fix: generate without suffix,
  # then rename to add .kdl. Uses TMPDIR so sandboxed environments work too.
  layout_tmp="$(mktemp "${TMPDIR:-/tmp}/agentdesk-layout-XXXXXX")" || {
    echo "agentdesk: failed to create temp layout file" >&2
    return 1
  }
  mv -f "$layout_tmp" "$layout_tmp.kdl" || return 1
  layout_tmp="$layout_tmp.kdl"

  # Declare loop locals ONCE, outside the redirected block. zsh's typeset
  # echoes `name=value` to stdout when re-declaring an existing local, which
  # would leak into the KDL file if `local` were used inside the `{ } > file`
  # block. Hoisting the declarations here avoids that.
  local t name cmd i main_count has_spend
  local -a main_tokens=()

  # Spend tab is always included. Filter any explicit spend tokens from main_tokens
  # (deduplication — passing spend explicitly still works).
  has_spend=1
  for t in "$@"; do
    if [ "$t" != "spend" ]; then
      main_tokens+=("$t")
    fi
  done
  main_count="${#main_tokens[@]}"

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

    if [ "$main_count" -gt 0 ]; then
      if [ "$main_count" -eq 1 ]; then
        t="${main_tokens[1]}"
        name="$(_agentdesk_pane_name "$t")"
        cmd="$(_agentdesk_pane_cmd "$t")"
        printf '    tab name="main" {\n'
        printf '        pane name="%s" {\n' "$name"
        printf '            command "zsh"\n'
        printf '            args "-lc" "%s"\n' "$cmd"
        printf '        }\n'
        printf '    }\n'
      elif [ "$main_count" -le 3 ]; then
        # side-by-side: split_direction="vertical" = vertical divider = side-by-side
        printf '    tab name="main" {\n'
        printf '        pane split_direction="vertical" {\n'
        for (( i=1; i<=main_count; i++ )); do
          t="${main_tokens[$i]}"
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
        for (( i=1; i<=main_count; i++ )); do
          t="${main_tokens[$i]}"
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
    fi

    if [ "$has_spend" -eq 1 ]; then
      name="$(_agentdesk_pane_name spend)"
      cmd="$(_agentdesk_pane_cmd spend)"
      printf '    tab name="Spend" {\n'
      printf '        pane name="%s" {\n' "$name"
      printf '            command "zsh"\n'
      printf '            args "-lc" "%s"\n' "$cmd"
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
  printf '  1) Standard (5 tabs: main / review / repos / shell / spend)  [default]\n' >&2
  printf '  2) claude + shell + spend\n' >&2
  printf '  3) claude + claude + shell + spend\n' >&2
  printf '  4) claude + codex + shell + spend\n' >&2
  printf '  5) claude + ccr + shell + spend\n' >&2
  printf '  6) Custom — type comma-separated: e.g. claude, codex, shell, ccr\n' >&2
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
      printf 'claude ccr shell\n'
      return 0
      ;;
    6)
      printf 'Type comma-separated tokens (claude, codex, shell, ccr): ' >&2
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
      claude|codex|shell|status|ccr|spend)
        parsed+=("$tok")
        ;;
      *)
        printf 'Unknown token: "%s". Valid tokens: claude, codex, shell, status, ccr, spend\n' "$tok" >&2
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

# ============================================================
# _agentdesk_open_dashboard
# Opt-in quoin dashboard prompt shown before the zellij TTY hand-off.
#
# User-mode only: deployed via deploy_agentdesk (not project mode); the server
# is reached via the $HOME/.claude deploy path (same convention as the status
# pane). Non-interactive / scripted desks are silently skipped via [ -t 0 ].
#
# Behavior:
#   - Skips (returns 0) immediately when stdin is not a TTY.
#   - Prompts "Open quoin dashboard? [y/N]:" — default No.
#   - On No/empty: returns 0, no server started.
#   - On Yes: starts dashboard_server.py in background with --no-browser,
#     captures the printed URL=<url> line, opens it in the default browser,
#     leaves the server running for the duration of the desk session.
#   - Always returns 0; any internal failure prints a note to stderr.
# ============================================================
_agentdesk_open_dashboard() {
  # Guard: skip entirely when stdin is not a TTY (non-interactive / scripted desks).
  [ ! -t 0 ] && return 0

  printf 'Open quoin dashboard? [y/N]: ' >&2
  local reply
  read -r reply

  # Default No: only explicit y/Y/yes/YES proceeds.
  case "$reply" in
    [Yy]|[Yy][Ee][Ss]) ;;
    *) return 0 ;;
  esac

  local server_script="$HOME/.claude/scripts/dashboard_server.py"

  # Presence guard: skip gracefully when the server is absent (e.g. project-scope
  # installs where deploy_agentdesk did not run, or the quoin install is stale).
  if [ ! -f "$server_script" ]; then
    printf 'agentdesk: dashboard server not found at %s; skipping\n' "$server_script" >&2
    return 0
  fi

  # Launch the server detached, capturing its stdout to a temp file so we can
  # poll for the "URL=<url>" line without blocking the foreground shell.
  local stdout_tmp
  stdout_tmp="$(mktemp)"
  python3 "$server_script" --no-browser > "$stdout_tmp" 2>/dev/null &
  local server_pid=$!

  # Poll for up to ~10 s (50 × 0.2 s) for the URL= line.
  local url=""
  local i=0
  while [ $i -lt 50 ]; do
    if grep -q '^URL=' "$stdout_tmp" 2>/dev/null; then
      url="$(grep '^URL=' "$stdout_tmp" | head -1 | sed 's/^URL=//')"
      break
    fi
    sleep 0.2
    i=$((i + 1))
  done

  rm -f "$stdout_tmp"

  if [ -z "$url" ]; then
    printf 'agentdesk: dashboard did not report a URL (server pid %s still running)\n' "$server_pid" >&2
    return 0
  fi

  # Open the URL in the default browser; fall back to printing if no opener found.
  if command -v open >/dev/null 2>&1; then
    open "$url"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url"
  else
    printf 'agentdesk: dashboard running at %s (no browser opener found)\n' "$url" >&2
  fi

  return 0
}

agentdesk() {
  local mode=""
  local custom_name=""
  local force_pick=""
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
      --pick)
        force_pick=1
        ;;
      -h|--help)
        cat <<'HELP'
Usage:
  agentdesk
  agentdesk <session-name>
  agentdesk --name <session-name>
  agentdesk --mode solo|duo|trio
  agentdesk claude [codex] [shell] [...]
  agentdesk --pick

Modes:
  solo   — one Claude pane full-width
  duo    — Claude + Shell side-by-side
  trio   — Claude + Codex + Shell side-by-side

Window types (positional):
  claude   start Claude Code in pane
  codex    start Codex in pane
  shell    plain zsh shell
  status   show workflow pipeline status graph
  ccr      start ccr code (OpenRouter via CCR) in pane
  spend    realtime token-spend monitor

Layout memory:
  agentdesk remembers your layout choice per project (or per session name).
  On subsequent runs it reuses your last layout silently.
  Use --pick to force the interactive picker and change the layout.
  The layout is stored in: ~/.config/agentdesk/last-layout
  To reset: delete that file, or delete the line for your project key.
  Project key namespace (proj:) and named-session namespace (name:) are
  independent — a named session save never affects a bare project launch.
  Set AGENTDESK_PICK=1 to force the picker via environment variable.

Behavior:
  Re-running in a folder with a live same-named session starts a NEW suffixed session (_1, _2, …); it never attaches.

Examples:
  agentdesk
  agentdesk pricing
  agentdesk --mode trio
  agentdesk claude codex shell
  agentdesk claude ccr shell
  agentdesk claude claude
  agentdesk --pick

Resume:
  agentdesk-attach SESSION-NAME   resume an existing session
HELP
        return 0
        ;;
      claude|codex|shell|status|ccr|spend)
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

  # Apply AGENTDESK_PICK env override (force picker via environment variable).
  if [ -n "${AGENTDESK_PICK:-}" ]; then
    force_pick=1
  fi

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

  # ── Compute layout persistence key BEFORE session-name suffixing ──────────
  # Key uses ORIGINAL custom_name (not suffixed), so _1/_2 suffixed sessions
  # still share the same reuse key as the base session name.
  local layout_key
  layout_key="$(_agentdesk_layout_key "$custom_name" "$project_root")"

  # ── Resolve session name suffix (never auto-attach) ───────────────────────
  local resolved_name
  resolved_name="$(_agentdesk_next_session_name "$session_name")"
  if [ "$resolved_name" != "$session_name" ]; then
    echo "Session '$session_name' already exists; starting new session '$resolved_name' instead."
    echo "(To resume the existing session: agentdesk-attach $session_name)"
    session_name="$resolved_name"
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

  # ── Resolve layout (D-08 branch order) ────────────────────────────────────
  # Declare ALL locals before the if/elif chain, outside any redirection block.
  # (zsh typeset echoes name=value to stdout when re-declaring inside { } > file)
  local layout_path="" layout_tmp=""
  local saved_value="" saved_value_loaded=""
  local -a effective_tokens=() picked_tokens=()

  if [ -n "$mode" ] || [ "${#tokens[@]}" -gt 0 ]; then
    # Branch 1: explicit mode or tokens — generate KDL at runtime
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
    # join OUTSIDE any redirection to avoid typeset-echo leak
    saved_value="${(j:+:)effective_tokens}"
    # Clean up temp file on exit, return, interrupt, or termination
    # shellcheck disable=SC2064
    trap "rm -f $layout_tmp" EXIT INT TERM

  elif [ -n "$force_pick" ]; then
    # Branch 2: --pick or AGENTDESK_PICK=1 — force interactive picker
    # --pick is inert when --mode/tokens are given (branch 1 wins above).
    if [ -t 0 ]; then
      # TTY: show picker
      local picked
      picked="$(_agentdesk_pick_layout)"
      local picker_rc=$?
      if [ $picker_rc -ne 0 ]; then
        printf 'Layout selection cancelled.\n' >&2
        return 1
      fi
      if [ -n "$picked" ]; then
        # Non-empty pick (options 2-6): split space-separated output into array
        read -rA picked_tokens <<< "$picked"
        layout_tmp="$(_agentdesk_gen_layout "${picked_tokens[@]}")"
        layout_path="$layout_tmp"
        # join OUTSIDE any redirection to avoid typeset-echo leak
        saved_value="${(j:+:)picked_tokens}"
        # shellcheck disable=SC2064
        trap "rm -f $layout_tmp" EXIT INT TERM
      else
        # Empty pick (option 1 / default): use fixed layout
        layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
        saved_value="__FIXED__"
      fi
    else
      # Non-TTY + --pick: skip reuse, go directly to fixed layout (D-07)
      layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
      saved_value="__FIXED__"
    fi

  elif saved_value_loaded="$(_agentdesk_load_layout "$layout_key" 2>/dev/null)" && [ -n "$saved_value_loaded" ]; then
    # Branch 3: saved layout exists — try to restore it
    local restored_path
    restored_path="$(_agentdesk_layout_from_value "$saved_value_loaded" 2>/dev/null)"
    local restore_rc=$?
    if [ $restore_rc -eq 0 ] && [ -n "$restored_path" ]; then
      layout_path="$restored_path"
      printf 'Reusing last layout (use --pick to change)\n' >&2
      saved_value="$saved_value_loaded"
      # If the restored path is a generated temp file (not the fixed kdl), register trap
      if [ "$restored_path" != "$HOME/.config/zellij/layouts/agent-desk.kdl" ]; then
        layout_tmp="$restored_path"
        # shellcheck disable=SC2064
        trap "rm -f $layout_tmp" EXIT INT TERM
      fi
    else
      # Corrupt saved value — fall through to branch 4/5
      if [ -t 0 ]; then
        local picked
        picked="$(_agentdesk_pick_layout)"
        local picker_rc=$?
        if [ $picker_rc -ne 0 ]; then
          printf 'Layout selection cancelled.\n' >&2
          return 1
        fi
        if [ -n "$picked" ]; then
          read -rA picked_tokens <<< "$picked"
          layout_tmp="$(_agentdesk_gen_layout "${picked_tokens[@]}")"
          layout_path="$layout_tmp"
          saved_value="${(j:+:)picked_tokens}"
          # shellcheck disable=SC2064
          trap "rm -f $layout_tmp" EXIT INT TERM
        else
          layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
          saved_value="__FIXED__"
        fi
      else
        layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
        saved_value="__FIXED__"
      fi
    fi

  elif [ -t 0 ]; then
    # Branch 4: no saved layout + TTY — first-run interactive picker
    local picked
    picked="$(_agentdesk_pick_layout)"
    local picker_rc=$?
    if [ $picker_rc -ne 0 ]; then
      printf 'Layout selection cancelled.\n' >&2
      return 1
    fi
    if [ -n "$picked" ]; then
      read -rA picked_tokens <<< "$picked"
      layout_tmp="$(_agentdesk_gen_layout "${picked_tokens[@]}")"
      layout_path="$layout_tmp"
      saved_value="${(j:+:)picked_tokens}"
      # shellcheck disable=SC2064
      trap "rm -f $layout_tmp" EXIT INT TERM
    else
      # Option 1 or empty — use fixed layout
      layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
      saved_value="__FIXED__"
    fi

  else
    # Branch 5: non-TTY + no saved layout — use fixed layout silently
    layout_path="$HOME/.config/zellij/layouts/agent-desk.kdl"
    saved_value="__FIXED__"
  fi

  if [ ! -f "$layout_path" ]; then
    echo "Zellij layout not found:"
    echo "  $layout_path"
    return 1
  fi

  # Save layout AFTER existence check passes (D-05): never persist a value
  # whose layout file is missing (would fail every subsequent launch).
  _agentdesk_save_layout "$layout_key" "$saved_value" 2>/dev/null || true

  echo "Starting agent desk:"
  echo "  PROJECT_ROOT=$PROJECT_ROOT"
  echo "  SESSION=$session_name"
  echo "  REPOS:"
  cat "$project_root/.workflow_artifacts/repos.md"
  echo

  # Offer the quoin dashboard before handing the TTY to zellij.
  # _agentdesk_open_dashboard self-skips on non-TTY and always returns 0.
  _agentdesk_open_dashboard

  PROJECT_ROOT="$project_root" zellij --new-session-with-layout "$layout_path" --session "$session_name"
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
