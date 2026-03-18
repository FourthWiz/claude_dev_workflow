#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
#  Dev Workflow Installer
#  Installs the multi-agent development workflow into a project.
#
#  Usage:
#    curl -sL <url>/install.sh | bash                   # current dir
#    curl -sL <url>/install.sh | bash -s -- /path/to    # specific dir
#    bash install.sh                                     # if local
#    bash install.sh /path/to/project                    # specific dir
# ═══════════════════════════════════════════════════════════════

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}ℹ${NC}  $1"; }
success() { echo -e "${GREEN}✓${NC}  $1"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $1"; }
error()   { echo -e "${RED}✗${NC}  $1"; }
header()  { echo -e "\n${BOLD}$1${NC}"; }

# ── Resolve paths ──
# Where this script lives = where the workflow source files are
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-$(pwd)}"
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

WORKFLOW_DIR="$TARGET_DIR/dev-workflow"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Dev Workflow Installer              ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""
info "Source:  $SCRIPT_DIR"
info "Target:  $TARGET_DIR"
echo ""

# ── Step 1: Check prerequisites ──
header "Step 1: Checking prerequisites..."

MISSING=()

if ! command -v claude &>/dev/null; then
  MISSING+=("claude (Claude Code CLI)")
fi

if ! command -v git &>/dev/null; then
  MISSING+=("git")
fi

if ! command -v gh &>/dev/null; then
  warn "gh (GitHub CLI) not found — /end_of_task push will still work, but PR creation won't."
fi

