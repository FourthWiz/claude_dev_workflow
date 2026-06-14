/**
 * Cost fixtures — captured verbatim from real on-disk files.
 * Used by costService.test.ts to validate parsing logic.
 *
 * T-01: Four real divergent cost-summary.json shapes + spend_monitor + dashboard_model fixtures.
 */

// ── spend_monitor.py --json --scope project fixture shapes ───────────────────

/**
 * (a) Positive today_usd + non-empty by_task (normal live case)
 */
export const SPEND_MONITOR_LIVE = JSON.stringify({
  today_usd: 9.05,
  by_model: { "claude-opus-4-5": 8.00, "claude-haiku-3-5": 1.05 },
  by_model_pct: { "claude-opus-4-5": 88.4, "claude-haiku-3-5": 11.6 },
  by_task: { "vscode-extension": 7.50, "other-task": 1.55 },
  by_task_partial: false,
  scope: "project",
  stale: false,
});

/**
 * (b) today_usd: 0.0 + empty by_task (legitimate live zero — NOT unavailable)
 */
export const SPEND_MONITOR_ZERO = JSON.stringify({
  today_usd: 0.0,
  by_model: {},
  by_model_pct: {},
  by_task: {},
  by_task_partial: false,
  scope: "project",
  stale: false,
});

/**
 * (c) by_task_partial: true + non-empty by_task (partial — some sessions unresolved)
 */
export const SPEND_MONITOR_PARTIAL = JSON.stringify({
  today_usd: 15.45,
  by_model: { "claude-opus-4-5": 12.00, "claude-sonnet-4-5": 3.45 },
  by_model_pct: { "claude-opus-4-5": 77.7, "claude-sonnet-4-5": 22.3 },
  by_task: { "vscode-extension": 15.45 },
  by_task_partial: true,
  scope: "project",
  stale: false,
});

/**
 * (d) Positive today_usd + EMPTY by_task (project rows unresolved — per-task list may be incomplete).
 * UI must NOT imply the per-task list is exhaustive.
 */
export const SPEND_MONITOR_EMPTY_BY_TASK = JSON.stringify({
  today_usd: 6.01,
  by_model: { "claude-sonnet-4-5": 6.01 },
  by_model_pct: { "claude-sonnet-4-5": 100.0 },
  by_task: {},
  by_task_partial: false,
  scope: "project",
  stale: true,
});

// ── dashboard_model.py --json (counts-mode) fixture ──────────────────────────

/**
 * Counts-mode payload — per-task cost.usd is always null (counts-mode).
 * Used only to enumerate tasks/states, NOT for USD.
 */
export const DASHBOARD_MODEL_COUNTS = JSON.stringify({
  project_root: "/fake/project",
  active_task: "vscode-extension",
  tasks: [
    {
      name: "vscode-extension",
      stage: "5",
      finalized: false,
      last_activity: "2026-06-14",
      cost: {
        mode: "counts",
        usd: null,
        tokens: null,
        by_phase: {
          implement: 3,
          review: 2,
          plan: 1,
          gate: 4,
        },
      },
    },
    {
      name: "other-task",
      stage: null,
      finalized: false,
      last_activity: "2026-06-10",
      cost: {
        mode: "counts",
        usd: null,
        tokens: null,
        by_phase: {
          implement: 1,
          review: 1,
        },
      },
    },
  ],
});

// ── cost-summary.json fixture shapes (4 real divergent schemas) ───────────────

/**
 * (a) HYBRID active-task shape: per-stage blocks "S-1".."S-4" + summary block.
 * grand_total: 35.0, fallback_used: true → state should be 'partial' (NOT 'unavailable').
 * Captured verbatim from .workflow_artifacts/vscode-extension/cost-summary.json
 */
export const COST_SUMMARY_HYBRID = JSON.stringify({
  "S-1": {
    per_phase: {
      architect: null,
      critic: null,
      "thorough-plan": null,
      plan: null,
      gate: null,
      "implement+review+checkpoint": 9.05,
      "review-round-2": 6.40,
      "end-of-task": null,
    },
    task_total: 15.45,
    fallback_note:
      "5 of 7 UUIDs returned null from ccusage — no JSONL data found for those sessions.",
    uuids_with_data: [
      { uuid: "c9b45ef5-4bcc-4112-a3be-52910c303b2c", phases: ["implement", "review"], cost_usd: 9.05, tokens: 15093084 },
      { uuid: "0ca5b9eb-3046-4beb-b19c-f317804bae6d", phases: ["review-round-2"], cost_usd: 6.40, tokens: 7892268 },
    ],
  },
  "S-2": {
    per_phase: {
      "thorough-plan": null,
      plan: null,
      implement: null,
      review: null,
    },
    task_total: null,
    fallback_note: "S-2 UUIDs not resolved to JSONL files.",
  },
  "S-3": {
    per_phase: {
      "thorough-plan": null,
      plan: null,
      review: 6.01,
    },
    task_total: 6.01,
    uuids_with_data: [
      { uuid: "49af3178-276e-4eaf-af33-ec28c61e1017", phases: ["review(S3)"], cost_usd: 6.014237, tokens: 13608067 },
    ],
  },
  "S-4": {
    per_phase: {
      "thorough-plan": null,
      plan: null,
      implement: null,
      review: null,
    },
    task_total: null,
    fallback_note: "S-4 UUIDs are workflow placeholder IDs.",
  },
  per_phase: {
    architect: null,
    plan: null,
    review: 21.46,
    implement: null,
  },
  per_model: {
    opus: 16.33,
    sonnet: 17.35,
    haiku: 1.33,
  },
  task_total: 35.00,
  grand_total: 35.00,
  fallback_used: true,
  fallback_note:
    "Only 3 of 25 ledger UUIDs resolved to JSONL session files. Remaining UUIDs ran as subagents.",
  cumulative_tracked_cost_usd: 35.00,
  finalized_at: "2026-06-14",
  branch: "ivangorban/ivg-54-vscode-extension-s4",
});

