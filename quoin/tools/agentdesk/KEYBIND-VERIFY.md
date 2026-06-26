# Keybind Verification Checklist (IVG-86)

Manual steps to verify that `manage_zellij_keybinds()` has correctly freed
Option+arrow and Ctrl+o from Zellij's global keybind intercept.

## Prerequisites

Run `setup-agentdesk.sh` (or re-source the config) to apply the keybind merge:

```sh
bash ~/.local/bin/setup-agentdesk.sh
# OR, if already applied, inspect the config directly:
grep -n 'agentdesk: freed' ~/.config/zellij/config.kdl
```

## Step 1 — Reload Zellij config

```sh
zellij action reload-config
```

Or restart your Zellij session entirely if reload-config is not available.

## Step 2 — Verify Option+Right (word-forward)

Inside a Zellij pane with a shell prompt, press **Option+Right** (macOS) or **Alt+Right**.

Expected: cursor moves one word forward (shell word-forward navigation).
Failure: Zellij session-switch popup appears — the bind was NOT freed.

## Step 3 — Verify Option+Left (word-backward)

Press **Option+Left** (macOS) or **Alt+Left**.

Expected: cursor moves one word backward.
Failure: Zellij session-switch popup appears — the bind was NOT freed.

## Step 4 — Verify Ctrl+o passes through

Inside the Claude Code pane, press **Ctrl+o**.

Expected: the keystroke reaches Claude Code (e.g., opens the editor overlay or
          is handled by Claude Code's own binding).
Failure: Zellij session mode opens — the bind was NOT freed.

## Step 5 — Verify Alt+s opens session mode

Press **Alt+s** from any normal Zellij pane.

Expected: Zellij session mode opens (the re-exposed binding).
Failure: nothing happens or Alt+s is intercepted elsewhere.

## Step 6 — Check config for no errors

```sh
zellij setup --check
```

Expected: no config-parse errors reported.

## Step 7 — Verify backup was created

```sh
ls -la ~/.config/zellij/config.kdl.keybinds.*.bak
```

Expected: at least one timestamped `.keybinds.YYYYMMDD-HHMMSS.bak` file.
This is the pre-merge backup created by `manage_zellij_keybinds()`.

## Step 8 — Verify idempotency

Re-run setup-agentdesk.sh (or call `manage_zellij_keybinds` directly) a second
time. Expected output: `Unchanged: Zellij keybind merge already applied`.
No second backup should be created and the config should be byte-identical.

## What was changed

`manage_zellij_keybinds()` makes the following surgical edits to `~/.config/zellij/config.kdl`:

| Bind | Block | Action |
|------|-------|--------|
| `bind "Alt left" { MoveFocusOrTab "left"; }` | `shared_except "locked"` | Commented out with `# [agentdesk: freed]` |
| `bind "Alt right" { MoveFocusOrTab "right"; }` | `shared_except "locked"` | Commented out with `# [agentdesk: freed]` |
| `bind "Ctrl o" { SwitchToMode "session"; }` | `shared_except "locked" "session"` | Commented out with `# [agentdesk: freed]` |
| `bind "Alt s" { SwitchToMode "session"; }` | `shared_except "locked"` | Added (re-exposes session mode) |

Note (T-04): Ghostty does NOT need changes. The binds `cmd+right` / `option+right`
are not configured in `~/.config/ghostty/config` — only `cmd+t/w/d/shift+d/shift+,`
are bound there. Ghostty passes Option+arrow through to the terminal application unchanged.
