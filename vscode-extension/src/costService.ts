/**
 * costService.ts — pure parse layer over cost data sources.
 * No `vscode` import — fully unit-testable with injectable seams.
 *
 * Data sources (read-only consumers; no Python edits this stage):
 *   - spend_monitor.py --json --scope project  (today_usd + by_task, project-scoped)
 *   - dashboard_model.py --json (counts-mode)  (task enumeration only; usd always null)
 *   - on-disk cost-summary.json files           (finalized totals, heterogeneous schema)
 *
 * Design decisions honored:
 *   D-01: No --with-cost flag; per-task USD from existing CLIs only.
 *   D-02: State precedence: unavailable > partial > counts-only > live.
 *         'unavailable' keys on ABSENCE of a resolvable total, NOT on fallback_used.
 *   D-05: --scope project aligns today_usd and by_task to same scope.
 *   D-06: cost-summary.json key-priority ladder tolerates 7 different total-key spellings.
 *   D-07: today_usd and finalized_usd are DISTINCT columns, NEVER summed.
 */

// ── Public types ──────────────────────────────────────────────────────────────

/**
 * Four cost UI states (R-02):
 *   live         — a real float incl. $0.00 (NOT unavailable)
 *   counts-only  — counts-mode usd:null from dashboard_model, no summary total
 *   partial      — a present total with fallback_used:true / by_task_partial:true
 *   unavailable  — NO resolvable numeric total anywhere
 */
export type CostState = 'live' | 'counts-only' | 'partial' | 'unavailable';

/** Numeric rank for precedence comparison (D-02). Higher rank wins. */
const STATE_RANK: Record<CostState, number> = {
  live: 0,
  'counts-only': 1,
  partial: 2,
  unavailable: 3,
};

export interface LiveSpend {
  today_usd: number;
  by_model: Record<string, number>;
  by_model_pct: Record<string, number>;
  by_task: Record<string, number>;
  by_task_partial: boolean;
  scope: string;
  stale: boolean;
}

/** Per-task cost row — two distinct, never-summed columns (D-07). */
export interface TaskCost {
  task: string;
  /** Today's spend (project scope). null if not in spend_monitor.by_task. */
  today_usd: number | null;
  /** Finalized total from cost-summary.json key-priority ladder. null if unresolvable. */
  finalized_usd: number | null;
  /** Worst-case state across both columns for this task. */
  state: CostState;
}

export interface CostView {
  /** Live spend snapshot (null if spend_monitor invocation failed). */
  live: LiveSpend | null;
  /** Per-task rows with two independent columns. */
  tasks: TaskCost[];
  /** Sum of resolvable finalized_usd values. null if none resolved. */
  finalizedGrandTotal: number | null;
  /** Worst-precedence state across all summaries. */
  finalizedGrandTotalState: CostState;
  /** Human-readable note about project scope alignment (D-05). */
  scopeNote: string;
}

/** Intermediate parse result from a single cost-summary.json file. */
export interface SummaryResult {
  task: string;
  finalizedUsd: number | null;
  state: CostState;
}

// ── State helpers ─────────────────────────────────────────────────────────────

/** Return the higher-precedence of two CostStates (D-02). */
export function worstState(a: CostState, b: CostState): CostState {
  return STATE_RANK[a] >= STATE_RANK[b] ? a : b;
}

/** Return true if the value is a finite number (rejects NaN, Infinity, strings). */
function isFiniteNumber(v: unknown): v is number {
  return typeof v === 'number' && isFinite(v);
}

// ── Key-priority ladder (D-06) ────────────────────────────────────────────────

const TOTAL_KEY_LADDER = [
  'grand_total',
  'grand_total_usd',
  'total_usd',
  'total_cost_usd',
  'period_total_cost_usd',
  'estimated_task_cost_usd',
  'task_total',
] as const;

/**
 * Resolve a numeric total from an object using the D-06 key-priority ladder.
 * Returns the first finite numeric hit, or null if none found.
 */
function resolveTotalFromLadder(obj: Record<string, unknown>): number | null {
  for (const key of TOTAL_KEY_LADDER) {
    if (key in obj) {
      const v = obj[key];
      if (isFiniteNumber(v)) {
        return v;
      }
    }
  }
  return null;
}

