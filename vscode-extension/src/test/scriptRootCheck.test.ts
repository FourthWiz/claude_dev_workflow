import { describe, it, mock } from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// We test the core logic in isolation by extracting the check function.
// The vscode module is mocked because tests run outside the extension host.

// --- inline pure-logic port of checkScriptRoots for unit testing ---

interface CheckResult {
  ok: boolean;
  failures: string[];
}

async function checkScriptRootsLogic(
  homeBase: string,
  canRunPython: () => Promise<boolean>
): Promise<CheckResult> {
  const adapterRoot = path.join(homeBase, '.claude', 'scripts');
  const coreRoot = path.join(homeBase, '.claude', 'core', 'scripts');
  const coreMarker = path.join(coreRoot, 'dashboard_model.py');
  const failures: string[] = [];

  if (!(await canRunPython())) failures.push('python3 not found on PATH');
  if (!fs.existsSync(adapterRoot)) failures.push(`adapter scripts missing: ${adapterRoot}`);
  if (!fs.existsSync(coreRoot)) failures.push(`core scripts missing: ${coreRoot}`);
  if (!fs.existsSync(coreMarker)) failures.push(`core marker missing: ${coreMarker}`);

  return { ok: failures.length === 0, failures };
}

// --- helpers ---

function makeFakeHome(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'quoin-test-'));
  return dir;
}

function setupFullRoots(home: string): void {
  const adapterRoot = path.join(home, '.claude', 'scripts');
  const coreRoot = path.join(home, '.claude', 'core', 'scripts');
  fs.mkdirSync(adapterRoot, { recursive: true });
  fs.mkdirSync(coreRoot, { recursive: true });
  fs.writeFileSync(path.join(coreRoot, 'dashboard_model.py'), '# stub');
}

// --- tests ---

describe('checkScriptRoots logic', () => {
  it('passes when both roots and dashboard_model.py are present and python3 available', async () => {
    const home = makeFakeHome();
    setupFullRoots(home);
    const result = await checkScriptRootsLogic(home, async () => true);
    assert.equal(result.ok, true);
    assert.deepEqual(result.failures, []);
  });

  it('fails with specific message when core marker (dashboard_model.py) is absent', async () => {
    const home = makeFakeHome();
    setupFullRoots(home);
    fs.unlinkSync(path.join(home, '.claude', 'core', 'scripts', 'dashboard_model.py'));
    const result = await checkScriptRootsLogic(home, async () => true);
    assert.equal(result.ok, false);
    assert.ok(result.failures.some((f) => f.includes('core marker missing')));
  });

  it('fails distinctly when python3 is absent', async () => {
    const home = makeFakeHome();
    setupFullRoots(home);
    const result = await checkScriptRootsLogic(home, async () => false);
    assert.equal(result.ok, false);
    assert.ok(result.failures.some((f) => f.includes('python3 not found')));
  });

  it('reports adapter scripts missing', async () => {
    const home = makeFakeHome();
    // Only create core root, not adapter root
    const coreRoot = path.join(home, '.claude', 'core', 'scripts');
    fs.mkdirSync(coreRoot, { recursive: true });
    fs.writeFileSync(path.join(coreRoot, 'dashboard_model.py'), '# stub');
    const result = await checkScriptRootsLogic(home, async () => true);
    assert.equal(result.ok, false);
    assert.ok(result.failures.some((f) => f.includes('adapter scripts missing')));
  });
});
