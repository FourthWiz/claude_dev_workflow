#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════════════════════
#  Dev Workflow Installer — User-level setup (run once per machine)
#
#  - Copies all skills to ~/.claude/skills/
#  - Writes workflow rules to ~/.claude/CLAUDE.md
#
#  After this, use /init_workflow inside any project to scaffold
#  the project-level memory structure and permissions.
#
#  Usage:
#    bash install.sh
# ═══════════════════════════════════════════════════════════════

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

info()    { echo -e "${BLUE}ℹ${NC}  $1"; }
success() { echo -e "${GREEN}✓${NC}  $1"; }
warn()    { echo -e "${YELLOW}⚠${NC}  $1"; }
error()   { echo -e "${RED}✗${NC}  $1"; }
header()  { echo -e "\n${BOLD}$1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Dev Workflow Installer              ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""
info "Source: $SCRIPT_DIR"
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

if ! command -v npx &>/dev/null; then
  warn "npx not found — cost tracking in /end_of_task requires npx (install Node.js from https://nodejs.org)."
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

# ── Step 2: Copy skills to ~/.claude/skills/ ──
header "Step 2: Copying skills to ~/.claude/skills/..."

USER_SKILLS_DIR="$HOME/.claude/skills"
mkdir -p "$USER_SKILLS_DIR"

SKILL_COUNT=0
for skill_dir in "$SCRIPT_DIR/skills"/*/; do
  if [ -d "$skill_dir" ]; then
    skill_name=$(basename "$skill_dir")
    mkdir -p "$USER_SKILLS_DIR/$skill_name"
    cp "$skill_dir/SKILL.md" "$USER_SKILLS_DIR/$skill_name/SKILL.md"
    SKILL_COUNT=$((SKILL_COUNT + 1))
  fi
done

success "Copied $SKILL_COUNT skills to ~/.claude/skills/"

# ── Step 2b: Copy terse-rubric and v3 reference files to ~/.claude/memory/ and v3 scripts to ~/.claude/scripts/ ──
header "Step 2b: Copying memory references and v3 scripts to ~/.claude/..."

USER_MEMORY_DIR="$HOME/.claude/memory"
USER_SCRIPTS_DIR="$HOME/.claude/scripts"

# v2 terse-rubric (pre-existing — keep this block content-identical)
RUBRIC_SRC="$SCRIPT_DIR/memory/terse-rubric.md"
RUBRIC_DST="$USER_MEMORY_DIR/terse-rubric.md"

if [ ! -f "$RUBRIC_SRC" ]; then
  error "Expected rubric at $RUBRIC_SRC but not found — aborting"
  exit 1
fi

mkdir -p "$USER_MEMORY_DIR"
cp "$RUBRIC_SRC" "$RUBRIC_DST"
success "Copied terse-rubric.md to ~/.claude/memory/"

# v3 reference files (NEW — mirror the rubric pattern exactly)
for ref_file in format-kit.md glossary.md format-kit.sections.json; do
  REF_SRC="$SCRIPT_DIR/memory/$ref_file"
  REF_DST="$USER_MEMORY_DIR/$ref_file"
  if [ ! -f "$REF_SRC" ]; then
    error "Expected $ref_file at $REF_SRC but not found — aborting"
    exit 1
  fi
  cp "$REF_SRC" "$REF_DST"
  success "Copied $ref_file to ~/.claude/memory/"
done

# v3 scripts (NEW — separate destination directory ~/.claude/scripts/)
mkdir -p "$USER_SCRIPTS_DIR"
for script_file in summarize_for_human.py validate_artifact.py; do
  SCRIPT_SRC="$SCRIPT_DIR/scripts/$script_file"
  SCRIPT_DST="$USER_SCRIPTS_DIR/$script_file"
  if [ ! -f "$SCRIPT_SRC" ]; then
    error "Expected $script_file at $SCRIPT_SRC but not found — aborting"
    exit 1
  fi
  cp "$SCRIPT_SRC" "$SCRIPT_DST"
  chmod +x "$SCRIPT_DST"
  success "Copied $script_file to ~/.claude/scripts/"
done

# Optional dep hint (architecture R-12 mitigation): print setup-friction reduction hints
if ! python3 -c 'import anthropic' 2>/dev/null; then
  warn "Python package 'anthropic' is not installed — summarize_for_human.py will fail at runtime."
  warn "  Install with: pip install anthropic"
fi
if ! python3 -c 'import yaml' 2>/dev/null; then
  warn "Python package 'pyyaml' is not installed — validate_artifact.py V-01 frontmatter check will fail at runtime."
  warn "  Install with: pip install pyyaml"
fi

# ── Step 3: Write workflow rules to ~/.claude/CLAUDE.md ──
header "Step 3: Writing workflow rules to ~/.claude/CLAUDE.md..."

USER_CLAUDE_MD="$HOME/.claude/CLAUDE.md"
MARKER_START="# === DEV WORKFLOW START ==="
MARKER_END="# === DEV WORKFLOW END ==="

if [ -f "$USER_CLAUDE_MD" ] && grep -q "$MARKER_START" "$USER_CLAUDE_MD"; then
  python3 - "$USER_CLAUDE_MD" "$SCRIPT_DIR/CLAUDE.md" << 'PYEOF'
import sys, re
user_path, source_path = sys.argv[1], sys.argv[2]
with open(user_path) as f: content = f.read()
with open(source_path) as f: new_rules = f.read()
marker_start = "# === DEV WORKFLOW START ==="
marker_end = "# === DEV WORKFLOW END ==="
new_section = f"{marker_start}\n{new_rules}\n{marker_end}"
updated = re.sub(
    rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
    new_section, content, flags=re.DOTALL)
with open(user_path, 'w') as f: f.write(updated)
PYEOF
  success "Updated dev-workflow section in ~/.claude/CLAUDE.md"
else
  {
    echo ""
    echo "$MARKER_START"
    cat "$SCRIPT_DIR/CLAUDE.md"
    echo ""
    echo "$MARKER_END"
  } >> "$USER_CLAUDE_MD"
  success "Appended dev-workflow rules to ~/.claude/CLAUDE.md"
fi

# ── Done ──
echo ""
echo -e "${BOLD}╔══════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   User-level install complete!        ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}$SKILL_COUNT skills${NC} installed in ~/.claude/skills/"
echo -e "  ${GREEN}Workflow rules${NC} written to ~/.claude/CLAUDE.md"
echo -e "  ${GREEN}Terse rubric${NC} copied to ~/.claude/memory/terse-rubric.md"
echo -e "  ${GREEN}v3 reference files${NC} copied to ~/.claude/memory/ (format-kit.md, glossary.md, format-kit.sections.json)"
echo -e "  ${GREEN}v3 scripts${NC} copied to ~/.claude/scripts/ (validate_artifact.py, summarize_for_human.py)"
echo ""
echo -e "  ${BLUE}Tip:${NC} re-run bash install.sh to refresh skills, CLAUDE.md, and the rubric together."
echo ""
echo -e "  ${BOLD}Next: scaffold a project${NC}"
echo ""
echo -e "  1. ${BLUE}cd /path/to/your/project${NC}"
echo -e "  2. ${BLUE}claude${NC}"
echo -e "  3. Type ${YELLOW}/init_workflow${NC}"
echo ""
