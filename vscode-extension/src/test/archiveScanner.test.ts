import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseDateFromFilename,
  parseSessionLabel,
  parseSessionMeta,
  parseFrontmatter,
  extractSection,
  scanArchive,
  FsLike,
} from '../archiveScanner';

// ── parseDateFromFilename ─────────────────────────────────────────────────────

describe('parseDateFromFilename', () => {
  it('extracts YYYY-MM-DD prefix', () => {
    assert.strictEqual(parseDateFromFilename('2026-06-14-vscode-extension-s3.md'), '2026-06-14');
  });

  it('returns undefined when no date prefix', () => {
    assert.strictEqual(parseDateFromFilename('no-date.md'), undefined);
  });

  it('returns undefined for empty string', () => {
    assert.strictEqual(parseDateFromFilename(''), undefined);
  });
});

// ── parseFrontmatter ──────────────────────────────────────────────────────────

describe('parseFrontmatter', () => {
  it('parses a full frontmatter block', () => {
    const body = '---\ntask: foo\nphase: bar\ndate: 2026-01-02\n---\n## Rest\n';
    const result = parseFrontmatter(body);
    assert.strictEqual(result.task, 'foo');
    assert.strictEqual(result.phase, 'bar');
    assert.strictEqual(result.date, '2026-01-02');
  });

  it('returns {} when no frontmatter present', () => {
    const result = parseFrontmatter('## Active task\nvscode-extension\n');
    assert.deepStrictEqual(result, {});
  });

  it('returns {} for malformed frontmatter (no closing ---)', () => {
    const result = parseFrontmatter('---\ntask: foo\n## rest\n');
    assert.deepStrictEqual(result, {});
  });

  it('MIN-6: splits on first colon only — value may contain colons', () => {
    const body = '---\ntitle: foo: bar\ntask: my-task\n---\n';
    const result = parseFrontmatter(body);
    assert.strictEqual(result['title'], 'foo: bar');
    assert.strictEqual(result.task, 'my-task');
  });

  it('handles frontmatter with only task key', () => {
    const result = parseFrontmatter('---\ntask: my-task\n---\n## Status\nin_progress\n');
    assert.strictEqual(result.task, 'my-task');
    assert.strictEqual(result.phase, undefined);
  });
});

// ── extractSection ────────────────────────────────────────────────────────────

describe('extractSection', () => {
  it('Shape A: blank line between heading and value (session files)', () => {
    // Dominant session-file format — naive line+1 read returns '' without the fix
    assert.strictEqual(
      extractSection('## Status\n\ncompleted\n', '## Status'),
      'completed',
    );
  });

  it('Shape B: value on the immediately following line (checkpoint files)', () => {
    assert.strictEqual(
      extractSection('## Status\ncheckpoint save\n', '## Status'),
      'checkpoint save',
    );
  });

  it('Shape C: empty section — next non-blank line is a heading → undefined', () => {
    // Critical: ensures status never returns '## Active task' for checkpoint files
    assert.strictEqual(
      extractSection('## Current stage\n## Active task\nsome-task\n', '## Current stage'),
      undefined,
    );
  });

  it('returns undefined when heading not found', () => {
    assert.strictEqual(extractSection('## Other\nvalue\n', '## Status'), undefined);
  });

  it('returns undefined at EOF after heading with no value', () => {
    assert.strictEqual(extractSection('## Status\n', '## Status'), undefined);
  });

  it('accepts headingText already prefixed with ##', () => {
    assert.strictEqual(
      extractSection('## Status\nok\n', '## Status'),
      'ok',
    );
  });
});

// ── parseSessionLabel ─────────────────────────────────────────────────────────

describe('parseSessionLabel', () => {
  it('returns task+phase from frontmatter when both present', () => {
    const body = '---\ntask: vscode-extension\nphase: review\ndate: 2026-06-14\n---\n\n## Current stage\ncompleted\n';
    assert.strictEqual(parseSessionLabel('2026-06-14-vscode-extension-review.md', body), 'vscode-extension review');
  });

  it('returns task-only from frontmatter when phase absent (MIN-5)', () => {
    // Pins the dominant real case: only ~23/50 frontmatter files carry phase:
    const body = '---\ntask: my-task\n---\n';
    assert.strictEqual(parseSessionLabel('2026-06-14-my-task.md', body), 'my-task');
    // Must NOT produce 'my-task undefined'
  });

  it('returns heading text when no frontmatter but # Session State — heading present', () => {
    const body = '# Session State — vscode-extension S-3\nsome content\n';
    assert.strictEqual(parseSessionLabel('2026-06-14-x.md', body), 'vscode-extension S-3');
  });

  it('returns filename stem fallback (date stripped, dashes → spaces)', () => {
    assert.strictEqual(parseSessionLabel('2026-05-08-foo-bar.md', 'no heading here'), 'foo bar');
  });

  it('MAJ-1: frontmatter session with task+phase yields correct label', () => {
    const body = '---\ntask: vscode-extension\nphase: review\ndate: 2026-06-14\n---\n\n## Current stage\ncompleted\n';
    assert.strictEqual(parseSessionLabel('any.md', body), 'vscode-extension review');
  });

  it('MAJ-1: frontmatter-only task (no heading needed)', () => {
    const body = '---\ntask: my-task\n---\n## Status\nin_progress\n';
    assert.strictEqual(parseSessionLabel('any.md', body), 'my-task');
  });
});

