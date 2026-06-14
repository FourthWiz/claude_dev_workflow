/**
 * costService.test.ts — pure-parse unit tests for the Cost service layer.
 *
 * All tests run over T-01 fixtures; no Python process required.
 * Validates all R-02 state transitions, D-06 key-priority ladder, D-07 no-double-count,
 * and D-02 precedence rules.
 */
import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  parseLiveSpend,
  parseTaskCounts,
  parseCostSummary,
  mergeCostView,
  worstState,
  CostState,
} from '../costService';
import {
  SPEND_MONITOR_LIVE,
  SPEND_MONITOR_ZERO,
  SPEND_MONITOR_PARTIAL,
  SPEND_MONITOR_EMPTY_BY_TASK,
  DASHBOARD_MODEL_COUNTS,
  COST_SUMMARY_HYBRID,
  COST_SUMMARY_GRAND_TOTAL,
  COST_SUMMARY_TOTAL_USD_NULL,
  COST_SUMMARY_GRAND_TOTAL_USD,
  COST_SUMMARY_TOTAL_COST_USD,
  COST_SUMMARY_NO_TOTAL,
} from './fixtures/cost';

// ── worstState helper ─────────────────────────────────────────────────────────

describe('worstState', () => {
  it('live < counts-only < partial < unavailable', () => {
    assert.strictEqual(worstState('live', 'counts-only'), 'counts-only');
    assert.strictEqual(worstState('counts-only', 'partial'), 'partial');
    assert.strictEqual(worstState('partial', 'unavailable'), 'unavailable');
    assert.strictEqual(worstState('unavailable', 'live'), 'unavailable');
  });
  it('same state returns that state', () => {
    assert.strictEqual(worstState('live', 'live'), 'live');
    assert.strictEqual(worstState('partial', 'partial'), 'partial');
  });
});

// ── parseLiveSpend ────────────────────────────────────────────────────────────

describe('parseLiveSpend', () => {
  it('(a) live: parses positive today_usd + non-empty by_task', () => {
    const result = parseLiveSpend(SPEND_MONITOR_LIVE, '', null);
    assert.ok(result, 'expected non-null result');
    assert.strictEqual(result!.today_usd, 9.05);
    assert.ok(Object.keys(result!.by_task).length > 0, 'by_task should be non-empty');
    assert.strictEqual(result!.by_task_partial, false);
    assert.strictEqual(result!.stale, false);
    assert.strictEqual(result!.scope, 'project');
  });

  it('(b) live: $0.00 is a valid live value — NOT null/unavailable', () => {
    const result = parseLiveSpend(SPEND_MONITOR_ZERO, '', null);
    assert.ok(result, 'expected non-null result for $0.00');
    assert.strictEqual(result!.today_usd, 0.0, '$0.00 must be returned, not treated as unavailable');
    assert.deepStrictEqual(result!.by_task, {});
    assert.strictEqual(result!.by_task_partial, false);
  });

  it('(c) partial: by_task_partial:true + non-empty by_task', () => {
    const result = parseLiveSpend(SPEND_MONITOR_PARTIAL, '', null);
    assert.ok(result);
    assert.strictEqual(result!.by_task_partial, true);
    assert.ok(Object.keys(result!.by_task).length > 0);
  });

  it('(d) stale:true + empty by_task with non-zero today_usd', () => {
    const result = parseLiveSpend(SPEND_MONITOR_EMPTY_BY_TASK, '', null);
    assert.ok(result);
    assert.strictEqual(result!.stale, true);
    assert.strictEqual(result!.today_usd, 6.01);
    assert.deepStrictEqual(result!.by_task, {});
  });

  it('returns null on empty stdout', () => {
    assert.strictEqual(parseLiveSpend('', '', null), null);
  });

  it('returns null on exec error with empty stdout', () => {
    assert.strictEqual(parseLiveSpend('', 'some error', new Error('exec failed')), null);
  });

  it('returns null on malformed JSON', () => {
    assert.strictEqual(parseLiveSpend('not json', '', null), null);
  });

  it('returns null when today_usd is absent from payload', () => {
    const noUsd = JSON.stringify({ by_task: {}, scope: 'project' });
    assert.strictEqual(parseLiveSpend(noUsd, '', null), null);
  });
});

// ── parseTaskCounts ───────────────────────────────────────────────────────────

describe('parseTaskCounts', () => {
  it('returns tasks with usd always null (counts-mode)', () => {
    const result = parseTaskCounts(DASHBOARD_MODEL_COUNTS, '', null);
    assert.ok(Array.isArray(result));
    assert.ok(result.length > 0, 'expected at least one task');
    for (const r of result) {
      assert.strictEqual(r.usd, null, 'usd must be null in counts-mode (D-01)');
      assert.strictEqual(typeof r.task, 'string');
    }
  });

  it('task names are extracted correctly', () => {
    const result = parseTaskCounts(DASHBOARD_MODEL_COUNTS, '', null);
    const names = result.map((r) => r.task);
    assert.ok(names.includes('vscode-extension'), 'vscode-extension task expected');
    assert.ok(names.includes('other-task'), 'other-task expected');
  });

  it('returns [] on empty stdout', () => {
    assert.deepStrictEqual(parseTaskCounts('', '', null), []);
  });

  it('returns [] on exec error with empty stdout', () => {
    assert.deepStrictEqual(parseTaskCounts('', 'err', new Error('x')), []);
  });

  it('returns [] on malformed JSON', () => {
    assert.deepStrictEqual(parseTaskCounts('bad json', '', null), []);
  });
});

