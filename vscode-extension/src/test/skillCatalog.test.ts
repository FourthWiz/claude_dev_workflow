import { describe, it, before, after } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { enumerateSkills, groupSkills } from '../skillCatalog';

// ── Fixture helpers ───────────────────────────────────────────────────────────

/** Create a temp directory with fake skill dirs matching a realistic set. */
function makeFixtureDir(): string {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'quoin-skills-'));
  const skillDirs = [
    // Normal skills
    'architect', 'plan', 'critic', 'revise', 'implement', 'review',
    'gate', 'rollback', 'end_of_task', 'pr', 'run',
    'start_of_day', 'end_of_day', 'checkpoint', 'cleanup', 'sleep',
    'capture_insight', 'triage', 'status', 'expand', 'cost_snapshot',
    // CRIT-1 regression guard: hyphenated name must enumerate
    'revise-fast',
    // Another hyphenated skill
    'thorough_plan',
  ];
  for (const d of skillDirs) {
    fs.mkdirSync(path.join(tmp, d));
  }
  // Stray noise — must NOT be enumerated
  fs.mkdirSync(path.join(tmp, 'next_steps 2'));          // space in name
  fs.writeFileSync(path.join(tmp, 'not-a-dir.txt'), ''); // file not dir
  fs.mkdirSync(path.join(tmp, '123-bad'));               // starts with digit
  return tmp;
}

let fixtureDir = '';

describe('enumerateSkills', () => {
  before(() => { fixtureDir = makeFixtureDir(); });
  after(() => { fs.rmSync(fixtureDir, { recursive: true, force: true }); });

  it('returns revise-fast (CRIT-1: hyphen must be admitted by regex)', () => {
    const names = enumerateSkills(fixtureDir);
    assert.ok(names.includes('revise-fast'),
      '"revise-fast" must be returned — CRIT-1 regression guard');
  });

  it('does NOT return "next_steps 2" (space rejected by regex)', () => {
    const names = enumerateSkills(fixtureDir);
    assert.ok(!names.includes('next_steps 2'),
      '"next_steps 2" must be excluded — embedded space fails the pattern');
  });

  it('does NOT return plain files', () => {
    const names = enumerateSkills(fixtureDir);
    assert.ok(!names.includes('not-a-dir.txt'), 'files must not be enumerated');
  });

  it('does NOT return dirs starting with a digit', () => {
    const names = enumerateSkills(fixtureDir);
    assert.ok(!names.includes('123-bad'), 'dirs starting with digit must be excluded');
  });

  it('returns only strings matching ^[a-z][a-z0-9_-]*$', () => {
    const names = enumerateSkills(fixtureDir);
    const re = /^[a-z][a-z0-9_-]*$/;
    for (const n of names) {
      assert.match(n, re, `${n} should match the skill name pattern`);
    }
  });

  it('returns empty array for a non-existent directory (R-02 rollback)', () => {
    const result = enumerateSkills('/this/path/does/not/exist');
    assert.deepEqual(result, []);
  });
});

// ── groupSkills ───────────────────────────────────────────────────────────────

describe('groupSkills', () => {
  it('places revise-fast in Planning (CRIT-1 + MAJ-2 combined)', () => {
    const groups = groupSkills(['revise-fast']);
    const planning = groups.find(g => g.group === 'Planning');
    assert.ok(planning, 'Planning group must exist');
    assert.ok(planning.skills.includes('revise-fast'),
      'revise-fast must be in Planning');
  });

  it('places sleep in Lifecycle (MAJ-2: not missing)', () => {
    const groups = groupSkills(['sleep']);
    const lifecycle = groups.find(g => g.group === 'Lifecycle');
    assert.ok(lifecycle, 'Lifecycle group must exist');
    assert.ok(lifecycle.skills.includes('sleep'), 'sleep must be in Lifecycle');
  });

  it('routes unknown skill names to Other (future-unknown fallback)', () => {
    const groups = groupSkills(['frobnicate', 'plan']);
    const other = groups.find(g => g.group === 'Other');
    assert.ok(other, 'Other group must exist');
    assert.ok(other.skills.includes('frobnicate'),
      'unknown skill must go to Other, not be dropped');
  });

  it('returns groups in stable order: Planning → Execution → Lifecycle → Cost → Other', () => {
    const names = [
      'cost_snapshot',   // Cost
      'implement',       // Execution
      'frobnicate',      // Other
      'plan',            // Planning
      'end_of_day',      // Lifecycle
    ];
    const groups = groupSkills(names);
    const order = groups.map(g => g.group);
    // Verify stable subset order
    const positions: Record<string, number> = {};
    order.forEach((g, i) => { positions[g] = i; });
    assert.ok(positions['Planning'] < positions['Execution'],
      'Planning must come before Execution');
    assert.ok(positions['Execution'] < positions['Lifecycle'],
      'Execution must come before Lifecycle');
    assert.ok(positions['Lifecycle'] < positions['Cost'],
      'Lifecycle must come before Cost');
    assert.ok(positions['Cost'] < positions['Other'],
      'Cost must come before Other');
  });

  it('omits empty groups', () => {
    const groups = groupSkills(['plan']); // only Planning populated
    const groupNames = groups.map(g => g.group);
    assert.ok(!groupNames.includes('Execution'), 'Empty Execution must be omitted');
    assert.ok(!groupNames.includes('Other'), 'Empty Other must be omitted');
  });

  it('returns empty array for empty input', () => {
    const groups = groupSkills([]);
    assert.equal(groups.length, 0);
  });
});

// ── Map-coverage test against real ~/.claude/skills/ ─────────────────────────

describe('map coverage — real ~/.claude/skills/', () => {
  it('every enumerated name is either mapped or visibly Other (no silent drops)', () => {
    const realDir = path.join(os.homedir(), '.claude', 'skills');
    if (!fs.existsSync(realDir)) {
      // Directory doesn't exist in CI or this environment — skip
      return;
    }
    const names = enumerateSkills(realDir);
    const groups = groupSkills(names);
    const allGroupedNames = groups.flatMap(g => g.skills);

    // Every enumerated name must appear in some group
    for (const n of names) {
      assert.ok(allGroupedNames.includes(n),
        `Skill '${n}' from real ~/.claude/skills/ is missing from groupSkills output`);
    }
  });
});