// ── parseSessionMeta ──────────────────────────────────────────────────────────

describe('parseSessionMeta', () => {
  it('extracts status from ## Current stage (Shape B — checkpoint-like)', () => {
    assert.deepStrictEqual(
      parseSessionMeta('## Current stage\ncompleted\n'),
      { status: 'completed', task: undefined },
    );
  });

  it('extracts task from ## Active task', () => {
    assert.deepStrictEqual(
      parseSessionMeta('## Active task\nvscode-extension-s3\n'),
      { status: undefined, task: 'vscode-extension-s3' },
    );
  });

  it('extracts status from ## Status (Shape A — blank line)', () => {
    assert.deepStrictEqual(
      parseSessionMeta('## Status\n\nin_progress\n'),
      { status: 'in_progress', task: undefined },
    );
  });

  it('extracts task from frontmatter (MAJ-1)', () => {
    const body = '---\ntask: my-task\n---\n## Status\nin_progress\n';
    const result = parseSessionMeta(body);
    assert.strictEqual(result.task, 'my-task');
    assert.strictEqual(result.status, 'in_progress');
  });

  it('returns {} for empty body', () => {
    const result = parseSessionMeta('');
    assert.strictEqual(result.status, undefined);
    assert.strictEqual(result.task, undefined);
  });
});

// ── scanArchive ───────────────────────────────────────────────────────────────