/**
 * (b) grand_total + fallback_used:false (clean resolution).
 * Captured from .workflow_artifacts/finalized/dashboard-redesign/cost-summary.json
 */
export const COST_SUMMARY_GRAND_TOTAL = JSON.stringify({
  task_total: 12.237305,
  grand_total: 12.237305,
  fallback_used: false,
  per_phase: {
    plan: 1.2,
    implement: 7.5,
    review: 3.537305,
  },
});

/**
 * (c-1) Alternate key: total_usd (null in agentdesk-spend-pane — should be treated as no-total → unavailable).
 * Captured from .workflow_artifacts/finalized/agentdesk-spend-pane/cost-summary.json
 */
export const COST_SUMMARY_TOTAL_USD_NULL = JSON.stringify({
  task: "agentdesk-spend-pane",
  linear: "IVG-62",
  date: "2026-05-20",
  note: "Cost tracking not available for this task.",
  phases: ["plan", "implement", "review"],
  model_summary: { opus: "~60%", sonnet: "~40%" },
  total_usd: null,
  total_usd_note: "Not tracked via ccusage",
});

/**
 * (c-2) Alternate key: grand_total_usd (real value).
 * Captured from .workflow_artifacts/finalized/eod-rollup-and-approvals/cost-summary.json
 */
export const COST_SUMMARY_GRAND_TOTAL_USD = JSON.stringify({
  task: "eod-rollup-and-approvals",
  date: "2026-05-15",
  generated_at: "2026-05-15T18:00:00Z",
  commit_hash: "abc123",
  note: "End-of-day rollup and approvals implementation.",
  sessions: [],
  per_phase_totals: {},
  per_model_totals: { opus: 70.0, sonnet: 12.59 },
  grand_total_usd: 82.59,
  pricing_note: "Opus at $15/M, Sonnet at $3/M",
});

/**
 * (c-3) Alternate key: total_cost_usd (real value 0.0 — legitimate live zero → 'live').
 * Captured from .workflow_artifacts/finalized/ivg-69-test-suite-cleanup/cost-summary.json
 */
export const COST_SUMMARY_TOTAL_COST_USD = JSON.stringify({
  task: "ivg-69-test-suite-cleanup",
  generated: "2026-05-28",
  note: "Test suite cleanup task.",
  total_sessions_in_ledger: 5,
  sessions_with_uuids: 5,
  sessions_without_uuids: 0,
  total_cost_usd: 0.0,
  cost_data_available: true,
  by_phase: { implement: 0.0, review: 0.0 },
  by_model: { sonnet: 0.0 },
  stages: [],
});

/**
 * (d) NO resolvable total key at all → state must degrade to 'unavailable' gracefully.
 * Captured from .workflow_artifacts/finalized/agentdesk-remember-layout/cost-summary.json
 */
export const COST_SUMMARY_NO_TOTAL = JSON.stringify({
  task_name: "agentdesk-remember-layout",
  task_date: "2026-04-10",
  phases: ["plan", "implement", "review"],
  total_phases: 3,
  opus_phases: 2,
  sonnet_phases: 1,
  note: "Layout memory implementation. Cost not tracked.",
});

// ── Parsed object versions (for tests that need typed access) ────────────────

export const SPEND_MONITOR_LIVE_OBJ = JSON.parse(SPEND_MONITOR_LIVE) as {
  today_usd: number;
  by_model: Record<string, number>;
  by_model_pct: Record<string, number>;
  by_task: Record<string, number>;
  by_task_partial: boolean;
  scope: string;
  stale: boolean;
};

export const DASHBOARD_MODEL_COUNTS_OBJ = JSON.parse(DASHBOARD_MODEL_COUNTS) as {
  project_root: string;
  active_task: string | null;
  tasks: Array<{
    name: string;
    stage: string | null;
    finalized: boolean;
    last_activity: string | null;
    cost: {
      mode: string;
      usd: number | null;
      tokens: number | null;
      by_phase: Record<string, number>;
    };
  }>;
};
