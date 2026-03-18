# Development Workflow — Setup Guide

## Quick Install (one command)

```bash
# From the dev-workflow/ directory, targeting your project:
bash install.sh /path/to/your/project

# Or from inside your project, pointing to the source:
bash /path/to/dev-workflow/install.sh
```

The script handles everything: copies files, creates symlinks in `.claude/skills/`, sets up CLAUDE.md, generates the quickstart guide, and configures `.gitignore`.

After the script finishes:
```bash
cd /path/to/your/project
claude
# then type: /init_workflow
```

That's it. `/init_workflow` scans your repos and populates the memory files.

---

## What the script does

1. **Checks prerequisites** — verifies `claude` and `git` are installed
2. **Copies workflow files** — all skills, CLAUDE.md, HTML guide into `<project>/dev-workflow/`
3. **Preserves memory** — if re-installing, existing `memory/` is never overwritten
4. **Creates Claude Code symlinks** — links each skill into `<project>/.claude/skills/` so Claude recognizes the commands
5. **Sets up CLAUDE.md** — adds a reference to the workflow rules in your root CLAUDE.md
6. **Generates QUICKSTART.md** — command reference card
7. **Configures permissions** — creates `.claude/settings.json` with auto-approved permissions for reading, git, and search operations
8. **Configures .gitignore** — excludes session/daily files (they're local-only)

## Prerequisites

- **Claude Code** installed (`claude` command available)
- **Git** installed
- **gh** (GitHub CLI) — optional, for PR creation later

## Manual Installation (if you prefer)

If you don't want to use the script:

### 1. Copy files
```bash
cp -r /path/to/dev-workflow ~/projects/my-app/dev-workflow
```

### 2. Symlink skills
```bash
cd ~/projects/my-app
mkdir -p .claude/skills
for skill in dev-workflow/skills/*/; do
  name=$(basename "$skill")
  ln -s "../../dev-workflow/skills/$name" ".claude/skills/$name"
done
```

### 3. Set up CLAUDE.md
```bash
echo -e "\n## Development Workflow\nSee dev-workflow/CLAUDE.md for workflow rules and commands." >> CLAUDE.md
```

### 4. Initialize
```bash
claude
# then type: /init_workflow
```

## Result

After installation, your project looks like:
```
~/projects/my-app/
├── .claude/skills/          ← symlinks to workflow skills
├── CLAUDE.md                ← references dev-workflow rules
├── dev-workflow/
│   ├── CLAUDE.md            ← shared workflow rules
│   ├── QUICKSTART.md        ← command reference
│   ├── SETUP.md             ← this file
│   ├── Workflow-User-Guide.html
│   ├── install.sh           ← the installer
│   ├── memory/
│   │   ├── sessions/
│   │   ├── daily/
│   │   ├── lessons-learned.md
│   │   ├── workflow-rules.md
│   │   └── ... (populated by /discover)
│   └── skills/
│       ├── discover/
│       ├── architect/
│       ├── plan/
│       ├── critic/
│       ├── revise/
│       ├── thorough_plan/
│       ├── gate/
│       ├── implement/
│       ├── review/
│       ├── rollback/
│       ├── end_of_task/
│       ├── end_of_day/
│       ├── start_of_day/
│       └── init_workflow/
├── service-a/               ← your repos
├── service-b/
└── frontend/
```

## Daily Usage

```bash
cd ~/projects/my-app && claude
```

| You want to... | Type |
|---|---|
| Start your day | `/start_of_day` |
| Plan a big feature | `/architect` then `/thorough_plan` |
| Fix a bug | `/plan` then `/implement` |
| Review implementation | `/review` |
| Ship it | `/end_of_task` |
| Wrap up for the day | `/end_of_day` |

## Updating

```bash
# Re-run the installer — it preserves your memory/
bash /path/to/new/dev-workflow/install.sh /path/to/your/project
```

## Troubleshooting

**Skills not recognized:** check that symlinks exist — `ls -la .claude/skills/` should show links pointing into `dev-workflow/skills/`.

**Claude doesn't follow workflow rules:** make sure `CLAUDE.md` at the project root references `dev-workflow/CLAUDE.md`. The installer does this automatically.

**/discover finds nothing:** your repos need to be git repositories (each has a `.git/` folder) inside the project root.

**Context filling up:** normal — each heavy command works best in its own chat session. The file-based memory carries state between sessions.
