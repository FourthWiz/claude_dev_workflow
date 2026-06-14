import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export type GroupName = 'Planning' | 'Execution' | 'Lifecycle' | 'Cost' | 'Other';

export interface SkillGroup {
  group: GroupName;
  skills: string[];
}

/**
 * Complete, explicit name→group map for all skills currently on disk (2026-06-14).
 * Any enumerated skill NOT in this map routes to 'Other' — it surfaces immediately
 * rather than being silently dropped (D-02).
 *
 * To recategorize: change the group string. To add a new skill: add a line here
 * (or let it land in 'Other' until intentionally mapped).
 */
const NAME_TO_GROUP: Record<string, GroupName> = {
  // Planning
  discover: 'Planning',
  architect: 'Planning',
  plan: 'Planning',
  critic: 'Planning',
  revise: 'Planning',
  'revise-fast': 'Planning',  // CRIT-1: hyphen-bearing name must be in map (and regex must admit it)
  thorough_plan: 'Planning',

  // Execution
  implement: 'Execution',
  review: 'Execution',
  gate: 'Execution',
  rollback: 'Execution',
  run: 'Execution',  // end-to-end pipeline orchestrator (kept in Execution per critic)
  pr: 'Execution',
  end_of_task: 'Execution',

  // Lifecycle (includes between-phase helpers: triage, status, expand)
  start_of_day: 'Lifecycle',
  end_of_day: 'Lifecycle',
  weekly_review: 'Lifecycle',
  checkpoint: 'Lifecycle',
  continue_work: 'Lifecycle',
  sleep: 'Lifecycle',  // session-memory consolidation — lifecycle action like end_of_day
  cleanup: 'Lifecycle',
  capture_insight: 'Lifecycle',
  next_steps: 'Lifecycle',
  triage: 'Lifecycle',
  init_workflow: 'Lifecycle',
  status: 'Lifecycle',
  expand: 'Lifecycle',

  // Cost
  cost_snapshot: 'Cost',
};

/**
 * The stable display order for groups.
 * Empty groups are omitted from the returned array.
 */
const GROUP_ORDER: GroupName[] = ['Planning', 'Execution', 'Lifecycle', 'Cost', 'Other'];

/**
 * Enumerate skill names from the given directory.
 *
 * Returns only entries that are:
 *   1. Directories (not files)
 *   2. Match `^[a-z][a-z0-9_-]*$` (CRIT-1 fix: includes hyphen, so 'revise-fast' passes;
 *      'next_steps 2' fails on the embedded space)
 *
 * Falls back to an empty array if the directory is unreadable (R-02 rollback).
 *
 * @param skillsDir - Directory to scan. Defaults to ~/.claude/skills
 */
export function enumerateSkills(
  skillsDir: string = path.join(os.homedir(), '.claude', 'skills')
): string[] {
  try {
    const entries = fs.readdirSync(skillsDir, { withFileTypes: true });
    const pattern = /^[a-z][a-z0-9_-]*$/;
    return entries
      .filter(e => e.isDirectory() && pattern.test(e.name))
      .map(e => e.name);
  } catch {
    // R-02 rollback: unreadable directory → empty list (UI shows no skill buttons)
    return [];
  }
}

/**
 * Group an array of skill names into ordered SkillGroup buckets.
 *
 * - Known names are placed in their mapped group.
 * - Unknown names (future skills not yet in NAME_TO_GROUP) route to 'Other'.
 * - Empty groups are omitted from the result.
 * - Groups are returned in stable order: Planning → Execution → Lifecycle → Cost → Other.
 *
 * @param skillNames - Skill names to group (typically from enumerateSkills())
 */
export function groupSkills(skillNames: string[]): SkillGroup[] {
  const buckets: Record<GroupName, string[]> = {
    Planning: [],
    Execution: [],
    Lifecycle: [],
    Cost: [],
    Other: [],
  };

  for (const name of skillNames) {
    const group: GroupName = NAME_TO_GROUP[name] ?? 'Other';
    buckets[group].push(name);
  }

  // Return stable order, omitting empty groups
  return GROUP_ORDER
    .filter(g => buckets[g].length > 0)
    .map(g => ({ group: g, skills: buckets[g] }));
}