if [ ${#MISSING[@]} -gt 0 ]; then
  error "Missing required tools:"
  for tool in "${MISSING[@]}"; do
    echo "       - $tool"
  done
  echo ""
  echo "Install them and re-run this script."
  exit 1
fi

success "Prerequisites OK"

# ── Step 2: Handle existing installation ──
header "Step 2: Preparing target directory..."

if [ -d "$WORKFLOW_DIR" ]; then
  warn "Existing dev-workflow/ found at $WORKFLOW_DIR"

  if [ -d "$WORKFLOW_DIR/memory" ]; then
    info "Preserving existing memory/ (lessons, sessions, inventory)"
    PRESERVE_MEMORY=true
  else
    PRESERVE_MEMORY=false
  fi

  # Back up memory before copying
  if [ "$PRESERVE_MEMORY" = true ]; then
    BACKUP_DIR=$(mktemp -d)
    cp -r "$WORKFLOW_DIR/memory" "$BACKUP_DIR/memory"
    success "Memory backed up to $BACKUP_DIR"
  fi
else
  PRESERVE_MEMORY=false
fi

# ── Step 3: Copy workflow files ──
header "Step 3: Copying workflow files..."

# Create directory structure
mkdir -p "$WORKFLOW_DIR"
mkdir -p "$WORKFLOW_DIR/skills"
mkdir -p "$WORKFLOW_DIR/memory/sessions"
mkdir -p "$WORKFLOW_DIR/memory/daily"

# Copy core files
for file in CLAUDE.md SETUP.md Workflow-User-Guide.html; do
  if [ -f "$SCRIPT_DIR/$file" ]; then
    cp "$SCRIPT_DIR/$file" "$WORKFLOW_DIR/$file"
    success "Copied $file"
  fi
done

# Copy all skills
SKILL_COUNT=0
for skill_dir in "$SCRIPT_DIR/skills"/*/; do
  if [ -d "$skill_dir" ]; then
    skill_name=$(basename "$skill_dir")
    mkdir -p "$WORKFLOW_DIR/skills/$skill_name"
    cp "$skill_dir/SKILL.md" "$WORKFLOW_DIR/skills/$skill_name/SKILL.md"
    SKILL_COUNT=$((SKILL_COUNT + 1))
  fi
done
success "Copied $SKILL_COUNT skills"

# Copy memory templates (only if not preserving)
if [ "$PRESERVE_MEMORY" = true ]; then
  # Restore backed-up memory
  cp -r "$BACKUP_DIR/memory"/* "$WORKFLOW_DIR/memory/" 2>/dev/null || true
  rm -rf "$BACKUP_DIR"
  success "Restored preserved memory"
else
  # Create fresh memory files
  cp "$SCRIPT_DIR/memory/workflow-rules.md" "$WORKFLOW_DIR/memory/workflow-rules.md" 2>/dev/null || true

  # Create lessons-learned template
  cat > "$WORKFLOW_DIR/memory/lessons-learned.md" << 'LESSONS_EOF'
# Lessons Learned

Accumulated insights from completed tasks. Read by /plan and /critic at the start of every session.

<!-- Add entries using the format:
## <date> — <task-name>
**What happened:** <the surprise, failure, or insight>
**Lesson:** <the reusable takeaway>
**Applies to:** <which skills should pay attention>
-->
LESSONS_EOF

  # Create empty memory placeholders
  touch "$WORKFLOW_DIR/memory/repos-inventory.md"
  touch "$WORKFLOW_DIR/memory/architecture-overview.md"
  touch "$WORKFLOW_DIR/memory/dependencies-map.md"
  touch "$WORKFLOW_DIR/memory/git-log.md"

  success "Created memory structure with templates"
fi

# ── Step 4: Register skills with Claude Code ──
header "Step 4: Registering skills with Claude Code..."

CLAUDE_SKILLS_DIR="$TARGET_DIR/.claude/skills"
mkdir -p "$CLAUDE_SKILLS_DIR"

# Create symlinks (relative paths so they work if the project moves)
LINKED=0
SKIPPED=0
for skill_dir in "$WORKFLOW_DIR/skills"/*/; do
  if [ -d "$skill_dir" ]; then
    skill_name=$(basename "$skill_dir")
    link_target="$CLAUDE_SKILLS_DIR/$skill_name"

    # Compute relative path from .claude/skills/ to dev-workflow/skills/<name>/
    rel_path="../../dev-workflow/skills/$skill_name"

    if [ -L "$link_target" ]; then
      # Symlink exists — update it
      rm "$link_target"
    elif [ -d "$link_target" ]; then
      # Real directory exists — skip
      warn "Skipping $skill_name — real directory exists at $link_target"
      SKIPPED=$((SKIPPED + 1))
      continue
    fi

    ln -s "$rel_path" "$link_target"
    LINKED=$((LINKED + 1))
  fi
done

success "Linked $LINKED skills into .claude/skills/"
[ $SKIPPED -gt 0 ] && warn "Skipped $SKIPPED (already exist as directories)"

# ── Step 5: Set up CLAUDE.md reference ──
header "Step 5: Setting up CLAUDE.md..."

ROOT_CLAUDE_MD="$TARGET_DIR/CLAUDE.md"

if [ -f "$ROOT_CLAUDE_MD" ]; then
  # Check if reference already exists
  if grep -q "dev-workflow/CLAUDE.md" "$ROOT_CLAUDE_MD" 2>/dev/null; then
    info "Root CLAUDE.md already references dev-workflow — skipping"
  else
    echo "" >> "$ROOT_CLAUDE_MD"
    echo "## Development Workflow" >> "$ROOT_CLAUDE_MD"
    echo "See dev-workflow/CLAUDE.md for workflow rules and commands." >> "$ROOT_CLAUDE_MD"
    success "Added workflow reference to existing CLAUDE.md"
  fi
else
  cat > "$ROOT_CLAUDE_MD" << 'CLAUDE_EOF'
# Project Rules

## Development Workflow
See dev-workflow/CLAUDE.md for workflow rules and commands.
CLAUDE_EOF
  success "Created root CLAUDE.md with workflow reference"
fi

# ── Step 6: Generate QUICKSTART.md ──
header "Step 6: Generating quickstart guide..."

cat > "$WORKFLOW_DIR/QUICKSTART.md" << 'QS_EOF'
# Development Workflow — Quickstart

## Your commands

| Command | What it does |
|---------|-------------|
| `/discover` | Scans all repos, maps architecture and dependencies |
| `/architect` | Designs solution architecture for a feature/change |
| `/thorough_plan` | Creates detailed implementation plan (with critic review) |
| `/implement` | Writes code from the plan (explicit command only) |
| `/review` | Verifies implementation against the plan |
| `/end_of_task` | Pushes branch, captures lessons (explicit command only) |
| `/rollback` | Safely undoes implementation work |
| `/start_of_day` | Morning briefing — restores context |
| `/end_of_day` | Saves session state, consolidates work |
| `/gate` | Quality checkpoint (runs automatically between phases) |

## Typical flows

**Large feature:**
`/discover` → `/architect` → `/thorough_plan` → `/implement` → `/review` → `/end_of_task`

**Bug fix:**
`/plan` → `/implement` → `/review` → `/end_of_task`

**Starting your day:**
`/start_of_day`

**Ending your day:**
`/end_of_day`

## Key rules

1. **`/implement` and `/end_of_task` never run automatically.** You must type them.
2. **Quality gates run between every phase.** Claude stops and asks for your approval.
3. **Each heavy command works best in its own chat session.** Context windows fill up — the file artifacts are the shared memory.
4. **`/end_of_task` pushes the branch only.** Create your PR separately when ready.
5. **Lessons accumulate.** The more you use the workflow, the smarter it gets about your codebase.

## Files

- `CLAUDE.md` — shared rules all skills follow
- `memory/` — accumulated knowledge (repos, architecture, lessons, sessions)
- `skills/` — all workflow skill definitions
- `Workflow-User-Guide.html` — detailed interactive guide with scenarios

## First time?

Open `Workflow-User-Guide.html` in your browser for a full walkthrough with example conversations.

## Getting started

```bash
claude                    # open Claude Code in this project
/init_workflow            # first-time setup: scans repos, populates memory
/start_of_day             # daily: restores context, shows what's in progress
```
QS_EOF

success "Generated QUICKSTART.md"

# ── Step 7: Configure default permissions ──
header "Step 7: Configuring Claude Code permissions..."

CLAUDE_SETTINGS="$TARGET_DIR/.claude/settings.json"

if [ -f "$CLAUDE_SETTINGS" ]; then
  info "Existing .claude/settings.json found — skipping (review manually if needed)"
else
  cat > "$CLAUDE_SETTINGS" << 'SETTINGS_EOF'
{
  "permissions": {
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "Bash(git status)",
      "Bash(git status *)",
      "Bash(git diff)",
      "Bash(git diff *)",
      "Bash(git log)",
      "Bash(git log *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git branch)",
      "Bash(git branch *)",
      "Bash(git checkout *)",
      "Bash(git push *)",
      "Bash(git pull *)",
      "Bash(git stash *)",
      "Bash(git rebase *)",
      "Bash(git merge *)",
      "Bash(git rev-parse *)",
      "Bash(git show *)",
      "Bash(git remote *)",
      "Bash(find *)",
      "Bash(ls *)",
      "Bash(cat *)",
      "Bash(head *)",
      "Bash(tail *)",
      "Bash(wc *)",
      "Bash(grep *)",
      "Bash(rg *)",
      "Bash(mkdir *)"
    ]
  }
}
SETTINGS_EOF
  success "Created .claude/settings.json with default permissions"
fi

# ── Step 8: Add .gitignore entries ──
header "Step 8: Configuring .gitignore..."

GITIGNORE="$TARGET_DIR/.gitignore"

ENTRIES_TO_ADD=(
  "dev-workflow/memory/sessions/"
  "dev-workflow/memory/daily/"
)

if [ -f "$GITIGNORE" ]; then
  for entry in "${ENTRIES_TO_ADD[@]}"; do
    if ! grep -qF "$entry" "$GITIGNORE" 2>/dev/null; then
      echo "$entry" >> "$GITIGNORE"
    fi
  done
  success "Updated .gitignore (session/daily files excluded from git)"
else
  printf "%s\n" "${ENTRIES_TO_ADD[@]}" > "$GITIGNORE"
  success "Created .gitignore (session/daily files excluded from git)"
fi

# ── Done ──
echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Installation Complete!              ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}$SKILL_COUNT skills${NC} installed"
echo -e "  ${GREEN}$LINKED symlinks${NC} created in .claude/skills/"
echo -e "  ${GREEN}memory/${NC} structure ready"
echo -e "  ${GREEN}permissions${NC} configured (read, git, search auto-approved)"
echo ""
echo -e "  ${BOLD}Next steps:${NC}"
echo ""
echo -e "  1. ${BLUE}cd $TARGET_DIR${NC}"
echo -e "  2. ${BLUE}claude${NC}"
echo -e "  3. Type ${YELLOW}/init_workflow${NC} to scan your repos and get started"
echo ""
echo -e "  Or open ${BLUE}dev-workflow/Workflow-User-Guide.html${NC} for the full guide."
echo ""
