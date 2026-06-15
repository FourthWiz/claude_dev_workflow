# Quoin for VSCode

VSCode extension providing a graphical control surface for the [quoin](../README.md) workflow toolkit.

## Requirements

Run `bash quoin/install.sh` from the quoin repo root before activating this extension. The extension requires:
- Python 3 on PATH
- `~/.claude/scripts/` (quoin adapter scripts)
- `~/.claude/core/scripts/` (quoin core scripts, including `dashboard_model.py`)

## Settings

Configure via VSCode Settings (File > Preferences > Settings, search "Quoin"):

| Setting | Default | Description |
|---|---|---|
| `quoin.pythonPath` | `python3` | Python executable for running quoin scripts |
| `quoin.projectRoot` | _(auto)_ | Override project root when auto-detection fails |
| `quoin.scriptRoots.adapter` | `~/.claude/scripts` | Adapter script directory |
| `quoin.scriptRoots.core` | `~/.claude/core/scripts` | Core script directory |
| `quoin.watcherDebounceMs` | `500` | File-watcher debounce in milliseconds |

## Development

```bash
cd quoin/vscode-extension
npm install
npm run compile   # or: npm run watch
# Press F5 in VSCode to launch Extension Development Host
```

## Packaging

```bash
npm run package   # produces quoin-vscode-<version>.vsix
```

Install with: `code --install-extension quoin-vscode-<version>.vsix`

## Activity Bar layout

The extension registers two groups in the Activity Bar:

- **Quoin Workflow** — Workflow Tree (current task pipeline) + Control Panel (launch sessions)
- **Quoin Sessions** — Sessions tree (active terminals), Sessions Archive (past sessions), Cost view

## Project isolation

Each window shows data for one project at a time. The extension resolves the active project root by:

1. An explicit user override (set via the project switcher)
2. Walk-up from the workspace folder to the nearest `.workflow_artifacts/` ancestor
3. The last persisted project root
4. Empty state ("no quoin project found")

All five panels (Workflow Tree, Control Panel, Sessions, Sessions Archive, Cost) are scoped to the active project root. Switching projects re-scopes all panels simultaneously.

### Project switcher

A status bar item (bottom-left, `$(folder) <project-name>`) shows the current project. Click it — or run **Quoin: Switch Project** — to pick from all known project roots. The selection persists across reloads.

### Multi-root / nested-folder workspaces

If the workspace folder is a subdirectory of the project root (e.g. workspace is `/repo/packages/app` but `.workflow_artifacts/` lives at `/repo/`), the extension walks up automatically and scopes to `/repo`.

### Archive panel

The Sessions Archive panel shows archived sessions for the active project:

- **Active** section (expanded by default) — sessions currently in memory
- **Archived** section (collapsed by default) — past sessions from disk; supports live text filtering by label/task/date and 25-items-per-page pagination

## Architecture

See [`../quoin/.workflow_artifacts/vscode-extension/architecture.md`](../.workflow_artifacts/vscode-extension/architecture.md) for the full design.
