/**
 * ArchiveScanner — pure fs scan + parse module.
 * No `vscode` import (unit-testable like workflowMapping.ts).
 * All fs access goes through an injectable FsLike seam.
 */
import * as path from 'node:path';

// ── Public types ──────────────────────────────────────────────────────────────

export interface ArchivedSession {
  /** Display label, e.g. "vscode-extension review" (from frontmatter task+phase) or
   *  "# Session State —" heading, or filename stem. */
  label: string;
  /** Absolute path to the .md file to open on click. */
  filePath: string;
  /** Source bucket — drives the group/badge in the UI. */
  source: 'session' | 'checkpoint';
  /** ISO date: from frontmatter `date:` first, then filename prefix (YYYY-MM-DD), or undefined. */
  date?: string;
  /** Status line if present (from `## Status` or `## Current stage` body heading); optional. */
  status?: string;
  /** Active task name: from frontmatter `task:` first, then `## Active task` body heading; optional. */
  task?: string;
}

/** Minimal fs seam for testability — defaults to node:fs sync calls in the provider. */
export interface FsLike {
  existsSync(p: string): boolean;
  readdirSync(p: string): string[];
  readFileSync(p: string, enc: 'utf8'): string;
}

// ── Pure parse helpers ────────────────────────────────────────────────────────

/**
 * Parse YAML frontmatter block at the top of a session-state file.
 * Returns parsed fields; all optional. Returns {} if no frontmatter present.
 * Frontmatter is a leading `---\n...\n---` block; only simple `key: value` scalar
 * lines are extracted. Never throws; malformed frontmatter → {}.
 * Value extraction splits on the FIRST colon only (handles `value: with: colons`).
 */
export function parseFrontmatter(body: string): {
  task?: string;
  phase?: string;
  date?: string;
  artifact?: string;
  [key: string]: string | undefined;
} {
  try {
    if (!body.startsWith('---\n')) { return {}; }
    const end = body.indexOf('\n---\n', 4);
    if (end === -1) { return {}; }
    const block = body.slice(4, end);
    const result: Record<string, string> = {};
    for (const line of block.split('\n')) {
      const colonIdx = line.indexOf(':');
      if (colonIdx < 1) { continue; } // no colon or leading colon → skip
      const key = line.slice(0, colonIdx).trim();
      const value = line.slice(colonIdx + 1).trim(); // everything AFTER the first colon
      if (/^\w+$/.test(key) && value) {
        result[key] = value;
      }
    }
    return result;
  } catch {
    return {};
  }
}

/**
 * Shared heading-section value extractor.
 * 1. Finds the line equal to `## <headingText>` (exact match).
 * 2. Advances past the heading, skipping any blank lines.
 * 3. Returns the first non-blank line trimmed, OR
 * 4. Returns undefined if EOF is reached OR the first non-blank line starts
 *    with `#` (i.e. the section is empty — the next heading immediately follows).
 * Handles all three real on-disk shapes:
 *   Shape A — blank line between heading and value (session files).
 *   Shape B — value on the immediately following line (checkpoint files).
 *   Shape C — empty section (next non-blank line is another heading → undefined).
 */
export function extractSection(body: string, headingText: string): string | undefined {
  const lines = body.split('\n');
  // Accept headingText already prefixed with '## ' for convenience
  const target = headingText.startsWith('## ') ? headingText : `## ${headingText}`;
  const idx = lines.findIndex((l) => l === target);
  if (idx === -1) { return undefined; } // heading not found

  for (let i = idx + 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (line === '') { continue; }                   // skip blank lines (handles Shape A)
    if (line.startsWith('#')) { return undefined; }  // next non-blank is a heading → empty section (Shape C)
    return line;                                      // first non-blank non-heading line (Shape B or Shape A value)
  }
  return undefined; // EOF after heading with no value
}

/**
 * Extract ISO date prefix from filename.
 * Returns 'YYYY-MM-DD' if filename starts with that pattern, else undefined.
 */
export function parseDateFromFilename(filename: string): string | undefined {
  const m = filename.match(/^(\d{4}-\d{2}-\d{2})-/);
  return m ? m[1] : undefined;
}

/**
 * Derive a display label for a session file.
 * Priority:
 *   1. Frontmatter task+phase → "<task> <phase>"
 *   2. Frontmatter task only → "<task>"
 *   3. Body `# Session State — <rest>` heading
 *   4. Filename stem (date prefix stripped, dashes → spaces)
 */