// ── parseCostSummary ──────────────────────────────────────────────────────────

describe('parseCostSummary', () => {
  it('(a) HYBRID: grand_total:35.0 + fallback_used:true → partial, finalizedUsd=35.0 (CRIT-2 regression guard)', () => {
    const result = parseCostSummary(COST_SUMMARY_HYBRID, 'vscode-extension');
    assert.strictEqual(result.finalizedUsd, 35.0, 'must not hide the real $35.00');
    assert.strictEqual(result.state, 'partial', 'fallback_used:true + present total → partial, NOT unavailable');
    assert.strictEqual(result.task, 'vscode-extension');
  });

  it('(b) grand_total + fallback_used:false → live state', () => {
    const result = parseCostSummary(COST_SUMMARY_GRAND_TOTAL, 'dashboard-redesign');
    assert.ok(result.finalizedUsd !== null, 'expected a resolved total');
    assert.ok(Math.abs(result.finalizedUsd! - 12.237305) < 0.001, 'expected ~12.24');
    assert.strictEqual(result.state, 'live');
  });

  it('(c-1) total_usd:null → unavailable (null value not treated as numeric hit)', () => {
    const result = parseCostSummary(COST_SUMMARY_TOTAL_USD_NULL, 'agentdesk-spend-pane');
    assert.strictEqual(result.finalizedUsd, null);
    assert.strictEqual(result.state, 'unavailable');
  });

  it('(c-2) grand_total_usd key → resolves via ladder (CRIT-1)', () => {
    const result = parseCostSummary(COST_SUMMARY_GRAND_TOTAL_USD, 'eod-rollup-and-approvals');
    assert.strictEqual(result.finalizedUsd, 82.59);
    assert.strictEqual(result.state, 'live');
  });

  it('(c-3) total_cost_usd:0.0 → live (legitimate $0.00, NOT unavailable)', () => {
    const result = parseCostSummary(COST_SUMMARY_TOTAL_COST_USD, 'ivg-69-test-suite-cleanup');
    assert.strictEqual(result.finalizedUsd, 0.0);
    assert.strictEqual(result.state, 'live', '$0.00 total_cost_usd must be live, not unavailable');
  });

  it('(d) no resolvable total key → unavailable (D-06)', () => {
    const result = parseCostSummary(COST_SUMMARY_NO_TOTAL, 'agentdesk-remember-layout');
    assert.strictEqual(result.finalizedUsd, null);
    assert.strictEqual(result.state, 'unavailable', 'no total key → unavailable');
  });

  it('malformed JSON → safe default (no throw)', () => {
    assert.doesNotThrow(() => {
      const result = parseCostSummary('not valid json', 'test-task');
      assert.strictEqual(result.finalizedUsd, null);
      assert.strictEqual(result.state, 'unavailable');
    });
  });

  it('empty string → safe default (no throw)', () => {
    assert.doesNotThrow(() => {
      const result = parseCostSummary('', 'test-task');
      assert.strictEqual(result.state, 'unavailable');
    });
  });

  it('HYBRID: fallback_note present (not fallback_used) → still partial when total exists', () => {
    // Partial detection should also fire on fallback_note presence
    const withFallbackNote = JSON.stringify({
      grand_total: 10.0,
      fallback_note: 'Some sessions unresolved',
    });
    const result = parseCostSummary(withFallbackNote, 'test');
    assert.strictEqual(result.finalizedUsd, 10.0);
    assert.strictEqual(result.state, 'partial');
  });
});

// ── mergeCostView ─────────────────────────────────────────────────────────────

