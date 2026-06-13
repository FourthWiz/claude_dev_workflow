export type Runtime = 'claude' | 'codex';

export interface QuoinSession {
  id: string;
  label: string;
  runtime: Runtime;
  terminal?: import('vscode').Terminal;
  projectRoot: string;
  taskName?: string;
  createdAt: number;
  relaunchable: boolean;
}

/** Shape persisted to globalState — terminal is not serializable */
export type PersistedSession = Omit<QuoinSession, 'terminal'>;