/**
 * Check if an object has any fallback indicator (D-02).
 * A present total with any of these → state = 'partial', not 'unavailable'.
 */
function hasFallbackIndicator(obj: Record<string, unknown>): boolean {
  if (obj['fallback_used'] === true) { return true; }
  if (typeof obj['fallback_note'] === 'string' && obj['fallback_note']) { return true; }
  // Check for *_partial keys
  return Object.keys(obj).some((k) => k.endsWith('_partial') && obj[k] === true);
}

// ── Pure parse functions ──────────────────────────────────────────────────────

/**
 * Parse spend_monitor.py --json --scope project output.
 * Returns LiveSpend on success, null on any error.
 * today_usd: 0.0 is a VALID live value, NOT unavailable.
 */
export function parseLiveSpend(
  stdout: string,
  stderr: string,
  err: Error | null,
): LiveSpend | null {
  void stderr; // stderr is informational only; we don't fail on it
  if (err && !stdout.trim()) { return null; }
  const trimmed = stdout.trim();
  if (!trimmed) { return null; }
  try {
    const data = JSON.parse(trimmed) as Record<string, unknown>;
    // Validate required shape
    if (typeof data['today_usd'] !== 'number') { return null; }
    if (typeof data['by_task'] !== 'object' || data['by_task'] === null) { return null; }
    return {
      today_usd: data['today_usd'] as number,
      by_model: (data['by_model'] as Record<string, number>) ?? {},
      by_model_pct: (data['by_model_pct'] as Record<string, number>) ?? {},
      by_task: (data['by_task'] as Record<string, number>),
      by_task_partial: data['by_task_partial'] === true,
      scope: typeof data['scope'] === 'string' ? data['scope'] : 'project',
      stale: data['stale'] === true,
    };
  } catch {
    return null;
  }
}

/**
 * Parse dashboard_model.py --json (counts-mode) output.
 * Returns an array of {task, usd} pairs. usd is ALWAYS null in counts-mode.
 * Returns [] on any error.
 */
export function parseTaskCounts(
  stdout: string,
  stderr: string,
  err: Error | null,
): Array<{ task: string; usd: number | null }> {
  void stderr;
  if (err && !stdout.trim()) { return []; }
  const trimmed = stdout.trim();
  if (!trimmed) { return []; }
  try {
    const data = JSON.parse(trimmed) as Record<string, unknown>;
    if (!Array.isArray(data['tasks'])) { return []; }
    const tasks = data['tasks'] as Array<Record<string, unknown>>;
    return tasks
      .filter((t) => typeof t['name'] === 'string')
      .map((t) => ({
        task: t['name'] as string,
        usd: null, // always null in counts-mode
      }));
  } catch {
    return [];
  }
}

/**
 * Parse one cost-summary.json file text via the D-06 key-priority ladder.
 *
 * State derivation (D-02):
 *   - NO resolvable numeric total → 'unavailable'
 *   - Present total + fallback indicator → 'partial'
 *   - Present total, no fallback → 'live'
 *
 * For the HYBRID active-task shape (per-stage blocks "S-1".."S-4" + summary),
 * the summary-block ladder is tried first; if absent, sums the present
 * per-stage block task_total values as a fallback total.
 *
 * Never throws; malformed input → { task: '', finalizedUsd: null, state: 'unavailable' }.
 */