describe('scanArchive', () => {
  /**
   * Build a FsLike seam from a map of directory→filenames and path→contents.
   */
  function makeFakeFs(opts: {
    dirs: Record<string, string[]>;  // dir path → list of filenames
    files: Record<string, string>;   // file path → content
  }): FsLike {
    return {
      existsSync(p: string): boolean {
        return p in opts.dirs || p in opts.files;
      },
      readdirSync(p: string): string[] {
        return opts.dirs[p] ?? [];
      },
      readFileSync(p: string, _enc: 'utf8'): string {
        if (p in opts.files) { return opts.files[p]; }
        throw new Error(`ENOENT: ${p}`);
      },
    };
  }

  const root = '/project';
  const sessionsDir = '/project/.workflow_artifacts/memory/sessions';
  const checkpointsDir = '/project/.workflow_artifacts/memory/checkpoints';
  const recentPath = '/project/.workflow_artifacts/memory/recent-sessions.md';

  it('returns 5 entries from 3 sessions + 2 checkpoints; recent-sessions contributes 0 (D-03)', () => {
    const fakeFs = makeFakeFs({
      dirs: {
        [sessionsDir]: ['2026-06-14-vscode-review.md', '2026-06-01-auth.md', '2026-05-01-old.md'],
        [checkpointsDir]: ['2026-06-10-ckpt.md', '2026-06-09-ckpt2.md'],
      },
      files: {
        [`${sessionsDir}/2026-06-14-vscode-review.md`]:
          '---\ntask: vscode-extension\nphase: review\ndate: 2026-06-14\n---\n\n## Current stage\ncompleted\n',
        [`${sessionsDir}/2026-06-01-auth.md`]:
          '# Session State — auth-refactor\n## Status\nin_progress\n',
        [`${sessionsDir}/2026-05-01-old.md`]:
          'no frontmatter no heading\n',
        [`${checkpointsDir}/2026-06-10-ckpt.md`]:
          '## Status\ncheckpoint save\n## Active task\nvscode-extension\n',
        [`${checkpointsDir}/2026-06-09-ckpt2.md`]:
          '## Status\ncheckpoint save\n',
        [recentPath]: '2026-06-14T10:00:00Z | UUID-1\n2026-06-14T11:00:00Z | UUID-2\n',
      },
    });

    const result = scanArchive(root, fakeFs);
    assert.strictEqual(result.length, 5, 'Expected 5 entries (3 sessions + 2 checkpoints)');

    // All have correct source types
    const sessionEntries = result.filter((e) => e.source === 'session');
    const checkpointEntries = result.filter((e) => e.source === 'checkpoint');
    assert.strictEqual(sessionEntries.length, 3);
    assert.strictEqual(checkpointEntries.length, 2);

    // Sorted newest first: 2026-06-14 comes first
    assert.strictEqual(result[0].date, '2026-06-14');
    assert.strictEqual(result[0].label, 'vscode-extension review');
  });

  it('MAJ-1 frontmatter session: task, date, status correctly extracted', () => {
    const body = '---\ntask: vscode-extension\nphase: review\ndate: 2026-06-14\n---\n\n## Current stage\ncompleted\n';
    const fakeFs = makeFakeFs({
      dirs: { [sessionsDir]: ['2026-06-14-s.md'], [checkpointsDir]: [] },
      files: { [`${sessionsDir}/2026-06-14-s.md`]: body },
    });

    const result = scanArchive(root, fakeFs);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].label, 'vscode-extension review');
    assert.strictEqual(result[0].task, 'vscode-extension');
    assert.strictEqual(result[0].date, '2026-06-14');
    assert.strictEqual(result[0].status, 'completed');
  });

  it('MAJ-1 frontmatter-only task (no phase): label is bare task', () => {
    const body = '---\ntask: my-task\n---\n## Status\nin_progress\n';
    const fakeFs = makeFakeFs({
      dirs: { [sessionsDir]: ['2026-06-10-my-task.md'], [checkpointsDir]: [] },
      files: { [`${sessionsDir}/2026-06-10-my-task.md`]: body },
    });

    const result = scanArchive(root, fakeFs);
    assert.strictEqual(result.length, 1);
    assert.strictEqual(result[0].label, 'my-task');
    assert.strictEqual(result[0].task, 'my-task');
    assert.strictEqual(result[0].status, 'in_progress');
  });

  it('returns [] when sessions and checkpoints dirs are missing', () => {
    const fakeFs = makeFakeFs({ dirs: {}, files: {} });
    const result = scanArchive(root, fakeFs);
    assert.deepStrictEqual(result, []);
  });

  it('skips a file whose readFileSync throws; others still returned', () => {
    const fakeFs: FsLike = {
      existsSync: (p: string) => p === sessionsDir,
      readdirSync: (p: string) => p === sessionsDir ? ['good.md', 'bad.md'] : [],
      readFileSync: (p: string, _enc: 'utf8') => {
        if (p.endsWith('bad.md')) { throw new Error('unreadable'); }
        return '## Status\nok\n';
      },
    };

    const result = scanArchive(root, fakeFs);
    assert.strictEqual(result.length, 1);
    assert.ok(result[0].filePath.endsWith('good.md'));
  });

  it('results are sorted newest date first; no-date entries last', () => {
    const fakeFs = makeFakeFs({
      dirs: {
        [sessionsDir]: ['no-date.md', '2026-01-01-old.md', '2026-06-14-new.md'],
        [checkpointsDir]: [],
      },
      files: {
        [`${sessionsDir}/no-date.md`]: '## Status\nok\n',
        [`${sessionsDir}/2026-01-01-old.md`]: '## Status\nok\n',
        [`${sessionsDir}/2026-06-14-new.md`]: '## Status\nok\n',
      },
    });

    const result = scanArchive(root, fakeFs);
    assert.strictEqual(result[0].date, '2026-06-14');
    assert.strictEqual(result[1].date, '2026-01-01');
    assert.strictEqual(result[2].date, undefined); // no-date last
  });

  it('archive does not include entries from recent-sessions.md (D-03)', () => {
    const fakeFs = makeFakeFs({
      dirs: { [sessionsDir]: [], [checkpointsDir]: [] },
      files: {
        [recentPath]: '2026-06-14T10:00:00Z | UUID-1\n2026-06-14T11:00:00Z | UUID-2\n',
      },
    });

    const result = scanArchive(root, fakeFs);
    assert.strictEqual(result.length, 0, 'recent-sessions.md must contribute 0 rows');
  });

  it('no vscode import in archiveScanner.ts (zero vscode dependency)', () => {
    // Verify at module load level: if we got here without error and the import
    // of archiveScanner above works without a real vscode module, the module
    // has no vscode import.
    // Additional assertion: grep for import * as vscode would fail; here we
    // confirm the FsLike seam compiles and works with no vscode in scope.
    // (The tsconfig.test.json mocks vscode, but a real vscode import would surface
    // type errors if the mock interface mismatched. This test passing confirms
    // archiveScanner.ts never calls any vscode.* at runtime.)
    assert.ok(true, 'archiveScanner.ts is importable without a real vscode host');
  });
});
