import * as path from 'node:path';
import { FsLike } from './archiveScanner';

/**
 * Walk up from startDir, returning the first ancestor directory that contains
 * a `.workflow_artifacts/` subdirectory, or undefined if none is found.
 *
 * This is the single canonical implementation — dataService.getProjectRoot
 * and commands.resolveProjectRoot both delegate here so session.projectRoot
 * is always the artifacts-root, never a raw workspace folder path.
 */
export function findArtifactsRoot(
  startDir: string,
  fsImpl: Pick<FsLike, 'existsSync'>,
): string | undefined {
  let dir = startDir;
  for (let i = 0; i < 20; i++) {
    if (fsImpl.existsSync(path.join(dir, '.workflow_artifacts'))) {
      return dir;
    }
    const parent = path.dirname(dir);
    if (parent === dir) { break; }
    dir = parent;
  }
  return undefined;
}