export function parseCostSummary(
  fileText: string,
  taskName: string = '',
): SummaryResult {
  const safe: SummaryResult = { task: taskName, finalizedUsd: null, state: 'unavailable' };
  try {
    const data = JSON.parse(fileText) as Record<string, unknown>;

    // Step 1: try the ladder on the top-level object (covers summary-block for hybrid)
    let total = resolveTotalFromLadder(data);

    // Step 2: hybrid fallback — if no top-level total, sum present S-* block task_totals
    if (total === null) {
      let stageSumTotal = 0;
      let foundAnyStage = false;
      for (const key of Object.keys(data)) {
        // Stage blocks match "S-N" where N is one or more digits
        if (/^S-\d+$/.test(key)) {
          const block = data[key] as Record<string, unknown> | null;
          if (block && typeof block === 'object') {
            const stageTotal = block['task_total'];
            if (isFiniteNumber(stageTotal)) {
              stageSumTotal += stageTotal;
              foundAnyStage = true;
            }
          }
        }
      }
      if (foundAnyStage) {
        total = stageSumTotal;
      }
    }

    // Step 3: determine state
    if (total === null) {
      return { task: taskName, finalizedUsd: null, state: 'unavailable' };
    }

    // Present total — check for fallback indicators (D-02)
    const hasFallback = hasFallbackIndicator(data);
    const state: CostState = hasFallback ? 'partial' : 'live';
    return { task: taskName, finalizedUsd: total, state };
  } catch {
    return safe;
  }
}

// ── mergeCostView ─────────────────────────────────────────────────────────────

/**
 * Fold live spend, task counts, and summaries into a unified CostView.
 * D-07: today_usd and finalized_usd are NEVER summed together.
 * D-02: per-task state = worst across contributing columns.
 */
export function mergeCostView(
  live: LiveSpend | null,
  taskCounts: Array<{ task: string; usd: number | null }>,
  summaries: SummaryResult[],
): CostView {
  // Build a unified set of task names across all sources
  const taskNames = new Set<string>();
  if (live) {
    for (const t of Object.keys(live.by_task)) { taskNames.add(t); }
  }
  for (const tc of taskCounts) { taskNames.add(tc.task); }
  for (const s of summaries) { if (s.task) { taskNames.add(s.task); } }

  const summaryMap = new Map<string, SummaryResult>();
  for (const s of summaries) { summaryMap.set(s.task, s); }

  const tasks: TaskCost[] = [];
  let grandTotalSum = 0;
  let hasAnyFinalized = false;
  let grandTotalState: CostState = 'live';

  for (const taskName of taskNames) {
    // today column (from spend_monitor.by_task)
    const today_usd = live?.by_task[taskName] ?? null;

    // today state
    let todayState: CostState | null = null;
    if (today_usd !== null) {
      todayState = (live?.by_task_partial === true) ? 'partial' : 'live';
    }

    // finalized column (from cost-summary.json)
    const summary = summaryMap.get(taskName);
    const finalized_usd = summary?.finalizedUsd ?? null;
    const finalizedState: CostState = summary?.state ?? 'unavailable';

    // counts-only state: task appears in taskCounts with usd:null and no summary total
    let countsState: CostState | null = null;
    const hasCountsEntry = taskCounts.some((tc) => tc.task === taskName);
    if (hasCountsEntry && finalized_usd === null && today_usd === null) {
      countsState = 'counts-only';
    }

    // Aggregate finalized grand total
    if (finalized_usd !== null) {
      grandTotalSum += finalized_usd;
      hasAnyFinalized = true;
      grandTotalState = worstState(grandTotalState, finalizedState);
    } else if (summary) {
      // summary was found but total was null → 'unavailable' affects grand total state
      grandTotalState = worstState(grandTotalState, 'unavailable');
    }

    // Per-task worst state (D-02)
    let taskState: CostState = 'live'; // default to best
    if (todayState !== null) { taskState = worstState(taskState, todayState); }
    if (summary) { taskState = worstState(taskState, finalizedState); }
    if (countsState !== null) { taskState = worstState(taskState, countsState); }
    // If we have no data at all for this task
    if (today_usd === null && finalized_usd === null && !hasCountsEntry) {
      taskState = 'unavailable';
    }

    tasks.push({ task: taskName, today_usd, finalized_usd, state: taskState });
  }

  // Build scope note (D-05)
  const scopeNote = live
    ? `Today's spend is project-scoped (${live.scope}). Per-task USD uses spend_monitor --scope project.`
    : 'Live spend data unavailable.';

  return {
    live,
    tasks,
    finalizedGrandTotal: hasAnyFinalized ? grandTotalSum : null,
    finalizedGrandTotalState: hasAnyFinalized ? grandTotalState : 'unavailable',
    scopeNote,
  };
}
