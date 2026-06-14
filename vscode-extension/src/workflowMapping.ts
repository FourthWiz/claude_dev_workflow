export type NodeState = 'done' | 'active' | 'future';

export interface WorkflowNode {
  node: string;
  state: NodeState;
  critic_rounds?: number;
  review_rounds?: number;
}

/** Canonical pipeline order — mirrors _PIPELINE in status_graph.py */
export const PIPELINE: readonly string[] = [
  'discover', 'architect', 'thorough_plan', 'implement', 'review', 'end_of_task',
];

/** Maps detect_phase() output → which pipeline node is active — mirrors _PHASE_TO_NODE */
export const PHASE_TO_NODE: Record<string, string> = {
  'discover':        'discover',
  'architecture':    'architect',
  'planning':        'thorough_plan',
  'plan-gated':      'thorough_plan',
  'implement':       'implement',
  'implement-gated': 'implement',
  'review':          'review',
  'review-gated':    'review',
  'done':            'end_of_task',
};

/**
 * Maps active pipeline node → the next skill to highlight.
 * 'end_of_task' → null is defensive only: end_of_task node is never active
 * in the auto-select path (detect_phase returns 'done' only for finalized tasks
 * which pick_active_task excludes).
 */
export const NEXT_SKILL: Record<string, string | null> = {
  'discover':     'architect',
  'architect':    'thorough_plan',
  'thorough_plan': 'implement',
  'implement':    'review',
  'review':       'end_of_task',
  'end_of_task':  null,
};

export function getNextSkill(activeNode: string | null): string | null {
  if (activeNode === null) { return null; }
  return NEXT_SKILL[activeNode] ?? null;
}
