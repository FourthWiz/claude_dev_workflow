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

## Architecture

See [`../quoin/.workflow_artifacts/vscode-extension/architecture.md`](../.workflow_artifacts/vscode-extension/architecture.md) for the full design.