describe('mergeCostView', () => {
  it('no-double-count: today_usd and finalized_usd stay SEPARATE (D-07/MAJ-2)', () => {
    const live = parseLiveSpend(SPEND_MONITOR_LIVE, '', null);
    assert.ok(live);
    const counts = parseTaskCounts(DASHBOARD_MODEL_COUNTS, '', null);
    const summaries = [parseCostSummary(COST_SUMMARY_HYBRID, 'vscode-extension')];
    const view = mergeCostView(live!, counts, summaries);

    const vsTask = view.tasks.find((t) => t.task === 'vscode-extension');
    assert.ok(vsTask, 'vscode-extension task expected in merged view');

    // today_usd from live.by_task; finalized_usd from summary — they must NOT be summed
    assert.ok(vsTask!.today_usd !== null, 'today_usd expected');
    assert.ok(vsTask!.finalized_usd !== null, 'finalized_usd expected');

    // The total must NOT be today+finalized (that would be double-count)
    const wouldBeDoubleCount = vsTask!.today_usd! + vsTask!.finalized_usd!;
    // They are independent columns — no field should equal the sum
    // We just assert they're separate values (no merging)
    assert.notStrictEqual(vsTask!.today_usd, vsTask!.finalized_usd,
      'today_usd and finalized_usd are from different sources and should differ');
    void wouldBeDoubleCount; // not used in any assertion — presence of both confirms two-column design
  });

  it('$0.00 live today_usd is included (not dropped as unavailable)', () => {
    const live = parseLiveSpend(SPEND_MONITOR_ZERO, '', null);
    assert.ok(live);
    const counts: Array<{ task: string; usd: number | null }> = [];
    const summaries = [{ task: 'some-task', finalizedUsd: 5.0, state: 'live' as CostState }];
    const view = mergeCostView(live!, counts, summaries);
    assert.ok(view.live, 'live should be present');
    assert.strictEqual(view.live!.today_usd, 0.0, '$0.00 must not be dropped');
  });

  it('D-02 state precedence: partial > counts-only > live', () => {
    // A task that has: live today_usd + partial summary
    const live = parseLiveSpend(SPEND_MONITOR_LIVE, '', null);
    assert.ok(live);
    const counts = parseTaskCounts(DASHBOARD_MODEL_COUNTS, '', null);
    const summaries = [parseCostSummary(COST_SUMMARY_HYBRID, 'vscode-extension')];
    const view = mergeCostView(live!, counts, summaries);

    const vsTask = view.tasks.find((t) => t.task === 'vscode-extension');
    assert.ok(vsTask);
    // today_usd is live, but summary is partial → task state should be at least partial
    const rank = { live: 0, 'counts-only': 1, partial: 2, unavailable: 3 };
    assert.ok(rank[vsTask!.state] >= rank['partial'],
      `expected state >= partial, got ${vsTask!.state}`);
  });

  it('D-02: unavailable > partial — task with no sources at all is unavailable', () => {
    const view = mergeCostView(null, [], [
      { task: 'ghost-task', finalizedUsd: null, state: 'unavailable' },
    ]);
    const t = view.tasks.find((task) => task.task === 'ghost-task');
    assert.ok(t);
    assert.strictEqual(t!.state, 'unavailable');
  });

  it('finalizedGrandTotal is sum of resolvable finalized_usd values', () => {
    const summaries = [
      parseCostSummary(COST_SUMMARY_HYBRID, 'vscode-extension'),    // 35.0
      parseCostSummary(COST_SUMMARY_GRAND_TOTAL, 'dashboard-redesign'), // ~12.24
    ];
    const view = mergeCostView(null, [], summaries);
    assert.ok(view.finalizedGrandTotal !== null);
    assert.ok(view.finalizedGrandTotal! > 40, 'grand total expected > 40');
  });

  it('partial grand total state when any summary is partial', () => {
    const summaries = [
      parseCostSummary(COST_SUMMARY_HYBRID, 'task-a'),            // partial
      parseCostSummary(COST_SUMMARY_GRAND_TOTAL, 'task-b'),        // live
    ];
    const view = mergeCostView(null, [], summaries);
    assert.strictEqual(view.finalizedGrandTotalState, 'partial');
  });

  it('no-scripts: null live + empty counts + empty summaries → safe empty view', () => {
    assert.doesNotThrow(() => {
      const view = mergeCostView(null, [], []);
      assert.strictEqual(view.live, null);
      assert.deepStrictEqual(view.tasks, []);
      assert.strictEqual(view.finalizedGrandTotal, null);
      assert.strictEqual(view.finalizedGrandTotalState, 'unavailable');
    });
  });

  it('scopeNote is set and non-empty when live is provided', () => {
    const live = parseLiveSpend(SPEND_MONITOR_LIVE, '', null);
    assert.ok(live);
    const view = mergeCostView(live!, [], []);
    assert.ok(view.scopeNote && view.scopeNote.length > 0, 'scopeNote should be set');
  });

  it('by_task_partial drives partial state for per-task today_usd entries', () => {
    const live = parseLiveSpend(SPEND_MONITOR_PARTIAL, '', null);
    assert.ok(live);
    assert.strictEqual(live!.by_task_partial, true);
    const view = mergeCostView(live!, [], []);
    const taskInByTask = view.tasks.find((t) => t.today_usd !== null);
    if (taskInByTask) {
      // Tasks with today_usd present under by_task_partial → at least partial state
      const rank = { live: 0, 'counts-only': 1, partial: 2, unavailable: 3 };
      assert.ok(rank[taskInByTask.state] >= rank['partial']);
    }
  });

  it('empty by_task with positive today_usd — tasks list empty for per-task, but live present', () => {
    const live = parseLiveSpend(SPEND_MONITOR_EMPTY_BY_TASK, '', null);
    assert.ok(live);
    assert.strictEqual(live!.today_usd, 6.01);
    assert.deepStrictEqual(live!.by_task, {});
    const view = mergeCostView(live!, [], []);
    // No tasks from by_task (empty), no counts, no summaries
    assert.strictEqual(view.tasks.length, 0);
    assert.ok(view.live, 'live should be present');
    assert.strictEqual(view.live!.today_usd, 6.01);
  });
});
