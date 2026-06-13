import * as os from 'os';
import * as path from 'path';
import * as fs from 'fs';
import { execFile } from 'child_process';
import * as vscode from 'vscode';

let pythonPath = 'python3';

/** Call once from activate(); reads quoin.pythonPath setting (placeholder for S-6) */
export function setPythonPath(p: string): void {
  pythonPath = p;
}

function canRunPython(): Promise<boolean> {
  return new Promise((resolve) => {
    execFile(pythonPath, ['--version'], { timeout: 5000 }, (err) => resolve(!err));
  });
}

export async function checkScriptRoots(homeBase = os.homedir()): Promise<boolean> {
  const adapterRoot = path.join(homeBase, '.claude', 'scripts');
  const coreRoot = path.join(homeBase, '.claude', 'core', 'scripts');
  const coreMarker = path.join(coreRoot, 'dashboard_model.py');

  const failures: string[] = [];

  if (!(await canRunPython())) {
    failures.push(`python3 not found on PATH (tried: ${pythonPath})`);
  }
  if (!fs.existsSync(adapterRoot)) {
    failures.push(`adapter scripts missing: ${adapterRoot}`);
  }
  if (!fs.existsSync(coreRoot)) {
    failures.push(`core scripts missing: ${coreRoot}`);
  }
  if (!fs.existsSync(coreMarker)) {
    failures.push(`core marker missing: ${coreMarker}`);
  }

  const ok = failures.length === 0;
  void vscode.commands.executeCommand('setContext', 'quoin.scriptsAvailable', ok);

  if (!ok) {
    const detail = failures.join('\n');
    const choice = await vscode.window.showErrorMessage(
      'Quoin: required scripts not found. Run `bash quoin/install.sh` from the quoin repo, then reload the window.',
      'Show Details'
    );
    if (choice === 'Show Details') {
      const channel = vscode.window.createOutputChannel('Quoin');
      channel.appendLine(detail);
      channel.show();
    }
  }

  return ok; // non-fatal: caller continues regardless
}