export function parseSessionLabel(filename: string, body: string): string {
  const fm = parseFrontmatter(body);
  if (fm.task && fm.phase) { return `${fm.task} ${fm.phase}`; }
  if (fm.task) { return fm.task; }

  // Body heading fallback
  const m = body.match(/^#\s*Session State\s*[—-]\s*(.+)$/m);
  if (m) { return m[1].trim(); }

  // Filename stem fallback
  const stem = filename
    .replace(/^\d{4}-\d{2}-\d{2}-/, '')
    .replace(/\.md$/, '');
  return stem.replace(/-/g, ' ');
}

/**
 * Extract metadata (status, task) from a file body.
 * Frontmatter keys take priority over body headings.
 * NOTE: callers that already parsed frontmatter should pass frontmatter `task` directly.
 */
export function parseSessionMeta(body: string): { status?: string; task?: string } {
  const fm = parseFrontmatter(body);
  const task: string | undefined =
    fm.task ||
    extractSection(body, '## Active task') ||
    undefined;

  const status: string | undefined =
    extractSection(body, '## Status') ??
    extractSection(body, '## Current stage') ??
    undefined;

  return { status, task };
}

// ── scanArchive ───────────────────────────────────────────────────────────────

/**
 * Scan the three durable on-disk session sources under the given project root
 * and return a normalized, de-duplicated, sorted ArchivedSession[].
 *
 * Sources:
 *  - .workflow_artifacts/memory/sessions/*.md   (source: 'session')
 *  - .workflow_artifacts/memory/checkpoints/*.md (source: 'checkpoint')
 *  - .workflow_artifacts/memory/recent-sessions.md (read-and-ignore, D-03)
 */
export function scanArchive(projectRoot: string, fsImpl: FsLike): ArchivedSession[] {
  const memoryDir = path.join(projectRoot, '.workflow_artifacts', 'memory');
  const out: ArchivedSession[] = [];

  const sources: Array<[string, 'session' | 'checkpoint']> = [
    ['sessions', 'session'],
    ['checkpoints', 'checkpoint'],
  ];

  for (const [dirName, sourceKind] of sources) {
    const fullDir = path.join(memoryDir, dirName);
    if (!fsImpl.existsSync(fullDir)) { continue; }

    let names: string[];
    try {
      names = fsImpl.readdirSync(fullDir);
    } catch {
      continue;
    }

    for (const name of names) {
      if (!name.endsWith('.md')) { continue; }
      const filePath = path.join(fullDir, name);

      let body: string;
      try {
        body = fsImpl.readFileSync(filePath, 'utf8');
      } catch {
        continue; // skip unreadable file (S4-1)
      }

      // Parse frontmatter first (MAJ-1)
      const fm = parseFrontmatter(body);
      const date = fm.date ?? parseDateFromFilename(name);
      const label = parseSessionLabel(name, body);
      const task = fm.task || extractSection(body, '## Active task') || undefined;
      const status =
        extractSection(body, '## Status') ??
        extractSection(body, '## Current stage') ??
        undefined;

      out.push({ label, filePath, source: sourceKind, date, status, task });
    }
  }

  // recent-sessions.md: read-and-ignore as a row source (D-03)
  const recentPath = path.join(memoryDir, 'recent-sessions.md');
  if (fsImpl.existsSync(recentPath)) {
    try {
      fsImpl.readFileSync(recentPath, 'utf8'); // read to honor "scan inputs"; contribute 0 rows
    } catch {
      // ignore read failure
    }
  }

  // De-dupe by filePath
  const seen = new Set<string>();
  const deduped = out.filter((entry) => {
    if (seen.has(entry.filePath)) { return false; }
    seen.add(entry.filePath);
    return true;
  });

  // Sort: newest date first; undefined-date last; within same date, filename descending (stable)
  deduped.sort((a, b) => {
    const aDate = a.date;
    const bDate = b.date;
    if (aDate && bDate) {
      if (bDate > aDate) { return 1; }
      if (aDate > bDate) { return -1; }
      // Same date: sort by filePath descending
      return b.filePath > a.filePath ? 1 : b.filePath < a.filePath ? -1 : 0;
    }
    if (aDate && !bDate) { return -1; }
    if (!aDate && bDate) { return 1; }
    // Both undefined: sort by filePath descending
    return b.filePath > a.filePath ? 1 : b.filePath < a.filePath ? -1 : 0;
  });

  return deduped;
}
